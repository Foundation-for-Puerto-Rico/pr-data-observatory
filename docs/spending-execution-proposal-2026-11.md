# Proposal: from where public money is assigned to how far it has gone (Public spending)

Date: 2026-11-10. Status: **approved by the project lead on 2026-11-12 (decision 96 in HANDOFF.md), choices (a) to (e) as proposed. Step 1 merged as #199 on 2026-11-11 and live; steps 2 to 4 next, each its own PR.**

**In one paragraph.** A CPA colleague of the project lead checked the Public spending page on 2026-11-10. They found that it brings together sources usually read apart and says what cannot be added. They also found that it shows where money is *assigned*, not how far it has gone: approved, obligated, contracted, disbursed, spent. They asked whether the tool is for distribution only or also for execution and results. This proposal keeps the page a **distribution tool that states the stage of every figure**. It adds execution only where a script can read the stage directly: federal **outlays** from USAspending, and **FEMA Public Assistance** by project from OpenFEMA, with each project's stage. Results (what the money achieved) are left out: they need program data no source here has. The first step is notes only and shows on the site.

## 1. What the colleague asked, against the page today

Measured on `main` (`bcaab7c`), page `site/public-spending.html`, generator `docs/analysis/public-spending-2026-11/make_page.py`.

| Point | Today | Proposed |
|---|---|---|
| Budget, federal obligations and recovery subawards are not added | **Done.** The page says so | Keep |
| Stage of each figure (approved, obligated, contracted, disbursed, spent) | **Partial.** The budget shows proposed, approved and spent; federal is obligated; recovery is subawarded. No common label, and no "reported or audited" | A stage and basis label on every figure (step 1) |
| FY2025: $29.23 B spent of $33.28 B approved | **No context.** The gap is shown bare | A note on what the gap can and cannot mean (step 1) |
| Spending comes from agency reports, not Hacienda's audited close | **Not said** | Said in the note; the latest audited statements found are for FY2023 (step 1) |
| Municipio figures read as benefit to residents | **Partial.** The budget places nothing in a municipio; the capital plan and recovery maps do | "Where the project is, who runs the money, who benefits" kept apart in words and on the maps (step 1, step 3) |
| Municipal budgets and public corporations are outside | **Half.** Public corporations are named as outside; municipal budgets are not | Both named (step 1) |
| Functions of mixed agencies | **Reviewed** on 2026-11-09 (decision 92, COFOG), row by row | Link the decisions from the page (step 1) |
| "By sector" compares Puerto Rico's fiscal year (July to June) with the federal one (October to September) | **No note** (checked in `site/js/public_spending_sectors.js`) | A short note (step 1) |
| FEMA Public Assistance, the largest recovery program, is missing | **Used only to avoid double counting** (dedup group `fema_pa`) | Its own section and map, by project stage (step 3) |
| CDBG-DR actual spending (DRGR quarterly reports) | **Missing** | Draws from USAspending outlays, checked against HUD's monthly report (step 4) |
| COR3 project data | **Dropped** (its API does not answer a plain script, and it is not worked around; its map layers have no licence and repeat OpenFEMA) | Stays out |
| Contralor contract register (who receives the money) | **Dropped** by the project lead on 2026-11-04 (lean open data: no letter, no scraping) | Stays out unless the project lead reopens it |

## 2. What the sources give, tested on 2026-11-10 with plain scripts

- **USAspending, award search** (`/api/v2/search/spending_by_award/`): every grant to Puerto Rico has `Award Amount` (obligated) and `Total Outlays` (paid out by the Treasury to the recipient). Outlays are cumulative over the award's life and reported from FY2020 (File C). Example: Medicaid award `2405RQTMAP`, $3.66 B obligated, $3.33 B outlaid. Some awards show outlays above the amount (`2205RQTMAP`: $2.41 B and $3.05 B), so the step checks and flags these.
- **CDBG-DR in USAspending**: the prime grants to the Department of Housing total about $20.7 B, with about $6.3 B outlaid (for example `B-18-DP-72-0001`: $8.22 B and $4.10 B; `B-18-DP-72-0002`: $8.29 B and $0.64 B). HUD's monthly *CDBG-DR Grants Financial Report* (PDF on hud.gov) gives the drawn share per grant and can check these figures. DRGR's quarterly reports per activity are long PDFs and are not read.
- **FEMA Public Assistance in USAspending is not usable**: the largest Puerto Rico award (`4339DRPRP00100001`) shows $0.44 B, against tens of billions in OpenFEMA. FEMA reports Public Assistance to USAspending in a way that does not follow the projects.
- **OpenFEMA, Public Assistance Funded Projects Details**: 23,056 Puerto Rico projects, $39.07 B federal share obligated. Each has its process step, which gives a stage:
  - obligated and open: 10,491 projects, $27.31 B;
  - closed out: 11,592 projects, $4.03 B;
  - pending a review or award: 973 projects, $7.74 B.
  - Disaster 4339 (María) is $35.57 B. **$30.42 B (78%) is "Statewide"**: no municipio. That is the colleague's point on location: most of the money is run centrally, so a municipio map would show only a fifth of it.
  - OpenFEMA gives obligations, not payments. What FEMA has paid out per project is not published in a form a script can read.
- **Hacienda's audited Basic Financial Statements**: the latest found is FY2023 (`hacienda.pr.gov/sites/default/files/cwpr_fs_2023.pdf`). They are audited on an accounting basis (GAAP) that differs from the budget's. They are named in the note as the audited reference, not read.

## 3. Steps

Each step is its own PR, merged only on the project lead's word. Every new technical word gets a sourced es/en definition with its tooltip.

1. **Notes and labels (first visible on the site).** No new data.
   - A stage and basis label on every figure: *proposed*, *approved*, *spent (reported by agencies)*, *obligated*, *subawarded*, and later *outlaid*. Each label says "reported" or "audited".
   - A note under the FY2025 gap. The difference can come from reserves, payment calendars, legal restrictions, accounting differences or later amendments. The two columns also come from two different OGP sheets. The gap alone does not show inefficiency.
   - A fiscal-year note in "By sector".
   - The scope: municipal budgets and public corporations are outside.
   - A link to the crosswalk decisions (decision 92).
   - New terms: obligation, outlay, subaward, reported, audited.
2. **Federal outlays next to obligations.** From USAspending award search: outlays by program and by function, next to obligations, for every year it has. A chart "obligated and paid out" by function. FEMA Public Assistance is left out of this chart (see section 2) and pointed to step 3. Awards with outlays above the amount are counted and flagged in the data notes.
3. **FEMA Public Assistance by stage.** A section and a map from OpenFEMA: federal share obligated by stage (open, closed out, pending), by damage category and by disaster. The map shows only the municipio-placed share and states the "Statewide" share in its title. The dedup with the federal totals stays as it is.
4. **CDBG-DR draws.** Outlays per grant from USAspending next to the obligations already on the page, checked against HUD's monthly financial report. Spanish that names CDBG or HUD stays held for Compliance (decision 21).

## 4. Left out

- **Results** (what the money achieved): needs program data, not spending data.
- **Contracted** as a stage: needs the Contralor register (dropped) or agency procurement systems.
- **COR3 project data** and **DRGR activity reports**: see sections 1 and 2.
- **A budget-to-actual from the audited statements**: PDF tables, on another accounting basis.

## 5. Choices for the project lead

- (a) **Scope**: distribution with stage labels, plus execution only where a script reads the stage (this proposal). The alternative is a full execution analysis, which needs the sources in section 4.
- (b) **Order**: 1 notes, 2 federal outlays, 3 FEMA Public Assistance, 4 CDBG-DR draws.
- (c) **HUD's monthly PDF** read only as a check on step 4, not as a published figure.
- (d) **Contralor and COR3** stay out.
- (e) **Steps 3 and 4** go through the Compliance review of federal grant content (decision 21) like the rest of the page.
