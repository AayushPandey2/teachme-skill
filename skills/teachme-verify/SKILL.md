---
name: teachme-verify
description: Multi-pass audit and auto-repair of broken wikilinks, typed YAML edges, orphaned files, and malformed LaTeX across a /teachme vault. Usage: /teachme-verify <topic>
---

# `/teachme-verify` — Vault Integrity Audit & Auto-Repair

Wrapper skill exposing the `verify` (`audit`) subcommand as a top-level slash command without duplicating core logic.

## 1. Argument Parsing
- Extract `<topic>` from `$ARGUMENTS` (or the text immediately following `/teachme-verify`).
- If `<topic>` is missing, scan `~/notes/*/00-SESSION-STATE.md` for an active vault or ask a single clarifying question.

## 2. Core Reference Resolution
Load these canonical instructions before scanning or editing (checking local sibling paths first, then global skills directories):
1. **Core Operating Laws & LaTeX/Link Hygiene:** `../teachme/SKILL.md` (fallback: `~/.gemini/antigravity/skills/teachme/SKILL.md` or `~/.claude/skills/teachme/SKILL.md`).
2. **Subcommand Workflow (`verify` / `audit` §8):** `../teachme/references/SUBCOMMANDS.md` (fallback: `~/.gemini/antigravity/skills/teachme/references/SUBCOMMANDS.md`).
3. **8-Block Standard & 6-Point Critic Audit (§6):** `../teachme/references/STUDY-AND-GLOSSARY.md` (fallback: `~/.gemini/antigravity/skills/teachme/references/STUDY-AND-GLOSSARY.md`).

## 3. Execution Mandate
- Execute the 3-pass **`/teachme verify <topic>`** workflow end-to-end inside `~/notes/<topic-slug>/`.
- **Pass 1:** Audit and repair `[[wikilinks]]`, relative links, typed YAML semantic edges (`depends_on`, `unlocks`, `contrasts_with`, `fixes_failure_of`), orphaned files, `00-SESSION-STATE.md` (<60 lines), and `L1-ANCHOR`..`L5-WORKBOOK-AND-GRAPH` markers.
- **Pass 2 & 3:** Strip any backtick-wrapped LaTeX, fix raw `|` pipes inside table math (`\mid`), enforce the **6-Point Writer -> Critic Audit** on every `topics/*.md` file, re-run verification until 0 errors remain, and output the verification report table.
