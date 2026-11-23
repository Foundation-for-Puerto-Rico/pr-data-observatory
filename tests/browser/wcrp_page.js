// The WCRP page (site/wcrp.html; docs/wcrp.md, "What it is") in a real browser, in each language and width: the Social Capital map first and ready, the vulnerability
// map not loaded until its section comes near, its legend following the area and the version, a version chosen before the map's script arrived kept, the change view
// from the comparison section's button and from an old #v=change link, the shared municipio, the pop-up inside a phone's map, no horizontal scroll, no missing Spanish,
// a clean console. Then every closed <details> opened from a link to it, and the page with one Social Capital file blocked: the vulnerability map must still load
// on approach (review of PR #69).
//   chrome --headless=new --remote-debugging-port=9333 --user-data-dir=<a scratch folder> --no-first-run     (or your own port in CDP_PORT)
//   node tests/browser/serve_gzip.js site 8041
//   node tests/browser/wcrp_page.js [base URL, default http://127.0.0.1:8041] [folder for screenshots] [langs, default es,en] [widths, default 1400,390]
// Exit code: 0 when every check passed, 1 when one failed, 2 on an error.
const fs = require('fs'), path = require('path');
const { openPage } = require('./cdp.js');
const base = process.argv[2] || 'http://127.0.0.1:8041', shots = process.argv[3] || '', langs = (process.argv[4] || 'es,en').split(','), widths = (process.argv[5] || '1400,390').split(',').map(Number);
const sleep = (ms) => new Promise(r => setTimeout(r, ms));
const results = [];
const check = (tag, what, ok, detail) => { results.push({ tag, what, ok: !!ok, detail }); if (!ok) console.error(`FAIL ${tag}: ${what}`, detail === undefined ? '' : JSON.stringify(detail)); };
const consoleErrors = (logs) => logs.filter(l => /error|EXCEPTION/i.test(l.type) && !/favicon/.test(l.text + (l.url || '')));
const WORDS = { es: { econ: 'pobreza', updated: 'Actualizado 2020–2024', original: '2015–2019' }, en: { econ: 'poverty', updated: 'Updated 2020–2024', original: '2015–2019' } };
const ready = "performance.getEntriesByName('ready').length > 0";

async function shot(p, name, selector) {
  if (!shots) return;
  await p.eval(`(() => { const e = document.querySelector(${JSON.stringify(selector)}); e.scrollIntoView({ block: 'start' }); window.scrollBy(0, -110); })()`);
  await sleep(1500);
  const b = await p.eval(`(() => { const r = document.querySelector(${JSON.stringify(selector)}).getBoundingClientRect(); return { y: r.top + scrollY, h: r.height, w: innerWidth }; })()`);
  const res = await p.send('Page.captureScreenshot', { format: 'png', captureBeyondViewport: true, clip: { x: 0, y: Math.max(0, b.y - 8), width: b.w, height: Math.min(b.h + 16, 2400), scale: 1 } });
  fs.mkdirSync(shots, { recursive: true }); fs.writeFileSync(path.join(shots, name + '.png'), Buffer.from(res.data, 'base64'));
}
const pick = (area, ver) => `(async () => { const a = document.querySelector('#wmArea'); a.value = '${area}'; a.dispatchEvent(new Event('change', { bubbles: true }));
  const r = document.querySelector('#wmVer input[value="${ver}"]'); r.checked = true; r.dispatchEvent(new Event('change', { bubbles: true })); await new Promise(x => setTimeout(x, 150));
  return { area: document.querySelector('#wmAreaLine').textContent, ver: document.querySelector('#wmVerLine').textContent, hash: location.hash }; })()`;

async function page(lang, width) {
  const tag = `${lang} ${width}`, W_ = WORDS[lang];
  const p = await openPage(`${base}/wcrp.html?lang=${lang}`, { width, height: width < 500 ? 844 : 900, mobile: width < 500, noCache: true });
  try {
    check(tag, 'ready (the Social Capital map drawn)', await p.waitFor(`${ready} && !!document.querySelector('#scLegend b')`, 60000));
    check(tag, 'the vulnerability map has not loaded', await p.eval("typeof Vuln === 'undefined' && !performance.getEntriesByType('resource').some(e => /barrios\\.geojson|wcrp_vuln\\.js/.test(e.name))"));
    check(tag, 'Social Capital first', await p.eval("[...document.querySelectorAll('main > section, main > details')].map(e => e.id).join()") === 'about,social,vulnerability,method,compare,sources');
    check(tag, 'every explanation closed', await p.eval("![...document.querySelectorAll('details')].some(d => d.open)"));
    check(tag, 'the version selector names the years before the map loads', (await p.eval("document.querySelector('#wmVerRebuild').textContent")) === W_.updated);
    check(tag, 'no horizontal scroll at the top', !(await p.eval('document.documentElement.scrollWidth > innerWidth')));
    await shot(p, `top_${lang}_${width}`, 'main');
    await shot(p, `social_${lang}_${width}`, '#social');
    // a version chosen before the map's script arrives is kept
    await p.eval(`(() => { const r = document.querySelector('#wmVer input[value="rebuild"]'); r.checked = true; r.dispatchEvent(new Event('change', { bubbles: true })); })()`);
    check(tag, 'choosing a version loads the map', await p.waitFor('W.vuln === true', 60000));
    const kept = await p.eval("({ ver: W.ver, checked: document.querySelector('#wmVer input:checked') && document.querySelector('#wmVer input:checked').value, line: document.querySelector('#wmVerLine').textContent })");
    check(tag, 'the early choice is kept', kept.ver === 'rebuild' && kept.checked === 'rebuild' && kept.line.startsWith(W_.updated), kept);
    await p.eval("document.querySelector('#vulnerability').scrollIntoView()");
    await sleep(800);
    check(tag, 'the legend: five levels and no value', (await p.eval("document.querySelectorAll('#wmLevels li').length")) === 6);
    const econ = await p.eval(pick('econ', 'rebuild')), envir = await p.eval(pick('envir', 'orig')), overall = await p.eval(pick('overall', 'orig'));
    check(tag, 'the area line follows the area', econ.area.includes(W_.econ) && envir.area !== econ.area && overall.area !== envir.area, { econ, envir, overall });
    check(tag, 'the version line follows the version', econ.ver.startsWith(W_.updated) && envir.ver.includes(W_.original) && econ.hash === '#a=econ&v=rebuild', { econ: econ.ver, envir: envir.ver });
    await shot(p, `vulnerability_${lang}_${width}`, '#vulnerability .wm-card');
    const ch = await p.eval(`(async () => { document.querySelector('#cmpShow').click(); await new Promise(r => setTimeout(r, 400));
      const o = { ver: W.ver, bar: !document.querySelector('#wmChange').hidden, checked: document.querySelectorAll('#wmVer input:checked').length, hash: location.hash, focus: document.activeElement.id };
      document.querySelector('#wmBack').click(); await new Promise(r => setTimeout(r, 200)); o.after = W.ver; o.barAfter = !document.querySelector('#wmChange').hidden; return o; })()`);
    check(tag, 'the comparison button opens the change view, and the bar goes back', ch.ver === 'change' && ch.bar && ch.checked === 0 && ch.hash === '#v=change' && ch.focus === 'wmChange' && ch.after === 'orig' && !ch.barAfter, ch);
    const mu = await p.eval(`(async () => { const s = document.querySelector('#scMuni'); s.value = 'Adjuntas'; s.dispatchEvent(new Event('change', { bubbles: true })); await new Promise(r => setTimeout(r, 1000));
      const o = { wm: document.querySelector('#wmMuni').value, hash: location.hash }; const w = document.querySelector('#wmMuni'); w.value = ''; w.dispatchEvent(new Event('change', { bubbles: true })); await new Promise(r => setTimeout(r, 300)); o.back = document.querySelector('#scMuni').value; return o; })()`);
    check(tag, 'one municipio for both maps', mu.wm === 'Adjuntas' && mu.hash === '#m=Adjuntas' && mu.back === '', mu);
    const pop = await p.eval(`(async () => { document.querySelector('#vulnerability .wm-card').scrollIntoView(); await new Promise(r => setTimeout(r, 400)); const m = document.querySelector('#wmMap').getBoundingClientRect();
      let best = null, d = 1e9; for (const el of document.querySelectorAll('#wmMap path.leaflet-interactive')) { const b = el.getBoundingClientRect(); if (b.width < 6) continue; const dd = Math.hypot(b.left + b.width / 2 - m.left - m.width / 2, b.top + b.height / 2 - m.top - m.height / 2); if (dd < d) { d = dd; best = el; } }
      const b = best.getBoundingClientRect(); best.dispatchEvent(new MouseEvent('click', { bubbles: true, clientX: b.left + b.width / 2, clientY: b.top + b.height / 2 })); await new Promise(r => setTimeout(r, 2500));
      const pw = document.querySelector('#wmMap .leaflet-popup-content-wrapper'); if (!pw) return null; const q = pw.getBoundingClientRect(); return { inside: q.left >= m.left - 1 && q.right <= m.right + 1, w: Math.round(q.width), map: Math.round(m.width) }; })()`);
    check(tag, 'the pop-up stays inside the map', pop && pop.inside, pop);
    await p.eval("document.querySelectorAll('details').forEach(d => d.open = false); document.querySelector('#care').open = true");
    await shot(p, `details_care_${lang}_${width}`, '#care');
    check(tag, 'no horizontal scroll', !(await p.eval('document.documentElement.scrollWidth > innerWidth')));
    check(tag, 'no missing Spanish', (await p.eval('I18N.missed ? I18N.missed.size || [...I18N.missed].length : 0')) === 0);
  } finally {
    check(tag, 'a clean console', consoleErrors(p.logs).length === 0, consoleErrors(p.logs));
    await p.close();
  }
}

async function anchors(lang) {
  for (const id of ['socialAbout', 'socialNotes', 'ceAbout', 'care', 'method', 'compare', 'sources']) {
    const p = await openPage(`${base}/wcrp.html?lang=${lang}#${id}`, { width: 1400, height: 900, noCache: true });
    await p.waitFor(ready, 60000); await sleep(800);
    const r = await p.eval(`(() => { const e = document.getElementById('${id}'), b = e.getBoundingClientRect(); return { open: e.closest('details').open, inView: b.top >= 0 && b.top < innerHeight - 40 }; })()`);
    check(`${lang} #${id}`, 'a link opens it, in view', r.open && r.inView, r);
    await p.close();
  }
  const p = await openPage(`${base}/wcrp.html?lang=${lang}#a=econ&v=change`, { width: 1400, height: 900, noCache: true });
  await p.waitFor('W.vuln === true', 60000); await sleep(1200);
  const r = await p.eval("({ ver: W.ver, area: W.area, bar: !document.querySelector('#wmChange').hidden, top: document.querySelector('#vulnerability').getBoundingClientRect().top })");
  check(`${lang} #v=change`, 'an old link opens the change view, with the way back, in view', r.ver === 'change' && r.area === 'econ' && r.bar && r.top >= 0 && r.top < 400, r);
  check(`${lang} #v=change`, 'a clean console', consoleErrors(p.logs).length === 0, consoleErrors(p.logs));
  await p.close();
}

async function blocked() {   // one Social Capital file does not load: the vulnerability map still loads on approach
  const p = await openPage(`${base}/wcrp.html?lang=es`, { width: 1400, height: 900, noCache: true, block: ['*care_series.json*'] });
  const tag = 'care_series.json blocked';
  check(tag, 'the page gets ready', await p.waitFor(ready, 60000));
  check(tag, 'the Social Capital map still draws its points', await p.waitFor("!!document.querySelector('#scLegend b')", 10000));
  check(tag, 'it says the data could not be loaded', /No se pudieron cargar/.test(await p.eval("document.querySelector('#scStatus').textContent")));
  await p.eval("document.querySelector('#vulnerability').scrollIntoView()");
  check(tag, 'the vulnerability map loads on approach', await p.waitFor('W.vuln === true', 60000));
  await p.close();
}

(async () => {
  for (const l of langs) for (const w of widths) await page(l, w);
  for (const l of langs) await anchors(l);
  await blocked();
  const failed = results.filter(r => !r.ok);
  console.log(JSON.stringify({ checks: results.length, failed: failed.length, failures: failed }, null, 1));
  process.exitCode = failed.length ? 1 : 0;
})().catch(e => { console.error(e); process.exit(2); });
