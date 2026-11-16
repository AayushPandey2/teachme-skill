---
name: teachme-drill
description: Generate and grade Tier 1 (recall), Tier 2 (multi-step), or Tier 3 (adversarial edge-case) practice problems for a /teachme topic. Usage: /teachme-drill <topic> [1|2|3]
---

# `/teachme-drill` — Tiered Practice Generator & Grader

Wrapper skill exposing the `drill` subcommand as a top-level slash command without duplicating core logic.

## 1. Argument Parsing
- Extract `<topic>` and optional tier (`1`, `2`, `3`, or `--tier 1|2|3`) from `$ARGUMENTS` (or the text immediately following `/teachme-drill`).
- If `<topic>` is missing, scan `~/notes/*/00-SESSION-STATE.md` for an active vault or ask a single clarifying question.

## 2. Core Reference Resolution
Load these canonical instructions before generating drills (checking local sibling paths first, then global skills directories):
1. **Core Operating Laws & LaTeX Hygiene:** `../teachme/SKILL.md` (fallback: `~/.gemini/antigravity/skills/teachme/SKILL.md` or `~/.claude/skills/teachme/SKILL.md`).
2. **Subcommand Workflow (`drill` §5):** `../teachme/references/SUBCOMMANDS.md` (fallback: `~/.gemini/antigravity/skills/teachme/references/SUBCOMMANDS.md`).
3. **Formula Anatomy & Zero-Skip Walkthrough Standards (§4, §6):** `../teachme/references/STUDY-AND-GLOSSARY.md` (fallback: `~/.gemini/antigravity/skills/teachme/references/STUDY-AND-GLOSSARY.md`).

## 3. Execution Mandate
- Read `07-PRACTICE-PROBLEMS.md` (if present) and `00-SESSION-STATE.md` to avoid duplicate problems and calibrate to the active ZPD tier.
- Present **one problem at a time** (Tier 1 recall/substitution, Tier 2 multi-step synthesis, or Tier 3 adversarial edge cases), grade step-by-step reasoning without spoilers on errors, and append solved problems with full step-by-step solutions into `~/notes/<topic-slug>/07-PRACTICE-PROBLEMS.md`.
