# `/teachme-vault` — Connect, Inspect & Manage Obsidian Vaults

Manage Vault-Native Mode (`references/VAULT-NATIVE.md`).

## Subcommands
- `connect <vault-path> [--mode auto|vault-native|standalone] [--state-dir <dir>]` — Connect an existing Obsidian vault, persist `~/.teachme-config.json`, and run initial discovery + indexing.
- `profile [vault-path]` / `discover [vault-path] [--refresh]` — Inspect and display inferred folder roles, tag vocabulary, metadata schema, note styles, and plugin capabilities.
- `search [vault-path] --query "<topic>"` — Retrieve relevant existing notes and backlinks.
- `plan [vault-path] --topic "<topic>"` — Preview placement confidence, template selection, tags, frontmatter, and verified wikilinks.
- `generate [vault-path] --topic "<topic>" [--dry-run|--apply] [--extend <relpath>]` — Preview or write a vault-native note safely.
- `audit [vault-path] [--file <relpath>]` — Audit TeachMe-managed vault-native notes without touching user notes.
- `mode [auto|standalone|vault-native]` — View or switch operating mode.
