# Health care providers by type, NPPES registry (decision 107, step 8)

Built 2026-11-18 (row `nppes`). Individual health care providers registered with a practice address in each municipio, by type, from CMS's NPPES registry (NPPES_November_2026_V2.zip).
The code is `providers.py`, the tests are `tests/test_providers.py`, the file is `site/data/providers_series.json`.

## 1. Results for the island

| Key | Type | Registered | Updated within 5 years |
|---|---|---|---|
| `prov_primary_care` | Primary care physicians | 7,296 | 3,302 |
| `prov_psychiatrists` | Psychiatrists | 507 | 193 |
| `prov_other_physicians` | Other physicians (specialists) | 4,572 | 1,911 |
| `prov_dentists` | Dentists | 1,773 | 587 |
| `prov_np_pa` | Nurse practitioners and physician assistants | 591 | 494 |
| `prov_mental_other` | Psychologists, counselors and social workers | 7,539 | 4,107 |
| `prov_pharmacists` | Pharmacists | 3,462 | 1,128 |

The number practicing is likely between the two columns: the registry keeps providers who left or retired, and many who still practice never update a record that is still right.

## 2. Source

The NPPES monthly full replacement file (about 1.1 GB zipped, 9,891,116 national records), read as a stream. Only Puerto Rico's individual providers (entity type 1) are kept, and of them only the primary taxonomy code, practice city and ZIP, last update year and whether the NPI is active: no name, NPI, address or telephone reaches the cache. The registry API's pages were not needed.

## 3. Method

- Type: the provider's primary taxonomy code (NUCC), by prefix: primary care (family medicine, general practice, general internal medicine, general pediatrics, general OB-GYN), psychiatry, other physicians, dentists, nurse practitioners and physician assistants, psychologists, counselors and social workers, pharmacists.
- Place: the practice city when it is a municipio's name; else a known postal place (Hato Rey, Río Piedras and Santurce are San Juan); else the municipio holding most of the land of the ZIP code (Census ZCTA file). The same placement as `nonprofits.py`. 99.9% placed.
- Privacy (decision 107 d): a municipio with 1 to 9 is empty (177 cells); 0 and 10 or more are shown; the island totals are exact.

## 4. Left out on purpose

- **Registered nurses.** Only nurses who bill need an NPI: the registry lists about 1,250 against tens of thousands working in Puerto Rico.
- **Organizations** (entity type 2): hospitals and clinics are already counted from CMS's facility lists (`health_series.json`).

## 5. Reading the numbers

- 14,018 of the 25,740 records counted were last updated more than five years ago.
- One person who practices in several municipios is counted once, at the primary practice location; San Juan gathers many offices.
- No outside count of active physicians by municipio was found to check against; Puerto Rico's practicing physicians, commonly put at about 9,000 to 10,000, fall inside the physicians' range here (5,406 to 12,375).

## 6. Rebuilding

```
python providers.py             # build from cache/nppes/providers_pr.csv
python providers.py --refresh   # newest monthly NPPES file (~1.1 GB), extract Puerto Rico, build
python providers.py --check     # rebuild from the cache and compare (no network)
```

Refresh unit `providers` (local); the freshness check reads the NPPES page for a new monthly file every 30 days.
