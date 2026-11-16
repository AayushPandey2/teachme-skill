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
6. **Exhaustive Subtopic Coverage (1 Topic / Subtopic = 1 Dedicated `.md` File, No Caps):** Never compress, merge, or skip subtopics or cards to save space. Decompose the subject into an exhaustive syllabus in Phase 2, and generate a full-length, standalone `topics/<nn>-<subtopic-slug>.md` file for **every single topic and subtopic** in that syllabus, plus as many `atomic/` Zettelkasten cards as needed for full mastery.
7. **Zero Black-Box Formulas & 4-Layer Theory Standard:** Every concept in `topics/<nn>-<subtopic-slug>.md` and Phase 6 must be presented in the strict **4-Layer Sequence** (Concrete -> Representational -> Abstract): (1) Daily-Life Intuition, (2) Theoretical Explanation (causal mechanism, diagram, Contrastive Non-Example, and Where the Analogy Breaks Down), (3) Mathematical Intuition before notation, and (4) Mathematical Explanation & Formula Anatomy (display LaTeX blocks, complete Symbol/Operator Breakdown Table with directional sensitivity, boundary edge cases `0`, `1`, `\infty`, and a concrete 3-number `I Do` worked trace). Across `02-DEEP-RESEARCH.md` and `03-CORNELL-STUDY-GUIDE.md`, **no formula, recurrence, objective/loss function, or complexity bound** may appear without an immediate Formula Anatomy Breakdown.
8. **Hybrid Discovery + Teach-Before-Mastery Rule:** Never dump theory before posing Checkpoint `[1/5]` (Discovery Prediction Hook), and never test Checkpoints `[2/5]`–`[5/5]` on a subtopic you have not taught in full first. Always deliver the complete **4-Layer Lesson** (Layers 1 -> 2 -> 3 -> 4 + 3-number `I Do` worked trace) right after Checkpoint `[1/5]`, then advance strictly 1 question per turn through `[2/5]`–`[5/5]` with zero skips and strict Anti-Spoiler productive struggle on wrong attempts.
9. **Zero Backtick-Wrapped Math Rule:** **NEVER** wrap inline or display LaTeX delimiters in backticks anywhere (never enclose single-dollar or double-dollar math inside Markdown code ticks). Backticks force literal code rendering and break MathJax/KaTeX. Always write pure math delimiters directly ($\mathbf{W}^{(1)}$ inline, display math blocks on their own lines), including inside every Markdown table cell.
10. **Table-Safe LaTeX Delimiters & Escaping:** Inside Markdown table cells, **NEVER** use raw pipe characters `|` inside math (never write conditional probability or absolute value with a raw vertical bar, which breaks table columns); always use `\mid` ($P(A \mid B)$) or `\lvert x \rvert` / `\lVert x \rVert`. Never leave unescaped newlines inside single-line inline math, and ensure every opening `$` or `$$` has a matching closing delimiter on the same block.
11. **Zero-Dead-Link Generation Rule:** Before writing any `[[wikilink]]` or standard Markdown link `[text](path.md)`, verify that the target filename matches the exact slug actually written to disk in `topics/<nn>-<subtopic-slug>.md`, `atomic/<concept-slug>.md`, or root vault files (`00-MOC-INDEX`, `04-GLOSSARY`, `06-DERIVATIONS-AND-PROOFS`, etc.). Never link to planned or hypothetical files that were not written to disk, and never use placeholder links like `[[none]]` (use `prerequisites: []`).

---

## Central Vault File Architecture

For any `<topic>`, create and maintain this exact directory tree at `~/notes/<topic-slug>/`:

```text
~/notes/<topic-slug>/
├── 00-MISSION.md                  # Concrete goals, success criteria, constraints, out-of-scope
├── 00-MOC-INDEX.md                # Master Map of Content, Mermaid+ASCII prereq graph & progress tracker
├── 01-RESOURCES.md                # Vetted Knowledge (primary) + Wisdom (communities) + Exhaustive Syllabus + Gaps
├── 02-DEEP-RESEARCH.md            # Primary-source chased dossier with claim provenance, Formula Anatomy & conflicts
├── 03-CORNELL-STUDY-GUIDE.md      # Master index linking all topics/<nn>-*.md, comparison tables, worked examples, <details> cues
├── 04-GLOSSARY.md                 # Canonical 1-2 sentence definitions + "_Avoid_:" aliases
├── 05-MENTAL-MODELS.md            # Feynman analogies, first-principles axioms, ASCII diagrams, failure modes
├── 06-DERIVATIONS-AND-PROOFS.md   # Step-by-step axiom-to-formula derivations with justifications
├── 07-PRACTICE-PROBLEMS.md        # Tiered quantitative/diagnostic drill problems & solutions
├── 08-FLASHCARDS.md               # Obsidian Spaced Repetition & Anki active-recall + cloze deck
├── 09-CHEAT-SHEET.md              # Distilled 1-page review sheet (/teachme distill)
├── topics/                        # 01-<subtopic-slug>.md ... 1 dedicated full deep-dive per subtopic (no cap)
├── learning-records/              # 000N-<slug>.md ADR-style mastery & misconception logs
└── atomic/                        # Interlinked 150-300 word Zettelkasten cards with [[wikilinks]] (no arbitrary cap)
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
2. Formulate a falsifiable Research Brief, decompose the subject into a **complete, exhaustive syllabus** covering every topic, subtopic, algorithm, theorem, and mechanism required for full mastery, and execute deep web/primary-source searches.
3. Write `~/notes/<topic-slug>/01-RESOURCES.md` separating **Knowledge** (specs, papers, official docs), **Wisdom** (post-mortems, maintainer talks, practitioner insights), the **Exhaustive Syllabus**, and **Gaps**.
4. Chase primary sources and write `~/notes/<topic-slug>/02-DEEP-RESEARCH.md` with inline `[Source]` citations, internal mechanics, empirical benchmarks, failure modes, a comparative landscape table, and a **Formula Anatomy Breakdown** for every formula.

### Phase 3: First-Principles Mental Models, Glossary & Derivations (`references/STUDY-AND-GLOSSARY.md`)
1. Read `references/STUDY-AND-GLOSSARY.md`.
2. Generate `~/notes/<topic-slug>/05-MENTAL-MODELS.md` containing:
   - Zero-jargon Feynman core analogy (including where the analogy holds and where it breaks).
   - First-principles axiom stack.
   - Clean ASCII architecture and state-transition diagram.
   - Adversarial pre-mortem (how to break it, silent failure modes, and defensive invariants).
3. Generate `~/notes/<topic-slug>/04-GLOSSARY.md` with strict 1-2 sentence definitions of what each canonical term IS, plus `_Avoid_:` lines for overloaded synonyms.
4. Generate `~/notes/<topic-slug>/06-DERIVATIONS-AND-PROOFS.md` deriving every major equation, complexity bound, and theorem step-by-step from base axioms with 1-sentence justifications and cross-references to `topics/*.md` and `04-GLOSSARY.md`.

### Phase 4: Master Cornell Guide, Subtopic Files, MOC Index & Flashcards (`references/STUDY-AND-GLOSSARY.md`)
1. Generate a dedicated, full-length file `~/notes/<topic-slug>/topics/<nn>-<subtopic-slug>.md` for **every single topic and subtopic** in the Phase 2 exhaustive syllabus (no compressing, merging, or skipping), structured in the strict **4-Layer Theory Presentation Standard** (Layer 1 Daily-Life Intuition -> Layer 2 Theoretical Explanation with causal mechanism, diagram, Contrastive Non-Example, and Where the Analogy Breaks Down -> Layer 3 Mathematical Intuition -> Layer 4 Mathematical Explanation & Formula Anatomy with 3-number `I Do` worked trace), plus YAML frontmatter, worked examples/annotated code, edge cases, `<details>` self-check questions, and navigation footers.
2. Synthesize `00-MISSION.md`, `02-DEEP-RESEARCH.md`, `04-GLOSSARY.md`, `05-MENTAL-MODELS.md`, and all `topics/` files into `~/notes/<topic-slug>/03-CORNELL-STUDY-GUIDE.md`, explicitly linking **every** `[[topics/<nn>-<subtopic-slug>]]` file in its syllabus index and sections, with **Formula Anatomy Breakdowns**, trade-off tables, `<details>` active-recall cues, a 5-bullet synthesis summary, and `## Living Session Notes & Insights`.
3. Generate `~/notes/<topic-slug>/00-MOC-INDEX.md` as the master navigation dashboard with vault header links, a dual-format **Prerequisite & Dependency Graph** (Mermaid `graph TD` + ASCII tree), a complete `topics/` syllabus checklist with difficulty/prereq tags, and an `atomic/` concept index.
4. Generate `~/notes/<topic-slug>/08-FLASHCARDS.md` formatted for Obsidian Spaced Repetition (`#flashcards/<topic-slug>`) and Anki with conceptual/mechanism cards (`::` and `?`) and formula/symbol cloze deletions (`==...==`).

### Phase 5: Atomic Zettelkasten Cards (`references/STUDY-AND-GLOSSARY.md`)
1. Extract standalone atomic concept cards into `~/notes/<topic-slug>/atomic/<concept-slug>.md` covering every key mechanism, theorem, and invariant (no arbitrary cap).
2. Each card must be 150-300 words, include YAML frontmatter (`tags`, `created`, `status: evergreen`, `parent: "[[03-CORNELL-STUDY-GUIDE]]"`), ground terms in `04-GLOSSARY.md`, cite `[Source]`, and interlink via `[[wikilinks]]` under `## Related Concepts`.

### Phase 6: Hybrid Discovery + 5-Checkpoint Mastery Loop & Learning Records (`references/RETENTION-AND-RECORDS.md`)
1. Read `references/RETENTION-AND-RECORDS.md`.
2. Present a crisp executive summary (<250 words) in chat and list all created vault files (highlighting `00-MOC-INDEX.md` and `topics/*.md`).
3. **Interleaved Warm-Up:** When starting Subtopic $N \ge 3$, open with a 1-question rapid recall check from Subtopic $N-2$ before starting Checkpoint `[1/5]`.
4. **Banner & Strict 5-Checkpoint Mastery Ladder (1 Question per Turn, Zero Skips):** Start every subtopic by displaying its 5-checkpoint roadmap and track **`Subtopic X/Y — Checkpoint [k/5]`** on every turn:
   - **Checkpoint `[1/5]` — Discovery Prediction Hook (Before Theory):** Present a concrete failure scenario or intuition puzzle *before* definitions/formulas and ask the user to predict what happens or what mechanism is needed.
   - *(Deliver 4-Layer Theory: Layers 1 -> 2 -> 3 -> 4, ending with a thinking-aloud `I Do` 3-number worked trace).*
   - **Checkpoint `[2/5]` — Formula & Conceptual Logic Check:** Ask a targeted question verifying why a specific term/operator exists or how scaling/sensitivity behaves.
   - **Checkpoint `[3/5]` — `We Do` Faded Scaffolding:** Present a second worked problem with 60% of steps filled in and 2 surgical blanks (`[Step 2: ___]`, `[Step 4: ___]`) for the user to complete.
   - **Checkpoint `[4/5]` — `You Do` Cold Solo Execution:** Give a fresh problem with zero scaffolding for the user to solve solo.
   - **Checkpoint `[5/5]` — Adversarial Edge Case + Feynman Gate:** Test a boundary/failure case (`0`, `\infty`, negative/degenerate inputs) and require a 2-sentence plain-English Feynman explanation with zero unstated jargon.
5. **Anti-Spoiler Productive Struggle & Baseline Calibration:** If the user answers incorrectly on attempt 1, NEVER reveal the full answer—pinpoint the exact divergent step, give a surgical hint or simpler sub-question, and let them self-correct. Calibrate numerical complexity and hints to `00-MISSION.md`.
6. Honor the inline `wait-what` / `simplify` protocol immediately if the user hits friction—re-pitch from scratch using `04-GLOSSARY.md` terms and a 1-number trace, append the clearer explanation to `05-MENTAL-MODELS.md`, and resume at the current checkpoint.
7. Check off mastered subtopics (`- [x]`) in `00-MOC-INDEX.md` upon passing `[5/5]`, log breakthroughs/misconceptions/mission shifts in `learning-records/000N-<slug>.md` (`Status: active` or `superseded by LR-000N`), and append user insights to `03-CORNELL-STUDY-GUIDE.md` (`## Living Session Notes & Insights`) and `04-GLOSSARY.md`.
