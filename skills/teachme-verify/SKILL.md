---
name: teachme-verify
description: "Multi-pass audit and auto-repair of broken wikilinks, typed YAML edges, orphaned files, malformed LaTeX, and <details> blocks across a /teachme vault. Usage: /teachme-verify <topic>"
---

# `/teachme-verify` — Vault Integrity Audit & Auto-Repair

## Arguments
- Parse `<topic>` from `$ARGUMENTS` (or text after `/teachme-verify`).
- If the topic is missing: run `vault_cli.py state` to auto-select the active vault, else ask ONE question.

## Load (Minimal)
Resolve `teachme/` at `../teachme/` first, then `~/.gemini/antigravity/skills/teachme/`:
1. `teachme/SKILL.md` (laws §A–§D)
2. `teachme/references/cmd-verify.md`
3. Nothing else unless the command file names it.

## Execute
Follow `cmd-verify.md` end-to-end; finish writes with `vault_cli.py fix` -> `verify` (`errors: []`).
