/* Capture script for the Economy tab of the 2D map (plan item 6 regression harness). Runs in a browser page that has loaded index.html (any language), through
   the browser pane's javascript tool, and posts what the tab shows to the local collector (tests/browser/README.md):

     eval(await (await fetch('http://127.0.0.1:8099/s/capture_economy.js')).text())

   It exercises the public surface only (ECON.api, the DOM, the Leaflet layers the tab owns), so the same script runs on the old and the new code and the
   two captures can be compared with tests/browser/compare.py. The captures hold no personal data: they are aggregates of the published series. */
(async () => {
  const TAG = location.port === '8022' ? 'old' : 'new', LANG = new URLSearchParams(location.search).get('lang') || 'es';
  const wait = (ms) => new Promise(r => setTimeout(r, ms));
  const post = (name, obj) => fetch('http://127.0.0.1:8099/save?name=' + name, { method: 'POST', body: JSON.stringify(obj) }).then(r => r.json());
  const html = (sel) => { const e = document.querySelector(sel); return e ? e.innerHTML.replace(/data-id="\d+"/g, 'data-id="#"') : null; };
  const api = ECON.api;
  if (!(await api.ready())) return { error: 'the economy data did not load' };
  const out = { tag: TAG, lang: LANG, env: { width: innerWidth, mobile: typeof isMobile === 'function' ? isMobile() : null }, years: api.years(), base: api.base(), places: api.places(), datasets: api.datasets(), perKey: {}, configs: {}, ui: {} };

  // 1. every dataset: its options, defaults, units and values under every normalisation, for three years
  const NUMS = [0, 1.2345, 1234567.891, -5.5, 0.04];
  for (const d of out.datasets) {
    const k = d.key, opts = api.normOptions(k), e = { norm: opts, defaultFill: api.defaultNorm(k, 'fill'), defaultSymbol: api.defaultNorm(k, 'symbol'), dictId: api.dictId(k), units: {}, fmt: {}, values: {} };
    for (const [n] of opts) {
      e.units[n] = api.unitLabel(k, n);
      e.fmt[n] = NUMS.map(x => api.fmt(k, x, n)).concat([api.fmt(k, null, n)]);
      for (const y of [null, 2012, 2020]) for (const real of (d.unit === '$' ? [false, true] : [false])) {
        const r = api.values(k, { year: y, norm: n, real, base: 2014 });
        e.values[`${n}|${y}|${real ? 'real' : 'nominal'}`] = r ? { year: r.year, exact: r.exact, values: r.values } : null;
      }
    }
    out.perKey[k] = e;
  }

  // 2. layer stacks, as the tab draws them
  const CFG = (await (await fetch('http://127.0.0.1:8099/s/economy_configs.json')).json()).map(c => [c.id, c.layers.map(l => { const { key, mode, ...o } = l; return [key, mode, o]; }), c.year, c.base]);
  const BENCH = new Set(['pay_fill', 'biv_poverty_unemployment', 'three_layers_2017', 'income_change_2023']);
  const fills = () => { const L = EC.fillLayer, o = {}; if (!L || !map.hasLayer(L)) return null; L.eachLayer(l => { o[l.feature.properties.municipality] = [l.options.fillColor, l.options.fillOpacity]; }); return o; };
  const syms = () => { const o = []; EC.symGroup.eachLayer(l => o.push([l.getLatLng().lat.toFixed(4), l.getLatLng().lng.toFixed(4), +l.options.radius.toFixed(3), l.options.fillColor, l.options.fillOpacity])); return o; };
  for (const [id, layers, year, base] of CFG) {
    const spec = { clear: true, layers: layers.map(([key, mode, o]) => ({ key, mode, ...(o || {}) })), year, context: [] };
    if (base) spec.base = base; else spec.base = 2014;
    const r = await api.show(spec);
    await wait(330);
    const c = { applied: r.applied, skipped: r.skipped, legend: html('#econLegend'), cards: html('#ecLayers'), status: (document.querySelector('#ecStatus') || {}).textContent, fills: fills(), symbols: syms(), state: api.state(), encode: ECON.encode(), extra: ECON.extra(), body: [...document.body.classList].filter(x => /^econ/.test(x)).sort() };
    if (BENCH.has(id)) {
      await api.show({ clear: false, select: 'San Juan', bench: 'inspect' }); await wait(120); c.inspect = html('#econBench');
      await api.show({ clear: false, bench: 'table' }); await wait(120); c.table = html('#ebBody');
      try { map.fire('click', { latlng: L.latLng(18.0111, -66.6141) }); await wait(150); const p = document.querySelector('.ec-pop .leaflet-popup-content'); c.popup = p ? p.innerHTML : null; map.closePopup(); } catch (e) { c.popup = 'error ' + e.message; }
      if (layers.length >= 2) { await api.show({ clear: false, bench: 'scatter' }); await wait(200); c.scatter = (EC.charts.sc && EC.charts.sc.data.datasets[0].data.map(d => [d.n, +d.x.toFixed(6), +d.y.toFixed(6)])) || null; c.scatterNote = html('#ebBody .eb-tools'); }
      await api.show({ clear: false, bench: 'trend' }); await wait(200); c.trend = (EC.charts.tr && EC.charts.tr.data.datasets.map(d => [d.label, d.data.map(x => x == null ? null : +(+x).toFixed(6))])) || null; c.trendLabels = (EC.charts.tr && EC.charts.tr.data.labels) || null;
      { const b = document.querySelector('#ebClose'); if (b) b.click(); }
    }
    out.configs[id] = c;
  }

  // 3. the dataset browser, presets and sources, which depend on every dataset
  await api.show({ clear: true, layers: [], year: null, context: [] }); await wait(200);
  out.ui.browse = html('#ecBrowse'); out.ui.presets = html('#ecPresets'); out.ui.sources = html('#ecSources'); out.ui.skeleton = html('#econRoot').length;
  out.ui.yearSelect = html('#ecYear'); out.ui.baseSelect = html('#ecBase');
  // dataset dialog for three datasets
  out.ui.dialogs = {};
  for (const k of ['qcew_jobs', 'median_gross_rent', 'tourism_places']) { api.info(k); await wait(80); out.ui.dialogs[k] = html('#ecDlgBody'); document.querySelector('#ecDlg').close(); }
  out.missed = (window.I18N && I18N.missed) ? [...I18N.missed] : null;
  const saved = await post(`${TAG}_economy_${LANG}`, out);
  return { saved, configs: Object.keys(out.configs).length, keys: Object.keys(out.perKey).length, missed: out.missed };
})()
