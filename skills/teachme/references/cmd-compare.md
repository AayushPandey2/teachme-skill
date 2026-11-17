# `/teachme-compare <A> vs <B>`

Primary-source trade-off matrix at `<VAULT_ROOT>/comparisons/<a-vs-b>.md`. Laws: `SKILL.md §B`. Sourcing: `RESEARCH-TOOLCHAIN.md`.

## Steps
1. **Check Mode & Lookup:**
   - **Vault-Native Mode (`VAULT-NATIVE.md`):** run `vault_cli.py search` for `<A>` and `<B>`, then `plan --topic "<A> vs <B>" --content-json ...` -> preview -> `apply --plan <plan_id>` -> `audit` so the comparison note inherits vault tags, MOC links, and relationship Mermaid diagram automatically.
   - **Standalone Mode:** for each existing `<VAULT_ROOT>/<slug>/`, read only `00-GRAPH.json` + `L0-L1` / `L3-FOUR-LAYER-THEORY` slices. For a missing vault, run targeted primary-source research first.
2. **Write the file (4 sections):**
   - `## 1. Executive Verdict & Selection Rule` — choose A when… / choose B when…
   - `## 2. Side-by-Side "Is vs. Is Not" Matrix` — mechanism, complexity, guarantees, operational overhead, failure modes.
   - `## 3. Mathematical & Quantitative Contrast` — governing equations side by side with Formula Anatomy and crossover points.
   - `## 4. Migration, Hybrid Patterns & Pitfalls`
3. **Link & gate:** add `[[../comparisons/<a-vs-b>]]` under `## Comparisons` in each existing vault's `00-MOC-INDEX.md`, then `verify`.
