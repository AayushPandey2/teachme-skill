"""Comprehensive fixture-based tests for automatic context-aware Obsidian integration."""

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

from teachme_vault.discovery import discover_vault, load_or_discover_profile
from teachme_vault.indexer import build_or_update_index, links_equivalent, load_or_build_index, resolve_safe_wikilink
from teachme_vault.mermaid import plan_mermaid_diagram, validate_mermaid_syntax
from teachme_vault.models import read_text_safe
from teachme_vault.planner import plan_note
from teachme_vault.tagging import select_and_plan_tags
from teachme_vault.writer import audit_vault_native, generate_vault_note


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


class ObsidianIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="teachme_obs_test_"))

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_tags_nested_inline_yaml_mixed_and_workflow_isolation(self) -> None:
        vault = self.tmp / "TagVault"
        write_file(vault / ".obsidian" / "app.json", "{}")
        # Folder uses inline snake_case nested tags, plus an irrelevant popular tag `meeting_notes`
        for idx, name in enumerate(["Linear Algebra", "Eigenvalues", "Matrix Rank"]):
            write_file(
                vault / "Math" / f"{name}.md",
                f"# {name}\n\n#math/linear_algebra #meeting_notes #evergreen\n\nVector spaces and linear transformations ({idx}).\n",
            )
        write_file(
            vault / "Math" / "Calculus.md",
            "---\ntags:\n  - math/calculus\nstatus: mastered\n---\n\n# Calculus\n\nDerivatives and integrals.\n",
        )

        profile = discover_vault(vault)
        tax = profile["tag_taxonomy"]
        self.assertTrue(tax["uses_nested_tags"])
        self.assertEqual(tax["placement"], "both")
        self.assertIn("evergreen", [w["tag"] for w in tax["workflow_tags"]])
        self.assertNotIn("evergreen", tax["all_subject_tags"])

        # Popular irrelevant folder tag `meeting_notes` must be REJECTED for Singular Value Decomposition
        tag_plan = select_and_plan_tags(
            topic="Singular Value Decomposition",
            profile=profile,
            target_folder="Math",
            related_results=[
                {"title": "Eigenvalues", "summary": "Vector spaces", "headings": [], "tags": ["math/linear_algebra", "meeting_notes"]},
            ],
            content={"intuition": "Matrix factorization decomposing linear maps into orthogonal rotations and scaling."},
            proposed_tags=[
                {"tag": "Linear Algebras", "reason": "Near duplicate test"},
                {"tag": "Matrix Factorization", "reason": "Justified new subconcept"},
                {"tag": "mastered", "reason": "Should never infer workflow tag"},
                {"tag": "one off very specific 2025 note tag here", "reason": "Should reject overly specific one-off"},
            ],
        )
        sel = tag_plan["selected_tags"]
        self.assertIn("math/linear_algebra", sel)
        self.assertIn("math/matrix_factorization", sel)
        self.assertNotIn("meeting_notes", sel)
        self.assertNotIn("mastered", sel)
        self.assertNotIn("evergreen", sel)
        self.assertEqual(tag_plan["placement"], "inline")

        decisions_by_tag = {d["tag"]: d for d in tag_plan["decisions"]}
        self.assertEqual(decisions_by_tag["meeting_notes"]["decision"], "reject")
        self.assertEqual(decisions_by_tag["mastered"]["decision"], "reject")
        self.assertEqual(decisions_by_tag["math/matrix_factorization"]["decision"], "create")

    def test_tag_free_vault_permits_zero_tags(self) -> None:
        vault = self.tmp / "TagFreeVault"
        write_file(vault / ".obsidian" / "app.json", "{}")
        write_file(vault / "Notes" / "Alpha.md", "# Alpha\n\nPure prose note without tags.\n")
        write_file(vault / "Notes" / "Beta.md", "# Beta\n\nAnother pure prose note.\n")

        plan = plan_note(vault, topic="Gamma")
        self.assertEqual(plan["tags"], [])
        self.assertTrue(any(d["decision"] == "skip" for d in plan["tag_decisions"]["decisions"]))

    def test_multi_signal_moc_detection_avoids_false_positives(self) -> None:
        vault = self.tmp / "MocSignalVault"
        write_file(vault / ".obsidian" / "app.json", "{}")
        # Prose note with "Indexing" in title and 9 inline links — NOT a MOC!
        prose_links = " ".join(f"[[Concept {i}]]" for i in range(9))
        write_file(
            vault / "DB" / "Database Indexing.md",
            f"# Database Indexing\n\nB-trees speed up lookups using {prose_links} across disk pages.\n\nMore explanation of page splits and write amplification in storage engines.\n",
        )
        # Real MOC with structured bullet list + hub title
        write_file(
            vault / "DB" / "Databases MOC.md",
            "# Databases MOC\n\n## Storage\n- [[Database Indexing]] — B-tree structures\n- [[Write Ahead Log]] — Durability\n- [[Buffer Pool]] — Page cache\n",
        )
        for name in ["Write Ahead Log", "Buffer Pool"] + [f"Concept {i}" for i in range(9)]:
            write_file(vault / "DB" / f"{name}.md", f"# {name}\n\nDetails.\n")

        profile = discover_vault(vault)
        moc_paths = {m["path"] for m in profile["mocs"]}
        self.assertIn("DB/Databases MOC.md", moc_paths)
        self.assertNotIn("DB/Database Indexing.md", moc_paths)

    def test_existing_moc_minimal_update_and_alias_dedup(self) -> None:
        vault = self.tmp / "ExistingMocVault"
        write_file(vault / ".obsidian" / "app.json", "{}")
        orig_moc = (
            "---\n"
            "title: Systems MOC\n"
            "tags:\n  - moc\n"
            "---\n\n"
            "<!-- Keep this comment intact -->\n"
            "# Systems MOC\n\n"
            "## Concurrency\n"
            "- [[Mutex|Mutual Exclusion]] — Lock primitive\n"
            "- [[Semaphore]] — Counting signal\n\n"
            "## Storage\n"
            "- [[Write Ahead Log]] — Crash recovery\n"
        )
        write_file(vault / "Systems" / "Systems MOC.md", orig_moc)
        write_file(vault / "Systems" / "Mutex.md", "---\ntags: [systems/concurrency]\n---\n# Mutex\nLocking.\n")
        write_file(vault / "Systems" / "Semaphore.md", "---\ntags: [systems/concurrency]\n---\n# Semaphore\nSignaling.\n")
        write_file(vault / "Systems" / "Write Ahead Log.md", "---\ntags: [systems/storage]\n---\n# Write Ahead Log\nDurability.\n")

        # 1. Alias-equivalent existing note: Mutex already linked as [[Mutex|Mutual Exclusion]]
        plan_existing = plan_note(
            vault,
            topic="Mutex",
            extend_rel_path="Systems/Mutex.md",
            keywords=["concurrency", "lock"],
        )
        self.assertEqual(plan_existing["moc_decisions"]["action"], "already_linked")

        # 2. New note in Concurrency should update ONLY the Concurrency section minimally
        res = generate_vault_note(
            vault,
            topic="Condition Variable",
            explicit_folder="Systems",
            keywords=["concurrency", "mutex", "semaphore"],
            content={"intuition": "Wait queue paired with a mutex for predicate synchronization."},
            apply=True,
        )
        self.assertTrue(res["ok"])
        self.assertEqual(res["plan"]["moc_decisions"]["action"], "update_existing")
        self.assertEqual(res["plan"]["moc_decisions"]["target_section"], "Concurrency")
        moc_after = read_text_safe(vault / "Systems" / "Systems MOC.md")
        self.assertIn("<!-- Keep this comment intact -->", moc_after)
        self.assertIn("- [[Condition Variable]]", moc_after)
        # Ensure Storage section remained untouched at the bottom
        self.assertTrue(moc_after.index("Condition Variable") < moc_after.index("## Storage"))

        # 3. Repeated MOC update / alias link equivalence must not duplicate link
        plan_repeat = plan_note(
            vault,
            topic="Condition Variable",
            extend_rel_path="Systems/Condition Variable.md",
            keywords=["concurrency"],
        )
        self.assertEqual(plan_repeat["moc_decisions"]["action"], "already_linked")

    def test_justified_new_moc_creation_and_suppression(self) -> None:
        vault = self.tmp / "ClusterMocVault"
        write_file(vault / ".obsidian" / "app.json", "{}")
        # Create 2 notes in Graphs/ (with new note => 3 coherent notes!)
        write_file(vault / "Graphs" / "Breadth First Search.md", "---\ntags: [algorithms/graphs]\n---\n# Breadth First Search\nShortest path unweighted graphs.\n")
        write_file(vault / "Graphs" / "Depth First Search.md", "---\ntags: [algorithms/graphs]\n---\n# Depth First Search\nGraph traversal with stack.\n")
        # Isolated single note in Misc/
        write_file(vault / "Misc" / "Cooking Recipe.md", "# Cooking Recipe\nPasta sauce.\n")

        # Small cluster (< 3) in Misc must SUPPRESS MOC creation
        suppressed = plan_note(vault, topic="Baking Bread", explicit_folder="Misc", min_moc_cluster_size=3)
        self.assertEqual(suppressed["moc_decisions"]["action"], "none")
        self.assertIsNone(suppressed["moc_decisions"]["new_moc_path"])

        # Coherent cluster (>= 3) in Graphs must CREATE a justified MOC
        res = generate_vault_note(
            vault,
            topic="Dijkstra Shortest Path",
            explicit_folder="Graphs",
            keywords=["graphs", "breadth first search", "depth first search"],
            min_moc_cluster_size=3,
            apply=True,
        )
        self.assertTrue(res["ok"])
        self.assertEqual(res["plan"]["moc_decisions"]["action"], "create_new")
        new_moc = res["plan"]["moc_decisions"]["new_moc_path"]
        self.assertIsNotNone(new_moc)
        moc_text = read_text_safe(vault / new_moc)
        self.assertIn("[[Dijkstra Shortest Path]]", moc_text)
        self.assertIn("[[Breadth First Search]]", moc_text)

    def test_query_driven_moc_avoids_manual_list_duplication(self) -> None:
        vault = self.tmp / "QueryMocVault"
        write_file(vault / ".obsidian" / "app.json", "{}")
        write_file(vault / ".obsidian" / "community-plugins.json", json.dumps(["dataview"]))
        dql_moc = (
            "# Physics Index\n\n"
            "```dataview\n"
            "TABLE status, topic_area FROM \"Physics\"\n"
            "WHERE status != \"archived\"\n"
            "```\n"
        )
        write_file(vault / "Physics" / "Physics Index.md", dql_moc)
        write_file(
            vault / "Physics" / "Kinematics.md",
            "---\ntags: [physics]\nstatus: seedling\ntopic_area: mechanics\n---\n# Kinematics\nMotion equations.\n",
        )

        res = generate_vault_note(
            vault,
            topic="Newtonian Dynamics",
            explicit_folder="Physics",
            keywords=["physics", "kinematics", "motion"],
            apply=True,
        )
        self.assertTrue(res["ok"])
        self.assertEqual(res["plan"]["moc_decisions"]["action"], "satisfy_query")
        # Query-driven MOC file must NOT be cluttered with manual bullet links
        self.assertEqual(read_text_safe(vault / "Physics" / "Physics Index.md"), dql_moc)
        gen_text = read_text_safe(vault / res["target_rel_path"])
        self.assertIn("status: seedling", gen_text)

    def test_duplicate_basenames_aliases_headings_blocks_and_unicode(self) -> None:
        vault = self.tmp / "LinkResVault"
        write_file(vault / ".obsidian" / "app.json", "{}")
        write_file(vault / "Math" / "Entropy.md", "---\ntitle: Entropy (Math)\naliases:\n  - Shannon Entropy\n---\n# Entropy\n## Definition\nInformation measure ^ent-def\n")
        write_file(vault / "Physics" / "Entropy.md", "---\ntitle: Entropy (Thermo)\n---\n# Entropy\nThermodynamic disorder.\n")
        write_file(vault / "Équations" / "Café_Θέτα.md", "---\ntitle: Café Θέτα\n---\n# Café Θέτα\nUnicode concepts.\n")

        idx = build_or_update_index(vault)
        w1 = resolve_safe_wikilink("Math/Entropy.md", idx)
        self.assertEqual(w1, "[[Math/Entropy|Entropy (Math)]]")
        w_anchor = resolve_safe_wikilink("Math/Entropy.md", idx, anchor="^ent-def")
        self.assertEqual(w_anchor, "[[Math/Entropy#^ent-def|Entropy (Math)]]")
        self.assertTrue(links_equivalent("[[Shannon Entropy]]", "Math/Entropy.md", idx))
        self.assertTrue(links_equivalent("[[Math/Entropy|Custom Alias]]", "Math/Entropy.md", idx))

        # Unicode search & plan
        plan = plan_note(vault, topic="Théorème de Café", keywords=["Café", "Θέτα"])
        self.assertTrue(any("Café_Θέτα" in r["rel_path"] for r in plan["relevant_notes"]))

    def test_mermaid_escaping_direction_fallback_and_user_diagram_preservation(self) -> None:
        vault = self.tmp / "MermaidVault"
        write_file(vault / ".obsidian" / "app.json", "{}")
        write_file(
            vault / "ML" / "Existing Diagram Note.md",
            "# Existing Diagram Note\n\n```mermaid\nflowchart LR\n  A[User Input] --> B[User Output]\n```\n\nExisting prose.\n",
        )
        write_file(vault / "ML" / "Linear Algebra.md", "# Linear Algebra\nVectors & matrices.\n")
        write_file(vault / "ML" / "Gradient Descent.md", "# Gradient Descent\nIterative optimization.\n")

        profile = discover_vault(vault)
        self.assertTrue(profile["mermaid_conventions"]["uses_mermaid"])
        self.assertEqual(profile["mermaid_conventions"]["preferred_direction"], "LR")

        # 1. Special character escaping + mindmap + flowchart fallback
        diag_mm = plan_mermaid_diagram(
            topic="Backprop (Chain Rule) [v2]",
            profile=profile,
            target_folder="ML",
            related_notes=[
                {"rel_path": "ML/Linear Algebra.md", "title": "Linear Algebra", "stem": "Linear Algebra", "score": 9.0},
                {"rel_path": "ML/Gradient Descent.md", "title": "Gradient Descent", "stem": "Gradient Descent", "score": 8.0},
            ],
            content={"concepts": ["Jacobian (J)", "Chain Rule: f(g(x))"]},
            mermaid_mode="mindmap",
            mindmap_supported=True,
        )
        self.assertTrue(diag_mm["include_diagram"])
        self.assertEqual(diag_mm["diagram_type"], "mindmap")
        self.assertTrue(diag_mm["validation"]["valid"])
        self.assertEqual(diag_mm["validation"]["validation_mode"], "structural_only")
        self.assertIn("limitation", diag_mm["validation"])

        diag_fb = plan_mermaid_diagram(
            topic="Backprop (Chain Rule) [v2]",
            profile=profile,
            target_folder="ML",
            related_notes=[
                {"rel_path": "ML/Linear Algebra.md", "title": "Linear Algebra", "stem": "Linear Algebra", "score": 9.0},
            ],
            content={"concepts": ["Jacobian (J)", "Chain Rule: f(g(x))"]},
            mermaid_mode="mindmap",
            mindmap_supported=False,
        )
        self.assertTrue(diag_fb["fallback_used"])
        self.assertEqual(diag_fb["diagram_type"], "flowchart")
        self.assertTrue(diag_fb["validation"]["valid"])

        # 2. Do NOT fabricate prerequisite arrows from keyword similarity alone
        diag_rel = plan_mermaid_diagram(
            topic="Attention",
            profile=profile,
            target_folder="ML",
            related_notes=[
                {"rel_path": "ML/Linear Algebra.md", "title": "Linear Algebra", "stem": "Linear Algebra", "score": 9.0},
                {"rel_path": "ML/Gradient Descent.md", "title": "Gradient Descent", "stem": "Gradient Descent", "score": 8.0},
            ],
            mermaid_mode="flowchart",
        )
        self.assertNotIn("prerequisite", diag_rel["mermaid_code"])

        # 3. Extending existing note with user Mermaid diagram MUST preserve the user diagram
        ext = generate_vault_note(
            vault,
            topic="Existing Diagram Note",
            extend_rel_path="ML/Existing Diagram Note.md",
            content={
                "prerequisites": ["Linear Algebra"],
                "steps": ["Forward Pass", "Backward Pass"],
            },
            mermaid_mode="flowchart",
            apply=True,
        )
        self.assertTrue(ext["ok"])
        updated = read_text_safe(vault / "ML" / "Existing Diagram Note.md")
        self.assertIn("A[User Input] --> B[User Output]", updated)
        self.assertIn("<!-- teachme:mermaid:start", updated)

        # Invalid Mermaid check
        bad = validate_mermaid_syntax("flowchart TD\n  A[Unclosed --> B")
        self.assertFalse(bad["valid"])

    def test_stale_cache_concurrent_edit_and_rollback_on_failed_write(self) -> None:
        vault = self.tmp / "TxVault"
        write_file(vault / ".obsidian" / "app.json", "{}")
        n1 = write_file(vault / "ML" / "Loss Functions.md", "---\ntags: [ml]\n---\n# Loss Functions\nErrors.\n")
        n2 = write_file(vault / "ML" / "Optimization.md", "---\ntags: [ml]\n---\n# Optimization\nGradients.\n")
        moc = write_file(vault / "ML" / "ML MOC.md", "# ML MOC\n\n- [[Loss Functions]]\n- [[Optimization]]\n")

        # 1. Stale cache refresh when a file is deleted/renamed
        discover_vault(vault)
        build_or_update_index(vault)
        n2.unlink()
        write_file(vault / "ML" / "Convex Optimization.md", "---\ntags: [ml]\n---\n# Convex Optimization\nGradients.\n")
        prof2 = load_or_discover_profile(vault)
        idx2 = load_or_build_index(vault)
        self.assertNotIn("ML/Optimization.md", idx2["docs"])
        self.assertIn("ML/Convex Optimization.md", idx2["docs"])
        self.assertEqual(prof2["total_notes"], 3)

        # 2. Preview -> Concurrent edit -> Reject stale plan on apply!
        plan = plan_note(
            vault,
            topic="Adam Optimizer",
            explicit_folder="ML",
            keywords=["optimization", "loss functions"],
            save_plan=True,
        )
        self.assertEqual(plan["moc_decisions"]["action"], "update_existing")
        # Simulate external user edit to ML MOC after preview
        moc.write_text("# ML MOC\n\n- [[Loss Functions]]\n- [[Convex Optimization]]\n- [[User Added Note]]\n", encoding="utf-8")
        with self.assertRaises(RuntimeError):
            generate_vault_note(vault, plan_ref=plan["plan_id"], apply=True)
        # Target note must NOT have been created because transaction aborted
        self.assertFalse((vault / "ML" / "Adam Optimizer.md").exists())

        # 3. Failed write on 2nd file in multi-file transaction must ROLL BACK 1st file!
        fresh_plan = plan_note(
            vault,
            topic="Adam Optimizer",
            explicit_folder="ML",
            keywords=["optimization", "loss functions"],
            save_plan=True,
        )
        moc_before_fail = read_text_safe(moc)
        write_calls = {"count": 0}

        def failing_writer(path: Path, text: str) -> None:
            write_calls["count"] += 1
            if write_calls["count"] == 2:
                raise OSError("Simulated disk full on second file")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")

        with self.assertRaises(RuntimeError):
            generate_vault_note(vault, plan_ref=fresh_plan["plan_id"], apply=True, write_fn=failing_writer)

        # Verify full rollback: 1st file deleted, MOC untouched, transaction journal marked rolled_back
        self.assertFalse((vault / "ML" / "Adam Optimizer.md").exists())
        self.assertEqual(read_text_safe(moc), moc_before_fail)
        tx_files = list((vault / ".teachme" / "transactions").glob("tx-*.json"))
        self.assertEqual(len(tx_files), 1)
        tx_data = json.loads(read_text_safe(tx_files[0]))
        self.assertEqual(tx_data["status"], "rolled_back")

    def test_end_to_end_cli_discover_plan_preview_apply_audit_repeat(self) -> None:
        vault = self.tmp / "E2EVault"
        fake_home = self.tmp / "Home"
        fake_home.mkdir(parents=True, exist_ok=True)
        env = {"HOME": str(fake_home), "USERPROFILE": str(fake_home)}

        write_file(vault / ".obsidian" / "app.json", "{}")
        # User MOC intentionally has a pre-existing broken link `[[PreExisting Missing]]`
        write_file(
            vault / "CS" / "Algorithms MOC.md",
            "# Algorithms MOC\n\n- [[Binary Search]]\n- [[Quick Sort]]\n- [[PreExisting Missing]]\n",
        )
        write_file(vault / "CS" / "Binary Search.md", "---\ntags: [cs/algorithms]\n---\n# Binary Search\nDivide and conquer search.\n")
        write_file(vault / "CS" / "Quick Sort.md", "---\ntags: [cs/algorithms]\n---\n# Quick Sort\nDivide and conquer sorting.\n")

        content_file = self.tmp / "content.json"
        write_file(
            content_file,
            json.dumps(
                {
                    "intuition": "Merge sort divides arrays in half and merges sorted subarrays in O(n log n) time.",
                    "prerequisites": ["Binary Search"],
                    "contrasts_with": ["Quick Sort"],
                    "steps": ["Split Array", "Sort Halves", "Merge Sorted"],
                    "concepts": ["Divide and Conquer", "Stable Sorting"],
                }
            ),
        )

        # 1. Connect & Discover
        r_conn = run_cli("connect", str(vault), env=env)
        self.assertEqual(r_conn.returncode, 0, r_conn.stderr)
        r_disc = run_cli("discover", env=env)
        self.assertEqual(r_disc.returncode, 0, r_disc.stderr)
        disc_data = json.loads(r_disc.stdout)
        self.assertTrue(any(m["path"] == "CS/Algorithms MOC.md" for m in disc_data["mocs"]))

        # 2. Plan & Preview
        r_plan = run_cli(
            "plan",
            "--topic", "Merge Sort",
            "--keywords", "algorithms,sorting,divide and conquer",
            "--content-json", str(content_file),
            env=env,
        )
        self.assertEqual(r_plan.returncode, 0, r_plan.stderr)
        plan_data = json.loads(r_plan.stdout)
        plan_id = plan_data["plan_id"]
        self.assertEqual(plan_data["moc_decisions"]["action"], "update_existing")
        self.assertEqual(plan_data["moc_decisions"]["selected_moc"], "CS/Algorithms MOC.md")
        self.assertTrue(plan_data["diagram_decisions"]["include_diagram"])
        self.assertIn("cs/algorithms", plan_data["tags"])

        # 3. Apply exact reviewed plan
        r_apply = run_cli("apply", "--plan", plan_id, "--plan-hash", plan_data["plan_hash"], env=env)
        self.assertEqual(r_apply.returncode, 0, r_apply.stderr)
        apply_data = json.loads(r_apply.stdout)
        self.assertTrue(apply_data["applied"])
        self.assertTrue((vault / "CS" / "Merge Sort.md").is_file())
        moc_text = read_text_safe(vault / "CS" / "Algorithms MOC.md")
        self.assertIn("[[Merge Sort]]", moc_text)

        # 4. Audit: zero TeachMe errors, pre-existing broken link separated into pre_existing_issues
        r_audit = run_cli("audit", env=env)
        self.assertEqual(r_audit.returncode, 0, r_audit.stderr)
        audit_data = json.loads(r_audit.stdout)
        self.assertEqual(audit_data["errors"], [])
        self.assertIn("CS/Algorithms MOC.md", audit_data["audited_moc_updates"])
        self.assertTrue(any("PreExisting Missing" in pe["detail"] for pe in audit_data["pre_existing_issues"]))

        # 5. Repeat workflow (--extend on Merge Sort): must produce NO duplicate tags, links, sections, MOCs, or diagrams!
        r_repeat = run_cli(
            "generate",
            "--topic", "Merge Sort",
            "--extend", "CS/Merge Sort.md",
            "--content-json", str(content_file),
            "--apply",
            env=env,
        )
        self.assertEqual(r_repeat.returncode, 0, r_repeat.stderr)
        repeat_data = json.loads(r_repeat.stdout)
        self.assertEqual(repeat_data["moc_decisions"]["action"], "already_linked")
        self.assertNotIn("plan", repeat_data)  # compact apply receipt omits full nested plan

        moc_after_repeat = read_text_safe(vault / "CS" / "Algorithms MOC.md")
        self.assertEqual(moc_after_repeat.count("[[Merge Sort]]"), 1)

        note_after_repeat = read_text_safe(vault / "CS" / "Merge Sort.md")
        self.assertEqual(note_after_repeat.count("## TeachMe Extension: Merge Sort"), 1)
        self.assertEqual(note_after_repeat.count("```mermaid"), 2)  # 1 from initial creation + 1 in extension block

        # Run extend a second time with identical content -> must remain exactly 1 extension & 2 diagrams (idempotent!)
        r_repeat_2 = run_cli(
            "generate",
            "--topic", "Merge Sort",
            "--extend", "CS/Merge Sort.md",
            "--content-json", str(content_file),
            "--apply",
            env=env,
        )
        self.assertEqual(r_repeat_2.returncode, 0, r_repeat_2.stderr)
        note_after_repeat_2 = read_text_safe(vault / "CS" / "Merge Sort.md")
        self.assertEqual(note_after_repeat_2.count("## TeachMe Extension: Merge Sort"), 1)
        self.assertEqual(note_after_repeat_2, note_after_repeat)

    def test_reviewed_plan_tamper_rejection_and_unresolved_refusal(self) -> None:
        vault = self.tmp / "PlanIntegrityVault"
        write_file(vault / ".obsidian" / "app.json", "{}")
        write_file(vault / "ML" / "Gradient Descent.md", "# Gradient Descent\nBase.\n")

        # 1. Valid plan saved on disk -> tamper new_text without updating plan_hash -> must reject!
        plan = plan_note(vault, topic="Backpropagation", explicit_folder="ML", save_plan=True)
        plan_path = Path(plan["plan_file"])
        tampered = json.loads(read_text_safe(plan_path))
        tampered["affected_files"][0]["new_text"] += "\nTampered content!\n"
        plan_path.write_text(json.dumps(tampered, indent=2), encoding="utf-8")

        with self.assertRaises(RuntimeError):
            generate_vault_note(vault, plan_ref=plan["plan_id"], apply=True)
        self.assertFalse((vault / "ML" / "Backpropagation.md").exists())

        # 2. Tamper rel_path / action / must_not_exist while keeping stored plan_hash -> must reject!
        tampered2 = json.loads(read_text_safe(plan_path))
        tampered2["affected_files"][0]["new_text"] = plan["affected_files"][0]["new_text"]
        tampered2["affected_files"][0]["must_not_exist"] = False
        plan_path.write_text(json.dumps(tampered2, indent=2), encoding="utf-8")
        with self.assertRaises(RuntimeError):
            generate_vault_note(vault, plan_ref=plan["plan_id"], apply=True)

        # 3. Unresolved exact-match plan without --extend must be refused by apply
        unresolved_plan = plan_note(vault, topic="Gradient Descent", explicit_folder="ML", save_plan=True)
        self.assertTrue(unresolved_plan["unresolved"])
        with self.assertRaises(RuntimeError):
            generate_vault_note(vault, plan_ref=unresolved_plan["plan_id"], apply=True)

    def test_second_extension_validation_catches_errors_while_ignoring_user_prose(self) -> None:
        vault = self.tmp / "ExtValVault"
        write_file(vault / ".obsidian" / "app.json", "{}")
        # User note has pre-existing broken user link + valid 1st TeachMe extension block
        orig = (
            "# User Note\n\n"
            "Pre-existing user prose with [[PreExisting Broken User Link]] and $a$.\n\n"
            "<!-- teachme:extension:start id=first-topic -->\n"
            "## TeachMe Extension: First Topic\n\n"
            "Valid first extension.\n"
            "<!-- teachme:extension:end -->\n"
        )
        note_path = write_file(vault / "Notes" / "User Note.md", orig)

        # Valid 2nd extension must succeed despite pre-existing broken user link
        ok_res = generate_vault_note(
            vault,
            topic="Second Valid Topic",
            extend_rel_path="Notes/User Note.md",
            content={"intuition": "Clean second extension."},
            apply=True,
        )
        self.assertTrue(ok_res["ok"])
        self.assertTrue(ok_res["audit_passed"])

        # Craft a plan where the 1st extension is valid, but the 2nd extension has a broken link + unmatched $ + bad Mermaid
        bad_plan = plan_note(
            vault,
            topic="Broken Second Topic",
            extend_rel_path="Notes/User Note.md",
            save_plan=False,
        )
        bad_ext_text = (
            read_text_safe(note_path).rstrip()
            + "\n\n<!-- teachme:extension:start id=broken-second-topic -->\n"
            + "## TeachMe Extension: Broken Second Topic\n\n"
            + "Broken [[Missing Target]] and $unclosed math.\n\n"
            + "<!-- teachme:mermaid:start id=bad -->\n```mermaid\nflowchart TD\n  A[Unclosed --> B\n```\n<!-- teachme:mermaid:end -->\n"
            + "<!-- teachme:extension:end -->\n"
        )
        bad_plan["affected_files"][0]["new_text"] = bad_ext_text
        from teachme_vault.planner import compute_canonical_plan_hash
        bad_plan["plan_hash"] = compute_canonical_plan_hash(bad_plan)

        with self.assertRaises(ValueError) as ctx:
            generate_vault_note(vault, plan_ref=bad_plan, apply=True)
        msg = str(ctx.exception)
        self.assertIn("Missing Target", msg)
        self.assertIn("Odd number of $", msg)
        self.assertIn("Invalid Mermaid diagram", msg)

    def test_audit_cli_exit_codes_and_post_commit_status_semantics(self) -> None:
        vault = self.tmp / "AuditExitVault"
        fake_home = self.tmp / "AuditHome"
        fake_home.mkdir(parents=True, exist_ok=True)
        env = {"HOME": str(fake_home), "USERPROFILE": str(fake_home)}

        write_file(vault / ".obsidian" / "app.json", "{}")
        write_file(vault / "ML" / "Base.md", "# Base\nBase note.\n")
        write_file(vault / "ML" / "ML MOC.md", "# ML MOC\n\n- [[Base]]\n- [[UserBrokenLink]]\n")

        self.assertEqual(run_cli("connect", str(vault), env=env).returncode, 0)
        r_gen = run_cli("generate", "--topic", "Linear Models", "--folder", "ML", "--apply", env=env)
        self.assertEqual(r_gen.returncode, 0, r_gen.stderr)
        gen_data = json.loads(r_gen.stdout)
        self.assertTrue(gen_data["writes_committed"])
        self.assertTrue(gen_data["audit_passed"])
        self.assertEqual(gen_data["status"], "applied_and_audited")

        # Audit with pre_existing_issues (warnings/user broken link) MUST still exit 0
        r_audit_ok = run_cli("audit", env=env)
        self.assertEqual(r_audit_ok.returncode, 0, r_audit_ok.stderr)

        # Introduce a real error inside the TeachMe-managed note -> audit MUST exit 1!
        managed_note = vault / "ML" / "Linear Models.md"
        managed_note.write_text(read_text_safe(managed_note) + "\nBroken [[Missing Note]].\n", encoding="utf-8")
        r_audit_err = run_cli("audit", env=env)
        self.assertEqual(r_audit_err.returncode, 1)
        self.assertGreater(len(json.loads(r_audit_err.stdout)["errors"]), 0)

        # Post-commit bookkeeping error must NOT claim rollback when writes succeeded
        def fail_post_commit() -> None:
            raise OSError("Simulated manifest permission failure after commit")

        res_pc = generate_vault_note(
            vault,
            topic="Logistic Regression",
            explicit_folder="ML",
            apply=True,
            post_commit_fn=fail_post_commit,
        )
        self.assertTrue(res_pc["writes_committed"])
        self.assertEqual(res_pc["transaction_status"], "committed")
        self.assertFalse(res_pc["audit_passed"])
        self.assertEqual(res_pc["status"], "applied_audit_failed")
        self.assertFalse(res_pc["ok"])
        self.assertTrue((vault / "ML" / "Logistic Regression.md").is_file())

    def test_proposed_related_notes_merged_deduped_and_fed_to_diagram(self) -> None:
        vault = self.tmp / "ProposedLinksVault"
        write_file(vault / ".obsidian" / "app.json", "{}")
        write_file(vault / "ML" / "Linear Algebra.md", "# Linear Algebra\nVectors and matrices.\n")
        write_file(vault / "ML" / "Matrix Calculus.md", "# Matrix Calculus\nJacobians and Hessians.\n")

        plan = plan_note(
            vault,
            topic="Gradient Descent",
            explicit_folder="ML",
            keywords=["linear algebra"],
            proposal={
                "related_notes": [
                    {"target": "ML/Matrix Calculus.md", "reason": "Provides Jacobian computation"},
                    "ML/Linear Algebra.md",  # Duplicate with search -> should deduplicate!
                    "ML/Gradient Descent.md",  # Self-link -> should exclude!
                    "ML/Does Not Exist.md",  # Invalid -> should reject!
                ]
            },
            mermaid_mode="flowchart",
        )
        verified_rels = [v["rel_path"] for v in plan["relevant_notes"]]
        self.assertIn("ML/Matrix Calculus.md", verified_rels)
        self.assertEqual(verified_rels.count("ML/Linear Algebra.md"), 1)
        self.assertNotIn("ML/Gradient Descent.md", verified_rels)
        self.assertTrue(any(r["target"] == "ML/Does Not Exist.md" for r in plan["link_decisions"]["rejected_or_unresolved"]))
        # Proposed link fed into rendered note AND Mermaid diagram
        self.assertIn("[[Matrix Calculus]]", plan["affected_files"][0]["new_text"])
        self.assertIn("Matrix Calculus", plan["diagram_decisions"]["mermaid_code"])

    def test_planning_action_consistency_no_silent_similar_extend(self) -> None:
        vault = self.tmp / "ActionConsistencyVault"
        write_file(vault / ".obsidian" / "app.json", "{}")
        write_file(
            vault / "ML" / "Gradient Descent Guide.md",
            "---\ntags: [ml]\n---\n# Gradient Descent Guide\nGradient descent optimization guide.\n",
        )

        # Similar (non-exact) match should NOT silently recommend extend_existing
        plan_sim = plan_note(vault, topic="Gradient Descent", explicit_folder="ML", keywords=["optimization", "gradient", "descent"])
        self.assertIn(plan_sim["recommended_action"], ("create_new", "split_atomic"))
        self.assertEqual(plan_sim["affected_files"][0]["action"], "create")
        self.assertFalse(plan_sim["unresolved"])

        # Exact match without --extend must have consistent extend_existing + unresolved conflict state
        write_file(vault / "ML" / "Gradient Descent.md", "# Gradient Descent\nExact note.\n")
        plan_exact = plan_note(vault, topic="Gradient Descent", explicit_folder="ML")
        self.assertEqual(plan_exact["recommended_action"], "extend_existing")
        self.assertTrue(plan_exact["unresolved"])
        self.assertEqual(plan_exact["affected_files"][0]["action"], "extend")
        self.assertTrue(plan_exact["affected_files"][0]["conflict"])

    def test_two_unrelated_query_mocs_in_same_folder_and_complex_where(self) -> None:
        vault = self.tmp / "DualQueryMocVault"
        write_file(vault / ".obsidian" / "app.json", "{}")
        write_file(vault / ".obsidian" / "community-plugins.json", json.dumps(["dataview"]))
        write_file(
            vault / "CS" / "Algorithms Query MOC.md",
            '# Algorithms Query MOC\n\n```dataview\nTABLE status FROM "CS" AND #algorithms\nWHERE status != "archived"\n```\n',
        )
        write_file(
            vault / "CS" / "Databases Query MOC.md",
            '# Databases Query MOC\n\n```dataview\nTABLE engine FROM "CS" AND #databases\nWHERE engine = "postgres" AND contains(topic, "sql")\n```\n',
        )
        write_file(vault / "CS" / "Quick Sort.md", "---\ntags: [algorithms]\nstatus: seedling\n---\n# Quick Sort\nSorting.\n")

        plan = plan_note(vault, topic="Heap Sort", explicit_folder="CS", keywords=["algorithms", "sorting"])
        self.assertEqual(plan["moc_decisions"]["action"], "satisfy_query")
        self.assertEqual(plan["moc_decisions"]["selected_moc"], "CS/Algorithms Query MOC.md")
        self.assertNotIn("databases", plan["tags"])
        self.assertNotIn("engine", plan["frontmatter"])
        self.assertEqual(plan["frontmatter"].get("status"), "seedling")

        # Complex WHERE predicate on Databases Query MOC should NOT emit empty engine="" and pretend it satisfied predicate
        db_plan = plan_note(vault, topic="Postgres Indexing", explicit_folder="CS", keywords=["databases", "sql"])
        self.assertEqual(db_plan["moc_decisions"]["selected_moc"], "CS/Databases Query MOC.md")
        self.assertEqual(db_plan["moc_decisions"]["query_satisfaction"], "unverified_complex_or_predicate")
        self.assertNotEqual(db_plan["frontmatter"].get("engine"), "")
        self.assertTrue(any("complex Dataview" in w for w in db_plan["warnings"]))

    def test_reliability_unicode_slugs_attachments_obsidian_staleness_and_rollback_safety(self) -> None:
        vault = self.tmp / "ReliabilityVault"
        write_file(vault / ".obsidian" / "app.json", "{}")
        write_file(vault / ".obsidian" / "templates.json", json.dumps({"folder": "Templates"}))
        write_file(vault / "Templates" / "Concept.md", "---\ntags: [study]\n---\n# {{title}}\n")
        write_file(vault / "Assets" / "diagram.png", "PNGDATA")
        write_file(vault / "Notes" / "Target.md", "# Target\nBase note.\n")
        write_file(vault / "Notes" / "TargetTwo.md", "# TargetTwo\nSecond note.\n")
        write_file(vault / "Notes" / "Notes MOC.md", "# Notes MOC\n\n- [[Target]]\n- [[TargetTwo]]\n")

        # 1. Distinct non-ASCII Unicode topics produce distinct session dirs and extension IDs
        r1 = generate_vault_note(vault, topic="Θέτα", extend_rel_path="Notes/Target.md", apply=True)
        r2 = generate_vault_note(vault, topic="Άλφα", extend_rel_path="Notes/Target.md", apply=True)
        self.assertNotEqual(r1["session_dir"], r2["session_dir"])
        target_text = read_text_safe(vault / "Notes" / "Target.md")
        self.assertIn("## TeachMe Extension: Θέτα", target_text)
        self.assertIn("## TeachMe Extension: Άλφα", target_text)

        # 2. Valid attachment embed ![[diagram.png]] passes both preflight AND audit without missing-note error
        plan_att = plan_note(
            vault,
            topic="Visual Concept",
            explicit_folder="Notes",
            content={"intuition": "See ![[diagram.png]] for the layout."},
            save_plan=True,
        )
        res_att = generate_vault_note(vault, plan_ref=plan_att["plan_id"], apply=True)
        self.assertTrue(res_att["ok"])
        self.assertEqual(res_att["audit"]["errors"], [])

        # 3. Changing .obsidian/templates.json invalidates cached profile automatically
        p1 = load_or_discover_profile(vault)
        self.assertEqual(p1["plugins"]["template_folders"], ["Templates"])
        write_file(vault / "AltTemplates" / "Concept.md", "# {{title}}\n")
        write_file(vault / ".obsidian" / "templates.json", json.dumps({"folder": "AltTemplates"}))
        p2 = load_or_discover_profile(vault)
        self.assertEqual(p2["plugins"]["template_folders"], ["AltTemplates"])

        # 4. Rollback skips overwriting a file modified externally after our 1st write before 2nd write fails
        plan_rb = plan_note(vault, topic="Rollback Test", explicit_folder="Notes", keywords=["target"], save_plan=True)
        # Ensure we have 2 affected files (target note + Notes MOC)
        self.assertGreaterEqual(len(plan_rb["affected_files"]), 2)
        first_file = vault / plan_rb["affected_files"][0]["rel_path"]
        calls = {"n": 0}

        def external_race_writer(path: Path, text: str) -> None:
            calls["n"] += 1
            if calls["n"] == 1:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(text + "\n<!-- external process edit -->\n", encoding="utf-8")
            else:
                raise OSError("Simulated failure on 2nd write")

        with self.assertRaises(RuntimeError):
            generate_vault_note(vault, plan_ref=plan_rb["plan_id"], apply=True, write_fn=external_race_writer)
        # External edit must NOT have been deleted/overwritten by rollback
        self.assertTrue(first_file.is_file())
        self.assertIn("<!-- external process edit -->", read_text_safe(first_file))
        tx_files = list((vault / ".teachme" / "transactions").glob("tx-*.json"))
        tx_jsons = [json.loads(read_text_safe(p)) for p in tx_files]
        rolled_back_txs = [tx for tx in tx_jsons if tx.get("status") == "rolled_back"]
        self.assertTrue(rolled_back_txs)
        self.assertTrue(
            any("modified externally" in w for w in rolled_back_txs[-1].get("rollback_warnings", []))
        )

    def test_cli_bounded_output_modes_and_apply_receipt(self) -> None:
        vault = self.tmp / "OutputModesVault"
        fake_home = self.tmp / "OutHome"
        fake_home.mkdir(parents=True, exist_ok=True)
        env = {"HOME": str(fake_home), "USERPROFILE": str(fake_home)}

        write_file(vault / ".obsidian" / "app.json", "{}")
        write_file(vault / "ML" / "Regression.md", "# Regression\nLinear model.\n")
        self.assertEqual(run_cli("connect", str(vault), env=env).returncode, 0)

        r_plan = run_cli("plan", "--topic", "Ridge Regression", "--folder", "ML", env=env)
        self.assertEqual(r_plan.returncode, 0, r_plan.stderr)
        plan_sum = json.loads(r_plan.stdout)
        self.assertNotIn("diff", plan_sum["affected_files"][0])
        self.assertIn("detail_commands", plan_sum)

        r_dry = run_cli("generate", "--topic", "Ridge Regression", "--folder", "ML", "--dry-run", env=env)
        self.assertEqual(r_dry.returncode, 0, r_dry.stderr)
        dry_out = json.loads(r_dry.stdout)
        self.assertIn("diff", dry_out)
        self.assertNotIn("preview", dry_out)
        self.assertNotIn("plan", dry_out)
        self.assertNotIn("diff", dry_out["affected_files"][0])

        r_apply = run_cli("apply", "--plan", plan_sum["plan_id"], "--plan-hash", plan_sum["plan_hash"], env=env)
        self.assertEqual(r_apply.returncode, 0, r_apply.stderr)
        app_out = json.loads(r_apply.stdout)
        self.assertNotIn("diff", app_out)
        self.assertNotIn("preview", app_out)
        self.assertNotIn("plan", app_out)
        self.assertTrue(app_out["writes_committed"])
        self.assertTrue(app_out["audit_passed"])


if __name__ == "__main__":
    unittest.main()
