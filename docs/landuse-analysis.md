# Land use: classes on the map and the analysis (2026-10-16)

The Plan de Uso de Terrenos 2015 of the Junta de Planificación (PUT-2014, adopted 30 November 2015) is a layer of the 2D map (Layers tab, Land use group).

## Classes on the map

Each of the ten classes in the legend has a tick box. All are ticked when the layer opens; unticking a class hides its polygons on the map and in the click pop-up (`app.js`: `LU_KEYS`, `luStyle`, `luShown`). Codes without a colour of their own (SREP-AE, SREP-EP, SREP-EA, SREP-P, SREP-AP) draw and count as "Rústico especialmente protegido" (`landuse.class_key`), as before. The choice is not kept in the map's link.

## The analysis

The button "Land use by municipality and for Puerto Rico", in the same group, opens a panel under the map (`js/landuse_view.js`, loaded the first time it opens; about 3 KB compressed, plus 4.6 KB of data). It replaces the Economy workbench while open, and the workbench replaces it.

- The chosen area (Puerto Rico or a municipality): one bar split by class, and a table with the km² and the share of land of each class.
- The 78 municipalities: one bar each, sorted by the share of a class you choose. Clicking one shows it and moves the map there.
- Ten classes or four groups (urban, for urban growth, ordinary rural, specially protected rural).
- A CSV with the km² and shares of Puerto Rico and every municipality.

## Data

`site/data/landuse_summary.json` (`landuse.class_summary`, written by the full build): km² of each class by municipio and for Puerto Rico, from the `Shape_Area` of the full-resolution polygons. Shares of land leave out water (AGUA) and road rights-of-way (VIAL), as `urban_pct`, `protected_land_pct` and the other fields of `municipalities.json` do; grouped, the classes give back `landuse_km2` (checked by `tests/test_landuse_summary.py`).

Puerto Rico, land in the plan: 8,409.1 km². Urban 14.2%, for urban growth 0.8%, ordinary rural 21.3%, specially protected rural 63.7% (agricultural 27.7%, ecological 21.3%, ecological and water 7.3%, with no sub-class 5.2%, agricultural and water 1.4%, water 0.8%).

## Limits

- A planning classification, not land cover: what the plan allows or protects, not what is on the ground today.
- One plan version (30 November 2015); later amendments and municipal plans are not included.
- Areas are planar, from the plan's projected coordinates, and can differ slightly from the Census land areas (`land_km2`).
