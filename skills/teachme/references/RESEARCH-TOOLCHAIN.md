# Primary-Source Retrieval & Provenance Isolation (Teaching & Ingestion)

Core laws live in `SKILL.md §A–§D`. Treat pre-trained knowledge as untrusted until grounded against primary sources when verifying technical claims, equations, or benchmarks for teaching.

## §1. Retrieval Rules
- **Chase to origin:** Prefer canonical primary sources over secondary summaries whenever reachable.
- **Knowledge (primary):** official docs, RFCs/standards, peer-reviewed papers, canonical textbooks, source repositories, release notes.
- **Wisdom (practitioner):** post-mortems, creator/maintainer talks, vetted issue threads exposing real edge cases.
- **Exclude:** SEO listicles, AI-generated summaries, undated/unversioned tutorials, unverifiable claims.
- **Never fabricate citations:** Never invent DOIs, URLs, authors, dates, theorem numbers, or benchmarks. Mark unverified claims explicitly in chat and log unresolved conflicts or gaps in `learning-records/` or `scratchpad/ingested-sources.json`.

## §2. Operational Scratchpad & Provenance Storage
- Raw extraction, rough derivations, and source inventories live inside the session's `scratchpad/` (`raw-research.md`, `derivation-drafts.md`, `subtopics.json`, `curriculum.json`, `ingested-sources.json`, `events.jsonl`, `queue-<nn>.json`).
- Keep `scratchpad/ingested-sources.json` compact (`title`, `url`, `type`, `retrieved_at`, `claims_or_topics`) so `vault_cli.py handoff` can export verified `source_provenance` without dumping full transcripts or raw notes.
- Existing study notes (whether in an Obsidian vault or legacy files) are **read-only learning inputs**; never write `01-RESOURCES.md`, `02-DEEP-RESEARCH.md`, or merge ingested content into study notes.
