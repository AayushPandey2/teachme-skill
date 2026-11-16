# Command: `/teachme-ingest <topic> <source>` *(aliases: `/teachme ingest <source> into <topic>`)*

Absorb a new PDF, URL, transcript, repo, or raw notes into `<VAULT_ROOT>/<topic-slug>/` without overwriting mastered `[x]` checkpoints.

## Execution Sequence
1. **Load State & Context Economically:**
   - Run `vault_cli.py state <VAULT_PATH>` and `vault_cli.py graph <VAULT_PATH>`.
   - If the vault does not exist yet, initialize it first (Phase 1 defaults if `--auto`, or quick Mission Lock).
   - Read `01-RESOURCES.md`, `04-GLOSSARY.md`, and ONLY `L0-L1` slices (`vault_cli.py slice ... --section L0-L1`) of related existing `topics/*.md` files.
2. **Extract & Verify Claims:**
   - Parse `<source>` (write raw extraction notes to `scratchpad/raw-research.md` first).
   - Extract every new claim, mechanism, benchmark, and equation with inline `[Source]` citations and full **Formula Anatomy Breakdowns** (`subtopic-8block.md` §1).
3. **Non-Destructive Vault Merge:**
   - Append the source under `## Knowledge` or `## Wisdom` in `01-RESOURCES.md`.
   - Merge findings into `02-DEEP-RESEARCH.md` and `03-CORNELL-STUDY-GUIDE.md`, and add new canonical terms (`1–2` sentences + `_Avoid_:`) to `04-GLOSSARY.md`.
   - Create **8-Block Standard** `topics/<nn>-<slug>.md` files (passing the 6-Point Writer -> Critic Audit) for any newly uncovered subtopics, register them in `00-MOC-INDEX.md`, and update `00-SESSION-STATE.md` (`<60` lines) **preserving all existing `[x]` checkpoints**.
4. **Contradiction Detection & Verification:**
   - Flag any conflicts with existing notes under `## Contradictions & Version Deltas` (`> [!WARNING]`) in `02-DEEP-RESEARCH.md` and report them in chat.
   - Run `vault_cli.py graph <VAULT_PATH>` and `vault_cli.py verify <VAULT_PATH>` to confirm zero broken links/LaTeX.
