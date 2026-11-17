#!/usr/bin/env python3
"""Deterministic CLI for managing /teachme operational learning state.

Standard-library only (Python 3). Handles curriculum state initialization,
session recovery, checkpoint ticking, state-only mastery flushing, legacy
memory migration, state validation, read-only vault indexing, and Scriptorium
context-envelope generation. Never creates or modifies study notes.
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
from teachme_vault.models import (
    MODE_VAULT_NATIVE,
    atomic_write_text,
    detect_vault_mode,
    load_config,
    read_text_safe,
    resolve_state_dir,
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
    normalize_topic_num,
    rebuild_curriculum_graph,
    resolve_session_dir,
    save_curriculum,
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

    if not args.vault_path:
        mode_info = detect_vault_mode(None, config=cfg)
        if mode_info["mode"] == MODE_VAULT_NATIVE and cfg.get("obsidian_vault"):
            obs_path = Path(os.path.expandvars(str(cfg["obsidian_vault"]))).expanduser().resolve()
            if obs_path.is_dir():
                sdir = resolve_state_dir(obs_path, config=cfg)
                sessions = list_vault_native_sessions(obs_path, config=cfg)
                if session_slug or sessions:
                    try:
                        sess_dir = resolve_session_dir(None, session_slug=session_slug)
                        summary = _build_session_state_summary(sess_dir, mode="vault-native")
                        summary["obsidian_vault"] = str(obs_path)
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
                            "vault_path": str(obs_path),
                            "state_dir": str(sdir),
                            "has_index": (sdir / "index.json").is_file(),
                            "sessions": sessions,
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
                summary = _build_session_state_summary(sess_dir, mode="vault-native")
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
    print(dump_json(_build_session_state_summary(sess_dir, mode="standalone")))
    return 0


def _build_session_state_summary(sess_dir: Path, mode: str) -> dict[str, Any]:
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
    obs_cfg = str(cfg.get("obsidian_vault", "")).strip()
    is_configured_obs = bool(obs_cfg and Path(os.path.expandvars(obs_cfg)).expanduser().resolve() == raw_target)
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
    res = init_session_state(
        sess_dir,
        topic_title=eff_title,
        items=items,
        mode=eff_mode,
        vault_root=raw_target if is_obsidian_root else None,
    )
    print(dump_json(res))
    return 0


def cmd_tick(args: argparse.Namespace) -> int:
    sess_dir = resolve_session_dir(args.vault_path, session_slug=getattr(args, "session", None))
    topic_num = normalize_topic_num(args.topic)
    node_id = f"topic-{topic_num}"
    cp = int(args.cp)
    status = args.status
    stage = infer_depth_stage(cp, args.stage)

    scratchpad = sess_dir / "scratchpad"
    scratchpad.mkdir(parents=True, exist_ok=True)
    events_path = scratchpad / "events.jsonl"

    event: dict[str, Any] = {
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "topic": topic_num,
        "stage": stage,
        "cp": cp,
        "status": status,
    }
    if args.note:
        event["note"] = args.note

    with events_path.open("a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")

    # Update 00-GRAPH.json operationally without touching any study notes
    graph_path = sess_dir / "00-GRAPH.json"
    graph = load_json_dict(graph_path) or {"schema_version": 2, "kind": "curriculum_dependency_graph", "nodes": {}, "order": []}
    nodes = dict(graph.get("nodes", {}))
    order = list(graph.get("order", []))
    node = dict(nodes.get(node_id, {"title": node_id, "depends_on": [], "unlocks": [], "contrasts_with": [], "fixes_failure_of": []}))
    node["checkpoint"] = f"{cp}/4"
    if node.get("status") != "mastered":
        node["status"] = "mastered" if (cp == 4 and status == "pass") else "in_progress"
    if args.note and status == "pass":
        node["last_invariant"] = args.note
    ev_list = list(node.get("evidence", []))
    ev_list.append({"ts": event["ts"], "cp": cp, "status": status, "note": args.note or ""})
    node["evidence"] = ev_list[-20:]
    nodes[node_id] = node
    if node_id not in order:
        order.append(node_id)
    graph["nodes"] = nodes
    graph["order"] = order
    atomic_write_text(graph_path, json.dumps(graph, indent=2, ensure_ascii=False) + "\n")

    state_file = sess_dir / "00-SESSION-STATE.md"
    mark = "[x]" if (cp == 4 and status == "pass") else "[~]"
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
        elif args.note and status == "pass" and line.lstrip().startswith("- **Last Verified Invariant:**"):
            updated_lines.append(f"- **Last Verified Invariant:** {args.note}")
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
                "topic": topic_num,
                "node_id": node_id,
                "stage": f"{stage}/3",
                "cp": f"{cp}/4",
                "status": status,
                "events_file": str(events_path),
                "state_file": str(state_file),
            }
        )
    )
    return 0


def cmd_context(args: argparse.Namespace) -> int:
    """Return operational state + curriculum node + queue + recent evidence + 1-hop anchors."""
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
    recent_events = load_events(sess_dir, topic_num=topic_num)[-10:]

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
    }
    if legacy_slice:
        curriculum_view["legacy_read_only_slices"] = legacy_slice

    lr_refs = [
        {"file": r["file"], "title": r["title"], "status": r["status"]}
        for r in load_learning_records(sess_dir)
        if not r.get("status", "").startswith("superseded")
    ][-5:]

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
    }
    print(dump_json(bundle))
    return 0


def cmd_flush(args: argparse.Namespace) -> int:
    """Persist [4/4] mastery into operational state only (never mutates study notes)."""
    sess_dir = resolve_session_dir(args.vault_path, session_slug=getattr(args, "session", None))
    topic_num = normalize_topic_num(args.topic)
    node_id = f"topic-{topic_num}"
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

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
    if curr_path.is_file():
        curr = load_curriculum(sess_dir)
        if node_id in curr.get("nodes", {}):
            curr["nodes"][node_id]["status"] = "mastered"
            curr["nodes"][node_id]["checkpoint"] = "4/4"
            save_curriculum(sess_dir, curr)

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
            }
        )
    )
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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="vault_cli.py",
        description="Deterministic operational learning-state CLI for /teachme.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_state = sub.add_parser("state", help="Print compact JSON session state summary.")
    p_state.add_argument("vault_path", nargs="?", default=None, help="Path to session or Obsidian vault (optional).")
    p_state.add_argument("--session", default=None, help="Optional vault-native session slug.")
    p_state.set_defaults(func=cmd_state)

    p_graph = sub.add_parser("graph", help="Rebuild/validate 00-GRAPH.json curriculum dependency graph.")
    p_graph.add_argument("vault_path", nargs="?", default=None, help="Path to session or Obsidian vault (optional).")
    p_graph.add_argument("--session", default=None, help="Optional vault-native session slug.")
    p_graph.set_defaults(func=cmd_graph)

    p_slice = sub.add_parser("slice", help="Read-only extractor for an HTML-comment section in a Markdown file.")
    p_slice.add_argument("markdown_file", help="Path to Markdown file.")
    p_slice.add_argument("--section", required=True, help="Section name (e.g. L0-L1, L1-ANCHOR).")
    p_slice.set_defaults(func=cmd_slice)

    p_tick = sub.add_parser("tick", help="Append checkpoint event to events.jsonl and update operational state.")
    p_tick.add_argument("vault_path", nargs="?", default=None, help="Path to session or Obsidian vault (optional).")
    p_tick.add_argument("--session", default=None, help="Optional vault-native session slug.")
    p_tick.add_argument("--topic", required=True, help="Subtopic number or ID (e.g. 03 or topic-03).")
    p_tick.add_argument("--cp", required=True, type=int, choices=[1, 2, 3, 4], help="Checkpoint 1..4.")
    p_tick.add_argument("--status", required=True, choices=["pass", "retry"], help="Checkpoint outcome.")
    p_tick.add_argument("--stage", type=int, choices=[1, 2, 3], default=None, help="Optional depth stage 1..3.")
    p_tick.add_argument("--note", default="", help="Optional short invariant/misconception note.")
    p_tick.set_defaults(func=cmd_tick)

    p_init = sub.add_parser("init", help="Initialize operational session state only (no study-note scaffolds).")
    p_init.add_argument("vault_path", help="Target session directory or connected Obsidian vault root.")
    p_init.add_argument("--session", default=None, help="Optional vault-native session slug.")
    p_init.add_argument("--topic", default="", help="Human-readable topic title.")
    p_init.add_argument("--title", default="", help="Alias for --topic.")
    p_init.add_argument("--subtopics", default="", help="Path to JSON file listing curriculum subtopics.")
    p_init.add_argument("--curriculum", default="", help="Alias for --subtopics.")
    p_init.add_argument("--topics", default="", help="Comma-separated topic slugs fallback (e.g. 01-intro,02-core).")
    p_init.set_defaults(func=cmd_init)

    p_context = sub.add_parser("context", help="Return state + curriculum node + queue + evidence + 1-hop neighbors.")
    p_context.add_argument("vault_path", nargs="?", default=None, help="Path to session or Obsidian vault (optional).")
    p_context.add_argument("--session", default=None, help="Optional vault-native session slug.")
    p_context.add_argument("--topic", required=True, help="Subtopic number or ID (e.g. 03 or topic-03).")
    p_context.add_argument("--section", default=None, help="Optional section override for legacy read-only fallback.")
    p_context.set_defaults(func=cmd_context)

    p_flush = sub.add_parser("flush", help="Persist [4/4] mastery into operational state only (never mutates study notes).")
    p_flush.add_argument("vault_path", nargs="?", default=None, help="Path to session or Obsidian vault (optional).")
    p_flush.add_argument("--session", default=None, help="Optional vault-native session slug.")
    p_flush.add_argument("--topic", required=True, help="Subtopic number or ID (e.g. 01).")
    p_flush.add_argument("--note", default="", help="Optional verified invariant note.")
    p_flush.set_defaults(func=cmd_flush)

    p_val = sub.add_parser("validate-state", help="Validate operational learning state files without inspecting study notes.")
    p_val.add_argument("vault_path", nargs="?", default=None, help="Path to session or Obsidian vault (optional).")
    p_val.add_argument("--session", default=None, help="Optional vault-native session slug.")
    p_val.set_defaults(func=cmd_validate_state)

    p_imp = sub.add_parser("import-legacy", help="Non-destructively import legacy study-note-embedded memory into operational state.")
    p_imp.add_argument("source_vault", help="Path to legacy TeachMe vault.")
    p_imp.add_argument("--target", default=None, help="Optional target directory for imported operational state.")
    p_imp.set_defaults(func=cmd_import_legacy)

    p_hand = sub.add_parser("handoff", help="Generate a versioned teaching-context envelope for Scriptorium.")
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
