# Exposure series: how much does counting a block whole change a count?

Evidence for the cautions in [`docs/exposure.md`](../../exposure.md) (sections 5 and 6) and for the dictionary entry `exposure.method`. Written 2026-10-06 with plan item 5. Nothing here is published on the site.

| File | What it is |
|---|---|
| `block_edge_bounds.py` | Downloads the 2020 census block outlines once (about 40 MB, into `cache/network/blocks_geom`), samples each block with a grid of points about 60 m apart, tests every sample against the polygon families of the exposure series (FEMA flood areas, NOAA sea level rise at 1, 3 and 10 ft, USGS protected areas) and makes the two comparisons below. About 4 minutes in all, 2 of them the download. |
| `block_edge_bounds.json` | The results of the run on the 2026-10-06 build (aggregates only). |

Run it again from the repository root (needs the venv and network access; run `python exposure.py` first so the published files and the NOAA geodatabase are in place):

```
venv\Scripts\python docs\analysis\exposure-2026-10\block_edge_bounds.py
```

`tests/test_exposure.py` fails when the published counts are no longer the ones this analysis was run on, and when the dictionary text quotes a figure that this file does not hold.

## The question

`exposure.py` gives a census block to a layer by its one internal point: all of the block's residents are counted in the layer, or none are. A block that the layer's edge cuts is therefore counted too high or too low. How much?

## 1. Bounds that assume nothing

The true count lies between the residents of blocks that lie **wholly inside** the layer (lower bound) and the residents of **every block the layer touches** (upper bound), whatever the way people live inside a block. The internal-point count lies between them in every area, at every level, for every layer tested (and so do the housing units).

| Island, residents | Lower bound | Counted (internal point) | Upper bound |
|---|---|---|---|
| 1% annual chance flood area | 5.1% | 9.6% | 24.1% |
| 1% or 0.2% annual chance flood area | 8.4% | 13.8% | 28.9% |
| Sea level rise, 1 ft | 0.0% | 0.3% | 2.3% |
| Sea level rise, 3 ft | 0.0% | 0.8% | 3.7% |
| Sea level rise, 10 ft | 3.4% | 6.5% | 11.0% |
| Protected area | 0.0% | 1.8% | 8.9% |
| Strictly protected area | 0.0% | 0.9% | 2.9% |

The ranges are wide because rivers, coasts and park edges cut through many blocks. They are the largest possible error, not the likely one. They are also wider than they need to be near the coast: block outlines run out into coastal water, and NOAA's sea level rise areas are land, so a coastal block can never be wholly inside one (the lower bound is low); protected-area outlines can include sea (the upper bound is high).

## 2. Residents spread evenly over each block's area

On the blocks with no water (outline area within 3% of the Census land area: 36,152 blocks, 98.9% of residents), spread each block's residents evenly over its outline and count the share inside the layer. Compare with the internal-point count:

| Layer, residents | Island, internal point | Island, by area | Municipio: middle and largest difference | Barrio or tract: 9 in 10 differ by less than | Largest barrio or tract difference |
|---|---|---|---|---|---|
| 1% flood area | 9.5% | 10.5% | 1.0 and 7.1 points | 6.2 points | 45 points |
| 1% or 0.2% flood area | 13.6% | 14.6% | 1.1 and 6.8 points | 6.5 points | 41 points |
| Sea level rise 1 ft | 0.3% | 0.2% | 0.0 and 1.4 points | 0.5 points | 43 points |
| Sea level rise 3 ft | 0.7% | 0.8% | 0.1 and 3.8 points | 1.2 points | 74 points |
| Sea level rise 10 ft | 6.3% | 6.6% | 0.1 and 11.2 points | 4.4 points | 55 points |
| Protected area | 1.7% | 1.5% | 0.3 and 2.7 points | 3.3 points | 39 points |
| Strictly protected area | 0.9% | 0.8% | 0.2 and 3.0 points | 1.9 points | 66 points |

"Points" are percentage points of the area's own residents. There are 78 municipios, 896 barrios and 933 census tracts with residents.

Reading: for the island and for most municipios the two ways of counting agree to about a point of residents. For a barrio or a tract, one in ten differs by several points (flood areas: more than 6), and a few by a great deal, so small-area counts should be shown beside their totals and called approximate. The internal-point count is lower than the area-weighted count for the flood areas (by about 1 point of the island's residents) and for sea level rise at 3 and 10 ft; it is higher for protected areas and at 1 ft. Neither way is "right": the area-weighted count assumes people are spread evenly over a block, and homes are not.

## Method notes

- Each block outline is sampled with a regular grid (about 60 m apart, 5 to 40 points on a side, only the points inside the block) plus the block's internal point; 2,456,925 points in 36,611 blocks (blocks with no residents and no housing units are skipped). "Wholly inside" means every sample is inside the layer; "touched" means any is. A sliver thinner than the grid can be missed, so the bounds are close, not exact.
- The outlines come from TIGERweb layer 10 (2020 blocks) generalised by about 2 m. The layers are the ones `exposure.py` reads (`flood.geojson`, `protected.geojson`, and NOAA's `PR_slr_{n}ft`).
- Housing units give the same picture (the JSON holds both measures).
