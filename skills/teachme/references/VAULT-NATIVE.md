# Vault-Native Mode: Context-Aware Obsidian Integration

Use this workflow whenever the target is an existing Obsidian vault (`.obsidian/` detected or `mode: vault-native`). Never impose TeachMe's standalone folder layout (`00-SESSION-STATE.md`, `topics/`, `01`–`09`) on an existing vault; store TeachMe state in `<vault>/.teachme/` (or configured `--state-dir`).

## §1. Mandatory Discovery-First Workflow (Before Any Write)
1. **Profile & Index:** Run `vault_cli.py discover <vault>` (or `profile` + `reindex`) so `profile.json` and `index.json` reflect the current vault. Never load the whole vault into LLM context.
2. **Retrieve Existing Knowledge:** Run `vault_cli.py search <vault> --query "<topic>"` to inspect:
   - Existing notes on the topic (avoid creating duplicates; prefer `--extend` or linked companion notes).
   - Covered prerequisites and terminology/notation already established by the user.
   - Contradictions or alternative definitions to surface explicitly.
3. **Plan Placement, Template & Style:** Run `vault_cli.py plan <vault> --topic "<topic>"` to get:
   - Confidence-ranked destination folder + filename matching the folder's naming convention.
   - Best matching vault template (6-level priority: explicit > configured folder template > inferred folder convention > vault convention > adaptive blueprint).
   - Reusable tags & frontmatter properties from the vault's actual vocabulary (never invent a parallel tag taxonomy).
   - Verified `[[wikilinks]]` (never fabricate targets).
   - Folder-specific style guidance (atomic vs. comprehensive, headings, callouts, math, flashcards).
4. **Confirm on Low Confidence:** If `destination.needs_confirmation` or `template.needs_confirmation` is `true`, show the top candidates with evidence or preview via dry-run before applying.

## §2. Plugin & Asset Safety Rules
- **Templater / Templates:** Fill safe static placeholders (`{{title}}`, `{{date}}`, `<% tp.file.title %>`, `<% tp.date.now() %>`). Preserve unsupported dynamic `<% ... %>` expressions untouched; never execute JS/shell.
- **Dataview:** Preserve queried YAML/inline fields (`key:: val`) required by existing DQL queries; never execute `dataviewjs`.
- **Spaced Repetition / Tasks:** Match the vault's detected `#flashcards` / `::` / `?` / cloze syntax and task global filters/markers.
- **Excalidraw / Canvas / Bases:** Treat `.excalidraw.md`, `.canvas`, and `.base` files as read-only protected assets.

## §3. Non-Destructive Write & Audit Gate
- Preview first: `vault_cli.py generate <vault> --topic "<topic>" --dry-run` (default).
- Write atomically only with explicit apply: `vault_cli.py generate <vault> --topic "<topic>" --apply` (or `--extend <relpath>` to append a minimal, backed-up section without altering existing YAML, comments, or block IDs).
- Finish with `vault_cli.py audit <vault>` (audits ONLY TeachMe-managed notes; never flags or edits user-authored notes).
- Keep TeachMe's educational depth intact (first principles, prerequisites, derivations, examples, practice/Feynman checks, primary sources) while adapting formatting to the vault's style.
