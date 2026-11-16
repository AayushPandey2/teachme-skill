# `/teachme-ingest <topic> <source>` (also `<source> into <topic>`)

Absorb a PDF, URL, transcript, repo, or notes without overwriting mastered `[x]` checkpoints. Laws: `SKILL.md §B–§C`. Sourcing: `RESEARCH-TOOLCHAIN.md`. Note format: `STUDY-AND-GLOSSARY.md`.

## Steps
1. **Load economically:** `vault_cli.py state` + `graph`. If the vault is missing, run Phases 1–3 (`MISSION-AND-GRILL.md`; defaults on `--auto`). Read `01-RESOURCES.md`, `04-GLOSSARY.md`, and only `L0-L1` slices of related topics.
2. **Extract:** parse the source into `scratchpad/raw-research.md`; pull every claim, mechanism, benchmark, and equation with dual deep-link citations and Formula Anatomy.
3. **Merge non-destructively:** add the source under `## Knowledge` or `## Wisdom`; merge into `02-DEEP-RESEARCH.md` and `03-CORNELL-STUDY-GUIDE.md`; add glossary terms (`1–2` sentences + `_Avoid_:`).
4. **New subtopics:** append to `scratchpad/subtopics.json`, re-run `vault_cli.py init … --subtopics`, then write each file through the 7-Point Critic Gate.
5. **Contradictions:** log conflicts under `## Contradictions & Version Deltas` (`> [!WARNING]`) in `02-DEEP-RESEARCH.md` and report them in chat.
6. **Gate:** `graph` → `fix` → `verify` until `errors: []`.
