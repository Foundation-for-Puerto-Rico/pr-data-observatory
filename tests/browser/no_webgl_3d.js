// The 3D view in a browser without WebGL (the review of PR #86 found series3d.js calling map.on although twin3d.js never made the map, a ReferenceError).
// twin3d.js stops on purpose when WebGL is missing: it shows a message in the loader and throws "WebGL unavailable" to end its script. Every script after it must then
// do nothing: no time series panel (window.Series is null), no transit supply wiring, and no other console error.
//   chrome --headless=new --remote-debugging-port=<port> --user-data-dir=<a scratch folder> --no-first-run --disable-webgl --disable-3d-apis
//   node tests/browser/serve_gzip.js site 8041
//   CDP_PORT=<port> node tests/browser/no_webgl_3d.js [base URL, default http://127.0.0.1:8041] [langs, default es,en]
// Exit code: 0 when every check passed, 1 when one failed, 2 on an error (also when the browser has WebGL: start it with the two flags above).
const { openPage } = require('./cdp.js');
const base = process.argv[2] || 'http://127.0.0.1:8041', langs = (process.argv[3] || 'es,en').split(',');
const sleep = (ms) => new Promise(r => setTimeout(r, ms));
const problems = []; let passed = 0;
const check = (ok, what) => { if (ok) passed++; else problems.push(what); console.log(`  ${ok ? 'ok  ' : 'FAIL'} ${what}`); return ok; };
const STOP = /^Error: WebGL unavailable\b/;   // twin3d.js's own stop, the one expected exception

async function run(lang) {
  console.log(lang);
  const p = await openPage(`${base}/3d.html?lang=${lang}`, { width: 1280, height: 900 });
  try {
    const gl = await p.eval("(() => { const c = document.createElement('canvas'); return !!(c.getContext('webgl2') || c.getContext('webgl')); })()");
    if (gl) throw new Error('this browser has WebGL: start it with --disable-webgl --disable-3d-apis');
    check(await p.waitFor("document.getElementById('loader').classList.contains('error')", 30000), `${lang}: the loader says the 3D map cannot be drawn`);
    const msg = await p.eval("document.getElementById('loaderText').textContent");
    check(lang === 'es' ? /WebGL no está disponible/.test(msg) && !/This browser/.test(msg) : /WebGL is unavailable/.test(msg), `${lang}: the message names WebGL ("${msg.slice(0, 90)}…")`);
    await sleep(3000);   // the scripts after twin3d.js, and anything they would start late
    const s = await p.eval("({ series: window.Series, panel: !!document.getElementById('series') })");
    check(s.series === null && !s.panel, `${lang}: no time series panel without a map (${JSON.stringify(s)})`);
    for (const type of ['mousePressed', 'mouseReleased']) await p.send('Input.dispatchMouseEvent', { type, x: 640, y: 450, button: 'left', clickCount: 1 });
    await p.send('Input.dispatchKeyEvent', { type: 'keyDown', key: 'Escape', code: 'Escape', windowsVirtualKeyCode: 27 });
    await sleep(500);
    const errs = p.logs.filter(l => (l.type === 'error' || l.type === 'EXCEPTION' || l.type === 'log.error') && !(l.type === 'EXCEPTION' && STOP.test(l.text || '')));
    check(!errs.length, `${lang}: no console error besides twin3d.js's own stop ${errs.length ? JSON.stringify(errs).slice(0, 400) : ''}`);
    check(p.logs.filter(l => l.type === 'EXCEPTION' && STOP.test(l.text || '')).length === 1, `${lang}: twin3d.js stopped once`);
  } finally { await p.close(); }
}

(async () => {
  try { for (const lang of langs) await run(lang); }
  catch (e) { console.error(e); process.exit(2); }
  console.log(`\n${passed} passed, ${problems.length} failed`); problems.forEach(x => console.log('  - ' + x));
  process.exit(problems.length ? 1 : 0);
})();
