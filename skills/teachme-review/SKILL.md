---
name: teachme-review
description: "Launch an interleaved spaced-repetition Socratic coaching session targeting weak spots logged in a /teachme vault. Usage: /teachme-review <topic>"
---

# `/teachme-review` — Interleaved Spaced-Repetition Coaching

## 1. Argument Parsing
- Extract `<topic>` from `$ARGUMENTS` (or the text immediately following `/teachme-review`).
- If missing, run `../teachme/scripts/vault_cli.py state` (or check `<VAULT_ROOT>/*/00-SESSION-STATE.md`) or ask 1 clarifying question.

## 2. Core Reference Resolution (Minimal Load)
Load ONLY these files (checking sibling `../teachme/` first, then `~/.gemini/antigravity/skills/teachme/` or `~/.claude/skills/teachme/`):
1. `../teachme/SKILL.md`
2. `../teachme/references/cmd-review.md`

## 3. Execution Mandate
- Follow `cmd-review.md` end-to-end inside `<VAULT_ROOT>/<topic-slug>/`: run `vault_cli.py state` & `graph`, load 1-hop neighbors (`--section L0-L1`) + active topic slice, log mid-lesson turns via `vault_cli.py tick`, and flush Markdown updates upon passing `[4/4]`.
