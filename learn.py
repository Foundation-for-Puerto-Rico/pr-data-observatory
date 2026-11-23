"""The Learn registry and the figures the lessons quote (docs/learn.md, HANDOFF decision 106).

    python learn.py           check learn_src/lessons.json and write site/js/learn_items.js
    python learn.py --check   check it and exit 1 if the file is out of date (the tests and build.py run this)

Writes site/js/learn_items.js (window.LEARN, read by js/learn_page.js on learn.html): the parts, the built lessons with the names of their
map tools and layers in both languages, and every figure a lesson quotes. No lesson types a number: a figure is computed here from the
published data files (site/data), so the page says what the map shows.

The figures read only files that the local build writes (the registry's "inputs"), never a file an automated rebuild writes
(refresh/sources.json): a figure cannot go stale behind a bot's pull request. build.py runs this after it writes those files.
"""
import json
import math
import re
import statistics
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "learn_src" / "lessons.json"
SITE = ROOT / "site"
DATA = SITE / "data"
PAGE = SITE / "learn.html"
ITEMS_JS = SITE / "js" / "learn_items.js"
LINKS_JS = SITE / "js" / "learn_links.js"
LINKS_HEAD = "/* PR Data Observatory: which lesson of the Learn page teaches each map tool, layer and glossary term. Written by learn.py from learn_src/lessons.json: edit that file, then run python learn.py. */\n"
HELP_KEYS = {"rings": "walk", "prot": "protected"}   # a layer whose help button has another key than its l= key
HEAD = "/* PR Data Observatory: the Learn page's lessons and figures. Written by learn.py from learn_src/lessons.json and the published data files: edit that file, then run python learn.py. */\n"

STATUSES = ("built", "planned")
M_PER_DEG_LNG, M_PER_DEG_LAT = 111320, 110574   # metres per degree on the flat projection of the map's own tool (Core.study.ring in site/js/core/study.js)
MIN_CONFIDENCE = 0.5   # the map's own basis for tourism places: confidence 0.50 or more, places of worship left out (build.py; municipalities.json "assets")
WORSHIP = "Places of Worship"


def load_json(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def bilingual(v):
    return isinstance(v, dict) and all(isinstance(v.get(k), str) and v[k].strip() for k in ("en", "es"))


def metres(lat0, lng0, lat, lng):
    """Distance from (lat0, lng0) to a point, in metres, on the flat projection at lat0 that the map's Area around a point tool draws its ring on
    (Core.study.ring), so the tool gives the figures the lesson quotes. Good for the few kilometres a ring covers."""
    return math.hypot((lng - lng0) * M_PER_DEG_LNG * math.cos(math.radians(lat0)), (lat - lat0) * M_PER_DEG_LAT)


# ---- what the map itself calls its tools and layers ----
def map_tools(site=SITE):
    """{data-mt code: English label} of the map's Tools > Map tools pane."""
    html = (site / "index.html").read_text(encoding="utf-8")
    return dict(re.findall(r'<button type="button" class="mt-tool" data-mt="([^"]+)">(?:<span class="ms-icon"[^>]*>[^<]*</span>)?([^<]+)</button>', html))


def layer_keys(site=SITE):
    """The l= keys of the map's address (Core.viewstate LAYERS)."""
    js = (site / "js" / "core" / "viewstate.js").read_text(encoding="utf-8")
    return set(re.findall(r"(\w+): \{ '(?:2d|3d)':", js))


def spanish(root=ROOT):
    """Every English -> Spanish pair of the map's own scopes (the Spanish a tool's name already has)."""
    out = {}
    for scope in ("map", "studyareas", "terrain", "transit", "help"):
        f = root / "i18n_src" / "es" / f"{scope}.json"
        if f.exists():
            for k, v in load_json(f).items():
                if isinstance(v, str):
                    out.setdefault(k, v)
    return out


# ---- the rules ----
def problems(reg, glossary_ids, tools, layers, es, page_html):
    """Every rule the registry breaks, as text; an empty list when it is sound."""
    P = []
    parts = reg.get("parts") or []
    part_ids = [p.get("id") for p in parts]
    for p in parts:
        if not bilingual(p.get("name")):
            P.append(f"part {p.get('id')}: name needs English and Spanish")
        if not re.fullmatch(r"[A-Z]", str(p.get("letter") or "")):
            P.append(f"part {p.get('id')}: letter must be one capital letter")
    lessons = reg.get("lessons") or []
    for key in ("id", "code"):
        seen = [l.get(key) for l in lessons]
        for d in sorted({str(v) for v in seen if seen.count(v) > 1}):
            P.append(f"{d}: {key} used twice")
    letters = {p.get("id"): p.get("letter") for p in parts}
    for l in lessons:
        i = l.get("id") or "?"
        if not re.fullmatch(r"[a-z][a-z0-9]*", str(i)):
            P.append(f"{i}: id must be lower-case letters and digits")
        if l.get("part") not in part_ids:
            P.append(f"{i}: unknown part {l.get('part')}")
        elif not re.fullmatch(re.escape(letters[l["part"]]) + r"[1-9]", str(l.get("code") or "")):
            P.append(f"{i}: code {l.get('code')} does not start with its part's letter")
        if l.get("status") not in STATUSES:
            P.append(f"{i}: status must be one of {', '.join(STATUSES)}")
        for f in ("title", "term"):
            if not bilingual(l.get(f)):
                P.append(f"{i}: {f} needs English and Spanish")
        for t in l.get("tools") or []:
            if t not in tools:
                P.append(f"{i}: the map has no tool {t} (data-mt in site/index.html)")
            elif l.get("status") == "built" and tools[t] not in es:
                P.append(f"{i}: the tool \"{tools[t]}\" has no Spanish in the map's scopes")
        for k in l.get("layers") or []:
            if k not in layers:
                P.append(f"{i}: the map has no layer key {k} (site/js/core/viewstate.js)")
        for g in l.get("glossary") or []:
            if l.get("status") == "built" and g not in glossary_ids:
                P.append(f"{i}: no glossary term {g}")
    # the page and the registry say the same thing: a section and a card drawing for each built lesson, and none for the others
    built = {l["id"] for l in lessons if l.get("status") == "built" and l.get("id")}
    on_page = set(re.findall(r'<section class="block lesson" id="lesson-([a-z0-9]+)"', page_html))
    drawn = set(re.findall(r'<symbol id="lg-([a-z0-9]+)"', page_html))
    for i in sorted(built - on_page):
        P.append(f"{i}: built, but learn.html has no section id=\"lesson-{i}\"")
    for i in sorted(on_page - built):
        P.append(f"{i}: learn.html has a lesson section, but the registry does not say it is built")
    for i in sorted(built - drawn):
        P.append(f"{i}: built, but learn.html has no card drawing (symbol id=\"lg-{i}\")")
    return P


# ---- the figures ----
def basis(places):
    """The tourism places the map counts: confidence 0.50 or more, places of worship left out."""
    return [p for p in places if (p.get("confidence") or 0) >= MIN_CONFIDENCE and p.get("type") != WORSHIP]


def drawn(places):
    """The counted places that have a point: a holiday rental or a home is counted and never drawn (docs/places-privacy.md), so it has no coordinates here."""
    return [p for p in basis(places) if "lat" in p and "lng" in p]


def listed(places):
    """Every listing that has a point, at any confidence and with the places of worship: what the Area around a point tool counts as "Tourism places"
    in its summary (site/js/studyareas.js: not withheld, with coordinates). The lesson "What is near" counts the same, so the tool repeats its figures."""
    return [p for p in places if not p.get("withheld") and "lat" in p and "lng" in p]


def fig_shapes(data=DATA):
    places = load_json(data / "places.json")
    heat = load_json(data / "heat_surface.json")
    return {
        "points": len(drawn(places)),
        "counted": len(basis(places)),   # with the places that are counted and not drawn: what the municipios' counts add to
        "lines": len(load_json(data / "streams.geojson")["features"]),
        "barrios": len(load_json(data / "barrios.geojson")["features"]),
        "municipios": len(load_json(data / "municipios.geojson")["features"]),
        "cell_m": round(heat["pixel_m"]),
        "cells_across": heat["size"][0],
        "cells_down": heat["size"][1],
    }


def fig_near(spec, data=DATA):
    """Tourism places and residents within each distance of a public place, counted as the map's Area around a point tool counts them."""
    places = listed(load_json(data / "places.json"))
    centre = [p for p in places if p.get("name") == spec["place"] and p.get("municipality") == spec["municipality"]]
    if len(centre) != 1:
        raise ValueError(f"near: {len(centre)} places named {spec['place']!r} in {spec['municipality']} (one expected)")
    c = centre[0]
    blocks = load_json(data / "population_blocks.json")   # [lon, lat, residents, metres to the nearest scheduled stop]: the first three are read
    d_places = sorted(metres(c["lat"], c["lng"], p["lat"], p["lng"]) for p in places)   # the plaza is a listed place too: the tool counts it
    d_blocks = [(metres(c["lat"], c["lng"], b[1], b[0]), b[2]) for b in blocks]
    rings = []
    for r in spec["metres"]:
        rings.append({
            "m": r,
            "places": sum(1 for d in d_places if d <= r),
            "residents": sum(n for d, n in d_blocks if d <= r),
            "km2": round(math.pi * r * r / 1e6, 2),
        })
    return {"place": c["name"], "municipality": c["municipality"], "lat": round(c["lat"], 5), "lng": round(c["lng"], 5), "rings": rings}


def fig_rates(data=DATA):
    """Tourism places by municipio, as a count and per 1,000 residents (2020 Census)."""
    muni = load_json(data / "municipalities.json")
    rows = []
    for name, m in muni.items():
        rate = m["assets_per_1000_residents"]   # the published rate, so the lesson and the map show the same number
        if abs(rate - m["assets"] / m["population_2020"] * 1000) > 0.006:
            raise ValueError(f"rates: {name}: {rate} per 1,000 in municipalities.json, but {m['assets']} places and {m['population_2020']} residents")
        rows.append([name, m["assets"], m["population_2020"], rate])
    rows.sort(key=lambda r: r[0])
    by_count = sorted(rows, key=lambda r: (-r[1], r[0]))
    by_rate = sorted(rows, key=lambda r: (-r[3], r[0]))
    top_c, top_r = by_count[0], by_rate[0]
    return {
        "rows": rows,   # [municipio, tourism places, residents in 2020, places per 1,000 residents]
        "total": sum(r[1] for r in rows),
        "top_count": {"name": top_c[0], "count": top_c[1], "rate": top_c[3], "rank_by_rate": by_rate.index(top_c) + 1},
        "top_rate": {"name": top_r[0], "count": top_r[1], "rate": top_r[3], "residents": top_r[2], "rank_by_count": by_count.index(top_r) + 1},
    }


def fig_count(data=DATA):
    """Tourism places by barrio: how many, the total, the mean, the median and the largest (lesson B1)."""
    rows = [(f["properties"]["assets"], f["properties"]["barrio"], f["properties"]["municipality"]) for f in load_json(data / "barrios.geojson")["features"]]
    n = [r[0] for r in rows]
    top = max(rows)
    order = sorted(n)
    bins = [0, 1, 6, 11, 26, 51, 101, 501]   # the first value of each class of the lesson's chart; the last class is open
    hist = [sum(1 for v in n if lo <= v < hi) for lo, hi in zip(bins, bins[1:] + [float("inf")])]
    return {"barrios": len(n), "total": sum(n), "mean": round(statistics.mean(n), 1), "median": statistics.median(n), "none": sum(1 for v in n if v == 0),
            "max": top[0], "max_barrio": top[1], "max_municipio": top[2], "below_mean": sum(1 for v in n if v < statistics.mean(n)),
            "bins": bins, "hist": hist, "top_decile_share": round(sum(order[-len(n) // 10:]) / sum(n) * 100, 1)}


def fig_overlay(data=DATA):
    """Tourism places inside two other layers, as the build overlays them: FEMA's Special Flood Hazard Area and the protected areas (lesson B2)."""
    muni = load_json(data / "municipalities.json")
    total = sum(m["assets"] for m in muni.values())
    def layer(key):
        inside = sum(m[key] for m in muni.values())
        rows = sorted(([name, m[key], m["assets"], round(m[key] / m["assets"] * 100, 1)] for name, m in muni.items() if m["assets"]), key=lambda r: (-r[3], r[0]))
        return {"inside": inside, "pct": round(inside / total * 100, 1), "top": rows[:5], "none": sum(1 for r in rows if r[1] == 0)}
    return {"places": total, "flood": layer("in_sfha"), "protected": layer("in_protected")}


MOE_SHARE = 0.3   # Core.reliability.MOE_SHARE: a margin of error above 30% of the estimate makes it less reliable (tests/learn.test.js checks the two agree)


def unreliable(v, moe):
    """Core.reliability.isUnreliable: a margin of error above 30% of the estimate; an estimate of zero with any margin counts."""
    return v is not None and moe is not None and moe > 0 and (v == 0 or moe / abs(v) > MOE_SHARE)


def acs_barrios(data=DATA):
    """The barrios' survey file (acs_small.py): its newest five-year window, and each dataset's values and margins for that window."""
    a = load_json(data / "acs_barrio.json")
    y = str(max(int(k) for k in a["vars"][0]["years"]))
    return a, y, {v["key"]: v for v in a["vars"]}


def fig_attributes(data=DATA):
    """The table behind one barrio, the one with the most tourism places (lesson A2): what the map's layer holds for it, and what a join by its
    GEOID brings from the barrios' survey file."""
    feats = load_json(data / "barrios.geojson")["features"]
    p = max(feats, key=lambda f: (f["properties"]["assets"], f["properties"]["barrio"]))["properties"]
    a, y, V = acs_barrios(data)
    ids = a["geo"]["ids"]
    i = ids.index(p["geoid"])
    row = lambda k: [V[k]["years"][y][i], V[k]["moe"][y][i]]
    names = {}
    for f in feats:
        names[f["properties"]["barrio"]] = names.get(f["properties"]["barrio"], 0) + 1
    top_name = max(names.items(), key=lambda kv: (kv[1], [-ord(c) for c in kv[0]]))   # the most shared name; on a tie, the first in code-point order
    return {"barrio": p["barrio"], "municipality": p["municipality"], "geoid": p["geoid"], "km2": p["km2"], "assets": p["assets"], "sfha": p["sfha"],
            "lodging": p["lodging"], "per_km2": p["assets_per_km2"], "fields": len(p), "acs_fields": len(V), "window": a["notes"]["windows"][-1],
            "joined": len(set(ids) & {f["properties"]["geoid"] for f in feats}), "barrios": len(feats),
            "shared_names": sum(1 for v in names.values() if v > 1), "top_name": {"name": top_name[0], "n": top_name[1]},
            "residents": row("acs_population"), "income": row("median_hh_income"), "age": row("median_age")}


def fig_relations(own, data=DATA):
    """How the shapes fit together (lesson A3): barrios inside municipios, and the counted places the build placed in a barrio."""
    feats = load_json(data / "barrios.geojson")["features"]
    per = {}
    for f in feats:
        per[f["properties"]["municipality"]] = per.get(f["properties"]["municipality"], 0) + 1
    most = max(per.items(), key=lambda kv: (kv[1], kv[0]))
    ones = sorted(k for k, v in per.items() if v == 1)
    places = basis(load_json(data / "places.json"))
    return {"barrios": len(feats), "municipios": len(per), "most": {"name": most[0], "n": most[1]}, "one": ones,
            "places": len(places), "in_barrio": sum(1 for p in places if p.get("barrio")),
            "no_point_no_barrio": sum(1 for p in places if not p.get("barrio") and "lat" not in p), **own}


def fig_sure(data=DATA):
    """How sure a survey figure is, by the size of the area (lesson A6): the poverty rate of the municipios and of the barrios in the newest
    five-year window, and how many carry a margin of error above 30% of the estimate, the rule the map hatches (Core.reliability)."""
    h = load_json(data / "housing_series.json")
    y = str(h["latest"]["acs"])
    names = h["geo"]["names"][:-1]   # the last place is Puerto Rico as a whole
    pov = next(v for v in h["vars"] if v["key"] == "poverty_pct")
    mv, mm = pov["years"][y][:len(names)], pov["moe"][y][:len(names)]
    a, by, V = acs_barrios(data)
    if by != y:
        raise ValueError(f"sure: the municipios' newest survey year is {y}, the barrios' {by}")
    bv, bm = V["poverty_pct"]["years"][y], V["poverty_pct"]["moe"][y]
    iv, im = V["median_hh_income"]["years"][y], V["median_hh_income"]["moe"][y]
    pop = V["acs_population"]["years"][y]
    def level(vals, moes):
        n = sum(1 for v in vals if v is not None)
        bad = sum(1 for v, m in zip(vals, moes) if unreliable(v, m))
        return {"n": n, "flagged": bad, "pct": round(bad / n * 100, 1), "none": sum(1 for v in vals if v is None)}
    # two barrios with a published rate, to read the margin: the most populous, and the one at the tenth of the barrios with the fewest residents
    feats = load_json(data / "barrios.geojson")["features"]
    names_b = {f["properties"]["geoid"]: (f["properties"]["barrio"], f["properties"]["municipality"]) for f in feats}
    have = sorted((pop[i], a["geo"]["ids"][i], i) for i in range(len(pop)) if bv[i] is not None and pop[i])
    big, small = have[-1], have[len(have) // 10]
    ex = lambda t: {"barrio": names_b[t[1]][0], "municipality": names_b[t[1]][1], "residents": t[0], "rate": bv[t[2]], "moe": bm[t[2]]}
    return {"window": a["notes"]["windows"][-1], "year": int(y), "muni": level(mv, mm), "barrio": level(bv, bm), "income_barrio": level(iv, im),
            "big": ex(big), "small": ex(small)}


def fig_areasize(data=DATA):
    """The same survey figure at two sizes of area (lesson C1): the poverty rate of the newest window by municipio and by barrio, its range at
    each size, and the municipio whose barrios are furthest apart. Barrios count only where the margin of error is within 30% of the estimate,
    so a gap is not just the noise of a small sample."""
    h = load_json(data / "housing_series.json")
    y = str(h["latest"]["acs"])
    names = h["geo"]["names"][:-1]
    mv = dict(zip(names, next(v for v in h["vars"] if v["key"] == "poverty_pct")["years"][y][:len(names)]))
    a, by, V = acs_barrios(data)
    ok = [None if unreliable(v, m) else v for v, m in zip(V["poverty_pct"]["years"][y], V["poverty_pct"]["moe"][y])]   # only the estimates the map does not flag (lesson A6)
    bv = dict(zip(a["geo"]["ids"], ok))
    feats = load_json(data / "barrios.geojson")["features"]
    rows = [(f["properties"]["municipality"], f["properties"]["barrio"], bv.get(f["properties"]["geoid"])) for f in feats]
    rows = [r for r in rows if r[2] is not None]
    by_muni = {}
    for m, b, v in rows:
        by_muni.setdefault(m, []).append((v, b))
    spread = max(((max(l)[0] - min(l)[0], m, min(l), max(l)) for m, l in by_muni.items() if len(l) > 1), key=lambda t: (t[0], t[1]))
    m_lo, m_hi = min(v for v in mv.values() if v is not None), max(v for v in mv.values() if v is not None)
    return {"year": int(y), "window": a["notes"]["windows"][-1],
            "muni": {"n": sum(1 for v in mv.values() if v is not None), "lo": m_lo, "hi": m_hi},
            "barrio": {"n": len(rows), "lo": min(r[2] for r in rows), "hi": max(r[2] for r in rows),
                       "above": sum(1 for r in rows if r[2] > m_hi), "below": sum(1 for r in rows if r[2] < m_lo)},
            "spread": {"municipality": spread[1], "rate": mv[spread[1]], "low": {"barrio": spread[2][1], "rate": spread[2][0]}, "high": {"barrio": spread[3][1], "rate": spread[3][0]}, "barrios": len(by_muni[spread[1]])}}


def fig_leftout(data=DATA):
    """What the observatory counts and does not draw (lesson C3): the tourism listings withheld by the privacy rule (docs/places-privacy.md),
    by reason, and the barrios whose survey estimate is not published."""
    places = load_json(data / "places.json")
    w = [p for p in places if p.get("withheld")]
    reasons = {}
    for p in w:
        reasons[p["withheld"]] = reasons.get(p["withheld"], 0) + 1
    if any("lat" in p or "name" in p for p in w):
        raise ValueError("leftout: a withheld listing has a point or a name in places.json")
    b = basis(places)
    a, y, V = acs_barrios(data)
    return {"withheld": len(w), "reasons": dict(sorted(reasons.items(), key=lambda kv: (-kv[1], kv[0]))), "counted_not_drawn": sum(1 for p in b if "lat" not in p),
            "counted": len(b), "no_income": sum(1 for v in V["median_hh_income"]["years"][y] if v is None), "barrios": len(a["geo"]["ids"]), "window": a["notes"]["windows"][-1]}


def js_const(path, name):
    """A numeric constant of one of the map's scripts (`NAME = 200000` or `NAME = 20 * 1024 * 1024`), so a lesson quotes the tool's own limit."""
    m = re.search(rf"\b{name} = ([0-9 *]+)[,;]", path.read_text(encoding="utf-8"))
    if not m:
        raise ValueError(f"{path.name}: no constant {name}")
    v = 1
    for part in m.group(1).split("*"):
        v *= int(part.strip())
    return v


def fig_owndata(site=SITE):
    """What the tools that read a person's own file accept (lesson D1), read from their code: Count my points (studyareas.js) and Study areas (core/study.js)."""
    sa, st = site / "js" / "studyareas.js", site / "js" / "core" / "study.js"
    return {"max_points": js_const(sa, "MAX_PTS"), "max_mb": js_const(sa, "MAX_FILE") // (1024 * 1024), "min_shown": js_const(sa, "MIN_SHOWN"),
            "max_areas": js_const(st, "MAX_AREAS"), "areas_mb": js_const(st, "MAX_TEXT") // (1024 * 1024)}


def fig_qgis(attr, data=DATA):
    """The files a lesson opens in QGIS (lesson D2): the barrios and municipios layers as published, and the parts of a barrio's GEOID."""
    def layer(f):
        g = load_json(data / f)
        if "crs" in g:
            raise ValueError(f"qgis: {f} names a crs; the lesson says the files are in longitude and latitude (RFC 7946)")
        return {"file": f, "features": len(g["features"]), "kb": round((data / f).stat().st_size / 1024)}
    gid = attr["geoid"]
    return {"barrios": layer("barrios.geojson"), "municipios": layer("municipios.geojson"),
            "geoid": {"barrio": attr["barrio"], "municipality": attr["municipality"], "full": gid, "state": gid[:2], "county": gid[2:5], "subdivision": gid[5:]}}


def fig_own_code(spec, centre, data=DATA):
    """The figures the map's own code computes (learn_src/figures.js, run with Node): a walk from the plaza and the places in hexagons (lessons B4 and B6)."""
    cmd = ["node", str(ROOT / "learn_src" / "figures.js"), str(data.parent), str(centre["lng"]), str(centre["lat"]), ",".join(str(m) for m in spec["walk_minutes"])]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", timeout=600)
    except FileNotFoundError:
        raise ValueError("Node is needed to compute the walking and hexagon figures (learn_src/figures.js): it was not found")
    if r.returncode:
        raise ValueError("learn_src/figures.js failed: " + (r.stderr or r.stdout)[-400:])
    out = json.loads(r.stdout)
    blocks = load_json(data / "population_blocks.json")
    for w in out["walk"]:   # the ring of the same distance, measured as lesson B3 measures it, beside each walk
        w["ring_residents"] = sum(b[2] for b in blocks if metres(centre["lat"], centre["lng"], b[1], b[0]) <= w["m"])
        w["ring_km2"] = round(math.pi * w["m"] ** 2 / 1e6, 2)
    out["hex"]["half_pct_of_cells"] = round(out["hex"]["half_cells"] / out["hex"]["cells"] * 100, 1)
    out["hex"]["top10_pct"] = round(out["hex"]["top10"] / out["hex"]["places"] * 100, 1)
    return out


def figures(reg, data=DATA):
    spec = reg["figures"]
    out = {"shapes": fig_shapes(data), "near": fig_near(spec["near"], data), "rates": fig_rates(data), "count": fig_count(data), "overlay": fig_overlay(data)}
    own = fig_own_code(spec, out["near"], data)   # reads roads.bin, population_blocks.json and places.json: data / "roads.bin"
    out["walk"] = {"place": out["near"]["place"], "municipality": out["near"]["municipality"], "lat": out["near"]["lat"], "lng": out["near"]["lng"], "steps": own["walk"]}
    out["hex"] = own["hex"]
    out["attributes"] = fig_attributes(data)
    out["relations"] = fig_relations(own["relations"], data)
    out["classes"] = own["classes"]
    out["sure"] = fig_sure(data)
    out["areasize"] = fig_areasize(data)
    out["cause"] = own["cause"]
    out["leftout"] = fig_leftout(data)
    out["owndata"] = fig_owndata(data.parent)
    out["qgis"] = fig_qgis(out["attributes"], data)
    if out["relations"]["places"] != out["shapes"]["counted"]:
        raise ValueError("the relations lesson and the layers lesson count different places")
    out["land_km2"] = round(sum(m["land_km2"] for m in load_json(data / "municipalities.json").values()))   # the land the rain gauges stand for (lesson B5)
    if out["hex"]["places"] != out["shapes"]["points"]:
        raise ValueError(f"the hexagons count {out['hex']['places']} places, the layer draws {out['shapes']['points']}")
    if out["overlay"]["places"] != out["shapes"]["counted"]:
        raise ValueError("the overlay lesson and the layers lesson count different places")
    if out["rates"]["total"] != out["shapes"]["counted"]:   # the two lessons count the same places
        raise ValueError(f"the municipios' tourism places add to {out['rates']['total']}, places.json counts {out['shapes']['counted']}")
    return out


# ---- the file ----
def items(reg, tools, es, data=DATA):
    built = [l for l in reg["lessons"] if l["status"] == "built"]
    return {
        "parts": [{"id": p["id"], "letter": p["letter"], "name": p["name"]} for p in reg["parts"]],
        "lessons": [{"id": l["id"], "code": l["code"], "part": l["part"], "title": l["title"], "term": l["term"],
                     "tools": [{"mt": t, "en": tools[t], "es": es[tools[t]]} for t in l.get("tools") or []],
                     "layers": l.get("layers") or []} for l in built],
        "planned": sum(1 for l in reg["lessons"] if l["status"] == "planned"),
        "figures": figures(reg, data),
    }


def links(reg, site=SITE):
    """{ tools, layers, terms }: for each map tool (its data-mt), layer (the key of its help button) and glossary term (its id), the first built
    lesson that names it, as [lesson id, { en, es }]. The map's Tools pane, the layers' "?" and the glossary's pop-ups link to it."""
    helps = set()   # the help buttons of the 2D map and of the 3D view (which calls the tourism places places3d)
    for page in ("index.html", "3d.html"):
        helps |= set(re.findall(r'data-help="([a-z0-9_]+)"', (site / page).read_text(encoding="utf-8")))
    out = {"tools": {}, "layers": {}, "terms": {}}
    for l in sorted((x for x in reg["lessons"] if x["status"] == "built"), key=lambda x: x["code"]):
        to = [l["id"], l["title"]]
        for t in l.get("tools") or []:
            out["tools"].setdefault(t, to)
        for k in l.get("layers") or []:
            for h in (HELP_KEYS.get(k, k), "fac_" + k, k + "3d"):
                if h in helps:
                    out["layers"].setdefault(h, to)
        for g in l.get("glossary") or []:
            out["terms"].setdefault(g, to)
    return out


def render_links(obj):
    return LINKS_HEAD + "window.LEARN_LINKS = " + json.dumps(obj, ensure_ascii=False, separators=(",", ":")) + ";\n"


def render(obj):
    return HEAD + "window.LEARN = " + json.dumps(obj, ensure_ascii=False, separators=(",", ":")) + ";\n"


def main(argv):
    check = "--check" in argv
    reg = load_json(SRC)
    glossary_ids = {t["id"] for t in load_json(ROOT / "dictionary_src" / "glossary.json")}
    tools, es = map_tools(), spanish()
    page = PAGE.read_text(encoding="utf-8") if PAGE.exists() else ""
    P = problems(reg, glossary_ids, tools, layer_keys(), es, page)
    if P:
        print("learn.py: the registry has problems:")
        for p in P:
            print("  " + p)
        return 1
    try:
        text = render(items(reg, tools, es))
    except ValueError as e:
        print(f"learn.py: {e}")
        return 1
    n = sum(1 for l in reg["lessons"] if l["status"] == "built")
    stale = [f for f, new in ((ITEMS_JS, text), (LINKS_JS, render_links(links(reg)))) if not f.exists() or f.read_text(encoding="utf-8") != new]
    if not stale:
        print(f"learn: {n} lessons built of {len(reg['lessons'])}; {ITEMS_JS.name} and {LINKS_JS.name} are current")
        return 0
    if check:
        print("learn.py: out of date: " + ", ".join(f.relative_to(ROOT).as_posix() for f in stale) + ": run python learn.py")
        return 1
    for f, new in ((ITEMS_JS, text), (LINKS_JS, render_links(links(reg)))):
        f.write_text(new, encoding="utf-8", newline="\n")
    print(f"learn: {n} lessons built of {len(reg['lessons'])}; wrote " + ", ".join(f.relative_to(ROOT).as_posix() for f in stale))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
