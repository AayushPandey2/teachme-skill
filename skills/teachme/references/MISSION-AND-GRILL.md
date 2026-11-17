# Phases 1–3: Frontier Grilling, Research Workflow & Vault Scaffold

Formatting, linking, and CLI laws live in `SKILL.md §B–§C` only.

## Phase 1 — Frontier Grilling & Mission Lock
- **Facts are yours, decisions are the user's.** Never ask about specs, history, or benchmarks — research them in Phase 2. Never dump a long form.
- Unless `--auto` / `defaults` / `go` was passed, ask exactly these 4 questions in ONE turn and wait:

```markdown
Before I research and build your vault at `<VAULT_ROOT>/<topic-slug>/`, let's lock the mission (reply e.g. `1 working familiarity, 2 defaults`, or `defaults` / `go`):

1. ❓ **Prior Knowledge:** How much background do you have in `<topic>`?
   ➡️ *Default:* **No prior knowledge** *(build from absolute zero; define every symbol and term).*
   *Alternatives:* Basic intuition | Working familiarity | Advanced (skip fundamentals).
2. ❓ **Depth & Coverage:** How thoroughly should we cover it?
   ➡️ *Default:* **Absolute mastery covering all topics** *(zero-omission syllabus, one file per subtopic, full derivations).*
   *Alternatives:* Core fundamentals | Exam / interview prep | Practical implementation.
3. ❓ **Mastery Goal:** What defines success?
   ➡️ *Default:* **Complete first-principles mastery** *(derive every formula, explain without jargon, solve Tier 3 drills).*
4. ❓ **Seed Notes / Scope (Optional):** Any syllabus, textbook, notes, or exclusions?
   ➡️ *Default:* **None** *(full syllabus anchored on canonical primary sources).*
```

Write `00-MISSION.md` (record defaults verbatim so Phase 6 calibrates Turn 1 to a beginner-safe scalar trace):

```markdown
# Mission: <Topic Title>

- **Vault Path:** `<VAULT_ROOT>/<topic-slug>/` | **Created:** <YYYY-MM-DD> | **Status:** Active
- **Prior Knowledge Baseline:** No prior knowledge (Zero-baseline first principles)
- **Coverage & Depth Mode:** Absolute mastery covering all topics (Zero-omission syllabus)

## 1. Target Outcome
<Complete first-principles mastery of <Topic>, or the user's custom outcome.>

## 2. Success Criteria
- [ ] Explain every core mechanism from first principles without jargon.
- [ ] Derive every governing equation step-by-step from base axioms.
- [ ] Compare against the top 2–3 alternatives (complexity, trade-offs, failure modes).
- [ ] Diagnose Tier 3 edge cases and boundary failures.

## 3. Curriculum Milestones
1. <Prerequisites, Origin & Core Mental Model> 2. <Internal Mechanics> 3. <Derivations, Trade-offs & Edge Cases> 4. <Comparative Landscape & Applied Mastery>

## 4. Scope Boundaries
- **In Scope:** <Full syllabus or custom scope> | **Out of Scope:** <None or exclusions>

## 5. User Seed Inputs
- <Syllabus / textbook / questions provided, or "None provided.">
```

## Phase 2 — Primary-Source Research
1. Load `references/RESEARCH-TOOLCHAIN.md` (retrieval rules + `01-RESOURCES.md` / `02-DEEP-RESEARCH.md` templates).
2. Write a falsifiable Research Brief (4–6 questions tied to mission milestones).
3. Decompose the topic into an **exhaustive numbered syllabus** (`01`…`NN`) in topological prerequisite order — every subtopic becomes one `topics/<nn>-<slug>.md`.
4. Keep raw notes in `scratchpad/raw-research.md`; write `01-RESOURCES.md` then `02-DEEP-RESEARCH.md`.

## Phase 3 — Deterministic Vault Scaffold (Zero LLM Boilerplate)
**Check Operating Mode (`SKILL.md §A`):**
- **Vault-Native Mode (`.obsidian/` or `mode: vault-native`):** Do NOT scaffold `topics/`, `00-MOC-INDEX.md`, or `01`–`09` at the Obsidian vault root. Instead run `vault_cli.py discover`, `search --query "<topic>"`, and `plan --topic "<topic>"` (which resolves placement, tags, MOC selection/creation, and Mermaid diagrams with `plan_id` + `expected_hashes`), preview via `--dry-run`, execute `apply --plan <plan_id>` (or `generate --apply`), keep `scratchpad/` inside `<vault>/.teachme/sessions/<topic-slug>/`, and finish with `vault_cli.py audit` (`references/VAULT-NATIVE.md`).
- **Standalone Mode:** Save the syllabus as `scratchpad/subtopics.json`, then run `vault_cli.py init`:

```json
[
  {"slug": "01-<slug>", "title": "<Title>", "depends_on": [], "contrasts_with": []},
  {"slug": "02-<slug>", "title": "<Title>", "depends_on": ["topic-01"], "contrasts_with": []}
]
```

```bash
python vault_cli.py init "<VAULT_ROOT>/<topic-slug>" --topic "<Topic Title>" --subtopics "<VAULT_ROOT>/<topic-slug>/scratchpad/subtopics.json"
```

This creates `topics/`, `atomic/`, `learning-records/`, `scratchpad/`, `00-SESSION-STATE.md` (`<60` lines), `00-MOC-INDEX.md`, `00-GRAPH.json`, and YAML-valid topic stubs (existing files are never overwritten). Then continue with Phase 4 (`references/STUDY-AND-GLOSSARY.md`).
