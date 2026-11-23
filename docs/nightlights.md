# Night-time lights by barrio and municipio (NASA Black Marble; 2026-11-02, branch `data/nightlights-black-marble`)

Live since 2026-11-04 (HANDOFF decision 75, approved 2026-11-03). The first full run (GitHub Actions run 41771300885, 18 minutes) read all 177 months from January 2012 to September 2026. The build uses one free NASA Earthdata token, kept only as the GitHub secret `EARTHDATA_TOKEN`; Francis made the account and the secret with `docs/nightlights-setup.md`, and Claude never saw the token.

## The source

NASA's Black Marble monthly product, **VNP46A3** collection 2 (https://doi.org/10.5067/VIIRS/VNP46A3.002; Román, M.O., et al., 2018, *NASA's Black Marble nighttime lights product suite*, Remote Sensing of Environment 210, 113–143, https://doi.org/10.1016/j.rse.2018.03.017).

- **What it is.** The VIIRS Day/Night Band on the Suomi NPP satellite, every month since January 2012. Each pixel is a monthly composite of clear nights. Moonlight is removed (lunar BRDF correction), and clouds, stray light and snow are screened out. The grid is 15 arc-seconds, about 460 m across at 18° N. The files are HDF5 in tiles of 10 by 10 degrees.
- **Layers read.** `AllAngle_Composite_Snow_Free` (radiance in nW/cm²/sr) and `AllAngle_Composite_Snow_Free_Quality`, which is 0 for good (more than three clear observations), 1 for poor (three or fewer), 2 for gap-filled (none: the value comes from earlier data) and 255 for no value. In collection 2 the radiance is a 32-bit float with fill value −999.9 and scale 1 (Black Marble User Guide v2.0, October 2024, tables 11 and 12). The reader uses the file's own attributes when it has them.
- **Tile.** All of Puerto Rico is in **h11v07** (70–60° W, 20–10° N), from Mona and Desecheo to Culebra and Vieques. h10v07 (80–70° W) holds Hispaniola and no barrio, so it is not downloaded. `tiles_for` works this out from the barrio outlines, and a test checks it.
- **Access.** LAADS DAAC lists the archive openly (`…/archive/allData/5200/VNP46A3/<year>/<day>.json`). A download without a login gets an HTTP 303 to a sign-in page (checked 2026-11-02). The build reads a user token from `EARTHDATA_TOKEN` and sends it only to LAADS, in the `Authorization` header. It never prints, caches or publishes the token. Without the token, the script says so, exits with status 0 and changes nothing.
- **Size.** About 70 MB a month for h11v07. The first run downloads about 177 months (roughly 12 GB). Each file is summarised into `cache/nightlights/summary/YYYY-MM.json` (a few hundred KB) and then deleted, unless `--keep`. Later runs download only months that are new or that NASA reprocessed (a new file name).
- **Licence.** Under NASA's data use guidance, data from a NASA-led mission are CC0 unless marked otherwise, and NASA strongly urges users to cite them. The source card `nasa_black_marble` gives the citation.

## How each figure is made

| Key | What | Unit |
|---|---|---|
| `ntl_radiance` | Mean night-time radiance of the area's pixels | nW/cm²/sr |
| `ntl_poor_pct` | Share of the area's pixels flagged poor or gap-filled | % |

- **Pixels to areas.** A pixel counts in the barrio whose outline (`barrios.geojson`) holds its centre. 43,925 pixels fall in a barrio. Three barrios are smaller than a pixel and hold no centre; each takes the pixel under its representative point, for its own figure only. Pixels over the sea count nowhere.
- **Pooled, not averaged.** A municipio's and Puerto Rico's mean is over all their pixels, each pixel once. It is not an average of barrio means. A year's value pools the pixels of its twelve months. A year with fewer than twelve months appears only in the monthly file, and the series notes say so (`partial_years`).
- **Quality share.** Pixels flagged 1 or 2 over pixels with a quality value. A high share means the month's (or the year's) light rests on few clear nights.

## Files

- `nightlights_series.json`: the yearly values for the 78 municipios and Puerto Rico. It has the shape of `labor_sex_series.json` (`years`, `geo`, `vars[].years`), so `Core.adapters.seriesFile` reads it as is. Each variable names its barrio file (`barrioFile`).
- `nightlights_barrio.json`: the same two variables for the 901 barrios. It has the shape of `landslide_barrio.json` (`level`, `geo.ids`, `vars[].years`), which `economy.js` loads when a layer is shaded by barrio.
- `nightlights_monthly.json`: one value for each area and month (`months`, then `municipio` and `barrio`, each with `ids` and one list per variable). No page reads it yet. It is for the 3D view's time-series panel and the area profiles. Estimated at 1.5–2 MB, which is the medium tier.

`python nightlights.py --check` rebuilds the three files from the cached summaries without the network or a token, and exits 1 when a published file differs.

## Caveats (for the dictionary entries)

- **Clouds.** Puerto Rico is cloudy, especially from May to November. A month with few clear nights is flagged poor (three or fewer) or gap-filled (none), and its value can lag the real light. Read `ntl_poor_pct` with `ntl_radiance`.
- **Moonlight.** The product removes moonlight with a lunar BRDF correction, so bright-moon months are comparable with dark ones. The correction is a model with its own error, largest for dim areas.
- **A proxy, not a count.** Light rises with streetlights, buildings, traffic and industry, and falls in a blackout. It is a proxy for activity and for power. It is not a count of people, jobs or homes with power, and a change can come from new LED streetlights (whiter light, which the sensor sees less of) as well as from activity.
- **Pixel size.** At about 460 m, a small barrio rests on a few pixels, and light spills across borders (blooming), so a dark barrio next to a bright one reads brighter than it is.

## How it is kept current

- **Monthly.** `refresh/sources.json` has a unit `nightlights` and a monthly check (`calendar`, rule `month`). The freshness job starts `rebuild.yml` with that unit; the Rebuild step gets `EARTHDATA_TOKEN` and restores the monthly summaries from the Actions cache (about 5 MB), so it downloads only the new months (about 70 MB each) and opens a pull request that a person reviews.
- **By hand.** `.github/workflows/nightlights.yml` runs the build and keeps the three files with the run as an artifact for 30 days. Start it from the Actions tab once it is on main, or by pushing a tag named `nightlights-run-*`. A tag named `nightlights-diag-*` only reports what LAADS answers for one file (`python nightlights.py --diagnose`), without ever printing the token.
- **The token expires about every 60 days** (this one on 2027-01-02). An expired token stops the rebuild with a clear message and changes nothing. Renew it with step 3 of the setup guide and update the secret.

## First figures (run of 2026-11-04)

- Puerto Rico's mean radiance fell from 6.22 nW/cm²/sr in 2012 to 5.25 in 2016, dropped to 4.23 in 2017 and 4.10 in 2018 after Hurricane María, and was 5.43 in 2025. The decline before María may be partly the change to LED streetlights, whose whiter light the sensor sees less of.
- Month by month: 4.78 in August 2017, 3.98 in September (María struck on the 20th), 1.40 in October, 2.82 in December and 4.50 by June 2018.
- Brightest municipios in 2025: San Juan (47.2), Cataño (38.4), Guaynabo (26.2). Darkest: Maricao (0.5), Vieques (0.7), Las Marías (0.8).
- The quality share is small at the monthly scale (0.2% of Puerto Rico's pixels in 2025): NASA's monthly composite rarely lacks clear nights.
