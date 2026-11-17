# `/teachme-vault` — Connect, Inspect & Manage Obsidian Vaults

Manage Vault-Native Mode (`references/VAULT-NATIVE.md`; detailed policies in `references/VAULT-INTEGRATION-DETAILS.md`).

## Subcommands
- `connect <vault-path> [--mode auto|vault-native|standalone] [--state-dir <dir>]` — Connect an existing Obsidian vault, persist `~/.teachme-config.json`, and run initial discovery + indexing.
- `profile [vault-path] [--output summary|full]` / `discover [vault-path] [--refresh] [--output summary|full]` — Inspect inferred folder roles, tag vocabulary, multi-signal MOCs, Mermaid conventions, metadata schema, and plugins.
- `search [vault-path] --query "<topic>"` — Retrieve relevant existing notes and backlinks.
- `plan [vault-path] --topic "<topic>" [--folder ...] [--template ...] [--keywords ...] [--extend <rel>] [--content-json <file>] [--proposal-json <file>] [--mermaid auto|mindmap|flowchart|none] [--no-mindmap] [--min-moc-cluster-size N] [--no-moc] [--output summary|diff|full]` — Plan placement, tags, MOC, Mermaid, and links; saves canonical hashed snapshot (`plan_id`, `plan_hash`) under `.teachme/plans/`.
- `generate [vault-path] --topic "<topic>" [--dry-run|--apply] [--extend <relpath>] [--plan <id_or_file>] [--plan-hash <hash>] [--expected-hash <sha256>] [--mermaid ...] [--output summary|diff|full]` — Preview diff once (`--dry-run`, default `diff`) or apply transactionally (`--apply`, default `summary` receipt).
- `apply [vault-path] --plan <plan_id_or_file> [--plan-hash <hash>] [--output summary|diff|full]` — Validate and execute an exact saved plan without recomputing; rejects tampered, unresolved, or stale plans.
- `audit [vault-path] [--file <relpath>] [--output summary|full]` — Audit TeachMe-managed notes, extensions, and added MOC entries. Exits `0` when `errors: []` (warnings/pre-existing user issues do not fail), `1` when errors exist.
- `mode [auto|standalone|vault-native]` — View or switch operating mode.
