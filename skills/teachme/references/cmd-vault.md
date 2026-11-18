# `/teachme-vault` — Multi-Vault Registry, Isolated State & Read-Only Source Lookup

Manage Vault-Native Mode (`references/VAULT-NATIVE.md`) for operational learning-state isolation, multi-vault selection, and read-only source retrieval. Persistent study-note creation belongs to external note-writing skills (`references/NOTE-SKILL-HANDOFF.md`), never TeachMe.

## Subcommands
- `connect <vault-path> [--name <alias>] [--mode auto|vault-native|standalone] [--state-dir <dir>] [--no-activate]` — Register an existing Obsidian vault, persist `~/.teachme-config.json`, and build the incremental index in `.teachme/index.json`.
- `vaults` — List registered vaults, active selection, accessibility status, and isolated session counts.
- `use-vault <name-or-path>` — Switch the active registered vault explicitly.
- `remove-vault <name-or-path>` — Unregister a vault from `~/.teachme-config.json` without deleting any files on disk.
- `resolve-sources [vault-path] --topic "<topic>" [--vault <ref>] [--session <slug>] [--no-web]` — Resolve `vault` / `hybrid` / `web` mode with bounded matched sections, related notes, and coverage gaps.
- `search [vault-path] --query "<topic>" [--vault <ref>] [--limit N] [--sections]` — Read-only search across existing vault notes as optional learning context.
- `reindex [vault-path] [--vault <ref>] [--full]` — Refresh the read-only vault search index.
- `mode [auto|standalone|vault-native]` — View or switch operating mode.
- `state [vault-path] [--session <slug>]` — Inspect isolated TeachMe sessions under `<vault>/.teachme/sessions/`.
