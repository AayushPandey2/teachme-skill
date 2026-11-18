"""Capability-aware educational web image selection, verification, caching, and terminal fallback."""

from __future__ import annotations

import base64
import importlib
import json
from pathlib import Path
import re
from typing import Any, Callable, Mapping, Sequence
from urllib.parse import urlparse

from .models import atomic_write_text, is_within_root, read_text_safe, utc_now_iso
from .terminal_caps import detect_terminal_capabilities

# Domains generally carrying credible educational, scientific, or official technical diagrams
CREDIBLE_DOMAIN_SUFFIXES = (
    ".edu",
    ".gov",
    ".ac.uk",
    ".ac.jp",
)
CREDIBLE_DOMAINS = frozenset(
    {
        "wikimedia.org",
        "upload.wikimedia.org",
        "commons.wikimedia.org",
        "en.wikipedia.org",
        "wikipedia.org",
        "openstax.org",
        "nih.gov",
        "ncbi.nlm.nih.gov",
        "nasa.gov",
        "mit.edu",
        "stanford.edu",
        "python.org",
        "docs.python.org",
        "pytorch.org",
        "numpy.org",
        "scikit-learn.org",
        "developer.mozilla.org",
        "w3.org",
        "arxiv.org",
    }
)
LOW_TRUST_OR_STOCK_DOMAINS = frozenset(
    {
        "pinterest.com",
        "shutterstock.com",
        "istockphoto.com",
        "gettyimages.com",
        "dreamstime.com",
        "123rf.com",
        "vecteezy.com",
    }
)

_VISUAL_REAL_WORLD_HINTS = (
    "anatomy",
    "organ",
    "bone",
    "muscle",
    "heart",
    "brain",
    "cell",
    "microscop",
    "geolog",
    "rock",
    "stratum",
    "hardware",
    "motherboard",
    "pinout",
    "port",
    "connector",
    "circuit board",
    "pcb",
    "telescope",
    "spectrum",
    "histology",
    "species",
    "botan",
    "fossil",
)

_NON_IMAGE_PREFER_GRAPH_OR_TEXT_HINTS = (
    "gradient descent",
    "loss curve",
    "sorting",
    "bubble sort",
    "selection sort",
    "insertion sort",
    "pointer",
    "definition",
    "what is",
    "theorem",
    "equation",
    "derivative",
    "bernoulli",
    "complexity",
)

_QUERY_STOPWORDS = frozenset(
    {
        "the", "and", "for", "with", "that", "this", "from", "into", "about",
        "how", "why", "what", "learn", "understand", "explain", "basic", "basics",
    }
)

_ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]|\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)|\x1b_[^\x1b]*\x1b\\")
_CTRL_CHARS_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def sanitize_untrusted_text(raw: str | None, *, max_len: int = 240) -> str:
    """Strip terminal escape sequences and control chars from retrieved text."""
    text = str(raw or "")
    text = _ANSI_ESCAPE_RE.sub("", text)
    text = _CTRL_CHARS_RE.sub(" ", text)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > max_len:
        text = text[: max_len - 3].rstrip() + "..."
    return text


def should_retrieve_image(
    objective_desc: str,
    *,
    concept_type: str = "",
    explicit_request: bool = False,
    host_tools: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Decide whether web image retrieval is genuinely helpful and possible."""
    tools = dict(host_tools or {})
    text = (objective_desc or "").strip().lower()
    ctype = (concept_type or "").strip().lower()

    if not explicit_request:
        if any(tok in text for tok in _NON_IMAGE_PREFER_GRAPH_OR_TEXT_HINTS) or ctype in (
            "definition",
            "mathematical_function",
            "optimization_dynamics",
            "algorithm_stepwise",
            "memory_pointer_code",
            "probability_experiment",
        ):
            return {
                "retrieve": False,
                "reason": "Objective is better served by a terminal graph, simulation, trace, or concise text than a web photo.",
                "alternative": "terminal_graph_or_text",
            }
        has_real_world_need = ctype == "spatial_real_world" or any(tok in text for tok in _VISUAL_REAL_WORLD_HINTS)
        if not has_real_world_need:
            return {
                "retrieve": False,
                "reason": "No clear real-world visual recognition or labeled spatial artifact requirement detected.",
                "alternative": "text_diagram_or_direct_explanation",
            }

    if not tools.get("image_search", False):
        return {
            "retrieve": False,
            "reason": "Host agent does not expose image_search capability; degrading cleanly without inventing URLs.",
            "alternative": "text_diagram_or_direct_explanation",
        }

    return {
        "retrieve": True,
        "reason": "Real-world labeled visual aids spatial recognition for this objective and image_search is available.",
        "alternative": "text_diagram",
    }


def build_image_query(topic: str, objective_desc: str, *, preferred_terms: Sequence[str] | None = None) -> str:
    """Build a focused educational image-search query."""
    combined = f"{topic} {objective_desc}".strip()
    tokens = re.findall(r"[A-Za-z0-9][A-Za-z0-9_-]{1,}", combined.lower())
    kept: list[str] = []
    for tok in tokens:
        if tok in _QUERY_STOPWORDS or tok in kept:
            continue
        kept.append(tok)
        if len(kept) >= 6:
            break
    if preferred_terms:
        for term in preferred_terms:
            clean = sanitize_untrusted_text(str(term), max_len=32).lower()
            if clean and clean not in kept:
                kept.append(clean)
    if "diagram" not in kept and "labeled" not in kept:
        kept.append("labeled diagram")
    return " ".join(kept) if kept else "educational diagram"


def _domain_score(url: str) -> tuple[int, str]:
    parsed = urlparse(url.strip())
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return -100, "invalid_or_unsafe_url_scheme"
    host = parsed.netloc.lower().split(":")[0]
    if any(host == bad or host.endswith("." + bad) for bad in LOW_TRUST_OR_STOCK_DOMAINS):
        return -50, f"low_trust_stock_domain:{host}"
    if any(host == good or host.endswith("." + good) for good in CREDIBLE_DOMAINS):
        return 30, f"credible_domain:{host}"
    if any(host.endswith(suf) for suf in CREDIBLE_DOMAIN_SUFFIXES):
        return 25, f"credible_edu_gov:{host}"
    return 5, f"general_web:{host}"


def evaluate_image_candidate(
    candidate: Mapping[str, Any],
    *,
    image_inspect_available: bool = False,
) -> dict[str, Any]:
    """Score and verify a candidate web image without ever fabricating inspection or licensing."""
    source_page = str(candidate.get("source_page_url") or "").strip()
    asset_url = str(candidate.get("asset_url") or "").strip()
    title = sanitize_untrusted_text(candidate.get("title"), max_len=140)
    description = sanitize_untrusted_text(candidate.get("description") or candidate.get("alt_text"), max_len=240)
    creator = sanitize_untrusted_text(candidate.get("creator") or "unknown", max_len=80) or "unknown"
    license_info = sanitize_untrusted_text(candidate.get("license") or "unknown", max_len=80) or "unknown"

    if not source_page and not asset_url:
        return {"accepted": False, "score": -100, "reason": "Missing both source_page_url and asset_url"}

    primary_url = source_page or asset_url
    d_score, d_reason = _domain_score(primary_url)
    if d_score < 0:
        return {"accepted": False, "score": d_score, "reason": d_reason}

    if asset_url:
        a_score, a_reason = _domain_score(asset_url)
        if a_score < 0:
            return {"accepted": False, "score": a_score, "reason": a_reason}

    if not title or title.lower() in ("untitled", "image", "unknown"):
        return {"accepted": False, "score": -20, "reason": "Candidate lacks verifiable descriptive title"}

    if candidate.get("is_thumbnail_only", False) and not source_page:
        return {"accepted": False, "score": -30, "reason": "Thumbnail-only result without source page rejected"}

    inspected_flag = candidate.get("inspection_passed")
    if image_inspect_available:
        if inspected_flag is False:
            reason = sanitize_untrusted_text(
                candidate.get("inspection_notes") or "Rejected during visual inspection (misleading/irrelevant/bad labels)"
            )
            return {"accepted": False, "score": -80, "reason": reason}
        if inspected_flag is True:
            verification_status = "inspected_verified"
            d_score += 20
        else:
            # Inspection tool exists but was not actually run on this candidate
            verification_status = "metadata_only_unverified"
    else:
        # Never claim inspected_verified when image inspection is unavailable
        verification_status = "metadata_only_unverified"

    return {
        "accepted": True,
        "score": d_score,
        "domain_reason": d_reason,
        "verification_status": verification_status,
        "title": title,
        "description": description,
        "creator": creator,
        "license": license_info,
        "source_page_url": source_page,
        "asset_url": asset_url,
    }


def _load_media_cache(session_dir: Path | None) -> dict[str, Any]:
    if session_dir is None:
        return {"items": {}}
    path = session_dir / "scratchpad" / "media-cache.json"
    if not path.is_file():
        return {"items": {}}
    try:
        data = json.loads(read_text_safe(path))
        if isinstance(data, dict) and isinstance(data.get("items"), dict):
            return data
    except (OSError, json.JSONDecodeError):
        pass
    return {"items": {}}


def _save_media_cache(session_dir: Path | None, cache: dict[str, Any]) -> None:
    if session_dir is None:
        return
    path = session_dir / "scratchpad" / "media-cache.json"
    atomic_write_text(path, json.dumps(cache, indent=2, ensure_ascii=False) + "\n")


def format_inline_terminal_image(
    image_path: Path,
    protocol: str,
    *,
    is_tty: bool,
) -> dict[str, Any]:
    """Generate terminal image escape payload ONLY when protocol and TTY genuinely support it."""
    proto = (protocol or "none").strip().lower()
    if not is_tty or proto not in ("kitty", "iterm2", "sixel"):
        return {"supported": False, "protocol": "none", "payload": ""}
    if not image_path.is_file():
        return {"supported": False, "protocol": "none", "payload": ""}

    raw = image_path.read_bytes()
    if len(raw) > 2 * 1024 * 1024:
        return {"supported": False, "protocol": "none", "payload": "", "reason": "image_too_large"}

    b64 = base64.b64encode(raw).decode("ascii")
    if proto == "kitty":
        # Chunked Kitty graphics protocol sequence (safe bounded size)
        chunks = [b64[i : i + 4096] for i in range(0, len(b64), 4096)] or [""]
        seq_parts: list[str] = []
        for idx, chunk in enumerate(chunks):
            more = 1 if idx < len(chunks) - 1 else 0
            if idx == 0:
                seq_parts.append(f"\x1b_Ga=T,f=100,m={more};{chunk}\x1b\\")
            else:
                seq_parts.append(f"\x1b_Gm={more};{chunk}\x1b\\")
        return {"supported": True, "protocol": "kitty", "payload": "".join(seq_parts)}

    if proto == "iterm2":
        name_b64 = base64.b64encode(image_path.name.encode("utf-8")).decode("ascii")
        payload = f"\x1b]1337;File=name={name_b64};size={len(raw)};inline=1:{b64}\x07"
        return {"supported": True, "protocol": "iterm2", "payload": payload}

    # Sixel requires pre-encoded sixel stream; we do not emit raw PNG/JPEG bytes as fake sixel
    return {"supported": False, "protocol": "none", "payload": "", "reason": "sixel_encoder_unavailable"}


def optional_ascii_image_preview(image_path: Path, *, width: int = 48, height: int = 16) -> str | None:
    """Return an optional grayscale ASCII preview only if Pillow (PIL) is installed."""
    try:
        pil_img_mod = importlib.import_module("PIL.Image")
    except ImportError:
        return None
    if not image_path.is_file():
        return None
    chars = " .:-=+*#%@"
    try:
        with pil_img_mod.open(image_path) as im:
            gray = im.convert("L").resize((max(16, width), max(6, height)))
            w, h = gray.size
            pixels = list(gray.getdata())
        rows: list[str] = []
        for r in range(h):
            row_px = pixels[r * w : (r + 1) * w]
            rows.append("".join(chars[min(len(chars) - 1, (px * len(chars)) // 256)] for px in row_px))
        return "\n".join(rows)
    except Exception:
        return None


def select_and_prepare_image(
    topic: str,
    objective_id: str,
    objective_desc: str,
    *,
    concept_type: str = "",
    explicit_request: bool = False,
    candidates: Sequence[Mapping[str, Any]] | None = None,
    search_fn: Callable[[str], Sequence[Mapping[str, Any]]] | None = None,
    inspect_fn: Callable[[Mapping[str, Any]], Mapping[str, Any]] | None = None,
    host_tools: Mapping[str, Any] | None = None,
    terminal_caps: Mapping[str, Any] | None = None,
    session_dir: Path | None = None,
    local_image_path: Path | None = None,
    what_to_observe: str = "",
    terminal_alternative: str = "",
) -> dict[str, Any]:
    """Select, verify, cache, and terminal-format an educational image with clean fallbacks."""
    t_caps = dict(terminal_caps) if terminal_caps is not None else detect_terminal_capabilities()
    tools = dict(host_tools or {})
    if search_fn is not None:
        tools.setdefault("image_search", True)
    if inspect_fn is not None:
        tools.setdefault("image_inspect", True)

    decision = should_retrieve_image(
        objective_desc,
        concept_type=concept_type,
        explicit_request=explicit_request,
        host_tools=tools,
    )
    query = build_image_query(topic, objective_desc)

    if not decision["retrieve"] and candidates is None:
        return {
            "ok": False,
            "used_image": False,
            "query": query,
            "reason": decision["reason"],
            "render_mode": "text_fallback",
            "fallback_text": terminal_alternative or f"Teach '{objective_desc}' via {decision['alternative']}.",
            "escape_sequences_emitted": False,
        }

    cache_key = f"{objective_id}::{query}"
    cache = _load_media_cache(session_dir)
    if cache_key in cache.get("items", {}) and candidates is None and search_fn is None:
        cached = dict(cache["items"][cache_key])
        cached["from_cache"] = True
        return cached

    raw_candidates = list(candidates) if candidates is not None else (list(search_fn(query)) if search_fn else [])
    if not raw_candidates:
        return {
            "ok": False,
            "used_image": False,
            "query": query,
            "reason": "No image candidates returned by host search.",
            "render_mode": "text_fallback",
            "fallback_text": terminal_alternative or f"No verified image found for '{objective_desc}'; use labeled text diagram.",
            "escape_sequences_emitted": False,
        }

    inspect_avail = bool(tools.get("image_inspect", False))
    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []

    for raw_c in raw_candidates[:8]:
        cand = dict(raw_c)
        if inspect_avail and inspect_fn is not None and cand.get("inspection_passed") is None:
            insp = dict(inspect_fn(cand) or {})
            cand["inspection_passed"] = insp.get("passed")
            if insp.get("notes"):
                cand["inspection_notes"] = insp["notes"]
        ev = evaluate_image_candidate(cand, image_inspect_available=inspect_avail)
        if ev["accepted"]:
            accepted.append(ev)
        else:
            rejected.append({"title": str(cand.get("title") or ""), "reason": ev["reason"]})

    if not accepted:
        return {
            "ok": False,
            "used_image": False,
            "query": query,
            "reason": "All candidate images failed credibility or visual verification checks.",
            "rejected": rejected,
            "render_mode": "text_fallback",
            "fallback_text": terminal_alternative or f"Rejected unreliable candidates for '{objective_desc}'; teach with text diagram.",
            "escape_sequences_emitted": False,
        }

    accepted.sort(key=lambda item: item["score"], reverse=True)
    best = accepted[0]

    inline_payload = {"supported": False, "protocol": "none", "payload": ""}
    ascii_preview: str | None = None
    if local_image_path is not None:
        lp = local_image_path.resolve()
        if session_dir is None or is_within_root(lp, session_dir):
            inline_payload = format_inline_terminal_image(
                lp,
                str(t_caps.get("inline_image_protocol") or "none"),
                is_tty=bool(t_caps.get("is_tty", False)),
            )
            if not inline_payload["supported"] and t_caps.get("pil_available"):
                ascii_preview = optional_ascii_image_preview(lp)

    observe_note = sanitize_untrusted_text(
        what_to_observe or f"Observe the labeled parts relevant to: {objective_desc}.",
        max_len=240,
    )
    fallback_desc = sanitize_untrusted_text(
        terminal_alternative or best["description"] or f"Refer to source URL for labeled diagram of {topic}.",
        max_len=280,
    )

    result = {
        "ok": True,
        "used_image": True,
        "from_cache": False,
        "query": query,
        "selected": {
            "title": best["title"],
            "creator": best["creator"],
            "license": best["license"],
            "source_page_url": best["source_page_url"],
            "asset_url": best["asset_url"],
            "description": best["description"],
            "verification_status": best["verification_status"],
        },
        "what_to_observe": observe_note,
        "render_mode": f"inline_{inline_payload['protocol']}" if inline_payload["supported"] else "text_fallback",
        "inline_payload": inline_payload["payload"],
        "escape_sequences_emitted": bool(inline_payload["supported"]),
        "ascii_preview": ascii_preview,
        "fallback_text": fallback_desc,
        "rejected_count": len(rejected),
        "cached_at": utc_now_iso(),
    }

    if session_dir is not None:
        cache.setdefault("items", {})[cache_key] = dict(result, inline_payload="", escape_sequences_emitted=False)
        _save_media_cache(session_dir, cache)

    return result
