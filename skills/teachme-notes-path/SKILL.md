---
name: teachme-notes-path
description: "View, change, or reset the folder path where /teachme saves your notes vault. Usage: /teachme-notes-path <folder-path>"
---

# `/teachme-notes-path` — Configure Vault Root

## Arguments
- Parse `<folder-path>`, `reset`, or empty (show active root) from `$ARGUMENTS` (or text after `/teachme-notes-path`).
- If the topic is missing: run `vault_cli.py state` to auto-select the active vault, else ask ONE question.

## Load (Minimal)
Resolve `teachme/` at `../teachme/` first, then `~/.gemini/antigravity/skills/teachme/`:
1. `teachme/SKILL.md` (laws §A–§D)
2. `teachme/references/cmd-notes-path.md`
3. Nothing else unless the command file names it.

## Execute
Follow `cmd-notes-path.md` end-to-end; finish writes with `vault_cli.py fix` -> `verify` (`errors: []`).
