"""Refresh only the transit network files in site/data (runs nightly on GitHub, takes about a minute).

Re-reads the feed registry, downloads every operator's GTFS feed and the OpenStreetMap routes, and rewrites:
  transit_routes.geojson, trips.json, trips_sa.json, trips_su.json, operators.json, population_blocks.json,
  the scheduled stops inside transport.json, and the transit fields of municipalities.json and meta.json.
It then runs access.py, which recomputes from those stops how close each tourism place is to a stop with a current timetable
(place_access.json, the access fields of municipalities.json and meta.json, and the transit_m / transit_400m / nearest_stop fields of places.json),
and catalog.py, which rewrites catalog.json only when a headline figure or the index changed (the Overview of the map reads it),
and registry.py last, which moves the last-updated date of every file whose content changed in the ledger (dictionary_src/data_ledger.json, committed with the data)
and rewrites registry.json only when something other than the date changed (docs/data-management.md).
It also recomputes the six transit families of the exposure series (exposure_municipio.json, exposure_barrio.json, exposure_tract.json: residents and housing units within
400 m of a stop), from the same stops and timetable end dates, writing only what changed. A failure there never stops the transit refresh.
It writes transit_supply.json (supply.py: scheduled service by stop pattern, route and stop, hour by hour) on every run, when it changed.
Everything else (places, flood, land use, housing, barrios, OSM stops, airports) is left as the last full build wrote it.
Run a full `build.py` for those. Nothing is written when no feed changed, so the nightly job commits only real changes.

    python refresh_network.py            # normal
    python refresh_network.py --force    # write even if nothing changed
    python refresh_network.py --offline  # read the feeds from cache/network instead of downloading them again (development; a missing file is still fetched)
"""

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path

from shapely.geometry import shape

import access
import catalog
import exposure
import muni_locate
import network
import registry
import supply
import trip_paths
from municipalities import MUNICIPALITIES

ROOT = Path(__file__).resolve().parent
CACHE = ROOT / "cache"
OUT = ROOT / "site" / "data"


def load(name):
    return json.loads((OUT / name).read_text(encoding="utf-8"))


def dump(name, data):
    (OUT / name).write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"  wrote {name}")


def refresh_exposure():
    """The transit families of the exposure series follow the stops and the timetable end dates. The series must never stop the transit refresh, so any failure is only reported."""
    try:
        exposure.apply_transit(OUT, date.today())
    except BaseException as e:   # SystemExit included: a stale series is better than a blocked refresh
        print(f"  exposure series not refreshed: {type(e).__name__}: {e}")   # str(e) names the file; repr(e) does not


def refresh_climb():
    """The climb on the walk to a stop follows the same walkers as the exposure files (climb.py). Like them it must never stop the transit refresh."""
    try:
        import climb
        climb.build()
    except BaseException as e:
        print(f"  climb on the walks not refreshed: {type(e).__name__}: {e}")


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--offline", action="store_true", help="use the feeds, registry and OpenStreetMap routes already in cache/ (only a file that is missing there is downloaded)")
    args = ap.parse_args()
    CACHE.mkdir(exist_ok=True)

    names = {network.norm(m["name"]): m["name"] for m in MUNICIPALITIES}
    net = network.build_network(CACHE, not args.offline, names, date.today(), roads=network.load_roads(OUT), previous=network.previous_routes(OUT))

    # safety: a failed download must never degrade the published site
    withfeed = sum(1 for o in net["operators"].values() if o["feed"]["status"] in ("current", "expiring", "expired"))
    if withfeed < 20:
        sys.exit(f"Only {withfeed} operators returned a feed (expected about 25); not publishing.")
    if "osm" not in net["operators"]:   # Overpass was unavailable: keep the OpenStreetMap routes from the last build
        try:
            old_routes = [f for f in load("transit_routes.geojson")["features"] if f["properties"].get("operator") == "osm"]
            old_op = next((o for o in load("operators.json")["operators"] if o["id"] == "osm"), None)
        except FileNotFoundError:
            old_routes, old_op = [], None
        if old_routes and old_op:
            print(f"  Overpass unavailable: keeping {len(old_routes)} OpenStreetMap routes from the last build")
            net["routes"] += old_routes
            net["operators"]["osm"] = old_op

    # municipality of each stop, and county code -> municipality, from the published boundaries
    muni_fc = load("municipios.geojson")
    geoms, gnames, by_fips = [], [], {}
    for ft in muni_fc["features"]:
        n = ft["properties"].get("municipality")
        if not n:
            continue
        geoms.append(shape(ft["geometry"])); gnames.append(n)
        by_fips[str(ft["properties"].get("GEOID"))[:5]] = n
    locate = muni_locate.Locator(geoms, gnames)
    try:
        old_transport = load("transport.json")
    except FileNotFoundError:
        old_transport = []
    for s in net["stops"]:   # as the full build does: the outline that holds the stop, else (a pier or a shoreline stop) the nearest outline (muni_locate.py)
        s["municipality"] = locate(s["lat"], s["lng"])

    inactive = {k for k, o in net["operators"].items() if o["feed"]["status"] == "expired"}
    import walknet
    blocks, cov = network.coverage(network.load_blocks(CACHE / "network", False), net["stops"], by_fips, inactive, net=walknet.load(OUT / "roads.bin"))   # residents also by walking
    xfers, n_xfers = network.transfers(net["stops"])

    operators = sorted(net["operators"].values(), key=lambda o: (o["feed"]["status"] in ("none",), o["type"] != "regional", o["short"] or o["name"]))
    ops_doc = {"built": net["built"], "operators": operators, "live": {"checked": network.LIVE_CHECKED, "sources": network.LIVE_SOURCES}, "coverage": cov, "transfers": xfers, "transfers_total": n_xfers}

    # nothing to do when the content is unchanged (the build date alone is not a change)
    try:
        old = load("operators.json")
    except FileNotFoundError:
        old = {}
    same = {k: v for k, v in old.items() if k != "built"} == {k: v for k, v in json.loads(json.dumps(ops_doc)).items() if k != "built"}
    routes_fc = {"type": "FeatureCollection", "features": net["routes"]}
    try:
        same = same and load("transit_routes.geojson") == json.loads(json.dumps(routes_fc))
    except FileNotFoundError:
        same = False
    same = same and [f for f in old_transport if f.get("source") in ("ati_gtfs", "muni_gtfs")] == json.loads(json.dumps(net["stops"]))
    if same and not args.force:
        print("No transit feed changed; nothing written.")
        access.apply_files(OUT, date.today())   # still recomputed: it writes only when a value changed
        refresh_exposure()                      # residents and housing units near a stop, in the exposure files, only when a value changed
        catalog.apply()                         # the Overview headline of residents near a stop follows municipalities.json
        supply.apply(OUT)                       # transit_supply.json: whether each timetable is current changes with the date, so it is recomputed (written only when it changed)
        registry.apply()                        # the ledger and registry.json, last: only the files whose content changed get a new last-updated date
        return

    dump("transit_routes.geojson", routes_fc)
    dump("trips.json", trip_paths.trip_doc("weekday (typical Wednesday service)", net["trips"]["wk"], net["trip_paths"]["wk"]))   # vehicles follow the route lines
    for d, label in (("sa", "Saturday"), ("su", "Sunday")):
        dump(f"trips_{d}.json", trip_paths.trip_doc(label, net["trips"][d], net["trip_paths"][d]))
    dump("operators.json", ops_doc)
    dump("population_blocks.json", blocks)

    # scheduled stops live inside transport.json next to the OpenStreetMap stops and airports, which stay as they are
    transport = [f for f in load("transport.json") if f.get("source") not in ("ati_gtfs", "muni_gtfs")]
    dump("transport.json", transport + net["stops"])

    stats = load("municipalities.json")
    muni_op = {o["municipality"]: o for o in net["operators"].values() if o.get("municipality")}
    for n, st in stats.items():
        c = cov.get(n, {})
        st.update({"pop_served_400m": c.get("served"), "pop_served_pct": c.get("served_pct"), "pop_served_active_pct": c.get("served_active_pct"), "pop_served_ati": c.get("served_ati"), "pop_served_muni": c.get("served_muni"),
                   "pop_walk_400m": c.get("walk_served"), "pop_walk_pct": c.get("walk_served_pct"), "pop_walk_active_pct": c.get("walk_served_active_pct")})   # walking along mapped roads (network.coverage)
        o = muni_op.get(n)
        st["muni_system"] = o["feed"]["status"] if o else None
        st["muni_system_routes"] = o["routes"] if o else 0
    dump("municipalities.json", stats)

    meta = load("meta.json")
    status = {}
    for o in net["operators"].values():
        status[o["feed"]["status"]] = status.get(o["feed"]["status"], 0) + 1
    meta["network"] = {"built": net["built"], "operators": len(net["operators"]), "by_status": dict(sorted(status.items())), "routes": len(net["routes"]), "scheduled_stops": len(net["stops"]),
                       "weekday_trips": len(net["trips"]["wk"]), "residents": sum(c["pop"] for c in cov.values()), "residents_within_400m": sum(c["served"] for c in cov.values()),
                       "residents_walk_400m": sum(c.get("walk_served", 0) for c in cov.values())}
    dump("meta.json", meta)
    access.apply_files(OUT, date.today())   # place_access.json, the access fields of municipalities.json and meta.json, the transit_* fields of places.json
    refresh_exposure()                      # the transit families of the three exposure files
    refresh_climb()                         # the climb on the walk to a current stop (climb.py), after the walkers above
    catalog.apply()                         # catalog.json: the headline figure of residents near a stop and the file weights, only when something changed
    supply.apply(OUT)                       # transit_supply.json: service by stop pattern, route and stop, hour by hour
    registry.apply()                        # the ledger (dictionary_src/data_ledger.json) and registry.json, last, so they describe every file written above
    print("Transit network refreshed.")


if __name__ == "__main__":
    main()
