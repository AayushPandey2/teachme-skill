---
name: teachme-ingest
description: Absorb new PDFs, URLs, lecture notes, or raw dumps into an existing /teachme vault without overwriting mastered checkpoints. Usage: /teachme-ingest <topic> <source>
---

# `/teachme-ingest` — Source Ingestion & Non-Destructive Vault Merge

Wrapper skill exposing the `ingest` subcommand as a top-level slash command without duplicating core logic.

## 1. Argument Parsing
- Extract `<topic>` and `<source>` (URL, PDF, file path, or raw notes) from `$ARGUMENTS` (supporting both `<topic> <source>` and `<source> into <topic>` forms).
- If `<topic>` is missing, check `<VAULT_ROOT>/*/00-SESSION-STATE.md` for an active vault or ask a single clarifying question.

## 2. Core Reference Resolution
Load these canonical instructions before ingesting (checking local sibling paths first, then global skills directories):
1. **Core Operating Laws & Hygiene:** `../teachme/SKILL.md` (fallback: `~/.gemini/antigravity/skills/teachme/SKILL.md` or `~/.claude/skills/teachme/SKILL.md`).
2. **Subcommand Workflow (`ingest` §1):** `../teachme/references/SUBCOMMANDS.md` (fallback: `~/.gemini/antigravity/skills/teachme/references/SUBCOMMANDS.md`).
3. **8-Block Standard & `00-SESSION-STATE.md` Sync Rules:** `../teachme/references/STUDY-AND-GLOSSARY.md` (§6–7) and `../teachme/references/RETENTION-AND-RECORDS.md` (§1) (fallbacks in `~/.gemini/antigravity/skills/teachme/references/` or `~/.claude/skills/teachme/references/`).

## 3. Execution Mandate
- Execute **`/teachme ingest`** end-to-end inside `<VAULT_ROOT>/<topic-slug>/`, parsing the new source with inline `[Source]` citations and full Formula Anatomy Breakdowns.
- Flag conflicts under `## Contradictions & Version Deltas` in `02-DEEP-RESEARCH.md`, register new subtopics in `00-MOC-INDEX.md`, and sync `00-SESSION-STATE.md` (<60 lines) **without overwriting existing mastered `[x]` checkpoints**.
