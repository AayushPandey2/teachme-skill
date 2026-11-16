# Phase 4B & Formula Reference: Formula Anatomy, 7-Section Subtopic Notes & 8-Point Critic Audit

---

## 1. Mandatory Formula Anatomy Breakdown & LaTeX Hygiene

Across `02-DEEP-RESEARCH.md`, `03-CORNELL-STUDY-GUIDE.md`, and every `topics/<nn>-<subtopic-slug>.md`, **every** formula/recurrence/bound MUST include:
1. **Zero-Baseline Micro-Bridge** for any new symbol (2–3 plain-English lines + 2-number example).
2. **Mathematical Intuition (Before Symbols)** explaining geometry/scaling before formal notation.
3. **Consistent `$inline$` & `$$display$$` LaTeX Hygiene:**
   - Wrap **EVERY** mathematical variable, operator, or expression in prose, tables, and `<details>` blocks in `$...$` (e.g., `$x_i \in \{0, 1\}$`, `$\theta$`, `$\hat{y}$`).
   - **Zero** bare LaTeX commands (`\theta`, `\sum`, `\hat`, `\mathbf`, etc.) outside `$...$`/`$$...$$`.
   - **Zero** spaces before a closing `$` (never `= $`), **zero** backticks around `$`/`$$`, and always `\mid`/`\lvert`/`\rvert` instead of raw `|` inside Markdown tables.
4. **Symbol & Operator Table** covering every variable, subscript, superscript, constant, and operator.
5. **Zero-Skip `I Do` Trace** + **Limiting Cases** (`$0$`, `$1$`, `$-1$`, `$\infty$`, degenerate).

---

## 2. Dual-Layer Primary-Source Deep-Linking Standard

Never write bare `[Author, Year]` text citations or link to a bare domain homepage.
- **Inline Deep-Link Citation Format:** Wherever a theorem, historical motivation, benchmark, or formula is introduced, cite as:
  `([Author, Year](<direct-doi-or-url>) · [[01-RESOURCES#<source-anchor>|Source]] · [[02-DEEP-RESEARCH#<section-anchor>|Research]])`
  Always link to the exact paper DOI/arXiv URL, RFC `#section-X`, or official documentation anchor.

---

## 3. Learner-Centric 7-Section Subtopic Blueprint (`topics/<nn>-<subtopic-slug>.md`)

Partition every `topics/*.md` file with the 5 invisible HTML markers (`L1-ANCHOR`..`L5-WORKBOOK-AND-GRAPH`) for `vault_cli.py slice`, using these exact **7 learner-centric headings (`1.` through `7.`, zero duplicate numbers)**:

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
## 1. The Core Idea (30-Second Anchor)
- **Core Thesis:** <2–3 sentences: problem solved, mechanism, unbreakable invariant.>
- **One-Line Mental Hook:** <1-sentence vivid recall hook.>

<!-- SECTION: L2-PREREQS-AND-MOTIVATION -->
## 2. Building Blocks & Why This Exists

> [!note] Zero-Baseline Prerequisites
> Define every new symbol/operator/term from scratch before use (wrapping all math in `$...$`):
> - **<Term 1> (`$x_i$`):** <2–3 plain-English lines + 2-number example.>

### Historical & Engineering Motivation
<3–4 sentences on what failed or scaled poorly previously ([Author, Year](<direct-doi-or-url>) · [[01-RESOURCES#<source-anchor>|Source]] · [[02-DEEP-RESEARCH#<section-anchor>|Research]]).>

<!-- SECTION: L3-FOUR-LAYER-THEORY -->
## 3. How It Works: Intuition to Formal Math

### Daily-Life Analogy
<Thorough physical/human analogy with zero jargon.>

### Step-by-Step Mechanism & Visuals
- **Causal Flow (`Input → Transformation → Output`):** <Step-by-step walkthrough using **bolded** `04-GLOSSARY.md` terms ([Author, Year](<direct-doi-or-url>) · [[01-RESOURCES#<source-anchor>|Source]] · [[02-DEEP-RESEARCH#<section-anchor>|Research]]).>

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
> <Where the everyday analogy diverges from true mechanics.>

### Mathematical Intuition
<Plain-English geometric, scaling, directional & limiting behavior before formal symbols.>

### Formal Equation & Symbol Breakdown
*(If purely non-mathematical, state "No formal equations govern this mechanism" and give complexity/invariant bounds.)*

$$
<Display LaTeX Equation>
$$

| Symbol / Operator | Name & Physical Role | Tensor Shape / Domain / Units | Directional Sensitivity |
|---|---|---|---|
| $x$ | <Name & role> | <Shape / domain / units> | <Effect when $x$ increases/decreases> |

#### Input-to-Output Behavior Table *(Required for discrete states, logic gates, vector/matrix ops, or thresholds)*
| Concrete Inputs | Intermediate Value | Output | Interpretation |
|---|---|---|---|
| <e.g., $(0, 0)$> | <$s = 0$> | <$\hat{y} = 0$> | <Below threshold> |

- **Directional Sensitivity & Boundary Limits:** Input $\to 0$: <behavior> | $\to 1$/$-1$: <behavior> | Negative/degenerate: <behavior> | $\to \infty$: <behavior>.

<!-- SECTION: L4-DERIVATION-AND-CODE -->
## 4. Step-by-Step Proof (Zero Skips)
1. **Step 1 (Axiom):** $$<Start>$$ — *Why:* <1-sentence justification>.
2. **Step 2 (Transition):** $$<Mid>$$ — *Why:* <1-sentence justification>.
3. **Step 3 (Final):** $$<Target>$$ — *Why:* <1-sentence justification>.

## 5. Run It Yourself (Python Verification)
```python
import numpy as np
# 10-18 line self-contained verification matching worked example
x = np.array([2.0, 3.0], dtype=float)
assert np.allclose(actual, expected), f"Invariant failed: {actual} != {expected}"
```

<!-- SECTION: L5-WORKBOOK-AND-GRAPH -->
## 6. Practice Workbook (I Do → We Do → You Do)

### `I Do` (Fully Worked 3-Number Trace)
1. **Inputs:** <3 numbers matching Section 5> | 2. **Arithmetic:** <Zero skipped steps> | 3. **Result:** <Value + meaning>.

### `We Do` (Faded Multi-Step Boundary Problem)
<Second problem testing a boundary condition or edge-case interaction—NOT trivial arithmetic identical to `I Do`—with ~60% shown and `[Step 2: ___]`, `[Step 4: ___]` missing.>
<details><summary>Reveal Step-by-Step Solution</summary>
<Exact missing steps + final answer with clean `$...$` math.>
</details>

### `You Do` (Two-Part Solo Mastery)
- **Drill A — Reverse-Engineering / Design Problem:** <Design parameters/weights/thresholds to satisfy a specification.>
  <details><summary>Reveal Step-by-Step Solution</summary>
  <Complete design derivation + verification.>
  </details>
- **Drill B — Adversarial Edge-Case / Impossibility Proof:** <Prove or test a boundary failure / impossibility condition.>
  <details><summary>Reveal Step-by-Step Solution</summary>
  <Complete proof/analysis + 2-sentence Feynman check.>
  </details>

## 7. Common Traps, Primary Sources & Mastery Graph

> [!caution] Common Misconceptions
> - **_Avoid_:** <Mistake 1> → **True Invariant:** <Correct behavior in `$...$`>.
> - **_Avoid_:** <Mistake 2> → **True Invariant:** <Correct behavior in `$...$`>.

**Bridge to Next Topic:** <2 sentences explaining the exact limitation that motivates `[[topics/<next-nn>-<next-slug>]]`.>

### Primary Sources & Deep Links
| Source | Direct External Deep Link | Vault Deep Link | Exact Claim / Equation Verified |
|---|---|---|---|
| <Author (Year) — Title> | [<Paper / Docs Section>](https://...) | [[01-RESOURCES#<source-anchor>]] · [[02-DEEP-RESEARCH#<section-anchor>]] | *<Exact claim or equation>* |

### Typed Knowledge Graph
- **Depends On:** [[topics/<prev>-<slug>|<prev-nn>: <Prev Title>]]
- **Unlocks:** [[topics/<next>-<slug>|<next-nn>: <Next Title>]]
- **Contrasts With:** [[topics/<lookalike>-<slug>|<lookalike-nn>: <Title>]]
- **Fixes Failure Of:** [[topics/<broken>-<slug>|<broken-nn>: <Title>]]
- **Atomic:** [[atomic/<concept-slug>|<Concept Title>]]

### 4-Checkpoint Mastery Ledger
- [ ] `[1/4]` Discovery Prediction
- [ ] `[2/4]` We-Do Faded Step
- [ ] `[3/4]` You-Do Cold Drill
- [ ] `[4/4]` Edge-Case & Feynman Gate

---
**Navigation:** ← [[topics/<prev-subtopic>|Previous]] | [[03-CORNELL-STUDY-GUIDE|Study Guide]] | [[topics/<next-subtopic>|Next]] →
````

---

## 4. Mandatory 8-Point Writer -> Critic Audit (Before Saving Any `topics/*.md`)
1. Every Section 3 symbol is defined in Section 2 or the Symbol Table; zero bare `\theta`/`\sum`/etc. outside `$...$` and zero spaces before closing `$`.
2. Strict sequential `## 1.` through `## 7.` headings with zero duplicate numbers.
3. Zero skipped algebraic steps in Section 4 (`Step-by-Step Proof`).
4. Zero backtick-wrapped LaTeX (`$`/`$$`) and `\mid` used instead of `|` inside every table.
5. Includes ASCII diagram, Contrastive "Is vs. Is Not" table, `> [!warning] Where the Analogy Breaks Down`, Input-to-Output Behavior Table (where applicable), Section 6 `We Do` boundary + `You Do` Drills A & B, and Section 7 `> [!caution]` + Bridge.
6. Includes runnable 10–18 line Python/NumPy `assert` snippet in Section 5.
7. All typed links (`depends_on`, `unlocks`, `contrasts_with`, `fixes_failure_of`, Section 7 clickable `[[wikilinks]]`) resolve to existing vault files (`[]` if none), and YAML strings with special chars are double-quoted.
8. **Primary-Source Deep-Link Verification:** File contains inline dual deep-link citations AND a Section 7 `Primary Sources & Deep Links` table with clickable `https://` direct links + valid `[[01-RESOURCES#<anchor>]]` / `[[02-DEEP-RESEARCH#<anchor>]]` anchors.
