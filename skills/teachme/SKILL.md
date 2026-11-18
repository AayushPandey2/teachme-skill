---
name: teachme
description: "Adaptive first-principles teaching, lightweight calibration, diagnostic prerequisite repair, evidence-based assessment, delayed review scheduling, and durable learning-state tracking. Invoke with /teachme <topic> or when the user asks to learn, practice, review, or be quizzed on any topic. Delegates requested reusable study-note, cheat-sheet, flashcard, and summary artifact creation to Scriptorium."
---

# `/teachme` Master Router & Core Laws

This file is the **single source of truth** for TeachMe's core invariants, operational learning-state paths, intent routing, and CLI laws. Reference files cite `SKILL.md §A–§D` and are loaded **only when relevant**.

## §A. Learning-State Root & Operating Mode Resolution
TeachMe persists **operational learning state only** (never reusable study notes) in two compatible modes configured via `~/.teachme-config.json`:
1. **Standalone Mode:** `<STATE_ROOT>` = `notes_root` in `~/.teachme-config.json` (fallback `~/notes`). Session state lives at `<STATE_ROOT>/<topic-slug>/` (`00-SESSION-STATE.md`, `00-GRAPH.json`, `learning-records/`, `scratchpad/`).
2. **Vault-Native Mode (Existing Obsidian Vault):** Activated when `.obsidian/` is detected, `mode` is `vault-native`, or `obsidian_vault` is connected via `/teachme-vault connect`. Isolated state lives at `<vault>/.teachme/sessions/<topic-slug>/` (or `--state-dir`). Existing vault notes are **read-only learning sources only**.
- Scriptorium's study-note vault (`SCRIPTORIUM_VAULT_PATH` or `~/.scriptorium-config.json`) is independent; never substitute TeachMe's `notes_root` or `.teachme/` as Scriptorium's vault.
- If `<topic>` is omitted, run `vault_cli.py state` to auto-select the active session, or ask ONE clarifying question.

## §B. Teaching, Evidence, Capability & Ownership Invariants
1. **TeachMe vs. Scriptorium Ownership:** TeachMe owns interactive teaching, calibration, diagnostics, objective coverage, assessment evidence, review scheduling, misconception records, and transient live visuals/experiments (`scratchpad/media/`). Scriptorium owns requested reusable study artifacts (study notes, study guides, cheat sheets, flashcards, glossaries, MOCs).
2. **No Study-Note Generation:** TeachMe must NEVER create, expand, format, tag, link-repair, or write study notes or reusable study-summary artifacts (not even in chat as a fallback if Scriptorium is unavailable). Transient teaching plots, traces, or experiments are operational teaching assets, not study notes.
3. **Existing Notes Are Read-Only:** Never modify, rename, reformat, or delete user notes or legacy study-note files. `flush` and `tick`/`assess` update operational state only.
4. **Honest Evidence & Coverage:** Separate coverage (`not_taught`, `introduced`, `assessed`, `demonstrated`, `unresolved`, `out_of_scope`), proficiency (`untested`, `introduced`, `practiced_with_support`, `demonstrated_independently`, `weakened`, `legacy_unverified`), retention, and transfer. Never promise "zero gaps" or universal mastery; report untested required objectives and unresolved gaps explicitly. Never fabricate confidence, response time, learner answers, independent success, retention, transfer, URLs, licenses, or image inspection results.
5. **Capability-Aware Tool Use:** Use only tools exposed by the current host. Provide progressive fallbacks (render directly -> local/browser artifact -> static/text fallback). Never require installing an MCP merely to continue a lesson.
6. **Clarity in Chat:** Define unfamiliar symbols, units, domains, and assumptions before relying on them (`$...$` / `$$...$$` for math); state any unverified claim explicitly.

## §C. Operational State CLI (`scripts/vault_cli.py`, Python 3 stdlib)
Resolve the script at `../teachme/scripts/vault_cli.py` or `~/.gemini/antigravity/skills/teachme/scripts/vault_cli.py`.

| Call | Use |
|---|---|
| `init <path> --topic "<T>" --subtopics <file.json>` | Initialize operational state with assessable objectives |
| `calibrate [path] [--goal ...] [--prereq name=state[:ev]]` | Persist lightweight calibration & prerequisite states (`unknown\|needs_support\|demonstrated`) |
| `context [path] --topic <nn> [--now <iso>]` | Per-turn bounded load: state + objectives + prerequisites + due summary + recent events + 1-hop neighbors |
| `assess` / `tick [path] --topic <nn> --result <pass\|partial\|fail\|skipped> --assistance <none\|hint\|scaffold\|worked_example\|unknown>` | Append evidence event (supports `--objective`, `--assessment-type`, `--attempt-id`, `--now`) and update coverage & review schedule |
| `coverage [path]` / `progress [path]` / `due [path]` | Inspect objective coverage/gaps, honest progress metrics, and prioritized due reviews (read-only) |
| `revise-curriculum [path] ...` | Insert discovered prerequisite node or add/update objective while preserving stable IDs, evidence, and resume state |
| `record-media [path] --objective <id> ...` | Record image/plot provenance without fabricating licenses or verification status |
| `state [path]` / `graph [path]` / `validate-state [path]` | Resume summary / rebuild `00-GRAPH.json` / validate DAG acyclicity, objective refs, and JSON/JSONL |
| `migrate [path]` / `import-legacy <vault> [--target <dir>]` | Idempotently migrate v1 state or legacy note-embedded memory (with backup) without fabricating retention/transfer |
| `flush [path] --topic <nn> [--note "<invariant>"]` | Legacy `[4/4]` completion marker in operational state only (never fabricates retention/transfer) |
| `handoff [path] --request "<req>"` | Build `schema_version: "1.1"` teaching-context envelope for Scriptorium |
| `connect <vault>` / `mode` / `reindex` / `search <vault> --query "<T>"` | Obsidian vault isolation (`.teachme/`) and read-only source search |

## §D. Intent-Based Routing (Lazy-Load ONLY Relevant References)

Classify user intent first:
- **Teaching / conceptual question / practice / review / Feynman:** Teach adaptively, assess, and persist evidence. Do **not** invoke Scriptorium or load `SCRIPTORIUM-HANDOFF.md`. Direct conceptual questions may receive direct answers without a forced closing quiz.
- **Notes-only request** (study notes, study guide, cheat sheet, flashcards, glossary, atomic notes, MOC, `/teachme-distill`): Route directly to Scriptorium via `references/SCRIPTORIUM-HANDOFF.md`. Do **not** force calibration, a lesson, or a checkpoint first.
- **Mixed request** (e.g., *"teach me X, then make revision notes"*): Teach normally. At the requested boundary, persist accurate teaching state, generate the context envelope (`vault_cli.py handoff`), and delegate ONCE via `references/SCRIPTORIUM-HANDOFF.md`. Preserve the resume location.
- **Existing-note expansion** (`/teachme-expand`): Route to Scriptorium (`/scribe-expand`) via `references/SCRIPTORIUM-HANDOFF.md`.
- **Doubt clarification:** Ordinary conceptual doubts during learning -> TeachMe. Explicit `/scribe-doubt <topic> <doubt>` -> Scriptorium's read-only route (never use `/scribe-doubt` to create notes).
- **Ambiguous "summarize":** Brief conversational recap for teaching continuity -> TeachMe in chat (never produce a requested study-summary artifact in chat). Requested reusable revision summary -> Scriptorium (`references/SCRIPTORIUM-HANDOFF.md`). Ask ONE focused question only if the distinction materially affects the action.

| Trigger | Reference to Load | Operational Output |
|---|---|---|
| `/teachme <topic>` calibration, diagnostics & curriculum init (skip intake on `--auto`/`defaults`/`go`) | `references/MISSION-AND-GRILL.md` (+ `RESEARCH-TOOLCHAIN.md` when researching) | `scratchpad/mission.json`, `00-SESSION-STATE.md`, `00-GRAPH.json`, `scratchpad/curriculum.json` |
| Live adaptive teaching, graduated support, assessments & records | `references/RETENTION-AND-RECORDS.md` | `scratchpad/events.jsonl`, `scratchpad/review-state.json`, `learning-records/` |
| When a visual, retrieved image, plot, trace, or small experiment helps an objective | `references/VISUALS-AND-EXPERIMENTS.md` | `scratchpad/media-provenance.json`, optional bounded transient asset |
| Any note/summary/expansion/Scriptorium handoff or retired note command (`/teachme-distill`, `-expand`, `-compare`, `-verify`) | `references/SCRIPTORIUM-HANDOFF.md` *(load ONLY on handoff)* | Context envelope + Scriptorium delegation or blocked handoff |
| `/teachme-vault`, `/teachme-notes-path`, `/teachme-ingest`, `/teachme-review`, `/teachme-feynman`, `/teachme-drill` | `references/cmd-<name>.md` (+ `VAULT-NATIVE.md` if Obsidian) | Corresponding operational state updates |

Space-separated aliases (`/teachme review <topic>`) route identically.
