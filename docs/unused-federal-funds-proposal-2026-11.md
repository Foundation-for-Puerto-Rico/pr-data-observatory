# Proposal: federal funds returned and unused (decision 110)

Date: 2026-11-17. Status: **approved by Francis on 2026-11-18 (decision 110 in HANDOFF.md), choices (a) to (h) as proposed. All four steps were built, merged and live on 2026-11-18 (#292, #294, #297, #299; `docs/unused-funds.md`). Francis approved the eighteen choices made in the work on 2026-11-19.**

**In one paragraph.** Francis shared an opinion column on 2026-11-17 about federal money Puerto Rico loses: funds the federal government takes back, funds that expire, and funds still waiting to be paid. The column says no public inventory brings these together by program. Francis asked whether the observatory can measure or monitor it, and said "Sí, prepárala" to a proposal. He also asked that it be clear that **WIOA is only an example**: the column uses the workforce program to make its point, and the page must cover every federal program. This document tests three measures on every grant program with data a script can read today. All three work. None of them is "money lost" by itself, and the raw totals are dominated by routine accounting in a few very large programs, so each measure needs a stated rule before it is published. The proposal is a new Knowledge Area page under Public money, built in four steps, the first of which shows on the site.

## 1. What the observatory already answers

The Public spending page answers one of the column's three categories, **money still pending** (decisions 96 and 109):
- federal grants and contracts signed since fiscal year 2020, obligated and paid out;
- FEMA Public Assistance projects by stage and by age;
- CDBG-DR draws.

It does not show money **taken back** or money in grants that have **ended**. The column itself separates the three: not every unused balance is a loss.

## 2. The test (run on 2026-11-17)

Scripts and their outputs are in `docs/analysis/unused-funds-2026-11/`. Every figure below comes from them. The caches are outside the repository.

### 2.1 Money taken back: negative transactions in USAspending

`measure.py` reads every negative transaction (a reduction of the amount obligated to an award) on grants whose recipient is in Puerto Rico, federal fiscal years 2019 to 2026.

| | Transactions | Awards | Amount |
|---|---|---|---|
| All grant programs | 9,851 | 5,626 | $23.33 B |
| Disaster programs (FEMA Public Assistance, CDBG State program, Hazard Mitigation, Individuals and Households) | 3,120 | | $16.17 B |
| **All other programs** | 6,731 | 5,607 | **$7.15 B** |

The other programs are 477 assistance listings and 408 recipients. The largest:

| Program (assistance listing) | Reductions | Transactions |
|---|---|---|
| Medicaid (93.778) | $2,426.0 M | 54 |
| Highway Planning and Construction (20.205) | $1,338.9 M | 955 |
| WIC (10.557) | $407.9 M | 61 |
| Grid Infrastructure Deployment and Resilience (81.254) | $306.7 M | 3 |
| Child Care mandatory and matching funds (93.596) | $248.1 M | 9 |
| National School Lunch Program (10.555) | $224.6 M | 27 |
| Children's Health Insurance Program (93.767) | $202.6 M | 5 |
| Education Stabilization Fund (84.425) | $166.3 M | 88 |
| Vocational Rehabilitation (84.126) | $146.3 M | 12 |
| Head Start (93.600) | $127.2 M | 280 |

**WIOA is one example among hundreds.** The two WIOA programs in the first 25 (Youth 17.259, $85.1 M; Dislocated Worker 17.278, $34.8 M) are 1.7% of the $7.15 B. The test still reproduces the column to the dollar: -$2,677,483 on 2020-05-07 and -$449,019 on 2021-05-06, both on Dislocated Worker grants to the Departamento de Desarrollo Económico y Comercio. The 2023 recapture the column names ($4.7 M) is not under that listing; step 2 looks for it in the other WIOA listings.

**What the test shows**
- **A script can read it**, for every program, with the award, the recipient, the date and the federal agency.
- **A negative transaction is not a loss.** It can be a recapture, a balance left when a grant closed, or a correction of an estimate. Medicaid, highways and WIC are 58% of the $7.15 B, and in those programs awards are estimates or project agreements that are adjusted as a routine. The Dislocated Worker listing shows $34.8 M in reductions where the column counts $7.8 M of recaptures.
- **Disaster programs behave differently.** FEMA Public Assistance alone has $16.14 B in reductions, because projects are re-versioned. The Public spending page already reads those projects from OpenFEMA, so they stay apart.
- **So the published measure needs a rule.** Proposed: the net reduction of each award over its life (its highest cumulative obligation minus its final one), only for awards that have ended, shown by program, with the estimate-based programs marked. The gross figure above is never published as a total.

### 2.2 Money at risk: grants that have ended with an unpaid balance

`expired.py` reads the same grants as the page's paid-out card (place of performance Puerto Rico, signed in fiscal years 2020 to 2025, FEMA Public Assistance left out), with each award's end date.

| | Awards | Obligated | Unpaid |
|---|---|---|---|
| Grants signed FY2020 to FY2025 | 8,052 | $67.93 B | |
| Ended more than a year ago | 3,331 | $38.14 B | $7.13 B |
| ... with a balance of at least 5% and $1,000 | 601 | | $6.87 B |
| ... of which Medicaid (93.778) | 18 | | $5.13 B |
| ... all other programs | 583 | | $1.74 B |

The 601 awards are in 224 assistance listings and 16 federal agencies. After Medicaid, the largest are TANF (93.558, $320.9 M), the Children's Health Insurance Program ($162.5 M), an Environmental Protection Agency listing (66.959, $156.0 M, one award), WIOA Youth ($126.0 M), and Title I grants to schools (84.010, $100.7 M). 81 ended awards ($71.7 M) report no outlay at all.

**What the test shows**
- **A script can read it**: `federal_outlays.py` already downloads these awards and only needs to keep the end date.
- **Medicaid needs its own line.** $5.13 B of the balance is in 18 Medicaid awards that ended in 2020 and 2021. That is more likely a gap in what USAspending reports as paid for that program than unpaid money. It is shown apart with that note, not added to the rest.
- **It is risk, not loss.** A grant can be extended, and an agency can pay a late claim. The page says "ended with an unpaid balance", never "lost".

### 2.3 What was corrected: audit findings that repeat

`fac_findings.py` reads the Federal Audit Clearinghouse, the source the observatory already uses for municipio audits (decision 70), for the findings of every single audit filed by a body in Puerto Rico for audit year 2023.

| Audit year 2023 | |
|---|---|
| Audits filed | 350 ($23.07 B in federal money spent) |
| Audits with at least one finding on a federal program | 141 |
| Findings | 306 |
| ... marked as repeated from an earlier audit | 140 (46%) |
| ... that are a material weakness | 120 (39%) |
| ... with questioned costs | 15 (5%) |
| Federal programs with at least one finding | 145 |
| Audits accepted more than 9 months after the fiscal year ended (the deadline) | 159 of 350 |
| ... more than 18 months after | 51 |

By a rough match on the name of the body: Commonwealth agencies and public corporations 114 findings (58 repeated), municipio bodies 83 (38), nonprofits and others 109 (44). The programs with most findings are the Coronavirus State and Local Fiscal Recovery Funds (59, of which 29 repeated), FEMA Public Assistance (44, 28), the CDBG State program (32, 15) and Section 8 vouchers (24, 16).

**What the test shows**
- **This is the closest open answer to the column's main question**: after a finding, was it corrected? A repeated finding says it was not, by program and by body, every year.
- **The dollar amount of questioned costs is not in the data**, only a yes or no. The page reports counts.
- **Lateness can be measured** and is itself a sign: almost half of the audits arrive after the deadline.
- **A full run needs the key** of decision 70 (`FAC_API_KEY`); the public demonstration key was enough for one year.

## 3. What open data cannot answer

- **Commonwealth money that replaces a denied federal payment** (the column's first case, $14.8 M for an education project). It appears in letters of the Oversight Board, case by case, not in a data source.
- **Services not delivered** because the money was not used. No source has it.
- **Why** a balance was returned, and what the agency did afterwards. Audit texts and corrective action plans say some of it, in prose.
- **Lists held by agencies**, such as the one the Departamento de la Familia offered the Senate. The observatory makes no data requests (lean open data rule).
- **Audits of the Oficina del Contralor**: left out on 2026-11-04 (no licence stated).

The page says this in its scope note instead of leaving a silence.

## 4. The page

- **Where:** a new Knowledge Area page in the Public money domain, next to Public spending and FEMA disaster funding. Money that was not used is the opposite of spending, so it does not belong inside the Public spending page.
- **Name:** "Federal funds returned and unused" / "Fondos federales devueltos y sin usar". Not "lost": the test shows that most reductions and balances are not losses, and the page must not say more than the data.
- **Shape:** three sections, one per measure, each with its rule, its basis line and its "what this is not". A filter by federal agency, by program and by kind of recipient. No single total across the three.
- **Scope:** every federal grant program. WIOA appears only as a worked example that checks the method against published figures.

## 5. Steps

Each step is its own pull request, merged only on Francis's word.

1. **Ended grants with an unpaid balance, and the page** (first visible). `federal_outlays.py` keeps each award's end date; a new file by program and federal agency; the page with its scope note, section 2.2 and Medicaid apart.
2. **Money taken back.** A new script for the net reduction per ended award; by program, agency and year; disaster programs apart; the two WIOA figures as a test of the method.
3. **Findings that repeat, and audit timing.** The findings of every audit year from 2019, by program and by kind of body, with the share repeated and the months to acceptance.
4. **Connections.** A "returned" line in the Public spending page's stage notes; a row in My municipio for the municipio government's own audit findings; the Public spending title change of choice (f).

Glossary terms come with each step (deobligation, recapture, period of performance, closeout, single audit, finding, repeated finding, questioned costs, material weakness).

## 6. Left out

- A total of "money lost". No source supports one.
- A register of cases compiled by hand from inspector general reports or Oversight Board letters.
- The Contralor, COR3, DRGR and any source that needs a request or a login.
- Contracts: a reduced contract is a purchasing matter, not a lost grant. Loans and direct payments to people are out for the same reason.
- Any judgement on an agency. The page states amounts, dates and rules, and recommends no policy.

## 7. Choices for Francis

- **(a) A page of its own** under Public money, named "Federal funds returned and unused" / "Fondos federales devueltos y sin usar".
- **(b) Three measures, never added up:** taken back (net reduction per ended award), at risk (ended with an unpaid balance), and findings that repeat. Each figure says which it is.
- **(c) Every program.** WIOA only as the worked check. Disaster programs and Medicaid shown apart, with the reason.
- **(d) Who is named.** Commonwealth agencies, public corporations and municipio governments are named as the federal source names them. Nonprofits, firms and other private bodies are grouped by kind and not named.
- **(e) The Clearinghouse key** of decision 70 is reused for step 3; no new key.
- **(f) The Public spending page's title** becomes "Budget and public spending" / "Presupuesto y gasto público": the page covers approved, obligated and paid money, and "spending" alone is only the last. The address does not change.
- **(g) Review before it is public.** The page opens with the "In review" marker, the AI notice and `noindex`, and goes through the Compliance review (decision 21), because it names public bodies next to unused money.
- **(h) The order of the steps** in section 5.
