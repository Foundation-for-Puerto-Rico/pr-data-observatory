# Daytime population and commuting by municipio (decision 107, step 1)

`commuting.py` writes `site/data/commuting_series.json`: three datasets for the 78 municipios and Puerto Rico, in the group **Population · Daytime population** of the Analysis tab. They are the observatory's first **calculated** layer in the sense of decision 107: arithmetic on published figures, with nothing assumed. (The other two kinds are *overlaid*, one published layer laid on another, and *estimate*, a model with assumptions.)

## What it holds

| Dataset | What it is |
|---|---|
| `daytime_population` | The people in the municipio on a working day: residents, plus workers who come in, minus workers who leave |
| `daytime_change_pct` | Workers who come in minus workers who leave, as a percent of residents |
| `work_elsewhere_pct` | Of the workers who live in the municipio and work in Puerto Rico, the share who work in another municipio |

## Sources (no key)

- **US Census Bureau, County-to-County Commuting Flows, American Community Survey 2016-2020, Table 1**: workers 16 and over by the municipio where they live and the one where they work, each flow with a 90 percent margin of error. It is the file `transit_links.py` reads for the Connections between municipios page; both read the same cached copy. US Government work.
- **US Census Bureau, 2020 Census**: residents of each municipio (`geo/crosswalk.json`).

## How it is calculated

The Census Bureau calls the daytime population the *commuter-adjusted population* and gives the formula: the resident population, plus the workers working in the area, minus the workers living in the area (census.gov, Calculating Commuter-Adjusted Population Estimates). Workers who live and work in the same municipio cancel out, so this is the same as:

    daytime population = residents + workers who come in - workers who leave

- **Workers who come in** live in another municipio or outside Puerto Rico. **Workers who leave** work in another municipio or outside Puerto Rico. 2,657 workers who live in puerto rico work outside it and 1,860 who work in it live outside it; both are counted.
- **Puerto Rico** changes only at its edge: inside it, every worker who leaves one municipio comes in to another. The 78 municipios add up to the island's figure exactly, and a test checks it.
- **`work_elsewhere_pct`** is the figure of the Connections between municipios page (`transit_links.json`), here with its margin of error: it leaves the workers who work outside Puerto Rico out of both sides. A test checks that the two files agree for every municipio. For Puerto Rico the page says 53.3% because it divides by all workers; this dataset says 53.4%.
- **Margins of error** are at 90 percent. The margin of a sum of flows is the square root of the sum of the squares of their margins; the census count has none; the share uses the Census Bureau's proportion formula. A sum of many small flows has a wide margin, and it is published as it comes out.
- **The period** is the flows' five-year window, 2016-2020, labelled by its last year. The residents are those of 2020.

## What it shows (2016-2020)

20 of the 78 municipios have more people on a working day than residents; 58 have fewer. The five that fill most and the five that empty most:

| Municipio | Residents (2020) | Daytime population | Margin | Change | Margin |
|---|---|---|---|---|---|
| San Juan | 342,259 | 450,689 | ±3,342 | +31.7% | ±0.98 |
| Guaynabo | 89,780 | 110,182 | ±2,091 | +22.7% | ±2.33 |
| Cataño | 23,155 | 27,810 | ±1,012 | +20.1% | ±4.37 |
| Mayagüez | 73,077 | 87,071 | ±1,308 | +19.1% | ±1.79 |
| Barceloneta | 22,657 | 26,686 | ±907 | +17.8% | ±4.01 |
| Aguas Buenas | 24,223 | 19,666 | ±684 | -18.8% | ±2.82 |
| Gurabo | 40,622 | 32,735 | ±1,552 | -19.4% | ±3.82 |
| Loíza | 23,693 | 18,774 | ±646 | -20.8% | ±2.73 |
| Trujillo Alto | 67,740 | 52,653 | ±1,281 | -22.3% | ±1.89 |
| Toa Alta | 66,852 | 45,868 | ±1,581 | -31.4% | ±2.36 |

The share of resident workers who work in another municipio runs from 2.7% in Vieques and 3.8% in Culebra to 87.5% in Toa Alta.

## How reliable

- `daytime_population`: no municipio is flagged less reliable (margin above 30% of the estimate).
- `work_elsewhere_pct`: 4 municipios are flagged.
- `daytime_change_pct`: 38 municipios are flagged; in 35 of them the change is under 10 points. The rule compares the margin with the size of the figure, so a change close to zero is flagged even when its margin is small in points. For 72 of the 78 municipios the change is larger than its margin, so its direction (fills or empties) is clear.

## Limits

- **Workers only.** Students, shoppers, patients and visitors also move by day and are not counted.
- **One workplace for each worker**, the one where they worked most in the survey's reference week.
- **Two periods.** The flows are an average of 2016 to 2020; the residents are those of 2020. Remote work has changed since.
- **Municipio level only.** The Census Bureau publishes these flows between municipios, not between barrios or tracts.

## Checks (`tests/test_commuting.py`)

- On invented flows: the formula, the Census Bureau's own form of it, the margins, the island as the sum of the municipios, and the build stopping on a table of another release.
- On the published file: the areas and their order, the municipios adding up to the island, the daytime population equal to residents plus the change, and `work_elsewhere_pct` equal to the Connections page's figure.
- With the cached table: a rebuild gives the published file again (`python commuting.py --check`).

## Refresh

The flows come out about every five years. The refresh unit `transit_links` (`refresh/sources.json`) now also runs `python commuting.py`. A new release needs a person: the file's address and the period are named in `transit_links.py`.
