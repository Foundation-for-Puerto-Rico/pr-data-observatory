// Tests for the Data management page's own logic (site/js/datamgmt.js: DM) and its agreement with data/registry.json. Run: node --test tests/datamgmt.test.js
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');

const DM = require(path.join(__dirname, '..', 'site', 'js', 'datamgmt.js'));
const REG = JSON.parse(fs.readFileSync(path.join(__dirname, '..', 'site', 'data', 'registry.json'), 'utf8'));

const rows = [
  { file: 'b.json', kind: 'data', records: 10, fields: 2, values: 20, vertices: null, bytes: 100, documented_by: 2, first_published: '2026-10-01', last_updated: '2026-10-05', review: { status: 'cleared', cleared: '2026-10-18' } },
  { file: 'a.json', kind: 'data', records: 5, fields: 1, values: 5, vertices: 7, bytes: 50, documented_by: 1, first_published: '2026-10-02', last_updated: '2026-10-19', review: { status: 'open' } },
  { file: 'd.json', kind: 'documentation', records: null, fields: null, values: null, vertices: null, bytes: 30, documented_by: 0, first_published: '2026-10-05', last_updated: '2026-10-05', review: { status: 'none' } },
  { file: 'c.json', kind: 'data', records: 10, fields: 3, values: 1, vertices: null, bytes: 70, documented_by: 0, first_published: '2026-10-01', last_updated: '2026-10-01', review: { status: 'cleared', cleared: '2026-10-19' } },
];

test('numbers sort in both directions, with the files that have no value last and ties in file order', () => {
  assert.deepStrictEqual(DM.sortRows(rows, f => f.values, 'desc').map(f => f.file), ['b.json', 'a.json', 'c.json', 'd.json']);
  assert.deepStrictEqual(DM.sortRows(rows, f => f.values, 'asc').map(f => f.file), ['c.json', 'a.json', 'b.json', 'd.json']);
  assert.deepStrictEqual(DM.sortRows(rows, f => f.records, 'desc').map(f => f.file), ['b.json', 'c.json', 'a.json', 'd.json'], 'b and c tie: file order');
  assert.deepStrictEqual(DM.sortRows(rows, f => f.last_updated, 'desc').map(f => f.file), ['a.json', 'b.json', 'd.json', 'c.json'], 'dates sort as dates');
});

test('the compliance column puts open reviews first, then the latest clearances, then what needs nothing', () => {
  assert.deepStrictEqual(DM.sortRows(rows, DM.reviewKey, 'asc').map(f => f.file), ['a.json', 'c.json', 'b.json', 'd.json']);
  assert.ok(DM.RANK.open < DM.RANK.unstated && DM.RANK.unstated < DM.RANK.cleared && DM.RANK.cleared < DM.RANK.none);
});

test('the totals row adds the counted files, the size of every file and spans the dates', () => {
  assert.deepStrictEqual(DM.totalsOf(rows), { files: 4, counted: 3, records: 25, fields: 6, values: 26, vertices: 7, bytes: 250, documented_by: 3, first_published: '2026-10-01', last_updated: '2026-10-19' });
  assert.deepStrictEqual(DM.totalsOf([]), { files: 0, counted: 0, records: 0, fields: 0, values: 0, vertices: 0, bytes: 0, documented_by: 0, first_published: null, last_updated: null });
});

test('the totals of every row are the registry totals', () => {
  const t = DM.totalsOf(REG.files);
  for (const k of ['records', 'fields', 'values', 'bytes']) assert.strictEqual(t[k], REG.totals[k], k);
  assert.strictEqual(t.files, REG.totals.files);
  assert.strictEqual(t.counted, REG.totals.counted_files);
  assert.strictEqual(t.first_published, REG.totals.first_published);
  assert.strictEqual(t.last_updated, REG.totals.last_updated);
});

test('the review filter: "License not stated" keeps every file of that class, with or without a review', () => {
  assert.ok(DM.reviewMatch({ status: 'unstated', flags: ['licence-unstated'] }, 'unstated'));
  assert.ok(DM.reviewMatch({ status: 'open', flags: ['counts-only', 'licence-unstated'] }, 'unstated'));
  assert.ok(!DM.reviewMatch({ status: 'cleared', flags: [] }, 'unstated'));
  assert.ok(DM.reviewMatch({ status: 'cleared', flags: ['federal-grant'] }, 'federal-grant') && !DM.reviewMatch({ status: 'cleared', flags: [] }, 'federal-grant'));
  assert.ok(DM.reviewMatch({ status: 'open', flags: [] }, 'open') && !DM.reviewMatch({ status: 'none', flags: [] }, 'open'));
  const unstated = REG.files.filter(f => f.licence_class === 'unstated').length;
  assert.strictEqual(REG.files.filter(f => DM.reviewMatch(f.review, 'unstated')).length, unstated);
});

test('the growth note: what never fell, and the largest fall of the size', () => {
  const H = [{ date: 'a', files: 1, records: 5, fields: 2, values: 9, items: null, bytes: 100 }, { date: 'b', files: 2, records: 6, fields: 2, values: 9, items: 3, bytes: 80 }, { date: 'c', files: 2, records: 7, fields: 3, values: 12, items: 4, bytes: 70 }];
  assert.deepStrictEqual(DM.growthFacts(H), { grew: true, fell: [], drop: { date: 'b', bytes: 20 } });
  H.push({ date: 'd', files: 1, records: 7, fields: 3, values: 10, items: 4, bytes: 90 });
  assert.deepStrictEqual(DM.growthFacts(H).fell, ['files', 'values']);
  const real = DM.growthFacts(REG.history);
  // Records and values can fall, as when 6 care homes left the LIHTC layer (HANDOFF decision 84), though the history keeps one row per day, so a fall
  // on a day that also gains data (2026-11-06: the disaster recovery file, decision 89) does not show. Fields and items fell once, on 2026-11-23, when the
  // licensed short-term rental figures and their four dictionary entries were removed; files never fell
  assert.ok(real.fell.every((k) => ['records', 'values', 'fields', 'items'].includes(k)), `in the published history files may not fall, but ${real.fell.join(', ')} did`);
  assert.ok(real.drop && real.drop.date === '2026-10-09', 'the size fell on 2026-10-09');
});

test('a CSV cell is quoted when it must be and a formula is not run', () => {
  assert.strictEqual(DM.csvCell('a,b'), '"a,b"');
  assert.strictEqual(DM.csvCell('say "x"'), '"say ""x"""');
  assert.strictEqual(DM.csvCell('=1+1'), "'=1+1");
  assert.strictEqual(DM.csvCell(-5), '-5', 'a number is not a formula');
  assert.strictEqual(DM.csvCell(null), '');
  assert.strictEqual(DM.csvText(['a', 'b'], [[1, 'x,y']]), '﻿a,b\n1,"x,y"');
});

test('axis ticks are clean steps from zero past the maximum', () => {
  assert.deepStrictEqual(DM.ticks(3520446), [0, 1e6, 2e6, 3e6, 4e6]);
  assert.deepStrictEqual(DM.ticks(77), [0, 20, 40, 60, 80]);
  assert.deepStrictEqual(DM.ticks(0), [0, 1]);
  for (const m of [1, 9, 13, 865, 80681114]) { const t = DM.ticks(m); assert.ok(t[t.length - 1] >= m && t[0] === 0, String(m)); }
});

test('a step line holds each total until the next date', () => {
  assert.strictEqual(DM.stepPath([[0, 10], [5, 4], [9, 2]]), 'M0.0,10.0H5.0V4.0H9.0V2.0');
  assert.strictEqual(DM.dayNo('2026-10-19') - DM.dayNo('2026-10-01'), 18);
});

test('the growth history is in date order, one row per date', () => {
  const d = REG.history.map(h => h.date);
  assert.deepStrictEqual(d, [...new Set(d)].sort());
  assert.ok(REG.history.every(h => h.values >= 0 && h.files > 0));
});

test('the category filter keeps a domain and its sub-domains, and offers only the domains that have a file', () => {
  assert.ok(DM.domainMatch(['economy.visitor-economy', 'hazards'], 'economy'), 'a sub-domain is in its parent');
  assert.ok(DM.domainMatch(['economy.visitor-economy'], 'economy.visitor-economy'));
  assert.ok(!DM.domainMatch(['economy'], 'economy.visitor-economy'), 'a parent is not in its sub-domain');
  assert.ok(!DM.domainMatch(['environment.land'], 'environment-x') && !DM.domainMatch(['public-money'], 'public'), 'a name that only starts the same does not match');
  assert.ok(DM.domainMatch(['housing'], '') && DM.domainMatch(undefined, ''), 'no choice keeps every file');
  assert.ok(!DM.domainMatch(undefined, 'housing'));
  const files = [{ domains: ['economy.visitor-economy'] }, { domains: ['economy', 'housing'] }, { domains: ['housing'] }];
  assert.deepStrictEqual(DM.domainOptions(files, { population: {}, economy: {}, 'economy.visitor-economy': {}, housing: {} }),
    [{ id: 'economy', depth: 0, n: 2 }, { id: 'economy.visitor-economy', depth: 1, n: 1 }, { id: 'housing', depth: 0, n: 2 }]);
});

test('on the registry: every file falls in a category, every domain a file carries has a name, and the choices follow the registry order', () => {
  const opts = DM.domainOptions(REG.files, REG.domain_names), ids = opts.map(o => o.id);
  for (const f of REG.files) {
    assert.ok((f.domains || []).length, f.file + ' has a domain');
    for (const d of f.domains) assert.ok(REG.domain_names[d], f.file + ': ' + d + ' has a name');
    assert.ok(opts.some(o => DM.domainMatch(f.domains, o.id)), f.file + ' is found under a category');
  }
  assert.deepStrictEqual(ids, Object.keys(REG.domain_names).filter(id => ids.includes(id)), 'the order of the registry');
  for (const o of opts) assert.strictEqual(o.n, REG.files.filter(f => DM.domainMatch(f.domains, o.id)).length);
  const html = fs.readFileSync(path.join(__dirname, '..', 'site', 'data-management.html'), 'utf8');
  assert.match(html, /<select id="dmDom"><option value="">All categories<\/option><\/select>/, 'the page has the filter, with no domain written into it');
});

test('the "Sort by" list: every choice names a column of the table and a direction, and the first one is the order the page opens in', () => {
  assert.deepStrictEqual(DM.sortParse('last_updated:desc'), { sort: 'last_updated', dir: 'desc' });
  assert.strictEqual(DM.sortParse(''), null);
  assert.strictEqual(DM.sortParse('file:up'), null);
  assert.strictEqual(DM.sortChoice('bytes', 'asc'), 'bytes:asc');
  const html = fs.readFileSync(path.join(__dirname, '..', 'site', 'data-management.html'), 'utf8');
  const js = fs.readFileSync(path.join(__dirname, '..', 'site', 'js', 'datamgmt.js'), 'utf8');
  const list = /<select id="dmSort">(.*?)<\/select>/.exec(html)[1];
  const values = [...list.matchAll(/<option value="([^"]*)"/g)].map(m => m[1]);
  assert.strictEqual(values[0], 'values:desc', 'the opening order');
  assert.strictEqual(new Set(values).size, values.length);
  for (const v of values.filter(Boolean)) {
    const c = DM.sortParse(v);
    assert.ok(c, v);
    assert.ok(js.includes(`{ k: '${c.sort}',`), v + ' is a column of the table');
  }
  for (const v of ['last_updated:desc', 'last_updated:asc', 'first_published:desc', 'first_published:asc']) assert.ok(values.includes(v), v);
  const old = { file: 'a', last_updated: '2026-01-05' }, mid = { file: 'b', last_updated: '2026-06-01' }, neu = { file: 'c', last_updated: '2026-11-11' };
  assert.deepStrictEqual(DM.sortRows([mid, neu, old], f => f.last_updated, 'desc').map(f => f.file), ['c', 'b', 'a'], 'newest first');
  assert.deepStrictEqual(DM.sortRows([mid, neu, old], f => f.last_updated, 'asc').map(f => f.file), ['a', 'b', 'c'], 'oldest first');
});

test('the "Show on the map" link: the layers of a file switched on, its first dataset shaded, nothing for a file the map does not draw', () => {
  assert.strictEqual(DM.mapHref({ l: 'flood,slr' }), 'index.html#l=flood,slr');
  assert.strictEqual(DM.mapHref({ e: 'poverty_pct', n: 38 }), 'index.html#e=poverty_pct.f');
  assert.strictEqual(DM.mapHref({ l: 'reservoirs', e: 'water_systems', n: 2 }), 'index.html#l=reservoirs&e=water_systems.f');
  assert.strictEqual(DM.mapHref(undefined), null);
  assert.strictEqual(DM.mapHref({}), null);
  assert.strictEqual(DM.mapHref({ l: 'flood&ask=x', e: 'a.b,c' }), null, 'a key that could add a part to the address is left out');
  const vs = require('../site/js/core/viewstate.js'), index = fs.readFileSync(path.join(__dirname, '..', 'site', 'index.html'), 'utf8');
  let n = 0;
  for (const f of REG.files) {
    const h = DM.mapHref(f.map);
    if (!f.map) continue;
    n++;
    assert.ok(h, f.file + ' has a link');
    for (const k of (f.map.l || '').split(',').filter(Boolean)) {
      assert.ok(vs.LAYERS[k] && vs.LAYERS[k]['2d'], f.file + ': ' + k + ' is a layer of the 2D map');
      assert.ok(index.includes('id="' + vs.LAYERS[k]['2d'] + '"'), f.file + ': the map has the switch of ' + k);
    }
    if (f.map.e) assert.ok(f.map.n >= 1 && /^[A-Za-z0-9_]+$/.test(f.map.e), f.file);
  }
  assert.ok(n >= 20, 'the registry says how the map shows its files (' + n + ')');
});
