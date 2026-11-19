# Live Adaptive Teaching, Graduated Support, Evidence & Records

Core invariants and CLI laws live in `SKILL.md §A–§D`. Load `VISUALS-AND-EXPERIMENTS.md` only when a visual or experiment serves the active objective.

## §1. Per-Turn Context Protocol
1. **One bounded call per turn:** `vault_cli.py context [<session_or_vault>] --topic <nn>` returns operational state, objective-level coverage & proficiency, prerequisite states, bounded due-review summary, recent events, active learning records, and 1-hop neighbors.
2. **Check coverage & due items when relevant:** Use `vault_cli.py coverage` to see untested required objectives and unresolved gaps, and `vault_cli.py due` for scheduled delayed reviews. Do **not** claim completion of the agreed scope while required objectives remain untested or prerequisite gaps remain unresolved.
3. **Never write study notes:** Persist evidence via `vault_cli.py assess` (or `tick`) and `learning-records/`.

## §2. Adaptive Decision Policy & Modality Selection
Keep modality selection separate from `resolve-sources` (sources decide *where* knowledge comes from; `vault_cli.py route-modality` decides *how* to teach it). Run this adaptive loop with **no rigid sequence**:
1. **Identify objective** (from agreed scope, due reviews, or learner question).
2. **Load minimal context & evidence** (`vault_cli.py context` + prerequisite states + recent errors).
3. **Select a teaching modality** (`vault_cli.py route-modality`): choose a visual, simulation, quiz, or experiment **only** when it materially improves understanding or assessment; if evidence of usefulness is weak, prefer simpler/cheaper text.
4. **Explain or demonstrate** using evidence-informed methods:
   - *First-principles teaching:* Fundamental intuition before advanced terminology; explain why the mechanism works and unpack equations via `Formula Anatomy`.
   - *Predict -> Observe -> Explain:* For simulations/experiments, ask for a prediction, run/advance, show the observed result, explain mismatches, then vary a parameter.
   - *Worked example fading:* Start with an explained example (`I Do`), fade assistance (`We Do`), then verify with a fresh independent problem (`You Do`).
   - *Misconception-driven teaching & modality switching:* Target the specific flawed mental model; after repeated errors, switch to a genuinely different modality instead of repeating the same explanation.
   - *Retrieval practice & interleaving:* Start due reviews with **unaided retrieval** before any recap; interleave related objectives when ready.
   - *Transfer-based mastery:* Test unfamiliar reasoning contexts (changing numbers alone is **not** transfer).
   - *Adaptive pacing:* Keep explanations short for demonstrated familiarity; add scaffolding when evidence shows struggle; respect short time budgets.
   - *Explain-on-request:* If the learner explicitly asks for a direct explanation (`"explain"`), provide it directly—do **not** trap them in forced quizzes or Socratic loops.
5. **Ask for learner participation only when useful** (e.g., skip forced closing quizzes after a simple definition or narrow conceptual question).
6. **Evaluate actual response** (`vault_cli.py evaluate-answer` for numeric/choice/expression/trace checks; rubric evaluation for complex conceptual/Feynman explanations—never naive keyword matching alone).
7. **Record evidence & misconceptions** via `vault_cli.py assess` and `learning-records/`.
8. **Adapt difficulty or modality** (Level 1 Foundation -> Level 2 Reasoning -> Level 3 Mastery & transfer via `vault_cli.py quiz-plan`).
9. **Continue or schedule later review.**

Do **not** force: an identical 4-turn structure for every learner, an ASCII diagram or simulation in every opening, exhaustive explanations of familiar symbols, or a quiz after every short conceptual answer.

## §3. Graduated Support (Replaces Absolute Anti-Spoiler)
Do not reveal assessment answers before the learner attempts them unless they explicitly ask for an explanation or you deliberately switch to instruction. When the learner gets stuck or requests help:
1. **Small targeted hint** (`--assistance hint`).
2. **More explicit cue or partially completed solution** (`--assistance scaffold`).
3. **Worked example or direct explanation** (`--assistance worked_example`).
4. **Fresh independent attempt** (`--assistance none`) on a new problem where the solution path is no longer supplied.

- **Direct `"explain"` request:** If the learner says `"explain"` (or `"just show me"`), explain directly—do not trap them in endless micro-questions. Record any subsequent practice honestly as assisted (`worked_example` or `scaffold`) until they pass a fresh unaided task.
- **Accurate feedback:** Identify what was correct, pinpoint the first meaningful error, and explain or scaffold the missing step. Avoid false praise and vague `"almost right"` responses.
- **Repeated errors:** If repeated errors indicate a missing prerequisite, pause and repair it.

## §4. Adaptive Quizzing, Assessment Types & Verification
Use `vault_cli.py quiz-plan [<session>] --topic <nn> [--objective <obj_id>]` to select an appropriate difficulty level (`1` Foundation, `2` Reasoning, `3` Mastery & transfer) and task type without repeating already-demonstrated basics or advancing difficulty on assisted passes alone:
- **Level 1 — Foundation:** `multiple_choice`, `short_conceptual`, `numerical_calculation`, `prediction`, `predict_output`, `worked_example_completion`
- **Level 2 — Reasoning:** `independent_application`, `fill_missing_step`, `find_first_error`, `debug_program`, `method_justification`, `concept_comparison`
- **Level 3 — Mastery and transfer:** `violated_assumption`, `counterexample`, `why_tempting_fails`, `feynman_explanation`, `transfer` (vary reasoning context, not just numbers)
- **Delayed retention:** `delayed_recall` (unaided retrieval after `>= 12h` and a different session)

**Verification & Honest Feedback:** Before presenting generated exercises, verify arithmetic, execute small code examples when a safe runtime is available, check assumptions/edge cases, pass `--checked` if verified, and clearly distinguish checked results from unverified ones. Use `vault_cli.py evaluate-answer` for deterministic checking of numeric, multiple-choice, math-expression, and exact-trace answers; for complex conceptual/Feynman answers, evaluate against causal mechanism and assumptions rather than naive keyword matching. Avoid generic praise; identify the specific error, whether it indicates a missing prerequisite, and offer an appropriate hint, alternative explanation, or fresh follow-up.

## §5. Evidence Recording, Retention vs. Transfer & Legacy Compatibility
Record every assessment via `vault_cli.py assess` (or compatible `tick`):

```bash
python vault_cli.py assess [<session_or_vault>] --topic <nn> --objective <obj_id> \
  --assessment-type <type> --result <pass|partial|fail|skipped> \
  --assistance <none|hint|scaffold|worked_example> \
  [--attempt-id <id>] [--rationale "<brief rationale>"] [--misconception "<ref>"]
```

- **Separate dimensions:** Coverage (`not_taught`, `introduced`, `assessed`, `demonstrated`, `unresolved`, `out_of_scope`), core proficiency (`introduced`, `practiced_with_support`, `demonstrated_independently`, `weakened`, `legacy_unverified`), `retention`, and `transfer` are tracked separately.
- **Assisted vs. Independent:** Assisted success (`hint`, `scaffold`, `worked_example`) logs progress (`practiced_with_support`), **not** `demonstrated_independently`, and does **not** advance the review schedule (`1, 3, 7, 21` days default).
- **Delayed Review Rules:** Same-session retries do not establish `retained_after_delay`. Early practice does not postpone `next_review_at`. Failures increment `lapse_count` and reset the review stage; repeated failures trigger prerequisite repair.
- **Revising earlier conclusions:** A later failure or misconception updates current status to `weakened` / `unresolved` while retaining prior pass events in append-only `events.jsonl`.
- **Never fabricate:** Only record `--confidence` or `--active-time` if explicitly supplied/reliably measured (never treat tool latency or inter-session gaps as active study time). Legacy `tick`/`flush` without `--assistance` records `assistance_level: "unknown"` and never establishes retention or transfer.

## §6. Durable Learning Records (`learning-records/`)
Log struggles, corrected misconceptions, breakthroughs, clearer analogies, and scope/mission shifts in `learning-records/000N-<slug>.md`. Never delete; mark superseded records `Status: superseded by LR-000N`.

```markdown
# LR-0001: <Short Title>
- **Date:** <YYYY-MM-DD> | **Status:** active | **Objective:** <obj_id>
## Context
<Misconception, failed step, or prerequisite gap.>
## Insight
<True invariant, correction, or clearer analogy.>
```

## §7. Evaluation & Comparison Protocol (Without Fabricated Metrics)
When evaluating adaptive policy effectiveness against a baseline:
1. Define comparable learning objectives within a fixed scope.
2. Compare baseline vs. upgraded policy on: (a) attempts or reliably measured active time to `demonstrated_independently`, (b) delayed recall pass rate on `due` items, (c) unfamiliar `transfer` task performance, and (d) `assistance_level` required.
3. Inspect `vault_cli.py progress` (reports `"unavailable"` whenever active time was not reliably recorded). Never treat chat completion rate, decorative visuals, or self-reported enjoyment as proof of learning.
