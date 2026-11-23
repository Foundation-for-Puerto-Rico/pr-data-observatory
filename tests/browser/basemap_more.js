// The base maps added on 2026-11-13 (HANDOFF decision 102; docs/basemap.md, "More base maps"), in a real browser, each opened fresh from its address.
//  1. 2D, every new style in English and Spanish at 1400 × 900: it loads (data-basemap "on"), the switcher shows it with its description and its group headings in
//     the page's language, the credit box names its sources (OpenStreetMap's three, or the USGS line, plus "Orthoimagery" for the aerial imagery), the map
//     inspector is enabled on an OpenStreetMap style and disabled with its note on a USGS one, bm= stays in the address, no tile answers 404, no console error.
//  2. 2D at 390 px, the aerial imagery in Spanish: the credits fold behind the "i" button once the USGS credit is in the box.
//  3. 3D in English and Spanish: opened on the aerial imagery, then switched to Liberty, Topographic, Dark and Shaded relief. Each time: the credits of that style
//     once (the USGS line or OpenStreetMap's, never both), the inspector as above, the 3D buildings only on an OpenStreetMap style, the fonts kept for the view's
//     own labels, the base map still on 8 s later (no tile rule fired), no 404 from the USGS, no console error.
// Screenshots of each go to the folder in the second argument.
//   chrome --headless=new --remote-debugging-port=9333 --user-data-dir=<a scratch folder> --use-angle=d3d11 --enable-gpu     (or your own port in CDP_PORT)
//   node tests/browser/serve_gzip.js site 8041
//   node tests/browser/basemap_more.js [base URL, default http://127.0.0.1:8041] [screenshot folder, default none] [cases, default 1,2,3]
// Exit code: 0 when every check passed, 1 when one failed, 2 on an error.
const fs = require('node:fs');
const path = require('node:path');
const { openPage } = require('./cdp.js');
const B = require(path.join(__dirname, '..', '..', 'site', 'js', 'core', 'basemap.js'));
const base = process.argv[2] || 'http://127.0.0.1:8041', shots = process.argv[3] && process.argv[3] !== '-' ? process.argv[3] : null, cases = (process.argv[4] || '1,2,3').split(',');
const sleep = (ms) => new Promise(r => setTimeout(r, ms));
let fails = 0; const check = (ok, what) => { console.log(`  ${ok ? 'ok  ' : 'FAIL'} ${what}`); if (!ok) fails++; return ok; };
const USGS = ['imagery', 'topo', 'relief'], NEW = ['bright', 'dark', 'fiord', ...USGS];
const errors = (p) => p.logs.filter(l => /error|EXCEPTION/i.test(l.type) && !/favicon/.test(l.text + (l.url || '')));
const usgs404 = (p) => p.bad.filter(b => /nationalmap\.gov/.test(b.url));
async function shot(p, name) {
  if (!shots) return;
  const { data } = await p.send('Page.captureScreenshot', { format: 'jpeg', quality: 70 });
  fs.mkdirSync(shots, { recursive: true }); fs.writeFileSync(path.join(shots, name + '.jpg'), Buffer.from(data, 'base64'));
}
const count = (s, re) => (s.match(re) || []).length;

async function twoD() {
  for (const l of ['en', 'es']) for (const n of NEW) {
    console.log(`\n1. 2D, ${n}, ${l}`);
    const p = await openPage(`${base}/index.html?lang=${l}#c=18.4300,-66.0700,12&l=muni&bm=${n}`, { width: 1400, height: 900 });
    try {
      check(await p.waitFor(`document.getElementById('map').dataset.basemap === 'on'`, 45000), `loads (${await p.eval(`document.getElementById('map').dataset.basemap`)})`);
      const s = await p.eval(`(() => { const sel = document.getElementById('basemap'), b = document.getElementById('osmInspect');
        return { v: sel.value, desc: document.getElementById('basemapDesc').textContent, groups: [...sel.querySelectorAll('optgroup')].map(g => g.label),
          credit: document.querySelector('.leaflet-control-attribution').innerHTML, insp: b.disabled, note: document.getElementById('osmInspectNote').textContent, hash: location.hash }; })()`);
      check(s.v === n, `the switcher shows it (${s.v})`);
      check(s.desc === B.OPTIONS[n].desc[l], `its description in ${l}`);
      check(JSON.stringify(s.groups) === JSON.stringify(Object.values(B.GROUPS).map(g => g[l])), `group headings in ${l} (${s.groups.join(' / ')})`);
      const isU = USGS.includes(n);
      check(count(s.credit, /apps\.nationalmap\.gov/g) === (isU ? 1 : 0) && count(s.credit, /openstreetmap\.org\/copyright/g) === (isU ? 0 : 1), `credits of its source once (${isU ? 'USGS' : 'OpenStreetMap'})`);
      if (n === 'imagery') check(/Orthoimagery: USDA, USGS|Ortoimágenes: USDA, USGS/.test(s.credit), 'the orthoimagery credit');
      check(s.insp === isU, `inspector ${isU ? 'disabled' : 'enabled'}${isU ? ` with its note ("${s.note.slice(0, 50)}…")` : ''}`);
      check(new RegExp(`[#&]bm=${n}(&|$)`).test(s.hash), 'bm= kept in the address');
      await sleep(3000); await shot(p, `2d_${n}_${l}`);
      check(usgs404(p).length === 0, `no 404 from the USGS (${usgs404(p).map(b => b.url.split('MapServer/')[1]).join(', ')})`);
      check(await p.eval(`document.getElementById('map').dataset.basemap`) === 'on', 'still on 3 s later');
      check(errors(p).length === 0, `clean console${errors(p).length ? ': ' + errors(p).map(e => e.text).join(' | ').slice(0, 300) : ''}`);
    } finally { await p.close(); }
  }
}

async function phone() {
  console.log('\n2. 2D at 390 px, imagery, es: the credits fold once the USGS credit is in the box');
  const p = await openPage(`${base}/index.html?lang=es#c=18.4300,-66.0700,12&l=muni&bm=imagery`, { width: 390, height: 844, mobile: true });
  try {
    check(await p.waitFor(`document.getElementById('map').dataset.basemap === 'on'`, 45000), 'loads');
    check(await p.waitFor(`!!document.querySelector('.leaflet-control-attribution.cr-shut')`, 12000), 'folded 5 s after the USGS credit showed (before the 20 s wait)');
    check(await p.eval(`document.querySelector('.cr-btn').getAttribute('aria-expanded')`) === 'false', 'the "i" button says it is closed');
    await shot(p, '2d_imagery_es_390');
  } finally { await p.close(); }
}

const READY3 = `document.getElementById('loader').classList.contains('hide') && !document.getElementById('basemap').disabled`;
const STATE3 = `(() => { const at = document.querySelector('.maplibregl-ctrl-attrib-inner'), credit = at ? at.innerHTML : '';
  return { name: BM.name, off: BM.off, busy: BM.busy, credit, insp: document.getElementById('osmInspect').disabled, glyphs: !!map.getStyle().glyphs,
    buildings: !!map.getLayer('buildings-3d'), gap: !!map.getLayer('buildings-3d-gap'), labels: map.getStyle().layers.filter(l => l.type === 'symbol' && !(BM.base && BM.base.layers.has(l.id))).length }; })()`;
async function threeD() {
  for (const l of ['en', 'es']) {
    console.log(`\n3. 3D, ${l}: opened on the aerial imagery, then switched`);
    const p = await openPage(`${base}/3d.html?lang=${l}#bm=imagery`, { width: 1400, height: 900 });
    try {
      check(await p.waitFor(READY3, 90000), 'ready');
      for (const n of ['imagery', 'liberty', 'topo', 'dark', 'relief']) {
        if (n !== 'imagery') {
          await p.eval(`(() => { const s = document.getElementById('basemap'); s.value = '${n}'; s.dispatchEvent(new Event('change')); return 1; })()`);
          check(await p.waitFor(`BM.name === '${n}' && !BM.busy`, 60000), `switched to ${n}`);
        }
        await sleep(8000);
        const s = await p.eval(STATE3), isU = USGS.includes(n);
        check(s.name === n && !s.off, `${n}: on, 8 s later (off: ${s.off})`);
        check(count(s.credit, /apps\.nationalmap\.gov/g) === (isU ? 1 : 0) && count(s.credit, /openstreetmap\.org\/copyright/g) === (isU ? 0 : 1), `${n}: credits once, of its source only`);
        check(/Orthoimagery: USDA, USGS|Ortoimágenes: USDA, USGS/.test(s.credit) === (n === 'imagery'), `${n}: the orthoimagery credit only on the imagery`);
        check(s.insp === isU, `${n}: inspector ${isU ? 'disabled' : 'enabled'}`);
        check(s.buildings === !isU && (!isU || !s.gap), `${n}: 3D buildings ${isU ? 'absent, the ones OpenStreetMap lacks too (no OpenStreetMap tiles)' : 'drawn'} (base ${s.buildings}, gap ${s.gap})`);
        check(s.glyphs, `${n}: fonts for the view's own labels`);
        await shot(p, `3d_${n}_${l}`);
      }
      check(usgs404(p).length === 0, `no 404 from the USGS (${usgs404(p).slice(0, 5).map(b => b.url.split('MapServer/')[1]).join(', ')})`);
      check(errors(p).length === 0, `clean console${errors(p).length ? ': ' + errors(p).map(e => e.text).join(' | ').slice(0, 300) : ''}`);
    } finally { await p.eval(`localStorage.removeItem('twin.basemap'), 1`).catch(() => {}); await p.close(); }
  }
}

(async () => {
  if (cases.includes('1')) await twoD();
  if (cases.includes('2')) await phone();
  if (cases.includes('3')) await threeD();
  console.log(`\n${fails ? fails + ' check(s) failed' : 'all checks passed'}`);
  process.exit(fails ? 1 : 0);
})().catch(e => { console.error(e); process.exit(2); });
