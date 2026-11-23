// A static server for the page-weight measurements (docs/performance.md): it serves a site folder the way GitHub Pages does for these files, with gzip for text
// and byte ranges, and asks the browser not to cache, so every load is a first load.   node tests/browser/serve_gzip.js <site folder> <port>
const http = require('http'), fs = require('fs'), path = require('path'), zlib = require('zlib');
const root = path.resolve(process.argv[2] || 'site'), port = +(process.argv[3] || 8041);
const TYPES = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript', '.css': 'text/css', '.json': 'application/json', '.geojson': 'application/geo+json', '.svg': 'image/svg+xml', '.png': 'image/png', '.woff2': 'font/woff2', '.bin': 'application/octet-stream', '.ico': 'image/x-icon' };
const TEXT = new Set(['.html', '.js', '.css', '.json', '.geojson', '.svg', '.bin']);
http.createServer((req, res) => {
  let p = decodeURIComponent(new URL(req.url, 'http://x').pathname); if (p.endsWith('/')) p += 'index.html';
  const f = path.join(root, p); if (!f.startsWith(root) || !fs.existsSync(f) || fs.statSync(f).isDirectory()) { res.writeHead(404); res.end(); return; }
  const ext = path.extname(f), body = fs.readFileSync(f), head = { 'Content-Type': TYPES[ext] || 'application/octet-stream', 'Cache-Control': 'no-store', 'Accept-Ranges': 'bytes', 'Access-Control-Allow-Origin': '*' };
  if (TEXT.has(ext) && /gzip/.test(req.headers['accept-encoding'] || '')) { res.writeHead(200, { ...head, 'Content-Encoding': 'gzip', Vary: 'Accept-Encoding' }); res.end(zlib.gzipSync(body, { level: 6 })); return; }
  const m = /^bytes=(\d+)-(\d*)$/.exec(req.headers.range || '');   // a byte range, as GitHub Pages answers it (PMTiles reads its files this way)
  if (m) { const a = +m[1], b = Math.min(m[2] ? +m[2] : body.length - 1, body.length - 1); if (a > b) { res.writeHead(416, { 'Content-Range': `bytes */${body.length}` }); res.end(); return; }
    res.writeHead(206, { ...head, 'Content-Range': `bytes ${a}-${b}/${body.length}`, 'Content-Length': b - a + 1 }); res.end(body.subarray(a, b + 1)); return; }
  res.writeHead(200, head); res.end(body);
}).listen(port, '127.0.0.1', () => console.log(`serving ${root} on http://127.0.0.1:${port}`));
