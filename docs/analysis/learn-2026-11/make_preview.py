"""Preview of the Learn overview page, for the proposal docs/learn-proposal-2026-11.md (HANDOFF decision 106).

    python docs/analysis/learn-2026-11/make_preview.py     # writes preview.svg beside this file

A drawing for the proposal, not a page of the site. It reads no data: the diagrams are schematic and carry no figure of Puerto Rico. The tools and
layers named on the cards are the ones on main (023d38b, 2026-11-14): site/index.html (Tools > Map tools, Map layers). The colors are the site's
(site/css/twin.css). The file is written with LF line ends, as the repository stores it.
"""
import math
from pathlib import Path

W, CARD_W, CARD_H, GAP, LEFT = 960, 296, 196, 16, 20
BLUE, BLUE_D, BLUE_L = "#338CB3", "#205D7B", "#5FAFDA"
RAMP = ["#BDE0F2", "#8FCAE8", "#5FAFDA", "#338CB3", "#205D7B"]
RED, YELLOW, GREEN, GREEN_D = "#FF4D38", "#FFA600", "#A6BF33", "#79901E"
TEXT, MUTED, BORDER, BG, GREY = "#2A2E2E", "#666666", "#E6E6E6", "#F2F2F2", "#8C8E8E"
FONT = "'Segoe UI', system-ui, -apple-system, sans-serif"


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def text(x, y, s, size=12, fill=TEXT, weight=400, anchor="start"):
    return f'<text x="{x:g}" y="{y:g}" font-size="{size:g}" fill="{fill}" font-weight="{weight}" text-anchor="{anchor}">{esc(s)}</text>'


def pts(pairs):
    return " ".join(f"{x:g},{y:g}" for x, y in pairs)


# The diagrams: each draws inside a zone 272 wide and 76 high whose top left corner is (x, y).
def d_shapes(x, y):
    o = [f'<circle cx="{x + 30}" cy="{y + 34}" r="7" fill="{RED}"/>']
    o.append(f'<polyline points="{pts([(x + 68, y + 52), (x + 88, y + 20), (x + 108, y + 44), (x + 128, y + 16)])}" fill="none" stroke="{BLUE_D}" stroke-width="3" stroke-linejoin="round" stroke-linecap="round"/>')
    o.append(f'<polygon points="{pts([(x + 160, y + 52), (x + 170, y + 18), (x + 200, y + 12), (x + 212, y + 42), (x + 190, y + 56)])}" fill="{RAMP[1]}" stroke="{BLUE_D}" stroke-width="1.5"/>')
    cells = [0, 2, 3, 1, 4, 2, 0, 1, 3]
    for i, c in enumerate(cells):
        o.append(f'<rect x="{x + 228 + 14 * (i % 3)}" y="{y + 13 + 14 * (i // 3)}" width="14" height="14" fill="{RAMP[c]}" stroke="#FFFFFF" stroke-width="1"/>')
    for cx, lab in ((30, "point"), (98, "line"), (186, "area"), (249, "grid")):
        o.append(text(x + cx, y + 73, lab, 10, MUTED, anchor="middle"))
    return o


def d_attributes(x, y):
    o = [f'<polygon points="{pts([(x + 22, y + 56), (x + 30, y + 16), (x + 70, y + 8), (x + 88, y + 40), (x + 58, y + 64)])}" fill="{RAMP[1]}" stroke="{BLUE_D}" stroke-width="1.5"/>']
    o.append(f'<line x1="{x + 96}" y1="{y + 36}" x2="{x + 128}" y2="{y + 36}" stroke="{GREY}" stroke-width="1.5"/>')
    o.append(f'<polygon points="{pts([(x + 128, y + 31), (x + 137, y + 36), (x + 128, y + 41)])}" fill="{GREY}"/>')
    o.append(f'<rect x="{x + 144}" y="{y + 8}" width="112" height="56" rx="3" fill="#FFFFFF" stroke="{BORDER}" stroke-width="1.5"/>')
    o.append(f'<rect x="{x + 144}" y="{y + 8}" width="112" height="14" rx="3" fill="{RAMP[0]}"/>')
    for r in range(1, 4):
        o.append(f'<line x1="{x + 144}" y1="{y + 8 + 14 * r}" x2="{x + 256}" y2="{y + 8 + 14 * r}" stroke="{BORDER}" stroke-width="1"/>')
    o.append(f'<line x1="{x + 200}" y1="{y + 8}" x2="{x + 200}" y2="{y + 64}" stroke="{BORDER}" stroke-width="1"/>')
    for r in range(4):   # bars stand for the words and the numbers of a table: no value is shown
        fill = BLUE_D if r == 0 else GREY
        o.append(f'<rect x="{x + 150}" y="{y + 13 + 14 * r}" width="{[34, 40, 28, 36][r]}" height="4" rx="2" fill="{fill}" opacity="{1 if r == 0 else .55}"/>')
        o.append(f'<rect x="{x + 206}" y="{y + 13 + 14 * r}" width="{[30, 22, 26, 18][r]}" height="4" rx="2" fill="{fill}" opacity="{1 if r == 0 else .55}"/>')
    return o


def d_topology(x, y):
    o = [f'<polygon points="{pts([(x + 40, y + 50), (x + 52, y + 12), (x + 104, y + 8), (x + 112, y + 54)])}" fill="{RAMP[0]}" stroke="{BLUE_D}" stroke-width="1.5"/>']
    o.append(f'<polygon points="{pts([(x + 104, y + 8), (x + 168, y + 14), (x + 176, y + 48), (x + 112, y + 54)])}" fill="{RAMP[2]}" stroke="{BLUE_D}" stroke-width="1.5"/>')
    o.append(f'<circle cx="{x + 72}" cy="{y + 32}" r="5" fill="{RED}"/>')
    o.append(f'<polyline points="{pts([(x + 150, y + 4), (x + 196, y + 30), (x + 236, y + 20)])}" fill="none" stroke="{YELLOW}" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>')
    for cx, lab in ((72, "inside"), (118, "touching"), (212, "crossing")):
        o.append(text(x + cx, y + 73, lab, 10, MUTED, anchor="middle"))
    return o


def d_count(x, y):
    o = [f'<polygon points="{pts([(x + 60, y + 60), (x + 70, y + 14), (x + 150, y + 6), (x + 178, y + 40), (x + 140, y + 68)])}" fill="{RAMP[0]}" stroke="{BLUE_D}" stroke-width="1.5"/>']
    dots = [(88, 30), (104, 50), (122, 24), (134, 44), (150, 30), (112, 36), (92, 48)]
    for dx, dy in dots:
        o.append(f'<circle cx="{x + dx}" cy="{y + dy}" r="4" fill="{GREEN_D}"/>')
    o.append(f'<circle cx="{x + 214}" cy="{y + 36}" r="17" fill="{BLUE_D}"/>')
    o.append(text(x + 214, y + 42, str(len(dots)), 17, "#FFFFFF", 700, "middle"))
    return o


def d_overlay(x, y):
    def sheet(dy, fill, op):
        return f'<polygon points="{pts([(x + 66, y + 34 + dy), (x + 150, y + 10 + dy), (x + 214, y + 28 + dy), (x + 130, y + 52 + dy)])}" fill="{fill}" fill-opacity="{op}" stroke="{BLUE_D}" stroke-width="1.2"/>'
    o = [sheet(18, RAMP[3], 1), sheet(4, YELLOW, .8), sheet(-8, GREEN, .75)]
    return o


def d_buffer(x, y):
    cx, cy = x + 120, y + 38
    o = [f'<circle cx="{cx}" cy="{cy}" r="34" fill="{RAMP[0]}" stroke="{BLUE}" stroke-width="1.5" stroke-dasharray="4 3"/>']
    o.append(f'<circle cx="{cx}" cy="{cy}" r="17" fill="{RAMP[1]}" stroke="{BLUE}" stroke-width="1"/>')
    for dx, dy, inside in ((-14, -8, 1), (18, 12, 1), (6, -22, 1), (-24, 14, 1), (62, -18, 0), (78, 20, 0), (-70, 6, 0), (-58, -24, 0)):
        o.append(f'<circle cx="{cx + dx}" cy="{cy + dy}" r="4" fill="{GREEN_D if inside else GREY}"/>')
    o.append(f'<circle cx="{cx}" cy="{cy}" r="5.5" fill="{RED}" stroke="#FFFFFF" stroke-width="1.5"/>')
    return o


def d_network(x, y):
    o = []
    xs, ys = [44, 88, 132, 176, 220], [10, 36, 62]
    for gx in xs:
        o.append(f'<line x1="{x + gx}" y1="{y + ys[0]}" x2="{x + gx}" y2="{y + ys[-1]}" stroke="{BORDER}" stroke-width="5" stroke-linecap="round"/>')
    for gy in ys:
        o.append(f'<line x1="{x + xs[0]}" y1="{y + gy}" x2="{x + xs[-1]}" y2="{y + gy}" stroke="{BORDER}" stroke-width="5" stroke-linecap="round"/>')
    route = [(44, 62), (88, 62), (88, 36), (176, 36), (176, 10), (220, 10)]
    o.append(f'<polyline points="{pts([(x + a, y + b) for a, b in route])}" fill="none" stroke="{BLUE}" stroke-width="4" stroke-linejoin="round" stroke-linecap="round"/>')
    o.append(f'<circle cx="{x + 44}" cy="{y + 62}" r="6.5" fill="{YELLOW}" stroke="#FFFFFF" stroke-width="1.5"/>')
    o.append(f'<rect x="{x + 213}" y="{y + 3}" width="14" height="14" rx="3" fill="{RED}" stroke="#FFFFFF" stroke-width="1.5"/>')
    return o


def d_interp(x, y):
    grid = [[0, 1, 1, 2, 3, 4, 4], [0, 0, 1, 2, 3, 3, 4], [0, 0, 1, 1, 2, 3, 3]]
    o = []
    for r, row in enumerate(grid):
        for c, v in enumerate(row):
            o.append(f'<rect x="{x + 59 + 22 * c}" y="{y + 5 + 22 * r}" width="22" height="22" fill="{RAMP[v]}" stroke="#FFFFFF" stroke-width="1"/>')
    for c, r in ((0, 2), (2, 0), (4, 1), (6, 0)):   # the cells that hold a measurement; the others are estimated from them
        o.append(f'<circle cx="{x + 70 + 22 * c}" cy="{y + 16 + 22 * r}" r="4.5" fill="#FFFFFF" stroke="{TEXT}" stroke-width="2"/>')
    return o


def d_hot(x, y):
    r = 13
    w, h = math.sqrt(3) * r, 1.5 * r
    o = []
    hot = (4.2, 1.0)
    for row in range(3):
        for col in range(8):
            cx = x + 46 + col * w + (w / 2 if row % 2 else 0)
            cy = y + 16 + row * h
            d = math.hypot(col + (0.5 if row % 2 else 0) - hot[0], (row - hot[1]) * 0.9)
            v = max(0, min(4, 4 - int(d / 0.85)))
            corners = [(cx + r * math.cos(math.radians(60 * k - 30)), cy + r * math.sin(math.radians(60 * k - 30))) for k in range(6)]
            o.append(f'<polygon points="{" ".join(f"{a:.1f},{b:.1f}" for a, b in corners)}" fill="{RAMP[v]}" stroke="#FFFFFF" stroke-width="1.2"/>')
    return o


# (plain question, GIS term, the observatory's own examples in two lines, diagram, note)
MADE_OF = [
    ("Layers and shapes", "spatial data (vector and raster)", ("Fire stations, transit routes, barrios,", "surface heat"), d_shapes, None),
    ("What a shape knows", "attribute data", ("See the map as a table; the pop-up", "of a barrio"), d_attributes, None),
    ("How shapes relate", "topology", ("Build my region; tourism places", "inside a flood zone"), d_topology, None),
]
WAYS = [
    ("How many, how much", "descriptive analysis", ("Count my points; Rankings;", "Land-use analysis"), d_count, None),
    ("What overlaps", "overlay analysis", ("Compare two maps; Composite index;", "places inside flood zones"), d_overlay, None),
    ("What is near", "buffer and proximity", ("Area around a point; 400 m walk", "radius around transit stops"), d_buffer, None),
    ("How to get there", "network analysis", ("Walking time; Plan a route;", "Residents far from service"), d_network, None),
    ("Between measurements", "spatial interpolation", ("Contour lines and Slope, from the", "10 m elevation grid"), d_interp, "No tool of its own"),
    ("Where things concentrate", "hot spots and clusters", ("Places in hexagons; Broadband gaps", "(FCC hexagons)"), d_hot, "No statistical test"),
]


def card(x, y, item):
    title, term, examples, diagram, note = item
    o = [f'<rect x="{x}" y="{y}" width="{CARD_W}" height="{CARD_H}" rx="10" fill="#FFFFFF" stroke="{BORDER}" stroke-width="1"/>']
    o += diagram(x + 12, y + 10)
    o.append(text(x + 16, y + 112, title, 16, TEXT, 700))
    o.append(text(x + 16, y + 130, "GIS term: " + term, 11.5, MUTED))
    o.append(text(x + 16, y + 152, "IN THE OBSERVATORY", 9.5, BLUE_D, 700))
    o.append(text(x + 16, y + 168, examples[0], 12, TEXT))
    o.append(text(x + 16, y + 184, examples[1], 12, TEXT))
    if note:
        wid = 7 + 5.6 * len(note) + 7
        o.append(f'<rect x="{x + CARD_W - 12 - wid:g}" y="{y + 139}" width="{wid:g}" height="18" rx="9" fill="#FFE9A8"/>')   # on the label's line, clear of the title
        o.append(text(x + CARD_W - 12 - wid / 2, y + 151.5, note, 10, "#8A5200", 700, "middle"))
    return o


def main():
    o = []
    y = 40
    o.append(text(LEFT, y, "Learn: how a map answers a question", 24, TEXT, 700))
    o.append(text(LEFT, y + 24, "Preview of the overview page (proposal, decision 106). Every card opens a short lesson; every lesson opens the live map on its example.", 12.5, MUTED))
    y = 100
    o.append(text(LEFT, y, "WHAT A MAP IS MADE OF", 11, BLUE_D, 700))
    y += 14
    for i, item in enumerate(MADE_OF):
        o += card(LEFT + i * (CARD_W + GAP), y, item)
    y += CARD_H + 34
    o.append(text(LEFT, y, "SIX WAYS TO ASK A MAP A QUESTION", 11, BLUE_D, 700))
    y += 14
    for i, item in enumerate(WAYS):
        o += card(LEFT + (i % 3) * (CARD_W + GAP), y + (i // 3) * (CARD_H + GAP), item)
    y += 2 * CARD_H + GAP + 28
    o.append(text(LEFT, y, "Not on this preview: the lessons that read a map (classes, counts and rates, how sure a number is), judge a map, and take the data further.", 11.5, MUTED))
    height = y + 22
    head = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {height}" width="{W}" height="{height}" font-family="{FONT}" role="img" aria-labelledby="t d">'
            '<title id="t">Preview of the Learn overview page</title>'
            '<desc id="d">Nine cards. What a map is made of: layers and shapes; what a shape knows; how shapes relate. Six ways to ask a map a question: '
            'how many, what overlaps, what is near, how to get there, between measurements, where things concentrate. Each card names the GIS term '
            'and the tools or layers of the observatory that the lesson uses.</desc>'
            f'<rect width="{W}" height="{height}" fill="{BG}"/>')
    svg = head + "\n" + "\n".join(o) + "\n</svg>\n"
    out = Path(__file__).with_name("preview.svg")
    out.write_text(svg, encoding="utf-8", newline="\n")
    print(f"{out.name}: {len(svg.encode('utf-8')) / 1024:.1f} KB, {W} x {height}")


if __name__ == "__main__":
    main()
