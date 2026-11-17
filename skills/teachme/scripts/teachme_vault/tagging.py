"""Context-aware tag selection, synonym detection, and justified tag creation."""

from __future__ import annotations

import re
from typing import Any

from .indexer import tokenize
from .markdown_utils import is_workflow_or_status_tag, normalize_tag


def _singularize(word: str) -> str:
    if len(word) > 4 and word.endswith("ies"):
        return word[:-3] + "y"
    if len(word) > 4 and word.endswith("es") and word[-3] in ("s", "x", "z", "h"):
        return word[:-2]
    if len(word) > 3 and word.endswith("s") and not word.endswith(("ss", "is", "us")):
        return word[:-1]
    return word


def _tag_stem_tokens(tag: str) -> list[str]:
    clean = normalize_tag(tag).lower()
    raw_parts = re.split(r"[/\-_\s]+", clean)
    return [_singularize(p) for p in raw_parts if p]


def _canonical_tag_key(tag: str) -> str:
    """Normalized comparison key for detecting separator/case/plural near-duplicates."""
    return "-".join(_tag_stem_tokens(tag))


def _format_segment(words: list[str], case_style: str) -> str:
    cleaned = [re.sub(r"[^\w]", "", w, flags=re.UNICODE) for w in words if w.strip()]
    cleaned = [w for w in cleaned if w]
    if not cleaned:
        return ""
    if case_style == "snake_case":
        return "_".join(w.lower() for w in cleaned)
    if case_style == "camel_case":
        return cleaned[0].lower() + "".join(w[:1].upper() + w[1:].lower() for w in cleaned[1:])
    if case_style == "pascal_case":
        return "".join(w[:1].upper() + w[1:].lower() for w in cleaned)
    if case_style == "lowercase":
        return "".join(w.lower() for w in cleaned)
    return "-".join(w.lower() for w in cleaned)


def _format_tag_to_convention(
    raw_concept: str,
    case_style: str,
    namespace: str = "",
) -> str:
    """Format a candidate concept tag according to vault/folder case and namespace conventions."""
    norm = normalize_tag(raw_concept)
    if "/" in norm:
        parts = [p.strip() for p in norm.split("/") if p.strip()]
        formatted_parts = [
            _format_segment(re.split(r"[\s_-]+", p), case_style)
            for p in parts
        ]
        formatted_parts = [p for p in formatted_parts if p]
        return "/".join(formatted_parts)

    words = [w for w in re.split(r"[\s_-]+", norm) if w]
    leaf = _format_segment(words, case_style)
    if not leaf:
        return ""
    if namespace:
        ns_clean = normalize_tag(namespace).strip("/")
        if ns_clean and ns_clean.lower() != leaf.lower():
            return f"{ns_clean}/{leaf}"
    return leaf


def _extract_content_corpus(
    topic: str,
    content: dict[str, Any] | None,
    keywords: list[str] | None,
    related_results: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build bounded semantic signal sets from note content, topic, and neighbors."""
    c = content or {}
    content_parts = [
        topic,
        str(c.get("intuition", "")),
        str(c.get("mechanism", "")),
        str(c.get("invariant", "")),
        str(c.get("summary", "")),
        str(c.get("example", "")),
        str(c.get("body", "")),
        " ".join(keywords or []),
        " ".join(str(x) for x in c.get("concepts", []) if isinstance(x, str)),
    ]
    note_text = " ".join(p for p in content_parts if p.strip())
    note_tokens = set(tokenize(note_text))
    note_stems = {_singularize(t) for t in note_tokens}

    neighbor_tokens: set[str] = set()
    neighbor_tag_counts: dict[str, int] = {}
    for r in related_results[:5]:
        neighbor_tokens.update(tokenize(f"{r.get('title', '')} {r.get('summary', '')} {' '.join(r.get('headings', []))}"))
        for t in r.get("tags", []):
            neighbor_tag_counts[t] = neighbor_tag_counts.get(t, 0) + 1
    neighbor_stems = {_singularize(t) for t in neighbor_tokens}

    return {
        "note_text_low": note_text.lower(),
        "note_tokens": note_tokens,
        "note_stems": note_stems,
        "neighbor_tokens": neighbor_tokens,
        "neighbor_stems": neighbor_stems,
        "neighbor_tag_counts": neighbor_tag_counts,
    }


def _vault_uses_parent_and_child_together(profile: dict[str, Any]) -> bool:
    """Detect whether the vault explicitly co-applies parent and child tags on notes."""
    file_cache = profile.get("_file_cache", {})
    co_occur = 0
    nested_notes = 0
    for rec in list(file_cache.values())[:200]:
        tags = rec.get("tags", [])
        nested = [t for t in tags if "/" in t]
        if nested:
            nested_notes += 1
            tag_set = set(tags)
            if any(nt.split("/")[0] in tag_set for nt in nested):
                co_occur += 1
    return nested_notes >= 3 and co_occur >= max(2, nested_notes // 2)


def _find_best_namespace(
    target_folder: str,
    profile: dict[str, Any],
    related_results: list[dict[str, Any]],
    corpus: dict[str, Any],
) -> str:
    """Select an appropriate existing nested namespace if the vault uses nested tags."""
    tax = profile.get("tag_taxonomy", {})
    if not tax.get("uses_nested_tags"):
        return ""
    nested_roots: list[str] = tax.get("nested_roots", [])
    if not nested_roots:
        return ""

    folder_info = profile.get("folders", {}).get(target_folder or ".", {})
    folder_tags = [
        st["tag"] if isinstance(st, dict) else st
        for st in folder_info.get("subject_tags", folder_info.get("top_tags", []))
    ]
    # 1. Namespace already active in destination folder
    for ft in folder_tags:
        if "/" in ft:
            return ft.split("/")[0]
    # 2. Namespace used by top related neighbors
    for r in related_results[:3]:
        for t in r.get("tags", []):
            if "/" in t:
                return t.split("/")[0]
    # 3. Root namespace matching folder path or note content
    folder_stems = {_singularize(t) for t in tokenize(target_folder.replace("/", " "))}
    for root_ns in nested_roots:
        ns_stems = set(_tag_stem_tokens(root_ns))
        if ns_stems & (folder_stems | corpus["note_stems"]):
            return root_ns
    return ""


def _find_near_duplicate(candidate: str, existing_vocab: list[str]) -> str | None:
    """Find an existing vault tag that is a synonym, separator/case variant, or near-duplicate."""
    cand_norm = normalize_tag(candidate)
    cand_low = cand_norm.lower()
    cand_key = _canonical_tag_key(cand_norm)
    cand_leaf_key = "-".join(_tag_stem_tokens(cand_norm.split("/")[-1]))
    cand_stem_set = set(_tag_stem_tokens(cand_norm))

    for ex in existing_vocab:
        ex_low = normalize_tag(ex).lower()
        if ex_low == cand_low:
            return ex
        if _canonical_tag_key(ex) == cand_key:
            return ex
        ex_leaf_key = "-".join(_tag_stem_tokens(ex.split("/")[-1]))
        if cand_leaf_key and cand_leaf_key == ex_leaf_key and "/" in ex and "/" not in cand_norm:
            return ex
        ex_stem_set = set(_tag_stem_tokens(ex))
        if cand_stem_set and ex_stem_set:
            jaccard = len(cand_stem_set & ex_stem_set) / len(cand_stem_set | ex_stem_set)
            if jaccard >= 0.8 and len(cand_stem_set) >= 2:
                return ex
    return None


def _is_overly_specific_one_off(tag: str) -> tuple[bool, str]:
    """Reject overly narrow, ephemeral, or sentence-like one-off tags."""
    leaf = normalize_tag(tag).split("/")[-1]
    parts = [p for p in re.split(r"[-_\s]+", leaf) if p]
    if len(parts) > 4:
        return True, "Too many words (>4) for a reusable tag"
    if len(leaf) > 45:
        return True, "Tag leaf exceeds 45 characters"
    if re.search(r"\b\d{4,}\b", leaf):
        return True, "Contains specific multi-digit identifier/date"
    if len(leaf) <= 1:
        return True, "Single-character tag is too ambiguous"
    return False, ""


def select_and_plan_tags(
    topic: str,
    profile: dict[str, Any],
    target_folder: str,
    related_results: list[dict[str, Any]],
    keywords: list[str] | None = None,
    content: dict[str, Any] | None = None,
    proposed_tags: list[str | dict[str, Any]] | None = None,
    template_tags: list[str] | None = None,
    moc_query_tags: list[str] | None = None,
    max_tags: int = 4,
) -> dict[str, Any]:
    """Select context-appropriate existing tags and create justified new tags with evidence."""
    tax = profile.get("tag_taxonomy", {})
    folder_info = profile.get("folders", {}).get(target_folder or ".", {})
    plugin_conv = profile.get("plugins", {}).get("conventions", {})

    plugin_tags: set[str] = set()
    for ft in plugin_conv.get("flashcard_tags", []):
        plugin_tags.add(str(ft).lstrip("#").lower())
    tgf = str(plugin_conv.get("task_global_filter", "")).strip()
    if tgf.startswith("#"):
        plugin_tags.add(tgf.lstrip("#").lower())

    # Determine convention priority: folder local > template > vault-wide > minimal default
    placement = folder_info.get("tag_placement", "unknown")
    if placement in ("unknown", "none"):
        placement = tax.get("placement", "frontmatter")
    if placement == "none":
        placement = "frontmatter"

    case_style = folder_info.get("tag_case", "unknown")
    if case_style == "unknown":
        case_style = tax.get("case_style", "kebab_case")

    # Build subject vocabulary (excluding workflow/status/plugin tags)
    all_subject_map: dict[str, int] = dict(tax.get("all_subject_tags", {}))
    if not all_subject_map:
        for item in tax.get("subject_tags", []) or tax.get("top_tags", []):
            if isinstance(item, dict):
                t = item.get("tag", "")
                c = int(item.get("count", 1))
            else:
                t, c = str(item), 1
            if t and not is_workflow_or_status_tag(t, plugin_tags=plugin_tags):
                all_subject_map[t] = c

    folder_subject_tags: list[str] = []
    for item in folder_info.get("subject_tags", []):
        t = item["tag"] if isinstance(item, dict) else str(item)
        if t and not is_workflow_or_status_tag(t, plugin_tags=plugin_tags):
            folder_subject_tags.append(t)
    if not folder_subject_tags:
        for t in folder_info.get("top_tags", []):
            if not is_workflow_or_status_tag(t, plugin_tags=plugin_tags):
                folder_subject_tags.append(t)

    corpus = _extract_content_corpus(topic, content, keywords, related_results)
    decisions: list[dict[str, Any]] = []
    warnings: list[str] = []
    selected: list[str] = []
    seen_canonical: set[str] = set()

    # Check if vault uses tags at all (empty or tag-free vault)
    total_notes = profile.get("total_notes", 0)
    vault_uses_tags = bool(all_subject_map) or bool(template_tags) or bool(moc_query_tags)

    # 1. Evaluate existing subject tags from neighbors, folder, template, and vault-wide vocab
    candidate_pool: list[str] = []
    for src_list in (
        moc_query_tags or [],
        list(corpus["neighbor_tag_counts"].keys()),
        folder_subject_tags,
        template_tags or [],
        list(all_subject_map.keys())[:120],
    ):
        for t in src_list:
            norm = normalize_tag(str(t))
            if not norm:
                continue
            if is_workflow_or_status_tag(norm, plugin_tags=plugin_tags):
                if norm not in [d["tag"] for d in decisions]:
                    decisions.append(
                        {
                            "tag": norm,
                            "decision": "skip",
                            "category": "workflow_excluded",
                            "reason": "Workflow/status/plugin tag kept separate from subject tags",
                            "evidence": [],
                            "confidence": "high",
                        }
                    )
                continue
            if norm not in candidate_pool:
                candidate_pool.append(norm)

    scored_existing: list[tuple[float, str, list[str], str]] = []
    for tag in candidate_pool:
        tag_low = tag.lower()
        tag_stems = set(_tag_stem_tokens(tag))
        leaf_stems = set(_tag_stem_tokens(tag.split("/")[-1]))

        note_overlap = tag_stems & corpus["note_stems"]
        leaf_overlap = leaf_stems & corpus["note_stems"]
        neighbor_overlap = tag_stems & corpus["neighbor_stems"]
        phrase_hit = tag_low.replace("/", " ").replace("-", " ").replace("_", " ") in corpus["note_text_low"]
        in_neighbors = corpus["neighbor_tag_counts"].get(tag, 0)
        in_folder = tag in folder_subject_tags
        in_moc_query = bool(moc_query_tags and tag in moc_query_tags)
        in_template = bool(template_tags and tag in template_tags)

        # Require genuine semantic evidence (content/concept overlap or strong neighbor/query grounding)
        has_semantic_match = bool(note_overlap or leaf_overlap or phrase_hit or in_neighbors >= 2 or (in_neighbors >= 1 and neighbor_overlap))
        if not has_semantic_match and not in_moc_query:
            if in_folder or in_template:
                decisions.append(
                    {
                        "tag": tag,
                        "decision": "reject",
                        "category": "subject",
                        "reason": "Popular in folder/template but lacks semantic relevance to note content",
                        "evidence": [f"folder={target_folder or '.'}"],
                        "confidence": "high",
                    }
                )
            continue

        score = (
            len(leaf_overlap) * 4.0
            + len(note_overlap) * 2.5
            + (4.0 if phrase_hit else 0.0)
            + min(3, in_neighbors) * 2.0
            + (1.5 if neighbor_overlap else 0.0)
            + (1.0 if in_folder else 0.0)
            + (3.0 if in_moc_query else 0.0)
            + (0.5 if "/" in tag else 0.0)
        )
        ev: list[str] = []
        if note_overlap or phrase_hit:
            ev.append(f"Matches note content/concepts ({', '.join(sorted(note_overlap)[:3]) or tag})")
        if in_neighbors:
            ev.append(f"Used by {in_neighbors} related neighbor note(s)")
        if in_folder:
            ev.append(f"Established in folder '{target_folder or '.'}'")
        if in_moc_query:
            ev.append("Required by query-driven MOC filter")
        conf = "high" if (leaf_overlap or phrase_hit or (note_overlap and in_neighbors)) else "medium"
        scored_existing.append((score, tag, ev, conf))

    scored_existing.sort(key=lambda x: x[0], reverse=True)
    for score, tag, ev, conf in scored_existing:
        if len(selected) >= max_tags:
            break
        canon = _canonical_tag_key(tag)
        if canon in seen_canonical:
            decisions.append(
                {
                    "tag": tag,
                    "decision": "reject",
                    "category": "subject",
                    "reason": "Near-duplicate of already selected tag",
                    "evidence": ev,
                    "confidence": "high",
                }
            )
            continue
        selected.append(tag)
        seen_canonical.add(canon)
        decisions.append(
            {
                "tag": tag,
                "decision": "reuse",
                "category": "subject",
                "reason": "Reused established vault tag matching note semantics",
                "evidence": ev,
                "confidence": conf,
            }
        )

    # 2. Evaluate explicit semantic proposals from coding agent or content concepts
    raw_proposals: list[tuple[str, str]] = []
    if proposed_tags:
        for item in proposed_tags:
            if isinstance(item, dict):
                t_val = str(item.get("tag", "")).strip()
                t_why = str(item.get("reason", "Proposed from note semantic analysis")).strip()
                if t_val:
                    raw_proposals.append((t_val, t_why))
            elif isinstance(item, str) and item.strip():
                raw_proposals.append((item.strip(), "Proposed from note semantic analysis"))
    elif content and isinstance(content.get("tags"), list):
        for t in content["tags"]:
            if str(t).strip():
                raw_proposals.append((str(t).strip(), "Extracted from structured note content"))

    # If still under max_tags and no existing tag matched strongly, inspect keywords/concepts
    if len(selected) == 0 and not raw_proposals and keywords and vault_uses_tags:
        for kw in keywords[:2]:
            raw_proposals.append((kw, f"Core concept '{kw}' not covered by existing vault tags"))

    allow_parent_child = _vault_uses_parent_and_child_together(profile)
    existing_vocab_list = list(all_subject_map.keys()) + selected
    default_ns = _find_best_namespace(target_folder, profile, related_results, corpus)

    for raw_tag, why in raw_proposals:
        if len(selected) >= max_tags:
            break
        norm_raw = normalize_tag(raw_tag)
        if not norm_raw:
            continue
        if is_workflow_or_status_tag(norm_raw, plugin_tags=plugin_tags):
            decisions.append(
                {
                    "tag": norm_raw,
                    "decision": "reject",
                    "category": "workflow_excluded",
                    "reason": "Never infer or emit workflow/status/mastery tags as subject tags",
                    "evidence": [],
                    "confidence": "high",
                }
            )
            continue

        # Synonym / near-duplicate check against existing vocabulary
        dup = _find_near_duplicate(norm_raw, existing_vocab_list)
        if dup:
            canon = _canonical_tag_key(dup)
            if canon not in seen_canonical and len(selected) < max_tags:
                selected.append(dup)
                seen_canonical.add(canon)
                decisions.append(
                    {
                        "tag": dup,
                        "decision": "reuse",
                        "category": "subject",
                        "reason": f"Reused existing tag '{dup}' instead of creating near-duplicate '{norm_raw}'",
                        "evidence": [f"Matched candidate '{norm_raw}'"],
                        "confidence": "high",
                    }
                )
            else:
                decisions.append(
                    {
                        "tag": norm_raw,
                        "decision": "reject",
                        "category": "subject",
                        "reason": f"Near-duplicate/synonym of existing tag '{dup}'",
                        "evidence": [f"Existing canonical tag: {dup}"],
                        "confidence": "high",
                    }
                )
            continue

        too_specific, spec_reason = _is_overly_specific_one_off(norm_raw)
        if too_specific:
            decisions.append(
                {
                    "tag": norm_raw,
                    "decision": "reject",
                    "category": "subject",
                    "reason": f"Avoided one-off tag: {spec_reason}",
                    "evidence": [],
                    "confidence": "high",
                }
            )
            continue

        # Format new tag to established vault conventions (case, separator, namespace)
        ns_to_use = "" if "/" in norm_raw else default_ns
        formatted = _format_tag_to_convention(norm_raw, case_style=case_style, namespace=ns_to_use)
        if not formatted:
            continue

        # Re-check near-duplicate after namespace formatting
        dup_after = _find_near_duplicate(formatted, existing_vocab_list)
        if dup_after:
            decisions.append(
                {
                    "tag": formatted,
                    "decision": "reject",
                    "category": "subject",
                    "reason": f"Duplicate of existing tag '{dup_after}' after convention formatting",
                    "evidence": [f"Existing tag: {dup_after}"],
                    "confidence": "high",
                }
            )
            continue

        canon_new = _canonical_tag_key(formatted)
        if canon_new in seen_canonical:
            continue

        selected.append(formatted)
        seen_canonical.add(canon_new)
        existing_vocab_list.append(formatted)
        decisions.append(
            {
                "tag": formatted,
                "decision": "create",
                "category": "subject",
                "reason": why,
                "evidence": [
                    f"Conforms to case={case_style}" + (f", namespace={ns_to_use}" if ns_to_use else ""),
                    "No semantic duplicate found in existing vault vocabulary",
                ],
                "confidence": "medium",
            }
        )

    # 3. Redundant parent/child pruning unless vault convention uses both
    if not allow_parent_child and len(selected) > 1:
        nested_roots_present = {t.split("/")[0].lower() for t in selected if "/" in t}
        pruned: list[str] = []
        for t in selected:
            if "/" not in t and t.lower() in nested_roots_present:
                decisions.append(
                    {
                        "tag": t,
                        "decision": "reject",
                        "category": "subject",
                        "reason": "Pruned redundant parent tag because more specific nested child tag is selected",
                        "evidence": [f"Vault rarely co-occurs parent '{t}' with '{t}/...'"],
                        "confidence": "high",
                    }
                )
                continue
            pruned.append(t)
        selected = pruned

    if not selected and total_notes > 0 and not vault_uses_tags:
        decisions.append(
            {
                "tag": "",
                "decision": "skip",
                "category": "subject",
                "reason": "Vault does not use tags; permitting tag-free note",
                "evidence": [f"total_notes={total_notes}, unique_tags=0"],
                "confidence": "high",
            }
        )

    return {
        "selected_tags": selected,
        "placement": placement,
        "case_style": case_style,
        "decisions": decisions,
        "warnings": warnings,
    }
