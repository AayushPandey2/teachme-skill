---
name: teachme-drill
description: Generate and grade Tier 1 (recall), Tier 2 (multi-step), or Tier 3 (adversarial edge-case) practice problems for a /teachme topic. Usage: /teachme-drill <topic> [1|2|3]
---

# `/teachme-drill` — Tiered Practice Generator & Grader

## 1. Argument Parsing
- Extract `<topic>` and optional tier (`1`, `2`, `3`, or `--tier 1|2|3`) from `$ARGUMENTS` (or the text immediately following `/teachme-drill`).
- If missing, run `../teachme/scripts/vault_cli.py state` (or check `<VAULT_ROOT>/*/00-SESSION-STATE.md`) or ask 1 clarifying question.

## 2. Core Reference Resolution (Minimal Load)
Load ONLY these files (checking sibling `../teachme/` first, then `~/.gemini/antigravity/skills/teachme/` or `~/.claude/skills/teachme/`):
1. `../teachme/SKILL.md`
2. `../teachme/references/cmd-drill.md`

## 3. Execution Mandate
- Follow `cmd-drill.md` end-to-end inside `<VAULT_ROOT>/<topic-slug>/`: check `vault_cli.py state` + `07-PRACTICE-PROBLEMS.md`, slice relevant subtopic sections via `vault_cli.py slice`, grade 1 problem per turn without spoilers, and append solved drills to `07-PRACTICE-PROBLEMS.md`.
