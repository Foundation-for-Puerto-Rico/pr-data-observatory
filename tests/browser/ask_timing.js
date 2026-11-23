// "Ask the observatory": the time to the first answer on a throttled connection (docs/ask.md, "Time to the first answer"). Each run is a first load with the cache off,
// at Lighthouse's Slow 4G figures (as throttle.js); once the map is ready, the pointer goes over the Ask button, presses it 300 ms later and asks the question at once.
// It reports the seconds from the press to the answer, and the compressed bytes the chat fetched (chat.js, ask.js, the layer registry and the files of the index).
//   chrome --headless=new --remote-debugging-port=<port> --user-data-dir=<a scratch folder>      (CDP_PORT=<port>)
//   node tests/browser/serve_gzip.js site 8041
//   node tests/browser/ask_timing.js [base URL, default http://127.0.0.1:8041] [label] [runs, default 3]
//   ASK_PAGE=dictionary.html (a page without a map: the press as soon as the button is there; the chat there also fetches askpage.js, the shared engine and its datasets)
const { openPage } = require('./cdp.js');
const base = process.argv[2] || 'http://127.0.0.1:8041', label = process.argv[3] || '', runs = +(process.argv[4] || 3);
const SLOW4G = { offline: false, latency: 150, downloadThroughput: 1.6e6 / 8, uploadThroughput: 750e3 / 8 };
const Q = { es: 'transporte y vivienda', en: 'Transportation and housing' };
const CHAT_FILES = /js\/(chat|ask|askpage)\.js|js\/core\/layers\.js|data\/(catalog_es|glossary_forms_(en|es))\.json/, PAGE = process.env.ASK_PAGE || '';
(async () => {
  for (const lang of ['en', 'es']) {
    const times = [], kbs = [];
    for (let i = 0; i < runs; i++) {
      const p = await openPage('about:blank', { noCache: true, width: 1400, height: 900 });
      const bytes = new Map();
      await p.send('Network.emulateNetworkConditions', SLOW4G);
      await p.send('Page.navigate', { url: `${base}/${PAGE || 'index.html'}?lang=${lang}` });
      if (PAGE) await p.waitFor(`document.readyState === 'complete'`, 180000);
      else await p.waitFor(`!!document.querySelector('#loader.hide') || (document.querySelector('#loader') && getComputedStyle(document.querySelector('#loader')).display === 'none')`, 180000);
      await p.waitFor(`!!document.getElementById('chBtn')`, 60000);
      await p.eval(`(() => { window.__res0 = performance.getEntriesByType('resource').length; const b = document.getElementById('chBtn'); b.dispatchEvent(new PointerEvent('pointerenter')); return true; })()`);
      await new Promise(r => setTimeout(r, 300));
      const t0 = await p.eval(`(() => { window.__t0 = performance.now(); document.getElementById('chBtn').click(); return window.__t0; })()`);
      await p.waitFor(`typeof Chat !== 'undefined' && document.body.classList.contains('chat-open')`, 180000, 50);
      await p.eval(`Chat.ask(${JSON.stringify(Q[lang])})`);
      await p.waitFor(`!Chat.state.busy && document.querySelectorAll('#chLog .ch-msg.bot').length >= 2`, 180000, 50);
      const t1 = await p.eval(`performance.now()`);
      const kb = await p.eval(`performance.getEntriesByType('resource').filter(e => ${CHAT_FILES}.test(e.name)).reduce((a, e) => a + (e.transferSize || 0), 0) / 1024`);
      times.push((t1 - t0) / 1000); kbs.push(kb);
      await p.close();
    }
    const med = (a) => a.slice().sort((x, y) => x - y)[Math.floor(a.length / 2)];
    console.log(`${label}${PAGE ? ' ' + PAGE : ''} ${lang}: press to first answer ${times.map(t => t.toFixed(2)).join(', ')} s (median ${med(times).toFixed(2)} s); chat files ${med(kbs).toFixed(1)} KB compressed`);
  }
})().catch(e => { console.error(e); process.exitCode = 2; });
