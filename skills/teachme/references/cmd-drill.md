# `/teachme-drill <topic> [1|2|3]` (alias `--tier 1|2|3`)

Generate, verify, and grade adaptive practice problems interactively without writing study notes. Laws: `SKILL.md §A–§D`. Pedagogy & Graduated Support: `RETENTION-AND-RECORDS.md §3–§5`.

## Steps
1. **Load bounded context:** `vault_cli.py context [<session>] --topic <nn>` to inspect active objectives, assumptions, recent events, and `learning-records/`.
2. **Select appropriate tasks:** Match the objective and learner evidence instead of mechanically forcing identical task types:
   - Tier 1 (foundational): `prediction`, `worked_example_completion`, `independent_application`, `predict_output`
   - Tier 2 (reasoning & diagnosis): `find_first_error`, `method_justification`, `concept_comparison`, `debug_program`
   - Tier 3 (edge cases & transfer): `violated_assumption`, `counterexample`, `why_tempting_fails`, `transfer` (vary reasoning context, not just numbers)
3. **Verify before presenting:** Check arithmetic, execute small code examples when a safe runtime exists, verify assumptions, and distinguish checked (`--checked`) from unverified cases.
4. **Grade interactively with Graduated Support:** Wait for the learner's attempt before revealing solutions (unless they say `"explain"`). Identify what was right and the first meaningful error. Offer `hint` -> `scaffold` -> `worked_example` -> fresh independent attempt as needed.
5. **Log evidence:** Record `--result` and `--assistance` (`none|hint|scaffold|worked_example`) via `vault_cli.py assess` (or `tick`), and log notable misconceptions in `learning-records/`. Never write study notes.
