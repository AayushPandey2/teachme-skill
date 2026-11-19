"""Notes-first rapid revision, active recall planning, and shared TeachMe memory integration."""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
import shlex
import uuid
from typing import Any, Mapping, Sequence

from .adaptive_quiz import evaluate_learner_response
from .evidence import (
    derive_session_coverage_and_gaps,
    format_utc_ts,
    normalize_objectives_list,
    parse_utc_ts,
)
from .indexer import resolve_sources
from .models import atomic_write_text, load_config, read_text_safe
from .scheduler import get_due_reviews, load_review_state
from .state_store import (
    init_session_state,
    load_curriculum,
    load_events,
    load_learning_records,
    load_mission,
    normalize_topic_num,
    record_assessment_event,
    resolve_session_dir,
    slugify_topic,
)

RAPID_MODES = ("recall", "mcq", "mixed", "weak", "qa", "exam")

MODE_QUESTION_TYPES: dict[str, list[str]] = {
    "recall": ["recall", "short_conceptual", "formula_recall"],
    "mcq": ["mcq"],
    "mixed": [
        "recall",
        "mcq",
        "formula_recall",
        "comparison",
        "true_false",
        "calculation",
        "predict_output",
        "find_error",
        "application",
    ],
    "weak": ["recall", "find_error", "application", "mcq"],
    "qa": [],
    "exam": ["application", "recall", "mcq", "calculation", "comparison"],
}


def parse_rapid_invocation(raw_args: str) -> dict[str, Any]:
    """Parse /teachme-rapid invocations cleanly without requiring complex CLI syntax."""
    text = str(raw_args or "").strip()
    if text.startswith("/teachme-rapid"):
        text = text[len("/teachme-rapid"):].strip()
    elif text.startswith("/teachme rapid"):
        text = text[len("/teachme rapid"):].strip()

    try:
        tokens = shlex.split(text)
    except ValueError:
        tokens = text.split()

    mode = "mixed"
    mode_explicit = False
    minutes: int | None = None
    questions: int | None = None
    resume = False
    vault: str | None = None
    session_slug: str | None = None
    allow_web = False
    allow_general = False
    difficulty: int | None = None
    positional: list[str] = []

    i = 0
    while i < len(tokens):
        tok = tokens[i]
        low = tok.lower()
        if low in ("--resume", "-r"):
            resume = True
            i += 1
        elif low == "--mode" and i + 1 < len(tokens):
            cand = tokens[i + 1].strip().lower()
            if cand == "q&a":
                cand = "qa"
            if cand not in RAPID_MODES:
                raise ValueError(f"Unsupported rapid mode {cand!r}; expected {RAPID_MODES}")
            mode = cand
            mode_explicit = True
            i += 2
        elif low in ("--minutes", "--time") and i + 1 < len(tokens):
            minutes = max(1, int(tokens[i + 1]))
            i += 2
        elif low in ("--questions", "-q", "-n") and i + 1 < len(tokens):
            questions = max(1, min(50, int(tokens[i + 1])))
            i += 2
        elif low == "--vault" and i + 1 < len(tokens):
            vault = tokens[i + 1]
            i += 2
        elif low == "--session" and i + 1 < len(tokens):
            session_slug = tokens[i + 1]
            i += 2
        elif low == "--difficulty" and i + 1 < len(tokens):
            difficulty = max(1, min(3, int(tokens[i + 1])))
            i += 2
        elif low in ("--allow-web", "--web"):
            allow_web = True
            i += 1
        elif low in ("--allow-general", "--general"):
            allow_general = True
            i += 1
        elif tok.startswith("--"):
            i += 1
        else:
            positional.append(tok)
            i += 1

    topic = " ".join(positional).strip()
    if questions is not None:
        budget = questions
    elif minutes is not None:
        budget = max(4, min(25, round(minutes * 0.8)))
    else:
        budget = 10

    return {
        "topic": topic,
        "mode": mode,
        "mode_explicit": mode_explicit,
        "minutes": minutes,
        "questions": budget,
        "questions_explicit": questions is not None,
        "resume": resume,
        "vault": vault,
        "session_slug": session_slug,
        "allow_web": allow_web,
        "allow_general": allow_general,
        "difficulty": difficulty,
    }


def _rapid_session_path(session_dir: Path) -> Path:
    return session_dir / "scratchpad" / "rapid-session.json"


def load_rapid_session(session_dir: Path) -> dict[str, Any] | None:
    path = _rapid_session_path(session_dir)
    if not path.is_file():
        return None
    try:
        data = json.loads(read_text_safe(path))
        return data if isinstance(data, dict) else None
    except (OSError, json.JSONDecodeError):
        return None


def save_rapid_session(session_dir: Path, state: dict[str, Any]) -> Path:
    path = _rapid_session_path(session_dir)
    atomic_write_text(path, json.dumps(state, indent=2, ensure_ascii=False) + "\n")
    return path


def _safe_try_resolve_session(
    vault_or_session: str | None,
    *,
    session_slug: str | None = None,
    topic_hint: str = "",
) -> Path | None:
    # If vault_or_session is a direct operational session directory, use it
    if vault_or_session:
        cand = Path(os.path.expandvars(vault_or_session)).expanduser().resolve()
        if (cand / "00-SESSION-STATE.md").is_file() or (cand / "00-GRAPH.json").is_file():
            return cand
    if session_slug:
        try:
            return resolve_session_dir(vault_or_session, session_slug=session_slug)
        except FileNotFoundError:
            pass
    if topic_hint:
        try:
            return resolve_session_dir(vault_or_session, session_slug=slugify_topic(topic_hint))
        except FileNotFoundError:
            pass
    try:
        return resolve_session_dir(vault_or_session)
    except FileNotFoundError:
        return None


def _extract_testable_units_from_sections(
    matched_sections: Sequence[Mapping[str, Any]],
    related_notes: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Extract grounded testable note units strictly from retrieved vault sections."""
    units: list[dict[str, Any]] = []
    seen_keys: set[str] = set()

    for sec in matched_sections:
        rel_path = str(sec.get("rel_path") or "")
        heading = str(sec.get("heading") or "Overview")
        content = str(sec.get("content") or "").strip()
        if not content:
            continue

        # Detect potential ambiguity/stub/error flags in retrieved note content
        warnings: list[str] = []
        low_content = content.lower()
        if any(marker in low_content for marker in ("todo", "fixme", "???", "check this", "verify")):
            warnings.append("Note section contains unfinished/verification marker; verify claims before asserting as fact.")
        has_math = "$$" in content or "$" in content or bool(re.search(r"[=<>+\-*/^]", content))
        has_code = "```" in content or bool(re.search(r"\b(int|void|def|return|printf|malloc)\b", content))
        if has_math or has_code:
            warnings.append("Contains mathematical or code claim; verify result deterministically before grading.")

        # Split section into clean bullet/sentence units while staying grounded in exact heading
        raw_lines = [ln.strip() for ln in content.splitlines() if ln.strip() and not ln.strip().startswith("#")]
        facts: list[str] = []
        for ln in raw_lines:
            cleaned = re.sub(r"^[-*+]\s+", "", ln).strip()
            if len(cleaned) >= 12:
                facts.append(cleaned)
        if not facts:
            facts = [content[:350]]

        unit_key = f"{rel_path}::{heading}"
        if unit_key in seen_keys:
            continue
        seen_keys.add(unit_key)
        units.append(
            {
                "unit_key": unit_key,
                "source_origin": "vault_note",
                "untrusted_source": True,
                "rel_path": rel_path,
                "note_title": str(sec.get("note_title") or Path(rel_path).stem),
                "heading": heading,
                "heading_path": list(sec.get("heading_path") or [heading]),
                "anchor": str(sec.get("anchor") or ""),
                "excerpt": content[:700],
                "candidate_facts": facts[:6],
                "has_code": has_code,
                "has_math": has_math,
                "note_verification_warnings": warnings,
                "matched_objectives": list(sec.get("matched_objectives") or []),
            }
        )

    for rel in related_notes:
        rel_path = str(rel.get("rel_path") or "")
        excerpt = str(rel.get("excerpt") or "").strip()
        if not excerpt or not rel_path:
            continue
        anchor = str(rel.get("anchor") or rel.get("relation") or "related")
        unit_key = f"{rel_path}::{anchor}"
        if unit_key in seen_keys:
            continue
        seen_keys.add(unit_key)
        units.append(
            {
                "unit_key": unit_key,
                "source_origin": "vault_note_related",
                "untrusted_source": True,
                "rel_path": rel_path,
                "note_title": str(rel.get("title") or Path(rel_path).stem),
                "heading": anchor,
                "heading_path": [str(rel.get("title") or Path(rel_path).stem), anchor],
                "anchor": anchor,
                "excerpt": excerpt[:500],
                "candidate_facts": [excerpt[:300]],
                "has_code": "```" in excerpt,
                "has_math": "$" in excerpt,
                "note_verification_warnings": [],
                "matched_objectives": [],
            }
        )
    return units


def _build_session_objective_signals(session_dir: Path | None) -> dict[str, Any]:
    """Load objective proficiency, weak spots, due items, misconceptions, and exam scope."""
    if session_dir is None:
        return {
            "curriculum": None,
            "mission": {},
            "objectives_by_id": {},
            "weak_objective_ids": set(),
            "due_objective_ids": set(),
            "assisted_objective_ids": set(),
            "untested_required_ids": set(),
            "in_scope_terms": set(),
            "misconceptions": [],
        }

    curriculum = load_curriculum(session_dir)
    events = load_events(session_dir)
    mission = load_mission(session_dir)
    rev_store = load_review_state(session_dir)
    due = get_due_reviews(curriculum, events, rev_store, limit=30)
    cov = derive_session_coverage_and_gaps(curriculum, events, mission=mission, review_due=due)
    lrs = [r for r in load_learning_records(session_dir) if not str(r.get("status", "")).startswith("superseded")]

    objectives_by_id: dict[str, dict[str, Any]] = {}
    weak_ids: set[str] = set()
    assisted_ids: set[str] = set()
    untested_req_ids: set[str] = set()
    due_ids = {d["objective_id"] for d in due}

    for obj in cov.get("objectives", []):
        oid = obj["objective_id"]
        objectives_by_id[oid] = obj
        pstat = obj["proficiency_status"]
        if pstat == "weakened" or obj["unresolved_gaps"]:
            weak_ids.add(oid)
        if pstat == "practiced_with_support":
            assisted_ids.add(oid)
        if obj.get("required") and obj.get("in_scope", True) and pstat in ("untested", "introduced"):
            untested_req_ids.add(oid)

    # Also inspect events directly for prior failures even if later partially resolved
    for ev in events:
        if str(ev.get("result") or ev.get("status") or "").lower() == "fail" and ev.get("objective_id"):
            if objectives_by_id.get(ev["objective_id"], {}).get("proficiency_status") != "demonstrated_independently":
                weak_ids.add(str(ev["objective_id"]))

    scope_blob = " ".join(
        [
            str(mission.get("goal") or ""),
            " ".join(str(x) for x in (mission.get("in_scope") or [])),
        ]
    ).lower()
    in_scope_terms = {t for t in re.findall(r"[a-z0-9]+", scope_blob) if len(t) >= 3}

    return {
        "curriculum": curriculum,
        "mission": mission,
        "objectives_by_id": objectives_by_id,
        "weak_objective_ids": weak_ids,
        "due_objective_ids": due_ids,
        "assisted_objective_ids": assisted_ids,
        "untested_required_ids": untested_req_ids,
        "in_scope_terms": in_scope_terms,
        "misconceptions": [
            {
                "file": r["file"],
                "title": r["title"],
                "context": r["context"],
                "insight": r["insight"],
            }
            for r in lrs
        ],
    }


def _map_unit_to_objective(
    unit: Mapping[str, Any],
    signals: Mapping[str, Any],
) -> tuple[str | None, str | None, int, list[str]]:
    """Link a vault note unit to an existing TeachMe objective ID & priority weight."""
    objectives_by_id: dict[str, dict[str, Any]] = signals.get("objectives_by_id", {})
    if not objectives_by_id:
        return None, None, 0, []

    unit_blob = f"{unit['rel_path']} {unit['heading']} {unit['excerpt']}".lower()
    unit_terms = {t for t in re.findall(r"[a-z0-9]+", unit_blob) if len(t) >= 3}
    heading_terms = {t for t in re.findall(r"[a-z0-9]+", str(unit.get("heading") or "").lower()) if len(t) >= 3}

    curriculum_nodes = (signals.get("curriculum") or {}).get("nodes") or {}
    matched_set = set(unit.get("matched_objectives") or [])

    best_oid: str | None = None
    best_tnum: str | None = None
    best_score = 0

    for oid, oinfo in objectives_by_id.items():
        if not oinfo.get("in_scope", True):
            continue
        node = curriculum_nodes.get(oinfo["topic_id"]) or {}
        obj_blob = f"{node.get('title', '')} {oinfo['description']}".lower()
        obj_terms = {t for t in re.findall(r"[a-z0-9]+", obj_blob) if len(t) >= 3}
        score = (len(heading_terms & obj_terms) * 4) + len(unit_terms & obj_terms)
        if oid in matched_set:
            score += 2
        if score > best_score:
            best_score = score
            best_oid = oid
            best_tnum = normalize_topic_num(oinfo["topic_id"])

    reasons: list[str] = []
    priority = 0
    if best_oid:
        if best_oid in signals["weak_objective_ids"]:
            priority += 50
            reasons.append("weak_or_failed_objective")
        if best_oid in signals["due_objective_ids"]:
            priority += 35
            reasons.append("due_for_review")
        if best_oid in signals["assisted_objective_ids"]:
            priority += 25
            reasons.append("assisted_only_needs_unaided_check")
        if best_oid in signals["untested_required_ids"]:
            priority += 20
            reasons.append("untested_required_objective")

    # Check misconception text overlap even if objective didn't match directly
    for mc in signals.get("misconceptions", []):
        mc_blob = f"{mc.get('title', '')} {mc.get('context', '')}".lower()
        mc_terms = {t for t in re.findall(r"[a-z0-9]+", mc_blob) if len(t) >= 4}
        if len(unit_terms & mc_terms) >= 1:
            priority += 40
            reasons.append(f"misconception:{mc['title']}")

    if signals.get("in_scope_terms") and (unit_terms & signals["in_scope_terms"]):
        priority += 15
        reasons.append("in_exam_scope")

    return best_oid, best_tnum, priority, reasons


def _choose_question_type(mode: str, unit: Mapping[str, Any], idx: int) -> str:
    if mode == "mcq":
        return "mcq"
    if mode == "recall":
        return "formula_recall" if unit.get("has_math") and idx % 2 == 1 else "recall"
    if mode == "qa":
        return "qa"
    pool = list(MODE_QUESTION_TYPES.get(mode, MODE_QUESTION_TYPES["mixed"]))
    if not unit.get("has_code") and "predict_output" in pool:
        pool.remove("predict_output")
    if not unit.get("has_math") and "calculation" in pool:
        pool.remove("calculation")
    if not pool:
        pool = ["recall"]
    return pool[idx % len(pool)]


def build_rapid_plan(
    raw_args: str = "",
    *,
    vault_path: str | None = None,
    vault_ref: str | None = None,
    session_slug: str | None = None,
    now: str | None = None,
) -> dict[str, Any]:
    """Build a notes-first rapid revision plan strictly grounded in retrieved vault notes."""
    parsed = parse_rapid_invocation(raw_args)
    eff_session_slug = session_slug or parsed["session_slug"]
    eff_vault_ref = vault_ref or parsed["vault"]

    sess_dir = _safe_try_resolve_session(
        vault_path,
        session_slug=eff_session_slug,
        topic_hint=parsed["topic"],
    )
    prev_rapid = load_rapid_session(sess_dir) if sess_dir else None

    if parsed["resume"] and prev_rapid:
        if not parsed["topic"]:
            parsed["topic"] = str(prev_rapid.get("topic") or "")
        if not parsed["mode_explicit"] and prev_rapid.get("mode"):
            parsed["mode"] = str(prev_rapid["mode"])
        if not parsed["questions_explicit"] and prev_rapid.get("question_budget"):
            parsed["questions"] = int(prev_rapid["question_budget"])
        if parsed["difficulty"] is None and prev_rapid.get("current_difficulty"):
            parsed["difficulty"] = int(prev_rapid["current_difficulty"])

    topic_query = parsed["topic"].strip()
    signals = _build_session_objective_signals(sess_dir)
    if not topic_query and signals.get("curriculum"):
        topic_query = str(signals["curriculum"].get("topic") or "").strip()

    # Notes-first resolution: web_available=False by default unless user explicitly opted into web augmentation
    src_res = resolve_sources(
        topic_query or "revision",
        vault_path=vault_path,
        vault_ref=eff_vault_ref,
        session_dir=sess_dir,
        web_available=bool(parsed["allow_web"]),
        max_notes=6,
        max_sections_per_note=5,
        max_total_chars=12000,
    )
    if not src_res.get("matched_sections") and sess_dir is not None and topic_query:
        # Topic-level vault lookup fallback when curriculum objective phrasing did not match note prose 1:1
        topic_src_res = resolve_sources(
            topic_query,
            vault_path=vault_path,
            vault_ref=eff_vault_ref,
            session_dir=None,
            web_available=bool(parsed["allow_web"]),
            max_notes=6,
            max_sections_per_note=5,
            max_total_chars=12000,
        )
        if topic_src_res.get("matched_sections"):
            src_res = topic_src_res

    matched_sections = list(src_res.get("matched_sections") or [])
    related_notes = list(src_res.get("related_notes") or [])

    # Strictly filter out web/missing supplementation unless explicitly requested
    web_aug_targets: list[dict[str, Any]] = []
    if parsed["allow_web"] and src_res.get("mode") in ("hybrid", "web"):
        web_aug_targets = [
            {**m, "source_origin": "external_web"}
            for m in (src_res.get("missing_coverage") or [])
        ]

    # Handle case where NO usable vault notes exist
    if not matched_sections and not parsed["allow_general"]:
        return {
            "ok": True,
            "ready": False,
            "status": "no_usable_notes",
            "notes_grounded": False,
            "query": topic_query,
            "mode": parsed["mode"],
            "source_mode": src_res.get("mode"),
            "vault": src_res.get("vault"),
            "message": (
                "No usable study notes covering this topic were found in the configured Obsidian vault. "
                "Rapid revision is notes-first by default and will not silently invent note coverage."
            ),
            "next_options": [
                "Connect or select an Obsidian vault containing notes for this topic (`vault_cli.py connect <path>` or `--vault <name>`).",
                "Explicitly opt into non-note-based general revision (`--allow-general` or `--allow-web`).",
            ],
            "study_notes_modified": False,
        }

    units = _extract_testable_units_from_sections(matched_sections, related_notes)
    asked_keys = set(prev_rapid.get("asked_keys", [])) if (parsed["resume"] and prev_rapid) else set()

    enriched_items: list[dict[str, Any]] = []
    for idx, unit in enumerate(units):
        oid, tnum, prio, reasons = _map_unit_to_objective(unit, signals)
        if parsed["mode"] == "weak" and not reasons:
            # Keep note-grounded items available as fallback if no weak objective matched, but rank lower
            prio -= 10
        qtype = _choose_question_type(parsed["mode"], unit, idx)
        item_key = f"{unit['unit_key']}::{qtype}"
        if item_key in asked_keys:
            continue
        enriched_items.append(
            {
                "question_id": f"rq-{idx + 1:02d}",
                "item_key": item_key,
                "objective_id": oid,
                "topic_num": tnum,
                "source_origin": unit["source_origin"],
                "untrusted_source": True,
                "source_path": unit["rel_path"],
                "source_heading": unit["heading"],
                "heading_path": unit["heading_path"],
                "question_type": qtype,
                "priority_score": prio,
                "priority_reasons": reasons,
                "excerpt": unit["excerpt"],
                "candidate_facts": unit["candidate_facts"],
                "note_verification_warnings": unit["note_verification_warnings"],
                "answer_key_contract": {
                    "require_note_grounding": True,
                    "track_expected_answer": True,
                    "track_rubric": True,
                    "track_valid_alternatives": True,
                    "track_misconception": True,
                },
            }
        )

    # Sort by priority (weak/due/assisted/misconception first), then interleave across distinct headings/files
    enriched_items.sort(key=lambda it: (-it["priority_score"], it["source_path"], it["source_heading"]))
    buckets: dict[str, list[dict[str, Any]]] = {}
    for item in enriched_items:
        buckets.setdefault(item["source_path"], []).append(item)
    interleaved: list[dict[str, Any]] = []
    bucket_lists = list(buckets.values())
    while any(bucket_lists):
        for bl in bucket_lists:
            if bl:
                interleaved.append(bl.pop(0))

    budget = parsed["questions"]
    planned_items = interleaved[:budget]
    start_diff = parsed["difficulty"] or 1
    if start_diff == 1 and signals.get("objectives_by_id"):
        # Start at level 2 only if matched objectives already have independent demonstrations and no weakness
        matched_objs = [
            signals["objectives_by_id"][it["objective_id"]]
            for it in planned_items
            if it.get("objective_id") and it["objective_id"] in signals["objectives_by_id"]
        ]
        if matched_objs and all(o["proficiency_status"] == "demonstrated_independently" for o in matched_objs):
            start_diff = 2

    # Determine operational session directory to persist rapid-session.json
    if sess_dir is None and parsed["mode"] != "qa":
        slug = eff_session_slug or slugify_topic(topic_query or "rapid-revision")
        vault_info = src_res.get("vault") or {}
        if vault_info.get("accessible") and vault_info.get("path"):
            vpath = Path(vault_info["path"])
            sess_dir = resolve_session_dir(str(vpath), session_slug=slug, topic_hint=topic_query, for_init=True)
            mode_str = "vault-native"
        else:
            cfg = load_config()
            raw_root = str(cfg.get("notes_root", "")).strip()
            base_root = Path(os.path.expandvars(raw_root)).expanduser().resolve() if raw_root else (Path.home() / "notes").resolve()
            sess_dir = base_root / slug
            mode_str = "standalone"
        init_session_state(
            sess_dir,
            topic_title=topic_query or slug,
            items=[
                {
                    "slug": f"01-{slug}",
                    "title": topic_query or slug,
                    "objective": f"Rapid active recall on {topic_query or slug} grounded in notes.",
                }
            ],
            mode=mode_str,
        )

    now_iso = format_utc_ts(parse_utc_ts(now))
    if parsed["resume"] and prev_rapid:
        rapid_state = dict(prev_rapid)
        rapid_state["updated_at"] = now_iso
    else:
        rapid_state = {
            "schema_version": 1,
            "run_id": f"rapid-{uuid.uuid4().hex[:8]}",
            "topic": topic_query,
            "mode": parsed["mode"],
            "question_budget": budget,
            "requested_minutes": parsed["minutes"],
            "current_difficulty": start_diff,
            "questions_answered": 0,
            "correct_count": 0,
            "partial_count": 0,
            "incorrect_count": 0,
            "skipped_count": 0,
            "consecutive_correct": 0,
            "consecutive_wrong": 0,
            "asked_keys": [],
            "strong_concepts": [],
            "needs_practice": [],
            "pending_followups": [],
            "responses": [],
            "started_at": now_iso,
            "updated_at": now_iso,
        }

    if sess_dir is not None and parsed["mode"] != "qa":
        save_rapid_session(sess_dir, rapid_state)

    return {
        "ok": True,
        "ready": True,
        "status": "qa_ready" if parsed["mode"] == "qa" else ("resumed" if (parsed["resume"] and prev_rapid) else "ready"),
        "resumed": bool(parsed["resume"] and prev_rapid),
        "notes_grounded": bool(matched_sections),
        "general_opt_in": bool(not matched_sections and parsed["allow_general"]),
        "force_quiz": parsed["mode"] != "qa",
        "record_test_results": parsed["mode"] != "qa",
        "exam_probability_claims": "disabled" if parsed["mode"] == "exam" else None,
        "query": topic_query,
        "mode": parsed["mode"],
        "source_mode": src_res.get("mode"),
        "web_supplementation_blocked": src_res.get("mode") in ("hybrid", "web") and not parsed["allow_web"],
        "web_augmentation_targets": web_aug_targets,
        "session_dir": str(sess_dir) if sess_dir else None,
        "vault": src_res.get("vault"),
        "relevant_vault_paths": src_res.get("relevant_vault_paths", []),
        "question_budget": rapid_state["question_budget"],
        "questions_answered_so_far": rapid_state["questions_answered"],
        "current_difficulty": rapid_state["current_difficulty"],
        "pending_followups": rapid_state["pending_followups"],
        "planned_items": planned_items,
        "next_item": planned_items[0] if planned_items else None,
        "active_misconceptions": signals.get("misconceptions", [])[:6],
        "source_provenance": src_res.get("source_provenance", []),
        "timing_note": "Active study time is not measured automatically in conversational mode; use question-count budget.",
        "study_notes_modified": False,
    }


def record_rapid_answer(
    session_dir: Path,
    *,
    item_key: str,
    concept_label: str,
    learner_answer: str = "",
    question_spec: Mapping[str, Any] | None = None,
    result: str | None = None,
    assistance: str = "none",
    topic_num: str | None = None,
    objective_id: str | None = None,
    misconception: str | None = None,
    rationale: str = "",
    active_time: float | None = None,
    now: str | None = None,
) -> dict[str, Any]:
    """Check/record a single rapid-revision response and update shared TeachMe memory safely."""
    rapid_state = load_rapid_session(session_dir)
    if rapid_state is None:
        raise FileNotFoundError(f"No rapid-session.json found under {session_dir}")

    if rapid_state.get("mode") == "qa":
        return {
            "ok": True,
            "mode": "qa",
            "recorded_test_result": False,
            "note": "Q&A-only interactions do not create artificial test results.",
            "study_notes_modified": False,
        }

    eval_out: dict[str, Any] | None = None
    eff_result = result
    if eff_result is None and question_spec:
        eval_out = evaluate_learner_response(question_spec, learner_answer)
        if eval_out.get("verification_mode") != "rubric_review_required":
            eff_result = str(eval_out["suggested_result"])

    if not eff_result:
        raise ValueError("Either --result or a deterministic --question-spec with --answer is required")

    norm_res = eff_result.strip().lower()
    if norm_res not in ("pass", "partial", "fail", "skipped"):
        raise ValueError(f"Unsupported rapid result: {eff_result!r}")

    now_iso = format_utc_ts(parse_utc_ts(now))
    rapid_state["questions_answered"] = int(rapid_state.get("questions_answered", 0)) + (0 if norm_res == "skipped" else 1)
    if norm_res == "pass":
        rapid_state["correct_count"] = int(rapid_state.get("correct_count", 0)) + 1
        if assistance == "none":
            rapid_state["consecutive_correct"] = int(rapid_state.get("consecutive_correct", 0)) + 1
            rapid_state["consecutive_wrong"] = 0
            if rapid_state["consecutive_correct"] >= 2:
                rapid_state["current_difficulty"] = min(3, int(rapid_state.get("current_difficulty", 1)) + 1)
            if concept_label and concept_label not in rapid_state["strong_concepts"]:
                rapid_state["strong_concepts"].append(concept_label)
        else:
            rapid_state["consecutive_correct"] = 0
            if concept_label and concept_label not in rapid_state["needs_practice"]:
                rapid_state["needs_practice"].append(concept_label)
    elif norm_res == "partial":
        rapid_state["partial_count"] = int(rapid_state.get("partial_count", 0)) + 1
        rapid_state["consecutive_correct"] = 0
        if concept_label and concept_label not in rapid_state["needs_practice"]:
            rapid_state["needs_practice"].append(concept_label)
    elif norm_res == "fail":
        rapid_state["incorrect_count"] = int(rapid_state.get("incorrect_count", 0)) + 1
        rapid_state["consecutive_correct"] = 0
        rapid_state["consecutive_wrong"] = int(rapid_state.get("consecutive_wrong", 0)) + 1
        if rapid_state["consecutive_wrong"] >= 2:
            rapid_state["current_difficulty"] = 1
        if concept_label and concept_label not in rapid_state["needs_practice"]:
            rapid_state["needs_practice"].append(concept_label)
        # Schedule a fresh related follow-up (different angle, not exact duplicate question)
        rapid_state.setdefault("pending_followups", []).append(
            {
                "concept": concept_label,
                "reason": misconception or rationale or "Incorrect rapid recall",
                "require_fresh_variant": True,
                "queued_at": now_iso,
            }
        )
    else:
        rapid_state["skipped_count"] = int(rapid_state.get("skipped_count", 0)) + 1

    if item_key and item_key not in rapid_state.get("asked_keys", []):
        rapid_state.setdefault("asked_keys", []).append(item_key)

    if active_time is not None and float(active_time) >= 0:
        prev_time = float(rapid_state.get("active_time_total_sec") or 0.0)
        rapid_state["active_time_total_sec"] = round(prev_time + float(active_time), 2)

    rapid_state.setdefault("responses", []).append(
        {
            "ts": now_iso,
            "item_key": item_key,
            "concept": concept_label,
            "result": norm_res,
            "assistance": assistance,
            "objective_id": objective_id,
        }
    )
    rapid_state["updated_at"] = now_iso
    save_rapid_session(session_dir, rapid_state)

    # Update shared TeachMe assessment evidence when a valid objective/topic exists
    # Pass session_run so same-session repeated recall NEVER counts as delayed retention!
    assessment_out: dict[str, Any] | None = None
    if topic_num and objective_id:
        curr = load_curriculum(session_dir)
        node_id = f"topic-{normalize_topic_num(topic_num)}"
        node = (curr.get("nodes") or {}).get(node_id) or {}
        valid_oids = {o["id"] for o in normalize_objectives_list(node_id, node)} if node else set()
        if objective_id in valid_oids:
            assessment_out = record_assessment_event(
                session_dir,
                topic=topic_num,
                objective=objective_id,
                result=norm_res,
                assistance=assistance,
                assessment_type="short_conceptual",
                item_id=item_key[:64],
                rationale=rationale or f"Rapid recall ({concept_label})",
                misconception=misconception,
                active_time=active_time,
                session_run=str(rapid_state["run_id"]),
                now=now_iso,
            )

    return {
        "ok": True,
        "result": norm_res,
        "assistance": assistance,
        "evaluation": eval_out,
        "current_difficulty": rapid_state["current_difficulty"],
        "questions_answered": rapid_state["questions_answered"],
        "question_budget": rapid_state["question_budget"],
        "pending_followups_count": len(rapid_state.get("pending_followups", [])),
        "shared_assessment_recorded": assessment_out is not None,
        "assessment_event": assessment_out,
        "delayed_retention_recorded": False,
        "study_notes_modified": False,
    }


def build_rapid_status_report(session_dir: Path) -> dict[str, Any]:
    """Generate an honest, compact end-of-session rapid revision summary."""
    rapid_state = load_rapid_session(session_dir)
    if rapid_state is None:
        raise FileNotFoundError(f"No rapid-session.json found under {session_dir}")

    budget = int(rapid_state.get("question_budget", 0))
    answered = int(rapid_state.get("questions_answered", 0))
    unanswered = max(0, budget - answered)
    needs_practice = list(rapid_state.get("needs_practice", []))
    strong = [c for c in rapid_state.get("strong_concepts", []) if c not in needs_practice]

    if needs_practice:
        suggested = f"3 targeted questions on {needs_practice[0]}"
    elif unanswered > 0:
        suggested = f"Resume rapid revision ({unanswered} budgeted questions remaining)"
    else:
        suggested = "Wait for spaced review via /teachme-review to test delayed retention"

    active_t = rapid_state.get("active_time_total_sec")
    return {
        "ok": True,
        "topic": rapid_state.get("topic", ""),
        "mode": rapid_state.get("mode", "mixed"),
        "questions_budgeted": budget,
        "questions_answered": answered,
        "unanswered_count": unanswered,
        "correct": int(rapid_state.get("correct_count", 0)),
        "partial": int(rapid_state.get("partial_count", 0)),
        "incorrect": int(rapid_state.get("incorrect_count", 0)),
        "skipped": int(rapid_state.get("skipped_count", 0)),
        "strong": strong,
        "needs_practice": needs_practice,
        "suggested_next_step": suggested,
        "delayed_retention_recorded": False,
        "active_time_sec": active_t if active_t is not None else "unavailable",
        "study_notes_modified": False,
    }
