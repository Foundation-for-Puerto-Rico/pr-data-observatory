# Spanish text of the data dictionary

`python dictionary.py` reads these files and puts the Spanish next to the English in `site/data/dictionary.json`, and from there into files that only the Spanish dictionary page reads, so the English page loads nothing more: `dictionary_list_es.json` (the names, the short labels, the source cards, the area and group texts, the search words of "how to read it" and the list of held entries), fetched right after the page is ready, and `dictionary_detail_<domain>_es.json` ("how to read it"), fetched with the detail file of the same domain when an entry is opened. Until the Spanish is in, the page shows the English; a field with no Spanish here stays in English, marked `lang="en"`.

The Spanish of the summaries is in `i18n_src/dictionary_plain.json` (`plain_es`) and the glossary's in `dictionary_src/glossary.json` (`term_es`, `expansion_es`, `plain_es`, with its source); this folder does not repeat them.

**Status: draft translation (2026-10), drafted by Claude, under review by a Spanish-speaking reviewer at FPR.** The page says so at the top in Spanish. `docs/i18n.md` has the style guide and the terminology to use.

## Files

| File | What it holds | Keyed by |
|---|---|---|
| `entries/<area>.json` | `name` and `how_to_read` of each entry (phase 1); `definition`, `method`, `caveats`, `source_detail` later (phase 2) | entry id |
| `labels.json` | short labels that repeat across entries: units, geographies, group names, update frequencies | the English label itself |
| `sources.json` | `access`, `cadence`, `used_for`, `terms_note` of each source card | source id |
| `groups.json` | the area summary and the group notes of each domain | domain id (group names stay English as keys) |
| `held_for_review.json` | Spanish **not published** until Finance and Compliance review it: `entries` (Table 10 and the federal money and FEMA entries of Public money; the WCRP entries were released on 2026-10-21, per decision 51), `sources` (the 2023 housing study, which holds Table 10, and the USAspending and OpenFEMA cards; the WCRP card was released on 2026-10-21, per decision 51), `groups` (the Public money area) and `labels` (the labels that only held entries use). The build reads only its ids, plus the entries held in `i18n_src/held_for_review.json` (`dictionary_plain`), and keeps their Spanish out; a held entry shows all its labels in English | as above |
| `status.json` | the review status the page can show | |

## Keeping Spanish in step with the English

Every record has `"_en": {field: fingerprint}`: 8 hex characters of the English it was translated from (`dictionary.fingerprint()`). When someone edits the English, the old Spanish no longer matches; the build leaves it out (the page shows the new English) and prints it as `STALE`. `python dictionary.py --es` lists every stale field. To fix one, translate the new English and update its fingerprint, for example:

```python
import dictionary as d
print(d.fingerprint("the new English text"))
```

`labels.json` needs no fingerprint: its key is the English, so a changed label simply stops matching.

## Rules

- Follow the Spanish style guide and terminology in `docs/i18n.md`. When the interface already translates a name or label (`i18n_src/es/*.json`), use that Spanish.
- Keep every number, unit, threshold and caution exactly as in the English. Nothing about the facts changes in translation.
- Text about federal grant programs goes to `held_for_review.json`, not to the published files. Holds go by what the text belongs to (an entry, a source card, an area), not by its words. `tests/test_dictionary_es.py` checks that no held Spanish reaches a published file.
- The Spanish is loaded only on the Spanish page, and only when it is read: the list file after the page is ready, "how to read it" when an entry is opened (`dictionary_src/routes.json`: 'later' and 'on_use'). Keep the dictionary page within its budget (`python budget.py`).
