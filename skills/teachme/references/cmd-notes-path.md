# Command: `/teachme-notes-path [path|reset]` *(alias: `/teachme notes-path [path|reset]`)*

View, change, or reset `<VAULT_ROOT>` in `~/.teachme-config.json` (defaulting to `~/notes` if absent or unset).

## Execution Sequence
1. **Mode A — `<path>` Provided (`/teachme-notes-path <path>`):**
   - Expand `~`, `$HOME`, `%USERPROFILE%`, or `$env:USERPROFILE` and normalize slashes cleanly.
   - Create the target directory if missing (`mkdir -p` / `New-Item -ItemType Directory -Force`) and verify write access before writing config.
   - Check the previous `<OLD_VAULT_ROOT>`: if existing topic vaults exist there, display both `<OLD_VAULT_ROOT>` and `<NEW_VAULT_ROOT>` and ask whether to copy/move them or keep them separate (**never** move or delete files without explicit confirmation).
   - Write `~/.teachme-config.json`:
     ```json
     {
       "notes_root": "<normalized-path>",
       "updated_at": "<YYYY-MM-DD>"
     }
     ```
   - Confirm the newly active `<VAULT_ROOT>` clearly.
2. **Mode B — No Argument Provided (`/teachme-notes-path`):**
   - Read `~/.teachme-config.json` (or note default `~/notes`), print active `<VAULT_ROOT>`, and list all topic vaults (plus `comparisons/`) stored inside it.
3. **Mode C — `reset` Provided (`/teachme-notes-path reset`):**
   - Reset `notes_root` in `~/.teachme-config.json` back to `~/notes` (`updated_at: "<YYYY-MM-DD>"`) and confirm without deleting files in the previous custom folder.
