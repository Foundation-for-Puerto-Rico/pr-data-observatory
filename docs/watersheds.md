# Watersheds, streams and What drains here (GIS tools step 3)

Plan: `docs/gis-tools-proposal-2026-11.md`, step 3 (HANDOFF decision 93). Code: `watersheds.py` (the data), `site/js/terrain.js` (the map layer), `site/js/studyareas.js` and `Core.study.upstream` (What drains here).

## What visitors get

- **Explore › Environment and climate › Watersheds and streams** (2D map): the 227 subwatersheds (HUC-12) of the USGS Watershed Boundary Dataset as dashed outlines, and the 3,992 streams of NHDPlus High Resolution that drain 5 km² or more, wider for larger rivers. A click on the map names the subwatershed there, its subbasin, area and 2020 residents.
- **Tools › Map tools › What drains here:** pick a point (or use the center of the map) and the land whose rain flows to it becomes a study area, in the set "Areas that drain to points", with the full study-area summary (residents, transit, and on request flood zones, heat, greenness, landslides, slope). The stream network (`catchments.geojson`, about 2.1 MB compressed) loads the first time.

## How it is made (`watersheds.py`)

1. **Sources:** WBD subwatersheds (HUC-12) and subbasins (HUC-8) of subregion 2101, and NHDPlus HR VPU 2101 network flowlines and catchments, from The National Map's ArcGIS services (no key; outlines simplified by the service to about 20 m). Cached in `cache/watersheds/`.
2. **Links downstream:** each catchment shares an NHDPlusID with its flowline; `dn` is the catchment of the flowline's downstream main-path flowline (DnHydroSeq), going on down past short connectors that have no catchment; -1 at an outlet.
3. **Minor branches:** where a river splits, NHDPlus routes the water down the main path, so a minor branch (Divergence 2) has nothing upstream through DnHydroSeq; and some branches start with a connector that has no catchment. Each minor branch's first catchment gets `via`, the catchments of the reaches it splits from (DnMinorHyd), walking down or up past connectors. Without this, four outlets of 72 to 224 km² drained less than 10 km² (found by the build's own check).
4. **Upstream** (in the browser): the catchment under the point, and every catchment whose chain of `dn` or `via` reaches it (`Core.study.upstream`); the catchments become one MultiPolygon (`Core.study.merge`), measured like any study area.
5. **Subwatersheds:** residents are the 2020 census blocks whose point is inside, as the study areas count them (3,285,324 of 3,285,874).

**Checks that stop the build:** 12,000 to 16,000 catchments and flowlines; links valid, without a cycle; catchments adding up to 8,500 to 10,500 km² (they add up to 8,860.4 km²); 200 to 260 subwatersheds; 99% of the residents in one; and the drainage area the network gives within 3% of NHDPlus's own TotDASqKm for the five largest named rivers and the largest minor branch:

| River (largest reach) | The network (km²) | NHDPlus (km²) |
|---|---|---|
| Río Grande De Loiza | 749.5 | 749.5 |
| Río Grande de Arecibo | 654.8 | 654.8 |
| Río Grande de Manati | 592.9 | 592.9 |
| Río Cocal | 586.4 | 586.4 |
| Río de la Plata | 567.6 | 567.6 |
| (no name) (minor branch) | 543.7 | 543.7 |

**In the browser:** the whole Río Grande de Loíza basin is 1,527 catchments, 749.5 km² and about 34,000 points (the study-area limit is 100,000); its summary measures in under half a second.

## Not done here

- Canals and pipes that move water between basins (the network routes water down each river's main path).
- The watersheds layer in the 3D view.
- HUC-10 outlines and flood-zone shares by subwatershed.

## River mouths are not chained along the coast (2026-11-23)

NHDPlus links each river's last reach to the next mouth along the coast. Until 2026-11-23 the network kept those links, so 12,202 of the 13,809 catchments drained to one outlet and What drains here, clicked near the coast, returned most of the island. `watersheds.py` now stops each river at its last reach (NHDPlus `terminalfl`), and the build stops if any outlet drains more land than the largest river. Found while building `upstream.py` (docs/upstream.md).
