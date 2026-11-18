"""Tests for NTT source-independent teaching refactor: source resolution, multi-vaults, incremental index, and safety."""

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

from teachme_vault.indexer import resolve_sources
from teachme_vault.models import is_within_root


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


def assert_no_study_notes_created(testcase: unittest.TestCase, directory: Path) -> None:
    forbidden_files = (
        "01-RESOURCES.md",
        "02-DEEP-RESEARCH.md",
        "03-CORNELL-STUDY-GUIDE.md",
        "04-GLOSSARY.md",
        "08-FLASHCARDS.md",
        "09-CHEAT-SHEET.md",
        "00-MOC-INDEX.md",
        "raw-research.md",
    )
    for fname in forbidden_files:
        testcase.assertFalse((directory / fname).exists(), f"Unexpected study artifact: {directory / fname}")
        testcase.assertFalse((directory / "scratchpad" / fname).exists(), f"Unexpected scratchpad artifact: {fname}")
    for dname in ("topics", "atomic"):
        testcase.assertFalse((directory / dname).exists(), f"Unexpected study-note folder: {directory / dname}")


class SourceResolutionNTTTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="teachme_ntt_test_"))
        self.cfg_path = self.tmp / "teachme-config.json"
        self.notes_root = self.tmp / "state-notes"
        self.env = {"TEACHME_CONFIG_PATH": str(self.cfg_path)}
        # Configure isolated standalone notes_root so tests never touch user's ~/notes
        write_file(self.cfg_path, json.dumps({"notes_root": str(self.notes_root)}))

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_01_existing_notes_vault_mode_with_sections_embeds_and_prereqs(self) -> None:
        """Existing Obsidian notes (created by any tool) resolve to vault mode with bounded sections and related context."""
        vault = self.tmp / "AnyObsidianVault"
        write_file(vault / ".obsidian" / "app.json", "{}")
        prereq_note = write_file(
            vault / "Math" / "Chain Rule.md",
            "---\ntags: [calculus, prerequisite]\n---\n# Chain Rule\n\n"
            "For composite functions $f(g(x))$, the derivative is $f'(g(x)) \\cdot g'(x)$.\n"
            "Always differentiate the outer function at the inner value, then multiply by the inner derivative.\n",
        )
        embed_note = write_file(
            vault / "ML" / "Loss Functions.md",
            "# Loss Functions\n\n## Mean Squared Error\n\n"
            "MSE measures average squared residuals: $L(\\theta) = \\frac{1}{n}\\sum (y_i - \\hat{y}_i)^2$.\n"
            "Squaring penalizes large errors more strongly and keeps the loss smooth.\n",
        )
        main_note = write_file(
            vault / "ML" / "Gradient Descent.md",
            "---\n"
            "title: Gradient Descent\n"
            "aliases: [GD, Steepest Descent]\n"
            "tags: [optimization, ml/core]\n"
            "depends_on: [\"[[Chain Rule]]\"]\n"
            "---\n"
            "# Gradient Descent\n\n"
            "## Intuition\n\n"
            "Gradient descent is a first-order iterative optimization method that moves parameters "
            "opposite to the local gradient to minimize a differentiable objective function.\n\n"
            "## Update Rule\n\n"
            "Given learning rate $\\eta > 0$ and objective $L(\\theta)$:\n"
            "$$\\theta_{t+1} = \\theta_t - \\eta \\nabla_\\theta L(\\theta_t)$$\n"
            "![[Loss Functions#Mean Squared Error]]\n\n"
            "## Choosing the Learning Rate\n\n"
            "If $\\eta$ is too small, convergence is slow. If $\\eta$ is too large, steps overshoot the valley "
            "and iterates can oscillate or diverge. Convexity and Lipschitz smoothness govern step bounds.\n",
        )
        orig_bytes = {p: p.read_bytes() for p in (prereq_note, embed_note, main_note)}

        r_conn = run_cli("connect", str(vault), "--name", "main-vault", env=self.env)
        self.assertEqual(r_conn.returncode, 0, r_conn.stderr)

        r_res = run_cli("resolve-sources", "--topic", "Gradient Descent", env=self.env)
        self.assertEqual(r_res.returncode, 0, r_res.stderr)
        data = json.loads(r_res.stdout)

        self.assertEqual(data["mode"], "vault")
        self.assertFalse(data["web"]["needed"])
        self.assertIn("ML/Gradient Descent.md", data["relevant_vault_paths"])
        self.assertEqual(data["missing_coverage"], [])

        # Retrieved real sections (not just 280-char summary!)
        headings = [s["heading"] for s in data["matched_sections"]]
        self.assertIn("Update Rule", headings)
        self.assertIn("Choosing the Learning Rate", headings)
        full_content = "\n".join(s["content"] for s in data["matched_sections"])
        self.assertIn("Lipschitz smoothness", full_content)
        self.assertGreater(len(full_content), 280)

        # Related prerequisite & embedded notes resolved
        rel_map = {r["rel_path"]: r for r in data["related_notes"]}
        self.assertIn("Math/Chain Rule.md", rel_map)
        self.assertEqual(rel_map["Math/Chain Rule.md"]["relation"], "prerequisite")
        self.assertIn("ML/Loss Functions.md", rel_map)
        self.assertEqual(rel_map["ML/Loss Functions.md"]["relation"], "embed")
        self.assertIn("MSE measures average squared residuals", rel_map["ML/Loss Functions.md"]["excerpt"])

        # Provenance marks source content untrusted
        prov = {p["rel_path"]: p for p in data["source_provenance"]}
        self.assertEqual(prov["ML/Gradient Descent.md"]["trust"], "untrusted_source_content")

        # Existing vault notes byte-for-byte untouched
        for p, expected in orig_bytes.items():
            self.assertEqual(p.read_bytes(), expected)

    def test_02_no_notes_and_no_vault_selects_web_mode_without_raw_research(self) -> None:
        """Unconfigured vault or empty/no-match vault selects web mode and creates no raw-research.md."""
        r_novault = run_cli("resolve-sources", "--topic", "Fourier Transform", env=self.env)
        self.assertEqual(r_novault.returncode, 0, r_novault.stderr)
        d1 = json.loads(r_novault.stdout)
        self.assertEqual(d1["mode"], "web")
        self.assertFalse(d1["vault"]["configured"])
        self.assertEqual(d1["relevant_vault_paths"], [])
        self.assertEqual(d1["matched_sections"], [])
        self.assertTrue(d1["web"]["needed"])

        # Connected vault with no matching notes -> web mode
        vault = self.tmp / "EmptyMatchVault"
        write_file(vault / ".obsidian" / "app.json", "{}")
        write_file(vault / "Cooking" / "Pasta.md", "# Pasta\n\nBoil salted water and cook al dente.\n")
        run_cli("connect", str(vault), env=self.env)

        r_nomatch = run_cli("resolve-sources", "--topic", "Fourier Transform", env=self.env)
        self.assertEqual(r_nomatch.returncode, 0, r_nomatch.stderr)
        d2 = json.loads(r_nomatch.stdout)
        self.assertEqual(d2["mode"], "web")
        self.assertTrue(d2["vault"]["accessible"])
        self.assertEqual(d2["relevant_vault_paths"], [])

        # Initializing session in web mode must not create raw-research.md or study notes
        sess = self.notes_root / "fourier-transform"
        r_init = run_cli("init", str(sess), "--topic", "Fourier Transform", "--topics", "01-basics", env=self.env)
        self.assertEqual(r_init.returncode, 0, r_init.stderr)
        assert_no_study_notes_created(self, sess)

    def test_03_keyword_overlap_and_stubs_not_confused_with_vault_coverage(self) -> None:
        """Superficial keyword mentions, todo lists, stubs, and partial-word matches do not trigger vault mode."""
        vault = self.tmp / "KeywordTrapVault"
        write_file(vault / ".obsidian" / "app.json", "{}")
        write_file(
            vault / "Daily" / "2026-11-01.md",
            "# 2026-11-01\n\n- [ ] Study backpropagation tomorrow\n- Saw a post about backpropagation.\n",
        )
        write_file(
            vault / "ML" / "Transformers Overview.md",
            "# Transformers Overview\n\n## Training Setup\n\n"
            "Modern transformers use AdamW, cosine learning rate warmup, residual dropout, and mixed precision. "
            "Weights update via backpropagation during training. Large batches stabilize layer norm statistics "
            "and improve throughput across accelerator clusters.\n",
        )
        write_file(
            vault / "ML" / "Gradient Boosting.md",
            "# Gradient Boosting\n\n## Additive Trees\n\n"
            "Gradient boosting builds an ensemble of weak decision trees sequentially where each tree fits "
            "pseudo-residuals of the loss functional over prior predictions.\n",
        )
        run_cli("connect", str(vault), env=self.env)

        # Passing mention + todo task != Backpropagation coverage
        r_bp = run_cli("resolve-sources", "--topic", "Backpropagation", env=self.env)
        self.assertEqual(r_bp.returncode, 0, r_bp.stderr)
        d_bp = json.loads(r_bp.stdout)
        self.assertEqual(d_bp["mode"], "web")
        self.assertEqual(d_bp["relevant_vault_paths"], [])

        # "Gradient Boosting" sharing word "Gradient" != "Gradient Descent"
        r_gd = run_cli("resolve-sources", "--topic", "Gradient Descent", env=self.env)
        self.assertEqual(r_gd.returncode, 0, r_gd.stderr)
        d_gd = json.loads(r_gd.stdout)
        self.assertEqual(d_gd["mode"], "web")
        self.assertEqual(d_gd["relevant_vault_paths"], [])

    def test_04_partially_relevant_notes_selects_hybrid_with_missing_coverage(self) -> None:
        """Partial objective coverage, stub headings, and missing compound facets resolve to hybrid mode."""
        vault = self.tmp / "PartialVault"
        write_file(vault / ".obsidian" / "app.json", "{}")
        write_file(
            vault / "LinearAlgebra" / "Dot Product.md",
            "# Dot Product\n\n## Algebraic & Geometric Definition\n\n"
            "The dot product of vectors $a, b \\in \\mathbb{R}^n$ is $a \\cdot b = \\sum_i a_i b_i = \\|a\\|\\|b\\|\\cos\\theta$. "
            "It measures signed alignment and equals zero iff nonzero vectors are orthogonal.\n\n"
            "## Failure Modes\n\nTODO\n",
        )
        write_file(
            vault / "Algorithms" / "BFS.md",
            "# Breadth-First Search (BFS)\n\n## Algorithm & Queue Invariant\n\n"
            "BFS explores a graph layer by layer using a FIFO queue, guaranteeing shortest path length in "
            "unweighted graphs in $O(V + E)$ time and $O(V)$ space.\n",
        )
        run_cli("connect", str(vault), env=self.env)

        # Explicit objectives: 1 covered, 1 missing -> hybrid
        r_obj = run_cli(
            "resolve-sources",
            "--topic", "Dot Product",
            "--objective", "Compute algebraic and geometric dot product",
            "--objective", "Prove the Cauchy-Schwarz inequality using quadratic discriminants",
            env=self.env,
        )
        self.assertEqual(r_obj.returncode, 0, r_obj.stderr)
        d_obj = json.loads(r_obj.stdout)
        self.assertEqual(d_obj["mode"], "hybrid")
        self.assertIn("LinearAlgebra/Dot Product.md", d_obj["relevant_vault_paths"])
        missing_targets = [m["target"] for m in d_obj["missing_coverage"]]
        self.assertTrue(any("Cauchy-Schwarz" in t for t in missing_targets))
        self.assertTrue(d_obj["web"]["needed"])

        # Stub section detection without explicit objectives -> hybrid
        r_stub = run_cli("resolve-sources", "--topic", "Dot Product", env=self.env)
        d_stub = json.loads(r_stub.stdout)
        self.assertEqual(d_stub["mode"], "hybrid")
        self.assertTrue(any("Failure Modes" in m["target"] for m in d_stub["missing_coverage"]))

        # Compound query "BFS vs DFS" with only BFS note -> hybrid
        r_cmp = run_cli("resolve-sources", "--topic", "BFS vs DFS", env=self.env)
        d_cmp = json.loads(r_cmp.stdout)
        self.assertEqual(d_cmp["mode"], "hybrid")
        self.assertTrue(any("DFS" in m["target"] for m in d_cmp["missing_coverage"]))

    def test_05_multiple_vaults_registration_switching_and_isolation(self) -> None:
        """Multiple registered vaults support explicit active switching and never scan unconfigured directories."""
        ml_vault = self.tmp / "MLVault"
        sys_vault = self.tmp / "SystemsVault"
        unconfigured = self.tmp / "UnconfiguredSecretVault"

        write_file(ml_vault / ".obsidian" / "app.json", "{}")
        write_file(
            ml_vault / "Attention.md",
            "# Scaled Dot-Product Attention\n\n## Mechanism\n\n"
            "Attention computes $\\text{softmax}(QK^T / \\sqrt{d_k})V$ to weight value vectors by query-key similarity. "
            "Scaling by $\\sqrt{d_k}$ prevents softmax saturation in high dimensions.\n",
        )
        write_file(sys_vault / ".obsidian" / "app.json", "{}")
        write_file(
            sys_vault / "Virtual Memory.md",
            "# Virtual Memory & Page Tables\n\n## Address Translation\n\n"
            "The MMU translates virtual addresses to physical frames using multi-level page tables and a TLB cache. "
            "Each process gets an isolated virtual address space mapped onto physical RAM frames.\n\n"
            "## Page Faults and Protection\n\n"
            "When a page is absent or permissions fail, a page fault traps to the kernel to load the page from backing "
            "storage or terminate an invalid access.\n",
        )
        write_file(
            unconfigured / "Quantum Cryptography.md",
            "# Quantum Cryptography\n\nBB84 quantum key distribution uses non-orthogonal photon polarizations.\n",
        )

        r1 = run_cli("connect", str(ml_vault), "--name", "ml", env=self.env)
        self.assertEqual(r1.returncode, 0, r1.stderr)
        r2 = run_cli("connect", str(sys_vault), "--name", "sys", "--no-activate", env=self.env)
        self.assertEqual(r2.returncode, 0, r2.stderr)
        self.assertFalse(json.loads(r2.stdout)["active"])

        # List registered vaults: ml active, sys inactive, unconfigured absent
        r_list = run_cli("vaults", env=self.env)
        self.assertEqual(r_list.returncode, 0, r_list.stderr)
        vdata = json.loads(r_list.stdout)
        self.assertEqual(vdata["active_vault"], "ml")
        by_name = {v["name"]: v for v in vdata["vaults"]}
        self.assertEqual(set(by_name.keys()), {"ml", "sys"})
        self.assertTrue(by_name["ml"]["active"])
        self.assertFalse(by_name["sys"]["active"])

        # Never scan unconfigured directory
        r_unconf = run_cli("resolve-sources", "--topic", "Quantum Cryptography", env=self.env)
        self.assertEqual(json.loads(r_unconf.stdout)["mode"], "web")

        # Active is ml: Virtual Memory not in ml -> web, unless explicitly targeting --vault sys
        self.assertEqual(json.loads(run_cli("resolve-sources", "--topic", "Virtual Memory", env=self.env).stdout)["mode"], "web")
        r_explicit = run_cli("resolve-sources", "--vault", "sys", "--topic", "Virtual Memory", env=self.env)
        self.assertEqual(json.loads(r_explicit.stdout)["mode"], "vault")

        # Switch active vault to sys
        r_use = run_cli("use-vault", "sys", env=self.env)
        self.assertEqual(r_use.returncode, 0, r_use.stderr)
        self.assertEqual(json.loads(r_use.stdout)["active_vault"], "sys")
        self.assertEqual(json.loads(run_cli("resolve-sources", "--topic", "Virtual Memory", env=self.env).stdout)["mode"], "vault")

        # Unregister sys without deleting any files on disk
        r_rm = run_cli("remove-vault", "sys", env=self.env)
        self.assertEqual(r_rm.returncode, 0, r_rm.stderr)
        self.assertTrue((sys_vault / "Virtual Memory.md").is_file())
        self.assertEqual(json.loads(run_cli("resolve-sources", "--topic", "Virtual Memory", env=self.env).stdout)["mode"], "web")

    def test_06_external_vault_modifications_incremental_index_update(self) -> None:
        """Vault additions/edits by another skill are picked up incrementally without rebuilding unchanged notes."""
        vault = self.tmp / "SharedVault"
        write_file(vault / ".obsidian" / "app.json", "{}")
        write_file(
            vault / "Core" / "Vectors.md",
            "# Vectors\n\n## Operations\n\nVector addition and scalar multiplication form a linear space over $\\mathbb{R}$.\n",
        )
        eig_path = write_file(
            vault / "Core" / "Eigenvalues.md",
            "# Eigenvalues\n\n## Definition\n\nTODO\n",
        )
        run_cli("connect", str(vault), env=self.env)

        # Initial resolve: stub only -> web
        r1 = run_cli("resolve-sources", "--topic", "Eigenvalues", env=self.env)
        d1 = json.loads(r1.stdout)
        self.assertEqual(d1["mode"], "web")
        self.assertTrue(d1["vault"]["index_stats"].get("cache_hit"))

        # Simulate another skill editing Eigenvalues.md and adding Spectral Theorem.md
        write_file(
            eig_path,
            "# Eigenvalues\n\n## Characteristic Equation\n\n"
            "A scalar $\\lambda$ is an eigenvalue of $A$ iff $Av = \\lambda v$ for some $v \\neq 0$, "
            "equivalently $\\det(A - \\lambda I) = 0$.\n\n"
            "## Geometric Meaning\n\n"
            "Eigenvectors span invariant directions scaled by $\\lambda$ without rotation.\n",
        )
        write_file(
            vault / "Core" / "Spectral Theorem.md",
            "# Spectral Theorem\n\nSymmetric real matrices admit an orthonormal eigenbasis.\n",
        )

        r2 = run_cli("resolve-sources", "--topic", "Eigenvalues", env=self.env)
        d2 = json.loads(r2.stdout)
        self.assertEqual(d2["mode"], "vault")
        self.assertIn("Core/Eigenvalues.md", d2["relevant_vault_paths"])
        stats2 = d2["vault"]["index_stats"]
        self.assertFalse(stats2.get("cache_hit"))
        self.assertGreaterEqual(stats2.get("reused", 0), 1)
        self.assertEqual(stats2.get("added", 0), 1)
        self.assertEqual(stats2.get("updated", 0), 1)

        # Third call with no modifications hits cache
        r3 = run_cli("resolve-sources", "--topic", "Eigenvalues", env=self.env)
        d3 = json.loads(r3.stdout)
        self.assertTrue(d3["vault"]["index_stats"].get("cache_hit"))

    def test_07_inaccessible_vault_and_traversal_guards(self) -> None:
        """Missing/inaccessible configured vault falls back cleanly to web mode; path traversal stays blocked."""
        vault = self.tmp / "TempVault"
        write_file(vault / ".obsidian" / "app.json", "{}")
        write_file(vault / "Topic.md", "# Topic\n\n## Core\n\nDetailed explanation of topic mechanics and proofs.\n")
        run_cli("connect", str(vault), env=self.env)

        # Delete vault from disk to simulate unmounted drive / inaccessible folder
        shutil.rmtree(vault)

        r_res = run_cli("resolve-sources", "--topic", "Topic", env=self.env)
        self.assertEqual(r_res.returncode, 0, r_res.stderr)
        data = json.loads(r_res.stdout)
        self.assertEqual(data["mode"], "web")
        self.assertTrue(data["vault"]["configured"])
        self.assertFalse(data["vault"]["accessible"])
        self.assertTrue(any("inaccessible" in n.lower() or "does not exist" in n.lower() for n in data["notices"]))

        r_st = run_cli("state", env=self.env)
        self.assertEqual(r_st.returncode, 0, r_st.stderr)
        self.assertFalse(json.loads(r_st.stdout)["vault_accessible"])

        # Path traversal check
        outside = self.tmp / "outside.md"
        write_file(outside, "# Secret")
        vault2 = self.tmp / "SafeVault"
        vault2.mkdir(parents=True, exist_ok=True)
        self.assertFalse(is_within_root(outside, vault2))

    def test_08_unavailable_web_tools_explicit_limitations(self) -> None:
        """When web tools are unavailable (--no-web), resolve-sources surfaces explicit honest limitation notices."""
        r_res = run_cli("resolve-sources", "--topic", "Quantum Error Correction", "--no-web", env=self.env)
        self.assertEqual(r_res.returncode, 0, r_res.stderr)
        data = json.loads(r_res.stdout)
        self.assertEqual(data["mode"], "web")
        self.assertFalse(data["web"]["available"])
        self.assertTrue(
            any("unavailable" in n.lower() and "never fabricate" in n.lower() for n in data["notices"])
        )

    def test_09_session_resume_across_source_modes_preserves_evidence(self) -> None:
        """Resuming a session across web -> hybrid -> inaccessible vault preserves all prior evidence and writes no study notes."""
        sub_file = self.tmp / "bayes-subtopics.json"
        write_file(
            sub_file,
            json.dumps(
                [
                    {
                        "slug": "01-bayes-rule",
                        "title": "Bayes Rule",
                        "objectives": [
                            {"id": "obj-01-prior", "description": "Update prior probability using likelihood and evidence", "required": True},
                            {"id": "obj-01-base-rate", "description": "Avoid base rate fallacy in medical screening", "required": True},
                        ],
                    }
                ]
            ),
        )
        sess_dir = self.notes_root / "bayes-rule"
        self.assertEqual(run_cli("init", str(sess_dir), "--topic", "Bayes Rule", "--subtopics", str(sub_file), env=self.env).returncode, 0)
        self.assertEqual(
            run_cli(
                "assess", str(sess_dir), "--topic", "01", "--objective", "obj-01-prior",
                "--assessment-type", "independent_application", "--result", "pass", "--assistance", "none",
                "--rationale", "Computed posterior correctly", "--now", "2026-11-10T10:00:00Z", env=self.env,
            ).returncode,
            0,
        )
        self.assertEqual(
            run_cli(
                "assess", str(sess_dir), "--topic", "01", "--objective", "obj-01-base-rate",
                "--assessment-type", "violated_assumption", "--result", "fail", "--assistance", "none",
                "--rationale", "Ignored low disease prevalence", "--now", "2026-11-10T10:05:00Z", env=self.env,
            ).returncode,
            0,
        )
        assert_no_study_notes_created(self, sess_dir)

        # Later connect a vault that covers prior/likelihood update but NOT base-rate fallacy
        vault = self.tmp / "BayesVault"
        write_file(vault / ".obsidian" / "app.json", "{}")
        bayes_note = write_file(
            vault / "Stats" / "Bayes Rule.md",
            "# Bayes Rule\n\n## Posterior Update\n\n"
            "Bayes' theorem updates a prior probability $P(H)$ using likelihood $P(E|H)$ and marginal evidence $P(E)$:\n"
            "$$P(H|E) = \\frac{P(E|H)P(H)}{P(E)}$$\n",
        )
        orig_note_bytes = bayes_note.read_bytes()
        run_cli("connect", str(vault), env=self.env)

        # Resolve sources using the existing session's curriculum objectives -> hybrid!
        r_res = run_cli("resolve-sources", "--topic", "Bayes Rule", "--session", "bayes-rule", env=self.env)
        self.assertEqual(r_res.returncode, 0, r_res.stderr)
        res_data = json.loads(r_res.stdout)
        self.assertEqual(res_data["mode"], "hybrid")
        missing_ids = [m["objective_id"] for m in res_data["missing_coverage"]]
        self.assertIn("obj-01-base-rate", missing_ids)
        self.assertNotIn("obj-01-prior", missing_ids)

        # Resuming standalone session via --session still preserves all evidence
        r_cov = run_cli("coverage", "--session", "bayes-rule", env=self.env)
        self.assertEqual(r_cov.returncode, 0, r_cov.stderr)
        cov = json.loads(r_cov.stdout)
        objs = {o["objective_id"]: o for o in cov["objectives"]}
        self.assertEqual(objs["obj-01-prior"]["proficiency_status"], "demonstrated_independently")
        self.assertEqual(objs["obj-01-base-rate"]["coverage_status"], "unresolved")
        self.assertEqual(cov["independent_successes"], 1)

        # Vault note untouched and no study notes created
        self.assertEqual(bayes_note.read_bytes(), orig_note_bytes)
        assert_no_study_notes_created(self, vault)
        assert_no_study_notes_created(self, sess_dir)

    def test_10_bounded_retrieval_budget_respected(self) -> None:
        """Retrieved sections respect max_chars, max_notes, and max_sections bounds."""
        vault = self.tmp / "LargeVault"
        write_file(vault / ".obsidian" / "app.json", "{}")
        long_para = " ".join(["Optimization converges smoothly under convex assumptions."] * 60)
        write_file(
            vault / "Convex Optimization.md",
            f"# Convex Optimization\n\n## Section One\n\n{long_para}\n\n## Section Two\n\n{long_para}\n\n## Section Three\n\n{long_para}\n",
        )
        run_cli("connect", str(vault), env=self.env)

        r_res = run_cli(
            "resolve-sources", "--topic", "Convex Optimization",
            "--max-notes", "1", "--max-sections", "2", "--max-chars", "1500",
            env=self.env,
        )
        self.assertEqual(r_res.returncode, 0, r_res.stderr)
        data = json.loads(r_res.stdout)
        self.assertEqual(data["mode"], "vault")
        self.assertLessEqual(len(data["matched_sections"]), 2)
        total_chars = sum(len(s["content"]) for s in data["matched_sections"])
        self.assertLessEqual(total_chars, 1500)
        self.assertTrue(any(s["truncated"] for s in data["matched_sections"]))


if __name__ == "__main__":
    unittest.main()
