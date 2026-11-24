// Tests for the Knowledge Area registry (site/js/core/knowledge.js, docs/knowledge-areas.md). Run: node --test tests/knowledge.test.js   (python -m unittest tests.test_core_js runs it too)
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');

const ROOT = path.join(__dirname, '..');
const SITE = path.join(ROOT, 'site');
const K = require(path.join(SITE, 'js', 'core', 'knowledge.js'));
const KF = require(path.join(SITE, 'js', 'core', 'knowledge_more.js'));
const read = (f) => fs.readFileSync(path.join(SITE, f), 'utf8');
const AREAS = [
  { id: 'a', label: { en: 'Area A', es: 'Área A' }, icon: 'home_work', page: 'a.html', status: 'published' },
  { id: 'b', label: { en: 'Area B', es: 'Área B' }, icon: 'map', page: 'b.html', status: 'in_review' },
  { id: 'c', label: { en: 'Area C', es: 'Área C' }, icon: 'map', page: 'c.html', status: 'hidden' },
  { id: 'd', label: { en: 'Area D', es: 'Área D' }, icon: 'map', page: 'd.html', status: 'published', review: true },
];

test('the "All areas" menu: a hidden area is not in it; an area in review is, with its marker; a published area has none, unless it keeps the marker (review: true)', () => {
  const html = KF.menu('a', { areas: AREAS, lang: 'en', domains: {} });
  assert.strictEqual((html.match(/<a href="[a-d]\.html"/g) || []).length, 3);
  assert.ok(!html.includes('c.html') && !html.includes('Area C'), 'the hidden area is not in the menu');
  const b = /<a href="b.html"[^>]*>(.*?)<\/a>/.exec(html);
  assert.ok(b, 'the area in review is listed, marked');
  assert.match(b[1], /Area B<span class="ka-mark">In review<\/span>/);
  const a = /<a href="a.html"[^>]*>(.*?)<\/a>/.exec(html);
  assert.ok(a && !a[1].includes('ka-mark'), 'a published area has no marker');
  const d = /<a href="d.html"[^>]*>(.*?)<\/a>/.exec(html);
  assert.ok(d, 'a published area that keeps the marker is listed, marked like an area in review');
  assert.match(d[1], /Area D<span class="ka-mark">In review<\/span>/);
  assert.match(html, /<a class="ka-menu-all" href="knowledge\.html">/, 'the menu ends with the way to the Knowledge home');
  assert.deepStrictEqual(K.visible(AREAS).map(x => x.id), ['a', 'b', 'd']);
  assert.deepStrictEqual(AREAS.filter(K.marked).map(x => x.id), ['b', 'd']);
  assert.strictEqual(K.marked({ status: 'hidden', review: true }), false, 'review: true marks a published area only');
});

test('the current area is the one menu entry with aria-current; the menu is skipped by I18N.apply (already in the page language)', () => {
  const html = KF.menu('b', { areas: AREAS, lang: 'es', domains: {} });
  assert.strictEqual((html.match(/aria-current="page"/g) || []).length, 1);
  assert.match(html, /<a href="b.html" aria-current="page">/);
  assert.match(html, /Área A/);
  assert.match(K.header('a', { areas: AREAS, lang: 'es', domains: {} }), /<details class="ka-menu" data-t="skip" data-ka-menu="a">/);
});

test('the page of an area in review: its name, the marker, the message, and links to the first published area and the map', () => {
  const html = K.reviewHtml('b', { areas: AREAS, lang: 'en' });
  assert.match(html, /<h1>Area B <span class="ka-mark">In review<\/span><\/h1>/);
  assert.match(html, /This knowledge area is in review and will be published when the review is complete\./);
  assert.match(html, /href="a.html"[^>]*>.*Go to Area A<\/a>/);
  assert.match(html, /href="index.html"[^>]*>.*Open the map<\/a>/);
  assert.strictEqual(K.reviewHtml('nope', { areas: AREAS }), '');
});

test('in Spanish the marker and the message come from the knowledge scope', () => {
  const es = JSON.parse(fs.readFileSync(path.join(ROOT, 'i18n_src', 'es', 'knowledge.json'), 'utf8'));
  globalThis.T = (s, v) => String(es[s] !== undefined ? es[s] : s).replace(/\{(\w+)\}/g, (m, k) => v && k in v ? v[k] : m);
  globalThis.I18N = { lang: 'es' };
  try {
    assert.match(KF.menu('a', { areas: AREAS, domains: {} }), /Área B<span class="ka-mark">En revisión<\/span>/);
    const html = K.reviewHtml('b', { areas: AREAS });
    assert.match(html, /Esta área de conocimiento está en revisión y se publicará cuando concluya\./);
    assert.match(html, /Ir a Área A/);
    assert.match(html, /Abrir el mapa/);
    // the registry as it is today: each tab carries the marker exactly when its area is in review (publishing an area needs no edit here)
    const first = K.AREAS.find(a => a.status === 'published');
    for (const a of K.visible()) {
      const tab = new RegExp(`href="${a.page}"[^>]*>(.*?)</a>`).exec(KF.menu(first.id))[1];
      assert.strictEqual(tab.includes('<span class="ka-mark">En revisión</span>'), K.marked(a), a.id);
      assert.ok(tab.includes(a.label.es), a.id);
    }
  } finally { delete globalThis.T; delete globalThis.I18N; }
});

test('render() fills each tab group and, on the page of an area that is not published, its message and the title', () => {
  const fake = (id, main) => {
    const g = { innerHTML: '' };
    const doc = { title: 'x', querySelectorAll: (sel) => sel.startsWith('.ka-tabs') ? [{ getAttribute: () => id, set innerHTML(h) { g.innerHTML = h; } }] : [], getElementById: (k) => k === 'kaReview' ? main : null };
    K.render(doc);
    return { g, doc };
  };
  // the registry's own areas, plus a temporary hidden area and a temporary published area that keeps the marker, pushed into K.AREAS (the array find() reads)
  const tmp = [{ id: 'tmp_hidden', label: { en: 'Tmp H', es: 'Tmp H' }, icon: 'map', page: 'tmp_hidden.html', status: 'hidden' },
    { id: 'tmp_review', label: { en: 'Tmp R', es: 'Tmp R' }, icon: 'map', page: 'tmp_review.html', status: 'published', review: true }];
  K.AREAS.push(...tmp);
  try {
    for (const a of [...K.AREAS, { id: 'c' }]) {   // read from the registry, so the statuses can change without editing this test
      const main = { innerHTML: '' }, { g, doc } = fake(a.id, main);
      if (a.id === 'c') { assert.strictEqual(main.innerHTML, '', 'an id the registry does not know draws no message'); continue; }
      // the header (Knowledge plan PR 2): Knowledge › its topic on the map, then the "All areas" menu, where the page's own area is current
      assert.match(g.innerHTML, /^<a class="ka-home" href="knowledge\.html"/, `${a.id}: the header starts with the way to the Knowledge home`);
      assert.match(g.innerHTML, new RegExp(`<a class="ka-topic" href="index\\.html#topic=${(a.domain || '').split('.')[0]}"`), `${a.id}: its topic on the map`);
      assert.match(g.innerHTML, /<details class="ka-menu" data-t="skip" data-ka-menu="[a-z_]+"><summary>All areas<\/summary><div class="ka-menu-panel"><\/div><\/details>/, `${a.id}: the menu's panel fills when it is opened (knowledge_more.js)`);
      assert.doesNotMatch(g.innerHTML, /class="ka-tab/, `${a.id}: no strip of tabs any more`);
      const panel = KF.menu(a.id);
      if (a.status !== 'hidden') assert.match(panel, new RegExp(`<a href="${a.page}" aria-current="page">`), a.id);
      else {
        assert.ok(!panel.includes(`href="${a.page}"`) && !panel.includes(a.label.en), `${a.id}: a hidden area is not in the menu, even on its own page`);
        assert.doesNotMatch(panel, /aria-current/, `${a.id}: nothing is current on a hidden area's page`);
      }
      if (K.marked(a)) {
        assert.match(panel, new RegExp(`<a href="${a.page}"[^>]*>.*?<span class="ka-mark">In review</span></a>`), `${a.id}: its menu entry keeps the marker`);
        assert.match(g.innerHTML, /<span class="ka-mark ka-status">In review( · [^<]+)?<\/span>/, `${a.id}: the header says it is in review`);
      }
      if (a.status === 'published') { assert.strictEqual(main.innerHTML, '', `${a.id}: a published area keeps its own page, with or without the marker`); assert.strictEqual(doc.title, 'x'); }
      else { assert.match(main.innerHTML, /in review/, a.id); assert.strictEqual(doc.title, `Knowledge Area · ${a.label.en} · In review`); }
    }
  } finally { K.AREAS.splice(K.AREAS.length - tmp.length, tmp.length); }
  assert.ok(!K.AREAS.some(a => a.id.startsWith('tmp_')), 'the temporary areas are removed');
});

test('the "In review" notice: one base sentence for every area that keeps the marker, plus one standard sentence where the content was drafted with AI help', () => {
  const areas = [...AREAS, { id: 'e', label: { en: 'E', es: 'E' }, icon: 'map', page: 'e.html', status: 'published', review: true, ai: true },
    { id: 'f', label: { en: 'F', es: 'F' }, icon: 'map', page: 'f.html', status: 'published', ai: true }, { id: 'g', label: { en: 'G', es: 'G' }, icon: 'map', page: 'g.html', status: 'in_review', ai: true }];
  const n = (id) => K.notice(id, { areas });
  assert.strictEqual(n('a'), '', 'a plain published area has no notice');
  assert.strictEqual(n('b'), '', 'an area in review shows its placeholder message, not the notice');
  assert.strictEqual(n('g'), '');
  assert.strictEqual(n('d'), K.NOTICE);
  assert.strictEqual(n('d'), '<b>In review:</b> the content of this page is under review and may change.');
  assert.strictEqual(n('e'), `${K.NOTICE} ${K.AI}`);
  assert.strictEqual(K.AI, 'Draft prepared with the help of Claude (artificial intelligence).');
  assert.strictEqual(n('f'), K.AI, 'the AI disclosure stays when the marker goes');
  const es = JSON.parse(fs.readFileSync(path.join(ROOT, 'i18n_src', 'es', 'knowledge.json'), 'utf8'));
  assert.strictEqual(es[K.NOTICE], '<b>En revisión:</b> el contenido de esta página está en revisión y puede cambiar.');
  assert.strictEqual(es[K.AI], 'Borrador preparado con ayuda de Claude (inteligencia artificial).');
  globalThis.T = (s) => es[s] !== undefined ? es[s] : s; globalThis.I18N = { lang: 'es' };
  try { assert.strictEqual(n('e'), `${es[K.NOTICE]} ${es[K.AI]}`); } finally { delete globalThis.T; delete globalThis.I18N; }
  // render() writes it into the page's box, skipped by I18N.apply, and takes the box away where there is nothing to say
  for (const [id, want] of [['d', true], ['a', false]]) {
    const box = { attrs: {}, removed: false, innerHTML: '', setAttribute(k, v) { this.attrs[k] = v; }, remove() { this.removed = true; } };
    const doc = { title: 'x', querySelectorAll: (sel) => sel.startsWith('.ka-tabs') ? [{ getAttribute: () => id, set innerHTML(h) { } }] : sel === '[data-ka-note]' ? [box] : [], getElementById: () => null };
    const saved = K.AREAS.splice(0, K.AREAS.length, ...areas);
    try { K.render(doc); } finally { K.AREAS.splice(0, K.AREAS.length, ...saved); }
    assert.strictEqual(box.removed, !want, id);
    if (want) { assert.strictEqual(box.attrs['data-t'], 'skip'); assert.strictEqual(box.innerHTML, `<span class="ms-icon" aria-hidden="true">warning</span><span>${K.NOTICE}</span>`); }
  }
});

test('the pages: one notice box on each published page with a notice, written by the registry (no page keeps its own wording), and noindex while the marker is on', () => {
  for (const a of K.AREAS.filter(x => x.status === 'published')) {
    const html = read(a.page), boxes = html.match(/<div class="note caution review-note" role="note" data-ka-note><\/div>/g) || [];
    assert.strictEqual(boxes.length, K.notice(a.id) ? 1 : 0, `${a.page}: ${K.notice(a.id) ? 'one empty notice box' : 'no notice box'}`);
    assert.strictEqual((html.match(/review-note/g) || []).length, boxes.length, `${a.page}: no other review note`);
    if (K.marked(a)) assert.match(html, /<meta name="robots" content="noindex, nofollow">/, `${a.page}: not indexed while the marker is on`);
    if (boxes.length) assert.ok(/icon_names=([a-z0-9_,]+)/.exec(html)[1].split(',').includes('warning'), `${a.page}: the icon font has the notice's icon`);
  }
  for (const f of fs.readdirSync(SITE).filter(f => f.endsWith('.html'))) assert.doesNotMatch(read(f), /In review:<\/b>|En revisión:<\/b>/, `${f}: the notice's words live in core/knowledge.js only`);
  assert.deepStrictEqual(K.AREAS.filter(a => a.ai).map(a => a.id), ['routes', 'gii', 'women', 'moneycycle', 'publicmoney', 'publicspending', 'unusedfunds', 'urbanheat', 'inflation', 'reservoirs', 'broadband', 'energy', 'oppzones', 'tlinks', 'treach'], 'the areas drafted with AI help (Route analysis, GII, Women in the labor force, FEMA disaster funding and need, Urban heat) keep their disclosure');
});

test('the registry: unique ids, a known status, a name in both languages, and a page that draws its tabs from the registry', () => {
  const ids = K.AREAS.map(a => a.id);
  assert.strictEqual(new Set(ids).size, ids.length);
  assert.ok(K.AREAS.some(a => a.status === 'published'), 'the Knowledge Area button opens a published area');
  assert.strictEqual(K.AREAS.find(a => a.status === 'published').page, 'housing.html', 'an in-review page\'s "Go to" link opens the first published area (housing.html)');
  // the top bar's Knowledge button opens the Knowledge home page on every page (knowledge plan, decision 90, PR 1)
  for (const f of fs.readdirSync(path.join(__dirname, '..', 'site')).filter(f => f.endsWith('.html'))) {
    const html = fs.readFileSync(path.join(__dirname, '..', 'site', f), 'utf8'), bar = (html.match(/<nav class="views"[\s\S]*?<\/nav>/) || [''])[0];
    if (!bar.includes('lightbulb')) continue;
    assert.match(bar, /<a class="btn" href="knowledge\.html"[^>]*><span class="ms-icon" aria-hidden="true">lightbulb<\/span><span class="lbl">Knowledge<\/span><\/a>/, `${f}: the Knowledge button opens knowledge.html`);
  }
  for (const a of K.AREAS) {
    assert.ok(K.STATUSES.includes(a.status), a.id);
    if ('review' in a) assert.ok(a.review === true && a.status === 'published', `${a.id}: review: true goes on a published area only (an area in review is marked already)`);
    assert.ok(a.label.en && a.label.es, a.id);
    assert.match(a.icon, /^[a-z0-9_]+$/);
    if (a.status === 'hidden' && !fs.existsSync(path.join(SITE, a.page))) continue;   // a hidden area may have no page yet
    const html = read(a.page);
    assert.match(html, new RegExp(`<span class="ka-tabs" role="group" aria-label="Knowledge Area" data-ka="${a.id}"></span>`), `${a.page}: an empty tab group with its own id`);
    assert.match(html, /<script src="js\/core\/knowledge\.js\?v=\d+"><\/script>\r?\n<script>Core\.knowledge\.render\(\); I18N\.apply\(\);<\/script>/, `${a.page}: the registry draws before I18N.apply`);
    const icons = /icon_names=([a-z0-9_,]+)/.exec(html)[1].split(',');
    for (const b of K.visible()) assert.ok(icons.includes(b.icon), `${a.page}: the icon font lacks ${b.icon}`);
    assert.ok(icons.includes('map'), `${a.page}: the icon font lacks map`);
  }
  for (const f of fs.readdirSync(SITE).filter(f => f.endsWith('.html'))) {   // the other pages keep the Knowledge Area button, to the first published area
    const html = read(f);
    if (/class="lbl">Knowledge Area</.test(html)) assert.match(html, /<a class="btn" href="housing\.html"[^>]*><span class="ms-icon" aria-hidden="true">lightbulb<\/span><span class="lbl">Knowledge Area<\/span><\/a>/, f);
  }
});

// What the page of an area that is not published may show on main: its tab, its marker and the in-review message (the WCRP name alone is already public, as the
// map's WCRP communities layer). Anything about the program (its full name, the agency, the grant, the plans, the index, its tools, its datasets) waits for
// Finance and Compliance on its own branch (docs/knowledge-areas.md). The match decodes HTML entities, then ignores case, accents and runs of spaces.
const ENTITY = { amp: '&', lt: '<', gt: '>', quot: '"', apos: "'", nbsp: ' ', szlig: 'ss' };
const decode = (s) => String(s)
  .replace(/&#x([0-9a-f]+);?/gi, (m, h) => String.fromCodePoint(parseInt(h, 16)))
  .replace(/&#(\d+);?/g, (m, d) => String.fromCodePoint(+d))
  .replace(/&([A-Za-z])(acute|grave|circ|tilde|uml|ring|cedil);/g, '$1')
  .replace(/&([A-Za-z]+);/g, (m, n) => ENTITY[n] !== undefined ? ENTITY[n] : m);
const fold = (s) => decode(s).normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase().replace(/\s+/g, ' ');
const BANNED = new RegExp([
  'cdbg', 'prdoh', 'hud', 'lihtc', 'hunter', '(?<![a-z])rvi(?![a-z])',   // acronyms and makers as substrings, so "PlanningCDBG" is caught; "rvi" needs letter edges ("service")
  'whole[- ]community', 'resilien', 'planificacion integral', 'social[- ]capital', 'capital[- ]social', 'white[- ]paper', 'libro blanco',
  'department of housing', 'departamento de (la )?vivienda', 'housing and urban development', 'vivienda y desarrollo urbano',
  'disaster recovery', 'recuperacion (ante|de|tras|despues de) (los |un |el )?desastres?',
  'fondos federales', 'federal funds', 'subvencion', '(?<![a-z])grant', 'vulnerab',   // "grant" at a word start, so "immigrant" passes
  'plan aprobado', 'plan approved', 'plan en (curso|progreso|proceso)', 'plan in progress', 'planes de resiliencia', 'resilience plan',
  'list of \\d{4}-\\d{2}-\\d{2}', 'lista del? \\d{4}-\\d{2}-\\d{2}', 'list of communities', 'lista de comunidades',
  'wcrp[._-](?!html)',   // the program's datasets and files (wcrp.rvi_..., wcrp_social.json); the page wcrp.html is allowed
].join('|'));
const banned = (text) => { const m = BANNED.exec(fold(text)); return m ? m[0] : null; };
// every value of a JSON file that belongs to one dictionary entry: an object with that id, a key named by it, or a row that starts with it (catalog_index.json)
function entryParts(node, id, out = []) {
  if (Array.isArray(node)) { if (node[0] === id) out.push(node); else node.forEach(x => entryParts(x, id, out)); }
  else if (node && typeof node === 'object') { if (node.id === id) out.push(node); else for (const [k, v] of Object.entries(node)) { if (k === id) out.push(v); else entryParts(v, id, out); } }
  return out;
}
const readJson = (...p) => JSON.parse(fs.readFileSync(path.join(ROOT, ...p), 'utf8'));
const notPublished = K.AREAS.filter(x => x.status !== 'published');

test('the match catches the program terms in Spanish and English, with or without accents or entities, and lets the bare acronym through', () => {
  for (const t of ['Resiliencia Comunitaria', 'Whole Community', 'Whole-Community', 'Whole&nbsp;Community', 'Departamento de la Vivienda', 'Departamento de Vivienda', 'Department of Housing', 'Housing and Urban Development', 'Vivienda y Desarrollo Urbano',
    'fondos federales', 'Fondos Federales', 'federal funds', 'subvención', 'SUBVENCION', 'grant', 'Grants', 'Planificación Integral', 'Planificaci&oacute;n Integral', 'Planificaci&#243;n Integral', 'Planificaci&#xF3;n Integral',
    'Hunter', 'RVI', 'rvi_overall', 'CDBG-DR', 'PlanningCDBG', 'HUD', 'PRDOH', 'vulnerabilidad', 'Vulnerability', 'vulnérable', 'Social Capital', 'Social-Capital', 'Capital Social', 'white paper', 'disaster recovery',
    'recuperación ante desastres', 'recuperación de desastres', 'plan aprobado', 'Plan approved', 'Plan in progress', 'list of 2026-10-06', 'lista del 2026-10-06', 'dictionary.html#wcrp.rvi_overall_orig', 'wcrp_social.json'])
    assert.ok(banned('… ' + t + ' …'), t);
  for (const t of ['WCRP', 'WCRP · En revisión', 'Knowledge Area · WCRP · In review', 'wcrp.html', 'data-ka="wcrp"', 'Foundation for Puerto Rico', 'Área de conocimiento', 'En revisión', 'servicio', 'service', 'Vivienda', 'added 2026-10-19', 'immigrant populations', 'inmigrantes'])
    assert.strictEqual(banned(t), null, t);
});

test('the page of an area that is not published shows nothing but the in-review message', () => {
  assert.strictEqual(banned(fs.readFileSync(path.join(SITE, 'js', 'core', 'knowledge.js'), 'utf8')), null, 'core/knowledge.js is published: no program terms in it');
  const scope = readJson('i18n_src', 'es', 'knowledge.json'), words = Object.fromEntries(Object.entries(scope).filter(([k]) => !k.startsWith('_')));
  for (const [k, v] of Object.entries(words)) assert.strictEqual(banned(k + ' ' + v), null, `i18n_src/es/knowledge.json: ${k}`);
  const pages = readJson('i18n_src', 'pages.json').pages;
  for (const a of notPublished) {
    assert.strictEqual(banned(a.label.en + ' ' + a.label.es), null, a.id);
    if (!fs.existsSync(path.join(SITE, a.page))) continue;   // a hidden area with no page yet
    const html = read(a.page);
    assert.strictEqual(banned(html), null, a.page);
    assert.match(html, /<meta name="robots" content="noindex, nofollow">/, a.page);
    assert.match(html, /<main class="page" id="kaReview"><\/main>/, `${a.page}: the body is the registry's message only`);
    const scripts = [...html.matchAll(/<script src="([^"]+)"/g)].map(m => m[1].split('?')[0]);
    assert.deepStrictEqual(scripts, ['js/i18n.js', 'js/core/knowledge.js'], `${a.page}: no data, no map`);
    assert.doesNotMatch(html, /data\/|leaflet|fetch\(|<(iframe|object|embed|video|audio|canvas|svg|picture|source)\b/i, a.page);
    const imgs = [...html.matchAll(/<img\b[^>]*>/gi)].map(m => (/\ssrc="([^"]*)"/.exec(m[0]) || [])[1]);
    assert.deepStrictEqual(imgs, ['img/fpr-logo.png'], `${a.page}: the FPR logo is its only image`);
    for (const [, h] of html.matchAll(/\shref="([^"]*)"/g))   // links: the other views, its own anchor, the icon, its styles and the font; no deep link (dictionary.html#wcrp.rvi_...)
      assert.match(h, /^(index|3d|housing|dictionary)\.html$|^#kaReview$|^img\/fpr-mark\.png$|^css\/(twin|housing)\.css\?v=\d+$|^https:\/\/fonts\.(gstatic|googleapis)\.com(\/|$)/, `${a.page}: link ${h}`);
    // its Spanish bundle is the knowledge scope, keys and values, and nothing else (the common scope carries the map's WCRP layer strings)
    const page = /data-page="(\w+)"/.exec(html)[1];
    assert.deepStrictEqual(pages[page].scopes, ['knowledge'], `${a.page}: its bundle is the knowledge scope only`);
    const bundle = fs.readFileSync(path.join(SITE, 'i18n', `es.${page}.js`), 'utf8');
    const parsed = JSON.parse(/I18N\.add\((\{[\s\S]*\})\);?\s*$/.exec(bundle.trim())[1]);
    assert.deepStrictEqual(parsed, words, `site/i18n/es.${page}.js is the knowledge scope, keys and values (run python i18n.py)`);
    assert.strictEqual(banned(bundle), null, `site/i18n/es.${page}.js`);
    assert.strictEqual(banned(JSON.stringify(parsed)), null, `site/i18n/es.${page}.js`);
  }
});

test('the dictionary entry of the Knowledge Area names no program terms while an area is not published', { skip: notPublished.length === 0 && 'every area is published' }, () => {
  // its source, its Spanish summary, and every published data file that carries it (on publishing, the entry may describe the published area: docs/knowledge-areas.md)
  const id = 'layers.knowledge_area';
  const files = [['dictionary_src', 'entries', 'views_layers.json'], ['i18n_src', 'dictionary_plain.json'], ...fs.readdirSync(path.join(SITE, 'data')).filter(f => f.endsWith('.json')).map(f => ['site', 'data', f])];
  let found = 0;
  for (const f of files) {
    const text = fs.readFileSync(path.join(ROOT, ...f), 'utf8');
    if (!text.includes(id)) continue;
    const parts = entryParts(JSON.parse(text), id);
    assert.ok(parts.length > 0, `${f.join('/')}: names ${id} but holds no part of it`);
    found++;
    assert.strictEqual(banned(JSON.stringify(parts)), null, `${f.join('/')}: ${id}`);
  }
  assert.ok(found >= 7, `${id} is in its source, the Spanish summaries and the dictionary and catalog files (${found} found)`);
});

test('the header and foot of an area page with the registry\'s items loaded (Knowledge plan PR 2): topic name, reviewer, date, related areas and data', () => {
  const src = fs.readFileSync(path.join(SITE, 'js', 'knowledge_items.js'), 'utf8');
  const KN = JSON.parse(src.slice(src.indexOf('{'), src.lastIndexOf('}') + 1));
  globalThis.KNOWLEDGE = KN;
  try {
    for (const it of KN.items) {
      const h = K.header(it.id, { lang: 'en' }), top = it.domains[0].split('.')[0], dom = KN.domains.find(d => d.id === top);
      assert.ok(h.includes(`>${dom.name.en}</a>`), `${it.id}: the topic is named (${dom.name.en})`);
      assert.ok(h.length < 4000, `${it.id}: the header stays small`);
      const a = K.find(it.id);
      if (K.marked(a) && (it.reviewer || []).length) assert.match(h, new RegExp(`In review · ${KN.reviewers[it.reviewer[0]].en}`), `${it.id}: the reviewer is named`);
      if (!K.marked(a)) assert.doesNotMatch(h, /ka-status/, `${it.id}: no status badge when the marker is off`);
      assert.match(h, /<span class="ka-upd">Updated [A-Z][a-z]+ 20\d\d<\/span>/, `${it.id}: when it was updated`);
      const f = KF.foot(it.id, { lang: 'en' });
      for (const r of it.related || []) assert.ok(f.includes(`href="${KN.items.find(x => x.id === r).page}"`), `${it.id}: related ${r} is linked`);
      for (const d of it.datasets || []) assert.ok(f.includes(KN.datasets[d].en.replace(/&/g, '&amp;')), `${it.id}: dataset ${d} is listed`);
      assert.ok(f.includes(`href="${it.cite}"`), `${it.id}: the way to its cite text`);
      const es = K.header(it.id, { lang: 'es' });
      assert.ok(es.includes(`>${dom.name.es}</a>`), `${it.id}: the topic in Spanish`);
    }
  } finally { delete globalThis.KNOWLEDGE; }
  assert.doesNotMatch(KF.foot('publicmoney', { lang: 'en' }), /Data used on this page/, 'without the items file the foot lists no datasets (it waits for js/knowledge_items.js)');
});

test('no area page loads the items file on its first load: core/knowledge.js loads it after the page is ready, with the same ?v= as the home page', () => {
  for (const a of K.AREAS) {
    if (!fs.existsSync(path.join(SITE, a.page))) continue;
    assert.doesNotMatch(read(a.page), /knowledge_items\.js/, `${a.page}: not on the first load (page-weight budget)`);
  }
  const core = fs.readFileSync(path.join(SITE, 'js', 'core', 'knowledge.js'), 'utf8'), home = read('knowledge.html');
  assert.strictEqual(/const ITEMS_V = (\d+)/.exec(core)[1], /knowledge_items\.js\?v=(\d+)/.exec(home)[1], 'one cached copy for the home page and the area pages');
  for (const it of Object.keys(K.DOMAINS)) assert.ok(K.DOMAINS[it].en && K.DOMAINS[it].es, `topic ${it} named in both languages`);
});

test('the Knowledge home page loads the icon of every area (an icon missing from icon_names shows as its name: BOLT, 2026-11-17)', () => {
  const icons = /icon_names=([a-z0-9_,]+)/.exec(read('knowledge.html'))[1].split(',');
  for (const a of K.AREAS) assert.ok(icons.includes(a.icon), `knowledge.html: add ${a.icon} (${a.id}) to icon_names`);
});
