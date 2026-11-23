// Helpers for the base map's tile rules in a real browser (docs/basemap.md, section 4; basemap_fallback.js, basemap_switch.js).
//  - rewriteTileJson(page, template): answers the provider's TileJSON (https://tiles.openfreemap.org/planet, the vector source of Liberty and Positron) with its
//    tiles at another URL template, through the DevTools protocol (Fetch, at the response stage). MapLibre reads the TileJSON in the page and fetches the tiles in
//    its workers, so this reaches every tile. Call it on a blank page, then navigate.
//  - tileServer(port): a local server for such a template (its `url`) that fails, holds or passes tiles on from the provider, as its `st.mode` says:
//    'proxy' passes every tile on; 'fail' answers 500 to each; 'first-fails-rest-held' answers 500 to the first st.failFirst (1) and holds the others st.holdMs (7 s) before
//    passing them on (the case of the review of PR #92). It counts what it did in st (n, failed, held, served). Only the tiles a page view asks for go through.
const http = require('http');
const TILEJSON = '*tiles.openfreemap.org/planet';

async function rewriteTileJson(p, template, seen = []) {
  p.on('Fetch.requestPaused', async (e) => {
    try {
      const r = await p.send('Fetch.getResponseBody', { requestId: e.requestId });
      const j = JSON.parse(r.base64Encoded ? Buffer.from(r.body, 'base64').toString('utf8') : r.body);
      seen.push(j.tiles[0]);
      j.tiles = [typeof template === 'function' ? template(j.tiles[0]) : template];
      await p.send('Fetch.fulfillRequest', { requestId: e.requestId, responseCode: 200, body: Buffer.from(JSON.stringify(j)).toString('base64'),
        responseHeaders: [{ name: 'Content-Type', value: 'application/json' }, { name: 'Access-Control-Allow-Origin', value: '*' }, { name: 'Cache-Control', value: 'no-store' }] });
      if (!seen.time) seen.time = Date.now();   // when the page got the rewritten TileJSON: no tile of it can fail before
    } catch (err) { await p.send('Fetch.continueRequest', { requestId: e.requestId }).catch(() => {}); }
  });
  await p.send('Fetch.enable', { patterns: [{ urlPattern: TILEJSON, requestStage: 'Response' }] });
  return seen;   // the provider's own tile templates, as they came; seen.time: when the first rewritten TileJSON was answered
}

function tileServer(port) {
  const st = { mode: 'proxy', upstream: null, n: 0, failed: 0, held: 0, served: 0, holdMs: 7000, failFirst: 1 };
  const server = http.createServer(async (req, res) => {
    const m = /^\/t\/(\d+)\/(\d+)\/(\d+)/.exec(req.url), head = { 'Access-Control-Allow-Origin': '*', 'Cache-Control': 'no-store' };
    if (!m || !st.upstream) { res.writeHead(404, head); res.end(); return; }
    const n = ++st.n;
    if (st.mode === 'fail' || (st.mode === 'first-fails-rest-held' && n <= st.failFirst)) { st.failed++; res.writeHead(500, head); res.end(); return; }
    if (st.mode === 'first-fails-rest-held') { st.held++; await new Promise(r => setTimeout(r, st.holdMs)); }
    try {
      const r = await fetch(st.upstream.replace('{z}', m[1]).replace('{x}', m[2]).replace('{y}', m[3]), { headers: { 'User-Agent': 'pr-digital-twin browser test' } });
      const body = Buffer.from(await r.arrayBuffer()); st.served++;
      res.writeHead(r.status, { ...head, 'Content-Type': 'application/x-protobuf' }); res.end(body);
    } catch (e) { res.writeHead(502, head); res.end(); }
  });
  return new Promise((ok) => server.listen(port, '127.0.0.1', () => ok({
    st, url: `http://127.0.0.1:${port}/t/{z}/{x}/{y}.pbf`,
    close: () => new Promise(r => { if (server.closeAllConnections) server.closeAllConnections(); server.close(() => r()); }),
  })));
}

module.exports = { rewriteTileJson, tileServer, TILEJSON };
