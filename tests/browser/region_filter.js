// The region filter of the Layers tab's Reference group (HANDOFF decision 113; docs/regions.md, "The region filter"), in a real browser.
//  1. 2D in English and Spanish, opened from the regional profile's link (#rg=ersv, no c=): the Region tab opens, the menu shows the Eastern Region, the note
//     counts 15 municipios, the region pane holds 63 veiled and 15 outlined municipios and takes no click, the map is framed on the region, rg= is in the
//     address and in the 3D link. Then a tourism region, then "All of Puerto Rico" (outline and veil gone, rg= out of the address).
//  2. 2D opened from an address the map wrote (c= and rg=): the camera is kept, the filter is on, the Region tab is not opened.
//  3. 3D in English and Spanish (#rg=ersv): the menu, the veil and outline layers, rg= in the address and in the 2D link; after a base map switch the layers
//     are still there; "All of Puerto Rico" hides them.
// Screenshots go to the folder in the second argument.
//   chrome --headless=new --remote-debugging-port=9333 --user-data-dir=<a scratch folder> --use-angle=d3d11 --enable-gpu     (or your own port in CDP_PORT)
//   node tests/browser/serve_gzip.js site 8041
//   node tests/browser/region_filter.js [base URL, default http://127.0.0.1:8041] [screenshot folder, default none] [cases, default 1,2,3]
// Exit code: 0 when every check passed, 1 when one failed, 2 on an error.
const fs = require('node:fs');
const path = require('node:path');
const { openPage } = require('./cdp.js');
const base = process.argv[2] || 'http://127.0.0.1:8041', shots = process.argv[3] && process.argv[3] !== '-' ? process.argv[3] : null, cases = (process.argv[4] || '1,2,3').split(',');
const sleep = (ms) => new Promise(r => setTimeout(r, ms));
let fails = 0; const check = (ok, what) => { console.log(`  ${ok ? 'ok  ' : 'FAIL'} ${what}`); if (!ok) fails++; return ok; };
const errors = (p) => p.logs.filter(l => /error|EXCEPTION/i.test(l.type) && !/favicon/.test(l.text + (l.url || '')));
async function shot(p, name) {
  if (!shots) return;
  const { data } = await p.send('Page.captureScreenshot', { format: 'jpeg', quality: 70 });
  fs.mkdirSync(shots, { recursive: true }); fs.writeFileSync(path.join(shots, name + '.jpg'), Buffer.from(data, 'base64'));
}
const LABEL = { en: 'Region', es: 'Región' };
const pick = (id) => `(() => { const s = document.getElementById('regionFilter'); s.value = ${JSON.stringify(id)}; s.dispatchEvent(new Event('change')); return s.value; })()`;
const state2d = `(() => { const s = document.getElementById('regionFilter'), pane = map.getPane('regionfilter'), c = map.getCenter();
  return { v: s.value, disabled: s.disabled, label: document.querySelector('label[for=regionFilter]').textContent, note: document.getElementById('regionFilterNote').textContent,
    paths: pane ? pane.querySelectorAll('path').length : -1, filled: pane ? [...pane.querySelectorAll('path')].filter(e => e.getAttribute('fill') !== 'none').length : -1,
    pe: pane ? getComputedStyle(pane).pointerEvents : '', hash: location.hash, l3: (document.querySelector('.views a[href^="3d.html"]') || {}).href || '',
    tab: document.getElementById('s-region').getAttribute('aria-selected') === 'true' ? 'region' : 'other',
    lat: c.lat, lng: c.lng, z: map.getZoom() }; })()`;

async function twoD() {
  for (const l of ['en', 'es']) {
    console.log(`\n1. 2D, ${l}, from the regional profile's link`);
    const p = await openPage(`${base}/index.html?lang=${l}#rg=ersv`, { width: 1400, height: 900 });
    try {
      check(await p.waitFor(`!document.getElementById('regionFilter').disabled && document.getElementById('regionFilter').value === 'ersv'`, 45000), 'the menu is ready on the Eastern Region');
      await sleep(1200);
      let s = await p.eval(state2d);
      check(s.label === LABEL[l], `label in ${l} (${s.label})`);
      check(/15/.test(s.note) && /profile|perfil/i.test(s.note), `the note counts 15 municipios (${s.note.slice(0, 70)}…)`);
      check(s.paths === 78 && s.filled === 63, `63 veiled and 15 outlined municipios (${s.filled} / ${s.paths})`);
      check(s.pe === 'none', 'the region pane takes no click');
      check(s.lng > -65.95 && s.lng < -65.4 && s.lat > 18.05 && s.lat < 18.45 && s.z >= 9, `framed on the east (${s.lat.toFixed(3)}, ${s.lng.toFixed(3)}, z ${s.z})`);
      check(/[#&]rg=ersv(&|$)/.test(s.hash) && /[#&]c=/.test(s.hash), `rg= and c= in the address (${s.hash})`);
      check(/[#&]rg=ersv(&|$)/.test(s.l3), 'rg= in the 3D link');
      check(s.tab === 'region', `the Region tab opened (${s.tab})`);
      await shot(p, `2d_ersv_${l}`);
      await p.eval(pick('reg-caribe')); await sleep(1500);
      s = await p.eval(state2d);
      check(/[#&]rg=reg-caribe(&|$)/.test(s.hash) && s.filled === 78 - 11, `a tourism region: rg=reg-caribe, ${s.filled} veiled`);
      check(s.lat < 18.2, `framed on the south (${s.lat.toFixed(3)})`);
      await shot(p, `2d_caribe_${l}`);
      await p.eval(pick('')); await sleep(800);
      s = await p.eval(state2d);
      check(s.paths === 0 && !/rg=/.test(s.hash), `All of Puerto Rico: nothing drawn, rg= out (${s.paths}, ${s.hash})`);
      check(errors(p).length === 0, `clean console${errors(p).length ? ': ' + errors(p).map(e => e.text).join(' | ').slice(0, 300) : ''}`);
    } finally { await p.close(); }
  }
}

async function written() {
  console.log('\n2. 2D from an address the map wrote: the camera is kept, the Region tab is not opened');
  const p = await openPage(`${base}/index.html?lang=en#c=18.4000,-66.1000,11&l=muni&rg=reg-capital`, { width: 1400, height: 900 });
  try {
    check(await p.waitFor(`!document.getElementById('regionFilter').disabled && document.getElementById('regionFilter').value === 'reg-capital'`, 45000), 'the menu is on Porta Capital');
    await sleep(1200);
    const s = await p.eval(state2d);
    check(Math.abs(s.lat - 18.4) < 0.01 && Math.abs(s.lng + 66.1) < 0.01 && s.z === 11, `camera kept (${s.lat.toFixed(4)}, ${s.lng.toFixed(4)}, z ${s.z})`);
    check(s.tab !== 'region', `the Region tab not opened (${s.tab})`);
    check(s.filled === 78 - 10, `${s.filled} veiled`);
    const bad = await openPage(`${base}/index.html?lang=en#c=18.4000,-66.1000,11&rg=nope`, { width: 1200, height: 800 });
    try {
      check(await bad.waitFor(`!document.getElementById('regionFilter').disabled`, 45000), 'an unknown region: the menu is ready');
      await sleep(800);
      const b = await bad.eval(state2d);
      check(b.v === '' && b.paths === 0 && !/rg=/.test(b.hash), `an unknown region is dropped (${b.hash})`);
    } finally { await bad.close(); }
    check(errors(p).length === 0, 'clean console');
  } finally { await p.close(); }
  for (const page of ['index.html', '3d.html']) {
    console.log(`
2b. ${page} with no rg=: the filter loads on use, when the Reference group opens`);
    const q = await openPage(`${base}/${page}?lang=en#c=18.2000,-66.5000,9`, { width: 1400, height: 900 });
    try {
      check(await q.waitFor(`document.getElementById('loader').classList.contains('hide')`, 60000), 'the page is ready');
      await sleep(2500);
      check(await q.eval(`!(window.Core && window.Core.regionfilter) && document.getElementById('regionFilter').disabled`), 'not loaded yet, the menu disabled');
      await q.eval(`[...document.querySelectorAll('#tab-layers .fold-toggle')].find(b => /Reference/.test(b.textContent)).click()`);
      check(await q.waitFor(`!document.getElementById('regionFilter').disabled && document.getElementById('regionFilter').options.length === 9`, 20000), 'loaded when Reference opens: 1 + 8 options');
      check(!/rg=/.test(await q.eval('location.hash')), 'no rg= until a region is picked');
    } finally { await q.close(); }
  }
}

const state3d = `(() => { const s = document.getElementById('regionFilter'), v = (id) => map.getLayer(id) ? (map.getLayoutProperty(id, 'visibility') || 'visible') : 'none', c = map.getCenter();
  return { v: s.value, label: document.querySelector('label[for=regionFilter]').textContent, note: document.getElementById('regionFilterNote').textContent, veil: v('region-veil'), line: v('region-line'),
    n: map.getSource('region-filter') ? map.querySourceFeatures('region-filter').length : -1, hash: location.hash, l2: (document.querySelector('.views a[href^="index.html"]') || {}).href || '',
    lat: c.lat, lng: c.lng }; })()`;
async function threeD() {
  for (const l of ['en', 'es']) {
    console.log(`\n3. 3D, ${l}`);
    const p = await openPage(`${base}/3d.html?lang=${l}#rg=ersv`, { width: 1400, height: 900 });
    try {
      check(await p.waitFor(`!document.getElementById('regionFilter').disabled && document.getElementById('regionFilter').value === 'ersv'`, 60000), 'the menu is ready on the Eastern Region');
      await sleep(4000);
      let s = await p.eval(state3d);
      check(s.label === LABEL[l], `label in ${l} (${s.label})`);
      check(/15/.test(s.note), 'the note counts 15 municipios');
      check(s.veil === 'visible' && s.line === 'visible', `veil and outline drawn (${s.veil}, ${s.line})`);
      check(s.lng > -66 && s.lng < -65.3, `camera on the east (${s.lat.toFixed(3)}, ${s.lng.toFixed(3)})`);
      check(/[#&]rg=ersv(&|$)/.test(s.hash) && /[#&]rg=ersv(&|$)/.test(s.l2), `rg= in the address and the 2D link (${s.hash})`);
      await shot(p, `3d_ersv_${l}`);
      await p.eval(`(() => { const s = document.getElementById('basemap'); s.value = 'dark'; s.dispatchEvent(new Event('change')); })()`);
      check(await p.waitFor(`document.getElementById('basemap').value === 'dark' && !document.getElementById('basemap').disabled && !!map.getLayer('region-veil')`, 30000), 'after a switch to Dark the region layers are still there');
      await sleep(2500); await shot(p, `3d_ersv_dark_${l}`);
      await p.eval(pick('')); await sleep(800);
      s = await p.eval(state3d);
      check(s.veil === 'none' && s.line === 'none' && !/rg=/.test(s.hash), `All of Puerto Rico hides them and takes rg= out (${s.hash})`);
      check(errors(p).length === 0, `clean console${errors(p).length ? ': ' + errors(p).map(e => e.text).join(' | ').slice(0, 300) : ''}`);
    } finally { await p.close(); }
  }
}

(async () => {
  if (cases.includes('1')) await twoD();
  if (cases.includes('2')) await written();
  if (cases.includes('3')) await threeD();
  console.log(`\n${fails ? fails + ' check(s) failed' : 'all checks passed'}`);
  process.exit(fails ? 1 : 0);
})().catch(e => { console.error(e); process.exit(2); });
