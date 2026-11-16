# Command: `/teachme-compare <A> vs <B>` *(alias: `/teachme compare <topic-a> vs <topic-b>`)*

Build a primary-source structural trade-off matrix at `<VAULT_ROOT>/comparisons/<a-vs-b>.md` contrasting two concepts, algorithms, or architectures.

## Execution Sequence
1. **Cross-Vault & Primary-Source Lookup:**
   - Check if `<VAULT_ROOT>/<a-slug>/` and `<VAULT_ROOT>/<b-slug>/` exist.
   - For existing vaults, load ONLY `00-GRAPH.json` + `--section L0-L1` / `L3-FOUR-LAYER-THEORY` via `vault_cli.py slice`.
   - For any missing vault, run targeted primary-source research (`RESEARCH-TOOLCHAIN.md`) first so all claims carry `[Source]` provenance.
2. **Generate `<VAULT_ROOT>/comparisons/<a-vs-b>.md`:**
   - `## 1. Executive Verdict & Selection Rule` (Choose A when... / Choose B when...)
   - `## 2. Side-by-Side Architecture & Contrastive "Is vs. Is Not" Matrix` (Core Mechanism, Complexity in pure LaTeX with `\mid` in tables, Guarantees, Operational Overhead, Primary Failure Modes)
   - `## 3. Mathematical & Quantitative Contrast` (Governing equations side-by-side with Symbol Anatomy & crossover points—zero backtick-wrapped math)
   - `## 4. Migration, Hybrid Patterns & Pitfalls`
3. **Bidirectional Linking & Verify:**
   - Add `[[../comparisons/<a-vs-b>]]` under `## Comparisons` in both vaults' `00-MOC-INDEX.md` (where those vaults exist) and run `vault_cli.py verify`.
