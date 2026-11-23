/* Capture script for the shading menu and the ranking table of the 2D map (plan item 6 regression harness; see capture_economy.js and README.md):

     eval(await (await fetch('http://127.0.0.1:8099/s/capture_choro.js')).text())                                                         */
(async () => {
  const TAG = location.port === '8022' ? 'old' : 'new', LANG = new URLSearchParams(location.search).get('lang') || 'es';
  const wait = (ms) => new Promise(r => setTimeout(r, ms));
  const post = (name, obj) => fetch('http://127.0.0.1:8099/save?name=' + name, { method: 'POST', body: JSON.stringify(obj) }).then(r => r.json());
  const html = (sel) => { const e = document.querySelector(sel); return e ? e.innerHTML : null; };
  const sel = document.querySelector('#choro');
  const out = { tag: TAG, lang: LANG, env: { width: innerWidth, mobile: typeof isMobile === 'function' ? isMobile() : null }, options: [...sel.options].map(o => [o.value, o.textContent]), shades: {}, ranks: {} };
  const fills = () => { const o = {}; muniLayer.eachLayer(l => { o[l.feature.properties.municipality] = [l.options.fillColor, l.options.fillOpacity]; }); return o; };
  if (typeof ensurePlaces === 'function') await ensurePlaces().catch(() => {});   // the choropleths of the places shown count the listings: have them before the first option is read
  for (const [key] of out.options) {
    sel.value = key; sel.dispatchEvent(new Event('change')); await wait(330);
    out.shades[key || '(none)'] = { legend: html('#choroLegend'), mapLegend: html('#mapLegend'), mapLegendShown: document.querySelector('#mapLegend').classList.contains('show'), fills: fills(), hash: location.hash.replace(/c=[^&]*&?/, '') };
  }
  sel.value = ''; sel.dispatchEvent(new Event('change'));
  const rb = document.querySelector('#rankBy');
  out.rankOptions = [...rb.options].map(o => [o.value, o.textContent]);
  for (const [key] of out.rankOptions) { rb.value = key; rb.dispatchEvent(new Event('change')); await wait(60); out.ranks[key] = html('#rankBody'); }
  out.missed = (window.I18N && I18N.missed) ? [...I18N.missed] : null;
  const saved = await post(`${TAG}_choro_${LANG}`, out);
  return { saved, shades: Object.keys(out.shades).length, ranks: Object.keys(out.ranks).length, missed: out.missed };
})()
