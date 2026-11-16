---
name: teachme-distill
description: "Compress a /teachme vault into a high-density 1-page 09-CHEAT-SHEET.md and update the 08-FLASHCARDS.md spaced-repetition deck. Usage: /teachme-distill <topic>"
---

# `/teachme-distill` — Cheat Sheet & Flashcard Distillation

## Arguments
- Parse `<topic>` from `$ARGUMENTS` (or text after `/teachme-distill`).
- If the topic is missing: run `vault_cli.py state` to auto-select the active vault, else ask ONE question.

## Load (Minimal)
Resolve `teachme/` at `../teachme/` first, then `~/.gemini/antigravity/skills/teachme/`:
1. `teachme/SKILL.md` (laws §A–§D)
2. `teachme/references/cmd-distill.md`
3. On demand only: `references/STUDY-AND-GLOSSARY.md` (§4 only)

## Execute
Follow `cmd-distill.md` end-to-end; finish writes with `vault_cli.py fix` -> `verify` (`errors: []`).
