"""End-to-end integration tests across /teachme -> /teachme-code -> /teachme-rapid -> /teachme-review."""

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
from teachme_vault.state_store import load_events, resolve_session_dir  # noqa: E402


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


class CodeRapidEcosystemIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="teachme_eco_int_"))
        self.cfg_path = self.tmp / "teachme-config.json"
        self.env = {"TEACHME_CONFIG_PATH": str(self.cfg_path)}

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_01_skill_discovery_and_router_invariants(self) -> None:
        code_skill = (REPO_ROOT / "skills" / "teachme-code" / "SKILL.md").read_text(encoding="utf-8")
        rapid_skill = (REPO_ROOT / "skills" / "teachme-rapid" / "SKILL.md").read_text(encoding="utf-8")
        master_skill = (REPO_ROOT / "skills" / "teachme" / "SKILL.md").read_text(encoding="utf-8")

        self.assertIn("name: teachme-code", code_skill)
        self.assertIn("name: teachme-rapid", rapid_skill)
        self.assertIn("cmd-code.md", code_skill)
        self.assertIn("cmd-rapid.md", rapid_skill)
        self.assertIn("/teachme code <topic>", master_skill)
        self.assertIn("/teachme rapid <topic>", master_skill)
        self.assertTrue((REPO_ROOT / "skills" / "teachme" / "references" / "cmd-code.md").is_file())
        self.assertTrue((REPO_ROOT / "skills" / "teachme" / "references" / "cmd-rapid.md").is_file())

    def test_02_full_lifecycle_teachme_to_code_to_rapid_to_review(self) -> None:
        vault = self.tmp / "ObsidianVault"
        (vault / ".obsidian").mkdir(parents=True, exist_ok=True)
        note_content = (
            "# C Pointers\n\n"
            "## Dereferencing Basics\n"
            "In C, the address-of operator `&x` returns the memory address of variable `x`. "
            "A pointer variable `int *p = &x;` stores that address, and dereferencing `*p` reads or modifies `x` directly in memory.\n\n"
            "## Pointer Arithmetic\n"
            "Adding an integer offset `k` to a typed pointer `int *p` advances the address by `k * sizeof(int)` bytes rather than `k` raw bytes. "
            "For an array `a`, `*(a + i)` accesses element `a[i]` safely within array bounds.\n"
        )
        note_file = write_file(vault / "C" / "Pointers.md", note_content)

        # Register vault cleanly via CLI
        r_conn = run_cli("connect", str(vault), "--name", "cs", env=self.env)
        self.assertEqual(r_conn.returncode, 0, r_conn.stderr)

        # 1. /teachme C pointers: init + fail on pointer arithmetic (obj-02-01)
        sub_file = self.tmp / "subtopics.json"
        write_file(
            sub_file,
            json.dumps(
                [
                    {
                        "slug": "01-deref",
                        "title": "Dereferencing Basics",
                        "objective": "Use & and * operators safely in C.",
                    },
                    {
                        "slug": "02-pointer-arithmetic",
                        "title": "Pointer Arithmetic",
                        "objective": "Compute pointer arithmetic offsets by sizeof(type).",
                    },
                ]
            ),
        )
        r_init = run_cli(
            "init", str(vault), "--session", "c-pointers", "--topic", "C Pointers",
            "--subtopics", str(sub_file), env=self.env,
        )
        self.assertEqual(r_init.returncode, 0, r_init.stderr)

        # Pass 01 independently; struggle on 02
        run_cli(
            "assess", str(vault), "--session", "c-pointers",
            "--topic", "01", "--objective", "obj-01-01",
            "--assessment-type", "predict_output", "--result", "pass", "--assistance", "none",
            "--now", "2026-11-18T09:00:00Z", env=self.env,
        )
        run_cli(
            "assess", str(vault), "--session", "c-pointers",
            "--topic", "02", "--objective", "obj-02-01",
            "--assessment-type", "prediction", "--result", "fail", "--assistance", "none",
            "--rationale", "Confused pointer arithmetic stride with byte addition",
            "--now", "2026-11-18T09:05:00Z", env=self.env,
        )

        # 2. /teachme-code C pointers: surfaces obj-02-01 weakness, tests code with assistance then independently
        r_cplan = run_cli(
            "code-plan", str(vault), "--session", "c-pointers",
            "--args", "C pointers --mode practice", env=self.env,
        )
        self.assertEqual(r_cplan.returncode, 0, r_cplan.stderr)
        cplan = json.loads(r_cplan.stdout)
        self.assertTrue(any(w["objective_id"] == "obj-02-01" for w in cplan["prioritize_weak_spots"]))

        # Assisted code pass on obj-02-01 (hint_level=1) -> must NOT mark independent mastery
        r_cc_assist = run_cli(
            "code-check", str(vault), "--session", "c-pointers",
            "--language", "python",
            "--code", "arr = [10, 20, 30]\nprint(arr[1])\n",
            "--tests-json", json.dumps([{"stdin": "", "expected_stdout": "20", "kind": "edge"}]),
            "--authorize-exec", "--hint-level", "1",
            "--topic", "02", "--objective", "obj-02-01", "--assess",
            "--now", "2026-11-18T10:00:00Z", env=self.env,
        )
        self.assertEqual(r_cc_assist.returncode, 0, r_cc_assist.stderr)
        ctx_mid = json.loads(run_cli("context", str(vault), "--session", "c-pointers", "--topic", "02", env=self.env).stdout)
        self.assertEqual(ctx_mid["curriculum"]["objectives"][0]["proficiency_status"], "practiced_with_support")

        # Independent code pass on obj-02-01
        r_cc_indep = run_cli(
            "code-check", str(vault), "--session", "c-pointers",
            "--language", "python",
            "--code", "arr = [10, 20, 30]\nprint(arr[2])\n",
            "--tests-json", json.dumps([{"stdin": "", "expected_stdout": "30", "kind": "edge"}]),
            "--authorize-exec", "--hint-level", "0",
            "--topic", "02", "--objective", "obj-02-01", "--assess",
            "--now", "2026-11-18T10:15:00Z", env=self.env,
        )
        self.assertEqual(r_cc_indep.returncode, 0, r_cc_indep.stderr)

        # 3. /teachme-rapid C pointers --mode weak: prioritizes Pointer Arithmetic note section, records shared recall
        r_rplan = run_cli(
            "rapid-plan", str(vault), "--session", "c-pointers",
            "--args", "C pointers --mode weak --questions 4", env=self.env,
        )
        self.assertEqual(r_rplan.returncode, 0, r_rplan.stderr)
        rplan = json.loads(r_rplan.stdout)
        self.assertTrue(rplan["ready"])
        self.assertTrue(rplan["notes_grounded"])
        # Note section for Pointer Arithmetic maps to obj-02-01
        arith_item = next(it for it in rplan["planned_items"] if it["source_heading"] == "Pointer Arithmetic")
        self.assertEqual(arith_item["objective_id"], "obj-02-01")

        sess_dir = Path(rplan["session_dir"])
        r_rrec = run_cli(
            "rapid-record", str(sess_dir),
            "--item-key", arith_item["item_key"],
            "--concept", "Pointer Arithmetic",
            "--result", "pass", "--assistance", "none",
            "--topic", "02", "--objective", "obj-02-01",
            "--now", "2026-11-18T11:00:00Z", env=self.env,
        )
        self.assertEqual(r_rrec.returncode, 0, r_rrec.stderr)
        rrec = json.loads(r_rrec.stdout)
        self.assertTrue(rrec["shared_assessment_recorded"])
        self.assertFalse(rrec["delayed_retention_recorded"])

        # 4. /teachme-review C pointers (>24h later): due items & delayed_recall verification
        r_due = run_cli("due", str(vault), "--session", "c-pointers", "--now", "2026-11-20T12:00:00Z", env=self.env)
        self.assertEqual(r_due.returncode, 0, r_due.stderr)
        due_out = json.loads(r_due.stdout)
        due_oids = {d["objective_id"] for d in due_out["due_items"]}
        self.assertIn("obj-01-01", due_oids)
        self.assertIn("obj-02-01", due_oids)

        r_rev = run_cli(
            "assess", str(vault), "--session", "c-pointers",
            "--topic", "02", "--objective", "obj-02-01",
            "--assessment-type", "delayed_recall", "--result", "pass", "--assistance", "none",
            "--session-run", "review-run-2",
            "--now", "2026-11-20T12:00:00Z", env=self.env,
        )
        self.assertEqual(r_rev.returncode, 0, r_rev.stderr)

        ctx_end = json.loads(run_cli("context", str(vault), "--session", "c-pointers", "--topic", "02", env=self.env).stdout)
        obj2 = ctx_end["curriculum"]["objectives"][0]
        self.assertEqual(obj2["proficiency_status"], "demonstrated_independently")
        self.assertEqual(obj2["retention_status"], "retained")

        # Validate state integrity & verify vault study note is untouched
        r_val = run_cli("validate-state", str(vault), "--session", "c-pointers", env=self.env)
        self.assertEqual(r_val.returncode, 0, r_val.stdout)
        self.assertTrue(json.loads(r_val.stdout)["ok"])
        self.assertEqual(note_file.read_text(encoding="utf-8"), note_content)


if __name__ == "__main__":
    unittest.main()
