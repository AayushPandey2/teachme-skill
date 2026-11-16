# Phase 4B & Formula Reference: Formula Anatomy, 8-Block Subtopic Notes & 7-Point Critic Audit

---

## 1. Mandatory Formula Anatomy Breakdown Standard

Across `02-DEEP-RESEARCH.md`, `03-CORNELL-STUDY-GUIDE.md`, and every `topics/<nn>-<subtopic-slug>.md`, **every** formula/recurrence/bound MUST include:
1. **Zero-Baseline Micro-Bridge** for any new symbol (2–3 plain-English lines + 2-number example).
2. **Mathematical Intuition (Before Symbols)** explaining geometry/scaling before formal notation.
3. **Display LaTeX (`$$...$$`)** — zero backticks around `$`/`$$`, `\mid`/`\lvert`/`\rvert` instead of raw `|` inside tables.
4. **Symbol & Operator Table** covering every variable, subscript, superscript, constant, and operator.
5. **Zero-Skip `I Do` Trace** + **Limiting Cases** (`0`, `1`, `-1`, `\infty`, degenerate).

---

## 2. Detailed Subtopic Notes — 8-Block Standard (`topics/<nn>-<subtopic-slug>.md`)

Partition every `topics/*.md` file with the 5 strict HTML markers (`L1-ANCHOR`..`L5-WORKBOOK-AND-GRAPH`) for `L0`/`L1`/`L2` progressive disclosure:

````markdown
---
id: "topic-<nn>"
title: "<Subtopic Title>"
status: "unstarted"
checkpoint: "0/4"
depends_on: ["topic-<prev>-<slug>"]
unlocks: ["topic-<next>-<slug>"]
contrasts_with: ["topic-<lookalike>-<slug>"]
fixes_failure_of: ["topic-<broken-method>-<slug>"]
key_equations:
  - "<clean LaTeX equation>"
---

# <nn>. <Subtopic Title>

<!-- SECTION: L1-ANCHOR -->
## 1. The 30-Second Executive Anchor
- **Core Thesis:** <2–3 sentences: problem solved, mechanism, unbreakable invariant.>
- **One-Line Mental Hook:** <1-sentence vivid recall hook.>

<!-- SECTION: L2-PREREQS-AND-MOTIVATION -->
## 2. Zero-Baseline Prerequisite Micro-Bridge & Engineering Motivation

> [!note] Zero-Baseline Prerequisites
> Define every new symbol/operator/term from scratch before use:
> - **<Term 1>:** <2–3 plain-English lines + 2-number example.>

### Engineering Motivation ("Why This Had to Be Invented")
<3–4 sentences on what failed or scaled poorly previously [Source].>

<!-- SECTION: L3-FOUR-LAYER-THEORY -->
## 3. 4-Layer Deep Theory Stack

### Layer 1 — Daily-Life Intuition
<Thorough physical/human analogy with zero jargon.>

### Layer 2 — Theoretical Mechanism, Visual Diagram & Contrastive Boundaries
- **Causal Mechanism (`Input → Transformation → Output`):** <Step-by-step causal walkthrough using **bolded** `04-GLOSSARY.md` terms [Source].>

```text
<Mandatory ASCII geometry/pipeline/state diagram>
```

#### Contrastive "Is vs. Is Not" Table
| Dimension | <This Concept> (What It IS) | <Closest Lookalike> (What It Is NOT) |
|---|---|---|
| **Core Mechanism** | <Exact mechanism> | <How lookalike differs/fails> |
| **Invariant** | <What strictly holds> | <Where lookalike breaks> |
| **Failure Mode** | <Real edge behavior> | <Lookalike trap> |

> [!warning] Where the Analogy Breaks Down
> <Where Layer 1's everyday analogy diverges from true mechanics.>

### Layer 3 — Mathematical Intuition (Before Symbols)
<Plain-English geometric, scaling, directional & limiting behavior before formal symbols.>

### Layer 4 — Formal Governing Mathematics & Complete Formula Anatomy
*(If purely non-mathematical, state "No formal equations govern this mechanism" and give complexity/invariant bounds.)*

$$
<Display LaTeX Equation>
$$

| Symbol / Operator | Name & Physical Role | Tensor Shape / Domain / Units | Directional Sensitivity |
|---|---|---|---|
| $x$ | <Name & role> | <Shape / domain / units> | <Effect when $x$ increases/decreases> |

- **Directional Sensitivity & Boundary Limits:** Input $\to 0$: <behavior> | $\to 1$/$-1$: <behavior> | Negative/degenerate: <behavior> | $\to \infty$: <behavior>.

<!-- SECTION: L4-DERIVATION-AND-CODE -->
## 4. Step-by-Step Axiom Derivation
1. **Step 1 (Axiom):** $$<Start>$$ — *Why:* <1-sentence justification>.
2. **Step 2 (Transition):** $$<Mid>$$ — *Why:* <1-sentence justification>.
3. **Step 3 (Final):** $$<Target>$$ — *Why:* <1-sentence justification>.

## 5. Executable "Code-as-Truth" Verification Block
```python
import numpy as np
# 10-18 line self-contained verification matching worked example
x = np.array([2.0, 3.0], dtype=float)
assert np.allclose(actual, expected), f"Invariant failed: {actual} != {expected}"
```

<!-- SECTION: L5-WORKBOOK-AND-GRAPH -->
## 6. Gradual-Release Practice Workbook (`I Do` → `We Do` → `You Do`)

### `I Do` (Fully Worked 3-Number Trace)
1. **Inputs:** <3 numbers matching Code-as-Truth> | 2. **Arithmetic:** <Zero skipped steps> | 3. **Result:** <Value + meaning>.

### `We Do` (Faded Fill-in-the-Blank)
<Second problem with 60% shown and `[Step 2: ___]`, `[Step 4: ___]` missing.>
<details><summary>Reveal Step-by-Step Solution</summary>
<Exact missing steps + final answer.>
</details>

### `You Do` (Cold Solo + Adversarial Edge-Case Drill)
<Boundary-breaking problem with zero scaffolding.>
<details><summary>Reveal Step-by-Step Solution</summary>
<Verified solution + boundary analysis + 2-sentence Feynman check.>
</details>

## 7. Typed Knowledge Graph Footer & 4-Checkpoint Mastery Ledger

### Typed Semantic Links
- **Depends On:** [[topics/<prev>-<slug>]] | **Unlocks:** [[topics/<next>-<slug>]] | **Contrasts With:** [[topics/<lookalike>-<slug>]] | **Fixes Failure Of:** [[topics/<broken>-<slug>]] | **Atomic:** [[atomic/<concept>]]

### 4-Checkpoint Mastery Ledger
- [ ] `[1/4]` Discovery Prediction
- [ ] `[2/4]` We-Do Faded Step
- [ ] `[3/4]` You-Do Cold Drill
- [ ] `[4/4]` Edge-Case & Feynman Gate

---
**Navigation:** ← [[<prev-subtopic>|Previous]] | [[03-CORNELL-STUDY-GUIDE|Study Guide]] | [[<next-subtopic>|Next]] →
````

---

## 3. Mandatory 7-Point Writer -> Critic Audit (Before Saving Any `topics/*.md`)
1. Every Layer 4 symbol is defined in Block 2 or the Symbol Table.
2. Zero skipped algebraic steps in Block 4.
3. Zero backtick-wrapped LaTeX (`$`/`$$`) and `\mid` used instead of `|` inside every table.
4. Includes ASCII diagram, Contrastive "Is vs. Is Not" table, and `> [!warning] Where the Analogy Breaks Down`.
5. Includes runnable 10–18 line Python/NumPy `assert` snippet in Block 5.
6. All typed links (`depends_on`, `unlocks`, `contrasts_with`, `fixes_failure_of`, Block 7) resolve to existing vault files (or `[]`).
7. **Strict YAML Frontmatter:** Double-quote `"..."` all `description`, `title`, `checkpoint`, `key_equations`, and string values with `:`, `|`, `[`, `]`, `{`, `}`, `<`, `>`, `*`, `&`, `#`, `?`, or `\`.
