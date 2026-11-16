---
name: teachme-notes-path
description: "View, change, or reset the folder path where /teachme saves your notes vault. Usage: /teachme-notes-path <folder-path>"
---

# `/teachme-notes-path` — Configure Vault Root Directory

## 1. Argument Parsing
- Extract optional argument from `$ARGUMENTS`: `<folder-path>`, `reset`, or *(empty)* to display active `<VAULT_ROOT>` and stored vaults.

## 2. Core Reference Resolution (Minimal Load)
Load ONLY these files (checking sibling `../teachme/` first, then `~/.gemini/antigravity/skills/teachme/` or `~/.claude/skills/teachme/`):
1. `../teachme/SKILL.md`
2. `../teachme/references/cmd-notes-path.md`

## 3. Execution Mandate
- Follow `cmd-notes-path.md` end-to-end: resolve/normalize path, verify write access, update `~/.teachme-config.json`, and never move existing vaults without explicit confirmation.
