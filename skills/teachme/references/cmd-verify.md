# Command: `/teachme-verify <topic>` *(aliases: `/teachme verify`, `/teachme audit`)*

Run a deterministic, zero-token multi-pass integrity sweep across `<VAULT_ROOT>/<topic-slug>/` and auto-repair only the exact lines/files flagged until zero errors remain.

## Execution Sequence (CLI-Backed Auto-Repair)
1. **Zero-Token Scan (Pass 1):**
   - Run `vault_cli.py graph <VAULT_PATH>` (refreshes `00-GRAPH.json`) and `vault_cli.py verify <VAULT_PATH>`.
   - Inspect ONLY the compact JSON `errors` and `warnings` arrays (`file`, `line`, `type`, `detail`). **Do NOT burn tokens reading clean files.**
   - Also check `00-SESSION-STATE.md` exists (`<60` lines) and `scratchpad/` exists.
2. **Targeted Auto-Repair (Only Flagged Files/Lines):**
   - **`backtick_latex`:** Strip outer code backticks around `$` / `$$` math.
   - **`table_pipe_in_math`:** Replace raw `|` inside table math with `\mid`, `\lvert`, `\rvert`, `\lVert`, or `\rVert`.
   - **`unmatched_dollar` / `unclosed_display_math`:** Fix unclosed `$` / `$$` or stray currency `$` collisions.
   - **`broken_wikilink` / `broken_md_link` / `broken_anchor` / `placeholder_wikilink` / `broken_typed_edge`:** Strip stray `.md` inside wikilinks, resolve slug/case mismatches, replace `[[none]]` with `[]`, fix `depends_on` / `unlocks` / `contrasts_with` / `fixes_failure_of`, or generate missing target `.md` files if clearly required by the syllabus.
   - **`missing_section_marker` / Missing 8-Block Items:** Slice or inspect the flagged `topics/*.md` or `atomic/*.md` file and repair missing `L1-ANCHOR`..`L5-WORKBOOK-AND-GRAPH` markers, duplicate section numbers (`duplicate_section_number`), unlinked Section 8 paths (`unlinked_graph_path`), or 8-Point Writer -> Critic items (`subtopic-8block.md` §4).
   - **`bare_latex_command` / `latex_trailing_space`:** Wrap bare `\theta`, `\sum`, etc. in `$...$` and strip spaces before closing `$`.
   - **`missing_primary_sources_table` / `missing_primary_source_deep_link`:** Add Section 8 `Primary Sources & Deep Links` table with clickable `https://` direct URLs + valid `[[01-RESOURCES#...]]` / `[[02-DEEP-RESEARCH#...]]` anchors.
   - **`orphan_file`:** Register unlisted `topics/*.md` or `atomic/*.md` files in `00-MOC-INDEX.md` and `00-SESSION-STATE.md`.
   - **Glossary & Formula Anatomy Check:** Ensure canonical terms align with `04-GLOSSARY.md` and display equations in `02-DEEP-RESEARCH.md`, `03-CORNELL-STUDY-GUIDE.md`, and `topics/*.md` have complete Formula Anatomy breakdowns.
3. **Re-Verification Loop:**
   - Re-run `vault_cli.py graph <VAULT_PATH>` and `vault_cli.py verify <VAULT_PATH>` until `errors` = `[]` and `orphans` = `0`.
   - Output a compact verification report table (`File | Links Fixed | Formulas Fixed | 8-Block | Status`).
