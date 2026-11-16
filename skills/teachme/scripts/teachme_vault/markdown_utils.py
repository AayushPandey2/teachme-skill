"""Fault-tolerant Markdown, YAML frontmatter, and Obsidian syntax parsers."""

from __future__ import annotations

import re
from typing import Any

FENCE_RE = re.compile(r"^\s*(`{3,}|~{3,})(.*)$")
HEADING_RE = re.compile(r"^\s{0,3}(#{1,6})\s+(.+?)\s*$")
WIKILINK_RE = re.compile(r"(!?)\[\[([^\[\]\r\n]+)\]\]")
MDLINK_RE = re.compile(r"(?<!!)\[([^\]]*)\]\(([^)]+)\)")
INLINE_TAG_RE = re.compile(
    r"(?:^|(?<=[\s,(]))#([A-Za-z_][A-Za-z0-9_/-]*[A-Za-z0-9_]|[A-Za-z][A-Za-z0-9_-]*)"
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


def analyze_markdown_body(body: str) -> dict[str, Any]:
    """Extract headings, links, inline tags, block IDs, and style signals from Markdown body."""
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

    in_fence = False
    fence_char = ""
    fence_lang = ""
    fence_lines: list[str] = []
    in_display_math = False
    display_math_count = 0
    inline_math_count = 0
    bullet_lines = 0
    prose_lines = 0
    table_lines = 0
    mermaid_blocks = 0
    sr_single_cards = 0
    sr_multi_cards = 0
    cloze_cards = 0
    paragraph_lengths: list[int] = []
    cur_para_words = 0

    for line in lines:
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
            headings.append({"level": level, "text": htext, "slug": heading_slug(htext)})
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
        for wm in WIKILINK_RE.finditer(no_code):
            parsed = parse_wikilink_parts(wm.group(2), is_embed=bool(wm.group(1)))
            wikilinks.append(parsed)

        # Markdown links
        for mm in MDLINK_RE.finditer(no_code):
            md_links.append({"label": mm.group(1), "href": mm.group(2).strip()})

        # Dataview inline fields
        dvm = DV_INLINE_FIELD_RE.match(no_code)
        if dvm and not SR_SINGLE_RE.match(no_code.split("::", 1)[0] + "::"):
            pass
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
        if stripped.startswith("|") and stripped.endswith("|"):
            table_lines += 1
        elif re.match(r"^(?:[-*+]|\d+\.)\s+", stripped):
            bullet_lines += 1
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
        "display_math_count": display_math_count,
        "inline_math_count": inline_math_count,
        "bullet_lines": bullet_lines,
        "prose_lines": prose_lines,
        "table_lines": table_lines,
        "sr_single_cards": sr_single_cards,
        "sr_multi_cards": sr_multi_cards,
        "cloze_cards": cloze_cards,
        "paragraph_lengths": paragraph_lengths,
        "word_count": word_count,
        "line_count": len(lines),
    }
