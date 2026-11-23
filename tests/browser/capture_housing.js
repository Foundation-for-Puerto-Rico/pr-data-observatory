/* Capture script for the Housing page (plan item 6 regression harness; see capture_economy.js and README.md). Run it on housing.html:

     eval(await (await fetch('http://127.0.0.1:8099/s/capture_housing.js')).text())                                                       */
window.__capture = { status: 'running' };
(async () => {
  const TAG = location.port === '8022' ? 'old' : 'new', LANG = new URLSearchParams(location.search).get('lang') || 'es';
  const wait = (ms) => new Promise(r => setTimeout(r, ms));
  const post = (name, obj) => fetch('http://127.0.0.1:8099/save?name=' + name, { method: 'POST', body: JSON.stringify(obj) }).then(r => r.json());
  const html = (sel) => { const e = document.querySelector(sel); return e ? e.innerHTML : null; };
  const hash = (s) => { let h = 2166136261; for (let i = 0; i < s.length; i++) { h ^= s.charCodeAt(i); h = Math.imul(h, 16777619); } return (h >>> 0).toString(16); };
  for (let i = 0; i < 100 && !(window.S === undefined ? typeof S !== 'undefined' && S.series && S.vizzes && document.querySelectorAll('.viz[data-var]').length : true); i++) await wait(200);
  await wait(600);
  const vizzes = [...document.querySelectorAll('.viz[data-var]')];
  vizzes.forEach(el => { el._vis = true; if (!el.dataset.built) buildViz(el); });
  await wait(800);
  const out = { tag: TAG, lang: LANG, env: { width: innerWidth, mobile: typeof isMobile === 'function' ? isMobile() : null }, keys: Object.keys(S.V), years: {}, profiles: {}, dialogs: {}, catalog: html('#catalogList') };
  const snap = () => {
    const o = { note: (document.querySelector('#yearNote') || {}).textContent, vizzes: {}, blocks: {}, kpis: html('#latestKpis'), profile: html('#profileCard') };
    for (const el of vizzes) {
      const st = el._viz, f = {};
      st.layer.eachLayer(l => { f[l.feature.properties.municipality] = [l.options.fillColor, l.options.fillOpacity]; });
      const ds = st.chart.data.datasets[0];
      o.vizzes[el.dataset.var] = { title: (el.querySelector('.vt') || {}).textContent, chip: html(`.viz[data-var="${el.dataset.var}"] .chip`), stats: (el.querySelector('.stats') || {}).innerHTML, readout: (el.querySelector('.readout') || {}).innerHTML, ramp: (el.querySelector('.ramp-row') || {}).innerHTML, fills: f, rows: st.rows.map(r => [r.n, r.v]), bars: [st.chart.data.labels, ds.data, ds.backgroundColor], ariaMap: (el.querySelector('.mini-map') || {}).getAttribute('aria-label') };
    }
    document.querySelectorAll('.block, .hero, .card').forEach((b, i) => { const id = b.id || `${b.className}#${i}`; o.blocks[id] = hash(b.innerText || ''); });
    return o;
  };
  for (const [y, base] of [[null, 2012], [2012, 2012], [2016, 2012], [2020, 2012], [2023, 2012], [2022, 2016], [null, 2017]]) {
    setBase(base); setYear(y); await wait(900);
    out.years[`${y}|${base}`] = snap();
  }
  setBase(2012); setYear(null); await wait(400);
  for (const name of ['San Juan', 'Culebra', 'Maricao']) { selectMuni(name); await wait(150); out.profiles[name] = html('#profileCard'); }
  for (const k of ['median_gross_rent', 'population', 'renter_cost_burden_pct', 'urban_pct', 'gross_rent_change_pct', 'max_affordable_loan']) {
    if (!S.V[k]) continue;
    openDataset(k); await wait(250); out.dialogs[k] = { title: document.querySelector('#dlgTitle').textContent, body: html('#dlgBody').replace(/<canvas[^>]*>/g, '<canvas>') }; document.querySelector('#dataDlg').close();
  }
  out.missed = (window.I18N && I18N.missed) ? [...I18N.missed] : null;
  const saved = await post(`${TAG}_housing_${LANG}`, out);
  return { saved, vizzes: vizzes.length, years: Object.keys(out.years).length, missed: out.missed };
})().then(r => { window.__capture = { status: 'done', result: r }; }).catch(e => { window.__capture = { status: 'error', error: String(e && e.stack || e) }; });
'started; poll window.__capture'
