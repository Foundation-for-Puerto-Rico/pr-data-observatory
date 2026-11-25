// The workspace in a real browser (docs/workspace.md, docs/workspace-feature-parity.md check C): the map's timeline, undo and redo, the panel's tabs, the
// workbench's views and its grip, Ask, the widgets and their filters, saved maps, four widths in Spanish, and twelve other pages.
//  1. The timeline: enabled with the engine's years, named for a screen reader, Previous, Latest (no ey= in the address), 41 rapid moves ending on the last,
//     play and pause, each layer's own period at the last year, a snapshot layer alone, sea level rise named as a scenario.
//  2. Undo and redo of a layer switch; the eight tabs; the ten workbench views; the grip with the keyboard; Ask.
//  3. Widgets: Puerto Rico's own figure, a region filter that says what it counts and labels the figure, Clear filters; a saved map.
//  4. The map at 1280, 1024, 768 and 390 px in Spanish: no sideways scroll, a slider at least 120 px wide, play and Latest in reach.
//  5. Twelve other pages in Spanish: the rail's eight areas, the light/dark switch, no console error, no sideways scroll.
// It is run by hand, like the other scripts of this folder (README.md); it is not part of `node --test`.
//   chrome --headless=new --remote-debugging-port=9333 --user-data-dir=<a scratch folder> --use-angle=swiftshader --enable-unsafe-swiftshader
//   python -m http.server 8151 --bind 127.0.0.1 --directory site
//   node tests/browser/workspace.js [base URL, default http://127.0.0.1:8151/] [screenshot folder, default none]
// Exit code: 0 when every check passed, 1 when one failed, 2 on an error.
const fs = require('node:fs');
const path = require('node:path');
const { openPage } = require('./cdp.js');
const base = (process.argv[2] || 'http://127.0.0.1:8151/').replace(/\/?$/, '/'), shots = process.argv[3] && process.argv[3] !== '-' ? process.argv[3] : null;
const sleep = (ms) => new Promise(r => setTimeout(r, ms));

(async () => {
  const p = await openPage('about:blank', { width: 1440, height: 900 });
  const errs = () => p.logs.filter(l => /^(EXCEPTION|error|log\.error)$/.test(l.type) && !/favicon/.test(l.text + (l.url || ''))).map(l => l.type + ' ' + l.text);
  const page = {
    get errors() { return errs(); },
    wait: sleep,
    eval: (js) => p.eval(js, { timeout: 60000 }),
    until: (js, ms) => p.waitFor(js, ms || 15000),
    goto: async (url) => { await p.send('Page.navigate', { url }); await sleep(800); },
    size: (w, h) => p.send('Emulation.setDeviceMetricsOverride', { width: w, height: h, deviceScaleFactor: 1, mobile: w < 600 }),
    shot: async (file) => { if (!shots) return; const { data } = await p.send('Page.captureScreenshot', { format: 'png' }); fs.mkdirSync(shots, { recursive: true }); fs.writeFileSync(path.join(shots, path.basename(file)), Buffer.from(data, 'base64')); },
  };
  const out = '';
  let R = [];
  try {
    R = await journey(page, out);
  } catch (e) { console.log('ERROR', e); await p.close(); process.exit(2); }
  await p.close();
  console.log(R.map(x => '  ' + x.replace(/^PASS /, 'ok   ')).join('\n'));
  const failed = R.filter(x => x.startsWith('FAIL')).length;
  console.log(`${failed} failed of ${R.length}`);
  process.exit(failed ? 1 : 0);
})();

async function journey(page, out) {
  const R = [], ok = (n, v, d) => { R.push((v ? 'PASS ' : 'FAIL ') + n + (d ? '  ' + d : '')); };
  await page.size(1440, 900);
  await page.goto(base + '404.html'); await page.eval("localStorage.setItem('twin.theme','dark');localStorage.setItem('twin.gloss','off');localStorage.removeItem('twin.maps');localStorage.removeItem('twin.ws.right')");
  await page.goto(base + 'index.html?lang=en#e=median_hh_income.f,jobs.s'); await page.wait(9000);
  const E0 = page.errors.length;
  ok('slider enabled with real years', await page.eval("!document.getElementById('wtRange').disabled && document.getElementById('wtRange').max == Workspace.timeline.years().length - 1"));
  ok('slider has an accessible name and value text', await page.eval("!!document.getElementById('wtRange').getAttribute('aria-label') && /Latest available, \\d{4}/.test(document.getElementById('wtRange').getAttribute('aria-valuetext'))"));
  await page.eval("document.getElementById('wtPrev').click()"); await page.wait(600);
  ok('Previous steps back one year from the latest', await page.eval("ECON.api.state().year === Workspace.timeline.years().slice(-2)[0]"), await page.eval("String(ECON.api.state().year)"));
  await page.eval("document.getElementById('wtLatest').click()"); await page.wait(600);
  ok('Latest returns to the latest (year null, no ey= in the link)', await page.eval("ECON.api.state().year === null && !/ey=/.test(location.hash) && document.getElementById('wtLatest').getAttribute('aria-pressed') === 'true'"));
  ok('rapid scrubbing ends on the last value', await page.eval("new Promise(done => { const r = document.getElementById('wtRange'), ys = Workspace.timeline.years(); for (let i = 0; i < 40; i++) { r.value = i % ys.length; r.dispatchEvent(new Event('input')); } r.value = 3; r.dispatchEvent(new Event('input')); setTimeout(() => done(ECON.api.state().year === ys[3]), 500); })"));
  await page.eval("document.getElementById('wtSpeed').value = '600'; document.getElementById('wtPlay').click()"); await page.wait(2100);
  const mid = await page.eval("ECON.api.state().year"); await page.eval("document.getElementById('wtPlay').click()"); await page.wait(900);
  const stop = await page.eval("ECON.api.state().year"); await page.wait(1300);
  ok('play advances and pause holds', mid > 2013 && stop === (await page.eval("ECON.api.state().year")) && (await page.eval("document.getElementById('wtPlay').getAttribute('aria-pressed') === 'false'")), mid + ' then ' + stop);
  await page.eval("document.getElementById('wtLatest').click()"); await page.wait(500); await page.eval("(() => { const r = document.getElementById('wtRange'); r.value = r.max; r.dispatchEvent(new Event('input')); })()"); await page.wait(700);
  ok('each layer names its own period at 2026', await page.eval("/2020–2024 \\(latest at or before 2026\\)/.test(document.getElementById('wtLayers').innerText)"), await page.eval("document.getElementById('wtLayers').innerText.replace(/\\n/g,' ')"));
  await page.eval("ECON.api.clear(); document.getElementById('lyFlood').click()"); await page.wait(2500);
  ok('with only a snapshot layer the timeline explains itself', await page.eval("/No dataset on the map yet/.test(document.getElementById('wtLayers').innerText)"));
  await page.eval("document.getElementById('lySlr').click()"); await page.wait(1500);
  ok('sea level rise is named as a scenario, not a year', await page.eval("/scenario and not a year/.test(document.getElementById('wtModes').innerText)"));
  ok('Undo is offered after layer changes', await page.eval("!document.getElementById('wsUndo').disabled"));
  await page.eval("document.getElementById('wsUndo').click()"); await page.wait(900);
  ok('Undo takes the last layer change back', await page.eval("!document.getElementById('lySlr').checked && document.getElementById('lyFlood').checked"));
  await page.eval("document.getElementById('wsRedo').click()"); await page.wait(900);
  ok('Redo puts it back', await page.eval("document.getElementById('lySlr').checked"));
  for (const [tab, sel] of [['layers', '#tab-layers.active'], ['catalog', '#tab-catalog.active'], ['muni', '#tab-muni.active'], ['rank', '#tab-rank.active'], ['maptools', '#tab-maptools.active'], ['transit', '#tab-transit.active'], ['economy', '#tab-economy.active'], ['about', '#tab-about.active']]) { await page.eval("showTab('" + tab + "')"); await page.wait(700); ok('tab ' + tab, await page.eval("!!document.querySelector('" + sel + "')")); }
  await page.wait(2500);
  ok('map tools list its tools', await page.eval("document.querySelectorAll('#tab-maptools [data-mt]').length >= 21"));
  await page.eval("ECON.api.show({ stay: true, layers: [{ key: 'median_hh_income', mode: 'fill' }, { key: 'poverty_pct', mode: 'symbol' }] }).then(() => window.__s = 1)"); await page.until('window.__s === 1', 30000);
  for (const v of ['inspect', 'table', 'scatter', 'trend', 'matrix', 'multiples', 'swipe', 'composite', 'scenarios', 'study']) { await page.eval("ECON.api.benchOpen('" + v + "')"); await page.wait(1800); ok('workbench ' + v, await page.eval("!document.getElementById('econBench').hidden && document.getElementById('ebBody').innerText.length > 20")); }
  await page.shot(out + 'bench_study.png');
  const h0 = await page.eval("document.getElementById('econBench').getBoundingClientRect().height");
  await page.eval("(() => { const g = document.getElementById('wsGrip'); g.focus(); g.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowUp', bubbles: true })); g.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowUp', bubbles: true })); })()"); await page.wait(500);
  ok('workbench grows from the grip with the keyboard', (await page.eval("document.getElementById('econBench').getBoundingClientRect().height")) > h0 + 30);
  await page.eval("document.getElementById('ebClose').click(); document.getElementById('chBtn').click()"); await page.wait(4500);
  ok('Ask opens', await page.eval("document.body.classList.contains('chat-open') && !!document.getElementById('chat')"));
  await page.shot(out + 'chat.png');
  await page.eval("document.getElementById('chBtn').click()"); await page.wait(600);
  ok('widgets show a key figure for Puerto Rico', await page.eval("/Puerto Rico/.test((document.querySelector('.ws-sub')||{}).innerText || '')"), await page.eval("(document.querySelector('.ws-big')||{}).innerText"));
  await page.eval("document.querySelector('[data-region]').click()"); await page.wait(500);
  ok('a region filter says what it counts and labels the figure', await page.eval("/of 78 municipios/.test(document.getElementById('wsFilter').innerText) && /Median of the values of \\d+ municipios/.test(document.querySelector('.ws-sub').innerText)"), await page.eval("document.querySelector('.ws-scope').innerText.replace(/\\n/g,' ') + ' | ' + document.querySelector('.ws-sub').innerText"));
  await page.eval("document.getElementById('wsClear').click()"); await page.wait(400);
  ok('Clear filters returns to all 78', await page.eval("/All 78 municipios/.test(document.getElementById('wsFilter').innerText)"));
  await page.eval("document.getElementById('wsSave').click()"); await page.wait(400);
  await page.eval("document.getElementById('wsSaveName').value = 'Test map'; document.getElementById('wsSaveGo').click()"); await page.wait(1200);
  ok('a saved map is listed', await page.eval("!!JSON.parse(localStorage.getItem('twin.maps'))['Test map'] && /Test map/.test(document.getElementById('wsMapsBody').innerText)"));
  const savedHash = await page.eval("JSON.parse(localStorage.getItem('twin.maps'))['Test map'].hash");
  ok('the saved map holds the layers', /median_hh_income/.test(savedHash) && /poverty_pct/.test(savedHash), savedHash.slice(0, 120));
  ok('no console errors on the map', page.errors.length === E0, page.errors.slice(E0).join(' | ').slice(0, 500));
  for (const [w, h] of [[1280, 800], [1024, 768], [768, 1024], [390, 844]]) {
    await page.size(w, h); await page.goto(base + '404.html'); await page.goto(base + 'index.html?lang=es#e=median_hh_income.f'); await page.wait(8000);
    const m = JSON.parse(await page.eval("JSON.stringify({ sx: document.documentElement.scrollWidth - innerWidth, map: Math.round(document.getElementById('map').getBoundingClientRect().width) + 'x' + Math.round(document.getElementById('map').getBoundingClientRect().height), tl: Math.round(document.getElementById('wtRange').getBoundingClientRect().width), play: !!document.getElementById('wtPlay').offsetParent, latest: !!document.getElementById('wtLatest').offsetParent })"));
    ok('width ' + w + ': no sideways scroll, map and timeline usable', m.sx <= 0 && m.tl >= 120 && m.play && m.latest && parseInt(m.map) >= 300, JSON.stringify(m));
    await page.shot(out + 'map_es_' + w + '.png');
  }
  await page.size(1440, 900);
  for (const p of ['3d.html', 'housing.html', 'profile.html?area=72127', 'dictionary.html', 'knowledge.html', 'learn.html', 'public-spending.html', 'wcrp.html', 'explore.html', 'data.html', 'workflows.html', 'data-management.html']) {
    const e0 = page.errors.length; await page.goto(base + p + (p.includes('?') ? '&' : '?') + 'lang=es'); await page.wait(6500); await page.until("!!document.documentElement && document.readyState === 'complete'", 20000);
    const info = JSON.parse(await page.eval("JSON.stringify({ missed: (window.I18N && I18N.missed || []).slice(0, 6), rail: document.querySelectorAll('.topbar .views a').length, theme: !!document.getElementById('themeBtn'), sx: document.documentElement.scrollWidth - innerWidth })"));
    ok('page ' + p, page.errors.length === e0 && info.rail === 8 && info.theme && info.sx <= 0, JSON.stringify(info) + ' ' + page.errors.slice(e0).join(' | ').slice(0, 300));
  }
  return R;
}
