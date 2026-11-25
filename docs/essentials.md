# Road distance to essentials (decision 107, step 6)

Built 2026-11-18 (row `derived-access-essentials`). For every municipio and barrio: how far residents live, **along the roads**, from the nearest supermarket, any food store, pharmacy, bank or cooperativa, library and fire or EMS station, and the share of residents more than 5 km by road from a supermarket.
The code is `essentials.py`, the tests are `tests/test_essentials.py`, the files are `site/data/essentials_series.json` (78 municipios and Puerto Rico) and `site/data/essentials_barrio.json` (901 barrios).

**An estimate** (decision 107 b): a road-network model, with the word "estimate" in every name, a check and a range below. Only distances are published, never the shops.

## 1. Results for the island

| Kind | Places | Mean km (residents) | Median km | Mean km from Overture alone |
|---|---|---|---|---|
| Supermarket (`ess_supermarket_km`) | 553 | 2.81 | 1.97 | 2.94 |
| Any food store (supermarket or colmado) (`ess_grocery_km`) | 1,496 | 1.88 | 1.29 | 1.92 |
| Pharmacy (`ess_pharmacy_km`) | 1,018 | 2.24 | 1.49 | 2.3 |
| Bank or cooperativa (`ess_bank_km`) | 488 | 3.44 | 2.56 | 3.53 |
| Library (map layer) (`ess_library_km`) | 1,099 | 2.41 | 1.78 | — |
| Fire or EMS station (`ess_fire_km`) | 98 | 4.58 | 4.07 | — |

16.0% of residents live more than 5 km by road from a supermarket (17.4% from Overture's places alone).

## 2. Where the places come from

| Kind | Source | Rule |
|---|---|---|
| Supermarket | Overture places, release 2026-10-21.0 (confidence 0.5 or more), and OpenStreetMap supermarkets Overture lacks | A grocery or warehouse-club place whose name is a supermarket's: "supermercado", "supermarket" or a chain (Econo, Selectos, Pueblo, SuperMax, Amigo, Mr. Special, Ralph's, Famcoop, Agranel, Centro Ahorros, Plaza Loíza, Mi Gente, Mega Fresh, Freshmart, Hatillo Kash, Napo, Pitusa, Super Ahorros, Superdescuentos, P&G Cada Día); Walmart, Costco and Sam's Club in a store category. "Colmado", "mini market" and "to go" names are left out. "Pueblo" and "Amigo" count only at the start of a name. |
| Any food store | The same, plus every Overture place of a grocery category | Colmados included. |
| Pharmacy | Overture (pharmacy, drugstore) and OpenStreetMap pharmacies Overture lacks | |
| Bank or cooperativa | Overture (bank, credit union) and OpenStreetMap banks Overture lacks | ATMs are not counted. FDIC branches are not used: since 2023 half sit at the center of their ZIP code (`docs/credit.md`). |
| Library | `libraries.geojson` (USAC E-Rate list, `facilities.py`) | In Puerto Rico the list also holds community, church and university libraries and municipal technology centers, so the label says "a library", not "a public library". |
| Fire or EMS station | `fire_stations.geojson` (USGS), and OpenStreetMap fire stations with no USGS point within 300 m | USGS lacks Jayuya's station. |

"Lacks" means no point of the same kind within 300 m. OpenStreetMap is Geofabrik's Puerto Rico extract (puerto-rico-261117.osm.pbf), read with `osmium`.

## 3. Method

As `care_access.py` and the distance to a general hospital: one shortest-path search over the road graph (`roads.bin`) from every place of a kind at once, in both directions of every road (one-way streets read as two-way: a distance, not a driving route). Each 2020 Census block with residents is snapped to the nearest road within 2 km that reaches a place of the kind; its distance is the road distance to the nearest place plus the straight lines from the block and the place to their roads. A barrio's or municipio's figure is the average over its residents. No travel time is estimated.

Blocks with no road within 2 km, or no road path to a place of the kind, have no figure: 46 residents for most kinds, and Culebra's 1,792 for pharmacies (neither directory lists one there).

## 4. Check and range

- **Check.** Of OpenStreetMap's places, 76.0% of 292 supermarkets, 87.1% of 387 pharmacies and 84.1% of 308 banks have an Overture place of the same kind within 300 m. The rest are added.
- **Range.** The last column of the table: the island figure from Overture alone. Adding OpenStreetMap moves it by 0.1 km or less. A shop that closed but is still listed shortens a distance; that error is not measured.
- **Small towns.** In Maricao, Comerío and Santa Isabel neither directory lists a supermarket by the rule; the food stores there are colmados and "super colmados". The distance to any food store shows it: Maricao is 14.96 km from a supermarket and 5.61 km from a food store on average.

## 5. Rebuilding

```
python essentials.py --refresh   # newest Overture places (~130 MB) and OpenStreetMap extract (~75 MB) into cache/essentials, then build
python essentials.py             # build from cache/essentials/points.json
python essentials.py --check     # rebuild and compare (no network)
```

The refresh unit is `essentials` (local, by hand); the freshness check's `overture` entry (weekly) notes that a new release calls for this rebuild. CI has no cache, so `--check` and the cache tests skip there.

## 6. Not done

- No travel time, and no transit: a road distance says nothing about whether people have a car.
- The shops are not drawn on the map.
- Closed shops are not removed: Overture's places carry no opening status in the 2026-10 release.
