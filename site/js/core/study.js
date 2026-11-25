/* PR Data Observatory core: study areas (plan item 16, section C4; docs/study-areas.md). No page state: text and data in, objects out.

     Study.parse(text)                    a GeoJSON file of polygons -> { areas: [{ name, geometry }], meta, errors }; meta is the "study" member of a file this page exported
     Study.make({ name, description, source, areas })   a set of study areas as it is stored (IndexedDB) and exported
     Study.check(obj) / Study.read(text)  problems with a stored or imported set ([] when none); read parses a file and checks it
     Study.toGeoJSON(set)                 the file "Export" writes: a FeatureCollection any GIS opens, with the set's description in a "study" member
     Study.inside(g, x, y), Study.areaKm2(g), Study.sample(g, n)   point in polygon, area, and a grid of points inside (longitude, latitude)
     Study.ring(lng, lat, r, r0)          the area around a point (a buffer, GIS tools step 1, docs/gis-tools-proposal-2026-11.md): a circle of r meters, or the ring from r0 to r meters
     Study.raster(steps, W, H, bounds, low, high, n)   a reader of a surface image's steps (Core.surfscale): (lng, lat) -> its value, or null
     Study.locate(list)                   (lng, lat) -> the index of the polygon of the list that holds the point, or -1 (a grid index, built once per list)
     Study.upstream(dn, i, via)           the indices that drain to i through a network where dn[k] is the next one downstream (-1 at an outlet) and via[k] (optional)
                                          lists the reaches a minor branch k splits from; i first
     Study.merge(geoms)                   one MultiPolygon of a list of polygons (no dissolve: the parts are kept, which the measures handle)
     Study.points(text, name, max)        the points of a CSV or GeoJSON file, with the rows that have none or fall outside Puerto Rico
     Study.overlaps(g, geoms)             the indices of the polygons that overlap area g (whole outlines: no clipping)
     Study.walkArea(roads, lng, lat, m)   the area within a walk of m meters along mapped roads (js/roads.js's graph), as cells of 25 m
     Study.measure(g, ctx)                what one area holds: { km2, residents, far, stops, munis: [{ i, km2, residents }], places?, flood?, protected?, surf?, zone? }
     Study.estimate(E, m, key, year, pop) one dataset of the engine for one area, from the values of the municipios it covers: { value, y, method, coverage }

   Everything runs in the browser: an area is never uploaded. Residents are counted by census block centroid (Census 2020). A dataset published by municipio
   is estimated for an area from the municipios it covers, and the result says how (method). Only an area's name and geometry are kept from a file. */
(function (name, root, factory) {
  const dep = (n) => (typeof module === 'object' && module.exports ? require('./' + n + '.js') : root.Core[n]);
  const api = factory(root, dep);
  if (typeof module === 'object' && module.exports) module.exports = api; else { root.Core = root.Core || {}; root.Core[name] = api; }
})('study', typeof window !== 'undefined' ? window : globalThis, function (root, dep) {
  'use strict';
  const VERSION = 1, MAX_TEXT = 5 * 1024 * 1024, MAX_AREAS = 200, MAX_POINTS = 100000, MAX_NAME = 80, MAX_SET = 120, MAX_DESC = 2000, MAX_SOURCE = 300;
  const BOX = [-68.1, 17.5, -65.0, 18.8];   // Puerto Rico with Mona, Vieques and Culebra, in longitude and latitude
  const FAR_M = 800;                        // a block is "far from a scheduled stop" beyond 800 m, as on the map's transit view
  const personal = (s) => dep('scenario').personal(String(s));
  const clean = (s, max) => String(s == null ? '' : s).replace(/[\u0000-\u001f\u007f]/g, ' ').trim().slice(0, max);
  const str = (x, max) => typeof x === 'string' && x.length <= max;
  const NAME_KEYS = ['name', 'Name', 'NAME', 'nombre', 'Nombre', 'NOMBRE', 'label', 'title'];

  // ── geometry ───────────────────────────────────────────────────────────
  const polys = (g) => g.type === 'Polygon' ? [g.coordinates] : g.coordinates;   // MultiPolygon: a list of polygons; a polygon: a list of rings (the first is the outer edge)
  const bboxCache = new WeakMap();
  function bbox(g) {
    let b = bboxCache.get(g); if (b) return b;
    b = [Infinity, Infinity, -Infinity, -Infinity];
    for (const p of polys(g)) for (const [x, y] of p[0]) { if (x < b[0]) b[0] = x; if (y < b[1]) b[1] = y; if (x > b[2]) b[2] = x; if (y > b[3]) b[3] = y; }
    bboxCache.set(g, b); return b;
  }
  // Point in ring by crossings. Only the edges that span the point's latitude can cross, so a large ring (a municipio, a flood zone: thousands of corners) is cut once
  // into latitude bands, each listing the edges that reach it, and a point is tested against its band's edges only. The answer is the same as testing every edge.
  const bandCache = new WeakMap();
  function bands(r) {
    let ix = bandCache.get(r); if (ix) return ix;
    let y0 = Infinity, y1 = -Infinity; for (const p of r) { if (p[1] < y0) y0 = p[1]; if (p[1] > y1) y1 = p[1]; }
    const B = Math.ceil(r.length / 8), h = (y1 - y0) / B || 1, list = Array.from({ length: B }, () => []);
    for (let i = 0; i < r.length; i++) {
      const j = i === 0 ? r.length - 1 : i - 1, lo = Math.min(r[i][1], r[j][1]), hi = Math.max(r[i][1], r[j][1]);
      for (let k = Math.max(0, Math.floor((lo - y0) / h)); k <= Math.min(B - 1, Math.floor((hi - y0) / h)); k++) list[k].push(i);
    }
    ix = { y0, y1, h, B, list }; bandCache.set(r, ix); return ix;
  }
  function inRing(r, x, y) {
    let c = false;
    const cross = (i, j) => { const xi = r[i][0], yi = r[i][1], xj = r[j][0], yj = r[j][1]; if ((yi > y) !== (yj > y) && x < (xj - xi) * (y - yi) / (yj - yi) + xi) c = !c; };
    if (r.length < 64) { for (let i = 0, j = r.length - 1; i < r.length; j = i++) cross(i, j); return c; }
    const ix = bands(r); if (y < ix.y0 || y > ix.y1) return false;
    for (const i of ix.list[Math.min(ix.B - 1, Math.floor((y - ix.y0) / ix.h))]) cross(i, i === 0 ? r.length - 1 : i - 1);
    return c;
  }
  const partBox = new WeakMap();
  function boxOf(ring) { let b = partBox.get(ring); if (!b) { b = [Infinity, Infinity, -Infinity, -Infinity]; for (const [x, y] of ring) { if (x < b[0]) b[0] = x; if (y < b[1]) b[1] = y; if (x > b[2]) b[2] = x; if (y > b[3]) b[3] = y; } partBox.set(ring, b); } return b; }
  function inPart(p, x, y) { const b = boxOf(p[0]); if (x < b[0] || x > b[2] || y < b[1] || y > b[3]) return false; if (!inRing(p[0], x, y)) return false; for (let h = 1; h < p.length; h++) if (inRing(p[h], x, y)) return false; return true; }
  function inside(g, x, y) {
    const b = bbox(g); if (x < b[0] || x > b[2] || y < b[1] || y > b[3]) return false;
    for (const p of polys(g)) if (inPart(p, x, y)) return true;
    return false;
  }
  function ringKm2(r, kx) { let s = 0; for (let i = 0, j = r.length - 1; i < r.length; j = i++) s += (r[j][0] * kx) * (r[i][1] * 110.574) - (r[i][0] * kx) * (r[j][1] * 110.574); return Math.abs(s) / 2; }
  /** Area in km², on a flat projection at the area's latitude (good to well under 1% across Puerto Rico). */
  function areaKm2(g) {
    const b = bbox(g), kx = 111.32 * Math.cos((b[1] + b[3]) / 2 * Math.PI / 180);
    return polys(g).reduce((a, p) => a + Math.max(0, ringKm2(p[0], kx) - p.slice(1).reduce((h, r) => h + ringKm2(r, kx), 0)), 0);
  }
  /** About n points on a square grid inside the area, and the km² each stands for (the area divided by the points, so they add up to it). */
  function sample(g, n = 8000) {
    const b = bbox(g), lat = (b[1] + b[3]) / 2, kx = 111.32 * Math.cos(lat * Math.PI / 180), boxKm2 = (b[2] - b[0]) * kx * (b[3] - b[1]) * 110.574;
    const c = Math.sqrt(Math.max(boxKm2, 1e-6) / n), dx = c / kx, dy = c / 110.574, pts = [];
    for (let y = b[1] + dy / 2; y < b[3]; y += dy) for (let x = b[0] + dx / 2; x < b[2]; x += dx) if (inside(g, x, y)) pts.push([x, y]);
    if (!pts.length) { const r = polys(g)[0][0]; pts.push([r.reduce((a, p) => a + p[0], 0) / r.length, r.reduce((a, p) => a + p[1], 0) / r.length]); }   // smaller than one cell
    return { pts, cellKm2: areaKm2(g) / pts.length };
  }

  /** Which of these polygons holds the point (its index, or -1), with the polygons bucketed on a grid of 0.05° so a point is tested only against those near it.
      anyInside(list) is the same test as true or false. Both are built once for a list and kept. */
  const whichCache = new WeakMap();
  function which(list) {
    let f = whichCache.get(list); if (f) return f;
    const C = 0.05, cells = new Map(), key = (i, j) => i * 100000 + j, parts = [];   // each part of a MultiPolygon on its own: one protected area can lie in pieces across the island
    list.forEach((g, k) => { if (!g) return; for (const p of polys(g)) {
      const b = boxOf(p[0]), n = parts.push([k, p]) - 1;
      for (let i = Math.floor(b[0] / C); i <= Math.floor(b[2] / C); i++) for (let j = Math.floor(b[1] / C); j <= Math.floor(b[3] / C); j++) { const q = key(i, j); if (!cells.has(q)) cells.set(q, []); cells.get(q).push(n); }
    } });
    f = (x, y) => { for (const n of cells.get(key(Math.floor(x / C), Math.floor(y / C))) || []) if (inPart(parts[n][1], x, y)) return parts[n][0]; return -1; };
    whichCache.set(list, f); return f;
  }
  const anyInside = (list) => { const w = which(list); return (x, y) => w(x, y) >= 0; };

  /** The area around a point: a circle of r meters, or with r0 > 0 the ring between r0 and r meters (a hole of r0), as a Polygon of n corners on the flat projection
      at the point's latitude. Each edge is pushed out a little (by the ratio of a circle's area to its n-gon's) so the polygon's area equals the circle's: with 128 corners
      the plain polygon would be 0.04% short. Corners are rounded to 6 decimals (about 0.1 m). */
  function ring(lng, lat, r, r0 = 0, n = 128) {
    const kx = 111320 * Math.cos(lat * Math.PI / 180), ky = 110574, eq = Math.sqrt(2 * Math.PI / (n * Math.sin(2 * Math.PI / n)));
    const circle = (m, dir) => { const c = []; for (let k = 0; k < n; k++) { const a = dir * 2 * Math.PI * k / n; c.push([+(lng + m * eq * Math.cos(a) / kx).toFixed(6), +(lat + m * eq * Math.sin(a) / ky).toFixed(6)]); } c.push(c[0].slice()); return c; };
    return { type: 'Polygon', coordinates: r0 > 0 ? [circle(r, 1), circle(r0, -1)] : [circle(r, 1)] };
  }
  /** A reader of a surface image (Core.surfscale.open: its steps, one per pixel, 0 = no value; the image spans bounds [w, s, e, n] in Web Mercator): the value of the
      pixel under (lng, lat), its step's place on the scale from low to high (n steps), or null outside the image or where it has no value. */
  function raster(steps, W, H, bounds, low, high, n = 64) {
    const [w, s, e, nn] = bounds, my = (la) => Math.log(Math.tan(Math.PI / 4 + la * Math.PI / 360)), y0 = my(s), y1 = my(nn);
    return (x, y) => {
      if (!(x >= w && x < e && y >= s && y < nn)) return null;
      const c = Math.min(W - 1, Math.floor((x - w) / (e - w) * W)), r = Math.min(H - 1, Math.max(0, Math.floor((y1 - my(y)) / (y1 - y0) * H))), k = steps[r * W + c];
      return k ? low + (k - 1) / (n - 1) * (high - low) : null;
    };
  }

  // ── reading a file ─────────────────────────────────────────────────────
  /** Problems with one geometry, and its corrected copy (open rings closed, a third coordinate dropped). */
  function cleanGeometry(g, label, count) {
    const errs = [];
    if (!g || (g.type !== 'Polygon' && g.type !== 'MultiPolygon') || !Array.isArray(g.coordinates)) return { errs: [`${label}: ${g && g.type ? `a ${g.type}` : 'no geometry'}, not a polygon`] };
    const list = g.type === 'Polygon' ? [g.coordinates] : g.coordinates, out = [];
    let projected = false;
    for (const p of list) {
      if (!Array.isArray(p) || !p.length) { errs.push(`${label}: an empty polygon`); continue; }
      const rings = [];
      for (const r of p) {
        if (!Array.isArray(r)) { errs.push(`${label}: a ring that is not a list of points`); continue; }
        const pts = [];
        for (const q of r) {
          if (!Array.isArray(q) || typeof q[0] !== 'number' || typeof q[1] !== 'number' || !isFinite(q[0]) || !isFinite(q[1])) { errs.push(`${label}: a point that is not two numbers`); break; }
          if (Math.abs(q[0]) > 180 || Math.abs(q[1]) > 90) projected = true;
          else if (q[0] < BOX[0] || q[0] > BOX[2] || q[1] < BOX[1] || q[1] > BOX[3]) { errs.push(`${label}: a point outside Puerto Rico (${q[0]}, ${q[1]})`); break; }
          pts.push([q[0], q[1]]);
        }
        if (pts.length && (pts[0][0] !== pts[pts.length - 1][0] || pts[0][1] !== pts[pts.length - 1][1])) pts.push(pts[0].slice());
        if (pts.length < 4) errs.push(`${label}: a ring with fewer than three corners`);
        count.n += pts.length; rings.push(pts);
      }
      out.push(rings);
    }
    if (projected) return { errs: [`${label}: the coordinates are not longitude and latitude; save the file in WGS 84 (EPSG:4326)`] };
    if (errs.length) return { errs: errs.slice(0, 3) };
    const geometry = out.length === 1 ? { type: 'Polygon', coordinates: out[0] } : { type: 'MultiPolygon', coordinates: out };
    if (!(areaKm2(geometry) > 0)) return { errs: [`${label}: the polygon has no area`] };
    return { errs: [], geometry };
  }
  function parse(text) {
    const errors = [], areas = [];
    text = String(text || '');
    if (text.length > MAX_TEXT) return { areas, meta: null, errors: ['the file is larger than 5 MB'] };
    let j; try { j = JSON.parse(text.replace(/^﻿/, '')); } catch { return { areas, meta: null, errors: ['the file is not GeoJSON (not valid JSON)'] }; }
    const feats = !j || typeof j !== 'object' ? null : j.type === 'FeatureCollection' && Array.isArray(j.features) ? j.features : j.type === 'Feature' ? [j] : (j.type === 'Polygon' || j.type === 'MultiPolygon') ? [{ type: 'Feature', properties: {}, geometry: j }] : null;
    if (!feats) return { areas, meta: null, errors: ['a study area file is a GeoJSON FeatureCollection of polygons'] };
    if (!feats.length) return { areas, meta: null, errors: ['the file holds no area'] };
    if (feats.length > MAX_AREAS) return { areas, meta: null, errors: [`more than ${MAX_AREAS} areas`] };
    const count = { n: 0 }, seen = new Map();
    feats.forEach((f, k) => {
      const props = (f && f.properties) || {}, raw = NAME_KEYS.map(n => props[n]).find(v => typeof v === 'string' || typeof v === 'number');
      let nm = clean(raw == null ? '' : raw, MAX_NAME) || `Area ${k + 1}`;
      const label = `area ${k + 1} (${nm})`;
      if (personal(nm)) { errors.push(`${label}: the name holds an e-mail address or a telephone number`); return; }
      const r = cleanGeometry(f && f.geometry, label, count);
      if (r.errs.length) { errors.push(...r.errs); return; }
      const d = seen.get(nm) || 0; seen.set(nm, d + 1); if (d) nm = `${nm} (${d + 1})`;
      areas.push({ name: nm, geometry: r.geometry });
    });
    if (count.n > MAX_POINTS) errors.push(`more than ${MAX_POINTS.toLocaleString('en-US')} points: simplify the polygons first`);
    const m = j.study && typeof j.study === 'object' ? j.study : null;
    return { areas: errors.length ? [] : areas, meta: m, errors: errors.slice(0, 50) };
  }

  // ── a set of areas: stored, exported, imported ─────────────────────────
  function uid() { return 'st-' + Date.now().toString(36) + '-' + Math.random().toString(36).slice(2, 8); }
  function make(o) {
    return { v: VERSION, id: o.id || uid(), name: clean(o.name, MAX_SET), description: clean(o.description, MAX_DESC), source: clean(o.source, MAX_SOURCE), created: o.created || new Date().toISOString(),
      areas: (o.areas || []).map(a => ({ name: clean(a.name, MAX_NAME), geometry: a.geometry })) };
  }
  function check(s) {
    const P = [];
    if (!s || typeof s !== 'object' || Array.isArray(s)) return ['not a set of study areas'];
    if (s.v !== VERSION) P.push(`version ${s.v} is not ${VERSION}`);
    if (!s.id || !str(s.id, 80)) P.push('no id');
    if (!s.name || !str(s.name, MAX_SET)) P.push('no name');
    if (!str(s.description, MAX_DESC)) P.push('the description is not a text');
    if (!s.source || !str(s.source, MAX_SOURCE)) P.push('no source: say where the polygons come from');
    if (typeof s.created !== 'string' || !/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?Z$/.test(s.created)) P.push('no date of creation');
    for (const f of ['name', 'description', 'source']) if (typeof s[f] === 'string' && personal(s[f])) P.push(`${f} holds an e-mail address or a telephone number`);
    if (!Array.isArray(s.areas) || !s.areas.length || s.areas.length > MAX_AREAS) { P.push(`areas are not a list of 1 to ${MAX_AREAS}`); return P; }
    const count = { n: 0 };
    s.areas.forEach((a, k) => {
      if (!a || !str(a.name, MAX_NAME) || !a.name) { P.push(`area ${k + 1} has no name`); return; }
      if (personal(a.name)) P.push(`area ${k + 1}: the name holds an e-mail address or a telephone number`);
      const r = cleanGeometry(a.geometry, `area ${k + 1}`, count); P.push(...r.errs);
    });
    if (count.n > MAX_POINTS) P.push(`more than ${MAX_POINTS} points`);
    return P.slice(0, 50);
  }
  function toGeoJSON(s) {
    return { type: 'FeatureCollection', study: { v: s.v, id: s.id, name: s.name, description: s.description, source: s.source, created: s.created },
      features: s.areas.map(a => ({ type: 'Feature', properties: { name: a.name }, geometry: a.geometry })) };
  }
  /** A file exported by this page (it carries its name, description and source), checked whole; other GeoJSON goes through parse and the form. */
  function read(text) {
    const r = parse(text); if (r.errors.length) return { set: null, errors: r.errors };
    if (!r.meta) return { set: null, errors: ['the file has no "study" description: load it as a new set and give its name and source'] };
    const m = r.meta, s = make({ id: str(m.id, 80) && /^st-[a-z0-9-]+$/.test(m.id) ? m.id : null, name: m.name, description: m.description, source: m.source, created: str(m.created, 40) ? m.created : null, areas: r.areas });
    const errors = check(s);
    return { set: errors.length ? null : s, errors };
  }

  // ── what an area holds ─────────────────────────────────────────────────
  /** ctx: { blocks: [[lng, lat, residents, meters to the nearest scheduled stop]], munis: [geometry, in the engine's order of places], stops: [[lng, lat]],
             places: [[lng, lat]] | null, mine: [[lng, lat]] | null (the visitor's own points), flood: [geometry] | null, protected: [geometry] | null,
             surfaces: [{ key, at: (lng, lat) -> value | null }] | null, zones: { geoms: [geometry], vals: { key: [value | null, one per geometry] } } | null }.
             The last five are measured only when given; flood is the special flood hazard areas only (FEMA's A and V zones, not zone X). Shares are of the area's land:
             grid points in no municipio (sea, lagoons outside the boundaries) are left out.
             surf[key]: { mean, cover }: the mean of the surface's values at the grid points on land that have one (zonal statistics), and the share of the land points that do.
             zone[key]: { value, cover }: the zones' values (barrios, say) averaged, weighted by each zone's land inside the area (an estimate: a zone is taken as the same
             throughout), and the share of the land in zones that have a value. */
  function measure(g, ctx) {
    const km2 = areaKm2(g), b = bbox(g), muniOf = which(ctx.munis);
    const by = new Map(), row = (i) => { if (!by.has(i)) by.set(i, { i, km2: 0, residents: 0 }); return by.get(i); };
    let residents = 0, far = 0;
    for (const k of ctx.blocks) {
      if (k[0] < b[0] || k[0] > b[2] || k[1] < b[1] || k[1] > b[3] || !inside(g, k[0], k[1])) continue;
      residents += k[2]; if ((k.length > 4 ? k[4] : k[3]) > FAR_M) far += k[2];   // walked along mapped roads when the blocks file has it (network.py coverage), else the straight line
      const i = muniOf(k[0], k[1]); if (i >= 0) row(i).residents += k[2];
    }
    const { pts, cellKm2 } = sample(g), inFlood = ctx.flood && anyInside(ctx.flood), inProt = ctx.protected && anyInside(ctx.protected);
    const surfs = ctx.surfaces || [], sSum = surfs.map(() => 0), sN = surfs.map(() => 0), zoneOf = ctx.zones && which(ctx.zones.geoms), zl = new Map();
    let fl = 0, pr = 0, land = 0;
    for (const [x, y] of pts) {
      const i = muniOf(x, y); if (i < 0) continue;   // water, or outside every municipio: the shares below are of the land
      row(i).km2 += cellKm2; land++;
      if (inFlood && inFlood(x, y)) fl++;
      if (inProt && inProt(x, y)) pr++;
      for (let k = 0; k < surfs.length; k++) { const v = surfs[k].at(x, y); if (v != null && isFinite(v)) { sSum[k] += v; sN[k]++; } }
      if (zoneOf) { const z = zoneOf(x, y); if (z >= 0) zl.set(z, (zl.get(z) || 0) + 1); }
    }
    const count = (list) => list.reduce((a, p) => a + (p[0] >= b[0] && p[0] <= b[2] && p[1] >= b[1] && p[1] <= b[3] && inside(g, p[0], p[1]) ? 1 : 0), 0);
    const out = { km2, landKm2: land * cellKm2, residents, far, stops: count(ctx.stops || []), munis: [...by.values()].sort((p, q) => q.km2 - p.km2), samples: pts.length };
    if (ctx.places) out.places = count(ctx.places);
    if (ctx.mine) out.mine = count(ctx.mine);   // the points of a visitor's file (Count my points): a count, never the points
    if (ctx.flood) out.flood = land ? fl / land * 100 : null;          // % of the area's land
    if (ctx.protected) out.protected = land ? pr / land * 100 : null;
    if (surfs.length) { out.surf = {}; surfs.forEach((sf, k) => { out.surf[sf.key] = { mean: sN[k] ? sSum[k] / sN[k] : null, cover: land ? sN[k] / land : 0 }; }); }
    if (ctx.zones) {
      out.zone = {};
      for (const [key, vals] of Object.entries(ctx.zones.vals)) {
        let w = 0, wv = 0;
        for (const [z, c] of zl) { const v = vals[z]; if (v != null && isFinite(v)) { w += c; wv += c * v; } }
        out.zone[key] = { value: w ? wv / w : null, cover: land ? w / land : 0 };
      }
    }
    return out;
  }

  /** One dataset for one area, from the municipios the area covers (m = measure()). pop: residents of each municipio (Census 2020, the engine's order).
      Counts and dollar totals: each municipio's value times the share of its residents inside the area (of its land, for totals measured in km²), added up.
      Rates, ratios and levels: the municipios' values averaged, weighted by the residents of each inside the area (by land when the area has no residents).
      method: 'whole' (whole municipios: their exact sum, plus the edge slivers shared as usual), 'residents', 'land', 'avg-residents', 'avg-land'.
      coverage: the share of the weight with a value (1 = all). */
  function estimate(E, m, key, year, pop) {
    const v = E.V[key]; if (!v || !m.munis.length) return null;
    const r = E.resolve(key, year); if (r.y == null) return null;
    const ck = `study|${key}|${r.y}`, a = E.cache[ck] !== undefined ? E.cache[ck] : (E.cache[ck] = E.calc({ key, norm: 'value', real: false }, r.y)); if (!a) return null;   // once per dataset and year, for every area (the engine clears its cache when a dataset is added)
    const extensive = v.type === 'count' || v.type === 'total$';
    const byLand = extensive ? /^(km²|km2|acres|ha)$/.test(v.unit || '') : !(m.residents > 0);   // a total of land (km² of wetland, say) is shared by land; every other total by residents
    const shareOf = (p) => { const area = E.geo.area[p.i]; return Math.min(1, byLand ? (area ? p.km2 / area : 0) : (pop[p.i] ? p.residents / pop[p.i] : 0)); };
    // An area drawn on municipio boundaries holds whole municipios (99% or more of each inside), give or take the blocks and grid cells along its edge. Those count
    // whole, and the result is their exact sum, when the rest of the area (the parts in other municipios) holds at most 0.5% of the area's own residents (or land).
    // Any larger part of another municipio, and any area that holds no municipio whole, is shared by residents (or land) as usual; no part is ever dropped.
    const inside_ = (p) => byLand ? p.km2 : p.residents, total = m.munis.reduce((t, p) => t + inside_(p), 0);
    const full = (p) => shareOf(p) >= 0.99, rest = m.munis.reduce((t, p) => t + (full(p) ? 0 : inside_(p)), 0);
    const whole = extensive && m.munis.some(full) && rest <= 0.005 * total;
    let sum = 0, w = 0, wv = 0;
    for (const p of m.munis) {
      let share = shareOf(p); if (whole && share >= 0.99) share = 1;
      const weight = extensive ? share * (byLand ? E.geo.area[p.i] || 0 : pop[p.i] || 0) : (byLand ? p.km2 : p.residents);
      w += weight; if (a[p.i] == null || !isFinite(a[p.i])) continue;
      wv += weight; sum += extensive ? a[p.i] * share : a[p.i] * weight;
    }
    if (!wv) return null;
    const value = extensive ? sum : sum / wv;
    const method = extensive ? (whole ? 'whole' : byLand ? 'land' : 'residents') : (byLand ? 'avg-land' : 'avg-residents');
    return { value, y: r.y, exact: r.exact, early: r.early, method, coverage: w ? wv / w : 0 };
  }

  /** The points of a visitor's file (Count my points, GIS tools step 4): a CSV whose header names a latitude and a longitude column (lat/lon, latitude/longitude,
      latitud/longitud, y/x; comma, semicolon or tab separated, quotes allowed, a decimal comma with ; or tab), or a GeoJSON of Point or MultiPoint features.
      -> { pts: [[lng, lat]] (inside Puerto Rico's box, at most max), rows, bad (no usable coordinates), outside } or { error: 'json' | 'empty' | 'columns' }. */
  const LAT = /^(lat|latitude|latitud|y|lat_dd|latitude_dd)$/i, LON = /^(lon|lng|long|longitude|longitud|x|lon_dd|longitude_dd)$/i;
  function points(text, name = '', max = 200000) {
    const pts = []; let rows = 0, bad = 0, outside = 0;
    const take = (x, y) => { rows++; if (!(isFinite(x) && isFinite(y))) { bad++; return; } if (x < BOX[0] || x > BOX[2] || y < BOX[1] || y > BOX[3]) { outside++; return; } if (pts.length < max) pts.push([x, y]); };
    if (/\.(geo)?json$/i.test(name) || /^\s*\{/.test(text)) {
      let d; try { d = JSON.parse(text); } catch { return { error: 'json' }; }
      const fs = d && d.type === 'FeatureCollection' ? d.features || [] : d && d.type === 'Feature' ? [d] : [];
      for (const f of fs) { const g = f && f.geometry; if (g && g.type === 'Point') take(+g.coordinates[0], +g.coordinates[1]); else if (g && g.type === 'MultiPoint') g.coordinates.forEach(c => take(+c[0], +c[1])); else { rows++; bad++; } }
      return { pts, rows, bad, outside };
    }
    const lines = String(text).replace(/^\ufeff/, '').split(/\r?\n/).filter(l => l.trim()); if (lines.length < 2) return { error: 'empty' };
    const sep = [',', ';', '\t'].map(s => [s, lines[0].split(s).length]).sort((a, b) => b[1] - a[1])[0][0];
    const split = (l) => { const out = []; let cur = '', q = false; for (let i = 0; i < l.length; i++) { const c = l[i]; if (q) { if (c === '"' && l[i + 1] === '"') { cur += '"'; i++; } else if (c === '"') q = false; else cur += c; } else if (c === '"') q = true; else if (c === sep) { out.push(cur); cur = ''; } else cur += c; } out.push(cur); return out.map(s => s.trim()); };
    const head = split(lines[0]), iy = head.findIndex(h => LAT.test(h)), ix = head.findIndex(h => LON.test(h));
    if (iy < 0 || ix < 0) return { error: 'columns' };
    const num = (s) => parseFloat(sep !== ',' ? String(s).replace(',', '.') : s);
    for (const l of lines.slice(1)) { const c = split(l); take(num(c[ix]), num(c[iy])); }
    return { pts, rows, bad, outside };
  }

  /** The area within a walk of `metres` along mapped roads from (lng, lat) (Travel time, GIS tools step 6, docs/study-areas.md), on the road graph of js/roads.js
      (roads.bin: the edge length is stored in 2 m units). As walknet.py walks it: every road but motorways and their links, both ways (one-way rules are for
      vehicles). The point is snapped to the nearest walkable road within SNAP_M (the walk starts there, the straight connector counted); the walk spreads along the
      roads (Dijkstra) until the distance is spent; then each reached stretch of road reaches off the road by up to OFF_M, or by what is left of the walk if less.
      The result is drawn on cells of CELL_M and returned as a MultiPolygon of the cells' rows (rectangles), so the study-area measures can use it.
      -> { geometry, snapM, roadsM } or null when no walkable road is within SNAP_M. */
  const WALK = { SNAP_M: 150, OFF_M: 100, CELL_M: 25, STEP_M: 20, NO_WALK: new Set([0, 1]) };   // road classes 0 and 1: motorway, motorway_link (roads.py CLASSES)
  const walkAdj = new WeakMap();
  function walkArea(R, lng, lat, metres, o = {}) {
    const P = { ...WALK, ...o };
    let A = walkAdj.get(R);
    if (!A) {   // the walkable roads, both ways: node -> (neighbor, edge)
      const deg = new Int32Array(R.nN + 1);
      for (let e = 0; e < R.nE; e++) if (!P.NO_WALK.has(R.cls[e])) { deg[R.eu[e] + 1]++; deg[R.ev[e] + 1]++; }
      for (let i = 0; i < R.nN; i++) deg[i + 1] += deg[i];
      const to = new Int32Array(deg[R.nN]), ed = new Int32Array(deg[R.nN]), fill = deg.slice(0, R.nN);
      for (let e = 0; e < R.nE; e++) if (!P.NO_WALK.has(R.cls[e])) { let k = fill[R.eu[e]]++; to[k] = R.ev[e]; ed[k] = e; k = fill[R.ev[e]]++; to[k] = R.eu[e]; ed[k] = e; }
      A = { start: deg, to, ed }; walkAdj.set(R, A);
    }
    const kx = Math.cos(lat * Math.PI / 180) * 111320, ky = 110574;
    // the nearest walkable road: the snapper of js/roads.js, asked again a little farther out when the nearest road is a motorway
    let s = R.snap(lng, lat, P.SNAP_M);
    if (s && P.NO_WALK.has(R.cls[s.edge])) {
      if (!R.grid) R._buildGrid();
      const cx = Math.floor((lng + 70) / 0.002), cy = Math.floor((lat - 17) / 0.002); s = null;
      for (let dx = -1; dx <= 1; dx++) for (let dy = -1; dy <= 1; dy++) for (const e of R.grid.get((cx + dx) * 2048 + cy + dy) || []) {
        if (P.NO_WALK.has(R.cls[e])) continue; const p = R._project(lng, lat, e); if (!s || p.dist < s.dist) s = p;
      }
      if (s && s.dist > P.SNAP_M) s = null;
    }
    if (!s) return null;
    const dist = new Map(), heap = [], push = (d, n) => { heap.push([d, n]); let i = heap.length - 1; while (i > 0) { const j = (i - 1) >> 1; if (heap[j][0] <= d) break; [heap[i], heap[j]] = [heap[j], heap[i]]; i = j; } };
    const pop = () => { const top = heap[0], last = heap.pop(); if (heap.length) { heap[0] = last; let i = 0; for (;;) { let c = 2 * i + 1; if (c >= heap.length) break; if (c + 1 < heap.length && heap[c + 1][0] < heap[c][0]) c++; if (heap[c][0] >= heap[i][0]) break; [heap[i], heap[c]] = [heap[c], heap[i]]; i = c; } } return top; };
    const relax = (n, d) => { if (d <= metres && d < (dist.has(n) ? dist.get(n) : Infinity)) { dist.set(n, d); push(d, n); } };
    const len = (e) => R.len[e] * 2;
    relax(R.eu[s.edge], s.dist + s.along / s.total * len(s.edge)); relax(R.ev[s.edge], s.dist + (1 - s.along / s.total) * len(s.edge));
    while (heap.length) {
      const [d, n] = pop(); if (d > dist.get(n)) continue;
      for (let k = A.start[n]; k < A.start[n + 1]; k++) relax(A.to[k], d + len(A.ed[k]));
    }
    // the reached stretches: from each reached end of an edge, as far along it as the walk has left; and the start's own edge from the snapped point
    const rows = new Map(), stamp = (x, y, r) => {   // the cells (column i, row j) whose center is within r of (x, y), or within half a cell's diagonal of it
      const c = P.CELL_M, x0 = Math.floor((x - r) / c), x1 = Math.floor((x + r) / c), y0 = Math.floor((y - r) / c), y1 = Math.floor((y + r) / c);
      for (let j = y0; j <= y1; j++) { let row = rows.get(j); for (let i = x0; i <= x1; i++) { const cx = (i + 0.5) * c - x, cy = (j + 0.5) * c - y; if (cx * cx + cy * cy <= r * r + c * c / 2) { if (!row) rows.set(j, row = new Set()); row.add(i); } } }
    };
    const walkEdge = (e, from, d0, startAt) => {   // along edge e from its end `from` (0: u, 1: v), the walk having used d0, starting `startAt` meters along from that end
      const p = R.poly(e), pts = []; for (let i = 0; i < p.length; i += 2) pts.push([(p[i] - lng) * kx, (p[i + 1] - lat) * ky]);
      if (from === 1) pts.reverse();
      const total = len(e), seg = []; let geo = 0; for (let i = 1; i < pts.length; i++) { const l = Math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]); seg.push(l); geo += l; }
      const scale = geo > 0 ? total / geo : 1;
      let run = 0;
      for (let i = 1; i < pts.length; i++) {
        const l = seg[i - 1] * scale, steps = Math.max(1, Math.ceil(l / P.STEP_M));
        for (let k = 0; k <= steps; k++) {
          const along = run + l * k / steps; if (along < startAt) continue;
          const used = d0 + (along - startAt), left = metres - used; if (left < 0) return;
          const t = k / steps; stamp(pts[i - 1][0] + (pts[i][0] - pts[i - 1][0]) * t, pts[i - 1][1] + (pts[i][1] - pts[i - 1][1]) * t, Math.min(P.OFF_M, left));
        }
        run += l;
      }
    };
    for (const [n, d] of dist) for (let k = A.start[n]; k < A.start[n + 1]; k++) { const e = A.ed[k]; walkEdge(e, R.eu[e] === n ? 0 : 1, d, 0); }
    const a = s.along / s.total * len(s.edge);
    walkEdge(s.edge, 0, s.dist - a, a); walkEdge(s.edge, 1, s.dist - (len(s.edge) - a), len(s.edge) - a);
    stamp(0, 0, Math.min(P.OFF_M, metres));
    // the cells as rectangles, one per run along each row
    const c = P.CELL_M, toLL = (x, y) => [+(lng + x / kx).toFixed(6), +(lat + y / ky).toFixed(6)], polys_ = [];
    for (const [j, set] of [...rows].sort((p, q) => p[0] - q[0])) {
      const xs = [...set].sort((p, q) => p - q);
      for (let k = 0; k < xs.length;) { let m = k; while (m + 1 < xs.length && xs[m + 1] === xs[m] + 1) m++; const x0 = xs[k] * c, x1 = (xs[m] + 1) * c, y0 = j * c, y1 = (j + 1) * c;
        polys_.push([[toLL(x0, y0), toLL(x1, y0), toLL(x1, y1), toLL(x0, y1), toLL(x0, y0)]]); k = m + 1; }
    }
    return { geometry: { type: 'MultiPolygon', coordinates: polys_ }, snapM: s.dist, reachedNodes: dist.size };
  }

  /** Which of a list of polygons overlap area g (Download what's inside, GIS tools step 5): the sorted indices of those that hold one of g's grid points, or have a
      corner inside g (a small polygon between the grid's points). Boxes first, so far polygons cost nothing. */
  function overlaps(g, geoms, n = 4000) {
    const b = bbox(g), near = [];
    geoms.forEach((h, k) => { if (!h) return; const c = bbox(h); if (!(c[2] < b[0] || c[0] > b[2] || c[3] < b[1] || c[1] > b[3])) near.push(k); });
    if (!near.length) return [];
    const at = which(near.map(k => geoms[k])), hit = new Set();
    for (const [x, y] of sample(g, n).pts) { const j = at(x, y); if (j >= 0) hit.add(near[j]); }
    for (const k of near) if (!hit.has(k) && polys(geoms[k]).some(p => p[0].some(([x, y]) => inside(g, x, y)))) hit.add(k);
    return [...hit].sort((p, q) => p - q);
  }

  /** The catchments that drain to catchment i (GIS tools step 3, "What drains here"): i and every k whose chain of dn reaches it. The reverse links are built once
      per network and kept. A link that would loop is never followed twice. */
  const upCache = new WeakMap();
  function upstream(dn, i, via) {
    let kids = upCache.get(dn);
    if (!kids) { kids = new Map(); for (let k = 0; k < dn.length; k++) if (dn[k] >= 0) { if (!kids.has(dn[k])) kids.set(dn[k], []); kids.get(dn[k]).push(k); } upCache.set(dn, kids); }
    const out = [], seen = new Set([i]), stack = [i];
    while (stack.length) {
      const k = stack.pop(); out.push(k);
      for (const c of [...(kids.get(k) || []), ...((via && via[k]) || [])]) if (!seen.has(c)) { seen.add(c); stack.push(c); }
    }
    return out;
  }
  const merge = (geoms) => ({ type: 'MultiPolygon', coordinates: geoms.flatMap(g => g.type === 'Polygon' ? [g.coordinates] : g.coordinates) });

  // CRIM's Catastro Digital viewer opened at a point (GIS tools; docs/gis-tools-proposal-2026-11.md, "Parcels in CRIM's viewer"). Only a link: CRIM's terms let its parcels be
  // seen only in its own viewer, so nothing of the catastro is read, copied or drawn here. Web AppBuilder takes ?center=longitude,latitude (WGS 84) and ?level= (zoom; 18 shows
  // single parcels). null for a point that is not a number or is outside Puerto Rico.
  const CRIM_VIEWER = 'https://catastro.crimpr.net/cdprpc/', CRIM_LEVEL = 18;
  function crimUrl(x, y) {
    if (!(Number.isFinite(x) && Number.isFinite(y)) || x < BOX[0] || x > BOX[2] || y < BOX[1] || y > BOX[3]) return null;
    return `${CRIM_VIEWER}?center=${x.toFixed(5)},${y.toFixed(5)}&level=${CRIM_LEVEL}`;
  }
  return { VERSION, MAX_AREAS, MAX_POINTS, FAR_M, BOX, parse, make, check, read, toGeoJSON, inside, areaKm2, sample, bbox, ring, raster, measure, estimate, locate: which, upstream, merge, points, overlaps, walkArea, WALK, crimUrl, CRIM_VIEWER };
});
