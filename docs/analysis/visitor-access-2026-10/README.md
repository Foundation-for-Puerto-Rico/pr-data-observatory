# Visitor access to transport: evidence for the 2026-10-05 analysis

This folder holds the evidence behind [`docs/visitor-transport-access-2026-10.md`](../../visitor-transport-access-2026-10.md), the note that says how to link tourism places to
transport options and when to do it. Nothing here is published on the site and nothing here changed `site/`.

| File or group | What it is |
|---|---|
| `REPORT.md` | The full spike report (answer, definitions, five questions, recommended method, data problems, limits). Every number in the design note comes from here. |
| `EXTERNAL_DATA.md` | Open data outside the repository that could feed the analysis (ferries, airports, cruise, taxi fares, walkability, demand weights): what was checked, what passed, what is blocked and who to ask. The 21 resulting rows are in `site/data/wanted.json`; `wanted_rows_added.json` is a copy. |
| `common.py`, `service.py`, `walknet.py`, `csa.py` | Shared code: projection, stop sets and feed status, walking engine, timetable scan. |
| `01_…` to `07b_…`, `05_problems.py`, `06_design_numbers.py`, `make_report.py` | One script per question. Each prints its steps and writes a `q*.json` or `q*.csv` next to itself. |
| `99_privacy_scan.py` | Compares every text output with the business names, addresses and websites in `places.json` and with e-mail patterns. |
| `q*.json`, `q*.csv`, `stop_sets.json`, `report_numbers.json`, `tables.md`, `timings*.json` | The results (aggregates only). |
| `run_all.py` | Runs every script in order and records the wall-clock time of each. |

## Run it again

From this folder, with the repository's virtual environment (needs `numpy`, `pyproj` and `shapely`):

```
..\..\..\venv\Scripts\python.exe run_all.py
```

It reads `site/data/*`, the repository's `roads.py` and `municipalities.py`, and the cached OpenStreetMap extract `cache/roads/puerto-rico.osm.pbf` (not in git: `roads.py` downloads it from Geofabrik, about 74 MB,
the first time `python build.py` needs the road graph). It takes about two minutes on a quiet machine. It writes only into this folder: large intermediates (`*.npz`, `*.npy`, `*.pkl`, `logs/`) are ignored by git.
The first script alone (`01_baseline.py`, about 4 seconds) reproduces the headline figures; a re-run from this location gave results identical to the original.

Feed status is computed against the date in `common.py` (`AS_OF = 2026-10-05`). Change it to see how many feeds have expired on a later day.

## Privacy

Aggregates only. No business name, address, website, phone number or e-mail address from `places.json` is reproduced: `99_privacy_scan.py` found none (the only matches are generic phrases and public
place names such as Old San Juan). `q3_gateways.json` names only airports, ferry terminals and stations. Keep it that way when adding outputs, and follow the standing rule: never publish business
contact details or any personal data.

## Limits

One snapshot (places and stops built 2026-10-02), one day type per timetable scan, estimates for walking and driving, no field validation. See section 9 of `REPORT.md`.
