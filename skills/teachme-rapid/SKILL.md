---
name: teachme-rapid
description: "Notes-first rapid revision and active recall mode that retrieves bounded sections from existing vault notes and runs fast 1-question-per-turn testing, weak-spot prioritization, or direct Q&A using shared TeachMe learning state. Usage: /teachme-rapid <topic> [--mode recall|mcq|mixed|weak|qa|exam] [--questions N] [--minutes N] [--resume]"
---

# `/teachme-rapid` — Rapid Revision & Active Recall

## Arguments
- Parse `<topic>`, `--mode`, `--questions`, `--minutes`, `--vault`, `--session`, `--resume`, `--allow-web`, or `--allow-general` from `$ARGUMENTS` (or text after `/teachme-rapid`).
- Examples: `/teachme-rapid calculus`, `/teachme-rapid C pointers --minutes 10`, `/teachme-rapid machine learning --questions 20`, `/teachme-rapid matrices --mode recall`, `/teachme-rapid probability --mode mcq`, `/teachme-rapid DSA --mode mixed`, `/teachme-rapid --mode weak`, `/teachme-rapid --mode qa`, `/teachme-rapid --resume`.
- Rapid revision is **notes-first and notes-grounded by default**: never silently supplement missing vault coverage with general knowledge or web results.

## Load (Minimal)
Resolve `teachme/` at `../teachme/` first, then `~/.gemini/antigravity/skills/teachme/` (or `~/.claude/skills/teachme/` / `~/.agents/skills/teachme/`):
1. `teachme/SKILL.md` (laws §A–§D — never generate or edit study notes)
2. `teachme/references/cmd-rapid.md`
3. Do **not** load `VISUALS-AND-EXPERIMENTS.md` or full vault files unnecessarily.

## Execute
Follow `cmd-rapid.md` end-to-end using `vault_cli.py rapid-plan`, `vault_cli.py rapid-record` (or `assess`), and `vault_cli.py rapid-status`, keeping prompts crisp, asking one question per turn, and never creating or modifying study notes.
