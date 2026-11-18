"""Intelligent, explainable teaching modality router for TeachMe.

Decides *how* to teach or assess the active objective based on concept type,
learner proficiency, prerequisite states, recent errors, time budget, host/terminal
capabilities, and explicit learner preferences. Completely separate from source
resolution (`resolve-sources`).
"""

from __future__ import annotations

import re
from typing import Any, Mapping, Sequence

from .terminal_caps import detect_host_capabilities, detect_terminal_capabilities

SUPPORTED_MODALITIES = (
    "direct_explanation",
    "first_principles_derivation",
    "worked_example",
    "socratic_questioning",
    "adaptive_quiz",
    "error_detection_challenge",
    "terminal_graph",
    "text_diagram",
    "interactive_simulation",
    "retrieved_web_image",
    "code_execution_trace",
    "feynman_explanation",
    "transfer_application",
    "spaced_retrieval",
)

CONCEPT_TYPES = (
    "definition",
    "mathematical_function",
    "optimization_dynamics",
    "algorithm_stepwise",
    "memory_pointer_code",
    "probability_experiment",
    "spatial_real_world",
    "conceptual_mechanism",
)

_MODALITY_COST: dict[str, str] = {
    "direct_explanation": "low",
    "socratic_questioning": "low",
    "adaptive_quiz": "low",
    "error_detection_challenge": "low",
    "spaced_retrieval": "low",
    "feynman_explanation": "low",
    "worked_example": "medium",
    "first_principles_derivation": "medium",
    "text_diagram": "low",
    "code_execution_trace": "medium",
    "transfer_application": "medium",
    "terminal_graph": "medium",
    "interactive_simulation": "high",
    "retrieved_web_image": "high",
}

_DEFINITION_PAT = re.compile(
    r"\b(?:what\s+is|define|definition\s+of|meaning\s+of|difference\s+between\s+terms|simple\s+definition|terminology|glossary\s+term)\b",
    re.IGNORECASE,
)


def infer_concept_type(objective_desc: str, topic_title: str = "") -> str:
    """Heuristically classify an objective into a canonical concept type."""
    combined = f"{topic_title} {objective_desc}".strip().lower()
    if not combined:
        return "conceptual_mechanism"

    if _DEFINITION_PAT.search(combined) and not any(
        k in combined for k in ("gradient", "sort", "pointer", "curve", "plot", "bernoulli", "anatomy")
    ):
        return "definition"

    if any(k in combined for k in ("gradient descent", "learning rate", "step size", "loss landscape", "converge", "diverge", "optimization step")):
        return "optimization_dynamics"

    if any(k in combined for k in ("bubble sort", "selection sort", "insertion sort", "sorting", "quicksort", "mergesort", "swap", "array pass")):
        return "algorithm_stepwise"

    if any(k in combined for k in ("pointer", "dereferenc", "address-of", "&x", "*p", "null pointer", "memory address", "c pointers")):
        return "memory_pointer_code"

    if any(k in combined for k in ("bernoulli", "coin flip", "coin toss", "empirical frequency", "law of large numbers", "sample size", "trials")):
        return "probability_experiment"

    if any(k in combined for k in ("anatomy", "ventricle", "aorta", "neuron structure", "organ", "microscop", "geological", "rock strata", "hardware port", "motherboard", "pinout")):
        return "spatial_real_world"

    if any(
        k in combined
        for k in (
            "graph", "plot", "curve", "asymptot", "extrema", "local minimum",
            "derivative", "loss function", "sigmoid", "exponential", "logarithm",
            "sine", "cosine", "parabola", "histogram", "distribution", "trajectory",
        )
    ):
        return "mathematical_function"

    return "conceptual_mechanism"


def _match_simulation_template(concept_type: str, text: str) -> str | None:
    low = text.lower()
    if concept_type == "optimization_dynamics" or "gradient descent" in low:
        return "gradient_descent"
    if concept_type == "algorithm_stepwise" or any(k in low for k in ("bubble sort", "selection sort", "insertion sort", "sorting")):
        return "sorting"
    if concept_type == "memory_pointer_code" or "pointer" in low:
        return "c_pointers"
    if concept_type == "probability_experiment" or "bernoulli" in low or "empirical frequency" in low:
        return "probability"
    return None


def _normalize_preference(raw: str | None) -> str:
    val = str(raw or "").strip().lower()
    aliases = {
        "explain": "direct_explanation",
        "just explain": "direct_explanation",
        "direct": "direct_explanation",
        "direct_explanation": "direct_explanation",
        "definition": "direct_explanation",
        "derivation": "first_principles_derivation",
        "first_principles": "first_principles_derivation",
        "example": "worked_example",
        "worked_example": "worked_example",
        "socratic": "socratic_questioning",
        "quiz": "adaptive_quiz",
        "practice": "adaptive_quiz",
        "drill": "adaptive_quiz",
        "graph": "terminal_graph",
        "plot": "terminal_graph",
        "diagram": "text_diagram",
        "sim": "interactive_simulation",
        "simulation": "interactive_simulation",
        "interactive_simulation": "interactive_simulation",
        "image": "retrieved_web_image",
        "photo": "retrieved_web_image",
        "trace": "code_execution_trace",
        "code": "code_execution_trace",
        "feynman": "feynman_explanation",
        "transfer": "transfer_application",
        "review": "spaced_retrieval",
    }
    return aliases.get(val, val if val in SUPPORTED_MODALITIES else "")


def _pick_alternative_after_error(
    *,
    last_modality: str,
    concept_type: str,
    sim_template: str | None,
    has_missing_prereq: bool,
    terminal_width: int,
) -> tuple[str, str, str]:
    """Select a genuinely different teaching approach when prior attempts failed."""
    if has_missing_prereq:
        return (
            "first_principles_derivation",
            "prerequisite_repair",
            "Repeated errors suggest a prerequisite gap; step back to foundational intuition before resuming.",
        )

    candidates: list[tuple[str, str, str]] = []
    if concept_type == "memory_pointer_code":
        candidates.extend(
            [
                ("code_execution_trace", "misconception_remediation", "Trace variable values and pointer targets step by step."),
                ("text_diagram", "misconception_remediation", "Draw named variable/address/target boxes to repair pointer mental model."),
                ("error_detection_challenge", "misconception_remediation", "Spot the faulty dereference or pointer reassignment."),
            ]
        )
    elif sim_template is not None:
        candidates.extend(
            [
                ("interactive_simulation", "predict_observe_explain", "Use Predict -> Observe -> Explain in a bounded simulation to confront the misconception."),
                ("worked_example", "worked_example_fading", "Walk through a concrete step-by-step worked example."),
                ("error_detection_challenge", "misconception_remediation", "Diagnose a targeted error in a similar worked step."),
            ]
        )
    elif concept_type == "mathematical_function" and terminal_width >= 30:
        candidates.extend(
            [
                ("terminal_graph", "misconception_remediation", "Plot the computed curve to make the behavior concrete."),
                ("worked_example", "worked_example_fading", "Substitute concrete numbers step by step."),
                ("error_detection_challenge", "misconception_remediation", "Identify the first wrong algebraic or sign step."),
            ]
        )
    else:
        candidates.extend(
            [
                ("worked_example", "worked_example_fading", "Switch from abstract explanation to a concrete worked example."),
                ("error_detection_challenge", "misconception_remediation", "Contrast a common wrong step against the true mechanism."),
                ("socratic_questioning", "misconception_remediation", "Use targeted probing on the exact failing step."),
                ("first_principles_derivation", "first_principles", "Rebuild the causal chain from basic assumptions."),
            ]
        )

    for mod, ped, why in candidates:
        if mod != last_modality:
            return mod, ped, why
    return candidates[0]


def select_teaching_modality(
    *,
    objective_desc: str,
    topic_title: str = "",
    objective_id: str = "",
    concept_type: str = "",
    proficiency_status: str = "untested",
    transfer_status: str = "untested",
    prerequisite_states: Mapping[str, Any] | None = None,
    recent_events: Sequence[Mapping[str, Any]] | None = None,
    is_due_review: bool = False,
    difficulty: str = "medium",
    abstraction: str = "medium",
    time_budget_minutes: int | None = None,
    explicit_preference: str | None = None,
    last_modality: str = "",
    host_capabilities: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Deterministically select the best teaching modality with clear rationale and fallbacks."""
    caps = dict(host_capabilities) if host_capabilities is not None else detect_host_capabilities(
        terminal_caps=detect_terminal_capabilities()
    )
    term = dict(caps.get("terminal") or detect_terminal_capabilities())
    term_width = int(term.get("width", 80))
    is_interactive = bool(term.get("interactive", False))
    image_search_avail = bool(caps.get("image_search", False))

    ctype = concept_type.strip().lower() if concept_type.strip().lower() in CONCEPT_TYPES else infer_concept_type(
        objective_desc, topic_title
    )
    combined_text = f"{topic_title} {objective_desc}".strip()
    sim_template = _match_simulation_template(ctype, combined_text)
    pref = _normalize_preference(explicit_preference)

    events = list(recent_events or [])
    consecutive_failures = 0
    for ev in reversed(events):
        res = str(ev.get("result") or ev.get("status") or "").lower()
        if res in ("fail", "retry", "partial"):
            consecutive_failures += 1
        elif res == "pass":
            break

    prereqs = dict(prerequisite_states or {})
    missing_prereq = any(
        isinstance(v, Mapping) and str(v.get("state") or "") == "needs_support"
        for v in prereqs.values()
    )

    selected = "direct_explanation"
    pedagogical_method = "first_principles"
    rationale = ""
    fallbacks: list[str] = []
    recommended_asset: dict[str, Any] | None = None

    # 1. Explicit learner request (explain-on-request takes top priority)
    if pref == "direct_explanation":
        selected = "direct_explanation"
        pedagogical_method = "explain_on_request"
        rationale = "Learner explicitly requested a direct explanation; answer clearly without forcing a quiz or simulation."
        fallbacks = ["worked_example"]
    elif pref:
        if pref == "retrieved_web_image" and not image_search_avail:
            selected = "text_diagram"
            pedagogical_method = "capability_fallback"
            rationale = "Learner requested an image, but host image_search is unavailable; falling back to labeled text diagram."
            fallbacks = ["direct_explanation"]
        elif pref == "interactive_simulation":
            selected = "interactive_simulation"
            pedagogical_method = "predict_observe_explain"
            rationale = "Learner requested an interactive simulation."
            if sim_template:
                recommended_asset = {"kind": "simulation", "template": sim_template, "non_interactive_demo": not is_interactive}
            fallbacks = ["terminal_graph", "worked_example"]
        elif pref == "terminal_graph" and term_width < 30:
            selected = "direct_explanation"
            pedagogical_method = "capability_fallback"
            rationale = "Terminal width < 30 columns is too narrow for a readable plot; using concise text explanation."
            fallbacks = ["text_diagram"]
        else:
            selected = pref
            pedagogical_method = "learner_preference"
            rationale = f"Selected '{pref}' matching explicit learner preference."
            fallbacks = ["direct_explanation", "worked_example"]

    # 2. Due spaced review -> unaided retrieval first
    elif is_due_review:
        selected = "spaced_retrieval"
        pedagogical_method = "unaided_spaced_retrieval"
        rationale = "Objective is due for spaced review; prompt unaided retrieval before any recap."
        fallbacks = ["adaptive_quiz", "direct_explanation"]

    # 3. Repeated errors / weakened proficiency -> genuine modality switch
    elif consecutive_failures >= 1 or proficiency_status == "weakened" or missing_prereq:
        selected, pedagogical_method, rationale = _pick_alternative_after_error(
            last_modality=last_modality,
            concept_type=ctype,
            sim_template=sim_template,
            has_missing_prereq=missing_prereq,
            terminal_width=term_width,
        )
        if selected == "interactive_simulation" and sim_template:
            recommended_asset = {"kind": "simulation", "template": sim_template, "non_interactive_demo": not is_interactive}
        fallbacks = ["worked_example", "direct_explanation"]

    # 4. Simple definitions or low-benefit narrow questions -> cheap direct text
    elif ctype == "definition" or (difficulty == "low" and abstraction == "low" and ctype == "conceptual_mechanism"):
        selected = "direct_explanation"
        pedagogical_method = "first_principles"
        rationale = "Simple definition or low-complexity concept is clearest as concise text; no visual, simulation, or forced quiz needed."
        fallbacks = ["worked_example"]

    # 5. Transfer check for independently demonstrated objective
    elif proficiency_status == "demonstrated_independently" and transfer_status != "demonstrated":
        selected = "transfer_application"
        pedagogical_method = "transfer_check"
        rationale = "Objective already demonstrated independently; test transfer in an unfamiliar reasoning context."
        fallbacks = ["feynman_explanation", "adaptive_quiz"]

    # 6. Domain-driven high-value visuals / simulations / traces
    elif ctype == "spatial_real_world":
        if image_search_avail:
            selected = "retrieved_web_image"
            pedagogical_method = "visual_observation"
            rationale = "Real-world spatial/anatomical recognition benefits from a verified labeled reference image."
            recommended_asset = {"kind": "web_image"}
            fallbacks = ["text_diagram", "direct_explanation"]
        else:
            selected = "text_diagram"
            pedagogical_method = "capability_fallback"
            rationale = "Spatial concept would benefit from an image, but image_search is unavailable; using labeled ASCII/Unicode diagram."
            fallbacks = ["direct_explanation"]

    elif ctype in ("optimization_dynamics", "algorithm_stepwise", "probability_experiment") and (
        time_budget_minutes is None or time_budget_minutes >= 5
    ):
        selected = "interactive_simulation"
        pedagogical_method = "predict_observe_explain"
        rationale = (
            f"Concept type '{ctype}' has dynamic parameter/step behavior where Predict -> Observe -> Explain "
            "materially clarifies the mechanism."
        )
        recommended_asset = {
            "kind": "simulation",
            "template": sim_template,
            "non_interactive_demo": not is_interactive,
        }
        fallbacks = ["terminal_graph", "worked_example", "direct_explanation"]

    elif ctype == "memory_pointer_code":
        if sim_template == "c_pointers" and proficiency_status in ("untested", "introduced") and (
            time_budget_minutes is None or time_budget_minutes >= 5
        ):
            selected = "code_execution_trace"
            pedagogical_method = "predict_observe_explain"
            rationale = "Pointer/variable mutation requires an accurate variable/address/target trace rather than abstract prose."
            recommended_asset = {
                "kind": "simulation",
                "template": "c_pointers",
                "non_interactive_demo": not is_interactive,
            }
            fallbacks = ["text_diagram", "interactive_simulation", "worked_example"]
        else:
            selected = "code_execution_trace"
            pedagogical_method = "worked_example_fading"
            rationale = "Program/pointer state transitions are clearest via step-by-step variable/address/target tracing."
            fallbacks = ["text_diagram", "worked_example"]

    elif ctype == "mathematical_function":
        if term_width >= 30 and (time_budget_minutes is None or time_budget_minutes >= 3):
            selected = "terminal_graph"
            pedagogical_method = "first_principles"
            rationale = "Computed 2D terminal graph reveals function shape, extrema, and behavior accurately."
            recommended_asset = {"kind": "terminal_graph"}
            fallbacks = ["first_principles_derivation", "worked_example"]
        else:
            selected = "first_principles_derivation"
            pedagogical_method = "first_principles"
            rationale = "Narrow terminal or tight time budget; teach mathematical behavior directly via intuition and key values."
            fallbacks = ["direct_explanation"]

    # 7. Practiced with support -> ready for independent adaptive quiz or Feynman check
    elif proficiency_status == "practiced_with_support":
        selected = "adaptive_quiz"
        pedagogical_method = "worked_example_fading"
        rationale = "Learner has only assisted passes so far; assign a fresh unaided problem to check independent mastery."
        fallbacks = ["feynman_explanation", "worked_example"]

    # 8. General conceptual mechanism: prefer low/medium-cost direct or first-principles explanation
    else:
        if difficulty == "high" or abstraction == "high":
            selected = "first_principles_derivation"
            pedagogical_method = "first_principles"
            rationale = "Abstract mechanism benefits from first-principles intuition before formalism; no forced visual or quiz."
            fallbacks = ["worked_example", "direct_explanation"]
        else:
            selected = "direct_explanation"
            pedagogical_method = "first_principles"
            rationale = "Evidence for heavy visual or simulation benefit is weak; prefer concise first-principles text."
            fallbacks = ["worked_example", "socratic_questioning"]

    return {
        "objective_id": objective_id,
        "concept_type": ctype,
        "selected_modality": selected,
        "fallback_modalities": fallbacks,
        "pedagogical_method": pedagogical_method,
        "estimated_cost": _MODALITY_COST.get(selected, "low"),
        "requires_visual": selected in ("terminal_graph", "text_diagram", "retrieved_web_image"),
        "requires_simulation": selected == "interactive_simulation",
        "requires_quiz": selected in ("adaptive_quiz", "spaced_retrieval", "error_detection_challenge", "transfer_application"),
        "recommended_asset": recommended_asset,
        "rationale": rationale,
        "capabilities_snapshot": {
            "terminal_width": term_width,
            "interactive": is_interactive,
            "image_search": image_search_avail,
            "no_color": bool(term.get("no_color", False)),
        },
    }
