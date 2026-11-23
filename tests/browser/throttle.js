// Page loads on a throttled connection (docs/performance.md). Needs a headless Chrome with its own profile on port 9333 (or the port in CDP_PORT) and the site served with gzip (serve_gzip.js):
//   chrome --headless=new --remote-debugging-port=9333 --user-data-dir=<a scratch folder> --no-first-run
//   node tests/browser/throttle.js http://127.0.0.1:8041 [label] [runs]   (some pages only: PAGES=map,wcrp)
// Each run is a first load with the cache off, at Lighthouse's Slow 4G figures (150 ms round trip, 1.6 Mbit/s down, 750 kbit/s up). It records the bytes the page
// transferred (compressed, all hosts: the map tiles and the libraries from cdnjs too), when the load event fired, and when the page was ready to use (its own sign).
// It then waits for the glossary (js/core/glossary.js), which loads once the page has its data and fetches its match forms ('later' in routes.json), and reports when its
// underlines were in (gloss_s) and the bytes by then (gloss_kb). kb and site_kb stay what they were before the glossary: the bytes up to 1.6 s after the page was ready.
const { connect } = require('./cdp.js');
const base = process.argv[2] || 'http://127.0.0.1:8041', label = process.argv[3] || '', runs = +(process.argv[4] || 3);
const PAGES = [
  { name: 'map', path: '/index.html?lang=es', ready: "!!document.querySelector('#loader.hide') || (document.querySelector('#loader') && getComputedStyle(document.querySelector('#loader')).display === 'none')" },
  { name: '3d', path: '/3d.html?lang=es', ready: "!!document.querySelector('#loader.hide')" },   // the places start switched off (2026-10-15): nothing to wait for after ready
  { name: 'profile', path: '/profile.html?area=72127&lang=es', ready: "!!document.querySelector('.pf-sec')" },
  { name: 'housing', path: '/housing.html?lang=es', ready: "!!document.querySelector('#snapshotLabel b')" },
  { name: 'wcrp', path: '/wcrp.html?lang=es', ready: "performance.getEntriesByName('ready').length > 0" },   // the Social Capital map, the page's first, has drawn its points (2026-10-19; the vulnerability map loads on approach)
  { name: 'routes', path: '/route-analysis.html?lang=es', ready: "!!document.querySelector('#rcBody tr')" },   // the chart and the route table are drawn (route_analysis.js)
  { name: 'gii', path: '/gii.html?lang=es', ready: "document.querySelectorAll('.gp-ind').length === 80" },   // the profile is drawn (gii.js)
  { name: 'women', path: '/women-labor.html?lang=es', ready: "document.querySelectorAll('#wlMap path.mu').length === 78" },   // the charts and the municipio map are drawn (women_labor.js)
  { name: 'knowledge', path: '/knowledge.html?lang=es', ready: "document.querySelectorAll('.kh-card').length > 0" },   // the cards are drawn (knowledge_home.js)
  { name: 'learn', path: '/learn.html?lang=es', ready: "document.querySelectorAll('.ln-card').length > 0 && !!document.querySelector('#lnNearFig table')" },   // the cards and the lessons' figures are drawn (learn_page.js)
  { name: 'publicmoney', path: '/public-money.html?lang=es', ready: "document.querySelectorAll('#pmMap path.mu').length === 78 && !!document.querySelector('#pmHma tbody tr')" },   // the bivariate map and the Hazard Mitigation table are drawn (public_money.js)
  { name: 'publicspending', path: '/public-spending.html?lang=es', ready: "document.querySelectorAll('#psTree .tile').length > 5 && !!document.querySelector('#psGap circle.sp') && document.querySelectorAll('#psMap path.mu').length === 78" },   // the treemap, the approved-against-spent dots and the capital projects map are drawn
  { name: 'reservoirs', path: '/reservoirs.html?lang=es', ready: "!!document.querySelector('#rvRank tbody tr[data-r]') && !!document.querySelector('#rvRecent svg')" },
  { name: 'oppzones', path: '/opportunity-zones.html?lang=es', ready: "!!document.querySelector('#ozMunis tbody tr') && document.querySelectorAll('#ozMap path').length > 900 && !!document.querySelector('#ozScatter circle')" },   // the municipio table, the tract map and the scatter are drawn (oz_page.js)
  { name: 'energy', path: '/energy.html?lang=es', ready: "!!document.querySelector('#enMunis tbody tr') && !!document.querySelector('#enMix svg rect')" },   // the municipio table and the mix chart are drawn (energy_page.js)
  { name: 'broadband', path: '/broadband.html?lang=es', ready: "!!document.querySelector('#bbMunis tbody tr') && document.querySelectorAll('#bbMap path').length > 800" },   // the municipio table and the barrio map are drawn (broadband_page.js)
  { name: 'urbanheat', path: '/urban-heat.html?lang=es', ready: "!!document.querySelector('#uhScatter circle') && !!document.querySelector('#uhTable tbody tr')" },   // the scatter and the barrio table are drawn (urban_heat.js)
  { name: 'inflation', path: '/inflation.html?lang=es', ready: "!!document.querySelector('#inMain path') && !!document.querySelector('#inYearTable tbody tr')" },   // the headline chart and the table of years
  { name: 'dictionary', path: '/dictionary.html?lang=es', ready: "!!document.querySelector('#snapshotLabel') && document.querySelector('#snapshotLabel').textContent !== '—'" },
  { name: 'datamgmt', path: '/data-management.html?lang=es', ready: "performance.getEntriesByName('ready').length > 0" },   // the table, the growth chart and the counts are drawn (datamgmt.js)
];
const SLOW4G = { offline: false, latency: 150, downloadThroughput: 1.6e6 / 8, uploadThroughput: 750e3 / 8 };

async function measure(c, page) {
  const { targetId } = await c.send('Target.createTarget', { url: 'about:blank' });
  const { sessionId } = await c.send('Target.attachToTarget', { targetId, flatten: true });
  const send = (m, p = {}) => c.send(m, p, sessionId);
  let bytes = 0, t0 = 0, loadAt = null, readyAt = null; const byHost = {}, url = new Map(), asked = [], got = [];
  c.on(msg => {
    if (msg.sessionId !== sessionId) return;
    if (msg.method === 'Network.requestWillBeSent') { const u = msg.params.request.url; url.set(msg.params.requestId, u); const m = u.startsWith(base) && /\/data\/([^?#]+)/.exec(u); if (m) asked.push([m[1], msg.params.wallTime * 1000]); }   // which data files are asked for, and when
    if (msg.method === 'Network.loadingFinished') { const b = msg.params.encodedDataLength || 0, u = url.get(msg.params.requestId) || ''; bytes += b; const h = u.startsWith(base) ? 'site' : (u.split('/')[2] || '?'); byHost[h] = (byHost[h] || 0) + b; got.push([Date.now() - t0, b, h]); }
    if (msg.method === 'Page.loadEventFired' && loadAt == null) loadAt = Date.now() - t0;
  });
  for (const d of ['Network', 'Page', 'Runtime']) await send(d + '.enable');
  await send('Network.setCacheDisabled', { cacheDisabled: true });
  await send('Network.emulateNetworkConditions', SLOW4G);
  // In the page, on its own clock: each data file's fetch() call (every data file comes through common.js's fetchRetry), and a 10 ms poller for the ready sign.
  await send('Page.addScriptToEvaluateOnNewDocument', { source: `(() => {
    const asked = window.__asked = [], f0 = window.fetch;
    window.fetch = function (input) { try { const u = new URL(input instanceof Request ? input.url : String(input), location.href), m = u.origin === location.origin && new RegExp('/data/([^?#]+)').exec(u.pathname); if (m) asked.push([m[1], performance.now()]); } catch (e) {} return f0.apply(this, arguments); };
    const m0 = performance.mark; performance.mark = function (name) { try { if (name === 'ready' && window.__readyIdx == null) window.__readyIdx = asked.length; } catch (e) {} return m0.apply(this, arguments); };   // where the mark falls in the list of calls: an order, not a time (two calls in one step can share a rounded timestamp)
    const f = () => { try { if (${page.ready}) { window.__readyNow = performance.now(); return; } } catch (e) {} setTimeout(f, 10); }; f();
  })();` });
  await send('Emulation.setDeviceMetricsOverride', { width: 1280, height: 800, deviceScaleFactor: 1, mobile: false });
  t0 = Date.now(); await send('Page.navigate', { url: base + page.path });
  const wait = async (expr, ms) => { while (Date.now() - t0 < ms) { try { const r = await send('Runtime.evaluate', { expression: expr, returnByValue: true }); if (r.result && r.result.value) return Date.now() - t0; } catch (e) { /* navigating */ } await new Promise(r => setTimeout(r, 100)); } return null; };
  readyAt = await wait(page.ready, 120000); const laterAt = page.later ? await wait(page.later, 180000) : null;
  const glossAt = await wait("typeof netBusy === 'undefined' || !!(window.Core && Core.glossary && Core.glossary.state && Core.glossary.state !== 'loading')", 180000);   // a build without the glossary (before 2026-10-19) answers at once
  // When the page was ready, and which files came before. Best: the mark the map and the 3D view set where they hide the loader, placed in the list of the
  // page's own fetch() calls at the moment it is made, so the split is by order, not by time (the page clock is rounded to 0.1 ms, and a call made in the same
  // step as the mark can share its timestamp; review of PR #43): the 3D view's trips and hurricanes, asked for just after it, come after it; the map's
  // operators.json, asked for just before it, comes before, although the browser sends it a few ms after. Else the poller on the page clock (late under load:
  // 2 of 4 batches on 2026-10-16 put the 3D files in 'first'), else this script's poll against the browser's request times, up to 100 ms late.
  const own = (await send('Runtime.evaluate', { expression: "({ idx: window.__readyIdx, poll: window.__readyNow, asked: window.__asked || [] })", returnByValue: true })).result.value;
  let first, later;
  if (own.asked.length > 0 && own.idx != null) {
    first = new Set(own.asked.slice(0, own.idx).map(a => a[0])); later = new Set(own.asked.slice(own.idx).map(a => a[0]));
  } else {
    const inPage = own.asked.length > 0 && own.poll != null;
    const [log, ep, EDGE] = inPage ? [own.asked, own.poll, 20] : [asked, readyAt != null ? t0 + readyAt : Infinity, 150];   // ms: the poller checks every 10 ms
    first = new Set(log.filter(a => a[1] < ep - EDGE).map(a => a[0])); later = new Set(log.filter(a => a[1] >= ep - EDGE).map(a => a[0]));
  }
  await new Promise(r => setTimeout(r, 1500));   // what the page fetches just after it is ready (tiles) counts too
  const upTo = (ms, site) => got.filter(g => g[0] <= ms && (!site || g[2] === 'site')).reduce((s, g) => s + g[1], 0), cut = (readyAt || 0) + 1600;
  const out = { page: page.name, kb: Math.round(upTo(cut) / 1024), site_kb: Math.round(upTo(cut, true) / 1024), gloss_kb: glossAt ? Math.round(upTo(glossAt + 1500) / 1024) : null, load_s: loadAt && +(loadAt / 1000).toFixed(1), ready_s: readyAt && +(readyAt / 1000).toFixed(1), ...(page.later ? { places_s: laterAt && +(laterAt / 1000).toFixed(1) } : {}), gloss_s: glossAt && +(glossAt / 1000).toFixed(1), first: [...first].sort(), later: [...later].sort() };
  try { await c.send('Target.closeTarget', { targetId }); } catch (e) { /* ignore */ }
  return out;
}

(async () => {
  const c = await connect(+process.env.CDP_PORT || 9333), rows = [], routes = JSON.parse(require('fs').readFileSync(require('path').join(__dirname, '..', '..', 'dictionary_src', 'routes.json'), 'utf8')).routes;
  for (const p of PAGES.filter(p => !process.env.PAGES || process.env.PAGES.split(",").includes(p.name))) for (let k = 0; k < runs; k++) rows.push({ label, run: k + 1, ...(await measure(c, p)) });
  console.log(JSON.stringify(rows));
  // what the browser fetched against what budget.py counts (dictionary_src/routes.json)
  let off = 0;
  for (const r of rows) { const want = routes[r.page] || {}; for (const when of ['first', 'later']) { const a = JSON.stringify(r[when]), b = JSON.stringify([...(want[when] || [])].sort()); if (a !== b) { off++; console.error(`${r.page} run ${r.run}: '${when}' fetched ${a}, routes.json says ${b}`); } } }
  if (off) process.exitCode = 2;
  c.ws.close();
})().catch(e => { console.error(e); process.exit(1); });
