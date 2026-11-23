# Storm recovery from night-time light (decision 107, step 5, second part; 2026-11-17, branch `data/storm-recovery`)

How long night-time light took to come back after Hurricanes María (2017) and Fiona (2022), and how dark each area got, for the 78 municipios, Puerto Rico and the 901 barrios. The figures are **calculated with a stated rule** from a file the observatory already publishes. They are not an estimate, and they are not the utility's restoration record.

## Input

`site/data/nightlights_monthly.json`: one mean radiance (nW/cm²/sr) for each area and month since January 2012. It comes from NASA Black Marble VNP46A3 (pixels of about 460 m), as read by `nightlights.py` (see `docs/nightlights.md`). `storm_recovery.py` needs no network and no key.

## The rule

- **The year before.** Each month after the storm month (September) is compared with the same calendar month in the twelve months before the storm: October 2017 with October 2016, and so on. Comparing like months cancels out the seasons. Puerto Rico's light is lower in the cloudy autumn months (for example 4.55 in November 2016 against 5.13 in October 2016).
- **Back.** Light counts as back in the first month after September when that month and the next are both at least **80%** of the same months the year before. Requiring two months in a row stops one clear month from counting. The figure counts months from September, so 1 means back by October.
- **Lowest.** The darkest month from September to March, as a share of the same month the year before.
- **Too dim to read.** An area whose mean in the year before is under **0.5 nW/cm²/sr** has no figure. In those barrios the light moves 22% to 68% from one month to the next with no storm, more than the 20% the rule allows (the median month-to-month variation in the year before; 79 barrios before María, 57 before Fiona). Between 0.5 and 1 it moves 14% to 21%, and from 2 up, 6% to 11%.
- **Hurricane Irma** passed north of the island on 2017-09-06, in the same month as María. The 2017 figures cover both storms.

### Why 80% and two months

The wish-list row first suggested 90% for three months. At 90%, the island's light takes 14 months to come back after María, but the restoration record says about 8 months. The light stayed about 10% to 15% under the year before well after power was back, which is consistent with homes left empty, closed businesses and the change to LED streetlights. The 80% line puts the island in the month the record does. The rule's effect, from `notes.sensitivity`:

| Line | Island, María | Barrio median, María | Barrio 90th percentile, María | Island, Fiona |
|---|---|---|---|---|
| 70% | 6 months | 6 | 10 | 1 |
| **80% (used)** | **8** | **8** | **18** | **1** |
| 90% | 14 | 13 | 26 | 1 |

## Checks

- **María, island.** By the rule, the island's light was back by May 2018 (8 months), and its darkest month was 27% of the year before. The restoration record agrees on both:
  - EIA reported 95% of customers restored in mid-April 2018 (eia.gov/todayinenergy/detail.php?id=36832).
  - The Army Corps of Engineers reported 98.4% restored in mid-May 2018.
  - Román et al. (2019, PLOS ONE 14(6): e0218883, doi 10.1371/journal.pone.0218883) measured an 80% drop in the island's light right after María with the daily product, which matches the darkest month here.
- **Fiona, island.** By the rule, the island's light was back by October 2022 (1 month). LUMA reported 90% of customers restored on 2022-10-01 (American Public Power Association, "Power restored to more than 1.3 million customers in Puerto Rico").
- **Fiona, by region.** EAGLE-I records outages every 15 minutes (Oak Ridge National Laboratory, CC BY 4.0, figshare article 24237376, file `eaglei_outages_2022.csv`). Puerto Rico appears in it as seven LUMA regions, each under one municipio code. In each region, the daily peak of customers out fell to 10% of the storm's peak or fewer on these dates:
  - San Juan, Bayamón and Carolina: September 29.
  - Caguas and Arecibo: October 3.
  - Ponce: October 7.
  - Mayagüez: October 10.

  So every region was mostly back within October, with the southwest last. That is where the light fell most: Maricao 41%, Adjuntas 57% and Guánica 58% of the year before. Sabana Grande is the only municipio that took 2 months. The check was run by hand on 2026-11-17. The build does not download EAGLE-I (1.2 GB a year) and publishes nothing from it.

## First figures (2026-11-17)

- **María:**
  - The island's light was back after 8 months. Slowest: Vieques (26 months), Maunabo (25), Salinas (20). Fastest: Hormigueros and San Germán (2), then Cabo Rojo (3).
  - Darkest month: Adjuntas 2%, Orocovis 3% and Ciales 4% of the year before.
  - Barrios: half took 8 months or less, one in ten took 18 or more, and the longest took 66.
- **Fiona:** 77 of the 78 municipios were back by October.
- **What a long time can mean.** It can be a lasting change rather than a long outage. In one barrio of Toa Baja, the light stayed at 55% to 80% of 2016-2017 for five years. A closed business or new streetlights could explain that kind of gap.

## Caveats (also in the dictionary entries)

- **Light, not service.** Light is a proxy for power and activity, not a count of homes with power. It includes streetlights, businesses and traffic. The pages say "light came back", not "power came back".
- **A month is a composite of its clear nights.** An outage of a few days or weeks barely shows. Most customers had power back within two weeks of Fiona, so most areas read 1 month. The storm month mixes nights before and after the storm, so Fiona's darkest month reads well above zero.
- **Small barrios.** Pixels are about 460 m across and light spills over borders, so a small barrio next to a bright one reads brighter than it was.

## Files and how they stay current

- **`storm_recovery_series.json`:** the municipio file, with the 78 municipios and then Puerto Rico. It has the shape of `nightlights_series.json`, with the years 2017 and 2022. `notes` holds the rule, the storms, the counts of dim areas, the sensitivity and the checks.
- **`storm_recovery_barrio.json`:** the same two variables for the 901 barrios, in the shape of `nightlights_barrio.json`.
- **Keeping them current:**
  - `python storm_recovery.py --check` rebuilds both files and exits 1 when one differs.
  - `build.py` runs the script.
  - The monthly rebuild unit `nightlights` in `refresh/sources.json` runs it after `nightlights.py`, so the files follow any month NASA reprocesses.
- **When a new storm comes:** add it to `STORMS`. It needs twelve months of light before the storm, and a few months after it before a figure can be read.
