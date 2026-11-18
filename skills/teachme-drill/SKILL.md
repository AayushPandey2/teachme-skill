---
name: teachme-drill
description: "Generate and grade live Tier 1 (recall), Tier 2 (multi-step), or Tier 3 (adversarial edge-case) practice problems interactively for a /teachme topic. Usage: /teachme-drill <topic> [1|2|3]"
---

# `/teachme-drill` — Live Tiered Practice Drills

## Arguments
- Parse `<topic> [1|2|3]` from `$ARGUMENTS` (or text after `/teachme-drill`).
- If the topic is missing: run `vault_cli.py state` to auto-select the active session, else ask ONE question.

## Load (Minimal)
Resolve `teachme/` at `../teachme/` first, then `~/.gemini/antigravity/skills/teachme/`:
1. `teachme/SKILL.md` (laws §A–§D)
2. `teachme/references/cmd-drill.md`
3. On demand only: `references/RETENTION-AND-RECORDS.md` (§3–§5 only)

## Execute
Follow `cmd-drill.md` end-to-end; log assessment evidence (`--result` and `--assistance`) via `vault_cli.py assess` (or `tick`) and `learning-records/` without writing study notes.
