# How public money moves

The Knowledge Area page `site/money-cycle.html` ("How public money moves" / "Cómo se mueve el dinero público"), under the Public money domain. HANDOFF decision 112, step 1; the proposal is `docs/public-money-cycle-proposal-2026-11.md`.

**What it is for.** The three public money pages count money at different stages: approved, obligated, paid out, closed. A figure means little until the reader knows which stage it is. This page explains the stages once, so the other pages can point to it.

**Rules**
- **It explains; it does not count.** No figure of its own, no data file, no script of its own. A test checks there is no dollar figure on it.
- **Every statement has a public source.** The sources are a list in the generator (`SOURCES`): the name, what it supports and its address. A statement with no source there does not go on the page.
- **No opinion on how the process should work.** The page says what each body does by law, not whether it does it well.
- **No example from a private conversation.** An example of something paid for and not in service is used only with a public record (decision 112 (e)); the page has none yet.
- **In review.** It keeps the "In review" marker, the AI notice and `noindex` until Francis takes them off. Reviewer: leadership.

**What is on it**

| Section | Content |
|---|---|
| 1 The stages | Design, request, approval, assignment, obligation, execution, spending, in service. The last one is marked: no open source records it. |
| 2 Who does what | The Oversight Board, the Office of Management and Budget, the Legislature, the Treasury (Hacienda), the General Services Administration, the agency. |
| 3 The federal side | Appropriation, award, the recipient's own commitment, outlay, end of the period of performance, closeout. A federal grant is obligated twice, and the federal record shows only the first. |
| 4 Two calendars | July to June and October to September, as two bars over fifteen months. |
| 5 Services and works | Why the same share paid out means different things. |
| 6 Follow one grant | A made-up federal grant, step by step, with where each step can be seen. Half of the steps show nowhere. No amount, no real place. |
| 7 What open data do not show | Service, the second obligation, spending as it happens, the reasons. |
| 8 Often confused | Seven pairs: approved and spent, obligated and paid, paid and in service, a balance and money lost, a reduction and a payment sent back, a finding and a verdict, the two fiscal years. |
| 9 Five questions | What to ask of any figure about public money. |
| 10 See it in the data | Links to the exact section of the other pages where each stage shows, then the three pages and their stages. |
| 11 Check what you learned | Four cases with the answer folded (`<details>`, no script). |

**It teaches (2026-11-20).** Francis asked that the page be "bien educativa". The hero says what the reader can do after it (`LEARN`), and sections 6 and 8 to 11 are lists in the generator: `EXAMPLE`, `CONFUSED`, `QUESTIONS`, `SEE` and `CHECK`. Rules for them:
- The example is marked as made up and has no amount. A real case goes in only with a public record (decision 112 (e)).
- A link into another page names a section that exists; a test checks every one.
- The wording rule of the grants page (decision 111) holds: the page names a confusion only to deny it ("a balance is not money lost").
- No lesson was added to the Learn page: its lessons are about maps and each one drives a map tool, and its script budget has little room. The page is its own lesson.

**How to change it.** Everything is in `docs/analysis/money-cycle-2026-11/make_page.py`: `STAGES`, `FEDERAL`, `PAGES` and `SOURCES` are lists of (English, Spanish) pairs. Edit them, run the generator, then `python i18n.py`. Raise `I18N_V` when a string changes.

**Links.** The page is the first of the Public money areas in the Knowledge menu. It is in the "Related" list of the three pages, and Budget and public spending and Federal grants each carry a line to it near the top. The Disaster funding and need page links through "Related" only, because its generator is behind its page.

**Sources and a caution.** The library of laws of the Office of Management and Budget (`bvirtualogp.pr.gov`) did not answer from the build computer on 2026-11-19, so two laws link to copies on `hacienda.pr.gov` and `docs.pr.gov`; Act 147 of 1980 links to the library, which a web search confirmed holds it.

**Tests:** `tests/test_money_cycle.py`.

## OGP's Manual of the Budget Process (2026-11-23)

The stages "Request" and "Approval" follow the order of OGP's manual (https://gestion-presupuestaria.ogp.pr.gov/): the Board approves the Governor's proposal or sends it back before the Legislature sees it, and certifies the budget after the Governor signs. "Approved is not spent" gives the manual's rule on money of earlier fiscal years. The manual is in `SOURCES`. More in `docs/spending.md`.
