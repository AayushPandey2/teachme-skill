# Command: `/teachme-distill <topic>` *(alias: `/teachme distill <topic>`)*

Compress `<VAULT_ROOT>/<topic-slug>/` into a single-page executive cheat sheet (`09-CHEAT-SHEET.md`) and refresh `08-FLASHCARDS.md`.

## Execution Sequence
1. **Token-Efficient Vault Harvest:**
   - Run `vault_cli.py state <VAULT_PATH>` and `vault_cli.py graph <VAULT_PATH>`.
   - Read `04-GLOSSARY.md`, `05-MENTAL-MODELS.md`, `06-DERIVATIONS-AND-PROOFS.md`, and slice `--section L0-L1` (plus `L3-FOUR-LAYER-THEORY` key equations where needed) from `topics/*.md` via `vault_cli.py slice`.
2. **Generate `<VAULT_ROOT>/<topic-slug>/09-CHEAT-SHEET.md` (4 Sections Only):**
   - `## 1. Core Axioms & Invariants` (5–8 crisp 1-sentence truths)
   - `## 2. Critical Formula Reference Table` (`Formula Name | Equation | Compact Symbol Key | Limiting Behavior` — pure LaTeX, zero backticks, `\mid` in tables)
   - `## 3. Decision & Trade-Off Matrix` (`Scenario / Requirement | Choose <Topic> When... | Avoid / Alternative When...`)
   - `## 4. Top Failure Modes & Gotchas` (`Symptom | Root Cause | Immediate Fix / Invariant`)
3. **Refresh Flashcards & Link MOC:**
   - Append any missing high-yield conceptual (`::` / `?`) or formula cloze (`==...==`) cards to `08-FLASHCARDS.md` without deleting existing cards.
   - Ensure `[[09-CHEAT-SHEET]]` is linked in `00-MOC-INDEX.md` Vault Navigation and run `vault_cli.py verify <VAULT_PATH>`.
