# `/teachme-vault` — Connect, Inspect & Manage Obsidian Vaults

Manage Vault-Native Mode (`references/VAULT-NATIVE.md`).

## Subcommands
- `connect <vault-path> [--mode auto|vault-native|standalone] [--state-dir <dir>]` — Connect an existing Obsidian vault, persist `~/.teachme-config.json`, and run initial discovery + indexing.
- `profile [vault-path]` / `discover [vault-path] [--refresh]` — Inspect and display inferred folder roles, tag vocabulary (placement, case, subject vs workflow), multi-signal MOCs, Mermaid conventions, metadata schema, note styles, and plugin capabilities.
- `search [vault-path] --query "<topic>"` — Retrieve relevant existing notes and backlinks.
- `plan [vault-path] --topic "<topic>" [--folder ...] [--template ...] [--keywords ...] [--extend <rel>] [--content-json <file>] [--proposal-json <file>] [--mermaid auto|mindmap|flowchart|none] [--no-mindmap] [--min-moc-cluster-size N] [--no-moc]` — Preview placement, template, tag decisions, MOC selection/creation, Mermaid diagram, verified wikilinks, affected file diffs, and expected hashes; saves a reviewable plan snapshot (`plan_id`, `plan_hash`).
- `generate [vault-path] --topic "<topic>" [--dry-run|--apply] [--extend <relpath>] [--plan <id_or_file>] [--plan-hash <hash>] [--expected-hash <sha256>] [--mermaid ...]` — Preview or execute vault-native note + MOC + Mermaid changes transactionally with backups and rollback.
- `apply [vault-path] --plan <plan_id_or_file> [--plan-hash <hash>]` — Execute an exact previously previewed plan without recomputing, rejecting if any target file changed on disk.
- `audit [vault-path] [--file <relpath>]` — Audit TeachMe-managed vault-native notes, extensions, and added MOC entries without touching or blaming pre-existing user notes.
- `mode [auto|standalone|vault-native]` — View or switch operating mode.
