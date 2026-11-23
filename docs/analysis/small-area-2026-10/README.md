# Small-area survey estimates: how reliable are they in Puerto Rico?

Evidence for the cautions in [`docs/geography.md`](../../geography.md) (section 5) and for the dictionary entry `methods.small_area_estimates`. Written 2026-10-06 with plan item 4. Nothing here is published on the site.

| File | What it is |
|---|---|
| `small_area_reliability.py` | Reads three ACS 5-year tables (median gross rent B25064, median household income B19013, median home value B25077) and, for the share of renter households paying 30% or more of income, table B25070, at each level with `acs_small.py`. Counts the units with no estimate and works out the width of the 90% margin of error. |
| `small_area_reliability.json` | The results of the run on the 2020-2024 window (aggregates only). |

Run it again from the repository root (needs the venv and network access; about 1 minute):

```
venv\Scripts\python docs\analysis\small-area-2026-10\small_area_reliability.py
```

## Results, 2020-2024 window

Units with no estimate, and the typical (median) margin of error as a share of the estimate:

| | Municipio (78) | Barrio (901) | Tract (981) | Block group (2,555) |
|---|---|---|---|---|
| Median gross rent: no estimate | 0 | 372 (41%) | 124 (13%) | 1,155 (45%) |
| Median gross rent: typical margin | 9% | 23% | 25% | 32% |
| Median household income: no estimate | 0 | 111 (12%) | 66 (7%) | 302 (12%) |
| Median household income: typical margin | 9% | 30% | 25% | 40% |
| Median home value: no estimate | 0 | 83 (9%) | 73 (7%) | 217 (9%) |
| Median home value: typical margin | 5% | 17% | 12% | 19% |

Share of renter households paying 30% or more of income (units with 20 or more renter households), typical margin of the share: about plus or minus 18 points for a municipio (78), 36 for a tract (909) and 55 for a block group (2,142).
The margin of a share uses the Census Bureau's approximate formula for a proportion, with the margin of the sum of the four cells (30% to 50% or more of income) and of the denominator (total minus "not computed") each worked out as the square root of the sum of squared margins.

Reading: below the municipio, a median or a share is often too rough to rank areas. Look at the margin before the number.
