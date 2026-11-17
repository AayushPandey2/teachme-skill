# `/teachme-notes-path [path|reset]`

View, change, or reset TeachMe's standalone learning-state root (`notes_root` in `~/.teachme-config.json`, `SKILL.md §A`). This setting controls where standalone TeachMe session state lives and does **not** configure Scriptorium's study-note vault (`SCRIPTORIUM_VAULT_PATH` or `~/.scriptorium-config.json`). For connecting an existing Obsidian vault in Vault-Native Mode, use `/teachme-vault connect <vault-path>`.

## Modes
1. **`<path>`:** Expand `~`, `$HOME`, `%USERPROFILE%`, `$env:USERPROFILE`; normalize slashes; create the folder if missing and confirm write access.
   - If `<path>/.obsidian/` exists, ask whether to connect it in **Vault-Native Mode** (`vault_cli.py connect <path>`) or keep `notes_root` for standalone session directories — never restructure an existing Obsidian vault.
   - If standalone sessions exist at the old root, show both roots and ask whether to copy/move or keep separate — **never move or delete without explicit confirmation**. Merge into `~/.teachme-config.json` (preserving `mode`, `obsidian_vault`, and `vault_state_dirs`):

   ```json
   {"notes_root": "<normalized-path>", "updated_at": "<YYYY-MM-DD>"}
   ```

2. **No argument:** Print the active standalone `<STATE_ROOT>`, active mode (`auto`/`standalone`/`vault-native`), connected `obsidian_vault` (if any), and list standalone session folders.
3. **`reset`:** Set `notes_root` back to `~/notes` (update `updated_at`); never delete files in the old folder.

Confirm the active root in one line.
