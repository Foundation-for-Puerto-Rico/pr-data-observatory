"""Which tourism places are counted but not drawn, and what a published place may carry (owner rule of 2026-10-18).

    python places_privacy.py            mask the withheld places in site/data/places.json, drop the contact fields and the listings that are not tourism
                                        (after a build, or once by hand; then run build.py so that the counts follow)
    python places_privacy.py --check    exit 1 when the published file breaks a rule below (no network, nothing written; the tests and pages.yml run it)
    python places_privacy.py --report   counts by reason, Overture category and rule (no names)

The rule. Private residences, residential buildings, any listing whose name is a street address, house or unit number, care, shelter
and treatment services, and holiday rentals (an entire home or apartment rented for short stays; HANDOFF decision 48, 2026-10-18) are
counted in their municipio but never drawn: their row in places.json keeps only what the counts need (municipio,
barrio, category, type, confidence, flood, protected-area and land-use flags, the distance to the nearest stop) and loses its name, Overture id,
point and the name of its nearest stop. No published place carries a street address, a website, a telephone, an e-mail or a social account ("never publish business
contact details or any personal data"); `has_website` says only whether the listing had a website, for the count the Municipality tab shows.

Overture has no ownership or use field, and its 'lodging' and 'historic_site' categories hold many homes, condominiums, housing estates and
subdivisions that Meta users filed there. So name patterns pick the listings, and the categories decide what a match means:

  - a sensitive word (elderly or children's home, shelter, rehabilitation, addiction treatment, hospice...): withheld in any category;
  - a street address, house, lot or unit number, or a postcode in the name: withheld in any category;
  - a housing word first ("Urb. ...", "Residencial ...", "Parcelas ..."): withheld in any category; a building or estate word (condominio,
    apartments, towers, jardines, estancias, villas de...): withheld in the categories Meta users file homes under (places_review.json:
    categories.ambiguous), unless an accommodation word or a public venue named first goes with it;
  - a home word (Casa, Residencia, House, Home, Hacienda, Villa, Quinta, Finca...): withheld only in the categories Meta users file homes
    under (places_review.json: categories.ambiguous); a restaurant, guest house or museum called "Casa ..." stays;
  - 'lodging' listings must also name an accommodation (hotel, guest house, rental, resort...): the category alone is not evidence of a business;
  - a holiday rental: every listing in a holiday-rental category (places_review.json: categories.holiday_rental: holiday rental homes, cabins,
    cottages, service apartments), and a listing whose name says it is one ("Vacation Rental", "Beach House", "Airbnb", "Short Term Rental",
    "Tiny House"...) in the lodging categories and where homes are filed, unless the name also names a lodging business (hotel, guest house,
    inn, B&B, hostel, posada, parador, resort); and in the hotel, B&B, hostel and campground categories (categories.unit_names) a name that rents a
    unit, a house or a run of units ("... Apartment", "... House", "... Villa", "Condominio ...", "Casa Ejemplo", "Casa Ejemplo Rincón"), with the
    same exception. Hotels, guest houses, inns and B&Bs stay drawn; a holiday rental is usually someone's home.

Not tourism (HANDOFF decision 47, 2026-10-18). Most withheld listings are not tourism supply at all, so they are not counted either: build.py
drops them before any count (not_tourism()). Dropped: 'residential' (subdivisions, condominiums, housing estates, barrios filed as lodging),
'residence' (private homes), 'sensitive' (care homes, shelters, recovery homes) and an 'address' listing filed where homes are filed
(categories.ambiguous: lodging, historic sites, parks, beaches...): a numbered house, flat or lot (one whose name also says holiday rental is
recorded as 'holiday_rental').
A listing that matches 'holiday_rental' and a weaker housing signal (the lodging category naming no accommodation, "... Apartments", "... Condo", a
home word) is recorded as 'holiday_rental' too; 'residential' stays only for clear housing (clear_housing(): a subdivision or estate word, a named
condominium or apartment building, a neighborhood of the gazetteer within 3 km). Review of PR #62. Kept, counted and not drawn: 'holiday_rental' (decision 48: tourism supply), and an 'address' listing filed as a hotel, B&B, holiday rental,
cabin or campground (a numbered unit rented to visitors) or as a business (a restaurant or bar named by its address).

places_review.json is the reviewed list: listings drawn although their name matches ('public', each with a reason and its name, which is a
public place's name) and listings withheld although no pattern matches ('withheld', by Overture id only, never by name). A listing in neither
list is decided by the patterns, so an unreviewed match is withheld, not drawn. tests/test_places_privacy.py fails if a drawn place matches
a pattern without a review. Guide: docs/places-privacy.md.
"""
import argparse
import json
import math
import re
import sys
import unicodedata
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "site" / "data"
REVIEW = ROOT / "places_review.json"

REASONS = ("sensitive", "address", "residential", "residence", "holiday_rental")   # in the order they are tested; the first that applies is recorded

# Fields a published place may never carry (contact details and data used only while building).
CONTACT_FIELDS = {"address", "website", "phone", "email", "socials", "postcode", "brand", "source_license"}
# What a withheld place loses besides the contact fields: its name, its Overture id (which leads to the name), its point, the name of its nearest
# stop and the date its listing was updated (which, with the rest, could single the row out). It keeps the fields every count and filter reads
# (municipio, barrio, category, type, confidence, flood, protected area, land use, transit distance), so the Municipality tab, the barrio counts and
# the nightly access refresh (access.py) still add up. Its confidence is cut down to the map slider's step (CONF_STEP), so every count the slider
# gives is unchanged.
MASKED_DROP = {"name", "oid", "lat", "lng", "nearest_stop", "updated"}
CONF_STEP = 0.05


def conf_step(c):
    """A confidence cut down to the slider's 0.05 step (0.57 -> 0.55; 0.55 stays). Every threshold the pages and access.py use is a multiple of the step."""
    return round(math.floor((c or 0) / CONF_STEP + 1e-6) * CONF_STEP, 2)


# Distances and departures of a withheld place, coarsened to one value per class (HANDOFF decision 49, 2026-10-18): the meter-exact distance to a stop
# singled almost every withheld row out. Each value keeps the side of every threshold a reader uses, so every count and share is unchanged:
#   transit_m (places.json; any mapped stop, cut to whole meters): transit_400m says <= 400 m (access._carry), the map's class rule reads < 800
#             (access.js accessClass) and the nightly refresh <= 800 (access.flags any800): 400 / 700 / 800 (exactly 800) / 1000 (more than 800)
#   ts_m (place_access.json; current stop, straight line, rounded up): <= 400 and <= 800 (cur400, cur800, accessClass), and the walk bound for the
#             places walked in a straight line (tw_straight, where tw_m is ts_m): 400 / 800 / 1000 / the cap (99,999, beyond the bound)
#   tw_m (the same on foot): <= 400, <= 800 and the walk bound (1,000 m; accessClass, walk400, walk800): 400 / 800 / 1000 / the cap; never below ts_m
#   ts_calls, tw_calls (weekday departures): >= 20 (frequent) and > 0: 0 / 1 / 20. ts_we and tw_we (weekend service flags) are kept.
TRANSIT_CLASSES = (400, 700, 800, 1000)
DISTANCE_CLASSES = (400, 800, 1000)
CALL_CLASSES = (0, 1, 20)


def coarse_transit(m, near400):
    """transit_m of a withheld place: 400 when the exact distance was within 400 m, 700 below 800, 800 at 800 (cut), 1000 beyond."""
    if m is None:
        return None
    return 400 if near400 else 700 if m < 800 else 800 if m == 800 else 1000


def coarse_distance(m, cap=99999, bound=1000):
    """ts_m or tw_m of a withheld place: 400, 800 or 1000 (within 400 m, 800 m, the walk bound), the cap when beyond the bound."""
    return 400 if m <= 400 else 800 if m <= 800 else bound if m <= bound else cap


def coarse_calls(n):
    return 0 if not n else 1 if n < 20 else 20


def coarsen_columns(doc, places):
    """Coarsen the place_access.json columns of the withheld places in place (see TRANSIT_CLASSES); returns doc. A walk stays at least the straight
    line, and a place with no walkable road (tw_straight) keeps its walk equal to its straight line."""
    cap, bound = doc.get("cap_m", 99999), doc.get("walk_bound_m", 1000)
    straight = set(doc.get("tw_straight", []))
    for i, p in enumerate(places):
        if not p.get("withheld"):
            continue
        doc["ts_m"][i] = coarse_distance(doc["ts_m"][i], cap, bound)
        doc["ts_calls"][i] = coarse_calls(doc["ts_calls"][i])
        if "tw_m" in doc:
            if i in straight:   # no walkable road near the place: the walk is the straight line (access.walking)
                doc["tw_m"][i], doc["tw_calls"][i] = doc["ts_m"][i], doc["ts_calls"][i]
            else:
                doc["tw_m"][i] = coarse_distance(doc["tw_m"][i], cap, bound)
                doc["tw_calls"][i] = coarse_calls(doc["tw_calls"][i])
    return doc


def _canonical(row):
    return json.dumps(row, sort_keys=True, ensure_ascii=False)


def publish_order(rows):
    """The order to publish the rows in: the drawn places as built (Overture's order, which follows location), then the withheld places sorted by
    their own published fields. In Overture's order a withheld row sat between drawn rows a few hundred meters from it, so its position gave its
    place away (decision 49). rows: the published rows (public_row). Returns the permutation (new position -> old index)."""
    drawn = [i for i, r in enumerate(rows) if not r.get("withheld")]
    return drawn + sorted((i for i, r in enumerate(rows) if r.get("withheld")), key=lambda i: _canonical(rows[i]))


def permute_columns(doc, perm):
    """place_access.json in the order publish_order gives (its columns follow places.json row by row; tw_straight lists row numbers). perm lists old
    row numbers: a permutation, or a selection when rows are dropped (decision 47: the listings that are not tourism)."""
    n = doc.get("n", len(perm))
    for k, v in list(doc.items()):
        if isinstance(v, list) and len(v) == n and k != "tw_straight":
            doc[k] = [v[i] for i in perm]
    if "n" in doc:
        doc["n"] = len(perm)
    if "tw_straight" in doc:
        new = {old: pos for pos, old in enumerate(perm)}
        doc["tw_straight"] = sorted(new[i] for i in doc["tw_straight"] if i in new)
    return doc


def order_problems(places):
    """A withheld row before a drawn one, or withheld rows out of publish_order."""
    w = [i for i, p in enumerate(places) if p.get("withheld")]
    out = []
    if w and w[0] != len(places) - len(w):
        out.append(f"rows: a withheld place comes before a drawn one (row {w[0]}); withheld rows go last (publish_order)")
    keys = [_canonical(places[i]) for i in w]
    if keys != sorted(keys):
        out.append("rows: the withheld places are not in publish_order")
    return out


def column_problems(doc, places):
    """What breaks the coarsening in place_access.json (row numbers only)."""
    out = []
    cap = doc.get("cap_m", 99999)
    for i, p in enumerate(places):
        if not p.get("withheld"):
            continue
        if doc["ts_m"][i] not in DISTANCE_CLASSES + (cap,) or doc["ts_calls"][i] not in CALL_CLASSES:
            out.append(f"row {i}: withheld place's ts_m or ts_calls is not coarsened")
        if "tw_m" in doc and (doc["tw_m"][i] not in DISTANCE_CLASSES + (cap,) or doc["tw_calls"][i] not in CALL_CLASSES or doc["tw_m"][i] < doc["ts_m"][i]):
            out.append(f"row {i}: withheld place's tw_m or tw_calls is not coarsened")
    return out


def norm(s):
    """Lower case, accents and punctuation off, one space between words."""
    s = "".join(c for c in unicodedata.normalize("NFD", s or "") if unicodedata.category(c) != "Mn").lower()
    return " ".join(re.sub(r"[^a-z0-9#&/ ]+", " ", s).split())


def _rx(words):
    return re.compile(r"\b(" + "|".join(words) + r")\b")


# Care, shelter and treatment services (the observatory publishes those as counts only: community_series.json, SAMHSA).
SENSITIVE = _rx([
    r"hogar(es)? (de |del |para )?(ancianos?|envejecientes?|ninos?|ninas?|nino|nina|menores|jovenes|mujeres|madres|ancianas)", r"hogar crea", r"crea inc",
    r"hogar (de )?(sustituto|temporero|transitorio|seguro|grupal|de cuido)", r"casa protegida", r"casa de (la )?mujer", r"casa cuna", r"orfanato", r"huerfanos?",
    r"albergue(?! olimpico)", r"shelter(?! marine)", r"refugio (para |de )(mujeres|ninos|victimas|animales sin hogar|deambulantes)",
    r"rehab", r"rehabilitacion", r"centro de rehabilitacion", r"rehabilitation", r"adiccion(es)?", r"addiction", r"drogas?", r"drug", r"alcoholicos", r"alcoholics",
    r"narcoticos", r"narcotics", r"teen challenge", r"desafio juvenil", r"reto juvenil", r"metadona", r"methadone", r"detox(?! pr)", r"desintoxicacion", r"recovery", r"recuperacion",
    r"salud mental", r"mental health", r"psiquiatric[oa]s?", r"psychiatric", r"crisis center", r"linea de crisis", r"violencia domestica", r"domestic violence", r"victimas?", r"victims?",
    r"deambulantes?", r"homeless", r"sin techo", r"hospicio", r"hospice", r"envejecientes?", r"ancianos?", r"elderly care", r"assisted living", r"senior living", r"home care",
    r"nursing home", r"egida", r"vih", r"hiv", r"ex confinados?", r"confinados?", r"transitional", r"casa de transicion", r"hogar de transicion", r"reinsercion",
    r"assisted care", r"edad dorada", r"golden living", r"cuido de (ancianos|envejecientes|personas mayores)", r"adult day care",
    # care, foster and recovery homes named as such (final review of PR #60, 2026-10-18)
    r"institucion hogar", r"casa hogar", r"colegio hogar", r"hogar (de )?(restauracion|crianza|sustituto|substituto|convalecencia|geriatrico)",
    r"geriatric[oa]s?", r"geriatric", r"group homes?", r"foster (homes?|care)", r"halfway house", r"sober living", r"safe house", r"orphanages?",
    r"residential treatment", r"centro de tratamiento",   # not a bare "convalecencia": a plaza and a church carry the name
])
# A licensed care home is usually filed as "Hogar <name>, Inc." under a hotel or B&B category: a name that starts with "Hogar" (or "Institución Hogar")
# is a care home in the lodging, rental and unit categories.
CARE_HOME_FIRST = re.compile(r"^(institucion )?hogar\b")
# A street address, house, lot or unit number: "A1 Calle 99", "Calle Ficticia K7", "Apt. 208", "Edificio 11". ADDRESS applies in any category;
# ADDRESS_LOOSE (a postcode, "#27", a lot code after an estate word, a bare number) only where homes and rented units are filed, because
# businesses number their branches and kiosks ("Pizza #2", "Kiosko #8", "Agencia Hípica #917") and some add their postcode to their name.
ADDRESS = [
    re.compile(r"^#?\d+[a-z]?(-\d+)? (calle|c|cll|ave|avenida|av|carr|carretera|camino|paseo|street|st|road|rd|avenue|blvd)\b"),   # 123 Calle ...
    re.compile(r"\b(calle|c/|cll|street|st)\b [a-z ]{2,30}\b(#|num|no)? ?\d{1,4}[a-z]?\b(?! de )"),               # Calle Ficticia 123, but not Calle 25 de Enero
    re.compile(r"\b(apt|apto|apartamento|apartment|piso|suite|ste|edif|edificio|bloque|blq|unit|unidad|floor|torre|tower|building|bldg)\b ?#? ?[a-z]?\d{1,4}\b"),   # Apt. 208, Edificio 11, Torre 2
    re.compile(r"\b(urb|urbanizacion|urbanization|res|residencial|reparto|barriada|bda|parcelas|ext|extension|cond|condominio)\b.*\b[a-z]{1,2} ?-?\d{1,4}\b"),   # Urb. Ejemplo C35
]
ADDRESS_LOOSE = [
    re.compile(r"\b00[6-9]\d\d\b"),                                                                              # a Puerto Rico postcode
    re.compile(r"#\s?\d"),                                                                                       # #461
    re.compile(r"^\d+[a-z]?$|^[a-z]{1,2}-?\d{1,4}$"),                                                            # a bare number: 901, K10
    re.compile(r"\b(?!(?:pr|sk|mp|fm|am|pm|no|nm|tv|dj|mr|ms|dr|st|nd|rd|th|km|el|la|lo|de|en|y|b) ?\d)[a-z]{1,2} ?-?\d{1,3}[a-z]?\b"),   # a lot code: R-13, cc06, C9, M 209 (not PR15, SK8, La 15)
    re.compile(r"\b(?!(?:carretera|carr|ruta|route|highway|road|pr|no|num|numero|bridge|puente|km|edicion|festival|piso|floor|construccion)\b)[a-z]{3,} "
               r"(?!787\b|939\b|(?:18|19|20)\d\d\b)\d{3,4}[a-z]?\b"),   # a street and house number: Ficticia 1571, Ejemplo 109C (not a road, a year or an area code)
]
LEADING_NUMBER = re.compile(r"^\d{1,4}[a-z]? (?!de\b)[a-z]")   # "60 Ficticia", "511 Calle Ficticia...": a house number first (not "3 Ejemplos Vacation Rentals")
# Residential buildings, complexes, housing estates and subdivisions. STRONG words name housing in any category when they come first ("Urb. ...",
# "Residencial ...", "Parcelas ..."); BUILDING and ESTATE words name housing only where Meta users file homes (a hotel called "... Apartments" or
# "... Gardens" is a business). A public venue named before an estate word names the venue ("Parque de Pelota, Urb. Ejemplo"); a building word
# is a building wherever it stands ("Ejemplo Park Apartments").
STRONG = _rx([
    r"urb", r"urba", r"urbanizacion", r"urbanization", r"residencial", r"recidencial", r"^res", r"reparto", r"barriada", r"bda", r"parcelas", r"parc",
    r"cooperativa de viviendas?", r"coop viviendas?", r"coop de viviendas?", r"housing", r"elderly", r"multifamiliar", r"condominio privado", r"consejo de titulares",
    r"asociacion de residentes", r"residentes",
])
BUILDING = _rx([
    r"condominios?", r"condominiums?", r"condos?", r"cond", r"apartments?", r"apartamentos?", r"apartaments?", r"aparments?", r"apts?", r"aptos?", r"court", r"courts",
    r"walk ups?", r"townhouses?", r"townhomes?", r"lofts?", r"mansions", r"residences", r"row houses",
])
# A building word that names any building ("Edificio Ejemplo", "Ejemplo Building"): housing only in the
# lodging category, where the listing names no accommodation anyway; in a monument, historic site, park or other public category it is not evidence of
# housing (review of PR #62). "Court" names a housing complex unless a public venue is named first ("Supreme Court ...").
BUILDING_WEAK = _rx([r"edificio", r"edif", r"edf", r"building", r"bldg"])
# What still says housing when a name also says holiday rental (reason()): a subdivision, urbanización, residencial, housing estate, a condominium or
# apartment building named as such ("Condominio Ejemplo", "Edificio Ejemplo", "Torres de Ejemplo"), or a neighborhood, sector or barrio name from the
# gazetteer ("Villa Ejemplo" when Villa Ejemplo is a neighborhood). A weaker housing signal (the lodging category naming no accommodation, "... Apartments",
# "... Condo", a home word) gives way to the holiday rental: it is counted, not drawn (decision 48).
CLEAR_HOUSING = _rx([r"condominios?", r"condominiums?", r"cond", r"edificio", r"edif", r"edf", r"torres?", r"multifamiliar", r"walk ups?", r"row houses"])
ESTATE = _rx([
    r"estancias", r"jardines", r"chalets", r"mansiones", r"quintas", r"haciendas", r"alturas", r"colinas", r"lomas", r"praderas", r"portales", r"balcones",
    r"villas", r"villas? del?", r"villa del? rey", r"levittown", r"heights", r"estates?", r"gardens", r"comunidad", r"vista real", r"ciudad jardin", r"terrazas",
    r"paseos", r"porticos", r"veredas", r"palacios", r"village", r"torres? de", r"towers?",
])
# A private home, or a place named after the person who lives there ("Jane Doe's Place", "J. Doe Host").
HOME = _rx([
    r"casa", r"casita", r"casona", r"residencia", r"residence", r"home", r"house", r"houses", r"hogar", r"mansion", r"manor", r"chalet", r"quinta", r"hacienda",
    r"finca", r"estancia", r"villa", r"familia", r"family", r"mi casa", r"mi ranchito", r"rancho", r"ranchito", r"cabana", r"cottage", r"bungalow", r"vivienda",
    r"host", r"[a-z]+ s (place|spot|corner|paradise|hideaway)", r"terrenos?", r"solar", r"se vende", r"for sale",
])
# An accommodation business: what a 'lodging' listing must name to be drawn, and what makes "Casa ..." in an ambiguous category a business.
ACCOMMODATION = _rx([
    r"hotel", r"hoteles", r"motel", r"inn", r"guest ?houses?", r"guesthouse", r"hostel", r"hostal", r"resort", r"resorts", r"suites?", r"rentals?", r"alquiler(es)?",
    r"airbnb", r"bnb", r"b&b", r"bed (and|&) breakfast", r"vacation", r"vacacional(es)?", r"vacaciones", r"retreat", r"glamping", r"camping", r"campground", r"campers?",
    r"campamento", r"cabanas?", r"cabins?", r"lodge", r"posada", r"parador", r"hospedaje", r"beach ?house", r"tree ?house", r"tiny house", r"getaways?", r"stays?",
    r"short term", r"str", r"bungalows?", r"cottages?", r"agroturismo", r"ecolodge", r"for rent", r"para alquiler", r"rent",
])
# A holiday rental named as such (HANDOFF decision 48): an entire home or apartment rented for short stays. HOLIDAY names one in the lodging categories
# and where homes are filed ("Ejemplo Beach House" filed as a beach or a historic site); HOLIDAY_LOOSE ("... Rentals", "... Stays", "... Getaway") only in
# the lodging categories, because elsewhere it names a kayak, boat or car rental. LODGING_BUSINESS keeps a hotel, guest house, inn or B&B drawn.
HOLIDAY = _rx([
    r"vacation(al)? (rentals?|homes?|houses?|villas?|apartments?|condos?|studios?)", r"vacation condo rentals?", r"holiday (homes?|rentals?)",
    r"casa de vacacionar", r"residencias? para vacacionar", r"(casas?|apartamentos?|apto|villas?|residencias?) vacacional(es)?", r"vrbo", r"short (term )?rentals?", r"str",
    r"[a-z]*(airbnb|beachhouse|vacationrental|apartmentrental)[a-z]*",   # also run together: "Ejemploairbnb", "...BeachHouseLLC"
    r"daily rentals?", r"rental (apartments?|homes?|condos?|studios?)", r"beach ?house", r"beach cottage", r"tree ?house", r"tiny house", r"pool rentals?",
    r"para alquiler", r"alquiler (de )?(piscina|casa|apto|apartamento|villa)s?", r"lake ?house", r"river ?house",
])
HOLIDAY_LOOSE = _rx([r"rentals?", r"alquiler(es)?", r"stays?", r"getaways?"])
LODGING_BUSINESS = _rx([
    r"hotel", r"hoteles", r"motel", r"inn", r"guest ?houses?", r"guesthouse", r"hostel", r"hostal", r"b&b", r"bnb", r"bed (and|&) breakfast", r"posada",
    r"parador", r"hospedaje", r"resorts?",
])
# A holiday rental filed as a hotel, B&B, hostel or campground (places_review.json: categories.unit_names), named by what it rents: one unit ("Ejemplo
# Beach Apartment", "Casita Ejemplo", "Penthouse Ejemplo", "Villa 12"), a run of units ("Ejemplo Apartments": real aparthotels and rental offices are
# reviewed as public), or a house called "Casa" or "Villa" and one word ("Casa Ejemplo", "Villa de Doe", "Casa Jane Doe's"): withheld unless the
# name also names a lodging business (LODGING_BUSINESS). A real guest house called "Casa ..." is drawn by review.
UNIT = _rx([
    r"apartment", r"apartament", r"apartamento", r"apto", r"condo", r"condo unit", r"condominium unit", r"condominio unit", r"studio", r"estudio", r"loft",
    r"penthouse", r"casita", r"bungalow", r"cabana", r"cabin", r"chalet", r"cottage", r"villa \d{1,4}[a-z]?", r"house", r"home", r"villa( pr| puerto rico)?$",   # "Ejemplo Beach Home", "Ejemplo View Villa"
])
UNITS = _rx([r"apartments", r"apartamentos", r"apartaments", r"aparments", r"apts", r"aptos", r"condos", r"condominiums", r"condominio", r"condominium",
             r"studios", r"lofts"])
# "Casa Ejemplo", "Villa de Doe", and the same followed by a town, barrio or municipio ("Casa Ejemplo Rincón", "Casa Doe, Culebra PR"; PLACE_NAMES).
HOUSE_ONE_WORD = re.compile(r"^(casa|villa)( (?:de|del|la|las|los|el|di|da))? ([a-z0-9]+)( s)?(?: (.+))?$")   # matched without a final "PR"
GAZETTEER = DATA / "gazetteer.json"
_places = None


def place_names():
    """Normalized names of the municipios, towns, villages, barrios and neighborhoods (sectors, urbanizaciones) in site/data/gazetteer.json, for
    HOUSE_ONE_WORD."""
    global _places
    if _places is None:
        try:
            g = json.loads(GAZETTEER.read_text(encoding="utf-8"))
            keep = {k for k, name in enumerate(g["kinds"]) if name in ("municipio", "town", "village", "barrio", "neighborhood")}
            _places = {norm(it[0]) for it in g["items"] if it[3] in keep} - {""}
        except (OSError, ValueError, KeyError, IndexError):
            _places = set()
    return _places


def house_one_word(n):
    """n (normalized) is a house called Casa or Villa and one word, optionally followed by a town, barrio or municipio."""
    m = HOUSE_ONE_WORD.match(re.sub(r" (pr|puerto rico)$", "", n))
    return bool(m) and (m.group(5) is None or m.group(5) in place_names())
# A home word followed by a unit or house number ("Casa Ejemplo 28", "Cluster 2 - 39B"): an address in any category. Not a year, and not when the name
# also names a public venue, a lodging business or a food or drink business ("La Casita del Ejemplo 2", a branch number); outside the categories
# where homes are filed or rented a one-digit number is a branch number, so it must have two digits or a letter.
HOME_NUMBER = re.compile(r"\b(casa|casita|villa|residencia|home|house|apartment|apartamento|apto|condo|cluster|unit|unidad|penthouse|bungalow|cabana|chalet|quinta)\b"
                         r"(?: (?!(?:de|del|la|las|los|el|y|and)\b)[a-z]+){0,2} ?#? ?-? ?(?!(?:18|19|20)\d\d\b)(\d{1,4})([a-z]?)\b")
SHOP = _rx([
    r"restaurant", r"restaurante", r"bar", r"grill", r"cafe", r"cafeteria", r"coffee", r"pinchos", r"panaderia", r"bakery", r"reposteria", r"pizza",
    r"pizzeria", r"burgers?", r"club", r"lounge", r"pub", r"colmado", r"chinchorro", r"kiosko", r"food", r"deli", r"sabor", r"cocina", r"kitchen", r"bistro",
    r"tienda", r"shop", r"store", r"iasd", r"suites",
])
# A public venue: what makes "Parque de Villa Ejemplo", "Playa Villa Ficticia" or "Antigua Casa Alcaldía" in an ambiguous category a public place.
# (Beach, river and forest words count only at the start of the name: "Villa Ejemplo Playa Ficticia" is a house at a beach.)
PUBLIC_VENUE = _rx([
    r"parque", r"park", r"plaza", r"cancha", r"pista", r"centro deportivo", r"complejo deportivo", r"estadio", r"reserva", r"reserve", r"museo", r"museum",
    r"biblioteca", r"library", r"alcaldia", r"city hall", r"mausoleo", r"customs house", r"aduana", r"villa pesquera", r"fundacion", r"escuela", r"iglesia",
    r"capilla", r"parroquia", r"templo", r"ministerio", r"congregacion", r"tabernaculo", r"iddpmi", r"idpmi", r"centro comunal", r"centro cristiano",
    r"supreme court", r"tribunal", r"observaciones", r"observation", r"lookout", r"mirador", r"trail", r"sendero", r"^playa", r"^beach", r"^balneario", r"^rio", r"^lago", r"^cerro",
])
NATURAL = {"playa", "beach", "balneario", "rio", "lago", "cerro"}   # the PUBLIC_VENUE words that count only at the start of a name


def load_review(path=REVIEW):
    rv = json.loads(Path(path).read_text(encoding="utf-8"))
    both = set(rv["public"]) & set(rv["withheld"])
    if both:
        raise SystemExit(f"places_privacy: {Path(path).name} lists {sorted(both)} as both public and withheld")
    bad = {k: v for k, v in rv["withheld"].items() if v not in REASONS}
    if bad:
        raise SystemExit(f"places_privacy: unknown reason in {Path(path).name}: {bad}")
    return rv


def matches(name, category, rv):
    """The rules the name and Overture category trigger, in REASONS order (before the reviewed list is consulted)."""
    n = norm(name)
    cats = rv["categories"]
    hits = []
    if (category in cats["sensitive"] or SENSITIVE.search(n)
            or (CARE_HOME_FIRST.search(n) and category in set(cats["lodging_names"]) | set(cats["rental"]) | set(cats["unit_names"]))):
        hits.append("sensitive")
    amb, rent = category in cats["ambiguous"], category in cats["rental"]
    business = bool(ACCOMMODATION.search(n))   # "Casa Ejemplo Short Rentals", "Villa Ejemplo Guest House": a home word beside a business word names a business
    venue = PUBLIC_VENUE.search(n) if category != "lodging" else None   # "Parque de Villa Ejemplo", "Iglesia ... Parcelas Ficticias": a public venue
    first = lambda m: venue is not None and venue.start() < m.start()   # noqa: E731  (the venue is named before the housing word)
    if (any(rx.search(n) for rx in ADDRESS)
            or ((amb or rent) and any(rx.search(n) for rx in ADDRESS_LOOSE)) or (amb and LEADING_NUMBER.search(n) and not (business or venue))
            or home_number(n, amb or rent or category in cats["lodging_names"])):
        hits.append("address")
    strong, estate = STRONG.search(n), ESTATE.search(n)
    building = BUILDING.search(n) or (BUILDING_WEAK.search(n) if category == "lodging" else None)
    court = building is not None and building.group(0) in ("court", "courts") and first(building)   # "Supreme Court ...": the venue is named first
    if ((category in cats["residential"] and not business)
            or (strong and (strong.start() == 0 or ((amb or rent) and not first(strong))))
            or (amb and not business and ((building and not court) or (estate and not first(estate))))
            or (category == "lodging" and not business)):
        hits.append("residential")
    if (HOME.search(n) and amb and not (business or venue)) or category in cats["home_business"]:
        hits.append("residence")
    lodging = category in cats["lodging_names"]
    if (category in cats["holiday_rental"]
            or ((amb or rent or lodging) and (HOLIDAY.search(n) or (lodging and HOLIDAY_LOOSE.search(n))) and not LODGING_BUSINESS.search(n))
            or (category in cats["unit_names"] and (UNIT.search(n) or UNITS.search(n) or house_one_word(n)) and not LODGING_BUSINESS.search(n))):
        hits.append("holiday_rental")
    return hits


def home_number(n, homes_filed):
    """A home word followed by a unit or house number (HOME_NUMBER) in the normalized name n; homes_filed: a category where homes are filed or rented."""
    if any(m.group(1) not in NATURAL for m in PUBLIC_VENUE.finditer(n)) or LODGING_BUSINESS.search(n) or SHOP.search(n):
        return False   # a beach or river word does not make a public venue here ("Rio Ejemplo Cluster 2 - 39B")
    return any(homes_filed or len(m.group(2)) > 1 or m.group(3) for m in HOME_NUMBER.finditer(n))


def reason(p, rv):
    """None (drawn) or why the place is counted but not drawn."""
    oid = p.get("oid")
    if oid in rv["withheld"]:
        return rv["withheld"][oid]
    if oid in rv["public"]:
        return None
    name, category = p.get("name") or "", p.get("overture_category")
    hits = matches(name, category, rv)
    if hits[:1] == ["address"] and "holiday_rental" in hits and category in rv["categories"]["ambiguous"]:
        return "holiday_rental"   # a holiday rental named by its unit number, filed where homes are filed: tourism supply (not_tourism())
    if hits[:1] in (["residential"], ["residence"]) and "holiday_rental" in hits and not clear_housing(name, category, rv, p.get("lat"), p.get("lng")):
        return "holiday_rental"   # a holiday rental whose only housing signal is weak (review of PR #62): tourism supply, counted, not drawn
    return hits[0] if hits else None


_hoods = None


def neighbourhood_name(n, lat=None, lng=None):
    """n (normalized) starts with the name (two words or more) of a neighborhood, sector, urbanización, barrio, village, town or municipio of the
    gazetteer that lies within 3 km of the place ("Villa Ejemplo" is a subdivision only where a Villa Ejemplo is mapped nearby); anywhere when the place
    has no point."""
    global _hoods
    if _hoods is None:
        _hoods = {}
        try:
            g = json.loads(GAZETTEER.read_text(encoding="utf-8"))
            keep = {k for k, name in enumerate(g["kinds"]) if name in ("municipio", "town", "village", "barrio", "neighborhood")}
            for it in g["items"]:
                if it[3] in keep and norm(it[0]):
                    _hoods.setdefault(norm(it[0]), []).append((it[1], it[2]))
        except (OSError, ValueError, KeyError, IndexError):
            pass
    w = n.split()
    for k in range(2, min(len(w), 5) + 1):
        pts = _hoods.get(" ".join(w[:k]))
        if pts and (lat is None or lng is None or any(math.hypot((a - lat) * 111.32, (b - lng) * 111.32 * math.cos(math.radians(lat))) <= 3 for a, b in pts)):
            return True
    return False


def clear_housing(name, category, rv, lat=None, lng=None):
    """The name says housing clearly (CLEAR_HOUSING): a subdivision or estate word, a condominium or apartment building named as such, or a
    neighborhood from the gazetteer; or the category is residential."""
    n = norm(name)
    estate = ESTATE.search(n)
    if estate and re.fullmatch(r"villa del?", estate.group(0)):
        estate = None   # "Villa de Ejemplo" alone is a house name; it is a subdivision when the gazetteer maps it nearby (neighbourhood_name)
    return bool(category in rv["categories"]["residential"] or STRONG.search(n) or estate or CLEAR_HOUSING.search(n) or neighbourhood_name(n, lat, lng))


# Withheld for a reason that says the listing is not tourism supply (decision 47): not counted either, and not published (build.py drops it).
NOT_TOURISM = ("sensitive", "residential", "residence")


def not_tourism(p, rv=None):
    """True when the place (with its 'withheld' reason from classify()) is not tourism supply and is left out of every count (decision 47): a home,
    housing, a care service, or a listing named by a street address or unit number in a category where homes are filed (categories.ambiguous: a
    numbered house, flat or lot; reason() records a numbered holiday rental there as 'holiday_rental'). A holiday rental, and an address-named unit
    filed as a hotel, B&B, rental, cabin or campground or as a business (a restaurant named by its address), stay counted."""
    r = p.get("withheld")
    if r in NOT_TOURISM:
        return True
    return r == "address" and p.get("overture_category") in (rv or load_review())["categories"]["ambiguous"]


def classify(places, rv=None):
    """Set p['withheld'] (a reason or None) on every place; return the counts by reason."""
    rv = rv or load_review()
    for p in places:
        p["withheld"] = reason(p, rv)
    return Counter(p["withheld"] for p in places if p["withheld"])


PHONE = re.compile(r"[\s,;:(-]*(?:\+?1[ .-]?)?\(?\b\d{3}\)?[ .-]?\d{3}[ .-]?\d{4}\b\)?")
EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")


def scrub_name(name):
    """The name without a telephone number or an e-mail address in it (a few listings append their number to the name); any other name as written."""
    if not name or not (PHONE.search(name) or EMAIL.search(name)):
        return name or None
    return EMAIL.sub("", PHONE.sub("", name)).strip(" ,;:-") or None


def public_row(p):
    """The published row: contact fields dropped, the name scrubbed, and a withheld place reduced to what the counts need."""
    drop = CONTACT_FIELDS | (MASKED_DROP if p.get("withheld") else {"withheld", "hub_400m"})
    row = {k: v for k, v in p.items() if k not in drop and k != "region"}
    row["has_website"] = bool(p.get("website") or p.get("has_website"))
    if not p.get("withheld"):
        row["name"] = scrub_name(p.get("name"))
    else:
        if "confidence" in row:
            row["confidence"] = conf_step(row["confidence"])
        if row.get("transit_m") is not None:
            row["transit_m"] = coarse_transit(row["transit_m"], bool(row.get("transit_400m")))
    return {k: v for k, v in row.items() if v is not None and v is not False and v != "" and v != []}


def problems(places, rv):
    """What breaks the rule in a published places.json (a list of strings; names of withheld places are never printed)."""
    out = []
    for i, p in enumerate(places):
        bad = sorted(set(p) & CONTACT_FIELDS)
        if bad:
            out.append(f"row {i}: publishes {bad}")
        if p.get("withheld"):
            extra = sorted(set(p) & MASKED_DROP)
            if extra:
                out.append(f"row {i}: withheld place carries {extra}")
            if p["withheld"] not in REASONS:
                out.append(f"row {i}: unknown reason {p['withheld']!r}")
            elif not_tourism(p, rv):
                out.append(f"row {i}: not tourism ({p['withheld']}, {p.get('overture_category')}), so not counted or published (decision 47): run build.py")
            if p.get("confidence") is not None and p["confidence"] != conf_step(p["confidence"]):
                out.append(f"row {i}: withheld place's confidence is not on the {CONF_STEP} step")
            if p.get("transit_m") is not None and p["transit_m"] != coarse_transit(p["transit_m"], bool(p.get("transit_400m"))):
                out.append(f"row {i}: withheld place's transit_m is not coarsened")
            continue
        name = p.get("name") or ""
        if PHONE.search(name) or EMAIL.search(name):
            out.append(f"row {i} ({p.get('oid')}): the name holds a telephone number or an e-mail address")
        if p.get("oid") in rv["withheld"]:
            out.append(f"row {i} ({p.get('oid')}): drawn, but places_review.json withholds it ({rv['withheld'][p['oid']]})")
        elif p.get("oid") not in rv["public"]:
            hits = matches(name, p.get("overture_category"), rv)
            if hits:
                out.append(f"row {i} ({p.get('oid')}, {p.get('overture_category')}): drawn but matches {hits} without a review")
    return out


def count_problems(places, data_dir=DATA):
    """The published counts that no longer agree with places.json (after rows were dropped without a build): meta.json's tourism_places and the
    municipalities' assets, on the default basis (confidence 0.50 or more, no places of worship)."""
    n = sum(1 for p in places if p.get("type") != "Places of Worship" and (p.get("confidence") or 0) >= 0.5)
    out = []
    try:
        meta = json.loads((Path(data_dir) / "meta.json").read_text(encoding="utf-8"))
        stats = json.loads((Path(data_dir) / "municipalities.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return out
    if meta.get("counts", {}).get("tourism_places") != n:
        out.append(f"meta.json: tourism_places {meta.get('counts', {}).get('tourism_places')} but places.json has {n:,} on the default basis: run build.py")
    if sum(s.get("assets", 0) for s in stats.values()) != n:
        out.append(f"municipalities.json: the assets add up to {sum(s.get('assets', 0) for s in stats.values()):,}, places.json has {n:,}: run build.py")
    return out


def apply_files(data_dir=DATA, write=True, log=print):
    """Mask the withheld places of a published places.json that still carries names (the build does this itself; this is for a file written before
    the rule). Drops the listings that are not tourism (not_tourism(), decision 47; the counts then need build.py), moves the withheld ones last
    (publish_order), with place_access.json in the same order; a withheld place keeps
    a coarsened transit_m and gets hub_400m from access.py, so the nightly refresh can count it without its point. Returns the counts by reason."""
    import access
    import walknet  # noqa: F401  (access.compute imports it when given a network; not needed for hub400)
    rv = load_review()
    path = Path(data_dir) / "places.json"
    places = json.loads(path.read_text(encoding="utf-8"))
    todo = [i for i, p in enumerate(places) if not p.get("withheld") and "lat" in p]
    for i in todo:
        places[i]["withheld"] = reason(places[i], rv)
    stops = json.loads((Path(data_dir) / "transport.json").read_text(encoding="utf-8"))
    ops = json.loads((Path(data_dir) / "operators.json").read_text(encoding="utf-8"))["operators"]
    meta = json.loads((Path(data_dir) / "meta.json").read_text(encoding="utf-8"))
    from datetime import date
    as_of = date.fromisoformat(meta["access"]["as_of"])
    have = [i for i, p in enumerate(places) if "lat" in p]
    res = access.compute([places[i] for i in have], stops, ops, as_of)   # hub400 only (straight line); the published columns are not touched here
    for k, i in enumerate(have):
        if places[i].get("withheld") and res.hub400[k]:
            places[i]["hub_400m"] = True
    out = [public_row(p) for p in places]
    keep = [i for i, p in enumerate(out) if not not_tourism(p, rv)]   # decision 47: what is not tourism is not counted or published
    keepset = set(keep)
    dropped = Counter(out[i]["withheld"] for i in range(len(out)) if i not in keepset)
    counts = Counter(out[i]["withheld"] for i in keep if out[i].get("withheld"))
    cols_path = Path(data_dir) / "place_access.json"
    cols = coarsen_columns(json.loads(cols_path.read_text(encoding="utf-8")), out) if cols_path.exists() else None
    kept = [out[i] for i in keep]
    perm = [keep[i] for i in publish_order(kept)]   # old row numbers, in the published order
    out = [out[i] for i in perm]
    cols = permute_columns(cols, perm) if cols is not None else None
    if write:
        path.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        if cols is not None:
            cols_path.write_text(json.dumps(cols, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    log(f"places_privacy: {len(out):,} rows; withheld {sum(counts.values()):,} ({', '.join(f'{k} {v:,}' for k, v in counts.most_common())}); contact fields dropped; "
        "the distances of the withheld places coarsened"
        + (f"; {sum(dropped.values()):,} not tourism dropped ({', '.join(f'{k} {v:,}' for k, v in dropped.most_common())}): run build.py so that every count follows"
           if dropped else ""))
    return counts


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--check", action="store_true", help="exit 1 when the published places.json breaks the rule")
    ap.add_argument("--report", action="store_true", help="counts by reason and Overture category (no names)")
    args = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    rv = load_review()
    places = json.loads((DATA / "places.json").read_text(encoding="utf-8"))
    if args.check or args.report:
        P = problems(places, rv) + order_problems(places)
        cols_path = DATA / "place_access.json"
        if cols_path.exists():
            P += column_problems(json.loads(cols_path.read_text(encoding="utf-8")), places)
        P += count_problems(places, DATA)
        counts = Counter(p["withheld"] for p in places if p.get("withheld"))
        print(f"places_privacy: {len(places):,} rows, {sum(counts.values()):,} withheld ({', '.join(f'{k} {v:,}' for k, v in counts.most_common())}), "
              f"{sum(1 for p in places if p.get('oid') in rv['public'])} drawn by review; {len(P)} problems")
        for x in P[:50]:
            print("  PROBLEM " + x)
        if args.report:
            by = Counter((p["withheld"], p["type"]) for p in places if p.get("withheld"))
            for (r, t), n in sorted(by.items(), key=lambda x: (x[0][0], -x[1])):
                print(f"  {r:12s} {t:28s} {n:6,}")
        return 1 if P else 0
    apply_files()
    return 0


if __name__ == "__main__":
    sys.exit(main())
