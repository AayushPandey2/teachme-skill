"""Comprehensive tests for /teachme-code subskill and coding_practice engine."""

from __future__ import annotations

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

from teachme_vault.coding_practice import (  # noqa: E402
    analyze_code_static,
    build_code_plan,
    detect_coding_runtimes,
    parse_code_invocation,
    verify_learner_code,
)
from teachme_vault.simulations import run_non_interactive_demo  # noqa: E402
from teachme_vault.state_store import init_session_state, load_events, record_assessment_event  # noqa: E402


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


class TeachMeCodeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="teachme_code_test_"))
        self.cfg_path = self.tmp / "teachme-config.json"
        self.env = {"TEACHME_CONFIG_PATH": str(self.cfg_path)}
        self.orig_cfg_env = os.environ.get("TEACHME_CONFIG_PATH")
        os.environ["TEACHME_CONFIG_PATH"] = str(self.cfg_path)

    def tearDown(self) -> None:
        if self.orig_cfg_env is None:
            os.environ.pop("TEACHME_CONFIG_PATH", None)
        else:
            os.environ["TEACHME_CONFIG_PATH"] = self.orig_cfg_env
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _create_session(self, name: str = "c-pointers") -> Path:
        sess = self.tmp / "notes" / name
        init_session_state(
            sess,
            topic_title="C Pointers",
            items=[
                {
                    "slug": "01-addresses",
                    "title": "Addresses and Dereferencing",
                    "objective": "Use & and * operators safely in C.",
                },
                {
                    "slug": "02-pointer-arithmetic",
                    "title": "Pointer Arithmetic",
                    "objective": "Index arrays and compute offsets with pointer arithmetic.",
                },
            ],
        )
        return sess

    def test_01_invocation_and_language_parsing(self) -> None:
        cases = [
            ("C pointers", "c", "pointers", None, None, None, False),
            ("/teachme-code Python recursion", "python", "recursion", None, None, None, False),
            ("C arrays --mode practice", "c", "arrays", "practice", None, None, False),
            ("Python two pointers --mode challenge", "python", "two pointers", "challenge", None, None, False),
            ("C --mode debug", "c", "C debugging", "debug", None, None, False),
            ("DSA binary search --level intermediate", "", "binary search", None, "intermediate", None, False),
            ("C functions --minutes 20", "c", "functions", None, None, 20, False),
            ("--resume", "", "", None, None, None, True),
            ("/teachme code JavaScript closures --mode interview", "javascript", "closures", "interview", None, None, False),
        ]
        for raw, exp_lang, exp_topic_sub, exp_mode, exp_lvl, exp_min, exp_res in cases:
            parsed = parse_code_invocation(raw)
            self.assertEqual(parsed["language"], exp_lang, raw)
            self.assertIn(exp_topic_sub.lower(), (parsed["full_topic"] or parsed["topic"]).lower(), raw)
            self.assertEqual(parsed["mode"], exp_mode, raw)
            self.assertEqual(parsed["level"], exp_lvl, raw)
            self.assertEqual(parsed["minutes"], exp_min, raw)
            self.assertEqual(parsed["resume"], exp_res, raw)

    def test_02_basic_learn_mode_and_hint_ladder(self) -> None:
        sess = self._create_session("py-recursion")
        plan = build_code_plan("Python recursion", vault_path=str(sess))
        self.assertTrue(plan["ok"])
        self.assertEqual(plan["language"], "python")
        self.assertEqual(plan["mode"], "learn")
        self.assertEqual(plan["difficulty"], "foundation")
        self.assertEqual(plan["hint_ladder"][0]["assistance"], "none")
        self.assertEqual(plan["hint_ladder"][3]["assistance"], "scaffold")
        self.assertEqual(plan["hint_ladder"][4]["assistance"], "worked_example")

    def test_03_practice_progression_requires_independent_success(self) -> None:
        sess = self._create_session()
        # Assisted pass alone must keep difficulty at foundation
        record_assessment_event(
            sess,
            topic="01",
            objective="obj-01-01",
            result="pass",
            assistance="hint",
            assessment_type="independent_application",
            now="2026-11-18T10:00:00Z",
        )
        p1 = build_code_plan("C pointers --mode practice", vault_path=str(sess), topic_num="01")
        self.assertEqual(p1["difficulty"], "foundation")
        self.assertTrue(p1["quiz_plan"]["assisted_only_gate_active"])

        # Independent pass advances difficulty to intermediate
        record_assessment_event(
            sess,
            topic="01",
            objective="obj-01-01",
            result="pass",
            assistance="none",
            assessment_type="independent_application",
            now="2026-11-18T10:05:00Z",
        )
        p2 = build_code_plan("C pointers --mode practice", vault_path=str(sess), topic_num="01")
        self.assertEqual(p2["difficulty"], "intermediate")

    def test_04_debugging_workflow_c_beginner_errors(self) -> None:
        buggy_c = (
            "#include <stdio.h>\n"
            "int main() {\n"
            "    int x;\n"
            "    int a[4];\n"
            "    int *p = x;\n"
            '    scanf("%d", x);\n'
            "    for (int i = 0; i <= 4; i++) {\n"
            "        a[i] = i;\n"
            "    }\n"
            '    printf("%d", x);\n'
            "    return 0;\n"
            "}\n"
        )
        diag = analyze_code_static(buggy_c, "c")
        self.assertFalse(diag["ok"])
        msgs = " | ".join(f["message"] for f in diag["findings"])
        self.assertIn("without '&'", msgs)
        self.assertIn("scanf", msgs)
        self.assertIn("<= 4", msgs)

        # Memory leak & missing NULL check
        leak_c = (
            "#include <stdlib.h>\n"
            "int main() {\n"
            "    int *arr = malloc(10 * sizeof(int));\n"
            "    return 0;\n"
            "}\n"
        )
        leak_diag = analyze_code_static(leak_c, "c")
        leak_msgs = " | ".join(f["message"] for f in leak_diag["findings"])
        self.assertIn("not freed", leak_msgs)
        self.assertIn("NULL check", leak_msgs)

    def test_05_predict_output_and_trace_simulation(self) -> None:
        sess = self._create_session()
        plan = build_code_plan("C pointers --mode trace", vault_path=str(sess))
        self.assertEqual(plan["mode"], "trace")
        self.assertEqual(plan["recommended_simulation"], "c_pointers")

        sim = run_non_interactive_demo(
            "c_pointers",
            steps=4,
            params={"scenario": "basic_deref"},
            prediction="x=10",
        )
        self.assertTrue(sim["final_state"]["last_prediction_feedback"]["matched"])

    def test_06_syntax_error_feedback_python(self) -> None:
        bad_py = "def add(a, b)\n    return a + b\n"
        res = verify_learner_code(code=bad_py, language="python", authorize_exec=True)
        self.assertFalse(res["ok"])
        self.assertFalse(res["execution_performed"])
        self.assertEqual(res["first_error"]["category"], "syntax_error")
        self.assertEqual(res["suggested_result"], "fail")

    def test_07_incorrect_logic_detection(self) -> None:
        wrong_py = "def binary_search(arr, target):\n    return 0\n"
        tests = [
            {"name": "found_mid", "call": "binary_search", "args": [[1, 3, 5, 7], 5], "expected_return": 2, "kind": "example"},
            {"name": "missing", "call": "binary_search", "args": [[1, 3, 5, 7], 4], "expected_return": -1, "kind": "edge"},
        ]
        res = verify_learner_code(code=wrong_py, language="python", test_cases=tests, authorize_exec=True)
        self.assertFalse(res["ok"])
        self.assertTrue(res["execution_performed"])
        self.assertEqual(res["tests_passed"], 0)
        self.assertEqual(res["first_error"]["category"], "logical_error")
        self.assertEqual(res["suggested_result"], "fail")

    def test_08_correct_code_passes_verified_tests_and_distinguishes_edge_cases(self) -> None:
        good_py = (
            "def binary_search(arr, target):\n"
            "    lo, hi = 0, len(arr) - 1\n"
            "    while lo <= hi:\n"
            "        mid = (lo + hi) // 2\n"
            "        if arr[mid] == target:\n"
            "            return mid\n"
            "        if arr[mid] < target:\n"
            "            lo = mid + 1\n"
            "        else:\n"
            "            hi = mid - 1\n"
            "    return -1\n"
        )
        sample_only = [
            {"name": "ex1", "call": "binary_search", "args": [[1, 3, 5], 3], "expected_return": 1, "kind": "example"},
        ]
        r_sample = verify_learner_code(code=good_py, language="python", test_cases=sample_only, authorize_exec=True)
        self.assertTrue(r_sample["ok"])
        self.assertEqual(r_sample["verification_scope"], "partial_sample_only")

        with_edge = sample_only + [
            {"name": "empty", "call": "binary_search", "args": [[], 3], "expected_return": -1, "kind": "edge"},
        ]
        r_full = verify_learner_code(code=good_py, language="python", test_cases=with_edge, authorize_exec=True)
        self.assertTrue(r_full["ok"])
        self.assertEqual(r_full["verification_scope"], "verified_with_edge_cases")
        self.assertEqual(r_full["suggested_result"], "pass")

    def test_09_assisted_vs_independent_evidence(self) -> None:
        sess = self._create_session("py-search")
        py_code = "print(int(input()) * 2)\n"
        tests = [{"name": "double", "stdin": "7\n", "expected_stdout": "14", "kind": "edge"}]

        res_hint = verify_learner_code(
            code=py_code,
            language="python",
            test_cases=tests,
            authorize_exec=True,
            hint_level=2,
            session_dir=sess,
            topic_num="01",
            objective_id="obj-01-01",
            record_evidence=True,
            now="2026-11-18T11:00:00Z",
        )
        self.assertEqual(res_hint["suggested_assistance"], "hint")
        self.assertTrue(res_hint["evidence_recorded"])

        # Assisted pass must NOT produce demonstrated_independently
        ctx = json.loads(run_cli("context", str(sess), "--topic", "01", env=self.env).stdout)
        self.assertEqual(ctx["curriculum"]["objectives"][0]["proficiency_status"], "practiced_with_support")

        # Now independent attempt (hint_level=0)
        res_indep = verify_learner_code(
            code=py_code,
            language="python",
            test_cases=tests,
            authorize_exec=True,
            hint_level=0,
            session_dir=sess,
            topic_num="01",
            objective_id="obj-01-01",
            record_evidence=True,
            now="2026-11-18T11:05:00Z",
        )
        self.assertEqual(res_indep["suggested_assistance"], "none")
        ctx2 = json.loads(run_cli("context", str(sess), "--topic", "01", env=self.env).stdout)
        self.assertEqual(ctx2["curriculum"]["objectives"][0]["proficiency_status"], "demonstrated_independently")

    def test_10_safe_execution_fallback_requires_authorization(self) -> None:
        res = verify_learner_code(
            code="print('hello')\n",
            language="python",
            authorize_exec=False,
            trusted_sandbox=False,
        )
        self.assertFalse(res["execution_performed"])
        self.assertEqual(res["execution_status"], "authorization_required")
        self.assertEqual(res["verification_scope"], "static_only")

    def test_11_missing_compiler_runtime_fallback(self) -> None:
        # Simulate missing gcc and missing javac (even if java is present)
        def fake_which(name: str) -> str | None:
            if name == "java":
                return "/usr/bin/java"
            return None

        rt = detect_coding_runtimes(which_fn=fake_which, python_exe="")
        self.assertFalse(rt["runtimes"]["c"]["available"])
        self.assertFalse(rt["runtimes"]["java"]["available"])
        self.assertFalse(rt["runtimes"]["python"]["available"])

        res = verify_learner_code(
            code="int main() { return 0; }\n",
            language="c",
            authorize_exec=True,
            which_fn=fake_which,
        )
        self.assertFalse(res["execution_performed"])
        self.assertEqual(res["execution_status"], "runtime_unavailable")

    def test_12_execution_timeout_and_output_bounds(self) -> None:
        # Infinite loop triggers timeout bound
        inf_py = "i = 0\nwhile i >= 0:\n    i += 1\n"
        res_to = verify_learner_code(
            code=inf_py,
            language="python",
            authorize_exec=True,
            timeout_sec=0.6,
        )
        self.assertFalse(res_to["ok"])
        self.assertTrue(res_to["test_results"][0]["timed_out"])
        self.assertEqual(res_to["runtime_error"]["category"], "runtime_error")

        # Huge output is truncated cleanly
        noisy_py = "print('A' * 5000)\n"
        res_out = verify_learner_code(
            code=noisy_py,
            language="python",
            authorize_exec=True,
            max_output_chars=200,
        )
        self.assertTrue(res_out["test_results"][0]["output_truncated"])
        self.assertLessEqual(len(res_out["test_results"][0]["stdout"]), 230)

    def test_13_windows_cli_compatibility(self) -> None:
        sess = self._create_session()
        r1 = run_cli("code-plan", str(sess), "--args", "C pointers --mode practice", env=self.env)
        self.assertEqual(r1.returncode, 0, r1.stderr)
        p_out = json.loads(r1.stdout)
        self.assertTrue(p_out["ok"])
        self.assertEqual(p_out["language"], "c")

        r2 = run_cli(
            "code-check", str(sess),
            "--language", "python",
            "--code", "print(42)",
            "--tests-json", json.dumps([{"stdin": "", "expected_stdout": "42"}]),
            "--authorize-exec",
            env=self.env,
        )
        self.assertEqual(r2.returncode, 0, r2.stderr)
        c_out = json.loads(r2.stdout)
        self.assertTrue(c_out["ok"])
        self.assertEqual(c_out["tests_passed"], 1)

    def test_14_session_resumption(self) -> None:
        sess = self._create_session()
        build_code_plan("C pointer arithmetic --mode challenge --minutes 15", vault_path=str(sess))
        resumed = build_code_plan("--resume", vault_path=str(sess))
        self.assertTrue(resumed["resumed"])
        self.assertEqual(resumed["language"], "c")
        self.assertEqual(resumed["mode"], "challenge")
        self.assertEqual(resumed["parsed"]["minutes"], 15)

    def test_15_shared_teachme_memory(self) -> None:
        sess = self._create_session()
        # Simulate prior /teachme struggle on topic 02 (pointer arithmetic)
        record_assessment_event(
            sess,
            topic="02",
            objective="obj-02-01",
            result="fail",
            assistance="none",
            assessment_type="prediction",
            rationale="Added byte offset instead of sizeof(int) element stride",
            now="2026-11-18T09:00:00Z",
        )
        write_file(
            sess / "learning-records" / "0001-pointer-stride.md",
            "# LR-0001: Pointer Arithmetic Stride\n"
            "- **Date:** 2026-11-18 | **Status:** active | **Objective:** obj-02-01\n"
            "## Context\nConfused p + 1 with +1 byte.\n"
            "## Insight\np + 1 advances by sizeof(*p) bytes.\n",
        )
        plan = build_code_plan("C pointers", vault_path=str(sess))
        self.assertTrue(any(w["objective_id"] == "obj-02-01" for w in plan["prioritize_weak_spots"]))
        self.assertTrue(any("Stride" in m["title"] for m in plan["active_misconceptions"]))
        self.assertEqual(plan["mode"], "practice")

    def test_16_no_unauthorized_writes_to_learner_files(self) -> None:
        learner_dir = self.tmp / "learner_repo"
        src = write_file(learner_dir / "main.py", "def sq(x):\n    return x * x\n")
        note = write_file(learner_dir / "Pointers.md", "# Pointers\nUser study note.\n")
        before_src = src.read_text(encoding="utf-8")
        before_note = note.read_text(encoding="utf-8")

        res = verify_learner_code(
            code_file=str(src),
            language="python",
            test_cases=[{"call": "sq", "args": [5], "expected_return": 25}],
            authorize_exec=True,
        )
        self.assertTrue(res["ok"])
        self.assertFalse(res["study_notes_modified"])
        self.assertEqual(src.read_text(encoding="utf-8"), before_src)
        self.assertEqual(note.read_text(encoding="utf-8"), before_note)
        # Ensure no build/temp artifacts were left inside learner_dir
        self.assertEqual(sorted(p.name for p in learner_dir.iterdir()), ["Pointers.md", "main.py"])


if __name__ == "__main__":
    unittest.main()
