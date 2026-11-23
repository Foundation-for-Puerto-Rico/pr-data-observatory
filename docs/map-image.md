# Save the map as an image

Plan: `docs/map-tools-proposal-2026-11.md`, step 3 (HANDOFF decision 97). Code: `site/js/core/mapimage.js` (scale bar, file name, legend swatches and columns; tested in Node by `tests/mapimage.test.js`) and `site/js/mapimage.js` (draws and saves the image). Spanish: `i18n_src/es/mapimage.json` (module `mapimage` of the map page).

## What a visitor gets

**Tools › Map tools › Share and download › Save the map as an image** saves a PNG named `pr-data-observatory-map-YYYY-MM-DD.png`: the map as it is on screen, at up to twice the screen's resolution, and under it

- a title: the legends' titles (up to three), or the switched-on layers when nothing is shaded;
- the legends on screen: the Analysis layers' legend and each switched-on layer's legend, colour ramps (slope, heat) included, with the "Show only above" threshold when one is set; up to 12 rows each, and a line that says how many rows or legends did not fit;
- a scale bar at the map's centre latitude (1, 2 or 5 × 10ⁿ m);
- the sources: the map's own credit line;
- "PR Data Observatory · Foundation for Puerto Rico", the date and the address of the view, which reopens it.

Everything is drawn in the browser; nothing is sent anywhere.

## How the map is drawn

The map is a stack, and the image draws it in the same order (by the z-index of each element's pane):

| Part | How |
|---|---|
| Base map | MapLibre's canvas. `core/basemap.js` creates it with `preserveDrawingBuffer: true`; without it the canvas reads as blank (a test checks the flag). |
| Vector layers | Leaflet canvases (the map uses `preferCanvas`), one per pane. |
| Surfaces (heat, slope, night lights) | Their `<img>` overlays. All are served by this site, so the image is not "tainted" and can be saved. An image from another site that refuses to be read is left out, not the whole map. |
| Markers (place clusters, stops) | Drawn as boxes from their computed style: background, border, round corners and their number. |
| Pop-ups, tooltips, the map's buttons | Left out. |

When the base map provider does not answer, the map has no base map and the image has a white background, as the screen does.

## Notes

- A layer that is still loading is not in the image yet: wait until the map has finished drawing.
- `StudyAreas`, `Measure` and `MapImage` are top-level `const`s, not properties of `window`.
- In the desktop app's hidden browser pane, screenshots of the page are not faithful; the checks for this PR read the image's own pixels and saved a downscaled copy to look at.
