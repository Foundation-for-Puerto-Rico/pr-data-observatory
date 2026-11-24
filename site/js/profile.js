/* PR Data Observatory: area profiles (profile.html?area=72127, plan B5; docs/workbench.md).
   One page for each municipio: every dataset the Economy tab holds (the same files and engine: js/core/datasets.js), grouped by the registry's fields (catalog.json and the domain of each entry, catalog_domains.json; the full index, catalog_index.json, loads only when the chat needs it), each with its
   latest value and margin of error, the value a shaded map compares (per resident, per km² or a share), its rank among the 78 municipios, Puerto Rico's value and its trend;
   five similar municipios (by population and density) and a small locator map. Text goes through T / Tn / Th (docs/i18n.md).
   The page is drawn twice (docs/performance.md): first with the files of its first field (Housing) and of the similar municipios, then, once the other files of
   js/core/datasets.js have arrived, with every dataset. tests/profile_first.test.js checks that the first field is the same both times. */

const P = { E: Core.engine.create(), rows: [], area: null, complete: false };
const getJson = (path) => fetchJson(path);
const FIRST = ['econ', 'hous', 'popu', 'commuting', 'netmig', 'expo', 'facilities', 'conditions'];   // names in Core.datasets.FILES
const LEFT_OUT = ['wcrp'];   // barrio values only (WCRP vulnerability ranks), so no municipio has one: the profile does not fetch them

async function profLoad() {
  const [meta, muni, fc, catalog, doms, first] = await Promise.all([...['data/meta.json', 'data/municipalities.json', 'data/municipios.geojson', 'data/catalog.json', 'data/catalog_domains.json'].map(getJson), Core.datasets.fetchFiles(getJson, FIRST)]);
  P.regions = await getJson('data/geo/regions.json').then(d => d.regions, () => []);   // the regions of profile.html?region= (regions.py); without the file the page offers only municipios
  Object.assign(P, { meta, muni, fc, catalog, year: +((meta.generated_at || '').slice(0, 4)) || 2026, docs: first.docs, failed: first.failed });
  Core.datasets.apply(P.E, P.docs, muni, P.year);
  P.domainOf = new Map(Object.entries(doms.domain_of).flatMap(([d, ids]) => ids.map(id => [id, d || null])));   // catalog.py writes it from the index (catalog_index.json), which the chat fetches on first use (common.js withIndex)
  P.domains = catalog.domains.filter(d => !d.parent).sort((a, b) => a.order - b.order);
  P.parent = new Map(catalog.domains.map(d => [d.id, d.parent || d.id]));
}

/** The other files, after the first drawing; then every dataset is added again, in the order of js/core/datasets.js, and the page is drawn again. */
async function profRest() {
  const rest = await Core.datasets.fetchFiles(getJson, Core.datasets.FILES.map(f => f.name).filter(n => !FIRST.includes(n) && !LEFT_OUT.includes(n)));
  const X = Core.engine.create();
  Core.datasets.apply(X, { ...P.docs, ...rest.docs }, P.muni, P.year);
  Object.assign(P, { E: X, failed: [...P.failed, ...rest.failed], complete: true });
  draw();
}

/** The page's place: a region (profile_region.js) or a municipio. */
const draw = () => (P.reg ? ProfRegion.render(P.reg, regionCtx()) : render(P.area));
const dnameOf = (id) => { const d = P.catalog.domains.find(x => x.id === id); return d ? I18N.name(d) : T('Other'); };
const regionCtx = () => ({ X: E(), prIdx: pr(), P, dname: dnameOf, spark, lang: I18N.lang === 'es' ? 'es' : 'en' });

const E = () => P.E;
const pr = () => P.E.geo.pr;
function geoidOf(i) { return P.E.geo.ids[i]; }

/** The five municipios most like place i: nearest on the logarithms of population and of residents per km², each put on z-scores (Core.stats.peers). */
function peersOf(i) {
  const r = E().values('population', {}); if (!r) return { list: [], year: null };
  const pop = r.values, area = E().geo.area, lg = (x) => x > 0 ? Math.log(x) : null;
  return { list: Core.stats.peers(i, [pop.map(lg), pop.map((x, k) => area[k] ? lg(x / area[k]) : null)], pr(), 5), year: r.year };
}

/** One row of a dataset for place i, or null when the place has no value and the dataset gives no meaning to an empty place. */
function rowOf(v, i) {
  const X = E(), raw = X.values(v.key, {}); if (!raw) return null;
  const L0 = { key: v.key, norm: 'value' }, val = raw.values[i], miss = val == null ? X.missing(L0, i) : null;
  if (val == null && !miss) return null;
  const n = Core.normalize.defaultNorm(v, 'fill'), L = { key: v.key, norm: n }, cmp = n === 'value' ? raw : X.values(v.key, { norm: n });
  const moe = X.moe(L0, raw.year), rk = cmp ? Core.stats.rank(cmp.values, i, pr()) : null;
  const trend = v.static ? null : v.ys.slice(-15).map(y => { const a = X.calc(L, y); return a ? [y, a[i]] : [y, null]; }).filter(p => p[1] != null);
  const dom = P.parent.get(P.domainOf.get(X.dictId(v.key))) || 'other';
  return { v, L, L0, dom, year: raw.year, chip: X.chip(L0, { y: raw.year, exact: true }), val, miss, moe: moe ? moe[i] : null, norm: n, cmp: cmp ? cmp.values[i] : null, prv: cmp ? cmp.values[pr()] : null, rk, trend };
}

function spark(t, L) {
  if (!t || t.length < 2) return '';
  const xs = t.map(p => p[0]), ys = t.map(p => p[1]), x0 = Math.min(...xs), x1 = Math.max(...xs), y0 = Math.min(...ys), y1 = Math.max(...ys), w = 110, h = 26;
  const X = (x) => 3 + (x - x0) / ((x1 - x0) || 1) * (w - 6), Y = (y) => h - 3 - (y - y0) / ((y1 - y0) || 1) * (h - 6);
  const lab = T('Trend from {from} ({a}) to {to} ({b})', { from: xs[0], a: E().fmt(L, ys[0]), to: xs[xs.length - 1], b: E().fmt(L, ys[ys.length - 1]) });
  return `<svg class="pf-spark" viewBox="0 0 ${w} ${h}" role="img" aria-label="${esc(lab)}"><title>${esc(lab)}</title><polyline fill="none" stroke="#205D7B" stroke-width="1.6" points="${t.map(p => `${X(p[0]).toFixed(1)},${Y(p[1]).toFixed(1)}`).join(' ')}"/><circle cx="${X(xs[xs.length - 1]).toFixed(1)}" cy="${Y(ys[ys.length - 1]).toFixed(1)}" r="2.4" fill="#205D7B"/></svg>`;
}

function render(i) {
  const X = E(), name = X.geo.names[i], m = P.muni[name] || {}, peers = peersOf(i);
  P.area = i;
  document.title = T('{name} · Area profile · PR Data Observatory', { name });
  $('#pTitle').textContent = name;
  $('#pLede').textContent = T('{region} · {pop} residents (Census 2020) · {area} km² of land · code {geoid}', { region: m.region || '', pop: fmt(m.population_2020 || 0), area: fmt(m.land_km2 || 0), geoid: geoidOf(i) });
  $('#pMap').href = 'index.html#' + encodeURIComponent(name);
  $('#pArea').value = String(i); P.reg = null;
  const strong = new Set([i]), fills = X.geo.names.slice(0, pr()).map((_, k) => k === i ? '#205D7B' : peers.list.some(p => p.i === k) ? '#8FCAE8' : '#E6E6E6');
  P.paths = P.paths || Core.minimap.project(P.fc, X.geo.names.slice(0, pr()), 600);
  $('#pMapFig').innerHTML = Core.minimap.svg(P.paths, fills, { label: T('Map of Puerto Rico with {name} and its five similar municipios marked', { name }), strong, titles: X.geo.names.slice(0, pr()) })
    + `<div class="mm-legend"><span><i style="background:#205D7B"></i>${esc(name)}</span><span><i style="background:#8FCAE8"></i>${esc(T('Similar municipios'))}</span></div>`;
  $('#pPeers').innerHTML = `<h2>${esc(T('Similar municipios'))}</h2>${peers.list.length ? `<ol>${peers.list.map(p => `<li><a href="profile.html?area=${geoidOf(p.i)}">${esc(X.geo.names[p.i])}</a></li>`).join('')}</ol>` : `<p class="note">${esc(T('Not available: the population figures did not load.'))}</p>`}<p class="note">${esc(T('The five municipios nearest to {name} in population and in residents per km² ({year}): both on a log scale, put on z-scores across the 78 municipios, and compared by straight-line distance. Similar in size and density, not in every way.', { name, year: peers.year || '' }))}</p>`;
  // rows, grouped by field and then by the dataset's group
  P.rows = X.list().map(v => rowOf(v, i)).filter(Boolean);
  const byDom = new Map(); P.rows.forEach(r => { if (!byDom.has(r.dom)) byDom.set(r.dom, []); byDom.get(r.dom).push(r); });
  const all = [...P.domains.map(d => d.id).filter(id => byDom.has(id)), ...[...byDom.keys()].filter(k => !P.domains.some(d => d.id === k))], order = P.complete ? all : all.slice(0, 1);   // before the other files arrive: the first field
  const dname = (id) => { const d = P.catalog.domains.find(x => x.id === id); return d ? I18N.name(d) : T('Other'); };
  const cell = (r) => {
    const val = r.val == null ? `<span class="pf-miss">${esc(r.miss)}</span>` : `${esc(X.fmt(r.L0, r.val))}${r.moe != null ? ` <small class="moe">± ${esc(X.fmt(r.L0, r.moe))}</small>` : ''}`;
    const same = r.norm === 'value', cmp = r.cmp == null ? '—' : same ? '' : esc(X.fmt(r.L, r.cmp));
    return `<tr><th scope="row">${esc(T(r.v.label))}<small>${esc(r.chip)}</small></th><td class="num">${val}</td><td class="num">${same ? '' : `${cmp}<small>${esc(X.normLabel(r.L))}</small>`}</td><td class="num">${r.rk ? esc(T('#{rank} of {n}', r.rk)) : '—'}</td><td class="num">${r.prv == null ? '—' : esc(X.fmt(r.L, r.prv))}</td><td>${spark(r.trend, r.L)}</td></tr>`;
  };
  $('#pSections').innerHTML = order.map(id => {
    const rows = byDom.get(id), groups = new Map(); rows.forEach(r => { const g = r.v.group; if (!groups.has(g)) groups.set(g, []); groups.get(g).push(r); });
    return `<section class="d-block pf-sec" id="dom-${esc(id)}" aria-labelledby="h-${esc(id)}"><h2 id="h-${esc(id)}">${esc(dname(id))} <small>${esc(Tn(rows.length, '{n} dataset', '{n} datasets'))}</small></h2>
      <div class="tbl-wrap" tabindex="0" role="region" aria-label="${esc(T('{field}: datasets for {name}, scrollable', { field: dname(id), name }))}"><table class="pt pf-tbl"><thead><tr><th scope="col">${esc(T('Dataset'))}</th><th scope="col" class="num">${esc(T('Value'))}</th><th scope="col" class="num">${esc(T('As a shaded map compares it'))}</th><th scope="col" class="num">${esc(T('Rank among the 78'))}</th><th scope="col" class="num">${esc(T('Puerto Rico'))}</th><th scope="col">${esc(T('Trend'))}</th></tr></thead>
      ${[...groups].map(([g, rs]) => `<tbody><tr class="pf-g"><th colspan="6" scope="colgroup">${esc(T(g))}</th></tr>${rs.map(cell).join('')}</tbody>`).join('')}</table></div></section>`;
  }).join('') + (P.complete ? '' : `<p class="note pf-wait" role="status">${esc(T('Loading the other fields…'))}</p>`);
  $('#profNav').innerHTML = `<h2 class="side-h">${esc(T('On this page'))}</h2>` + order.map(id => `<a href="#dom-${esc(id)}">${esc(dname(id))} <small>${byDom.get(id).length}</small></a>`).join('');
  const left = X.list().length - P.rows.length;
  if (!P.complete) { $('#pNote').textContent = P.notice || ''; return; }   // the rest of the note counts every dataset
  $('#pNote').textContent = [P.notice || '', T('Rank 1 is the highest value among the municipios that have one; it says where {name} stands, not whether that is good. The rank, Puerto Rico\'s value and the trend use the same measure as a shaded map: counts per 1,000 residents, dollar totals per resident, shares as they are.', { name }),
    left ? Tn(left, '{n} dataset has no value for this municipio and is left out.', '{n} datasets have no value for this municipio and are left out.') : '',
    P.failed.length ? T('Some data did not load, so some datasets are missing. Reload the page to try again.') : ''].filter(Boolean).join(' ');
}

function csv() {
  const X = E(), i = P.area, name = X.geo.names[i];
  const q = v => { if (v == null) return ''; let s = String(v); if (/^[=+\-@\t\r]/.test(s) && typeof v !== 'number') s = "'" + s; return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s; };
  const head = [T('Field'), T('Group'), T('Dataset'), T('Year'), T('Value'), T('Margin of error'), T('Compared as'), T('Compared value'), T('Rank among the 78'), T('Puerto Rico')];
  const dn = (id) => { const d = P.catalog.domains.find(x => x.id === id); return d ? I18N.name(d) : T('Other'); };
  const rows = P.rows.map(r => [dn(r.dom), T(r.v.group), T(r.v.label), r.chip, r.val, r.moe, X.normLabel(r.L), r.cmp, r.rk ? r.rk.rank : null, r.prv]);
  const a = document.createElement('a'); a.href = URL.createObjectURL(new Blob(['﻿' + [head, ...rows].map(r => r.map(q).join(',')).join('\n')], { type: 'text/csv;charset=utf-8' }));
  a.download = `pr_profile_${geoidOf(i)}_${norm(name).replace(/\W+/g, '_')}.csv`; a.click(); setTimeout(() => URL.revokeObjectURL(a.href), 4000);
}

async function profInit() {
  try { await profLoad(); } catch (e) { $('#pTitle').textContent = T('The profile could not be loaded'); $('#pLede').textContent = T('The data did not load ({error}). Check your connection and reload the page.', { error: e.message }); return; }
  $('#snapshotLabel').innerHTML = `<b>${esc(snapshotLabel(P.meta.label))}</b>`;
  const X = E(), names = X.geo.names.slice(0, pr());
  const lg = I18N.lang === 'es' ? 'es' : 'en', regOpt = (r) => `<option value="r:${esc(r.id)}">${esc(r.name[lg] || r.name.en)}</option>`;
  $('#pArea').innerHTML = (P.regions.length ? `<optgroup label="${esc(T('Regions'))}">${P.regions.map(regOpt).join('')}</optgroup>` : '') +
    `<optgroup label="${esc(T('Municipalities'))}">${names.map((n, i) => ({ n, i })).sort((a, b) => a.n.localeCompare(b.n, 'es')).map(o => `<option value="${o.i}">${esc(o.n)}</option>`).join('')}</optgroup>`;
  const want = new URLSearchParams(location.search).get('area') || '', at = X.geo.ids.indexOf(want);
  const i = at >= 0 && at < pr() ? at : X.placeIndex('San Juan');
  if (want && at < 0) P.notice = T('There is no municipio with the code {code}; showing San Juan.', { code: want });   // render() puts it first in the note under the title
  const wantReg = new URLSearchParams(location.search).get('region'), reg = wantReg && P.regions.find(r => r.id === wantReg);
  if (wantReg && !reg) P.notice = T('There is no region with the code {code}; showing San Juan.', { code: wantReg });
  // a region of the visitor's own (Study areas › Build my region, GIS tools step 4): profile.html?ids=72029,72037,... (two or more municipio codes), pooled the same way
  const wantIds = !reg && new URLSearchParams(location.search).get('ids'), mine = wantIds ? [...new Set(wantIds.split(',').filter(g => { const k = X.geo.ids.indexOf(g); return /^72\d{3}$/.test(g) && k >= 0 && k < pr(); }))].sort() : [];
  const own = mine.length >= 2 ? { id: 'custom', kind: 'custom', ids: mine, names: mine.map(g => names[X.geo.ids.indexOf(g)]),
    name: { en: T('Your region of {n} municipios', { n: mine.length }), es: T('Your region of {n} municipios', { n: mine.length }) },
    source: { en: T('municipios chosen in Build my region'), es: T('municipios chosen in Build my region') } } : null;
  if (wantIds && !own) P.notice = T('A region needs two or more municipio codes; showing San Juan.');
  if (own) $('#pArea').insertAdjacentHTML('afterbegin', `<option value="r:custom">${esc(own.name.en)}</option>`);
  P.area = i; P.reg = reg || own || null; draw(); if (P.reg) $('#pArea').value = 'r:' + P.reg.id;
  $('#pArea').onchange = e => { P.notice = ''; const u = new URL(location.href), val = e.target.value;
    if (val === 'r:custom') { P.reg = own; draw(); window.scrollTo(0, 0); return; }
    if (val.startsWith('r:')) { P.reg = P.regions.find(r => r.id === val.slice(2)); u.searchParams.delete('area'); u.searchParams.set('region', P.reg.id); history.replaceState(null, '', u); draw(); window.scrollTo(0, 0); return; }
    const k = +val; u.searchParams.delete('region'); u.searchParams.set('area', geoidOf(k)); history.replaceState(null, '', u); render(k); window.scrollTo(0, 0); };
  $('#pCsv').onclick = async () => {   // the file holds every dataset: wait for the other files
    if (!P.complete) {
      const btn = $('#pCsv'), lbl = btn.lastChild, text = lbl.textContent;
      btn.disabled = true; lbl.textContent = T('Preparing the download…');
      try { await P.rest; } catch { return; } finally { btn.disabled = false; lbl.textContent = text; }
    }
    if (P.reg) ProfRegion.csv(P.reg, regionCtx()); else csv();
  };
  P.rest = profRest().catch(e => { const w = $('#pSections .pf-wait'); if (w) w.textContent = T('The data did not load ({error}). Check your connection and reload the page.', { error: e.message }); throw e; });
  P.rest.catch(() => {});   // the note says it; the CSV button waits on P.rest
}
profInit();
