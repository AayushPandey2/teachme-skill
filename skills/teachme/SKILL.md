---
name: teachme
description: "Unified end-to-end learning, deep primary-source research, frontier grilling, Socratic teaching, and structured Markdown note-taking pipeline. Invoke with /teachme <topic> or when the user asks to deeply research, learn, build a study guide, generate Cornell notes, create Zettelkasten cards, or master any topic from first principles into a central vault (<VAULT_ROOT>/<topic-slug>/, defaulting to ~/notes)."
---

# `/teachme` Master Router & Core Laws

This file is the **single source of truth** for vault location, formatting, linking, and CLI laws. Reference files never restate these laws; they cite `SKILL.md §A–§D`.

## §A. Vault Root Resolution
- `<VAULT_ROOT>` = `notes_root` in `~/.teachme-config.json`; fallback `~/notes`. Change it only via `/teachme-notes-path`.
- Write ONLY inside `<VAULT_ROOT>/<topic-slug>/` (comparisons: `<VAULT_ROOT>/comparisons/`). Never scatter notes in project folders.
- If `<topic>` is omitted, run `vault_cli.py state` (auto-selects the most recently active vault) or ask ONE clarifying question.

## §B. Non-Negotiable Formatting & Hygiene Laws (Every Vault `.md` File)
1. **Pure Markdown + Strict YAML:** Double-quote `title`, `description`, `checkpoint`, `key_equations` items, and any YAML string containing `: | [ ] { } < > * & # ? \`. Spaces (never tabs) for indentation.
2. **Math Delimiter Law (100% coverage):** Every math symbol, Greek letter, sub/superscripted variable, arrow, set operator, or LaTeX macro (`\theta \in \to \implies \iff \sum \hat \mathbf \le \ge \neq \approx \frac \sqrt \lVert \rVert \mathbb \text \operatorname`) anywhere in prose, lists, headings, tables, or `<details>` MUST sit inside `$...$` or `$$...$$`. Zero bare backslashes outside code fences/inline code.
3. **Math Hygiene:** Never wrap `$`/`$$` math in backticks. No space before a closing `$`. Keep inline math single-line and balanced. Inside tables use `\mid \lvert \rvert \lVert \rVert`, never a raw `|`.
4. **`<details>` Block Law:** `<details>` and `</details>` each stand alone at column 0 (never inline, never inside a `-`/`1.` list item). Required shape — blank line, `<details>`, `<summary>…</summary>`, blank line, body, blank line, `</details>`. Put the question in a `####` heading above the block.
5. **Zero Black-Box Formulas:** Every equation gets a Formula Anatomy Breakdown (`references/STUDY-AND-GLOSSARY.md §1`).
6. **Dual-Layer Deep-Linking:** Never cite bare `[Author, Year]` or a bare homepage. Inline format: `([Author, Year](<doi-or-exact-url>) · [[01-RESOURCES#<anchor>|Source]] · [[02-DEEP-RESEARCH#<anchor>|Research]])` (`references/RESEARCH-TOOLCHAIN.md §3`).
7. **Zero Dead Links:** Every `[[wikilink]]`, relative link, and typed YAML edge (`depends_on`, `unlocks`, `contrasts_with`, `fixes_failure_of` → `topic-<nn>` IDs) resolves to an existing vault file. Empty edge = `[]`, never `[[none]]`.
8. **Exhaustive Coverage:** One `topics/<nn>-<slug>.md` per syllabus subtopic (no caps, no merges) + `atomic/` cards.

## §C. CLI-First Execution Mandate (`scripts/vault_cli.py`, Python 3 stdlib)
Never hand-generate scaffolding or scan Markdown when a CLI call answers it. Resolve the script at `../teachme/scripts/vault_cli.py` or `~/.gemini/antigravity/skills/teachme/scripts/vault_cli.py`.

| Call | Use |
|---|---|
| `init <vault> --topic "<T>" --subtopics <file.json>` | Scaffold dirs, `00-SESSION-STATE.md`, `00-MOC-INDEX.md`, `00-GRAPH.json`, topic stubs |
| `context <vault> --topic <nn>` | **Default per-turn load:** state + node + stage slice + 1-hop `L0-L1` anchors in ONE call |
| `state` / `graph` / `slice <file> --section <S>` | Resume pointer / rebuild `00-GRAPH.json` / single section (`L0-L1`, `L1-ANCHOR`…`L5-WORKBOOK-AND-GRAPH`) |
| `tick <vault> --topic <nn> --cp <1-4> --status <pass\|retry>` | Log checkpoints to `scratchpad/events.jsonl` |
| `flush <vault> --topic <nn> --note "<invariant>"` | Persist mastery once on `[4/4]` |
| `fix <vault>` → `verify <vault>` | Auto-repair `<details>`/bare LaTeX, then audit until `errors: []` |

- **1-Hop Rule:** Load only the active topic's stage slice + `depends_on`/`contrasts_with` `L0-L1` anchors. Never load mastered nodes >1 hop away unless an interleaved warm-up needs them.
- **Exit Gate:** Every write-phase ends with `fix` → `verify` returning `errors: []`.

## §D. Routing (Load ONLY the Listed File)

| Trigger | Reference | Output |
|---|---|---|
| `/teachme <topic>` Phases 1–3 (grill, research, scaffold); skip grilling on `--auto`/`defaults`/`go` | `references/MISSION-AND-GRILL.md` (+ `RESEARCH-TOOLCHAIN.md` in Phase 2) | `00-MISSION.md`, `01-RESOURCES.md`, `02-DEEP-RESEARCH.md`, scaffold |
| Phases 4–5 (notes, glossary, models, Cornell, flashcards, atomic) | `references/STUDY-AND-GLOSSARY.md` | `topics/`, `03`–`09`, `atomic/` |
| Phase 6 live Socratic coaching | `references/RETENTION-AND-RECORDS.md` | `events.jsonl`, `learning-records/` |
| `/teachme-notes-path [path\|reset]` | `references/cmd-notes-path.md` | `~/.teachme-config.json` |
| `/teachme-expand <topic>` | `references/cmd-expand.md` | `topics/`, `atomic/` |
| `/teachme-verify <topic>` (alias `audit`) | `references/cmd-verify.md` | repaired vault |
| `/teachme-ingest <topic> <source>` | `references/cmd-ingest.md` | merged vault |
| `/teachme-distill <topic>` | `references/cmd-distill.md` | `09-CHEAT-SHEET.md`, `08-FLASHCARDS.md` |
| `/teachme-review <topic>` | `references/cmd-review.md` | coaching session |
| `/teachme-feynman <concept>` | `references/cmd-feynman.md` | `learning-records/` |
| `/teachme-drill <topic> [1\|2\|3]` | `references/cmd-drill.md` | `07-PRACTICE-PROBLEMS.md` |
| `/teachme-compare <A> vs <B>` | `references/cmd-compare.md` | `comparisons/<a-vs-b>.md` |

Space-separated aliases (`/teachme expand <topic>`) route identically.
