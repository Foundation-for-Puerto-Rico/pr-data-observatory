"""One-off: write dictionary_src/spending_crosswalk.csv (the function crosswalk; the review decisions of 2026-11-09 are in crosswalk_decisions.py) from the OGP code lists and the USAspending listings.
Run: python -I make_crosswalk.py <work dir> <repo>"""
import csv, json, re, sys
from pathlib import Path

W, REPO = Path(sys.argv[1]), Path(sys.argv[2])
ogp = json.loads((W / "ogp_lists.json").read_text(encoding="utf-8"))
K27 = next(k for k in ogp if "27" in k)
K26 = next(k for k in ogp if "26" in k)
cfda = json.loads((W / "cfda.json").read_text(encoding="utf-8"))

ED, HE, PS, TR, HO, PA, EN, EC, UT, SS, DP, GG, OT = ("education", "health", "public_safety", "transportation", "housing", "parks_recreation",
    "environment_natural_resources", "economic_development", "utilities_energy", "social_services", "debt_pensions", "general_government", "other")
rows = []
def row(kind, code, name, fn="", concept="", allocation="", conf="high", flag="", reason="", years=""):
    rows.append({"kind": kind, "code": code, "name": name, "function_category": fn, "concept_of_expense": concept, "allocation": allocation,
                 "confidence": conf, "flag": flag, "reason": reason, "years": years})

# ── OGP concepts (A0xx in FY27, C0xx in FY26: the same numbers) ──
C = {
 "001": ("Nómina y costos relacionados", "payroll", "", ""),
 "002": ("Facilidades y pagos por servicios públicos", "purchased_services", "", "Rent and utility bills (AEE, AAA) of the agency"),
 "003": ("Servicios comprados", "purchased_services", "", ""),
 "004": ("Donativos, subsidios y otras distribuciones", "transfers", "", ""),
 "005": ("Gastos de transportación y subsistencia", "other", "", "Travel; not a purchased service in the brief's sense"),
 "006": ("Servicios profesionales", "purchased_services", "", ""),
 "007": ("Otros gastos", "other", "", ""),
 "008": ("Inversión en mejoras permanentes", "capex", "", ""),
 "009": ("Amortización de la deuda", "debt_service", "override", "Debt service: function debt_pensions and island-wide whatever the agency (brief: allocation rules)"),
 "010": ("Materiales y suministros", "other", "", ""),
 "011": ("Compra de equipo", "capex", "review", "Equipment is capital outlay in OGP's structure, but much of it is small operating equipment; capex keeps it out of apportionment"),
 "012": ("Anuncios y pautas en medios", "purchased_services", "", ""),
 "013": ("Incentivos y subsidios dirigidos al bienestar de la ciudadanía", "transfers", "", "The largest concept: ASES (Vital), PAN, TANF, subsidies"),
 "014": ("Aportaciones a entidades no gubernamentales", "transfers", "", ""),
 "030": ("Plan de pensiones (PayGo)", "transfers", "override", "Pensions: function debt_pensions and island-wide whatever the agency"),
 "081": ("Asignaciones englobadas", "other", "review", "Lump-sum appropriations: the object of expense says what they buy (Vivienda's federal CDBG-DR money is mostly here); concept left 'other' unless the object maps"),
 "082": ("Asignación pareo de fondos federales", "transfers", "review", "State match for federal programs; transfers is a guess"),
 "089": ("Pago de deudas contraídas en años anteriores", "other", "review", "Prior-year bills, not bond debt; not debt_service"),
 "098": ("Reserva presupuestaria", "other", "", "Budget reserve; usually zero"),
}
for code, (name, concept, flag, why) in C.items():
    if code in ("009", "030"):
        row("ogp_concept", code, name, DP, concept, "island_wide", "high", "override", why)
    else:
        row("ogp_concept", code, name, "", concept, "", "high" if not flag else "medium", flag, why)

# ── OGP agencies (three-digit code); function is the default for every program and object of the agency ──
A = {
 "008": (GG, "", ""), "010": (PS, "medium", "Courts: COFOG puts law courts under public order and safety"), "011": (TR, "medium", "Traffic safety commission"),
 "015": (GG, "", ""), "016": (GG, "", "One large program overrides (broadband)"), "017": (GG, "low", "Funds in OGP's custody: government-wide payroll items, federal match, some road paving; see object rows"),
 "018": (GG, "medium", "Planning Board: land-use and economic planning; could be economic_development"), "022": (EC, "medium", "Insurance regulator"),
 "023": (GG, "", ""), "024": (GG, "", "Lottery programs override"), "025": (OT, "low", "Funds in Hacienda's custody ($3.4 B in FY27, one program): the object rows give the function of each line the budget resolutions name; what is left is 'other'"),
 "028": (GG, "", ""), "029": (GG, "", ""), "030": (GG, "", ""), "031": (GG, "", ""), "034": (PS, "medium", "Reviews complaints against police and other officers"),
 "037": (GG, "medium", "Civil rights commission"), "038": (PS, "", ""), "040": (PS, "", ""), "043": (PS, "", ""), "045": (PS, "", "Departamento de Seguridad Pública and its bureaus (police, fire, EMS, 9-1-1, emergency management, investigations) share code 045"),
 "049": (TR, "", ""), "050": (EN, "", "Parks program overrides"), "055": (EC, "", "Agriculture"), "060": (GG, "", ""), "062": (EC, "", ""),
 "067": (EC, "medium", "Labor: unemployment and disability insurance programs override to social_services"), "068": (EC, "", ""), "069": (EC, "", "Consumer affairs"),
 "070": (SS, "medium", "State Insurance Fund (workers' compensation); its medical program could be health"), "071": (HE, "", ""), "075": (EC, "", ""), "078": (HO, "", "Includes CDBG-DR/MIT federal funds"),
 "079": (SS, "medium", "Auto accident compensation"), "081": (ED, "", ""), "082": (PA, "medium", "Culture: the brief has no culture category; COFOG groups recreation and culture"),
 "087": (PA, "", ""), "090": (HE, "", ""), "095": (HE, "", ""), "096": (SS, "", ""), "100": (GG, "", ""), "105": (SS, "medium", "Industrial Commission: workers' compensation appeals"),
 "106": (HO, "", ""), "109": (ED, "", ""), "119": (EC, "", ""), "120": (SS, "", ""), "122": (SS, "", ""), "123": (SS, "", ""), "124": (SS, "", ""), "126": (SS, "", ""),
 "127": (SS, "", "PAN nutrition assistance and TANF"), "137": (PS, "", ""), "138": (PS, "medium", ""), "139": (PS, "", ""), "143": (SS, "", ""), "152": (SS, "", ""), "153": (SS, "", ""),
 "155": (PA, "medium", "Historic preservation: culture"), "161": (EC, "low", "Infrastructure Financing Authority: finances water, roads and other works; function depends on the project"),
 "162": (GG, "low", "Public Buildings Authority: owns and maintains schools and government buildings; much of it is school space"),
 "165": (EC, "", ""), "167": (HO, "medium", "Península de Cantera community development"), "168": (TR, "", "Ports and airports"), "176": (ED, "", ""), "177": (EC, "", ""), "180": (EC, "", "Tourism"),
 "186": (EN, "medium", "Culebra conservation and development"), "187": (HE, "", "ASES: the government health plan (Vital)"), "188": (HE, "", ""), "189": (PS, "", "Forensic sciences"),
 "191": (PA, "medium", "Culture"), "192": (PA, "medium", "Culture"), "193": (GG, "", ""), "195": (EC, "", ""), "196": (PA, "medium", "Public broadcasting: COFOG recreation and culture"),
 "198": (EC, "", ""), "200": (PS, "medium", "Special independent prosecutor"), "209": (GG, "", "Public funding of political parties (Ley 222-2011); FY26 only"),
 "208": (GG, "medium", "Contributions to municipios (Fondo de Equiparación): intergovernmental transfer; direct once split by municipio"),
 "215": (ED, "", ""), "220": (HE, "", ""), "231": (HE, "", ""), "235": (HO, "", ""), "236": (EC, "", ""), "238": (TR, "", ""),
 "241": (SS, "medium", "Child care and Head Start (ACUDEN): could be education"), "264": (HO, "medium", "ENLACE Caño Martín Peña: community and housing development"),
 "265": (EC, "", "Roosevelt Roads redevelopment"), "266": (PS, "", ""), "268": (GG, "", ""), "271": (GG, "", ""), "272": (GG, "", ""),
 "276": (OT, "low", "Public-Private Partnerships Authority (196 M in FY27, one program): energy and other concession contracts; needs object detail"),
 "277": (EC, "", ""), "279": (GG, "", ""), "281": (GG, "", ""), "285": (TR, "", ""), "286": (TR, "", ""), "288": (HE, "", ""), "293": (HE, "", ""),
 "295": (GG, "medium", "AAFAF: fiscal agent and financial adviser"), "297": (GG, "medium", "Financial Oversight and Management Board"), "298": (UT, "", "Energy regulator (Negociado de Energía)"),
 "303": (EC, "", ""), "310": (DP, "low", "Corporación de Financiamiento Municipal (COFIM): municipal debt; 422 M of subsidies in FY27"),
 "311": (OT, "low", "Gaming Commission (492 M in 'supervisión de juegos de azar'): likely distributions of gaming revenue; needs object detail"),
 "312": (DP, "", "Retirement Board"), "329": (SS, "medium", "Socioeconomic and community development office"),
}
ALLOC = {"081": "apportion:school_enrollment", "071": "pending_driver:health_facilities", "187": "pending_driver:health_facilities", "090": "pending_driver:health_facilities",
         "049": "pending_driver:road_km", "050": "pending_driver:protected_area", "087": "no_driver", "025": "island_wide", "017": "island_wide", "016": "island_wide",
         "024": "island_wide", "297": "island_wide", "295": "island_wide", "310": "island_wide", "312": "island_wide", "100": "island_wide", "015": "island_wide"}
code = lambda s: (re.search(r"(\d{3})", str(s)) or [None, None])[1] if s else None
names = {}
for k in (K26, K27):
    for a, _ in ogp[k]["ag"]:
        c = code(a)
        if c and not str(a).startswith(("TOTAL", "Total")):
            names[c] = re.sub(r"^\s*[A-Z]?\d{3}[:\s]\s*", "", str(a)).strip()
missing = sorted(set(names) - set(A))
assert not missing, f"agencies without a function: {[(c, names[c]) for c in missing]}"
for c in sorted(names):
    fn, conf, why = A[c]
    row("ogp_agency", c, names[c], fn, "", ALLOC.get(c, ""), conf or "high", "review" if conf == "low" else "", why)

# ── OGP programs that differ from their agency (agency code + 4-digit program number) ──
P = [
 ("016", "2076", "Programa de Banda Ancha en Puerto Rico", UT, "medium", "review", "Broadband: the brief has no communications category; utilities_energy is the nearest"),
 ("024", "1550", "Administración de la Lotería de Puerto Rico", OT, "medium", "review", "Lottery operations (prizes and sales costs), not a public service"),
 ("024", "1551", "Administración de la Lotería Electrónica", OT, "medium", "review", "Lottery operations (prizes and sales costs), not a public service"),
 ("050", "1159", "Parques de Puerto Rico", PA, "high", "", ""),
 ("067", "1167", "Beneficio de Seguridad por Desempleo", SS, "high", "", "Unemployment benefits"),
 ("067", "1174", "Seguro por Incapacidad No Ocupacional Temporal", SS, "high", "", ""),
 ("067", "1494", "Prog. de Empleo en Servicio Comunitario para Personas de Mayor Edad", SS, "medium", "", ""),
 ("070", "1138", "Servicios Médicos a Trabajadores Lesionados", HE, "medium", "review", "Medical care inside workers' compensation"),
 ("081", "1010", "Servicios de Alimentos al Estudiante", ED, "high", "", "School meals stay in education (they are a school program)"),
 ("045", "1224", "Servicios de Emergencias Médicas", PS, "medium", "review", "Ambulances: COFOG puts them under health; the bureau is part of public safety"),
 ("049", "1312", "Reglamentación de Vehículos de Motor y Servicio al Conductor", TR, "high", "", ""),
 ("049", "1310", "Embellecimiento y Ornato de Áreas Turísticas", EC, "medium", "", "Tourism areas"),
 ("071", "1474", "Programa Especial de Nutrición Suplementaria (WIC)", HE, "medium", "", "WIC is run by Health; nutrition could be social_services"),
 ("071", "1053", "Reglamentación sobre Salud Ambiental", HE, "medium", "", ""),
 ("162", "1586", "Conservación y Mantenimiento de Estructuras Físicas", GG, "low", "review", "Building maintenance, much of it schools"),
]
for a, p, name, fn, conf, flag, why in P:
    row("ogp_program", f"{a}-{p}", name, fn, "", "", conf, flag, why)

# ── OGP objects of expense inside the custodial accounts (agency code + E-code, the object code both data sheets share: "611088-...-E7003" in FY27,
#    "001-E7003: ..." in FY26; "@general" or "@special" for one fund). Hacienda Custodia's objects are matched to the named assignments of the budget
#    resolutions (FY27 Certified Budget Resolution, FY26 Resolución Conjunta 14, the Oversight Board's FY25 certified budget letter): a row that holds
#    only in some years carries those years, and other years fall back to the plain row or the agency ("other"). FY24 uses other object codes.
O = [
 ("025", "E8990", "Pagos relacionados a deuda pública no clasificados", DP, "debt_service", "island_wide", "high", "", "", ""),
 ("025", "E7003", "Pensiones del ERS", DP, "transfers", "island_wide", "high", "", "", ""),
 ("025", "E6390@general", "Aportación al Fideicomiso de la Reserva de Pensiones", DP, "transfers", "island_wide", "high", "",
  "The contribution to the Pension Reserve Trust: $970.3 M in FY25, $970.5 M in FY26 and $1,131.7 M in FY27 in the budget resolutions, the whole of this General Fund line", "2025-2027"),
 ("025", "E6390@special", "Arbitrio al ron y Fondo de Incentivo Económico", EC, "transfers", "island_wide", "medium", "",
  "FY27 resolution: the rum cover-over paid to rum producers ($188.9 M) and the Economic Incentive Fund's share of corporate taxes ($80.9 M)", "2026-2027"),
 ("025", "E6390", "Otras compensaciones no clasificadas", OT, "transfers", "island_wide", "low", "review", "Years and funds not matched to a budget resolution", ""),
 ("025", "E9760@general", "Transferencias a la ACT y a la ATI", TR, "transfers", "island_wide", "high", "",
  "Transfers to the Highways and Transportation Authority (non-toll roads, operations and capital) and cigarette funds to the Integrated Transit Authority: $237.7 M in FY26, $234.5 M in FY27", "2026-2027"),
 ("025", "E9760@special", "Fondo de Incentivo Económico", EC, "transfers", "island_wide", "medium", "", "FY27 resolution: green energy, development and export incentives of the Economic Incentive Fund", "2026-2027"),
 ("025", "E9760", "Transferencia operacional (salida)", OT, "transfers", "island_wide", "low", "review",
  "FY25 mixes the highway and transit transfers (about $230 M) with rum cover-over payments (about $161 M); FY24 uses other codes", ""),
 ("025", "E9761", "Transferencia mismo fondo", OT, "transfers", "island_wide", "low", "review", "FY27: compulsory auto insurance premiums passed to the insurers (Law 253-1995), a pass-through", ""),
 ("025", "E6151", "Fondos de Desarrollo y de Mejoras Municipales", GG, "transfers", "island_wide", "medium", "",
  "Each municipio's Municipal Development and Improvement Funds (Law 107-2020, distributed under Law 1-2011): $101.9 M in FY26; direct once split by municipio", "2025-2027"),
 ("025", "E1290", "Gastos del IVU (servicios profesionales)", GG, "purchased_services", "island_wide", "medium", "", "Sales and use tax (SUT, IVU) collection expenses", ""),
 ("025", "E6170", "Donativos y aportaciones a entidades privadas", OT, "transfers", "island_wide", "low", "review",
  "Grants to legal aid organizations, the Conservation Trust, cultural and other entities (15 named recipients, $45.8 M in FY27): mixed functions", ""),
 ("025", "E2970@special", "Otros gastos operacionales de Hacienda", GG, "other", "island_wide", "medium", "", "Hacienda's other operating and centralized banking expenses ($47.6 M in FY27)", "2025-2027"),
 ("025", "E6890", "Fondo de Incentivo Económico (arbitrio al ron)", EC, "transfers", "island_wide", "medium", "", "Rum cover-over funds in the Economic Incentive Fund and other incentives", "2025-2027"),
 ("025", "E2890", "Seguro de inundación", HO, "purchased_services", "island_wide", "medium", "", "Flood insurance for recipients of federal disaster assistance", "2025-2027"),
 ("017", "E9761", "Transferencia mismo fondo", OT, "transfers", "island_wide", "low", "review", "Transfer within a fund: risk of counting twice", ""),
 ("017", "E9951", "Costos indirectos - fondos federales", GG, "transfers", "island_wide", "medium", "", "Federal match and indirect costs", ""),
 ("017", "E7150", "Construcción de pavimentos y carreteras por contrato", TR, "capex", "", "high", "", "Road paving funded from OGP's custody", ""),
 ("017", "E1490", "Compensación adicional a empleados no clasificada", GG, "payroll", "island_wide", "medium", "", "Government-wide payroll adjustments", ""),
 ("017", "E1410", "Compensación adicional - bono de Navidad", GG, "payroll", "island_wide", "medium", "", "Government-wide Christmas bonus", ""),
 ("017", "E7003", "Pensiones del ERS", DP, "transfers", "island_wide", "high", "", "", ""),
]
for a, o, name, fn, concept, alloc, conf, flag, why, years in O:
    row("ogp_object", f"{a}-{o}", name, fn, concept, alloc, conf, flag, why, years)

# ── Federal programs (assistance listings): agency prefix defaults, then listings ──
PRE = {"10": (EC, "USDA: agriculture and rural development; nutrition listings override"), "11": (EC, "Commerce"), "12": (PS, "Defense"), "14": (HO, "HUD"),
       "15": (EN, "Interior"), "16": (PS, "Justice"), "17": (EC, "Labor: employment and training"), "19": (GG, "State"), "20": (TR, "Transportation"),
       "21": (GG, "Treasury: fiscal relief (CRF, SLFRF) has no single function"), "23": (EC, "Appalachian Regional Commission"), "32": (UT, "FCC: communications"), "39": (GG, "GSA"),
       "43": (ED, "NASA: mostly education and research grants"), "45": (PA, "Arts and humanities: culture"), "47": (ED, "NSF: research and education"),
       "31": (EC, "Export-Import Bank"), "57": (SS, "Railroad Retirement Board"), "59": (EC, "Small Business Administration"), "95": (PS, "Office of National Drug Control Policy (HIDTA)"), "64": (SS, "Veterans Affairs: benefits"), "66": (EN, "EPA"), "77": (UT, "Nuclear Regulatory Commission"),
       "81": (UT, "Energy"), "84": (ED, "Education"), "86": (DP, "Pension Benefit Guaranty"), "89": (GG, "National Archives"), "90": (EC, "Regional commissions"),
       "93": (HE, "HHS: health; human-services listings override"), "94": (SS, "AmeriCorps"), "96": (SS, "Social Security"), "97": (PS, "Homeland Security (FEMA): see listings"),
       "98": (EC, "USAID: international development (a few small awards to Puerto Rico before FY2017)")}
for p, (fn, why) in sorted(PRE.items()):
    row("cfda_agency", p, why.split(":")[0], fn, "", "", "medium", "", "Default for listings of this federal agency not named below (a lookup that falls back to it is low confidence)" + (": " + why.split(": ", 1)[1] if ": " in why else ""))
L = {
 "96.002": SS, "96.001": SS, "96.004": SS, "96.006": SS, "64.109": SS, "64.110": SS, "64.104": SS, "64.105": SS,
 "93.774": HE, "93.773": HE, "93.770": HE, "93.778": HE, "93.767": HE, "93.224": HE,
 "93.558": SS, "93.596": SS, "93.575": SS, "93.569": SS, "93.658": SS, "93.600": (ED, "medium", "review", "Head Start: early childhood education, run in part by social-service agencies"),
 "10.566": SS, "10.557": (SS, "medium", "", "WIC nutrition; Health runs it in PR"), "10.555": (ED, "medium", "", "School lunch: a school program"), "10.553": (ED, "medium", "", "School breakfast"),
 "10.559": (ED, "medium", "", "Summer food service for children"), "10.646": SS, "10.558": SS, "10.760": (UT, "high", "", "Rural water and waste systems"),
 "97.036": (OT, "low", "review", "FEMA Public Assistance: use the FEMA damage category (fema_category rows), not one function"),
 "97.039": (EN, "medium", "", "Hazard mitigation"), "97.048": HO, "97.030": (GG, "medium", "", "Community Disaster Loans to governments"), "97.067": PS,
 "14.228": (HO, "medium", "review", "CDBG (incl. disaster recovery): housing, infrastructure and economic programs; Vivienda's program data split it"),
 "14.218": (HO, "medium", "", "CDBG entitlement"), "14.850": HO, "14.871": HO, "14.872": HO, "14.195": HO,
 "20.205": TR, "20.507": TR, "20.527": TR, "20.106": TR, "20.934": TR, "20.509": TR,
 "81.254": UT, "81.041": UT, "66.959": (UT, "medium", "", "Solar for All"), "66.458": (EN, "medium", "review", "Clean Water SRF: wastewater; could be utilities_energy (PRASA)"),
 "66.468": (UT, "medium", "review", "Drinking Water SRF: water supply (PRASA)"),
 "32.008": (UT, "medium", "review", "Affordable Connectivity Program: a household subsidy for internet; could be social_services"),
 "32.003": (UT, "medium", "review", "Lifeline: a household subsidy for phone service"), "32.004": (ED, "medium", "", "E-Rate: schools and libraries"), "32.002": UT,
 "11.035": (UT, "medium", "review", "BEAD broadband: no communications category"),
 "84.010": ED, "84.027": ED, "84.063": ED, "84.367": ED, "84.287": ED, "84.126": (SS, "medium", "", "Vocational rehabilitation"),
 "17.278": EC, "17.225": SS, "64.028": (ED, "medium", "", "GI Bill education benefits"), "12.401": PS,
 "21.019": (GG, "low", "review", "Coronavirus Relief Fund: general fiscal relief"), "21.027": (GG, "low", "review", "State and Local Fiscal Recovery Funds: general fiscal relief"),
}
listed = {}
for fy, res in cfda.items():
    for r in res:
        listed.setdefault(r["code"], [r["name"], 0.0])[1] += r["amount"]
for k in sorted(L):
    v = L[k]
    fn, conf, flag, why = (v, "high", "", "") if isinstance(v, str) else v
    row("cfda", k, listed.get(k, ["", 0])[0], fn, "", "", conf, flag, why)

# ── FEMA Public Assistance damage categories ──
F = [("A", "Debris removal", GG, "medium", "review", "Debris clearing; COFOG would put waste under environment"),
     ("B", "Emergency protective measures", PS, "high", "", ""), ("C", "Roads and bridges", TR, "high", "", ""),
     ("D", "Water control facilities", EN, "high", "", ""), ("E", "Public buildings and equipment", GG, "low", "review", "Schools, hospitals, city halls together: the project's applicant decides the function"),
     ("F", "Public utilities", UT, "high", "", ""), ("G", "Parks, recreational and other facilities", PA, "medium", "", "'Other' facilities are mixed"),
     ("Z", "Management costs", GG, "high", "", "")]
for c, name, fn, conf, flag, why in F:
    row("fema_category", c, name, fn, "", "", conf, flag, why)

# ── Contralor contract groups (Registro de Contratos, ServiceGroupId) ──
G = [
 ("1", "Compra, venta y alquiler de equipo, vehículos y otros", "", "capex", "medium", "review", "Rentals are operating; purchases are capital"),
 ("2", "Compra, venta, alquiler y/o desarrollo de inmuebles", "", "capex", "medium", "review", "Leases are operating"),
 ("3", "Compra de materiales, suministros y efectos", "", "other", "high", "", ""),
 ("4", "Adquisición de seguros", "", "purchased_services", "high", "", ""),
 ("5", "Construcción y reparación de vías públicas", TR, "capex", "high", "", ""),
 ("6", "Construcción y reparación de estructuras", "", "capex", "high", "", ""),
 ("7", "Préstamos y becas", "", "transfers", "high", "", ""),
 ("8", "Rescisión de contratos", "", "other", "low", "review", "Ends a contract: its amount is not new spending; leave out of totals"),
 ("9", "Servicios educativos, de adiestramiento y de orientaciones", "", "purchased_services", "medium", "", "Mostly staff training; function from the entity"),
 ("10", "Servicios de consultoría", "", "purchased_services", "high", "", ""),
 ("11", "Servicios de publicidad, de representación o artísticos", "", "purchased_services", "high", "", ""),
 ("12", "Servicios misceláneos no personales", "", "purchased_services", "high", "", ""),
 ("13", "Servicios personales no profesionales", "", "purchased_services", "high", "", ""),
 ("14", "Servicios relacionados con la salud", HE, "purchased_services", "high", "", ""),
 ("15", "Servicios técnicos", "", "purchased_services", "high", "", ""),
 ("16", "Transferencia de fondos", "", "transfers", "low", "review", "Often between government entities: risk of counting twice"),
 ("17", "Acuerdos financieros y no financieros", "", "other", "low", "review", ""),
 ("18", "Compra y venta de obras de arte y tesoros históricos", PA, "capex", "medium", "", "Culture"),
 ("19", "Proyectos relacionados a energía renovable y no renovable", UT, "capex", "medium", "", ""),
 ("20", "Servicios profesionales", "", "purchased_services", "high", "", ""),
 ("21", "Servicios relacionados a los sistemas de información", "", "purchased_services", "high", "", ""),
 ("22", "Recogido de desperdicios y reciclaje", EN, "purchased_services", "high", "", ""),
 ("23", "Interagenciales", "", "transfers", "low", "review", "Between agencies: the money is in the paying agency's budget already; leave out of totals"),
]
for c, name, fn, concept, conf, flag, why in G:
    row("contralor_group", c, name, fn, concept, "", conf, flag, why + ("" if fn else ("; " if why else "") + "function from the contracting entity"))

for r in rows:
    if (r["kind"], r["code"]) == ("ogp_program", "050-1159"):
        r["allocation"] = "no_driver"   # parks: no driver in the repository (Phase 0 audit)
sys.path.insert(0, str(Path(__file__).resolve().parent))
import crosswalk_decisions   # noqa: E402  the review of 2026-11-09 (decision 92), applied before the CSV is written
crosswalk_decisions.apply(rows)
out = REPO / "dictionary_src" / "spending_crosswalk.csv"
with open(out, "w", encoding="utf-8", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator="\n")
    w.writeheader()
    w.writerows(rows)
import collections
print(len(rows), "rows", dict(collections.Counter(r["kind"] for r in rows)), "review", sum(r["flag"] == "review" for r in rows))
tot = sum(v for _, v in listed.values()); named = sum(v for k, (_, v) in listed.items() if k in L)
print(f"cfda listings {len(listed)}, named {len(L)} cover {named/tot:.1%} of FY2023-2025 dollars; prefixes cover", sorted({k.split('.')[0] for k in listed} - set(PRE)))
progs = {(code(a), (re.search(r"P(\d{4})", str(p)) or [None, None])[1]) for k in (K26, K27) for a, p, _ in ogp[k]["pg"]}
bad = [r["code"] for r in rows if r["kind"] == "ogp_program" and tuple(r["code"].split("-")) not in progs]
print("program rows not in the data sheets:", bad)
# Evidence for the tests: the code lists the crosswalk must cover (OGP data sheets FY26 and FY27, USAspending FY2023-2025 in PR)
EV = REPO / "docs" / "analysis" / "public-spending-2026-11"
EV.mkdir(parents=True, exist_ok=True)
amt = {}
for k, fy in ((K26, "FY26"), (K27, "FY27")):
    for a, p, v in ogp[k]["pg"]:
        c, pn = code(a), (re.search(r"P(\d{4})", str(p)) or [None, None])[1]
        if c and pn:
            e = amt.setdefault(f"{c}-{pn}", {"name": re.sub(r"^P\d+-", "", str(p)).strip(), "FY26": 0.0, "FY27": 0.0})
            e[fy] += round(v)   # thousands of dollars, approved
codes = {"note": "OGP 'Sábana' data sheets, approved budget, thousands of dollars; FY26 = Aprobado-2025-2026, FY27 = Aprobado-2026-2027; read 2026-11-02",
         "agencies": dict(sorted(names.items())), "programs": dict(sorted(amt.items())),
         "concepts": sorted({(re.match(r"[AC](\d{3})", str(c)) or [None, None])[1] for k in (K26, K27) for c, _ in ogp[k]["cc"]} - {None})}
(EV / "ogp_codes.json").write_text(json.dumps(codes, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
(EV / "cfda_listings.json").write_text(json.dumps({"note": "USAspending spending_by_category/cfda, place of performance Puerto Rico, federal FY2023-2025 summed (dollars); read 2026-11-02",
    "listings": {k: [n, round(v)] for k, (n, v) in sorted(listed.items())}}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
print("evidence written", len(codes["programs"]), "programs", len(listed), "listings", codes["concepts"])

# The review lists: rows still flagged for review (crosswalk_review.md) and the decisions of 2026-11-09 (crosswalk_decisions.md)
left, done = crosswalk_decisions.write_lists(rows)
print("review rows", len(left), "reviewed", len(done))
