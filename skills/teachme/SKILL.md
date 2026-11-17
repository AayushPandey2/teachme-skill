---
name: teachme
description: "Interactive first-principles teaching, learner calibration, Socratic coaching, spaced-repetition review, and durable learning-state tracking. Invoke with /teachme <topic> or when the user asks to learn, practice, review, or be quizzed on any topic. Delegates study-note, cheat-sheet, flashcard, and summary artifact creation to Scriptorium."
---

# `/teachme` Master Router & Core Laws

This file is the **single source of truth** for TeachMe's teaching invariants, operational learning-state paths, intent routing, and CLI laws. Reference files cite `SKILL.md §A–§D`.

## §A. Learning-State Root & Operating Mode Resolution
TeachMe persists **operational learning state only** (never study notes) in two compatible modes configured via `~/.teachme-config.json`:
1. **Standalone Mode:** `<STATE_ROOT>` = `notes_root` in `~/.teachme-config.json` (fallback `~/notes`). Session state lives at `<STATE_ROOT>/<topic-slug>/` (`00-SESSION-STATE.md`, `00-GRAPH.json`, `learning-records/`, `scratchpad/`).
2. **Vault-Native Mode (Existing Obsidian Vault):** Activated when `.obsidian/` is detected, `mode` is `vault-native`, or `obsidian_vault` is connected via `/teachme-vault connect`. Isolated state lives at `<vault>/.teachme/sessions/<topic-slug>/` (or configured `--state-dir`). Existing vault notes are **read-only learning sources only**.
- Scriptorium's study-note vault (`SCRIPTORIUM_VAULT_PATH` or `~/.scriptorium-config.json`) is completely independent; never substitute TeachMe's `notes_root` or `.teachme/` as Scriptorium's vault.
- If `<topic>` is omitted, run `vault_cli.py state` to auto-select the active session, or ask ONE clarifying question.

## §B. Teaching, Memory & Non-Destructive Invariants
1. **Teaching & Memory Only:** TeachMe owns interactive teaching, calibration, curriculum dependency planning, Socratic questioning, worked examples, live drills, Feynman checks, spaced review, checkpoints, and `learning-records/`.
2. **No Study-Note Generation:** TeachMe must NEVER create, expand, format, tag, link-repair, or write study notes, study guides, cheat sheets, flashcards, glossaries, atomic Zettelkasten cards, MOCs, or requested study-summary artifacts (not even in chat as a fallback if Scriptorium is unavailable).
3. **Existing Notes Are Read-Only:** Never modify, rename, reformat, or delete user notes or legacy study-note files. `flush` updates operational state (`00-GRAPH.json`, `00-SESSION-STATE.md`, `scratchpad/curriculum.json`) only.
4. **Accurate Evidence:** Never fabricate mastery scores, checkpoint passes, examples, or citations. Note generation/completion NEVER counts as mastery evidence.
5. **Math & Clarity in Chat:** When explaining formulas in chat, define every symbol before use (`Formula Anatomy`), use clean `$...$` / `$$...$$` delimiters, and state any unverified claim explicitly.

## §C. Operational State CLI (`scripts/vault_cli.py`, Python 3 stdlib)
Resolve the script at `../teachme/scripts/vault_cli.py` or `~/.gemini/antigravity/skills/teachme/scripts/vault_cli.py`.

| Call | Use |
|---|---|
| `init <path> --topic "<T>" --subtopics <file.json>` | Initialize operational state only (`00-SESSION-STATE.md`, `00-GRAPH.json`, `learning-records/`, `scratchpad/curriculum.json`) |
| `context [path] --topic <nn>` | Per-turn load: state + curriculum node + queue + recent events + active learning records + 1-hop neighbors |
| `state [path]` / `graph [path]` | Resume pointer / rebuild curriculum dependency `00-GRAPH.json` |
| `tick [path] --topic <nn> --cp <1-4> --status <pass\|retry>` | Append checkpoint evidence to `scratchpad/events.jsonl` and update operational state |
| `flush [path] --topic <nn> --note "<invariant>"` | Persist `[4/4]` mastery into operational state only (never mutates study notes) |
| `validate-state [path]` | Validate operational state files (`00-SESSION-STATE.md` `<60` lines, DAG acyclicity, JSONL) |
| `import-legacy <vault> [--target <dir>]` | Non-destructively import legacy note-embedded memory into operational state |
| `handoff [path] --request "<req>"` | Build versioned teaching-context JSON envelope for Scriptorium |
| `connect <vault>` / `mode` / `reindex` / `search <vault> --query "<T>"` | Connect Obsidian vault for isolated `.teachme/` state and read-only source search |

## §D. Intent-Based Routing (Load ONLY the Listed File)

Classify user intent first:
- **Teaching request** (`/teachme <topic>`, explanations, live practice, review, Feynman): Teach, adapt, assess, and persist learning state. Do **not** invoke Scriptorium or load `SCRIPTORIUM-HANDOFF.md`.
- **Notes-only request** (create study notes, study guide, cheat sheet, flashcards, glossary, atomic notes, MOC, or `/teachme-distill`): Route directly to Scriptorium via `references/SCRIPTORIUM-HANDOFF.md`. Do **not** force calibration, a lesson, or a checkpoint first.
- **Mixed request** (e.g., *"teach me X, then make revision notes"*): Teach normally. At the requested boundary, persist accurate teaching state (`tick`/`flush` as earned), generate the context envelope (`vault_cli.py handoff`), and delegate ONCE via `references/SCRIPTORIUM-HANDOFF.md`. Preserve the exact lesson/checkpoint for later resumption.
- **Existing-note expansion** (expand/enrich existing notes, or `/teachme-expand`): Route to Scriptorium (`/scribe-expand`) via `references/SCRIPTORIUM-HANDOFF.md`.
- **Doubt clarification**: Ordinary conceptual questions during learning -> TeachMe. Explicit `/scribe-doubt <topic> <doubt>` -> Scriptorium's read-only route (never use `/scribe-doubt` to create notes).
- **Ambiguous "summarize"**: A brief conversational recap for teaching continuity -> TeachMe in chat (never produce a requested study-summary artifact in chat). A requested revision summary or reusable study artifact -> Scriptorium (`references/SCRIPTORIUM-HANDOFF.md`). Ask ONE focused question only if the distinction materially affects the action.

| Trigger | Reference to Load | Operational Output |
|---|---|---|
| `/teachme <topic>` Phases 1–3 (calibration, research, curriculum `init`; skip grilling on `--auto`/`defaults`/`go`) | `references/MISSION-AND-GRILL.md` (+ `RESEARCH-TOOLCHAIN.md` in Phase 2) | `scratchpad/mission.json`, `00-SESSION-STATE.md`, `00-GRAPH.json`, `scratchpad/curriculum.json` |
| Phase 4 live Socratic coaching & pedagogy | `references/RETENTION-AND-RECORDS.md` | `scratchpad/events.jsonl`, `learning-records/` |
| Any note/summary/expansion/Scriptorium handoff or legacy note command (`/teachme-distill`, `-expand`, `-compare`, `-verify`) | `references/SCRIPTORIUM-HANDOFF.md` *(load ONLY on handoff)* | Context envelope + Scriptorium delegation or blocked handoff |
| `/teachme-vault <connect\|mode\|search\|reindex\|state>` | `references/cmd-vault.md` (+ `VAULT-NATIVE.md` for isolation rules) | `~/.teachme-config.json`, `<vault>/.teachme/` |
| `/teachme-notes-path [path\|reset]` | `references/cmd-notes-path.md` | `~/.teachme-config.json` |
| `/teachme-ingest <topic> <source>` | `references/cmd-ingest.md` | `scratchpad/ingested-sources.json`, `curriculum.json`, `learning-records/` |
| `/teachme-review <topic>` | `references/cmd-review.md` | `scratchpad/events.jsonl`, `learning-records/` |
| `/teachme-feynman <concept>` | `references/cmd-feynman.md` | `learning-records/`, `events.jsonl` |
| `/teachme-drill <topic> [1\|2\|3]` | `references/cmd-drill.md` | `scratchpad/events.jsonl`, `learning-records/` |

Space-separated aliases (`/teachme review <topic>`) route identically.
