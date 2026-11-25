/* PR Data Observatory: helpers shared by the three pages. Load before the page script. */

const $ = (s) => document.querySelector(s);
const fmt = (n, d = 0) => I18N.fmt(n, d);   // locale-aware: Spanish in Puerto Rico uses the US number form (1,234.5)
const esc = (s) => s == null ? '' : String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
const norm = (s) => (s || '').normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase().trim();
// Every data file the pages read comes through these two. A failed answer, or one that is not whole JSON, is tried twice more (after 1 and 3
// seconds) with the browser's cache bypassed: GitHub Pages keeps each file for 10 minutes, and a request made while the site is being
// republished can get an error or a cut file that would otherwise be served again until it expires.
async function fetchRetry(path, read = (r) => r.json(), waits = [1000, 3000]) {
  let last;
  netBusy++;
  try {
    for (let k = 0; k <= waits.length; k++) {
      try {
        const r = await fetch(path, k ? { cache: 'reload' } : undefined);
        if (!r.ok) throw new Error(`${path}: ${r.status}`);
        return await read(r);
      } catch (e) {
        last = e;
        if (k < waits.length) await new Promise(ok => setTimeout(ok, waits[k]));
      }
    }
  } finally { netBusy--; }
  throw last;
}
let netBusy = 0;   // data files being fetched: the glossary waits for none (below)
const fetchJson = (path) => fetchRetry(path);
// The index of the dictionary and its sources (data/catalog_index.json, catalog.py) are not in catalog.json, so the map's first load stays small. Fetched once, on
// first use, into the catalog object (cat.index, cat.sources). Resolves to the catalog, or null when there is none; a failed fetch is tried again next time.
const CAT_INDEX = new WeakMap();
function withIndex(cat) {
  if (!cat || cat.index) return Promise.resolve(cat || null);
  if (!CAT_INDEX.has(cat)) CAT_INDEX.set(cat, fetchJson('data/catalog_index.json').then(x => { cat.index = x.index; cat.sources = x.sources; return cat; }, e => { CAT_INDEX.delete(cat); throw e; }));
  return CAT_INDEX.get(cat);
}
const humanize = (s) => (s || '').replace(/_/g, ' ').replace(/^./, c => c.toUpperCase());
// Only http(s) links from third-party data become hrefs (blocks javascript: and data: URLs).
const safeUrl = (u) => { try { const x = new URL(/^https?:\/\//i.test(u) ? u : 'https://' + u); return /^https?:$/.test(x.protocol) ? x.href : null; } catch { return null; } };
const helpBtn = (key) => `<button type="button" class="help-btn" data-help="${key}" aria-label="${esc(T('What is this?'))}"><span class="ms-icon" aria-hidden="true">help</span></button>`;
// The build writes the snapshot label in English ("Snapshot 2026-10"); show it in the page language.
const snapshotLabel = (label) => { const m = /^Snapshot\s+(.+)$/.exec(label || ''); return m ? T('Snapshot {date}', { date: m[1] }) : (label || '—'); };

// ── Vocabulary of the data contract, for the catalog tab and the dictionary filters ───────────────────────────
// Geography levels and license classes are the ids of dictionary_src/datasets.json (contract.py). A class is the strictest of the sources an entry uses.
const LEVEL_LABEL = () => ({ island: T('Whole island'), region: T('Region'), municipio: T('Municipality'), barrio: T('Barrio'), tract: T('Census tract'), 'block-group': T('Census block group'), block: T('Census block'), point: T('Points (places, stops)'), line: T('Lines (routes)'), polygon: T('Areas'), raster: T('Grid'), network: T('Network') });
const LICENCE_LABEL = () => ({ open: T('Open license'), 'open-with-conditions': T('Open license, with conditions'), own: T("FPR's own"), unstated: T('License not stated'), 'licensed-not-open': T('Licensed, not open') });
const LICENCE_RANK = { own: 0, open: 0, 'open-with-conditions': 1, unstated: 2, 'licensed-not-open': 3 };
const strictestLicence = (classes) => { const k = classes.filter(x => x in LICENCE_RANK); return k.length ? k.reduce((a, b) => LICENCE_RANK[b] > LICENCE_RANK[a] ? b : a) : null; };
// Entries run from 1851 (storm tracks) to 2100 (sea level scenarios): the year filter lists 2000 up to the snapshot year, then "before 2000" and "projections".
const yearOptions = (snapYear) => [['future', T('Projections (after {year})', { year: snapYear })], ...Array.from({ length: Math.max(0, snapYear - 1999) }, (_, i) => [String(snapYear - i), String(snapYear - i)]), ['past', T('Before 2000')]];
const coversYear = (years, y, snapYear) => !y || (!!years && (y === 'future' ? years[1] > snapYear : y === 'past' ? years[0] < 2000 : years[0] <= +y && +y <= years[1]));

// ── Timetable replay (trips*.json), shared by the 2D "vehicles now" layer and the 3D view ──
// Format 2 (trip_paths.py): each trip names a stop pattern ("k": a path along the route line, [lng, lat, meters]), where its stops are on it ("s")
// and its timetable ("t": seconds after midnight). tripPoints() gives [lng, lat, seconds] for every point of the path, the time between two stops
// spread by distance, so a vehicle follows the roads. Format 1 files (a straight "p" list of stops) still work.
function tripPoints(doc, t) {
  if (t.p) return t.p;
  if (t._p) return t._p;
  const path = doc.paths[t.k], out = [];
  for (let j = 0; j < t.s.length - 1; j++) {
    const a = t.s[j], b = t.s[j + 1], t0 = t.t[j], t1 = t.t[j + 1], m0 = path[a][2], m1 = path[b][2];
    if (j === 0) out.push([path[a][0], path[a][1], t0]);
    if (a === b) { out.push([path[b][0], path[b][1], t1]); continue; }   // two stops at one place: the vehicle waits there
    for (let i = a + 1; i <= b; i++) out.push([path[i][0], path[i][1], i === b ? t1 : m1 === m0 ? t0 : t0 + (t1 - t0) * (path[i][2] - m0) / (m1 - m0)]);
  }
  return (t._p = out);
}
const tripStart = (t) => t.t ? t.t[0] : t.p[0][2];
const tripEnd = (t) => t.t ? t.t[t.t.length - 1] : t.p[t.p.length - 1][2];

// ── WCRP communities popup, shared by the 2D map and the 3D view ─────────────
const WCRP_ESTADO = { plan_aprobado: T('Plan approved by the Puerto Rico Department of Housing'), en_proceso: T('Plan in progress') };
const WCRP_UBICACION = {   // where the point comes from (wcrp.py); the plans draw their own area only in a PDF map
  comunidad_especial: T('Point inside the Comunidad Especial (Junta de Planificación, 2006)'),
  osm: T('Point at the OpenStreetMap place or landmark'),
  barrio_censo: T('Point inside the Census barrio'),
  pueblo: T('Point at the town center'),
  manual: T('Point at coordinates the plan gives'),
};
function wcrpPopup(list) {   // one marker can hold several plans at the same point (for example Villa Calma 1 and 2)
  return `<div class="pop">${list.map(p => `<h4><img src="img/${p.estado === 'plan_aprobado' ? 'wcrp-pin' : 'wcrp-pin-open'}.svg" alt="" width="16" height="20" style="margin-right:6px;vertical-align:-3px">${esc(p.comunidad)}</h4><div class="meta">${esc(T('WCRP community'))} · ${esc(p.municipio)} ${p.region ? ` · ${esc(T('WCRP region: {region}', { region: p.region }))}` : ''}</div><div class="meta"><b>${esc(WCRP_ESTADO[p.estado] || p.estado)}</b></div><div class="meta">${esc(T('Led by {name}', { name: p.subrecipiente }))}</div><div class="meta">${esc(WCRP_UBICACION[p.ubicacion] || '')}${p.referencia ? `: ${esc(p.referencia)}` : ''}.${p.estado === 'plan_aprobado' && p.ubicacion !== 'poblacion' ? ` ${esc(T("The plan's own boundary is in its PDF map."))}` : ''}</div>`).join('')}<div class="src">${esc(T('Foundation for Puerto Rico, Whole Community Resilience Planning (WCRP) program, list of 2026-10-06'))}</div></div>`;
}

// ── Off-canvas panel on phones ────────────────────────────────────────────────
const mobileQuery = window.matchMedia('(max-width: 860px)');
const isMobile = () => mobileQuery.matches;
function setPanel(open) {
  const p = $('#panel'); if (!p) return;
  p.classList.toggle('open', open);
  const bd = $('#backdrop'); if (bd) bd.classList.toggle('show', open && isMobile());
  const mb = $('#menuBtn'); if (mb) mb.setAttribute('aria-expanded', String(open || !isMobile()));
  // a closed off-canvas panel must not be reachable by keyboard or screen reader
  if (isMobile() && !open) p.setAttribute('inert', ''); else p.removeAttribute('inert');
}
function initPanel() {
  if (!$('#panel')) return;
  const fold = (on) => { document.body.classList.toggle('panel-folded', on); $('#menuBtn').setAttribute('aria-expanded', !on); dispatchEvent(new Event('resize')); };
  mobileQuery.addEventListener('change', () => { fold(false); setPanel(false); });
  $('#menuBtn').onclick = () => isMobile() ? setPanel(!$('#panel').classList.contains('open')) : (fold(false), $('#panelClose').focus());
  $('#panelClose').onclick = () => { isMobile() ? setPanel(false) : fold(true); $('#menuBtn').focus(); };
  $('#backdrop').onclick = () => setPanel(false);
  setPanel(false);
}

// ── Collapsible groups (Layers tab, map and 3D) ── each `h2.sec` and what follows it, to the next one, is a WAI-ARIA accordion group, closed at first.
// A closed group says how much of it is on ("2 layers on": checked layers and set shading selects; not rows marked nocount: limits, 3D scene; js/core/layers.js).
function foldCount(body) {
  return body.querySelectorAll('.layer:not(.nocount) input[type=checkbox]:checked, #walkRings:checked').length + [...body.querySelectorAll('select[data-layer-select]')].filter(s => s.value).length;
}
function initFolds(root) {
  if (!root || root.foldRefresh) return;
  const folds = [...root.querySelectorAll(':scope > h2.sec')].map((h, i) => {
    const fold = document.createElement('div'), body = document.createElement('div');
    fold.className = 'fold'; body.className = 'fold-body'; body.id = `${root.id}-group-${i}`; body.hidden = true;
    const rest = [];
    for (let n = h.nextSibling; n && !(n.nodeType === 1 && n.matches('h2.sec')); n = n.nextSibling) rest.push(n);
    h.before(fold); fold.append(h, body); rest.forEach(n => body.append(n));
    const btn = document.createElement('button'), title = document.createElement('span'), count = document.createElement('span'), chev = document.createElement('span');
    btn.type = 'button'; btn.className = 'fold-toggle'; btn.setAttribute('aria-expanded', 'false'); btn.setAttribute('aria-controls', body.id);
    title.className = 'fold-title'; while (h.firstChild) title.append(h.firstChild);
    count.className = 'fold-count'; count.hidden = true;
    chev.className = 'ms-icon fold-chevron'; chev.setAttribute('aria-hidden', 'true'); chev.textContent = 'keyboard_arrow_down';
    btn.append(title, count, chev); h.append(btn);
    btn.onclick = () => { const open = btn.getAttribute('aria-expanded') !== 'true'; btn.setAttribute('aria-expanded', String(open)); body.hidden = !open; };
    return { body, count };
  });
  root.foldRefresh = () => folds.forEach(f => { const n = foldCount(f.body); f.count.textContent = n ? Tn(n, '{n} layer on', '{n} layers on', { n }) : ''; f.count.hidden = !n; });
  root.addEventListener('change', root.foldRefresh, true);   // capture phase: layers are also switched from code, with a change event that does not bubble
  root.foldRefresh();
}
const refreshFolds = () => { const r = document.getElementById('tab-layers'); if (r && r.foldRefresh) r.foldRefresh(); };   // for code that sets a layer or a shading choice without a change event

// ── Tabs (WAI-ARIA tablist, arrow keys move between tabs) ─────────────────────
// The 2D map groups its panes under four tabs (navigation plan, decision 81): a main tab [data-main] holds a row of sub-tabs (.subtabs[data-group]), one per pane.
// showTab takes a pane's name (the old tab names: 'economy', 'layers', 'rank'… stay valid) or a main tab's; the 3D view has no groups and works as before.
const tabLast = {};
function showTab(name, { open = true } = {}) {
  const m = document.querySelector(`.tabs [data-main="${name}"]`); if (m) name = tabLast[name] || m.dataset.tab;
  const st = document.querySelector(`.subtabs [data-tab="${name}"]`), group = st ? st.closest('.subtabs').dataset.group : null; if (group) tabLast[group] = name;
  const sel = (b, on) => { b.classList.toggle('active', on); b.setAttribute('aria-selected', String(on)); b.tabIndex = on ? 0 : -1; if (on && b.scrollIntoView) b.scrollIntoView({ block: 'nearest', inline: 'nearest' }); };
  document.querySelectorAll('.tabs button').forEach(b => { const on = group ? b.dataset.main === group : b.dataset.tab === name; sel(b, on); if (on && group) b.setAttribute('aria-controls', 'tab-' + name); });
  document.querySelectorAll('.subtabs').forEach(s => { s.hidden = s.dataset.group !== group; s.querySelectorAll('button').forEach(b => sel(b, b.dataset.tab === name)); });
  document.querySelectorAll('.tab-page').forEach(p => p.classList.toggle('active', p.id === 'tab-' + name));
  refreshFolds();   // a layer may have been switched from another tab
  if (typeof onTabShown === 'function') onTabShown(name);
  if (isMobile() && open) setPanel(true);
}
function initTabs() {
  for (const list of document.querySelectorAll('.tabs, .subtabs')) {   // arrow keys move within one row
    const tabs = [...list.querySelectorAll('button')];
  tabs.forEach((b, i) => {
    b.onclick = () => showTab(b.dataset.main || b.dataset.tab);
    b.onkeydown = e => { if (e.key !== 'ArrowRight' && e.key !== 'ArrowLeft') return; const n = tabs[(i + (e.key === 'ArrowRight' ? 1 : tabs.length - 1)) % tabs.length]; n.focus(); showTab(n.dataset.main || n.dataset.tab, { open: false }); };
  });
  }
}

// ── Help popover: opened by any [data-help] button; lookup(key) returns [title, text] ──
let helpTrigger = null;
function hideHelp(restoreFocus) { $('#helpPop').classList.remove('show'); if (restoreFocus && helpTrigger) helpTrigger.focus({ preventScroll: true }); }
function initHelp(lookup, { onOutsideClick } = {}) {
  document.addEventListener('click', e => {
    const h = e.target.closest('[data-help]');
    if (h) {
      const entry = lookup(h.dataset.help); if (!entry) return;
      e.preventDefault(); e.stopPropagation();
      helpTrigger = h;
      $('#helpTitle').textContent = entry[0]; $('#helpBody').textContent = entry[1];
      const pop = $('#helpPop'); pop.classList.add('show');
      const r = h.getBoundingClientRect(), pw = pop.offsetWidth, ph = pop.offsetHeight;
      pop.style.left = Math.max(8, Math.min(r.left, window.innerWidth - pw - 8)) + 'px';
      pop.style.top = Math.max(8, r.bottom + 6 + ph > window.innerHeight - 8 ? r.top - ph - 6 : r.bottom + 6) + 'px';
      $('#helpClose').focus({ preventScroll: true });
      return;
    }
    if (!e.target.closest('#helpPop')) hideHelp(false);
    if (onOutsideClick) onOutsideClick(e);
  });
  $('#helpClose').onclick = () => hideHelp(true);
  document.addEventListener('keydown', e => {
    if (e.key !== 'Escape') return;
    if ($('#helpPop').classList.contains('show')) hideHelp(true);
    else if ($('#panel') && isMobile() && $('#panel').classList.contains('open')) { setPanel(false); $('#menuBtn').focus(); }
  });
}

// If the Material Symbols font has not loaded a few seconds after the page, hide icon text instead of showing ligature words.
window.addEventListener('load', () => setTimeout(() => {
  if (!document.fonts || !document.fonts.load) return;
  document.fonts.load('24px "Material Symbols Rounded"', 'home').then(f => { if (!f.length) document.documentElement.classList.add('no-icons'); }).catch(() => document.documentElement.classList.add('no-icons'));
}, 3500));
// The glossary (js/core/glossary.js, docs/glossary.md) loads once the page has its data, is ready (READY_PAGES mark it) and the browser is idle.
const READY_PAGES = ['map', 'threed', 'wcrp', 'datamgmt'];
window.addEventListener('load', function glossary() {
  (window.requestIdleCallback || setTimeout)(() => {
    const page = (document.querySelector('script[data-page]') || { dataset: {} }).dataset.page;
    if (READY_PAGES.includes(page) && !performance.getEntriesByName('ready').length && (glossary.r = (glossary.r || 0) + 1) < 240) return setTimeout(glossary, 500);
    if (netBusy && (glossary.n = (glossary.n || 0) + 1) < 60) return setTimeout(glossary, 500);
    const s = document.createElement('script'); s.src = 'js/core/glossary.js?v=8'; document.body.appendChild(s);
  }, { timeout: 2000 });
});
