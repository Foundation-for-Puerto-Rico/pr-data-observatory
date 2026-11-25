"""Tests for raster.py, the build's reader of Cloud Optimized GeoTIFFs (docs/raster.md).

  python -m unittest tests.test_raster

Every case writes a small tiled GeoTIFF here (classic and BigTIFF, both byte orders; no compression, Deflate and LZW; predictors 1, 2 and 3; integer and float
samples; an overview; a sparse tile) and checks that the reader gives back exactly the array that was written, across tile edges and outside the image.
The georeferencing (tiepoint and scale, ModelTransformation, PixelIsPoint, EPSG), point sampling, the summaries by polygon, the tile cache and the errors
on files the reader must refuse are checked too. No network: the reads against real Landsat, Sentinel-2 and 3DEP files are `python raster.py --check`.
"""
import math
import struct
import sys
import tempfile
import unittest
import zlib
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import raster  # noqa: E402


# ── a minimal LZW encoder (TIFF 6.0 section 13: MSB first, 9-12 bits, early change) ──

def widen(nxt):
    """Code width after the encoder's next free code reaches nxt. The decoder's table is one entry behind, so the encoder widens at 512, 1024 and 2048."""
    return 12 if nxt >= 2048 else 11 if nxt >= 1024 else 10 if nxt >= 512 else 9


def lzw_encode(data):
    out, acc, nacc = bytearray(), 0, 0
    width = 9

    def emit(code):
        nonlocal acc, nacc
        acc = (acc << width) | code
        nacc += width
        while nacc >= 8:
            nacc -= 8
            out.append((acc >> nacc) & 0xFF)

    table = {bytes([i]): i for i in range(256)}
    nxt = 258
    emit(256)
    w = b""
    for byte in data:
        wc = w + bytes([byte])
        if wc in table:
            w = wc
            continue
        emit(table[w])
        table[wc] = nxt
        nxt += 1
        if nxt == 4094:                      # table full: clear (the decoder resets with it)
            emit(256)
            table = {bytes([i]): i for i in range(256)}
            nxt, width = 258, 9
        else:
            width = widen(nxt)
        w = bytes([byte])
    if w:
        emit(table[w])
        nxt += 1                             # the decoder adds an entry on this code too, so EOI may need the next width
        width = widen(nxt)
    emit(257)
    if nacc:
        out.append((acc << (8 - nacc)) & 0xFF)
    return bytes(out)


# ── a minimal tiled GeoTIFF writer ──

def encode_tile(t, bo, compression, predictor):
    t = np.ascontiguousarray(t)
    if predictor == 2:
        d = t.copy()
        d[:, 1:] = t[:, 1:] - t[:, :-1]      # wraps in the integer type
        raw = d.astype(t.dtype.newbyteorder(bo)).tobytes()
    elif predictor == 3:
        th, tw = t.shape
        b = t.astype(t.dtype.newbyteorder(">")).view(np.uint8).reshape(th, tw, t.dtype.itemsize)
        b = b.transpose(0, 2, 1).reshape(th, tw * t.dtype.itemsize)     # byte planes, most significant first
        d = b.copy()
        d[:, 1:] = b[:, 1:] - b[:, :-1]
        raw = d.tobytes()
    else:
        raw = t.astype(t.dtype.newbyteorder(bo)).tobytes()
    if compression == 8:
        return zlib.compress(raw)
    if compression == 5:
        return lzw_encode(raw)
    return raw


def write_tiff(path, levels, *, tile=16, bo="<", big=False, compression=8, predictor=1, nodata=None, epsg=32620,
               tiepoint=(0, 0, 0, 500000.0, 2050000.0, 0), scale=(30.0, 30.0, 0), transformation=None, pixel_is_point=False,
               sparse=(), extra_tags=None, stripped=False, spp=1):
    """levels: list of 2-D arrays, the first full resolution, then overviews. sparse: (level, tile index) pairs written with 0 bytes."""
    I = "Q" if big else "I"
    entry = 20 if big else 12
    blobs = []          # (tile bytes) for every level, then patched offsets
    ifds = []
    for li, arr in enumerate(levels):
        h, w = arr.shape
        across, down = math.ceil(w / tile), math.ceil(h / tile)
        tiles = []
        for tj in range(down):
            for ti in range(across):
                t = np.zeros((tile, tile), arr.dtype)
                part = arr[tj * tile:(tj + 1) * tile, ti * tile:(ti + 1) * tile]
                t[:part.shape[0], :part.shape[1]] = part
                tiles.append(b"" if (li, tj * across + ti) in sparse else encode_tile(t, bo, compression, predictor))
        kind = {"u": 1, "i": 2, "f": 3}[arr.dtype.kind]
        tags = {256: (4, [w]), 257: (4, [h]), 258: (3, [arr.dtype.itemsize * 8]), 259: (3, [compression]), 262: (3, [1]),
                277: (3, [spp]), 284: (3, [1]), 317: (3, [predictor]), 339: (3, [kind])}
        if li:
            tags[254] = (4, [1])
        if not stripped:
            tags[322] = (3, [tile])
            tags[323] = (3, [tile])
            tags[324] = (16 if big else 4, ["OFFSETS"] * len(tiles))
            tags[325] = (16 if big else 4, [len(b) for b in tiles])
        else:
            tags[273] = (4, [0])
        if li == 0:
            if transformation:
                tags[34264] = (12, list(transformation))
            else:
                tags[33550] = (12, list(scale))
                tags[33922] = (12, list(tiepoint))
            keys = [1, 1, 0, 3, 1024, 0, 1, 1, 1025, 0, 1, 2 if pixel_is_point else 1, 3072, 0, 1, epsg]
            tags[34735] = (3, keys)
            if nodata is not None:
                tags[42113] = (2, str(nodata).encode() + b"\0")
            for k, v in (extra_tags or {}).items():
                tags[k] = v
        ifds.append(tags)
        blobs.append(tiles)

    fmt = {3: "H", 4: "I", 12: "d", 16: "Q", 2: "s"}
    size = {3: 2, 4: 4, 12: 8, 16: 8, 2: 1}
    head = 16 if big else 8
    # layout: header, IFDs with their out-of-line values, then tile data
    def ifd_len(tags):
        n = (8 if big else 2) + len(tags) * entry + (8 if big else 4)
        for typ, vals in tags.values():
            total = size[typ] * len(vals)
            if total > (8 if big else 4):
                n += total + (total & 1)
        return n
    starts, at = [], head
    for tags in ifds:
        starts.append(at)
        at += ifd_len(tags)
    data_at = at
    offsets = []
    for tiles in blobs:
        offs = []
        for b in tiles:
            offs.append(data_at if b else 0)
            data_at += len(b)
        offsets.append(offs)
    out = bytearray()
    out += (b"II" if bo == "<" else b"MM")
    out += struct.pack(bo + "H", 43 if big else 42)
    if big:
        out += struct.pack(bo + "HHQ", 8, 0, starts[0])
    else:
        out += struct.pack(bo + "I", starts[0])
    for li, tags in enumerate(ifds):
        assert len(out) == starts[li]
        n = len(tags)
        out += struct.pack(bo + ("Q" if big else "H"), n)
        ext = bytearray()
        ext_at = starts[li] + (8 if big else 2) + n * entry + (8 if big else 4)
        entries = bytearray()
        for tag in sorted(tags):
            typ, vals = tags[tag]
            if tag == 324:
                vals = offsets[li]
            count = len(vals)
            if typ == 2:
                payload = bytes(vals)
            else:
                payload = struct.pack(bo + fmt[typ] * count, *vals)
            inline = 8 if big else 4
            entries += struct.pack(bo + "HH" + I, tag, typ, count)
            if len(payload) <= inline:
                entries += payload.ljust(inline, b"\0")
            else:
                entries += struct.pack(bo + I, ext_at + len(ext))
                ext += payload + (b"\0" if len(payload) & 1 else b"")
        out += entries
        nxt = starts[li + 1] if li + 1 < len(ifds) else 0
        out += struct.pack(bo + I, nxt)
        out += ext
    for tiles in blobs:
        for b in tiles:
            out += b
    Path(path).write_bytes(bytes(out))
    return path


def demo(dtype, shape=(37, 45), seed=7):
    rng = np.random.default_rng(seed)
    if np.dtype(dtype).kind == "f":
        return (rng.standard_normal(shape) * 300 + 500).astype(dtype)
    info = np.iinfo(dtype)
    return rng.integers(info.min, info.max, size=shape, endpoint=True, dtype=dtype)


class Roundtrip(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.n = 0

    def tearDown(self):
        self.dir.cleanup()

    def path(self):
        self.n += 1
        return Path(self.dir.name) / f"t{self.n}.tif"

    def roundtrip(self, arr, **kw):
        p = write_tiff(self.path(), [arr], **kw)
        cog = raster.COG(p)
        got = cog.read_window(0, 0, arr.shape[1], arr.shape[0])
        np.testing.assert_array_equal(got, arr, err_msg=str(kw))
        return cog

    def test_every_compression_predictor_type_and_byte_order(self):
        cases = 0
        for bo in "<>":
            for big in (False, True):
                for comp in (1, 8, 5):
                    for dt in (np.uint8, np.uint16, np.int16, np.int32, np.float32, np.float64):
                        preds = (1, 3) if np.dtype(dt).kind == "f" else (1, 2)
                        for pred in preds:
                            self.roundtrip(demo(dt), bo=bo, big=big, compression=comp, predictor=pred)
                            cases += 1
        self.assertEqual(cases, 2 * 2 * 3 * 6 * 2)

    def test_lzw_long_stream_crosses_every_code_width_and_a_clear(self):
        rng = np.random.default_rng(3)
        data = bytes(rng.integers(0, 40, size=60000, dtype=np.uint8))   # few symbols: long strings, the table fills and clears
        enc = lzw_encode(data)
        self.assertEqual(raster.lzw_decode(enc), data)
        self.assertEqual(raster.lzw_decode(lzw_encode(b"")), b"")
        self.assertEqual(raster.lzw_decode(lzw_encode(b"ABABABA")), b"ABABABA")   # the KwKwK case

    def test_windows_across_tiles_and_outside_the_image(self):
        arr = demo(np.uint16)
        p = write_tiff(self.path(), [arr], nodata=0)
        cog = raster.COG(p)
        for c0, r0, w, h in [(5, 7, 20, 18), (15, 15, 2, 2), (40, 30, 10, 10), (-3, -4, 8, 9), (0, 0, 45, 37)]:
            got = cog.read_window(c0, r0, w, h)
            want = np.zeros((h, w), np.uint16)
            ca, cb, ra, rb = max(c0, 0), min(c0 + w, 45), max(r0, 0), min(r0 + h, 37)
            want[ra - r0:rb - r0, ca - c0:cb - c0] = arr[ra:rb, ca:cb]
            np.testing.assert_array_equal(got, want, err_msg=f"window {c0},{r0},{w},{h}")
        self.assertTrue((cog.read_window(100, 100, 3, 3) == 0).all())

    def test_only_the_tiles_under_a_window_are_read(self):
        arr = demo(np.uint16, (64, 64))
        cog = raster.COG(write_tiff(self.path(), [arr]))
        before = cog.source.reads
        cog.read_window(17, 17, 10, 10)                 # inside tile (1, 1), 16-pixel tiles
        self.assertEqual(cog.source.reads - before, 1)

    def test_values_at_reads_only_the_tiles_under_the_pixels(self):
        arr = demo(np.uint16, (64, 64))
        cog = raster.COG(write_tiff(self.path(), [arr]))
        cols = np.array([1, 2, 40, 63, -1, 64, 5])
        rows = np.array([1, 3, 40, 0, 0, 5, 70])
        before = cog.source.reads
        v, inside = cog.values_at(cols, rows)
        self.assertEqual(list(inside), [True, True, True, True, False, False, False])
        np.testing.assert_array_equal(v[inside], arr[rows[inside], cols[inside]])
        self.assertEqual(cog.source.reads - before, 3)                 # tiles (0,0), (2,2) and (3,0) of 16 px; never the other 13

    def test_sparse_tile_reads_as_nodata(self):
        arr = demo(np.uint16, (32, 32))
        cog = raster.COG(write_tiff(self.path(), [arr], nodata=0, sparse={(0, 3)}))
        got = cog.read_window(0, 0, 32, 32)
        self.assertTrue((got[16:, 16:] == 0).all())
        np.testing.assert_array_equal(got[:16, :], arr[:16, :])

    def test_overview_level_and_its_transform(self):
        arr = demo(np.float32, (64, 48))
        ov = arr[::2, ::2].copy()
        cog = raster.COG(write_tiff(self.path(), [arr, ov], predictor=3, compression=5))
        self.assertEqual([lv.width for lv in cog.levels], [48, 24])
        np.testing.assert_array_equal(cog.read_window(0, 0, 24, 32, level=1), ov)
        self.assertEqual(cog.level_transform(1), (60.0, 0.0, 500000.0, 0.0, -60.0, 2050000.0))


class Georeferencing(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.dir.cleanup()

    def test_tiepoint_scale_epsg_nodata(self):
        p = write_tiff(Path(self.dir.name) / "a.tif", [demo(np.uint16)], nodata=0, epsg=32620)
        cog = raster.COG(p)
        self.assertEqual(cog.epsg, 32620)
        self.assertEqual(cog.nodata, 0.0)
        self.assertEqual(cog.transform, (30.0, 0.0, 500000.0, 0.0, -30.0, 2050000.0))

    def test_a_user_defined_crs_needs_the_epsg_given(self):
        p = write_tiff(Path(self.dir.name) / "u.tif", [demo(np.uint16)], epsg=32767)    # the CRS only as text, as in ECOSTRESS tiles
        with self.assertRaises(raster.RasterError):
            raster.COG(p)
        self.assertEqual(raster.COG(p, epsg=32619).epsg, 32619)
        q = write_tiff(Path(self.dir.name) / "k.tif", [demo(np.uint16)], epsg=32620)
        self.assertEqual(raster.COG(q, epsg=32620).epsg, 32620)
        with self.assertRaises(raster.RasterError):           # a file that names its EPSG is not overruled
            raster.COG(q, epsg=32619)

    def test_tiepoint_at_another_pixel_and_model_transformation(self):
        p = write_tiff(Path(self.dir.name) / "b.tif", [demo(np.uint8)], tiepoint=(10, 20, 0, 800300.0, 2049400.0, 0))
        self.assertEqual(raster.COG(p).transform, (30.0, 0.0, 800000.0, 0.0, -30.0, 2050000.0))
        m = (10.0, 0, 0, 1000.0, 0, -10.0, 0, 5000.0, 0, 0, 0, 0, 0, 0, 0, 1)
        p = write_tiff(Path(self.dir.name) / "c.tif", [demo(np.uint8)], transformation=m)
        self.assertEqual(raster.COG(p).transform, (10.0, 0.0, 1000.0, 0.0, -10.0, 5000.0))

    def test_pixel_is_point_shifts_half_a_pixel_as_gdal_does(self):
        p = write_tiff(Path(self.dir.name) / "d.tif", [demo(np.float32)], pixel_is_point=True, predictor=3,
                       epsg=4269, scale=(1 / 10800, 1 / 10800, 0), tiepoint=(0, 0, 0, -67.0, 19.0, 0))
        cog = raster.COG(p)
        a, _, c, _, e, f = cog.transform
        self.assertAlmostEqual(c, -67.0 - a / 2)
        self.assertAlmostEqual(f, 19.0 - e / 2)
        self.assertEqual(cog.epsg, 4269)

    def test_read_bbox_and_sample_in_lon_lat(self):
        # a UTM zone 20N grid near San Juan; each pixel holds its column + 1000 * row, so a read tells where it came from
        rows, cols = 64, 64
        arr = (np.arange(cols)[None, :] + 1000 * np.arange(rows)[:, None]).astype(np.int32)
        x0, y0 = 800000.0, 2040000.0
        p = write_tiff(Path(self.dir.name) / "e.tif", [arr], tiepoint=(0, 0, 0, x0, y0, 0), scale=(30.0, 30.0, 0))
        cog = raster.COG(p)
        lon, lat = raster.transform_points([x0 + 30 * 10.5], [y0 - 30 * 20.5], 32620, 4326)
        self.assertEqual(cog.sample(lon, lat)[0], 20 * 1000 + 10)
        self.assertTrue(np.isnan(cog.sample([-60.0], [10.0])[0]))
        box = raster.to_crs_bounds((x0 + 300, y0 - 900, x0 + 600, y0 - 600), 32620, 4326)
        got, tr = cog.read_bbox(box)
        self.assertEqual(tr[0], 30.0)
        # the window covers columns 10-20 and rows 20-30 of the grid, a little more because the lon/lat box is wider in UTM
        c0, r0 = round((tr[2] - x0) / 30), round((y0 - tr[5]) / 30)
        np.testing.assert_array_equal(got, arr[r0:r0 + got.shape[0], c0:c0 + got.shape[1]])
        self.assertLessEqual(c0, 10)
        self.assertLessEqual(r0, 20)
        self.assertGreaterEqual(c0 + got.shape[1], 20)
        self.assertGreaterEqual(r0 + got.shape[0], 30)


class Zonal(unittest.TestCase):
    def test_pixel_centres_inside_the_polygon_and_masks(self):
        from shapely.geometry import box
        arr = np.arange(100, dtype=np.float64).reshape(10, 10)     # value = 10 * row + col
        tr = (1.0, 0.0, 0.0, 0.0, -1.0, 10.0)                        # x = col, y = 10 - row
        arr[2, 2] = -9999
        valid = np.ones_like(arr, bool)
        valid[3, 3] = False
        shapes = {"sq": box(2, 6, 5, 8.2),                           # centers x 2.5-4.5, y 6.5-7.5 -> rows 2-3, cols 2-4
                  "out": box(50, 50, 60, 60)}
        z = raster.zonal(arr, tr, 32620, shapes, nodata=-9999, shapes_crs=32620, valid=valid)
        self.assertEqual(z["sq"]["pixels"], 6)
        want = [23, 24, 32, 34]                                       # 22 is nodata, 33 masked
        self.assertEqual(z["sq"]["valid"], 4)
        self.assertAlmostEqual(z["sq"]["mean"], float(np.mean(want)))
        self.assertEqual((z["sq"]["min"], z["sq"]["max"]), (23.0, 34.0))
        self.assertAlmostEqual(z["sq"]["p50"], float(np.percentile(want, 50)))
        self.assertEqual(z["out"], {"pixels": 0, "valid": 0, "mean": None, "min": None, "max": None, "p10": None, "p50": None, "p90": None})

    def test_polygons_in_lon_lat_over_a_utm_raster(self):
        from shapely.geometry import Polygon
        x0, y0 = 800000.0, 2040000.0
        arr = np.ones((100, 100))
        tr = (30.0, 0.0, x0, 0.0, -30.0, y0)
        corners = [(x0 + 600, y0 - 600), (x0 + 1500, y0 - 600), (x0 + 1500, y0 - 1500), (x0 + 600, y0 - 1500)]
        lon, lat = raster.transform_points([c[0] for c in corners], [c[1] for c in corners], 32620, 4326)
        z = raster.zonal(arr, tr, 32620, {"p": Polygon(zip(lon, lat))})
        self.assertAlmostEqual(z["p"]["pixels"], 30 * 30, delta=31)    # a 900 m square of 30 m pixels, edges reprojected


class CacheAndErrors(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.d = Path(self.dir.name)

    def tearDown(self):
        self.dir.cleanup()

    def test_second_read_comes_from_the_cache(self):
        arr = demo(np.uint16, (32, 32))
        p = write_tiff(self.d / "c.tif", [arr])
        cog = raster.COG(p, cache=self.d / "cache")
        cog.read_window(0, 0, 32, 32)
        cog2 = raster.COG(p, cache=self.d / "cache")
        self.assertEqual(cog2.source.reads, 0)                 # the header came from the cache too
        np.testing.assert_array_equal(cog2.read_window(0, 0, 32, 32), arr)
        self.assertEqual(cog2.source.reads, 0)
        self.assertEqual(sorted(f.name for f in (self.d / "cache").rglob("*.bin")), ["0_0_0.bin", "0_0_1.bin", "0_1_0.bin", "0_1_1.bin", "header.bin"])

    def test_offline_reads_only_the_cache(self):
        arr = demo(np.uint16, (32, 32))
        p = write_tiff(self.d / "o.tif", [arr])
        raster.COG(p, cache=self.d / "c1").read_window(0, 0, 16, 16)          # caches the header and tile (0, 0) only
        cog = raster.COG(p, cache=self.d / "c1", offline=True)
        np.testing.assert_array_equal(cog.read_window(0, 0, 16, 16), arr[:16, :16])
        with self.assertRaises(raster.RasterError) as cm:
            cog.read_window(16, 16, 16, 16)                                    # a tile that is not cached
        self.assertIn("offline", str(cm.exception))
        with self.assertRaises(raster.RasterError):
            raster.COG(p, cache=self.d / "empty", offline=True)               # no cached header

    def test_cache_key_leaves_out_the_query_string(self):
        import hashlib
        k1 = hashlib.sha1(raster._short("https://x/y.tif?sig=1").encode()).hexdigest()
        k2 = hashlib.sha1(raster._short("https://x/y.tif?sig=2").encode()).hexdigest()
        self.assertEqual(k1, k2)

    def test_refuses_what_it_would_misread(self):
        arr = demo(np.uint16, (16, 16))
        cases = {
            "striped": dict(stripped=True),
            "samples per pixel": dict(spp=3),
            "compression 7": dict(compression=7),
            "user-defined CRS": dict(epsg=32767),
        }
        for want, kw in cases.items():
            if kw.get("compression") == 7:
                p = write_tiff(self.d / "x.tif", [arr], compression=1)
                b = bytearray(p.read_bytes())
                # patch the Compression tag's value from 1 to 7
                i = b.find(struct.pack("<HHI", 259, 3, 1))
                b[i + 8:i + 10] = struct.pack("<H", 7)
                p.write_bytes(bytes(b))
            else:
                p = write_tiff(self.d / "x.tif", [arr], **kw)
            with self.assertRaises(raster.RasterError, msg=want) as cm:
                raster.COG(p)
            self.assertIn(want.split()[0].lower(), str(cm.exception).lower(), msg=str(cm.exception))
        (self.d / "n.tif").write_bytes(b"GIF89a" + b"\0" * 100)
        with self.assertRaises(raster.RasterError):
            raster.COG(self.d / "n.tif")


if __name__ == "__main__":
    unittest.main()
