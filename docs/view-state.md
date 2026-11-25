# The view state shared by the 2D map and the 3D view

The 2D map (`index.html`) and the 3D view (`3d.html`) write what they show in the address's hash, and their links to each other carry the whole hash. Switching views keeps the place, the extent, the layers, the measure, the Economy layers and their year, the selected municipality, the route and the base map. One file sets the schema for both views: `site/js/core/viewstate.js` (since 2026-10-26, branch `view-state`, HANDOFF decision 63).

Before this change, the 2D→3D link carried only the camera's center and zoom (`c=`), the route (`r=`) and the base map (`bm=`). The 3D view never wrote its own state to the address: MapLibre's `hash: false`, and only the route planner and the base-map switcher wrote `c=`, `r=` and `bm=`.

## 1. What each view has, and what it honors

| State | 2D map | 3D view | Hash key | Shared |
|---|---|---|---|---|
| Selected municipality | its card (`S.selected`, `selectMuni`) | its card (`muniCard`), opened on load | bare first part (`#Ponce&…`) | both ways |
| Camera center and zoom | Leaflet center and zoom | MapLibre center and zoom (one level less for the same scale: its tiles are 512 px) | `c=lat,lng,zoom` (zoom in Leaflet units) | both ways |
| Bearing and pitch | none (flat, north up) | MapLibre bearing and pitch | `b=`, `p=` | 3D only; the 2D map keeps them in the address so a return to 3D finds them |
| Layers | 23 switches (`LAYER_KEYS`) | 28 switches, the 3D scene's two settings among them | `l=` | the 22 layers of both views both ways; one-view layers are kept and not drawn |
| Measure of the municipios | the shading (`#choro`) | the columns (`#lyCols`, `#metric`: the 2D measures but the three "shown" ones, which count what the 2D filters let through, and a few more) | `s=` | both ways |
| Economy layers and their mode | Shaded (`f`, or `b` by barrio) or Symbol (`s`), with ramp, classes and opacity | the columns' "Any dataset" option: a height dataset and a color dataset | `e=` | both ways (section 3) |
| Economy year | the year bar | the columns' Year menu (`#engY`) | `ey=` | both ways |
| Dollars' base year, composite, scenario | yes | none | `eb=`, `ix=`, `sc=` | 2D only; kept by 3D |
| Places view | pins or hexagons | none (points or heat map, not in the address) | `pv=` | 2D only; kept by 3D |
| Route plan | yes | yes | `r=` | both ways (unchanged) |
| Sea level rise | feet, 1 to 10 | NOAA year and scenario | `slr=` | 2D only; kept by 3D. The 3D view's year and scenario are not in the address: they do not convert to one height |
| Base map | `bm=` (decision 62; nine names since decision 102: positron, liberty, bright, dark, fiord, imagery, topo, relief, none) | `bm=` | `bm=` | both ways (unchanged) |
| Region filter (Reference) | the Region menu (`core/regionfilter.js`, decision 113) | the Region menu | `rg=<id>` (an id of `data/geo/regions.json`) | both ways; the regional profile's link `#rg=<id>` without `c=` also opens the 2D Region tab (`docs/regions.md`) |
| Time bar (vehicles' clock, storm years) | none | the time bar | none | not shared |
| A pop-up of a point or area | Leaflet pop-up | MapLibre card | none | not shared; only the municipality's card is a selection |
| One-time requests | `wb=`, `wc=` (open a workbench view or the composite builder, from the 3D chat); `mt=` (open a tool of Tools › Map tools by its `data-mt` code, from a lesson of the Learn page: `app.js` `MT_LINK` and `openToolLink`, only for a code a button of the pane has; `docs/learn.md`) | `ask=` (a question handed over by the 2D chat); `topic=` (open a topic of Explore: a Knowledge Area page's link back, `catalog.js` reads it before the map rewrites the address) | | read once, never written again |

## 2. The schema

`#<municipality>&c=lat,lng,zoom&b=bearing&p=pitch&l=key,key,-key&s=measure&pv=…&r=…&e=…&ey=yyyy&eb=yyyy&ix=…&sc=…&slr=n&bm=name&rg=id`, in that order, then any other key as it came. Every key is optional.

- **The keys the 2D map has always written keep their names and formats.** `e=`, `ix=` and `sc=` stay URI-encoded (`encodeURIComponent`), and the municipality stays the bare first part. Every old link reads as before.
- **`c=`**: latitude and longitude to 4 decimals (about 10 m) and the zoom to 2 decimals, in Leaflet units. The 3D view subtracts one level when it reads (`toMapLibre`) and adds it back when it writes (`fromMapLibre`). This is the ±1 rule both views already used.
- **`l=`**: the layers on, by their key: the 2D map's `LAYER_KEYS` and `core/layers.js`, plus a key for each 3D-only switch: `trips`, `storms`, `suproutes`, `supstops`, and the scene settings `terrain` and `buildings`. `-key` marks a layer that its view turns on by default (the 3D routes, vehicles, terrain and buildings; the municipal boundaries in both) as off.
  - **Reading** (`layerPlan`): a key listed is on and `-key` is off. A layer of both views that the list does not name is off, because the other view would have listed it. A layer of one view only that the list does not name takes its default, because the other view cannot say. So a link from the 2D map leaves the 3D vehicles and terrain on.
  - **Old links:** an address with no `l=` (every 3D link before this change) changes no layer.
- **Kept, not lost.** When a view writes the address, it puts in its own values and keeps everything else as it came (`write`). That covers a key it does not use (`b=` and `p=` on the 2D map, `eb=` or `pv=` in 3D), a layer it does not have, a measure only the other view has, and a key of a later version. ask, wb and wc are dropped.
- **Ignored, not broken.** A value that does not read is ignored when applied: a `c=` that is not three numbers in range, a bearing beyond ±360°, a pitch outside 0–85°, a year that is not four digits, a sea level outside 1–10 feet, a layer token that is not a key, or a measure no view has. A view then writes its own values over it.
- **Own keys only, the first of each, within caps** (review of #97). A value from the address is looked up only among an object's own keys (`has`), so `s=constructor`, `__proto__`, `toString` or `hasOwnProperty` names no measure, no layer and no dataset (the engine's datasets have no prototype either); before, `#s=constructor` threw in the 3D view. The parts are read into an object with no prototype, so `constructor=1` is an unknown key like any other. A key that comes twice counts once, the first, in `viewstate.parse` and in the 2D map's `parseHash`, which now uses it. What a view keeps of keys it does not know is capped (`KEEP`): a value over 200 characters is dropped, the kept unknown part stops at 1,000 characters, and at most 40 layer tokens of the other view are kept.
- **Written encoded.** Every value a view writes is encoded: `e=`, `ix=` and `sc=` whole, as before, and the others wherever a character would end the part or the address (`%`, `&`, `#`, `=`, spaces). A value cannot add a key. The address's own text passes through unchanged (`{ raw }`). The palettes' ramps and the engine's classes are looked up by their own names too, so a token with the ramp "constructor" draws in blue (it threw on the 2D map).
- **A dataset the 3D view does not have.** If `e=` names a dataset the 3D view lacks (the WCRP datasets are by barrio and the columns are by municipio), the columns stay off and `e=` stays as it came.

## 3. The Economy layers and the 3D columns

The 2D map's Economy tab draws up to two Shaded layers and any number of Symbol layers. The 3D columns show one dataset as the height and one as the color. `econColumns` reads `e=` this way:
- **Height:** the first Symbol layer (the size of a symbol is a quantity, like a column's height), or else the first Shaded layer.
- **Color:** the first Shaded layer, when it is another dataset.
- Each takes the rescaling its token names, when the dataset offers it.

`econOf` writes them back:
- the color as a Shaded layer and the height as a Symbol layer;
- or one Shaded layer when the color is the height.

Tokens that still say the same thing are kept whole, with their ramp, classes, opacity and color. A round trip that changes nothing gives back the 2D map's `e=` unchanged.

The 3D view writes `s=`, `e=` and `ey=` only once its columns have been changed in this view (`VS.measure`). Until then, the three stay as the address had them.
- **A measure picked in 3D:** writes `s=` and takes `e=` and `ey=` out. The 2D map draws its Economy layers over the shading, so keeping them would hide the measure picked.
- **The Economy columns:** write `e=` and `ey=` and take `s=` out: the columns show one measure, and an `s=` kept beside them would be a measure the view no longer shows (a "Turn all off" and its Undo then gave a different address, `tests/browser/active_layers.js`). A 2D measure the columns do not have (the three "shown" ones) stays.
- **Columns turned off:** takes out `s=`, `e=` and `ey=`.
- **Undo of "Turn all off"** (the chip, `core/activelayers.js`) puts `s=`, `e=` and `ey=` back exactly as they were, with the tokens the columns do not draw (a third Economy layer, ramps, classes), and whether they had been changed here (`measureSnap`, `measureRestore`). Switching the columns back on alone rebuilt `e=` from what the view draws (review of #97). The snapshot keeps the raw text of the three keys, never decoded, and puts it back as it was (second review of #97: a broken `%` threw, and a decoded `%26` added keys to the address and the 2D link).

`eb=`, `ix=` and `sc=` are always kept.

## 4. Writing the address

- **2D map:** as before, after each change (250 ms debounce, `writeHash`), with `history.replaceState`. Its 3D link is `3d.html` plus the hash.
- **3D view:**
  - **When it starts writing:** only once the view has applied the address it opened on (`applyState`, run just after `ready`; nothing is written before, so a slow start cannot write its defaults over the link).
  - **What it writes:** its camera (`c=`, `b=`, `p=`), its layers, the columns once changed here, the route, the base map and the municipality whose card is open (`writeState`).
  - **When it writes:** on `moveend`, on any change in the side panel, and when a card opens or closes.
  - **How:** `history.replaceState`, at most every 400 ms (a burst of moves writes once at the end), never a new history entry, so Back still leaves the page.
  - **Links:** the 2D link is `index.html` plus the hash. The "Open in 2D analysis" link of a municipality's card carries the same state with that municipality selected and no `c=`, so the 2D map flies to it. The card's link is rebuilt with the address while the card is open, and again on the click (review of #97: it kept the state of the moment the card opened). When the 3D view cannot start (no WebGL, or its libraries did not load), its 2D link still carries the address. Every link to the other view keeps the page's `?lang=`, as the chat's links do. After an old `r=` link, the planned route's fit moves the camera, and the address takes the camera where the fit ends.
  - **Other writers:** the route planner and the base-map switcher go through the same writer. The chat's `ask=` hand-over (`chat.js` `chHandIn`, on every page) takes `ask=` out and leaves the other parts as they came (before, `URLSearchParams` turned a bare `#Ponce` into `Ponce=`).
- **Not done:** the 3D view does not listen for `hashchange` (a pasted address needs a reload); the 2D map does, as before.

## 5. Tests

- `tests/viewstate.test.js` (Node; run by CI with `node --test tests/*.test.js`) covers:
  - parse and write round trips;
  - old 2D and 3D links, written back unchanged;
  - bogus values, unknown keys and one-time requests;
  - the layer tokens and plan in both directions, the 3D vehicles left on after a 2D link;
  - the layer keys against `app.js LAYER_KEYS`, `core/layers.js` and `3d.html`;
  - the Economy↔columns mapping and its round trip;
  - the zoom rule;
  - the wiring of both pages.
- `tests/browser/view_state.js` (headless Chrome; `tests/browser/README.md`) runs 2D → 3D → 2D, then old and bogus links, in es and en at 1400 px and in en at 390 px:
  1. **2D:** Ponce, flood zones and routes, the shading, two Economy layers and a year are set.
  2. **3D:** opened from the 2D link, the camera, layers, columns, year and card are checked. Then layers, camera and the columns' height change; the address follows with no new history entry.
  3. **2D:** back from the 3D link, everything is checked again, with the 3D-only parts still in the address.
  4. **Old and bogus links** open on the defaults or ignore what does not read.

  On 2026-10-26: 62 checks pass in es and en at 1400 px, and 31 in en at 390 px. After the review of #97 (2026-10-27) it also checks names of Object.prototype as the municipality, s=, e= and layer keys on both views, the open card's 2D link after changes, and Undo of "Turn all off" on a link with three Economy layers (with and without a change of year): 132 checks in es and en at 1400 px.

## Not in the address: the OpenStreetMap inspector (2026-10-27, branch `osm-inspector`)
The inspect mode of the base map (`docs/basemap.md`, section 8) is not written to the hash and no key reads it. It is a short-lived way of using the map, and a shared link that opened in it would take the recipient's clicks away from the data layers without their knowing. The base map it needs (`bm=`) travels as before.
