"""Context-aware knowledge integration and note generation planning."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .discovery import load_or_discover_profile
from .indexer import load_or_build_index, resolve_safe_wikilink, search_vault
from .mermaid import plan_mermaid_diagram
from .moc import plan_moc_integration
from .models import (
    atomic_write_text,
    is_within_root,
    read_text_safe,
    resolve_state_dir,
    sha256_text,
    today_iso,
    utc_now_iso,
)
from .placement import format_note_filename, resolve_destination
from .renderer import render_target_note_file
from .tagging import select_and_plan_tags
from .templates import resolve_template


def _recommend_frontmatter(
    topic: str,
    profile: dict[str, Any],
    target_folder: str,
    tags: list[str],
    template_res: dict[str, Any],
    extra_query_fields: list[str] | None = None,
) -> dict[str, Any]:
    """Build frontmatter matching the target folder and vault metadata schema."""
    folder_info = profile.get("folders", {}).get(target_folder or ".", {})
    folder_props = folder_info.get("properties", {})
    global_schema = profile.get("metadata_schema", {})
    tpl_info = template_res.get("template_info") or {}
    tpl_keys = set(tpl_info.get("frontmatter_keys", []))

    fm: dict[str, Any] = {}
    candidate_keys = set(folder_props.keys()) | tpl_keys | set(extra_query_fields or [])
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
        common_vals = [
            v for v in global_schema.get("status", {}).get("common_values", [])
            if str(v).lower() not in ("archived", "archive", "mastered", "reviewed")
        ]
        fm["status"] = common_vals[0] if common_vals else "seedling"
    if "type" in candidate_keys:
        common_vals = global_schema.get("type", {}).get("common_values", [])
        fm["type"] = "concept" if "concept" in common_vals else (common_vals[0] if common_vals else "note")

    dv_fields = profile.get("plugins", {}).get("conventions", {}).get("dataview_queried_fields", [])
    for df in list(dv_fields) + list(extra_query_fields or []):
        if (df in folder_props or df in (extra_query_fields or [])) and df not in fm and df not in ("file",):
            ptype = folder_props.get(df, "string")
            fm[df] = today if ptype == "date" else ([] if ptype == "list" else "")

    return fm


def _compute_plan_hash(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return sha256_text(canonical)


def save_plan_snapshot(
    state_dir: Path,
    plan: dict[str, Any],
) -> Path:
    """Persist a reviewed plan snapshot inside <state_dir>/plans/."""
    plans_dir = state_dir / "plans"
    plans_dir.mkdir(parents=True, exist_ok=True)
    plan_file = plans_dir / f"{plan['plan_id']}.json"
    atomic_write_text(plan_file, json.dumps(plan, indent=2, ensure_ascii=False) + "\n")
    return plan_file


def load_reviewed_plan(
    vault_root: Path,
    plan_ref: str | Path | dict[str, Any],
    state_dir: Path | None = None,
) -> dict[str, Any]:
    """Load a previously previewed/saved plan by dict, plan_id, or file path."""
    if isinstance(plan_ref, dict):
        return plan_ref

    root = vault_root.resolve()
    sdir = state_dir or resolve_state_dir(root)
    raw = str(plan_ref).strip()
    cand = Path(raw)
    if not cand.is_file():
        cand = sdir / "plans" / (raw if raw.endswith(".json") else f"{raw}.json")
    if not cand.is_file():
        raise FileNotFoundError(f"Reviewed plan not found: {plan_ref}")
    if not is_within_root(cand, sdir) and not is_within_root(cand, root):
        # Allow explicit plan files outside vault only if directly specified as an existing file path
        if not Path(raw).is_file():
            raise ValueError(f"Refusing unsafe plan path: {cand}")

    data = json.loads(read_text_safe(cand))
    if not isinstance(data, dict) or "affected_files" not in data:
        raise ValueError(f"Invalid plan file format: {cand}")
    return data


def plan_note(
    vault_root: Path,
    topic: str,
    explicit_folder: str | None = None,
    explicit_template: str | None = None,
    keywords: list[str] | None = None,
    refresh: bool = False,
    state_dir: Path | None = None,
    content: dict[str, Any] | None = None,
    proposal: dict[str, Any] | None = None,
    extend_rel_path: str | None = None,
    mermaid_mode: str = "auto",
    mindmap_supported: bool = True,
    min_moc_cluster_size: int | None = None,
    allow_moc: bool = True,
    save_plan: bool = False,
) -> dict[str, Any]:
    """Create a complete, evidence-backed note placement, tagging, MOC, Mermaid, and edit plan."""
    root = vault_root.resolve()
    sdir = state_dir or resolve_state_dir(root)
    profile = load_or_discover_profile(root, refresh=refresh, state_dir=sdir)
    index = load_or_build_index(root, refresh=refresh, state_dir=sdir)

    c = content or {}
    prop = proposal or {}

    extra_terms = list(keywords or [])
    for ck in c.get("concepts", []):
        if isinstance(ck, str) and ck.strip():
            extra_terms.append(ck.strip())
    search_query = " ".join([topic] + extra_terms)
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
        if extra_terms
        else search_res
    )
    matches = search_res["results"]

    moc_paths = {m["path"] for m in profile.get("mocs", [])}
    content_matches = [m for m in matches if m["rel_path"] not in moc_paths]
    exact_matches = [m for m in content_matches if m.get("exact_title_match")]
    strong_overlaps = [m for m in content_matches if m["score"] >= 22.0]
    existing_target = exact_matches[0] if exact_matches else (strong_overlaps[0] if strong_overlaps else None)

    dest = resolve_destination(
        topic=topic,
        profile=profile,
        search_results=placement_search if placement_search.get("results") else search_res,
        explicit_folder=explicit_folder,
        keywords=keywords,
    )
    target_folder = dest["recommended_folder"]
    if extend_rel_path:
        ext_parent = Path(extend_rel_path.strip().lstrip("/")).parent.as_posix()
        target_folder = "" if ext_parent == "." else ext_parent

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

    if extend_rel_path:
        recommended_action = "extend_existing"
    elif existing_target is not None:
        recommended_action = "extend_existing"
    elif granularity == "atomic" or org_primary == "zettelkasten":
        recommended_action = "split_atomic"
    else:
        recommended_action = "create_new"

    existing_stems = {
        d["stem"] for d in index.get("docs", {}).values()
        if d.get("folder", "") == target_folder
    }
    filename = (
        Path(extend_rel_path).name
        if extend_rel_path
        else format_note_filename(topic, dest["naming_convention"], existing_stems=existing_stems)
    )
    proposed_rel_path = (
        extend_rel_path.strip().lstrip("/")
        if extend_rel_path
        else (f"{target_folder}/{filename}" if target_folder else filename)
    )

    # Link decisions: verify every target against index and detect ambiguous stems
    link_style = folder_style.get("link_style", "wikilink")
    ambiguous_titles = index.get("ambiguous_titles", {})
    verified_links: list[dict[str, Any]] = []
    rejected_links: list[dict[str, Any]] = []
    ambiguous_warnings: list[str] = []

    target_rel_for_self = extend_rel_path.strip().lstrip("/") if extend_rel_path else (
        existing_target["rel_path"] if existing_target else proposed_rel_path
    )
    for m in content_matches[:6]:
        if m["rel_path"] == target_rel_for_self:
            continue
        wlink = resolve_safe_wikilink(m["rel_path"], index, preferred_style=link_style)
        if wlink:
            is_ambig = m.get("stem", "").lower() in ambiguous_titles
            if is_ambig:
                ambiguous_warnings.append(
                    f"Disambiguated duplicate basename '{m['stem']}' using folder-qualified link {wlink}"
                )
            verified_links.append(
                {
                    "rel_path": m["rel_path"],
                    "title": m["title"],
                    "stem": m["stem"],
                    "wikilink": wlink,
                    "score": m["score"],
                    "reasons": m["reasons"],
                    "headings": m["headings"][:5],
                    "summary": m.get("summary", ""),
                    "disambiguated": is_ambig,
                }
            )

    for prop_rel in prop.get("related_notes", []):
        wlink = resolve_safe_wikilink(str(prop_rel), index, preferred_style=link_style)
        if not wlink:
            rejected_links.append({"target": str(prop_rel), "reason": "Proposed link target does not exist in vault"})

    # Check if any query-driven MOC in target folder imposes metadata/tag filters
    moc_query_tags: list[str] = []
    moc_query_fields: list[str] = []
    for m_entry in profile.get("mocs", []):
        if m_entry.get("moc_kind") in ("query_driven", "hybrid"):
            qreq = m_entry.get("query_requirements") or {}
            q_folders = qreq.get("folders", [])
            if (target_folder and any(target_folder == qf or target_folder.startswith(qf + "/") for qf in q_folders)) or (
                not q_folders and m_entry.get("folder") == target_folder
            ):
                moc_query_tags.extend(qreq.get("tags", []))
                moc_query_fields.extend(qreq.get("fields", []))

    tpl_tags = (template_res.get("template_info") or {}).get("tags", [])
    tag_decisions = select_and_plan_tags(
        topic=topic,
        profile=profile,
        target_folder=target_folder,
        related_results=content_matches,
        keywords=keywords,
        content=c,
        proposed_tags=prop.get("proposed_tags") or c.get("proposed_tags"),
        template_tags=tpl_tags,
        moc_query_tags=moc_query_tags,
    )
    tags = tag_decisions["selected_tags"]

    frontmatter = _recommend_frontmatter(
        topic=topic,
        profile=profile,
        target_folder=target_folder,
        tags=tags,
        template_res=template_res,
        extra_query_fields=moc_query_fields,
    )

    diagram_decisions = plan_mermaid_diagram(
        topic=topic,
        profile=profile,
        target_folder=target_folder,
        related_notes=verified_links,
        content=c,
        proposal=prop,
        mermaid_mode=mermaid_mode,
        mindmap_supported=mindmap_supported,
        note_role="note",
    )

    short_desc = str(c.get("summary") or c.get("intuition") or "").strip()
    if len(short_desc) > 90:
        short_desc = short_desc[:87].rstrip() + "..."

    moc_decisions = plan_moc_integration(
        vault_root=root,
        topic=topic,
        target_rel_path=proposed_rel_path,
        target_folder=target_folder,
        selected_tags=tags,
        related_results=content_matches,
        profile=profile,
        index=index,
        link_style=link_style,
        keywords=keywords,
        short_desc=short_desc,
        min_cluster_size=min_moc_cluster_size,
        allow_moc=allow_moc,
    )

    # Assemble base plan before rendering target note so renderer sees tags, diagram, and MOC hub
    warnings: list[str] = []
    warnings.extend(ambiguous_warnings)
    warnings.extend(tag_decisions.get("warnings", []))
    warnings.extend(moc_decisions.get("warnings", []))
    if diagram_decisions.get("validation") and diagram_decisions["validation"].get("limitation"):
        warnings.append(diagram_decisions["validation"]["limitation"])

    evidence: list[str] = list(dest.get("evidence", []))
    if template_res.get("reason"):
        evidence.append(f"Template: {template_res['reason']}")
    if moc_decisions.get("reason"):
        evidence.append(f"MOC: {moc_decisions['reason']}")

    plan: dict[str, Any] = {
        "plan_version": 2,
        "created_at": utc_now_iso(),
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
        "tag_decisions": tag_decisions,
        "relevant_notes": verified_links,
        "link_decisions": {
            "verified_links": verified_links,
            "rejected_or_unresolved": rejected_links,
            "ambiguous_warnings": ambiguous_warnings,
        },
        "moc_decisions": {k: v for k, v in moc_decisions.items() if k != "file_edit"},
        "diagram_decisions": diagram_decisions,
        "style_guidance": {
            "granularity": granularity,
            "style_preference": folder_style.get("style_preference", "mixed"),
            "uses_h1": folder_style.get("uses_h1", True),
            "numbered_headings": folder_style.get("numbered_headings", False),
            "common_callouts": folder_style.get("common_callouts", ["note"]),
            "uses_math": folder_style.get("uses_math", True),
            "uses_tables": folder_style.get("uses_tables", True),
            "uses_mermaid": folder_style.get("uses_mermaid", False) or bool(diagram_decisions.get("include_diagram")),
            "flashcard_syntax": folder_style.get("flashcard_syntax", "inline_double_colon"),
            "link_style": link_style,
            "common_summary_headings": folder_style.get("common_summary_headings", []),
        },
        "plugin_conventions": profile.get("plugins", {}).get("conventions", {}),
        "safety": {
            "teachme_state_dir": str(sdir),
            "will_modify_existing_user_notes": bool(
                extend_rel_path or moc_decisions.get("action") == "update_existing"
            ),
        },
        "evidence": evidence,
        "warnings": warnings,
    }

    target_edit = render_target_note_file(
        vault_root=root,
        topic=topic,
        plan=plan,
        extend_rel_path=extend_rel_path,
        content=c,
    )
    warnings.extend(target_edit.get("warnings", []))

    affected_files: list[dict[str, Any]] = [
        {
            "rel_path": target_edit["rel_path"],
            "role": target_edit["role"],
            "action": target_edit["action"],
            "conflict": target_edit["conflict"],
            "conflict_reason": target_edit.get("reason", ""),
            "expected_sha256": target_edit["expected_sha256"],
            "must_not_exist": target_edit["must_not_exist"],
            "preserved_dynamic_expressions": target_edit["preserved_dynamic_expressions"],
            "confidence": dest["confidence"],
            "needs_confirmation": dest["needs_confirmation"],
            "no_changes": target_edit["no_changes"],
            "diff": target_edit["diff"],
            "new_text": target_edit["new_text"],
        }
    ]
    moc_edit = moc_decisions.get("file_edit")
    if moc_edit and not target_edit["conflict"]:
        affected_files.append(moc_edit)

    expected_hashes = {
        af["rel_path"]: af["expected_sha256"]
        for af in affected_files
    }
    confs = [dest["confidence"], moc_decisions.get("confidence", "high")]
    overall_conf = "low" if "low" in confs else ("medium" if "medium" in confs else "high")

    plan_hash = _compute_plan_hash(
        {
            "vault_path": str(root),
            "topic": topic,
            "affected_files": [
                {
                    "rel_path": af["rel_path"],
                    "action": af["action"],
                    "expected_sha256": af["expected_sha256"],
                    "new_text": af["new_text"],
                }
                for af in affected_files
            ],
        }
    )
    stamp = utc_now_iso().replace(":", "").replace("-", "")
    plan["plan_id"] = f"plan-{stamp}-{plan_hash[:8]}"
    plan["plan_hash"] = plan_hash
    plan["confidence"] = overall_conf
    plan["expected_hashes"] = expected_hashes
    plan["affected_files"] = affected_files

    if save_plan:
        plan_path = save_plan_snapshot(sdir, plan)
        plan["plan_file"] = str(plan_path)

    return plan
