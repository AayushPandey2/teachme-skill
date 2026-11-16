"""Confidence-based destination folder and filename resolver."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
import re
from typing import Any

from .indexer import tokenize

NON_CONTENT_ROLES = frozenset(
    {"templates", "attachments", "protected_assets", "archive", "periodic"}
)


def format_note_filename(
    topic_title: str,
    naming_convention: str,
    existing_stems: set[str] | None = None,
) -> str:
    """Format a note filename matching the target folder/vault naming convention."""
    clean = re.sub(r'[<>:"/\\|?*]', "", topic_title).strip()
    words = re.findall(r"[A-Za-z0-9]+", clean)
    slug_kebab = "-".join(w.lower() for w in words) or "note"
    slug_snake = "_".join(w.lower() for w in words) or "note"

    if naming_convention == "kebab_case":
        stem = slug_kebab
    elif naming_convention == "snake_case":
        stem = slug_snake
    elif naming_convention == "zettelkasten_timestamp":
        ts = datetime.now(timezone.utc).strftime("%Y%m%d%H%M")
        stem = f"{ts}-{slug_kebab}"
    elif naming_convention == "numeric_prefix" and existing_stems is not None:
        max_num = 0
        for s in existing_stems:
            m = re.match(r"^(\d+)[-_\s]", s)
            if m:
                max_num = max(max_num, int(m.group(1)))
        stem = f"{max_num + 1:02d}-{slug_kebab}"
    elif naming_convention == "title_case":
        stem = " ".join(w.capitalize() if w.islower() else w for w in clean.split())
    else:
        stem = clean or slug_kebab

    return f"{stem}.md"


def resolve_destination(
    topic: str,
    profile: dict[str, Any],
    search_results: dict[str, Any],
    explicit_folder: str | None = None,
    keywords: list[str] | None = None,
) -> dict[str, Any]:
    """Rank candidate folders for a topic and return destination with confidence and evidence."""
    folders_meta: dict[str, Any] = profile.get("folders", {})
    plugins = profile.get("plugins", {})
    folder_templates: dict[str, str] = plugins.get("folder_templates", {})
    mocs = profile.get("mocs", [])

    if explicit_folder is not None:
        clean_f = explicit_folder.strip().strip("/")
        f_info = folders_meta.get(clean_f or ".", {})
        naming = f_info.get("naming_convention", "unknown")
        if naming == "unknown":
            naming = profile.get("naming_convention", {}).get("primary", "title_case")
        return {
            "recommended_folder": clean_f,
            "confidence": "high",
            "needs_confirmation": False,
            "evidence": ["Explicitly specified destination folder"],
            "naming_convention": naming,
            "candidates": [
                {
                    "folder": clean_f,
                    "score": 100.0,
                    "confidence": "high",
                    "evidence": ["Explicitly specified destination folder"],
                }
            ],
        }

    topic_tokens = set(tokenize(topic))
    if keywords:
        for kw in keywords:
            topic_tokens.update(tokenize(kw))

    # Group search result scores by folder
    folder_rel_scores: dict[str, float] = defaultdict(float)
    folder_rel_notes: dict[str, list[str]] = defaultdict(list)
    for res in search_results.get("results", []):
        f = res.get("folder", "")
        folder_rel_scores[f] += float(res.get("score", 0.0))
        folder_rel_notes[f].append(res.get("title", res.get("stem", "")))

    candidates: list[dict[str, Any]] = []
    for folder_key, finfo in folders_meta.items():
        folder_path = finfo.get("path", "")
        role = finfo.get("role", "knowledge")
        if role in NON_CONTENT_ROLES:
            continue

        score = 0.0
        evidence: list[str] = []

        # 1. Related notes in this folder (strongest signal)
        rel_score = folder_rel_scores.get(folder_path, 0.0)
        if rel_score > 0:
            boost = min(28.0, rel_score * 0.9)
            score += boost
            sample_titles = ", ".join(folder_rel_notes[folder_path][:3])
            evidence.append(f"Contains related notes: {sample_titles}")

        # 2. Folder taxonomy / path token overlap
        path_tokens = set(tokenize(folder_path.replace("/", " ")))
        leaf_tokens = set(tokenize(folder_path.split("/")[-1])) if folder_path else set()
        path_overlap = topic_tokens & path_tokens
        leaf_overlap = topic_tokens & leaf_tokens
        if path_overlap:
            score += 10.0 * len(path_overlap) + (4.0 * len(leaf_overlap))
            evidence.append(f"Folder taxonomy matches: {', '.join(sorted(path_overlap))}")

        # 3. Existing tag patterns inside folder
        folder_tag_tokens: set[str] = set()
        for t in finfo.get("top_tags", []):
            folder_tag_tokens.update(tokenize(t))
        tag_overlap = topic_tokens & folder_tag_tokens
        if tag_overlap:
            score += 5.0 * min(3, len(tag_overlap))
            evidence.append(f"Matching folder tags ({', '.join(finfo.get('top_tags', [])[:3])})")

        # 4. Associated template or Dataview queried folder
        if folder_path and folder_path in folder_templates:
            score += 2.5
            evidence.append(f"Has configured folder template: {folder_templates[folder_path]}")
        dv_folders = plugins.get("conventions", {}).get("dataview_queried_folders", [])
        if folder_path and any(folder_path == df or folder_path.startswith(df + "/") for df in dv_folders):
            score += 2.0
            evidence.append("Referenced by Dataview query")

        # 5. MOC hub connection
        for moc in mocs:
            moc_folder = moc.get("folder", "")
            if (
                moc_folder == folder_path
                or (moc_folder and folder_path.startswith(moc_folder + "/"))
                or (folder_path and folder_path.split("/")[0].lower() in moc.get("title", "").lower())
            ):
                score += 2.5
                evidence.append(f"Covered by MOC: {moc.get('title')}")
                break

        # 6. Role adjustment
        if role in ("knowledge", "zettelkasten"):
            score += 2.0
        elif role == "inbox":
            score -= 2.0
        elif role == "empty_or_container":
            score -= 1.0

        # Prefer deeper specific subfolder when parent has zero direct files
        if finfo.get("file_count", 0) == 0 and "/" not in folder_path:
            score -= 2.0

        if score > 0 or folder_path == "":
            candidates.append(
                {
                    "folder": folder_path,
                    "role": role,
                    "score": round(score, 2),
                    "evidence": evidence or ["Vault root fallback"],
                    "naming_convention": finfo.get("naming_convention", "unknown"),
                }
            )

    if not candidates:
        fallback_naming = profile.get("naming_convention", {}).get("primary", "title_case")
        return {
            "recommended_folder": "",
            "confidence": "low",
            "needs_confirmation": True,
            "evidence": ["No clear existing knowledge folder matched; defaulting to vault root"],
            "naming_convention": fallback_naming,
            "candidates": [],
        }

    candidates.sort(key=lambda c: c["score"], reverse=True)
    top = candidates[0]
    second_score = candidates[1]["score"] if len(candidates) > 1 else 0.0
    margin = top["score"] - second_score

    if top["score"] >= 14.0 and margin >= 4.0:
        confidence = "high"
    elif top["score"] >= 6.0 and margin >= 1.5:
        confidence = "medium"
    else:
        confidence = "low"

    for c in candidates:
        c["confidence"] = confidence if c is top else ("medium" if c["score"] >= 6.0 else "low")

    naming = top["naming_convention"]
    if naming == "unknown":
        naming = profile.get("naming_convention", {}).get("primary", "title_case")

    return {
        "recommended_folder": top["folder"],
        "confidence": confidence,
        "needs_confirmation": confidence == "low",
        "evidence": top["evidence"],
        "naming_convention": naming,
        "candidates": candidates[:5],
    }
