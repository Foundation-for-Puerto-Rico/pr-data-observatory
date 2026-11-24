"""Builds site/data/catalog.json, what the map reads first, and the two files the map reads on first use: site/data/catalog_index.json, the index of the dictionary,
and site/data/catalog_es.json, the words of the Spanish summaries for the Catalog search of a Spanish page.

The neutral landing view needs the domains (from the registry) and one headline figure for each. It does not need the tourism listings (places.json), the series
files or any boundary beyond the municipalities. catalog.json is that small first read: the registry, a headline figure and trend for each domain, and the weight of
every published file (so the page can say what a module costs before it loads). The index of everything the dictionary documents, which lets a visitor find data and
put it on the map, is in catalog_index.json with the data sources behind it: the map fetches it the first time the Catalog tab, the chat or the Economy tab needs it
(docs/performance.md); the area profile fetches it with its first load. A Spanish page's Catalog tab also fetches catalog_es.json, so its search finds an entry by the
words of its Spanish summary (es_words).

  python catalog.py            write the three files (run python dictionary.py first: the index is made from site/data/dictionary.json)
  python catalog.py --check    exit 1 when the files on disk are not what the sources give (the weights and the build date are left out of the comparison)

The nightly transit refresh (refresh_network.py) calls apply(): it rewrites municipalities.json and operators.json, which feed a headline figure, so the catalog
is rebuilt there too, and only when something other than the file sizes changed (no nightly churn).

Nothing here is typed in by hand. A headline figure is read from the series files (the Puerto Rico row) or, for a snapshot field of municipalities.json, worked out
from the 78 municipal values by the rule written next to the headline in dictionary_src/domains.json ("island": a sum, a ratio of two sums or a weighted mean).
Adding a domain, a headline or a dataset needs no change in this file. Rules: docs/adding-data.md.
"""
import gzip
import json
import re
import sys
import unicodedata
from pathlib import Path

import contract

ROOT = Path(__file__).parent
SRC = ROOT / "dictionary_src"
DATA = ROOT / "site" / "data"
OUT = DATA / "catalog.json"
OUT_INDEX = DATA / "catalog_index.json"
OUT_ES = DATA / "catalog_es.json"
OUT_VIEWS = DATA / "catalog_views.json"
OUT_DOMAINS = DATA / "catalog_domains.json"   # the domain of each entry, from the index: all the area profile needs of it to group its tables before they draw (the index loads on first use)
PARTS = {OUT_INDEX: ("index", "sources"), OUT_ES: ("words_es",), OUT_VIEWS: ("presets",)}   # the parts of build() that go to the files read on first use; the rest is catalog.json
VERSION = 1
GZ_LEVEL = 6   # an estimate of what a server sends; GitHub Pages compresses on the fly

SERIES_FILES = {"housing_series.json": "housing", "economy_series.json": "economy", "health_series.json": "health", "population_series.json": "population", "commuting_series.json": "population", "svi_series.json": "hazards", "credit_series.json": "economy", "drought_series.json": "hazards", "storm_recovery_series.json": "hazards", "essentials_series.json": "communities", "cutoff_series.json": "hazards", "jobs_reach_series.json": "economy", "degrees_series.json": "education", "school_conditions_series.json": "education", "proficiency_series.json": "education", "providers_series.json": "health", "facility_exposure_series.json": "hazards", "education_series.json": "education", "medicare_series.json": "health", "care_series.json": "health", "infrastructure_series.json": "infrastructure", "bridges_series.json": "infrastructure", "traffic_series.json": "infrastructure", "crashes_series.json": "infrastructure", "environment_series.json": "environment", "hazard_series.json": "environment", "gateway_series.json": "infrastructure", "facility_series.json": "facilities", "community_series.json": "community", "nonprofit_series.json": "nonprofits", "conditions_series.json": "conditions", "landslide_series.json": "landslide", "heat_series.json": "heat", "vegetation_series.json": "vegetation", "buildings_series.json": "buildings", "fires_series.json": "fires", "night_heat_series.json": "night_heat", "climb_series.json": "climb", "slope_series.json": "slope", "nightlights_series.json": "nightlights", "broadband_series.json": "broadband", "energy_series.json": "energy", "wcrp_rvi_barrio.json": "wcrp", "labor_sex_series.json": "labor_sex"}


def load(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


# ── Headline figures ──────────────────────────────────────────────────────────

def island_fields(spec):
    """The municipal fields an island rule reads."""
    if "sum" in spec:
        return [spec["sum"]]
    if "ratio" in spec:
        return [spec["ratio"]["num"], spec["ratio"]["den"]]
    if "wmean" in spec:
        return [spec["wmean"]["field"], spec["wmean"]["weight"]]
    return []


def check_island(spec, muni, who):
    """A mistyped field would read as a zero on the card: stop the build instead."""
    fields = island_fields(spec)
    if not fields:
        raise SystemExit(f"catalog: the island rule of {who} has no sum, ratio or wmean")
    for f in fields:
        if not any(f.partition(".")[0] in r and (not f.partition(".")[2] or isinstance(r[f.partition(".")[0]], dict)) for r in muni.values()):
            raise SystemExit(f"catalog: the island rule of {who} reads '{f}', which no municipality has in municipalities.json")
    if spec.get("unit", "") not in ("", "$", "%"):
        raise SystemExit(f"catalog: the island rule of {who} has the unit '{spec['unit']}'; use '', '$' or '%'")
    if not (isinstance(spec.get("d", 0), int) and spec.get("d", 0) >= 0):
        raise SystemExit(f"catalog: the island rule of {who} needs 'd' (decimals) as a whole number of 0 or more")


def field_value(row, f):
    """A municipal field; "a.b" reads key b of the object a (missing = 0), and an object field (the areas of landuse_km2) reads as the sum of its values."""
    head, _, key = f.partition(".")
    v = row.get(head)
    if isinstance(v, dict):
        return v.get(key) or 0 if key else sum(x or 0 for x in v.values())
    return v


def island_value(spec, muni):
    """The Puerto Rico figure of a municipal snapshot field, by the rule in the registry: {"sum": f} | {"ratio": {num, den, scale}} | {"wmean": {field, weight}}.
    In a ratio, "a.b" reads key b of an object field and an object field reads as the sum of its values (landuse_km2.protected / landuse_km2)."""
    rows = list(muni.values())
    if "sum" in spec:
        return sum(r.get(spec["sum"]) or 0 for r in rows)
    if "ratio" in spec:
        r = spec["ratio"]
        den = sum(field_value(x, r["den"]) or 0 for x in rows)
        return sum(field_value(x, r["num"]) or 0 for x in rows) / den * r.get("scale", 1) if den else None
    if "wmean" in spec:
        w = spec["wmean"]
        pairs = [(x.get(w["field"]), x.get(w["weight"])) for x in rows if x.get(w["field"]) is not None and x.get(w["weight"])]
        tot = sum(b for _, b in pairs)
        return sum(a * b for a, b in pairs) / tot if tot else None
    return None


def period_of(entry, year):
    c = entry.get("coverage") or {}
    t = c.get("timeline")
    if t == "five-year window":
        return {"type": "window", "first": year - 4, "last": year}
    if t == "annual":
        return {"type": "year", "year": year}
    if t == "event-based":
        return {"type": "event", "year": year}
    if t == "snapshot":
        return {"type": "snapshot"}
    return {"type": t or "static", **({"year": year} if year else {})}


def series_of(entry):
    """(file, var) for an entry that describes a yearly series, from its where.files ('housing_series.json:median_gross_rent')."""
    for f in entry["where"].get("files", []):
        name, _, key = f.partition(":")
        if name in SERIES_FILES and key and key != "*":
            return name, key
    return None, None


def headline(dom, entries, muni, series_cache, snapshot):
    h = dom.get("headline")
    if not h:
        return None
    e = entries.get(h["variable"])
    out = {"variable": h["variable"], "name": e["name"] if e else None, "label": h.get("label"), "norm": h.get("norm", "value"), "scope": "Puerto Rico", "dict": h["variable"]}
    fname, key = series_of(e) if e else (None, None)
    if fname:
        if fname not in series_cache:
            series_cache[fname] = load(DATA / fname)
        data = series_cache[fname]
        v = next((x for x in data["vars"] if x["key"] == key), None)
        if v and v.get("from") == "housing":   # the economy file points at the Housing series for these
            if "housing_series.json" not in series_cache:
                series_cache["housing_series.json"] = load(DATA / "housing_series.json")
            v = next(x for x in series_cache["housing_series.json"]["vars"] if x["key"] == key)
        if not v:
            raise SystemExit(f"catalog: headline variable {h['variable']} points at {fname}:{key}, which has no such series")
        ys = sorted(int(y) for y in v["years"])
        pts = [(y, v["years"][str(y)][-1]) for y in ys if v["years"][str(y)][-1] is not None]   # the last element of every array is Puerto Rico
        if not pts:
            raise SystemExit(f"catalog: {h['variable']} has no Puerto Rico value")
        last = pts[-1]
        out.update({"kind": "series", "value": last[1], "year": last[0], "unit": v.get("unit", ""), "d": v.get("d", 0), "period": period_of(e, last[0]),
                    "series": [[y, x] for y, x in pts] if len(pts) > 1 else None, "map": ["econ", key, h.get("norm", "value")]})
        return out
    isl = h.get("island")
    if not isl:
        raise SystemExit(f"catalog: headline {h['variable']} of domain {dom['id']} is a snapshot field, so the registry needs an 'island' rule for it (docs/adding-data.md)")
    check_island(isl, muni, h["variable"])
    val = island_value(isl, muni)
    mfile = next((f.partition(":") for f in (e["where"].get("files", []) if e else []) if f.startswith("municipalities.json:")), None)
    out.update({"kind": "snapshot", "value": None if val is None else round(val, isl.get("d", 0)), "year": None, "unit": isl.get("unit", ""), "d": isl.get("d", 0), "period": {"type": "snapshot"}, "series": None,
                "island": isl, "map": (["econ", *shade_datasets()[mfile[2]]] if mfile and mfile[2] in shade_datasets() else None), "snapshot": snapshot})
    return out


# ── Index of the dictionary ───────────────────────────────────────────────────


def shade_datasets():
    """{old shading measure: [dataset key] or [dataset key, norm]} from site/js/app.js SHADE_DS: the retired "Shade municipalities by" menu (decision 81 (d)), each measure now a dataset."""
    app = (ROOT / "site" / "js" / "app.js").read_text(encoding="utf-8")
    body = re.search(r"const SHADE_DS = \{(.*?)\};", app).group(1)
    return {k: [x for x in (a, b) if x] for k, a, b in re.findall(r"(\w+): \['(\w+)'(?:, '(\w+)')?\]", body)}

def map_layers(by_id):
    """{dictionary entry id: layer keys} from dictionary_src/map_layers.json: the entries that are a layer of the map (the file explains why it is a list)."""
    p = SRC / "map_layers.json"
    layers = load(p)["layers"] if p.exists() else {}
    for i, keys in layers.items():
        if i not in by_id:
            raise SystemExit(f"catalog: dictionary_src/map_layers.json names '{i}', which is not a dictionary entry")
        if not re.fullmatch(r"[a-z]+(,[a-z]+)*", keys):
            raise SystemExit(f"catalog: dictionary_src/map_layers.json gives '{keys}' for {i}; use layer keys separated by commas")
    return layers


SHADE = None


def map_action(entry, series_keys, layers):
    """How an entry goes onto the map: a yearly series (or an exposure count) joins the layer stack, a field of municipalities.json that is a dataset (app.js SHADE_DS) joins it too, a listed layer is switched on.
    The page checks that it knows the target before it offers the button."""
    global SHADE
    SHADE = SHADE if SHADE is not None else shade_datasets()
    for f in entry["where"].get("files", []):
        name, _, key = f.partition(":")
        if name in SERIES_FILES and key in series_keys:
            return ["econ", key]
        if name == "municipalities.json" and key and key != "*" and entry["kind"] == "variable" and key in SHADE:   # a field the retired shading menu had: its dataset
            return ["econ", *SHADE[key]]
        m = re.match(r"exposure\.(pop|hu)_", entry["id"])
        if name == "exposure_municipio.json" and key and key != "*" and m:   # the exposure series: the first family of the entry, shaded as a share of the area's own residents or housing units
            return ["econ", f"exp_{key}_{m.group(1)}", "shareArea"]
    if entry["id"] in layers:
        return ["layers", layers[entry["id"]]]
    return None


def strictest(classes):
    rank = {"own": 0, "open": 0, "open-with-conditions": 1, "unstated": 2, "licensed-not-open": 3}
    cs = [c for c in classes if c in rank]
    return max(cs, key=lambda c: rank[c]) if cs else None


ES_STOP = {"de", "la", "el", "los", "las", "del", "por", "para", "con", "que", "una", "unos", "unas", "sus", "como", "mas", "son", "sin", "cada", "este", "esta", "estos", "estas",
           "entre", "sobre", "segun", "hasta", "desde", "cuando", "donde", "tambien", "les", "pero", "hay", "ese", "esa", "esos", "esas", "otro", "otra", "otros", "otras"}


def search_norm(s):
    """The page's norm() (site/js/common.js): accents off (NFD, then U+0300 to U+036F dropped), lower case, trimmed."""
    return "".join(c for c in unicodedata.normalize("NFD", s or "") if not 0x300 <= ord(c) <= 0x36F).lower().strip()


def es_words(text):
    """The words of an entry's Spanish summary (plain_es), for the Catalog search of a Spanish page: normalised as the page does, each once, in order, leaving out
    words of one or two letters and common little words. None when the entry has no Spanish summary."""
    words = [w for w in re.findall(r"[a-z0-9]+", search_norm(text)) if len(w) > 2 and w not in ES_STOP]
    return " ".join(dict.fromkeys(words)) or None


def build_index(entries, sources, recs, series_keys, layers):
    fields = ["id", "name", "domain", "domains", "levels", "years", "timeline", "sources", "licence", "map", "ask"]   # ask: the words people use to ask for it (the chat, plan item 14), or null. No "kind": no reader of the index used it (the dictionary page reads dictionary.json), and dropping it keeps the catalog inside its 200 KB
    rows = []
    for e in entries:
        levels = []
        for f in e["where"].get("files", []):
            r = recs.get(f.partition(":")[0])
            lv = r["geography"]["level"] if r else None
            if lv and lv != "none" and lv not in levels:
                levels.append(lv)
        c = e.get("coverage") or {}
        years = [c["first"], c["last"]] if c.get("first") and c.get("last") else None
        doms = e.get("domains") or [e["domain"]]
        rows.append([e["id"], e["name"], e["domain"], None if doms == [e["domain"]] else doms, levels, years, c.get("timeline"), e["sources"],   # domains: null when the entry has only its primary domain (keeps the file inside its 200 KB; catalog.js reads null as [domain])
                     strictest([(sources.get(s) or {}).get("licence_class") for s in e["sources"]]), map_action(e, series_keys, layers), e.get("ask")])
    return {"fields": fields, "rows": rows}


# ── Weights of the files, for the pages that say what a module costs ─────────

def weights():
    out = {}
    for name, p in contract.published_files(DATA):
        if name in (OUT.name, OUT_INDEX.name, OUT_ES.name, OUT_VIEWS.name, OUT_DOMAINS.name):   # the files written here: their own weight would always be one build late
            continue
        b = p.read_bytes().replace(b"\r\n", b"\n")
        out[name] = {"raw": len(b), "gz": len(gzip.compress(b, GZ_LEVEL, mtime=0))}
    return out


# ── Build ─────────────────────────────────────────────────────────────────────

def wanted_counts(domains):
    """How many wanted datasets (site/data/wanted.json) each domain has, by status; a parent counts its sub-domains."""
    p = DATA / "wanted.json"
    items = load(p)["items"] if p.exists() else []
    out = {d["id"]: {} for d in domains}
    for it in items:
        dom = it.get("domain")
        while dom:
            if dom in out:
                out[dom][it.get("status", "candidate")] = out[dom].get(it.get("status", "candidate"), 0) + 1
            dom = dom.rpartition(".")[0]
    return out


def knowledge_areas():
    """The published Knowledge Area pages with their home domain, from js/core/knowledge.js (navigation plan PR 3: each domain page links to its analyses)."""
    src = (ROOT / "site" / "js" / "core" / "knowledge.js").read_text(encoding="utf-8")
    out = []
    for m in re.finditer(r"\{ id: '(\w+)', label: \{ en: '((?:[^'\\]|\\.)*)', es: '((?:[^'\\]|\\.)*)' \}, icon: '(\w+)', page: '([\w.-]+)', status: '(\w+)'.*?domain: '([\w.-]+)'", src):
        if m.group(6) == "published":
            out.append({"id": m.group(1), "label": {"en": m.group(2), "es": m.group(3)}, "icon": m.group(4), "page": m.group(5), "domain": m.group(7)})
    return out


def view_sources(entries, series_keys, layers):
    """{('econ', dataset key) or ('layers', l= key): the source ids of the dictionary entries that put it on the map (a layer: each entry's main source)}, for the ready-made views."""
    out = {}
    for e in entries:
        a = map_action(e, series_keys, layers)
        if not a:
            continue
        for k in ([a[1]] if a[0] == "econ" else a[1].split(",")):
            got = out.setdefault((a[0], k), [])
            got += [x for x in (e["sources"] if a[0] == "econ" else e["sources"][:1]) if x not in got]   # a layer: the main source of its entry (its first), not the sources of the counts it carries
    return out


def presets(d, srcs, sources):
    """A domain's ready-made views (navigation plan PR 6, decision 81): as the registry has them, each with the ids of the data sources of what it shows (the page
    names them from catalog_index.json's sources; both files load before it draws a topic page).
    Every dataset must be one the map can show, every layer an l= key of app.js, at most two shaded layers (the Analysis tab's limit), one to four views."""
    keys = set(re.findall(r"(\w+): 'ly\w+'", re.search(r"const LAYER_KEYS = \{([^}]*)\}", (ROOT / "site" / "js" / "app.js").read_text(encoding="utf-8")).group(1)))
    ps = d["presets"]
    if not 1 <= len(ps) <= 4 or len({p["id"] for p in ps}) != len(ps):
        raise SystemExit(f"catalog: domain {d['id']} has {len(ps)} ready-made views (one to four, each id once)")
    out = []
    for p in ps:
        ramps = set(re.findall(r"^\s+(\w+): \[", (ROOT / "site" / "js" / "core" / "palettes.js").read_text(encoding="utf-8").split("const RAMPS = {")[1].split("};")[0], re.M))
        opt = lambda s: s[2] if len(s) > 2 else {}   # {norm, ramp}: the scale (checked against the engine in tests/presets.test.js) and the colour ramp (core/palettes.js RAMPS)
        bad = [s[0] for s in p["show"] if ("econ", s[0]) not in srcs or s[1] not in ("fill", "symbol") or not isinstance(opt(s), dict) or set(opt(s)) - {"norm", "ramp"} or opt(s).get("ramp", "blue") not in ramps] + [k for k in p["on"] if k not in keys]
        if bad or sum(s[1] == "fill" for s in p["show"]) > 2 or not (p["show"] or p["on"]) or not all(p["name"].get(l) and p["note"].get(l) for l in ("en", "es")):
            raise SystemExit(f"catalog: ready-made view {d['id']}.{p['id']}: unknown or misused {bad}, more than two shaded layers, nothing to show, or a name or note missing a language")
        ids = [x for s in p["show"] for x in srcs[("econ", s[0])]] + [x for k in p["on"] for x in srcs.get(("layers", k), [])]
        out.append({**{k: p[k] for k in ("id", "name", "note", "show", "on")}, "sources": list(dict.fromkeys(x for x in ids if x in sources and sources[x].get("kind") == "data"))})
    return out


def build(with_weights=True):
    reg = load(SRC / "domains.json")
    dj = load(DATA / "dictionary.json")
    meta = load(DATA / "meta.json")
    muni = load(DATA / "municipalities.json")
    recs = {r["file"]: r for r in load(SRC / "datasets.json")["datasets"]}
    entries = dj["entries"]
    by_id = {e["id"]: e for e in entries}
    series_keys = set()
    for fname in SERIES_FILES:
        series_keys |= {v["key"] for v in load(DATA / fname)["vars"]}
    wanted = wanted_counts(reg["domains"])
    cache = {}
    domains = []
    ka = knowledge_areas()
    srcs, views = view_sources(entries, series_keys, map_layers(by_id)), {}   # views: {domain id: its ready-made views}, read when a topic page opens (catalog_views.json)
    for d in reg["domains"]:
        n = sum(1 for e in entries if any(x == d["id"] or x.startswith(d["id"] + ".") for x in (e.get("domains") or [e["domain"]])))
        row = {k: d[k] for k in ("id", "parent", "order", "name", "description", "icon", "accent", "status", "system", "examples")}
        row["entries"] = n
        row["wanted"] = wanted.get(d["id"], {})
        row["headline"] = headline(d, by_id, muni, cache, meta["label"])
        row["knowledge"] = [{k: a[k] for k in ("label", "icon", "page")} for a in ka if a["domain"] == d["id"] or a["domain"].startswith(d["id"] + ".")]
        if d.get("presets"):
            views[d["id"]] = presets(d, srcs, dj["sources"])
        domains.append(row)
    out = {
        "version": VERSION,
        "built": meta["generated_at"],
        "snapshot": meta["label"],
        "domains": domains,
        "presets": views,
        "index": build_index(entries, dj["sources"], recs, series_keys, map_layers(by_id)),
        "words_es": {e["id"]: w for e in entries if (w := es_words(e.get("plain_es")))},   # {entry id: the words of its Spanish summary}, for catalog_es.json
    }
    used = {s for e in entries for s in e["sources"]}   # the data sources behind the index, for the catalog's Source filter
    out["sources"] = {sid: {"name": s["name"], "licence_class": s.get("licence_class")} for sid, s in dj["sources"].items() if sid in used and s.get("kind") == "data"}
    if with_weights:
        out["weights"] = weights()
    return out


def dumps(obj):
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))


def split(full):
    """{path: content} from what build() gives: each file read on first use takes its parts (PARTS) with the version and the build time; catalog.json the rest."""
    taken = {k for ks in PARTS.values() for k in ks}
    out = {OUT: {k: v for k, v in full.items() if k not in taken}}
    for path, ks in PARTS.items():
        out[path] = {"version": full["version"], "built": full["built"], **{k: full[k] for k in ks if k in full}}
    return out


def published():
    """The files on disk put back together as build() gives them, or None when one is missing."""
    if not all(p.exists() for p in (OUT, *PARTS)):
        return None
    full = load(OUT)
    for path, ks in PARTS.items():
        full.update({k: v for k, v in load(path).items() if k in ks})
    return full


def comparable(full):
    """What --check and apply() compare: everything but the build time and the weights."""
    return json.dumps({k: v for k, v in full.items() if k not in ("built", "weights")}, ensure_ascii=False, sort_keys=True)


def domains_doc(full):
    """{domain: [entry ids]} from the index, for the area profile's first view (catalog_domains.json)."""
    F = {f: i for i, f in enumerate(full["index"]["fields"])}
    by = {}
    for r in (full["index"]["rows"] if "id" in F and "domain" in F else []):
        by.setdefault(r[F["domain"]] or "", []).append(r[F["id"]])
    return {"version": full["version"], "built": full["built"], "domain_of": by}


def domains_current(full):
    """True when catalog_domains.json on disk says what the index gives (the build time left out)."""
    path = OUT.with_name(OUT_DOMAINS.name)   # beside catalog.json (the tests move it)
    if not path.exists():
        return False
    return load(path).get("domain_of") == domains_doc(full)["domain_of"]


def write(full):
    OUT.with_name(OUT_DOMAINS.name).write_text(dumps(domains_doc(full)), encoding="utf-8")
    for path, doc in reversed(list(split(full).items())):   # catalog.json last
        path.write_text(dumps(doc), encoding="utf-8")


def apply(log=print):
    """Rebuilds the catalog files when what they say has changed (the weights and the build time do not count), so the nightly refresh does not rewrite them
    every night."""
    want = build()
    have = published()
    if have is not None and comparable(have) == comparable(want) and domains_current(want):
        log("catalog.json: unchanged")
        return False
    write(want)
    log("catalog.json, catalog_index.json, catalog_es.json and catalog_views.json: rewritten (a headline figure or the dictionary changed)")
    return True


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if "--check" in argv:
        have = published()
        if have is None:
            print("a catalog file (catalog.json, catalog_index.json, catalog_es.json, catalog_views.json) is missing: run python catalog.py")
            return 1
        if comparable(have) != comparable(build(with_weights=False)) or not domains_current(have):
            print("the catalog files (catalog.json, catalog_index.json, catalog_es.json, catalog_views.json) are not what the sources give: run python catalog.py")
            return 1
        print("catalog.json, catalog_index.json, catalog_es.json and catalog_views.json are current")
        return 0
    out = build()
    write(out)
    kb = lambda p: f"{p.stat().st_size / 1024:.0f} KB ({len(gzip.compress(p.read_bytes(), GZ_LEVEL, mtime=0)) / 1024:.0f} KB gzip)"
    hl = [d for d in out["domains"] if d["headline"]]
    print(f"catalog.json: {len(out['domains'])} domains ({len(hl)} with a headline figure), {kb(OUT)}; catalog_index.json: {len(out['index']['rows'])} indexed entries, {kb(OUT_INDEX)}; "
          f"catalog_es.json: {len(out['words_es'])} Spanish summaries, {kb(OUT_ES)}; catalog_views.json: {sum(map(len, out['presets'].values()))} ready-made views, {kb(OUT_VIEWS)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
