"""transport_inventories.py: bridges and tunnels, airports and heliports, ferry routes and EV charging stations as map layers (HANDOFF decision 105, step 4).
The rules are tested on made-up rows; the published files are checked for their notes, for what they must never hold, and, where the downloads are cached,
against a rebuild."""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import transport_inventories as ti   # noqa: E402

DATA = ROOT / "site" / "data"


class FakeMunis:
    name_of = {"72127": "San Juan"}

    def at(self, lon, lat, tol_km=2.0):
        return "72127" if lon is not None and lat is not None and -67.5 < lon < -65 and 17.8 < lat < 18.6 else None


class Rules(unittest.TestCase):
    def test_nbi_degrees_minutes_seconds(self):
        self.assertAlmostEqual(ti.dms("18210507", 2), 18 + 21 / 60 + 5.07 / 3600, places=9)
        self.assertAlmostEqual(ti.dms("066052961", 3), 66 + 5 / 60 + 29.61 / 3600, places=9)
        self.assertIsNone(ti.dms("18999999", 2), "minutes over 59")
        self.assertIsNone(ti.dms("", 2))

    def test_names_and_owners(self):
        self.assertEqual(ti.tidy("FRAILES CREEK"), "Frailes Creek")
        self.assertEqual(ti.tidy("PR 873 0.7 KM"), "PR 873 0.7 KM")
        self.assertEqual(ti.tidy("ISABEL II FERRY TERMINAL"), "Isabel II Ferry Terminal")
        self.assertEqual(ti.tidy("CATANO FERRY TERMINAL"), "Cataño Ferry Terminal")
        self.assertEqual([ti.owner(c) for c in ("01", "31", "4", "62", "26")], ["state", "toll", "municipal", "federal", "other"])

    def test_a_private_facility_owned_privately_is_counted_not_drawn(self):
        rows = [{"ARPT_STATUS": "O", "SITE_TYPE_CODE": "H", "FACILITY_USE_CODE": "PR", "OWNERSHIP_TYPE_CODE": "PR", "ARPT_ID": "PR06", "ARPT_NAME": "HILL", "LONG_DECIMAL": -66.1, "LAT_DECIMAL": 18.4, "EFF_DATE": "2026/10/29"},
                {"ARPT_STATUS": "O", "SITE_TYPE_CODE": "H", "FACILITY_USE_CODE": "PR", "OWNERSHIP_TYPE_CODE": "PU", "ARPT_ID": "PR33", "ARPT_NAME": "BAYAMON RGNL HOSPITAL", "LONG_DECIMAL": -66.15, "LAT_DECIMAL": 18.39, "EFF_DATE": "2026/10/29"},
                {"ARPT_STATUS": "O", "SITE_TYPE_CODE": "A", "FACILITY_USE_CODE": "PU", "OWNERSHIP_TYPE_CODE": "PU", "ARPT_ID": "SJU", "ARPT_NAME": "LUIS MUNOZ MARIN INTL", "FAR_139_TYPE_CODE": "I D", "LONG_DECIMAL": -66.0, "LAT_DECIMAL": 18.44, "EFF_DATE": "2026/10/29"},
                {"ARPT_STATUS": "CI", "SITE_TYPE_CODE": "A", "FACILITY_USE_CODE": "PU", "OWNERSHIP_TYPE_CODE": "PU", "ARPT_ID": "OLD", "ARPT_NAME": "CLOSED", "LONG_DECIMAL": -66.0, "LAT_DECIMAL": 18.4}]
        feats, notes, eff, _ = ti.airports({"rows": rows, "fetched": "2026-11-14"}, FakeMunis())
        self.assertEqual([f["properties"]["faa"] for f in feats], ["SJU", "PR33"])
        self.assertEqual(feats[0]["properties"]["cat"], "commercial")
        self.assertEqual((notes["private_not_drawn"], notes["private_by_kind"]), (1, {"Heliport": 1}))
        self.assertNotIn("HILL", json.dumps(feats) + json.dumps(notes))
        self.assertEqual(eff, "2026-10-29")

    def test_a_ferry_crossing_adds_both_directions_and_needs_a_line(self):
        line = {"type": "LineString", "coordinates": [[-66.1166, 18.4440], [-66.1150, 18.4500], [-66.1131, 18.4628]]}
        d = {"fetched": "2026-11-14", "census": 2024,
             "terminals": [{"terminal_id": "447", "terminal_name": "CATANO FERRY TERMINAL"}, {"terminal_id": "452", "terminal_name": "OLD SAN JUAN PIER TWO"}, {"terminal_id": "448", "terminal_name": "CULEBRA"}],
             "segments": [{"segment_id": "1", "seg_terminal1_id": "447", "seg_terminal2_id": "452"}, {"segment_id": "2", "seg_terminal1_id": "452", "seg_terminal2_id": "447"},
                          {"segment_id": "3", "seg_terminal1_id": "448", "seg_terminal2_id": "447"}],
             "operations": [{"segment_id": "1", "passengers": "100", "vehicles": "0", "trips_per_year": "10", "average_trip_time": "12"},
                            {"segment_id": "2", "passengers": "50", "vehicles": "0", "trips_per_year": "10", "average_trip_time": "14"},
                            {"segment_id": "3", "passengers": "7", "vehicles": "0", "trips_per_year": "1", "average_trip_time": "90"}],
             "lines": {"features": [{"properties": {"seg_terminal1_id": "447", "seg_terminal2_id": "452"}, "geometry": line}]}}
        feats, notes, year, _ = ti.ferries(d)
        self.assertEqual(len(feats), 1)
        p = feats[0]["properties"]
        self.assertEqual((p["pax"], p["trips"], p["min"]), (150, 20, 13))
        self.assertEqual(notes["not_drawn"], [{"pair": "Cataño Ferry Terminal – Culebra", "passengers": 7}])
        self.assertEqual(year, "2024")

    def test_only_public_stations_open_or_temporarily_unavailable(self):
        base = {"latitude": 18.4, "longitude": -66.1, "station_name": "A", "ev_network": "X", "ev_level2_evse_num": 2, "ev_connector_types": "J1772", "updated_at": 1794637195000}
        rows = [{**base, "id": 1, "access_code": "public", "status_code": "E"}, {**base, "id": 2, "access_code": "private", "status_code": "E"},
                {**base, "id": 3, "access_code": "public", "status_code": "P"}, {**base, "id": 4, "access_code": "public", "status_code": "T", "ev_dc_fast_num": 1}]
        feats, notes, _, _ = ti.ev({"rows": rows, "fetched": "2026-11-14"}, FakeMunis())
        self.assertEqual(sorted(f["properties"]["afdc"] for f in feats), [1, 4])
        self.assertEqual((notes["dc_fast_stations"], notes["unavailable"], notes["ports"]), (1, 1, 5))


class Published(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.f = {k: json.loads((DATA / name).read_text(encoding="utf-8")) for k, (name, _) in ti.LAYERS.items()}

    def test_bridges_add_up_to_their_notes(self):
        b = self.f["bridges"]
        n = b["notes"]
        p = [f["properties"] for f in b["features"] if f["properties"]["type"] == "Bridge"]
        self.assertEqual(len(p), n["bridges"])
        self.assertEqual(sum(1 for f in b["features"] if f["properties"]["type"] == "Tunnel"), n["tunnels"])
        self.assertEqual((n["good"], n["fair"], n["poor"]), tuple(sum(1 for x in p if x.get("c") == c) for c in "GFP"))
        self.assertGreaterEqual(n["bridges"] + len(n["left_out"]), ti.FLOORS["bridges"])
        self.assertTrue(all(x.get("c") in ("G", "F", "P") and x.get("o") in ("A", "P", "B", "E", "D", "K") for x in p))

    def test_no_private_facility_owned_privately_is_drawn(self):
        a = self.f["airports"]
        self.assertTrue(all(not (f["properties"]["use"] == "private" and f["properties"]["own"] == "private") for f in a["features"]))
        self.assertLessEqual(len(a["features"]) + a["notes"]["private_not_drawn"], a["notes"]["in_faa_file"])   # closed facilities are neither

    def test_ev_stations_keep_no_phone_or_address(self):
        text = json.dumps(self.f["ev"]).lower()
        for word in ("phone", "street_address", "zip"):
            self.assertNotIn(word, text)

    def test_ferry_lines_follow_the_crossing(self):
        for f in self.f["ferry"]["features"]:
            self.assertGreater(len(f["geometry"]["coordinates"]), 2, f["properties"]["name"])

    def test_the_files_are_what_the_cache_gives(self):
        if not (ti.CACHE / "nbi.pr.json").exists():
            self.skipTest("the downloads are not cached here (cache/inventories/)")
        self.assertEqual(ti.build(check=True), 0)


if __name__ == "__main__":
    unittest.main()
