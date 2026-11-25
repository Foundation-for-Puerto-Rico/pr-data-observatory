# Credit: bank offices, deposits and home loans (decision 107, step 4)

`credit.py` writes `site/data/credit_series.json`: six yearly datasets for the 78 municipios and Puerto Rico, in two groups of the Analysis tab.

| Group | Dataset | Years | Source |
|---|---|---|---|
| Economy · Banks and deposits (FDIC) | `bank_branches`: offices of FDIC-insured banks | 2000-2026 (June 30) | FDIC Summary of Deposits |
| | `bank_deposits`: deposits booked at those offices, dollars of each year | 2000-2026 | FDIC Summary of Deposits |
| Housing · Home loans (HMDA) | `hmda_loans`: home loans made | 2018-2025 | HMDA Data Browser |
| | `hmda_purchase_loans`: loans to buy a home | 2018-2025 | HMDA |
| | `hmda_loan_amount`: their amount, dollars of each year | 2018-2025 | HMDA |
| | `hmda_denial_pct`: share of decided applications denied | 2018-2025 | HMDA |

Both sources are read with no key:

- **FDIC:** `api.fdic.gov/banks/sod`, filter `STALPBR:PR`, every year since 2000, paged by 10,000 rows. Each office is counted in the municipio the FDIC gives it (`STCNTYBR`).
- **HMDA:** `ffiec.cfpb.gov/v2/data-browser-api/view/csv?states=PR&years=<year>`, about 10 MB a year, one row for each application. The refresh asks for the next year until the Data Browser has none. 2018 is the first year of the current record layout.

## What it shows

- **Bank offices fell by more than half.** Puerto Rico had 571 offices in 2006 and 260 on June 30, 2026. Most were lost in San Juan (68), Carolina (24), Ponce (22) and Bayamón (21). In 2026 Cataño and Guánica have no FDIC-insured office.
- **Deposits** were $85.5 billion in 2026 ($30.4 billion in 2000, in dollars of each year), and San Juan holds $56.2 billion of them.
- **Home loans:** 14,269 loans made in 2025, worth $2.86 billion. Lending peaked in 2021 (21,197 loans), when refinancing rose with low interest rates.
- **Denials:** 18.5% of decided applications were denied in 2025, down from 26.2% in 2018. The highest shares were in Guánica (39.5%), Maunabo (35.5%) and Villalba (31.2%).

## Rules

- **HMDA rows describe single borrowers** (income, age, race, sex). Only municipio counts and sums are published. A municipio-year with fewer than 10 loans has no amount, and one with fewer than 10 decided applications has no denial share (`MIN_LOANS`). Census tracts are not published.
- **Loans bought from another lender** (HMDA action 6) are left out: they are not new lending and would count a loan twice.
- **A decided application** is one that was made (1), approved but not taken (2) or denied (3). Withdrawn and incomplete applications are not decisions.
- **Rows with no municipio** count in Puerto Rico's figure only (62 in 2025).

## What it does not say

- **Cooperativas are not counted.** The cooperativas de ahorro y crédito are insured by COSSEC, not the FDIC. A municipio with no bank office may still have a cooperativa.
- **Deposits are where the bank books them**, not where the depositors live. A main office books far more than its share.
- **Small lenders** below HMDA's reporting thresholds are missing, so the loan counts are less than all home lending.
- **Loan amounts** are the midpoint of each loan's $10,000 band in the public file, so a sum is within $5,000 a loan of the true amount.
- **A denial share** does not say why. Income, debts, credit and the home all count, and the share does not separate them.
- **Dollars are not adjusted for inflation.**

## Why there is no map of bank offices

Since 2023 the FDIC places about half of Puerto Rico's offices at the center of their ZIP code. Their geocode is "M", the same point as the "US_Zipcode" match of 2022. In June 2026 only 113 of the 260 offices have a location at their street or address. A points layer would put half the banks where they are not, so the observatory counts the offices by municipio and draws none. Geocoding the offices' addresses is left for step 6 (access to essentials), which needs bank points.

## Rent vouchers: not published

HUD's Housing Choice Vouchers by Tract (up to December 2025) leaves out every tract with 10 or fewer voucher holders. In Puerto Rico, 766 of the 942 tracts have no value. The 176 tracts shown hold 5,841 vouchers, while HUD's housing authority file counts 26,474 occupied Section 8 units. A municipio sum would hold about a fifth of the vouchers and would rank municipios by how many tracts pass the threshold. The wanted-data row (`hud-vouchers`) is blocked with these numbers.

## Checks (`tests/test_credit.py`)

- The 2023 HMDA figures for Puerto Rico equal the Data Browser's own totals: 13,550 loans and $2.24 billion.
- In the published file, every municipio adds up to Puerto Rico's offices and deposits.
- Amounts and denial shares are null under the floor.
- Denial shares are between 0 and 100.
- With the cache, a rebuild gives the published file again (`python credit.py --check`).
