# What lies upstream of each reservoir and river gauge (decision 107, step 9, fourth part)

Built 2026-11-23 (row `derived-upstream`). For each of the 25 reservoirs and 71 river gauges on the map: the land whose rain runs to it, and the residents, housing units, buildings, wastewater treatment plants and protected land on that land.
The code is `upstream.py`, the tests are `tests/test_upstream.py`, the file is `site/data/upstream.json`, and the figures show on the Reservoirs page (section 4, `js/reservoirs_upstream.js`).

**Overlaid** (decision 107 b): published layers added up along the stream network. A count on the land upstream says what is there, not what reaches the water.

## 1. The reservoirs

| Reservoir | Land that drains to it (km²) | USGS drainage area (km²) | Residents | Buildings | Wastewater plants | Protected land (%) |
|---|---|---|---|---|---|---|
| Carraízo (Lago Loíza) | 530.3 | 538.7 | 281,551 | 180,720 | 3 | 3.0 |
| La Plata | 467.1 | 468.8 | 157,661 | 109,519 | 5 | 4.7 |
| Dos Bocas | 446.6 | 438.9 | 51,944 | 45,382 | 3 | 9.3 |
| Lago Coamo | 178.8 | 172.5 | 29,876 | 24,718 | 0 | 0.8 |
| Guayabal | 112.4 | 112.1 | 22,267 | 15,912 | 0 | 1.4 |
| Guajataca | 73.6 | 60.3 | 17,254 | 14,603 | 1 | 3.8 |
| Caonillas | 128.2 | 125.4 | 14,920 | 13,224 | 1 | 13.1 |
| Cidra | 21.7 | 21.4 | 12,198 | 8,724 | 0 | 0.1 |
| Toa Vaca | 59.7 | 57.0 | 4,180 | 3,591 | 0 | 2.0 |
| Patillas | 67.1 | 66.3 | 2,697 | 2,895 | 0 | 23.7 |
| Guayo | 26.1 | 24.9 | 2,185 | 2,101 | 0 | 2.1 |
| Cerrillos | 47.5 | 45.1 | 1,766 | 1,985 | 0 | 9.8 |
| Lucchetti | 45.1 | 45.1 | 1,638 | 1,859 | 0 | 2.1 |
| Loco | 22.3 | 21.6 | 1,373 | 1,094 | 0 | 43.9 |
| Lago Vivi | 20.5 | 16.9 | 928 | 1,130 | 0 | 2.1 |
| Carite | 21.5 | 21.2 | 828 | 1,106 | 0 | 26.6 |
| Garzas | 12.3 | 15.9 | 723 | 706 | 0 | 41.6 |
| Matrullas | 11.3 | 11.6 | 691 | 670 | 0 | 22.5 |
| Guineo | 5.3 | 4.2 | 84 | 59 | 0 | 52.7 |

Six reservoirs are off the stream, fed by canals or pumps, and USGS publishes no drainage area for them: Fajardo, Lago Adjuntas, Lago Dagüey, Lago Melania, Lago Regulador de Isabela, Río Blanco (Lago Blanco). The stream network cannot say what feeds them, so they have no figures.

## 2. Method

1. **The land.** The NHDPlus HR catchments of "What drains here" (`catchments.geojson`, `watersheds.py`), each linked to the next one downstream (`dn`) and, at a split, to the reach it splits from (`via`).
2. **Placing a site on its stream.** A gauge's or dam's point often falls in a small catchment on the river bank, not in the river's own reach. Each site is placed, within 300 m, on the catchment whose flowline bears the site's river name and drains the most land; else, within 150 m, on the catchment that drains the most land; else on the catchment that holds its point. The rule uses names and distance only, not USGS's drainage area, so the check below stays independent. On 2026-11-23: 71 sites by name, 25 by the largest stream nearby.
3. **Splits.** A split is followed only when both branches reach the same mouth: a link between two rivers is a canal or a transfer, not land upstream (53 such links not followed).
4. **Counts.** Residents and housing units: the 2020 census blocks whose internal point is on the land. Buildings: the footprints of the map's building layer (Overture, release 2026-10-21.0) whose point is on it. Protected land: the area of PAD-US protected areas inside it, proclamation boundaries left out (as the exposure series). Wastewater plants: EPA's publicly owned treatment works (FRS interest type POTW) whose permit is effective or administratively continued: 51 of 63 records, read 2026-11-23. They are public facilities and are named.

## 3. Check against USGS

USGS publishes a drainage area for 87 of the sites (NWIS site service, read 2026-11-23). The land found here is within 25% of it for **73** of them; the median ratio is 1.03. The rest are marked on the page:

| Site | Land found here (km²) | USGS (km²) | Ratio |
|---|---|---|---|
| Guineo (reservoir) | 5.3 | 4.2 | 1.26 |
| Quebrada Josefina (gauge) | 38.5 | 9.8 | 3.93 |
| Quebrada Margarita (gauge) | 2.2 | 5.2 | 0.42 |
| Río Cayaguás (gauge) | 33.6 | 26.2 | 1.28 |
| Río Espíritu Santo (gauge) | 34.1 | 22.3 | 1.53 |
| Río Grande de Loíza (gauge) | 32.8 | 15.5 | 2.12 |
| Río Guajataca (gauge) | 15.3 | 8.2 | 1.87 |
| Río Jacaguas (gauge) | 4.3 | 133.4 | 0.03 |
| Río Portugués (gauge) | 15.5 | 30.3 | 0.51 |
| Río Sabana (gauge) | 12.9 | 10.3 | 1.25 |
| Río Tanamá (gauge) | 71.9 | 46.6 | 1.54 |
| Río Tanamá (gauge) | 136.4 | 57.5 | 2.37 |
| Río de Bayamón (gauge) | 3.4 | 1.1 | 3.09 |
| Río de Bayamón (gauge) | 27.5 | 21.5 | 1.28 |

The Río Tanamá gauges are in the northern karst, where water sinks and runs underground, so the surface land and USGS's figure differ. Small gauges near a larger river can be placed on the larger one. Sites with no USGS drainage area (gauges: Río Camuy, Río Guajataca, Río Loco) are marked "not checked".

## 4. A fix to the catchment network (watersheds.py)

Building this step found that NHDPlus links each river's last reach to the next mouth along the coast, so the published network chained the island's rivers: 12,202 of the 13,809 catchments drained to one outlet, and "What drains here" clicked near the coast returned most of the island. `watersheds.py` now stops each river at its last reach (`terminalfl`), and a new build check stops the build if any outlet drains more land than the largest river. The mouths of the five largest rivers still match NHDPlus exactly.

## 5. Reading notes

- A count is not a load: a wastewater plant may discharge below the reservoir, and most homes outside the towns are not on a sewer.
- In the northern karst, water also moves underground: the surface land is not all the water that arrives.
- Some reservoirs also receive water piped or channeled from another basin.
- Impaired waters (EPA ATTAINS) were in the plan but are not added: the ATTAINS file is not in the local cache.

## 6. Rebuilding

`python upstream.py --refresh` reads EPA's plants and USGS's drainage areas (seconds); `python upstream.py` rebuilds from the cache (local; refresh unit `upstream`). Rebuild after `watersheds.py`, `buildings.py` or a new census table.
