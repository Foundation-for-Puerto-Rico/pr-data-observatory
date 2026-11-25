/* PR Data Observatory core: the view state the 2D map (app.js) and the 3D view (twin3d.js) share through the address's hash, and carry in their links to
   each other (docs/view-state.md: the keys, what each view honors, the rules). The keys the 2D map has always written keep their names and formats; the 3D
   view adds its camera's b= and p=. A key or a layer a view does not use is kept as it came when it writes; a value that does not read is ignored; ask, wb and
   wc are one-time requests, never written again. */
(function (name, root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api; else { root.Core = root.Core || {}; root.Core[name] = api; }
})('viewstate', typeof window !== 'undefined' ? window : globalThis, function () {
  'use strict';
  const ORDER = ['c', 'b', 'p', 'l', 's', 'pv', 'r', 'e', 'ey', 'eb', 'ix', 'sc', 'slr', 'bm', 'rg'];   // after the bare municipality; any other key follows, as it came
  const ENCODED = new Set(['e', 'ix', 'sc']);   // written with encodeURIComponent, as the 2D map always has
  const ONCE = new Set(['ask', 'wb', 'wc', 'topic', 'mt']);   // topic: open a topic in Explore (catalog.js, from a Knowledge Area page); mt: open a map tool (app.js openToolLink, from a lesson of the Learn page)
  const VIEWS = ['2d', '3d'];
  // The layers by their l= key (app.js LAYER_KEYS, core/layers.js; tests/viewstate.test.js), with their element id in each view that has them
  const LAYERS = {
    surfheat: { '2d': 'lySurfHeat', '3d': 'lySurfHeat' }, muni: { '2d': 'lyMuni', '3d': 'lyMuni' }, barrios: { '2d': 'lyBarrios', '3d': 'lyBarrios' },
    flood: { '2d': 'lyFlood', '3d': 'lyFlood' }, slide: { '2d': 'lySlide', '3d': 'lySlide' }, slr: { '2d': 'lySlr', '3d': 'lySlr' }, prot: { '2d': 'lyProt', '3d': 'lyProt' },
    landuse: { '2d': 'lyLanduse', '3d': 'lyLanduse' }, soil: { '2d': 'lySoil', '3d': 'lySoil' }, slope: { '2d': 'lySlope' }, contours: { '2d': 'lyContours' }, watersheds: { '2d': 'lyWatersheds' }, oz: { '2d': 'lyOz', '3d': 'lyOz' }, pubhousing: { '2d': 'lyPubHousing', '3d': 'lyPubHousing' }, lihtc: { '2d': 'lyLihtc', '3d': 'lyLihtc' }, reservoirs: { '2d': 'lyReservoirs', '3d': 'lyReservoirs' }, broadband: { '2d': 'lyBroadband', '3d': 'lyBroadband' }, hexgrid: { '2d': 'lyHexgrid', '3d': 'lyHexgrid' }, powerlines: { '2d': 'lyPowerLines', '3d': 'lyPowerLines' }, plants: { '2d': 'lyPlants', '3d': 'lyPlants' }, rivers: { '2d': 'lyRivers', '3d': 'lyRivers' }, groundwater: { '2d': 'lyGroundwater', '3d': 'lyGroundwater' }, rain: { '2d': 'lyRain', '3d': 'lyRain' }, comunidades: { '2d': 'lyComunidades', '3d': 'lyComunidades' },
    routes: { '2d': 'lyRoutes', '3d': 'lyRoutes' }, stops: { '2d': 'lyStops', '3d': 'lyStops' }, hubs: { '2d': 'lyHubs', '3d': 'lyHubs' }, taxi: { '2d': 'lyTaxi', '3d': 'lyTaxi' },
    rings: { '2d': 'walkRings', '3d': 'walkRings' }, gaps: { '2d': 'lyGaps', '3d': 'lyGaps' }, xfer: { '2d': 'lyXfer', '3d': 'lyXfer' },
    fire: { '2d': 'lyFire', '3d': 'lyFire' }, police: { '2d': 'lyPolice', '3d': 'lyPolice' }, townhalls: { '2d': 'lyTownhalls', '3d': 'lyTownhalls' }, dumping: { '2d': 'lyDumping', '3d': 'lyDumping' }, fprroutes: { '2d': 'lyFprRoutes', '3d': 'lyFprRoutes' }, publicos: { '2d': 'lyPublicos', '3d': 'lyPublicos' }, links: { '2d': 'lyLinks', '3d': 'lyLinks' }, traffic: { '2d': 'lyTraffic', '3d': 'lyTraffic' }, bridges: { '2d': 'lyBridges', '3d': 'lyBridges' }, airports: { '2d': 'lyAirports', '3d': 'lyAirports' }, ferries: { '2d': 'lyFerries', '3d': 'lyFerries' }, evcharge: { '2d': 'lyEvCharge', '3d': 'lyEvCharge' },
    libraries: { '2d': 'lyLibraries', '3d': 'lyLibraries' }, schools: { '2d': 'lySchools', '3d': 'lySchools' }, historic: { '2d': 'lyHistoric', '3d': 'lyHistoric' }, wcrp: { '2d': 'lyWcrp', '3d': 'lyWcrp' },
    places: { '2d': 'lyPlaces', '3d': 'lyPlaces' },
    now: { '2d': 'lyNow' },   // the 3D view replays the vehicles on its time bar instead (trips)
    trips: { '3d': 'lyTrips' }, storms: { '3d': 'lyStorms' }, suproutes: { '3d': 'lySupRoutes' }, supstops: { '3d': 'lySupStops' },
    terrain: { '3d': 'lyTerrain' }, buildings: { '3d': 'lyBuildings' },   // the 3D scene's settings
  };
  const KEY_RE = /^[a-z0-9_]+$/;
  // A key read from an address is looked up only among an object's own keys: "constructor", "__proto__" or "toString" names no layer and no measure.
  const has = (o, k) => o != null && typeof k === 'string' && Object.prototype.hasOwnProperty.call(o, k);
  const lay = (k) => (has(LAYERS, k) ? LAYERS[k] : null);
  // What a view keeps of keys it does not know: each value up to 200 characters, 1,000 in all, and 40 layer tokens of the other view (docs/view-state.md).
  const KEEP = { value: 200, total: 1000, layers: 40 };

  const dec = (s) => { try { return decodeURIComponent(s); } catch (e) { return s; } };
  const num = (s) => (s != null && s !== '' && Number.isFinite(+s) ? +s : null);
  /** "lat,lng,zoom" → { lat, lng, z } (Leaflet zoom), or null when it does not read. */
  function readC(v) {
    const a = String(v || '').split(',').map(num);
    if (a.length !== 3 || a.some(x => x == null)) return null;
    const [lat, lng, z] = a;
    return Math.abs(lat) <= 90 && Math.abs(lng) <= 180 && z >= 0 && z <= 24 ? { lat, lng, z } : null;
  }
  /** A hash → { muni, c, b, p, l, s, pv, r, e, ey, eb, ix, sc, slr, bm, rg } (null when absent or not read), raw (each key's text as it came) and order. */
  function parse(hash) {
    const raw = Object.create(null), order = []; let muni = null;
    for (const part of String(hash || '').replace(/^#/, '').split('&')) {
      if (!part) continue;
      const i = part.indexOf('=');
      if (i < 0) { if (muni == null) muni = dec(part); continue; }
      const k = part.slice(0, i); if (!k || k in raw) continue;
      raw[k] = part.slice(i + 1); order.push(k);
    }
    const g = (k) => (k in raw ? dec(raw[k]) : null);   // decoded: an address rebuilt by URLSearchParams (commas as %2C) still reads
    const l = 'l' in raw ? g('l').split(',').filter(t => KEY_RE.test(t.replace(/^-/, ''))) : null;
    const b = num(g('b')), p = num(g('p')), ey = g('ey'), eb = g('eb'), slr = num(g('slr')), s = g('s'), bm = g('bm'), pv = g('pv'), rg = g('rg');
    return {
      muni: muni || null, c: readC(g('c')), b: b != null && Math.abs(b) <= 360 ? b : null, p: p != null && p >= 0 && p <= 85 ? p : null, l,
      s: s && KEY_RE.test(s) ? s : null, pv: pv && /^[a-z0-9]+$/.test(pv) ? pv : null, r: g('r') || null, e: g('e') || null,
      ey: ey && /^\d{4}$/.test(ey) ? +ey : null, eb: eb && /^\d{4}$/.test(eb) ? +eb : null, ix: g('ix') || null, sc: g('sc') || null,
      slr: slr != null && slr >= 1 && slr <= 10 && Number.isInteger(slr) ? slr : null, bm: bm && /^[a-z]+$/.test(bm) ? bm : null, rg: rg && /^[a-z0-9-]{1,40}$/.test(rg) ? rg : null, raw, order,
    };
  }
  // A value is always written encoded: e=, ix= and sc= whole (as the 2D map always has); the others where a character would end the part or the address
  // (% & # = and spaces), so a value cannot add a key ("s=x&ask=…"). { raw } passes text from an address through as it came (Undo of Turn all off).
  const enc = (k, v) => (v && typeof v === 'object' && typeof v.raw === 'string' ? v.raw
    : ENCODED.has(k) ? encodeURIComponent(v) : String(v).replace(/[%&#=\s]/g, encodeURIComponent));
  /** The hash `prev` with a view's values put in: in `mine`, a value writes its key, null takes it out, undefined keeps it; other keys stay, after the known
   *  ones (ask, wb, wc aside). mine.l: this view's tokens (layerTokens), followed by the address's layers this view does not have. */
  function write(view, prev, mine) {
    const P = parse(prev), out = Object.create(null);
    let room = KEEP.total;
    for (const k of P.order) {
      if (ONCE.has(k)) continue;
      if (!ORDER.includes(k)) { const v = P.raw[k]; if (v.length > KEEP.value || k.length + v.length + 2 > room) continue; room -= k.length + v.length + 2; }   // an unknown key: kept within the caps
      out[k] = P.raw[k];
    }
    let muni = P.muni;
    for (const [k, v] of Object.entries(mine || {})) {
      if (v === undefined) continue;
      if (k === 'muni') { muni = v || null; continue; }
      if (k === 'l') { const own = v || []; out.l = [...own, ...foreignLayers(view, P.l || [])].join(','); continue; }
      if (v === null || v === '' || (v && typeof v === 'object' && !v.raw)) delete out[k]; else out[k] = enc(k, v);
    }
    const keys = [...ORDER.filter(k => k in out), ...Object.keys(out).filter(k => !ORDER.includes(k))];
    const parts = [...(muni ? [encodeURIComponent(muni)] : []), ...keys.map(k => `${k}=${out[k]}`)];
    return parts.length ? '#' + parts.join('&') : '';
  }
  /** The l= tokens naming a layer this view does not have, or an unknown key. */
  const foreignLayers = (view, tokens) => tokens.filter(t => { const L = lay(t.replace(/^-/, '')); return !(L && L[view]); }).slice(0, KEEP.layers);
  /** Whether a layer key is drawn in both views. */
  const shared = (key) => { const L = lay(key); return !!(L && VIEWS.every(v => L[v])); };
  /** This view's l= tokens: a layer on (on(id)) by its key, one off that is on by default (byDefault(id)) as "-key". */
  function layerTokens(view, on, byDefault) {
    const out = [];
    for (const [k, L] of Object.entries(LAYERS)) {
      const id = L[view]; if (!id) continue;
      if (on(id)) out.push(k); else if (byDefault(id)) out.push('-' + k);
    }
    return out;
  }
  /** What l= asks of this view's layers, { id: on }: nothing without l= (an old link); else listed on, "-key" off, a layer of both views not listed off, one of
   *  this view only not listed at its default (the other view cannot say). */
  function layerPlan(view, tokens, byDefault = () => false) {
    const plan = {};
    if (!tokens) return plan;
    const set = new Set(tokens);
    for (const [k, L] of Object.entries(LAYERS)) {
      const id = L[view]; if (!id) continue;
      plan[id] = set.has(k) ? true : set.has('-' + k) ? false : shared(k) ? false : !!byDefault(id);
    }
    return plan;
  }

  /** The address's zoom is Leaflet's; MapLibre's is one less for the same scale (512 px tiles). */
  const toMapLibre = (z) => z - 1, fromMapLibre = (z) => z + 1;
  /** c= : lat and lng to 4 decimals (about 10 m), the zoom (Leaflet's) to 2. */
  const cOf = (lat, lng, z) => `${(+lat).toFixed(4)},${(+lng).toFixed(4)},${+(+z).toFixed(2)}`;

  /** The 3D columns from e= (tokens "key.mode.norm…", core/engine.js; mode f or b Shaded, s Symbol): height from the first Symbol layer, else the first
   *  Shaded; color from the first Shaded when another dataset ('' = the height); with their normalizations. null when e= names none. */
  function econColumns(e) {
    const toks = String(e || '').split(',').map(t => t.split('.')).filter(f => f[0] && KEY_RE.test(f[0]));
    if (!toks.length) return null;
    const fill = toks.find(f => f[1] !== 's'), sym = toks.find(f => f[1] === 's'), h = sym || fill;
    const c = fill && fill[0] !== h[0] ? fill : null;   // the same dataset as the height: no color of its own
    return { h: h[0], c: c ? c[0] : '', hNorm: h[2] || null, cNorm: c ? c[2] || null : null };
  }
  /** e= for the 3D columns: the color Shaded and the height a Symbol, or one Shaded layer; the tokens of `prev` that still apply are kept whole. */
  function econOf(h, c, prev, norms = {}) {
    const was = econColumns(prev);
    if (was && was.h === h && was.c === (c || '')) return prev;
    const toks = String(prev || '').split(',');
    const tok = (key, mode, norm) => toks.find(t => { const f = t.split('.'); return f[0] === key && (f[1] === 's') === (mode === 's'); }) || [key, mode, ...(norm ? [norm] : [])].join('.');
    return c && c !== h ? `${tok(c, 'f', norms.c)},${tok(h, 's', norms.h)}` : tok(h, 'f', norms.h);
  }

  return { ORDER, ENCODED, ONCE, LAYERS, KEEP, has, parse, write, layerTokens, layerPlan, foreignLayers, shared, toMapLibre, fromMapLibre, cOf, econColumns, econOf };
});
