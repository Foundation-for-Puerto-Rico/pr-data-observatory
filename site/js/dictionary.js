/* PR Data Observatory: data dictionary page.
   Every dataset, variable, layer and measure has an entry: meaning, unit, years, how it is computed, cautions, sources, where it appears, how to cite.
   dictionary.py builds data/dictionary.json from dictionary_src/ (entries, sources, glossary) and the series catalogs, and makes from it the files this page reads
   (docs/performance.md): data/dictionary_list.json before it is ready (the list, the filters, the search words, the sources, the glossary) and the rest of each entry
   (definition, method, cautions, codes, the whole summaries, how to read it) in data/dictionary_detail_<domain>.json, fetched the first time an entry of that domain
   is opened, printed or exported. The Spanish travels in the same files (see Spanish, below). */

const D = { data: null, entries: [], byId: {}, sources: {}, f: { q: '', domain: '', source: '', kind: '', time: '', level: '', year: '', licence: '', moe: false, file: '' }, series: {} };
const CANON = 'https://observatory.foundationpr.org/';
const KIND = { variable: T('Variable'), layer: T('Map layer'), table: T('Published table'), boundary: T('Boundary'), category: T('Category'), measure: T('Measure'), method: T('Method') };
const VTYPE = { count: T('Count'), rate: T('Rate or share'), level: T('Typical value or amount'), ratio: T('Ratio'), index: T('Index'), flag: T('Yes or no'), code: T('Code'), text: T('Text'), date: T('Date'), geometry: T('Shape on the map') };
const TIME = { snapshot: T('One snapshot'), annual: T('Every year'), 'five-year window': T('Five-year windows'), decennial: T('Every ten years'), 'event-based': T('By event'), live: T('Live'), static: T('Not tied to a year') };
const slug = (s) => norm(s).replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
const baseUrl = () => /^(localhost|127\.|\[::1\])/.test(location.hostname) ? CANON : location.href.replace(/[#?].*$/, '').replace(/[^/]*$/, '');
const longDate = (d) => I18N.date(d);
const safeHref = (u) => { try { const x = new URL(u, location.href); return /^https?:$/.test(x.protocol) ? x.href : null; } catch { return null; } };
const sizeText = (b) => b >= 1048576 ? (b / 1048576).toFixed(1) + ' MB' : Math.max(1, Math.round(b / 1024)) + ' KB';

function yearsText(e) {
  const c = e.coverage || {};
  if (c.timeline === 'snapshot') return T('Snapshot {year}', { year: c.last || c.first || (D.data.snapshot_built || '').slice(0, 4) });
  if (c.first && c.last) return c.first === c.last ? String(c.first) : `${c.first}–${c.last}`;
  return TIME[c.timeline] || '';
}
// ── The rest of each entry: one file per top-level domain, fetched once, the first time it is needed ──
const DETAIL = {};   // {file: promise}
const detailFile = (e) => `dictionary_detail_${e.domain.split('.')[0]}.json`;
function mergeDetail(j) {
  for (const [id, d] of Object.entries(j.entries || {})) {
    const e = D.byId[id]; if (!e) continue;
    const { view, ...rest } = d; Object.assign(e, rest); if (view) e.where.view = view; e._full = true;
  }
}
// On the Spanish page each detail file has a Spanish one (dictionary_detail_<domain>_es.json: "how to read it"), fetched with it; without it the entry shows the English.
const esFile = (f) => f.replace(/\.json$/, '_es.json');
const mergeEs = (j) => { for (const [id, d] of Object.entries(j.entries || {})) if (D.byId[id]) Object.assign(D.byId[id], d); };
function withDetail(list) {
  const files = [...new Set(list.filter(e => !e._full).map(detailFile))];
  const es = LANG === 'es' ? files.map(f => DETAIL[esFile(f)] || (DETAIL[esFile(f)] = fetchJson('data/' + esFile(f)).then(mergeEs, () => { delete DETAIL[esFile(f)]; }))) : [];
  return Promise.all([...files.map(f => DETAIL[f] || (DETAIL[f] = fetchJson('data/' + f).then(mergeDetail, err => { delete DETAIL[f]; throw err; }))), ...es]);
}
function withDetailNow(list) {   // printing cannot wait for a fetch: the files still missing are read before the page is printed
  for (const f of new Set(list.filter(e => !e._full).map(detailFile))) {
    for (const [g, merge] of [[f, mergeDetail], ...(LANG === 'es' ? [[esFile(f), mergeEs]] : [])]) {
      try { const x = new XMLHttpRequest(); x.open('GET', 'data/' + g, false); x.send(); if (x.status === 200) merge(JSON.parse(x.responseText)); } catch { /* printed without it: the entry says it is loading, or shows the English */ }
    }
  }
}
const resolveId = (id) => D.byId[id] ? id : (D.data.id_alias || {})[id];

// Domains come from the registry (dictionary_src/domains.json via dictionary.json): the page never hard-codes a domain name or how many there are.
const LANG = I18N.lang;
const REG = () => (D.data && D.data.domain_registry) || {};
const dname = (id) => (REG()[id] && I18N.name(REG()[id])) || id;
const dpath = (id) => { const d = REG()[id]; return d && d.parent ? `${dname(d.parent)} › ${dname(id)}` : dname(id); };
const dmatch = (e, dom) => (e.domains || [e.domain]).some(x => x === dom || x.startsWith(dom + '.'));
const dcount = (dom) => D.entries.filter(e => dmatch(e, dom)).length;
const dsystem = (id) => !!(REG()[id] || {}).system;

// ── Spanish ──────────────────────────────────────────────────────────────────
// The Spanish of dictionary_src/es/ is in files that only the Spanish page reads (dictionary.py spanish_page_files), so the English page loads what it did before.
// dictionary_list_es.json (names, short labels keyed by the English label, source cards, area and group texts, the search words of "how to read it", the entries held
// for review) is fetched once the page is ready; until it is in, the page shows the English, marked lang="en", and then draws the list and the sources again, keeping
// what is open and where the reader is. "How to read it" comes with the detail files (above). A text without Spanish, and every label of an entry held for review
// (hold_es), stays English. Group names stay English inside (they are keys of the domain notes and of the list) and are shown through lblHtml().
const esOf = (o, f) => (LANG === 'es' && o && o[f + '_es']) || '';   // the Spanish of field f, or ''
const tx = (o, f) => esOf(o, f) ? esc(o[f + '_es']) : I18N.en(esc(o[f]));   // field f as HTML in the page language
const lbl = (v, e) => (LANG === 'es' && v && !(e && e.hold_es) && (D.data.labels_es || {})[v]) || '';   // a unit, geography, group or update frequency in Spanish, or ''
const lblHtml = (v, e) => lbl(v, e) ? esc(lbl(v, e)) : I18N.en(esc(v));
const nameOf = (e) => esOf(e, 'name') || e.name;   // the name the reader sees
function applySpanish(x) {
  const held = new Set(x.held || []), w = x.w || {};
  D.data.labels_es = x.labels || {};
  for (const e of D.entries) {
    if (x.names[e.id]) e.name_es = x.names[e.id];
    if (held.has(e.id)) e.hold_es = true;
    e._hay += ' ' + norm([e.name_es, lbl(e.group, e), lbl(e.unit, e), w[e.id]].filter(Boolean).join(' '));
  }
  for (const [id, s] of Object.entries(x.sources || {})) if (D.sources[id]) for (const [k, v] of Object.entries(s)) D.sources[id][k + '_es'] = v;
  for (const [d, i] of Object.entries(x.domain_info || {})) { const o = (D.data.domain_info[d] = D.data.domain_info[d] || {}); if (i.summary) o.summary_es = i.summary; if (i.groups) o.groups_es = i.groups; }
}
// Whether the reader has moved the page since it loaded: until then a link to #<id> still decides where the page is (redraw).
let readerMoved = false;
for (const t of ['wheel', 'touchmove', 'keydown', 'mousedown']) window.addEventListener(t, () => { readerMoved = true; }, { passive: true, once: true });
const FOCUSABLE = 'a, button:not(.gl-mark), summary, input, select, textarea, [tabindex]:not(.gl-mark)';   // the glossary's marks (gl-mark) come and go
function focusKey() {   // the focused element inside the list or the sources, as the id of its card or entry and its place among the card's focusable elements
  const a = document.activeElement; if (!a || a === document.body || !a.closest('#dList, #srcList')) return null;
  const host = a.closest('#dList [id], #srcList [id]'); if (!host) return null;
  return { id: host.id, i: a === host ? -1 : [...host.querySelectorAll(FOCUSABLE)].indexOf(a.closest(FOCUSABLE)) };
}
// A smooth scroll to a linked entry (openEntry) can still be under way when the Spanish is drawn, and it ends where the entry was in the English list. So the entry is
// put at the top now and again once the page has stopped scrolling (150 ms without a scroll event, at most 4 s), unless the reader has moved the page meanwhile.
function keepAtTop(id) {
  const put = () => {   // window.scrollTo, not scrollIntoView: on a phone (390 px) Chrome left scrollIntoView without effect here
    const el = document.getElementById(id), pad = parseFloat(getComputedStyle(document.documentElement).scrollPaddingTop) || 0;
    if (el && !readerMoved) window.scrollTo({ top: window.scrollY + el.getBoundingClientRect().top - pad, behavior: 'instant' });
  };
  let t; const t0 = Date.now(), done = () => { window.removeEventListener('scroll', on); put(); }, on = () => { clearTimeout(t); t = setTimeout(done, Date.now() - t0 > 4000 ? 0 : 150); };
  put(); window.addEventListener('scroll', on, { passive: true }); t = setTimeout(done, 150);
}
function redraw() {   // the list and the sources in Spanish, with the same entries open, the same element focused and the same element at the same place on the screen
  const els = () => [...document.querySelectorAll('#dList details.de, #srcList .src-card')];
  // at the top of the page nothing is kept in place: the page stays at its top (the first entry, below the fold, moved a phone's page down by the Spanish of the text above it)
  const anchor = window.scrollY > 0 && els().find(el => el.getBoundingClientRect().bottom > 0), id = anchor && anchor.id, top = anchor && anchor.getBoundingClientRect().top;
  const open = [...document.querySelectorAll('#dList details.de[open]')].map(d => d.id), fk = focusKey();
  let hash = ''; try { hash = decodeURIComponent(location.hash.slice(1)); } catch { /* a broken % in the link */ }
  renderList(); renderSources();
  for (const i of open) { const d = document.getElementById(i); if (d && d.matches('details.de')) { d.open = true; fillBody(d); } }
  const linked = hash && !readerMoved && document.getElementById(resolveId(hash) || hash);
  if (linked) keepAtTop(linked.id);   // opened by a link and not moved since: the linked entry ends at the top
  else { const again = id && document.getElementById(id); if (again) window.scrollBy(0, again.getBoundingClientRect().top - top); }
  if (fk) { const h = document.getElementById(fk.id), el = h && (fk.i < 0 ? h : [...h.querySelectorAll(FOCUSABLE)][fk.i]); if (el) el.focus({ preventScroll: true }); }
}
// The words of each entry's definition, method, geography, source notes, how to read it and cautions (dictionary.py PAGE_WORDS), fetched once the page is ready: until
// they are in, a search reads the names, groups, units, sources and summaries; then the list is drawn again if a search is typed.
async function loadWords() {
  let x; try { x = await fetchJson('data/dictionary_words.json'); } catch { return; }   // without it the search reads what it has
  const w = x.w || {};
  for (const e of D.entries) if (w[e.id]) e._hay += ' ' + w[e.id];
  if (D.f.q) redraw();
}
async function loadSpanish() {
  try { applySpanish(await fetchJson('data/dictionary_list_es.json')); } catch { return; }   // without it the page stays as it is: English, marked lang="en"
  redraw();
}

// ── Load ─────────────────────────────────────────────────────────────────────
async function boot() {
  try {
    D.data = await fetchJson('data/dictionary_list.json');
  } catch (e) { $('#dList').innerHTML = `<div class="note">${esc(T('The dictionary could not be loaded ({error}). Check your connection and reload.', { error: e.message }))}</div>`; return; }
  D.sources = D.data.sources;
  D.reg = { files: [] };   // registry.json loads after the first paint ('later' in routes.json): the geography filter, the file count and the files summary fill in then
  D.entries = D.data.entries.map(e => {
    e._levels = [];
    e._licence = strictestLicence((e.sources || []).map(id => (D.sources[id] || {}).licence_class));
    const srcNames = e.sources.map(id => (D.sources[id] || {}).name || id).join(' ');
    e._hay = norm([e.id, e.name, e.name_es, (e.domains || [e.domain]).map(dname).join(' '), e.group, lbl(e.group, e), KIND[e.kind], e.wp, e.unit, lbl(e.unit, e), srcNames].join(' '));   // wp, and the words of dictionary_words.json once in (loadWords): the words of the summaries, definition, method, geography, source notes, how to read (both languages) and cautions (dictionary.py search_words)
    return e;
  });
  D.entries.forEach(e => { D.byId[e.id] = e; });
  $('#snapshotLabel').textContent = snapshotLabel(D.data.snapshot);
  if (LANG !== 'en') $('#langNote').hidden = false;   // what is in Spanish and what is still English
  const q = new URLSearchParams(location.search);
  for (const k of ['q', 'domain', 'source', 'kind', 'time', 'level', 'year', 'licence', 'file']) if (q.get(k)) D.f[k] = q.get(k);
  if (D.f.domain && !REG()[D.f.domain]) D.f.domain = (D.data.legacy_domain_names || {})[D.f.domain] || '';   // links made before the domain registry used area names
  if (q.get('moe') === '1') D.f.moe = true;
  renderStats(); renderFilters(); renderDomainNav(); renderList(); renderSources(); renderGlossary(); renderFiles(); renderCiteSite(); wire();
  openFromHash(true);
  requestAnimationFrame(() => setTimeout(loadRegistry));   // after the first paint of the ready page: 'later' in routes.json
  requestAnimationFrame(() => setTimeout(loadWords));   // the search words of the long texts: 'later' in routes.json
  if (LANG === 'es') requestAnimationFrame(() => setTimeout(loadSpanish));   // after the first paint of the ready page: 'later' in routes.json
}
/** The data contract's registry (registry.json): the geography level of each published file, for the 'Any geography' filter, and the files summary. Optional: without it the page works with no level filter. */
async function loadRegistry() {
  try { D.reg = await fetchJson('data/registry.json'); } catch { return; }
  const fileLevel = Object.fromEntries((D.reg.files || []).map(f => [f.file, f.geography]));
  D.entries.forEach(e => { e._levels = [...new Set((e.where.files || []).map(r => fileLevel[r.split(':')[0]]).filter(l => l && l !== 'none'))]; });
  renderStats(); renderFilters(); renderFiles();
  if (D.f.level) renderList();   // a link that names a geography level waited for the registry
}

function renderStats() {
  const d = D.data, data = Object.values(D.sources).filter(s => s.kind === 'data').length;
  $('#dStats').innerHTML = [[D.entries.length, T('documented items')], [data, T('data sources')], [d.glossary.length, T('glossary terms')], ...(D.reg.files.length ? [[D.reg.files.length, D.reg.total_bytes ? T('published data files, {size}', { size: sizeText(D.reg.total_bytes) }) : T('published data files')]] : [])].map(([v, l]) => `<div class="kpi"><div class="v">${fmt(v)}</div><div class="l">${esc(l)}</div></div>`).join('');
}

// ── Filters and list ─────────────────────────────────────────────────────────
function renderFilters() {
  const count = (fn) => D.entries.filter(fn).length;
  $('#fDomain').innerHTML = `<option value="">${esc(T('All domains'))}</option>` + D.data.domains.map(d => `<option value="${esc(d)}">${esc(dcount(d) ? T('{name} ({n})', { name: dpath(d), n: dcount(d) }) : T('{name} (0, no data yet)', { name: dpath(d) }))}</option>`).join('');
  const used = Object.values(D.sources).filter(s => s.used_by).sort((a, b) => a.name.localeCompare(b.name));
  $('#fSource').innerHTML = `<option value="">${esc(T('All sources'))}</option>` + used.map(s => `<option value="${esc(s.id)}">${esc(s.name.length > 70 ? s.name.slice(0, 68) + '…' : s.name)} (${s.used_by})</option>`).join('');
  $('#fKind').innerHTML = `<option value="">${esc(T('All kinds'))}</option>` + Object.keys(KIND).filter(k => count(e => e.kind === k)).map(k => `<option value="${k}">${KIND[k]} (${count(e => e.kind === k)})</option>`).join('');
  $('#fTime').innerHTML = `<option value="">${esc(T('Any'))}</option>` + Object.keys(TIME).filter(k => count(e => (e.coverage || {}).timeline === k)).map(k => `<option value="${k}">${TIME[k]} (${count(e => (e.coverage || {}).timeline === k)})</option>`).join('');
  const lv = LEVEL_LABEL(), lc = LICENCE_LABEL();
  $('#fLevel').innerHTML = `<option value="">${esc(T('Any geography'))}</option>` + Object.keys(lv).filter(k => count(e => e._levels.includes(k))).map(k => `<option value="${k}">${esc(lv[k])} (${count(e => e._levels.includes(k))})</option>`).join('');
  $('#fYear').innerHTML = `<option value="">${esc(T('Any year'))}</option>` + yearOptions(snapYear()).map(([v, l]) => `<option value="${v}">${esc(l)} (${count(e => coversYear(yearsOf(e), v, snapYear()))})</option>`).join('');
  $('#fLicence').innerHTML = `<option value="">${esc(T('Any license'))}</option>` + Object.keys(lc).filter(k => count(e => e._licence === k)).map(k => `<option value="${k}">${esc(lc[k])} (${count(e => e._licence === k)})</option>`).join('');
  syncControls();
}
const snapYear = () => +((D.data && D.data.snapshot_built) || '').slice(0, 4) || 2026;
const yearsOf = (e) => { const c = e.coverage || {}; return c.first && c.last ? [c.first, c.last] : null; };
function syncControls() {
  $('#dq').value = D.f.q; $('#fDomain').value = D.f.domain; $('#fSource').value = D.f.source; $('#fKind').value = D.f.kind; $('#fTime').value = D.f.time; $('#fLevel').value = D.f.level; $('#fYear').value = D.f.year; $('#fLicence').value = D.f.licence; $('#fMoe').checked = D.f.moe;
  $('#dqClear').hidden = !D.f.q;
}
function renderDomainNav() {
  $('#domainNav').innerHTML = `<h2 class="side-h" data-gloss="domain-in-the-dictionary">${esc(T('Domains'))}</h2>` + `<button type="button" class="dn ${D.f.domain ? '' : 'on'}" data-domain="">${esc(T('All'))} <small>${D.entries.length}</small></button>` + D.data.domains.map(d => { const n = dcount(d), sub = REG()[d] && REG()[d].parent; return `<button type="button" class="dn ${sub ? 'sub' : ''} ${D.f.domain === d ? 'on' : ''}" data-domain="${esc(d)}" aria-pressed="${D.f.domain === d}">${esc(dname(d))} <small>${n || esc(T('none yet'))}</small></button>`; }).join('');
}
function filtered() {
  const f = D.f, toks = norm(f.q).split(/\s+/).filter(Boolean);
  let rows = D.entries.filter(e => (!f.domain || dmatch(e, f.domain)) && (!f.kind || e.kind === f.kind) && (!f.source || e.sources.includes(f.source)) && (!f.time || (e.coverage || {}).timeline === f.time) && (!f.level || e._levels.includes(f.level)) && coversYear(yearsOf(e), f.year, snapYear()) && (!f.licence || e._licence === f.licence) && (!f.moe || e.has_moe) && (!f.file || (e.where.files || []).some(x => x.split(':')[0] === f.file)) && toks.every(t => e._hay.includes(t)));
  if (toks.length) {
    const score = (e) => toks.reduce((s, t) => s + (norm(e.name).includes(t) || norm(e.name_es).includes(t) ? 6 : 0) + (norm(e.id).includes(t) ? 3 : 0) + (norm(e.group).includes(t) || norm(lbl(e.group, e)).includes(t) ? 2 : 0) + (e.wp.includes(t) ? 1 : 0), 0);
    rows = rows.map(e => [score(e), e]).sort((a, b) => b[0] - a[0] || nameOf(a[1]).localeCompare(nameOf(b[1]))).map(x => x[1]);
  }
  return rows;
}
// the Spanish summary (plain_es, from i18n_src/dictionary_plain.json) when there is one; else the English, marked lang="en"
const plainEs = (e) => LANG === 'es' && e.plain_es;
const oneEs = (e) => LANG === 'es' && e.one_es != null;   // the list shows the first sentence (one, one_es: dictionary.py first_sentence)
function summaryHtml(e) {
  const first = oneEs(e) ? e.one_es : e.one;
  const chips = [e.unit && (lbl(e.unit, e) || e.unit).length < 34 ? `<span class="chip g">${lblHtml(e.unit, e)}</span>` : '', yearsText(e) && (e.coverage || {}).timeline !== 'static' ? `<span class="chip b">${esc(yearsText(e))}</span>` : '', e.kind !== 'variable' ? `<span class="chip y">${esc(KIND[e.kind])}</span>` : ''].join('');
  return `<summary><span class="de-main"><span class="de-name">${tx(e, 'name')}</span><span class="de-one">${oneEs(e) ? esc(first) : I18N.en(esc(first))}</span></span><span class="de-meta">${chips}</span></summary>`;
}
function entryHtml(e) { return `<details class="de" id="${esc(e.id)}" data-id="${esc(e.id)}">${summaryHtml(e)}<div class="de-body"></div></details>`; }
function renderList() {
  const rows = filtered(), f = D.f, active = f.q || f.domain || f.source || f.kind || f.time || f.level || f.year || f.licence || f.moe || f.file;
  $('#dCount').textContent = active ? T('{n} of {m} items match your filters', { n: rows.length, m: D.entries.length }) : T('{n} of {m} items', { n: rows.length, m: D.entries.length });
  if (!rows.length) {
    const dd = f.domain && REG()[f.domain], bare = dd && !f.q && !f.source && !f.kind && !f.time && !f.level && !f.year && !f.licence && !f.moe && !f.file;
    $('#dList').innerHTML = bare ? `<div class="empty">${Th('<strong>{name}: no data yet.</strong> {description} Datasets that could fill this domain are listed in the wish list (see “Data inventory and wish list” below); ask the chat “What data is missing?”.', { name: dpath(f.domain), description: I18N.text(dd.description) })}</div>`
      : `<div class="empty">${esc(T('Nothing matches. Try fewer words, or reset the filters. If a dataset is missing from the observatory, ask the chat “What data is missing?”.'))}</div>`;
    return;
  }
  if (f.q) { $('#dList').innerHTML = rows.map(e => `<div class="flat-row"><div class="flat-dom">${esc(dpath(e.domain))} › ${lblHtml(e.group, e)}</div>${entryHtml(e)}</div>`).join(''); return; }
  const byDom = {}; rows.forEach(e => { ((byDom[e.domain] = byDom[e.domain] || {})[e.group] = byDom[e.domain][e.group] || []).push(e); });
  $('#dList').innerHTML = D.data.domains.filter(d => byDom[d]).map(d => {
    const groups = Object.entries(byDom[d]), n = groups.reduce((s, [, a]) => s + a.length, 0);
    // the long area text and the group notes: their Spanish (summary_es, groups_es) when the area has it, else the registry's Spanish description
    const info = (D.data.domain_info || {})[d] || {}, gi = LANG === 'en' ? (info.groups || {}) : (info.groups_es || {}), desc = (LANG === 'en' ? info.summary : info.summary_es) || (REG()[d] ? I18N.text(REG()[d].description) : '');
    return `<section class="dom" aria-labelledby="dom-${slug(d)}"><h3 id="dom-${slug(d)}">${esc(dpath(d))} <small>${n}</small></h3>${desc ? `<p class="dom-sum">${esc(desc)}</p>` : ''}${groups.map(([g, a]) => `<h4 class="grp">${lblHtml(g)} <small>${a.length}</small></h4>${gi[g] ? `<p class="grp-sum">${esc(gi[g])}</p>` : ''}${a.map(entryHtml).join('')}`).join('')}</section>`;
  }).join('');
}
function setFilter(k, v, scroll) {
  D.f[k] = v; syncControls(); renderDomainNav(); renderList(); pushQuery();
  if (scroll) $('#browse').scrollIntoView({ behavior: 'smooth', block: 'start' });
}
function pushQuery() {
  const q = new URLSearchParams(location.search); for (const k of ['q', 'domain', 'source', 'kind', 'time', 'level', 'year', 'licence', 'file', 'moe']) q.delete(k);   // lang stays
  for (const k of ['q', 'domain', 'source', 'kind', 'time', 'level', 'year', 'licence', 'file']) if (D.f[k]) q.set(k, D.f[k]); if (D.f.moe) q.set('moe', '1');
  history.replaceState(null, '', location.pathname + (q.toString() ? '?' + q : '') + location.hash);
}

// ── Entry body (built when an entry is opened) ───────────────────────────────
function block(title, html) { return html ? `<h5>${esc(title)}</h5>${html}` : ''; }
function fileLinks(e) {
  const files = (e.where.files || []).map(r => { const [f, fld] = r.split(':'); return `<li><a href="data/${esc(f)}" download>${esc(f)}</a>${fld && fld !== '*' ? ` ${Th('<small>· field <code>{field}</code></small>', { field: fld })}` : ` <small>${esc(T('· whole file'))}</small>`}</li>`; });
  return files.length ? `<ul class="plain-list">${files.join('')}</ul>` : '';
}
function entryBody(e) {
  const src = e.sources.map(id => D.sources[id]).filter(Boolean), c = e.coverage || {};
  const h = (v) => v ? esc(v) : '', facts = [[T('Unit'), e.unit && lblHtml(e.unit, e)], [T('Type'), h(VTYPE[e.value_type])], [T('Geography'), e.geography && lblHtml(e.geography, e)], [T('Years'), h(yearsText(e))], [T('Updates'), c.frequency ? lblHtml(c.frequency, e) : h(TIME[c.timeline])], [T('Domain'), `${esc(dpath(e.domain))} › ${lblHtml(e.group, e)}`], [T('Also tagged'), h((e.domains || []).slice(1).map(dpath).join(', '))], [T('Kind'), h(KIND[e.kind])], [T('Added'), h(e.added)]].filter(f => f[1]);
  const vals = e.values && Object.keys(e.values).length ? `<div class="tbl-wrap" tabindex="0" role="region" aria-label="${esc(T('Codes for {name}, scrollable', { name: nameOf(e) }))}"><table class="pt codes"><thead><tr><th scope="col">${esc(T('Code'))}</th><th scope="col">${esc(T('Meaning'))}</th></tr></thead><tbody>${Object.entries(e.values).map(([k, v]) => `<tr><td><code>${esc(k)}</code></td><td>${esc(v)}</td></tr>`).join('')}</tbody></table></div>` : '';
  const views = (e.where.view || []).map(v => { const h = safeHref(v.href); return h ? `<li><a href="${esc(v.href)}">${esc(v.label)}</a></li>` : ''; }).join('');
  const see = (e.see_also || []).map(id => { const t = resolveId(id); return t ? `<li><a href="#${esc(t)}" data-open="${esc(t)}">${esc(nameOf(D.byId[t]))}</a> <small>${esc(dpath(D.byId[t].domain))}</small></li>` : ''; }).join('');
  const srcHtml = src.length ? `<ul class="plain-list">${src.map(s => `<li><a href="#src-${esc(s.id)}">${esc(s.name)}</a> <small>· ${esc(s.licence || '')}</small></li>`).join('')}</ul>${e.source_detail ? `<p class="de-sd">${I18N.en(esc(e.source_detail))}</p>` : ''}` : '';
  const csv = (e.where.files || []).some(r => /^(economy|housing)_series\.json:/.test(r));
  return `<p class="de-plain">${plainEs(e) ? esc(e.plain_es) : e.plain ? I18N.en(esc(e.plain)) : Th('<i>A fuller description is being written.</i>')}</p>
    <dl class="de-facts">${facts.map(([k, v]) => `<div><dt>${esc(k)}</dt><dd>${v}</dd></div>`).join('')}</dl>
    ${block(T('Definition'), e.definition ? `<p>${I18N.en(esc(e.definition))}</p>` : '')}${block(T('How it is computed'), e.method ? `<p>${I18N.en(esc(e.method))}</p>` : '')}${block(T('How to read it'), e.how_to_read ? `<p>${tx(e, 'how_to_read')}</p>` : '')}
    ${block(T('Cautions'), (e.caveats || []).length ? `<ul class="plain-list caution">${e.caveats.map(c => `<li>${I18N.en(esc(c))}</li>`).join('')}</ul>` : '')}${block(T('Codes'), vals)}
    ${block(T('Sources'), srcHtml)}${block(T('Where it appears'), (views ? `<ul class="plain-list">${views}</ul>` : '') + fileLinks(e))}${block(T('Related'), see ? `<ul class="plain-list">${see}</ul>` : '')}
    <div class="de-actions"><button type="button" class="btn small" data-act="cite"><span class="ms-icon" aria-hidden="true">format_quote</span>${esc(T('Cite'))}</button><button type="button" class="btn small" data-act="link"><span class="ms-icon" aria-hidden="true">link</span>${esc(T('Copy link'))}</button>${csv ? `<button type="button" class="btn small" data-act="csv"><span class="ms-icon" aria-hidden="true">download</span>${esc(T('Download all years (CSV)'))}</button>` : ''}</div>
    <div class="de-cite" hidden></div>`;
}
function fillBody(d) {
  const b = d.querySelector('.de-body'); if (!b || b.dataset.filled) return;
  const e = D.byId[d.dataset.id]; if (!e) return;
  if (!e._full) {   // its domain's file is not in yet: say so, fetch it, then fill the entry
    if (b.dataset.loading) return;
    b.dataset.loading = '1'; b.innerHTML = `<p class="note">${esc(T('Loading the entry…'))}</p>`;
    withDetail([e]).then(() => { delete b.dataset.loading; fillBody(d); }, err => { delete b.dataset.loading; b.innerHTML = `<p class="note">${esc(T('The entry could not be loaded ({error}). Close it and open it again to retry.', { error: err.message }))}</p>`; });
    return;
  }
  b.innerHTML = entryBody(e); b.dataset.filled = '1';
}

// ── Citations ────────────────────────────────────────────────────────────────
function citeTexts(e) {
  const y = (D.data.snapshot_built || D.data.built).slice(0, 4), snap = D.data.snapshot ? snapshotLabel(D.data.snapshot) : T('current snapshot'), acc = longDate(new Date());
  const src = (e.sources || []).map(id => D.sources[id]).filter(Boolean), names = src.map(s => s.name), credit = src.map(s => (s.credit || '').replace(/^Source:\s*/i, '').replace(/\.$/, '')).filter(Boolean);
  const url = e.site ? baseUrl() : baseUrl() + 'dictionary.html#' + e.id, yr = e.id && (e.coverage || {}).timeline !== 'snapshot' ? yearsText(e) : '', title = e.name + (yr ? ` (${yr})` : '');   // a snapshot entry is dated by the snapshot name already
  const orig = names.length ? ` ${T('Original data: {names}.', { names: names.join('; ') })}` : '';
  return {
    short: e.site ? T('Foundation for Puerto Rico, PR Data Observatory ({snap}). Open data; each layer credits its source.', { snap }) : `${credit.length ? T('Source: {names}', { names: credit.join('; ') }) : names.length ? T('Source: {names}', { names: names.join('; ') }) : ''}${credit.length || names.length ? '. ' : ''}${T('Processed by Foundation for Puerto Rico, PR Data Observatory ({snap}).', { snap })}`,
    apa: e.site ? `Foundation for Puerto Rico. (${y}). PR Data Observatory ${T('[Interactive map and data]')}. ${snap}. ${url} ${T('Retrieved {date}.', { date: acc })}` : `Foundation for Puerto Rico. (${y}). ${title} ${T('[Data set]')}. PR Data Observatory, ${snap}. ${url}${orig} ${T('Retrieved {date}.', { date: acc })}`,
    chicago: e.site ? `Foundation for Puerto Rico. PR Data Observatory. ${snap}. ${T('Accessed {date}.', { date: acc })} ${url}.` : `Foundation for Puerto Rico. “${e.name}.” PR Data Observatory, ${snap}. ${T('Accessed {date}.', { date: acc })} ${url}.${orig}`,
    bibtex: `@misc{prdt${e.id ? '_' + e.id.replace(/[^a-z0-9]+/g, '_') : ''}_${y},\n  author = {{Foundation for Puerto Rico}},\n  title = {${title}},\n  year = {${y}},\n  howpublished = {PR Data Observatory, ${snap}},\n  url = {${url}},\n  note = {${orig.trim()} ${T('Accessed {date}', { date: acc })}}\n}`,
    credits: credit,
  };
}
function citePanel(box, e) {
  const t = citeTexts(e), fmts = [['short', T('Credit line')], ['apa', 'APA 7'], ['chicago', 'Chicago'], ['bibtex', 'BibTeX']], uid = 'c' + Math.random().toString(36).slice(2, 8);
  box.innerHTML = `<fieldset class="seg"><legend class="sr-only">${esc(T('Citation format'))}</legend>${fmts.map(([k, l], i) => `<label><input type="radio" name="${uid}" value="${k}" ${i ? '' : 'checked'}><span>${l}</span></label>`).join('')}</fieldset><pre class="cite-pre" tabindex="0"></pre><div class="de-actions"><button type="button" class="btn small" data-act="copy"><span class="ms-icon" aria-hidden="true">content_copy</span>${esc(T('Copy'))}</button><span class="note" role="status"></span></div><p class="note">${esc(T('Cite the observatory for how the data were put together and the original source for the data.'))} ${t.credits.length ? esc(T('Credit to show with the data: {credits}', { credits: t.credits.join(' · ') })) + '.' : ''} ${esc(T("Check the source's terms before reuse."))}</p>`;
  const pre = box.querySelector('pre'), show = () => { pre.textContent = t[box.querySelector('input:checked').value]; };
  box.querySelectorAll('input').forEach(i => i.onchange = show); show();
  box.querySelector('[data-act=copy]').onclick = async () => { const note = box.querySelector('.note[role=status]'); try { await navigator.clipboard.writeText(pre.textContent); note.textContent = T('Copied.'); } catch { note.textContent = T('Copy did not work here: select the text and copy it.'); } };
}
function renderCiteSite() { citePanel($('#citeSite'), { id: '', site: true, name: 'PR Data Observatory', sources: [] }); }

// ── Series CSV ───────────────────────────────────────────────────────────────
async function downloadSeries(e) {
  const ref = (e.where.files || []).find(r => /^(economy|housing)_series\.json:/.test(r)); if (!ref) return;
  const [file, key] = ref.split(':');
  if (!D.series[file]) D.series[file] = fetchJson('data/' + file).catch(e => { delete D.series[file]; throw e; });
  const j = await D.series[file], v = j.vars.find(x => x.key === key); if (!v || !v.years) return;
  const ys = Object.keys(v.years).sort(), hasM = !!v.moe;
  const head = ['GEOID', T('Municipality'), ...ys.flatMap(y => hasM ? [y, T('{year} margin of error', { year: y })] : [y])];
  const rows = j.geo.names.map((n, i) => [j.geo.ids[i], n, ...ys.flatMap(y => hasM ? [(v.years[y] || [])[i], ((v.moe || {})[y] || [])[i]] : [(v.years[y] || [])[i]])]);
  saveCsv(`pr_digital_twin_${e.id.replace(/[^a-z0-9]+/g, '_')}.csv`, head, rows);
}
function saveCsv(name, header, rows) {
  const q = (v) => { if (v == null) return ''; let s = String(v); if (/^[=+\-@\t\r]/.test(s) && typeof v !== 'number') s = "'" + s; return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s; };
  const a = document.createElement('a'); a.href = URL.createObjectURL(new Blob(['﻿' + [header, ...rows].map(r => r.map(q).join(',')).join('\n')], { type: 'text/csv;charset=utf-8' })); a.download = name; a.click(); setTimeout(() => URL.revokeObjectURL(a.href), 4000);
}
async function downloadDictionary() {
  const btn = $('#dlDict'), lbl = btn.lastChild, text = lbl.textContent;
  if (D.entries.some(e => !e._full)) {   // the definitions, methods and cautions are in the detail files
    btn.disabled = true; lbl.textContent = T('Preparing the download…');
    try { await withDetail(D.entries); } catch (err) { $('#dCount').textContent = T('The download could not be prepared ({error}). Check your connection and try again.', { error: err.message }); return; } finally { btn.disabled = false; lbl.textContent = text; }
  }
  const head = ['id', T('name'), T('domain'), T('also tagged'), T('group'), T('kind'), T('type'), T('unit'), T('geography'), T('years'), T('updates'), T('plain description'), T('definition'), T('how it is computed'), T('how to read it'), T('cautions'), T('sources'), T('source detail'), T('data fields'), T('related'), T('added')];
  saveCsv('pr_digital_twin_data_dictionary.csv', head, D.entries.map(e => [e.id, e.name, dpath(e.domain), (e.domains || []).slice(1).map(dpath).join('; '), e.group, KIND[e.kind], VTYPE[e.value_type], e.unit, e.geography, yearsText(e), (e.coverage || {}).frequency || '', e.plain, e.definition, e.method, e.how_to_read || '', (e.caveats || []).join(' | '), e.sources.map(id => (D.sources[id] || {}).name || id).join('; '), e.source_detail || '', (e.where.files || []).join('; '), (e.see_also || []).join('; '), e.added]));
}

// ── Sources, glossary, files ─────────────────────────────────────────────────
function renderSources() {
  const kind = $('#srcKind').value, q = norm($('#srcQ').value);
  const list = Object.values(D.sources).filter(s => (!kind || s.kind === kind) && (!q || norm([s.name, s.publisher, s.licence, s.used_for, s.used_for_es, s.credit].join(' ')).includes(q))).sort((a, b) => (a.kind === b.kind ? 0 : a.kind === 'data' ? -1 : 1) || a.name.localeCompare(b.name));
  $('#srcList').innerHTML = list.map(s => {
    const lic = s.licence_url && safeHref(s.licence_url) ? `<a href="${esc(safeHref(s.licence_url))}" target="_blank" rel="noopener">${esc(s.licence || T('License'))}</a>` : esc(s.licence || '');
    const links = [[s.name, s.url], ...(s.more_links || []).map(l => [l.label, l.url])].filter(l => safeHref(l[1])).map(l => `<a href="${esc(safeHref(l[1]))}" target="_blank" rel="noopener">${esc(l[0].length > 60 ? l[0].slice(0, 58) + '…' : l[0])} <span class="ms-icon" aria-hidden="true">open_in_new</span></a>`);
    const ver = s.verified || {}, vtxt = { verified: T('Link and license checked'), 'link-works-licence-unclear': T('Link works; license wording unclear'), unreachable: T('Link did not respond when checked'), unchecked: T('Not yet checked') }[ver.status] || '';
    const row = (k, v) => v ? `<div><dt>${k}</dt><dd>${v}</dd></div>` : '';
    return `<article class="src-card" id="src-${esc(s.id)}"><h3>${esc(s.name)} <span class="chip ${s.kind === 'data' ? 'b' : 'y'}">${esc(s.kind === 'data' ? T('Data source') : T('Base map or tool'))}</span></h3>
      <dl class="kvl">${row(T('Published by'), esc(s.publisher))}${row(T('License or terms'), lic)}${row(T('Credit line'), s.credit ? `<span class="credit">${esc(s.credit)}</span> <button type="button" class="linklike" data-copy="${esc(s.credit)}">${esc(T('Copy'))}</button>` : '')}${row(T('How the observatory gets it'), s.access && tx(s, 'access'))}${row(T('Updates'), s.cadence && tx(s, 'cadence'))}${row(T('Used for'), s.used_for && tx(s, 'used_for'))}${row(T('Good to know'), s.terms_note && tx(s, 'terms_note'))}${row(T('Checked'), vtxt ? `${esc(vtxt)}${ver.date ? ' · ' + esc(ver.date) : ''}` : '')}</dl>
      <p class="src-links">${links.join('')}</p>${s.used_by ? `<p><button type="button" class="btn small" data-filter-source="${esc(s.id)}">${esc(Tn(s.used_by, 'Show the {n} dictionary item that uses it', 'Show the {n} dictionary items that use it'))}</button></p>` : ''}</article>`;
  }).join('') || `<div class="empty">${esc(T('No source matches.'))}</div>`;
}
// Each term (dictionary_src/glossary.json, docs/glossary.md) has a definition in both languages and its source. In Spanish the term, its expansion and its definition are
// the Spanish ones; a definition held for review (hold_es) has no Spanish in the published file, so the English one is shown, marked lang="en".
// The anchor stays g-<the English term's slug> in both languages, so links to a term work in either.
const gTerm = (t) => (LANG === 'es' && t.term_es) || t.term;
function renderGlossary() {
  const first = (t) => norm(gTerm(t))[0].toUpperCase().replace(/[^A-Z]/, '#');
  const g = D.data.glossary.slice().sort((a, b) => norm(gTerm(a)).localeCompare(norm(gTerm(b)))), letters = [...new Set(g.map(first))].sort();
  const SECTION = { browse: T('Browse the dictionary'), sources: T('Sources and licenses'), files: T('Published data files'), cite: T('How to cite') };
  $('#azStrip').innerHTML = letters.map(l => `<a href="#gl-${l}">${l}</a>`).join('');
  const by = {}; g.forEach(t => { (by[first(t)] = by[first(t)] || []).push(t); });
  $('#gList').innerHTML = letters.map(l => `<h3 class="gl-letter" id="gl-${l}">${l}</h3><dl class="gl-dl">${by[l].map(t => {
    const see = (t.see_also || []).map(id => { const r = resolveId(id); return r ? `<a href="#${esc(r)}" data-open="${esc(r)}">${esc(nameOf(D.byId[r]))}</a>` : ''; }).filter(Boolean);
    if (SECTION[t.section]) see.push(`<a href="#${esc(t.section)}">${esc(SECTION[t.section])}</a>`);
    const es = LANG === 'es', def = es && t.plain_es ? t.plain_es : t.plain, shown = norm(gTerm(t)), has = (x) => x && shown.includes(norm(x));
    const exp = [(es && t.expansion_es) || t.expansion].find(x => x && !has(x)) || '', other = es && t.term_es && !has(t.term) ? t.term : '';
    const s = t.source || {}, href = safeHref(s.url || '');
    const src = href ? `<div class="gl-src">${esc(T('Source:'))} <a href="${esc(href)}" target="_blank" rel="noopener">${esc((es && s.name_es) || s.name)}</a>${s.checked ? ` <span class="gl-chk">· ${esc(T('link checked {date}', { date: longDate(s.checked) }))}</span>` : ''}</div>` : '';
    return `<dt id="g-${esc(t.id || slug(t.term))}">${esc(gTerm(t))}${exp ? ` <small>${esc(exp)}</small>` : ''}${other ? ` <small class="gl-en">${esc(T('in English: {term}', { term: other }))}</small>` : ''}</dt><dd><span${es && !t.plain_es ? ' lang="en"' : ''}>${esc(def)}</span>${src}${see.length ? `<div class="gl-see">${esc(T('See also:'))} ${see.join(' · ')}</div>` : ''}</dd>`;
  }).join('')}</dl>`).join('');
}
function renderFiles() {   // a summary: the table of files is on the Data management page (data-management.html), which reads the same registry
  const r = D.reg, files = r.files || [], t = r.totals || {};
  $('#filesLede').textContent = [T('The observatory runs on {n} data files that anyone can download from this site.', { n: files.length }),
    r.total_bytes ? (r.used_fraction != null ? T('Together they are {size}, about {pct}% of the 1 GB a GitHub Pages site may hold.', { size: sizeText(r.total_bytes), pct: (r.used_fraction * 100).toFixed(0) }) : T('Together they are {size}.', { size: sizeText(r.total_bytes) })) : '',
    t.values ? T('The data files hold {records} records and {values} values (data points), counted at each build.', { records: fmt(t.records), values: fmt(t.values) }) : '',
    T("Each file's license is that of its sources (above).")].filter(Boolean).join(' ');
  $('#growNote').textContent = r.growth_note ? T(r.growth_note) : '';
}

// ── Navigation ───────────────────────────────────────────────────────────────
function openEntry(id, scroll = true) {
  const t = resolveId(id); if (!t) return false;
  let d = document.getElementById(t);
  if (!d || !d.matches('details.de')) { D.f = { q: '', domain: '', source: '', kind: '', time: '', level: '', year: '', licence: '', moe: false, file: '' }; syncControls(); renderDomainNav(); renderList(); pushQuery(); d = document.getElementById(t); }
  if (!d) return false;
  d.open = true; fillBody(d); d.classList.add('flash'); setTimeout(() => d.classList.remove('flash'), 2200);
  if (scroll) d.scrollIntoView({ behavior: 'smooth', block: 'start' });
  return true;
}
function openFromHash(first) {
  let h = ''; try { h = decodeURIComponent(location.hash.slice(1)); } catch { /* a broken % in the link: no entry is opened */ } if (!h) return;
  if (D.byId[h] || (D.data.id_alias || {})[h]) { openEntry(h, true); return; }
  const el = document.getElementById(h); if (el) setTimeout(() => el.scrollIntoView({ block: 'start' }), first ? 60 : 0);
}
function wire() {
  let t; $('#dq').oninput = e => { clearTimeout(t); t = setTimeout(() => setFilter('q', e.target.value.trim()), 150); };
  $('#dqClear').onclick = () => { setFilter('q', ''); $('#dq').focus(); };
  ['Domain', 'Source', 'Kind', 'Time', 'Level', 'Year', 'Licence'].forEach(k => { $('#f' + k).onchange = e => setFilter(k.toLowerCase(), e.target.value); });
  $('#fMoe').onchange = e => setFilter('moe', e.target.checked);
  $('#fReset').onclick = () => { D.f = { q: '', domain: '', source: '', kind: '', time: '', level: '', year: '', licence: '', moe: false, file: '' }; syncControls(); renderDomainNav(); renderList(); pushQuery(); };
  $('#expAll').onclick = () => {   // opening hundreds of entries at once is slow and not readable: open the first 60 of what is listed
    const all = [...document.querySelectorAll('#dList details.de')], ds = all.slice(0, 60);
    ds.forEach(d => { d.open = true; fillBody(d); });
    $('#dCount').textContent = all.length > 60 ? T('Opened the first 60 of {n}. Use the filters or search to narrow the list, then expand again.', { n: all.length }) : T('{n} items opened', { n: all.length });
  };
  $('#colAll').onclick = () => document.querySelectorAll('#dList details.de').forEach(d => { d.open = false; });
  $('#dlDict').onclick = downloadDictionary;
  $('#srcKind').onchange = renderSources; $('#srcQ').oninput = renderSources;
  $('#domainNav').onclick = e => { const b = e.target.closest('[data-domain]'); if (b) setFilter('domain', b.dataset.domain, true); };
  document.addEventListener('toggle', e => { if (e.target.matches && e.target.matches('details.de') && e.target.open) fillBody(e.target); }, true);
  document.addEventListener('click', e => {
    const o = e.target.closest('[data-open]'); if (o) { e.preventDefault(); history.replaceState(null, '', '#' + o.dataset.open); openEntry(o.dataset.open); return; }
    const fs = e.target.closest('[data-filter-source]'); if (fs) { D.f.file = ''; setFilter('source', fs.dataset.filterSource, true); return; }
    const ff = e.target.closest('[data-filter-file]'); if (ff) { D.f.source = ''; setFilter('file', ff.dataset.filterFile, true); return; }
    const cp = e.target.closest('[data-copy]'); if (cp) { navigator.clipboard.writeText(cp.dataset.copy).then(() => { cp.textContent = T('Copied'); setTimeout(() => cp.textContent = T('Copy'), 1800); }).catch(() => {}); return; }
    const act = e.target.closest('[data-act]'); const card = act && act.closest('details.de'); if (!card) return;
    const en = D.byId[card.dataset.id], a = act.dataset.act;
    if (a === 'cite') { const box = card.querySelector('.de-cite'); if (box.hidden) { citePanel(box, en); box.hidden = false; box.scrollIntoView({ block: 'nearest' }); } else box.hidden = true; }
    else if (a === 'link') { navigator.clipboard.writeText(baseUrl() + 'dictionary.html#' + en.id).then(() => { act.lastChild.textContent = T('Link copied'); setTimeout(() => act.lastChild.textContent = T('Copy link'), 1800); }).catch(() => {}); }
    else if (a === 'csv') downloadSeries(en);
  });
  window.addEventListener('hashchange', () => openFromHash(false));
  window.addEventListener('beforeprint', () => { const ds = [...document.querySelectorAll('#dList details.de')]; withDetailNow(ds.map(d => D.byId[d.dataset.id]).filter(Boolean)); ds.forEach(d => { d.open = true; fillBody(d); }); });
}
boot();
