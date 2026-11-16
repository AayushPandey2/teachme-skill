"""Incremental searchable vault knowledge index and deterministic retrieval."""

from __future__ import annotations

from collections import Counter, defaultdict
import json
import math
from pathlib import Path
import re
from typing import Any

from .markdown_utils import (
    analyze_markdown_body,
    extract_aliases,
    extract_frontmatter_tags,
    parse_frontmatter_tolerant,
)
from .models import (
    atomic_write_text,
    read_text_safe,
    resolve_state_dir,
    safe_iter_files,
    sha256_text,
    utc_now_iso,
)

MAX_INDEX_BYTES = 131072
STOP_WORDS = frozenset(
    {
        "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "has",
        "he", "in", "is", "it", "its", "of", "on", "or", "that", "the", "to",
        "was", "were", "will", "with", "this", "these", "those", "we", "you",
        "can", "into", "using", "use", "used", "about", "what", "how", "why",
    }
)


def _add_token_variants(tok: str, out: list[str]) -> None:
    if len(tok) <= 1 or tok in STOP_WORDS:
        return
    out.append(tok)
    if len(tok) > 4 and tok.endswith("s") and not tok.endswith(("ss", "is", "us")):
        stem = tok[:-2] if tok.endswith("es") and len(tok) > 5 and tok[-3] in "sxzh" else tok[:-1]
        if len(stem) > 2 and stem not in STOP_WORDS and stem != tok:
            out.append(stem)


def tokenize(text: str) -> list[str]:
    """Tokenize text into lowercase alphanumeric terms excluding stopwords."""
    tokens = re.findall(r"[a-z0-9]+(?:[-_][a-z0-9]+)*", text.lower())
    out: list[str] = []
    for tok in tokens:
        if len(tok) <= 1 or tok in STOP_WORDS:
            continue
        _add_token_variants(tok, out)
        if "-" in tok or "_" in tok:
            for sub in re.split(r"[-_]", tok):
                _add_token_variants(sub, out)
    return out


def _extract_lead_summary(body: str, max_chars: int = 280) -> str:
    """Extract first non-heading prose lines as a concise summary snippet."""
    chunks: list[str] = []
    in_fence = False
    for line in body.splitlines():
        s = line.strip()
        if s.startswith("```") or s.startswith("~~~"):
            in_fence = not in_fence
            continue
        if in_fence or not s or s.startswith("#") or s.startswith(">"):
            continue
        chunks.append(s)
        if sum(len(c) for c in chunks) >= max_chars:
            break
    summary = " ".join(chunks)
    if len(summary) > max_chars:
        summary = summary[: max_chars - 3].rstrip() + "..."
    return summary


def _build_doc_entry(path: Path, vault_root: Path) -> dict[str, Any]:
    rel = path.relative_to(vault_root).as_posix()
    folder = path.parent.relative_to(vault_root).as_posix()
    if folder == ".":
        folder = ""
    st = path.stat()
    raw = read_text_safe(path, max_bytes=MAX_INDEX_BYTES)
    fm = parse_frontmatter_tolerant(raw)
    meta = fm["meta"]
    body = fm["body"]
    info = analyze_markdown_body(body)

    headings_text = [h["text"] for h in info["headings"]]
    title = str(meta.get("title") or (headings_text[0] if headings_text else path.stem)).strip()
    aliases = extract_aliases(meta)
    tags = list(dict.fromkeys(extract_frontmatter_tags(meta) + info["inline_tags"]))

    # Weighted term counts for deterministic retrieval
    tf_title = Counter(tokenize(f"{path.stem} {title} {' '.join(aliases)}"))
    tf_struct = Counter(tokenize(f"{' '.join(headings_text)} {' '.join(tags)} {folder.replace('/', ' ')}"))
    tf_body = Counter(tokenize(body))

    combined_tf: dict[str, int] = {}
    for term in set(tf_title) | set(tf_struct) | set(tf_body):
        score_w = tf_title[term] * 5 + tf_struct[term] * 3 + min(tf_body[term], 20)
        if score_w > 0:
            combined_tf[term] = score_w

    # Keep top 80 weighted terms to keep index compact on huge vaults
    top_terms = dict(sorted(combined_tf.items(), key=lambda kv: kv[1], reverse=True)[:80])

    outgoing = []
    for wl in info["wikilinks"]:
        note = wl["note"]
        if note:
            outgoing.append(
                {
                    "target": note,
                    "anchor": wl["anchor"],
                    "alias": wl["alias"],
                    "embed": wl["embed"],
                }
            )

    prop_summary = {
        k: v for k, v in meta.items()
        if k not in ("tags", "tag", "aliases", "alias") and not isinstance(v, dict)
    }

    return {
        "rel_path": rel,
        "folder": folder,
        "stem": path.stem,
        "title": title,
        "aliases": aliases,
        "tags": tags,
        "headings": headings_text[:40],
        "heading_slugs": [h["slug"] for h in info["headings"][:40]],
        "block_ids": info["block_ids"][:40],
        "properties": prop_summary,
        "outgoing_links": outgoing,
        "incoming_count": 0,
        "word_count": info["word_count"],
        "summary": _extract_lead_summary(body),
        "mtime_ns": st.st_mtime_ns,
        "size": st.st_size,
        "content_hash": sha256_text(raw)[:16],
        "terms": top_terms,
    }


def _resolve_link_targets(docs: dict[str, dict[str, Any]]) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    """Build stem/alias lookup tables and populate incoming backlink counts."""
    stem_map: dict[str, list[str]] = defaultdict(list)
    alias_map: dict[str, list[str]] = defaultdict(list)

    for rel, doc in docs.items():
        doc["incoming_count"] = 0
        stem_map[doc["stem"].lower()].append(rel)
        if doc["title"].lower() != doc["stem"].lower():
            alias_map[doc["title"].lower()].append(rel)
        for al in doc.get("aliases", []):
            alias_map[al.lower()].append(rel)

    for rel, doc in docs.items():
        seen_targets: set[str] = set()
        for link in doc.get("outgoing_links", []):
            raw_target = link["target"].strip()
            clean = raw_target[:-3] if raw_target.endswith(".md") else raw_target
            candidate_path = f"{clean}.md"
            resolved: str | None = None
            if candidate_path in docs:
                resolved = candidate_path
            else:
                base = Path(clean).name.lower()
                matches = stem_map.get(base, [])
                if len(matches) == 1:
                    resolved = matches[0]
                elif not matches:
                    al_matches = alias_map.get(base, [])
                    if len(al_matches) == 1:
                        resolved = al_matches[0]
            if resolved and resolved != rel and resolved not in seen_targets:
                seen_targets.add(resolved)
                docs[resolved]["incoming_count"] += 1

    return dict(stem_map), dict(alias_map)


def build_or_update_index(
    vault_root: Path,
    full: bool = False,
    state_dir: Path | None = None,
) -> dict[str, Any]:
    """Build or incrementally refresh the searchable vault knowledge index."""
    root = vault_root.resolve()
    sdir = state_dir or resolve_state_dir(root)
    index_path = sdir / "index.json"

    old_docs: dict[str, dict[str, Any]] = {}
    if not full and index_path.is_file():
        try:
            old_data = json.loads(read_text_safe(index_path))
            if old_data.get("vault_path") == str(root):
                old_docs = old_data.get("docs", {})
        except (OSError, json.JSONDecodeError):
            old_docs = {}

    old_by_hash: dict[str, str] = {}
    for old_rel, old_doc in old_docs.items():
        ch = old_doc.get("content_hash")
        if ch:
            old_by_hash[ch] = old_rel

    new_docs: dict[str, dict[str, Any]] = {}
    renamed_detected: list[dict[str, str]] = []
    added = 0
    reused = 0
    updated = 0

    for p in safe_iter_files(root, extensions=(".md",)):
        if p.name.lower().endswith(".excalidraw.md"):
            continue
        rel = p.relative_to(root).as_posix()
        st = p.stat()
        cached = old_docs.get(rel)
        if cached and cached.get("mtime_ns") == st.st_mtime_ns and cached.get("size") == st.st_size:
            new_docs[rel] = cached
            reused += 1
        else:
            doc = _build_doc_entry(p, root)
            new_docs[rel] = doc
            if rel in old_docs:
                updated += 1
            else:
                added += 1
                ch = doc.get("content_hash", "")
                prev_rel = old_by_hash.get(ch)
                if prev_rel and prev_rel not in new_docs and not (root / prev_rel).exists():
                    renamed_detected.append({"from": prev_rel, "to": rel})

    removed = len([r for r in old_docs if r not in new_docs])
    stem_map, alias_map = _resolve_link_targets(new_docs)

    # Document frequencies for IDF weighting
    df_counts: Counter[str] = Counter()
    for doc in new_docs.values():
        df_counts.update(doc.get("terms", {}).keys())

    ambiguous_titles = {
        k: v for k, v in stem_map.items() if len(v) > 1
    }
    alias_collisions = {
        k: v for k, v in alias_map.items() if len(v) > 1
    }

    index_obj: dict[str, Any] = {
        "schema_version": 1,
        "vault_path": str(root),
        "indexed_at": utc_now_iso(),
        "doc_count": len(new_docs),
        "stats": {
            "added": added,
            "updated": updated,
            "reused": reused,
            "removed": removed,
            "renamed_detected": renamed_detected,
        },
        "ambiguous_titles": ambiguous_titles,
        "alias_collisions": alias_collisions,
        "df": dict(df_counts),
        "docs": new_docs,
    }

    sdir.mkdir(parents=True, exist_ok=True)
    atomic_write_text(index_path, json.dumps(index_obj, indent=2, ensure_ascii=False) + "\n")
    return index_obj


def load_or_build_index(
    vault_root: Path,
    refresh: bool = False,
    state_dir: Path | None = None,
) -> dict[str, Any]:
    """Load index.json if present or build/update incrementally."""
    root = vault_root.resolve()
    sdir = state_dir or resolve_state_dir(root)
    index_path = sdir / "index.json"
    if not refresh and index_path.is_file():
        try:
            data = json.loads(read_text_safe(index_path))
            if isinstance(data, dict) and data.get("vault_path") == str(root):
                return data
        except (OSError, json.JSONDecodeError):
            pass
    return build_or_update_index(root, full=refresh, state_dir=sdir)


def search_vault(
    vault_root: Path,
    query: str,
    limit: int = 10,
    index: dict[str, Any] | None = None,
    exclude_roles: set[str] | None = None,
    profile: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Retrieve ranked relevant notes for a topic query using deterministic BM25-weighted scoring."""
    idx = index if index is not None else load_or_build_index(vault_root)
    docs: dict[str, dict[str, Any]] = idx.get("docs", {})
    df_map: dict[str, int] = idx.get("df", {})
    n_docs = max(1, len(docs))

    q_clean = query.strip().lower()
    q_tokens = tokenize(query)
    q_token_set = set(q_tokens)
    folders_meta = (profile or {}).get("folders", {})

    results: list[dict[str, Any]] = []
    for rel, doc in docs.items():
        folder_key = doc.get("folder") or "."
        f_role = folders_meta.get(folder_key, {}).get("role", "")
        if exclude_roles and f_role in exclude_roles:
            continue

        score = 0.0
        reasons: list[str] = []

        stem_low = doc.get("stem", "").lower()
        title_low = doc.get("title", "").lower()
        aliases_low = [a.lower() for a in doc.get("aliases", [])]

        is_exact_match = False
        if q_clean and (q_clean == stem_low or q_clean == title_low or q_clean in aliases_low):
            score += 25.0
            reasons.append("Exact title/alias match")
            is_exact_match = True
        elif q_clean and (q_clean in title_low or q_clean in stem_low or any(q_clean in a for a in aliases_low)):
            score += 12.0
            reasons.append("Partial title/alias phrase match")

        # Heading & tag phrase matches
        heading_matches = [
            h for h in doc.get("headings", [])
            if q_clean in h.lower() or len(q_token_set & set(tokenize(h))) >= max(1, len(q_token_set) // 2)
        ]
        if heading_matches:
            score += 4.5 * min(3, len(heading_matches))
            reasons.append(f"Matching headings: {', '.join(heading_matches[:3])}")

        tag_matches = [
            t for t in doc.get("tags", [])
            if q_clean.replace(" ", "-") in t.lower() or bool(q_token_set & set(tokenize(t)))
        ]
        if tag_matches:
            score += 3.5 * min(3, len(tag_matches))
            reasons.append(f"Matching tags: {', '.join(tag_matches[:3])}")

        # Weighted term IDF scoring
        doc_terms: dict[str, int] = doc.get("terms", {})
        matched_terms: list[str] = []
        for tok in q_token_set:
            tf = doc_terms.get(tok, 0)
            if tf > 0:
                df = df_map.get(tok, 1)
                idf = math.log(1.0 + (n_docs - df + 0.5) / (df + 0.5))
                score += (1.0 + math.log(1.0 + tf)) * max(0.5, idf)
                matched_terms.append(tok)

        if matched_terms and not reasons:
            reasons.append(f"Keyword overlap: {', '.join(sorted(matched_terms)[:5])}")

        # Small centrality boost for well-linked notes
        inc = doc.get("incoming_count", 0)
        if score > 0 and inc > 0:
            score += min(3.0, math.log1p(inc))

        if score > 0.5:
            results.append(
                {
                    "rel_path": rel,
                    "folder": doc.get("folder", ""),
                    "title": doc.get("title", doc.get("stem")),
                    "stem": doc.get("stem"),
                    "aliases": doc.get("aliases", []),
                    "tags": doc.get("tags", []),
                    "headings": doc.get("headings", [])[:10],
                    "incoming_count": inc,
                    "outgoing_count": len(doc.get("outgoing_links", [])),
                    "word_count": doc.get("word_count", 0),
                    "summary": doc.get("summary", ""),
                    "exact_title_match": is_exact_match,
                    "score": round(score, 2),
                    "reasons": reasons,
                }
            )

    results.sort(key=lambda r: (r["score"], r["incoming_count"]), reverse=True)
    return {
        "query": query,
        "total_matches": len(results),
        "results": results[:limit],
        "ambiguous_titles": idx.get("ambiguous_titles", {}),
    }


def resolve_safe_wikilink(
    target_stem_or_rel: str,
    index: dict[str, Any],
    preferred_style: str = "wikilink",
    alias: str = "",
) -> str | None:
    """Resolve an existing note in index into a verified Obsidian wikilink, or None if missing."""
    docs: dict[str, dict[str, Any]] = index.get("docs", {})
    ambiguous: dict[str, list[str]] = index.get("ambiguous_titles", {})

    # Check exact relative path
    cand_rel = target_stem_or_rel if target_stem_or_rel.endswith(".md") else f"{target_stem_or_rel}.md"
    doc = docs.get(cand_rel)
    if doc is None:
        # Match by stem
        matches = [r for r, d in docs.items() if d["stem"].lower() == target_stem_or_rel.lower()]
        if len(matches) == 1:
            cand_rel = matches[0]
            doc = docs[cand_rel]
        elif len(matches) > 1:
            cand_rel = matches[0]
            doc = docs[cand_rel]
        else:
            return None

    stem = doc["stem"]
    no_ext = cand_rel[:-3] if cand_rel.endswith(".md") else cand_rel
    is_ambiguous = stem.lower() in ambiguous
    use_folder = is_ambiguous or preferred_style == "wikilink_folder_qualified"
    link_target = no_ext if (use_folder and "/" in no_ext) else stem

    display = alias or (doc["title"] if doc["title"] != stem and is_ambiguous else "")
    if display and display != link_target:
        return f"[[{link_target}|{display}]]"
    return f"[[{link_target}]]"
