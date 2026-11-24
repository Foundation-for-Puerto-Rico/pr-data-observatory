# Jobs within reach (decision 107, step 9, fifth part)

Built 2026-11-24 (row `derived-jobs-reach`). For every municipio: how many jobs its residents can reach within **30 and 45 minutes by car**, on average, and what share of Puerto Rico's 943,002 jobs that is.
The code is `jobs_reach.py`, the tests are `tests/test_jobs_reach.py` and a test in `tests/core.test.js`, the file is `site/data/jobs_reach_series.json`. It runs locally in about 20 minutes and needs `scipy`.

**An estimate** (decision 107 b): a road-network model, with the word "estimate" in every name, a check and a range below. Only municipio figures are published.

## 1. Results

Puerto Rico: **236,860** jobs within 30 minutes (25.1%) and **371,661** within 45 (39.4%), on average over residents.

| Municipio | Within 30 min | Share | Within 45 min | Share |
|---|---|---|---|---|
| Guaynabo | 540,462 | 57.3% | 632,281 | 67.0% |
| San Juan | 538,985 | 57.2% | 634,669 | 67.3% |
| Cataño | 533,484 | 56.6% | 634,092 | 67.2% |
| Bayamón | 514,241 | 54.5% | 626,474 | 66.4% |
| Trujillo Alto | 500,894 | 53.1% | 607,038 | 64.4% |
| … | | | | |
| Utuado | 12,116 | 1.3% | 67,544 | 7.2% |
| Orocovis | 8,710 | 0.9% | 35,499 | 3.8% |
| Maricao | 6,895 | 0.7% | 50,990 | 5.4% |
| Jayuya | 5,487 | 0.6% | 32,209 | 3.4% |
| Vieques | 1,507 | 0.2% | 1,514 | 0.2% |
| Culebra | 502 | 0.1% | 502 | 0.1% |

Vieques and Culebra reach only their own island's jobs (no road leaves them). In the mountains (Jayuya, Maricao, Orocovis) the jobs within 30 minutes are a few thousand; within 45 minutes they reach the coast's.

## 2. Method

1. **Jobs.** QCEW's jobs at all employers by municipio, 2025 (`economy_series.json`, `qcew_jobs`): 943,002.
2. **Where in the municipio.** QCEW says how many jobs a municipio has, not where in it. The model spreads them evenly over the municipio's business places: the Overture places (release 2026-10-21.0, confidence 0.5 or more) whose point falls inside the municipio's outline, 83,470 in all. No place, and nothing below the municipio, is published.
3. **Drive time.** The road graph the map uses (`roads.bin`, OpenStreetMap), one-way streets one way, at the observatory's planning speeds by road class (90, 55, 75, 45, 55… km/h; `roads.py`): free flow, no traffic, stops or parking.
4. **From where residents live.** Each 2020 Census block with residents starts from its nearest road node on the network (within 2 km); 54 residents had none. A search from each start node (up to an hour) sums the jobs whose place is within 30 and 45 minutes.
5. A municipio's figure is the average over its residents; the share divides by all of Puerto Rico's jobs.

## 3. Range and check

**Range** (`notes.range`): with each municipio's jobs spread over where its residents live instead of over its business places, the island figure is 224,304 within 30 minutes and 360,639 within 45 (published: 236,860 and 371,661).

**Check against the commuting flows** (US Census Bureau, County-to-County Commuting Flows, ACS 2016-2020, Table 1; the same table as the commuting series). For each pair of municipios, the model's drive time is the residents-weighted average from the home municipio to the job-weighted places of the work municipio. Of the 997,439 workers who live and work in Puerto Rico, **95.9%** work in a municipio within 45 minutes in the model; of the 532,691 who work in another municipio, **92.3%**. The workers who commute between municipios, by the model's drive time:

| Drive time | Workers | Share |
|---|---|---|
| 0-15 min | 81,380 | 15.3% |
| 15-30 min | 325,982 | 61.2% |
| 30-45 min | 84,145 | 15.8% |
| 45-60 min | 35,616 | 6.7% |
| 60+ min | 5,568 | 1.0% |

Most commuting between municipios happens within the model's 45 minutes, so the thresholds describe the trips people actually make.

## 4. Reading notes

- A drive time, not a commute: it assumes a car and free-flowing roads. 13.0% of Puerto Rico's households have no vehicle (ACS 2020-2024), and rush hour in the San Juan area is slower.
- QCEW counts jobs at employers covered by unemployment insurance: the self-employed and informal work are not in it, and a job is where the employer reports it.
- Jobs are where they are now (2025); the flows are of 2016-2020.

## 5. Rebuilding

`python jobs_reach.py --refresh` reads the commuting flows (about 6 MB); `python jobs_reach.py` rebuilds from the cache (local; refresh unit `jobs_reach`). Rebuild with a new QCEW year, a new `roads.bin` or a new Overture release.
