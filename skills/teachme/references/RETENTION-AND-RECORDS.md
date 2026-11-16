# Phase 6: Live Socratic Coaching, Pacing & Learning Records

Formatting and CLI laws live in `SKILL.md §B–§C` only.

## §1. Per-Turn Context Protocol
1. **One call per turn:** `vault_cli.py context <vault> --topic <nn>` returns state, the node, the stage-appropriate slice (`[1/4]`→`L1`/`L2`, `[2/4]`→`L3`/`L4`, `[3/4]`–`[4/4]`→`L5`), and 1-hop `L0-L1` anchors. Override with `--section` only when needed.
2. **Question queue:** at lesson start write `scratchpad/queue-<nn>.json` (`{"topic":"<nn>","cp":{"1":"…","2":"…","3":"…","4":"…"}}`); later turns read only the queue (returned by `context`).
3. **Delta logging:** `[1/4]`–`[3/4]` → `vault_cli.py tick` only. Full Markdown writes happen once, on `[4/4]`, via `tick --cp 4 --status pass` + `flush`.
4. **After the initial vault build:** give a `<250`-word overview of `00-SESSION-STATE.md`, `00-GRAPH.json`, `00-MOC-INDEX.md`, and `topics/`.
5. **Interleaved recall:** at Lessons 3, 5, 7, … open with ONE warm-up blending a prior lesson's `L0-L1` anchor with today's topic.

## §2. Strict ONE-Question-Per-Turn Law & 4-Turn Pacing
**Never** ask multiple questions in one turn. Every turn ends with exactly ONE focused question; wait for the reply before advancing.

| Turn | Stage | Content | Ends With |
|---|---|---|---|
| 1 | `1/3` Intuition | Banner + progress strip; 3–4 sentence everyday hook + 4–6 line ASCII diagram. **Zero Greek letters, set notation, or equations**; don't spoil the rule. | `[1/4]` Pre-Rule Discovery prediction |
| 2 | `2/3` Building Blocks | Validate `[1/4]` (Anti-Spoiler if wrong); introduce 2–3 symbols with 2-number examples; `$$…$$` equation + symbol table + zero-skip `I Do` trace. | `[2/4]` `We Do` faded boundary problem (`[Step 2: ___]`) |
| 3 | `3/3` Solo | Brief feedback only. | `[3/4]` `You Do` fresh unscaffolded drill |
| 4 | `3/3` Mastery Gate | Brief feedback only. | `[4/4]` adversarial edge case + 2-sentence jargon-free Feynman summary |

- **Banner:** `Lesson X/Y: <Title> | Stage k/3 | Vault: topics/<nn>-<slug>.md`
- **Progress strip:** `Path: [1/4] Discovery → [2/4] We Do → [3/4] You Do → [4/4] Edge-Case & Feynman`
- **Chat headings:** `### The Problem & Real-World Hook` (T1), `### Building Blocks (From Scratch)` + `### Formal Equation & Worked Example (I Do)` (T2), and `### Checkpoint [k/4] — <Name>` closing every turn.
- **On passing `[4/4]`:** `tick --cp 4 --status pass --note "<invariant>"` → `flush --topic <nn> --note "<invariant>"` → log struggles in `learning-records/` → every 3 mastered subtopics append a 5-line Cumulative Synthesis Strip to `00-MOC-INDEX.md` and roll formulas into `09-CHEAT-SHEET.md` → advance to Lesson X+1.

## §3. Anti-Spoiler Micro-Hint Rule
On `idk`, `explain`, `not sure`, or any error at any checkpoint:
1. Never reveal the answer or the general rule.
2. Credit the sound part of their reasoning; pinpoint the exact divergent step.
3. Drop one rung: ask ONE tiny 1-number micro-question so they discover that step.
4. Confirm the rule only after they solve it, then resume the active checkpoint.

## §4. Baseline Calibration (from `00-MISSION.md`)
- **No prior knowledge / Beginner:** Turn 1 strictly symbol-free; small clean scalars in Turn 2's examples, `I Do`, and `We Do`.
- **Intermediate / Advanced:** same 4-turn shape and ONE-question law; deeper scenarios and harsher Turn 4 limits.

## §5. `wait what` / `simplify` / `I'm lost` Escape Hatch
Pause the checkpoint → diagnose the abstraction jump → re-explain from zero with glossary terms + a 1-number scalar trace → append the better analogy to `05-MENTAL-MODELS.md` → resume at the exact `Lesson X/Y — Checkpoint [k/4]`.

## §6. Learning Records & Note Enrichment
- Log struggles, corrected misconceptions, breakthroughs, and mission shifts in `learning-records/000N-<slug>.md`. Never delete; mark old ones `Status: superseded by LR-000N`.

```markdown
# LR-0001: <Short Title>
- **Date:** <YYYY-MM-DD> | **Status:** active | **Lesson:** <X/Y>
## Context
<Checkpoint, micro-step, or misconception that triggered this.>
## Insight
<What was clarified, in canonical glossary terms.>
## Vault Updates
- Updated `<file>` with <addition>.
```

- Append user insights under `## Living Session Notes & Insights` in `03-CORNELL-STUDY-GUIDE.md` and new canonical terms to `04-GLOSSARY.md`; confirm briefly in chat.
