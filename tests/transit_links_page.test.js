// The Connections between municipios page's arithmetic (site/js/transit_links_page.js) and the files it and the two map layers read (transit_links.py,
// decision 105): the pairs add up to Puerto Rico's totals, the filters and the tally agree with the file, the page's statuses are the file's, the layers are
// in the shared list with a style the two maps can draw, and the page says it is a simulation.
'use strict';
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');

globalThis.T = (s) => s;
require(path.join(__dirname, '..', 'site', 'js', 'transit_links_page.js'));
const P = globalThis.TransitLinksPage;
const site = path.join(__dirname, '..', 'site');
const read = (f) => JSON.parse(fs.readFileSync(path.join(site, 'data', f), 'utf8'));
const D = read('transit_links.json'), L = read('simulated_links.geojson'), PUB = read('publicos.geojson');

test('the pairs: the page reads every pair, and its tally by status is the file\'s', () => {
  const all = P.pairs(D), t = P.tally(all);
  assert.strictEqual(all.length, D.pr.pairs);
  assert.deepStrictEqual(P.ORDER, D.rules.statuses, 'the page knows every status the file can hold');
  for (const k of P.ORDER) {
    assert.ok(P.STATUS[k] && P.STATUS[k].label && /^#[0-9a-f]{6}$/i.test(P.STATUS[k].color), k);
    assert.deepStrictEqual(t[k], { pairs: D.pr.by_status[k].pairs, workers: D.pr.by_status[k].workers }, k);
  }
  assert.strictEqual(all.reduce((s, p) => s + p.workers, 0), D.pr.other_municipio);
});

test('the filters: one municipio, one status, and the sort', () => {
  const all = P.pairs(D), ms = P.munis(D);
  assert.strictEqual(ms.length, 78);
  const sj = ms.find(m => m.name === 'San Juan').geoid;
  const mine = P.select(all, sj, '', ['workers', -1]);
  assert.ok(mine.length > 50 && mine.every(p => p.a === sj || p.b === sj));
  assert.deepStrictEqual(mine.map(p => p.workers), mine.map(p => p.workers).sort((a, b) => b - a), 'most workers first');
  const m = ms.find(x => x.geoid === sj);
  assert.strictEqual(mine.reduce((s, p) => s + p.workers, 0), m.work_elsewhere + m.come_in, 'a municipio\'s pairs hold everyone who leaves it or comes in to work');
  const none = P.select(all, sj, 'none');
  assert.ok(none.length && none.every(p => p.status === 'none'));
  assert.strictEqual(P.select(all, '', 'timetable').length, D.pr.by_status.timetable.pairs);
  const byKm = P.select(all, sj, '', ['km', 1]).filter(p => p.km != null).map(p => p.km);
  assert.deepStrictEqual(byKm, byKm.slice().sort((a, b) => a - b));
});

test('the simulated connections of the layer are the pairs the page ranks', () => {
  const sims = P.pairs(D).filter(p => p.sim);
  assert.strictEqual(L.features.length, sims.length);
  assert.strictEqual(L.features.length, D.pr.simulated);
  assert.ok(sims.every(p => p.workers >= D.rules.sim_min_workers && !p.low && (p.status === 'none' || p.status === 'publico')));
  assert.ok(L.features.every(f => f.properties.c === 1 || f.properties.c === 2));
});

test('the two layers are in the shared list, drawn as lines, and their texts say what they are', () => {
  globalThis.Core = { text: require(path.join(site, 'js', 'core', 'text.js')) };
  const F = require(path.join(site, 'js', 'core', 'facilities.js'));
  assert.strictEqual(F.LAYERS.links.file, 'simulated_links.geojson');
  assert.strictEqual(F.LAYERS.publicos.file, 'publicos.geojson');
  const wide = F.lineStyle('links', { c: 1, workers: 7500 }), thin = F.lineStyle('links', { c: 2, workers: 500 }), more = F.lineStyle('links', { c: 1, workers: 90000 });
  assert.strictEqual(wide.color, F.LAYERS.links.line.colors[1]);
  assert.strictEqual(thin.color, F.LAYERS.links.line.colors[2]);
  assert.notStrictEqual(wide.color, thin.color);
  assert.ok(wide.weight > thin.weight && thin.weight >= 2 && wide.weight <= 9 && more.weight === wide.weight, 'wider where more workers travel, within the layer\'s limits');
  assert.ok(Array.isArray(wide.dash), 'a simulated connection is dashed');
  assert.strictEqual(P.STATUS.none.color, F.LAYERS.links.line.colors[1], 'the page and the map layer use the same colors');
  assert.strictEqual(P.STATUS.publico.color, F.LAYERS.links.line.colors[2]);
  const pub = F.lineStyle('publicos', {}), fpr = F.lineStyle('fprroutes', {});
  assert.deepStrictEqual([pub.color, pub.dash], [F.LAYERS.publicos.color, null]);
  assert.deepStrictEqual([fpr.color, fpr.weight, fpr.opacity, fpr.dash], [F.LAYERS.fprroutes.color, 3.5, 0.9, null], 'the older line layer is drawn as before');
  for (const f of L.features.concat(PUB.features)) assert.ok(F.TYPES.includes(f.properties.type), f.properties.type);
  const pop = F.popup('links', L.features[0].properties, L);
  assert.match(pop, /A simulation, not a proposed route\./);
  assert.match(pop, /transit-links\.html/);
  assert.match(F.noteText('links', L, ''), /A simulation, not proposed routes\./);
  assert.match(F.HELP_TEXT.fac_links[1], /not a proposed route/);
  assert.match(F.popup('publicos', PUB.features[0].properties, PUB), /it may no longer run/);
  assert.match(F.legendHtml('links'), /No route listed/);
});

test('the page: its sections, the notice that it proposes no route, and the layers it links to', () => {
  const html = fs.readFileSync(path.join(site, 'transit-links.html'), 'utf8');
  for (const id of ['now', 'links', 'pairs', 'municipios', 'reading', 'method', 'sources']) assert.match(html, new RegExp(`id="${id}"`), id);
  assert.doesNotMatch(html, /id="map"/, 'twin.css styles #map as the main page\'s map');
  assert.match(html, /It is not a proposed route, a service plan or a demand forecast/);
  assert.match(html, /noindex/);
  assert.match(html, /index\.html#l=links/);
  assert.match(html, /data-ka="tlinks"/);
  const p = D.pr;
  assert.ok(html.includes(p.other_municipio.toLocaleString('en-US')), 'the lede carries the file\'s figure');
});

test('the traffic layer: classes by vehicles a day, wider where more vehicles pass, a solid legend and a pop-up with the count and its year', () => {
  globalThis.Core = { text: require(path.join(site, 'js', 'core', 'text.js')) };
  const F = require(path.join(site, 'js', 'core', 'facilities.js'));
  const TR = read('traffic_roads.geojson');
  assert.strictEqual(F.LAYERS.traffic.file, 'traffic_roads.geojson');
  const busy = F.lineStyle('traffic', { c: 6, a: 120000 }), quiet = F.lineStyle('traffic', { c: 1, a: 800 });
  assert.strictEqual(busy.color, F.LAYERS.traffic.line.colors[6]);
  assert.ok(busy.weight > quiet.weight && busy.dash === null);
  assert.doesNotMatch(F.legendHtml('traffic'), /dashed/);
  assert.match(F.legendHtml('links'), /dashed/);
  const p = TR.features[TR.features.length - 1].properties, pop = F.popup('traffic', p, TR);
  assert.match(pop, /count or estimate of \{y\}/, 'the pop-up gives the year of the count (T() fills it on the page)');
  assert.match(pop, new RegExp(p.r));
  assert.match(F.tip('traffic', p), /vehicles a day/);
  assert.strictEqual(F.tip('pubhousing', { name: 'x' }), null, 'a point layer keeps its name as the hover text');
  assert.match(F.noteText('traffic', TR, ''), /stretches/);
  const L = read('simulated_links.geojson'), q = L.features[0].properties;
  assert.match(F.popup('links', q, L), /vehicles a day at the middle count/);
});

test('road deaths along a simulated connection: in the pop-up and per 10 km on the page, never added up', () => {
  globalThis.Core = { text: require(path.join(site, 'js', 'core', 'text.js')) };
  const F = require(path.join(site, 'js', 'core', 'facilities.js'));
  const L = read('simulated_links.geojson');
  assert.match(F.popup('links', L.features[0].properties, L), /people were killed in crashes within 100 m/);
  const ps = P.pairs(D).filter(p => p.sim);
  assert.ok(ps.every(p => p.death_km != null && Math.abs(p.death_km - 10 * p.deaths_5y / p.km) < 1e-9));
  assert.ok(P.pairs(D).filter(p => !p.sim).every(p => p.death_km === null));
  const html = fs.readFileSync(path.join(site, 'transit-links.html'), 'utf8');
  assert.match(html, /must not be added up/);
});
