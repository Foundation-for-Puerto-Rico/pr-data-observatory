"""Shared loaders for the access spike (READ-ONLY on the repository).

Everything is read from the repository's published files in site/data/. Nothing is written inside the repository.
Outputs go to the folder this file lives in.
"""
import sys
sys.dont_write_bytecode = True     # never write .pyc files into the repository when importing its modules
import json
import math
import time
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

import numpy as np
from pyproj import Transformer
from shapely import STRtree, points

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]             # docs/analysis/visitor-access-2026-10 -> the repository root
DATA = REPO / "site" / "data"

AS_OF = date(2026, 10, 5)          # today's date in this session; feed status is recomputed against it
MIN_CONF = 0.5                     # app default (S.conf = 0.5) and build.py MIN_CONF
ACCESS_KINDS = {"transit_stop", "bus_stop", "bus_station", "rail_station", "ferry_terminal"}   # transport.py access_kinds
SCHEDULED_SOURCES = {"ati_gtfs", "muni_gtfs"}
CATS = ["ACCOMMODATIONS", "ATTRACTIONS", "GASTRONOMY", "VISITOR_SERVICES"]

_to_xy = Transformer.from_crs("EPSG:4326", "EPSG:32161", always_xy=True)   # NAD83 / Puerto Rico & Virgin Is. (meters)


def to_xy(lng, lat):
    x, y = _to_xy.transform(np.asarray(lng, dtype=float), np.asarray(lat, dtype=float))
    return np.asarray(x), np.asarray(y)


def jload(name):
    with open(DATA / name, encoding="utf-8") as f:
        return json.load(f)


import unicodedata as _ud
import re as _re


def slug(s):
    return _re.sub(r"[^a-z0-9]+", "_", "".join(c for c in _ud.normalize("NFD", s) if _ud.category(c) != "Mn").lower()).strip("_")

def timer():
    t = time.time()
    return lambda: time.time() - t


def feed_status(op):
    """Recompute the feed status as of AS_OF from the feed end date (the site does the same in the browser)."""
    f = op["feed"]
    st = f["status"]
    if st in ("none", "in_ati", "community", "broken"):
        return st
    end = f.get("end")
    if not end:
        return "unknown"
    e = date.fromisoformat(end)
    if e < AS_OF:
        return "expired"
    return "expiring" if (e - AS_OF).days <= 60 else "current"


class Data:
    """Loads the published files once and exposes arrays."""

    def __init__(self):
        self.places = jload("places.json")
        self.transport = jload("transport.json")
        self.ops = jload("operators.json")
        self.muni = jload("municipalities.json")
        sys.path.insert(0, str(REPO))
        from municipalities import MUNICIPALITIES   # data only (a list of dicts); the repository is not modified
        self.region_of = {m["name"]: m["region"] for m in MUNICIPALITIES}

        # places
        P = self.places
        self.n_places = len(P)
        self.p_lng = np.array([p["lng"] for p in P])
        self.p_lat = np.array([p["lat"] for p in P])
        self.p_x, self.p_y = to_xy(self.p_lng, self.p_lat)
        self.p_cat = np.array([p["category"] for p in P])
        self.p_type = np.array([p["type"] for p in P])
        self.p_muni = np.array([p["municipality"] for p in P])
        self.p_conf = np.array([p["confidence"] for p in P])
        self.p_region = np.array([self.region_of.get(p["municipality"], "") for p in P])
        self.p_transit_m = np.array([p.get("transit_m", np.nan) for p in P], dtype=float)
        self.p_t400 = np.array([bool(p.get("transit_400m")) for p in P])
        self.default = (self.p_conf >= MIN_CONF) & (self.p_type != "Places of Worship")

        # operators and feed status
        self.op_by_id = {o["id"]: o for o in self.ops["operators"]}
        self.op_status = {o["id"]: feed_status(o) for o in self.ops["operators"]}
        self.op_status_published = {o["id"]: o["feed"]["status"] for o in self.ops["operators"]}

        # transport features
        T = self.transport
        self.n_tr = len(T)
        self.t_lng = np.array([f["lng"] for f in T])
        self.t_lat = np.array([f["lat"] for f in T])
        self.t_x, self.t_y = to_xy(self.t_lng, self.t_lat)
        self.t_kind = np.array([f["kind"] for f in T])
        self.t_src = np.array([f["source"] for f in T])
        self.t_op = np.array([f.get("operator") or "" for f in T])
        self.t_trips = np.array([f.get("trips_weekday", 0) or 0 for f in T])
        self.t_sched = np.isin(self.t_src, list(SCHEDULED_SOURCES))
        self.t_access = np.isin(self.t_kind, list(ACCESS_KINDS))
        st = np.array([self.op_status.get(o, "") if s in SCHEDULED_SOURCES else ("osm" if s == "osm_transport" else "faa") for o, s in zip(self.t_op, self.t_src)])
        self.t_status = st
        self.t_current = self.t_sched & np.isin(st, ["current", "expiring"])
        self.t_expired = self.t_sched & (st == "expired")


def nearest_dist(px, py, sx, sy):
    """Distance in meters from each point to the nearest of the stops (arrays of projected coordinates); inf when the set is empty."""
    out = np.full(len(px), np.inf)
    if len(sx) == 0:
        return out, np.full(len(px), -1)
    tree = STRtree(points(sx, sy))
    idx, d = tree.query_nearest(points(px, py), return_distance=True, all_matches=False)
    out[idx[0]] = d
    nn = np.full(len(px), -1)
    nn[idx[0]] = idx[1]
    return out, nn


def count_within(px, py, sx, sy, radius):
    """Number of stops within radius of each point."""
    n = np.zeros(len(px), dtype=int)
    if len(sx) == 0:
        return n
    tree = STRtree(points(sx, sy))
    i, j = tree.query(points(px, py), predicate="dwithin", distance=radius)
    np.add.at(n, i, 1)
    return n


def pct(a, b, nd=1):
    return round(100.0 * a / b, nd) if b else None


def write_json(name, obj):
    with open(HERE / name, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1, default=lambda o: o.item() if hasattr(o, "item") else str(o))


def read_json(name):
    with open(HERE / name, encoding="utf-8") as f:
        return json.load(f)
