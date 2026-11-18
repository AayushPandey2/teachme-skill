# `/teachme-ingest <topic> <source>` (also `<source> into <topic>`)

Absorb a PDF, URL, transcript, repo, or existing notes into TeachMe's **lesson context and curriculum state** without modifying study notes or overwriting mastered `[x]` checkpoints. Laws: `SKILL.md §A–§D`. Sourcing: `RESEARCH-TOOLCHAIN.md`.

## Steps
1. **Load Existing State:**
   - Run `vault_cli.py state` (or initialize a new minimal operational session via `MISSION-AND-GRILL.md` if none exists).
   - Inspect `00-GRAPH.json`, `scratchpad/curriculum.json`, and `learning-records/`. When a vault is registered, `vault_cli.py resolve-sources --topic "<topic>"` inspects existing notes read-only.
2. **Extract for Teaching:** Extract key concepts, claims, equations, and compact source provenance (`title`, `url`, `type`, `retrieved_at`, `claims_or_topics`) into `scratchpad/ingested-sources.json` (lazy-create `scratchpad/raw-research.md` only when bulky external dump retention is explicitly needed).
3. **Update Curriculum State Non-Destructively:**
   - If the source introduces new subtopics or prerequisites, append them to `scratchpad/subtopics.json` and re-run `vault_cli.py init` (or `revise-curriculum`), preserving all existing mastered `[x]` checkpoints and evidence.
   - Never merge content into `01-RESOURCES.md`, `02-DEEP-RESEARCH.md`, `03-CORNELL-STUDY-GUIDE.md`, `04-GLOSSARY.md`, or any study notes. (If the user explicitly asks to create or update persistent study notes from the source, offer an optional handoff via `references/NOTE-SKILL-HANDOFF.md`.)
4. **Contradictions:** Log notable conflicts or version deltas against prior curriculum expectations in `learning-records/000N-<slug>.md` and report them in chat.
5. **Validate State:** Run `vault_cli.py validate-state`.
