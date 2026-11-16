---
name: teachme-ingest
description: "Absorb new PDFs, URLs, lecture notes, or raw dumps into an existing /teachme vault without overwriting mastered checkpoints. Usage: /teachme-ingest <topic> <source>"
---

# `/teachme-ingest` — Non-Destructive Source Ingestion

## Arguments
- Parse `<topic> <source>` or `<source> into <topic>` from `$ARGUMENTS` (or text after `/teachme-ingest`).
- If the topic is missing: run `vault_cli.py state` to auto-select the active vault, else ask ONE question.

## Load (Minimal)
Resolve `teachme/` at `../teachme/` first, then `~/.gemini/antigravity/skills/teachme/`:
1. `teachme/SKILL.md` (laws §A–§D)
2. `teachme/references/cmd-ingest.md`
3. On demand only: `references/STUDY-AND-GLOSSARY.md`, `references/RESEARCH-TOOLCHAIN.md`

## Execute
Follow `cmd-ingest.md` end-to-end; finish writes with `vault_cli.py fix` -> `verify` (`errors: []`).
