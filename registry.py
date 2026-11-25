"""Inventory of everything the observatory publishes, written to site/data/registry.json: what the Data management page (site/data-management.html),
the data dictionary and the chat read.

The observatory's database only grows: every dataset that is harvested stays, and new ones are added. This file is how the chat (and whoever maintains
the observatory) sees what is there and how big it is, against the hosting limits, so growth is planned and never a surprise. For each file it gives the
size, the records, fields and values (data points) counted by ledger.py, the dates it was first published and last updated (the ledger,
dictionary_src/data_ledger.json, which this updates), the dictionary items that document it and the state of its compliance review (the data contract,
dictionary_src/datasets.json); and, for the whole folder, the totals, their history and the counts of what is not published. Definitions:
docs/data-management.md.

  python registry.py           update the ledger and write registry.json (only when something other than the build date changed)
  python registry.py --check   exit 1 when the ledger or registry.json does not describe the files as they are (dates are never compared with today)

Run it after any build (build.py and the nightly transit refresh do).
"""
import gzip
import json
import sys
from collections import Counter
from pathlib import Path

import contract
import ledger

DATA = Path(__file__).parent / "site" / "data"
OUT = DATA / "registry.json"
PAGES_SITE_LIMIT = 1000 * 1024 * 1024      # GitHub Pages: published site should stay under about 1 GB
PAGES_FILE_LIMIT = 100 * 1024 * 1024       # GitHub: files over 100 MB are refused
WARN_AT = 0.6                              # start planning the move to object storage at 60% of the site limit

SRC = Path(__file__).parent / "dictionary_src"
GROWTH_NOTE = ("Every harvested dataset stays and new ones are added, so the data folder only grows. Each dataset is its own lazily loaded file. When the total passes "
               "the planning line, move the large files to object storage as Parquet or PMTiles and query them in the browser (for example with DuckDB-WASM) while the "
               "small summaries stay on the page.")


def load(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def records():
    """File records of the data contract (dictionary_src/datasets.json): titles, domains, license class, geography, time, reviews and flags of every file."""
    p = SRC / "datasets.json"
    return {r["file"]: r for r in load(p)["datasets"]} if p.exists() else {}


def loaded_by():
    """{file: [{route, when}]}: the pages that load a data file without a click, from dictionary_src/routes.json (budget.py)."""
    p = SRC / "routes.json"
    out = {}
    if p.exists():
        for name, r in load(p)["routes"].items():
            for when in ("first", "later"):
                for f in r.get(when, []):
                    out.setdefault(f, []).append({"route": name, "when": when})
    return out


def documented_by(data_dir=DATA):
    """{file: number of dictionary entries whose where.files name it}, and the number of entries that document at least one file."""
    p = Path(data_dir) / "dictionary.json"
    if not p.exists():
        return {}, 0
    by, any_ = Counter(), 0
    for e in load(p)["entries"]:
        files = {x.split(":")[0] for x in (e.get("where") or {}).get("files") or []}
        by.update(files)
        any_ += bool(files)
    return dict(by), any_


def on_map(data_dir=DATA):
    """{file: how the map shows it}, for the Data management page's "On the map" link: {"l": the layer keys its dictionary entries switch on,
    "e": the first dataset of the file the Analysis tab can shade, "n": how many such datasets it has}. From the dictionary (which entries document a
    file) and the Catalog's index (catalog.py map_action: how an entry goes onto the map). A file no entry puts on the map has no line."""
    d, c = Path(data_dir) / "dictionary.json", Path(data_dir) / "catalog_index.json"
    if not d.exists() or not c.exists():
        return {}
    ix = load(c)["index"]
    i_id, i_map = ix["fields"].index("id"), ix["fields"].index("map")
    action = {r[i_id]: r[i_map] for r in ix["rows"] if r[i_map]}
    out = {}
    for e in load(d)["entries"]:
        a = action.get(e["id"])
        if not a:
            continue
        for name in dict.fromkeys(x.split(":")[0] for x in (e.get("where") or {}).get("files") or []):
            o = out.setdefault(name, {"l": [], "e": []})
            for k in ([a[1]] if a[0] == "econ" else a[1].split(",")):
                if k not in o["e" if a[0] == "econ" else "l"]:
                    o["e" if a[0] == "econ" else "l"].append(k)
    return {name: {**({"l": ",".join(o["l"])} if o["l"] else {}), **({"e": o["e"][0], "n": len(o["e"])} if o["e"] else {})} for name, o in out.items()}


def sources():
    """The source records of dictionary_src/sources.json, with the old ids of "_aliases" resolved."""
    s = load(SRC / "sources.json")
    aliases = s.pop("_aliases", {})
    return s, aliases


def licence_from(rec, srcs=None):
    """The sources that set a file's license class: a file takes the most restrictive class of its sources, so a file 'unstated' has at least one
    source that states no license. [{id, en, es}] with the source's short name, for the Compliance review column ("License not stated: municipal
    GTFS feeds"); empty when no source has the file's class."""
    s, aliases = srcs or sources()
    out = []
    for sid in rec.get("sources") or []:
        sid = aliases.get(sid, sid)
        src = s.get(sid) or {}
        if src.get("licence_class") == rec.get("licence_class") and sid not in [x["id"] for x in out]:
            short = src.get("short") or {}
            out.append({"id": sid, "en": short.get("en") or src.get("name") or sid, "es": short.get("es") or short.get("en") or src.get("name") or sid})
    return out


def review_of(rec, srcs=None):
    """The Compliance review column: 'open' (with the short reason of each open review), else 'cleared' (with the latest date), else 'unstated' (at
    least one source states no license; the file takes the most restrictive class of its sources), else 'none' (no review is needed). Flags:
    federal-grant, counts-only (the contract's flags) and the license class when it is unstated or licensed-not-open, with licence_from, the
    sources that set it."""
    revs = [r for r in rec.get("review") or [] if isinstance(r, dict)]
    open_ = [{"type": r["type"], "summary": r.get("summary")} for r in revs if r.get("status") == "open"]
    cleared = [r for r in revs if r.get("status") == "cleared"]
    dates = sorted(r["date"] for r in cleared if r.get("date"))
    flags = list(rec.get("flags") or [])
    lc = rec.get("licence_class")
    if lc == "unstated":
        flags.append("licence-unstated")
    elif lc == "licensed-not-open":
        flags.append("licensed-not-open")
    status = "open" if open_ else "cleared" if cleared else "unstated" if lc == "unstated" else "none"
    out = {"status": status, "flags": flags}
    if lc in ("unstated", "licensed-not-open"):
        out["licence_from"] = licence_from(rec, srcs)
    if open_:
        out["open"] = open_
    if cleared:
        out["cleared"] = dates[-1] if dates else None
        out["cleared_types"] = sorted({r["type"] for r in cleared})
    return out


def note(doc, *path):
    for k in path:
        doc = doc.get(k) if isinstance(doc, dict) else None
    return doc if isinstance(doc, int) and not isinstance(doc, bool) else None


def withheld(data_dir=DATA):
    """What is not published, as counts only (no name, no place): read from the published files themselves, so the page follows each build. Each row
    names the file the count comes from and the dictionary entry that gives the rule."""
    def read(name):
        try:
            return load(Path(data_dir) / name)
        except (OSError, ValueError):
            return {}
    places, meta, health, community, facility, npo, wanted = (read(n) for n in ("places.json", "meta.json", "health_series.json", "community_series.json",
                                                                                "facility_series.json", "nonprofit_series.json", "wanted.json"))
    why = Counter(p["withheld"] for p in places if isinstance(p, dict) and p.get("withheld")) if isinstance(places, list) else Counter()
    sites = (health.get("notes") or {}).get("sites") or {}
    hp = (community.get("notes") or {}).get("historic_places") or {}
    ph = (facility.get("notes") or {}).get("public_housing") or {}
    tc = (facility.get("notes") or {}).get("lihtc") or {}
    shelters = next((w.get("status") for w in wanted.get("items") or [] if w.get("id") == "shelters"), None)
    return [
        {"id": "places_not_drawn", "count": sum(why.values()) if why else None, "of": len(places) if isinstance(places, list) else None, "parts": dict(sorted(why.items())), "file": "places.json", "doc": "places.withheld"},
        {"id": "not_tourism", "count": note(meta, "counts", "not_tourism_dropped"), "file": "meta.json", "doc": "places.withheld"},
        {"id": "hrsa_sites", "count": note(sites, "service_sites"), "parts": {k: sites[k] for k in ("permanent", "mobile_vans") if isinstance(sites.get(k), int)}, "file": "health_series.json", "doc": "health.sites_method"},
        {"id": "shelters", "count": 0, "wanted_status": shelters, "file": "wanted.json", "doc": "data.wanted"},
        {"id": "nrhp_private_homes", "count": note(hp, "counted_not_drawn_residences"), "of": note(hp, "listings"), "file": "community_series.json", "doc": "layers.historic_places"},
        {"id": "public_housing_approximate", "count": note(ph, "not_drawn_approximate_location"), "of": note(ph, "developments"), "file": "facility_series.json", "doc": "layers.public_housing"},
        {"id": "lihtc_not_drawn", "count": (note(tc, "not_drawn_approximate_location") or 0) + (note(tc, "not_drawn_sensitive") or 0) + (note(tc, "not_drawn_point_outside_its_municipio") or 0) if tc else None,
         "of": note(tc, "projects"), "parts": {k: tc[k] for k in ("not_drawn_approximate_location", "not_drawn_sensitive", "not_drawn_point_outside_its_municipio") if isinstance(tc.get(k), int)},
         "file": "facility_series.json", "doc": "layers.lihtc"},
        {"id": "treatment_facilities", "count": note(community, "notes", "treatment_facilities", "facilities"), "file": "community_series.json", "doc": "community.bh_all"},
        {"id": "nonprofits", "count": note(npo, "notes", "organizations"), "file": "nonprofit_series.json", "doc": "nonprofits.npo_all"},
    ]


def domain_names():
    return {d["id"]: d["name"] for d in contract.load_registry()["domains"]}


def build(cur, led, data_dir=DATA):
    """registry.json from the described files (ledger.current()) and the ledger. 'built' is set by write()."""
    recs, by, files, srcs = records(), loaded_by(), [], sources()
    docs, documenting = documented_by(data_dir)
    shown = on_map(data_dir)
    for name in sorted(cur):
        c, l, rec, p = cur[name], led["files"].get(name, {}), recs.get(name), Path(data_dir) / name
        raw = ledger.lf(p.read_bytes(), name)
        row = {"file": name, "title": rec["title"]["en"] if rec else name, "bytes": c["bytes"], "gzip_bytes": len(gzip.compress(raw, 6, mtime=0)),   # what a browser downloads (docs/performance.md)
               "loaded_by": by.get(name, [])}   # pages that fetch it without a click; an empty list: only on use (a switch, a button, a download)
        if rec:
            row.update({"title_es": rec["title"]["es"], "domains": rec["domains"], "licence_class": rec["licence_class"], "tier": rec["tier"],
                        "geography": rec["geography"]["level"], "time": rec["time"]["type"]})
        if p.suffix == ".json" and c["bytes"] < 40 * 1024 * 1024:
            try:
                j = json.loads(raw.decode("utf-8"))
            except ValueError:
                j = None
            if isinstance(j, dict):
                if isinstance(j.get("vars"), list):
                    row["datasets"] = len(j["vars"])
                    yrs = j.get("years")
                    if isinstance(yrs, list) and yrs:
                        row["years"] = [min(yrs), max(yrs)]
                if j.get("built"):
                    row["built"] = j["built"]
                if isinstance(j.get("items"), list):
                    row["items"] = len(j["items"])
        if c.get("items") is not None:
            row["items"] = c["items"]
        row.update({"kind": c["kind"], "records": c["records"], "fields": c["fields"], "values": c["values"], "vertices": c["vertices"],
                    "first_published": l.get("first_published"), "last_updated": l.get("last_updated"), "versions": l.get("versions"),
                    "documented_by": docs.get(name, 0), "review": review_of(rec, srcs) if rec else {"status": "none", "flags": []}})
        if name in shown:
            row["map"] = shown[name]
        files.append(row)
    total =sum(f["bytes"] for f in files)
    t = ledger.totals(cur, ledger.documented_items(data_dir))
    counted = [f for f in files if f["kind"] == "data"]
    meta = {}
    try:
        meta = load(Path(data_dir) / "meta.json")
    except (OSError, ValueError):
        pass
    return {
        "built": None,
        "snapshot": meta.get("label"),
        "total_bytes": total,
        "limits": {"site_bytes": PAGES_SITE_LIMIT, "file_bytes": PAGES_FILE_LIMIT, "plan_at_fraction": WARN_AT},
        "used_fraction": round(total / PAGES_SITE_LIMIT, 3),
        "needs_planning": total >= PAGES_SITE_LIMIT * WARN_AT or any(f["bytes"] >= PAGES_FILE_LIMIT * WARN_AT for f in files),
        "growth_note": GROWTH_NOTE,
        "totals": {**t, "vertices": sum(f["vertices"] or 0 for f in counted), "counted_files": len(counted), "documenting_items": documenting,
                   "first_published": min((f["first_published"] for f in files if f["first_published"]), default=None),
                   "last_updated": max((f["last_updated"] for f in files if f["last_updated"]), default=None)},
        "history": led.get("history", []),
        "domain_names": domain_names(),
        "withheld": withheld(data_dir),
        "files": files,
    }


def comparable(reg):
    """What decides whether registry.json is rewritten, and what --check compares: everything but the build date and the compressed sizes (which can
    differ by a few bytes between zlib versions, so a runner would otherwise rewrite the file every night)."""
    r = {k: v for k, v in reg.items() if k != "built"}
    r["files"] = [{k: v for k, v in f.items() if k != "gzip_bytes"} for f in reg.get("files", [])]
    return json.dumps(r, ensure_ascii=False, sort_keys=True)


def write(reg, day):
    reg = {**reg, "built": day}
    OUT.write_text(json.dumps(reg, indent=1, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    return reg


def apply(log=print, day=None):
    """Update the ledger and rewrite registry.json when something changed. Returns True when registry.json was written."""
    day = day or ledger.today()
    cur = ledger.current()
    items = ledger.documented_items()
    before = ledger.load()
    led, changed = ledger.update(before, cur, items, day)
    if led != before:
        ledger.dump(led)
        log(f"data_ledger.json: {len(changed)} file(s) with new content: {', '.join(changed[:8])}{'…' if len(changed) > 8 else ''}" if changed else "data_ledger.json: counts or sizes updated")
    reg = build(cur, led)
    try:
        old = load(OUT)
    except (OSError, ValueError):
        old = None
    t = reg["totals"]
    summary = (f"{t['files']} files, {reg['total_bytes'] / 1048576:.1f} MB ({reg['used_fraction'] * 100:.1f}% of the 1 GB Pages limit), {t['records']:,} records, "
               f"{t['fields']:,} fields, {t['values']:,} values in {t['counted_files']} data files")
    if old is not None and comparable(old) == comparable(reg):
        log(f"registry.json: unchanged ({summary})")
        return False
    write(reg, day)
    log(f"registry.json: {summary}")
    return True


def check():
    cur = ledger.current()
    items = ledger.documented_items()
    led = ledger.load()
    P = ledger.problems(led, cur, items)
    try:
        have = load(OUT)
    except (OSError, ValueError):
        have = None
    if have is None or comparable(have) != comparable(build(cur, led)):
        P.append("registry.json is not what the files and the ledger give")
    for p in P[:20]:
        print("  " + p)
    if P:
        print(f"registry: {len(P)} problem(s). Run python registry.py and commit site/data/registry.json and dictionary_src/data_ledger.json "
              "(on a conflict in the ledger, take main's version first).")
        return 1
    print(f"registry.json and data_ledger.json are current ({len(cur)} files)")
    return 0


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if "--check" in argv:
        return check()
    apply()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
