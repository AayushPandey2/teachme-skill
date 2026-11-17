"""Structured Mermaid mindmap & relationship diagram generation and validation."""

from __future__ import annotations

import hashlib
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
from typing import Any

MERMAID_RESERVED_IDS = frozenset(
    {
        "end", "subgraph", "graph", "flowchart", "mindmap", "class",
        "classdef", "style", "linkstyle", "click", "call", "href", "default",
    }
)


def _safe_node_id(raw: str, idx: int) -> str:
    """Create a deterministic, keyword-safe Mermaid node identifier."""
    ascii_slug = re.sub(r"[^A-Za-z0-9_]+", "_", raw).strip("_").lower()
    if not ascii_slug:
        digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:6]
        ascii_slug = f"node_{digest}"
    cand = f"n_{idx}_{ascii_slug[:24]}"
    if cand.lower() in MERMAID_RESERVED_IDS:
        cand = f"node_{cand}"
    return cand


def escape_mermaid_label(text: str, for_mindmap: bool = False) -> str:
    """Escape quotes, brackets, braces, and newlines safely for Mermaid labels."""
    clean = " ".join(str(text).replace("\r", " ").replace("\n", " ").split()).strip()
    clean = clean.replace("`", "'")
    if for_mindmap:
        # Mindmap node labels with punctuation are safest wrapped in double quotes
        # with inner double quotes converted to single quotes.
        safe = clean.replace('"', "'")
        if any(ch in safe for ch in ("(", ")", "[", "]", "{", "}", ":", ";", "|", ">", "<", "#")):
            return f'"{safe}"'
        return safe or "Concept"
    # Flowchart quoted label: escape double quotes as #quot; to keep brackets/parens safe
    safe = clean.replace('"', "#quot;")
    return safe or "Concept"


def build_diagram_spec(
    topic: str,
    diagram_kind: str,
    direction: str,
    related_notes: list[dict[str, Any]],
    content: dict[str, Any] | None = None,
    proposal: dict[str, Any] | None = None,
    existing_note_paths: set[str] | None = None,
    max_nodes: int = 12,
    class_defs: list[str] | None = None,
    init_directives: list[str] | None = None,
) -> dict[str, Any]:
    """Build a deterministic structural graph/hierarchy spec before Mermaid rendering."""
    c = content or {}
    p = proposal or {}
    diagram_prop = p.get("diagram") if isinstance(p.get("diagram"), dict) else {}
    existing_set = existing_note_paths or {r["rel_path"] for r in related_notes if r.get("rel_path")}

    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    seen_labels: set[str] = set()

    def add_node(label: str, node_role: str, rel_path: str | None = None, group: str = "") -> str:
        clean_lbl = " ".join(str(label).split()).strip() or "Concept"
        key = clean_lbl.lower()
        for existing in nodes:
            if existing["label"].lower() == key:
                return existing["id"]
        if len(nodes) >= max_nodes:
            return ""
        nid = _safe_node_id(clean_lbl, len(nodes))
        seen_labels.add(key)
        nodes.append(
            {
                "id": nid,
                "label": clean_lbl,
                "node_role": node_role,  # "subject" | "existing_note" | "concept"
                "rel_path": rel_path if rel_path in existing_set else None,
                "group": group,
            }
        )
        return nid

    root_id = add_node(topic, node_role="subject", group="core")

    # 1. Explicit structural diagram proposal if provided by coding agent/user
    if isinstance(diagram_prop.get("nodes"), list) and diagram_prop["nodes"]:
        id_map: dict[str, str] = {}
        for item in diagram_prop["nodes"][: max_nodes - 1]:
            if isinstance(item, dict):
                lbl = str(item.get("label", "")).strip()
                role = str(item.get("node_role", "concept")).strip()
                rpath = item.get("rel_path")
                if rpath and rpath in existing_set:
                    role = "existing_note"
                elif role == "existing_note" and (not rpath or rpath not in existing_set):
                    role = "concept"
                nid = add_node(lbl, node_role=role, rel_path=rpath, group=str(item.get("group", "")))
                if nid and item.get("id"):
                    id_map[str(item["id"])] = nid
        for edge in diagram_prop.get("edges", []):
            if isinstance(edge, dict):
                src = id_map.get(str(edge.get("source", "")), root_id if str(edge.get("source", "")) == "root" else "")
                dst = id_map.get(str(edge.get("target", "")), root_id if str(edge.get("target", "")) == "root" else "")
                if src and dst and src != dst:
                    edges.append(
                        {
                            "source": src,
                            "target": dst,
                            "relation": str(edge.get("relation", "related")),
                            "label": str(edge.get("label", "")).strip(),
                        }
                    )

    # 2. Explicit prerequisites / contrasts / mechanism steps / concept branches from content
    elif diagram_kind == "mindmap":
        concepts = [str(x).strip() for x in c.get("concepts", []) if str(x).strip()]
        if concepts:
            for cpt in concepts[:5]:
                cid = add_node(cpt, node_role="concept", group="Core Concepts")
                if cid:
                    edges.append({"source": root_id, "target": cid, "relation": "part_of", "label": ""})

        for r in sorted(related_notes, key=lambda x: (-float(x.get("score", 0)), x.get("rel_path", "")))[:4]:
            r_title = r.get("title") or r.get("stem") or ""
            nid = add_node(r_title, node_role="existing_note", rel_path=r.get("rel_path"), group="Related Vault Notes")
            if nid:
                edges.append({"source": root_id, "target": nid, "relation": "related", "label": ""})

    else:
        # Flowchart / relationship graph:
        # Preserve true semantics — only mark prerequisite/contrasts_with/leads_to when explicitly provided;
        # otherwise label neutral vault connection ("related").
        prereqs = [str(x).strip() for x in c.get("prerequisites", []) if str(x).strip()]
        contrasts = [str(x).strip() for x in c.get("contrasts_with", []) if str(x).strip()]
        next_topics = [str(x).strip() for x in c.get("unlocks", []) if str(x).strip()]
        steps = [str(x).strip() for x in c.get("steps", []) if str(x).strip()]

        rel_by_title: dict[str, dict[str, Any]] = {}
        for r in related_notes:
            for key in (r.get("title", ""), r.get("stem", ""), r.get("rel_path", "")):
                if key:
                    rel_by_title[key.lower()] = r

        for pr in prereqs[:3]:
            match = rel_by_title.get(pr.lower())
            pid = add_node(
                match["title"] if match else pr,
                node_role="existing_note" if match else "concept",
                rel_path=match["rel_path"] if match else None,
                group="Prerequisites",
            )
            if pid:
                edges.append({"source": pid, "target": root_id, "relation": "prerequisite", "label": "prerequisite"})

        prev_step = root_id
        for stp in steps[:3]:
            sid = add_node(stp, node_role="concept", group="Mechanism")
            if sid:
                edges.append({"source": prev_step, "target": sid, "relation": "leads_to", "label": "step"})
                prev_step = sid

        for ct in contrasts[:2]:
            match = rel_by_title.get(ct.lower())
            cid = add_node(
                match["title"] if match else ct,
                node_role="existing_note" if match else "concept",
                rel_path=match["rel_path"] if match else None,
                group="Contrasts",
            )
            if cid:
                edges.append({"source": root_id, "target": cid, "relation": "contrasts_with", "label": "contrasts"})

        for nt in next_topics[:2]:
            match = rel_by_title.get(nt.lower())
            nid = add_node(
                match["title"] if match else nt,
                node_role="existing_note" if match else "concept",
                rel_path=match["rel_path"] if match else None,
                group="Applications",
            )
            if nid:
                edges.append({"source": root_id, "target": nid, "relation": "leads_to", "label": "unlocks"})

        # Add remaining top related notes neutrally (do NOT fabricate prerequisite arrows from keyword overlap!)
        for r in sorted(related_notes, key=lambda x: (-float(x.get("score", 0)), x.get("rel_path", "")))[:4]:
            r_title = r.get("title") or r.get("stem") or ""
            if r_title.lower() in seen_labels:
                continue
            nid = add_node(r_title, node_role="existing_note", rel_path=r.get("rel_path"), group="Related Notes")
            if nid:
                edges.append({"source": root_id, "target": nid, "relation": "related", "label": "related"})

    truncated = (len(related_notes) + len(c.get("concepts", [])) + len(c.get("steps", []))) > max_nodes
    return {
        "kind": diagram_kind,
        "direction": direction,
        "title": topic,
        "nodes": nodes,
        "edges": edges,
        "class_defs": list(class_defs or [])[:4],
        "init_directives": list(init_directives or [])[:1],
        "max_nodes": max_nodes,
        "truncated_into_views": truncated,
    }


def render_mermaid_from_spec(
    spec: dict[str, Any],
    mindmap_supported: bool = True,
) -> dict[str, Any]:
    """Render a structural diagram spec into valid Mermaid markdown with fallback if needed."""
    kind = spec.get("kind", "flowchart")
    fallback_used = False
    if kind == "mindmap" and not mindmap_supported:
        kind = "flowchart"
        fallback_used = True

    direction = spec.get("direction", "TD")
    if direction not in ("TD", "TB", "LR", "RL", "BT"):
        direction = "TD"

    nodes: list[dict[str, Any]] = spec.get("nodes", [])
    edges: list[dict[str, Any]] = spec.get("edges", [])
    node_map = {n["id"]: n for n in nodes}

    lines: list[str] = []
    for idir in spec.get("init_directives", []):
        lines.append(idir)

    if kind == "mindmap":
        lines.append("mindmap")
        root_node = next((n for n in nodes if n.get("node_role") == "subject"), nodes[0] if nodes else None)
        if root_node:
            root_lbl = escape_mermaid_label(root_node["label"], for_mindmap=True)
            lines.append(f"  root(({root_lbl}))" if not root_lbl.startswith('"') else f"  root({root_lbl})")
            children_by_parent: dict[str, list[dict[str, Any]]] = {}
            attached: set[str] = {root_node["id"]}
            for e in edges:
                src, dst = e.get("source"), e.get("target")
                if src in node_map and dst in node_map and dst not in attached:
                    children_by_parent.setdefault(src, []).append(node_map[dst])
                    attached.add(dst)
            for n in nodes:
                if n["id"] not in attached:
                    children_by_parent.setdefault(root_node["id"], []).append(n)
                    attached.add(n["id"])

            def _emit_children(parent_id: str, depth: int) -> None:
                indent = "  " * depth
                for child in children_by_parent.get(parent_id, []):
                    lbl = escape_mermaid_label(child["label"], for_mindmap=True)
                    lines.append(f"{indent}{lbl}")
                    _emit_children(child["id"], depth + 1)

            # Group by group label if multiple groups exist
            groups: dict[str, list[dict[str, Any]]] = {}
            direct_children = children_by_parent.get(root_node["id"], [])
            for ch in direct_children:
                grp = ch.get("group") or ""
                groups.setdefault(grp, []).append(ch)
            if len([g for g in groups if g]) >= 2:
                for grp_name, grp_nodes in groups.items():
                    if grp_name:
                        lines.append(f"    {escape_mermaid_label(grp_name, for_mindmap=True)}")
                        for ch in grp_nodes:
                            lines.append(f"      {escape_mermaid_label(ch['label'], for_mindmap=True)}")
                    else:
                        for ch in grp_nodes:
                            lines.append(f"    {escape_mermaid_label(ch['label'], for_mindmap=True)}")
            else:
                _emit_children(root_node["id"], 2)
    else:
        lines.append(f"flowchart {direction}")
        for n in nodes:
            lbl = escape_mermaid_label(n["label"], for_mindmap=False)
            role = n.get("node_role", "concept")
            if role == "subject":
                lines.append(f'  {n["id"]}(["{lbl}"])')
            elif role == "existing_note":
                lines.append(f'  {n["id"]}["{lbl}"]')
            else:
                lines.append(f'  {n["id"]}(("{lbl}"))' if len(lbl) < 20 else f'  {n["id"]}["{lbl}"]')

        for e in edges:
            src, dst = e.get("source"), e.get("target")
            if src not in node_map or dst not in node_map:
                continue
            rel = e.get("relation", "related")
            elbl = escape_mermaid_label(e.get("label", ""), for_mindmap=False) if e.get("label") else ""
            if rel == "contrasts_with":
                arrow = f"-. {elbl} .->" if elbl else "-.->"
            elif rel == "related":
                arrow = f"--- |{elbl}|" if elbl else "---"
                lines.append(f"  {src} {arrow} {dst}")
                continue
            else:
                arrow = f"-->|{elbl}|" if elbl else "-->"
            lines.append(f"  {src} {arrow} {dst}")

        for cd in spec.get("class_defs", []):
            lines.append(f"  {cd}")

    mermaid_code = "\n".join(lines)
    return {
        "rendered_type": kind,
        "fallback_used": fallback_used,
        "code": mermaid_code,
    }


def validate_mermaid_syntax(mermaid_code: str) -> dict[str, Any]:
    """Validate Mermaid syntax using mmdc CLI if available, else thorough structural checks."""
    errors: list[str] = []
    warnings: list[str] = []
    lines = [ln for ln in mermaid_code.splitlines() if ln.strip() and not ln.strip().startswith("%%")]
    if not lines:
        return {
            "valid": False,
            "validation_mode": "structural_only",
            "parser_available": False,
            "limitation": "Empty Mermaid diagram",
            "errors": ["Empty Mermaid diagram"],
            "warnings": [],
        }

    header = lines[0].strip()
    is_mindmap = header.lower() == "mindmap"
    is_flowchart = bool(re.match(r"^(?:flowchart|graph)\s+(?:TD|TB|LR|RL|BT)\b", header, re.IGNORECASE))
    if not (is_mindmap or is_flowchart):
        errors.append(f"Unsupported or missing Mermaid header: '{header}'")

    if len(lines) < 2:
        errors.append("Diagram has no nodes or body lines")

    subgraph_depth = 0
    prev_indent = 0
    for idx, raw in enumerate(lines[1:], start=2):
        if "\t" in raw[: len(raw) - len(raw.lstrip())]:
            errors.append(f"Line {idx}: Tab indentation is invalid in Mermaid")
        stripped = raw.strip()
        if stripped.startswith("classDef ") or stripped.startswith("style ") or stripped.startswith("linkStyle "):
            continue
        if stripped.count('"') % 2 == 1:
            errors.append(f"Line {idx}: Unclosed double quote")

        if is_mindmap:
            indent = len(raw) - len(raw.lstrip(" "))
            if indent == 0:
                errors.append(f"Line {idx}: Mindmap body node must be indented under root")
            if indent - prev_indent > 4 and idx > 2:
                warnings.append(f"Line {idx}: Large indentation jump in mindmap")
            prev_indent = indent
            if "-->" in stripped or "-.->" in stripped:
                errors.append(f"Line {idx}: Edge arrow syntax is invalid inside mindmap")
        else:
            if stripped.lower().startswith("subgraph "):
                subgraph_depth += 1
                continue
            if stripped.lower() == "end":
                subgraph_depth -= 1
                if subgraph_depth < 0:
                    errors.append(f"Line {idx}: Unexpected 'end' without matching 'subgraph'")
                continue
            # Check balanced brackets outside quoted strings
            unquoted = re.sub(r'"[^"]*"', "", stripped)
            for op, cl in (("[", "]"), ("(", ")"), ("{", "}")):
                if unquoted.count(op) != unquoted.count(cl):
                    errors.append(f"Line {idx}: Unbalanced '{op}{cl}' delimiters")

    if subgraph_depth != 0:
        errors.append("Unclosed 'subgraph' block")

    # Attempt real parser/render check via mmdc only if installed on PATH
    mmdc = shutil.which("mmdc")
    if mmdc and not errors:
        try:
            with tempfile.TemporaryDirectory(prefix="teachme_mmd_") as tdir:
                in_file = Path(tdir) / "diagram.mmd"
                out_file = Path(tdir) / "diagram.svg"
                in_file.write_text(mermaid_code, encoding="utf-8")
                proc = subprocess.run(
                    [mmdc, "-i", str(in_file), "-o", str(out_file)],
                    capture_output=True,
                    text=True,
                    timeout=10,
                    check=False,
                )
                if proc.returncode != 0:
                    errors.append(f"mmdc parser failed: {(proc.stderr or proc.stdout).strip()[:200]}")
                return {
                    "valid": len(errors) == 0,
                    "validation_mode": "cli_render",
                    "parser_available": True,
                    "limitation": None,
                    "errors": errors,
                    "warnings": warnings,
                }
        except (OSError, subprocess.SubprocessError) as exc:
            warnings.append(f"mmdc check failed to invoke ({exc}); fell back to structural check")

    return {
        "valid": len(errors) == 0,
        "validation_mode": "structural_only",
        "parser_available": False,
        "limitation": "Mermaid CLI (mmdc) not installed; performed deterministic structural syntax validation only.",
        "errors": errors,
        "warnings": warnings,
    }


def wrap_generated_mermaid_block(mermaid_code: str, diagram_id: str = "overview") -> str:
    """Wrap generated Mermaid code in non-destructive generated-region markers."""
    return "\n".join(
        [
            f"<!-- teachme:mermaid:start id={diagram_id} -->",
            "```mermaid",
            mermaid_code.strip(),
            "```",
            "<!-- teachme:mermaid:end -->",
        ]
    )


def merge_generated_mermaid_into_note(
    existing_text: str,
    wrapped_block: str,
    diagram_id: str = "overview",
) -> dict[str, Any]:
    """Safely insert or update ONLY a TeachMe-generated Mermaid block; never replace user diagrams."""
    marker_re = re.compile(
        rf"<!--\s*teachme:mermaid:start\s+id={re.escape(diagram_id)}\s*-->[\s\S]*?<!--\s*teachme:mermaid:end\s*-->",
        re.MULTILINE,
    )
    if marker_re.search(existing_text):
        updated = marker_re.sub(wrapped_block, existing_text, count=1)
        return {
            "action": "updated_generated_region",
            "text": updated,
            "preserved_user_diagrams": True,
        }

    # Check if user already authored a Mermaid diagram outside TeachMe markers
    has_user_mermaid = bool(re.search(r"^\s*```mermaid\b", existing_text, re.MULTILINE))
    return {
        "action": "append_new_diagram",
        "text": existing_text,
        "preserved_user_diagrams": has_user_mermaid,
        "note": "Existing user-authored Mermaid diagram left untouched." if has_user_mermaid else "",
    }


def plan_mermaid_diagram(
    topic: str,
    profile: dict[str, Any],
    target_folder: str,
    related_notes: list[dict[str, Any]],
    content: dict[str, Any] | None = None,
    proposal: dict[str, Any] | None = None,
    mermaid_mode: str = "auto",
    mindmap_supported: bool = True,
    note_role: str = "note",
) -> dict[str, Any]:
    """Decide whether and how to generate a Mermaid diagram for a note or MOC."""
    mode = (mermaid_mode or "auto").strip().lower()
    if mode == "none":
        return {
            "include_diagram": False,
            "diagram_type": None,
            "fallback_used": False,
            "reason": "Mermaid generation disabled by option",
            "spec": None,
            "rendered_block": "",
            "validation": None,
            "placement_heading": "",
            "confidence": "high",
        }

    c = content or {}
    p = proposal or {}
    m_conv = profile.get("mermaid_conventions", {})
    folder_info = profile.get("folders", {}).get(target_folder or ".", {})
    folder_m_types: list[str] = folder_info.get("mermaid_types", [])
    granularity = folder_info.get("style", {}).get("note_granularity") or profile.get("global_style", {}).get("note_granularity", "balanced")

    has_explicit_structure = bool(
        p.get("diagram")
        or c.get("steps")
        or c.get("prerequisites")
        or c.get("contrasts_with")
        or len(c.get("concepts", [])) >= 2
    )
    has_enough_links = len(related_notes) >= 2

    if mode == "auto" and not has_explicit_structure and not has_enough_links:
        return {
            "include_diagram": False,
            "diagram_type": None,
            "fallback_used": False,
            "reason": "Insufficient verified relationships or structural hierarchy to justify a diagram",
            "spec": None,
            "rendered_block": "",
            "validation": None,
            "placement_heading": "",
            "confidence": "high",
        }

    # Skip diagram on tiny atomic notes unless vault uses Mermaid there or explicitly requested
    if mode == "auto" and granularity == "atomic" and not folder_m_types and not has_explicit_structure and len(related_notes) < 3:
        return {
            "include_diagram": False,
            "diagram_type": None,
            "fallback_used": False,
            "reason": "Atomic note granularity without explicit hierarchy; keeping note concise",
            "spec": None,
            "rendered_block": "",
            "validation": None,
            "placement_heading": "",
            "confidence": "medium",
        }

    # Choose diagram type based on educational value and vault conventions
    if mode in ("mindmap", "flowchart"):
        chosen_kind = mode
    elif note_role == "moc" or (len(c.get("concepts", [])) >= 2 and not c.get("steps") and not c.get("prerequisites")):
        chosen_kind = "mindmap"
    elif folder_m_types:
        chosen_kind = "mindmap" if folder_m_types[0] == "mindmap" and not (c.get("steps") or c.get("prerequisites")) else "flowchart"
    elif m_conv.get("preferred_types"):
        pref = m_conv["preferred_types"][0]
        chosen_kind = pref if pref in ("mindmap", "flowchart") else "flowchart"
    else:
        chosen_kind = "flowchart"

    direction = m_conv.get("preferred_direction") or "TD"
    spec = build_diagram_spec(
        topic=topic,
        diagram_kind=chosen_kind,
        direction=direction,
        related_notes=related_notes,
        content=c,
        proposal=p,
        class_defs=m_conv.get("reusable_class_defs", []),
        init_directives=m_conv.get("init_directives", []),
    )

    if len(spec["nodes"]) < 2:
        return {
            "include_diagram": False,
            "diagram_type": None,
            "fallback_used": False,
            "reason": "Fewer than 2 nodes in diagram spec",
            "spec": spec,
            "rendered_block": "",
            "validation": None,
            "placement_heading": "",
            "confidence": "high",
        }

    rendered = render_mermaid_from_spec(spec, mindmap_supported=mindmap_supported)
    validation = validate_mermaid_syntax(rendered["code"])
    wrapped = wrap_generated_mermaid_block(rendered["code"], diagram_id="concept-map" if rendered["rendered_type"] == "mindmap" else "relationship-map")

    common_heads = m_conv.get("common_headings", [])
    placement_heading = common_heads[0].title() if common_heads else ("Concept Map" if rendered["rendered_type"] == "mindmap" else "Knowledge & Dependency Map")

    return {
        "include_diagram": validation["valid"],
        "diagram_type": rendered["rendered_type"],
        "requested_type": chosen_kind,
        "fallback_used": rendered["fallback_used"],
        "reason": (
            f"Generated {rendered['rendered_type']} diagram ({len(spec['nodes'])} nodes, {len(spec['edges'])} edges)"
            + (" via flowchart fallback (mindmap unavailable)" if rendered["fallback_used"] else "")
        ),
        "spec": spec,
        "mermaid_code": rendered["code"],
        "rendered_block": wrapped,
        "validation": validation,
        "placement_heading": placement_heading,
        "confidence": "high" if validation["valid"] else "low",
    }
