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

from .evidence import (
    CURRICULUM_SCHEMA_VERSION,
    derive_objective_evidence,
    derive_session_coverage_and_gaps,
    load_media_provenance,
    normalize_event,
    normalize_objectives_list,
    normalize_prerequisite_state,
)
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
from .scheduler import (
    load_review_state,
    save_review_state,
    sync_review_item_for_legacy_node,
)

HANDOFF_SCHEMA_VERSION = "1.1"
LEGACY_IMPORT_SCHEMA_VERSION = 2
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
    """Load scratchpad/curriculum.json if present, falling back read-only to 00-GRAPH.json."""
    data = load_json_dict(session_dir / "scratchpad" / "curriculum.json")
    if data and isinstance(data.get("nodes"), dict):
        return data
    graph = load_json_dict(session_dir / "00-GRAPH.json")
    if graph and isinstance(graph.get("nodes"), dict):
        return {
            "schema_version": int(graph.get("schema_version") or 1),
            "topic": str(graph.get("topic") or ""),
            "nodes": dict(graph["nodes"]),
            "order": list(graph.get("order") or graph["nodes"].keys()),
        }
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


def load_mission(session_dir: Path) -> dict[str, Any]:
    """Load scratchpad/mission.json or synthesize from 00-MISSION.md without fabricating missing fields."""
    data = _extract_mission_metadata(session_dir)
    if not isinstance(data, dict):
        data = {}
    return data


def save_mission(
    session_dir: Path,
    updates: dict[str, Any] | None = None,
    prerequisite_updates: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Merge calibration and prerequisite states into scratchpad/mission.json atomically."""
    current = load_mission(session_dir)
    current.setdefault("schema_version", 2)
    if updates:
        for key, val in updates.items():
            if val is not None:
                current[key] = val
    prereqs = dict(current.get("prerequisites") or {})
    if prerequisite_updates:
        now_iso = utc_now_iso()
        for pid, info in prerequisite_updates.items():
            clean_id = str(pid).strip()
            if not clean_id:
                continue
            state = normalize_prerequisite_state(info.get("state"))
            prev = dict(prereqs.get(clean_id) or {})
            prev["state"] = state
            if info.get("evidence") is not None:
                prev["evidence"] = str(info["evidence"])
            prev["updated_at"] = str(info.get("updated_at") or now_iso)
            prereqs[clean_id] = prev
    if prereqs:
        current["prerequisites"] = prereqs
    out = session_dir / "scratchpad" / "mission.json"
    atomic_write_text(out, json.dumps(current, indent=2, ensure_ascii=False) + "\n")
    return current


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
    in_scope = bool(item.get("in_scope", True))
    required = bool(item.get("required", True)) if in_scope else False

    node: dict[str, Any] = {
        "id": node_id,
        "slug": slug,
        "title": title,
        "status": str(item.get("status") or "unstarted"),
        "checkpoint": str(item.get("checkpoint") or "0/4"),
        "required": required,
        "in_scope": in_scope,
        "depends_on": deps,
        "unlocks": unlocks,
        "contrasts_with": contrasts,
        "fixes_failure_of": fixes,
        "objective": str(item.get("objective") or ""),
        "anchor": str(item.get("anchor") or ""),
        "summary": str(item.get("summary") or ""),
        "key_concepts": key_concepts,
        "key_equations": key_eqs,
        "assumptions": [str(x).strip() for x in item.get("assumptions", []) if str(x).strip()],
        "expected_assessments": [str(x).strip() for x in item.get("expected_assessments", []) if str(x).strip()],
    }
    if isinstance(item.get("objectives"), list) and item["objectives"]:
        node["objectives"] = item["objectives"]
    node["objectives"] = normalize_objectives_list(node_id, node)
    return node_id, node


def init_session_state(
    session_dir: Path,
    topic_title: str,
    items: list[dict[str, Any]],
    mode: str = "standalone",
    vault_root: Path | None = None,
    scope_info: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Create operational learning state only (never study-note scaffolds)."""
    (session_dir / "learning-records").mkdir(parents=True, exist_ok=True)
    (session_dir / "scratchpad").mkdir(parents=True, exist_ok=True)

    slugs = [str(it["slug"]).strip() for it in items if it.get("slug")]
    nums = [s.split("-", 1)[0].zfill(2) if s.split("-", 1)[0].isdigit() else s for s in slugs]
    first_id = f"topic-{nums[0]}" if nums else "topic-01"

    # Persist/merge curriculum.json without clobbering existing node mastery or objective evidence
    curriculum = load_curriculum(session_dir)
    curriculum["schema_version"] = CURRICULUM_SCHEMA_VERSION
    if topic_title and not curriculum.get("topic"):
        curriculum["topic"] = topic_title
    if scope_info:
        cur_scope = dict(curriculum.get("scope") or {})
        cur_scope.update({k: v for k, v in scope_info.items() if v is not None})
        curriculum["scope"] = cur_scope
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
            # Enrich curriculum metadata non-destructively while keeping progress & objective evidence
            prev = cur_nodes[node_id]
            merged = dict(node_data)
            merged["status"] = prev.get("status", merged["status"])
            merged["checkpoint"] = prev.get("checkpoint", merged["checkpoint"])
            if "last_invariant" in prev:
                merged["last_invariant"] = prev["last_invariant"]
            if "mastered_at" in prev:
                merged["mastered_at"] = prev["mastered_at"]
            prev_objs = {o["id"]: o for o in normalize_objectives_list(node_id, prev)}
            merged_objs = []
            for obj in node_data["objectives"]:
                if obj["id"] in prev_objs:
                    old_o = prev_objs[obj["id"]]
                    kept = dict(obj)
                    kept["coverage_status"] = old_o.get("coverage_status", obj["coverage_status"])
                    kept["proficiency"] = old_o.get("proficiency", obj["proficiency"])
                    kept["evidence_summary"] = old_o.get("evidence_summary", obj["evidence_summary"])
                    kept["unresolved_gaps"] = old_o.get("unresolved_gaps", obj["unresolved_gaps"])
                    merged_objs.append(kept)
                else:
                    merged_objs.append(obj)
            merged["objectives"] = merged_objs
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


def _validate_curriculum_references_and_cycles(curriculum: dict[str, Any]) -> list[dict[str, Any]]:
    """Validate objective IDs, prerequisite_refs, and combined dependency acyclicity."""
    errors: list[dict[str, Any]] = []
    nodes = curriculum.get("nodes", {})
    if not isinstance(nodes, dict):
        return [{"file": "scratchpad/curriculum.json", "type": "invalid_curriculum_schema", "detail": "Expected nodes dict"}]

    all_topic_ids = set(nodes.keys())
    seen_obj_ids: set[str] = set()
    combined_adj: dict[str, list[str]] = {nid: list(n.get("depends_on", []) or []) for nid, n in nodes.items() if isinstance(n, dict)}

    for nid, node in nodes.items():
        if not isinstance(node, dict):
            continue
        for edge_key in TYPED_EDGE_FIELDS:
            for target in node.get(edge_key, []) or []:
                if target not in all_topic_ids:
                    errors.append(
                        {
                            "file": "scratchpad/curriculum.json",
                            "type": "broken_curriculum_edge",
                            "detail": f"{nid}.{edge_key} -> missing {target}",
                        }
                    )
        raw_objs = node.get("objectives")
        if isinstance(raw_objs, list):
            for obj in raw_objs:
                if not isinstance(obj, dict):
                    continue
                oid = str(obj.get("id") or "").strip()
                if not oid:
                    errors.append(
                        {
                            "file": "scratchpad/curriculum.json",
                            "type": "missing_objective_id",
                            "detail": f"Node {nid} contains an objective without an id",
                        }
                    )
                    continue
                if oid in seen_obj_ids:
                    errors.append(
                        {
                            "file": "scratchpad/curriculum.json",
                            "type": "duplicate_objective_id",
                            "detail": f"Duplicate objective id {oid}",
                        }
                    )
                seen_obj_ids.add(oid)
                combined_adj[oid] = list(obj.get("prerequisite_refs") or [])

    valid_targets = all_topic_ids | seen_obj_ids
    for nid, node in nodes.items():
        if not isinstance(node, dict):
            continue
        raw_objs = node.get("objectives")
        if not isinstance(raw_objs, list):
            continue
        for obj in raw_objs:
            if not isinstance(obj, dict):
                continue
            oid = str(obj.get("id") or "").strip()
            for pref in obj.get("prerequisite_refs") or []:
                if pref not in valid_targets:
                    errors.append(
                        {
                            "file": "scratchpad/curriculum.json",
                            "type": "broken_objective_reference",
                            "detail": f"{oid}.prerequisite_refs -> missing {pref}",
                        }
                    )

    # Check combined graph acyclicity
    state: dict[str, int] = {}
    path: list[str] = []

    def dfs(u: str) -> list[str] | None:
        state[u] = 1
        path.append(u)
        for dep in combined_adj.get(u, []):
            if dep not in combined_adj:
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

    for key in combined_adj:
        if state.get(key, 0) == 0:
            cyc = dfs(key)
            if cyc:
                errors.append(
                    {
                        "file": "scratchpad/curriculum.json",
                        "type": "curriculum_cycle",
                        "detail": f"Cycle detected: {' -> '.join(cyc)}",
                    }
                )
                break
    return errors


def backup_state_files(session_dir: Path, label: str = "migration") -> Path | None:
    """Create a timestamped backup of existing operational state files before rewriting."""
    candidates = [
        session_dir / "00-SESSION-STATE.md",
        session_dir / "00-GRAPH.json",
        session_dir / "scratchpad" / "curriculum.json",
        session_dir / "scratchpad" / "review-state.json",
    ]
    existing = [p for p in candidates if p.is_file()]
    if not existing:
        return None
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    bdir = session_dir / "scratchpad" / "backups" / f"{label}-{stamp}"
    bdir.mkdir(parents=True, exist_ok=True)
    for src in existing:
        rel_name = src.name if src.parent == session_dir else f"scratchpad__{src.name}"
        atomic_write_text(bdir / rel_name, read_text_safe(src))
    return bdir


def revise_curriculum(
    session_dir: Path,
    *,
    node_id: str | None = None,
    slug: str | None = None,
    title: str | None = None,
    objective_desc: str | None = None,
    depends_on: list[str] | None = None,
    unlocks: list[str] | None = None,
    before_topic: str | None = None,
    required: bool | None = None,
    in_scope: bool | None = None,
    target_topic: str | None = None,
    objective_id: str | None = None,
    prerequisite_refs: list[str] | None = None,
    assumptions: list[str] | None = None,
    expected_assessments: list[str] | None = None,
) -> dict[str, Any]:
    """Revise curriculum (add prerequisite node or add/update objective) preserving IDs, evidence, and resume state.

    Validates DAG acyclicity and all references before writing anything.
    """
    curriculum = load_curriculum(session_dir)
    curriculum["schema_version"] = CURRICULUM_SCHEMA_VERSION
    nodes = dict(curriculum.get("nodes", {}))
    order = list(curriculum.get("order", []))

    graph_path = session_dir / "00-GRAPH.json"
    graph = load_json_dict(graph_path) or {"schema_version": 2, "kind": "curriculum_dependency_graph", "nodes": {}, "order": []}
    g_nodes = dict(graph.get("nodes", {}))
    g_order = list(graph.get("order", []))

    # Normalize existing nodes' objectives without erasing evidence
    for nid_k, nval in list(nodes.items()):
        if isinstance(nval, dict):
            nval = dict(nval)
            nval["objectives"] = normalize_objectives_list(nid_k, nval)
            nodes[nid_k] = nval

    action = ""
    if node_id or slug:
        clean_slug = (slug or node_id or "").strip()
        prefix = clean_slug.split("-", 1)[0]
        num = prefix.zfill(2) if prefix.isdigit() else prefix
        nid = (node_id or f"topic-{num}").strip()
        if not nid.startswith("topic-"):
            nid = f"topic-{normalize_topic_num(nid)}"
        if nid in nodes:
            raise ValueError(f"Topic node {nid} already exists; use --target-topic/--objective-id to update objectives")

        item = {
            "id": nid,
            "slug": clean_slug,
            "title": (title or clean_slug).strip(),
            "depends_on": list(depends_on or []),
            "unlocks": list(unlocks or []),
            "objective": (objective_desc or title or clean_slug).strip(),
            "required": True if required is None else bool(required),
            "in_scope": True if in_scope is None else bool(in_scope),
            "assumptions": list(assumptions or []),
            "expected_assessments": list(expected_assessments or []),
        }
        _, built = _build_curriculum_node(item, None)
        if prerequisite_refs and built["objectives"]:
            built["objectives"][0]["prerequisite_refs"] = list(prerequisite_refs)
        nodes[nid] = built

        # Wire unlocks -> target depends_on automatically if requested
        for target in built["unlocks"]:
            if target in nodes:
                t_deps = list(nodes[target].get("depends_on", []))
                if nid not in t_deps:
                    t_deps.append(nid)
                    nodes[target]["depends_on"] = t_deps
            if target in g_nodes:
                gt_deps = list(g_nodes[target].get("depends_on", []))
                if nid not in gt_deps:
                    gt_deps.append(nid)
                    g_nodes[target]["depends_on"] = gt_deps

        if before_topic:
            bt_id = f"topic-{normalize_topic_num(before_topic)}"
            if bt_id in order:
                idx = order.index(bt_id)
                order.insert(idx, nid)
            else:
                order.append(nid)
            if bt_id in g_order:
                g_idx = g_order.index(bt_id)
                g_order.insert(g_idx, nid)
            else:
                g_order.append(nid)
        else:
            order.append(nid)
            g_order.append(nid)

        g_nodes[nid] = {
            "slug": built["slug"],
            "title": built["title"],
            "status": built["status"],
            "checkpoint": built["checkpoint"],
            "depends_on": built["depends_on"],
            "unlocks": built["unlocks"],
            "contrasts_with": built["contrasts_with"],
            "fixes_failure_of": built["fixes_failure_of"],
        }
        action = f"added_node:{nid}"
    elif target_topic:
        t_nid = f"topic-{normalize_topic_num(target_topic)}"
        if t_nid not in nodes:
            raise ValueError(f"Target topic {t_nid} not found")
        tnode = dict(nodes[t_nid])
        objs = normalize_objectives_list(t_nid, tnode)
        oid = (objective_id or f"obj-{t_nid.replace('topic-', '')}-{len(objs) + 1:02d}").strip()
        existing_idx = next((i for i, o in enumerate(objs) if o["id"] == oid), None)
        if existing_idx is not None:
            cur_obj = dict(objs[existing_idx])
            if objective_desc is not None:
                cur_obj["description"] = objective_desc
            if required is not None:
                cur_obj["required"] = bool(required)
            if in_scope is not None:
                cur_obj["in_scope"] = bool(in_scope)
                if not in_scope:
                    cur_obj["coverage_status"] = "out_of_scope"
                    cur_obj["required"] = False
            if prerequisite_refs is not None:
                cur_obj["prerequisite_refs"] = list(prerequisite_refs)
            if assumptions is not None:
                cur_obj["assumptions"] = list(assumptions)
            if expected_assessments is not None:
                cur_obj["expected_assessments"] = list(expected_assessments)
            objs[existing_idx] = cur_obj
            action = f"updated_objective:{oid}"
        else:
            new_obj = {
                "id": oid,
                "description": (objective_desc or oid).strip(),
                "required": True if required is None else bool(required),
                "in_scope": True if in_scope is None else bool(in_scope),
                "prerequisite_refs": list(prerequisite_refs or []),
                "assumptions": list(assumptions or []),
                "expected_assessments": list(expected_assessments or []),
                "coverage_status": "out_of_scope" if in_scope is False else "not_taught",
            }
            objs.append(new_obj)
            tnode["objectives"] = objs
            objs = normalize_objectives_list(t_nid, tnode)
            action = f"added_objective:{oid}"
        tnode["objectives"] = objs
        if depends_on:
            cur_deps = list(tnode.get("depends_on", []))
            for d in depends_on:
                if d not in cur_deps:
                    cur_deps.append(d)
            tnode["depends_on"] = cur_deps
            if t_nid in g_nodes:
                g_nodes[t_nid]["depends_on"] = list(cur_deps)
        nodes[t_nid] = tnode
    else:
        raise ValueError("Provide either --slug/--node-id for a new node or --target-topic for an objective update")

    candidate_curr = dict(curriculum)
    candidate_curr["nodes"] = nodes
    candidate_curr["order"] = order

    # Validate before persisting!
    validation_errors = _validate_curriculum_references_and_cycles(candidate_curr)
    g_cyc = _detect_graph_cycle(g_nodes)
    if g_cyc:
        validation_errors.append({"file": "00-GRAPH.json", "type": "curriculum_cycle", "detail": f"Cycle: {' -> '.join(g_cyc)}"})
    if validation_errors:
        raise ValueError(f"Invalid curriculum revision: {validation_errors[0]['detail']}")

    save_curriculum(session_dir, candidate_curr)
    graph["nodes"] = g_nodes
    graph["order"] = g_order
    atomic_write_text(graph_path, json.dumps(graph, indent=2, ensure_ascii=False) + "\n")

    # Preserve resume position in 00-SESSION-STATE.md; only insert new status map token if a node was added
    state_file = session_dir / "00-SESSION-STATE.md"
    if action.startswith("added_node:") and state_file.is_file():
        added_nid = action.split(":", 1)[1]
        added_num = added_nid.replace("topic-", "")
        s_lines = read_text_safe(state_file).splitlines()
        out_s: list[str] = []
        for line in s_lines:
            if ("`[ ] " in line or "`[x] " in line or "`[~] " in line) and not re.search(rf"`\[[ x~]\]\s*{re.escape(added_num)}`", line):
                if before_topic:
                    bt_num = normalize_topic_num(before_topic)
                    pat = re.compile(rf"(`\[[ x~]\]\s*{re.escape(bt_num)}`)")
                    if pat.search(line):
                        line = pat.sub(rf"`[ ] {added_num}` \1", line, count=1)
                    else:
                        line = line.rstrip() + f" `[ ] {added_num}`"
                else:
                    line = line.rstrip() + f" `[ ] {added_num}`"
            out_s.append(line)
        atomic_write_text(state_file, "\n".join(out_s[:59]) + "\n")

    return {
        "ok": True,
        "action": action,
        "topics": len(order),
        "session_dir": str(session_dir),
    }


def migrate_session_state(session_dir: Path) -> dict[str, Any]:
    """Idempotently migrate a v1 session into v2 operational state without fabricating evidence.

    Backs up existing files before any persistent write and validates before replacing.
    """
    curr_path = session_dir / "scratchpad" / "curriculum.json"
    graph_path = session_dir / "00-GRAPH.json"
    if not curr_path.is_file() and not graph_path.is_file():
        raise FileNotFoundError(f"No operational session state found in {session_dir}")

    curr = load_curriculum(session_dir)
    graph = load_json_dict(graph_path) or {"schema_version": 2, "kind": "curriculum_dependency_graph", "nodes": {}, "order": []}
    events = load_events(session_dir)
    review_store = load_review_state(session_dir)

    g_nodes = dict(graph.get("nodes", {}))
    c_nodes = dict(curr.get("nodes", {}))
    order = list(curr.get("order") or graph.get("order") or list(g_nodes.keys()))

    for nid in order:
        gnode = g_nodes.get(nid, {}) if isinstance(g_nodes.get(nid), dict) else {}
        cnode = dict(c_nodes.get(nid, {})) if isinstance(c_nodes.get(nid), dict) else {}
        merged = dict(gnode)
        merged.update(cnode)
        merged.setdefault("id", nid)
        merged.setdefault("slug", nid)
        merged.setdefault("title", nid)
        merged["objectives"] = normalize_objectives_list(nid, merged)

        # Derive objective proficiency from existing events without fabricating assistance/retention/transfer
        node_status = str(merged.get("status") or "unstarted")
        node_cp = str(merged.get("checkpoint") or "0/4")
        tnum = nid.replace("topic-", "")
        t_evs = [e for e in events if normalize_topic_num(str(e.get("topic", ""))) == tnum]
        for idx, obj in enumerate(merged["objectives"]):
            oid = obj["id"]
            obj_evs = [e for e in t_evs if e.get("objective_id") == oid]
            if idx == 0:
                obj_evs.extend(e for e in t_evs if not e.get("objective_id"))
            derived = derive_objective_evidence(obj, obj_evs, node_status=node_status, node_checkpoint=node_cp)
            merged["objectives"][idx] = derived
            if derived["proficiency"].get("legacy_completed") or derived["proficiency"]["status"] == "demonstrated_independently":
                last_ts = t_evs[-1].get("ts") if t_evs else merged.get("mastered_at") or merged.get("last_event_ts")
                sync_review_item_for_legacy_node(
                    review_store,
                    target_id=oid,
                    topic_id=nid,
                    last_ts=last_ts,
                    legacy_mastered=bool(derived["proficiency"].get("legacy_completed")),
                )
        c_nodes[nid] = merged

    new_curr = dict(curr)
    new_curr["schema_version"] = CURRICULUM_SCHEMA_VERSION
    new_curr["topic"] = curr.get("topic") or graph.get("topic") or session_dir.name
    new_curr["nodes"] = c_nodes
    new_curr["order"] = order

    # Validate before persisting
    val_errs = _validate_curriculum_references_and_cycles(new_curr)
    if val_errs:
        raise ValueError(f"Migration aborted due to invalid state: {val_errs[0]['detail']}")

    new_curr_text = json.dumps(new_curr, indent=2, ensure_ascii=False) + "\n"
    new_rev_text = json.dumps(review_store, indent=2, ensure_ascii=False) + "\n"

    curr_changed = (not curr_path.is_file()) or read_text_safe(curr_path) != new_curr_text
    rev_path = session_dir / "scratchpad" / "review-state.json"
    rev_changed = (not rev_path.is_file()) or read_text_safe(rev_path) != new_rev_text

    backup_dir: Path | None = None
    if curr_changed or rev_changed:
        backup_dir = backup_state_files(session_dir, label="migrate")
        if curr_changed:
            atomic_write_text(curr_path, new_curr_text)
        if rev_changed:
            atomic_write_text(rev_path, new_rev_text)

    return {
        "ok": True,
        "session_dir": str(session_dir),
        "schema_version": CURRICULUM_SCHEMA_VERSION,
        "migrated_nodes": len(c_nodes),
        "changed": curr_changed or rev_changed,
        "backup_dir": str(backup_dir) if backup_dir else None,
    }


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
            else:
                errors.extend(_validate_curriculum_references_and_cycles(curr))
        except (OSError, json.JSONDecodeError) as exc:
            errors.append({"file": "scratchpad/curriculum.json", "type": "invalid_json", "detail": str(exc)})

    rev_file = session_dir / "scratchpad" / "review-state.json"
    if rev_file.is_file():
        try:
            rev = json.loads(read_text_safe(rev_file))
            if not isinstance(rev, dict) or not isinstance(rev.get("items"), dict):
                errors.append({"file": "scratchpad/review-state.json", "type": "invalid_review_schema", "detail": "Expected object with items dict"})
        except (OSError, json.JSONDecodeError) as exc:
            errors.append({"file": "scratchpad/review-state.json", "type": "invalid_json", "detail": str(exc)})

    media_file = session_dir / "scratchpad" / "media-provenance.json"
    if media_file.is_file():
        try:
            mp = json.loads(read_text_safe(media_file))
            if not isinstance(mp, dict) or not isinstance(mp.get("items"), list):
                errors.append({"file": "scratchpad/media-provenance.json", "type": "invalid_media_schema", "detail": "Expected object with items list"})
        except (OSError, json.JSONDecodeError) as exc:
            errors.append({"file": "scratchpad/media-provenance.json", "type": "invalid_json", "detail": str(exc)})

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

        # Build honest objective-level state without fabricating assistance/retention/transfer
        node_objs = normalize_objectives_list(node_id, node_entry)
        for oidx, obj in enumerate(node_objs):
            node_objs[oidx] = derive_objective_evidence(
                obj,
                t_events if oidx == 0 else [],
                node_status=status,
                node_checkpoint=checkpoint,
            )
        node_entry["objectives"] = node_objs

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
        c_entry = dict(gval)
        c_entry.setdefault("id", gid)
        c_entry["objectives"] = normalize_objectives_list(gid, c_entry)
        for oidx, obj in enumerate(c_entry["objectives"]):
            c_entry["objectives"][oidx] = derive_objective_evidence(
                obj,
                [],
                node_status=str(c_entry.get("status") or "unstarted"),
                node_checkpoint=str(c_entry.get("checkpoint") or "0/4"),
            )
        curriculum_nodes[gid] = c_entry
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

    new_curr = {
        "schema_version": CURRICULUM_SCHEMA_VERSION,
        "topic": existing_graph.get("topic") or src.name,
        "nodes": curriculum_nodes,
        "order": order,
        "learning_records": [r["file"] for r in lr_records],
    }

    # Build deterministic review state for imported nodes without fabricating timestamps
    review_store = load_review_state(dest)
    for nid in order:
        cnode = curriculum_nodes.get(nid, {})
        last_ts = cnode.get("last_event_ts") or cnode.get("mastered_at") or None
        for obj in cnode.get("objectives", []):
            prof = obj.get("proficiency", {})
            if prof.get("legacy_completed") or prof.get("status") == "demonstrated_independently":
                sync_review_item_for_legacy_node(
                    review_store,
                    target_id=obj["id"],
                    topic_id=nid,
                    last_ts=last_ts,
                    legacy_mastered=bool(prof.get("legacy_completed")),
                )

    val_errs = _validate_curriculum_references_and_cycles(new_curr)
    if val_errs:
        raise ValueError(f"Imported legacy curriculum failed validation: {val_errs[0]['detail']}")

    new_graph_text = json.dumps(new_graph, indent=2, ensure_ascii=False) + "\n"
    new_curr_text = json.dumps(new_curr, indent=2, ensure_ascii=False) + "\n"
    new_rev_text = json.dumps(review_store, indent=2, ensure_ascii=False) + "\n"

    graph_dest = dest / "00-GRAPH.json"
    curr_dest = dest / "scratchpad" / "curriculum.json"
    rev_dest = dest / "scratchpad" / "review-state.json"

    graph_changed = (not graph_dest.is_file()) or read_text_safe(graph_dest) != new_graph_text
    curr_changed = (not curr_dest.is_file()) or read_text_safe(curr_dest) != new_curr_text
    rev_changed = (not rev_dest.is_file()) or read_text_safe(rev_dest) != new_rev_text

    if (graph_changed and graph_dest.is_file()) or (curr_changed and curr_dest.is_file()):
        backup_state_files(dest, label="import-legacy")

    if graph_changed:
        atomic_write_text(graph_dest, new_graph_text)
    if curr_changed:
        atomic_write_text(curr_dest, new_curr_text)
    if rev_changed:
        atomic_write_text(rev_dest, new_rev_text)

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
            "agreed_scope": {"goal": "unknown", "in_scope": [], "out_of_scope": []},
            "topic": topic or "unknown",
            "curriculum_ids": [],
            "session_id": "unknown",
            "resume_checkpoint": "unknown",
            "resume_location": {"active_subtopic": "unknown", "stage_cp": "unknown"},
            "concepts_taught": [],
            "concepts_introduced": [],
            "concepts_planned": [],
            "objectives_demonstrated": [],
            "unresolved_topics": [],
            "untested_or_unresolved_gaps": {
                "required_untested": [],
                "unresolved_objectives": [],
                "unresolved_prerequisites": [],
            },
            "mastery_claims": [],
            "weak_spots_and_misconceptions": [],
            "misconceptions_and_corrections": [],
            "examples_analogies_used": list(examples_used or []),
            "learner_profile": {
                "level": "unknown",
                "language": "unknown",
                "known_preferences": [],
            },
            "source_provenance": [],
            "media_provenance": [],
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
    events_by_obj: dict[str, list[dict[str, Any]]] = {}
    for ev in events:
        nev = normalize_event(ev)
        if nev["topic_id"]:
            events_by_nid.setdefault(nev["topic_id"], []).append(nev)
        if nev["objective_id"]:
            events_by_obj.setdefault(nev["objective_id"], []).append(nev)

    concepts_taught: list[dict[str, Any]] = []
    concepts_introduced: list[dict[str, Any]] = []
    concepts_planned: list[dict[str, Any]] = []
    objectives_demonstrated: list[dict[str, Any]] = []
    unresolved_topics: list[dict[str, Any]] = []
    mastery_claims: list[dict[str, Any]] = []

    for nid in selected_ids:
        gnode = nodes.get(nid, {})
        cnode = c_nodes.get(nid, {})
        title = str(gnode.get("title") or cnode.get("title") or nid)
        status = str(gnode.get("status") or "unstarted")
        cp = str(gnode.get("checkpoint") or "0/4")
        nid_events = events_by_nid.get(nid, [])

        merged_node = dict(cnode)
        merged_node.update(gnode)
        objs = normalize_objectives_list(nid, merged_node)
        derived_objs = []
        for idx, obj in enumerate(objs):
            oevs = list(events_by_obj.get(obj["id"], []))
            if idx == 0:
                oevs.extend(e for e in nid_events if not e.get("objective_id"))
            derived_objs.append(derive_objective_evidence(obj, oevs, node_status=status, node_checkpoint=cp))

        item_ref: dict[str, Any] = {"id": nid, "title": title}
        key_eqs = cnode.get("key_equations") or gnode.get("key_equations") or []
        if key_eqs:
            item_ref["key_equations"] = key_eqs[:4]

        has_independent = any(d["proficiency"]["status"] == "demonstrated_independently" for d in derived_objs)
        has_assisted_or_intro = any(
            d["proficiency"]["status"] in ("introduced", "practiced_with_support")
            or d["coverage_status"] in ("introduced", "assessed")
            for d in derived_objs
        )
        has_pass_or_progress = (
            status == "mastered"
            or cp != "0/4"
            or any(ev.get("result") == "pass" or ev.get("status") == "pass" for ev in nid_events)
            or has_independent
            or has_assisted_or_intro
        )

        for d in derived_objs:
            dp = d["proficiency"]
            if dp["status"] == "demonstrated_independently":
                objectives_demonstrated.append(
                    {
                        "id": d["id"],
                        "topic_id": nid,
                        "description": d["description"],
                        "retention_status": dp["retention"]["status"],
                        "transfer_status": dp["transfer"]["status"],
                        "dimensions_evidenced": dp["dimensions_evidenced"],
                    }
                )
            elif dp["status"] in ("introduced", "practiced_with_support"):
                concepts_introduced.append(
                    {
                        "id": d["id"],
                        "topic_id": nid,
                        "title": title,
                        "description": d["description"],
                        "proficiency_status": dp["status"],
                    }
                )

        # Aggregate topic-level retention/transfer honestly
        ret_statuses = [d["proficiency"]["retention"]["status"] for d in derived_objs]
        tr_statuses = [d["proficiency"]["transfer"]["status"] for d in derived_objs]
        agg_ret = "retained" if ret_statuses and all(s == "retained" for s in ret_statuses) else ("lapsed" if "lapsed" in ret_statuses else "untested")
        agg_tr = "demonstrated" if tr_statuses and all(s == "demonstrated" for s in tr_statuses) else ("failed" if "failed" in tr_statuses else "untested")

        if status == "mastered" or (derived_objs and all(d["proficiency"]["status"] == "demonstrated_independently" for d in derived_objs)):
            concepts_taught.append(item_ref)
            evidence_bits = []
            if gnode.get("last_invariant"):
                evidence_bits.append(f"invariant: {gnode['last_invariant']}")
            if nid_events:
                last_ev = nid_events[-1]
                evidence_bits.append(
                    f"event {last_ev.get('assessment_type')} {last_ev.get('result')} (assistance={last_ev.get('assistance_level')}) at {last_ev.get('ts', '')}"
                )
            assessed_label = "mastered" if status == "mastered" else "demonstrated_independently"
            mastery_claims.append(
                {
                    "id": nid,
                    "title": title,
                    "assessed_status": assessed_label,
                    "proficiency_status": "demonstrated_independently" if has_independent else "legacy_unverified",
                    "retention_status": agg_ret,
                    "transfer_status": agg_tr,
                    "checkpoint": cp,
                    "evidence": "; ".join(evidence_bits) if evidence_bits else "checkpoint 4/4 flushed",
                }
            )
        elif has_pass_or_progress:
            concepts_taught.append(item_ref)
            unresolved_topics.append(item_ref)
            statuses = [d["proficiency"]["status"] for d in derived_objs]
            if "weakened" in statuses:
                claim_status = "weakened"
            elif "practiced_with_support" in statuses:
                claim_status = "practiced_with_support"
            elif "introduced" in statuses:
                claim_status = "introduced"
            else:
                claim_status = "in_progress"
            passed_cps = [f"{ev.get('cp')}/4" for ev in nid_events if ev.get("status") == "pass" and ev.get("cp") is not None]
            mastery_claims.append(
                {
                    "id": nid,
                    "title": title,
                    "assessed_status": claim_status if claim_status != "in_progress" else "in_progress",
                    "proficiency_status": claim_status,
                    "retention_status": agg_ret,
                    "transfer_status": agg_tr,
                    "checkpoint": cp,
                    "evidence": f"passed checkpoints {passed_cps}" if passed_cps else (derived_objs[0]["evidence_summary"] if derived_objs else f"checkpoint {cp}"),
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
                    "proficiency_status": "untested",
                    "retention_status": "untested",
                    "transfer_status": "untested",
                    "checkpoint": "0/4",
                    "evidence": "unassessed",
                }
            )

    weak_spots: list[dict[str, Any]] = []
    misconceptions_and_corrections: list[dict[str, Any]] = []
    for raw_ev in events:
        nev = normalize_event(raw_ev)
        if nev["result"] in ("fail", "partial") or nev["status"] == "retry":
            entry = {
                "topic": nev["topic_id"] or f"topic-{nev['topic']}",
                "objective_id": nev["objective_id"] or None,
                "checkpoint": f"{nev['cp']}/4" if nev.get("cp") is not None else "n/a",
                "note": nev["rationale"] or "retry recorded",
                "misconception_ref": nev.get("misconception_ref"),
                "ts": nev["ts"],
            }
            weak_spots.append(entry)
            misconceptions_and_corrections.append(entry)

    lr_records = load_learning_records(session_dir)
    for rec in lr_records:
        if rec.get("status", "").startswith("superseded"):
            continue
        lr_entry = {
            "record": rec["file"],
            "title": rec["title"],
            "insight": rec["insight"] or rec["context"],
        }
        weak_spots.append(lr_entry)
        misconceptions_and_corrections.append(lr_entry)

    ingested = load_json_dict(session_dir / "scratchpad" / "ingested-sources.json") or {}
    sources: list[dict[str, Any]] = []
    for src_item in ingested.get("sources", []) if isinstance(ingested.get("sources"), list) else []:
        if isinstance(src_item, dict):
            entry = {k: v for k, v in src_item.items() if k in {"title", "url", "type", "retrieved_at"}}
            if entry:
                sources.append(entry)

    media_store = load_media_provenance(session_dir)
    media_prov = [
        {
            k: m.get(k)
            for k in ("media_id", "objective_id", "kind", "title", "source_page_url", "asset_url", "license", "verification_status", "retrieved_at")
        }
        for m in media_store.get("items", [])[-10:]
        if isinstance(m, dict)
    ]

    mission = _extract_mission_metadata(session_dir)
    gap_summary = derive_session_coverage_and_gaps(curriculum, events, mission=mission)

    known_prefs: list[str] = []
    if mission.get("depth_mode"):
        known_prefs.append(str(mission["depth_mode"]))
    for ec in mission.get("explanation_constraints", []) or []:
        if str(ec).strip() and str(ec).strip() not in known_prefs:
            known_prefs.append(str(ec).strip())

    learner_profile = {
        "level": str(mission.get("prior_knowledge") or "unknown"),
        "language": str(mission.get("language") or "unknown"),
        "known_preferences": known_prefs,
    }
    if mission.get("time_budget_minutes"):
        learner_profile["time_budget_minutes"] = mission["time_budget_minutes"]

    agreed_scope = {
        "goal": str(mission.get("goal") or (curriculum.get("scope") or {}).get("goal") or "unknown"),
        "in_scope": mission.get("in_scope") or (curriculum.get("scope") or {}).get("in_scope") or [],
        "out_of_scope": mission.get("out_of_scope") or (curriculum.get("scope") or {}).get("out_of_scope") or [],
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
    active_sub = m_active.group(1).strip() if m_active else "unknown"
    stage_cp_str = m_stage_cp.group(1).strip() if m_stage_cp else "unknown"
    resume_cp = f"{active_sub} | {stage_cp_str}" if m_active else stage_cp_str

    envelope = redact_sensitive(
        {
            "schema_version": HANDOFF_SCHEMA_VERSION,
            "request_id": req_id,
            "requested_artifact": requested_artifact or "study_notes",
            "requested_scope": requested_scope or ("subtopic" if target_nid else "topic"),
            "agreed_scope": agreed_scope,
            "topic": resolved_topic,
            "curriculum_ids": selected_ids,
            "session_id": session_dir.name,
            "resume_checkpoint": resume_cp,
            "resume_location": {
                "active_subtopic": active_sub,
                "stage_cp": stage_cp_str,
            },
            "concepts_taught": concepts_taught,
            "concepts_introduced": concepts_introduced,
            "concepts_planned": concepts_planned,
            "objectives_demonstrated": objectives_demonstrated,
            "unresolved_topics": unresolved_topics,
            "untested_or_unresolved_gaps": {
                "required_untested": gap_summary["required_untested"],
                "unresolved_objectives": gap_summary["unresolved_objectives"],
                "unresolved_prerequisites": gap_summary["unresolved_prerequisites"],
            },
            "mastery_claims": mastery_claims,
            "weak_spots_and_misconceptions": weak_spots[-12:],
            "misconceptions_and_corrections": misconceptions_and_corrections[-12:],
            "examples_analogies_used": list(examples_used or []),
            "learner_profile": learner_profile,
            "source_provenance": sources[:10],
            "media_provenance": media_prov,
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
