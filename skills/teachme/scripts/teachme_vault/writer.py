"""Non-destructive vault-native note generation, extension, backup, and audit."""

from __future__ import annotations

import difflib
import json
from pathlib import Path
import re
from typing import Any

from .indexer import build_or_update_index, load_or_build_index
from .markdown_utils import (
    FENCE_RE,
    WIKILINK_RE,
    heading_slug,
    parse_frontmatter_tolerant,
    parse_wikilink_parts,
)
from .models import (
    atomic_write_text,
    is_within_root,
    read_text_safe,
    resolve_state_dir,
    sha256_text,
    today_iso,
    utc_now_iso,
)
from .planner import plan_note
from .templates import render_template_safely

YAML_NEEDS_QUOTE_RE = re.compile(r"[:\[\]{}|<>*&#?\\]")


def _format_yaml_value(val: Any) -> str:
    if isinstance(val, bool):
        return "true" if val else "false"
    if isinstance(val, (int, float)):
        return str(val)
    s = str(val)
    if s == "":
        return '""'
    if YAML_NEEDS_QUOTE_RE.search(s) or s.startswith(("-", " ")) or s.endswith(" "):
        escaped = s.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    return s


def serialize_frontmatter(meta: dict[str, Any]) -> str:
    """Serialize a frontmatter dictionary into clean, Obsidian-compatible YAML."""
    if not meta:
        return ""
    lines = ["---"]
    for key, val in meta.items():
        if isinstance(val, list):
            if not val:
                lines.append(f"{key}: []")
            else:
                lines.append(f"{key}:")
                for item in val:
                    lines.append(f"  - {_format_yaml_value(item)}")
        elif isinstance(val, dict):
            lines.append(f"{key}:")
            for sub_k, sub_v in val.items():
                lines.append(f"  {sub_k}: {_format_yaml_value(sub_v)}")
        else:
            lines.append(f"{key}: {_format_yaml_value(val)}")
    lines.append("---")
    return "\n".join(lines)


def _slugify(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return s or "topic"


def _append_flashcard_block(
    lines: list[str],
    topic: str,
    c: dict[str, Any],
    fc_syntax: str,
    sr_tags: list[str],
) -> None:
    if fc_syntax == "none" and not sr_tags:
        return
    if sr_tags:
        lines.append(f"#{sr_tags[0]}")
    answer = c.get("invariant", f"{topic} maintains its core structural constraint across valid inputs.")
    if fc_syntax == "multiline_question":
        lines.extend([f"What invariant does {topic} preserve?", "?", answer, ""])
    else:
        lines.extend([f"What invariant does {topic} preserve? :: {answer}", ""])


def _compose_educational_body(
    topic: str,
    plan: dict[str, Any],
    content: dict[str, Any] | None = None,
) -> str:
    """Build vault-native Markdown body preserving TeachMe's educational rigor."""
    c = content or {}
    style = plan.get("style_guidance", {})
    plugins_conv = plan.get("plugin_conventions", {})
    relevant = plan.get("relevant_notes", [])
    granularity = style.get("granularity", "balanced")
    uses_h1 = style.get("uses_h1", True)
    numbered = style.get("numbered_headings", False)
    callouts = style.get("common_callouts", ["note"])
    primary_callout = callouts[0] if callouts else "note"
    fc_syntax = style.get("flashcard_syntax", "inline_double_colon")
    sr_tags = plugins_conv.get("flashcard_tags", [])

    def h(num: int, title: str) -> str:
        return f"## {num}. {title}" if numbered else f"## {title}"

    lines: list[str] = []
    if uses_h1:
        lines.extend([f"# {topic}", ""])

    core_intuition = c.get(
        "intuition",
        f"{topic} solves a core structural problem from first principles by balancing invariants against concrete constraints.",
    )
    prereq_notes = [r["wikilink"] for r in relevant[:3]]
    prereq_line = ", ".join(prereq_notes) if prereq_notes else "Foundational definitions"

    if granularity == "atomic":
        lines.extend(
            [
                core_intuition,
                "",
                f"> [!{primary_callout}] Core Principle & Prerequisites",
                f"> - **Prerequisites:** {prereq_line}",
                f"> - **Key Invariant:** {c.get('invariant', f'State the exact governing relationship of {topic} clearly before applying it.')}",
                "",
            ]
        )
        if c.get("equation"):
            lines.extend(["$$", str(c["equation"]).strip(), "$$", ""])
        if c.get("example"):
            lines.extend([h(1, "Worked Example"), "", str(c["example"]).strip(), ""])
        _append_flashcard_block(lines, topic, c, fc_syntax, sr_tags)
        if relevant:
            lines.append(h(2, "Related Notes"))
            for r in relevant[:5]:
                why = r["reasons"][0] if r.get("reasons") else "Related concept"
                lines.append(f"- {r['wikilink']} — {why}")
            lines.append("")
        if c.get("sources"):
            lines.append(h(3, "References"))
            for src in c["sources"]:
                lines.append(f"- {src}")
            lines.append("")
        return "\n".join(lines).rstrip() + "\n"

    # Balanced / comprehensive vault-native note preserving TeachMe educational depth
    lines.extend(
        [
            h(1, "Core Intuition & Prerequisites"),
            "",
            core_intuition,
            "",
            f"> [!{primary_callout}] Prerequisites",
            f"> - **Building Blocks:** {prereq_line}",
            f"> - **Mental Hook:** {c.get('mental_hook', f'Track how inputs transform step-by-step under {topic}.')}",
            "",
            h(2, "Mechanism & Step-by-Step Derivation"),
            "",
            c.get(
                "mechanism",
                f"1. **Starting Axiom:** Establish the base quantities and domain for {topic}.\n"
                f"2. **Core Transformation:** Derive the governing update or structural rule without skipped steps.\n"
                f"3. **Boundary Behavior:** Inspect behavior at degenerate limits ($0$, $1$, $\\infty$).",
            ),
            "",
        ]
    )
    if c.get("equation"):
        lines.extend(["$$", str(c["equation"]).strip(), "$$", ""])

    lines.extend(
        [
            h(3, "Worked Example"),
            "",
            c.get(
                "example",
                f"Trace a concrete 2-number input through {topic} to verify each intermediate value and directional sensitivity.",
            ),
            "",
            h(4, "Practice & Feynman Check"),
            "",
            c.get(
                "practice",
                f"- **Feynman Prompt:** Explain {topic} in two jargon-free sentences.\n"
                f"- **Edge-Case Check:** What happens when the primary parameter approaches $0$ or grows unbounded?",
            ),
            "",
        ]
    )

    _append_flashcard_block(lines, topic, c, fc_syntax, sr_tags)

    if relevant:
        lines.append(h(5, "Connected Knowledge"))
        lines.append("")
        for r in relevant[:6]:
            why = r["reasons"][0] if r.get("reasons") else "Related concept"
            lines.append(f"- {r['wikilink']} — {why}")
        lines.append("")

    summary_heading = style.get("common_summary_headings", [])
    if summary_heading:
        lines.extend([h(6, summary_heading[0].title()), "", c.get("summary", f"{topic} bridges its prerequisites to downstream applications."), ""])

    sources = c.get("sources", [])
    if sources:
        lines.append(h(7, "Primary Sources"))
        lines.append("")
        for src in sources:
            lines.append(f"- {src}")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def _load_managed_manifest(state_dir: Path) -> dict[str, Any]:
    mpath = state_dir / "managed-notes.json"
    if mpath.is_file():
        try:
            data = json.loads(read_text_safe(mpath))
            if isinstance(data, dict):
                return data
        except (OSError, json.JSONDecodeError):
            pass
    return {"schema_version": 1, "notes": {}}


def _save_managed_manifest(state_dir: Path, manifest: dict[str, Any]) -> None:
    state_dir.mkdir(parents=True, exist_ok=True)
    atomic_write_text(
        state_dir / "managed-notes.json",
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
    )


def _create_backup(vault_root: Path, state_dir: Path, rel_path: str, text: str) -> str:
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
            f"- **Vault Mode:** `vault-native`",
            f"- **Vault Root:** `{vault_root}`",
            f"- **Active Note:** `{target_rel_path}`",
            "- **Live Stage & Checkpoint:** `Depth Stage 1/3 | Checkpoint [1/4]`",
            "- **Last Verified Invariant:** Vault-native note planned/created.",
        ]
        atomic_write_text(state_file, "\n".join(lines) + "\n")
    return sess_dir


def generate_vault_note(
    vault_root: Path,
    topic: str,
    apply: bool = False,
    explicit_folder: str | None = None,
    explicit_template: str | None = None,
    extend_rel_path: str | None = None,
    content: dict[str, Any] | None = None,
    expected_hash: str | None = None,
    state_dir: Path | None = None,
) -> dict[str, Any]:
    """Plan and generate (or non-destructively extend) a vault-native note."""
    root = vault_root.resolve()
    sdir = state_dir or resolve_state_dir(root)

    plan = plan_note(
        vault_root=root,
        topic=topic,
        explicit_folder=explicit_folder,
        explicit_template=explicit_template,
        state_dir=sdir,
    )

    mode = "extend" if extend_rel_path else "create"
    if extend_rel_path:
        target_rel = extend_rel_path.strip().lstrip("/")
    else:
        target_rel = plan["destination"]["proposed_rel_path"]

    target_abs = (root / target_rel).resolve()
    if not is_within_root(target_abs, root):
        raise ValueError(f"Refusing path outside vault root: {target_rel}")

    backup_rel = ""
    preserved_dynamic: list[str] = []

    if mode == "extend":
        if not target_abs.is_file():
            raise FileNotFoundError(f"Cannot extend missing note: {target_rel}")
        orig_text = read_text_safe(target_abs)
        cur_hash = sha256_text(orig_text)
        if expected_hash and cur_hash != expected_hash:
            raise RuntimeError(
                f"Conflict detected for {target_rel}: file changed since inspection"
            )
        # Non-destructive extension: preserve original frontmatter, comments, block IDs, and prose
        ext_body = _compose_educational_body(topic, plan, content=content)
        # Strip leading H1 from extension snippet to avoid duplicate H1
        ext_lines = ext_body.splitlines()
        if ext_lines and ext_lines[0].startswith("# "):
            ext_lines = ext_lines[1:]
        addition = "\n".join(ext_lines).strip()
        separator = "\n\n---\n\n" if orig_text.strip() else ""
        new_text = orig_text.rstrip() + separator + f"## TeachMe Extension: {topic}\n\n" + addition + "\n"
        diff_lines = list(
            difflib.unified_diff(
                orig_text.splitlines(keepends=True),
                new_text.splitlines(keepends=True),
                fromfile=f"a/{target_rel}",
                tofile=f"b/{target_rel}",
            )
        )
    else:
        if target_abs.exists():
            # Non-destructive conflict protection: never silently overwrite an existing user note
            return {
                "ok": False,
                "conflict": True,
                "mode": "create",
                "target_rel_path": target_rel,
                "reason": "Target note already exists. Use --extend or choose another title/folder.",
                "plan": plan,
            }

        tpl_rel = plan["template"]["selected"]
        fm_dict = dict(plan["frontmatter"])
        body_text = _compose_educational_body(topic, plan, content=content)

        if tpl_rel:
            tpl_abs = (root / tpl_rel).resolve()
            if tpl_abs.is_file() and is_within_root(tpl_abs, root):
                tpl_raw = read_text_safe(tpl_abs)
                rendered_info = render_template_safely(tpl_raw, title=topic, date_str=today_iso())
                preserved_dynamic = rendered_info["preserved_dynamic_expressions"]
                tpl_fm = parse_frontmatter_tolerant(rendered_info["rendered"])
                merged_meta = dict(tpl_fm["meta"])
                for k, v in fm_dict.items():
                    if k not in merged_meta or not merged_meta[k]:
                        merged_meta[k] = v
                fm_block = serialize_frontmatter(merged_meta)
                tpl_body = tpl_fm["body"].strip()
                if tpl_body and any(ln.lstrip().startswith("# ") for ln in tpl_body.splitlines()):
                    b_lines = body_text.splitlines()
                    if b_lines and b_lines[0].startswith("# "):
                        body_text = "\n".join(b_lines[1:]).lstrip("\n")
                combined_body = (tpl_body + "\n\n" + body_text) if tpl_body else body_text
                new_text = (fm_block + "\n\n" + combined_body).rstrip() + "\n"
            else:
                fm_block = serialize_frontmatter(fm_dict)
                new_text = ((fm_block + "\n\n") if fm_block else "") + body_text
        else:
            fm_block = serialize_frontmatter(fm_dict)
            new_text = ((fm_block + "\n\n") if fm_block else "") + body_text

        diff_lines = list(
            difflib.unified_diff(
                [],
                new_text.splitlines(keepends=True),
                fromfile="/dev/null",
                tofile=f"b/{target_rel}",
            )
        )

    if apply:
        if mode == "extend":
            backup_rel = _create_backup(root, sdir, target_rel, read_text_safe(target_abs))
        atomic_write_text(target_abs, new_text)

        manifest = _load_managed_manifest(sdir)
        manifest["notes"][target_rel] = {
            "topic": topic,
            "mode": mode,
            "updated_at": utc_now_iso(),
            "sha256": sha256_text(new_text),
            "backup": backup_rel,
        }
        _save_managed_manifest(sdir, manifest)
        sess_dir = _init_isolated_session(root, sdir, topic, target_rel)
        # Refresh vault index incrementally so newly written note is immediately discoverable
        build_or_update_index(root, full=False, state_dir=sdir)
    else:
        sess_dir = sdir / "sessions" / _slugify(topic)

    return {
        "ok": True,
        "applied": apply,
        "dry_run": not apply,
        "mode": mode,
        "target_rel_path": target_rel,
        "target_abs_path": str(target_abs),
        "backup_rel_path": backup_rel,
        "preserved_dynamic_expressions": preserved_dynamic,
        "diff": "".join(diff_lines),
        "preview": new_text if not apply else "",
        "session_dir": str(sess_dir),
        "plan": plan,
    }


def audit_vault_native(
    vault_root: Path,
    target_files: list[str] | None = None,
    state_dir: Path | None = None,
) -> dict[str, Any]:
    """Audit ONLY TeachMe-managed vault-native notes (never user-authored notes)."""
    root = vault_root.resolve()
    sdir = state_dir or resolve_state_dir(root)
    manifest = _load_managed_manifest(sdir)
    index = load_or_build_index(root, refresh=False, state_dir=sdir)
    docs = index.get("docs", {})

    if target_files:
        candidates = [f.strip().lstrip("/") for f in target_files if f.strip()]
    else:
        candidates = sorted(manifest.get("notes", {}).keys())

    # Build lookup structures across ALL vault notes for link validation
    stem_map: dict[str, list[str]] = {}
    alias_set: set[str] = set()
    for rel, d in docs.items():
        stem_map.setdefault(d["stem"].lower(), []).append(rel)
        for al in d.get("aliases", []):
            alias_set.add(al.lower())

    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    audited: list[str] = []

    for rel in candidates:
        fpath = (root / rel).resolve()
        if not fpath.is_file() or not is_within_root(fpath, root):
            errors.append({"file": rel, "line": 1, "type": "missing_managed_file", "detail": "File does not exist"})
            continue
        audited.append(rel)
        text = read_text_safe(fpath)
        fm = parse_frontmatter_tolerant(text)
        for w in fm["warnings"]:
            errors.append({"file": rel, "line": 1, "type": "yaml_syntax", "detail": w})

        # Check math parity and broken wikilinks outside code fences
        in_fence = False
        fence_char = ""
        in_display = False
        for line_no, line in enumerate(text.splitlines(), start=1):
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

        if in_display:
            errors.append({"file": rel, "line": 1, "type": "unclosed_display_math", "detail": "Unclosed $$ block"})

    return {
        "vault_path": str(root),
        "mode": "vault-native",
        "audited_files": audited,
        "errors": errors,
        "warnings": warnings,
        "user_notes_untouched": True,
    }
