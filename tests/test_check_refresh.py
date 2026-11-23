"""check_refresh.py: the nightly refresh is held when its data look broken."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import check_refresh as C  # noqa: E402


def files(routes=100, trips=1000, ops=40, stops=500, places=50, munis=78, place_fields=("name", "type")):
    d = {
        "transit_routes.geojson": {"features": [{}] * routes},
        "trips.json": {"trips": [0] * trips}, "trips_sa.json": {"trips": [0] * trips}, "trips_su.json": {"trips": [0] * trips},
        "operators.json": {"operators": [{}] * ops}, "transport.json": [{}] * stops, "population_blocks.json": [[0, 0, 1, 0]] * 300,
        "place_access.json": {"ts_m": [0] * places}, "transit_supply.json": {"days": [{}] * 3},
        "places.json": [{f: 1 for f in place_fields}] * places, "municipalities.json": {str(i): {} for i in range(munis)},
    }
    return d.__getitem__


class CheckRefresh(unittest.TestCase):
    def test_the_same_data_passes(self):
        self.assertEqual(C.check(files(), files())[0], [])

    def test_a_small_drop_passes_and_a_large_one_is_held(self):
        self.assertEqual(C.check(files(trips=800), files())[0], [])
        p = C.check(files(trips=700), files())[0]
        self.assertTrue(any("trips.json" in x and "down 30%" in x for x in p), p)

    def test_a_large_drop_allowed_by_hand_is_a_note(self):
        p, notes = C.check(files(trips=700), files(), allow_drop=True)
        self.assertEqual(p, [])
        self.assertTrue(any("allowed by hand" in n for n in notes))

    def test_empty_or_unreadable_files_are_held(self):
        self.assertTrue(any("no records" in x for x in C.check(files(routes=0), files())[0]))
        new = files()
        broken = lambda n: (_ for _ in ()).throw(ValueError("not JSON")) if n == "operators.json" else new(n)
        self.assertTrue(any("operators.json: cannot be read" in x for x in C.check(broken, files())[0]))

    def test_rows_of_files_the_refresh_only_updates_must_not_change(self):
        self.assertTrue(any("municipalities.json" in x for x in C.check(files(munis=77), files())[0]))
        self.assertTrue(any("places.json" in x for x in C.check(files(places=51), files())[0]))

    def test_contact_fields_are_held(self):
        p = C.check(files(place_fields=("name", "phone")), files())[0]
        self.assertTrue(any("contact fields" in x for x in p), p)

    def test_a_file_not_yet_published_is_counted_without_comparison(self):
        old = files()
        self.assertEqual(C.check(files(), lambda n: None if n == "trips_su.json" else old(n))[0], [])

    def test_the_published_data_passes(self):
        problems, _ = C.check(C.from_disk, C.from_disk)
        self.assertEqual(problems, [])


if __name__ == "__main__":
    unittest.main()
