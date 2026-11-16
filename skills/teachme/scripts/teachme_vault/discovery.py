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
    extract_aliases,
    extract_frontmatter_tags,
    infer_property_type,
    parse_frontmatter_tolerant,
)
from .models import (
    atomic_write_text,
    read_text_safe,
    resolve_state_dir,
    safe_iter_files,
    utc_now_iso,
)
from .plugins import inspect_obsidian_plugins

MAX_PROFILE_READ_BYTES = 65536
MAX_STYLE_SAMPLES_PER_FOLDER = 12
MAX_STYLE_SAMPLES_GLOBAL = 300

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
    all_tags = list(dict.fromkeys(fm_tags + body_info["inline_tags"]))
    aliases = extract_aliases(meta)

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
    is_moc = (
        link_count >= 8
        or "moc" in path.stem.lower()
        or "index" in path.stem.lower()
        or any(t.lower() in ("moc", "index", "map-of-content") for t in all_tags)
    )

    rec: dict[str, Any] = {
        "rel_path": rel,
        "folder": folder,
        "stem": path.stem,
        "mtime_ns": stat.st_mtime_ns,
        "size": stat.st_size,
        "name_style": _classify_filename(path.stem),
        "title": str(meta.get("title") or (headings[0]["text"] if has_h1 else path.stem)),
        "aliases": aliases,
        "tags": all_tags,
        "prop_types": prop_types,
        "prop_samples": prop_samples,
        "yaml_valid": fm["valid"],
        "yaml_warnings": fm["warnings"],
        "is_moc": is_moc,
        "link_count": link_count,
        "word_count": body_info["word_count"],
        "has_tasks": len(body_info["tasks"]) > 0,
        "templater_hits": 1 if "<%" in raw_text else 0,
        "placeholder_hits": 1 if ("{{" in raw_text and "}}" in raw_text) else 0,
        "dv_queries": body_info["dv_queries"],
        "dv_fields": list(body_info["dv_fields"].keys()),
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

    # Aggregate folder, metadata, tag, naming, and style profiles
    folder_records: dict[str, list[dict[str, Any]]] = defaultdict(list)
    global_tags: Counter[str] = Counter()
    global_props: dict[str, Counter[str]] = defaultdict(Counter)
    global_prop_values: dict[str, Counter[str]] = defaultdict(Counter)
    global_name_styles: Counter[str] = Counter()
    global_styles: list[dict[str, Any]] = []
    moc_notes: list[dict[str, Any]] = []
    malformed_yaml_files: list[dict[str, Any]] = []
    folder_notes: dict[str, str] = {}

    for rel, rec in records.items():
        folder = rec["folder"]
        folder_records[folder].append(rec)
        global_tags.update(rec["tags"])
        global_name_styles[rec["name_style"]] += 1
        for k, t in rec["prop_types"].items():
            global_props[k][t] += 1
        for k, v in rec["prop_samples"].items():
            if len(global_prop_values[k]) < 20:
                global_prop_values[k][v] += 1
        if "style" in rec:
            global_styles.append(rec["style"])
        if rec["is_moc"]:
            moc_notes.append({"path": rel, "title": rec["title"], "links": rec["link_count"], "folder": folder})
        if not rec["yaml_valid"]:
            malformed_yaml_files.append({"path": rel, "warnings": rec["yaml_warnings"]})
        if folder:
            leaf = folder.split("/")[-1].lower()
            if rec["stem"].lower() in (leaf, "index", "_index"):
                folder_notes[folder] = rel

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
        f_props: dict[str, Counter[str]] = defaultdict(Counter)
        f_name_styles: Counter[str] = Counter()
        f_styles: list[dict[str, Any]] = []
        date_count = 0
        zettel_count = 0
        moc_count = 0
        task_notes = 0
        templater_hits = 0
        placeholder_hits = 0

        for r in recs:
            f_tags.update(r["tags"])
            f_name_styles[r["name_style"]] += 1
            for k, t in r["prop_types"].items():
                f_props[k][t] += 1
            if "style" in r:
                f_styles.append(r["style"])
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
        folders_profile[folder or "."] = {
            "path": folder,
            "role": role,
            "role_confidence": role_conf,
            "role_evidence": role_evidence,
            "file_count": len(recs),
            "naming_convention": dom_name_style,
            "top_tags": [t for t, _ in f_tags.most_common(12)],
            "properties": {
                k: cnt.most_common(1)[0][0] for k, cnt in sorted(f_props.items())
            },
            "folder_note": folder_notes.get(folder, ""),
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

    nested_tags = [t for t in global_tags if "/" in t]
    tag_hierarchy_roots = Counter(t.split("/")[0] for t in nested_tags)

    profile: dict[str, Any] = {
        "schema_version": 1,
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
            "uses_nested_tags": len(nested_tags) > 0,
            "top_tags": [{"tag": t, "count": c} for t, c in global_tags.most_common(30)],
            "nested_roots": [r for r, _ in tag_hierarchy_roots.most_common(15)],
        },
        "metadata_schema": metadata_schema,
        "mocs": sorted(moc_notes, key=lambda x: x["links"], reverse=True)[:30],
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


def load_or_discover_profile(
    vault_root: Path,
    refresh: bool = False,
    state_dir: Path | None = None,
) -> dict[str, Any]:
    """Load persisted vault profile if present and fresh, else run discovery."""
    root = vault_root.resolve()
    sdir = state_dir or resolve_state_dir(root)
    profile_path = sdir / "profile.json"
    if not refresh and profile_path.is_file():
        try:
            data = json.loads(read_text_safe(profile_path))
            if isinstance(data, dict) and data.get("vault_path") == str(root):
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
            "granularity": v["style"]["note_granularity"],
        }
        for k, v in profile.get("folders", {}).items()
    }
    return {
        "vault_path": profile.get("vault_path"),
        "vault_name": profile.get("vault_name"),
        "profiled_at": profile.get("profiled_at"),
        "total_notes": profile.get("total_notes"),
        "total_folders": profile.get("total_folders"),
        "organization_pattern": profile.get("organization_pattern"),
        "naming_convention": profile.get("naming_convention"),
        "global_style": profile.get("global_style"),
        "tag_taxonomy": profile.get("tag_taxonomy"),
        "metadata_schema": profile.get("metadata_schema"),
        "mocs": profile.get("mocs", [])[:15],
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
