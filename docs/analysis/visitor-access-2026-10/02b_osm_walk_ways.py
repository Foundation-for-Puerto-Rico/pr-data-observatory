"""Q2 support: read the repository's cached OpenStreetMap extract (cache/roads/puerto-rico.osm.pbf, read only) and keep every way a
pedestrian may use, so that the road-only walking distances from roads.bin can be compared with a full walking network.

Output: osm_walk_ways.pkl in this folder (ways as lists of node refs with a class and flags, node coordinates), and
q2b_osm_inventory.json (km by highway class: all ways in the extract, and the ways roads.bin keeps).
"""
from common import *
import os
import pickle

PBF_DIR = REPO / "cache" / "roads"
PBF_NAME = "puerto-rico.osm.pbf"
import osmium

t = timer()
here = os.getcwd()
os.chdir(PBF_DIR)    # libosmium cannot open paths with accented characters on Windows (the repository folder contains one), so open by bare name
WALK_OK = {"residential", "living_street", "unclassified", "tertiary", "tertiary_link", "secondary", "secondary_link", "primary", "primary_link",
           "trunk", "trunk_link", "service", "pedestrian", "footway", "path", "steps", "track", "cycleway", "bridleway", "road", "corridor"}
ROADS_BIN_KEEPS = {"motorway", "motorway_link", "trunk", "trunk_link", "primary", "primary_link", "secondary", "secondary_link", "tertiary", "tertiary_link", "unclassified", "residential", "living_street", "busway"}
SKIP_SERVICE_IN_ROADS_BIN = True   # roads.py _usable(): all service roads dropped

ways = []            # (class, refs, flags)
coord = {}
inv_all = Counter()          # hw -> count
inv_len = defaultdict(float) # hw -> km (computed after the pass from coordinates)
way_len_refs = []
hav_cache = {}
n_ways_seen = 0
tags_seen = Counter()
fp = osmium.FileProcessor(PBF_NAME, osmium.osm.NODE | osmium.osm.WAY).with_locations().with_filter(osmium.filter.KeyFilter("highway"))
for w in fp:
    if not w.is_way():
        continue
    n_ways_seen += 1
    tg = w.tags
    hw = tg.get("highway")
    refs = []
    for n in w.nodes:
        if not n.location.valid():
            continue
        refs.append(n.ref)
        coord[n.ref] = (n.lon, n.lat)
    if len(refs) < 2:
        continue
    foot = tg.get("foot")
    access = tg.get("access")
    area = tg.get("area") == "yes"
    inv_all[hw] += 1
    way_len_refs.append((hw, refs))
    # walkable test
    ok = hw in WALK_OK and not area
    if hw in ("motorway", "motorway_link") and foot in ("yes", "designated", "permissive"):
        ok = True
    if foot == "no":
        ok = False
    if access in ("no", "private") and foot not in ("yes", "designated", "permissive"):
        ok = False
    if hw in ("cycleway", "bridleway") and foot not in ("yes", "designated", "permissive"):
        ok = False
    if hw == "service" and tg.get("service") in ("emergency_access",):
        ok = False
    if tg.get("highway") in ("construction", "proposed"):
        ok = False
    if ok:
        ways.append((hw, refs, tg.get("sidewalk"), tg.get("surface")))
os.chdir(here)
print("read PBF in", round(t(), 1), "s; highway ways", n_ways_seen, "walkable ways", len(ways), "nodes with coordinates", len(coord))

# length of every highway class in the extract (all ways), and of the ones roads.bin keeps
def hav(lon1, lat1, lon2, lat2):
    p = math.pi / 180
    a = math.sin((lat2 - lat1) * p / 2) ** 2 + math.cos(lat1 * p) * math.cos(lat2 * p) * math.sin((lon2 - lon1) * p / 2) ** 2
    return 12742000 * math.asin(math.sqrt(a))

km_all = defaultdict(float)
for hw, refs in way_len_refs:
    s = 0.0
    for a, b in zip(refs, refs[1:]):
        s += hav(coord[a][0], coord[a][1], coord[b][0], coord[b][1])
    km_all[hw] += s / 1000
km_walk = defaultdict(float)
for hw, refs, sw, sf in ways:
    s = 0.0
    for a, b in zip(refs, refs[1:]):
        s += hav(coord[a][0], coord[a][1], coord[b][0], coord[b][1])
    km_walk[hw] += s / 1000
inv = {
    "read_pbf_seconds": round(t(), 1),
    "highway_ways_in_extract": n_ways_seen,
    "km_by_highway_all_ways": {k: round(v, 1) for k, v in sorted(km_all.items(), key=lambda kv: -kv[1])},
    "ways_by_highway_all": dict(inv_all.most_common()),
    "km_by_highway_walkable_ways_used": {k: round(v, 1) for k, v in sorted(km_walk.items(), key=lambda kv: -kv[1])},
    "walkable_km_total": round(sum(km_walk.values()), 0),
    "classes_not_in_roads_bin_but_walkable_km": round(sum(v for k, v in km_walk.items() if k not in ROADS_BIN_KEEPS), 1),
    "service_km_all": round(km_all.get("service", 0), 1),
    "footway_path_pedestrian_steps_track_cycleway_km_all": round(sum(km_all.get(k, 0) for k in ("footway", "path", "pedestrian", "steps", "track", "cycleway", "bridleway")), 1),
}
write_json("q2b_osm_inventory.json", inv)
# keep only the nodes we need
need = set()
for hw, refs, sw, sf in ways:
    need.update(refs)
coord_small = {r: coord[r] for r in need}
with open(HERE / "osm_walk_ways.pkl", "wb") as f:
    pickle.dump({"ways": ways, "coord": coord_small}, f, protocol=4)
print(json.dumps(inv, indent=1)[:3500])
print("total", round(t(), 1), "s")
