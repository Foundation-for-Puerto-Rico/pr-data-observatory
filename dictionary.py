"""Builds site/data/dictionary.json (the data dictionary page) from dictionary_src/, and checks that it stays complete.

  python dictionary.py                   build site/data/dictionary.json and the files the dictionary page reads (dictionary_list.json, dictionary_detail_*.json)
  python dictionary.py --check FILE...   validate entry files (schema, ids, sources, cross-references)
  python dictionary.py --coverage        list published fields that no entry documents
  python dictionary.py --links           check that every "where it appears" link opens something real
  python dictionary.py --index [DOMAIN]  list entries (id | domain | group | name | file), read-only; DOMAIN is a registry id (a parent includes its sub-domains)
  python dictionary.py --dump [DOMAIN]   print full entries, read-only
  python dictionary.py --domains         write docs/domains.md from the domain registry (dictionary_src/domains.json)
  python dictionary.py --es              how much of the dictionary has Spanish, and which Spanish is older than its English (read-only)

The observatory's database only grows. build.py runs the coverage check so a new dataset cannot ship undocumented.
Format and writing rules: dictionary_src/README.md. Spanish: dictionary_src/es/README.md.
"""
import hashlib
import json
import re
import sys
import unicodedata
from urllib.parse import unquote
from collections import Counter, OrderedDict
from datetime import date
from pathlib import Path

import contract

ROOT = Path(__file__).parent
SRC = ROOT / "dictionary_src"
DATA = ROOT / "site" / "data"
PLAIN_ES = ROOT / "i18n_src" / "dictionary_plain.json"

KINDS = ["variable", "layer", "table", "boundary", "category", "measure", "method"]
VALUE_TYPES = ["count", "rate", "level", "ratio", "index", "flag", "code", "text", "date", "geometry"]
TIMELINES = ["snapshot", "annual", "five-year window", "decennial", "event-based", "live", "static"]
REQUIRED = ["id", "name", "domain", "domains", "group", "kind", "plain", "definition", "unit", "value_type", "geography", "coverage", "method", "sources", "where", "added"]
ID_RE = re.compile(r"^[a-z0-9][a-z0-9_.-]*$")
FILEREF_RE = re.compile(r"^[A-Za-z0-9_.\-/]+:(\*|\S.*)$")
FILE_LEVEL = {"buildings_gap.pmtiles", "operators.json", "trips.json", "trips_sa.json", "trips_su.json", "population_blocks.json", "gazetteer.json", "roads.bin",
              "housing.json", "meta.json", "registry.json", "wanted.json", "catalog.json", "catalog_index.json", "catalog_domains.json", "facility_hazards.json", "catalog_es.json", "catalog_views.json", "geo/crosswalk.json", "transit_supply.json", "population_age.json", "women_labor.json", "nightlights_monthly.json", "inflation.json"}   # documented as whole files (file:*), or field by field if an author prefers
SKIP_FILES = {"dictionary.json", "dictionary_summary.json"}   # and the files of the dictionary page made from dictionary.json (is_page_file), and the highlighter's (GLOSSARY_FILES)

# series variables that no author has covered yet get a domain from their catalog group (registry ids; see dictionary_src/domains.json)
SERIES_DOMAIN = {"economy": {"Public money": "public-money", "People": "population"},
                 "housing": {"Population": "population", "Disaster recovery": "public-money"},
                 "health": {},
                 "population": {"Health insurance": "health", "Education level": "education"},
                 "education": {},
                 "labor_sex": {"Labor force by sex": "economy"},
                 "infrastructure": {},
                 "community": {"Education · Historic places": "education", "Health · Treatment facilities (SAMHSA)": "health"},
                 "facilities": {"Housing · Public housing": "housing", "Infrastructure · Emergency services": "infrastructure", "Education · Libraries": "education"},
                 "nonprofits": {"Economy · Nonprofit organizations": "economy"},
                 "conditions": {"Environment · Regulated sites (EPA)": "environment", "Environment · Water and air quality (EPA)": "environment", "Housing · Severe housing problems": "housing",
                                "Infrastructure · Street connectivity": "infrastructure.mobility", "Health care · Distance to a general hospital": "health"},
                 "landslide": {"Environment · Landslide susceptibility (USGS)": "hazards"},
                 "nightlights": {"Economy · Night-time lights (NASA Black Marble)": "economy"},
                 "broadband": {"Infrastructure · Broadband (FCC)": "infrastructure"},
                 "commuting": {"Population · Daytime population": "population"},
                 "svi": {"Vulnerability (CDC/ATSDR SVI)": "hazards"},
                 "credit": {"Economy · Banks and deposits (FDIC)": "economy", "Housing · Home loans (HMDA)": "housing"},
                 "facility_exposure": {"Hazards · Facilities and roads in hazard areas": "hazards"},
                 "drought": {"Hazards · Drought (US Drought Monitor)": "hazards"},
                 "storm_recovery": {"Hazards · Storm recovery (night-time light)": "hazards"},
                 "essentials": {"Communities · Road distance to essentials (estimate)": "communities"},
                 "cutoff": {"Hazards · Cut off from hospitals (estimate)": "hazards"},
                 "jobs_reach": {"Economy · Jobs within reach (estimate)": "economy"},
                 "netmig_age": {"Population · Net migration by age, 2010-2020 (estimate)": "population"},
                 "degrees": {"Education · Degrees awarded (IPEDS)": "education"},
                 "school_conditions": {"Education · School conditions (Civil Rights Data Collection)": "education"},
                 "proficiency": {"Education · Test results (META-PR, 2014-15 to 2018-19)": "education"},
                 "providers": {"Health · Health care providers (NPPES registry)": "health"},
                 "energy": {"Infrastructure · Energy (LUMA)": "infrastructure.energy", "Infrastructure · Energy (ACS)": "infrastructure.energy"},
                 "heat": {"Environment · Surface heat (Landsat)": "environment"},
                 "vegetation": {"Environment · Vegetation (Sentinel-2)": "environment.land"},
                 "buildings": {"Housing · Buildings (Overture)": "housing"},
                 "fires": {"Environment · Fires (NASA FIRMS)": "hazards"},
                 "night_heat": {"Environment · Night surface heat (ECOSTRESS)": "environment"},
                 "climb": {"Infrastructure · Climb on the walk to a stop (USGS 3DEP)": "infrastructure.mobility"},
                 "slope": {"Environment · Slope of the land (USGS 3DEP)": "environment.land"},
                 "environment": {"Natural hazard risk": "hazards", "Landslides": "hazards", "Earthquakes": "hazards", "Community resilience": "hazards", "Wetlands": "environment.land"}}
HS_COUNT = {"census_housing_units", "census_vacant_units", "housing_units", "vacant_units", "seasonal_units", "other_vacant_units", "households", "fema_ia_households", "population"}


def load_json(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


# ── Inventory of what is published ───────────────────────────────────────────

def inventory():
    """{file: set(fields)}; '*' marks a file that is documented as a whole."""
    inv = {}
    for name, p in contract.published_files(DATA):
        if name in SKIP_FILES or is_page_file(name) or name in GLOSSARY_FILES:
            continue
        if p.suffix == ".geojson":
            g = load_json(p)
            fields = set()
            for f in g["features"]:
                fields.update((f.get("properties") or {}).keys())
            inv[name] = fields
        elif name in ("economy_series.json", "housing_series.json", "health_series.json", "population_series.json", "commuting_series.json", "svi_series.json", "svi_tract.json", "credit_series.json", "drought_series.json", "storm_recovery_series.json", "storm_recovery_barrio.json", "essentials_series.json", "essentials_barrio.json", "cutoff_series.json", "cutoff_barrio.json", "jobs_reach_series.json", "netmig_age_series.json", "degrees_series.json", "school_conditions_series.json", "proficiency_series.json", "providers_series.json", "facility_exposure_series.json", "education_series.json", "labor_sex_series.json", "medicare_series.json", "care_series.json", "infrastructure_series.json", "bridges_series.json", "traffic_series.json", "crashes_series.json", "environment_series.json", "hazard_series.json", "gateway_series.json", "facility_series.json", "community_series.json", "nonprofit_series.json", "conditions_series.json", "conditions_barrio.json", "landslide_series.json", "landslide_barrio.json", "heat_series.json", "heat_barrio.json", "vegetation_series.json", "buildings_series.json", "fires_series.json", "vegetation_barrio.json", "buildings_barrio.json", "night_heat_series.json", "night_heat_barrio.json", "climb_series.json", "climb_barrio.json", "infrastructure_barrio.json", "slope_series.json", "slope_barrio.json", "nightlights_series.json", "nightlights_barrio.json", "broadband_series.json", "energy_series.json", "broadband_barrio.json", "energy_barrio.json", "wcrp_rvi_barrio.json", "acs_barrio.json", "acs_tract.json", "acs_blockgroup.json"):   # the last three hold, for variables that exist for the municipios, the same keys at finer levels
            j = load_json(p)
            inv[name] = {v["key"] for v in j["vars"] if v.get("years")}
        elif name.startswith("exposure_") and p.suffix == ".json":   # one field per family (each holds residents and housing units per area), and the totals they are shares of
            inv[name] = set(load_json(p)["vars"]) | {"total"}
        elif name == "wcrp_rvi_inputs.json":   # the input values behind the WCRP vulnerability index, one field per input of each version, and the population
            j = load_json(p)
            inv[name] = {k for ver in ("orig", "rebuild") for k in j[ver]["values"]} | {"population"} | set(j["rebuild"].get("context", {}))   # context: the age groups beside the index
        elif name == "wcrp_social.json":   # the WCRP Social Capital summary (wcrp_social.py): residents, Comunidades Especiales and the WCRP list's asset flags, by municipio
            j = load_json(p)
            inv[name] = {"population", "polygons", "housing_units", "listed", "matched"} | set(j["assets"]["flags"])
        elif name == "landuse_summary.json":   # one field per land-use class (km² of it in each municipio and in Puerto Rico); the municipios are rows, not fields
            inv[name] = {c["key"] for c in load_json(p)["classes"]}
        elif name == "route_compare.json":   # the Route analysis (docs/analysis/route-analysis-2026-10/): the fields of its routes and of its operators
            j = load_json(p)
            inv[name] = {k for table in ("routes", "operators") for r in j[table] for k in r}
        elif name == "gii_profile.json":   # the Global Innovation Index (gii.py): the fields of its 80 indicator records; pillars, texts and sources are metadata
            inv[name] = {k for r in load_json(p)["indicators"] for k in r}
        elif name == "reservoir_history.json":   # the Reservoirs page (reservoirs.py): the fields of its reservoir records; source, years and notes are metadata
            inv[name] = {k for r in load_json(p)["reservoirs"] for k in r}
        elif name == "place_access.json":   # columns (one value per place, in the order of places.json); the other keys only describe them
            j = load_json(p)
            inv[name] = {k for k, v in j.items() if isinstance(v, list)}
        elif p.suffix == ".json" and name not in FILE_LEVEL:
            j = load_json(p)
            fields = set()
            if isinstance(j, list):
                for r in j:
                    if isinstance(r, dict):
                        fields.update(r.keys())
            elif isinstance(j, dict):
                for r in j.values():
                    if isinstance(r, dict):
                        fields.update(r.keys())
            inv[name] = fields or {"*"}
        else:
            inv[name] = {"*"}
    return inv


# ── Sources ──────────────────────────────────────────────────────────────────

def load_sources():
    s = load_json(SRC / "sources.json")
    aliases = s.pop("_aliases", {})
    return s, aliases


def resolve(sid, sources, aliases):
    if sid in sources:
        return sid
    return aliases.get(sid)


# ── Series catalogs → base entries ───────────────────────────────────────────

def series_base():
    out = {}
    for ds, fname in (("economy", "economy_series.json"), ("housing", "housing_series.json"), ("health", "health_series.json"), ("population", "population_series.json"), ("commuting", "commuting_series.json"), ("svi", "svi_series.json"), ("facility_exposure", "facility_exposure_series.json"), ("credit", "credit_series.json"), ("drought", "drought_series.json"), ("storm_recovery", "storm_recovery_series.json"), ("essentials", "essentials_series.json"), ("cutoff", "cutoff_series.json"), ("jobs_reach", "jobs_reach_series.json"), ("netmig_age", "netmig_age_series.json"), ("degrees", "degrees_series.json"), ("school_conditions", "school_conditions_series.json"), ("proficiency", "proficiency_series.json"), ("providers", "providers_series.json"), ("education", "education_series.json"), ("labor_sex", "labor_sex_series.json"), ("health", "medicare_series.json"), ("health", "care_series.json"), ("infrastructure", "infrastructure_series.json"), ("infrastructure", "bridges_series.json"), ("infrastructure", "traffic_series.json"), ("infrastructure", "crashes_series.json"), ("environment", "environment_series.json"), ("environment", "hazard_series.json"), ("infrastructure", "gateway_series.json"), ("facilities", "facility_series.json"), ("community", "community_series.json"), ("nonprofits", "nonprofit_series.json"), ("conditions", "conditions_series.json"), ("landslide", "landslide_series.json"), ("heat", "heat_series.json"), ("vegetation", "vegetation_series.json"), ("buildings", "buildings_series.json"), ("fires", "fires_series.json"), ("night_heat", "night_heat_series.json"), ("climb", "climb_series.json"), ("slope", "slope_series.json"), ("nightlights", "nightlights_series.json"), ("broadband", "broadband_series.json"), ("energy", "energy_series.json")):
        j = load_json(DATA / fname)
        for v in j["vars"]:
            if not v.get("years"):
                continue   # metadata-only rows (values live in the Housing series)
            ys = sorted(int(y) for y in v["years"])
            unit = v.get("unit") or ""
            kind = v.get("type") or v.get("kind")
            if ds in ("economy", "health", "population", "labor_sex", "facilities", "community", "nonprofits", "conditions", "landslide", "nightlights", "broadband", "heat", "vegetation", "buildings", "fires", "night_heat", "climb", "slope"):
                vt = {"count": "count", "total$": "level", "level$": "level", "rate": "rate", "ratio": "ratio"}.get(kind, "count")
                srcs = list(v.get("sources") or [])
            else:
                vt = "level" if unit == "$" else ("count" if v["key"] in HS_COUNT else ("rate" if unit == "%" else "ratio"))
                srcs = {"pop": ["housing_pep"], "census": ["housing_census"], "acs": ["housing_acs"], "derived": ["housing_acs", "housing_derived"], "fema": ["housing_fema"]}.get(v.get("kind"), ["housing_acs"])
            group = v.get("group") or ""
            domain = SERIES_DOMAIN[ds].get(group) or ds
            out[f"{ds}.{v['key']}"] = {
                "id": f"{ds}.{v['key']}", "name": v.get("label") or v["key"], "domain": domain, "domains": [domain], "group": group, "kind": "variable",
                "plain": "", "definition": v.get("definition") or "", "unit": unit or ("count" if vt == "count" else ""), "value_type": vt,
                "geography": "78 municipalities and Puerto Rico", "coverage": {"timeline": "snapshot" if ds in ("health", "facilities", "community", "nonprofits", "conditions", "landslide", "heat", "vegetation", "buildings", "night_heat", "climb", "slope") else "five-year window" if ds in ("population", "labor_sex") else "annual", "first": ys[0], "last": ys[-1], "frequency": "Rebuilt with each snapshot"},
                "method": "", "sources": srcs, "source_detail": v.get("ref") or "", "where": {"files": [f"{fname}:{v['key']}"]}, "added": {"housing": "2026-10-02", "economy": "2026-10-03", "health": "2026-10-06", "population": "2026-10-06", "commuting": "2026-11-14", "svi": "2026-11-14", "credit": "2026-11-16", "drought": "2026-11-16", "storm_recovery": "2026-11-17", "essentials": "2026-11-18", "cutoff": "2026-11-20", "jobs_reach": "2026-11-24", "netmig_age": "2026-11-24", "degrees": "2026-11-18", "school_conditions": "2026-11-18", "proficiency": "2026-11-18", "providers": "2026-11-18", "facility_exposure": "2026-11-16", "education": "2026-10-14", "labor_sex": "2026-10-30", "infrastructure": "2026-10-14", "environment": "2026-10-14", "facilities": "2026-10-17", "community": "2026-10-18", "nonprofits": "2026-10-17", "conditions": "2026-10-17", "landslide": "2026-10-18", "nightlights": "2026-11-04", "broadband": "2026-11-10", "heat": "2026-11-04", "vegetation": "2026-11-04", "buildings": "2026-11-09", "fires": "2026-11-10", "night_heat": "2026-11-04", "climb": "2026-11-04", "slope": "2026-11-10", "energy": "2026-11-14"}[ds],
                "has_moe": bool(v.get("moe")), "_autofilled": True,
            }
    return out


# ── Load and validate entry files ────────────────────────────────────────────

def load_entries(paths=None):
    entries, problems = [], []
    files = [Path(p) for p in paths] if paths else sorted((SRC / "entries").glob("*.json"))
    for f in files:
        try:
            data = load_json(f)
        except Exception as e:
            problems.append(("error", f.name, "-", f"not valid JSON: {e}"))
            continue
        if not isinstance(data, list):
            problems.append(("error", f.name, "-", "the file must hold a JSON list of entries"))
            continue
        for e in data:
            e["_file"] = f.name
            entries.append(e)
    return entries, problems


def validate(entries, sources, aliases, inv, known_ids=None, domain_ids=None):
    P = []
    domain_ids = set(domain_ids if domain_ids is not None else contract.domains_by_id(contract.load_registry()))
    seen = {}
    for e in entries:
        f, i = e.get("_file", "-"), e.get("id", "?")

        def err(msg, sev="error"):
            P.append((sev, f, i, msg))
        for k in REQUIRED:
            if k not in e or e[k] in (None, "", [], {}):
                if k == "where" and isinstance(e.get("where"), dict) and "files" in e["where"]:
                    continue
                err(f"missing required field '{k}'")
        if not isinstance(i, str) or not ID_RE.match(i):
            err("id must be lowercase letters, digits, _ - . and start with a letter or digit")
        elif i in seen:
            err(f"duplicate id (also in {seen[i]})")
        else:
            seen[i] = f
        if e.get("domain") not in domain_ids:
            err(f"domain '{e.get('domain')}' is not in the registry (dictionary_src/domains.json)")
        dl = e.get("domains")
        if isinstance(dl, list):
            if dl and dl[0] != e.get("domain"):
                err("domains must start with the primary domain (the same value as 'domain')")
            for x in dl:
                if x not in domain_ids:
                    err(f"domains lists '{x}', which is not in the registry")
            if len(set(dl)) != len(dl):
                err("domains lists a domain twice")
        elif "domains" in e:
            err("domains must be a list of domain ids, primary first")
        if e.get("kind") not in KINDS:
            err(f"kind '{e.get('kind')}' is not in the list")
        if e.get("value_type") not in VALUE_TYPES:
            err(f"value_type '{e.get('value_type')}' is not in the list")
        c = e.get("coverage")
        if isinstance(c, dict):
            if c.get("timeline") not in TIMELINES:
                err(f"coverage.timeline '{c.get('timeline')}' is not in the list")
            for k in ("first", "last"):
                if c.get(k) is not None and not isinstance(c.get(k), int):
                    err(f"coverage.{k} must be a year (number) or null")
        elif "coverage" in e:
            err("coverage must be an object")
        s = e.get("sources")
        if isinstance(s, list):
            for sid in s:
                if not resolve(sid, sources, aliases):
                    err(f"unknown source id '{sid}'")
        elif "sources" in e:
            err("sources must be a list")
        w = e.get("where")
        if isinstance(w, dict):
            for ref in w.get("files", []) or []:
                if not isinstance(ref, str) or not FILEREF_RE.match(ref):
                    err(f"where.files entry '{ref}' must look like file.json:field")
                    continue
                fn, fld = ref.split(":", 1)
                if fn not in inv:
                    err(f"where.files names '{fn}', which is not in site/data/")
                elif fld != "*" and fld not in inv[fn] and inv[fn] != {"*"}:
                    err(f"where.files names '{fld}', which is not a field of {fn}")
            for v in w.get("view", []) or []:
                if not isinstance(v, dict) or not v.get("label") or not v.get("href"):
                    err("where.view entries need label and href")
        elif "where" in e:
            err("where must be an object")
        for k in ("caveats", "see_also"):
            if k in e and not (isinstance(e[k], list) and all(isinstance(x, str) and x for x in e[k])):
                err(f"{k} must be a list of non-empty strings")
        p = e.get("plain") or ""
        if len(p) > 480:
            err(f"plain is {len(p)} characters; keep it to one or two sentences", "warn")
        if "\n" in p:
            err("plain must be one paragraph", "warn")
        if re.search(r"\bTODO\b|\bTBD\b", json.dumps(e, ensure_ascii=False)):
            err("contains a TODO placeholder")
        if e.get("added") and not re.match(r"^\d{4}-\d{2}-\d{2}$", str(e["added"])):
            err("added must be YYYY-MM-DD")
        if "ask" in e:   # the words people use to ask for it, for the chat (plan item 14): { "en": [...], "es": [...] }, plain lower-case words without accents or question marks
            a = e["ask"]
            if not isinstance(a, dict) or set(a) - {"en", "es"} or not a:
                err("ask must be an object with 'en' and/or 'es' lists")
            else:
                for lang, ws in a.items():
                    if not isinstance(ws, list) or not all(isinstance(w, str) and w.strip() and len(w.strip()) >= 3 and w == w.lower() and not re.search(r"[?¿!¡]", w) for w in ws):
                        err(f"ask.{lang} must be a list of lower-case phrases of 3 or more characters, without question marks")
        if known_ids is not None:
            for r in e.get("see_also", []) or []:
                if r not in known_ids:
                    err(f"see_also '{r}' does not exist", "warn")
    return P


# ── Merge, coverage, build ───────────────────────────────────────────────────

# A glossary term (dictionary_src/README.md, "Glossary"; docs/glossary.md): both languages and a source are required.
GLOSSARY_KEYS = {"id", "term", "term_es", "expansion", "expansion_es", "plain", "plain_es", "hold_es", "source", "match", "not_match", "case_sensitive", "highlight", "highlight_why", "priority", "see_also", "section"}
GLOSSARY_SECTIONS = ("browse", "sources", "glossary", "files", "cite")
OBS_URL = "https://observatory.foundationpr.org/"
SOURCE_KEYS = {"name", "name_es", "url", "checked"}


def is_iso_date(s):
    """A real calendar date written YYYY-MM-DD (date.fromisoformat also accepts other ISO forms, so the length is checked too)."""
    try:
        return isinstance(s, str) and len(s) == 10 and bool(date.fromisoformat(s))
    except ValueError:
        return False


def glossary_slug(term):
    """The anchor of a term on the dictionary page (dictionary.js slug(): accents removed, lower case, runs of other characters become '-')."""
    return re.sub(r"^-|-$", "", re.sub(r"[^a-z0-9]+", "-", js_norm(term)))


def glossary_form_cs(term, form):
    """Whether a match form is compared with its capitals: every form of a case_sensitive term, and in any term a form written in capitals (an acronym such as STR or SFHA)."""
    return bool(term.get("case_sensitive")) or (form == form.upper() and len(re.sub(r"[^A-Z]", "", form)) >= 2)


def check_glossary(glossary, known_ids):
    P, seen, ids, forms = [], set(), set(), {}
    for g in glossary:
        t = g.get("term")
        def err(msg, sev="error"):
            P.append((sev, "glossary.json", t or "?", msg))
        if not t or not g.get("plain"):
            err("needs term and plain")
            continue
        if t.lower() in seen:
            err("duplicate term")
        seen.add(t.lower())
        for k in set(g) - GLOSSARY_KEYS:
            err(f"unknown field '{k}'")
        if g.get("id") != glossary_slug(t):
            err(f"id must be '{glossary_slug(t)}' (the term's anchor on the dictionary page)")
        elif g["id"] in ids:
            err("two terms have the same id")
        ids.add(g.get("id"))
        if not (g.get("plain_es") or "").strip():
            err("needs a Spanish definition (plain_es): every term is defined in both languages")
        if g.get("hold_es") not in (None, "compliance"):
            err("hold_es must be 'compliance' (the Spanish waits for Finance and Compliance review) or absent")
        s = g.get("source")
        if not isinstance(s, dict) or not (s.get("name") or "").strip() or not re.match(r"^https://\S+$", s.get("url") or ""):
            err("needs a source: {name, url (https), checked}")
        else:
            if not is_iso_date(s.get("checked")):
                err("source.checked must be the date the link was checked (YYYY-MM-DD, a real date)")
            for k in set(s) - SOURCE_KEYS:
                err(f"unknown source field '{k}'")
            if s["url"].startswith(OBS_URL) and not (s.get("name_es") or "").strip():
                err("a source on the observatory's own pages needs its Spanish name (source.name_es)")
            if s["url"].startswith(OBS_URL + "dictionary.html#"):
                a = s["url"].split("#", 1)[1]
                if a not in known_ids and a not in GLOSSARY_SECTIONS:
                    err(f"source link '#{a}' is not a dictionary entry or section")
        m = g.get("match")
        if not isinstance(m, dict) or set(m) != {"en", "es"} or not all(isinstance(m[l], list) and m[l] and all(isinstance(f, str) and f.strip() == f and f for f in m[l]) for l in ("en", "es")):
            err("match needs 'en' and 'es' lists of the forms to find in text")
        else:
            for lang in ("en", "es"):
                for f in m[lang]:
                    key = (lang, f if glossary_form_cs(g, f) else f.lower())
                    if g.get("highlight") and key in forms and forms[key] != t:
                        err(f"match form '{f}' ({lang}) is also a form of '{forms[key]}': a highlighted form must name one term")
                    if g.get("highlight"):
                        forms.setdefault(key, t)
                    if f.startswith("!"):
                        err(f"match form '{f}' ({lang}) starts with '!', which the highlighter's files use for not_match")
            nm = g.get("not_match")
            if nm is not None:
                if not isinstance(nm, dict) or not set(nm) <= {"en", "es"} or not all(isinstance(nm[l], list) and nm[l] and all(isinstance(f, str) and f.strip() == f and f and not f.startswith("!") for f in nm[l]) for l in nm):
                    err("not_match is {lang: [phrases]}: longer phrases that hold one of the term's forms but are not the term")
                else:
                    for lang, phrases in nm.items():
                        for f in phrases:
                            if not any(glossary_form_re(x, glossary_form_cs(g, x)).search(f) for x in m[lang]):
                                err(f"not_match phrase '{f}' ({lang}) holds none of the term's forms, so it would never stop a mark")
        for k in ("case_sensitive", "highlight"):
            if not isinstance(g.get(k), bool):
                err(f"{k} must be true or false")
        if "highlight_why" in g and (g.get("highlight") is not False or not isinstance(g["highlight_why"], str) or not g["highlight_why"].strip()):
            err("highlight_why is the reason a term is not underlined: a non-empty text, only with highlight false")
        if g.get("priority") not in (1, 2, 3):
            err("priority must be 1 (blocks understanding), 2 or 3")
        if g.get("section") is not None and g["section"] not in GLOSSARY_SECTIONS:
            err(f"section must be one of {', '.join(GLOSSARY_SECTIONS)}")
        for r in g.get("see_also", []) or []:
            if r not in known_ids:
                err(f"see_also '{r}' does not exist", "warn")
        if re.search(r"\bTODO\b", json.dumps(g, ensure_ascii=False)):
            err("contains a TODO placeholder")
    return P


def published_glossary(glossary):
    """The glossary as the site publishes it: a Spanish definition held for review (hold_es) is left out, so Spanish pages show the English one."""
    out = []
    for g in sorted(glossary, key=lambda g: g["term"].lower()):
        g = dict(g)
        if g.get("hold_es"):
            g.pop("plain_es", None)
            g.pop("expansion_es", None)
            if "name_es" in (g.get("source") or {}):
                g["source"] = {k: v for k, v in g["source"].items() if k != "name_es"}
        out.append(g)
    return out


# ── The highlighter's files (docs/glossary.md, part 2) ────────────────────────
# Made from the published glossary, so held Spanish never reaches them. site/js/core/glossary.js builds the same two structures from the dictionary page's own copy of the
# glossary (formsFrom, defsFrom), and tests/glossary.test.js checks that both give the same result.
#   glossary_forms_<lang>.json  {"lang", "terms": [[id, [forms], [1 when the form is compared with its capitals, else 0]]]}: the highlighted terms only, fetched just after the page is
#                               ready; a form with "!" in front is a not_match phrase, where nothing is marked
#   glossary_defs_<lang>.json   {"lang", "terms": {id: [name, expansion, definition, source name, source url, date checked, english]}}: every term (a page can mark a term
#                               that is not highlighted on purpose, data-gloss="<id>"), fetched the first time a reader points at a word. On a Spanish page `english` says
#                               which texts are still English, so the tooltip marks them lang="en": 1 the definition (held for review), 2 the expansion, 4 the source's name.
GLOSSARY_LANGS = ("es", "en")
GLOSSARY_FILES = tuple(f"glossary_{kind}_{lang}.json" for kind in ("forms", "defs") for lang in GLOSSARY_LANGS)


def glossary_shown(g, lang):
    """The name and the expansion a tooltip shows, as the dictionary's Glossary section shows them (dictionary.js renderGlossary): the expansion only when the name does not hold it."""
    es = lang == "es"
    name = (es and g.get("term_es")) or g["term"]
    exp = (es and g.get("expansion_es")) or g.get("expansion") or ""
    return name, ("" if exp and js_norm(exp) in js_norm(name) else exp)


def glossary_page_files(published):
    """{file name: content} of the highlighter's four files, made from the published glossary (published_glossary)."""
    out = {}
    for lang in GLOSSARY_LANGS:
        es = lang == "es"
        forms = []
        for g in published:
            if g.get("highlight"):
                nm = (g.get("not_match") or {}).get(lang, [])   # a phrase that holds a form but is not the term: kept with "!" in front (glossary.js formsFrom)
                forms.append([g["id"], g["match"][lang] + ["!" + f for f in nm], [1 if glossary_form_cs(g, f) else 0 for f in g["match"][lang] + nm]])
        defs = {}
        for g in published:
            name, exp = glossary_shown(g, lang)
            s = g.get("source") or {}
            english = (1 if es and not g.get("plain_es") else 0) | (2 if es and exp and not g.get("expansion_es") else 0) | (4 if es and not s.get("name_es") else 0)
            defs[g["id"]] = [name, exp, (es and g.get("plain_es")) or g["plain"], (es and s.get("name_es")) or s.get("name", ""), s.get("url", ""), s.get("checked", ""), english]
        out[f"glossary_forms_{lang}.json"] = {"lang": lang, "terms": forms}
        out[f"glossary_defs_{lang}.json"] = {"lang": lang, "terms": defs}
    return out


def write_glossary_files(published, data_dir=DATA):
    for name, j in glossary_page_files(published).items():
        (data_dir / name).write_text(json.dumps(j, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"wrote {len(GLOSSARY_FILES)} glossary files for the highlighter ({sum(1 for g in published if g.get('highlight'))} highlighted terms)")


# A priority-1 term (it blocks understanding of what a page shows) that appears in the interface is underlined, unless its record says why not (highlight_why).
UI_PAGES = ("index.html", "3d.html", "profile.html", "housing.html", "wcrp.html", "route-analysis.html", "gii.html", "women-labor.html", "public-money.html", "public-spending.html", "knowledge.html", "learn.html", "dictionary.html", "data-management.html")


def ui_texts():
    """The visible text of the interface, by language: the static text of the pages and every interface string (the English keys and the Spanish values of
    i18n_src/es/*.json, which hold the legends, the help texts and the pop-ups): the text the glossary's inventory scanned (docs/glossary.md)."""
    import html as _html
    pages = []
    for p in UI_PAGES:
        t = re.sub(r"(?is)<(script|style|noscript|svg)\b.*?</\1>", " ", (ROOT / "site" / p).read_text(encoding="utf-8"))
        pages.append(_html.unescape(re.sub(r"<[^>]+>", " ", t)))
    en, es = list(pages), []
    for f in sorted((ROOT / "i18n_src" / "es").glob("*.json")):
        for k, v in load_json(f).items():
            if not k.startswith("_"):
                en.append(k)
                es += v if isinstance(v, list) else [v]
    return {"en": "\n".join(en), "es": "\n".join(es)}


def glossary_form_re(form, cs):
    """A match form as the highlighter finds it (site/js/core/glossary.js): an edge that is a letter or a digit must not touch another letter or digit."""
    body = r"\s+".join(re.escape(w) for w in form.split())
    a = r"(?<![^\W_])" if re.match(r"[^\W_]", form) else ""
    z = r"(?![^\W_])" if re.search(r"[^\W_]$", form) else ""
    return re.compile(a + body + z, 0 if cs else re.IGNORECASE)


def check_glossary_ui(glossary, texts=None):
    """Errors for a priority-1 term that appears in the interface but is not underlined, with no highlight_why to say why."""
    texts = texts or ui_texts()
    P = []
    for g in glossary:
        if g.get("priority") != 1 or g.get("highlight") is not False or (g.get("highlight_why") or "").strip():
            continue
        seen = [f"'{f}' ({lang})" for lang in ("en", "es") for f in (g.get("match") or {}).get(lang, []) if glossary_form_re(f, glossary_form_cs(g, f)).search(texts[lang])]
        if seen:
            P.append(("error", "glossary.json", g.get("term", "?"), f"a priority-1 term shown in the interface ({', '.join(seen[:3])}) must be highlighted, or say why not in highlight_why"))
    return P


def load_groups():
    """Longer area text and group descriptions for the dictionary page (dictionary_src/groups.json, keyed by domain id)."""
    p = SRC / "groups.json"
    g = load_json(p) if p.exists() else {}
    g.pop("_about", None)
    return g


def domain_order(reg):
    """Domain ids in display order: data domains first (parent, then its sub-domains), system entries last."""
    ds = reg["domains"]
    top = sorted([d for d in ds if d["parent"] is None], key=lambda d: (d["system"], d["order"]))
    out = []
    for d in top:
        out.append(d["id"])
        out += [c["id"] for c in sorted((x for x in ds if x["parent"] == d["id"]), key=lambda x: x["order"])]
    return out


def in_domain(e, dom):
    """True when the entry is tagged with the domain or one of its sub-domains (primary or secondary)."""
    return any(x == dom or x.startswith(dom + ".") for x in (e.get("domains") or [e.get("domain")]))


def merge(entries, base):
    merged = OrderedDict()
    for k, b in base.items():
        merged[k] = dict(b)
    for e in entries:
        k = e["id"]
        if k in merged:
            m = merged[k]
            for fld, val in e.items():
                if fld == "_file":
                    continue
                if fld in ("definition", "name", "unit", "geography") and not val:
                    continue
                if fld == "where" and isinstance(val, dict):
                    m["where"] = {**m.get("where", {}), **val}
                    m["where"]["files"] = sorted(set(m["where"].get("files", [])) | set(val.get("files", [])))
                    continue
                if fld == "coverage" and isinstance(val, dict):
                    m["coverage"] = {**m.get("coverage", {}), **val}
                    continue
                m[fld] = val
            m["_autofilled"] = False
            m["_file"] = e["_file"]
        else:
            e = dict(e)
            e["_autofilled"] = False
            merged[k] = e
    return merged


def coverage(merged, inv):
    claimed = {}
    for e in merged.values():
        for ref in (e.get("where") or {}).get("files", []) or []:
            fn, fld = ref.split(":", 1)
            claimed.setdefault(fn, set()).add(fld)
    missing = []
    for fn, fields in inv.items():
        got = claimed.get(fn, set())
        if "*" in got:
            continue
        for f in sorted(fields - {"*"}):
            if f not in got:
                missing.append(f"{fn}:{f}")
        if fields == {"*"} and not got:
            missing.append(f"{fn}:*")
    return missing


def build(write=True):
    sources, aliases = load_sources()
    inv = inventory()
    base = series_base()
    entries, problems = load_entries()
    merged = merge(entries, base)
    registry = contract.load_registry()
    reg_ids = contract.domains_by_id(registry)
    problems += validate([e for e in entries], sources, aliases, inv, set(merged), set(reg_ids))
    problems += contract.validate_registry(registry, set(merged), contract.accent_tokens())
    id_known = set(merged) | set(load_json(DATA / "dictionary.json").get("id_alias", {})) if (DATA / "dictionary.json").exists() else set(merged)
    problems += check_glossary(load_json(SRC / "glossary.json"), id_known)
    problems += check_glossary_ui(load_json(SRC / "glossary.json"))
    domains_info = load_groups()
    used_groups = {(e["domain"], e["group"]) for e in merged.values()}
    for d, info in domains_info.items():
        if d not in reg_ids:
            problems.append(("error", "groups.json", d, "not a domain id in domains.json"))
        for g in (info.get("groups") or {}):
            if (d, g) not in used_groups:
                problems.append(("warn", "groups.json", d, f"group '{g}' has a description but no entry uses it"))
    # series variables that no author has covered yet are still published (name, unit, source from the catalog) but flagged
    unauthored = [k for k, e in merged.items() if e.get("_autofilled")]
    miss = coverage(merged, inv)
    errors = [p for p in problems if p[0] == "error"]
    print(f"dictionary: {len(merged)} entries ({len(merged) - len(unauthored)} authored, {len(unauthored)} from catalogs only), {len(entries)} authored rows in {len(list((SRC / 'entries').glob('*.json')))} files")
    for sev, f, i, msg in problems:
        print(f"  {sev.upper():5s} {f}:{i}  {msg}")
    print(f"  {len(miss)} published fields without an entry" + (": " + ", ".join(miss[:12]) + (" ..." if len(miss) > 12 else "") if miss else ""))
    if not write:
        return merged, problems, miss
    # canonical sources with usage counts
    used = Counter()
    for e in merged.values():
        for sid in e.get("sources", []) or []:
            r = resolve(sid, sources, aliases)
            if r:
                used[r] += 1
    meta = load_json(DATA / "meta.json")
    # alias ids so that deep links from the Economy tab (economy.<housing key>) find the one entry
    id_alias = {}
    for k in load_json(DATA / "economy_series.json")["vars"]:
        if not k.get("years") and f"housing.{k['key']}" in merged:
            id_alias[f"economy.{k['key']}"] = f"housing.{k['key']}"
    # Spanish summaries (i18n_src/dictionary_plain.json, by entry id): used only while they translate the current English plain
    plain_es = load_json(PLAIN_ES) if PLAIN_ES.exists() else {}
    out_entries = []
    for k, e in merged.items():
        x = {a: b for a, b in e.items() if not a.startswith("_")}
        s = plain_es.get(k)
        if isinstance(s, dict) and s.get("es") and s.get("en") == x.get("plain"):
            x["plain_es"] = s["es"]
        x["sources"] = [resolve(s, sources, aliases) or s for s in x.get("sources", [])]
        x["sources"] = list(OrderedDict.fromkeys(x["sources"]))
        x["authored"] = not e.get("_autofilled")
        out_entries.append(x)
    es, _ = spanish(merged, sources, domains_info)
    domain_info = add_spanish(out_entries, sources, domains_info, es)
    order_ids = domain_order(registry)
    order = {d: n for n, d in enumerate(order_ids)}
    out_entries.sort(key=lambda x: (order.get(x["domain"], 99), x.get("group", ""), x["name"].lower()))
    glossary = published_glossary(load_json(SRC / "glossary.json"))
    for sid, s in sources.items():
        s["used_by"] = used.get(sid, 0)
    out = {
        "built": date.today().isoformat(), "snapshot": meta.get("label"), "snapshot_built": (meta.get("generated_at") or "")[:10],
        "domains": order_ids, "domain_registry": {d["id"]: d for d in registry["domains"]}, "legacy_domain_names": registry.get("legacy_names", {}),
        "kinds": KINDS, "entries": out_entries, "sources": sources, "aliases": {**aliases, **{}}, "id_alias": id_alias,
        "glossary": glossary, "domain_info": domain_info, "labels_es": es["labels"],
        "coverage": {"undocumented": miss, "unauthored": unauthored},
    }
    (DATA / "dictionary.json").write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"wrote dictionary.json {(DATA / 'dictionary.json').stat().st_size / 1024:.0f} KB")
    write_page_files(out)
    write_glossary_files(glossary)
    # a small file for pages that only need the size of the dictionary (the About tab)
    summary = {"built": out["built"], "entries": len(out_entries), "data_sources": sum(1 for x in sources.values() if x.get("kind") == "data"), "glossary_terms": len(glossary)}
    (DATA / "dictionary_summary.json").write_text(json.dumps(summary), encoding="utf-8")
    return merged, problems, miss


# ── The files the dictionary page reads (docs/performance.md) ─────────────────
# dictionary.json stays the whole dictionary, for anyone who downloads it and for catalog.py, contract.py and the tests. The page reads smaller files made
# from it: dictionary_list.json before it is ready (what the list, the filters, the search, the sources, the glossary and the files table need) and, the first
# time an entry is opened, printed or exported, the rest of the entries of its top-level domain (dictionary_detail_<domain>.json).
PAGE_LIST = "dictionary_list.json"
PAGE_TOP = ("built", "snapshot", "snapshot_built", "domains", "domain_registry", "legacy_domain_names", "id_alias", "glossary", "domain_info", "sources")
LIST_KEYS = ("id", "name", "domain", "domains", "group", "kind", "unit", "coverage", "sources", "has_moe")
DETAIL_KEYS = ("plain", "plain_es", "definition", "method", "how_to_read", "caveats", "values", "geography", "value_type", "added", "see_also", "source_detail")
SEARCH_KEYS = ("plain_es", "definition", "method", "geography", "source_detail", "how_to_read")   # with plain and caveats: the text the page's search reads that is now in the detail files
JS_SPACE = "\t\n\v\f\r                  　﻿"   # what \s matches in JavaScript
_JS_SPACES = re.compile("[" + JS_SPACE + "]+")
_SENTENCE = re.compile("(?<=[.!?])[" + JS_SPACE + "]")


def detail_file(domain):
    return f"dictionary_detail_{domain.split('.')[0]}.json"


def is_page_file(name):
    return name in (PAGE_LIST, PAGE_LIST_ES, PAGE_WORDS) or (name.startswith("dictionary_detail_") and name.endswith(".json"))


def js_norm(s):
    """The page's norm() (common.js): accents removed, lower case."""
    return re.sub("[̀-ͯ]", "", unicodedata.normalize("NFD", s or "")).lower().strip(JS_SPACE)


def search_words(texts, known=()):
    """The words of the texts as the page's search sees them (js_norm, cut at white space), sorted, without a word that is part of a longer one or of a word in `known`.
    The search keeps an entry when each word typed is part of its text. A word typed has no space, so it is part of the text exactly when it is part of one of these
    words: the page finds what it found when it read the whole text (tests/dictionary_page.test.js checks this on every entry)."""
    words = {w for t in texts for w in _JS_SPACES.split(js_norm(t)) if w}
    kept, seen = [], "\x00".join(known)
    for w in sorted(words, key=lambda x: (-len(x), x)):
        if w not in seen:
            kept.append(w)
            seen += "\x00" + w
    return " ".join(sorted(kept))


def first_sentence(s):
    """The first sentence of a summary as the list shows it (dictionary.js): up to the first white space after . ! or ?"""
    return _SENTENCE.split(s or "", maxsplit=1)[0]


def page_files(out):
    """{file name: content} of the files the dictionary page reads, made from the content of dictionary.json: the list and the detail files (both languages read them), and
    the Spanish of dictionary_src/es/ in files of its own that only the Spanish page reads (spanish_page_files)."""
    entries, details, words = [], {}, {}
    for e in out["entries"]:
        x = {k: e[k] for k in LIST_KEYS if k in e}
        x["where"] = {"files": (e.get("where") or {}).get("files", [])}
        x["one"] = first_sentence(e.get("plain") or e.get("definition") or "")   # the first sentence the list shows
        if e.get("plain_es"):
            x["one_es"] = first_sentence(e["plain_es"])
        x["wp"] = search_words([e.get("plain")])   # the words of the English summary: the search ranks an entry higher when they hold a word typed
        known = _JS_SPACES.split(js_norm(" ".join([e["id"], e["name"], e.get("group") or "", e.get("unit") or "", x["wp"]])))
        words[e["id"]] = search_words([e.get(k) for k in SEARCH_KEYS] + list(e.get("caveats") or []), known)   # the other words the search reads: dictionary_words.json
        entries.append(x)
        d = {k: e[k] for k in DETAIL_KEYS if k in e}
        if (e.get("where") or {}).get("view"):
            d["view"] = e["where"]["view"]
        details.setdefault(detail_file(e["domain"]), {})[e["id"]] = d
    lst = {k: out[k] for k in PAGE_TOP if k in out}
    lst["sources"] = {sid: {k: v for k, v in s.items() if k not in ES_SOURCE_KEYS} for sid, s in out["sources"].items()}
    lst["domain_info"] = {d: {k: v for k, v in i.items() if k not in ES_DOMAIN_KEYS} for d, i in out["domain_info"].items()}
    lst["detail_files"] = sorted(details)
    lst["entries"] = entries
    return {PAGE_LIST: lst, PAGE_WORDS: {"built": out["built"], "w": words}, **{f: {"entries": details[f]} for f in sorted(details)},
            **spanish_page_files(out, entries, sorted(details), words)}


# The words of the definition, method, geography, source notes, how to read it and cautions of every entry, which only the search reads, are in a file of their own that
# the page fetches right after it is ready ('later' in routes.json): they were 330 of the 750 KB (compressed) the list file made the page load first (docs/performance.md).
PAGE_WORDS = "dictionary_words.json"


# The Spanish page reads two more kinds of file, which the English page never fetches (docs/performance.md): dictionary_list_es.json right after the page is ready
# ('later' in routes.json; the page shows the English until it is in), and dictionary_detail_<domain>_es.json with the detail file of the same domain ('on_use').
PAGE_LIST_ES = "dictionary_list_es.json"
ES_SOURCE_KEYS = tuple(f + "_es" for f in ("access", "cadence", "used_for", "terms_note"))
ES_DOMAIN_KEYS = ("summary_es", "groups_es")


def es_detail_file(name):
    return name[:-len(".json")] + "_es.json"


def spanish_page_files(out, list_entries, detail_names, list_words):
    """{file name: content} of the Spanish page's own files: dictionary_list_es.json {"built", "names", "held", "labels", "sources", "domain_info", "w"} and, for each detail
    file, its Spanish {"entries": {id: {"how_to_read_es"}}} (written for every domain, empty or not, so the page knows its name)."""
    by_list = {x["id"]: x for x in list_entries}
    names, w, held, details = {}, {}, [], {f: {} for f in detail_names}
    for e in out["entries"]:
        if e.get("hold_es"):
            held.append(e["id"])
        if e.get("name_es"):
            names[e["id"]] = e["name_es"]
        if e.get("how_to_read_es"):
            details[detail_file(e["domain"])][e["id"]] = {"how_to_read_es": e["how_to_read_es"]}
            x = by_list[e["id"]]
            known = _JS_SPACES.split(js_norm(" ".join([e["id"], e["name"], e.get("name_es") or "", e.get("group") or "", e.get("unit") or "", x["wp"], list_words.get(e["id"], "")])))
            words = search_words([e["how_to_read_es"]], known)   # the words of the Spanish "how to read it" that the English list does not already hold
            if words:
                w[e["id"]] = words
    srcs = {sid: {k[:-3]: s[k] for k in ES_SOURCE_KEYS if s.get(k)} for sid, s in out["sources"].items()}
    dom = {d: {k[:-3]: i[k] for k in ES_DOMAIN_KEYS if i.get(k)} for d, i in out["domain_info"].items()}
    es_list = {"built": out["built"], "names": names, "held": held, "labels": out.get("labels_es") or {}, "sources": {k: v for k, v in srcs.items() if v},
               "domain_info": {k: v for k, v in dom.items() if v}, "w": w}
    return {PAGE_LIST_ES: es_list, **{es_detail_file(f): {"entries": details[f]} for f in detail_names}}


def write_page_files(out, data_dir=DATA):
    files = page_files(out)
    for old in data_dir.glob("dictionary_detail_*.json"):   # a domain that no longer has entries
        if old.name not in files:
            old.unlink()
    for name, j in files.items():
        (data_dir / name).write_text(json.dumps(j, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    n = sum(1 for k in files if k.startswith("dictionary_detail_") and not k.endswith("_es.json"))
    print(f"wrote {PAGE_LIST} {(data_dir / PAGE_LIST).stat().st_size / 1024:.0f} KB and {n} detail files for the dictionary page, and for the Spanish page "
          f"{PAGE_LIST_ES} {(data_dir / PAGE_LIST_ES).stat().st_size / 1024:.0f} KB and {n} Spanish detail files")


# ── Spanish of the dictionary (dictionary_src/es/ and its README) ─────────────
# Names, "how to read it", short labels, source cards and the area and group texts. The Spanish of the summaries is plain_es (i18n_src/dictionary_plain.json) and
# the glossary's is in dictionary_src/glossary.json. Each translated field keeps a fingerprint of the English it was translated from ("_en"): when the English
# changes, the old Spanish is left out (the page shows the English, marked lang="en") and reported as stale. Short labels (units, geographies, group names,
# update frequencies) are keyed by the English itself. The Spanish goes into dictionary.json next to the English (name_es, how_to_read_es, labels_es, the
# sources' access_es, cadence_es, used_for_es and terms_note_es, domain_info's summary_es and groups_es) and from there into the Spanish page's own files
# (spanish_page_files): names, labels, source cards and area texts in dictionary_list_es.json, "how to read it" in dictionary_detail_<domain>_es.json.
# What is held for Finance and Compliance review never reaches a published file: the entries, source cards, area texts and labels of
# dictionary_src/es/held_for_review.json, and the entries of i18n_src/held_for_review.json (dictionary_plain). A held entry is marked hold_es, and the page
# shows every label of it in English.
ES = SRC / "es"
ES_ENTRY_FIELDS = ("name", "how_to_read")
ES_SOURCE_FIELDS = ("access", "cadence", "used_for", "terms_note")
HELD_ES = ES / "held_for_review.json"
HELD_REVIEW = ROOT / "i18n_src" / "held_for_review.json"


def fingerprint(v):
    """8 hex characters of the English a translation was made from (a list is fingerprinted as its JSON)."""
    s = v if isinstance(v, str) else json.dumps(v, ensure_ascii=False, sort_keys=True)
    return hashlib.sha1(s.encode("utf-8")).hexdigest()[:8]


def _es_take(es_rec, en_rec, fields, where, stale):
    """The fields of one Spanish record whose fingerprint matches the current English."""
    out, fp = {}, es_rec.get("_en") or {}
    for f in fields:
        if f not in es_rec or f not in en_rec or en_rec[f] in (None, "", []):
            continue
        if fp.get(f) == fingerprint(en_rec[f]):
            out[f] = es_rec[f]
        else:
            stale.append(f"{where}.{f}")
    return out


def label_keys(e):
    """The English short labels of an entry that labels.json translates."""
    return [e.get("unit"), e.get("geography"), e.get("group"), (e.get("coverage") or {}).get("frequency")]


def es_holds():
    """What stays English, by what it belongs to: {"entries", "sources", "groups", "labels"} (sets of ids or English labels)."""
    h = load_json(HELD_ES) if HELD_ES.exists() else {}
    plain = (load_json(HELD_REVIEW).get("dictionary_plain") or {}) if HELD_REVIEW.exists() else {}
    return {"entries": set(plain) | set(h.get("entries") or {}), "sources": set(h.get("sources") or {}), "groups": set(h.get("groups") or {}), "labels": set(h.get("labels") or {})}


def spanish(merged, sources, domains_info, quiet=False):
    """The Spanish of dictionary_src/es/ that translates the current English and is not held, and the list of stale fields:
    ({"entries": {id: {field: es}}, "labels": {en: es}, "sources": {id: {field: es}}, "domain_info": {domain: {"summary": es, "groups": {group: es}}}, "held": {entry ids}}, stale)."""
    hold = es_holds()
    es = {"entries": {}, "labels": {}, "sources": {}, "domain_info": {}, "held": hold["entries"] & set(merged)}
    stale = []
    if not ES.exists():
        return es, stale
    for p in sorted((ES / "entries").glob("*.json")):
        for k, rec in load_json(p).items():
            if k not in merged:
                stale.append(f"entries.{k} (no such entry)")
            elif k not in hold["entries"] and (got := _es_take(rec, merged[k], ES_ENTRY_FIELDS, f"entries.{k}", stale)):
                es["entries"][k] = got
    open_labels = {x for k, e in merged.items() if k not in hold["entries"] for x in label_keys(e)}
    labels = load_json(ES / "labels.json") if (ES / "labels.json").exists() else {}
    es["labels"] = {en: t for en, t in labels.items() if t and en in open_labels and en not in hold["labels"]}
    es_src = load_json(ES / "sources.json") if (ES / "sources.json").exists() else {}
    es["sources"] = {sid: got for sid, rec in es_src.items() if sid in sources and sid not in hold["sources"] and (got := _es_take(rec, sources[sid], ES_SOURCE_FIELDS, f"sources.{sid}", stale))}
    es_dom = load_json(ES / "groups.json") if (ES / "groups.json").exists() else {}
    for d, rec in es_dom.items():
        if d in hold["groups"]:
            continue
        en = domains_info.get(d) or {}
        flat_en = {"summary": en.get("summary"), **{f"groups.{g}": t for g, t in (en.get("groups") or {}).items()}}
        flat_es = {**({"summary": rec["summary"]} if rec.get("summary") else {}), **{f"groups.{g}": t for g, t in (rec.get("groups") or {}).items()}, "_en": rec.get("_en") or {}}
        got = _es_take(flat_es, flat_en, list(flat_en), f"groups.{d}", stale)
        if got:
            es["domain_info"][d] = {"summary": got.get("summary"), "groups": {k[7:]: v for k, v in got.items() if k.startswith("groups.")}}
    if not quiet:
        n = sum(len(v) for v in es["entries"].values())
        print(f"spanish: names or how to read of {len(es['entries'])} of {len(merged)} entries ({n} fields), {len(es['labels'])} labels, {len(es['sources'])} source cards, "
              f"{len(es['domain_info'])} area texts; {len(es['held'])} entries held for review; {len(stale)} older than their English")
        for s in stale[:20]:
            print(f"  STALE {s}")
        if len(stale) > 20:
            print(f"  ... and {len(stale) - 20} more (python dictionary.py --es lists them all)")
    return es, stale


def add_spanish(out_entries, sources, domains_info, es):
    """Put the Spanish next to the English: the entries' name_es and how_to_read_es (and hold_es on a held entry) and the sources' <field>_es.
    Returns a copy of domains_info with summary_es and groups_es."""
    for x in out_entries:
        if x["id"] in es["held"]:
            x["hold_es"] = True
        for f, v in es["entries"].get(x["id"], {}).items():
            x[f + "_es"] = v
    for sid, got in es["sources"].items():
        for f, v in got.items():
            sources[sid][f + "_es"] = v
    info = {d: dict(i) for d, i in domains_info.items()}
    for d, got in es["domain_info"].items():
        if d in info:
            if got.get("summary"):
                info[d]["summary_es"] = got["summary"]
            if got.get("groups"):
                info[d]["groups_es"] = got["groups"]
    return info


def check_links():
    """Every where.view link must open something real: layer keys, shading keys, dataset keys, files, dictionary ids."""
    site = ROOT / "site"
    idx = (site / "index.html").read_text(encoding="utf-8")
    app = (site / "js" / "app.js").read_text(encoding="utf-8")
    layer_keys = set(re.findall(r"(\w+): '(?:ly\w+|walkRings)'", app))
    choro = set(re.findall(r"(\w+): \['\w+'", re.search(r"const SHADE_DS = \{(.*?)\};", app).group(1)))   # s= opens an old shading measure as its dataset (app.js SHADE_DS, decision 81 (d))
    econ = {v["key"] for f in ("economy_series.json", "health_series.json", "population_series.json", "commuting_series.json", "svi_series.json", "facility_exposure_series.json", "credit_series.json", "drought_series.json", "storm_recovery_series.json", "essentials_series.json", "cutoff_series.json", "jobs_reach_series.json", "netmig_age_series.json", "degrees_series.json", "school_conditions_series.json", "proficiency_series.json", "providers_series.json", "education_series.json", "labor_sex_series.json", "medicare_series.json", "care_series.json", "infrastructure_series.json", "bridges_series.json", "traffic_series.json", "crashes_series.json", "environment_series.json", "hazard_series.json", "gateway_series.json", "facility_series.json", "community_series.json", "nonprofit_series.json", "conditions_series.json", "landslide_series.json", "heat_series.json", "vegetation_series.json", "buildings_series.json", "fires_series.json", "night_heat_series.json", "climb_series.json", "slope_series.json", "nightlights_series.json", "broadband_series.json", "energy_series.json", "wcrp_rvi_barrio.json") for v in load_json(DATA / f)["vars"]}   # the layers of the Economy tab: its own series, the health series and the Population domain's
    hous = {v["key"] for v in load_json(DATA / "housing_series.json")["vars"]}
    hous_pages = hous | {"home_value_change_pct", "gross_rent_change_pct", "income_change_pct", "bachelors_change_pts", "t6live", "table10", "table2study", "table6", "table7", "grapilive", "smocapilive"}   # housing.js: CHANGE variables and S.STATIC tables
    snap = {"tourism_places", "lodging_places", "gastronomy_places", "attractions_places", "visitor_services_places"}
    munis = set(load_json(DATA / "municipalities.json"))
    geoids = {str(f["properties"]["GEOID"])[:5] for f in load_json(DATA / "municipios.geojson")["features"]}
    wcrp_ids = set(re.findall(r'\sid="([^"]+)"', (site / "wcrp.html").read_text(encoding="utf-8")))
    dm_ids = set(re.findall(r'\sid="([^"]+)"', (site / "data-management.html").read_text(encoding="utf-8"))) if (site / "data-management.html").exists() else set()
    ra_ids = set(re.findall(r'\sid="([^"]+)"', (site / "route-analysis.html").read_text(encoding="utf-8"))) if (site / "route-analysis.html").exists() else set()
    gii_ids = set(re.findall(r'\sid="([^"]+)"', (site / "gii.html").read_text(encoding="utf-8"))) if (site / "gii.html").exists() else set()
    gii_ids |= {"i-" + r["code"].replace(".", "-") for r in load_json(DATA / "gii_profile.json")["indicators"]} if (DATA / "gii_profile.json").exists() else set()   # gii.js gives each indicator an id
    wl_ids = set(re.findall(r'\sid="([^"]+)"', (site / "women-labor.html").read_text(encoding="utf-8"))) if (site / "women-labor.html").exists() else None   # None until the page is built
    pm_ids = set(re.findall(r'\sid="([^"]+)"', (site / "public-money.html").read_text(encoding="utf-8"))) if (site / "public-money.html").exists() else None
    merged, _, _ = build(write=False)
    ids = set(merged) | set(load_json(DATA / "dictionary.json").get("id_alias", {})) if (DATA / "dictionary.json").exists() else set(merged)
    links = {e["id"]: [v["href"] for v in (e.get("where") or {}).get("view", []) or []] for e in merged.values()}
    for g in load_json(SRC / "glossary.json"):   # a glossary source on the observatory's own pages must open something real too
        u = (g.get("source") or {}).get("url") or ""
        if u.startswith(OBS_URL):
            links[f"glossary: {g['term']}"] = [u[len(OBS_URL):]]
    bad, n = [], 0
    for owner, hrefs in links.items():
        for h in hrefs:
            n += 1
            def no(msg):
                bad.append((owner, h, msg))
            if re.match(r"^https?://", h):
                continue
            page, _, rest = h.partition("#")
            page, _, query = page.partition("?")
            if page not in ("index.html", "3d.html", "housing.html", "wcrp.html", "route-analysis.html", "gii.html", "women-labor.html", "public-money.html", "public-spending.html", "unused-funds.html", "money-cycle.html", "reservoirs.html", "broadband.html", "opportunity-zones.html", "transit-links.html", "knowledge.html", "learn.html", "dictionary.html", "about.html", "profile.html", "data-management.html", ""):
                no("unknown page")
                continue
            if page == "data-management.html":   # the Data management page: a part of the page (#files, #growth, #withheld, #definitions)
                if rest and rest not in dm_ids:
                    no("no such part of the Data management page")
                continue
            if page == "route-analysis.html":   # the Route analysis page: a part of the page (#about, #exposure, #compare, #sources)
                if rest and rest not in ra_ids:
                    no("no such part of the Route analysis page")
                continue
            if page == "gii.html":   # the Global Innovation Index page: a part of the page (#about, #profile, #read, #sources) or one indicator (#i-1-1-2), which opens
                if rest and rest not in gii_ids:
                    no("no such part of the Global Innovation Index page")
                continue
            if page == "women-labor.html":   # the Women in the labor force page (Knowledge Area): a part of the page, checked once the page exists
                if rest and wl_ids is not None and rest not in wl_ids:
                    no("no such part of the Women in the labor force page")
                continue
            if page == "public-money.html":   # the Disaster funding and need page (Knowledge Area): #compare, #scatter, #placed, #mitigation, #hud, #method, #sources, or the page's state (#m=..&n=..)
                if rest and "=" not in rest and pm_ids is not None and rest not in pm_ids:
                    no("no such part of the Disaster funding and need page")
                continue
            if page == "wcrp.html":   # the WCRP page: #a= an area, v= a version, m= a municipio; or a part of the page (#vulnerability, #method), which opens if it is collapsed
                if rest and "=" not in rest:
                    if rest not in wcrp_ids:
                        no("no such part of the WCRP page")
                    continue
                q = dict(x.split("=", 1) for x in rest.split("&") if "=" in x)
                if q.get("a", "overall") not in ("overall", "econ", "edu", "envir", "health", "housing", "infra") or q.get("v", "orig") not in ("orig", "rebuild", "change") or (q.get("m") and unquote(q["m"]) not in munis):
                    no("unknown WCRP view")
                continue
            if page == "dictionary.html":
                if rest and rest not in ids and rest not in ("sources", "glossary", "files", "cite", "browse") and not rest.startswith(("src-", "g-")):
                    no("dictionary id not found")
                continue
            if page == "profile.html":   # an area profile: ?area= a municipio's five-digit code (plan item 12), or ?region= a region of geo/regions.json (regions.py)
                q = dict(x.split("=", 1) for x in query.split("&") if "=" in x)
                if "region" in q:
                    rp = DATA / "geo" / "regions.json"
                    if q["region"] not in ({r["id"] for r in load_json(rp)["regions"]} if rp.exists() else set()):
                        no(f"region '{q['region']}' is not in geo/regions.json")
                elif q.get("area") not in geoids:
                    no(f"area '{q.get('area')}' is not a municipio code")
                continue
            if page == "housing.html":
                q = dict(x.split("=", 1) for x in query.split("&") if "=" in x)
                if q.get("d") and q["d"] not in hous_pages:
                    no(f"housing dataset '{q['d']}' not found")
                continue
            for part in rest.split("&"):
                if not part:
                    continue
                if "=" not in part:
                    if unquote(part) not in munis:
                        no(f"municipality '{part}' not found")
                    continue
                k, val = part.split("=", 1)
                if page == "index.html" and k == "l":
                    for x in val.split(","):
                        if x and x not in layer_keys:
                            no(f"layer key '{x}' unknown")
                elif page == "index.html" and k == "s":
                    if val not in choro:
                        no(f"shading '{val}' unknown")
                elif page == "index.html" and k == "e":
                    for t in val.split("%2C") if "%2C" in val else val.split(","):
                        key = t.split(".")[0]
                        if key and key not in econ | hous | snap:
                            no(f"economy layer '{key}' unknown")
                elif page == "index.html" and k == "ix":   # a user-built composite: its inputs must be datasets of the Economy tab
                    f = unquote(val).split(",")
                    if f[0] not in ("z", "mm", "pct"):
                        no(f"composite scale '{f[0]}' unknown")
                    for x in f[1:]:
                        if x.split(":")[0] not in econ | hous | snap:
                            no(f"composite input '{x.split(':')[0]}' unknown")
                elif page == "index.html" and k == "pv":
                    if val not in ("hex2", "hex10", "hex50"):
                        no(f"places view '{val}' unknown")
                elif k not in ("c", "r", "slr", "ey", "eb", "y", "m", "d", "mode", "t"):
                    no(f"unknown parameter '{k}'")
    print(f"{n} view links checked: {len(bad)} problems")
    for i, h, m in bad:
        print(f"  {i}  {h}  -> {m}")
    return 1 if bad else 0


def dump(argv):
    """Read-only views for reviewers: --index lists id, area, group and name; --dump AREA prints the full entries of one area."""
    sources, aliases = load_sources()
    entries, _ = load_entries()
    merged = merge(entries, series_base())
    area = next((a for a in argv if a not in ("--dump", "--index")), None)
    if "--index" in argv:
        for e in merged.values():
            if not area or in_domain(e, area):
                print(f"{e['id']} | {', '.join(e.get('domains') or [e['domain']])} | {e['group']} | {e['name']} | {e.get('_file', '')}")
        return 0
    for e in merged.values():
        if area and not in_domain(e, area):
            continue
        print(f"=== {e['id']}  [{e.get('_file', '')}]  {', '.join(e.get('domains') or [e['domain']])} > {e['group']}  ({e['kind']}, {e['value_type']})")
        print(f"NAME: {e['name']}")
        print(f"PLAIN: {e.get('plain', '')}")
        print(f"DEFINITION: {e.get('definition', '')}")
        print(f"UNIT: {e.get('unit', '')}  GEOGRAPHY: {e.get('geography', '')}  COVERAGE: {json.dumps(e.get('coverage'), ensure_ascii=False)}")
        print(f"METHOD: {e.get('method', '')}")
        print(f"HOW TO READ: {e.get('how_to_read', '')}")
        for c in e.get("caveats", []) or []:
            print(f"CAVEAT: {c}")
        if e.get("values"):
            print(f"VALUES: {json.dumps(e['values'], ensure_ascii=False)}")
        print(f"SOURCES: {', '.join(resolve(x, sources, aliases) or x for x in e.get('sources', []))} | DETAIL: {e.get('source_detail', '')}")
        print(f"SEE ALSO: {', '.join(e.get('see_also', []) or [])} | FILES: {', '.join((e.get('where') or {}).get('files', []) or [])}")
    return 0


def write_domains_doc():
    """docs/domains.md: the current set of domains, generated from the registry so the documentation never hard-codes them."""
    reg = contract.load_registry()
    ds = contract.load_datasets()
    merged, _, _ = build(write=False)
    ents = list(merged.values())
    by = {d["id"]: d for d in reg["domains"]}
    lines = ["# Domains of the PR Data Observatory", "",
             "Generated by `python dictionary.py --domains` from `dictionary_src/domains.json`. Do not edit by hand: add or change a domain in the registry.", "",
             "A domain is a field of information (housing, education and so on). The set is open and grows as data are added. "
             "A dataset belongs to one primary domain and may carry secondary ones. Rules and the placement guide: [adding-data.md](adding-data.md).", "",
             "**Where visitors meet them (navigation plan, HANDOFF decision 81).** On the 2D map each top-level domain is a topic of the Explore tab: a card with its "
             "headline figure, and a page with its ready-made views, its datasets by area, its points, lines and areas, what is also in it, and FPR's analyses on it. "
             "The layer menu of the 2D map and the 3D view, and the dataset menus (Tools › Analysis, Rankings, the 3D columns), list their groups in the same order. "
             "A dataset's primary domain is its home topic; its other domains list it under \"Also in this topic\". The system domains are not topics.", "",
             "| Domain | Id | Status | Entries (primary) | Entries (any tag, with sub-domains) | Files (any tag, with sub-domains) |", "|---|---|---|---:|---:|---:|"]
    for did in domain_order(reg):
        d = by[did]
        indent = "&nbsp;&nbsp;&nbsp;" if d["parent"] else ""
        n1 = sum(1 for e in ents if e["domain"] == did)
        n2 = sum(1 for e in ents if in_domain(e, did))
        f2 = sum(1 for r in ds["datasets"] if in_domain(r, did))
        lines.append(f"| {indent}{d['name']['en']} / {d['name']['es']} | `{did}` | {d['status']}{' (system)' if d['system'] else ''} | {n1} | {n2} | {f2} |")
    lines += ["", "## Descriptions", ""]
    for did in domain_order(reg):
        d = by[did]
        lines += [f"### {d['name']['en']} / {d['name']['es']} (`{did}`)", "", f"- EN: {d['description']['en']}", f"- ES: {d['description']['es']}",
                  f"- Icon: `{d['icon']}`; accent token: `{d['accent']}`; status: {d['status']}"]
        if d.get("headline"):
            lines.append(f"- Headline indicator: `{d['headline']['variable']}`")
        if d["examples"]["en"]:
            lines.append("- Example questions: " + "; ".join(f"\"{q}\"" for q in d["examples"]["en"]))
        if d.get("presets"):
            lines.append("- Ready-made views: " + "; ".join(p["name"]["en"] for p in d["presets"]))
        lines.append("")
    out = ROOT / "docs" / "domains.md"
    out.parent.mkdir(exist_ok=True)
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {out.relative_to(ROOT)}")
    return 0


def main(argv):
    if "--domains" in argv:
        return write_domains_doc()
    if "--dump" in argv or "--index" in argv:
        return dump(argv)
    if "--links" in argv:
        return check_links()
    if "--es" in argv:
        merged, _, _ = build(write=False)
        sources, _ = load_sources()
        _, stale = spanish(merged, sources, load_groups())
        for s in stale:
            print("  stale:", s)
        return 0
    if "--check" in argv:
        files = [a for a in argv if a != "--check"]
        sources, aliases = load_sources()
        inv = inventory()
        base = series_base()
        entries, problems = load_entries(files or None)
        all_entries, _ = load_entries()
        known = set(base) | {e.get("id") for e in all_entries}
        problems += validate(entries, sources, aliases, inv, known, set(contract.domains_by_id(contract.load_registry())))
        if not files:   # the whole dictionary: the glossary too (a term without a source or without both languages is an error)
            alias = set(load_json(DATA / "dictionary.json").get("id_alias", {})) if (DATA / "dictionary.json").exists() else set()
            problems += check_glossary(load_json(SRC / "glossary.json"), known | alias)
            problems += check_glossary_ui(load_json(SRC / "glossary.json"))
        for sev, f, i, msg in problems:
            print(f"{sev.upper():5s} {f}:{i}  {msg}")
        errs = sum(1 for p in problems if p[0] == "error")
        print(f"{len(entries)} entries{'' if files else ' and the glossary'} checked: {errs} errors, {len(problems) - errs} warnings")
        return 1 if errs else 0
    if "--coverage" in argv:
        merged, problems, miss = build(write=False)
        for m in miss:
            print("  undocumented:", m)
        print(f"{len(miss)} undocumented fields")
        return 1 if miss else 0
    merged, problems, miss = build()
    return 1 if any(p[0] == "error" for p in problems) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
