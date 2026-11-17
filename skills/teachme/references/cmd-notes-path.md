# `/teachme-notes-path [path|reset]`

View, change, or reset `<VAULT_ROOT>` (`SKILL.md §A`). For connecting an existing Obsidian vault in Vault-Native Mode, see `/teachme-vault connect <vault-path>`.

## Modes
1. **`<path>`:** expand `~`, `$HOME`, `%USERPROFILE%`, `$env:USERPROFILE`; normalize slashes; create the folder if missing and confirm write access.
   - If `<path>/.obsidian/` exists, ask whether to connect it in **Vault-Native Mode** (`vault_cli.py connect <path>`) or keep `notes_root` for standalone vaults — never restructure an existing Obsidian vault.
   - If standalone vaults exist at the old root, show both roots and ask whether to copy/move or keep separate — **never move or delete without explicit confirmation**. Then merge into `~/.teachme-config.json` (preserving `mode`, `obsidian_vault`, and `vault_state_dirs`):

   ```json
   {"notes_root": "<normalized-path>", "updated_at": "<YYYY-MM-DD>"}
   ```

2. **No argument:** print the active `<VAULT_ROOT>`, active mode (`auto`/`standalone`/`vault-native`), connected `obsidian_vault` (if any), and list standalone topic vaults plus `comparisons/`.
3. **`reset`:** set `notes_root` back to `~/notes` (update `updated_at`); never delete files in the old folder.

Confirm the active root in one line.
