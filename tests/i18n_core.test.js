// Tests for site/js/i18n.js (the language layer). Run: node --test tests/i18n_core.test.js   (python -m unittest discover -s tests runs it too when node is installed)
const test = require('node:test');
const assert = require('node:assert');
const path = require('node:path');
const { create } = require(path.join(__dirname, '..', 'site', 'js', 'i18n.js'));

const mk = (o = {}) => create(Object.assign({ document: null, search: '', languages: [], storage: null }, o));
const DICT = {
  'Tourism places': 'Lugares turísticos',
  '{n} of {m} places': '{n} de {m} lugares',
  '{n} place': ['{n} lugar', '{n} lugares'],
  '<b>{n}</b> places': '<b>{n}</b> lugares',
  'verb\u0004Show': 'Mostrar',
  'Show': 'Muestra',
};

test('language choice: URL, then saved choice, then browser, then Spanish', () => {
  assert.deepStrictEqual([mk({ search: '?lang=en', languages: ['es'] }).lang, mk({ search: '?lang=en', languages: ['es'] }).source], ['en', 'url']);
  assert.strictEqual(mk({ search: '?lang=xx', languages: ['en-US'] }).lang, 'en');           // an unknown value is ignored
  assert.strictEqual(mk({ languages: ['en-US'], storage: { getItem: () => 'es' } }).lang, 'es');
  assert.strictEqual(mk({ languages: ['en-US'], storage: { getItem: () => 'es' } }).source, 'saved');
  assert.strictEqual(mk({ languages: ['en-US'], session: { getItem: () => 'es' }, storage: { getItem: () => 'en' } }).lang, 'es');   // a link's choice outranks the remembered one for the session
  assert.strictEqual(mk({ languages: ['en-US'], session: { getItem: () => 'es' }, storage: { getItem: () => 'en' } }).source, 'session');
  assert.strictEqual(mk({ languages: ['en-US', 'es-PR'] }).lang, 'es');                      // mixed browser list: Spanish
  assert.strictEqual(mk({ languages: ['en-US', 'en'] }).lang, 'en');
  assert.strictEqual(mk({ languages: ['fr-FR'] }).lang, 'es');                               // nothing we know: Spanish first
  assert.strictEqual(mk({ languages: [] }).lang, 'es');
  assert.strictEqual(mk({ languages: ['en'], storage: { getItem: () => { throw new Error('blocked'); } } }).lang, 'en');   // storage may throw
});

test('English returns the key itself, with placeholders filled', () => {
  const I = mk({ search: '?lang=en' });
  I.add(DICT);
  assert.strictEqual(I.t('Tourism places'), 'Tourism places');
  assert.strictEqual(I.t('{n} of {m} places', { n: 3, m: 9 }), '3 of 9 places');
  assert.strictEqual(I.tn(1, '{n} place', '{n} places'), '1 place');
  assert.strictEqual(I.tn(2, '{n} place', '{n} places'), '2 places');
  assert.strictEqual(I.tn(0, '{n} place', '{n} places'), '0 places');
  assert.deepStrictEqual(I.missed, []);
});

test('Spanish translates, fills placeholders and records misses', () => {
  const I = mk({ search: '?lang=es' });
  I.add(DICT);
  assert.strictEqual(I.t('Tourism places'), 'Lugares turísticos');
  assert.strictEqual(I.t('{n} of {m} places', { n: 3, m: 9 }), '3 de 9 lugares');
  assert.strictEqual(I.t('Not in the file'), 'Not in the file');
  assert.deepStrictEqual(I.missed, ['Not in the file']);
  assert.strictEqual(I.t('{unknown} stays', { n: 1 }), '{unknown} stays');                    // a missing value leaves the placeholder
});

test('plurals follow the language rules', () => {
  const I = mk({ search: '?lang=es' });
  I.add(DICT);
  assert.strictEqual(I.tn(1, '{n} place', '{n} places'), '1 lugar');
  assert.strictEqual(I.tn(2, '{n} place', '{n} places'), '2 lugares');
  assert.strictEqual(I.tn(0, '{n} place', '{n} places'), '0 lugares');
  assert.strictEqual(I.tn(1000000, '{n} place', '{n} places'), '1000000 lugares');          // CLDR calls this "many": still the plural
  assert.strictEqual(I.tn(2, '{n} thing', '{n} things'), '2 things');                         // no entry: English fallback, recorded
  assert.ok(I.missed.includes('{n} thing'));
});

test('context disambiguates the same English text', () => {
  const I = mk({ search: '?lang=es' });
  I.add(DICT);
  assert.strictEqual(I.t('Show', null, 'verb'), 'Mostrar');
  assert.strictEqual(I.t('Show'), 'Muestra');
});

test('Th escapes values unless they are raw', () => {
  const I = mk({ search: '?lang=es' });
  I.add(DICT);
  assert.strictEqual(I.th('<b>{n}</b> places', { n: '<i>x</i>' }), '<b>&lt;i&gt;x&lt;/i&gt;</b> lugares');
  assert.strictEqual(I.th('<b>{n}</b> places', { n: I.raw('<i>x</i>') }), '<b><i>x</i></b> lugares');
  const E = mk({ search: '?lang=en' });
  assert.strictEqual(E.th('<b>{n}</b> places', { n: 'a & b' }), '<b>a &amp; b</b> places');
});

test('numbers, dates and lists use the page language (Puerto Rico uses the US number form)', () => {
  const es = mk({ search: '?lang=es' }), en = mk({ search: '?lang=en' });
  assert.strictEqual(es.fmt(1234567.891, 1), '1,234,567.9');
  assert.strictEqual(en.fmt(1234567.891, 1), '1,234,567.9');
  assert.strictEqual(es.fmt(null), '—');
  assert.strictEqual(es.date('2026-10-05T12:00:00Z'), '5 de octubre de 2026');
  assert.strictEqual(en.date('2026-10-05T12:00:00Z'), 'October 5, 2026');
  assert.strictEqual(es.date('2026-10-05'), '5 de octubre de 2026');             // a date-only text is that calendar day, in any time zone
  assert.strictEqual(en.date('2026-01-01'), 'January 1, 2026');
  assert.strictEqual(es.list(['a', 'b', 'c']), 'a, b y c');
  assert.strictEqual(en.list(['a', 'b', 'c']), 'a, b, and c');
  assert.strictEqual(es.name({ name: { es: 'Vivienda', en: 'Housing' } }), 'Vivienda');
  assert.strictEqual(en.name({ name: { es: 'Vivienda', en: 'Housing' } }), 'Housing');
  assert.strictEqual(en.name({ name: { en: 'Only English' } }), 'Only English');
});

test('href() keeps the path and hash and sets lang', () => {
  const I = mk({ search: '', href: 'http://x.test/pr/index.html?foo=1#c=18.2,-66.4,9&l=muni' });
  assert.strictEqual(I.href('en'), '/pr/index.html?foo=1&lang=en#c=18.2,-66.4,9&l=muni');
});

// ── static markup: a minimal fake DOM (nodeType, tagName, childNodes, attributes, innerHTML) ──
function text(s) { return { nodeType: 3, nodeValue: s }; }
function el(tag, attrs, kids, html) {
  const e = {
    nodeType: 1, tagName: tag.toUpperCase(), childNodes: kids || [], _attrs: Object.assign({}, attrs), innerHTML: html || '', type: attrs && attrs.type, value: attrs && attrs.value,
    getAttribute(n) { return n in this._attrs ? this._attrs[n] : null; }, setAttribute(n, v) { this._attrs[n] = v; },
    classList: { contains: (c) => ((attrs && attrs.class) || '').split(' ').includes(c) },
    matches(sel) { return sel === '.skipme' && ((attrs && attrs.class) || '').split(' ').includes('skipme'); },
  };
  return e;
}
const doc = (body) => ({ body, title: 'Map', documentElement: { lang: 'en', setAttribute() {} }, querySelector: () => null });

test('apply() translates text nodes, attributes, mixed-content units and leaves the rest', () => {
  const t1 = text('\n   Tourism places  \n'), t2 = text('Unknown text here'), t3 = text('menu'), t4 = text('42');
  const unit = el('p', {}, [text('Click '), el('b', {}, [text('now')])], '<b>{n}</b> places');
  const btn = el('button', { title: 'Tourism places', 'aria-label': 'Nothing to say' }, [el('span', { class: 'ms-icon' }, [t3]), t1]);
  const skipped = el('code', {}, [text('Tourism places')]);
  const body = el('body', {}, [btn, el('div', {}, [t2, t4, skipped]), unit]);
  const I = create({ document: doc(body), search: '?lang=es', languages: [], storage: null });
  I.add(Object.assign({ 'Map': 'Mapa' }, DICT));
  I.apply();
  assert.strictEqual(t1.nodeValue, '\n   Lugares turísticos  \n');            // whitespace around the text is kept
  assert.strictEqual(btn.getAttribute('title'), 'Lugares turísticos');
  assert.strictEqual(btn.getAttribute('aria-label'), 'Nothing to say');        // no entry: left alone
  assert.strictEqual(t3.nodeValue, 'menu');                                    // icon ligature
  assert.strictEqual(t4.nodeValue, '42');
  assert.strictEqual(skipped.childNodes[0].nodeValue, 'Tourism places');       // <code> is skipped
  assert.strictEqual(unit.innerHTML, '<b>{n}</b> lugares');                    // the unit is keyed by its innerHTML
  assert.ok(I.pending.includes('Unknown text here'));
  I.apply();                                                                   // safe to repeat
  assert.strictEqual(t1.nodeValue, '\n   Lugares turísticos  \n');
});

test('apply() does nothing in English', () => {
  const t1 = text('Tourism places'), body = el('body', {}, [el('div', {}, [t1])]);
  const I = create({ document: doc(body), search: '?lang=en', languages: [], storage: null });
  I.add(DICT);
  I.apply();
  assert.strictEqual(t1.nodeValue, 'Tourism places');
});

test('audit() lists static text that has no Spanish yet, ignoring text built from templates and excluded areas', () => {
  const body = el('body', {}, [el('p', {}, [text('Tourism places')]), el('p', {}, [text('Needs a translation')]), el('p', {}, [text('3 de 9 lugares')]), el('p', { class: 'skipme' }, [text('English data on purpose')])]);
  const I = create({ document: doc(body), search: '?lang=es', languages: [], storage: null });
  I.add(DICT);
  assert.deepStrictEqual(I.audit(body, { exclude: '.skipme' }), ['text: Needs a translation']);
});

test('en() marks English text as English in a Spanish page, and leaves it alone in an English one', () => {
  const es = mk({ search: '?lang=es' }), en = mk({ search: '?lang=en' });
  assert.strictEqual(es.en('A definition'), '<span lang="en">A definition</span>');
  assert.strictEqual(es.en(''), '', 'nothing to mark');
  assert.strictEqual(en.en('A definition'), 'A definition');
});

test('load() fetches a module bundle once, can try again after a failure, and does nothing in English', async () => {
  let calls = 0, fail = true;
  const es = mk({ search: '?lang=es', bundle: (mod) => { calls++; if (fail) return Promise.reject(new Error(mod)); es.add({ Views: 'Vistas' }); return Promise.resolve(); } });
  await assert.rejects(es.load('views'));
  fail = false;
  await Promise.all([es.load('views'), es.load('views')]);
  await es.load('views');
  assert.strictEqual(calls, 2, 'one failed try, then one load shared by every caller');
  assert.strictEqual(es.t('Views'), 'Vistas');
  const en = mk({ search: '?lang=en', bundle: () => { throw new Error('English needs no bundle'); } });
  await en.load('views');
  await mk({ search: '?lang=es' }).load('views');   // no bundle loader (node, or a page without data-page): nothing to wait for
});
