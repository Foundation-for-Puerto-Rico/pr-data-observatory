// "Ask the observatory": the understanding layer (site/js/ask.js) and the answers it changes (site/js/chat.js), with the real datasets and a page stand-in
// (tests/ask_runtime.js). docs/ask.md describes the design; tests/ask_dev.json and tests/ask_check.json are the question sets whose pass rates are kept here.
'use strict';
const test = require('node:test'), assert = require('node:assert');
const fs = require('fs'), path = require('path');
const A = require('../site/js/ask.js');
const R = require('./ask_runtime');
const LY = require('../site/js/core/layers.js');

let ENV = {};
const envOf = (lang = 'es', view = '2d') => ENV[lang + view] || (ENV[lang + view] = R.env({ lang, view }));
const ask = (q, lang = 'es', view = '2d') => envOf(lang, view).answer(q);
const index = async () => (await envOf('es').chat.chAskModule()).ix;

test('stem: one family for the forms of a word, and no family for different words that look alike', () => {
  for (const w of ['transporte', 'transportation', 'transportacion', 'transport']) assert.strictEqual(A.stem(w), 'transport', w);
  assert.strictEqual(A.stem('escuelas'), A.stem('escuela'));
  assert.strictEqual(A.stem('viviendas'), A.stem('vivienda'));
  assert.strictEqual(A.stem('libraries'), A.stem('library'));
  assert.notStrictEqual(A.stem('parking'), A.stem('parks'), '"ing" is not an ending of the stem: parking is not parks');
  assert.notStrictEqual(A.stem('viviendo'), A.stem('vivienda'), 'a gerund is a verb');
  assert.notStrictEqual(A.stem('costo'), A.stem('costa'), 'cost is not coast');
  assert.notStrictEqual(A.stem('caso'), A.stem('casa'));
});

test('typos: a word one edit from a topic is read as that topic (two edits from eight letters); real words, other first letters and long sentences are left alone', async () => {
  const ix = await index();
  for (const [w, c] of [['pobresa', 'pobreza'], ['desempelo', 'desempleo'], ['vivenda', 'vivienda'], ['transprte', 'transporte'], ['esculeas', 'escuelas'], ['inundasiones', 'inundaciones'], ['hopsitales', 'hospitales'], ['poberty', 'poverty'], ['derumbes', 'derrumbes'], ['envejesientes', 'envejecientes']])
    assert.strictEqual(A.correct(w, ix), c, w);
  for (const w of ['pasada', 'relation', 'addition', 'cifra', 'order', 'escuelas', 'pobreza', 'casos', 'decade', 'people']) assert.strictEqual(A.correct(w, ix), null, w);
  assert.strictEqual(A.dl('desempelo', 'desempleo'), 1, 'a swap of two letters is one edit');
  assert.deepStrictEqual(A.fix('pobresa en mayaguez', ix).fixes, [['pobresa', 'pobreza']]);
  assert.deepStrictEqual(A.fix('la pobreza, mujeres vs la década pasada', ix, { listed: true }).fixes, [], 'only the words of a list are read when the rest is understood');
  assert.deepStrictEqual(A.fix('pobreza y desempelo', ix, { listed: true }).fixes, [['desempelo', 'desempleo']]);
  assert.deepStrictEqual(A.fix('the contributions of every pobresa add up to the score of the island today', ix).fixes, [], 'a long sentence is not read as a misspelt topic');
});

test('understand: topics, layers, places, a time, what must not be drawn and a term to define, each where it stands in the question', async () => {
  const ix = await index(), u = (q) => A.understand(A.nrm(q), ix, { explain: true });
  assert.deepStrictEqual(u('transporte y vivienda').concepts.map(h => h.id), ['transport', 'housing']);
  assert.deepStrictEqual(u('Transportation and housing').concepts.map(h => h.id), ['transport', 'housing']);
  assert.deepStrictEqual(u('rutas de guagua y paradas en Bayamón').layers.map(h => h.id), ['lyRoutes', 'lyStops']);
  assert.deepStrictEqual(u('cuarteles de la policia').layers.map(h => h.id), ['lyPolice']);
  const s = u('salud en Santurce').places[0]; assert.deepStrictEqual([s.muni, s.lat != null], ['San Juan', true], 'an alias with its point');
  assert.strictEqual(u('desempleo en ponse').places[0].muni, 'Ponce', 'a municipio one edit away, after a word that places');
  assert.strictEqual(u('la pobreza y la cifra de los hombres').places.length, 0, '"la cifra" is not Cidra');
  assert.strictEqual(u('¿bajó el desempleo después de María?').time.since, 2017);
  assert.strictEqual(u('poverty overlapping with the pandemic').time.since, null, 'an event is a time only with its cue');
  assert.ok(u('¿bajó el desempleo después de María?').concepts.every(h => h.id !== 'hurricane'), 'the event is not a topic');
  assert.deepStrictEqual(u('¿dónde están los refugios de violencia doméstica?').sens.map(x => x.kind), ['dv']);
  assert.deepStrictEqual(u('¿dónde vive el alcalde de Ponce?').sens.map(x => x.kind), ['pii']);
  assert.deepStrictEqual(u('where do rich people live').sens, [], 'a group of people is not a person');
  assert.deepStrictEqual(u('ubicación de las clínicas de metadona').sens.map(x => x.kind), ['facility']);
  assert.strictEqual(u('¿qué es el margen de error?').explain.glossary, 'moe');
  { const e = u('what is the population of San Juan').explain; assert.ok(!e || (!e.glossary && !e.layer), 'a question about a value is not a definition'); }
  assert.strictEqual(A.correct('unemployement', ix), null, 'a form that its stem already reads (the rule takes unemploy*) needs no correction');
  assert.ok(A.coordinated('transporte y vivienda', { a: 0, b: 10 }, { a: 13, b: 21 }));
  assert.ok(!A.coordinated('rent of students', { a: 0, b: 4 }, { a: 8, b: 16 }), '"of" is not a list');
  assert.ok(!A.coordinated('people with disabilities', { a: 0, b: 6 }, { a: 12, b: 24 }) && A.coordinated('people with disabilities', { a: 0, b: 6 }, { a: 12, b: 24 }, true), '"with" joins two topics only in a question that relates them');
});

test('the lexicon names only datasets the engine has and layers the registry or the 3D view has; every proxy and missing note has both languages', () => {
  const X = R.engine(), page = (f) => [...fs.readFileSync(path.join(__dirname, '..', 'site', f), 'utf8').matchAll(/<input type="checkbox" id="(\w+)"/g)].map(m => m[1]);
  const ids = new Set([...LY.rows().map(r => r.id), ...page('index.html'), ...page('3d.html')]);   // the registry's layers and the switches of the Transit tab, the clock and the Time tab
  for (const id of ['lyStorms', 'lySupRoutes', 'lySupStops', 'lyGaps', 'lyXfer', 'lyNow']) assert.ok(ids.has(id), id);
  for (const c of A.CONCEPTS) {
    c.data.forEach(k => assert.ok(X.V[k], `${c.id}: ${k} is a dataset`));
    c.layers.forEach(id => assert.ok(ids.has(id), `${c.id}: ${id} is a layer`));
    for (const f of ['proxy', 'missing']) if (c[f]) assert.ok(c[f].es && c[f].en, `${c.id}: ${f} in both languages`);
    (c.near || []).forEach(k => assert.ok(X.V[k], `${c.id}: near ${k} is a dataset`));
    (c.related || []).forEach(id => assert.ok(ids.has(id), `${c.id}: related ${id} is a layer`));
    if (c.group) assert.ok(c.group.es && c.group.en, `${c.id}: group in both languages`);
    assert.ok(c.es.length && c.en.length, `${c.id}: words in both languages`);
  }
  for (const [id, keys] of Object.entries(A.LAYER_DATA)) { assert.ok(ids.has(id), id); keys.forEach(k => assert.ok(X.V[k], `${id}: ${k}`)); }
  for (const id of Object.keys(A.LAYER_WORDS)) assert.ok(ids.has(id), id);
  for (const [a, v] of Object.entries(A.ALIASES)) assert.ok(X.placeIndex(v[0]) >= 0, `${a}: ${v[0]} is a municipio`);
  const tour = A.CONCEPTS.findIndex(c => c.id === 'tourism'); assert.ok(A.CONCEPT.tourism.last && tour > A.CONCEPTS.findIndex(c => c.id === 'federal'), 'tourism after the other economy topics');
});

test('answers: two topics compose (a layer for one, the data of the other, their relation); a place and its point; layers alone; what is never drawn', async () => {
  let o = await ask('transporte y vivienda');
  assert.deepStrictEqual([o.intent, o.layers, o.data], ['show', ['lyRoutes', 'lyStops'], ['median_gross_rent']]);
  assert.deepStrictEqual(o.plan.relation, ['median_gross_rent', 'pop_walk_active_pct']);
  assert.match(o.text, /patrón, no una causa/);
  assert.match(o.text, /horarios programados/, 'transit is labeled as scheduled');
  o = await ask('Transportation and housing', 'en');
  assert.deepStrictEqual([o.lang, o.layers, o.data], ['en', ['lyRoutes', 'lyStops'], ['median_gross_rent']]);
  o = await ask('pobreza y escuelas en Ponce');
  assert.deepStrictEqual([o.data, o.select], [['poverty_pct', 'sch_open'], 'Ponce']);
  o = await ask('muestra las rutas de guagua'); assert.deepStrictEqual([o.intent, o.layers, o.data], ['layers', ['lyRoutes'], []]);
  o = await ask('zonas inundables en Toa Baja'); assert.deepStrictEqual([o.intent, o.layers, o.select], ['layers', ['lyFlood'], 'Toa Baja']);
  o = await ask('salud en Santurce'); assert.deepStrictEqual([o.select, !!(o.zoom && o.zoom.lat)], ['San Juan', true]);
  o = await ask('¿dónde están los refugios de violencia doméstica?'); assert.deepStrictEqual([o.intent, o.layers, o.data], ['sensitive', [], []]); assert.match(o.text, /nunca publica/);
  o = await ask('show me the HRSA health center locations', 'en'); assert.ok(o.data.includes('hc_sites') && !o.layers.length); assert.match(o.text, /never drawn as points/);
  o = await ask('¿dónde hay más tapones?'); assert.deepStrictEqual([o.intent, o.data], ['rank', ['commute_45plus_pct']]); assert.match(o.text, /Aproximación/);
  o = await ask('pobresa en mayaguez'); assert.deepStrictEqual([o.data, o.select], [['poverty_pct'], 'Mayagüez']); assert.match(o.text, /Leí «pobresa» como «pobreza»/);
  o = await ask('¿qué es el margen de error?'); assert.strictEqual(o.intent, 'explain'); assert.match(o.text, /90%/);
  o = await ask('salud'); assert.strictEqual(o.data[0], 'hc_sites', 'the topic\'s own dataset, the rule\'s (health-care jobs) as a chip'); assert.ok(o.follow.some(x => /Empleos: Cuidado de la salud/.test(x)));
});

test('the rules keep their answers: groups, the wording that says whose figure it is, a word of a dataset\'s phrase', async () => {
  for (const [q, data] of [['rent of students with children', ['median_gross_rent']], ['compare teenagers and children poverty', ['poverty_pct']], ['poverty of retirees with disabilities', ['poverty_pct']],
    ['compare women of the population with poverty', ['acs_female_pct', 'poverty_pct']], ['mental health shortage areas', ['hpsa_mh_short']], ['distance to a health center', ['hc_road_km']], ['propietarios con hipoteca y mujeres', ['owner_occupied_pct', 'acs_female_pct']]]) {
    const o = await ask(q, 'en'); assert.deepStrictEqual(o.data.filter((k, i, a) => a.indexOf(k) === i), data, q);
  }
});

test('3D: the same reading drives the columns and the layers, and the scene layers of the 3D view', async () => {
  let o = await ask('transporte y vivienda', 'es', '3d'); assert.deepStrictEqual([o.layers, o.data], [['lyRoutes', 'lyStops'], ['median_gross_rent']]);
  o = await ask('edificios en 3D', 'es', '3d'); assert.deepStrictEqual([o.intent, o.layers], ['layers', ['lyBuildings']]);
  o = await ask('guaguas moviéndose en el mapa', 'es', '3d'); assert.deepStrictEqual(o.layers, ['lyTrips']);
  o = await ask('edificios en 3D'); assert.ok(!o.layers.includes('lyBuildings'), 'the 2D map has no 3D buildings');
  o = await ask('ver el desempleo en 3D'); assert.ok(o.actions.includes('Ver en 3D'), 'the 2D answer offers the 3D view');
});

test('the development set and the check set pass at their recorded rates (docs/ask.md)', () => {
  const run = (set) => JSON.parse(require('child_process').execFileSync(process.execPath, [path.join(__dirname, 'ask_dev.js'), ...(set ? ['--set', set] : []), '--json', '-'], { encoding: 'utf8', maxBuffer: 1 << 26 }).split('\n').filter(l => l.startsWith('{"base"')).join('') || '{}');
  const dev = run(null), check = run('tests/ask_check.json');
  assert.ok(dev.rate >= 0.97, `development set: ${dev.rate}`);
  assert.ok(check.rate >= 0.9, `check set: ${check.rate}`);
});

// Review of PR #95 (2026-10-26): a person in crisis says it in the first person, or names the line; each gets the crisis reply (988, the Línea PAS) and is never a
// data wish. Data questions about deaths, and "matar" not said of oneself, are not a crisis.
test('crisis: first-person words and the lines named get the crisis reply, never a wish; data questions about deaths do not', async () => {
  const yes = { es: ['me quiero matar', 'no quiero vivir', 'quiero morir', 'me voy a matar', 'quiero quitarme la vida', 'tengo ganas de morir', 'no quiero seguir viviendo', 'línea PAS', '¿cuál es el teléfono de la línea PAS?', 'llamar al 988'],
    en: ['I want to die', "I don't want to live", 'I want to kill myself', 'I keep hurting myself', 'better off dead'] };
  const no = { es: ['¿cuántos centros de ASSMCA hay en Ponce?', 'centros de tratamiento de ASSMCA', 'muertes por accidentes de tránsito', 'mortalidad', 'mortalidad infantil en Ponce', 'matar mosquitos', 'quiero vivir en Ponce', 'me quiero mudar a Caguas'], en: ['traffic deaths', 'mortality rate', 'where do people want to live'] };
  for (const lang of ['es', 'en']) {
    const env = R.env({ lang, view: '2d' });
    for (const q of yes[lang]) {
      const o = await env.answer(q);
      assert.strictEqual(o.intent, 'crisis', q);
      assert.ok(/988/.test(o.text) && /1-800-981-0023/.test(o.text), `${q}: 988 and the Línea PAS`);
    }
    assert.deepStrictEqual(env.chat.chWish().map(w => w.q).filter(w => yes[lang].includes(w)), [], 'never on the wishlist');
    for (const q of no[lang]) assert.notStrictEqual((await env.answer(q)).intent, 'crisis', q);
  }
});

// Re-review of PR #95: the crisis words are read in context. A place one does not want to live in, a highway numbered 988 and people dying in a disaster are data
// questions; the first person stays a crisis.
test('crisis: PR-988 and "going to die in floods" are not a crisis; any "no quiero vivir" and the first person are', async () => {
  const yes = { es: ['no quiero vivir', 'no quiero vivir más', 'llamar al 988', 'no quiero vivir en este mundo', 'no quiero vivir con este dolor', 'no quiero vivir con esta tristeza', 'no quiero vivir por nada', 'no quiero seguir viviendo en esta vida', 'no quiero vivir aquí en la tierra', 'no quiero vivir en San Juan'], en: ["I'm going to die", 'I am going to die', 'call 988'] };
  const no = { es: ['tráfico en la PR-988', 'carretera 988'], en: ['how many people are going to die in floods', 'going to die in a hurricane', 'traffic on road 988'] };
  for (const lang of ['es', 'en']) {
    const env = R.env({ lang, view: '2d' });
    for (const q of yes[lang]) assert.strictEqual((await env.answer(q)).intent, 'crisis', q);
    for (const q of no[lang]) assert.notStrictEqual((await env.answer(q)).intent, 'crisis', q);
  }
});
