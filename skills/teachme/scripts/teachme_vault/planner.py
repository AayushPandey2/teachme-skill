"""Context-aware knowledge integration and note generation planning."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .discovery import load_or_discover_profile
from .indexer import load_or_build_index, resolve_safe_wikilink, search_vault, tokenize
from .models import resolve_state_dir, today_iso
from .placement import format_note_filename, resolve_destination
from .templates import resolve_template


def _select_reusable_tags(
    topic: str,
    profile: dict[str, Any],
    target_folder: str,
    related_results: list[dict[str, Any]],
    keywords: list[str] | None = None,
    max_tags: int = 4,
) -> list[str]:
    """Select tags strictly from existing vault/folder vocabulary when evidence exists."""
    folder_info = profile.get("folders", {}).get(target_folder or ".", {})
    candidate_pool: list[str] = []

    for r in related_results[:5]:
        for t in r.get("tags", []):
            if t not in candidate_pool:
                candidate_pool.append(t)
    for t in folder_info.get("top_tags", []):
        if t not in candidate_pool:
            candidate_pool.append(t)

    topic_tokens = set(tokenize(topic))
    if keywords:
        for kw in keywords:
            topic_tokens.update(tokenize(kw))
    if target_folder:
        topic_tokens.update(tokenize(target_folder.replace("/", " ")))

    scored_tags: list[tuple[float, str]] = []
    for tag in candidate_pool:
        if tag.lower() in ("moc", "index", "template", "daily"):
            continue
        tag_tokens = set(tokenize(tag.replace("/", " ")))
        overlap = len(topic_tokens & tag_tokens)
        in_folder = 1 if tag in folder_info.get("top_tags", []) else 0
        in_related = sum(1 for r in related_results[:4] if tag in r.get("tags", []))
        score = overlap * 3.0 + in_folder * 1.5 + in_related * 1.5
        if score > 0:
            scored_tags.append((score, tag))

    scored_tags.sort(key=lambda x: x[0], reverse=True)
    chosen = [t for _, t in scored_tags[:max_tags]]

    # If folder has a strong consistent tag and nothing matched tokens, reuse top folder tag
    if not chosen and folder_info.get("top_tags"):
        for t in folder_info["top_tags"]:
            if t.lower() not in ("moc", "index", "template", "daily"):
                chosen.append(t)
                if len(chosen) >= 2:
                    break
    return chosen


def _recommend_frontmatter(
    topic: str,
    profile: dict[str, Any],
    target_folder: str,
    tags: list[str],
    template_res: dict[str, Any],
) -> dict[str, Any]:
    """Build frontmatter matching the target folder and vault metadata schema."""
    folder_info = profile.get("folders", {}).get(target_folder or ".", {})
    folder_props = folder_info.get("properties", {})
    global_schema = profile.get("metadata_schema", {})
    tpl_info = template_res.get("template_info") or {}
    tpl_keys = set(tpl_info.get("frontmatter_keys", []))

    fm: dict[str, Any] = {}
    # Include keys observed in folder schema (>20% global or folder-specific) or template
    candidate_keys = set(folder_props.keys()) | tpl_keys
    for key, info in global_schema.items():
        if info.get("frequency", 0) >= 0.35:
            candidate_keys.add(key)

    today = today_iso()
    if "title" in candidate_keys:
        fm["title"] = topic
    if tags or "tags" in candidate_keys:
        fm["tags"] = tags
    if "aliases" in candidate_keys:
        fm["aliases"] = []
    for date_key in ("created", "date", "created_at", "updated"):
        if date_key in candidate_keys:
            fm[date_key] = today
    if "status" in candidate_keys:
        common_vals = global_schema.get("status", {}).get("common_values", [])
        fm["status"] = common_vals[0] if common_vals else "seedling"
    if "type" in candidate_keys:
        common_vals = global_schema.get("type", {}).get("common_values", [])
        fm["type"] = "concept" if "concept" in common_vals else (common_vals[0] if common_vals else "note")

    # Preserve any Dataview queried fields observed in vault if present in folder
    dv_fields = profile.get("plugins", {}).get("conventions", {}).get("dataview_queried_fields", [])
    for df in dv_fields:
        if df in folder_props and df not in fm:
            ptype = folder_props[df]
            fm[df] = today if ptype == "date" else ([] if ptype == "list" else "")

    return fm


def plan_note(
    vault_root: Path,
    topic: str,
    explicit_folder: str | None = None,
    explicit_template: str | None = None,
    keywords: list[str] | None = None,
    refresh: bool = False,
    state_dir: Path | None = None,
) -> dict[str, Any]:
    """Create a complete, evidence-backed note placement, linking, and style plan."""
    root = vault_root.resolve()
    sdir = state_dir or resolve_state_dir(root)
    profile = load_or_discover_profile(root, refresh=refresh, state_dir=sdir)
    index = load_or_build_index(root, refresh=refresh, state_dir=sdir)

    search_query = " ".join([topic] + (keywords or []))
    search_res = search_vault(
        root,
        search_query,
        limit=10,
        index=index,
        exclude_roles={"templates", "attachments", "archive", "protected_assets"},
        profile=profile,
    )
    placement_search = (
        search_vault(
            root,
            topic,
            limit=10,
            index=index,
            exclude_roles={"templates", "attachments", "archive", "protected_assets"},
            profile=profile,
        )
        if keywords
        else search_res
    )
    matches = search_res["results"]

    # Detect existing note / duplicate overlap
    exact_matches = [m for m in matches if m.get("exact_title_match")]
    strong_overlaps = [m for m in matches if m["score"] >= 22.0]
    existing_target = exact_matches[0] if exact_matches else (strong_overlaps[0] if strong_overlaps else None)

    dest = resolve_destination(
        topic=topic,
        profile=profile,
        search_results=placement_search if placement_search.get("results") else search_res,
        explicit_folder=explicit_folder,
        keywords=keywords,
    )
    target_folder = dest["recommended_folder"]

    template_res = resolve_template(
        vault_root=root,
        profile=profile,
        target_folder=target_folder,
        topic=topic,
        note_type="concept",
        explicit_template=explicit_template,
    )

    folder_info = profile.get("folders", {}).get(target_folder or ".", {})
    folder_style = folder_info.get("style", {})
    if not folder_style or folder_style.get("sample_count", 0) == 0:
        folder_style = profile.get("global_style", {})

    granularity = folder_style.get("note_granularity", "balanced")
    org_primary = profile.get("organization_pattern", {}).get("primary", "topic_hierarchy")

    if existing_target is not None:
        recommended_action = "extend_existing"
    elif granularity == "atomic" or org_primary == "zettelkasten":
        recommended_action = "split_atomic"
    else:
        recommended_action = "create_new"

    existing_stems = {
        d["stem"] for d in index.get("docs", {}).values()
        if d.get("folder", "") == target_folder
    }
    filename = format_note_filename(topic, dest["naming_convention"], existing_stems=existing_stems)
    proposed_rel_path = f"{target_folder}/{filename}" if target_folder else filename

    # Build verified wikilinks from relevant notes (never fabricate targets!)
    link_style = folder_style.get("link_style", "wikilink")
    verified_links: list[dict[str, Any]] = []
    for m in matches[:6]:
        if existing_target and m["rel_path"] == existing_target["rel_path"]:
            continue
        wlink = resolve_safe_wikilink(m["rel_path"], index, preferred_style=link_style)
        if wlink:
            verified_links.append(
                {
                    "rel_path": m["rel_path"],
                    "title": m["title"],
                    "wikilink": wlink,
                    "score": m["score"],
                    "reasons": m["reasons"],
                    "headings": m["headings"][:5],
                }
            )

    tags = _select_reusable_tags(topic, profile, target_folder, matches, keywords=keywords)
    frontmatter = _recommend_frontmatter(topic, profile, target_folder, tags, template_res)

    return {
        "topic": topic,
        "vault_path": str(root),
        "recommended_action": recommended_action,
        "existing_note": existing_target,
        "destination": {
            "folder": target_folder,
            "filename": filename,
            "proposed_rel_path": proposed_rel_path,
            "confidence": dest["confidence"],
            "needs_confirmation": dest["needs_confirmation"],
            "evidence": dest["evidence"],
            "alternatives": dest["candidates"][1:4],
        },
        "template": {
            "selected": template_res["selected"],
            "priority_level": template_res["priority_level"],
            "confidence": template_res["confidence"],
            "needs_confirmation": template_res["needs_confirmation"],
            "reason": template_res["reason"],
            "alternatives": template_res["alternatives"],
        },
        "frontmatter": frontmatter,
        "tags": tags,
        "relevant_notes": verified_links,
        "style_guidance": {
            "granularity": granularity,
            "style_preference": folder_style.get("style_preference", "mixed"),
            "uses_h1": folder_style.get("uses_h1", True),
            "numbered_headings": folder_style.get("numbered_headings", False),
            "common_callouts": folder_style.get("common_callouts", ["note"]),
            "uses_math": folder_style.get("uses_math", True),
            "uses_tables": folder_style.get("uses_tables", True),
            "uses_mermaid": folder_style.get("uses_mermaid", False),
            "flashcard_syntax": folder_style.get("flashcard_syntax", "inline_double_colon"),
            "link_style": link_style,
            "common_summary_headings": folder_style.get("common_summary_headings", []),
        },
        "plugin_conventions": profile.get("plugins", {}).get("conventions", {}),
        "safety": {
            "teachme_state_dir": str(sdir),
            "will_modify_existing_user_notes": False,
        },
    }
