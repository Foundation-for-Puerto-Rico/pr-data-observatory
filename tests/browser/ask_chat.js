// "Ask the observatory" in a real browser (docs/ask.md): the chat's understanding layer (site/js/ask.js) on the 2D map and the 3D view, in each language and width.
// It asks a question of each kind and checks what the page then shows: the layer switches and the "layers on" chip, the Economy tab's layers (shaded by barrio
// for a ranking of barrios), the selected municipio, the 3D columns and scene, the text of the answer; "Turn all off" and Undo after a chat answer; the 2D answer's
// "See in 3D" hand-over (3d.html#ask=), no horizontal scroll, a clean console and no missing Spanish.
//   chrome --headless=new --remote-debugging-port=<port> --user-data-dir=<a scratch folder>      (CDP_PORT=<port>)
//   node tests/browser/serve_gzip.js site 8041
//   node tests/browser/ask_chat.js [base URL, default http://127.0.0.1:8041] [folder for screenshots] [langs, default es,en] [widths, default 1400,390]
// Exit code: 0 when every check passed, 1 when one failed, 2 on an error.
const fs = require('fs'), path = require('path');
const { openPage } = require('./cdp.js');
const base = process.argv[2] || 'http://127.0.0.1:8041', shots = process.argv[3] || '', langs = (process.argv[4] || 'es,en').split(','), widths = (process.argv[5] || '1400,390').split(',').map(Number);
const problems = []; let passed = 0;
const check = (ok, what) => { if (ok) passed++; else problems.push(what); console.log(`  ${ok ? 'ok  ' : 'FAIL'} ${what}`); return ok; };
const view = (w) => ({ width: w, height: w < 500 ? 812 : 900, mobile: w < 500 });
const Q = {
  es: { yunque: 'El Yunque', trees: 'árboles en San Juan', nearest: /más cercano/, allOff: 'quita todas las capas', two: 'transporte y vivienda', routes: 'muestra las rutas de guagua', barrios: '¿qué barrios de Ponce tienen más pobreza?', typo: 'pobresa en mayaguez', flood: 'zonas inundables en Toa Baja', dv: '¿dónde están los refugios de violencia doméstica?', term: '¿qué es el margen de error?', buildings: 'edificios en 3D', storms: 'huracanes desde 1851', never: /nunca/, approx: 'apagones de luz', approxWord: /Aproximación/ },
  en: { yunque: 'El Yunque', trees: 'trees in San Juan', nearest: /nearest/, allOff: 'turn off all layers', two: 'Transportation and housing', routes: 'show the bus routes', barrios: 'which barrios of Ponce have the most poverty', typo: 'poberty in mayaguez', flood: 'flood zones in Toa Baja', dv: 'where are the domestic violence shelters?', term: 'what is the margin of error?', buildings: '3D buildings', storms: 'hurricane tracks since 1851', never: /never/, approx: 'power outages', approxWord: /Approximation/ },
};
async function shot(p, name) {
  if (!shots) return;
  const r = await p.send('Page.captureScreenshot', { format: 'png' });
  fs.writeFileSync(path.join(shots, `ask_${name}.png`), Buffer.from(r.data, 'base64'));
}
const LAST = `(() => { const m = [...document.querySelectorAll('#chLog .ch-msg.bot')].pop(); return m ? m.textContent.replace(/\\s+/g, ' ') : ''; })()`;
const ON = (ids) => `${JSON.stringify(ids)}.every(id => document.getElementById(id) && document.getElementById(id).checked)`;
async function ask(p, q) {
  const before = await p.eval(`document.querySelectorAll('#chLog .ch-msg.bot').length`);
  await p.eval(`Chat.ask(${JSON.stringify(q)})`);
  await p.waitFor(`!Chat.state.busy && document.querySelectorAll('#chLog .ch-msg.bot').length > ${before}`, 60000);
  await new Promise(r => setTimeout(r, 400));
  return p.eval(LAST);
}
async function map2d(lang, w) {
  const label = `2D ${lang} ${w}`, t = Q[lang]; console.log(label);
  const p = await openPage(`${base}/index.html?lang=${lang}`, view(w));
  try {
    await p.waitFor(`document.getElementById('chBtn') && typeof ECON !== 'undefined'`, 60000);
    await p.eval(`localStorage.setItem('twin.wishlist.v1', '[]')`);
    await p.eval(`document.getElementById('chBtn').click()`);
    check(await p.waitFor(`typeof Chat !== 'undefined' && document.body.classList.contains('chat-open')`, 60000), `${label}: the chat opens`);
    let a = await ask(p, t.two);
    check(await p.waitFor(ON(['lyRoutes', 'lyStops']), 20000), `${label}: "${t.two}" switches on the routes and the stops`);
    check(await p.eval(`ECON.api.state().layers.some(l => l.key === 'median_gross_rent')`), `${label}: and shades the rent`);
    check(await p.eval(`ActiveLayers.list().some(i => i.id === 'lyRoutes') && ActiveLayers.list().some(i => /^ec/.test(i.id))`), `${label}: the chip lists the routes and the rent`);
    check(/r = /.test(a) && /(patrón|pattern)/.test(a), `${label}: the answer gives the relation, as a pattern`);
    await shot(p, `2d_${lang}_${w}_two`);
    // Turn all off, then Undo
    const n0 = await p.eval(`ActiveLayers.count()`);
    await p.eval(`document.getElementById('alChip').click()`); await p.waitFor(`!document.getElementById('alPanel').hidden`, 5000);
    await p.eval(`document.querySelector('#alPanel .al-all').click()`);
    check(await p.waitFor(`ActiveLayers.count() === 0`, 10000), `${label}: "Turn all off" takes the chat's layers off`);
    await p.waitFor(`document.getElementById('toastAct') && !document.getElementById('toastAct').hidden`, 5000);
    await p.eval(`document.getElementById('toastAct').click()`);
    check(await p.waitFor(`ActiveLayers.count() === ${n0}`, 10000), `${label}: Undo puts them back (${n0})`);
    a = await ask(p, t.routes);
    check(await p.waitFor(ON(['lyRoutes']), 10000) && /GTFS/.test(a), `${label}: "${t.routes}" switches the routes on and says they are timetables`);
    a = await ask(p, t.flood);
    check(await p.waitFor(ON(['lyFlood']), 10000), `${label}: "${t.flood}" switches the flood zones on`);
    a = await ask(p, t.barrios);
    check(await p.waitFor(`typeof EC !== 'undefined' && EC.layers.some(l => l.key === 'poverty_pct' && l.level === 'barrio')`, 30000), `${label}: "${t.barrios}" shades the poverty by barrio`);
    check(await p.eval(`ECON.api.state().selected === 'Ponce'`) && /Ponce/.test(a), `${label}: and ranks the barrios of Ponce`);
    await shot(p, `2d_${lang}_${w}_barrios`);
    a = await ask(p, t.typo);
    check(await p.eval(`ECON.api.state().selected === 'Mayagüez' && ECON.api.state().layers.some(l => l.key === 'poverty_pct')`), `${label}: "${t.typo}" reads the typo (poverty in Mayagüez)`);
    a = await ask(p, t.approx);
    check(t.approxWord.test(a), `${label}: "${t.approx}" says it is an approximation`);
    const drawn = await p.eval(`ActiveLayers.count()`);
    a = await ask(p, t.dv);
    check(t.never.test(a) && (await p.eval(`ActiveLayers.count()`)) <= drawn && (await p.eval(`ECON.api.state().layers.length`)) === 0, `${label}: "${t.dv}" says why and draws nothing (the earlier answer's datasets are taken off)`);
    a = await ask(p, t.term);
    check(/90/.test(a), `${label}: "${t.term}" gives the glossary's definition`);
    // the crisis reply and the treatment answer to "near me": 988 and the Línea PAS of ASSMCA, with its source linked (docs/ask.md, "Línea PAS")
    const PAS = lang === 'es' ? /Línea PAS de ASSMCA al 1-800-981-0023 \(24 horas, gratis y confidencial\)/ : /Línea PAS at 1-800-981-0023 \(24 hours, free and confidential\)/;
    const PASLINK = `(() => { const m = [...document.querySelectorAll('#chLog .ch-msg.bot')].pop(); return !!m && ['https://assmca.pr.gov/', 'https://lineapas.assmca.pr.gov/'].every(u => [...m.querySelectorAll('a')].some(x => x.href === u && x.target === '_blank' && /noopener/.test(x.rel))); })()`;
    for (const q of lang === 'es' ? ['tasa de suicidio por municipio', 'tratamiento de drogas cerca de mí'] : ['suicide rates by town', 'drug treatment near me']) {
      a = await ask(p, q);
      check(/988/.test(a) && PAS.test(a) && /ASSMCA \(assmca\.pr\.gov (?:y|and) lineapas\.assmca\.pr\.gov\), (?:consultadas el|checked) 2026-10-21/.test(a) && await p.eval(PASLINK), `${label}: "${q}" gives 988 and the Línea PAS, with both sources linked (${a.slice(0, 80)})`);
      check(await p.eval(`![...[...document.querySelectorAll('#chLog .ch-msg.bot')].pop().querySelectorAll('.ch-acts a')].some(x => /^3d\\.html/.test(x.getAttribute('href')))`), `${label}: "${q}" offers no 3D view (review of PR #95)`);
    }
    for (const q of lang === 'es' ? ['hospitales cerca de mí', 'me quiero matar', 'no quiero vivir en este mundo', 'no quiero vivir con este dolor', 'no quiero vivir con esta tristeza', 'no quiero vivir por nada', 'no quiero seguir viviendo en esta vida', 'no quiero vivir aquí en la tierra', 'no quiero vivir en San Juan'] : ['hospitals near me', 'I want to die']) {   // "near me" and the first person: no 3D link either
      a = await ask(p, q);
      check(await p.eval(`![...[...document.querySelectorAll('#chLog .ch-msg.bot')].pop().querySelectorAll('.ch-acts a')].some(x => /^3d\\.html/.test(x.getAttribute('href')))`) && (/cerca|near/.test(q) ? /ubicaci|location/.test(a) : /988/.test(a)), `${label}: "${q}": its reply, no 3D view (${a.slice(0, 60)})`);
    }
    check(await p.eval(`!JSON.parse(localStorage.getItem('twin.wishlist.v1') || '[]').some(w => /quiero|die/.test(w.q))`), `${label}: no crisis message is on the wishlist`);
    // round 2 (docs/ask.md): a place beside a topic, a real word that is not a typo, "not available" with the nearest layers, and "turn all layers off"
    a = await ask(p, t.yunque);
    check(await p.waitFor(ON(['lyProt']), 10000) && await p.waitFor(`(() => { const c = map.getCenter(); return Math.abs(c.lat - 18.31) < .03 && Math.abs(c.lng + 65.79) < .03; })()`, 6000), `${label}: "${t.yunque}" goes to El Yunque and switches the protected areas on`);
    a = await ask(p, t.trees);
    check(!/I read|Leí/.test(a) && await p.waitFor(ON(['lyProt']), 10000) && t.nearest.test(a), `${label}: "${t.trees}" is not a typo: not available, the nearest layers on`);
    a = await ask(p, t.allOff);
    check(await p.waitFor(`ActiveLayers.count() === 0`, 10000), `${label}: "${t.allOff}" turns every layer off`);
    const links = await p.eval(`[...document.querySelectorAll('#chLog a.btn')].map(x => x.getAttribute('href'))`);
    check(links.some(h => h.startsWith(`3d.html?lang=${lang}#ask=`)), `${label}: an answer offers the 3D view with the question, in the page's language`);
    check(await p.eval(`document.documentElement.scrollWidth <= innerWidth + 1`), `${label}: no horizontal scroll`);
    await shot(p, `2d_${lang}_${w}_end`);
    await focusBack(p, label);
    const missed = await p.eval(`(I18N.missed ? [...I18N.missed] : [])`);
    check(lang === 'en' || !missed.length, `${label}: no Spanish missing (${missed.slice(0, 5).join(' | ')})`);
    const errs = p.logs.filter(l => l.type === 'EXCEPTION' || l.type === 'error' || l.type === 'log.error');
    check(!errs.length, `${label}: a clean console (${errs.map(e => e.text).slice(0, 3).join(' | ')})`);
  } finally { await p.close(); }
}
// Round 4 (docs/ask.md): questions typed into the chat's box and sent with Enter, on a page just opened (the first question is asked before the Economy tab has loaded):
// a misspelt municipio selects it and moves the map there; every answer that shades a dataset for something the observatory lacks says "Aproximación", and one that
// lacks it leaves no dataset on the map; what is never drawn says why; a barrio named alone goes to that barrio, by barrio, or offers one chip per municipio.
const R4 = {
  es: { typos: [['turismo en culbra', 'Culebra'], ['veteranos en aguadila', 'Aguadilla'], ['escuelas en Toa Vaja', 'Toa Baja']],
    stand: ['dentistas en Caguas', 'vuelos de carga', 'tiempo de espera en sala de emergencia', 'placas solares en las casas de Ponce', 'paneles solares en los techos', 'carga aérea en Aguadilla', '¿cuántos hogares reciben el PAN?'],
    sens: [['¿dónde hay clínicas de aborto?', /aborto/, []], ['anfitriones de Airbnb en Rincón', /anfitriones/, ['seasonal_units', 'seasonal_pct']], ['dueños de las casas abandonadas en Ponce', /dueños/, ['vacant_units', 'other_vacant_units']],
      ['¿dónde viven las personas que reciben cupones?', /privada/, ['poverty_pct']], ['casas que recibieron ayuda de FEMA', /privada/, ['fema_ia_households']], ['residenciales públicos con más crimen', /solo se publica por municipio/, ['crime_type1']]],
    stops: [['Número de paradas de transporte colectivo en San Juan', 'transit_stops', 'San Juan', /1,186 \(puesto 1 de 78/], ['¿cuántos residentes viven cerca de una parada en Caguas?', 'pop_walk_active_pct', 'Caguas', /400 m/], ['transporte colectivo al trabajo', 'commute_transit_pct', null, /trabajo/]],
    barrio: 'pobreza en Guayabal', many: 'pobreza en Cuchillas', approx: /Aproximación/, none: /no tiene/, playa: 'pobreza en el barrio Playa de Ponce' },
  en: { typos: [['veterans in aguadila', 'Aguadilla'], ['tourism in culbra', 'Culebra'], ['schools in Toa Vaja', 'Toa Baja']],
    stand: ['dentists in Caguas', 'cargo flights', 'emergency room wait times', 'rooftop solar on the houses of Ponce', 'solar panels', 'air cargo in Aguadilla', 'how many households get food stamps'],
    sens: [['where are the abortion clinics?', /abortion/, []], ['Airbnb hosts in Rincón', /hosts/, ['seasonal_units', 'seasonal_pct']], ['who owns the abandoned houses in Ponce', /owners/, ['vacant_units', 'other_vacant_units']],
      ['homes of food stamp recipients', /private/, ['poverty_pct']], ['homes of FEMA aid recipients', /private/, ['fema_ia_households']], ['public housing with the most crime', /only published by municipio/, ['crime_type1']]],
    stops: [['how many bus stops in San Juan', 'transit_stops', 'San Juan', /1,186 \(1st highest of 78/], ['how many people live near a bus stop in Caguas?', 'pop_walk_active_pct', 'Caguas', /400 m/], ['take the bus to work', 'commute_transit_pct', null, /work/]],
    barrio: 'poverty in Guayabal', many: 'income in Cuchillas', approx: /Approximation/, none: /has no/, playa: 'poverty in barrio Playa, Ponce' },
};
async function typed(p, q) {   // the question typed into the box and sent with Enter, as a person does
  const before = await p.eval(`document.querySelectorAll('#chLog .ch-msg.bot').length`);
  await p.eval(`document.getElementById('chInput').focus()`);
  await p.send('Input.insertText', { text: q });
  for (const type of ['keyDown', 'keyUp']) await p.send('Input.dispatchKeyEvent', { type, key: 'Enter', code: 'Enter', windowsVirtualKeyCode: 13, nativeVirtualKeyCode: 13, ...(type === 'keyDown' ? { text: '\r' } : {}) });
  await p.waitFor(`!Chat.state.busy && document.querySelectorAll('#chLog .ch-msg.bot').length > ${before}`, 60000);
  await new Promise(r => setTimeout(r, 1200));   // the map's flight (0.8 s)
  return p.eval(LAST);
}
const NEAR = (lat, lng, d = .06) => `(() => { const c = map.getCenter(); return Math.abs(c.lat - ${lat}) < ${d} && Math.abs(c.lng - (${lng})) < ${d}; })()`;
const LASTCHIPS = `[...[...document.querySelectorAll('#chLog .ch-msg.bot')].pop().querySelectorAll('.ch-chips .chip')]`;
async function focusBack(p, label) {   // closing the chat (its close button, or Escape in the box) puts the keyboard focus back on the Ask button
  await p.eval(`document.getElementById('chClose').click()`);
  check(await p.waitFor(`!document.body.classList.contains('chat-open') && document.activeElement && document.activeElement.id === 'chBtn'`, 5000), `${label}: the close button gives the focus back to the Ask button`);
  await p.eval(`document.getElementById('chBtn').click()`);
  await p.waitFor(`document.body.classList.contains('chat-open') && document.activeElement && document.activeElement.id === 'chInput'`, 5000);
  for (const type of ['keyDown', 'keyUp']) await p.send('Input.dispatchKeyEvent', { type, key: 'Escape', code: 'Escape', windowsVirtualKeyCode: 27, nativeVirtualKeyCode: 27 });
  check(await p.waitFor(`!document.body.classList.contains('chat-open') && document.activeElement && document.activeElement.id === 'chBtn'`, 5000), `${label}: Escape gives the focus back to the Ask button`);
}
async function round4(lang, w) {
  const label = `2D ${lang} ${w} typed`, t = R4[lang]; console.log(label);
  const p = await openPage(`${base}/index.html?lang=${lang}`, view(w));
  try {
    await p.waitFor(`document.getElementById('chBtn') && typeof ECON !== 'undefined'`, 60000);
    await p.eval(`localStorage.setItem('twin.wishlist.v1', '[]')`);
    await p.eval(`document.getElementById('chBtn').click()`);
    check(await p.waitFor(`typeof Chat !== 'undefined' && document.body.classList.contains('chat-open')`, 60000), `${label}: the chat opens`);
    const cw = await p.eval(`fetch('data/geo/crosswalk.json').then(r => r.json()).then(c => { const F = Object.fromEntries(c.fields.map((f, i) => [f, i])), m = (n) => c.units.municipio.find(r => r[F.name_es] === n), b = c.units.barrio.find(r => r[F.norm] === 'guayabal'); return { b: [b[F.lat], b[F.lng]], m: Object.fromEntries(${JSON.stringify(t.typos.map(x => x[1]))}.map(n => [n, [m(n)[F.lat], m(n)[F.lng]]])) }; })`);
    for (const [q, muni] of t.typos) {
      const a = await typed(p, q), [lat, lng] = cw.m[muni];
      check(await p.eval(`ECON.api.state().selected === ${JSON.stringify(muni)} && ECON.api.state().layers.length > 0`) && await p.waitFor(NEAR(lat, lng, .15), 4000), `${label}: "${q}" selects ${muni} and moves the map there (${a.slice(0, 60)})`);
    }
    for (const q of t.stand) {
      const a = await typed(p, q), n = await p.eval(`ECON.api.state().layers.length`);
      check(n ? t.approx.test(a) : t.none.test(a), `${label}: "${q}": ${n ? 'shades a dataset and says it is an approximation' : 'not available, and no dataset left on the map'} (${a.slice(0, 80)})`);
    }
    for (const [q, why, ok] of t.sens) {
      const a = await typed(p, q), keys = await p.eval(`ECON.api.state().layers.map(l => l.key)`);
      check(why.test(a) && keys.every(k => ok.includes(k)), `${label}: "${q}" says why, and shows only counts by municipio (${keys.join(', ') || 'nothing'})`);
    }
    for (const [q, key, muni, rx] of t.stops) {   // the stops rules of PR #8 (Maite Barragán): the count with its rank, residents within a 400 m walk, transit to work
      const a = await typed(p, q), st = await p.eval(`(() => { const s = ECON.api.state(); return { keys: s.layers.map(l => l.key), sel: s.selected || null, stops: !!(document.getElementById('lyStops') || {}).checked }; })()`);
      check(st.keys[0] === key && (!muni || st.sel === muni) && (key === 'commute_transit_pct' || st.stops) && rx.test(a), `${label}: "${q}" shades ${key}${muni ? ' in ' + muni : ''} (${st.keys.join(', ')}; ${a.slice(0, 80)})`);
    }
    let a = await typed(p, t.barrio);
    check(await p.eval(`ECON.api.state().selected === 'Juana Díaz' && EC.layers.some(l => l.key === 'poverty_pct' && l.level === 'barrio')`) && await p.waitFor(NEAR(cw.b[0], cw.b[1], .03) + ` && map.getZoom() >= 12`, 4000) && /Guayabal/.test(a), `${label}: "${t.barrio}" goes to the barrio Guayabal (Juana Díaz), shaded by barrio`);
    a = await typed(p, t.playa);
    check(await p.eval(`ECON.api.state().selected === 'Ponce' && EC.layers.some(l => l.key === 'poverty_pct' && l.level === 'barrio')`) && /Playa \(Ponce\)/.test(a), `${label}: "${t.playa}": the barrio Playa of Ponce, by barrio, not the beaches`);
    a = await typed(p, t.many);
    const chips = await p.eval(`${LASTCHIPS}.map(c => c.textContent)`);
    check(chips.filter(c => /Cuchillas, /.test(c)).length >= 2, `${label}: "${t.many}" offers one chip per municipio (${chips.join(' | ')})`);
    const n0 = await p.eval(`document.querySelectorAll('#chLog .ch-msg.bot').length`);
    await p.eval(`${LASTCHIPS}.find(c => /Cuchillas, /.test(c.textContent)).click()`);
    await p.waitFor(`!Chat.state.busy && document.querySelectorAll('#chLog .ch-msg.bot').length > ${n0}`, 30000); await new Promise(r => setTimeout(r, 1200));
    check(await p.eval(`!!ECON.api.state().selected && EC.layers.some(l => l.level === 'barrio')`) && /Cuchillas/.test(await p.eval(LAST)), `${label}: a chip answers for that barrio`);
    await shot(p, `2d_${lang}_${w}_typed`);
    const missed = await p.eval(`(I18N.missed ? [...I18N.missed] : [])`);
    check(lang === 'en' || !missed.length, `${label}: no Spanish missing (${missed.slice(0, 5).join(' | ')})`);
    const errs = p.logs.filter(l => l.type === 'EXCEPTION' || l.type === 'error' || l.type === 'log.error');
    check(!errs.length, `${label}: a clean console (${errs.map(e => e.text).slice(0, 3).join(' | ')})`);
  } finally { await p.close(); }
}
async function view3d(lang, w) {
  const label = `3D ${lang} ${w}`, t = Q[lang]; console.log(label);
  const p = await openPage(`${base}/3d.html?lang=${lang}#ask=${encodeURIComponent(t.two)}`, view(w));
  try {
    check(await p.waitFor(`typeof Chat !== 'undefined' && !Chat.state.busy && document.querySelectorAll('#chLog .ch-msg.bot').length >= 2`, 90000), `${label}: the question handed over in #ask= is asked`);
    check(await p.waitFor(ON(['lyRoutes', 'lyStops']) + ` && document.getElementById('metric').value === '__any' && ENG.h === 'median_gross_rent'`, 30000), `${label}: the routes and stops on, rent on the columns`);
    check(!/ask=/.test(await p.eval('location.hash')), `${label}: the question is taken out of the address`);
    await shot(p, `3d_${lang}_${w}_two`);
    await p.eval(`document.getElementById('lyBuildings').checked = false; document.getElementById('lyBuildings').dispatchEvent(new Event('change'))`);
    let a = await ask(p, t.buildings);
    check(await p.waitFor(ON(['lyBuildings']), 10000), `${label}: "${t.buildings}" switches the 3D buildings on`);
    a = await ask(p, t.storms);
    check(await p.waitFor(ON(['lyStorms']), 10000), `${label}: "${t.storms}" switches the storm tracks on`);
    a = await ask(p, t.barrios);
    check(/Ponce/.test(a), `${label}: "${t.barrios}" answers for Ponce (the 3D columns are by municipio)`);
    check(await p.eval(`document.documentElement.scrollWidth <= innerWidth + 1`), `${label}: no horizontal scroll`);
    await shot(p, `3d_${lang}_${w}_end`);
    await focusBack(p, label);
    const missed = await p.eval(`(I18N.missed ? [...I18N.missed] : [])`);
    check(lang === 'en' || !missed.length, `${label}: no Spanish missing (${missed.slice(0, 5).join(' | ')})`);
    const errs = p.logs.filter(l => (l.type === 'EXCEPTION' || l.type === 'error' || l.type === 'log.error') && !/WebGL|GPU|context lost/i.test(l.text || ''));
    check(!errs.length, `${label}: a clean console (${errs.map(e => e.text).slice(0, 3).join(' | ')})`);
  } finally { await p.close(); }
}
// The pages without a map (docs/ask.md, "Pages without a map"): the same Ask button in the top bar, the chat loaded only on first use, a definition and a ranking answered
// in the chat, "what is this?" from what the page shows, and a map question that hands over to the 2D map ("Show on the map": index.html#ask=…), where the layers come on.
const PAGES = [['dictionary.html#housing.poverty_pct', 'dictionary'], ['data-management.html', 'datamgmt'], ['housing.html', 'housing'], ['wcrp.html', 'wcrp'], ['route-analysis.html', 'routes'], ['gii.html', 'gii'], ['profile.html?area=72113', 'profile']];
const QP = {
  es: { term: '¿qué es el margen de error?', rank: '¿Dónde es más alto el desempleo?', what: '¿Qué es esto?', map: 'muestra las rutas de guagua', show: 'Ver en el mapa', entry: /Población bajo el nivel de pobreza/, three: 'edificios en 3D' },
  en: { term: 'what is the margin of error?', rank: 'Where is unemployment highest?', what: 'What is this?', map: 'show the bus routes', show: 'Show on the map', entry: /Population below the poverty level/, three: '3D buildings' },
};
const MAPLINK = `(() => { const m = [...document.querySelectorAll('#chLog .ch-msg.bot')].pop(); const a = m && [...m.querySelectorAll('.ch-acts a')].find(x => /^(index|3d)\\.html[?#]/.test(x.getAttribute('href'))); return a ? { href: a.getAttribute('href'), text: a.textContent, primary: a.classList.contains('primary'), first: a === m.querySelector('.ch-acts > *') } : null; })()`;
async function pageAsk(file, name, lang, w) {
  const label = `${name} ${lang} ${w}`, t = QP[lang], [path0, hash] = file.split('#'); console.log(label);
  const p = await openPage(`${base}/${path0}${path0.includes('?') ? '&' : '?'}lang=${lang}${hash ? '#' + hash : ''}`, view(w));
  try {
    check(await p.waitFor(`!!document.getElementById('chBtn') && document.getElementById('chBtn').nextElementSibling === document.querySelector('.topbar .views')`, 30000), `${label}: the Ask button is in the top bar, before the views`);
    check(await p.eval(`typeof Chat === 'undefined' && ![...document.scripts].some(s => /js\\/(chat|ask|askpage)\\.js/.test(s.src))`), `${label}: the chat is not loaded before it is used`);
    await p.eval(`localStorage.setItem('twin.wishlist.v1', '[]')`);
    await p.eval(`document.getElementById('chBtn').click()`);
    check(await p.waitFor(`typeof Chat !== 'undefined' && document.body.classList.contains('chat-open') && document.activeElement && document.activeElement.id === 'chInput'`, 60000), `${label}: the chat opens, the focus in its box`);
    check(await p.eval(`ECON.api.mapless === true && document.querySelectorAll('#chLog .ch-msg.bot .ch-chips .chip').length >= 3`), `${label}: the page's own greeting and questions`);
    let a = await ask(p, t.term);
    check(/90/.test(a) && !(await p.eval(MAPLINK)), `${label}: "${t.term}" gives the glossary's definition, in the chat`);
    a = await ask(p, t.rank);
    const rank = await p.eval(MAPLINK);
    check(/Maricao/.test(a) && /26[.,]5/.test(a) && !!rank && rank.primary && rank.first && rank.text === t.show && /^index\.html(\?[^#]*)?#ask=/.test(rank.href), `${label}: "${t.rank}" ranks the municipios with their numbers, and offers "${t.show}" first`);
    a = await ask(p, t.what);
    if (name === 'dictionary') check(t.entry.test(a), `${label}: "${t.what}" explains the open entry (${a.slice(0, 60)})`);
    else check(a.length > 40 && a.includes(await p.eval(`document.querySelector('main h1, h1').textContent.replace(/\\s+/g, ' ').trim().slice(0, 20)`)), `${label}: "${t.what}" sums up the page (${a.slice(0, 60)})`);
    a = await ask(p, t.three);
    const three = await p.eval(MAPLINK);
    check(!!three && /^3d\.html(\?[^#]*)?#ask=/.test(three.href), `${label}: "${t.three}" offers the 3D view with the question`);
    a = await ask(p, t.map);
    const link = await p.eval(MAPLINK);
    const search = await p.eval('location.search');
    check(!!link && link.href === 'index.html' + search + '#ask=' + encodeURIComponent(t.map) && /GTFS/.test(a), `${label}: "${t.map}" names the layer, its source, and offers "${t.show}" with the question and the page's ${search}`);
    const PAS = lang === 'es' ? /Línea PAS de ASSMCA al 1-800-981-0023/ : /Línea PAS at 1-800-981-0023/;
    a = await ask(p, lang === 'es' ? 'tasa de suicidio por municipio' : 'suicide rates by town');
    check(/988/.test(a) && PAS.test(a) && !(await p.eval(MAPLINK)), `${label}: the crisis reply, 988 and the Línea PAS, with nothing to show on a map`);
    for (const q of lang === 'es' ? ['me quiero matar', 'tratamiento de drogas cerca de mí', 'hospitales cerca de mí'] : ['I want to die', 'drug treatment near me', 'hospitals near me']) {   // review of PR #95: a crisis or "near me" never gets a map button
      a = await ask(p, q);
      check(!(await p.eval(MAPLINK)) && (/cerca|near/.test(q) ? /ubicaci|location/.test(a) : /988/.test(a) && PAS.test(a)), `${label}: "${q}": its reply, and no map button (${a.slice(0, 60)})`);
    }
    check(await p.eval(`!JSON.parse(localStorage.getItem('twin.wishlist.v1') || '[]').some(w => /matar|die/.test(w.q))`), `${label}: a crisis is never on the wishlist`);
    a = await ask(p, lang === 'es' ? '¿dónde están los refugios de violencia doméstica?' : 'where are the domestic violence shelters?');
    check((lang === 'es' ? /nunca/ : /never/).test(a) && !(await p.eval(MAPLINK)), `${label}: a shelter is never drawn, and nothing is offered on the map`);
    check(await p.eval(`document.documentElement.scrollWidth <= innerWidth + 1`), `${label}: no horizontal scroll`);
    if (await p.eval(`!!document.querySelector('.ka-tabs')`)) check(await p.eval(`(() => { const t = document.querySelector('.toc').getBoundingClientRect(), c = document.getElementById('chat').getBoundingClientRect(); return innerWidth < 861 || c.top >= t.bottom - 1; })()`), `${label}: the Knowledge Area tabs stay in view above the chat`);
    await shot(p, `page_${name}_${lang}_${w}`);
    await focusBack(p, label);
    const missed = await p.eval(`(I18N.missed ? [...I18N.missed] : [])`);
    check(lang === 'en' || !missed.length, `${label}: no Spanish missing (${missed.slice(0, 5).join(' | ')})`);
    const errs = p.logs.filter(l => l.type === 'EXCEPTION' || l.type === 'error' || l.type === 'log.error');
    check(!errs.length, `${label}: a clean console (${errs.map(e => e.text).slice(0, 3).join(' | ')})`);
    if (!link) return;
    // the hand-over: the 2D map asks the question once it is ready, switches the routes on and takes the question out of the address
    const m = await openPage(`${base}/${link.href}`, view(w));
    try {
      check(await m.waitFor(`typeof Chat !== 'undefined' && !Chat.state.busy && document.querySelectorAll('#chLog .ch-msg.user').length === 1 && document.querySelectorAll('#chLog .ch-msg.bot').length >= 2`, 90000), `${label}: index.html#ask= asks the question on the 2D map`);
      check(await m.eval(`document.querySelector('#chLog .ch-msg.user').textContent === ${JSON.stringify(t.map)}`), `${label}: the same question, as text`);
      check(await m.waitFor(ON(['lyRoutes']), 10000), `${label}: the routes are on, on the 2D map`);
      check(!/ask=/.test(await m.eval('location.hash')), `${label}: the question is taken out of the address`);
      await shot(m, `page_${name}_${lang}_${w}_handover`);
      const errs2 = m.logs.filter(l => l.type === 'EXCEPTION' || l.type === 'error' || l.type === 'log.error');
      check(!errs2.length, `${label}: a clean console on the 2D map (${errs2.map(e => e.text).slice(0, 3).join(' | ')})`);
    } finally { await m.close(); }
    if (name !== 'dictionary') return;
    for (const [q, why] of [[lang === 'es' ? 'quita todas las capas' : 'turn off all layers', 'clear'], ['qwzx vbnm plkj', 'wish']]) {   // #ask= may come from any link: it never clears the map, it is never a wish
      const h = await openPage(`${base}/index.html?lang=${lang}#l=routes&ask=${encodeURIComponent(q)}`, view(w));
      try {
        await h.waitFor(`typeof Chat !== 'undefined' && !Chat.state.busy && document.querySelectorAll('#chLog .ch-msg.bot').length >= 2`, 90000);
        const said = await h.eval(LAST);
        if (why === 'clear') check(await h.eval(ON(['lyRoutes'])) && /enlace|link/.test(said), `${label}: "${q}" in a link does not clear the map (${said.slice(0, 60)})`);
        else check(await h.eval(`!JSON.parse(localStorage.getItem('twin.wishlist.v1') || '[]').some(w => w.q === ${JSON.stringify(q)})`), `${label}: a question in a link is not added to the wishlist`);
      } finally { await h.close(); }
    }
  } finally { await p.close(); }
}
(async () => {
  if (shots) fs.mkdirSync(shots, { recursive: true });
  if (process.env.ONLY_PAGES) { for (const lang of langs) for (const w of widths) for (const [f, n] of PAGES) await pageAsk(f, n, lang, w); console.log(`\n${passed} passed, ${problems.length} failed`); problems.forEach(x => console.log('  ' + x)); process.exit(problems.length ? 1 : 0); }
  for (const lang of langs) { if (!process.env.SKIP_TYPED) await round4(lang, widths[0]); if (process.env.ONLY_TYPED) continue; for (const w of widths) { await map2d(lang, w); await view3d(lang, w); for (const [f, n] of PAGES) await pageAsk(f, n, lang, w); } }
  console.log(`\n${passed} passed, ${problems.length} failed`); problems.forEach(x => console.log('  ' + x));
  process.exit(problems.length ? 1 : 0);
})().catch(e => { console.error(e); process.exit(2); });
