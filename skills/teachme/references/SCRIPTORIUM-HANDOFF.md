# Scriptorium Handoff & Note Delegation Contract

Load this reference **only** when the user requests reusable study notes, study summaries, cheat sheets, flashcards, glossaries, atomic notes, MOCs, note expansion, `/scribe-*`, or a retired TeachMe note command. Do **not** route ordinary conceptual explanations or transient live teaching plots/experiments (`VISUALS-AND-EXPERIMENTS.md`) to Scriptorium.

## §1. Role Boundary & Inspected Scriptorium Contract
- **TeachMe owns:** live explanations, transient teaching visuals/experiments, interactive practice, diagnostics, objective coverage, assessment evidence, review scheduling, misconception records, and `learning-records/`.
- **Scriptorium owns:** creating, expanding, organizing, formatting, linking, and validating reusable study artifacts (`/scribe-notes`, `/scribe-expand`, `/scribe-doubt`, `scripts/vault_index.py`, `scripts/verify_vault_notes.py`).
- **Supported Scriptorium Commands (Instruction-Level Contract):**
  - `/scribe-notes <topic>` — Primary-source research, acyclic DAG, 7-section note generation, and automated+semantic verification.
  - `/scribe-expand <topic name>` — Index-first gap analysis and incremental creation/patching of missing subtopics.
  - `/scribe-doubt <topic name> <doubt>` — Strictly **read-only** Q&A grounded in 1–3 indexed notes with `[[Note Title]]` citations. Never use `/scribe-doubt` to create or modify notes.
- **Vault Resolution:** Scriptorium resolves its target Obsidian vault from explicit argument, `SCRIPTORIUM_VAULT_PATH`, or `~/.scriptorium-config.json` (`{"vault_path": "..."}`). Never pass TeachMe's `notes_root` or `.teachme/` state folder as Scriptorium's vault; ask the user for a destination only when Scriptorium's workflow requires one and none is configured.
- **Known Interface Limitation:** Scriptorium has no CLI context-import flag and no machine-readable completion API. Handoff passes an instruction-level context envelope in the active agent context, and completion paths are only reported if directly observed in tool output.

## §2. Legacy TeachMe Command Redirects
- `/teachme-distill <topic>` -> Route to Scriptorium `/scribe-notes <topic>` (or `/scribe-expand <topic>` if notes already exist).
- `/teachme-expand <topic>` -> Route to Scriptorium `/scribe-expand <topic>`.
- `/teachme-compare <A> vs <B>` -> If asking to learn/contrast interactively, handle in `/teachme`; if asking for a written comparison artifact, route to Scriptorium `/scribe-notes "<A> vs <B>"`.
- `/teachme-verify <topic>` -> For study-note formatting/link verification, route to Scriptorium (`scripts/verify_vault_notes.py "<vault_path>" [--fix]`). For TeachMe learning-state checks, run `vault_cli.py validate-state`.

## §3. Versioned Teaching-Context Envelope (`schema_version: "1.1"`, compatible with `"1.0"`)
When delegating after teaching (or a mixed request), persist TeachMe state first (`assess`/`tick`/`flush` as earned), then generate the compact envelope:

```bash
python vault_cli.py handoff [<session_or_vault>] [--topic <nn>] --request "<user request>" --scope "<scope>" [--request-id "<id>"] [--destination "<dest>"]
```

**Envelope Contents & Rules:**
1. Exports concise: `agreed_scope`, `concepts_introduced`, `objectives_demonstrated` (with separate `retention_status` and `transfer_status`), `untested_or_unresolved_gaps`, `misconceptions_and_corrections`, `source_provenance`, `media_provenance`, evidenced `learner_profile` preferences, and `resume_location` (plus backward-compatible v1.0 fields `concepts_taught`, `concepts_planned`, `unresolved_topics`, `mastery_claims`, `resume_checkpoint`).
2. Never describe `introduced` or `practiced_with_support` content as `mastered`; keep `mastery_claims` strictly evidence-backed (`"unknown"` where unassessed).
3. Never export full chat transcripts, full memory dumps, credentials, or fabricated media licenses/verification status.
4. Keep the envelope ephemeral in active agent context by default (`--persist` writes to `scratchpad/handoffs/<request_id>.json`, never to a note directory). Never invent Scriptorium CLI flags to consume it.

## §4. Host Resolution, Execution & Fallbacks
1. **Resolve Scriptorium (Read-Only):** Check the active skill registry or standard installed skill locations (`~/.gemini/antigravity/skills/scriptorium/SKILL.md`, `~/.gemini/config/skills/scriptorium/SKILL.md`, `~/.agents/skills/scriptorium/SKILL.md`, `~/.claude/skills/scriptorium/SKILL.md`). Never auto-download/install skills or spawn external `agy` processes at runtime.
2. **Delegate Once:** Invoke `scriptorium` with the selected `/scribe-*` intent and the context envelope (or load `scriptorium/SKILL.md` if permitted). Never re-enter `/teachme` teaching while running Scriptorium's note workflow.
3. **If Scriptorium Is Unavailable or Vault Is Unconfigured:**
   - Retain all accurate TeachMe state; do **not** advance mastery.
   - Return a concise **Blocked Handoff** stating: (a) the exact Scriptorium command (`/scribe-notes <topic>`, `/scribe-expand <topic>`, or `/scribe-doubt <topic> <doubt>`), (b) how to configure Scriptorium's vault (`SCRIPTORIUM_VAULT_PATH` or `~/.scriptorium-config.json`), and (c) the compact context summary for manual continuation.
   - **Prohibited Fallback:** Never generate a requested study-note or study-summary artifact in chat as a substitute for unavailable Scriptorium.
4. **Failure & Retry:** On failure, preserve TeachMe's resume location and report the handoff as failed/blocked. On retry, reuse the same `request_id`. Note completion NEVER advances TeachMe mastery.
