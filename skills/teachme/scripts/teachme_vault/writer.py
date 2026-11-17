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
from .planner import load_reviewed_plan, plan_note
from .renderer import serialize_frontmatter  # noqa: F401  (re-exported for compatibility)

PROTECTED_SUFFIXES = (".excalidraw.md", ".excalidraw", ".canvas", ".base")
TEACHME_MERMAID_BLOCK_RE = re.compile(
    r"<!--\s*teachme:mermaid:start\s+id=[^\s>]+\s*-->\s*```mermaid\s*([\s\S]*?)```\s*<!--\s*teachme:mermaid:end\s*-->",
    re.MULTILINE,
)


def _slugify(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return s or "topic"


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


def _validate_generated_text(
    rel_path: str,
    text: str,
    role: str,
    action: str,
    inserted_line: str,
    index: dict[str, Any],
    created_rel_paths: set[str],
) -> list[str]:
    """Validate proposed file content before writing any files to disk."""
    errors: list[str] = []

    if role == "moc_update" and action == "insert_section_line":
        for wm in WIKILINK_RE.finditer(inserted_line):
            parts = parse_wikilink_parts(wm.group(2), is_embed=bool(wm.group(1)))
            if parts["note"]:
                res = resolve_link_to_rel_path(parts["note"], index, extra_rel_paths=created_rel_paths)
                if not res["resolved"] and not res["ambiguous"]:
                    errors.append(f"{rel_path}: Inserted MOC link [[{parts['raw']}]] does not resolve")
        return errors

    if action in ("create",):
        fm = parse_frontmatter_tolerant(text)
        for w in fm["warnings"]:
            errors.append(f"{rel_path}: YAML warning: {w}")

    # Check math parity and wikilinks in newly generated text (or extension slice)
    text_to_check = text
    if action == "extend":
        m = re.search(r"<!--\s*teachme:extension:start\b[\s\S]*?<!--\s*teachme:extension:end\s*-->", text)
        if m:
            text_to_check = m.group(0)

    in_fence = False
    fence_char = ""
    in_display = False
    for line_no, line in enumerate(text_to_check.splitlines(), start=1):
        fm_m = FENCE_RE.match(line)
        if fm_m:
            mk = fm_m.group(1)
            if not in_fence:
                in_fence = True
                fence_char = mk[0]
            elif mk[0] == fence_char:
                in_fence = False
            continue
        if in_fence:
            continue
        no_code = re.sub(r"`[^`\r\n]*`", "", line).replace(r"\$", "")
        if no_code.count("$$") % 2 == 1:
            in_display = not in_display
        no_dd = no_code.replace("$$", "")
        if not in_display and no_dd.count("$") % 2 == 1:
            errors.append(f"{rel_path}:{line_no}: Unmatched '$' delimiter")

        for wm in WIKILINK_RE.finditer(no_code):
            parts = parse_wikilink_parts(wm.group(2), is_embed=bool(wm.group(1)))
            if not parts["note"]:
                continue
            res = resolve_link_to_rel_path(parts["note"], index, extra_rel_paths=created_rel_paths)
            if not res["resolved"] and not res["ambiguous"]:
                errors.append(f"{rel_path}:{line_no}: Broken wikilink [[{parts['raw']}]]")

    if in_display:
        errors.append(f"{rel_path}: Unclosed $$ display math block")

    # Validate any TeachMe-generated Mermaid blocks
    for mm in TEACHME_MERMAID_BLOCK_RE.finditer(text_to_check):
        m_val = validate_mermaid_syntax(mm.group(1))
        if not m_val["valid"]:
            for err in m_val["errors"]:
                errors.append(f"{rel_path}: Invalid Mermaid diagram: {err}")

    return errors


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
        if existed and read_text_safe(abs_path) == new_text:
            # Idempotent no-op
            continue

        errs = _validate_generated_text(
            rel_path=rel,
            text=new_text,
            role=af.get("role", "target_note"),
            action=af.get("action", "create"),
            inserted_line=af.get("inserted_line", ""),
            index=index,
            created_rel_paths=created_rel_paths,
        )
        validation_errors.extend(errs)

        orig_text = read_text_safe(abs_path) if existed else ""
        prepared_ops.append(
            {
                "rel_path": rel,
                "abs_path": abs_path,
                "role": af.get("role", "target_note"),
                "action": af.get("action", "create"),
                "existed": existed,
                "orig_text": orig_text,
                "new_text": new_text,
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
            "written_files": [],
            "backups": {},
            "atomicity": "per_file_atomic_with_rollback",
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

    journal = {
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
                "new_sha256": sha256_text(op["new_text"]),
            }
            for op in prepared_ops
        ],
    }
    atomic_write_text(journal_path, json.dumps(journal, indent=2, ensure_ascii=False) + "\n")

    # 3. Apply per-file atomic writes with automatic rollback on failure
    completed: list[dict[str, Any]] = []
    try:
        for op in prepared_ops:
            writer(op["abs_path"], op["new_text"])
            completed.append(op)
    except Exception as exc:
        # Roll back already-written files in reverse order
        rollback_errors: list[str] = []
        for comp in reversed(completed):
            try:
                if comp["existed"]:
                    atomic_write_text(comp["abs_path"], comp["orig_text"])
                else:
                    if comp["abs_path"].exists():
                        comp["abs_path"].unlink()
            except Exception as rb_exc:
                rollback_errors.append(f"{comp['rel_path']}: {rb_exc}")

        journal["status"] = "rolled_back" if not rollback_errors else "rollback_partial_error"
        journal["error"] = str(exc)
        journal["rollback_errors"] = rollback_errors
        atomic_write_text(journal_path, json.dumps(journal, indent=2, ensure_ascii=False) + "\n")
        raise RuntimeError(f"Transaction {tx_id} failed and rolled back: {exc}") from exc

    journal["status"] = "committed"
    journal["committed_at"] = utc_now_iso()
    atomic_write_text(journal_path, json.dumps(journal, indent=2, ensure_ascii=False) + "\n")

    return {
        "tx_id": tx_id,
        "journal_path": str(journal_path),
        "status": "committed",
        "written_files": [op["rel_path"] for op in prepared_ops],
        "backups": backups,
        "atomicity": "per_file_atomic_with_rollback",
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
) -> dict[str, Any]:
    """Plan and generate (or non-destructively extend) vault-native notes + MOCs + Mermaid."""
    root = vault_root.resolve()
    sdir = state_dir or resolve_state_dir(root)

    if plan_ref is not None:
        plan = load_reviewed_plan(root, plan_ref, state_dir=sdir)
        if Path(str(plan.get("vault_path", ""))).resolve() != root:
            raise ValueError("Reviewed plan belongs to a different vault path")
        if expected_plan_hash and plan.get("plan_hash") != expected_plan_hash:
            raise RuntimeError("Reviewed plan hash mismatch")
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
            "conflict": True,
            "mode": mode,
            "target_rel_path": target_rel,
            "reason": target_af.get("conflict_reason") or "Target note already exists. Use --extend or choose another title/folder.",
            "plan_id": plan.get("plan_id"),
            "plan_hash": plan.get("plan_hash"),
            "plan": plan,
        }

    combined_diff = "\n".join(af.get("diff", "") for af in affected_files if af.get("diff"))
    backup_rel = ""
    tx_info: dict[str, Any] = {}
    audit_report: dict[str, Any] | None = None

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
                entry["sha256"] = sha256_text(op["new_text"])
                manifest["moc_updates"][rel] = entry
            else:
                manifest["notes"][rel] = {
                    "topic": topic,
                    "mode": "moc_create" if role == "moc_create" else mode,
                    "updated_at": utc_now_iso(),
                    "sha256": sha256_text(op["new_text"]),
                    "backup": op["backup_rel_path"],
                }
        _save_managed_manifest(sdir, manifest)

        sess_dir = _init_isolated_session(root, sdir, topic, target_rel)
        # Refresh vault index and profile incrementally after successful transaction
        build_or_update_index(root, full=False, state_dir=sdir)
        discover_vault(root, refresh=False, state_dir=sdir)

        audit_files = [af["rel_path"] for af in affected_files]
        audit_report = audit_vault_native(root, target_files=audit_files, state_dir=sdir)
    else:
        sess_dir = sdir / "sessions" / _slugify(topic)

    return {
        "ok": True,
        "applied": apply,
        "dry_run": not apply,
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


def _audit_lines_for_links_and_math(
    rel: str,
    text_lines: list[tuple[int, str]],
    docs: dict[str, dict[str, Any]],
    stem_map: dict[str, list[str]],
    alias_set: set[str],
    errors: list[dict[str, Any]],
    warnings: list[dict[str, Any]],
    check_math: bool = True,
) -> None:
    """Audit specific line ranges for math parity and broken/ambiguous wikilinks."""
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
                errors.append({"file": rel, "line": line_no, "type": "unmatched_dollar", "detail": "Odd number of $ delimiters"})

        for wm in WIKILINK_RE.finditer(no_code):
            parts = parse_wikilink_parts(wm.group(2), is_embed=bool(wm.group(1)))
            target = parts["note"]
            if not target:
                continue
            clean = target[:-3] if target.endswith(".md") else target
            cand_rel = f"{clean}.md"
            target_doc = docs.get(cand_rel)
            if target_doc is None:
                base = Path(clean).name.lower()
                matches = stem_map.get(base, [])
                if len(matches) == 1:
                    target_doc = docs[matches[0]]
                elif len(matches) > 1:
                    warnings.append({"file": rel, "line": line_no, "type": "ambiguous_wikilink", "detail": f"Ambiguous target [[{target}]]"})
                    continue
                elif base in alias_set:
                    continue
            if target_doc is None:
                errors.append({"file": rel, "line": line_no, "type": "broken_wikilink", "detail": f"Unresolved wikilink [[{parts['raw']}]]"})
            elif parts["anchor"]:
                anc = parts["anchor"]
                if anc.startswith("^"):
                    bid = anc[1:]
                    if bid not in target_doc.get("block_ids", []):
                        warnings.append({"file": rel, "line": line_no, "type": "missing_block_id", "detail": f"Block ID ^{bid} not found in {target_doc['rel_path']}"})
                else:
                    slug = heading_slug(anc)
                    if slug not in target_doc.get("heading_slugs", []):
                        warnings.append({"file": rel, "line": line_no, "type": "missing_heading_anchor", "detail": f"Heading #{anc} not found in {target_doc['rel_path']}"})

    if check_math and in_display:
        errors.append({"file": rel, "line": 1, "type": "unclosed_display_math", "detail": "Unclosed $$ block"})


def audit_vault_native(
    vault_root: Path,
    target_files: list[str] | None = None,
    state_dir: Path | None = None,
) -> dict[str, Any]:
    """Audit ONLY TeachMe-managed notes, extensions, and added MOC entries (never blaming pre-existing user issues)."""
    root = vault_root.resolve()
    sdir = state_dir or resolve_state_dir(root)
    manifest = _load_managed_manifest(sdir)
    index = load_or_build_index(root, refresh=False, state_dir=sdir)
    docs = index.get("docs", {})

    managed_notes = manifest.get("notes", {})
    moc_updates = manifest.get("moc_updates", {})

    if target_files:
        candidates = [f.strip().lstrip("/") for f in target_files if f.strip()]
    else:
        candidates = sorted(set(managed_notes.keys()) | set(moc_updates.keys()))

    stem_map: dict[str, list[str]] = {}
    alias_set: set[str] = set()
    for rel, d in docs.items():
        stem_map.setdefault(d["stem"].lower(), []).append(rel)
        for al in d.get("aliases", []):
            alias_set.add(al.lower())

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
                rel, added_numbered, docs, stem_map, alias_set, errors, warnings, check_math=False
            )
            pre_errs: list[dict[str, Any]] = []
            pre_warns: list[dict[str, Any]] = []
            _audit_lines_for_links_and_math(
                rel, user_numbered, docs, stem_map, alias_set, pre_errs, pre_warns, check_math=False
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
            _audit_lines_for_links_and_math(rel, ext_lines, docs, stem_map, alias_set, errors, warnings, check_math=True)
            ext_text = "\n".join(ln for _, ln in ext_lines)
            for mm in TEACHME_MERMAID_BLOCK_RE.finditer(ext_text):
                m_val = validate_mermaid_syntax(mm.group(1))
                if not m_val["valid"]:
                    for err in m_val["errors"]:
                        errors.append({"file": rel, "line": 1, "type": "invalid_mermaid", "detail": err})

            pre_errs = []
            pre_warns = []
            _audit_lines_for_links_and_math(rel, user_lines, docs, stem_map, alias_set, pre_errs, pre_warns, check_math=False)
            for pe in pre_errs:
                pe["pre_existing"] = True
                pre_existing_issues.append(pe)
            continue

        # Case 3: TeachMe-created note or newly created MOC
        fm = parse_frontmatter_tolerant(text)
        for w in fm["warnings"]:
            errors.append({"file": rel, "line": 1, "type": "yaml_syntax", "detail": w})
        numbered = list(enumerate(text.splitlines(), start=1))
        _audit_lines_for_links_and_math(rel, numbered, docs, stem_map, alias_set, errors, warnings, check_math=True)
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
