# Scenarios and model outputs (Phase 3, item 15)

Plan: `docs/proposal-2026-10.md`, section F (J row 15). The workspace is the workbench's **Scenarios** tab on the 2D map. Its code (`site/js/scenarios.js` and `site/js/core/scenario.js`, about 10 KB compressed) loads the first time the tab opens, so the map's first load does not carry it.

## Scenarios

A scenario holds four things:

- **The map's link.** That is the layers with their settings, the year, the base year, the composite (`ix=`), the planned route (`r=`) and the map position.
- **Figures.**
  - The planned route's measures: length, residents within 400 m, of them those with no current stop within 400 m, tourism places within 400 m, the share of the length near an existing route, the share in a flood hazard area and the municipalities crossed.
  - Puerto Rico's value of each visible layer, with its year and settings.
- **The model outputs whose layers are on the map** when it is saved.
- **A name, a label and notes.** The label is "prepared by", meaning a team or organization. The name, label and notes refuse an e-mail address or a telephone number.

**Storage.** Scenarios stay in the browser, in IndexedDB under `pr-twin-scenarios`; nothing is sent anywhere. In a private window the browser may keep nothing, and the tab then says the scenarios last until the page closes.

**What you can do with them:**
- **Export:** saves one as a JSON file.
- **Import a scenario:** reads one back after checking it. The checks are the version, a name, a label, notes and a date of creation of the right kind, a link that is a link, figures that are numbers, and every model output it holds checked by the same rules as a model file (header, variables, units, one number or none per place and year). No field may hold contact details. Fields the observatory does not know are dropped, not stored.
- **Saved list:** a stored scenario that fails these checks (one saved before a check was added) is left out of the list; it does not hide the others.
- **Open scenario:** restores the view from its link. When the scenario holds model outputs, the link carries `sc=<id>`, and on load the page first makes their datasets again, then the layers of the link.
- **Compare two scenarios:** lists every figure with A, B, B − A and the change in percent. A figure only one scenario has shows a dash for the other. When both scenarios hold a model output of the same variable, "Map B − A" shades the difference for the periods both give. That map is also labeled as model output.

## Model outputs

A model output is the result of a model, not observed data. The observatory checks its format, never its numbers, and every dataset it makes is labeled **"Model output (not observed data)"**. The label appears in the dataset's name, its group and the legend, and the model's header appears in its definition.

### The format

**CSV.** Header lines start with `#`, then come the columns:

```
# model_name: Example housing demand model
# model_version: 1.2
# run_id: 2026-10-a
# date: 2026-10-15
# assumptions_url: https://example.org/assumptions
# licence: CC BY 4.0
# contact_label: Example Research Team
geography_key,geography_level,period,variable,value,unit,lower,upper
72001,municipio,2030,new_households,120,households,100,140
72,municipio,2030,new_households,15000,households,,
```

**GeoJSON.** A `FeatureCollection` with a top-level `model` member that holds the same header fields, and the same row fields in each feature's `properties`. The geometry is not read.

**Rules.** The whole file is refused when any rule fails, and the first 50 problems are listed:

- **Header:** all seven fields are required.
  - `date` is YYYY-MM-DD and `assumptions_url` is a web address.
  - No header field, and no `unit`, may hold an e-mail address or a telephone number. Name a team or an organization.
  - The variable may not hold a telephone number either.
  - A telephone is a US number in forms such as 787-555-0123, (787) 555 0123, (787)5550123 or 7875550123, whose area code and exchange start with 2 to 9. A date such as 2026-10-15 or a run id such as 1760540000 passes; a date-hour such as 2026101512 is refused, so write it with a separator.
  - The check is a pattern, not a guarantee: it misses forms such as 787/555/0123 or 787 555 01 23. Name a team or an organization, never a person.
- **`geography_level`** is `municipio`, the only level the map draws today.
  - `geography_key` is the five-digit municipio code; `72` is Puerto Rico as a whole.
- **`period`** is a year.
- **`variable`** is letters, digits, spaces, dots, dashes or underscores, at most 60 characters. One variable has one unit.
- **`value`** is a number. One value per place, period and variable.
- **`lower` and `upper`** are optional and must bracket the value. The map shows the value, and the definition says that the file gives a range.
- **Size:** at most 5 MB and 20,000 rows.

**On the map.** Each variable becomes a dataset of the Economy tab. It is shaded on its own: the other shaded layers are taken off, and symbols stay. A unit of `%` or `$` is used as the dataset's unit; any other unit is shown in its name.

### Sample file

`site/samples/model_output_sample.csv` (linked from the tab as "Sample file (made-up values)") gives a variable `sample_index` for 2030 and 2035 in every municipio.
- **Its values are made up:** a repeating pattern, not data.
- **Its header says so:** `model_name: SAMPLE - MADE-UP VALUES (format example only)`.
- **Use:** to try the loader and the comparison only. The observatory publishes no model results.

## Not done in item 15

- **Scoring any set of points, lines or areas** against any series (plan F, "scoring generalized"): the figures a scenario keeps are the route planner's and the visible layers' island values.
- **Levels below the municipio** for model outputs: they wait for the map to draw those levels.
- **Ranges on the map:** the lower and upper values of a model output are not drawn.
