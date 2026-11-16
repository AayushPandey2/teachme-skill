# Phase 3 Reference: Mental Models, Glossary & Derivations

---

## 1. Phase 3A: First-Principles & Adversarial Models (`05-MENTAL-MODELS.md`)

````markdown
# Mental Models & First-Principles Breakdown: <Topic Title>

## 1. Zero-Jargon Feynman Core
<2–3 plain-English paragraphs using one concrete physical analogy; note where it holds and breaks.>

## 2. First-Principles Axiom Stack
1. **Axiom 1 (<Fundamental Truth>):** <Why true regardless of implementation>
2. **Axiom 2 (<Derived Necessity>):** <How Axiom 1 + constraint forces the design>
3. **Axiom 3 (<Architectural Consequence>):** <Why system takes canonical shape>

## 3. System Architecture & Flow Diagram (ASCII)
```text
<Clean ASCII component, data/control flow & state diagram>
```

## 4. Adversarial Pre-Mortem (How to Break It)
1. **Failure Mode 1 (<Name>):**
   - *Trigger:* <Exact condition>
   - *Blast Radius:* <Corruption / latency / deadlock / crash>
   - *Defensive Invariant:* <How to prevent or detect>
2. **Failure Mode 2 (<Name>):** *Trigger:* <Condition> | *Blast Radius:* <Impact> | *Defensive Invariant:* <Mitigation>
3. **Failure Mode 3 (<Name>):** *Trigger:* <Condition> | *Blast Radius:* <Impact> | *Defensive Invariant:* <Mitigation>
````

---

## 2. Phase 3B: Canonical Domain Glossary (`04-GLOSSARY.md`)

```markdown
# Canonical Glossary: <Topic Title>

> **Rule:** 1–2 sentences stating *what the term IS*. Never dump tutorials here.

- **<Term 1>:** <1–2 sentence definition.>
  _Avoid:_ <Overloaded synonym/alias>.
- **<Term 2>:** <1–2 sentence definition.>
  _Avoid:_ <Overloaded synonym/alias>.
```

---

## 3. Phase 3C: Step-by-Step Derivations (`06-DERIVATIONS-AND-PROOFS.md`)

```markdown
# Step-by-Step Derivations & Proofs: <Topic Title>

## 1. Derivation of <Formula / Theorem>
- **Target Formula:**
$$
<Display LaTeX>
$$
- **Starting Axioms:** <Base axioms from 04-GLOSSARY.md / 05-MENTAL-MODELS.md>
- **Cross-References:** [[topics/<nn>-<slug>]] | [[04-GLOSSARY#<term>]]

### Step-by-Step Proof
1. **Step 1:** $$<Start>$$ — *Why:* <1-sentence justification>.
2. **Step 2:** $$<Transition>$$ — *Why:* <1-sentence justification>.
3. **Step 3 (Final):** $$<Target>$$ — *Why:* <1-sentence justification>.
```
