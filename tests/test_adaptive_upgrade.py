"""Comprehensive tests for adaptive teaching state, scheduling, migration, provenance, and handoff."""

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


class AdaptiveUpgradeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="teachme_adaptive_"))
        self.cfg_path = self.tmp / "teachme-config.json"
        self.env = {"TEACHME_CONFIG_PATH": str(self.cfg_path)}

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _init_two_topic_session(self, name: str = "calc-session") -> Path:
        session = self.tmp / "notes" / name
        sub_file = self.tmp / f"{name}-subtopics.json"
        write_file(
            sub_file,
            json.dumps(
                [
                    {
                        "slug": "01-derivatives",
                        "title": "Derivatives & Slopes",
                        "depends_on": [],
                        "objective": "Interpret derivative as instantaneous rate of change",
                        "anchor": "Slope of the tangent line.",
                        "objectives": [
                            {
                                "id": "obj-01-slope",
                                "description": "Interpret derivative sign and magnitude geometrically",
                                "required": True,
                                "in_scope": True,
                                "prerequisite_refs": [],
                                "assumptions": ["Function is differentiable at the point"],
                                "expected_assessments": ["explain_concept", "apply_procedure"],
                            },
                            {
                                "id": "obj-01-opt",
                                "description": "Optional higher-order curvature note",
                                "required": False,
                                "in_scope": False,
                                "prerequisite_refs": ["obj-01-slope"],
                            },
                        ],
                    },
                    {
                        "slug": "02-gradient-descent",
                        "title": "Gradient Descent Step",
                        "depends_on": ["topic-01"],
                        "objective": "Apply update w <- w - eta * grad",
                        "anchor": "Move opposite the uphill slope.",
                        "objectives": [
                            {
                                "id": "obj-02-step",
                                "description": "Compute and predict gradient descent step direction",
                                "required": True,
                                "in_scope": True,
                                "prerequisite_refs": ["obj-01-slope"],
                                "assumptions": ["Small enough step size eta"],
                                "expected_assessments": ["prediction", "independent_application"],
                            }
                        ],
                    },
                ]
            ),
        )
        res = run_cli(
            "init",
            str(session),
            "--topic",
            "Gradient Optimization",
            "--subtopics",
            str(sub_file),
            "--goal",
            "Understand 1D gradient descent",
            env=self.env,
        )
        self.assertEqual(res.returncode, 0, res.stderr)
        return session

    def test_01_old_session_loads_and_migrates_idempotently_without_fabricated_evidence(self) -> None:
        """Old v1 sessions load without fabricated retention/transfer; migration backs up & is idempotent."""
        session = self.tmp / "old-v1-session"
        write_file(
            session / "00-SESSION-STATE.md",
            "# Session State: Old Topic\n\n"
            "- **Active Subtopic:** `topic-01`\n"
            "- **Live Stage & Checkpoint:** `Depth Stage 3/3 | Checkpoint [4/4]`\n"
            "- **Last Verified Invariant:** Old invariant.\n\n"
            "## Compact Subtopic Status Map\n"
            "`[x] 01` `[ ] 02`\n",
        )
        write_file(
            session / "00-GRAPH.json",
            json.dumps(
                {
                    "schema_version": 1,
                    "topic": "Old Topic",
                    "custom_top_tag": "preserve-top",
                    "nodes": {
                        "topic-01": {
                            "slug": "01-intro",
                            "title": "Intro",
                            "status": "mastered",
                            "checkpoint": "4/4",
                            "depends_on": [],
                            "unlocks": ["topic-02"],
                            "last_invariant": "Old invariant.",
                            "mastered_at": "2026-10-01T10:00:00Z",
                            "custom_node_meta": "keep-me",
                        },
                        "topic-02": {
                            "slug": "02-next",
                            "title": "Next",
                            "status": "unstarted",
                            "checkpoint": "0/4",
                            "depends_on": ["topic-01"],
                            "unlocks": [],
                        },
                    },
                    "order": ["topic-01", "topic-02"],
                }
            ),
        )
        write_file(
            session / "scratchpad" / "events.jsonl",
            json.dumps({"ts": "2026-10-01T10:00:00Z", "topic": "01", "stage": 3, "cp": 4, "status": "pass"}) + "\n",
        )

        # Coverage before explicit migrate works and does NOT fabricate retention or transfer
        r_cov = run_cli("coverage", str(session), "--now", "2026-11-18T12:00:00Z", env=self.env)
        self.assertEqual(r_cov.returncode, 0, r_cov.stderr)
        cov = json.loads(r_cov.stdout)
        objs = {o["objective_id"]: o for o in cov["objectives"]}
        self.assertEqual(objs["obj-01-01"]["proficiency_status"], "legacy_unverified")
        self.assertEqual(objs["obj-01-01"]["retention_status"], "untested")
        self.assertEqual(objs["obj-01-01"]["transfer_status"], "untested")
        self.assertFalse(cov["scope_complete"])

        # Migrate creates backup, upgrades curriculum.json to v2, and is idempotent
        r_mig1 = run_cli("migrate", str(session), env=self.env)
        self.assertEqual(r_mig1.returncode, 0, r_mig1.stderr)
        mig1 = json.loads(r_mig1.stdout)
        self.assertTrue(mig1["ok"])
        self.assertTrue(mig1["changed"])
        self.assertIsNotNone(mig1["backup_dir"])
        self.assertTrue(Path(mig1["backup_dir"]).is_dir())

        curr_after_1 = (session / "scratchpad" / "curriculum.json").read_text(encoding="utf-8")
        curr_data = json.loads(curr_after_1)
        self.assertEqual(curr_data["schema_version"], 2)
        self.assertEqual(curr_data["nodes"]["topic-01"]["custom_node_meta"], "keep-me")
        self.assertEqual(curr_data["nodes"]["topic-01"]["objectives"][0]["proficiency"]["retention"]["status"], "untested")
        self.assertEqual(curr_data["nodes"]["topic-01"]["objectives"][0]["proficiency"]["transfer"]["status"], "untested")

        r_mig2 = run_cli("migrate", str(session), env=self.env)
        self.assertEqual(r_mig2.returncode, 0, r_mig2.stderr)
        mig2 = json.loads(r_mig2.stdout)
        self.assertFalse(mig2["changed"])
        self.assertEqual((session / "scratchpad" / "curriculum.json").read_text(encoding="utf-8"), curr_after_1)

        # Progress reports active_time_sec as 'unavailable' (never fabricated)
        r_prog = run_cli("progress", str(session), "--now", "2026-11-18T12:00:00Z", env=self.env)
        self.assertEqual(r_prog.returncode, 0, r_prog.stderr)
        self.assertEqual(json.loads(r_prog.stdout)["active_time_sec"], "unavailable")

    def test_02_assisted_vs_independent_and_untested_required_objectives(self) -> None:
        """Assisted success does not become independent success; required untested objectives stay visible."""
        session = self._init_two_topic_session("assist-vs-indep")

        # Assisted pass (worked_example) on obj-01-slope
        r_a = run_cli(
            "assess",
            str(session),
            "--topic",
            "01",
            "--objective",
            "obj-01-slope",
            "--assessment-type",
            "worked_example_completion",
            "--result",
            "pass",
            "--assistance",
            "worked_example",
            "--rationale",
            "Solved after worked example",
            "--now",
            "2026-11-10T10:00:00Z",
            env=self.env,
        )
        self.assertEqual(r_a.returncode, 0, r_a.stderr)

        r_cov = run_cli("coverage", str(session), "--now", "2026-11-10T10:05:00Z", env=self.env)
        cov = json.loads(r_cov.stdout)
        objs = {o["objective_id"]: o for o in cov["objectives"]}
        self.assertEqual(objs["obj-01-slope"]["proficiency_status"], "practiced_with_support")
        self.assertEqual(objs["obj-01-slope"]["coverage_status"], "assessed")
        self.assertEqual(objs["obj-01-opt"]["coverage_status"], "out_of_scope")
        self.assertEqual(cov["assisted_successes"], 1)
        self.assertEqual(cov["independent_successes"], 0)
        self.assertFalse(cov["scope_complete"])
        untested_ids = [u["objective_id"] for u in cov["required_untested"]]
        self.assertIn("obj-02-step", untested_ids)

    def test_03_review_scheduler_rules_fixed_clock(self) -> None:
        """Tests same-session, early practice, delayed retrieval, assisted review, failed review, and due previously demonstrated topics."""
        session = self._init_two_topic_session("scheduler-rules")

        # Day 0 (10:00): Independent pass on obj-01-slope
        run_cli(
            "assess",
            str(session),
            "--topic",
            "01",
            "--objective",
            "obj-01-slope",
            "--assessment-type",
            "independent_application",
            "--result",
            "pass",
            "--assistance",
            "none",
            "--session-run",
            "run-1",
            "--now",
            "2026-11-01T10:00:00Z",
            env=self.env,
        )
        rev1 = json.loads((session / "scratchpad" / "review-state.json").read_text(encoding="utf-8"))
        item = rev1["items"]["obj-01-slope"]
        self.assertEqual(item["stage"], 0)
        self.assertEqual(item["interval_days"], 1)
        self.assertEqual(item["next_review_at"], "2026-11-02T10:00:00Z")

        # Same-session retry 2 hours later: MUST NOT count as delayed retention or advance stage
        run_cli(
            "assess",
            str(session),
            "--topic",
            "01",
            "--objective",
            "obj-01-slope",
            "--assessment-type",
            "delayed_recall",
            "--result",
            "pass",
            "--assistance",
            "none",
            "--session-run",
            "run-1",
            "--now",
            "2026-11-01T12:00:00Z",
            env=self.env,
        )
        rev2 = json.loads((session / "scratchpad" / "review-state.json").read_text(encoding="utf-8"))
        self.assertEqual(rev2["items"]["obj-01-slope"]["stage"], 0)
        self.assertEqual(rev2["items"]["obj-01-slope"]["next_review_at"], "2026-11-02T10:00:00Z")

        cov_same = json.loads(run_cli("coverage", str(session), "--now", "2026-11-01T12:00:00Z", env=self.env).stdout)
        self.assertEqual(cov_same["delayed_retained_objectives"], 0)

        # Early practice on 2026-11-02T08:00:00Z (before 10:00 due): MUST NOT postpone next_review_at
        run_cli(
            "assess",
            str(session),
            "--topic",
            "01",
            "--objective",
            "obj-01-slope",
            "--assessment-type",
            "independent_application",
            "--result",
            "pass",
            "--assistance",
            "none",
            "--session-run",
            "run-2",
            "--now",
            "2026-11-02T08:00:00Z",
            env=self.env,
        )
        rev_early = json.loads((session / "scratchpad" / "review-state.json").read_text(encoding="utf-8"))
        self.assertEqual(rev_early["items"]["obj-01-slope"]["next_review_at"], "2026-11-02T10:00:00Z")
        self.assertEqual(rev_early["items"]["obj-01-slope"]["stage"], 0)

        # Opening due check at 2026-11-02T11:00:00Z: includes previously demonstrated obj-01-slope, mutates nothing!
        before_bytes = (session / "scratchpad" / "review-state.json").read_bytes()
        r_due = run_cli("due", str(session), "--now", "2026-11-02T11:00:00Z", env=self.env)
        self.assertEqual(r_due.returncode, 0, r_due.stderr)
        due_data = json.loads(r_due.stdout)
        self.assertEqual(due_data["due_count"], 1)
        self.assertEqual(due_data["due_items"][0]["objective_id"], "obj-01-slope")
        self.assertEqual(due_data["due_items"][0]["proficiency_status"], "demonstrated_independently")
        self.assertEqual((session / "scratchpad" / "review-state.json").read_bytes(), before_bytes)

        # Assisted review at 2026-11-02T11:05:00Z: MUST NOT advance stage to 1 (3 days)
        run_cli(
            "assess",
            str(session),
            "--topic",
            "01",
            "--objective",
            "obj-01-slope",
            "--assessment-type",
            "delayed_recall",
            "--result",
            "pass",
            "--assistance",
            "hint",
            "--session-run",
            "run-3",
            "--now",
            "2026-11-02T11:05:00Z",
            env=self.env,
        )
        rev_assist = json.loads((session / "scratchpad" / "review-state.json").read_text(encoding="utf-8"))
        self.assertEqual(rev_assist["items"]["obj-01-slope"]["stage"], 0)
        self.assertEqual(rev_assist["items"]["obj-01-slope"]["interval_days"], 1)
        self.assertEqual(rev_assist["items"]["obj-01-slope"]["next_review_at"], "2026-11-03T11:05:00Z")

        # Delayed independent retrieval at 2026-11-03T12:00:00Z: advances stage 0 -> 1 (3 days) and marks retained!
        run_cli(
            "assess",
            str(session),
            "--topic",
            "01",
            "--objective",
            "obj-01-slope",
            "--assessment-type",
            "delayed_recall",
            "--result",
            "pass",
            "--assistance",
            "none",
            "--session-run",
            "run-4",
            "--now",
            "2026-11-03T12:00:00Z",
            env=self.env,
        )
        rev_adv = json.loads((session / "scratchpad" / "review-state.json").read_text(encoding="utf-8"))
        self.assertEqual(rev_adv["items"]["obj-01-slope"]["stage"], 1)
        self.assertEqual(rev_adv["items"]["obj-01-slope"]["interval_days"], 3)
        self.assertEqual(rev_adv["items"]["obj-01-slope"]["next_review_at"], "2026-11-06T12:00:00Z")

        cov_ret = json.loads(run_cli("coverage", str(session), "--now", "2026-11-03T12:00:00Z", env=self.env).stdout)
        self.assertEqual(cov_ret["delayed_retained_objectives"], 1)

        # Failed review at 2026-11-06T13:00:00Z: increments lapse_count, resets stage=0, preserves historical success!
        run_cli(
            "assess",
            str(session),
            "--topic",
            "01",
            "--objective",
            "obj-01-slope",
            "--assessment-type",
            "delayed_recall",
            "--result",
            "fail",
            "--assistance",
            "none",
            "--misconception",
            "LR-0001",
            "--rationale",
            "Flipped derivative sign for decreasing function",
            "--session-run",
            "run-5",
            "--now",
            "2026-11-06T13:00:00Z",
            env=self.env,
        )
        rev_fail = json.loads((session / "scratchpad" / "review-state.json").read_text(encoding="utf-8"))
        self.assertEqual(rev_fail["items"]["obj-01-slope"]["stage"], 0)
        self.assertEqual(rev_fail["items"]["obj-01-slope"]["lapse_count"], 1)
        self.assertEqual(rev_fail["items"]["obj-01-slope"]["next_review_at"], "2026-11-07T13:00:00Z")

        cov_fail = json.loads(run_cli("coverage", str(session), "--now", "2026-11-06T13:00:00Z", env=self.env).stdout)
        unres = {u["objective_id"]: u for u in cov_fail["unresolved_objectives"]}
        self.assertEqual(unres["obj-01-slope"]["proficiency_status"], "weakened")
        self.assertEqual(unres["obj-01-slope"]["prior_independent_success_at"], "2026-11-03T12:00:00Z")
        self.assertIsNotNone(unres["obj-01-slope"]["current_weakness"])

    def test_04_prerequisite_revision_and_validation_catches_cycles_and_broken_refs(self) -> None:
        """Inserting a prerequisite preserves evidence & resume position; invalid refs & cycles are rejected."""
        session = self._init_two_topic_session("revise-dag")
        run_cli(
            "assess",
            str(session),
            "--topic",
            "02",
            "--objective",
            "obj-02-step",
            "--result",
            "fail",
            "--assistance",
            "none",
            "--rationale",
            "Unsure about vector scaling",
            "--now",
            "2026-11-18T10:00:00Z",
            env=self.env,
        )

        # Insert discovered prerequisite node topic-00 before topic-02
        r_rev = run_cli(
            "revise-curriculum",
            str(session),
            "--slug",
            "00-vector-scaling",
            "--title",
            "Scalar Multiplication of Vectors",
            "--objective",
            "Scale each vector component by scalar eta",
            "--unlocks",
            "topic-02",
            "--before-topic",
            "02",
            env=self.env,
        )
        self.assertEqual(r_rev.returncode, 0, r_rev.stderr)
        self.assertTrue(json.loads(r_rev.stdout)["ok"])

        # Resume position (topic-02) and prior fail event preserved
        st = json.loads(run_cli("state", str(session), env=self.env).stdout)
        self.assertEqual(st["active_topic"], "topic-02")
        ctx2 = json.loads(run_cli("context", str(session), "--topic", "02", env=self.env).stdout)
        self.assertIn("topic-00", ctx2["curriculum"]["depends_on"])
        self.assertEqual(len(ctx2["recent_events"]), 1)

        # Broken objective reference must fail revise-curriculum and not corrupt state
        r_bad_ref = run_cli(
            "revise-curriculum",
            str(session),
            "--target-topic",
            "02",
            "--objective-id",
            "obj-02-step",
            "--prerequisite-ref",
            "obj-does-not-exist",
            env=self.env,
        )
        self.assertNotEqual(r_bad_ref.returncode, 0)

        # Cycle in objective prerequisite_refs must fail validate-state / revise-curriculum
        r_cyc = run_cli(
            "revise-curriculum",
            str(session),
            "--target-topic",
            "01",
            "--objective-id",
            "obj-01-slope",
            "--prerequisite-ref",
            "obj-02-step",
            env=self.env,
        )
        self.assertNotEqual(r_cyc.returncode, 0)

        # Explicitly corrupt curriculum.json with cycle and verify validate-state catches it
        curr_path = session / "scratchpad" / "curriculum.json"
        curr = json.loads(curr_path.read_text(encoding="utf-8"))
        curr["nodes"]["topic-01"]["objectives"][0]["prerequisite_refs"] = ["obj-02-step"]
        curr_path.write_text(json.dumps(curr), encoding="utf-8")
        r_val = run_cli("validate-state", str(session), env=self.env)
        self.assertNotEqual(r_val.returncode, 0)
        val_report = json.loads(r_val.stdout)
        self.assertFalse(val_report["ok"])
        self.assertTrue(any(e["type"] == "curriculum_cycle" for e in val_report["errors"]))

    def test_05_context_bounded_idempotent_attempt_and_calibration(self) -> None:
        """Context stays bounded with visible gaps; attempt-id deduplicates retries; skipped prereqs stay unknown."""
        session = self._init_two_topic_session("ctx-cal")

        # Calibration with skipped prerequisite -> remains 'unknown'
        r_cal = run_cli(
            "calibrate",
            str(session),
            "--time-budget",
            "20",
            "--diagnostic-status",
            "skipped",
            "--prereq",
            "chain_rule=unknown:Skipped by learner",
            "--prereq",
            "algebra=demonstrated:Solved 2 equations",
            env=self.env,
        )
        self.assertEqual(r_cal.returncode, 0, r_cal.stderr)

        # Emit 15 events; attempt-id deduplication should prevent duplicate event on retry
        for i in range(15):
            r_ev = run_cli(
                "assess",
                str(session),
                "--topic",
                "01",
                "--objective",
                "obj-01-slope",
                "--result",
                "pass",
                "--assistance",
                "none",
                "--attempt-id",
                f"att-{i}",
                "--active-time",
                "30",
                "--now",
                "2026-11-18T10:00:00Z",
                env=self.env,
            )
            self.assertEqual(r_ev.returncode, 0, r_ev.stderr)

        # Retry same attempt-id -> deduplicated!
        r_dup = run_cli(
            "assess",
            str(session),
            "--topic",
            "01",
            "--objective",
            "obj-01-slope",
            "--result",
            "pass",
            "--assistance",
            "none",
            "--attempt-id",
            "att-0",
            "--now",
            "2026-11-18T10:00:00Z",
            env=self.env,
        )
        self.assertEqual(r_dup.returncode, 0, r_dup.stderr)
        self.assertTrue(json.loads(r_dup.stdout)["deduplicated"])
        lines = [ln for ln in (session / "scratchpad" / "events.jsonl").read_text(encoding="utf-8").splitlines() if ln.strip()]
        self.assertEqual(len(lines), 15)

        ctx = json.loads(run_cli("context", str(session), "--topic", "01", env=self.env).stdout)
        self.assertLessEqual(len(ctx["recent_events"]), 10)
        self.assertEqual(ctx["prerequisite_states"]["chain_rule"]["state"], "unknown")
        self.assertGreaterEqual(ctx["gaps_summary"]["required_untested_count"], 1)

        prog = json.loads(run_cli("progress", str(session), env=self.env).stdout)
        self.assertEqual(prog["active_time_sec"], 450.0)

    def test_06_media_provenance_honesty_and_handoff_separation(self) -> None:
        """Media provenance never fabricates license/verification; handoff separates introduced/demonstrated/retained/transferred."""
        session = self._init_two_topic_session("media-handoff")

        # Record media with omitted license -> defaults to 'unknown'; metadata_only_unverified stays unverified
        plot_file = write_file(session / "scratchpad" / "media" / "loss.png", "fake-png-bytes")
        r_med = run_cli(
            "record-media",
            str(session),
            "--objective",
            "obj-01-slope",
            "--kind",
            "retrieved_image",
            "--source-page",
            "https://example.org/slopes",
            "--verification",
            "metadata_only_unverified",
            "--local-path",
            str(plot_file),
            "--fallback-text",
            "Table of (x, x^2, 2x)",
            env=self.env,
        )
        self.assertEqual(r_med.returncode, 0, r_med.stderr)
        entry = json.loads(r_med.stdout)["entry"]
        self.assertEqual(entry["license"], "unknown")
        self.assertEqual(entry["verification_status"], "metadata_only_unverified")
        self.assertTrue(entry["sha256"])

        # Reject path traversal outside session dir
        outside = self.tmp / "outside.png"
        outside.write_text("bad", encoding="utf-8")
        r_bad_path = run_cli(
            "record-media",
            str(session),
            "--objective",
            "obj-01-slope",
            "--local-path",
            str(outside),
            env=self.env,
        )
        self.assertNotEqual(r_bad_path.returncode, 0)

        # Topic 01: independent + transfer; Topic 02: assisted only (introduced/practiced_with_support)
        run_cli(
            "assess",
            str(session),
            "--topic",
            "01",
            "--objective",
            "obj-01-slope",
            "--assessment-type",
            "transfer",
            "--transfer-context",
            "Interpreting marginal cost slope in economics",
            "--result",
            "pass",
            "--assistance",
            "none",
            "--now",
            "2026-11-10T10:00:00Z",
            env=self.env,
        )
        run_cli(
            "assess",
            str(session),
            "--topic",
            "02",
            "--objective",
            "obj-02-step",
            "--assessment-type",
            "worked_example_completion",
            "--result",
            "pass",
            "--assistance",
            "scaffold",
            "--now",
            "2026-11-10T10:15:00Z",
            env=self.env,
        )

        r_hand = run_cli("handoff", str(session), "--request", "study notes", env=self.env)
        self.assertEqual(r_hand.returncode, 0, r_hand.stderr)
        env_data = json.loads(r_hand.stdout)

        self.assertEqual(len(env_data["objectives_demonstrated"]), 1)
        self.assertEqual(env_data["objectives_demonstrated"][0]["id"], "obj-01-slope")
        self.assertEqual(env_data["objectives_demonstrated"][0]["transfer_status"], "demonstrated")
        self.assertEqual(env_data["objectives_demonstrated"][0]["retention_status"], "untested")

        self.assertEqual(len(env_data["concepts_introduced"]), 1)
        self.assertEqual(env_data["concepts_introduced"][0]["id"], "obj-02-step")

        claims = {c["id"]: c for c in env_data["mastery_claims"]}
        self.assertEqual(claims["topic-02"]["assessed_status"], "practiced_with_support")
        self.assertNotEqual(claims["topic-02"]["assessed_status"], "mastered")
        self.assertEqual(len(env_data["media_provenance"]), 1)
        self.assertEqual(env_data["media_provenance"][0]["license"], "unknown")

    def test_07_legacy_tick_and_flush_remain_compatible_and_honest(self) -> None:
        """Legacy tick/flush preserve compatibility without fabricating retention or transfer."""
        session = self._init_two_topic_session("legacy-compat")
        r_tick = run_cli("tick", str(session), "--topic", "01", "--cp", "2", "--status", "pass", env=self.env)
        self.assertEqual(r_tick.returncode, 0, r_tick.stderr)
        t_out = json.loads(r_tick.stdout)
        self.assertEqual(t_out["assistance_level"], "unknown")

        r_flush = run_cli("flush", str(session), "--topic", "01", "--note", "Legacy invariant", env=self.env)
        self.assertEqual(r_flush.returncode, 0, r_flush.stderr)
        f_out = json.loads(r_flush.stdout)
        self.assertFalse(f_out["retention_verified"])
        self.assertFalse(f_out["transfer_verified"])

        cov = json.loads(run_cli("coverage", str(session), env=self.env).stdout)
        objs = {o["objective_id"]: o for o in cov["objectives"]}
        self.assertEqual(objs["obj-01-slope"]["retention_status"], "untested")
        self.assertEqual(objs["obj-01-slope"]["transfer_status"], "untested")


if __name__ == "__main__":
    unittest.main()
