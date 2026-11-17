---
name: teachme-vault
description: "Connect an existing Obsidian vault to isolate TeachMe learning state in .teachme/ and search notes read-only as teaching sources (no note creation). Usage: /teachme-vault <connect|mode|search|reindex|state> [args]"
---

# `/teachme-vault` — Obsidian State Isolation & Read-Only Lookup

## Arguments
- Parse subcommand (`connect`, `mode`, `search`, `reindex`, `state`) and arguments from `$ARGUMENTS`.
- If no subcommand is given, run `vault_cli.py mode` and `vault_cli.py state` (if connected) or ask ONE clarifying question for the Obsidian vault path.

## Load (Minimal)
Resolve `teachme/` at `../teachme/` first, then `~/.gemini/antigravity/skills/teachme/`:
1. `teachme/SKILL.md` (laws §A–§D)
2. `teachme/references/cmd-vault.md`
3. On demand only: `teachme/references/VAULT-NATIVE.md`

## Execute
Run the corresponding `vault_cli.py` subcommand (`connect`, `mode`, `search`, `reindex`, `state`). Never create, modify, format, or validate study notes; delegate study-note workflows to Scriptorium (`references/SCRIPTORIUM-HANDOFF.md`).
