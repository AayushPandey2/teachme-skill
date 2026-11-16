# `/teachme-drill <topic> [1|2|3]` (alias `--tier 1|2|3`)

Generate and grade calibrated practice problems into `07-PRACTICE-PROBLEMS.md`. Laws: `SKILL.md §B`. Grading: `RETENTION-AND-RECORDS.md §2–§3`.

## Steps
1. **Load:** `vault_cli.py context <vault> --topic <nn> --section L4-DERIVATION-AND-CODE` (add `L3`/`L5` only if needed); skim `07-PRACTICE-PROBLEMS.md` headings to avoid duplicates.
2. **Generate 1–3 problems:** Tier 1 = substitution & directional sensitivity; Tier 2 = multi-step derivation or cross-subtopic synthesis; Tier 3 = adversarial edge cases and limits ($0$, $1$, $-1$, $\infty$).
3. **Grade interactively:** one problem per turn; Anti-Spoiler micro-steps on misses.
4. **Persist:** append each solved problem under a `#### Tier <k> — <Title>` heading with its zero-skip solution in a `SKILL.md §B.4` `<details>` block; then `fix` → `verify`.
