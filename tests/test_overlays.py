"""Boxes over the map (2026-11-11): the time bar folds, status boxes are see-through at rest and solid in use, and Clean view hides the boxes but keeps
the scale and the map credits (their licenses ask for them). Static checks of site/3d.html, site/index.html, the CSS and the scripts."""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site"
read = lambda p: (SITE / p).read_text(encoding="utf-8")


def rules(css):
    """{selector text: declarations} for each plain rule (media blocks flattened)."""
    out = {}
    for sel, body in re.findall(r"([^{}]+)\{([^{}]*)\}", css):
        out[" ".join(sel.split())] = body
    return out


class Overlays(unittest.TestCase):
    def test_time_bar_folds(self):
        html = read("3d.html")
        bar = re.search(r'<div class="timebar" id="timebar".*?\n</div>', html, re.S).group(0)
        self.assertRegex(bar, r'<button type="button" class="icon-btn tb-fold" id="tbFold" aria-expanded="true" aria-label="Fold the time bar"')
        js = read("js/twin3d.js")
        self.assertIn("function tbFoldApply()", js)
        self.assertRegex(js, r"\['#lyTrips', '#lySlr', '#lyStorms'\]", "it folds by itself while nothing moves in time")
        self.assertIn("sessionStorage.setItem('tbFold'", js, "the visitor's choice is kept for the visit")
        css = read("css/twin3d.css")
        self.assertRegex(css, r"\.timebar\.folded input\[type=range\], \.timebar\.folded \.tb-modes \{ display: none; \}")
        self.assertIn("background: rgba(255,255,255,.85)", re.search(r"\.timebar \{ position: fixed;[^}]*\}", css).group(0), "see-through at rest")
        self.assertRegex(css, r"\.timebar:hover, \.timebar:focus-within \{ background: rgba\(255,255,255,\.9\d\); \}", "solid while used")
        for word in ("keyboard_arrow_down", "keyboard_arrow_up"):
            self.assertIn(word, re.search(r"icon_names=([a-z0-9_,]+)", html).group(1).split(","), word)

    def test_clean_view_on_both_maps(self):
        for page, script in (("index.html", "js/app.js"), ("3d.html", "js/twin3d.js")):
            html = read(page)
            srcs = [m.split("?")[0] for m in re.findall(r'<script src="([^"]+)"', html)]
            self.assertIn("js/core/cleanview.js", srcs, page)
            self.assertLess(srcs.index("js/core/cleanview.js"), srcs.index(script), f"{page}: Clean view loads before the map script that mounts its button")
            self.assertIn("CleanView.button()", read(script), script)
            icons = re.search(r"icon_names=([a-z0-9_,]+)", html).group(1).split(",")
            for word in ("visibility", "visibility_off"):
                self.assertIn(word, icons, f"{page}: {word}")
        cv = read("js/core/cleanview.js")
        self.assertIn("e.key === 'v' || e.key === 'V'", cv)
        self.assertIn("e.key === 'Escape'", cv)
        self.assertIn("aria-pressed", cv)

    def test_clean_view_keeps_scale_and_credits(self):
        css = read("css/twin.css")
        hide = [sel for sel, body in rules(css).items() if "body.clean-view" in sel and "display: none" in body]
        self.assertTrue(hide, "Clean view hides something")
        hidden = " ".join(hide)
        self.assertIn(".leaflet-control:not(.leaflet-control-scale):not(.leaflet-control-attribution)", hidden, "every 2D control hides but the scale and credits")
        self.assertIn(".maplibregl-ctrl:not(.maplibregl-ctrl-scale):not(.maplibregl-ctrl-attrib)", hidden, "every 3D control hides but the scale and credits")
        for gone in (".timebar", ".al", ".map-legend", ".series", ".map-toast"):
            self.assertIn(gone, hidden, gone)
        self.assertNotRegex(hidden.replace(":not(.leaflet-control-scale)", "").replace(":not(.leaflet-control-attribution)", "").replace(":not(.maplibregl-ctrl-scale)", "").replace(":not(.maplibregl-ctrl-attrib)", ""), r"scale|attrib", "the scale and credits are never hidden")

    def test_status_boxes_see_through_panels_solid(self):
        css = read("css/twin.css")
        self.assertIn(".map-legend { background: rgba(255,255,255,.86);", css)
        self.assertRegex(css, r"\.map-legend:hover, \.map-legend:focus-within \{ background: rgba\(255,255,255,\.9\d\); \}")
        self.assertRegex(css, r"\.al-panel \{[^}]*background: (#fff|var\(--color-surface\));", "the On the map panel (read) stays solid: white, or the surface token that is white in the light theme and charcoal in the dark one (css/ws.css)")
        self.assertNotIn("backdrop-filter", css + read("css/twin3d.css"), "no frosted glass (FPR brand)")


if __name__ == "__main__":
    unittest.main()
