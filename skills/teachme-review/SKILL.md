---
name: teachme-review
description: Launch an interleaved spaced-repetition Socratic coaching session targeting weak spots logged in a /teachme vault. Usage: /teachme-review <topic>
---

# `/teachme-review` — Interleaved Spaced-Repetition Coaching

Wrapper skill exposing the `review` subcommand as a top-level slash command without duplicating core logic.

## 1. Argument Parsing
- Extract `<topic>` from `$ARGUMENTS` (or the text immediately following `/teachme-review`).
- If `<topic>` is missing, scan `~/notes/*/00-SESSION-STATE.md` for an active vault or ask a single clarifying question.

## 2. Core Reference Resolution
Load these canonical instructions before starting the review loop (checking local sibling paths first, then global skills directories):
1. **Core Operating Laws & Progressive Disclosure:** `../teachme/SKILL.md` (fallback: `~/.gemini/antigravity/skills/teachme/SKILL.md` or `~/.claude/skills/teachme/SKILL.md`).
2. **Subcommand Workflow (`review` §3):** `../teachme/references/SUBCOMMANDS.md` (fallback: `~/.gemini/antigravity/skills/teachme/references/SUBCOMMANDS.md`).
3. **Hybrid Discovery + `I Do / We Do / You Do` Loop (§1–6):** `../teachme/references/RETENTION-AND-RECORDS.md` (fallback: `~/.gemini/antigravity/skills/teachme/references/RETENTION-AND-RECORDS.md`).

## 3. Execution Mandate
- Read `00-SESSION-STATE.md` (<60 lines) FIRST, then inspect `00-MOC-INDEX.md` and `learning-records/` using `L0 + L1` disclosure for prerequisites and full `L2` content only for the active weak/unchecked subtopic.
- Run the interleaved spaced-repetition Socratic coaching loop (`I Do / We Do / You Do`, 1 question per turn, **Strict Anti-Spoiler Rule** with drop-down 1-number micro-steps on errors).
- Persist mastered `[x]` checkboxes in `00-MOC-INDEX.md`, update `00-SESSION-STATE.md`, and log breakthroughs in `learning-records/000N-<slug>.md`.
