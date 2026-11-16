# Phases 3–5 Reference Index

Split into phase-scoped files to minimize context load:

| Scope | Target File |
|---|---|
| **Phase 3 (`05-MENTAL-MODELS.md`, `04-GLOSSARY.md`, `06-DERIVATIONS-AND-PROOFS.md`)** | `references/phase3-models-glossary.md` |
| **Phase 4B (`topics/<nn>-*.md` 8-Block Standard, Formula Anatomy, 7-Point Critic Audit)** | `references/subtopic-8block.md` |
| **Phases 4A/C/D & 5 (`03-CORNELL-STUDY-GUIDE.md`, `00-MOC-INDEX.md`, `00-SESSION-STATE.md`, `08-FLASHCARDS.md`, `atomic/`)** | `references/phase4-5-moc-cards.md` |

## Non-Negotiable Global Formatting Laws (All Vault `.md` Files)

1. **Global `<details>` HTML Block Law:** `<details>` and `</details>` MUST start at column 0 on their own line (never inline or inside `-` / `1.` list items), with a blank line before `<details>`, `<summary>...</summary>` on its own line immediately after `<details>`, a blank line after `</summary>`, and a blank line before `</details>`. Use `####` subheadings instead of list-nested `<details>`.
2. **Global Math Delimiter Law (100% `$...$` / `$$...$$` Coverage):** Every math symbol, Greek letter, subscripted/superscripted variable, arrow (`$\to$`, `$\implies$`, `$\iff$`), set operator (`$\in$`, `$\mathbb{R}$`), or LaTeX macro (`$\theta$`, `$\sum$`, `$\hat{y}$`, `$\mathbf{w}$`, `$\le$`, `$\ge$`, `$\neq$`, `$\approx$`, `$\frac{a}{b}$`, `$\sqrt{x}$`, `$\lVert x \rVert$`, `$\operatorname{sign}$`) anywhere in prose, lists, headings, tables, or `<details>` MUST be enclosed in `$...$` or `$$...$$`. Zero bare backslashes outside code fences and inline code.
