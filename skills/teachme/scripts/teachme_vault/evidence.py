"""Objective-level coverage, assistance-aware proficiency evidence, and media provenance."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from typing import Any
import uuid

from .models import atomic_write_text, is_within_root, read_text_safe, utc_now_iso

EVIDENCE_SCHEMA_VERSION = 2
CURRICULUM_SCHEMA_VERSION = 2
MEDIA_PROVENANCE_SCHEMA_VERSION = 1

COVERAGE_STATUSES = (
    "not_taught",
    "introduced",
    "assessed",
    "demonstrated",
    "unresolved",
    "out_of_scope",
)

PREREQUISITE_STATES = ("unknown", "needs_support", "demonstrated")

ASSISTANCE_LEVELS = ("none", "hint", "scaffold", "worked_example", "unknown")

ASSESSMENT_RESULTS = ("pass", "partial", "fail", "skipped")

ASSESSMENT_TYPES = (
    "prediction",
    "worked_example_completion",
    "independent_application",
    "find_first_error",
    "method_justification",
    "violated_assumption",
    "counterexample",
    "concept_comparison",
    "why_tempting_fails",
    "predict_output",
    "debug_program",
    "transfer",
    "delayed_recall",
    "feynman_explanation",
    "multiple_choice",
    "short_conceptual",
    "numerical_calculation",
    "fill_missing_step",
    "diagnostic",
    "legacy_checkpoint",
)

ASSESSMENT_DIMENSIONS = (
    "explain_concept",
    "apply_procedure",
    "identify_assumptions",
    "recognize_failure",
    "transfer",
    "delayed_recall",
)

ASSESSMENT_TYPE_TO_DIMENSION: dict[str, str] = {
    "prediction": "explain_concept",
    "feynman_explanation": "explain_concept",
    "concept_comparison": "explain_concept",
    "multiple_choice": "explain_concept",
    "short_conceptual": "explain_concept",
    "worked_example_completion": "apply_procedure",
    "independent_application": "apply_procedure",
    "method_justification": "apply_procedure",
    "predict_output": "apply_procedure",
    "debug_program": "apply_procedure",
    "numerical_calculation": "apply_procedure",
    "fill_missing_step": "apply_procedure",
    "violated_assumption": "identify_assumptions",
    "find_first_error": "recognize_failure",
    "counterexample": "recognize_failure",
    "why_tempting_fails": "recognize_failure",
    "transfer": "transfer",
    "delayed_recall": "delayed_recall",
}

PROFICIENCY_STATUSES = (
    "untested",
    "introduced",
    "practiced_with_support",
    "demonstrated_independently",
    "weakened",
    "legacy_unverified",
)

VERIFICATION_STATUSES = (
    "inspected_verified",
    "metadata_only_unverified",
    "generated_plot",
    "local_diagram",
    "unverified",
)

ALLOWED_MEDIA_EXTENSIONS = frozenset(
    {".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg", ".csv", ".json", ".txt", ".md"}
)
BLOCKED_ACTIVE_EXTENSIONS = frozenset(
    {".exe", ".bat", ".cmd", ".ps1", ".sh", ".dll", ".so", ".msi", ".vbs", ".scr"}
)
MAX_MEDIA_FILE_BYTES = 10 * 1024 * 1024
DEFAULT_MIN_RETENTION_DELAY_HOURS = 12.0


def parse_utc_ts(raw: str | datetime | None) -> datetime:
    """Parse ISO-8601 timestamp (or date) into a UTC-aware datetime."""
    if raw is None:
        return datetime.now(timezone.utc)
    if isinstance(raw, datetime):
        if raw.tzinfo is None:
            return raw.replace(tzinfo=timezone.utc)
        return raw.astimezone(timezone.utc)
    text = str(raw).strip()
    if not text:
        return datetime.now(timezone.utc)
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
        text = f"{text}T00:00:00+00:00"
    elif text.endswith("Z"):
        text = text[:-1] + "+00:00"
    dt = datetime.fromisoformat(text)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def format_utc_ts(dt: datetime) -> str:
    """Format a datetime as canonical UTC ISO-8601 string."""
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def normalize_result(raw_status: str) -> str:
    """Normalize legacy or v2 assessment outcome into ASSESSMENT_RESULTS."""
    val = str(raw_status or "").strip().lower()
    if val == "retry":
        return "fail"
    if val in ASSESSMENT_RESULTS:
        return val
    raise ValueError(f"Unsupported assessment result: {raw_status!r}")


def normalize_assistance(raw_assistance: str | None) -> str:
    """Normalize assistance level; never fabricates independent ('none') status."""
    if raw_assistance is None or not str(raw_assistance).strip():
        return "unknown"
    val = str(raw_assistance).strip().lower()
    if val not in ASSISTANCE_LEVELS:
        raise ValueError(
            f"Unsupported assistance level {raw_assistance!r}; expected one of {ASSISTANCE_LEVELS}"
        )
    return val


def normalize_assessment_type(raw_type: str | None, legacy_cp: int | None = None) -> str:
    """Normalize assessment type; defaults legacy ticks to 'legacy_checkpoint'."""
    if raw_type is None or not str(raw_type).strip():
        return "legacy_checkpoint" if legacy_cp is not None else "independent_application"
    val = str(raw_type).strip().lower()
    if val not in ASSESSMENT_TYPES:
        raise ValueError(
            f"Unsupported assessment_type {raw_type!r}; expected one of {ASSESSMENT_TYPES}"
        )
    return val


def normalize_prerequisite_state(raw_state: str | None) -> str:
    val = str(raw_state or "unknown").strip().lower()
    if val not in PREREQUISITE_STATES:
        raise ValueError(
            f"Unsupported prerequisite state {raw_state!r}; expected one of {PREREQUISITE_STATES}"
        )
    return val


def default_objective_for_node(node_id: str, node: dict[str, Any]) -> dict[str, Any]:
    """Synthesize a deterministic primary objective when a node uses legacy single-objective format."""
    num = node_id.replace("topic-", "")
    desc = str(node.get("objective") or node.get("title") or node_id).strip()
    in_scope = bool(node.get("in_scope", True))
    required = bool(node.get("required", True)) if in_scope else False
    return {
        "id": f"obj-{num}-01",
        "description": desc,
        "required": required,
        "in_scope": in_scope,
        "prerequisite_refs": list(node.get("depends_on", []) or []),
        "assumptions": list(node.get("assumptions", []) or []),
        "expected_assessments": list(node.get("expected_assessments", []) or []),
        "coverage_status": "out_of_scope" if not in_scope else str(node.get("coverage_status") or "not_taught"),
        "proficiency": _empty_proficiency(),
        "evidence_summary": "",
        "unresolved_gaps": [],
    }


def _empty_proficiency() -> dict[str, Any]:
    return {
        "status": "untested",
        "independent_successes": 0,
        "assisted_successes": 0,
        "unknown_assistance_passes": 0,
        "failures": 0,
        "partial_count": 0,
        "dimensions_evidenced": [],
        "dimensions_assisted": [],
        "retention": {"status": "untested", "last_verified_at": None, "prior_verified_at": None},
        "transfer": {"status": "untested", "last_verified_at": None, "prior_verified_at": None, "contexts": []},
        "legacy_completed": False,
        "prior_independent_success_at": None,
        "current_weakness": None,
    }


def normalize_objectives_list(node_id: str, node: dict[str, Any]) -> list[dict[str, Any]]:
    """Normalize objectives on a curriculum node without discarding existing evidence."""
    raw_objs = node.get("objectives")
    if not isinstance(raw_objs, list) or not raw_objs:
        return [default_objective_for_node(node_id, node)]

    num = node_id.replace("topic-", "")
    out: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for idx, raw in enumerate(raw_objs, start=1):
        if isinstance(raw, str):
            raw = {"description": raw}
        if not isinstance(raw, dict):
            continue
        oid = str(raw.get("id") or f"obj-{num}-{idx:02d}").strip()
        if oid in seen_ids:
            oid = f"{oid}-{idx}"
        seen_ids.add(oid)
        in_scope = bool(raw.get("in_scope", node.get("in_scope", True)))
        required = bool(raw.get("required", True)) if in_scope else False
        cov = str(raw.get("coverage_status") or ("out_of_scope" if not in_scope else "not_taught"))
        if cov not in COVERAGE_STATUSES:
            cov = "not_taught"
        prof = raw.get("proficiency") if isinstance(raw.get("proficiency"), dict) else _empty_proficiency()
        base_prof = _empty_proficiency()
        base_prof.update(prof)
        out.append(
            {
                "id": oid,
                "description": str(raw.get("description") or raw.get("title") or oid).strip(),
                "required": required,
                "in_scope": in_scope,
                "prerequisite_refs": [str(x).strip() for x in (raw.get("prerequisite_refs") or []) if str(x).strip()],
                "assumptions": [str(x).strip() for x in (raw.get("assumptions") or []) if str(x).strip()],
                "expected_assessments": [str(x).strip() for x in (raw.get("expected_assessments") or []) if str(x).strip()],
                "coverage_status": "out_of_scope" if not in_scope else cov,
                "proficiency": base_prof,
                "evidence_summary": str(raw.get("evidence_summary") or ""),
                "unresolved_gaps": [str(x).strip() for x in (raw.get("unresolved_gaps") or []) if str(x).strip()],
            }
        )
    return out or [default_objective_for_node(node_id, node)]


def normalize_event(raw: dict[str, Any], default_topic: str = "") -> dict[str, Any]:
    """Normalize a v1 or v2 event without fabricating missing fields."""
    topic_raw = str(raw.get("topic") or raw.get("topic_id") or default_topic).strip()
    if topic_raw.startswith("topic-"):
        topic_num = topic_raw[len("topic-"):]
    else:
        topic_num = topic_raw
    topic_num = topic_num.zfill(2) if topic_num.isdigit() else topic_num
    topic_id = f"topic-{topic_num}" if topic_num else ""

    cp = raw.get("cp")
    raw_res = raw.get("result") or raw.get("status") or "pass"
    result = normalize_result(str(raw_res))
    assistance = normalize_assistance(raw.get("assistance_level"))
    atype = normalize_assessment_type(raw.get("assessment_type"), legacy_cp=cp if isinstance(cp, int) else None)

    return {
        "schema_version": int(raw.get("schema_version") or (2 if "assistance_level" in raw or "objective_id" in raw else 1)),
        "event_id": str(raw.get("event_id") or ""),
        "attempt_id": raw.get("attempt_id"),
        "ts": str(raw.get("ts") or ""),
        "session_run_id": raw.get("session_run_id"),
        "topic": topic_num,
        "topic_id": topic_id,
        "objective_id": str(raw.get("objective_id") or ""),
        "item_id": str(raw.get("item_id") or (f"cp-{cp}" if cp is not None else "")),
        "assessment_type": atype,
        "result": result,
        "status": str(raw.get("status") or ("retry" if result == "fail" else result)),
        "assistance_level": assistance,
        "stage": raw.get("stage"),
        "cp": cp,
        "rationale": str(raw.get("rationale") or raw.get("note") or ""),
        "misconception_ref": raw.get("misconception_ref"),
        "learner_confidence": raw.get("learner_confidence"),
        "active_time_sec": raw.get("active_time_sec"),
        "response_summary": raw.get("response_summary"),
        "transfer_context": raw.get("transfer_context"),
        "verification": raw.get("verification"),
    }


def append_event_idempotent(
    events_path: Path,
    event: dict[str, Any],
    existing_events: list[dict[str, Any]] | None = None,
) -> tuple[dict[str, Any], bool]:
    """Append event to events.jsonl unless an identical attempt_id already exists.

    Returns (recorded_event, deduplicated_flag).
    """
    attempt_id = str(event.get("attempt_id") or "").strip()
    if attempt_id and existing_events is not None:
        for ev in existing_events:
            if str(ev.get("attempt_id") or "").strip() == attempt_id:
                return ev, True
    elif attempt_id and events_path.is_file():
        for raw in read_text_safe(events_path).splitlines():
            line = raw.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(obj, dict) and str(obj.get("attempt_id") or "").strip() == attempt_id:
                return obj, True

    events_path.parent.mkdir(parents=True, exist_ok=True)
    if not event.get("event_id"):
        event["event_id"] = f"evt-{uuid.uuid4().hex[:12]}"
    with events_path.open("a", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(event, ensure_ascii=False) + "\n")
    return event, False


def derive_objective_evidence(
    objective: dict[str, Any],
    events: list[dict[str, Any]],
    node_status: str = "unstarted",
    node_checkpoint: str = "0/4",
    min_retention_delay_hours: float = DEFAULT_MIN_RETENTION_DELAY_HOURS,
) -> dict[str, Any]:
    """Derive coverage status, proficiency dimensions, and unresolved gaps from append-only events.

    Preserves historical success even when later failures weaken current proficiency.
    Never upgrades legacy 4/4 flags or assisted passes into independent retention or transfer.
    """
    obj = dict(objective)
    in_scope = bool(obj.get("in_scope", True))
    if not in_scope:
        obj["coverage_status"] = "out_of_scope"
        obj["required"] = False
        return obj

    prof = _empty_proficiency()
    dims_indep: list[str] = []
    dims_assist: list[str] = []
    transfer_contexts: list[str] = []
    unresolved_gaps: list[str] = []
    last_indep_dt: datetime | None = None
    last_indep_ts: str | None = None
    prior_indep_ts: str | None = None
    last_run_id: str | None = None
    current_weakness: dict[str, Any] | None = None
    introduced_seen = obj.get("coverage_status") == "introduced"

    def _sort_key(ev: dict[str, Any]) -> str:
        return str(ev.get("ts") or "")

    for raw_ev in sorted(events, key=_sort_key):
        ev = normalize_event(raw_ev)
        res = ev["result"]
        assist = ev["assistance_level"]
        atype = ev["assessment_type"]
        ts_str = ev["ts"]
        run_id = ev.get("session_run_id")
        ev_dt: datetime | None = None
        if ts_str:
            try:
                ev_dt = parse_utc_ts(ts_str)
            except ValueError:
                ev_dt = None

        dim = ASSESSMENT_TYPE_TO_DIMENSION.get(atype)

        if res == "skipped":
            continue

        if atype == "diagnostic" and res == "fail":
            prof["failures"] += 1
            gap_msg = ev["rationale"] or "Diagnostic gap identified"
            if gap_msg not in unresolved_gaps:
                unresolved_gaps.append(gap_msg)
            current_weakness = {"ts": ts_str, "reason": gap_msg, "misconception_ref": ev.get("misconception_ref")}
            continue

        if res == "fail":
            prof["failures"] += 1
            gap_msg = ev["rationale"] or f"Failed {atype}"
            if gap_msg not in unresolved_gaps:
                unresolved_gaps.append(gap_msg)
            current_weakness = {
                "ts": ts_str,
                "assessment_type": atype,
                "reason": gap_msg,
                "misconception_ref": ev.get("misconception_ref"),
            }
            if prof["retention"]["status"] == "retained":
                prof["retention"]["status"] = "lapsed"
            if atype == "transfer":
                prof["transfer"]["status"] = "failed"
            continue

        if res == "partial":
            prof["partial_count"] += 1
            introduced_seen = True
            if ev["rationale"]:
                current_weakness = {
                    "ts": ts_str,
                    "assessment_type": atype,
                    "reason": ev["rationale"],
                    "misconception_ref": ev.get("misconception_ref"),
                }
            continue

        # res == "pass"
        introduced_seen = True
        if assist == "none":
            prof["independent_successes"] += 1
            if dim and dim not in dims_indep:
                dims_indep.append(dim)

            # Determine whether this counts as delayed retention
            is_delayed = False
            if last_indep_dt is not None and ev_dt is not None:
                elapsed_hours = (ev_dt - last_indep_dt).total_seconds() / 3600.0
                same_session = bool(run_id and last_run_id and run_id == last_run_id)
                if elapsed_hours >= min_retention_delay_hours and not same_session:
                    is_delayed = True

            if is_delayed:
                prof["retention"]["status"] = "retained"
                prof["retention"]["last_verified_at"] = ts_str
                prof["retention"]["prior_verified_at"] = ts_str
                if "delayed_recall" not in dims_indep:
                    dims_indep.append("delayed_recall")

            if atype == "transfer" or (ev.get("transfer_context") and str(ev.get("transfer_context")).strip()):
                prof["transfer"]["status"] = "demonstrated"
                prof["transfer"]["last_verified_at"] = ts_str
                prof["transfer"]["prior_verified_at"] = ts_str
                ctx = str(ev.get("transfer_context") or ev.get("rationale") or "unfamiliar context").strip()
                if ctx and ctx not in transfer_contexts:
                    transfer_contexts.append(ctx)
                if "transfer" not in dims_indep:
                    dims_indep.append("transfer")

            last_indep_dt = ev_dt
            last_indep_ts = ts_str
            prior_indep_ts = ts_str
            last_run_id = run_id or last_run_id
            # Independent success resolves prior weakness on this objective
            current_weakness = None
            unresolved_gaps = []
        elif assist in ("hint", "scaffold", "worked_example"):
            prof["assisted_successes"] += 1
            if dim and dim not in dims_assist:
                dims_assist.append(dim)
        else:
            # assistance_level == "unknown" (legacy event)
            prof["unknown_assistance_passes"] += 1

    # Determine proficiency status and coverage status honestly
    if prof["independent_successes"] > 0 and current_weakness is None:
        prof_status = "demonstrated_independently"
        cov_status = "demonstrated"
    elif current_weakness is not None:
        if prior_indep_ts is not None:
            prof_status = "weakened"
        elif prof["assisted_successes"] > 0:
            prof_status = "practiced_with_support"
        else:
            prof_status = "introduced" if introduced_seen else "untested"
        cov_status = "unresolved"
    elif prof["assisted_successes"] > 0:
        prof_status = "practiced_with_support"
        cov_status = "assessed"
    elif node_status == "mastered" or node_checkpoint == "4/4" or prof["unknown_assistance_passes"] > 0:
        # Legacy checkpoint completion without explicit unassisted evidence
        prof["legacy_completed"] = node_status == "mastered" or node_checkpoint == "4/4"
        prof_status = "legacy_unverified"
        cov_status = "assessed"
    elif introduced_seen or node_status == "in_progress":
        prof_status = "introduced"
        cov_status = "introduced"
    else:
        prof_status = "untested"
        cov_status = obj.get("coverage_status") if obj.get("coverage_status") in ("introduced", "not_taught") else "not_taught"

    prof["status"] = prof_status
    prof["dimensions_evidenced"] = dims_indep
    prof["dimensions_assisted"] = dims_assist
    prof["transfer"]["contexts"] = transfer_contexts
    prof["prior_independent_success_at"] = prior_indep_ts
    prof["current_weakness"] = current_weakness

    summary_parts = [f"status={prof_status}"]
    if prof["independent_successes"]:
        summary_parts.append(f"independent={prof['independent_successes']}")
    if prof["assisted_successes"]:
        summary_parts.append(f"assisted={prof['assisted_successes']}")
    if prof["failures"]:
        summary_parts.append(f"failures={prof['failures']}")
    if prof["legacy_completed"]:
        summary_parts.append("legacy_4of4_assistance_unknown")
    if prof["retention"]["status"] != "untested":
        summary_parts.append(f"retention={prof['retention']['status']}")
    if prof["transfer"]["status"] != "untested":
        summary_parts.append(f"transfer={prof['transfer']['status']}")

    obj["coverage_status"] = cov_status
    obj["proficiency"] = prof
    obj["evidence_summary"] = "; ".join(summary_parts)
    obj["unresolved_gaps"] = unresolved_gaps
    return obj


def derive_session_coverage_and_gaps(
    curriculum: dict[str, Any],
    events: list[dict[str, Any]],
    mission: dict[str, Any] | None = None,
    review_due: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Compute objective-level coverage, proficiency rollup, and visible gaps across a session."""
    nodes = curriculum.get("nodes", {})
    order = curriculum.get("order") or list(nodes.keys())

    # Index events by objective_id, falling back to topic_id when topic has 1 objective or no objective_id
    events_by_obj: dict[str, list[dict[str, Any]]] = {}
    events_by_topic: dict[str, list[dict[str, Any]]] = {}
    for raw in events:
        ev = normalize_event(raw)
        if ev["objective_id"]:
            events_by_obj.setdefault(ev["objective_id"], []).append(ev)
        elif ev["topic_id"]:
            events_by_topic.setdefault(ev["topic_id"], []).append(ev)

    coverage_counts = {k: 0 for k in COVERAGE_STATUSES}
    required_total = 0
    required_demonstrated = 0
    required_untested: list[dict[str, Any]] = []
    unresolved_objectives: list[dict[str, Any]] = []
    objectives_detail: list[dict[str, Any]] = []

    independent_success_total = 0
    assisted_success_total = 0
    delayed_retained_count = 0
    transfer_demonstrated_count = 0
    active_times: list[float] = []

    for ev in events:
        nev = normalize_event(ev)
        if nev["result"] == "pass":
            if nev["assistance_level"] == "none":
                independent_success_total += 1
            elif nev["assistance_level"] in ("hint", "scaffold", "worked_example"):
                assisted_success_total += 1
        at = nev.get("active_time_sec")
        if isinstance(at, (int, float)) and at >= 0:
            active_times.append(float(at))

    for nid in order:
        node = nodes.get(nid)
        if not isinstance(node, dict):
            continue
        objs = normalize_objectives_list(nid, node)
        topic_fallback_evs = events_by_topic.get(nid, [])
        for idx, obj in enumerate(objs):
            oid = obj["id"]
            matched = list(events_by_obj.get(oid, []))
            if idx == 0 and topic_fallback_evs:
                matched.extend(topic_fallback_evs)
            derived = derive_objective_evidence(
                obj,
                matched,
                node_status=str(node.get("status") or "unstarted"),
                node_checkpoint=str(node.get("checkpoint") or "0/4"),
            )
            cov = derived["coverage_status"]
            coverage_counts[cov] = coverage_counts.get(cov, 0) + 1
            prof = derived["proficiency"]

            if prof["retention"]["status"] == "retained":
                delayed_retained_count += 1
            if prof["transfer"]["status"] == "demonstrated":
                transfer_demonstrated_count += 1

            if derived.get("in_scope", True) and derived.get("required", True):
                required_total += 1
                if cov == "demonstrated":
                    required_demonstrated += 1
                elif prof["status"] in ("untested", "introduced"):
                    required_untested.append(
                        {
                            "objective_id": oid,
                            "topic_id": nid,
                            "description": derived["description"],
                            "coverage_status": cov,
                        }
                    )

            if cov == "unresolved" or derived.get("unresolved_gaps") or prof["status"] in ("weakened", "legacy_unverified"):
                unresolved_objectives.append(
                    {
                        "objective_id": oid,
                        "topic_id": nid,
                        "description": derived["description"],
                        "proficiency_status": prof["status"],
                        "gaps": derived.get("unresolved_gaps", []),
                        "prior_independent_success_at": prof.get("prior_independent_success_at"),
                        "current_weakness": prof.get("current_weakness"),
                        "legacy_unverified": bool(prof.get("legacy_completed")),
                    }
                )

            objectives_detail.append(
                {
                    "topic_id": nid,
                    "objective_id": oid,
                    "description": derived["description"],
                    "required": derived["required"],
                    "in_scope": derived["in_scope"],
                    "coverage_status": cov,
                    "proficiency_status": prof["status"],
                    "retention_status": prof["retention"]["status"],
                    "transfer_status": prof["transfer"]["status"],
                    "unresolved_gaps": derived["unresolved_gaps"],
                    "evidence_summary": derived["evidence_summary"],
                }
            )

    # Prerequisite gaps from mission calibration
    prereq_gaps: list[dict[str, Any]] = []
    prereq_map = (mission or {}).get("prerequisites", {})
    if isinstance(prereq_map, dict):
        for pid, pinfo in prereq_map.items():
            if not isinstance(pinfo, dict):
                continue
            pstate = str(pinfo.get("state") or "unknown")
            if pstate in ("unknown", "needs_support"):
                prereq_gaps.append(
                    {
                        "prerequisite": pid,
                        "state": pstate,
                        "evidence": str(pinfo.get("evidence") or ""),
                    }
                )

    scope_complete = (
        required_total > 0
        and required_demonstrated == required_total
        and not required_untested
        and not any(g["state"] == "needs_support" for g in prereq_gaps)
        and not any(u["proficiency_status"] == "weakened" for u in unresolved_objectives)
    )

    return {
        "required_objectives_total": required_total,
        "required_objectives_demonstrated": required_demonstrated,
        "scope_complete": scope_complete,
        "coverage_counts": coverage_counts,
        "required_untested": required_untested,
        "unresolved_objectives": unresolved_objectives,
        "unresolved_prerequisites": prereq_gaps,
        "independent_successes": independent_success_total,
        "assisted_successes": assisted_success_total,
        "delayed_retained_objectives": delayed_retained_count,
        "transfer_demonstrated_objectives": transfer_demonstrated_count,
        "active_time_total_sec": round(sum(active_times), 1) if active_times else None,
        "due_reviews_count": len(review_due) if review_due is not None else 0,
        "objectives": objectives_detail,
    }


def load_media_provenance(session_dir: Path) -> dict[str, Any]:
    """Load scratchpad/media-provenance.json safely."""
    path = session_dir / "scratchpad" / "media-provenance.json"
    if not path.is_file():
        return {"schema_version": MEDIA_PROVENANCE_SCHEMA_VERSION, "items": []}
    try:
        data = json.loads(read_text_safe(path))
        if isinstance(data, dict) and isinstance(data.get("items"), list):
            return data
    except (OSError, json.JSONDecodeError):
        pass
    return {"schema_version": MEDIA_PROVENANCE_SCHEMA_VERSION, "items": []}


def record_media_provenance(
    session_dir: Path,
    *,
    objective_id: str,
    kind: str = "retrieved_image",
    source_page_url: str = "",
    asset_url: str = "",
    title: str = "",
    creator: str = "",
    license_info: str = "",
    verification_status: str = "metadata_only_unverified",
    local_path: str = "",
    assumptions: list[str] | None = None,
    fallback_text: str = "",
    retrieved_at: str | None = None,
) -> dict[str, Any]:
    """Persist a validated media provenance entry without fabricating license or verification state."""
    vstatus = str(verification_status or "unverified").strip().lower()
    if vstatus not in VERIFICATION_STATUSES:
        raise ValueError(
            f"Unsupported verification_status {verification_status!r}; expected one of {VERIFICATION_STATUSES}"
        )

    clean_license = str(license_info or "").strip() or "unknown"
    resolved_local_rel = ""
    digest = ""
    content_type = ""

    if local_path:
        cand = Path(local_path)
        if not cand.is_absolute():
            cand = (session_dir / cand).resolve()
        else:
            cand = cand.resolve()
        if not is_within_root(cand, session_dir):
            raise ValueError(f"Cached media path must reside inside session directory: {local_path}")
        if not cand.is_file():
            raise FileNotFoundError(f"Cached media file not found: {cand}")
        ext = cand.suffix.lower()
        if ext in BLOCKED_ACTIVE_EXTENSIONS or (ext and ext not in ALLOWED_MEDIA_EXTENSIONS):
            raise ValueError(f"Disallowed cached media file extension: {ext}")
        raw_bytes = cand.read_bytes()
        if len(raw_bytes) > MAX_MEDIA_FILE_BYTES:
            raise ValueError(f"Cached media exceeds {MAX_MEDIA_FILE_BYTES} byte limit")
        digest = hashlib.sha256(raw_bytes).hexdigest()
        resolved_local_rel = cand.relative_to(session_dir.resolve()).as_posix()
        ext_map = {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".webp": "image/webp",
            ".gif": "image/gif",
            ".svg": "image/svg+xml",
            ".csv": "text/csv",
            ".json": "application/json",
            ".txt": "text/plain",
            ".md": "text/markdown",
        }
        content_type = ext_map.get(ext, "application/octet-stream")

    entry: dict[str, Any] = {
        "media_id": f"med-{uuid.uuid4().hex[:10]}",
        "objective_id": objective_id.strip(),
        "kind": kind.strip() or "retrieved_image",
        "title": title.strip() or "unknown",
        "creator": creator.strip() or "unknown",
        "source_page_url": source_page_url.strip(),
        "asset_url": asset_url.strip(),
        "retrieved_at": retrieved_at or utc_now_iso(),
        "license": clean_license,
        "verification_status": vstatus,
        "local_path": resolved_local_rel,
        "sha256": digest,
        "content_type": content_type,
        "assumptions": [str(a).strip() for a in (assumptions or []) if str(a).strip()],
        "fallback_text": fallback_text.strip(),
    }

    store = load_media_provenance(session_dir)
    items = list(store.get("items", []))
    items.append(entry)
    store["schema_version"] = MEDIA_PROVENANCE_SCHEMA_VERSION
    store["items"] = items
    atomic_write_text(
        session_dir / "scratchpad" / "media-provenance.json",
        json.dumps(store, indent=2, ensure_ascii=False) + "\n",
    )
    return entry
