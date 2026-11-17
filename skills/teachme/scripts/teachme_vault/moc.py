"""Automatic MOC selection, query satisfaction, justified creation, and minimal updates."""

from __future__ import annotations

import difflib
from pathlib import Path
import re
from typing import Any

from .indexer import links_equivalent, resolve_safe_wikilink, tokenize
from .markdown_utils import (
    HEADING_RE,
    MDLINK_RE,
    WIKILINK_RE,
    analyze_markdown_body,
    parse_frontmatter_tolerant,
    parse_wikilink_parts,
)
from .mermaid import plan_mermaid_diagram
from .models import load_config, read_text_safe, sha256_text, today_iso

DEFAULT_MIN_CLUSTER_SIZE = 3
SKIP_MOC_SECTIONS = frozenset({"archive", "archived", "references", "sources", "templates", "changelog"})


def _extract_all_live_links(text: str) -> list[str]:
    """Extract all wikilink and relative Markdown link targets from live MOC text."""
    fm = parse_frontmatter_tolerant(text)
    info = analyze_markdown_body(fm["body"])
    links: list[str] = []
    for wl in info["wikilinks"]:
        if wl["note"] and not wl["embed"]:
            links.append(wl["note"])
    for ml in info["md_links"]:
        href = ml["href"]
        if href and not href.startswith(("http://", "https://", "mailto:")):
            links.append(href.split("#", 1)[0])
    return links


def _moc_matches_query_scope(
    moc: dict[str, Any],
    target_folder: str,
    selected_tags: list[str],
    topic_tokens: set[str] | None = None,
) -> tuple[bool, dict[str, Any]]:
    """Check if a query-driven MOC's Dataview query covers this note without cross-contaminating."""
    qreq = moc.get("query_requirements") or {}
    q_folders: list[str] = qreq.get("folders", [])
    q_tags: list[str] = qreq.get("tags", [])
    q_fields: list[str] = qreq.get("fields", [])
    q_preds: list[dict[str, str]] = qreq.get("predicates", [])
    complex_where = bool(qreq.get("complex_where", False))

    folder_match = False
    if q_folders and target_folder:
        folder_match = any(
            target_folder == qf or target_folder.startswith(qf + "/")
            for qf in q_folders
        )
    elif not q_folders and moc.get("folder") and target_folder:
        folder_match = target_folder == moc["folder"] or target_folder.startswith(moc["folder"] + "/")

    sel_low = {t.lower() for t in selected_tags}
    tag_match = bool(q_tags and any(qt.lower() in sel_low for qt in q_tags))

    # If the query explicitly filters by tags, require either tag overlap or semantic topic alignment
    t_tokens = topic_tokens or set()
    q_tag_tokens = set()
    for qt in q_tags:
        q_tag_tokens.update(tokenize(qt.replace("/", " ")))
    pred_val_tokens = set()
    for pr in q_preds:
        if pr.get("kind") == "equality" and pr.get("value"):
            pred_val_tokens.update(tokenize(pr["value"]))

    topic_aligns_with_query = bool(t_tokens & (q_tag_tokens | pred_val_tokens))

    matches = False
    if tag_match:
        matches = True
    elif folder_match and (not q_tags or topic_aligns_with_query):
        matches = True

    if matches:
        return True, {
            "folders": q_folders,
            "tags": q_tags,
            "fields": q_fields,
            "predicates": q_preds,
            "where_clauses": qreq.get("where_clauses", []),
            "complex_where": complex_where,
        }
    return False, {}


def _score_existing_mocs(
    topic: str,
    target_folder: str,
    selected_tags: list[str],
    related_results: list[dict[str, Any]],
    profile: dict[str, Any],
    index: dict[str, Any],
    keywords: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Rank all vault MOCs (including outside target folder) by contextual fit."""
    mocs = profile.get("mocs", [])
    if not mocs:
        return []

    topic_tokens = set(tokenize(topic))
    if keywords:
        for kw in keywords:
            topic_tokens.update(tokenize(kw))
    folder_tokens = set(tokenize(target_folder.replace("/", " "))) if target_folder else set()
    sel_tag_set = {t.lower() for t in selected_tags}
    related_paths = {r["rel_path"] for r in related_results[:8]}

    scored: list[dict[str, Any]] = []
    for moc in mocs:
        m_path = moc["path"]
        m_folder = moc.get("folder", "")
        score = 0.0
        evidence: list[str] = []

        # 1. Folder proximity
        if target_folder and m_folder == target_folder:
            score += 8.0
            evidence.append(f"Located in target folder '{target_folder}'")
        elif target_folder and m_folder and target_folder.startswith(m_folder + "/"):
            depth_diff = target_folder.count("/") - m_folder.count("/")
            score += max(3.0, 6.5 - depth_diff * 1.5)
            evidence.append(f"Ancestor hub covering '{m_folder}'")
        elif m_folder and target_folder and m_folder.split("/")[0] == target_folder.split("/")[0]:
            score += 2.0
            evidence.append(f"Same top-level hierarchy '{m_folder.split('/')[0]}'")

        # 2. Neighbor links already present in MOC
        linked_neighbors = 0
        for out_t in moc.get("outgoing_targets", []):
            for rel_p in related_paths:
                if links_equivalent(out_t, rel_p, index):
                    linked_neighbors += 1
                    break
        if linked_neighbors > 0:
            score += min(12.0, linked_neighbors * 4.0)
            evidence.append(f"Already links {linked_neighbors} related neighbor note(s)")

        # 3. Tag overlap
        moc_tags = {t.lower() for t in moc.get("tags", []) if t.lower() not in ("moc", "index", "map-of-content")}
        tag_overlap = sel_tag_set & moc_tags
        if tag_overlap:
            score += 3.5 * min(3, len(tag_overlap))
            evidence.append(f"Shares subject tags: {', '.join(sorted(tag_overlap)[:3])}")

        # 4. Title & section heading overlap (prioritize direct topic alignment over folder-name coincidence)
        moc_title_tokens = set(tokenize(f"{moc.get('title', '')} {moc.get('stem', '')}"))
        topic_title_ov = topic_tokens & moc_title_tokens
        folder_title_ov = folder_tokens & moc_title_tokens
        if topic_title_ov:
            score += 4.5 * min(3, len(topic_title_ov))
            evidence.append(f"Title aligns with topic: {', '.join(sorted(topic_title_ov)[:3])}")
        elif folder_title_ov:
            score += 2.0 * min(2, len(folder_title_ov))
            evidence.append(f"Title aligns with folder: {', '.join(sorted(folder_title_ov)[:2])}")

        sec_tokens: set[str] = set()
        for sec in moc.get("sections", []):
            sec_tokens.update(tokenize(sec.get("heading", "")))
        sec_ov = topic_tokens & sec_tokens
        if sec_ov:
            score += 2.5 * min(2, len(sec_ov))
            evidence.append(f"Section heading matches: {', '.join(sorted(sec_ov)[:2])}")

        # 5. Query-driven scope match (requires tag/topic compatibility when query filters tags)
        q_match, q_req = _moc_matches_query_scope(moc, target_folder, selected_tags, topic_tokens=topic_tokens)
        if q_match and moc.get("moc_kind") in ("query_driven", "hybrid"):
            q_tag_bonus = 3.0 if any(qt.lower() in sel_tag_set for qt in q_req.get("tags", [])) else 0.0
            score += 6.0 + q_tag_bonus
            evidence.append("Query-driven filter covers note scope")

        if score > 0:
            scored.append(
                {
                    "moc": moc,
                    "path": m_path,
                    "title": moc.get("title", moc.get("stem", "")),
                    "moc_kind": moc.get("moc_kind", "manual"),
                    "score": round(score, 2),
                    "evidence": evidence,
                    "query_match": q_match,
                    "query_requirements": q_req,
                }
            )

    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored


def apply_selected_moc_query_requirements(
    moc_decisions: dict[str, Any],
    topic: str,
    keywords: list[str] | None,
    frontmatter: dict[str, Any],
    selected_tags: list[str],
    profile: dict[str, Any],
    target_folder: str,
) -> dict[str, Any]:
    """Apply ONLY the selected relevant query-driven MOC's justified tags and predicates."""
    if moc_decisions.get("action") != "satisfy_query":
        return {"frontmatter": frontmatter, "tags": selected_tags, "warnings": [], "query_satisfaction": "not_applicable"}

    qreq = moc_decisions.get("query_requirements") or {}
    q_tags: list[str] = qreq.get("tags", [])
    q_fields: list[str] = qreq.get("fields", [])
    q_preds: list[dict[str, str]] = qreq.get("predicates", [])
    complex_where = bool(qreq.get("complex_where", False))

    updated_fm = dict(frontmatter)
    updated_tags = list(selected_tags)
    warnings: list[str] = []
    unverified: list[str] = []

    topic_tokens = set(tokenize(topic))
    if keywords:
        for kw in keywords:
            topic_tokens.update(tokenize(kw))

    # Add required FROM #tag only if semantically compatible or already matched to this selected MOC
    for qt in q_tags:
        clean_qt = qt.lstrip("#").strip()
        if clean_qt and clean_qt.lower() not in {t.lower() for t in updated_tags}:
            qt_tokens = set(tokenize(clean_qt.replace("/", " ")))
            if qt_tokens & topic_tokens or len(q_tags) == 1:
                updated_tags.append(clean_qt)
    if updated_tags and "tags" in updated_fm or updated_tags != selected_tags:
        updated_fm["tags"] = updated_tags

    global_schema = profile.get("metadata_schema", {})
    folder_props = profile.get("folders", {}).get(target_folder or ".", {}).get("properties", {})

    for pred in q_preds:
        fld = pred.get("field", "")
        kind = pred.get("kind", "")
        val = pred.get("value", "")
        if not fld or fld == "file":
            continue
        if kind == "negated_equality":
            cur = str(updated_fm.get(fld, "")).strip()
            if not cur or cur.lower() == val.lower():
                candidates = [
                    str(v) for v in global_schema.get(fld, {}).get("common_values", [])
                    if str(v).strip() and str(v).lower() != val.lower()
                ]
                if candidates:
                    updated_fm[fld] = candidates[0]
                elif fld == "status" and val.lower() != "seedling":
                    updated_fm[fld] = "seedling"
                else:
                    unverified.append(f"{fld} != {val}")
        elif kind == "equality":
            cur = str(updated_fm.get(fld, "")).strip()
            if cur.lower() == val.lower():
                continue
            val_tokens = set(tokenize(val))
            # Only auto-assign an equality predicate value when it matches topic/keywords or is a safe structural type
            if val_tokens & topic_tokens:
                updated_fm[fld] = val
            else:
                unverified.append(f"{fld} = {val}")

    # Do NOT invent empty strings for unpopulated queried fields used in predicates
    for df in q_fields:
        if df in ("file",) or df in updated_fm:
            continue
        if df in folder_props:
            ptype = folder_props[df]
            if ptype == "date":
                updated_fm[df] = today_iso()
            elif ptype == "list":
                updated_fm[df] = []
            # Leave string scalar fields absent rather than emitting empty string "" if value unknown

    if complex_where:
        warnings.append(
            f"Selected query-driven MOC '{moc_decisions.get('selected_moc')}' uses complex Dataview expressions; verify note matches query criteria."
        )
    if unverified:
        warnings.append(
            f"Could not safely auto-satisfy Dataview predicate(s) for '{moc_decisions.get('selected_moc')}': {', '.join(unverified)}"
        )

    satisfaction = "unverified_complex_or_predicate" if (complex_where or unverified) else "verified"
    return {
        "frontmatter": updated_fm,
        "tags": updated_tags,
        "warnings": warnings,
        "unverified_predicates": unverified,
        "query_satisfaction": satisfaction,
    }


def _select_moc_section(
    moc_text: str,
    topic: str,
    keywords: list[str] | None,
    related_results: list[dict[str, Any]],
    index: dict[str, Any],
) -> dict[str, Any]:
    """Choose the safest, most semantically fitting section inside an existing MOC."""
    lines = moc_text.splitlines()
    fm = parse_frontmatter_tolerant(moc_text)
    body_start = fm["body_start_line"]

    topic_tokens = set(tokenize(topic))
    if keywords:
        for kw in keywords:
            topic_tokens.update(tokenize(kw))
    related_paths = {r["rel_path"] for r in related_results[:6]}

    # Parse heading blocks in original file coordinates
    sections: list[dict[str, Any]] = []
    in_fence = False
    fence_char = ""
    current: dict[str, Any] = {
        "heading": "",
        "level": 0,
        "heading_line": body_start,
        "start_line": body_start,
        "end_line": len(lines),
        "link_lines": [],
        "bullet_prefix": "- ",
        "annotation_sep": "",
        "has_query": False,
        "links": [],
    }

    for idx in range(body_start, len(lines)):
        line = lines[idx]
        s = line.strip()
        if s.startswith("```") or s.startswith("~~~"):
            ch = s[0]
            if not in_fence:
                in_fence = True
                fence_char = ch
                if "dataview" in s.lower():
                    current["has_query"] = True
            elif ch == fence_char:
                in_fence = False
            continue
        if in_fence:
            continue

        hm = HEADING_RE.match(line)
        if hm:
            current["end_line"] = idx
            sections.append(current)
            level = len(hm.group(1))
            htext = hm.group(2).strip()
            current = {
                "heading": htext,
                "level": level,
                "heading_line": idx,
                "start_line": idx + 1,
                "end_line": len(lines),
                "link_lines": [],
                "bullet_prefix": "- ",
                "annotation_sep": "",
                "has_query": False,
                "links": [],
            }
            continue

        has_link = bool(WIKILINK_RE.search(line) or MDLINK_RE.search(line))
        if has_link:
            for wm in WIKILINK_RE.finditer(line):
                p = parse_wikilink_parts(wm.group(2), is_embed=bool(wm.group(1)))
                if p["note"] and p["embed"] and p["note"].lower().endswith(".base"):
                    current["has_query"] = True
                elif p["note"]:
                    current["links"].append(p["note"])
            bm = re.match(r"^(\s*(?:[-*+]|\d+\.)(?:\s+\[[ xX/\->!?]\])?\s+)", line)
            if bm:
                current["link_lines"].append(idx)
                current["bullet_prefix"] = bm.group(1)
                after = re.sub(r".*(?:\[\[[^\]]+\]\]|\[[^\]]*\]\([^)]+\))\s*", "", s)
                for sep in (" — ", " - ", ": "):
                    if after.startswith(sep.strip()):
                        current["annotation_sep"] = sep
                        break

    current["end_line"] = len(lines)
    sections.append(current)

    # Filter eligible sections (prefer H2/H3 or H1/root list, exclude query-only or archive)
    candidates: list[tuple[float, dict[str, Any], list[str]]] = []
    for sec in sections:
        h_low = sec["heading"].lower()
        if any(skip in h_low for skip in SKIP_MOC_SECTIONS):
            continue
        if sec["has_query"] and not sec["link_lines"]:
            continue
        # Skip empty H1 container if there are H2+ sections with links below it
        if sec["level"] == 1 and not sec["link_lines"] and any(s["level"] >= 2 and s["link_lines"] for s in sections):
            continue

        score = 0.0
        reasons: list[str] = []
        h_tokens = set(tokenize(sec["heading"]))
        ov = topic_tokens & h_tokens
        if ov:
            score += 5.0 * len(ov)
            reasons.append(f"Section heading matches '{', '.join(sorted(ov))}'")

        neighbor_hits = 0
        for ltarget in sec["links"]:
            for rp in related_paths:
                if links_equivalent(ltarget, rp, index):
                    neighbor_hits += 1
                    break
        if neighbor_hits:
            score += 4.0 * neighbor_hits
            reasons.append(f"Section already groups {neighbor_hits} related note(s)")

        if sec["link_lines"]:
            score += 1.5
            reasons.append("Existing curated link list")
        elif sec["level"] == 0 and len(sections) == 1:
            score += 1.0

        if sec["heading"] or sec["link_lines"] or len(sections) == 1:
            candidates.append((score, sec, reasons))

    if not candidates:
        return {
            "section": sections[-1],
            "confidence": "low",
            "needs_confirmation": True,
            "reason": "No clear link-list section found in MOC",
        }

    candidates.sort(key=lambda x: x[0], reverse=True)
    best_score, best_sec, best_reasons = candidates[0]
    ambiguous = len(candidates) > 1 and abs(best_score - candidates[1][0]) < 1.0 and best_score < 4.0
    conf = "high" if best_score >= 5.0 else ("medium" if best_score >= 1.5 and not ambiguous else "low")
    return {
        "section": best_sec,
        "confidence": conf,
        "needs_confirmation": conf == "low" or ambiguous,
        "reason": "; ".join(best_reasons) if best_reasons else "Selected main MOC link list",
    }


def _render_moc_entry_line(
    link_str: str,
    bullet_prefix: str,
    annotation_sep: str,
    short_desc: str,
) -> str:
    prefix = bullet_prefix if bullet_prefix else "- "
    if annotation_sep and short_desc:
        return f"{prefix}{link_str}{annotation_sep}{short_desc}"
    return f"{prefix}{link_str}"


def build_minimal_moc_update(
    moc_rel_path: str,
    moc_text: str,
    target_rel_path: str,
    target_title: str,
    link_style: str,
    short_desc: str,
    section_choice: dict[str, Any],
) -> dict[str, Any]:
    """Insert a single verified link into the chosen MOC section without touching unrelated text."""
    lines = moc_text.splitlines()
    sec = section_choice["section"]
    no_ext = target_rel_path[:-3] if target_rel_path.endswith(".md") else target_rel_path
    stem = Path(no_ext).name
    link_target = no_ext if link_style == "wikilink_folder_qualified" and "/" in no_ext else stem
    link_str = f"[[{link_target}]]" if link_target == target_title else f"[[{link_target}|{target_title}]]"
    if link_style == "markdown":
        link_str = f"[{target_title}]({target_rel_path})"

    new_line = _render_moc_entry_line(
        link_str,
        sec.get("bullet_prefix", "- "),
        sec.get("annotation_sep", ""),
        short_desc,
    )

    link_lines: list[int] = sec.get("link_lines", [])
    if link_lines:
        # Check if existing link lines appear alphabetically sorted
        existing_labels: list[tuple[int, str]] = []
        for ln_idx in link_lines:
            raw = lines[ln_idx]
            wm = WIKILINK_RE.search(raw)
            label = (wm.group(2).split("|")[-1] if wm else raw).strip().lower()
            existing_labels.append((ln_idx, label))
        sorted_labels = [lbl for _, lbl in existing_labels]
        is_sorted = len(sorted_labels) >= 3 and sorted_labels == sorted(sorted_labels)

        if is_sorted:
            insert_at = link_lines[-1] + 1
            for ln_idx, lbl in existing_labels:
                if target_title.lower() < lbl:
                    insert_at = ln_idx
                    break
        else:
            insert_at = link_lines[-1] + 1
    else:
        insert_at = sec["start_line"]
        while insert_at < sec["end_line"] and not lines[insert_at].strip():
            insert_at += 1

    updated_lines = lines[:insert_at] + [new_line] + lines[insert_at:]
    trailing = "\n" if (moc_text.endswith("\n") or not moc_text) else ""
    new_text = "\n".join(updated_lines) + trailing
    diff = "".join(
        difflib.unified_diff(
            moc_text.splitlines(keepends=True),
            new_text.splitlines(keepends=True),
            fromfile=f"a/{moc_rel_path}",
            tofile=f"b/{moc_rel_path}",
        )
    )
    return {
        "rel_path": moc_rel_path,
        "inserted_line": new_line,
        "insert_line_number": insert_at + 1,
        "new_text": new_text,
        "diff": diff,
        "expected_sha256": sha256_text(moc_text),
    }


def _infer_new_moc_location_and_name(
    topic: str,
    target_folder: str,
    cluster_notes: list[dict[str, Any]],
    profile: dict[str, Any],
) -> tuple[str, str]:
    """Match existing vault MOC naming and placement conventions without mandating MOCs/."""
    existing_mocs = profile.get("mocs", [])
    folders_meta = profile.get("folders", {})

    # Determine cluster name from target folder leaf or shared topic/tag theme
    if target_folder:
        cluster_label = target_folder.split("/")[-1]
    else:
        cluster_label = topic

    # Check if vault uses folder-note MOCs (`Folder/Folder.md` or `Folder/index.md`)
    folder_note_hits = sum(1 for m in existing_mocs if m.get("moc_kind") == "folder_note")
    moc_suffix_hits = sum(1 for m in existing_mocs if re.search(r"\bMOC\b", m.get("stem", ""), re.IGNORECASE))
    index_hits = sum(1 for m in existing_mocs if re.search(r"\bIndex\b", m.get("stem", ""), re.IGNORECASE))

    # Check if existing MOCs live inside a dedicated moc_hub folder
    moc_hub_folders = [
        fk for fk, fv in folders_meta.items()
        if fv.get("role") == "moc_hub" and fk != "."
    ]

    if target_folder:
        dest_folder = target_folder
    elif moc_hub_folders:
        dest_folder = moc_hub_folders[0]
    else:
        dest_folder = ""

    if folder_note_hits > max(moc_suffix_hits, index_hits) and target_folder:
        stem = target_folder.split("/")[-1]
    elif index_hits > moc_suffix_hits:
        stem = f"{cluster_label} Index"
    else:
        stem = f"{cluster_label} MOC"

    rel_path = f"{dest_folder}/{stem}.md" if dest_folder else f"{stem}.md"
    return dest_folder, rel_path


def _select_coherent_cluster(
    topic: str,
    target_folder: str,
    related_results: list[dict[str, Any]],
    profile: dict[str, Any],
    index: dict[str, Any],
    min_cluster_size: int,
) -> list[dict[str, Any]]:
    """Find closely related, unhubbed notes forming a coherent navigation cluster."""
    mocs = profile.get("mocs", [])
    already_hubbed: set[str] = set()
    for m in mocs:
        for out_t in m.get("outgoing_targets", []):
            for r in related_results:
                if links_equivalent(out_t, r["rel_path"], index):
                    already_hubbed.add(r["rel_path"])

    coherent: list[dict[str, Any]] = []
    for r in related_results:
        # Require strong semantic score OR same folder + meaningful overlap
        same_folder = bool(target_folder and r.get("folder", "") == target_folder)
        if r.get("score", 0) >= 6.0 or (same_folder and r.get("score", 0) >= 3.0):
            if r["rel_path"] not in already_hubbed:
                coherent.append(r)

    if 1 + len(coherent) < min_cluster_size:
        return []
    return coherent[:8]


def _render_new_moc_content(
    moc_rel_path: str,
    moc_title: str,
    target_rel_path: str,
    topic: str,
    cluster_notes: list[dict[str, Any]],
    selected_tags: list[str],
    parent_moc: dict[str, Any] | None,
    link_style: str,
    index: dict[str, Any],
    mermaid_block: str = "",
) -> str:
    """Render a clean, scope-documented new MOC matching vault conventions."""
    lines: list[str] = [
        "---",
        f'title: "{moc_title}"',
        "tags:",
        "  - moc",
    ]
    for t in selected_tags[:3]:
        lines.append(f"  - {t}")
    lines.append(f'created: "{today_iso()}"')
    if parent_moc:
        p_stem = Path(parent_moc["path"]).stem
        lines.append(f'up: "[[{p_stem}]]"')
    lines.extend(["---", "", f"# {moc_title}", ""])

    if parent_moc:
        p_stem = Path(parent_moc["path"]).stem
        lines.extend([f"**Parent Hub:** [[{p_stem}]]", ""])

    lines.extend(
        [
            f"Navigation hub for coherent concepts around **{topic}** and related notes in this area.",
            "",
        ]
    )

    if mermaid_block:
        lines.extend(["## Concept Map", "", mermaid_block.strip(), ""])

    lines.extend(["## Core Concepts", ""])

    # Include the newly planned note + verified links to coherent existing cluster notes
    target_no_ext = target_rel_path[:-3] if target_rel_path.endswith(".md") else target_rel_path
    target_stem = Path(target_no_ext).name
    target_link = (
        f"[[{target_no_ext}|{topic}]]"
        if (link_style == "wikilink_folder_qualified" and "/" in target_no_ext)
        else (f"[[{target_stem}]]" if target_stem == topic else f"[[{target_stem}|{topic}]]")
    )
    entries: list[tuple[str, str]] = [(topic.lower(), f"- {target_link} — Primary entry for {topic}")]
    for r in cluster_notes:
        wlink = resolve_safe_wikilink(r["rel_path"], index, preferred_style=link_style)
        if wlink:
            summary = (r.get("summary") or "").strip()
            if len(summary) > 90:
                summary = summary[:87].rstrip() + "..."
            desc = f" — {summary}" if summary else ""
            entries.append((r.get("title", r["stem"]).lower(), f"- {wlink}{desc}"))

    entries.sort(key=lambda x: x[0])
    for _, line in entries:
        lines.append(line)
    lines.append("")
    return "\n".join(lines)


def plan_moc_integration(
    vault_root: Path,
    topic: str,
    target_rel_path: str,
    target_folder: str,
    selected_tags: list[str],
    related_results: list[dict[str, Any]],
    profile: dict[str, Any],
    index: dict[str, Any],
    link_style: str = "wikilink",
    keywords: list[str] | None = None,
    short_desc: str = "",
    min_cluster_size: int | None = None,
    allow_moc: bool = True,
) -> dict[str, Any]:
    """Plan MOC selection, query metadata satisfaction, minimal update, or justified creation."""
    if not allow_moc:
        return {
            "action": "none",
            "reason": "MOC integration disabled for this run",
            "selected_moc": None,
            "target_section": None,
            "new_moc_path": None,
            "query_requirements": {},
            "cluster_candidates": [],
            "min_cluster_size": min_cluster_size or DEFAULT_MIN_CLUSTER_SIZE,
            "evidence": [],
            "confidence": "high",
            "needs_confirmation": False,
            "warnings": [],
            "file_edit": None,
        }

    cfg = load_config()
    eff_min_cluster = int(min_cluster_size or cfg.get("moc_min_cluster_size", DEFAULT_MIN_CLUSTER_SIZE))
    eff_min_cluster = max(2, eff_min_cluster)

    ranked = _score_existing_mocs(
        topic=topic,
        target_folder=target_folder,
        selected_tags=selected_tags,
        related_results=related_results,
        profile=profile,
        index=index,
        keywords=keywords,
    )

    extra_rels = {target_rel_path}
    if ranked and ranked[0]["score"] >= 6.0:
        best = ranked[0]
        moc_rel = best["path"]
        moc_abs = (vault_root / moc_rel).resolve()

        # If target note IS the MOC itself, do not self-link
        if moc_rel == target_rel_path:
            return {
                "action": "none",
                "reason": "Target note is the MOC itself",
                "selected_moc": moc_rel,
                "target_section": None,
                "new_moc_path": None,
                "query_requirements": {},
                "cluster_candidates": [],
                "min_cluster_size": eff_min_cluster,
                "evidence": best["evidence"],
                "confidence": "high",
                "needs_confirmation": False,
                "warnings": [],
                "file_edit": None,
            }

        # Check query-driven MOC first (avoid inserting redundant manual lists!)
        if best["moc_kind"] == "query_driven" and best["query_match"]:
            return {
                "action": "satisfy_query",
                "reason": f"Query-driven MOC '{moc_rel}' auto-includes matching notes via metadata/folder; skipping manual list edit",
                "selected_moc": moc_rel,
                "target_section": None,
                "new_moc_path": None,
                "query_requirements": best["query_requirements"],
                "cluster_candidates": [],
                "min_cluster_size": eff_min_cluster,
                "evidence": best["evidence"],
                "confidence": "high",
                "needs_confirmation": False,
                "warnings": [],
                "file_edit": None,
            }

        if moc_abs.is_file():
            moc_text = read_text_safe(moc_abs)
            live_links = _extract_all_live_links(moc_text)
            if any(links_equivalent(lnk, target_rel_path, index, extra_rel_paths=extra_rels) for lnk in live_links):
                return {
                    "action": "already_linked",
                    "reason": f"'{moc_rel}' already contains an equivalent link to '{topic}'",
                    "selected_moc": moc_rel,
                    "target_section": None,
                    "new_moc_path": None,
                    "query_requirements": {},
                    "cluster_candidates": [],
                    "min_cluster_size": eff_min_cluster,
                    "evidence": best["evidence"],
                    "confidence": "high",
                    "needs_confirmation": False,
                    "warnings": [],
                    "file_edit": None,
                }

            sec_choice = _select_moc_section(moc_text, topic, keywords, related_results, index)
            target_stem_low = Path(target_rel_path).stem.lower()
            stem_collides = any(
                d.get("stem", "").lower() == target_stem_low and rel != target_rel_path
                for rel, d in index.get("docs", {}).items()
            )
            eff_link_style = "wikilink_folder_qualified" if stem_collides else link_style
            edit = build_minimal_moc_update(
                moc_rel_path=moc_rel,
                moc_text=moc_text,
                target_rel_path=target_rel_path,
                target_title=topic,
                link_style=eff_link_style,
                short_desc=short_desc,
                section_choice=sec_choice,
            )
            warnings = []
            if sec_choice["needs_confirmation"]:
                warnings.append(f"MOC section insertion in '{moc_rel}' has low confidence; preview recommended.")
            return {
                "action": "update_existing",
                "reason": f"Selected closest existing hub '{moc_rel}' ({sec_choice['reason']})",
                "selected_moc": moc_rel,
                "target_section": sec_choice["section"]["heading"] or "(root list)",
                "new_moc_path": None,
                "query_requirements": {},
                "cluster_candidates": [],
                "min_cluster_size": eff_min_cluster,
                "evidence": best["evidence"],
                "confidence": sec_choice["confidence"],
                "needs_confirmation": sec_choice["needs_confirmation"],
                "warnings": warnings,
                "file_edit": {
                    "rel_path": moc_rel,
                    "role": "moc_update",
                    "action": "insert_section_line",
                    "expected_sha256": edit["expected_sha256"],
                    "must_not_exist": False,
                    "confidence": sec_choice["confidence"],
                    "needs_confirmation": sec_choice["needs_confirmation"],
                    "inserted_line": edit["inserted_line"],
                    "diff": edit["diff"],
                    "new_text": edit["new_text"],
                },
            }

    # No existing MOC adequately covers this topic; check if a coherent cluster justifies a new MOC
    cluster = _select_coherent_cluster(
        topic=topic,
        target_folder=target_folder,
        related_results=related_results,
        profile=profile,
        index=index,
        min_cluster_size=eff_min_cluster,
    )
    if not cluster:
        return {
            "action": "none",
            "reason": f"No existing MOC matched strongly and cluster size < {eff_min_cluster} coherent unhubbed notes; suppressing unnecessary MOC creation",
            "selected_moc": None,
            "target_section": None,
            "new_moc_path": None,
            "query_requirements": {},
            "cluster_candidates": [r["rel_path"] for r in related_results[:4]],
            "min_cluster_size": eff_min_cluster,
            "evidence": ["Suppressed unnecessary MOC creation"],
            "confidence": "high",
            "needs_confirmation": False,
            "warnings": [],
            "file_edit": None,
        }

    _, new_moc_rel = _infer_new_moc_location_and_name(topic, target_folder, cluster, profile)
    if (vault_root / new_moc_rel).exists():
        # Safety check: if inferred MOC path unexpectedly exists on disk, don't overwrite
        return {
            "action": "none",
            "reason": f"Inferred MOC path '{new_moc_rel}' already exists on disk",
            "selected_moc": new_moc_rel,
            "target_section": None,
            "new_moc_path": None,
            "query_requirements": {},
            "cluster_candidates": [r["rel_path"] for r in cluster],
            "min_cluster_size": eff_min_cluster,
            "evidence": [],
            "confidence": "medium",
            "needs_confirmation": True,
            "warnings": [f"Candidate new MOC '{new_moc_rel}' already exists"],
            "file_edit": None,
        }

    moc_title = Path(new_moc_rel).stem
    parent_moc = ranked[0] if ranked and ranked[0]["score"] >= 2.0 else None
    moc_diagram = plan_mermaid_diagram(
        topic=moc_title,
        profile=profile,
        target_folder=target_folder,
        related_notes=cluster,
        content={"concepts": [topic] + [r.get("title", r["stem"]) for r in cluster[:4]]},
        mermaid_mode="auto",
        note_role="moc",
    )
    new_moc_text = _render_new_moc_content(
        moc_rel_path=new_moc_rel,
        moc_title=moc_title,
        target_rel_path=target_rel_path,
        topic=topic,
        cluster_notes=cluster,
        selected_tags=selected_tags,
        parent_moc=parent_moc,
        link_style=link_style,
        index=index,
        mermaid_block=moc_diagram.get("rendered_block", "") if moc_diagram.get("include_diagram") else "",
    )
    diff = "".join(
        difflib.unified_diff(
            [],
            new_moc_text.splitlines(keepends=True),
            fromfile="/dev/null",
            tofile=f"b/{new_moc_rel}",
        )
    )
    return {
        "action": "create_new",
        "reason": f"Coherent cluster of {1 + len(cluster)} unhubbed notes justifies navigation MOC '{new_moc_rel}'",
        "selected_moc": new_moc_rel,
        "target_section": "Core Concepts",
        "new_moc_path": new_moc_rel,
        "query_requirements": {},
        "cluster_candidates": [r["rel_path"] for r in cluster],
        "min_cluster_size": eff_min_cluster,
        "evidence": [
            f"Cluster size {1 + len(cluster)} >= min_cluster_size {eff_min_cluster}",
            f"Grouped notes: {', '.join(r['stem'] for r in cluster[:4])}",
        ],
        "confidence": "medium",
        "needs_confirmation": False,
        "warnings": [],
        "diagram": moc_diagram if moc_diagram.get("include_diagram") else None,
        "file_edit": {
            "rel_path": new_moc_rel,
            "role": "moc_create",
            "action": "create",
            "expected_sha256": None,
            "must_not_exist": True,
            "confidence": "medium",
            "needs_confirmation": False,
            "diff": diff,
            "new_text": new_moc_text,
        },
    }
