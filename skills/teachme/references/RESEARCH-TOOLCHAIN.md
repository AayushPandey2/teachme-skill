# Primary-Source Retrieval, Deep-Linking & Scratchpad Isolation

Formatting laws live in `SKILL.md §B` only. Treat pre-trained knowledge as untrusted until grounded here.

## §1. Retrieval Rules
- **Chase to origin:** Never cite a secondary blog when the paper, RFC, spec, or source code is reachable.
- **Knowledge (primary):** official docs, RFCs/standards, peer-reviewed papers, canonical textbooks, source repos, release notes.
- **Wisdom (practitioner):** post-mortems, creator/maintainer talks, vetted issue threads exposing real sharp edges.
- **Exclude:** SEO listicles, AI-generated summaries, undated/unversioned tutorials, unverifiable claims.
- **Log gaps explicitly:** conflicts, paywalls, or missing benchmarks go to `## Gaps & Unverified Claims` — never paper over them.

## §2. Scratchpad Isolation
- All raw extraction, rough algebra, and drafts live in `scratchpad/` (`raw-research.md`, `derivation-drafts.md`, `subtopics.json`, `events.jsonl`, `queue-<nn>.json`).
- `scratchpad/` is excluded from `verify`, graph building, and MOC registration; never link to it from notes.

## §3. Deep-Link Standard
- Link the exact DOI / arXiv abs page / RFC `#section-N` / docs anchor — never a bare domain.
- Every `01-RESOURCES.md` source gets its own `###` heading so `[[01-RESOURCES#<heading>]]` resolves; every `02-DEEP-RESEARCH.md` subsection uses a stable `###` heading for `[[02-DEEP-RESEARCH#<heading>]]`.
- Inline citation format is defined once in `SKILL.md §B.6`.

## §4. Template — `01-RESOURCES.md`

```markdown
# Research Resources & Provenance Index: <Topic Title>

## Research Brief
- **Mission Alignment:** [[00-MISSION]]
- **Core Questions:** 1. <Q1> 2. <Q2> 3. <Q3> 4. <Q4>

## Exhaustive Syllabus (1 Subtopic = 1 `topics/<nn>-<slug>.md`)
1. `01-<slug>` — <Title & scope>

## Knowledge (Primary Sources)
### <Author / Org> (<Year>) — <Source Title>
- **Direct Link:** [<Paper DOI / Docs Section>](<exact-deep-url>)
- **Type:** Spec / Paper / Docs | **Covers:** <Exact mechanism, equation, or claim>

## Wisdom (Practitioner Signal)
### <Author> (<Year>) — <Talk / Post-Mortem Title>
- **Direct Link:** [<Section / Timestamp>](<exact-deep-url>)
- **Type:** Post-Mortem / Talk | **Covers:** <Real-world failure mode or trade-off>

## Gaps & Unverified Claims
- **Gap 1:** <What could not be verified and why.>
```

## §5. Template — `02-DEEP-RESEARCH.md`
Every equation is `$$...$$` display math followed by a Formula Anatomy Breakdown (`STUDY-AND-GLOSSARY.md §1`).

```markdown
# Deep Primary-Source Research Dossier: <Topic Title>

## 1. Origin & Problem Statement
- **Catalyst:** <What existed before and the bottleneck solved> <citation>
- **Design Constraints:** <Constraints that shaped the architecture> <citation>

## 2. Architecture & Internal Mechanics
- **Components:** <Each component's responsibility> <citation>
- **Execution Flow:** <Exact step-by-step mechanics> <citation>
- **Invariants & Guarantees:** <What strictly holds, under which preconditions> <citation>

## 3. Mathematical Formulations & Complexity Bounds
### <Formula Name>
<Display equation + Formula Anatomy Breakdown> <citation>

## 4. Benchmarks, Trade-offs & Failure Modes
- **Performance:** <Verified bounds and benchmarks> <citation>
- **Where It Breaks:** <Edge cases causing bugs or degradation> <citation>

## 5. Comparative Landscape
| Dimension | <Topic> | <Alt A> | <Alt B> |
|---|---|---|---|
| **Core Mechanism** | ... | ... | ... |
| **Primary Strength** | ... | ... | ... |
| **Critical Weakness** | ... | ... | ... |
| **Best-Fit Scenario** | ... | ... | ... |

## 6. Contested Claims & Open Questions
- <Conflicting benchmarks, version deltas, unresolved edge cases.>
```
