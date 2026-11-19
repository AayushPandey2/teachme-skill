---
name: teachme-notes-path
description: "View, change, or reset the standalone learning-state directory (~/.teachme-config.json) used by /teachme sessions. Usage: /teachme-notes-path [folder-path|reset]"
---

# `/teachme-notes-path` — Configure Standalone Learning-State Root

## Arguments
- Parse `<folder-path>`, `reset`, or empty (show active root) from `$ARGUMENTS` (or text after `/teachme-notes-path`).

## Load (Minimal)
Resolve `teachme/` at `../teachme/` first, then `~/.gemini/antigravity/skills/teachme/`:
1. `teachme/SKILL.md` (laws §A–§D)
2. `teachme/references/cmd-notes-path.md`
3. Nothing else unless the command file names it.

## Execute
Follow `cmd-notes-path.md` end-to-end.
