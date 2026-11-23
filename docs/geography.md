# The geography crosswalk and the small-area base

Built 2026-10-06 (plan item 4). Every dataset the observatory holds is reduced to numbers for a list of areas. This guide says what the areas are, how to join data to them, how to move numbers between
areas that do not fit one inside the other, and how to read survey estimates for small areas. The code is `geo.py` (the crosswalk and the outlines), `acs_small.py` (a reader for small-area survey tables) and the block table in `network.py`.

## 1. What was built

| File | What it holds | Size (compressed) | Loaded by |
|---|---|---|---|
| `site/data/geo/crosswalk.json` | One row per area (4,523 in six levels): id, parent, names in Spanish and English, plain form of the name, land area, 2020 residents and housing units, an internal point. Also the barrio-to-tract weights and the totals. | 157 KB | the Economy tab, only when a person asks for the areas below the municipio of a dataset (the CSV by area; `economy.js`, plan item 7) |
| `site/data/geo/tracts.geojson` | Outlines of the 939 census tracts that have land (of 981), for drawing only. | 240 KB | no page yet (decision 27 in `HANDOFF.md`) |
| `site/data/geo/blockgroups.geojson` | Outlines of the 2,513 block groups that have land (of 2,555), for drawing only. | 361 KB | no page yet (decision 27 in `HANDOFF.md`) |
| `cache/network/census_blocks_ids.json` (build only, not published) | The 41,987 census blocks with 15-digit id, residents, housing units, land area and internal point. | 2.3 MB raw | `network.py`, `geo.py` |

Nothing on the first load of any page changed. Only the Economy tab reads the crosswalk, and only after a person asks for the areas of a dataset; no page draws the outlines yet. These files are the base that the layer engine (plan item 6), the exposure series (item 5) and the Census small-area data (item 7) are built on.

## 2. The areas

| Level | Id | Parent | Count | Where it comes from |
|---|---|---|---|---|
| `island` | `72` (the Census code of Puerto Rico) | none | 1 | the blocks, added up |
| `region` | `reg-capital`, `reg-atlantico`, `reg-mar`, `reg-caribe`, `reg-cordillera`, `reg-sol-norte`, `reg-sol-sur` | island | 7 | the Puerto Rico Tourism Company's tourism regions (the only region scheme the observatory holds) |
| `municipio` | 5 digits (`72001`) | region | 78 | Census 2020 counties |
| `barrio` | 10 digits (`7200113645`) | municipio | 901 | Census 2020 county subdivisions that have land |
| `tract` | 11 digits (`72001956400`) | municipio | 981 | Census 2020 census tracts |
| `block-group` | 12 digits (`720019564001`) | tract | 2,555 | Census 2020 block groups |

- An id contains the id of the area it sits in: the first 5 digits of a barrio, tract or block group id are its municipio, and the first 11 digits of a block group id are its tract.
- Keep ids as text. They start with `72`, and an 11-digit tract id is more than a spreadsheet keeps as a number.
- A **census block** (15 digits) is not an area of the crosswalk. Blocks are used only to count: the numbers of every area are the sum of its blocks.
- The 38 county subdivisions named "Municipio subdivision not defined" are offshore water with no land, no residents and no housing units. They are not barrios. The small-area reader drops them and counts them.
- 42 tracts and 42 block groups are all water (no land, no residents, no housing units). They are in the crosswalk but have no outline.
- **Regions are tourism regions.** If a general planning region is adopted, replace or add to this level in `geo.py`; nothing else changes.
- Population and housing units are the **2020 Census** counts. They do not show change since 2020; use the population estimates and survey series for later years.

### The numbers in a row

`fields` in the file names them: `id, parent, name_es, name_en, norm, km2, pop, hu, lat, lng`.

- `km2`: the Census Bureau's land area (AREALAND), water left out, four decimals. It is measured on the Census Bureau's own boundaries, not on the simplified outlines the maps draw, so it can differ from `km2` in `barrios.geojson` (barrio Guayabal in Juana Díaz: 15.31 here, 15.68 there).
- `pop`: residents. The Census Bureau adds statistical noise to block counts to protect privacy, so small areas are approximate.
- `hu`: housing units. The Census Bureau does not add noise to housing-unit counts at block level, so housing units are the better weight for moving numbers between areas. (Group quarters are not housing units: 53 blocks hold 6,503 residents and no housing units; 41 blocks have housing units and no residents.)
- `lat`, `lng`: a point inside the area (the Census Bureau's internal point; for the island and the regions a point inside the union of the municipio outlines). It is not the center.
- `norm`: the Spanish name in lower case without accents, for matching what a person types. **Data joins use ids, never names.**

## 3. Joining data to the areas

```python
import json
cw = json.load(open("site/data/geo/crosswalk.json", encoding="utf-8"))
F = {f: i for i, f in enumerate(cw["fields"])}
by_id = {r[F["id"]]: r for rows in cw["units"].values() for r in rows}
by_id["72001956400"][F["pop"]]          # 2645 residents (2020 Census)
```

```js
const cw = await (await fetch('data/geo/crosswalk.json')).json();
const F = Object.fromEntries(cw.fields.map((f, i) => [f, i]));
const byId = new Map(Object.values(cw.units).flat().map(r => [r[F.id], r]));
```

- A dataset that declares `geography.level` and `geography.key` in `dictionary_src/datasets.json` has its ids checked against the crosswalk by `python contract.py`: more than 1% unmatched fails the build, any unmatched is a warning. `joins_to` may be `region`, `municipio`, `barrio`, `tract` or `block-group`.
- **Adding up** (finer to coarser) is exact for counts: people, housing units, places. Add the children to get the parent. Do not add percentages, medians or averages: work them out again from their parts (numerator and denominator), or weight them by the right count.
- Several files still key municipios by name (`municipalities.json`, the Housing and Economy series). The contract accepts the name or its accent-free form for the municipio level. The six accent-stripping name joins in the pages move to ids when the pages move to the layer engine (plan item 6).

## 4. Moving numbers between areas that do not fit one inside the other

**Barrios and census tracts do not nest.** Both sit inside a municipio, but 489 of the 896 barrios that have residents or housing units (55%) lie in two or more tracts (up to 35), and they hold 81% of the island's residents. 407 barrios lie in one tract. (The research note that proposed the crosswalk, from outline overlap, said 57% and 83%; the counts above are by census block and are the ones to use.)

`weights.barrio_tract` in the crosswalk has one row for each barrio-and-tract pair that share at least one block with residents or housing units: `[barrio, tract, pop, hu, blocks]` (2,057 rows; the 5 barrios with neither have none).

To spread a **count** known for tracts over barrios, split each tract's count among its barrios in proportion to their housing units in that tract, then add up for each barrio:

```
count(barrio b) = sum over tracts t of  count(t) * hu(b, t) / HU(t)        HU(t) = the tract's housing units (the sum of hu(b, t) over its barrios)
count(tract t)  = sum over barrios b of count(b) * hu(b, t) / HU(b)        the same, the other way
```

- For a **rate**, spread its numerator and its denominator as counts and divide; never spread the percentage itself.
- Say what the number is wherever it is shown: "estimated from census tracts using 2020 housing units". Do not show margins of error for it (they cannot be carried across), and never mix it with observed data without that label.
- The method assumes a count is spread over a tract like its housing units. That is often wrong for incomes, rents and poverty. **Prefer the Census Bureau's own barrio rows** when a survey table has them (they are in the small-area reader below).
- An example: the barrio Guaniquilla in Aguada (`7200331318`) has 748 housing units in tract 4302 and 421 in tract 4303, so 64% of its housing units are in the first and 36% in the second.

## 5. Small-area survey estimates (`acs_small.py`)

The American Community Survey 5-year tables give estimates, with margins of error, for the island, the 78 municipios, the 901 barrios, the 981 tracts and the 2,555 block groups. The Census Bureau's table-based files hold the whole nation in one sorted
file per table (18 to 121 MB). `acs_small.py` finds Puerto Rico's rows by binary search with HTTP byte ranges and downloads only them: **0.5 to 1.5 MB per table for all five levels, in 80 to 110 small requests**.

```
python acs_small.py B25077                              # latest vintage, every level, cached under cache/acs_small
python acs_small.py B25077 --vintage 2023 --levels tract,barrio
python acs_small.py --check                             # live: municipio rows equal the ones housing_series.py read
```

```python
import acs_small
r = acs_small.read_table("B25077", levels=["tract", "barrio"])
r["levels"]["tract"]["72001956400"]["B25077_001"]       # [estimate, margin of error (90%)]
```

- Rows whose id is not an area of the crosswalk are dropped and counted (`r["dropped"]`); `r["match"]` gives how many ids were found.
- **Vintages.** The table-based files exist from the 2021 vintage (2017-2021). The vintages 2021 to 2024 all use the **2020 geography** (981 tracts, 2,555 block groups, 939 county subdivisions: every id matches the crosswalk), so no crosswalk is needed between them. Five-year windows that end in 2020 or earlier use the 2010 geography and are in per-sequence files that this reader does not read.
- **Checked.** The municipio and island rows equal what `housing_series.py` read from the same files (395 values, none different). For total population (B01003, 2020-2024) the pieces add up with no difference: block groups to tracts (981), tracts and barrios to municipios (78), municipios to the island.
- **Used by** `small_area.py` (plan item 7, built 2026-10-06), which publishes the barrio, census tract and block group files and the Population domain's series: see `docs/small-area.md` for what is published, how rough each variable is and how it was checked.

### Cautions that every use of small-area estimates must keep

1. Margins of error are at the **90% confidence level**. Do not add or average margins, and do not carry them through a conversion between areas.
2. An **empty value is not zero**. The Census Bureau fills empty values with negative codes (-666666666 and others); the reader turns every code at or below -222222222 into `null`, and a negative margin into `null`. Median gross rent, 2020-2024: no estimate for 45% of block groups (1,155 of 2,555), 13% of tracts and 41% of barrios, against none of the municipios.
3. **Margins are wide.** The typical margin as a share of the estimate (median gross rent): 9% for a municipio, 23% for a barrio, 24.5% for a tract, 32% for a block group. Median household income: 9%, 30%, 25%, 40%. For the share of renter households paying 30% or more of income the typical margin is about plus or minus 18 points for a municipio, 36 for a tract and 55 for a block group. These come from `docs/analysis/small-area-2026-10/small_area_reliability.py`; re-run it after a new vintage. The same measure for every variable the observatory publishes, taken from the published files, is in `docs/small-area.md` (section 4; `python small_area.py --measure`).
4. **Medians and rates cannot be summed** or averaged. Counts add up; percentages are worked out again from numerator and denominator.
5. Adjacent five-year windows share four of their five years: they are not independent, so a change from one window to the next is not a trend to read closely.
6. Estimates are for a five-year window (labelled by its last year) and dollar values are in the dollars of that year. They are not the 2020 Census counts of the crosswalk.

## 6. Outlines for drawing (`tracts.geojson`, `blockgroups.geojson`)

They are the Census Bureau's cartographic boundary files (1:500,000, clipped to a simplified outline of the coast), reduced to the GEOID and rounded to 5 decimals. **Draw them; never measure them.** The Census Bureau says on its description page: "These files should not be used for: geographic analysis including area or perimeter calculation." Areas come from `km2` in the crosswalk,
and anything that needs a distance or an overlay uses the block table. The shapes are in NAD83 longitude and latitude, which the observatory treats as WGS 84 (about a meter apart). The Census Bureau's description page states no copyright or citation rule; the credit line is in `dictionary_src/sources.json` (`census_cartographic`).

## 7. The block table, and why the ids are not published

`network.load_block_table` keeps every 2020 census block of Puerto Rico (41,987; 36,570 with residents; 3,285,874 residents; 1,598,159 housing units) with its 15-digit id. `network.load_blocks` (the transit coverage) and `geo.py` (the crosswalk) both read it, and `population_blocks.json` is unchanged by it:
the published file is the 36,570 blocks with residents, in the same order, without the id. Adding the ids would add 141 KB compressed (45%) to a file the Transit tab loads, so the contract record says `ids_not_published: true`.

Exposure counts (plan item 5, built 2026-10-06: residents or housing units in a flood zone, within 400 m of a stop, and so on, by municipio, barrio and tract; see `docs/exposure.md`) are counted from this table in the build: give each block to the area that holds its internal point, then add residents or housing units. A block is counted wholly in or out of a zone by its one point, so label such figures "computed from block internal points".

## 8. Building and checking

```
python geo.py            # builds site/data/geo/ (downloads once into cache/geo and cache/network)
python geo.py --refresh  # downloads again
python geo.py --check    # checks the published files against each other (no network)
python -m unittest discover -s tests
```

`build.py` runs `geo.build` after the municipality and barrio files are written and before the contract check. `geo.py` **writes nothing and stops** unless the census blocks add up exactly to the Census Bureau's own residents and housing units for all 78 municipios, 981 tracts, 2,555 block groups and 939 county subdivisions (it placed all 41,987 blocks in a barrio by their internal points, none needing the nearest-polygon rule).
`--check` also verifies that ids are unique, every parent exists and is of the right level, residents, housing units and land areas of the children add up to their parent, the weights add up to each barrio and tract, and every outline belongs to a unit.

To publish a new subfolder of `site/data`, add it to `SUBDIRS` in `contract.py` (only `geo` is published today); the contract, dictionary, registry and catalog then see its files under names such as `geo/crosswalk.json`.

## 9. Not done in item 4, on purpose

- The `norm()` name joins in the pages (and the Economy, Housing and chat code) still exist; they move to ids when each page moves to the layer engine (item 6), so that no page loads the crosswalk before it needs it.
- `housing_series.py` still keeps its own municipio reader. `small_area.py` (item 7) reads the same tables through `acs_small.py`, and a test shows that the municipal values of the two are the same (1,716 values in 2020-2024, none different), so the switch can be made later with no change to a published value.
- No page draws the tract or block group outlines yet.
- Per-sequence ACS vintages (windows ending 2020 or earlier, 2010 geography) are not read.
