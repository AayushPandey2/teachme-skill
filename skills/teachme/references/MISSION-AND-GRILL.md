# Phases 1–3: Frontier Grilling, Curriculum Research & State Initialization

Core routing and state laws live in `SKILL.md §A–§D`.

## Phase 1 — Frontier Grilling & Mission Lock
- **Facts are yours, decisions are the user's.** Never ask about specs, history, or benchmarks — research them in Phase 2. Never dump a long form.
- Unless `--auto` / `defaults` / `go` was passed, ask exactly these 4 questions in ONE turn and wait:

```markdown
Before I map your learning path for `<Topic>`, let's calibrate the session (reply e.g. `1 working familiarity, 2 defaults`, or `defaults` / `go`):

1. ❓ **Prior Knowledge:** How much background do you have in `<topic>`?
   ➡️ *Default:* **No prior knowledge** *(build from absolute zero; define every symbol and term).*
   *Alternatives:* Basic intuition | Working familiarity | Advanced (skip fundamentals).
2. ❓ **Depth & Coverage:** How thoroughly should we cover it?
   ➡️ *Default:* **Absolute mastery covering all topics** *(zero-omission syllabus, full derivations, adversarial checks).*
   *Alternatives:* Core fundamentals | Exam / interview prep | Practical implementation.
3. ❓ **Mastery Goal:** What defines success?
   ➡️ *Default:* **Complete first-principles mastery** *(derive every formula, explain without jargon, solve Tier 3 drills).*
4. ❓ **Seed Materials / Scope (Optional):** Any syllabus, textbook, existing notes, or exclusions?
   ➡️ *Default:* **None** *(full syllabus anchored on canonical primary sources).*
```

Save the calibration baseline into `scratchpad/mission.json` (and optionally `00-MISSION.md` inside the operational session directory — never as a study note) so every resumed turn preserves `prior_knowledge`, `depth_mode`, `goal`, `scope`, and `language`:

```json
{
  "topic": "<Topic Title>",
  "created": "<YYYY-MM-DD>",
  "prior_knowledge": "No prior knowledge (Zero-baseline first principles)",
  "depth_mode": "Absolute mastery covering all topics",
  "goal": "<Mastery goal>",
  "in_scope": "<Full syllabus or custom scope>",
  "out_of_scope": "<None or exclusions>",
  "seed_inputs": []
}
```

## Phase 2 — Primary-Source Curriculum Planning
1. Load `references/RESEARCH-TOOLCHAIN.md` for source hierarchy and provenance rules.
2. If an Obsidian vault is connected in Vault-Native Mode, optionally run `vault_cli.py search <vault> --query "<topic>"` to see what existing notes the learner already has (read-only learning context only).
3. Decompose the topic into an **acyclic curriculum syllabus** (`01`…`NN`) in topological prerequisite order with `depends_on`, `unlocks`, `contrasts_with`, `objective`, `anchor`, `key_concepts`, and `key_equations`.
4. Capture any raw research drafts in `scratchpad/raw-research.md` and source URLs in `scratchpad/ingested-sources.json` — never generate `01-RESOURCES.md`, `02-DEEP-RESEARCH.md`, `00-MOC-INDEX.md`, or `topics/*.md`.

## Phase 3 — Deterministic Operational State Init
Save the curriculum list as `scratchpad/subtopics.json`:

```json
[
  {
    "slug": "01-<slug>",
    "title": "<Title>",
    "depends_on": [],
    "contrasts_with": [],
    "objective": "<1-line learning objective>",
    "anchor": "<2-3 sentence 30-second anchor + mental hook>",
    "key_concepts": ["<concept>"],
    "key_equations": ["<LaTeX equation>"]
  }
]
```

Run `vault_cli.py init`:

```bash
python vault_cli.py init "<SESSION_OR_VAULT_PATH>" --topic "<Topic Title>" --subtopics "<SESSION_DIR>/scratchpad/subtopics.json"
```

- **Standalone Mode:** Pass `<STATE_ROOT>/<topic-slug>`.
- **Vault-Native Mode:** Passing the connected Obsidian vault root automatically isolates state inside `<vault>/.teachme/sessions/<topic-slug>/`.

This creates **operational state only**: `learning-records/`, `scratchpad/curriculum.json`, `00-SESSION-STATE.md` (`<60` lines), and `00-GRAPH.json` (curriculum dependency graph). Never scaffold `topics/`, `atomic/`, or `00-MOC-INDEX.md`. Then proceed directly to Phase 4 (`references/RETENTION-AND-RECORDS.md`).
