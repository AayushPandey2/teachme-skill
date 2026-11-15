# Phase 6 Reference: Teach-Before-Test Socratic Loop, Learning Records & `wait-what`

---

## 1. Mandatory Teach-Before-Test Rule

**Non-Negotiable Rule:** Never cold-quiz the user on a topic or subtopic you have not explained in chat first.

### Execution Sequence Before Question 1 (and Before Any New Subtopic)
1. **Vault Summary:** After generating the vault files at `~/notes/<topic-slug>/`, provide a crisp executive overview (<250 words) and list the generated files (highlighting `00-MOC-INDEX.md`).
2. **Teach Subtopic 1 in Full Detail First:** Before asking Question 1, deliver a comprehensive, crystal-clear lesson on Subtopic 1 directly in chat:
   - Explain the core concept, intuition, and step-by-step mechanics in plain English.
   - Present **every mathematical formula** belonging to that subtopic in LaTeX (`$$...$$`) and immediately provide a complete **Component & Symbol Breakdown** explaining what **every single variable, subscript, superscript, constant, and mathematical operator** means, its units/domain, how increasing or decreasing it affects the output, and a concrete numerical walkthrough.
3. **Ask Question 1:** Only after completing this detailed explanation, present Question 1.
4. **Repeat Per Subtopic:** Apply this exact same **Teach-Before-Test** pattern whenever advancing to subsequent subtopics during the Socratic loop.

---

## 2. Baseline-Calibrated Socratic Grilling (Beginner-Safe Question 1)

Calibrate Question 1 strictly to the user's baseline recorded in `00-MISSION.md`:

- **For `0 knowledge` / `Beginner` baselines:**
  - *Mandatory Rule:* Start Question 1 with a concrete **1-number scalar trace** (plugging 1 simple number into the mechanism or formula to see what comes out) before introducing 2D geometry, vectors/matrices, or multi-variable edge cases.
  - Only escalate to 2D geometry or multi-feature interactions in Question 2+ once the 1-number trace succeeds.
- **For `Intermediate` / `Advanced` baselines:**
  - Start Question 1 with a targeted diagnostic, invariant check, or failure-mode prediction scenario.

### Pedagogical Rules (Storage Strength vs. Retrieval Fluency)
- **Test Storage, Not Recognition:** Never ask `"Do you understand X?"` or simple definition lookups. Ask trace, diagnostic, transfer, or failure-prediction questions.
- **One Question at a Time:** Wait for the user's response before moving on.
- **Evaluate & Calibrate:**
  - Identify what the user nailed accurately.
  - Pinpoint any subtle misconception or missing invariant without lecturing.
  - Adjust difficulty dynamically (step up to edge cases if they ace it; scaffold down to a simpler 1-number trace if they struggle).
  - When a subtopic is mastered, check it off (`- [x]`) in `~/notes/<topic-slug>/00-MOC-INDEX.md`.

---

## 3. Inline `wait-what` Protocol

If at any point the user replies with **`wait what`**, **`/wait-what`**, **`I'm lost`**, or **`simplify`**:
1. **Pause the grill immediately**—do not judge or test them.
2. **Diagnose the Jargon/Abstraction Jump:** Identify the exact concept or unstated assumption that caused friction.
3. **Re-Pitch in Plain English:** Explain the concept from scratch using:
   - Strictly canonical terms defined in `04-GLOSSARY.md` (defining any new word inline).
   - A concrete **1-number scalar trace** or simpler step-by-step mental model.
4. **Update the Vault:** Append the clearer explanation or analogy to `~/notes/<topic-slug>/05-MENTAL-MODELS.md` so the permanent notes improve alongside the user's understanding.
5. **Resume Gently:** Check that the re-pitch clicks before asking a lighter verification question.

---

## 4. ADR-Style Learning Records (`learning-records/000N-<slug>.md`)

Maintain a chronological log of breakthroughs, corrected misconceptions, and mission changes inside `~/notes/<topic-slug>/learning-records/` (numbered `0001-<slug>.md`, `0002-<slug>.md`, etc.). Never delete old records; if a later insight supersedes an earlier understanding or goal, mark the old record `Status: superseded by LR-000N`.

### Template: `~/notes/<topic-slug>/learning-records/0001-<slug>.md`

```markdown
# LR-0001: <Short Title of Breakthrough, Misconception Fix, or Mission Shift>

- **Date:** <YYYY-MM-DD>
- **Status:** active
- **Milestone:** <Milestone # from 00-MISSION.md>

## Context
<What question, scenario, or confusion triggered this learning moment.>

## Insight / Mastery Demonstrated
<What was clarified, proven, or decided—using canonical terms from 04-GLOSSARY.md.>

## Vault Updates Made
- Updated `<filename>` with <specific addition or correction>.
```

---

## 5. Continuous Note Enrichment

Whenever the user shares a new insight, real-world war story, voice transcript, or sharp follow-up question during Phase 6:
- Cleanly format and append it under `## Living Session Notes & Insights` in `~/notes/<topic-slug>/03-CORNELL-STUDY-GUIDE.md`.
- If it introduces a new core term, add a 1-2 sentence entry to `~/notes/<topic-slug>/04-GLOSSARY.md`.
- Confirm briefly in chat what was persisted to the vault.
