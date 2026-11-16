# Phases 4 & 5 Reference: Cornell Guide, Session State, MOC Index, Flashcards & Zettelkasten

---

## 1. Phase 4A: Master Cornell Study Guide (`03-CORNELL-STUDY-GUIDE.md`)

Link **every** `[[topics/<nn>-<subtopic-slug>]]` file, include Formula Anatomy Breakdowns for any equation, `<details>` active-recall cues, trade-off matrix, 5-bullet synthesis summary, and `## Living Session Notes & Insights`:

````markdown
# Cornell Study Guide: <Topic Title>

- **Date:** <YYYY-MM-DD> | **MOC:** [[00-MOC-INDEX]] | **Glossary:** [[04-GLOSSARY]] | **Models:** [[05-MENTAL-MODELS]] | **Derivations:** [[06-DERIVATIONS-AND-PROOFS]] | **Flashcards:** [[08-FLASHCARDS]]
- **Executive Thesis:** <2-sentence core mechanism + why it matters.>

## Complete Syllabus Index
1. [[topics/01-<subtopic-slug>]] — <1-line summary>

## 1. <Milestone Title>
*Deep-dive:* [[topics/01-<subtopic-slug>]]
<Structured explanation using **bold** `04-GLOSSARY.md` terms + [Source] citations + Formula Anatomy.>

### Active-Recall Cue Questions
#### Cue 1: <Diagnostic/mechanism question?>

<details>
<summary>Reveal Answer</summary>

<Crisp answer with all math wrapped in `$...$`.>

</details>

## Trade-Offs & Comparative Matrix
| Criterion | <Topic> | <Alt A> | <Alt B> |
|---|---|---|---|
| **Mechanism / Failure Mode** | ... | ... | ... |

## Cornell Summary Synthesis
1. **Core Problem:** <1-sentence> | 2. **Mechanism:** <1-sentence> | 3. **Invariant:** <1-sentence> | 4. **Failure Mode:** <1-sentence> | 5. **Decision Rule:** <When to choose>.

## Living Session Notes & Insights
- *[<YYYY-MM-DD>]* <Initial vault synthesis completed.>
````

---

## 2. Phase 4C: Session State (`00-SESSION-STATE.md`), MOC (`00-MOC-INDEX.md`) & `scratchpad/`

Use `scripts/vault_cli.py init <VAULT_PATH> --title "<Topic Title>" --topics <01-slug,02-slug,...>` to scaffold `00-SESSION-STATE.md` (<60 lines), `00-MOC-INDEX.md`, `00-GRAPH.json`, and `scratchpad/` in 0 LLM tokens, then enrich `00-MOC-INDEX.md` with Mermaid `graph TD` + ASCII dependency tree + difficulty/prereq tags.
- **Auto-Compaction (Every 3 Completed Subtopics):** Append a 5-line **Cumulative Synthesis Strip** to `00-MOC-INDEX.md` and roll up verified formulas into `09-CHEAT-SHEET.md`.
- **Working Buffer:** Store rough drafts in `scratchpad/raw-research.md` and `scratchpad/derivation-drafts.md`.

---

## 3. Phase 4D: Spaced-Repetition Deck (`08-FLASHCARDS.md`)

Enforce the **Global Math Delimiter Law** (`100%` `$...$` / `$$...$$` coverage—never leave bare `\theta`, `\in`, `\to`, etc. on card fronts or backs) and the **Global `<details>` HTML Block Law** (if any card uses `<details>`, place it at column 0 with blank lines before `<details>`, after `</summary>`, and before `</details>`).

```markdown
# Spaced-Repetition Flashcards: <Topic Title>

#flashcards/<topic-slug>

## 1. Conceptual & Mechanism Cards
<Single-line question> :: <Exact answer>

<Multi-line question>
?
<Structured answer grounded in 04-GLOSSARY.md & 05-MENTAL-MODELS.md.>

## 2. Formula & Symbol Cloze Cards
For `<Formula>` ($$<Equation>$$): ==$<symbol>$== is ==<role & units>==; as ==$<symbol>$== $\to \infty$, output ==<limit>==.
```

---

## 4. Phase 5: Atomic Zettelkasten Cards (`atomic/<concept-slug>.md`)

150–300 words per key mechanism/theorem/invariant, partitioned with strict `L1`–`L5` HTML anchors:

```markdown
---
tags:
  - "<topic-slug>"
  - "evergreen"
created: "<YYYY-MM-DD>"
status: "evergreen"
parent: "[[03-CORNELL-STUDY-GUIDE]]"
---

# <Atomic Concept Title>

<!-- SECTION: L1-ANCHOR -->
<2-sentence core thesis + 1-line mental hook.>

<!-- SECTION: L2-PREREQS-AND-MOTIVATION -->
<1–2 sentence prerequisites and why concept exists.>

<!-- SECTION: L3-FOUR-LAYER-THEORY -->
<Mechanism grounded in 04-GLOSSARY.md + [Source] + boundary condition.>

<!-- SECTION: L4-DERIVATION-AND-CODE -->
<Concrete example, invariant check, or equation.>

<!-- SECTION: L5-WORKBOOK-AND-GRAPH -->
## Related Concepts
- [[<sibling-1>]] — <How/why connected>
```
