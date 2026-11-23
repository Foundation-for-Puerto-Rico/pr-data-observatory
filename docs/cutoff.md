# Residents cut off from hospitals (decision 107, step 9, third part)

Built 2026-11-20 (row `derived-cut-off-communities`). For every municipio and barrio: the share of residents who would have **no open road to any hospital** when the roads in FEMA's 1% annual chance flood area close, when the bridges in poor condition (and those already closed) close, and both.
The code is `cutoff.py`, the tests are `tests/test_cutoff.py` and a test in `tests/core.test.js`, the files are `site/data/cutoff_series.json` (78 municipios and Puerto Rico) and `site/data/cutoff_barrio.json` (901 barrios). It reads only files already in the repository (`roads.bin`, `flood.geojson`, `bridges.geojson`, `gazetteer.json`, `wcrp.geojson`) and the census block cache; it runs in about a minute with `python cutoff.py`.

**An estimate** (decision 107 b): a road-network model, with the word "estimate" in every name, a check and a range below. **A worst case**: the 1% flood everywhere at once and every flooded stretch closed for its whole length. It says which communities depend on roads that can flood, not how many will be cut off in any one storm.

## 1. Results for the island

| Closed | Residents cut off | Share |
|---|---|---|
| Roads in the 1% flood area (`cut_flood_pct`, `cut_flood_res`) | 532,031 | 16.2% |
| of them, whose own street floods | 255,628 | 7.8% |
| of them, on a dry street with every road to a hospital flooded (`cut_flood_dry_pct`) | 276,403 | 8.4% |
| Bridges in poor condition or closed (`cut_bridge_pct`) | 4,478 | 0.1% |
| Both (`cut_both_pct`) | 554,342 | 16.9% |

Shares of the 3,275,791 residents measured. Left out: Vieques (8,245) and Culebra (1,792), which have no road to a hospital with nothing closed (their health centres are not hospitals by the rule below), and 46 residents with no road within 2 km.

Half of those cut off by floods live on a street that stays dry: a flood map alone does not show them. The 1% flood area holds 316,309 residents (the exposure series); 255,628 of them live on a stretch of road that closes, the rest near a raised road or one that stays out of the water.

The highest municipios (floods):

| Municipio | Floods | On a dry street | Residents | Floods or poor bridges |
|---|---|---|---|---|
| Salinas | 84.2% | 43.8% | 21,678 | 84.2% |
| Loíza | 75.8% | 50.6% | 17,962 | 75.8% |
| Dorado | 58.4% | 45.1% | 20,946 | 58.4% |
| Juana Díaz | 42.6% | 29.8% | 19,821 | 42.6% |
| Guánica | 42.5% | 27.4% | 5,856 | 42.5% |
| Cataño | 40.9% | 16.4% | 9,477 | 40.9% |
| Guayanilla | 39.9% | 27.3% | 7,104 | 40.3% |
| Naguabo | 39.0% | 34.7% | 9,121 | 39.0% |
| Ponce | 33.0% | 14.1% | 45,389 | 33.0% |
| Barceloneta | 32.2% | 12.5% | 7,286 | 32.2% |

The two closures together cut off more than each alone where a poor bridge sits on the road left when the floods close the main one: Patillas has 28.2% by floods, 1.0% by bridges and 71.6% by both.

## 2. Method

1. **Test points.** One point every 25 m along each road of the observatory's road graph (`roads.bin`, from OpenStreetMap): 1,232,207 points, 101,194 of them in FEMA's 1% annual chance flood area (`flood.geojson`, SFHA).
2. **Flood closures.** A stretch closes where its points fall in the flood area, except:
   - motorways and trunk roads and their ramps: expressways stand on raised embankments;
   - the span of each bridge the National Bridge Inventory rates good or fair (its point, half its length and 15 m either side): a sound bridge carries the road over the water.
   23,477 road edges have at least one closed point.
3. **Bridge closures.** The road under the point of each bridge rated poor, or listed as closed (status K), within 60 m: 355 bridges, 339 road edges (6 bridges have no road within 60 m).
4. **Hospitals.** The hospitals and medical centres of OpenStreetMap in the observatory's place index (`gazetteer.json`, the rule of `conditions.py`): 73, all on a road. CMS's hospital list is the better source but its API answered 403 on 2026-11-17; OpenStreetMap's list needs no download.
5. **Who is cut off.** Each 2020 Census block with residents is placed on its nearest road joined to the network within 2 km. With the stretches closed, the roads split into pieces (roads read in both directions); a block is cut off when its piece holds no hospital it can reach. Along its own edge, a block reaches an end only if no closed point lies between it and that end; a block whose own stretch is closed is cut off and counted as on a street that floods.
6. A barrio's and a municipio's figure is the share of its residents.

## 3. Range and check

**Range for the island** (in the notes): 14.9% with primary roads also kept open; 24.5% with the 0.2% annual chance area closed too and every road class closed, sound bridges included. The published figure is 16.2%.

**Check against the WCRP community plans.** On 2026-11-20 the WCRP plans were searched for communities that floods or a failing bridge leave cut off ("incomunicada", a single road in, a bridge at risk). Buena Vista (Humacao) is not counted: its plan names landslides, which the model leaves out. For each community, the share of residents within 800 m of its point who are cut off by floods:

| Community whose plan says it is cut off | Cut off in the model |
|---|---|
| La Vega (Río Grande) | 74.9% |
| Mariana (Humacao) | 0.0% |
| Punta Santiago (Humacao) | 100.0% |
| Punta Tuna (Maunabo) | 0.0% |
| Río Blanco (Naguabo) | 0.0% |
| Tropical Beach (Naguabo) | 100.0% |
| Tumbao (Maunabo) | 100.0% |
| Verde Mar (Humacao) | 100.0% |

5 of 8 have half or more cut off (59.4% on average), against 16 of the other 67 WCRP communities (27.7%). The model misses Mariana, Punta Tuna and Río Blanco: their plans describe a quebrada or river that floods the road, and landslides; small streams are often outside FEMA's mapped area.

## 4. Reading notes

- A worst case, not a forecast: in a real storm only some rivers rise, for a few hours, and some flooded roads can still be crossed.
- The town centre is not the test: a town centre in the flood area is often itself cut off. The test is a hospital.
- Landslides, fallen trees and power lines also close roads (Hurricane María); they are not in the model. Private and unmapped roads are missing from OpenStreetMap.
- Poor condition is the National Bridge Inventory's rating of a bridge's parts: it does not mean the bridge will fail. A bridge over another road may close the wrong road.
- The count (`cut_flood_res`) is shaded per 1,000 residents by default on the map: the share times ten.

## 5. Rebuilding

`python cutoff.py` (local; refresh unit `cutoff`). Rebuild when `roads.bin`, `flood.geojson` or `bridges.geojson` change: the FEMA and National Bridge Inventory sources in `refresh/sources.json` say so. `python cutoff.py --check` rebuilds and compares with the published files.
