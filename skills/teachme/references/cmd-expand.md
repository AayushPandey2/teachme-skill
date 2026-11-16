# `/teachme-expand <topic>`

Deepen shallow notes to the 7-Section Blueprint and add missing subtopics, never touching `[x]` progress or `learning-records/`. Laws: `SKILL.md §B–§C`. Blueprint + Critic Gate: `STUDY-AND-GLOSSARY.md §2–§3`.

## Steps
1. **Discover (zero tokens):** `vault_cli.py state`, `graph`, `verify`. Flagged `missing_section_marker`, `non_sequential_section_numbers`, or missing tables = shallow file.
2. **Gap audit:** read `00-MISSION.md`, `01-RESOURCES.md`, `00-MOC-INDEX.md`, and only `slice --section L0-L1` of each topic to find missing prerequisites or related subtopics.
3. **Deepen in place:** open each flagged topic individually and fill it to `§2`; partition `atomic/` cards with the 5 markers.
4. **Add new subtopics:** append them to `scratchpad/subtopics.json` and re-run `vault_cli.py init … --subtopics` (creates only missing stubs + MOC/graph entries), then write each file; update `02`, `03`, `04`, `06` as needed.
5. **Gate:** pass the 7-Point Critic Gate per file, then `graph` → `fix` → `verify` until `errors: []`.
6. **Report:** list deepened vs. newly created files.
