---
name: teachme-expand
description: Deepen pre-existing /teachme notes in place to the 8-Block Mastery Standard and generate dedicated files for missing related subtopics. Usage: /teachme-expand <topic>
---

# `/teachme-expand` — Vault Expansion & 8-Block Deepening

Wrapper skill exposing the `expand` subcommand as a top-level slash command without duplicating core logic.

## 1. Argument Parsing
- Extract `<topic>` from `$ARGUMENTS` (or the text immediately following `/teachme-expand`).
- If `<topic>` is missing, scan `~/notes/*/00-SESSION-STATE.md` for an active vault or ask a single clarifying question.

## 2. Core Reference Resolution
Load these canonical instructions before making any edits (checking local sibling paths first, then global skills directories):
1. **Core Operating Laws & Hygiene:** `../teachme/SKILL.md` (fallback: `~/.gemini/antigravity/skills/teachme/SKILL.md` or `~/.claude/skills/teachme/SKILL.md`).
2. **Subcommand Workflow (`expand` §7):** `../teachme/references/SUBCOMMANDS.md` (fallback: `~/.gemini/antigravity/skills/teachme/references/SUBCOMMANDS.md`).
3. **8-Block Standard & 6-Point Critic Audit (§6):** `../teachme/references/STUDY-AND-GLOSSARY.md` (fallback: `~/.gemini/antigravity/skills/teachme/references/STUDY-AND-GLOSSARY.md`).

## 3. Execution Mandate
- Execute the **`/teachme expand <topic>`** workflow end-to-end inside `~/notes/<topic-slug>/`.
- Upgrade shallow `topics/*.md` files in place and generate missing subtopics using the full **8-Block Subtopic Note Standard** (`L1-ANCHOR`..`L5-WORKBOOK-AND-GRAPH`, Contrastive "Is vs. Is Not" table, Python/NumPy `assert` verification snippet, typed YAML semantic edges).
- Run and pass the **Mandatory 6-Point Writer -> Critic Audit** before saving every modified or created `topics/*.md` file, preserve existing `[x]` progress, and update `00-MOC-INDEX.md` and `00-SESSION-STATE.md` (<60 lines).
