"""Interactive coding tutor engine, safe verification, and TeachMe memory integration."""

from __future__ import annotations

import ast
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import tempfile
import uuid
from typing import Any, Callable, Mapping, Sequence

from .adaptive_quiz import select_question_plan
from .evidence import (
    derive_objective_evidence,
    derive_session_coverage_and_gaps,
    format_utc_ts,
    normalize_objectives_list,
    parse_utc_ts,
)
from .models import atomic_write_text, read_text_safe
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
    revise_curriculum,
    slugify_topic,
)

SUPPORTED_CODING_MODES = ("learn", "practice", "debug", "trace", "challenge", "interview")
CODING_DIFFICULTIES = ("foundation", "intermediate", "advanced")

DIFFICULTY_TO_TIER = {"foundation": 1, "intermediate": 2, "advanced": 3}
TIER_TO_DIFFICULTY = {1: "foundation", 2: "intermediate", 3: "advanced"}

PROGRESSIVE_HINT_LEVELS: dict[int, dict[str, str]] = {
    0: {"level": "0", "label": "Independent attempt", "assistance": "none"},
    1: {"level": "1", "label": "Small directional hint", "assistance": "hint"},
    2: {"level": "2", "label": "Relevant concept or invariant", "assistance": "hint"},
    3: {"level": "3", "label": "Partial implementation or scaffold", "assistance": "scaffold"},
    4: {"level": "4", "label": "Complete worked solution on request", "assistance": "worked_example"},
}

LANGUAGE_ALIASES: dict[str, str] = {
    "c": "c",
    "py": "python",
    "python": "python",
    "python3": "python",
    "cpp": "cpp",
    "c++": "cpp",
    "java": "java",
    "js": "javascript",
    "javascript": "javascript",
    "node": "javascript",
}

MAX_CODE_BYTES = 256 * 1024
DEFAULT_TIMEOUT_SEC = 3.0
MAX_TIMEOUT_SEC = 10.0
DEFAULT_MAX_OUTPUT_CHARS = 8192


def normalize_language(raw: str | None) -> str:
    """Normalize a programming language alias into a canonical identifier."""
    val = str(raw or "").strip().lower()
    return LANGUAGE_ALIASES.get(val, "")


def parse_code_invocation(raw_args: str) -> dict[str, Any]:
    """Parse natural or flag-based /teachme-code invocations deterministically."""
    text = str(raw_args or "").strip()
    if text.startswith("/teachme-code"):
        text = text[len("/teachme-code"):].strip()
    elif text.startswith("/teachme code"):
        text = text[len("/teachme code"):].strip()

    try:
        tokens = shlex.split(text)
    except ValueError:
        tokens = text.split()

    mode: str | None = None
    level: str | None = None
    minutes: int | None = None
    resume = False
    code_file: str | None = None
    session_slug: str | None = None
    language = ""
    track = "programming"
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
            if cand not in SUPPORTED_CODING_MODES:
                raise ValueError(f"Unsupported coding mode {cand!r}; expected {SUPPORTED_CODING_MODES}")
            mode = cand
            i += 2
        elif low == "--level" and i + 1 < len(tokens):
            raw_lvl = tokens[i + 1].strip().lower()
            if raw_lvl in ("1", "foundation", "beginner"):
                level = "foundation"
            elif raw_lvl in ("2", "intermediate", "medium"):
                level = "intermediate"
            elif raw_lvl in ("3", "advanced", "hard"):
                level = "advanced"
            else:
                raise ValueError(f"Unsupported coding level {raw_lvl!r}")
            i += 2
        elif low in ("--minutes", "--time") and i + 1 < len(tokens):
            minutes = max(1, int(tokens[i + 1]))
            i += 2
        elif low in ("--file", "--code-file") and i + 1 < len(tokens):
            code_file = tokens[i + 1]
            i += 2
        elif low == "--session" and i + 1 < len(tokens):
            session_slug = tokens[i + 1]
            i += 2
        elif low in ("--lang", "--language") and i + 1 < len(tokens):
            language = normalize_language(tokens[i + 1])
            if not language:
                raise ValueError(f"Unsupported language {tokens[i + 1]!r}")
            i += 2
        elif tok.startswith("--"):
            i += 1
        else:
            positional.append(tok)
            i += 1

    if positional:
        first_low = positional[0].lower()
        if first_low == "dsa":
            track = "dsa"
            positional = positional[1:]
        elif not language:
            maybe_lang = normalize_language(first_low)
            if maybe_lang:
                language = maybe_lang
                positional = positional[1:]

    if positional and positional[0].lower() == "dsa" and track != "dsa":
        track = "dsa"
        positional = positional[1:]

    topic = " ".join(positional).strip()
    full_topic = topic
    if not topic and language and not resume:
        topic = f"{language} fundamentals" if mode != "debug" else f"{language} debugging"
        full_topic = topic
    elif topic and language and language not in topic.lower():
        full_topic = f"{language.upper() if language in ('c', 'cpp') else language.title()} {topic}"

    return {
        "language": language,
        "track": track,
        "topic": topic,
        "full_topic": full_topic.strip(),
        "mode": mode,
        "level": level,
        "minutes": minutes,
        "resume": resume,
        "code_file": code_file,
        "session_slug": session_slug,
    }


def detect_coding_runtimes(
    which_fn: Callable[[str], str | None] | None = None,
    *,
    python_exe: str | None = None,
    trusted_sandbox: bool | None = None,
) -> dict[str, Any]:
    """Honestly detect available local compilers/runtimes and sandbox limitations."""
    finder = which_fn or shutil.which
    py_path = python_exe if python_exe is not None else (finder("python3") or finder("python") or "")

    c_compiler = finder("gcc") or finder("clang") or finder("cc") or finder("cl") or ""
    cpp_compiler = finder("g++") or finder("clang++") or ""
    javac_path = finder("javac") or ""
    java_path = finder("java") or ""
    node_path = finder("node") or ""

    if trusted_sandbox is None:
        env_sb = str(os.environ.get("TEACHME_TRUSTED_SANDBOX", "")).strip().lower() in ("1", "true", "yes")
    else:
        env_sb = bool(trusted_sandbox)

    runtimes: dict[str, dict[str, Any]] = {
        "python": {
            "available": bool(py_path),
            "tier": "first_class",
            "executable": py_path,
            "compiler": None,
        },
        "c": {
            "available": bool(c_compiler),
            "tier": "first_class",
            "compiler": c_compiler,
            "executable": c_compiler,
        },
        "cpp": {
            "available": bool(cpp_compiler),
            "tier": "adapter",
            "compiler": cpp_compiler,
            "executable": cpp_compiler,
        },
        "java": {
            "available": bool(javac_path and java_path),
            "tier": "adapter",
            "compiler": javac_path,
            "executable": java_path,
            "missing_reason": "" if (javac_path and java_path) else "Requires both javac and java on PATH",
        },
        "javascript": {
            "available": bool(node_path),
            "tier": "adapter",
            "compiler": None,
            "executable": node_path,
        },
    }

    return {
        "runtimes": runtimes,
        "isolated_sandbox": env_sb,
        "authorization_required_for_exec": not env_sb,
        "isolation_note": (
            "Trusted sandbox configured."
            if env_sb
            else "Local execution runs in a temporary working directory with timeout and output caps, "
                 "without OS-level process/memory isolation; require explicit authorization before running learner code."
        ),
    }


def hint_level_to_assistance(hint_level: int) -> str:
    """Map progressive hint level (0..4) to TeachMe ASSISTANCE_LEVELS."""
    lvl = max(0, min(4, int(hint_level)))
    return PROGRESSIVE_HINT_LEVELS[lvl]["assistance"]


def _code_session_path(session_dir: Path) -> Path:
    return session_dir / "scratchpad" / "code-session.json"


def load_code_session(session_dir: Path) -> dict[str, Any] | None:
    path = _code_session_path(session_dir)
    if not path.is_file():
        return None
    try:
        data = json.loads(read_text_safe(path))
        return data if isinstance(data, dict) else None
    except (OSError, json.JSONDecodeError):
        return None


def save_code_session(session_dir: Path, state: dict[str, Any]) -> Path:
    path = _code_session_path(session_dir)
    atomic_write_text(path, json.dumps(state, indent=2, ensure_ascii=False) + "\n")
    return path


def _safe_try_resolve_session(
    vault_or_session: str | None,
    *,
    session_slug: str | None = None,
    topic_hint: str = "",
) -> Path | None:
    if vault_or_session or session_slug:
        try:
            return resolve_session_dir(vault_or_session, session_slug=session_slug)
        except FileNotFoundError:
            pass
    if topic_hint:
        try:
            return resolve_session_dir(None, session_slug=slugify_topic(topic_hint))
        except FileNotFoundError:
            pass
    try:
        return resolve_session_dir(None)
    except FileNotFoundError:
        return None


def _collect_shared_weak_spots(session_dir: Path) -> dict[str, Any]:
    """Inspect existing TeachMe evidence, due items, and learning-records without duplicating state."""
    curriculum = load_curriculum(session_dir)
    events = load_events(session_dir)
    mission = load_mission(session_dir)
    rev_store = load_review_state(session_dir)
    due = get_due_reviews(curriculum, events, rev_store, limit=15)
    cov = derive_session_coverage_and_gaps(curriculum, events, mission=mission, review_due=due)
    lrs = [r for r in load_learning_records(session_dir) if not str(r.get("status", "")).startswith("superseded")]

    weak_items: list[dict[str, Any]] = []
    nodes = curriculum.get("nodes", {})
    for obj_info in cov.get("objectives", []):
        p_status = obj_info["proficiency_status"]
        nid = obj_info["topic_id"]
        oid = obj_info["objective_id"]
        cnode = nodes.get(nid) or {}
        if p_status in ("weakened", "practiced_with_support") or obj_info["unresolved_gaps"]:
            weak_items.append(
                {
                    "topic_id": nid,
                    "topic_title": cnode.get("title", nid),
                    "objective_id": oid,
                    "description": obj_info["description"],
                    "proficiency_status": p_status,
                    "gaps": obj_info["unresolved_gaps"],
                }
            )

    misconceptions = [
        {
            "file": r["file"],
            "title": r["title"],
            "context": r["context"],
            "insight": r["insight"],
        }
        for r in lrs[-8:]
    ]

    return {
        "curriculum": curriculum,
        "events": events,
        "mission": mission,
        "due": due,
        "coverage": cov,
        "weak_items": weak_items,
        "misconceptions": misconceptions,
    }


def _match_topic_and_objective(
    curriculum: dict[str, Any],
    topic_query: str,
    explicit_topic: str | None = None,
    explicit_objective: str | None = None,
) -> tuple[str | None, str | None, dict[str, Any] | None]:
    nodes = curriculum.get("nodes") or {}
    if not nodes:
        return None, None, None

    if explicit_topic:
        t_num = normalize_topic_num(explicit_topic)
        nid = f"topic-{t_num}"
        if nid in nodes:
            objs = normalize_objectives_list(nid, nodes[nid])
            picked = next((o for o in objs if o["id"] == explicit_objective), objs[0]) if explicit_objective else objs[0]
            return t_num, picked["id"], picked

    q_terms = {t for t in re.findall(r"[a-z0-9]+", topic_query.lower()) if len(t) >= 2}
    best_score = -1
    best_nid = None
    best_obj = None

    for nid in curriculum.get("order") or list(nodes.keys()):
        node = nodes.get(nid)
        if not isinstance(node, dict):
            continue
        title_blob = f"{node.get('title', '')} {node.get('objective', '')} {' '.join(node.get('key_concepts', []))}".lower()
        objs = normalize_objectives_list(nid, node)
        for obj in objs:
            desc_blob = f"{title_blob} {obj.get('description', '')}".lower()
            score = sum(1 for qt in q_terms if qt in desc_blob)
            if score > best_score:
                best_score = score
                best_nid = nid
                best_obj = obj

    if best_nid and best_obj:
        return normalize_topic_num(best_nid), best_obj["id"], best_obj
    first_nid = (curriculum.get("order") or list(nodes.keys()))[0]
    first_objs = normalize_objectives_list(first_nid, nodes[first_nid])
    return normalize_topic_num(first_nid), first_objs[0]["id"], first_objs[0]


def build_code_plan(
    raw_args: str = "",
    *,
    vault_path: str | None = None,
    session_slug: str | None = None,
    topic_num: str | None = None,
    objective_id: str | None = None,
    init_if_missing: bool = False,
    ensure_objective: str | None = None,
    now: str | None = None,
    which_fn: Callable[[str], str | None] | None = None,
) -> dict[str, Any]:
    """Build a bounded interactive coding session plan backed by shared TeachMe memory."""
    parsed = parse_code_invocation(raw_args)
    eff_session_slug = session_slug or parsed["session_slug"]
    topic_hint = parsed["full_topic"] or parsed["topic"]

    sess_dir = _safe_try_resolve_session(
        vault_path,
        session_slug=eff_session_slug,
        topic_hint=topic_hint,
    )

    prev_code_state = load_code_session(sess_dir) if sess_dir else None
    if parsed["resume"] and prev_code_state:
        if not parsed["language"]:
            parsed["language"] = str(prev_code_state.get("language") or "")
        if not parsed["topic"]:
            parsed["topic"] = str(prev_code_state.get("topic") or "")
            parsed["full_topic"] = str(prev_code_state.get("full_topic") or parsed["topic"])
        if parsed["mode"] is None:
            parsed["mode"] = prev_code_state.get("mode")
        if parsed["level"] is None:
            parsed["level"] = prev_code_state.get("difficulty")
        if parsed["minutes"] is None:
            parsed["minutes"] = prev_code_state.get("time_budget_minutes")

    if sess_dir is None and init_if_missing and (parsed["full_topic"] or parsed["language"]):
        slug = eff_session_slug or slugify_topic(parsed["full_topic"] or parsed["language"])
        if vault_path:
            target_root = resolve_session_dir(
                vault_path,
                session_slug=slug,
                topic_hint=parsed["full_topic"] or parsed["language"],
                for_init=True,
            )
            mode_str = "vault-native" if ".teachme" in target_root.parts else "standalone"
        else:
            from .models import load_config
            cfg = load_config()
            raw_root = str(cfg.get("notes_root", "")).strip()
            base_root = Path(os.path.expandvars(raw_root)).expanduser().resolve() if raw_root else (Path.home() / "notes").resolve()
            target_root = base_root / slug
            mode_str = "standalone"
        eff_title = parsed["full_topic"] or f"{parsed['language'].title()} Coding Practice"
        init_session_state(
            target_root,
            topic_title=eff_title,
            items=[
                {
                    "slug": f"01-{slugify_topic(parsed['topic'] or parsed['language'] or 'core')}",
                    "title": eff_title,
                    "objective": f"Write, trace, and debug {eff_title} code accurately.",
                }
            ],
            mode=mode_str,
        )
        sess_dir = target_root

    runtimes_info = detect_coding_runtimes(which_fn=which_fn)

    shared_state: dict[str, Any] = {}
    matched_topic_num: str | None = None
    matched_obj_id: str | None = None
    matched_obj: dict[str, Any] | None = None
    quiz_plan: dict[str, Any] | None = None

    if sess_dir is not None:
        shared_state = _collect_shared_weak_spots(sess_dir)
        curr = shared_state["curriculum"]
        matched_topic_num, matched_obj_id, matched_obj = _match_topic_and_objective(
            curr,
            parsed["full_topic"] or parsed["topic"],
            explicit_topic=topic_num,
            explicit_objective=objective_id,
        )

        # Optionally integrate a missing coding objective while preserving existing IDs & DAG
        if ensure_objective and matched_topic_num:
            target_nid = f"topic-{matched_topic_num}"
            cnode = (curr.get("nodes") or {}).get(target_nid) or {}
            existing_objs = normalize_objectives_list(target_nid, cnode)
            if not any(ensure_objective.lower() in o["description"].lower() for o in existing_objs):
                new_oid = f"obj-{matched_topic_num}-{len(existing_objs) + 1:02d}"
                revise_curriculum(
                    sess_dir,
                    target_topic=target_nid,
                    objective_id=new_oid,
                    objective_desc=ensure_objective,
                    required=True,
                    in_scope=True,
                    expected_assessments=["independent_application", "debug_program"],
                )
                shared_state = _collect_shared_weak_spots(sess_dir)
                curr = shared_state["curriculum"]
                matched_topic_num, matched_obj_id, matched_obj = _match_topic_and_objective(
                    curr,
                    ensure_objective,
                    explicit_topic=matched_topic_num,
                    explicit_objective=new_oid,
                )

        if matched_topic_num and matched_obj is not None:
            t_events = [
                e for e in shared_state["events"]
                if normalize_topic_num(str(e.get("topic", ""))) == matched_topic_num
                and (e.get("objective_id") == matched_obj_id or not e.get("objective_id"))
            ]
            cnode = (curr.get("nodes") or {}).get(f"topic-{matched_topic_num}") or {}
            derived_obj = derive_objective_evidence(
                matched_obj,
                t_events,
                node_status=str(cnode.get("status") or "unstarted"),
                node_checkpoint=str(cnode.get("checkpoint") or "0/4"),
            )
            matched_obj = derived_obj
            due_item = next((d for d in shared_state["due"] if d["objective_id"] == matched_obj_id), None)
            req_tier = DIFFICULTY_TO_TIER[parsed["level"]] if parsed["level"] else None
            quiz_plan = select_question_plan(
                derived_obj,
                recent_events=t_events[-6:],
                due_item=due_item,
                requested_tier=req_tier,
                concept_type="memory_pointer_code" if parsed["language"] == "c" else "algorithm_stepwise",
            )

    # Select mode and difficulty honestly
    weak_items = shared_state.get("weak_items", [])
    misconceptions = shared_state.get("misconceptions", [])
    if parsed["mode"]:
        eff_mode = parsed["mode"]
    elif weak_items or misconceptions:
        eff_mode = "practice"
    else:
        eff_mode = "learn"

    if parsed["level"]:
        eff_difficulty = parsed["level"]
    elif quiz_plan is not None:
        eff_difficulty = TIER_TO_DIFFICULTY.get(int(quiz_plan.get("level", 1)), "foundation")
    else:
        eff_difficulty = "foundation"

    # Recommend simulation or trace table
    low_topic = (parsed["full_topic"] or "").lower()
    sim_template: str | None = None
    if parsed["language"] == "c" and any(k in low_topic for k in ("pointer", "address", "deref", "swap", "null")):
        sim_template = "c_pointers"
    elif any(k in low_topic for k in ("sort", "bubble", "insertion", "selection", "merge", "quick")):
        sim_template = "sorting"

    eff_lang = parsed["language"] or ("python" if parsed["track"] == "dsa" else "")
    lang_runtime = runtimes_info["runtimes"].get(eff_lang) if eff_lang else None

    run_id = (prev_code_state.get("run_id") if parsed["resume"] and prev_code_state else None) or f"code-{uuid.uuid4().hex[:8]}"
    session_state_payload = {
        "schema_version": 1,
        "run_id": run_id,
        "language": eff_lang,
        "track": parsed["track"],
        "topic": parsed["topic"],
        "full_topic": parsed["full_topic"],
        "mode": eff_mode,
        "difficulty": eff_difficulty,
        "time_budget_minutes": parsed["minutes"],
        "active_topic_num": matched_topic_num,
        "active_objective_id": matched_obj_id,
        "hint_level": int(prev_code_state.get("hint_level", 0)) if (parsed["resume"] and prev_code_state) else 0,
        "file_path": parsed["code_file"] or (prev_code_state.get("file_path") if parsed["resume"] and prev_code_state else None),
        "updated_at": format_utc_ts(parse_utc_ts(now)),
    }
    if sess_dir is not None:
        save_code_session(sess_dir, session_state_payload)

    return {
        "ok": True,
        "resumed": bool(parsed["resume"] and prev_code_state is not None),
        "session_dir": str(sess_dir) if sess_dir else None,
        "parsed": parsed,
        "mode": eff_mode,
        "difficulty": eff_difficulty,
        "language": eff_lang or "unspecified",
        "language_runtime": lang_runtime,
        "runtimes": runtimes_info,
        "active_topic_num": matched_topic_num,
        "active_objective_id": matched_obj_id,
        "active_objective": matched_obj,
        "quiz_plan": quiz_plan,
        "prioritize_weak_spots": weak_items[:5],
        "active_misconceptions": misconceptions[:5],
        "recommended_simulation": sim_template,
        "hint_ladder": PROGRESSIVE_HINT_LEVELS,
        "code_session": session_state_payload,
        "study_notes_modified": False,
    }


def _find_unterminated_loop_semicolon(lines: list[str]) -> tuple[int, str] | None:
    for idx, line in enumerate(lines, start=1):
        stripped = line.strip()
        if re.match(r"^(for|while)\s*\([^;{}]*;[^;{}]*;[^;{}]*\)\s*;$", stripped) or re.match(
            r"^while\s*\([^;{}]+\)\s*;$", stripped
        ):
            return idx, "Loop header ends with ';', creating an empty loop body."
    return None


def analyze_code_static(code: str, language: str) -> dict[str, Any]:
    """Perform safe, zero-execution static checks and beginner diagnostics."""
    lang = normalize_language(language) or language.strip().lower()
    lines = code.splitlines()
    findings: list[dict[str, Any]] = []

    if not code.strip():
        findings.append(
            {
                "category": "syntax_error",
                "line": 1,
                "message": "Submitted code is empty.",
                "why": "There are no statements to inspect or verify.",
                "hint": "Write your first attempt and submit it for feedback.",
            }
        )
        return {
            "language": lang,
            "ok": False,
            "has_blocking_error": True,
            "findings": findings,
            "first_error": findings[0],
        }

    if lang == "python":
        try:
            tree = ast.parse(code)
        except SyntaxError as exc:
            msg = exc.msg or "Invalid Python syntax"
            hint = "Check indentation, colons after def/if/for/while, and matching parentheses."
            if "expected ':'" in msg:
                hint = "Add a colon ':' at the end of the header line."
            elif "invalid syntax" in msg and exc.text and "=" in exc.text and "==" not in exc.text and ("if " in exc.text or "while " in exc.text):
                hint = "Use '==' for comparison instead of '=' assignment inside a condition."
            findings.append(
                {
                    "category": "syntax_error",
                    "line": exc.lineno or 1,
                    "column": exc.offset or 1,
                    "message": msg,
                    "why": f"Python could not parse line {exc.lineno or 1}: {msg}.",
                    "hint": hint,
                }
            )
            return {
                "language": lang,
                "ok": False,
                "has_blocking_error": True,
                "findings": findings,
                "first_error": findings[0],
            }

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                for dflt in node.args.defaults:
                    if isinstance(dflt, (ast.List, ast.Dict, ast.Set)):
                        findings.append(
                            {
                                "category": "logical_error",
                                "line": node.lineno,
                                "message": f"Mutable default argument in function '{node.name}'.",
                                "why": "Python creates default argument objects once at definition time, sharing state across calls.",
                                "hint": "Default to None and create a fresh list/dict inside the function.",
                            }
                        )
                # Recursion base-case heuristic
                calls_self = any(
                    isinstance(sub, ast.Call) and isinstance(sub.func, ast.Name) and sub.func.id == node.name
                    for sub in ast.walk(node)
                )
                if calls_self:
                    has_non_recursive_return = False
                    for sub in ast.walk(node):
                        if isinstance(sub, ast.Return):
                            has_self_call = any(
                                isinstance(c, ast.Call) and isinstance(c.func, ast.Name) and c.func.id == node.name
                                for c in ast.walk(sub)
                            )
                            if not has_self_call:
                                has_non_recursive_return = True
                                break
                    if not has_non_recursive_return:
                        findings.append(
                            {
                                "category": "logical_error",
                                "line": node.lineno,
                                "message": f"Recursive function '{node.name}' appears to lack a base-case return.",
                                "why": "Without a non-recursive return path, recursion continues until RecursionError.",
                                "hint": "Check your stopping condition and ensure it returns without calling the function again.",
                            }
                        )
            elif isinstance(node, ast.While):
                if isinstance(node.test, ast.Constant) and node.test.value is True:
                    has_exit = any(isinstance(sub, (ast.Break, ast.Return)) for sub in ast.walk(node))
                    if not has_exit:
                        findings.append(
                            {
                                "category": "logical_error",
                                "line": node.lineno,
                                "message": "Infinite 'while True' loop without break or return.",
                                "why": "The loop condition never becomes false and no exit statement was found.",
                                "hint": "Add a break or return condition when your target state is reached.",
                            }
                        )

    elif lang == "c":
        # Track declared scalars, arrays, pointers, and mallocs for beginner diagnostics
        declared_ints: set[str] = set()
        initialized_vars: set[str] = set()
        declared_arrays: dict[str, int] = {}
        malloc_vars: set[str] = set()
        freed_vars: set[str] = set()
        checked_null: set[str] = set()
        current_fn: str | None = None
        fn_has_self_call = False
        fn_has_base_return = False
        fn_start_line = 1

        semi_loop = _find_unterminated_loop_semicolon(lines)
        if semi_loop:
            findings.append(
                {
                    "category": "logical_error",
                    "line": semi_loop[0],
                    "message": semi_loop[1],
                    "why": "The trailing ';' terminates the loop before the following block.",
                    "hint": "Remove the ';' right after the loop parentheses.",
                }
            )

        for idx, raw_line in enumerate(lines, start=1):
            line = re.sub(r"//.*$", "", raw_line).strip()
            if not line or line.startswith("#"):
                continue

            # Track simple function definitions for recursion checks
            m_fn = re.match(r"^(?:int|void|long|double|float|char)\s+([a-zA-Z_]\w*)\s*\(([^)]*)\)\s*\{?", line)
            if m_fn and m_fn.group(1) not in ("if", "for", "while", "switch"):
                if current_fn and fn_has_self_call and not fn_has_base_return:
                    findings.append(
                        {
                            "category": "logical_error",
                            "line": fn_start_line,
                            "message": f"Recursive C function '{current_fn}' may lack a base-case return.",
                            "why": "Every recursive path must reach a non-recursive return to prevent stack overflow.",
                            "hint": "Add an early `if (...) return ...;` base case before the recursive call.",
                        }
                    )
                current_fn = m_fn.group(1)
                fn_start_line = idx
                fn_has_self_call = False
                fn_has_base_return = False
                for param in m_fn.group(2).split(","):
                    pm = re.search(r"([a-zA-Z_]\w*)\s*(?:\[\s*\])?$", param.strip())
                    if pm:
                        initialized_vars.add(pm.group(1))
                continue

            if current_fn:
                if re.search(rf"\b{re.escape(current_fn)}\s*\(", line):
                    fn_has_self_call = True
                elif re.search(r"\breturn\b", line):
                    fn_has_base_return = True

            # gets() unsafe usage
            if re.search(r"\bgets\s*\(", line):
                findings.append(
                    {
                        "category": "undefined_behavior_risk",
                        "line": idx,
                        "message": "Unsafe use of gets().",
                        "why": "gets() performs no bounds checking and was removed from C11.",
                        "hint": "Use fgets(buf, sizeof(buf), stdin) instead.",
                    }
                )

            # Array declarations: int a[5];
            m_arr = re.match(r"^(?:int|char|double|float|long)\s+([a-zA-Z_]\w*)\s*\[\s*(\d+)\s*\]\s*(=\s*[^;]+)?;", line)
            if m_arr:
                aname, asize, init_part = m_arr.group(1), int(m_arr.group(2)), m_arr.group(3)
                declared_arrays[aname] = asize
                if init_part:
                    initialized_vars.add(aname)
                if "char " in line and init_part:
                    m_str = re.search(r'=\s*"([^"]*)"', init_part)
                    if m_str and len(m_str.group(1)) >= asize:
                        findings.append(
                            {
                                "category": "undefined_behavior_risk",
                                "line": idx,
                                "message": f"String literal leaves no room for null terminator '\\0' in '{aname}[{asize}]'.",
                                "why": "C strings require one extra byte for '\\0'; printing or strlen() may read past the buffer.",
                                "hint": f"Increase '{aname}' size to at least {len(m_str.group(1)) + 1}.",
                            }
                        )

            # Scalar int declarations without init
            m_uninit = re.match(r"^(?:int|long|float|double|char)\s+([a-zA-Z_]\w*)\s*;", line)
            if m_uninit:
                vname = m_uninit.group(1)
                declared_ints.add(vname)
                continue

            # Pointer declarations: int *p = x; (missing &) or int *p = malloc(...)
            m_ptr_init = re.match(r"^(?:int|char|double|float|void)\s*\*\s*([a-zA-Z_]\w*)\s*=\s*([^;]+);", line)
            if m_ptr_init:
                pname, rhs = m_ptr_init.group(1), m_ptr_init.group(2).strip()
                initialized_vars.add(pname)
                if rhs in declared_ints:
                    findings.append(
                        {
                            "category": "compilation_error",
                            "line": idx,
                            "message": f"Pointer '{pname}' initialized from integer '{rhs}' without '&'.",
                            "why": "A pointer stores a memory address, not the integer value itself.",
                            "hint": f"Use `int *{pname} = &{rhs};` if you want '{pname}' to point to '{rhs}'.",
                        }
                    )
                if "malloc(" in rhs or "calloc(" in rhs or "realloc(" in rhs:
                    malloc_vars.add(pname)
                continue

            # Uninitialized variable read heuristic (e.g. printf("%d", x); before x = ...)
            if re.search(r"\bprintf\s*\(", line) or re.search(r"\breturn\b", line):
                for vname in declared_ints:
                    if vname not in initialized_vars and re.search(rf"\b{re.escape(vname)}\b", line):
                        findings.append(
                            {
                                "category": "undefined_behavior_risk",
                                "line": idx,
                                "message": f"Variable '{vname}' may be read before being initialized.",
                                "why": "Local variables in C contain indeterminate garbage values until assigned.",
                                "hint": f"Initialize '{vname}' when declaring it (e.g. `int {vname} = 0;`).",
                            }
                        )

            # Assignments mark variable initialized (including scanf("%d", &x))
            m_assign = re.match(r"^([a-zA-Z_]\w*)\s*=\s*([^;]+);", line)
            if m_assign:
                lhs, rhs = m_assign.group(1), m_assign.group(2)
                initialized_vars.add(lhs)
                if "malloc(" in rhs or "calloc(" in rhs:
                    malloc_vars.add(lhs)

            # scanf mistakes: missing & on scalar argument
            m_scanf = re.search(r'\bscanf\s*\(\s*"([^"]*)"\s*,\s*([^)]+)\)', line)
            if m_scanf:
                fmt, arg_str = m_scanf.group(1), m_scanf.group(2)
                args_list = [a.strip() for a in arg_str.split(",") if a.strip()]
                specs = re.findall(r"%[a-zA-Z]+", fmt)
                for sp, arg in zip(specs, args_list):
                    if sp in ("%d", "%i", "%f", "%lf", "%c", "%ld") and not arg.startswith("&") and arg in declared_ints:
                        findings.append(
                            {
                                "category": "undefined_behavior_risk",
                                "line": idx,
                                "message": f"scanf('{sp}', {arg}) is missing '&' before '{arg}'.",
                                "why": "scanf requires the address of the variable to store input; passing the value causes undefined behavior or crashes.",
                                "hint": f"Pass `&{arg}` to scanf.",
                            }
                        )
                    elif sp in ("%d", "%i", "%f", "%lf", "%c", "%ld") and arg.startswith("&"):
                        initialized_vars.add(arg[1:].strip())

            # NULL check & free tracking
            for mv in list(malloc_vars):
                if re.search(rf"\b{re.escape(mv)}\s*==\s*NULL|!\s*{re.escape(mv)}\b", line):
                    checked_null.add(mv)
                if re.search(rf"\bfree\s*\(\s*{re.escape(mv)}\s*\)", line):
                    freed_vars.add(mv)

            # Array off-by-one loop bound: for (...; i <= N; ...) with a[N]
            m_for = re.search(r"for\s*\([^;]*;\s*[a-zA-Z_]\w*\s*<=\s*(\d+)\s*;", line)
            if m_for:
                bound = int(m_for.group(1))
                for aname, asize in declared_arrays.items():
                    if bound == asize:
                        findings.append(
                            {
                                "category": "undefined_behavior_risk",
                                "line": idx,
                                "message": f"Loop condition uses '<= {bound}' on array '{aname}[{asize}]'.",
                                "why": f"Valid indices for '{aname}[{asize}]' are 0 to {asize - 1}; index {asize} is out of bounds.",
                                "hint": f"Use '< {asize}' instead of '<= {asize}'.",
                            }
                        )

            # Direct out-of-bounds literal index
            for aname, asize in declared_arrays.items():
                for m_idx in re.finditer(rf"\b{re.escape(aname)}\s*\[\s*(\d+)\s*\]", line):
                    ival = int(m_idx.group(1))
                    if ival >= asize:
                        findings.append(
                            {
                                "category": "undefined_behavior_risk",
                                "line": idx,
                                "message": f"Out-of-bounds index {aname}[{ival}] for size {asize}.",
                                "why": f"Valid indices are 0..{asize - 1}.",
                                "hint": "Keep indices strictly below the array length.",
                            }
                        )

        if current_fn and fn_has_self_call and not fn_has_base_return:
            findings.append(
                {
                    "category": "logical_error",
                    "line": fn_start_line,
                    "message": f"Recursive C function '{current_fn}' may lack a base-case return.",
                    "why": "Every recursive path must reach a non-recursive return to prevent stack overflow.",
                    "hint": "Add an early `if (...) return ...;` base case before the recursive call.",
                }
            )

        for mv in sorted(malloc_vars - freed_vars):
            findings.append(
                {
                    "category": "undefined_behavior_risk",
                    "line": 1,
                    "message": f"Allocated pointer '{mv}' is not freed with free({mv}).",
                    "why": "Forgetting free() leaks heap memory.",
                    "hint": f"Call `free({mv});` once '{mv}' is no longer needed.",
                }
            )
        for mv in sorted(malloc_vars - checked_null):
            findings.append(
                {
                    "category": "undefined_behavior_risk",
                    "line": 1,
                    "message": f"Allocation '{mv}' has no visible NULL check.",
                    "why": "malloc/calloc returns NULL if allocation fails; dereferencing NULL causes a crash.",
                    "hint": f"Check `if ({mv} == NULL)` before dereferencing '{mv}'.",
                }
            )

    else:
        # Basic brace balance check for C++/Java/JavaScript
        balance = code.count("{") - code.count("}")
        if balance != 0:
            findings.append(
                {
                    "category": "syntax_error",
                    "line": len(lines),
                    "message": "Unbalanced curly braces '{' and '}'.",
                    "why": "Every opening '{' must have a matching closing '}'.",
                    "hint": "Count opening and closing braces around functions and blocks.",
                }
            )

    has_blocking = any(f["category"] in ("syntax_error", "compilation_error") for f in findings)
    return {
        "language": lang,
        "ok": not has_blocking and not findings,
        "has_blocking_error": has_blocking,
        "findings": findings,
        "first_error": findings[0] if findings else None,
    }


def _truncate_output(text: str, max_chars: int) -> tuple[str, bool]:
    if len(text) <= max_chars:
        return text, False
    return text[:max_chars] + "\n...[truncated]", True


def _run_bounded_subprocess(
    cmd: list[str],
    *,
    cwd: Path,
    stdin_text: str = "",
    timeout_sec: float = DEFAULT_TIMEOUT_SEC,
    max_output_chars: int = DEFAULT_MAX_OUTPUT_CHARS,
) -> dict[str, Any]:
    """Run a bounded subprocess without shell=True and with strict timeout/output limits."""
    bounded_timeout = max(0.5, min(MAX_TIMEOUT_SEC, float(timeout_sec)))
    try:
        proc = subprocess.run(
            cmd,
            input=stdin_text,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=str(cwd),
            timeout=bounded_timeout,
            shell=False,
            check=False,
        )
        stdout, out_trunc = _truncate_output(proc.stdout or "", max_output_chars)
        stderr, err_trunc = _truncate_output(proc.stderr or "", max_output_chars)
        return {
            "timed_out": False,
            "returncode": proc.returncode,
            "stdout": stdout,
            "stderr": stderr,
            "output_truncated": out_trunc or err_trunc,
        }
    except subprocess.TimeoutExpired as exc:
        out_raw = exc.stdout.decode("utf-8", errors="replace") if isinstance(exc.stdout, bytes) else (exc.stdout or "")
        err_raw = exc.stderr.decode("utf-8", errors="replace") if isinstance(exc.stderr, bytes) else (exc.stderr or "")
        stdout, _ = _truncate_output(out_raw, max_output_chars)
        stderr, _ = _truncate_output(err_raw, max_output_chars)
        return {
            "timed_out": True,
            "returncode": -1,
            "stdout": stdout,
            "stderr": stderr or f"Execution timed out after {bounded_timeout:.1f}s.",
            "output_truncated": True,
        }
    except OSError as exc:
        return {
            "timed_out": False,
            "returncode": -1,
            "stdout": "",
            "stderr": str(exc),
            "output_truncated": False,
        }


def _normalize_output(text: str) -> str:
    return "\n".join(line.rstrip() for line in text.replace("\r\n", "\n").strip().splitlines())


def verify_learner_code(
    *,
    code: str | None = None,
    code_file: str | None = None,
    language: str,
    test_cases: Sequence[Mapping[str, Any]] | None = None,
    authorize_exec: bool = False,
    timeout_sec: float = DEFAULT_TIMEOUT_SEC,
    max_output_chars: int = DEFAULT_MAX_OUTPUT_CHARS,
    hint_level: int = 0,
    session_dir: Path | None = None,
    topic_num: str | None = None,
    objective_id: str | None = None,
    assessment_type: str = "independent_application",
    record_evidence: bool = False,
    now: str | None = None,
    which_fn: Callable[[str], str | None] | None = None,
    trusted_sandbox: bool | None = None,
) -> dict[str, Any]:
    """Inspect, optionally compile/execute in an isolated temp dir, test, and classify evidence."""
    lang = normalize_language(language)
    if not lang:
        raise ValueError(f"Unsupported coding language: {language!r}")

    source_text = code
    resolved_file: str | None = None
    if source_text is None and code_file:
        p = Path(os.path.expandvars(code_file)).expanduser().resolve()
        if not p.is_file():
            raise FileNotFoundError(f"Code file not found: {p}")
        if p.stat().st_size > MAX_CODE_BYTES:
            raise ValueError(f"Code file exceeds {MAX_CODE_BYTES} byte safety limit")
        source_text = read_text_safe(p)
        resolved_file = str(p)
    if source_text is None:
        source_text = ""

    static_report = analyze_code_static(source_text, lang)
    rt_report = detect_coding_runtimes(which_fn=which_fn, trusted_sandbox=trusted_sandbox)
    rt_info = rt_report["runtimes"][lang]
    exec_allowed = bool(authorize_exec or rt_report["isolated_sandbox"])
    assistance = hint_level_to_assistance(hint_level)

    result_payload: dict[str, Any] = {
        "ok": True,
        "language": lang,
        "code_file": resolved_file,
        "static_analysis": static_report,
        "execution_performed": False,
        "execution_status": "not_attempted",
        "isolation_note": rt_report["isolation_note"],
        "compilation_error": None,
        "runtime_error": None,
        "test_results": [],
        "tests_passed": 0,
        "tests_total": len(test_cases or []),
        "example_tests_passed": None,
        "edge_tests_passed": None,
        "verification_scope": "static_only",
        "first_error": static_report["first_error"],
        "suggested_result": "fail" if static_report["has_blocking_error"] else "skipped",
        "suggested_assistance": assistance,
        "hint_level": max(0, min(4, int(hint_level))),
        "study_notes_modified": False,
    }

    if static_report["has_blocking_error"]:
        result_payload["ok"] = False
        result_payload["execution_status"] = "blocked_by_static_error"
        result_payload["suggested_result"] = "fail"
        return _maybe_record_code_evidence(
            result_payload,
            record_evidence=record_evidence,
            session_dir=session_dir,
            topic_num=topic_num,
            objective_id=objective_id,
            assessment_type=assessment_type,
            now=now,
        )

    if not rt_info["available"]:
        result_payload["execution_status"] = "runtime_unavailable"
        result_payload["execution_notice"] = (
            f"No {lang} compiler/runtime was detected on PATH; static feedback only."
        )
        return _maybe_record_code_evidence(
            result_payload,
            record_evidence=record_evidence,
            session_dir=session_dir,
            topic_num=topic_num,
            objective_id=objective_id,
            assessment_type=assessment_type,
            now=now,
        )

    if not exec_allowed:
        result_payload["execution_status"] = "authorization_required"
        result_payload["execution_notice"] = (
            "Explicit authorization is required before executing learner code locally; returning static feedback only."
        )
        return _maybe_record_code_evidence(
            result_payload,
            record_evidence=record_evidence,
            session_dir=session_dir,
            topic_num=topic_num,
            objective_id=objective_id,
            assessment_type=assessment_type,
            now=now,
        )

    # Execute inside a fresh temporary directory so no build artifacts enter user repo or notes
    with tempfile.TemporaryDirectory(prefix="teachme_code_run_") as tmpdir:
        tmp_path = Path(tmpdir)
        exe_cmd_base: list[str] = []

        if lang == "python":
            src_file = tmp_path / "solution.py"
            src_file.write_text(source_text, encoding="utf-8")
            exe_cmd_base = [rt_info["executable"], "-I", str(src_file)]
        elif lang == "javascript":
            src_file = tmp_path / "solution.js"
            src_file.write_text(source_text, encoding="utf-8")
            chk = _run_bounded_subprocess(
                [rt_info["executable"], "--check", str(src_file)],
                cwd=tmp_path,
                timeout_sec=timeout_sec,
                max_output_chars=max_output_chars,
            )
            if chk["returncode"] != 0:
                err = {
                    "category": "syntax_error",
                    "message": chk["stderr"].strip() or "JavaScript syntax check failed.",
                    "why": "Node reported a syntax error before execution.",
                    "hint": "Fix the reported syntax error and re-run.",
                }
                result_payload["ok"] = False
                result_payload["compilation_error"] = err
                result_payload["first_error"] = err
                result_payload["execution_status"] = "syntax_error"
                result_payload["suggested_result"] = "fail"
                return _maybe_record_code_evidence(
                    result_payload,
                    record_evidence=record_evidence,
                    session_dir=session_dir,
                    topic_num=topic_num,
                    objective_id=objective_id,
                    assessment_type=assessment_type,
                    now=now,
                )
            exe_cmd_base = [rt_info["executable"], str(src_file)]
        elif lang in ("c", "cpp"):
            ext = ".c" if lang == "c" else ".cpp"
            src_file = tmp_path / f"solution{ext}"
            bin_file = tmp_path / ("solution.exe" if os.name == "nt" else "solution")
            src_file.write_text(source_text, encoding="utf-8")
            comp_name = Path(rt_info["compiler"]).stem.lower()
            if comp_name == "cl":
                comp_cmd = [rt_info["compiler"], "/nologo", str(src_file), f"/Fe:{bin_file}"]
            else:
                comp_cmd = [rt_info["compiler"], "-Wall", "-Wextra", str(src_file), "-o", str(bin_file)]
            comp = _run_bounded_subprocess(
                comp_cmd,
                cwd=tmp_path,
                timeout_sec=max(timeout_sec, 5.0),
                max_output_chars=max_output_chars,
            )
            if comp["returncode"] != 0:
                err = {
                    "category": "compilation_error",
                    "message": (comp["stderr"] or comp["stdout"]).strip() or "Compilation failed.",
                    "why": f"The {lang.upper()} compiler rejected the program.",
                    "hint": "Address the first compiler error line reported above.",
                }
                result_payload["ok"] = False
                result_payload["compilation_error"] = err
                result_payload["first_error"] = result_payload["first_error"] or err
                result_payload["execution_status"] = "compilation_error"
                result_payload["suggested_result"] = "fail"
                return _maybe_record_code_evidence(
                    result_payload,
                    record_evidence=record_evidence,
                    session_dir=session_dir,
                    topic_num=topic_num,
                    objective_id=objective_id,
                    assessment_type=assessment_type,
                    now=now,
                )
            exe_cmd_base = [str(bin_file)]
        elif lang == "java":
            src_file = tmp_path / "Main.java"
            src_file.write_text(source_text, encoding="utf-8")
            comp = _run_bounded_subprocess(
                [rt_info["compiler"], str(src_file)],
                cwd=tmp_path,
                timeout_sec=max(timeout_sec, 5.0),
                max_output_chars=max_output_chars,
            )
            if comp["returncode"] != 0:
                err = {
                    "category": "compilation_error",
                    "message": (comp["stderr"] or comp["stdout"]).strip() or "Java compilation failed.",
                    "why": "javac rejected Main.java.",
                    "hint": "Ensure public class Main matches Main.java and fix the first compiler error.",
                }
                result_payload["ok"] = False
                result_payload["compilation_error"] = err
                result_payload["first_error"] = err
                result_payload["execution_status"] = "compilation_error"
                result_payload["suggested_result"] = "fail"
                return _maybe_record_code_evidence(
                    result_payload,
                    record_evidence=record_evidence,
                    session_dir=session_dir,
                    topic_num=topic_num,
                    objective_id=objective_id,
                    assessment_type=assessment_type,
                    now=now,
                )
            exe_cmd_base = [rt_info["executable"], "-cp", str(tmp_path), "Main"]

        cases = list(test_cases or [{"name": "default_run", "stdin": "", "kind": "example"}])
        results: list[dict[str, Any]] = []
        first_runtime_or_logic_err: dict[str, Any] | None = None
        example_total = 0
        example_pass = 0
        edge_total = 0
        edge_pass = 0

        for idx, tc in enumerate(cases, start=1):
            kind = str(tc.get("kind") or ("edge" if tc.get("hidden") or tc.get("edge") else "example"))
            tc_name = str(tc.get("name") or f"test_{idx}")
            if kind in ("edge", "hidden"):
                edge_total += 1
            else:
                example_total += 1

            # Python function-call harness support
            if lang == "python" and "call" in tc:
                harness = (
                    "import importlib.util\n"
                    "import json\n"
                    f"_spec = importlib.util.spec_from_file_location('solution', {str(src_file)!r})\n"
                    "_mod = importlib.util.module_from_spec(_spec)\n"
                    "_spec.loader.exec_module(_mod)\n"
                    f"fn = getattr(_mod, {tc['call']!r})\n"
                    f"res = fn(*{list(tc.get('args', []))!r})\n"
                    "print(json.dumps(res))\n"
                )
                harness_file = tmp_path / f"_harness_{idx}.py"
                harness_file.write_text(harness, encoding="utf-8")
                run_res = _run_bounded_subprocess(
                    [rt_info["executable"], "-I", str(harness_file)],
                    cwd=tmp_path,
                    stdin_text=str(tc.get("stdin") or ""),
                    timeout_sec=timeout_sec,
                    max_output_chars=max_output_chars,
                )
                expected_val = tc.get("expected_return")
                passed = False
                actual_val: Any = run_res["stdout"].strip()
                if run_res["returncode"] == 0 and not run_res["timed_out"]:
                    try:
                        parsed_ret = json.loads(run_res["stdout"].strip())
                        actual_val = parsed_ret
                        passed = parsed_ret == expected_val
                    except json.JSONDecodeError:
                        passed = False
            else:
                run_res = _run_bounded_subprocess(
                    exe_cmd_base,
                    cwd=tmp_path,
                    stdin_text=str(tc.get("stdin") or ""),
                    timeout_sec=timeout_sec,
                    max_output_chars=max_output_chars,
                )
                expected_out = tc.get("expected_stdout")
                expected_val = expected_out
                actual_val = run_res["stdout"]
                if run_res["timed_out"] or run_res["returncode"] != 0:
                    passed = False
                elif expected_out is None:
                    passed = True
                else:
                    passed = _normalize_output(run_res["stdout"]) == _normalize_output(str(expected_out))

            if run_res["timed_out"] or run_res["returncode"] != 0:
                err_cat = "runtime_error"
                err_msg = run_res["stderr"].strip() or f"Process exited with code {run_res['returncode']}"
                if first_runtime_or_logic_err is None:
                    first_runtime_or_logic_err = {
                        "category": err_cat,
                        "test": tc_name,
                        "message": err_msg,
                        "why": "Execution timed out." if run_res["timed_out"] else "Program terminated abnormally at runtime.",
                        "hint": "Check loop termination, recursion base cases, or invalid memory/index accesses.",
                    }
                    result_payload["runtime_error"] = first_runtime_or_logic_err
            elif not passed:
                if first_runtime_or_logic_err is None:
                    first_runtime_or_logic_err = {
                        "category": "logical_error",
                        "test": tc_name,
                        "message": f"Output mismatch on {tc_name}: got {actual_val!r}, expected {expected_val!r}.",
                        "why": "The program ran without crashing but produced an incorrect result.",
                        "hint": "Trace the failing input step by step and compare variable values.",
                    }

            if passed:
                if kind in ("edge", "hidden"):
                    edge_pass += 1
                else:
                    example_pass += 1

            results.append(
                {
                    "name": tc_name,
                    "kind": kind,
                    "passed": passed,
                    "timed_out": run_res["timed_out"],
                    "returncode": run_res["returncode"],
                    "stdout": run_res["stdout"],
                    "stderr": run_res["stderr"],
                    "output_truncated": run_res["output_truncated"],
                }
            )

        passed_count = sum(1 for r in results if r["passed"])
        total_count = len(results)
        result_payload["execution_performed"] = True
        result_payload["execution_status"] = "executed"
        result_payload["test_results"] = results
        result_payload["tests_passed"] = passed_count
        result_payload["tests_total"] = total_count
        result_payload["example_tests_passed"] = (example_pass == example_total) if example_total else None
        result_payload["edge_tests_passed"] = (edge_pass == edge_total) if edge_total else None

        if passed_count == total_count:
            result_payload["ok"] = True
            result_payload["suggested_result"] = "pass"
            result_payload["verification_scope"] = (
                "verified_with_edge_cases" if edge_total > 0 else "partial_sample_only"
            )
        elif example_total > 0 and example_pass == example_total and edge_total > 0 and edge_pass < edge_total:
            result_payload["ok"] = False
            result_payload["suggested_result"] = "partial"
            result_payload["verification_scope"] = "passed_example_failed_edge"
            result_payload["first_error"] = first_runtime_or_logic_err
        else:
            result_payload["ok"] = False
            result_payload["suggested_result"] = "fail"
            result_payload["verification_scope"] = "failed_tests"
            result_payload["first_error"] = result_payload["first_error"] or first_runtime_or_logic_err

    return _maybe_record_code_evidence(
        result_payload,
        record_evidence=record_evidence,
        session_dir=session_dir,
        topic_num=topic_num,
        objective_id=objective_id,
        assessment_type=assessment_type,
        now=now,
    )


def _maybe_record_code_evidence(
    payload: dict[str, Any],
    *,
    record_evidence: bool,
    session_dir: Path | None,
    topic_num: str | None,
    objective_id: str | None,
    assessment_type: str,
    now: str | None,
) -> dict[str, Any]:
    if not record_evidence or session_dir is None or not topic_num:
        payload["evidence_recorded"] = False
        return payload
    res_val = payload["suggested_result"]
    if res_val == "skipped":
        payload["evidence_recorded"] = False
        return payload

    rationale = (
        f"Code check ({payload['language']}): {payload['tests_passed']}/{payload['tests_total']} tests passed "
        f"[{payload['verification_scope']}]"
    )
    if payload.get("first_error"):
        rationale += f"; first issue: {payload['first_error'].get('message', '')[:120]}"

    ev_out = record_assessment_event(
        session_dir,
        topic=topic_num,
        objective=objective_id,
        result=res_val,
        assistance=payload["suggested_assistance"],
        assessment_type=assessment_type,
        rationale=rationale,
        now=now,
        checked=bool(payload["execution_performed"]),
    )
    payload["evidence_recorded"] = True
    payload["assessment_event"] = ev_out
    return payload
