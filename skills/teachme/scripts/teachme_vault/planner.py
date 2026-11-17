"""Context-aware knowledge integration and note generation planning."""

from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Any

from .discovery import load_or_discover_profile
from .indexer import (
    load_or_build_index,
    resolve_link_to_rel_path,
    resolve_safe_wikilink,
    search_vault,
)
from .mermaid import plan_mermaid_diagram
from .moc import apply_selected_moc_query_requirements, plan_moc_integration
from .models import (
    atomic_write_text,
    is_within_root,
    read_text_safe,
    resolve_state_dir,
    safe_iter_files,
    sha256_text,
    today_iso,
    utc_now_iso,
)
from .placement import format_note_filename, resolve_destination
from .renderer import render_target_note_file
from .tagging import select_and_plan_tags
from .templates import resolve_template

HEX64_RE = re.compile(r"^[0-9a-f]{64}$")
REQUIRED_AF_FIELDS = ("rel_path", "role", "action", "must_not_exist", "expected_sha256", "new_text")


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
        common_vals = [
            v for v in global_schema.get("status", {}).get("common_values", [])
            if str(v).lower() not in ("archived", "archive", "mastered", "reviewed")
        ]
        fm["status"] = common_vals[0] if common_vals else "seedling"
    if "type" in candidate_keys:
        common_vals = global_schema.get("type", {}).get("common_values", [])
        fm["type"] = "concept" if "concept" in common_vals else (common_vals[0] if common_vals else "note")

    dv_fields = profile.get("plugins", {}).get("conventions", {}).get("dataview_queried_fields", [])
    for df in dv_fields:
        if df in folder_props and df not in fm and df not in ("file",):
            ptype = folder_props.get(df, "string")
            if ptype == "date":
                fm[df] = today
            elif ptype == "list":
                fm[df] = []
            # Omit unknown string scalar fields rather than emitting empty string ""

    return fm


def compute_canonical_plan_hash(plan: dict[str, Any]) -> str:
    """Compute a deterministic unkeyed SHA-256 integrity digest over all execution-relevant fields."""
    canonical_payload = {
        "plan_version": int(plan.get("plan_version", 2)),
        "vault_path": str(Path(str(plan.get("vault_path", ""))).resolve()),
        "topic": str(plan.get("topic", "")),
        "recommended_action": str(plan.get("recommended_action", "")),
        "unresolved": bool(plan.get("unresolved", False)),
        "affected_files": [
            {
                "rel_path": str(af.get("rel_path", "")),
                "role": str(af.get("role", "")),
                "action": str(af.get("action", "")),
                "must_not_exist": bool(af.get("must_not_exist", False)),
                "expected_sha256": af.get("expected_sha256"),
                "conflict": bool(af.get("conflict", False)),
                "no_changes": bool(af.get("no_changes", False)),
                "inserted_line": str(af.get("inserted_line", "")),
                "new_text": str(af.get("new_text", "")),
            }
            for af in plan.get("affected_files", [])
        ],
    }
    encoded = json.dumps(canonical_payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return sha256_text(encoded)


def validate_reviewed_plan(
    plan: dict[str, Any],
    expected_vault_root: Path,
    expected_plan_hash: str | None = None,
) -> None:
    """Validate reviewed plan schema, recompute canonical integrity hash, and reject tampered/unresolved plans."""
    if not isinstance(plan, dict):
        raise ValueError("Reviewed plan must be a JSON object")

    for req in ("plan_version", "vault_path", "topic", "recommended_action", "plan_hash", "affected_files"):
        if req not in plan:
            raise ValueError(f"Reviewed plan missing required field: {req}")

    if int(plan["plan_version"]) != 2:
        raise ValueError(f"Unsupported plan_version: {plan['plan_version']}")

    root = expected_vault_root.resolve()
    if Path(str(plan["vault_path"])).resolve() != root:
        raise ValueError("Reviewed plan belongs to a different vault path")

    stored_hash = str(plan.get("plan_hash", "")).strip().lower()
    if not HEX64_RE.fullmatch(stored_hash):
        raise ValueError("Reviewed plan has malformed plan_hash")

    affected = plan.get("affected_files")
    if not isinstance(affected, list) or not affected:
        raise ValueError("Reviewed plan has empty or invalid affected_files")

    for idx, af in enumerate(affected):
        if not isinstance(af, dict):
            raise ValueError(f"affected_files[{idx}] must be an object")
        for fkey in REQUIRED_AF_FIELDS:
            if fkey not in af:
                raise ValueError(f"affected_files[{idx}] missing required field: {fkey}")

    recomputed = compute_canonical_plan_hash(plan)
    if recomputed != stored_hash:
        raise RuntimeError(
            f"Reviewed plan integrity check failed: content hash {recomputed[:12]} does not match stored plan_hash {stored_hash[:12]}"
        )

    if expected_plan_hash and expected_plan_hash.strip().lower() != recomputed:
        raise RuntimeError(
            f"Reviewed plan hash mismatch: expected {expected_plan_hash[:12]}, got {recomputed[:12]}"
        )

    if plan.get("unresolved"):
        opts = "; ".join(plan.get("resolution_options", [])) or "Specify --extend or rename target."
        raise RuntimeError(f"Reviewed plan is unresolved and requires a decision before apply: {opts}")


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
        if not Path(raw).is_file():
            raise ValueError(f"Refusing unsafe plan path: {cand}")

    data = json.loads(read_text_safe(cand))
    if not isinstance(data, dict) or "affected_files" not in data:
        raise ValueError(f"Invalid plan file format: {cand}")
    return data


def _merge_proposed_related_notes(
    verified_links: list[dict[str, Any]],
    rejected_links: list[dict[str, Any]],
    ambiguous_warnings: list[str],
    proposed_items: list[Any],
    index: dict[str, Any],
    link_style: str,
    target_rel_for_self: str,
    moc_paths: set[str],
) -> None:
    """Resolve valid proposal.related_notes, deduplicate canonically, and feed into verified_links."""
    docs = index.get("docs", {})
    ambiguous_titles = index.get("ambiguous_titles", {})
    seen_rels = {v["rel_path"].lower() for v in verified_links}

    for item in proposed_items:
        if isinstance(item, dict):
            raw_target = str(item.get("target") or item.get("rel_path") or item.get("note") or "").strip()
            reason = str(item.get("reason", "")).strip() or "Proposed related note"
            anchor = str(item.get("anchor", "")).strip()
        else:
            raw_target = str(item).strip()
            reason = "Proposed related note"
            anchor = ""
        if not raw_target:
            continue

        res = resolve_link_to_rel_path(raw_target, index)
        resolved_rel = res.get("resolved")
        parsed_anchor = anchor or res.get("anchor", "")
        if not resolved_rel:
            if res.get("ambiguous"):
                cands = res.get("candidates", [])
                rejected_links.append(
                    {
                        "target": raw_target,
                        "reason": f"Ambiguous proposed link target (candidates: {', '.join(cands[:4])})",
                    }
                )
                ambiguous_warnings.append(f"Proposed related note '{raw_target}' is ambiguous: {', '.join(cands[:3])}")
            else:
                rejected_links.append({"target": raw_target, "reason": "Proposed link target does not exist in vault"})
            continue

        if resolved_rel.lower() == target_rel_for_self.lower():
            continue
        if resolved_rel in moc_paths:
            continue
        if resolved_rel.lower() in seen_rels:
            # Enrich reason if already discovered by search
            for v in verified_links:
                if v["rel_path"].lower() == resolved_rel.lower() and reason not in v["reasons"]:
                    v["reasons"].append(reason)
            continue

        wlink = resolve_safe_wikilink(resolved_rel, index, preferred_style=link_style, anchor=parsed_anchor)
        if not wlink:
            rejected_links.append({"target": raw_target, "reason": "Proposed link target could not be resolved safely"})
            continue

        doc = docs.get(resolved_rel, {})
        stem = doc.get("stem", Path(resolved_rel).stem)
        is_ambig = stem.lower() in ambiguous_titles
        if is_ambig:
            ambiguous_warnings.append(f"Disambiguated duplicate basename '{stem}' using folder-qualified link {wlink}")

        seen_rels.add(resolved_rel.lower())
        verified_links.append(
            {
                "rel_path": resolved_rel,
                "title": doc.get("title", stem),
                "stem": stem,
                "wikilink": wlink,
                "score": 15.0,
                "reasons": [reason],
                "headings": doc.get("headings", [])[:5],
                "summary": doc.get("summary", ""),
                "disambiguated": is_ambig,
                "proposed": True,
            }
        )


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
    profile: dict[str, Any] | None = None,
    index: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Create a complete, evidence-backed note placement, tagging, MOC, Mermaid, and edit plan."""
    root = vault_root.resolve()
    sdir = state_dir or resolve_state_dir(root)

    if profile is None or index is None:
        note_files = [
            p for p in safe_iter_files(root, extensions=(".md",))
            if not p.name.lower().endswith(".excalidraw.md")
        ]
        if profile is None:
            profile = load_or_discover_profile(root, refresh=refresh, state_dir=sdir, note_files=note_files)
        if index is None:
            index = load_or_build_index(root, refresh=refresh, state_dir=sdir, note_files=note_files)

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
    similar_matches = [m for m in content_matches if not m.get("exact_title_match") and m["score"] >= 22.0]
    existing_target = exact_matches[0] if exact_matches else None

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

    existing_stems = {
        d["stem"] for d in index.get("docs", {}).values()
        if d.get("folder", "") == target_folder
    }

    # Action consistency:
    # - Explicit extend_rel_path -> executable extend_existing
    # - Exact match without extend_rel_path -> unresolved extend_existing requiring explicit decision
    # - Similar (non-exact) match -> create_new/split_atomic with advisory warning (never silently extend!)
    unresolved = False
    resolution_options: list[str] = []
    if extend_rel_path:
        recommended_action = "extend_existing"
        proposed_rel_path = extend_rel_path.strip().lstrip("/")
        filename = Path(proposed_rel_path).name
    elif existing_target is not None:
        recommended_action = "extend_existing"
        proposed_rel_path = existing_target["rel_path"]
        filename = Path(proposed_rel_path).name
        unresolved = True
        resolution_options = [
            f"Pass --extend '{proposed_rel_path}' to extend the existing note non-destructively",
            "Specify a different --topic or --folder to create a separate note",
        ]
    elif granularity == "atomic" or org_primary == "zettelkasten":
        recommended_action = "split_atomic"
        filename = format_note_filename(topic, dest["naming_convention"], existing_stems=existing_stems)
        proposed_rel_path = f"{target_folder}/{filename}" if target_folder else filename
    else:
        recommended_action = "create_new"
        filename = format_note_filename(topic, dest["naming_convention"], existing_stems=existing_stems)
        proposed_rel_path = f"{target_folder}/{filename}" if target_folder else filename

    # Link decisions: verify search matches + merge valid proposed related_notes
    link_style = folder_style.get("link_style", "wikilink")
    ambiguous_titles = index.get("ambiguous_titles", {})
    verified_links: list[dict[str, Any]] = []
    rejected_links: list[dict[str, Any]] = []
    ambiguous_warnings: list[str] = []

    target_rel_for_self = proposed_rel_path
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
                    "reasons": list(m["reasons"]),
                    "headings": m["headings"][:5],
                    "summary": m.get("summary", ""),
                    "disambiguated": is_ambig,
                }
            )

    raw_proposed_links = list(prop.get("related_notes", [])) + list(c.get("related_notes", []))
    _merge_proposed_related_notes(
        verified_links=verified_links,
        rejected_links=rejected_links,
        ambiguous_warnings=ambiguous_warnings,
        proposed_items=raw_proposed_links,
        index=index,
        link_style=link_style,
        target_rel_for_self=target_rel_for_self,
        moc_paths=moc_paths,
    )

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
    )
    tags = tag_decisions["selected_tags"]

    frontmatter = _recommend_frontmatter(
        topic=topic,
        profile=profile,
        target_folder=target_folder,
        tags=tags,
        template_res=template_res,
    )

    short_desc = str(c.get("summary") or c.get("intuition") or "").strip()
    if len(short_desc) > 90:
        short_desc = short_desc[:87].rstrip() + "..."

    # Select relevant MOC FIRST, then apply ONLY that selected MOC's query requirements
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

    q_apply = apply_selected_moc_query_requirements(
        moc_decisions=moc_decisions,
        topic=topic,
        keywords=keywords,
        frontmatter=frontmatter,
        selected_tags=tags,
        profile=profile,
        target_folder=target_folder,
    )
    frontmatter = q_apply["frontmatter"]
    tags = q_apply["tags"]
    if tags != tag_decisions["selected_tags"]:
        added_q = [t for t in tags if t not in tag_decisions["selected_tags"]]
        tag_decisions["selected_tags"] = tags
        for qt in added_q:
            tag_decisions["decisions"].append(
                {
                    "tag": qt,
                    "decision": "reuse",
                    "category": "subject",
                    "reason": f"Required by selected query-driven MOC '{moc_decisions.get('selected_moc')}'",
                    "evidence": [f"selected_moc={moc_decisions.get('selected_moc')}"],
                    "confidence": "high",
                }
            )
    if moc_decisions.get("action") == "satisfy_query":
        moc_decisions["query_satisfaction"] = q_apply["query_satisfaction"]

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

    warnings: list[str] = []
    warnings.extend(ambiguous_warnings)
    warnings.extend(tag_decisions.get("warnings", []))
    warnings.extend(moc_decisions.get("warnings", []))
    warnings.extend(q_apply.get("warnings", []))
    if similar_matches and not extend_rel_path and existing_target is None:
        warnings.append(
            f"Similar existing note found ({similar_matches[0]['rel_path']}); creating separate note as requested."
        )
    if unresolved:
        warnings.append(
            f"Exact existing note '{proposed_rel_path}' matches '{topic}'; pass --extend to update it or rename."
        )
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
        "unresolved": unresolved,
        "resolution_options": resolution_options,
        "existing_note": existing_target,
        "similar_notes": similar_matches[:3],
        "destination": {
            "folder": target_folder,
            "filename": filename,
            "proposed_rel_path": proposed_rel_path,
            "confidence": dest["confidence"],
            "needs_confirmation": dest["needs_confirmation"] or unresolved,
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

    if unresolved:
        # Non-executable conflict representation consistent with recommended_action="extend_existing"
        existing_sha = sha256_text(read_text_safe(root / proposed_rel_path)) if (root / proposed_rel_path).is_file() else None
        affected_files: list[dict[str, Any]] = [
            {
                "rel_path": proposed_rel_path,
                "role": "target_note",
                "action": "extend",
                "conflict": True,
                "conflict_reason": (
                    f"Target note '{proposed_rel_path}' already exists. "
                    "Pass --extend to extend it non-destructively or choose another topic/folder."
                ),
                "expected_sha256": existing_sha,
                "must_not_exist": False,
                "preserved_dynamic_expressions": [],
                "confidence": dest["confidence"],
                "needs_confirmation": True,
                "no_changes": True,
                "inserted_line": "",
                "diff": "",
                "new_text": "",
            }
        ]
    else:
        target_edit = render_target_note_file(
            vault_root=root,
            topic=topic,
            plan=plan,
            extend_rel_path=extend_rel_path,
            content=c,
        )
        warnings.extend(target_edit.get("warnings", []))

        affected_files = [
            {
                "rel_path": target_edit["rel_path"],
                "role": target_edit["role"],
                "action": target_edit["action"],
                "granularity": granularity if recommended_action == "split_atomic" else None,
                "conflict": target_edit["conflict"],
                "conflict_reason": target_edit.get("reason", ""),
                "expected_sha256": target_edit["expected_sha256"],
                "must_not_exist": target_edit["must_not_exist"],
                "preserved_dynamic_expressions": target_edit["preserved_dynamic_expressions"],
                "confidence": dest["confidence"],
                "needs_confirmation": dest["needs_confirmation"],
                "no_changes": target_edit["no_changes"],
                "inserted_line": "",
                "diff": target_edit["diff"],
                "new_text": target_edit["new_text"],
            }
        ]
        moc_edit = moc_decisions.get("file_edit")
        if moc_edit and not target_edit["conflict"]:
            moc_edit.setdefault("inserted_line", "")
            affected_files.append(moc_edit)

    expected_hashes = {
        af["rel_path"]: af["expected_sha256"]
        for af in affected_files
    }
    confs = [dest["confidence"], moc_decisions.get("confidence", "high")]
    overall_conf = "low" if "low" in confs else ("medium" if "medium" in confs else "high")

    plan["affected_files"] = affected_files
    plan["expected_hashes"] = expected_hashes
    plan["confidence"] = overall_conf

    plan_hash = compute_canonical_plan_hash(plan)
    stamp = utc_now_iso().replace(":", "").replace("-", "")
    plan["plan_id"] = f"plan-{stamp}-{plan_hash[:8]}"
    plan["plan_hash"] = plan_hash

    if save_plan:
        plan_path = save_plan_snapshot(sdir, plan)
        plan["plan_file"] = str(plan_path)

    return plan
