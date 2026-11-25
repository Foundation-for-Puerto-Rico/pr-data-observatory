"""Can the colors of the twin's data layers be told apart by people with color-vision deficiency? (plan item 6, 2026-10-06)

    python docs/analysis/palettes-2026-10/colour_vision.py          # prints the tables and writes colour_vision.json next to this file

It reads every palette from site/js/core/palettes.js (through Node, so the numbers are always those the pages draw), simulates the three kinds of dichromacy
(protanopia, deuteranopia, tritanopia; Machado, Oliveira and Fernandes 2009, severity 1.0) and measures how far apart colors are with CIEDE2000, a
standard color difference (about 2 is the smallest difference an observer notices side by side, 5 is clear, 10 or more tells a legend's classes apart at a glance).

What is compared, for each palette and each vision (normal, protan, deutan, tritan):
  sequential ramps     every pair of neighboring classes, and the lightest and darkest class (the classes must stay in order)
  diverging scale      every pair of neighboring classes, and the two ends
  bivariate grid       every pair of the nine cells that share an edge, and the three corners that must stay apart
  symbols and lines    every pair of colors (they are told apart by color alone in a legend or a chart)
  map background       the "no value" gray against the lightest class of each ramp
Only the numbers are computed here. What to do about a weak pair is a design decision: docs/palettes.md records the results and what was decided.
"""
import itertools
import json
import math
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]

MACHADO = {   # applied to linear RGB
    "protan": [[0.152286, 1.052583, -0.204868], [0.114503, 0.786281, 0.099216], [-0.003882, -0.048116, 1.051998]],
    "deutan": [[0.367322, 0.860646, -0.227968], [0.280085, 0.672501, 0.047413], [-0.011820, 0.042940, 0.968881]],
    "tritan": [[1.255528, -0.076749, -0.178779], [-0.078411, 0.930809, 0.147602], [0.004733, 0.691367, 0.303900]],
}
WEAK, CLEAR = 5.0, 10.0   # CIEDE2000 below WEAK: hard to tell apart; below CLEAR: tell apart with care; CLEAR or more: at a glance


def rgb(hex_):
    return [int(hex_[i:i + 2], 16) / 255 for i in (1, 3, 5)]


def lin(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def delin(c):
    c = min(1.0, max(0.0, c))
    return 12.92 * c if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055


def simulate(hex_, kind):
    r = [lin(c) for c in rgb(hex_)]
    if kind == "normal":
        return r
    m = MACHADO[kind]
    return [sum(m[i][j] * r[j] for j in range(3)) for i in range(3)]


def lab(linear):
    x = 0.4124564 * linear[0] + 0.3575761 * linear[1] + 0.1804375 * linear[2]
    y = 0.2126729 * linear[0] + 0.7151522 * linear[1] + 0.0721750 * linear[2]
    z = 0.0193339 * linear[0] + 0.1191920 * linear[1] + 0.9503041 * linear[2]
    f = lambda t: t ** (1 / 3) if t > 216 / 24389 else (24389 / 27 * t + 16) / 116   # noqa: E731
    fx, fy, fz = f(x / 0.95047), f(y), f(z / 1.08883)
    return 116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz)


def de2000(l1, l2):
    """CIEDE2000 (Sharma, Wu and Dalal 2005)."""
    L1, a1, b1 = l1
    L2, a2, b2 = l2
    C1, C2 = math.hypot(a1, b1), math.hypot(a2, b2)
    Cb = (C1 + C2) / 2
    G = 0.5 * (1 - math.sqrt(Cb ** 7 / (Cb ** 7 + 25 ** 7)))
    a1p, a2p = (1 + G) * a1, (1 + G) * a2
    C1p, C2p = math.hypot(a1p, b1), math.hypot(a2p, b2)
    h1p = math.degrees(math.atan2(b1, a1p)) % 360 if (b1 or a1p) else 0
    h2p = math.degrees(math.atan2(b2, a2p)) % 360 if (b2 or a2p) else 0
    dLp, dCp = L2 - L1, C2p - C1p
    if C1p * C2p == 0:
        dhp = 0
    else:
        dhp = h2p - h1p
        dhp += -360 if dhp > 180 else 360 if dhp < -180 else 0
    dHp = 2 * math.sqrt(C1p * C2p) * math.sin(math.radians(dhp / 2))
    Lbp, Cbp = (L1 + L2) / 2, (C1p + C2p) / 2
    if C1p * C2p == 0:
        hbp = h1p + h2p
    elif abs(h1p - h2p) <= 180:
        hbp = (h1p + h2p) / 2
    else:
        hbp = (h1p + h2p + 360) / 2 if h1p + h2p < 360 else (h1p + h2p - 360) / 2
    T = 1 - 0.17 * math.cos(math.radians(hbp - 30)) + 0.24 * math.cos(math.radians(2 * hbp)) + 0.32 * math.cos(math.radians(3 * hbp + 6)) - 0.20 * math.cos(math.radians(4 * hbp - 63))
    dTheta = 30 * math.exp(-(((hbp - 275) / 25) ** 2))
    Rc = 2 * math.sqrt(Cbp ** 7 / (Cbp ** 7 + 25 ** 7))
    Sl = 1 + 0.015 * (Lbp - 50) ** 2 / math.sqrt(20 + (Lbp - 50) ** 2)
    Sc, Sh = 1 + 0.045 * Cbp, 1 + 0.015 * Cbp * T
    Rt = -math.sin(math.radians(2 * dTheta)) * Rc
    return math.sqrt((dLp / Sl) ** 2 + (dCp / Sc) ** 2 + (dHp / Sh) ** 2 + Rt * (dCp / Sc) * (dHp / Sh))


def self_check():
    """Two pairs from the published CIEDE2000 test data (Sharma, Wu and Dalal 2005, table 1)."""
    assert abs(de2000((50.0, 2.6772, -79.7751), (50.0, 0.0, -82.7485)) - 2.0425) < 1e-4
    assert abs(de2000((50.0, 3.1571, -77.2803), (50.0, 0.0, -82.7485)) - 2.8615) < 1e-4
    assert abs(de2000((50.0, 2.5, 0.0), (73.0, 25.0, -18.0)) - 27.1492) < 1e-4
    assert abs(de2000((50.0, 2.5, 0.0), (61.0, -5.0, 29.0)) - 22.8977) < 1e-4


def palettes():
    out = subprocess.run(["node", "-p", "JSON.stringify(require('./site/js/core/palettes.js'))"], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", check=True)
    return json.loads(out.stdout)


def distance(a, b, kind):
    return de2000(lab(simulate(a, kind)), lab(simulate(b, kind)))


def pairs_of(p):
    """{palette name: [(label, color a, color b)]}: what must stay apart."""
    out = {}
    for name, ramp in p["RAMPS"].items():
        out[f"ramp {name}"] = [(f"class {i + 1} and {i + 2}", ramp[i], ramp[i + 1]) for i in range(4)] + [("lightest and darkest", ramp[0], ramp[4]), ("lightest and the map background", ramp[0], p["NOVAL"])]
    d = p["DIVERGING"]
    out["diverging"] = [(f"class {i + 1} and {i + 2}", d[i], d[i + 1]) for i in range(4)] + [("the two ends", d[0], d[4])]
    g = p["BIVARIATE"]
    edge = []
    for r in range(3):
        for c in range(3):
            if c < 2:
                edge.append((f"cell [{r}][{c}] and [{r}][{c + 1}]", g[r][c], g[r][c + 1]))
            if r < 2:
                edge.append((f"cell [{r}][{c}] and [{r + 1}][{c}]", g[r][c], g[r + 1][c]))
    out["bivariate grid"] = edge + [("low-low and high-high", g[0][0], g[2][2]), ("high A / low B and low A / high B", g[0][2], g[2][0])]
    for name in ("SYMBOLS", "LINES"):
        cs = p[name]
        out[name.lower()] = [(f"{i + 1} and {j + 1}", cs[i], cs[j]) for i, j in itertools.combinations(range(len(cs)), 2)]
    return out


def main():
    self_check()
    p = palettes()
    groups = pairs_of(p)
    kinds = ["normal", *MACHADO]
    result = {"threshold_weak": WEAK, "threshold_clear": CLEAR, "palettes": {}}
    print(f"{'palette':16s}" + "".join(f"{k:>10s}" for k in kinds) + "   weakest pair under normal vision")
    for name, items in groups.items():
        row = {}
        for k in kinds:
            ds = [(distance(a, b, k), lab_, a, b) for lab_, a, b in items]
            worst = min(ds)
            row[k] = {"min": round(worst[0], 1), "pair": [worst[1], worst[2], worst[3]], "below_weak": [[x[1], x[2], x[3], round(x[0], 1)] for x in ds if x[0] < WEAK], "below_clear": sum(1 for x in ds if x[0] < CLEAR), "pairs": len(ds)}
        result["palettes"][name] = row
        n = row["normal"]
        print(f"{name:16s}" + "".join(f"{row[k]['min']:10.1f}" for k in kinds) + f"   {n['pair'][0]} ({n['pair'][1]} / {n['pair'][2]})")
    (HERE / "colour_vision.json").write_text(json.dumps(result, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print()
    for name, row in result["palettes"].items():
        for k in kinds:
            for lab_, a, b, d in row[k]["below_weak"]:
                print(f"  under {WEAK:g}: {name}, {k}: {lab_}  {a} / {b}  {d}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
