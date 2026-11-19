"""Tests for Vault-Native state isolation, read-only Obsidian search, and safety guards."""

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

from teachme_vault.indexer import build_or_update_index, search_vault
from teachme_vault.models import (
    MODE_STANDALONE,
    MODE_VAULT_NATIVE,
    detect_vault_mode,
    is_within_root,
    redact_sensitive,
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


class VaultNativeStateAndSearchTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="teachme_vn_test_"))
        self.cfg_path = self.tmp / "teachme-config.json"
        self.env = {"TEACHME_CONFIG_PATH": str(self.cfg_path)}

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_connect_search_and_isolated_session_do_not_modify_obsidian_notes(self) -> None:
        vault = self.tmp / "ObsidianVault"
        write_file(vault / ".obsidian" / "app.json", json.dumps({"newLinkFormat": "shortest"}))
        note1 = write_file(
            vault / "ML" / "Gradient Descent.md",
            "---\ntags:\n  - optimization\n---\n# Gradient Descent\n\nIterative first-order optimization.\n",
        )
        note2 = write_file(
            vault / "ML" / "Loss Functions.md",
            "# Loss Functions\n\nMeasures prediction error.\n",
        )
        orig_bytes = {
            note1: note1.read_bytes(),
            note2: note2.read_bytes(),
        }

        res_conn = run_cli("connect", str(vault), env=self.env)
        self.assertEqual(res_conn.returncode, 0, res_conn.stderr)
        conn_data = json.loads(res_conn.stdout)
        self.assertTrue(conn_data["ok"])
        self.assertEqual(conn_data["active_mode"], MODE_VAULT_NATIVE)
        self.assertEqual(conn_data["indexed_notes"], 2)
        self.assertTrue((vault / ".teachme" / "index.json").is_file())

        res_search = run_cli("search", str(vault), "--query", "Gradient Descent", env=self.env)
        self.assertEqual(res_search.returncode, 0, res_search.stderr)
        s_data = json.loads(res_search.stdout)
        self.assertGreaterEqual(s_data["total_matches"], 1)
        self.assertEqual(s_data["results"][0]["rel_path"], "ML/Gradient Descent.md")

        subtopics_file = self.tmp / "subtopics.json"
        write_file(
            subtopics_file,
            json.dumps(
                [
                    {
                        "slug": "01-loss-surface",
                        "title": "Loss Surface",
                        "depends_on": [],
                        "objective": "Understand objective landscapes",
                        "anchor": "A loss surface maps parameters to scalar error.",
                    }
                ]
            ),
        )
        res_init = run_cli(
            "init", str(vault), "--topic", "Gradient Descent", "--subtopics", str(subtopics_file),
            env=self.env,
        )
        self.assertEqual(res_init.returncode, 0, res_init.stderr)
        init_data = json.loads(res_init.stdout)
        sess_dir = Path(init_data["session_dir"])
        self.assertTrue(is_within_root(sess_dir, vault / ".teachme" / "sessions"))
        self.assertFalse((vault / "00-SESSION-STATE.md").exists())
        self.assertFalse((vault / "topics").exists())
        self.assertFalse((vault / "00-MOC-INDEX.md").exists())

        # Verify state, context, tick, flush work in isolated vault-native session
        res_state = run_cli("state", env=self.env)
        self.assertEqual(res_state.returncode, 0, res_state.stderr)
        st = json.loads(res_state.stdout)
        self.assertEqual(st["mode"], "vault-native")
        self.assertEqual(st["active_topic"], "topic-01")

        res_tick = run_cli("tick", "--topic", "01", "--cp", "1", "--status", "pass", env=self.env)
        self.assertEqual(res_tick.returncode, 0, res_tick.stderr)
        res_flush = run_cli("flush", "--topic", "01", "--note", "Gradient points uphill", env=self.env)
        self.assertEqual(res_flush.returncode, 0, res_flush.stderr)

        # Existing Obsidian notes must remain byte-for-byte untouched
        for path, expected in orig_bytes.items():
            self.assertEqual(path.read_bytes(), expected)

    def test_mode_detection_distinguishes_standalone_and_obsidian(self) -> None:
        obs = self.tmp / "Obs"
        write_file(obs / ".obsidian" / "app.json", "{}")
        self.assertEqual(detect_vault_mode(obs, config={})["mode"], MODE_VAULT_NATIVE)

        standalone = self.tmp / "StandaloneSession"
        write_file(standalone / "00-SESSION-STATE.md", "# Session State\n")
        write_file(standalone / "00-GRAPH.json", '{"nodes":{},"order":[]}\n')
        self.assertEqual(detect_vault_mode(standalone, config={})["mode"], MODE_STANDALONE)

    def test_malformed_yaml_and_redaction_safety(self) -> None:
        vault = self.tmp / "MalformedVault"
        write_file(vault / ".obsidian" / "app.json", "{}")
        write_file(vault / "Broken.md", "---\ntitle: [unclosed\n---\n# Broken\n\nStill searchable content.\n")
        idx = build_or_update_index(vault, full=True)
        self.assertEqual(idx["doc_count"], 1)
        hits = search_vault(vault, "searchable", index=idx)
        self.assertEqual(hits["total_matches"], 1)

        redacted = redact_sensitive({"api_key": "secret-123", "topic": "math"})
        self.assertEqual(redacted["api_key"], "<redacted>")
        self.assertEqual(redacted["topic"], "math")


if __name__ == "__main__":
    unittest.main()
