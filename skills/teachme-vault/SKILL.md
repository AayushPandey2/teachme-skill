---
name: teachme-vault
description: "Connect and manage registered Obsidian vaults for isolated TeachMe learning state in .teachme/ and read-only source retrieval (no note creation). Usage: /teachme-vault <connect|vaults|use-vault|remove-vault|resolve-sources|mode|search|reindex|state> [args]"
---

# `/teachme-vault` — Multi-Vault Registry, Isolated State & Read-Only Lookup

## Arguments
- Parse subcommand (`connect`, `vaults`, `use-vault`, `remove-vault`, `resolve-sources`, `mode`, `search`, `reindex`, `state`) and arguments from `$ARGUMENTS`.
- If no subcommand is given, run `vault_cli.py vaults`, `vault_cli.py mode`, and `vault_cli.py state` (if connected) or ask ONE clarifying question for the Obsidian vault path.

## Load (Minimal)
Resolve `teachme/` at `../teachme/` first, then `~/.gemini/antigravity/skills/teachme/`:
1. `teachme/SKILL.md` (laws §A–§D)
2. `teachme/references/cmd-vault.md`
3. On demand only: `teachme/references/VAULT-NATIVE.md`

## Execute
Run the corresponding `vault_cli.py` subcommand. Never create, modify, reorganize, format, or validate study notes; if the user explicitly asks to create or edit persistent study notes, follow `teachme/references/NOTE-SKILL-HANDOFF.md`.
