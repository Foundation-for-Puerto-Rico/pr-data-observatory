/* PR Data Observatory: the views of the Economy tab's workbench that load on first use (docs/workbench.md, docs/performance.md): Scatter and Trend (Chart.js, which
   economy.js loads on first use too), Correlations, Small multiples, Compare two maps and the builder of the composite index. economy.js loads this file, core/minimap.js
   (the small maps) and their Spanish (I18N.load('workbench')) the first time one of these views opens (ecWorkbenchLib), and draws the view once all are in. The functions
   are the tab's own: they read and write EC and E, and the inspector, the table, the scenarios, the study areas and the composite's dataset (ecIxApply) stay in economy.js. */

// ── Scatter and trend (plan B4) ──────────────────────────────────────────────
function ecBenchScatter() {
  const vis = ecVisible(); if (vis.length < 2) { $('#ebBody').innerHTML = `<div class="empty">${esc(T('A scatter plot needs two visible layers.'))} ${esc(vis.length ? T('Add one more.') : T('Add two layers.'))}</div>`; return; }
  if (!ecNeedChart('scatter')) return;
  const st = EC.sc = EC.sc || { x: vis[0].id, y: vis[1].id, log: false, size: false };
  if (!vis.find(l => l.id === st.x)) st.x = vis[0].id; if (!vis.find(l => l.id === st.y)) st.y = vis[1].id;
  const opt = (sel) => vis.map(L => `<option value="${L.id}"${L.id === sel ? ' selected' : ''}>${esc(T(EC.V[L.key].label))}</option>`).join('');
  const X = vis.find(l => l.id === st.x), Y = vis.find(l => l.id === st.y), ax = EC.eval[X.id].a, ay = EC.eval[Y.id].a, pop = popAt(EC.eval[X.id].y || 2020);
  const idx = [...Array(EC.PR).keys()].filter(i => ax[i] != null && ay[i] != null && (!st.log || (ax[i] > 0 && ay[i] > 0)));
  const n = idx.length, mx = idx.reduce((s, i) => s + ax[i], 0) / n, my = idx.reduce((s, i) => s + ay[i], 0) / n;
  const sxx = idx.reduce((s, i) => s + (ax[i] - mx) ** 2, 0), syy = idx.reduce((s, i) => s + (ay[i] - my) ** 2, 0), sxy = idx.reduce((s, i) => s + (ax[i] - mx) * (ay[i] - my), 0), r = sxx && syy ? sxy / Math.sqrt(sxx * syy) : null, slope = sxx ? sxy / sxx : 0, icpt = my - slope * mx;
  $('#ebBody').innerHTML = `<div class="eb-tools"><label>X <select id="scX">${opt(st.x)}</select></label><label>Y <select id="scY">${opt(st.y)}</select></label><label class="chk"><input type="checkbox" id="scLog" ${st.log ? 'checked' : ''}> ${esc(T('Log scales'))}</label><label class="chk"><input type="checkbox" id="scSize" ${st.size ? 'checked' : ''}> ${esc(T('Size by population'))}</label><span class="note">${esc(Tn(n, '{n} municipality', '{n} municipalities'))} · ${Th('correlation r = <b>{r}</b>. Correlation across places is not cause and effect; large places and survey noise can drive it.', { r: r == null ? '—' : r.toFixed(2) })}</span></div><div class="eb-chart"><canvas id="scCanvas"></canvas></div>`;
  $('#scX').onchange = e => { st.x = +e.target.value; ecBenchScatter(); }; $('#scY').onchange = e => { st.y = +e.target.value; ecBenchScatter(); }; $('#scLog').onchange = e => { st.log = e.target.checked; ecBenchScatter(); }; $('#scSize').onchange = e => { st.size = e.target.checked; ecBenchScatter(); };
  const xs = idx.map(i => ax[i]), xmin = Math.min(...xs), xmax = Math.max(...xs), lab = L => `${T(EC.V[L.key].label)} (${ecChip(L)})`;
  const c = $('#scCanvas'); c.setAttribute('role', 'img'); c.setAttribute('aria-label', Tn(n, 'Scatter of {y} against {x} for {n} municipality', 'Scatter of {y} against {x} for {n} municipalities', { y: T(EC.V[Y.key].label), x: T(EC.V[X.key].label) }));
  EC.charts.sc = new Chart(c, { data: { datasets: [{ type: 'scatter', label: T('Municipalities'), data: idx.map(i => ({ x: ax[i], y: ay[i], n: EC.NM[i], i })), backgroundColor: idx.map(i => i === EC.selected ? '#FF4D38' : 'rgba(32,93,123,.65)'), pointRadius: idx.map(i => st.size && pop[i] ? 3 + Math.sqrt(pop[i]) / 30 : i === EC.selected ? 7 : 5) }, { type: 'line', label: T('Linear fit'), data: st.log ? [] : [{ x: xmin, y: icpt + slope * xmin }, { x: xmax, y: icpt + slope * xmax }], borderColor: '#2A2E2E', borderDash: [6, 4], borderWidth: 1.4, pointRadius: 0 }] },
    options: { maintainAspectRatio: false, animation: false, plugins: { legend: { display: false }, tooltip: { callbacks: { label: t => t.raw.n ? ` ${t.raw.n}: ${ecFmt(X, t.raw.x)} · ${ecFmt(Y, t.raw.y)}` : '' } } }, scales: { x: { type: st.log ? 'logarithmic' : 'linear', ...ecPad(xs, st.log), title: { display: true, text: lab(X) }, ticks: { callback: v => ecFmt(X, v, true) }, grid: { color: '#f0f0f0' } }, y: { type: st.log ? 'logarithmic' : 'linear', ...ecPad(idx.map(i => ay[i]), st.log), title: { display: true, text: lab(Y) }, ticks: { callback: v => ecFmt(Y, v, true) }, grid: { color: '#f0f0f0' } } }, onClick: (e, items) => { const it = items[0]; if (it && it.datasetIndex === 0) { const d = EC.charts.sc.data.datasets[0].data[it.index]; ecSelect(d.i, null, false); ecBenchScatter(); } } } });
}
function ecPad(vals, log) {   // fixed axis bounds from the data, so the fitted line cannot stretch the axes into impossible values
  if (log || !vals.length) return {};
  const lo = Math.min(...vals), hi = Math.max(...vals), pad = (hi - lo) * .06 || Math.abs(hi) * .1 || 1;
  return { min: lo >= 0 ? Math.max(0, lo - pad) : lo - pad, max: hi <= 0 ? Math.min(0, hi + pad) : hi + pad };
}
function ecBenchTrend() {
  const vis = ecVisible().filter(l => !EC.V[l.key].static); if (!vis.length) { $('#ebBody').innerHTML = `<div class="empty">${esc(T('Add a layer with more than one year of data to see its trend.'))}</div>`; return; }
  if (!ecNeedChart('trend')) return;
  const st = EC.tr = EC.tr || { id: vis[0].id }; if (!vis.find(l => l.id === st.id)) st.id = vis[0].id;
  const L = vis.find(l => l.id === st.id), v = EC.V[L.key], years = v.ys.filter(y => y >= 2010 || v.key.startsWith('fema'));
  const picks = [...EC.trend].filter(i => i != null).sort((a, b) => (a === EC.PR ? -1 : b === EC.PR ? 1 : a - b)).slice(0, 8);   // Puerto Rico first, so it is never the one cut
  $('#ebBody').innerHTML = `<div class="eb-tools"><label>${esc(T('Layer'))} <select id="trL">${vis.map(l => `<option value="${l.id}"${l.id === st.id ? ' selected' : ''}>${esc(T(EC.V[l.key].label))}</option>`).join('')}</select></label><label>${esc(T('Add a place'))} ${ecMuniSelect('trAdd', -1).replace('<select', '<select').replace('>', `><option value="">${esc(T('Choose…'))}</option>`)}</label><button type="button" class="btn small" id="trReset">${esc(T('Reset places'))}</button><span class="note">${esc(T("Lines follow this layer's settings ({norm}). Click a legend entry to hide a line.", { norm: ecLc(T((ecNormOptions(v).find(o => o[0] === L.norm) || [0, L.norm])[1])) }))}</span></div><div class="eb-chart"><canvas id="trCanvas"></canvas></div>`;
  $('#trL').onchange = e => { st.id = +e.target.value; ecBenchTrend(); };
  $('#trAdd').onchange = e => { if (e.target.value !== '') { EC.trend.add(+e.target.value); ecBenchTrend(); } };
  $('#trReset').onclick = () => { EC.trend = new Set([EC.PR, ...(EC.selected != null ? [EC.selected] : [])]); ecBenchTrend(); };
  const data = years.map(y => ecCalc(L, y)), c = $('#trCanvas'); c.setAttribute('role', 'img'); c.setAttribute('aria-label', T('Trend of {name} for {places}', { name: T(v.label), places: picks.map(i => EC.NM[i]).join(', ') }));
  EC.charts.tr = new Chart(c, { type: 'line', data: { labels: years, datasets: picks.map((i, k) => ({ label: EC.NM[i], data: data.map(a => a ? a[i] : null), borderColor: EC_LINES[k % 8], backgroundColor: EC_LINES[k % 8], borderWidth: i === EC.PR ? 3 : 2, pointRadius: 3, spanGaps: true, tension: .1 })) },
    options: { maintainAspectRatio: false, animation: false, plugins: { legend: { position: 'bottom', labels: { usePointStyle: true, boxWidth: 9 } }, tooltip: { callbacks: { label: t => ` ${t.dataset.label}: ${ecFmt(L, t.raw)}` } } }, scales: { y: { ticks: { callback: x => ecFmt(L, x, true) }, grid: { color: '#f0f0f0' } }, x: { grid: { display: false } } } } });
  ecTrendKeys(c, EC.charts.tr, years, L);
}
/** The trend chart is a slider for the keyboard (WAI-ARIA APG): the arrows move one year (Left and Down back, Right and Up on), Page Up and Page Down five, Home and End
    to the ends. The chosen year shows the chart's own tooltip, and a screen reader hears the year and each visible line's value (aria-valuetext). The pointer is unchanged. */
function ecTrendKeys(c, ch, years, L) {
  if (!years.length) return;
  const STEP = { ArrowLeft: -1, ArrowDown: -1, ArrowRight: 1, ArrowUp: 1, PageDown: -5, PageUp: 5, Home: -Infinity, End: Infinity };
  let k = years.length - 1;
  const text = () => T('{year}: {values}', { year: years[k], values: ch.data.datasets.map((d, di) => ch.isDatasetVisible(di) ? `${d.label} ${d.data[k] == null ? T('no value') : ecFmt(L, d.data[k])}` : null).filter(Boolean).join('; ') });
  const show = (on) => {
    const act = on ? ch.data.datasets.map((d, di) => ({ datasetIndex: di, index: k })).filter(a => ch.isDatasetVisible(a.datasetIndex) && ch.data.datasets[a.datasetIndex].data[k] != null) : [];
    const pt = act.length && ch.getDatasetMeta(act[0].datasetIndex).data[k];
    ch.setActiveElements(act); ch.tooltip.setActiveElements(act, pt ? { x: pt.x, y: pt.y } : { x: 0, y: 0 }); ch.update('none');
  };
  c.tabIndex = 0; c.setAttribute('role', 'slider'); c.setAttribute('aria-valuemin', years[0]); c.setAttribute('aria-valuemax', years.at(-1));
  const set = () => { c.setAttribute('aria-valuenow', years[k]); c.setAttribute('aria-valuetext', text()); };
  set();
  c.addEventListener('keydown', e => {
    const K = STEP[e.key]; if (K == null || e.altKey || e.ctrlKey || e.metaKey) return;
    e.preventDefault();
    k = !isFinite(K) ? (K < 0 ? 0 : years.length - 1) : Math.min(years.length - 1, Math.max(0, k + K));
    set(); show(true);
  });
  c.addEventListener('blur', () => show(false));
}

// ── Workbench: correlations, small multiples, two maps compared (plan B4; docs/workbench.md) ──
const ecLabel = (L) => T(EC.V[L.key].label);
function ecBenchMatrix() {
  const vis = ecVisible(); if (vis.length < 2) { $('#ebBody').innerHTML = `<div class="empty">${esc(T('Correlations need two visible layers or more.'))}</div>`; return; }
  const st = EC.mx = EC.mx || { method: 'pearson' }, use = vis.slice(0, 8), M = Core.stats.matrix(use.map(L => EC.eval[L.id].a), EC.PR, st.method);
  const cls = (r) => r == null ? -1 : r < -.5 ? 0 : r < -.1 ? 1 : r <= .1 ? 2 : r <= .5 ? 3 : 4, DIV = Core.palettes.DIVERGING;
  const cell = (i, j) => { if (i === j) return `<td class="num mx-d">—</td>`; const r = M.r[i][j], c = cls(r); return `<td class="num" style="background:${c < 0 ? '#fff' : DIV[c]};color:${c === 0 || c === 4 ? '#fff' : '#2A2E2E'}"><b>${r == null ? '—' : r.toFixed(2)}</b><small>n = ${M.n[i][j]}</small></td>`; };
  $('#ebBody').innerHTML = `<div class="eb-tools"><label>${esc(T('Method'))} <select id="mxM"><option value="pearson"${st.method === 'pearson' ? ' selected' : ''}>${esc(T('Pearson (straight-line)'))}</option><option value="spearman"${st.method === 'spearman' ? ' selected' : ''}>${esc(T('Spearman (rank order)'))}</option></select></label><span class="note">${esc(T('Each pair uses the municipalities that have a value for both (n). A correlation across places is a pattern, not cause and effect: large places, survey noise and a third factor can drive it.'))}${vis.length > 8 ? ' ' + esc(T('The first 8 visible layers are shown.')) : ''}</span></div>
    <div class="eb-scroll" tabindex="0" role="region" aria-label="${esc(T('Correlation matrix of the visible layers, scrollable'))}"><table class="ec-tbl wide mx"><thead><tr><th scope="col">${esc(T('Layer'))}</th>${use.map((L, j) => `<th scope="col" class="num">${j + 1}</th>`).join('')}</tr></thead><tbody>${use.map((L, i) => `<tr><th scope="row"><b>${i + 1}</b> ${esc(ecLabel(L))}<small>${esc(ecChip(L))}${L.norm !== 'value' ? ' · ' + esc(ecLc(E.normLabel(L))) : ''}</small></th>${use.map((_, j) => cell(i, j)).join('')}</tr>`).join('')}</tbody></table></div>
    <div class="note">${esc(T('Colours: dark red is a strong negative correlation (below -0.5), dark blue a strong positive one (above 0.5); grey is near none (-0.1 to 0.1).'))}</div>`;
  $('#mxM').onchange = e => { st.method = e.target.value; ecBenchMatrix(); };
}
const ecPaths = () => EC.mm || (EC.mm = Core.minimap.project(S.muniFc, EC.NM.slice(0, EC.PR), 600));
function ecClassFill(L, y, a) {   // the colours of one shaded map of layer L in year y, with the layer's own classes (held across years when the layer holds them)
  const b = E.breaks(L, y), cols = b.div ? Core.palettes.DIVERGING : E.ramp(L);
  return { fills: a.slice(0, EC.PR).map(x => { const c = Core.classify.classOf(b, x); return c < 0 ? Core.palettes.NOVAL : cols[c]; }), rows: cols.map((c, i) => ({ color: c, label: b.div ? Core.stack.divLabels(E, L, b)[i] : Core.classify.single(b, i) ? E.fmt(L, b.edges[i], true) : T('{from} to {to}', { from: E.fmt(L, b.edges[i], true), to: E.fmt(L, b.edges[i + 1], true) }) })).filter((_, i) => !Core.classify.hidden(b, i)) };
}
const ecMiniLegend = (rows) => `<div class="mm-legend">${rows.map(r => `<span><i style="background:${r.color}"></i>${esc(r.label)}</span>`).join('')}<span><i style="background:${Core.palettes.NOVAL}"></i>${esc(T('No data'))}</span></div>`;
const ecTitles = (L, a) => EC.NM.slice(0, EC.PR).map((n, i) => `${n}: ${a[i] == null ? T('No data') : ecFmt(L, a[i])}`);
function ecBenchMultiples() {
  const vis = ecVisible(); if (!vis.length) { $('#ebBody').innerHTML = `<div class="empty">${esc(T('Add a layer to see small multiples.'))}</div>`; return; }
  const st = EC.sm = EC.sm || { by: 'year', id: vis[0].id }; if (!vis.find(l => l.id === st.id)) st.id = vis[0].id;
  const L = vis.find(l => l.id === st.id), v = EC.V[L.key], P = ecPaths();
  let maps = [], legend = '', note;
  if (st.by === 'year') {
    const H = { ...L, fixed: true }, ys = v.ys.filter(y => E.calc(H, y)).slice(-12);   // one set of classes for every year, so a colour means the same in each map
    maps = ys.map(y => { const a = E.calc(H, y), f = ecClassFill(H, y, a); legend = ecMiniLegend(f.rows); return { cap: Core.time.label(v, y), sub: `${T('Puerto Rico')}: ${a[EC.PR] == null ? '—' : ecFmt(H, a[EC.PR])}`, svg: Core.minimap.svg(P, f.fills, { label: T('{name}, {year}', { name: ecLabel(L), year: y }), titles: ecTitles(H, a), thin: true }) }; });
    note = v.ys.length > 12 ? T('The last 12 years with values; the classes are the same in every map.') : T('The classes are the same in every map, so a colour means the same in each year.');
  } else {
    maps = vis.slice(0, 8).map(M => { const ev = EC.eval[M.id], f = ecClassFill(M, ev.y, ev.a); return { cap: ecLabel(M), sub: ecChip(M), svg: Core.minimap.svg(P, f.fills, { label: ecLabel(M), titles: ecTitles(M, ev.a), thin: true }), legend: ecMiniLegend(f.rows) }; });
    note = T('Each map has its own classes: compare where values are high or low, not the colours across maps.');
  }
  $('#ebBody').innerHTML = `<div class="eb-tools"><label>${esc(T('One map for each'))} <select id="smBy"><option value="year"${st.by === 'year' ? ' selected' : ''}>${esc(T('year of one layer'))}</option><option value="layer"${st.by === 'layer' ? ' selected' : ''}>${esc(T('visible layer'))}</option></select></label>${st.by === 'year' ? `<label>${esc(T('Layer'))} <select id="smL">${vis.map(l => `<option value="${l.id}"${l.id === st.id ? ' selected' : ''}>${esc(ecLabel(l))}</option>`).join('')}</select></label>` : ''}<span class="note">${esc(note)}</span></div>
    <div class="eb-scroll"><div class="mm-grid">${maps.map(m => `<figure class="mm-cell">${m.svg}<figcaption><b>${esc(m.cap)}</b><small>${esc(m.sub)}</small></figcaption>${m.legend || ''}</figure>`).join('')}</div>${st.by === 'year' ? `<div class="mm-key"><b>${esc(E.title(L))}</b>${legend}</div>` : ''}</div>`;
  $('#smBy').onchange = e => { st.by = e.target.value; ecBenchMultiples(); };
  if ($('#smL')) $('#smL').onchange = e => { st.id = +e.target.value; ecBenchMultiples(); };
}
function ecBenchSwipe() {
  const vis = ecVisible(); if (vis.length < 2) { $('#ebBody').innerHTML = `<div class="empty">${esc(T('Comparing two maps needs two visible layers.'))} ${esc(vis.length ? T('Add one more.') : T('Add two layers.'))}</div>`; return; }
  const st = EC.sw = EC.sw || { a: vis[0].id, b: vis[1].id, pos: 50 };
  if (!vis.find(l => l.id === st.a)) st.a = vis[0].id; if (!vis.find(l => l.id === st.b) || st.b === st.a) st.b = vis.find(l => l.id !== st.a).id;
  const A = vis.find(l => l.id === st.a), B = vis.find(l => l.id === st.b), ea = EC.eval[A.id], eb = EC.eval[B.id], fa = ecClassFill(A, ea.y, ea.a), fb = ecClassFill(B, eb.y, eb.a), P = ecPaths();
  const titles = EC.NM.slice(0, EC.PR).map((n, i) => `${n}: ${ecLabel(A)} ${ea.a[i] == null ? T('No data') : ecFmt(A, ea.a[i])} · ${ecLabel(B)} ${eb.a[i] == null ? T('No data') : ecFmt(B, eb.a[i])}`);
  const g = (f) => P.d.map((d, i) => d ? `<path d="${d}" fill="${f.fills[i]}"><title>${esc(titles[i])}</title></path>` : '').join(''), x = P.w * st.pos / 100;
  const opt = (sel) => vis.map(l => `<option value="${l.id}"${l.id === sel ? ' selected' : ''}>${esc(ecLabel(l))}</option>`).join('');
  $('#ebBody').innerHTML = `<div class="eb-tools"><label>${esc(T('Left'))} <select id="swA">${opt(st.a)}</select></label><label>${esc(T('Right'))} <select id="swB">${opt(st.b)}</select></label><span class="note">${esc(T('Drag the slider to move the divider: the left side shows one layer, the right side the other. Each keeps its own classes.'))}</span></div>
    <div class="eb-scroll"><div class="sw-map"><svg viewBox="0 0 ${P.w} ${P.h}" role="img" aria-label="${esc(T('{a} on the left and {b} on the right of a divider', { a: ecLabel(A), b: ecLabel(B) }))}"><defs><clipPath id="swClip"><rect id="swRect" x="${x}" y="0" width="${P.w}" height="${P.h}"/></clipPath></defs><g stroke="#fff" stroke-width=".8">${g(fa)}</g><g stroke="#fff" stroke-width=".8" clip-path="url(#swClip)">${g(fb)}</g><line id="swLine" x1="${x}" x2="${x}" y1="0" y2="${P.h}" stroke="#2A2E2E" stroke-width="2.5"/></svg></div>
    <input type="range" id="swPos" class="sw-range" min="0" max="100" step="1" value="${st.pos}" aria-label="${esc(T('Divider position'))}">
    <div class="sw-keys"><div><b>${esc(T('Left'))}: ${esc(E.title(A, ea.y))}</b> <small>${esc(ecChip(A))}</small>${ecMiniLegend(fa.rows)}</div><div><b>${esc(T('Right'))}: ${esc(E.title(B, eb.y))}</b> <small>${esc(ecChip(B))}</small>${ecMiniLegend(fb.rows)}</div></div></div>`;
  $('#swA').onchange = e => { st.a = +e.target.value; if (st.a === st.b) st.b = vis.find(l => l.id !== st.a).id; ecBenchSwipe(); };
  $('#swB').onchange = e => { st.b = +e.target.value; if (st.a === st.b) st.a = vis.find(l => l.id !== st.b).id; ecBenchSwipe(); };
  $('#swPos').oninput = e => { st.pos = +e.target.value; const nx = P.w * st.pos / 100; $('#swRect').setAttribute('x', nx); $('#swLine').setAttribute('x1', nx); $('#swLine').setAttribute('x2', nx); };
}

// ── The composite index a person builds (plan B6; Core.composite; ecIxApply, IX and IX_T are in economy.js) ──
function ecBenchComposite() {
  const st = EC.ixDraft = EC.ixDraft || (EC.ix ? JSON.parse(JSON.stringify(EC.ix)) : { t: 'z', items: ecVisible().filter(l => l.key !== IX).slice(0, 4).map(L => ({ key: L.key, dir: 0, w: 1 })) });
  const groups = {}; E.list().filter(v => v.key !== IX).forEach(v => (groups[v.group] = groups[v.group] || []).push(v));
  const add = `<select id="ixAdd" aria-label="${esc(T('Add an input'))}"><option value="">${esc(T('Add an input…'))}</option>${Object.keys(groups).map(g => `<optgroup label="${esc(T(g))}">${groups[g].filter(v => !st.items.some(it => it.key === v.key)).map(v => `<option value="${v.key}">${esc(T(v.label))}</option>`).join('')}</optgroup>`).join('')}</select>`;
  const rows = st.items.map((it, k) => `<tr data-k="${k}"><th scope="row">${esc(T(EC.V[it.key].label))}<small>${esc(ecLc(E.normLabel({ key: it.key, norm: Core.normalize.defaultNorm(EC.V[it.key], 'fill') })))}</small></th><td><select data-f="dir" aria-label="${esc(T('Direction'))}"${it.dir ? '' : ' aria-invalid="true"'}>${it.dir ? '' : `<option value="0" selected>${esc(T('Choose…'))}</option>`}<option value="1"${it.dir > 0 ? ' selected' : ''}>${esc(T('higher is better'))}</option><option value="-1"${it.dir < 0 ? ' selected' : ''}>${esc(T('lower is better'))}</option></select></td><td><input type="number" data-f="w" min="0.1" max="100" step="0.1" value="${it.w}" aria-label="${esc(T('Weight'))}" class="ix-w"></td><td><button type="button" class="icon-btn small" data-del="${k}" aria-label="${esc(T('Remove {name}', { name: T(EC.V[it.key].label) }))}"><span class="ms-icon" aria-hidden="true">close</span></button></td></tr>`).join('');
  const total = st.items.reduce((s, it) => s + it.w, 0);
  let result = '';
  if (EC.ix && EC.V[IX]) {
    const { spec, ins, res } = EC.V[IX].ix, order = [...Array(EC.PR).keys()].sort((p, q) => (res.score[q] ?? -Infinity) - (res.score[p] ?? -Infinity) || EC.NM[p].localeCompare(EC.NM[q], 'es'));
    const f = (x) => x == null ? '—' : x.toFixed(spec.t === 'z' ? 2 : 1), blank = res.score.slice(0, EC.PR).filter(x => x == null).length;
    const flat = spec.items.filter((it, k) => res.scaled[k].every(x => x == null)).map(it => T(EC.V[it.key].label));
    result = `<h3 class="sec">${esc(T('Result'))}</h3><div class="note ix-method">${esc(EC.V[IX].definition)}</div>${flat.length ? `<div class="note" role="status">${esc(T('These inputs have the same value in every municipality (or a value in only one), so they count as missing: {list}.', { list: flat.join('; ') }))}</div>` : ''}${blank ? `<div class="note">${esc(Tn(blank, '{n} municipality is left blank: less than 80% of the weight has values.', '{n} municipalities are left blank: less than 80% of the weight has values.'))}</div>` : ''}
      <div class="btn-row"><button type="button" class="btn small" id="ixCsv"><span class="ms-icon" aria-hidden="true">download</span>${esc(T('Download CSV'))}</button></div>
      <div class="eb-scroll" tabindex="0" role="region" aria-label="${esc(T('Composite scores and what each input adds, scrollable'))}"><table class="ec-tbl wide"><thead><tr><th scope="col">${esc(T('Rank'))}</th><th scope="col">${esc(T('Municipality'))}</th><th scope="col" class="num">${esc(T('Score'))}</th><th scope="col" class="num">${esc(T('Weight with values'))}</th>${spec.items.map((it, k) => `<th scope="col" class="num">${esc(T(ins[k].v.label))}<small>${esc(T('adds'))}</small></th>`).join('')}</tr></thead><tbody>${order.map((i, r) => `<tr class="${i === EC.selected ? 'me' : ''}"><td class="num">${res.score[i] == null ? '—' : r + 1}</td><th scope="row">${esc(EC.NM[i])}</th><td class="num"><b>${f(res.score[i])}</b></td><td class="num">${Math.round(res.cover[i] * 100)}%</td>${res.parts[i].map(x => `<td class="num">${f(x)}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`;
  }
  $('#ebBody').innerHTML = `<div class="ix-warn" role="note"><span class="ms-icon" aria-hidden="true">warning</span>${esc(T(IX_LABEL))}. ${esc(T('The inputs, directions and weights are your choice; the result depends on them.'))}</div>
    <div class="eb-tools"><label>${esc(T('Scale'))} <select id="ixT">${Core.composite.TRANSFORMS.map(t => `<option value="${t}"${st.t === t ? ' selected' : ''}>${esc(T(IX_T[t]))}</option>`).join('')}</select></label>${add}<button type="button" class="btn small" id="ixVis">${esc(T('Start from the visible layers'))}</button></div>
    ${st.items.length ? `<table class="ec-tbl ix-in"><thead><tr><th scope="col">${esc(T('Input'))}</th><th scope="col">${esc(T('Direction'))}</th><th scope="col">${esc(T('Weight'))}</th><th scope="col"><span class="sr-only">${esc(T('Remove'))}</span></th></tr></thead><tbody>${rows}</tbody></table><div class="note">${esc(T('Weights add up to {w}; each input counts in proportion to its weight. Counts and dollar totals enter per resident or per 1,000 residents, as a shaded map shows them.', { w: +total.toFixed(2) }))}</div>` : `<div class="empty">${esc(T('Add two inputs or more.'))}</div>`}
    <div class="btn-row">${st.items.some(it => !it.dir) ? `<div class="note" role="status">${esc(T('Choose for each input whether a higher value is better or worse. No direction is set for you: it depends on what the index is meant to show.'))}</div>` : ''}<button type="button" class="btn primary" id="ixGo"${st.items.length < 2 || st.items.some(it => !it.dir) ? ' disabled' : ''}>${esc(EC.ix ? T('Update the map') : T('Put on the map'))}</button>${EC.ix ? `<button type="button" class="btn" id="ixOff">${esc(T('Remove the composite'))}</button>` : ''}</div>${result}`;
  $('#ebBody').classList.add('eb-free');   // a form and a table one under the other: the whole view scrolls
  $('#ixT').onchange = e => { st.t = e.target.value; ecBenchComposite(); };
  $('#ixAdd').onchange = e => { const k = e.target.value; if (k && st.items.length < Core.composite.MAX_ITEMS) { st.items.push({ key: k, dir: 0, w: 1 }); ecBenchComposite(); } else if (k) toast(T('A composite can have up to {n} inputs.', { n: Core.composite.MAX_ITEMS }), 4000); };
  $('#ixVis').onclick = () => { st.items = ecVisible().filter(l => l.key !== IX).slice(0, Core.composite.MAX_ITEMS).map(L => ({ key: L.key, dir: 0, w: 1 })); ecBenchComposite(); };
  const tb = $('#ebBody').querySelector('.ix-in');
  if (tb) { tb.onchange = e => { const tr = e.target.closest('tr[data-k]'), f = e.target.dataset.f; if (!tr || !f) return; const it = st.items[+tr.dataset.k]; if (f === 'dir') it.dir = +e.target.value; else { const w = +e.target.value; if (w > 0) it.w = Math.min(100, Math.max(0.1, w)); } ecBenchComposite(); };   // a weight outside 0.1 to 100 is brought inside; an empty or zero weight keeps the last one
    tb.onclick = e => { const b = e.target.closest('[data-del]'); if (b) { st.items.splice(+b.dataset.del, 1); ecBenchComposite(); } }; }
  $('#ixGo').onclick = () => { if (st.items.length < 2 || st.items.some(it => !it.dir)) return; EC.ixDraft = null; ecIxApply(JSON.parse(JSON.stringify(st)), true); ecRender(); toast(EC.layers.some(l => l.key === IX) ? T('The composite is on the map. It is your own index, not an official one.') : T('The composite is worked out and its scores are in the table. To shade it on the map, remove one of the two shaded layers and press the button again.'), 7000); };
  if ($('#ixOff')) $('#ixOff').onclick = () => { EC.ixDraft = null; ecIxApply(null); ecRender(); };
  if ($('#ixCsv')) $('#ixCsv').onclick = () => { const { spec, ins, res } = EC.V[IX].ix; ecSaveCsv('pr_user_composite.csv', ['GEOID', T('Municipality'), T('Score'), T('Weight with values'), ...spec.items.map((it, k) => T('{name}: adds', { name: T(ins[k].v.label) }))], EC.NM.slice(0, EC.PR).map((n, i) => [EC.ids[i], n, res.score[i], +(res.cover[i] * 100).toFixed(1), ...res.parts[i]])); };
}
