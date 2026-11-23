/* PR Data Observatory: shading the Economy tab's map by barrio. A shaded layer whose dataset has values for the 901 barrios (the American Community Survey
   datasets of acs_barrio.json) can be drawn on the barrio outlines instead of the 78 municipalities: Settings > Area. Loaded the first time a layer asks for it
   (economy.js ecLevelDraw). The values come from the engine's contract (E.series(layer, period, 'barrio')), so the classes, ramps and the 30% margin rule are the
   municipal map's. At this level a value is shown as published or as a percentile among the barrios: the rescalings of a municipio need its residents and land.
   A dataset that brings its own barrio values names their file (barrioFile: conditions_barrio.json); that file is read instead of acs_barrio.json (docs/conditions.md). */
const EconLevel = (() => {
  const TK = (t) => t;   // translated where it is shown, with T()
  const st = { fc: null, ready: null, layer: null, hatch: null, key: '', s: null, b: null, nv: null, tried: new Set() };
  // the outlines, and the barrio values: the survey's (acs_barrio.json), the file the layer's dataset names (barrioFile), or none when the dataset came with its barrio values (level: the WCRP ranks)
  const ensure = (L) => { const v = L && EC.V[L.key] || {}, own = v.barrioFile;
    return Promise.all([st.ready || (st.ready = getJson('data/barrios.geojson', T('barrios')).catch(e => { st.ready = null; throw e; })), own ? ECON.loadLevelFile(own) : v.level ? null : ECON.loadLevel('barrio')]).then(([fc]) => { st.fc = fc; }); };

  function series(L) {   // the layer at the barrio level for the year the map shows
    const s = E.series({ ...L, norm: L.norm === 'pctile' ? 'pctile' : 'value' }, EC.year, 'barrio'); if (!s || !s.values) return null;
    const by = new Map(s.ids.map((id, i) => [id, i])), pool = s.values.filter(x => x != null && isFinite(x)).sort((p, q) => p - q);
    const manual = L.classes === 'manual' ? Core.classify.parseBreaks(L.breaks, 5) : null, fifths = !manual && EC.V[L.key].fifths && s.meta.norm !== 'pctile';
    // a WCRP vulnerability index is drawn by its ranks, the fifths of the index (0-20 is rank 1 ... above 80 is rank 5), whatever the class method, unless a person types limits
    const b = Core.classify.make(pool, fifths ? { method: 'manual', k: 5, edges: [20, 40, 60, 80] } : { method: manual ? 'manual' : L.classes === 'manual' ? 'quantile' : L.classes, k: 5, edges: manual });
    const weak = s.values.map((v, i) => v != null && s.moe && s.moe[i] != null && Core.reliability.isUnreliable(v, s.moe[i]));
    return { s, by, b, cols: E.ramp(L), weak, fifths };
  }
  const label = (s, i, f) => { const n = s.names && s.names[i]; return n ? (I18N.lang === 'es' ? n.es : n.en) : (f && f.properties.barrio) || s.ids[i]; };   // a barrio file without names: the outline's
  const RANKS = [TK('1 · Low'), TK('2 · Medium-low'), TK('3 · Medium'), TK('4 · Medium-high'), TK('5 · High')];   // the WCRP ranks: fifths of the index
  const rankOf = (x) => x == null ? -1 : Math.min(4, Math.max(0, Math.ceil(x / 20 - 1e-7) - 1));   // x is the index times 100; ceil(5 × index) − 1, as wcrp_rvi.py
  const fmtV = (r, x) => x == null ? T('No data') : r.s.meta.norm === 'pctile' ? T('percentile {n}', { n: fmt(x, 0) }) : E.fmt({ ...EC.layers.find(l => l.id === st.key) || {}, norm: 'value' }, x, true);

  function draw(L) {
    if (!L) { map.getPane('econfill').style.pointerEvents = 'none'; if (st.layer && map.hasLayer(st.layer)) map.removeLayer(st.layer); if (st.hatch && map.hasLayer(st.hatch)) map.removeLayer(st.hatch); st.key = ''; st.s = null; return; }
    const has = ((EC.V[L.key] || {}).levels || {}).barrio;   // asked once per dataset, so a dataset with no barrio values falls back to the municipios instead of asking again
    if (!st.fc || (!has && !st.tried.has(L.key))) { st.tried.add(L.key); ensure(L).then(() => ecRender(), () => { st.tried.delete(L.key); toast(T('The barrio values could not be loaded. Check your connection and try again.')); }); return; }
    const r = series(L); st.key = L.id; st.s = r; st.nv = (EC.V[L.key] || {}).noValue || null;   // nv: what an empty barrio means (no road to a hospital), said instead of "No data"
    if (!r) { draw(null); return; }
    const colorOf = id => { const i = r.by.get(id), v = i == null ? null : r.s.values[i], c = Core.classify.classOf(r.b, v, 5); return c < 0 ? Core.palettes.NOVAL : r.cols[c]; };
    if (!st.layer) st.layer = window.L.geoJSON(st.fc, { pane: 'econfill', style: () => ({}), onEachFeature: (f, lyr) => lyr.bindTooltip(() => {
      const c = st.s, i = c && c.by.get(f.properties.geoid); if (i == null) return '';
      const v = c.s.values[i], m = c.s.moe && c.s.moe[i];
      const why = v == null && c.s.flags.why && c.s.flags.why[i];   // an empty barrio for its own reason (no residents) before the dataset's (not mapped)
      if (c.fifths) return `<b>${esc(label(c.s, i, f))}</b> · ${esc(f.properties.municipality || '')}<br>${v == null ? esc(T(why || 'No data')) : esc(T('Rank {rank} · index {value} of 100', { rank: T(RANKS[rankOf(v)]), value: fmt(v, 2) }))}`;
      return `<b>${esc(label(c.s, i, f))}</b> · ${esc(f.properties.municipality || '')}<br>${why ? esc(T(why)) : v == null && st.nv ? esc(T(st.nv)) : esc(fmtV(c, v))}${m != null && c.s.meta.norm !== 'pctile' ? ` ± ${esc(fmtV(c, m))}` : ''}${c.weak[i] ? `<br><i>${esc(T('less reliable: the margin of error is above 30% of the estimate'))}</i>` : ''}`;
    }, { sticky: true }) });
    map.getPane('econfill').style.pointerEvents = 'auto';   // the barrios answer hover with their own value; a click still reaches the map (bubbling)
    st.layer.setStyle(f => ({ color: '#fff', weight: .4, fillColor: colorOf(f.properties.geoid), fillOpacity: L.opacity }));
    if (!map.hasLayer(st.layer)) st.layer.addTo(map);
    const weakIds = new Set(r.s.ids.filter((_, i) => r.weak[i]));
    if (!st.hatch) st.hatch = window.L.geoJSON(null, { pane: 'echatch', interactive: false, renderer: window.L.svg({ pane: 'echatch' }), style: { stroke: false, fill: true, fillColor: 'url(#ec-hatch)', fillOpacity: 1 } });
    st.hatch.clearLayers().addData(st.fc.features.filter(f => weakIds.has(f.properties.geoid)));
    if (weakIds.size && !map.hasLayer(st.hatch)) st.hatch.addTo(map); else if (!weakIds.size && map.hasLayer(st.hatch)) map.removeLayer(st.hatch);
    ecHatch([]);   // the municipal hatching stays off while the barrios are shown
    const svg = map.getPane('echatch').querySelector('svg');
    if (svg && !svg.querySelector('#ec-hatch')) svg.insertAdjacentHTML('afterbegin', '<defs><pattern id="ec-hatch" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><line x1="0" y1="0" x2="0" y2="6" stroke="#2A2E2E" stroke-opacity=".6" stroke-width="1.4"/><line x1="2.2" y1="0" x2="2.2" y2="6" stroke="#fff" stroke-opacity=".6" stroke-width="1"/></pattern></defs>');
  }

  function legend(L) {   // the legend block of the barrio layer, in the municipal legend's form
    const r = st.s; if (!r || st.key !== L.id) return `<div class="el-block"><div class="el-t">${esc(T(EC.V[L.key].label))}</div><div class="row">${esc(T('Loading the barrios…'))}</div></div>`;
    const v = EC.V[L.key], n = [0, 0, 0, 0, 0], whyN = new Map(); let nod = 0;   // whyN: the empty barrios that have a reason of their own, counted by reason
    r.s.values.forEach((x, i) => { const c = Core.classify.classOf(r.b, x, 5), w = x == null && r.s.flags.why && r.s.flags.why[i]; if (w) whyN.set(w, (whyN.get(w) || 0) + 1); else if (c < 0) nod++; else n[c]++; });
    if (r.fifths) return `<div class="el-block"><div class="el-t">${esc(T(v.label))} · ${esc(T('by barrio'))}</div>`
      + r.cols.map((c, i) => `<div class="row"><span class="sw" style="background:${c}"></span>${esc(T(RANKS[i]))}<small>${n[i]}</small></div>`).join('')
      + (nod ? `<div class="row"><span class="sw" style="background:${Core.palettes.NOVAL}"></span>${esc(T('No data'))}<small>${nod}</small></div>` : '')
      + [...whyN].map(([w, k]) => `<div class="row"><span class="sw" style="background:${Core.palettes.NOVAL}"></span>${esc(T(w))}<small>${k}</small></div>`).join('')
      + `<div class="note">${esc(T('WCRP Risk and Vulnerability Indicators: each rank is a fifth of the barrios, 5 the most vulnerable. A rank compares barrios with each other; it is not a measure of need.'))} <a href="wcrp.html">${esc(T('How the index is built'))}</a></div></div>`;
    const lab = i => Core.classify.single(r.b, i) ? fmtV(r, r.b.edges[i]) : T('{from} to {to}', { from: fmtV(r, r.b.edges[i]), to: fmtV(r, r.b.edges[i + 1]) });   // a class of one value is named by it ("0.00%"); an empty one that ties leave is not shown
    const weak = r.weak.filter(Boolean).length, asPub = (L.norm !== 'value' && L.norm !== 'pctile') || L.real;   // the barrio values are as published: no rescaling, no inflation adjustment
    const y = r.s.meta.period, title = E.title({ ...L, norm: r.s.meta.norm, real: false }, y);
    // the period the barrio map shows, from the barrio series itself (acs_barrio.json starts later than the municipal series): a survey's five-year window named by its years, a snapshot,
    // or a year of a dataset that brings its own yearly barrio file (FCC broadband, night lights: no survey, no margin of error)
    const tt = r.s.meta.timeType, win = tt === 'window', fl = r.s.flags, src = (v.sources || []).filter(s => s !== 'census_tiger').map(s => (EC.sources[s] || {}).name).filter(Boolean);
    const chip = tt === 'snapshot' ? T('snapshot {year}', { year: y }) : (win ? `${y - 4}–${y}` : String(y)) + (fl.exact ? '' : ' · ' + T(fl.early ? (win ? 'the first barrio window' : 'the first barrio year') : win ? 'the latest barrio window' : 'the latest barrio year'));
    return `<div class="el-block"><div class="el-t">${esc(title)} · ${esc(T('by barrio'))} <small>${esc(chip)}${asPub ? ' · ' + esc(T('as published')) : ''}</small></div>`
      + r.cols.map((c, i) => Core.classify.hidden(r.b, i) ? '' : `<div class="row"><span class="sw" style="background:${c}"></span>${esc(lab(i))}<small>${n[i]}</small></div>`).join('')
      + (nod ? `<div class="row"><span class="sw" style="background:${Core.palettes.NOVAL}"></span>${esc(v.noValue ? T(v.noValue) : T('No data'))}<small>${nod}</small></div>` : '')
      + [...whyN].map(([w, k]) => `<div class="row"><span class="sw" style="background:${Core.palettes.NOVAL}"></span>${esc(T(w))}<small>${k}</small></div>`).join('')
      + (weak ? `<div class="row rel"><span class="sw hatch"></span>${esc(T('less reliable (margin of error above 30%)'))}<small>${weak}</small></div>` : '')
      + `<div class="note">${esc(win ? T('901 barrios, American Community Survey 5-year estimates. Hover a barrio for its value and margin of error. The workbench and the table still show the municipalities.') : T('901 barrios. Hover a barrio for its value. The workbench and the table still show the municipalities.'))}${!win && src.length ? ' ' + esc(T('Source: {source}', { source: src.join('; ') })) + '.' : ''}${!win && v.tag === 'estimate' ? ' ' + esc(T('The barrio values are estimates: the dataset\'s window says how they are made.')) : ''}${v.caution ? ' ' + esc(T(v.caution)) : ''}${asPub ? ' ' + esc(T('At the barrio level a value is shown as published or as a percentile.')) : ''}</div></div>`;
  }
  return { draw, legend, ensure };
})();
