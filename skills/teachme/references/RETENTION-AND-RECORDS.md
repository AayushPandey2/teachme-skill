# Phase 6 Reference: Hybrid Discovery + 5-Checkpoint Mastery Loop, Learning Records & `wait-what`

---

## 1. Vault Launch & Interleaved Warm-Up

1. **Vault Summary:** After generating the vault files at `~/notes/<topic-slug>/`, present a crisp executive overview (<250 words) and list the generated files (highlighting `00-MOC-INDEX.md` and `topics/*.md`).
2. **Interleaved Warm-Up (Subtopic $N \ge 3$):**
   - Whenever starting Subtopic $N \ge 3$ (e.g., before Subtopic 3 recall Subtopic 1; before Subtopic 4 recall Subtopic 2), open with a **1-question rapid recall check from Subtopic $N-2$** before launching Checkpoint `[1/5]` of Subtopic $N$.
   - Wait for the user's answer (applying the **Anti-Spoiler Productive Struggle Rule** if they miss it), reinforce briefly, and then proceed to the Subtopic $N$ Banner and Checkpoint `[1/5]`.

---

## 2. Banner, Queue Transparency & Strict 5-Checkpoint Mastery Ladder

Replace any "1 theory dump + 1 question" pattern with a strict, sequential **5-Checkpoint Mastery Ladder** for every subtopic.

### Banner & Queue Transparency
- Start every subtopic by displaying its 5-checkpoint roadmap banner:
  ```text
  Subtopic X/Y: <Subtopic Title>
  Roadmap: [1/5] Discovery Prediction → [2/5] Formula & Logic → [3/5] We Do (Faded) → [4/5] You Do (Solo) → [5/5] Edge Case + Feynman Gate
  ```
- Track and display exact progress at the top of **every turn**: **`Subtopic X/Y — Checkpoint [k/5]`** (where `X` is the current subtopic number, `Y` is the total subtopic count in `00-MOC-INDEX.md`, and `k` is `1` through `5`).

### Strict Sequential Order (1 Question per Turn, Zero Skips)

Never skip a checkpoint and never bundle two checkpoints into the same turn. Wait for the user's response at each step:

1. **Checkpoint `[1/5]` — Discovery Prediction Hook (Before Theory):**
   - **Rule:** Do NOT reveal definitions, jargon, or formulas yet.
   - Present a concrete failure scenario or everyday intuition puzzle exposing *why* the naive approach breaks or why this mechanism is needed, and ask the user to predict what happens or what mechanism is required.
   - Wait for the user's prediction.

2. **Deliver 4-Layer Theory (Bridge from Checkpoint `[1/5]` -> Pose Checkpoint `[2/5]`):**
   - Bridge directly from the user's prediction (validating accurate intuition or gently reframing what diverged), then teach the subtopic in the exact **4-Layer Theory Presentation Standard** (Concrete -> Representational -> Abstract):
     1. **Layer 1 — Daily-Life Intuition:** Relatable physical/human analogy + 1-line mental hook (zero technical jargon or math symbols).
     2. **Layer 2 — Theoretical Explanation:** Precise causal mechanism (`Inputs -> Transformation -> Outputs`), clean ASCII or Mermaid flow diagram, a **Contrastive Non-Example** ("What it is NOT" and why a lookalike fails), and an explicit **"Where the Analogy Breaks Down"** note.
     3. **Layer 3 — Mathematical Intuition:** Plain-English geometric, scaling, or behavioral explanation of what the math is doing *before* introducing formal notation.
     4. **Layer 4 — Mathematical Explanation & Formula Anatomy:**
        - Present every formal equation in pure display LaTeX (double-dollar blocks on their own lines, zero backticks around math, `\mid` / `\lvert` / `\rvert` instead of raw `|` inside Markdown tables).
        - Complete Symbol / Operator Breakdown Table (Symbol / Operator | Name & Exact Role | Units / Domain / Shape | Directional Sensitivity) covering every variable, subscript, superscript, constant, and operator.
        - Boundary edge cases (`0`, `1`, `\infty`, negative/degenerate inputs).
        - **Thinking-Aloud `I Do` Worked Trace:** Walk through the equation step-by-step using **3 concrete numbers**, narrating each substitution and interpreting the final value in plain English.
   - Immediately conclude this lesson turn by asking **Checkpoint `[2/5]`** (headed with `Subtopic X/Y — Checkpoint [2/5]`).

3. **Checkpoint `[2/5]` — Formula & Conceptual Logic Check:**
   - Ask one targeted question verifying *why* a specific term/operator exists in the equation or how scaling/directional sensitivity behaves (never `"Do you understand?"` or a simple definition lookup).
   - Wait for the user's response.

4. **Checkpoint `[3/5]` — `We Do` Faded Scaffolding:**
   - Present a second worked problem with ~60% of the steps already filled in and **2 surgical blanks** (`[Step 2: ___]`, `[Step 4: ___]`) for the user to complete.
   - Wait for the user's response.

5. **Checkpoint `[4/5]` — `You Do` Cold Solo Execution:**
   - Give a fresh problem with **zero scaffolding** for the user to solve completely solo.
   - Wait for the user's response.

6. **Checkpoint `[5/5]` — Adversarial Edge Case + Feynman Gate:**
   - Test a boundary/failure case (`0`, `\infty`, negative, or degenerate inputs) **and** ask the user for a **2-sentence plain-English Feynman explanation** with zero unstated jargon.
   - Wait for the user's response.
   - **Mastery Gate:** Only after passing Checkpoint `[5/5]`, check off `- [x]` for that subtopic in `~/notes/<topic-slug>/00-MOC-INDEX.md`, log any breakthrough in `learning-records/`, and advance to Subtopic $X+1$ (opening with an Interleaved Warm-Up from Subtopic $X-1$ whenever the new subtopic index is $\ge 3$).

---

## 3. Anti-Spoiler Productive Struggle & Baseline Calibration

### Anti-Spoiler Productive Struggle Rule
If the user answers incorrectly on **attempt 1** at any checkpoint (`[1/5]` through `[5/5]`):
1. **NEVER reveal the full answer.**
2. Acknowledge any part of their reasoning that is sound.
3. **Pinpoint the exact step** where their reasoning or calculation diverged.
4. Give a **surgical hint or simpler sub-question** targeting only that divergent step, and let the user self-correct on the next turn.

### Baseline Calibration (`00-MISSION.md`)
Keep the strict 5-checkpoint sequence for **all** baselines (zero skips), while calibrating scenario framing and numerical complexity to `Prior Knowledge Baseline` in `00-MISSION.md`:
- **For `No prior knowledge (Zero-baseline first principles)` / `Beginner` baselines:**
  - Keep Checkpoint `[1/5]` strictly jargon-free and grounded in an everyday scenario.
  - Use small, clean scalar numbers in the `I Do` 3-number trace, `We Do`, and `You Do` before introducing 2D geometry, vectors/matrices, or multi-variable coupling.
  - Keep surgical hints concrete and trace-oriented.
- **For `Intermediate` / `Advanced` baselines:**
  - Anchor Checkpoint `[1/5]` in a realistic systems/production failure puzzle or architectural paradox.
  - Probe non-obvious operator interactions in `[2/5]`, multi-step transformations in `[3/5]`–`[4/5]`, and subtle degenerate/asymptotic edge cases in `[5/5]`.

### Pedagogical Discipline (Storage Strength vs. Retrieval Fluency)
- **Test Storage, Not Recognition:** Never ask `"Do you understand X?"` or pure recall lookups.
- **One Checkpoint per Turn:** Never stack multiple checkpoints in a single message.

---

## 4. Inline `wait-what` Protocol

If at any point the user replies with **`wait what`**, **`/wait-what`**, **`I'm lost`**, or **`simplify`**:
1. **Pause the active checkpoint immediately**—do not judge or grade them.
2. **Diagnose the Jargon/Abstraction Jump:** Identify the exact concept, symbol, or unstated assumption that caused friction.
3. **Re-Pitch in Plain English:** Explain the sticking point from scratch using:
   - Strictly canonical terms defined in `04-GLOSSARY.md` (defining any new word inline).
   - A concrete **1-number scalar trace** or simpler everyday mental model.
4. **Update the Vault:** Append the clearer explanation or analogy to `~/notes/<topic-slug>/05-MENTAL-MODELS.md` so the permanent notes improve alongside the user's understanding.
5. **Resume at the Active Checkpoint:** Confirm the re-pitch clicks, then resume at the exact **`Subtopic X/Y — Checkpoint [k/5]`** where you paused (without skipping ahead).

---

## 5. ADR-Style Learning Records (`learning-records/000N-<slug>.md`)

Maintain a chronological log of breakthroughs, corrected misconceptions, and mission changes inside `~/notes/<topic-slug>/learning-records/` (numbered `0001-<slug>.md`, `0002-<slug>.md`, etc.). Never delete old records; if a later insight supersedes an earlier understanding or goal, mark the old record `Status: superseded by LR-000N`.

### Template: `~/notes/<topic-slug>/learning-records/0001-<slug>.md`

```markdown
# LR-0001: <Short Title of Breakthrough, Misconception Fix, or Mission Shift>

- **Date:** <YYYY-MM-DD>
- **Status:** active
- **Milestone:** <Milestone # from 00-MISSION.md>

## Context
<What question, checkpoint, or confusion triggered this learning moment.>

## Insight / Mastery Demonstrated
<What was clarified, proven, or decided—using canonical terms from 04-GLOSSARY.md.>

## Vault Updates Made
- Updated `<filename>` with <specific addition or correction>.
```

---

## 6. Continuous Note Enrichment

Whenever the user shares a new insight, real-world war story, voice transcript, or sharp follow-up question during Phase 6:
- Cleanly format and append it under `## Living Session Notes & Insights` in `~/notes/<topic-slug>/03-CORNELL-STUDY-GUIDE.md`.
- If it introduces a new core term, add a 1-2 sentence entry to `~/notes/<topic-slug>/04-GLOSSARY.md`.
- Confirm briefly in chat what was persisted to the vault.
