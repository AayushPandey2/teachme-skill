#!/usr/bin/env python3
"""Deterministic zero-token CLI for managing /teachme Markdown vaults.

Standard-library only (Python 3). Offloads session state inspection, graph
indexing, HTML-section slicing, delta event ticking, and vault verification.
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

REQUIRED_TOPIC_SECTIONS = [
    "L1-ANCHOR",
    "L2-PREREQS-AND-MOTIVATION",
    "L3-FOUR-LAYER-THEORY",
    "L4-DERIVATION-AND-CODE",
    "L5-WORKBOOK-AND-GRAPH",
]

TYPED_EDGE_FIELDS = (
    "depends_on",
    "unlocks",
    "contrasts_with",
    "fixes_failure_of",
)

SECTION_RE = re.compile(r"^\s*<!--\s*SECTION:\s*([A-Za-z0-9_-]+)\s*-->\s*$")
WIKILINK_RE = re.compile(r"\[\[([^\]]+)\]\]")
MDLINK_RE = re.compile(r"(?<!!)\[[^\]]*\]\(([^)]+)\)")
HEADING_RE = re.compile(r"^\s{0,3}#{1,6}\s+(.+?)\s*$")
FENCE_RE = re.compile(r"^\s*(`{3,}|~{3,})")


def resolve_vault_root() -> Path:
    """Resolve <VAULT_ROOT> from ~/.teachme-config.json or default ~/notes."""
    cfg_path = Path.home() / ".teachme-config.json"
    if cfg_path.is_file():
        try:
            data = json.loads(cfg_path.read_text(encoding="utf-8"))
            raw = str(data.get("notes_root", "")).strip()
            if raw:
                return Path(os.path.expandvars(raw)).expanduser().resolve()
        except (OSError, json.JSONDecodeError):
            pass
    return (Path.home() / "notes").resolve()


def resolve_vault_path(raw_path: str | None) -> Path:
    """Resolve an explicit vault path or auto-select the active vault."""
    if raw_path:
        return Path(os.path.expandvars(raw_path)).expanduser().resolve()

    vault_root = resolve_vault_root()
    if not vault_root.is_dir():
        raise FileNotFoundError(f"Vault root does not exist: {vault_root}")

    candidates = [
        p for p in vault_root.iterdir()
        if p.is_dir() and (p / "00-SESSION-STATE.md").is_file()
    ]
    if not candidates:
        raise FileNotFoundError(
            f"No vault with 00-SESSION-STATE.md found under {vault_root}"
        )
    if len(candidates) == 1:
        return candidates[0]

    # Pick the most recently updated 00-SESSION-STATE.md
    candidates.sort(
        key=lambda p: (p / "00-SESSION-STATE.md").stat().st_mtime,
        reverse=True,
    )
    return candidates[0]


def parse_scalar(val: str) -> str:
    val = val.split("#", 1)[0].strip() if not (val.startswith('"') or val.startswith("'")) else val.strip()
    if len(val) >= 2 and ((val[0] == '"' and val[-1] == '"') or (val[0] == "'" and val[-1] == "'")):
        return val[1:-1]
    return val


def parse_inline_list(raw: str) -> list[str]:
    inner = raw.strip()[1:-1].strip()
    if not inner:
        return []
    return [parse_scalar(item) for item in inner.split(",") if parse_scalar(item)]


def read_utf8(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig", errors="replace")


def parse_frontmatter(text: str) -> tuple[dict[str, Any], int]:
    """Parse simple YAML frontmatter returning (metadata_dict, body_start_line_idx)."""
    lines = text.lstrip("\ufeff").splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, 0

    end_idx = -1
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end_idx = i
            break
    if end_idx == -1:
        return {}, 0

    meta: dict[str, Any] = {}
    current_key: str | None = None
    for raw_line in lines[1:end_idx]:
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("- ") and current_key is not None:
            existing = meta.get(current_key)
            if not isinstance(existing, list):
                existing = []
            existing.append(parse_scalar(stripped[2:].strip()))
            meta[current_key] = existing
            continue
        if ":" in raw_line:
            key, rest = raw_line.split(":", 1)
            key = key.strip()
            val = rest.strip()
            current_key = key
            if not val:
                meta[key] = []
            elif val.startswith("[") and val.endswith("]"):
                meta[key] = parse_inline_list(val)
            else:
                meta[key] = parse_scalar(val)
    return meta, end_idx + 1


def build_graph(vault: Path) -> dict[str, Any]:
    """Scan topics/*.md frontmatter and write 00-GRAPH.json."""
    topics_dir = vault / "topics"
    nodes: dict[str, Any] = {}
    order: list[str] = []

    if topics_dir.is_dir():
        for path in sorted(topics_dir.glob("*.md")):
            text = read_utf8(path)
            meta, _ = parse_frontmatter(text)
            stem_prefix = path.stem.split("-", 1)[0]
            node_id = str(meta.get("id") or f"topic-{stem_prefix}")
            node: dict[str, Any] = {
                "file": f"topics/{path.name}",
                "title": str(meta.get("title") or meta.get("subtopic") or path.stem),
                "status": str(meta.get("status") or "unstarted"),
                "checkpoint": str(meta.get("checkpoint") or "0/4"),
            }
            for edge in TYPED_EDGE_FIELDS:
                raw_edges = meta.get(edge, [])
                if isinstance(raw_edges, str):
                    raw_edges = [raw_edges] if raw_edges else []
                node[edge] = [str(x) for x in raw_edges if str(x).strip()]
            nodes[node_id] = node
            order.append(node_id)

    graph = {"nodes": nodes, "order": order}
    (vault / "00-GRAPH.json").write_text(
        json.dumps(graph, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return graph


def dump_json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, separators=(",", ":"))


def cmd_graph(args: argparse.Namespace) -> int:
    vault = resolve_vault_path(args.vault_path)
    graph = build_graph(vault)
    print(dump_json(graph))
    return 0


def parse_session_state_fields(text: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    patterns = {
        "active_topic": r"^\s*-\s*\*\*Active Subtopic:\*\*\s*`?([^`\r\n]+?)`?\s*$",
        "stage_cp": r"^\s*-\s*\*\*Live Stage & Checkpoint:\*\*\s*`?([^`\r\n]+?)`?\s*$",
        "last_invariant": r"^\s*-\s*\*\*Last Verified Invariant:\*\*\s*(.+?)\s*$",
    }
    for key, pat in patterns.items():
        m = re.search(pat, text, flags=re.MULTILINE)
        if m:
            fields[key] = m.group(1).strip()
    return fields


def cmd_state(args: argparse.Namespace) -> int:
    vault = resolve_vault_path(args.vault_path)
    state_file = vault / "00-SESSION-STATE.md"
    graph_file = vault / "00-GRAPH.json"

    fields: dict[str, str] = {}
    state_text = ""
    if state_file.is_file():
        state_text = read_utf8(state_file)
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
        try:
            graph = json.loads(graph_file.read_text(encoding="utf-8"))
            nodes = graph.get("nodes", {})
            total_count = len(nodes)
            completed_count = sum(
                1 for n in nodes.values() if n.get("status") == "mastered"
            )
        except (OSError, json.JSONDecodeError):
            pass
    if total_count == 0 and (vault / "topics").is_dir():
        topic_files = sorted((vault / "topics").glob("*.md"))
        total_count = len(topic_files)
        completed_count = len(re.findall(r"`\[x\]\s*\d+`", state_text))

    summary = {
        "vault_path": str(vault),
        "active_topic": fields.get("active_topic", ""),
        "depth_stage": depth_stage or "1/3",
        "checkpoint": checkpoint or "1/4",
        "completed_count": completed_count,
        "total_count": total_count,
        "last_invariant": fields.get("last_invariant", ""),
    }
    print(dump_json(summary))
    return 0


def extract_section(text: str, section_name: str) -> str:
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


def cmd_slice(args: argparse.Namespace) -> int:
    md_path = Path(os.path.expandvars(args.markdown_file)).expanduser().resolve()
    if not md_path.is_file():
        print(json.dumps({"error": f"File not found: {md_path}"}), file=sys.stderr)
        return 1
    text = read_utf8(md_path)
    try:
        sliced = extract_section(text, args.section)
    except ValueError as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        return 1
    print(sliced)
    return 0


def infer_depth_stage(cp: int, explicit_stage: int | None) -> int:
    if explicit_stage is not None:
        return explicit_stage
    if cp <= 1:
        return 1
    if cp == 2:
        return 2
    return 3


def cmd_tick(args: argparse.Namespace) -> int:
    vault = resolve_vault_path(args.vault_path)
    topic_num = str(args.topic).strip().zfill(2) if args.topic.isdigit() else str(args.topic).strip()
    cp = int(args.cp)
    status = args.status
    stage = infer_depth_stage(cp, args.stage)

    scratchpad = vault / "scratchpad"
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

    with events_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")

    # Resolve matching topic file
    topics_dir = vault / "topics"
    matched_file = f"topics/{topic_num}-subtopic.md"
    all_nums: list[str] = []
    if topics_dir.is_dir():
        for p in sorted(topics_dir.glob("*.md")):
            num_prefix = p.stem.split("-", 1)[0]
            all_nums.append(num_prefix)
            if num_prefix == topic_num:
                matched_file = f"topics/{p.name}"

    state_file = vault / "00-SESSION-STATE.md"
    mark = "[x]" if (cp == 4 and status == "pass") else "[~]"

    if state_file.is_file():
        lines = read_utf8(state_file).splitlines()
    else:
        status_tokens = " ".join(f"`[ ] {n}`" for n in (all_nums or [topic_num]))
        lines = [
            f"# Session State: {vault.name}",
            "",
            f"- **Active Subtopic:** `{matched_file}`",
            f"- **Live Stage & Checkpoint:** `Depth Stage {stage}/3 | Checkpoint [{cp}/4]`",
            "- **Last Verified Invariant:** Initialized.",
            "",
            "## Compact Subtopic Status Map",
            status_tokens,
            "<!-- Legend: [x] mastered | [~] in-progress | [ ] unstarted -->",
        ]

    updated_lines: list[str] = []
    token_re = re.compile(rf"`\[[ x~]\]\s*{re.escape(topic_num)}`")
    for line in lines:
        if line.lstrip().startswith("- **Active Subtopic:**"):
            updated_lines.append(f"- **Active Subtopic:** `{matched_file}`")
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

    state_file.write_text("\n".join(updated_lines[:59]) + "\n", encoding="utf-8")
    print(
        dump_json(
            {
                "ok": True,
                "topic": topic_num,
                "stage": f"{stage}/3",
                "cp": f"{cp}/4",
                "status": status,
                "events_file": str(events_path),
                "state_file": str(state_file),
            }
        )
    )
    return 0


def _quote_yaml(val: str) -> str:
    escaped = val.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _format_yaml_list(items: list[str]) -> str:
    if not items:
        return "[]"
    return "[" + ", ".join(_quote_yaml(str(x)) for x in items) + "]"


def _build_topic_stub(item: dict[str, Any], next_id: str | None) -> str:
    slug = str(item["slug"]).strip()
    num = slug.split("-", 1)[0].zfill(2) if slug.split("-", 1)[0].isdigit() else slug
    title = str(item.get("title") or slug).strip()
    deps = [str(x) for x in item.get("depends_on", []) if str(x).strip()]
    contrasts = [str(x) for x in item.get("contrasts_with", []) if str(x).strip()]
    unlocks = [str(x) for x in item.get("unlocks", []) if str(x).strip()] or ([next_id] if next_id else [])
    fixes = [str(x) for x in item.get("fixes_failure_of", []) if str(x).strip()]

    return "\n".join(
        [
            "---",
            f"id: {_quote_yaml(f'topic-{num}')}",
            f"title: {_quote_yaml(title)}",
            'status: "unstarted"',
            'checkpoint: "0/4"',
            f"depends_on: {_format_yaml_list(deps)}",
            f"unlocks: {_format_yaml_list(unlocks)}",
            f"contrasts_with: {_format_yaml_list(contrasts)}",
            f"fixes_failure_of: {_format_yaml_list(fixes)}",
            "key_equations: []",
            "---",
            "",
            f"# {num}. {title}",
            "",
            "<!-- SECTION: L1-ANCHOR -->",
            "## 1. The Core Idea (30-Second Anchor)",
            "",
            "<!-- SECTION: L2-PREREQS-AND-MOTIVATION -->",
            "## 2. Building Blocks & Why This Exists",
            "",
            "<!-- SECTION: L3-FOUR-LAYER-THEORY -->",
            "## 3. How It Works: Intuition to Formal Math",
            "",
            "<!-- SECTION: L4-DERIVATION-AND-CODE -->",
            "## 4. Step-by-Step Proof (Zero Skips)",
            "",
            "## 5. Run It Yourself (Python Verification)",
            "",
            "<!-- SECTION: L5-WORKBOOK-AND-GRAPH -->",
            "## 6. Practice Workbook (I Do -> We Do -> You Do)",
            "",
            "## 7. Common Traps, Primary Sources & Mastery Graph",
            "",
            "### 4-Checkpoint Mastery Ledger",
            "- [ ] `[1/4]` Discovery Prediction",
            "- [ ] `[2/4]` We-Do Faded Step",
            "- [ ] `[3/4]` You-Do Cold Drill",
            "- [ ] `[4/4]` Edge-Case & Feynman Gate",
            "",
        ]
    )


def _load_subtopic_items(args: argparse.Namespace) -> list[dict[str, Any]]:
    sub_file = getattr(args, "subtopics", None)
    if sub_file:
        p = Path(os.path.expandvars(sub_file)).expanduser().resolve()
        if not p.is_file():
            raise FileNotFoundError(f"Subtopics JSON not found: {p}")
        data = json.loads(read_utf8(p))
        if not isinstance(data, list):
            raise ValueError("Subtopics JSON must be a list of objects")
        return [dict(item) for item in data if isinstance(item, dict) and item.get("slug")]
    raw_topics = getattr(args, "topics", "") or ""
    return [
        {"slug": t.strip(), "title": t.strip()}
        for t in raw_topics.split(",")
        if t.strip()
    ]


def cmd_init(args: argparse.Namespace) -> int:
    vault = Path(os.path.expandvars(args.vault_path)).expanduser().resolve()
    for sub in ("topics", "atomic", "learning-records", "scratchpad"):
        (vault / sub).mkdir(parents=True, exist_ok=True)

    topic_title = (getattr(args, "topic", None) or getattr(args, "title", None) or vault.name).strip()
    items = _load_subtopic_items(args)
    slugs = [str(it["slug"]).strip() for it in items]
    nums = [s.split("-", 1)[0].zfill(2) if s.split("-", 1)[0].isdigit() else s for s in slugs]
    first_topic = f"topics/{slugs[0]}.md" if slugs else "topics/01-overview.md"

    # 1. Create missing topic stubs without overwriting existing files
    stubs_created = 0
    for idx, item in enumerate(items):
        slug = str(item["slug"]).strip()
        target = vault / "topics" / f"{slug}.md"
        if not target.exists():
            next_id = f"topic-{nums[idx + 1]}" if idx + 1 < len(nums) else None
            target.write_text(_build_topic_stub(item, next_id), encoding="utf-8")
            stubs_created += 1

    # 2. Create or non-destructively update 00-SESSION-STATE.md (<60 lines)
    state_path = vault / "00-SESSION-STATE.md"
    if not state_path.exists():
        status_tokens = " ".join(f"`[ ] {n}`" for n in (nums or ["01"]))
        state_lines = [
            f"# Session State: {topic_title}",
            "",
            f"- **Active Subtopic:** `{first_topic}`",
            "- **Live Stage & Checkpoint:** `Depth Stage 1/3 | Checkpoint [1/4]`",
            "- **Last Verified Invariant:** Vault initialized.",
            "",
            "## Compact Subtopic Status Map",
            status_tokens,
            "<!-- Legend: [x] mastered | [~] in-progress | [ ] unstarted -->",
        ]
        state_path.write_text("\n".join(state_lines) + "\n", encoding="utf-8")
    elif nums:
        s_lines = read_utf8(state_path).splitlines()
        out_s: list[str] = []
        for line in s_lines:
            if "`[ ] " in line or "`[x] " in line or "`[~] " in line:
                missing_nums = [
                    n for n in nums if not re.search(rf"`\[[ x~]\]\s*{re.escape(n)}`", line)
                ]
                if missing_nums:
                    line = line.rstrip() + " " + " ".join(f"`[ ] {n}`" for n in missing_nums)
            out_s.append(line)
        state_path.write_text("\n".join(out_s[:59]) + "\n", encoding="utf-8")

    # 3. Create or non-destructively update 00-MOC-INDEX.md
    moc_path = vault / "00-MOC-INDEX.md"
    if not moc_path.exists():
        tracker_lines = [
            f"- [ ] **{n}.** [[topics/{s}]]" for n, s in zip(nums, slugs)
        ] or ["- [ ] **01.** [[topics/01-overview]]"]
        moc_lines = [
            f"# Map of Content (MOC): {topic_title}",
            "",
            "## Vault Navigation",
            "- [[00-SESSION-STATE]] — Hot-state resume pointer (<60 lines)",
            "",
            "## Complete Subtopic Syllabus Tracker (`topics/`)",
            *tracker_lines,
            "",
            "## Cumulative Synthesis Strips (Auto-Compacted Every 3 Subtopics)",
            "",
            "## Atomic Zettelkasten Concept Index (`atomic/`)",
        ]
        moc_path.write_text("\n".join(moc_lines) + "\n", encoding="utf-8")
    elif slugs:
        moc_text = read_utf8(moc_path)
        moc_lines = moc_text.splitlines()
        missing_entries = [
            f"- [ ] **{n}.** [[topics/{s}]]"
            for n, s in zip(nums, slugs)
            if f"topics/{s}" not in moc_text
        ]
        if missing_entries:
            inserted = False
            new_moc: list[str] = []
            for idx, line in enumerate(moc_lines):
                new_moc.append(line)
                if not inserted and line.startswith("## Complete Subtopic Syllabus Tracker"):
                    # Insert after existing tracker bullets
                    j = idx + 1
                    while j < len(moc_lines) and (moc_lines[j].startswith("- ") or not moc_lines[j].strip()):
                        j += 1
                    # Defer insertion right before next heading
                if not inserted and idx > 0 and line.startswith("## ") and "Syllabus Tracker" not in line and any("Syllabus Tracker" in x for x in new_moc):
                    new_moc.pop()
                    new_moc.extend(missing_entries)
                    new_moc.append("")
                    new_moc.append(line)
                    inserted = True
            if not inserted:
                new_moc.extend(missing_entries)
            moc_path.write_text("\n".join(new_moc) + "\n", encoding="utf-8")

    graph = build_graph(vault)
    print(
        dump_json(
            {
                "ok": True,
                "vault_path": str(vault),
                "topics": len(slugs),
                "stubs_created": stubs_created,
                "graph_nodes": len(graph["nodes"]),
            }
        )
    )
    return 0


def cmd_context(args: argparse.Namespace) -> int:
    """Return state + node + stage slice + queue + 1-hop L0-L1 anchors in one call."""
    vault = resolve_vault_path(args.vault_path)
    raw_topic = str(args.topic).strip()
    if raw_topic.startswith("topic-"):
        raw_topic = raw_topic[len("topic-"):]
    topic_num = raw_topic.zfill(2) if raw_topic.isdigit() else raw_topic
    node_id = f"topic-{topic_num}"

    # 1. Session state
    state_file = vault / "00-SESSION-STATE.md"
    fields = parse_session_state_fields(read_utf8(state_file)) if state_file.is_file() else {}
    stage_cp = fields.get("stage_cp", "")
    m_cp = re.search(r"Checkpoint\s*\[?([0-9]+)/[0-9]+\]?", stage_cp)
    active_cp = int(m_cp.group(1)) if m_cp else 1

    # 2. Graph lookup (read existing or build)
    graph_path = vault / "00-GRAPH.json"
    if graph_path.is_file():
        try:
            graph = json.loads(read_utf8(graph_path))
        except json.JSONDecodeError:
            graph = build_graph(vault)
    else:
        graph = build_graph(vault)

    nodes = graph.get("nodes", {})
    node = nodes.get(node_id)
    if node is None:
        # Fallback: match topics/<nn>-*.md
        topics_dir = vault / "topics"
        if topics_dir.is_dir():
            for p in sorted(topics_dir.glob("*.md")):
                if p.stem.split("-", 1)[0] == topic_num:
                    node = {"file": f"topics/{p.name}", "title": p.stem, "status": "unstarted", "checkpoint": "0/4", "depends_on": [], "contrasts_with": []}
                    break
    if node is None:
        print(dump_json({"error": f"Topic {node_id} not found"}), file=sys.stderr)
        return 1

    topic_path = vault / node["file"]
    if not topic_path.is_file():
        print(dump_json({"error": f"Topic file not found: {topic_path}"}), file=sys.stderr)
        return 1

    topic_text = read_utf8(topic_path)
    if args.section:
        sections_to_load = [args.section]
    elif active_cp <= 1:
        sections_to_load = ["L1-ANCHOR", "L2-PREREQS-AND-MOTIVATION"]
    elif active_cp == 2:
        sections_to_load = ["L3-FOUR-LAYER-THEORY", "L4-DERIVATION-AND-CODE"]
    else:
        sections_to_load = ["L5-WORKBOOK-AND-GRAPH"]

    slices: dict[str, str] = {}
    for sec in sections_to_load:
        try:
            slices[sec] = extract_section(topic_text, sec)
        except ValueError:
            pass

    # 3. Question queue if present
    queue_file = vault / "scratchpad" / f"queue-{topic_num}.json"
    queue_data: Any = None
    if queue_file.is_file():
        try:
            queue_data = json.loads(read_utf8(queue_file))
        except json.JSONDecodeError:
            queue_data = None

    # 4. 1-hop neighbors (depends_on & contrasts_with) L0-L1 anchors
    neighbor_ids: list[str] = []
    for key in ("depends_on", "contrasts_with"):
        for nid in node.get(key, []):
            if nid not in neighbor_ids:
                neighbor_ids.append(nid)

    neighbors: dict[str, str] = {}
    for nid in neighbor_ids[:4]:
        n_info = nodes.get(nid)
        if not n_info:
            continue
        n_path = vault / n_info.get("file", "")
        if n_path.is_file():
            try:
                l01 = extract_section(read_utf8(n_path), "L0-L1")
                neighbors[nid] = l01[:400] + ("..." if len(l01) > 400 else "")
            except ValueError:
                pass

    bundle = {
        "topic": node_id,
        "file": node.get("file", ""),
        "status": node.get("status", "unstarted"),
        "checkpoint": node.get("checkpoint", "0/4"),
        "active_subtopic": fields.get("active_topic", ""),
        "stage_cp": stage_cp,
        "last_invariant": fields.get("last_invariant", ""),
        "slices": slices,
        "queue": queue_data,
        "neighbors_l0_l1": neighbors,
    }
    print(dump_json(bundle))
    return 0


def cmd_flush(args: argparse.Namespace) -> int:
    vault = resolve_vault_path(args.vault_path)
    topic_num = str(args.topic).strip().zfill(2) if args.topic.isdigit() else str(args.topic).strip()
    topics_dir = vault / "topics"
    target_file: Path | None = None
    if topics_dir.is_dir():
        for p in sorted(topics_dir.glob("*.md")):
            if p.stem.split("-", 1)[0] == topic_num:
                target_file = p
                break
    if target_file is None:
        print(dump_json({"error": f"Topic {topic_num} not found in {topics_dir}"}), file=sys.stderr)
        return 1

    # 1. Update topic YAML status/checkpoint & Block 7 checkboxes
    t_lines = read_utf8(target_file).splitlines()
    in_fm = bool(t_lines and t_lines[0].strip() == "---")
    fm_done = False
    new_t_lines: list[str] = []
    for idx, line in enumerate(t_lines):
        if idx > 0 and in_fm and not fm_done:
            if line.strip() == "---":
                fm_done = True
            elif line.startswith("status:"):
                new_t_lines.append('status: "mastered"')
                continue
            elif line.startswith("checkpoint:"):
                new_t_lines.append('checkpoint: "4/4"')
                continue
        if fm_done or not in_fm:
            if re.match(r"^\s*-\s*\[\s\]\s*`?\[[1-4]/4\]`?", line):
                new_t_lines.append(re.sub(r"\[\s\]", "[x]", line, count=1))
                continue
        new_t_lines.append(line)
    target_file.write_text("\n".join(new_t_lines) + "\n", encoding="utf-8")

    # 2. Check off in 00-MOC-INDEX.md
    moc_path = vault / "00-MOC-INDEX.md"
    if moc_path.is_file():
        moc_lines = read_utf8(moc_path).splitlines()
        slug = target_file.stem
        new_moc = []
        for line in moc_lines:
            if f"[[topics/{slug}]]" in line or f"[[{slug}]]" in line:
                new_moc.append(re.sub(r"^(\s*-\s*)\[\s\]", r"\1[x]", line, count=1))
            else:
                new_moc.append(line)
        moc_path.write_text("\n".join(new_moc) + "\n", encoding="utf-8")

    # 3. Refresh 00-GRAPH.json and 00-SESSION-STATE.md
    graph = build_graph(vault)
    state_file = vault / "00-SESSION-STATE.md"
    if state_file.is_file():
        s_lines = read_utf8(state_file).splitlines()
        token_re = re.compile(rf"`\[[ x~]\]\s*{re.escape(topic_num)}`")
        out_s = []
        for line in s_lines:
            if args.note and line.lstrip().startswith("- **Last Verified Invariant:**"):
                out_s.append(f"- **Last Verified Invariant:** {args.note}")
            elif token_re.search(line):
                out_s.append(token_re.sub(f"`[x] {topic_num}`", line))
            else:
                out_s.append(line)
        state_file.write_text("\n".join(out_s[:59]) + "\n", encoding="utf-8")

    print(dump_json({"ok": True, "flushed": target_file.name, "graph_nodes": len(graph["nodes"])}))
    return 0


def heading_slug(heading_text: str) -> str:
    slug = heading_text.strip().lower()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"\s+", "-", slug)
    slug = re.sub(r"-+", "-", slug)
    return slug.strip("-")


def extract_headings(text: str) -> set[str]:
    slugs: set[str] = set()
    in_fence = False
    fence_char = ""
    for line in text.splitlines():
        fm = FENCE_RE.match(line)
        if fm:
            marker = fm.group(1)
            if not in_fence:
                in_fence = True
                fence_char = marker[0]
            elif marker[0] == fence_char:
                in_fence = False
            continue
        if in_fence:
            continue
        hm = HEADING_RE.match(line)
        if hm:
            raw_h = hm.group(1).strip()
            slugs.add(heading_slug(raw_h))
            slugs.add(raw_h.lower())
    return slugs


def strip_escaped_dollars(line: str) -> str:
    return line.replace(r"\$", "")


YAML_SPECIAL_RE = re.compile(r"[:\[\]{}|<>*&#?\\]")


def is_properly_quoted(val: str) -> bool:
    return (len(val) >= 2 and val[0] == '"' and val[-1] == '"') or (
        len(val) >= 2 and val[0] == "'" and val[-1] == "'"
    )


def has_unclosed_quote(val: str) -> bool:
    if not val:
        return False
    if val[0] == '"':
        # Must end with unescaped "
        if len(val) < 2 or val[-1] != '"':
            return True
        escapes = 0
        i = len(val) - 2
        while i >= 0 and val[i] == "\\":
            escapes += 1
            i -= 1
        return escapes % 2 == 1
    if val[0] == "'":
        return len(val) < 2 or val[-1] != "'"
    return False


def strip_yaml_comment(val: str) -> str:
    """Strip unquoted trailing `# comment` from a YAML value."""
    in_single = False
    in_double = False
    i = 0
    while i < len(val):
        ch = val[i]
        if ch == "\\" and in_double:
            i += 2
            continue
        if ch == '"' and not in_single:
            in_double = not in_double
        elif ch == "'" and not in_double:
            in_single = not in_single
        elif ch == "#" and not in_single and not in_double:
            if i == 0 or val[i - 1].isspace():
                return val[:i].rstrip()
        i += 1
    return val.strip()


def validate_yaml_frontmatter(
    rel_path: str, text: str, errors: list[dict[str, Any]]
) -> None:
    """Validate GitHub-compatible YAML frontmatter in pure stdlib Python."""
    raw_lines = text.lstrip("\ufeff").splitlines()
    if not raw_lines or raw_lines[0].strip() != "---":
        return

    end_idx = -1
    for i in range(1, len(raw_lines)):
        if raw_lines[i].strip() == "---":
            end_idx = i
            break
    if end_idx == -1:
        errors.append(
            {
                "file": rel_path,
                "line": 1,
                "type": "yaml_unclosed_frontmatter",
                "detail": "Opening '---' frontmatter block is not closed",
            }
        )
        return

    current_key: str | None = None
    expecting_list = False
    for offset, raw_line in enumerate(raw_lines[1:end_idx], start=2):
        if "\t" in raw_line[: len(raw_line) - len(raw_line.lstrip())]:
            errors.append(
                {
                    "file": rel_path,
                    "line": offset,
                    "type": "yaml_bad_indent",
                    "detail": "Tab character used in YAML indentation",
                }
            )
            continue

        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        if stripped.startswith("- ") or stripped == "-":
            if not expecting_list and current_key is None:
                errors.append(
                    {
                        "file": rel_path,
                        "line": offset,
                        "type": "yaml_syntax_error",
                        "detail": "List item without preceding YAML key",
                    }
                )
                continue
            item_val = strip_yaml_comment(stripped[1:].strip())
            if has_unclosed_quote(item_val):
                errors.append(
                    {
                        "file": rel_path,
                        "line": offset,
                        "type": "yaml_unclosed_quote",
                        "detail": f"Unclosed quote in list item: {item_val}",
                    }
                )
            elif item_val and not is_properly_quoted(item_val) and YAML_SPECIAL_RE.search(item_val):
                errors.append(
                    {
                        "file": rel_path,
                        "line": offset,
                        "type": "yaml_unquoted_special_char",
                        "detail": f"Unquoted special char in list item: {item_val}",
                    }
                )
            continue

        if raw_line[0].isspace():
            errors.append(
                {
                    "file": rel_path,
                    "line": offset,
                    "type": "yaml_bad_indent",
                    "detail": f"Unexpected indentation: {raw_line}",
                }
            )
            continue

        if ":" not in raw_line:
            errors.append(
                {
                    "file": rel_path,
                    "line": offset,
                    "type": "yaml_syntax_error",
                    "detail": f"Missing ':' in YAML mapping line: {stripped}",
                }
            )
            continue

        key_part, val_part = raw_line.split(":", 1)
        key = key_part.strip()
        current_key = key
        val = strip_yaml_comment(val_part.strip())
        if not val:
            expecting_list = True
            continue
        expecting_list = False

        if has_unclosed_quote(val):
            errors.append(
                {
                    "file": rel_path,
                    "line": offset,
                    "type": "yaml_unclosed_quote",
                    "detail": f"Unclosed quote for key '{key}'",
                }
            )
            continue

        if is_properly_quoted(val):
            continue

        if val.startswith("[") or val.endswith("]"):
            if not (val.startswith("[") and val.endswith("]")):
                errors.append(
                    {
                        "file": rel_path,
                        "line": offset,
                        "type": "yaml_malformed_list",
                        "detail": f"Malformed inline list for key '{key}': {val}",
                    }
                )
            continue

        if YAML_SPECIAL_RE.search(val) or (key == "checkpoint" and "/" in val):
            errors.append(
                {
                    "file": rel_path,
                    "line": offset,
                    "type": "yaml_unquoted_special_char",
                    "detail": f"Value for '{key}' must be double-quoted: {val}",
                }
            )


BARE_LATEX_CMD_NAMES = (
    r"theta|in|to|sum|hat|mathbf|implies|iff|le|ge|neq|approx|frac|sqrt|"
    r"lVert|rVert|lvert|rvert|mathbb|text|operatorname|prod|nabla|partial|"
    r"alpha|beta|gamma|sigma|lambda|vec|infty|cdot|times|leq|geq|mid|"
    r"forall|exists|Delta|eta|mu|epsilon|varepsilon|mathcal|tilde"
)

BARE_LATEX_CMD_RE = re.compile(rf"\\(?:{BARE_LATEX_CMD_NAMES})\b")
BARE_LATEX_EXPR_RE = re.compile(
    rf"\\(?:{BARE_LATEX_CMD_NAMES})\b(?:\s*\{{[^{{}}]*\}})*(?:[_^](?:\{{[^{{}}]*\}}|[A-Za-z0-9]))*"
)


def scan_details_in_file(
    rel_path: str, text: str, errors: list[dict[str, Any]]
) -> None:
    """Flag <details> / </details> blocks violating the Global <details> HTML Block Law."""
    lines = text.lstrip("\ufeff").splitlines()
    _, body_start = parse_frontmatter(text)
    in_fence = False
    fence_char = ""
    open_details_line: int | None = None

    for idx, raw_line in enumerate(lines, start=1):
        if idx <= body_start:
            continue
        fm = FENCE_RE.match(raw_line)
        if fm:
            marker = fm.group(1)
            if not in_fence:
                in_fence = True
                fence_char = marker[0]
            elif marker[0] == fence_char:
                in_fence = False
            continue
        if in_fence:
            continue

        # Ignore <details> / </details> inside inline code spans
        no_code = re.sub(r"`[^`\r\n]*`", "", raw_line)
        has_open = "<details>" in no_code
        has_close = "</details>" in no_code
        if not (has_open or has_close):
            continue

        stripped = raw_line.strip()
        if has_open:
            open_details_line = idx
            if raw_line != stripped or stripped != "<details>":
                errors.append(
                    {
                        "file": rel_path,
                        "line": idx,
                        "type": "details_block_format",
                        "detail": "<details> must be alone at column 0 on its own line",
                    }
                )
            elif idx > body_start + 1 and lines[idx - 2].strip() != "":
                errors.append(
                    {
                        "file": rel_path,
                        "line": idx,
                        "type": "details_block_format",
                        "detail": "Missing blank line immediately before <details>",
                    }
                )

            # Check next line is <summary>...</summary> followed by a blank line
            if idx >= len(lines) or not re.match(r"^<summary>.*</summary>$", lines[idx]):
                errors.append(
                    {
                        "file": rel_path,
                        "line": idx,
                        "type": "details_block_format",
                        "detail": "<summary>...</summary> must be alone at column 0 immediately after <details>",
                    }
                )
            elif idx + 1 >= len(lines) or lines[idx + 1].strip() != "":
                errors.append(
                    {
                        "file": rel_path,
                        "line": idx + 1,
                        "type": "details_block_format",
                        "detail": "Missing blank line immediately after </summary>",
                    }
                )

        if has_close:
            open_details_line = None
            if raw_line != stripped or stripped != "</details>":
                errors.append(
                    {
                        "file": rel_path,
                        "line": idx,
                        "type": "details_block_format",
                        "detail": "</details> must be alone at column 0 on its own line",
                    }
                )
            elif idx > body_start + 1 and lines[idx - 2].strip() != "":
                errors.append(
                    {
                        "file": rel_path,
                        "line": idx,
                        "type": "details_block_format",
                        "detail": "Missing blank line immediately before </details>",
                    }
                )

    if open_details_line is not None:
        errors.append(
            {
                "file": rel_path,
                "line": open_details_line,
                "type": "details_block_format",
                "detail": "Unclosed <details> block",
            }
        )


def scan_latex_in_file(
    rel_path: str, text: str, errors: list[dict[str, Any]]
) -> None:
    lines = text.lstrip("\ufeff").splitlines()
    _, body_start = parse_frontmatter(text)
    in_fence = False
    fence_char = ""
    in_display_math = False
    display_start_line = 0

    for idx, raw_line in enumerate(lines, start=1):
        if idx <= body_start:
            continue
        fm = FENCE_RE.match(raw_line)
        if fm:
            marker = fm.group(1)
            if not in_fence:
                in_fence = True
                fence_char = marker[0]
            elif marker[0] == fence_char:
                in_fence = False
            continue
        if in_fence:
            continue

        line = strip_escaped_dollars(raw_line)

        # 1. Backtick-wrapped LaTeX (ignore single-char `$` or `$$` meta-mentions)
        for m in re.finditer(r"`([^`\r\n]+)`", line):
            inner = m.group(1)
            if re.match(r"^\$\$(.+)\$\$$", inner) or (
                re.match(r"^\$([^$\s].*)\$$", inner) and not re.match(r"^\$[A-Za-z_][A-Za-z0-9_]*$", inner)
            ):
                errors.append(
                    {
                        "file": rel_path,
                        "line": idx,
                        "type": "backtick_latex",
                        "detail": f"Backtick-wrapped math: `{inner}`",
                    }
                )

        # Remove inline code spans before counting $ delimiters
        no_code = re.sub(r"`[^`\r\n]*`", "", line)

        # 2. Display math $$ toggling
        dd_count = no_code.count("$$")
        if dd_count % 2 == 1:
            if not in_display_math:
                in_display_math = True
                display_start_line = idx
            else:
                in_display_math = False
        no_dd = no_code.replace("$$", "")

        # 3. Single $ parity & trailing-space / bare LaTeX checks outside display math
        if not in_display_math:
            if no_dd.count("$") % 2 == 1:
                errors.append(
                    {
                        "file": rel_path,
                        "line": idx,
                        "type": "unmatched_dollar",
                        "detail": "Odd number of $ delimiters on line",
                    }
                )
            else:
                dollar_idxs = [i for i, ch in enumerate(no_dd) if ch == "$"]
                outside_parts: list[str] = []
                last_end = 0
                for p_i in range(0, len(dollar_idxs), 2):
                    s_pos = dollar_idxs[p_i]
                    e_pos = dollar_idxs[p_i + 1]
                    outside_parts.append(no_dd[last_end:s_pos])
                    inner_span = no_dd[s_pos + 1 : e_pos]
                    if inner_span and inner_span[-1].isspace():
                        errors.append(
                            {
                                "file": rel_path,
                                "line": idx,
                                "type": "latex_trailing_space",
                                "detail": f"Space before closing '$': ${inner_span}$",
                            }
                        )
                    last_end = e_pos + 1
                outside_parts.append(no_dd[last_end:])
                outside_math = " ".join(outside_parts)
                bare_m = BARE_LATEX_CMD_RE.search(outside_math)
                if bare_m:
                    errors.append(
                        {
                            "file": rel_path,
                            "line": idx,
                            "type": "bare_latex_command",
                            "detail": f"Bare LaTeX command outside $...$: {bare_m.group(0)}",
                        }
                    )

        # 4. Raw pipe inside math on Markdown table rows
        stripped = no_code.strip()
        if stripped.startswith("|") and stripped.endswith("|"):
            for math_span in re.finditer(r"\$([^$\r\n]+)\$", no_dd):
                inner_math = math_span.group(1)
                if "|" in inner_math:
                    errors.append(
                        {
                            "file": rel_path,
                            "line": idx,
                            "type": "table_pipe_in_math",
                            "detail": f"Raw '|' inside table math: ${inner_math}$",
                        }
                    )

    if in_display_math:
        errors.append(
            {
                "file": rel_path,
                "line": display_start_line,
                "type": "unclosed_display_math",
                "detail": "Unclosed $$ display math block",
            }
        )


def resolve_wikilink_target(
    raw_target: str, vault: Path, stem_map: dict[str, list[Path]]
) -> tuple[Path | None, str]:
    target = raw_target.split("|", 1)[0].strip()
    anchor = ""
    if "#" in target:
        target, anchor = target.split("#", 1)
        target = target.strip()
        anchor = anchor.strip()

    if not target:
        return None, anchor
    if target.startswith("../"):
        candidate = (vault / target).resolve()
        if candidate.suffix != ".md":
            candidate = candidate.with_suffix(".md")
        return (candidate if candidate.is_file() else None), anchor

    clean = target[:-3] if target.endswith(".md") else target
    direct = vault / f"{clean}.md"
    if direct.is_file():
        return direct, anchor

    base = Path(clean).name.lower()
    matches = stem_map.get(base, [])
    if len(matches) == 1:
        return matches[0], anchor
    return None, anchor


def cmd_verify(args: argparse.Namespace) -> int:
    vault = resolve_vault_path(args.vault_path)
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []

    all_md = [
        p for p in sorted(vault.rglob("*.md"))
        if "scratchpad" not in p.relative_to(vault).parts
    ]

    stem_map: dict[str, list[Path]] = {}
    heading_cache: dict[Path, set[str]] = {}
    text_cache: dict[Path, str] = {}

    for p in all_md:
        text = read_utf8(p)
        text_cache[p] = text
        heading_cache[p] = extract_headings(text)
        stem_map.setdefault(p.stem.lower(), []).append(p)

    # Build topic ID -> Path lookup
    topic_id_map: dict[str, Path] = {}
    topics_dir = vault / "topics"
    if topics_dir.is_dir():
        for p in sorted(topics_dir.glob("*.md")):
            meta, _ = parse_frontmatter(text_cache[p])
            tid = str(meta.get("id") or f"topic-{p.stem.split('-', 1)[0]}")
            topic_id_map[tid] = p
            topic_id_map[p.stem] = p

    atomic_dir = vault / "atomic"
    if atomic_dir.is_dir():
        for p in sorted(atomic_dir.glob("*.md")):
            topic_id_map[p.stem] = p

    broken_links = 0
    missing_sections = 0

    for p in all_md:
        rel_path = p.relative_to(vault).as_posix()
        text = text_cache[p]
        lines = text.splitlines()

        # YAML frontmatter, LaTeX & <details> HTML block checks
        validate_yaml_frontmatter(rel_path, text, errors)
        scan_latex_in_file(rel_path, text, errors)
        scan_details_in_file(rel_path, text, errors)
        # Check section markers for topics/*.md and atomic/*.md
        parts = p.relative_to(vault).parts
        if parts[0] in ("topics", "atomic"):
            found_sections = {
                m.group(1).strip().upper()
                for line in lines
                if (m := SECTION_RE.match(line))
            }
            for req in REQUIRED_TOPIC_SECTIONS:
                if req not in found_sections:
                    missing_sections += 1
                    errors.append(
                        {
                            "file": rel_path,
                            "line": 1,
                            "type": "missing_section_marker",
                            "detail": f"Missing <!-- SECTION: {req} -->",
                        }
                    )

        # Typed YAML edge, duplicate section numbers, Section 8 wikilinks & primary-source deep-links for topics/*.md
        if parts[0] == "topics":
            meta, _ = parse_frontmatter(text)
            for edge in TYPED_EDGE_FIELDS:
                vals = meta.get(edge, [])
                if isinstance(vals, str):
                    vals = [vals] if vals else []
                for val in vals:
                    v = str(val).strip()
                    if not v or v.startswith("<"):
                        continue
                    if v not in topic_id_map:
                        broken_links += 1
                        errors.append(
                            {
                                "file": rel_path,
                                "line": 1,
                                "type": "broken_typed_edge",
                                "detail": f"{edge} target not found: {v}",
                            }
                        )

            # Sequential ## <N>. section numbers (1..7) & unlinked Section 7 paths
            seen_sec_nums: dict[str, int] = {}
            sec_order: list[int] = []
            in_sec7 = False
            in_fence_t = False
            fence_char_t = ""
            for idx_t, raw_t in enumerate(lines, start=1):
                fm_t = FENCE_RE.match(raw_t)
                if fm_t:
                    mk = fm_t.group(1)
                    if not in_fence_t:
                        in_fence_t = True
                        fence_char_t = mk[0]
                    elif mk[0] == fence_char_t:
                        in_fence_t = False
                    continue
                if in_fence_t:
                    continue
                sec_m = re.match(r"^\s*##\s+(\d+)\.\s+", raw_t)
                if sec_m:
                    snum = sec_m.group(1)
                    if snum in seen_sec_nums:
                        errors.append(
                            {
                                "file": rel_path,
                                "line": idx_t,
                                "type": "duplicate_section_number",
                                "detail": f"Duplicate section number '## {snum}.' (first at line {seen_sec_nums[snum]})",
                            }
                        )
                    else:
                        seen_sec_nums[snum] = idx_t
                        sec_order.append(int(snum))
                    in_sec7 = snum == "7"
                if in_sec7 and re.match(
                    r"^\s*-\s*\*\*(?:Depends On|Unlocks|Contrasts With|Fixes Failure Of|Atomic):\*\*",
                    raw_t,
                ):
                    no_wiki = re.sub(r"\[\[[^\]]+\]\]", "", raw_t)
                    unlinked_m = re.search(r"\b(?:topics|atomic)/[A-Za-z0-9_.-]+", no_wiki)
                    if unlinked_m:
                        broken_links += 1
                        errors.append(
                            {
                                "file": rel_path,
                                "line": idx_t,
                                "type": "unlinked_graph_path",
                                "detail": f"Unlinked path in Section 7 (wrap in [[...]]): {unlinked_m.group(0)}",
                            }
                        )
            if sec_order and sec_order != list(range(1, len(sec_order) + 1)):
                errors.append(
                    {
                        "file": rel_path,
                        "line": 1,
                        "type": "non_sequential_section_numbers",
                        "detail": f"Section numbers must be sequential 1..N, got: {sec_order}",
                    }
                )

            if "Primary Sources & Deep Links" not in text:
                errors.append(
                    {
                        "file": rel_path,
                        "line": 1,
                        "type": "missing_primary_sources_table",
                        "detail": "Missing Section 8 'Primary Sources & Deep Links' table",
                    }
                )
            has_http = bool(re.search(r"https?://[^\s)>]+", text))
            has_res_anchor = bool(re.search(r"\[\[01-RESOURCES#[^\]]+\]\]", text))
            if not (has_http and has_res_anchor):
                errors.append(
                    {
                        "file": rel_path,
                        "line": 1,
                        "type": "missing_primary_source_deep_link",
                        "detail": "Topic must include clickable https:// primary-source URL and [[01-RESOURCES#...]] anchor",
                    }
                )

        # Wikilinks & Markdown links (outside fenced code blocks)
        in_fence = False
        fence_char = ""
        for idx, raw_line in enumerate(lines, start=1):
            fm = FENCE_RE.match(raw_line)
            if fm:
                marker = fm.group(1)
                if not in_fence:
                    in_fence = True
                    fence_char = marker[0]
                elif marker[0] == fence_char:
                    in_fence = False
                continue
            if in_fence:
                continue

            for wm in WIKILINK_RE.finditer(raw_line):
                raw_link = wm.group(1).strip()
                if raw_link.lower().startswith("none"):
                    broken_links += 1
                    errors.append(
                        {
                            "file": rel_path,
                            "line": idx,
                            "type": "placeholder_wikilink",
                            "detail": f"Placeholder wikilink: [[{raw_link}]]",
                        }
                    )
                    continue
                target_file, anchor = resolve_wikilink_target(raw_link, vault, stem_map)
                if raw_link.split("|", 1)[0].strip().startswith("#"):
                    target_file = p
                if target_file is None:
                    broken_links += 1
                    errors.append(
                        {
                            "file": rel_path,
                            "line": idx,
                            "type": "broken_wikilink",
                            "detail": f"Missing target for [[{raw_link}]]",
                        }
                    )
                elif anchor and (anchor.lower() not in heading_cache.get(target_file, set()) and heading_slug(anchor) not in heading_cache.get(target_file, set())):
                    broken_links += 1
                    errors.append(
                        {
                            "file": rel_path,
                            "line": idx,
                            "type": "broken_anchor",
                            "detail": f"Missing heading #{anchor} in {target_file.name}",
                        }
                    )

            for mm in MDLINK_RE.finditer(raw_line):
                href = mm.group(1).strip()
                if not href or href.startswith(("http://", "https://", "mailto:")):
                    continue
                path_part, _, anchor = href.partition("#")
                if not path_part:
                    if anchor and heading_slug(anchor) not in heading_cache.get(p, set()):
                        broken_links += 1
                        errors.append(
                            {
                                "file": rel_path,
                                "line": idx,
                                "type": "broken_anchor",
                                "detail": f"Missing local heading #{anchor}",
                            }
                        )
                    continue
                cand = (p.parent / path_part).resolve()
                if not cand.is_file():
                    broken_links += 1
                    errors.append(
                        {
                            "file": rel_path,
                            "line": idx,
                            "type": "broken_md_link",
                            "detail": f"Missing relative link target: {href}",
                        }
                    )
                elif anchor and cand in heading_cache and heading_slug(anchor) not in heading_cache[cand]:
                    broken_links += 1
                    errors.append(
                        {
                            "file": rel_path,
                            "line": idx,
                            "type": "broken_anchor",
                            "detail": f"Missing heading #{anchor} in {cand.name}",
                        }
                    )

    # Orphan check against 00-MOC-INDEX.md and 00-GRAPH.json
    moc_text = text_cache.get(vault / "00-MOC-INDEX.md", "")
    graph_files: set[str] = set()
    graph_path = vault / "00-GRAPH.json"
    if graph_path.is_file():
        try:
            gdata = json.loads(graph_path.read_text(encoding="utf-8"))
            graph_files = {
                str(n.get("file", "")) for n in gdata.get("nodes", {}).values()
            }
        except (OSError, json.JSONDecodeError):
            pass

    orphans = 0
    for folder_name in ("topics", "atomic"):
        folder = vault / folder_name
        if not folder.is_dir():
            continue
        for f in sorted(folder.glob("*.md")):
            rel_no_ext = f"{folder_name}/{f.stem}"
            rel_full = f"{folder_name}/{f.name}"
            in_moc = (rel_no_ext in moc_text) or (f.stem in moc_text)
            in_graph = (not graph_files) or (folder_name != "topics") or (rel_full in graph_files)
            if not in_moc or not in_graph:
                orphans += 1
                warnings.append(
                    {
                        "file": rel_full,
                        "line": 1,
                        "type": "orphan_file",
                        "detail": "Missing from 00-MOC-INDEX.md or 00-GRAPH.json",
                    }
                )

    broken_yaml = sum(1 for e in errors if e["type"].startswith("yaml_"))
    broken_details = sum(1 for e in errors if e["type"] == "details_block_format")
    broken_latex = sum(
        1
        for e in errors
        if e["type"] in {
            "backtick_latex",
            "unmatched_dollar",
            "table_pipe_in_math",
            "unclosed_display_math",
            "bare_latex_command",
            "latex_trailing_space",
        }
    )

    report = {
        "errors": errors,
        "warnings": warnings,
        "summary": {
            "files": len(all_md),
            "broken_yaml": broken_yaml,
            "broken_links": broken_links,
            "broken_latex": broken_latex,
            "broken_details": broken_details,
            "missing_sections": missing_sections,
            "orphans": orphans,
        },
    }
    print(dump_json(report))
    return 0


def _wrap_bare_latex_segment(seg: str) -> tuple[str, int]:
    """Wrap unambiguous bare LaTeX tokens in $...$ within a plain-text segment."""
    count = 0

    def _repl(m: re.Match[str]) -> str:
        nonlocal count
        count += 1
        return f"${m.group(0)}$"

    updated = BARE_LATEX_EXPR_RE.sub(_repl, seg)
    return updated, count


def fix_bare_latex_in_text(text: str) -> tuple[str, int]:
    """Wrap bare LaTeX commands outside $...$, $$...$$, code fences, and inline code."""
    has_bom = text.startswith("\ufeff")
    raw_lines = text.lstrip("\ufeff").splitlines()
    _, body_start = parse_frontmatter(text)
    in_fence = False
    fence_char = ""
    in_display_math = False
    fixes = 0
    out_lines: list[str] = []

    token_re = re.compile(r"(`[^`\r\n]*`|\$\$|\$[^$\r\n]*\$)")

    for idx, line in enumerate(raw_lines, start=1):
        if idx <= body_start:
            out_lines.append(line)
            continue
        fm = FENCE_RE.match(line)
        if fm:
            marker = fm.group(1)
            if not in_fence:
                in_fence = True
                fence_char = marker[0]
            elif marker[0] == fence_char:
                in_fence = False
            out_lines.append(line)
            continue
        if in_fence:
            out_lines.append(line)
            continue

        no_code = re.sub(r"`[^`\r\n]*`", "", line)
        dd_count = no_code.count("$$")
        if dd_count % 2 == 1:
            in_display_math = not in_display_math
            out_lines.append(line)
            continue
        if in_display_math:
            out_lines.append(line)
            continue

        parts = token_re.split(line)
        new_parts: list[str] = []
        for i, part in enumerate(parts):
            if i % 2 == 1:
                new_parts.append(part)
            else:
                fixed_part, n = _wrap_bare_latex_segment(part)
                fixes += n
                new_parts.append(fixed_part)
        out_lines.append("".join(new_parts))

    result = "\n".join(out_lines) + ("\n" if text.endswith("\n") else "")
    return ("\ufeff" + result if has_bom else result), fixes


def _ensure_blank_before(out: list[str]) -> None:
    if out and out[-1].strip() != "":
        out.append("")


def fix_details_in_text(text: str) -> tuple[str, int]:
    """Normalize <details> blocks to column 0 with required blank lines and clean bullets."""
    has_bom = text.startswith("\ufeff")
    raw_lines = text.lstrip("\ufeff").splitlines()
    _, body_start = parse_frontmatter(text)
    in_fence = False
    fence_char = ""
    in_details = False
    fixes = 0
    out: list[str] = []

    for idx, line in enumerate(raw_lines, start=1):
        if idx <= body_start:
            out.append(line)
            continue
        fm = FENCE_RE.match(line)
        if fm:
            marker = fm.group(1)
            if not in_fence:
                in_fence = True
                fence_char = marker[0]
            elif marker[0] == fence_char:
                in_fence = False
            out.append(line)
            continue
        if in_fence:
            out.append(line)
            continue

        no_code = re.sub(r"`[^`\r\n]*`", "", line)
        if "<details>" in no_code:
            before, after = line.split("<details>", 1)
            if before.strip():
                out.append(before.rstrip())
                fixes += 1
            elif line != line.lstrip():
                fixes += 1

            _ensure_blank_before(out)
            out.append("<details>")
            in_details = True

            # Handle <summary>...</summary> on same line or remaining content
            rem = after.strip()
            sum_m = re.match(r"^<summary>(.*?)</summary>(.*)$", rem)
            if sum_m:
                out.append(f"<summary>{sum_m.group(1).strip()}</summary>")
                out.append("")
                tail = sum_m.group(2).strip()
                if "</details>" in tail:
                    inner, post = tail.split("</details>", 1)
                    if inner.strip():
                        out.append(inner.strip())
                    out.append("")
                    out.append("</details>")
                    in_details = False
                    if post.strip():
                        out.append(post.strip())
                    fixes += 1
                elif tail:
                    out.append(tail)
                    fixes += 1
            elif rem:
                out.append(rem)
                fixes += 1
            continue

        if in_details:
            stripped = line.strip()
            # Remove stray empty bullets left behind inside broken <details> blocks
            if stripped in ("-", "*"):
                fixes += 1
                continue
            if "</details>" in no_code:
                before, after = line.split("</details>", 1)
                if before.strip():
                    out.append(before.strip())
                    fixes += 1
                _ensure_blank_before(out)
                out.append("</details>")
                in_details = False
                if line != "</details>":
                    fixes += 1
                if after.strip():
                    out.append(after.strip())
                continue

            # De-indent list-nested lines inside <details>
            deindented = line.lstrip(" ") if line.startswith("  ") else line
            if deindented != line:
                fixes += 1
            # Ensure blank line after standalone <summary>...</summary>
            if re.match(r"^<summary>.*</summary>$", stripped):
                out.append(stripped)
                out.append("")
                continue
            # Avoid duplicate consecutive blank lines right after </summary>
            if stripped == "" and out and out[-1] == "":
                continue
            out.append(deindented)
            continue

        out.append(line)

    result = "\n".join(out) + ("\n" if text.endswith("\n") else "")
    return ("\ufeff" + result if has_bom else result), fixes


def cmd_fix(args: argparse.Namespace) -> int:
    """Deterministically auto-repair <details> block formatting and bare LaTeX."""
    vault = resolve_vault_path(args.vault_path)
    all_md = [
        p for p in sorted(vault.rglob("*.md"))
        if "scratchpad" not in p.relative_to(vault).parts
    ]

    fixed_files: list[str] = []
    details_fixed_total = 0
    latex_fixed_total = 0

    for p in all_md:
        orig = read_utf8(p)
        updated, d_count = fix_details_in_text(orig)
        updated, l_count = fix_bare_latex_in_text(updated)
        if updated != orig:
            p.write_text(updated, encoding="utf-8")
            fixed_files.append(p.relative_to(vault).as_posix())
            details_fixed_total += d_count
            latex_fixed_total += l_count

    print(
        dump_json(
            {
                "vault_path": str(vault),
                "files_scanned": len(all_md),
                "files_modified": len(fixed_files),
                "modified_files": fixed_files,
                "details_fixes": details_fixed_total,
                "latex_fixes": latex_fixed_total,
            }
        )
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="vault_cli.py",
        description="Zero-token deterministic CLI for /teachme Markdown vaults.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_state = sub.add_parser("state", help="Print compact JSON session state summary.")
    p_state.add_argument("vault_path", nargs="?", default=None, help="Path to topic vault (optional).")
    p_state.set_defaults(func=cmd_state)

    p_graph = sub.add_parser("graph", help="Build/update 00-GRAPH.json from topics/*.md YAML.")
    p_graph.add_argument("vault_path", nargs="?", default=None, help="Path to topic vault (optional).")
    p_graph.set_defaults(func=cmd_graph)

    p_slice = sub.add_parser("slice", help="Extract a single <!-- SECTION: ... --> or L0-L1 slice.")
    p_slice.add_argument("markdown_file", help="Path to Markdown file.")
    p_slice.add_argument("--section", required=True, help="Section name (e.g. L0-L1, L1-ANCHOR, L3-FOUR-LAYER-THEORY).")
    p_slice.set_defaults(func=cmd_slice)

    p_tick = sub.add_parser("tick", help="Append checkpoint event to events.jsonl and update 00-SESSION-STATE.md.")
    p_tick.add_argument("vault_path", nargs="?", default=None, help="Path to topic vault (optional).")
    p_tick.add_argument("--topic", required=True, help="Subtopic number (e.g. 03).")
    p_tick.add_argument("--cp", required=True, type=int, choices=[1, 2, 3, 4], help="Checkpoint 1..4.")
    p_tick.add_argument("--status", required=True, choices=["pass", "retry"], help="Checkpoint outcome.")
    p_tick.add_argument("--stage", type=int, choices=[1, 2, 3], default=None, help="Optional depth stage 1..3.")
    p_tick.add_argument("--note", default="", help="Optional short invariant/misconception note.")
    p_tick.set_defaults(func=cmd_tick)

    p_verify = sub.add_parser("verify", help="Verify YAML, LaTeX, <details>, links, typed edges, section markers & orphans.")
    p_verify.add_argument("vault_path", nargs="?", default=None, help="Path to topic vault (optional).")
    p_verify.set_defaults(func=cmd_verify)

    p_fix = sub.add_parser("fix", help="Auto-repair <details> block formatting and unambiguous bare LaTeX.")
    p_fix.add_argument("vault_path", nargs="?", default=None, help="Path to topic vault (optional).")
    p_fix.set_defaults(func=cmd_fix)

    p_init = sub.add_parser("init", help="Scaffold vault dirs, 00-SESSION-STATE.md, 00-MOC-INDEX.md, topic stubs & 00-GRAPH.json.")
    p_init.add_argument("vault_path", help="Target topic vault directory.")
    p_init.add_argument("--topic", default="", help="Human-readable topic title.")
    p_init.add_argument("--title", default="", help="Alias for --topic.")
    p_init.add_argument("--subtopics", default="", help="Path to JSON file listing subtopic objects.")
    p_init.add_argument("--topics", default="", help="Comma-separated topic slugs fallback (e.g. 01-intro,02-core).")
    p_init.set_defaults(func=cmd_init)

    p_context = sub.add_parser("context", help="Return state + graph node + stage slice + queue + 1-hop L0-L1 anchors in one call.")
    p_context.add_argument("vault_path", nargs="?", default=None, help="Path to topic vault (optional).")
    p_context.add_argument("--topic", required=True, help="Subtopic number or ID (e.g. 03 or topic-03).")
    p_context.add_argument("--section", default=None, help="Optional section override.")
    p_context.set_defaults(func=cmd_context)

    p_flush = sub.add_parser("flush", help="Flush [4/4] mastery to topics/*.md, 00-MOC-INDEX.md & 00-GRAPH.json.")
    p_flush.add_argument("vault_path", nargs="?", default=None, help="Path to topic vault (optional).")
    p_flush.add_argument("--topic", required=True, help="Subtopic number (e.g. 01).")
    p_flush.add_argument("--note", default="", help="Optional verified invariant note.")
    p_flush.set_defaults(func=cmd_flush)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except FileNotFoundError as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
