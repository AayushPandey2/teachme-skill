# `/teachme-review <topic>`

Delayed spaced-review and gap-targeted Socratic coaching without generating or modifying study notes. Laws: `SKILL.md §A–§D`. Adaptive pedagogy & evidence: `RETENTION-AND-RECORDS.md`.

## Steps
1. **Select due & weak targets (read-only):** Run `vault_cli.py due [<session>]` and `vault_cli.py coverage [<session>]`. Due items include **previously demonstrated/mastered topics whose review is due** (default configurable intervals `[1, 3, 7, 21]` days), legacy unverified topics needing a retrieval check, and lapsed/weakened objectives — prioritized transparently by recent failure, overdue days, required status, and prerequisite impact. Opening review state never mutates evidence.
2. **Load bounded context:** Run `vault_cli.py context [<session>] --topic <nn>`.
3. **Start with unaided retrieval BEFORE any recap:** Prompt the learner to retrieve or solve the target objective unaided first (`--assessment-type delayed_recall`). Do not give away the recap beforehand.
4. **Respond adaptively:**
   - **Independent pass (`--assistance none`):** If `>= 12` hours elapsed since prior independent demonstration and in a new session, this verifies delayed retention and advances the schedule.
   - **Failure or misconception:** Teach or scaffold via Graduated Support (`RETENTION-AND-RECORDS.md §3`), check if a missing prerequisite needs repair (`revise-curriculum` / `calibrate`), then test with a **fresh** problem.
   - **Assisted pass (`hint`/`scaffold`/`worked_example`):** Counts as progress, not independent retention; schedule stays unadvanced for a fresh unaided check.
5. **Log evidence:** Record every attempt with `vault_cli.py assess` (or `tick`) specifying `--objective`, `--assessment-type`, `--result`, and `--assistance`. Log resolved misconceptions or breakthroughs in `learning-records/`.
