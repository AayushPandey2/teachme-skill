# `/teachme` — Source-Independent Adaptive Teaching & Learning-Memory Skill

An AI agent skill suite (`/teachme` + 6 `/teachme-*` subcommands) for **source-independent adaptive first-principles teaching, lightweight calibration, diagnostic prerequisite repair, objective-level coverage & gap tracking, assistance-aware evidence, and deterministic delayed review**.

**Fundamental rule: TeachMe teaches. Other skills write notes.** TeachMe works independently of any note-generation skill and teaches from existing Obsidian vaults, web/documentation sources, or both (`vault`, `hybrid`, or `web` mode).

Works with **Claude Code**, **Cursor**, **Windsurf**, **Antigravity**, **Gemini CLI**, **Cline**, **Codex**, and any `SKILL.md`-compatible AI coding or research assistant.

## Separation of Responsibilities

- **TeachMe owns:**
  - Deterministic source resolution (`vault_cli.py resolve-sources`) across permitted Obsidian vaults (retrieving bounded actual Markdown sections and related prerequisite/embedded notes) and/or host web/documentation tools (`vault` / `hybrid` / `web`).
  - Interactive adaptive teaching, lightweight calibration, short adaptive diagnostics, and prerequisite repair (`revise-curriculum`).
  - Graduated support (`hint` -> `scaffold` -> `worked_example` -> fresh unaided attempt), direct answers to direct conceptual questions, and optional bounded live visuals/experiments (`scratchpad/media/`).
  - Objective-level curriculum coverage, assistance-aware proficiency, separate retention and transfer tracking, append-only event history (`scratchpad/events.jsonl`), deterministic delayed review scheduling (`scratchpad/review-state.json`), lazy misconception records (`learning-records/`), and optional provider-independent context handoff (`vault_cli.py handoff`).
- **External note-writing skills (optional) own:**
  - Creating, expanding, organizing, formatting, linking, and validating persistent reusable study artifacts when explicitly requested by the user. TeachMe never invokes note skills during normal teaching and never writes study notes or `raw-research.md` by default.

## Key Adaptive Capabilities

- **Adaptive Teaching & Graduated Support:** Replaces rigid 4-turn templates, forced closing quizzes, mandatory ASCII diagrams, and endless anti-spoiler hinting with an evidence-driven decision policy (`Identify objective -> Inspect prerequisites/performance -> Teach or assess -> Observe -> Update evidence -> Select next action`). If you ask `"explain"`, TeachMe explains directly and follows up later with a fresh unaided problem.
- **Lightweight Calibration & Diagnostics:** Uses known session context first and asks only for missing information that materially changes the path (goal/scope, background, time budget, language/constraints). Substantial topics use short 2–4 task adaptive diagnostics; skipped prerequisites are marked `unknown` (untested), never mastered.
- **Visible Coverage & Gaps:** Curriculum nodes support multiple assessable objectives with stable IDs, required/optional scope status, assumptions, and DAG-validated prerequisites. TeachMe never promises "zero gaps" across an unlimited scope; `coverage` and `progress` report demonstrated vs. untested required objectives and unresolved prerequisites.
- **Retention vs. Transfer & Delayed Review:** Tracks delayed recall (`>= 12h` in a new session) and unfamiliar transfer separately from immediate unaided success. A deterministic scheduler (configurable defaults `[1, 3, 7, 21]` days) surfaces due previously demonstrated items, legacy unverified items, and lapsed items via `vault_cli.py due`. Assisted passes and same-session retries never advance the retention schedule.
- **Optional Visuals & Capability-Aware Fallbacks:** Chooses photographs, computed plots, trace tables, or small bounded experiments only when they serve an explicit objective. Never invents host tools, image inspections, URLs, or licenses (`record-media` defaults unknown licenses to `"unknown"`), and falls back cleanly to terminal/text tables when rich rendering is unavailable.

## Operational State Architecture

TeachMe creates **operational learning state only** — never reusable study-note scaffolds:

- **Standalone Mode** (`<STATE_ROOT>/<topic-slug>/`, defaulting to `~/notes/<topic-slug>/`, customizable via `/teachme-notes-path`):

```text
<STATE_ROOT>/<topic-slug>/
├── 00-SESSION-STATE.md            # Hot-state resume pointer (<60 lines) & status map
├── 00-GRAPH.json                  # Curriculum dependency & progression graph
├── learning-records/              # Chronological mastery & misconception logs
└── scratchpad/                    # curriculum.json (v2), review-state.json, mission.json,
                                   # media-provenance.json, ingested-sources.json,
                                   # events.jsonl, backups/, queue-<nn>.json
```

- **Vault-Native Mode (Existing Obsidian Vaults & Multi-Vault Registry):** Register one or more Obsidian vaults to isolate TeachMe's operational state inside `<vault>/.teachme/sessions/<topic-slug>/` and retrieve bounded note sections **read-only** as teaching sources:

```bash
python skills/teachme/scripts/vault_cli.py connect "/path/to/MyObsidianVault" --name main
python skills/teachme/scripts/vault_cli.py vaults
python skills/teachme/scripts/vault_cli.py use-vault main
python skills/teachme/scripts/vault_cli.py resolve-sources --topic "Gradient Descent"
python skills/teachme/scripts/vault_cli.py search "/path/to/MyObsidianVault" --query "Gradient Descent" --sections
python skills/teachme/scripts/vault_cli.py reindex "/path/to/MyObsidianVault"
```

## Legacy Session & Migration Compatibility

- Legacy vaults (`topics/*.md`, `00-MOC-INDEX.md`, v1 `00-GRAPH.json` / `curriculum.json`, and legacy `tick`/`flush` calls) continue to work and can be migrated idempotently via `migrate` or `import-legacy`.
- Migration backs up existing operational state files under `scratchpad/backups/`, validates references and DAG acyclicity before replacing files, preserves unrelated metadata, and never touches user study notes.
- Legacy `4/4` / `mastered` flags without explicit independent evidence are marked `legacy_unverified` with `retention: "untested"` and `transfer: "untested"` — missing historical evidence is never fabricated.

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

### Optional External Note-Skill Interoperability

TeachMe works completely standalone without any note-generation skill. If you explicitly request persistent reusable study notes, TeachMe can discover a compatible installed note-writing skill and pass a compact instruction-level context envelope (`vault_cli.py handoff`). If none is installed or configured, TeachMe preserves your learning state and reports the handoff as blocked/unavailable with the context summary instead of creating study notes itself.

## Usage & Lifecycle Commands

| Autocomplete Command | Space-Separated Alias | What It Does |
| :--- | :--- | :--- |
| `/teachme <topic>` | *(or `/teachme <topic> --auto`)* | Runs lightweight calibration & adaptive diagnostics, builds an acyclic objective curriculum, and teaches adaptively using evidence-based assessments. |
| `/teachme-review <topic>` | `/teachme review <topic>` | Runs delayed spaced review (`due`) starting with unaided retrieval on due demonstrated, legacy-unverified, and lapsed objectives. |
| `/teachme-feynman <concept>` | `/teachme feynman <concept>` | Reverse-teaching check: explain a concept and its assumptions in plain English with zero unstated jargon. |
| `/teachme-drill <topic> [1\|2\|3]` | `/teachme drill <topic> [--tier 1\|2\|3]` | Generates, verifies, and grades adaptive Tier 1–3 tasks with graduated support and assistance-aware logging. |
| `/teachme-ingest <topic> <source>` | `/teachme ingest <topic> <source>` | Absorbs PDFs, URLs, transcripts, or repos into lesson context without modifying study notes or overwriting demonstrated evidence. |
| `/teachme-vault <subcommand>` | `/teachme vault <subcommand>` | Connects an existing Obsidian vault (`connect`, `mode`, `search`, `reindex`, `state`) for isolated `.teachme/` state and read-only source lookup. |
| `/teachme-notes-path [path\|reset]` | `/teachme notes-path [path\|reset]` | Views, changes, or resets TeachMe's standalone learning-state root in `~/.teachme-config.json`. |

### Removed Note Commands & Replacements

| Removed TeachMe Command | Replacement |
| :--- | :--- |
| `/teachme-distill <topic>` | Optional external note-writing skill via `NOTE-SKILL-HANDOFF.md` |
| `/teachme-expand <topic>` | Optional external note-writing skill via `NOTE-SKILL-HANDOFF.md` |
| `/teachme-compare <A> vs <B>` | Interactive contrast in `/teachme`, or optional external note-writing skill for a persistent comparison artifact |
| `/teachme-verify <topic>` | `vault_cli.py validate-state` for TeachMe operational state; external note skill for study-note formatting verification |

### Operational State CLI (`scripts/vault_cli.py`)

```bash
# Initialize session and record lightweight calibration/diagnostic prerequisites
python skills/teachme/scripts/vault_cli.py init <session_or_vault> --topic "<Topic>" --subtopics subtopics.json --goal "<Goal>"
python skills/teachme/scripts/vault_cli.py calibrate <session_or_vault> --background "<bg>" --time-budget 20 --prereq "chain_rule=demonstrated:Solved composite example"

# Per-turn bounded context and objective-level assessment logging
python skills/teachme/scripts/vault_cli.py context <session_or_vault> --topic 01
python skills/teachme/scripts/vault_cli.py assess <session_or_vault> --topic 01 --objective obj-01-01 --assessment-type independent_application --result pass --assistance none --rationale "Solved without hints"

# Inspect coverage/gaps, honest progress, and due delayed reviews (read-only)
python skills/teachme/scripts/vault_cli.py coverage <session_or_vault>
python skills/teachme/scripts/vault_cli.py progress <session_or_vault>
python skills/teachme/scripts/vault_cli.py due <session_or_vault>

# Revise curriculum when a missing prerequisite is discovered, or record media provenance
python skills/teachme/scripts/vault_cli.py revise-curriculum <session_or_vault> --slug 00-slopes --title "Slope Intuition" --unlocks topic-01 --before-topic 01
python skills/teachme/scripts/vault_cli.py record-media <session_or_vault> --objective obj-01-01 --kind generated_plot --local-path scratchpad/media/loss.png --verification generated_plot

# Validate, migrate, import legacy vaults, or generate an optional note-skill handoff envelope
python skills/teachme/scripts/vault_cli.py validate-state <session_or_vault>
python skills/teachme/scripts/vault_cli.py migrate <session_or_vault>
python skills/teachme/scripts/vault_cli.py import-legacy <legacy_vault> [--target <state_dir>]
python skills/teachme/scripts/vault_cli.py handoff <session_or_vault> --topic 01 --request "revision notes"

# Terminal-first intelligent teaching engine (modality router, graphs, simulations, adaptive quizzes, image planning)
python skills/teachme/scripts/vault_cli.py capabilities
python skills/teachme/scripts/vault_cli.py route-modality <session_or_vault> --topic 01
python skills/teachme/scripts/vault_cli.py graph-render --kind function --expr "x^2 - 2*x" --x-min -2 --x-max 4 --format text
python skills/teachme/scripts/vault_cli.py simulate --template gradient_descent --param lr=0.2 --param w0=4 --predict decrease --steps 5 --format text
python skills/teachme/scripts/vault_cli.py simulate --template sorting --param algorithm=selection --param array=5,2,8,1,4 --steps 4 --format text
python skills/teachme/scripts/vault_cli.py simulate --template c_pointers --param scenario=basic_deref --steps 3 --format text
python skills/teachme/scripts/vault_cli.py simulate --template probability --param p=0.5 --param batch_size=50 --steps 4 --format text
python skills/teachme/scripts/vault_cli.py quiz-plan <session_or_vault> --topic 01
python skills/teachme/scripts/vault_cli.py evaluate-answer --kind numeric --expected 4.5 --answer "4.5"
python skills/teachme/scripts/vault_cli.py image-plan --topic-name "Human Heart" --desc "Identify left ventricle anatomy" --no-tty
```

## Policy Scenarios & Tests

- Documented adaptive teaching policy scenarios (`A`–`J`): [docs/TEACHING-SCENARIOS.md](docs/TEACHING-SCENARIOS.md)
- Run unit tests: `python -m unittest discover -s tests -v`

## Repository Structure

```text
teachme-skill/
├── README.md
├── LICENSE
├── docs/
│   └── TEACHING-SCENARIOS.md              # Documented policy scenarios A–J
├── tests/
└── skills/
    ├── teachme/
    │   ├── SKILL.md                       # Master router, core invariants & intent routing
    │   ├── scripts/
    │   │   ├── vault_cli.py               # Operational state CLI
    │   │   └── teachme_vault/
    │   │       ├── __init__.py
    │       ├── adaptive_quiz.py   # Level 1-3 question selection & deterministic checking
    │   │       ├── cli_commands.py        # connect, vaults, use-vault, resolve-sources, search, reindex
    │   │       ├── engine_commands.py # capabilities, route-modality, graph-render, simulate, quiz-plan, evaluate-answer, image-plan
    │       ├── evidence.py            # Objective coverage, proficiency & media provenance
    │       ├── indexer.py             # Read-only incremental vault index & source resolution
    │       ├── markdown_utils.py      # Read-only Markdown/YAML parser
    │   │       ├── media_retrieval.py # Credible web image filtering, caching & terminal fallbacks
    │   │       ├── modality_router.py # Explainable teaching modality selection policy
    │       ├── models.py              # Config, multi-vault registry, mode detection, safety guards
    │       ├── scheduler.py           # Deterministic delayed-review scheduler & ranking
    │   │       ├── simulations.py     # Bounded portable simulations (GD, sorting, C pointers, probability)
    │       ├── state_store.py         # Curriculum state, migration, revision & handoff
    │   │       ├── terminal_caps.py   # Cross-platform TTY, NO_COLOR, Unicode & image protocol detection
    │   │       └── terminal_graph.py  # Stdlib ASCII/Unicode/Braille plotter & safe math AST evaluator
    │   └── references/
    │       ├── MISSION-AND-GRILL.md       # Source resolution, fast calibration, diagnostics & init
    │       ├── RESEARCH-TOOLCHAIN.md      # Source-mode-aware retrieval & untrusted content rules
    │       ├── RETENTION-AND-RECORDS.md   # Adaptive teaching policy, graduated support & records
    │       ├── VISUALS-AND-EXPERIMENTS.md # Visual selection, capability contract & image provenance
    │       ├── NOTE-SKILL-HANDOFF.md      # Lazy-loaded provider-independent note-skill contract
    │       ├── VAULT-NATIVE.md            # Multi-vault registry, isolated state & read-only lookup
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
