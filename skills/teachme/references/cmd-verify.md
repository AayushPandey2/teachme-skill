# `/teachme-verify <topic>` (alias `audit`)

Deterministic integrity sweep (`SKILL.md §B`).

## Mode Guard
- **Vault-Native Mode:** `vault_cli.py verify` automatically delegates to `audit` (checks ONLY TeachMe-managed notes in `.teachme/managed-notes.json` for YAML, math parity, and broken wikilinks) and `vault_cli.py fix` skips user-authored notes. NEVER run standalone format-repair across an existing Obsidian vault.
- **Standalone Mode:** Repair ONLY flagged lines until zero errors.

## Standalone Steps
1. `vault_cli.py graph` → `fix` (auto-repairs `<details>` shape + unambiguous bare LaTeX) → `verify`.
2. Read only the JSON `errors`/`warnings` (`file`, `line`, `type`, `detail`); never read clean files. Confirm `00-SESSION-STATE.md` (`<60` lines) and `scratchpad/` exist.
3. Repair by type:

| `type` | Fix |
|---|---|
| `details_block_format` | Reshape to `SKILL.md §B.4` |
| `bare_latex_command`, `latex_trailing_space`, `backtick_latex` | Wrap in `$…$`, drop space before closing `$`, strip backticks around math |
| `table_pipe_in_math` | Raw pipe → `\mid`, `\lvert`/`\rvert`, `\lVert`/`\rVert` |
| `unmatched_dollar`, `unclosed_display_math` | Balance delimiters; escape currency as `\$` |
| `broken_wikilink`, `broken_md_link`, `broken_anchor`, `placeholder_wikilink`, `broken_typed_edge` | Remove `.md` in wikilinks, fix slug/case/anchor, `[[none]]` → `[]`, fix `topic-<nn>` edges, or create the missing file if the syllabus requires it |
| `missing_section_marker`, `duplicate_section_number`, `non_sequential_section_numbers`, `unlinked_graph_path` | Restore markers/headings per `STUDY-AND-GLOSSARY.md §2`; wrap Section 7 paths in `[[…]]` |
| `missing_primary_sources_table`, `missing_primary_source_deep_link` | Add the Section 7 table with `https://` + `[[01-RESOURCES#…]]` anchors |
| `yaml_*` | Quote/indent per `SKILL.md §B.1` |
| `orphan_file` (warning) | Register in `00-MOC-INDEX.md`; re-run `graph` |

4. Also spot-check glossary alignment and Formula Anatomy on display equations.
5. Loop `graph` → `verify` until `errors: []` and `orphans: 0`; output `File | Links Fixed | Formulas Fixed | Structure | Status`.
