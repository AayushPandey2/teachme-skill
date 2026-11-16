---
name: teachme
description: "Unified end-to-end learning, deep primary-source research, frontier grilling, Socratic teaching, and structured Markdown note-taking pipeline. Invoke with /teachme <topic> or when the user asks to deeply research, learn, build a study guide, generate Cornell notes, create Zettelkasten cards, or master any topic from first principles into a central vault (<VAULT_ROOT>/<topic-slug>/, defaulting to ~/notes)."
---

# Unified `/teachme` Master Pipeline

When invoked as `/teachme <topic>` (or when the user asks to deeply research, learn, and take complete notes on a topic), execute this **6-Phase Stateful Pipeline** inside the user's **central knowledge vault** (`<VAULT_ROOT>/<topic-slug>/`).

Do NOT dump everything in a single wall of chat text. Write clean, pure Markdown files into `<VAULT_ROOT>/<topic-slug>/` while guiding the user interactively in chat.

---

## Non-Negotiable Operating Laws & Path Resolution

1. **Central Vault Only (Dynamic `<VAULT_ROOT>` Resolution):** Always write all generated files to `<VAULT_ROOT>/<topic-slug>/`, regardless of which workspace is currently open, and never scatter notes inside random project folders. Resolve `<VAULT_ROOT>` dynamically before any read/write in every command (`/teachme`, `/teachme-expand`, `/teachme-verify`, `/teachme-ingest`, `/teachme-distill`, `/teachme-review`, `/teachme-feynman`, `/teachme-drill`, `/teachme-compare`):
   - **Step 1:** Check `~/.teachme-config.json` (e.g., `{"notes_root": "C:/Users/aayus/OneDrive/Desktop/MyVault"}`) first.
   - **Step 2:** If `~/.teachme-config.json` does not exist or `notes_root` is unset, default `<VAULT_ROOT>` to `~/notes` (expanding `~` to the user's home directory).
   - **Never hardcode `<VAULT_ROOT>/`** when `notes_root` is configured; use `/teachme-notes-path <path>` to view, change, or reset `<VAULT_ROOT>`.
2. **Always Start with Frontier Grilling:** Every new `/teachme <topic>` session MUST begin with Phase 1 (Frontier Grilling Round with `❓` questions and `➡️` defaults: `No prior knowledge` + `Absolute mastery covering all topics`) before running research—unless the user explicitly passes `--auto` or replies `"auto"`, `"defaults"`, or `"go"`.
3. **Pure Markdown & Strict YAML Frontmatter Output:** Produce 100% pure Markdown (`.md`) files across the entire vault (no HTML wrappers, no PDFs). Whenever writing YAML frontmatter (`--- ... ---`), double-quote `"..."` all `description`, `title`, `checkpoint`, `key_equations`, and string values containing `:`, `|`, `[`, `]`, `{`, `}`, `<`, `>`, `*`, `&`, `#`, `?`, or `\` so GitHub and Obsidian parse them with zero warnings.
4. **Never Trust Parametric Knowledge Alone:** Treat pre-trained knowledge as untrusted until grounded in primary sources during Phase 2.
5. **Progressive Reference Loading:** Read supporting files in `references/` only for the active phase or subcommand:
   - Phase 1: `references/MISSION-AND-GRILL.md` | Phase 2: `references/RESEARCH-TOOLCHAIN.md`
   - Phases 3–5: `references/STUDY-AND-GLOSSARY.md` | Phase 6: `references/RETENTION-AND-RECORDS.md`
   - Subcommands: load `references/cmd-<subcommand>.md` directly (`references/SUBCOMMANDS.md` holds the index).
6. **Exhaustive Subtopic Coverage (No Caps):** Generate a standalone `topics/<nn>-<subtopic-slug>.md` (8-Block Standard + 6-Point Critic Audit, `STUDY-AND-GLOSSARY.md` §6) for every syllabus subtopic, plus `atomic/` cards.
7. **Zero Black-Box Formulas:** Every formula in `02-DEEP-RESEARCH.md`, `03-CORNELL-STUDY-GUIDE.md`, and `topics/*.md` MUST follow `STUDY-AND-GLOSSARY.md` §4 (Zero-Baseline Micro-Bridge, Mathematical Intuition before symbols, Formula Anatomy Table, zero-skip `I Do` trace, limiting cases).
8. **7-Component Blueprint & Strict Anti-Spoiler Rule:** Phase 6 runs the 7-Component Blueprint across 3 Escalating Depth Turns (`1/3`, `2/3`, `3/3`) and 4 Checkpoints (`[1/4]`–`[4/4]`) per `RETENTION-AND-RECORDS.md` §2–3. On `"idk"`, `"explain"`, or errors, **NEVER** reveal the answer—drop down to a 1-number micro-question.
9. **Zero Backtick-Wrapped Math:** NEVER wrap inline `$` or display `$$` math in code backticks anywhere (including table cells).
10. **Table-Safe LaTeX Delimiters:** Inside Markdown tables, use `\mid` / `\lvert` / `\rvert` / `\lVert` / `\rVert` instead of raw `|`; keep `$...$` single-line and balanced.
11. **Zero-Dead-Link & Typed Edge Rule:** Every `[[wikilink]]`, relative `.md` link, and YAML typed edge (`depends_on`, `unlocks`, `contrasts_with`, `fixes_failure_of`) must resolve to an existing vault file (use `[]`, never `[[none]]`).
12. **CLI-Backed Spreading Activation, Question Queue & Delta-Flush:**
    - **Start / Resume:** Run `scripts/vault_cli.py state` and `scripts/vault_cli.py graph` instead of scanning Markdown files.
    - **Spreading-Activation 1-Hop Rule:** For active `topic-<nn>`, load ONLY the current stage's sections via `vault_cli.py slice` (`L1-ANCHOR`/`L2-PREREQS-AND-MOTIVATION` for Stage 1; `L3-FOUR-LAYER-THEORY`/`L4-DERIVATION-AND-CODE` for Stage 2; `L5-WORKBOOK-AND-GRAPH` for Stage 3) + immediate **1-hop neighbors** (`depends_on`, `contrasts_with` from `00-GRAPH.json`) via `--section L0-L1` (~25 lines). **Forbid** loading mastered nodes $>1$ hop away unless an interleaved warm-up queries them.
    - **Pre-Computed Queue & Delta-Flush:** Write `scratchpad/queue-<nn>.json` (`[1/4]`..`[4/4]`) once per lesson; record Checkpoints `1`–`3` solely via `vault_cli.py tick` (`scratchpad/events.jsonl` + `00-SESSION-STATE.md`); flush full Markdown updates (`topics/*.md`, `00-MOC-INDEX.md`, `00-GRAPH.json`) **once** upon passing `[4/4]`.
    - **Auto-Compaction:** Keep raw drafts in `scratchpad/`; every 3 completed subtopics append a 5-line **Cumulative Synthesis Strip** to `00-MOC-INDEX.md` and roll up verified formulas into `09-CHEAT-SHEET.md`.

---

## Central Vault File Architecture

For any `<topic>`, create and maintain this exact directory tree at `<VAULT_ROOT>/<topic-slug>/`:

```text
<VAULT_ROOT>/<topic-slug>/
├── 00-SESSION-STATE.md            # Strictly <60 lines: hot-state resume pointer, status map & last verified invariant
├── 00-GRAPH.json                  # Compact typed adjacency map generated by scripts/vault_cli.py graph
├── 00-MISSION.md                  # Concrete goals, success criteria, constraints, out-of-scope
├── 00-MOC-INDEX.md                # Master Map of Content, Mermaid+ASCII prereq graph, synthesis strips & checkboxes
├── 01-RESOURCES.md                # Vetted Knowledge (primary) + Wisdom (communities) + Exhaustive Syllabus + Gaps
├── 02-DEEP-RESEARCH.md            # Primary-source chased dossier with claim provenance, Formula Anatomy & conflicts
├── 03-CORNELL-STUDY-GUIDE.md      # Master index linking all topics/<nn>-*.md, comparison tables, worked examples, <details> cues
├── 04-GLOSSARY.md                 # Canonical 1-2 sentence definitions + "_Avoid_:" aliases
├── 05-MENTAL-MODELS.md            # Feynman analogies, first-principles axioms, ASCII diagrams, failure modes
├── 06-DERIVATIONS-AND-PROOFS.md   # Step-by-step axiom-to-formula derivations with justifications
├── 07-PRACTICE-PROBLEMS.md        # Tiered quantitative/diagnostic drill problems & solutions
├── 08-FLASHCARDS.md               # Obsidian Spaced Repetition & Anki active-recall + cloze deck
├── 09-CHEAT-SHEET.md              # Distilled 1-page review sheet (/teachme distill + auto-compacted every 3 subtopics)
├── topics/                        # 01-<subtopic-slug>.md ... 8-Block Standard with L1-L5 semantic anchors (no cap)
├── atomic/                        # Interlinked 150-300 word Zettelkasten cards with L1-L5 semantic anchors
├── learning-records/              # 000N-<slug>.md ADR-style mastery & misconception logs
└── scratchpad/                    # Ephemeral buffer (raw-research.md, derivation-drafts.md, events.jsonl, queue-<nn>.json)
```
*(Cross-vault comparisons are stored at `<VAULT_ROOT>/comparisons/<topic-a-slug>-vs-<topic-b-slug>.md`.)*

---

## Subcommand Router

Route any subcommand invocation (both top-level `/teachme-<subcommand>` wrapper skills and space-separated `/teachme <subcommand>` aliases) directly to its dedicated workflow in `references/SUBCOMMANDS.md` without rebuilding the entire vault from scratch:

| Autocomplete Command & Space-Separated Alias | Mode | Target Path |
|---|---|---|
| `/teachme <topic>` | **Full Pipeline** | `<VAULT_ROOT>/<topic-slug>/` (Runs Phases 1–6, starting with Frontier Grilling) |
| `/teachme <topic> --auto` | **Fast-Track Pipeline** | `<VAULT_ROOT>/<topic-slug>/` (Skips Phase 1 grilling with defaults; runs Phases 2–6) |
| `/teachme-notes-path [path\|reset]` \| `/teachme notes-path [path\|reset]` | **Vault Root Configuration** | `~/.teachme-config.json` & `<VAULT_ROOT>/` |
| `/teachme-expand <topic>` \| `/teachme expand <topic>` | **Vault Expansion & Deepening** | `<VAULT_ROOT>/<topic-slug>/` |
| `/teachme-verify <topic>` \| `/teachme verify <topic>` *(alias: `/teachme audit <topic>`)* | **Vault Integrity & Auto-Repair** | `<VAULT_ROOT>/<topic-slug>/` |
| `/teachme-ingest <topic> <source>` \| `/teachme ingest <topic> <source>` *(or `<source> into <topic>`)* | **Source Ingestion & Merge** | `<VAULT_ROOT>/<topic-slug>/` |
| `/teachme-distill <topic>` \| `/teachme distill <topic>` | **Executive Cheat Sheet & Flashcards** | `<VAULT_ROOT>/<topic-slug>/09-CHEAT-SHEET.md` |
| `/teachme-review <topic>` \| `/teachme review <topic>` | **Spaced-Repetition Coaching** | `<VAULT_ROOT>/<topic-slug>/` |
| `/teachme-feynman <concept>` \| `/teachme feynman <concept>` | **Reverse-Teaching Audit** | `<VAULT_ROOT>/<topic-slug>/` |
| `/teachme-drill <topic> [1\|2\|3]` \| `/teachme drill <topic> [1\|2\|3]` *(or `--tier 1\|2\|3`)* | **Problem Generator & Grader** | `<VAULT_ROOT>/<topic-slug>/07-PRACTICE-PROBLEMS.md` |
| `/teachme-compare <A> vs <B>` \| `/teachme compare <A> vs <B>` | **Cross-Vault Synthesis** | `<VAULT_ROOT>/comparisons/<a-vs-b>.md` |

---

## 6-Phase Execution Pipeline

### Phase 1: Frontier Grilling & Mission Lock (`references/MISSION-AND-GRILL.md`)
1. Read `references/MISSION-AND-GRILL.md`.
2. Unless `--auto` or `defaults` / `go` was passed, present the **4 numbered `❓` questions** with `➡️` recommended defaults (`No prior knowledge`, `Absolute mastery covering all topics`, `Complete first-principles mastery`, `None`) to calibrate baseline (ZPD), depth, outcome, and custom scope/seed material. Wait for the user's response.
3. Once answered (or defaulted), create `<VAULT_ROOT>/<topic-slug>/00-MISSION.md` with explicit baseline/coverage fields, concrete success criteria, and curriculum milestones.

### Phase 2: Primary-Source Research Toolchain & Exhaustive Syllabus (`references/RESEARCH-TOOLCHAIN.md`)
1. Read `references/RESEARCH-TOOLCHAIN.md`.
2. Formulate a falsifiable Research Brief, decompose the subject into a **complete, exhaustive syllabus** covering every topic, subtopic, algorithm, theorem, and mechanism required for full mastery, and capture raw intermediate search/reading drafts inside `<VAULT_ROOT>/<topic-slug>/scratchpad/raw-research.md` so canonical notes stay clean.
3. Write `<VAULT_ROOT>/<topic-slug>/01-RESOURCES.md` separating **Knowledge** (specs, papers, official docs), **Wisdom** (post-mortems, maintainer talks, practitioner insights), the **Exhaustive Syllabus**, and **Gaps**.
4. Chase primary sources and write `<VAULT_ROOT>/<topic-slug>/02-DEEP-RESEARCH.md` with inline `[Source]` citations, internal mechanics, empirical benchmarks, failure modes, a comparative landscape table, and a **Formula Anatomy Breakdown** for every formula.

### Phase 3: First-Principles Mental Models, Glossary & Derivations (`references/STUDY-AND-GLOSSARY.md`)
1. Read `references/STUDY-AND-GLOSSARY.md`.
2. Use `<VAULT_ROOT>/<topic-slug>/scratchpad/derivation-drafts.md` for rough intermediate algebra/brainstorming before committing canonical notes.
3. Generate `<VAULT_ROOT>/<topic-slug>/05-MENTAL-MODELS.md` containing:
   - Zero-jargon Feynman core analogy (including where the analogy holds and where it breaks).
   - First-principles axiom stack.
   - Clean ASCII architecture and state-transition diagram.
   - Adversarial pre-mortem (how to break it, silent failure modes, and defensive invariants).
4. Generate `<VAULT_ROOT>/<topic-slug>/04-GLOSSARY.md` with strict 1-2 sentence definitions of what each canonical term IS, plus `_Avoid_:` lines for overloaded synonyms.
5. Generate `<VAULT_ROOT>/<topic-slug>/06-DERIVATIONS-AND-PROOFS.md` deriving every major equation, complexity bound, and theorem step-by-step from base axioms with 1-sentence justifications and cross-references to `topics/*.md` and `04-GLOSSARY.md`.

### Phase 4: Cornell Guide, 8-Block Subtopic Files, State/Graph & Flashcards (`references/STUDY-AND-GLOSSARY.md`)
1. Generate `<VAULT_ROOT>/<topic-slug>/topics/<nn>-<subtopic-slug>.md` for every syllabus subtopic using the **8-Block Standard** and pass the **6-Point Writer -> Critic Audit** (`STUDY-AND-GLOSSARY.md` §6) before saving.
2. Synthesize `03-CORNELL-STUDY-GUIDE.md` linking every `[[topics/<nn>-<subtopic-slug>]]` file (`STUDY-AND-GLOSSARY.md` §5).
3. Generate `00-MOC-INDEX.md`, `00-SESSION-STATE.md` (<60 lines), and `08-FLASHCARDS.md` (`STUDY-AND-GLOSSARY.md` §7–8).
4. Run `scripts/vault_cli.py graph <VAULT_PATH>` and `scripts/vault_cli.py verify <VAULT_PATH>` to build `00-GRAPH.json` and confirm 0 errors.

### Phase 5: Atomic Zettelkasten Cards (`references/STUDY-AND-GLOSSARY.md` §9)
1. Extract 150–300 word standalone `atomic/<concept-slug>.md` cards for key mechanisms, theorems, and invariants—partitioned with `L1-ANCHOR`..`L5-WORKBOOK-AND-GRAPH` markers and linked via `[[wikilinks]]`.

### Phase 6: Progressive 7-Component Mastery Loop (`references/RETENTION-AND-RECORDS.md`)
1. Read `references/RETENTION-AND-RECORDS.md` and run `scripts/vault_cli.py state` + `graph` on resume.
2. Follow Law 12 (**Spreading-Activation 1-Hop Context**, `scratchpad/queue-<nn>.json`, and **Delta-Flush via `vault_cli.py tick`**).
3. Deliver each lesson across **3 Escalating Depth Turns** (`Depth Stage 1/3`, `2/3`, `3/3`) and **4 Sequential Checkpoints** (`[1/4]`–`[4/4]`) per `RETENTION-AND-RECORDS.md` §2–3, honoring **Anti-Spoiler**, **`wait-what`**, **Interleaved Recall** (Lesson 3, 5, 7...), and **Auto-Compaction** (every 3 subtopics).
