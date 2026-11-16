# Subcommand Router Reference: Lifecycle, Ingestion, Retention & Synthesis Commands

When invoked with a subcommand, execute its dedicated workflow directly without rebuilding the entire vault from scratch. All outputs remain 100% pure Markdown inside `~/notes/` and strictly enforce **Zero Black-Box Formulas** (Mandatory Formula Anatomy Breakdown) and **Teach-Before-Test**.

---

## A. Ingestion & Source-Driven Commands

### 1. `/teachme ingest <path-or-url> into <topic>` (Source Ingestion & Merge)

1. **Read Existing Vault First:** Load `00-MOC-INDEX.md`, `01-RESOURCES.md`, `02-DEEP-RESEARCH.md`, and `04-GLOSSARY.md` inside `~/notes/<topic-slug>/`. If the vault does not exist yet, initialize it first (using Phase 1 defaults if `--auto` or after a quick Mission Lock).
2. **Extract & Verify:** Parse the provided local file (PDF, lecture notes, code, transcript) or URL (research paper, YouTube transcript, GitHub repository, official docs). Extract every new claim, mechanism, benchmark, and mathematical equation with inline `[Source]` citations.
3. **Apply Mandatory Formula Anatomy:** For every new formula extracted, generate the complete Formula Anatomy Breakdown (`$$...$$`, Plain-English Intuition, 4-column Component & Operator Breakdown Table, Boundary & Limiting Cases, and Worked Numerical Walkthrough).
4. **Update Vault Files:**
   - Add the source under `## Knowledge` or `## Wisdom` in `01-RESOURCES.md`.
   - Append synthesized findings to `02-DEEP-RESEARCH.md` and `03-CORNELL-STUDY-GUIDE.md`.
   - Generate new dedicated `topics/<nn>-<subtopic-slug>.md` files for any newly uncovered subtopics and register them in `00-MOC-INDEX.md` (updating both the Mermaid `graph TD` and ASCII dependency tree).
   - Add any new canonical terms to `04-GLOSSARY.md` (strictly 1–2 sentences stating what each term IS + `_Avoid_:` aliases).
5. **Contradiction Detection:** Explicitly flag any claims, benchmarks, or definitions in the ingested source that conflict with existing vault notes under a `## Contradictions & Version Deltas` alert block in `02-DEEP-RESEARCH.md` and report them in chat:

```markdown
## Contradictions & Version Deltas
> [!WARNING] Conflict Detected — [<Source Title>] vs. Existing Vault Notes
> - **Topic / Claim:** <Exact mechanism, benchmark, or definition>
> - **Existing Vault Claim:** <What the vault currently states> [Existing Source]
> - **Newly Ingested Claim:** <What the new source states> [New Source]
> - **Resolution / Context:** <Version difference, workload assumption, or unresolved open question>
```

---

### 2. `/teachme distill <topic>` (Executive Cheat Sheet)

1. **Read Full Vault:** Scan `00-MOC-INDEX.md`, `02-DEEP-RESEARCH.md`, `03-CORNELL-STUDY-GUIDE.md`, `04-GLOSSARY.md`, `05-MENTAL-MODELS.md`, and `topics/*.md` inside `~/notes/<topic-slug>/`.
2. **Generate `~/notes/<topic-slug>/09-CHEAT-SHEET.md`:** Compress the entire topic into a high-density, single-page last-minute review sheet containing ONLY these 4 sections:

```markdown
# Executive Cheat Sheet: <Topic Title>

- **Vault:** [[00-MOC-INDEX]] | **Study Guide:** [[03-CORNELL-STUDY-GUIDE]] | **Glossary:** [[04-GLOSSARY]]

## 1. Core Axioms & Invariants
1. **<Axiom / Invariant 1>:** <1-sentence non-negotiable truth>.
2. ... (5–8 total)

## 2. Critical Formula Reference Table
| Formula Name | Equation | Compact Symbol Key | Limiting Behavior |
|---|---|---|---|
| **<Name>** | $$...$$ | $x$: ...; $y$: ... | As $x \to 0$: ...; as $x \to \infty$: ... |

## 3. Decision & Trade-Off Matrix
| Scenario / Requirement | Choose `<Topic>` When... | Avoid `<Topic>` / Choose Alternative When... |
|---|---|---|
| **<Dimension 1>** | ... | ... |

## 4. Top Failure Modes & Gotchas
| Symptom | Root Cause | Immediate Fix / Invariant |
|---|---|---|
| **<Symptom 1>** | <Exact mechanism that broke> | <Preventive invariant or mitigation> |
```

3. **Link in MOC:** Ensure `[[09-CHEAT-SHEET]]` is linked in the Vault Navigation header of `~/notes/<topic-slug>/00-MOC-INDEX.md`.

---

## B. Retention & Active-Recall Commands

### 3. `/teachme review <topic>` (Spaced-Repetition Quiz)

1. **Scan State (Read-Only on Notes):** Read `00-MOC-INDEX.md` (looking for unchecked `- [ ]` subtopics), `learning-records/` (looking for past misconceptions or `superseded` records), and `08-FLASHCARDS.md`. Do NOT regenerate or overwrite existing vault notes.
2. **Teach-Before-Test & ZPD Quiz:** Briefly recap the weakest or next unchecked subtopic in topological order—including plain-English mechanics and a full component breakdown of any formulas involved—then run a targeted spaced-repetition Socratic quiz **one question at a time** (respecting Beginner-Safe 1-number scalar traces for `0 knowledge` / `Beginner` baselines).
3. **Persist Progress:** Check off mastered subtopics (`- [x]`) in `00-MOC-INDEX.md` and log breakthroughs or corrected gaps in `learning-records/000N-<slug>.md`.

---

### 4. `/teachme feynman <topic> [subtopic]` (Reverse-Teaching Audit)

1. **Role Reversal:** Pick the specified `[subtopic]` (or the next unchecked subtopic in `00-MOC-INDEX.md`) and prompt the user to explain the concept—and its core formula(s)—from scratch in plain English as if teaching a complete beginner.
2. **Strict 4-Axis Grading Rubric:** Wait for the user's explanation, then evaluate it across:
   1. **Plain-English Clarity:** Did they explain without hiding behind unstated jargon instead of `04-GLOSSARY.md` definitions?
   2. **First-Principles Accuracy:** Are the causal steps and invariants sound?
   3. **Formula Intuition:** Did they accurately explain what each variable, subscript, and operator does?
   4. **Edge-Case Awareness:** Did they note where the intuition or analogy breaks down?
3. **Patch & Record:** Point out exact gaps gently, provide a refined model explanation if needed, save the session outcome to `~/notes/<topic-slug>/learning-records/000N-feynman-<slug>.md`, and check off `- [x]` in `00-MOC-INDEX.md` if passed.

---

### 5. `/teachme drill <topic> [--tier 1|2|3]` (Problem Generator & Grader)

1. **Read Existing Problems:** Check `~/notes/<topic-slug>/07-PRACTICE-PROBLEMS.md` (if it exists) so no duplicate problems are generated.
2. **Generate Fresh Problems:** Create 1–3 new quantitative or diagnostic problems calibrated to the requested tier (defaulting to the user's current ZPD tier if `--tier` is omitted):
   - **Tier 1:** Direct formula substitution & symbol sensitivity.
   - **Tier 2:** Multi-step derivation or cross-subtopic synthesis.
   - **Tier 3:** Adversarial edge cases, failure diagnosis, and boundary limits ($\to 0$, $\to \infty$).
3. **Interactive Grading & Persistence:** Present **one problem at a time** in chat, grade the user's step-by-step math and reasoning, and append all newly solved problems with full step-by-step solutions into `~/notes/<topic-slug>/07-PRACTICE-PROBLEMS.md`:

```markdown
## Problem <N> [Tier <1|2|3>] — <Subtopic Title>
- **Prompt:** <Concrete quantitative or diagnostic problem statement>
- **Step-by-Step Solution:**
  1. <Formula / setup with variable values>
  2. <Intermediate calculation / reasoning>
  3. **Final Answer & Interpretation:** <Result + plain-English meaning>
```

---

## C. Synthesis & Applied Mastery Commands

### 6. `/teachme compare <topic-a> vs <topic-b>` (Cross-Vault Synthesis)

1. **Cross-Vault & Primary-Source Lookup:** Check if `~/notes/<topic-a-slug>/` and `~/notes/<topic-b-slug>/` already exist in the central vault. For whichever vault is missing, run targeted primary-source research (Phase 2) first so all claims are grounded.
2. **Generate `~/notes/comparisons/<topic-a-slug>-vs-<topic-b-slug>.md`:**

```markdown
# Comparison: <Topic A> vs. <Topic B>

- **Vault A:** [[../<topic-a-slug>/00-MOC-INDEX|<Topic A>]] | **Vault B:** [[../<topic-b-slug>/00-MOC-INDEX|<Topic B>]]

## 1. Executive Verdict & Selection Rule
- **Choose <Topic A> when:** <Concrete workload, scale, or invariant conditions>.
- **Choose <Topic B> when:** <Concrete workload, scale, or invariant conditions>.

## 2. Side-by-Side Architecture & Mechanics Matrix
| Dimension | <Topic A> | <Topic B> |
|---|---|---|
| **Core Mechanism** | ... [Source] | ... [Source] |
| **Time / Space / Network Complexity** | $$...$$ (with symbol key) | $$...$$ (with symbol key) |
| **Consistency / Guarantees** | ... | ... |
| **Operational Overhead** | ... | ... |
| **Primary Failure Modes** | ... | ... |

## 3. Mathematical & Quantitative Contrast
<Compare governing equations, bounds, or objective functions side-by-side with complete symbol keys and crossover points.>

## 4. Migration, Hybrid Patterns & Pitfalls
- **Migrating A → B / B → A:** <Key impedance mismatches and hidden costs>.
- **Hybrid Pattern:** <When and how they compose together>.
```

3. **Bidirectional Linking:** Add a `## Comparisons` section with `[[../comparisons/<topic-a-slug>-vs-<topic-b-slug>]]` inside both `00-MOC-INDEX.md` files (where those vaults exist).

---

### 7. `/teachme expand <topic>` (Vault Expansion & Deepening)

Upgrade an existing vault at `~/notes/<topic-slug>/` from surface-level or incomplete coverage to exhaustive, zero-omission mastery without deleting existing progress or learning records:

1. **Scan Existing Vault:** Read `00-MISSION.md`, `00-MOC-INDEX.md`, `01-RESOURCES.md`, `02-DEEP-RESEARCH.md`, `04-GLOSSARY.md`, `06-DERIVATIONS-AND-PROOFS.md`, and all existing files in `topics/*.md` and `atomic/*.md`.
2. **Gap & Depth Audit:**
   - Identify **missing related topics, prerequisite foundations, advanced extensions, edge cases, and subtopics** not yet present in `topics/`.
   - Identify **existing `topics/*.md` or research files that are too brief**, lack full step-by-step derivations, miss edge cases/worked examples, or lack complete component-by-component Formula Anatomy breakdowns.
3. **Deepen Pre-Existing Files In Place:**
   - Enrich every shallow `topics/<nn>-<subtopic-slug>.md` file with deeper mechanics, concrete worked numerical/code examples, adversarial edge cases, and complete Formula Anatomy breakdowns (symbol/operator tables, units/domain, directional sensitivity, boundary limits).
   - Update `02-DEEP-RESEARCH.md`, `03-CORNELL-STUDY-GUIDE.md`, `04-GLOSSARY.md` (1–2 sentence definitions + `_Avoid_:` aliases), and `06-DERIVATIONS-AND-PROOFS.md` with the newly added depth.
4. **Generate All Missing Related Subtopic Files:**
   - Create dedicated `topics/<nn>-<new-subtopic-slug>.md` files and corresponding `atomic/<concept-slug>.md` Zettelkasten cards for every missing related subtopic discovered.
5. **Update Navigation & Graphs:**
   - Register all newly created `topics/*.md` and `atomic/*.md` files in `00-MOC-INDEX.md` with status checkboxes (`[ ]`), difficulty tags, and updated **Mermaid + ASCII prerequisite dependency graphs** (preserving existing `[x]` checkmarks on previously mastered subtopics).
6. **Report Expansion Summary:** Print a concise summary in chat listing which pre-existing files were deepened and which new subtopic files were added.

---

### 8. `/teachme verify <topic>` *(alias: `/teachme audit <topic>`)* (Vault Integrity & Auto-Repair)

Run an exhaustive, multi-pass structural, mathematical, and link-integrity scan and auto-repair loop across **every `.md` file** inside `~/notes/<topic-slug>/` until **zero** broken links or broken formulas remain:

1. **Pass 1 — Exhaustive Link & Reference Audit + Auto-Repair:**
   - Scan **every `.md` file** in `~/notes/<topic-slug>/` (root files, `topics/*.md`, `atomic/*.md`, `learning-records/*.md`) for:
     - Obsidian wikilinks: `[[target]]`, `[[target|alias]]`, and heading/block links `[[target#Section]]`.
     - Standard relative Markdown links: `[label](relative/path.md)`.
     - Mermaid graph nodes and navigation footers (`Previous:`, `Next:`, `Index:`).
   - **Auto-Fix Actions:**
     - Strip stray `.md` extensions inside `[[wikilinks]]` if inconsistent, resolve case/slug mismatches to the real file on disk, fix broken `Previous:` / `Next:` neighbor chains in `topics/*.md`, and validate `#Section` anchor headings against actual headings in the target file.
     - Remove placeholder `[[none]]` frontmatter links (`prerequisites: []`). If a link points to a missing subtopic or concept file that *should* exist, generate that missing `.md` file immediately rather than leaving a dead link; if it is an invalid/typo link with no valid target, clean or remap it.
     - Detect any orphaned `.md` files in `topics/` or `atomic/` not listed in `00-MOC-INDEX.md` or `03-CORNELL-STUDY-GUIDE.md` and register them into the checklists and Mermaid/ASCII dependency graphs.

2. **Pass 2 — Exhaustive LaTeX Formula Syntax & Anatomy Audit + Auto-Repair:**
   - Scan **every `.md` file** in `~/notes/<topic-slug>/` for:
     - **Backtick-wrapped LaTeX:** Any `` `$...$` `` or `` `$$...$$` `` → strip the outer backticks immediately so it becomes pure `$...$` / `$$...$$`.
     - **Table-breaking pipes in math:** Any `$... | ...$` inside Markdown table rows `| ... |` → replace raw `|` with `\mid` or `\lvert` / `\rvert` (or `\lVert` / `\rVert`).
     - **Unclosed or mismatched delimiters:** Odd numbers of `$` on a line, unclosed `$$` blocks, stray currency `$` colliding with math, unescaped newlines inside single-line `$...$`, or broken braces `{` / `}`.
     - **Double-escaped or malformed commands:** Fix broken commands like `\\mathbf` where single `\mathbf` is needed, or missing backslashes on standard operators (`frac`, `sum`, `mathbf`, `partial`, `nabla`).
     - **Missing Formula Anatomy Breakdowns:** Any display equation `$$...$$` in `02-DEEP-RESEARCH.md`, `03-CORNELL-STUDY-GUIDE.md`, or `topics/*.md` lacking its Plain-English Intuition, complete symbol/operator breakdown table, units/domain, directional sensitivity, boundary limits, or worked numerical walkthrough → generate and insert the complete breakdown block in place.

3. **Pass 3 — Mandatory Re-Verification Loop (Zero-Remaining Guarantee) & Cross-File Glossary Check:**
   - Ensure canonical terms used across `topics/*.md` and `atomic/*.md` match `04-GLOSSARY.md` (adding any undefined domain terms to `04-GLOSSARY.md`).
   - After applying all file edits, **re-run** the link scanner and LaTeX regex/delimiter check across the entire `~/notes/<topic-slug>/` directory to confirm **0 broken links** and **0 broken formulas** remain before finishing.
   - Output a clear verification report table in chat:

```markdown
| File | Links Checked / Fixed | Formulas Checked / Fixed | Status |
|---|---|---|---|
| `00-MOC-INDEX.md` | 20 / 0 | 0 / 0 | PASS |
| `topics/01-...md` | 4 / 1 | 2 / 1 | PASS |
```
