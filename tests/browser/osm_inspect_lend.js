// The OpenStreetMap inspector's road matching (site/js/core/osminspect.js, sameAlong; docs/basemap.md, section 8), from the review of PR #99: a merged road
// label (ID ending 0) borrowed the ID of the nearest road line of its class within 8 px, which near a crossing was the cross street (4 of 101 points:
// "Calle de San Francisco" → way 22230974, Calle de O'Donnell; "Calle de la Tanca" → 60330131, Recinto Sur; "Paseo Dr. Gilberto Concepción de Gracia" →
// 22230881, Calle del Muelle; "Paseo Covadonga" → 22222684, an unnamed tertiary_link). On the 2D map and the 3D view, at three places (Old San Juan at zoom 17,
// Hato Rey and Carolina at 16), every 15 px along every merged label drawn on top:
//   - a label that borrows a way: that way's line runs along the label (half its vertices on screen within 3 px of it), never a cross street;
//   - the four ways of the review are never lent to those four labels;
// and every 15 px along every road line drawn on top that borrows a name: the label lines of its class passing within 3 px of the click along the road's
// bearing (20°) all bear that one name (a road line may be merged from several streets, so only the street at the click counts; a label that only ends at the
// click, the next street of a junction, counts only when no label passes there inside its length).
//   chrome --headless=new --remote-debugging-port=9333 --user-data-dir=<a scratch folder> --use-angle=d3d11 --enable-gpu     (or your own port in CDP_PORT)
//   node tests/browser/serve_gzip.js site 8041
//   node tests/browser/osm_inspect_lend.js [base URL, default http://127.0.0.1:8041] [views, default 2d,3d] [places 1-3, default all]
// Exit code: 0 when every check passed, 1 when one failed, 2 on an error.
const { openPage } = require('./cdp.js');
const base = process.argv[2] || 'http://127.0.0.1:8041', views = (process.argv[3] || '2d,3d').split(','), only = process.argv[4] ? process.argv[4].split(',').map(Number) : null;
const sleep = (ms) => new Promise(r => setTimeout(r, ms));
let fails = 0, checks = 0; const check = (ok, what) => { checks++; console.log(`  ${ok ? 'ok  ' : 'FAIL'} ${what}`); if (!ok) fails++; return ok; };
const PLACES = [[18.4655, -66.1100, 17], [18.4005, -66.1047, 16], [18.4210, -66.0388, 16]];
const REVIEW = { 'Calle de San Francisco': 22230974, 'Calle de la Tanca': 60330131, 'Paseo Dr. Gilberto Concepción de Gracia': 22230881, 'Paseo Covadonga': 22222684 };
const PROBE = (GL) => `(() => { const gl = ${GL}, M = Core.osminspect, W = gl.getCanvas().clientWidth, H = gl.getCanvas().clientHeight, REVIEW = ${JSON.stringify(REVIEW)};
  const proj = (g) => (g.type === 'LineString' ? [g.coordinates] : g.type === 'MultiLineString' ? g.coordinates : []).map(l => l.map(c => gl.project(c)));
  const dist = (pt, lines) => { let b = Infinity; for (const l of lines) for (let i = 1; i < l.length; i++) b = Math.min(b, M.segDist(pt, l[i - 1], l[i])); return b; };
  const visible = (lines) => lines.flat().filter(q => q.x > 0 && q.y > 0 && q.x < W && q.y < H);
  const runsAlong = (a, b) => { const vs = visible(a); return vs.length < 2 || vs.filter(q => dist(q, b) <= 3).length / vs.length >= 0.5; };
  const roads = gl.querySourceFeatures('openmaptiles', { sourceLayer: 'transportation' }), names = gl.querySourceFeatures('openmaptiles', { sourceLayer: 'transportation_name' });
  const r = { labelTried: 0, lent: 0, cross: 0, review: 0, lineTried: 0, named: 0, wrongName: 0, ex: [] };
  const walk = (f, fn) => { for (const l of proj(f.geometry)) for (let i = 1; i < l.length; i++) { const a = l[i - 1], b = l[i], len = Math.hypot(b.x - a.x, b.y - a.y);
    for (let t = 0; t < len; t += 15) { const pt = { x: a.x + (b.x - a.x) * t / len, y: a.y + (b.y - a.y) * t / len }; if (pt.x > 20 && pt.y > 20 && pt.x < W - 20 && pt.y < H - 20) fn(pt); } } };
  const topAt = (pt) => gl.queryRenderedFeatures([[pt.x - 3, pt.y - 3], [pt.x + 3, pt.y + 3]]).filter(g => g.sourceLayer && M.describe(g))[0];
  const seen = new Set();
  for (const f of gl.queryRenderedFeatures().filter(f => f.sourceLayer === 'transportation_name' && f.id % 10 === 0 && f.properties.name)) {
    if (seen.has('n' + f.id + f.properties.name)) continue; seen.add('n' + f.id + f.properties.name);
    const L = proj(f.geometry);
    walk(f, (pt) => {
      const top = topAt(pt); if (!top || top.sourceLayer !== 'transportation_name' || top.id !== f.id) return;
      r.labelTried++; const d = M.at(gl, pt); if (!d || !d.osm) return; r.lent++;
      if (REVIEW[d.name] === d.osm.id) r.review++;
      const rd = roads.filter(g => g.id === d.osm.id * 10 + 2); if (!rd.length) return;
      if (!runsAlong(rd.flatMap(g => proj(g.geometry)), L)) { r.cross++; if (r.ex.length < 4) r.ex.push({ label: d.name, way: d.osm.id }); }
    });
  }
  for (const f of gl.queryRenderedFeatures().filter(f => f.sourceLayer === 'transportation')) {
    if (seen.has('t' + f.id)) continue; seen.add('t' + f.id);
    const L = proj(f.geometry);
    walk(f, (pt) => {
      if (r.lineTried >= 400) return;
      const top = topAt(pt); if (!top || top.sourceLayer !== 'transportation' || top.id !== f.id) return;
      r.lineTried++; const d = M.at(gl, pt); if (!d || !d.name) return; r.named++;
      // at the click: the label lines of the road's class that pass within 3 px of it running the same way (bearing within 20°). Those that pass there
      // inside their length must all bear the borrowed name; when none does, the borrowed name must be one of those that end there. A road line may be merged
      // from several streets (a grid at low zoom), so only the street at the click counts; a label that only ends at the click (the next street of a junction)
      // or one of another class beside it (a cycle lane) is not the road's.
      const segAt = (q, lines) => { let best = null; for (const l of lines) for (let i = 1; i < l.length; i++) { const a = l[i - 1], b = l[i], dx = b.x - a.x, dy = b.y - a.y, n = dx * dx + dy * dy,
        t = n ? Math.max(0, Math.min(1, ((q.x - a.x) * dx + (q.y - a.y) * dy) / n)) : 0, d = M.segDist(q, a, b); if (!best || d < best.d) best = { d, a, b, end: (i === 1 && t === 0) || (i === l.length - 1 && t === 1) }; } return best; };
      const ang = (s1, s2) => { let x = Math.abs(Math.atan2(s1.b.y - s1.a.y, s1.b.x - s1.a.x) - Math.atan2(s2.b.y - s2.a.y, s2.b.x - s2.a.x)) % Math.PI; if (x > Math.PI / 2) x = Math.PI - x; return x * 180 / Math.PI; };
      const mine = segAt(pt, L), inside = new Set(), ends = new Set();
      for (const g of names) {
        if (!g.properties.name || g.properties.class !== f.properties.class) continue;
        const t = segAt(pt, proj(g.geometry)); if (t && t.d <= 3 && ang(mine, t) <= 20) (t.end ? ends : inside).add(g.properties.name);
      }
      const here = inside.size ? inside : ends;
      const ok = inside.size ? inside.size === 1 && inside.has(d.name) : ends.has(d.name);   // at a junction of two streets of one line, either is the road there
      if (!ok) { r.wrongName++; if (r.ex.length < 8) r.ex.push({ line: f.id, name: d.name, here: [...here] }); }
    });
  }
  return r; })()`;

async function run(v) {
  for (const [lat, lng, z] of PLACES.filter((x, i) => !only || only.includes(i + 1))) {
    console.log(`\n${v} ${lat},${lng} z${z}`);
    const GL = v === '2d' ? 'bmH.layer.getMaplibreMap()' : 'map';
    const p = await openPage(`${base}/${v === '2d' ? 'index' : '3d'}.html?lang=en#c=${lat},${lng},${z}${v === '3d' ? '&b=0&p=0' : ''}&bm=liberty`, { width: 1400, height: 900, noCache: true });
    try {
      check(await p.waitFor(`document.getElementById('loader').classList.contains('hide') && !document.getElementById('osmInspect').disabled`, 120000), 'ready');
      await p.eval(`document.getElementById('osmInspect').click(), 1`); await p.waitFor(`!!(window.Core && Core.osminspect)`, 30000);
      await p.waitFor(`${GL}.loaded()`, 60000); await sleep(1500);
      const r = await p.eval(PROBE(GL), { timeout: 900000 });
      check(r.labelTried > 20 && r.lineTried > 20, `points tried: ${r.labelTried} on merged labels (${r.lent} with a borrowed way), ${r.lineTried} on road lines (${r.named} with a name)`);
      check(r.cross === 0, `no label borrows a way that does not run along it (${r.cross}) ${JSON.stringify(r.ex)}`);
      check(r.review === 0, `none of the review's four wrong ways (${r.review})`);
      check(r.wrongName === 0, `no road line borrows the name of a label that does not run along it (${r.wrongName})`);
    } finally { await p.close(); }
  }
}
(async () => {
  for (const v of views) await run(v);
  console.log(`\n${checks - fails}/${checks} checks passed`);
  process.exit(fails ? 1 : 0);
})().catch(e => { console.error(e); process.exit(2); });
