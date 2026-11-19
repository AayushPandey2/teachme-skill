"""Incremental searchable vault knowledge index and deterministic retrieval."""

from __future__ import annotations

from collections import Counter, defaultdict
import json
import math
import os
from pathlib import Path
import re
from typing import Any

from .markdown_utils import (
    BLOCK_ID_RE,
    FENCE_RE,
    HEADING_RE,
    TASK_RE,
    WIKILINK_RE,
    analyze_markdown_body,
    extract_aliases,
    extract_frontmatter_links,
    extract_frontmatter_tags,
    heading_slug,
    is_workflow_or_status_tag,
    normalize_tag,
    parse_frontmatter_tolerant,
    parse_wikilink_parts,
)
from .models import (
    atomic_write_text,
    expand_path,
    get_active_vault_entry,
    is_within_root,
    load_config,
    read_text_safe,
    resolve_state_dir,
    safe_iter_files,
    sha256_text,
    utc_now_iso,
)

MAX_INDEX_BYTES = 131072
ATTACHMENT_EXTENSIONS = frozenset(
    {
        ".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".bmp", ".ico",
        ".pdf", ".mp3", ".mp4", ".wav", ".ogg", ".webm", ".mov",
        ".csv", ".tsv", ".json", ".yaml", ".yml", ".xml", ".txt",
        ".canvas", ".base", ".excalidraw",
    }
)
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
    """Tokenize text into lowercase alphanumeric/Unicode terms excluding stopwords."""
    tokens = re.findall(r"[^\W_]+(?:[-_][^\W_]+)*", text.lower())
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
    all_files: list[Path] | None = None,
    ignore_write_errors: bool = False,
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
    assets: list[str] = []
    renamed_detected: list[dict[str, str]] = []
    added = 0
    reused = 0
    updated = 0

    iter_source = all_files if all_files is not None else safe_iter_files(root, extensions=())
    for p in iter_source:
        name_low = p.name.lower()
        if name_low.endswith(".excalidraw.md"):
            assets.append(p.relative_to(root).as_posix())
            continue
        if not name_low.endswith(".md"):
            if p.suffix.lower() in ATTACHMENT_EXTENSIONS:
                assets.append(p.relative_to(root).as_posix())
            continue
        rel = p.relative_to(root).as_posix()
        try:
            st = p.stat()
        except OSError:
            continue
        cached = old_docs.get(rel)
        if cached and cached.get("mtime_ns") == st.st_mtime_ns and cached.get("size") == st.st_size:
            new_docs[rel] = cached
            reused += 1
        else:
            try:
                doc = _build_doc_entry(p, root)
            except OSError:
                continue
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

    persisted = True
    try:
        sdir.mkdir(parents=True, exist_ok=True)
    except OSError:
        if not ignore_write_errors:
            raise
        persisted = False

    index_obj: dict[str, Any] = {
        "schema_version": 2,
        "vault_path": str(root),
        "indexed_at": utc_now_iso(),
        "doc_count": len(new_docs),
        "stats": {
            "added": added,
            "updated": updated,
            "reused": reused,
            "removed": removed,
            "renamed_detected": renamed_detected,
            "cache_hit": False,
            "persisted": persisted,
        },
        "ambiguous_titles": ambiguous_titles,
        "alias_collisions": alias_collisions,
        "assets": assets,
        "df": dict(df_counts),
        "docs": new_docs,
    }

    if persisted:
        try:
            atomic_write_text(index_path, json.dumps(index_obj, indent=2, ensure_ascii=False) + "\n")
        except OSError:
            if not ignore_write_errors:
                raise
            index_obj["stats"]["persisted"] = False
    return index_obj


def _is_index_stale(
    root: Path,
    cached_idx: dict[str, Any],
    note_files: list[Path] | None = None,
) -> bool:
    """Fast check for added, deleted, renamed, or modified Markdown files."""
    if cached_idx.get("schema_version") != 2:
        return True
    docs = cached_idx.get("docs", {})
    if not isinstance(docs, dict):
        return True
    current_files = (
        note_files
        if note_files is not None
        else [
            p for p in safe_iter_files(root, extensions=(".md",))
            if not p.name.lower().endswith(".excalidraw.md")
        ]
    )
    if len(current_files) != len(docs):
        return True
    for p in current_files:
        rel = p.relative_to(root).as_posix()
        doc = docs.get(rel)
        if not isinstance(doc, dict):
            return True
        try:
            st = p.stat()
        except OSError:
            return True
        if doc.get("mtime_ns") != st.st_mtime_ns or doc.get("size") != st.st_size:
            return True
    return False


def load_or_build_index(
    vault_root: Path,
    refresh: bool = False,
    state_dir: Path | None = None,
    note_files: list[Path] | None = None,
    ignore_write_errors: bool = False,
) -> dict[str, Any]:
    """Load index.json if present and fresh, else build/update incrementally."""
    root = vault_root.resolve()
    sdir = state_dir or resolve_state_dir(root)
    index_path = sdir / "index.json"
    if not refresh and index_path.is_file():
        try:
            data = json.loads(read_text_safe(index_path))
            if isinstance(data, dict) and data.get("vault_path") == str(root):
                if not _is_index_stale(root, data, note_files=note_files):
                    stats = dict(data.get("stats") or {})
                    stats["cache_hit"] = True
                    data["stats"] = stats
                    return data
        except (OSError, json.JSONDecodeError):
            pass
    return build_or_update_index(
        root,
        full=refresh,
        state_dir=sdir,
        ignore_write_errors=ignore_write_errors,
    )


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

    results.sort(key=lambda r: (-r["score"], -r["incoming_count"], r["rel_path"]))
    return {
        "query": query,
        "total_matches": len(results),
        "results": results[:limit],
        "ambiguous_titles": idx.get("ambiguous_titles", {}),
    }


def is_attachment_target(raw_target: str) -> bool:
    """Return True if a wikilink target points to a non-Markdown or Excalidraw attachment."""
    clean = raw_target.split("|", 1)[0].split("#", 1)[0].strip().lower()
    if clean.endswith(".excalidraw.md"):
        return True
    suffix = Path(clean).suffix
    return bool(suffix and suffix != ".md" and suffix in ATTACHMENT_EXTENSIONS)


def resolve_link_to_rel_path(
    raw_link_target: str,
    index: dict[str, Any],
    extra_rel_paths: set[str] | None = None,
    vault_root: Path | None = None,
) -> dict[str, Any]:
    """Resolve a wikilink/Markdown link target (without alias) to vault rel_path & ambiguity info."""
    docs: dict[str, dict[str, Any]] = index.get("docs", {})
    assets: list[str] = index.get("assets", [])
    note_part = raw_link_target.split("|", 1)[0].strip()
    anchor = ""
    if "#" in note_part:
        note_part, anchor = note_part.split("#", 1)
        note_part = note_part.strip()
        anchor = anchor.strip()

    if not note_part:
        return {"resolved": None, "ambiguous": False, "anchor": anchor, "candidates": [], "is_attachment": False}

    if is_attachment_target(note_part):
        np_low = note_part.lstrip("/").lower()
        exact_asset = [a for a in assets if a.lower() == np_low]
        if len(exact_asset) == 1:
            return {"resolved": exact_asset[0], "ambiguous": False, "anchor": anchor, "candidates": exact_asset, "is_attachment": True}
        base_asset = Path(np_low).name
        name_matches = [a for a in assets if Path(a).name.lower() == base_asset]
        if len(name_matches) == 1:
            return {"resolved": name_matches[0], "ambiguous": False, "anchor": anchor, "candidates": name_matches, "is_attachment": True}
        if len(name_matches) > 1:
            return {"resolved": None, "ambiguous": True, "anchor": anchor, "candidates": name_matches, "is_attachment": True}
        # Fallback check on disk if vault_root is provided (e.g. newly dropped attachment before reindex)
        if vault_root is not None:
            cand_disk = (vault_root / note_part.lstrip("/")).resolve()
            if cand_disk.is_file():
                try:
                    rel_a = cand_disk.relative_to(vault_root.resolve()).as_posix()
                    return {"resolved": rel_a, "ambiguous": False, "anchor": anchor, "candidates": [rel_a], "is_attachment": True}
                except ValueError:
                    pass
        return {"resolved": None, "ambiguous": False, "anchor": anchor, "candidates": [], "is_attachment": True}

    clean = note_part[:-3] if note_part.endswith(".md") else note_part
    cand_rel = f"{clean}.md"
    if cand_rel in docs or (extra_rel_paths and cand_rel in extra_rel_paths):
        return {"resolved": cand_rel, "ambiguous": False, "anchor": anchor, "candidates": [cand_rel], "is_attachment": False}

    # Case-insensitive exact relpath match
    cand_low = cand_rel.lower()
    for rel in docs:
        if rel.lower() == cand_low:
            return {"resolved": rel, "ambiguous": False, "anchor": anchor, "candidates": [rel], "is_attachment": False}
    if extra_rel_paths:
        for rel in extra_rel_paths:
            if rel.lower() == cand_low:
                return {"resolved": rel, "ambiguous": False, "anchor": anchor, "candidates": [rel], "is_attachment": False}

    base_low = Path(clean).name.lower()
    stem_matches = [r for r, d in docs.items() if d.get("stem", "").lower() == base_low]
    if extra_rel_paths:
        for er in extra_rel_paths:
            if Path(er).stem.lower() == base_low and er not in stem_matches:
                stem_matches.append(er)

    if len(stem_matches) == 1:
        return {"resolved": stem_matches[0], "ambiguous": False, "anchor": anchor, "candidates": stem_matches, "is_attachment": False}
    if len(stem_matches) > 1:
        return {"resolved": None, "ambiguous": True, "anchor": anchor, "candidates": stem_matches, "is_attachment": False}

    # Fallback: title / alias match
    alias_matches = [
        r for r, d in docs.items()
        if d.get("title", "").lower() == base_low
        or any(str(a).lower() == base_low for a in d.get("aliases", []))
    ]
    if len(alias_matches) == 1:
        return {"resolved": alias_matches[0], "ambiguous": False, "anchor": anchor, "candidates": alias_matches, "is_attachment": False}
    if len(alias_matches) > 1:
        return {"resolved": None, "ambiguous": True, "anchor": anchor, "candidates": alias_matches, "is_attachment": False}

    return {"resolved": None, "ambiguous": False, "anchor": anchor, "candidates": [], "is_attachment": False}


def links_equivalent(
    link_a: str,
    link_b: str,
    index: dict[str, Any],
    extra_rel_paths: set[str] | None = None,
) -> bool:
    """Return True if two link targets (even with aliases or path spellings) refer to the same note."""
    a_clean = link_a.strip()
    b_clean = link_b.strip()
    if a_clean.startswith("[[") and a_clean.endswith("]]"):
        a_clean = a_clean[2:-2]
    if b_clean.startswith("[[") and b_clean.endswith("]]"):
        b_clean = b_clean[2:-2]

    res_a = resolve_link_to_rel_path(a_clean, index, extra_rel_paths=extra_rel_paths)
    res_b = resolve_link_to_rel_path(b_clean, index, extra_rel_paths=extra_rel_paths)
    if res_a["resolved"] and res_b["resolved"]:
        return res_a["resolved"].lower() == res_b["resolved"].lower()

    # Fallback normalized stem comparison when not yet indexed
    na = Path(a_clean.split("|", 1)[0].split("#", 1)[0].strip()).stem.lower()
    nb = Path(b_clean.split("|", 1)[0].split("#", 1)[0].strip()).stem.lower()
    return bool(na and na == nb)


def resolve_safe_wikilink(
    target_stem_or_rel: str,
    index: dict[str, Any],
    preferred_style: str = "wikilink",
    alias: str = "",
    anchor: str = "",
) -> str | None:
    """Resolve an existing note in index into a verified Obsidian wikilink, or None if missing."""
    docs: dict[str, dict[str, Any]] = index.get("docs", {})
    ambiguous: dict[str, list[str]] = index.get("ambiguous_titles", {})

    raw_part = target_stem_or_rel.strip()
    parsed_anchor = anchor.strip()
    if "#" in raw_part and not parsed_anchor:
        raw_part, parsed_anchor = raw_part.split("#", 1)
        raw_part = raw_part.strip()
        parsed_anchor = parsed_anchor.strip()

    res = resolve_link_to_rel_path(raw_part, index)
    cand_rel = res["resolved"]
    if cand_rel is None:
        if res["ambiguous"] and res["candidates"]:
            cand_rel = res["candidates"][0]
        else:
            return None

    doc = docs.get(cand_rel)
    if doc is None:
        return None

    stem = doc["stem"]
    no_ext = cand_rel[:-3] if cand_rel.endswith(".md") else cand_rel
    is_ambiguous = stem.lower() in ambiguous or res["ambiguous"]
    use_folder = is_ambiguous or preferred_style == "wikilink_folder_qualified"
    link_target = no_ext if (use_folder and "/" in no_ext) else stem
    if parsed_anchor:
        link_target = f"{link_target}#{parsed_anchor}"

    display = alias or (doc["title"] if doc["title"] != stem and is_ambiguous else "")
    if display and display != link_target:
        return f"[[{link_target}|{display}]]"
    return f"[[{link_target}]]"


GENERIC_OBJECTIVE_VERBS = frozenset(
    {
        "explain", "understand", "compute", "define", "analyze", "analyse",
        "identify", "describe", "apply", "compare", "learn", "interpret",
        "calculate", "derive", "evaluate", "demonstrate", "verify", "predict",
        "recognize", "recognise", "state", "show", "solve", "distinguish",
    }
)
INCOMPLETE_STATUSES = frozenset({"draft", "wip", "stub", "todo", "incomplete", "seedling"})
BOILERPLATE_HEADINGS = frozenset(
    {"references", "links", "related", "see also", "sources", "bibliography", "backlinks", "notes"}
)
PREREQ_FM_KEYS = ("depends_on", "prerequisites", "prerequisite", "prereqs", "prereq", "requires", "up", "parent", "moc")
PLACEHOLDER_RE = re.compile(
    r"^(?:todo|tbd|wip|fixme|coming\s+soon|placeholder|stub|fill\s+in|none|\.{3,})[\s:.\-!]*$",
    re.IGNORECASE,
)


def _stem_token(tok: str) -> str:
    if len(tok) > 4 and tok.endswith("s") and not tok.endswith(("ss", "is", "us")):
        return tok[:-2] if tok.endswith("es") and len(tok) > 5 and tok[-3] in "sxzh" else tok[:-1]
    return tok


def _base_terms(text: str, *, extra_stop: frozenset[str] | set[str] = frozenset()) -> list[str]:
    out: list[str] = []
    for raw in re.findall(r"[^\W_]+", text.lower()):
        if raw in STOP_WORDS or raw in extra_stop or raw in {"i", "vs", "versus"}:
            continue
        if len(raw) == 1 and not raw.isalpha():
            continue
        out.append(_stem_token(raw))
    return out


def _term_set(text: str, *, extra_stop: frozenset[str] | set[str] = frozenset()) -> set[str]:
    terms = set(_base_terms(text, extra_stop=extra_stop))
    for t in tokenize(text):
        if t not in extra_stop:
            terms.add(t)
    return terms


def _truncate_text(text: str, max_chars: int) -> tuple[str, bool]:
    if max_chars <= 0 or len(text) <= max_chars:
        return text, False
    cut = text[: max(0, max_chars - 16)].rstrip()
    nl = cut.rfind("\n")
    if nl > len(cut) // 2:
        cut = cut[:nl].rstrip()
    return cut + "\n...[truncated]", True


def extract_markdown_sections(text: str, *, fallback_title: str = "") -> dict[str, Any]:
    """Parse frontmatter and split a Markdown note into structured sections safely."""
    fm = parse_frontmatter_tolerant(text)
    meta = fm["meta"]
    body = fm["body"]
    body_start_line = int(fm.get("body_start_line") or 0)

    aliases = extract_aliases(meta)
    fm_tags = extract_frontmatter_tags(meta)
    fm_links = extract_frontmatter_links(meta)
    info = analyze_markdown_body(body)
    tags = list(dict.fromkeys(fm_tags + info["inline_tags"]))

    first_h = info["headings"][0]["text"] if info["headings"] else ""
    title = str(meta.get("title") or first_h or fallback_title).strip()

    lines = body.splitlines()
    raw_sections: list[dict[str, Any]] = []
    heading_stack: list[tuple[int, str]] = []

    cur_heading = ""
    cur_level = 0
    cur_path: list[str] = []
    cur_start = 0
    cur_lines: list[str] = []

    in_fence = False
    fence_char = ""
    in_display_math = False

    def _flush_section(end_idx: int) -> None:
        if not cur_lines and not cur_heading:
            return
        # Trim leading/trailing empty lines while keeping heading
        trimmed = list(cur_lines)
        while trimmed and not trimmed[0].strip():
            trimmed.pop(0)
        while trimmed and not trimmed[-1].strip():
            trimmed.pop()
        if not trimmed:
            return
        sec_text = "\n".join(trimmed)

        # Analyze section substance (prose vs stubs/todos/pure link lists)
        sec_in_fence = False
        sec_fence_ch = ""
        sec_in_math = False
        has_code = False
        has_eq = False
        prose_words = 0
        task_lines = 0
        pure_link_lines = 0
        non_heading_lines: list[str] = []
        sec_wikilinks: list[dict[str, Any]] = []
        sec_blocks: list[str] = []

        for ln_idx, ln in enumerate(trimmed):
            if ln_idx == 0 and cur_heading and HEADING_RE.match(ln):
                continue
            fm_m = FENCE_RE.match(ln)
            if fm_m:
                marker = fm_m.group(1)
                if not sec_in_fence:
                    sec_in_fence = True
                    sec_fence_ch = marker[0]
                    has_code = True
                elif marker[0] == sec_fence_ch:
                    sec_in_fence = False
                continue
            if sec_in_fence:
                prose_words += len(re.findall(r"\b\w+\b", ln))
                continue

            s = ln.strip()
            if not s or s.startswith("<!--") or re.fullmatch(r"[-*_]{3,}", s):
                continue
            if s.startswith("$$") and s.endswith("$$") and len(s) > 2:
                has_eq = True
                non_heading_lines.append(s)
                continue
            if s.count("$$") % 2 == 1:
                sec_in_math = not sec_in_math
                has_eq = True
                continue
            if sec_in_math:
                has_eq = True
                non_heading_lines.append(s)
                continue

            non_heading_lines.append(s)
            no_code = re.sub(r"`[^`\r\n]*`", "", ln)
            if re.search(r"(?<!\\)\$[^$\r\n]+?(?<!\\)\$", no_code):
                has_eq = True

            for wm in WIKILINK_RE.finditer(no_code):
                sec_wikilinks.append(parse_wikilink_parts(wm.group(2), is_embed=bool(wm.group(1))))
            bm = BLOCK_ID_RE.search(no_code)
            if bm:
                sec_blocks.append(bm.group(1))

            if TASK_RE.match(ln):
                task_lines += 1
                continue
            # Pure link-list bullet without annotation prose
            if re.match(r"^\s*[-*+]\s+(?:!\[\[[^\]]+\]\]|\[\[[^\]]+\]\]|\[[^\]]*\]\([^)]+\))\s*$", ln):
                pure_link_lines += 1
                continue

            clean_prose = re.sub(r"!\[\[[^\]]+\]\]", " ", s)
            clean_prose = re.sub(r"\[\[[^\]|]+\|([^\]]+)\]\]", r"\1", clean_prose)
            clean_prose = re.sub(r"\[\[([^\]]+)\]\]", r"\1", clean_prose)
            clean_prose = re.sub(r"\[([^\]]*)\]\([^)]+\)", r"\1", clean_prose)
            prose_words += len(re.findall(r"[^\W_]+", clean_prose))

        body_only = "\n".join(non_heading_lines).strip()
        is_placeholder = (not body_only) or bool(PLACEHOLDER_RE.match(body_only))
        effective_words = prose_words + (12 if has_eq else 0) + (15 if has_code else 0)
        is_stub = is_placeholder or (effective_words < 15)

        raw_sections.append(
            {
                "heading": cur_heading or (title or "Introduction"),
                "level": cur_level,
                "heading_path": list(cur_path) if cur_path else [title or "Introduction"],
                "anchor": heading_slug(cur_heading) if cur_heading else "",
                "start_line": body_start_line + cur_start + 1,
                "end_line": body_start_line + end_idx,
                "content": sec_text,
                "word_count": len(re.findall(r"[^\W_]+", body_only)),
                "prose_word_count": prose_words,
                "effective_words": effective_words,
                "has_equations": has_eq,
                "has_code": has_code,
                "task_lines": task_lines,
                "pure_link_lines": pure_link_lines,
                "is_placeholder": is_placeholder,
                "is_stub": is_stub,
                "wikilinks": sec_wikilinks,
                "block_ids": sec_blocks,
            }
        )

    for idx, line in enumerate(lines):
        fm_m = FENCE_RE.match(line)
        if fm_m:
            marker = fm_m.group(1)
            if not in_fence:
                in_fence = True
                fence_char = marker[0]
            elif marker[0] == fence_char:
                in_fence = False
            cur_lines.append(line)
            continue
        if in_fence:
            cur_lines.append(line)
            continue

        stripped = line.strip()
        if stripped.startswith("$$") and stripped.endswith("$$") and len(stripped) > 2:
            cur_lines.append(line)
            continue
        if stripped.count("$$") % 2 == 1:
            in_display_math = not in_display_math
            cur_lines.append(line)
            continue
        if in_display_math:
            cur_lines.append(line)
            continue

        hm = HEADING_RE.match(line)
        if hm:
            _flush_section(idx)
            level = len(hm.group(1))
            htext = hm.group(2).strip()
            while heading_stack and heading_stack[-1][0] >= level:
                heading_stack.pop()
            heading_stack.append((level, htext))
            cur_heading = htext
            cur_level = level
            cur_path = [h for _, h in heading_stack]
            cur_start = idx
            cur_lines = [line]
            continue

        cur_lines.append(line)

    _flush_section(len(lines))

    # Merge empty parent heading into immediate child context awareness, keep stub detection accurate
    raw_status = str(meta.get("status") or "").strip().lower()
    has_incomplete_marker = raw_status in INCOMPLETE_STATUSES or any(
        normalize_tag(t).lower() in INCOMPLETE_STATUSES for t in tags
    )
    stub_headings = [
        sec["heading"]
        for sec in raw_sections
        if sec["is_stub"]
        and sec["level"] > 0
        and sec["heading"].strip().lower() not in BOILERPLATE_HEADINGS
        # An H1 parent heading that immediately precedes an H2 child is just a document header, not a stub section
        and not (
            sec["level"] == 1
            and sec["is_placeholder"]
            and any(s["level"] >= 2 and not s["is_stub"] for s in raw_sections)
        )
    ]

    return {
        "meta": meta,
        "title": title,
        "aliases": aliases,
        "tags": tags,
        "frontmatter_links": fm_links,
        "has_incomplete_marker": has_incomplete_marker,
        "stub_headings": stub_headings,
        "sections": raw_sections,
    }


def _extract_anchor_excerpt(parsed: dict[str, Any], anchor: str, max_chars: int = 800) -> str:
    sections = parsed.get("sections", [])
    if not sections:
        return ""
    clean_anchor = anchor.strip()
    if clean_anchor.startswith("^"):
        bid = clean_anchor[1:].strip()
        for sec in sections:
            if bid in sec.get("block_ids", []):
                # Extract paragraph/lines containing ^block_id
                lines = sec["content"].splitlines()
                for idx, ln in enumerate(lines):
                    if f"^{bid}" in ln:
                        lo = max(0, idx - 2)
                        hi = min(len(lines), idx + 3)
                        excerpt, _ = _truncate_text("\n".join(lines[lo:hi]), max_chars)
                        return excerpt
                excerpt, _ = _truncate_text(sec["content"], max_chars)
                return excerpt
    elif clean_anchor:
        target_slug = heading_slug(clean_anchor)
        for sec in sections:
            if sec["anchor"] == target_slug or sec["heading"].strip().lower() == clean_anchor.lower():
                excerpt, _ = _truncate_text(sec["content"], max_chars)
                return excerpt

    for sec in sections:
        if not sec["is_stub"]:
            excerpt, _ = _truncate_text(sec["content"], max_chars)
            return excerpt
    excerpt, _ = _truncate_text(sections[0]["content"], max_chars)
    return excerpt


def _safe_read_vault_note(vault_root: Path, rel_path: str) -> str | None:
    root = vault_root.resolve()
    cand = (root / rel_path).resolve()
    if not is_within_root(cand, root):
        return None
    if cand.is_symlink() and not is_within_root(cand, root):
        return None
    if not cand.is_file():
        return None
    try:
        return read_text_safe(cand, max_bytes=MAX_INDEX_BYTES)
    except OSError:
        return None


def retrieve_note_sections(
    vault_root: Path,
    rel_path: str,
    query: str = "",
    *,
    max_sections: int = 4,
    max_section_chars: int = 1500,
) -> dict[str, Any]:
    """Safely read and return bounded relevant sections from a single vault note."""
    text = _safe_read_vault_note(vault_root, rel_path)
    if text is None:
        raise FileNotFoundError(f"Vault note not accessible inside vault: {rel_path}")
    parsed = extract_markdown_sections(text, fallback_title=Path(rel_path).stem)
    q_terms = set(_base_terms(query)) if query.strip() else set()
    q_clean = query.strip().lower()

    scored: list[tuple[float, int, dict[str, Any]]] = []
    for idx, sec in enumerate(parsed["sections"]):
        if sec["is_placeholder"] and sec["level"] == 1:
            continue
        score = 0.0
        if q_terms:
            h_terms = _term_set(" ".join(sec["heading_path"]))
            b_terms = _term_set(sec["content"])
            h_hits = len(q_terms & h_terms)
            b_hits = len(q_terms & b_terms)
            score += h_hits * 5.0 + b_hits * 2.0
            if q_clean and q_clean in sec["heading"].lower():
                score += 10.0
            if q_clean and q_clean in sec["content"].lower():
                score += 4.0
        if not sec["is_stub"]:
            score += min(3.0, sec["effective_words"] / 40.0)
        scored.append((score, idx, sec))

    if q_terms:
        scored.sort(key=lambda it: (-it[0], it[1]))
    chosen = sorted(scored[:max_sections], key=lambda it: it[1])

    out_sections: list[dict[str, Any]] = []
    for score, _, sec in chosen:
        content, truncated = _truncate_text(sec["content"], max_section_chars)
        out_sections.append(
            {
                "rel_path": rel_path,
                "heading": sec["heading"],
                "heading_path": sec["heading_path"],
                "anchor": sec["anchor"],
                "word_count": sec["word_count"],
                "prose_word_count": sec["prose_word_count"],
                "effective_words": sec["effective_words"],
                "is_stub": sec["is_stub"],
                "has_equations": sec["has_equations"],
                "has_code": sec["has_code"],
                "score": round(score, 2),
                "content": content,
                "truncated": truncated,
            }
        )
    return {
        "rel_path": rel_path,
        "title": parsed["title"],
        "aliases": parsed["aliases"],
        "tags": parsed["tags"],
        "has_incomplete_marker": parsed["has_incomplete_marker"],
        "stub_headings": parsed["stub_headings"],
        "sections": out_sections,
    }


def _evaluate_section_focus(
    sec: dict[str, Any],
    *,
    note_title: str,
    note_stem: str,
    note_aliases: list[str],
    note_tags: list[str],
    query: str,
) -> dict[str, Any]:
    """Distinguish focused substantive coverage from superficial keyword overlap."""
    q_clean = query.strip().lower()
    q_base = list(dict.fromkeys(_base_terms(query)))
    if not q_base:
        return {"focused": False, "score": 0.0, "matched_terms": []}

    title_blob = " ".join([note_stem, note_title, *note_aliases, *[t.replace("-", " ") for t in note_tags]])
    title_terms = _term_set(title_blob)
    heading_terms = _term_set(" ".join(sec["heading_path"]))
    body_terms = _term_set(sec["content"])

    title_phrase = bool(q_clean and q_clean in title_blob.lower())
    heading_phrase = bool(q_clean and q_clean in " ".join(sec["heading_path"]).lower())
    body_phrase = bool(q_clean and q_clean in sec["content"].lower())

    title_hits = [t for t in q_base if t in title_terms]
    heading_hits = [t for t in q_base if t in heading_terms]
    combined_hits = [t for t in q_base if t in (title_terms | heading_terms | body_terms)]

    # Multi-word queries require core concept token coverage (prevents "Gradient Boosting" matching "Gradient Descent")
    req_hits = 1 if len(q_base) == 1 else (2 if len(q_base) == 2 else max(2, math.ceil(0.6 * len(q_base))))
    has_token_coverage = title_phrase or heading_phrase or body_phrase or (len(combined_hits) >= req_hits)
    if not has_token_coverage:
        return {"focused": False, "score": 0.0, "matched_terms": combined_hits}

    if sec["is_stub"]:
        return {"focused": False, "score": 0.0, "matched_terms": combined_hits}

    # Count sentences/lines in section mentioning query tokens
    sentences = [
        s.strip()
        for s in re.split(r"(?<=[.!?])\s+|\n+", sec["content"])
        if s.strip() and not HEADING_RE.match(s)
    ]
    matching_sentences = 0
    for sent in sentences:
        st_terms = _term_set(sent)
        if any(t in st_terms for t in q_base):
            matching_sentences += 1

    title_ratio = len(title_hits) / len(q_base)
    heading_ratio = len(heading_hits) / len(q_base)
    body_hits = [t for t in q_base if t in body_terms]

    # Topical focus gate: dedicated note/section heading OR repeated substantive discussion
    is_focused = (
        title_phrase
        or heading_phrase
        or title_ratio >= 0.5
        or heading_ratio >= 0.5
        or (matching_sentences >= 2 and len(body_hits) >= req_hits and sec["effective_words"] >= 25)
    )
    if not is_focused:
        return {"focused": False, "score": 0.0, "matched_terms": combined_hits}

    score = (
        (12.0 if title_phrase else 0.0)
        + (10.0 if heading_phrase else 0.0)
        + (4.0 if body_phrase else 0.0)
        + len(title_hits) * 4.0
        + len(heading_hits) * 4.5
        + len(body_hits) * 2.5
        + min(4.0, matching_sentences * 1.2)
        + min(4.0, sec["effective_words"] / 30.0)
    )
    return {"focused": True, "score": round(score, 2), "matched_terms": combined_hits}


def _split_compound_facets(query: str) -> list[str]:
    parts = re.split(r"\s+(?:vs\.?|versus|and)\s+", query.strip(), flags=re.IGNORECASE)
    cleaned = [p.strip() for p in parts if len(_base_terms(p)) >= 1]
    if len(cleaned) >= 2:
        return cleaned[:4]
    return []


def resolve_sources(
    query: str,
    *,
    vault_path: str | Path | None = None,
    vault_ref: str | None = None,
    objectives: list[dict[str, Any] | str] | None = None,
    session_dir: Path | None = None,
    config: dict[str, Any] | None = None,
    state_dir: Path | None = None,
    web_available: bool = True,
    max_notes: int = 5,
    max_sections_per_note: int = 4,
    max_related_notes: int = 3,
    max_section_chars: int = 1500,
    max_total_chars: int = 10000,
) -> dict[str, Any]:
    """Deterministically resolve permitted learning sources into vault, hybrid, or web mode.

    Retrieves bounded Markdown sections and related prerequisite/embedded notes rather than
    relying on filenames, titles, or 280-char summaries, and never scans arbitrary directories.
    """
    cfg = config if config is not None else load_config()
    q_clean = query.strip()
    notices: list[str] = []

    # Load explicit objectives from session curriculum if provided and objectives arg omitted
    resolved_objectives: list[dict[str, Any]] = []
    if objectives:
        for idx, raw_o in enumerate(objectives, start=1):
            if isinstance(raw_o, str):
                desc = raw_o.strip()
                if desc:
                    resolved_objectives.append(
                        {"id": f"obj-{idx:02d}", "description": desc, "required": True, "in_scope": True}
                    )
            elif isinstance(raw_o, dict):
                desc = str(raw_o.get("description") or raw_o.get("title") or "").strip()
                if desc:
                    resolved_objectives.append(
                        {
                            "id": str(raw_o.get("id") or f"obj-{idx:02d}"),
                            "description": desc,
                            "required": bool(raw_o.get("required", True)),
                            "in_scope": bool(raw_o.get("in_scope", True)),
                        }
                    )
    elif session_dir is not None and session_dir.is_dir():
        curr_path = session_dir / "scratchpad" / "curriculum.json"
        if curr_path.is_file():
            try:
                curr = json.loads(read_text_safe(curr_path))
                for nid in curr.get("order") or list((curr.get("nodes") or {}).keys()):
                    node = (curr.get("nodes") or {}).get(nid)
                    if not isinstance(node, dict):
                        continue
                    for obj in node.get("objectives") or []:
                        if isinstance(obj, dict) and obj.get("in_scope", True):
                            resolved_objectives.append(
                                {
                                    "id": str(obj.get("id") or nid),
                                    "description": str(obj.get("description") or node.get("title") or nid),
                                    "required": bool(obj.get("required", True)),
                                    "in_scope": True,
                                }
                            )
            except (OSError, json.JSONDecodeError):
                pass

    # Step 1: Resolve permitted vault ONLY from explicit argument or configured active vault
    target_entry: dict[str, Any] | None = None
    if vault_path is not None:
        p = Path(vault_path)
        target_entry = get_active_vault_entry(cfg, explicit_vault=str(p))
    elif vault_ref is not None:
        target_entry = get_active_vault_entry(cfg, explicit_vault=vault_ref)
    else:
        target_entry = get_active_vault_entry(cfg)

    def _web_result(
        *,
        vault_info: dict[str, Any],
        reason: str,
        missing: list[dict[str, Any]],
        extra_notices: list[str] | None = None,
    ) -> dict[str, Any]:
        all_notices = list(notices) + list(extra_notices or [])
        if not web_available:
            all_notices.append(
                "Web browsing/search tools are unavailable. Continue with available knowledge when appropriate, "
                "make limitations explicit, and never fabricate retrieval or citations."
            )
        return {
            "schema_version": 1,
            "query": q_clean,
            "mode": "web",
            "mode_reason": reason,
            "vault": vault_info,
            "web": {
                "available": bool(web_available),
                "needed": True,
                "targets": [m["target"] for m in missing] or ([q_clean] if q_clean else []),
            },
            "relevant_vault_paths": [],
            "matched_sections": [],
            "related_notes": [],
            "coverage_assessment": {
                "status": "insufficient",
                "objectives": [
                    {
                        "id": o["id"],
                        "description": o["description"],
                        "required": o["required"],
                        "status": "missing",
                        "matched_paths": [],
                    }
                    for o in resolved_objectives
                    if o["in_scope"]
                ],
            },
            "missing_coverage": missing,
            "source_provenance": [],
            "notices": all_notices,
        }

    if target_entry is None:
        missing = (
            [{"objective_id": o["id"], "target": o["description"], "reason": "No Obsidian vault configured"} for o in resolved_objectives if o["in_scope"]]
            if resolved_objectives
            else [{"target": q_clean, "reason": "No Obsidian vault configured"}]
        )
        return _web_result(
            vault_info={"configured": False, "accessible": False, "status": "not_configured", "name": "", "path": ""},
            reason="No Obsidian vault is configured; using web teaching mode.",
            missing=missing,
        )

    v_path = Path(target_entry["path"])
    v_name = target_entry["name"]
    try:
        is_dir = v_path.is_dir()
        if is_dir:
            os.listdir(v_path)
    except OSError as exc:
        missing = (
            [{"objective_id": o["id"], "target": o["description"], "reason": f"Vault inaccessible: {exc}"} for o in resolved_objectives if o["in_scope"]]
            if resolved_objectives
            else [{"target": q_clean, "reason": f"Vault inaccessible: {exc}"}]
        )
        return _web_result(
            vault_info={
                "configured": True,
                "accessible": False,
                "status": "inaccessible",
                "name": v_name,
                "path": str(v_path),
                "error": str(exc),
            },
            reason=f"Configured vault '{v_name}' is inaccessible; falling back to web mode.",
            missing=missing,
            extra_notices=[f"Configured vault '{v_name}' ({v_path}) is inaccessible: {exc}"],
        )

    if not is_dir:
        missing = (
            [{"objective_id": o["id"], "target": o["description"], "reason": "Configured vault directory does not exist"} for o in resolved_objectives if o["in_scope"]]
            if resolved_objectives
            else [{"target": q_clean, "reason": "Configured vault directory does not exist"}]
        )
        return _web_result(
            vault_info={
                "configured": True,
                "accessible": False,
                "status": "inaccessible",
                "name": v_name,
                "path": str(v_path),
                "error": f"Vault directory not found: {v_path}",
            },
            reason=f"Configured vault '{v_name}' directory does not exist; falling back to web mode.",
            missing=missing,
            extra_notices=[f"Configured vault '{v_name}' ({v_path}) does not exist on disk."],
        )

    # Step 2: Incremental index load/refresh
    eff_state_dir = state_dir or (expand_path(target_entry["state_dir"]) if target_entry.get("state_dir") else resolve_state_dir(v_path, config=cfg))
    idx = load_or_build_index(v_path, refresh=False, state_dir=eff_state_dir, ignore_write_errors=True)
    vault_info = {
        "configured": True,
        "accessible": True,
        "status": "accessible",
        "name": v_name,
        "path": str(v_path),
        "doc_count": idx.get("doc_count", 0),
        "index_stats": idx.get("stats", {}),
    }

    # Step 3: Search candidate notes (query + objectives)
    cand_paths: list[str] = []
    seen_cands: set[str] = set()
    search_queries = [q_clean] if q_clean else []
    for obj in resolved_objectives[:6]:
        if obj["in_scope"] and obj["description"]:
            search_queries.append(obj["description"])
    for facet in _split_compound_facets(q_clean):
        search_queries.append(facet)

    cand_cap = max(10, max_notes * 3)
    per_query_cap = max(5, max_notes * 2)
    for sq in search_queries:
        res = search_vault(v_path, sq, limit=per_query_cap, index=idx)
        for hit in res.get("results", []):
            rp = hit["rel_path"]
            if rp not in seen_cands:
                seen_cands.add(rp)
                cand_paths.append(rp)
        if len(cand_paths) >= cand_cap * 2:
            break
    cand_paths = cand_paths[: cand_cap * 2]

    # Step 4: Retrieve actual sections and score focus + depth
    docs_meta = idx.get("docs", {})
    parsed_cache: dict[str, dict[str, Any]] = {}
    focused_candidates: list[dict[str, Any]] = []
    all_parsed_notes: dict[str, dict[str, Any]] = {}

    facets = _split_compound_facets(q_clean)
    for rel_path in cand_paths:
        raw_text = _safe_read_vault_note(v_path, rel_path)
        if raw_text is None:
            continue
        doc_entry = docs_meta.get(rel_path, {})
        parsed = extract_markdown_sections(raw_text, fallback_title=Path(rel_path).stem)
        parsed_cache[rel_path] = parsed
        all_parsed_notes[rel_path] = parsed

        note_focused_secs: list[dict[str, Any]] = []
        for sec in parsed["sections"]:
            ev = _evaluate_section_focus(
                sec,
                note_title=parsed["title"],
                note_stem=Path(rel_path).stem,
                note_aliases=parsed["aliases"],
                note_tags=parsed["tags"],
                query=q_clean,
            )
            if not ev["focused"] and facets:
                for facet in facets:
                    fev = _evaluate_section_focus(
                        sec,
                        note_title=parsed["title"],
                        note_stem=Path(rel_path).stem,
                        note_aliases=parsed["aliases"],
                        note_tags=parsed["tags"],
                        query=facet,
                    )
                    if fev["focused"] and fev["score"] > ev["score"]:
                        ev = fev
            if ev["focused"]:
                note_focused_secs.append({**sec, "focus_score": ev["score"], "matched_terms": ev["matched_terms"]})

        if note_focused_secs:
            note_focused_secs.sort(key=lambda s: (-s["focus_score"], s["start_line"]))
            top_secs = note_focused_secs[:max_sections_per_note]
            focused_candidates.append(
                {
                    "rel_path": rel_path,
                    "doc": doc_entry,
                    "parsed": parsed,
                    "sections": top_secs,
                    "note_score": sum(s["focus_score"] for s in top_secs),
                    "effective_words": sum(s["effective_words"] for s in top_secs),
                }
            )

    focused_candidates.sort(key=lambda c: (-c["note_score"], -c["effective_words"], c["rel_path"]))

    # Step 5: Objective-level or implicit completeness assessment
    missing_coverage: list[dict[str, Any]] = []
    objective_evals: list[dict[str, Any]] = []
    selected_sections_raw: list[dict[str, Any]] = []
    selected_note_paths: list[str] = []

    if resolved_objectives:
        # Evaluate each in-scope objective against all candidate notes' non-stub sections
        note_obj_hits: dict[str, float] = defaultdict(float)
        matched_sec_keys: dict[tuple[str, str, int], list[str]] = defaultdict(list)

        for obj in resolved_objectives:
            if not obj["in_scope"]:
                continue
            obj_terms = list(dict.fromkeys(_base_terms(obj["description"], extra_stop=GENERIC_OBJECTIVE_VERBS)))
            if not obj_terms:
                obj_terms = list(dict.fromkeys(_base_terms(obj["description"])))
            topic_terms = list(dict.fromkeys(_base_terms(q_clean)))

            best_status = "missing"
            best_score = 0.0
            best_sec_info: tuple[str, dict[str, Any], dict[str, Any]] | None = None

            for rel_path, parsed in all_parsed_notes.items():
                title_blob = " ".join([Path(rel_path).stem, parsed["title"], *parsed["aliases"], *parsed["tags"]])
                title_set = _term_set(title_blob)
                for sec in parsed["sections"]:
                    if sec["is_stub"]:
                        continue
                    sec_set = _term_set(sec["content"] + " " + " ".join(sec["heading_path"])) | title_set
                    hits = [t for t in obj_terms if t in sec_set]
                    ratio = len(hits) / max(1, len(obj_terms))
                    # Must also have topic relevance if topic terms exist
                    topic_hits = [t for t in topic_terms if t in sec_set]
                    if topic_terms and not topic_hits:
                        continue

                    min_cov_words = 18 if (sec["has_equations"] or sec["has_code"]) else 25
                    if (ratio >= 0.5 or (len(hits) >= 2 and ratio >= 0.4)) and sec["effective_words"] >= min_cov_words:
                        sc = ratio * 10.0 + len(hits) * 2.0 + min(3.0, sec["effective_words"] / 30.0)
                        if best_status != "covered" or sc > best_score:
                            best_status = "covered"
                            best_score = sc
                            best_sec_info = (rel_path, parsed, sec)
                    elif ratio >= 0.3 and sec["effective_words"] >= 12 and best_status != "covered":
                        sc = ratio * 6.0 + len(hits)
                        if best_status != "partial" or sc > best_score:
                            best_status = "partial"
                            best_score = sc
                            best_sec_info = (rel_path, parsed, sec)

            matched_paths_for_obj: list[str] = []
            if best_sec_info is not None and best_status in ("covered", "partial"):
                rp, _, bsec = best_sec_info
                matched_paths_for_obj.append(rp)
                note_obj_hits[rp] += best_score
                matched_sec_keys[(rp, bsec["heading"], bsec["start_line"])].append(obj["id"])

            objective_evals.append(
                {
                    "id": obj["id"],
                    "description": obj["description"],
                    "required": obj["required"],
                    "status": best_status,
                    "matched_paths": matched_paths_for_obj,
                }
            )
            if best_status in ("missing", "partial"):
                missing_coverage.append(
                    {
                        "objective_id": obj["id"],
                        "target": obj["description"],
                        "status": best_status,
                        "reason": (
                            "No substantive vault section covers this objective"
                            if best_status == "missing"
                            else "Only partial/shallow vault coverage found for this objective"
                        ),
                    }
                )

        # Select top notes combining topic focus and objective matches
        ranked_rel_paths: list[str] = []
        combined_rank: dict[str, float] = {}
        for fc in focused_candidates:
            combined_rank[fc["rel_path"]] = combined_rank.get(fc["rel_path"], 0.0) + fc["note_score"]
        for rp, oscore in note_obj_hits.items():
            combined_rank[rp] = combined_rank.get(rp, 0.0) + oscore * 2.0
        for rp, _ in sorted(combined_rank.items(), key=lambda kv: (-kv[1], kv[0]))[:max_notes]:
            ranked_rel_paths.append(rp)

        selected_note_paths = ranked_rel_paths
        for rp in selected_note_paths:
            parsed = all_parsed_notes[rp]
            # Pick objective-matched sections first, then topic-focused sections
            cand_secs: list[tuple[float, dict[str, Any]]] = []
            for sec in parsed["sections"]:
                if sec["is_stub"]:
                    continue
                key = (rp, sec["heading"], sec["start_line"])
                obj_ids = matched_sec_keys.get(key, [])
                ev = _evaluate_section_focus(
                    sec,
                    note_title=parsed["title"],
                    note_stem=Path(rp).stem,
                    note_aliases=parsed["aliases"],
                    note_tags=parsed["tags"],
                    query=q_clean,
                )
                sc = len(obj_ids) * 15.0 + ev["score"]
                if obj_ids or ev["focused"]:
                    cand_secs.append((sc, sec))
            cand_secs.sort(key=lambda it: (-it[0], it[1]["start_line"]))
            for sc, sec in cand_secs[:max_sections_per_note]:
                key = (rp, sec["heading"], sec["start_line"])
                selected_sections_raw.append(
                    {
                        "rel_path": rp,
                        "parsed": parsed,
                        "sec": sec,
                        "score": sc,
                        "matched_objectives": matched_sec_keys.get(key, []),
                    }
                )

        req_evals = [o for o in objective_evals if o["required"]] or objective_evals
        if not req_evals:
            mode = "web"
            mode_reason = "No in-scope objectives to satisfy from vault."
        elif all(o["status"] == "covered" for o in req_evals):
            mode = "vault"
            mode_reason = "Existing vault notes substantively cover all required learning objectives."
        elif any(o["status"] in ("covered", "partial") for o in objective_evals) and selected_sections_raw:
            mode = "hybrid"
            mode_reason = "Existing vault notes cover part of the requested objectives; missing objectives require targeted research."
        else:
            return _web_result(
                vault_info=vault_info,
                reason="Vault notes lacked substantive coverage of requested objectives; using web mode.",
                missing=missing_coverage,
            )

    else:
        # No explicit objectives: assess substantive depth & completeness from focused sections
        total_focused_words = sum(fc["effective_words"] for fc in focused_candidates[:max_notes])
        if not focused_candidates or total_focused_words < 25:
            return _web_result(
                vault_info=vault_info,
                reason="No substantive vault notes cover the requested topic (keyword-only/stub matches excluded); using web mode.",
                missing=[{"target": q_clean, "reason": "No substantive vault coverage found"}],
            )

        selected_candidates = focused_candidates[:max_notes]
        selected_note_paths = [c["rel_path"] for c in selected_candidates]
        for c in selected_candidates:
            for sec in c["sections"]:
                selected_sections_raw.append(
                    {
                        "rel_path": c["rel_path"],
                        "parsed": c["parsed"],
                        "sec": sec,
                        "score": sec["focus_score"],
                        "matched_objectives": [],
                    }
                )

        # Check multi-facet gaps (e.g. "BFS vs DFS")
        facets = _split_compound_facets(q_clean)
        missing_facets: list[str] = []
        for facet in facets:
            has_facet = False
            for c in selected_candidates:
                for sec in c["sections"]:
                    fev = _evaluate_section_focus(
                        sec,
                        note_title=c["parsed"]["title"],
                        note_stem=Path(c["rel_path"]).stem,
                        note_aliases=c["parsed"]["aliases"],
                        note_tags=c["parsed"]["tags"],
                        query=facet,
                    )
                    if fev["focused"]:
                        has_facet = True
                        break
                if has_facet:
                    break
            if not has_facet:
                missing_facets.append(facet)

        # Check incomplete markers or shallow single-section depth on primary matched note
        primary = selected_candidates[0]
        primary_parsed = primary["parsed"]
        for sh in primary_parsed["stub_headings"]:
            missing_coverage.append(
                {"target": sh, "reason": f"Section '{sh}' in {primary['rel_path']} is empty or a stub"}
            )
        for mf in missing_facets:
            missing_coverage.append(
                {"target": mf, "reason": f"Subtopic '{mf}' has no substantive coverage in vault"}
            )
        if primary_parsed["has_incomplete_marker"] and not missing_coverage:
            missing_coverage.append(
                {"target": q_clean, "reason": f"Primary note {primary['rel_path']} is marked draft/wip/stub"}
            )
        if total_focused_words < 35 and not missing_coverage:
            missing_coverage.append(
                {
                    "target": f"{q_clean}: mechanisms, worked examples, and edge cases",
                    "reason": f"Vault note coverage is brief ({total_focused_words} effective words); deeper explanation and examples needed",
                }
            )

        if missing_coverage:
            mode = "hybrid"
            mode_reason = "Existing vault notes partially cover the topic; missing gaps require selective research."
        else:
            mode = "vault"
            mode_reason = "Existing vault notes sufficiently cover the requested topic; teach from notes without unnecessary web research."

    # Step 6: Package bounded matched_sections & resolve related prerequisite/embedded notes
    matched_sections_out: list[dict[str, Any]] = []
    provenance_map: dict[str, dict[str, Any]] = {}
    used_chars = 0
    related_budget = min(2400, max_total_chars // 4)
    primary_budget = max(1000, max_total_chars - related_budget)

    for item in selected_sections_raw:
        if used_chars >= primary_budget:
            break
        rp = item["rel_path"]
        parsed = item["parsed"]
        sec = item["sec"]
        remaining = primary_budget - used_chars
        cap = min(max_section_chars, remaining)
        if cap < 120 and matched_sections_out:
            break
        bounded_text, was_trunc = _truncate_text(sec["content"], cap)
        used_chars += len(bounded_text)

        matched_sections_out.append(
            {
                "rel_path": rp,
                "note_title": parsed["title"],
                "folder": docs_meta.get(rp, {}).get("folder", ""),
                "aliases": parsed["aliases"],
                "tags": parsed["tags"],
                "heading": sec["heading"],
                "heading_path": sec["heading_path"],
                "anchor": sec["anchor"],
                "word_count": sec["word_count"],
                "effective_words": sec["effective_words"],
                "score": round(item["score"], 2),
                "matched_objectives": item["matched_objectives"],
                "content": bounded_text,
                "truncated": was_trunc,
            }
        )
        prov = provenance_map.setdefault(
            rp,
            {
                "source_type": "obsidian_note",
                "vault_name": v_name,
                "vault_path": str(v_path),
                "rel_path": rp,
                "title": parsed["title"],
                "aliases": parsed["aliases"],
                "tags": parsed["tags"],
                "sections": [],
                "content_hash": docs_meta.get(rp, {}).get("content_hash", ""),
                "trust": "untrusted_source_content",
            },
        )
        if sec["heading"] not in prov["sections"]:
            prov["sections"].append(sec["heading"])

    # Resolve 1-hop related prerequisite & embedded notes
    related_candidates: list[tuple[int, str, str, str]] = []  # (priority, rel_path, relation, anchor)
    seen_rel_targets: set[tuple[str, str]] = set()
    selected_set = set(selected_note_paths)

    for rp in selected_note_paths:
        parsed = all_parsed_notes.get(rp)
        if not parsed:
            continue
        # 1) Embeds in matched sections (highest priority)
        for item in selected_sections_raw:
            if item["rel_path"] != rp:
                continue
            for wl in item["sec"].get("wikilinks", []):
                if wl.get("embed") and wl.get("note"):
                    res_l = resolve_link_to_rel_path(
                        f"{wl['note']}#{wl['anchor']}" if wl.get("anchor") else wl["note"],
                        idx,
                        vault_root=v_path,
                    )
                    target_rp = res_l.get("resolved")
                    if target_rp and not res_l.get("is_attachment") and target_rp != rp:
                        tkey = (target_rp, wl.get("anchor", ""))
                        if tkey not in seen_rel_targets:
                            seen_rel_targets.add(tkey)
                            related_candidates.append((0, target_rp, "embed", wl.get("anchor", "")))

        # 2) Frontmatter prerequisite/hierarchy links
        for fkey, targets in parsed.get("frontmatter_links", {}).items():
            if fkey.lower() in PREREQ_FM_KEYS:
                for tgt in targets:
                    res_l = resolve_link_to_rel_path(tgt, idx, vault_root=v_path)
                    target_rp = res_l.get("resolved")
                    if target_rp and target_rp not in selected_set and not res_l.get("is_attachment"):
                        tkey = (target_rp, res_l.get("anchor", ""))
                        if tkey not in seen_rel_targets:
                            seen_rel_targets.add(tkey)
                            related_candidates.append((1, target_rp, "prerequisite", res_l.get("anchor", "")))

        # 3) Wikilinks inside matched sections
        for item in selected_sections_raw:
            if item["rel_path"] != rp:
                continue
            for wl in item["sec"].get("wikilinks", []):
                if not wl.get("embed") and wl.get("note"):
                    res_l = resolve_link_to_rel_path(wl["note"], idx, vault_root=v_path)
                    target_rp = res_l.get("resolved")
                    if target_rp and target_rp not in selected_set and not res_l.get("is_attachment"):
                        tkey = (target_rp, wl.get("anchor", ""))
                        if tkey not in seen_rel_targets:
                            seen_rel_targets.add(tkey)
                            rel_kind = (
                                "prerequisite"
                                if any(k in item["sec"]["heading"].lower() for k in ("prereq", "background", "require", "foundat"))
                                else "linked"
                            )
                            related_candidates.append((2 if rel_kind == "prerequisite" else 3, target_rp, rel_kind, wl.get("anchor", "")))

    related_candidates.sort(key=lambda it: (it[0], it[1]))
    related_notes_out: list[dict[str, Any]] = []
    rel_used = 0
    for _, trp, rel_kind, anchor in related_candidates:
        if len(related_notes_out) >= max_related_notes or rel_used >= related_budget:
            break
        raw_rel = _safe_read_vault_note(v_path, trp)
        if raw_rel is None:
            continue
        tparsed = extract_markdown_sections(raw_rel, fallback_title=Path(trp).stem)
        cap = min(800, related_budget - rel_used)
        if cap < 80:
            break
        excerpt = _extract_anchor_excerpt(tparsed, anchor, max_chars=cap)
        if not excerpt:
            continue
        rel_used += len(excerpt)
        related_notes_out.append(
            {
                "rel_path": trp,
                "title": tparsed["title"],
                "relation": rel_kind,
                "anchor": anchor,
                "tags": tparsed["tags"],
                "excerpt": excerpt,
            }
        )
        if trp not in provenance_map:
            provenance_map[trp] = {
                "source_type": "obsidian_note",
                "vault_name": v_name,
                "vault_path": str(v_path),
                "rel_path": trp,
                "title": tparsed["title"],
                "aliases": tparsed["aliases"],
                "tags": tparsed["tags"],
                "sections": [anchor or "lead"],
                "content_hash": docs_meta.get(trp, {}).get("content_hash", ""),
                "trust": "untrusted_source_content",
            }

    if mode == "hybrid" and not web_available:
        notices.append(
            "Web browsing/search tools are unavailable. Teach covered objectives from retrieved vault notes, "
            "continue missing objectives with available knowledge if appropriate, state limitations explicitly, "
            "and never fabricate retrieval or citations."
        )

    return {
        "schema_version": 1,
        "query": q_clean,
        "mode": mode,
        "mode_reason": mode_reason,
        "vault": vault_info,
        "web": {
            "available": bool(web_available),
            "needed": mode != "vault",
            "targets": [m["target"] for m in missing_coverage] if mode != "vault" else [],
        },
        "relevant_vault_paths": selected_note_paths,
        "matched_sections": matched_sections_out,
        "related_notes": related_notes_out,
        "coverage_assessment": {
            "status": "sufficient" if mode == "vault" else "partial",
            "objectives": objective_evals,
        },
        "missing_coverage": missing_coverage,
        "source_provenance": list(provenance_map.values()),
        "notices": notices,
    }
