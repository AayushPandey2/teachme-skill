# Documented Adaptive Teaching Policy Scenarios (A–J)

> **Note:** These scenarios specify expected routing, teaching actions, and operational state transitions under the upgraded TeachMe policy. They are behavioral policy specifications, **not** empirical proof of real learner outcomes.

---

## Scenario A: Beginner Asks to Learn C Pointers
- **User Input:** `/teachme C pointers` (user knows basic Python variables/lists; never used manual memory).
- **Expected Routing:** Teaching intent -> load `SKILL.md`, `MISSION-AND-GRILL.md` (source resolution + lightweight calibration), then `RETENTION-AND-RECORDS.md` (and `VISUALS-AND-EXPERIMENTS.md` if a trace/diagram helps). Do **not** load `NOTE-SKILL-HANDOFF.md` or detect/invoke external note skills.
- **Next Teaching Action:**
  1. Run lightweight calibration (confirm goal/scope and check only missing prerequisites, e.g., variable binding vs aliasing).
  2. Optionally run 1–2 narrow diagnostic probes (`calibrate --prereq`).
  3. Teach with a named-variable/address/target trace table (`VISUALS-AND-EXPERIMENTS.md` — never a misleading physical memory layout), introducing `&` and `*` with concrete scalar examples before pointer arithmetic.
- **State Effects:**
  - `scratchpad/mission.json` records `prior_knowledge`, agreed scope, and prerequisite states (`unknown` / `needs_support` / `demonstrated`).
  - `scratchpad/curriculum.json` & `00-GRAPH.json` initialize objectives (e.g., `obj-01-01` address-of/dereference).
  - `assess` logs events with `assistance_level` and `assessment_type` (e.g. `predict_output`).

---

## Scenario B: Experienced Learner Demonstrates Prerequisites and Skips Basics
- **User Input:** *"Teach me backpropagation; I already know multivariable chain rule and matrix multiplication."*
- **Expected Routing:** Teaching intent -> `MISSION-AND-GRILL.md` -> `RETENTION-AND-RECORDS.md`.
- **Next Teaching Action:**
  1. Verify rather than blindly trust self-report: run 1–2 quick diagnostic tasks (e.g., partial derivative of a composite scalar/matrix term).
  2. Once passed unaided, stop diagnostic early, mark prerequisites `demonstrated`, skip basic calculus lessons, and jump directly to reverse-mode computational graphs / Jacobian-vector products.
- **State Effects:**
  - `calibrate` records prerequisites as `demonstrated` with diagnostic evidence.
  - Skipped foundational objectives (if outside agreed scope) are marked `in_scope: false` / `out_of_scope` or bypassed without fabricating delayed retention or transfer.

---

## Scenario C: Learner Says `"explain"` After a Failed Attempt
- **User Input:** Learner misses a question on why learning rate $\eta$ too large diverges, and replies: `"explain"`.
- **Expected Routing:** Stay in live teaching (`RETENTION-AND-RECORDS.md §3` Graduated Support). Do **not** loop on anti-spoiler micro-questions.
- **Next Teaching Action:**
  1. Log the failed attempt (`assess --result fail --assistance none`).
  2. Explain directly and clearly (where the step overshoots the minimum, optional computed 1D loss curve + step trace if helpful).
  3. Follow up with a **fresh** problem later where the answer path is no longer supplied before claiming independent demonstration.
- **State Effects:**
  - `events.jsonl` logs the `fail` event and updates `review-state.json` (`lapse_count += 1`).
  - Direct explanation does **not** record a pass; only a subsequent attempt records `worked_example`/`scaffold` or (on a fresh problem) `none`.

---

## Scenario D: Learner Gets a Correct Answer Only After a Worked Example
- **User Input:** Learner succeeds on a similar problem immediately after walking through a worked example (`I Do` / explicit cue).
- **Expected Routing:** Live teaching (`RETENTION-AND-RECORDS.md §3, §5`).
- **Next Teaching Action:** Acknowledge what was solved correctly, record the success honestly with `--assistance worked_example` (or `scaffold`), and queue a fresh unaided problem before treating the objective as independently demonstrated.
- **State Effects:**
  - `events.jsonl` records `result: "pass"`, `assistance_level: "worked_example"`.
  - Objective `proficiency.status` becomes `"practiced_with_support"` and `coverage_status` becomes `"assessed"` (**never** `"demonstrated_independently"` or `"mastered"`).
  - `review-state.json` does **not** advance the retention stage; `handoff` will list it under `concepts_introduced`, not `objectives_demonstrated`.

---

## Scenario E: Learner Returns After a Delay and Fails Recall
- **User Input:** `/teachme-review linear-classifiers` 5 days after passing `obj-01-01` independently.
- **Expected Routing:** `cmd-review.md` -> `RETENTION-AND-RECORDS.md`.
- **Next Teaching Action:**
  1. Run `vault_cli.py due` and `vault_cli.py context` (read-only; opening session mutates nothing).
  2. Prompt **unaided retrieval first** (`delayed_recall`) before giving any recap.
  3. On failure: record `result: "fail"`, identify the first error, teach/scaffold (checking if a prerequisite gap caused the lapse), then test with a fresh problem.
- **State Effects:**
  - `events.jsonl` retains the earlier independent pass AND appends the new `fail` event.
  - Objective `proficiency.status` becomes `"weakened"`, `coverage_status` becomes `"unresolved"`, and `prior_independent_success_at` remains preserved for auditability.
  - `review-state.json` increments `lapse_count`, resets `stage = 0`, and sets `next_review_at = now + 1 day` (or immediate on repeated failures).

---

## Scenario F: Image Search Exists, But Image Inspection Does Not
- **User Input:** Learner asks to recognize a hardware interface or anatomical structure; host exposes web/image search metadata only, with no visual inspection tool.
- **Expected Routing:** `VISUALS-AND-EXPERIMENTS.md §2–§3`.
- **Next Teaching Action:**
  1. Inspect credible source page text if available.
  2. Do **not** claim visual verification from thumbnail/metadata alone.
  3. Either provide a clear labeled text/structural fallback or present source attribution while explicitly marking inspection unverified.
- **State Effects:**
  - If recorded via `record-media`, `verification_status` MUST be `"metadata_only_unverified"` (never `"inspected_verified"`), and `license` defaults to `"unknown"` unless explicitly confirmed from the source page.

---

## Scenario G: No Media or Browser Tools Are Available
- **User Input:** Running inside a plain-text terminal CLI with no image display, plot viewer, or browser rendering.
- **Expected Routing:** `VISUALS-AND-EXPERIMENTS.md §2` Progressive Fallback.
- **Next Teaching Action:** Never claim rich media was displayed. Provide a concise text/trace-table/numeric-table fallback (e.g., small `(w, L(w), dL/dw)` table for gradient descent or variable/address/target table for pointers) and continue teaching smoothly without asking the user to install an MCP.
- **State Effects:** Standard teaching/assessment state updates proceed normally; optional `record-media` entries include `fallback_text`.

---

## Scenario H: Learner Requests Teaching Followed by Revision Notes
- **User Input:** *"Teach me Bayes' rule, then make revision notes on what we covered."*
- **Expected Routing:** Mixed request (`SKILL.md §D`): teach first in TeachMe, then offer/execute an optional provider-independent note-skill handoff ONCE at the boundary via `NOTE-SKILL-HANDOFF.md`.
- **Next Teaching Action:**
  1. Teach Bayes' rule adaptively and record honest assessment evidence (`assess`).
  2. Run `vault_cli.py handoff --request "revision notes on what we covered" --scope "covered_plus_pending"`.
  3. Discover and hand off to a compatible installed note-writing skill if available, or return a Blocked / Unavailable Note Handoff with the compact context summary. Never generate study notes in chat as a fallback.
- **State Effects:**
  - `handoff` exports `schema_version: "1.1"` envelope separating `concepts_introduced`, `objectives_demonstrated`, `untested_or_unresolved_gaps`, `misconceptions_and_corrections`, and `resume_location`.
  - Handoff never advances mastery or modifies existing notes.

---

## Scenario I: Learner Has Only 20 Minutes Before an Exam
- **User Input:** *"I have an exam in 20 minutes on eigenvalues and eigenvectors — help me focus on what's most likely tested."*
- **Expected Routing:** `MISSION-AND-GRILL.md` -> `RETENTION-AND-RECORDS.md`.
- **Next Teaching Action:**
  1. Record `time_budget_minutes: 20` and narrow `in_scope` / `out_of_scope` via `calibrate` / `init`.
  2. Skip non-essential derivations (`out_of_scope` / optional objectives); prioritize high-leverage required objectives (geometric intuition, $\det(A - \lambda I)=0$, quick sanity checks like trace/determinant) and short active checks (`find_first_error`, `independent_application`).
  3. Explicitly state at the end which required objectives were demonstrated vs. left untested due to the 20-minute scope.
- **State Effects:**
  - `mission.json` stores `time_budget_minutes: 20` and narrow `in_scope`/`out_of_scope`.
  - `coverage` shows only the agreed in-scope required objectives as complete or explicitly lists untested ones.

---

## Scenario J: A Later Misconception Invalidates an Earlier Broad Conclusion
- **User Input:** Learner earlier passed a basic dot-product calculation (`obj-01-01`), then later reveals a fundamental misconception (e.g., claiming `a · b = 0` means one vector must be zero, failing `violated_assumption` / `counterexample`).
- **Expected Routing:** `RETENTION-AND-RECORDS.md §5–§6`.
- **Next Teaching Action:**
  1. Record the failure with `--misconception LR-000N` and log `learning-records/000N-<slug>.md`.
  2. If a missing prerequisite (e.g. orthogonality/angle intuition) is exposed, insert it via `revise-curriculum` without erasing earlier evidence.
  3. Address the misconception directly with a counterexample (`(1,0) · (0,1) = 0`), then re-verify with a fresh task.
- **State Effects:**
  - `events.jsonl` retains the original pass event AND appends the failure event.
  - `derive_objective_evidence` marks `proficiency.status = "weakened"`, `coverage_status = "unresolved"`, `current_weakness` populated, AND `prior_independent_success_at` preserved (history is never silently erased).
