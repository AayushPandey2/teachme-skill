"""Deterministic spaced-review scheduler and transparent priority ranking."""

from __future__ import annotations

from datetime import datetime, timedelta
import json
from pathlib import Path
from typing import Any

from .evidence import (
    DEFAULT_MIN_RETENTION_DELAY_HOURS,
    derive_objective_evidence,
    format_utc_ts,
    normalize_assistance,
    normalize_event,
    normalize_objectives_list,
    normalize_result,
    parse_utc_ts,
)
from .models import atomic_write_text, read_text_safe

REVIEW_STATE_SCHEMA_VERSION = 1
DEFAULT_INTERVALS_DAYS = [1, 3, 7, 21]
REVIEW_POLICY_NOTE = (
    "Default intervals [1, 3, 7, 21] days are configurable operational defaults, "
    "not scientifically universal optimal intervals."
)


def default_review_store(intervals_days: list[int] | None = None) -> dict[str, Any]:
    return {
        "schema_version": REVIEW_STATE_SCHEMA_VERSION,
        "intervals_days": list(intervals_days or DEFAULT_INTERVALS_DAYS),
        "min_retention_delay_hours": DEFAULT_MIN_RETENTION_DELAY_HOURS,
        "policy_note": REVIEW_POLICY_NOTE,
        "items": {},
    }


def load_review_state(session_dir: Path) -> dict[str, Any]:
    """Load scratchpad/review-state.json safely without mutating anything."""
    path = session_dir / "scratchpad" / "review-state.json"
    if not path.is_file():
        return default_review_store()
    try:
        data = json.loads(read_text_safe(path))
        if isinstance(data, dict) and isinstance(data.get("items"), dict):
            intervals = data.get("intervals_days")
            if not isinstance(intervals, list) or not intervals:
                data["intervals_days"] = list(DEFAULT_INTERVALS_DAYS)
            data.setdefault("min_retention_delay_hours", DEFAULT_MIN_RETENTION_DELAY_HOURS)
            data.setdefault("schema_version", REVIEW_STATE_SCHEMA_VERSION)
            data.setdefault("policy_note", REVIEW_POLICY_NOTE)
            return data
    except (OSError, json.JSONDecodeError):
        pass
    return default_review_store()


def save_review_state(session_dir: Path, store: dict[str, Any]) -> Path:
    """Persist scratchpad/review-state.json atomically."""
    out = session_dir / "scratchpad" / "review-state.json"
    atomic_write_text(out, json.dumps(store, indent=2, ensure_ascii=False) + "\n")
    return out


def _empty_item(target_id: str, topic_id: str) -> dict[str, Any]:
    return {
        "target_id": target_id,
        "topic_id": topic_id,
        "last_tested_at": None,
        "last_independent_at": None,
        "last_run_id": None,
        "next_review_at": None,
        "interval_days": 0,
        "stage": 0,
        "lapse_count": 0,
        "consecutive_failures": 0,
        "consecutive_independent_successes": 0,
        "needs_prerequisite_repair": False,
        "legacy_unverified": False,
        "recent_outcomes": [],
    }


def apply_event_to_review_store(
    store: dict[str, Any],
    *,
    target_id: str,
    topic_id: str,
    result: str,
    assistance_level: str,
    assessment_type: str,
    now: str | datetime | None = None,
    session_run_id: str | None = None,
) -> dict[str, Any]:
    """Update a single review item deterministically according to evidence rules."""
    intervals = [int(x) for x in (store.get("intervals_days") or DEFAULT_INTERVALS_DAYS) if int(x) > 0]
    if not intervals:
        intervals = list(DEFAULT_INTERVALS_DAYS)
    min_delay_h = float(store.get("min_retention_delay_hours", DEFAULT_MIN_RETENTION_DELAY_HOURS))

    now_dt = parse_utc_ts(now)
    now_iso = format_utc_ts(now_dt)

    norm_res = normalize_result(result)
    norm_assist = normalize_assistance(assistance_level)

    items = dict(store.get("items", {}))
    item = dict(items.get(target_id) or _empty_item(target_id, topic_id))
    item["topic_id"] = topic_id or item.get("topic_id", "")

    if norm_res == "skipped":
        items[target_id] = item
        store["items"] = items
        return item

    prev_indep_dt = parse_utc_ts(item["last_independent_at"]) if item.get("last_independent_at") else None
    prev_due_dt = parse_utc_ts(item["next_review_at"]) if item.get("next_review_at") else None
    prev_run_id = item.get("last_run_id")

    same_session = False
    if prev_indep_dt is not None:
        elapsed_h = (now_dt - prev_indep_dt).total_seconds() / 3600.0
        if elapsed_h < min_delay_h:
            same_session = True
    if session_run_id and prev_run_id and session_run_id == prev_run_id:
        same_session = True

    delayed_flag = False
    is_early = bool(prev_due_dt is not None and now_dt < prev_due_dt)

    if norm_res == "pass" and norm_assist == "none":
        item["consecutive_failures"] = 0
        item["needs_prerequisite_repair"] = False
        item["legacy_unverified"] = False

        if prev_indep_dt is None:
            # First independent demonstration enters schedule at stage 0 (default 1 day)
            stage = 0
            iv = intervals[stage]
            item["stage"] = stage
            item["interval_days"] = iv
            item["next_review_at"] = format_utc_ts(now_dt + timedelta(days=iv))
            item["consecutive_independent_successes"] = 1
        elif is_early:
            # Early practice before due date: never accidentally postpone scheduled review
            item["consecutive_independent_successes"] = int(item.get("consecutive_independent_successes", 0)) + 1
        elif same_session:
            # Same-session retry/practice must NOT advance delayed retention stage
            if prev_due_dt is None or now_dt >= prev_due_dt:
                iv = intervals[int(item.get("stage", 0))]
                item["interval_days"] = iv
                item["next_review_at"] = format_utc_ts(now_dt + timedelta(days=iv))
        else:
            # Delayed independent retrieval (now >= next_review_at and elapsed >= min_delay_h)
            delayed_flag = True
            cur_stage = int(item.get("stage", 0))
            next_stage = min(cur_stage + 1, len(intervals) - 1)
            iv = intervals[next_stage]
            item["stage"] = next_stage
            item["interval_days"] = iv
            item["next_review_at"] = format_utc_ts(now_dt + timedelta(days=iv))
            item["consecutive_independent_successes"] = int(item.get("consecutive_independent_successes", 0)) + 1

        item["last_independent_at"] = now_iso
        if session_run_id:
            item["last_run_id"] = session_run_id

    elif norm_res == "pass" and norm_assist in ("hint", "scaffold", "worked_example"):
        # Assisted success does NOT advance retention stage or count as independent
        item["consecutive_failures"] = 0
        item["consecutive_independent_successes"] = 0
        item["legacy_unverified"] = False
        if prev_due_dt is None or now_dt >= prev_due_dt:
            item["stage"] = 0
            item["interval_days"] = intervals[0]
            item["next_review_at"] = format_utc_ts(now_dt + timedelta(days=intervals[0]))
        # If early (now_dt < prev_due_dt), preserve existing next_review_at

    elif norm_res == "pass" and norm_assist == "unknown":
        # Legacy unknown-assistance pass: never advance retention stage
        item["legacy_unverified"] = True
        if prev_due_dt is None:
            item["stage"] = 0
            item["interval_days"] = intervals[0]
            item["next_review_at"] = format_utc_ts(now_dt + timedelta(days=intervals[0]))

    elif norm_res == "partial":
        item["consecutive_independent_successes"] = 0
        if prev_due_dt is None or now_dt >= prev_due_dt:
            item["stage"] = 0
            item["interval_days"] = intervals[0]
            item["next_review_at"] = format_utc_ts(now_dt + timedelta(days=intervals[0]))

    elif norm_res == "fail":
        item["lapse_count"] = int(item.get("lapse_count", 0)) + 1
        item["consecutive_failures"] = int(item.get("consecutive_failures", 0)) + 1
        item["consecutive_independent_successes"] = 0
        item["stage"] = 0
        if item["consecutive_failures"] >= 2:
            item["needs_prerequisite_repair"] = True
            item["interval_days"] = 0
            item["next_review_at"] = now_iso
        else:
            item["interval_days"] = intervals[0]
            item["next_review_at"] = format_utc_ts(now_dt + timedelta(days=intervals[0]))

    item["last_tested_at"] = now_iso
    outcomes = list(item.get("recent_outcomes", []))
    outcomes.append(
        {
            "ts": now_iso,
            "result": norm_res,
            "assistance_level": norm_assist,
            "assessment_type": assessment_type,
            "delayed": delayed_flag,
        }
    )
    item["recent_outcomes"] = outcomes[-10:]

    items[target_id] = item
    store["items"] = items
    return item


def sync_review_item_for_legacy_node(
    store: dict[str, Any],
    *,
    target_id: str,
    topic_id: str,
    last_ts: str | None,
    legacy_mastered: bool,
) -> dict[str, Any]:
    """Ensure a migrated legacy mastered/completed node is represented honestly in review state."""
    items = dict(store.get("items", {}))
    if target_id in items:
        return items[target_id]
    intervals = [int(x) for x in (store.get("intervals_days") or DEFAULT_INTERVALS_DAYS) if int(x) > 0] or list(DEFAULT_INTERVALS_DAYS)
    item = _empty_item(target_id, topic_id)
    item["legacy_unverified"] = bool(legacy_mastered)
    if last_ts:
        try:
            dt = parse_utc_ts(last_ts)
            item["last_tested_at"] = format_utc_ts(dt)
            item["interval_days"] = intervals[0]
            item["next_review_at"] = format_utc_ts(dt + timedelta(days=intervals[0]))
        except ValueError:
            pass
    items[target_id] = item
    store["items"] = items
    return item


def get_due_reviews(
    curriculum: dict[str, Any],
    events: list[dict[str, Any]],
    review_store: dict[str, Any],
    *,
    now: str | datetime | None = None,
    limit: int = 10,
) -> list[dict[str, Any]]:
    """Compute prioritized due reviews strictly read-only without mutating any state."""
    now_dt = parse_utc_ts(now)
    nodes = curriculum.get("nodes", {})
    order = curriculum.get("order") or list(nodes.keys())
    items = review_store.get("items", {})

    # Compute downstream prerequisite importance per topic
    downstream_counts: dict[str, int] = {nid: 0 for nid in nodes}
    for nid, node in nodes.items():
        if not isinstance(node, dict):
            continue
        for dep in node.get("depends_on", []) or []:
            if dep in downstream_counts:
                downstream_counts[dep] += 1

    # Index events by objective and topic for status awareness
    events_by_obj: dict[str, list[dict[str, Any]]] = {}
    events_by_topic: dict[str, list[dict[str, Any]]] = {}
    for raw in events:
        ev = normalize_event(raw)
        if ev["objective_id"]:
            events_by_obj.setdefault(ev["objective_id"], []).append(ev)
        elif ev["topic_id"]:
            events_by_topic.setdefault(ev["topic_id"], []).append(ev)

    due_list: list[dict[str, Any]] = []
    for nid in order:
        node = nodes.get(nid)
        if not isinstance(node, dict):
            continue
        objs = normalize_objectives_list(nid, node)
        topic_evs = events_by_topic.get(nid, [])
        for idx, obj in enumerate(objs):
            if not obj.get("in_scope", True):
                continue
            oid = obj["id"]
            matched_evs = list(events_by_obj.get(oid, []))
            if idx == 0 and topic_evs:
                matched_evs.extend(topic_evs)
            derived = derive_objective_evidence(
                obj,
                matched_evs,
                node_status=str(node.get("status") or "unstarted"),
                node_checkpoint=str(node.get("checkpoint") or "0/4"),
            )
            prof = derived["proficiency"]
            prof_status = prof["status"]
            ritem = items.get(oid) or items.get(nid)

            next_due_str = ritem.get("next_review_at") if isinstance(ritem, dict) else None
            lapse_count = int(ritem.get("lapse_count", 0)) if isinstance(ritem, dict) else 0
            needs_repair = bool(ritem.get("needs_prerequisite_repair")) if isinstance(ritem, dict) else False
            legacy_unverified = bool(
                (ritem.get("legacy_unverified") if isinstance(ritem, dict) else False)
                or prof.get("legacy_completed")
            )

            overdue_days = 0.0
            is_due = False
            reasons: list[str] = []

            if next_due_str:
                try:
                    due_dt = parse_utc_ts(next_due_str)
                    if now_dt >= due_dt:
                        is_due = True
                        overdue_days = round((now_dt - due_dt).total_seconds() / 86400.0, 2)
                        reasons.append(f"overdue_by_{overdue_days}d" if overdue_days > 0 else "due_now")
                except ValueError:
                    pass
            elif legacy_unverified:
                is_due = True
                reasons.append("legacy_4of4_unverified_needs_retrieval_check")

            if prof_status == "weakened" or needs_repair:
                is_due = True
                reasons.append("recent_failure_or_weakened")

            if not is_due:
                continue

            if prof_status == "demonstrated_independently":
                reasons.append("previously_demonstrated_due_for_retention")
            elif prof_status == "practiced_with_support":
                reasons.append("assisted_only_needs_unaided_check")

            if derived.get("required", True):
                reasons.append("required_in_scope")
            ds_impact = downstream_counts.get(nid, 0)
            if ds_impact > 0:
                reasons.append(f"unlocks_{ds_impact}_downstream_topics")
            if lapse_count > 0:
                reasons.append(f"lapses={lapse_count}")

            # Transparent deterministic priority score (higher = more urgent)
            score = 0.0
            if needs_repair or prof_status == "weakened":
                score += 100.0
            if lapse_count > 0:
                score += min(40.0, lapse_count * 10.0)
            if overdue_days > 0:
                score += min(50.0, 10.0 + overdue_days * 5.0)
            else:
                score += 10.0
            if derived.get("required", True):
                score += 15.0
            score += min(20.0, ds_impact * 5.0)
            if legacy_unverified:
                score += 5.0

            due_list.append(
                {
                    "objective_id": oid,
                    "topic_id": nid,
                    "title": node.get("title", nid),
                    "description": derived["description"],
                    "proficiency_status": prof_status,
                    "required": bool(derived.get("required", True)),
                    "stage": int(ritem.get("stage", 0)) if isinstance(ritem, dict) else 0,
                    "interval_days": int(ritem.get("interval_days", 0)) if isinstance(ritem, dict) else 0,
                    "last_tested_at": ritem.get("last_tested_at") if isinstance(ritem, dict) else None,
                    "next_review_at": next_due_str,
                    "overdue_days": overdue_days,
                    "lapse_count": lapse_count,
                    "legacy_unverified": legacy_unverified,
                    "priority_score": round(score, 2),
                    "priority_reasons": reasons,
                }
            )

    due_list.sort(key=lambda item: (-item["priority_score"], item["topic_id"], item["objective_id"]))
    return due_list[:limit]
