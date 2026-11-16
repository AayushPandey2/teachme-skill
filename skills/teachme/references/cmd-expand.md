# Command: `/teachme-expand <topic>` *(alias: `/teachme expand <topic>`)*

Deepen shallow notes in `<VAULT_ROOT>/<topic-slug>/` to the **8-Block Subtopic Standard** (`references/subtopic-8block.md`) and add missing subtopics without deleting existing `[x]` progress or `learning-records/`.

## Execution Sequence (Token-Efficient)
1. **Zero-Token Discovery:**
   - Run `vault_cli.py state <VAULT_PATH>` and `vault_cli.py graph <VAULT_PATH>` (reads `00-SESSION-STATE.md` and builds `00-GRAPH.json`).
   - Run `vault_cli.py verify <VAULT_PATH>` to detect missing `L1`–`L5` section markers, broken typed edges, or shallow files.
   - If `00-SESSION-STATE.md` or `scratchpad/` is missing, create them (`00-SESSION-STATE.md` strictly `<60` lines).
2. **Targeted Gap & Depth Audit:**
   - Load `00-MISSION.md`, `01-RESOURCES.md`, `00-MOC-INDEX.md`, and ONLY `--section L0-L1` of `topics/*.md` via `vault_cli.py slice` to spot missing prerequisites, missing related subtopics, or incomplete 8-Block files.
   - For any shallow `topics/*.md` file flagged, load it individually to upgrade in place.
3. **Deepen & Generate (8-Block Standard + 6-Point Audit):**
   - Upgrade shallow `topics/*.md` files to full **7-Section / 8-Block Standard** compliance (`## 1.`–`## 7.` learner-centric headings, `L1-ANCHOR`..`L5-WORKBOOK-AND-GRAPH` HTML markers, Contrastive "Is vs. Is Not" table, Input-to-Output Behavior Table, zero-skip Proof, 10–18 line Python/NumPy `assert` verification snippet, `I Do -> We Do -> You Do` Drills A & B, Section 7 Misconceptions + Bridge + clickable `[[wikilinks]]` + `Primary Sources & Deep Links` table).
   - Partition `atomic/*.md` cards with `L1-ANCHOR`..`L5-WORKBOOK-AND-GRAPH` markers.
   - Generate new `topics/<nn>-<slug>.md` and `atomic/<slug>.md` files for uncovered subtopics; update `02-DEEP-RESEARCH.md`, `03-CORNELL-STUDY-GUIDE.md`, `04-GLOSSARY.md`, `06-DERIVATIONS-AND-PROOFS.md`.
   - Pass ALL **8 Points of the Writer -> Critic Audit** (`subtopic-8block.md` §4, including Check #8 Primary-Source Deep-Link Verification) and the **Global `<details>` Block Law & Math Delimiter Law** (`SKILL.md` §9–10: column-0 blank-line-padded `<details>` blocks, `100%` `$...$`/`$$...$$` math coverage) before saving each `topics/*.md` file.
4. **Refresh Graph & Verify:**
   - Update `00-MOC-INDEX.md` (preserving `[x]` checkmarks) and run `vault_cli.py graph <VAULT_PATH>`, `vault_cli.py fix <VAULT_PATH>` (if needed), and `vault_cli.py verify <VAULT_PATH>` until `errors` is empty.
   - Print a concise summary of deepened and newly created files.
