# Command: `/teachme-feynman <concept>` *(alias: `/teachme feynman <topic> [subtopic]`)*

Test plain-English mastery by reversing roles: the learner explains `<concept>` (and its governing equation) from scratch with zero unstated jargon under Socratic probing.

## Execution Sequence
1. **Targeted Context Load:**
   - Run `vault_cli.py state` (resolving `<VAULT_PATH>`) and `vault_cli.py graph <VAULT_PATH>` if `<topic>` exists.
   - Load ONLY `04-GLOSSARY.md` (relevant terms) and `L0-L1` + `L3-FOUR-LAYER-THEORY` of the target subtopic via `vault_cli.py slice`.
2. **Role Reversal Prompt:**
   - Ask the user to explain `<concept>` and what each symbol/operator in its core equation does in plain English as if teaching a complete beginner. Wait for their explanation.
3. **4-Axis Grading Rubric + Anti-Spoiler Probing:**
   - Grade strictly on: (1) **Plain-English Clarity** (zero unstated jargon vs. `04-GLOSSARY.md`), (2) **First-Principles Accuracy** (causal steps & invariants), (3) **Formula Intuition** (every variable/operator explained), and (4) **Edge-Case Awareness** (where the analogy or mechanism breaks down).
   - If gaps exist, **do not give away the full explanation immediately**—ask 1–2 surgical Socratic micro-questions targeting the missing link (`RETENTION-AND-RECORDS.md` §3).
4. **Persist Outcome:**
   - Save the session summary to `<VAULT_ROOT>/<topic-slug>/learning-records/000N-feynman-<slug>.md`.
   - If a subtopic passes, run `vault_cli.py tick ... --cp 4 --status pass --note "<verified invariant>"` and `vault_cli.py flush <VAULT_PATH> --topic <nn> --note "<verified invariant>"`.
