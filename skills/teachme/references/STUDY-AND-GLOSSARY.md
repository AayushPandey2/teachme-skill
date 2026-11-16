# Phases 4–5: Subtopic Blueprint, Supporting Vault Files & Critic Gate

Formatting, linking, and CLI laws live in `SKILL.md §B–§C` only. Templates below already comply; keep them compliant.

## §1. Formula Anatomy Breakdown (Every Equation, Every File)
1. **Zero-Baseline Micro-Bridge:** each new symbol gets 2–3 plain-English lines + a 2-number example before use.
2. **Intuition Before Symbols:** geometry, scaling, and direction in words first.
3. **Symbol & Operator Table:** every variable, sub/superscript, constant, operator — role, shape/domain/units, directional sensitivity.
4. **Zero-Skip `I Do` Trace + Limiting Cases:** numeric walkthrough with no skipped algebra; behavior at $0$, $1$, $-1$, $\infty$, and degenerate inputs.

## §2. 7-Section Subtopic Blueprint (`topics/<nn>-<slug>.md`)
`vault_cli.py init` writes the frontmatter + markers; fill every section. The 5 HTML markers power `vault_cli.py slice`/`context`. Exactly 7 numbered `##` headings, no duplicates.

````markdown
---
id: "topic-<nn>"
title: "<Subtopic Title>"
status: "unstarted"
checkpoint: "0/4"
depends_on: ["topic-<prev-nn>"]
unlocks: ["topic-<next-nn>"]
contrasts_with: []
fixes_failure_of: []
key_equations:
  - "<clean LaTeX equation>"
---

# <nn>. <Subtopic Title>

<!-- SECTION: L1-ANCHOR -->
## 1. The Core Idea (30-Second Anchor)
- **Core Thesis:** <2–3 sentences: problem solved, mechanism, unbreakable invariant.>
- **One-Line Mental Hook:** <Vivid recall hook.>

<!-- SECTION: L2-PREREQS-AND-MOTIVATION -->
## 2. Building Blocks & Why This Exists

> [!note] Zero-Baseline Prerequisites
> - **<Term> ($x_i$):** <2–3 plain lines + 2-number example.>

### Historical & Engineering Motivation
<3–4 sentences on what failed before, with a dual deep-link citation.>

<!-- SECTION: L3-FOUR-LAYER-THEORY -->
## 3. How It Works: Intuition to Formal Math

### Daily-Life Analogy
<Thorough zero-jargon physical/human analogy.>

### Step-by-Step Mechanism & Visuals
- **Causal Flow (Input → Transformation → Output):** <Walkthrough using **bold** glossary terms + citation.>

```text
<Mandatory ASCII geometry / pipeline / state diagram>
```

#### Contrastive "Is vs. Is Not" Table
| Dimension | <This Concept> (IS) | <Closest Lookalike> (IS NOT) |
|---|---|---|
| **Core Mechanism** | <Exact mechanism> | <How it differs/fails> |
| **Invariant** | <What strictly holds> | <Where it breaks> |
| **Failure Mode** | <Real edge behavior> | <Lookalike trap> |

> [!warning] Where the Analogy Breaks Down
> <Where the analogy diverges from the true mechanics.>

### Mathematical Intuition
<Geometric, scaling, directional & limiting behavior in words.>

### Formal Equation & Symbol Breakdown
*(If non-mathematical: state "No formal equations govern this mechanism" and give complexity/invariant bounds.)*

$$
<Display LaTeX Equation>
$$

| Symbol / Operator | Name & Role | Shape / Domain / Units | Directional Sensitivity |
|---|---|---|---|
| $x$ | <Role> | <Domain> | <Effect as $x$ grows/shrinks> |

#### Input-to-Output Behavior Table *(discrete states, gates, thresholds, vector ops)*
| Concrete Inputs | Intermediate Value | Output | Interpretation |
|---|---|---|---|
| $(0, 0)$ | $s = 0$ | $\hat{y} = 0$ | <Below threshold> |

- **Boundary Limits:** Input $\to 0$: <…> | $\to \pm 1$: <…> | degenerate: <…> | $\to \infty$: <…>.

<!-- SECTION: L4-DERIVATION-AND-CODE -->
## 4. Step-by-Step Proof (Zero Skips)
1. **Step 1 (Axiom):** $$<Start>$$ — *Why:* <justification>.
2. **Step 2 (Transition):** $$<Mid>$$ — *Why:* <justification>.
3. **Step 3 (Final):** $$<Target>$$ — *Why:* <justification>.

## 5. Run It Yourself (Python Verification)
```python
import numpy as np
# 10–18 self-contained lines reproducing the I Do trace
assert np.allclose(actual, expected), f"Invariant failed: {actual} != {expected}"
```

<!-- SECTION: L5-WORKBOOK-AND-GRAPH -->
## 6. Practice Workbook (I Do → We Do → You Do)

### I Do (Fully Worked 3-Number Trace)
1. **Inputs:** <Numbers matching Section 5> 2. **Arithmetic:** <Zero skipped steps> 3. **Result:** <Value + meaning>

### We Do (Faded Boundary Problem)
<A boundary/edge-case problem (not a copy of I Do) with ~60% shown and `[Step 2: ___]` blanks.>

<details>
<summary>Reveal Step-by-Step Solution</summary>

<Missing steps + final answer.>

</details>

### You Do (Two-Part Solo Mastery)

#### Drill A — Reverse-Engineering / Design
<Design parameters to satisfy a specification.>

<details>
<summary>Reveal Step-by-Step Solution</summary>

<Design derivation + verification.>

</details>

#### Drill B — Adversarial Edge Case / Impossibility
<Prove or test a boundary failure.>

<details>
<summary>Reveal Step-by-Step Solution</summary>

<Proof + 2-sentence Feynman check.>

</details>

## 7. Common Traps, Primary Sources & Mastery Graph

> [!caution] Common Misconceptions
> - **_Avoid_:** <Mistake> → **True Invariant:** <Correct behavior>.

**Bridge to Next Topic:** <2 sentences on the limitation motivating [[topics/<next-nn>-<next-slug>]].>

### Primary Sources & Deep Links
| Source | Direct External Deep Link | Vault Deep Link | Exact Claim Verified |
|---|---|---|---|
| <Author (Year) — Title> | [<Section>](https://<exact-url>) | [[01-RESOURCES#<anchor>]] · [[02-DEEP-RESEARCH#<anchor>]] | *<Claim or equation>* |

### Typed Knowledge Graph
- **Depends On:** [[topics/<prev-nn>-<slug>|<Title>]]
- **Unlocks:** [[topics/<next-nn>-<slug>|<Title>]]
- **Contrasts With:** [[topics/<nn>-<slug>|<Title>]]
- **Fixes Failure Of:** [[topics/<nn>-<slug>|<Title>]]
- **Atomic:** [[atomic/<concept-slug>|<Concept>]]

### 4-Checkpoint Mastery Ledger
- [ ] `[1/4]` Discovery Prediction
- [ ] `[2/4]` We-Do Faded Step
- [ ] `[3/4]` You-Do Cold Drill
- [ ] `[4/4]` Edge-Case & Feynman Gate

---
**Navigation:** ← [[topics/<prev>|Previous]] | [[03-CORNELL-STUDY-GUIDE|Study Guide]] | [[topics/<next>|Next]] →
````

## §3. 7-Point Critic Self-Audit Gate (Before Saving Any `topics/*.md`)
1. **Math:** every Section 3 symbol is defined in Section 2 or the Symbol Table, and `SKILL.md §B.2–3` holds.
2. **Structure:** all 5 section markers + sequential `## 1.`–`## 7.` headings.
3. **Proof:** Section 4 skips zero algebraic steps.
4. **Visuals:** ASCII diagram, "Is vs. Is Not" table, analogy-break warning, Input-to-Output table (where applicable).
5. **Practice:** runnable 10–18 line `assert` snippet; `We Do` + Drills A & B in `§B.4` `<details>` shape; Section 7 caution + Bridge.
6. **Links & YAML:** typed edges and Section 7 wikilinks resolve (`[]` if none); special-char YAML strings double-quoted.
7. **Provenance:** inline dual deep-links AND the `Primary Sources & Deep Links` table with `https://` + `[[01-RESOURCES#…]]` / `[[02-DEEP-RESEARCH#…]]` anchors.

## §4. Supporting Vault Files

### `04-GLOSSARY.md`
```markdown
# Canonical Glossary: <Topic Title>
- **<Term>:** <1–2 sentence definition of what it IS — never a tutorial.>
  _Avoid:_ <Overloaded synonym>.
```

### `05-MENTAL-MODELS.md`
````markdown
# Mental Models: <Topic Title>
## 1. Zero-Jargon Feynman Core
<2–3 paragraphs, one physical analogy, where it holds and breaks.>
## 2. First-Principles Axiom Stack
1. **Axiom 1 (<Truth>):** <Why true> 2. **Axiom 2 (<Necessity>):** <What it forces> 3. **Axiom 3 (<Consequence>):** <Resulting shape>
## 3. System Flow Diagram
```text
<ASCII component / data-flow / state diagram>
```
## 4. Adversarial Pre-Mortem
1. **<Failure Mode>:** *Trigger:* <condition> | *Blast Radius:* <impact> | *Defensive Invariant:* <mitigation>
````

### `06-DERIVATIONS-AND-PROOFS.md`
```markdown
# Derivations & Proofs: <Topic Title>
## 1. Derivation of <Formula>
$$
<Target>
$$
- **Starting Axioms:** <From 04/05> | **Cross-Refs:** [[topics/<nn>-<slug>]] · [[04-GLOSSARY#<term>]]
1. **Step 1:** $$<Start>$$ — *Why:* <justification>.
2. **Step 2 (Final):** $$<Target>$$ — *Why:* <justification>.
```

### `03-CORNELL-STUDY-GUIDE.md`
Link every topic file; Formula Anatomy for every equation.

````markdown
# Cornell Study Guide: <Topic Title>
- **Nav:** [[00-MOC-INDEX]] · [[04-GLOSSARY]] · [[05-MENTAL-MODELS]] · [[06-DERIVATIONS-AND-PROOFS]] · [[08-FLASHCARDS]]
- **Executive Thesis:** <2 sentences.>

## Complete Syllabus Index
1. [[topics/01-<slug>]] — <1-line summary>

## 1. <Milestone Title>
*Deep-dive:* [[topics/01-<slug>]]
<Explanation with **bold** glossary terms + citations.>

### Active-Recall Cues

#### Cue 1: <Diagnostic question?>

<details>
<summary>Reveal Answer</summary>

<Crisp answer.>

</details>

## Trade-Offs & Comparative Matrix
| Criterion | <Topic> | <Alt A> | <Alt B> |
|---|---|---|---|

## Cornell Summary Synthesis
1. **Core Problem** 2. **Mechanism** 3. **Invariant** 4. **Failure Mode** 5. **Decision Rule** — one sentence each.

## Living Session Notes & Insights
- *[<YYYY-MM-DD>]* <Insight.>
````

### `00-MOC-INDEX.md` & `00-SESSION-STATE.md`
- Both are scaffolded by `vault_cli.py init`; `00-SESSION-STATE.md` stays `<60` lines and is only mutated by `tick`/`flush`.
- Enrich the MOC with a Mermaid `graph TD` + ASCII prerequisite tree + difficulty tags, keep the `## Cumulative Synthesis Strips` section, and register every `atomic/` card under `## Atomic Zettelkasten Concept Index`.

### `08-FLASHCARDS.md`
```markdown
# Flashcards: <Topic Title>
#flashcards/<topic-slug>

## 1. Conceptual Cards
<Single-line question> :: <Exact answer>

<Multi-line question>
?
<Answer grounded in 04-GLOSSARY / 05-MENTAL-MODELS.>

## 2. Formula Cloze Cards
For <Formula> ($$<Equation>$$): ==$<symbol>$== is ==<role & units>==; as ==$<symbol>$== $\to \infty$, output ==<limit>==.
```

### `09-CHEAT-SHEET.md` (4 Sections Only)
1. `## 1. Core Axioms & Invariants` — 5–8 one-sentence truths.
2. `## 2. Critical Formula Reference Table` — `Formula | Equation | Symbol Key | Limiting Behavior`.
3. `## 3. Decision & Trade-Off Matrix` — `Scenario | Choose <Topic> When | Avoid / Alternative When`.
4. `## 4. Top Failure Modes & Gotchas` — `Symptom | Root Cause | Fix / Invariant`.

### `atomic/<concept-slug>.md` (Phase 5, 150–300 words)
```markdown
---
tags:
  - "<topic-slug>"
  - "evergreen"
created: "<YYYY-MM-DD>"
status: "evergreen"
parent: "[[03-CORNELL-STUDY-GUIDE]]"
---

# <Atomic Concept>

<!-- SECTION: L1-ANCHOR -->
<2-sentence thesis + 1-line hook.>

<!-- SECTION: L2-PREREQS-AND-MOTIVATION -->
<Prerequisites and why the concept exists.>

<!-- SECTION: L3-FOUR-LAYER-THEORY -->
<Mechanism + citation + boundary condition.>

<!-- SECTION: L4-DERIVATION-AND-CODE -->
<Concrete example, invariant check, or equation.>

<!-- SECTION: L5-WORKBOOK-AND-GRAPH -->
## Related Concepts
- [[<sibling>]] — <How connected>
```

## §5. Phase 4–5 Exit
Write topics in syllabus order → `03`–`06`, `08` → `atomic/` → `vault_cli.py graph`, `fix`, `verify` until `errors: []` → hand off to Phase 6 (`RETENTION-AND-RECORDS.md`).
