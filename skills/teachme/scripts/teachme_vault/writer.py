"""Non-destructive vault-native note generation, transactional multi-file apply, and audit."""

from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Any, Callable

from .discovery import discover_vault
from .indexer import build_or_update_index, load_or_build_index, resolve_link_to_rel_path
from .markdown_utils import (
    FENCE_RE,
    WIKILINK_RE,
    heading_slug,
    parse_frontmatter_tolerant,
    parse_wikilink_parts,
)
from .mermaid import validate_mermaid_syntax
from .models import (
    atomic_write_text,
    is_within_root,
    read_text_safe,
    resolve_state_dir,
    sha256_text,
    utc_now_iso,
)
from .planner import load_reviewed_plan, plan_note, validate_reviewed_plan
from .renderer import serialize_frontmatter  # noqa: F401  (re-exported for compatibility)

PROTECTED_SUFFIXES = (".excalidraw.md", ".excalidraw", ".canvas", ".base")
TEACHME_MERMAID_BLOCK_RE = re.compile(
    r"<!--\s*teachme:mermaid:start\s+id=[^\s>]+\s*-->\s*```mermaid\s*([\s\S]*?)```\s*<!--\s*teachme:mermaid:end\s*-->",
    re.MULTILINE,
)
TEACHME_EXT_BLOCK_RE = re.compile(
    r"<!--\s*teachme:extension:start\b[^>]*-->[\s\S]*?<!--\s*teachme:extension:end\s*-->",
    re.MULTILINE,
)


def _slugify(text: str) -> str:
    clean = re.sub(r"[^\w]+", "-", text.lower(), flags=re.UNICODE).strip("-_")
    if clean and re.fullmatch(r"[a-z0-9-]+", clean):
        return clean
    digest = sha256_text(text)[:6]
    return f"{clean}-{digest}" if clean else f"topic-{digest}"


def _load_managed_manifest(state_dir: Path) -> dict[str, Any]:
    mpath = state_dir / "managed-notes.json"
    if mpath.is_file():
        try:
            data = json.loads(read_text_safe(mpath))
            if isinstance(data, dict):
                data.setdefault("notes", {})
                data.setdefault("moc_updates", {})
                return data
        except (OSError, json.JSONDecodeError):
            pass
    return {"schema_version": 2, "notes": {}, "moc_updates": {}}


def _save_managed_manifest(state_dir: Path, manifest: dict[str, Any]) -> None:
    state_dir.mkdir(parents=True, exist_ok=True)
    atomic_write_text(
        state_dir / "managed-notes.json",
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
    )


def _create_backup(state_dir: Path, rel_path: str, text: str) -> str:
    backup_dir = state_dir / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = utc_now_iso().replace(":", "").replace("-", "")
    safe_name = rel_path.replace("/", "__")
    bpath = backup_dir / f"{stamp}__{safe_name}"
    atomic_write_text(bpath, text)
    return bpath.relative_to(state_dir).as_posix()


def _init_isolated_session(
    vault_root: Path,
    state_dir: Path,
    topic: str,
    target_rel_path: str,
) -> Path:
    """Initialize isolated TeachMe session state inside .teachme/sessions/<topic-slug>/."""
    slug = _slugify(topic)
    sess_dir = state_dir / "sessions" / slug
    (sess_dir / "learning-records").mkdir(parents=True, exist_ok=True)
    (sess_dir / "scratchpad").mkdir(parents=True, exist_ok=True)
    state_file = sess_dir / "00-SESSION-STATE.md"
    if not state_file.exists():
        lines = [
            f"# Session State: {topic}",
            "",
            "- **Vault Mode:** `vault-native`",
            f"- **Vault Root:** `{vault_root}`",
            f"- **Active Note:** `{target_rel_path}`",
            "- **Live Stage & Checkpoint:** `Depth Stage 1/3 | Checkpoint [1/4]`",
            "- **Last Verified Invariant:** Vault-native note planned/created.",
        ]
        atomic_write_text(state_file, "\n".join(lines) + "\n")
    return sess_dir


def _is_protected_relpath(rel_path: str, protected_folders: list[str]) -> bool:
    low = rel_path.lower()
    if any(low.endswith(suf) for suf in PROTECTED_SUFFIXES):
        return True
    for pf in protected_folders:
        clean_pf = pf.strip("/")
        if clean_pf and (rel_path == clean_pf or rel_path.startswith(clean_pf + "/")):
            return True
    return False


def _check_wikilink_target(
    parts: dict[str, Any],
    rel: str,
    line_no: int,
    index: dict[str, Any],
    vault_root: Path,
    created_rel_paths: set[str] | None,
    errors: list[dict[str, Any]],
    warnings: list[dict[str, Any]],
    check_anchors: bool = True,
) -> None:
    """Shared link & attachment resolution used identically by preflight and audit."""
    target = parts.get("note", "")
    if not target:
        return
    res = resolve_link_to_rel_path(
        target,
        index,
        extra_rel_paths=created_rel_paths,
        vault_root=vault_root,
    )
    if res.get("is_attachment"):
        if res["resolved"]:
            return
        if res["ambiguous"]:
            warnings.append(
                {
                    "file": rel,
                    "line": line_no,
                    "type": "ambiguous_attachment",
                    "detail": f"Ambiguous attachment [[{target}]]",
                }
            )
            return
        errors.append(
            {
                "file": rel,
                "line": line_no,
                "type": "missing_attachment",
                "detail": f"Missing attachment [[{parts['raw']}]]",
            }
        )
        return

    if res["ambiguous"]:
        warnings.append(
            {
                "file": rel,
                "line": line_no,
                "type": "ambiguous_wikilink",
                "detail": f"Ambiguous target [[{target}]]",
            }
        )
        return

    resolved_rel = res["resolved"]
    if not resolved_rel:
        errors.append(
            {
                "file": rel,
                "line": line_no,
                "type": "broken_wikilink",
                "detail": f"Unresolved wikilink [[{parts['raw']}]]",
            }
        )
        return

    if check_anchors and parts.get("anchor"):
        target_doc = index.get("docs", {}).get(resolved_rel)
        if target_doc is not None:
            anc = parts["anchor"]
            if anc.startswith("^"):
                bid = anc[1:]
                if bid not in target_doc.get("block_ids", []):
                    warnings.append(
                        {
                            "file": rel,
                            "line": line_no,
                            "type": "missing_block_id",
                            "detail": f"Block ID ^{bid} not found in {resolved_rel}",
                        }
                    )
            else:
                slug = heading_slug(anc)
                if slug not in target_doc.get("heading_slugs", []):
                    warnings.append(
                        {
                            "file": rel,
                            "line": line_no,
                            "type": "missing_heading_anchor",
                            "detail": f"Heading #{anc} not found in {resolved_rel}",
                        }
                    )


def _extract_extension_regions(text: str) -> list[tuple[int, str]]:
    """Return (start_line_no, region_text) for EVERY TeachMe extension region in text."""
    regions: list[tuple[int, str]] = []
    covered_spans: list[tuple[int, int]] = []

    for m in TEACHME_EXT_BLOCK_RE.finditer(text):
        start_line = text[: m.start()].count("\n") + 1
        regions.append((start_line, m.group(0)))
        covered_spans.append((m.start(), m.end()))

    # Also detect any legacy unmarked `## TeachMe Extension:` tail outside marked spans
    for m in re.finditer(r"^## TeachMe Extension:.*$", text, flags=re.MULTILINE):
        pos = m.start()
        if any(s <= pos <= e for s, e in covered_spans):
            continue
        start_line = text[:pos].count("\n") + 1
        regions.append((start_line, text[pos:]))
        break

    return regions


def _audit_lines_for_links_and_math(
    rel: str,
    text_lines: list[tuple[int, str]],
    index: dict[str, Any],
    vault_root: Path,
    errors: list[dict[str, Any]],
    warnings: list[dict[str, Any]],
    check_math: bool = True,
    created_rel_paths: set[str] | None = None,
    check_anchors: bool = True,
) -> None:
    """Audit specific line ranges for math parity and broken/ambiguous wikilinks & attachments."""
    in_fence = False
    fence_char = ""
    in_display = False
    for line_no, line in text_lines:
        fm_match = FENCE_RE.match(line)
        if fm_match:
            mk = fm_match.group(1)
            if not in_fence:
                in_fence = True
                fence_char = mk[0]
            elif mk[0] == fence_char:
                in_fence = False
            continue
        if in_fence:
            continue

        no_code = re.sub(r"`[^`\r\n]*`", "", line).replace(r"\$", "")
        if check_math:
            if no_code.count("$$") % 2 == 1:
                in_display = not in_display
            no_dd = no_code.replace("$$", "")
            if not in_display and no_dd.count("$") % 2 == 1:
                errors.append(
                    {
                        "file": rel,
                        "line": line_no,
                        "type": "unmatched_dollar",
                        "detail": "Odd number of $ delimiters",
                    }
                )

        for wm in WIKILINK_RE.finditer(no_code):
            parts = parse_wikilink_parts(wm.group(2), is_embed=bool(wm.group(1)))
            _check_wikilink_target(
                parts=parts,
                rel=rel,
                line_no=line_no,
                index=index,
                vault_root=vault_root,
                created_rel_paths=created_rel_paths,
                errors=errors,
                warnings=warnings,
                check_anchors=check_anchors,
            )

    if check_math and in_display:
        errors.append(
            {
                "file": rel,
                "line": 1,
                "type": "unclosed_display_math",
                "detail": "Unclosed $$ block",
            }
        )


def _validate_generated_text(
    rel_path: str,
    text: str,
    orig_text: str,
    role: str,
    action: str,
    inserted_line: str,
    index: dict[str, Any],
    vault_root: Path,
    created_rel_paths: set[str],
) -> list[str]:
    """Validate proposed file content before writing any files to disk."""
    errors_dicts: list[dict[str, Any]] = []
    warnings_dicts: list[dict[str, Any]] = []

    if role == "moc_update" and action == "insert_section_line":
        for wm in WIKILINK_RE.finditer(inserted_line):
            parts = parse_wikilink_parts(wm.group(2), is_embed=bool(wm.group(1)))
            _check_wikilink_target(
                parts=parts,
                rel=rel_path,
                line_no=1,
                index=index,
                vault_root=vault_root,
                created_rel_paths=created_rel_paths,
                errors=errors_dicts,
                warnings=warnings_dicts,
                check_anchors=False,
            )
        return [f"{e['file']}: {e['detail']}" for e in errors_dicts]

    if action == "create":
        fm = parse_frontmatter_tolerant(text)
        for w in fm["warnings"]:
            errors_dicts.append({"file": rel_path, "line": 1, "type": "yaml_syntax", "detail": w})

    if action == "extend":
        # Validate EVERY newly added or modified TeachMe extension region (not just the first!)
        orig_regions = {reg_text for _, reg_text in _extract_extension_regions(orig_text)}
        new_regions = _extract_extension_regions(text)
        regions_to_check = [
            (start_ln, reg_text)
            for start_ln, reg_text in new_regions
            if reg_text not in orig_regions
        ]
        # If none differed by exact match (or unmarked), validate all extension regions found
        if not regions_to_check and new_regions:
            regions_to_check = new_regions
        for start_ln, reg_text in regions_to_check:
            numbered = [(start_ln + i, ln) for i, ln in enumerate(reg_text.splitlines())]
            _audit_lines_for_links_and_math(
                rel_path,
                numbered,
                index=index,
                vault_root=vault_root,
                errors=errors_dicts,
                warnings=warnings_dicts,
                check_math=True,
                created_rel_paths=created_rel_paths,
                check_anchors=False,
            )
            for mm in TEACHME_MERMAID_BLOCK_RE.finditer(reg_text):
                m_val = validate_mermaid_syntax(mm.group(1))
                if not m_val["valid"]:
                    for err in m_val["errors"]:
                        errors_dicts.append(
                            {"file": rel_path, "line": start_ln, "type": "invalid_mermaid", "detail": f"Invalid Mermaid diagram: {err}"}
                        )
    else:
        numbered = list(enumerate(text.splitlines(), start=1))
        _audit_lines_for_links_and_math(
            rel_path,
            numbered,
            index=index,
            vault_root=vault_root,
            errors=errors_dicts,
            warnings=warnings_dicts,
            check_math=True,
            created_rel_paths=created_rel_paths,
            check_anchors=False,
        )
        for mm in TEACHME_MERMAID_BLOCK_RE.finditer(text):
            m_val = validate_mermaid_syntax(mm.group(1))
            if not m_val["valid"]:
                for err in m_val["errors"]:
                    errors_dicts.append(
                        {"file": rel_path, "line": 1, "type": "invalid_mermaid", "detail": f"Invalid Mermaid diagram: {err}"}
                    )

    return [f"{e['file']}:{e['line']}: {e['detail']}" for e in errors_dicts]


def _execute_file_transaction(
    vault_root: Path,
    state_dir: Path,
    affected_files: list[dict[str, Any]],
    index: dict[str, Any],
    protected_folders: list[str],
    write_fn: Callable[[Path, str], None] | None = None,
) -> dict[str, Any]:
    """Validate all edits, back up modified files, and apply per-file atomic writes with rollback."""
    root = vault_root.resolve()
    writer = write_fn or atomic_write_text

    # 1. Pre-validation & staleness/concurrent-edit detection
    created_rel_paths: set[str] = {
        af["rel_path"] for af in affected_files if af.get("action") == "create"
    }
    prepared_ops: list[dict[str, Any]] = []
    validation_errors: list[str] = []

    for af in affected_files:
        rel = af["rel_path"]
        abs_path = (root / rel).resolve()
        if not is_within_root(abs_path, root):
            raise ValueError(f"Refusing path outside vault root: {rel}")
        if _is_protected_relpath(rel, protected_folders):
            raise ValueError(f"Refusing to modify protected asset: {rel}")

        must_not_exist = bool(af.get("must_not_exist"))
        expected_sha = af.get("expected_sha256")
        existed = abs_path.exists()

        if must_not_exist and existed:
            raise RuntimeError(f"Stale plan conflict: target '{rel}' already exists on disk")
        if expected_sha is not None:
            if not abs_path.is_file():
                raise RuntimeError(f"Stale plan conflict: expected existing file '{rel}' is missing")
            disk_sha = sha256_text(read_text_safe(abs_path))
            if disk_sha != expected_sha:
                raise RuntimeError(
                    f"Concurrent edit / stale plan detected for '{rel}' (expected {expected_sha[:12]}, got {disk_sha[:12]})"
                )

        new_text = af.get("new_text", "")
        orig_text = read_text_safe(abs_path) if existed else ""
        if existed and orig_text == new_text:
            continue

        errs = _validate_generated_text(
            rel_path=rel,
            text=new_text,
            orig_text=orig_text,
            role=af.get("role", "target_note"),
            action=af.get("action", "create"),
            inserted_line=af.get("inserted_line", ""),
            index=index,
            vault_root=root,
            created_rel_paths=created_rel_paths,
        )
        validation_errors.extend(errs)

        prepared_ops.append(
            {
                "rel_path": rel,
                "abs_path": abs_path,
                "role": af.get("role", "target_note"),
                "action": af.get("action", "create"),
                "existed": existed,
                "must_not_exist": must_not_exist,
                "expected_sha256": expected_sha,
                "orig_text": orig_text,
                "new_text": new_text,
                "new_sha256": sha256_text(new_text),
                "inserted_line": af.get("inserted_line", ""),
                "backup_rel_path": "",
            }
        )

    if validation_errors:
        raise ValueError("Pre-write validation failed: " + "; ".join(validation_errors))

    if not prepared_ops:
        return {
            "tx_id": None,
            "status": "no_changes",
            "writes_committed": False,
            "written_files": [],
            "backups": {},
            "atomicity": "per_file_atomic_with_rollback",
            "post_commit_warnings": [],
        }

    # 2. Backups & transaction journal
    tx_dir = state_dir / "transactions"
    tx_dir.mkdir(parents=True, exist_ok=True)
    stamp = utc_now_iso().replace(":", "").replace("-", "")
    tx_id = f"tx-{stamp}-{sha256_text(','.join(op['rel_path'] for op in prepared_ops))[:8]}"
    journal_path = tx_dir / f"{tx_id}.json"

    backups: dict[str, str] = {}
    for op in prepared_ops:
        if op["existed"]:
            brel = _create_backup(state_dir, op["rel_path"], op["orig_text"])
            op["backup_rel_path"] = brel
            backups[op["rel_path"]] = brel

    journal: dict[str, Any] = {
        "tx_id": tx_id,
        "created_at": utc_now_iso(),
        "status": "pending",
        "atomicity": "per_file_atomic_with_rollback",
        "ops": [
            {
                "rel_path": op["rel_path"],
                "role": op["role"],
                "action": op["action"],
                "existed": op["existed"],
                "backup_rel_path": op["backup_rel_path"],
                "new_sha256": op["new_sha256"],
            }
            for op in prepared_ops
        ],
    }
    atomic_write_text(journal_path, json.dumps(journal, indent=2, ensure_ascii=False) + "\n")

    # 3. Apply per-file atomic writes with immediate pre-write concurrent-edit guard & safe rollback
    completed: list[dict[str, Any]] = []
    try:
        for op in prepared_ops:
            abs_p = op["abs_path"]
            if op["must_not_exist"] and abs_p.exists():
                raise RuntimeError(f"Concurrent creation detected right before write for '{op['rel_path']}'")
            if op["expected_sha256"] is not None:
                if not abs_p.is_file():
                    raise RuntimeError(f"Concurrent deletion detected right before write for '{op['rel_path']}'")
                cur_sha = sha256_text(read_text_safe(abs_p))
                if cur_sha != op["expected_sha256"]:
                    raise RuntimeError(f"Concurrent edit detected right before write for '{op['rel_path']}'")
            writer(abs_p, op["new_text"])
            completed.append(op)
    except Exception as exc:
        rollback_errors: list[str] = []
        rollback_warnings: list[str] = []
        for comp in reversed(completed):
            try:
                abs_c = comp["abs_path"]
                if abs_c.is_file():
                    post_write_sha = sha256_text(read_text_safe(abs_c))
                    if post_write_sha != comp["new_sha256"]:
                        rollback_warnings.append(
                            f"Skipped rollback of '{comp['rel_path']}' because it was modified externally after write"
                        )
                        continue
                if comp["existed"]:
                    atomic_write_text(abs_c, comp["orig_text"])
                else:
                    if abs_c.exists():
                        abs_c.unlink()
            except Exception as rb_exc:
                rollback_errors.append(f"{comp['rel_path']}: {rb_exc}")

        journal["status"] = "rolled_back" if not rollback_errors else "rollback_partial_error"
        journal["error"] = str(exc)
        journal["rollback_errors"] = rollback_errors
        journal["rollback_warnings"] = rollback_warnings
        try:
            atomic_write_text(journal_path, json.dumps(journal, indent=2, ensure_ascii=False) + "\n")
        except OSError:
            pass
        raise RuntimeError(f"Transaction {tx_id} failed and rolled back: {exc}") from exc

    # All target writes succeeded and are committed on disk.
    post_commit_warnings: list[str] = []
    journal["status"] = "committed"
    journal["committed_at"] = utc_now_iso()
    try:
        atomic_write_text(journal_path, json.dumps(journal, indent=2, ensure_ascii=False) + "\n")
    except Exception as j_exc:
        post_commit_warnings.append(f"Target writes committed, but journal finalization failed: {j_exc}")

    return {
        "tx_id": tx_id,
        "journal_path": str(journal_path),
        "status": "committed",
        "writes_committed": True,
        "written_files": [op["rel_path"] for op in prepared_ops],
        "backups": backups,
        "atomicity": "per_file_atomic_with_rollback",
        "post_commit_warnings": post_commit_warnings,
        "ops": prepared_ops,
    }


def generate_vault_note(
    vault_root: Path,
    topic: str = "",
    apply: bool = False,
    explicit_folder: str | None = None,
    explicit_template: str | None = None,
    extend_rel_path: str | None = None,
    content: dict[str, Any] | None = None,
    expected_hash: str | None = None,
    state_dir: Path | None = None,
    keywords: list[str] | None = None,
    proposal: dict[str, Any] | None = None,
    plan_ref: str | Path | dict[str, Any] | None = None,
    expected_plan_hash: str | None = None,
    mermaid_mode: str = "auto",
    mindmap_supported: bool = True,
    min_moc_cluster_size: int | None = None,
    allow_moc: bool = True,
    write_fn: Callable[[Path, str], None] | None = None,
    post_commit_fn: Callable[[], None] | None = None,
) -> dict[str, Any]:
    """Plan and generate (or non-destructively extend) vault-native notes + MOCs + Mermaid."""
    root = vault_root.resolve()
    sdir = state_dir or resolve_state_dir(root)

    if plan_ref is not None:
        plan = load_reviewed_plan(root, plan_ref, state_dir=sdir)
        validate_reviewed_plan(plan, root, expected_plan_hash=expected_plan_hash)
        topic = topic or str(plan.get("topic", ""))
    else:
        if not topic:
            raise ValueError("topic is required when no --plan is provided")
        plan = plan_note(
            vault_root=root,
            topic=topic,
            explicit_folder=explicit_folder,
            explicit_template=explicit_template,
            keywords=keywords,
            state_dir=sdir,
            content=content,
            proposal=proposal,
            extend_rel_path=extend_rel_path,
            mermaid_mode=mermaid_mode,
            mindmap_supported=mindmap_supported,
            min_moc_cluster_size=min_moc_cluster_size,
            allow_moc=allow_moc,
            save_plan=not apply,
        )

    affected_files: list[dict[str, Any]] = plan.get("affected_files", [])
    target_af = next((af for af in affected_files if af.get("role") == "target_note"), affected_files[0])
    target_rel = target_af["rel_path"]
    target_abs = (root / target_rel).resolve()
    mode = "extend" if target_af.get("action") == "extend" else "create"

    if not is_within_root(target_abs, root):
        raise ValueError(f"Refusing path outside vault root: {target_rel}")

    if mode == "extend" and expected_hash:
        if not target_abs.is_file():
            raise FileNotFoundError(f"Cannot extend missing note: {target_rel}")
        cur_hash = sha256_text(read_text_safe(target_abs))
        if cur_hash != expected_hash:
            raise RuntimeError(f"Conflict detected for {target_rel}: file changed since inspection")

    if target_af.get("conflict"):
        return {
            "ok": False,
            "status": "conflict",
            "conflict": True,
            "applied": False,
            "writes_committed": False,
            "audit_passed": None,
            "mode": mode,
            "target_rel_path": target_rel,
            "reason": target_af.get("conflict_reason") or "Target note already exists. Use --extend or choose another title/folder.",
            "resolution_options": plan.get("resolution_options", []),
            "plan_id": plan.get("plan_id"),
            "plan_hash": plan.get("plan_hash"),
            "plan": plan,
        }

    combined_diff = "\n".join(af.get("diff", "") for af in affected_files if af.get("diff"))
    backup_rel = ""
    tx_info: dict[str, Any] = {}
    audit_report: dict[str, Any] | None = None
    post_commit_errors: list[str] = []

    if apply:
        index = load_or_build_index(root, refresh=False, state_dir=sdir)
        protected_folders = plan.get("plugin_conventions", {}).get("protected_folders", [])
        tx_info = _execute_file_transaction(
            vault_root=root,
            state_dir=sdir,
            affected_files=affected_files,
            index=index,
            protected_folders=protected_folders,
            write_fn=write_fn,
        )
        backup_rel = tx_info.get("backups", {}).get(target_rel, "")
        post_commit_errors.extend(tx_info.get("post_commit_warnings", []))

        # Writes are already committed on disk; record any post-commit bookkeeping issues
        # without ever falsely claiming the transaction rolled back.
        try:
            if post_commit_fn is not None:
                post_commit_fn()
            manifest = _load_managed_manifest(sdir)
            for op in tx_info.get("ops", []):
                rel = op["rel_path"]
                role = op["role"]
                if role == "moc_update":
                    entry = manifest["moc_updates"].get(rel, {"added_lines": [], "backups": []})
                    if op["inserted_line"] and op["inserted_line"] not in entry["added_lines"]:
                        entry["added_lines"].append(op["inserted_line"])
                    if op["backup_rel_path"]:
                        entry["backups"].append(op["backup_rel_path"])
                    entry["updated_at"] = utc_now_iso()
                    entry["sha256"] = op["new_sha256"]
                    manifest["moc_updates"][rel] = entry
                else:
                    manifest["notes"][rel] = {
                        "topic": topic,
                        "mode": "moc_create" if role == "moc_create" else mode,
                        "updated_at": utc_now_iso(),
                        "sha256": op["new_sha256"],
                        "backup": op["backup_rel_path"],
                    }
            _save_managed_manifest(sdir, manifest)

            sess_dir = _init_isolated_session(root, sdir, topic, target_rel)
            refreshed_index = build_or_update_index(root, full=False, state_dir=sdir)
            discover_vault(root, refresh=False, state_dir=sdir)

            audit_files = [af["rel_path"] for af in affected_files]
            audit_report = audit_vault_native(root, target_files=audit_files, state_dir=sdir, index=refreshed_index)
        except Exception as pc_exc:
            post_commit_errors.append(f"Post-commit bookkeeping/audit error (writes remain committed): {pc_exc}")
            sess_dir = sdir / "sessions" / _slugify(topic)
            audit_report = {
                "vault_path": str(root),
                "mode": "vault-native",
                "audited_files": [],
                "audited_moc_updates": [],
                "errors": [{"file": target_rel, "line": 1, "type": "post_commit_bookkeeping_error", "detail": str(pc_exc)}],
                "warnings": [],
                "pre_existing_issues": [],
                "user_notes_untouched": True,
            }

        writes_committed = bool(tx_info.get("writes_committed"))
        tx_status = tx_info.get("status", "committed")
        audit_passed = bool(audit_report is not None and len(audit_report.get("errors", [])) == 0)
        if not audit_passed:
            overall_status = "applied_audit_failed"
        elif tx_status == "no_changes":
            overall_status = "applied_no_changes"
        else:
            overall_status = "applied_and_audited"
        overall_ok = audit_passed and not post_commit_errors
    else:
        sess_dir = sdir / "sessions" / _slugify(topic)
        writes_committed = False
        tx_status = "dry_run"
        audit_passed = None
        overall_status = "dry_run"
        overall_ok = True

    return {
        "ok": overall_ok,
        "status": overall_status,
        "applied": apply,
        "dry_run": not apply,
        "writes_committed": writes_committed,
        "transaction_status": tx_status,
        "audit_passed": audit_passed,
        "post_commit_errors": post_commit_errors,
        "mode": mode,
        "plan_id": plan.get("plan_id"),
        "plan_hash": plan.get("plan_hash"),
        "plan_file": plan.get("plan_file", ""),
        "target_rel_path": target_rel,
        "target_abs_path": str(target_abs),
        "backup_rel_path": backup_rel,
        "preserved_dynamic_expressions": target_af.get("preserved_dynamic_expressions", []),
        "affected_files": [
            {k: v for k, v in af.items() if k != "new_text"}
            for af in affected_files
        ],
        "expected_hashes": plan.get("expected_hashes", {}),
        "transaction": {k: v for k, v in tx_info.items() if k != "ops"} if tx_info else None,
        "audit": audit_report,
        "diff": combined_diff,
        "preview": target_af.get("new_text", "") if not apply else "",
        "session_dir": str(sess_dir),
        "plan": plan,
    }


def audit_vault_native(
    vault_root: Path,
    target_files: list[str] | None = None,
    state_dir: Path | None = None,
    index: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Audit ONLY TeachMe-managed notes, extensions, and added MOC entries (never blaming pre-existing user issues)."""
    root = vault_root.resolve()
    sdir = state_dir or resolve_state_dir(root)
    manifest = _load_managed_manifest(sdir)
    idx_data = index if index is not None else load_or_build_index(root, refresh=False, state_dir=sdir)

    managed_notes = manifest.get("notes", {})
    moc_updates = manifest.get("moc_updates", {})

    if target_files:
        candidates = [f.strip().lstrip("/") for f in target_files if f.strip()]
    else:
        candidates = sorted(set(managed_notes.keys()) | set(moc_updates.keys()))

    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    pre_existing_issues: list[dict[str, Any]] = []
    audited: list[str] = []
    audited_moc_updates: list[str] = []

    for rel in candidates:
        fpath = (root / rel).resolve()
        if not fpath.is_file() or not is_within_root(fpath, root):
            errors.append({"file": rel, "line": 1, "type": "missing_managed_file", "detail": "File does not exist"})
            continue

        text = read_text_safe(fpath)
        note_meta = managed_notes.get(rel)
        moc_meta = moc_updates.get(rel)

        # Case 1: Updated existing MOC (audit ONLY TeachMe-added lines; report pre-existing broken links separately)
        if moc_meta and not note_meta:
            audited_moc_updates.append(rel)
            added_set = {ln.strip() for ln in moc_meta.get("added_lines", []) if ln.strip()}
            added_numbered: list[tuple[int, str]] = []
            user_numbered: list[tuple[int, str]] = []
            for idx, ln in enumerate(text.splitlines(), start=1):
                if ln.strip() in added_set:
                    added_numbered.append((idx, ln))
                else:
                    user_numbered.append((idx, ln))
            _audit_lines_for_links_and_math(
                rel, added_numbered, idx_data, root, errors, warnings, check_math=False
            )
            pre_errs: list[dict[str, Any]] = []
            pre_warns: list[dict[str, Any]] = []
            _audit_lines_for_links_and_math(
                rel, user_numbered, idx_data, root, pre_errs, pre_warns, check_math=False
            )
            for pe in pre_errs:
                pe["pre_existing"] = True
                pre_existing_issues.append(pe)
            continue

        audited.append(rel)

        # Case 2: Extended existing user note (audit ONLY TeachMe Extension blocks; preserve user YAML/content)
        if note_meta and note_meta.get("mode") == "extend":
            all_lines = text.splitlines()
            ext_lines: list[tuple[int, str]] = []
            user_lines: list[tuple[int, str]] = []
            in_ext = False
            for idx, ln in enumerate(all_lines, start=1):
                if "<!-- teachme:extension:start" in ln or ln.startswith("## TeachMe Extension:"):
                    in_ext = True
                if in_ext:
                    ext_lines.append((idx, ln))
                else:
                    user_lines.append((idx, ln))
                if in_ext and "<!-- teachme:extension:end" in ln:
                    in_ext = False
            _audit_lines_for_links_and_math(
                rel, ext_lines, idx_data, root, errors, warnings, check_math=True
            )
            ext_text = "\n".join(ln for _, ln in ext_lines)
            for mm in TEACHME_MERMAID_BLOCK_RE.finditer(ext_text):
                m_val = validate_mermaid_syntax(mm.group(1))
                if not m_val["valid"]:
                    for err in m_val["errors"]:
                        errors.append({"file": rel, "line": 1, "type": "invalid_mermaid", "detail": err})

            pre_errs = []
            pre_warns = []
            _audit_lines_for_links_and_math(
                rel, user_lines, idx_data, root, pre_errs, pre_warns, check_math=False
            )
            for pe in pre_errs:
                pe["pre_existing"] = True
                pre_existing_issues.append(pe)
            continue

        # Case 3: TeachMe-created note or newly created MOC
        fm = parse_frontmatter_tolerant(text)
        for w in fm["warnings"]:
            errors.append({"file": rel, "line": 1, "type": "yaml_syntax", "detail": w})
        numbered = list(enumerate(text.splitlines(), start=1))
        _audit_lines_for_links_and_math(
            rel, numbered, idx_data, root, errors, warnings, check_math=True
        )
        for mm in TEACHME_MERMAID_BLOCK_RE.finditer(text):
            m_val = validate_mermaid_syntax(mm.group(1))
            if not m_val["valid"]:
                for err in m_val["errors"]:
                    errors.append({"file": rel, "line": 1, "type": "invalid_mermaid", "detail": err})

    return {
        "vault_path": str(root),
        "mode": "vault-native",
        "audited_files": audited,
        "audited_moc_updates": audited_moc_updates,
        "errors": errors,
        "warnings": warnings,
        "pre_existing_issues": pre_existing_issues,
        "user_notes_untouched": True,
    }
