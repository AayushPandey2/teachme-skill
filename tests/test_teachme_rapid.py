"""Comprehensive tests for /teachme-rapid subskill and rapid_revision engine."""

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

from teachme_vault.models import register_vault  # noqa: E402
from teachme_vault.rapid_revision import (  # noqa: E402
    build_rapid_plan,
    build_rapid_status_report,
    parse_rapid_invocation,
    record_rapid_answer,
)
from teachme_vault.state_store import (  # noqa: E402
    init_session_state,
    load_curriculum,
    load_events,
    record_assessment_event,
    resolve_session_dir,
    save_mission,
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


class TeachMeRapidTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="teachme_rapid_test_"))
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

    def _create_vault_with_c_notes(self) -> tuple[Path, dict[Path, str]]:
        vault = self.tmp / "StudyVault"
        (vault / ".obsidian").mkdir(parents=True, exist_ok=True)
        n1 = write_file(
            vault / "C" / "Pointers.md",
            "# C Pointers\n\n"
            "## Address-Of and Dereference\n"
            "The address-of operator `&x` yields the memory address of `x` when `x` is an lvalue.\n"
            "Dereferencing `*p` accesses the object pointed to by `p`. Changing `*p = 20` mutates `x`.\n\n"
            "## Pointer Arithmetic\n"
            "Adding 1 to an `int *p` advances by `sizeof(int)` bytes, not 1 byte.\n"
            "```c\nint a[3] = {10, 20, 30};\nint *p = a;\n// *(p + 1) == 20\n```\n",
        )
        n2 = write_file(
            vault / "Math" / "Calculus.md",
            "# Calculus Derivatives\n\n"
            "## Power Rule\n"
            "The derivative of $x^n$ with respect to $x$ is $n x^{n-1}$.\n\n"
            "## Chain Rule\n"
            "For composite functions $f(g(x))$, $(f \\circ g)'(x) = f'(g(x)) g'(x)$.\n",
        )
        register_vault(vault, name="study", activate=True)
        return vault, {n1: n1.read_text(encoding="utf-8"), n2: n2.read_text(encoding="utf-8")}

    def test_01_and_02_note_backed_question_generation_and_section_grounding(self) -> None:
        vault, _ = self._create_vault_with_c_notes()
        plan = build_rapid_plan("C pointers", vault_path=str(vault))
        self.assertTrue(plan["ok"])
        self.assertTrue(plan["ready"])
        self.assertTrue(plan["notes_grounded"])
        self.assertGreaterEqual(len(plan["planned_items"]), 2)
        for item in plan["planned_items"]:
            self.assertEqual(item["source_origin"], "vault_note")
            self.assertTrue(item["untrusted_source"])
            self.assertEqual(item["source_path"], "C/Pointers.md")
            self.assertTrue(item["source_heading"])

    def test_03_mcq_and_recall_modes(self) -> None:
        vault, _ = self._create_vault_with_c_notes()
        p_mcq = build_rapid_plan("C pointers --mode mcq", vault_path=str(vault))
        self.assertEqual(p_mcq["mode"], "mcq")
        self.assertTrue(all(it["question_type"] == "mcq" for it in p_mcq["planned_items"]))

        p_rec = build_rapid_plan("calculus --mode recall", vault_path=str(vault))
        self.assertEqual(p_rec["mode"], "recall")
        self.assertTrue(all(it["question_type"] in ("recall", "formula_recall") for it in p_rec["planned_items"]))

    def test_04_mixed_question_selection(self) -> None:
        vault, _ = self._create_vault_with_c_notes()
        p_mix = build_rapid_plan("C pointers --mode mixed", vault_path=str(vault))
        self.assertEqual(p_mix["mode"], "mixed")
        qtypes = {it["question_type"] for it in p_mix["planned_items"]}
        self.assertGreaterEqual(len(qtypes), 2)

    def test_05_weak_concept_prioritization(self) -> None:
        vault, _ = self._create_vault_with_c_notes()
        sess = resolve_session_dir(str(vault), session_slug="c-pointers", topic_hint="C Pointers", for_init=True)
        init_session_state(
            sess,
            topic_title="C Pointers",
            items=[
                {"slug": "01-deref", "title": "Address-Of and Dereference", "objective": "Use & and * operators to read and mutate values."},
                {"slug": "02-arith", "title": "Pointer Arithmetic", "objective": "Compute pointer arithmetic offsets by sizeof(type)."},
            ],
            mode="vault-native",
            vault_root=vault,
        )
        # Master topic 01, fail topic 02
        record_assessment_event(sess, topic="01", objective="obj-01-01", result="pass", assistance="none", now="2026-11-18T09:00:00Z")
        record_assessment_event(
            sess, topic="02", objective="obj-02-01", result="fail", assistance="none",
            rationale="Thought p + 1 adds 1 byte", now="2026-11-18T09:05:00Z",
        )
        plan = build_rapid_plan("C pointers --mode weak", vault_path=str(vault), session_slug="c-pointers")
        self.assertTrue(plan["ready"])
        first_item = plan["next_item"]
        self.assertEqual(first_item["source_heading"], "Pointer Arithmetic")
        self.assertIn("weak_or_failed_objective", first_item["priority_reasons"])

    def test_06_no_note_handling_without_fabrication(self) -> None:
        empty_vault = self.tmp / "EmptyVault"
        (empty_vault / ".obsidian").mkdir(parents=True, exist_ok=True)
        register_vault(empty_vault, name="empty", activate=True)

        plan = build_rapid_plan("quantum field theory", vault_path=str(empty_vault))
        self.assertTrue(plan["ok"])
        self.assertFalse(plan["ready"])
        self.assertEqual(plan["status"], "no_usable_notes")
        self.assertFalse(plan["notes_grounded"])
        self.assertGreaterEqual(len(plan["next_options"]), 2)

        # Explicit opt-in succeeds honestly
        opt_plan = build_rapid_plan("quantum field theory --allow-general", vault_path=str(empty_vault))
        self.assertTrue(opt_plan["ready"])
        self.assertTrue(opt_plan["general_opt_in"])
        self.assertFalse(opt_plan["notes_grounded"])

    def test_07_hybrid_mode_blocks_silent_web_supplementation(self) -> None:
        vault, _ = self._create_vault_with_c_notes()
        # Compound query: Power Rule exists in Calculus.md, "Stokes Theorem" does NOT exist
        plan = build_rapid_plan("Power Rule and Stokes Theorem", vault_path=str(vault))
        self.assertTrue(plan["ready"])
        self.assertEqual(plan["source_mode"], "hybrid")
        self.assertTrue(plan["web_supplementation_blocked"])
        self.assertEqual(plan["web_augmentation_targets"], [])
        self.assertTrue(all(it["source_origin"].startswith("vault_note") for it in plan["planned_items"]))

        # Only when explicitly opted in with --allow-web are external targets surfaced separately
        plan_web = build_rapid_plan("Power Rule and Stokes Theorem --allow-web", vault_path=str(vault))
        self.assertFalse(plan_web["web_supplementation_blocked"])
        self.assertTrue(any(t["source_origin"] == "external_web" for t in plan_web["web_augmentation_targets"]))

    def test_08_direct_qa_without_forced_quiz(self) -> None:
        vault, _ = self._create_vault_with_c_notes()
        sess = resolve_session_dir(str(vault), session_slug="c-pointers", topic_hint="C Pointers", for_init=True)
        init_session_state(
            sess,
            topic_title="C Pointers",
            items=[{"slug": "01-deref", "title": "Dereference", "objective": "Explain & and *."}],
            mode="vault-native",
            vault_root=vault,
        )
        plan = build_rapid_plan("C pointers --mode qa", vault_path=str(vault), session_slug="c-pointers")
        self.assertTrue(plan["ready"])
        self.assertFalse(plan["force_quiz"])
        self.assertFalse(plan["record_test_results"])

        rec = record_rapid_answer(
            sess,
            item_key="C/Pointers.md::qa",
            concept_label="Address-of",
            result="pass",
        ) if (sess / "scratchpad" / "rapid-session.json").is_file() else None
        self.assertIsNone(rec)  # Q&A never even created rapid-session.json
        self.assertEqual(load_events(sess), [])

    def test_09_and_10_rapid_answer_checking_and_incorrect_remediation(self) -> None:
        vault, _ = self._create_vault_with_c_notes()
        plan = build_rapid_plan("C pointers --mode mcq --questions 5", vault_path=str(vault))
        sess = Path(plan["session_dir"])

        # Deterministic MCQ check: wrong then wrong (triggers difficulty reset & fresh followup)
        qspec = {
            "kind": "multiple_choice",
            "expected": "B",
            "choices": {"A": "1 byte", "B": "sizeof(int) bytes", "C": "8 bytes always"},
        }
        r1 = record_rapid_answer(
            sess,
            item_key="C/Pointers.md::Pointer Arithmetic::mcq",
            concept_label="Pointer Arithmetic",
            learner_answer="A",
            question_spec=qspec,
            misconception="Byte vs element stride",
            now="2026-11-18T10:00:00Z",
        )
        self.assertEqual(r1["result"], "fail")
        self.assertEqual(r1["pending_followups_count"], 1)

        r2 = record_rapid_answer(
            sess,
            item_key="C/Pointers.md::Address-Of and Dereference::mcq",
            concept_label="Address-Of",
            learner_answer="B",
            question_spec={"kind": "multiple_choice", "expected": "B"},
            now="2026-11-18T10:01:00Z",
        )
        self.assertEqual(r2["result"], "pass")

    def test_11_session_resumption(self) -> None:
        vault, _ = self._create_vault_with_c_notes()
        p1 = build_rapid_plan("C pointers --questions 6", vault_path=str(vault))
        sess = Path(p1["session_dir"])
        first_item = p1["planned_items"][0]
        record_rapid_answer(
            sess,
            item_key=first_item["item_key"],
            concept_label=first_item["source_heading"],
            result="pass",
            now="2026-11-18T10:00:00Z",
        )
        p2 = build_rapid_plan("--resume", vault_path=str(vault), session_slug=sess.name)
        self.assertTrue(p2["resumed"])
        self.assertEqual(p2["questions_answered_so_far"], 1)
        self.assertEqual(p2["question_budget"], 6)
        self.assertNotIn(first_item["item_key"], [it["item_key"] for it in p2["planned_items"]])

    def test_12_and_13_budget_and_honest_unanswered_reporting(self) -> None:
        parsed_q = parse_rapid_invocation("machine learning --questions 20")
        self.assertEqual(parsed_q["questions"], 20)
        parsed_m = parse_rapid_invocation("C pointers --minutes 10")
        self.assertEqual(parsed_m["minutes"], 10)
        self.assertGreaterEqual(parsed_m["questions"], 4)

        vault, _ = self._create_vault_with_c_notes()
        plan = build_rapid_plan("C pointers --questions 5", vault_path=str(vault))
        sess = Path(plan["session_dir"])
        record_rapid_answer(
            sess,
            item_key="item-1",
            concept_label="Address-Of",
            result="pass",
            now="2026-11-18T10:00:00Z",
        )
        record_rapid_answer(
            sess,
            item_key="item-2",
            concept_label="Pointer Arithmetic",
            result="fail",
            now="2026-11-18T10:01:00Z",
        )
        rep = build_rapid_status_report(sess)
        self.assertEqual(rep["questions_budgeted"], 5)
        self.assertEqual(rep["questions_answered"], 2)
        self.assertEqual(rep["unanswered_count"], 3)
        self.assertEqual(rep["correct"], 1)
        self.assertEqual(rep["incorrect"], 1)
        self.assertEqual(rep["active_time_sec"], "unavailable")
        self.assertFalse(rep["delayed_retention_recorded"])

    def test_14_and_15_shared_mastery_evidence_and_no_fabricated_delayed_retention(self) -> None:
        vault, _ = self._create_vault_with_c_notes()
        sess = resolve_session_dir(str(vault), session_slug="c-pointers", topic_hint="C Pointers", for_init=True)
        init_session_state(
            sess,
            topic_title="C Pointers",
            items=[{"slug": "01-deref", "title": "Address-Of and Dereference", "objective": "Use & and * operators safely."}],
            mode="vault-native",
            vault_root=vault,
        )
        plan = build_rapid_plan("C pointers --questions 4", vault_path=str(vault), session_slug="c-pointers")
        item = plan["planned_items"][0]

        # Even if two rapid answers are spaced out or repeated in same session, run_id blocks delayed retention
        r1 = record_rapid_answer(
            sess,
            item_key=item["item_key"],
            concept_label="Address-Of",
            result="pass",
            assistance="none",
            topic_num="01",
            objective_id="obj-01-01",
            now="2026-11-18T10:00:00Z",
        )
        r2 = record_rapid_answer(
            sess,
            item_key=item["item_key"] + "-v2",
            concept_label="Address-Of",
            result="pass",
            assistance="none",
            topic_num="01",
            objective_id="obj-01-01",
            now="2026-11-18T23:00:00Z",
        )
        self.assertTrue(r1["shared_assessment_recorded"])
        self.assertFalse(r2["delayed_retention_recorded"])

        ctx = json.loads(run_cli("context", str(sess), "--topic", "01", env=self.env).stdout)
        obj = ctx["curriculum"]["objectives"][0]
        self.assertEqual(obj["proficiency_status"], "demonstrated_independently")
        self.assertEqual(obj["retention_status"], "untested")

    def test_16_no_study_note_creation_or_modification(self) -> None:
        vault, orig_notes = self._create_vault_with_c_notes()
        r_plan = run_cli("rapid-plan", str(vault), "--args", "C pointers --questions 3", env=self.env)
        self.assertEqual(r_plan.returncode, 0, r_plan.stderr)
        p_out = json.loads(r_plan.stdout)
        sess = Path(p_out["session_dir"])

        run_cli(
            "rapid-record", str(sess),
            "--item-key", "C/Pointers.md::Address-Of and Dereference::recall",
            "--concept", "Address-Of",
            "--result", "pass",
            env=self.env,
        )
        r_stat = run_cli("rapid-status", str(sess), env=self.env)
        self.assertEqual(r_stat.returncode, 0, r_stat.stderr)

        for npath, orig_text in orig_notes.items():
            self.assertEqual(npath.read_text(encoding="utf-8"), orig_text)
        self.assertFalse((vault / "08-FLASHCARDS.md").exists())
        self.assertFalse((vault / "09-CHEAT-SHEET.md").exists())
        self.assertFalse((sess / "topics").exists())


if __name__ == "__main__":
    unittest.main()
