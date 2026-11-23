# Function crosswalk: the review decisions

Francis asked on 2026-11-09 for the flagged rows to be decided (HANDOFF decision 92). Each row was decided against the UN Classification of the Functions of Government (COFOG),
mapped to the crosswalk's functions, with one rule for rows of the same kind. Three functions changed; the other rows keep the draft's choice, now reviewed.

| Kind | Code | Name | Function | Decision |
|---|---|---|---|---|
| ogp_concept | 011 | Compra de equipo | (from the entity) | Kept capex: equipment purchases are capital outlay in OGP's structure, and capex is never apportioned |
| ogp_concept | 081 | Asignaciones englobadas | (from the entity) | Kept 'other': a lump-sum appropriation's concept is what its object of expense says |
| ogp_concept | 082 | Asignación pareo de fondos federales | (from the entity) | Kept transfers: the state match moves money into federal programs |
| ogp_concept | 089 | Pago de deudas contraídas en años anteriores | (from the entity) | Kept 'other': prior-year bills are not bond debt service |
| ogp_agency | 017 | Asignaciones bajo la Custodia de la Oficina de Gerencia y Presupuesto | general_government | Kept general_government: government-wide items (COFOG 01.3 general services); the object rows give the named lines theirs |
| ogp_agency | 025 | Departamento De Hacienda Custodia | other | Kept 'other' for what the budget resolutions do not name; the object rows give every named line its function |
| ogp_agency | 161 | Autoridad para el Financiamiento de la Infraestructura | economic_development | Kept economic_development: the Authority's own budget is its administration ($4 M); the works it finances are in other agencies' lines |
| ogp_agency | 162 | Autoridad de Edificios Públicos | general_government | Kept general_government: the Public Buildings Authority rents and maintains buildings for many agencies (COFOG 01.3); the schools' share is not in the sheets |
| ogp_agency | 276 | Autoridad para las Alianzas Público Privadas | utilities_energy | Changed to utilities_energy: the Authority's budget is the energy system's operation and generation contracts (COFOG 04.3 fuel and energy) |
| ogp_agency | 310 | Corporación de Financiamiento Municipal | debt_pensions | Kept debt_pensions: COFIM pays municipal debt service (COFOG 01.7 public debt transactions) |
| ogp_agency | 311 | Comision Juegos Gobierno PR | other | Kept 'other': the Gaming Commission mostly distributes gaming revenue to several functions |
| ogp_program | 016-2076 | Programa de Banda Ancha en Puerto Rico | utilities_energy | Kept utilities_energy, whose label includes communications (COFOG 04.6) |
| ogp_program | 024-1550 | Administración de la Lotería de Puerto Rico | other | Kept 'other': lottery operations, as 024-1551 |
| ogp_program | 024-1551 | Administración de la Lotería Electrónica | other | Kept 'other': lottery operations are a commercial activity (prizes and sales costs), not a function of government |
| ogp_program | 070-1138 | Servicios Médicos a Trabajadores Lesionados | health | Kept health: medical care is health (COFOG 07) inside any agency |
| ogp_program | 045-1224 | Servicios de Emergencias Médicas | health | Changed to health: ambulance and paramedical services are health (COFOG 07.2), whatever department runs them |
| ogp_program | 162-1586 | Conservación y Mantenimiento de Estructuras Físicas | general_government | Kept general_government, as its agency 162 |
| ogp_object | 025-E6390 | Otras compensaciones no clasificadas | other | Kept 'other' for the years and funds no budget resolution names |
| ogp_object | 025-E9760 | Transferencia operacional (salida) | other | Kept 'other' for FY2025, which mixes transit transfers and rum cover-over payments; FY2026 and FY2027 keep transportation |
| ogp_object | 025-E9761 | Transferencia mismo fondo | other | Kept 'other': compulsory auto insurance premiums passed to the insurers, a pass-through |
| ogp_object | 025-E6170 | Donativos y aportaciones a entidades privadas | other | Kept 'other': grants to 15 named entities of several functions |
| ogp_object | 017-E9761 | Transferencia mismo fondo | other | Kept 'other' and transfers: a transfer within one fund; OGP's totals include it, so it stays and is labelled |
| cfda | 11.035 | Broadband Equity, Access, and Deployment Program | utilities_energy | Kept utilities_energy: broadband is communications (COFOG 04.6) |
| cfda | 14.228 | Community Development Block Grants/State's program and Non-Entitlement Grants in Hawaii | housing | Kept housing: CDBG is housing and community development (COFOG 06), its largest use in Puerto Rico |
| cfda | 21.019 | Coronavirus Relief Fund | general_government | Kept general_government: general fiscal relief (COFOG 01.8) |
| cfda | 21.027 |  | general_government | Kept general_government: general fiscal transfers (COFOG 01.8) |
| cfda | 32.003 | UNIVERSAL SERVICE FUND - LIFELINE | utilities_energy | Kept utilities_energy: a phone subsidy, as 32.008 |
| cfda | 32.008 | Affordable Connectivity Program | utilities_energy | Kept utilities_energy: a subsidy is classed by what it buys, here communications (COFOG 04.6) |
| cfda | 66.458 | Clean Water State Revolving Fund | environment_natural_resources | Kept environment_natural_resources: wastewater is environmental protection (COFOG 05.2) |
| cfda | 66.468 | Drinking Water State Revolving Fund | utilities_energy | Kept utilities_energy: water supply (COFOG 06.3) sits with the utilities, as the Aqueduct and Sewer Authority does |
| cfda | 93.600 | Head Start | education | Kept education: Head Start is pre-primary education (COFOG 09.1), whoever runs it |
| cfda | 97.036 | Disaster Grants - Public Assistance (Presidentially Declared Disasters) | other | Kept 'other' in the federal totals: Public Assistance spans every damage category, and its money is counted by category from OpenFEMA (dedup group fema_pa), never added here |
| fema_category | A | Debris removal | environment_natural_resources | Changed to environment_natural_resources: debris removal is waste management (COFOG 05.1) |
| fema_category | E | Public buildings and equipment | general_government | Kept general_government: the category mixes schools, hospitals and city halls; the applicant's own function applies where it is known |
| contralor_group | 1 | Compra, venta y alquiler de equipo, vehículos y otros | (from the entity) | Not used: the Contralor contracts were dropped on 2026-11-04 (lean open data); kept so the codes stay documented |
| contralor_group | 2 | Compra, venta, alquiler y/o desarrollo de inmuebles | (from the entity) | Not used: the Contralor contracts were dropped on 2026-11-04 (lean open data); kept so the codes stay documented |
| contralor_group | 8 | Rescisión de contratos | (from the entity) | Not used: the Contralor contracts were dropped on 2026-11-04 (lean open data); kept so the codes stay documented |
| contralor_group | 16 | Transferencia de fondos | (from the entity) | Not used: the Contralor contracts were dropped on 2026-11-04 (lean open data); kept so the codes stay documented |
| contralor_group | 17 | Acuerdos financieros y no financieros | (from the entity) | Not used: the Contralor contracts were dropped on 2026-11-04 (lean open data); kept so the codes stay documented |
| contralor_group | 23 | Interagenciales | (from the entity) | Not used: the Contralor contracts were dropped on 2026-11-04 (lean open data); kept so the codes stay documented |
