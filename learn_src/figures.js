// The figures of the Learn page that the map's own code must compute, so a lesson and the tool it opens give the same numbers (docs/learn.md).
// learn.py runs this with Node and reads the JSON it prints:
//   node learn_src/figures.js <site dir> <lng> <lat> <minutes,comma separated>
// walk: the area within a walk of so many minutes along mapped roads from the point, exactly as the Walking time tool traces it
//       (Core.study.walkArea on js/roads.js's graph, 80 m a minute), with its residents (2020 Census blocks whose point is inside).
// hex:  the tourism places the map draws, counted in hexagons of 10 km² exactly as "Places in hexagons" counts them (Core.hexbin).
'use strict';
const fs = require('fs'), path = require('path'), vm = require('vm');
const [site, lng, lat, mins] = [path.resolve(process.argv[2]), +process.argv[3], +process.argv[4], process.argv[5].split(',').map(Number)];
const Study = require(path.join(site, 'js', 'core', 'study.js'));
const Hexbin = require(path.join(site, 'js', 'core', 'hexbin.js'));
const ctx = { console, Math, Map, Set, Float64Array, Float32Array, Int32Array, Uint32Array, Uint16Array, Uint8Array, DataView, ArrayBuffer, TextDecoder };
vm.runInNewContext(fs.readFileSync(path.join(site, 'js', 'roads.js'), 'utf8') + '\nthis.Roads = Roads;', ctx);
const b = fs.readFileSync(path.join(site, 'data', 'roads.bin'));
const R = new ctx.Roads(b.buffer.slice(b.byteOffset, b.byteOffset + b.byteLength));
const blocks = JSON.parse(fs.readFileSync(path.join(site, 'data', 'population_blocks.json'), 'utf8'));   // [lon, lat, residents, ...]
const WALK_MPM = 80;   // site/js/studyareas.js: 4.8 km/h

const walk = mins.map((min) => {
  const w = Study.walkArea(R, lng, lat, min * WALK_MPM);
  if (!w) throw new Error('no walkable road near the point');
  const box = Study.bbox(w.geometry);
  let residents = 0;
  for (const k of blocks) if (k[0] >= box[0] && k[0] <= box[2] && k[1] >= box[1] && k[1] <= box[3] && Study.inside(w.geometry, k[0], k[1])) residents += k[2];
  return { min, m: min * WALK_MPM, km2: +Study.areaKm2(w.geometry).toFixed(2), residents };
});

const places = JSON.parse(fs.readFileSync(path.join(site, 'data', 'places.json'), 'utf8'))
  .filter(p => (p.confidence || 0) >= 0.5 && p.type !== 'Places of Worship' && isFinite(p.lat) && isFinite(p.lng));
const bins = Hexbin.bin(places.map(p => ({ lat: p.lat, lng: p.lng })), { area: 10 });
const counts = bins.cells.map(c => c.n).sort((x, y) => y - x);
const total = counts.reduce((t, n) => t + n, 0);
let run = 0, half = 0;
for (const n of counts) { run += n; half++; if (run * 2 >= total) break; }
const top10 = counts.slice(0, 10).reduce((t, n) => t + n, 0);
const hex = { km2: bins.km2, cells: counts.length, places: total, max: counts[0], half_cells: half, top10, one: counts.filter(n => n === 1).length };

// relations (lesson A3): the counted places with a point that the build placed in no barrio, tested against the municipios' outlines with the
// map's own point-in-polygon test (Core.study.inside), and how far each lies from the nearest barrio outline (flat projection, as Core.study.ring).
const counted = JSON.parse(fs.readFileSync(path.join(site, 'data', 'places.json'), 'utf8')).filter(p => (p.confidence || 0) >= 0.5 && p.type !== 'Places of Worship');
const munis = JSON.parse(fs.readFileSync(path.join(site, 'data', 'municipios.geojson'), 'utf8')).features.map(f => ({ g: f.geometry, box: Study.bbox(f.geometry) }));
const barrioGeo = JSON.parse(fs.readFileSync(path.join(site, 'data', 'barrios.geojson'), 'utf8')).features.map(f => f.geometry);
const rings = (g) => (g.type === 'Polygon' ? g.coordinates : g.coordinates.flat());
const segM = (px, py, a, b2, k) => {   // metres from a point to a segment, on the flat projection at the point's latitude
  const ax = (a[0] - px) * k, ay = (a[1] - py) * 110574, bx = (b2[0] - px) * k, by = (b2[1] - py) * 110574, dx = bx - ax, dy = by - ay, L = dx * dx + dy * dy;
  const t = L ? Math.max(0, Math.min(1, -(ax * dx + ay * dy) / L)) : 0;
  return Math.hypot(ax + t * dx, ay + t * dy);
};
const loose = counted.filter(p => isFinite(p.lat) && isFinite(p.lng) && !p.barrio);
let offIsland = 0; const gaps = [];
for (const p of loose) {
  if (!munis.some(m => p.lng >= m.box[0] && p.lng <= m.box[2] && p.lat >= m.box[1] && p.lat <= m.box[3] && Study.inside(m.g, p.lng, p.lat))) offIsland++;
  const k = 111320 * Math.cos(p.lat * Math.PI / 180);
  let best = Infinity;
  for (const g of barrioGeo) for (const r of rings(g)) for (let i = 1; i < r.length; i++) { const d = segM(p.lng, p.lat, r[i - 1], r[i], k); if (d < best) best = d; }
  gaps.push(best);
}
gaps.sort((x, y) => x - y);
const relations = { loose: loose.length, off_island: offIsland, median_m: Math.round(gaps[Math.floor((gaps.length - 1) / 2)] || 0), within100: gaps.filter(d => d <= 100).length };

// classes (lesson A4): the newest poverty rate of the municipios in five classes by each of the map's three methods (Core.classify, as the Analysis tab shades a layer)
const Classify = require(path.join(site, 'js', 'core', 'classify.js'));
const hs = JSON.parse(fs.readFileSync(path.join(site, 'data', 'housing_series.json'), 'utf8'));
const pov = hs.vars.find(v => v.key === 'poverty_pct'), yr = String(hs.latest.acs), names = hs.geo.names.slice(0, -1);   // the last place is Puerto Rico as a whole
const vals = pov.years[yr].slice(0, names.length), pool = vals.filter(v => v != null).sort((x, y) => x - y);
const methods = {};
for (const m of ['quantile', 'equal', 'jenks']) {
  const br = Classify.make(pool, { method: m, k: 5 });
  const cls = vals.map(v => (v == null ? -1 : Classify.classOf(br, v, 5)));
  methods[m] = { edges: br.edges.map(x => +x.toFixed(2)), counts: [0, 1, 2, 3, 4].map(c => cls.filter(x => x === c).length), cls };
}
const classes = { year: +yr, n: pool.length, values: vals, names,
  moved: names.filter((_, i) => methods.quantile.cls[i] !== methods.equal.cls[i]).length,
  methods: Object.fromEntries(Object.entries(methods).map(([m, o]) => [m, { edges: o.edges, counts: o.counts, cls: o.cls }])) };

// cause (lesson C2): adults with a bachelor's degree against the poverty rate, by municipio and by barrio, in the same newest window, with the
// correlation the map's workbench computes (Core.stats.correlation, Pearson, over the places where both have a value)
const Stats = require(path.join(site, 'js', 'core', 'stats.js'));
const ab = JSON.parse(fs.readFileSync(path.join(site, 'data', 'acs_barrio.json'), 'utf8')), AB = Object.fromEntries(ab.vars.map(v => [v.key, v]));
const deg = hs.vars.find(v => v.key === 'bachelors_pct').years[yr].slice(0, names.length);
const cm = Stats.correlation(deg, vals, names.length), bd = AB.bachelors_pct.years[yr], bp = AB.poverty_pct.years[yr], cb = Stats.correlation(bd, bp, bd.length);
const cause = { year: +yr, x: 'bachelors_pct', y: 'poverty_pct', muni: { r: +cm.r.toFixed(2), n: cm.n, points: deg.map((d, i) => [d, vals[i]]) }, barrio: { r: +cb.r.toFixed(2), n: cb.n } };

process.stdout.write(JSON.stringify({ walk, hex, relations, classes, cause }));
