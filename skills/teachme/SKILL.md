---
name: teachme
description: "Unified end-to-end learning, deep primary-source research, frontier grilling, Socratic teaching, and structured Markdown note-taking pipeline. Invoke with /teachme <topic> or when the user asks to deeply research, learn, build a study guide, generate Cornell notes, create Zettelkasten cards, or master any topic from first principles into a central vault (<VAULT_ROOT>/<topic-slug>/, defaulting to ~/notes)."
---

# `/teachme` Master Router & Core Laws

This file is the **single source of truth** for vault location, formatting, linking, and CLI laws. Reference files never restate these laws; they cite `SKILL.md §A–§D`.

## §A. Vault Root & Operating Mode Resolution
TeachMe supports two compatible operating modes (auto-detected or explicitly configured in `~/.teachme-config.json`):
1. **Standalone Mode (Legacy):** `<VAULT_ROOT>` = `notes_root` in `~/.teachme-config.json` (fallback `~/notes`). Write ONLY inside `<VAULT_ROOT>/<topic-slug>/` (comparisons: `<VAULT_ROOT>/comparisons/`).
2. **Vault-Native Mode (Existing Obsidian Vault):** Activated when `.obsidian/` is detected, `mode` is `vault-native`, or `obsidian_vault` is connected via `/teachme-vault connect`. Adapt to the vault's folders, templates, tags, metadata, links, and style (`references/VAULT-NATIVE.md`). Store TeachMe learning state in `<vault>/.teachme/` (or configured `--state-dir`), isolated from ordinary user notes.
- If `<topic>` is omitted, run `vault_cli.py state` (auto-selects active standalone or vault-native vault) or ask ONE clarifying question.

## §B. Non-Negotiable Formatting & Hygiene Laws
**Scope Boundary (Mandatory):**
- **Standalone TeachMe files** (`00`–`09`, `topics/*.md`, `atomic/*.md`): enforce all 8 laws below.
- **Vault-Native generated notes**: preserve math hygiene (`§B.2–3`), valid YAML, and verified non-fabricated links (`§B.7`), while adapting YAML keys, tags, headings, callouts, and note length to the target vault's inferred conventions (`VAULT-NATIVE.md`).
- **Existing user-authored notes**: NEVER overwrite, reformat, rename, inject TeachMe IDs/markers, or run legacy `fix`/`verify` repairs on user notes. Extensions require explicit `--extend --apply` with backup.

1. **Pure Markdown + Strict YAML:** Double-quote `title`, `description`, `checkpoint`, `key_equations` items, and any YAML string containing `: | [ ] { } < > * & # ? \`. Spaces (never tabs) for indentation.
2. **Math Delimiter Law (100% coverage):** Every math symbol, Greek letter, sub/superscripted variable, arrow, set operator, or LaTeX macro (`\theta \in \to \implies \iff \sum \hat \mathbf \le \ge \neq \approx \frac \sqrt \lVert \rVert \mathbb \text \operatorname`) anywhere in prose, lists, headings, tables, or `<details>` MUST sit inside `$...$` or `$$...$$`. Zero bare backslashes outside code fences/inline code.
3. **Math Hygiene:** Never wrap `$`/`$$` math in backticks. No space before a closing `$`. Keep inline math single-line and balanced. Inside tables use `\mid \lvert \rvert \lVert \rVert`, never a raw `|`.
4. **`<details>` Block Law:** `<details>` and `</details>` each stand alone at column 0 (never inline, never inside a `-`/`1.` list item). Required shape — blank line, `<details>`, `<summary>…</summary>`, blank line, body, blank line, `</details>`. Put the question in a `####` heading above the block.
5. **Zero Black-Box Formulas:** Every equation gets a Formula Anatomy Breakdown (`references/STUDY-AND-GLOSSARY.md §1`).
6. **Dual-Layer Deep-Linking:** Never cite bare `[Author, Year]` or a bare homepage. Inline format: `([Author, Year](<doi-or-exact-url>) · [[01-RESOURCES#<anchor>|Source]] · [[02-DEEP-RESEARCH#<anchor>|Research]])` (`references/RESEARCH-TOOLCHAIN.md §3`). In Vault-Native Mode, adapt citation links to vault conventions while keeping exact external URLs.
7. **Zero Dead Links:** Every `[[wikilink]]`, relative link, and typed YAML edge (`depends_on`, `unlocks`, `contrasts_with`, `fixes_failure_of` → `topic-<nn>` IDs) resolves to an existing vault file. Never fabricate a wikilink target. Empty edge = `[]`, never `[[none]]`.
8. **Exhaustive Coverage:** In Standalone Mode, one `topics/<nn>-<slug>.md` per syllabus subtopic + `atomic/` cards. In Vault-Native Mode, adapt granularity (atomic split vs. comprehensive note) to the vault's inferred style.

## §C. CLI-First Execution Mandate (`scripts/vault_cli.py`, Python 3 stdlib)
Never hand-generate scaffolding or scan Markdown when a CLI call answers it. Resolve the script at `../teachme/scripts/vault_cli.py` or `~/.gemini/antigravity/skills/teachme/scripts/vault_cli.py`.

| Call | Use |
|---|---|
| `connect <vault> [--mode ...]` / `mode [mode]` | Connect existing Obsidian vault or view/switch operating mode |
| `discover <vault>` / `profile [vault]` / `reindex [vault]` | Profile vault folders, metadata, tags, style & plugins; refresh search index |
| `search <vault> --query "<T>"` / `plan <vault> --topic "<T>"` | Retrieve relevant existing notes and compute placement, template, tags & links |
| `generate <vault> --topic "<T>" [--dry-run\|--apply]` / `audit <vault>` | Preview/write vault-native notes safely and audit TeachMe-managed notes only |
| `init <vault> --topic "<T>" --subtopics <file.json>` | Standalone: scaffold dirs, `00-SESSION-STATE.md`, `00-MOC-INDEX.md`, `00-GRAPH.json`, topic stubs |
| `context <vault> --topic <nn>` | Standalone default per-turn load: state + node + stage slice + 1-hop `L0-L1` anchors |
| `state` / `graph` / `slice <file> --section <S>` | Resume pointer / rebuild `00-GRAPH.json` / single section (`L0-L1`, `L1-ANCHOR`…`L5-WORKBOOK-AND-GRAPH`) |
| `tick <vault> --topic <nn> --cp <1-4> --status <pass\|retry>` | Log checkpoints to `scratchpad/events.jsonl` |
| `flush <vault> --topic <nn> --note "<invariant>"` | Persist mastery once on `[4/4]` |
| `fix <vault>` → `verify <vault>` | Standalone: auto-repair `<details>`/bare LaTeX, then audit until `errors: []` (auto-skips user notes in vault-native mode) |

- **1-Hop Rule & Bounded Context:** Load only relevant indexed slices/neighbors; never dump an entire vault into LLM context.
- **Exit Gate:** Standalone write-phases end with `fix` → `verify` (`errors: []`). Vault-Native write-phases end with `audit <vault>` (`errors: []`).

## §D. Routing (Load ONLY the Listed File)

| Trigger | Reference | Output |
|---|---|---|
| Vault-Native Obsidian workflow (any write to an existing Obsidian vault) | `references/VAULT-NATIVE.md` | `profile.json`, `index.json`, vault-native notes |
| `/teachme-vault <subcommand>` | `references/cmd-vault.md` | `~/.teachme-config.json`, `.teachme/`, vault notes |
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
