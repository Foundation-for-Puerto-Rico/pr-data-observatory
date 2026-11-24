/* PR Data Observatory · Knowledge Area · WCRP (wcrp.html). Two maps (2026-10-19, the project lead: Social Capital first): 1, the Social Capital map (js/wcrp_social.js), which
   loads with the page, and 2, the vulnerability map: the Risk and Vulnerability Indicators by barrio, the original as published (2022) and the observatory's
   updated version with the same method ("Updated 2020–2024" on the page, 'rebuild' in ids, data keys and the address; wcrp_rvi.py), drawn by js/wcrp_vuln.js, which loads with its Spanish and the barrio outlines (barrios.geojson) when its section
   comes near, when one of its explanations opens, or at once for an address that names a view of it (#a=, #v=). This file holds what both maps share: the
   index (wcrp_rvi_barrio.json, read at load: the Social Capital summary shows each municipio's levels), the program's communities (wcrp.geojson), the municipios
   (wcrp_social.json), the one municipio filter of the page and the address (#a=econ&v=rebuild&m=Adjuntas; v=change is the comparison view), and the page's
   collapsible explanations (<details>, closed), which open from any link to them. docs/wcrp.md. */
const TK = (t) => t;   // translated where it is shown, with T()
const AREAS = ['overall', 'econ', 'edu', 'envir', 'health', 'housing', 'infra'];
const AREA_NAME = { overall: TK('Overall'), econ: TK('Economy'), edu: TK('Education'), envir: TK('Environment'), health: TK('Health'), housing: TK('Housing'), infra: TK('Infrastructure') };
const VERSIONS = ['orig', 'rebuild', 'change'];   // change: each barrio's level in the rebuild minus the original's, opened from "More about the comparison" (or an old link); also w2021...: the rebuild in an older window (the slider, W.steps)
const RAMP = Core.palettes.RAMPS.red, NOVAL = Core.palettes.NOVAL;
const W = { doc: null, fc: null, comm: null, ids: [], at: new Map(), v: {}, area: 'overall', ver: 'orig', muni: '', names: [], code: new Map(), geoP: null, vuln: false };

/** Rank 1 to 5 from an index stored as a percentile times 100 (two decimals): ceil(5 × index), at least 1, as wcrp_rvi.py computes it. */
const rankOf = (x) => x == null ? null : Math.min(5, Math.max(1, Math.ceil(x / 20 - 1e-7)));
const winAt = (ver) => W.doc.series.ends.indexOf(+ver.slice(1));   // 'w2022': the rebuild in the window that ends in 2022 (wcrp_rvi.py series: one digit a barrio, 0 for none)
const rankAt = (ver, area, i) => ver[0] === 'w' ? +W.doc.series.levels[area][winAt(ver)][i] || null : rankOf(W.v[ver][area][i]);
const verWindow = (ver) => ver[0] === 'w' ? W.doc.series.windows[winAt(ver)] : W.doc.versions[ver].window;
const verName = (ver) => ver === 'orig' ? T('Original 2022') : T('Updated {window}', { window: verWindow(ver) });
/** The slider: Original 2022, then each survey window the rebuild has (the last is the updated version); the change view keeps the last stop. */
function syncVer() { const s = $('#wmVer'), k = W.steps.indexOf(W.ver), v = W.ver === 'change' ? 'rebuild' : W.ver; s.value = k < 0 ? W.steps.length - 1 : k; $('#wmVerOut').textContent = verName(v); s.setAttribute('aria-valuetext', verName(v)); }
const muniOf = (geoid) => W.code.get(String(geoid).slice(0, 5)) || '';   // a barrio's GEOID starts with its municipio's
const inkOn = (r) => r >= 4 ? '#fff' : '#2A2E2E';   // the text on a level's colour

/** Every pop-up of a map stays narrower than the map (Leaflet's maxWidth is in pixels: 340 is wider than a phone's map), so its right column is never cut off. */
function capPopups(map, room = 64) {
  map.on('popupopen', (e) => {
    const p = e.popup; if (p._capMax == null) p._capMax = p.options.maxWidth;
    const w = Math.max(160, Math.min(p._capMax, map.getSize().x - room));
    if (p.options.maxWidth !== w) { p.options.maxWidth = w; p.update(); }
  });
}
/** The barrio outlines, once: the vulnerability map draws them; the Social Capital map zooms to a municipio's barrios. */
const geo = () => W.geoP || (W.geoP = fetchJson('data/barrios.geojson').then(fc => (W.fc = fc), e => { W.geoP = null; throw e; }));

// ── The address and the one municipio of the page ───────────────────────────
const isView = (h) => /(^|&)[avm]=/.test(h);   // a view (#a=econ&m=Adjuntas), not a link to a part of the page (#method)
/** Reads the view from the address; true when it names a view of the vulnerability map (an area or a version), which then opens at once. */
function readHash() {
  const h = location.hash.slice(1); if (!isView(h)) return false;
  const q = new URLSearchParams(h);
  if (AREAS.includes(q.get('a'))) W.area = q.get('a');
  if (VERSIONS.includes(q.get('v')) || /^w\d{4}$/.test(q.get('v'))) W.ver = q.get('v');   // a window is checked against the file once it has arrived (W.steps)
  const m = q.get('m'); if (m) W.muni = W.names.find(n => norm(n) === norm(m)) || '';
  return q.has('a') || q.has('v');
}
function writeHash() {
  const q = new URLSearchParams(); if (W.area !== 'overall') q.set('a', W.area); if (W.ver !== 'orig') q.set('v', W.ver); if (W.muni) q.set('m', W.muni);
  const h = q.toString(); history.replaceState(null, '', h ? '#' + h : location.pathname + location.search);
}
/** One municipio for the whole page: the Social Capital map and its summary, and the vulnerability map's filter. */
function setMuni(m) {
  W.muni = m || '';
  for (const s of ['#scMuni', '#wmMuni']) $(s).value = W.muni;
  writeHash();
  Social.setMuni();
  if (W.vuln) Vuln.setMuni();
}

// ── The vulnerability map: its script, Spanish and outlines load on approach (js/wcrp_vuln.js) ──
const script = (src) => new Promise((ok, fail) => { const s = document.createElement('script'); s.src = src; s.onload = ok; s.onerror = () => { s.remove(); fail(new Error(src)); }; document.body.appendChild(s); });
// ── The base map of both maps (js/core/basemap.js: OpenFreeMap vector tiles drawn by MapLibre under each map's layers), once the page is ready, so it stays
// off the first load; with no WebGL or no answer from the provider, a map goes on over a plain background with a notice in its credits line (docs/basemap.md) ──
let readyNow = null; const readyP = new Promise(r => { readyNow = r; });
let basemapJs = null;
W.basemap = (map) => readyP.then(() => basemapJs || (basemapJs = window.Core.basemap ? Promise.resolve() : script('js/core/basemap.js?v=8').catch(e => { basemapJs = null; throw e; })))
  .then(() => Core.basemap.leaflet(map), () => { map.getContainer().dataset.basemap = 'off'; });
let vulnP = null, vulnJs = null;
function loadVuln() {
  return vulnP || (vulnP = Promise.all([W.coreP, I18N.load('vuln'), vulnJs || (vulnJs = script('js/wcrp_vuln.js?v=4').catch(e => { vulnJs = null; throw e; })), geo()])
    .then(() => { Vuln.init(); W.vuln = true; if (anchored && Math.abs(scrollY - anchored.y) < 2) { anchored.el.scrollIntoView(); anchored.y = scrollY; } })   // its legend and texts fill in: a part of the page that a link scrolled to stays in place
    .catch(e => { vulnP = null; console.error(e); $('#wmStatus').textContent = T('The vulnerability map could not be loaded. Check your connection, then scroll away and back to try again.'); throw e; }));
}
const quiet = (p) => p.catch(() => {});   // the error is on the page already

// ── Collapsible explanations: a link to a closed <details> (the bar "On this page", "Read with care", an address with #method) opens it ──
/** Opens the closed <details> that hold an element, and the element itself when it is one. */
function reveal(el) { for (let d = el; d; d = d.parentElement) if (d.tagName === 'DETAILS' && !d.open) d.open = true; }
const target = (hash) => { let id = ''; try { id = decodeURIComponent((hash || '').replace(/^#/, '')); } catch (e) { return null; }   // a broken % (wcrp.html#%) names nothing
  return id && !isView(id) ? document.getElementById(id) : null; };
let anchored = null;   // the part of the page a link scrolled to, and where
function revealHash() { const el = target(location.hash); if (el) { reveal(el); el.scrollIntoView(); anchored = { el, y: scrollY }; } }
document.addEventListener('click', (e) => { const a = e.target.closest && e.target.closest('a[href^="#"]'), el = a && target(a.getAttribute('href')); if (el) reveal(el); });   // before the browser follows the link
window.addEventListener('hashchange', revealHash);
for (const id of ['care', 'method', 'compare', 'sources']) $('#' + id).addEventListener('toggle', (e) => { if (e.target.open) quiet(loadVuln()); });   // what they show comes with the vulnerability map
$('#cmpShow').onclick = () => quiet(loadVuln().then(() => Vuln.showChange()));
// printing shows every explanation
window.addEventListener('beforeprint', () => document.querySelectorAll('details:not([open])').forEach(d => { d.open = true; d.dataset.printed = '1'; }));
window.addEventListener('afterprint', () => document.querySelectorAll('details[data-printed]').forEach(d => { d.open = false; delete d.dataset.printed; }));
reveal(target(location.hash));   // a link from another page (the data dictionary's wcrp.html#method)

/** The vulnerability map's controls, before its script arrives: the areas, the version's name with its years, and a choice that is kept (Vuln.init reads W) and loads the map. */
function initVulnControls() {
  $('#wmArea').innerHTML = AREAS.map(a => `<option value="${a}">${esc(T(AREA_NAME[a]))}</option>`).join('');
  $('#wmArea').value = W.area;
  W.steps = ['orig', ...W.doc.series.ends.slice(0, -1).map(e => 'w' + e), 'rebuild'];
  if (W.ver[0] === 'w' && !W.steps.includes(W.ver)) W.ver = 'orig';
  $('#wmVer').max = W.steps.length - 1;
  $('#wmTicks').innerHTML = W.steps.map(v => `<span>${esc(v === 'orig' ? T('Original 2022') : verWindow(v))}</span>`).join('');
  syncVer();
  $('#wmArea').onchange = e => { W.area = e.target.value; quiet(loadVuln()); };
  $('#wmVer').oninput = e => { W.ver = W.steps[+e.target.value]; syncVer(); quiet(loadVuln()); };
  $('#wmComm').onchange = () => quiet(loadVuln());   // Vuln.init draws the communities if the box is checked by then
}

// ── The program ──────────────────────────────────────────────────────────────
function renderAbout() {
  const P = W.comm.features.map(f => f.properties), munis = new Set(P.map(p => p.municipio)), approved = P.filter(p => p.estado === 'plan_aprobado').length;
  const kpi = (v, l) => `<div class="kpi"><div class="v">${esc(v)}</div><div class="l">${esc(l)}</div></div>`;
  $('#aboutKpis').innerHTML = kpi(fmt(P.length), T('WCRP communities')) + kpi(fmt(munis.size), T('municipios with a WCRP community')) + kpi(fmt(approved), T('plans approved by the Puerto Rico Department of Housing')) + kpi(fmt(W.ids.length), T('barrios on the vulnerability map'));
}

// ── Page ─────────────────────────────────────────────────────────────────────
const obs = new IntersectionObserver(entries => entries.forEach(en => { if (en.isIntersecting) document.querySelectorAll('.toc a[href^="#"]').forEach(a => { const on = a.getAttribute('href') === '#' + en.target.id; a.classList.toggle('active', on); if (on) a.setAttribute('aria-current', 'location'); else a.removeAttribute('aria-current'); }); }), { rootMargin: '-45% 0px -50% 0px' });
document.querySelectorAll('#wmLevels .rk[data-r]').forEach(e => { const r = +e.dataset.r; e.style.background = r ? RAMP[r - 1] : NOVAL; e.style.color = inkOn(r); });   // the legend in the map's own colours, before the map loads
W.coreP = (async () => {
  Social.start();   // its map and its files, at once
  const [meta, doc, comm, sd] = await Promise.all(['meta.json', 'wcrp_rvi_barrio.json', 'wcrp.geojson', 'wcrp_social.json'].map(f => fetchJson('data/' + f)));
  W.doc = doc; W.comm = comm; W.ids = doc.geo.ids; W.at = new Map(W.ids.map((g, i) => [g, i]));
  for (const v of doc.vars) { const m = /^rvi_(\w+)_(orig|rebuild)$/.exec(v.key); if (m) (W.v[m[2]] = W.v[m[2]] || {})[m[1]] = Object.values(v.years)[0]; }
  const last = sd.geo.names.length - 1;   // the last row is Puerto Rico
  W.code = new Map(sd.geo.ids.slice(0, last).map((c, i) => [c, sd.geo.names[i]]));
  W.names = sd.geo.names.slice(0, last).sort((a, b) => a.localeCompare(b, 'es'));
  $('#snapshotLabel').innerHTML = `<b>${esc(snapshotLabel(meta.label))}</b>`;
  document.querySelectorAll('.snap').forEach(e => e.textContent = snapshotLabel(meta.label));
  return sd;
})();
(async function init() {
  let map2 = null;
  try {
    const sd = await W.coreP;
    const view = readHash();
    for (const s of ['#scMuni', '#wmMuni']) { $(s).insertAdjacentHTML('beforeend', W.names.map(n => `<option>${esc(n)}</option>`).join('')); $(s).value = W.muni; $(s).onchange = e => setMuni(e.target.value); }
    initVulnControls();
    renderAbout();
    map2 = view ? loadVuln() : null;   // an address that names a view of the vulnerability map (the dictionary's links, a shared view, an old #v=change)
    await Social.init(sd);   // it draws what it can when one of its files fails, and says so
    performance.mark('ready');
  } catch (e) {
    console.error(e);
    $('#scStatus').textContent = T('The data could not be loaded. Check your connection and reload the page.');
  } finally {   // whatever happened above
    readyNow();   // the base maps load now, whether or not the data did, the vulnerability map loads on approach and links to parts of the page work (review of PR #69: a failed Social Capital file kept map 2 from loading)
    document.querySelectorAll('.block[id], .hero[id]').forEach(s => obs.observe(s));
    new IntersectionObserver(en => { if (en.some(x => x.isIntersecting)) quiet(loadVuln()); }, { rootMargin: '400px 0px' }).observe($('#vulnerability'));   // once the summary tables are drawn, so the section is where it stays
    if (map2) quiet(map2.then(() => $('#vulnerability').scrollIntoView()));
    else revealHash();   // a link to a part of the page: there, now that what comes before it is drawn
  }
})();
