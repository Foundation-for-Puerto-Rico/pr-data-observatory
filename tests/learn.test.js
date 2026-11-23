// Tests for the Learn page's script and the link that opens a map tool (site/js/learn_page.js, site/js/app.js MT_LINK; docs/learn.md, HANDOFF decision 106).
// Run: node --test tests/learn.test.js
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const SITE = path.join(__dirname, '..', 'site');
const read = (f) => fs.readFileSync(path.join(SITE, f), 'utf8');
const V = require(path.join(SITE, 'js', 'core', 'viewstate.js'));
const LEARN = (() => { const js = read('js/learn_items.js'); return JSON.parse(js.slice(js.indexOf('{'), js.lastIndexOf('}') + 1)); })();

const GAUGES = { features: [[-66.0, 18.0], [-66.1, 18.0], [-66.5, 18.2]].map(c => ({ geometry: { type: 'Point', coordinates: c } })) };   // three gauges: 10.6 km, 10.6 km and far away

// learn_page.js run on a page that is only its named elements: what it writes into each is what a visitor reads
function page(lang) {
  const els = {};
  const el = (id) => (els[id] = els[id] || { id, innerHTML: '', textContent: '', href: '' });
  const fmt = (n, d = 0) => Number(n).toLocaleString('en-US', { minimumFractionDigits: d, maximumFractionDigits: d });
  const fill = (s, v) => String(s).replace(/\{(\w+)\}/g, (m, k) => (v && k in v ? v[k] : m));
  const handlers = {};
  const ctx = {
    window: { LEARN, I18N: { lang }, addEventListener: () => {} }, I18N: { lang }, location: { hash: '' },
    document: { getElementById: el, querySelector: () => null, addEventListener: (type, fn) => { handlers[type] = fn; } },
    T: (k, v) => fill(k, v), Th: (k, v) => fill(k, v), Tn: (n, one, other) => fill(n === 1 ? one : other, { n }),
    fetchJson: () => Promise.resolve(GAUGES),
    fmt, esc: (s) => String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;'),
  };
  ctx.window.Core = undefined;
  vm.runInNewContext(read('js/learn_page.js'), ctx);
  const press = (data) => handlers.click({ target: { closest: () => ({ dataset: data }) } });
  return { els, press, fmt };
}

test('the page draws a card for each built lesson, in its language, and says how many more are planned', () => {
  for (const lang of ['en', 'es']) {
    const { els } = page(lang);
    const cards = els.lnCards.innerHTML;
    assert.strictEqual((cards.match(/<a class="ln-card"/g) || []).length, LEARN.lessons.length);
    for (const l of LEARN.lessons) {
      assert.ok(cards.includes(`href="#lesson-${l.id}"`) && cards.includes(`<use href="#lg-${l.id}"/>`), l.id);
      assert.ok(cards.includes(`<b>${l.title[lang]}</b>`), `${l.id}: its title in ${lang}`);
      for (const t of l.tools) assert.ok(cards.includes(t[lang]), `${l.id}: the tool's name in ${lang}`);
    }
    if (LEARN.planned) assert.match(els.lnMore.textContent, new RegExp(`^${LEARN.planned} more lessons are planned\\.$`));
    else assert.strictEqual(els.lnMore.textContent, '', 'every lesson is built: no "planned" line');
  }
});

test('Layers and shapes quotes the layers\' own counts', () => {
  const { els, fmt } = page('en');
  const s = LEARN.figures.shapes, h = els.lnShapesFig.innerHTML;
  for (const n of [s.points, s.lines, s.barrios, s.municipios, s.cells_across, s.cells_down]) assert.ok(h.includes(fmt(n)), String(n));
  assert.match(els.lnShapesTry.href, /^index\.html#c=[\d.]+,-[\d.]+,14&l=places,watersheds,barrios,surfheat$/);
});

test('Counts and rates: the two orders, with the two municipios the text follows kept in view', () => {
  const { els, press, fmt } = page('en');
  const r = LEARN.figures.rates;
  let h = els.lnRatesFig.innerHTML;
  assert.ok(h.includes('aria-pressed="true">A count<'), 'opens on the count');
  const first = (html) => /<li class="ln-row[^"]*"><span class="ln-rank">1<\/span><span class="ln-name">([^<]+)</.exec(html)[1];
  assert.strictEqual(first(h), r.top_count.name);
  assert.ok(h.includes(`<span class="ln-rank">${r.top_rate.rank_by_count}</span><span class="ln-name">${r.top_rate.name}</span>`), 'the highest rate is shown at its rank by count');
  assert.ok(h.includes(fmt(r.top_count.count)) && h.includes(fmt(r.top_rate.rate, 1)));
  press({ rates: 'rate' });
  h = els.lnRatesFig.innerHTML;
  assert.ok(h.includes('aria-pressed="true">Per 1,000 residents<'));
  assert.strictEqual(first(h), r.top_rate.name);
  assert.ok(h.includes(`<span class="ln-rank">${r.top_count.rank_by_rate}</span><span class="ln-name">${r.top_count.name}</span>`), 'the highest count is shown at its rank by rate');
  assert.strictEqual((h.match(/class="ln-row/g) || []).length, 8 + (r.top_count.rank_by_rate > 8 ? 1 : 0), 'eight rows, and the followed municipio when it is further down');
});

test('What is near: a distance shows its own figures, every distance is in the table, and the links open the tool at the plaza', () => {
  const { els, press, fmt } = page('en');
  const n = LEARN.figures.near;
  let h = els.lnNearFig.innerHTML;
  const def = n.rings.findIndex(r => r.m === 800);
  assert.ok(h.includes(`data-ring="${def}" aria-pressed="true"`), 'opens on 800 m, the tool\'s own first distance');
  for (const r of n.rings) assert.ok(h.includes(`<td>${fmt(r.places)}</td><td>${fmt(r.residents)}</td><td>${fmt(r.km2, 1)}</td>`), `${r.m} m is in the table`);
  assert.ok(h.includes('<b>4 times</b>'), 'twice the distance, four times the area');
  press({ ring: '0' });
  h = els.lnNearFig.innerHTML;
  assert.ok(h.includes('data-ring="0" aria-pressed="true"') && h.includes('This is the shortest distance.'));
  assert.ok(h.includes(`<b>${fmt(n.rings[0].places)}</b>`));
  assert.strictEqual(els.lnNearTry.href, `index.html#c=${n.lat},${n.lng},16&l=places&mt=b:study:saAroundH`);
  assert.strictEqual(els.lnNearRings.href, `index.html#c=${n.lat},${n.lng},16&l=stops,rings`);
});

test('step 5: the tools\' own limits, the parts of a GEOID, and every lesson has a card', () => {
  const { els, fmt } = page('en');
  const F = LEARN.figures;
  let h = els.lnOwndataFig.innerHTML;
  assert.ok(h.includes(`up to ${fmt(F.owndata.max_points)} points`) && h.includes(`"fewer than ${fmt(F.owndata.min_shown)}"`));
  h = els.lnQgisFig.innerHTML;
  assert.ok(h.includes(`<b>${F.qgis.geoid.state}</b>`) && h.includes(`<b>${F.qgis.geoid.subdivision}</b>`) && h.includes('EPSG:32161'));
  assert.strictEqual(LEARN.planned, 0);
  assert.strictEqual(els.lnMore.textContent, '', 'no "more lessons are planned" line once all are built');
});

test('step 4: two sizes of area, a correlation at each, and what is counted and not drawn', () => {
  const { els, fmt } = page('en');
  const F = LEARN.figures;
  let h = els.lnAreasizeFig.innerHTML;
  assert.ok(h.includes(`<b>${F.areasize.spread.municipality}</b>`) && h.includes(`${fmt(F.areasize.barrio.above)} barrios are above`));
  assert.ok(!h.includes(F.areasize.spread.high.barrio), 'the barrios of the widest spread are not named');
  h = els.lnCauseFig.innerHTML;
  assert.strictEqual((h.match(/<circle /g) || []).length, F.cause.muni.points.filter(p => p[0] != null && p[1] != null).length, 'one dot for each municipio');
  assert.ok(h.includes(`<b>r = ${fmt(F.cause.muni.r, 2)}</b>`) && h.includes(`<b>r = ${fmt(F.cause.barrio.r, 2)}</b>`));
  h = els.lnLeftoutFig.innerHTML;
  assert.ok(h.includes(`<b>${fmt(F.leftout.withheld)}</b>`) && h.includes(fmt(F.leftout.reasons.holiday_rental)));
});

test('step 3: a barrio\'s row, the points in no barrio, the classes by method and the margins by size', () => {
  const { els, press, fmt } = page('en');
  const F = LEARN.figures;
  let h = els.lnAttributesFig.innerHTML;
  assert.ok(h.includes(`<b>${F.attributes.barrio}</b>`) && h.includes(F.attributes.geoid) && h.includes(`${fmt(F.attributes.residents[0])} ± ${fmt(F.attributes.residents[1])}`));
  h = els.lnRelationsFig.innerHTML;
  assert.ok(h.includes(`<b>${fmt(F.relations.in_barrio)}</b>`) && h.includes(`<b>${fmt(F.relations.loose)}</b>`) && h.includes(`${fmt(F.relations.median_m)} m`));
  h = els.lnClassesFig.innerHTML;
  assert.ok(h.includes('data-classes="quantile" aria-pressed="true"'));
  assert.strictEqual((h.match(/<circle /g) || []).length, F.classes.n, 'one dot for each municipio');
  press({ classes: 'equal' });
  h = els.lnClassesFig.innerHTML;
  assert.ok(h.includes('data-classes="equal" aria-pressed="true"'));
  F.classes.methods.equal.counts.forEach(n => assert.ok(h.includes(`<td>${fmt(n)}</td>`)));
  h = els.lnSureFig.innerHTML;
  assert.ok(h.includes(`<b>${F.sure.window}</b>`) && h.includes(`<td>${fmt(F.sure.barrio.flagged)}</td>`) && h.includes(F.sure.small.barrio));
  const R = require(path.join(SITE, 'js', 'core', 'reliability.js'));
  assert.strictEqual(R.MOE_SHARE, 0.3, 'learn.py flags with the map\'s own share');
});

test('step 2: the count by barrio, the overlay, the walk beside its ring, the gauges and the hexagons', async () => {
  const { els, press, fmt } = page('en');
  const F = LEARN.figures;
  let h = els.lnCountFig.innerHTML;
  assert.ok(h.includes(`<b>${fmt(F.count.mean, 1)}</b>`) && h.includes(`<b>${fmt(F.count.median)}</b>`) && h.includes(F.count.max_barrio));
  assert.strictEqual((h.match(/class="ln-row"/g) || []).length, F.count.hist.length, 'one bar for each class');
  assert.ok(h.includes('>none<') && h.includes(`>${fmt(F.count.bins[F.count.bins.length - 1])} or more<`));
  h = els.lnOverlayFig.innerHTML;
  assert.ok(h.includes('data-overlay="flood" aria-pressed="true"') && h.includes(`<b>${fmt(F.overlay.flood.inside)}</b>`) && h.includes(F.overlay.flood.top[0][0]));
  press({ overlay: 'protected' });
  h = els.lnOverlayFig.innerHTML;
  assert.ok(h.includes('data-overlay="protected" aria-pressed="true"') && h.includes(`<b>${fmt(F.overlay.protected.inside)}</b>`) && h.includes('inside a protected area'));
  h = els.lnNetworkFig.innerHTML;
  const ten = F.walk.steps.find(s => s.min === 10);
  assert.ok(h.includes('data-walk="1" aria-pressed="true"') && h.includes(`<b>${fmt(ten.residents)}</b>`) && h.includes(fmt(ten.ring_residents)), 'opens on 10 minutes, with the ring beside it');
  press({ walk: '3' });
  const twenty = F.walk.steps[3];
  assert.ok(els.lnNetworkFig.innerHTML.includes(`<b>${fmt(twenty.residents)}</b>`));
  assert.strictEqual(els.lnWalkTry.href, `index.html#c=${F.walk.lat},${F.walk.lng},15&mt=b:study:saWalkH`);
  h = els.lnConcentrateFig.innerHTML;
  assert.ok(h.includes(`<b>${fmt(F.hex.cells)}</b>`) && h.includes(`<b>${fmt(F.hex.half_cells)}</b>`));
  await new Promise(r => setTimeout(r, 20));   // the gauges are read from their own file
  h = els.lnBetweenFig.innerHTML;
  assert.ok(h.includes('<b>3</b> rain gauges') && h.includes(`one gauge for every <b>${fmt(F.land_km2 / 3)}</b> km`), 'counted from the file, not typed');
  assert.match(h, /nearest other gauge is 10\.6 km away/);
});

test('the glossary pop-up links to the lesson that teaches the term, when there is one', () => {
  const G = require(path.join(SITE, 'js', 'core', 'glossary.js'));
  global.T = (k, v) => String(k).replace(/\{(\w+)\}/g, (m, x) => (v && x in v ? v[x] : m));
  const d = ['Buffer', '', 'The area within a set distance.', 'QGIS', 'https://docs.qgis.org/', '2026-11-09', 0];
  const withLesson = G.tipHtml(d, 'buffer', { lesson: ['near', 'What is near'] });
  assert.match(withLesson, /<p class="gl-lesson"><a href="learn\.html#lesson-near">Lesson: What is near<\/a><\/p>/);
  assert.ok(!G.tipHtml(d, 'buffer', {}).includes('gl-lesson'), 'no link for a term no lesson teaches');
  delete global.T;
});

test('mt= opens a map tool once: read by the map before it rewrites its address, never written back, and only for a tool the pane has', () => {
  assert.ok(V.ONCE.has('mt'));
  assert.strictEqual(V.write('2d', '#c=18,-66,9&l=places&mt=b:study:saAroundH', { c: V.cOf(18.1, -66.2, 10) }), '#c=18.1000,-66.2000,10&l=places', 'mt= is dropped when the map writes its address');
  const app = read('js/app.js');
  const re = /const MT_LINK = \((\/.+?\/)\.exec\(location\.hash\)/.exec(app);
  assert.ok(re, 'app.js reads mt= from the address as it came');
  const rx = eval(re[1]);
  const got = (h) => (rx.exec(h) || [])[1] || null;
  assert.strictEqual(got('#c=18,-66,16&l=places&mt=b:study:saAroundH'), 'b:study:saAroundH');
  assert.strictEqual(got('#mt=l:lySlope'), 'l:lySlope');
  assert.strictEqual(got('#Ponce&format=x'), null, 'a key that only ends in mt is not the request');
  assert.strictEqual(got('#mt=<img src=x>'), null, 'only the characters a tool code has');
  assert.match(app, /function openToolLink\(spec\) \{\s*if \(!Array\.from\(document\.querySelectorAll\('#tab-maptools \[data-mt\]'\)\)\.some\(b => b\.dataset\.mt === spec\)\) return;/, 'a code no button has opens nothing');
  assert.match(app, /performance\.mark\('ready'\);[^\n]*\n\s*if \(MT_LINK\) openToolLink\(MT_LINK\);/, 'the tool opens once the map is ready');
  const tools = new Set(Array.from(read('index.html').matchAll(/class="mt-tool" data-mt="([^"]+)"/g), m => m[1]));
  for (const l of LEARN.lessons) for (const t of l.tools) assert.ok(tools.has(t.mt), `${l.id}: ${t.mt} is a tool of the map`);
});

test('the help texts load on a map where the Analysis engine has not loaded (no global TK), and leave no TK behind for economy.js to trip on', () => {
  const HELP = {}, ctx = { HELP, T: (s) => s, Object };
  vm.runInNewContext(read('js/help.js'), ctx);
  assert.strictEqual(HELP.flood[0], 'Flood zones');
  assert.strictEqual(vm.runInContext('typeof TK', vm.createContext(ctx)), 'undefined', 'TK stays inside help.js');
  assert.match(read('js/app.js'), /js\/help\.js\?v=12/);
});
