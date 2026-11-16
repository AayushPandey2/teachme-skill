# Phase 6 Reference: 4-Turn Progressive Pacing, ONE-Question Rule & Learning Records

---

## 1. CLI-Backed Spreading Activation, Question Queue & Delta-Flush Protocol

1. **Zero-Token Resume & Graph Lookup:**
   - On session start or resume, run `scripts/vault_cli.py state <VAULT_PATH>` and `scripts/vault_cli.py graph <VAULT_PATH>` instead of reading multiple Markdown files.
2. **Spreading-Activation 1-Hop Context Rule:**
   - When teaching active `topic-<nn>`, load **ONLY**:
     - Active `topic-<nn>` via `vault_cli.py slice` for the current stage (`L1-ANCHOR`/`L2-PREREQS-AND-MOTIVATION` for Turn 1; `L3-FOUR-LAYER-THEORY`/`L4-DERIVATION-AND-CODE` for Turn 2; `L5-WORKBOOK-AND-GRAPH` for Turns 3–4).
     - Immediate **1-hop neighbors** (`depends_on` and `contrasts_with` from `00-GRAPH.json`) via `--section L0-L1` (~25 lines).
   - **Strictly forbid** loading mastered nodes $>1$ hop away unless an interleaved warm-up explicitly queries them.
3. **Pre-Computed Subtopic Question Queue (`scratchpad/queue-<nn>.json`):**
   - At the start of `Lesson <nn>`, write a compact 4-item JSON queue (`{"topic": "03", "cp": {"1": "...", "2": "...", "3": "...", "4": "..."}}`) at `scratchpad/queue-<nn>.json` and read only it on subsequent turns.
4. **Append-Only Delta Logging -> Batch Markdown Flush:**
   - Record Checkpoints `[1/4]`–`[3/4]` solely via `vault_cli.py tick <VAULT_PATH> --topic <nn> --cp <1..3> --status <pass|retry> [--note "..."]`.
   - Perform the full Markdown flush **only once** upon passing Checkpoint `[4/4]` via `vault_cli.py flush <VAULT_PATH> --topic <nn> --note "<verified invariant>"`.
5. **Vault Summary & Interleaved Cumulative Recall:**
   - After initial vault build, print a crisp executive overview (<250 words) highlighting `00-SESSION-STATE.md`, `00-GRAPH.json`, `00-MOC-INDEX.md`, and `topics/*.md`.
   - Starting at `Lesson 3` and every 2 lessons thereafter (`Lesson 3`, `5`, `7`...), open with **ONE** quick warm-up question blending a previous lesson's concept (sliced via `--section L0-L1`) with the current lesson before Turn 1.

---

## 2. Strict "ONE Question Per Turn" Law & 4-Turn Progressive Lesson Pacing

**Non-Negotiable Rule:** **NEVER** ask multiple numbered questions (`1.`, `2.`, `3.`) in a single turn. Every turn MUST end with **exactly ONE focused question**, and you MUST wait for the user's reply before advancing.

### Turn 1 — `Depth Stage 1/3: Intuition & Discovery Hook` (ZERO Greek Symbols or Set Notation)
- **Banner:** `Lesson X/Y: <Title> | Stage 1/3 (Intuition) | Vault: topics/<nn>-<slug>.md`
- **Progress Strip:** `Path: [1/4] Discovery → [2/4] Guided (We Do) → [3/4] Solo (You Do) → [4/4] Edge-Case & Feynman`
- **`### The Problem & Real-World Hook`:** Write 3–4 sentences giving a concrete everyday analogy + a 4–6 line **ASCII visual diagram** showing inputs entering the system. Do **NOT** introduce `\theta`, `\sum`, set notation (`x_i \in \{0,1\}`), or formal equations yet, and do **NOT** spoil the exact mathematical rule.
- **`### Checkpoint [1/4] — Design Prediction`:** Ask **ONE** pre-formula design/prediction question (e.g., *"If every input has a fixed, unchangeable weight of +1 and a hardcoded cutoff, what happens when we try to teach this neuron a new pattern from data?"*).

### Turn 2 — `Depth Stage 2/3: Building Blocks, Formal Math & Guided Practice`
- Validate the user's `[1/4]` prediction (using the Strict Anti-Spoiler micro-hint rule if they answered `"idk"` or guessed wrong).
- **`### Building Blocks (From Scratch)`:** Now introduce the 2–3 exact symbols needed (`$x_i$`, `$\sum$`, `$\theta$`) with concrete 2-number examples.
- **`### Formal Equation & Worked Example (I Do)`:** Present the clean `$$...$$` equation (zero backticks), symbol breakdown table, and a 3-step numerical walkthrough (`I Do`) with zero skipped algebraic steps.
- **`### Checkpoint [2/4] — Guided Practice (We Do)`:** Give **ONE** faded fill-in-the-blank problem (`[Step 2: ___]`) testing a boundary or edge-case interaction for the user to complete.

### Turn 3 — `Depth Stage 3/3: Solo Execution`
- **`### Checkpoint [3/4] — Solo Drill (You Do)`:** Give **ONE** fresh problem with zero scaffolding.

### Turn 4 — `Depth Stage 3/3: Edge Cases & Mastery Gate`
- **`### Checkpoint [4/4] — Boundary Stress-Test & Feynman Check`:** Ask **ONE** adversarial edge-case + plain-English synthesis question (e.g., testing a boundary/veto override and summarizing the mechanism in 2 plain sentences with zero unstated jargon).
- **Batch Flush & Advance:** Upon passing `[4/4]`, run `vault_cli.py tick ... --cp 4 --status pass --note "<verified invariant>"` and `vault_cli.py flush <VAULT_PATH> --topic <nn> --note "<verified invariant>"`, log any struggled concepts in `learning-records/000N-<slug>.md`, append a 5-line **Cumulative Synthesis Strip** to `00-MOC-INDEX.md` + roll up formulas into `09-CHEAT-SHEET.md` every 3 completed subtopics, and advance to `Lesson X+1`.

---

## 3. Strict Anti-Spoiler Rule & Baseline Calibration

### Strict Anti-Spoiler Rule (Drop-Down Micro-Step Protocol)
If the user replies **`"idk"`**, **`"explain"`**, **`"not sure"`**, or makes an error at **any** checkpoint (`[1/4]` through `[4/4]`):
1. **NEVER immediately reveal the final answer or general rule.**
2. Acknowledge any sound part of their reasoning and pinpoint the exact divergent step.
3. **Drop down one rung to ONE tiny 1-number micro-question** so the user discovers that step themselves.
4. Only confirm the general rule after they solve the micro-step, then resume the active checkpoint.

### Baseline Calibration (`00-MISSION.md`)
- For `No prior knowledge` / `Beginner`, keep Turn 1 strictly jargon-free and symbol-free, and use small clean scalars in Turn 2's Building Blocks, `I Do`, and `We Do`.
- For `Intermediate` / `Advanced`, keep the exact 4-turn structure and ONE-question-per-turn law while scaling scenario depth and Turn 4 adversarial limits.

---

## 4. Inline `wait-what` Protocol

If at any point the user replies with **`wait what`**, **`/wait-what`**, **`I'm lost`**, or **`simplify`**:
1. **Pause the active checkpoint immediately.**
2. **Diagnose the Abstraction Jump** and re-pitch from scratch using `04-GLOSSARY.md` terms + a concrete 1-number scalar trace.
3. **Update the Vault:** Append the clearer analogy to `<VAULT_ROOT>/<topic-slug>/05-MENTAL-MODELS.md`.
4. **Resume** at the exact **`Lesson X/Y — Checkpoint [k/4]`** where you paused.

---

## 5. ADR-Style Learning Records (`learning-records/000N-<slug>.md`)

Log struggled concepts, corrected misconceptions, breakthroughs, and mission shifts in `<VAULT_ROOT>/<topic-slug>/learning-records/000N-<slug>.md` (never delete old records; mark superseded ones `Status: superseded by LR-000N`):

```markdown
# LR-0001: <Short Title>
- **Date:** <YYYY-MM-DD> | **Status:** active | **Lesson:** <Lesson X/Y>
## Context
<Which checkpoint, micro-step, or misconception triggered this record.>
## Insight / Mastery Demonstrated
<What was clarified or discovered using canonical `04-GLOSSARY.md` terms.>
## Vault Updates Made
- Updated `<filename>` with <specific addition>.
```

---

## 6. Continuous Note Enrichment

Append user insights or war stories under `## Living Session Notes & Insights` in `03-CORNELL-STUDY-GUIDE.md` (and new canonical terms to `04-GLOSSARY.md`), confirming briefly in chat.
