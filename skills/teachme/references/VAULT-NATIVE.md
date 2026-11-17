# Vault-Native Mode: Isolated State & Read-Only Obsidian Lookup

Use this workflow whenever targeting an existing Obsidian vault (`.obsidian/` detected or `mode: vault-native`). Never create, modify, rename, or reformat user notes or impose TeachMe's directory layout on the Obsidian vault root. Isolate all TeachMe operational state inside `<vault>/.teachme/sessions/<topic-slug>/` (or `--state-dir`), and treat all vault notes strictly as read-only learning data.

## §1. Supported Workflow (`connect` → `search` → Teach in Isolated State)
1. **Connect Vault:** Run `vault_cli.py connect <vault> [--mode vault-native] [--state-dir <dir>]`. Persists `~/.teachme-config.json` and builds a read-only search index at `<vault>/.teachme/index.json`.
2. **Search Existing Notes (Read-Only):** Run `vault_cli.py search <vault> --query "<topic>"` to inspect relevant existing notes as optional learning context before planning a curriculum. Run `vault_cli.py reindex <vault>` to refresh the index after external vault edits.
3. **Run Teaching Sessions in Isolated State:** `vault_cli.py init <vault> --topic "<topic>" --subtopics <file.json>` creates operational state ONLY inside `<vault>/.teachme/sessions/<topic-slug>/`. `state`, `context`, `tick`, `flush`, `validate-state`, and `handoff` operate exclusively on `.teachme/`.

## §2. Study-Note Boundary
- TeachMe **never** writes, extends, tags, links, or validates study notes in the Obsidian vault.
- Whenever the user asks to create, expand, summarize into, or verify Obsidian study notes, delegate to **Scriptorium** (`references/SCRIPTORIUM-HANDOFF.md`), which uses its own vault configuration (`SCRIPTORIUM_VAULT_PATH` or `~/.scriptorium-config.json`).
