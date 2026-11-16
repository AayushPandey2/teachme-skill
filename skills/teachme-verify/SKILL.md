---
name: teachme-verify
description: Multi-pass audit and auto-repair of broken wikilinks, typed YAML edges, orphaned files, and malformed LaTeX across a /teachme vault. Usage: /teachme-verify <topic>
---

# `/teachme-verify` — Vault Integrity Audit & Auto-Repair

## 1. Argument Parsing
- Extract `<topic>` from `$ARGUMENTS` (or the text immediately following `/teachme-verify`).
- If missing, run `../teachme/scripts/vault_cli.py state` (or check `<VAULT_ROOT>/*/00-SESSION-STATE.md`) to locate the active vault, or ask 1 clarifying question.

## 2. Core Reference Resolution (Minimal Load)
Load ONLY these files (checking sibling `../teachme/` first, then `~/.gemini/antigravity/skills/teachme/` or `~/.claude/skills/teachme/`):
1. `../teachme/SKILL.md`
2. `../teachme/references/cmd-verify.md`

## 3. Execution Mandate
- Follow `cmd-verify.md` end-to-end inside `<VAULT_ROOT>/<topic-slug>/`: run `../teachme/scripts/vault_cli.py graph` + `verify`, edit ONLY the flagged lines/files, re-run `vault_cli.py verify` until 0 errors remain, and output the verification report table.
