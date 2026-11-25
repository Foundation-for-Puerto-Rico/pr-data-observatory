# Public spending: the question test and the next upgrade (decision 109)

Date: 2026-11-17. Status: **choices decided by Claude under the project lead's standing delegation (open plan choices: decide and record), recorded in HANDOFF decision 109; nothing built yet.** This pull request changes no page and builds no data.

**In one paragraph.** A CPA colleague reviewed the Public spending page a second time (2026-11-17). They liked the stage lines and the obligated-and-paid-out card, and suggested choosing one or two concrete questions and testing whether the platform can answer them before adding indicators. The project lead then said "Sí, empieza". This document runs that test for three municipios (San Juan, Utuado and Yabucoa) with the observatory's published files and OpenFEMA. It also answers two points the project lead and the colleague raised: whether to link to ABRE Tu Municipio for municipal finances (yes, and copy nothing), and how much of the budget takes its function from the agency instead of its own program. It ends with the upgrade plan, ordered by what improves the answers most.

## 1. The questions

For one municipio's disaster recovery money:
1. **Obligated:** how much has been committed?
2. **Paid:** how much of that has been paid?
3. **Pending:** how long has it been waiting?
4. **Progress:** what do we know about the projects' progress?

## 2. The test (run on 2026-11-17)

Sources: `site/data/spending_cdbgdr.json` (CDBG-DR and CDBG-MIT subawards by municipio, FY2019 to FY2025), `site/data/spending_pica.json` (capital plan) and OpenFEMA's Public Assistance Funded Projects Details (23,059 Puerto Rico projects, read the same day). FEMA amounts are the federal share obligated. "Open" is OpenFEMA's process step *Obligated*; "pending" is any *Pending …* step; "closed" is *Project Closed Out*. Age counts from each project's first obligation date, weighted by dollars.

| | San Juan | Utuado | Yabucoa |
|---|---|---|---|
| **1 Obligated:** CDBG-DR subawards placed in the municipio | $3,373 M ($10,230 per resident) | $60.0 M ($2,231) | $45.3 M ($1,616) |
| **1 Obligated:** FEMA Public Assistance, projects naming the municipio | $647.7 M (949 projects) | $356.9 M (1,070) | $348.9 M (432) |
| **2 Paid** | not published by municipio | not published | not published |
| **3 Pending:** FEMA open or pending, median age | 4.4 years | 6.6 years | 2.9 years |
| **3 Pending:** FEMA open more than 5 years | $217.7 M | $258.8 M | $83.0 M |
| **4 Progress:** FEMA dollars in closed-out projects | $63.0 M (9.7%) | $29.2 M (8.2%) | $24.0 M (6.9%) |
| Capital plan, FY2026 to FY2029 (planned, not obligated) | $1,218 M | $125.5 M | $21.9 M |

**What the test shows**
- **Question 1 can be answered, with two large caveats.**
  - 78% of FEMA Public Assistance ($30.4 B of $39.1 B) is recorded as *Statewide*: no municipio. A municipio's figure is the part that names it, not its whole recovery.
  - San Juan's CDBG-DR subawards ($3.4 B) are where the work is *reported*. Much of it is island-wide programs run from San Juan, not money for San Juan's residents. This is the colleague's point about location, administration and benefit, in numbers.
- **Question 2 cannot be answered by municipio from any open source a script can read.**
  - USAspending reports no outlays for subawards.
  - OpenFEMA gives obligations, not payments.
  - Payments exist only island-wide, by prime grant: step 2 of decision 96 shows them for grants and contracts, and step 4 will add CDBG-DR. FEMA's payments per project are in COR3's systems, which are out (decision 96 (d)).
- **Question 3 can be answered for FEMA**, from the first obligation date and the process step. For CDBG-DR only the subaward year is known.
- **Question 4 has only a proxy:** whether a FEMA project is closed out. Fewer than 10% of the dollars named in these three municipios are in closed-out projects. No open source gives physical progress. DRGR's quarterly reports describe progress by activity, but as long PDFs.
- **What is truly missing:** payments by project and by municipio, CDBG-DR expenditure by activity and municipio, and physical progress. None of it is in a source a script can read today. The page should say so per municipio rather than leave a blank.

## 3. ABRE Tu Municipio

ABRE Puerto Rico's ABRE Tu Municipio (abretumunicipio.org) publishes a yearly Fiscal Health Index for the 78 municipios, from their audited financial statements. It covers:
- assets, liabilities, revenues, debt and pensions;
- a rating for each municipio;
- a report per municipio and year, at `https://www.abretumunicipio.org/municipio/<slug>?year=2024`. The slug is the name in lower case, without accents, with hyphens for spaces. Tested on 2026-11-17 for 15 municipios, including `san-juan`, `mayaguez`, `juana-diaz` and `las-marias`; an unknown slug gives 404.

**Recommendation: link, do not copy.**
- **It is a different question.** ABRE answers how healthy a municipal government's finances are. The observatory answers what public money, mostly federal and Commonwealth, is assigned in the municipio's territory, and how far it has gone. They complement each other.
- **Their compilation is theirs.** ABRE's website disclaimer (section 7) says the site's design, text, graphics and data compilation are its property, protected by copyright. The underlying public records keep their original terms.
- **Their CSV is not a stable source.** The download is labeled `data_export_test_DEV.csv` and has one year (2023) for 78 municipios.
- **Lean open data.** Copying would duplicate a maintained product, which the project lead asked to avoid.

So the Public spending page's scope note, which says municipal budgets are outside, would link to ABRE Tu Municipio for municipal finances. The municipio view (step 5) would link to that municipio's ABRE report. Municipal budgets and public corporations stay outside the observatory's figures.

## 4. How the budget gets its function (COFOG)

Measured on the approved budget for FY2027 ($33.58 B), with the order `spending.ogp_function` uses:

| Where the function comes from | Share |
|---|---|
| The agency's general function | 74.8% |
| The concept (debt service, pensions) | 10.9% |
| The object of expense | 7.3% |
| The program | 7.0% |

The other years are close: the agency default covers 76% to 80%.

Leaving debt and pensions aside, only nine agencies split their money across more than one function ($5.3 B). The largest are Treasury custody (025, six functions), the Treasury Department (024) and OGP's custody appropriations (017). Every other agency takes one function. So the colleague's concern is where the risk lies: a large agency with mixed work, classified by its general function, hides the mix. Examples are the Health Insurance Administration ($5.4 B, health), the Department of Housing ($3.3 B, housing) and ADSEF ($3.3 B, social services). The page should show this share, and the next crosswalk review should start with the largest agencies classified by default.

## 5. The upgrade plan

Each step is its own PR, merged only on the project lead's word. Every step must improve the answer to at least one of the four questions, or say plainly why it cannot.

1. **Paid out by signing year, visible.**
   - A column chart of the share paid out per signing year, in the "Obligated and paid out" card. Today it is in a hidden table.
   - The text says that an older award with a low share points to where to ask, and does not show non-compliance.
   - First visible step, small.
2. **FEMA Public Assistance by stage and age** (decision 96, step 3):
   - by municipio and island-wide: obligated by stage, and the dollar-weighted age of open projects;
   - the Statewide share stated in the map's title;
   - links to and from the Disaster funding page instead of duplicating it;
   - answers questions 1, 3 and 4 for FEMA.
3. **CDBG-DR draws** (decision 96, step 4): obligated and paid out per grant, checked against HUD's monthly financial report. Answers question 2 island-wide.
4. **How the budget gets its function:** section 4's table on the page, with the agencies classified by default listed by size.
5. **My municipio.** A municipio picker on the Public spending page that gathers what is in the territory:
   - capital plan;
   - CDBG-DR subawards;
   - FEMA by stage and age;
   - federal awards.

   Each item says who runs the money: the agency, the Department of Housing, or the municipio as FEMA applicant. Each of the four questions gets an answer or a plain "not published, and why". Then come a short list of what a municipio or a citizen could request to evaluate execution, and a link to the municipio's ABRE Tu Municipio report.

**Left out**
- DRGR activity reports (PDFs).
- COR3 (decision 96 (d)).
- Contralor.
- Municipal budgets and public corporations' budgets: no open source a script can read. ABRE covers municipal finances.
- No outreach or data requests by FPR. The "what to request" list is text on the page for its readers.

## 6. Decisions (recorded in HANDOFF decision 109)

- (a) **The four questions are the test** each step is checked against.
- (b) **Order:** 1 paid out by signing year, 2 FEMA by stage and age, 3 CDBG-DR draws, 4 how the budget gets its function, 5 My municipio.
- (c) **ABRE Tu Municipio:** link from the scope note and per municipio. Copy no data.
- (d) **Out of scope:** municipal budgets and public corporations stay out. DRGR and COR3 stay out.
- (e) **Compliance:** steps 2, 3 and 5 go through the Compliance review of federal grant content (decision 21), like the rest of the page.
