---
name: teachme-expand
description: "Deepen pre-existing /teachme notes in place to the 8-Block Mastery Standard and generate dedicated files for missing related subtopics. Usage: /teachme-expand <topic>"
---

# `/teachme-expand` — Vault Expansion & 8-Block Deepening

## 1. Argument Parsing
- Extract `<topic>` from `$ARGUMENTS` (or the text immediately following `/teachme-expand`).
- If missing, run `../teachme/scripts/vault_cli.py state` (or check `<VAULT_ROOT>/*/00-SESSION-STATE.md`) to locate the active vault, or ask 1 clarifying question.

## 2. Core Reference Resolution (Minimal Load)
Load ONLY these files (checking sibling `../teachme/` first, then `~/.gemini/antigravity/skills/teachme/` or `~/.claude/skills/teachme/`):
1. `../teachme/SKILL.md`
2. `../teachme/references/cmd-expand.md`
3. `../teachme/references/subtopic-8block.md` *(for the 8-Block Subtopic Standard & 7-Point Critic Audit)*

## 3. Execution Mandate
- Follow `cmd-expand.md` end-to-end inside `<VAULT_ROOT>/<topic-slug>/`: offload graph/state/verify to `vault_cli.py`, enforce the 8-Block Standard + 6-Point Critic Audit on every saved `topics/*.md` file, preserve `[x]` progress, and verify 0 errors before finishing.
