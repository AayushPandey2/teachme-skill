"""Comprehensive integration tests for Vault-Native Mode and Legacy Compatibility."""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "skills" / "teachme" / "scripts"
VAULT_CLI = SCRIPTS_DIR / "vault_cli.py"

if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from teachme_vault.discovery import MAX_STYLE_SAMPLES_GLOBAL, discover_vault
from teachme_vault.indexer import build_or_update_index, search_vault
from teachme_vault.models import MODE_STANDALONE, MODE_VAULT_NATIVE, detect_vault_mode
from teachme_vault.planner import plan_note
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


class VaultNativeIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="teachme_test_"))

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_scenario_a_organized_knowledge_vault(self) -> None:
        vault = self.tmp / "OrganizedVault"
        write_file(vault / ".obsidian" / "app.json", json.dumps({"newLinkFormat": "shortest"}))
        write_file(vault / ".obsidian" / "core-plugins.json", json.dumps(["templates", "backlinks"]))
        write_file(vault / ".obsidian" / "templates.json", json.dumps({"folder": "Templates"}))

        write_file(
            vault / "Templates" / "ML Concept Template.md",
            "---\ntags:\n  - machine-learning\ncreated: \"{{date}}\"\nstatus: \"evergreen\"\n---\n\n# {{title}}\n",
        )
        write_file(
            vault / "Knowledge" / "Machine Learning" / "Optimization" / "Loss Functions.md",
            "---\ntags:\n  - machine-learning/supervised\n  - mathematics/optimization\ncreated: \"2025-01-10\"\nstatus: \"evergreen\"\n---\n\n# Loss Functions\n\nLoss functions measure prediction error for [[Linear Regression]] and guide parameter updates via [[Partial Derivatives]].\n\n> [!note] Key Idea\n> Minimize empirical risk over training samples.\n",
        )
        write_file(
            vault / "Knowledge" / "Machine Learning" / "Linear Regression.md",
            "---\ntags:\n  - machine-learning/supervised\ncreated: \"2025-01-08\"\nstatus: \"evergreen\"\n---\n\n# Linear Regression\n\nFits linear weights minimizing squared [[Loss Functions]].\n",
        )
        write_file(
            vault / "Knowledge" / "Mathematics" / "Partial Derivatives.md",
            "---\ntags:\n  - mathematics/optimization\ncreated: \"2025-01-05\"\nstatus: \"evergreen\"\n---\n\n# Partial Derivatives\n\nGradients point in the direction of steepest ascent; negative gradients drive optimization.\n",
        )
        write_file(
            vault / "Knowledge" / "Machine Learning" / "ML MOC.md",
            "# Machine Learning MOC\n\n- [[Linear Regression]]\n- [[Loss Functions]]\n- [[Partial Derivatives]]\n",
        )
        write_file(vault / "Journal" / "2025-01-12.md", "# 2025-01-12\nReviewed optimization notes.\n")
        write_file(vault / "Projects" / "Build Classifier.md", "- [ ] Train baseline model\n")

        plan = plan_note(
            vault,
            topic="Gradient Descent",
            keywords=["optimization", "loss", "partial derivatives"],
        )
        dest_folder = plan["destination"]["folder"]
        self.assertIn("Knowledge/Machine Learning", dest_folder)
        self.assertEqual(plan["destination"]["confidence"], "high")
        self.assertEqual(plan["template"]["selected"], "Templates/ML Concept Template.md")
        self.assertTrue(
            any("machine-learning" in t or "optimization" in t for t in plan["tags"]),
            f"Expected vault ML/optimization tags, got {plan['tags']}",
        )
        self.assertNotIn("ai", plan["tags"])
        self.assertNotIn("educational", plan["tags"])
        linked_paths = {r["rel_path"] for r in plan["relevant_notes"]}
        self.assertIn("Knowledge/Machine Learning/Optimization/Loss Functions.md", linked_paths)

        res = generate_vault_note(vault, topic="Gradient Descent", apply=True)
        self.assertTrue(res["ok"])
        self.assertTrue((vault / res["target_rel_path"]).is_file())
        # State isolated under .teachme/
        self.assertTrue((vault / ".teachme" / "profile.json").is_file())
        self.assertFalse((vault / "00-SESSION-STATE.md").exists())
        audit = audit_vault_native(vault)
        self.assertEqual(audit["errors"], [])

    def test_scenario_b_zettelkasten_vault(self) -> None:
        vault = self.tmp / "ZettelVault"
        write_file(vault / ".obsidian" / "app.json", json.dumps({"newLinkFormat": "shortest"}))
        notes = [
            ("202501010900-entropy.md", "Entropy", ["information-theory"], "Measures uncertainty in bits. Links to [[202501010915-cross-entropy|Cross Entropy]]."),
            ("202501010915-cross-entropy.md", "Cross Entropy", ["information-theory"], "Expected message length under model distribution $q$. Built on [[202501010900-entropy|Entropy]]."),
            ("202501010930-kl-divergence.md", "KL Divergence", ["information-theory"], "Relative entropy between distributions $p$ and $q$. See [[202501010915-cross-entropy|Cross Entropy]]."),
            ("202501010945-mutual-information.md", "Mutual Information", ["information-theory"], "Shared information between random variables via [[202501010930-kl-divergence|KL Divergence]]."),
            ("202501011000-shannon-coding.md", "Shannon Coding", ["information-theory"], "Optimal prefix codes bounded by [[202501010900-entropy|Entropy]]."),
        ]
        for fname, title, aliases, body in notes:
            write_file(
                vault / "Slipbox" / fname,
                f"---\ntitle: \"{title}\"\naliases:\n  - \"{aliases[0]}\"\ntags:\n  - zettel/math\n---\n\n{body}\n",
            )

        profile = discover_vault(vault)
        self.assertEqual(profile["organization_pattern"]["primary"], "zettelkasten")
        plan = plan_note(vault, topic="Jensen Shannon Divergence", keywords=["kl divergence", "entropy"])
        self.assertEqual(plan["recommended_action"], "split_atomic")
        self.assertRegex(plan["destination"]["filename"], r"^\d{12}-jensen-shannon-divergence\.md$")
        self.assertTrue(len(plan["relevant_notes"]) >= 1)

    def test_scenario_c_plugin_heavy_vault(self) -> None:
        vault = self.tmp / "PluginVault"
        obs = vault / ".obsidian"
        write_file(
            obs / "community-plugins.json",
            json.dumps([
                "templater-obsidian",
                "dataview",
                "obsidian-spaced-repetition",
                "obsidian-tasks-plugin",
                "obsidian-excalidraw-plugin",
                "mystery-custom-plugin",
            ]),
        )
        write_file(
            obs / "plugins" / "templater-obsidian" / "data.json",
            json.dumps({
                "templates_folder": "Templates",
                "folder_templates": [{"folder": "CS", "template": "Templates/CS Templater.md"}],
            }),
        )
        write_file(
            obs / "plugins" / "dataview" / "data.json",
            json.dumps({"enableDataviewJs": False, "inlineQueryPrefix": "="}),
        )
        write_file(
            obs / "plugins" / "obsidian-spaced-repetition" / "data.json",
            json.dumps({"flashcardTags": ["#cards"], "singleLineCardSeparator": "::"}),
        )
        write_file(
            obs / "plugins" / "obsidian-tasks-plugin" / "data.json",
            json.dumps({"globalFilter": "#task"}),
        )
        write_file(
            obs / "plugins" / "obsidian-excalidraw-plugin" / "data.json",
            json.dumps({"folder": "Excalidraw"}),
        )
        write_file(
            obs / "plugins" / "mystery-custom-plugin" / "data.json",
            json.dumps({"apiKey": "super-secret-token-12345", "theme": "dark"}),
        )

        write_file(
            vault / "Templates" / "CS Templater.md",
            "---\ntags:\n  - cs\ndifficulty: \"medium\"\ncreated: \"<% tp.date.now('YYYY-MM-DD') %>\"\n---\n\n# <% tp.file.title %>\n\n<%* const preserved = true; %>\n",
        )
        write_file(
            vault / "CS" / "CS Index.md",
            "# CS Index\n\n```dataview\nTABLE difficulty, status FROM \"CS\"\nWHERE status != \"archived\"\n```\n",
        )
        write_file(
            vault / "CS" / "Binary Search.md",
            "---\ntags:\n  - cs\ndifficulty: \"easy\"\n---\n\n# Binary Search\n\n#cards\nTime complexity of binary search? :: $O(\\log n)$\n",
        )
        excalidraw_content = "---\nexcalidraw-plugin: parsed\ntags:\n  - excalidraw\n---\n# Drawing\n"
        write_file(vault / "Excalidraw" / "Architecture.excalidraw.md", excalidraw_content)
        write_file(vault / "Maps" / "Graph.canvas", '{"nodes":[],"edges":[]}')
        write_file(vault / "Views" / "Topics.base", "views:\n  - type: table\n")

        profile = discover_vault(vault)
        caps = {c["id"]: c for c in profile["plugins"]["capabilities"]}
        self.assertEqual(caps["templater-obsidian"]["status"], "supported_safe_render")
        self.assertEqual(caps["mystery-custom-plugin"]["status"], "detected_unsupported")
        self.assertIn("difficulty", profile["plugins"]["conventions"]["dataview_queried_fields"])
        self.assertEqual(profile["plugins"]["conventions"]["flashcard_tags"], ["cards"])

        # Ensure secret apiKey never leaked into profile.json
        profile_raw = (vault / ".teachme" / "profile.json").read_text(encoding="utf-8")
        self.assertNotIn("super-secret-token-12345", profile_raw)

        res = generate_vault_note(vault, topic="Merge Sort", explicit_folder="CS", apply=True)
        self.assertTrue(res["ok"])
        generated_text = (vault / res["target_rel_path"]).read_text(encoding="utf-8")
        # Dynamic Templater <%* ... %> preserved, safe tp.file.title replaced
        self.assertIn("<%* const preserved = true; %>", generated_text)
        self.assertEqual(generated_text.count("# Merge Sort"), 1)
        self.assertIn("#cards", generated_text)
        # Protected assets untouched
        self.assertEqual((vault / "Excalidraw" / "Architecture.excalidraw.md").read_text(encoding="utf-8"), excalidraw_content)

    def test_scenario_d_inconsistent_vault(self) -> None:
        vault = self.tmp / "MessyVault"
        write_file(vault / ".obsidian" / "app.json", "{}")
        write_file(vault / "MiscA" / "Random Note 1.md", "Just some thoughts.\n")
        write_file(vault / "MiscB" / "Another Note.md", "---\nauthor: Alice\n---\nAnother brief note.\n")
        write_file(vault / "Templates" / "Tpl A.md", "# {{title}}\n")
        write_file(vault / "Templates" / "Tpl B.md", "---\ntags: [draft]\n---\n# {{title}}\n")

        plan = plan_note(vault, topic="Quantum Entanglement")
        self.assertEqual(plan["destination"]["confidence"], "low")
        self.assertTrue(plan["destination"]["needs_confirmation"])

    def test_scenario_e_existing_note_non_destructive_extend(self) -> None:
        vault = self.tmp / "ExistingVault"
        write_file(vault / ".obsidian" / "app.json", "{}")
        orig_note = (
            "---\n"
            "title: \"Gradient Descent\"\n"
            "custom_prop: keep-me\n"
            "---\n\n"
            "<!-- user comment preserved -->\n"
            "# Gradient Descent\n\n"
            "Iterative first-order optimization algorithm. ^gd-core\n"
        )
        note_path = write_file(vault / "ML" / "Gradient Descent.md", orig_note)

        plan = plan_note(vault, topic="Gradient Descent")
        self.assertEqual(plan["recommended_action"], "extend_existing")
        self.assertIsNotNone(plan["existing_note"])

        # Creating without --extend must refuse overwrite
        conflict_res = generate_vault_note(vault, topic="Gradient Descent", explicit_folder="ML", apply=True)
        self.assertFalse(conflict_res["ok"])
        self.assertTrue(conflict_res["conflict"])
        self.assertEqual(note_path.read_text(encoding="utf-8"), orig_note)

        # Dry-run extend returns unified diff without changing file
        dry_res = generate_vault_note(
            vault, topic="Gradient Descent", extend_rel_path="ML/Gradient Descent.md", apply=False
        )
        self.assertTrue(dry_res["dry_run"])
        self.assertIn("+## TeachMe Extension: Gradient Descent", dry_res["diff"])
        self.assertEqual(note_path.read_text(encoding="utf-8"), orig_note)

        # Apply extend preserves original YAML, comment, block ID, and creates backup
        ext_res = generate_vault_note(
            vault, topic="Gradient Descent", extend_rel_path="ML/Gradient Descent.md", apply=True
        )
        self.assertTrue(ext_res["applied"])
        updated_text = note_path.read_text(encoding="utf-8")
        self.assertIn("custom_prop: keep-me", updated_text)
        self.assertIn("<!-- user comment preserved -->", updated_text)
        self.assertIn("^gd-core", updated_text)
        self.assertIn("## TeachMe Extension: Gradient Descent", updated_text)
        self.assertTrue((vault / ".teachme" / ext_res["backup_rel_path"]).is_file())

        # Stale expected_hash raises conflict
        with self.assertRaises(RuntimeError):
            generate_vault_note(
                vault,
                topic="Gradient Descent",
                extend_rel_path="ML/Gradient Descent.md",
                expected_hash="deadbeef",
                apply=True,
            )

    def test_scenario_f_large_vault_bounded_and_incremental(self) -> None:
        vault = self.tmp / "LargeVault"
        write_file(vault / ".obsidian" / "app.json", "{}")
        for i in range(1200):
            bucket = f"Domain_{i % 12:02d}"
            write_file(
                vault / bucket / f"Concept {i:04d}.md",
                f"---\ntags:\n  - domain-{i % 12}\n---\n\n# Concept {i:04d}\n\nNote body about topic {i} and optimization.\n",
            )

        t0 = time.perf_counter()
        profile = discover_vault(vault)
        idx1 = build_or_update_index(vault)
        elapsed = time.perf_counter() - t0

        self.assertEqual(profile["total_notes"], 1200)
        self.assertEqual(idx1["doc_count"], 1200)
        self.assertLessEqual(profile["global_style"]["sample_count"], MAX_STYLE_SAMPLES_GLOBAL)
        self.assertLess(elapsed, 15.0)

        # Incremental refresh should reuse all 1200 unchanged notes
        idx2 = build_or_update_index(vault, full=False)
        self.assertEqual(idx2["stats"]["reused"], 1200)
        self.assertEqual(idx2["stats"]["added"], 0)
        self.assertEqual(idx2["stats"]["updated"], 0)

        # Search remains fast and accurate
        res = search_vault(vault, "Concept 0456", limit=5, index=idx2, profile=profile)
        self.assertEqual(res["results"][0]["stem"], "Concept 0456")

    def test_scenario_g_legacy_standalone_compatibility(self) -> None:
        vault = self.tmp / "standalone-topic"
        subtopics = [
            {"slug": "01-basics", "title": "Basics", "depends_on": [], "contrasts_with": []},
            {"slug": "02-advanced", "title": "Advanced", "depends_on": ["topic-01"], "contrasts_with": []},
        ]
        sub_file = self.tmp / "subtopics.json"
        write_file(sub_file, json.dumps(subtopics))

        r_init = run_cli("init", str(vault), "--topic", "Test Topic", "--subtopics", str(sub_file))
        self.assertEqual(r_init.returncode, 0, r_init.stderr)
        self.assertEqual(detect_vault_mode(vault)["mode"], MODE_STANDALONE)

        # Add required sections/sources so verify passes cleanly
        write_file(vault / "01-RESOURCES.md", "# Resources\n\n### Source 1\n- https://example.org/spec\n")
        write_file(vault / "02-DEEP-RESEARCH.md", "# Research\n\n### Deep 1\nDetails.\n")
        for n, slug, title in [("01", "01-basics", "Basics"), ("02", "02-advanced", "Advanced")]:
            p = vault / "topics" / f"{slug}.md"
            text = p.read_text(encoding="utf-8")
            text += (
                "\n### Primary Sources & Deep Links\n"
                "| Source | Direct External Deep Link | Vault Deep Link | Exact Claim Verified |\n"
                "|---|---|---|---|\n"
                "| Spec | [Sec](https://example.org/spec) | [[01-RESOURCES#Source 1]] | *Claim* |\n"
            )
            p.write_text(text, encoding="utf-8")

        r_ctx = run_cli("context", str(vault), "--topic", "01")
        self.assertEqual(r_ctx.returncode, 0, r_ctx.stderr)
        r_tick = run_cli("tick", str(vault), "--topic", "01", "--cp", "4", "--status", "pass", "--note", "Base invariant")
        self.assertEqual(r_tick.returncode, 0, r_tick.stderr)
        r_flush = run_cli("flush", str(vault), "--topic", "01", "--note", "Base invariant")
        self.assertEqual(r_flush.returncode, 0, r_flush.stderr)
        r_fix = run_cli("fix", str(vault))
        self.assertEqual(r_fix.returncode, 0, r_fix.stderr)
        r_verify = run_cli("verify", str(vault))
        self.assertEqual(r_verify.returncode, 0, r_verify.stderr)
        vdata = json.loads(r_verify.stdout)
        self.assertEqual(vdata["errors"], [])

    def test_scenario_h_safety_and_malformed_inputs(self) -> None:
        vault = self.tmp / "SafetyVault"
        outside_secret = self.tmp / "outside_secret.md"
        write_file(outside_secret, "# SECRET\nDo not leak this external file!\n")

        write_file(vault / ".obsidian" / "app.json", json.dumps({"userIgnoreFilters": ["IgnoredFolder/"]}))
        write_file(vault / "IgnoredFolder" / "Private.md", "# Private\nShould be ignored.\n")
        # Malformed YAML + broken user link + unbracketed bare LaTeX
        malformed_user_note = (
            "---\n"
            "title: Broken: Unquoted\n"
            "\tbad_tab: true\n"
            "---\n\n"
            "# Café Θέτα\n\n"
            "See [[NonExistent User Link]] and \\theta without dollars.\n"
        )
        unicode_note = write_file(vault / "Équations" / "Café_Θέτα.md", malformed_user_note)

        # Attempt symlink pointing outside vault (skip symlink creation if Windows privilege denies it)
        symlink_path = vault / "escape_link.md"
        try:
            os.symlink(outside_secret, symlink_path)
        except OSError:
            pass

        self.assertEqual(detect_vault_mode(vault)["mode"], MODE_VAULT_NATIVE)

        profile = discover_vault(vault)
        idx = build_or_update_index(vault)
        self.assertNotIn("escape_link.md", idx["docs"])
        self.assertNotIn("IgnoredFolder/Private.md", idx["docs"])
        self.assertIn("Équations/Café_Θέτα.md", idx["docs"])
        self.assertGreaterEqual(profile["health"]["malformed_yaml_count"], 1)

        # Path traversal attempt must fail
        with self.assertRaises(ValueError):
            generate_vault_note(vault, topic="Hack", extend_rel_path="../outside_secret.md", apply=True)

        # Legacy fix & verify must NOT touch or fail on user-authored notes in vault-native mode
        r_fix = run_cli("fix", str(vault))
        self.assertEqual(r_fix.returncode, 0, r_fix.stderr)
        fix_data = json.loads(r_fix.stdout)
        self.assertTrue(fix_data["skipped"])
        self.assertEqual(unicode_note.read_text(encoding="utf-8"), malformed_user_note)

        r_verify = run_cli("verify", str(vault))
        self.assertEqual(r_verify.returncode, 0, r_verify.stderr)
        v_data = json.loads(r_verify.stdout)
        self.assertTrue(v_data["user_notes_untouched"])
        self.assertEqual(v_data["errors"], [])

    def test_cli_connect_discover_search_plan_generate_audit(self) -> None:
        vault = self.tmp / "CLIVault"
        fake_home = self.tmp / "FakeHome"
        fake_home.mkdir(parents=True, exist_ok=True)
        write_file(vault / ".obsidian" / "app.json", "{}")
        write_file(
            vault / "ML" / "Backpropagation.md",
            "---\ntags:\n  - ml/training\n---\n\n# Backpropagation\n\nComputes gradients using the chain rule.\n",
        )
        env = {"HOME": str(fake_home), "USERPROFILE": str(fake_home)}

        r_conn = run_cli("connect", str(vault), env=env)
        self.assertEqual(r_conn.returncode, 0, r_conn.stderr)
        self.assertEqual(json.loads(r_conn.stdout)["active_mode"], "vault-native")

        r_prof = run_cli("profile", env=env)
        self.assertEqual(r_prof.returncode, 0, r_prof.stderr)
        self.assertEqual(json.loads(r_prof.stdout)["total_notes"], 1)

        r_search = run_cli("search", "--query", "chain rule gradients", env=env)
        self.assertEqual(r_search.returncode, 0, r_search.stderr)
        self.assertEqual(json.loads(r_search.stdout)["results"][0]["stem"], "Backpropagation")

        r_plan = run_cli("plan", "--topic", "Automatic Differentiation", "--keywords", "chain rule,gradients", env=env)
        self.assertEqual(r_plan.returncode, 0, r_plan.stderr)
        self.assertEqual(json.loads(r_plan.stdout)["destination"]["folder"], "ML")

        r_gen = run_cli("generate", "--topic", "Automatic Differentiation", "--apply", env=env)
        self.assertEqual(r_gen.returncode, 0, r_gen.stderr)
        gen_data = json.loads(r_gen.stdout)
        self.assertTrue(gen_data["applied"])

        r_audit = run_cli("audit", env=env)
        self.assertEqual(r_audit.returncode, 0, r_audit.stderr)
        audit_data = json.loads(r_audit.stdout)
        self.assertEqual(audit_data["errors"], [])
        self.assertIn(gen_data["target_rel_path"], audit_data["audited_files"])


if __name__ == "__main__":
    unittest.main()
