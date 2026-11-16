# Phase 1 Reference: Frontier Grilling & Mission Lock

## 1. Dependency-Tree Frontier Grilling Protocol

Never dump a 10-question form on the user, and never ask questions you can answer yourself via research.

### Step A: Separate Facts from Decisions
- **Facts (Agent Responsibility):** Technical specs, history, benchmarks, standard architectures, best practices. *Never ask the user about facts—research them in Phase 2.*
- **Decisions & Context (User Responsibility):**
  1. **Prior Knowledge & Prerequisites:** Baseline in `<topic>` (defaulting to **No prior knowledge** / zero-baseline first principles).
  2. **Depth & Syllabus Coverage:** Thoroughness level (defaulting to **Absolute mastery covering all topics** / zero-omission syllabus).
  3. **Concrete Mastery Goal:** What "done" looks like (defaulting to **Complete first-principles mastery**).
  4. **Seed Notes or Custom Scope Boundaries:** Any syllabus, textbook, lecture notes, or exclusions to anchor on (defaulting to **None**).

### Step B: Present Only the Unblocked Frontier
Ask these **4 numbered questions** in a single clean turn. Format every question with `❓` and provide the primary recommended default prefixed with `➡️ Default:`:

```markdown
Before I launch primary-source research and build your vault at `<VAULT_ROOT>/<topic-slug>/`, let's lock the mission (reply with numbers, e.g. `1 working familiarity, 2 defaults`, or type `defaults` / `go`):

1. ❓ **1. Prior Knowledge & Prerequisites:** How much background do you already have in `<topic>`?
   ➡️ *Default:* **No prior knowledge** *(Build from absolute zero and first principles; explain every prerequisite, symbol, and term from scratch).*
   *Alternatives:* Basic intuition only | Working familiarity | Advanced (skip fundamentals).

2. ❓ **2. Depth & Syllabus Coverage:** How thoroughly should we cover the subject?
   ➡️ *Default:* **Absolute mastery covering all topics** *(Zero-omission syllabus decomposition—every subtopic gets its own dedicated `.md` file, full step-by-step axiom derivations, and symbol-by-symbol formula anatomy).*
   *Alternatives:* Core fundamentals only | Exam / interview prep | Practical implementation focus.

3. ❓ **3. Concrete Mastery Goal:** What outcome defines success for you?
   ➡️ *Default:* **Complete first-principles mastery** *(Able to derive every formula without faith, explain every concept in plain English without jargon, and solve Tier 3 edge-case drills).*

4. ❓ **4. Seed Notes or Custom Scope Boundaries (Optional):** Any specific syllabus, textbook, lecture notes, or exclusions to anchor on?
   ➡️ *Default:* **None** *(Full unrestricted syllabus anchored on canonical primary sources).*
```

---

## 2. Mission Lock (`00-MISSION.md`)

Once the user answers (or selects `defaults`, `go`, or `--auto`), create `<VAULT_ROOT>/<topic-slug>/00-MISSION.md` using this exact structure. Whenever defaults are chosen, write the exact baseline and coverage lines below so Phase 6 automatically calibrates Question 1 to a beginner-safe 1-number scalar trace:

### Template: `<VAULT_ROOT>/<topic-slug>/00-MISSION.md`

```markdown
# Mission: <Topic Title>

- **Vault Path:** `<VAULT_ROOT>/<topic-slug>/`
- **Created:** <YYYY-MM-DD>
- **Prior Knowledge Baseline:** No prior knowledge (Zero-baseline first principles)
- **Coverage & Depth Mode:** Absolute mastery covering all topics (Zero-omission syllabus)
- **Status:** Active

## 1. Target Outcome
Complete first-principles mastery of `<Topic Title>`: able to derive every formula without faith, explain every concept in plain English without jargon, and solve Tier 3 edge-case drills. *(Or custom outcome if specified by the user.)*

## 2. Success Criteria (Observable Proof of Mastery)
- [ ] Explain every core mechanism from first principles without jargon.
- [ ] Derive every governing equation step-by-step from base axioms.
- [ ] Compare `<topic>` against its top 2–3 alternatives across complexity, trade-offs, and failure modes.
- [ ] Diagnose and resolve Tier 3 edge cases, boundary limits, and failure scenarios.

## 3. Curriculum Milestones
1. **Milestone 1:** <Prerequisites, Origin & Core Mental Model>
2. **Milestone 2:** <Internal Architecture & Step-by-Step Mechanics>
3. **Milestone 3:** <Mathematical Derivations, Trade-offs & Edge Cases>
4. **Milestone 4:** <Comparative Landscape & Applied Mastery>

## 4. Explicit Scope Boundaries
- **In Scope:** Full unrestricted syllabus anchored on canonical primary sources (zero-omission coverage). *(Or custom scope if specified.)*
- **Out of Scope:** None—all subtopics covered. *(Or explicit exclusions if specified.)*

## 5. User Seed Questions & Raw Inputs
- <List any specific syllabus, textbook, lecture notes, or questions provided by the user, or "None provided.">
```
