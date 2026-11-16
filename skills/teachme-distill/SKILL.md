---
name: teachme-distill
description: Compress a /teachme vault into a high-density 1-page 09-CHEAT-SHEET.md and update the 08-FLASHCARDS.md spaced-repetition deck. Usage: /teachme-distill <topic>
---

# `/teachme-distill` — Executive Cheat Sheet & Flashcard Roll-Up

## 1. Argument Parsing
- Extract `<topic>` from `$ARGUMENTS` (or the text immediately following `/teachme-distill`).
- If missing, run `../teachme/scripts/vault_cli.py state` (or check `<VAULT_ROOT>/*/00-SESSION-STATE.md`) or ask 1 clarifying question.

## 2. Core Reference Resolution (Minimal Load)
Load ONLY these files (checking sibling `../teachme/` first, then `~/.gemini/antigravity/skills/teachme/` or `~/.claude/skills/teachme/`):
1. `../teachme/SKILL.md`
2. `../teachme/references/cmd-distill.md`

## 3. Execution Mandate
- Follow `cmd-distill.md` end-to-end inside `<VAULT_ROOT>/<topic-slug>/`: slice topic anchors via `vault_cli.py slice`, build the 4-section `09-CHEAT-SHEET.md`, update `08-FLASHCARDS.md`, link `[[09-CHEAT-SHEET]]` in `00-MOC-INDEX.md`, and run `vault_cli.py verify`.
