"""Page-weight budget of each page of the observatory (plan item 13, section E of docs/proposal-2026-10.md; docs/performance.md).

    python budget.py           # the compressed size of what each page loads before it is ready, against its budget; exits 1 when a page is over
    python budget.py --json    # the same as JSON

What a page loads is declared in dictionary_src/routes.json: its HTML gives the scripts and styles; "first" lists the data files it fetches before it is ready,
"later" the ones it fetches on its own just after (the 3D view's trips, the area profile's other fields) and "on_use" the ones it fetches after it is ready, the first time a
visitor needs them (the map's index of the dictionary, the dictionary's detail files), which are reported, with the largest of each, but not budgeted; "external" gives the compressed size of the libraries from other hosts.
"deferred" lists the scripts and styles a page adds by itself once it is ready (the base map of the 2D map and the WCRP maps: js/core/basemap.js, MapLibre and
its Leaflet bridge; docs/basemap.md; deck.gl in the 3D view): they are not in the page's HTML, so they are counted apart, against "deferred_kb", and never in the first load. The Spanish
bundle (site/i18n/es.<page>.js) counts as a script, because Spanish is the first language. Sizes are gzip level 6, as the test server sends them; GitHub Pages
compresses a little better or worse file by file. tests/browser/throttle.js checks the "first" and "later" lists against what a real browser fetches.
Fonts and images are reported but not budgeted.
"""
import gzip
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SITE = ROOT / "site"
ROUTES = ROOT / "dictionary_src" / "routes.json"


def gz(path):
    return len(gzip.compress(Path(path).read_bytes(), 6))


def load_routes():
    return json.loads(ROUTES.read_text(encoding="utf-8"))


def measure(name, r, external):
    html = (SITE / r["page"]).read_text(encoding="utf-8")
    src = [s.split("?")[0] for s in re.findall(r'<script src="([^"]+)"', html)]
    css = [s.split("?")[0] for s in re.findall(r'<link rel="stylesheet" href="([^"]+)"', html) if not s.startswith("http")]
    local = [s for s in src if not s.startswith("http")]
    ext = [s for s in src if s.startswith("http")]
    missing_ext = [s for s in ext if s not in external]
    page = re.search(r'data-page="(\w+)"', html).group(1)
    scripts = sum(gz(SITE / s) for s in local) + sum(external.get(s, 0) for s in ext) + gz(SITE / "i18n" / f"es.{page}.js")
    data = {f: gz(SITE / "data" / f) for f in r.get("first", [])}
    later = {f: gz(SITE / "data" / f) for f in r.get("later", [])}
    on_use = {f: gz(SITE / "data" / f) for f in r.get("on_use", [])}
    other = gz(SITE / r["page"]) + sum(gz(SITE / c) for c in css)
    deferred = r.get("deferred", [])
    missing_ext += [s for s in deferred if s.startswith("http") and s not in external]
    deferred_b = sum(external.get(s, 0) if s.startswith("http") else gz(SITE / s) for s in deferred)
    kb = lambda b: round(b / 1024, 1)
    top = lambda files, n: sorted(((f, kb(v)) for f, v in files.items()), key=lambda x: -x[1])[:n]
    b = r["budget"]
    row = {"route": name, "page": r["page"], "scripts_kb": kb(scripts), "data_kb": kb(sum(data.values())), "html_css_kb": kb(other), "later_kb": kb(sum(later.values())), "on_use_kb": kb(sum(on_use.values())), "deferred_kb": kb(deferred_b), "deferred_budget_kb": r.get("deferred_kb"),
           "budget": b, "over": [], "missing_external": missing_ext, "largest_first": top(data, 3), "largest_later": top(later, 1), "largest_on_use": top(on_use, 1)}
    if kb(scripts) > b["script_kb"]:
        row["over"].append(f"scripts {kb(scripts)} KB > {b['script_kb']} KB")
    if kb(sum(data.values())) > b["data_kb"]:
        row["over"].append(f"data {kb(sum(data.values()))} KB > {b['data_kb']} KB")
    if r.get("deferred_kb") is not None and kb(deferred_b) > r["deferred_kb"]:
        row["over"].append(f"after-ready scripts {kb(deferred_b)} KB > {r['deferred_kb']} KB")
    if missing_ext:
        row["over"].append("a library from another host has no size in routes.json: " + ", ".join(missing_ext))
    return row


def tiles_candidates(limit_mb):
    """Published files above the size at which the plan moves a layer to PMTiles or Parquet (compressed)."""
    out = []
    for p in sorted((SITE / "data").rglob("*")):
        if p.is_file() and p.stat().st_size > limit_mb * 1024 * 1024:   # only a file whose raw size passes the line can pass it compressed
            g = gz(p)
            if g > limit_mb * 1024 * 1024:
                out.append((p.relative_to(SITE / "data").as_posix(), round(g / 1048576, 2)))
    return out


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    R = load_routes()
    rows = [measure(n, r, R["external"]) for n, r in R["routes"].items()]
    big = tiles_candidates(R["tiles_at_mb"])
    if "--json" in argv:
        print(json.dumps({"routes": rows, "tiles_candidates": big}, indent=1))
    else:
        for r in rows:
            b = r["budget"]
            print(f"{r['route']:<11} scripts {r['scripts_kb']:7.1f} / {b['script_kb']} KB   data {r['data_kb']:7.1f} / {b['data_kb']} KB   html+css {r['html_css_kb']:5.1f} KB   after ready {r['later_kb']:7.1f} KB   on first use {r['on_use_kb']:5.1f} KB{f"   libraries after ready {r['deferred_kb']:5.1f} / {r['deferred_budget_kb']} KB" if r['deferred_budget_kb'] is not None else ''}   {'OVER: ' + '; '.join(r['over']) if r['over'] else 'ok'}")
            for label, key in (("after ready", "largest_later"), ("on first use", "largest_on_use")):
                if r[key]:
                    print(f"{'':<11} largest {label}: {r[key][0][0]} ({r[key][0][1]} KB)")
        print(f"files above {R['tiles_at_mb']} MB compressed (move to PMTiles or Parquet): {', '.join(f'{f} ({mb} MB)' for f, mb in big) or 'none'}")
    return 1 if any(r["over"] for r in rows) else 0


if __name__ == "__main__":
    raise SystemExit(main())
