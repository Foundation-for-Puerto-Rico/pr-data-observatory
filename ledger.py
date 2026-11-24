"""Counts and dates of every published data file: the ledger behind the Data management page (site/data-management.html; docs/data-management.md).

Definitions (docs/data-management.md, section 1, gives them in full with the validation):
  record   an observation unit: a feature of a GeoJSON file, a row of a table (a municipio in a year, a barrio in a five-year window, a place, a stop,
           a trip, a road edge). A series file has one record for each area and period that holds at least one value.
  field    a variable the records carry: a GeoJSON property, a series variable, its margin of error, a column. A cell that holds a list (24 hourly
           counts, the stop times of a trip) is one field. A file with several tables counts the fields of each table.
  value    a data point: a non-null scalar in a record's field. A list cell counts its non-null elements. Missing: null, absent and the empty string.
           Not values: metadata (labels, notes, sources, about, build stamps, method and check blocks), geometry coordinates (counted as vertices),
           the keys a file stores once as a lookup (geo.ids, years) and lookup tables (a legend, a deflator, a search index).
  vertex   a position of a geometry: a GeoJSON coordinate pair, a point's latitude and longitude, a path point, a road node or shape point.
  kind     data (counted), documentation (system.docs: the dictionary, the catalog, meta.json, wanted.json) or index (system.tools: gazetteer.json, a
           search lookup of names held in other files). Documentation and index files are listed and sized but not counted.

Content hash: the SHA-256 of the file's JSON in canonical form (keys sorted, no spaces), with the build stamps (STAMPS) left out wherever they are not
inside a record, so a rebuild that only writes a new date has the same hash. A file that is not JSON is hashed as bytes (line ends as LF).

Ledger (dictionary_src/data_ledger.json): for each file the first-published date, the last date its content changed, how many content versions were
published, and the current hash, size, records, fields, values and vertices; and a history of the totals, one row per date they changed.
registry.py updates it on every build (update()); `python ledger.py --backfill` rebuilds it from the git history of main (backfill()).
Dates are Puerto Rico dates (UTC-4, no daylight saving time).

  python ledger.py --count FILE...     the counts of published files (site/data/FILE), with the table each field belongs to (--fields)
  python ledger.py --backfill [REF]    rebuild the ledger's dates and history from the first-parent history of REF (default origin/main), then the working tree
"""
import hashlib
import gzip
import json
import math
import struct
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import contract

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "site" / "data"
LEDGER = ROOT / "dictionary_src" / "data_ledger.json"
DATASETS = ROOT / "dictionary_src" / "datasets.json"
PR_TZ = timezone(timedelta(hours=-4))          # Puerto Rico: Atlantic Standard Time all year
STAMPS = {"built", "generated_at", "snapshot_built"}   # build dates written into files; left out of the content hash
NOT_LISTED = {"registry.json"}                 # the inventory itself: it describes the others and is written after them
VERSION = 1
TOTAL_KEYS = ("files", "bytes", "records", "fields", "values", "items")   # a history row: these totals on a date


def today():
    return datetime.now(PR_TZ).date().isoformat()


# ── Values ───────────────────────────────────────────────────────────────────

def missing(x):
    return x is None or x == "" or (isinstance(x, float) and math.isnan(x))


def leaves(x):
    """The values in one cell: 1 for a scalar, the non-null scalars of a list or an object, 0 for a missing value."""
    if isinstance(x, (list, tuple)):
        return sum(leaves(v) for v in x)
    if isinstance(x, dict):
        return sum(leaves(v) for v in x.values())
    return 0 if missing(x) else 1


def flatten(cells, prefix=""):
    """(field, cell) pairs of a record; an object inside a record is a group of fields (by_category.ATTRACTIONS), a list is one field."""
    for k, v in cells.items():
        if isinstance(v, dict) and v:
            yield from flatten(v, f"{prefix}{k}.")
        else:
            yield prefix + str(k), v


def positions(c):
    """The positions of a GeoJSON coordinates array (the closing position of each ring counts)."""
    if not c:
        return 0
    if isinstance(c[0], (int, float)):
        return 1
    return sum(positions(x) for x in c)


def geometry_positions(g):
    if not g:
        return 0
    if g.get("type") == "GeometryCollection":
        return sum(geometry_positions(x) for x in g.get("geometries") or [])
    return positions(g.get("coordinates"))


class Tally:
    """Records, fields (table, name) with at least one value, values and vertices of one file."""

    def __init__(self):
        self.records = 0
        self.fields = set()
        self.values = 0
        self.vertices = 0
        self.geometry = False

    def row(self, table, cells):
        for name, v in flatten(cells):
            n = leaves(v)
            if n:
                self.fields.add((table, name))
                self.values += n
        self.records += 1

    def result(self):
        return {"records": self.records, "fields": len(self.fields), "values": self.values, "vertices": self.vertices if self.geometry else None}


# ── Adapters: what a record is in each family of files ───────────────────────

def geojson(doc, t):
    """A feature is a record, its properties its fields; the geometry is counted as vertices. The collection's own keys (source, vintage, notes) are metadata."""
    t.geometry = True
    for f in doc.get("features") or []:
        t.row("features", f.get("properties") or {})
        t.vertices += geometry_positions(f.get("geometry"))


def rows(items, t, table="rows", point=("lat", "lng")):
    """A list of objects: each object a record. A latitude and longitude pair is a vertex, not two values."""
    lat, lng = point
    for r in items:
        if not isinstance(r, dict):
            continue
        if lat in r or lng in r:
            t.geometry = True
            if not missing(r.get(lat)) and not missing(r.get(lng)):
                t.vertices += 1
            r = {k: v for k, v in r.items() if k not in point}
        t.row(table, r)


def keyed_rows(obj, t, table="rows"):
    """An object of objects keyed by an id or a name (municipalities.json: one record for each municipio); the key is not a value."""
    rows([v for v in obj.values() if isinstance(v, dict)], t, table)


def series(doc, t, cols=(), island=()):
    """A series file: geo.ids (the areas, once) and vars [{key, years: {year: [one value per area]}, moe: {...}}]. A record is an area in a period with at
    least one value; a field is a variable, and its margin of error is a field of its own. cols are more fields of the same shape {year: [per area]};
    island are fields of Puerto Rico as a whole {year: value}, which join the island's record ('72') of that year."""
    tables = [(doc.get("level") or "area", doc["geo"]["ids"], doc.get("vars") or [], cols, island)]
    for lvl, sub in (doc.get("levels") or {}).items():   # population_age.json: the barrio and tract tables
        tables.append((lvl, sub["ids"], sub.get("vars") or [], (), ()))
    for name, ids, vars_, more, isl in tables:
        keys = set()

        def take(label, block, index=None):
            got = False
            for y, arr in (block or {}).items():
                if index is not None:
                    n = leaves(arr)
                    if n:
                        keys.add((index, str(y)))
                        t.values += n
                        got = True
                    continue
                if not isinstance(arr, list):
                    continue
                for i, x in enumerate(arr):
                    n = leaves(x)
                    if n:
                        keys.add((i, str(y)))
                        t.values += n
                        got = True
            if got:
                t.fields.add((name, label))

        for v in vars_:
            take(v["key"], v.get("years"))
            take(v["key"] + " (margin of error)", v.get("moe"))
        for label, block in more:
            take(label, block)
        pr = ids.index("72") if "72" in ids else "island"
        for label, block in isl:
            take(label, block, index=pr)
        t.records += len(keys)


def columns(doc, n, t, table="area", skip=("geo",), extra=()):
    """A columnar file: every list of length n (one value per record) under the document is a field, named by its path; a record is a position with at
    least one value. Lists of another length and objects of labels are metadata. extra: (field, [record index, ...]) for a flag stored as the list of
    the records that have it."""
    cols = []

    def walk(x, path):
        if isinstance(x, dict):
            for k, v in x.items():
                if not path and k in skip:
                    continue
                walk(v, f"{path}.{k}" if path else k)
        elif isinstance(x, list) and len(x) == n and path:
            cols.append((path, x))
    walk(doc, "")
    has = [False] * n
    for path, arr in cols:
        got = False
        for i, x in enumerate(arr):
            k = leaves(x)
            if k:
                t.values += k
                has[i] = True
                got = True
        if got:
            t.fields.add((table, path))
    for field, idx in extra:
        idx = [i for i in idx if isinstance(i, int) and 0 <= i < n]
        if idx:
            t.fields.add((table, field))
            t.values += len(idx)
            for i in idx:
                has[i] = True
    t.records += sum(has)


def a_series(name, doc, t):
    if name == "economy_series.json":
        ex = doc.get("extras") or {}
        series(doc, t, cols=[("top_sector", ex.get("top_sector"))],
               island=[(k, ex.get(k)) for k in ("fed_unplaced_share", "fema_pa_statewide_share")])   # the deflator (CPI) is a lookup table
    elif name == "housing_series.json":
        series(doc, t, island=[(f"tables.{k}", v) for k, v in (doc.get("tables") or {}).items()])   # the island's cost-burden distributions, every year
    else:
        series(doc, t)


def a_places(name, doc, t):
    rows(doc, t, "places")   # the withheld rows (counted, not drawn) are records too: they keep their category, municipio and flags


def a_hurricanes(name, doc, t):
    """A storm is a record. Its track is one field: each fix [lon, lat, time, wind, status] gives a vertex and three values."""
    t.geometry = True
    for s in doc:
        track = s.get("track") or []
        t.vertices += len(track)
        cells = {k: v for k, v in s.items() if k != "track"}
        cells["track"] = [fix[2:] for fix in track if isinstance(fix, list)]
        t.row("storms", cells)


def a_population_blocks(name, doc, t):
    """A 2020 census block with residents: [lon, lat, residents, metres to the nearest scheduled stop, metres walking]; the point is a vertex."""
    t.geometry = True
    for r in doc:
        t.vertices += 1
        t.row("blocks", dict(zip(("residents", "stop_m", "walk_m"), r[2:])))


def a_transit_supply(name, doc, t):
    """Scheduled service on each day type: tables of stop patterns, routes and stops, and one record a day for the island's hourly profile. The periods,
    thresholds and day labels are parameters (metadata)."""
    for day, d in (doc.get("days") or {}).items():
        for r in d.get("patterns") or []:
            t.row("patterns", r)
        for r in d.get("routes") or []:
            t.row("routes", r)
        for r in (d.get("stops") or {}).values():
            t.row("stops", r)
        t.row("island", {**(d.get("island") or {}), "trips_without_stop_ids": d.get("trips_without_stop_ids")})


def a_trips(name, doc, t):
    """Scheduled trips of one day: a trip is a record (route, mode, operator, path, stops, times); a path is a record of the paths table (kind and its
    stops), and its points [lon, lat, metres along] are vertices."""
    t.geometry = True
    for r in doc.get("trips") or []:
        if "p" in r:   # format 1 (before 2026-10-09): the trip carried its own points [lon, lat, seconds]
            pts = r.get("p") or []
            t.vertices += len(pts)
            r = {**{k: v for k, v in r.items() if k != "p"}, "t": [p[2] for p in pts if isinstance(p, list) and len(p) > 2]}
        t.row("trips", r)
    paths, kinds, stops = doc.get("paths") or [], doc.get("path_kind") or [], doc.get("path_stops") or []
    for i, p in enumerate(paths):
        t.vertices += len(p)
        t.row("paths", {"kind": kinds[i] if i < len(kinds) else None, "stops": stops[i] if i < len(stops) else None})


def a_operators(name, doc, t):
    """Transit operators, the transit coverage of each municipio and the transfer points between operators (a point is a vertex). The live-data notes
    and the transfer total are metadata."""
    rows(doc.get("operators") or [], t, "operators")
    keyed_rows(doc.get("coverage") or {}, t, "coverage")
    rows(doc.get("transfers") or [], t, "transfers")


def a_crosswalk(name, doc, t):
    """The geography crosswalk: one record for each area of every level (id, parent, names, area, residents, housing units; the internal point is a
    vertex), and one for each barrio and tract pair of the weights table. The levels list, totals and nesting figures are metadata."""
    fields = doc.get("fields") or []
    for lvl, units in (doc.get("units") or {}).items():
        rows([dict(zip(fields, u)) for u in units], t, "units")
    w = (doc.get("weights") or {}).get("barrio_tract") or {}
    for r in w.get("rows") or []:
        t.row("barrio_tract", dict(zip(w.get("fields") or [], r)))


def a_housing(name, doc, t):
    """The 2023 State of Housing study as published: the island figures (one record), the LIHTC table. The citation and links are metadata."""
    island = {k: doc.get(k) for k in ("grapi", "smocapi", "renters_burdened_pct", "owners_burdened_pct", "headline") if k in doc}
    t.row("study", island)
    rows(doc.get("lihtc") or [], t, "lihtc")


def a_landuse_summary(name, doc, t):
    """Land-use areas (km²) by class: one record for each municipio, Puerto Rico and the area no municipio holds. The classes list is the legend (a lookup)."""
    keyed_rows(doc.get("municipios") or {}, t, "areas")
    for k in ("puerto_rico", "unassigned"):
        if isinstance(doc.get(k), dict):
            t.row("areas", doc[k])


def a_place_access(name, doc, t):
    """Access to transit of each place of places.json, in the same order: one column per measure, and the places walked in a straight line as a list."""
    columns(doc, doc.get("n") or 0, t, "places", skip=(), extra=[("tw_straight", doc.get("tw_straight") or [])])


def a_wcrp_social(name, doc, t):
    """The Social Capital map: one record for each municipio (columns of 79), and one for each Comunidad Especial matched to the list, whose code holds
    one character per asset flag (1 yes, 0 no, - unknown: missing)."""
    columns(doc, len(doc["geo"]["ids"]), t, "municipios")
    a = doc.get("assets") or {}
    flags = a.get("flags") or []
    for code in (a.get("poly") or {}).values():
        t.row("communities", {f: (c if c in "01" else None) for f, c in zip(flags, code or "")})


def a_route_compare(name, doc, t):
    """The Route analysis (route_compare.json): one record for each bus route, and one for each operator (its name and the end date of its timetable).
    The description and the day and date of the timetables are metadata."""
    rows(doc.get("routes") or [], t, "routes")
    rows(doc.get("operators") or [], t, "operators")


def a_gii_profile(name, doc, t):
    """The Global Innovation Index (gii_profile.json, gii.py): one record for each of the 80 indicators (the 2021 value and rank, the updated value, the
    GII 2026 position). The pillars, the texts in both languages, the sources and the about block are metadata."""
    rows(doc.get("indicators") or [], t, "indicators")


def a_gii_changes(name, doc, t):
    """The Global Innovation Index's changes since 2020 (gii_changes.json, gii.py): one record for each edition compared, each of the 80 indicators of
    2020 (its GII 2026 code and status) and each indicator new in the GII 2026. The method texts and the sources are metadata."""
    rows(doc.get("editions") or [], t, "editions")
    rows(doc.get("crosswalk") or [], t, "crosswalk")
    rows([{k: v for k, v in r.items() if k not in ("name", "pr_note")} for r in doc.get("new_2026") or []], t, "new_2026")


def a_spending_state(name, doc, t):
    """The Commonwealth budget (spending_state.json, ogp_budget.py): one record for each agency, fund, concept of expense and function, whose fields are its
    dollars in each fiscal year and stage (columns). The agency names, the lists the rows index, the columns' sheets and totals and the notes are metadata."""
    cols = [f"{c['stage']}_{c['year']}" for c in doc.get("columns") or []]
    rows([{"agency": a, "fund": f, "concept": c, "function": fn, **dict(zip(cols, v))} for a, f, c, fn, v in doc.get("rows") or []], t, "rows")


def a_spending_pica(name, doc, t):
    """Capital projects by municipio (spending_pica.json, pica.py): one record for each municipio, whose fields are its dollars in each fiscal year, its
    dollars from each agency and its population. The years, the agency list, the unplaced dollars and the totals are metadata."""
    flat = {**{f"by_muni.{y}": a for y, a in zip(doc.get("years") or [], doc.get("by_muni") or [])}, "population": doc.get("population") or [],
            **{f"by_agency.{a}": m for a, m, u in doc.get("by_agency") or []}}
    columns(flat, len(doc["geo"]["ids"]), t, "municipio")


def a_spending_federal(name, doc, t):
    """Federal money in Puerto Rico by function (spending_federal.json, federal_awards.py): one record for each program (or contracting agency) and award
    type, whose fields are its dollars in each federal fiscal year. The lists the rows index, the agency names, USAspending's totals and the dedup and
    unmapped lists are metadata."""
    ys = doc.get("years") or []
    rows([{"code": c, "group": g, "function": fn, "confidence": cf, **{f"fy{y}": v for y, v in zip(ys, vals)}} for c, _n, g, fn, cf, vals in doc.get("rows") or []], t, "rows")


def a_spending_outlays(name, doc, t):
    """Federal grants and contracts obligated and paid out (spending_outlays.json, federal_outlays.py): one record for each program (or contract agency)
    and group, whose fields are its obligated and paid dollars in each signing year. The lists the rows index, the totals and the excluded programs
    are metadata."""
    ys = doc.get("years") or []
    rows([{"code": c, "group": g, "function": fn, "confidence": cf, **{f"obligated_fy{y}": v for y, v in zip(ys, o)}, **{f"paid_fy{y}": v for y, v in zip(ys, p)}}
          for c, _n, g, fn, cf, o, p in doc.get("rows") or []], t, "rows")


def a_unused_funds(name, doc, t):
    """Federal grants that ended with an unpaid balance (unused_funds.json, unused_funds.py): one record for each program line (assistance listing and
    awarding agency), with its grants, obligated and unpaid dollars. The agency and end-year sums, the totals and the programs kept apart are metadata."""
    rows([{"listing": c, "agency": a, "awards": n, "obligated": o, "unpaid": u} for c, _name, a, n, o, u in doc.get("listings") or []], t, "listings")


def a_taken_back(name, doc, t):
    """Federal grant money taken back (taken_back.json, taken_back.py): one record for each program line (assistance listing and awarding agency), with
    its grants and their net reduction. The agency and year sums, the totals, the counts read and the programs kept apart are metadata."""
    rows([{"listing": c, "agency": a, "awards": n, "net_reduction": v, "combined_awards": k} for c, _name, a, n, v, k in doc.get("listings") or []], t, "listings")


def a_audit_findings(name, doc, t):
    """Single audit findings (audit_findings.json, audit_findings.py): one record for each audit year, with its audits, findings and late audits. The
    tallies by kind of body, federal agency and program, and the totals, are metadata."""
    keys = ["audit_year", "audits", "audits_with_findings", "findings", "repeated", "material_weakness", "questioned_costs", "accepted_late", "median_months", "dollars_spent"]
    rows([dict(zip(keys, r)) for r in doc.get("by_year") or []], t, "by_year")


def a_spending_fema_pa(name, doc, t):
    """FEMA Public Assistance by stage and age (spending_fema_pa.json, fema_pa_stage.py): one record for each municipio, whose fields are its dollars and
    project counts by stage, the median age of its open money and its dollars open more than five years. The island, statewide, disaster and category
    sums are metadata."""
    m, st = doc.get("by_muni") or {}, doc.get("stages") or []
    flat = {**{f"usd.{s}": [v[k] for v in m.get("usd") or []] for k, s in enumerate(st)}, **{f"count.{s}": [v[k] for v in m.get("count") or []] for k, s in enumerate(st)},
            "median_age": m.get("median_age") or [], "over5_usd": m.get("over5_usd") or []}
    columns(flat, len(doc["geo"]["ids"]), t, "municipio")


def a_spending_municipio(name, doc, t):
    """Public money in each municipio's territory (spending_municipio.json, municipio_view.py): one record for each municipio, whose fields are its
    capital plan, subawards, FEMA dollars by stage, FEMA ages and federal awards. The years, context and ABRE year are metadata."""
    rows([{k: v for k, v in m.items() if k not in ("plan_top",)} for m in doc.get("municipios") or []], t, "municipios")


def a_spending_cdbgdr(name, doc, t):
    """Disaster recovery subawards by municipio (spending_cdbgdr.json, cdbg_dr.py): one record for each municipio, whose fields are its dollars in each
    federal fiscal year and its population. The grant numbers, the unplaced subawards and the totals are metadata."""
    flat = {**{f"by_muni.{y}": a for y, a in zip(doc.get("years") or [], doc.get("by_muni") or [])}, "population": doc.get("population") or []}
    columns(flat, len(doc["geo"]["ids"]), t, "municipio")


def a_spending_cdbg(name, doc, t):
    """HUD's yearly CDBG by municipio (spending_cdbg.json, cdbg_regular.py): one record for each municipio, whose fields are its entitlement grant and
    its state program subawards in each federal fiscal year, and its population. The grant numbers and the island totals are metadata."""
    ys = doc.get("years") or []
    flat = {**{f"entitlement.{y}": a for y, a in zip(ys, doc.get("entitlement") or [])}, **{f"state_by_muni.{y}": a for y, a in zip(ys, doc.get("state_by_muni") or [])},
            "population": doc.get("population") or []}
    columns(flat, len(doc["geo"]["ids"]), t, "municipio")


def a_inflation(name, doc, t):
    """Inflation in Puerto Rico and the US (inflation.json, inflation.py): one record for each month since 2000, whose fields are the two 12-month rates and
    the two index values; one for each projected month; one for each group. The backtest, the income and Social Security tables and the sources are metadata."""
    m = doc.get("monthly") or {}
    rows([{"pr_yoy": a, "us_yoy": b, "pr_index": c, "us_index": d} for a, b, c, d in zip(m.get("pr_yoy") or [], m.get("us_yoy") or [], m.get("pr_index") or [], m.get("us_index") or [])], t, "month")
    p = doc.get("projection") or {}
    rows([{"c": r[1], "lo80": r[2], "hi80": r[3], "lo95": r[4], "hi95": r[5]} for r in (p.get("pr_path") or []) + (p.get("us_path") or [])], t, "projected month")
    rows([{k: g.get(k) for k in ("weight", "pr_yoy", "us_yoy", "pr_since2020", "us_since2020")} for g in doc.get("groups") or []], t, "group")


def a_columns(name, doc, t):
    columns(doc, len(doc["geo"]["ids"]), t, doc.get("level") or "area")


def a_nightlights_monthly(name, doc, t):
    """Night-time lights by month (nightlights.py): one record for each area (municipio, Puerto Rico, barrio) in each month, whose fields are the mean
    radiance and the quality share. The months and the units are metadata."""
    for level in ("municipio", "barrio"):
        blk = doc.get(level) or {}
        rad, poor = blk.get("ntl_radiance") or [], blk.get("ntl_poor_pct") or []
        for a, b in zip(rad, poor):
            for x, y in zip(a, b):
                t.row(level, {"ntl_radiance": x, "ntl_poor_pct": y})


def a_women_labor(name, doc, t):
    """Women in the labor force (women_labor.json, women_labor.py): one record for each area (the island and the 78 municipios) in each five-year window, whose
    fields are the estimate and the margin of the population 16 and over, the labor force, the civilian labor force and the unemployed, for each sex and age group
    (f.25-34.lf), the women 20 to 64 by own children (kids.u6.lf) and the survey's sample (sample.people). The names, the groups of municipios, the texts and
    the precomputed analysis are metadata: they repeat or combine those counts."""
    ages, cells = doc.get("ages") or [], doc.get("cells") or []
    for w, areas in (doc.get("areas") or {}).items():
        for g, rec in areas.items():
            row = {}
            for sex in ("m", "f"):
                for a, grp in zip(ages, rec.get(sex) or []):
                    for c, e in zip(cells, grp):
                        row[f"{sex}.{a}.{c}"] = e
            for k, v in (rec.get("kids") or {}).items():
                for c, e in zip(cells, v):
                    row[f"kids.{k}.{c}"] = e
            if rec.get("sample"):
                row["sample"] = rec["sample"]
            t.row("areas", row)


def a_regions(name, doc, t):
    """The regions (geo/regions.json, regions.py): one record for each region (id, kind, its names, its source, how many municipios); each region's
    municipio codes and names are the region's membership, counted as one field."""
    rows([{"id": r.get("id"), "kind": r.get("kind"), "name": r.get("name"), "source": r.get("source"), "municipios": r.get("ids")} for r in doc.get("regions") or []], t, "regions")


def a_roads(name, raw, t):
    """roads.bin (roads.py): header "PRRD", u32 version, n_nodes, n_edges, n_shape. An edge (a road segment) is a record with three fields (length,
    road class, one-way); its two end nodes are topology. Nodes and interior shape points are vertices."""
    if raw[:4] != b"PRRD" or len(raw) < 20:
        raise ValueError("not a roads.bin file")
    _, n_nodes, n_edges, n_shape = struct.unpack_from("<IIII", raw, 4)
    t.geometry = True
    t.records += n_edges
    t.values += 3 * n_edges
    t.fields |= {("edges", "length"), ("edges", "class"), ("edges", "one_way")}
    t.vertices += n_nodes + n_shape


def a_oz(name, doc, t):
    """opportunity_zones.json (opportunity_zones.py): three tables of rows whose column names are listed beside them (tracts with tract_fields, barrios with
    barrio_fields, municipios with muni_fields); each row is a record and a tract's list of barrios one value. Puerto Rico's totals, the medians by status and
    the first round are summaries of these records, not counted again."""
    for table, fk in (("tracts", "tract_fields"), ("barrios", "barrio_fields"), ("municipios", "muni_fields")):
        cols = doc.get(fk) or []
        rows([dict(zip(cols, r)) for r in doc.get(table) or []], t, table)


def a_tlinks(name, doc, t):
    """transit_links.json (transit_links.py): two tables of rows whose column names are listed beside them (pairs with pair_fields, municipios with
    muni_fields); each row is a record and a pair's list of operators one value. Puerto Rico's totals by status are summaries of these records."""
    for table, fk in (("pairs", "pair_fields"), ("municipios", "muni_fields")):
        cols = doc.get(fk) or []
        rows([dict(zip(cols, r)) for r in doc.get(table) or []], t, table)


def a_energy(name, doc, t):
    """energy.json (energy_series.py): one record for each month since 2010 (production by source, rooftop solar, the RPS share), one for each municipio
    (batteries, sales, smart meters), one for each LUMA commercial district, one for each month of SAIDI and of the price. Totals and the flood figures are
    summaries."""
    s = doc.get("series") or {}
    g = s.get("gen_gwh") or {}
    rows([{**{k: g[k][i] for k in g}, "rps_pct": s["rps_pct"][i], "rooftop_customers": s["rooftop_customers"][i], "rooftop_mw": s["rooftop_mw"][i], "exported_gwh": s["exported_gwh"][i]}
          for i in range(len(s.get("months") or []))], t, "month")
    m = doc.get("municipios") or {}
    cols = ("hu", "pop", "bess", "bess_kwh", "sales_gwh_12m", "ami_pct")
    rows([{k: m[k][i] for k in cols} for i in range(len(m.get("ids") or []))], t, "municipio")
    rows([dict(zip(doc["districts"]["fields"], r)) for r in (doc.get("districts") or {}).get("rows") or []], t, "district")
    sa = doc.get("saidi") or {}
    rows([{"td": a, "dist": b} for a, b in zip(sa.get("td") or [], sa.get("dist") or [])], t, "SAIDI month")
    p = doc.get("price") or {}
    rows([{"pr": a, "us": b} for a, b in zip(p.get("pr") or [], p.get("us") or [])], t, "price month")


SERIES = {"acs_barrio.json", "acs_blockgroup.json", "acs_tract.json", "bridges_series.json", "traffic_series.json", "crashes_series.json", "care_series.json", "community_series.json", "conditions_barrio.json",
          "conditions_series.json", "economy_series.json", "education_series.json", "environment_series.json", "facility_series.json", "gateway_series.json",
          "hazard_series.json", "health_series.json", "housing_series.json", "infrastructure_series.json", "infrastructure_barrio.json", "energy_series.json", "energy_barrio.json", "labor_sex_series.json", "landslide_barrio.json", "landslide_series.json", "heat_barrio.json", "heat_series.json", "vegetation_barrio.json", "vegetation_series.json", "buildings_barrio.json", "buildings_series.json", "fires_series.json", "night_heat_barrio.json", "night_heat_series.json", "climb_barrio.json", "climb_series.json", "slope_barrio.json", "slope_series.json", "nightlights_barrio.json", "nightlights_series.json", "broadband_barrio.json", "broadband_series.json",
          "medicare_series.json", "nonprofit_series.json", "population_age.json", "population_series.json", "commuting_series.json", "svi_series.json", "svi_tract.json", "credit_series.json", "drought_series.json", "storm_recovery_series.json", "storm_recovery_barrio.json", "essentials_series.json", "essentials_barrio.json", "cutoff_series.json", "cutoff_barrio.json", "degrees_series.json", "school_conditions_series.json", "proficiency_series.json", "providers_series.json", "facility_exposure_series.json", "wcrp_rvi_barrio.json"}
SPECIAL = {"places.json": a_places, "upstream.json": lambda n, d, t: rows(d["sites"], t, "sites"), "facility_hazards.json": lambda n, d, t: rows([{"layer": k, "point": p, "hz": c} for k, m in d["layers"].items() for p, c in m.items()], t, "flagged points"), "transport.json": lambda n, d, t: rows(d, t, "stops"), "hurricanes.json": a_hurricanes,
           "municipalities.json": lambda n, d, t: keyed_rows(d, t, "municipios"), "population_blocks.json": a_population_blocks,
           "transit_supply.json": a_transit_supply, "trips.json": a_trips, "trips_sa.json": a_trips, "trips_su.json": a_trips, "operators.json": a_operators,
           "geo/crosswalk.json": a_crosswalk, "housing.json": a_housing, "landuse_summary.json": a_landuse_summary, "place_access.json": a_place_access,
           "wcrp_social.json": a_wcrp_social, "wcrp_rvi_inputs.json": a_columns, "exposure_municipio.json": a_columns, "exposure_barrio.json": a_columns,
           "exposure_tract.json": a_columns, "route_compare.json": a_route_compare, "gii_profile.json": a_gii_profile,
           "gii_changes.json": a_gii_changes, "women_labor.json": a_women_labor, "geo/regions.json": a_regions,
           "public_money_need.json": a_columns, "opportunity_zones.json": a_oz, "transit_links.json": a_tlinks, "urban_heat.json": a_columns, "reservoir_history.json": lambda n, d, t: rows(d["reservoirs"], t, "reservoirs"), "inflation.json": a_inflation, "energy.json": a_energy, "spending_state.json": a_spending_state, "spending_pica.json": a_spending_pica, "spending_federal.json": a_spending_federal, "spending_outlays.json": a_spending_outlays, "unused_funds.json": a_unused_funds, "taken_back.json": a_taken_back, "audit_findings.json": a_audit_findings, "spending_fema_pa.json": a_spending_fema_pa, "spending_municipio.json": a_spending_municipio, "spending_cdbgdr.json": a_spending_cdbgdr, "spending_cdbg.json": a_spending_cdbg, "nightlights_monthly.json": a_nightlights_monthly}
FAMILY = {**{n: "series" for n in SERIES}, **{n: "special" for n in SPECIAL}}


def kinds(path=DATASETS):
    """{file: kind} from the data contract: a file whose primary domain is system.docs is documentation, system.tools an index; the rest are data."""
    try:
        recs = json.loads(Path(path).read_text(encoding="utf-8"))["datasets"]
    except (OSError, ValueError, KeyError):
        return {}
    out = {}
    for r in recs:
        top = (r.get("domains") or [""])[0]
        out[r["file"]] = "documentation" if top == "system.docs" else "index" if top == "system.tools" else "data"
    return out


def a_surface_png(name, raw, t):
    """heat_surface.png (surface_image.py): an 8-bit indexed PNG whose index 0 is transparent. Each drawn pixel (index above 0) is a record with one value (its
    colour step). No vertices: it is a picture, not a geometry."""
    import struct
    import zlib
    if raw[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError(f"{name} is not a PNG")
    i, w, h, idat = 8, 0, 0, b""
    while i < len(raw):
        n = struct.unpack(">I", raw[i:i + 4])[0]; typ = raw[i + 4:i + 8]; data = raw[i + 8:i + 8 + n]
        if typ == b"IHDR":
            w, h = struct.unpack(">II", data[:8])
        elif typ == b"IDAT":
            idat += data
        i += 12 + n
    px = zlib.decompress(idat)
    drawn = sum(len(px[r * (w + 1) + 1:(r + 1) * (w + 1)].replace(b"\x00", b"")) for r in range(h))   # each row starts with its filter byte (0)
    t.records += drawn; t.values += drawn
    if drawn:
        t.fields.add(("pixels", "colour step"))


def a_pmtiles(name, raw, t):
    """buildings_gap.pmtiles (buildings3d.py): a PMTiles v3 file of vector tiles. Each building at zoom 14 is a record (one on a tile edge counts in each tile)
    with its outline and up to two fields (height, base height); the counts are in the file's metadata, written by buildings3d.py, so the tiles are not decoded here."""
    if raw[:7] != b"PMTiles" or raw[7] != 3:
        raise ValueError("not a PMTiles v3 file")
    off, length = struct.unpack_from("<QQ", raw, 24)
    meta = json.loads(gzip.decompress(raw[off:off + length]) if raw[97] == 2 else raw[off:off + length])
    t.records += int(meta["features_z14"])
    t.values += int(meta["features_z14"]) + int(meta["values_z14"])   # each outline is a value, and each height or base height
    t.fields |= {("buildings", "outline")} | {("buildings", f) for f in meta["vector_layers"][0]["fields"]}


def family(name):
    """The adapter family of a published file, or None when no adapter knows it (a test makes sure every published data file has one)."""
    if name in FAMILY:
        return FAMILY[name]
    if ("heat_surface" in name or name.startswith("slope_surface")) and name.endswith(".png"):   # heat_surface.png, night_heat_surface.png, slope_surface.png
        return "image"
    if ("heat_surface" in name or name.startswith("slope_surface")) and name.endswith(".json"):
        return "meta"
    if name.endswith(".geojson"):
        return "geojson"
    if name == "roads.bin":
        return "binary"
    if name.endswith(".pmtiles"):
        return "tiles"
    return None


def count(name, raw, kind="data"):
    """{records, fields, values, vertices} of a file's bytes, or all None for documentation, index files and files no adapter knows."""
    empty = {"records": None, "fields": None, "values": None, "vertices": None}
    if kind != "data":
        return empty
    fam = family(name)
    t = Tally()
    if fam == "binary":
        a_roads(name, raw, t)
        return t.result()
    if fam == "image":
        a_surface_png(name, raw, t)
        return t.result()
    if fam == "tiles":
        a_pmtiles(name, raw, t)
        return t.result()
    if fam is None:
        return empty
    doc = json.loads(raw.decode("utf-8"))
    if fam == "meta":   # one record: the description of an image (its corners, size and scale)
        t.row("meta", {k: v for k, v in doc.items() if k != "built"})
        return t.result()
    if fam == "geojson":
        geojson(doc, t)
    elif fam == "series":
        a_series(name, doc, t)
    else:
        SPECIAL[name](name, doc, t)
    return t.result()


def fields_of(name, raw):
    """The (table, field) pairs counted for a file, for checking by hand (python ledger.py --count FILE --fields)."""
    t = Tally()
    doc = json.loads(raw.decode("utf-8"))
    fam = family(name)
    if fam == "geojson":
        geojson(doc, t)
    elif fam == "series":
        a_series(name, doc, t)
    else:
        SPECIAL[name](name, doc, t)
    return sorted(t.fields)


# ── Content hash and size ────────────────────────────────────────────────────

def strip_stamps(x, in_record=False):
    """The document without its build stamps. A key inside a list (a record of a table or a feature) is data and stays."""
    if isinstance(x, dict):
        return {k: strip_stamps(v, in_record) for k, v in x.items() if in_record or k not in STAMPS}
    if isinstance(x, list):
        return [strip_stamps(v, True) for v in x]
    return x


def lf(raw, name):
    return raw if name.endswith((".bin", ".png", ".pmtiles")) else raw.replace(b"\r\n", b"\n")


def content_hash(name, raw):
    if name.endswith((".json", ".geojson")):
        try:
            doc = json.loads(raw.decode("utf-8"))
        except ValueError:
            doc = None
        if doc is not None:
            canon = json.dumps(strip_stamps(doc), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            return "j" + hashlib.sha256(canon.encode("utf-8")).hexdigest()[:16]
    return "b" + hashlib.sha256(lf(raw, name)).hexdigest()[:16]


def items_of(name, raw):
    """Entries of a documentation file (dictionary, catalog, wish list), for the table's 'what it holds'."""
    if not name.endswith(".json"):
        return None
    try:
        j = json.loads(raw.decode("utf-8"))
    except ValueError:
        return None
    if not isinstance(j, dict):
        return None
    for k in ("items", "entries"):
        if isinstance(j.get(k), (list, dict)):
            return len(j[k])
    if isinstance((j.get("index") or {}).get("rows"), list):
        return len(j["index"]["rows"])
    if isinstance(j.get("words_es"), dict):
        return len(j["words_es"])
    return None


def describe(name, raw, kind):
    """What the ledger keeps about one version of a file."""
    out = {"kind": kind, "hash": content_hash(name, raw), "bytes": len(lf(raw, name)), **count(name, raw, kind)}
    if kind != "data":
        out["items"] = items_of(name, raw)
    return out


def current(data_dir=DATA, kind_of=None):
    """{file: describe()} for every published file of the working tree but registry.json."""
    kind_of = kinds() if kind_of is None else kind_of
    out = {}
    for name, p in contract.published_files(data_dir):
        if name in NOT_LISTED:
            continue
        out[name] = describe(name, p.read_bytes(), kind_of.get(name, "data"))
    return out


# ── Ledger ───────────────────────────────────────────────────────────────────

def documented_items(data_dir=DATA):
    p = Path(data_dir) / "dictionary.json"
    try:
        return len(json.loads(p.read_text(encoding="utf-8"))["entries"])
    except (OSError, ValueError, KeyError):
        return None


def totals(files, items):
    """The totals of a set of described files: records, fields and values over the counted (data) files; bytes over all."""
    s = lambda k: sum(f[k] or 0 for f in files.values())
    return {"files": len(files), "bytes": s("bytes"), "records": s("records"), "fields": s("fields"), "values": s("values"), "items": items}


def empty_ledger():
    return {"version": VERSION, "about": "Written by registry.py on every build (ledger.update) and rebuilt from git by python ledger.py --backfill; docs/data-management.md. "
            "first_published never moves; last_updated is the date of the build (or, before 2026-10-19, of the merge into main) that last changed the file's content hash; "
            "versions counts the content versions published. Dates are Puerto Rico dates (UTC-4). On a merge conflict, take main's version of this file and run python registry.py.",
            "files": {}, "removed": {}, "history": []}


def load(path=LEDGER):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return empty_ledger()


def dump(led, path=LEDGER):
    Path(path).write_text(json.dumps(led, indent=1, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")


def update(led, cur, items, day):
    """The ledger after a build on `day` whose files are `cur` (current()). A file whose content hash changed gets last_updated = day and one more version;
    a new file gets first_published = day (or its old date, when it was published before and removed); first_published never moves. Counts and sizes
    follow the files. The history gets a row for `day` when the totals differ from the last row (a second build on the same day replaces that row).
    Returns (ledger, the files whose content changed)."""
    led = json.loads(json.dumps(led))   # a copy
    files, removed, changed = led.setdefault("files", {}), led.setdefault("removed", {}), []
    for name in sorted(cur):
        c, old = cur[name], files.get(name)
        if old is None:
            back = removed.pop(name, None)
            files[name] = {"first_published": back["first_published"] if back else day, "last_updated": day, "versions": (back or {}).get("versions", 0) + 1, **c}
            changed.append(name)
            continue
        if old.get("hash") != c["hash"]:
            old["last_updated"] = day
            old["versions"] = old.get("versions", 1) + 1
            changed.append(name)
        for k in [k for k in old if k not in c and k not in ("first_published", "last_updated", "versions")]:
            del old[k]
        old.update(c)
    for name in [n for n in files if n not in cur]:
        rec = files.pop(name)
        rec["removed"] = day
        removed[name] = rec
        changed.append(name)
    led["files"] = dict(sorted(files.items()))
    row = {"date": day, **totals(cur, items)}
    hist = led.setdefault("history", [])
    if not hist or {k: hist[-1].get(k) for k in TOTAL_KEYS} != {k: row[k] for k in TOTAL_KEYS}:
        if hist and hist[-1]["date"] == day:
            hist[-1] = row
        else:
            hist.append(row)
    return led, changed


def problems(led, cur, items):
    """What --check reports: the ledger does not describe the files as they are (dates are never compared with today)."""
    P = []
    files = led.get("files", {})
    for name in sorted(set(cur) | set(files)):
        if name not in files:
            P.append(f"{name} is published but not in the ledger")
        elif name not in cur:
            P.append(f"{name} is in the ledger but no longer published")
        else:
            for k, v in cur[name].items():
                if files[name].get(k) != v:
                    P.append(f"{name}: {k} is {files[name].get(k)!r} in the ledger, {v!r} in the file")
                    break
            f = files[name]
            if not (f.get("first_published") and f.get("last_updated") and f["first_published"] <= f["last_updated"]):
                P.append(f"{name}: first_published {f.get('first_published')} must be on or before last_updated {f.get('last_updated')}")
    hist = led.get("history") or []
    want = totals(cur, items)
    if not hist or {k: hist[-1].get(k) for k in TOTAL_KEYS} != want:
        P.append(f"the last row of the history is not the current totals ({want})")
    if [h["date"] for h in hist] != sorted({h["date"] for h in hist}):
        P.append("the history has two rows for a date or is out of order")
    return P


# ── Backfill from git ────────────────────────────────────────────────────────

def git(*args):
    return subprocess.run(["git", *args], cwd=ROOT, check=True, capture_output=True).stdout


class Blobs:
    """Reads git blobs through one `git cat-file --batch` process."""

    def __init__(self):
        self.p = subprocess.Popen(["git", "cat-file", "--batch"], cwd=ROOT, stdin=subprocess.PIPE, stdout=subprocess.PIPE)

    def read(self, sha):
        self.p.stdin.write(sha.encode() + b"\n")
        self.p.stdin.flush()
        head = self.p.stdout.readline().split()
        size = int(head[2])
        data = self.p.stdout.read(size)
        self.p.stdout.read(1)
        return data

    def close(self):
        self.p.stdin.close()
        self.p.wait()


def backfill(ref="origin/main", log=print):
    """A ledger rebuilt from the first-parent history of `ref`: each commit that reached it is a publication on its Puerto Rico date. A file's
    first_published is the date of the first such commit that holds it; last_updated the date of the last one that changed its content hash; versions
    the number of content hashes it had. The history has the totals at the end of each date on which they changed. Counts of old versions use today's
    adapters; a version they cannot read keeps the counts of the version before it (said in the log)."""
    kind_of = kinds()
    commits = [l.split() for l in git("log", "--first-parent", "--reverse", "--format=%H %ct %P", ref).decode().splitlines()]
    blobs, cache = Blobs(), {}
    state, led, last_day, docs = {}, empty_ledger(), None, None
    try:
        for c in commits:
            sha, ts, parents = c[0], int(c[1]), c[2:]
            day = datetime.fromtimestamp(ts, PR_TZ).date().isoformat()
            if parents:
                out = git("diff-tree", "-r", "--no-commit-id", "--no-renames", parents[0], sha, "--", "site/data").decode().splitlines()
            else:
                out = git("ls-tree", "-r", sha, "--", "site/data").decode().splitlines()
                out = [f":000000 {l.split()[0]} 0 {l.split()[2]} A\t{l.split(chr(9))[1]}" for l in out]
            touched = False
            for line in out:
                meta, path = line.split("\t", 1)
                parts = meta.split()
                status, new = parts[-1], parts[3]
                if not path.startswith("site/data/"):
                    continue
                name = path[len("site/data/"):]
                if "/" in name and name.split("/")[0] not in contract.SUBDIRS:
                    continue
                if name in NOT_LISTED:
                    continue
                touched = True
                if status == "D":
                    state.pop(name, None)
                    continue
                if new not in cache:
                    raw = blobs.read(new)
                    try:
                        cache[new] = describe(name, raw, kind_of.get(name, "data"))
                    except Exception as e:   # an old format today's adapter cannot read: keep the counts of the version before, with its new hash and size
                        prev = state.get(name) or {}
                        cache[new] = {**prev, "kind": kind_of.get(name, "data"), "hash": content_hash(name, raw), "bytes": len(lf(raw, name))}
                        log(f"  {day} {name}: counts of the version before kept ({e.__class__.__name__}: {e})")
                    if name == "dictionary.json":
                        try:
                            cache[new]["_entries"] = len(json.loads(raw.decode("utf-8"))["entries"])
                        except (ValueError, KeyError):
                            pass
                state[name] = cache[new]
            if not touched:
                continue
            if "dictionary.json" in state:
                docs = state["dictionary.json"].get("_entries", docs)
            cur = {n: {k: v for k, v in d.items() if not k.startswith("_")} for n, d in state.items()}
            led, _ = update(led, cur, docs, day)
            last_day = day
    finally:
        blobs.close()
    log(f"backfill: {len(commits)} commits of {ref}, {len(led['files'])} files, {len(led['history'])} history rows, last {last_day}")
    return led


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if argv and argv[0] == "--count":
        kind_of = kinds()
        names = [a for a in argv[1:] if not a.startswith("--")]
        for name in names:
            raw = (DATA / name).read_bytes()
            d = describe(name, raw, kind_of.get(name, "data"))
            print(f"{name}: {json.dumps(d)}")
            if "--fields" in argv and d.get("records") is not None and family(name) != "binary":
                for table, f in fields_of(name, raw):
                    print(f"   {table}: {f}")
        return 0
    if argv and argv[0] == "--backfill":
        ref = argv[1] if len(argv) > 1 else "origin/main"
        led = backfill(ref)
        dump(led)
        print(f"wrote {LEDGER.relative_to(ROOT)}; now run python registry.py to add the working tree's changes")
        return 0
    print(__doc__)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
