// Minimal Chrome DevTools Protocol client for a headless browser that is already running (port 9333). Read-only review tool: it only loads the pages of the scratch copy.
const http = require('http');

function getJson(url) {
  return new Promise((ok, fail) => {
    http.get(url, (r) => { let s = ''; r.on('data', (d) => s += d); r.on('end', () => { try { ok(JSON.parse(s)); } catch (e) { fail(e); } }); }).on('error', fail);
  });
}

async function connect(port = 9333) {
  const v = await getJson(`http://127.0.0.1:${port}/json/version`);
  const ws = new WebSocket(v.webSocketDebuggerUrl);
  await new Promise((ok, fail) => { ws.onopen = ok; ws.onerror = fail; });
  let id = 0; const pending = new Map(), listeners = [];
  ws.onmessage = (m) => {
    const msg = JSON.parse(m.data);
    if (msg.id && pending.has(msg.id)) { const { ok, fail } = pending.get(msg.id); pending.delete(msg.id); msg.error ? fail(new Error(JSON.stringify(msg.error))) : ok(msg.result); }
    else listeners.forEach(l => l(msg));
  };
  const send = (method, params = {}, sessionId) => new Promise((ok, fail) => { const i = ++id; pending.set(i, { ok, fail }); ws.send(JSON.stringify({ id: i, method, params, sessionId })); });
  return { ws, send, on: (f) => listeners.push(f) };
}

async function openPage(url, opts = {}) {
  const c = await connect(opts.port || +process.env.CDP_PORT || 9333);   // CDP_PORT: your own Chrome when 9333 is taken
  const { targetId } = await c.send('Target.createTarget', { url: 'about:blank' });
  const { sessionId } = await c.send('Target.attachToTarget', { targetId, flatten: true });
  const logs = [], failed = [], bad = [];
  c.on((msg) => {
    if (msg.sessionId !== sessionId) return;
    const p = msg.params || {};
    if (msg.method === 'Runtime.consoleAPICalled') logs.push({ type: p.type, text: (p.args || []).map(a => a.value !== undefined ? String(a.value) : (a.description || a.type)).join(' ') });
    if (msg.method === 'Runtime.exceptionThrown') { const d = p.exceptionDetails || {}; logs.push({ type: 'EXCEPTION', text: (d.exception && (d.exception.description || d.exception.value)) || d.text, url: d.url, line: d.lineNumber, col: d.columnNumber }); }
    if (msg.method === 'Log.entryAdded') logs.push({ type: 'log.' + p.entry.level, text: p.entry.text + (p.entry.url ? ' [' + p.entry.url + ']' : '') });
    if (msg.method === 'Network.loadingFailed') failed.push({ url: p.requestId, error: p.errorText, canceled: p.canceled });
    if (msg.method === 'Network.responseReceived' && p.response.status >= 400) bad.push({ url: p.response.url, status: p.response.status });
  });
  const reqUrl = new Map();
  c.on((msg) => { if (msg.sessionId === sessionId && msg.method === 'Network.requestWillBeSent') reqUrl.set(msg.params.requestId, msg.params.request.url); });
  for (const d of ['Runtime', 'Log', 'Page', 'Network']) await c.send(d + '.enable', {}, sessionId);
  if (opts.block) await c.send('Network.setBlockedURLs', { urls: opts.block }, sessionId);
  if (opts.block) {   // the page's workers too (MapLibre fetches its tiles in web workers, which the page's own blocking does not reach)
    c.on((msg) => {
      if (msg.sessionId !== sessionId || msg.method !== 'Target.attachedToTarget') return;
      const s = msg.params.sessionId, worker = /worker/.test(msg.params.targetInfo.type);
      (worker ? c.send('Network.enable', {}, s).then(() => c.send('Network.setBlockedURLs', { urls: opts.block }, s)) : Promise.resolve())
        .catch(() => {}).then(() => c.send('Runtime.runIfWaitingForDebugger', {}, s)).catch(() => {});
    });
    await c.send('Target.setAutoAttach', { autoAttach: true, waitForDebuggerOnStart: true, flatten: true }, sessionId);
  }
  if (opts.noCache) await c.send('Network.setCacheDisabled', { cacheDisabled: true }, sessionId);
  if (opts.network) await c.send('Network.emulateNetworkConditions', opts.network, sessionId);   // e.g. Slow 4G: { offline: false, latency: 150, downloadThroughput: 200000, uploadThroughput: 93750 }
  if (opts.width) await c.send('Emulation.setDeviceMetricsOverride', { width: opts.width, height: opts.height || 900, deviceScaleFactor: 1, mobile: !!opts.mobile }, sessionId);
  if (opts.colorScheme) await c.send('Emulation.setEmulatedMedia', { features: [{ name: 'prefers-color-scheme', value: opts.colorScheme }] }, sessionId);
  const loaded = new Promise((ok) => c.on((msg) => { if (msg.sessionId === sessionId && msg.method === 'Page.loadEventFired') ok(); }));
  await c.send('Page.navigate', { url }, sessionId);
  await Promise.race([loaded, new Promise(r => setTimeout(r, 30000))]);
  // o.timeout: the limit of this one evaluation (30 s unless a call says otherwise). Chrome answers a script that passes it with a bare "Internal error": say which.
  const evalJs = async (expression, o = {}) => {
    const limit = o.timeout || 30000, t0 = Date.now();
    let r; try { r = await c.send('Runtime.evaluate', { expression, awaitPromise: true, returnByValue: true, timeout: limit }, sessionId); }
    catch (e) { if (Date.now() - t0 >= limit - 100) throw new Error(`eval did not finish within its ${limit} ms limit (${e.message}): ${expression.replace(/\s+/g, ' ').slice(0, 120)}`); throw e; }
    if (r.exceptionDetails) throw new Error('eval failed: ' + ((r.exceptionDetails.exception && r.exceptionDetails.exception.description) || r.exceptionDetails.text));
    return r.result.value;
  };
  const waitFor = async (expression, ms = 40000, step = 250) => { const t0 = Date.now(); while (Date.now() - t0 < ms) { try { if (await evalJs(expression)) return true; } catch (e) { /* page not ready */ } await new Promise(r => setTimeout(r, step)); } return false; };
  const close = async () => { try { await c.send('Target.closeTarget', { targetId }); } catch (e) { /* ignore */ } c.ws.close(); };
  const failedUrls = () => failed.map(f => ({ url: reqUrl.get(f.url) || f.url, error: f.error, canceled: f.canceled }));
  const on = (method, f) => c.on((msg) => { if (msg.sessionId === sessionId && msg.method === method) f(msg.params); });   // an event of this page (e.g. Fetch.requestPaused)
  return { send: (m, p) => c.send(m, p, sessionId), on, eval: evalJs, waitFor, logs, failed: failedUrls, bad, close };
}

module.exports = { openPage, connect, getJson };
