# `/teachme-distill <topic>`

Compress the vault into a one-page `09-CHEAT-SHEET.md` and top up `08-FLASHCARDS.md`. Laws: `SKILL.md §B`. Templates: `STUDY-AND-GLOSSARY.md §4`.

## Steps
1. **Harvest:** `vault_cli.py state` + `graph`; read `04-GLOSSARY.md`, `05-MENTAL-MODELS.md`, `06-DERIVATIONS-AND-PROOFS.md`; slice `L0-L1` (plus `L3-FOUR-LAYER-THEORY` for key equations) per topic.
2. **Write `09-CHEAT-SHEET.md`:** exactly the 4 sections in the template.
3. **Flashcards:** append missing conceptual (`::` / `?`) and cloze (`==…==`) cards; never delete existing cards.
4. **Link & gate:** ensure `[[09-CHEAT-SHEET]]` is in `00-MOC-INDEX.md` Vault Navigation, then `fix` → `verify`.
