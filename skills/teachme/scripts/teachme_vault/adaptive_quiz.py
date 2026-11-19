"""Adaptive question selection and deterministic answer verification for TeachMe."""

from __future__ import annotations

from fractions import Fraction
import math
import re
from typing import Any, Mapping, Sequence

from .terminal_graph import compile_safe_math_expr

DIFFICULTY_LEVELS: dict[int, dict[str, Any]] = {
    1: {
        "level": 1,
        "name": "Foundation",
        "description": "Definitions, basic understanding, and direct application.",
        "question_types": [
            "multiple_choice",
            "short_conceptual",
            "numerical_calculation",
            "prediction",
            "predict_output",
            "worked_example_completion",
        ],
    },
    2: {
        "level": 2,
        "name": "Reasoning",
        "description": "Explanation, multi-step application, comparisons, and debugging.",
        "question_types": [
            "independent_application",
            "fill_missing_step",
            "find_first_error",
            "debug_program",
            "method_justification",
            "concept_comparison",
        ],
    },
    3: {
        "level": 3,
        "name": "Mastery and transfer",
        "description": "Edge cases, unfamiliar contexts, counterexamples, and assumption failures.",
        "question_types": [
            "violated_assumption",
            "counterexample",
            "why_tempting_fails",
            "feynman_explanation",
            "transfer",
        ],
    },
}


def select_question_plan(
    objective: Mapping[str, Any],
    *,
    recent_events: Sequence[Mapping[str, Any]] | None = None,
    due_item: Mapping[str, Any] | None = None,
    requested_tier: int | None = None,
    concept_type: str = "",
    learner_request: str = "",
) -> dict[str, Any]:
    """Select adaptive difficulty level (1-3) and question type(s) from objective evidence.

    Never advances difficulty based on assisted successes alone.
    """
    req_low = (learner_request or "").strip().lower()
    if req_low in ("explain", "just explain", "just show me", "direct_explanation"):
        return {
            "objective_id": objective.get("id") or objective.get("objective_id") or "",
            "skip_quiz": True,
            "reason": "Learner explicitly requested a direct explanation; explain directly without forcing a quiz.",
            "level": 1,
            "level_name": DIFFICULTY_LEVELS[1]["name"],
            "recommended_types": [],
            "assistance_expectation": "worked_example",
        }

    prof = dict(objective.get("proficiency") or {})
    prof_status = str(prof.get("status") or objective.get("proficiency_status") or "untested")
    indep_count = int(prof.get("independent_successes", 0))
    assist_count = int(prof.get("assisted_successes", 0))
    failures = int(prof.get("failures", 0))
    transfer_status = str((prof.get("transfer") or {}).get("status") or objective.get("transfer_status") or "untested")
    retention_status = str((prof.get("retention") or {}).get("status") or objective.get("retention_status") or "untested")

    events = list(recent_events or [])
    last_type = str(events[-1].get("assessment_type") or "") if events else ""
    recent_fail = any(
        str(ev.get("result") or ev.get("status") or "").lower() in ("fail", "retry")
        for ev in events[-2:]
    )

    if due_item is not None:
        return {
            "objective_id": objective.get("id") or objective.get("objective_id") or "",
            "skip_quiz": False,
            "level": 2 if indep_count >= 1 else 1,
            "level_name": DIFFICULTY_LEVELS[2 if indep_count >= 1 else 1]["name"],
            "recommended_types": ["delayed_recall"],
            "primary_type": "delayed_recall",
            "assistance_expectation": "none",
            "reason": "Objective is due for spaced review; begin with unaided delayed_recall before any recap.",
            "avoid_repeating_basics": indep_count >= 1,
        }

    # Determine adaptive level strictly from independent evidence
    if requested_tier in (1, 2, 3):
        level = int(requested_tier)
        reason = f"Explicitly requested Tier {level} ({DIFFICULTY_LEVELS[level]['name']})."
    elif prof_status == "weakened" or recent_fail:
        level = 1 if indep_count == 0 else 2
        reason = "Recent error or weakened state detected; target remediation on the specific misconception before advancing."
    elif indep_count == 0:
        # Assisted passes alone NEVER advance beyond Level 1!
        level = 1
        if assist_count > 0:
            reason = (
                "Prior successes were assisted only; remain at Level 1 with a fresh unaided check "
                "before advancing difficulty."
            )
        else:
            reason = "Objective has no independent demonstrations yet; start at Level 1 (Foundation)."
    elif indep_count == 1 and transfer_status != "demonstrated":
        level = 2
        reason = "1 independent foundation demonstration recorded; advance to Level 2 (Reasoning) and skip basic recall."
    else:
        level = 3
        reason = "Independent reasoning demonstrated; advance to Level 3 (Mastery and transfer)."

    pool = list(DIFFICULTY_LEVELS[level]["question_types"])
    ctype = (concept_type or "").strip().lower()

    # Tailor ordering to concept type and remediation need
    prioritized: list[str] = []
    if prof_status == "weakened" or recent_fail:
        prioritized = ["find_first_error", "why_tempting_fails", "worked_example_completion"]
    elif ctype in ("memory_pointer_code", "algorithm_stepwise"):
        if level == 1:
            prioritized = ["predict_output", "multiple_choice", "worked_example_completion"]
        elif level == 2:
            prioritized = ["debug_program", "find_first_error", "independent_application"]
        else:
            prioritized = ["violated_assumption", "counterexample", "transfer"]
    elif ctype in ("mathematical_function", "optimization_dynamics", "probability_experiment"):
        if level == 1:
            prioritized = ["prediction", "numerical_calculation", "multiple_choice"]
        elif level == 2:
            prioritized = ["independent_application", "fill_missing_step", "find_first_error", "method_justification"]
        else:
            prioritized = ["violated_assumption", "counterexample", "transfer"]
    elif ctype == "definition":
        prioritized = ["short_conceptual", "multiple_choice", "concept_comparison"]
    else:
        prioritized = list(pool)

    # Merge remaining pool items while avoiding immediate repetition of last_type
    ordered = [t for t in prioritized if t in pool or prof_status == "weakened" or recent_fail]
    for t in pool:
        if t not in ordered:
            ordered.append(t)
    if len(ordered) > 1 and ordered[0] == last_type:
        ordered = ordered[1:] + [ordered[0]]

    return {
        "objective_id": objective.get("id") or objective.get("objective_id") or "",
        "skip_quiz": False,
        "level": level,
        "level_name": DIFFICULTY_LEVELS[level]["name"],
        "primary_type": ordered[0],
        "recommended_types": ordered[:3],
        "assistance_expectation": "none",
        "avoid_repeating_basics": indep_count >= 1,
        "assisted_only_gate_active": assist_count > 0 and indep_count == 0,
        "retention_status": retention_status,
        "transfer_status": transfer_status,
        "failures": failures,
        "reason": reason,
    }


def _parse_numeric(raw: str) -> float | None:
    text = str(raw or "").strip().replace(",", "")
    if not text:
        return None
    m = re.search(r"-?\d+(?:\.\d+)?(?:/\d+(?:\.\d+)?)?", text)
    if not m:
        return None
    token = m.group(0)
    try:
        if "/" in token:
            return float(Fraction(token))
        val = float(token)
        return val if math.isfinite(val) else None
    except (ValueError, ZeroDivisionError):
        return None


def evaluate_learner_response(
    question_spec: Mapping[str, Any],
    learner_answer: str,
) -> dict[str, Any]:
    """Deterministically verify objective answers when possible and give targeted feedback.

    Never fabricates grades or uses naive keyword matching as sole verification for complex
    conceptual explanations. Avoids generic praise.
    """
    ans = str(learner_answer or "").strip()
    kind = str(question_spec.get("kind") or "conceptual").strip().lower()
    prereq_hint = str(question_spec.get("prerequisite_hint") or "").strip() or None
    alt_expl = str(question_spec.get("alternative_explanation") or "").strip()
    first_err_hint = str(question_spec.get("first_error_hint") or "").strip()

    if not ans:
        return {
            "outcome": "unassessed",
            "suggested_result": "skipped",
            "verified": False,
            "verification_mode": "empty_response",
            "specific_error": "No answer was provided.",
            "indicates_missing_prerequisite": False,
            "suggested_prerequisite": prereq_hint,
            "next_step": "hint",
            "hint_or_alternative": first_err_hint or "Attempt the first step or reply 'explain' for a direct explanation.",
            "followup_needed": True,
        }

    if kind == "numeric":
        expected = float(question_spec["expected"])
        tol = float(question_spec.get("tolerance", 1e-3))
        got = _parse_numeric(ans)
        if got is None:
            return {
                "outcome": "incorrect",
                "suggested_result": "fail",
                "verified": True,
                "verification_mode": "deterministic_numeric",
                "specific_error": f"Could not parse a numeric value from {ans!r}.",
                "indicates_missing_prerequisite": bool(prereq_hint),
                "suggested_prerequisite": prereq_hint,
                "next_step": "hint",
                "hint_or_alternative": first_err_hint or "Write your final numerical value explicitly.",
                "followup_needed": True,
            }
        err = abs(got - expected)
        if err <= tol:
            return {
                "outcome": "correct",
                "suggested_result": "pass",
                "verified": True,
                "verification_mode": "deterministic_numeric",
                "specific_error": "",
                "indicates_missing_prerequisite": False,
                "suggested_prerequisite": None,
                "next_step": "advance_difficulty",
                "hint_or_alternative": f"Verified numerically: {got} matches expected {expected} (within {tol}).",
                "followup_needed": False,
            }
        # Detect common sign flip or close approximation
        if expected != 0 and abs(got + expected) <= tol:
            err_msg = f"Sign error: got {got}, expected {expected}."
        elif err <= max(tol * 10.0, 0.05 * abs(expected)):
            return {
                "outcome": "partially_correct",
                "suggested_result": "partial",
                "verified": True,
                "verification_mode": "deterministic_numeric",
                "specific_error": f"Close numerical estimate ({got}), but outside tolerance {tol} of {expected}.",
                "indicates_missing_prerequisite": False,
                "suggested_prerequisite": None,
                "next_step": "fresh_followup",
                "hint_or_alternative": first_err_hint or "Re-check intermediate rounding or step arithmetic.",
                "followup_needed": True,
            }
        else:
            err_msg = f"Computed {got}, expected {expected}."
        return {
            "outcome": "incorrect",
            "suggested_result": "fail",
            "verified": True,
            "verification_mode": "deterministic_numeric",
            "specific_error": err_msg,
            "indicates_missing_prerequisite": bool(prereq_hint),
            "suggested_prerequisite": prereq_hint,
            "next_step": "prerequisite_repair" if prereq_hint else "alternative_explanation",
            "hint_or_alternative": alt_expl or first_err_hint or "Check the sign and substitution in each step.",
            "followup_needed": True,
        }

    if kind == "multiple_choice":
        expected_key = str(question_spec["expected"]).strip().upper()
        choices = dict(question_spec.get("choices") or {})
        norm_ans = ans.strip().upper()
        # Accept 'A' or 'A)' or 'A.' or matching choice text
        m = re.match(r"^([A-Z])(?:\)|\.|\s|$)", norm_ans)
        picked = m.group(1) if m else ""
        if not picked and choices:
            for k, v in choices.items():
                if str(v).strip().lower() == ans.lower():
                    picked = str(k).strip().upper()
                    break
        if picked == expected_key:
            return {
                "outcome": "correct",
                "suggested_result": "pass",
                "verified": True,
                "verification_mode": "deterministic_choice",
                "specific_error": "",
                "indicates_missing_prerequisite": False,
                "suggested_prerequisite": None,
                "next_step": "advance_difficulty",
                "hint_or_alternative": f"Option {expected_key} verified.",
                "followup_needed": False,
            }
        distractor_notes = dict(question_spec.get("distractor_errors") or {})
        specific = str(distractor_notes.get(picked) or f"Selected {picked or ans!r}; expected option {expected_key}.")
        return {
            "outcome": "incorrect",
            "suggested_result": "fail",
            "verified": True,
            "verification_mode": "deterministic_choice",
            "specific_error": specific,
            "indicates_missing_prerequisite": bool(prereq_hint),
            "suggested_prerequisite": prereq_hint,
            "next_step": "alternative_explanation",
            "hint_or_alternative": alt_expl or first_err_hint or "Compare the assumptions behind each option.",
            "followup_needed": True,
        }

    if kind == "math_expression":
        expected_expr = str(question_spec["expected"])
        sample_xs = list(question_spec.get("sample_points") or [-2.0, -0.5, 0.5, 1.5, 3.0])
        try:
            f_exp = compile_safe_math_expr(expected_expr)
            f_got = compile_safe_math_expr(ans)
        except ValueError as exc:
            return {
                "outcome": "incorrect",
                "suggested_result": "fail",
                "verified": True,
                "verification_mode": "deterministic_math_ast",
                "specific_error": f"Invalid expression: {exc}",
                "indicates_missing_prerequisite": bool(prereq_hint),
                "suggested_prerequisite": prereq_hint,
                "next_step": "hint",
                "hint_or_alternative": first_err_hint or "Write a valid expression in x.",
                "followup_needed": True,
            }
        diffs = []
        for xv in sample_xs:
            ye = f_exp(float(xv))
            yg = f_got(float(xv))
            if math.isfinite(ye) and math.isfinite(yg):
                diffs.append(abs(ye - yg))
        if diffs and all(d <= 1e-4 for d in diffs):
            return {
                "outcome": "correct",
                "suggested_result": "pass",
                "verified": True,
                "verification_mode": "deterministic_math_ast",
                "specific_error": "",
                "indicates_missing_prerequisite": False,
                "suggested_prerequisite": None,
                "next_step": "advance_difficulty",
                "hint_or_alternative": f"Expression '{ans}' matches expected '{expected_expr}' across test points.",
                "followup_needed": False,
            }
        return {
            "outcome": "incorrect",
            "suggested_result": "fail",
            "verified": True,
            "verification_mode": "deterministic_math_ast",
            "specific_error": f"Expression '{ans}' disagrees with expected '{expected_expr}' on sampled inputs.",
            "indicates_missing_prerequisite": bool(prereq_hint),
            "suggested_prerequisite": prereq_hint,
            "next_step": "alternative_explanation",
            "hint_or_alternative": alt_expl or first_err_hint or "Test your expression at x=1 and compare.",
            "followup_needed": True,
        }

    if kind == "exact_trace":
        expected_str = str(question_spec["expected"]).strip()
        norm_got = re.sub(r"\s+", " ", ans).strip().lower()
        norm_exp = re.sub(r"\s+", " ", expected_str).strip().lower()
        if norm_got == norm_exp:
            return {
                "outcome": "correct",
                "suggested_result": "pass",
                "verified": True,
                "verification_mode": "deterministic_trace",
                "specific_error": "",
                "indicates_missing_prerequisite": False,
                "suggested_prerequisite": None,
                "next_step": "advance_difficulty",
                "hint_or_alternative": f"Trace output '{expected_str}' verified.",
                "followup_needed": False,
            }
        return {
            "outcome": "incorrect",
            "suggested_result": "fail",
            "verified": True,
            "verification_mode": "deterministic_trace",
            "specific_error": f"Observed trace {ans!r} differs from expected {expected_str!r}.",
            "indicates_missing_prerequisite": bool(prereq_hint),
            "suggested_prerequisite": prereq_hint,
            "next_step": "hint",
            "hint_or_alternative": first_err_hint or "Trace each statement one line at a time.",
            "followup_needed": True,
        }

    # Complex conceptual / Feynman / transfer: NEVER use naive keyword matching as sole pass criterion!
    return {
        "outcome": "unassessed",
        "suggested_result": "skipped",
        "verified": False,
        "verification_mode": "rubric_review_required",
        "specific_error": "Free-form conceptual reasoning requires rubric inspection rather than keyword matching.",
        "indicates_missing_prerequisite": False,
        "suggested_prerequisite": prereq_hint,
        "next_step": "rubric_evaluation",
        "hint_or_alternative": (
            "Evaluate causal mechanism, unstated assumptions, symbol definitions, and edge cases "
            "against the active objective before calling `vault_cli.py assess`."
        ),
        "followup_needed": True,
    }
