---
name: teachme
description: Unified end-to-end learning, deep primary-source research, frontier grilling, Socratic teaching, and structured Markdown note-taking pipeline. Invoke with `/teachme <topic>` or when the user asks to deeply research, learn, build a study guide, generate Cornell notes, create Zettelkasten cards, or master any topic from first principles into a central vault (`~/notes/<topic-slug>/`).
---

# Unified `/teachme` Master Pipeline

When invoked as `/teachme <topic>` (or when the user asks to deeply research, learn, and take complete notes on a topic), execute this **6-Phase Stateful Pipeline** inside the user's **central knowledge vault** (`~/notes/<topic-slug>/`).

Do NOT dump everything in a single wall of chat text. Write clean, pure Markdown files into `~/notes/<topic-slug>/` while guiding the user interactively in chat.

---

## Non-Negotiable Operating Laws

1. **Central Vault Only:** Always write all generated files to `~/notes/<topic-slug>/` (expanding `~` to the user's home directory), regardless of which workspace is currently open. Never scatter notes inside random project folders.
2. **Always Start with Frontier Grilling:** Every new `/teachme <topic>` session MUST begin with Phase 1 (Frontier Grilling Round with `❓` questions and `➡️` defaults: `No prior knowledge` + `Absolute mastery covering all topics`) before running research—unless the user explicitly passes `--auto` or replies `"auto"`, `"defaults"`, or `"go"`.
3. **Pure Markdown Output:** Produce 100% pure Markdown (`.md`) files across the entire vault (no HTML wrappers, no PDFs). Keep formatting clean for Obsidian, Git, and standard Markdown viewers.
4. **Never Trust Parametric Knowledge Alone:** Treat pre-trained knowledge as untrusted until grounded in primary sources during Phase 2.
5. **Progressive Reference Loading:** Read the supporting reference files in `references/` at the exact phase or subcommand they govern so instructions stay crisp and complete:
   - Phase 1: `references/MISSION-AND-GRILL.md`
   - Phase 2: `references/RESEARCH-TOOLCHAIN.md`
   - Phases 3, 4 & 5: `references/STUDY-AND-GLOSSARY.md`
   - Phase 6: `references/RETENTION-AND-RECORDS.md`
   - Subcommands (`ingest`, `distill`, `review`, `feynman`, `drill`, `compare`, `expand`, `verify`, `audit`): `references/SUBCOMMANDS.md`
6. **Exhaustive Subtopic Coverage (1 Topic / Subtopic = 1 Dedicated `.md` File, No Caps):** Never compress, merge, or skip subtopics or cards to save space. Decompose the subject into an exhaustive syllabus in Phase 2, and generate a full-length, standalone `topics/<nn>-<subtopic-slug>.md` file for **every single topic and subtopic** in that syllabus (following the **8-Block Subtopic Note Standard** and passing the **6-Point Writer -> Critic Audit** before saving), plus as many `atomic/` Zettelkasten cards as needed for full mastery.
7. **Zero Black-Box Formulas & Progressive 3-Stage Theory Standard:** Every concept in `topics/<nn>-<subtopic-slug>.md` and Phase 6 must progress from **Absolute Zero (zero assumed prerequisites)** to **Complete Mastery** across 3 escalating depth stages: (1) **Zero-Baseline Micro-Bridge & Engineering Motivation** (define every new symbol/term from scratch in 2–3 plain-English lines + 2-number example; explain what failed previously), (2) **Depth Stage 1 — Intuition, Visuals & Mechanism** (daily-life analogy + mental hook, causal walkthrough, ASCII diagram, Contrastive "Is vs. Is Not" table + Where the Analogy Breaks Down), (3) **Depth Stage 2 — Mathematical Intuition, Formal Equation, Axiom Derivation & `I Do` Trace** (plain-English geometry/scaling before symbols, pure display LaTeX, complete Symbol & Operator Anatomy Table, zero-skip step-by-step axiom derivation, runnable Python/NumPy `assert` verification snippet, and step-by-step `I Do` walkthrough), and (4) **Depth Stage 3 — Deeper Nuances, Limiting Behaviors ($0, 1, -1, \infty$, negative/degenerate) & Gradual-Release Workbook**. Across `02-DEEP-RESEARCH.md` and `03-CORNELL-STUDY-GUIDE.md`, **no formula, recurrence, objective/loss function, or complexity bound** may appear without an immediate Formula Anatomy Breakdown.
8. **7-Component Blueprint & Strict Anti-Spoiler Mastery Rule:** In Phase 6, every lesson must follow the **7-Component Lesson Blueprint** across **3 Escalating Depth Turns** (`Depth Stage 1/3`, `2/3`, `3/3`) and **4 Sequential Checkpoints** (`[1/4]` Discovery Hook, `[2/4]` `We Do` Guided Practice, `[3/4]` `You Do` Cold Solo Execution, `[4/4]` Adversarial Edge-Case + Feynman Gate)—never a 1-paragraph summary + 1 plug-in question, and never skipping foundational concepts. If the user replies `"idk"`, `"explain"`, or makes an error, **NEVER reveal the final answer or general rule immediately**; drop down one rung to a tiny 1-number micro-question so they discover the step themselves.
9. **Zero Backtick-Wrapped Math Rule:** **NEVER** wrap inline or display LaTeX delimiters in backticks anywhere (never enclose single-dollar or double-dollar math inside Markdown code ticks). Backticks force literal code rendering and break MathJax/KaTeX. Always write pure math delimiters directly ($\mathbf{W}^{(1)}$ inline, display math blocks on their own lines), including inside every Markdown table cell.
10. **Table-Safe LaTeX Delimiters & Escaping:** Inside Markdown table cells, **NEVER** use raw pipe characters `|` inside math (never write conditional probability or absolute value with a raw vertical bar, which breaks table columns); always use `\mid` ($P(A \mid B)$) or `\lvert x \rvert` / `\lVert x \rVert`. Never leave unescaped newlines inside single-line inline math, and ensure every opening `$` or `$$` has a matching closing delimiter on the same block.
11. **Zero-Dead-Link Generation & Typed Edge Rule:** Before writing any `[[wikilink]]`, Markdown link `[text](path.md)`, or YAML typed semantic edge (`depends_on`, `unlocks`, `contrasts_with`, `fixes_failure_of`), verify that the target filename matches an exact file actually written to disk in `topics/<nn>-<subtopic-slug>.md`, `atomic/<concept-slug>.md`, or root vault files (`00-SESSION-STATE`, `00-MOC-INDEX`, `04-GLOSSARY`, `06-DERIVATIONS-AND-PROOFS`, etc.). Never link to planned or hypothetical files, and never use placeholder links like `[[none]]` (use `[]`).
12. **Hot-State Resume, Progressive Disclosure (`L0`/`L1`/`L2`) & Auto-Compaction:** Always read `00-SESSION-STATE.md` (<60 lines) FIRST when resuming a session instead of scanning the full vault. When teaching Subtopic $N$, load ONLY `L0` (YAML frontmatter) + `L1` (`<!-- SECTION: L1-ANCHOR -->`, ~25 lines/file) for prerequisite Subtopics `1..N-1`, and load full `L2` content ONLY for active Subtopic $N$. Keep raw drafts inside `scratchpad/`, and every 3 completed subtopics append a 5-line **Cumulative Synthesis Strip** to `00-MOC-INDEX.md` and roll up verified formulas into `09-CHEAT-SHEET.md`.

---

## Central Vault File Architecture

For any `<topic>`, create and maintain this exact directory tree at `~/notes/<topic-slug>/`:

```text
~/notes/<topic-slug>/
├── 00-SESSION-STATE.md            # Strictly <60 lines: hot-state resume pointer, status map & last verified invariant
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
└── scratchpad/                    # Ephemeral working buffer (raw-research.md, derivation-drafts.md)
```
*(Cross-vault comparisons are stored at `~/notes/comparisons/<topic-a-slug>-vs-<topic-b-slug>.md`.)*

---

## Subcommand Router

Route any subcommand invocation directly to its dedicated workflow in `references/SUBCOMMANDS.md` without rebuilding the entire vault from scratch:

| Invocation | Mode | Target Path |
|---|---|---|
| `/teachme <topic>` | **Full Pipeline** | `~/notes/<topic-slug>/` (Runs Phases 1–6, starting with Frontier Grilling) |
| `/teachme <topic> --auto` | **Fast-Track Pipeline** | `~/notes/<topic-slug>/` (Skips Phase 1 grilling with defaults; runs Phases 2–6) |
| `/teachme ingest <path-or-url> into <topic>` | **Source Ingestion & Merge** | `~/notes/<topic-slug>/` |
| `/teachme distill <topic>` | **Executive Cheat Sheet** | `~/notes/<topic-slug>/09-CHEAT-SHEET.md` |
| `/teachme review <topic>` | **Spaced-Repetition Quiz** | `~/notes/<topic-slug>/` |
| `/teachme feynman <topic> [subtopic]` | **Reverse-Teaching Audit** | `~/notes/<topic-slug>/` |
| `/teachme drill <topic> [--tier 1\|2\|3]` | **Problem Generator & Grader** | `~/notes/<topic-slug>/07-PRACTICE-PROBLEMS.md` |
| `/teachme compare <topic-a> vs <topic-b>` | **Cross-Vault Synthesis** | `~/notes/comparisons/<a-vs-b>.md` |
| `/teachme expand <topic>` | **Vault Expansion & Deepening** | `~/notes/<topic-slug>/` |
| `/teachme verify <topic>` *(alias: `audit`)* | **Vault Integrity & Auto-Repair** | `~/notes/<topic-slug>/` |

---

## 6-Phase Execution Pipeline

### Phase 1: Frontier Grilling & Mission Lock (`references/MISSION-AND-GRILL.md`)
1. Read `references/MISSION-AND-GRILL.md`.
2. Unless `--auto` or `defaults` / `go` was passed, present the **4 numbered `❓` questions** with `➡️` recommended defaults (`No prior knowledge`, `Absolute mastery covering all topics`, `Complete first-principles mastery`, `None`) to calibrate baseline (ZPD), depth, outcome, and custom scope/seed material. Wait for the user's response.
3. Once answered (or defaulted), create `~/notes/<topic-slug>/00-MISSION.md` with explicit baseline/coverage fields, concrete success criteria, and curriculum milestones.

### Phase 2: Primary-Source Research Toolchain & Exhaustive Syllabus (`references/RESEARCH-TOOLCHAIN.md`)
1. Read `references/RESEARCH-TOOLCHAIN.md`.
2. Formulate a falsifiable Research Brief, decompose the subject into a **complete, exhaustive syllabus** covering every topic, subtopic, algorithm, theorem, and mechanism required for full mastery, and capture raw intermediate search/reading drafts inside `~/notes/<topic-slug>/scratchpad/raw-research.md` so canonical notes stay clean.
3. Write `~/notes/<topic-slug>/01-RESOURCES.md` separating **Knowledge** (specs, papers, official docs), **Wisdom** (post-mortems, maintainer talks, practitioner insights), the **Exhaustive Syllabus**, and **Gaps**.
4. Chase primary sources and write `~/notes/<topic-slug>/02-DEEP-RESEARCH.md` with inline `[Source]` citations, internal mechanics, empirical benchmarks, failure modes, a comparative landscape table, and a **Formula Anatomy Breakdown** for every formula.

### Phase 3: First-Principles Mental Models, Glossary & Derivations (`references/STUDY-AND-GLOSSARY.md`)
1. Read `references/STUDY-AND-GLOSSARY.md`.
2. Use `~/notes/<topic-slug>/scratchpad/derivation-drafts.md` for rough intermediate algebra/brainstorming before committing canonical notes.
3. Generate `~/notes/<topic-slug>/05-MENTAL-MODELS.md` containing:
   - Zero-jargon Feynman core analogy (including where the analogy holds and where it breaks).
   - First-principles axiom stack.
   - Clean ASCII architecture and state-transition diagram.
   - Adversarial pre-mortem (how to break it, silent failure modes, and defensive invariants).
4. Generate `~/notes/<topic-slug>/04-GLOSSARY.md` with strict 1-2 sentence definitions of what each canonical term IS, plus `_Avoid_:` lines for overloaded synonyms.
5. Generate `~/notes/<topic-slug>/06-DERIVATIONS-AND-PROOFS.md` deriving every major equation, complexity bound, and theorem step-by-step from base axioms with 1-sentence justifications and cross-references to `topics/*.md` and `04-GLOSSARY.md`.

### Phase 4: Master Cornell Guide, 8-Block Subtopic Files, Session State, MOC Index & Flashcards (`references/STUDY-AND-GLOSSARY.md`)
1. Generate a dedicated, full-length file `~/notes/<topic-slug>/topics/<nn>-<subtopic-slug>.md` for **every single topic and subtopic** in the Phase 2 exhaustive syllabus (no compressing, merging, or skipping), structured in the exact **8-Block Subtopic Note Standard** (Block 0 typed YAML `L0` metadata, Block 1 `L1-ANCHOR`, Block 2 `L2-PREREQS-AND-MOTIVATION`, Block 3 `L3-FOUR-LAYER-THEORY` with ASCII diagram + Contrastive "Is vs. Is Not" table + Analogy Break-Down callout + Symbol Anatomy + Directional Sensitivity & Boundary Limits, Block 4 `L4-DERIVATION-AND-CODE` zero-skip axiom derivation, Block 5 executable 10–18 line Python/NumPy `assert` verification snippet, Block 6 `L5-WORKBOOK-AND-GRAPH` `I Do` → `We Do` → `You Do` with `<details>`, Block 7 Typed Knowledge Graph Footer & 4-Checkpoint Mastery Ledger). Run the **Mandatory 6-Point Writer -> Critic Audit** before saving each file to disk.
2. Synthesize `00-MISSION.md`, `02-DEEP-RESEARCH.md`, `04-GLOSSARY.md`, `05-MENTAL-MODELS.md`, and all `topics/` files into `~/notes/<topic-slug>/03-CORNELL-STUDY-GUIDE.md`, explicitly linking **every** `[[topics/<nn>-<subtopic-slug>]]` file in its syllabus index and sections, with **Formula Anatomy Breakdowns**, trade-off tables, `<details>` active-recall cues, a 5-bullet synthesis summary, and `## Living Session Notes & Insights`.
3. Generate `~/notes/<topic-slug>/00-MOC-INDEX.md` as the master navigation dashboard (with Cumulative Synthesis Strip support) and `~/notes/<topic-slug>/00-SESSION-STATE.md` (strictly `< 60` lines) as the hot-state resume pointer.
4. Generate `~/notes/<topic-slug>/08-FLASHCARDS.md` formatted for Obsidian Spaced Repetition (`#flashcards/<topic-slug>`) and Anki with conceptual/mechanism cards (`::` and `?`) and formula/symbol cloze deletions (`==...==`).

### Phase 5: Atomic Zettelkasten Cards (`references/STUDY-AND-GLOSSARY.md`)
1. Extract standalone atomic concept cards into `~/notes/<topic-slug>/atomic/<concept-slug>.md` covering every key mechanism, theorem, and invariant (no arbitrary cap).
2. Each card must be 150-300 words, include YAML frontmatter (`tags`, `created`, `status: evergreen`, `parent: "[[03-CORNELL-STUDY-GUIDE]]"`), partition content with the strict HTML semantic anchors (`<!-- SECTION: L1-ANCHOR -->` through `<!-- SECTION: L5-WORKBOOK-AND-GRAPH -->`), ground terms in `04-GLOSSARY.md`, cite `[Source]`, and interlink via `[[wikilinks]]` under `## Related Concepts`.

### Phase 6: Progressive 7-Component Socratic Mastery Loop & Learning Records (`references/RETENTION-AND-RECORDS.md`)
1. Read `references/RETENTION-AND-RECORDS.md`.
2. **Hot-State Resume & Progressive Disclosure (`L0`/`L1`/`L2`):** On session resume, read `00-SESSION-STATE.md` FIRST instead of scanning the entire vault. When teaching Subtopic $N$, load ONLY `L0` (YAML frontmatter) + `L1` (`<!-- SECTION: L1-ANCHOR -->`, ~25 lines/file) of prerequisite Subtopics `1..N-1`, and load the full `L2` body ONLY for active Subtopic $N$.
3. Present a crisp executive summary (<250 words) in chat and list all created vault files (highlighting `00-SESSION-STATE.md`, `00-MOC-INDEX.md`, and `topics/*.md`).
4. **Interleaved Cumulative Recall:** Starting at `Lesson 3` and every 2 lessons thereafter, open with a quick 1-question warm-up blending a previous lesson's concept with the current lesson before starting Component 1.
5. **7-Component Lesson Blueprint Across 3 Escalating Depth Turns (`Depth Stage 1/3`, `2/3`, `3/3`) & 4 Checkpoints (`[1/4]`–`[4/4]`):**
   - **Component 1 (Lesson Header & Prerequisite Micro-Bridge):** Show **`Lesson X/Y: <Lesson Title> | Depth Stage: 1/3 (Intuition & Hook)`** and define *every* new mathematical symbol, operator, or technical term from scratch in 2–3 plain-English lines with a tiny 2-number example (assuming zero prior background).
   - **Component 2 (Engineering Motivation & Discovery Prediction Hook — `Checkpoint [1/4]`):** Give 2 sentences on why this exists, present a concrete problem/failure scenario before revealing the formula, and wait for the user's prediction.
   - **Component 3 (Layered Theory — Turn 1, ~300–400 words):** After `[1/4]`, teach Daily-Life Intuition + Mental Hook, Step-by-Step Mechanism, ASCII Visual Diagram, and Contrastive Boundary + Where the Analogy Breaks Down; verify conceptual understanding before escalating.
   - **Component 4 (Layered Theory — Turn 2, ~300–400 words, `Depth Stage: 2/3`):** Teach Mathematical Intuition (before symbols), Formal Governing Equation (pure display LaTeX, zero backticks, `\mid` in tables), Complete Symbol & Operator Anatomy, and a thinking-aloud `I Do` worked walkthrough skipping zero algebraic steps.
   - **Component 5 (Guided Practice — `We Do` — `Checkpoint [2/4]`):** Present a richer second problem with ~60% filled in and 2 surgical blanks (`[Step 2: ___]`, `[Step 4: ___]`). Enforce the **Strict Anti-Spoiler Rule** (drop down to a 1-number micro-question on `"idk"`, `"explain"`, or error).
   - **Component 6 (`You Do` — `Checkpoint [3/4]` & Depth Stage 3/3 Deepening):** Present a fresh cold solo problem with zero scaffolding; once solved, unlock **Depth Stage 3/3 (~250–350 words)** covering edge cases, limiting behaviors (`0, 1, -1, \infty`, negative values), why alternatives fail, and links to advanced topics.
   - **Component 7 (Adversarial Edge-Case & Feynman Mastery Gate — `Checkpoint [4/4]`):** Test a tricky boundary/failure input + 2-sentence plain-English Feynman Teach-Back with zero unstated jargon.
6. Honor the inline `wait-what` / `simplify` protocol immediately if the user hits friction—re-pitch from scratch using `04-GLOSSARY.md` terms and a 1-number trace, append the clearer explanation to `05-MENTAL-MODELS.md`, and resume at the current checkpoint.
7. **Auto-Log, State Update & Auto-Compaction:** Upon passing `[4/4]`, check off `- [x]` in `00-MOC-INDEX.md`, update `00-SESSION-STATE.md` (<60 lines) and the subtopic's `status`/`checkpoint` ledger, log struggled concepts/misconceptions in `learning-records/000N-<slug>.md`, and append insights to `03-CORNELL-STUDY-GUIDE.md` and `04-GLOSSARY.md`. Every 3 completed subtopics, append a 5-line **Cumulative Synthesis Strip** to `00-MOC-INDEX.md` and roll up verified formulas into `09-CHEAT-SHEET.md`.
