---
name: teachme-feynman
description: "Test plain-English mastery of any concept by explaining it back with zero unstated jargon under Socratic probing. Usage: /teachme-feynman <concept>"
---

# `/teachme-feynman` — Feynman Reverse-Teaching Audit

## Arguments
- Parse `<concept>` (optionally `<topic> <subtopic>`) from `$ARGUMENTS` (or text after `/teachme-feynman`).
- If the topic is missing: run `vault_cli.py state` to auto-select the active vault, else ask ONE question.

## Load (Minimal)
Resolve `teachme/` at `../teachme/` first, then `~/.gemini/antigravity/skills/teachme/`:
1. `teachme/SKILL.md` (laws §A–§D)
2. `teachme/references/cmd-feynman.md`
3. On demand only: `references/RETENTION-AND-RECORDS.md` (§3 only)

## Execute
Follow `cmd-feynman.md` end-to-end; finish writes with `vault_cli.py fix` -> `verify` (`errors: []`).
