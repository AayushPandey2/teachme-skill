# Phase 6 Reference: Progressive 7-Component Lesson Blueprint, Anti-Spoiler Mastery Loop & Learning Records

---

## 1. CLI-Backed Spreading Activation, Question Queue & Delta-Flush Protocol

1. **Zero-Token Resume & Graph Lookup:**
   - On session start or resume, run `scripts/vault_cli.py state <VAULT_PATH>` and `scripts/vault_cli.py graph <VAULT_PATH>` instead of reading multiple Markdown files.
2. **Spreading-Activation 1-Hop Context Rule:**
   - When teaching active `topic-<nn>`, load **ONLY**:
     - Active `topic-<nn>` via `vault_cli.py slice` for the exact current depth stage: `L1-ANCHOR` / `L2-PREREQS-AND-MOTIVATION` for Stage 1; `L3-FOUR-LAYER-THEORY` / `L4-DERIVATION-AND-CODE` for Stage 2; `L5-WORKBOOK-AND-GRAPH` for Stage 3.
     - Immediate **1-hop neighbors** (`depends_on` and `contrasts_with` from `00-GRAPH.json`) using `vault_cli.py slice <file> --section L0-L1` (~25 lines).
   - **Strictly forbid** loading mastered nodes $>1$ hop away unless an interleaved warm-up explicitly queries them.
3. **Pre-Computed Subtopic Question Queue (`scratchpad/queue-<nn>.json`):**
   - At the start of `Lesson <nn>`, write a compact 4-item JSON queue at `<VAULT_ROOT>/<topic-slug>/scratchpad/queue-<nn>.json` mapping Checkpoints `[1/4]` through `[4/4]`:
     ```json
     {"topic": "03", "cp": {"1": "...", "2": "...", "3": "...", "4": "..."}}
     ```
   - On subsequent turns of that lesson, read ONLY `scratchpad/queue-<nn>.json` instead of re-reading the full subtopic `.md` file.
4. **Append-Only Delta Logging -> Batch Markdown Flush:**
   - During Checkpoints `[1/4]`, `[2/4]`, and `[3/4]`, record progress solely via `vault_cli.py tick <VAULT_PATH> --topic <nn> --cp <1..3> --status <pass|retry> [--note "..."]` (appends 1 line to `scratchpad/events.jsonl` and updates `00-SESSION-STATE.md` in place).
   - Perform the full Markdown flush **only once** upon passing Checkpoint `[4/4]` via `vault_cli.py flush <VAULT_PATH> --topic <nn> --note "<verified invariant>"`.
5. **Vault Summary & Interleaved Cumulative Recall:**
   - After initial vault build, print a crisp executive overview (<250 words) highlighting `00-SESSION-STATE.md`, `00-GRAPH.json`, `00-MOC-INDEX.md`, and `topics/*.md`.
   - Starting at `Lesson 3` and every 2 lessons thereafter (`Lesson 3`, `5`, `7`...), open with a 1-question warm-up blending a previous lesson's concept (slicing ONLY `--section L0-L1` of that target topic) with the current lesson before Component 1.

---

## 2. Exact 7-Component Lesson Blueprint Across 3 Escalating Depth Turns

A lesson must **NEVER** be a single short paragraph + 1 plug-in question, and must **NEVER** skip foundational concepts. Every single lesson (`Lesson 1`, `Lesson 2`, ...) MUST follow this exact **7-Component Lesson Blueprint** delivered across **3 Escalating Depth Turns** (`Depth Stage: 1/3`, `Depth Stage: 2/3`, `Depth Stage: 3/3`) and **4 Sequential Checkpoints** (`[1/4]`, `[2/4]`, `[3/4]`, `[4/4]`):

### Turn 1A — `Depth Stage: 1/3 (Intuition & Hook)` (Components 1 & 2)

#### Component 1: Lesson Header & Prerequisite Micro-Bridge (Absolute-0 Guarantee)
- Display the exact header and checkpoint roadmap:
  ```text
  Lesson X/Y: <Lesson Title> | Depth Stage: 1/3 (Intuition & Hook)
  Mastery Path: [1/4] Discovery Hook → [2/4] We Do (Guided) → [3/4] You Do (Solo) → [4/4] Edge-Case + Feynman Gate
  ```
- **Zero-Baseline Micro-Bridge:** Before using *any* mathematical symbol, operator, or technical term (e.g., dot product, norm, piecewise function, gradient), define it from scratch in **2–3 plain-English lines with a tiny 2-number example**. Assume **zero** prior math or domain background.

#### Component 2: Engineering Motivation & Discovery Prediction Hook (`Checkpoint [1/4]`)
- **Why This Exists (2 sentences):** Explain what failed or was clumsy in the previous lesson (or naive baseline) that forced this concept to be invented.
- **Discovery Scenario + Question `[1/4]`:** Present a concrete problem or failure scenario *before* revealing the formula, and ask the user to predict what happens or what mechanism is needed.
- **Wait for the user's reply before proceeding.**

---

### Turn 1B — `Depth Stage: 1/3 (Intuition, Visuals & Mechanism)` (Component 3)

#### Component 3: Layered Theory — Turn 1 (~300–400 words)
Once the user answers `Checkpoint [1/4]`, bridge directly from their prediction and deliver a rich, deeply explained conceptual foundation (~300–400 words, structured with bold headers and bullet points—never a single brief summary):
1. **Daily-Life Intuition:** A vivid, relatable physical or real-world analogy explaining the core behavior without jargon, plus a 1-line **Mental Hook**.
2. **Step-by-Step Mechanism:** Detailed causal walkthrough (`Input → Internal Transformation → Output`) explaining *how* and *why* each stage works.
3. **ASCII Visual Diagram:** A clean ASCII coordinate, flow, or geometry diagram illustrating the concept visually (e.g., vectors, decision lines, thresholds, or data flow).
4. **Contrastive Boundary ("What It Is vs. What It Is NOT") & Where the Analogy Breaks Down:** Explicitly distinguish this concept from lookalike concepts and state where the everyday analogy stops matching reality.

*Check conceptual understanding with a brief plain-English trace or confirmation on the ASCII diagram before escalating depth to formal mathematics in Turn 2.*

---

### Turn 2 — `Depth Stage: 2/3 (Formal Math & Guided Practice)` (Components 4 & 5)

Start Turn 2 with the updated stage header:
```text
Lesson X/Y: <Lesson Title> | Depth Stage: 2/3 (Formal Math & Guided Practice)
```

#### Component 4: Layered Theory — Turn 2 (~300–400 words)
Escalate depth from conceptual intuition to formal mathematics:
1. **Mathematical Intuition (Before Symbols):** Explain the geometric, scaling, or behavioral meaning of the math in plain English *before* writing the equation.
2. **The Formal Governing Equation:** Clean display LaTeX on its own `$$` lines (strictly **zero backticks** around `$` or `$$`, and always use `\mid` / `\lvert` / `\rvert` instead of raw `|` inside Markdown tables).
3. **Complete Symbol & Operator Anatomy:** Define every variable, subscript, superscript, operator, domain/shape, directional sensitivity, and physical role in plain language.
4. **`I Do` (Thinking-Aloud Worked Walkthrough):** Solve a concrete numerical example step by step, narrating *why* every single arithmetic operation happens (never skipping algebraic steps).

#### Component 5: Guided Practice (`We Do` — `Checkpoint [2/4]`)
- Immediately follow Component 4 with a second, slightly richer problem with **~60% of the steps completed** and **2 surgical blanks** (`[Step 2: ___]`, `[Step 4: ___]`) for the user to fill in.
- **Wait for the user's reply** (applying the **Strict Anti-Spoiler Rule** below if they say `"idk"`, `"explain"`, or make an error).

---

### Turn 3 — `Depth Stage: 3/3 (Solo Execution, Deeper Theory & Mastery Gate)` (Components 6 & 7)

Start Turn 3 with the updated stage header:
```text
Lesson X/Y: <Lesson Title> | Depth Stage: 3/3 (Solo Execution, Deeper Theory & Mastery Gate)
```

#### Component 6: Cold Solo Execution & Deepening (`You Do` — `Checkpoint [3/4]`)
1. **Cold Solo Execution (`Checkpoint [3/4]`):** Give a fresh problem with **zero scaffolding** for the user to solve completely on their own. Wait for the user's reply (enforcing the **Strict Anti-Spoiler Rule** if they struggle).
2. **Unlock Depth Stage 3/3 Deeper Theory (~250–350 words):** Once `[3/4]` is solved, unlock the third escalation layer covering:
   - Deeper nuances and scaling behavior.
   - Limiting behaviors ($0$, $1$, $\infty$, negative or degenerate values).
   - Why alternative formulations fail.
   - How this concept connects to advanced downstream topics.

#### Component 7: Adversarial Edge-Case & Feynman Mastery Gate (`Checkpoint [4/4]`)
- Immediately after unlocking Depth Stage 3/3 deeper theory, pose **`Checkpoint [4/4]`**:
  1. Test a tricky boundary/failure input (e.g., zero vector, equal-to-threshold boundary, scaling invariance, or degenerate case).
  2. Ask for a **2-sentence plain-English Feynman Teach-Back** with zero unstated jargon.
- Wait for the user's reply.
- **Batch Markdown Flush, Auto-Log & Auto-Compaction:** Once `[4/4]` passes:
  - Run `vault_cli.py tick <VAULT_PATH> --topic <nn> --cp 4 --status pass --note "<verified invariant>"` and `vault_cli.py flush <VAULT_PATH> --topic <nn> --note "<verified invariant>"`.
  - Log any struggled concepts, micro-steps needed, or corrected misconceptions into `<VAULT_ROOT>/<topic-slug>/learning-records/000N-<slug>.md`.
  - **Auto-Compaction (Every 3 Completed Subtopics):** Append a 5-line **Cumulative Synthesis Strip** to `00-MOC-INDEX.md` and roll up verified formulas into `09-CHEAT-SHEET.md`.
  - Unlock `Lesson X+1` (opening with an **Interleaved Cumulative Recall** warm-up at `Lesson 3` and every 2 lessons thereafter).

---

## 3. Strict Anti-Spoiler Rule & Pedagogical Discipline

### Strict Anti-Spoiler Rule (Drop-Down Micro-Step Protocol)
If the user replies **`"idk"`**, **`"explain"`**, **`"not sure"`**, or makes an error at **any** checkpoint (`[1/4]` through `[4/4]`):
1. **NEVER immediately reveal the final answer or general rule.**
2. Acknowledge any part of their attempt that is on track.
3. Pinpoint the exact step where reasoning diverged.
4. **Drop down one rung to a tiny 1-number micro-question** so the user discovers that single step themselves.
5. Only confirm the general rule or full step **after** they solve the micro-step, then resume the active checkpoint.

### Baseline Calibration (`00-MISSION.md`)
- Always enforce the full **7-Component Blueprint** and **Absolute-0 Prerequisite Micro-Bridge** whenever `Prior Knowledge Baseline` is `No prior knowledge` or `Beginner`, using clean, small scalars in the micro-bridge, `I Do`, and `We Do` before scaling up.
- For `Intermediate` / `Advanced` baselines, keep all 7 components and 4 checkpoints intact while scaling the scenario complexity, mathematical rigor, and Depth Stage 3/3 nuances accordingly.

### Storage Strength vs. Retrieval Fluency
- Never ask `"Do you understand X?"` or simple definition lookups.
- Never bundle multiple checkpoints into a single turn—wait for the user's reply at every checkpoint.

---

## 4. Inline `wait-what` Protocol

If at any point the user replies with **`wait what`**, **`/wait-what`**, **`I'm lost`**, or **`simplify`**:
1. **Pause the active checkpoint immediately**—do not judge or grade them.
2. **Diagnose the Jargon/Abstraction Jump:** Identify the exact symbol, step, or unstated assumption that caused friction.
3. **Re-Pitch from Absolute Zero:** Explain the sticking point using:
   - Strictly canonical terms defined in `04-GLOSSARY.md` (plus a fresh 2-line Zero-Baseline Micro-Bridge if any new term slipped in).
   - A concrete **2-number or 1-number scalar trace** or simpler everyday mental model.
4. **Update the Vault:** Append the clearer explanation or analogy to `<VAULT_ROOT>/<topic-slug>/05-MENTAL-MODELS.md` so the permanent notes improve alongside the user's understanding.
5. **Resume at the Active Checkpoint:** Confirm the re-pitch clicks, then resume at the exact **`Lesson X/Y — Checkpoint [k/4]`** where you paused.

---

## 5. ADR-Style Learning Records (`learning-records/000N-<slug>.md`)

Maintain a chronological log of struggled concepts, corrected misconceptions, breakthroughs, and mission changes inside `<VAULT_ROOT>/<topic-slug>/learning-records/` (numbered `0001-<slug>.md`, `0002-<slug>.md`, etc.). Never delete old records; if a later insight supersedes an earlier understanding or goal, mark the old record `Status: superseded by LR-000N`.

### Template: `<VAULT_ROOT>/<topic-slug>/learning-records/0001-<slug>.md`

```markdown
# LR-0001: <Short Title of Struggled Concept, Misconception Fix, or Breakthrough>

- **Date:** <YYYY-MM-DD>
- **Status:** active
- **Lesson / Milestone:** <Lesson X/Y — Milestone # from 00-MISSION.md>

## Context
<Which checkpoint, micro-step, or misconception triggered this learning moment.>

## Insight / Mastery Demonstrated
<What was clarified, discovered via micro-stepping, or proven—using canonical terms from 04-GLOSSARY.md.>

## Vault Updates Made
- Updated `<filename>` with <specific addition or correction>.
```

---

## 6. Continuous Note Enrichment

Whenever the user shares a new insight, real-world war story, voice transcript, or sharp follow-up question during Phase 6:
- Cleanly format and append it under `## Living Session Notes & Insights` in `<VAULT_ROOT>/<topic-slug>/03-CORNELL-STUDY-GUIDE.md`.
- If it introduces a new core term, add a 1-2 sentence entry to `<VAULT_ROOT>/<topic-slug>/04-GLOSSARY.md`.
- Confirm briefly in chat what was persisted to the vault.
