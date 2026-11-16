---
name: teachme-distill
description: Compress a /teachme vault into a high-density 1-page 09-CHEAT-SHEET.md and update the 08-FLASHCARDS.md spaced-repetition deck. Usage: /teachme-distill <topic>
---

# `/teachme-distill` — Executive Cheat Sheet & Flashcard Roll-Up

Wrapper skill exposing the `distill` subcommand as a top-level slash command without duplicating core logic.

## 1. Argument Parsing
- Extract `<topic>` from `$ARGUMENTS` (or the text immediately following `/teachme-distill`).
- If `<topic>` is missing, scan `<VAULT_ROOT>/*/00-SESSION-STATE.md` for an active vault or ask a single clarifying question.

## 2. Core Reference Resolution
Load these canonical instructions before distilling (checking local sibling paths first, then global skills directories):
1. **Core Operating Laws & LaTeX Hygiene:** `../teachme/SKILL.md` (fallback: `~/.gemini/antigravity/skills/teachme/SKILL.md` or `~/.claude/skills/teachme/SKILL.md`).
2. **Subcommand Workflow (`distill` §2):** `../teachme/references/SUBCOMMANDS.md` (fallback: `~/.gemini/antigravity/skills/teachme/references/SUBCOMMANDS.md`).
3. **Cheat Sheet & Flashcard Templates (§7–8):** `../teachme/references/STUDY-AND-GLOSSARY.md` (fallback: `~/.gemini/antigravity/skills/teachme/references/STUDY-AND-GLOSSARY.md`).

## 3. Execution Mandate
- Execute **`/teachme distill <topic>`** end-to-end inside `<VAULT_ROOT>/<topic-slug>/`.
- Distill core axioms, critical formulas (with table-safe `\mid` delimiters and zero backtick-wrapped math), decision matrix, and top failure modes into `09-CHEAT-SHEET.md`.
- Refresh `08-FLASHCARDS.md` with any newly synthesized invariants/formula cloze cards and ensure `[[09-CHEAT-SHEET]]` is linked in `00-MOC-INDEX.md`.
