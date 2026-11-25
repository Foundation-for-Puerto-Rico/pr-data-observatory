# Climb on the walk to a transit stop (`climb.py`)

Step 4 of the terrain and climate plan (`docs/terrain-climate-proposal-2026-11.md`, HANDOFF decision 80, approved 2026-11-04). Built on 2026-11-04 on branch `data/walk-climb`.

A flat 400 m and a 400 m up a hill in Barranquitas are not the same walk, especially for older adults and anyone with a stroller or a wheelchair. The observatory already counts the residents who live within a 400 m walk of a stop with a current timetable (`walk_cur`, in the exposure files). This step reads the ground under those walks.

`climb.py` writes two files, shaded on the map's Economy tab in the group "Infrastructure · Climb on the walk to a stop (USGS 3DEP)":

- `climb_series.json`: 3 datasets for the 78 municipios and Puerto Rico.
- `climb_barrio.json`: the same 3 datasets for the 901 barrios.

## The figures (build of 2026-11-04, stops current on 2026-10-29)

| Key | What | Puerto Rico |
|---|---|---|
| `walk_climb_med` | Round-trip climb of the walk to a current stop, median over the residents with a walk (m) | 3.4 |
| `walk_steep_pct` | Residents with a walk whose walk has a stretch steeper than a ramp may be (%) | 13.7 |
| `walk_steep_res` | The same, as residents (estimate) | 55,648 |

- **Who is counted:** the 405,841 residents (4,914 census blocks) within a 400 m walk of a stop with a current timetable, exactly the published `walk_cur` residents. They live in 29 municipios and 155 barrios; the other areas have no value ("No residents within a 400 m walk of a current stop").
- **Most walks are flat:** most of these residents live in the San Juan metro and the coastal towns, where walks climb little (Cataño 0.9 m, Toa Baja 1.5 m).
- **Steep walks:** Orocovis (95.7% of the residents with a walk), Hormigueros (60.2%) and Jayuya (56.5%) have the highest shares; San Juan (12,793) and Guaynabo (11,726) have the most residents with a steep walk.

## How it is made

**The walkers.** Each 2020 census block whose point is within a 400 m walk along mapped roads of a stop with a current timetable, by the rule of `access.py` (the walking rule of the exposure files), on the date of the published exposure files (`as_of`). The build stops if their residents do not add up to the published `walk_cur` residents.

**The walk.** The shortest walk along mapped roads (`roads.bin`, without motorways) from the block's point to its nearest current stop. `walknet.nearest_paths` is the same bounded search as `walknet.from_stops`, keeping each node's parent so the walk can be drawn; a test checks that the length of the drawn walk is the searched distance.
- The climb is read **along the roads only**, from the point of the road nearest the block's point to the point nearest the stop. The block's point is a geometric center, not a door, and the straight line from it to the road can cross ground nobody walks. (The first build included those connectors: the median was 4.4 m and 19.9% of walks were steep. Arroyo's walks showed why: a straight line climbing 23 m over a hill between a block's point and its road.)
- 99 walks whose block or stop is on no walkable road are read along the straight line, as `access.py` measures them.

**The ground.** USGS 3D Elevation Program, 1/3 arc-second seamless DEM (about 10 m; public domain), the newest version of each one-degree tile over Puerto Rico (2026-07-22), read with `raster.py`. The height is read every 10 m along the walk, interpolated between the four nearest cells: 128,339 points.

**Round-trip climb.** The sum of the rises and the falls along the walk: the meters climbed going to the stop and coming back. It is the same whichever way the walk is read.

**Steep stretch.** A 30 m stretch whose rise or fall is more than 1 in 12 (8.33%): the steepest **running slope** a ramp may have under the 2010 ADA Standards for Accessible Design (405.2). A walk with one such stretch counts as steep. It is a reference for what a wheelchair user can be expected to manage, not a rule for streets.

**Areas.** A block counts whole in the barrio the crosswalk gives it (`geo.block_barrios`) and in its municipio; Puerto Rico pools all blocks. The median is weighted by residents.

## What it does not see

- **Bare ground, not structures:** a road on a bridge or an embankment reads the valley or the slope below; a steep stretch can then appear where the road is level.
- **Mapped roads only:** steps, sidewalks, footpaths and shortcuts are not in `roads.bin`.
- **About 10 m:** a short ramp or a few steps are smoothed out.
- **Small numbers:** where few residents live within a walk, one block moves the figure a lot (Arroyo: 72 residents).

## Checks at every build

- The residents with a walk equal the published `walk_cur` residents of Puerto Rico (405,841).
- Puerto Rico's median round-trip climb is between 0 and 30 m (3.4).
- Barranquitas (4.8), Jayuya (11.6) and Orocovis (20.6) climb more than Puerto Rico; Cataño (0.9) and Toa Baja (1.5) less. Aibonito, the first choice, has no current stop within a walk.
- Fewer than 1% of the points along the walks lack a height.

`tests/test_climb.py`: the drawn walk on a small grid of roads (joined from the place to the stop, with the searched length; the nearest stop wins; too far gets none), the climb and grade on made-up heights, the weighted median, the elevation tile of a point, and the published files.

## Refresh

The stops with a current timetable change with the timetables. The nightly transit refresh (`refresh_network.py`, `refresh-transit.yml`) runs `climb.build()` after the exposure files, and writes the two files only when a value changed; the elevation tiles are cached with the transit network (`cache/dem`). A failure there is reported and never stops the transit refresh.

## Spanish names load with the Economy tab

To keep the map under its 250 KB script budget, the Spanish names of the terrain and climate groups (surface heat, vegetation, night heat and this one) are in a module of the map page, `econ_terrain`, loaded with the Economy tab's data instead of with the page (`economy.js`, `ecLoad`; `docs/i18n.md`, rule 15). This freed 0.6 KB on the map.

## License

USGS 3DEP data are public domain; USGS asks for credit. The source card is `usgs_3dep_13`. No elevation image is published, only figures by area.
