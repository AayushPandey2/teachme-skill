# Subcommand Router Index

Every subcommand has its own dedicated, minimal instruction file in `references/` so slash-command invocations load ONLY the rules they need (~75% fewer instruction tokens). All commands resolve `<VAULT_ROOT>` via `~/.teachme-config.json` (default `~/notes`) and use `scripts/vault_cli.py` for zero-token state, graph, slicing, ticking, and verification.

| Subcommand | Canonical Reference File |
|---|---|
| `/teachme-expand` \| `/teachme expand` | `references/cmd-expand.md` |
| `/teachme-verify` \| `/teachme verify` / `audit` | `references/cmd-verify.md` |
| `/teachme-ingest` \| `/teachme ingest` | `references/cmd-ingest.md` |
| `/teachme-distill` \| `/teachme distill` | `references/cmd-distill.md` |
| `/teachme-review` \| `/teachme review` | `references/cmd-review.md` |
| `/teachme-feynman` \| `/teachme feynman` | `references/cmd-feynman.md` |
| `/teachme-drill` \| `/teachme drill` | `references/cmd-drill.md` |
| `/teachme-compare` \| `/teachme compare` | `references/cmd-compare.md` |
| `/teachme-notes-path` \| `/teachme notes-path` | `references/cmd-notes-path.md` |
