# `/teachme` — Socratic Teaching & Learning-Memory Agent Skill

An AI agent skill suite (`/teachme` + 6 `/teachme-*` subcommands) for **interactive first-principles teaching, learner calibration, curriculum progression, and durable learning memory**. Works alongside **[Scriptorium](https://github.com/AayushPandey2/scriptorium)**, which owns study-note creation, expansion, formatting, linking, and vault validation.

Works with **Claude Code**, **Cursor**, **Windsurf**, **Antigravity**, **Gemini CLI**, **Cline**, **Codex**, and any `SKILL.md`-compatible AI coding or research assistant.

## Separation of Responsibilities

- **TeachMe owns:**
  - Interactive teaching, Socratic questioning, live Formula Anatomy walkthroughs, worked examples (`I Do` → `We Do` → `You Do`), and live Tier 1–3 practice.
  - Learner calibration (4-question Frontier Grilling with zero-baseline defaults), adaptive pacing, and curriculum dependency progression (`00-GRAPH.json`).
  - Checkpoints (`[1/4]`–`[4/4]`), append-only event history (`scratchpad/events.jsonl`), misconceptions and breakthroughs (`learning-records/`), interleaved spaced review, session recovery (`00-SESSION-STATE.md`), and compact context handoff (`vault_cli.py handoff`).
- **Scriptorium owns:**
  - Creating, expanding, organizing, formatting, linking, and validating study notes (`/scribe-notes`, `/scribe-expand`, `/scribe-doubt`, `scripts/vault_index.py`, `scripts/verify_vault_notes.py`).
  - Study guides, requested study-summary artifacts, and Obsidian note presentation.

*(Note: Scriptorium generates 7-section Markdown lessons and validates Obsidian notes; it does not replicate TeachMe's retired standalone `03-CORNELL-STUDY-GUIDE.md`, `08-FLASHCARDS.md`, `09-CHEAT-SHEET.md`, or `atomic/` layouts.)*

## Operational State Architecture

TeachMe creates **operational learning state only** — never study-note scaffolds:

- **Standalone Mode** (`<STATE_ROOT>/<topic-slug>/`, defaulting to `~/notes/<topic-slug>/`, customizable via `/teachme-notes-path`):

```text
<STATE_ROOT>/<topic-slug>/
├── 00-SESSION-STATE.md            # Hot-state resume pointer (<60 lines) & status map
├── 00-GRAPH.json                  # Curriculum dependency & progression graph
├── learning-records/              # ADR-style chronological mastery & misconception logs
└── scratchpad/                    # curriculum.json, subtopics.json, mission.json,
                                   # ingested-sources.json, events.jsonl, queue-<nn>.json
```

- **Vault-Native Mode (Existing Obsidian Vaults):** Connect an existing Obsidian vault to isolate TeachMe's operational state inside `<vault>/.teachme/sessions/<topic-slug>/` and search existing notes **read-only** as optional learning context:

```bash
# Connect your Obsidian vault (isolated state + read-only search index)
python skills/teachme/scripts/vault_cli.py connect "/path/to/MyObsidianVault"

# Search existing notes read-only as optional teaching context
python skills/teachme/scripts/vault_cli.py search "/path/to/MyObsidianVault" --query "Gradient Descent"
python skills/teachme/scripts/vault_cli.py reindex "/path/to/MyObsidianVault"
```

## Installation

Clone this repository and copy all `skills/teachme*` folders into your AI tool's skills directory:

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

### Optional Scriptorium Companion Setup

If you want TeachMe to hand off study-note creation or expansion to Scriptorium, install `scriptorium` separately in your agent's skills directory and configure its independent Obsidian vault path via `SCRIPTORIUM_VAULT_PATH` or `~/.scriptorium-config.json`:

```json
{
  "vault_path": "C:\\path\\to\\YourObsidianVault"
}
```

TeachMe never treats `~/.teachme-config.json` (`notes_root` or `.teachme/`) as Scriptorium's vault. If Scriptorium is not installed or its vault is unconfigured, TeachMe preserves your learning state and returns a blocked handoff with the exact `/scribe-*` command and context summary instead of generating study notes itself.

## Usage & Lifecycle Commands

| Autocomplete Command | Space-Separated Alias | What It Does |
| :--- | :--- | :--- |
| `/teachme <topic>` | *(or `/teachme <topic> --auto`)* | Runs 4-question calibration (or `--auto` defaults), builds an acyclic curriculum in `00-GRAPH.json`, and teaches interactively via the 4-Turn ONE-question Socratic loop. |
| `/teachme-review <topic>` | `/teachme review <topic>` | Launches an interleaved spaced-repetition Socratic coaching session targeting weak spots logged in `00-SESSION-STATE.md` and `learning-records/`. |
| `/teachme-feynman <concept>` | `/teachme feynman <concept>` | Reverse-teaching mastery audit: explain a concept and its formulas in plain English with zero unstated jargon under Socratic probing. |
| `/teachme-drill <topic> [1\|2\|3]` | `/teachme drill <topic> [--tier 1\|2\|3]` | Generates and grades live Tier 1–3 practice problems interactively, logging evidence to `events.jsonl` and `learning-records/`. |
| `/teachme-ingest <topic> <source>` | `/teachme ingest <topic> <source>` | Absorbs PDFs, URLs, transcripts, or repos into lesson context (`scratchpad/ingested-sources.json`, `curriculum.json`, `learning-records/`) without modifying study notes or mastered checkpoints. |
| `/teachme-vault <subcommand>` | `/teachme vault <subcommand>` | Connects an existing Obsidian vault (`connect`, `mode`, `search`, `reindex`, `state`) for isolated `.teachme/` state and read-only source lookup. |
| `/teachme-notes-path [path\|reset]` | `/teachme notes-path [path\|reset]` | Views, changes, or resets TeachMe's standalone learning-state root in `~/.teachme-config.json` (independent of Scriptorium's vault). |
| `wait what` / `simplify` | `/wait-what` | Pauses quizzing, re-explains from zero with a scalar trace, logs the clearer analogy to `learning-records/`, and resumes the exact checkpoint. |

### Removed Note Commands & Supported Replacements

| Removed TeachMe Command | Replacement |
| :--- | :--- |
| `/teachme-distill <topic>` | Scriptorium `/scribe-notes <topic>` or `/scribe-expand <topic>` |
| `/teachme-expand <topic>` | Scriptorium `/scribe-expand <topic>` |
| `/teachme-compare <A> vs <B>` | Interactive contrast in `/teachme`, or Scriptorium `/scribe-notes "<A> vs <B>"` for a note artifact |
| `/teachme-verify <topic>` | Scriptorium `scripts/verify_vault_notes.py "<vault_path>" [--fix]` for study notes; `vault_cli.py validate-state` for TeachMe operational state |

### Operational State CLI (`scripts/vault_cli.py`)

```bash
python skills/teachme/scripts/vault_cli.py init <session_or_vault> --topic "<Topic>" --subtopics subtopics.json
python skills/teachme/scripts/vault_cli.py context <session_or_vault> --topic 01
python skills/teachme/scripts/vault_cli.py tick <session_or_vault> --topic 01 --cp 2 --status pass
python skills/teachme/scripts/vault_cli.py flush <session_or_vault> --topic 01 --note "<verified invariant>"
python skills/teachme/scripts/vault_cli.py validate-state <session_or_vault>
python skills/teachme/scripts/vault_cli.py import-legacy <legacy_vault> [--target <state_dir>]
python skills/teachme/scripts/vault_cli.py handoff <session_or_vault> --topic 01 --request "revision notes"
```

## Repository Structure

```text
teachme-skill/
├── README.md
├── LICENSE
├── tests/
└── skills/
    ├── teachme/
    │   ├── SKILL.md                       # Master router, core invariants & intent routing
    │   ├── scripts/
    │   │   ├── vault_cli.py               # Operational state CLI (init, context, state, graph, tick, flush, validate-state, import-legacy, handoff, connect, mode, reindex, search, slice)
    │   │   └── teachme_vault/
    │   │       ├── __init__.py
    │   │       ├── cli_commands.py        # connect, mode, reindex, search handlers
    │   │       ├── indexer.py             # Read-only incremental vault search index
    │   │       ├── markdown_utils.py      # Read-only Markdown/YAML parser
    │   │       ├── models.py              # Config, mode detection, atomic writes, safety guards
    │   │       └── state_store.py         # Curriculum state, legacy importer & handoff envelope
    │   └── references/
    │       ├── MISSION-AND-GRILL.md       # Calibration grilling, curriculum planning & state init
    │       ├── RESEARCH-TOOLCHAIN.md      # Primary-source retrieval & provenance rules
    │       ├── RETENTION-AND-RECORDS.md   # 4-Turn Socratic loop, Formula Anatomy, Anti-Spoiler & ADR records
    │       ├── SCRIPTORIUM-HANDOFF.md     # Lazy-loaded Scriptorium delegation contract & context envelope
    │       ├── VAULT-NATIVE.md            # Isolated .teachme/ state & read-only Obsidian lookup
    │       └── cmd-*.md                   # Per-command workflows (drill, feynman, ingest, notes-path, review, vault)
    ├── teachme-drill/SKILL.md
    ├── teachme-feynman/SKILL.md
    ├── teachme-ingest/SKILL.md
    ├── teachme-notes-path/SKILL.md
    ├── teachme-review/SKILL.md
    └── teachme-vault/SKILL.md
```

## License

MIT
