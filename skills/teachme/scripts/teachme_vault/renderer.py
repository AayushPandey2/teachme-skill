"""Deterministic vault-native note rendering, template merging, and idempotent extension."""

from __future__ import annotations

import difflib
from pathlib import Path
import re
from typing import Any

from .markdown_utils import parse_frontmatter_tolerant
from .mermaid import merge_generated_mermaid_into_note
from .models import is_within_root, read_text_safe, sha256_text, today_iso
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


def compose_educational_body(
    topic: str,
    plan: dict[str, Any],
    content: dict[str, Any] | None = None,
    include_inline_tags: bool = True,
) -> str:
    """Build vault-native Markdown body preserving TeachMe's educational rigor."""
    c = content or {}
    style = plan.get("style_guidance", {})
    plugins_conv = plan.get("plugin_conventions", {})
    relevant = plan.get("relevant_notes", [])
    tag_dec = plan.get("tag_decisions", {})
    diag_dec = plan.get("diagram_decisions", {})
    moc_dec = plan.get("moc_decisions", {})

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

    # Render inline tags only if vault/folder uses inline or mixed tag placement
    placement = tag_dec.get("placement", "frontmatter")
    selected_tags = tag_dec.get("selected_tags", plan.get("tags", []))
    if include_inline_tags and selected_tags and placement in ("inline", "both"):
        lines.extend([" ".join(f"#{t.lstrip('#')}" for t in selected_tags), ""])

    core_intuition = c.get(
        "intuition",
        f"{topic} solves a core structural problem from first principles by balancing invariants against concrete constraints.",
    )
    prereq_notes = [r["wikilink"] for r in relevant[:3]]
    prereq_line = ", ".join(prereq_notes) if prereq_notes else "Foundational definitions"

    diagram_block = diag_dec.get("rendered_block", "") if diag_dec.get("include_diagram") else ""
    diagram_heading = diag_dec.get("placement_heading") or "Knowledge & Dependency Map"

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
        if diagram_block:
            lines.extend([h(2, diagram_heading), "", diagram_block, ""])
        _append_flashcard_block(lines, topic, c, fc_syntax, sr_tags)
        if relevant or moc_dec.get("selected_moc"):
            lines.append(h(3 if diagram_block else 2, "Related Notes"))
            if moc_dec.get("selected_moc"):
                moc_stem = Path(moc_dec["selected_moc"]).stem
                lines.append(f"- **Hub:** [[{moc_stem}]]")
            for r in relevant[:5]:
                why = r["reasons"][0] if r.get("reasons") else "Related concept"
                lines.append(f"- {r['wikilink']} — {why}")
            lines.append("")
        if c.get("sources"):
            lines.append(h(4 if diagram_block else 3, "References"))
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

    sec_idx = 5
    if diagram_block:
        lines.extend([h(sec_idx, diagram_heading), "", diagram_block, ""])
        sec_idx += 1

    if relevant or moc_dec.get("selected_moc"):
        lines.append(h(sec_idx, "Connected Knowledge"))
        lines.append("")
        if moc_dec.get("selected_moc"):
            moc_stem = Path(moc_dec["selected_moc"]).stem
            lines.append(f"- **MOC Hub:** [[{moc_stem}]]")
        for r in relevant[:6]:
            why = r["reasons"][0] if r.get("reasons") else "Related concept"
            lines.append(f"- {r['wikilink']} — {why}")
        lines.append("")
        sec_idx += 1

    summary_heading = style.get("common_summary_headings", [])
    if summary_heading:
        lines.extend(
            [
                h(sec_idx, summary_heading[0].title()),
                "",
                c.get("summary", f"{topic} bridges its prerequisites to downstream applications."),
                "",
            ]
        )
        sec_idx += 1

    sources = c.get("sources", [])
    if sources:
        lines.append(h(sec_idx, "Primary Sources"))
        lines.append("")
        for src in sources:
            lines.append(f"- {src}")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def _extension_slug(topic: str) -> str:
    clean = re.sub(r"[^\w]+", "-", topic.lower(), flags=re.UNICODE).strip("-_")
    ascii_only = bool(re.fullmatch(r"[a-z0-9-]+", clean)) if clean else False
    if ascii_only:
        return clean
    digest = sha256_text(topic)[:6]
    return f"{clean}-{digest}" if clean else f"ext-{digest}"


def _apply_idempotent_extension(
    orig_text: str,
    topic: str,
    addition_body: str,
    diag_dec: dict[str, Any],
) -> tuple[str, list[str]]:
    """Append or idempotently update a TeachMe Extension section without touching user YAML/prose/diagrams."""
    warnings: list[str] = []
    ext_id = _extension_slug(topic)
    start_marker = f"<!-- teachme:extension:start id={ext_id} -->"
    end_marker = "<!-- teachme:extension:end -->"

    # Never overwrite a user-authored Mermaid diagram; check if generated diagram region exists
    if diag_dec.get("include_diagram") and diag_dec.get("rendered_block"):
        diag_id = "concept-map" if diag_dec.get("diagram_type") == "mindmap" else "relationship-map"
        merge_info = merge_generated_mermaid_into_note(orig_text, diag_dec["rendered_block"], diagram_id=diag_id)
        if merge_info.get("preserved_user_diagrams"):
            warnings.append("Existing user-authored Mermaid diagram preserved untouched.")

    ext_section = "\n".join(
        [
            start_marker,
            f"## TeachMe Extension: {topic}",
            "",
            addition_body.strip(),
            end_marker,
        ]
    )

    marker_re = re.compile(
        rf"<!--\s*teachme:extension:start\s+id={re.escape(ext_id)}\s*-->[\s\S]*?<!--\s*teachme:extension:end\s*-->",
        re.MULTILINE,
    )
    if marker_re.search(orig_text):
        new_text = marker_re.sub(ext_section, orig_text, count=1)
        if not new_text.endswith("\n"):
            new_text += "\n"
        return new_text, warnings

    # Also detect unmarked legacy `## TeachMe Extension: <topic>` at tail
    legacy_re = re.compile(
        rf"(?:\n---\n+)?## TeachMe Extension: {re.escape(topic)}\b[\s\S]*\Z",
        re.MULTILINE,
    )
    if legacy_re.search(orig_text):
        prefix = orig_text[: legacy_re.search(orig_text).start()].rstrip()  # type: ignore[union-attr]
        separator = "\n\n---\n\n" if prefix else ""
        return prefix + separator + ext_section + "\n", warnings

    separator = "\n\n---\n\n" if orig_text.strip() else ""
    return orig_text.rstrip() + separator + ext_section + "\n", warnings


def render_target_note_file(
    vault_root: Path,
    topic: str,
    plan: dict[str, Any],
    extend_rel_path: str | None = None,
    content: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Compute exact target note content, unified diff, expected hash, and metadata."""
    root = vault_root.resolve()
    mode = "extend" if extend_rel_path else "create"
    target_rel = extend_rel_path.strip().lstrip("/") if extend_rel_path else plan["destination"]["proposed_rel_path"]
    target_abs = (root / target_rel).resolve()

    if not is_within_root(target_abs, root):
        raise ValueError(f"Refusing path outside vault root: {target_rel}")

    preserved_dynamic: list[str] = []
    warnings: list[str] = []

    if mode == "extend":
        if not target_abs.is_file():
            raise FileNotFoundError(f"Cannot extend missing note: {target_rel}")
        orig_text = read_text_safe(target_abs)
        expected_sha256 = sha256_text(orig_text)

        ext_body = compose_educational_body(topic, plan, content=content, include_inline_tags=True)
        ext_lines = ext_body.splitlines()
        if ext_lines and ext_lines[0].startswith("# "):
            ext_lines = ext_lines[1:]
        addition = "\n".join(ext_lines).strip()

        new_text, ext_warnings = _apply_idempotent_extension(
            orig_text,
            topic=topic,
            addition_body=addition,
            diag_dec=plan.get("diagram_decisions", {}),
        )
        warnings.extend(ext_warnings)
        diff_lines = list(
            difflib.unified_diff(
                orig_text.splitlines(keepends=True),
                new_text.splitlines(keepends=True),
                fromfile=f"a/{target_rel}",
                tofile=f"b/{target_rel}",
            )
        )
        return {
            "rel_path": target_rel,
            "role": "target_note",
            "action": "extend",
            "conflict": False,
            "expected_sha256": expected_sha256,
            "must_not_exist": False,
            "preserved_dynamic_expressions": preserved_dynamic,
            "warnings": warnings,
            "new_text": new_text,
            "diff": "".join(diff_lines),
            "no_changes": new_text == orig_text,
        }

    # mode == "create"
    if target_abs.exists():
        return {
            "rel_path": target_rel,
            "role": "target_note",
            "action": "create",
            "conflict": True,
            "reason": "Target note already exists. Use --extend or choose another title/folder.",
            "expected_sha256": sha256_text(read_text_safe(target_abs)),
            "must_not_exist": True,
            "preserved_dynamic_expressions": [],
            "warnings": [],
            "new_text": "",
            "diff": "",
            "no_changes": True,
        }

    tpl_rel = plan["template"]["selected"]
    fm_dict = dict(plan["frontmatter"])
    # Omit YAML tags only if vault strictly uses inline-only tagging AND template doesn't define tags
    tag_placement = plan.get("tag_decisions", {}).get("placement", "frontmatter")
    if tag_placement == "inline" and "tags" in fm_dict and not (plan.get("template", {}).get("template_info") or {}).get("frontmatter_keys"):
        fm_dict.pop("tags", None)

    body_text = compose_educational_body(topic, plan, content=content, include_inline_tags=True)

    if tpl_rel:
        tpl_abs = (root / tpl_rel).resolve()
        if tpl_abs.is_file() and is_within_root(tpl_abs, root):
            tpl_raw = read_text_safe(tpl_abs)
            rendered_info = render_template_safely(tpl_raw, title=topic, date_str=today_iso())
            preserved_dynamic = rendered_info["preserved_dynamic_expressions"]
            tpl_fm = parse_frontmatter_tolerant(rendered_info["rendered"])
            merged_meta = dict(tpl_fm["meta"])
            for k, v in fm_dict.items():
                if k == "tags" and isinstance(merged_meta.get("tags"), list) and isinstance(v, list):
                    # Preserve template tags only if semantically selected; otherwise replace template placeholder tags with planned tags
                    if v:
                        merged_meta["tags"] = v
                elif k not in merged_meta or not merged_meta[k]:
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
    return {
        "rel_path": target_rel,
        "role": "target_note",
        "action": "create",
        "conflict": False,
        "expected_sha256": None,
        "must_not_exist": True,
        "preserved_dynamic_expressions": preserved_dynamic,
        "warnings": warnings,
        "new_text": new_text,
        "diff": "".join(diff_lines),
        "no_changes": False,
    }
