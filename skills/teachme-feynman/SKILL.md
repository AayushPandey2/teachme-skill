---
name: teachme-feynman
description: Test plain-English mastery of any concept by explaining it back with zero unstated jargon under Socratic probing. Usage: /teachme-feynman <concept>
---

# `/teachme-feynman` — Reverse-Teaching Mastery Audit

Wrapper skill exposing the `feynman` subcommand as a top-level slash command without duplicating core logic.

## 1. Argument Parsing
- Extract `<concept>` (and optional `<topic>` / `[subtopic]`) from `$ARGUMENTS` (or the text immediately following `/teachme-feynman`).
- If ambiguous, check `<VAULT_ROOT>/*/00-SESSION-STATE.md` for an active vault or ask a single clarifying question.

## 2. Core Reference Resolution
Load these canonical instructions before auditing (checking local sibling paths first, then global skills directories):
1. **Core Operating Laws:** `../teachme/SKILL.md` (fallback: `~/.gemini/antigravity/skills/teachme/SKILL.md` or `~/.claude/skills/teachme/SKILL.md`).
2. **Subcommand Workflow (`feynman` §4):** `../teachme/references/SUBCOMMANDS.md` (fallback: `~/.gemini/antigravity/skills/teachme/references/SUBCOMMANDS.md`).
3. **Anti-Spoiler Productive Struggle & Learning Records (§3, §5):** `../teachme/references/RETENTION-AND-RECORDS.md` (fallback: `~/.gemini/antigravity/skills/teachme/references/RETENTION-AND-RECORDS.md`).

## 3. Execution Mandate
- Execute **`/teachme feynman`** end-to-end: prompt the user to explain `<concept>` and its governing formula(s) from scratch in plain English with zero unstated jargon.
- Grade strictly across the 4 axes (Plain-English Clarity, First-Principles Accuracy, Formula Intuition, Edge-Case Awareness) while enforcing the **Anti-Spoiler Productive Struggle Rule** (probe gaps with surgical sub-questions rather than immediately giving away the answer).
- Record the outcome in `learning-records/000N-feynman-<slug>.md` and update `00-MOC-INDEX.md` / `00-SESSION-STATE.md` if a subtopic passes.
