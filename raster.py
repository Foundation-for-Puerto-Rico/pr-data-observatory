"""A small reader of Cloud Optimized GeoTIFFs (COGs) for the PR Data Observatory's build: satellite and lidar rasters summarized by barrio and municipio.

    python raster.py --check      # read three real files over the network and check them against known facts (Cerro de Punta, Landsat, Sentinel-2)

Why our own reader (HANDOFF decision 80 b, 2026-11-04). The build has numpy, pyproj and shapely, but no raster library: rasterio and GDAL are not in
requirements.txt (landslide.py decodes its PNG tiles with zlib and numpy for the same reason). The rasters the terrain and climate plan needs
(docs/terrain-climate-proposal-2026-11.md) are all COGs, which are tiled and indexed at the front of the file, so a reader can fetch only the tiles that
cover Puerto Rico with HTTP range requests, instead of whole scenes of 100 to 400 MB. What the sources use (read from their headers on 2026-11-04):

    source                                   compression   predictor        sample type   tile
    Landsat Collection 2 Level-2 (Planetary)  Deflate (8)   none (1)         uint16        256
    Sentinel-2 L2A (Earth Search)             Deflate (8)   horizontal (2)   uint16/uint8  1024/512
    USGS 3DEP 1 m and 1/3 arc-second          LZW (5)       floating (3)     float32       512

This module reads exactly that family: classic TIFF and BigTIFF, either byte order, tiled (not striped), one sample per pixel, compression none, Deflate or
LZW, predictor 1, 2 or 3, unsigned and signed integers and floats of 8 to 64 bits, overviews (the later full-resolution-reduced IFDs), the GDAL nodata tag,
and the georeferencing of a north-up image (ModelTiepoint + ModelPixelScale, or ModelTransformation without rotation) with an EPSG code from the GeoKeys.
Anything else stops with a clear error naming the tag, so a file the reader would misread is never summarized.

Use:

    import raster
    cog = raster.COG(url, cache="cache/raster/landsat")         # reads the header (a few range requests); local paths work too
    arr, tr = cog.read_bbox((-66.2, 18.3, -65.9, 18.5))          # lon/lat box -> array and its affine transform (in the raster's CRS)
    stats = raster.zonal(arr, tr, cog.epsg, {"72127": shape}, nodata=cog.nodata)   # per polygon: pixels, valid, mean, median, p10, p90, min, max
    values = cog.sample([-66.59], [18.17])                       # values at lon/lat points

Tiles are cached by URL path (the query string, which holds Planetary Computer's short-lived token, is left out of the key), level and tile number, so a
second build reads nothing from the network. Values are returned as stored: a source's scale and offset (Landsat ST = DN x 0.00341802 + 149.0 K) are the
caller's, and are named in the step that uses them.
"""
import hashlib
import math
import struct
import sys
import time
import zlib
from pathlib import Path

import numpy as np

UA = {"User-Agent": "pr-digital-twin/1.0 (Foundation for Puerto Rico; open-data build)"}
HEADER_BYTES = 65536          # first read; COGs keep every IFD and most tag arrays here, and more is read when one is not

# TIFF tags this reader understands
TAG = {"width": 256, "height": 257, "bits": 258, "compression": 259, "photometric": 262, "strip_offsets": 273, "spp": 277, "planar": 284,
       "predictor": 317, "tile_width": 322, "tile_height": 323, "tile_offsets": 324, "tile_counts": 325, "sample_format": 339,
       "subfile": 254, "pixel_scale": 33550, "tiepoint": 33922, "transformation": 34264, "geokeys": 34735, "nodata": 42113}
TYPES = {1: ("B", 1), 2: ("s", 1), 3: ("H", 2), 4: ("I", 4), 5: ("II", 8), 6: ("b", 1), 7: ("B", 1), 8: ("h", 2), 9: ("i", 4),
         10: ("ii", 8), 11: ("f", 4), 12: ("d", 8), 16: ("Q", 8), 17: ("q", 8), 18: ("Q", 8)}
SAMPLE = {1: "u", 2: "i", 3: "f"}   # SampleFormat: unsigned, signed, IEEE float


class RasterError(ValueError):
    """A file this reader cannot read correctly; the message names what it met."""


# ── bytes: local file or HTTP range requests ────────────────────────────────

class _Source:
    def __init__(self, src, session=None, retries=4, offline=False):
        self.src = str(src)
        self.offline = offline    # True: any read is an error (a rebuild from the cache must not touch the network)
        self.remote = self.src.startswith(("http://", "https://"))
        self.retries = retries
        if self.remote:
            import requests
            self.http = session or requests.Session()
        elif not Path(self.src).is_file():
            raise RasterError(f"no such file: {self.src}")
        self.reads = 0            # number of reads (range requests or file reads), for the check and the tests
        self.bytes = 0

    def read(self, offset, length):
        if length <= 0:
            return b""
        if self.offline:
            raise RasterError(f"{_short(self.src)}: bytes {offset}-{offset + length - 1} are not in the cache (offline)")
        self.reads += 1
        self.bytes += length
        if not self.remote:                       # open per read: no handle stays open (Windows cannot delete an open file)
            with open(self.src, "rb") as fh:
                fh.seek(offset)
                return fh.read(length)
        err = None
        for attempt in range(self.retries):
            try:
                r = self.http.get(self.src, headers={**UA, "Range": f"bytes={offset}-{offset + length - 1}"}, timeout=120)
                if r.status_code == 206:
                    return r.content
                if r.status_code == 200:          # a server that ignores Range sends the whole file: take the slice, but say so once
                    raise RasterError(f"{_short(self.src)} ignores HTTP range requests (200 for bytes={offset}-); a COG needs 206")
                if r.status_code in (429, 500, 502, 503, 504):
                    err = f"HTTP {r.status_code}"
                    time.sleep(2 ** attempt)
                    continue
                raise RasterError(f"{_short(self.src)}: HTTP {r.status_code} for a range request")
            except RasterError:
                raise
            except Exception as e:                # network errors: retry with backoff
                err = repr(e)
                time.sleep(2 ** attempt)
        raise RasterError(f"{_short(self.src)}: gave up after {self.retries} attempts ({err})")


def _short(url):
    return url.split("?")[0]


# ── TIFF structure ──────────────────────────────────────────────────────────

class _Header:
    """The first bytes of the file, extended on demand, and the IFDs read from them."""

    def __init__(self, source, buf=None):
        self.s = source
        self.buf = buf if buf is not None else source.read(0, HEADER_BYTES)
        if self.buf[:2] == b"II":
            self.bo = "<"
        elif self.buf[:2] == b"MM":
            self.bo = ">"
        else:
            raise RasterError("not a TIFF file (no II or MM byte order mark)")
        ver = self._unpack("H", 2)
        if ver == 42:
            self.big, first = False, self._unpack("I", 4)
        elif ver == 43:
            self.big, first = True, self._unpack("Q", 8)
        else:
            raise RasterError(f"TIFF version {ver} is neither classic (42) nor BigTIFF (43)")
        self.ifds = []
        off, seen = first, set()
        while off and off not in seen:
            seen.add(off)
            tags, off = self._ifd(off)
            self.ifds.append(tags)

    def _need(self, end):
        if end > len(self.buf):
            more = max(end - len(self.buf), HEADER_BYTES)
            self.buf += self.s.read(len(self.buf), more)
            if end > len(self.buf):
                raise RasterError("the file ends inside its own header")

    def _unpack(self, fmt, at):
        size = struct.calcsize(self.bo + fmt)
        self._need(at + size)
        v = struct.unpack_from(self.bo + fmt, self.buf, at)
        return v[0] if len(v) == 1 else v

    def _ifd(self, off):
        n = self._unpack("Q" if self.big else "H", off)
        entry, at = (20, off + 8) if self.big else (12, off + 2)
        self._need(at + n * entry + 8)
        tags = {}
        for i in range(n):
            p = at + i * entry
            tag, typ = self._unpack("HH", p)
            count = self._unpack("Q" if self.big else "I", p + 4)
            if typ not in TYPES:
                continue                       # an unknown type in a tag we never read
            fmt, size = TYPES[typ]
            total = size * count
            inline = 8 if self.big else 4
            vp = p + (12 if self.big else 8)
            if total > inline:
                vp = self._unpack("Q" if self.big else "I", vp)
            self._need(vp + total)
            if typ == 2:
                tags[tag] = self.buf[vp:vp + count].split(b"\0")[0].decode("ascii", "replace")
            elif typ in (5, 10):
                raw = struct.unpack_from(self.bo + fmt[0] * (2 * count), self.buf, vp)
                tags[tag] = tuple(raw[k] / raw[k + 1] if raw[k + 1] else 0.0 for k in range(0, len(raw), 2))
            else:
                tags[tag] = struct.unpack_from(self.bo + fmt[0] * count, self.buf, vp)
        nxt = self._unpack("Q" if self.big else "I", at + n * entry)
        return tags, nxt


def _one(tags, name, default=None):
    v = tags.get(TAG[name])
    if v is None:
        if default is None:
            raise RasterError(f"missing TIFF tag {name} ({TAG[name]})")
        return default
    return v[0] if isinstance(v, tuple) else v


class Level:
    """One image of the file: the full resolution (level 0) or an overview."""

    def __init__(self, tags, bo):
        self.width, self.height = _one(tags, "width"), _one(tags, "height")
        if TAG["tile_width"] not in tags:
            raise RasterError("striped TIFF (no TileWidth tag): only tiled TIFFs (COGs) are read")
        self.tw, self.th = _one(tags, "tile_width"), _one(tags, "tile_height")
        spp = _one(tags, "spp", 1)
        if spp != 1:
            raise RasterError(f"{spp} samples per pixel: only single-band files are read")
        self.compression = _one(tags, "compression", 1)
        if self.compression not in (1, 5, 8, 32946):
            raise RasterError(f"compression {self.compression} (only none 1, LZW 5 and Deflate 8/32946 are read)")
        self.predictor = _one(tags, "predictor", 1)
        if self.predictor not in (1, 2, 3):
            raise RasterError(f"predictor {self.predictor}")
        bits = _one(tags, "bits", 1)
        fmt = SAMPLE.get(_one(tags, "sample_format", 1))
        if fmt is None or bits not in (8, 16, 32, 64) or (fmt == "f" and bits < 32):
            raise RasterError(f"sample type {fmt}{bits}")
        self.dtype = np.dtype(f"{bo}{fmt}{bits // 8}")
        if self.predictor == 3 and fmt != "f":
            raise RasterError("floating-point predictor on integer samples")
        self.offsets = tags[TAG["tile_offsets"]]
        self.counts = tags[TAG["tile_counts"]]
        self.across = math.ceil(self.width / self.tw)
        self.down = math.ceil(self.height / self.th)
        if len(self.offsets) != self.across * self.down:
            raise RasterError(f"{len(self.offsets)} tile offsets for {self.across} x {self.down} tiles (planar configuration 2 is not read)")


# ── decoding ────────────────────────────────────────────────────────────────

def lzw_decode(data):
    """TIFF LZW (MSB-first codes, 9 to 12 bits, early change), as in the TIFF 6.0 specification, section 13."""
    out = bytearray()
    table = [bytes([i]) for i in range(256)] + [b"", b""]   # 256 = Clear, 257 = EndOfInformation
    width, bitpos, nbits = 9, 0, len(data) * 8
    prev = None
    get = int.from_bytes
    while bitpos + width <= nbits:
        byte = bitpos >> 3
        chunk = get(data[byte:byte + 3].ljust(3, b"\0"), "big")
        code = (chunk >> (24 - width - (bitpos & 7))) & ((1 << width) - 1)
        bitpos += width
        if code == 256:
            table = table[:258]
            width, prev = 9, None
            continue
        if code == 257:
            break
        if prev is None:
            entry = table[code]
        elif code < len(table):
            entry = table[code]
            table.append(prev + entry[:1])
        elif code == len(table):
            entry = prev + prev[:1]
            table.append(entry)
        else:
            raise RasterError(f"LZW code {code} beyond the table ({len(table)})")
        out += entry
        prev = entry
        n = len(table) + 1                    # early change: widen one code before the table fills
        if n >= 2048:
            width = 12
        elif n >= 1024:
            width = 11
        elif n >= 512:
            width = 10
    return bytes(out)


def decode_tile(raw, level):
    """Bytes of one tile -> a (th, tw) array in native byte order."""
    c = level.compression
    if c in (8, 32946):
        raw = zlib.decompress(raw)
    elif c == 5:
        raw = lzw_decode(raw)
    th, tw, dt = level.th, level.tw, level.dtype
    need = th * tw * dt.itemsize
    if len(raw) < need:                         # a short last tile: pad (the padding is outside the image and is cut off)
        raw = raw + b"\0" * (need - len(raw))
    if level.predictor == 3:                    # floating point: per row, bytes split into planes (most significant first), then differenced
        b = np.frombuffer(raw[:need], np.uint8).reshape(th, tw * dt.itemsize)
        b = np.cumsum(b, axis=1, dtype=np.uint8)
        b = b.reshape(th, dt.itemsize, tw).transpose(0, 2, 1)     # -> (row, pixel, byte), bytes big-endian
        return np.ascontiguousarray(b).view(dt.newbyteorder(">")).reshape(th, tw).astype(dt.newbyteorder("="))
    a = np.frombuffer(raw[:need], dt).reshape(th, tw).astype(dt.newbyteorder("="))
    if level.predictor == 2:                    # horizontal differencing, with the wrap-around of the sample type
        a = np.cumsum(a, axis=1, dtype=a.dtype)
    return a


# ── georeferencing ──────────────────────────────────────────────────────────

def _geokeys(v):
    if not v or len(v) < 4:
        return {}
    keys = {}
    for i in range(v[3]):
        k, loc, cnt, val = v[4 + 4 * i: 8 + 4 * i]
        if loc == 0:
            keys[k] = val
    return keys


class COG:
    """A tiled GeoTIFF read lazily by tiles. `src` is a URL or a local path; `cache` a folder for tile bytes (optional)."""

    def __init__(self, src, cache=None, session=None, workers=8, offline=False, epsg=None):
        self.src = str(src)
        self.workers = workers            # parallel tile requests for a remote file (read_window)
        self.source = _Source(src, session=session, offline=offline)
        self.cache = Path(cache) if cache else None
        self._key = hashlib.sha1(_short(self.src).encode()).hexdigest()[:16]
        hp = self.cache / self._key / "header.bin" if self.cache else None   # the header is cached too, so a rebuild from the cache needs no network
        h = _Header(self.source, hp.read_bytes() if hp is not None and hp.exists() else None)
        if hp is not None and not hp.exists():
            hp.parent.mkdir(parents=True, exist_ok=True)
            hp.write_bytes(h.buf)
        self.bo = h.bo
        tags = h.ifds[0]
        self.levels = [Level(t, h.bo) for t in h.ifds if (_one(t, "subfile", 0) & 4) == 0]   # skip masks (NewSubfileType bit 2)
        self.levels.sort(key=lambda lv: -lv.width)
        self.width, self.height, self.dtype = self.levels[0].width, self.levels[0].height, self.levels[0].dtype.newbyteorder("=")
        nd = tags.get(TAG["nodata"])
        self.nodata = float(nd) if isinstance(nd, str) and nd.strip() not in ("", "nan") else (math.nan if isinstance(nd, str) else None)
        self.transform = self._transform(tags)
        gk = _geokeys(tags.get(TAG["geokeys"]))
        self.epsg = gk.get(3072) or gk.get(2048)          # ProjectedCSTypeGeoKey, else GeographicTypeGeoKey
        if self.epsg in (None, 32767):
            if epsg is None:
                raise RasterError("no EPSG code in the GeoKeys (user-defined CRS): give the CRS explicitly (epsg=)")
            self.epsg = int(epsg)                       # given by the caller, who knows the file's CRS from elsewhere (ECOSTRESS tiles: the MGRS zone)
        elif epsg is not None and int(epsg) != self.epsg:
            raise RasterError(f"the file says EPSG:{self.epsg}, not EPSG:{epsg}")
        self.area_or_point = "point" if gk.get(1025) == 2 else "area"   # RasterPixelIsPoint
        if self.area_or_point == "point":       # as GDAL does: shift by half a pixel so the transform names pixel corners
            a, b, c, d, e, f = self.transform
            self.transform = (a, b, c - a / 2, d, e, f - e / 2)

    @staticmethod
    def _transform(tags):
        if TAG["transformation"] in tags:
            m = tags[TAG["transformation"]]
            if m[1] or m[4]:
                raise RasterError("rotated raster (ModelTransformation with rotation terms)")
            return (m[0], 0.0, m[3], 0.0, m[5], m[7])
        sc, tp = tags.get(TAG["pixel_scale"]), tags.get(TAG["tiepoint"])
        if not sc or not tp:
            raise RasterError("no georeferencing (ModelPixelScale and ModelTiepoint, or ModelTransformation)")
        i, j, _, x, y, _ = tp[:6]
        return (sc[0], 0.0, x - i * sc[0], 0.0, -sc[1], y + j * sc[1])   # (a, b, c, d, e, f): x = a*col + c, y = e*row + f

    # transform of a level (overviews cover the same extent with fewer pixels)
    def level_transform(self, level=0):
        a, _, c, _, e, f = self.transform
        lv = self.levels[level]
        return (a * self.width / lv.width, 0.0, c, 0.0, e * self.height / lv.height, f)

    def _tile(self, level, ti, tj):
        lv = self.levels[level]
        k = tj * lv.across + ti
        off, cnt = lv.offsets[k], lv.counts[k]
        if cnt == 0:                           # a sparse tile: all nodata
            fill = self.nodata if self.nodata is not None and not (math.isnan(self.nodata) and lv.dtype.kind != "f") else 0
            return np.full((lv.th, lv.tw), fill, lv.dtype.newbyteorder("="))
        path = self.cache / self._key / f"{level}_{ti}_{tj}.bin" if self.cache else None
        if path is not None and path.exists():
            raw = path.read_bytes()
        else:
            raw = self.source.read(off, cnt)
            if path is not None:
                path.parent.mkdir(parents=True, exist_ok=True)
                tmp = path.with_suffix(".part")
                tmp.write_bytes(raw)
                tmp.replace(path)
        return decode_tile(raw, lv)

    def read_window(self, col0, row0, cols, rows, level=0):
        """Pixels [row0, row0+rows) x [col0, col0+cols) of a level, clipped to the image; cells outside it get nodata (or 0)."""
        lv = self.levels[level]
        fill = self.nodata if self.nodata is not None else 0
        dt = np.float64 if (isinstance(fill, float) and math.isnan(fill) and lv.dtype.kind != "f") else lv.dtype.newbyteorder("=")
        out = np.full((rows, cols), fill, dt)
        c0, r0 = max(col0, 0), max(row0, 0)
        c1, r1 = min(col0 + cols, lv.width), min(row0 + rows, lv.height)
        if c0 >= c1 or r0 >= r1:
            return out
        keys = [(ti, tj) for tj in range(r0 // lv.th, (r1 - 1) // lv.th + 1) for ti in range(c0 // lv.tw, (c1 - 1) // lv.tw + 1)]
        if self.source.remote and self.workers > 1 and len(keys) > 1:   # a window is tens of small range requests: fetch them in parallel
            from concurrent.futures import ThreadPoolExecutor
            with ThreadPoolExecutor(min(self.workers, len(keys))) as ex:
                tiles = dict(zip(keys, ex.map(lambda k: self._tile(level, *k), keys)))
        else:
            tiles = {k: self._tile(level, *k) for k in keys}
        for (ti, tj), t in tiles.items():
            tx0, ty0 = ti * lv.tw, tj * lv.th
            xa, xb = max(c0, tx0), min(c1, tx0 + lv.tw)
            ya, yb = max(r0, ty0), min(r1, ty0 + lv.th)
            out[ya - row0:yb - row0, xa - col0:xb - col0] = t[ya - ty0:yb - ty0, xa - tx0:xb - tx0]
        return out

    def window_of(self, bounds, level=0):
        """Pixel window (col0, row0, cols, rows) that covers bounds (minx, miny, maxx, maxy) in the raster's CRS."""
        a, _, c, _, e, f = self.level_transform(level)
        minx, miny, maxx, maxy = bounds
        cols_ = sorted(((minx - c) / a, (maxx - c) / a))
        rows_ = sorted(((maxy - f) / e, (miny - f) / e))
        col0, row0 = math.floor(cols_[0]), math.floor(rows_[0])
        return col0, row0, math.ceil(cols_[1]) - col0, math.ceil(rows_[1]) - row0

    def read_bbox(self, bbox, crs=4326, level=0):
        """Read the window that covers bbox (minx, miny, maxx, maxy) given in `crs` (lon/lat by default). Returns (array, transform)."""
        bounds = to_crs_bounds(bbox, crs, self.epsg)
        col0, row0, cols, rows = self.window_of(bounds, level)
        arr = self.read_window(col0, row0, cols, rows, level)
        a, _, c, _, e, f = self.level_transform(level)
        return arr, (a, 0.0, c + col0 * a, 0.0, e, f + row0 * e)

    def values_at(self, cols, rows, level=0):
        """The stored values at pixels (cols, rows) of a level, and a mask of the pixels inside the image. Reads only the tiles that hold them,
        in parallel for a remote file: for scattered pixels (land cells, points) far fewer bytes than the window around them."""
        lv = self.levels[level]
        cols, rows = np.asarray(cols, np.int64), np.asarray(rows, np.int64)
        inside = (cols >= 0) & (cols < lv.width) & (rows >= 0) & (rows < lv.height)
        out = np.zeros(len(cols), lv.dtype.newbyteorder("="))
        k = np.flatnonzero(inside)
        if not k.size:
            return out, inside
        tid = (rows[k] // lv.th) * lv.across + cols[k] // lv.tw
        keys = [(int(t % lv.across), int(t // lv.across)) for t in np.unique(tid)]
        if self.source.remote and self.workers > 1 and len(keys) > 1:
            from concurrent.futures import ThreadPoolExecutor
            with ThreadPoolExecutor(min(self.workers, len(keys))) as ex:
                tiles = dict(zip(keys, ex.map(lambda q: self._tile(level, *q), keys)))
        else:
            tiles = {q: self._tile(level, *q) for q in keys}
        order = np.argsort(tid, kind="stable")
        bounds = np.flatnonzero(np.diff(tid[order])) + 1
        for grp in np.split(order, bounds):
            ti, tj = int(cols[k[grp[0]]] // lv.tw), int(rows[k[grp[0]]] // lv.th)
            out[k[grp]] = tiles[(ti, tj)][rows[k[grp]] % lv.th, cols[k[grp]] % lv.tw]
        return out, inside

    def sample(self, xs, ys, crs=4326, level=0):
        """Values at points (x, y in `crs`); nan outside the image or on nodata. Reads only the tiles under the points."""
        X, Y = transform_points(xs, ys, crs, self.epsg)
        a, _, c, _, e, f = self.level_transform(level)
        cols = np.floor((np.asarray(X) - c) / a).astype(np.int64)
        rows = np.floor((np.asarray(Y) - f) / e).astype(np.int64)
        v, inside = self.values_at(cols, rows, level)
        out = np.where(inside, v.astype(np.float64), np.nan)
        if self.nodata is not None:
            out[(out == self.nodata) | (math.isnan(self.nodata) & np.isnan(out))] = np.nan
        return out


# ── coordinates ─────────────────────────────────────────────────────────────

_TRANSFORMERS = {}


def _transformer(src, dst):
    from pyproj import Transformer
    key = (src, dst)
    if key not in _TRANSFORMERS:
        _TRANSFORMERS[key] = Transformer.from_crs(f"EPSG:{src}", f"EPSG:{dst}", always_xy=True)
    return _TRANSFORMERS[key]


def transform_points(xs, ys, src, dst):
    if src == dst:
        return np.asarray(xs, float), np.asarray(ys, float)
    return _transformer(src, dst).transform(np.asarray(xs, float), np.asarray(ys, float))


def to_crs_bounds(bbox, src, dst, densify=21):
    """Bounds of a box after reprojection, densifying the edges (a lon/lat box is curved in UTM)."""
    if src == dst:
        return tuple(bbox)
    minx, miny, maxx, maxy = bbox
    t = np.linspace(0, 1, densify)
    xs = np.concatenate([minx + (maxx - minx) * t, np.full(densify, maxx), maxx - (maxx - minx) * t, np.full(densify, minx)])
    ys = np.concatenate([np.full(densify, miny), miny + (maxy - miny) * t, np.full(densify, maxy), maxy - (maxy - miny) * t])
    X, Y = transform_points(xs, ys, src, dst)
    return (float(np.min(X)), float(np.min(Y)), float(np.max(X)), float(np.max(Y)))


# ── summaries by polygon ────────────────────────────────────────────────────

def zonal(arr, transform, epsg, shapes, nodata=None, shapes_crs=4326, valid=None, percentiles=(10, 50, 90)):
    """Summaries of `arr` for each polygon of `shapes` ({id: shapely geometry in `shapes_crs`}).

    A pixel belongs to a polygon when its center is inside it (the rule of landslide.py). `valid` is an optional boolean array of the same shape
    (for example a cloud mask) that removes pixels on top of nodata. Returns {id: {pixels, valid, mean, min, max, p10, p50, p90}}; pixels counts
    every center inside the polygon, valid the ones with a value, and the statistics are None when no pixel is valid.
    """
    import shapely
    from shapely.ops import transform as shp_transform
    a, _, c, _, e, f = transform
    rows, cols = arr.shape
    data = arr.astype(np.float64, copy=False)
    ok = np.isfinite(data)
    if nodata is not None and not (isinstance(nodata, float) and math.isnan(nodata)):
        ok &= data != nodata
    if valid is not None:
        ok &= valid
    tr = None if shapes_crs == epsg else _transformer(shapes_crs, epsg)
    out = {}
    for k, geom in shapes.items():
        g = geom if tr is None else shp_transform(tr.transform, geom)
        minx, miny, maxx, maxy = g.bounds
        c0 = max(int(math.floor((min(minx, maxx) - c) / a)), 0)
        c1 = min(int(math.ceil((max(minx, maxx) - c) / a)), cols)
        r0 = max(int(math.floor((maxy - f) / e)), 0)
        r1 = min(int(math.ceil((miny - f) / e)), rows)
        rec = {"pixels": 0, "valid": 0, "mean": None, "min": None, "max": None, **{f"p{p}": None for p in percentiles}}
        if c0 < c1 and r0 < r1:
            cc, rr = np.meshgrid(np.arange(c0, c1), np.arange(r0, r1))
            inside = shapely.contains_xy(g, c + (cc + 0.5) * a, f + (rr + 0.5) * e)
            rec["pixels"] = int(inside.sum())
            vals = data[r0:r1, c0:c1][inside & ok[r0:r1, c0:c1]]
            rec["valid"] = int(vals.size)
            if vals.size:
                rec.update(mean=float(vals.mean()), min=float(vals.min()), max=float(vals.max()),
                           **{f"p{p}": float(v) for p, v in zip(percentiles, np.percentile(vals, percentiles))})
        out[k] = rec
    return out


# ── live check against known facts ──────────────────────────────────────────

def _check():
    """Three real files, three facts. Network required; nothing is written."""
    import json
    import requests
    s = requests.Session()
    ok = True

    def report(name, cond, detail):
        nonlocal ok
        ok &= bool(cond)
        print(f"{'PASS' if cond else 'FAIL'}  {name}: {detail}")

    # 1. Cerro de Punta, Puerto Rico's highest point, 1,338 m (USGS GNIS), from 3DEP 1/3 arc-second (LZW, floating predictor)
    q = s.get("https://tnmaccess.nationalmap.gov/api/v1/products", headers=UA, timeout=60, params={
        "datasets": "National Elevation Dataset (NED) 1/3 arc-second", "bbox": "-66.62,18.15,-66.57,18.19", "max": 5, "outputFormat": "JSON"}).json()
    url = sorted((i["downloadURL"] for i in q["items"] if i["downloadURL"].endswith(".tif")), reverse=True)[0]
    cog = COG(url, session=s)
    arr, tr = cog.read_bbox((-66.60, 18.16, -66.58, 18.18))
    top = float(np.nanmax(np.where(arr == cog.nodata, np.nan, arr)))
    report("3DEP 1/3 arc-second, Cerro de Punta", abs(top - 1338) < 15, f"highest cell {top:.1f} m within 1 km (published 1,338 m); {cog.source.reads} reads, {cog.source.bytes / 1e6:.1f} MB")
    ov = cog.levels[2] if len(cog.levels) > 2 else None
    if ov is not None:
        arr2, _ = cog.read_bbox((-66.60, 18.16, -66.58, 18.18), level=2)
        report("3DEP overview agrees", abs(float(np.nanmean(arr2)) - float(np.nanmean(arr))) < 25,
               f"mean {np.nanmean(arr):.1f} m full resolution, {np.nanmean(arr2):.1f} m at overview 2")

    # 2. Landsat surface temperature over San Juan (Deflate, no predictor): plausible kelvin after the USGS scale. A scene's footprint is slanted and
    #    row 048 stops at about 18.41 N, so take a scene whose footprint holds the whole box (else most pixels are fill).
    import shapely.geometry as sg
    box = (-66.09, 18.37, -66.03, 18.42)
    feats = s.post("https://planetarycomputer.microsoft.com/api/stac/v1/search", headers=UA, timeout=60, json={
        "collections": ["landsat-c2-l2"], "bbox": list(box), "limit": 20,
        "datetime": "2026-01-01T00:00:00Z/2026-10-31T23:59:59Z", "query": {"eo:cloud_cover": {"lt": 20}}}).json()["features"]
    item = next(f for f in feats if sg.shape(f["geometry"]).contains(sg.box(*box)))
    tok = s.get("https://planetarycomputer.microsoft.com/api/sas/v1/token/landsat-c2-l2", headers=UA, timeout=60).json()["token"]
    cog = COG(item["assets"]["lwir11"]["href"] + "?" + tok, session=s)
    arr, tr = cog.read_bbox(box)
    k = arr[arr != 0].astype(float) * 0.00341802 + 149.0
    med = float(np.median(k) - 273.15) if k.size else float("nan")
    # Some pixels inside the footprint are 0 where USGS computed no surface temperature, mostly under and next to clouds (QA_PIXEL bit 3 on 60% of them
    # in LC09_L2SP_004047_20261029, none flagged water or fill, checked 2026-11-04): step 1 masks them with QA_PIXEL, so here half the box is enough.
    report("Landsat ST over San Juan", 15 < med < 50 and k.size > 0.5 * arr.size,
           f"{item['id']}: median surface {med:.1f} C over {k.size:,} of {arr.size:,} pixels (EPSG {cog.epsg})")

    # 3. Sentinel-2 over El Yunque (Deflate, horizontal predictor): dense forest has NDVI above 0.6
    feats = s.post("https://earth-search.aws.element84.com/v1/search", headers=UA, timeout=60, json={
        "collections": ["sentinel-2-l2a"], "bbox": [-65.82, 18.29, -65.76, 18.33], "limit": 10,
        "datetime": "2026-01-01T00:00:00Z/2026-10-31T23:59:59Z", "query": {"eo:cloud_cover": {"lt": 10}}}).json()["features"]
    item = feats[0]
    red = COG(item["assets"]["red"]["href"], session=s)
    nir = COG(item["assets"]["nir"]["href"], session=s)
    box = (-65.80, 18.30, -65.78, 18.32)
    r, _ = red.read_bbox(box)
    n, _ = nir.read_bbox(box)
    m = (r > 0) & (n > 0)
    ndvi = (n[m].astype(float) - r[m]) / (n[m].astype(float) + r[m])
    md = float(np.median(ndvi)) if ndvi.size else float("nan")
    report("Sentinel-2 NDVI over El Yunque", md > 0.6, f"{item['id']}: median NDVI {md:.2f} over {ndvi.size:,} pixels (EPSG {red.epsg})")
    print(json.dumps({"ok": ok}))
    return ok


if __name__ == "__main__":
    if "--check" in sys.argv:
        sys.exit(0 if _check() else 1)
    print(__doc__)
