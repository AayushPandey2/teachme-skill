"""Comprehensive tests for TeachMe NTT intelligent terminal-first teaching engine."""

from __future__ import annotations

import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "skills" / "teachme" / "scripts"
VAULT_CLI = SCRIPTS_DIR / "vault_cli.py"

if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from teachme_vault.adaptive_quiz import evaluate_learner_response, select_question_plan
from teachme_vault.media_retrieval import (
    build_image_query,
    evaluate_image_candidate,
    select_and_prepare_image,
    should_retrieve_image,
)
from teachme_vault.modality_router import select_teaching_modality
from teachme_vault.simulations import (
    MAX_STEPS_PER_RUN,
    create_simulation,
    run_interactive_cli,
    run_non_interactive_demo,
)
from teachme_vault.terminal_caps import detect_host_capabilities, detect_terminal_capabilities
from teachme_vault.terminal_graph import (
    compile_safe_math_expr,
    render_bar_chart,
    render_function_graph,
    render_histogram,
    render_optimization_trace,
    render_xy_graph,
)


def write_file(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def run_cli(*args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)
    return subprocess.run(
        [sys.executable, str(VAULT_CLI), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=merged_env,
        check=False,
    )


class TeachingEngineNTTTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="teachme_ntt_engine_"))
        self.cfg_path = self.tmp / "teachme-config.json"
        self.env = {"TEACHME_CONFIG_PATH": str(self.cfg_path)}

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _init_session(self, name: str, subtopics: list[dict]) -> Path:
        session = self.tmp / "notes" / name
        sub_file = self.tmp / f"{name}-subtopics.json"
        write_file(sub_file, json.dumps(subtopics))
        res = run_cli(
            "init",
            str(session),
            "--topic",
            name.replace("-", " ").title(),
            "--subtopics",
            str(sub_file),
            env=self.env,
        )
        self.assertEqual(res.returncode, 0, res.stderr)
        return session

    # 1. Simple definition selects text explanation
    def test_01_simple_definition_selects_text_explanation(self) -> None:
        decision = select_teaching_modality(
            objective_desc="Define what idempotency means in HTTP APIs",
            topic_title="REST Basics",
        )
        self.assertEqual(decision["concept_type"], "definition")
        self.assertEqual(decision["selected_modality"], "direct_explanation")
        self.assertEqual(decision["estimated_cost"], "low")
        self.assertFalse(decision["requires_visual"])
        self.assertFalse(decision["requires_simulation"])
        self.assertFalse(decision["requires_quiz"])

    # 2. Graph-heavy topic selects an appropriate graph when helpful
    def test_02_graph_heavy_topic_selects_terminal_graph(self) -> None:
        caps = detect_host_capabilities(
            terminal_caps=detect_terminal_capabilities(width=80, height=24, is_tty=True, interactive=True)
        )
        decision = select_teaching_modality(
            objective_desc="Analyze the local minimum and derivative behavior of the sigmoid curve and loss function",
            topic_title="Activation Functions",
            host_capabilities=caps,
        )
        self.assertEqual(decision["selected_modality"], "terminal_graph")
        self.assertTrue(decision["requires_visual"])
        self.assertEqual(decision["recommended_asset"]["kind"], "terminal_graph")

    # 3. Simulation-worthy topic selects a valid simulation
    def test_03_simulation_worthy_topic_selects_valid_simulation(self) -> None:
        gd = select_teaching_modality(
            objective_desc="Observe how learning rate affects gradient descent convergence and oscillation",
            topic_title="Gradient Descent",
        )
        self.assertEqual(gd["selected_modality"], "interactive_simulation")
        self.assertTrue(gd["requires_simulation"])
        self.assertEqual(gd["recommended_asset"]["template"], "gradient_descent")

        sort_dec = select_teaching_modality(
            objective_desc="Trace bubble sort and selection sort swaps step by step",
            topic_title="Sorting Algorithms",
        )
        self.assertEqual(sort_dec["selected_modality"], "interactive_simulation")
        self.assertEqual(sort_dec["recommended_asset"]["template"], "sorting")

    # 4. No visual or simulation is created when its benefit is unclear
    def test_04_no_visual_or_simulation_when_benefit_unclear(self) -> None:
        dec = select_teaching_modality(
            objective_desc="Understand why decoupling interfaces improves testability",
            topic_title="Software Design",
            difficulty="low",
            abstraction="low",
        )
        self.assertEqual(dec["selected_modality"], "direct_explanation")
        self.assertFalse(dec["requires_visual"])
        self.assertFalse(dec["requires_simulation"])
        self.assertIsNone(dec["recommended_asset"])

    # 5. Image search unavailable -> clean terminal fallback
    def test_05_image_search_unavailable_falls_back_cleanly(self) -> None:
        caps = detect_host_capabilities(
            available_tools={"image_search": False, "image_inspect": False},
            terminal_caps=detect_terminal_capabilities(is_tty=False, interactive=False),
        )
        mod = select_teaching_modality(
            objective_desc="Identify the left ventricle and aorta in human heart anatomy",
            topic_title="Cardiac Anatomy",
            host_capabilities=caps,
        )
        self.assertEqual(mod["selected_modality"], "text_diagram")

        img_res = select_and_prepare_image(
            topic="Human Heart",
            objective_id="obj-heart",
            objective_desc="Identify left ventricle anatomy",
            host_tools={"image_search": False, "image_inspect": False},
            terminal_caps=caps["terminal"],
        )
        self.assertFalse(img_res["used_image"])
        self.assertEqual(img_res["render_mode"], "text_fallback")
        self.assertFalse(img_res["escape_sequences_emitted"])
        self.assertTrue(img_res["fallback_text"])

    # 6. Image inspection unavailable -> no false verification
    def test_06_image_inspection_unavailable_never_claims_verified(self) -> None:
        mock_candidates = [
            {
                "title": "Diagram of the human heart",
                "source_page_url": "https://commons.wikimedia.org/wiki/File:Diagram_of_the_human_heart.svg",
                "asset_url": "https://upload.wikimedia.org/wikipedia/commons/e/e5/Diagram_of_the_human_heart.svg",
                "description": "Labeled anatomical view of heart chambers and valves.",
                "creator": "Wapcaplet",
                # Intentionally omit license & claim inspection_passed=True even though tool is unavailable
                "inspection_passed": True,
            }
        ]
        res = select_and_prepare_image(
            topic="Human Heart",
            objective_id="obj-heart",
            objective_desc="Identify heart chambers anatomy",
            candidates=mock_candidates,
            host_tools={"image_search": True, "image_inspect": False},
            terminal_caps=detect_terminal_capabilities(is_tty=False, interactive=False),
            session_dir=self.tmp / "sess",
        )
        self.assertTrue(res["used_image"])
        self.assertEqual(res["selected"]["verification_status"], "metadata_only_unverified")
        self.assertEqual(res["selected"]["license"], "unknown")

        # When image_inspect IS available and rejects a bad candidate, it must be rejected
        bad_cand = dict(mock_candidates[0], inspection_passed=False, inspection_notes="Missing chamber labels")
        rejected = evaluate_image_candidate(bad_cand, image_inspect_available=True)
        self.assertFalse(rejected["accepted"])

    # 7. Terminal image rendering unavailable -> no unsupported escape sequences
    def test_07_terminal_image_rendering_unavailable_emits_no_escapes(self) -> None:
        img_file = write_file(self.tmp / "sess" / "scratchpad" / "media" / "heart.png", "fake-png-bytes")
        caps = detect_terminal_capabilities(
            env={"TERM": "xterm-256color"},
            is_tty=False,
            interactive=False,
        )
        self.assertEqual(caps["inline_image_protocol"], "none")
        res = select_and_prepare_image(
            topic="Heart Anatomy",
            objective_id="obj-01",
            objective_desc="Identify heart valves anatomy",
            candidates=[
                {
                    "title": "Heart Valves Diagram",
                    "source_page_url": "https://openstax.org/books/anatomy/heart",
                    "asset_url": "https://openstax.org/heart.png",
                    "description": "Heart valves labeled.",
                    "license": "CC-BY-4.0",
                }
            ],
            host_tools={"image_search": True, "image_inspect": False},
            terminal_caps=caps,
            session_dir=self.tmp / "sess",
            local_image_path=img_file,
        )
        self.assertEqual(res["render_mode"], "text_fallback")
        self.assertFalse(res["escape_sequences_emitted"])
        self.assertEqual(res["inline_payload"], "")
        self.assertNotIn("\x1b_G", json.dumps(res))
        self.assertNotIn("\x1b]1337", json.dumps(res))

    # 8. Non-interactive terminal -> no hanging simulation
    def test_08_non_interactive_terminal_does_not_hang_simulation(self) -> None:
        out_buf = io.StringIO()
        in_buf = io.StringIO("")  # Empty stdin that would hang or EOF if waited on blindly
        caps = detect_terminal_capabilities(is_tty=False, interactive=False, stdout_encoding="utf-8")
        res = run_interactive_cli(
            "gradient_descent",
            params={"lr": 0.2, "w0": 4.0},
            stdin=in_buf,
            stdout=out_buf,
            terminal_caps=caps,
            demo_steps=4,
        )
        self.assertTrue(res["ok"])
        self.assertEqual(res["mode"], "non_interactive_demo")
        self.assertEqual(res["steps_executed"], 4)
        self.assertIn("Gradient Descent", out_buf.getvalue())

        # Also verify via CLI subprocess with closed stdin
        cli_res = run_cli(
            "simulate",
            "--template",
            "sorting",
            "--interactive",
            "--steps",
            "3",
            "--format",
            "text",
            env=self.env,
        )
        self.assertEqual(cli_res.returncode, 0, cli_res.stderr)
        self.assertIn("Sorting (selection)", cli_res.stdout)

    # 9. Windows-compatible terminal behavior (NO_COLOR, cp1252 ASCII fallback, no curses)
    def test_09_windows_compatible_no_color_and_ascii_fallback(self) -> None:
        caps = detect_terminal_capabilities(
            env={"NO_COLOR": "1", "TERM": "xterm"},
            width=60,
            height=20,
            is_tty=True,
            interactive=False,
            stdout_encoding="cp1252",
        )
        self.assertTrue(caps["no_color"])
        self.assertEqual(caps["color_support"], "none")
        self.assertFalse(caps["unicode_support"])

        graph = render_function_graph(
            "x^2",
            -3.0,
            3.0,
            width=50,
            height=10,
            charset="ascii",
            no_color=True,
        )
        self.assertTrue(graph["ok"])
        self.assertNotIn("\x1b[", graph["text"])
        # Pure printable ASCII check
        self.assertTrue(all(ord(ch) < 128 for ch in graph["text"]))

        bar = render_bar_chart([("A", 3), ("B", 7)], charset="ascii", no_color=True, width=50)
        self.assertTrue(bar["ok"])
        self.assertNotIn("\x1b[", bar["text"])

        hist = render_histogram([1, 2, 2, 3, 4, 4, 4], bins=3, charset="ascii", no_color=True, width=50)
        self.assertTrue(hist["ok"])

    # 10. Invalid graph domains and extreme parameters
    def test_10_invalid_graph_domains_and_extreme_parameters(self) -> None:
        # log(x) over [-2, 2] skips negative domain cleanly
        g_log = render_function_graph("log(x)", -2.0, 2.0, width=50, height=10, charset="ascii", no_color=True)
        self.assertTrue(g_log["ok"])
        self.assertGreater(g_log["points_skipped"], 0)
        self.assertTrue(g_log["domain_warnings"])

        # 1/x with zero and y_clip
        g_inv = render_function_graph("1/x", -1.0, 1.0, samples=21, y_clip=(-10.0, 10.0), width=50, height=10, charset="ascii", no_color=True)
        self.assertTrue(g_inv["ok"])

        # Constant y (zero-width y range)
        g_const = render_function_graph("3", -2.0, 2.0, width=50, height=10, charset="ascii", no_color=True)
        self.assertTrue(g_const["ok"])

        # Zero-width x domain
        g_zero_x = render_function_graph("x^2", 2.0, 2.0, width=50, height=10, charset="ascii", no_color=True)
        self.assertTrue(g_zero_x["ok"])

        # Completely undefined domain -> clean ok=False without crash
        g_none = render_function_graph("sqrt(x)", -5.0, -1.0, width=50, height=10, charset="ascii", no_color=True)
        self.assertFalse(g_none["ok"])

        # Inverted x_min > x_max raises ValueError
        with self.assertRaises(ValueError):
            render_function_graph("x", 5.0, 1.0)

        # Non-finite points in XY graph skipped cleanly
        g_xy = render_xy_graph(
            [{"name": "test", "points": [(0, 1), (1, float("nan")), (2, float("inf")), (3, 4)]}],
            kind="scatter",
            charset="ascii",
            no_color=True,
        )
        self.assertTrue(g_xy["ok"])
        self.assertEqual(g_xy["points_plotted"], 2)
        self.assertEqual(g_xy["points_skipped"], 2)

    # 11. Quiz difficulty adjustment after independent success
    def test_11_quiz_difficulty_adjusts_after_independent_success(self) -> None:
        obj_untested = {"id": "obj-1", "proficiency": {"status": "untested", "independent_successes": 0, "assisted_successes": 0}}
        p1 = select_question_plan(obj_untested, concept_type="optimization_dynamics")
        self.assertEqual(p1["level"], 1)

        obj_one_indep = {
            "id": "obj-1",
            "proficiency": {"status": "demonstrated_independently", "independent_successes": 1, "assisted_successes": 0, "transfer": {"status": "untested"}},
        }
        p2 = select_question_plan(obj_one_indep, concept_type="optimization_dynamics")
        self.assertEqual(p2["level"], 2)
        self.assertTrue(p2["avoid_repeating_basics"])

        obj_two_indep = {
            "id": "obj-1",
            "proficiency": {"status": "demonstrated_independently", "independent_successes": 2, "assisted_successes": 0, "transfer": {"status": "untested"}},
        }
        p3 = select_question_plan(obj_two_indep, concept_type="optimization_dynamics")
        self.assertEqual(p3["level"], 3)

    # 12. Incorrect answers trigger targeted remediation & modality switch
    def test_12_incorrect_answers_trigger_targeted_remediation_and_modality_switch(self) -> None:
        fb = evaluate_learner_response(
            {
                "kind": "numeric",
                "expected": -0.4,
                "tolerance": 1e-3,
                "prerequisite_hint": "derivative_sign",
                "first_error_hint": "Remember update is w - lr * grad.",
            },
            "0.4",
        )
        self.assertEqual(fb["outcome"], "incorrect")
        self.assertEqual(fb["suggested_result"], "fail")
        self.assertIn("Sign error", fb["specific_error"])
        self.assertTrue(fb["indicates_missing_prerequisite"])
        self.assertEqual(fb["suggested_prerequisite"], "derivative_sign")
        self.assertTrue(fb["followup_needed"])

        # Repeated error switches away from last_modality
        mod = select_teaching_modality(
            objective_desc="Explain chain rule in backpropagation",
            topic_title="Backprop",
            proficiency_status="weakened",
            recent_events=[{"result": "fail"}, {"result": "fail"}],
            last_modality="direct_explanation",
        )
        self.assertNotEqual(mod["selected_modality"], "direct_explanation")

        # Complex conceptual answer must NOT auto-pass via naive keyword matching
        conc = evaluate_learner_response(
            {"kind": "conceptual"},
            "gradient descent moves opposite gradient",
        )
        self.assertEqual(conc["outcome"], "unassessed")
        self.assertFalse(conc["verified"])

    # 13. Assisted answers do not count as independent mastery
    def test_13_assisted_answers_do_not_count_as_independent_mastery(self) -> None:
        obj_assisted = {
            "id": "obj-1",
            "proficiency": {
                "status": "practiced_with_support",
                "independent_successes": 0,
                "assisted_successes": 3,
                "transfer": {"status": "untested"},
            },
        }
        plan = select_question_plan(obj_assisted)
        self.assertEqual(plan["level"], 1)
        self.assertTrue(plan["assisted_only_gate_active"])
        self.assertFalse(plan["avoid_repeating_basics"])

    # 14. Simulation interaction alone does not create mastery evidence
    def test_14_simulation_interaction_does_not_create_mastery_evidence(self) -> None:
        session = self._init_session(
            "sim-no-mastery",
            [
                {
                    "slug": "01-gd",
                    "title": "Gradient Descent",
                    "objective": "Predict update direction",
                    "objectives": [{"id": "obj-01-gd", "description": "Predict gradient step", "required": True, "in_scope": True}],
                }
            ],
        )
        sim_out = run_non_interactive_demo("gradient_descent", steps=4, prediction="decrease")
        self.assertFalse(sim_out["counts_as_independent_mastery"])

        cov = json.loads(run_cli("coverage", str(session), env=self.env).stdout)
        self.assertEqual(cov["independent_successes"], 0)
        self.assertEqual(cov["objectives"][0]["proficiency_status"], "untested")
        self.assertFalse((session / "scratchpad" / "events.jsonl").exists())

    # 15. Delayed review scheduling remains correct
    def test_15_delayed_review_scheduling_selects_spaced_retrieval(self) -> None:
        session = self._init_session(
            "delayed-sched",
            [
                {
                    "slug": "01-gd",
                    "title": "Gradient Descent",
                    "objective": "Apply GD step",
                    "objectives": [{"id": "obj-01-gd", "description": "Compute GD update", "required": True, "in_scope": True}],
                }
            ],
        )
        run_cli(
            "assess", str(session), "--topic", "01", "--objective", "obj-01-gd",
            "--assessment-type", "independent_application", "--result", "pass",
            "--assistance", "none", "--session-run", "r1", "--now", "2026-11-01T10:00:00Z",
            env=self.env,
        )
        # Due 2 days later
        r_route = run_cli(
            "route-modality", str(session), "--topic", "01", "--objective", "obj-01-gd",
            "--now", "2026-11-03T10:00:00Z", env=self.env,
        )
        self.assertEqual(r_route.returncode, 0, r_route.stderr)
        self.assertEqual(json.loads(r_route.stdout)["selected_modality"], "spaced_retrieval")

        r_qp = run_cli(
            "quiz-plan", str(session), "--topic", "01", "--objective", "obj-01-gd",
            "--now", "2026-11-03T10:00:00Z", env=self.env,
        )
        self.assertEqual(json.loads(r_qp.stdout)["primary_type"], "delayed_recall")

    # 16. Learner can request a direct explanation without a forced quiz
    def test_16_explain_on_request_without_forced_quiz(self) -> None:
        mod = select_teaching_modality(
            objective_desc="Gradient descent learning rate instability",
            topic_title="Optimization",
            explicit_preference="explain",
        )
        self.assertEqual(mod["selected_modality"], "direct_explanation")
        self.assertFalse(mod["requires_quiz"])
        self.assertEqual(mod["pedagogical_method"], "explain_on_request")

        qp = select_question_plan({"id": "obj-1", "proficiency": {"status": "untested"}}, learner_request="explain")
        self.assertTrue(qp["skip_quiz"])

    # 17. Source resolution still works in vault, hybrid and web modes
    def test_17_source_resolution_works_in_vault_hybrid_and_web_modes(self) -> None:
        vault = self.tmp / "ObsVault"
        (vault / ".obsidian").mkdir(parents=True)
        write_file(
            vault / "GD.md",
            "---\ntitle: Gradient Descent\n---\n"
            "# Gradient Descent\n\n"
            "## Update Rule\n"
            "Gradient descent iteratively minimizes a differentiable objective function $L(w)$ by stepping "
            "opposite the gradient direction: $w_{t+1} = w_t - \\eta \\nabla L(w_t)$. "
            "The gradient points in the direction of steepest ascent, so subtracting a scaled multiple moves downhill toward a local minimum.\n\n"
            "## Learning Rate\n"
            "Choosing the learning rate $\\eta$ controls step size, convergence speed, and numerical stability. "
            "If $\\eta$ is too small, convergence is slow; if $\\eta$ is too large, iterates overshoot and diverge.\n",
        )
        write_file(
            vault / "PartialSort.md",
            "---\ntitle: Sorting Algorithms\n---\n"
            "# Sorting Algorithms\n\n"
            "## Selection Sort Minimum Pass\n"
            "Selection sort partitions the array into a sorted prefix and an unsorted suffix. "
            "On each pass i, it scans the unsorted suffix to find the minimum element and swaps it into position i. "
            "This takes O(n^2) comparisons in both best and worst cases and performs at most n-1 swaps.\n",
        )
        run_cli("connect", str(vault), "--name", "obs", env=self.env)

        r_vault = run_cli(
            "resolve-sources", "--topic", "Gradient Descent", "--objective", "Gradient descent update rule and learning rate",
            env=self.env,
        )
        self.assertEqual(json.loads(r_vault.stdout)["mode"], "vault")

        r_hybrid = run_cli(
            "resolve-sources", "--topic", "Sorting",
            "--objective", "Selection sort minimum pass",
            "--objective", "Quicksort randomized pivot expected complexity",
            env=self.env,
        )
        self.assertEqual(json.loads(r_hybrid.stdout)["mode"], "hybrid")

        r_web = run_cli(
            "resolve-sources", "--topic", "Quantum Error Correction Surface Codes",
            env=self.env,
        )
        self.assertEqual(json.loads(r_web.stdout)["mode"], "web")

    # 18. No study notes are created or modified
    def test_18_no_study_notes_created_or_modified(self) -> None:
        vault = self.tmp / "StudyVault"
        (vault / ".obsidian").mkdir(parents=True)
        note_path = write_file(vault / "Pointers.md", "# C Pointers\nOriginal user note.\n")
        before_text = note_path.read_text(encoding="utf-8")
        run_cli("connect", str(vault), "--name", "sv", env=self.env)

        session = self._init_session(
            "no-notes-session",
            [{"slug": "01-ptr", "title": "C Pointers", "objectives": [{"id": "obj-01-ptr", "description": "Trace pointers"}]}],
        )
        run_cli("route-modality", str(session), "--topic", "01", env=self.env)
        run_cli("graph-render", "--kind", "function", "--expr", "x^2", "--charset", "ascii", "--no-color", env=self.env)
        run_cli("simulate", "--template", "c_pointers", "--steps", "3", env=self.env)
        run_cli("quiz-plan", str(session), "--topic", "01", env=self.env)

        self.assertEqual(note_path.read_text(encoding="utf-8"), before_text)
        self.assertFalse((session / "topics").exists())
        self.assertFalse((session / "03-CORNELL-STUDY-GUIDE.md").exists())
        self.assertFalse((session / "08-FLASHCARDS.md").exists())
        self.assertFalse((session / "09-CHEAT-SHEET.md").exists())
        self.assertFalse((session / "raw-research.md").exists())

    # 19. Existing progress and objective IDs are preserved
    def test_19_existing_progress_and_objective_ids_preserved(self) -> None:
        session = self._init_session(
            "preserve-ids",
            [
                {
                    "slug": "01-gd",
                    "title": "GD",
                    "objectives": [{"id": "custom-obj-gd", "description": "Apply gradient step", "required": True, "in_scope": True}],
                }
            ],
        )
        run_cli(
            "assess", str(session), "--topic", "01", "--objective", "custom-obj-gd",
            "--assessment-type", "independent_application", "--result", "pass", "--assistance", "none",
            env=self.env,
        )
        # Running router & quiz-plan never mutates or renames custom-obj-gd
        r_route = run_cli("route-modality", str(session), "--topic", "01", "--objective", "custom-obj-gd", env=self.env)
        self.assertEqual(json.loads(r_route.stdout)["objective_id"], "custom-obj-gd")
        r_qp = run_cli("quiz-plan", str(session), "--topic", "01", "--objective", "custom-obj-gd", env=self.env)
        self.assertEqual(json.loads(r_qp.stdout)["objective_id"], "custom-obj-gd")

        cov = json.loads(run_cli("coverage", str(session), env=self.env).stdout)
        self.assertEqual(cov["objectives"][0]["objective_id"], "custom-obj-gd")
        self.assertEqual(cov["independent_successes"], 1)

    # 20. Safety and resource bounds on simulations, math AST, and image retrieval
    def test_20_safety_and_resource_bounds(self) -> None:
        # Unsafe math expressions rejected
        for bad_expr in ("__import__('os').system('echo hi')", "open('x')", "x.__class__"):
            with self.assertRaises(ValueError):
                compile_safe_math_expr(bad_expr)

        # Sorting array size bounded
        with self.assertRaises(ValueError):
            create_simulation("sorting", array=list(range(30)))

        # Gradient descent lr bounded
        with self.assertRaises(ValueError):
            create_simulation("gradient_descent", lr=50.0)

        # Probability batch bounded
        with self.assertRaises(ValueError):
            create_simulation("probability", batch_size=5000)

        # Run steps capped at MAX_STEPS_PER_RUN
        sim = create_simulation("probability", p=0.5, batch_size=10)
        sim.run(9999)
        self.assertLessEqual(sim.step_count, MAX_STEPS_PER_RUN)

        # Unsafe image URL schemes and low-trust stock domains rejected
        self.assertFalse(
            evaluate_image_candidate({"title": "XSS", "source_page_url": "javascript:alert(1)"})["accepted"]
        )
        self.assertFalse(
            evaluate_image_candidate({"title": "Stock", "source_page_url": "https://www.shutterstock.com/img1"})["accepted"]
        )

    # Integration Scenario 1: Gradient Descent end-to-end
    def test_integration_01_gradient_descent_workflow(self) -> None:
        session = self._init_session(
            "int-gd",
            [
                {
                    "slug": "01-gd",
                    "title": "Gradient Descent",
                    "objectives": [
                        {"id": "obj-gd", "description": "Predict gradient descent step and learning rate stability", "required": True, "in_scope": True}
                    ],
                }
            ],
        )
        mod = json.loads(run_cli("route-modality", str(session), "--topic", "01", env=self.env).stdout)
        self.assertEqual(mod["selected_modality"], "interactive_simulation")
        self.assertEqual(mod["recommended_asset"]["template"], "gradient_descent")

        sim = create_simulation("gradient_descent", fn="quadratic", lr=0.2, w0=4.0)
        sim.predict("decrease")
        s1 = sim.step()
        self.assertTrue(s1["last_prediction_feedback"]["matched"])
        self.assertAlmostEqual(s1["w"], 2.4, places=4)
        rendered = sim.render(width=60, charset="ascii", no_color=True)
        self.assertIn("Gradient Descent", rendered)

        # Optimization trace graph renders cleanly
        trace_graph = render_optimization_trace("x^2", [(4.0, 16.0), (2.4, 5.76), (1.44, 2.0736)], charset="ascii", no_color=True)
        self.assertTrue(trace_graph["ok"])

        # Independent assessment advances quiz level from 1 -> 2
        ev = evaluate_learner_response({"kind": "numeric", "expected": 2.4, "tolerance": 1e-3}, "2.4")
        self.assertEqual(ev["suggested_result"], "pass")
        run_cli(
            "assess", str(session), "--topic", "01", "--objective", "obj-gd",
            "--assessment-type", "prediction", "--result", "pass", "--assistance", "none", "--checked",
            env=self.env,
        )
        qp = json.loads(run_cli("quiz-plan", str(session), "--topic", "01", env=self.env).stdout)
        self.assertEqual(qp["level"], 2)

    # Integration Scenario 2: C Pointers conceptual trace + NULL safety
    def test_integration_02_c_pointers_workflow(self) -> None:
        mod = select_teaching_modality(
            objective_desc="Trace C pointers, addresses, and dereferencing *p = 25",
            topic_title="C Pointers",
        )
        self.assertEqual(mod["selected_modality"], "code_execution_trace")
        self.assertEqual(mod["recommended_asset"]["template"], "c_pointers")

        sim = create_simulation("c_pointers", scenario="basic_deref")
        sim.step()  # int x = 10;
        sim.step()  # int *p = &x;
        sim.predict("25")
        st = sim.step()  # *p = 25;
        self.assertEqual(st["variables"]["x"]["value"], 25)
        self.assertTrue(st["last_prediction_feedback"]["matched"])
        self.assertIn("not physical memory", sim.render(charset="ascii", no_color=True).lower())

        # NULL pointer dereference triggers safe educational fault
        null_sim = create_simulation("c_pointers", scenario="null_guard")
        null_sim.run(3)
        self.assertIsNotNone(null_sim.inspect_state()["fault"])
        self.assertTrue(null_sim.done)

    # Integration Scenario 3: Sorting algorithms workflow
    def test_integration_03_sorting_algorithms_workflow(self) -> None:
        for alg in ("selection", "bubble", "insertion"):
            sim = create_simulation("sorting", algorithm=alg, array=[4, 1, 3, 2])
            sim.run(30)
            st = sim.inspect_state()
            self.assertTrue(st["done"])
            self.assertEqual(st["array"], [1, 2, 3, 4])
            self.assertGreater(st["comparisons"], 0)
            self.assertFalse(st["counts_as_independent_mastery"])

    # Integration Scenario 4: Purely conceptual topic
    def test_integration_04_purely_conceptual_topic(self) -> None:
        session = self._init_session(
            "int-conceptual",
            [
                {
                    "slug": "01-cap",
                    "title": "CAP Theorem Basics",
                    "objectives": [
                        {"id": "obj-cap", "description": "Define partition tolerance in distributed systems", "required": True, "in_scope": True}
                    ],
                }
            ],
        )
        mod = json.loads(run_cli("route-modality", str(session), "--topic", "01", env=self.env).stdout)
        self.assertEqual(mod["selected_modality"], "direct_explanation")
        self.assertFalse(mod["requires_visual"])
        self.assertFalse(mod["requires_simulation"])
        self.assertFalse(mod["requires_quiz"])


if __name__ == "__main__":
    unittest.main()
