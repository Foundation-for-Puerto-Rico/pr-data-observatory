"""The municipality of a point: the outline that holds it, else the outline nearest to it.

A pier, a ferry terminal or a shoreline stop can sit a few metres outside every municipal outline (the outlines follow the shore).
Such a point belongs to the municipality whose outline is nearest, not to the one whose town centre is nearest: the Cataño ferry
terminal is 50 m from Cataño's shore but closer to San Juan's town centre than to Cataño's. build.py (places, stops, airports) and
refresh_network.py (scheduled stops) both use this rule, so a full build and the nightly refresh place a stop the same way.

    locate = Locator(geoms, names)   # shapely geometries in longitude/latitude, and the municipality of each
    locate(18.4436, -66.1176)        # -> "Cataño"
"""

from math import cos, radians

from shapely import affinity
from shapely.geometry import Point
from shapely.strtree import STRtree

M_PER_DEG = 111_320
SEARCH_DEG = 0.05   # about 5 km: outlines whose box lies this close are the candidates; a point farther than that from every outline is compared with all of them


class Locator:
    def __init__(self, geoms, names):
        self.geoms, self.names = list(geoms), list(names)
        self.tree = STRtree(self.geoms)

    def __call__(self, lat, lng):
        hits = self.tree.query(Point(lng, lat), predicate="within")
        return self.names[hits[0]] if len(hits) else self.names[self.nearest(lat, lng)[0]]

    def nearest(self, lat, lng):
        """(index, metres) of the outline nearest to the point. Distances are measured with longitude scaled by cos(latitude), as everywhere in the observatory."""
        pt = Point(lng, lat)
        k = cos(radians(lat))
        here = Point(lng * k, lat)

        def closest(idx):
            dist = {i: affinity.scale(self.geoms[i], xfact=k, yfact=1, origin=(0, 0)).distance(here) * M_PER_DEG for i in sorted(idx)}
            best = min(dist, key=lambda i: (dist[i], i))
            return best, dist[best]

        cand = [int(i) for i in self.tree.query(pt.buffer(SEARCH_DEG))]
        best = closest(cand) if cand else None
        # an outline nearer than the best candidate lies within best/k degrees, so inside the search box only when best < SEARCH_DEG * k; otherwise look at all
        if best is None or best[1] >= SEARCH_DEG * k * M_PER_DEG:
            best = closest(range(len(self.geoms)))
        return best
