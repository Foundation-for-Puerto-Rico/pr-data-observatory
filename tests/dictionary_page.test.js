// The dictionary page reads data/dictionary_list.json first and the rest of each entry from data/dictionary_detail_<domain>.json on first use (dictionary.py page_files;
// docs/performance.md). These tests check, on every entry of the published dictionary.json, that the page's list and search see what they saw when the page read
// dictionary.json whole. Run: node --test tests/dictionary_page.test.js
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');

const DATA = path.join(__dirname, '..', 'site', 'data');
const read = (f) => JSON.parse(fs.readFileSync(path.join(DATA, f), 'utf8'));
const norm = (s) => (s || '').normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase().trim();   // common.js
const full = read('dictionary.json'), list = read('dictionary_list.json');
const byId = Object.fromEntries(list.entries.map(e => [e.id, e]));

test('the list file has every entry of dictionary.json, in the same order, and the page-level parts', () => {
  assert.deepStrictEqual(list.entries.map(e => e.id), full.entries.map(e => e.id));
  for (const k of ['built', 'snapshot', 'snapshot_built', 'domains', 'domain_registry', 'legacy_domain_names', 'id_alias', 'glossary']) assert.deepStrictEqual(list[k], full[k], k);
  // the Spanish of the source cards and of the area texts is in the Spanish page's own file (below)
  const strip = (o, keys) => Object.fromEntries(Object.entries(o).map(([id, x]) => [id, Object.fromEntries(Object.entries(x).filter(([k]) => !keys.includes(k)))]));
  assert.deepStrictEqual(list.sources, strip(full.sources, ['access_es', 'cadence_es', 'used_for_es', 'terms_note_es']), 'sources');
  assert.deepStrictEqual(list.domain_info, strip(full.domain_info, ['summary_es', 'groups_es']), 'domain_info');
  assert.strictEqual(list.labels_es, undefined);
});

test('an entry is its list part and its detail part: nothing lost, nothing changed', () => {
  const details = {};
  for (const f of list.detail_files) Object.assign(details, read(f).entries);
  const KEEP = ['id', 'name', 'domain', 'domains', 'group', 'kind', 'unit', 'coverage', 'sources', 'has_moe', 'plain', 'plain_es', 'definition', 'method', 'how_to_read', 'caveats', 'values', 'geography', 'value_type', 'added', 'see_also', 'source_detail'];
  for (const e of full.entries) {
    const l = byId[e.id], d = details[e.id];
    assert.ok(d, e.id + ' has a detail record');
    assert.ok(list.detail_files.includes(`dictionary_detail_${e.domain.split('.')[0]}.json`), e.id);
    const merged = { ...l, ...d };
    for (const k of KEEP) assert.deepStrictEqual(merged[k], e[k], `${e.id}.${k}`);
    assert.deepStrictEqual(l.where.files, e.where.files || [], e.id + ' files');
    assert.deepStrictEqual(d.view, e.where.view && e.where.view.length ? e.where.view : undefined, e.id + ' view');
  }
});

test('the first sentence of each summary is the one the list showed', () => {
  for (const e of full.entries) {
    const l = byId[e.id];
    assert.strictEqual(l.one, (e.plain || e.definition || '').split(/(?<=[.!?])\s/)[0], e.id);
    assert.strictEqual(l.one_es, e.plain_es ? e.plain_es.split(/(?<=[.!?])\s/)[0] : undefined, e.id + ' (es)');
  }
});

// A word typed has no space: it is part of a text exactly when it is part of one of the text's words. So the search finds the same entries when every word
// of the old text is part of the new one, and every word of the new text is part of the old one.
const words = (s) => norm(s).split(/\s+/).filter(Boolean);
function sameSearch(oldText, newText, what) {
  const o = norm(oldText), n = norm(newText);
  for (const w of words(oldText)) assert.ok(n.includes(w), `${what}: "${w}" is no longer found`);
  for (const w of words(newText)) assert.ok(o.includes(w), `${what}: "${w}" was not found before`);
}

test('the search finds every entry it found when it read the whole text', () => {
  const W = read('dictionary_words.json').w;
  for (const e of full.entries) {
    const l = { ...byId[e.id], w: W[e.id] || '' };
    assert.strictEqual(byId[e.id].w, undefined, e.id + ': the long texts\' words are in dictionary_words.json, not the list file');
    const before = [e.id, e.name, e.group, e.plain, e.plain_es, e.definition, e.method, e.unit, e.geography, e.source_detail, e.how_to_read, (e.caveats || []).join(' ')].join(' ');
    const after = [l.id, l.name, l.group, l.wp, l.w, l.unit].join(' ');
    sameSearch(before, after, e.id);
    sameSearch(e.plain, l.wp, e.id + ' (the summary, which ranks the results)');
    assert.strictEqual(norm(l.wp), l.wp, e.id);
    assert.strictEqual(norm(l.w), l.w, e.id);
  }
});

test('the page reads the list file first and a detail file on first use', () => {
  const js = fs.readFileSync(path.join(__dirname, '..', 'site', 'js', 'dictionary.js'), 'utf8');
  assert.match(js, /fetchJson\('data\/dictionary_list\.json'\)/);
  assert.doesNotMatch(js, /fetchJson\('data\/dictionary\.json'\)/);
  assert.match(js, /dictionary_detail_\$\{e\.domain\.split\('\.'\)\[0\]\}\.json/);
  const routes = JSON.parse(fs.readFileSync(path.join(__dirname, '..', 'dictionary_src', 'routes.json'), 'utf8')).routes.dictionary;
  assert.deepStrictEqual(routes.first, ['dictionary_list.json']);
  assert.deepStrictEqual(routes.later, ['dictionary_words.json', 'dictionary_list_es.json', 'registry.json'], 'the search words, the Spanish page its own file, and the registry, right after the page is ready');
  assert.match(js, /requestAnimationFrame\(\(\) => setTimeout\(loadWords\)\)/, 'the search words after the first paint');
  assert.match(js, /fetchJson\('data\/dictionary_words\.json'\)/);
  assert.match(js, /requestAnimationFrame\(\(\) => setTimeout\(loadRegistry\)\)/, 'the registry after the first paint');
  assert.deepStrictEqual([...routes.on_use].sort(), [...list.detail_files, ...list.detail_files.map(f => f.replace(/\.json$/, '_es.json'))].sort());
  assert.match(js, /fetchJson\('data\/dictionary_list_es\.json'\)/);
});

// The Spanish of dictionary_src/es/ (dictionary.py spanish_page_files) is in files of its own that only the Spanish page reads, so the English page loads what it did before:
// dictionary_list_es.json (names, labels, source cards, area texts, search words, the held entries) and dictionary_detail_<domain>_es.json ("how to read it").
// Nothing of an entry held for Finance and Compliance review is in Spanish, and no label that only held entries use is published.
test('the Spanish is in the Spanish page\'s own files, is all of it, and nothing held is in Spanish', () => {
  const es = read('dictionary_list_es.json'), details = {}, esDetails = {};
  for (const f of list.detail_files) { Object.assign(details, read(f).entries); Object.assign(esDetails, read(f.replace(/\.json$/, '_es.json')).entries); }
  for (const e of list.entries) for (const k of ['name_es', 'hold_es']) assert.strictEqual(e[k], undefined, `${e.id}: ${k} is not in the list file`);
  for (const d of Object.values(details)) assert.strictEqual(d.how_to_read_es, undefined, 'how_to_read_es is not in the detail files');
  const held = full.entries.filter(e => e.hold_es), open = full.entries.filter(e => !e.hold_es);
  assert.deepStrictEqual(es.held, held.map(e => e.id));
  assert.ok(held.length >= 12, 'the entries held for review are marked');
  for (const e of full.entries) {
    assert.strictEqual(es.names[e.id], e.name_es, e.id + ' name');
    assert.strictEqual((esDetails[e.id] || {}).how_to_read_es, e.how_to_read_es, e.id + ' how to read it');
  }
  assert.ok(open.filter(e => e.name_es).length > 600 && open.filter(e => e.how_to_read_es).length > 550, 'most entries have a Spanish name and how to read it');
  for (const e of held) assert.ok(!e.name_es && !e.how_to_read_es, e.id + ': nothing in Spanish');
  const heldPlain = Object.keys(JSON.parse(fs.readFileSync(path.join(__dirname, '..', 'i18n_src', 'held_for_review.json'), 'utf8')).dictionary_plain);
  for (const id of heldPlain) { assert.ok(es.held.includes(id), id + ' is held'); assert.strictEqual(details[id].plain_es, undefined, id + ': no Spanish summary'); }
  assert.deepStrictEqual(es.labels, full.labels_es);
  const labelsOf = (e) => [e.unit, e.geography, e.group, (e.coverage || {}).frequency];
  const openLabels = new Set(open.flatMap(labelsOf));
  for (const k of Object.keys(es.labels)) assert.ok(openLabels.has(k), `labels: "${k}" is used by an entry that is not held`);
  for (const [id, s] of Object.entries(full.sources)) for (const f of ['access', 'cadence', 'used_for', 'terms_note']) assert.strictEqual((es.sources[id] || {})[f], s[f + '_es'], `${id}.${f}`);
  for (const [d, i] of Object.entries(full.domain_info)) { assert.strictEqual((es.domain_info[d] || {}).summary, i.summary_es, d); assert.deepStrictEqual((es.domain_info[d] || {}).groups, i.groups_es, d); }
  // the search in Spanish finds the Spanish name and "how to read it"
  for (const e of full.entries) {
    const l = byId[e.id];
    const hay = norm([l.id, l.name, l.group, l.wp, (read('dictionary_words.json').w)[e.id], l.unit, es.names[e.id], es.w[e.id]].join(' '));
    for (const w of words([e.name_es, e.how_to_read_es].join(' '))) assert.ok(hay.includes(w), `${e.id} (Spanish): "${w}" is not found`);
  }
  assert.strictEqual(fs.existsSync(path.join(DATA, 'dictionary.es.json')), false, 'no dictionary.es.json');
});
