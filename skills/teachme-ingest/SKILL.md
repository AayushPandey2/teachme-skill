---
name: teachme-ingest
description: "Absorb PDFs, URLs, lecture transcripts, or notes into TeachMe lesson context and curriculum state without modifying study notes or overwriting mastered checkpoints. Usage: /teachme-ingest <topic> <source>"
---

# `/teachme-ingest` — Non-Destructive Source Ingestion for Teaching

## Arguments
- Parse `<topic> <source>` or `<source> into <topic>` from `$ARGUMENTS` (or text after `/teachme-ingest`).
- If the topic is missing: run `vault_cli.py state` to auto-select the active session, else ask ONE question.

## Load (Minimal)
Resolve `teachme/` at `../teachme/` first, then `~/.gemini/antigravity/skills/teachme/`:
1. `teachme/SKILL.md` (laws §A–§D)
2. `teachme/references/cmd-ingest.md`
3. On demand only: `references/RESEARCH-TOOLCHAIN.md`

## Execute
Follow `cmd-ingest.md` end-to-end; update operational state only and finish with `vault_cli.py validate-state`.
