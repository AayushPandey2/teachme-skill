#!/usr/bin/env python3
"""Deterministic CLI for managing /teachme operational learning state.

Standard-library only (Python 3). Handles curriculum state initialization,
session recovery, checkpoint ticking, state-only mastery flushing, legacy
memory migration, state validation, read-only vault indexing, source
resolution, and optional note-skill context-envelope generation. Never
creates or modifies study notes.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import sys
from typing import Any

_SCRIPT_DIR = str(Path(__file__).resolve().parent)
if _SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _SCRIPT_DIR)

from teachme_vault.cli_commands import register_vault_native_subcommands
from teachme_vault.evidence import (
    ASSISTANCE_LEVELS,
    ASSESSMENT_RESULTS,
    ASSESSMENT_TYPES,
    VERIFICATION_STATUSES,
    append_event_idempotent,
    derive_objective_evidence,
    derive_session_coverage_and_gaps,
    format_utc_ts,
    load_media_provenance,
    normalize_assessment_type,
    normalize_assistance,
    normalize_event,
    normalize_objectives_list,
    normalize_result,
    parse_utc_ts,
    record_media_provenance,
)
from teachme_vault.models import (
    MODE_VAULT_NATIVE,
    atomic_write_text,
    detect_vault_mode,
    get_active_vault_entry,
    get_registered_vaults,
    load_config,
    read_text_safe,
    resolve_state_dir,
)
from teachme_vault.scheduler import (
    apply_event_to_review_store,
    get_due_reviews,
    load_review_state,
    save_review_state,
    sync_review_item_for_legacy_node,
)
from teachme_vault.state_store import (
    build_handoff_envelope,
    import_legacy_vault,
    init_session_state,
    list_vault_native_sessions,
    load_curriculum,
    load_events,
    load_json_dict,
    load_learning_records,
    load_mission,
    migrate_session_state,
    normalize_topic_num,
    rebuild_curriculum_graph,
    resolve_session_dir,
    revise_curriculum,
    save_curriculum,
    save_mission,
    validate_session_state,
)

SECTION_RE = re.compile(r"^\s*<!--\s*SECTION:\s*([A-Za-z0-9_-]+)\s*-->\s*$")


def resolve_vault_root() -> Path:
    """Resolve standalone learning-state root from config or default ~/notes."""
    cfg = load_config()
    raw = str(cfg.get("notes_root", "")).strip()
    if raw:
        return Path(os.path.expandvars(raw)).expanduser().resolve()
    return (Path.home() / "notes").resolve()


def dump_json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, separators=(",", ":"))


def parse_session_state_fields(text: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    patterns = {
        "active_topic": r"^\s*-\s*\*\*(?:Active Subtopic|Active Note):\*\*\s*`?([^`\r\n]+?)`?\s*$",
        "stage_cp": r"^\s*-\s*\*\*Live Stage & Checkpoint:\*\*\s*`?([^`\r\n]+?)`?\s*$",
        "last_invariant": r"^\s*-\s*\*\*Last Verified Invariant:\*\*\s*(.+?)\s*$",
    }
    for key, pat in patterns.items():
        m = re.search(pat, text, flags=re.MULTILINE)
        if m:
            fields[key] = m.group(1).strip()
    return fields


def extract_section(text: str, section_name: str) -> str:
    """Read-only helper to extract an HTML-comment section from an existing Markdown file."""
    lines = text.lstrip("\ufeff").splitlines()
    target = section_name.strip().upper()

    if target == "L0-L1":
        out: list[str] = []
        if lines and lines[0].strip() == "---":
            out.append(lines[0])
            for i in range(1, len(lines)):
                out.append(lines[i])
                if lines[i].strip() == "---":
                    break
        l1_body = extract_section(text, "L1-ANCHOR")
        if out and l1_body:
            out.append("")
        if l1_body:
            out.append(l1_body)
        return "\n".join(out).strip()

    capturing = False
    collected: list[str] = []
    for line in lines:
        m = SECTION_RE.match(line)
        if m:
            found = m.group(1).strip().upper()
            if capturing:
                break
            if found == target:
                capturing = True
                collected.append(line)
            continue
        if capturing:
            collected.append(line)

    if not capturing:
        raise ValueError(f"Section marker not found: {section_name}")
    return "\n".join(collected).strip()


def infer_depth_stage(cp: int, explicit_stage: int | None) -> int:
    if explicit_stage is not None:
        return explicit_stage
    if cp <= 1:
        return 1
    if cp == 2:
        return 2
    return 3


def _load_subtopic_items(args: argparse.Namespace) -> list[dict[str, Any]]:
    sub_file = getattr(args, "subtopics", None) or getattr(args, "curriculum", None)
    if sub_file:
        p = Path(os.path.expandvars(sub_file)).expanduser().resolve()
        if not p.is_file():
            raise FileNotFoundError(f"Subtopics JSON not found: {p}")
        data = json.loads(read_text_safe(p))
        if isinstance(data, dict) and isinstance(data.get("subtopics"), list):
            data = data["subtopics"]
        if not isinstance(data, list):
            raise ValueError("Subtopics JSON must be a list of objects")
        return [dict(item) for item in data if isinstance(item, dict) and item.get("slug")]
    raw_topics = getattr(args, "topics", "") or ""
    return [
        {"slug": t.strip(), "title": t.strip()}
        for t in raw_topics.split(",")
        if t.strip()
    ]


def cmd_graph(args: argparse.Namespace) -> int:
    session_dir = resolve_session_dir(args.vault_path, session_slug=getattr(args, "session", None))
    graph = rebuild_curriculum_graph(session_dir)
    print(dump_json(graph))
    return 0


def cmd_state(args: argparse.Namespace) -> int:
    cfg = load_config()
    session_slug = getattr(args, "session", None)
    now_arg = getattr(args, "now", None)

    if not args.vault_path:
        mode_info = detect_vault_mode(None, config=cfg)
        active_entry = get_active_vault_entry(cfg)
        if mode_info["mode"] == MODE_VAULT_NATIVE and active_entry is not None:
            obs_path = Path(active_entry["path"])
            if obs_path.is_dir():
                sdir = resolve_state_dir(obs_path, config=cfg)
                sessions = list_vault_native_sessions(obs_path, config=cfg)
                if session_slug or sessions:
                    try:
                        sess_dir = resolve_session_dir(None, session_slug=session_slug)
                        summary = _build_session_state_summary(sess_dir, mode="vault-native", now=now_arg)
                        summary["active_vault"] = active_entry["name"]
                        summary["obsidian_vault"] = str(obs_path)
                        summary["vault_accessible"] = True
                        summary["state_dir"] = str(sdir)
                        summary["has_index"] = (sdir / "index.json").is_file()
                        summary["sessions"] = sessions
                        print(dump_json(summary))
                        return 0
                    except FileNotFoundError:
                        pass
                print(
                    dump_json(
                        {
                            "mode": "vault-native",
                            "active_vault": active_entry["name"],
                            "vault_path": str(obs_path),
                            "vault_accessible": True,
                            "state_dir": str(sdir),
                            "has_index": (sdir / "index.json").is_file(),
                            "sessions": sessions,
                        }
                    )
                )
                return 0
            # Configured active vault is inaccessible; try standalone session resume before returning status
            try:
                sess_dir = resolve_session_dir(None, session_slug=session_slug)
                summary = _build_session_state_summary(sess_dir, mode="standalone", now=now_arg)
                summary["active_vault"] = active_entry["name"]
                summary["obsidian_vault"] = str(obs_path)
                summary["vault_accessible"] = False
                print(dump_json(summary))
                return 0
            except FileNotFoundError:
                print(
                    dump_json(
                        {
                            "mode": "vault-native",
                            "active_vault": active_entry["name"],
                            "vault_path": str(obs_path),
                            "vault_accessible": False,
                            "has_index": False,
                            "sessions": [],
                        }
                    )
                )
                return 0

    raw = args.vault_path
    if raw:
        candidate = Path(os.path.expandvars(raw)).expanduser().resolve()
        mode_info = detect_vault_mode(candidate, config=cfg)
        if (
            mode_info["mode"] == MODE_VAULT_NATIVE
            and not (candidate / "00-SESSION-STATE.md").is_file()
            and not (candidate / "00-GRAPH.json").is_file()
        ):
            sdir = resolve_state_dir(candidate, config=cfg)
            sessions = list_vault_native_sessions(candidate, config=cfg)
            if session_slug or sessions:
                sess_dir = resolve_session_dir(raw, session_slug=session_slug)
                summary = _build_session_state_summary(sess_dir, mode="vault-native", now=now_arg)
                summary["obsidian_vault"] = str(candidate)
                summary["state_dir"] = str(sdir)
                summary["has_index"] = (sdir / "index.json").is_file()
                summary["sessions"] = sessions
                print(dump_json(summary))
                return 0
            print(
                dump_json(
                    {
                        "mode": "vault-native",
                        "vault_path": str(candidate),
                        "state_dir": str(sdir),
                        "has_index": (sdir / "index.json").is_file(),
                        "sessions": sessions,
                    }
                )
            )
            return 0

    sess_dir = resolve_session_dir(raw, session_slug=session_slug)
    print(dump_json(_build_session_state_summary(sess_dir, mode="standalone", now=now_arg)))
    return 0


def _build_session_state_summary(sess_dir: Path, mode: str, now: str | None = None) -> dict[str, Any]:
    state_file = sess_dir / "00-SESSION-STATE.md"
    graph_file = sess_dir / "00-GRAPH.json"

    fields: dict[str, str] = {}
    state_text = ""
    if state_file.is_file():
        state_text = read_text_safe(state_file)
        fields = parse_session_state_fields(state_text)

    stage_cp = fields.get("stage_cp", "")
    depth_stage = ""
    checkpoint = ""
    m_stage = re.search(r"Depth Stage\s*([0-9]+/[0-9]+)", stage_cp)
    m_cp = re.search(r"Checkpoint\s*\[?([0-9]+/[0-9]+)\]?", stage_cp)
    if m_stage:
        depth_stage = m_stage.group(1)
    if m_cp:
        checkpoint = m_cp.group(1)

    completed_count = 0
    total_count = 0
    if graph_file.is_file():
        graph = load_json_dict(graph_file) or {}
        nodes = graph.get("nodes", {})
        total_count = len(nodes)
        completed_count = sum(1 for n in nodes.values() if isinstance(n, dict) and n.get("status") == "mastered")

    curriculum = load_curriculum(sess_dir)
    events = load_events(sess_dir)
    mission = load_mission(sess_dir)
    rev_store = load_review_state(sess_dir)
    due_items = get_due_reviews(curriculum, events, rev_store, now=now, limit=50)
    cov = derive_session_coverage_and_gaps(curriculum, events, mission=mission, review_due=due_items)

    return {
        "mode": mode,
        "vault_path": str(sess_dir),
        "session_dir": str(sess_dir),
        "active_topic": fields.get("active_topic", ""),
        "depth_stage": depth_stage or "1/3",
        "checkpoint": checkpoint or "1/4",
        "completed_count": completed_count,
        "total_count": total_count,
        "last_invariant": fields.get("last_invariant", ""),
        "required_objectives_total": cov["required_objectives_total"],
        "required_objectives_demonstrated": cov["required_objectives_demonstrated"],
        "required_untested_count": len(cov["required_untested"]),
        "unresolved_gaps_count": len(cov["unresolved_objectives"]) + len(cov["unresolved_prerequisites"]),
        "due_reviews_count": len(due_items),
        "scope_complete": cov["scope_complete"],
    }


def cmd_slice(args: argparse.Namespace) -> int:
    md_path = Path(os.path.expandvars(args.markdown_file)).expanduser().resolve()
    if not md_path.is_file():
        print(json.dumps({"error": f"File not found: {md_path}"}), file=sys.stderr)
        return 1
    text = read_text_safe(md_path)
    try:
        sliced = extract_section(text, args.section)
    except ValueError as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        return 1
    print(sliced)
    return 0


def cmd_init(args: argparse.Namespace) -> int:
    topic_title = (getattr(args, "topic", None) or getattr(args, "title", None) or "").strip()
    items = _load_subtopic_items(args)

    raw_target = Path(os.path.expandvars(args.vault_path)).expanduser().resolve()
    cfg = load_config()
    mode_info = detect_vault_mode(raw_target, config=cfg)
    registered_paths = {Path(v["path"]).resolve() for v in get_registered_vaults(cfg).values() if v.get("path")}
    is_configured_obs = raw_target in registered_paths
    is_obsidian_root = (
        (raw_target / ".obsidian").is_dir()
        or (raw_target / ".teachme").is_dir()
        or is_configured_obs
        or mode_info.get("reason") == "existing_non_teachme_markdown_detected"
    )

    session_slug = getattr(args, "session", None)
    sess_dir = resolve_session_dir(
        args.vault_path,
        session_slug=session_slug,
        topic_hint=topic_title or raw_target.name,
        for_init=True,
    )
    eff_title = topic_title or sess_dir.name
    eff_mode = "vault-native" if is_obsidian_root else "standalone"
    scope_info: dict[str, Any] = {}
    if getattr(args, "goal", None):
        scope_info["goal"] = args.goal
    if getattr(args, "in_scope", None):
        scope_info["in_scope"] = [x.strip() for x in args.in_scope.split(",") if x.strip()]
    if getattr(args, "out_of_scope", None):
        scope_info["out_of_scope"] = [x.strip() for x in args.out_of_scope.split(",") if x.strip()]

    res = init_session_state(
        sess_dir,
        topic_title=eff_title,
        items=items,
        mode=eff_mode,
        vault_root=raw_target if is_obsidian_root else None,
        scope_info=scope_info or None,
    )
    print(dump_json(res))
    return 0


def cmd_tick(args: argparse.Namespace) -> int:
    sess_dir = resolve_session_dir(args.vault_path, session_slug=getattr(args, "session", None))
    topic_num = normalize_topic_num(args.topic)
    node_id = f"topic-{topic_num}"

    cp_val = getattr(args, "cp", None)
    cp = int(cp_val) if cp_val is not None else 1
    raw_status = getattr(args, "result", None) or getattr(args, "status", None) or "pass"
    norm_result = normalize_result(raw_status)
    raw_assistance = getattr(args, "assistance", None)
    assistance_level = normalize_assistance(raw_assistance)
    atype = normalize_assessment_type(getattr(args, "assessment_type", None), legacy_cp=cp_val)
    stage = infer_depth_stage(cp, getattr(args, "stage", None))

    now_dt = parse_utc_ts(getattr(args, "now", None))
    now_iso = format_utc_ts(now_dt)

    scratchpad = sess_dir / "scratchpad"
    scratchpad.mkdir(parents=True, exist_ok=True)
    events_path = scratchpad / "events.jsonl"

    curriculum = load_curriculum(sess_dir)
    c_nodes = dict(curriculum.get("nodes", {}))
    cnode = dict(c_nodes.get(node_id) or {"id": node_id, "slug": node_id, "title": node_id})
    objs = normalize_objectives_list(node_id, cnode)
    target_oid = (getattr(args, "objective", None) or "").strip() or objs[0]["id"]

    # Validate objective exists on node if explicitly requested
    if getattr(args, "objective", None) and not any(o["id"] == target_oid for o in objs):
        raise ValueError(f"Objective {target_oid} not found under {node_id}")

    rationale = (getattr(args, "rationale", None) or getattr(args, "note", None) or "").strip()
    attempt_id = (getattr(args, "attempt_id", None) or "").strip() or None
    confidence = getattr(args, "confidence", None)
    active_time = getattr(args, "active_time", None)

    event: dict[str, Any] = {
        "schema_version": 2,
        "ts": now_iso,
        "topic": topic_num,
        "topic_id": node_id,
        "objective_id": target_oid,
        "item_id": (getattr(args, "item_id", None) or (f"cp-{cp}" if cp_val is not None else "")).strip(),
        "assessment_type": atype,
        "result": norm_result,
        "status": "retry" if raw_status == "retry" else norm_result,
        "assistance_level": assistance_level,
        "stage": stage,
    }
    if cp_val is not None:
        event["cp"] = cp
    if attempt_id:
        event["attempt_id"] = attempt_id
    if rationale:
        event["note"] = rationale
        event["rationale"] = rationale
    if getattr(args, "misconception", None):
        event["misconception_ref"] = args.misconception.strip()
    if confidence is not None:
        event["learner_confidence"] = confidence
    if active_time is not None:
        event["active_time_sec"] = float(active_time)
    if getattr(args, "response_summary", None):
        event["response_summary"] = args.response_summary.strip()
    if getattr(args, "transfer_context", None):
        event["transfer_context"] = args.transfer_context.strip()
    if getattr(args, "session_run", None):
        event["session_run_id"] = args.session_run.strip()
    if getattr(args, "checked", False):
        event["verification"] = {"checked": True}

    existing_events = load_events(sess_dir)
    recorded_ev, deduplicated = append_event_idempotent(events_path, event, existing_events=existing_events)
    if deduplicated:
        print(
            dump_json(
                {
                    "ok": True,
                    "deduplicated": True,
                    "event_id": recorded_ev.get("event_id"),
                    "attempt_id": attempt_id,
                    "topic": topic_num,
                    "node_id": node_id,
                    "objective_id": target_oid,
                }
            )
        )
        return 0

    all_topic_events = load_events(sess_dir, topic_num=topic_num)

    # Update review scheduler deterministically
    review_store = load_review_state(sess_dir)
    review_item = apply_event_to_review_store(
        review_store,
        target_id=target_oid,
        topic_id=node_id,
        result=norm_result,
        assistance_level=assistance_level,
        assessment_type=atype,
        now=now_dt,
        session_run_id=event.get("session_run_id"),
    )
    save_review_state(sess_dir, review_store)

    # Re-derive objective evidence across curriculum node
    for idx, obj in enumerate(objs):
        oid = obj["id"]
        obj_evs = [e for e in all_topic_events if e.get("objective_id") == oid]
        if idx == 0:
            obj_evs.extend(e for e in all_topic_events if not e.get("objective_id"))
        objs[idx] = derive_objective_evidence(
            obj,
            obj_evs,
            node_status=str(cnode.get("status") or "in_progress"),
            node_checkpoint=f"{cp}/4" if cp_val is not None else str(cnode.get("checkpoint") or "0/4"),
        )
    cnode["objectives"] = objs

    # Determine honest topic status without silently upgrading assisted passes to mastered
    all_objs_indep = bool(objs) and all(
        (not o.get("in_scope", True)) or o["proficiency"]["status"] == "demonstrated_independently"
        for o in objs
    )
    any_weakened = any(o["proficiency"]["status"] == "weakened" for o in objs)
    legacy_cp4_pass = cp_val == 4 and norm_result == "pass" and assistance_level == "unknown"

    if any_weakened or norm_result == "fail":
        new_node_status = "in_progress"
    elif all_objs_indep or legacy_cp4_pass:
        new_node_status = "mastered"
    elif cnode.get("status") == "mastered" and norm_result == "pass":
        new_node_status = "mastered"
    else:
        new_node_status = "in_progress"

    cnode["status"] = new_node_status
    if cp_val is not None:
        cnode["checkpoint"] = f"{cp}/4"
    if rationale and norm_result == "pass":
        cnode["last_invariant"] = rationale
    c_nodes[node_id] = cnode
    curriculum["nodes"] = c_nodes
    if node_id not in curriculum.get("order", []):
        curriculum.setdefault("order", []).append(node_id)
    save_curriculum(sess_dir, curriculum)

    # Update 00-GRAPH.json operationally without touching any study notes
    graph_path = sess_dir / "00-GRAPH.json"
    graph = load_json_dict(graph_path) or {"schema_version": 2, "kind": "curriculum_dependency_graph", "nodes": {}, "order": []}
    nodes = dict(graph.get("nodes", {}))
    order = list(graph.get("order", []))
    node = dict(nodes.get(node_id, {"title": node_id, "depends_on": [], "unlocks": [], "contrasts_with": [], "fixes_failure_of": []}))
    if cp_val is not None:
        node["checkpoint"] = f"{cp}/4"
    node["status"] = new_node_status
    if rationale and norm_result == "pass":
        node["last_invariant"] = rationale
    ev_list = list(node.get("evidence", []))
    ev_list.append(
        {
            "ts": now_iso,
            "cp": cp_val,
            "objective_id": target_oid,
            "assessment_type": atype,
            "result": norm_result,
            "status": event["status"],
            "assistance_level": assistance_level,
            "note": rationale,
        }
    )
    node["evidence"] = ev_list[-20:]
    nodes[node_id] = node
    if node_id not in order:
        order.append(node_id)
    graph["nodes"] = nodes
    graph["order"] = order
    atomic_write_text(graph_path, json.dumps(graph, indent=2, ensure_ascii=False) + "\n")

    state_file = sess_dir / "00-SESSION-STATE.md"
    mark = "[x]" if new_node_status == "mastered" else "[~]"
    all_nums = [nid.replace("topic-", "") for nid in order] or [topic_num]

    if state_file.is_file():
        lines = read_text_safe(state_file).splitlines()
    else:
        status_tokens = " ".join(f"`[ ] {n}`" for n in all_nums)
        lines = [
            f"# Session State: {sess_dir.name}",
            "",
            f"- **Active Subtopic:** `{node_id}`",
            f"- **Live Stage & Checkpoint:** `Depth Stage {stage}/3 | Checkpoint [{cp}/4]`",
            "- **Last Verified Invariant:** Initialized.",
            "",
            "## Compact Subtopic Status Map",
            status_tokens,
            "<!-- Legend: [x] mastered | [~] in-progress | [ ] unstarted -->",
        ]

    updated_lines: list[str] = []
    token_re = re.compile(rf"`\[[ x~]\]\s*{re.escape(topic_num)}`")
    has_token = any(token_re.search(line) for line in lines)
    for line in lines:
        if line.lstrip().startswith("- **Active Subtopic:**") or line.lstrip().startswith("- **Active Note:**"):
            updated_lines.append(f"- **Active Subtopic:** `{node_id}`")
        elif line.lstrip().startswith("- **Live Stage & Checkpoint:**"):
            updated_lines.append(
                f"- **Live Stage & Checkpoint:** `Depth Stage {stage}/3 | Checkpoint [{cp}/4]`"
            )
        elif rationale and norm_result == "pass" and line.lstrip().startswith("- **Last Verified Invariant:**"):
            updated_lines.append(f"- **Last Verified Invariant:** {rationale}")
        elif token_re.search(line):
            updated_lines.append(token_re.sub(f"`{mark} {topic_num}`", line))
        else:
            updated_lines.append(line)

    if not has_token:
        for idx, line in enumerate(updated_lines):
            if line.startswith("## Compact Subtopic Status Map") and idx + 1 < len(updated_lines):
                updated_lines[idx + 1] = updated_lines[idx + 1].rstrip() + f" `{mark} {topic_num}`"
                break

    atomic_write_text(state_file, "\n".join(updated_lines[:59]) + "\n")
    print(
        dump_json(
            {
                "ok": True,
                "event_id": recorded_ev.get("event_id"),
                "topic": topic_num,
                "node_id": node_id,
                "objective_id": target_oid,
                "assessment_type": atype,
                "result": norm_result,
                "assistance_level": assistance_level,
                "stage": f"{stage}/3",
                "cp": f"{cp}/4",
                "status": event["status"],
                "next_review_at": review_item.get("next_review_at"),
                "events_file": str(events_path),
                "state_file": str(state_file),
            }
        )
    )
    return 0


def cmd_context(args: argparse.Namespace) -> int:
    """Return bounded operational state + curriculum node + objectives + gaps + due summary + 1-hop neighbors."""
    sess_dir = resolve_session_dir(args.vault_path, session_slug=getattr(args, "session", None))
    topic_num = normalize_topic_num(args.topic)
    node_id = f"topic-{topic_num}"

    state_file = sess_dir / "00-SESSION-STATE.md"
    fields = parse_session_state_fields(read_text_safe(state_file)) if state_file.is_file() else {}
    stage_cp = fields.get("stage_cp", "")
    m_cp = re.search(r"Checkpoint\s*\[?([0-9]+)/[0-9]+\]?", stage_cp)
    active_cp = int(m_cp.group(1)) if m_cp else 1

    graph = load_json_dict(sess_dir / "00-GRAPH.json") or rebuild_curriculum_graph(sess_dir)
    curriculum = load_curriculum(sess_dir)
    nodes = graph.get("nodes", {})
    c_nodes = curriculum.get("nodes", {})

    gnode = nodes.get(node_id)
    cnode = c_nodes.get(node_id)
    if gnode is None and cnode is None:
        print(dump_json({"error": f"Topic {node_id} not found"}), file=sys.stderr)
        return 1

    merged_node = dict(cnode or {})
    merged_node.update(gnode or {})

    # Optional read-only fallback if a legacy topic file exists and internal curriculum has no summary/anchor
    legacy_slice: dict[str, str] = {}
    legacy_rel = str(merged_node.get("file") or merged_node.get("source_file") or "")
    if legacy_rel and not merged_node.get("objective") and not merged_node.get("anchor"):
        legacy_path = sess_dir / legacy_rel
        if legacy_path.is_file():
            topic_text = read_text_safe(legacy_path)
            if args.section:
                sections_to_load = [args.section]
            elif active_cp <= 1:
                sections_to_load = ["L1-ANCHOR", "L2-PREREQS-AND-MOTIVATION"]
            elif active_cp == 2:
                sections_to_load = ["L3-FOUR-LAYER-THEORY", "L4-DERIVATION-AND-CODE"]
            else:
                sections_to_load = ["L5-WORKBOOK-AND-GRAPH"]
            for sec in sections_to_load:
                try:
                    legacy_slice[sec] = extract_section(topic_text, sec)
                except ValueError:
                    pass

    queue_file = sess_dir / "scratchpad" / f"queue-{topic_num}.json"
    queue_data = load_json_dict(queue_file)
    all_events = load_events(sess_dir)
    topic_events = [e for e in all_events if normalize_topic_num(str(e.get("topic", ""))) == topic_num]
    recent_events = topic_events[-10:]

    # Derive current objectives for this topic
    objs = normalize_objectives_list(node_id, merged_node)
    derived_objs = []
    for idx, obj in enumerate(objs):
        oid = obj["id"]
        oevs = [e for e in topic_events if e.get("objective_id") == oid]
        if idx == 0:
            oevs.extend(e for e in topic_events if not e.get("objective_id"))
        derived_objs.append(
            derive_objective_evidence(
                obj,
                oevs,
                node_status=str(merged_node.get("status") or "unstarted"),
                node_checkpoint=str(merged_node.get("checkpoint") or "0/4"),
            )
        )

    neighbor_ids: list[str] = []
    for key in ("depends_on", "contrasts_with"):
        for nid in merged_node.get(key, []):
            if nid not in neighbor_ids:
                neighbor_ids.append(nid)

    neighbors: dict[str, Any] = {}
    for nid in neighbor_ids[:4]:
        ng = nodes.get(nid, {})
        nc = c_nodes.get(nid, {})
        if ng or nc:
            neighbors[nid] = {
                "title": ng.get("title") or nc.get("title") or nid,
                "status": ng.get("status", "unstarted"),
                "anchor": nc.get("anchor") or nc.get("summary") or ng.get("last_invariant") or "",
            }

    curriculum_view = {
        "title": merged_node.get("title", node_id),
        "objective": merged_node.get("objective", ""),
        "anchor": merged_node.get("anchor", ""),
        "summary": merged_node.get("summary", ""),
        "key_concepts": merged_node.get("key_concepts", []),
        "key_equations": merged_node.get("key_equations", []),
        "depends_on": merged_node.get("depends_on", []),
        "unlocks": merged_node.get("unlocks", []),
        "contrasts_with": merged_node.get("contrasts_with", []),
        "objectives": [
            {
                "id": o["id"],
                "description": o["description"],
                "required": o["required"],
                "in_scope": o["in_scope"],
                "coverage_status": o["coverage_status"],
                "proficiency_status": o["proficiency"]["status"],
                "retention_status": o["proficiency"]["retention"]["status"],
                "transfer_status": o["proficiency"]["transfer"]["status"],
                "unresolved_gaps": o["unresolved_gaps"],
                "evidence_summary": o["evidence_summary"],
            }
            for o in derived_objs[:8]
        ],
    }
    if legacy_slice:
        curriculum_view["legacy_read_only_slices"] = legacy_slice

    lr_refs = [
        {"file": r["file"], "title": r["title"], "status": r["status"]}
        for r in load_learning_records(sess_dir)
        if not r.get("status", "").startswith("superseded")
    ][-5:]

    mission = load_mission(sess_dir)
    rev_store = load_review_state(sess_dir)
    now_arg = getattr(args, "now", None)
    due_all = get_due_reviews(curriculum, all_events, rev_store, now=now_arg, limit=50)
    cov = derive_session_coverage_and_gaps(curriculum, all_events, mission=mission, review_due=due_all)

    bundle = {
        "topic": node_id,
        "session_dir": str(sess_dir),
        "status": merged_node.get("status", "unstarted"),
        "checkpoint": merged_node.get("checkpoint", "0/4"),
        "active_subtopic": fields.get("active_topic", ""),
        "stage_cp": stage_cp,
        "last_invariant": fields.get("last_invariant", ""),
        "curriculum": curriculum_view,
        "queue": queue_data,
        "recent_events": recent_events,
        "active_learning_records": lr_refs,
        "neighbors": neighbors,
        "prerequisite_states": mission.get("prerequisites", {}),
        "due_reviews_summary": {
            "total_due": len(due_all),
            "top_due": due_all[:5],
        },
        "gaps_summary": {
            "required_untested_count": len(cov["required_untested"]),
            "required_untested": cov["required_untested"][:6],
            "unresolved_objectives": [u for u in cov["unresolved_objectives"] if u["topic_id"] == node_id][:5],
            "unresolved_prerequisites": cov["unresolved_prerequisites"][:5],
        },
    }
    print(dump_json(bundle))
    return 0


def cmd_flush(args: argparse.Namespace) -> int:
    """Persist [4/4] legacy completion into operational state only (never mutates study notes).

    Does NOT fabricate independent assistance, delayed retention, or transfer evidence.
    """
    sess_dir = resolve_session_dir(args.vault_path, session_slug=getattr(args, "session", None))
    topic_num = normalize_topic_num(args.topic)
    node_id = f"topic-{topic_num}"
    now_iso = format_utc_ts(parse_utc_ts(getattr(args, "now", None)))

    graph_path = sess_dir / "00-GRAPH.json"
    graph = load_json_dict(graph_path)
    if graph is None:
        graph = rebuild_curriculum_graph(sess_dir)

    nodes = dict(graph.get("nodes", {}))
    order = list(graph.get("order", []))
    if node_id not in nodes:
        print(dump_json({"error": f"Topic {node_id} not found in {graph_path}"}), file=sys.stderr)
        return 1

    node = dict(nodes[node_id])
    node["status"] = "mastered"
    node["checkpoint"] = "4/4"
    node["mastered_at"] = now_iso
    if args.note:
        node["last_invariant"] = args.note
    ledger = dict(node.get("checkpoints_passed") or {})
    for cp_key in ("1/4", "2/4", "3/4", "4/4"):
        ledger[cp_key] = True
    node["checkpoints_passed"] = ledger
    nodes[node_id] = node
    graph["nodes"] = nodes
    if node_id not in order:
        order.append(node_id)
    graph["order"] = order
    atomic_write_text(graph_path, json.dumps(graph, indent=2, ensure_ascii=False) + "\n")

    curr_path = sess_dir / "scratchpad" / "curriculum.json"
    curr = load_curriculum(sess_dir)
    if curr_path.is_file() and node_id in curr.get("nodes", {}):
        cnode = curr["nodes"][node_id]
        cnode["status"] = "mastered"
        cnode["checkpoint"] = "4/4"
        cnode["mastered_at"] = now_iso
        objs = normalize_objectives_list(node_id, cnode)
        t_evs = load_events(sess_dir, topic_num=topic_num)
        rev_store = load_review_state(sess_dir)
        for idx, obj in enumerate(objs):
            oevs = [e for e in t_evs if e.get("objective_id") == obj["id"]]
            if idx == 0:
                oevs.extend(e for e in t_evs if not e.get("objective_id"))
            derived = derive_objective_evidence(obj, oevs, node_status="mastered", node_checkpoint="4/4")
            objs[idx] = derived
            sync_review_item_for_legacy_node(
                rev_store,
                target_id=obj["id"],
                topic_id=node_id,
                last_ts=now_iso,
                legacy_mastered=bool(derived["proficiency"].get("legacy_completed")),
            )
        cnode["objectives"] = objs
        save_curriculum(sess_dir, curr)
        save_review_state(sess_dir, rev_store)

    state_file = sess_dir / "00-SESSION-STATE.md"
    if state_file.is_file():
        s_lines = read_text_safe(state_file).splitlines()
        token_re = re.compile(rf"`\[[ x~]\]\s*{re.escape(topic_num)}`")
        out_s: list[str] = []
        for line in s_lines:
            if args.note and line.lstrip().startswith("- **Last Verified Invariant:**"):
                out_s.append(f"- **Last Verified Invariant:** {args.note}")
            elif line.lstrip().startswith("- **Live Stage & Checkpoint:**"):
                out_s.append("- **Live Stage & Checkpoint:** `Depth Stage 3/3 | Checkpoint [4/4]`")
            elif token_re.search(line):
                out_s.append(token_re.sub(f"`[x] {topic_num}`", line))
            else:
                out_s.append(line)
        atomic_write_text(state_file, "\n".join(out_s[:59]) + "\n")

    print(
        dump_json(
            {
                "ok": True,
                "flushed": node_id,
                "state_only": True,
                "graph_nodes": len(nodes),
                "retention_verified": False,
                "transfer_verified": False,
            }
        )
    )
    return 0


def cmd_coverage(args: argparse.Namespace) -> int:
    sess_dir = resolve_session_dir(args.vault_path, session_slug=getattr(args, "session", None))
    curriculum = load_curriculum(sess_dir)
    events = load_events(sess_dir)
    mission = load_mission(sess_dir)
    rev_store = load_review_state(sess_dir)
    due = get_due_reviews(curriculum, events, rev_store, now=getattr(args, "now", None), limit=50)
    cov = derive_session_coverage_and_gaps(curriculum, events, mission=mission, review_due=due)
    cov["session_dir"] = str(sess_dir)
    cov["topic"] = curriculum.get("topic", sess_dir.name)
    print(dump_json(cov))
    return 0


def cmd_progress(args: argparse.Namespace) -> int:
    sess_dir = resolve_session_dir(args.vault_path, session_slug=getattr(args, "session", None))
    curriculum = load_curriculum(sess_dir)
    events = load_events(sess_dir)
    mission = load_mission(sess_dir)
    rev_store = load_review_state(sess_dir)
    due = get_due_reviews(curriculum, events, rev_store, now=getattr(args, "now", None), limit=50)
    cov = derive_session_coverage_and_gaps(curriculum, events, mission=mission, review_due=due)
    out = {
        "session_dir": str(sess_dir),
        "topic": curriculum.get("topic", sess_dir.name),
        "required_scope_coverage": {
            "demonstrated": cov["required_objectives_demonstrated"],
            "total": cov["required_objectives_total"],
            "scope_complete": cov["scope_complete"],
            "untested_count": len(cov["required_untested"]),
        },
        "independent_successes": cov["independent_successes"],
        "assisted_successes": cov["assisted_successes"],
        "unresolved_prerequisites_count": len(cov["unresolved_prerequisites"]),
        "unresolved_objectives_count": len(cov["unresolved_objectives"]),
        "delayed_recall_retained_objectives": cov["delayed_retained_objectives"],
        "transfer_demonstrated_objectives": cov["transfer_demonstrated_objectives"],
        "due_reviews_count": cov["due_reviews_count"],
        "active_time_sec": cov["active_time_total_sec"] if cov["active_time_total_sec"] is not None else "unavailable",
    }
    print(dump_json(out))
    return 0


def cmd_due(args: argparse.Namespace) -> int:
    sess_dir = resolve_session_dir(args.vault_path, session_slug=getattr(args, "session", None))
    curriculum = load_curriculum(sess_dir)
    events = load_events(sess_dir)
    rev_store = load_review_state(sess_dir)
    due_items = get_due_reviews(
        curriculum,
        events,
        rev_store,
        now=getattr(args, "now", None),
        limit=getattr(args, "limit", 10),
    )
    print(
        dump_json(
            {
                "session_dir": str(sess_dir),
                "due_count": len(due_items),
                "intervals_days": rev_store.get("intervals_days"),
                "policy_note": rev_store.get("policy_note"),
                "due_items": due_items,
            }
        )
    )
    return 0


def cmd_calibrate(args: argparse.Namespace) -> int:
    sess_dir = resolve_session_dir(args.vault_path, session_slug=getattr(args, "session", None))
    updates: dict[str, Any] = {}
    if getattr(args, "goal", None):
        updates["goal"] = args.goal.strip()
    if getattr(args, "in_scope", None):
        updates["in_scope"] = [x.strip() for x in args.in_scope.split(",") if x.strip()]
    if getattr(args, "out_of_scope", None):
        updates["out_of_scope"] = [x.strip() for x in args.out_of_scope.split(",") if x.strip()]
    if getattr(args, "background", None):
        updates["prior_knowledge"] = args.background.strip()
    if getattr(args, "time_budget", None) is not None:
        updates["time_budget_minutes"] = int(args.time_budget)
    if getattr(args, "deadline", None):
        updates["deadline"] = args.deadline.strip()
    if getattr(args, "language", None):
        updates["language"] = args.language.strip()
    if getattr(args, "constraint", None):
        updates["explanation_constraints"] = [c.strip() for c in args.constraint if c.strip()]
    if getattr(args, "depth_mode", None):
        updates["depth_mode"] = args.depth_mode.strip()
    if getattr(args, "diagnostic_status", None):
        updates["diagnostic"] = {
            "status": args.diagnostic_status.strip(),
            "tasks_asked": int(getattr(args, "diagnostic_tasks", 0) or 0),
            "skipped": args.diagnostic_status.strip() == "skipped",
        }

    prereq_updates: dict[str, dict[str, Any]] = {}
    for raw_p in getattr(args, "prereq", None) or []:
        if "=" not in raw_p:
            raise ValueError(f"Invalid --prereq format {raw_p!r}; expected name=state[:evidence]")
        name_part, rest = raw_p.split("=", 1)
        if ":" in rest:
            state_part, ev_part = rest.split(":", 1)
        else:
            state_part, ev_part = rest, ""
        prereq_updates[name_part.strip()] = {"state": state_part.strip(), "evidence": ev_part.strip()}

    mission = save_mission(sess_dir, updates=updates, prerequisite_updates=prereq_updates or None)
    print(dump_json({"ok": True, "session_dir": str(sess_dir), "mission": mission}))
    return 0


def cmd_revise_curriculum(args: argparse.Namespace) -> int:
    sess_dir = resolve_session_dir(args.vault_path, session_slug=getattr(args, "session", None))
    deps = [x.strip() for x in (getattr(args, "depends_on", "") or "").split(",") if x.strip()]
    unlocks = [x.strip() for x in (getattr(args, "unlocks", "") or "").split(",") if x.strip()]
    prefs = [x.strip() for x in (getattr(args, "prerequisite_ref", None) or []) if x.strip()]
    assumptions = [x.strip() for x in (getattr(args, "assumption", None) or []) if x.strip()]
    expected = [x.strip() for x in (getattr(args, "expected_assessment", None) or []) if x.strip()]

    req_flag: bool | None = None
    if getattr(args, "required", False):
        req_flag = True
    elif getattr(args, "optional", False):
        req_flag = False

    in_scope_flag: bool | None = None
    if getattr(args, "out_of_scope", False):
        in_scope_flag = False
    elif getattr(args, "in_scope", False):
        in_scope_flag = True

    res = revise_curriculum(
        sess_dir,
        node_id=getattr(args, "node_id", None),
        slug=getattr(args, "slug", None),
        title=getattr(args, "title", None),
        objective_desc=getattr(args, "objective", None),
        depends_on=deps or None,
        unlocks=unlocks or None,
        before_topic=getattr(args, "before_topic", None),
        required=req_flag,
        in_scope=in_scope_flag,
        target_topic=getattr(args, "target_topic", None),
        objective_id=getattr(args, "objective_id", None),
        prerequisite_refs=prefs or None,
        assumptions=assumptions or None,
        expected_assessments=expected or None,
    )
    print(dump_json(res))
    return 0


def cmd_migrate(args: argparse.Namespace) -> int:
    sess_dir = resolve_session_dir(args.vault_path, session_slug=getattr(args, "session", None))
    res = migrate_session_state(sess_dir)
    print(dump_json(res))
    return 0


def cmd_record_media(args: argparse.Namespace) -> int:
    sess_dir = resolve_session_dir(args.vault_path, session_slug=getattr(args, "session", None))
    entry = record_media_provenance(
        sess_dir,
        objective_id=args.objective,
        kind=args.kind,
        source_page_url=args.source_page or "",
        asset_url=args.asset_url or "",
        title=args.title or "",
        creator=args.creator or "",
        license_info=args.license or "",
        verification_status=args.verification,
        local_path=args.local_path or "",
        assumptions=args.assumption or [],
        fallback_text=args.fallback_text or "",
        retrieved_at=args.retrieved_at,
    )
    print(dump_json({"ok": True, "entry": entry}))
    return 0


def cmd_validate_state(args: argparse.Namespace) -> int:
    sess_dir = resolve_session_dir(args.vault_path, session_slug=getattr(args, "session", None))
    report = validate_session_state(sess_dir)
    print(dump_json(report))
    return 0 if report["ok"] else 1


def cmd_import_legacy(args: argparse.Namespace) -> int:
    src = Path(os.path.expandvars(args.source_vault)).expanduser().resolve()
    target = (
        Path(os.path.expandvars(args.target)).expanduser().resolve()
        if getattr(args, "target", None)
        else None
    )
    try:
        res = import_legacy_vault(src, target_dir=target)
    except (FileNotFoundError, ValueError) as exc:
        print(dump_json({"ok": False, "error": str(exc)}), file=sys.stderr)
        return 1
    print(dump_json(res))
    return 0


def cmd_handoff(args: argparse.Namespace) -> int:
    sess_dir: Path | None = None
    if args.vault_path or getattr(args, "session", None):
        sess_dir = resolve_session_dir(args.vault_path, session_slug=getattr(args, "session", None))
    else:
        try:
            sess_dir = resolve_session_dir(None)
        except FileNotFoundError:
            sess_dir = None

    examples = [e for e in (args.example or []) if e.strip()]
    envelope = build_handoff_envelope(
        session_dir=sess_dir,
        requested_artifact=args.request,
        topic=args.topic_name or "",
        topic_num=args.topic,
        requested_scope=args.scope or "",
        request_id=args.request_id,
        destination_constraints=args.destination or "",
        examples_used=examples,
        persist=bool(args.persist),
    )
    print(dump_json(envelope))
    return 0


def _add_assessment_args(parser: argparse.ArgumentParser, *, require_cp: bool = False) -> None:
    parser.add_argument("vault_path", nargs="?", default=None, help="Path to session or Obsidian vault (optional).")
    parser.add_argument("--session", default=None, help="Optional vault-native session slug.")
    parser.add_argument("--topic", required=True, help="Subtopic number or ID (e.g. 03 or topic-03).")
    parser.add_argument("--objective", default=None, help="Objective ID within topic (defaults to primary objective).")
    parser.add_argument("--cp", required=require_cp, type=int, choices=[1, 2, 3, 4], default=None, help="Optional legacy checkpoint 1..4.")
    parser.add_argument("--status", default=None, choices=["pass", "retry", "fail", "partial", "skipped"], help="Assessment outcome.")
    parser.add_argument("--result", default=None, choices=list(ASSESSMENT_RESULTS) + ["retry"], help="Assessment outcome alias.")
    parser.add_argument("--assistance", default=None, choices=list(ASSISTANCE_LEVELS), help="Assistance level (none|hint|scaffold|worked_example|unknown).")
    parser.add_argument("--assessment-type", default=None, choices=list(ASSESSMENT_TYPES), help="Assessment task type.")
    parser.add_argument("--item-id", default="", help="Assessment item identifier.")
    parser.add_argument("--attempt-id", default=None, help="Stable attempt ID for idempotent retries.")
    parser.add_argument("--stage", type=int, choices=[1, 2, 3], default=None, help="Optional depth stage 1..3.")
    parser.add_argument("--note", default="", help="Optional short invariant/misconception note.")
    parser.add_argument("--rationale", default="", help="Brief grading rationale.")
    parser.add_argument("--misconception", default=None, help="Misconception reference (e.g. LR-0001).")
    parser.add_argument("--confidence", default=None, help="Learner-supplied confidence (only when explicitly stated).")
    parser.add_argument("--active-time", type=float, default=None, help="Reliable active learning time in seconds.")
    parser.add_argument("--response-summary", default=None, help="Concise learner response excerpt/summary.")
    parser.add_argument("--transfer-context", default=None, help="Unfamiliar transfer context description.")
    parser.add_argument("--session-run", default=None, help="Current session run identifier for same-session checks.")
    parser.add_argument("--now", default=None, help="Optional fixed UTC ISO timestamp for deterministic scheduling.")
    parser.add_argument("--checked", action="store_true", help="Mark generated exercise arithmetic/code as verified.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="vault_cli.py",
        description="Deterministic operational learning-state CLI for /teachme.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_state = sub.add_parser("state", help="Print compact JSON session state summary.")
    p_state.add_argument("vault_path", nargs="?", default=None, help="Path to session or Obsidian vault (optional).")
    p_state.add_argument("--session", default=None, help="Optional vault-native session slug.")
    p_state.add_argument("--now", default=None, help="Optional fixed UTC ISO timestamp.")
    p_state.set_defaults(func=cmd_state)

    p_graph = sub.add_parser("graph", help="Rebuild/validate 00-GRAPH.json curriculum dependency graph.")
    p_graph.add_argument("vault_path", nargs="?", default=None, help="Path to session or Obsidian vault (optional).")
    p_graph.add_argument("--session", default=None, help="Optional vault-native session slug.")
    p_graph.set_defaults(func=cmd_graph)

    p_slice = sub.add_parser("slice", help="Read-only extractor for an HTML-comment section in a Markdown file.")
    p_slice.add_argument("markdown_file", help="Path to Markdown file.")
    p_slice.add_argument("--section", required=True, help="Section name (e.g. L0-L1, L1-ANCHOR).")
    p_slice.set_defaults(func=cmd_slice)

    p_tick = sub.add_parser("tick", help="Append checkpoint/assessment event to events.jsonl and update operational state.")
    _add_assessment_args(p_tick, require_cp=False)
    p_tick.set_defaults(func=cmd_tick)

    p_assess = sub.add_parser("assess", help="Record objective-level assessment evidence and update review schedule.")
    _add_assessment_args(p_assess, require_cp=False)
    p_assess.set_defaults(func=cmd_tick)

    p_init = sub.add_parser("init", help="Initialize operational session state only (no study-note scaffolds).")
    p_init.add_argument("vault_path", help="Target session directory or connected Obsidian vault root.")
    p_init.add_argument("--session", default=None, help="Optional vault-native session slug.")
    p_init.add_argument("--topic", default="", help="Human-readable topic title.")
    p_init.add_argument("--title", default="", help="Alias for --topic.")
    p_init.add_argument("--subtopics", default="", help="Path to JSON file listing curriculum subtopics.")
    p_init.add_argument("--curriculum", default="", help="Alias for --subtopics.")
    p_init.add_argument("--topics", default="", help="Comma-separated topic slugs fallback (e.g. 01-intro,02-core).")
    p_init.add_argument("--goal", default=None, help="Agreed learning goal.")
    p_init.add_argument("--in-scope", default=None, help="Comma-separated in-scope areas.")
    p_init.add_argument("--out-of-scope", default=None, help="Comma-separated out-of-scope exclusions.")
    p_init.set_defaults(func=cmd_init)

    p_context = sub.add_parser("context", help="Return bounded state + curriculum + objectives + gaps + due summary.")
    p_context.add_argument("vault_path", nargs="?", default=None, help="Path to session or Obsidian vault (optional).")
    p_context.add_argument("--session", default=None, help="Optional vault-native session slug.")
    p_context.add_argument("--topic", required=True, help="Subtopic number or ID (e.g. 03 or topic-03).")
    p_context.add_argument("--section", default=None, help="Optional section override for legacy read-only fallback.")
    p_context.add_argument("--now", default=None, help="Optional fixed UTC ISO timestamp.")
    p_context.set_defaults(func=cmd_context)

    p_cov = sub.add_parser("coverage", help="Show objective-level coverage, proficiency, and unresolved gaps.")
    p_cov.add_argument("vault_path", nargs="?", default=None, help="Path to session or Obsidian vault (optional).")
    p_cov.add_argument("--session", default=None, help="Optional vault-native session slug.")
    p_cov.add_argument("--now", default=None, help="Optional fixed UTC ISO timestamp.")
    p_cov.set_defaults(func=cmd_coverage)

    p_prog = sub.add_parser("progress", help="Show honest measurement summary without fabricated metrics.")
    p_prog.add_argument("vault_path", nargs="?", default=None, help="Path to session or Obsidian vault (optional).")
    p_prog.add_argument("--session", default=None, help="Optional vault-native session slug.")
    p_prog.add_argument("--now", default=None, help="Optional fixed UTC ISO timestamp.")
    p_prog.set_defaults(func=cmd_progress)

    p_due = sub.add_parser("due", help="List prioritized due reviews without mutating learning state.")
    p_due.add_argument("vault_path", nargs="?", default=None, help="Path to session or Obsidian vault (optional).")
    p_due.add_argument("--session", default=None, help="Optional vault-native session slug.")
    p_due.add_argument("--now", default=None, help="Optional fixed UTC ISO timestamp.")
    p_due.add_argument("--limit", type=int, default=10, help="Maximum due items to return.")
    p_due.set_defaults(func=cmd_due)

    p_cal = sub.add_parser("calibrate", help="Update calibration baseline and diagnostic prerequisite states.")
    p_cal.add_argument("vault_path", nargs="?", default=None, help="Path to session or Obsidian vault (optional).")
    p_cal.add_argument("--session", default=None, help="Optional vault-native session slug.")
    p_cal.add_argument("--goal", default=None)
    p_cal.add_argument("--in-scope", default=None, help="Comma-separated in-scope items.")
    p_cal.add_argument("--out-of-scope", default=None, help="Comma-separated out-of-scope items.")
    p_cal.add_argument("--background", default=None)
    p_cal.add_argument("--time-budget", type=int, default=None, help="Available minutes if time-constrained.")
    p_cal.add_argument("--deadline", default=None)
    p_cal.add_argument("--language", default=None)
    p_cal.add_argument("--constraint", action="append", default=None, help="Explanation constraint (repeatable).")
    p_cal.add_argument("--depth-mode", default=None)
    p_cal.add_argument("--diagnostic-status", choices=["offered", "completed", "skipped", "in_progress"], default=None)
    p_cal.add_argument("--diagnostic-tasks", type=int, default=None)
    p_cal.add_argument("--prereq", action="append", default=None, help="Prerequisite state: name=unknown|needs_support|demonstrated[:evidence]")
    p_cal.set_defaults(func=cmd_calibrate)

    p_rev = sub.add_parser("revise-curriculum", help="Add prerequisite node or update objective while preserving IDs, evidence, and resume state.")
    p_rev.add_argument("vault_path", nargs="?", default=None, help="Path to session or Obsidian vault (optional).")
    p_rev.add_argument("--session", default=None, help="Optional vault-native session slug.")
    p_rev.add_argument("--node-id", default=None, help="New topic node ID (e.g. topic-00).")
    p_rev.add_argument("--slug", default=None, help="New topic slug (e.g. 00-slopes).")
    p_rev.add_argument("--title", default=None, help="New topic title.")
    p_rev.add_argument("--depends-on", default="", help="Comma-separated dependency topic IDs.")
    p_rev.add_argument("--unlocks", default="", help="Comma-separated unlocked topic IDs.")
    p_rev.add_argument("--before-topic", default=None, help="Insert new topic before this topic number/ID.")
    p_rev.add_argument("--target-topic", default=None, help="Existing topic number/ID for objective add/update.")
    p_rev.add_argument("--objective-id", default=None, help="Objective ID to add or update.")
    p_rev.add_argument("--objective", default=None, help="Objective description.")
    p_rev.add_argument("--prerequisite-ref", action="append", default=None, help="Objective or topic prerequisite reference.")
    p_rev.add_argument("--assumption", action="append", default=None, help="Relevant assumption.")
    p_rev.add_argument("--expected-assessment", action="append", default=None, help="Expected assessment dimension/type.")
    p_rev.add_argument("--required", action="store_true", help="Mark objective required within agreed scope.")
    p_rev.add_argument("--optional", action="store_true", help="Mark objective optional within agreed scope.")
    p_rev.add_argument("--in-scope", action="store_true", help="Mark objective in scope.")
    p_rev.add_argument("--out-of-scope", action="store_true", help="Mark objective outside agreed scope.")
    p_rev.set_defaults(func=cmd_revise_curriculum)

    p_flush = sub.add_parser("flush", help="Persist [4/4] legacy completion into operational state only (never mutates study notes).")
    p_flush.add_argument("vault_path", nargs="?", default=None, help="Path to session or Obsidian vault (optional).")
    p_flush.add_argument("--session", default=None, help="Optional vault-native session slug.")
    p_flush.add_argument("--topic", required=True, help="Subtopic number or ID (e.g. 01).")
    p_flush.add_argument("--note", default="", help="Optional verified invariant note.")
    p_flush.add_argument("--now", default=None, help="Optional fixed UTC ISO timestamp.")
    p_flush.set_defaults(func=cmd_flush)

    p_val = sub.add_parser("validate-state", help="Validate operational learning state files without inspecting study notes.")
    p_val.add_argument("vault_path", nargs="?", default=None, help="Path to session or Obsidian vault (optional).")
    p_val.add_argument("--session", default=None, help="Optional vault-native session slug.")
    p_val.set_defaults(func=cmd_validate_state)

    p_mig = sub.add_parser("migrate", help="Idempotently migrate v1 operational state to v2 with backup and validation.")
    p_mig.add_argument("vault_path", nargs="?", default=None, help="Path to session or Obsidian vault (optional).")
    p_mig.add_argument("--session", default=None, help="Optional vault-native session slug.")
    p_mig.set_defaults(func=cmd_migrate)

    p_med = sub.add_parser("record-media", help="Record verified/unverified media provenance without fabricating licenses.")
    p_med.add_argument("vault_path", nargs="?", default=None, help="Path to session or Obsidian vault (optional).")
    p_med.add_argument("--session", default=None, help="Optional vault-native session slug.")
    p_med.add_argument("--objective", required=True, help="Associated objective ID.")
    p_med.add_argument("--kind", default="retrieved_image", help="retrieved_image|generated_plot|diagram|experiment")
    p_med.add_argument("--source-page", default="", help="Source page URL.")
    p_med.add_argument("--asset-url", default="", help="Direct image/asset URL if known.")
    p_med.add_argument("--title", default="", help="Media title.")
    p_med.add_argument("--creator", default="", help="Author/creator if known.")
    p_med.add_argument("--license", default="", help="License/reuse info (defaults to 'unknown').")
    p_med.add_argument("--verification", default="metadata_only_unverified", choices=list(VERIFICATION_STATUSES))
    p_med.add_argument("--local-path", default="", help="Optional local cached path inside session directory.")
    p_med.add_argument("--assumption", action="append", default=[], help="Relevant visual assumption or limitation.")
    p_med.add_argument("--fallback-text", default="", help="Text fallback description.")
    p_med.add_argument("--retrieved-at", default=None, help="Optional UTC ISO timestamp.")
    p_med.set_defaults(func=cmd_record_media)

    p_imp = sub.add_parser("import-legacy", help="Non-destructively import legacy study-note-embedded memory into operational state.")
    p_imp.add_argument("source_vault", help="Path to legacy TeachMe vault.")
    p_imp.add_argument("--target", default=None, help="Optional target directory for imported operational state.")
    p_imp.set_defaults(func=cmd_import_legacy)

    p_hand = sub.add_parser("handoff", help="Generate a versioned teaching-context envelope for an optional note-writing skill.")
    p_hand.add_argument("vault_path", nargs="?", default=None, help="Path to session or Obsidian vault (optional).")
    p_hand.add_argument("--session", default=None, help="Optional vault-native session slug.")
    p_hand.add_argument("--topic", default=None, help="Optional subtopic number or ID to scope export.")
    p_hand.add_argument("--topic-name", default="", help="Human-readable topic name if no active session.")
    p_hand.add_argument("--request", default="study_notes", help="User's original artifact request.")
    p_hand.add_argument("--scope", default="", help="Requested scope (e.g. subtopic, full_topic, expansion).")
    p_hand.add_argument("--request-id", default=None, help="Optional request ID for retry deduplication.")
    p_hand.add_argument("--destination", default="", help="Explicit destination constraints, if known.")
    p_hand.add_argument("--example", action="append", default=[], help="Example/analogy actually used in lesson.")
    p_hand.add_argument("--persist", action="store_true", help="Optionally persist envelope under scratchpad/handoffs/.")
    p_hand.set_defaults(func=cmd_handoff)

    register_vault_native_subcommands(sub)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except (FileNotFoundError, ValueError) as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
