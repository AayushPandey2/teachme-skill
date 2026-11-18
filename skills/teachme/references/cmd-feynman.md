# `/teachme-feynman <concept>`

Role reversal: the learner explains `<concept>` in plain words with zero unstated jargon. Use when explaining a mechanism fits the objective (do not force Feynman checks on trivial notation). Laws: `SKILL.md §A–§D`. Graduated Support: `RETENTION-AND-RECORDS.md §3`.

## Steps
1. **Load:** `vault_cli.py state`; then `vault_cli.py context [<session>] --topic <nn>` (plus optional read-only vault search if in Vault-Native Mode).
2. **Prompt:** Ask the learner to explain the mechanism, key assumptions, and any unfamiliar symbols in plain language. Wait.
3. **Grade accurately:** Check (1) plain-English clarity without unstated jargon, (2) causal/first-principles accuracy, (3) symbol/assumption validity, (4) relevant failure/boundary cases. Identify what was accurate and the first meaningful gap; probe or scaffold via Graduated Support (if they say `"explain"`, explain directly and follow with a fresh check).
4. **Persist evidence:** Save `learning-records/000N-feynman-<slug>.md` when notable; record via `vault_cli.py assess --topic <nn> --objective <obj_id> --assessment-type feynman_explanation --result <pass|partial|fail> --assistance <none|hint|scaffold|worked_example> --rationale "<summary>"`. Never fabricate retention or transfer from a single Feynman check.
