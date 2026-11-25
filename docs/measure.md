# Measure distance and area, and Draw an area

Plan: `docs/map-tools-proposal-2026-11.md`, step 2 (HANDOFF decision 97). Code: `site/js/core/measure.js` (the numbers, tested in Node by `tests/measure.test.js`), `site/js/measure.js` (the box on the map), `StudyAreas.addDrawn` in `site/js/studyareas.js` (a drawn area joins Study areas). Spanish: `i18n_src/es/measure.json` (module `measure` of the map page).

## What a visitor does

- **Tools › Map tools › Measure distance and area** opens a box at the top left of the map, on Distance. **Draw an area** opens the same box on Area.
- Click the map to add points. Double-click, or press **Finish**, to end. **Undo the last point** and **Clear** do what they say; **Esc** clears, and a second Esc closes the box.
- **Distance:** the length of the path, in meters or kilometers and in miles. Lines are straight between the points (straight-line distance), not along the roads; for a walk along the roads, use Walking time.
- **Area:** the area the points outline, in m² or km², hectares, cuerdas and acres, and its perimeter. When two edges cross, the box says so and offers no area to add.
- **Add as a study area:** a finished area that does not cross itself goes into the set "Drawn areas" of Study areas, named by its size, and Study areas opens with its summary (residents, transit and, on request, flood zones, heat, greenness, landslides and slope). It is kept in this browser like any study area; nothing is uploaded.
- On a phone the side panel closes so the map shows. Double-tap does not zoom while the box is open; press Finish to end.

## The numbers

| Measure | How | Check |
|---|---|---|
| Distance, perimeter | Haversine formula on a sphere of the Earth's mean radius (6,371.0088 km, IUGG) | Within about 0.3% of the distance on the ellipsoid; `tests/measure.test.js` compares it with an independent haversine |
| Area | The flat projection `Core.study.areaKm2` uses (111.32 km per degree of longitude times the cosine of the mid latitude; 110.574 km per degree of latitude) | The same size Study areas gives the drawn area (test); a 1 km square measures 1 km² within 0.1% |
| Cuerda | 3,930.395625 m², Ley de Pesas y Medidas del Estado Libre Asociado de Puerto Rico (Ley Núm. 145 de 27 de junio de 1968, según enmendada), sección 3 (23 L.P.R.A. § 903), checked 2026-11-11 in the OGP text (rev. 15 de abril de 2024) | Glossary term `cuerda` gives the same value (test) |
| Acre | 4,046.8564224 m² (international acre) | |

## Notes

- The clicks are caught on the map's box before any layer gets them (capture phase), so a click does not also select a municipio or open a pop-up. The map's own controls still work, and a click that ends a drag is left to the map.
- The readout updates at once; the drawing waits for the next animation frame. A browser that runs no frames (a hidden tab) still shows the numbers.
- `StudyAreas` is a top-level `const` of `js/studyareas.js`, not a property of `window`: code outside the view tests `typeof StudyAreas`.
- Size: `js/maptools.js` loads `core/measure.js` and `measure.js` the first time either tool is used; the map's first load does not change.
