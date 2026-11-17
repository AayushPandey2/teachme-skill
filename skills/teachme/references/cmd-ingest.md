# `/teachme-ingest <topic> <source>` (also `<source> into <topic>`)

Absorb a PDF, URL, transcript, repo, or existing notes into TeachMe's **lesson context and curriculum state** without modifying study notes or overwriting mastered `[x]` checkpoints. Laws: `SKILL.md §A–§D`. Sourcing: `RESEARCH-TOOLCHAIN.md`.

## Steps
1. **Load Existing State:**
   - Run `vault_cli.py state` (or initialize a new operational session via `MISSION-AND-GRILL.md` if none exists).
   - Inspect `00-GRAPH.json`, `scratchpad/curriculum.json`, and `learning-records/`. In Vault-Native Mode, optional `vault_cli.py search <vault> --query "<topic>"` can inspect existing notes read-only.
2. **Extract for Teaching:** Parse the source into `scratchpad/raw-research.md`; extract key concepts, claims, equations, and source provenance (`title`, `url`, `type`, `retrieved_at`) into `scratchpad/ingested-sources.json`.
3. **Update Curriculum State Non-Destructively:**
   - If the source introduces new subtopics or prerequisites, append them to `scratchpad/subtopics.json` and re-run `vault_cli.py init` (preserves all existing mastered `[x]` checkpoints and progress).
   - Never merge content into `01-RESOURCES.md`, `02-DEEP-RESEARCH.md`, `03-CORNELL-STUDY-GUIDE.md`, `04-GLOSSARY.md`, or any study notes. (If the user asks to create or update study notes from the source, delegate to Scriptorium via `references/SCRIPTORIUM-HANDOFF.md`.)
4. **Contradictions:** Log any conflicts or version deltas against prior curriculum expectations in `learning-records/000N-<slug>.md` and report them in chat.
5. **Validate State:** Run `vault_cli.py validate-state`.
