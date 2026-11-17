"""Operational learning-state management, legacy memory import, and context handoff."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
from typing import Any
import uuid

from .markdown_utils import parse_frontmatter_tolerant
from .models import (
    MODE_VAULT_NATIVE,
    atomic_write_text,
    detect_vault_mode,
    load_config,
    read_text_safe,
    redact_sensitive,
    resolve_state_dir,
    utc_now_iso,
)

HANDOFF_SCHEMA_VERSION = "1.0"
LEGACY_IMPORT_SCHEMA_VERSION = 1
TYPED_EDGE_FIELDS = (
    "depends_on",
    "unlocks",
    "contrasts_with",
    "fixes_failure_of",
)
KNOWN_FRONTMATTER_KEYS = frozenset(
    {
        "id",
        "title",
        "subtopic",
        "status",
        "checkpoint",
        "depends_on",
        "unlocks",
        "contrasts_with",
        "fixes_failure_of",
        "key_equations",
        "objective",
        "summary",
        "key_concepts",
        "anchor",
    }
)
KNOWN_GRAPH_NODE_KEYS = frozenset(
    {
        "file",
        "source_id",
        "source_file",
        "slug",
        "title",
        "status",
        "checkpoint",
        "depends_on",
        "unlocks",
        "contrasts_with",
        "fixes_failure_of",
        "objective",
        "summary",
        "key_concepts",
        "key_equations",
        "anchor",
        "last_invariant",
        "last_event_ts",
        "mastered_at",
        "evidence",
        "checkpoints_passed",
        "extra_metadata",
    }
)
LEDGER_LINE_RE = re.compile(r"^\s*-\s*\[([ xX])\]\s*`?\[([1-4])/4\]`?\s*(.*)$")


def slugify_topic(text: str) -> str:
    """Return a deterministic filesystem-safe slug for a topic name."""
    clean = re.sub(r"[^\w]+", "-", text.lower(), flags=re.UNICODE).strip("-_")
    if clean and re.fullmatch(r"[a-z0-9-]+", clean):
        return clean
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()[:6]
    return f"{clean}-{digest}" if clean else f"topic-{digest}"


def is_operational_session_dir(path: Path) -> bool:
    """Return True if path already holds standalone or isolated session state."""
    return (
        (path / "00-SESSION-STATE.md").is_file()
        or (path / "00-GRAPH.json").is_file()
        or (path / "scratchpad" / "curriculum.json").is_file()
    )


def list_vault_native_sessions(vault_root: Path, config: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """List isolated TeachMe sessions inside <vault>/.teachme/sessions/."""
    sdir = resolve_state_dir(vault_root, config=config)
    sessions_root = sdir / "sessions"
    if not sessions_root.is_dir():
        return []
    out: list[dict[str, Any]] = []
    for child in sorted(sessions_root.iterdir()):
        if not child.is_dir():
            continue
        state_file = child / "00-SESSION-STATE.md"
        graph_file = child / "00-GRAPH.json"
        if not state_file.is_file() and not graph_file.is_file():
            continue
        mtime = (state_file if state_file.is_file() else graph_file).stat().st_mtime
        out.append(
            {
                "slug": child.name,
                "session_dir": str(child),
                "mtime": mtime,
            }
        )
    out.sort(key=lambda item: item["mtime"], reverse=True)
    return out


def resolve_session_dir(
    raw_path: str | None,
    session_slug: str | None = None,
    topic_hint: str | None = None,
    for_init: bool = False,
) -> Path:
    """Resolve an operational session directory for standalone or vault-native mode."""
    cfg = load_config()
    if raw_path:
        resolved = Path(os.path.expandvars(raw_path)).expanduser().resolve()

        # If the user pointed at an Obsidian vault root (not an inner session dir),
        # isolate operational state inside <vault>/.teachme/sessions/<slug>/.
        if not is_operational_session_dir(resolved):
            obs_cfg = str(cfg.get("obsidian_vault", "")).strip()
            is_configured_obs = bool(
                obs_cfg and Path(os.path.expandvars(obs_cfg)).expanduser().resolve() == resolved
            )
            mode_info = detect_vault_mode(resolved, config=cfg)
            is_actual_obsidian = (
                (resolved / ".obsidian").is_dir()
                or (resolved / ".teachme").is_dir()
                or is_configured_obs
                or mode_info.get("reason") == "existing_non_teachme_markdown_detected"
            )
            if is_actual_obsidian and mode_info["mode"] == MODE_VAULT_NATIVE:
                sdir = resolve_state_dir(resolved, config=cfg)
                sessions_root = sdir / "sessions"
                if session_slug:
                    return sessions_root / slugify_topic(session_slug)
                if topic_hint and for_init:
                    return sessions_root / slugify_topic(topic_hint)
                existing = list_vault_native_sessions(resolved, config=cfg)
                if existing:
                    return Path(existing[0]["session_dir"])
                if for_init:
                    return sessions_root / slugify_topic(topic_hint or resolved.name)
                raise FileNotFoundError(
                    f"No isolated TeachMe session found in {sessions_root}"
                )
        return resolved

    # No explicit path: check active vault-native obsidian_vault or standalone notes_root
    mode_info = detect_vault_mode(None, config=cfg)
    if mode_info["mode"] == MODE_VAULT_NATIVE and cfg.get("obsidian_vault"):
        obs = Path(os.path.expandvars(str(cfg["obsidian_vault"]))).expanduser().resolve()
        if obs.is_dir():
            sdir = resolve_state_dir(obs, config=cfg)
            sessions_root = sdir / "sessions"
            if session_slug:
                target = sessions_root / slugify_topic(session_slug)
                if for_init or is_operational_session_dir(target):
                    return target
            existing = list_vault_native_sessions(obs, config=cfg)
            if existing:
                return Path(existing[0]["session_dir"])
            if for_init and topic_hint:
                return sessions_root / slugify_topic(topic_hint)
            raise FileNotFoundError(
                f"No isolated TeachMe session found under {sessions_root}"
            )

    raw_root = str(cfg.get("notes_root", "")).strip()
    state_root = (
        Path(os.path.expandvars(raw_root)).expanduser().resolve()
        if raw_root
        else (Path.home() / "notes").resolve()
    )
    if not state_root.is_dir():
        raise FileNotFoundError(f"Learning-state root does not exist: {state_root}")

    if session_slug:
        cand = state_root / slugify_topic(session_slug)
        if cand.is_dir() and is_operational_session_dir(cand):
            return cand

    candidates = [
        p for p in state_root.iterdir()
        if p.is_dir() and is_operational_session_dir(p)
    ]
    if not candidates:
        raise FileNotFoundError(
            f"No session with 00-SESSION-STATE.md or 00-GRAPH.json found under {state_root}"
        )
    candidates.sort(
        key=lambda p: (
            (p / "00-SESSION-STATE.md").stat().st_mtime
            if (p / "00-SESSION-STATE.md").is_file()
            else (p / "00-GRAPH.json").stat().st_mtime
        ),
        reverse=True,
    )
    return candidates[0]


def normalize_topic_num(raw_topic: str) -> str:
    """Normalize a topic identifier such as '3', '03', or 'topic-03' to '03'."""
    val = str(raw_topic).strip()
    if val.startswith("topic-"):
        val = val[len("topic-"):]
    return val.zfill(2) if val.isdigit() else val


def load_json_dict(path: Path) -> dict[str, Any] | None:
    """Load a JSON object file, returning None if absent or invalid."""
    if not path.is_file():
        return None
    try:
        data = json.loads(read_text_safe(path))
        return data if isinstance(data, dict) else None
    except (OSError, json.JSONDecodeError):
        return None


def load_curriculum(session_dir: Path) -> dict[str, Any]:
    """Load scratchpad/curriculum.json if present."""
    data = load_json_dict(session_dir / "scratchpad" / "curriculum.json")
    if data and isinstance(data.get("nodes"), dict):
        return data
    return {"schema_version": 1, "topic": "", "nodes": {}, "order": []}


def save_curriculum(session_dir: Path, curriculum: dict[str, Any]) -> Path:
    """Persist scratchpad/curriculum.json atomically."""
    out = session_dir / "scratchpad" / "curriculum.json"
    atomic_write_text(out, json.dumps(curriculum, indent=2, ensure_ascii=False) + "\n")
    return out


def load_events(session_dir: Path, topic_num: str | None = None) -> list[dict[str, Any]]:
    """Read scratchpad/events.jsonl entries, optionally filtered by topic number."""
    events_path = session_dir / "scratchpad" / "events.jsonl"
    if not events_path.is_file():
        return []
    items: list[dict[str, Any]] = []
    for raw in read_text_safe(events_path).splitlines():
        line = raw.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(obj, dict):
            continue
        if topic_num is None or normalize_topic_num(str(obj.get("topic", ""))) == topic_num:
            items.append(obj)
    return items


def load_learning_records(session_dir: Path) -> list[dict[str, Any]]:
    """Summarize learning-records/*.md entries without modifying them."""
    lr_dir = session_dir / "learning-records"
    if not lr_dir.is_dir():
        return []
    records: list[dict[str, Any]] = []
    for p in sorted(lr_dir.glob("*.md")):
        text = read_text_safe(p)
        lines = text.splitlines()
        title = p.stem
        status = "active"
        lesson = ""
        date = ""
        context_lines: list[str] = []
        insight_lines: list[str] = []
        section = ""
        for line in lines:
            s = line.strip()
            if s.startswith("# ") and title == p.stem:
                title = s[2:].strip()
            elif s.startswith("- **Date:**") or "**Status:**" in s:
                m_status = re.search(r"\*\*Status:\*\*\s*([^|\r\n]+)", s)
                if m_status:
                    status = m_status.group(1).strip()
                m_date = re.search(r"\*\*Date:\*\*\s*([^|\r\n]+)", s)
                if m_date:
                    date = m_date.group(1).strip()
                m_lesson = re.search(r"\*\*Lesson:\*\*\s*([^|\r\n]+)", s)
                if m_lesson:
                    lesson = m_lesson.group(1).strip()
            elif s.startswith("## "):
                section = s[3:].strip().lower()
            elif section == "context" and s:
                context_lines.append(s)
            elif section == "insight" and s:
                insight_lines.append(s)
        records.append(
            {
                "file": f"learning-records/{p.name}",
                "title": title,
                "status": status,
                "date": date,
                "lesson": lesson,
                "context": " ".join(context_lines)[:300],
                "insight": " ".join(insight_lines)[:300],
            }
        )
    return records


def _extract_mission_metadata(session_dir: Path) -> dict[str, Any]:
    """Read optional operational mission/calibration baseline from scratchpad/mission.json or 00-MISSION.md."""
    mission_json = load_json_dict(session_dir / "scratchpad" / "mission.json")
    if mission_json:
        return mission_json

    mission_md = session_dir / "00-MISSION.md"
    if not mission_md.is_file():
        return {}
    text = read_text_safe(mission_md)
    info: dict[str, Any] = {}
    m_prior = re.search(r"\*\*Prior Knowledge Baseline:\*\*\s*(.+)", text)
    if m_prior:
        info["prior_knowledge"] = m_prior.group(1).strip()
    m_depth = re.search(r"\*\*Coverage & Depth Mode:\*\*\s*(.+)", text)
    if m_depth:
        info["depth_mode"] = m_depth.group(1).strip()
    m_lang = re.search(r"\*\*Language:\*\*\s*(.+)", text)
    if m_lang:
        info["language"] = m_lang.group(1).strip()
    return info


def _build_curriculum_node(item: dict[str, Any], next_id: str | None) -> tuple[str, dict[str, Any]]:
    slug = str(item["slug"]).strip()
    prefix = slug.split("-", 1)[0]
    num = prefix.zfill(2) if prefix.isdigit() else prefix
    node_id = str(item.get("id") or f"topic-{num}").strip()
    title = str(item.get("title") or slug).strip()
    deps = [str(x).strip() for x in item.get("depends_on", []) if str(x).strip()]
    contrasts = [str(x).strip() for x in item.get("contrasts_with", []) if str(x).strip()]
    unlocks = [str(x).strip() for x in item.get("unlocks", []) if str(x).strip()] or ([next_id] if next_id else [])
    fixes = [str(x).strip() for x in item.get("fixes_failure_of", []) if str(x).strip()]
    key_eqs = [str(x).strip() for x in item.get("key_equations", []) if str(x).strip()]
    key_concepts = [str(x).strip() for x in item.get("key_concepts", []) if str(x).strip()]

    node = {
        "id": node_id,
        "slug": slug,
        "title": title,
        "status": str(item.get("status") or "unstarted"),
        "checkpoint": str(item.get("checkpoint") or "0/4"),
        "depends_on": deps,
        "unlocks": unlocks,
        "contrasts_with": contrasts,
        "fixes_failure_of": fixes,
        "objective": str(item.get("objective") or ""),
        "anchor": str(item.get("anchor") or ""),
        "summary": str(item.get("summary") or ""),
        "key_concepts": key_concepts,
        "key_equations": key_eqs,
    }
    return node_id, node


def init_session_state(
    session_dir: Path,
    topic_title: str,
    items: list[dict[str, Any]],
    mode: str = "standalone",
    vault_root: Path | None = None,
) -> dict[str, Any]:
    """Create operational learning state only (never study-note scaffolds)."""
    (session_dir / "learning-records").mkdir(parents=True, exist_ok=True)
    (session_dir / "scratchpad").mkdir(parents=True, exist_ok=True)

    slugs = [str(it["slug"]).strip() for it in items if it.get("slug")]
    nums = [s.split("-", 1)[0].zfill(2) if s.split("-", 1)[0].isdigit() else s for s in slugs]
    first_id = f"topic-{nums[0]}" if nums else "topic-01"

    # Persist/merge curriculum.json without clobbering existing node mastery
    curriculum = load_curriculum(session_dir)
    if topic_title and not curriculum.get("topic"):
        curriculum["topic"] = topic_title
    cur_nodes = dict(curriculum.get("nodes", {}))
    cur_order = list(curriculum.get("order", []))

    existing_graph = load_json_dict(session_dir / "00-GRAPH.json") or {}
    g_nodes = dict(existing_graph.get("nodes", {}))
    g_order = list(existing_graph.get("order", []))

    created_nodes = 0
    for idx, item in enumerate(items):
        next_id = f"topic-{nums[idx + 1]}" if idx + 1 < len(nums) else None
        node_id, node_data = _build_curriculum_node(item, next_id)
        if node_id not in cur_nodes:
            cur_nodes[node_id] = node_data
            created_nodes += 1
        else:
            # Enrich curriculum metadata non-destructively while keeping progress fields
            merged = dict(node_data)
            merged["status"] = cur_nodes[node_id].get("status", merged["status"])
            merged["checkpoint"] = cur_nodes[node_id].get("checkpoint", merged["checkpoint"])
            cur_nodes[node_id] = merged
        if node_id not in cur_order:
            cur_order.append(node_id)

        if node_id not in g_nodes:
            g_nodes[node_id] = {
                "slug": node_data["slug"],
                "title": node_data["title"],
                "status": node_data["status"],
                "checkpoint": node_data["checkpoint"],
                "depends_on": node_data["depends_on"],
                "unlocks": node_data["unlocks"],
                "contrasts_with": node_data["contrasts_with"],
                "fixes_failure_of": node_data["fixes_failure_of"],
            }
        if node_id not in g_order:
            g_order.append(node_id)

    curriculum["nodes"] = cur_nodes
    curriculum["order"] = cur_order
    save_curriculum(session_dir, curriculum)

    # Persist scratchpad/subtopics.json for compatibility if absent
    subtopics_path = session_dir / "scratchpad" / "subtopics.json"
    if items and not subtopics_path.exists():
        atomic_write_text(subtopics_path, json.dumps(items, indent=2, ensure_ascii=False) + "\n")

    graph = {
        "schema_version": 2,
        "kind": "curriculum_dependency_graph",
        "topic": topic_title,
        "nodes": g_nodes,
        "order": g_order,
    }
    atomic_write_text(
        session_dir / "00-GRAPH.json",
        json.dumps(graph, indent=2, ensure_ascii=False) + "\n",
    )

    state_path = session_dir / "00-SESSION-STATE.md"
    if not state_path.exists():
        status_tokens = " ".join(f"`[ ] {n}`" for n in (nums or ["01"]))
        state_lines = [
            f"# Session State: {topic_title}",
            "",
            f"- **Vault Mode:** `{mode}`",
            f"- **Active Subtopic:** `{first_id}`",
            "- **Live Stage & Checkpoint:** `Depth Stage 1/3 | Checkpoint [1/4]`",
            "- **Last Verified Invariant:** Session initialized.",
        ]
        if vault_root is not None:
            state_lines.insert(3, f"- **Vault Root:** `{vault_root}`")
        state_lines.extend(
            [
                "",
                "## Compact Subtopic Status Map",
                status_tokens,
                "<!-- Legend: [x] mastered | [~] in-progress | [ ] unstarted -->",
            ]
        )
        atomic_write_text(state_path, "\n".join(state_lines[:59]) + "\n")
    elif nums:
        s_lines = read_text_safe(state_path).splitlines()
        out_s: list[str] = []
        for line in s_lines:
            if "`[ ] " in line or "`[x] " in line or "`[~] " in line:
                missing_nums = [
                    n for n in nums if not re.search(rf"`\[[ x~]\]\s*{re.escape(n)}`", line)
                ]
                if missing_nums:
                    line = line.rstrip() + " " + " ".join(f"`[ ] {n}`" for n in missing_nums)
            out_s.append(line)
        atomic_write_text(state_path, "\n".join(out_s[:59]) + "\n")

    return {
        "ok": True,
        "mode": mode,
        "session_dir": str(session_dir),
        "topics": len(cur_order),
        "nodes_created": created_nodes,
        "graph_nodes": len(g_nodes),
    }


def rebuild_curriculum_graph(session_dir: Path) -> dict[str, Any]:
    """Rebuild 00-GRAPH.json from internal curriculum/state data without modifying notes."""
    existing = load_json_dict(session_dir / "00-GRAPH.json") or {}
    nodes: dict[str, Any] = dict(existing.get("nodes", {}))
    order: list[str] = list(existing.get("order", []))

    curriculum = load_curriculum(session_dir)
    for nid in curriculum.get("order", []):
        cnode = curriculum.get("nodes", {}).get(nid)
        if not isinstance(cnode, dict):
            continue
        if nid not in nodes:
            nodes[nid] = {
                "slug": cnode.get("slug", nid),
                "title": cnode.get("title", nid),
                "status": cnode.get("status", "unstarted"),
                "checkpoint": cnode.get("checkpoint", "0/4"),
                "depends_on": list(cnode.get("depends_on", [])),
                "unlocks": list(cnode.get("unlocks", [])),
                "contrasts_with": list(cnode.get("contrasts_with", [])),
                "fixes_failure_of": list(cnode.get("fixes_failure_of", [])),
            }
        else:
            for edge in TYPED_EDGE_FIELDS:
                if edge not in nodes[nid]:
                    nodes[nid][edge] = list(cnode.get(edge, []))
        if nid not in order:
            order.append(nid)

    subtopics_path = session_dir / "scratchpad" / "subtopics.json"
    if subtopics_path.is_file():
        try:
            raw_items = json.loads(read_text_safe(subtopics_path))
            if isinstance(raw_items, list):
                for idx, item in enumerate(raw_items):
                    if not isinstance(item, dict) or not item.get("slug"):
                        continue
                    next_slug = raw_items[idx + 1]["slug"] if idx + 1 < len(raw_items) and isinstance(raw_items[idx + 1], dict) else None
                    next_num = str(next_slug).split("-", 1)[0].zfill(2) if next_slug and str(next_slug).split("-", 1)[0].isdigit() else None
                    next_id = f"topic-{next_num}" if next_num else None
                    nid, cnode = _build_curriculum_node(item, next_id)
                    if nid not in nodes:
                        nodes[nid] = {
                            "slug": cnode["slug"],
                            "title": cnode["title"],
                            "status": cnode["status"],
                            "checkpoint": cnode["checkpoint"],
                            "depends_on": cnode["depends_on"],
                            "unlocks": cnode["unlocks"],
                            "contrasts_with": cnode["contrasts_with"],
                            "fixes_failure_of": cnode["fixes_failure_of"],
                        }
                    if nid not in order:
                        order.append(nid)
        except (OSError, json.JSONDecodeError):
            pass

    graph = dict(existing)
    graph["kind"] = "curriculum_dependency_graph"
    graph["nodes"] = nodes
    graph["order"] = order
    atomic_write_text(
        session_dir / "00-GRAPH.json",
        json.dumps(graph, indent=2, ensure_ascii=False) + "\n",
    )
    return graph


def _detect_graph_cycle(nodes: dict[str, Any]) -> list[str] | None:
    state: dict[str, int] = {}
    path: list[str] = []

    def dfs(u: str) -> list[str] | None:
        state[u] = 1
        path.append(u)
        node = nodes.get(u, {})
        for dep in node.get("depends_on", []):
            if dep not in nodes:
                continue
            st = state.get(dep, 0)
            if st == 1:
                idx = path.index(dep)
                return path[idx:] + [dep]
            if st == 0:
                cyc = dfs(dep)
                if cyc:
                    return cyc
        path.pop()
        state[u] = 2
        return None

    for nid in nodes:
        if state.get(nid, 0) == 0:
            cyc = dfs(nid)
            if cyc:
                return cyc
    return None


def validate_session_state(session_dir: Path) -> dict[str, Any]:
    """Validate internal operational learning state (never modifies or audits study notes)."""
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []

    state_file = session_dir / "00-SESSION-STATE.md"
    if not state_file.is_file():
        errors.append({"file": "00-SESSION-STATE.md", "type": "missing_state_file", "detail": "00-SESSION-STATE.md missing"})
    else:
        lines = read_text_safe(state_file).splitlines()
        if len(lines) >= 60:
            errors.append({"file": "00-SESSION-STATE.md", "type": "state_too_long", "detail": f"Expected <60 lines, found {len(lines)}"})
        text = "\n".join(lines)
        if "**Active Subtopic:**" not in text:
            errors.append({"file": "00-SESSION-STATE.md", "type": "missing_field", "detail": "Missing Active Subtopic"})
        if "**Live Stage & Checkpoint:**" not in text:
            errors.append({"file": "00-SESSION-STATE.md", "type": "missing_field", "detail": "Missing Live Stage & Checkpoint"})

    graph_file = session_dir / "00-GRAPH.json"
    if not graph_file.is_file():
        errors.append({"file": "00-GRAPH.json", "type": "missing_graph_file", "detail": "00-GRAPH.json missing"})
    else:
        try:
            graph = json.loads(read_text_safe(graph_file))
            if not isinstance(graph, dict) or not isinstance(graph.get("nodes"), dict):
                errors.append({"file": "00-GRAPH.json", "type": "invalid_graph_schema", "detail": "Expected object with nodes dict"})
            else:
                nodes = graph["nodes"]
                for nid, node in nodes.items():
                    if not isinstance(node, dict):
                        errors.append({"file": "00-GRAPH.json", "type": "invalid_node", "detail": f"Node {nid} is not an object"})
                        continue
                    for edge_key in TYPED_EDGE_FIELDS:
                        for target in node.get(edge_key, []) or []:
                            if target not in nodes:
                                errors.append({"file": "00-GRAPH.json", "type": "broken_curriculum_edge", "detail": f"{nid}.{edge_key} -> missing {target}"})
                cyc = _detect_graph_cycle(nodes)
                if cyc:
                    errors.append({"file": "00-GRAPH.json", "type": "curriculum_cycle", "detail": f"Cycle detected: {' -> '.join(cyc)}"})
        except (OSError, json.JSONDecodeError) as exc:
            errors.append({"file": "00-GRAPH.json", "type": "invalid_json", "detail": str(exc)})

    events_file = session_dir / "scratchpad" / "events.jsonl"
    if events_file.is_file():
        for lineno, raw in enumerate(read_text_safe(events_file).splitlines(), start=1):
            if not raw.strip():
                continue
            try:
                obj = json.loads(raw)
                if not isinstance(obj, dict):
                    errors.append({"file": "scratchpad/events.jsonl", "line": lineno, "type": "invalid_event", "detail": "Line must be JSON object"})
            except json.JSONDecodeError as exc:
                errors.append({"file": "scratchpad/events.jsonl", "line": lineno, "type": "invalid_jsonl", "detail": str(exc)})

    curr_file = session_dir / "scratchpad" / "curriculum.json"
    if curr_file.is_file():
        try:
            curr = json.loads(read_text_safe(curr_file))
            if not isinstance(curr, dict) or not isinstance(curr.get("nodes"), dict):
                errors.append({"file": "scratchpad/curriculum.json", "type": "invalid_curriculum_schema", "detail": "Expected object with nodes dict"})
        except (OSError, json.JSONDecodeError) as exc:
            errors.append({"file": "scratchpad/curriculum.json", "type": "invalid_json", "detail": str(exc)})

    return {
        "ok": len(errors) == 0,
        "session_dir": str(session_dir),
        "errors": errors,
        "warnings": warnings,
    }


def _parse_topic_ledger(body: str) -> dict[str, bool]:
    ledger: dict[str, bool] = {}
    for line in body.splitlines():
        m = LEDGER_LINE_RE.match(line)
        if m:
            mark = m.group(1).lower() == "x"
            cp = f"{m.group(2)}/4"
            ledger[cp] = mark
    return ledger


def _parse_moc_checkboxes(moc_path: Path) -> dict[str, bool]:
    if not moc_path.is_file():
        return {}
    statuses: dict[str, bool] = {}
    for line in read_text_safe(moc_path).splitlines():
        m = re.match(r"^\s*-\s*\[([ xX])\]\s*.*\[\[(?:topics/)?([^\]|#]+)", line)
        if m:
            statuses[m.group(2).strip()] = m.group(1).lower() == "x"
    return statuses


def import_legacy_vault(
    source_vault: Path,
    target_dir: Path | None = None,
) -> dict[str, Any]:
    """Non-destructively and idempotently import legacy study-note-embedded memory into internal state.

    Original study notes (topics/*.md, 00-MOC-INDEX.md, 01..09, atomic/*.md) are
    never edited, reformatted, or deleted. Unknown YAML/JSON fields are preserved.
    """
    src = source_vault.resolve()
    if not src.is_dir():
        raise FileNotFoundError(f"Source legacy vault does not exist: {src}")

    dest = target_dir.resolve() if target_dir else src
    state_file = src / "00-SESSION-STATE.md"
    graph_file = src / "00-GRAPH.json"
    topics_dir = src / "topics"
    moc_file = src / "00-MOC-INDEX.md"

    has_legacy_signals = (
        state_file.is_file()
        or graph_file.is_file()
        or (topics_dir.is_dir() and any(topics_dir.glob("*.md")))
    )
    if not has_legacy_signals:
        raise ValueError(
            f"Unsupported or unrecognized vault format at {src}: expected 00-SESSION-STATE.md, 00-GRAPH.json, or topics/*.md"
        )

    existing_graph: dict[str, Any] = {}
    if graph_file.is_file():
        try:
            loaded_g = json.loads(read_text_safe(graph_file))
        except json.JSONDecodeError as exc:
            raise ValueError(f"Malformed 00-GRAPH.json in {src}: {exc}") from exc
        if not isinstance(loaded_g, dict) or not isinstance(loaded_g.get("nodes", {}), dict):
            raise ValueError(f"Unsupported 00-GRAPH.json schema in {src}: 'nodes' must be an object")
        sv = loaded_g.get("schema_version")
        if sv is not None and sv not in (1, 2):
            raise ValueError(f"Unsupported 00-GRAPH.json schema_version={sv!r} in {src}")
        existing_graph = loaded_g

    moc_checks = _parse_moc_checkboxes(moc_file)
    events = load_events(src)
    events_by_topic: dict[str, list[dict[str, Any]]] = {}
    for ev in events:
        tnum = normalize_topic_num(str(ev.get("topic", "")))
        if tnum:
            events_by_topic.setdefault(tnum, []).append(ev)

    lr_records = load_learning_records(src)
    curriculum_nodes: dict[str, Any] = {}
    graph_nodes: dict[str, Any] = {}
    order: list[str] = []

    raw_g_nodes = dict(existing_graph.get("nodes", {}))
    for gid in existing_graph.get("order", []):
        if isinstance(gid, str) and gid not in order:
            order.append(gid)

    topic_files = sorted(topics_dir.glob("*.md")) if topics_dir.is_dir() else []
    imported_sources: list[str] = []

    for tf in topic_files:
        raw_bytes = tf.read_bytes()
        if b"\x00" in raw_bytes:
            raise ValueError(f"Unsupported binary content in {tf}")
        text = raw_bytes.decode("utf-8-sig")
        parsed = parse_frontmatter_tolerant(text)
        if parsed["body_start_line"] == 0 or not parsed["valid"] or not isinstance(parsed["meta"], dict):
            raise ValueError(f"Unsupported or malformed YAML frontmatter in {tf}: {parsed['warnings']}")

        meta = parsed["meta"]
        prefix = tf.stem.split("-", 1)[0]
        num = prefix.zfill(2) if prefix.isdigit() else prefix
        node_id = str(meta.get("id") or f"topic-{num}").strip()
        if not node_id:
            raise ValueError(f"Missing node id in {tf}")

        ledger = _parse_topic_ledger(parsed["body"])
        g_existing = raw_g_nodes.get(node_id, {}) if isinstance(raw_g_nodes.get(node_id), dict) else {}

        status = str(meta.get("status") or g_existing.get("status") or ("mastered" if moc_checks.get(tf.stem) else "unstarted"))
        checkpoint = str(meta.get("checkpoint") or g_existing.get("checkpoint") or "0/4")
        if status == "mastered" and checkpoint == "0/4":
            checkpoint = "4/4"

        t_events = events_by_topic.get(num, [])
        last_ts = t_events[-1].get("ts") if t_events else ""
        unknown_fm = {
            k: v for k, v in meta.items() if k not in KNOWN_FRONTMATTER_KEYS
        }
        unknown_graph = {
            k: v for k, v in g_existing.items() if k not in KNOWN_GRAPH_NODE_KEYS
        }
        preserved_extra = {}
        if isinstance(g_existing.get("extra_metadata"), dict):
            preserved_extra.update(g_existing["extra_metadata"])
        preserved_extra.update(unknown_graph)
        preserved_extra.update(unknown_fm)

        deps = meta.get("depends_on") if "depends_on" in meta else g_existing.get("depends_on", [])
        unlocks = meta.get("unlocks") if "unlocks" in meta else g_existing.get("unlocks", [])
        contrasts = meta.get("contrasts_with") if "contrasts_with" in meta else g_existing.get("contrasts_with", [])
        fixes = meta.get("fixes_failure_of") if "fixes_failure_of" in meta else g_existing.get("fixes_failure_of", [])
        key_eqs = meta.get("key_equations") if "key_equations" in meta else g_existing.get("key_equations", [])

        def _as_list(val: Any) -> list[str]:
            if isinstance(val, list):
                return [str(x).strip() for x in val if str(x).strip()]
            if isinstance(val, str) and val.strip():
                return [val.strip()]
            return []

        node_entry: dict[str, Any] = {
            "id": node_id,
            "slug": tf.stem,
            "source_id": str(meta.get("id") or node_id),
            "source_file": f"topics/{tf.name}",
            "title": str(meta.get("title") or meta.get("subtopic") or g_existing.get("title") or tf.stem),
            "status": status,
            "checkpoint": checkpoint,
            "depends_on": _as_list(deps),
            "unlocks": _as_list(unlocks),
            "contrasts_with": _as_list(contrasts),
            "fixes_failure_of": _as_list(fixes),
            "key_equations": _as_list(key_eqs),
            "checkpoints_passed": ledger,
            "evidence": [
                {
                    "ts": ev.get("ts", ""),
                    "cp": ev.get("cp"),
                    "status": ev.get("status"),
                    "note": ev.get("note", ""),
                }
                for ev in t_events[-10:]
            ],
            "last_event_ts": last_ts,
        }
        if g_existing.get("last_invariant"):
            node_entry["last_invariant"] = g_existing["last_invariant"]
        if g_existing.get("mastered_at"):
            node_entry["mastered_at"] = g_existing["mastered_at"]
        if preserved_extra:
            node_entry["extra_metadata"] = preserved_extra

        curriculum_nodes[node_id] = dict(node_entry)
        graph_nodes[node_id] = {
            k: v for k, v in node_entry.items()
            if k in {
                "slug", "source_id", "source_file", "title", "status", "checkpoint",
                "depends_on", "unlocks", "contrasts_with", "fixes_failure_of",
                "checkpoints_passed", "evidence", "last_event_ts", "last_invariant",
                "mastered_at", "extra_metadata",
            }
        }
        if node_id not in order:
            order.append(node_id)
        imported_sources.append(f"topics/{tf.name}")

    # Preserve graph-only nodes when topics/*.md didn't exist for them
    for gid, gval in raw_g_nodes.items():
        if gid in graph_nodes or not isinstance(gval, dict):
            continue
        graph_nodes[gid] = dict(gval)
        curriculum_nodes[gid] = dict(gval)
        curriculum_nodes[gid].setdefault("id", gid)
        if gid not in order:
            order.append(gid)

    # Preserve unknown top-level keys in 00-GRAPH.json
    extra_graph_top = {
        k: v for k, v in existing_graph.items()
        if k not in {"schema_version", "kind", "topic", "nodes", "order", "extra_top_fields"}
    }
    if isinstance(existing_graph.get("extra_top_fields"), dict):
        merged_top = dict(existing_graph["extra_top_fields"])
        merged_top.update(extra_graph_top)
        extra_graph_top = merged_top

    # Copy operational files cleanly if migrating to a separate target dir
    (dest / "scratchpad").mkdir(parents=True, exist_ok=True)
    (dest / "learning-records").mkdir(parents=True, exist_ok=True)
    if dest != src:
        if state_file.is_file():
            atomic_write_text(dest / "00-SESSION-STATE.md", read_text_safe(state_file))
        events_src = src / "scratchpad" / "events.jsonl"
        if events_src.is_file():
            atomic_write_text(dest / "scratchpad" / "events.jsonl", read_text_safe(events_src))
        for qf in sorted((src / "scratchpad").glob("queue-*.json")) if (src / "scratchpad").is_dir() else []:
            atomic_write_text(dest / "scratchpad" / qf.name, read_text_safe(qf))
        for lrf in sorted((src / "learning-records").glob("*.md")) if (src / "learning-records").is_dir() else []:
            atomic_write_text(dest / "learning-records" / lrf.name, read_text_safe(lrf))
        mission_src = src / "00-MISSION.md"
        if mission_src.is_file():
            atomic_write_text(dest / "00-MISSION.md", read_text_safe(mission_src))

    # Build deterministic, idempotent operational files in dest
    new_graph: dict[str, Any] = {
        "schema_version": 2,
        "kind": "curriculum_dependency_graph",
        "topic": existing_graph.get("topic") or src.name,
        "nodes": graph_nodes,
        "order": order,
    }
    if extra_graph_top:
        new_graph["extra_top_fields"] = extra_graph_top
    atomic_write_text(dest / "00-GRAPH.json", json.dumps(new_graph, indent=2, ensure_ascii=False) + "\n")

    new_curr = {
        "schema_version": 1,
        "topic": existing_graph.get("topic") or src.name,
        "nodes": curriculum_nodes,
        "order": order,
        "learning_records": [r["file"] for r in lr_records],
    }
    save_curriculum(dest, new_curr)

    resume_state = ""
    if state_file.is_file():
        resume_state = read_text_safe(state_file)
    elif order:
        first_node = graph_nodes[order[0]]
        status_tokens = " ".join(
            f"`[{'x' if graph_nodes[nid].get('status') == 'mastered' else ('~' if graph_nodes[nid].get('checkpoint', '0/4') != '0/4' else ' ')}] {nid.replace('topic-', '')}`"
            for nid in order
        )
        resume_lines = [
            f"# Session State: {new_graph['topic']}",
            "",
            f"- **Active Subtopic:** `{order[0]}`",
            f"- **Live Stage & Checkpoint:** `Depth Stage 1/3 | Checkpoint [{first_node.get('checkpoint', '1/4')}]`",
            f"- **Last Verified Invariant:** {first_node.get('last_invariant', 'Imported from legacy vault.')}",
            "",
            "## Compact Subtopic Status Map",
            status_tokens,
            "<!-- Legend: [x] mastered | [~] in-progress | [ ] unstarted -->",
        ]
        atomic_write_text(dest / "00-SESSION-STATE.md", "\n".join(resume_lines) + "\n")
        resume_state = "synthesized"

    import_manifest = {
        "schema_version": LEGACY_IMPORT_SCHEMA_VERSION,
        "source_vault": str(src),
        "target_state_dir": str(dest),
        "imported_topic_files": imported_sources,
        "nodes_imported": len(graph_nodes),
        "events_imported": len(events),
        "learning_records_count": len(lr_records),
        "source_notes_modified": False,
        "has_session_state": bool(resume_state or state_file.is_file()),
    }
    atomic_write_text(
        dest / "scratchpad" / "legacy-import.json",
        json.dumps(import_manifest, indent=2, ensure_ascii=False) + "\n",
    )
    return {
        "ok": True,
        **import_manifest,
    }


def build_handoff_envelope(
    session_dir: Path | None,
    requested_artifact: str,
    topic: str = "",
    topic_num: str | None = None,
    requested_scope: str = "",
    request_id: str | None = None,
    destination_constraints: str = "",
    examples_used: list[str] | None = None,
    persist: bool = False,
) -> dict[str, Any]:
    """Build a compact, versioned, evidence-backed teaching-context envelope for Scriptorium."""
    req_id = (request_id or "").strip() or f"tm-handoff-{uuid.uuid4().hex[:12]}"
    now_iso = utc_now_iso()

    if session_dir is None or not session_dir.is_dir():
        envelope = {
            "schema_version": HANDOFF_SCHEMA_VERSION,
            "request_id": req_id,
            "requested_artifact": requested_artifact or "unknown",
            "requested_scope": requested_scope or "unknown",
            "topic": topic or "unknown",
            "curriculum_ids": [],
            "session_id": "unknown",
            "resume_checkpoint": "unknown",
            "concepts_taught": [],
            "concepts_planned": [],
            "unresolved_topics": [],
            "mastery_claims": [],
            "weak_spots_and_misconceptions": [],
            "examples_analogies_used": list(examples_used or []),
            "learner_profile": {
                "level": "unknown",
                "language": "unknown",
                "known_preferences": [],
            },
            "source_provenance": [],
            "destination_constraints": destination_constraints or "unknown",
            "state_provenance": {
                "state_dir": "none",
                "timestamp": now_iso,
                "source": "ephemeral_no_session",
            },
            "missing_fields": [
                "session_id",
                "curriculum_ids",
                "resume_checkpoint",
                "mastery_claims",
                "learner_profile",
            ],
        }
        return envelope

    graph = load_json_dict(session_dir / "00-GRAPH.json") or {"nodes": {}, "order": []}
    curriculum = load_curriculum(session_dir)
    nodes = graph.get("nodes", {})
    c_nodes = curriculum.get("nodes", {})
    order = graph.get("order") or list(nodes.keys())

    state_file = session_dir / "00-SESSION-STATE.md"
    state_text = read_text_safe(state_file) if state_file.is_file() else ""
    m_active = re.search(r"^\s*-\s*\*\*Active Subtopic:\*\*\s*`?([^`\r\n]+?)`?\s*$", state_text, re.M)
    m_stage_cp = re.search(r"^\s*-\s*\*\*Live Stage & Checkpoint:\*\*\s*`?([^`\r\n]+?)`?\s*$", state_text, re.M)

    target_nid = f"topic-{normalize_topic_num(topic_num)}" if topic_num else None
    selected_ids = [target_nid] if target_nid and target_nid in nodes else list(order)

    events = load_events(session_dir)
    events_by_nid: dict[str, list[dict[str, Any]]] = {}
    for ev in events:
        t = normalize_topic_num(str(ev.get("topic", "")))
        if t:
            events_by_nid.setdefault(f"topic-{t}", []).append(ev)

    concepts_taught: list[dict[str, Any]] = []
    concepts_planned: list[dict[str, Any]] = []
    unresolved_topics: list[dict[str, Any]] = []
    mastery_claims: list[dict[str, Any]] = []

    for nid in selected_ids:
        gnode = nodes.get(nid, {})
        cnode = c_nodes.get(nid, {})
        title = str(gnode.get("title") or cnode.get("title") or nid)
        status = str(gnode.get("status") or "unstarted")
        cp = str(gnode.get("checkpoint") or "0/4")
        nid_events = events_by_nid.get(nid, [])

        item_ref: dict[str, Any] = {"id": nid, "title": title}
        key_eqs = cnode.get("key_equations") or gnode.get("key_equations") or []
        if key_eqs:
            item_ref["key_equations"] = key_eqs[:4]

        has_pass_or_progress = status == "mastered" or cp != "0/4" or any(
            ev.get("status") == "pass" for ev in nid_events
        )
        if status == "mastered":
            concepts_taught.append(item_ref)
            evidence_bits = []
            if gnode.get("last_invariant"):
                evidence_bits.append(f"invariant: {gnode['last_invariant']}")
            if nid_events:
                last_ev = nid_events[-1]
                evidence_bits.append(f"event cp {last_ev.get('cp')}/4 {last_ev.get('status')} at {last_ev.get('ts', '')}")
            mastery_claims.append(
                {
                    "id": nid,
                    "title": title,
                    "assessed_status": "mastered",
                    "checkpoint": cp,
                    "evidence": "; ".join(evidence_bits) if evidence_bits else "checkpoint 4/4 flushed",
                }
            )
        elif has_pass_or_progress:
            concepts_taught.append(item_ref)
            unresolved_topics.append(item_ref)
            passed_cps = [f"{ev.get('cp')}/4" for ev in nid_events if ev.get("status") == "pass"]
            mastery_claims.append(
                {
                    "id": nid,
                    "title": title,
                    "assessed_status": "in_progress",
                    "checkpoint": cp,
                    "evidence": f"passed checkpoints {passed_cps}" if passed_cps else f"checkpoint {cp}",
                }
            )
        else:
            concepts_planned.append(item_ref)
            unresolved_topics.append(item_ref)
            mastery_claims.append(
                {
                    "id": nid,
                    "title": title,
                    "assessed_status": "unknown",
                    "checkpoint": "0/4",
                    "evidence": "unassessed",
                }
            )

    weak_spots: list[dict[str, Any]] = []
    for ev in events:
        if ev.get("status") == "retry":
            weak_spots.append(
                {
                    "topic": f"topic-{normalize_topic_num(str(ev.get('topic', '')))}",
                    "checkpoint": f"{ev.get('cp', '?')}/4",
                    "note": str(ev.get("note") or "retry recorded"),
                    "ts": ev.get("ts", ""),
                }
            )

    lr_records = load_learning_records(session_dir)
    for rec in lr_records:
        if rec.get("status", "").startswith("superseded"):
            continue
        weak_spots.append(
            {
                "record": rec["file"],
                "title": rec["title"],
                "insight": rec["insight"] or rec["context"],
            }
        )

    ingested = load_json_dict(session_dir / "scratchpad" / "ingested-sources.json") or {}
    sources: list[dict[str, Any]] = []
    for src_item in ingested.get("sources", []) if isinstance(ingested.get("sources"), list) else []:
        if isinstance(src_item, dict):
            entry = {k: v for k, v in src_item.items() if k in {"title", "url", "type", "retrieved_at"}}
            if entry:
                sources.append(entry)

    mission = _extract_mission_metadata(session_dir)
    learner_profile = {
        "level": str(mission.get("prior_knowledge") or "unknown"),
        "language": str(mission.get("language") or "unknown"),
        "known_preferences": [mission["depth_mode"]] if mission.get("depth_mode") else [],
    }

    missing_fields: list[str] = []
    if learner_profile["level"] == "unknown":
        missing_fields.append("learner_profile.level")
    if learner_profile["language"] == "unknown":
        missing_fields.append("learner_profile.language")
    if not sources:
        missing_fields.append("source_provenance")
    if not destination_constraints:
        missing_fields.append("destination_constraints")

    resolved_topic = topic or str(graph.get("topic") or curriculum.get("topic") or session_dir.name)
    resume_cp = m_stage_cp.group(1).strip() if m_stage_cp else "unknown"
    if m_active:
        resume_cp = f"{m_active.group(1).strip()} | {resume_cp}"

    envelope = redact_sensitive(
        {
            "schema_version": HANDOFF_SCHEMA_VERSION,
            "request_id": req_id,
            "requested_artifact": requested_artifact or "study_notes",
            "requested_scope": requested_scope or ("subtopic" if target_nid else "topic"),
            "topic": resolved_topic,
            "curriculum_ids": selected_ids,
            "session_id": session_dir.name,
            "resume_checkpoint": resume_cp,
            "concepts_taught": concepts_taught,
            "concepts_planned": concepts_planned,
            "unresolved_topics": unresolved_topics,
            "mastery_claims": mastery_claims,
            "weak_spots_and_misconceptions": weak_spots[-12:],
            "examples_analogies_used": list(examples_used or []),
            "learner_profile": learner_profile,
            "source_provenance": sources[:10],
            "destination_constraints": destination_constraints or "unknown",
            "state_provenance": {
                "state_dir": str(session_dir),
                "timestamp": now_iso,
                "source": "teachme_operational_state",
            },
            "missing_fields": missing_fields,
        }
    )

    if persist:
        handoff_dir = session_dir / "scratchpad" / "handoffs"
        handoff_dir.mkdir(parents=True, exist_ok=True)
        out_file = handoff_dir / f"{req_id}.json"
        atomic_write_text(out_file, json.dumps(envelope, indent=2, ensure_ascii=False) + "\n")
        envelope["persisted_envelope_path"] = str(out_file)

    return envelope
