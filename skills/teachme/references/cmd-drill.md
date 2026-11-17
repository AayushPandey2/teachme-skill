# `/teachme-drill <topic> [1|2|3]` (alias `--tier 1|2|3`)

Generate and grade live Tier 1–3 practice problems interactively without writing study notes. Laws: `SKILL.md §A–§D`. Grading & Anti-Spoiler: `RETENTION-AND-RECORDS.md §3–§4`.

## Steps
1. **Load:** `vault_cli.py context [<session>] --topic <nn>` to inspect the active curriculum node, equations, recent events, and active `learning-records/`.
2. **Generate 1–3 problems in chat:** Tier 1 = substitution & directional sensitivity; Tier 2 = multi-step derivation or cross-subtopic synthesis; Tier 3 = adversarial edge cases and limits ($0$, $1$, $-1$, $\infty$).
3. **Grade interactively (ONE question per turn):** Apply the Anti-Spoiler Micro-Hint Rule on misses.
4. **Log evidence:** Record retries/passes via `vault_cli.py tick` (with `--note "<misconception or invariant>"`) and persist notable struggles or breakthroughs in `learning-records/000N-<slug>.md`. Never write `07-PRACTICE-PROBLEMS.md` or other study notes.
