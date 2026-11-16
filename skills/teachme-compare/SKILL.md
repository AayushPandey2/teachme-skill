---
name: teachme-compare
description: "Build a primary-source structural trade-off matrix contrasting two concepts, algorithms, or architectures. Usage: /teachme-compare <A> vs <B>"
---

# `/teachme-compare` — Cross-Vault Structural Trade-Off Synthesis

## 1. Argument Parsing
- Extract `<A>` and `<B>` from `$ARGUMENTS` around `vs` / `vs.` (or the text immediately following `/teachme-compare`).
- If either side is missing, ask 1 clarifying question before proceeding.

## 2. Core Reference Resolution (Minimal Load)
Load ONLY these files (checking sibling `../teachme/` first, then `~/.gemini/antigravity/skills/teachme/` or `~/.claude/skills/teachme/`):
1. `../teachme/SKILL.md`
2. `../teachme/references/cmd-compare.md`

## 3. Execution Mandate
- Follow `cmd-compare.md` end-to-end: inspect existing vaults via `vault_cli.py slice --section L0-L1` (or research missing sides), write `<VAULT_ROOT>/comparisons/<a-slug>-vs-<b-slug>.md`, link both `00-MOC-INDEX.md` files, and run `vault_cli.py verify`.
