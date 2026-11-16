# `/teachme-review <topic>`

Interleaved spaced-repetition coaching on weak or unmastered subtopics, without regenerating notes. Laws: `SKILL.md §B–§C`. Pacing: `RETENTION-AND-RECORDS.md`.

## Steps
1. **Pick the target:** `vault_cli.py state`; from `00-GRAPH.json` + latest `learning-records/`, choose the highest-priority non-`mastered` or previously struggled subtopic in topological order.
2. **Load:** `vault_cli.py context <vault> --topic <nn>` (stage slice + 1-hop anchors in one call).
3. **Coach:** brief plain-English + Formula Anatomy recap, then the `RETENTION-AND-RECORDS.md §2` ladder (`We Do` → `You Do` → Edge-Case & Feynman), ONE question per turn, Anti-Spoiler (`§3`) on every miss.
4. **Log:** `tick` on `[1/4]`–`[3/4]`; on `[4/4]` pass, `tick --cp 4` + `flush` and record breakthroughs in `learning-records/`.
