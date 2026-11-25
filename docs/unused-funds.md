# Federal grants: balances, reductions and audit findings

(Until 2026-11-19 the page was called "Federal funds returned and unused".)

The Knowledge Area page `site/unused-funds.html` ("Federal funds returned and unused" / "Fondos federales devueltos y sin usar"), under the Public money domain. HANDOFF decision 110; the proposal and its tests are in `docs/unused-federal-funds-proposal-2026-11.md` and `docs/analysis/unused-funds-2026-11/`.

**Rules that hold for every step**
- **Every federal grant program is read.** No program is singled out. The workforce grants (WIOA) that prompted the page are lines like any other.
- **Three measures, never added up:** money at risk (step 1, built), money taken back (step 2, built) and audit findings that repeat (step 3, built). Step 4 connected the page to Budget and public spending.
- **Nothing is called "lost".** The data do not support it. A test checks the page's words.
- **No private recipient is named.** Step 1 names no recipient at all: it counts by federal agency and by program.
- **The page states amounts, dates and rules.** It draws no conclusion about an agency and recommends no policy.
- **In review.** The page keeps the "In review" marker, the AI notice and `noindex` until the Compliance review of federal grant content (decision 21) is done and the project lead takes them off.

**Status (2026-11-19):** the four steps are merged and live (#292, #294, #297, #299), and the project lead approved the eighteen choices made in the work (HANDOFF decision 110, (1) to (18)). Open: the Compliance review, a "returned" line in the Budget and public spending page's stage notes, and the other pages that still call that page "Public spending".

## The review of 2026-11-19 and what it changed (decision 111)

A reviewer with long experience in federal funds read both pages. Their main point: the title and the first screen said more than the data support. "Returned" was not shown, a balance not yet paid out is not money at risk, and a net reduction cannot be called the clearest sign of money withdrawn when the page itself says it cannot tell the causes apart. This section records what was corrected. The step sections below keep the figures of the day each step was built.

**The name.** The page is now "Federal grants: balances, reductions and audit findings" / "Subvenciones federales: saldos, reducciones y hallazgos de auditoría". Its tab in the Knowledge menu is "Balances, reductions and findings" / "Saldos, reducciones y hallazgos". The address `unused-funds.html` and the file names do not change.

**Four different things, kept apart:** balances not yet paid out; reductions of the amount committed (de-obligations); programs the federal government canceled; and documented losses, for which the page has no figure because no open source records a loss as such.

**Corrections to the data**
- **Only grants that began in the years read.** USAspending's search returns every award with an action signed in a year, so it also returned older awards that were only amended then (the reviewer found one that ended in 2018). `unused_funds.in_universe` keeps an award when its start date is on or after October 1, 2019. 1,250 older awards are left out.
- **TANF (93.558) is apart:** a State or territory may carry unspent TANF money forward without a deadline (42 U.S.C. 604(e)).
- **Programs the federal government ended are apart:** Solar for All (66.959), terminated by the Environmental Protection Agency on 2025-08-07, and the Community Change Grants (66.616), canceled in 2025. In the reductions, the same two plus Grid Infrastructure Deployment and Resilience (81.254): its $365.0 M reduction is three transactions of 2025-05-21, when the Department of Energy redirected the solar funds of the Puerto Rico Energy Resilience Fund.
- **Title I (84.010) stays, with a note:** the Tydings Amendment gives 27 months, and the Department of Education can extend the time to pay out.
- **Ended grants with no payment on record** are listed by federal agency in section 4, and are still in no total.
- **Audit findings by kind of body** count only the audit years that have mostly arrived.

**Corrections to the words**
- The read date and the cutoff are each named: the page used to put the cutoff (one year before the read) where a reader took it for the read date.
- The one-year line cites 2 CFR 200.344 in full: 120 days to pay bills and report (90 days for grants made before 2020-11-12), and the agency's effort to close within a year. Passing it does not show a loss.
- In section 5 the limit (the data do not say why an amount was lowered) comes before the figure.

**Figures after the corrections (read 2026-11-19)**

| | Grants | Dollars |
|---|---|---|
| Began FY2020 to FY2026 | 7,197 | $38.47 B obligated |
| Ended more than a year before | 3,257 | $17.32 B obligated |
| ... with a balance not yet paid out | 564 | $1.21 B of $3.77 B |
| ... with no payment on record (apart) | 79 | $71.2 M obligated |
| Apart: Medicaid / TANF / ended by the federal government | 18 / 6 / 4 | $5.13 B / $0.32 B / $0.21 B |
| Net reductions, main figures | 2,533 | $2.03 B in 422 programs |
| Net reductions apart: federal decisions of 2025 | 4 | $0.37 B |

**On the Budget and public spending page**
- FEMA Public Assistance: closed out is given in dollars and in projects (the two differ: about a tenth of the dollars, half of the projects).
- Recovery grants: the grants made before fiscal year 2020 (B-08-DI-72-0001 and B-17-DM-72-0001) carry a mark and a note, because USAspending has payments only from 2020.
- A caution beside the treemap says how much of the budget takes its agency's general function.
- These three texts did not fit: the page's budgets went from 42 to 43 KB (first load) and from 24 to 25 KB (after ready).

**Not done yet, in the order the reviewer suggests**
1. **Rebuild a few large awards from obligation to closing** (extensions, payments, the agency's determinations) before adding any indicator. This says how much the data can support. **Done on 2026-11-20: see "Five grants rebuilt" below.**
2. Findings by compliance requirement (the field is already read), lateness by submission date against the due date with the COVID extensions, and FEMA's Section 428 projects apart.
3. COR3 stays out (decision 96 (d)): its system does not answer scripts and its data carry no license.

## Step 1: grants that ended with an unpaid balance (built 2026-11-18)

**Data:** `site/data/unused_funds.json`, built by `unused_funds.py`.

| Command | What it does |
|---|---|
| `python unused_funds.py` | Builds the file; downloads only the signing years missing from `cache/spending/ended/`. |
| `python unused_funds.py --refresh` | Reads every signing year again from USAspending and sets a new read date. |
| `python unused_funds.py --check` | Rebuilds from the cache and fails when the published file differs. No network. |

**Source:** USAspending.gov's award search, no key. Grants (award types 02 to 05) with place of performance Puerto Rico, by the federal fiscal year they were signed, from 2020, because USAspending has outlays from then. The fields read are the award's amount, total outlays, assistance listing, end date and awarding agency. The recipient is not read.

**The rule**
- **Ended:** the end date is more than one year before the day the data were read. By then the 120 days a recipient has to draw down (2 CFR 200.344) and the agency's year to close the award have passed.
- **Unpaid balance:** the amount obligated minus the outlays, never below zero.
- **Counted:** an ended grant whose balance is at least 5% of the award and at least $1,000.
- **Not counted as unpaid:** an ended grant that reports no outlay at all. A blank is not a zero. They are counted apart (`no_outlay`).

**Kept apart**
- **Medicaid (93.778)** is in `apart`, never in the totals. Its ended grants show $5.13 B unpaid, mostly in grants that ended in 2020 and 2021. That is more likely a gap in what USAspending reports as paid than money not paid.
- **FEMA Public Assistance (97.036)** is left out (`excluded`). Its grants do not follow the projects; the Public spending page counts the projects from OpenFEMA.

**Figures on 2026-11-17**

| | Grants | Dollars |
|---|---|---|
| Signed FY2020 to FY2025 (without Medicaid and FEMA Public Assistance) | 8,010 | $47.90 B obligated |
| Ended more than a year before | 3,294 | $18.10 B obligated, $1.85 B unpaid |
| ... that report no outlay | 81 | $71.7 M obligated |
| ... that keep a balance | 583 | $4.46 B obligated, $1.74 B unpaid |

The 583 grants are in 223 programs of 16 federal agencies.

**Program names** come from the published federal files (`spending_federal.json`, `spending_outlays.json`). For a program those files do not name, `unused_funds.py` asks USAspending's listing search once and keeps the answer in the cache (`names.json`).

**The page** is written whole by `docs/analysis/unused-funds-2026-11/make_page.py`. It has no script of its own: the tables are in the page. Program names stay in English, as the federal government writes them; agency names have Spanish (`AGENCY_ES`; a new agency stops the build until it has one).

**Tests:** `tests/test_unused_funds.py`: the rule, the sums, no recipient in the file, the page's figures, its words and its review marker.

**What a refresh changes.** Balances fall as payments are reported and as end dates are extended, and new grants pass the one-year line. Run `--refresh`, then `make_page.py`, `i18n.py`, `dictionary.py`, `catalog.py` and `registry.py`.

## Step 2: money taken back (built 2026-11-18)

**Data:** `site/data/taken_back.json`, built by `taken_back.py` (`--refresh`, `--check` as in step 1; cache `cache/spending/taken_back/`, one file per quarter).

**Source:** USAspending.gov's transaction search, no key. Every transaction on grants (award types 02 to 05) with place of performance Puerto Rico, by action date, from federal fiscal year 2019. The fields read are the award's key, the action date, the amount, the assistance listing and the awarding agency. The recipient is not read, and no award key is published.

**The rule: net reduction, not negative transactions**
- A negative transaction (a de-obligation) lowers the amount obligated to a grant. Most are raised again later, so they are not counted one by one.
- **Net reduction of a grant** = the highest level its obligation reached in the period, counted from where it stood when the period began, minus the level where it ended. A grant lowered and raised back counts nothing.
- **One day, one change.** The transactions of a grant on the same day are added first. A swap between two lines of a grant is not a reduction, whatever order the source lists them in.
- **Moves are left out.** A reduction matched by an equal increase on another grant of the same listing and agency within 31 days is money moved. The reduction is dropped; the increase stays with the grant that received it.
- Grants with a net reduction under $1,000 are left out.
- **Year:** the federal fiscal year of the grant's last negative transaction.
- **Program of a grant that carries several listings:** the listing with most money obligated to it. The file counts these grants (`combined_awards`).

**Kept apart** (`APART`, each with its reason, never added to the totals)
- **Programs paid by actual cost** (Medicaid, the Children's Health Insurance Program, foster care, adoption assistance, child support enforcement, school meals, Pandemic EBT): each grant is an estimate adjusted to the actual costs.
- **Highway projects** (20.205): money released when a project closes goes back to the highway balance of Puerto Rico.
- **Disaster programs** (FEMA Public Assistance, Hazard Mitigation, Individuals and Households, the CDBG State program): their projects are re-versioned many times.

A program is apart only for a reason that holds for the whole program. The workforce programs are in the main figures.

**Figures read on 2026-11-18**

| | Grants | Dollars |
|---|---|---|
| Transactions read, FY2019 to FY2026 | 13,838 grants | 74,665 transactions |
| Negative transactions (gross, never published as a total) | | $23.39 B in 9,858 transactions |
| Moves left out | | $337.5 M in 184 reductions |
| **Net reduction, main figures** | 2,537 | **$2.39 B** in 423 programs of 27 federal agencies |
| Apart: programs paid by actual cost | 90 | $2.93 B |
| Apart: highway projects | 447 | $0.28 B |
| Apart: disaster programs | 12 | $0.12 B |

**The check against published figures.** The three recaptures of workforce money that the opinion column of 2026-11-17 names are in the source to the dollar: -$2,677,483 (2020-05-07), -$449,019 (2021-05-06) and -$4,694,538 (2023-03-29). They are an example of the method working, not the subject of the page. The same grants show larger reductions when they closed, which the column did not count; the data do not say why.

**What the measure cannot say:** why a grant was reduced. Money left unused at closing, a recapture, a program ended early by the federal government and a correction all look the same.

**Never add step 1 and step 2.** The grants overlap and the years differ (step 1: grants signed from FY2020; step 2: transactions from FY2019).

**Tests:** `tests/test_taken_back.py`.

## Step 3: audit findings that repeat (built 2026-11-18)

**Data:** `site/data/audit_findings.json`, built by `audit_findings.py` (`--refresh`, `--check`; cache `cache/spending/fac/`).

**Source:** the Federal Audit Clearinghouse API, the source of the municipio audit series (decision 70). It reads three tables: the single audits filed by bodies in Puerto Rico from audit year 2019 (`general`), their findings (`findings`) and their award lines with a finding (`federal_awards`).

**The key.** The API needs a free api.data.gov key in `FAC_API_KEY`. Without it the script uses the public `DEMO_KEY`, which allows ten calls an hour. A full read is seventeen calls, because the service refuses long addresses and the audits are asked for in eight chunks. With the public key the script stops at the limit, keeps the published file, and a rerun an hour later resumes from the cache. `build.py` never refreshes this file: refresh it by hand. The key was set on the project lead's computer on 2026-11-18 (user level); it is never written to the repository, the cache or the site.

**How a finding is counted**
- The API lists a finding once for each award line it touches. Here a finding is one (audit, reference number).
- It is **repeated**, a **material weakness** or has **questioned costs** when any of its lines says so.
- **By agency and by program** a finding counts once in each it touches, so those rows add up to more than the findings.
- **Late:** the audit was accepted more than nine months after the fiscal year ended (2 CFR 200.512).
- **Kind of body:** the Clearinghouse's own `entity_type` (state, local, non-profit, higher education). No body is named, and no name or contact field is published.

**Figures read on 2026-11-18, audit years 2019 to 2024** (later years are still arriving and are marked on the page)

| | |
|---|---|
| Single audits filed | 1,908 |
| ... with at least one finding | 720 |
| Findings | 1,659 |
| ... repeated from the audit before | 843 (51%) |
| ... material weakness | 654 |
| ... with questioned costs (a yes or no; no amount is published) | 112 |
| Audits accepted after the nine-month deadline | 1,044 |
| Programs with at least one finding, all years | 278 |

**What the measure cannot say:** how serious a finding is, how much money it involves, or why it was not corrected. A finding is not a loss.

**Tests:** `tests/test_audit_findings.py`.

## Step 4: connections (built 2026-11-18)

- **The Public spending page is now "Budget and public spending" / "Presupuesto y gasto público"** (choice (f)): its title, its heading, its tab in the Knowledge menu and its cite line. The address `public-spending.html` does not change. The page covers approved, obligated and paid money, and "spending" alone is only the last.
- **The two pages link to each other** through the "Related" list of the Knowledge registry (`related` in `knowledge_src/items.json`), which costs the page no first-load text.
- **My municipio shows the municipal government's own audits**: single audits filed in the three latest audit years that have mostly arrived, findings on federal programs, and findings repeated, with a link to section 6 of this page.
  - `audit_findings.py` writes `municipio_governments` in `audit_findings.json`: `{years, by_code: {municipio code: [audits filed, findings, repeated, latest audit year filed]}}`. The audits are matched by the name of the municipio's own government (`economy_series.fac_municipio`, as in decision 70 (b)): not its housing projects, consortia or other bodies. No name is in the file, only the Census code.
  - `municipio_view.py` copies the row into `spending_municipio.json` (`audit`), so the page fetches nothing more.
  - 2022 to 2024: all 78 municipio governments filed at least one audit and 73 filed all three; 246 findings, 116 repeated.
  - This is the first use of choice (d): municipio governments are public bodies and are named. No other body is.
- **Not built: a "returned" line among the Public spending page's stage notes.** That page's first-load scripts are at 41.9 of 42 KB and its after-ready scripts at 23.9 of 24 KB, so a new line there needs room first. The link in "Related" and the block in My municipio carry the connection meanwhile.
- **Other pages still say "Public spending"** where they mention the page in a sentence (the FEMA disaster funding page and others). Their generators are behind their pages on script versions, so they are left for a pass of their own.

**Tests:** `tests/test_audit_findings.py` (the match and the three-year count; the My municipio file carries the same figures).

## Five grants rebuilt (decision 112, step 4; decision 111 (d); built 2026-11-20)

**Why.** The reviewer asked for this before any new indicator: follow a few large grants through everything the open record gives, to see how far a balance on record can be trusted. It is a study of the source, done once.

**Files.** `docs/analysis/unused-funds-2026-11/rebuild_awards.py` writes `awards_rebuilt.json` beside it, and `make_page.py` reads that file for the section "Five grants rebuilt, one by one". The file is an input of the page, not a data file of the site, so it is not in the catalog and `build.py` does not refresh it.

| Command | What it does |
|---|---|
| `python docs/analysis/unused-funds-2026-11/rebuild_awards.py` | Reads USAspending (cached in `cache/spending/awards`, or `AWARDS_CACHE`) and writes the file. |
| `python docs/analysis/unused-funds-2026-11/rebuild_awards.py --check` | Rebuilds from the cache and fails when the file differs. No network. |

**The rule that picks the grants.** Grants with place of performance Puerto Rico signed in federal fiscal years 2020 to 2024 (the 300 largest of each year), ended more than one year before the read, outside the programs the page keeps apart or leaves out; ordered by the balance on record; the first grant of each of the first five programs. No grant is chosen by hand.

**What is read for each grant** (USAspending.gov, no key)
- The award: the dates, the amount, the total paid out (`/api/v2/awards/<key>/`).
- Its transactions: each change of the amount committed (`/api/v2/transactions/`). The changes of one day are added, as in the reductions.
- Its funding by reporting period: the payments the federal agency reported (`/api/v2/awards/funding/`). **They are year to date for each account line**, so a fiscal year's payments are the sum over lines at the last month reported that year. The script stops when those years do not add up to the award's own total paid out; for the five they agree to the dollar.
- The recipient is not written to the file, and no grant number is published. The cache holds the source's answers as they came and is not in the repository.

**What the five show** (read 2026-11-20)

| Program | Committed | Paid on record | What the record shows |
|---|---|---|---|
| WIOA, combined grant (17.258, 17.259, 17.278) | $121.9 M | $15.6 M | Payments in fiscal years 2021 and 2022 and none after; the grant ran to June 2024 and leaves the agency's account reports after 2022. |
| Children's Health Insurance Program (93.767) | $109.3 M | $9.3 M | Committed $192.8 M, lowered by $83.6 M in May 2022. Payments on record only from fiscal year 2022, for a grant of 2020 and 2021. |
| Education Stabilization Fund (84.425) | $2,968.1 M | $2,883.4 M | $2,081.8 M (72% of the paid) paid after the fiscal year of the end date; the end date was never changed. |
| Title I (84.010) | $447.7 M | $392.7 M | 92% of the paid came after the fiscal year of the end date; $109.6 M in fiscal year 2026, after the 27 months of the Tydings Amendment. |
| 21st Century Community Learning Centers (84.287) | $35.3 M | $0.6 M | $4.1 M paid through fiscal year 2025, then the total lowered by $3.4 M in 2026. |

**What follows**
- The end date on record is often not the last day to pay, and it is not updated.
- The record of payments can begin late, stop early or be corrected.
- USAspending publishes no closing date, no approved extension and no decision of the federal agency.
- So a balance after the end date tells where to ask. The page builds no indicator from these balances and says so beside the five.

**Open question, not on the page.** $665 M of the $1.21 B of balances of step 1 (55%) is in grants that began in fiscal years 2020 and 2021: 332 of the 564 grants. The one grant rebuilt from fiscal year 2020 has no payment on record before fiscal year 2022. One grant is not enough to say the same of the other 331; counting the first year with a payment for every grant of those two years would settle it (one call per grant).

Tests: class `Rebuilt` in `tests/test_unused_funds.py`.
