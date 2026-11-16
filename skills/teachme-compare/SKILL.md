---
name: teachme-compare
description: "Build a primary-source structural trade-off matrix contrasting two concepts, algorithms, or architectures. Usage: /teachme-compare <A> vs <B>"
---

# `/teachme-compare` — Primary-Source Comparison Matrix

## Arguments
- Parse `<A> vs <B>` from `$ARGUMENTS` (or text after `/teachme-compare`).
- If the topic is missing: run `vault_cli.py state` to auto-select the active vault, else ask ONE question.

## Load (Minimal)
Resolve `teachme/` at `../teachme/` first, then `~/.gemini/antigravity/skills/teachme/`:
1. `teachme/SKILL.md` (laws §A–§D)
2. `teachme/references/cmd-compare.md`
3. On demand only: `references/RESEARCH-TOOLCHAIN.md`

## Execute
Follow `cmd-compare.md` end-to-end; finish writes with `vault_cli.py fix` -> `verify` (`errors: []`).
