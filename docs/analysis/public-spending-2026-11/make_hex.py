"""Writes the hex-grid layout of the 78 municipios (one equal hexagon each) for the Public spending page's hex map (Public spending PR 7, HANDOFF decision 85).

    python docs/analysis/public-spending-2026-11/make_hex.py    read site/data/municipios.geojson; print the layout and write it into site/js/public_spending_charts.js

Each municipio gets one cell of a pointy-top hex grid (odd rows shifted right by half a cell). The cell is chosen so the grid keeps the island's shape:
the centroids (area-weighted, of each municipio's largest ring) are scaled to the grid, every municipio first takes the free cell nearest its scaled
centroid (those farthest from the island's centre first), then pairs of municipios swap cells while a swap lowers the total squared distance between
cells and centroids. Vieques and Culebra keep their places east of the main island. The result is deterministic.
"""
import json
import math
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
GEO = ROOT / "site" / "data" / "municipios.geojson"
JS = ROOT / "site" / "js" / "public_spending_charts.js"
COLS = 13          # hexes across the main island's width (76 municipios in about 17 x 5 cells)
ISLANDS = ("72147", "72049")   # Vieques and Culebra


def ring_centroid(ring):
    a = cx = cy = 0.0
    for (x0, y0), (x1, y1) in zip(ring, ring[1:] + ring[:1]):
        c = x0 * y1 - x1 * y0
        a += c
        cx += (x0 + x1) * c
        cy += (y0 + y1) * c
    if abs(a) < 1e-12:
        return sum(p[0] for p in ring) / len(ring), sum(p[1] for p in ring) / len(ring), 0.0
    return cx / (3 * a), cy / (3 * a), abs(a) / 2


def centroid(geom):
    polys = geom["coordinates"] if geom["type"] == "MultiPolygon" else [geom["coordinates"]]
    best = max((ring_centroid(p[0]) for p in polys), key=lambda c: c[2])
    return best[0], best[1]


def cell_xy(q, r):
    """Centre of cell (column q, row r) in cell units: odd rows shift half a cell right; rows are sqrt(3)/2 apart."""
    return q + (0.5 if r % 2 else 0.0), r * math.sqrt(3) / 2


def layout():
    g = json.loads(GEO.read_text(encoding="utf-8"))
    pts = {}
    for f in g["features"]:
        p = f["properties"]
        mid = str(p.get("GEOID") or p.get("geoid") or p.get("id") or p.get("fips"))
        lon, lat = centroid(f["geometry"])
        pts[mid] = (lon * math.cos(math.radians(18.2)), -lat)   # equal-ish distances; north up
    main = {m: v for m, v in pts.items() if m not in ISLANDS}
    xs = [x for x, _ in main.values()]
    ys = [y for _, y in main.values()]
    x0, y0 = min(xs), min(ys)
    s = (COLS - 1) / (max(xs) - x0)
    target = {m: ((x - x0) * s, (y - y0) * s) for m, (x, y) in pts.items()}
    rows = int(max(t[1] for t in target.values()) / (math.sqrt(3) / 2)) + 3
    cells = [(q, r) for r in range(rows) for q in range(COLS + 2)]
    cx = sum(t[0] for t in target.values()) / len(target)
    cy = sum(t[1] for t in target.values()) / len(target)
    order = sorted(target, key=lambda m: -((target[m][0] - cx) ** 2 + (target[m][1] - cy) ** 2))
    d2 = lambda m, c: (cell_xy(*c)[0] - target[m][0]) ** 2 + (cell_xy(*c)[1] - target[m][1]) ** 2
    taken, at = set(), {}
    for m in order:
        c = min((c for c in cells if c not in taken), key=lambda c: (d2(m, c), c))
        at[m] = c
        taken.add(c)
    ids = sorted(at)
    improved = True
    while improved:
        improved = False
        for i, a in enumerate(ids):
            for b in ids[i + 1:]:
                if d2(a, at[b]) + d2(b, at[a]) < d2(a, at[a]) + d2(b, at[b]) - 1e-9:
                    at[a], at[b] = at[b], at[a]
                    improved = True
            free = [c for c in cells if c not in set(at.values())]
            best = min(free, key=lambda c: (d2(a, c), c))
            if d2(a, best) < d2(a, at[a]) - 1e-9:
                at[a] = best
                improved = True
    qmin = min(q for q, r in at.values())
    rmin = min(r for q, r in at.values())
    if rmin % 2:          # keep row parity, so the half-cell shifts stay the same
        rmin -= 1
    return {m: (q - qmin, r - rmin) for m, (q, r) in sorted(at.items())}


SMALL = {"de", "del", "la", "las", "los"}


def abbreviations(names):
    """A short label of two or three letters for each municipio, all different: the initials of a name of several words (Cabo Rojo: CR), else its first
    three letters (Ponce: Pon); on a clash, the first letter and two later letters, in order (Aguada: Agu, Aguadilla: Agd)."""
    out, used = {}, set()
    for m in sorted(names, key=lambda m: names[m]):
        words = [w for w in names[m].replace("-", " ").split() if w.lower() not in SMALL] or names[m].split()
        first = names[m].replace(" ", "")
        cands = []
        if len(words) > 1:
            cands.append("".join(w[0] for w in words).upper())
            cands.append((words[0][0] + words[1][:2]).title())
        cands.append(first[:3].title())
        cands += [(first[0] + a + b).title() for i, a in enumerate(first[1:], 1) for b in first[i + 1:]]
        out[m] = next(c for c in cands if c not in used)
        used.add(out[m])
    return out


def main():
    lay = layout()
    g = json.loads(GEO.read_text(encoding="utf-8"))
    names = {str(f["properties"]["GEOID"]): f["properties"]["municipality"] for f in g["features"]}
    ab = abbreviations(names)
    text = ",".join(f"{m[2:]}:{q}.{r}:{ab[m]}" for m, (q, r) in lay.items())
    print(len(lay), "municipios;", text)
    js = JS.read_text(encoding="utf-8")
    js = re.sub(r"const HEX = '[^']*';", f"const HEX = '{text}';", js)
    JS.write_text(js, encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
