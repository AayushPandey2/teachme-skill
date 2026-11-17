# Vault-Native Integration Details (Load On Demand)

Detailed behavior for `teachme_vault/` tagging, MOCs, Mermaid diagrams, transactions, and CLI output modes.

## §1. Context-Aware Tagging (`tagging.py`)
- Uses note content (`intuition`, `mechanism`, `invariant`, `summary`, `concepts`), keywords, and neighboring notes—never folder popularity alone.
- Rejects irrelevant popular folder tags, synonymous/plural/separator duplicates, and overly specific one-off tags (`>4` words, dates/IDs).
- Creates new tags only when needed, matching folder/vault `case_style` (`kebab_case`, `snake_case`, `camel_case`, `pascal_case`, `lowercase`), placement (`frontmatter`, `inline`, `both`), and nested namespaces (`/`).
- Keeps workflow/status/plugin tags (`mastered`, `reviewed`, `evergreen`, `seedling`, `flashcards`, `cards`, `status/*`) strictly separate from subject tags; permits tag-free results.

## §2. Automatic MOC Selection, Query Satisfaction & Creation (`moc.py`)
- Multi-signal MOC identification: requires explicit metadata/tags, query-driven DQL/Base signals, or hub/folder-note naming + structured link lists (a prose note with links or `"index"` substring is not a MOC).
- Selects the closest matching existing hub vault-wide, chooses the semantic section, detects alias/path-equivalent links to prevent duplicates, and inserts minimal targeted lines.
- **Query-driven MOCs:** Selects the single matching query MOC first (never importing tags/fields from unrelated query MOCs in the same folder), satisfies `!=` exclusions safely, leaves unknown value predicates unset with a warning rather than writing `""`, and skips redundant manual bullet lists.
- Creates a new MOC only when no existing hub fits and a coherent unhubbed cluster meets `--min-moc-cluster-size` (default `3`).

## §3. Mermaid Diagrams & Validation (`mermaid.py`)
- Builds a structural spec first (`mindmap` for hierarchies; `flowchart` for prerequisites, processes, contrasts), distinguishing `existing_note` vs. `concept` nodes and never fabricating prerequisite edges from keyword similarity.
- Escapes quotes/brackets/parens, uses deterministic IDs, caps node counts, and falls back to `flowchart` if `mindmap` is unavailable (`--no-mindmap`).
- Validates using `mmdc` CLI if installed on `PATH`; otherwise runs structural validation and reports `"validation_mode": "structural_only"`.

## §4. Plan Integrity, Transactions & CLI Output Modes
- **Canonical Plan Hash:** Unkeyed SHA-256 over `plan_version`, `vault_path`, `topic`, `recommended_action`, `unresolved`, and every `affected_files` entry (`rel_path`, `role`, `action`, `must_not_exist`, `expected_sha256`, `conflict`, `no_changes`, `inserted_line`, `new_text`). `apply` recomputes and rejects any tampered or unresolved plan before checking disk freshness.
- **Transactions:** Validates all edits and attachments upfront, re-checks disk hashes right before each write, writes per-file atomically (`os.replace`) with backups in `.teachme/backups/` and a `.teachme/transactions/` journal, and rolls back only files still matching what this transaction wrote. Post-commit manifest/index/audit issues report `writes_committed: true` without falsely claiming rollback.
- **Output Modes (`--output`):**
  - `plan`: `summary` (default) | `diff` | `full`
  - `generate --dry-run`: `diff` (default, prints diff once) | `summary` | `full`
  - `generate --apply` / `apply`: `summary` (default compact receipt) | `diff` | `full`
  - `discover` / `profile` / `audit`: `summary` (default) | `full`
