---
name: teachme-ingest
description: "Absorb new PDFs, URLs, lecture notes, or raw dumps into an existing /teachme vault without overwriting mastered checkpoints. Usage: /teachme-ingest <topic> <source>"
---

# `/teachme-ingest` — Source Ingestion & Non-Destructive Vault Merge

## 1. Argument Parsing
- Extract `<topic>` and `<source>` from `$ARGUMENTS` (supporting both `<topic> <source>` and `<source> into <topic>`).
- If `<topic>` is missing, run `../teachme/scripts/vault_cli.py state` (or check `<VAULT_ROOT>/*/00-SESSION-STATE.md`) or ask 1 clarifying question.

## 2. Core Reference Resolution (Minimal Load)
Load ONLY these files (checking sibling `../teachme/` first, then `~/.gemini/antigravity/skills/teachme/` or `~/.claude/skills/teachme/`):
1. `../teachme/SKILL.md`
2. `../teachme/references/cmd-ingest.md`
3. `../teachme/references/subtopic-8block.md` *(for Formula Anatomy & 8-Block Subtopic templates when writing new notes)*

## 3. Execution Mandate
- Follow `cmd-ingest.md` end-to-end inside `<VAULT_ROOT>/<topic-slug>/`: flag contradictions, preserve mastered `[x]` checkpoints, sync `00-SESSION-STATE.md`, and run `vault_cli.py graph` + `verify`.
