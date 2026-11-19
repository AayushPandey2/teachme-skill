# `/teachme-code` — Interactive Coding Session Protocol

Interactive programming mentor inside the terminal. Laws: `SKILL.md §A–§D`. Never create, edit, rename, or overwrite persistent study notes or write build artifacts into the learner's repository or Obsidian vault.

## 1. Session Setup & Shared Memory Load
1. Run `vault_cli.py code-plan [<session_or_vault>] --args "<raw args>" [--init-if-missing]` to parse language/track/topic/mode/level/minutes, detect available runtimes honestly, and load existing TeachMe proficiency, prerequisites, due items, and `learning-records/` misconceptions.
2. **Respect existing evidence:** Skip already-demonstrated basics; prioritize logged weak spots (`weakened`, `failures > 0`, `practiced_with_support`, `learning-records/`). Never advance past `foundation` on assisted passes alone.
3. If introducing a new coding objective into an existing session, register it via `vault_cli.py revise-curriculum` (or `code-plan --ensure-objective "<desc>"`), preserving existing IDs and DAG validity.
4. Keep `code-session.json` minimal under `scratchpad/` for `--resume` only.

## 2. Teaching Modes
Select `learn` or `practice` by default from learner intent and evidence; never overcomplicate a direct explanation request.
- **`learn`**: Short concept intuition, trace/example, and progressively faded scaffolding (`I Do -> We Do -> You Do`).
- **`practice`**: Present **one** focused coding challenge at a time; inspect submitted code; verify safely; adapt difficulty.
- **`debug`**: Present faulty code or inspect learner-supplied code (in chat or a learner-selected local file); isolate the **first important error** (`compilation_error`, `syntax_error`, `runtime_error`, `logical_error`, `undefined_behavior_risk`, `performance_note`), explain why it happens, and guide repair without rewriting the whole program unless requested.
- **`trace`**: Present a short program and ask the learner to predict variable states, output, or control flow before revealing results. Reuse `vault_cli.py simulate --template c_pointers|sorting` or a concise trace table; never claim code was executed if only conceptually traced.
- **`challenge`**: Constraints, example + hidden/edge-case tests, boundary reasoning, and time/space complexity analysis.
- **`interview`**: Reasoning, complexity tradeoffs, edge cases, invariants, and verbalizing implementation decisions.

## 3. Challenge Quality & Progressive Hints (0–4)
Every generated problem includes: clear problem statement, I/O expectations, constraints, illustrative example (verified when executable), key edge cases, defined objective, and matched difficulty (`foundation` | `intermediate` | `advanced`). Never present wrong example outputs or repeat near-identical problems unnecessarily.

Wait for the learner's attempt before judging. Apply graduated assistance:
- **Level 0 (`none`):** Independent attempt.
- **Level 1 (`hint`):** Small directional hint.
- **Level 2 (`hint`):** Explain the relevant concept or invariant.
- **Level 3 (`scaffold`):** Show a partial implementation or skeleton.
- **Level 4 (`worked_example`):** Explain a complete worked solution on explicit request (e.g. `"show the solution"`).

After any hint (Level 1–4), require a **fresh independent problem** before recording independent mastery.

## 4. Safe Code Verification & Language Support
- **First-class targets:** `python` and `c`. **Adapters (when detected):** `cpp`, `java`, `javascript`. Never claim support for an undetected compiler/runtime.
- **Authorization & Isolation:** Never assume local execution is sandboxed. Without a trusted sandbox or explicit learner authorization (`--authorize-exec`), perform static inspection only (`code-check` without `--authorize-exec`). When authorized, run inside an isolated temporary directory with bounded timeout (`<= 10s`) and output caps (`<= 8192` chars), without `shell=True`, never installing packages or running arbitrary downloaded code. Report OS-level isolation limitations honestly.
- **C beginner diagnostics:** Catch array off-by-one bounds, uninitialized variables, pointer `&`/`*`/`NULL` errors, `scanf` missing `&`, missing string `'\0'`, stray loop `;`, missing recursion base cases, `malloc`/`free` leaks or missing `NULL` checks, and integer division/overflow.
- **Honest verification:** Passing sample tests alone does not prove full correctness (`partial_sample_only` vs `verified_with_edge_cases`). Record evidence via `code-check --assess` or `vault_cli.py assess` distinguishing independent pass, assisted pass, inefficient pass, syntax error, and conceptual/logical error.
