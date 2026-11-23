"""Night-time lights for the PR Data Observatory, for the 901 barrios, the 78 municipios and Puerto Rico: the mean brightness that NASA's Black Marble monthly product
(VNP46A3) records at night, every month since January 2012, and the share of the area's pixels that the product flags as poor quality or gap-filled (mostly clouds).

    python nightlights.py              # download the months missing from cache/nightlights/ and build the three files below (needs EARTHDATA_TOKEN)
    python nightlights.py --since 2024 # only the months from January 2024 on (a quick first run)
    python nightlights.py --refresh    # download every month again, even the ones already summarised
    python nightlights.py --keep       # keep the downloaded HDF5 files in cache/nightlights/h5/ (by default each is deleted once it is summarised: about 70 MB a month)
    python nightlights.py --check      # rebuild from the cached summaries and exit 1 when a published file is not what they give (no network, no token, nothing written)

The login. LAADS lists its files to anyone, but a download without a login answers 303 and sends the browser to a sign-in page. The build reads a NASA Earthdata user
token from the EARTHDATA_TOKEN environment variable (in GitHub Actions, the repository secret of that name) and sends it only to LAADS, in the Authorization header.
The token is never printed, written to the cache, the repository or a published file, and the site never calls NASA: visitors need no login (HANDOFF decision 75;
docs/nightlights-setup.md says how the account and the token are made). Without the variable the script says so and stops, and changes nothing.

The source. Román, M.O., et al., 2018, NASA's Black Marble nighttime lights product suite, Remote Sensing of Environment 210, 113-143
(https://doi.org/10.1016/j.rse.2018.03.017), and the monthly product, VNP46A3 collection 2 (https://doi.org/10.5067/VIIRS/VNP46A3.002): the Day/Night Band of the
VIIRS instrument on the Suomi NPP satellite, corrected for moonlight (the lunar BRDF correction of VNP46A2), with clouds, snow and stray light screened out, and
composited each month on a 15 arc-second grid (about 460 m across at Puerto Rico's latitude) in tiles of 10 by 10 degrees, as HDF5 files. NASA data are free to use
with credit (https://www.earthdata.nasa.gov/engage/open-data-services-software-policies/data-use-guidance).

Which tiles. Tile hHHvVV covers longitudes -180 + 10*HH to -170 + 10*HH and latitudes 90 - 10*VV down to 80 - 10*VV. All of Puerto Rico, Mona and Desecheo to
Culebra and Vieques (67.95 to 65.2 degrees west, 17.85 to 18.55 degrees north), lies in h11v07 (70 to 60 degrees west): h10v07 (80 to 70 degrees west) holds
Hispaniola and no barrio of Puerto Rico, so it is not downloaded (tiles_for works it out from the barrio outlines).

How each figure is made (docs/nightlights.md):
  - Layer: AllAngle_Composite_Snow_Free (the composite of every view angle, outside snow; Puerto Rico has none), in nanowatts per cm2 per steradian
    (nW/cm2/sr): in collection 2 a 32-bit float with fill value -999.9, scale 1 and offset 0 (Black Marble User Guide v2.0, October 2024, table 11). The file's
    own scale_factor, add_offset and _FillValue are used when it has them, and a negative value is no value (the valid range is 0 and up). Its quality layer,
    AllAngle_Composite_Snow_Free_Quality (table 12): 0 good (more than three clear observations in the month), 1 poor (three or fewer), 2 gap-filled (none: the
    value comes from earlier data), 255 no value. Clouds are the usual reason for few clear nights over Puerto Rico.
  - Pixels: each pixel counts in the barrio whose outline (site/data/barrios.geojson) holds its centre. A barrio smaller than a pixel that holds no centre takes
    the pixel under its representative point, for its own figure only. Pixels whose centre is over the sea count nowhere.
  - Mean radiance: the sum of the radiance of the area's pixels that have a value over their number (a pooled mean, so a municipio's and Puerto Rico's are over
    all their pixels, not averages of barrios). A year's value pools the pixels of its twelve months; a year with fewer than twelve months is in the monthly
    file only.
  - Quality share: the pixels flagged poor or gap-filled over the pixels with a quality value, in percent (a year's pools its twelve months).
No personal data: the files hold means and shares for areas, no images.
"""

import json
import os
import re
import sys
import time
from datetime import date, timedelta
from pathlib import Path

import requests

import housing_series as hs

ROOT = Path(__file__).resolve().parent
CACHE = ROOT / "cache" / "nightlights"
OUT = hs.OUT
OUT_SERIES = OUT / "nightlights_series.json"
OUT_BARRIO = OUT / "nightlights_barrio.json"
OUT_MONTHLY = OUT / "nightlights_monthly.json"
UA = {"User-Agent": "pr-digital-twin/1.0 (Foundation for Puerto Rico; open-data build)"}
log = hs.log

ARCHIVE = "https://ladsweb.modaps.eosdis.nasa.gov/archive/allData/5200/VNP46A3"   # collection 2 (5200), listed openly; a file download needs the token
TOKEN_VAR = "EARTHDATA_TOKEN"
FIRST_YEAR = 2012                     # the product starts in January 2012
GRID = 2400                           # pixels on each side of a tile (10 degrees at 15 arc-seconds)
STEP = 10 / GRID                      # degrees per pixel
RAD = "AllAngle_Composite_Snow_Free"
QUAL = RAD + "_Quality"
Q_GOOD, Q_FILL = 0, 255               # the quality layer: 0 good, 1 poor, 2 gap-filled, 255 no value
FILL = -999.9                         # the radiance's fill value in collection 2 (32-bit float, scale 1), when the file does not say
FILE_RE = re.compile(r"^VNP46A3\.A(\d{4})(\d{3})\.(h\d\dv\d\d)\.\d{3}\.\d+\.h5$")
HDF5_MAGIC = b"\x89HDF\r\n\x1a\n"
BUSY = {429, 500, 502, 503, 504}
G = "Economy · Night-time lights (NASA Black Marble)"
UNIT = "nW/cm²/sr"

SOURCES = {
    "nasa_black_marble": {
        "name": "NASA Black Marble — VNP46A3, VIIRS/NPP lunar BRDF-adjusted nighttime lights, monthly (collection 2)",
        "url": "https://doi.org/10.5067/VIIRS/VNP46A3.002",
        "license": "NASA data: Creative Commons Zero (CC0) unless a product is marked otherwise; NASA asks users to cite the data",
        "note": "Read from LAADS DAAC with a free NASA Earthdata login used only by the build; summaries only, no images. Román et al. (2018), https://doi.org/10.1016/j.rse.2018.03.017."},
    "census_tiger": {"name": "US Census Bureau — 2020 county subdivisions (barrios)", "url": "https://www.census.gov/geographies/mapping-files/time-series/geo/tiger-line-file.html",
                     "license": "US Government work (no US copyright)", "note": "Barrio outlines."},
}


# ── The login ────────────────────────────────────────────────────────────────

def token():
    """The Earthdata token from the environment, or None. Never printed."""
    t = os.environ.get(TOKEN_VAR, "").strip()
    return t or None


NO_TOKEN = (f"nightlights: {TOKEN_VAR} is not set, so nothing was downloaded and no file was changed. "
            "The NASA Earthdata token is made once by FPR (docs/nightlights-setup.md) and kept only as a GitHub Actions secret or a local environment variable.")
REFUSED = (f"nightlights: LAADS refused the download (HTTP {{code}}; pages: {{where}}). The token in {TOKEN_VAR} is missing or expired (tokens last about 60 days), "
           "the LAADS DAAC application is not approved on the account, or the account has not yet signed in once to LAADS and accepted its terms: see "
           "docs/nightlights-setup.md, steps 2 and 3. Nothing was written.")


# ── Tiles and the grid ───────────────────────────────────────────────────────

def tiles_for(bounds):
    """The Black Marble tiles ('h11v07') that a (west, south, east, north) box touches."""
    w, s, e, n = bounds
    hs_ = range(int((w + 180) // 10), int((e + 180) // 10) + 1)
    vs = range(int((90 - n) // 10), int((90 - s) // 10) + 1)
    return [f"h{h:02d}v{v:02d}" for v in vs for h in hs_]


def tile_origin(tile):
    """(west longitude, north latitude) of a tile's top-left corner."""
    h, v = int(tile[1:3]), int(tile[4:6])
    return -180 + 10 * h, 90 - 10 * v


def window(tile, bounds):
    """(row0, row1, col0, col1) of the tile's pixels that cover the box, rows from the north."""
    x0, y0 = tile_origin(tile)
    w, s, e, n = bounds
    px = lambda d: int(d / STEP + 1e-9)   # the pixel a distance from the corner falls in (1e-9: 3.8 degrees is pixel 912, not 911.99...)
    c0 = max(0, px(w - x0)); c1 = min(GRID, px(e - x0) + 1)
    r0 = max(0, px(y0 - n)); r1 = min(GRID, px(y0 - s) + 1)
    return r0, r1, c0, c1


def centres(tile, win):
    """Longitude and latitude of the centre of each pixel of a window (2-D arrays)."""
    import numpy as np
    x0, y0 = tile_origin(tile)
    r0, r1, c0, c1 = win
    lon = x0 + (np.arange(c0, c1) + 0.5) * STEP
    lat = y0 - (np.arange(r0, r1) + 0.5) * STEP
    return np.meshgrid(lon, lat)


def owners(geoms, lon, lat):
    """The index of the outline that holds each pixel's centre (-1: none), and [(outline, row, col)] for the outlines that hold no centre: the pixel under their
    representative point, so a barrio smaller than a pixel still has a value. `geoms` are shapely polygons in longitude and latitude."""
    import numpy as np
    import shapely
    owner = np.full(lon.shape, -1, dtype=np.int64)
    x0, y0, step = float(lon[0, 0]), float(lat[0, 0]), float(lon[0, 1] - lon[0, 0]) if lon.shape[1] > 1 else STEP
    for j, g in enumerate(geoms):
        gw, gs, ge, gn = g.bounds
        c0 = max(0, int((gw - x0) / step)); c1 = min(lon.shape[1], int((ge - x0) / step) + 2)
        r0 = max(0, int((y0 - gn) / step)); r1 = min(lon.shape[0], int((y0 - gs) / step) + 2)
        if c0 >= c1 or r0 >= r1:
            continue
        sub = owner[r0:r1, c0:c1]
        inside = shapely.contains_xy(g, lon[r0:r1, c0:c1], lat[r0:r1, c0:c1]) & (sub < 0)   # equally on two outlines: the first (the crosswalk's order)
        sub[inside] = j
    have = set(np.unique(owner[owner >= 0]).tolist())
    extra = []
    for j, g in enumerate(geoms):
        if j in have:
            continue
        p = g.representative_point()
        c = int(round((p.x - x0) / step)); r = int(round((y0 - p.y) / step))
        if 0 <= r < lon.shape[0] and 0 <= c < lon.shape[1]:
            extra.append((j, r, c))
    return owner, extra


def zonal(rad, qual, owner, n, extra=()):
    """For each of n areas: [sum of radiance, pixels with a radiance, pixels flagged poor or gap-filled, pixels with a quality value]. `rad` is radiance with NaN for
    no value, `qual` the quality layer, `owner` the area of each pixel (-1: none); `extra` adds one pixel to an area that owns none (owners)."""
    import numpy as np
    m = owner >= 0
    o, r, q = owner[m], rad[m], qual[m]
    ok = np.isfinite(r)
    hq = q != Q_FILL
    poor = hq & (q != Q_GOOD)
    out = np.zeros((n, 4))
    out[:, 0] = np.bincount(o[ok], weights=r[ok], minlength=n)
    out[:, 1] = np.bincount(o[ok], minlength=n)
    out[:, 2] = np.bincount(o[poor], minlength=n)
    out[:, 3] = np.bincount(o[hq], minlength=n)
    for j, row, col in extra:
        v, qq = rad[row, col], qual[row, col]
        if np.isfinite(v):
            out[j, 0] += v; out[j, 1] += 1
        if qq != Q_FILL:
            out[j, 3] += 1
            out[j, 2] += qq != Q_GOOD
    return out


def pooled(stats):
    """(mean radiance, quality share in %) of stats rows [sum, valid, poor, with quality] added together; None where there is nothing to divide by."""
    s, v, p, t = (float(x) for x in stats)
    return (round(s / v, 3) if v else None), (round(p / t * 100, 1) if t else None)


# ── Reading a file ───────────────────────────────────────────────────────────

def _attr(ds, name, default):
    v = ds.attrs.get(name, default)
    try:
        return float(v[0]) if hasattr(v, "__len__") and not isinstance(v, (str, bytes)) else float(v)
    except (TypeError, ValueError, IndexError):
        return default


def read_tile(path, tile, win):
    """(radiance with NaN for no value, quality) of a VNP46A3 HDF5 file, for the window's pixels. Stops when the layers or the grid are not what this script expects."""
    import h5py
    import numpy as np
    found = {}

    def seen(name, obj):
        if isinstance(obj, h5py.Dataset):
            found.setdefault(name.rsplit("/", 1)[-1], obj)
    r0, r1, c0, c1 = win
    with h5py.File(path, "r") as f:
        f.visititems(seen)
        if RAD not in found or QUAL not in found:
            raise SystemExit(f"nightlights: {Path(path).name} has no {RAD} or {QUAL} layer (it has {sorted(found)[:12]}): the product changed; read it again by hand")
        ds, dq = found[RAD], found[QUAL]
        if ds.shape != (GRID, GRID) or dq.shape != (GRID, GRID):
            raise SystemExit(f"nightlights: {Path(path).name}: the layers are {ds.shape}, not {GRID} x {GRID}")
        if "lat" in found and "lon" in found:   # the grid runs from the north-west corner, a pixel every 15 arc-seconds
            x0, y0 = tile_origin(tile)
            la, lo = found["lat"][[0, -1]], found["lon"][[0, -1]]
            if abs(la[0] - (y0 - STEP / 2)) > STEP or abs(lo[0] - (x0 + STEP / 2)) > STEP or la[1] > la[0]:
                raise SystemExit(f"nightlights: {Path(path).name}: the grid is not the one of {tile} (first latitude {la[0]}, first longitude {lo[0]})")
        raw = ds[r0:r1, c0:c1]
        q = dq[r0:r1, c0:c1].astype(np.uint8)
        fill = _attr(ds, "_FillValue", FILL)
        scale, offset = _attr(ds, "scale_factor", 1.0), _attr(ds, "add_offset", 0.0)
    raw = raw.astype(np.float64)
    rad = raw * scale + offset
    rad[np.isclose(raw, fill) | ~np.isfinite(raw) | (rad < 0)] = np.nan
    return rad, q


# ── The archive ──────────────────────────────────────────────────────────────

def get(url, tries=6, **kw):
    """A GET with a polite retry (a 429 or a 5xx answer, a timeout or a dropped connection waits 4, 8, 16, 32, 60 s)."""
    for attempt in range(tries):
        try:
            r = requests.get(url, timeout=(30, 300), **kw)
            if r.status_code in BUSY and attempt < tries - 1:
                time.sleep(min(60, 4 * 2 ** attempt))
                continue
            return r
        except requests.RequestException as e:
            if attempt == tries - 1:
                raise SystemExit(f"nightlights: {url} failed: {e}")
            time.sleep(min(60, 4 * 2 ** attempt))


def listing(url):
    r = get(url + ".json", headers=UA)
    r.raise_for_status()
    return r.json().get("content", [])


def month_of(year, doy):
    d = date(year, 1, 1) + timedelta(days=doy - 1)
    return f"{d.year}-{d.month:02d}"


def list_months(tiles, since=FIRST_YEAR):
    """{(month 'YYYY-MM', tile): (file name, url, bytes)} of the files LAADS lists (no login needed)."""
    out = {}
    years = sorted(int(x["name"]) for x in listing(ARCHIVE) if str(x.get("name", "")).isdigit() and int(x["name"]) >= since)
    for y in years:
        for d in listing(f"{ARCHIVE}/{y}"):
            if not str(d.get("name", "")).isdigit():
                continue
            for f in listing(f"{ARCHIVE}/{y}/{d['name']}"):
                m = FILE_RE.match(f.get("name", ""))
                if m and m.group(3) in tiles:
                    out[(month_of(int(m.group(1)), int(m.group(2))), m.group(3))] = (f["name"], f.get("downloadsLink") or f"{ARCHIVE}/{y}/{d['name']}/{f['name']}", f.get("size"))
    return out


NASA_HOSTS = {"ladsweb.modaps.eosdis.nasa.gov", "urs.earthdata.nasa.gov"}   # the only hosts the token is sent to: LAADS and the Earthdata Login it checks it with


def open_file(url, tok, session=None):
    """(response, hops) for one file. LAADS answers a download with a redirect to its licence check (/profiles/licenses/...), which sends it to Earthdata Login;
    with the token, Earthdata sends it back to LAADS, which sets a session cookie and sends it to the file. The redirects are followed by hand so that the token
    goes to LAADS and Earthdata Login only (a download host elsewhere gets no token), and hops lists the pages passed (host and path, never a query string)."""
    from urllib.parse import urljoin, urlsplit
    s = session or requests.Session()
    hops = []
    for _ in range(12):
        u = urlsplit(url)
        if u.scheme != "https":
            raise SystemExit(f"nightlights: LAADS sent the download to a page that is not https ({u.netloc}{u.path})")
        h = {**UA, **({"Authorization": f"Bearer {tok}"} if u.hostname in NASA_HOSTS else {})}
        for attempt in range(6):
            try:
                r = s.get(url, headers=h, allow_redirects=False, stream=True, timeout=(30, 300))
            except requests.RequestException as e:
                if attempt == 5:
                    raise SystemExit(f"nightlights: {u.netloc}{u.path} failed: {e}")
                time.sleep(min(60, 4 * 2 ** attempt))
                continue
            if r.status_code in BUSY and attempt < 5:
                r.close()
                time.sleep(min(60, 4 * 2 ** attempt))
                continue
            break
        hops.append(f"{r.status_code} {u.netloc}{u.path}")
        if not 300 <= r.status_code < 400:
            return r, hops
        url = urljoin(url, r.headers.get("Location", ""))
        r.close()
    raise SystemExit("nightlights: too many redirects from LAADS: " + " -> ".join(hops))


def download(url, dest, tok, session=None):
    """Stream one file to dest (open_file). It stops with REFUSED when LAADS or Earthdata Login refuse the token: a 401 or 403, or a page instead of the file."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_suffix(".part")
    r, hops = open_file(url, tok, session)
    ctype = (r.headers.get("content-type") or "").lower()
    if r.status_code in (401, 403) or (r.status_code == 200 and "html" in ctype):
        r.close()
        raise SystemExit(REFUSED.format(code=r.status_code, where=" -> ".join(hops)))
    r.raise_for_status()
    with open(part, "wb") as fh:
        for chunk in r.iter_content(1 << 20):
            fh.write(chunk)
    with open(part, "rb") as fh:
        if fh.read(8) != HDF5_MAGIC:
            part.unlink()
            raise SystemExit(f"nightlights: {dest.name} is not an HDF5 file ({ctype}): LAADS answered with something else (" + " -> ".join(hops) + ")")
    part.replace(dest)


def diagnose(tok):
    """What LAADS answers for one file, and the shape of the token, without ever printing the token or the account in it (--diagnose)."""
    import base64
    from datetime import datetime, timezone
    from urllib.parse import urlsplit
    raw = os.environ.get(TOKEN_VAR, "")
    QUOTES = "\"'"
    parts = tok.split(".")
    print(f"token: {len(tok)} characters; {len(parts)} parts separated by dots (a NASA Earthdata token has 3); "
          f"starts like a token: {tok[:3] == 'eyJ'}; starts with the word Bearer: {tok.lower().startswith('bearer')}; "
          f"spaces or line breaks inside: {any(c.isspace() for c in tok)}; quotes: {any(c in QUOTES for c in tok)}; "
          f"spaces around it in the secret: {raw != raw.strip()}")
    if len(parts) == 3:
        try:
            pay = json.loads(base64.urlsafe_b64decode(parts[1] + "=" * (-len(parts[1]) % 4)))
            exp = pay.get("exp")
            print(f"token: issued by {pay.get('iss', '?')}, type {pay.get('type', '?')}, expires "
                  f"{datetime.fromtimestamp(exp, timezone.utc).isoformat() if exp else '?'}")   # the account name in the token is not printed
        except ValueError:
            print("token: the middle part does not decode")
    f = "VNP46A3.A2012001.h11v07.002.2025086154536.h5"
    r, hops = open_file(f"{ARCHIVE}/2012/001/{f}", tok)
    print(f"following the redirects with the token: HTTP {r.status_code}, {r.headers.get('content-type')}, {r.headers.get('content-length')} bytes; pages: " + " -> ".join(hops))
    r.close()
    for label, url in (("archive", f"{ARCHIVE}/2012/001/{f}"),
                       ("api", f"https://ladsweb.modaps.eosdis.nasa.gov/api/v2/content/archives/allData/5200/VNP46A3/2012/001/{f}")):
        for auth in (True, False):
            h = {**UA, **({"Authorization": f"Bearer {tok}"} if auth else {})}
            r = requests.get(url, headers=h, allow_redirects=False, stream=True, timeout=(30, 60))
            loc = r.headers.get("Location")
            print(f"{label}, {'with' if auth else 'without'} the token: HTTP {r.status_code}"
                  + (f", sent to {urlsplit(loc)._replace(query='', fragment='').geturl()}" if loc else f", {r.headers.get('content-type')}, {r.headers.get('content-length')} bytes"))
            r.close()
    return 0


# ── Build ────────────────────────────────────────────────────────────────────

def load_barrios():
    import conditions
    return conditions.Barrios()


def summaries():
    """{month: summary} of the months already in the cache."""
    d = CACHE / "summary"
    return {p.stem: json.loads(p.read_text(encoding="utf-8")) for p in sorted(d.glob("*.json"))} if d.exists() else {}


def summarise(B, files, keep=False, tok=None):
    """Summarise each (month, tile) file into cache/nightlights/summary/YYYY-MM.json: the four sums of zonal() for each barrio (its own figure), each municipio and
    Puerto Rico (each pixel once)."""
    import numpy as np
    bounds = tuple(np.array([g.bounds for g in B.geoms]).min(axis=0)[:2]) + tuple(np.array([g.bounds for g in B.geoms]).max(axis=0)[2:])
    muni = np.array([B.mids.index(B.ids[i][:5]) for i in range(len(B.ids))])
    grid = {}
    session = requests.Session()   # keeps the LAADS session cookie between files
    for (month, tile), (name, url, size) in sorted(files.items()):
        if tile not in grid:
            win = window(tile, bounds)
            lon, lat = centres(tile, win)
            own, extra = owners(B.geoms, lon, lat)
            grid[tile] = (win, own, extra)
            log(f"  {tile}: {int((own >= 0).sum()):,} pixels in a barrio, {len(extra)} barrios smaller than a pixel take the pixel under them")
        win, own, extra = grid[tile]
        h5 = CACHE / "h5" / name
        if not h5.exists():
            log(f"  downloading {name} ({(size or 0) / 1e6:.0f} MB)")
            download(url, h5, tok, session)
        rad, q = read_tile(h5, tile, win)
        bz = zonal(rad, q, own, len(B.ids), extra)
        mown = np.where(own >= 0, muni[np.maximum(own, 0)], -1)
        mz = zonal(rad, q, mown, len(B.mids))
        iz = zonal(rad, q, np.where(own >= 0, 0, -1), 1)
        rec = {"month": month, "files": [name], "barrio": np.round(bz, 3).tolist(), "municipio": np.round(mz, 3).tolist(), "island": np.round(iz[0], 3).tolist()}
        p = CACHE / "summary" / f"{month}.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(rec, separators=(",", ":")), encoding="utf-8")
        if not keep:
            h5.unlink()
        mean, share = pooled(iz[0])
        log(f"  {month}: Puerto Rico {mean} {UNIT}, {share}% of pixels poor or gap-filled")


def assemble(B, S):
    """The three published files from the monthly summaries S ({month: summary})."""
    import numpy as np
    months = sorted(S)
    nb, nm = len(B.ids), len(B.mids)
    by_year = {}
    for m in months:
        by_year.setdefault(int(m[:4]), []).append(m)
    years = [y for y, ms in sorted(by_year.items()) if len(ms) == 12]
    partial = {str(y): len(ms) for y, ms in by_year.items() if len(ms) < 12}

    def stack(level, n):
        return np.array([S[m][level] for m in months]).reshape(len(months), n, 4)
    bs, ms_, isl = stack("barrio", nb), stack("municipio", nm), np.array([S[m]["island"] for m in months]).reshape(len(months), 1, 4)
    areas = np.concatenate([ms_, isl], axis=1)   # the 78 municipios, then Puerto Rico

    def yearly(a):
        out_r, out_q = {}, {}
        for y in years:
            idx = [months.index(m) for m in by_year[y]]
            tot = a[idx].sum(axis=0)
            pr = [pooled(row) for row in tot]
            out_r[str(y)] = [p[0] for p in pr]
            out_q[str(y)] = [p[1] for p in pr]
        return out_r, out_q

    def monthly(a):
        pr = [[pooled(a[k, i]) for k in range(len(months))] for i in range(a.shape[1])]
        return [[p[0] for p in row] for row in pr], [[p[1] for p in row] for row in pr]
    mr, mq = yearly(areas)
    br, bq = yearly(bs)
    REF = "NASA Black Marble VNP46A3 (collection 2), AllAngle_Composite_Snow_Free and its quality layer, tile h11v07, 15 arc-seconds (about 460 m); Román et al. (2018)"
    CAV = (" Light is a proxy for activity and for power: it rises with streetlights, buildings and traffic and falls in a blackout, but it is not a count of people, "
           "jobs or homes with power. The product removes moonlight (lunar BRDF correction) and screens out clouds; a month with many clouds rests on fewer nights "
           "or is gap-filled from an earlier month (the quality share says how much).")
    MEAN = (" The mean of the area's pixels with a value, each pixel in the barrio that holds its centre; a municipio's and Puerto Rico's means are over all their pixels "
            "(pooled, not an average of barrios). A year's value pools the pixels of its twelve months.")

    def var(key, label, unit, d, definition, vals, **extra):
        return {"key": key, "group": G, "label": label, "unit": unit, "d": d, "type": "rate", "sources": ["nasa_black_marble", "census_tiger"], "ref": REF,
                "definition": definition, "family": "nightlights", "counted": False, "noPerHU": True, "barrioFile": OUT_BARRIO.name, **extra, "years": vals}
    vs = [var("ntl_radiance", "Night-time light, mean radiance (NASA Black Marble, nW/cm²/sr)", UNIT, 2,
              "The mean brightness of the area at night that the VIIRS Day/Night Band records, in nanowatts per square centimetre per steradian (nW/cm²/sr)." + MEAN + CAV, mr),
          var("ntl_poor_pct", "Night-time light, pixels of poor quality or gap-filled (%)", "%", 1,
              "The share of the area's pixels that the product flags as poor quality (three or fewer clear observations in the month) or gap-filled (none), over all its pixels with a quality value, "
              "pooled over the year's twelve months. A high share means the area's light figure rests on few clear nights." + CAV, mq)]
    notes = {"tiles": ["h11v07"], "grid_arcsec": 15, "layer": RAD, "quality_layer": QUAL, "months": len(months), "first_month": months[0] if months else None,
             "last_month": months[-1] if months else None, "partial_years": partial, "files": sorted({f for m in months for f in S[m]["files"]})[-3:]}
    series = {"as_of": months[-1] if months else None, "years": years, "geo": {"ids": B.mids + ["72"], "names": B.names + ["Puerto Rico"]}, "vars": vs,
              "sources": SOURCES, "notes": notes}
    barrio = {"level": "barrio", "years": years, "geo": {"ids": B.ids}, "vars": [{"key": "ntl_radiance", "years": br}, {"key": "ntl_poor_pct", "years": bq}],
              "notes": {"areas": nb, "source": "nightlights.py; the municipio values and the method are in nightlights_series.json"}}
    mmr, mmq = monthly(areas)
    bmr, bmq = monthly(bs)
    mon = {"months": months, "unit": {"ntl_radiance": UNIT, "ntl_poor_pct": "%"},
           "municipio": {"ids": B.mids + ["72"], "ntl_radiance": mmr, "ntl_poor_pct": mmq},
           "barrio": {"ids": B.ids, "ntl_radiance": bmr, "ntl_poor_pct": bmq},
           "notes": {"source": "nightlights.py; one value for each area and month, in the order of months; the method is in nightlights_series.json"}}
    return series, barrio, mon


def build(refresh=False, check=False, keep=False, since=FIRST_YEAR):
    if not check:
        tok = token()
        if not tok:
            print(NO_TOKEN)
            return 0
    B = load_barrios()
    if not check:
        tiles = sorted({t for g in B.geoms for t in tiles_for(g.bounds)})
        if len(tiles) != 1:   # one summary a month: a second tile would need its sums added to the first's
            raise SystemExit(f"nightlights: the barrios fall in {tiles}; this script reads one tile")
        have = summaries()
        if have and not refresh:   # a monthly run lists only the latest summarised year and later (a few requests instead of about 200); --refresh lists every year again
            since = max(since, int(max(have)[:4]))
        files = list_months(tiles, since)
        todo = {k: v for k, v in files.items() if refresh or k[0] not in have or have[k[0]]["files"] != [v[0]]}   # a month NASA reprocessed has a new file name
        log(f"nightlights: {len(files)} monthly files listed for {', '.join(tiles)} since {since}; {len(todo)} to download")
        summarise(B, todo, keep, tok)
    S = summaries()
    if not S:
        print("nightlights: no month is summarised in cache/nightlights/summary/: nothing to build")
        return 1 if check else 0
    status = 0
    for path, d in zip((OUT_SERIES, OUT_BARRIO, OUT_MONTHLY), assemble(B, S)):
        if check:
            old = json.loads(path.read_text(encoding="utf-8")) if path.exists() else None
            if old is None or {**old, "built": None} != {**json.loads(json.dumps(d, ensure_ascii=False)), "built": None}:
                print(f"{path.name} is not what the cache gives: run python nightlights.py")
                status = 1
            else:
                print(f"{path.name} matches the cache")
            continue
        path.write_text(json.dumps({"built": date.today().isoformat(), **d}, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        log(f"wrote {path.name}: {path.stat().st_size / 1024:.1f} KB")
    return status


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    a = sys.argv[1:]
    if "--diagnose" in a:
        raise SystemExit(diagnose(token()) if token() else print(NO_TOKEN) or 1)
    since = int(a[a.index("--since") + 1]) if "--since" in a else FIRST_YEAR
    raise SystemExit(build("--refresh" in a, "--check" in a, "--keep" in a, since))
