"""WCRP Social Capital map: the community-asset flags of the Comunidades Especiales list, matched to the observatory's polygons, and what the WCRP page's
municipio summary needs that no published file holds.

    python wcrp_social.py                    build site/data/wcrp_social.json from wcrp_ce_assets.csv, comunidades.geojson and housing_series.json
    python wcrp_social.py --import FILE      clean the program's list (COMUNIDADES ESPECIALES.csv, WCRP SharePoint) into wcrp_ce_assets.csv, then build
    python wcrp_social.py --check            say whether wcrp_social.json is what the CSV and the published files give (nothing written)

The list. WCRP's Social Capital Mapping tool (a joint effort of the Puerto Rico Department of Housing and Foundation for Puerto Rico, funded with CDBG-DR)
kept a list of 711 Comunidades Especiales with Yes/No flags for community assets: community center, library, electronic library, passive park, sports court,
residents' association, recreation association, crime-prevention association, and PDI. Its date is not stated: it is the WCRP Social Capital Mapping list, about
2019-2021, built on the Junta de Planificacion inventory. No live source exists, so wcrp_ce_assets.csv keeps a cleaned extract: the community's name,
municipio and barrio as the list writes them, the polygon of comunidades.geojson it matches, and the nine flags (si, no, nd = "Informacion No Disponible").
The list's two hazard columns are left out (comunidades.geojson has the Junta's own). The list holds no personal data; the extract keeps no other column.

The copy read through the Microsoft 365 connector lost the list's accented letters (each became U+FFFD). Municipio names are restored from the 78 official
names; a community or barrio name is restored letter by letter from the polygon it matches when both have the same length; a letter that cannot be restored
is written "?".

Matching (to the 713 polygons of comunidades.geojson, the Junta's 2006 delimitation), within the same municipio, one polygon per row at most:
  exacto      the names are equal once accents, capitals and punctuation are set aside (a lost letter matches any letter);
  barrio      two polygons have that name; the one in the row's barrio is taken;
  parecido    no name is equal: the closest name in the same barrio is taken when it is clearly the closest (similarity 0.8 or more after setting aside
              generic words such as "Barriada", "Calle", "Parcelas" or "Sector", and at least 0.15 above the next polygon of that barrio), and no other row took it;
  sin_enlace  none of these.
The rule runs once, at --import; the CSV keeps its result (column enlace), so a reviewer can correct a row by hand and the build keeps it.

Output, site/data/wcrp_social.json (arrays follow geo.ids, the 78 municipios then Puerto Rico, the order of facility_series.json):
  population        residents, latest Census Bureau estimate in housing_series.json: the denominator of the page's per-1,000 rates
  polygons, housing_units   Comunidades Especiales and their housing units (Junta 2006 inventory) in each municipio, from comunidades.geojson
  assets            the list's rows by municipio (listed, matched), the count of "si" of each flag and of "nd", the match counts, and each matched
                    polygon's nine flags as one code ("1" si, "0" no, "-" nd), keyed "municipio|nombre|barrio" as comunidades.geojson writes them
WCRP is a HUD CDBG-DR program: the file's compliance review records FPR's approval of 2026-10-19 (HANDOFF decision 51) and its license review, cleared the same
day, that this approval covers republishing the list on the observatory; the list states no open license, so others should ask PRDOH and FPR before re-use
(dictionary_src/datasets.json; HANDOFF decision 54); the page keeps an "In review" marker (docs/wcrp.md).
"""
import csv
import difflib
import json
import re
import sys
import unicodedata
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "site" / "data"
CSV_PATH = ROOT / "wcrp_ce_assets.csv"
OUT = DATA / "wcrp_social.json"
LOST = "�"

# (column in the program's list, column in the extract): the nine asset flags, in the list's order
FLAGS = [("Centro Comunal", "centro_comunal"), ("Biblioteca", "biblioteca"), ("Bibilioteca Electrónica", "biblioteca_electronica"), ("Parque Pasivo", "parque_pasivo"),
         ("Cancha", "cancha"), ("Asociación de Residentes", "asoc_residentes"), ("Asociación Recreativa", "asoc_recreativa"),
         ("Asociació Prevención Crimen", "asoc_prevencion_crimen"), ("PDI", "pdi")]
COLUMNS = ["nombre_lista", "municipio", "barrio_lista", "nombre_jp", "barrio_jp", "enlace"] + [k for _, k in FLAGS]
GENERIC = {"barriada", "calle", "barrio", "bo", "parcelas", "sector", "comunidad", "urb", "urbanizacion", "la", "el", "los", "las", "de", "del", "y"}
VINTAGE = "unknown; WCRP Social Capital Mapping list, about 2019–2021, from the JP inventory"


def log(*a):
    print(*a, file=sys.stderr)


def load(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def fold(s):
    """Lower case, no accents, no punctuation; a lost letter becomes '?'."""
    s = unicodedata.normalize("NFD", s.replace(LOST, "?"))
    s = "".join(c for c in s if unicodedata.category(c) != "Mn").lower()
    s = re.sub(r"[^a-z0-9? ]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def same(a, b):
    """a (may hold '?') equals b letter for letter."""
    return len(a) == len(b) and all(x == y or x == "?" for x, y in zip(a, b))


def restore(raw, clean, lexicon):
    """The list's spelling, each lost letter taken from the matching name (aligned letter by letter), else from the only word of the Junta's names and the
    municipio names that fits; '?' when neither tells."""
    if LOST not in raw:
        return raw
    out = list(raw)
    if clean:
        sm = difflib.SequenceMatcher(None, raw.lower(), clean.lower(), autojunk=False)
        for tag, i1, i2, j1, j2 in sm.get_opcodes():
            if tag == "replace" and i2 - i1 == j2 - j1:
                for k in range(i2 - i1):
                    if raw[i1 + k] == LOST and ord(clean[j1 + k]) > 127 and clean[j1 + k].isalpha():   # only a letter outside ASCII was lost
                        out[i1 + k] = clean[j1 + k]
    def word(m):
        w = m.group(0)
        if LOST not in w:
            return w
        hits = {x.lower() for x in lexicon.get(len(w), ()) if same(fold(w), fold(x)) and all(ord(x[i]) > 127 for i, c in enumerate(w) if c == LOST)}
        if len(hits) != 1:
            return w
        h = hits.pop()
        return "".join(c if c != LOST else (h[i].upper() if w.isupper() or (i and w[i - 1].isupper() and i + 1 < len(w) and w[i + 1].isupper()) else h[i]) for i, c in enumerate(w))
    s = re.sub(r"[^\s,()/.\-]+", word, "".join(out))
    return s.replace(LOST, "?")


def core(s):
    w = [x for x in fold(s).split() if x not in GENERIC]
    return " ".join(w).replace(" iii", " 3").replace(" ii", " 2").replace(" i", " 1") if w else ""


def barrio_words(s):
    return set(fold(s).replace("/", " ").split())


def flag_value(s):
    f = fold(s)
    return "si" if f == "si" else "no" if f == "no" else "nd" if f.startswith("informaci") else None


def municipio_names():
    return load(DATA / "facility_series.json")["geo"]["names"][:-1]


def import_list(path):
    rows = list(csv.reader(Path(path).open(encoding="utf-8-sig", newline="")))
    head, rows = rows[0], rows[1:]
    col = {}
    for src, _ in FLAGS:   # the list's column names, as written (a lost letter matches any letter)
        hit = [i for i, h in enumerate(head) if same(fold(h), fold(src))]
        if len(hit) != 1:
            raise SystemExit(f"wcrp_social: column {src!r} not in {path}")
        col[fold(src)] = hit[0]
    munis = {fold(m): m for m in municipio_names()}
    feats = [f["properties"] for f in load(DATA / "comunidades.geojson")["features"]]
    by_muni = {}
    for i, p in enumerate(feats):
        by_muni.setdefault(p["municipio"], []).append(i)
    out, taken = [], {}
    pending = []
    lexicon = {}
    for x in [w for p in feats for w in re.split(r"[\s,()/.\-]+", f"{p['nombre']} {p.get('barrio') or ''}")] + [w for m in munis.values() for w in m.split()]:
        if x:
            lexicon.setdefault(len(x), set()).add(x)
    for r in rows:
        name, mraw, braw = r[0], r[1], r[2]
        mm = [m for k, m in munis.items() if same(fold(mraw), k)]
        if len(mm) != 1:
            raise SystemExit(f"wcrp_social: municipio {mraw!r} not found")
        m = mm[0]
        flags = {}
        for src, key in FLAGS:
            v = flag_value(r[col[fold(src)]])
            if v is None:
                raise SystemExit(f"wcrp_social: {name!r}: {src} = {r[col[fold(src)]]!r}")
            flags[key] = v
        cands = by_muni.get(m, [])
        hit = [i for i in cands if same(fold(name), fold(feats[i]["nombre"]))]
        how = "exacto"
        if len(hit) > 1:
            hit = [i for i in hit if barrio_words(braw) & barrio_words(feats[i].get("barrio") or "")]
            how = "barrio"
        row = {"raw": (name, braw), "municipio": m, "flags": flags, "poly": hit[0] if len(hit) == 1 else None, "how": how if len(hit) == 1 else None}
        if row["poly"] is not None:
            taken[row["poly"]] = True
        out.append(row)
        if row["poly"] is None:
            pending.append(row)
    for row in pending:   # parecido: the clearly closest name in the same barrio, not taken by another row
        a, bw = core(row["raw"][0]).replace("?", ""), barrio_words(row["raw"][1])
        scored = []
        for i in by_muni.get(row["municipio"], []):
            p = feats[i]
            if not (bw & barrio_words(p.get("barrio") or "")):
                continue
            b = core(p["nombre"])
            s = difflib.SequenceMatcher(None, a, b).ratio() if a and b else 0
            if a and b and (a in b or b in a):
                s = max(s, 0.9)
            scored.append((s, i))
        scored.sort(reverse=True)
        free = [(s, i) for s, i in scored if i not in taken]
        if free and free[0][0] >= 0.8 and (len(scored) < 2 or scored[0][1] == free[0][1]) and (len(free) < 2 or free[0][0] - free[1][0] >= 0.15):
            row["poly"], row["how"] = free[0][1], "parecido"
            taken[free[0][1]] = True
    with CSV_PATH.open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(COLUMNS)
        for row in out:
            p = feats[row["poly"]] if row["poly"] is not None else None
            w.writerow([restore(row["raw"][0], p["nombre"] if p else "", lexicon), row["municipio"], restore(row["raw"][1].strip(), (p.get("barrio") or "").upper() if p else "", lexicon),
                        p["nombre"] if p else "", (p.get("barrio") or "") if p else "", row["how"] or "sin_enlace"] + [row["flags"][k] for _, k in FLAGS])
    log(f"wrote {CSV_PATH.name}: {len(out)} rows")


def read_csv():
    with CSV_PATH.open(encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
    if not rows or list(rows[0].keys()) != COLUMNS:
        raise SystemExit(f"wcrp_social: {CSV_PATH.name} should have the columns {COLUMNS}")
    return rows


def build():
    rows = read_csv()
    fac = load(DATA / "facility_series.json")
    names, ids = fac["geo"]["names"], fac["geo"]["ids"]
    at = {n: i for i, n in enumerate(names)}
    pr = len(names) - 1
    hs = load(DATA / "housing_series.json")
    pv = next(v for v in hs["vars"] if v["key"] == "population")
    year = max(pv["years"], key=int)
    if hs["geo"]["names"] != names:
        raise SystemExit("wcrp_social: housing_series.json and facility_series.json list the municipios in different orders")
    feats = [f["properties"] for f in load(DATA / "comunidades.geojson")["features"]]
    key = lambda p: f"{p['municipio']}|{p['nombre']}|{p.get('barrio') or ''}"
    keys = {(p["municipio"], p["nombre"], p.get("barrio") or ""): key(p) for p in feats}
    polygons, units = [0] * len(names), [0] * len(names)
    for p in feats:
        for arr, v in ((polygons, 1), (units, p.get("viviendas") or 0)):
            arr[at[p["municipio"]]] += v
            arr[pr] += v
    flags = [k for _, k in FLAGS]
    listed, matched = [0] * len(names), [0] * len(names)
    yes = {k: [0] * len(names) for k in flags}
    nd = {k: [0] * len(names) for k in flags}
    poly, how = {}, {}
    for r in rows:
        if r["municipio"] not in at:
            raise SystemExit(f"wcrp_social: unknown municipio {r['municipio']!r}")
        i = at[r["municipio"]]
        for j in (i, pr):
            listed[j] += 1
            for k in flags:
                yes[k][j] += r[k] == "si"
                nd[k][j] += r[k] == "nd"
        how[r["enlace"]] = how.get(r["enlace"], 0) + 1
        if r["nombre_jp"]:
            k = keys.get((r["municipio"], r["nombre_jp"], r["barrio_jp"]))
            if not k:
                raise SystemExit(f"wcrp_social: {r['nombre_jp']!r} ({r['municipio']}) is not a polygon of comunidades.geojson")
            if k in poly:
                raise SystemExit(f"wcrp_social: two rows match {k!r}")
            poly[k] = "".join("1" if r[f] == "si" else "0" if r[f] == "no" else "-" for f in flags)
            for j in (i, pr):
                matched[j] += 1
    return {"version": 1, "built": date.today().isoformat(),
            "about": "What the WCRP page's Social Capital map needs that no other published file holds: the residents each per-1,000 rate divides by, the Comunidades Especiales "
                     "of each municipio, and the community-asset flags of the WCRP Social Capital Mapping list matched to those polygons. Arrays follow geo.ids (the last is Puerto Rico). "
                     "Built by wcrp_social.py; WCRP-derived; published with the 'In review' marker (HANDOFF decision 51).",
            "geo": {"ids": ids, "names": names},
            "population": {"year": int(year), "basis": (pv.get("basis") or {}).get(year, ""), "ref": "US Census Bureau, Population Estimates (housing_series.json)", "values": pv["years"][year]},
            "comunidades": {"ref": "Junta de Planificación, Comunidades Especiales, 2006 delimitation and inventory (comunidades.geojson)", "polygons": polygons, "housing_units": units},
            "assets": {"vintage": VINTAGE,
                       "source": "WCRP Social Capital Mapping tool (PRDOH and FPR, CDBG-DR), list COMUNIDADES ESPECIALES; cleaned extract wcrp_ce_assets.csv",
                       "flags": flags, "listed": listed, "matched": matched, "yes": yes, "unknown": nd,
                       "match": {"rows": len(rows), "polygons": len(feats), "by_rule": dict(sorted(how.items())), "matched_rows": sum(1 for r in rows if r["nombre_jp"]), "polygons_matched": len(poly)},
                       "poly": dict(sorted(poly.items()))}}


def write(doc):
    OUT.write_text(json.dumps(doc, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    m = doc["assets"]["match"]
    log(f"wrote {OUT.relative_to(ROOT)} ({OUT.stat().st_size / 1024:.0f} KB): {m['matched_rows']} of {m['rows']} rows matched {m['by_rule']}; {m['polygons_matched']} of {m['polygons']} polygons")


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if "--check" in argv:
        doc = build()
        old = load(OUT) if OUT.exists() else None
        for x in (old, doc):
            if x:
                x.pop("built", None)
        ok = old == doc
        log("wcrp_social: current" if ok else "wcrp_social: rebuild needed (python wcrp_social.py)")
        return 0 if ok else 1
    if "--import" in argv:
        import_list(argv[argv.index("--import") + 1])
    write(build())
    return 0


if __name__ == "__main__":
    sys.exit(main())
