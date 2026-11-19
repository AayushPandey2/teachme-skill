---
name: teachme-code
description: "Interactive programming tutor that teaches coding through active writing, tracing, debugging, output prediction, and safe verification using shared TeachMe learning state. Usage: /teachme-code <language-or-topic> [--mode learn|practice|debug|trace|challenge|interview] [--level foundation|intermediate|advanced] [--minutes N] [--resume]"
---

# `/teachme-code` — Interactive Coding Tutor

## Arguments
- Parse `<language-or-topic>`, `--mode`, `--level`, `--minutes`, `--file`, `--session`, or `--resume` from `$ARGUMENTS` (or text after `/teachme-code`).
- Examples: `/teachme-code C pointers`, `/teachme-code Python recursion`, `/teachme-code C arrays --mode practice`, `/teachme-code Python two pointers --mode challenge`, `/teachme-code C --mode debug`, `/teachme-code DSA binary search --level intermediate`, `/teachme-code C functions --minutes 20`, `/teachme-code --resume`.
- If omitted and no active session exists: run `vault_cli.py code-plan --args "$ARGUMENTS"`, or ask ONE clarifying question.

## Load (Minimal)
Resolve `teachme/` at `../teachme/` first, then `~/.gemini/antigravity/skills/teachme/` (or `~/.claude/skills/teachme/` / `~/.agents/skills/teachme/`):
1. `teachme/SKILL.md` (laws §A–§D — never generate or edit study notes)
2. `teachme/references/cmd-code.md`
3. On demand only: `references/RETENTION-AND-RECORDS.md` (§3–§5) or `references/VISUALS-AND-EXPERIMENTS.md` (only when running `simulate --template c_pointers` / `sorting`)

## Execute
Follow `cmd-code.md` end-to-end using `vault_cli.py code-plan` and `vault_cli.py code-check` (and shared `assess` / `context` / `revise-curriculum`), presenting one challenge at a time, using progressive hints (0–4), requiring explicit authorization before local code execution, and never creating or editing study notes.
