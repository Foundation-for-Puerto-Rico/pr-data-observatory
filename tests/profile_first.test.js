// The area profile draws its first field with only the files named in FIRST (site/js/profile.js), then fetches the other files of js/core/datasets.js and draws
// every field (docs/performance.md). This checks, for each of the 78 municipios, that the first field and the similar municipios are the same with those files
// as with every file, so the second drawing only adds the other fields. When a dataset of the first field moves to another file, add that file to FIRST.
// Run: node --test tests/profile_first.test.js
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');

globalThis.fmt = (n, d = 0) => Number(n).toLocaleString('en-US', { minimumFractionDigits: d, maximumFractionDigits: d });
const core = (n) => require(path.join(__dirname, '..', 'site', 'js', 'core', n + '.js'));
const readData = (f) => JSON.parse(fs.readFileSync(path.join(__dirname, '..', 'site', 'data', f), 'utf8'));
const Core = Object.fromEntries(['text', 'palettes', 'stats', 'classify', 'time', 'format', 'normalize', 'reliability', 'engine', 'adapters', 'datasets'].map(n => [n, core(n)]));
const T = Core.text.T;

const src = fs.readFileSync(path.join(__dirname, '..', 'site', 'js', 'profile.js'), 'utf8');
const FIRST = JSON.parse(src.match(/const FIRST = (\[[^\]]*\]);/)[1].replace(/'/g, '"'));
const page = new Function('P', 'Core', 'T', src.slice(src.indexOf('const E = () => P.E;'), src.indexOf('function spark(')) + '\nreturn { rowOf, peersOf };');

function profile(names) {   // what profLoad() and profRest() set up, with the files named
  const muni = readData('municipalities.json'), meta = readData('meta.json'), catalog = readData('catalog.json'), index = readData('catalog_index.json').index, docs = {};
  for (const f of Core.datasets.FILES) if (names.includes(f.name)) docs[f.name] = readData(f.file);
  const P = { E: Core.engine.create() };
  Core.datasets.apply(P.E, docs, muni, +((meta.generated_at || '').slice(0, 4)) || 2026);
  const F = Object.fromEntries(index.fields.map((f, i) => [f, i]));
  P.domainOf = new Map(index.rows.map(r => [r[F.id], r[F.domain]]));
  P.domains = catalog.domains.filter(d => !d.parent).sort((a, b) => a.order - b.order);
  P.parent = new Map(catalog.domains.map(d => [d.id, d.parent || d.id]));
  return { P, ...page(P, Core, T) };
}
function firstField(p, i) {   // render(): the rows of the first field that has any, in the page's order
  const rows = p.P.E.list().map(v => p.rowOf(v, i)).filter(Boolean), ids = p.P.domains.map(d => d.id), dom = ids.find(id => rows.some(r => r.dom === id));
  return { dom, rows: rows.filter(r => r.dom === dom).map(r => ({ key: r.v.key, group: r.v.group, label: r.v.label, year: r.year, chip: r.chip, val: r.val, miss: r.miss, moe: r.moe, norm: r.norm, cmp: r.cmp, prv: r.prv, rk: r.rk, trend: r.trend })) };
}

test('FIRST names files of js/core/datasets.js, with every required one', () => {
  const names = Core.datasets.FILES.map(f => f.name);
  for (const n of FIRST) assert.ok(names.includes(n), n);
  for (const f of Core.datasets.FILES.filter(f => f.required)) assert.ok(FIRST.includes(f.name), f.name);
  assert.ok(FIRST.length < names.length, 'some files are left for after the first drawing');
});

test('the first field and the similar municipios are the same with the first files as with every file, for each municipio', () => {
  const part = profile(FIRST), full = profile(Core.datasets.FILES.map(f => f.name)), pr = full.P.E.geo.pr;
  assert.deepStrictEqual(part.P.E.geo.names, full.P.E.geo.names);
  for (let i = 0; i < pr; i++) {
    const name = full.P.E.geo.names[i], a = firstField(part, i), b = firstField(full, i);
    assert.strictEqual(a.dom, b.dom, name);
    assert.ok(b.rows.length > 0, name);
    assert.deepStrictEqual(a.rows, b.rows, `${name}: the rows of the first field (${b.dom})`);
    assert.deepStrictEqual(part.peersOf(i), full.peersOf(i), `${name}: similar municipios`);
  }
});
