# `/teachme-feynman <concept>`

Role reversal: the learner explains `<concept>` and its governing equation to a beginner with zero unstated jargon. Laws: `SKILL.md §A–§D`. Probing: `RETENTION-AND-RECORDS.md §4`.

## Steps
1. **Load:** `vault_cli.py state`; then `vault_cli.py context [<session>] --topic <nn>` (plus optional read-only vault search if in Vault-Native Mode).
2. **Prompt:** Ask the learner to explain the concept and every symbol/operator of its core equation in plain English. Wait.
3. **Grade on 4 axes:** (1) plain-English clarity with zero unstated jargon, (2) first-principles accuracy, (3) formula intuition for every symbol, (4) edge-case awareness. For gaps, ask 1–2 surgical micro-questions — never hand over the explanation.
4. **Persist operational evidence:** Save `learning-records/000N-feynman-<slug>.md`; on pass, run `vault_cli.py tick --cp 4 --status pass --note "<invariant>"` + `vault_cli.py flush --topic <nn> --note "<invariant>"` (state-only; never mutates study notes).
