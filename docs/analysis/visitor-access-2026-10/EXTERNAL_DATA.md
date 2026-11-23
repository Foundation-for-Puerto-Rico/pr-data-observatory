# External open data for visitor-to-transport access (checked 2026-10-05)

Compiled on 2026-10-05 by a research subagent working for this session, using only keyless, open sources (curl, web fetch, web search and small Overpass count queries). Each finding is labelled **verified by request** (the agent fetched the file or the API) or **documentation only**. The figures below were **not re-verified by FPR staff**. Licences and reuse terms marked "not stated" must be confirmed in writing with the publisher before anything is harvested (see `site/data/wanted.json`, where every candidate is a row with its status). No personal data is reproduced: staff names, phone numbers and e-mail addresses that appear on source pages were not copied.

The 21 rows added to `site/data/wanted.json` from this research are in `wanted_rows_added.json` (a copy, for traceability).

## Part A. Summary

**Worth adding**
- **Ferries.** Official itineraries (PDF) plus ATI's fare regulation: non-residents pay 11.25 USD per trip plus a 2 USD fee; vehicles board only if owned by residents; residents have priority. The BTS ferry census (2024) gives passengers (Vieques 641,183, Culebra 546,258, Cataño 428,604) and vessel capacity (72 to 574). ATI's GTFS is the only machine-readable schedule, but its Culebra times and weekend Vieques times differ from the PDFs, and its run times are too short.
- **Gateways.** FAA CY2025 and BTS T-100 monthly passengers (PASS). PRTC and Ports Authority monthly PDFs/spreadsheets for 10 airports and cruise calls (PARTIAL: PDF/XLSX, no licence).
- **Transit stops.** BTS National Transit Map has 1,642 stops in 13 municipalities where the twin has no feed. Check this before sending the municipal outreach.
- **Last mile.** Official taxi fixed fares (21 USD to Old San Juan and the piers), the airport ground-transport page, EPA walkability for all 2,552 block groups, 25 EV chargers (OSM has 11), NPS visits, PRTC regional occupancy, island geoserver layers (160 lodgings, 144 attractions, 2010 públicos lines, 2026 roads).

**Blocked or not open**
- Opening hours at scale: Overture has no field; OSM has them for about 6% of attractions. Ask Overture, PRTC.
- Real-time: ATI says GTFS-RT is in development; ferry and bus positions are app-only. Ask ATI, Hornblower.
- Current públicos and franchise data: none public. Ask NTSP.
- El Yunque visits: the Forest Service app answers 403 (not bypassed). Ask the Forest Service, DRNA.
- Hotel rooms by property: not published. Ask PRTC.
- Not usable: Discover Puerto Rico (bot challenge), Inside Airbnb (no Puerto Rico), bike/scooter service areas, sidewalk inventories.

**Fix.** The `cruise` row url (pports.org) does not resolve; use prpa.pr.gov and tourism.pr.gov/statistics.

**Housekeeping.** The research agent wrote one temporary file into the repository root by mistake and deleted it at once; no other repository file was touched by it.

---

## Part B. Full report

Open and keyless sources only. No keys, accounts or sign-in; no bot protection bypassed. Every finding is labelled **verified by request** or **documentation only**.
**Verdicts:** PASS = keyless, Puerto Rico rows present, usable. PARTIAL = usable with the gap stated. FAIL = not usable (reason given).

### B1. Verdict table

| # | Candidate | Verdict | How checked |
|---|---|---|---|
| 1.1 | ATI GTFS ferry routes | PARTIAL | verified by request |
| 1.2 | Official ferry itineraries (PDF) | PARTIAL | verified by request |
| 1.3 | Ferry fares, reservation and capacity rules | PARTIAL | verified by request (news: documentation only) |
| 1.4 | BTS National Census of Ferry Operators | PASS | verified by request |
| 1.5 | Ferry real-time and app data | FAIL | verified by request |
| 2.1 | FAA enplanements CY2025 | PASS | verified by request |
| 2.2 | BTS T-100 monthly by airport | PASS | verified by request |
| 2.3 | Ports Authority monthly report (10 airports, cruise) | PARTIAL | verified by request |
| 2.4 | Cruise calls and passengers | PARTIAL | verified by request |
| 2.5 | CLIA | FAIL | documentation only |
| 2.6 | Visitor arrivals by mode | PARTIAL | verified by request |
| 3.1 | Taxi Turístico fixed fares | PARTIAL | verified by request |
| 3.2 | San Juan airport ground-transport page | PARTIAL | verified by request |
| 3.3 | Car-rental locations | PARTIAL | verified by request |
| 3.4 | Públicos and shared vans | PARTIAL (2010 lines); FAIL (current) | verified by request |
| 3.5 | Bike and scooter share | PARTIAL (city list); FAIL (GBFS, OSM) | verified by request |
| 3.6 | EV charging | PASS (BTS copy); AFDC API needs a key | verified by request |
| 4.1 | OSM pedestrian network | PARTIAL (too thin to route) | verified by request |
| 4.2 | EPA National Walkability Index | PASS | verified by request |
| 4.3 | Official sidewalk or curb-ramp inventory | FAIL | documentation only |
| 4.4 | FHWA HPMS traffic and road condition | PASS (already `traffic`) | verified by request |
| 4.5 | DTOP traffic counts | FAIL | verified by request |
| 4.6 | Open travel-time data | FAIL | documentation only |
| 5.1 | Opening hours in Overture | FAIL | verified by request |
| 5.2 | Opening hours in OSM | FAIL at scale | verified by request |
| 6.1 | NPS visits, San Juan NHS | PASS | verified by request |
| 6.2 | El Yunque visits (Forest Service) | FAIL (403) | verified by request |
| 6.3 | State forest, reserve and balneario visits | FAIL | documentation only |
| 6.4 | Museum and attraction attendance | FAIL | documentation only |
| 6.5 | Hotel occupancy (PRTC) | PARTIAL | verified by request |
| 6.6 | Lodging inventory and rooms | PARTIAL (160 points, no rooms); FAIL (rooms) | verified by request |
| 6.7 | Visitor Profile survey 2023-24 | PARTIAL | verified by request |
| 7.1 | ATI GTFS-Realtime | FAIL (in development) | verified by request |
| 7.2 | AMA Móvil, City Experiences apps | FAIL (app only) | verified by request (AMA: documentation only) |
| 7.3 | ATI Llame y Viaje | Not for visitors | verified by request |
| 8.1 | BTS National Transit Map (new) | PARTIAL | verified by request |
| 8.2 | Island geoserver, gis.pr.gov (new) | PARTIAL | verified by request |
| 8.3 | ATI shapefile and KML (new) | PASS but redundant | verified by request |

### B2. Findings by topic

#### 1. Ferries

**1.1 ATI GTFS ferry routes (PARTIAL).**
- Evidence: `https://docs.pr.gov/files/ATI/DATOS_ABIERTOS/GTFS/PRITA_GTFS.zip`, 2,234,433 bytes, modified 2026-08-26, service 2026-07-20 to 2027-07-19, agency ATI. 38 routes (33 bus, 4 ferry, 1 rail). Ferry routes: MA001 Cataño-Viejo San Juan, MA002 Ceiba-Culebra, MA003 Ceiba-Vieques, MA004 Ceiba-Mosquitos. Six stops (Cataño, San Juan, Ceiba, Culebra, Vieques Isabel II, Vieques Mosquito); 385 ferry trips. No Fajardo stop. Only one ferry fare: "Regular Lancha Metro" 2.00 USD (Cataño); nothing for Vieques or Culebra.
- Matches the PDFs: Cataño first and last departures (from Cataño 05:30 to 21:30 on weekdays; from San Juan 06:00 to 22:00) and Ceiba-Vieques on weekdays, apart from a Tuesday and Friday 3:45 AM departure only the PDF notes. The Cataño feed has a one-hour afternoon gap and a Sunday 23:30 departure that I could not check against the PDF day grid.
- Does not match: Ceiba-Culebra on all days (feed 8 weekday and 9 weekend departures each way; PDF 7; the feed adds 06:00, 06:30, 07:30 and lacks 5:30 AM and 5:30 PM) and Ceiba-Vieques at weekends (feed 8 each way, first 05:00; PDF 6, first 4:30 AM).
- Crossing times conflict: feed 45 minutes for both islands; operator portal 60 (Vieques) and 90 (Culebra); 2024 census 60 and 90; ATI's page 35 to 45 for Vieques; 2020 census 30 and 50 to 55. Use 60 and 90.
- Only machine-readable schedule? Yes. BTS National Transit Map holds the same 6 stops and 8 route lines without times; the BTS census has terminals and volumes; tickets, alerts and live tracking sit in the City Experiences app with no public feed.
- Terms: no licence in the feed; ATI's open data page names none ([page](https://www.ati.pr.gov/relaciones-comunidad?tab=DatosAbiertos)). Cadence: irregular ("Updated: Aug 26, 2026"). Size: 2.2 MB. Personal data: none (a role mailbox). Ask: ATI planning office.

**1.2 Official itineraries (PARTIAL).**
- PDFs on puertoricoferry.com: Vieques (309,639 bytes) and Culebra (360,433 bytes), effective 2026-08-01 to 2026-11-30, last update 2026-06-03; Cataño (316,815 bytes, March 2026). Text layer present. They state schedules are set at the direction of the Government of Puerto Rico and refer changes to DTOP.
- Departures (PDF): Ceiba-Vieques weekdays from Ceiba 4:30, 4:45 (Mosquito), 8:30, 1:00 pm, 3:00 pm, 4:45 pm (Mosquito), 6:30 pm, 8:00 pm; return 6:00, 7:15, 10:00, 3:00 pm, 4:30 pm, 7:15 pm, 8:30 pm, 9:30 pm; weekends 6 each way (4:30 am to 8:00 pm from Ceiba; 6:00 am to 9:30 pm back). Ceiba-Culebra weekdays 3:30, 5:30, 9:00, 12:30 pm, 3:30 pm, 5:30 pm, 7:30 pm; return 6:00, 8:00, 11:30, 3:30 pm, 5:30 pm, 7:30 pm, 9:30 pm; weekends 7 each way. Cataño-Old San Juan hourly, 5:30 am to 9:30 pm from Cataño, 6:00 am to 10:00 pm from San Juan (weekends later), 12-minute crossing. The earliest sailing leaves Ceiba at 3:30 AM.
- Terms: not stated; footer "All rights reserved"; robots file allows crawling; I read three PDFs and did not scrape. Cadence: seasonal (next after 2026-11-30). Size 0.3 MB each. Personal data: none. Ask: ATI.

**1.3 Fares, reservation and capacity (PARTIAL).**
- Operator: ferries now sit under ATI (site, GTFS, fare regulation); the old name Autoridad de Transporte Marítimo survives in legacy text. Tickets run under "Puerto Rico Ferry anchored by Hornblower"; the 2024 census names the operator "HMS Puerto Rico Ferry".
- Fares ([ATI regulation, PDF 192,637 bytes, 2025-02](https://docs.pr.gov/files/ATI/DERECHOS%20CIVILES/ATI%20-%20Reglamento%20de%20Tarifas%204867-0710-5125%20v.%206%20(002)%20Rev%20Final%2020%20feb%202025%20(1).pdf)): adult single trip, residents 2.00 (Vieques) or 2.25 (Culebra), non-residents 11.25 on both; a 2.00 conservation fee for each boarding or disembarking at Vieques or Culebra; Cataño-Old San Juan 2.00 (60 to 74 and disabled 0.50; 75 and over free). The regulation says it takes effect 1 January 2026 once filed; news (Metro, 2026-05-03) says the non-resident rise took effect 2026-05-05 after a delay. Conflict: the portal rates page still shows 2.00 and 2.25 for adults (apparently resident prices). The regulation's child and senior table extracted badly; read it by eye.
- Boarding rules (portal, Aug 2026): arrive one hour before; check-in closes 10 minutes before; all sales final; transfers at least one hour before and at most twice; infant and senior tickets only at the port window with photo ID; ID must match the ticket name for residents; pets in carriers; extra items (coolers, chairs, boards, bikes) need paid tickets.
- Capacity: travel is "subject to availability and priority to bona fide residents" ([terms](https://www.puertoricoferry.com/en/terms-and-conditions/), modified 2020-09-09). Vessel capacities are in 1.4. A reserved block of resident tickets was reported in earlier news; not confirmed (documentation only).
- Vehicles: the rates page lists vehicle prices but says vehicles board only if owned by a resident of Vieques or Culebra.
- Last mile from Ceiba (rates page; not sold online): Luquillo town 3.00; Río Grande 4.00 or 5.50; Canóvanas 7.00; Río Piedras 9.00 (minimum 30.00); shared rides Ceiba town 2.00, Fajardo 3.00, Humacao 5.00 (minimum four tickets).
- Hato Rey: the operator lists three routes only and the feed has no Hato Rey stop. A search summary says the line is discontinued (documentation only).
- Ask: ATI (fare in force, itinerary after 2026-11-30); Hornblower for the ground-transfer service.

**1.4 BTS National Census of Ferry Operators (PASS).**
- 2024 files on data.bts.gov (Socrata, keyless): Operator Segment `7umd-qc2k`, Vessels `u6m4-3cmd`, Terminals `difu-6bgs`, Operators `qzhh-3xej` (updated 2026-06). Operator 104 "HMS Puerto Rico Ferry".
- 2024 passengers, both directions: Ceiba-Vieques 641,183 (2,649 + 2,637 trips; 21,241 + 22,424 vehicles); Ceiba-Culebra 546,258 (2,750 + 2,750 trips); Cataño-Old San Juan 428,604 (4,835 + 5,002 trips). Average trip 60, 90 and 12 minutes. Two segments with one trip a year (114 and 120 passengers). The 2020 census (map layers, data for 2019): Cataño 631,179; Vieques 530,295; Culebra 477,704.
- Vessels: 24 listed, 10 in service; capacities 72 to 574 (Isla Bonita 401 passengers and 16 vehicles, Cayo Largo 297 and 19, Cayo Blanco 574, Santa María 128 and 20, Simplicity 149).
- Terminals (six, self-reported flags): local bus at all; intercity bus at Cataño and Old San Juan; bike share only at Old San Juan Pier Two; parking at all.
- Licence: "Public Domain U.S. Government" (Socrata); map layers: "available for unrestricted public use" ([layer](https://services.arcgis.com/xOi1kZaI0eWDREZv/arcgis/rest/services/NTAD_Ferry_Routes/FeatureServer/0)). Cadence: every two years. Grain: route segment, terminal, vessel; yearly totals. Size: under 20 KB. Personal data: none. Open point: the reference year of the 2024 file is not stated.

**1.5 Ferry real-time and app data (FAIL).** The portal and ATI pages say tracking, alerts and tickets live in the City Experiences app. No public feed.

#### 2. Gateway volumes

**2.1 FAA enplanements (PASS).** [CY2025 commercial-service file](https://www.faa.gov/airports/planning_capacity/passenger_allcargo_stats/passenger/arp-cy2025-commercial-service-enplanements.xlsx) 58,419 bytes (all-airports file 152,014), modified 2026-09-28. Eight airports, CY2025 (CY2024): San Juan 6,658,037 (6,490,669); Aguadilla 335,014 (360,645); Ponce 95,055 (137,553); Vieques 35,973 (37,756); Ceiba (RVR) 23,214 (19,681); Culebra 19,812 (14,663); Isla Grande 17,466 (16,844); Mayagüez 8,991 (9,207). Licence: US Government work; no licence stated on the page (documentation only). Cadence: yearly. Grain: airport, calendar year. Personal data: none (FAA staff contacts on the page not copied).

**2.2 BTS T-100 by origin airport (PASS).** `https://data.bts.gov/resource/r495-tyji.json` ("AFF - T100 Segment Summary By Origin Airport"), updated 2026-07-16. Seven airports (SJU, BQN, PSE, MAZ, VQS, CPX, SIG), monthly, January 2014 to April 2026 (up to 148 months). Fields include departures, passengers, seats, load factor, freight, mail, domestic and international splits. San Juan 6,479,732 passengers in 2024, 6,687,309 in 2025 (68,110 departures); January to April 2026: 595,942, 507,635, 638,285, 569,603. FAA and T-100 agree within about 1% (Culebra within 2%). Ceiba is not in T-100. Licence: "Public Domain U.S. Government". Size: about 1,000 rows (under 0.3 MB). Personal data: none.

**2.3 Ports Authority monthly operational report (PARTIAL).**
- Route 1: Instituto de Estadísticas inventory ([page](https://estadisticas.pr/en/inventario-de-estadisticas/carga_pasajeros_aereos_maritimos)): quarterly XLSX, 2023 Q1 to 2025 Q2 (latest published 2025-10-01, about 1 MB). Latest file: five fiscal years of monthly passengers in and out, cargo and operations for ten airports (San Juan, Aguadilla, Ponce, Mayagüez, Culebra, Ceiba, Humacao, Arecibo, Vieques, Isla Grande), monthly cruise passengers and calls, San Juan cargo tons.
- Route 2: PRTC statistics page, "Passenger Movement" PDFs (calendar year, fiscal year, comparison; 0.1 to 0.25 MB) for San Juan, Aguadilla and Ponce; the calendar-year file runs to July 2026 for San Juan though its heading says April. San Juan 2025: 6,824,176 in, 6,819,538 out.
- Gaps: spreadsheets lag a year; PDFs are fresher but PDF; Culebra April and May 2025 not provided; San Juan "out" counts exceed FAA enplanements (6.66 million) without explanation.
- Terms: no licence; the workbook says the report is free to distribute ("distribución gratuita") and that detailed figures are confidential and given on request. Personal data: a sheet names a responsible official with contacts; not copied. Ask: Autoridad de los Puertos (tariff affairs and economic studies); PRTC.

**2.4 Cruise (PARTIAL).**
- PRTC: `https://tourism.pr.gov/wp-content/uploads/2025/09/CY-Cruise-Info.pdf` and `FY-Cruise-Info.pdf` (about 0.24 MB, modified 2026-09-21): Old San Juan monthly passengers and trips, homeport vs in transit, with year-on-year change. 2025: 1,615,039 passengers (330,051 homeport, 1,284,988 in transit), 563 calls (205 and 358). The file lists Aug to Oct 2026 apart from the 2026 year-to-date (1,163,700 to July), so those months are probably scheduled calls (to confirm).
- San Juan Cruise Port ([statistics](https://sanjuancruiseport.com/port/statistics/)): yearly calls and passengers 2008 to 2025 in HTML; 2025 561 calls, 1,593,513 passengers (1.3% below PRTC); 2024 506 and 1,427,522 (1,162,607 transit, 264,915 turnaround).
- BTS (`bi2e-xh9z`, `3z7h-xatu`): 2023 only; San Juan 438 calls, 1,303,648 passengers.
- Piers: a Ports Authority PDF ([Puertos Marítimos](https://docs.pr.gov/files/Puertos/Documents/Puertos%20Maritimos.pdf)) names Pier 1, Pier 2 (the Cataño ferry terminal), Piers 3 and 4, and Pan American Piers I and II. PRTC says the Pan American pier needs a taxi or rideshare, and Ponce gets a few calls a year. No pier coordinates or pier-level counts.
- Terms: PRTC footer "All rights reserved"; BTS none; cruise port terms not read. Cadence: monthly (PRTC), yearly (others). Size under 0.5 MB. Personal data: none. Ask: PRTC (spreadsheets, pier counts); Autoridad de los Puertos (coordinates).

**2.5 CLIA (FAIL, documentation only).** National and regional PDF reports; no Puerto Rico port-level open data found.

**2.6 Visitor arrivals by mode (PARTIAL).** Planning Board table in a [PRTC PDF](https://tourism.pr.gov/wp-content/uploads/2025/09/JP-Visitors-Expenditures-Contribution.pdf) (57,671 bytes): visitors and spending by fiscal year from 2010 (tourists in hotels, tourists elsewhere, excursionists) and tourism's share of GDP; island level. PRTC also lists "Origin Data" PDFs by country (2010 to 2024; listed, not opened). Gap: PDF only, no arrival-mode split beyond air, cruise and excursionist. Terms not stated. Ask: PRTC.

#### 3. Visitor ground transport

**3.1 Taxi Turístico fixed fares (PARTIAL).**
- Publisher: the Negociado de Transporte y Otros Servicios Públicos (NTSP) sets fares in [Reglamento 9358](https://ntsp.pr.gov/ServiciosProgramas/Secretaria/Reglamentos/Reglamentos/9358%20C%C3%B3digo%20de%20Reglamentos%20de%20la%20NTSP.pdf) (5,219,643 bytes, modified 2022-03-17). The code notes that tourist taxi firms were also identified as "TT" by NTSP and the Tourism Company. Aerostar publishes an airport card.
- Evidence: chapter VIII: metered tariff (8.09); fixed fares from the airport to 74 municipalities (30 to 177 USD) and 11 areas of interest (8.11); fixed fares from the Port of Ponce to about 20 places (8.12); allowed surcharges (8.13). Airport card [`Taxis-Tarifario.pdf`](https://aeropuertosju.com/wp-content/uploads/2022/04/Taxis-Tarifario.pdf) (179,741 bytes, 2023-12, an image): Zone 2 Isla Verde 12; Zone 3 Ocean Park, Condado, Miramar, Santurce 17; Zone 4 Old San Juan and piers 21; Zone 5 Convention Center, Hyatt House, Isla Grande Airport, Sheraton 17; Coliseo and Plaza Carolina 16; Plaza las Américas 20; The Mall of San Juan 15. Surcharges: 3 airport fee, 1 per extra bag, 1 late night (10 pm to 6 am), 2 for the 6th and 7th passenger; per trip; tolls and tips extra.
- Gap: PDF only, tables keyed by hand, regulation from 2022. Terms: not stated (public regulation). Personal data: none. Ask: NTSP (table in force, as data); Compañía de Turismo.

**3.2 San Juan airport page (PARTIAL).** [aeropuertosju.com/transportacion](https://aeropuertosju.com/transportacion/) (Spanish, 167,175 bytes): taxi pickup at Terminal A main station and Terminal B (also for C); three bus stops on the departures level at Terminals A, D and E, routes to Isla Verde (T5 or D53), Condado (D53), Old San Juan (T5 or D53), Convention Center (D53) and Avenida Piñero (E40); Uber pickup at Terminal A and Terminals B and C columns 16 to 19 (Uber named as the only ride-hail service); 18 rental companies (Avis, Budget, Enterprise, Alamo, National, Thrifty, Hertz, Sixt, Dollar and nine more). Fares are "regulated and approved" by the Tourism Company. No coordinates or timetables. The ATI feed names these routes 5, 53 and 40 and has stops on Avenida José V. Caro about 300 to 500 m from the airport centre point, so a crosswalk and a terminal check are needed. The `www` host returned 500 and the English paths 404. Personal data: company phone numbers on the page, not copied. Ask: Aerostar Airport Holdings.

**3.3 Car rental (PARTIAL).** OSM (Overpass count, twin bounding box): 49 `amenity=car_rental` features (39 points, 10 areas), 6 with opening hours; the airport page alone lists 18 companies. NTSP regulates rental fleets (a circular on certifying rental-vehicle inventories exists; title seen in search, not opened); no public list. OSM is probably complete only for large brands and the airport. Licence: ODbL. Ask: NTSP.

**3.4 Públicos and shared vans (PARTIAL for 2010 lines, FAIL for current).** Island geoserver layer `g35_colectiva_rutas_porteadores_publicos_san_juan_metro_2010` (WFS, HTTP): 3,676 line segments, 64 route codes (for example `I-11-02`), direction text, and an ATI code (72 values); San Juan metro only; 2010; about 0.7 MB. OSM: 0 share-taxi routes, 60 bus route relations (the twin holds 16 as community routes). NTSP: no public franchise or route list. Ask: NTSP, ATI.

**3.5 Bike and scooter share (PARTIAL city list; FAIL GBFS and OSM).** BTS NTAD Bikeshare and Scooter Systems ([layer](https://services.arcgis.com/xOi1kZaI0eWDREZv/arcgis/rest/services/NTAD_Bikeshare_Scooter_Systems/FeatureServer/0), updated 2026-01-02): 22 Puerto Rico rows for Guaynabo, San Juan (Río Piedras, Condado) and Mayagüez, 2019 to 2026 (a 2026 row has an as-of date of 2026-12, so it looks carried forward). Operators Skootel (all three) and KICK (San Juan); a dockless system in San Juan from 2022; no docks. MobilityData GBFS catalog (1,541 systems, 220 KB): no Puerto Rico system. OSM: 0 bicycle and 0 kick-scooter rental points. Ask: the operators or municipalities for service areas.

**3.6 EV charging (PASS for the BTS copy).** [BTS NTAD "Alternative Fueling Stations"](https://services.arcgis.com/xOi1kZaI0eWDREZv/arcgis/rest/services/Alternative_Fueling_Stations/FeatureServer/0), a daily copy of the Department of Energy list (last edit 2026-10-05): 25 Puerto Rico stations, all public EV; 20 open, 5 temporarily unavailable; 2 fast-charge and 50 level-2 ports; San Juan 6, Guaynabo 4, Río Grande 2; 9,272 bytes. OSM has 11. The AFDC developer API needs a free key (documentation only; the old `developer.nrel.gov` host did not resolve because the lab is now the National Laboratory of the Rockies) and the AFDC bulk download asks for contact details, so use the BTS copy. Licence: "available for unrestricted public use". Personal data: a business phone field; do not publish. The count looks low; treat as a lower bound.

#### 4. Walking and driving realism

**4.1 OSM pedestrian network (PARTIAL, too thin to route).** Overpass counts, twin bounding box: footway ways 8,487; tagged sidewalk 2,031; tagged crossing 1,182; crossing nodes 3,006; pedestrian streets 627; steps 341; drivable road ways 114,013, of which 232 carry a sidewalk tag (both, left, right or yes) and 62 say none. Sidewalk ways are about 2% of road ways. Walk along the road graph and adjust with 4.2. The main Overpass server timed out several times; counts were batched. Licence: ODbL.

**4.2 EPA National Walkability Index (PASS).** `https://geodata.epa.gov/arcgis/rest/services/OA/WalkabilityIndex/MapServer/0` (keyless): 2,552 Puerto Rico block groups (state code 72), all scored (range 1 to 7.3, mean 4.7); 183 fields including intersection density (D3B), distance to transit (D4A), job-household mix, car-free households (AutoOwn0, Pct_AO0). Built on 2019 block groups; page size 1,000 rows. Gap: 2019 boundaries and older inputs; the street data behind it may be licensed (documentation only: read the user guide before republishing). Licence: none in the service metadata; EPA is a US agency (confirm). Size: 3 to 4 MB with all fields; take about ten. Personal data: none.

**4.3 Official sidewalk or curb-ramp inventory (FAIL, documentation only).** Searches found none. DTOP's interactive map covers road projects only (verified by request).

**4.4 FHWA HPMS (PASS, already `traffic`).** Not re-tested. Re-count: the BTS `HPMS_National_Current` layer has 180,776 Puerto Rico segments (matches the row). Fields include AADT by vehicle type, functional class, lanes, speed limit, signals, terrain, `TRAVEL_TIME_CODE`, and condition fields (IRI, PSR, rutting, faulting, cracking percent, surface type). Whether condition fields are filled for Puerto Rico was not tested. Suggest naming them in the `traffic` row.

**4.5 DTOP traffic counts (FAIL).** DTOP's interactive map shows projects; the older traffic-count page named in search did not respond. Ask: DTOP, Autoridad de Carreteras y Transportación.

**4.6 Open travel-time data (FAIL, documentation only).** None found; the twin's road graph supplies times.

#### 5. Opening hours

**5.1 Overture (FAIL).** Places schema v2.0.0 ([reference](https://docs.overturemaps.org/schema/reference/places/place/)) has no hours field; `operating_status` is "not an indication of opening hours". Latest release listed: 2026-09-23.1.

**5.2 OSM `opening_hours` (FAIL at scale; small sample only).** Twin bounding box: any feature with the tag 1,892; food and drink 603 of 3,895 (15%); attractions 25 of 442 (6%); lodging 4 of 347 (1%); car rental 6 of 49. Against 35,118 listings this cannot align places with service hours. Use category assumptions and label them. Ask: Overture (feature request); PRTC.

#### 6. Demand weights

**6.1 NPS visits (PASS).** `https://irmaservices.nps.gov/v3/rest/stats/visitation?unitCodes=SAJU&startMonth=1&startYear=2019&endMonth=12&endYear=2026` returns monthly recreation visits (XML, 18,542 bytes): 2019 1,197,345; 2020 357,100; 2021 798,188; 2022 1,027,264; 2023 1,314,819; 2024 1,329,728; 2025 1,402,132. US Government work; no licence text found. To our knowledge the only NPS unit on the island (documentation only).

**6.2 El Yunque (FAIL).** The Forest Service results app answered 403 to plain requests; not bypassed. Secondary sources quote about 600,000 to 1.2 million a year (unconfirmed). Ask: USDA Forest Service (Caribbean National Forest, visitor use monitoring).

**6.3 State forests, reserves, balnearios (FAIL, documentation only).** DRNA pages describe 21 state forests, 45 reserves and 6 wildlife refuges but no visit counts. The island geoserver lists 32 balnearios (parking, lifeguard, Blue Flag) without counts. Ask: DRNA, Compañía de Parques Nacionales.

**6.4 Museum and attraction attendance (FAIL, documentation only).** IMLS museum files are retired (per the wanted list); searches found no open series.

**6.5 Hotel occupancy (PARTIAL).** Instituto inventory page for the PRTC monthly report: 10 monthly XLSX files, Nov 2022 to Dec 2024, with gaps; the Dec 2024 file (709,262 bytes) has two sheets (by region; by room classification 1 to 80, 81 to 200, over 200) with arrivals, non-resident and resident shares, occupancy, room-nights sold and available, average daily rate, length of stay, guests per room, guests. Regions: Metro, Porta Atlántico, Porta Caribe, Porta Cordillera, Porta del Este, Porta del Sol. PRTC route: [41-page PDF](https://tourism.pr.gov/wp-content/uploads/2026/09/2000-Actual-Year-Updated-CY.pdf) (297,100 bytes, modified 2026-09-28) with 2026 to June, and a selected-lodgings report (80 or more rooms, Metro vs non-Metro). [PRTC regions page](https://tourism.pr.gov/regions/) lists municipalities by region (names changed: Porta Capital, Porta del Mar); the geoserver has 78 region polygons (2010). Gap: region level, not municipio or property. Terms not stated (footer "All rights reserved"). Personal data: a named contact on the inventory page, not copied. Ask: PRTC statistics office.

**6.6 Lodging inventory (PARTIAL presence, FAIL rooms).** Geoserver `g07_turismo_hospederias_endosadas_2021`: 160 endorsed lodgings (name, category, region, municipio, coordinates), no rooms. PRTC pages describe categories but publish no list with rooms. Inside Airbnb has no Puerto Rico data (page of 572,110 bytes checked): FAIL. The room-tax page holds forms only. Ask: PRTC.

**6.7 Visitor Profile 2023-24 (PARTIAL).** [PDF, 1,694,567 bytes](https://tourism.pr.gov/wp-content/uploads/2025/07/Visitor-Profile-Fiscal-Year-2023-2024.pdf), 2024-10-31, Instituto de Estadísticas with PRTC. Surveyed at San Juan, Ponce and Aguadilla airports and the Old San Juan piers; 23,782 valid responses. 49% of air passengers are visitors, 46% residents, 5% stopover. Lodging 47% friends and family, 22% hotels, 20% short-term rentals. Car rental 13% and transport services 6% of visitor spending; 1,178,417 cruise passengers in transit, 69.74 USD each, 65% on 5 to 10 hour excursions. No question on getting around the island. Microdata for 2010 to 2012 on request only.

#### 7. Real-time and on-demand

- **7.1 ATI GTFS-Realtime (FAIL).** ATI's open data page (published 2026-08-10, read 2026-10-05) says it is developing GTFS-RT. The MobilityData catalog (6,479 feeds; 1,929 real-time) has no Puerto Rico real-time feed and only 3 Puerto Rico static feeds. Ask: ATI.
- **7.2 Apps (FAIL).** City Experiences (ferries) and AMA Móvil (documentation only) are apps with no public feed.
- **7.3 Llame y Viaje.** Eligibility-based paratransit, 1.50 USD, eight to nine metro municipalities; not a visitor service.
- **7.4 Uber.** Already held as a yes-or-no listing; nothing more open.

#### 8. Other sources found

**8.1 BTS National Transit Map (PARTIAL).** NTAD layers `NTAD_National_Transit_Map_Stops`, `_Routes`, `_Agencies` (keyless; compiled 2026-03-09): 5,590 stops, 112 route lines, 40 agencies in Puerto Rico; licence field "Public Domain". New for the twin: 1,642 stops in 13 municipalities with no feed in the twin (Carolina 449, Yauco 195, Barceloneta 190, Mayagüez 186, Camuy 136, Toa Baja 134, Cataño 114, Dorado 88, Gurabo 66, Cayey 31, Hormigueros 22, Añasco 22, Aguada 9), all bus stops inside Puerto Rico; route lines for Carolina (17), Añasco (4), Toa Baja (3). `OUTREACH_TRANSIT_DATA.md` asks 15 municipalities for a feed; 13 of them (all but Comerío and Lares) appear here. Ask BTS or FTA for the source URLs first. Gap: no timetables; a March snapshot. Size: the 13-municipality extract is 351 KB.

**8.2 Island geoserver, gis.pr.gov (PARTIAL).** "Descarga de Geodatos" links to a keyless WFS at `http://geoserver2.pr.gov/geoserver/pr_geodata/ows` (HTTP only; 458 layers). Counts: endorsed lodgings 2021 (160); attractions (144: name, category, market, municipality, region, address text, activities); balnearios 2016 (32); public beaches 2005 (55); Blue Flag 2018 (6); national parks 2010 (23); agritourism 2021 (34); tourist-region polygons 2010 (78); tourist interest zones 2010 (105); paradores and hotels 2010 (202); San Juan metro públicos 2010 (3,676); AcuaExpreso 2010 (1); ports 2010 (10); airports FAA 2021 (49); Tren Urbano stations (16); state roads 2026 (4,198); toll plazas 2018 (34). Several vintages are old; no licence stated. The twin's notes say its police layer holds officer names, so check each layer. Ask: PRITS.

**8.3 ATI shapefile and KML, 2025-05 (PASS, redundant).** `PRITA_SHP_FILE.zip` (204,199 bytes): 1,378 stops, 90 route directions with headway and speed ranges; KML 597,572 bytes. The GTFS is newer; use only for ready-made headways.

### B3. Notes for the twin

1. Fix the `cruise` url: pports.org fails DNS; use `https://tourism.pr.gov/statistics/` and `https://www.prpa.pr.gov/`.
2. Ferries: use 60 and 90 minutes for the crossings; treat GTFS ferry times for Culebra and weekend Vieques as unreliable; the PDFs are the reference for 2026-08-01 to 2026-11-30. Earliest sailings leave Ceiba at 3:30 and 4:30 AM.
3. Do not model visitor car access to Vieques and Culebra.
4. Reconcile section 2 of `OUTREACH_TRANSIT_DATA.md` with 8.1 before sending.
5. Replace or complement the 11 OSM EV points with the 25 BTS/AFDC stations.
6. Build a route-name crosswalk for the airport bus routes (T5, D53, E40 vs GTFS 5, 53, 40; to confirm).
7. Add the HPMS condition fields to the `traffic` row note.
8. PRTC, NTSP and the Ports Authority state no licence; confirm reuse in writing before harvesting. EPA walkability may rest on licensed street data.

### B4. Method and limits

- Tools: curl, web fetch, web search. Overpass: count queries only, twin bounding box (17.85, -67.97, 18.57, -65.20).
- Transfers about 27 MB; largest: NTSP regulation 5.2 MB, Mobility Database catalog 2.6 MB, ATI GTFS 2.2 MB. The airport terminal map PDF (2.3 MB) came down by mistake and was not used. The Mobility Database and GBFS catalogs are national files, fetched only to check for Puerto Rico entries; the Mobility Database file is served from MobilityData's own domain (not Google Maps data).
- Not used: discoverpuertorico.com (bot challenge, 403), apps.fs.usda.gov NVUM (403), the ATI maritime fare link on Google Drive (Google product), the AFDC download (asks for contact details). Did not resolve: pports.org, developer.nrel.gov, www.puertorricoferry.com (typo; the site is puertoricoferry.com), geoserver.pr.gov. www.aeropuertosju.com answered 500.
- Not tested: whether HPMS condition fields are filled for Puerto Rico; municipal real-time feeds; reuse terms for PRTC, NTSP and the cruise port; the reference year of the 2024 ferry census.
- Personal data: none reproduced. Staff names, phones and emails appear on several source pages (Instituto, FAA, Ports Authority sheet, PRTC) and were not copied; nor were rental-company phone numbers.
- Repository: read only, apart from the stray `wi_meta.json` I created and deleted. Other changes I saw there during the session (Spanish-interface files, README, docs, site scripts) were not mine.
