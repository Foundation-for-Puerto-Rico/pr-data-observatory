# Proposal: the public money cycle, and what the meeting of 2026-11-19 asked for (decision 112)

Date: 2026-11-19. Status: **approved by the project lead on 2026-11-19 (decision 112 in HANDOFF.md), choices (a) to (g) as proposed. Step 1, the cycle page, built on 2026-11-19 (`docs/money-cycle.md`); step 2, approved and reported spent by agency and fund, built on 2026-11-20 (`docs/spending.md`); step 3, the notes and corrections, merged on 2026-11-20; step 4, five grants rebuilt, built on 2026-11-20 (`docs/unused-funds.md`).**

**In one paragraph.** On 2026-11-19 the project lead and two colleagues who have worked inside the Commonwealth's budget process went through the Budget and public spending page for an hour and twenty minutes. Many ideas came out, and the project lead asked how to organize them, and whether an explanation of the budget cycle belongs in the page or apart. This document sorts the ideas into five groups, recommends the cycle as **a page of its own**, tests the one new analysis the data already allow (money approved and not spent, by agency), and proposes an order. It carries ideas only: no name and no quotation from the meeting.

## 1. The budget cycle: a page of its own

**Recommendation: a short page, "How public money moves" / "Cómo se mueve el dinero público", in the Public money domain.**

Why apart and not a section of Budget and public spending:
- **It serves three pages, not one.** The same stages explain the Commonwealth budget, the federal grants page (why obligated is not paid) and the disaster funding page (why paid is not in service).
- **Budget and public spending is full.** It has nine sections, and its load budgets were raised on 2026-11-19 to fit three cautions (decision 111).
- **It is the teaching piece the meeting asked for.** A short page can be shown by itself in a meeting or a class.

Each of the three pages then carries one line at the top that says which stage its figures are in, with a link to the cycle. Those lines already exist as "Stage and basis" notes (decision 96); they would gain the link.

**What the page says** (all of it came up in the meeting; each point needs a source before it is written, see section 6)

| Part | Content |
|---|---|
| The stages | Design, request, approval, assignment, obligation, execution, spending, and at the end: in service. One drawing, as a path. |
| Who does what | The Oversight Board opens and closes the process. The Office of Management and Budget designs, approves and assigns. The Treasury (Hacienda) pays. The General Services Administration buys. The agency carries out. |
| The federal side | Congress appropriates, the federal agency awards, the recipient in Puerto Rico commits the money by contract, the Treasury pays out, the grant closes. |
| Two calendars | The Commonwealth's fiscal year runs July to June, the federal one October to September. An agency plans with both at once. |
| Services and works | In a service grant, payment follows delivery month by month. A bridge or a dredging can take ten years between obligation and service. The same share paid out means different things. |
| What the data do not show | Whether what was built is in service. No open source records it. The page says so as a gap. |
| Where each page sits | A table: which page shows which stage, from which source. |

The page has no data of its own and one drawing, so it is small. It teaches the vocabulary; the glossary pop-ups (obligation, outlay, de-obligation, closeout) link to it.

## 2. Explain better what is already there

Notes where readers stumble, each one or two sentences, in the place where the figure is:
- **Debt service:** what it is, and that it is a fixed first claim on the budget.
- **Appropriations under the custody of Hacienda:** money the Treasury holds for others (pensions, transfers), not the Treasury's own spending.
- **Public Housing Administration and Department of Housing:** two bodies. The first runs the public housing projects; the second runs the disaster recovery grants.
- **Federal loans and federal grants:** a loan is repaid; the page says which is which.
- **The capital plan:** it mixes Commonwealth and federal money, and it is a plan, not a commitment.
- **Why one municipio shows far more recovery money than another:** a municipio must apply and justify, and part of the money is reported where the agency is, not where the work is.

## 3. Correct

- **The Oversight Board is missing** from the chart of proposed, approved and spent. The budget in force is the one the Board certifies; the page should say who proposes, who approves and who certifies.
- **A click on a function leaves the page filtered,** and the way back is not clear. The "back to all functions" control exists; it needs to be visible where the reader is.
- **Say where "spent" comes from.** It is the "Gastado" column of the Office of Management and Budget's data sheets: what agencies report. The page reads nothing from Hacienda, and the figure is not an audited one. The method says part of this; the chart should say it too.

## 4. A new analysis the data already allow: approved and not spent

The meeting's strongest idea: Commonwealth money that is approved for an agency and not spent by the end of the year (the "sobrantes"). Tested on `site/data/spending_state.json` (2026-11-19), where both stages exist for fiscal years 2024 and 2025:

| | FY2024 | FY2025 |
|---|---|---|
| Approved | $31.34 B | $33.28 B |
| Spent | $30.78 B | $29.23 B |
| Agencies that spent less than approved | 73, by $2.51 B | 69, by $5.46 B |
| Agencies that spent more than approved | 30, by $1.95 B | 30, by $1.41 B |
| General Fund: approved, spent | $12.74 B, $13.73 B | $13.06 B, $11.58 B |
| Federal funds: approved, spent | $13.59 B, $12.38 B | $15.35 B, $13.16 B |

Largest gaps in FY2025: the Department of Education ($1.43 B), the Department of Housing ($1.39 B) and the Emergency Management bureau ($0.90 B).

**What the test shows**
- **It can be built now,** by agency, by fund and by concept of expense, with no new source.
- **It must not be read as money left over.** Most of the FY2025 gap is federal money (disaster recovery in Housing and Emergency Management), which is spent over several years. The useful view separates the General Fund from federal and special funds.
- **Agency codes move.** In FY2025 the Police show $0 approved and $867 M spent, because the budget was approved under another body. The view needs the agencies joined before any ranking.
- **"Spent" is what agencies report,** not what Hacienda certifies (section 3). The view says so beside the figure.
- **What happens to the money afterward is not in the data:** whether it is carried forward, returned to the Treasury or released by the Board. The page can explain the rule in words, with a source, and say that no figure follows it.

## 5. What needs data the observatory does not have

- **Execution and service.** Whether a hospital, a school or an office paid for is open. The reviewer of decision 111 asked for the same thing from the federal side: rebuild a few awards by hand, from obligation to closing, before any indicator. One piece of work serves both.
- **Spending as it happens.** The Commonwealth's accounting is not public in real time.
- **How late the audited statements are.** The audited statements of fiscal year 2023 came out on 2026-07-03, about 26 months after the year ended. A one-line fact with its source, updated when the next one is published. Not an indicator.
- **Contracts.** The registry of contracts now asks for registration; it stays out (lean open data rule).
- **Comparison with the states.** Federal money per resident by state is in USAspending and can be built; it is here because it is a new series, not a fix.

## 6. Sources to check before anything is written

Said from memory in the meeting, each needs a public source:
- The fiscal years: 46 states begin on July 1; New York (April 1), Texas (September 1), Alabama and Michigan (October 1) do not (NCSL and NASBO, checked 2026-11-19). The federal year has begun on October 1 since fiscal year 1977.
- The roles of the Oversight Board, the Office of Management and Budget, Hacienda and the General Services Administration: from PROMESA and each body's organic law.
- The rule on unspent Commonwealth money at year end: from the budget resolution and the certified fiscal plan.
- Examples of things paid for and not in service: only with a public record (an audit, a hearing, a press report), and only if the page needs an example at all.
- A federal portal named in the meeting could not be identified; it is left out until it is.

## 7. A separate track: municipal work

The colleagues' project for municipios, and whether one municipio's financial tool can be replicated for others, came up several times. What the observatory could give it (the My municipio section, the recovery money a municipio could apply for) deserves its own conversation with them, and is not in this plan.

## 8. Order proposed

Each step is its own pull request, merged only on the project lead's word.

1. **The cycle page** (first visible), with the stage line and link on the three pages.
2. **Approved and not spent, by agency and fund,** with the cautions of section 4.
3. **The notes and corrections** of sections 2 and 3.
4. **A few awards rebuilt from obligation to closing** (also decision 111 (d)).
5. Later, on his word: the comparison with the states; findings by compliance requirement; audit lateness by submission date; FEMA Section 428 apart.

## 9. Choices for the project lead

- **(a)** The cycle is a page of its own, "How public money moves" / "Cómo se mueve el dinero público", under Public money, and the three pages link to it from their stage line.
- **(b)** The page teaches and has no data of its own; every statement has a public source; it gives no opinion on how the process should work.
- **(c)** "Approved and not spent" is built from the data the observatory has, General Fund apart from federal and special funds, never called a surplus or a loss, with the note that "spent" is what agencies report.
- **(d)** Where step 2 goes: a new section of Budget and public spending (its budgets are tight) or a page of its own. Recommended: its own section loaded on first use, like My municipio.
- **(e)** Examples of things paid for and not in service are used only with a public record.
- **(f)** The municipal work is a separate conversation.
- **(g)** The order of section 8.
