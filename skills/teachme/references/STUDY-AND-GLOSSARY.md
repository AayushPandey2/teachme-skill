# Phases 3, 4 & 5 Reference: First-Principles Synthesis, Glossary, Derivations, MOC, Cornell Notes, Subtopic Deep-Dives, Flashcards & Zettelkasten

---

## 1. Phase 3A: First-Principles & Adversarial Models (`05-MENTAL-MODELS.md`)

Combine Feynman translation with divergent-to-convergent first-principles deconstruction, ASCII architecture diagrams, and adversarial pre-mortem inversion:

````markdown
# Mental Models & First-Principles Breakdown: <Topic Title>

## 1. Zero-Jargon Feynman Core
<Explain the entire mechanism in 2-3 paragraphs of plain everyday English using one concrete, physical analogy. Highlight both where the analogy holds and where it breaks down.>

## 2. First-Principles Axiom Stack
Rebuild `<topic>` from irreducible truths:
1. **Axiom 1 (<Fundamental Constraint/Truth>):** <Why this must be true regardless of implementation.>
2. **Axiom 2 (<Derived Necessity>):** <How combining Axiom 1 with the core problem constraint forces the design.>
3. **Axiom 3 (<Architectural Consequence>):** <Why the system takes its canonical shape.>

## 3. System Architecture & Flow Diagram (ASCII)
```text
<Clean ASCII diagram showing components, data/control flow, and state transitions>
```

## 4. Adversarial Pre-Mortem (How to Break It)
Assume the system just caused a catastrophic production outage or subtle data corruption. How did it happen?
1. **Failure Mode 1 (<Name>):**
   - *Trigger:* <Exact condition or workload that triggers the failure>
   - *Blast Radius:* <Silent corruption, latency spike, deadlock, or crash>
   - *Defensive Invariant:* <How to prevent, detect, or mitigate it>
2. **Failure Mode 2 (<Name>):**
   - *Trigger:* <Exact condition or workload>
   - *Blast Radius:* <Impact>
   - *Defensive Invariant:* <Mitigation>
3. **Failure Mode 3 (<Name>):**
   - *Trigger:* <Exact condition or workload>
   - *Blast Radius:* <Impact>
   - *Defensive Invariant:* <Mitigation>
````

---

## 2. Phase 3B: Canonical Domain Glossary (`04-GLOSSARY.md`)

Keep `04-GLOSSARY.md` lean, authoritative, and strictly focused on **what each term IS** (never dump implementation tutorials or usage guides into the glossary):

```markdown
# Canonical Glossary: <Topic Title>

> **Rule:** Every definition is 1-2 sentences stating *what the term IS*. Use the canonical term consistently across all notes and discussions.

- **<Canonical Term 1>:** <1-2 sentence crisp definition stating what the term IS.>
  _Avoid:_ <Sloppy or overloaded synonym/alias to avoid>.
- **<Canonical Term 2>:** <1-2 sentence crisp definition stating what the term IS.>
  _Avoid:_ <Sloppy or overloaded synonym/alias to avoid>.
```

---

## 3. Phase 3C: Step-by-Step Derivations Appendix (`06-DERIVATIONS-AND-PROOFS.md`)

Ensure zero "magic formulas" appear anywhere in the vault by deriving every major equation, complexity bound, and theorem step-by-step from base axioms:

```markdown
# Step-by-Step Derivations & Proofs: <Topic Title>

> **Rule:** Every major equation, complexity bound, and theorem is derived from base axioms with explicit step-by-step justifications.

## 1. Derivation of <Formula / Theorem Name>
- **Target Formula:**
$$
<Target LaTeX Equation>
$$
- **Starting Axioms / Premises:** <Explicit base definitions, axioms, or assumptions from `04-GLOSSARY.md` / `05-MENTAL-MODELS.md`>.
- **Cross-References:** [[topics/<nn>-<subtopic-slug>]] | [[04-GLOSSARY#<term>]]

### Step-by-Step Proof
1. **Step 1:**
   $$<Starting expression>$$
   *Why this holds:* <1-sentence justification>.
2. **Step 2:**
   $$<Intermediate algebraic or logical transition>$$
   *Why this holds:* <1-sentence justification>.
3. **Step 3 (Final Form):**
   $$<Target LaTeX Equation>$$
   *Why this holds:* <1-sentence justification>.
```

---

## 4. Mandatory Formula Anatomy Breakdown Standard (Layer 3 + Layer 4 Schema)

**Non-Negotiable Rules:**
- Across `02-DEEP-RESEARCH.md`, `03-CORNELL-STUDY-GUIDE.md`, and **every** `topics/<nn>-<subtopic-slug>.md` file, **no mathematical formula, equation, recurrence, objective/loss function, or complexity bound** may appear without **Layer 3 (Mathematical Intuition before formal notation)** and an immediate **Layer 4 Formula Anatomy Breakdown** following this exact structure.
- **Zero Backtick-Wrapped Math:** **NEVER** wrap inline or display LaTeX delimiters in backticks anywhere—especially not inside Markdown table cells. Always write raw `$` / `$$` math delimiters directly without code ticks.
- **Table-Safe LaTeX Delimiters & Escaping:** Inside Markdown table cells, **NEVER** use raw pipe `|` characters inside math (always use `\mid`, `\lvert`, `\rvert`, `\lVert`, `\rVert`). Keep single-line inline math free of unescaped newlines and verify every opening and closing math delimiter matches.
- **Zero-Dead-Link Generation:** Only emit `[[wikilinks]]` or `[text](path.md)` links whose exact target file exists on disk (never link to hypothetical files or `[[none]]`).

```markdown
- **Mathematical Intuition (Before Notation):** <1–3 sentences of plain-English geometric, scaling, or behavioral intuition explaining what the math is doing before showing formal symbols.>

$$
<Display LaTeX Equation>
$$

| Symbol / Operator | Name & Exact Role in the Equation | Units / Domain / Shape | Directional Sensitivity |
|---|---|---|---|
| $x$ | <Name & exact role> | <e.g., $\mathbb{R}^d$, scalar $>0$, bytes> | <What happens to the output when $x$ increases or decreases> |
| $\sum_{i=1}^{n}$ | <Summation operator over all $n$ items> | <Dimensionless aggregator> | <More terms / larger positive terms increase the sum linearly> |
| ... | ... | ... | ... |

- **Boundary & Limiting Cases:**
  - As $<var> \to 0$: <Exact mathematical & physical/system behavior>.
  - As $<var> \to 1$ (if applicable): <Exact behavior>.
  - As $<var> \to \infty$: <Exact behavior / asymptote / saturation>.
  - Negative / degenerate inputs (if applicable): <Exact failure or clamping behavior>.
- **Concrete 3-Number Worked Trace (`I Do`):**
  1. **Inputs (3 Concrete Numbers):** <3 specific, realistic numbers with units/shapes>.
  2. **Step-by-Step Substitution:** <Plug the 3 numbers step-by-step into the equation, thinking aloud>.
  3. **Evaluation & Plain-English Interpretation:** <Final number + what it means intuitively>.
```

*Every single variable, subscript, superscript, constant, and mathematical operator ($\sum$, $\prod$, $\nabla$, $\log$, $\arg\max$, $\mathbb{E}$, norms, matrices, etc.) in the equation MUST have a row in the Component & Operator Breakdown Table.*

---

## 5. Phase 4A: Master Cornell Study Guide (`03-CORNELL-STUDY-GUIDE.md`)

Synthesize `00-MISSION.md`, `02-DEEP-RESEARCH.md`, `04-GLOSSARY.md`, `05-MENTAL-MODELS.md`, `06-DERIVATIONS-AND-PROOFS.md`, and every `topics/<nn>-<subtopic-slug>.md` file into a comprehensive Markdown study guide. Its syllabus index and sections MUST explicitly link to **every single** `[[topics/<nn>-<subtopic-slug>]]` file created.

````markdown
# Cornell Study Guide: <Topic Title>

- **Date:** <YYYY-MM-DD>
- **Map of Content:** [[00-MOC-INDEX]]
- **Mission:** [[00-MISSION]] | **Research:** [[02-DEEP-RESEARCH]] | **Glossary:** [[04-GLOSSARY]] | **Models:** [[05-MENTAL-MODELS]] | **Derivations:** [[06-DERIVATIONS-AND-PROOFS]] | **Flashcards:** [[08-FLASHCARDS]]
- **Executive Thesis:** <2-sentence synthesis capturing the core mechanism and why it matters.>

---

## Complete Syllabus Index
> Every subtopic below has a dedicated, full-length deep-dive file in `topics/`.

1. [[topics/01-<subtopic-slug>]] — <1-line summary of what this subtopic covers>
2. [[topics/02-<subtopic-slug>]] — <1-line summary>
...
NN. [[topics/<nn>-<subtopic-slug>]] — <1-line summary>

---

## 1. <Milestone 1 Title>
*Deep-dive files:* [[topics/01-<subtopic-slug>]], [[topics/02-<subtopic-slug>]]

<Thorough, structured explanation using **bold terms** from `04-GLOSSARY.md` on first appearance, bullet points, and inline [Source] citations. Any formula here MUST include its full Formula Anatomy Breakdown.>

### Worked Example / Annotated Code
```<language>
// Concrete, realistic, annotated example (never foo/bar placeholders)
```

### Active-Recall Cue Questions (Milestone 1)
- **Cue 1:** <Diagnostic or mechanism-tracing question?>
  <details><summary>Reveal Answer</summary>
  <Crisp, complete answer grounded in first principles and primary sources.>
  </details>
- **Cue 2:** <Edge-case or failure-prediction question?>
  <details><summary>Reveal Answer</summary>
  <Crisp, complete answer explaining what breaks and why.>
  </details>

---

## 2. <Milestone 2 Title>
*Deep-dive files:* [[topics/03-<subtopic-slug>]], ...

<Thorough, structured explanation of internal architecture, state transitions, and invariants [Source], with Formula Anatomy Breakdowns for any equations.>

### Active-Recall Cue Questions (Milestone 2)
- **Cue 1:** <Why does invariant X hold under condition Y?>
  <details><summary>Reveal Answer</summary>
  <Complete explanation.>
  </details>

---

## 3. Trade-Offs, Edge Cases & Comparative Matrix
| Criterion | <Topic> | <Alternative A> | <Alternative B> |
|---|---|---|---|
| **Mechanism** | ... | ... | ... |
| **Latency / Throughput** | ... | ... | ... |
| **Failure Mode** | ... | ... | ... |
| **When to Choose** | ... | ... | ... |

### Active-Recall Cue Questions (Milestone 3 & 4)
- **Cue 1:** <Scenario-based design trade-off question?>
  <details><summary>Reveal Answer</summary>
  <Complete trade-off analysis.>
  </details>

---

## Cornell Summary Synthesis (Bottom-Line Takeaways)
1. **Core Problem Solved:** <1-sentence takeaway>
2. **Key Architectural Mechanism:** <1-sentence takeaway>
3. **Critical Invariant:** <1-sentence takeaway>
4. **Sharpest Edge / Failure Mode:** <1-sentence takeaway>
5. **Decision Rule:** <When to use `<topic>` vs. when to reach for an alternative.>

---

## Living Session Notes & Insights
- *[<YYYY-MM-DD>]* <Initial vault synthesis completed. Ongoing Socratic insights, war stories, and follow-up Q&A are appended here automatically.>
````

---

## 6. Phase 4B: Dedicated Per-Subtopic Deep-Dive Files (`topics/<nn>-<subtopic-slug>.md`)

For **every single topic and subtopic** in the Phase 2 exhaustive syllabus (no arbitrary file cap; never compress, merge, or skip subtopics), generate a full-length, standalone Markdown file inside `~/notes/<topic-slug>/topics/<nn>-<subtopic-slug>.md` numbered sequentially (`01-...`, `02-...`, etc.).

**Mandatory 4-Layer Theory Presentation Standard (Concrete -> Representational -> Abstract):**
Every subtopic file MUST present its core concept in this exact 4-layer sequence before moving to code examples, edge cases, and self-checks:
1. **Layer 1 — Daily-Life Intuition:** Relatable everyday physical/human analogy + 1-line mental hook (written *before* introducing any technical jargon or math symbols).
2. **Layer 2 — Theoretical Explanation:** Precise causal mechanism (`Inputs -> Transformation -> Outputs`), ASCII/Mermaid flow diagram, a **Contrastive Non-Example** ("What it is NOT" and why a lookalike fails), and an explicit **"Where the Analogy Breaks Down"** note.
3. **Layer 3 — Mathematical Intuition:** Plain-English geometric, scaling, or behavioral explanation of what the math is doing *before* showing formal notation.
4. **Layer 4 — Mathematical Explanation & Formula Anatomy:** Formal LaTeX equation in pure display math (zero backticks around math, `\mid` instead of `|` inside tables), complete Symbol/Operator Breakdown Table with directional sensitivity, boundary edge cases (`0`, `1`, `\infty`, negative/degenerate), and a concrete 3-number worked trace (`I Do`).

````markdown
---
topic: "<Topic Title>"
subtopic: "<Subtopic Title>"
order: <nn>
prerequisites:
  - "[[topics/<prereq-subtopic>]]" # or [] if none
parent: "[[03-CORNELL-STUDY-GUIDE]]"
---

# <nn>. <Subtopic Title>

## 1. Layer 1 — Daily-Life Intuition
<Relatable, everyday physical or human analogy explaining why this mechanism exists—written BEFORE introducing any technical jargon or math symbols.>

- **1-Line Mental Hook:** <One crisp sentence locking in the core intuition.>

## 2. Layer 2 — Theoretical Explanation
- **Causal Mechanism (Inputs → Transformation → Outputs):** <Precise step-by-step mechanics with zero hand-waving: exact inputs, state transitions/transformations, invariants, and outputs using **bolded canonical terms** from `04-GLOSSARY.md` and inline [Source] citations.>

```text
<Clean ASCII or Mermaid flow diagram showing Inputs -> Transformation -> Outputs>
```

- **Contrastive Non-Example ("What it is NOT"):** <Describe a common lookalike or naive alternative and explain specifically why it fails or behaves differently [Source].>
- **Where the Analogy Breaks Down:** <Explicit boundary explaining where Layer 1's everyday analogy diverges from the true formal mechanism.>

## 3. Layer 3 — Mathematical Intuition
<Plain-English geometric, scaling, or behavioral explanation of what the math is doing—how terms compete, grow, normalize, or project—written BEFORE showing formal equations or notation.>

## 4. Layer 4 — Mathematical Explanation & Formula Anatomy
<Every formal equation, recurrence, objective/loss function, or complexity bound for this subtopic rendered in pure display LaTeX (zero backticks, `\mid` / `\lvert` / `\rvert` inside tables) and immediately followed by its full Formula Anatomy Breakdown. If a purely non-mathematical subtopic has no formal equations, explicitly state "No formal equations govern this mechanism" and provide exact complexity/capacity bounds or invariant inequalities with full breakdown.>

$$
<Display LaTeX Equation>
$$

| Symbol / Operator | Name & Exact Role in the Equation | Units / Domain / Shape | Directional Sensitivity |
|---|---|---|---|
| $x$ | <Name & exact role> | <Units / domain / shape> | <Effect on output when $x$ increases or decreases> |
| ... | ... | ... | ... |

- **Boundary Edge Cases:**
  - Input $= 0$: <Exact behavior>.
  - Input $= 1$ (if applicable): <Exact behavior>.
  - Input $\to \infty$: <Exact limiting behavior>.
  - Negative / degenerate inputs (if applicable): <Exact behavior>.
- **Concrete 3-Number Worked Trace (`I Do`):**
  1. **Inputs (3 Concrete Numbers):** <3 specific, realistic numbers with units/shapes>.
  2. **Step-by-Step Substitution:** <Plug the 3 numbers step-by-step into the equation>.
  3. **Evaluation & Plain-English Interpretation:** <Final value + plain-English meaning>.

## 5. Worked Examples / Annotated Code
```<language>
// Realistic, end-to-end annotated example (never foo/bar placeholders)
```

## 6. Edge Cases, Failure Modes & Trade-offs
- **Edge Case / Failure Mode 1:** <Trigger, blast radius, and mitigation> [Source].
- **Trade-offs:** <What this design optimizes for vs. what it sacrifices>.

## 7. Subtopic Self-Check Questions
- **Question 1:** <Diagnostic, mechanism-tracing, or failure-prediction question?>
  <details><summary>Reveal Answer</summary>
  <Complete answer grounded in first principles and primary sources.>
  </details>
- **Question 2:** <Transfer or edge-case question?>
  <details><summary>Reveal Answer</summary>
  <Complete answer.>
  </details>

---
**Navigation:** ← [[<prev-subtopic>|Previous]] | [[03-CORNELL-STUDY-GUIDE|Study Guide]] | [[<next-subtopic>|Next]] →
````

---

## 7. Phase 4C: Master Map of Content (`00-MOC-INDEX.md`)

Create `~/notes/<topic-slug>/00-MOC-INDEX.md` as the central navigation dashboard so Obsidian and Markdown navigation stays effortless regardless of vault size:

````markdown
# Map of Content (MOC): <Topic Title>

## Vault Navigation
- [[00-MISSION]] — Target outcome, success criteria & scope boundaries
- [[01-RESOURCES]] — Primary Knowledge, practitioner Wisdom, exhaustive syllabus & gaps
- [[02-DEEP-RESEARCH]] — Primary-source research dossier & benchmarks
- [[03-CORNELL-STUDY-GUIDE]] — Master synthesized study guide
- [[04-GLOSSARY]] — Canonical 1–2 sentence domain definitions
- [[05-MENTAL-MODELS]] — Feynman analogies, axioms, ASCII architecture & pre-mortem
- [[06-DERIVATIONS-AND-PROOFS]] — Step-by-step axiom-to-formula derivations
- [[07-PRACTICE-PROBLEMS]] — Applied problem sets & scenarios (if generated)
- [[08-FLASHCARDS]] — Spaced-repetition & cloze active-recall deck
- [[09-CHEAT-SHEET]] — Distilled 1-page executive cheat sheet (via `/teachme distill`)

---

## Comparisons
- <Cross-vault comparisons linked here automatically by `/teachme compare`, e.g. `[[../comparisons/<topic-a>-vs-<topic-b>]]`>

---

## Prerequisite & Dependency Graph

```mermaid
graph TD
  T01["01: <Subtopic A>"] --> T02["02: <Subtopic B>"]
  T02 --> T03["03: <Subtopic C>"]
```

### ASCII Dependency Tree (Plain-Text Fallback)
```text
01: <Subtopic A>
└── 02: <Subtopic B>
    └── 03: <Subtopic C>
```

---

## Complete Subtopic Syllabus Tracker (`topics/`)
> Check off `- [x]` as each subtopic is mastered during Phase 6.

- [ ] **01.** [[topics/01-<subtopic-slug>]] `[Beginner]` — *Prereqs: None*
- [ ] **02.** [[topics/02-<subtopic-slug>]] `[Intermediate]` — *Prereqs: [[topics/01-<subtopic-slug>]]*
- [ ] **03.** [[topics/03-<subtopic-slug>]] `[Advanced]` — *Prereqs: [[topics/02-<subtopic-slug>]]*

---

## Atomic Zettelkasten Concept Index (`atomic/`)
- [ ] [[atomic/<concept-slug-1>]] `[Beginner]` — *Parent:* [[topics/01-<subtopic-slug>]]
- [ ] [[atomic/<concept-slug-2>]] `[Intermediate]` — *Parent:* [[topics/02-<subtopic-slug>]]
````

---

## 8. Phase 4D: Spaced-Repetition Cloze & Flashcard Deck (`08-FLASHCARDS.md`)

Generate `~/notes/<topic-slug>/08-FLASHCARDS.md` formatted cleanly for **Obsidian Spaced Repetition** (`#flashcards/<topic-slug>`) and **Anki** import:

```markdown
# Spaced-Repetition Flashcards: <Topic Title>

#flashcards/<topic-slug>

## 1. Conceptual & Mechanism Cards

<Single-line question testing an invariant, trade-off, or failure mode> :: <Crisp, exact answer>

<Multi-line diagnostic question>
?
<Complete, structured answer grounded in `04-GLOSSARY.md` and `05-MENTAL-MODELS.md`.>

---

## 2. Formula & Symbol Cloze Cards

For `<Formula Name>` ($$<Equation>$$): the term ==$<symbol>$== represents ==<exact name, role, and units>==; as ==$<symbol>$== $\to \infty$, the output ==<limiting behavior>==.

For `<Formula Name>`: increasing ==$<variable>$== causes the output to ==<increase / decrease / saturate>== because ==<1-clause mathematical reason>==.
```

---

## 9. Phase 5: Atomic Zettelkasten Cards (`atomic/`)

Create standalone Markdown cards inside `~/notes/<topic-slug>/atomic/<concept-slug>.md` for every key mechanism, theorem, invariant, and failure mode (no arbitrary card cap). Each card must express **one atomic concept** in 150-300 words so it is reusable across vaults:

```markdown
---
tags:
  - <topic-slug>
  - evergreen
created: <YYYY-MM-DD>
status: evergreen
parent: "[[03-CORNELL-STUDY-GUIDE]]"
---

# <Atomic Concept Title>

<150-300 words explaining this single concept clearly in your own words, grounded in 04-GLOSSARY.md terminology and citing primary sources [Source]. Include a brief concrete example or invariant.>

## Related Concepts
- [[<sibling-concept-1>]] — <Explicit explanation of how or why it connects (e.g., "Enforces the invariant required by...")>
- [[<sibling-concept-2>]] — <Explicit explanation of dependency or contrast>
```
