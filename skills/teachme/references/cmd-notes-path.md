# `/teachme-notes-path [path|reset]`

View, change, or reset `<VAULT_ROOT>` (`SKILL.md §A`).

## Modes
1. **`<path>`:** expand `~`, `$HOME`, `%USERPROFILE%`, `$env:USERPROFILE`; normalize slashes; create the folder if missing and confirm write access. If vaults exist at the old root, show both roots and ask whether to copy/move or keep separate — **never move or delete without explicit confirmation**. Then write:

   ```json
   {"notes_root": "<normalized-path>", "updated_at": "<YYYY-MM-DD>"}
   ```

2. **No argument:** print the active `<VAULT_ROOT>` (config or default `~/notes`) and list its topic vaults plus `comparisons/`.
3. **`reset`:** set `notes_root` back to `~/notes` (update `updated_at`); never delete files in the old folder.

Confirm the active root in one line.
