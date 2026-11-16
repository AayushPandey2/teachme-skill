---
name: teachme-review
description: "Launch an interleaved spaced-repetition Socratic coaching session targeting weak spots logged in a /teachme vault. Usage: /teachme-review <topic>"
---

# `/teachme-review` — Interleaved Spaced-Repetition Coaching

## Arguments
- Parse `<topic>` from `$ARGUMENTS` (or text after `/teachme-review`).
- If the topic is missing: run `vault_cli.py state` to auto-select the active vault, else ask ONE question.

## Load (Minimal)
Resolve `teachme/` at `../teachme/` first, then `~/.gemini/antigravity/skills/teachme/`:
1. `teachme/SKILL.md` (laws §A–§D)
2. `teachme/references/cmd-review.md`
3. On demand only: `references/RETENTION-AND-RECORDS.md`

## Execute
Follow `cmd-review.md` end-to-end; finish writes with `vault_cli.py fix` -> `verify` (`errors: []`).
