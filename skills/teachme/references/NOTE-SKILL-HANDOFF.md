# Optional External Note-Skill Handoff Contract

Load this reference **only** when the user explicitly requests persistent reusable study notes, study guides, cheat sheets, flashcards, glossaries, atomic notes, MOCs, or note expansion/verification.
**TeachMe must NEVER detect or invoke a note-generation skill during normal teaching, conceptual Q&A, practice, review, or transient teaching visuals (`VISUALS-AND-EXPERIMENTS.md`).**

## §1. Fundamental Separation & Provider Independence
- **TeachMe teaches. Other skills write notes.**
- TeachMe owns interactive teaching, source resolution (`vault` / `hybrid` / `web`), calibration, diagnostics, objective coverage, assessment evidence, review scheduling, and `learning-records/`.
- External note-writing skills (provider-independent — no specific skill such as Scriptorium is required or assumed) own creating, expanding, organizing, formatting, linking, and validating persistent study-note artifacts.
- TeachMe never creates study notes, deep research notes, chapter notes, revision notes, summaries, or glossaries itself — **not even as a fallback in chat or files when no note-writing skill is installed**.

## §2. Legacy Retired Note Commands
If the user invokes a retired note-generation command (`/teachme-distill`, `/teachme-expand`, `/teachme-verify` for study notes, or `/teachme-compare` requesting a written artifact):
- For interactive comparison (`/teachme-compare <A> vs <B>`), teach/contrast directly in `/teachme`.
- For TeachMe operational state validation (`/teachme-verify` on state), run `vault_cli.py validate-state`.
- For persistent study-note creation, expansion, or note-formatting verification, follow §3–§4 below using an installed compatible note-writing skill if available.

## §3. Versioned Teaching-Context Envelope (`schema_version: "1.1"`, compatible with `"1.0"`)
On an explicit persistent-notes or mixed request (after finishing the requested teaching boundary and persisting TeachMe state via `assess`/`tick`/`flush`), generate the compact learning-context envelope:

```bash
python vault_cli.py handoff [<session_or_vault>] [--topic <nn>] --request "<user request>" --scope "<scope>" [--request-id "<id>"] [--destination "<dest>"]
```

**Envelope Rules:**
1. Exports concise, evidence-backed fields: `agreed_scope`, `concepts_introduced`, `objectives_demonstrated` (with separate `retention_status` and `transfer_status`), `untested_or_unresolved_gaps`, `misconceptions_and_corrections`, `source_provenance`, `media_provenance`, evidenced `learner_profile` preferences, and `resume_location` (plus backward-compatible v1.0 fields `concepts_taught`, `concepts_planned`, `unresolved_topics`, `mastery_claims`, `resume_checkpoint`).
2. Never describe `introduced` or `practiced_with_support` content as `mastered`; keep `mastery_claims` strictly evidence-backed (`"unknown"` where unassessed).
3. Never export full chat transcripts, credentials, or fabricated licenses/verification statuses.
4. Keep the envelope ephemeral in active agent context by default (`--persist` writes only to `scratchpad/handoffs/<request_id>.json`, never to a study-note directory).

## §4. Optional Discovery, Instruction-Level Handoff & Unavailable Fallbacks
1. **Discover Compatible Note-Writing Skill (Only on Explicit Note Request):** Inspect only the active host's available skill registry or standard installed skill directories (e.g., `~/.gemini/antigravity/skills/`, `~/.gemini/config/skills/`, `~/.agents/skills/`, `~/.claude/skills/`) for a compatible installed note-writing skill. Never auto-download/install skills, spawn external agent processes, or require any specific provider.
2. **Offer/Execute Instruction-Level Handoff Once:** Pass the compact `vault_cli.py handoff` context envelope in the instruction-level handoff to the discovered compatible skill without inventing CLI flags or unsupported capabilities. Preserve TeachMe's resume location and never re-enter `/teachme` teaching while the note skill executes.
3. **If No Compatible Note-Writing Skill Is Installed (or Target Vault Is Unconfigured):**
   - Retain all TeachMe operational learning state accurately; do **not** advance mastery.
   - Return a concise **Blocked / Unavailable Note Handoff** stating: (a) no compatible note-writing skill is currently available (or its target vault is unconfigured), (b) the compact learning-context summary (`handoff` envelope highlights: demonstrated objectives, introduced concepts, gaps, misconceptions, and source provenance) so the user can hand it to any note tool later, and (c) what configuration/skill is needed.
   - **Prohibited Fallback:** Never generate study notes, revision notes, cheat sheets, or study summaries in chat or on disk as a substitute.
4. **Failure & Retry:** On failure, preserve TeachMe's resume location and report the handoff as failed/blocked. Reuse the same `request_id` on retry. Note generation NEVER advances TeachMe mastery.
