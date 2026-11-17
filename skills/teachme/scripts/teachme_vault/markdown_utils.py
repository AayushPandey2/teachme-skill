"""Fault-tolerant Markdown, YAML frontmatter, and Obsidian syntax parsers."""

from __future__ import annotations

import re
from typing import Any

FENCE_RE = re.compile(r"^\s*(`{3,}|~{3,})(.*)$")
HEADING_RE = re.compile(r"^\s{0,3}(#{1,6})\s+(.+?)\s*$")
WIKILINK_RE = re.compile(r"(!?)\[\[([^\[\]\r\n]+)\]\]")
MDLINK_RE = re.compile(r"(?<!!)\[([^\]]*)\]\(([^)]+)\)")
INLINE_TAG_RE = re.compile(
    r"(?:^|(?<=[\s,(]))#((?=[^\s#]*[^\W\d_])[\w][\w/-]*[\w]|[^\W\d_])"
)
CALLOUT_RE = re.compile(r"^\s*>\s*\[!([A-Za-z0-9_-]+)\]", re.IGNORECASE)
BLOCK_ID_RE = re.compile(r"(?:^|\s)\^([A-Za-z0-9-]+)\s*$")
DV_INLINE_FIELD_RE = re.compile(
    r"^\s*(?:[-*]\s+)?([A-Za-z][A-Za-z0-9 _-]{0,40})::\s*(.+?)\s*$"
)
DV_BRACKET_FIELD_RE = re.compile(r"\[([A-Za-z][A-Za-z0-9 _-]{0,40})::\s*([^\]]+)\]")
TASK_RE = re.compile(r"^\s*[-*]\s+\[([ xX/\->!?])\]\s+(.+)$")
SR_SINGLE_RE = re.compile(r"^.+?\s*::\s*.+$")
SR_MULTI_RE = re.compile(r"^\?\s*$")
CLOZE_RE = re.compile(r"(?:==[^=\r\n]+==|\{\{c\d+::[^}]+\}\})")
DATE_VALUE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}(?:[T ]\d{2}:\d{2}(?::\d{2})?)?$")
MERMAID_HEADER_RE = re.compile(
    r"^\s*(flowchart|graph|mindmap|sequenceDiagram|classDiagram|stateDiagram(?:-v2)?|erDiagram|gantt|pie|gitGraph)\b(?:\s+(TD|TB|LR|RL|BT))?",
    re.IGNORECASE,
)
CLASSDEF_RE = re.compile(r"^\s*classDef\s+([A-Za-z0-9_-]+)\s+(.+)$")
INIT_DIRECTIVE_RE = re.compile(r"%%\{init:[\s\S]*?\}%%")

WORKFLOW_TAG_EXACT = frozenset(
    {
        "moc",
        "index",
        "map-of-content",
        "hub",
        "template",
        "daily",
        "weekly",
        "monthly",
        "draft",
        "wip",
        "todo",
        "done",
        "seedling",
        "sprout",
        "evergreen",
        "reviewed",
        "mastered",
        "unreviewed",
        "cards",
        "flashcard",
        "flashcards",
        "task",
        "tasks",
        "to-read",
        "toread",
        "archive",
        "archived",
    }
)
WORKFLOW_TAG_PREFIXES = (
    "status/",
    "state/",
    "stage/",
    "workflow/",
    "flashcards/",
    "cards/",
    "review/",
    "srs/",
    "type/",
)


def is_workflow_or_status_tag(tag: str, plugin_tags: set[str] | None = None) -> bool:
    """Return True if tag represents workflow, lifecycle status, MOC marker, or plugin control."""
    norm = normalize_tag(tag).lower()
    if not norm:
        return True
    if norm in WORKFLOW_TAG_EXACT:
        return True
    if any(norm.startswith(pref) for pref in WORKFLOW_TAG_PREFIXES):
        return True
    if plugin_tags and norm in {t.lstrip("#").lower() for t in plugin_tags}:
        return True
    return False


def classify_tag_case(tag: str) -> str:
    """Classify casing/separator convention of a tag (analyzing leaf segment if nested)."""
    leaf = normalize_tag(tag).split("/")[-1]
    if not leaf:
        return "unknown"
    if "-" in leaf and leaf == leaf.lower():
        return "kebab_case"
    if "_" in leaf and leaf == leaf.lower():
        return "snake_case"
    if any(c.isupper() for c in leaf):
        if leaf[0].isupper() and "-" not in leaf and "_" not in leaf:
            return "pascal_case"
        if leaf[0].islower() and "-" not in leaf and "_" not in leaf:
            return "camel_case"
        return "mixed_case"
    return "lowercase"


def _parse_mermaid_block(lines: list[str], nearest_heading: str) -> dict[str, Any]:
    """Extract structural metadata from a Mermaid code fence."""
    diagram_type = "unknown"
    direction = ""
    class_defs: list[str] = []
    init_directives: list[str] = []
    has_subgraph = False
    node_ids: set[str] = set()
    quoted_labels = 0
    unquoted_labels = 0

    full_text = "\n".join(lines)
    for im in INIT_DIRECTIVE_RE.finditer(full_text):
        init_directives.append(im.group(0).strip())

    for raw in lines:
        s = raw.strip()
        if not s or s.startswith("%%"):
            continue
        if diagram_type == "unknown":
            hm = MERMAID_HEADER_RE.match(s)
            if hm:
                raw_type = hm.group(1)
                diagram_type = "flowchart" if raw_type.lower() == "graph" else raw_type.lower()
                if hm.group(2):
                    direction = hm.group(2).upper()
                continue
        if s.lower().startswith("subgraph "):
            has_subgraph = True
            continue
        cm = CLASSDEF_RE.match(s)
        if cm:
            class_defs.append(s)
            continue
        if diagram_type == "mindmap":
            node_ids.add(s[:40])
            if '"' in s:
                quoted_labels += 1
            else:
                unquoted_labels += 1
        elif diagram_type in ("flowchart", "graph"):
            if '["' in s or '("' in s or '{"' in s:
                quoted_labels += 1
            elif "[" in s or "(" in s or "{" in s:
                unquoted_labels += 1
            for nm in re.finditer(r"\b([A-Za-z_][A-Za-z0-9_]*)\s*(?:\[|\(|\{|<--|-->|---)", s):
                nid = nm.group(1)
                if nid.lower() not in ("subgraph", "end", "style", "classdef", "linkstyle", "click"):
                    node_ids.add(nid)

    return {
        "diagram_type": diagram_type,
        "direction": direction,
        "has_subgraph": has_subgraph,
        "class_defs": class_defs[:5],
        "init_directives": init_directives[:2],
        "nearest_heading": nearest_heading,
        "node_count": len(node_ids),
        "uses_quoted_labels": quoted_labels >= unquoted_labels and quoted_labels > 0,
        "snippet": "\n".join(lines[:20]),
    }


def _strip_quotes(val: str) -> str:
    val = val.strip()
    if len(val) >= 2 and (
        (val[0] == '"' and val[-1] == '"') or (val[0] == "'" and val[-1] == "'")
    ):
        return val[1:-1]
    return val


def _coerce_scalar(raw: str) -> Any:
    cleaned = raw.strip()
    if not cleaned:
        return ""
    if len(cleaned) >= 2 and (
        (cleaned[0] == '"' and cleaned[-1] == '"')
        or (cleaned[0] == "'" and cleaned[-1] == "'")
    ):
        return cleaned[1:-1]
    low = cleaned.lower()
    if low == "true":
        return True
    if low == "false":
        return False
    if low in ("null", "~"):
        return None
    if re.fullmatch(r"-?\d+", cleaned):
        try:
            return int(cleaned)
        except ValueError:
            return cleaned
    if re.fullmatch(r"-?\d+\.\d+", cleaned):
        try:
            return float(cleaned)
        except ValueError:
            return cleaned
    return cleaned


def _split_inline_yaml_list(raw: str) -> list[Any]:
    inner = raw.strip()[1:-1].strip()
    if not inner:
        return []
    items: list[str] = []
    cur: list[str] = []
    in_quote: str | None = None
    for ch in inner:
        if in_quote:
            cur.append(ch)
            if ch == in_quote:
                in_quote = None
            continue
        if ch in ('"', "'"):
            in_quote = ch
            cur.append(ch)
        elif ch == ",":
            items.append("".join(cur).strip())
            cur = []
        else:
            cur.append(ch)
    if cur:
        items.append("".join(cur).strip())
    return [_coerce_scalar(it) for it in items if it]


def parse_frontmatter_tolerant(text: str) -> dict[str, Any]:
    """Parse YAML frontmatter tolerantly, handling malformed lines safely.

    Returns dict with keys: meta, raw_yaml, body, body_start_line, valid, warnings.
    """
    clean = text.lstrip("\ufeff")
    lines = clean.splitlines()
    if not lines or lines[0].strip() != "---":
        return {
            "meta": {},
            "raw_yaml": "",
            "body": clean,
            "body_start_line": 0,
            "valid": True,
            "warnings": [],
        }

    end_idx = -1
    for idx in range(1, len(lines)):
        if lines[idx].strip() == "---":
            end_idx = idx
            break
    if end_idx == -1:
        return {
            "meta": {},
            "raw_yaml": "",
            "body": clean,
            "body_start_line": 0,
            "valid": False,
            "warnings": ["unclosed_frontmatter"],
        }

    yaml_lines = lines[1:end_idx]
    body = "\n".join(lines[end_idx + 1 :])
    meta: dict[str, Any] = {}
    warnings: list[str] = []
    current_key: str | None = None
    current_indent = 0

    for line_no, raw_line in enumerate(yaml_lines, start=2):
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if "\t" in raw_line[: len(raw_line) - len(raw_line.lstrip())]:
            warnings.append(f"line_{line_no}:tab_indent")
        indent = len(raw_line) - len(raw_line.lstrip(" \t"))

        if stripped.startswith("- ") or stripped == "-":
            if current_key is None:
                warnings.append(f"line_{line_no}:orphan_list_item")
                continue
            item_raw = stripped[1:].strip()
            existing = meta.get(current_key)
            if not isinstance(existing, list):
                existing = []
            if item_raw:
                existing.append(_coerce_scalar(item_raw))
            meta[current_key] = existing
            continue

        if ":" in raw_line:
            key_part, val_part = raw_line.split(":", 1)
            key = _strip_quotes(key_part.strip())
            if not key:
                warnings.append(f"line_{line_no}:empty_key")
                continue
            val = val_part.strip()
            if indent > current_indent and current_key is not None and isinstance(meta.get(current_key), dict):
                meta[current_key][key] = _coerce_scalar(val)
                continue

            current_key = key
            current_indent = indent
            if not val:
                meta[key] = []
            elif val.startswith("[") and val.endswith("]"):
                meta[key] = _split_inline_yaml_list(val)
            elif val.startswith("[") or val.endswith("]"):
                warnings.append(f"line_{line_no}:malformed_inline_list")
                meta[key] = val
            else:
                meta[key] = _coerce_scalar(val)
        else:
            warnings.append(f"line_{line_no}:unparseable_yaml_line")

    return {
        "meta": meta,
        "raw_yaml": "\n".join(yaml_lines),
        "body": body,
        "body_start_line": end_idx + 1,
        "valid": len(warnings) == 0,
        "warnings": warnings,
    }


def infer_property_type(value: Any) -> str:
    """Infer simplified schema type name for a frontmatter value."""
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, (int, float)):
        return "number"
    if isinstance(value, list):
        return "list"
    if isinstance(value, dict):
        return "object"
    s = str(value).strip()
    if DATE_VALUE_RE.match(s):
        return "date"
    if s.startswith("[[") and s.endswith("]]"):
        return "wikilink"
    return "string"


def normalize_tag(raw: str) -> str:
    """Normalize an Obsidian tag without leading '#'."""
    t = raw.strip().lstrip("#").strip()
    return t


def extract_frontmatter_tags(meta: dict[str, Any]) -> list[str]:
    """Extract normalized tags from frontmatter 'tags' or 'tag' keys."""
    found: list[str] = []
    for key in ("tags", "tag"):
        val = meta.get(key)
        if isinstance(val, list):
            for item in val:
                norm = normalize_tag(str(item))
                if norm and norm not in found:
                    found.append(norm)
        elif isinstance(val, str):
            for part in re.split(r"[\s,]+", val):
                norm = normalize_tag(part)
                if norm and norm not in found:
                    found.append(norm)
    return found


def extract_aliases(meta: dict[str, Any]) -> list[str]:
    """Extract frontmatter aliases ('aliases' or 'alias')."""
    found: list[str] = []
    for key in ("aliases", "alias"):
        val = meta.get(key)
        if isinstance(val, list):
            for item in val:
                s = str(item).strip()
                if s and s not in found:
                    found.append(s)
        elif isinstance(val, str) and val.strip():
            for part in val.split(","):
                s = part.strip()
                if s and s not in found:
                    found.append(s)
    return found


def parse_wikilink_parts(raw_inner: str, is_embed: bool = False) -> dict[str, Any]:
    """Parse [[Folder/Note#Heading^block|Alias]] into structured parts."""
    target_part = raw_inner
    alias = ""
    if "|" in raw_inner:
        target_part, alias = raw_inner.split("|", 1)
    target_part = target_part.strip()
    alias = alias.strip()

    note_part = target_part
    anchor = ""
    block_id = ""
    if "#" in target_part:
        note_part, anchor = target_part.split("#", 1)
        note_part = note_part.strip()
        anchor = anchor.strip()
        if anchor.startswith("^"):
            block_id = anchor[1:].strip()

    return {
        "raw": raw_inner,
        "embed": is_embed,
        "note": note_part,
        "anchor": anchor,
        "block_id": block_id,
        "alias": alias,
    }


def heading_slug(heading_text: str) -> str:
    """Convert Markdown heading text to Obsidian/GitHub-style anchor slug."""
    slug = heading_text.strip().lower()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"\s+", "-", slug)
    slug = re.sub(r"-+", "-", slug)
    return slug.strip("-")


def extract_frontmatter_links(meta: dict[str, Any]) -> dict[str, list[str]]:
    """Extract wikilinks found inside frontmatter properties (e.g., up, parent, moc)."""
    found: dict[str, list[str]] = {}
    for k, v in meta.items():
        vals = v if isinstance(v, list) else [v]
        links: list[str] = []
        for item in vals:
            if not isinstance(item, str):
                continue
            for wm in WIKILINK_RE.finditer(item):
                parsed = parse_wikilink_parts(wm.group(2), is_embed=bool(wm.group(1)))
                if parsed["note"]:
                    links.append(parsed["note"])
        if links:
            found[str(k)] = links
    return found


def analyze_markdown_body(body: str) -> dict[str, Any]:
    """Extract headings, links, inline tags, block IDs, Mermaid blocks, and style signals."""
    lines = body.splitlines()
    headings: list[dict[str, Any]] = []
    wikilinks: list[dict[str, Any]] = []
    md_links: list[dict[str, str]] = []
    inline_tags: list[str] = []
    block_ids: list[str] = []
    callouts: list[str] = []
    code_langs: list[str] = []
    dv_fields: dict[str, list[str]] = {}
    dv_queries: list[str] = []
    tasks: list[dict[str, str]] = []
    mermaid_examples: list[dict[str, Any]] = []
    base_embeds: list[str] = []

    in_fence = False
    fence_char = ""
    fence_lang = ""
    fence_lines: list[str] = []
    in_display_math = False
    display_math_count = 0
    inline_math_count = 0
    bullet_lines = 0
    bullet_link_lines = 0
    prose_lines = 0
    table_lines = 0
    mermaid_blocks = 0
    sr_single_cards = 0
    sr_multi_cards = 0
    cloze_cards = 0
    paragraph_lengths: list[int] = []
    cur_para_words = 0

    current_heading = ""
    section_stats: list[dict[str, Any]] = [
        {
            "heading": "",
            "level": 0,
            "line_idx": 0,
            "link_count": 0,
            "bullet_link_count": 0,
            "bullet_prefixes": [],
            "annotation_seps": [],
            "has_query": False,
            "links": [],
        }
    ]

    for line_idx, line in enumerate(lines):
        fm = FENCE_RE.match(line)
        if fm:
            marker = fm.group(1)
            info = fm.group(2).strip().lower()
            if not in_fence:
                in_fence = True
                fence_char = marker[0]
                fence_lang = info.split()[0] if info else ""
                fence_lines = []
                if fence_lang:
                    code_langs.append(fence_lang)
                    if fence_lang == "mermaid":
                        mermaid_blocks += 1
            elif marker[0] == fence_char:
                if fence_lang in ("dataview", "dataviewjs"):
                    dv_queries.append("\n".join(fence_lines))
                    section_stats[-1]["has_query"] = True
                elif fence_lang == "mermaid":
                    mermaid_examples.append(_parse_mermaid_block(fence_lines, current_heading))
                in_fence = False
                fence_lang = ""
                fence_lines = []
            continue

        if in_fence:
            fence_lines.append(line)
            continue

        stripped = line.strip()
        if not stripped:
            if cur_para_words > 0:
                paragraph_lengths.append(cur_para_words)
                cur_para_words = 0
            continue

        # Display math blocks
        if stripped.startswith("$$") and stripped.endswith("$$") and len(stripped) > 2:
            display_math_count += 1
            continue
        if stripped.count("$$") % 2 == 1:
            if not in_display_math:
                in_display_math = True
                display_math_count += 1
            else:
                in_display_math = False
            continue
        if in_display_math:
            continue

        # Strip inline code before scanning inline syntax
        no_code = re.sub(r"`[^`\r\n]*`", "", line)

        hm = HEADING_RE.match(line)
        if hm:
            if cur_para_words > 0:
                paragraph_lengths.append(cur_para_words)
                cur_para_words = 0
            level = len(hm.group(1))
            htext = hm.group(2).strip()
            current_heading = htext
            headings.append({"level": level, "text": htext, "slug": heading_slug(htext), "line_idx": line_idx})
            section_stats.append(
                {
                    "heading": htext,
                    "level": level,
                    "line_idx": line_idx,
                    "link_count": 0,
                    "bullet_link_count": 0,
                    "bullet_prefixes": [],
                    "annotation_seps": [],
                    "has_query": False,
                    "links": [],
                }
            )
            continue

        cm = CALLOUT_RE.match(line)
        if cm:
            callouts.append(cm.group(1).lower())

        bm = BLOCK_ID_RE.search(no_code)
        if bm:
            block_ids.append(bm.group(1))

        tm = TASK_RE.match(line)
        if tm:
            tasks.append({"status": tm.group(1), "text": tm.group(2).strip()})

        # Inline tags (ignore URLs and anchors)
        no_links_for_tags = re.sub(r"https?://\S+", "", no_code)
        no_links_for_tags = re.sub(r"\[\[[^\]]+\]\]", "", no_links_for_tags)
        for tmatch in INLINE_TAG_RE.finditer(no_links_for_tags):
            tag = normalize_tag(tmatch.group(1))
            if tag and tag not in inline_tags:
                inline_tags.append(tag)

        # Wikilinks & embeds
        line_links: list[str] = []
        for wm in WIKILINK_RE.finditer(no_code):
            parsed = parse_wikilink_parts(wm.group(2), is_embed=bool(wm.group(1)))
            wikilinks.append(parsed)
            if parsed["embed"] and parsed["note"].lower().endswith(".base"):
                base_embeds.append(parsed["note"])
                section_stats[-1]["has_query"] = True
            elif parsed["note"]:
                line_links.append(parsed["note"])
                section_stats[-1]["link_count"] += 1
                section_stats[-1]["links"].append(parsed["note"])

        # Markdown links
        for mm in MDLINK_RE.finditer(no_code):
            href = mm.group(2).strip()
            md_links.append({"label": mm.group(1), "href": href})
            if not href.startswith(("http://", "https://", "mailto:")):
                line_links.append(href)
                section_stats[-1]["link_count"] += 1
                section_stats[-1]["links"].append(href)

        # Dataview inline fields
        dvm = DV_INLINE_FIELD_RE.match(no_code)
        if dvm:
            k = dvm.group(1).strip()
            v = dvm.group(2).strip()
            # Heuristic: Dataview keys are short single/two words, SR questions are longer
            if len(k) <= 25 and " " not in k and not k.endswith("?"):
                dv_fields.setdefault(k, []).append(v)
            elif "::" in no_code and not dvm.group(1).strip().startswith("http"):
                sr_single_cards += 1
        for bvm in DV_BRACKET_FIELD_RE.finditer(no_code):
            dv_fields.setdefault(bvm.group(1).strip(), []).append(bvm.group(2).strip())

        if SR_MULTI_RE.match(stripped):
            sr_multi_cards += 1
        if CLOZE_RE.search(no_code):
            cloze_cards += 1

        # Inline math count
        inline_math_count += len(re.findall(r"(?<!\\)\$[^$\r\n]+?(?<!\\)\$", no_code))

        # Line classification
        bullet_m = re.match(r"^(\s*(?:[-*+]|\d+\.)(?:\s+\[[ xX/\->!?]\])?\s+)", line)
        if stripped.startswith("|") and stripped.endswith("|"):
            table_lines += 1
        elif bullet_m:
            bullet_lines += 1
            if line_links:
                bullet_link_lines += 1
                sec = section_stats[-1]
                sec["bullet_link_count"] += 1
                pref = bullet_m.group(1).lstrip()
                if pref not in sec["bullet_prefixes"]:
                    sec["bullet_prefixes"].append(pref)
                # Detect annotation separator after link
                after_link = re.sub(r".*(?:\[\[[^\]]+\]\]|\[[^\]]*\]\([^)]+\))\s*", "", stripped)
                for sep in (" — ", " - ", ": ", " | "):
                    if after_link.startswith(sep.strip()):
                        if sep not in sec["annotation_seps"]:
                            sec["annotation_seps"].append(sep)
                        break
        elif not stripped.startswith(">"):
            prose_lines += 1
            cur_para_words += len(stripped.split())

    if cur_para_words > 0:
        paragraph_lengths.append(cur_para_words)

    word_count = len(re.findall(r"\b\w+\b", body))
    return {
        "headings": headings,
        "wikilinks": wikilinks,
        "md_links": md_links,
        "inline_tags": inline_tags,
        "block_ids": block_ids,
        "callouts": callouts,
        "code_langs": code_langs,
        "dv_fields": dv_fields,
        "dv_queries": dv_queries,
        "tasks": tasks,
        "mermaid_blocks": mermaid_blocks,
        "mermaid_examples": mermaid_examples,
        "base_embeds": base_embeds,
        "section_stats": section_stats,
        "display_math_count": display_math_count,
        "inline_math_count": inline_math_count,
        "bullet_lines": bullet_lines,
        "bullet_link_lines": bullet_link_lines,
        "prose_lines": prose_lines,
        "table_lines": table_lines,
        "sr_single_cards": sr_single_cards,
        "sr_multi_cards": sr_multi_cards,
        "cloze_cards": cloze_cards,
        "paragraph_lengths": paragraph_lengths,
        "word_count": word_count,
        "line_count": len(lines),
    }
