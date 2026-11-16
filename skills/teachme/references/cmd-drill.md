# Command: `/teachme-drill <topic> [1|2|3]` *(alias: `/teachme drill <topic> [--tier 1|2|3]`)*

Generate and grade Tier 1 (recall/substitution), Tier 2 (multi-step synthesis), or Tier 3 (adversarial edge-case) practice problems for `<VAULT_ROOT>/<topic-slug>/`.

## Execution Sequence
1. **Zero-Token Context Load:**
   - Run `vault_cli.py state <VAULT_PATH>` to read active subtopic/ZPD stage.
   - Check `07-PRACTICE-PROBLEMS.md` (if it exists) to avoid duplicate problems.
   - Slice ONLY `L3-FOUR-LAYER-THEORY` / `L4-DERIVATION-AND-CODE` / `L5-WORKBOOK-AND-GRAPH` of the target subtopic(s) via `vault_cli.py slice`.
2. **Generate 1–3 Calibrated Problems:**
   - **Tier 1:** Direct formula substitution & directional sensitivity.
   - **Tier 2:** Multi-step derivation or cross-subtopic synthesis.
   - **Tier 3:** Adversarial edge cases, failure diagnosis, and boundary limits (`$0$`, `$1$`, `$-1$`, `$\infty$`).
3. **Interactive Grading (1 Problem per Turn, Anti-Spoiler):**
   - Present **one problem at a time** in chat. Wait for the user's solution.
   - On errors or `"idk"`, apply the **Strict Anti-Spoiler Rule** (`RETENTION-AND-RECORDS.md` §3): drop down to a 1-number micro-question on the divergent step rather than revealing the answer.
4. **Persist Solved Problems:**
   - Append solved problems with full zero-skip step-by-step solutions into `<VAULT_ROOT>/<topic-slug>/07-PRACTICE-PROBLEMS.md` (enforcing `SKILL.md` §9–10: `100%` `$...$`/`$$...$$` math coverage, zero bare LaTeX, zero backticks, `\mid` in tables, and column-0 blank-line-padded `<details>` blocks under `####` headings).
