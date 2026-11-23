"""Domain registry and data contract: validation.

  python contract.py             check dictionary_src/domains.json and dictionary_src/datasets.json against the files in site/data/
  python contract.py --reviews   also list every open review (personal data, licence, compliance)

The build (build.py) runs this first and stops on any error. Rules and the checklist for adding data: docs/adding-data.md.

Registry (domains.json): every list of domains in the observatory is read from it. Contract (datasets.json): one record per published file.
"""
import json
import re
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).parent
SRC = ROOT / "dictionary_src"
DATA = ROOT / "site" / "data"
CSS = ROOT / "site" / "css" / "twin.css"

MB = 1048576
LEVELS = ["island", "region", "municipio", "barrio", "tract", "block-group", "block", "point", "line", "polygon", "raster", "network", "none"]
KEYED_LEVELS = {"region", "municipio", "barrio", "tract", "block-group"}      # these must name the field that holds the id
TIME_TYPES = ["point", "period", "window", "vintage", "snapshot", "event", "static"]
LICENCE_CLASSES = ["open", "open-with-conditions", "own", "unstated", "licensed-not-open"]
LICENCE_RANK = {"own": 0, "open": 0, "open-with-conditions": 1, "unstated": 2, "licensed-not-open": 3}
CADENCES = ["static", "snapshot", "annual", "monthly", "weekly", "daily", "live", "as-needed"]
TIERS = {"small": 1 * MB, "medium": 8 * MB, "large": 50 * MB}                 # raw bytes; GitHub refuses files over 100 MB
STATUSES = ["active", "partial", "planned"]
REVIEW_TYPES = ["pii", "licence", "compliance"]
REVIEW_STATUSES = ["open", "cleared"]
# Flags the Data management page shows in its Compliance review column (docs/data-management.md, section 4):
#   federal-grant  the file holds or describes federal grant money or a grant-funded program (HUD CDBG-DR, FEMA assistance, federal awards); it needs a compliance review
#   counts-only    the file counts sensitive items whose points or names are not published (private homes, care and treatment services, sites kept local)
FLAGS = ["federal-grant", "counts-only"]
AUTHORITY = ["authoritative", "secondary"]                                     # sources.json: is the source the publisher of record for its figures

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
ID_RE = re.compile(r"^[a-z][a-z0-9-]*(\.[a-z][a-z0-9-]*)*$")
UNMATCHED_FAIL = 0.01                                                          # more than 1% of join keys without a match fails the build
JOIN_LEVELS = ("region", "municipio", "barrio", "tract", "block-group")        # the levels whose ids the crosswalk holds
SUBDIRS = ("geo",)                                                             # subfolders of site/data whose files are published (one level deep)

# Personal-data checks. Column names are matched exactly (so "owner_cost_burden_pct" is fine); values are matched by pattern.
PII_COLUMNS = {"address", "addr", "street", "website", "web", "email", "e_mail", "phone", "telephone", "tel", "fax", "ssn", "contact",
               "contact_name", "mayor", "contractor", "officer", "first_name", "last_name", "surname", "birth_date", "dob"}
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+\.[A-Za-z0-9.-]+")
PHONE_RE = re.compile(r"(?<!\d)(?:\+?1[ .-]?)?\(?\d{3}\)?[ .-]\d{3}[ .-]\d{4}(?!\d)")
SSN_RE = re.compile(r"(?<!\d)\d{3}-\d{2}-\d{4}(?!\d)")


def load_json(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def published_files(data_dir=DATA):
    """[(name, path)] for every published file, sorted by name: the files of site/data and of its subfolders in SUBDIRS ('geo/crosswalk.json')."""
    out = []
    for p in sorted(Path(data_dir).iterdir()):
        if p.is_file():
            out.append((p.name, p))
        elif p.is_dir() and p.name in SUBDIRS:
            out += [(f"{p.name}/{q.name}", q) for q in sorted(p.iterdir()) if q.is_file()]
    return sorted(out, key=lambda x: x[0])


def norm(s):
    return "".join(c for c in unicodedata.normalize("NFD", str(s).lower()) if unicodedata.category(c) != "Mn").strip()


def accent_tokens(css_path=CSS):
    if not Path(css_path).exists():
        return None
    return set(re.findall(r"(--fpr-[a-z]+)\s*:", Path(css_path).read_text(encoding="utf-8")))


# ── Registry ─────────────────────────────────────────────────────────────────

def load_registry(path=None):
    return load_json(path or SRC / "domains.json")


def domains_by_id(reg):
    return {d["id"]: d for d in reg.get("domains", [])}


def validate_registry(reg, entry_ids=None, tokens=None):
    """Problems as (severity, where, id, message). entry_ids: ids of dictionary entries (to check headline variables)."""
    P = []
    ds = reg.get("domains")
    if reg.get("version") != 1:
        P.append(("error", "domains.json", "-", "version must be 1"))
    if not isinstance(ds, list) or not ds:
        P.append(("error", "domains.json", "-", "'domains' must be a non-empty list"))
        return P
    seen, names = {}, {}
    ids = {d.get("id") for d in ds if isinstance(d, dict)}
    for d in ds:
        i = d.get("id", "?")

        def err(msg, sev="error"):
            P.append((sev, "domains.json", i, msg))
        if not isinstance(i, str) or not ID_RE.match(i):
            err("id must be lowercase letters, digits and hyphens, with dots for sub-domains (housing, economy.visitor-economy)")
            continue
        if i in seen:
            err("duplicate id")
        seen[i] = d
        parent = d.get("parent")
        if "." in i:
            if parent != i.rsplit(".", 1)[0]:
                err(f"a sub-domain's parent must be the id before the last dot ('{i.rsplit('.', 1)[0]}'), not '{parent}'")
        elif parent is not None:
            err("a top-level domain must have parent null")
        if parent is not None and parent not in ids:
            err(f"parent '{parent}' does not exist")
        if not isinstance(d.get("order"), int):
            err("order must be a whole number")
        for fld in ("name", "description"):
            v = d.get(fld)
            if not isinstance(v, dict) or not all(isinstance(v.get(l), str) and v.get(l).strip() for l in ("es", "en")):
                err(f"{fld} needs non-empty 'es' and 'en' text")
            elif fld == "name":
                for l in ("es", "en"):
                    k = (l, norm(v[l]))
                    if k in names:
                        err(f"name.{l} '{v[l]}' is already used by {names[k]}")
                    names[k] = i
        if not (isinstance(d.get("icon"), str) and d["icon"].strip()):
            err("icon must name a Material Symbols icon")
        acc = d.get("accent")
        if not (isinstance(acc, str) and acc.startswith("--")):
            err("accent must be a CSS token such as --fpr-blue")
        elif tokens is not None and acc not in tokens:
            err(f"accent '{acc}' is not defined in site/css/twin.css")
        if d.get("status") not in STATUSES:
            err(f"status must be one of {STATUSES}")
        if not isinstance(d.get("system"), bool):
            err("system must be true or false")
        ex = d.get("examples")
        if not isinstance(ex, dict) or not all(isinstance(ex.get(l), list) and all(isinstance(x, str) and x for x in ex.get(l)) for l in ("es", "en")):
            err("examples needs 'es' and 'en' lists of questions (empty lists are fine for system entries)")
        elif not d.get("system") and (not ex["es"] or not ex["en"]):
            err("a data domain needs at least one example question in each language (they become the chat's starter questions)")
        elif len(ex["es"]) != len(ex["en"]):
            err("examples: the es and en lists must have the same length", "warn")
        h = d.get("headline")
        if h is not None:
            if not isinstance(h, dict) or not h.get("variable"):
                err("headline must be null or {variable, norm, label, island}")
            elif entry_ids is not None and h["variable"] not in entry_ids:
                err(f"headline variable '{h['variable']}' is not a dictionary entry")
            else:
                lab = h.get("label")
                if not (isinstance(lab, dict) and all(isinstance(lab.get(l), str) and lab[l].strip() for l in ("es", "en"))):
                    err("headline needs a short 'label' with 'es' and 'en' text (the overview card shows it)", "warn")
                isl = h.get("island")
                if isl is not None:
                    kinds = [k for k in ("sum", "ratio", "wmean") if k in isl] if isinstance(isl, dict) else []
                    if len(kinds) != 1:
                        err("headline.island must hold exactly one of 'sum' (a field), 'ratio' ({num, den, scale}) or 'wmean' ({field, weight})")
                    elif kinds[0] == "sum" and not isinstance(isl["sum"], str):
                        err("headline.island.sum must name a field of municipalities.json")
                    elif kinds[0] == "ratio" and not (isinstance(isl["ratio"], dict) and isinstance(isl["ratio"].get("num"), str) and isinstance(isl["ratio"].get("den"), str)):
                        err("headline.island.ratio needs 'num' and 'den' fields of municipalities.json")
                    elif kinds[0] == "wmean" and not (isinstance(isl["wmean"], dict) and isinstance(isl["wmean"].get("field"), str) and isinstance(isl["wmean"].get("weight"), str)):
                        err("headline.island.wmean needs 'field' and 'weight' fields of municipalities.json")
        elif not d.get("system") and d.get("status") == "active" and "." not in i and not any(x.get("parent") == i for x in ds):
            err("an active domain without sub-domains should name a headline indicator", "warn")
    for d in ds:
        if d.get("system") is False and d.get("parent") and seen.get(d["parent"], {}).get("system"):
            P.append(("error", "domains.json", d["id"], "a data domain cannot sit under a system domain"))
        if d.get("system") is True and d.get("parent") and not seen.get(d["parent"], {}).get("system", True):
            P.append(("error", "domains.json", d["id"], "a system domain cannot sit under a data domain"))
    orders = {}
    for d in ds:
        orders.setdefault((d.get("parent"), d.get("order")), []).append(d.get("id"))
    for (parent, order), v in orders.items():
        if len(v) > 1:
            P.append(("warn", "domains.json", ",".join(map(str, v)), f"same order ({order}) under the same parent"))
    legacy = reg.get("legacy_names", {})
    for name, target in legacy.items():
        if target not in ids:
            P.append(("error", "domains.json", name, f"legacy name points to '{target}', which is not a domain"))
    return P


# ── Dataset records ──────────────────────────────────────────────────────────

def load_datasets(path=None):
    return load_json(path or SRC / "datasets.json")


def walk_keys(x, depth=0, out=None, max_depth=3):
    """Column names: keys of dicts (records, GeoJSON properties) down to a few levels."""
    out = set() if out is None else out
    if depth > max_depth:
        return out
    if isinstance(x, dict):
        for k, v in x.items():
            out.add(str(k).lower())
            walk_keys(v, depth + 1, out, max_depth)
    elif isinstance(x, list):
        for v in x[:200]:
            walk_keys(v, depth + 1, out, max_depth)
    return out


def walk_strings(x):
    if isinstance(x, str):
        yield x
    elif isinstance(x, dict):
        for v in x.values():
            yield from walk_strings(v)
    elif isinstance(x, list):
        for v in x:
            yield from walk_strings(v)


def records(data):
    """The list of record dicts in a data file (a list, a GeoJSON feature list's properties, or a dict of records)."""
    if isinstance(data, dict) and data.get("type") == "FeatureCollection":
        return [f.get("properties") or {} for f in data.get("features", [])]
    if isinstance(data, list):
        return [r for r in data if isinstance(r, dict)]
    if isinstance(data, dict):
        return [r for r in data.values() if isinstance(r, dict)]
    return []


def extract_keys(data, key):
    """Join keys named by geography.key: 'object-keys', 'field:NAME' (records or GeoJSON properties), 'rows:ROWS:FIELDS:COLUMN' (a table: the list ROWS
    of rows whose column names are the list FIELDS, opportunity_zones.json) or a dotted path to a list ('geo.ids')."""
    if key == "object-keys":
        return list(data.keys()) if isinstance(data, dict) else []
    if key.startswith("rows:"):
        rk, fk, col = key[5:].split(":")
        cols, rows = (data.get(fk), data.get(rk)) if isinstance(data, dict) else (None, None)
        if not isinstance(cols, list) or col not in cols or not isinstance(rows, list):
            return []
        j = cols.index(col)
        return [str(r[j]) for r in rows if isinstance(r, list) and len(r) > j and r[j] is not None]
    if key.startswith("field:"):
        f = key[6:]
        return [r[f] for r in records(data) if f in r and r[f] is not None]
    cur = data
    for part in key.split("."):
        cur = cur.get(part) if isinstance(cur, dict) else None
    return [str(x) for x in cur] if isinstance(cur, list) else []


def observed_years(data, years_path):
    if not years_path:
        return None
    if years_path.startswith("list:"):
        f = years_path[5:]
        ys = [r[f] for r in records(data) if isinstance(r.get(f), int)]
    else:
        cur = data
        for part in years_path.split("."):
            cur = cur.get(part) if isinstance(cur, dict) else None
        ys = [y for y in cur if isinstance(y, int)] if isinstance(cur, list) else []
    return (min(ys), max(ys)) if ys else None


def crosswalk(data_dir):
    """What the id joins resolve against: the units of site/data/geo/crosswalk.json (built by geo.py), plus the municipio names (several files key municipios by name).
    Where the crosswalk has not been built, the 78 municipios and 901 barrios the observatory holds."""
    p = Path(data_dir) / "geo" / "crosswalk.json"
    if not p.exists():
        return crosswalk_lite(data_dir)
    cw = load_json(p)
    out = {lv: {r[0] for r in rows} for lv, rows in cw["units"].items()}
    for r in cw["units"]["municipio"]:
        out["municipio"].update({r[2], norm(r[2])})
    return out


def crosswalk_lite(data_dir):
    """The stand-in used before the crosswalk exists: the 78 municipios and 901 barrios the observatory already holds."""
    out = {"municipio": set(), "barrio": set(), "island": {"72"}}
    p = data_dir / "municipios.geojson"
    if p.exists():
        for r in records(load_json(p)):
            out["municipio"].update({str(r.get("GEOID")), norm(r.get("municipality", "")), r.get("municipality", "")})
    p = data_dir / "barrios.geojson"
    if p.exists():
        for r in records(load_json(p)):
            out["barrio"].add(str(r.get("geoid")))
    out["municipio"].discard("")
    return out


def validate_datasets(ds, reg, sources, aliases, data_dir=DATA, scan=True):
    """Check the contract. Returns (problems, open_reviews)."""
    P, reviews = [], []
    domains = domains_by_id(reg)
    records_ = ds.get("datasets", [])
    if ds.get("version") != 1:
        P.append(("error", "datasets.json", "-", "version must be 1"))
    cw = crosswalk(data_dir) if scan else {**{lv: set() for lv in JOIN_LEVELS}, "island": {"72"}}
    ids, files = {}, {}
    for r in records_:
        i = r.get("id", "?")

        def err(msg, sev="error"):
            P.append((sev, "datasets.json", i, msg))
        if not isinstance(i, str) or not re.match(r"^[a-z][a-z0-9_]*$", i):
            err("id must be lowercase letters, digits and underscores")
        if i in ids:
            err("duplicate id")
        ids[i] = r
        f = r.get("file")
        if not f:
            err("file is required")
            continue
        if f in files:
            err(f"file '{f}' already has a record ({files[f]})")
        files[f] = i
        path = data_dir / f
        if not path.exists():
            err(f"file '{f}' is not in site/data/")
            continue
        for l in ("en", "es"):
            if not (isinstance(r.get("title"), dict) and r["title"].get(l)):
                err(f"title needs '{l}' text")
        # domains
        dl = r.get("domains")
        if not (isinstance(dl, list) and dl and all(isinstance(x, str) for x in dl)):
            err("domains must be a non-empty list (primary domain first)")
        else:
            for x in dl:
                if x not in domains:
                    err(f"domain '{x}' is not in the registry")
            if len(set(dl)) != len(dl):
                err("domains lists a domain twice")
            if all(x in domains for x in dl):
                if domains[dl[0]].get("system") and not r.get("generated") and dl[0] not in ("system.docs", "system.tools", "system.geography"):
                    err("a system domain cannot be the primary domain of a data file")
        # geography
        g = r.get("geography") or {}
        lvl = g.get("level")
        if lvl not in LEVELS:
            err(f"geography.level '{lvl}' is not one of {LEVELS}")
        elif lvl in KEYED_LEVELS and not g.get("key"):
            err(f"geography.key is required for level '{lvl}'")
        elif lvl == "block" and not g.get("key") and not g.get("ids_not_published"):
            err("a block-level file needs geography.key (the 15-digit block id), or geography.ids_not_published: true when the ids are kept out of the file on purpose (say why in note)", "warn")
        if g.get("joins_to") and g["joins_to"] not in JOIN_LEVELS:
            err(f"geography.joins_to must be one of {list(JOIN_LEVELS)}")
        # time
        t = r.get("time") or {}
        if t.get("type") not in TIME_TYPES:
            err(f"time.type '{t.get('type')}' is not one of {TIME_TYPES}")
        if t.get("type") in ("period", "window", "vintage", "event") and not t.get("years_path"):
            err(f"time.type '{t.get('type')}' needs time.years_path so the years can be checked against the file", "warn")
        # sources and licence
        sl = r.get("sources")
        worst = 0
        if not (isinstance(sl, list) and sl):
            err("sources must be a non-empty list of ids from sources.json")
        else:
            for sid in sl:
                rid = sid if sid in sources else aliases.get(sid)
                if rid is None or rid not in sources:
                    err(f"unknown source id '{sid}'")
                    continue
                c = sources[rid].get("licence_class")
                if c not in LICENCE_RANK:
                    err(f"source '{rid}' has no valid licence_class in sources.json")
                else:
                    worst = max(worst, LICENCE_RANK[c])
        lc = r.get("licence_class")
        if lc not in LICENCE_CLASSES:
            err(f"licence_class '{lc}' is not one of {LICENCE_CLASSES}")
        elif LICENCE_RANK[lc] < worst:
            err(f"licence_class '{lc}' is less restrictive than the sources it uses; set it to at least '{[k for k, v in LICENCE_RANK.items() if v == worst][-1]}'")
        if r.get("cadence") not in CADENCES:
            err(f"cadence '{r.get('cadence')}' is not one of {CADENCES}")
        if not re.match(r"^\d{4}-\d{2}$", str(r.get("published", ""))):
            err("published must be YYYY-MM")
        # reviews
        revs = r.get("review") or []
        open_types = set()
        for rv in revs:
            if not isinstance(rv, dict) or rv.get("type") not in REVIEW_TYPES or rv.get("status") not in REVIEW_STATUSES or not rv.get("note"):
                err(f"review entries need type {REVIEW_TYPES}, status {REVIEW_STATUSES} and a note")
                continue
            if rv["status"] == "open":
                reviews.append((i, rv))
            open_types.add(rv["type"])
            # what the Data management page shows: a short reason for an open review, the date of a cleared one
            sm = rv.get("summary")
            if sm is not None and not (isinstance(sm, dict) and all(isinstance(sm.get(l), str) and sm[l].strip() for l in ("en", "es"))):
                err("review summary needs short 'en' and 'es' text (the Data management page shows it after 'Open:')")
            elif sm is None and rv["status"] == "open":
                err(f"the open {rv['type']} review has no summary: the Data management page shows only its type", "warn")
            if rv.get("date") is not None and not DATE_RE.match(str(rv["date"])):
                err("review date must be YYYY-MM-DD (the day it was cleared)")
            elif rv.get("date") is None and rv["status"] == "cleared":
                err(f"the cleared {rv['type']} review has no date: the Data management page shows 'Cleared' without one", "warn")
        if lc == "licensed-not-open" and not any(rv.get("type") == "licence" for rv in revs if isinstance(rv, dict)):
            err("a licensed-not-open dataset needs a 'licence' review entry stating what permission is needed")
        fl = r.get("flags")
        if fl is not None:
            if not (isinstance(fl, list) and all(x in FLAGS for x in fl) and len(set(fl)) == len(fl)):
                err(f"flags must be a list of distinct values from {FLAGS}")
            elif "federal-grant" in fl and not any(rv.get("type") == "compliance" for rv in revs if isinstance(rv, dict)):
                err("a file flagged federal-grant needs a 'compliance' review (Finance and Compliance review before external communication)")
        # size tier
        size = path.stat().st_size
        tier = r.get("tier")
        if tier not in TIERS:
            err(f"tier '{tier}' is not one of {list(TIERS)}")
        elif size > TIERS[tier]:
            err(f"{f} is {size / MB:.1f} MB, over the '{tier}' budget of {TIERS[tier] // MB} MB; raise the tier on purpose (and note why) or shrink the file")
        if not scan:
            continue
        # content checks (JSON and GeoJSON only)
        if path.suffix not in (".json", ".geojson") or size > 40 * MB:
            continue
        try:
            data = load_json(path)
        except ValueError as e:
            err(f"not valid JSON: {e}")
            continue
        if r.get("generated"):
            continue
        # join keys
        key = g.get("key")
        target = g.get("joins_to") or (lvl if lvl in JOIN_LEVELS else None)
        if key and target in JOIN_LEVELS and target in cw:
            ks = [str(k) for k in extract_keys(data, key)]
            if not ks:
                err(f"geography.key '{key}' finds no keys in {f}")
            else:
                valid = cw[target] | (cw["island"] if g.get("level") in ("municipio",) else set())
                miss = [k for k in ks if k not in valid and norm(k) not in valid]
                share = len(miss) / len(ks)              # share of rows, so one misspelt polygon among hundreds is a warning, not a failure
                if share > UNMATCHED_FAIL:
                    err(f"{share:.1%} of {len(ks):,} {target} keys do not resolve (for example {sorted(set(miss))[:3]})")
                elif miss:
                    err(f"{len(miss)} of {len(ks):,} {target} key(s) do not resolve: {sorted(set(miss))[:3]}", "warn")
        # years
        if t.get("years_path"):
            oy = observed_years(data, t["years_path"])
            if oy is None:
                err(f"time.years_path '{t['years_path']}' finds no years in {f}")
            else:
                if t.get("first") is not None and t["first"] != oy[0]:
                    err(f"time.first is {t['first']} but the file starts in {oy[0]}")
                if t.get("last") is not None and t["last"] != oy[1]:
                    err(f"time.last is {t['last']} but the file ends in {oy[1]}")
        # personal data
        cols = walk_keys(data)
        for rec_ in records(data):
            cols.update(str(k).lower() for k in rec_)
        hit_cols = sorted(cols & PII_COLUMNS)
        covered = {f_ for rv in revs if isinstance(rv, dict) and rv.get("type") == "pii" for f_ in rv.get("fields", [])}
        for c in hit_cols:
            if c not in covered:
                err(f"column '{c}' looks like personal or business contact data; remove it, or record a 'pii' review naming it (the project rule is never to publish business contact details)")
        if scan and path.stat().st_size <= 20 * MB:
            n_email = n_phone = n_ssn = 0
            for sx in walk_strings(data):
                if len(sx) > 400:
                    continue
                if "@" in sx and EMAIL_RE.search(sx):
                    n_email += 1
                if PHONE_RE.search(sx):
                    n_phone += 1
                if SSN_RE.search(sx):
                    n_ssn += 1
            for label, n in (("email address", n_email), ("phone number", n_phone), ("SSN-like number", n_ssn)):
                if n and not any(rv.get("type") == "pii" for rv in revs if isinstance(rv, dict)):
                    err(f"{n} value(s) look like a {label}; remove them, or record a 'pii' review")
    # every published file needs a record
    for name, p in published_files(data_dir):
        if name not in files:
            P.append(("error", "datasets.json", name, "published file has no contract record; add one to dictionary_src/datasets.json"))
    return P, reviews


def validate_sources(src):
    """The optional manifest fields of sources.json (HANDOFF decision 73): `authority` (authoritative or secondary) and `lineage` ({en}: where the
    figures come from and which other source reports the same dollars; a secondary source must say what it repeats)."""
    P = []
    for sid, r in src.items():
        if not isinstance(r, dict):
            continue
        a, lin = r.get("authority"), r.get("lineage")
        if a is not None and a not in AUTHORITY:
            P.append(("error", "sources.json", sid, f"authority '{a}' is not one of {AUTHORITY}"))
        if lin is not None and not (isinstance(lin, dict) and isinstance(lin.get("en"), str) and lin["en"].strip()):
            P.append(("error", "sources.json", sid, "lineage needs an 'en' text"))
        if a == "secondary" and not lin:
            P.append(("error", "sources.json", sid, "a secondary source needs a lineage note (what it repeats, and which source is authoritative)"))
    return P


def validate_all(data_dir=DATA, entry_ids=None, scan=True):
    reg = load_registry()
    ds = load_datasets()
    src = load_json(SRC / "sources.json")
    aliases = src.pop("_aliases", {})
    P = validate_registry(reg, entry_ids, accent_tokens()) + validate_sources(src)
    P2, reviews = validate_datasets(ds, reg, src, aliases, data_dir, scan)
    return P + P2, reviews


def report(problems, reviews, show_reviews=False):
    errs = [p for p in problems if p[0] == "error"]
    warns = [p for p in problems if p[0] != "error"]
    for sev, f, i, msg in problems:
        print(f"  {sev.upper():5s} {f}:{i}  {msg}")
    print(f"contract: {len(errs)} errors, {len(warns)} warnings, {len(reviews)} open reviews")
    if show_reviews or reviews:
        for i, rv in reviews:
            print(f"  REVIEW [{rv['type']}] {i}: {', '.join(rv.get('fields', []))} - {rv['note'][:200]}")
    return len(errs)


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    ids = None
    dj = DATA / "dictionary.json"
    if dj.exists():
        try:
            ids = {e["id"] for e in load_json(dj).get("entries", [])}
        except Exception:
            ids = None
    problems, reviews = validate_all(entry_ids=ids)
    n = report(problems, reviews, "--reviews" in argv)
    return n


if __name__ == "__main__":
    sys.exit(1 if main() else 0)
