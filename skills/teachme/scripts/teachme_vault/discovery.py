"""Vault discovery, folder/metadata/style profiling, and incremental persistence."""

from __future__ import annotations

from collections import Counter, defaultdict
import json
from pathlib import Path
import re
import statistics
from typing import Any

from .markdown_utils import (
    analyze_markdown_body,
    classify_tag_case,
    extract_aliases,
    extract_frontmatter_links,
    extract_frontmatter_tags,
    infer_property_type,
    is_workflow_or_status_tag,
    parse_frontmatter_tolerant,
)
from .models import (
    atomic_write_text,
    read_text_safe,
    resolve_state_dir,
    safe_iter_files,
    utc_now_iso,
)
from .plugins import _parse_dql_signals, inspect_obsidian_plugins

PROFILE_SCHEMA_VERSION = 2
MAX_PROFILE_READ_BYTES = 65536
MAX_STYLE_SAMPLES_PER_FOLDER = 12
MAX_STYLE_SAMPLES_GLOBAL = 300
MAX_MERMAID_EXAMPLES = 10

HUB_TITLE_WORD_RE = re.compile(r"\b(?:moc|mocs|hub|map\s+of\s+content)\b", re.IGNORECASE)
INDEX_TITLE_WORD_RE = re.compile(r"\b(?:index|_index)\b", re.IGNORECASE)
MOC_EXPLICIT_TYPES = frozenset({"moc", "index", "hub", "map-of-content", "map of content"})

ZETTEL_NAME_RE = re.compile(r"^\d{10,14}(?:[-_\s].*)?$")
NUMERIC_PREFIX_RE = re.compile(r"^\d{1,4}[-_.\s].+")
DATE_NAME_RE = re.compile(r"^\d{4}-\d{2}(?:-\d{2}|-W\d{2})?(?:[-_\s].*)?$")
KEBAB_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)+$")
SNAKE_RE = re.compile(r"^[a-z0-9]+(?:_[a-z0-9]+)+$")


def _classify_filename(stem: str) -> str:
    if DATE_NAME_RE.match(stem):
        return "date_named"
    if ZETTEL_NAME_RE.match(stem):
        return "zettelkasten_timestamp"
    if NUMERIC_PREFIX_RE.match(stem):
        return "numeric_prefix"
    if KEBAB_RE.match(stem):
        return "kebab_case"
    if SNAKE_RE.match(stem):
        return "snake_case"
    if " " in stem and stem == stem.title():
        return "title_case"
    if " " in stem:
        return "spaced_phrase"
    return "single_or_mixed"


def _confidence_from_count(count: int, ratio: float = 1.0) -> str:
    if count >= 5 and ratio >= 0.6:
        return "high"
    if count >= 2 and ratio >= 0.35:
        return "medium"
    return "low"


def _aggregate_style_stats(samples: list[dict[str, Any]]) -> dict[str, Any]:
    if not samples:
        return {
            "sample_count": 0,
            "note_granularity": "unknown",
            "median_words": 0,
            "bullet_vs_prose_ratio": 0.0,
            "uses_h1": False,
            "numbered_headings": False,
            "common_callouts": [],
            "common_code_langs": [],
            "uses_math": False,
            "uses_tables": False,
            "uses_mermaid": False,
            "flashcard_syntax": "none",
            "link_style": "wikilink",
            "common_summary_headings": [],
            "confidence": "low",
        }

    words = [s["word_count"] for s in samples]
    med_words = int(statistics.median(words)) if words else 0
    total_bullets = sum(s["bullet_lines"] for s in samples)
    total_prose = sum(s["prose_lines"] for s in samples)
    bp_ratio = round(total_bullets / max(1, total_bullets + total_prose), 2)

    h1_hits = sum(1 for s in samples if s["has_h1"])
    numbered_hits = sum(1 for s in samples if s["has_numbered_headings"])
    callout_counter: Counter[str] = Counter()
    lang_counter: Counter[str] = Counter()
    summary_counter: Counter[str] = Counter()
    math_notes = 0
    table_notes = 0
    mermaid_notes = 0
    wikilink_count = 0
    mdlink_count = 0
    folder_qual_links = 0
    sr_single = 0
    sr_multi = 0
    cloze = 0

    for s in samples:
        callout_counter.update(s["callouts"])
        lang_counter.update(s["code_langs"])
        summary_counter.update(s["summary_headings"])
        if s["math_count"] > 0:
            math_notes += 1
        if s["table_lines"] > 0:
            table_notes += 1
        if s["mermaid_blocks"] > 0:
            mermaid_notes += 1
        wikilink_count += s["wikilink_count"]
        mdlink_count += s["mdlink_count"]
        folder_qual_links += s["folder_qual_links"]
        sr_single += s["sr_single_cards"]
        sr_multi += s["sr_multi_cards"]
        cloze += s["cloze_cards"]

    n = len(samples)
    granularity = "atomic" if med_words < 280 else ("comprehensive" if med_words >= 550 else "balanced")
    if mdlink_count > wikilink_count * 1.5 and mdlink_count >= 3:
        link_style = "markdown"
    elif folder_qual_links > max(1, wikilink_count // 2):
        link_style = "wikilink_folder_qualified"
    else:
        link_style = "wikilink"

    if sr_single >= sr_multi and sr_single > 0:
        fc_syntax = "inline_double_colon"
    elif sr_multi > 0:
        fc_syntax = "multiline_question"
    elif cloze > 0:
        fc_syntax = "cloze"
    else:
        fc_syntax = "none"

    return {
        "sample_count": n,
        "note_granularity": granularity,
        "median_words": med_words,
        "mean_words": int(statistics.mean(words)) if words else 0,
        "bullet_vs_prose_ratio": bp_ratio,
        "style_preference": "bullet_heavy" if bp_ratio >= 0.6 else ("prose_heavy" if bp_ratio <= 0.3 else "mixed"),
        "uses_h1": h1_hits >= max(1, n // 2),
        "numbered_headings": numbered_hits >= max(1, n // 2),
        "common_callouts": [k for k, _ in callout_counter.most_common(5)],
        "common_code_langs": [k for k, _ in lang_counter.most_common(5)],
        "uses_math": math_notes >= max(1, n // 4),
        "uses_tables": table_notes >= max(1, n // 4),
        "uses_mermaid": mermaid_notes > 0,
        "flashcard_syntax": fc_syntax,
        "link_style": link_style,
        "common_summary_headings": [k for k, _ in summary_counter.most_common(5)],
        "confidence": _confidence_from_count(n, 0.7 if n >= 5 else 0.4),
    }


def _infer_folder_role(
    folder_rel: str,
    stats: dict[str, Any],
    plugin_info: dict[str, Any],
) -> tuple[str, list[str], str]:
    """Infer folder organizational role from content evidence and plugin config."""
    evidence: list[str] = []
    low = folder_rel.lower()
    parts = low.split("/")
    leaf = parts[-1] if folder_rel else ""

    if folder_rel in plugin_info.get("template_folders", []):
        evidence.append("Configured as template folder in .obsidian plugin settings")
        return "templates", evidence, "high"
    if folder_rel in plugin_info.get("periodic_folders", []):
        evidence.append("Configured as periodic/daily notes folder in .obsidian")
        return "periodic", evidence, "high"
    if folder_rel in plugin_info.get("protected_folders", []):
        evidence.append("Configured as protected/attachment/drawing folder in .obsidian")
        return "protected_assets", evidence, "high"

    if leaf in ("templates", "_templates", "template"):
        evidence.append("Folder name matches template directory convention")
        if stats["templater_hits"] > 0 or stats["placeholder_hits"] > 0:
            evidence.append("Contains template placeholder syntax")
            return "templates", evidence, "high"
        return "templates", evidence, "medium"

    if leaf in ("attachments", "assets", "media", "images", "files"):
        evidence.append("Folder name matches asset/attachment directory")
        return "attachments", evidence, "medium"

    if leaf in ("archive", "archives", "99-archive", "4-archive", "completed"):
        evidence.append("Archive folder convention")
        return "archive", evidence, "high"

    if leaf in ("inbox", "00-inbox", "fleeting", "scratch", "drafts", "temp"):
        evidence.append("Inbox/transient capture folder convention")
        return "inbox", evidence, "medium"

    if stats["date_named_count"] >= max(2, int(stats["file_count"] * 0.6)):
        evidence.append(f"{stats['date_named_count']}/{stats['file_count']} notes use date-based filenames")
        return "periodic", evidence, "high"

    if leaf in ("journal", "daily", "daily notes", "weekly", "periodic"):
        evidence.append("Journal/periodic folder naming")
        return "periodic", evidence, "medium"

    if stats["moc_count"] > 0 and stats["moc_count"] >= max(1, stats["file_count"] // 2):
        evidence.append("Majority of notes are high-link MOC/index hubs")
        return "moc_hub", evidence, "high"

    if stats["zettel_count"] >= max(3, int(stats["file_count"] * 0.5)):
        evidence.append("Notes use Zettelkasten timestamp IDs and high link density")
        return "zettelkasten", evidence, "high"

    if any(p in ("projects", "01-projects", "1-projects") for p in parts):
        evidence.append("Located under Projects hierarchy (PARA/project-oriented)")
        return "projects", evidence, "high"

    if stats["task_notes"] >= max(2, int(stats["file_count"] * 0.5)):
        evidence.append("Notes contain task checklists (project/action tracking)")
        return "projects", evidence, "medium"

    if stats["file_count"] > 0:
        evidence.append(f"Contains {stats['file_count']} topic/knowledge notes")
        return "knowledge", evidence, "high" if stats["file_count"] >= 3 else "medium"

    return "empty_or_container", ["Directory acts as a parent category"], "low"


def _detect_moc_signals(
    path: Path,
    folder: str,
    title: str,
    meta: dict[str, Any],
    all_tags: list[str],
    body_info: dict[str, Any],
    fm_links: dict[str, list[str]],
) -> dict[str, Any]:
    """Identify MOC/hub/index notes using multiple independent signals."""
    signals: list[str] = []
    link_count = len(body_info["wikilinks"]) + len(body_info["md_links"])
    bullet_links = body_info.get("bullet_link_lines", 0)
    bullet_lines = body_info.get("bullet_lines", 0)
    prose_lines = body_info.get("prose_lines", 0)
    sections = body_info.get("section_stats", [])
    sections_with_links = [s for s in sections if s["link_count"] > 0]
    dv_queries = body_info.get("dv_queries", [])
    base_embeds = body_info.get("base_embeds", [])

    # Signal 1: Explicit metadata / tags
    raw_type = str(meta.get("type") or meta.get("note_type") or meta.get("kind") or "").strip().lower()
    raw_css = meta.get("cssclasses") or meta.get("cssclass") or []
    css_list = [str(x).lower() for x in raw_css] if isinstance(raw_css, list) else [str(raw_css).lower()]
    has_moc_tag = any(t.lower() in ("moc", "map-of-content", "hub", "index") for t in all_tags)
    has_explicit_meta = raw_type in MOC_EXPLICIT_TYPES or any(c in ("moc", "index") for c in css_list) or has_moc_tag
    if has_explicit_meta:
        signals.append("explicit_moc_metadata_or_tag")

    # Signal 2: Hub title / word-boundary MOC or index / folder-note naming
    stem_low = path.stem.lower()
    folder_leaf = folder.split("/")[-1].lower() if folder else ""
    is_folder_note = bool(folder_leaf and stem_low in (folder_leaf, "index", "_index"))
    has_hub_title = bool(
        HUB_TITLE_WORD_RE.search(path.stem)
        or HUB_TITLE_WORD_RE.search(title)
        or INDEX_TITLE_WORD_RE.search(path.stem)
        or INDEX_TITLE_WORD_RE.search(title)
        or is_folder_note
    )
    if has_hub_title:
        signals.append("folder_note_naming" if is_folder_note else "hub_title_or_index_word")

    # Signal 3: Structured link list organization (single unified signal — not double-counted)
    total_non_empty = max(1, bullet_lines + prose_lines)
    list_link_ratio = bullet_links / total_non_empty
    has_structured_list = (
        (bullet_links >= 3 and (list_link_ratio >= 0.35 or len(sections_with_links) >= 2))
        or (has_hub_title and bullet_links >= 2 and list_link_ratio >= 0.5 and prose_lines <= 2)
        or (len(sections_with_links) >= 2 and link_count >= 4 and prose_lines <= bullet_links * 2)
    )
    if has_structured_list:
        signals.append("structured_link_list")

    # Signal 4: Query-driven hub (Dataview or Bases)
    has_query_hub = bool(dv_queries or base_embeds)
    if has_query_hub:
        signals.append("query_driven_dataview_or_base")

    # Signal 5: Pure index-like link hub (overwhelmingly link bullets, negligible prose)
    is_pure_link_index = (
        link_count >= 10
        and bullet_links >= 8
        and list_link_ratio >= 0.65
        and prose_lines <= 3
        and body_info.get("word_count", 0) < 250
    )
    if is_pure_link_index:
        signals.append("pure_link_index_ratio")

    # Signal 6: Parent hub references in frontmatter
    parent_refs: list[str] = []
    for k in ("up", "parent", "moc", "hub"):
        parent_refs.extend(fm_links.get(k, []))
    if parent_refs:
        signals.append("parent_hub_frontmatter_link")

    # Multi-signal decision rule:
    # A single "index" substring or high link count alone is NEVER sufficient.
    is_moc = False
    if has_explicit_meta and (link_count >= 1 or has_query_hub or has_hub_title):
        is_moc = True
    elif has_query_hub and (has_hub_title or has_explicit_meta or any("from " in q.lower() for q in dv_queries) or bool(base_embeds)):
        is_moc = True
    elif has_hub_title and (has_structured_list or bool(parent_refs)):
        is_moc = True
    elif is_pure_link_index and has_structured_list:
        is_moc = True

    if not is_moc:
        return {"is_moc": False, "signals": signals}

    if has_query_hub and bullet_links < 2:
        moc_kind = "query_driven"
    elif has_query_hub and bullet_links >= 2:
        moc_kind = "hybrid"
    elif is_folder_note:
        moc_kind = "folder_note"
    else:
        moc_kind = "manual"

    dql_req = _parse_dql_signals(dv_queries) if dv_queries else {"folders": [], "tags": [], "fields": []}
    compact_sections = [
        {
            "heading": s["heading"],
            "level": s["level"],
            "link_count": s["link_count"],
            "bullet_link_count": s["bullet_link_count"],
            "bullet_prefix": s["bullet_prefixes"][0] if s["bullet_prefixes"] else "- ",
            "annotation_sep": s["annotation_seps"][0] if s["annotation_seps"] else "",
            "has_query": s["has_query"],
            "links": s["links"][:15],
        }
        for s in sections
        if s["heading"] or s["link_count"] > 0 or s["has_query"]
    ][:20]

    confidence = "high" if (len(signals) >= 3 or has_explicit_meta) else "medium"
    return {
        "is_moc": True,
        "moc_kind": moc_kind,
        "signals": signals,
        "confidence": confidence,
        "sections": compact_sections,
        "query_requirements": dql_req,
        "base_embeds": base_embeds[:5],
        "parent_refs": parent_refs[:10],
        "outgoing_targets": [w["note"] for w in body_info["wikilinks"] if w["note"] and not w["embed"]][:60],
    }


def _summarize_note_record(path: Path, vault_root: Path, include_style: bool) -> dict[str, Any]:
    """Extract compact metadata + optional style signals from a single note."""
    rel = path.relative_to(vault_root).as_posix()
    folder = path.parent.relative_to(vault_root).as_posix()
    if folder == ".":
        folder = ""
    stat = path.stat()
    raw_text = read_text_safe(path, max_bytes=MAX_PROFILE_READ_BYTES)
    fm = parse_frontmatter_tolerant(raw_text)
    meta = fm["meta"]
    body = fm["body"]
    body_info = analyze_markdown_body(body)

    fm_tags = extract_frontmatter_tags(meta)
    inline_tags = body_info["inline_tags"]
    all_tags = list(dict.fromkeys(fm_tags + inline_tags))
    if fm_tags and inline_tags:
        tag_placement = "both"
    elif fm_tags:
        tag_placement = "frontmatter"
    elif inline_tags:
        tag_placement = "inline"
    else:
        tag_placement = "none"

    aliases = extract_aliases(meta)
    fm_links = extract_frontmatter_links(meta)

    prop_types: dict[str, str] = {}
    prop_samples: dict[str, Any] = {}
    for k, v in meta.items():
        if k in ("tags", "tag", "aliases", "alias"):
            continue
        prop_types[k] = infer_property_type(v)
        if not isinstance(v, (list, dict)):
            prop_samples[k] = str(v)[:80]

    headings = body_info["headings"]
    has_h1 = any(h["level"] == 1 for h in headings)
    numbered_headings = sum(1 for h in headings if re.match(r"^\d+[\.)]\s+", h["text"])) >= 2
    summary_headings = [
        h["text"].lower()
        for h in headings
        if any(kw in h["text"].lower() for kw in ("summary", "takeaway", "tl;dr", "conclusion", "overview"))
    ]

    link_count = len(body_info["wikilinks"]) + len(body_info["md_links"])
    title = str(meta.get("title") or (headings[0]["text"] if has_h1 else path.stem))
    moc_eval = _detect_moc_signals(path, folder, title, meta, all_tags, body_info, fm_links)

    rec: dict[str, Any] = {
        "rel_path": rel,
        "folder": folder,
        "stem": path.stem,
        "mtime_ns": stat.st_mtime_ns,
        "size": stat.st_size,
        "name_style": _classify_filename(path.stem),
        "title": title,
        "aliases": aliases,
        "tags": all_tags,
        "fm_tags": fm_tags,
        "inline_tags": inline_tags,
        "tag_placement": tag_placement,
        "prop_types": prop_types,
        "prop_samples": prop_samples,
        "yaml_valid": fm["valid"],
        "yaml_warnings": fm["warnings"],
        "is_moc": moc_eval["is_moc"],
        "moc_info": moc_eval if moc_eval["is_moc"] else None,
        "link_count": link_count,
        "word_count": body_info["word_count"],
        "has_tasks": len(body_info["tasks"]) > 0,
        "templater_hits": 1 if "<%" in raw_text else 0,
        "placeholder_hits": 1 if ("{{" in raw_text and "}}" in raw_text) else 0,
        "dv_queries": body_info["dv_queries"],
        "dv_fields": list(body_info["dv_fields"].keys()),
        "mermaid_blocks": body_info["mermaid_blocks"],
        "mermaid_examples": body_info["mermaid_examples"][:3],
    }

    if include_style:
        folder_qual = sum(1 for w in body_info["wikilinks"] if "/" in w["note"])
        rec["style"] = {
            "word_count": body_info["word_count"],
            "bullet_lines": body_info["bullet_lines"],
            "prose_lines": body_info["prose_lines"],
            "has_h1": has_h1,
            "has_numbered_headings": numbered_headings,
            "callouts": body_info["callouts"],
            "code_langs": body_info["code_langs"],
            "math_count": body_info["display_math_count"] + body_info["inline_math_count"],
            "table_lines": body_info["table_lines"],
            "mermaid_blocks": body_info["mermaid_blocks"],
            "wikilink_count": len(body_info["wikilinks"]),
            "mdlink_count": len(body_info["md_links"]),
            "folder_qual_links": folder_qual,
            "sr_single_cards": body_info["sr_single_cards"],
            "sr_multi_cards": body_info["sr_multi_cards"],
            "cloze_cards": body_info["cloze_cards"],
            "summary_headings": summary_headings,
        }
    return rec


def discover_vault(
    vault_root: Path,
    refresh: bool = False,
    state_dir: Path | None = None,
) -> dict[str, Any]:
    """Discover and profile an Obsidian vault incrementally, persisting profile.json."""
    root = vault_root.resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"Vault directory not found: {root}")

    sdir = state_dir or resolve_state_dir(root)
    profile_path = sdir / "profile.json"
    existing_records: dict[str, dict[str, Any]] = {}

    if not refresh and profile_path.is_file():
        try:
            old_profile = json.loads(read_text_safe(profile_path))
            if old_profile.get("schema_version") == PROFILE_SCHEMA_VERSION:
                for rel, rec in old_profile.get("_file_cache", {}).items():
                    if isinstance(rec, dict):
                        existing_records[rel] = rec
        except (OSError, json.JSONDecodeError):
            existing_records = {}

    all_md = list(safe_iter_files(root, extensions=(".md",)))
    # Exclude .excalidraw.md from ordinary note profiling
    note_files = [p for p in all_md if not p.name.lower().endswith(".excalidraw.md")]

    # Bounded sampling decision per folder
    folder_counts: Counter[str] = Counter()
    for p in note_files:
        f = p.parent.relative_to(root).as_posix()
        folder_counts["" if f == "." else f] += 1

    sampled_per_folder: Counter[str] = Counter()
    global_style_count = 0
    records: dict[str, dict[str, Any]] = {}
    all_dv_queries: list[str] = []

    for p in note_files:
        rel = p.relative_to(root).as_posix()
        f = p.parent.relative_to(root).as_posix()
        folder = "" if f == "." else f
        st = p.stat()
        cached = existing_records.get(rel)
        need_style = (
            sampled_per_folder[folder] < MAX_STYLE_SAMPLES_PER_FOLDER
            and global_style_count < MAX_STYLE_SAMPLES_GLOBAL
        )

        if (
            cached
            and cached.get("mtime_ns") == st.st_mtime_ns
            and cached.get("size") == st.st_size
            and (not need_style or "style" in cached)
        ):
            rec = cached
        else:
            rec = _summarize_note_record(p, root, include_style=need_style)

        records[rel] = rec
        if "style" in rec:
            sampled_per_folder[folder] += 1
            global_style_count += 1
        all_dv_queries.extend(rec.get("dv_queries", []))

    plugin_info = inspect_obsidian_plugins(root, dataview_queries=all_dv_queries)
    plugin_tags: set[str] = set()
    for ft in plugin_info.get("conventions", {}).get("flashcard_tags", []):
        plugin_tags.add(str(ft).lstrip("#").lower())
    tgf = str(plugin_info.get("conventions", {}).get("task_global_filter", "")).strip()
    if tgf.startswith("#"):
        plugin_tags.add(tgf.lstrip("#").lower())

    # Aggregate folder, metadata, tag, naming, Mermaid, and MOC profiles
    folder_records: dict[str, list[dict[str, Any]]] = defaultdict(list)
    global_tags: Counter[str] = Counter()
    global_subject_tags: Counter[str] = Counter()
    global_workflow_tags: Counter[str] = Counter()
    global_tag_placement: Counter[str] = Counter()
    global_tag_case: Counter[str] = Counter()
    tag_evidence_paths: dict[str, list[str]] = defaultdict(list)
    placement_evidence: dict[str, list[str]] = defaultdict(list)

    global_props: dict[str, Counter[str]] = defaultdict(Counter)
    global_prop_values: dict[str, Counter[str]] = defaultdict(Counter)
    global_name_styles: Counter[str] = Counter()
    global_styles: list[dict[str, Any]] = []
    moc_notes: list[dict[str, Any]] = []
    malformed_yaml_files: list[dict[str, Any]] = []
    folder_notes: dict[str, str] = {}

    mermaid_examples_all: list[dict[str, Any]] = []
    mermaid_type_counts: Counter[str] = Counter()
    mermaid_dir_counts: Counter[str] = Counter()
    mermaid_heading_counts: Counter[str] = Counter()
    mermaid_class_defs: list[str] = []
    mermaid_init_directives: list[str] = []
    mermaid_subgraph_hits = 0
    mermaid_total = 0

    for rel, rec in records.items():
        folder = rec["folder"]
        folder_records[folder].append(rec)
        global_tags.update(rec["tags"])
        for t in rec["tags"]:
            if len(tag_evidence_paths[t]) < 5:
                tag_evidence_paths[t].append(rel)
            if is_workflow_or_status_tag(t, plugin_tags=plugin_tags):
                global_workflow_tags[t] += 1
            else:
                global_subject_tags[t] += 1
                global_tag_case[classify_tag_case(t)] += 1

        tp = rec.get("tag_placement", "none")
        if tp != "none":
            global_tag_placement[tp] += 1
            if len(placement_evidence[tp]) < 5:
                placement_evidence[tp].append(rel)

        global_name_styles[rec["name_style"]] += 1
        for k, t in rec["prop_types"].items():
            global_props[k][t] += 1
        for k, v in rec["prop_samples"].items():
            if len(global_prop_values[k]) < 20:
                global_prop_values[k][v] += 1
        if "style" in rec:
            global_styles.append(rec["style"])
        if rec["is_moc"]:
            minfo = rec.get("moc_info") or {}
            moc_notes.append(
                {
                    "path": rel,
                    "title": rec["title"],
                    "stem": rec["stem"],
                    "aliases": rec["aliases"],
                    "links": rec["link_count"],
                    "folder": folder,
                    "tags": rec["tags"],
                    "moc_kind": minfo.get("moc_kind", "manual"),
                    "signals": minfo.get("signals", []),
                    "confidence": minfo.get("confidence", "medium"),
                    "sections": minfo.get("sections", []),
                    "query_requirements": minfo.get("query_requirements", {}),
                    "parent_refs": minfo.get("parent_refs", []),
                    "outgoing_targets": minfo.get("outgoing_targets", []),
                }
            )
        if not rec["yaml_valid"]:
            malformed_yaml_files.append({"path": rel, "warnings": rec["yaml_warnings"]})
        if folder:
            leaf = folder.split("/")[-1].lower()
            if rec["stem"].lower() in (leaf, "index", "_index"):
                folder_notes[folder] = rel

        for mex in rec.get("mermaid_examples", []):
            mermaid_total += 1
            dtype = mex.get("diagram_type", "unknown")
            if dtype != "unknown":
                mermaid_type_counts[dtype] += 1
            if mex.get("direction"):
                mermaid_dir_counts[mex["direction"]] += 1
            if mex.get("nearest_heading"):
                mermaid_heading_counts[mex["nearest_heading"].lower()] += 1
            if mex.get("has_subgraph"):
                mermaid_subgraph_hits += 1
            for cd in mex.get("class_defs", []):
                if cd not in mermaid_class_defs and len(mermaid_class_defs) < 8:
                    mermaid_class_defs.append(cd)
            for idir in mex.get("init_directives", []):
                if idir not in mermaid_init_directives and len(mermaid_init_directives) < 4:
                    mermaid_init_directives.append(idir)
            if len(mermaid_examples_all) < MAX_MERMAID_EXAMPLES:
                mermaid_examples_all.append({"rel_path": rel, **mex})

    # Resolve MOC parent/child hierarchy
    moc_by_stem: dict[str, list[str]] = defaultdict(list)
    moc_by_path: dict[str, dict[str, Any]] = {}
    for m in moc_notes:
        moc_by_stem[m["stem"].lower()].append(m["path"])
        moc_by_path[m["path"]] = m
        m["parent_mocs"] = []
        m["child_mocs"] = []

    for m in moc_notes:
        for pref in m.get("parent_refs", []):
            clean = pref[:-3] if pref.endswith(".md") else pref
            cand = f"{clean}.md"
            if cand in moc_by_path:
                resolved_p = cand
            else:
                matches = moc_by_stem.get(Path(clean).name.lower(), [])
                resolved_p = matches[0] if len(matches) == 1 else ""
            if resolved_p and resolved_p != m["path"]:
                if resolved_p not in m["parent_mocs"]:
                    m["parent_mocs"].append(resolved_p)
                if m["path"] not in moc_by_path[resolved_p]["child_mocs"]:
                    moc_by_path[resolved_p]["child_mocs"].append(m["path"])

    # Include empty subdirectories in hierarchy awareness
    all_folders: set[str] = set(folder_records.keys())
    for d in root.rglob("*"):
        if d.is_dir() and not d.is_symlink():
            try:
                rel_d = d.relative_to(root).as_posix()
            except ValueError:
                continue
            parts = rel_d.split("/")
            if not any(part.startswith(".") or part in ("node_modules", "__pycache__") for part in parts):
                all_folders.add(rel_d)

    folders_profile: dict[str, Any] = {}
    for folder in sorted(all_folders):
        recs = folder_records.get(folder, [])
        f_tags: Counter[str] = Counter()
        f_subject_tags: Counter[str] = Counter()
        f_workflow_tags: Counter[str] = Counter()
        f_tag_placement: Counter[str] = Counter()
        f_tag_case: Counter[str] = Counter()
        f_props: dict[str, Counter[str]] = defaultdict(Counter)
        f_name_styles: Counter[str] = Counter()
        f_styles: list[dict[str, Any]] = []
        f_mermaid_types: Counter[str] = Counter()
        f_evidence_paths: list[str] = []
        date_count = 0
        zettel_count = 0
        moc_count = 0
        task_notes = 0
        templater_hits = 0
        placeholder_hits = 0

        for r in recs:
            if len(f_evidence_paths) < 6:
                f_evidence_paths.append(r["rel_path"])
            f_tags.update(r["tags"])
            for t in r["tags"]:
                if is_workflow_or_status_tag(t, plugin_tags=plugin_tags):
                    f_workflow_tags[t] += 1
                else:
                    f_subject_tags[t] += 1
                    f_tag_case[classify_tag_case(t)] += 1
            tp = r.get("tag_placement", "none")
            if tp != "none":
                f_tag_placement[tp] += 1
            f_name_styles[r["name_style"]] += 1
            for k, t in r["prop_types"].items():
                f_props[k][t] += 1
            if "style" in r:
                f_styles.append(r["style"])
            for mex in r.get("mermaid_examples", []):
                dt = mex.get("diagram_type", "unknown")
                if dt != "unknown":
                    f_mermaid_types[dt] += 1
            if r["name_style"] == "date_named":
                date_count += 1
            if r["name_style"] == "zettelkasten_timestamp":
                zettel_count += 1
            if r["is_moc"]:
                moc_count += 1
            if r["has_tasks"]:
                task_notes += 1
            templater_hits += r["templater_hits"]
            placeholder_hits += r["placeholder_hits"]

        role, role_evidence, role_conf = _infer_folder_role(
            folder,
            {
                "file_count": len(recs),
                "date_named_count": date_count,
                "zettel_count": zettel_count,
                "moc_count": moc_count,
                "task_notes": task_notes,
                "templater_hits": templater_hits,
                "placeholder_hits": placeholder_hits,
            },
            plugin_info,
        )

        dom_name_style = f_name_styles.most_common(1)[0][0] if f_name_styles else "unknown"
        dom_tag_place = f_tag_placement.most_common(1)[0][0] if f_tag_placement else "unknown"
        dom_tag_case = f_tag_case.most_common(1)[0][0] if f_tag_case else "unknown"
        folders_profile[folder or "."] = {
            "path": folder,
            "role": role,
            "role_confidence": role_conf,
            "role_evidence": role_evidence,
            "file_count": len(recs),
            "naming_convention": dom_name_style,
            "top_tags": [t for t, _ in f_tags.most_common(12)],
            "subject_tags": [{"tag": t, "count": c} for t, c in f_subject_tags.most_common(20)],
            "workflow_tags": [{"tag": t, "count": c} for t, c in f_workflow_tags.most_common(10)],
            "tag_placement": dom_tag_place,
            "tag_case": dom_tag_case,
            "mermaid_types": [t for t, _ in f_mermaid_types.most_common(4)],
            "properties": {
                k: cnt.most_common(1)[0][0] for k, cnt in sorted(f_props.items())
            },
            "folder_note": folder_notes.get(folder, ""),
            "evidence_paths": f_evidence_paths,
            "style": _aggregate_style_stats(f_styles),
        }

    # Detect overarching vault architecture pattern
    top_folders_lower = {f.split("/")[0].lower() for f in all_folders if f}
    para_hits = sum(
        1 for kw in ("project", "area", "resource", "archive")
        if any(kw in tf for tf in top_folders_lower)
    )
    total_zettel = sum(1 for r in records.values() if r["name_style"] == "zettelkasten_timestamp")
    if para_hits >= 3:
        org_pattern = "para"
    elif total_zettel >= max(5, int(len(records) * 0.4)):
        org_pattern = "zettelkasten"
    elif len([f for f in all_folders if f]) >= 3:
        org_pattern = "topic_hierarchy"
    else:
        org_pattern = "flat_or_mixed"

    dom_global_naming = global_name_styles.most_common(1)[0][0] if global_name_styles else "title_case"
    global_style = _aggregate_style_stats(global_styles)

    # Global metadata schema summary
    metadata_schema: dict[str, Any] = {}
    for prop, type_counts in sorted(global_props.items()):
        total_prop = sum(type_counts.values())
        dom_type = type_counts.most_common(1)[0][0]
        metadata_schema[prop] = {
            "type": dom_type,
            "count": total_prop,
            "frequency": round(total_prop / max(1, len(records)), 3),
            "common_values": [v for v, _ in global_prop_values[prop].most_common(6)],
        }

    nested_subject = [t for t in global_subject_tags if "/" in t]
    tag_hierarchy_roots = Counter(t.split("/")[0] for t in nested_subject)
    nested_children: dict[str, list[str]] = defaultdict(list)
    for t in sorted(global_subject_tags):
        if "/" in t:
            root_ns = t.split("/")[0]
            if len(nested_children[root_ns]) < 15:
                nested_children[root_ns].append(t)

    dom_tag_placement = global_tag_placement.most_common(1)[0][0] if global_tag_placement else "frontmatter"
    total_tagged_notes = sum(global_tag_placement.values())
    if global_tag_placement.get("frontmatter", 0) > 0 and global_tag_placement.get("inline", 0) > 0:
        min_side = min(global_tag_placement["frontmatter"], global_tag_placement["inline"])
        if min_side >= 2 or (total_tagged_notes > 0 and (min_side / total_tagged_notes) >= 0.2):
            dom_tag_placement = "both"

    dom_tag_case = global_tag_case.most_common(1)[0][0] if global_tag_case else "kebab_case"

    mermaid_conventions = {
        "uses_mermaid": mermaid_total > 0,
        "total_diagrams": mermaid_total,
        "preferred_types": [t for t, _ in mermaid_type_counts.most_common(4)],
        "preferred_direction": mermaid_dir_counts.most_common(1)[0][0] if mermaid_dir_counts else "TD",
        "uses_subgraphs": mermaid_subgraph_hits > 0,
        "reusable_class_defs": mermaid_class_defs,
        "init_directives": mermaid_init_directives,
        "common_headings": [h for h, _ in mermaid_heading_counts.most_common(4)],
        "examples": mermaid_examples_all,
        "confidence": _confidence_from_count(mermaid_total, 0.7 if mermaid_total >= 2 else 0.4),
    }

    profile: dict[str, Any] = {
        "schema_version": PROFILE_SCHEMA_VERSION,
        "vault_path": str(root),
        "vault_name": root.name,
        "profiled_at": utc_now_iso(),
        "total_notes": len(records),
        "total_folders": len(folders_profile),
        "organization_pattern": {
            "primary": org_pattern,
            "confidence": "high" if len(records) >= 10 else ("medium" if len(records) >= 3 else "low"),
            "has_para_signals": para_hits >= 3,
            "zettelkasten_ratio": round(total_zettel / max(1, len(records)), 3),
        },
        "naming_convention": {
            "primary": dom_global_naming,
            "distribution": dict(global_name_styles),
        },
        "global_style": global_style,
        "tag_taxonomy": {
            "total_unique_tags": len(global_tags),
            "subject_tag_count": len(global_subject_tags),
            "workflow_tag_count": len(global_workflow_tags),
            "uses_nested_tags": len(nested_subject) > 0,
            "placement": dom_tag_placement,
            "placement_distribution": dict(global_tag_placement),
            "placement_evidence": dict(placement_evidence),
            "case_style": dom_tag_case,
            "case_distribution": dict(global_tag_case),
            "top_tags": [{"tag": t, "count": c} for t, c in global_tags.most_common(30)],
            "subject_tags": [{"tag": t, "count": c} for t, c in global_subject_tags.most_common(80)],
            "all_subject_tags": {t: c for t, c in global_subject_tags.most_common(400)},
            "workflow_tags": [{"tag": t, "count": c} for t, c in global_workflow_tags.most_common(30)],
            "nested_roots": [r for r, _ in tag_hierarchy_roots.most_common(15)],
            "nested_children": dict(nested_children),
            "tag_evidence_paths": {t: tag_evidence_paths[t] for t, _ in global_subject_tags.most_common(40)},
        },
        "metadata_schema": metadata_schema,
        "mocs": sorted(moc_notes, key=lambda x: x["links"], reverse=True)[:40],
        "mermaid_conventions": mermaid_conventions,
        "folders": folders_profile,
        "plugins": plugin_info,
        "health": {
            "malformed_yaml_count": len(malformed_yaml_files),
            "malformed_yaml_sample": malformed_yaml_files[:15],
        },
        "_file_cache": records,
    }

    sdir.mkdir(parents=True, exist_ok=True)
    atomic_write_text(profile_path, json.dumps(profile, indent=2, ensure_ascii=False) + "\n")
    return profile


def _is_profile_stale(root: Path, cached_profile: dict[str, Any]) -> bool:
    """Fast check for added, deleted, renamed, or modified Markdown files or .obsidian configs."""
    if cached_profile.get("schema_version") != PROFILE_SCHEMA_VERSION:
        return True
    file_cache = cached_profile.get("_file_cache", {})
    if not isinstance(file_cache, dict):
        return True

    current_files = [
        p for p in safe_iter_files(root, extensions=(".md",))
        if not p.name.lower().endswith(".excalidraw.md")
    ]
    if len(current_files) != len(file_cache):
        return True

    for p in current_files:
        rel = p.relative_to(root).as_posix()
        cached_rec = file_cache.get(rel)
        if not isinstance(cached_rec, dict):
            return True
        st = p.stat()
        if cached_rec.get("mtime_ns") != st.st_mtime_ns or cached_rec.get("size") != st.st_size:
            return True
    return False


def load_or_discover_profile(
    vault_root: Path,
    refresh: bool = False,
    state_dir: Path | None = None,
) -> dict[str, Any]:
    """Load persisted vault profile if present and fresh, else run incremental discovery."""
    root = vault_root.resolve()
    sdir = state_dir or resolve_state_dir(root)
    profile_path = sdir / "profile.json"
    if not refresh and profile_path.is_file():
        try:
            data = json.loads(read_text_safe(profile_path))
            if isinstance(data, dict) and data.get("vault_path") == str(root):
                if not _is_profile_stale(root, data):
                    return data
        except (OSError, json.JSONDecodeError):
            pass
    return discover_vault(root, refresh=refresh, state_dir=sdir)


def summarize_profile_for_display(profile: dict[str, Any]) -> dict[str, Any]:
    """Return a token-efficient summary of the vault profile (without internal cache)."""
    folders_compact = {
        k: {
            "role": v["role"],
            "confidence": v["role_confidence"],
            "files": v["file_count"],
            "naming": v["naming_convention"],
            "top_tags": v["top_tags"][:5],
            "tag_placement": v.get("tag_placement", "unknown"),
            "tag_case": v.get("tag_case", "unknown"),
            "granularity": v["style"]["note_granularity"],
        }
        for k, v in profile.get("folders", {}).items()
    }
    tax = profile.get("tag_taxonomy", {})
    tax_display = {
        "total_unique_tags": tax.get("total_unique_tags", 0),
        "subject_tag_count": tax.get("subject_tag_count", 0),
        "workflow_tag_count": tax.get("workflow_tag_count", 0),
        "uses_nested_tags": tax.get("uses_nested_tags", False),
        "placement": tax.get("placement", "frontmatter"),
        "case_style": tax.get("case_style", "kebab_case"),
        "top_tags": tax.get("top_tags", [])[:20],
        "subject_tags": tax.get("subject_tags", [])[:25],
        "workflow_tags": tax.get("workflow_tags", [])[:15],
        "nested_roots": tax.get("nested_roots", []),
    }
    mocs_compact = [
        {
            "path": m.get("path"),
            "title": m.get("title"),
            "moc_kind": m.get("moc_kind", "manual"),
            "links": m.get("links", 0),
            "confidence": m.get("confidence", "medium"),
            "signals": m.get("signals", []),
            "parent_mocs": m.get("parent_mocs", []),
        }
        for m in profile.get("mocs", [])[:15]
    ]
    return {
        "vault_path": profile.get("vault_path"),
        "vault_name": profile.get("vault_name"),
        "profiled_at": profile.get("profiled_at"),
        "total_notes": profile.get("total_notes"),
        "total_folders": profile.get("total_folders"),
        "organization_pattern": profile.get("organization_pattern"),
        "naming_convention": profile.get("naming_convention"),
        "global_style": profile.get("global_style"),
        "tag_taxonomy": tax_display,
        "metadata_schema": profile.get("metadata_schema"),
        "mocs": mocs_compact,
        "mermaid_conventions": profile.get("mermaid_conventions", {}),
        "folders": folders_compact,
        "plugins": {
            "has_obsidian": profile.get("plugins", {}).get("has_obsidian"),
            "template_folders": profile.get("plugins", {}).get("template_folders", []),
            "folder_templates": profile.get("plugins", {}).get("folder_templates", {}),
            "conventions": profile.get("plugins", {}).get("conventions", {}),
            "capabilities": [
                {
                    "id": c["id"],
                    "name": c["name"],
                    "enabled": c["enabled"],
                    "status": c["status"],
                }
                for c in profile.get("plugins", {}).get("capabilities", [])
            ],
        },
        "health": profile.get("health"),
    }
