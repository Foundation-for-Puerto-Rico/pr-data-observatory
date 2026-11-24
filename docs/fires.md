# Vegetation fire detections by municipio (`fires.py`)

Step C of the GeoAI sources plan (`docs/geoai-sources-proposal-2026-11.md`, HANDOFF decision 91, approved 2026-11-09). Built on 2026-11-10 on branch `data/active-fires`.

`fires.py` writes `fires_series.json`: three datasets for the 78 municipios and Puerto Rico, in the Analysis tab's group "Environment · Fires (NASA FIRMS)". **No point is published.** A detection is a 375 m pixel, and in a populated area that pixel can hold a house, so the file holds only counts by municipio.

## The source

NASA FIRMS (Fire Information for Resource Management System, part of LANCE) gives active fire detections from the VIIRS instrument at 375 m. The observatory uses one satellite, **NOAA-20**, for every year, so the years compare:

- Suomi NPP stopped sending FIRMS data on 2026-11-02.
- NOAA-21 has no Puerto Rico yearly files yet.

NOAA-20 passes over Puerto Rico about 1:30 in the afternoon and again about 1:30 at night.

FIRMS's data are open with no restriction. Credit: "NASA FIRMS".

The data come in two parts:

| Part | Where from | Key |
|---|---|---|
| Complete years, 2019 to 2025 | FIRMS's yearly country files, `data/country/viirs-jpss1/<year>/viirs-jpss1_<year>_Puerto_Rico.csv` (standard processing; NOAA-20's files start on 2018-04-01, so 2019 is the first complete year) | none |
| The last 12 months | The FIRMS area API for the box -67.95, 17.85, -65.2, 18.55, in 5-day windows (the API accepts 1 to 5 days): `VIIRS_NOAA20_SP` up to the last date it reaches, `VIIRS_NOAA20_NRT` after | FPR's MAP_KEY, only as the GitHub Actions secret `FIRMS_MAP_KEY` |

The key is read from the environment and goes only into request addresses. It is never printed, cached or published. The project lead set the secret himself on 2026-11-10.

## How it is made

- **Which detections count.** In the yearly files, a detection counts when FIRMS's type is 0 (presumed vegetation fire) and its confidence is nominal or high. Low confidence is left out, and so are types 2 (static land source: industry, a power plant) and 3 (offshore).
- **Near-real-time rows have no type.** A detection within 400 m of any place the yearly files mark as type 2 is left out.
- **Places.** A detection belongs to the municipio of the barrio whose outline holds its pixel's centre, or of the nearest barrio within about 500 m. Farther ones, at sea, are left out.
- **Per 100 km².** Detections divided by the Census land area, times 100.

## The figures (build of 2026-11-10)

| Year | Detections in Puerto Rico |
|---|---|
| 2019 | 408 |
| 2020 | 182 |
| 2021 | 222 |
| 2022 | 150 |
| 2023 | 185 |
| 2024 | 143 |
| 2025 | 103 |
| Last 12 months (2025-11-10 to 2026-11-09) | 279 |

The 279 of the last 12 months is close to three times 2025's 103.

- **Where:** 68% of all detections in 2019-2025 fall in the dry south and southwest. Salinas has the most (273 over the seven years), then Ponce (111) and Juana Díaz (106).
- **Per 100 km² in 2025:** Salinas 15.6, Cabo Rojo 8.2 and Añasco 7.9; Puerto Rico 1.2.
- **When:** about 64% of all detections fall in January to April, the dry season.

## Checks that stop the build

- Each complete year has 50 to 2,000 detections in Puerto Rico.
- More than half of all detections fall in the 19 municipios of the dry south and southwest (`SOUTH` in `fires.py`).

`python fires.py --check` rebuilds from `cache/fires/` without the network. `tests/test_fires.py` checks the filters, the placement, the cache with and without a key, and that the published counts add up and match their rates. It also checks that the file holds no point and that the key never reaches the cache or the file.

## Limits

- **A detection is a hot pixel, not a fire.** One fire seen on two passes counts twice, and a large fire fills several pixels. A small fire, or one under clouds or between passes, is not seen. Detections cannot be read as hectares burned.
- **Small municipios jump from year to year.** Read several years together.
- **The last 12 months can still change.** Their most recent weeks are near real time, and FIRMS may reprocess them.

## Refresh and running it

- **Refresh unit `fires`** (`.github/workflows/rebuild.yml`, which gets the secret only for this unit). The source `nasa_firms` is checked every 30 days, and a person reviews each rebuild.
- **`.github/workflows/fires.yml`** builds the file by hand or on a tag named `fires-run-*`. It keeps the file and the downloaded detections as a run artifact, and writes nothing to the repository.
- **`build.py` does not run `fires.py`.** Without the key the last 12 months would drop out, so it runs only where the key is.

To rebuild locally:

1. Download the artifact of a `fires.yml` run.
2. Copy its `cache/fires/` into the repository folder.
3. Run `python fires.py`.
