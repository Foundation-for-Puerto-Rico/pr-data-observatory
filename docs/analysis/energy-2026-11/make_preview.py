"""Preview map for the energy proposal (decision 104): plants, transmission lines and home batteries, as one SVG.

Not part of the build. It reads three downloads made during the research of 2026-11-13 and writes preview.svg next to this file:

  --eia   EIA-860M generator inventory (september_generator2026.xlsx), sheet Operating_PR
  --osm   Overpass answer for Puerto Rico with power=line ways and their geometry (out geom)
  --luma  LUMA's "Resumen Metricas Master" workbook filed with the Puerto Rico Energy Bureau (docket NEPR-MI-2019-0007), sheet T&D

Plants are EIA's points summed by plant id, coloured by the technology with the most MW, circle AREA proportional to MW.
Lines are OpenStreetMap power=line by voltage tag. Municipios are shaded by LUMA's battery installations (BESS) per 100 housing
units of the 2020 Census (HU100 in site/data/municipios.geojson); LUMA splits San Juan into San Juan, Rio Piedras and Santurce,
which are added back together. Mona is left out (no grid). Standard library only.

Usage: python docs/analysis/energy-2026-11/make_preview.py --eia X.xlsx --osm Y.json --luma Z.xlsx
"""
import argparse
import datetime
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
import xlsx_lite as X  # noqa: E402

LON0, LON1, LAT0, LAT1 = -67.30, -65.20, 17.86, 18.56
W = 1200
PAD = 20
KX = math.cos(math.radians(18.2))
S = (W - 2 * PAD) / ((LON1 - LON0) * KX)
TOP = 126
MAP_H = (LAT1 - LAT0) * S
H = int(TOP + MAP_H + 190)

FUEL = [   # category, colour (Okabe-Ito, safe for colour-vision deficiency), label
    ('oil', '#E69F00', 'Oil (petroleum)'),
    ('gas', '#CC79A7', 'Natural gas'),
    ('coal', '#BDBDBD', 'Coal'),
    ('solar', '#F0E442', 'Solar'),
    ('wind', '#56B4E9', 'Wind'),
    ('hydro', '#009E73', 'Hydro'),
    ('battery', '#FFFFFF', 'Battery'),
    ('other', '#D55E00', 'Landfill gas'),
]
COLOR = {k: c for k, c, _ in FUEL}
LINES = [('38000', '#5f6f99', 0.7, '38 kV (about half mapped)'), ('115000', '#a78bfa', 1.1, '115 kV'),
         ('230000', '#ff5fd2', 1.9, '230 kV')]
CLASSES = [8, 11, 14, 17]
RAMP = ['#16203d', '#173a5a', '#1b5774', '#22768b', '#2f97a0']


def xy(lon, lat):
    return PAD + (lon - LON0) * KX * S, TOP + (LAT1 - lat) * S


def tech_cat(t):
    t = (t or '').lower()
    if 'petroleum' in t:
        return 'oil'
    if 'natural gas' in t:
        return 'gas'
    if 'coal' in t:
        return 'coal'
    if 'solar' in t:
        return 'solar'
    if 'wind' in t:
        return 'wind'
    if 'hydro' in t:
        return 'hydro'
    if 'batter' in t:
        return 'battery'
    return 'other'


def rows_with_header(path, sheet, first):
    rows = list(X.sheet_rows(path, sheet))
    for i, r in enumerate(rows):
        if first in [str(c).strip() for c in r]:
            hdr = [str(c).strip() for c in r]
            return hdr, rows[i + 1:]
    raise SystemExit(f'no header with {first!r} in {sheet}')


def plants(path):
    hdr, rows = rows_with_header(path, 'Operating_PR', 'Plant ID')
    ix = {h: i for i, h in enumerate(hdr)}
    out = {}
    for r in rows:
        try:
            pid = str(r[ix['Plant ID']]).strip()
            mw = float(r[ix['Nameplate Capacity (MW)']])
            lat, lon = float(r[ix['Latitude']]), float(r[ix['Longitude']])
        except (ValueError, IndexError, KeyError):
            continue
        p = out.setdefault(pid, {'lat': lat, 'lon': lon, 'by': {}})
        c = tech_cat(r[ix['Technology']])
        p['by'][c] = p['by'].get(c, 0) + mw
    for p in out.values():
        p['mw'] = sum(p['by'].values())
        p['cat'] = max(p['by'], key=p['by'].get)
    return out


def luma(path):
    rows = list(X.sheet_rows(path, 'T&D'))
    hdr = rows[0]

    def latest(r):
        for i in range(len(hdr) - 2, 4, -1):
            if i < len(r) and str(r[i]).strip() not in ('', 'None'):
                return i, float(r[i])
        return None, None

    bess, pv_mw, pv_n, month = {}, None, None, None
    for r in rows[1:]:
        if r[2] == 'Total number of BESS installations':
            i, v = latest(r)
            name = {'Río Piedras': 'San Juan', 'Santurce': 'San Juan'}.get(r[3], r[3])
            bess[name] = bess.get(name, 0) + v
            month = month or i
        elif r[2] == 'Total installed distributed generation capacity - Photovoltaic' and r[3] == 'Total':
            pv_mw = latest(r)[1]
        elif r[2] == 'Total number of distributed generation installations - Photovoltaic' and r[3] == 'Total':
            pv_n = latest(r)[1]
    serial = int(float(hdr[month]))
    when = datetime.date(1899, 12, 30) + datetime.timedelta(days=serial)
    return bess, pv_mw, pv_n, when


def ring_path(ring):
    return 'M' + 'L'.join(f'{x:.1f},{y:.1f}' for x, y in (xy(lon, lat) for lon, lat in ring)) + 'Z'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--eia', required=True)
    ap.add_argument('--osm', required=True)
    ap.add_argument('--luma', required=True)
    a = ap.parse_args()

    pl = plants(a.eia)
    bess, pv_mw, pv_n, when = luma(a.luma)
    munis = json.load(open(ROOT / 'site/data/municipios.geojson', encoding='utf-8'))['features']
    osm = json.load(open(a.osm, encoding='utf-8'))['elements']

    svg = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" '
           'font-family="Segoe UI, Roboto, Helvetica, Arial, sans-serif">',
           '<defs><filter id="glow" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="2.2" result="b"/>'
           '<feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter></defs>',
           f'<rect width="{W}" height="{H}" fill="#080c1a"/>']

    # municipios by batteries per 100 housing units
    total_b = total_hu = 0
    vals = {}
    for f in munis:
        p = f['properties']
        b = bess.get(p['municipality'])
        if b is None:
            continue
        vals[p['municipality']] = 100 * b / p['HU100']
        total_b += b
        total_hu += p['HU100']
    for f in munis:
        p = f['properties']
        v = vals.get(p['municipality'])
        cls = 0 if v is None else sum(v >= c for c in CLASSES)
        g = f['geometry']
        polys = [g['coordinates']] if g['type'] == 'Polygon' else g['coordinates']
        d = ''.join(ring_path(r) for poly in polys for r in poly)
        svg.append(f'<path d="{d}" fill="{RAMP[cls]}" stroke="#2c3866" stroke-width="0.5"><title>{p["municipality"]}: '
                   f'{v:.1f} batteries per 100 housing units</title></path>')

    # transmission lines, 38 kV under 115 kV under 230 kV
    km = {}
    for volt, col, wd, _ in LINES:
        parts = []
        for e in osm:
            t = e.get('tags', {})
            if e['type'] != 'way' or t.get('power') not in ('line', 'cable') or 'geometry' not in e:
                continue
            vs = t.get('voltage', '').split(';')
            if volt != max(vs, key=lambda s: int(s) if s.isdigit() else 0):
                continue
            pts = [xy(n['lon'], n['lat']) for n in e['geometry'] if n]
            parts.append('M' + 'L'.join(f'{x:.1f},{y:.1f}' for x, y in pts))
            km[volt] = km.get(volt, 0) + sum(
                6371.0 * math.hypot(math.radians(b['lon'] - c['lon']) * KX, math.radians(b['lat'] - c['lat']))
                for b, c in zip(e['geometry'], e['geometry'][1:]) if b and c)
        filt = ' filter="url(#glow)"' if volt != '38000' else ''
        svg.append(f'<path d="{"".join(parts)}" fill="none" stroke="{col}" stroke-width="{wd}" stroke-linejoin="round" '
                   f'stroke-linecap="round" opacity="0.9"{filt}/>')

    # plants, circle area proportional to MW, largest first
    k = 0.55
    for pid, p in sorted(pl.items(), key=lambda kv: -kv[1]['mw']):
        if not (LON0 < p['lon'] < LON1):
            continue
        x, y = xy(p['lon'], p['lat'])
        r = max(2.0, k * math.sqrt(p['mw']))
        svg.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r:.1f}" fill="{COLOR[p["cat"]]}" fill-opacity="0.85" '
                   f'stroke="#080c1a" stroke-width="0.6" filter="url(#glow)"><title>EIA plant {pid}: {p["mw"]:.1f} MW, '
                   f'{p["cat"]}</title></circle>')

    mw_all = sum(p['mw'] for p in pl.values())
    mw_bat = sum(p['by'].get('battery', 0) for p in pl.values())
    mw_ren = sum(p['by'].get(c, 0) for p in pl.values() for c in ('solar', 'wind', 'hydro', 'other'))
    month = when.strftime('%B %Y')
    svg += [f'<text x="{PAD}" y="40" fill="#ffffff" font-size="28" font-weight="700">Puerto Rico\'s power system</text>',
            f'<text x="{PAD}" y="66" fill="#ff8fe0" font-size="15">Where power is made, how it moves, and the homes that now store their own</text>',
            f'<text x="{PAD}" y="89" fill="#9aa6c8" font-size="13">Utility plants of 1 MW or more: {len(pl)}, {mw_all - mw_bat:,.0f} MW, '
            f'of which {mw_ren:,.0f} MW renewable (EIA-860M, September 2026)</text>',
            f'<text x="{PAD}" y="107" fill="#9aa6c8" font-size="13">Rooftop solar: {pv_mw:,.0f} MW at {pv_n:,.0f} installations, '
            f'and {total_b:,.0f} batteries (LUMA, {month})</text>']

    # legend
    ly = TOP + MAP_H + 34
    x = PAD
    for key, col, lab in FUEL:
        svg.append(f'<circle cx="{x + 6}" cy="{ly - 4}" r="6" fill="{col}" filter="url(#glow)"/>'
                   f'<text x="{x + 18}" y="{ly}" fill="#dfe5f5" font-size="13">{lab}</text>')
        x += 30 + 7.2 * len(lab)
    ly2 = ly + 46
    x = PAD
    for mw in (10, 100, 500, 1500):
        r = k * math.sqrt(mw)
        svg.append(f'<circle cx="{x + r}" cy="{ly2 - r + 6}" r="{r:.1f}" fill="none" stroke="#c9d2ea" stroke-width="1"/>'
                   f'<text x="{x + 2 * r + 6}" y="{ly2 + 4}" fill="#c9d2ea" font-size="12.5">{mw:,} MW</text>')
        x += 2 * r + 70
    x += 30
    for volt, col, wd, lab in reversed(LINES):
        svg.append(f'<line x1="{x}" y1="{ly2}" x2="{x + 34}" y2="{ly2}" stroke="{col}" stroke-width="{wd + 0.6}"/>'
                   f'<text x="{x + 42}" y="{ly2 + 4}" fill="#c9d2ea" font-size="12.5">{lab} ({km.get(volt, 0):,.0f} km)</text>')
        x += 60 + 7 * len(lab) + 50
    ly3 = ly2 + 40
    labs = [f'under {CLASSES[0]}'] + [f'{a}-{b}' for a, b in zip(CLASSES, CLASSES[1:])] + [f'{CLASSES[-1]} or more']
    svg.append(f'<text x="{PAD}" y="{ly3 + 4}" fill="#c9d2ea" font-size="12.5">Home batteries per 100 housing units, by municipio '
               f'(Puerto Rico {100 * total_b / total_hu:.1f}):</text>')
    x = PAD + 410
    for col, lab in zip(RAMP, labs):
        svg.append(f'<rect x="{x}" y="{ly3 - 8}" width="26" height="14" fill="{col}" stroke="#2c3866"/>'
                   f'<text x="{x + 32}" y="{ly3 + 4}" fill="#c9d2ea" font-size="12.5">{lab}</text>')
        x += 40 + 7 * len(lab) + 14
    svg.append(f'<text x="{PAD}" y="{H - 30}" fill="#6f7aa0" font-size="11.5">Preview for HANDOFF decision 104, not on the site. '
               'Plants: US EIA-860M (September 2026), circle area proportional to MW, colour = technology with the most MW. Mona not shown.</text>')
    svg.append(f'<text x="{PAD}" y="{H - 13}" fill="#6f7aa0" font-size="11.5">Lines: © OpenStreetMap contributors (ODbL), '
               '2026-11-13. Batteries: LUMA metrics filed with the Puerto Rico Energy Bureau. Housing units: 2020 Census.</text>')
    svg.append('</svg>')
    out = Path(__file__).with_name('preview.svg')
    out.write_text('\n'.join(svg), encoding='utf-8', newline='\n')
    print(out, f'{out.stat().st_size / 1024:.0f} KB', 'plants', len(pl), 'MW', round(mw_all, 1), 'renewable', round(mw_ren, 1),
          'battery MW', round(mw_bat, 1), 'km', {k: round(v) for k, v in km.items()}, 'bess', total_b,
          'per100', round(100 * total_b / total_hu, 2), 'pv', pv_mw, pv_n, when,
          'missing munis', sorted(set(f['properties']['municipality'] for f in munis) - set(vals)))
    print('per-100 range', min(vals.values()), max(vals.values()))


if __name__ == '__main__':
    main()
