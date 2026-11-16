# Command: `/teachme-review <topic>` *(alias: `/teachme review <topic>`)*

Launch an interleaved spaced-repetition Socratic coaching session targeting weak spots or unchecked subtopics in `<VAULT_ROOT>/<topic-slug>/` without regenerating vault notes.

## Execution Sequence (1-Hop Context + Delta Ticking)
1. **Zero-Token State & Weak-Spot Lookup:**
   - Run `vault_cli.py state <VAULT_PATH>` and `vault_cli.py graph <VAULT_PATH>`.
   - Inspect `learning-records/` titles/latest entries and `00-GRAPH.json` to pick the highest-priority unchecked (`status != mastered`) or previously struggled subtopic in topological order.
2. **Spreading-Activation 1-Hop Load:**
   - Load ONLY `--section L0-L1` (~25 lines) of immediate `depends_on` and `contrasts_with` 1-hop neighbors via `vault_cli.py slice`.
   - Slice ONLY the active subtopic's relevant section (`L1-ANCHOR`/`L2-PREREQS-AND-MOTIVATION`, `L3-FOUR-LAYER-THEORY`/`L4-DERIVATION-AND-CODE`, or `L5-WORKBOOK-AND-GRAPH`).
3. **Interactive Coaching (`I Do / We Do / You Do` + Anti-Spoiler):**
   - Follow `RETENTION-AND-RECORDS.md` (§2–3): brief plain-English + Formula Anatomy recap, then 1 question per turn (`We Do` -> `You Do` -> Edge-Case + Feynman Gate).
   - Never reveal the answer on `"idk"`, `"explain"`, or error—drop down to a 1-number micro-step.
   - On Checkpoints `1`–`3`, record progress solely via `vault_cli.py tick <VAULT_PATH> --topic <nn> --cp <1..3> --status <pass|retry>`.
4. **Batch Flush on Mastery:**
   - Only upon passing Checkpoint `[4/4]`, run `vault_cli.py tick ... --cp 4 --status pass` and `vault_cli.py flush <VAULT_PATH> --topic <nn> --note "<verified invariant>"`, and log breakthroughs in `learning-records/000N-<slug>.md`.
