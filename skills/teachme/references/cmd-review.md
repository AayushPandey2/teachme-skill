# `/teachme-review <topic>`

Interleaved spaced-repetition coaching on weak or unmastered subtopics, without generating or modifying study notes. Laws: `SKILL.md §A–§D`. Pedagogy & pacing: `RETENTION-AND-RECORDS.md`.

## Steps
1. **Pick the target:** Run `vault_cli.py state`; from `00-GRAPH.json` + latest `learning-records/`, choose the highest-priority non-`mastered` or previously struggled subtopic in topological order.
2. **Load:** Run `vault_cli.py context [<session>] --topic <nn>` (returns curriculum node, recent events, active learning records, and 1-hop dependency anchors in one call).
3. **Coach:** Brief plain-English + Formula Anatomy recap, then run the `RETENTION-AND-RECORDS.md §3` ladder (`We Do` → `You Do` → Edge-Case & Feynman), ONE question per turn, Anti-Spoiler (`§4`) on every miss.
4. **Log:** Run `vault_cli.py tick` on `[1/4]`–`[3/4]`; on `[4/4]` pass, run `tick --cp 4 --status pass` + state-only `flush` and record breakthroughs or resolved misconceptions in `learning-records/`.
