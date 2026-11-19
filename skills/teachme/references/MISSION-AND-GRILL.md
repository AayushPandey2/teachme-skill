# Source Resolution, Fast Calibration, Diagnostics & Minimal Curriculum Init

Core routing, source-independence, and state laws live in `SKILL.md §A–§D`. Start teaching quickly — avoid mandatory exhaustive upfront research, oversized curriculum planning, and unnecessary intake questions.

## Phase 0 — Load Existing State & Resolve Permitted Sources
1. **Check existing learning state first:** Run `vault_cli.py state` (or with `--session <slug>`) to detect an active/resumable session before asking questions.
2. **Resolve permitted sources automatically:** Run:

```bash
python vault_cli.py resolve-sources --topic "<Topic>" [--session <slug>] [--no-web]
```

3. **Act on the selected mode (`vault` | `hybrid` | `web`):**
   - `vault`: Existing Obsidian note sections sufficiently cover the topic/objectives. Teach directly from `matched_sections` and `related_notes` without unnecessary web research (verify consequential claims or contradictions if needed).
   - `hybrid`: Existing notes partially cover the topic. Teach covered areas from `matched_sections` and load `references/RESEARCH-TOOLCHAIN.md` ONLY to selectively research `missing_coverage`.
   - `web`: No suitable notes or no accessible vault. Load `references/RESEARCH-TOOLCHAIN.md` (if web/browser/docs tools exist) for lightweight fast-start research, or begin with available knowledge and explicit limitations if browsing tools are unavailable.

## Phase 1 — Lightweight Calibration (Only When Material)
1. **Use known context first:** Inspect `state`, `scratchpad/mission.json`, retrieved vault context, and the user's prompt before asking anything.
2. **Ask only for missing info that materially changes the path** (never a rigid 4-question form):
   - **Goal & agreed scope** (what is in scope vs excluded; never promise "zero gaps" across an unbounded domain).
   - **Background** (relevant prior concepts or tools).
   - **Time budget / deadline** or **explanation constraints** (only when relevant, e.g. exam in 20 minutes, code-first).
3. **`--auto` / `defaults` / `go`:** Skip intake immediately with explicit baseline assumptions and refine from diagnostic/teaching evidence.
4. **Persist calibration:** Record into `scratchpad/mission.json` via `vault_cli.py calibrate`:

```bash
python vault_cli.py calibrate "<SESSION_OR_VAULT>" --goal "<goal>" --in-scope "<a,b>" --out-of-scope "<c>" --background "<bg>" [--time-budget 20] [--language "<lang>"]
```

## Phase 2 — Brief Adaptive Diagnostic (Only When Useful)
For substantial new topics (unless skipped, already evidenced, or the learner asks a narrow direct question):
- Deliver **2–4 small diagnostic tasks**, **one at a time**, stopping early as soon as the starting level is clear.
- If the learner skips or adjusts, skip immediately and mark unassessed prerequisites `unknown` — **never** `demonstrated`.
- Self-reported confidence is calibration input only, never mastery evidence.
- Persist prerequisite evidence via:

```bash
python vault_cli.py calibrate "<SESSION_OR_VAULT>" --diagnostic-status completed --diagnostic-tasks 2 --prereq "variables=demonstrated:Predicted mutation"
```

## Phase 3 — Compact Acyclic Curriculum & Minimal Operational Init
1. Build a **compact, right-sized acyclic DAG** in `scratchpad/subtopics.json` with assessable `objectives` per topic node (no bloated upfront syllabi):

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

2. Initialize operational state only (never study-note scaffolds and never `raw-research.md` by default):

```bash
python vault_cli.py init "<SESSION_OR_VAULT_PATH>" --topic "<Topic Title>" --subtopics "<SESSION_DIR>/scratchpad/subtopics.json" --goal "<Goal>"
```

- **Dynamic curriculum revision:** Insert discovered prerequisites anytime with `vault_cli.py revise-curriculum` (validates DAG acyclicity and preserves IDs, evidence, and resume state).
- **Validate & Teach:** Run `vault_cli.py validate-state "<SESSION_OR_VAULT_PATH>"` and immediately start live adaptive teaching (`references/RETENTION-AND-RECORDS.md`).
