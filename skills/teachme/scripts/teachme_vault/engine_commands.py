"""CLI subcommand handlers for modality routing, terminal graphs, simulations, adaptive quizzing, and media retrieval."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

from .adaptive_quiz import evaluate_learner_response, select_question_plan
from .evidence import derive_objective_evidence, normalize_objectives_list
from .media_retrieval import select_and_prepare_image
from .modality_router import select_teaching_modality
from .models import expand_path, read_text_safe
from .scheduler import get_due_reviews, load_review_state
from .simulations import list_simulation_templates, run_interactive_cli, run_non_interactive_demo
from .state_store import (
    load_curriculum,
    load_events,
    load_mission,
    normalize_topic_num,
    resolve_session_dir,
)
from .terminal_caps import detect_host_capabilities, detect_terminal_capabilities
from .terminal_graph import (
    render_bar_chart,
    render_function_graph,
    render_histogram,
    render_optimization_trace,
    render_xy_graph,
)


def _dump_json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, separators=(",", ":"))


def _parse_param_pairs(raw_pairs: list[str] | None) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for item in raw_pairs or []:
        if "=" not in item:
            raise ValueError(f"Invalid --param {item!r}; expected key=value")
        k, v = item.split("=", 1)
        key = k.strip()
        val_str = v.strip()
        if not key:
            raise ValueError(f"Empty parameter name in {item!r}")
        if key == "array":
            out[key] = val_str
            continue
        try:
            if val_str.isdigit() or (val_str.startswith("-") and val_str[1:].isdigit()):
                out[key] = int(val_str)
            else:
                out[key] = float(val_str)
        except ValueError:
            out[key] = val_str
    return out


def cmd_capabilities(args: argparse.Namespace) -> int:
    t_caps = detect_terminal_capabilities(
        width=args.width,
        height=args.height,
        is_tty=True if args.tty else None,
        interactive=False if args.non_interactive else None,
    )
    if args.no_color:
        t_caps["no_color"] = True
        t_caps["color_support"] = "none"
    h_caps = detect_host_capabilities(
        available_tools={
            "web_search": bool(args.web_search),
            "source_fetch": bool(args.web_search),
            "image_search": bool(args.image_search),
            "image_inspect": bool(args.image_inspect),
            "python_exec": not bool(args.no_python),
            "browser": bool(args.browser),
        },
        terminal_caps=t_caps,
    )
    print(_dump_json(h_caps))
    return 0


def cmd_route_modality(args: argparse.Namespace) -> int:
    topic_title = (args.title or "").strip()
    obj_desc = (args.desc or "").strip()
    obj_id = (args.objective or "").strip()
    prof_status = "untested"
    transfer_status = "untested"
    prereq_states: dict[str, Any] = {}
    recent_events: list[dict[str, Any]] = []
    is_due = bool(args.due)

    if args.vault_path or args.session or (args.topic and not obj_desc):
        sess_dir = resolve_session_dir(args.vault_path, session_slug=args.session)
        curriculum = load_curriculum(sess_dir)
        mission = load_mission(sess_dir)
        prereq_states = dict(mission.get("prerequisites") or {})
        all_events = load_events(sess_dir)

        if args.topic:
            t_num = normalize_topic_num(args.topic)
            node_id = f"topic-{t_num}"
            cnode = (curriculum.get("nodes") or {}).get(node_id) or {}
            topic_title = topic_title or str(cnode.get("title") or node_id)
            t_events = [e for e in all_events if normalize_topic_num(str(e.get("topic", ""))) == t_num]
            objs = normalize_objectives_list(node_id, cnode) if cnode else []
            target_obj = None
            if obj_id:
                target_obj = next((o for o in objs if o["id"] == obj_id), None)
            elif objs:
                target_obj = objs[0]
            if target_obj is not None:
                obj_id = target_obj["id"]
                obj_desc = obj_desc or str(target_obj["description"])
                oevs = [e for e in t_events if e.get("objective_id") == obj_id]
                if objs and target_obj["id"] == objs[0]["id"]:
                    oevs.extend(e for e in t_events if not e.get("objective_id"))
                derived = derive_objective_evidence(
                    target_obj,
                    oevs,
                    node_status=str(cnode.get("status") or "unstarted"),
                    node_checkpoint=str(cnode.get("checkpoint") or "0/4"),
                )
                prof_status = derived["proficiency"]["status"]
                transfer_status = derived["proficiency"]["transfer"]["status"]
                recent_events = oevs[-6:]
            else:
                recent_events = t_events[-6:]

        if not is_due and obj_id:
            rev_store = load_review_state(sess_dir)
            due_items = get_due_reviews(curriculum, all_events, rev_store, now=args.now, limit=20)
            is_due = any(d["objective_id"] == obj_id for d in due_items)

        if args.time_budget is None and mission.get("time_budget_minutes") is not None:
            args.time_budget = int(mission["time_budget_minutes"])

    t_caps = detect_terminal_capabilities(
        width=args.width,
        interactive=False if args.non_interactive else None,
    )
    if args.no_color:
        t_caps["no_color"] = True
    h_caps = detect_host_capabilities(
        available_tools={
            "image_search": bool(args.image_search),
            "image_inspect": bool(args.image_inspect),
            "web_search": bool(args.web_search),
        },
        terminal_caps=t_caps,
    )

    decision = select_teaching_modality(
        objective_desc=obj_desc or topic_title,
        topic_title=topic_title,
        objective_id=obj_id,
        concept_type=args.concept_type or "",
        proficiency_status=prof_status,
        transfer_status=transfer_status,
        prerequisite_states=prereq_states,
        recent_events=recent_events,
        is_due_review=is_due,
        difficulty=args.difficulty,
        abstraction=args.abstraction,
        time_budget_minutes=args.time_budget,
        explicit_preference=args.preference,
        last_modality=args.last_modality or "",
        host_capabilities=h_caps,
    )
    print(_dump_json(decision))
    return 0


def _load_json_arg(raw_json: str | None, file_path: str | None) -> Any:
    if raw_json:
        return json.loads(raw_json)
    if file_path:
        p = expand_path(file_path)
        if not p.is_file():
            raise FileNotFoundError(f"Data file not found: {p}")
        return json.loads(read_text_safe(p))
    return None


def cmd_graph_render(args: argparse.Namespace) -> int:
    kind = args.kind
    no_color = True if args.no_color else None
    data = _load_json_arg(args.data_json, args.data_file)

    if kind == "function":
        if not args.expr:
            raise ValueError("--expr is required for --kind function")
        res = render_function_graph(
            args.expr,
            args.x_min,
            args.x_max,
            samples=args.samples,
            title=args.title or "",
            x_label=args.x_label or "x",
            y_label=args.y_label or "y",
            unit_x=args.unit_x or "",
            unit_y=args.unit_y or "",
            width=args.width,
            height=args.height,
            charset=args.charset,
            no_color=no_color,
        )
    elif kind in ("line", "scatter"):
        if not isinstance(data, list):
            raise ValueError("--data-json or --data-file must provide a JSON list of series")
        res = render_xy_graph(
            data,
            kind=kind,
            title=args.title or "",
            x_label=args.x_label or "x",
            y_label=args.y_label or "y",
            unit_x=args.unit_x or "",
            unit_y=args.unit_y or "",
            width=args.width,
            height=args.height,
            charset=args.charset,
            no_color=no_color,
        )
    elif kind == "bar":
        if not isinstance(data, list):
            raise ValueError("--data-json or --data-file must provide a JSON list of {label, value} or [label, value]")
        res = render_bar_chart(
            data,
            title=args.title or "",
            value_label=args.y_label or "value",
            unit=args.unit_y or "",
            width=args.width,
            charset=args.charset,
            no_color=no_color,
        )
    elif kind == "histogram":
        if not isinstance(data, list):
            raise ValueError("--data-json or --data-file must provide a JSON list of numbers")
        res = render_histogram(
            data,
            bins=args.bins,
            title=args.title or "Histogram",
            x_label=args.x_label or "value",
            unit=args.unit_x or "",
            width=args.width,
            charset=args.charset,
            no_color=no_color,
        )
    elif kind == "optimization_trace":
        if not args.expr:
            raise ValueError("--expr is required for --kind optimization_trace")
        iterates = data if isinstance(data, list) else []
        res = render_optimization_trace(
            args.expr,
            iterates,
            x_min=args.x_min if args.x_min is not None else None,
            x_max=args.x_max if args.x_max is not None else None,
            title=args.title or "Optimization Trace",
            x_label=args.x_label or "w",
            y_label=args.y_label or "L(w)",
            width=args.width,
            height=args.height,
            charset=args.charset,
            no_color=no_color,
        )
    else:
        raise ValueError(f"Unsupported graph kind: {kind}")

    if args.format == "text":
        print(res.get("text", ""))
    else:
        print(_dump_json(res))
    return 0 if res.get("ok", True) else 1


def cmd_simulate(args: argparse.Namespace) -> int:
    if args.list:
        print(_dump_json({"templates": list_simulation_templates()}))
        return 0
    if not args.template:
        raise ValueError("--template is required unless --list is specified")

    params = _parse_param_pairs(args.param)
    t_caps = detect_terminal_capabilities(
        width=args.width,
        interactive=False if args.non_interactive else None,
    )
    if args.no_color:
        t_caps["no_color"] = True

    if args.interactive and not args.non_interactive:
        res = run_interactive_cli(
            args.template,
            params=params,
            terminal_caps=t_caps,
            force_non_interactive=False,
            demo_steps=args.steps,
        )
        if args.format == "json":
            print(_dump_json(res))
        return 0

    res = run_non_interactive_demo(
        args.template,
        steps=args.steps,
        params=params,
        prediction=args.predict,
        width=t_caps["width"],
        no_color=t_caps["no_color"],
        charset=args.charset,
    )
    if args.format == "text":
        print(res["rendered"])
    else:
        print(_dump_json(res))
    return 0


def cmd_quiz_plan(args: argparse.Namespace) -> int:
    target_obj: dict[str, Any] = {
        "id": args.objective or "obj-01",
        "proficiency": {
            "status": args.proficiency or "untested",
            "independent_successes": int(args.indep or 0),
            "assisted_successes": int(args.assist or 0),
            "failures": int(args.failures or 0),
            "retention": {"status": "untested"},
            "transfer": {"status": "untested"},
        },
    }
    recent_events: list[dict[str, Any]] = []
    due_item: dict[str, Any] | None = {"objective_id": target_obj["id"]} if args.due else None

    if args.vault_path or args.session:
        sess_dir = resolve_session_dir(args.vault_path, session_slug=args.session)
        curriculum = load_curriculum(sess_dir)
        all_events = load_events(sess_dir)
        t_num = normalize_topic_num(args.topic or "01")
        node_id = f"topic-{t_num}"
        cnode = (curriculum.get("nodes") or {}).get(node_id)
        if cnode:
            objs = normalize_objectives_list(node_id, cnode)
            picked = next((o for o in objs if o["id"] == args.objective), objs[0])
            t_events = [e for e in all_events if normalize_topic_num(str(e.get("topic", ""))) == t_num]
            oevs = [e for e in t_events if e.get("objective_id") == picked["id"]]
            if picked["id"] == objs[0]["id"]:
                oevs.extend(e for e in t_events if not e.get("objective_id"))
            target_obj = derive_objective_evidence(
                picked,
                oevs,
                node_status=str(cnode.get("status") or "unstarted"),
                node_checkpoint=str(cnode.get("checkpoint") or "0/4"),
            )
            recent_events = oevs[-6:]
            if due_item is None:
                rev_store = load_review_state(sess_dir)
                due_list = get_due_reviews(curriculum, all_events, rev_store, now=args.now, limit=20)
                due_item = next((d for d in due_list if d["objective_id"] == picked["id"]), None)

    plan = select_question_plan(
        target_obj,
        recent_events=recent_events,
        due_item=due_item,
        requested_tier=args.tier,
        concept_type=args.concept_type or "",
        learner_request=args.learner_request or "",
    )
    print(_dump_json(plan))
    return 0


def cmd_evaluate_answer(args: argparse.Namespace) -> int:
    choices = _load_json_arg(args.choices_json, None) if args.choices_json else {}
    spec: dict[str, Any] = {
        "kind": args.kind,
        "expected": args.expected,
        "tolerance": args.tolerance,
        "choices": choices if isinstance(choices, dict) else {},
        "prerequisite_hint": args.prereq_hint or "",
        "first_error_hint": args.first_error_hint or "",
        "alternative_explanation": args.alt_explanation or "",
    }
    res = evaluate_learner_response(spec, args.answer)
    print(_dump_json(res))
    return 0


def cmd_image_plan(args: argparse.Namespace) -> int:
    sess_dir: Path | None = None
    if args.vault_path or args.session:
        sess_dir = resolve_session_dir(args.vault_path, session_slug=args.session)

    candidates = _load_json_arg(args.candidates_json, args.candidates_file)
    if candidates is not None and not isinstance(candidates, list):
        raise ValueError("Image candidates JSON must be a list of candidate dicts")

    local_img = expand_path(args.local_image) if args.local_image else None
    t_caps = detect_terminal_capabilities(
        width=args.width,
        is_tty=True if args.tty else False if args.no_tty else None,
    )

    res = select_and_prepare_image(
        topic=args.topic_name,
        objective_id=args.objective or "obj-01",
        objective_desc=args.desc or args.topic_name,
        concept_type=args.concept_type or "",
        explicit_request=bool(args.explicit),
        candidates=candidates,
        host_tools={
            "image_search": bool(args.image_search),
            "image_inspect": bool(args.image_inspect),
        },
        terminal_caps=t_caps,
        session_dir=sess_dir,
        local_image_path=local_img,
        what_to_observe=args.observe or "",
        terminal_alternative=args.fallback or "",
    )
    print(_dump_json(res))
    return 0


def register_teaching_engine_subcommands(subparsers: Any) -> None:
    """Register terminal-first teaching engine subcommands on vault_cli.py."""
    p_cap = subparsers.add_parser("capabilities", help="Detect terminal and host tool capabilities cleanly.")
    p_cap.add_argument("--width", type=int, default=None)
    p_cap.add_argument("--height", type=int, default=None)
    p_cap.add_argument("--tty", action="store_true")
    p_cap.add_argument("--non-interactive", action="store_true")
    p_cap.add_argument("--no-color", action="store_true")
    p_cap.add_argument("--web-search", action="store_true")
    p_cap.add_argument("--image-search", action="store_true")
    p_cap.add_argument("--image-inspect", action="store_true")
    p_cap.add_argument("--no-python", action="store_true")
    p_cap.add_argument("--browser", action="store_true")
    p_cap.set_defaults(func=cmd_capabilities)

    p_route = subparsers.add_parser("route-modality", help="Select the optimal teaching modality for an objective.")
    p_route.add_argument("vault_path", nargs="?", default=None)
    p_route.add_argument("--session", default=None)
    p_route.add_argument("--topic", default=None)
    p_route.add_argument("--objective", default=None)
    p_route.add_argument("--title", default="")
    p_route.add_argument("--desc", default="")
    p_route.add_argument("--concept-type", default="")
    p_route.add_argument("--preference", default=None)
    p_route.add_argument("--last-modality", default="")
    p_route.add_argument("--difficulty", choices=["low", "medium", "high"], default="medium")
    p_route.add_argument("--abstraction", choices=["low", "medium", "high"], default="medium")
    p_route.add_argument("--time-budget", type=int, default=None)
    p_route.add_argument("--due", action="store_true")
    p_route.add_argument("--image-search", action="store_true")
    p_route.add_argument("--image-inspect", action="store_true")
    p_route.add_argument("--web-search", action="store_true")
    p_route.add_argument("--width", type=int, default=None)
    p_route.add_argument("--no-color", action="store_true")
    p_route.add_argument("--non-interactive", action="store_true")
    p_route.add_argument("--now", default=None)
    p_route.set_defaults(func=cmd_route_modality)

    p_graph = subparsers.add_parser("graph-render", help="Render an ASCII/Unicode/Braille terminal graph.")
    p_graph.add_argument("--kind", required=True, choices=["function", "line", "scatter", "bar", "histogram", "optimization_trace"])
    p_graph.add_argument("--expr", default=None, help="Math expression in x for function or optimization_trace.")
    p_graph.add_argument("--x-min", type=float, default=-5.0)
    p_graph.add_argument("--x-max", type=float, default=5.0)
    p_graph.add_argument("--samples", type=int, default=None)
    p_graph.add_argument("--data-json", default=None)
    p_graph.add_argument("--data-file", default=None)
    p_graph.add_argument("--bins", type=int, default=10)
    p_graph.add_argument("--title", default="")
    p_graph.add_argument("--x-label", default="")
    p_graph.add_argument("--y-label", default="")
    p_graph.add_argument("--unit-x", default="")
    p_graph.add_argument("--unit-y", default="")
    p_graph.add_argument("--width", type=int, default=None)
    p_graph.add_argument("--height", type=int, default=None)
    p_graph.add_argument("--charset", choices=["auto", "braille", "unicode", "ascii"], default="auto")
    p_graph.add_argument("--no-color", action="store_true")
    p_graph.add_argument("--format", choices=["json", "text"], default="json")
    p_graph.set_defaults(func=cmd_graph_render)

    p_sim = subparsers.add_parser("simulate", help="Run a bounded terminal-native educational simulation.")
    p_sim.add_argument("--list", action="store_true", help="List available simulation templates.")
    p_sim.add_argument("--template", default=None, help="gradient_descent | sorting | c_pointers | probability")
    p_sim.add_argument("--param", action="append", default=None, help="Parameter override key=value (repeatable).")
    p_sim.add_argument("--steps", type=int, default=5, help="Bounded steps to execute in non-interactive mode.")
    p_sim.add_argument("--predict", default=None, help="Optional learner prediction before stepping.")
    p_sim.add_argument("--interactive", action="store_true", help="Enter interactive loop if terminal is TTY.")
    p_sim.add_argument("--non-interactive", action="store_true", help="Force deterministic non-interactive demo.")
    p_sim.add_argument("--width", type=int, default=None)
    p_sim.add_argument("--charset", choices=["auto", "braille", "unicode", "ascii"], default="auto")
    p_sim.add_argument("--no-color", action="store_true")
    p_sim.add_argument("--format", choices=["json", "text"], default="json")
    p_sim.set_defaults(func=cmd_simulate)

    p_quiz = subparsers.add_parser("quiz-plan", help="Select adaptive difficulty level and quiz type for an objective.")
    p_quiz.add_argument("vault_path", nargs="?", default=None)
    p_quiz.add_argument("--session", default=None)
    p_quiz.add_argument("--topic", default=None)
    p_quiz.add_argument("--objective", default=None)
    p_quiz.add_argument("--tier", type=int, choices=[1, 2, 3], default=None)
    p_quiz.add_argument("--concept-type", default="")
    p_quiz.add_argument("--learner-request", default="")
    p_quiz.add_argument("--proficiency", default=None)
    p_quiz.add_argument("--indep", type=int, default=0)
    p_quiz.add_argument("--assist", type=int, default=0)
    p_quiz.add_argument("--failures", type=int, default=0)
    p_quiz.add_argument("--due", action="store_true")
    p_quiz.add_argument("--now", default=None)
    p_quiz.set_defaults(func=cmd_quiz_plan)

    p_eval = subparsers.add_parser("evaluate-answer", help="Deterministically check structured learner answers and produce feedback.")
    p_eval.add_argument("--kind", required=True, choices=["numeric", "multiple_choice", "math_expression", "exact_trace", "conceptual"])
    p_eval.add_argument("--expected", default="")
    p_eval.add_argument("--answer", required=True)
    p_eval.add_argument("--tolerance", type=float, default=1e-3)
    p_eval.add_argument("--choices-json", default=None)
    p_eval.add_argument("--prereq-hint", default="")
    p_eval.add_argument("--first-error-hint", default="")
    p_eval.add_argument("--alt-explanation", default="")
    p_eval.set_defaults(func=cmd_evaluate_answer)

    p_img = subparsers.add_parser("image-plan", help="Evaluate, verify, cache, and format an educational web image with terminal fallbacks.")
    p_img.add_argument("vault_path", nargs="?", default=None)
    p_img.add_argument("--session", default=None)
    p_img.add_argument("--topic-name", required=True)
    p_img.add_argument("--objective", default="obj-01")
    p_img.add_argument("--desc", default="")
    p_img.add_argument("--concept-type", default="")
    p_img.add_argument("--explicit", action="store_true")
    p_img.add_argument("--image-search", action="store_true")
    p_img.add_argument("--image-inspect", action="store_true")
    p_img.add_argument("--candidates-json", default=None)
    p_img.add_argument("--candidates-file", default=None)
    p_img.add_argument("--local-image", default=None)
    p_img.add_argument("--observe", default="")
    p_img.add_argument("--fallback", default="")
    p_img.add_argument("--width", type=int, default=None)
    p_img.add_argument("--tty", action="store_true")
    p_img.add_argument("--no-tty", action="store_true")
    p_img.set_defaults(func=cmd_image_plan)
