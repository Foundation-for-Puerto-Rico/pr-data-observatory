/* PR Data Observatory: the workbench's "Study areas" view (plan item 16, section C4; docs/study-areas.md). Loaded the first time the view opens.
   A person loads a GeoJSON file of polygons (a neighborhood, a corridor, a program's service area). It is read in this browser and never uploaded; only each polygon's
   name and shape are kept, with the set's name, source and description, in IndexedDB, and "Export" writes it back as GeoJSON. For every area the view gives what it holds
   (residents by census block centroid, residents far from a scheduled stop, transit stops; on request tourism places and the share in flood and protected areas) and an
   estimate of every dataset of the Economy tab from the municipios it covers, each with its method.
   "Area around a point" (GIS tools step 1, HANDOFF decision 93, docs/gis-tools-proposal-2026-11.md): a circle or a ring around a point picked on the map, the map's center or
   typed coordinates, kept as an area of the set "Areas around points" and measured like any other. "Also measure surface heat, greenness and landslide susceptibility" adds
   zonal statistics of the summer heat images and estimates from the barrios covered.
   "What drains here" (GIS tools step 3, docs/watersheds.md): the land that drains to a point, from the USGS NHDPlus HR catchments (catchments.geojson, loaded on
   first use) walked upstream (Core.study.upstream), kept as an area of the set "Areas that drain to points".
   "Build my region" and "Count my points" (GIS tools step 4): municipios or barrios merged into one area (and the regional profile of two or more municipios);
   the points of a CSV or GeoJSON counted by barrio, municipio and study area, in this browser, never drawn, counts under 5 shown as "fewer than 5".
   "Download what's inside" (GIS tools step 5): for every area of the set summarized, the points of a dataset inside it or the outlines that overlap it, as
   GeoJSON or CSV, each row naming its area and source.
   "Walking time" (GIS tools step 6): the area within a walk of 5 to 20 minutes along mapped roads from a point, as a study area.
   Uses the Economy tab's engine (E, EC, ecSaveCsv), the map's state (S, map, Data) and Core.study. Text goes through T / Tn / Th. */
const StudyAreas = (() => {
  const DB = 'pr-twin-studyareas', STORE = 'sets', ST = Core.study;
  let mem = null;   // when the browser keeps no IndexedDB (a private window), the sets of this visit only
  const st = { sel: '', msg: '', err: [], persistent: true, y: null, q: '', extra: false, land: false, busy: false, res: null, shown: '', page: 0, r: 800, r0: 0, around: '', drawn: '', drain: '', picking: false, pickMode: 'around', rlev: 'muni', rsel: new Set(), rq: '', myreg: '', pts: null, plev: 'barrio', dl: 'stops', dlf: 'geojson', walk: '', wmin: 10 };
  const DIST = [400, 800, 1000, 1600, 5000], MAX_R = 20000;   // the distances offered in one click (meters); "More settings" takes any outer distance up to 20 km and an inner one for a ring
  const PAGE = 12;   // areas shown side by side; the CSV holds them all
  let layer = null;

  // ── storage ────────────────────────────────────────────────────────────
  function open() {
    return new Promise((ok, fail) => {
      if (typeof indexedDB === 'undefined') return fail(new Error('no IndexedDB'));
      const r = indexedDB.open(DB, 1);
      r.onupgradeneeded = () => r.result.createObjectStore(STORE, { keyPath: 'id' });
      r.onsuccess = () => ok(r.result); r.onerror = () => fail(r.error);
    });
  }
  async function run(mode, fn) {
    const d = await open();
    return new Promise((ok, fail) => { const t = d.transaction(STORE, mode), req = fn(t.objectStore(STORE)); t.oncomplete = () => ok(req && req.result); t.onerror = () => fail(t.error); });
  }
  const ok = new Set();   // sets checked in this visit: a set of many large polygons takes a moment to check, and the list is read on every redraw
  async function list() {   // the stored sets that pass the checks, newest first
    let all; try { all = (await run('readonly', s => s.getAll())) || []; } catch { st.persistent = false; all = (mem = mem || []).slice(); }
    return all.filter(x => x && (ok.has(x.id + '|' + x.created) || (!ST.check(x).length && ok.add(x.id + '|' + x.created)))).sort((p, q) => String(q.created).localeCompare(String(p.created)));
  }
  async function save(set) { ok.add(set.id + '|' + set.created); try { await run('readwrite', s => s.put(set)); } catch { st.persistent = false; mem = (mem || []).filter(x => x.id !== set.id).concat(set); } }
  async function remove(id) { try { await run('readwrite', s => s.delete(id)); } catch { mem = (mem || []).filter(x => x.id !== id); } }

  // ── what the measures read: loaded on first use ─────────────────────────
  const gz = (f) => (((S.catalog || {}).weights || {})[f] || {}).gz || 0;
  let baseP = null;
  function base() {
    return baseP || (baseP = Promise.all([Data.json('data/population_blocks.json'), Data.json('data/transport.json')]).then(([blocks, transport]) => {
      const at = new Map(S.muniFc.features.map(f => [f.properties.municipality, f.geometry]));
      return { blocks, stops: transport.filter(s => s.kind === 'transit_stop' && /gtfs/.test(s.source || '')).map(s => [s.lng, s.lat]),
        munis: E.geo.names.slice(0, E.geo.pr).map(n => at.get(n) || null), pop: E.geo.names.slice(0, E.geo.pr).map(n => (S.muni[n] || {}).population_2020 || 0) };
    }).catch(e => { baseP = null; throw e; }));
  }
  let extraP = null;
  function extra() {
    return extraP || (extraP = Promise.all([S.placesLoaded ? S.places : Data.json('data/places.json'), S.flood || Data.json('data/flood.geojson'), S.prot || Data.json('data/protected.geojson')]).then(([places, flood, prot]) => ({
      places: places.filter(p => isFinite(p.lng) && isFinite(p.lat)).map(p => [p.lng, p.lat]),
      flood: flood.features.filter(f => f.geometry && /Polygon/.test(f.geometry.type) && (f.properties || {}).SFHA_TF !== 'F').map(f => f.geometry),
      protected: prot.features.filter(f => f.geometry && /Polygon/.test(f.geometry.type)).map(f => f.geometry),
    })).catch(e => { extraP = null; throw e; }));
  }

  // The heat images (the map's own loader and cache: surfOpen in app.js, Core.surfscale) and the barrio values of greenness and landslide susceptibility, on request.
  const LAND = [{ key: 'veg', file: 'data/vegetation_barrio.json', v: 'veg_ndvi_med' }, { key: 'slide', file: 'data/landslide_barrio.json', v: 'ls_land_high_pct' }];
  let landP = null;
  function land() {
    return landP || (landP = (async () => {
      if (!(window.Core && Core.surfscale)) await addJs('js/core/surfscale.js?v=4');
      const [day, night, fc, ...zs] = await Promise.all([surfOpen('day'), surfOpen('night'), S.barrios || Data.json('data/barrios.geojson'), ...LAND.map(z => Data.json(z.file))]);
      const surf = (key, o) => ({ key, at: ST.raster(o.steps(), o.W, o.H, o.meta.bounds, o.meta.scale.low, o.meta.scale.high, Core.surfscale.STEPS), meta: o.meta });
      const feats = fc.features.filter(f => f.geometry && /Polygon/.test(f.geometry.type)), vals = {}, years = {};
      LAND.forEach((z, k) => {
        const d = zs[k], v = d.vars.find(x => x.key === z.v), y = Object.keys(v.years).sort().pop(), at = new Map(d.geo.ids.map((id, i) => [id, v.years[y][i]]));
        vals[z.key] = feats.map(f => { const x = at.get(f.properties.geoid); return x == null ? null : x; }); years[z.key] = +y;
      });
      return { surfaces: [surf('day', day), surf('night', night)], zones: { geoms: feats.map(f => f.geometry), vals }, years };
    })().catch(e => { landP = null; throw e; }));
  }

  // ── an area around a point ─────────────────────────────────────────────
  const dist = (m) => m >= 1000 ? T('{n} km', { n: fmt(m / 1000, m % 1000 ? 1 : 0) }) : T('{n} m', { n: fmt(m, 0) });
  /** Adds the circle (or ring) of the distances chosen around (lng, lat) to the set "Areas around points" of this visit (made on the first point), selects it and shows it.
      Returns the message for the view. */
  /** An area drawn with Tools › Map tools › Draw an area (js/measure.js), added to the set "Drawn areas" and summarized like any other. Returns the message to show. */
  async function addDrawn(geometry, name) {
    const area = { name: String(name || T('Drawn area')).slice(0, 80), geometry };
    let set = (await list()).find(x => x.id === st.drawn);
    if (set && set.areas.length >= ST.MAX_AREAS) set = null;
    if (set) { const names = new Set(set.areas.map(a => a.name)), b = area.name; let n = 2; while (names.has(area.name)) area.name = `${b} (${n++})`; set.areas.push(area); }
    else set = ST.make({ name: T('Drawn areas'), source: T('Drawn in this browser (Draw an area)'), description: '', areas: [area] });
    const errors = ST.check(set); if (errors.length) { if (set.id === st.drawn) set.areas.pop(); return errors[0]; }
    await save(set); st.drawn = set.id; st.sel = set.id; st.res = null; st.page = Math.floor((set.areas.length - 1) / PAGE);
    show(set);
    st.msg = T('Added "{name}" to "{set}". Its summary is below.', { name: area.name, set: set.name }); st.err = [];
    if (lastBody && lastBody.isConnected) render(lastBody);
    return st.msg;
  }
  async function addAround(lng, lat) {
    const r = st.r, r0 = st.r0 > 0 && st.r0 < r ? st.r0 : 0;
    if (!(isFinite(lng) && isFinite(lat)) || lng < ST.BOX[0] || lng > ST.BOX[2] || lat < ST.BOX[1] || lat > ST.BOX[3]) return T('That point is outside Puerto Rico.');
    let muni = '';
    try { const b = await base(), i = b.munis.findIndex(g => g && ST.inside(g, lng, lat)); if (i >= 0) muni = E.geo.names[i]; } catch { /* the name is a convenience */ }
    const where = `${lat.toFixed(4)}, ${lng.toFixed(4)}`;
    const area = { name: (r0 ? T('{inner} to {outer} around {where}', { inner: dist(r0), outer: dist(r), where }) : T('{d} around {where}', { d: dist(r), where })) + (muni ? ` (${muni})` : ''), geometry: ST.ring(lng, lat, r, r0) };
    let set = (await list()).find(x => x.id === st.around);
    if (set && set.areas.length >= ST.MAX_AREAS) set = null;
    if (set) { const names = new Set(set.areas.map(a => a.name)), base_ = area.name; let n = 2; while (names.has(area.name)) area.name = `${base_} (${n++})`; set.areas.push(area); }
    else set = ST.make({ name: T('Areas around points'), source: T('Drawn in this browser (Area around a point)'), description: '', areas: [area] });
    const errors = ST.check(set); if (errors.length) { if (set.id === st.around) set.areas.pop(); return errors[0]; }
    await save(set); st.around = set.id; st.sel = set.id; st.res = null; st.page = Math.floor((set.areas.length - 1) / PAGE);
    show(set);
    return T('Added "{name}" to "{set}". Its summary is below.', { name: area.name, set: set.name });
  }
  // ── what drains to a point ─────────────────────────────────────────────
  let catchP = null;
  const catchments = () => catchP || (catchP = Data.json('data/catchments.geojson').then(fc => {
    const geoms = fc.features.map(f => f.geometry), dn = fc.features.map(f => f.properties.dn), via = fc.features.map(f => f.properties.via || null);
    return { fc, geoms, dn, via, at: ST.locate(geoms) };
  }).catch(e => { catchP = null; throw e; }));
  /** Adds the land that drains to (lng, lat) to the set "Areas that drain to points" of this visit: the catchment under the point and every catchment upstream of it. */
  async function addDrain(lng, lat) {
    if (!(isFinite(lng) && isFinite(lat)) || lng < ST.BOX[0] || lng > ST.BOX[2] || lat < ST.BOX[1] || lat > ST.BOX[3]) return T('That point is outside Puerto Rico.');
    let C; try { C = await catchments(); } catch { return T('The stream network could not be loaded. Check your connection and try again.'); }
    const i = C.at(lng, lat); if (i < 0) return T('No mapped stream drains that point (the sea, or the edge of the coast). Pick a point on land.');
    const up = ST.upstream(C.dn, i, C.via), km2 = up.reduce((a, k) => a + C.fc.features[k].properties.km2, 0);
    let river = ''; for (let k = i, n = 0; k >= 0 && n < 50 && !river; k = C.dn[k], n++) river = C.fc.features[k].properties.name || '';
    const where = `${lat.toFixed(4)}, ${lng.toFixed(4)}`;
    const area = { name: T('Land draining to {where}', { where }) + (river ? ` (${river})` : ''), geometry: ST.merge(up.map(k => C.geoms[k])) };
    let set = (await list()).find(x => x.id === st.drain);
    if (set && set.areas.length >= ST.MAX_AREAS) set = null;
    if (set) { const names = new Set(set.areas.map(a => a.name)), base_ = area.name; let n = 2; while (names.has(area.name)) area.name = `${base_} (${n++})`; set.areas.push(area); }
    else set = ST.make({ name: T('Areas that drain to points'), source: T('USGS NHDPlus HR catchments, traced upstream in this browser (What drains here)'), description: '', areas: [area] });
    const errors = ST.check(set); if (errors.length) { if (set.id === st.drain) set.areas.pop(); return errors[0]; }
    await save(set); st.drain = set.id; st.sel = set.id; st.res = null; st.page = Math.floor((set.areas.length - 1) / PAGE);
    show(set);
    return T('Added "{name}": {n} catchments, {km2} km². Its summary is below.', { name: area.name, n: fmt(up.length, 0), km2: fmt(km2, 1) });
  }
  // ── build my region (GIS tools step 4, docs/study-areas.md) ────────────
  // Municipios or barrios chosen from a list (or a ready-made region), merged into one study area (a dissolve: the parts are kept, which the measures handle).
  // Two or more whole municipios also open the regional profile (profile.html?ids=), whose rates are pooled where their parts are published.
  const RLIMIT = 200;   // list rows shown at once; the search narrows them
  let barP = null, regP = null;
  const barrios = () => barP || (barP = (S.barrios ? Promise.resolve(S.barrios) : Data.json('data/barrios.geojson')).then(fc => {
    const fs = fc.features.filter(f => f.geometry && /Polygon/.test(f.geometry.type));
    return { fs, by: new Map(fs.map(f => [f.properties.geoid, f])), at: ST.locate(fs.map(f => f.geometry)) };
  }).catch(e => { barP = null; throw e; }));
  const regionsList = () => regP || (regP = Data.json('data/geo/regions.json').then(d => d.regions || [], () => []));
  async function regionUnits() {   // [{ id, name, geometry }] of the level chosen
    if (st.rlev === 'barrio') { const B = await barrios(); return B.fs.map(f => ({ id: f.properties.geoid, name: `${f.properties.barrio}, ${f.properties.municipality}`, geometry: f.geometry })); }
    const b = await base(); return E.geo.ids.slice(0, E.geo.pr).map((id, i) => ({ id, name: E.geo.names[i], geometry: b.munis[i] })).filter(u => u.geometry);
  }
  async function addRegion() {
    const units = (await regionUnits()).filter(u => st.rsel.has(u.id));
    if (!units.length) return T('Choose at least one municipio or barrio.');
    const names = units.map(u => u.name), label = names.length <= 3 ? names.join(', ') : T('{first} and {n} more', { first: names.slice(0, 2).join(', '), n: names.length - 2 });
    const area = { name: T('Region: {names}', { names: label }), geometry: ST.merge(units.map(u => u.geometry)) };
    let set = (await list()).find(x => x.id === st.myreg);
    if (set && set.areas.length >= ST.MAX_AREAS) set = null;
    if (set) { const have = new Set(set.areas.map(a => a.name)), base_ = area.name; let n = 2; while (have.has(area.name)) area.name = `${base_} (${n++})`; set.areas.push(area); }
    else set = ST.make({ name: T('My regions'), source: T('Municipios and barrios merged in this browser (Build my region)'), description: '', areas: [area] });
    const errors = ST.check(set); if (errors.length) { if (set.id === st.myreg) set.areas.pop(); return errors[0]; }
    await save(set); st.myreg = set.id; st.sel = set.id; st.res = null; st.page = Math.floor((set.areas.length - 1) / PAGE);
    show(set);
    return T('Added "{name}" ({n} parts). Its summary is below.', { name: area.name, n: units.length });
  }
  async function regionBox(body) {
    const box = body.querySelector('#saRegList'); if (!box) return;
    let units; try { units = await regionUnits(); } catch { box.innerHTML = `<div class="empty">${esc(T('The list could not be loaded. Check your connection and try again.'))}</div>`; return; }
    const q = norm(st.rq), hit = units.filter(u => !q || norm(u.name).includes(q)), shownU = hit.slice(0, RLIMIT);
    box.innerHTML = shownU.map(u => `<label class="sa-chk"><input type="checkbox" data-unit="${esc(u.id)}"${st.rsel.has(u.id) ? ' checked' : ''}> ${esc(u.name)}</label>`).join('')
      + (hit.length > RLIMIT ? `<div class="note">${esc(T('{n} more: type to narrow the list.', { n: hit.length - RLIMIT }))}</div>` : '') + (hit.length ? '' : `<div class="empty">${esc(T('Nothing matches.'))}</div>`);
    const nSel = st.rsel.size, munis = st.rlev === 'muni' ? [...st.rsel].filter(g => /^72\d{3}$/.test(g)) : [];
    body.querySelector('#saRegN').textContent = Tn(nSel, '{n} chosen', '{n} chosen');
    const prof = body.querySelector('#saRegProf');
    if (munis.length >= 2) { prof.href = 'profile.html?ids=' + munis.sort().join(','); prof.removeAttribute('aria-disabled'); prof.classList.remove('disabled'); }
    else { prof.removeAttribute('href'); prof.setAttribute('aria-disabled', 'true'); prof.classList.add('disabled'); }
  }

  // ── count my points (GIS tools step 4) ─────────────────────────────────
  // A CSV with latitude and longitude columns, or a GeoJSON of points, read in this browser and never uploaded or stored. The points are counted by barrio, by
  // municipio and in each study area of the summary; they are never drawn, and a count under MIN_SHOWN is shown as "fewer than 5" (the observatory's rule for
  // places that may be homes: count, never draw or name).
  const MIN_SHOWN = 5, MAX_PTS = 200000, MAX_FILE = 20 * 1024 * 1024;
  const READ_ERR = { json: 'The file is not valid JSON.', empty: 'The file has no rows.', columns: 'No latitude and longitude columns: name them lat and lon (or latitude and longitude, latitud and longitud).' };
  const readPoints = (text, name) => { const r = ST.points(text, name, MAX_PTS); return r.error ? { error: T(READ_ERR[r.error]) } : r; };   // TK: the three texts above are shown with T()
  async function countPoints() {
    const P = st.pts; if (!P) return null;
    if (P.by) return P.by;
    const [b, B] = await Promise.all([base(), barrios()]), mAt = ST.locate(b.munis);
    const muni = new Map(), bar = new Map(); let none = 0;
    for (const [x, y] of P.pts) {
      const i = mAt(x, y), k = B.at(x, y);
      if (i < 0 && k < 0) { none++; continue; }
      if (i >= 0) muni.set(E.geo.ids[i], (muni.get(E.geo.ids[i]) || 0) + 1);
      if (k >= 0) { const id = B.fs[k].properties.geoid; bar.set(id, (bar.get(id) || 0) + 1); }
    }
    return (P.by = { muni, bar, none, names: { muni: new Map(E.geo.ids.slice(0, E.geo.pr).map((id, i) => [id, E.geo.names[i]])), bar: new Map(B.fs.map(f => [f.properties.geoid, `${f.properties.barrio}, ${f.properties.municipality}`])) } });
  }
  const shownCount = (n) => n == null ? '—' : n > 0 && n < MIN_SHOWN ? T('fewer than {n}', { n: MIN_SHOWN }) : fmt(n, 0);
  let ptsLayer = null;
  async function shadePoints(on) {
    if (ptsLayer) { map.removeLayer(ptsLayer); ptsLayer = null; }
    if (!on || !st.pts) return;
    const by = await countPoints(), lv = st.plev, counts = lv === 'muni' ? by.muni : by.bar;
    const fc = lv === 'muni' ? S.muniFc : { type: 'FeatureCollection', features: (await barrios()).fs };
    const vals = [...counts.values()].filter(n => n >= MIN_SHOWN).sort((a, b) => a - b), q = (p) => vals.length ? vals[Math.min(vals.length - 1, Math.floor(p * vals.length))] : Infinity;
    const cuts = [q(0.25), q(0.5), q(0.75)], cols = ['#DEEBF7', '#9ECAE1', '#4292C6', '#08519C'];
    const idOf = (f) => lv === 'muni' ? E.geo.ids[E.geo.names.indexOf(f.properties.municipality)] : f.properties.geoid;
    ptsLayer = L.geoJSON(fc, { interactive: false, style: (f) => { const n = counts.get(idOf(f)) || 0; return n === 0 ? { stroke: false, fill: false } : n < MIN_SHOWN ? { color: '#757575', weight: .5, fillColor: '#BDBDBD', fillOpacity: .45 } : { color: '#08306B', weight: .5, fillColor: cols[cuts.filter(c => n > c).length], fillOpacity: .75 }; } }).addTo(map);
  }
  function pointsCsv() {
    const P = st.pts, by = P && P.by; if (!by) return;
    const rows = [...by.bar].map(([id, n]) => [T('Barrio'), id, by.names.bar.get(id) || id, n < MIN_SHOWN ? T('fewer than {n}', { n: MIN_SHOWN }) : n])
      .concat([...by.muni].map(([id, n]) => [T('Municipio'), id, by.names.muni.get(id) || id, n < MIN_SHOWN ? T('fewer than {n}', { n: MIN_SHOWN }) : n]));
    ecSaveCsv('pr_my_points_counts.csv', [T('Level'), T('Code'), T('Name'), T('Points')], rows);
  }
  async function pointsBox(body) {
    const box = body.querySelector('#saPtsRes'); if (!box) return;
    const P = st.pts; if (!P) { box.innerHTML = ''; return; }
    box.innerHTML = `<div class="empty" role="status">${esc(T('Counting…'))}</div>`;
    let by; try { by = await countPoints(); } catch { box.innerHTML = `<div class="empty">${esc(T('The outlines could not be loaded. Check your connection and try again.'))}</div>`; return; }
    const lv = st.plev, counts = lv === 'muni' ? by.muni : by.bar, names = lv === 'muni' ? by.names.muni : by.names.bar;
    const top = [...counts].sort((a, b) => b[1] - a[1]).slice(0, 15);
    box.innerHTML = `<div class="note">${esc(T('{file}: {rows} rows, {pts} points in Puerto Rico ({none} of them off the barrio outlines, in the sea or on a cay), {out} outside Puerto Rico, {bad} without coordinates.', { file: P.file, rows: fmt(P.rows, 0), pts: fmt(P.pts.length, 0), none: fmt(by.none, 0), out: fmt(P.outside, 0), bad: fmt(P.bad, 0) }))}</div>`
      + `<div class="eb-scroll" tabindex="0" role="region" aria-label="${esc(T('Points by area, scrollable'))}"><table class="ec-tbl"><thead><tr><th scope="col">${esc(lv === 'muni' ? T('Municipio') : T('Barrio'))}</th><th scope="col" class="num">${esc(T('Points'))}</th></tr></thead><tbody>`
      + top.map(([id, n]) => `<tr><th scope="row">${esc(names.get(id) || id)}</th><td class="num">${esc(shownCount(n))}</td></tr>`).join('') + `</tbody></table></div>`
      + `<div class="note">${esc(T('{n} areas have points; the 15 with the most are listed. Counts under {min} are shown as "fewer than {min}". The points are never drawn.', { n: counts.size, min: MIN_SHOWN }))}</div>`
      + `<div class="btn-row"><button type="button" class="btn small" data-ptsshade aria-pressed="${!!ptsLayer}">${esc(ptsLayer ? T('Hide the shading') : T('Shade the map by count'))}</button><button type="button" class="btn small" data-ptscsv><span class="ms-icon" aria-hidden="true">download</span>${esc(T('Download the counts (CSV)'))}</button><button type="button" class="btn small" data-ptsclear>${esc(T('Forget the file'))}</button></div>`;
  }
  // ── download what's inside (GIS tools step 5, docs/study-areas.md) ─────
  // For every area of the set on screen: the points of a dataset inside it (cut at its edge), or the polygons that overlap it (whole outlines, not cut: the observatory
  // has no polygon clipping). GeoJSON or CSV, one row per feature and area ("area" names it). Withheld places have no point, so they are never in a file.
  const FILEPT = (file, label, fields) => ({ id: file, label, kind: 'pt', file: file + '.geojson', load: async () => (await Data.json('data/' + file + '.geojson')).features.filter(f => f.geometry && f.geometry.type === 'Point').map(f => ({ lng: f.geometry.coordinates[0], lat: f.geometry.coordinates[1], p: Object.fromEntries(fields.map(k => [k, f.properties[k] == null ? '' : f.properties[k]])) })) });
  const FILEPOLY = (file, label, fields, keep) => ({ id: file, label, kind: 'poly', file: file + '.geojson', load: async () => (await Data.json('data/' + file + '.geojson')).features.filter(f => f.geometry && /Polygon/.test(f.geometry.type) && (!keep || keep(f))).map(f => ({ g: f.geometry, p: Object.fromEntries(fields.map(k => [k, f.properties[k] == null ? '' : f.properties[k]])) })) });
  const DL = [
    { id: 'stops', label: TK('Scheduled transit stops'), kind: 'pt', file: 'transport.json', load: async () => (await Data.json('data/transport.json')).filter(s => s.kind === 'transit_stop' && /gtfs/.test(s.source || '')).map(s => ({ lng: s.lng, lat: s.lat, p: { name: s.name || '', operator: s.operator_name || s.operator || '', municipio: s.municipality || '', routes: (s.routes || []).join(' '), trips_weekday: s.trips_weekday == null ? '' : s.trips_weekday } })) },
    { id: 'places', label: TK('Tourism places (withheld places left out)'), kind: 'pt', file: 'places.json', load: async () => (await Data.json('data/places.json')).filter(p => !p.withheld && isFinite(p.lng) && isFinite(p.lat)).map(p => ({ lng: p.lng, lat: p.lat, p: { name: p.name || '', category: p.category || '', type: p.type || '', municipio: p.municipality || '', barrio: p.barrio || '', source: p.source || '', updated: p.updated || '' } })) },
    { id: 'blocks', label: TK('Census 2020 blocks: residents at each block\'s point'), kind: 'pt', file: 'population_blocks.json', load: async () => (await base()).blocks.map(k => ({ lng: k[0], lat: k[1], p: { residents: k[2], metres_to_scheduled_stop: Math.round(k.length > 4 ? k[4] : k[3]) } })) },
    FILEPT('fire_stations', TK('Fire stations'), ['name', 'type', 'municipio']), FILEPT('police_stations', TK('Police stations'), ['name', 'type', 'municipio']),
    FILEPT('libraries', TK('Libraries'), ['name', 'type', 'municipio']), FILEPT('historic_places', TK('Historic places'), ['name', 'type', 'municipio', 'listed']),
    FILEPT('town_halls', TK('Town halls'), ['name', 'type', 'municipio']), FILEPT('public_housing', TK('Public housing'), ['name', 'type', 'municipio', 'units']),
    FILEPT('lihtc', TK('Tax-credit housing (LIHTC)'), ['name', 'type', 'municipio', 'units', 'li_units', 'year']), FILEPT('reservoirs', TK('Reservoir gauges'), ['name', 'type', 'municipio', 'usgs']), FILEPT('river_gauges', TK('River gauges'), ['name', 'type', 'municipio', 'usgs']), FILEPT('groundwater', TK('Groundwater wells'), ['name', 'type', 'municipio', 'usgs']), FILEPT('rain_gauges', TK('Rain gauges'), ['name', 'type', 'municipio', 'usgs']), FILEPT('bridges', TK('Bridges and tunnels (FHWA)'), ['name', 'type', 'municipio', 'sn', 'x', 'c', 'y', 'a', 'o', 's']), FILEPT('airports', TK('Airports and heliports (FAA)'), ['name', 'type', 'municipio', 'faa', 'cat']), FILEPT('ev_stations', TK('Public EV charging stations (AFDC)'), ['name', 'type', 'municipio', 'kind', 'ports', 'net', 'status']), FILEPT('power_plants', TK('Power plants (EIA)'), ['name', 'type', 'municipio', 'eia', 'tech', 'mw', 'bat_mw', 'status']),
    FILEPT('illegal_dumping', TK('Illegal dumping sites (FPR field survey)'), ['name', 'type', 'municipio', 'size', 'waste', 'burning']),
    FILEPOLY('flood', TK('FEMA flood hazard areas that overlap (whole outlines)'), ['FLD_ZONE', 'ZONE_SUBTY', 'SFHA_TF'], f => (f.properties || {}).SFHA_TF !== 'F'),
    FILEPOLY('protected', TK('Protected areas that overlap (whole outlines)'), ['Unit_Nm', 'Mang_Name', 'Des_Tp', 'GAP_Sts', 'Pub_Access']),
    FILEPOLY('watersheds', TK('Subwatersheds that overlap (whole outlines)'), ['huc12', 'name', 'basin', 'km2', 'residents']),
    FILEPOLY('barrios', TK('Barrios that overlap (whole outlines)'), ['barrio', 'municipality', 'geoid', 'km2']),
  ];
  /** The features of dataset d inside (points) or overlapping (polygons) each area of the set: [{ area, f }]. A polygon overlaps when one of the area's grid points is
      inside it or one of its corners is inside the area. */
  async function inside(set, d) {
    const feats = await d.load(), out = [];
    for (const a of set.areas) {
      const g = a.geometry, b = ST.bbox(g);
      if (d.kind === 'pt') { for (const f of feats) if (f.lng >= b[0] && f.lng <= b[2] && f.lat >= b[1] && f.lat <= b[3] && ST.inside(g, f.lng, f.lat)) out.push({ area: a.name, f }); continue; }
      ST.overlaps(g, feats.map(f => f.g)).forEach(k => out.push({ area: a.name, f: feats[k] }));
    }
    return out;
  }
  async function downloadInside(set, id, kind) {
    const d = DL.find(x => x.id === id); if (!d) return '';
    let rows; try { rows = await inside(set, d); } catch { return T('The data could not be loaded. Check your connection and try again.'); }
    const stem = `pr_${norm(set.name).replace(/[^a-z0-9]+/g, '_').slice(0, 30) || 'areas'}_${d.id}`, source = T('PR Data Observatory, data/{file}; license and credit in the data dictionary (dictionary.html)', { file: d.file });
    if (kind === 'csv') {
      const keys = rows.length ? Object.keys(rows[0].f.p) : [];
      ecSaveCsv(stem + '.csv', [T('Area'), ...keys, ...(d.kind === 'pt' ? ['lat', 'lon'] : []), T('Source')], rows.map(({ area, f }) => [area, ...keys.map(k => f.p[k]), ...(d.kind === 'pt' ? [f.lat, f.lng] : []), source]));
    } else {
      const fc = { type: 'FeatureCollection', name: stem, source, note: d.kind === 'pt' ? T('The points inside each area of "{set}".', { set: set.name }) : T('The outlines that overlap each area of "{set}", whole (not cut at the area\'s edge).', { set: set.name }),
        features: rows.map(({ area, f }) => ({ type: 'Feature', properties: { area, ...f.p }, geometry: d.kind === 'pt' ? { type: 'Point', coordinates: [f.lng, f.lat] } : f.g })) };
      const a = document.createElement('a'); a.href = URL.createObjectURL(new Blob([JSON.stringify(fc)], { type: 'application/geo+json' })); a.download = stem + '.geojson'; a.click(); setTimeout(() => URL.revokeObjectURL(a.href), 4000);
    }
    return Tn(rows.length, 'Downloaded {n} feature of "{data}".', 'Downloaded {n} features of "{data}".', { data: T(d.label) });
  }
  // ── walking time (GIS tools step 6, docs/study-areas.md) ───────────────
  // The area within a walk of some minutes along mapped roads (Core.study.walkArea on js/roads.js's graph, roads.bin, loaded on first use), at WALK_MPM meters a
  // minute, kept as an area of the set "Walking areas".
  const WALK_MPM = 80, WALK_MIN = [5, 10, 15, 20];   // 4.8 km/h, a common planning pace for adults (slower for older adults and children)
  let roadsP = null;
  const roads = () => roadsP || (roadsP = Roads.load('data/roads.bin').catch(e => { roadsP = null; throw e; }));
  async function addWalk(lng, lat) {
    if (!(isFinite(lng) && isFinite(lat)) || lng < ST.BOX[0] || lng > ST.BOX[2] || lat < ST.BOX[1] || lat > ST.BOX[3]) return T('That point is outside Puerto Rico.');
    let Rd; try { Rd = await roads(); } catch { return T('The road network could not be loaded. Check your connection and try again.'); }
    const min = st.wmin, w = ST.walkArea(Rd, lng, lat, min * WALK_MPM);
    if (!w) return T('No walkable mapped road is within 150 m of that point. Pick a point nearer a street.');
    let muni = '';
    try { const b = await base(), i = b.munis.findIndex(g => g && ST.inside(g, lng, lat)); if (i >= 0) muni = E.geo.names[i]; } catch { /* the name is a convenience */ }
    const where = `${lat.toFixed(4)}, ${lng.toFixed(4)}`;
    const area = { name: T('{n}-minute walk from {where}', { n: min, where }) + (muni ? ` (${muni})` : ''), geometry: w.geometry };
    let set = (await list()).find(x => x.id === st.walk);
    if (set && set.areas.length >= ST.MAX_AREAS) set = null;
    if (set) { const have = new Set(set.areas.map(a => a.name)), base_ = area.name; let n = 2; while (have.has(area.name)) area.name = `${base_} (${n++})`; set.areas.push(area); }
    else set = ST.make({ name: T('Walking areas'), source: T('Walks along mapped roads (OpenStreetMap), traced in this browser (Walking time)'), description: '', areas: [area] });
    const errors = ST.check(set); if (errors.length) { if (set.id === st.walk) set.areas.pop(); return errors[0]; }
    await save(set); st.walk = set.id; st.sel = set.id; st.res = null; st.page = Math.floor((set.areas.length - 1) / PAGE);
    show(set);
    return T('Added "{name}": {km2} km² within a {n}-minute walk. Its summary is below.', { name: area.name, km2: fmt(ST.areaKm2(w.geometry), 2), n: min });
  }
  /** CRIM's Catastro Digital at a point, in a new tab (only a link; Core.study.crimUrl). Called from the click itself, so the browser lets the tab open. */
  function openCrim(x, y) {
    const url = ST.crimUrl(x, y); if (!url) return T('That point is outside Puerto Rico.');
    window.open(url, '_blank', 'noopener');   // with noopener the browser returns no window, so a blocked tab cannot be told apart: the message says what to do
    return T('CRIM Catastro Digital opens in a new tab at {lat}, {lng}. If no tab opened, allow pop-ups for this site.', { lat: y.toFixed(5), lng: x.toFixed(5) });
  }
  let pickBody = null;
  // The click that picks the point is caught on the map's box before it reaches any layer (capture phase), so it does not also select a municipio or open a pop-up.
  // The map's controls (zoom, layers) still work, and a click that ends a drag of the map is left to the map.
  function stopPick() { st.picking = false; map.getContainer().removeEventListener('click', onPick, true); document.removeEventListener('keydown', onPickKey, true); map.getContainer().classList.remove('sa-picking'); }
  function onPick(e) {
    if (e.target.closest('.leaflet-control') || (map.dragging && map.dragging.moved())) return;
    e.stopPropagation(); e.preventDefault();
    const body = pickBody, ll = map.mouseEventToLatLng(e); stopPick();
    if (st.pickMode === 'crim') { const m = openCrim(ll.lng, ll.lat); st.msg = m; st.err = []; if (body) render(body); return; }
    if (body) { st.msg = st.pickMode === 'drain' ? T('Tracing the land upstream…') : st.pickMode === 'walk' ? T('Walking the roads…') : ''; render(body); }
    (st.pickMode === 'drain' ? addDrain : st.pickMode === 'walk' ? addWalk : addAround)(ll.lng, ll.lat).then(m => { st.msg = m; st.err = []; if (body) render(body); });
  }
  function onPickKey(e) { if (e.key === 'Escape' && st.picking) { stopPick(); st.msg = T('Picking a point was canceled.'); st.err = []; if (pickBody) render(pickBody); } }
  function startPick(body) {
    pickBody = body; if (st.picking) return;
    st.picking = true; map.getContainer().classList.add('sa-picking');
    map.getContainer().addEventListener('click', onPick, true); document.addEventListener('keydown', onPickKey, true);
  }
  /** The distances from the form: the menu's choice, or the outer distance typed under "More settings", and the inner one for a ring. '' when they are fine. */
  function readDist(body) {
    const o = +(body.querySelector('#saRo').value || 0), i = +(body.querySelector('#saRi').value || 0);
    if (o && !(o >= 50 && o <= MAX_R)) return T('The outer distance must be between 50 m and 20 km.');
    const r = o ? Math.round(o) : st.r;
    if (i && !(i > 0 && i < r)) return T('The inner distance must be less than the outer distance.');
    st.r = r; st.r0 = i > 0 ? Math.round(i) : 0;
    return '';
  }

  // ── the view ───────────────────────────────────────────────────────────
  const METHOD = {
    whole: 'Sum of the whole municipios inside',
    residents: 'Municipio totals × the share of their residents inside (estimate)',
    land: 'Municipio totals × the share of their land inside (estimate)',
    'avg-residents': 'Average of the municipios covered, weighted by their residents inside (estimate)',
    'avg-land': 'Average of the municipios covered, weighted by their land inside (estimate)',
  };
  const date = (s) => { try { return I18N.date(new Date(s), { dateStyle: 'medium' }); } catch { return s.slice(0, 10); } };
  let lastBody = null;   // the view's box, for addDrawn (js/measure.js), which is called from outside the view
  async function render(body) {
    lastBody = body;
    const all = await list();
    if (st.sel && !all.some(s => s.id === st.sel)) { st.sel = ''; st.res = null; }
    const rows = all.map(s => `<tr${s.id === st.sel ? ' class="sel"' : ''}><th scope="row">${esc(s.name)}<small>${esc(Tn(s.areas.length, '{n} area', '{n} areas'))} · ${esc(date(s.created))} · ${esc(T('Source: {source}', { source: s.source }))}</small>${s.description ? `<small class="sc-notes">${esc(s.description)}</small>` : ''}</th>
      <td class="sc-acts"><button type="button" class="btn small${s.id === st.sel ? ' primary' : ''}" data-sum="${esc(s.id)}">${esc(T('Summarize'))}</button><button type="button" class="btn small" data-show="${esc(s.id)}">${esc(st.shown === s.id ? T('Hide from the map') : T('Show on the map'))}</button><button type="button" class="btn small" data-export="${esc(s.id)}"><span class="ms-icon" aria-hidden="true">download</span>${esc(T('Export'))}</button><button type="button" class="icon-btn small" data-del="${esc(s.id)}" aria-label="${esc(T('Delete {name}', { name: s.name }))}"><span class="ms-icon" aria-hidden="true">delete</span></button></td></tr>`).join('');
    const custom = !DIST.includes(st.r) || st.r0 > 0;
    body.innerHTML = `<section class="sc-box sa-around" aria-labelledby="saAroundH"><h3 class="sec" id="saAroundH">${esc(T('Area around a point'))}</h3>
        <div class="note">${esc(T('Pick a point and a distance. The circle around it (a buffer) is measured like any study area: who lives there and how far they are from transit, and on request flood zones, surface heat, greenness and landslide susceptibility. It is drawn in this browser and kept with your study areas.'))}</div>
        <div class="btn-row sa-around-row"><label>${esc(T('Distance'))} <select id="saR">${DIST.map(m => `<option value="${m}"${m === st.r && !custom ? ' selected' : ''}>${esc(dist(m))}</option>`).join('')}${custom ? `<option value="" selected>${esc(st.r0 ? T('{inner} to {outer}', { inner: dist(st.r0), outer: dist(st.r) }) : dist(st.r))}</option>` : ''}</select></label>
          <button type="button" class="btn primary" data-pick aria-pressed="${st.picking && st.pickMode === 'around'}"><span class="ms-icon" aria-hidden="true">add_location_alt</span>${esc(st.picking && st.pickMode === 'around' ? T('Click the map (Esc to cancel)') : T('Pick a point on the map'))}</button>
          <button type="button" class="btn" data-centre><span class="ms-icon" aria-hidden="true">my_location</span>${esc(T('Use the center of the map'))}</button></div>
        <details class="sa-more"${custom ? ' open' : ''}><summary>${esc(T('More settings'))}</summary>
          <div class="sc-grid"><label class="sc-f">${esc(T('Outer distance (meters, 50 to 20,000)'))} <input type="number" id="saRo" min="50" max="20000" step="10" value="${custom ? st.r : ''}" placeholder="${st.r}"></label>
          <label class="sc-f">${esc(T('Inner distance for a ring (meters; empty for a full circle)'))} <input type="number" id="saRi" min="0" max="19990" step="10" value="${st.r0 || ''}"></label>
          <label class="sc-f">${esc(T('Latitude'))} <input type="text" inputmode="decimal" id="saLat" placeholder="18.4655"></label>
          <label class="sc-f">${esc(T('Longitude'))} <input type="text" inputmode="decimal" id="saLng" placeholder="-66.1057"></label></div>
          <div class="btn-row"><button type="button" class="btn small" data-coords>${esc(T('Add the area around these coordinates'))}</button><button type="button" class="btn small" data-newaround>${esc(T('Start a new set of areas around points'))}</button></div>
          <div class="note">${esc(T('A ring, from the inner to the outer distance, leaves out the land closest to the point: 800 m to 1.6 km, say. Every point you add goes into the same set, so the summary compares them side by side.'))}</div>
        </details></section>
      <section class="sc-box sa-around" aria-labelledby="saDrainH"><h3 class="sec" id="saDrainH">${esc(T('What drains here'))}</h3>
        <div class="note">${esc(T('Pick a point: the land whose rain flows to it, down the streams of the USGS network (its watershed), becomes a study area, with the same summary: residents, transit and, on request, flood zones, heat, greenness, landslides and slope. The stream network downloads once, about {mb} MB.', { mb: fmt(gz('catchments.geojson') / 1048576 || 3.2, 1) }))}</div>
        <div class="btn-row"><button type="button" class="btn primary" data-drainpick aria-pressed="${st.picking && st.pickMode === 'drain'}"><span class="ms-icon" aria-hidden="true">water</span>${esc(st.picking && st.pickMode === 'drain' ? T('Click the map (Esc to cancel)') : T('Pick a point on the map'))}</button>
          <button type="button" class="btn" data-draincentre><span class="ms-icon" aria-hidden="true">my_location</span>${esc(T('Use the center of the map'))}</button></div></section>
      <section class="sc-box sa-around" aria-labelledby="saWalkH"><h3 class="sec" id="saWalkH">${esc(T('Walking time'))}</h3>
        <div class="note">${esc(T('Pick a point: the area within a walk of so many minutes along mapped roads (a travel-time area) becomes a study area, with the same summary. At 4.8 km/h, on every road but motorways, both ways, and up to 100 m off the road; footpaths and steps are not on the map, so a walk is an estimate. The road network downloads once, about {mb} MB.', { mb: fmt(gz('roads.bin') / 1048576 || 3.3, 1) }))}</div>
        <div class="btn-row sa-around-row"><label>${esc(T('Minutes'))} <select id="saWm">${WALK_MIN.map(m => `<option value="${m}"${m === st.wmin ? ' selected' : ''}>${m}</option>`).join('')}</select></label>
          <button type="button" class="btn primary" data-walkpick aria-pressed="${st.picking && st.pickMode === 'walk'}"><span class="ms-icon" aria-hidden="true">hiking</span>${esc(st.picking && st.pickMode === 'walk' ? T('Click the map (Esc to cancel)') : T('Pick a point on the map'))}</button>
          <button type="button" class="btn" data-walkcentre><span class="ms-icon" aria-hidden="true">my_location</span>${esc(T('Use the center of the map'))}</button></div></section>
      <section class="sc-box sa-around" aria-labelledby="saCrimH"><h3 class="sec" id="saCrimH">${esc(T('Property parcels (CRIM)'))}</h3>
        <div class="note">${esc(T('Pick a point to open the CRIM Catastro Digital at that spot, in a new tab: the cadastre of every property in Puerto Rico, with its parcel outlines, numbers and aerial photos. CRIM lets its parcels be seen only in its own viewer, so the observatory copies nothing from it and draws no parcel. CRIM shows its own notice first; it is a tax record, not a survey.'))}</div>
        <div class="btn-row"><button type="button" class="btn primary" data-crimpick aria-pressed="${st.picking && st.pickMode === 'crim'}"><span class="ms-icon" aria-hidden="true">open_in_new</span>${esc(st.picking && st.pickMode === 'crim' ? T('Click the map (Esc to cancel)') : T('Pick a point on the map'))}</button>
          <button type="button" class="btn" data-crimcentre><span class="ms-icon" aria-hidden="true">my_location</span>${esc(T('Use the center of the map'))}</button></div></section>
      <section class="sc-box sa-around" aria-labelledby="saRegH"><h3 class="sec" id="saRegH">${esc(T('Build my region'))}</h3>
        <div class="note">${esc(T('Choose municipios or barrios, or start from a ready-made region, and add them as one study area (a dissolve). Two or more whole municipios also open the regional profile, where rates are pooled from their parts when those are published.'))}</div>
        <div class="btn-row sa-around-row"><label>${esc(T('Level'))} <select id="saRegL"><option value="muni"${st.rlev === 'muni' ? ' selected' : ''}>${esc(T('Municipios'))}</option><option value="barrio"${st.rlev === 'barrio' ? ' selected' : ''}>${esc(T('Barrios'))}</option></select></label>
          <label>${esc(T('Start from'))} <select id="saRegP"><option value="">${esc(T('(none)'))}</option></select></label>
          <label>${esc(T('Find'))} <input type="search" id="saRegQ" value="${esc(st.rq)}"></label></div>
        <div class="sa-list" id="saRegList" role="group" aria-label="${esc(T('Municipios or barrios to merge'))}"></div>
        <div class="btn-row"><span class="note" id="saRegN" role="status"></span><button type="button" class="btn primary small" data-regadd>${esc(T('Add as a study area'))}</button><a class="btn small" id="saRegProf" target="_blank" rel="noopener">${esc(T('Open the regional profile'))}</a><button type="button" class="btn small" data-regclear>${esc(T('Clear the choice'))}</button></div></section>
      <section class="sc-box sa-around" aria-labelledby="saPtsH"><h3 class="sec" id="saPtsH">${esc(T('Count my points'))}</h3>
        <div class="note">${esc(T('A CSV with latitude and longitude columns, or a GeoJSON of points (up to 200,000 points, 20 MB): counted by barrio and municipio, and in each area of the summary below. It is read in this browser, never uploaded or kept, and the points are never drawn. Counts under 5 are shown as "fewer than 5".'))}</div>
        <div class="btn-row sa-around-row"><label class="btn" for="saPtsF"><span class="ms-icon" aria-hidden="true">upload</span>${esc(T('Choose a file of points'))}</label><input type="file" id="saPtsF" accept=".csv,.txt,.geojson,.json,text/csv,application/geo+json,application/json" hidden>
          <label>${esc(T('Count by'))} <select id="saPtsL"><option value="barrio"${st.plev === 'barrio' ? ' selected' : ''}>${esc(T('Barrio'))}</option><option value="muni"${st.plev === 'muni' ? ' selected' : ''}>${esc(T('Municipio'))}</option></select></label></div>
        <div id="saPtsRes"></div></section>
      <div class="sc-grid">
      <section class="sc-box" aria-labelledby="saLoadH"><h3 class="sec" id="saLoadH">${esc(T('Load study areas'))}</h3>
        <div class="note">${esc(T('A GeoJSON file of polygons in longitude and latitude (WGS 84), up to 200 areas. It is read in this browser and never uploaded. Only each area\'s name and shape are kept.'))}${st.persistent ? '' : ' ' + esc(T('This browser keeps no stored data here (a private window, for example): study areas last until the page closes. Export the ones to keep.'))}</div>
        <label class="sc-f">${esc(T('Name of the set'))} <input type="text" id="saName" maxlength="120"></label>
        <label class="sc-f">${esc(T('Source of the polygons (an agency, a study or a team)'))} <input type="text" id="saSource" maxlength="300"></label>
        <label class="sc-f">${esc(T('Description'))} <textarea id="saDesc" rows="2" maxlength="2000"></textarea></label>
        <div class="btn-row"><label class="btn primary" for="saFile"><span class="ms-icon" aria-hidden="true">upload</span>${esc(T('Choose a GeoJSON file'))}</label><input type="file" id="saFile" accept=".geojson,.json,application/geo+json,application/json" hidden></div>
        <div class="note">${esc(T('A file exported from this view keeps its name, source and description: load it with the fields empty.'))}</div>
      </section>
      <section class="sc-box" aria-labelledby="saHowH"><h3 class="sec" id="saHowH">${esc(T('How an area is measured'))}</h3>
        <ul class="sc-ul"><li>${esc(T('Residents: the Census 2020 blocks whose center is inside the area. Far from a stop: more than an 800 m walk from a scheduled stop, along mapped roads (a straight line where a block has no mapped road nearby).'))}</li>
        <li>${esc(T('Most datasets are published by municipio. For an area they are estimated from the municipios it covers: totals by the share of each municipio\'s residents (or land) inside, rates and levels as an average weighted by the residents inside.'))}</li>
        <li>${esc(T('An estimate assumes a municipio is the same throughout. A small area inside one municipio gets that municipio\'s rate. Survey margins of error are not carried into the estimate.'))}</li></ul>
      </section></div>
      <div class="note" role="status" id="saMsg">${esc(st.msg)}</div>${st.err.length ? `<ul class="sc-err">${st.err.slice(0, 10).map(e => `<li>${esc(e)}</li>`).join('')}</ul>` : ''}
      <h3 class="sec">${esc(Tn(all.length, '{n} saved set of study areas', '{n} saved sets of study areas'))}</h3>
      ${all.length ? `<div class="eb-scroll" tabindex="0" role="region" aria-label="${esc(T('Saved study areas, scrollable'))}"><table class="ec-tbl wide"><tbody>${rows}</tbody></table></div>` : `<div class="empty">${esc(T('No study area saved yet.'))}</div>`}
      <div id="saRes"></div>`;
    body.classList.add('eb-free');
    wire(body, all);
    const set = all.find(s => s.id === st.sel); if (set) results(body, set);
  }

  function wire(body, all) {
    const say = (msg, err = []) => { st.msg = msg; st.err = err; render(body); };
    body.querySelector('#saFile').onchange = async (e) => {
      const f = e.target.files[0]; if (!f) return;
      if (f.size > 5 * 1024 * 1024) return say(T('The file is larger than 5 MB.'));
      const text = await f.text(), name = body.querySelector('#saName').value.trim(), source = body.querySelector('#saSource').value.trim(), description = body.querySelector('#saDesc').value.trim();
      let set;
      if (!name && !source && !description) {   // a file exported from this view, with its own description
        const r = ST.read(text); if (!r.set) return say(T('The file was not loaded: fix these and try again.'), r.errors);
        set = r.set;
      } else {
        const p = ST.parse(text); if (p.errors.length) return say(T('The file was not loaded: fix these and try again.'), p.errors);
        set = ST.make({ name, source, description, areas: p.areas });
        const errors = ST.check(set); if (errors.length) return say(T('Give the set a name and a source, without e-mail addresses or telephone numbers.'), errors);
      }
      await save(set); st.sel = set.id; st.res = null; st.page = 0;
      say(Tn(set.areas.length, 'Saved "{name}" with {n} area. Its summary is below.', 'Saved "{name}" with {n} areas. Their summary is below.', { name: set.name }));
    };
    // Build my region: the level, a ready-made region, the search and the ticks
    body.querySelector('#saWm').onchange = (e) => { st.wmin = +e.target.value; };
    const rl = body.querySelector('#saRegL'), rp = body.querySelector('#saRegP'), rq = body.querySelector('#saRegQ'), rlist = body.querySelector('#saRegList');
    regionsList().then(rs => { if (!body.contains(rp)) return; const lg = I18N.lang === 'es' ? 'es' : 'en'; rp.insertAdjacentHTML('beforeend', rs.map(r => `<option value="${esc(r.id)}">${esc(r.name[lg] || r.name.en)}</option>`).join('')); });
    rl.onchange = () => { st.rlev = rl.value; st.rsel.clear(); regionBox(body); };
    rp.onchange = async () => {
      const r = (await regionsList()).find(x => x.id === rp.value); rp.value = ''; if (!r) return;
      if (st.rlev === 'muni') r.ids.forEach(g => st.rsel.add(g)); else { const B = await barrios(); B.fs.forEach(f => { if (r.ids.includes(String(f.properties.geoid).slice(0, 5))) st.rsel.add(f.properties.geoid); }); }
      regionBox(body);
    };
    rq.oninput = () => { st.rq = rq.value; clearTimeout(st.rqt); st.rqt = setTimeout(() => regionBox(body), 200); };
    rlist.onchange = (e) => { const c = e.target.closest('[data-unit]'); if (!c) return; if (c.checked) st.rsel.add(c.dataset.unit); else st.rsel.delete(c.dataset.unit); regionBox(body); };
    regionBox(body);
    // Count my points: the file and the level
    body.querySelector('#saPtsF').onchange = async (e) => {
      const f = e.target.files[0]; e.target.value = ''; if (!f) return;
      if (f.size > MAX_FILE) return say(T('The file is larger than 20 MB.'));
      const r = readPoints(await f.text(), f.name); if (r.error) return say(r.error);
      if (!r.pts.length) return say(T('No point of the file is in Puerto Rico.'));
      st.pts = { ...r, file: f.name.slice(0, 80), v: (st.pts ? st.pts.v : 0) + 1 }; st.res = null; await shadePoints(false);
      say(T('Read {n} points. Their counts are below, and in the summary of the study areas.', { n: fmt(r.pts.length, 0) }));
    };
    body.querySelector('#saPtsL').onchange = async (e) => { st.plev = e.target.value; if (ptsLayer) await shadePoints(true); pointsBox(body); };
    pointsBox(body);
    const rSel = body.querySelector('#saR');
    rSel.onchange = () => { if (rSel.value) { st.r = +rSel.value; st.r0 = 0; body.querySelector('#saRo').value = ''; body.querySelector('#saRi').value = ''; } };
    body.onclick = async (e) => {
      const b = e.target.closest('[data-sum],[data-show],[data-export],[data-del],[data-extra],[data-land],[data-csv],[data-pick],[data-centre],[data-coords],[data-newaround],[data-drainpick],[data-draincentre],[data-regadd],[data-regclear],[data-ptsshade],[data-ptscsv],[data-ptsclear],[data-walkpick],[data-walkcentre],[data-crimpick],[data-crimcentre]'); if (!b) return;
      if (b.dataset.pick != null || b.dataset.centre != null || b.dataset.coords != null) {
        if (b.dataset.pick != null && st.picking) { const was = st.pickMode; stopPick(); if (was !== 'around') { st.pickMode = 'around'; startPick(body); return say(T('Click the map where the area should be centered. Press Esc to cancel.')); } return say(T('Picking a point was canceled.')); }
        const bad = readDist(body); if (bad) return say(bad);
        if (b.dataset.pick != null) { st.pickMode = 'around'; startPick(body); return say(T('Click the map where the area should be centered. Press Esc to cancel.')); }
        if (b.dataset.centre != null) { const c = map.getCenter(); return say(await addAround(c.lng, c.lat)); }
        const num = (id) => parseFloat(String(body.querySelector(id).value).replace(',', '.').trim());
        return say(await addAround(num('#saLng'), num('#saLat')));
      }
      if (b.dataset.walkpick != null) {
        if (st.picking) { const was = st.pickMode; stopPick(); if (was === 'walk') return say(T('Picking a point was canceled.')); }
        st.pickMode = 'walk'; startPick(body); return say(T('Click the map where the walk should start. Press Esc to cancel.'));
      }
      if (b.dataset.walkcentre != null) { const c = map.getCenter(); say(T('Walking the roads…')); return say(await addWalk(c.lng, c.lat)); }
      if (b.dataset.crimpick != null) {
        if (st.picking) { const was = st.pickMode; stopPick(); if (was === 'crim') return say(T('Picking a point was canceled.')); }
        st.pickMode = 'crim'; startPick(body); return say(T('Click the map where the CRIM viewer should open. Press Esc to cancel.'));
      }
      if (b.dataset.crimcentre != null) { const c = map.getCenter(); return say(openCrim(c.lng, c.lat)); }
      if (b.dataset.regadd != null) return say(await addRegion());
      if (b.dataset.regclear != null) { st.rsel.clear(); return regionBox(body); }
      if (b.dataset.ptsshade != null) { await shadePoints(!ptsLayer); return pointsBox(body); }
      if (b.dataset.ptscsv != null) return pointsCsv();
      if (b.dataset.ptsclear != null) { st.pts = null; st.res = null; await shadePoints(false); return say(T('The file of points was forgotten.')); }
      if (b.dataset.drainpick != null) {
        if (st.picking) { const was = st.pickMode; stopPick(); if (was === 'drain') return say(T('Picking a point was canceled.')); }
        st.pickMode = 'drain'; startPick(body); return say(T('Click the map where the water should end up. Press Esc to cancel.'));
      }
      if (b.dataset.draincentre != null) { const c = map.getCenter(); say(T('Tracing the land upstream…')); return say(await addDrain(c.lng, c.lat)); }
      if (b.dataset.newaround != null) { st.around = ''; return say(T('The next point starts a new set of areas around points.')); }
      if (b.dataset.extra != null) { st.extra = true; st.res = null; render(body); return; }
      if (b.dataset.land != null) { st.land = true; st.res = null; render(body); return; }
      if (b.dataset.csv != null) { csv(all.find(s => s.id === st.sel)); return; }
      const set = all.find(x => x.id === (b.dataset.sum || b.dataset.show || b.dataset.export || b.dataset.del)); if (!set) return;
      if (b.dataset.sum) { if (st.sel !== set.id) { st.sel = set.id; st.res = null; st.extra = false; st.page = 0; } render(body); return; }
      if (b.dataset.show) { show(st.shown === set.id ? null : set); render(body); return; }
      if (b.dataset.export) { const a = document.createElement('a'); a.href = URL.createObjectURL(new Blob([JSON.stringify(ST.toGeoJSON(set))], { type: 'application/geo+json' })); a.download = `pr_study_areas_${norm(set.name).replace(/[^a-z0-9]+/g, '_').slice(0, 40) || 'set'}.geojson`; a.click(); setTimeout(() => URL.revokeObjectURL(a.href), 4000); return; }
      if (b.dataset.del && window.confirm(T('Delete the study areas "{name}" from this browser?', { name: set.name }))) { await remove(set.id); if (st.shown === set.id) show(null); if (st.sel === set.id) { st.sel = ''; st.res = null; } say(T('Deleted "{name}".', { name: set.name })); }
    };
  }

  /** The areas on the 2D map: outlines with their names, the map moved to them. */
  function show(set) {
    if (layer) { map.removeLayer(layer); layer = null; }
    st.shown = set ? set.id : '';
    if (!set) return;
    // an area made of many parts (the catchments of What drains here) is drawn filled with faint edges, so it reads as one area, not as a mesh of outlines
    layer = L.geoJSON(ST.toGeoJSON(set), { interactive: true, style: (f) => f.geometry.type === 'MultiPolygon' && f.geometry.coordinates.length > 20 ? { color: '#205D7B', weight: .4, opacity: .35, fillColor: '#338CB3', fillOpacity: .3 } : { color: '#205D7B', weight: 2, dashArray: '5 4', fillColor: '#338CB3', fillOpacity: .08 },
      onEachFeature: (f, l) => l.bindTooltip(esc(f.properties.name), { sticky: true }) }).addTo(map);
    try { map.fitBounds(layer.getBounds(), { padding: [30, 30] }); } catch { /* an empty set */ }
  }

  // ── the summary of a set ───────────────────────────────────────────────
  /** The measures of every area of a set, one area at a time: the page stays responsive between areas, progress() reports to the box on screen, and the work stops (null)
      when another set or the extra measures are chosen meanwhile. */
  // The progress line of whatever summary is on screen now: a redraw while measuring replaces the box, and the run in progress keeps reporting to the new one.
  const progress = (k, n) => { const s = document.querySelector('#saRes [role="status"]'); if (s && n > 1) s.textContent = T('Measuring area {k} of {n}…', { k: k + 1, n }); };
  let running = null;   // { key, p }: the run in progress, so a redraw (Show on the map, say) waits for it instead of starting a second one
  function measureAll(set) {
    const pv = st.pts ? st.pts.v : 0, run = () => `${st.sel}|${st.extra}|${st.land}|${set.areas.length}|${st.pts ? st.pts.v : 0}`, key = `${set.id}|${st.extra}|${st.land}|${set.areas.length}|${pv}`;   // an area added to the set measures it again
    if (st.res && st.res.key === key) return Promise.resolve(st.res);
    if (running && running.key === key) return running.p;
    const p = (async () => {
      const b = await base(), x = st.extra ? await extra() : null, z = st.land ? await land() : null;
      const ctx = { blocks: b.blocks, munis: b.munis, stops: b.stops, places: x ? x.places : null, flood: x ? x.flood : null, protected: x ? x.protected : null,
        surfaces: z ? z.surfaces : null, zones: z ? z.zones : null, mine: st.pts ? st.pts.pts : null }, m = [];
      for (let k = 0; k < set.areas.length; k++) {
        if (run() !== key) return null;
        progress(k, set.areas.length);
        await new Promise(r => setTimeout(r, 0));
        m.push(ST.measure(set.areas[k].geometry, ctx));
      }
      return (st.res = { key, pop: b.pop, m, land: z });
    })();
    running = { key, p };
    const done = () => { if (running && running.p === p) running = null; };
    p.then(done, done);
    return p;
  }
  async function results(body, set) {
    const box = body.querySelector('#saRes'); if (!box) return;
    box.innerHTML = `<div class="empty" role="status">${esc(st.land ? T('Loading the summer heat images and the barrio values, and measuring…') : st.extra ? T('Loading the tourism places, flood and protected areas, and measuring…') : T('Loading the census blocks and transit stops, and measuring…'))}</div>`;
    let R; try { R = await measureAll(set); if (!R) return; } catch { box.innerHTML = `<div class="empty" role="status">${esc(T('The data for the measures could not be loaded. Check your connection and press Summarize again.'))}</div>`; return; }
    if (st.sel !== set.id || !body.contains(box)) return;   // another set was chosen meanwhile
    const A = set.areas, pages = Math.ceil(A.length / PAGE); if (st.page >= pages) st.page = 0;
    const p0 = st.page * PAGE, on = (list) => list.slice(p0, p0 + PAGE), shown = on(A);
    const head = `<tr><th scope="col">${esc(T('Measure'))}</th>${shown.map(a => `<th scope="col" class="num">${esc(a.name)}</th>`).join('')}</tr>`;
    const line = (label, f, d = 0, suf = '') => `<tr><th scope="row">${esc(label)}</th>${on(R.m).map(m => { const v = f(m); return `<td class="num">${v == null ? '—' : fmt(v, d) + suf}</td>`; }).join('')}</tr>`;
    const picker = pages > 1 ? `<div class="eb-tools"><label>${esc(T('Areas shown'))} <select id="saP">${Array.from({ length: pages }, (_, k) => `<option value="${k}"${k === st.page ? ' selected' : ''}>${k * PAGE + 1}–${Math.min(A.length, (k + 1) * PAGE)} ${esc(T('of {n}', { n: A.length }))}</option>`).join('')}</select></label><span class="note">${esc(T('The CSV holds every area.'))}</span></div>` : '';
    const held = [line(T('Area (km²)'), m => m.km2, 1), line(T('Residents (Census 2020, by block)'), m => m.residents), line(T('of them, more than an 800 m walk from a scheduled stop'), m => m.far),
      line(T('Scheduled transit stops'), m => m.stops)];
    if (st.extra) held.push(line(T('Tourism places'), m => m.places), line(T('% of the land in a FEMA flood hazard area'), m => m.flood, 1, '%'), line(T('% of the land in a protected area'), m => m.protected, 1, '%'));
    // a measure with its coverage: an asterisk, and the share in the tooltip, where part of the area's land has no value
    const lineC = (label, f, d = 0, suf = '') => `<tr><th scope="row">${esc(label)}</th>${on(R.m).map(m => { const o = f(m); if (!o || o.value == null) return '<td class="num">—</td>'; const part = o.cover < 0.999; return `<td class="num"${part ? ` title="${esc(T('{pct}% of the area has a value', { pct: fmt(o.cover * 100, 0) }))}"` : ''}>${fmt(o.value, d) + suf}${part ? '*' : ''}</td>`; }).join('')}</tr>`;
    const surfV = (k) => (m) => m.surf && m.surf[k] && { value: m.surf[k].mean, cover: m.surf[k].cover }, zoneV = (k) => (m) => m.zone && m.zone[k];
    if (st.land) held.push(lineC(T('Surface temperature, summer mornings (°C, mean of the land)'), surfV('day'), 1), lineC(T('Surface temperature, summer nights (°C, mean of the land)'), surfV('night'), 1),
      lineC(T('Greenness (NDVI), estimated from the barrios covered'), zoneV('veg'), 2), lineC(T('% of the land highly susceptible to landslides, estimated from the barrios covered'), zoneV('slide'), 1, '%'));
    if (st.pts) held.push(`<tr><th scope="row">${esc(T('Your points ({file})', { file: st.pts.file }))}</th>${on(R.m).map(m => `<td class="num">${esc(shownCount(m.mine))}</td>`).join('')}</tr>`);
    const ys = [...E.years()].sort((p, q) => q - p), q = norm(st.q);
    const ds = E.list().filter(v => !q || norm(T(v.label)).includes(q) || norm(T(v.group || '')).includes(q));
    const est = ds.map(v => ({ v, e: R.m.map(m => ST.estimate(E, m, v.key, st.y, R.pop)) })).filter(r => r.e.some(Boolean));
    const L0 = (v) => ({ key: v.key, norm: 'value' });
    const cell = (v, e) => e == null ? '<td class="num">—</td>' : `<td class="num"${e.coverage < 0.999 ? ` title="${esc(T('{pct}% of the area has a value', { pct: fmt(e.coverage * 100, 0) }))}"` : ''}>${esc(E.fmt(L0(v), e.value))}${e.coverage < 0.999 ? '*' : ''}</td>`;
    const period = (v, e) => { const f = e.find(Boolean); return f ? E.chip(L0(v), { y: f.y, exact: f.exact, early: f.early }) : ''; };
    const how = (v, e) => { const ms = [...new Set(e.filter(Boolean).map(x => x.method))]; return ms.map(k => T(METHOD[k])).join('; ') + (v.moe ? ' · ' + T('survey: margins of error not carried') : ''); };
    box.innerHTML = `<h3 class="sec">${esc(T('What the areas of "{name}" hold', { name: set.name }))}</h3>${picker}
      <div class="eb-scroll" tabindex="0" role="region" aria-label="${esc(T('What each area holds, scrollable'))}"><table class="ec-tbl wide"><thead>${head}</thead><tbody>${held.join('')}</tbody></table></div>
      <div class="eb-tools sa-dl"><label>${esc(T('Download what\'s inside'))} <select id="saDl">${DL.map(d => `<option value="${d.id}"${d.id === st.dl ? ' selected' : ''}>${esc(T(d.label))}</option>`).join('')}</select></label>
        <select id="saDlF" aria-label="${esc(T('Format'))}"><option value="geojson"${st.dlf !== 'csv' ? ' selected' : ''}>GeoJSON</option><option value="csv"${st.dlf === 'csv' ? ' selected' : ''}>CSV</option></select>
        <button type="button" class="btn small" data-dl><span class="ms-icon" aria-hidden="true">download</span>${esc(T('Download'))}</button><span class="note" id="saDlN" role="status"></span></div>
      <div class="note">${esc(T('For every area of the set: the points of the dataset inside it, cut at its edge, or the outlines that overlap it, whole. Each row names its area and its source; licenses and credits are in the data dictionary.'))}</div>
      ${st.extra ? `<div class="note">${esc(T('Holiday rentals and rented units named by an address are counted by municipio, not drawn, so they are not in the tourism places count.'))}</div>` : ''}
      ${st.land ? `<div class="note">${esc(T('Surface temperature is measured on the summer images at the same grid of points as the flood share (zonal statistics): Landsat at 60 m in the morning, ECOSTRESS at night. It is the temperature of the ground, not the air. Greenness and landslide susceptibility are the barrio values ({veg} and {slide}) averaged, weighted by each barrio\'s land inside the area: estimates that take a barrio as the same throughout. An asterisk marks an area where part of the land has no value: the heat images leave out Mona and Desecheo, and the landslide map covers the main island only.', { veg: R.land.years.veg, slide: R.land.years.slide }))}</div>` : ''}
      ${st.extra && st.land ? '' : `<div class="btn-row">${st.extra ? '' : `<button type="button" class="btn small" data-extra>${esc(T('Also count tourism places and measure flood and protected areas (downloads about {mb} MB)', { mb: fmt((gz('places.json') + gz('flood.geojson') + gz('protected.geojson')) / 1048576 || 5.5, 1) }))}</button>`}${st.land ? '' : `<button type="button" class="btn small" data-land>${esc(T('Also measure surface heat, greenness and landslide susceptibility (downloads about {mb} MB)', { mb: fmt((gz('heat_surface.png') + gz('night_heat_surface.png') + gz('barrios.geojson') + gz('vegetation_barrio.json') + gz('landslide_barrio.json')) / 1048576 || 3, 1) }))}</button>`}</div>`}
      <h3 class="sec">${esc(T('Every dataset by municipio, estimated for each area'))}</h3>
      <div class="eb-tools"><label>${esc(T('Year'))} <select id="saY"><option value="">${esc(T('Latest'))}</option>${ys.map(y => `<option${y === st.y ? ' selected' : ''}>${y}</option>`).join('')}</select></label>
        <label>${esc(T('Find a dataset'))} <input type="search" id="saQ" value="${esc(st.q)}"></label>
        <button type="button" class="btn small" data-csv><span class="ms-icon" aria-hidden="true">download</span>${esc(T('Download CSV'))}</button></div>
      <div class="ix-warn" role="note"><span class="ms-icon" aria-hidden="true">info</span>${esc(T('These are estimates from municipio values, not measurements of the areas. An asterisk marks an area where some of the municipios it covers have no value.'))}</div>
      <div class="eb-scroll tall" tabindex="0" role="region" aria-label="${esc(T('Estimates for each area, scrollable'))}"><table class="ec-tbl wide"><thead><tr><th scope="col">${esc(T('Dataset'))}</th><th scope="col">${esc(T('Period'))}</th>${shown.map(a => `<th scope="col" class="num">${esc(a.name)}</th>`).join('')}<th scope="col">${esc(T('Method'))}</th></tr></thead>
      <tbody>${est.map(({ v, e }) => `<tr><th scope="row">${esc(T(v.label))}</th><td>${esc(period(v, e))}</td>${on(e).map(x => cell(v, x)).join('')}<td class="sa-how">${esc(how(v, on(e)))}</td></tr>`).join('')}</tbody></table></div>
      <div class="note">${esc(Tn(est.length, '{n} dataset with a value for these areas.', '{n} datasets with a value for these areas.'))}</div>`;
    st.csv = { set, A, held: R.m, est, land: R.land };
    box.querySelector('#saDl').onchange = e => { st.dl = e.target.value; };
    box.querySelector('#saDlF').onchange = e => { st.dlf = e.target.value; };
    box.querySelector('[data-dl]').onclick = async () => { const n = box.querySelector('#saDlN'); n.textContent = T('Preparing the file…'); n.textContent = await downloadInside(set, box.querySelector('#saDl').value, box.querySelector('#saDlF').value); };
    box.querySelector('#saY').onchange = e => { st.y = e.target.value ? +e.target.value : null; results(body, set); };
    if (box.querySelector('#saP')) box.querySelector('#saP').onchange = e => { st.page = +e.target.value; results(body, set); };
    box.querySelector('#saQ').oninput = e => { st.q = e.target.value; clearTimeout(st.qt); st.qt = setTimeout(() => { results(body, set).then(() => { const i = box.querySelector('#saQ'); if (i) { i.focus(); i.setSelectionRange(i.value.length, i.value.length); } }); }, 250); };
  }
  function csv(set) {
    const c = st.csv; if (!c || c.set !== set) return;
    const names = c.A.map(a => a.name), rows = [
      [T('Area (km²)'), '', ...c.held.map(m => +m.km2.toFixed(3)), ''], [T('Residents (Census 2020, by block)'), '', ...c.held.map(m => m.residents), T('Census 2020 blocks whose center is inside')],
      [T('of them, more than an 800 m walk from a scheduled stop'), '', ...c.held.map(m => m.far), ''], [T('Scheduled transit stops'), '', ...c.held.map(m => m.stops), ''],
      ...(st.extra ? [[T('Tourism places'), '', ...c.held.map(m => m.places), ''], [T('% of the land in a FEMA flood hazard area'), '', ...c.held.map(m => m.flood == null ? null : +m.flood.toFixed(2)), T('share of a grid of points on land')], [T('% of the land in a protected area'), '', ...c.held.map(m => m.protected == null ? null : +m.protected.toFixed(2)), T('share of a grid of points on land')]] : []),
      ...(st.pts ? [[T('Your points ({file})', { file: st.pts.file }), '', ...c.held.map(m => m.mine == null ? null : m.mine > 0 && m.mine < MIN_SHOWN ? T('fewer than {n}', { n: MIN_SHOWN }) : m.mine), T('points of your file inside (counts under 5 not shown)')]] : []),
      ...(st.land && c.land ? [
        [T('Surface temperature, summer mornings (°C, mean of the land)'), c.land.surfaces[0].meta.summers.join('–'), ...c.held.map(m => m.surf && m.surf.day.mean != null ? +m.surf.day.mean.toFixed(2) : null), T('mean of a grid of points on land, Landsat 60 m image')],
        [T('Surface temperature, summer nights (°C, mean of the land)'), c.land.surfaces[1].meta.summers.join('–'), ...c.held.map(m => m.surf && m.surf.night.mean != null ? +m.surf.night.mean.toFixed(2) : null), T('mean of a grid of points on land, ECOSTRESS image')],
        [T('Greenness (NDVI), estimated from the barrios covered'), c.land.years.veg, ...c.held.map(m => m.zone && m.zone.veg.value != null ? +m.zone.veg.value.toFixed(3) : null), T('barrio values weighted by their land inside (estimate)')],
        [T('% of the land highly susceptible to landslides, estimated from the barrios covered'), c.land.years.slide, ...c.held.map(m => m.zone && m.zone.slide.value != null ? +m.zone.slide.value.toFixed(2) : null), T('barrio values weighted by their land inside (estimate)')]] : []),
      ...c.est.map(({ v, e }) => [T(v.label), (e.find(Boolean) || {}).y, ...e.map(x => x == null ? null : +x.value.toPrecision(8)), [...new Set(e.filter(Boolean).map(x => T(METHOD[x.method])))].join('; ') + (v.moe ? ' · ' + T('survey: margins of error not carried') : '')]),
    ];
    ecSaveCsv(`pr_study_areas_${norm(set.name).replace(/[^a-z0-9]+/g, '_').slice(0, 40) || 'set'}.csv`, [T('Measure'), T('Year'), ...names, T('Method')], rows);
  }
  return { render, list, save, remove, show, addDrawn };
})();
