# Calibration, Diagnostics & Curriculum Initialization

Core routing and state laws live in `SKILL.md §A–§D`.

## Phase 1 — Lightweight Calibration (Not a Rigid 4-Question Form)
1. **Use known context first:** Inspect `vault_cli.py state` and `scratchpad/mission.json` (plus the user's prompt) before asking anything.
2. **Ask only for missing info that materially changes the path:**
   - **Goal & agreed scope** (what is in scope vs excluded; never promise "zero gaps" across an unbounded domain).
   - **Background** (relevant prior concepts or tools).
   - **Time available or deadline** (when relevant, e.g. 20-minute exam prep vs open-ended study).
   - **Preferred language or explanation constraints** (when relevant, e.g. concise/code-first/no rich media).
3. **Retain `--auto` / `defaults` / `go`:** When passed, start immediately with explicit baseline assumptions (beginner-friendly, core scope, plain-English definitions first) and refine from diagnostic evidence.
4. **Persist calibration:** Record into `scratchpad/mission.json` via `vault_cli.py calibrate`:

```bash
python vault_cli.py calibrate "<SESSION_OR_VAULT>" --goal "<goal>" --in-scope "<a,b>" --out-of-scope "<c>" --background "<bg>" [--time-budget 20] [--language "<lang>"]
```

## Phase 2 — Adaptive Diagnostic & Prerequisite Tracking
For substantial new topics (unless skipped or already evidenced):
- Offer or begin a **short adaptive diagnostic** of **2–4 small tasks**, delivered **one at a time**.
- **Stop early** once enough evidence is available to choose the starting level.
- **Allow skipping/changing:** If the learner asks to skip or adjust, skip immediately and mark unassessed prerequisites as `unknown` (untested) — **never** as `demonstrated` or mastered.
- **Self-reported confidence** is calibration input only, **never** mastery evidence.
- **Diagnose narrowly:** Isolate the exact bottleneck (e.g., for gradient descent, test substitution, slope sign interpretation, or vector dimensions separately instead of re-explaining all of optimization).
- **Evidence-based prerequisite states** (`unknown`, `needs_support`, `demonstrated`):
  - An isolated correct guess does not establish broad prerequisite competence.
  - Record prerequisite evidence via:

```bash
python vault_cli.py calibrate "<SESSION_OR_VAULT>" --diagnostic-status completed --diagnostic-tasks 2 --prereq "variables=demonstrated:Predicted mutation" --prereq "hex_addresses=unknown:Skipped by learner"
```

## Phase 3 — Primary-Source Curriculum & Objective-Level Init
1. Load `references/RESEARCH-TOOLCHAIN.md` only when researching/verifying primary sources.
2. In Vault-Native Mode, optionally run `vault_cli.py search <vault> --query "<topic>"` to inspect existing notes read-only.
3. Build an **acyclic DAG** in `scratchpad/subtopics.json` with assessable `objectives` per topic node:

```json
[
  {
    "slug": "01-<slug>",
    "title": "<Title>",
    "required": true,
    "in_scope": true,
    "depends_on": [],
    "contrasts_with": [],
    "objective": "<summary objective>",
    "anchor": "<2-3 sentence mental hook>",
    "key_concepts": ["<concept>"],
    "key_equations": ["<LaTeX equation>"],
    "objectives": [
      {
        "id": "obj-01-01",
        "description": "<assessable objective>",
        "required": true,
        "in_scope": true,
        "prerequisite_refs": [],
        "assumptions": ["<valid domain/assumption>"],
        "expected_assessments": ["explain_concept", "apply_procedure"]
      }
    ]
  }
]
```

4. Initialize operational state only (never `topics/`, `atomic/`, or `00-MOC-INDEX.md`):

```bash
python vault_cli.py init "<SESSION_OR_VAULT_PATH>" --topic "<Topic Title>" --subtopics "<SESSION_DIR>/scratchpad/subtopics.json" --goal "<Goal>"
```

- **Dynamic curriculum revision:** If a missing prerequisite is discovered later, insert it with `vault_cli.py revise-curriculum` (validates DAG acyclicity and references while preserving stable IDs, prior evidence, and resume location).
- **Validate:** `vault_cli.py validate-state "<SESSION_OR_VAULT_PATH>"`. Proceed to live adaptive teaching (`references/RETENTION-AND-RECORDS.md`).
