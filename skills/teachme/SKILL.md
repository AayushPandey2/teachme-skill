---
name: teachme
description: "Unified end-to-end learning, deep primary-source research, frontier grilling, Socratic teaching, and structured Markdown note-taking pipeline. Invoke with /teachme <topic> or when the user asks to deeply research, learn, build a study guide, generate Cornell notes, create Zettelkasten cards, or master any topic from first principles into a central vault (<VAULT_ROOT>/<topic-slug>/, defaulting to ~/notes)."
---

# Unified `/teachme` Master Core

For full-pipeline `/teachme <topic>` (Phases 1–6), load `references/PIPELINE.md`. For subcommands, load only `references/cmd-<subcommand>.md`.

## Non-Negotiable Operating Laws

1. **Central Vault & Dynamic `<VAULT_ROOT>`:** Write only to `<VAULT_ROOT>/<topic-slug>/` (never scatter notes in project folders). Resolve `<VAULT_ROOT>` from `~/.teachme-config.json` (`notes_root`), defaulting to `~/notes` if absent/unset.
2. **Frontier Grilling First:** New `/teachme <topic>` runs start with Phase 1 (`MISSION-AND-GRILL.md`) unless `--auto`, `"auto"`, `"defaults"`, or `"go"` is passed.
3. **Pure Markdown & Strict YAML Frontmatter:** Produce 100% pure `.md` files. Double-quote `"..."` all `description`, `title`, `checkpoint`, `key_equations`, and YAML string values containing `:`, `|`, `[`, `]`, `{`, `}`, `<`, `>`, `*`, `&`, `#`, `?`, or `\`.
4. **Primary-Source Grounding:** Treat pre-trained knowledge as untrusted until grounded in primary sources (Phase 2).
5. **Minimal Progressive Reference Loading:** Load `references/PIPELINE.md` only for full `/teachme <topic>`, and `references/cmd-<subcommand>.md` for subcommands.
6. **Exhaustive Subtopics (No Caps):** Generate a standalone `topics/<nn>-<subtopic-slug>.md` (`references/subtopic-8block.md`) for every syllabus subtopic, plus `atomic/` cards.
7. **Zero Black-Box Formulas:** Every formula in `02-DEEP-RESEARCH.md`, `03-CORNELL-STUDY-GUIDE.md`, and `topics/*.md` follows `references/subtopic-8block.md` §1.
8. **7-Component Blueprint & Strict Anti-Spoiler Rule:** Phase 6 runs 3 Escalating Depth Turns (`1/3`, `2/3`, `3/3`) and 4 Checkpoints (`[1/4]`–`[4/4]`) per `references/RETENTION-AND-RECORDS.md` §2–3. On `"idk"`, `"explain"`, or errors, **NEVER** reveal the answer—drop down to a 1-number micro-question.
9. **Zero Backtick-Wrapped Math:** NEVER wrap `$` or `$$` math in code backticks anywhere (including table cells).
10. **Table-Safe LaTeX Delimiters:** Inside Markdown tables, use `\mid`, `\lvert`, `\rvert`, `\lVert`, `\rVert` instead of raw `|`; keep inline math single-line and balanced.
11. **Zero-Dead-Link & Typed Edge Rule:** Every `[[wikilink]]`, relative `.md` link, and YAML typed edge (`depends_on`, `unlocks`, `contrasts_with`, `fixes_failure_of`) must resolve to an existing vault file (use `[]`, never `[[none]]`).
12. **CLI-Backed Spreading Activation, Queue & Delta-Flush:**
    - **Start/Resume:** Run `scripts/vault_cli.py state` and `graph` instead of scanning Markdown files.
    - **1-Hop Spreading Activation:** Load ONLY active stage slices of `topic-<nn>` via `vault_cli.py slice` + immediate 1-hop neighbors (`depends_on`, `contrasts_with` from `00-GRAPH.json`) via `--section L0-L1`. Forbid loading mastered nodes $>1$ hop away unless an interleaved warm-up queries them.
    - **Queue & Batch Flush:** Write `scratchpad/queue-<nn>.json` once per lesson; log `[1/4]`–`[3/4]` via `vault_cli.py tick`; run `vault_cli.py flush` once on `[4/4]`.
    - **Auto-Compaction:** Keep raw drafts in `scratchpad/`; every 3 completed subtopics append a 5-line **Cumulative Synthesis Strip** to `00-MOC-INDEX.md` and roll up formulas into `09-CHEAT-SHEET.md`.

## Subcommand Router

| Autocomplete Command & Alias | Reference | Target |
|---|---|---|
| `/teachme <topic>` *(or `--auto`)* | `references/PIPELINE.md` | `<VAULT_ROOT>/<topic-slug>/` |
| `/teachme-notes-path [path\|reset]` \| `/teachme notes-path` | `references/cmd-notes-path.md` | `~/.teachme-config.json` |
| `/teachme-expand <topic>` \| `/teachme expand` | `references/cmd-expand.md` | `<VAULT_ROOT>/<topic-slug>/` |
| `/teachme-verify <topic>` \| `/teachme verify` / `audit` | `references/cmd-verify.md` | `<VAULT_ROOT>/<topic-slug>/` |
| `/teachme-ingest <topic> <source>` \| `/teachme ingest` | `references/cmd-ingest.md` | `<VAULT_ROOT>/<topic-slug>/` |
| `/teachme-distill <topic>` \| `/teachme distill` | `references/cmd-distill.md` | `<VAULT_ROOT>/<topic-slug>/09-CHEAT-SHEET.md` |
| `/teachme-review <topic>` \| `/teachme review` | `references/cmd-review.md` | `<VAULT_ROOT>/<topic-slug>/` |
| `/teachme-feynman <concept>` \| `/teachme feynman` | `references/cmd-feynman.md` | `<VAULT_ROOT>/<topic-slug>/` |
| `/teachme-drill <topic> [1\|2\|3]` \| `/teachme drill` | `references/cmd-drill.md` | `<VAULT_ROOT>/<topic-slug>/07-PRACTICE-PROBLEMS.md` |
| `/teachme-compare <A> vs <B>` \| `/teachme compare` | `references/cmd-compare.md` | `<VAULT_ROOT>/comparisons/<a-vs-b>.md` |
