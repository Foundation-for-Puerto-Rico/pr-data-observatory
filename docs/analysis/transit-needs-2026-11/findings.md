# Where a new route or connection is most needed: findings

Written by `transit_needs.py` for timetables running on 2026-11-10. A planning aid for FPR's review, not a demand forecast or an engineering study. Read `README.md` for the method and its limits; públicos are in no timetable, so a barrio without timetabled service may still have públicos.

## Island summary

- 3,284,650 residents (2020 Census blocks); 7.9% live within 400 m of a stop with a bus every 30 minutes or better through the weekday, 21.5% within 400 m of any stop with a current timetable.
- About 167,247 households have no vehicle (ACS 2020-2024); about 143,806 of them live in the unserved share of their barrio.
- 746 barrios with 500 residents or more are ranked; 18 operators have a timetable running on 2026-11-10.

## The 25 barrios to look at first

| # | Barrio | Municipio | Priority | Need | Car-free households | without useful service | Useful service | Municipal timetable | What the gap points to |
|---|---|---|---|---|---|---|---|---|---|
| 1 | Mayagüez | Mayagüez | 98.1 | 79.7 | 2,919 (31.0%) | 2,919 | 0.0% | none published | new service (no stop with a bus every 30 minutes within 1.5 km) |
| 2 | Machuelo Abajo | Ponce | 98.1 | 85.6 | 1,100 (22.2%) | 1,100 | 0.0% | expired 2024-12-31 | new service (no stop with a bus every 30 minutes within 1.5 km) |
| 3 | Segundo | Ponce | 98.1 | 93.0 | 820 (34.5%) | 820 | 0.0% | expired 2024-12-31 | new service (no stop with a bus every 30 minutes within 1.5 km) |
| 4 | Cayey | Cayey | 97.4 | 79.9 | 1,293 (22.0%) | 1,293 | 0.0% | none published | new service (no stop with a bus every 30 minutes within 1.5 km) |
| 5 | Manatí | Manatí | 97.1 | 87.2 | 748 (37.2%) | 748 | 0.0% | current | more frequent service on the current stops |
| 6 | Coamo | Coamo | 96.8 | 87.5 | 663 (24.6%) | 663 | 0.0% | current | more frequent service on the current stops |
| 7 | San Antón | Ponce | 96.8 | 81.9 | 806 (20.8%) | 806 | 0.0% | expired 2024-12-31 | new service (no stop with a bus every 30 minutes within 1.5 km) |
| 8 | Arecibo | Arecibo | 96.6 | 78.8 | 971 (30.3%) | 971 | 0.0% | no system listed | new service (no stop with a bus every 30 minutes within 1.5 km) |
| 9 | Aguadilla | Aguadilla | 95.9 | 94.9 | 472 (35.7%) | 472 | 0.0% | no system listed | new service (no stop with a bus every 30 minutes within 1.5 km) |
| 10 | Guayama | Guayama | 95.2 | 73.3 | 1,381 (22.0%) | 1,381 | 0.0% | no system listed | new service (no stop with a bus every 30 minutes within 1.5 km) |
| 11 | Caguas | Caguas | 95.1 | 80.6 | 2,069 (23.7%) | 1,856 | 10.3% | expired 2026-01-31 | extend or feed route 30 (Autoridad de Transporte Integrado (ATI)): the nearest stop with a bus every 30 minutes, Ave. Gurabo antes PR-1 Tribunal Judicial, is 615 m from where the unserved residents live |
| 12 | Primero | Ponce | 94.0 | 86.9 | 414 (33.2%) | 414 | 0.0% | expired 2024-12-31 | new service (no stop with a bus every 30 minutes within 1.5 km) |
| 13 | Sábalos | Mayagüez | 93.3 | 72.7 | 727 (18.2%) | 727 | 0.0% | none published | new service (no stop with a bus every 30 minutes within 1.5 km) |
| 14 | Utuado | Utuado | 92.9 | 73.1 | 586 (25.4%) | 586 | 0.0% | current | more frequent service on the current stops |
| 15 | Fajardo | Fajardo | 92.8 | 71.0 | 761 (16.4%) | 761 | 0.0% | expired 2026-06-15 | new service (no stop with a bus every 30 minutes within 1.5 km) |
| 16 | Camaceyes | Aguadilla | 92.7 | 70.3 | 844 (19.3%) | 844 | 0.0% | no system listed | new service (no stop with a bus every 30 minutes within 1.5 km) |
| 17 | Humacao | Humacao | 92.6 | 75.8 | 466 (27.6%) | 466 | 0.0% | current | more frequent service on the current stops |
| 18 | Yauco | Yauco | 92.6 | 83.5 | 356 (33.6%) | 356 | 0.0% | none published | new service (no stop with a bus every 30 minutes within 1.5 km) |
| 19 | Machuelo Arriba | Ponce | 91.7 | 70.4 | 613 (14.5%) | 613 | 0.0% | expired 2024-12-31 | new service (no stop with a bus every 30 minutes within 1.5 km) |
| 20 | Comerío | Comerío | 91.4 | 80.1 | 331 (32.4%) | 331 | 0.0% | none published | new service (no stop with a bus every 30 minutes within 1.5 km) |
| 21 | Juana Díaz | Juana Díaz | 91.4 | 87.6 | 302 (19.2%) | 302 | 0.0% | no system listed | new service (no stop with a bus every 30 minutes within 1.5 km) |
| 22 | Quebrada Grande | Mayagüez | 91.3 | 81.8 | 315 (19.9%) | 315 | 0.0% | none published | new service (no stop with a bus every 30 minutes within 1.5 km) |
| 23 | Aguas Buenas | Aguas Buenas | 91.2 | 94.2 | 282 (43.1%) | 282 | 0.0% | no system listed | new service (no stop with a bus every 30 minutes within 1.5 km) |
| 24 | Playa | Ponce | 91.2 | 67.6 | 863 (16.8%) | 863 | 0.0% | expired 2024-12-31 | new service (no stop with a bus every 30 minutes within 1.5 km) |
| 25 | Capitanejo | Juana Díaz | 91.1 | 78.9 | 345 (26.2%) | 345 | 0.0% | no system listed | new service (no stop with a bus every 30 minutes within 1.5 km) |

Useful service: residents within 400 m (straight line) of a stop with a bus every 30 minutes or better, 7:00-19:00 on a weekday. Low reliability: the margin of error of the no-vehicle share is larger than the share itself. Municipal timetable: the municipality's own system in `operators.json`. **14 of these 25 barrios are in a municipality whose system publishes no timetable or whose timetable has expired**: there the gap may be in the data, not in the service, and the first step is to confirm with the municipality what runs (and to obtain its timetable).

## Where the timetables are current: the gaps the data can show

The same ranking, only the barrios of municipalities whose own system has a current timetable, or that list no system of their own and have ATI stops (the ATI's timetable is current). Here a gap is a gap in the published service.

| # | Barrio | Municipio | Priority | Car-free households without useful service | Useful service | Any current stop | What the gap points to |
|---|---|---|---|---|---|---|---|
| 5 | Manatí | Manatí | 97.1 | 748 | 0.0% | 89.6% | more frequent service on the current stops |
| 6 | Coamo | Coamo | 96.8 | 663 | 0.0% | 78.3% | more frequent service on the current stops |
| 14 | Utuado | Utuado | 92.9 | 586 | 0.0% | 92.9% | more frequent service on the current stops |
| 17 | Humacao | Humacao | 92.6 | 466 | 0.0% | 66.4% | more frequent service on the current stops |
| 40 | Quebrada Negrito | Trujillo Alto | 87.6 | 273 | 0.0% | 0.0% | new service (no stop with a bus every 30 minutes within 1.5 km) |
| 48 | Río | Guaynabo | 85.1 | 219 | 0.0% | 26.1% | more frequent service on the current stops |
| 54 | Medianía Baja | Loíza | 84.8 | 432 | 0.5% | 0.5% | new service (no stop with a bus every 30 minutes within 1.5 km) |
| 56 | Medianía Alta | Loíza | 84.7 | 452 | 0.0% | 0.0% | new service (no stop with a bus every 30 minutes within 1.5 km) |
| 57 | Monacillo | San Juan | 84.7 | 652 | 0.0% | 87.4% | more frequent service on the current stops |
| 58 | Isabel II | Vieques | 84.5 | 198 | 0.0% | 78.6% | more frequent service on the current stops |
| 61 | Cabo Caribe | Vega Baja | 84.2 | 316 | 0.0% | 71.7% | more frequent service on the current stops |
| 62 | Pájaros | Bayamón | 84.0 | 1,519 | 0.0% | 8.5% | new service (no stop with a bus every 30 minutes within 1.5 km) |
| 65 | Maricao | Vega Alta | 83.8 | 300 | 0.0% | 22.1% | more frequent service on the current stops |
| 67 | Guaraguao | Guaynabo | 83.6 | 213 | 0.0% | 90.0% | more frequent service on the current stops |
| 71 | Bajura Adentro | Manatí | 83.3 | 197 | 0.0% | 0.0% | new service (no stop with a bus every 30 minutes within 1.5 km) |

## Connections between operators to look at first

| # | Where | Routes that come close | Closest gap | Residents within 800 m |
|---|---|---|---|---|
| 1 | 18.40743, -66.02996 | ATI 40 (32 trips); San Juan 4 (7 trips) | 392 m | 10,081 |
| 2 | 18.40743, -66.0688 | ATI 8 (32 trips); San Juan 7 (8 trips) | 584 m | 9,132 |
| 3 | 18.39752, -66.00084 | ATI 43 (43 trips); San Juan 4 (7 trips) | 480 m | 7,810 |
| 4 | 18.39837, -66.04354 | ATI 41 (78 trips); San Juan 6A (10 trips) | 686 m | 7,767 |
| 5 | 18.44029, -66.06778 | ATI 10 (106 trips); San Juan 1 (6 trips) | 723 m | 7,594 |
| 6 | 18.41063, -66.05537 | ATI 26 (45 trips); San Juan 7 (8 trips); ATI 40 (32 trips); ATI 41 (78 trips); ATI 17 (30 trips); San Juan 3 (8 trips) | 524 m | 7,224 |
| 7 | 18.45532, -66.07266 | ATI 53 (27 trips); San Juan 2 (6 trips) | 533 m | 7,176 |
| 8 | 18.42969, -66.05858 | ATI 4 (60 trips); San Juan 2 (6 trips) | 635 m | 7,149 |
| 9 | 18.40782, -66.05237 | ATI 40 (32 trips); San Juan 3 (8 trips) | 702 m | 6,948 |
| 10 | 18.37845, -66.12699 | Guaynabo TORR (22 trips); Bayamon BR-3 (12 trips) | 305 m | 6,915 |
| 11 | 18.40133, -66.05188 | ATI 1 (81 trips); San Juan 6A (10 trips); ATI 26 (45 trips); ATI 4 (60 trips); ATI 8 (32 trips) | 528 m | 6,777 |
| 12 | 18.37022, -66.08669 | ATI 27 (41 trips); San Juan 6 (7 trips) | 667 m | 5,425 |
| 13 | 18.44177, -66.11772 | ATI 37 (48 trips); Guaynabo AME (22 trips); ATI CSJ (32 trips) | 324 m | 4,544 |
| 14 | 18.36509, -66.13524 | Guaynabo CANTAG (22 trips); Bayamon BR-3 (12 trips) | 619 m | 4,150 |
| 15 | 18.39347, -66.10567 | ATI 8 (32 trips); Guaynabo TORR (22 trips) | 713 m | 4,148 |

26 pairs of current routes of different operators come within 250 to 800 m of each other with no stops within 250 m, at 19 places (pairs whose closest points are within 400 m count as one place): a short link, a new stop or a timed transfer could join them. Trips are weekday trips in both directions. Every pair is in `connections.csv`.

