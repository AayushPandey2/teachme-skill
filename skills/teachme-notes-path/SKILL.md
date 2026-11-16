---
name: teachme-notes-path
description: View, change, or reset the folder path where /teachme saves your notes vault. Usage: /teachme-notes-path <folder-path>
---

# `/teachme-notes-path` — Configure Vault Root Directory

Wrapper skill exposing the `notes-path` configuration workflow as a top-level slash command without duplicating core logic.

## 1. Argument Parsing
- Extract the optional argument from `$ARGUMENTS` (or the text immediately following `/teachme-notes-path`):
  - `<folder-path>` → change `<VAULT_ROOT>` to that folder.
  - `reset` → reset `notes_root` in `~/.teachme-config.json` back to `~/notes`.
  - *(empty)* → display the currently active `<VAULT_ROOT>` and list all topic vaults inside it.

## 2. Core Reference Resolution
Load these canonical instructions before making any config or directory changes (checking local sibling paths first, then global skills directories):
1. **Core Operating Laws & Path Resolution:** `../teachme/SKILL.md` (fallback: `~/.gemini/antigravity/skills/teachme/SKILL.md` or `~/.claude/skills/teachme/SKILL.md`).
2. **Subcommand Workflow (`notes-path` §9):** `../teachme/references/SUBCOMMANDS.md` (fallback: `~/.gemini/antigravity/skills/teachme/references/SUBCOMMANDS.md`).

## 3. Execution Mandate
- Execute the **`/teachme notes-path`** workflow end-to-end: normalize & expand the path, create the directory if missing and verify write access, save `{"notes_root": "<normalized-path>", "updated_at": "<YYYY-MM-DD>"}` into `~/.teachme-config.json`, and never copy/move existing vaults from a previous root without explicit user confirmation.
