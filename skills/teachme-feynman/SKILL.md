---
name: teachme-feynman
description: "Test plain-English mastery of any concept by explaining it back with zero unstated jargon under Socratic probing. Usage: /teachme-feynman <concept>"
---

# `/teachme-feynman` — Reverse-Teaching Mastery Audit

## 1. Argument Parsing
- Extract `<concept>` (and optional `<topic>` / `[subtopic]`) from `$ARGUMENTS` (or the text immediately following `/teachme-feynman`).
- If ambiguous, run `../teachme/scripts/vault_cli.py state` (or check `<VAULT_ROOT>/*/00-SESSION-STATE.md`) or ask 1 clarifying question.

## 2. Core Reference Resolution (Minimal Load)
Load ONLY these files (checking sibling `../teachme/` first, then `~/.gemini/antigravity/skills/teachme/` or `~/.claude/skills/teachme/`):
1. `../teachme/SKILL.md`
2. `../teachme/references/cmd-feynman.md`

## 3. Execution Mandate
- Follow `cmd-feynman.md` end-to-end: slice only the target subtopic via `vault_cli.py slice`, grade across the 4 Feynman axes using Anti-Spoiler probing, log `learning-records/000N-feynman-<slug>.md`, and tick mastery via `vault_cli.py tick` if passed.
