"""Tests for the per-stop service counts that network.parse_gtfs writes (weekday, Saturday and Sunday calls) and the feed end date build_network adds.

  python -m unittest discover -s tests -v

A tiny invented GTFS feed is built in memory. The tests need shapely (network.py imports it): they are skipped where it is not installed (the repository's venv has it).
"""
import io
import sys
import unittest
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
try:
    import network  # noqa: E402
except ImportError:   # shapely or requests missing: the full pipeline is not installed here
    network = None


def feed(calendar, trips, stop_times):
    """A GTFS zip with two stops in Puerto Rico. `calendar` rows: (service_id, mon..sun flags as a 7-char string), `trips`: (trip_id, service_id), `stop_times`: (trip_id, stop_id, seq, time)."""
    files = {
        "agency.txt": "agency_id,agency_name,agency_url,agency_timezone\nx,Test Agency,https://example.org,America/Puerto_Rico\n",
        "routes.txt": "route_id,route_short_name,route_type\nR1,1,3\n",
        "stops.txt": "stop_id,stop_name,stop_lat,stop_lon\nS1,First,18.40000,-66.10000\nS2,Second,18.41000,-66.11000\n",
        "calendar.txt": "service_id,monday,tuesday,wednesday,thursday,friday,saturday,sunday,start_date,end_date\n"
                        + "".join(f"{sid},{','.join(flags)},20260101,20271231\n" for sid, flags in calendar),
        "trips.txt": "route_id,service_id,trip_id\n" + "".join(f"R1,{sid},{tid}\n" for tid, sid in trips),
        "stop_times.txt": "trip_id,arrival_time,departure_time,stop_id,stop_sequence\n" + "".join(f"{tid},{t},{t},{sid},{n}\n" for tid, sid, n, t in stop_times),
    }
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for name, text in files.items():
            z.writestr(name, text)
    return buf.getvalue()


@unittest.skipIf(network is None, "shapely is not installed here")
class StopService(unittest.TestCase):
    def setUp(self):
        weekday, saturday, sunday = "11111" + "00", "00000" + "10", "00000" + "01"
        raw = feed(calendar=[("WK", list(weekday)), ("SA", list(saturday)), ("SU", list(sunday))],
                   trips=[("T1", "WK"), ("T2", "WK"), ("T3", "SA"), ("T4", "SU"), ("T5", "SA")],
                   stop_times=[("T1", "S1", 1, "06:00:00"), ("T1", "S2", 2, "06:10:00"), ("T2", "S1", 1, "07:00:00"),
                               ("T3", "S1", 1, "08:00:00"), ("T3", "S2", 2, "08:10:00"), ("T5", "S1", 1, "09:00:00"), ("T4", "S1", 1, "10:00:00")])
        self.stops, _, _, self.meta = network.parse_gtfs(raw, "test", "Test")
        self.by = {s["id"].split(":")[-1]: s for s in self.stops}

    def test_weekday_saturday_and_sunday_calls_per_stop(self):
        s1, s2 = self.by["S1"], self.by["S2"]
        self.assertEqual((s1["trips_weekday"], s1.get("calls_sat"), s1.get("calls_sun")), (2, 2, 1))
        self.assertEqual((s2["trips_weekday"], s2.get("calls_sat")), (1, 1))

    def test_a_day_with_no_service_leaves_the_field_out(self):
        self.assertNotIn("calls_sun", self.by["S2"])   # missing means no Sunday service in the feed, not zero measured

    def test_the_feed_dates_come_with_the_meta(self):
        self.assertEqual((self.meta["start"], self.meta["end"]), ("2026-01-01", "2027-12-31"))
        self.assertTrue(self.meta["weekend_service"])

    def test_a_feed_with_weekday_service_only(self):
        raw = feed(calendar=[("WK", list("1111100"))], trips=[("T1", "WK")], stop_times=[("T1", "S1", 1, "06:00:00"), ("T1", "S2", 2, "06:10:00")])
        stops, _, _, meta = network.parse_gtfs(raw, "test", "Test")
        self.assertTrue(all("calls_sat" not in s and "calls_sun" not in s for s in stops))
        self.assertFalse(meta["weekend_service"])

    def test_a_trip_on_several_days_replays_on_each(self):
        import trip_paths
        raw = feed(calendar=[("WS", list("1111110"))], trips=[("T1", "WS")], stop_times=[("T1", "S1", 1, "06:00:00"), ("T1", "S2", 2, "06:10:00")])
        _, routes, trips, _ = network.parse_gtfs(raw, "test", "Test")
        self.assertIsNot(trips["wk"][0], trips["sa"][0])   # follow_routes rewrites each day's trips in place
        paths = trip_paths.follow_routes(routes, trips)
        self.assertEqual((len(paths["wk"]["paths"]), len(paths["sa"]["paths"])), (1, 1))
        self.assertEqual(trips["sa"][0]["t"], [21600, 22200])


if __name__ == "__main__":
    unittest.main()
