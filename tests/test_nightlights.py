"""Tests for nightlights.py: night-time lights by barrio and municipio (NASA Black Marble VNP46A3; docs/nightlights.md).

  python -m unittest tests.test_nightlights

No network and no token: the zonal summary is checked on a small raster made here (pixels in two outlines, one outline smaller than a pixel, pixels over the sea,
fill values and every quality flag), the tile arithmetic on Puerto Rico's box, the pooled yearly figures on made-up monthly summaries, the HDF5 reader on a file
written here (when h5py is installed), and the login rules: without EARTHDATA_TOKEN the script stops and writes nothing, and a redirect to the sign-in page stops it
with a message that never holds the token.
"""
import json
import math
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import nightlights as nl  # noqa: E402

try:
    import numpy as np
    from shapely.geometry import box
except ImportError:   # the build's environment has both (requirements.txt)
    np = None

try:
    import h5py
except ImportError:
    h5py = None


@unittest.skipIf(np is None, "numpy and shapely are needed")
class Tiles(unittest.TestCase):
    def test_puerto_rico_lies_in_one_tile(self):
        self.assertEqual(nl.tiles_for((-67.95, 17.85, -65.20, 18.55)), ["h11v07"])   # Mona to Culebra: 70 to 60 degrees west
        self.assertEqual(nl.tiles_for((-71.0, 18.0, -69.0, 19.0)), ["h10v07", "h11v07"])   # Hispaniola's east coast crosses into h10v07
        self.assertEqual(nl.tile_origin("h11v07"), (-70, 20))

    def test_window_and_centres(self):
        win = nl.window("h11v07", (-66.2, 18.3, -66.0, 18.5))
        r0, r1, c0, c1 = win
        self.assertEqual((r0, c0), (int(1.5 * 240), int(3.8 * 240)))
        lon, lat = nl.centres("h11v07", win)
        self.assertEqual(lon.shape, (r1 - r0, c1 - c0))
        self.assertAlmostEqual(lon[0, 0], -70 + (c0 + 0.5) / 240)
        self.assertAlmostEqual(lat[0, 0], 20 - (r0 + 0.5) / 240)
        self.assertTrue(lon[0, 0] <= -66.2 + 1 / 240 and lat[-1, 0] <= 18.3 + 1 / 240)


@unittest.skipIf(np is None, "numpy and shapely are needed")
class Zonal(unittest.TestCase):
    """A 4 x 6 raster of 1-degree pixels from (0, 4) at the north-west corner: outline A holds the centres of the 2 x 2 block at the west, outline B the 2 x 2 block
    next to it, outline C is smaller than a pixel inside column 5 of row 0, the rest is sea."""

    def setUp(self):
        lon, lat = np.meshgrid(np.arange(6) + 0.5, 4 - (np.arange(4) + 0.5))
        self.lon, self.lat = lon, lat
        self.geoms = [box(0, 2, 2, 4), box(2, 2, 4, 4), box(5.1, 3.1, 5.3, 3.3)]
        self.rad = np.array([[1.0, 3.0, 10.0, 20.0, 0.0, 7.0],
                             [5.0, np.nan, 30.0, 40.0, 0.0, 0.0],
                             [9.0, 9.0, 9.0, 9.0, 9.0, 9.0],
                             [9.0, 9.0, 9.0, 9.0, 9.0, 9.0]])
        self.qual = np.array([[0, 1, 0, 2, 0, 1],
                              [0, 255, 0, 0, 0, 0],
                              [0, 0, 0, 0, 0, 0],
                              [0, 0, 0, 0, 0, 0]], dtype=np.uint8)

    def test_owners_by_pixel_centre_and_the_small_outline(self):
        own, extra = nl.owners(self.geoms, self.lon, self.lat)
        self.assertEqual(own[:2, :2].tolist(), [[0, 0], [0, 0]])
        self.assertEqual(own[:2, 2:4].tolist(), [[1, 1], [1, 1]])
        self.assertTrue((own[2:] == -1).all() and (own[:, 4:] == -1).all())   # sea, and C holds no centre
        self.assertEqual(extra, [(2, 0, 5)])   # C takes the pixel under it

    def test_sums_means_and_quality_share(self):
        own, extra = nl.owners(self.geoms, self.lon, self.lat)
        z = nl.zonal(self.rad, self.qual, own, 3, extra)
        self.assertEqual(z[0].tolist(), [9.0, 3, 1, 3])     # 1 + 3 + 5 (the NaN pixel has no value and no quality); one poor of three with a flag
        self.assertEqual(z[1].tolist(), [100.0, 4, 1, 4])   # 10 + 20 + 30 + 40; one gap-filled
        self.assertEqual(z[2].tolist(), [7.0, 1, 1, 1])     # the one pixel under C, poor
        self.assertEqual(nl.pooled(z[0]), (3.0, 33.3))
        self.assertEqual(nl.pooled(z[1]), (25.0, 25.0))
        self.assertEqual(nl.pooled([0, 0, 0, 0]), (None, None))

    def test_pooled_is_not_an_average_of_areas(self):
        own, _ = nl.owners(self.geoms, self.lon, self.lat)
        both = np.where(own >= 0, 0, -1)
        z = nl.zonal(self.rad, self.qual, both, 1)
        self.assertEqual(nl.pooled(z[0])[0], round(109 / 7, 3))   # 15.571, where the mean of the two areas' means would be 14.0
        self.assertNotEqual(nl.pooled(z[0])[0], (3.0 + 25.0) / 2)

    def test_the_sea_and_fill_count_nowhere(self):
        own = np.full(self.rad.shape, -1)
        z = nl.zonal(self.rad, self.qual, own, 2)
        self.assertEqual(z.sum(), 0)


class FakeBarrios:
    """Two municipios of one and two barrios."""
    ids = ["7200100001", "7200300001", "7200300002"]
    mids = ["72001", "72003"]
    names = ["Uno", "Dos"]


@unittest.skipIf(np is None, "numpy is needed")
class Assemble(unittest.TestCase):
    def summaries(self, months):
        S = {}
        for k, m in enumerate(months):
            b = [[10.0 + k, 2, 0, 2], [4.0, 1, 1, 1], [0.0, 0, 0, 0]]
            S[m] = {"month": m, "files": [f"VNP46A3.A{m[:4]}001.h11v07.002.1.h5"], "barrio": b,
                    "municipio": [b[0], [4.0, 1, 1, 1]], "island": [14.0 + k, 3, 1, 3]}
        return S

    def test_complete_years_only_and_pooled_months(self):
        months = [f"2024-{m:02d}" for m in range(1, 13)] + ["2025-01", "2025-02"]
        series, barrio, mon = nl.assemble(FakeBarrios, self.summaries(months))
        self.assertEqual(series["years"], [2024])
        self.assertEqual(series["notes"]["partial_years"], {"2025": 2})
        r = next(v for v in series["vars"] if v["key"] == "ntl_radiance")["years"]["2024"]
        self.assertEqual(len(r), 3)   # two municipios, then Puerto Rico
        self.assertEqual(r[0], round(sum(10.0 + k for k in range(12)) / 24, 3))
        self.assertEqual(r[2], round(sum(14.0 + k for k in range(12)) / 36, 3))
        q = next(v for v in series["vars"] if v["key"] == "ntl_poor_pct")["years"]["2024"]
        self.assertEqual(q, [0.0, 100.0, 33.3])
        self.assertEqual(barrio["vars"][0]["years"]["2024"][2], None)   # a barrio with no pixel value has no value, not zero
        self.assertEqual(mon["months"], months)
        self.assertEqual(len(mon["barrio"]["ntl_radiance"]), 3)
        self.assertEqual(len(mon["barrio"]["ntl_radiance"][0]), len(months))
        self.assertEqual(mon["municipio"]["ntl_radiance"][2][-1], round((14.0 + 13) / 3, 3))

    def test_the_series_has_the_shape_the_engine_reads(self):
        series, barrio, _ = nl.assemble(FakeBarrios, self.summaries([f"2023-{m:02d}" for m in range(1, 13)]))
        self.assertEqual(series["geo"]["ids"], ["72001", "72003", "72"])
        for v in series["vars"]:
            for k in ("key", "group", "label", "unit", "d", "type", "sources", "definition", "years"):
                self.assertIn(k, v)
            self.assertEqual(v["barrioFile"], "nightlights_barrio.json")
            self.assertEqual(set(v["sources"]), set(series["sources"]))
            self.assertIn("proxy", v["definition"])
        self.assertEqual(barrio["level"], "barrio")
        self.assertEqual([v["key"] for v in barrio["vars"]], [v["key"] for v in series["vars"]])
        json.dumps(series, allow_nan=False)


@unittest.skipIf(np is None or h5py is None, "numpy and h5py are needed")
class Reader(unittest.TestCase):
    def write(self, p, raw, attrs, q):
        with h5py.File(p, "w") as f:
            g = f.create_group("HDFEOS/GRIDS/VIIRS_Grid_DNB_2d/Data Fields")
            ds = g.create_dataset(nl.RAD, data=raw)
            for k, v in attrs.items():
                ds.attrs[k] = v
            g.create_dataset(nl.QUAL, data=q)
            g.create_dataset("lat", data=20 - (np.arange(nl.GRID) + 0.5) / 240)
            g.create_dataset("lon", data=-70 + (np.arange(nl.GRID) + 0.5) / 240)

    def test_collection_2_float_layer(self):
        """Collection 2: 32-bit float, fill -999.9, scale 1 (user guide v2.0, table 11), with or without the attributes in the file."""
        q = np.zeros((nl.GRID, nl.GRID), dtype=np.uint8)
        q[360, 913] = 255
        raw = np.zeros((nl.GRID, nl.GRID), dtype=np.float32)
        raw[360, 912] = 12.3
        raw[360, 913] = -999.9
        raw[360, 914] = -0.5   # below the valid range
        for attrs in ({}, {"_FillValue": np.array([-999.9], dtype=np.float32), "scale_factor": np.array([1.0]), "add_offset": np.array([0.0])}):
            with tempfile.TemporaryDirectory() as d:
                p = Path(d) / "VNP46A3.A2024001.h11v07.002.1.h5"
                self.write(p, raw, attrs, q)
                rad, qq = nl.read_tile(p, "h11v07", (360, 362, 912, 915))
                self.assertAlmostEqual(rad[0, 0], 12.3, places=5)
                self.assertTrue(math.isnan(rad[0, 1]) and math.isnan(rad[0, 2]))
                self.assertEqual(rad[1, 0], 0.0)
                self.assertEqual(qq[0, 1], 255)
                with self.assertRaises(SystemExit):
                    nl.read_tile(p, "h10v07", (0, 1, 0, 1))   # the grid of another tile

    def test_a_scaled_integer_layer_uses_the_files_attributes(self):
        raw = np.zeros((nl.GRID, nl.GRID), dtype=np.uint16)
        raw[0, 0], raw[0, 1] = 123, 65535
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "x.h5"
            self.write(p, raw, {"_FillValue": np.array([65535], dtype=np.uint16), "scale_factor": np.array([0.1]), "add_offset": np.array([0.0])}, np.zeros((nl.GRID, nl.GRID), dtype=np.uint8))
            rad, _ = nl.read_tile(p, "h11v07", (0, 1, 0, 2))
        self.assertAlmostEqual(rad[0, 0], 12.3)
        self.assertTrue(math.isnan(rad[0, 1]))


class Login(unittest.TestCase):
    def test_no_token_stops_and_writes_nothing(self):
        env = {k: v for k, v in os.environ.items() if k != nl.TOKEN_VAR}
        with mock.patch.dict(os.environ, env, clear=True), mock.patch.object(nl, "load_barrios") as lb, \
                mock.patch.object(nl, "list_months") as lm, mock.patch.object(Path, "write_text") as wt, mock.patch("builtins.print") as pr:
            self.assertEqual(nl.build(), 0)
        lb.assert_not_called(); lm.assert_not_called(); wt.assert_not_called()
        self.assertIn("EARTHDATA_TOKEN is not set", pr.call_args[0][0])

    def test_a_blank_token_is_no_token(self):
        with mock.patch.dict(os.environ, {nl.TOKEN_VAR: "  "}):
            self.assertIsNone(nl.token())

    @staticmethod
    def resp(code, location=None, ctype=None, body=b""):
        r = mock.Mock(status_code=code, headers={k: v for k, v in (("Location", location), ("content-type", ctype)) if v})
        r.iter_content = lambda n: [body]
        r.raise_for_status = lambda: None
        return r

    LADS = "https://ladsweb.modaps.eosdis.nasa.gov/archive/allData/5200/VNP46A3/2012/001/x.h5"

    def test_the_earthdata_round_trip_carries_the_token_to_nasa_only(self):
        """LAADS -> its licence check -> Earthdata Login -> LAADS's callback -> the file on a download host (where no token goes)."""
        secret = "not-a-real-token-123"
        body = nl.HDF5_MAGIC + b"rest"
        chain = [self.resp(303, "/profiles/licenses/archive/allData/5200/VNP46A3/2012/001/x.h5"),
                 self.resp(302, "https://urs.earthdata.nasa.gov/oauth/authorize?client_id=abc&state=s"),
                 self.resp(302, "https://ladsweb.modaps.eosdis.nasa.gov/oauth/callback?code=c"),
                 self.resp(302, "https://download.example.org/x.h5?sig=1"),
                 self.resp(200, ctype="application/x-hdf5", body=body)]
        s = mock.Mock(); s.get.side_effect = chain
        with tempfile.TemporaryDirectory() as d:
            nl.download(self.LADS, Path(d) / "x.h5", secret, s)
            self.assertEqual((Path(d) / "x.h5").read_bytes(), body)
        calls = s.get.call_args_list
        hosts = [c.args[0].split("/")[2] for c in calls]
        self.assertEqual(hosts, ["ladsweb.modaps.eosdis.nasa.gov", "ladsweb.modaps.eosdis.nasa.gov", "urs.earthdata.nasa.gov", "ladsweb.modaps.eosdis.nasa.gov", "download.example.org"])
        for c, h in zip(calls, hosts):
            self.assertEqual("Authorization" in c.kwargs["headers"], h in nl.NASA_HOSTS, h)   # the token goes to LAADS and Earthdata Login only
            self.assertFalse(c.kwargs["allow_redirects"])
            self.assertNotIn(secret, c.args[0])

    def test_a_sign_in_page_at_the_end_stops_without_showing_the_token(self):
        secret = "not-a-real-token-123"
        chain = [self.resp(303, "/profiles/licenses/archive/x.h5"),
                 self.resp(302, "https://urs.earthdata.nasa.gov/oauth/authorize?client_id=abc&state=secretstate"),
                 self.resp(200, ctype="text/html; charset=utf-8", body=b"<html>Earthdata Login</html>")]
        s = mock.Mock(); s.get.side_effect = chain
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(SystemExit) as cm:
                nl.download(self.LADS, Path(d) / "x.h5", secret, s)
            self.assertFalse((Path(d) / "x.h5").exists())
        msg = str(cm.exception)
        self.assertIn("urs.earthdata.nasa.gov/oauth/authorize", msg)
        self.assertNotIn(secret, msg)
        self.assertNotIn("secretstate", msg)   # no query string is printed

    def test_a_refusal_stops(self):
        s = mock.Mock(); s.get.side_effect = [self.resp(401)]
        with tempfile.TemporaryDirectory() as d, self.assertRaises(SystemExit) as cm:
            nl.download(self.LADS, Path(d) / "x.h5", "t", s)
        self.assertIn("401", str(cm.exception))

    def test_file_names_and_months(self):
        m = nl.FILE_RE.match("VNP46A3.A2024061.h11v07.002.2025161151305.h5")
        self.assertEqual(m.groups(), ("2024", "061", "h11v07"))
        self.assertEqual(nl.month_of(2024, 61), "2024-03")   # a leap year
        self.assertEqual(nl.month_of(2023, 60), "2023-03")
        self.assertIsNone(nl.FILE_RE.match("VNP46A3.A2024061.h11v07.002.2025161151305.h5.xml"))


if __name__ == "__main__":
    unittest.main()
