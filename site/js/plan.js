/* PR Data Observatory: place search and route planning, shared by the 2D map and the 3D view.
   Load after common.js / icons.js / roads.js and before the page script. The page supplies the map drawing through Plan.host.
   - Gaz      the place-name index (data/gazetteer.json: municipalities, barrios, towns, streets, PR route numbers, landmarks)
   - attachSearch  an accessible search box with a results list, used by both header boxes and the planner's From / Via / To boxes
   The route planner (Plan, planMarkup, planWire) is in plan_route.js: the 3D view loads it with the page, the 2D map on first use (network.js planLoad).
   Everything is computed in the browser; a typed place name leaves the page only if the visitor asks for the online address lookup. */

// ── Geometry ─────────────────────────────────────────────────────────────────
const rad = (d) => d * Math.PI / 180;
const distM = (a, b) => Math.hypot((b[1] - a[1]) * Math.cos(rad((a[0] + b[0]) / 2)) * 111320, (b[0] - a[0]) * 110574);   // [lat, lng] pairs
function segDistM(p, a, b) {   // meters from point p to segment a-b, all [lat, lng]
  const k = Math.cos(rad(p[0])) * 111320, ky = 110574;
  const px = (p[1] - a[1]) * k, py = (p[0] - a[0]) * ky, bx = (b[1] - a[1]) * k, by = (b[0] - a[0]) * ky, l2 = bx * bx + by * by;
  const t = l2 ? Math.max(0, Math.min(1, (px * bx + py * by) / l2)) : 0;
  return Math.hypot(px - t * bx, py - t * by);
}
function lineDistM(p, pts) { let d = Infinity; for (let i = 1; i < pts.length; i++) d = Math.min(d, segDistM(p, pts[i - 1], pts[i])); return d; }
function samples(pts, step = 100) {
  const out = [pts[0]];
  for (let i = 1; i < pts.length; i++) {
    const a = pts[i - 1], b = pts[i], n = Math.max(1, Math.round(distM(a, b) / step));
    for (let j = 1; j <= n; j++) out.push([a[0] + (b[0] - a[0]) * j / n, a[1] + (b[1] - a[1]) * j / n]);
  }
  return out;
}
function simplifyLine(pts, tolM) {   // Douglas-Peucker on [lat, lng] points
  if (pts.length < 3) return pts;
  const keep = new Uint8Array(pts.length); keep[0] = keep[pts.length - 1] = 1;
  const stack = [[0, pts.length - 1]];
  while (stack.length) {
    const [i, j] = stack.pop(); let dmax = 0, k = -1;
    for (let m = i + 1; m < j; m++) { const d = segDistM(pts[m], pts[i], pts[j]); if (d > dmax) { dmax = d; k = m; } }
    if (k >= 0 && dmax > tolM) { keep[k] = 1; stack.push([i, k], [k, j]); }
  }
  return pts.filter((_, i) => keep[i]);
}
function nearLine(pts) {   // (lat, lng, meters) => is the point within that distance of the line? skips segments whose box is too far
  const segs = [];
  for (let i = 1; i < pts.length; i++) { const a = pts[i - 1], b = pts[i]; segs.push([a, b, Math.min(a[0], b[0]), Math.max(a[0], b[0]), Math.min(a[1], b[1]), Math.max(a[1], b[1])]); }
  return (lat, lng, d) => {
    const dl = d / 110574 + 1e-5, dn = d / (111320 * Math.cos(rad(lat))) + 1e-5;
    for (const s of segs) { if (lat < s[2] - dl || lat > s[3] + dl || lng < s[4] - dn || lng > s[5] + dn) continue; if (segDistM([lat, lng], s[0], s[1]) <= d) return true; }
    return false;
  };
}
const lineKm = (pts) => pts.slice(1).reduce((a, p, i) => a + distM(pts[i], p), 0) / 1000;

// Point-in-polygon on plain GeoJSON, so overlay layers need not be interactive (an interactive polygon layer
// swallows every click and hover meant for the municipality layer beneath it).
const _bbox = new WeakMap();
function _ring(r, x, y) { let inside = false; for (let i = 0, j = r.length - 1; i < r.length; j = i++) { const xi = r[i][0], yi = r[i][1], xj = r[j][0], yj = r[j][1]; if ((yi > y) !== (yj > y) && x < (xj - xi) * (y - yi) / (yj - yi) + xi) inside = !inside; } return inside; }
function _poly(rings, x, y) { if (!_ring(rings[0], x, y)) return false; for (let k = 1; k < rings.length; k++) if (_ring(rings[k], x, y)) return false; return true; }
function featuresAt(fc, ll, accept = () => true, limit = 3) {
  const out = [], x = ll.lng, y = ll.lat;
  for (const f of fc.features) {
    const g = f.geometry; if (!g || !accept(f)) continue;
    let b = _bbox.get(f);
    if (!b) { b = [Infinity, Infinity, -Infinity, -Infinity]; const walk = (a) => typeof a[0] === 'number' ? (b[0] = Math.min(b[0], a[0]), b[1] = Math.min(b[1], a[1]), b[2] = Math.max(b[2], a[0]), b[3] = Math.max(b[3], a[1])) : a.forEach(walk); walk(g.coordinates); _bbox.set(f, b); }
    if (x < b[0] || x > b[2] || y < b[1] || y > b[3]) continue;
    const hit = g.type === 'Polygon' ? _poly(g.coordinates, x, y) : g.type === 'MultiPolygon' ? g.coordinates.some(p => _poly(p, x, y)) : false;
    if (hit) { out.push(f); if (out.length >= limit) break; }
  }
  return out;
}
function boundsOf(coords) {   // [[lng, lat], ...] -> [[south, west], [north, east]]
  let s = 90, w = 180, n = -90, e = -180;
  for (const [x, y] of coords) { s = Math.min(s, y); n = Math.max(n, y); w = Math.min(w, x); e = Math.max(e, x); }
  return [[s, w], [n, e]];
}

// ── Data: one download per file ──────────────────────────────────────────────
const Data = (() => {
  const cache = {};
  return { json(path) { if (!cache[path]) cache[path] = fetchJson(path).catch(e => { delete cache[path]; throw e; }); return cache[path]; } };
})();

// ── Gazetteer ────────────────────────────────────────────────────────────────
const KIND_INFO = {   // label (English key, shown through T()), icon (Material Symbols name), ranking weight (lower = listed first)
  municipio: ['Municipality', 'location_city', 0], town: ['Town', 'location_city', 1], village: ['Community', 'place', 3], barrio: ['Barrio', 'place', 4], neighborhood: ['Neighborhood', 'place', 4],
  route: ['Highway', 'route', 5], road: ['Street', 'route', 8], hospital: ['Hospital', 'local_hospital', 6], school: ['School', 'school', 7], university: ['College', 'school', 6], civic: ['Public building', 'account_balance', 6],
  transport: ['Terminal', 'transfer_within_a_station', 2], park: ['Park', 'park', 7], beach: ['Beach', 'beach_access', 6], peak: ['Mountain', 'landscape', 7], water: ['Water', 'waves', 7],
  landmark: ['Landmark', 'museum', 6], airport: ['Airport', 'flight', 2], mall: ['Shopping center', 'storefront', 6],
  stop: ['Transit stop', 'directions_bus', 5], transit_route: ['Transit route', 'commute', 5], tourism: ['Tourism place', 'place', 6], coords: ['Coordinates', 'place', 0], online: ['Address', 'place', 0],
};
const QUERY_WORDS = { av: 'avenida', ave: 'avenida', avda: 'avenida', cll: 'calle', carr: 'carretera', ctra: 'carretera', urb: 'urbanizacion', bo: 'barrio', res: 'residencial', hosp: 'hospital', univ: 'universidad', pza: 'plaza', mt: 'monte' };

function parseQuery(q) {
  let n = norm(q).replace(/[.,;:()"']/g, ' ').replace(/\s+/g, ' ').trim();
  const r = n.match(/^(?:pr|ruta|route|carr(?:etera)?|hwy|highway)\s*-?\s*(\d{1,4}[a-z]?)$/);
  if (r) n = 'pr-' + r[1];
  const tokens = n.split(' ').filter(Boolean).map(t => QUERY_WORDS[t] || t);
  return { n: tokens.join(' '), tokens };
}
// how well a name matches: 0 exact, 1 starts with the query, 2 every word starts a word of the name, 3 every word appears in it; null = no match
function textScore(nn, qn, tokens) {
  if (nn === qn) return 0;
  if (nn.startsWith(qn)) return 1;
  let allWordStart = true;
  for (const t of tokens) { if (!(nn.startsWith(t) || nn.includes(' ' + t) || nn.includes('-' + t) || nn.includes('(' + t))) { allWordStart = false; break; } }
  if (allWordStart) return 2;
  for (const t of tokens) if (!nn.includes(t)) return null;
  return 3;
}
const COORD_RE = /^\s*(-?\d{1,2}\.\d{2,})\s*[, ]\s*(-?\d{1,3}\.\d{2,})\s*$/;

const Gaz = {
  items: null, munis: [], kinds: [], norms: [], loading: null,
  load() {
    if (!this.loading) this.loading = Data.json('data/gazetteer.json').then(d => { this.munis = d.munis; this.kinds = d.kinds; this.items = d.items; this.norms = d.items.map(r => norm(r[0])); return this; }).catch(e => { this.loading = null; throw e; });
    return this.loading;
  },
  /** Ranked matches [{score, name, lat, lng, kind, muni, extra}] for a parsed query; bias = {lat, lng} breaks ties by distance. */
  search(pq, { kinds = null, limit = 40, bias = null } = {}) {
    if (!this.items || !pq.n) return [];
    const out = [];
    for (let i = 0; i < this.items.length; i++) {
      const r = this.items[i], kind = this.kinds[r[3]];
      if (kinds && !kinds.has(kind)) continue;
      const s = textScore(this.norms[i], pq.n, pq.tokens); if (s === null) continue;
      out.push({ score: s * 10 + KIND_INFO[kind][2] * .5, name: r[0], lat: r[1], lng: r[2], kind, muni: this.munis[r[4]] || '', extra: r[5] || '', i });
    }
    out.sort((a, b) => a.score - b.score || (bias ? distM([a.lat, a.lng], [bias.lat, bias.lng]) - distM([b.lat, b.lng], [bias.lat, bias.lng]) : 0) || a.name.length - b.name.length);
    // a common street name exists in dozens of municipalities: keep the nearest few instead of a wall of repeats
    const perName = {}, kept = [];
    for (const o of out) { const k = norm(o.name) + '|' + o.kind; perName[k] = (perName[k] || 0) + 1; if (perName[k] <= (o.kind === 'road' || o.kind === 'route' ? 4 : 6)) kept.push(o); if (kept.length >= limit) break; }
    return kept;
  },
  /** The closest named thing to a point, for labeling a spot picked on the map. */
  nearest(lat, lng, maxM = 400) {
    if (!this.items) return null;
    let best = null, bd = maxM;
    for (let i = 0; i < this.items.length; i++) { const r = this.items[i]; if (Math.abs(r[1] - lat) > .01 || Math.abs(r[2] - lng) > .012) continue; const d = distM([lat, lng], [r[1], r[2]]); if (d < bd) { bd = d; best = { name: r[0], kind: this.kinds[r[3]], muni: this.munis[r[4]] || '', d }; } }
    return best;
  },
};
const resultFromGaz = (g) => ({ kind: g.kind, label: g.name, sub: `${T(KIND_INFO[g.kind][0])}${g.extra && g.kind === 'route' ? ' · ' + g.extra : ''}${g.muni ? ' · ' + g.muni : ''}`, lat: g.lat, lng: g.lng, muni: g.muni, score: g.score });

// ── Search box ───────────────────────────────────────────────────────────────
/** Wires an <input> and a results container. cfg.run(q) returns (or resolves to) [{label, sub, kind | iconHtml, ...}];
 *  cfg.onPick(result) is called on a click or Enter. Arrow keys move through the list, Escape closes it. */
function attachSearch(input, list, cfg) {
  const id = list.id || (list.id = 'sr' + Math.random().toString(36).slice(2, 7));
  input.setAttribute('role', 'combobox'); input.setAttribute('aria-autocomplete', 'list'); input.setAttribute('aria-controls', id); input.setAttribute('aria-expanded', 'false'); input.autocomplete = 'off';
  list.setAttribute('role', 'listbox');
  let results = [], seq = 0, timer = null;
  const close = () => { list.classList.remove('open'); input.setAttribute('aria-expanded', 'false'); };
  const iconFor = (r) => r.iconHtml || icon((KIND_INFO[r.kind] || KIND_INFO.coords)[1], { size: 22, color: '#205D7B' });
  function paint(extra = '') {
    list.innerHTML = results.map((r, i) => `<button type="button" role="option" class="item" data-i="${i}" tabindex="-1">${iconFor(r)}<span>${esc(r.label)}<small>${esc(r.sub || '')}</small></span></button>`).join('') + extra;
    list.classList.add('open'); input.setAttribute('aria-expanded', 'true');
  }
  async function run() {
    const q = input.value, my = ++seq;
    if (q.trim().length < (cfg.minChars || 2)) { close(); return; }
    let rs; try { rs = await cfg.run(q); } catch { rs = []; }
    if (my !== seq) return;   // a newer keystroke is already being answered
    results = rs;
    paint((results.length ? '' : `<div class="item none"><small>${esc(cfg.emptyText || T('No match in the place index.'))}</small></div>`) + (cfg.online && q.trim().length >= 4 ? `<button type="button" role="option" class="item online" data-online="1" tabindex="-1">${icon('search', { size: 22, color: '#666' })}<span>${esc(T('Look up “{q}” as an address online', { q: q.trim() }))}<small>${esc(T('Sends your text to OpenStreetMap Nominatim'))}</small></span></button>` : ''));
  }
  async function online() {
    const q = input.value.trim(), my = ++seq;
    list.innerHTML = `<div class="item none"><small>${esc(T('Looking it up…'))}</small></div>`;
    try {
      const r = await fetch('https://nominatim.openstreetmap.org/search?' + new URLSearchParams({ format: 'jsonv2', q, countrycodes: 'pr', limit: '6', 'accept-language': 'es,en', viewbox: '-67.95,18.6,-65.2,17.85', bounded: '1' }));
      if (!r.ok) throw new Error(r.status);
      const js = await r.json(); if (my !== seq) return;
      results = js.map(x => ({ kind: 'online', label: (x.display_name || '').split(',').slice(0, 2).join(','), sub: (x.display_name || '').split(',').slice(2, 4).join(',').trim() || 'OpenStreetMap', lat: +x.lat, lng: +x.lon, bbox: x.boundingbox ? [[+x.boundingbox[0], +x.boundingbox[2]], [+x.boundingbox[1], +x.boundingbox[3]]] : null }));
      paint(results.length ? '' : `<div class="item none"><small>${esc(T('Nothing found for that address. Try the street and municipality.'))}</small></div>`);
    } catch { if (my === seq) { results = []; paint(`<div class="item none"><small>${esc(T('The address lookup is not available right now.'))}</small></div>`); } }
  }
  const pick = (r) => { close(); if (cfg.onPick) cfg.onPick(r); };
  const firstResult = () => results.find(r => !r.hint);   // Enter picks a result, never an offer that starts a download
  input.addEventListener('input', () => { clearTimeout(timer); timer = setTimeout(run, 90); });
  input.addEventListener('focus', () => { if (cfg.warm) cfg.warm(); if (input.value.trim().length >= (cfg.minChars || 2) && !list.classList.contains('open')) run(); });
  const keys = (e) => {
    const items = [...list.querySelectorAll('.item[role=option]')];
    if (e.key === 'Escape') { if (list.classList.contains('open')) { e.stopPropagation(); close(); input.focus(); } return; }
    if (!items.length) { if (e.key === 'Enter' && e.target === input) { e.preventDefault(); clearTimeout(timer); run().then(() => { const r = firstResult(); if (r) pick(r); }); } return; }
    const i = items.indexOf(document.activeElement);
    if (e.key === 'ArrowDown') { e.preventDefault(); items[Math.min(i + 1, items.length - 1)].focus(); }
    else if (e.key === 'ArrowUp') { e.preventDefault(); i <= 0 ? input.focus() : items[i - 1].focus(); }
    else if (e.key === 'Enter' && e.target === input) { e.preventDefault(); const r = firstResult(); if (r) pick(r); }
    else if (e.key === 'Tab') close();
  };
  input.addEventListener('keydown', keys); list.addEventListener('keydown', keys);
  list.addEventListener('click', e => { const b = e.target.closest('.item'); if (!b) return; if (b.dataset.online) { online(); return; } if (b.dataset.i != null) pick(results[+b.dataset.i]); });
  document.addEventListener('click', e => { if (!list.contains(e.target) && e.target !== input) close(); }, cfg.signal ? { signal: cfg.signal } : undefined);
  return { close, run, input };
}

/** Places the page offers besides the index (its tourism listings, municipalities with their statistics): [(parsedQuery) => results]. */
const SearchSources = [], SearchDecorate = [];   // decorators adjust a result's wording after ranking (the page knows its own statistics)
async function searchEverything(q, { pointsOnly = false, bias = null, max = 12 } = {}) {
  const c = q.match(COORD_RE);
  if (c && Math.abs(+c[1]) <= 90 && Math.abs(+c[2]) <= 180) return [{ kind: 'coords', label: `${(+c[1]).toFixed(5)}, ${(+c[2]).toFixed(5)}`, sub: T('Coordinates'), lat: +c[1], lng: +c[2] }];
  const pq = parseQuery(q); if (!pq.n) return [];
  try { await Gaz.load(); } catch { /* the page sources still work */ }
  let out = [];
  for (const src of SearchSources) { try { out = out.concat(await src(pq, { pointsOnly, bias }) || []); } catch { /* one source failing must not blank the list */ } }
  out = out.concat(Gaz.search(pq, { bias, limit: 30 }).map(resultFromGaz));
  out.sort((a, b) => (a.score ?? 50) - (b.score ?? 50));
  // a municipality is also the name of its town: keep one entry for each name
  const seen = new Set(), res = [];
  for (const r of out) { const k = norm(r.label) + '|' + r.kind + '|' + (r.muni || '') + '|' + Math.round((r.lat || 0) * 500) + Math.round((r.lng || 0) * 500); if (seen.has(k)) continue; seen.add(k); res.push(r); }
  const cap = {}; const final = [];
  for (const r of res.filter(x => !x.hint)) { cap[r.kind] = (cap[r.kind] || 0) + 1; if (cap[r.kind] <= ({ road: 4, route: 3, tourism: 5, stop: 4 }[r.kind] || 4)) final.push(r); if (final.length >= max) break; }
  final.push(...res.filter(x => x.hint));   // an offer ("load the tourism listings") is not a result: it is never cut by the cap
  if (!pointsOnly) SearchDecorate.forEach(f => final.forEach(f));
  return final;
}
