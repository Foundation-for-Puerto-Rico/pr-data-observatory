# Fixed broadband availability (FCC Broadband Data Collection)

`broadband.py` builds `site/data/broadband_series.json` (78 municipios and Puerto Rico) and `site/data/broadband_barrio.json` (901 barrios): for each June release of the
FCC's Broadband Data Collection since 2023, how many broadband serviceable locations each area has, the shares served, underserved and unserved in NTIA's BEAD terms,
the locations below 100/20 Mbps, and the share where fiber is available. HANDOFF decision 94.

## What the figures say, and what they do not

Availability is what internet providers report to the FCC that they can install at a location within ten business days. It is not what anyone subscribes to (the
survey's "Households with an internet subscription" says that) and it is not the speed anyone gets. Providers' reports can be challenged; the FCC republishes a release
as challenges are settled.

| Key | Dataset | How it is made |
|---|---|---|
| `bb_locations` | Broadband serviceable locations | Every location in a fixed broadband file of the release (satellite is reported for almost all of them) |
| `bb_served_pct` | Served, 100/20 Mbps or more (%) | Best low-latency service over a reliable technology is 100/20 Mbps or more |
| `bb_underserved_pct` | Underserved, 25/3 to 100/20 (%) | Best such service is 25/3 or more but below 100/20 |
| `bb_unserved_pct` | Unserved, below 25/3 (%) | No such service of 25/3 or more (satellite or unlicensed fixed wireless may still be there) |
| `bb_below100_n` | Locations below 100/20 | Underserved plus unserved: the locations BEAD can fund |
| `bb_fiber_pct` | Fiber available (%) | Any provider reports fiber to the premises, at any speed |

Reliable technologies (BEAD): copper (code 10), cable (40), fiber to the premises (50), licensed fixed wireless (71) and licensed-by-rule fixed wireless (72), with the
file's low-latency flag (100 ms or less). Geostationary and low-orbit satellite (60, 61), unlicensed fixed wireless (70) and other (0) do not count for the tiers.

## Method

1. List the releases (`listAsOfDates`) and keep the June 30 release of each year from 2023. June releases compare year to year; December releases are not used.
2. For each release, download Puerto Rico's state files (category State, subcategory Location Coverage, technology type Fixed Broadband): one CSV per technology,
   one row per location, provider and technology, with the maximum advertised download and upload speeds, the low-latency flag and the 2020 census block.
3. Give each location its best tier and its fiber flag; count locations by census block. The block counts are kept in `cache/broadband/blocks_<as of>.json`.
4. Add the blocks up: to the municipio by the first five digits of the block id, and to the barrio by the block's internal point (`geo.block_barrios`). The barrios add
   up exactly to the municipios and the municipios to Puerto Rico.
5. Checks that stop the build: each release has 900,000 to 1,500,000 locations; every municipio has locations; no location falls outside the 78 municipios; at most
   0.1% fall in a block with no barrio.

Check against another copy of the same data (2026-11-10): for June 2025 the build counts 1,108,862 served locations in Puerto Rico; Esri's Living Atlas layer "FCC
Broadband Data Collection December 2025", built from the same FCC files with the same BEAD tiers, gives 1,109,321 for six months before December 2025 (0.04% apart).
Esri's copy is not used as a source because its licence is Esri's, not the public domain.

## Results in the first build (2026-11-10)

| As of June 30 | Locations | Served | Underserved | Unserved | Fiber |
|---|---|---|---|---|---|
| 2023 | 1,179,988 | 91.1% | 2.7% | 6.2% | 46.3% |
| 2024 | 1,178,149 | 95.1% | 1.4% | 3.5% | 62.9% |
| 2025 | 1,178,387 | 94.1% | 1.8% | 4.1% | 63.2% |
| 2026 | 1,177,315 | 95.4% | 1.2% | 3.4% | 70.6% |

In June 2026 the lowest served shares were Yabucoa (63.4%), Maricao (67.7%) and Barranquitas (73.2%); 66 barrios had less than half their locations served.
The 2024 release has no geostationary satellite file for Puerto Rico; the location count still comes from the other files (low-orbit satellite covers nearly all).

## The FCC account (done once)

The public data API needs a free FCC account and an API token. The project lead created them on 2026-11-10 (CORES username, no FRN needed: an FRN is only for filers), and the
two values are the repository secrets `FCC_BDC_USERNAME` (the CORES email) and `FCC_BDC_HASH` (the token from broadbandmap.fcc.gov > username > Manage API Access).
They are never printed, written to the repository, the cache or the site. To renew the token: sign in at broadbandmap.fcc.gov, Manage API Access, generate a new token,
and replace the secret `FCC_BDC_HASH` (Settings > Secrets and variables > Actions).

## Running it

- In GitHub Actions: the workflow "Fixed broadband (FCC Broadband Data Collection)" (`.github/workflows/broadband.yml`), started by hand or by pushing a tag
  `broadband-run-*`; it keeps the two files and the block summaries as an artifact. A tag `broadband-diag-*` only lists what the API offers. The monthly refresh
  unit `broadband` (`rebuild.yml`, `refresh/sources.json`) opens a pull request when a new June release appears.
- Locally, with the cached block summaries: `python broadband.py --check` rebuilds both files and says whether they match (no network, no secret).

## The Knowledge Area page

`broadband.html` (HANDOFF decision 99) reads the two published files and `barrios.geojson`: Puerto Rico now and since 2023, a barrio map by the share of
locations below 100/20 Mbps (or unserved, or with fiber), the municipios and barrios with the largest gaps, and each municipio's share in each year. It is
written by `docs/analysis/broadband-2026-11/make_page.py`; rerun it and `python i18n.py` after a new release.

## Privacy and licence

The FCC files are works of the US Government (no US copyright). The location list behind them (the Fabric) is licensed by CostQuest Associates and is not used: the
public files carry each location's census block, and the observatory publishes no location id, address, coordinate or provider list, only counts and shares by area.

## The map layer (decision 101)

`broadband_hex.geojson` draws the newest June release on the 2D map and the 3D view (Layers > Infrastructure and mobility > Communications, `l=broadband`): one hexagon for each H3 resolution-8 cell (about 0.74 km²; the FCC gives every location its cell in `h3_res8_id`) with 10 or more locations, shaded by the share below 100/20 Mbps in the classes of the Broadband gaps page. The pop-up gives the locations and the shares below 100/20, unserved and with fiber; no address or provider. Cells with fewer than 10 locations are counted in the file's notes and not drawn (3,800 cells, 15,256 locations as of 2026-06-30).

The layer lives in the shared list `site/js/core/facilities.js` (an area layer: `area: { prop, breaks, colors }`), which both renderers draw, so a new map that draws that list gets it with no more work. The build keeps the cells of the newest release in `cache/broadband/hex_<as of>.json` and reads that release again only when they are missing; `python broadband.py --check` checks the hexagons too.
