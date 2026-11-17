---
name: teachme-vault
description: "Connect, discover, profile, search, plan, generate, and audit notes inside an existing Obsidian vault in Vault-Native Mode. Usage: /teachme-vault <subcommand> [args]"
---

# `/teachme-vault` — Obsidian Vault-Native Integration

## Arguments
- Parse subcommand (`connect`, `discover`, `profile`, `search`, `plan`, `generate`, `apply`, `audit`, `mode`, `reindex`) and arguments from `$ARGUMENTS`.
- If no subcommand is given, run `vault_cli.py mode` and `vault_cli.py profile` (if connected) or ask ONE clarifying question for the Obsidian vault path.

## Load (Minimal)
Resolve `teachme/` at `../teachme/` first, then `~/.gemini/antigravity/skills/teachme/`:
1. `teachme/SKILL.md` (laws §A–§D)
2. `teachme/references/cmd-vault.md`
3. `teachme/references/VAULT-NATIVE.md` when generating or planning notes.

## Execute
Run the corresponding `vault_cli.py` subcommand (`connect`, `discover`, `profile`, `reindex`, `search`, `plan`, `generate`, `apply`, `audit`, `mode`). Use `--dry-run` / `plan` to preview tags, MOC updates, and Mermaid diagrams, then `apply --plan <id>` or `generate --apply`. Never modify user-authored notes outside explicit `--extend --apply` or targeted MOC insertions with backup. Finish vault-native writes with `vault_cli.py audit`.
