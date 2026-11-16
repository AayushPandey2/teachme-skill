---
name: teachme-expand
description: "Deepen pre-existing /teachme notes in place to the 7-Section Mastery Standard and generate dedicated files for missing related subtopics. Usage: /teachme-expand <topic>"
---

# `/teachme-expand` — Vault Expansion & Deepening

## Arguments
- Parse `<topic>` from `$ARGUMENTS` (or text after `/teachme-expand`).
- If the topic is missing: run `vault_cli.py state` to auto-select the active vault, else ask ONE question.

## Load (Minimal)
Resolve `teachme/` at `../teachme/` first, then `~/.gemini/antigravity/skills/teachme/`:
1. `teachme/SKILL.md` (laws §A–§D)
2. `teachme/references/cmd-expand.md`
3. On demand only: `references/STUDY-AND-GLOSSARY.md`

## Execute
Follow `cmd-expand.md` end-to-end; finish writes with `vault_cli.py fix` -> `verify` (`errors: []`).
