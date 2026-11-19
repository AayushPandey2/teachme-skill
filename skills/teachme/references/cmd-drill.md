# `/teachme-drill <topic> [1|2|3]` (alias `--tier 1|2|3`)

Generate, verify, and grade adaptive practice problems interactively without writing study notes. Laws: `SKILL.md §A–§D`. Pedagogy & Graduated Support: `RETENTION-AND-RECORDS.md §3–§5`.

## Steps
1. **Load bounded context & adaptive quiz plan:** Run `vault_cli.py context [<session>] --topic <nn>` and `vault_cli.py quiz-plan [<session>] --topic <nn> [--objective <obj_id>] [--tier 1|2|3]` to inspect active objectives, assumptions, recent events, `learning-records/`, and recommended difficulty level.
2. **Select appropriate tasks:** Match the objective and learner evidence instead of mechanically forcing identical task types (never advance difficulty on assisted passes alone):
   - Level 1 — Foundation: `multiple_choice`, `short_conceptual`, `numerical_calculation`, `prediction`, `predict_output`, `worked_example_completion`
   - Level 2 — Reasoning: `independent_application`, `fill_missing_step`, `find_first_error`, `debug_program`, `method_justification`, `concept_comparison`
   - Level 3 — Mastery and transfer: `violated_assumption`, `counterexample`, `why_tempting_fails`, `feynman_explanation`, `transfer` (vary reasoning context, not just numbers)
3. **Verify before presenting:** Check arithmetic, execute small code examples when a safe runtime exists, verify assumptions, and distinguish checked (`--checked`) from unverified cases.
4. **Grade interactively with Graduated Support:** Wait for the learner's attempt before revealing solutions (unless they say `"explain"`). Use `vault_cli.py evaluate-answer` for deterministic numeric/multiple-choice/expression/trace checks, and rubric evaluation (not naive keyword matching) for complex conceptual explanations. Avoid generic praise; identify what was right, the first meaningful error, and whether a prerequisite is missing. Offer `hint` -> `scaffold` -> `worked_example` -> fresh independent attempt as needed.
5. **Log evidence:** Record `--result` and `--assistance` (`none|hint|scaffold|worked_example`) via `vault_cli.py assess` (or `tick`), and log notable misconceptions in `learning-records/`. Never write study notes.
