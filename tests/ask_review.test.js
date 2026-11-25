// "Ask the observatory": the second review of PR #79 (docs/ask.md, "Round 2"). Every example the review gave, as a regression test: real words and place
// names are never read as typos, stop words and words of the other language are not topics, a dataset shown in place of what was asked is labeled, survey
// estimates by barrio say when they are unreliable, what is never drawn says why, places are read beside topics, and the small fixes.
'use strict';
const test = require('node:test'), assert = require('node:assert');
const A = require('../site/js/ask.js');
const R = require('./ask_runtime');
const W = require('./ask_words');

const ENV = {};
const envOf = (lang = 'es', view = '2d') => ENV[lang + view] || (ENV[lang + view] = R.env({ lang, view }));
const ask = (q, lang = 'es', view = '2d') => envOf(lang, view).answer(q);
const shows = (o) => [...o.data, ...o.layers];

test('typos: real words and place names are never corrected; a municipio only after a word that places it or as the whole question; never into an alarm topic', async () => {
  const ix = (await envOf('es').chat.chAskModule()).ix;
  for (const w of ['guayabal', 'catalina', 'maraguez', 'cayaguas', 'guayabo', 'cidral', 'shopping', 'tienes', 'trees', 'salsa', 'critical', 'cancelar', 'horse', 'computer', 'elevation', 'policy', 'preciso', 'estacionales'])
    assert.strictEqual(A.correct(w, ix, { muni: true }), null, w);
  for (const [w, c] of [['pobresa', 'pobreza'], ['desempelo', 'desempleo'], ['hopsitales', 'hospitales']]) assert.strictEqual(A.correct(w, ix), c, w);
  assert.ok(/^historic/.test(A.correct('historical', ix) || ''), 'another form of the same word is still read');
  assert.strictEqual(A.correct('bayamom', ix), null, 'a municipio is not a correction by itself');
  assert.strictEqual(A.correct('bayamom', ix, { muni: true }), 'bayamon');
  assert.deepStrictEqual(A.fix('bayamom', ix).fixes, [['bayamom', 'bayamon']], 'the whole question is the municipio');
  assert.deepStrictEqual(A.fix('Santa Catalina', ix).fixes, [], '"Santa Catalina" is not "Santa Carolina"');
  for (const q of ['shopping malls in Bayamón', 'trees in San Juan', 'salsa', 'critical facilities', 'cancelar', 'horse riding', 'computer access', 'elevation in Utuado', '¿qué tienes?']) {
    const o = await ask(q, /in |access|riding|facilities|trees/.test(q) ? 'en' : 'es');
    assert.deepStrictEqual(o.plan && o.plan.fixes, [], q + ': no word corrected');
    assert.ok(!shows(o).some(k => /^crime|^cms_hospitals_er|hpsa|commute_|median_gross_rent|lyHubs|lyRoutes/.test(k)), q + ': ' + shows(o).join(','));
  }
  for (const q of ['pobreza en Guayabal', 'Santa Catalina', 'desempleo en Maragüez', 'Cayaguas', 'Guayabo', 'Cidral']) {
    const o = await ask(q);
    assert.ok(!['Guayama', 'Carolina', 'Mayagüez', 'Caguas', 'Guaynabo', 'Cidra'].includes(o.select), q + ': ' + o.select);
  }
});

test('the list of protected words is current (node tests/ask_words.js writes it)', async () => {
  const words = await W.protectedWords();
  assert.deepStrictEqual([...A.PROTECTED].filter(Boolean).sort(), words);
});

test('stop words and the other language: "estas zonas", "911 calls", "what is this called?", "parking"', async () => {
  assert.ok(!(await ask('muéstrame estas zonas')).layers.includes('lyHubs'), '"estas" is not "estaciones"');
  let o = await ask('911 calls', 'en'); assert.ok(!o.data.includes('street_intersections') && !o.data.includes('street_intersection_density')); assert.strictEqual(o.lang, 'en');
  o = await ask('what is this called?', 'en'); assert.ok(!o.data.some(k => /street/.test(k)));
  o = await ask('parking', 'en'); assert.ok(!o.layers.includes('lyProt') && !o.data.includes('protected_land_pct'), '"parking" is not parks');
  assert.strictEqual(A.langOf(A.nrm('unemployment in Bayamón')), 'en');
  assert.strictEqual((await ask('unemployment in Bayamón', 'es')).lang, 'en', 'an accented place name does not make a question Spanish');
});

test('a dataset shown in place of what was asked says so (and the request goes on the wishlist); weak stand-ins are "not available" with the nearest data', async () => {
  const APPROX = /aproximaci[oó]n|approximation/i;
  for (const [q, lang] of [['air quality', 'en'], ['drug use', 'en'], ['valores de tasación del CRIM', 'es'], ['youth unemployment', 'en'], ['CDT en Ponce', 'es'], ['apagones de luz', 'es'], ['unemployment by month', 'en'], ['computer access', 'en']]) {
    const o = await ask(q, lang); assert.ok(APPROX.test(o.text), q + ': ' + o.text.slice(0, 200)); assert.ok(shows(o).length, q + ': something on the map');
  }
  { const o = await ask('storm surge', 'en'); assert.ok(!o.data.includes('nri_eal_hurricane'), 'storm surge is not wind loss'); assert.ok(o.data.includes('exp_surge_cat3_pop'), 'storm surge: NOAA\'s surge maps (exposure series)'); assert.ok(!APPROX.test(o.text), 'storm surge: no longer an approximation'); }
  { const o = await ask('marejada ciclónica', 'es'); assert.ok(o.data.includes('exp_surge_cat3_pop'), 'marejada ciclónica: the surge maps'); }
  { const o = await ask('internet speed', 'en'); assert.ok(o.data.some(k => k.startsWith('bb_')), 'internet speed: the FCC speed tiers (broadband_series.json), not the survey stand-in'); assert.ok(!APPROX.test(o.text), 'internet speed: no longer an approximation'); }
  for (const [q, lang] of [['electricity price', 'en'], ['ocupación hotelera', 'es'], ['building permits', 'en'], ['diabetes', 'es'], ['farmacias en Ponce', 'es'], ['salario mínimo', 'es']]) {
    const o = await ask(q, lang); assert.strictEqual(o.intent, 'nodata', q); assert.ok(/m[aá]s cercano|nearest/i.test(o.text), q + ': the nearest data');
    assert.ok(!o.data.length, q + ': no stand-in shaded');
  }
  assert.strictEqual((await ask('farmacias en Ponce')).select, 'Ponce', 'the place is still selected');
  const e = envOf('en'); await e.answer('electricity price'); assert.ok(e.chat.chWish().some(x => x.q === 'electricity price'), 'on the wishlist');
});

test('barrio estimates: unreliable ones are marked, and the first ones that are not distinguishable from the first say so', async () => {
  const o = await ask('¿qué barrios de Utuado tienen más pobreza?');
  assert.ok(/poco confiable/.test(o.text) && /estimados poco confiables/.test(o.text), o.text.slice(0, 300));
  assert.ok(/no se distingue/.test(o.text) || /se distingue estadísticamente/.test(o.text));
  const r = await ask('where is poverty highest?', 'en'); assert.ok(/statistically different/.test(r.text), 'municipio rankings with margins too');
});

test('what is never drawn says why, with a count where there is one, and never goes on the wishlist', async () => {
  const cases = [['names of students in Ponce', 'en', /names/, 'sch_enroll'], ['where do people with diabetes live', 'en', /health data/, null], ['home addresses in Caguas', 'en', /addresses/, null],
    ['homes that received FEMA aid', 'en', /which households/, 'fema_ia_households'], ['nombres de los hogares de ancianos', 'es', /no los nombra/, 'cms_nursing_homes'], ['short-term rental addresses', 'en', /private homes/, null], ['drug treatment near me', 'en', /location/, 'bh_all']];
  for (const [q, lang, re, k] of cases) {
    const e = envOf(lang), o = await e.answer(q);
    assert.strictEqual(o.intent, 'sensitive', q); assert.ok(re.test(o.text), q + ': ' + o.text.slice(0, 160));
    if (k) assert.ok(o.data.includes(k), q + ': ' + o.data);
    assert.ok(!e.chat.chWish().some(x => x.q === q), q + ': not a data wish');
  }
});

test('places are read beside the topics their words also name: El Yunque, Caño Martín Peña, the airport', async () => {
  let o = await ask('El Yunque'); assert.ok(o.zoom && Math.abs(o.zoom.lat - 18.31) < .05, 'zooms to El Yunque'); assert.ok(o.layers.includes('lyProt'));
  o = await ask('Caño Martín Peña'); assert.ok(o.zoom && o.select === 'San Juan');
  o = await ask('el aeropuerto'); assert.ok(o.zoom && o.select === 'Carolina' && o.layers.includes('lyHubs'));
  o = await ask('pasajeros del aeropuerto de Aguadilla'); assert.strictEqual(o.select, 'Aguadilla');
});

test('small fixes: counting words, clear as a command, "quita todas las capas", hurto, one sentence once, the trend\'s range, per-resident population, words that follow the signs', async () => {
  let o = await ask('¿cuántas personas tienen internet en Ponce?'); assert.ok(!o.data.includes('population') && !/correlaci/.test(o.text));
  for (const q of ['limpia las playas', 'clear water']) assert.notStrictEqual((await ask(q, /clear/.test(q) ? 'en' : 'es')).intent, 'clear', q);
  o = await ask('quita todas las capas'); assert.strictEqual(o.intent, 'clear'); assert.ok(envOf('es').rec.calls.some(c => c[0] === 'alloff'));
  assert.ok((await ask('hurto')).data.includes('crime_property'));
  o = await ask('trees in San Juan', 'en'); assert.strictEqual(o.text.split('no tree').length - 1, 1, 'the "not available" sentence once');
  o = await ask('¿cómo ha cambiado el desempleo desde 2015?'); assert.ok(/de 2015 a 20\d\d/.test(o.text), 'the About line gives the range');
  o = await ask('population per 1,000 residents', 'en'); assert.ok(!/per 1,000 residents[^.]*1,000\b/.test(o.text) && !o.modes.some(m => m[0] === 'population' && m[2]), 'not 1,000 everywhere');
  o = await ask('¿dónde más subió el desempleo?'); assert.ok(!/Más subieron[^.]*\(−/.test(o.text), 'a place that fell is not among those that rose');
  o = await ask('elevación en Jayuya'); assert.ok(/3D/.test(o.text) && o.select === 'Jayuya');
});

// ── Round 3 (the measurement of 98f7359): crisis topics, register, misspelt municipios, prices, barrio twins, more privacy kinds, stand-ins, names that are not places
test('crisis topics: no stand-in, no ranking, nothing shaded, the 988 line and the Línea PAS with its source, not a data wish; related data only as a labeled chip', async () => {
  for (const [q, lang] of [['suicidios en Ponce', 'es'], ['¿dónde hay más suicidios?', 'es'], ['tasa de suicidio por municipio', 'es'], ['¿en qué pueblos se quita la vida más gente?', 'es'], ['autolesión en jóvenes', 'es'], ['muertes por sobredosis', 'es'],
    ['how many suicides in Ponce', 'en'], ['suicide rates by town', 'en'], ['self-harm among teens', 'en'], ['overdose deaths by town', 'en']]) {
    const e = envOf(lang), o = await e.answer(q);
    assert.strictEqual(o.intent, 'crisis', q); assert.ok(!o.data.length && !o.layers.length, q + ': nothing shaded');
    assert.ok(lang === 'es' ? /llame o escriba al 988 \(marque 2 para español; o escriba AYUDA al 988\)/.test(o.text) : /call or text 988/.test(o.text), q);
    assert.ok(lang === 'es' ? /En Puerto Rico también puede llamar a la Línea PAS de ASSMCA al 1-800-981-0023 \(24 horas, gratis y confidencial\) o usar su chat en lineapas\.assmca\.pr\.gov\./.test(o.text)
      : /In Puerto Rico you can also call ASSMCA.{1,6}s Línea PAS at 1-800-981-0023 \(24 hours, free and confidential\) or use its chat at lineapas\.assmca\.pr\.gov\./.test(o.text), q + ': the Línea PAS beside 988');
    assert.ok(o.html.includes('href="https://assmca.pr.gov/"') && o.html.includes('href="https://lineapas.assmca.pr.gov/"'), q + ': both sources linked; assmca.pr.gov states every fact of the sentence (free and confidential too)');
    assert.ok(lang === 'es' ? /Fuente: ASSMCA \( ?assmca\.pr\.gov y lineapas\.assmca\.pr\.gov ?\), consultadas el 2026-10-21\./.test(o.text) : /Source: ASSMCA \( ?assmca\.pr\.gov and lineapas\.assmca\.pr\.gov ?\), checked 2026-10-21\./.test(o.text), q + ': the source line and the date checked');   // the runtime's text puts a space where a tag was
    assert.strictEqual((o.text.match(/1-800-981-0023/g) || []).length, 1, q + ': one number, no other 1-800 line');
    assert.ok(!/puesto|highest|lowest|más alto|más bajo/i.test(o.text), q + ': no ranking');
    assert.ok(/no responden|do not answer/.test(o.text), q + ': related data labeled as related');
    assert.ok(!e.chat.chWish().some(x => x.q === q), q + ': not a data wish');
  }
  assert.ok(!/\b(?:tu|ti)\b/.test(A.SENS_TEXT.nearMeTx.es) && /usted/.test(A.SENS_TEXT.nearMeTx.es), 'usted, as the rest of the chat');
  assert.ok(!/\b(?:tu|ti)\b/.test(A.SENS_TEXT.crisis.es) && /usted/.test(A.SENS_TEXT.crisis.es), 'the crisis reply in usted too');
  for (const [q, lang] of [['tratamiento de drogas cerca de mí', 'es'], ['drug treatment near me', 'en']]) {   // the treatment answer to "near me": findtreatment.gov, 988 and the Línea PAS, with its source (docs/ask.md, "Línea PAS")
    const o = await envOf(lang).answer(q);
    assert.strictEqual(o.intent, 'sensitive', q); assert.ok(/findtreatment\.gov/.test(o.text) && /988/.test(o.text), q + ': ' + o.text.slice(0, 200));
    assert.ok(/Línea PAS (?:de ASSMCA al|at) 1-800-981-0023 \((?:24 horas, gratis y confidencial|24 hours, free and confidential)\)/.test(o.text), q + ': the Línea PAS');
    assert.ok(o.html.includes('href="https://assmca.pr.gov/"') && o.html.includes('href="https://lineapas.assmca.pr.gov/"') && /(?:consultadas el|checked) 2026-10-21/.test(o.text), q + ': its sources');
  }
});

test('misspelt municipios after a placing word or at the end of a question with a topic; barrio names still protected', async () => {
  for (const [q, lang, p] of [['escuelas en Toa Vaja', 'es', 'Toa Baja'], ['schools in Toa Vaja', 'en', 'Toa Baja'], ['poverty Aguadila', 'en', 'Aguadilla'], ['pobreza en culbra', 'es', 'Culebra'], ['unemployment in Sabana Grnade', 'en', 'Sabana Grande']])
    assert.strictEqual((await ask(q, lang)).select, p, q);
  for (const q of ['pobreza en Guayabal', 'desempleo en Maragüez', 'pobreza en Cayaguas', 'escuelas en Santa Catalina', 'pobreza en Guayabo', 'pobreza en Cidral'])
    assert.ok(!['Guayama', 'Mayagüez', 'Caguas', 'Carolina', 'Guaynabo', 'Cidra'].includes((await ask(q)).select), q);
});

test('prices and values of homes are the home value; a barrio ranking uses the survey dataset with barrio values', async () => {
  for (const [q, lang] of [['precio de las casas', 'es'], ['house prices', 'en'], ['housing prices', 'en'], ['casas valen más', 'es'], ['¿cuánto cuesta una casa en Dorado?', 'es']]) {
    const o = await ask(q, lang); assert.ok(o.data.includes('median_home_value') && !o.data.includes('median_gross_rent'), q + ': ' + o.data);
  }
  const o = await ask('¿qué barrios de Ponce tienen más desempleo?');
  assert.ok(o.modes.some(m => m[0] === 'unemployment_rate_pct' && m[2] === 'barrio') && !/No hay valores por barrio/.test(o.text), o.text.slice(0, 200));
});

test('more privacy kinds say why; an official is not rated', async () => {
  for (const [q, lang, re] of [['hogares de crianza en Bayamón', 'es', /crianza/], ['albergues para menores en Ponce', 'es', /menores/], ['Hogar CREA en Caguas', 'es', /recuperación/], ['personas encamadas en Ponce', 'es', /encamadas/],
    ['¿dónde viven los dominicanos en San Juan?', 'es', /origen nacional/], ['foster homes in Ponce', 'en', /foster/], ['people who are bedridden in Caguas', 'en', /bedridden/], ['how many Haitians live in Carolina', 'en', /national origin/]]) {
    const o = await ask(q, lang); assert.strictEqual(o.intent, 'sensitive', q); assert.ok(re.test(o.text), q + ': ' + o.text.slice(0, 120));
  }
  let o = await ask('¿qué tan bueno es el alcalde de Ponce?'); assert.ok(/no evalúa a funcionarios electos/.test(o.text) && o.select === 'Ponce');
  o = await ask('is the mayor of San Juan doing a good job?', 'en'); assert.ok(/does not evaluate elected officials/.test(o.text));
});

test('stand-ins and false friends: rooftop solar, ER waits, dentists, cargo, free wifi, homes for sale, blue tarps, no-car households, solar farms, news media', async () => {
  for (const [q, lang] of [['rooftop solar', 'en'], ['placas solares en techos', 'es'], ['ER wait times', 'en'], ['cargo flights', 'en'], ['free wifi', 'en'], ['houses for sale', 'en'], ['toldo azul', 'es'], ['news media', 'en']]) {
    const o = await ask(q, lang); assert.strictEqual(o.intent, 'nodata', q); assert.ok(!o.data.length, q);
  }
  assert.ok(/aproximaci|approximation/i.test((await ask('dentists in Ponce', 'en')).text));
  let o = await ask('hogares sin carro'); assert.deepStrictEqual(o.data, ['no_vehicle_hh_pct']);
  o = await ask('solar farms', 'en'); assert.ok(o.data.includes('power_renewable_mw') && !o.data.includes('jobs_naics_11'));
});

test('names that are a municipio and something else: Florida the state, the Río Grande de Loíza river', async () => {
  let o = await ask('se muda a Florida'); assert.notStrictEqual(o.select, 'Florida'); assert.ok(/estado de EE\. UU\./.test(o.text));
  o = await ask('moving to Florida', 'en'); assert.notStrictEqual(o.select, 'Florida');
  o = await ask('inundaciones del Río Grande de Loíza'); assert.ok(!['Río Grande', 'Loíza'].includes(o.select) && /es un río/.test(o.text));
  assert.strictEqual((await ask('pobreza en Florida')).select, 'Florida', 'the municipio is still a place');
});

// ── Round 4 (the measurement of f414f75): the index built before the page's data, one place for the labels, more reasons, barrios named alone
test('the index waits for the page data: a chat opened before the Economy tab has loaded still reads misspelt municipios and the datasets\' own words', async () => {
  const e = R.env({ lang: 'es' }), api = e.api, places = api.places, datasets = api.datasets, ready = api.ready; let go;
  api.places = () => []; api.datasets = () => [];   // the page as it is when the chat opens: no municipio, no dataset yet
  api.ready = () => new Promise(ok => { go = () => { api.places = places; api.datasets = datasets; ok(true); }; });
  const m = e.chat.chAskModule();   // chToggle starts it as the chat opens
  await new Promise(r => setTimeout(r, 20)); (go || (() => { api.places = places; api.datasets = datasets; }))(); const M = await m; api.ready = ready;
  assert.ok(M && M.ix.munis.length === 78 && M.ix.docs.length > 300, 'the index holds the municipios and the datasets');
  for (const [q, p] of [['turismo en culbra', 'Culebra'], ['veteranos en aguadila', 'Aguadilla'], ['escuelas en Toa Vaja', 'Toa Baja']]) assert.strictEqual((await e.answer(q)).select, p, q);
  const e2 = R.env({ lang: 'en' }); e2.api.places = () => []; e2.api.ready = async () => false;
  assert.strictEqual(await e2.chat.chAskModule(), null, 'no data: no index kept, the next question builds it');
});

test('one place for the labels: every answer that shades a dataset for something the observatory lacks says so; one that lacks it leaves nothing on the map', async () => {
  const e = envOf('es');
  for (const [q, lang] of [['dentistas en Caguas', 'es'], ['tiempo de espera en sala de emergencia', 'es'], ['¿cuántos hogares reciben el PAN?', 'es'], ['how many households get food stamps', 'en'], ['apagones de luz', 'es'], ['dentists in Ponce', 'en'],
    ['residenciales públicos con más crimen', 'es'], ['public housing with the most crime', 'en'], ['¿dónde viven las personas que reciben cupones?', 'es'], ['homes of food stamp recipients', 'en']]) {
    const o = await ask(q, lang); assert.ok(o.data.length, q + ': shows a dataset'); assert.ok(/Aproximación|Approximation/.test(o.text), q + ': labeled: ' + o.text.slice(-200));
  }
  for (const [q, lang] of [['placas solares en las casas de Ponce', 'es'], ['rooftop solar on the houses of Ponce', 'en'], ['vuelos de carga', 'es']]) {
    const o = await ask(q, lang); assert.strictEqual(o.intent, 'nodata', q); assert.ok(!o.data.length && !o.data.includes('median_gross_rent'), q);
  }
  await e.answer('dentistas en Caguas'); const o = await e.answer('vuelos de carga', { keepState: true });   // as in the page: the earlier answer's datasets are taken off
  assert.ok(!o.data.length, 'nothing left on the map: ' + o.data);
  const d = await e.answer('¿dónde hay refugios de violencia doméstica?', { keepState: true }); assert.ok(!d.data.length && /nunca/.test(d.text));
});

test('more reasons: abortion services, short-term rental hosts, owners of abandoned homes, homes of aid recipients, crime below the municipio', async () => {
  for (const [q, lang, re, ok] of [['¿dónde hay clínicas de aborto?', 'es', /servicios de aborto/, []], ['abortion clinics in San Juan', 'en', /abortion services/, []],
    ['anfitriones de Airbnb en Rincón', 'es', /anfitriones/, ['seasonal_units', 'seasonal_pct']], ['Airbnb hosts in Rincón', 'en', /hosts/, ['seasonal_units', 'seasonal_pct']],
    ['dueños de las casas abandonadas en Ponce', 'es', /dueños/, ['vacant_units', 'other_vacant_units']], ['addresses of abandoned homes in Santurce', 'en', /owners, names or addresses/, ['vacant_units', 'other_vacant_units']],
    ['casas de los que reciben el PAN en Bayamón', 'es', /privada/, ['poverty_pct']], ['where do people on welfare live in Caguas', 'en', /private/, ['poverty_pct']],
    ['casas que recibieron ayuda de FEMA', 'es', /privada/, ['fema_ia_households']], ['homes of FEMA aid recipients', 'en', /private/, ['fema_ia_households']]]) {
    const o = await ask(q, lang); assert.strictEqual(o.intent, 'sensitive', q); assert.ok(re.test(o.text), q + ': ' + o.text.slice(0, 160));
    assert.ok(o.data.every(k => ok.includes(k)), q + ': only counts by municipio: ' + o.data); assert.ok(!o.layers.length, q + ': no layer');
    assert.ok(!/r = |patr[oó]n|pattern/.test(o.text), q + ': no relation drawn');
  }
  assert.ok(!/Sitios de centros|Health center sites/.test((await ask('¿dónde hay clínicas de aborto?')).text), 'no list of health centers');
  for (const [q, lang] of [['¿cuántos hogares recibieron ayuda de FEMA?', 'es'], ['which municipios get the most federal aid', 'en'], ['names of the municipios with the most vacant homes', 'en'], ['¿qué pueblos reciben más ayuda federal?', 'es']])
    assert.notStrictEqual((await ask(q, lang)).intent, 'sensitive', q + ': a count or a place is not a person');
  for (const [q, lang, re] of [['residenciales públicos con más crimen', 'es', /solo se publica por municipio/], ['public housing with the most crime', 'en', /only published by municipio/], ['¿qué barrios de Ponce tienen más crimen?', 'es', /solo se publica por municipio/]]) {
    const o = await ask(q, lang); assert.ok(o.data.every(k => /^crime_/.test(k)) && o.data.length, q + ': ' + o.data); assert.ok(re.test(o.text), q);
  }
});

test('a barrio named alone: its value by barrio and the map at the barrio; a name of several barrios: one chip per municipio; words and aliases are not barrios', async () => {
  let o = await ask('pobreza en Guayabal');
  assert.strictEqual(o.intent, 'barrio'); assert.strictEqual(o.select, 'Juana Díaz'); assert.ok(o.modes.some(m => m[0] === 'poverty_pct' && m[2] === 'barrio'));
  assert.ok(o.zoom && Math.abs(o.zoom.lat - 18.081) < .01 && o.zoom.z >= 13, 'the map at the barrio'); assert.ok(/Guayabal \(Juana Díaz\)/.test(o.text) && !/los datos son del municipio/.test(o.text));
  o = await ask('unemployment in Guayabal', 'en'); assert.ok(o.modes.some(m => m[0] === 'unemployment_rate_pct' && m[2] === 'barrio') && /from the survey/.test(o.text), 'the survey twin by barrio');
  o = await ask('ingreso en Cuchillas'); assert.ok(o.follow.filter(c => /^ingreso en Cuchillas, /.test(c)).length === 3, o.follow); assert.strictEqual(o.select, null);
  o = await ask('ingreso en Cuchillas, Morovis'); assert.strictEqual(o.select, 'Morovis'); assert.strictEqual(o.intent, 'barrio');
  o = await ask('Guayabal'); assert.strictEqual(o.select, 'Juana Díaz');
  for (const q of ['escuelas en el pueblo', 'pobreza en la playa', 'pobreza en Ponce', 'pobreza en Rincón', 'El Yunque', 'pobreza en Santurce']) assert.notStrictEqual((await ask(q)).intent, 'barrio', q);
  for (const [q, lang] of [['Transportation and housing', 'en'], ['transporte y vivienda', 'es'], ['pobreza en Ponce', 'es'], ['zonas inundables en Toa Baja', 'es'], ['¿qué barrios de Ponce tienen más pobreza?', 'es']]) {   // the crosswalk (161 KB) only for a question that may name a barrio
    const e = R.env({ lang }); await e.answer(q); assert.ok(!e.chat.CH.barrios, q + ': the crosswalk is not read');
  }
});

// ── Round 4b (the measurement of f0deed2): a barrio's words are a place, never a topic; a topic before a missing word keeps its dataset; misspelt two-word municipios
test('a barrio whose name is also a word of a topic ("barrio Playa de Ponce", "Montaña", "Río", "Pueblo", "Llanos", "Costa"): the barrio, never the topic', async () => {
  for (const [q, p, k] of [['pobreza en el barrio Playa de Ponce', 'Ponce', 'poverty_pct'], ['poverty in barrio Playa, Ponce', 'Ponce', 'poverty_pct'], ['ingreso en el barrio Montaña de Aguadilla', 'Aguadilla', 'median_hh_income'],
    ['pobreza en el barrio Río de Guaynabo', 'Guaynabo', 'poverty_pct'], ['desempleo en el barrio Pueblo de Moca', 'Moca', 'unemployment_rate_pct'], ['pobreza en el barrio Llanos de Lajas', 'Lajas', 'poverty_pct'],
    ['ingreso en el barrio Costa de Lajas', 'Lajas', 'median_hh_income'], ['pobreza en el barrio Palmas de Cataño', 'Cataño', 'poverty_pct'], ['pobreza en el barrio Centro de Moca', 'Moca', 'poverty_pct']]) {
    const o = await ask(q, /^poverty/.test(q) ? 'en' : 'es');
    assert.strictEqual(o.intent, 'barrio', q); assert.strictEqual(o.select, p, q); assert.ok(o.modes.some(m => m[0] === k && m[2] === 'barrio'), q + ': ' + JSON.stringify(o.modes));
    assert.ok(!(o.plan.missing || []).length && !/playas|beach/i.test(o.text), q + ': no missing topic');
  }
  let o = await ask('pobreza en el barrio Playa'); assert.ok(o.follow.filter(c => /, /.test(c)).length >= 4, 'five barrios named Playa: chips');
  for (const q of ['pobreza en Playita', 'pobreza en el barrio Playita']) { o = await ask(q); assert.ok(o.data.includes('poverty_pct'), q + ': the poverty stays'); }
});

test('a topic before a word the observatory lacks keeps its dataset, labeled; a word of the missing topic\'s phrase after it does not', async () => {
  for (const [q, k] of [['pobreza en la playa', 'poverty_pct'], ['desempleo en la playa', 'laus_unemp_rate'], ['escuelas cerca de los centros comerciales', 'sch_open'], ['ingreso cerca del mall', 'median_hh_income']]) {
    const o = await ask(q); assert.ok(o.data.includes(k), q + ': ' + o.data); assert.ok(/Aproximación/.test(o.text), q + ': labeled');
  }
  for (const [q, lang] of [['placas solares en las casas de Ponce', 'es'], ['rooftop solar on the houses of Ponce', 'en']]) assert.strictEqual((await ask(q, lang)).intent, 'nodata', q);
});

test('two-word municipios misspelt (alone, with a stop word, with a real word); the reading is said; rent that is paid is rent; where vacant homes are is a count', async () => {
  for (const [q, p] of [['Toa Vaja', 'Toa Baja'], ['Juana Dias', 'Juana Díaz'], ['desempleo en Juana Dias', 'Juana Díaz'], ['pobreza en Las Pierdas', 'Las Piedras'], ['escuelas en Toa Vaja', 'Toa Baja']]) {
    const o = await ask(q); assert.strictEqual(o.select, p, q); assert.ok(/Leí «[a-z ]+» como «/.test(o.text), q + ': the reading is said');
  }
  for (const q of ['pobreza en las escuelas', 'pobreza en los llanos']) assert.ok(!['Las Piedras', 'Las Marías'].includes((await ask(q)).select), q);
  for (const [q, lang] of [['¿cuánto se paga de alquiler en Ponce?', 'es'], ['¿cuánto se paga de renta en Caguas?', 'es'], ['how much do people pay in rent in Ponce', 'en']]) {
    const o = await ask(q, lang); assert.ok(o.data.includes('median_gross_rent') && !o.data.includes('qcew_avg_pay'), q + ': ' + o.data);
  }
  assert.ok((await ask('¿cuánto paga un empleo en Ponce?')).data.includes('qcew_avg_pay'), 'pay is still pay');
  for (const [q, lang] of [['dónde están las casas vacías', 'es'], ['where are the vacant homes', 'en']]) { const o = await ask(q, lang); assert.notStrictEqual(o.intent, 'sensitive', q); assert.ok(o.data.some(k => /vacan/.test(k)), q); }
  assert.strictEqual((await ask('direcciones de las casas vacías en Ponce')).intent, 'sensitive', 'addresses still say why');
});
