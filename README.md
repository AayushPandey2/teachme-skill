# `/teachme` — Primary-Source Research & Mastery Agent Skill

An AI agent skill suite (`/teachme` + 9 autocomplete `/teachme-*` subcommands) that deeply researches any topic from primary sources, builds an interlinked Obsidian/Markdown study vault at `<VAULT_ROOT>/<topic-slug>/` (defaulting to `~/notes/<topic-slug>/`, customizable via `/teachme-notes-path`), and teaches it to you from **Absolute Zero** to **Complete Mastery**.

Works out of the box with **Claude Code**, **Cursor**, **Windsurf**, **Antigravity**, **Gemini CLI**, **Cline**, **Codex**, and any `SKILL.md`-compatible AI coding or research assistant.

## Why `/teachme`?

Standard LLM explanations dump a wall of text you forget five minutes later. `/teachme` acts as an end-to-end learning OS:

1. **Zero-Baseline & Absolute Mastery Defaults:** Starts every new session with 4 calibrated `❓` questions defaulting to **No prior knowledge** (build from absolute zero) and **Absolute mastery covering all topics** (zero-omission syllabus decomposition)—or jump straight in with `--auto`.
2. **Primary-Source Research Toolchain:** Separates vetted **Knowledge** (RFCs, papers, official docs, textbooks) from practitioner **Wisdom** (post-mortems, talks, benchmarks), captures rough drafts in `scratchpad/`, and logs unresolved gaps explicitly.
3. **8-Block Subtopic Notes & 6-Point Critic Audit:** Generates a dedicated deep-dive `.md` file inside `topics/` for **every** subtopic in topological prerequisite order—featuring typed YAML edges, `L1`–`L5` semantic section anchors, zero-baseline micro-bridges, 4-layer theory with ASCII diagrams and contrastive "Is vs. Is Not" tables, zero-skip axiom derivations, runnable Python/NumPy `assert` verification blocks, and gradual-release (`I Do` → `We Do` → `You Do`) workbooks.
4. **Hot-State Resume & Progressive Disclosure (`L0`/`L1`/`L2`):** Uses a compact `<60`-line `00-SESSION-STATE.md` pointer and `L1-ANCHOR` summaries to resume sessions without context rot, plus auto-compaction strips every 3 completed subtopics.
5. **Progressive 7-Component Socratic Loop:** Escalates across 3 depth stages (`1/3`, `2/3`, `3/3`) and 4 checkpoints (`[1/4]` Discovery Hook → `[2/4]` `We Do` → `[3/4]` `You Do` → `[4/4]` Adversarial Edge-Case + Feynman Gate), enforcing a strict **Anti-Spoiler Rule** with drop-down 1-number micro-steps and an inline `wait what` / `simplify` escape hatch.
6. **Autocomplete Slash-Command Suite & Custom Vault Root:** Exposes every workflow as a top-level `/teachme-*` skill alongside `/teachme` so all 10 commands appear immediately in your editor or CLI slash-command dropdown, and lets you redirect where vaults live via `/teachme-notes-path` (`~/.teachme-config.json`).

## Generated Vault Architecture

Every `/teachme <topic>` run creates and maintains a pure-Markdown vault inside `<VAULT_ROOT>/<topic-slug>/` (defaulting to `~/notes/<topic-slug>/`; change or reset anytime with `/teachme-notes-path`):

```text
<VAULT_ROOT>/<topic-slug>/
├── 00-SESSION-STATE.md            # Hot-state resume pointer (<60 lines), status map & last verified invariant
├── 00-MOC-INDEX.md                # Master Map of Content, Mermaid + ASCII dependency graph, synthesis strips & checkboxes
├── 00-MISSION.md                  # Target outcome, baseline (0 prior knowledge), scope & success criteria
├── 01-RESOURCES.md                # Primary sources (Knowledge), practitioner signal (Wisdom) & Gaps
├── 02-DEEP-RESEARCH.md            # Primary-source cited research dossier with full formula anatomy
├── 03-CORNELL-STUDY-GUIDE.md      # Master synthesis notes & <details> active-recall cues
├── 04-GLOSSARY.md                 # Crisp 1–2 sentence definitions + "_Avoid_:" aliases
├── 05-MENTAL-MODELS.md            # Feynman analogies, first-principles axioms & failure pre-mortems
├── 06-DERIVATIONS-AND-PROOFS.md   # Step-by-step algebraic & logical derivations from base axioms
├── 07-PRACTICE-PROBLEMS.md        # Graded Tier 1–3 problems with hidden step-by-step solutions
├── 08-FLASHCARDS.md               # Obsidian Spaced Repetition / Anki-ready Q&A & cloze cards
├── 09-CHEAT-SHEET.md              # Single-page executive cheat sheet (/teachme-distill & auto-compaction)
├── topics/                        # Dedicated 8-Block deep-dive .md file for EVERY subtopic (with L1-L5 anchors)
├── atomic/                        # Interlinked evergreen Zettelkasten cards ([[wikilinks]] + L1-L5 anchors)
├── learning-records/              # ADR-style chronological mastery & misconception logs
└── scratchpad/                    # Ephemeral working buffer (raw-research.md, derivation-drafts.md)
```

## Installation

Clone this repository and copy all `skills/teachme*` folders into your AI tool's skills directory (so `/teachme` and all `/teachme-*` subcommands appear in slash-command autocomplete), and create your central `~/notes` vault folder:

```bash
git clone https://github.com/AayushPandey2/teachme-skill.git
cd teachme-skill
mkdir -p ~/notes
```

### Copy by Agent

| Agent / Tool | Global Skills Path | Project-Local Path | Global Install Command |
| :--- | :--- | :--- | :--- |
| **Claude Code** | `~/.claude/skills/` | `.claude/skills/` | `mkdir -p ~/.claude/skills && cp -r skills/teachme* ~/.claude/skills/` |
| **Cursor** | `~/.cursor/skills/` | `.cursor/skills/` | `mkdir -p ~/.cursor/skills && cp -r skills/teachme* ~/.cursor/skills/` |
| **Antigravity** | `~/.gemini/antigravity/skills/` | `.agent/skills/` | `mkdir -p ~/.gemini/antigravity/skills && cp -r skills/teachme* ~/.gemini/antigravity/skills/` |
| **Gemini CLI** | `~/.gemini/skills/` | `.gemini/skills/` | `mkdir -p ~/.gemini/skills && cp -r skills/teachme* ~/.gemini/skills/` |
| **Windsurf** | `~/.codeium/windsurf/skills/` | `.windsurf/skills/` | `mkdir -p ~/.codeium/windsurf/skills && cp -r skills/teachme* ~/.codeium/windsurf/skills/` |
| **Cline** | `~/.cline/skills/` | `.cline/skills/` | `mkdir -p ~/.cline/skills && cp -r skills/teachme* ~/.cline/skills/` |
| **Codex / Generic** | `~/.agents/skills/` | `.agents/skills/` | `mkdir -p ~/.agents/skills && cp -r skills/teachme* ~/.agents/skills/` |

## Usage & Lifecycle Commands

Open a new session in your agent and type `/teachme` to see all subcommands in your slash-command autocomplete dropdown *(space-separated aliases like `/teachme expand <topic>` also work)*:

| Autocomplete Command | Space-Separated Alias | What It Does |
| :--- | :--- | :--- |
| `/teachme <topic>` | *(or `/teachme <topic> --auto`)* | Runs Phase 1 Frontier Grilling (or `--auto` defaults), builds the full vault at `<VAULT_ROOT>/<topic-slug>/` (default `~/notes/`), and teaches interactively via the 7-Component Mastery Loop. |
| `/teachme-notes-path [path\|reset]` | `/teachme notes-path [path\|reset]` | Views the active `<VAULT_ROOT>`, redirects vault storage to a custom folder (`~/.teachme-config.json`), or resets back to `~/notes`. |
| `/teachme-expand <topic>` | `/teachme expand <topic>` | Deepens pre-existing notes in place to the 8-Block Standard, creates `.md` files for missing related subtopics, and runs the 6-Point Critic Audit. |
| `/teachme-verify <topic>` | `/teachme verify <topic>` *(or `audit`)* | Multi-pass audit & auto-repair of broken `[[wikilinks]]`, typed YAML edges, orphaned files, `00-SESSION-STATE.md`, and malformed LaTeX across the vault. |
| `/teachme-ingest <topic> <source>` | `/teachme ingest <topic> <source>` | Absorbs new PDFs, URLs, lecture notes, or raw dumps into an existing vault, flags contradictions, and syncs `00-SESSION-STATE.md` without overwriting mastered checkpoints. |
| `/teachme-distill <topic>` | `/teachme distill <topic>` | Compresses a vault into a high-density 1-page `09-CHEAT-SHEET.md` and refreshes the `08-FLASHCARDS.md` spaced-repetition deck. |
| `/teachme-review <topic>` | `/teachme review <topic>` | Launches an interleaved spaced-repetition Socratic coaching session targeting weak spots logged in `00-SESSION-STATE.md` and `learning-records/`. |
| `/teachme-feynman <concept>` | `/teachme feynman <concept>` | Reverse-teaching mastery audit: explain a concept and its formulas back in plain English with zero unstated jargon under Socratic probing. |
| `/teachme-drill <topic> [1\|2\|3]` | `/teachme drill <topic> [--tier 1\|2\|3]` | Generates and grades Tier 1 (recall), Tier 2 (multi-step), or Tier 3 (adversarial edge-case) practice problems into `07-PRACTICE-PROBLEMS.md`. |
| `/teachme-compare <A> vs <B>` | `/teachme compare <A> vs <B>` | Builds a primary-source structural trade-off matrix at `<VAULT_ROOT>/comparisons/<a-vs-b>.md` contrasting two concepts, algorithms, or architectures. |
| `wait what` / `simplify` | `/wait-what` | Pauses quizzing during Phase 6, re-explains the sticking point from absolute zero using a scalar trace, and saves the clearer analogy to `05-MENTAL-MODELS.md`. |

*(If your agent does not support `/slash` skill commands natively, prompt: `"Use the teachme skill to research and teach me <topic>."`)*

## Repository Structure

```text
teachme-skill/
├── README.md
├── LICENSE
└── skills/
    ├── teachme/                           # Single source of truth: master router, operating laws & references
    │   ├── SKILL.md
    │   └── references/
    │       ├── MISSION-AND-GRILL.md       # Frontier grilling (0 prior knowledge + absolute mastery defaults)
    │       ├── RESEARCH-TOOLCHAIN.md      # Knowledge vs. Wisdom sourcing & primary-source chaser
    │       ├── STUDY-AND-GLOSSARY.md      # 8-Block subtopic standard, 6-Point Critic Audit, L1-L5 anchors & templates
    │       ├── RETENTION-AND-RECORDS.md   # 7-Component progressive mastery loop, Anti-Spoiler & ADR records
    │       └── SUBCOMMANDS.md             # Workflows for notes-path, expand, verify, ingest, distill, review, feynman, drill & compare
    ├── teachme-notes-path/SKILL.md        # Wrapper -> /teachme-notes-path [path|reset]
    ├── teachme-expand/SKILL.md            # Wrapper -> /teachme-expand <topic>
    ├── teachme-verify/SKILL.md            # Wrapper -> /teachme-verify <topic>
    ├── teachme-ingest/SKILL.md            # Wrapper -> /teachme-ingest <topic> <source>
    ├── teachme-distill/SKILL.md           # Wrapper -> /teachme-distill <topic>
    ├── teachme-review/SKILL.md            # Wrapper -> /teachme-review <topic>
    ├── teachme-feynman/SKILL.md           # Wrapper -> /teachme-feynman <concept>
    ├── teachme-drill/SKILL.md             # Wrapper -> /teachme-drill <topic> [1|2|3]
    └── teachme-compare/SKILL.md           # Wrapper -> /teachme-compare <A> vs <B>
```

## Acknowledgments

Inspired by workflow patterns from [`mattpocock/skills`](https://github.com/mattpocock/skills), [`rohankgeorge/the-researcher`](https://github.com/rohankgeorge/the-researcher), and [`rohankgeorge/thinking-tools`](https://github.com/rohankgeorge/thinking-tools).

## License

MIT
