# `/teachme-vault` — Connect Obsidian Vaults for Isolated State & Read-Only Search

Manage Vault-Native Mode (`references/VAULT-NATIVE.md`) for operational learning-state isolation and read-only source lookup. Study-note planning, generation, and validation belong to Scriptorium (`references/SCRIPTORIUM-HANDOFF.md`).

## Subcommands
- `connect <vault-path> [--mode auto|vault-native|standalone] [--state-dir <dir>]` — Connect an existing Obsidian vault, persist `~/.teachme-config.json`, and build the read-only search index in `.teachme/index.json`.
- `search [vault-path] --query "<topic>" [--limit N]` — Read-only search across existing vault notes as optional learning context.
- `reindex [vault-path] [--full]` — Refresh the read-only vault search index.
- `mode [auto|standalone|vault-native]` — View or switch operating mode.
- `state [vault-path] [--session <slug>]` — Inspect isolated TeachMe sessions under `<vault>/.teachme/sessions/`.
