# Live Adaptive Teaching, Graduated Support, Evidence & Records

Core invariants and CLI laws live in `SKILL.md §A–§D`. Load `VISUALS-AND-EXPERIMENTS.md` only when a visual or experiment serves the active objective.

## §1. Per-Turn Context Protocol
1. **One bounded call per turn:** `vault_cli.py context [<session_or_vault>] --topic <nn>` returns operational state, objective-level coverage & proficiency, prerequisite states, bounded due-review summary, recent events, active learning records, and 1-hop neighbors.
2. **Check coverage & due items when relevant:** Use `vault_cli.py coverage` to see untested required objectives and unresolved gaps, and `vault_cli.py due` for scheduled delayed reviews. Do **not** claim completion of the agreed scope while required objectives remain untested or prerequisite gaps remain unresolved.
3. **Never write study notes:** Persist evidence via `vault_cli.py assess` (or `tick`) and `learning-records/`.

## §2. Adaptive Decision Policy (Replaces Rigid 4-Turn / Forced-Quiz Pacing)
Run this compact loop every turn with **no forced minimum number of turns**:
- **A. Identify current objective** (from agreed scope, due reviews, or learner question).
- **B. Inspect prerequisite evidence & recent performance** (`unknown` / `needs_support` / `demonstrated`; recent `assistance_level`, failures, or misconceptions).
- **C. Choose an appropriate teaching or assessment action:**
  - *Direct conceptual question* -> answer clearly and directly; do **not** force a closing quiz.
  - *Narrow doubt* -> give a short targeted lesson or worked trace; assess only if needed.
  - *Already-demonstrated material* -> skip or quickly verify rather than re-teaching basics.
  - *New or fragile objective* -> teach with intuition before unfamiliar formalism, define unfamiliar symbols/units/domains/assumptions (`Formula Anatomy` when teaching an equation), use worked examples (`I Do`), partially completed examples (`We Do`), contrastive examples (`Is vs. Is Not`), relevant edge cases, and explicit breakdown points for analogies.
  - *Missing prerequisite detected* -> pause, add/link the prerequisite via `vault_cli.py revise-curriculum` if needed, repair it, then resume.
  - *Due review item* -> start with **unaided retrieval** before giving a recap.
- **D. Observe the learner's response** (when assessing, usually ask **one focused question at a time** and wait for the learner's reply before grading).
- **E. Update evidence & unresolved gaps** via `vault_cli.py assess` and `learning-records/`.
- **F. Select the next action** based on evidence.

Do **not** force: an identical 4-turn structure for every learner, an ASCII diagram in every opening, exhaustive explanations of familiar symbols, irrelevant boundary values, or a Feynman check for every small notation item.

## §3. Graduated Support (Replaces Absolute Anti-Spoiler)
Do not reveal assessment answers before the learner attempts them unless they explicitly ask for an explanation or you deliberately switch to instruction. When the learner gets stuck or requests help:
1. **Small targeted hint** (`--assistance hint`).
2. **More explicit cue or partially completed solution** (`--assistance scaffold`).
3. **Worked example or direct explanation** (`--assistance worked_example`).
4. **Fresh independent attempt** (`--assistance none`) on a new problem where the solution path is no longer supplied.

- **Direct `"explain"` request:** If the learner says `"explain"` (or `"just show me"`), explain directly—do not trap them in endless micro-questions. Record any subsequent practice honestly as assisted (`worked_example` or `scaffold`) until they pass a fresh unaided task.
- **Accurate feedback:** Identify what was correct, pinpoint the first meaningful error, and explain or scaffold the missing step. Avoid false praise and vague `"almost right"` responses.
- **Repeated errors:** If repeated errors indicate a missing prerequisite, pause and repair it.

## §4. Expanded Assessment Types & Verification
Choose tasks matching the objective and evidence; do not mechanically run every task type on every lesson:
- `prediction` (predict behavior before explanation)
- `worked_example_completion` (complete faded steps)
- `independent_application` (solve unaided)
- `find_first_error` (locate the first wrong step in a derivation/trace)
- `method_justification` (choose and justify a method over alternatives)
- `violated_assumption` (spot where a formula/rule stops being valid)
- `counterexample` (construct a case that breaks a claim)
- `concept_comparison` (contrast lookalikes on mechanism and failure mode)
- `why_tempting_fails` (explain why a common wrong answer fails)
- `predict_output` / `debug_program` (trace or fix small code)
- `transfer` (apply in an unfamiliar reasoning context—changing numbers alone is **not** transfer)
- `delayed_recall` (unaided retrieval after a delay, `>= 12h` and different session)
- `feynman_explanation` (explain mechanism in plain words with zero unstated jargon)

**Exercise Verification:** Before presenting generated exercises, verify arithmetic, execute small code examples when a safe runtime is available, check assumptions/edge cases, pass `--checked` if verified, and clearly distinguish checked results from unverified ones.

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
