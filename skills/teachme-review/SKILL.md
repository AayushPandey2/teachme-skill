---
name: teachme-review
description: "Launch an interleaved spaced-repetition Socratic coaching session targeting weak spots logged in TeachMe learning state. Usage: /teachme-review <topic>"
---

# `/teachme-review` — Interleaved Spaced-Repetition Coaching

## Arguments
- Parse `<topic>` from `$ARGUMENTS` (or text after `/teachme-review`).
- If the topic is missing: run `vault_cli.py state` to auto-select the active session, else ask ONE question.

## Load (Minimal)
Resolve `teachme/` at `../teachme/` first, then `~/.gemini/antigravity/skills/teachme/`:
1. `teachme/SKILL.md` (laws §A–§D)
2. `teachme/references/cmd-review.md`
3. On demand only: `references/RETENTION-AND-RECORDS.md`

## Execute
Follow `cmd-review.md` end-to-end; persist checkpoint evidence via `vault_cli.py tick` / `flush` and `learning-records/` without modifying study notes.
