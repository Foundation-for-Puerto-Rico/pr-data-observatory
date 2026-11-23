"""Every published route line is simplified to about 3 m (network.simplify_line), so transit_routes.geojson stays inside its 1 MB budget (2026-11-18)."""
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import contract  # noqa: E402
import network  # noqa: E402

DATA = Path(__file__).resolve().parent.parent / "site" / "data"


class SimplifyLine(unittest.TestCase):
    def test_points_on_a_straight_line_go_and_corners_stay(self):
        line = [(-66.0, 18.0), (-66.0005, 18.0000001), (-66.001, 18.0), (-66.001, 18.001)]
        self.assertEqual(network.simplify_line(line), [[-66.0, 18.0], [-66.001, 18.0], [-66.001, 18.001]])

    def test_short_lines_are_only_rounded(self):
        self.assertEqual(network.simplify_line([(-66.1234567, 18.7654321), (-66.2, 18.3)]), [[-66.12346, 18.76543], [-66.2, 18.3]])

    def test_the_published_file_has_room_in_its_budget(self):
        size = (DATA / "transit_routes.geojson").stat().st_size
        self.assertLess(size, 0.8 * contract.TIERS["small"], "transit_routes.geojson is close to its 1 MB budget; the nightly refresh will fail when it passes it")
        routes = json.loads((DATA / "transit_routes.geojson").read_text(encoding="utf-8"))["features"]
        self.assertGreater(len(routes), 100)


if __name__ == "__main__":
    unittest.main()
