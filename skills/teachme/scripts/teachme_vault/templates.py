"""Automatic template discovery, selection, and safe non-executing rendering."""

from __future__ import annotations

from pathlib import Path
import re
from typing import Any

from .markdown_utils import analyze_markdown_body, extract_frontmatter_tags, parse_frontmatter_tolerant
from .models import is_within_root, read_text_safe, today_iso

DYNAMIC_TEMPLATER_RE = re.compile(r"<%\*[\s\S]*?%>|<%[\s\S]*?%>")
SAFE_TP_TITLE_RE = re.compile(r"<%\s*tp\.file\.title\s*%>")
SAFE_TP_DATE_RE = re.compile(r"<%\s*tp\.date\.now\((?:['\"]([^'\"]*)['\"])?\)\s*%>")
CORE_DATE_RE = re.compile(r"\{\{date(?::([^}]+))?\}\}")
CORE_TITLE_RE = re.compile(r"\{\{title\}\}")


def discover_templates(vault_root: Path, profile: dict[str, Any]) -> list[dict[str, Any]]:
    """Discover template files in configured and inferred template directories."""
    root = vault_root.resolve()
    plugins = profile.get("plugins", {})
    template_dirs: list[str] = list(plugins.get("template_folders", []))

    for folder_key, finfo in profile.get("folders", {}).items():
        if finfo.get("role") == "templates" and finfo.get("path"):
            if finfo["path"] not in template_dirs:
                template_dirs.append(finfo["path"])

    # Also include QuickAdd explicit template paths
    extra_files: list[str] = []
    for cap in plugins.get("capabilities", []):
        if cap.get("id") == "quickadd":
            for tp in cap.get("conventions", {}).get("template_paths", []):
                if tp:
                    extra_files.append(tp)

    seen: set[str] = set()
    templates: list[dict[str, Any]] = []

    def _inspect_template(path: Path) -> None:
        if not path.is_file() or not is_within_root(path, root):
            return
        rel = path.relative_to(root).as_posix()
        if rel in seen:
            return
        seen.add(rel)
        text = read_text_safe(path)
        fm = parse_frontmatter_tolerant(text)
        body_info = analyze_markdown_body(fm["body"])
        has_dynamic = bool(re.search(r"<%\*|tp\.system\.|tp\.user\.", text))
        templates.append(
            {
                "rel_path": rel,
                "stem": path.stem,
                "name_lower": path.stem.lower(),
                "frontmatter_keys": list(fm["meta"].keys()),
                "tags": extract_frontmatter_tags(fm["meta"]) + body_info["inline_tags"],
                "headings": [h["text"] for h in body_info["headings"]],
                "has_templater_syntax": "<%" in text,
                "has_core_placeholders": "{{" in text and "}}" in text,
                "has_unsupported_dynamic": has_dynamic,
                "preview_lines": text.splitlines()[:25],
            }
        )

    for tdir in template_dirs:
        pdir = (root / tdir).resolve()
        if pdir.is_dir() and is_within_root(pdir, root):
            for p in sorted(pdir.rglob("*.md")):
                _inspect_template(p)

    for ef in extra_files:
        cand = root / (ef if ef.endswith(".md") else f"{ef}.md")
        _inspect_template(cand)

    return templates


def resolve_template(
    vault_root: Path,
    profile: dict[str, Any],
    target_folder: str,
    topic: str,
    note_type: str = "concept",
    explicit_template: str | None = None,
) -> dict[str, Any]:
    """Select the best template following the 6-level priority hierarchy."""
    templates = discover_templates(vault_root, profile)
    plugins = profile.get("plugins", {})
    folder_templates: dict[str, str] = plugins.get("folder_templates", {})

    # Priority 1 & 2: Explicit user / CLI selection
    if explicit_template:
        norm_exp = explicit_template.strip().lstrip("/")
        for tpl in templates:
            if tpl["rel_path"] == norm_exp or tpl["stem"].lower() == Path(norm_exp).stem.lower():
                return {
                    "selected": tpl["rel_path"],
                    "priority_level": 1,
                    "confidence": "high",
                    "needs_confirmation": False,
                    "reason": "Explicitly selected template",
                    "template_info": tpl,
                    "alternatives": [],
                }
        cand_path = (vault_root / norm_exp).resolve()
        if cand_path.is_file() and is_within_root(cand_path, vault_root):
            rel = cand_path.relative_to(vault_root).as_posix()
            return {
                "selected": rel,
                "priority_level": 1,
                "confidence": "high",
                "needs_confirmation": False,
                "reason": "Explicitly provided template path",
                "template_info": None,
                "alternatives": [],
            }

    if not templates:
        return {
            "selected": None,
            "priority_level": 6,
            "confidence": "high",
            "needs_confirmation": False,
            "reason": "No vault templates found; using TeachMe adaptive blueprint",
            "template_info": None,
            "alternatives": [],
        }

    # Priority 3: Configured folder-template mapping (Templater folder_templates)
    if target_folder:
        cur = target_folder.strip("/")
        while cur:
            if cur in folder_templates:
                mapped = folder_templates[cur]
                for tpl in templates:
                    if tpl["rel_path"] == mapped or mapped.endswith(tpl["rel_path"]) or tpl["stem"] == Path(mapped).stem:
                        return {
                            "selected": tpl["rel_path"],
                            "priority_level": 3,
                            "confidence": "high",
                            "needs_confirmation": False,
                            "reason": f"Configured folder template for '{cur}'",
                            "template_info": tpl,
                            "alternatives": [],
                        }
            if "/" not in cur:
                break
            cur = cur.rsplit("/", 1)[0]

    # Priority 4 & 5: Strongly inferred folder convention or general vault convention
    folder_info = profile.get("folders", {}).get(target_folder or ".", {})
    folder_props = set(folder_info.get("properties", {}).keys())
    folder_tags = set(folder_info.get("top_tags", []))
    folder_tokens = set(re.findall(r"[a-z0-9]+", f"{target_folder} {note_type} {topic}".lower()))

    scored: list[tuple[float, dict[str, Any], list[str]]] = []
    for tpl in templates:
        score = 0.0
        reasons: list[str] = []
        tpl_tokens = set(re.findall(r"[a-z0-9]+", tpl["stem"].lower()))

        # Avoid selecting daily/periodic/meeting templates for conceptual knowledge notes
        if any(bad in tpl["name_lower"] for bad in ("daily", "weekly", "monthly", "meeting", "journal")):
            if note_type not in tpl["name_lower"]:
                score -= 5.0

        # Match folder/note-type keywords
        overlap = tpl_tokens & folder_tokens
        if overlap:
            score += 4.0 * len(overlap)
            reasons.append(f"Template name matches {', '.join(sorted(overlap))}")

        if note_type == "concept" and any(k in tpl["name_lower"] for k in ("note", "concept", "topic", "knowledge", "zettel", "atomic")):
            score += 3.5
            reasons.append("Template aligns with conceptual/knowledge note type")

        # Match frontmatter properties used in target folder
        tpl_keys = set(tpl["frontmatter_keys"])
        prop_overlap = tpl_keys & folder_props
        if prop_overlap:
            score += 1.5 * len(prop_overlap)
            reasons.append(f"Shares folder frontmatter keys: {', '.join(sorted(prop_overlap)[:4])}")

        tag_overlap = set(tpl["tags"]) & folder_tags
        if tag_overlap:
            score += 2.0 * len(tag_overlap)
            reasons.append(f"Shares folder tags: {', '.join(sorted(tag_overlap)[:3])}")

        scored.append((score, tpl, reasons))

    scored.sort(key=lambda x: x[0], reverse=True)
    best_score, best_tpl, best_reasons = scored[0]

    if best_score < 2.0:
        return {
            "selected": None,
            "priority_level": 6,
            "confidence": "low",
            "needs_confirmation": len(templates) > 1,
            "reason": "Weak evidence for existing vault templates; falling back to TeachMe adaptive blueprint",
            "template_info": None,
            "alternatives": [t["rel_path"] for _, t, _ in scored[:4]],
        }

    ambiguous = len(scored) > 1 and (best_score - scored[1][0]) < 1.5
    conf = "medium" if ambiguous or best_score < 5.0 else "high"
    prio = 4 if (set(best_tpl["frontmatter_keys"]) & folder_props or set(best_tpl["tags"]) & folder_tags) else 5

    return {
        "selected": best_tpl["rel_path"],
        "priority_level": prio,
        "confidence": conf,
        "needs_confirmation": ambiguous,
        "reason": "; ".join(best_reasons) if best_reasons else "Best matching vault template",
        "template_info": best_tpl,
        "alternatives": [t["rel_path"] for _, t, _ in scored[1:4]],
    }


def render_template_safely(
    template_text: str,
    title: str,
    date_str: str | None = None,
) -> dict[str, Any]:
    """Fill safe static template fields while preserving dynamic expressions untouched."""
    date_val = date_str or today_iso()
    rendered = CORE_TITLE_RE.sub(title, template_text)
    rendered = CORE_DATE_RE.sub(date_val, rendered)
    rendered = SAFE_TP_TITLE_RE.sub(title, rendered)
    rendered = SAFE_TP_DATE_RE.sub(date_val, rendered)

    # Detect any remaining dynamic Templater blocks (e.g. <%* ... %> or custom tp calls)
    remaining_dynamic = DYNAMIC_TEMPLATER_RE.findall(rendered)
    return {
        "rendered": rendered,
        "preserved_dynamic_expressions": remaining_dynamic,
    }
