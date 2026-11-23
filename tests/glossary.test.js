// Tests for the in-page glossary (site/js/core/glossary.js; docs/glossary.md). Run: node --test tests/glossary.test.js   (python -m unittest discover runs it too when node is installed)
//  - the matcher: capitals, accents, word edges, file names, the longest form first, white space
//  - the skip rules and the sections, on plain objects that stand for elements (the module reads only tagName, id, classes and attributes)
//  - the first occurrence of each term in each section, and the tooltip's markup
//  - the data: the module builds from the dictionary's glossary exactly what dictionary.py writes in data/glossary_forms_<lang>.json and glossary_defs_<lang>.json
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');
const G = require(path.join(__dirname, '..', 'site', 'js', 'core', 'glossary.js'));
const readData = (f) => JSON.parse(fs.readFileSync(path.join(__dirname, '..', 'site', 'data', f), 'utf8'));
const SRC = JSON.parse(fs.readFileSync(path.join(__dirname, '..', 'dictionary_src', 'glossary.json'), 'utf8'));
const LIST = readData('dictionary_list.json').glossary;

const term = (id, forms, o = {}) => ({ id, term: o.term || id, match: { en: forms, es: o.es || forms }, case_sensitive: !!o.cs, highlight: o.highlight !== false });
const matcher = (terms, lang = 'en') => G.compile(G.formsFrom(terms, lang));
const found = (m, text) => m.find(text).map(([a, b, id]) => [text.slice(a, b), id]);

// ── the matcher ─────────────────────────────────────────────────────────────
test('capitals: a form written in capitals matches only in capitals; case_sensitive makes every form exact; other forms match in any case', () => {
  const m = matcher([term('sfha', ['SFHA', 'flood hazard area']), term('tren', ['Tren Urbano'], { cs: true }), term('moe', ['MOE', 'margin of error'])]);
  assert.deepStrictEqual(found(m, 'The SFHA, the sfha and the Sfha'), [['SFHA', 'sfha']]);
  assert.deepStrictEqual(found(m, 'Flood Hazard Area and FLOOD HAZARD AREA'), [['Flood Hazard Area', 'sfha'], ['FLOOD HAZARD AREA', 'sfha']]);
  assert.deepStrictEqual(found(m, 'Tren Urbano, not tren urbano'), [['Tren Urbano', 'tren']]);
  assert.deepStrictEqual(found(m, 'moe, Moe and MOE'), [['MOE', 'moe']], 'an acronym that is also a word');
  assert.strictEqual(G.formCs({ case_sensitive: false }, 'STR'), true);
  assert.strictEqual(G.formCs({ case_sensitive: false }, 'short-term rental'), false);
  assert.strictEqual(G.formCs({ case_sensitive: false }, 'PM2.5'), true);
  assert.strictEqual(G.formCs({ case_sensitive: false }, 'X'), false, 'one capital is not an acronym');
  assert.strictEqual(G.formCs({ case_sensitive: true }, 'margin'), true);
});

test('Spanish accents: accented letters are letters, capitals with accents match, and a form keeps its accents', () => {
  const m = matcher([term('moe', ['margin of error'], { es: ['MOE', 'margen de error', 'márgenes de error'] }), term('estimate', ['estimate'], { es: ['estimado', 'estimados'] }), term('area', ['area'], { es: ['área'] })], 'es');
  assert.deepStrictEqual(found(m, 'Márgenes de error y MÁRGENES DE ERROR'), [['Márgenes de error', 'moe'], ['MÁRGENES DE ERROR', 'moe']]);
  assert.deepStrictEqual(found(m, 'margenes de error'), [], 'the form has its accent');
  assert.deepStrictEqual(found(m, 'subestimado, estimadoé, estimados'), [['estimados', 'estimate']], 'a letter, accented or not, on either side is part of the word');
  assert.deepStrictEqual(found(m, 'el área, el Área, el ÁREA, la áreas'), [['área', 'area'], ['Área', 'area'], ['ÁREA', 'area']]);
  assert.deepStrictEqual(found(m, 'el áreá'), [], 'a combining accent after the form is part of the word');
});

test('word edges: whole words only, digits count as letters, and punctuation needs no edge', () => {
  const m = matcher([term('rate', ['rate']), term('acs', ['ACS']), term('400', ['400 m rule']), term('geojson', ['GeoJSON', '.geojson'], { cs: false }), term('json', ['JSON', '.json'])]);
  assert.deepStrictEqual(found(m, 'separate rates, a rate, (rate), rate.'), [['rate', 'rate'], ['rate', 'rate'], ['rate', 'rate']]);
  assert.deepStrictEqual(found(m, 'ACS2, 2ACS, ACS-5'), [['ACS', 'acs']], 'a digit touches the form, a hyphen does not');
  assert.deepStrictEqual(found(m, 'the 400 m rule; 1400 m rule'), [['400 m rule', '400']]);
  assert.deepStrictEqual(found(m, 'XGeoJSON and GeoJSONs, but GeoJSON.'), [['GeoJSON', 'geojson']]);
  assert.deepStrictEqual(found(m, 'GeoJSON is not JSON inside'), [['GeoJSON', 'geojson'], ['JSON', 'json']], 'JSON inside GeoJSON is not a match');
});

test('file names: an extension form marks the whole file name, and takes the place of a match inside it', () => {
  const m = matcher([term('geojson', ['GeoJSON', '.geojson']), term('flood', ['flood']), term('bin', ['.bin']), term('json', ['.json'])]);
  assert.deepStrictEqual(found(m, 'read data/flood.geojson (and roads.bin)'), [['data/flood.geojson', 'geojson'], ['roads.bin', 'bin']]);
  assert.deepStrictEqual(found(m, 'a flood map: flood.geojson'), [['flood', 'flood'], ['flood.geojson', 'geojson']]);
  assert.deepStrictEqual(found(m, 'files end in .json'), [['.json', 'json']]);
  assert.deepStrictEqual(found(m, 'dictionary.jsonl'), [], 'an extension is a whole word too');
});

test('the longest form first, and white space of any kind between words', () => {
  const m = matcher([term('bg', ['block group', 'census block group']), term('sfha', ['Special Flood Hazard Area', 'flood hazard area']), term('flood', ['flood']), term('moe', ['margin of error'])]);
  assert.deepStrictEqual(found(m, 'a census block group and a block group'), [['census block group', 'bg'], ['block group', 'bg']]);
  assert.deepStrictEqual(found(m, 'in the Special Flood Hazard Area, a flood hazard area, the flood'), [['Special Flood Hazard Area', 'sfha'], ['flood hazard area', 'sfha'], ['flood', 'flood']]);
  assert.deepStrictEqual(found(m, 'flood hazard areas'), [['flood', 'flood']], 'a longer form that would end inside a word gives way to a shorter one that does not');
  assert.deepStrictEqual(found(m, 'the margin of\n  error and the margin of error'), [['margin of\n  error', 'moe'], ['margin of error', 'moe']]);
});

test('the real glossary: the words Francis named are found in both languages, and a term that is not highlighted never is', () => {
  for (const [lang, text, want] of [
    ['es', 'El margen de error del estimado, por grupo de bloques, en el SFHA; un archivo de datos GeoJSON (flood.geojson); Dominio', ['moe', 'estimate', 'block-group', 'sfha', 'data-file', 'geojson', 'domain-in-the-dictionary']],
    ['en', 'The margin of error of the estimate, by block group, in the SFHA; a GeoJSON data file (flood.geojson); Domain', ['moe', 'estimate', 'block-group', 'sfha', 'geojson', 'data-file', 'domain-in-the-dictionary']]]) {
    const ids = G.compile(readData(`glossary_forms_${lang}.json`).terms).find(text).map(x => x[2]);
    for (const id of want) assert.ok(ids.includes(id), `${lang}: ${id} in ${JSON.stringify(ids)}`);
  }
  const off = SRC.filter(t => !t.highlight);
  assert.ok(off.length > 20);
  const ids = new Set(readData('glossary_forms_en.json').terms.map(t => t[0]));
  for (const t of off) assert.ok(!ids.has(t.id), `${t.id} is not highlighted`);
  const m = G.compile(readData('glossary_forms_en.json').terms);
  assert.deepStrictEqual(m.find('the rate, the share, the layer, the household').filter(x => off.some(t => t.id === x[2])), [], 'highlight: false is never marked by itself');
});

test('not_match: a longer phrase that holds a form but is not the term is read past, with nothing marked', () => {
  const t = Object.assign(term('per-capita', ['per capita', 'per resident'], { es: ['per cápita', 'por residente'] }), { not_match: { es: ['por residente empleado'] } });
  assert.deepStrictEqual(G.formsFrom([t], 'es')[0], ['per-capita', ['per cápita', 'por residente', '!por residente empleado'], [0, 0, 0]]);
  assert.deepStrictEqual(G.formsFrom([t], 'en')[0], ['per-capita', ['per capita', 'per resident'], [0, 0]], 'a language without phrases');
  const m = matcher([t], 'es');
  assert.deepStrictEqual(found(m, 'Empleos por residente empleado; ingreso por residente; Por Residente Empleado'), [['por residente', 'per-capita']]);
  assert.strictEqual(m.size, 2, 'a phrase is not a form');
});

test('the real glossary: GTFS-Realtime is GTFS-RT, and "por residente empleado" is not per capita', () => {
  for (const lang of ['es', 'en']) {
    const m = G.compile(readData(`glossary_forms_${lang}.json`).terms);
    assert.deepStrictEqual(m.find('El archivo GTFS-Realtime de la ATI').filter(x => /gtfs/.test(x[2])).map(x => x[2]), ['gtfs-rt'], lang);
  }
  const es = G.compile(readData('glossary_forms_es.json').terms);
  assert.deepStrictEqual(es.find('Empleos por residente empleado').filter(x => x[2] === 'per-capita'), []);
  assert.deepStrictEqual(es.find('Ingreso por residente').map(x => x[2]), ['per-capita']);
});

// ── the skip rules and the sections ──────────────────────────────────────────
function el(tag, o = {}, parent = null) {
  const cls = Object.assign([...new Set(o.cls || [])], { contains(c) { return this.includes(c); } }), attrs = Object.assign({}, o.attrs);   // a DOMTokenList and a NamedNodeMap, as far as the module reads them
  return { nodeType: 1, tagName: tag.toUpperCase(), id: o.id || '', parentNode: parent, previousElementSibling: o.prev || null, classList: cls, attributes: Object.entries(attrs).map(([name, value]) => ({ name, value })), getAttribute: (a) => a in attrs ? attrs[a] : null };
}
const txt = (s, parent) => ({ nodeType: 3, nodeValue: s, parentNode: parent });
const body = el('body'), html = el('html'); body.parentNode = html;

test('skipped: headings, controls, links, labels, code, the chat, map panes and controls, icons, hidden and opted-out text', () => {
  const p = el('p', {}, body);
  const skip = [el('h2', {}, body), el('h4', {}, el('div', { cls: ['pop'] }, body)), el('button', {}, p), el('a', {}, p), el('input', {}, p), el('select', {}, p), el('label', {}, p), el('summary', {}, el('details', {}, body)),
    el('code', {}, p), el('pre', {}, body), el('span', {}, el('aside', { id: 'chat' }, body)), el('span', { attrs: { translate: 'no' } }, p), el('span', { attrs: { 'data-gloss': 'off' } }, p),
    el('span', { attrs: { 'aria-hidden': 'true' } }, p), el('span', { cls: ['ms-icon'] }, p), el('span', { cls: ['sr-only'] }, p), el('span', { attrs: { role: 'button' } }, p), el('div', { attrs: { role: 'tab' } }, body),
    el('div', { cls: ['leaflet-control'] }, el('div', { cls: ['leaflet-control-container'] }, body)), el('div', { cls: ['maplibregl-ctrl', 'maplibregl-ctrl-attrib'] }, body), el('canvas', {}, body), el('text', {}, el('svg', {}, body)),
    el('div', { cls: ['muni-label'] }, body), el('span', { cls: ['gl-mark'] }, p), el('div', { id: 'gl-tip' }, body), el('span', { attrs: { contenteditable: 'true' } }, p)];
  skip.forEach((e, i) => assert.strictEqual(G.skipped(e), true, `case ${i}: ${e.tagName}`));
  const map = el('div', { cls: ['leaflet-container'] }, body), mapPane = el('div', { cls: ['leaflet-pane', 'leaflet-map-pane'] }, map);
  const markers = el('div', { cls: ['leaflet-pane', 'leaflet-marker-pane'] }, mapPane), tips = el('div', { cls: ['leaflet-pane', 'leaflet-tooltip-pane'] }, mapPane), labels = el('div', { cls: ['leaflet-pane', 'leaflet-muni-pane'] }, mapPane);
  const popup = el('div', { cls: ['leaflet-popup-content'] }, el('div', { cls: ['leaflet-popup'] }, el('div', { cls: ['leaflet-pane', 'leaflet-popup-pane'] }, mapPane)));
  for (const e of [el('div', {}, markers), el('div', {}, tips), el('div', {}, labels)]) assert.strictEqual(G.skipped(e), true, 'map labels, markers and tooltips');
  const mlMap = el('div', { cls: ['maplibregl-map'] }, body), mlPopup = el('div', { cls: ['maplibregl-popup-content'] }, el('div', { cls: ['maplibregl-popup'] }, mlMap));
  for (const e of [p, el('li', {}, el('ul', {}, body)), el('td', {}, el('tr', {}, body)), el('th', {}, el('tr', {}, body)), el('b', {}, p), el('div', {}, popup), el('p', {}, mlPopup), el('small', {}, el('div', { cls: ['legend-box'] }, body))])
    assert.strictEqual(G.skipped(e), false, `kept: ${e.tagName}`);
  assert.strictEqual(G.skipped(el('h2', { attrs: { 'data-gloss': 'domain-in-the-dictionary' } }, body)), true, 'an element marked on purpose is marked by markExplicit, not by the automatic pass');
});

test('skipped: no mark inside an interactive control (a second Tab stop, a focusable in a focusable), nor under data-no-glossary; a paragraph is still marked', () => {
  const m = matcher([term('moe', ['margin of error'])]), p = el('p', {}, body);
  const controls = { a: el('a', {}, p), button: el('button', {}, p), label: el('label', {}, p), select: el('select', {}, p), option: el('option', {}, el('select', {}, p)), textarea: el('textarea', {}, p),
    input: el('input', {}, p), summary: el('summary', {}, el('details', {}, body)), contenteditable: el('div', { attrs: { contenteditable: '' } }, body), 'data-no-glossary': el('div', { attrs: { 'data-no-glossary': '' } }, body) };
  for (const r of ['button', 'option', 'menuitem', 'menuitemcheckbox', 'menuitemradio', 'tab', 'switch', 'checkbox', 'radio', 'link']) controls['role=' + r] = el('div', { attrs: { role: r } }, body);
  for (const [k, c] of Object.entries(controls)) {
    const deep = el('span', {}, el('b', {}, c));   // the term sits below the control, not in it directly
    assert.strictEqual(G.skipped(deep), true, `${k}: skipped up to the root`);
    assert.deepStrictEqual(G.plan([txt('the margin of error', deep)], { default: m }, G.newCtx()), [], `${k}: nothing planned`);
  }
  // the "layers on" chip: its rows are not controls themselves, the list carries data-no-glossary (core/activelayers.js)
  const li = el('li', {}, el('ul', { cls: ['al-list'] }, el('div', { cls: ['al-panel'] }, el('div', { id: 'alWrap', attrs: { 'data-no-glossary': '' } }, body))));
  assert.strictEqual(G.skipped(el('span', { cls: ['al-name'] }, li)), true, 'a row of the layers chip');
  assert.strictEqual(G.skipped(el('div', { attrs: { 'data-no-glossary': 'false', role: 'region' } }, body)), true, 'the attribute opts out whatever its value');
  for (const kept of [el('div', { attrs: { role: 'region' } }, body), el('div', { attrs: { role: 'group' } }, body), el('div', { attrs: { contenteditable: 'false' } }, body)]) assert.strictEqual(G.skipped(kept), false, 'not a control');
  const out = G.plan([txt('the margin of error', el('span', {}, p))], { default: m }, G.newCtx());
  assert.deepStrictEqual(out.map(([n, picks]) => n.nodeValue.slice(picks[0][0], picks[0][1])), ['margin of error'], 'a normal paragraph is still marked');
});

test('a mark on purpose (data-gloss) keeps the skip rule of controls and data-no-glossary, but may sit in a heading', () => {
  const p = el('p', {}, body), mark = (parent, tag = 'span') => el(tag, { attrs: { 'data-gloss': 'base-map' } }, parent);
  for (const [k, parent] of Object.entries({ button: el('button', {}, p), a: el('a', {}, p), label: el('label', {}, p), summary: el('summary', {}, el('details', {}, body)),
    'role=tab': el('div', { attrs: { role: 'tab' } }, body), 'role=switch': el('div', { attrs: { role: 'switch' } }, body), contenteditable: el('div', { attrs: { contenteditable: '' } }, body),
    'data-no-glossary': el('div', { attrs: { 'data-no-glossary': '' } }, body), 'deep under data-no-glossary': el('td', {}, el('tr', {}, el('tbody', { attrs: { 'data-no-glossary': '' } }, body))) }))
    assert.strictEqual(G.inControl(mark(parent)), true, `${k}: no mark on purpose`);
  assert.strictEqual(G.inControl(mark(body, 'button')), true, 'the marked element is a control itself');
  for (const kept of [mark(body, 'h2'), mark(el('h2', { cls: ['side-h'] }, el('nav', {}, body))), mark(p), mark(el('div', { attrs: { role: 'heading' } }, body)), mark(el('div', { attrs: { contenteditable: 'false' } }, body))])
    assert.strictEqual(G.inControl(kept), false, 'a heading or a paragraph keeps its mark on purpose');
});

test('sections: the nearest section, panel, card, legend, pop-up or Glossary term; the body when there is none', () => {
  const tab = el('section', { cls: ['tab-page'] }, body), legend = el('div', { cls: ['legend-box'] }, tab), row = el('div', { cls: ['row'] }, legend);
  assert.strictEqual(G.sectionOf(row), legend);
  assert.strictEqual(G.sectionOf(el('p', {}, tab)), tab);
  assert.strictEqual(G.sectionOf(el('p', {}, el('div', {}, body))), body);
  const dl = el('dl', { cls: ['gl-dl'] }, body), dt = el('dt', { id: 'g-moe' }, dl), dd = el('dd', { prev: dt }, dl);
  assert.strictEqual(G.sectionOf(el('span', {}, dd)), dd);
  assert.strictEqual(G.selfOf(dd), 'moe', "a term's own definition does not mark the term");
  assert.strictEqual(G.sectionOf(el('dd', {}, el('dl', { cls: ['de-facts'] }, body))), body, 'only the Glossary terms are sections of their own');
  assert.strictEqual(G.sectionOf(el('div', { attrs: { 'data-gloss-root': '' } }, body)).tagName, 'DIV');
  const one = el('section', { attrs: { 'data-gloss-root': 'one' } }, body), card = el('article', { cls: ['src-card'] }, one), deep = el('dd', {}, el('dl', {}, el('div', { cls: ['legend-box'] }, card)));
  assert.strictEqual(G.sectionOf(el('p', {}, card)), one, 'data-gloss-root="one": the cards inside it are one section with it (the dictionary’s sources)');
  assert.strictEqual(G.sectionOf(deep), one);
  assert.strictEqual(G.sectionOf(one), one);
});

test('plan: a text that is not shown waits, and is read once it shows', () => {
  const m = matcher([term('est', ['estimate'])]), sec = el('section', {}, body), hid = el('span', {}, sec), n = txt('an estimate', hid);
  let shown = false;
  const ctx = G.newCtx(); ctx.hidden = (e) => e === hid && !shown;
  assert.deepStrictEqual(G.plan([n], { default: m }, ctx), [], 'not shown: no mark, and the term is still free in its section');
  shown = true;
  assert.strictEqual(G.plan([n], { default: m }, ctx).length, 1, 'shown: marked');
});

test('plan: the first occurrence of each term in each section, never in a skipped place, and never a term the section already marks', () => {
  const m = matcher([term('moe', ['margin of error', 'margins of error']), term('est', ['estimate', 'estimates']), term('acs', ['ACS'])]);
  const a = el('section', {}, body), b = el('section', {}, body), pa = el('p', {}, a), pa2 = el('p', {}, a), h = el('h3', {}, a), pb = el('p', {}, b), btn = el('button', {}, pb);
  const nodes = [txt('Margins of error', h), txt('The estimate and its margin of error.', pa), txt('Another estimate, another margin of error, from the ACS.', pa2), txt('ACS', btn), txt('An estimate', pb)];
  const out = G.plan(nodes, { default: m }, G.newCtx());
  const got = out.map(([n, picks]) => [n.nodeValue, picks.map(([s, e, id]) => [n.nodeValue.slice(s, e), id])]);
  assert.deepStrictEqual(got, [
    ['The estimate and its margin of error.', [['estimate', 'est'], ['margin of error', 'moe']]],
    ['Another estimate, another margin of error, from the ACS.', [['ACS', 'acs']]],
    ['An estimate', [['estimate', 'est']]],
  ], 'the heading and the button are skipped; the second section marks its own first estimate');
  const again = G.plan([txt('An estimate here too', el('p', {}, b))], { default: m }, G.newCtx((sec) => sec === b ? ['est'] : []));
  assert.deepStrictEqual(again, [], 'a section that already has a mark of the term (drawn earlier) gets no second one');
  const ctx = G.newCtx(), n = txt('estimate', el('p', {}, a));
  assert.strictEqual(G.plan([n], { default: m }, ctx).length, 1);
  assert.strictEqual(G.plan([n], { default: m }, ctx).length, 0, 'a text node is read once');
});

test('plan: English text on a Spanish page is matched with the English forms when the page has them', () => {
  const es = matcher([term('moe', ['margin of error'], { es: ['margen de error'] })], 'es'), en = matcher([term('moe', ['margin of error'], { es: ['margen de error'] })], 'en');
  const sec = el('section', {}, body), span = el('span', { attrs: { lang: 'en' } }, el('p', {}, sec)), p2 = el('p', {}, el('section', {}, body));
  const out = G.plan([txt('the margin of error', span), txt('el margen de error', p2)], { default: es, es, en }, G.newCtx());
  assert.deepStrictEqual(out.map(([n, picks]) => n.nodeValue.slice(picks[0][0], picks[0][1])), ['margin of error', 'margen de error']);
});

// ── the tooltip ─────────────────────────────────────────────────────────────
test('tooltip: the term, its expansion, the definition, the source with its date and the link to the Glossary, all escaped', () => {
  const h = G.tipHtml(['MOE <b>', 'Margin of error', 'A range <script>alert(1)</script> & more', 'Census "Bureau"', 'https://www.census.gov/x?a=1&b=2', '2026-10-19', 0], 'moe', { href: 'dictionary.html#g-moe', date: (d) => 'Oct 19, 2026' });
  assert.ok(h.includes('<b>MOE &lt;b&gt;</b>'));
  assert.ok(h.includes('A range &lt;script&gt;alert(1)&lt;/script&gt; &amp; more'));
  assert.ok(h.includes('<a href="https://www.census.gov/x?a=1&amp;b=2" target="_blank" rel="noopener">Census &quot;Bureau&quot;</a>'));
  assert.ok(h.includes('link checked Oct 19, 2026'));
  assert.ok(h.includes('<a href="dictionary.html#g-moe">See in the glossary</a>'));
  assert.ok(!h.includes('lang="en"'), 'an English page marks nothing as English');
  const bad = G.tipHtml(['X', '', 'Y', 'Evil', 'javascript:alert(1)', '', 0], 'x');
  assert.ok(!/javascript:/.test(bad) && !bad.includes('Evil'), 'a source link that is not http(s) is left out');
});

test('tooltip: a definition held for review shows its English text marked lang="en" on Spanish pages, as the dictionary does', () => {
  const defs = readData('glossary_defs_es.json').terms, held = SRC.filter(t => t.hold_es);
  assert.strictEqual(held.length, 45);   // 13, the six FEMA terms of Public money v2, step 1, the six program terms of step 2, the four audit terms of step 3, the four tax credit terms of step 4, subaward, subrecipient and outlay (Public spending, decision 96), project closeout (decision 109) and the four CDBG terms (decision 100)
  for (const t of held) {
    const d = defs[t.id];
    assert.strictEqual(d[2], t.plain, t.id);
    assert.ok(d[6] & 1, `${t.id}: the definition is marked English`);
    assert.ok(!JSON.stringify(d).includes(t.plain_es), `${t.id}: the held Spanish is not published`);
    assert.ok(G.tipHtml(d, t.id).includes(`<span lang="en">`), t.id);
  }
  const released = defs['wcrp'];
  assert.ok(!(released[6] & 1), 'WCRP was released (decision 51)');
});

// ── the data ────────────────────────────────────────────────────────────────
test('the module builds from the dictionary page\'s glossary exactly the files dictionary.py writes', () => {
  for (const lang of ['es', 'en']) {
    assert.deepStrictEqual(G.formsFrom(LIST, lang), readData(`glossary_forms_${lang}.json`).terms, `forms ${lang}: the capitals rule of glossary.js and of dictionary.py agree`);
    assert.deepStrictEqual(G.defsFrom(LIST, lang), readData(`glossary_defs_${lang}.json`).terms, `defs ${lang}`);
  }
  assert.strictEqual(readData('glossary_forms_es.json').terms.length, SRC.filter(t => t.highlight).length);
  assert.strictEqual(Object.keys(readData('glossary_defs_es.json').terms).length, SRC.length, 'every term has a tooltip, so a page can mark one that is not highlighted on purpose');
});

test('the matcher reads a page of text quickly: the Spanish interface strings (190 KB) in well under a second', () => {
  const m = G.compile(readData('glossary_forms_es.json').terms);
  let text = '';
  for (const f of fs.readdirSync(path.join(__dirname, '..', 'i18n_src', 'es'))) for (const [k, v] of Object.entries(JSON.parse(fs.readFileSync(path.join(__dirname, '..', 'i18n_src', 'es', f), 'utf8')))) if (!k.startsWith('_')) text += (Array.isArray(v) ? v.join(' ') : v) + '\n';
  const t0 = process.hrtime.bigint(), n = text.split('\n').reduce((s, l) => s + m.find(l).length, 0), ms = Number(process.hrtime.bigint() - t0) / 1e6;
  assert.ok(n > 1000, `${n} matches`);
  assert.ok(ms < 800, `${ms.toFixed(0)} ms`);
});
