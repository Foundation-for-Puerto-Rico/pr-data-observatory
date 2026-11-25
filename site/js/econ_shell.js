/* PR Data Observatory: the Economy tab's shell on the 2D map. The tab's engine (js/core/time … panel.js) and economy.js load the first time
   something needs them: the Economy tab, the chat, the catalog's "show on map", or an address that carries an Economy view (e=, ix=, sc=,
   wb=, wc=, or an old s= of the retired shading menu). Until then this stands in for window.ECON: the address keeps the view a link brought, the "layers on" chip lists nothing and
   Turn all off has nothing to take off, and any other call to ECON.api loads the engine and then answers. Once economy.js runs it puts the
   real window.ECON in place (econInit) and its own econShown replaces the one below; a caller that kept ECON.api from before reaches the
   real methods through the proxy. docs/performance.md, "Make room 4". */
const ECON_JS = ['js/core/time.js?v=1', 'js/core/format.js?v=2', 'js/core/normalize.js?v=4', 'js/core/reliability.js?v=4', 'js/core/engine.js?v=11', 'js/core/adapters.js?v=15', 'js/core/datasets.js?v=29', 'js/core/popup.js?v=5', 'js/core/panel.js?v=7', 'js/economy.js?v=87'];   // in the order the page loaded them
function ecCentroid(g) {   // also used before the tab loads (mapextras.js town names): area-weighted centroid of the largest polygon, so islands and detached parts do not drag the point into the sea
  const polys = g.type === 'Polygon' ? [g.coordinates] : g.coordinates; let best = null, bestA = -1;
  for (const p of polys) { const r = p[0]; let a = 0, cx = 0, cy = 0; for (let i = 0, j = r.length - 1; i < r.length; j = i++) { const f = r[j][0] * r[i][1] - r[i][0] * r[j][1]; a += f; cx += (r[j][0] + r[i][0]) * f; cy += (r[j][1] + r[i][1]) * f; } a /= 2; if (Math.abs(a) > bestA) { bestA = Math.abs(a); best = a ? [cy / (6 * a), cx / (6 * a)] : [r[0][1], r[0][0]]; } }
  return best;
}
let econLoadP = null;
function econLoad() {   // the scripts in order, each once, and the tab's Spanish (I18N.load); a failure can be tried again
  if (econLoadP) return econLoadP;
  const add = (src) => new Promise((ok, fail) => { const s = document.createElement('script'); s.src = src; s.onload = ok; s.onerror = () => { s.remove(); fail(new Error(src)); }; document.body.appendChild(s); });
  const es = I18N.load('economy').catch(() => null);   // alongside the engine; economy.js waits for it (econInit draws text at once), and without it the tab works in English
  return econLoadP = ECON_JS.slice(0, -1).reduce((p, src) => p.then(() => add(src)), Promise.resolve()).then(() => es).then(() => add(ECON_JS[ECON_JS.length - 1]))
    .then(() => window.ECON)
    .catch(e => { econLoadP = null; toast(T('The Analysis tab could not be loaded. Check your connection and try again.'), 6000); throw e; });
}
window.ECON = (() => {
  const dec = (s) => { try { return decodeURIComponent(s); } catch { return ''; } };
  const first = parseHash(), pending = () => first;   // the address the page opened with, read now: app.js rewrites it once the map is ready, and economy.js boots from this copy (EC.pending)
  const real = () => (window.ECON && !window.ECON.shell ? window.ECON : null);
  const idle = { places: () => [], active: () => [], state: () => ({ year: null, base: 2014, selected: null, layers: [] }), snap: () => ({ layers: [], ix: null, sc: null }), restore() {}, clear() {}, remove() {} };
  const api = new Proxy({}, { get(_, k) {
    const R = real(); if (R) return R.api[k];
    if (typeof k !== 'string' || k === 'then' || k === 'mapless' || k === 'page') return undefined;   // not methods: the map has a map (chat.js chMapless), and the proxy is not a promise
    if (k === 'ready') return () => econLoad().then(E => E.api.ready()).catch(() => false);
    if (k in idle) return idle[k];
    return (...a) => econLoad().then(E => E.api[k](...a));
  } });
  return {
    shell: true, opened: first, api, claims: () => false,
    loadLevel: (...a) => econLoad().then(E => E.loadLevel(...a)), loadLevelFile: (...a) => econLoad().then(E => E.loadLevelFile(...a)),
    encode: () => (pending().e ? dec(pending().e) : ''),
    extra: () => { const h = pending(); return [h.ey ? 'ey=' + h.ey : '', h.eb ? 'eb=' + h.eb : '', h.ix ? 'ix=' + h.ix : '', h.sc ? 'sc=' + h.sc : ''].filter(Boolean); },
  };
})();
function econShown(name) {   // app.js calls it on every tab change; economy.js replaces it with its own when it runs
  if (name !== 'economy' || !window.ECON.shell) return;
  const root = $('#econRoot'); if (root && !root.children.length) root.innerHTML = `<div class="note" role="status">${esc(T('Loading the economy data…'))}</div>`;
  econLoad().then(() => { const p = $('#tab-economy'); if (!window.ECON.shell && p && p.classList.contains('active')) econShown(name); })   // the tab may have been left while it loaded
    .catch(() => { if (root) root.innerHTML = `<div class="note">${esc(T('The Analysis tab could not be loaded. Check your connection and try again.'))}</div>`; });
}
{
  const _onMapReady = window.onMapReady;
  window.onMapReady = async function () {   // a link with an Economy view loads the engine at once, as the page did before
    const h = window.ECON.opened || {}; if (h.e || h.ix || h.sc || h.wb || h.wc || (h.s && typeof SHADE_DS !== 'undefined' && Core.viewstate.has(SHADE_DS, h.s))) { window.ECON.fromLink = true; econLoad().catch(() => { window.ECON.fromLink = false; }); }   // fromLink: economy.js opens the tab for the link, but not after a failed load is tried again later
    if (_onMapReady) await _onMapReady();
  };
}
