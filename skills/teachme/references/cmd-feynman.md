# `/teachme-feynman <concept>`

Role reversal: the learner explains `<concept>` and its governing equation to a beginner with zero unstated jargon. Laws: `SKILL.md §B–§C`. Probing: `RETENTION-AND-RECORDS.md §3`.

## Steps
1. **Load:** `vault_cli.py state`; then `vault_cli.py context <vault> --topic <nn> --section L3-FOUR-LAYER-THEORY` plus the relevant `04-GLOSSARY.md` terms.
2. **Prompt:** ask the user to explain the concept and every symbol/operator of its core equation in plain English. Wait.
3. **Grade on 4 axes:** (1) plain-English clarity vs. `04-GLOSSARY.md`, (2) first-principles accuracy, (3) formula intuition for every symbol, (4) edge-case awareness. For gaps, ask 1–2 surgical micro-questions — never hand over the explanation.
4. **Persist:** save `learning-records/000N-feynman-<slug>.md`; on pass, `tick --cp 4 --status pass --note "<invariant>"` + `flush`.
