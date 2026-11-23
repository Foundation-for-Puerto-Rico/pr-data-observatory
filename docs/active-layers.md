# The "layers on" chip (2026-10-19)

A chip at the top of the map says how many data layers are on, on the 2D map and on the 3D view. Pressing it lists them, each with a button that turns it off, and a "Turn all off" button. Turning layers off shows the map's message with **Undo**.

- **Code:** `site/js/core/activelayers.js`, shared by both pages. Each page builds an adapter from its parts and mounts it on its map: `app.js` (2D) and `twin3d.js` (3D), right after the Layers tab's groups are made.
- **Styles:** `site/css/twin.css`, at the end ("layers on" chip).
- **Spanish:** `i18n_src/es/activelayers.json`, a scope of the map and the 3D view.
- **Tests:** `tests/activelayers.test.js` (Node, in `node --test tests/*.test.js`) and `tests/browser/active_layers.js` (Chrome, by hand).

## Words

| | English | Spanish |
|---|---|---|
| Chip | {n} layer on / {n} layers on | {n} capa activa / {n} capas activas |
| List label | Layers on the map | Capas en el mapa |
| Each layer's button | Turn off {name} | Apagar {name} |
| Button under the list | Turn all off | Apagar todas |
| Message | {n} layer turned off / {n} layers turned off · Undo | Se apagó {n} capa / Se apagaron {n} capas · Deshacer |
| Note when the route plan is listed | Turn all off keeps the planned route; use its × to remove it. | La ruta planificada se queda al apagar todas; use su × para quitarla. |
| An Economy layer hidden with its eye | (hidden) | (oculta) |
| The walk radius around stops | Walk rings | Anillos de caminata |

The chip uses the same words as the count of a closed group in the Layers tab. On a phone (below 520 px) it shows the icon and the number only, and keeps the words for screen readers.

## What counts

There is one list (`adapter.list()`). The chip's number is its length, so the number and the list always agree.

**2D map**
- Every ticked switch of the layer menus: the ones the link keeps (`LAYER_KEYS` in `app.js`). That covers places, flood zones, sea level rise, routes, stops, stations, taxi stands and EV charging, protected areas, land use, Comunidades Especiales, WCRP communities, barrios, the public facility layers, and the Transit tab's vehicles, residents far from service and integration points.
- The walk rings ("Walk rings" in the list), only while they are drawn: the switch is ticked, the map is at zoom 14 or closer, and stops or stations are on. The chip follows the zoom. A ticked switch whose rings are not drawn is not counted, but "Turn all off" unticks it too, so the rings do not come back when stops come back on or the map zooms in.
- The municipality shading (`#choro`), when it is not "none".
- Each layer of the Economy tab, shaded or symbols. A composite index or a scenario's model output shows on the map as one of these layers, so each counts once, as that layer. A layer hidden with its eye stays counted, because it is still in the tab's stack, and the list marks it "(hidden)".
- The route plan, while it has a point on the map.

**Not counted on the 2D map:**
- Límites, the municipality boundaries. It is the reference layer and stays on.
- The base map.
- Filters such as the place categories, the confidence slider and the land-use classes. They change a layer; they are not layers.

**3D view**
- Every data layer switch: barrios, flood hazard areas, sea level rise, protected areas, land use, public housing, transit routes, stops, stations, taxi stands and EV charging, scheduled vehicles, the five service layers (fire and EMS stations, police stations, city halls, public libraries, historic places), Comunidades Especiales, WCRP communities, tourism places, storm tracks, the Time tab's routes and stops by service in the hour, and the Route tab's residents far from service and integration points (since 2026-10-19, `docs/layers.md`).
- The walk rings ("Walk rings"), only while they are drawn, with the same rules as on the 2D map.
- The municipality columns (`#lyCols`), named by the measure they show.
- The route plan, as on the 2D map.

**Not counted on the 3D view:** Límites, the municipal lines (since 2026-10-19 a switch, on when the view opens, as on the 2D map); the 3D scene group (3D terrain and 3D buildings), the time bar and the camera. These are settings of the view, not data. "Turn all off" leaves them as they are, and since 2026-10-19 the group's own count leaves them out too (their rows have class `nocount`, like Límites on the 2D map).

**Order of the list:** since 2026-10-19 the list follows the layer menu (`js/core/layers.js`, `docs/layers.md`): a row whose switch or menu is on the page comes where it stands there, then the Economy tab's layers and the route plan. Each row's group is the menu group's title.

## Turn all off, and Undo

Each layer goes off through its own path:
- A switch is unticked and its change event fired. "Turn all off" unticks every switch of the page's list, also one that is ticked but not listed (walk rings that are not drawn).
- The shading menu is set to none.
- The Economy tab is emptied through `ECON.api.clear()`: its layers, its composite and its scenario. The place picked in the tab stays.

On the 2D map, Límites and the selected municipio stay. On the 3D view, the camera stays.

**The message counts the rows that went.** A layer's button can take another row with it: turning stops off at zoom 14 also ends the drawn walk rings (when stations are off), so the message says "2 layers turned off".

**The route plan is kept.** It is listed, so the person knows it is on the map, but "Turn all off" does not clear it. While it is listed, a note above "Turn all off" says so. A plan holds what was typed: the names of the places, the order of the stops and the results. The link keeps only the points, and a message with Undo lasts a few seconds. So clearing the plan by accident would lose work that cannot be brought back. Its own button in the list clears it, with Undo, as the planner's own "Clear" does. When only the plan is left, the list shows the note and no "Turn all off".

**Undo** puts back what the page held just before:
- every switch, the shading choice, the Economy layers (the same layer objects, with their settings), the composite and the scenario;
- the route plan's stops and their names, when they changed;
- on the 3D view, whether the year mode switched sea level rise on, so leaving the year mode still turns it off.

The URL hash comes back the same. The browser test checks this in both languages at both widths.

The message stays while the pointer is on it or it has the focus. After "Turn all off" the focus goes to Undo, and after Undo it goes back to the chip.

**Undo is offered only right after the action.** The chip remembers what was on just after it. When any layer, the shading, an Economy layer or the route plan changes after that, the message goes away: its Undo would undo the later change too. What is on means the settings: each switch, ticked or not, and its name in the list. A zoom or a move of the map is not a change. Below zoom 14 the walk rings leave the list, but their switch is the same, so Undo stays.

**The focus never falls to the page's body.** When the message with Undo is withdrawn, or another message takes its place while Undo has the focus, the focus goes to the chip. When no chip shows, it goes to the map.

## How it stays current

The chip reads the list again, at most once per step, after any of these:
- any change event (capture phase, so it also sees the events that code fires, which do not bubble);
- `refreshFolds()`;
- `writeHash()` (2D), which runs after every change of what the map shows;
- `ecRender()` (Economy tab);
- `setMetric()` and the route planner's drawing (3D).

A failed download that unticks its switch calls `refreshFolds()` (the Transit tab's vehicles on the 2D map, the 3D service-in-the-hour layers), so the chip and the group counts follow.

The open list is rebuilt only when what is on changes, so a move of the map does not take the focus away.

The 2D map now reads the route plan of a link (`r=`) when `network.js` loads (`planInLink`). Before, it read it after the transit operators arrived. By then the map could already have rewritten the address without the plan, so a link with layers and a route sometimes opened without the route. The browser test caught this.

## Layout and accessibility

- **Placement:** centred at the top of the map's own element, so it moves with the map when the chat or the workbench takes part of the screen. Its layer (z-index 870) is under the legends (880 and 890) and the message (900), so it never covers them. While the chip shows, the message moves below it.
- **Open list:** above the legends and the map's buttons until it closes. Its height is set each time it opens or changes, and when the window is resized; it scrolls inside.
  - It ends 8 px above anything lower on the map in its column: the zoom buttons, the scale, the credits, the MapLibre buttons and, on the 3D view, the time bar. It is fitted again when one of them changes size while the list is open (the credits grow as the layers' sources load).
  - It also ends above a legend in its column when that leaves it at least 140 px.
  - If a message shows, the list starts below it, and a message shown while the list is open sits above it.
  - On a 3D phone (400 px wide or less) the list leaves the column of the MapLibre buttons free, so it reaches down to the scale instead of ending above the first button: 393 px instead of 141 at 390 px, 373 instead of 121 at 320 px.
  - The browser test checks this at 1400, 1024 (chat open), 768, 390 and 320 px on both pages.
- **Chip:** it does not shrink, so it keeps its height while a long list is open.
- **Pattern:** the WAI-ARIA disclosure pattern. The chip is a button with `aria-expanded` and `aria-controls`. Escape, a press outside the list or the chip closes it, and Escape gives the focus back to the chip. When a layer's button removes its row, the next row's button takes the focus.
- **Map events:** a press, scroll or double click on the chip, the list or the message does not reach the map under it.
- **Colours:** charcoal on white; the open chip uses the blue tint (`--tint-blue-bg`, `--tint-blue-fg`). Every pair passes WCAG AA. The site has no dark mode.

## Weight

`budget.py` on LF copies (`git archive`), main 23981cb against this branch:

| Page | Main (KB) | Branch (KB) |
|---|---|---|
| Map scripts | 235.0 of 250 | 240.7 |
| 3D scripts | 623.0 of 700 | 628.5 |

`core/activelayers.js` is 4.9 KB compressed, and the hooks in `app.js`, `economy.js`, `network.js` and `twin3d.js` add 0.1 to 0.4 KB each.

A version that loaded the list on the first press saved only 0.45 KB, at the cost of a wait on that press, so the list ships with the chip.

## The browser test

`tests/browser/active_layers.js` waits for conditions in the page, not fixed times. It exits 3 when the run stops before its end (a lost connection to Chrome, say), 2 on an error, 1 when a check fails and 0 when all pass. On 2026-10-19 it passed 716 checks three times in a row: es and en, at 1400 and 390 px on both pages, plus the five widths of the layout pass. After the second review it has a walk-rings pass (`ringRules`): the link `#c=18.45,-66.07,14&l=flood,stops,muni,rings`, × on Flood then a zoom to 13 (Undo stays), "Turn all off" at zoom 13 (the rings leave the link and stay off when stops come back), and × on Stops at zoom 14 ("2 layers turned off"). The whole run passed 804 checks; on the code before the fix, the walk-rings pass fails 8 of its 22 checks per language, among them the three findings.

## Not covered

- **Study areas shown on the 2D map** (the workbench's Study areas view) are not counted. They are drawn from a set kept in the browser, outside the layer menus and the link.
- **The 3D view's "Existing routes" profile** is not counted either. It is a selection, not a switch.

Both could join the list as parts of the adapter.

## The "On the map" panel (navigation plan PR 2, decision 81, 2026-11-04)

The chip's list is now the **"En el mapa / On the map" panel**:

- **Wide screens (1,100 px and up):** the panel opens by itself on the right of the map as soon as a layer is on, and stays open whatever tab is open and when the map is clicked. The chip folds it; a folded panel stays folded for the visit (`sessionStorage` `alFolded`), and the chip opens it again.
- **Narrower screens:** the chip opens and closes the list as before (a press elsewhere closes it).
- **What it holds:** a heading, the list of every layer that is on (points, lines, areas, "Shade municipalities by", the route plan), "Turn all off" with Undo, and a dock with the Economy tab's year control (year, play, slider, "change measured from"), its layer cards (order, opacity, Shaded or Symbol, settings and area level) and its buttons (Workbench, Clear all, Copy link). `Core.activelayers.dock(nodes)` moves those nodes once `economy.js` has built them (`econBoot`), so their handlers stay; the Economy tab keeps a note with "Open the panel" (`ActiveLayers.open()`). The Economy layers are listed once, as their cards, while the dock holds them.
- **Legends** stay on the map, as before.

To make room for it on the 2D map (250 KB of scripts), the route planner moved out of `plan.js` into `plan_route.js`, loaded on first use (network.js `planLoad`): map scripts 249.3 → 241.8 KB, and 242.7 KB with the panel (LF copy, `budget.py`).
