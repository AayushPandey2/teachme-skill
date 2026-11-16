# Subcommand Router Reference: Lifecycle, Ingestion, Retention, Synthesis & Vault Configuration

When invoked with a subcommand (via `/teachme-<subcommand>` or `/teachme <subcommand>`), execute its dedicated workflow directly without rebuilding the entire vault from scratch. Always resolve `<VAULT_ROOT>` dynamically by reading `~/.teachme-config.json` (`notes_root`, defaulting to `~/notes` if absent/unset)—never hardcode `<VAULT_ROOT>/`. All outputs remain 100% pure Markdown inside `<VAULT_ROOT>/` and strictly enforce **Zero Black-Box Formulas** (Mandatory Formula Anatomy Breakdown), **8-Block Subtopic Notes**, and **Anti-Spoiler Progressive Mastery**.

---

## A. Ingestion & Source-Driven Commands

### 1. `/teachme ingest <path-or-url> into <topic>` (Source Ingestion & Merge)

1. **Read Existing Vault First:** Load `00-MOC-INDEX.md`, `01-RESOURCES.md`, `02-DEEP-RESEARCH.md`, and `04-GLOSSARY.md` inside `<VAULT_ROOT>/<topic-slug>/`. If the vault does not exist yet, initialize it first (using Phase 1 defaults if `--auto` or after a quick Mission Lock).
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

1. **Read Full Vault:** Scan `00-MOC-INDEX.md`, `02-DEEP-RESEARCH.md`, `03-CORNELL-STUDY-GUIDE.md`, `04-GLOSSARY.md`, `05-MENTAL-MODELS.md`, and `topics/*.md` inside `<VAULT_ROOT>/<topic-slug>/`.
2. **Generate `<VAULT_ROOT>/<topic-slug>/09-CHEAT-SHEET.md`:** Compress the entire topic into a high-density, single-page last-minute review sheet containing ONLY these 4 sections:

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

3. **Link in MOC:** Ensure `[[09-CHEAT-SHEET]]` is linked in the Vault Navigation header of `<VAULT_ROOT>/<topic-slug>/00-MOC-INDEX.md`.

---

## B. Retention & Active-Recall Commands

### 3. `/teachme review <topic>` (Spaced-Repetition Quiz)

1. **Hot-State & Progressive Scan (Read-Only on Notes):** Read `00-SESSION-STATE.md` (<60 lines) FIRST instead of scanning the entire vault, then inspect `00-MOC-INDEX.md` and `learning-records/` for unchecked `- [ ]` subtopics or past misconceptions. Load ONLY `L0 + L1` (`<!-- SECTION: L1-ANCHOR -->`) for prerequisite subtopics and full `L2` content only for the subtopic under review. Do NOT regenerate or overwrite existing vault notes.
2. **Teach-Before-Test & ZPD Quiz:** Briefly recap the weakest or next unchecked subtopic in topological order—including plain-English intuition and a full component breakdown of any formulas involved—then run a targeted spaced-repetition Socratic quiz **one question at a time** (respecting the Strict Anti-Spoiler drop-down micro-step rule and Beginner-Safe scalar traces for `0 knowledge` / `Beginner` baselines).
3. **Persist Progress:** Check off mastered subtopics (`- [x]`) in `00-MOC-INDEX.md`, update `00-SESSION-STATE.md`, and log breakthroughs or corrected gaps in `learning-records/000N-<slug>.md`.

---

### 4. `/teachme feynman <topic> [subtopic]` (Reverse-Teaching Audit)

1. **Role Reversal:** Pick the specified `[subtopic]` (or the next unchecked subtopic in `00-MOC-INDEX.md`) and prompt the user to explain the concept—and its core formula(s)—from scratch in plain English as if teaching a complete beginner.
2. **Strict 4-Axis Grading Rubric:** Wait for the user's explanation, then evaluate it across:
   1. **Plain-English Clarity:** Did they explain without hiding behind unstated jargon instead of `04-GLOSSARY.md` definitions?
   2. **First-Principles Accuracy:** Are the causal steps and invariants sound?
   3. **Formula Intuition:** Did they accurately explain what each variable, subscript, and operator does?
   4. **Edge-Case Awareness:** Did they note where the intuition or analogy breaks down?
3. **Patch & Record:** Point out exact gaps gently, provide a refined model explanation if needed, save the session outcome to `<VAULT_ROOT>/<topic-slug>/learning-records/000N-feynman-<slug>.md`, and check off `- [x]` in `00-MOC-INDEX.md` if passed.

---

### 5. `/teachme drill <topic> [--tier 1|2|3]` (Problem Generator & Grader)

1. **Read Existing Problems:** Check `<VAULT_ROOT>/<topic-slug>/07-PRACTICE-PROBLEMS.md` (if it exists) so no duplicate problems are generated.
2. **Generate Fresh Problems:** Create 1–3 new quantitative or diagnostic problems calibrated to the requested tier (defaulting to the user's current ZPD tier if `--tier` is omitted):
   - **Tier 1:** Direct formula substitution & symbol sensitivity.
   - **Tier 2:** Multi-step derivation or cross-subtopic synthesis.
   - **Tier 3:** Adversarial edge cases, failure diagnosis, and boundary limits ($\to 0$, $\to \infty$).
3. **Interactive Grading & Persistence:** Present **one problem at a time** in chat, grade the user's step-by-step math and reasoning, and append all newly solved problems with full step-by-step solutions into `<VAULT_ROOT>/<topic-slug>/07-PRACTICE-PROBLEMS.md`:

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

1. **Cross-Vault & Primary-Source Lookup:** Check if `<VAULT_ROOT>/<topic-a-slug>/` and `<VAULT_ROOT>/<topic-b-slug>/` already exist in the central vault. For whichever vault is missing, run targeted primary-source research (Phase 2) first so all claims are grounded.
2. **Generate `<VAULT_ROOT>/comparisons/<topic-a-slug>-vs-<topic-b-slug>.md`:**

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

Upgrade an existing vault at `<VAULT_ROOT>/<topic-slug>/` from surface-level or incomplete coverage to exhaustive, zero-omission mastery without deleting existing progress or learning records:

1. **Scan Existing Vault:** Read `00-SESSION-STATE.md` (create it under 60 lines if missing, alongside `scratchpad/`), `00-MISSION.md`, `00-MOC-INDEX.md`, `01-RESOURCES.md`, `02-DEEP-RESEARCH.md`, `04-GLOSSARY.md`, `06-DERIVATIONS-AND-PROOFS.md`, and all existing files in `topics/*.md` and `atomic/*.md`.
2. **Gap & 8-Block Depth Audit:**
   - Identify **missing related topics, prerequisite foundations, advanced extensions, edge cases, and subtopics** not yet present in `topics/`.
   - Identify **existing `topics/*.md` or research files that are too brief** or missing any part of the **8-Block Subtopic Note Standard** (`references/STUDY-AND-GLOSSARY.md` §6): typed YAML frontmatter (`L0`), HTML semantic anchors (`<!-- SECTION: L1-ANCHOR -->` through `<!-- SECTION: L5-WORKBOOK-AND-GRAPH -->`), Zero-Baseline Micro-Bridge & Engineering Motivation, 4-Layer Deep Theory Stack (with ASCII diagram, Contrastive "Is vs. Is Not" table, Analogy Break-Down warning, Symbol Anatomy & Boundary Limits), zero-skip Axiom Derivation, 10–18 line Python/NumPy `assert` verification snippet, Gradual-Release Workbook (`I Do` → `We Do` → `You Do`), and Typed Knowledge Graph Footer + 4-checkpoint ledger.
3. **Deepen Pre-Existing Files In Place (With 6-Point Audit):**
   - Upgrade every shallow `topics/<nn>-<subtopic-slug>.md` file to full **8-Block Standard** compliance, and partition `atomic/*.md` cards with `L1-ANCHOR`..`L5-WORKBOOK-AND-GRAPH` markers.
   - Run the **Mandatory 6-Point Writer -> Critic Audit** (`references/STUDY-AND-GLOSSARY.md` §6) before saving every deepened file.
   - Update `02-DEEP-RESEARCH.md`, `03-CORNELL-STUDY-GUIDE.md`, `04-GLOSSARY.md` (1–2 sentence definitions + `_Avoid_:` aliases), and `06-DERIVATIONS-AND-PROOFS.md` with the newly added depth.
4. **Generate All Missing Related Subtopic Files:**
   - Create dedicated **8-Block Standard** `topics/<nn>-<new-subtopic-slug>.md` files (each passing the **6-Point Writer -> Critic Audit**) and corresponding `atomic/<concept-slug>.md` Zettelkasten cards for every missing related subtopic discovered.
5. **Update Navigation & Graphs:**
   - Register all newly created `topics/*.md` and `atomic/*.md` files in `00-MOC-INDEX.md` (with status checkboxes `[ ]`, difficulty tags, and updated **Mermaid + ASCII prerequisite dependency graphs**) and update `00-SESSION-STATE.md` (`< 60` lines) while preserving existing `[x]` checkmarks on previously mastered subtopics.
6. **Report Expansion Summary:** Print a concise summary in chat listing which pre-existing files were deepened and which new subtopic files were added.

---

### 8. `/teachme verify <topic>` *(alias: `/teachme audit <topic>`)* (Vault Integrity & Auto-Repair)

Run an exhaustive, multi-pass structural, mathematical, and link-integrity scan and auto-repair loop across **every `.md` file** inside `<VAULT_ROOT>/<topic-slug>/` until **zero** broken links, **zero** broken formulas, and **100% 8-Block Standard compliance** are confirmed:

1. **Pass 1 — Exhaustive Link, Typed Edge & Topology Audit + Auto-Repair:**
   - Scan **every `.md` file** in `<VAULT_ROOT>/<topic-slug>/` (root files, `topics/*.md`, `atomic/*.md`, `learning-records/*.md`) for:
     - Obsidian wikilinks: `[[target]]`, `[[target|alias]]`, and heading/block links `[[target#Section]]`.
     - YAML typed semantic edges (`depends_on`, `unlocks`, `contrasts_with`, `fixes_failure_of`) and Block 7 semantic links in `topics/*.md`.
     - Standard relative Markdown links: `[label](relative/path.md)`.
     - Mermaid graph nodes and navigation footers (`Previous:`, `Next:`, `Index:`).
     - Presence and `< 60`-line compliance of `00-SESSION-STATE.md`, presence of `scratchpad/`, and `<!-- SECTION: L1-ANCHOR -->`..`<!-- SECTION: L5-WORKBOOK-AND-GRAPH -->` markers in every `topics/*.md` and `atomic/*.md` file.
   - **Auto-Fix Actions:**
     - Strip stray `.md` extensions inside `[[wikilinks]]` if inconsistent, resolve case/slug mismatches to the real file on disk, repair broken `depends_on` / `unlocks` / `contrasts_with` / `fixes_failure_of` typed edges and `Previous:` / `Next:` neighbor chains, and validate `#Section` anchor headings against actual headings in the target file.
     - Remove placeholder `[[none]]` frontmatter links (use `[]`). If a link points to a missing subtopic or concept file that *should* exist, generate that missing `.md` file immediately following the 8-Block Standard rather than leaving a dead link; if it is an invalid/typo link with no valid target, clean or remap it.
     - Detect any orphaned `.md` files in `topics/` or `atomic/` not listed in `00-MOC-INDEX.md` or `03-CORNELL-STUDY-GUIDE.md` and register them into the checklists, `00-SESSION-STATE.md` compact map, and Mermaid/ASCII dependency graphs.

2. **Pass 2 — Exhaustive LaTeX Hygiene & Mandatory 6-Point Writer -> Critic Audit + Auto-Repair:**
   - Scan **every `.md` file** in `<VAULT_ROOT>/<topic-slug>/` for:
     - **Backtick-wrapped LaTeX:** Any `$` or `$$` math wrapped inside code backticks → strip outer backticks immediately so it becomes pure `$` / `$$` math.
     - **Table-breaking pipes in math:** Any `$... | ...$` inside Markdown table rows `| ... |` → replace raw `|` with `\mid` or `\lvert` / `\rvert` (or `\lVert` / `\rVert`).
     - **Unclosed or mismatched delimiters:** Odd numbers of `$` on a line, unclosed `$$` blocks, stray currency `$` colliding with math, unescaped newlines inside single-line inline math, or broken braces `{` / `}`.
     - **Double-escaped or malformed commands:** Fix broken commands like `\\mathbf` where single `\mathbf` is needed, or missing backslashes on standard operators (`frac`, `sum`, `mathbf`, `partial`, `nabla`).
     - **Missing Formula Anatomy Breakdowns & 8-Block Standard Violations:** Run all **6 Writer -> Critic Audit** checks on every `topics/*.md` file (every Layer 4 symbol defined in Block 2 or Symbol Table; zero skipped algebraic steps in Block 4; zero backtick-wrapped math & `\mid` in tables; ASCII diagram + Contrastive "Is vs. Is Not" table + "Where the Analogy Breaks Down" warning present; runnable 10–18 line Python/NumPy `assert` verification snippet in Block 5; valid typed links), plus check `02-DEEP-RESEARCH.md` & `03-CORNELL-STUDY-GUIDE.md` for complete Formula Anatomy Breakdowns. Generate and insert any missing block in place.

3. **Pass 3 — Mandatory Re-Verification Loop (Zero-Remaining Guarantee) & Cross-File Glossary Check:**
   - Ensure canonical terms used across `topics/*.md` and `atomic/*.md` match `04-GLOSSARY.md` (adding any undefined domain terms to `04-GLOSSARY.md`).
   - After applying all file edits, **re-run** the link scanner, typed-edge check, 6-Point Writer -> Critic Audit, and LaTeX regex/delimiter check across the entire `<VAULT_ROOT>/<topic-slug>/` directory to confirm **0 broken links**, **0 broken formulas**, and **0 missing 8-Block sections** remain before finishing.
   - Output a clear verification report table in chat:

```markdown
| File | Links Checked / Fixed | Formulas Checked / Fixed | 8-Block Audit | Status |
|---|---|---|---|---|
| `00-SESSION-STATE.md` | 1 / 0 | 0 / 0 | <60 lines | PASS |
| `00-MOC-INDEX.md` | 20 / 0 | 0 / 0 | — | PASS |
| `topics/01-...md` | 6 / 0 | 2 / 0 | 6/6 | PASS |
```

---

## D. Vault Configuration (`notes-path`)

### 9. `/teachme-notes-path [path|reset]` *(alias: `/teachme notes-path [path|reset]`)*

Manage the central `<VAULT_ROOT>` directory where all `/teachme` commands read and write topic vaults (`<VAULT_ROOT>/<topic-slug>/` and `<VAULT_ROOT>/comparisons/`).

**Vault Root Resolution Order (`<VAULT_ROOT>`):**
1. Check `~/.teachme-config.json` (`notes_root`) first.
2. If `~/.teachme-config.json` does not exist or `notes_root` is unset, default `<VAULT_ROOT>` to `~/notes`.

#### Mode A: `<path>` Provided (`/teachme-notes-path <path>` or `/teachme notes-path <path>`)
1. **Normalize & Expand Path:** Expand `~`, `$HOME`, `%USERPROFILE%`, or `$env:USERPROFILE`, resolve relative paths cleanly, and normalize slashes for the host OS (storing clean forward-slash or native normalized paths consistently in JSON).
2. **Create & Verify Write Access:** Create the directory if it does not exist (`mkdir -p` on POSIX / `New-Item -ItemType Directory -Force` on Windows) and verify write access inside it before saving configuration.
3. **Detect Existing Vaults & Ask Before Moving:** Check the previous `<OLD_VAULT_ROOT>` (if it existed and contains topic vault folders). If existing topic vaults are found, display both `<OLD_VAULT_ROOT>` and `<NEW_VAULT_ROOT>` and ask whether the user wants to copy/move existing topic vaults over or keep them separate (**never** move or delete existing vault files destructively without explicit confirmation).
4. **Save `~/.teachme-config.json`:** Write or update `~/.teachme-config.json`:
   ```json
   {
     "notes_root": "<normalized-path>",
     "updated_at": "<YYYY-MM-DD>"
   }
   ```
5. **Confirm:** Report the newly active `<VAULT_ROOT>` path clearly in chat.

#### Mode B: No Argument Provided (`/teachme-notes-path`)
1. Resolve `<VAULT_ROOT>` using `~/.teachme-config.json` (showing whether it is a **custom** `notes_root` or the **default** `~/notes`).
2. List all topic vaults currently stored inside `<VAULT_ROOT>` (along with `comparisons/` if present).

#### Mode C: `reset` Provided (`/teachme-notes-path reset`)
1. Update `~/.teachme-config.json` so `notes_root` is reset back to `~/notes` (with `updated_at: "<YYYY-MM-DD>"`).
2. Confirm in chat that `<VAULT_ROOT>` is now reset to the default `~/notes` (mentioning the previous custom path if one was set, without deleting any files there).
