# Full `/teachme` 6-Phase Execution Pipeline

Execute these 6 phases sequentially inside `<VAULT_ROOT>/<topic-slug>/` (resolved via `~/.teachme-config.json` -> `notes_root`, default `~/notes`):

### Phase 1: Frontier Grilling & Mission Lock (`references/MISSION-AND-GRILL.md`)
1. Read `references/MISSION-AND-GRILL.md`.
2. Unless `--auto` / `defaults` / `go` was passed, ask the **4 numbered `❓` questions** with `➡️` defaults (`No prior knowledge`, `Absolute mastery covering all topics`, `Complete first-principles mastery`, `None`) and wait.
3. Write `<VAULT_ROOT>/<topic-slug>/00-MISSION.md`.

### Phase 2: Primary-Source Research & Exhaustive Syllabus (`references/RESEARCH-TOOLCHAIN.md`)
1. Read `references/RESEARCH-TOOLCHAIN.md`.
2. Formulate a falsifiable Research Brief, decompose the subject into an exhaustive numbered syllabus (no caps/merges), and capture raw drafts in `scratchpad/raw-research.md`.
3. Write `01-RESOURCES.md` (**Knowledge** vs. **Wisdom**, Exhaustive Syllabus, Gaps) and `02-DEEP-RESEARCH.md` (inline `[Source]` citations, benchmarks, failure modes, Formula Anatomy Breakdowns).

### Phase 3: Mental Models, Glossary & Derivations (`references/phase3-models-glossary.md`)
1. Read `references/phase3-models-glossary.md`; draft rough algebra in `scratchpad/derivation-drafts.md`.
2. Write `05-MENTAL-MODELS.md`, `04-GLOSSARY.md` (1–2 sentence definitions + `_Avoid_:`), and `06-DERIVATIONS-AND-PROOFS.md`.

### Phase 4: Scaffolding, 8-Block Subtopic Notes, Cornell Guide & Flashcards
1. Run `scripts/vault_cli.py init <VAULT_PATH> --title "<Topic>" --topics <01-slug,02-slug,...>` to scaffold `00-SESSION-STATE.md`, `00-MOC-INDEX.md`, `00-GRAPH.json`, and `scratchpad/`.
2. Read `references/subtopic-8block.md` and generate `<VAULT_PATH>/topics/<nn>-<subtopic-slug>.md` for every syllabus subtopic, passing the **7-Point Writer -> Critic Audit** before saving each file.
3. Read `references/phase4-5-moc-cards.md` and write `03-CORNELL-STUDY-GUIDE.md`, enrich `00-MOC-INDEX.md` (Mermaid + ASCII prereq graph), and write `08-FLASHCARDS.md`.
4. Run `scripts/vault_cli.py graph <VAULT_PATH>` and `scripts/vault_cli.py verify <VAULT_PATH>` until `errors` is empty.

### Phase 5: Atomic Zettelkasten Cards (`references/phase4-5-moc-cards.md` §4)
1. Extract 150–300 word `atomic/<concept-slug>.md` cards partitioned with `L1-ANCHOR`..`L5-WORKBOOK-AND-GRAPH` markers and linked via `[[wikilinks]]`.

### Phase 6: Progressive 7-Component Mastery Loop (`references/RETENTION-AND-RECORDS.md`)
1. Read `references/RETENTION-AND-RECORDS.md` and run `scripts/vault_cli.py state` + `graph` on resume.
2. Follow Law 12 (**Spreading-Activation 1-Hop Context**, `scratchpad/queue-<nn>.json`, `vault_cli.py tick`, and `vault_cli.py flush` on `[4/4]`).
3. Teach each lesson across **3 Escalating Depth Turns** (`1/3`, `2/3`, `3/3`) and **4 Sequential Checkpoints** (`[1/4]`–`[4/4]`), honoring **Anti-Spoiler**, **`wait-what`**, **Interleaved Recall** (Lesson 3, 5, 7...), and **Auto-Compaction** (every 3 subtopics).
