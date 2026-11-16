---
name: teachme-compare
description: Build a primary-source structural trade-off matrix contrasting two concepts, algorithms, or architectures. Usage: /teachme-compare <A> vs <B>
---

# `/teachme-compare` — Cross-Vault Structural Trade-Off Synthesis

Wrapper skill exposing the `compare` subcommand as a top-level slash command without duplicating core logic.

## 1. Argument Parsing
- Extract `<A>` and `<B>` from `$ARGUMENTS` around `vs` / `vs.` (or the text immediately following `/teachme-compare`).
- If either side is missing, ask a single clarifying question before proceeding.

## 2. Core Reference Resolution
Load these canonical instructions before comparing (checking local sibling paths first, then global skills directories):
1. **Core Operating Laws & LaTeX Hygiene:** `../teachme/SKILL.md` (fallback: `~/.gemini/antigravity/skills/teachme/SKILL.md` or `~/.claude/skills/teachme/SKILL.md`).
2. **Subcommand Workflow (`compare` §6):** `../teachme/references/SUBCOMMANDS.md` (fallback: `~/.gemini/antigravity/skills/teachme/references/SUBCOMMANDS.md`).
3. **Contrastive "Is vs. Is Not" & Formula Anatomy Standards (§4, §6):** `../teachme/references/STUDY-AND-GLOSSARY.md` (fallback: `~/.gemini/antigravity/skills/teachme/references/STUDY-AND-GLOSSARY.md`).

## 3. Execution Mandate
- Execute **`/teachme compare <A> vs <B>`** end-to-end: check `<VAULT_ROOT>/<a-slug>/` and `<VAULT_ROOT>/<b-slug>/` (running targeted primary-source research for any missing vault), and write `<VAULT_ROOT>/comparisons/<a-slug>-vs-<b-slug>.md`.
- Include the Executive Verdict, Side-by-Side Architecture & Contrastive "Is vs. Is Not" Matrix, Mathematical Contrast (pure LaTeX with `\mid` in tables, zero backticks), and bidirectional links inside both vaults' `00-MOC-INDEX.md`.
