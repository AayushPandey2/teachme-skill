# Visuals, Small Experiments, Capability Contract & Image Provenance

Load this reference **only** when a visual, diagram, retrieved image, plot, or small experiment serves an explicit learning objective. Do **not** add decorative media or force a diagram into every lesson.

## §1. Visual & Experiment Selection Matrix
| Learning Need | Preferred Representation | Example Use |
|---|---|---|
| Real-world recognition | Retrieved verified photograph | Anatomical landmark, hardware port, geological structure |
| Spatial structure | Labeled diagram | Coordinate axes, circuit topology, neural layer wiring |
| Quantitative relationship | Computed plot (from explicit equations/data) | Loss curve $L(w)$ vs. parameter $w$, learning-rate steps |
| Process over time | Step-through trace or animation | Gradient descent iterations, sorting pass |
| Cause and effect | Small bounded interactive experiment / parameter sweep | Varying learning rate $\eta$ on $f(x)=x^2$ |
| Program execution | Trace table or named variable/target diagram | C pointers: named variables, addresses, targets after each statement (never teach a misleading physical memory layout) |
| Dependencies / structure | Graph (when helpful) | Prerequisite DAG |
| Concept clearer in words | Concise text (no visual) | Definitions, algebraic identities, narrow doubts |

**Required elements for any selected visual or experiment:**
1. Specific learning objective (`objective_id`).
2. Why this representation helps that objective.
3. Short explanation of **what to notice**.
4. An interpretation, prediction, or manipulation task when useful (e.g., for gradient descent, compute a loss curve, mark the current parameter, ask the learner to predict the update direction, then vary the learning rate).
5. Text alternative / terminal fallback when rich rendering is unavailable.
6. Relevant assumptions and limitations (e.g., simplified 1D convex slice, idealized pointer model).

## §2. Honest Host Capability Contract & Progressive Fallbacks
Do not assume all host agents expose the same tools. Check only tools actually exposed in the active host environment:
- **Capabilities:** Web search, Source-page retrieval, Image search, Image inspection, Local image display, Code execution, Plot generation, Browser/interactive artifact rendering.
- **Strict prohibitions:** Never invent tool names, MCP server availability, API credentials, browser support, image inspection results, or successful rendering. Never claim a plain-text CLI can display rich media when it cannot. Never require installing an MCP merely to continue a lesson.
- **Progressive fallback:**
  1. Render directly if the host supports inline images/plots/interactive artifacts.
  2. Otherwise open or link a local/browser artifact inside `scratchpad/media/` if supported.
  3. Otherwise provide a static representation (ASCII/Unicode table, trace table, or numeric table) and concise text explanation.
  4. Continue teaching smoothly if optional media tools fail.

## §3. Internet Image Retrieval & Provenance Workflow
When retrieving images during live teaching (only if host search/retrieval tools exist):
1. Identify the concept and required visual features.
2. Search credible, subject-appropriate primary/authoritative sources.
3. Inspect the **source page** and **candidate image** when tools permit.
4. Verify labels, assumptions, relevance, and consistency with the lesson.
5. Present with attribution, explanation of what to notice, and an interpretation/prediction question when useful.

**Image prohibitions:**
- Never use an image-search thumbnail as the sole factual authority.
- Never claim visual inspection (`inspected_verified`) when only metadata/text was available (`metadata_only_unverified`).
- Never invent URLs or licenses (record `"unknown"` if license/reuse terms are not explicitly verified; public accessibility does not imply permission to redistribute).
- Never treat AI-generated imagery as verified factual evidence or use image generation for exact mathematical plots/diagrams that require accurate labels.
- If an image cannot be adequately inspected, use a verified alternative or a clear text/diagram fallback.
- Never run a bulk downloader; if caching a single verified asset locally under `scratchpad/media/`, enforce bounded sizes/timeouts, validate content type and path, and avoid unsafe active content.

**Record provenance operationally:**
```bash
python vault_cli.py record-media [<session>] --objective <obj_id> --kind retrieved_image \
  --source-page "<url>" --asset-url "<url>" --title "<title>" --creator "<author>" \
  --license "<license_or_unknown>" --verification <inspected_verified|metadata_only_unverified|generated_plot|local_diagram|unverified> \
  [--local-path "scratchpad/media/plot.png"] --fallback-text "<text alternative>"
```

## §4. Small Bounded Experiments & Generated Visuals
- Derive exact plots and diagrams from explicit data, equations, or program traces (never hand-guessed curves).
- Transient operational visuals/experiments under `scratchpad/media/` are allowed teaching assets—do **not** route them to Scriptorium or confuse them with reusable study-note generation.
- **Safety bounds:** No arbitrary downloaded code execution, no learner secrets, no writes to unrelated files, no unbounded compute, no requirement for external paid APIs.
