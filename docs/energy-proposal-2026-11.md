# Proposal: energy in Puerto Rico (plants, grid, rooftop solar, reliability and cost)

Date: 2026-11-13. Status: **approved by the project lead on 2026-11-13 ("Approve, start step 1"): decision 104 (a) to (g) as proposed. Step 1 is being built on branch `data/power-plants`.** This pull request changes no page and publishes no data. It adds this document and a preview map made from the real data (`docs/analysis/energy-2026-11/preview.svg`, built by `make_preview.py` in the same folder).

**In one paragraph.** On 2026-11-13 the project lead shared a #30DayMapChallenge map of Romania's power grid: OpenStreetMap plants as glowing dots sized by MW and coloured by fuel, over the 400 kV and 220 kV lines. Drawn the same way, Puerto Rico's map would miss most of its solar power. Utility plants hold 398 MW of renewable capacity (EIA-860M, September 2026). Rooftop systems already hold **1,666 MW at 209,404 installations, with 189,459 batteries** (LUMA, September 2026). The rooftop figure is 4.2 times the utility-scale renewable capacity and 26% of the capacity of every utility plant together (6,436 MW). This proposal maps four things together:

- where power is made;
- how it moves;
- where homes and businesses now make and store their own;
- how reliable and how costly it is.

Each is placed by municipio wherever a public source allows. Every figure was measured on 2026-11-13 from sources a script can read with no key.

## What the Romania map does, and what we would do differently

| Romania map | Observatory |
|---|---|
| OSM plants; capacity only where volunteers tagged it | **EIA-860M** for plants: official MW by technology, status, operating year and a point for every plant of 1 MW or more, monthly. OSM gives MW for only 31 of its 70 Puerto Rico plants. |
| Rooftop solar invisible | **Rooftop solar and batteries by municipio and LUMA district**, monthly, from LUMA's reports to the Energy Bureau. Counts only, never a roof (sensitive-places rule). |
| Red and green fuel colours, neon on black | Okabe-Ito colours, safe for colour-vision deficiency. Circle area proportional to MW, with a size legend. The dark base map (OpenFreeMap Dark, decision 102) is an option, not the default. |
| One date | **Time:** capacity and generation by month (EIA-860M and EIA-923), rooftop solar every month since 2010, batteries and electricity use by municipio every month since June 2021. |
| Lines as decoration | Lines to show the island's main fact: most capacity sits on the south coast (Aguirre, Costa Sur, EcoEléctrica, AES), while the most electricity is used in the north, so power crosses the Cordillera Central. LUMA's **electricity sales by municipio** make that visible. |
| No context | Reliability (SAIDI by LUMA district), price against the US, households' electricity bills by tract, hazards along the lines, and solar and wind potential, each beside the map. |

The preview (`docs/analysis/energy-2026-11/preview.svg`) puts three of these on one image: EIA plants, OSM lines and home batteries per 100 housing units by municipio. It is not a page of the site.

## What was measured (2026-11-13; no key needed for any source)

### Plants and generation (US EIA)

- **EIA-860M**, September 2026 file, released 2026-10-23, next release 2026-11-24. Puerto Rico has its own sheets: `Operating_PR`, `Planned_PR` and `Retired_PR`. Every row has latitude, longitude and operating year.
  - Operating: 228 generators at 67 plants, 6,474 MW including 38.2 MW of batteries.
  - By technology: petroleum 4,078.5 MW, natural gas 1,449.9, coal 510, solar 167.0, wind 127.8, hydro 98.1, landfill gas 4.8.
  - Renewable capacity is 397.7 MW, 6.1% of the total.
  - About 80 units are on standby.
  - Planned: only 22.2 MW (Bayamón and Humacao solar). The Energy Bureau's procurement-tranche projects are not listed.
  - We already use this file for counts by municipio (`infrastructure_series.json`, Phase 3 item 10). Its points stay in the local cache.
- **EIA-923**, 2025 final, Puerto Rico sheet, plants of 1 MW or more. I recomputed these figures from the file.
  - Net generation 16.37 TWh: natural gas 44.2%, residual fuel oil 24.2%, coal 17.0%, distillate 11.6%, solar 1.7%, wind 1.2%, hydro 0.3%.
  - **Renewable 3.1%.** Rooftop solar is not in this figure.
  - Monthly data run to August 2026. EIA notes that Puerto Rico data "may be incomplete".
  - EIA's bulk file ELEC.zip has no Puerto Rico series, so the build reads the yearly zips.
- **US Wind Turbine Database** (USGS/LBNL, public domain, keyless API): 63 turbines in 5 projects, 128.5 MW.
  - Santa Isabel: 44 turbines.
  - Punta Lima: rebuilt in 2024 with 13 turbines.
  - The US large-scale solar database (USPVDB) has no Puerto Rico.

### Rooftop solar and batteries (LUMA, filed with the Puerto Rico Energy Bureau)

LUMA's own website bars automated access, so the `power` row of the wanted-data list is "blocked". **The same reports are public filings on the Energy Bureau's site (energia.pr.gov)**, which states no terms of use and whose robots.txt blocks only `/wp-admin/`.

- **Monthly metrics workbook** (`Resumen-Metricas-Master_<Month><Year>.xlsx`, case NEPR-MI-2019-0007, sheet `T&D`). Monthly series from June 2021 to September 2026:
  - **Battery installations and kWh by municipio:** 189,459 and 3.15 GWh. LUMA splits San Juan into San Juan, Río Piedras and Santurce, so the three are added back together.
  - **Electricity sales by municipio**, in GWh.
  - **Share of customers on smart meters (AMI) by municipio.**
  - **Rooftop solar MW and installations by LUMA's 34 commercial districts:** 1,666.2 MW, 209,404 installations.
  - **SAIDI by LUMA's 16 technical districts.**
  - Curtailment and capacity factor of each utility-scale renewable plant.
- **Distributed generation exhibits** (case NEPR-MI-2019-0016, quarterly; newest 2026-08-14).
  - A monthly series from January 2010: 206,006 customers and 1,621.6 MW in June 2026.
  - The same by customer class: residential 1,479.4 MW.
  - File names change, so a script reads the case page to find them.
- **EIA-861M** (monthly, public domain) carries the same net metering figures under PREPA's utility number: 207,976 customers and 1,647.6 MW AC in August 2026. It goes back to 2011 (57.6 MW in December 2015). It also lists Sunrun's leased systems: 70,128 customers and 499.8 MW / 1,044 MWh of batteries. EIA's annual file gives 1,455.6 MW at the end of 2025.
- **Geography.** No source gives rooftop solar by municipio. It is by LUMA district or by LUMA region. LUMA publishes no outline of its districts. Batteries, sales and AMI are by municipio.

### The grid (lines and substations)

- **OpenStreetMap** (Overpass, ODbL, data of 2026-11-13). It is the only current, open source a script can read.
  - Lines: 230 kV 752 km, one connected network. 115 kV 900 km, 97% in one piece. 38 kV about 1,050 km. 281 km carry no voltage.
  - The 2019 Integrated Resource Plan gives 413, 702 and 1,376 circuit miles. So OSM has the whole 230 kV network, about 82% of the 115 kV length and about **half of the 38 kV length**.
  - 549 substations, 296 with a voltage.
  - 24,886 solar generators, 24,303 of them tagged on roofs.
- **HIFLD Open** went offline in August 2025. An archived copy of its transmission lines (Esri, licence of the Esri master agreement) holds data from 2016 to 2020. HIFLD never published substations.
- **Island government GIS** (PRITS): a 2014 file of the Electric Power Authority (44,713 line segments, 961 substations), no licence stated. **NREL PR100** has a 115/230 kV line file with no licence of its own. Both are useful as checks only.
- **Sensitivity.** In a 2024 filing with the Energy Bureau, LUMA asked that the location and availability of its lines be treated as Critical Energy Infrastructure Information (CEII; 6 U.S.C. §§ 671-674, 18 C.F.R. § 388.113, Bureau policy CEPR-MI-2016-0009). EIA's FAQ says that EIA and HIFLD do not publish the location of substations. The lines are drawn in OpenStreetMap and visible on the ground, but FPR is choosing what it republishes (decision (c)).

### Reliability, price and bills

- **Reliability, 2025** (EIA-861):
  - SAIDI 3,547 minutes and SAIFI 17.17 interruptions per customer, with major event days.
  - 2,151 minutes and 15.5 without them.
  - LUMA's transmission-and-distribution-only measure for fiscal year 2026 is 1,656 minutes and 7.83. It leaves out generation shortfalls, and LUMA restates past values.
- **Outages**, EAGLE-I (ORNL, CC BY 4.0, keyless figshare API): 2021 to 2025. Puerto Rico is reported as LUMA's six regions under six municipio codes, so every use is labelled regional.
- **Price** (EIA-861M, August 2026, residential): Puerto Rico 26.36 cents per kWh, the United States 18.16.
- **Bills** (ACS 2020-2024, table B25132, keyless summary file, tract to island): 11.8% of the households that pay for electricity separately pay $250 or more a month (147,196 of 1,247,570).

### Potential

- **Global Solar Atlas** (World Bank and Solargis):
  - Rasters: PVOUT about 1 km, mean 4.57 kWh/kWp a day (range 3.61-5.01); GHI 250 m. Zip of 3.6 MB, files dated 2019.
  - Licence: CC BY 4.0, but the file's metadata adds **a binding mediation and arbitration clause** (decision (f)).
- **Global Wind Atlas 4.0** (DTU, CC BY 4.0): wind speed, power density and capacity factor at 250 m, 100 m above ground, keyless.
- **NREL PR100** (CC BY 4.0, OEDI):
  - Rooftop PV technical potential by roof plane, partitioned by municipio.
  - Modelled rooftop solar and storage adoption by municipio to 2050. Its scenario for 2026 is 828 MW; the real figure is about 1,650 MW, which is worth saying on the page.
- **NASA POWER:** a keyless API for points. **NSRDB:** its API needs a key. The S3 copy is 6 GB a year.

### Policy (for the page's context, facts only)

- **Act 17-2019:**
  - Renewable targets of 40% by 2025, 60% by 2040 and 100% by 2050.
  - No coal after 2028-01-01.
- **Act 1-2025:**
  - Removed the 40% and 60% interim targets and kept 100% by 2050.
  - Moved the end of coal to 2032-12-31.
  - The English text and the official compilation give different approval dates (March 3 and March 19, 2025).
- **Operators:** Genera PR runs the legacy generation (since July 2023); LUMA runs transmission and distribution.
- **Integrated Resource Plan:** LUMA filed the 2025 plan on 2025-10-17 (NEPR-AP-2023-0004). The Bureau deemed it complete on 2026-02-13. No final order was found.

## The steps, first visible result first

Effort as in `docs/proposal-2026-10.md`: **S** under 1 day, **M** 2-4 days, **L** 1-2 weeks. Each step is its own pull request, merged only on the project lead's word.

1. **Power plants on the map (S-M). Shows on the site first.**
   - Build: `energy.py` reads EIA-860M `Operating_PR` and `Planned_PR`, finding the newest file's link on EIA's page, and writes `power_plants.geojson`. Each plant is one point: EIA id, plant name, MW by technology, main technology, standby MW, first and last operating year, and status (operating or planned).
   - Map: a new subheading **Energy / Energía** under Infrastructure and mobility, in the 2D map and the 3D view, through `Core.facilities` (a new "sized" point kind). Circle area is proportional to MW and colour shows the main technology; planned plants have a dashed outline and standby capacity a hollow ring. The pop-up shows MW by technology.
   - Refresh: the bot refreshes it monthly after EIA's release (around the 24th).
   - Also in this PR: the wanted-data rows (`eia-860m`, `power`, `grid-assets`, `eagle-i`, plus new rows for EIA-923, EIA-861M, the LUMA filings, OSM power, Global Solar Atlas, Global Wind Atlas, PR100 and B25132), with the dictionary's counts updated; glossary terms for transmission line, kV, net generation, standby and capacity factor.
2. **Transmission lines (M).**
   - Build: OSM 230, 115 and 38 kV from Overpass, monthly, as `power_lines.geojson` (ODbL, its own layer, never joined to EIA's data, so EIA's data stay public domain).
   - Map: lines coloured by voltage, with 38 kV marked "about half mapped". Shape and substations as decided in (c).
   - Also: kilometres of line by voltage in FEMA flood areas, in landslide susceptibility classes and under sea level rise, as counts for step 3.
3. **Knowledge Area page "Energy in Puerto Rico" / "Energía en Puerto Rico" (M).** The page shows:
   - generation by fuel every month (EIA-923) and capacity by technology (EIA-860M);
   - the renewable share against the law's target, with utility plants and rooftop solar shown apart;
   - rooftop solar every month since 2010 and batteries since 2021;
   - residential price against the United States (EIA-861M);
   - reliability (EIA-861 each year; LUMA's districts each month);
   - electricity use by municipio (the north–south picture);
   - the grid's exposure to hazards (from step 2).
4. **Datasets by municipio and barrio for Explore, Analysis and the profiles (M).** Each by month since June 2021:
   - batteries per 100 housing units;
   - electricity sales per resident;
   - share of customers on smart meters;
   - households paying $250 or more a month for electricity (B25132, by municipio, barrio and tract).

   Rooftop solar by LUMA district goes on the page as a table, since the districts have no published outline.
5. **Solar and wind potential (M).**
   - Map: a wind speed image (Global Wind Atlas, 100 m) and, if cleared, the solar image (Global Solar Atlas).
   - PR100 rooftop technical potential summed by barrio, never by roof.
   - On the page: PR100's projected adoption against the real figures.
6. **Outages (S).** EAGLE-I 2021-2025 on the page, labelled by LUMA region. It fits beside the night lights (VNP46A3) that the observatory already has.

## Rules that apply to every step

- **Freshest source, with a harvester.** EIA monthly files, LUMA's monthly workbook and quarterly exhibits, OSM monthly, all through the refresh bot. Rasters are read once and checked each year. Caches go in `C:/t/cache/energy`, never in the synced folder.
- **Counts, not homes.** Rooftop solar and batteries only by municipio, barrio or LUMA district. OSM's 24,303 rooftop generators and PR100's roof planes are never drawn. Plants of 1 MW or more are businesses and public plants, not homes.
- **Every technical word** gets a sourced English and Spanish glossary entry in the PR that first shows it. Examples: kV, transmission line, substation, net metering, battery energy storage (kWh against kW), SAIDI, SAIFI, major event day, net generation, capacity factor, renewable portfolio standard, CEII, AMI.
- **Credit lines:** "US Energy Information Administration (EIA-860M, EIA-923, EIA-861M)"; "LUMA Energy, filed with the Puerto Rico Energy Bureau (case …)"; "© OpenStreetMap contributors (ODbL)"; "USGS/LBNL US Wind Turbine Database"; "Global Wind Atlas 4.0 (DTU), CC BY 4.0"; "NREL PR100 (CC BY 4.0)"; "US Census Bureau, ACS 2020-2024".
- **Weight:** map scripts 189.5 of 250 KB on main (measured 2026-11-13 on an LF copy). The energy layers load on first use, as the facility layers do.
- **Colours** are checked with `docs/palettes.md`'s method before the first PR.

## Not taken, and why

- **LUMA's outage map and website:** its terms bar automated access.
- **HIFLD archive lines:** data from 2016-2020 under Esri's licence.
- **PRITS 2014 grid file:** no licence stated, and 12 years old.
- **PR100 line file:** no licence of its own. Like PRITS, it serves as an internal check only.
- **EIA ELEC.zip** and **USPVDB:** neither has Puerto Rico data.
- **NSRDB API:** needs a key.
- **Google Project Sunroof:** Google-derived data, which the observatory does not use.
- **DOE's Puerto Rico Energy Resilience Fund (Acceso Solar):** more than 6,000 households received systems (DOE, 2026-03-04), but there is no dataset and nothing by municipio. Its eight awards were cancelled on 2026-01-09. It can be a sentence on the page.
- **LUMA's battery demand-response program:** about 115,000 customers enrolled (LUMA filing of 2026-10-06), in PDF filings only. It can be a sentence on the page.

## Decisions for the project lead (decision 104)

- **(a)** Approve the order: 1 plants (first visible), 2 lines, 3 page, 4 municipio datasets, 5 potential, 6 outages.
- **(b)** Publish EIA's plant points with plant name, MW by technology, status and years, but not the owner. This reverses item 10's choice of keeping the points in the cache. EIA publishes them; every plant is 1 MW or more, and none is a home. Recommended: yes.
- **(c)** Lines and substations. Recommended:
  - draw OSM's 230, 115 and 38 kV lines simplified to about 100 m, so the map shows the network's shape and not tower-level detail;
  - draw no substations or towers; count substations by municipio only.

  The alternative is to draw the 115 and 230 kV substations without names, as public OSM viewers already do. The reason for the recommendation is LUMA's CEII stance in its filings and EIA's practice of not publishing substations.
- **(d)** Read LUMA's filings on the Energy Bureau's site by script, credited to LUMA and the Bureau, with "no licence stated" in the data contract, as for USAspending. Recommended: yes. It turns the blocked `power` row into monthly data by municipio.
- **(e)** A new sub-domain **Energy / Energía** under Infrastructure (`infrastructure.energy` in `domains.json`), so energy datasets group together in Explore, the Catalog and the menu. Recommended: yes.
- **(f)** The Global Solar Atlas's arbitration clause: ask Compliance, and meanwhile use only the Global Wind Atlas. The other way is to leave the solar image out and give the page NASA POWER's coarse solar figure. Recommended: ask Compliance.
- **(g)** Name of the page: "Energía en Puerto Rico" / "Energy in Puerto Rico". Recommended: yes.

## Sources checked

- EIA-860M https://www.eia.gov/electricity/data/eia860m/ · EIA-923 https://www.eia.gov/electricity/data/eia923/ · EIA-861 and 861M https://www.eia.gov/electricity/data/eia861/ and https://www.eia.gov/electricity/data/eia861m/ · Puerto Rico territory profile https://www.eia.gov/state/?sid=RQ (text updated 2026-05-21) · EIA FAQ on substations https://www.eia.gov/tools/faqs/faq.php?id=567
- Energy Bureau cases NEPR-MI-2019-0007 (metrics), NEPR-MI-2019-0016 (distributed generation, https://energia.pr.gov/en/dockets/?docket=nepr-mi-2019-0016), NEPR-AP-2023-0004 (IRP; resolution of 2026-02-13), NEPR-MI-2026-0002 (battery program) · 2019 IRP Appendix 1 (line lengths)
- OpenStreetMap https://www.openstreetmap.org/copyright · ODbL collective database guideline https://osmfoundation.org/wiki/Licence/Community_Guidelines/Collective_Database_Guideline_Guideline
- HIFLD Open shutdown: https://www.datarescueproject.org/hifld-data-saved/ · PRITS grid file https://gis.pr.gov/descargaGeodatos/Infraestructuras/Pages/Electricidad.aspx
- US Wind Turbine Database https://energy.usgs.gov/uswtdb/ · USPVDB https://energy.usgs.gov/uspvdb/
- Global Solar Atlas https://globalsolaratlas.info · Global Wind Atlas https://globalwindatlas.info · NASA POWER https://power.larc.nasa.gov/api/
- NREL PR100 data https://data.openei.org/submissions/5749 · PVRDB-PR https://catalog.data.gov/dataset/pv-rooftop-database-for-puerto-rico-pvrdb-pr
- EAGLE-I https://api.figshare.com/v2/articles/24237376 · ACS summary file (B25132) https://www2.census.gov/programs-surveys/acs/summary_file/2024/table-based-SF/ · DOE PR-ERF Q&A https://www.energy.gov/oe/puerto-rico-energy-resilience-fund-qas
- Act 17-2019 https://bvirtualogp.pr.gov/ogp/Bvirtual/leyesreferencia/PDF/2-ingles/17-2019.pdf · Act 1-2025 https://bvirtualogp.pr.gov/ogp/Bvirtual/leyesreferencia/PDF/2-ingles/0001-2025.pdf
