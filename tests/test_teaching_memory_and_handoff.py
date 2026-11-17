"""Regression tests for teaching-and-memory-only TeachMe refactor and Scriptorium handoff."""

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

import teachme_vault
from teachme_vault.state_store import HANDOFF_SCHEMA_VERSION


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


class TeachingMemoryAndHandoffTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="teachme_reg_test_"))
        self.cfg_path = self.tmp / "teachme-config.json"
        self.env = {"TEACHME_CONFIG_PATH": str(self.cfg_path)}

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _make_subtopics(self) -> Path:
        p = self.tmp / "subtopics.json"
        write_file(
            p,
            json.dumps(
                [
                    {
                        "slug": "01-vectors",
                        "title": "Vectors and Dot Products",
                        "depends_on": [],
                        "contrasts_with": [],
                        "objective": "Compute and interpret dot products geometrically.",
                        "anchor": "Dot product measures alignment weighted by lengths.",
                        "key_concepts": ["dot product", "projection"],
                        "key_equations": ["a \\cdot b = \\|a\\|\\|b\\|\\cos\\theta"],
                    },
                    {
                        "slug": "02-hyperplanes",
                        "title": "Separating Hyperplanes",
                        "depends_on": ["topic-01"],
                        "contrasts_with": [],
                        "objective": "Classify points using signed distance w^T x + b.",
                        "anchor": "A hyperplane slices space into positive and negative half-spaces.",
                        "key_concepts": ["normal vector", "bias"],
                        "key_equations": ["w^T x + b = 0"],
                    },
                ]
            ),
        )
        return p

    def test_a_and_b_standalone_teaching_lifecycle_resume_across_processes(self) -> None:
        """A & B: Works without Scriptorium or study notes; retry -> pass -> flush -> resume preserves exact state."""
        session = self.tmp / "notes" / "linear-classifiers"
        sub_file = self._make_subtopics()

        res_init = run_cli(
            "init", str(session), "--topic", "Linear Classifiers", "--subtopics", str(sub_file),
            env=self.env,
        )
        self.assertEqual(res_init.returncode, 0, res_init.stderr)
        init_out = json.loads(res_init.stdout)
        self.assertTrue(init_out["ok"])

        # No study notes or note scaffolds created
        self.assertFalse((session / "topics").exists())
        self.assertFalse((session / "atomic").exists())
        self.assertFalse((session / "00-MOC-INDEX.md").exists())
        self.assertFalse((session / "03-CORNELL-STUDY-GUIDE.md").exists())
        self.assertFalse((session / "08-FLASHCARDS.md").exists())
        self.assertFalse((session / "09-CHEAT-SHEET.md").exists())
        self.assertTrue((session / "00-SESSION-STATE.md").is_file())
        self.assertTrue((session / "00-GRAPH.json").is_file())
        self.assertTrue((session / "learning-records").is_dir())
        self.assertTrue((session / "scratchpad" / "curriculum.json").is_file())

        # Begin lesson -> retry -> pass -> flush
        r_ctx1 = run_cli("context", str(session), "--topic", "01", env=self.env)
        self.assertEqual(r_ctx1.returncode, 0, r_ctx1.stderr)
        ctx1 = json.loads(r_ctx1.stdout)
        self.assertEqual(ctx1["curriculum"]["title"], "Vectors and Dot Products")

        r_retry = run_cli(
            "tick", str(session), "--topic", "01", "--cp", "2", "--status", "retry",
            "--note", "Confused angle cosine with sine", env=self.env,
        )
        self.assertEqual(r_retry.returncode, 0, r_retry.stderr)

        r_pass2 = run_cli(
            "tick", str(session), "--topic", "01", "--cp", "2", "--status", "pass",
            "--note", "a.b = 0 iff perpendicular", env=self.env,
        )
        self.assertEqual(r_pass2.returncode, 0, r_pass2.stderr)

        # Resume in a fresh process before flush: must show cp 2/4 and last invariant
        r_state_mid = run_cli("state", str(session), env=self.env)
        self.assertEqual(r_state_mid.returncode, 0, r_state_mid.stderr)
        st_mid = json.loads(r_state_mid.stdout)
        self.assertEqual(st_mid["active_topic"], "topic-01")
        self.assertEqual(st_mid["checkpoint"], "2/4")
        self.assertEqual(st_mid["completed_count"], 0)
        self.assertEqual(st_mid["last_invariant"], "a.b = 0 iff perpendicular")

        r_pass4 = run_cli(
            "tick", str(session), "--topic", "01", "--cp", "4", "--status", "pass",
            "--note", "Dot product measures signed projection", env=self.env,
        )
        self.assertEqual(r_pass4.returncode, 0, r_pass4.stderr)

        r_flush = run_cli(
            "flush", str(session), "--topic", "01",
            "--note", "Dot product measures signed projection", env=self.env,
        )
        self.assertEqual(r_flush.returncode, 0, r_flush.stderr)
        self.assertTrue(json.loads(r_flush.stdout)["state_only"])

        # New process resume check
        r_state_end = run_cli("state", str(session), env=self.env)
        st_end = json.loads(r_state_end.stdout)
        self.assertEqual(st_end["completed_count"], 1)
        self.assertEqual(st_end["total_count"], 2)
        self.assertEqual(st_end["checkpoint"], "4/4")

        r_ctx2 = run_cli("context", str(session), "--topic", "02", env=self.env)
        ctx2 = json.loads(r_ctx2.stdout)
        self.assertIn("topic-01", ctx2["neighbors"])
        self.assertEqual(ctx2["neighbors"]["topic-01"]["status"], "mastered")

        r_val = run_cli("validate-state", str(session), env=self.env)
        self.assertEqual(r_val.returncode, 0, r_val.stdout)
        self.assertTrue(json.loads(r_val.stdout)["ok"])

    def test_e_and_f_legacy_import_idempotent_lossless_and_non_destructive(self) -> None:
        """E & F: Legacy note-embedded memory imports losslessly & idempotently; study notes stay untouched."""
        legacy = self.tmp / "LegacyVault"
        topic1_content = (
            "---\n"
            'id: "topic-01"\n'
            'title: "Linear Model"\n'
            'status: "mastered"\n'
            'checkpoint: "4/4"\n'
            "depends_on: []\n"
            'unlocks: ["topic-02"]\n'
            'custom_legacy_tag: "keep-me-losslessly"\n'
            "---\n\n"
            "# 01. Linear Model\n\n"
            "### 4-Checkpoint Mastery Ledger\n"
            "- [x] `[1/4]` Discovery Prediction\n"
            "- [x] `[2/4]` We-Do Faded Step\n"
            "- [x] `[3/4]` You-Do Cold Drill\n"
            "- [x] `[4/4]` Edge-Case & Feynman Gate\n"
        )
        topic2_content = (
            "---\n"
            'id: "topic-02"\n'
            'title: "Gradient Step"\n'
            'status: "unstarted"\n'
            'checkpoint: "1/4"\n'
            'depends_on: ["topic-01"]\n'
            "---\n\n"
            "# 02. Gradient Step\n\n"
            "### 4-Checkpoint Mastery Ledger\n"
            "- [x] `[1/4]` Discovery Prediction\n"
            "- [ ] `[2/4]` We-Do Faded Step\n"
            "- [ ] `[3/4]` You-Do Cold Drill\n"
            "- [ ] `[4/4]` Edge-Case & Feynman Gate\n"
        )
        moc_content = "# MOC\n- [x] **01.** [[topics/01-linear]]\n- [ ] **02.** [[topics/02-grad]]\n"
        t1 = write_file(legacy / "topics" / "01-linear.md", topic1_content)
        t2 = write_file(legacy / "topics" / "02-grad.md", topic2_content)
        moc = write_file(legacy / "00-MOC-INDEX.md", moc_content)
        write_file(
            legacy / "00-SESSION-STATE.md",
            "# Session State: Legacy\n\n"
            "- **Active Subtopic:** `topics/02-grad.md`\n"
            "- **Live Stage & Checkpoint:** `Depth Stage 2/3 | Checkpoint [2/4]`\n"
            "- **Last Verified Invariant:** Linear weights scale inputs.\n\n"
            "## Compact Subtopic Status Map\n"
            "`[x] 01` `[~] 02`\n",
        )
        write_file(
            legacy / "scratchpad" / "events.jsonl",
            json.dumps({"ts": "2026-01-01T10:00:00Z", "topic": "01", "stage": 3, "cp": 4, "status": "pass", "note": "Linear weights scale inputs"}) + "\n",
        )
        write_file(
            legacy / "learning-records" / "0001-sign-flip.md",
            "# LR-0001: Sign Flip\n- **Date:** 2026-01-01 | **Status:** active | **Lesson:** 1/2\n## Context\nForgot minus sign.\n## Insight\nGradient descent subtracts the gradient.\n",
        )

        # Also test flush on legacy fixture NEVER mutates topics/*.md or 00-MOC-INDEX.md
        r_imp1 = run_cli("import-legacy", str(legacy), env=self.env)
        self.assertEqual(r_imp1.returncode, 0, r_imp1.stderr)
        imp1 = json.loads(r_imp1.stdout)
        self.assertTrue(imp1["ok"])
        self.assertFalse(imp1["source_notes_modified"])
        self.assertEqual(imp1["nodes_imported"], 2)

        graph_after_1 = (legacy / "00-GRAPH.json").read_text(encoding="utf-8")
        curr_after_1 = (legacy / "scratchpad" / "curriculum.json").read_text(encoding="utf-8")

        # Idempotent second run
        r_imp2 = run_cli("import-legacy", str(legacy), env=self.env)
        self.assertEqual(r_imp2.returncode, 0, r_imp2.stderr)
        self.assertEqual((legacy / "00-GRAPH.json").read_text(encoding="utf-8"), graph_after_1)
        self.assertEqual((legacy / "scratchpad" / "curriculum.json").read_text(encoding="utf-8"), curr_after_1)

        # Unknown frontmatter field preserved + source_file + timestamps preserved
        g_obj = json.loads(graph_after_1)
        self.assertEqual(g_obj["nodes"]["topic-01"]["extra_metadata"]["custom_legacy_tag"], "keep-me-losslessly")
        self.assertEqual(g_obj["nodes"]["topic-01"]["source_file"], "topics/01-linear.md")
        self.assertEqual(g_obj["nodes"]["topic-01"]["last_event_ts"], "2026-01-01T10:00:00Z")

        # State-only flush on topic 02 must NOT touch legacy study-note files
        r_flush = run_cli("flush", str(legacy), "--topic", "02", "--note", "Step opposite gradient", env=self.env)
        self.assertEqual(r_flush.returncode, 0, r_flush.stderr)
        self.assertEqual(t1.read_text(encoding="utf-8"), topic1_content)
        self.assertEqual(t2.read_text(encoding="utf-8"), topic2_content)
        self.assertEqual(moc.read_text(encoding="utf-8"), moc_content)

        # Reject malformed/unsupported legacy formats explicitly
        bad_dir = self.tmp / "BadLegacy"
        write_file(bad_dir / "topics" / "01-bad.md", "No YAML frontmatter here\n")
        r_bad = run_cli("import-legacy", str(bad_dir), env=self.env)
        self.assertNotEqual(r_bad.returncode, 0)
        self.assertFalse(json.loads(r_bad.stderr)["ok"])

    def test_h_j_k_handoff_context_envelope_evidence_and_no_mastery_advance(self) -> None:
        """H, J, K: Mixed-request handoff envelope contains only relevant evidence-backed data; unknown where unassessed."""
        session = self.tmp / "notes" / "backprop"
        sub_file = self._make_subtopics()
        run_cli("init", str(session), "--topic", "Backprop", "--subtopics", str(sub_file), env=self.env)
        write_file(
            session / "scratchpad" / "mission.json",
            json.dumps({"prior_knowledge": "Basic intuition", "language": "English", "depth_mode": "Core fundamentals"}),
        )
        write_file(
            session / "scratchpad" / "ingested-sources.json",
            json.dumps({"sources": [{"title": "Rumelhart 1986", "url": "https://example.org/bp", "type": "paper"}]}),
        )
        # Complete topic 01; leave topic 02 unassessed; record a retry weak spot
        run_cli("tick", str(session), "--topic", "01", "--cp", "2", "--status", "retry", "--note", "Chain rule order", env=self.env)
        run_cli("tick", str(session), "--topic", "01", "--cp", "4", "--status", "pass", "--note", "Multiply local Jacobians", env=self.env)
        run_cli("flush", str(session), "--topic", "01", "--note", "Multiply local Jacobians", env=self.env)

        r_hand = run_cli(
            "handoff", str(session),
            "--request", "make revision notes on what we covered",
            "--scope", "covered_plus_pending",
            "--request-id", "req-abc-123",
            "--example", "2-layer scalar chain f(g(x)) with x=3",
            env=self.env,
        )
        self.assertEqual(r_hand.returncode, 0, r_hand.stderr)
        env_data = json.loads(r_hand.stdout)

        self.assertEqual(env_data["schema_version"], HANDOFF_SCHEMA_VERSION)
        self.assertEqual(env_data["request_id"], "req-abc-123")
        self.assertEqual(env_data["requested_artifact"], "make revision notes on what we covered")
        self.assertEqual(env_data["destination_constraints"], "unknown")
        self.assertEqual(env_data["learner_profile"]["level"], "Basic intuition")
        self.assertEqual(env_data["examples_analogies_used"], ["2-layer scalar chain f(g(x)) with x=3"])
        self.assertEqual(len(env_data["concepts_taught"]), 1)
        self.assertEqual(env_data["concepts_taught"][0]["id"], "topic-01")
        self.assertEqual(len(env_data["concepts_planned"]), 1)
        self.assertEqual(env_data["concepts_planned"][0]["id"], "topic-02")

        claims_by_id = {c["id"]: c for c in env_data["mastery_claims"]}
        self.assertEqual(claims_by_id["topic-01"]["assessed_status"], "mastered")
        self.assertEqual(claims_by_id["topic-02"]["assessed_status"], "unknown")
        self.assertEqual(claims_by_id["topic-02"]["evidence"], "unassessed")

        # Ephemeral by default: no handoff file written unless --persist
        self.assertFalse((session / "scratchpad" / "handoffs").exists())
        # Note handoff must NEVER advance topic 02 mastery
        st_after = json.loads(run_cli("state", str(session), env=self.env).stdout)
        self.assertEqual(st_after["completed_count"], 1)

    def test_l_removed_note_commands_and_modules_are_not_callable(self) -> None:
        """L: Removed renderers, note commands, and note-writing side effects are no longer callable."""
        removed_cli = ["fix", "verify", "discover", "profile", "plan", "generate", "apply", "audit"]
        for cmd in removed_cli:
            res = run_cli(cmd, env=self.env)
            self.assertNotEqual(res.returncode, 0, f"Removed CLI command '{cmd}' should not succeed")

        removed_modules = [
            "discovery", "plugins", "templates", "placement", "tagging",
            "moc", "mermaid", "renderer", "planner", "writer",
        ]
        for mod in removed_modules:
            with self.assertRaises(ModuleNotFoundError):
                __import__(f"teachme_vault.{mod}")
            self.assertFalse(hasattr(teachme_vault, mod))

        for removed_skill in ("teachme-compare", "teachme-distill", "teachme-expand", "teachme-verify"):
            self.assertFalse((REPO_ROOT / "skills" / removed_skill).exists())

    def test_c_and_g_instruction_invariants_and_routing_contract(self) -> None:
        """C, G, I, J: Verify core teaching invariants, intent routing, and lazy handoff docs are present."""
        skill_md = (REPO_ROOT / "skills" / "teachme" / "SKILL.md").read_text(encoding="utf-8")
        retention_md = (REPO_ROOT / "skills" / "teachme" / "references" / "RETENTION-AND-RECORDS.md").read_text(encoding="utf-8")
        mission_md = (REPO_ROOT / "skills" / "teachme" / "references" / "MISSION-AND-GRILL.md").read_text(encoding="utf-8")
        handoff_md = (REPO_ROOT / "skills" / "teachme" / "references" / "SCRIPTORIUM-HANDOFF.md").read_text(encoding="utf-8")

        # Teaching invariants
        self.assertIn("No prior knowledge", mission_md)
        self.assertIn("ONE-Question-Per-Turn", retention_md)
        self.assertIn("Anti-Spoiler Micro-Hint Rule", retention_md)
        self.assertIn("Interleaved recall", retention_md)
        self.assertIn("Feynman", retention_md)
        self.assertIn("Formula Anatomy Breakdown", retention_md)
        self.assertIn("Status: superseded by LR-000N", retention_md)

        # Intent routing & prohibitions
        self.assertIn("Notes-only request", skill_md)
        self.assertIn("Mixed request", skill_md)
        self.assertIn("/scribe-doubt", skill_md)
        self.assertIn("not even in chat as a fallback", skill_md)
        self.assertIn("NEVER counts as mastery evidence", skill_md)

        # Lazy handoff contract & Scriptorium verified triggers
        self.assertIn("/scribe-notes <topic>", handoff_md)
        self.assertIn("/scribe-expand <topic name>", handoff_md)
        self.assertIn("/scribe-doubt <topic name> <doubt>", handoff_md)
        self.assertIn("SCRIPTORIUM_VAULT_PATH", handoff_md)
        self.assertIn("~/.scriptorium-config.json", handoff_md)
        self.assertIn("Blocked Handoff", handoff_md)


if __name__ == "__main__":
    unittest.main()
