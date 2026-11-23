/* Capture script for the municipality columns of the 3D page (plan item 6 regression harness; see capture_economy.js and README.md). Run it on 3d.html with the
   browser tab in front (WebGL does not finish loading in a hidden tab):

     eval(await (await fetch('http://127.0.0.1:8099/s/capture_3d.js')).text())                                                            */
window.__capture = { status: 'running' };
(async () => {
  const TAG = location.port === '8022' ? 'old' : 'new', LANG = new URLSearchParams(location.search).get('lang') || 'es';
  const wait = (ms) => new Promise(r => setTimeout(r, ms));
  const post = (name, obj) => fetch('http://127.0.0.1:8099/save?name=' + name, { method: 'POST', body: JSON.stringify(obj) }).then(r => r.json());
  const html = (sel) => { const e = document.querySelector(sel); return e ? e.innerHTML : null; };
  for (let i = 0; i < 150 && !(typeof map !== 'undefined' && map.getLayer && map.getLayer('muni-cols')); i++) await wait(200);
  if (!(typeof map !== 'undefined' && map.getLayer('muni-cols'))) return { error: 'the 3D map did not finish loading (is the tab in front?)' };
  const out = { tag: TAG, lang: LANG, env: { width: innerWidth, mobile: typeof isMobile === 'function' ? isMobile() : null }, metrics: {}, options: [...document.querySelectorAll('select option')].filter(o => o.parentElement.id && /metric/i.test(o.parentElement.id)).map(o => [o.parentElement.id, o.value, o.textContent]) };
  for (const key of ['', ...Object.keys(METRIC)]) {
    setMetric(key); await wait(80);
    out.metrics[key || '(none)'] = { legend: html('#metricLegend'), color: JSON.stringify(map.getPaintProperty('muni-cols', 'fill-extrusion-color')), height: JSON.stringify(map.getPaintProperty('muni-cols', 'fill-extrusion-height')), visibility: map.getLayoutProperty('muni-cols', 'visibility') };
  }
  setMetric('');
  out.missed = (window.I18N && I18N.missed) ? [...I18N.missed] : null;
  const saved = await post(`${TAG}_3d_${LANG}`, out);
  return { saved, metrics: Object.keys(out.metrics).length, missed: out.missed };
})().then(r => { window.__capture = { status: 'done', result: r }; }).catch(e => { window.__capture = { status: 'error', error: String(e && e.stack || e) }; });
'started; poll window.__capture'
