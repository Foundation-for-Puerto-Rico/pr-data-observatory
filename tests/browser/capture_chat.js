/* Capture script for the chat ("Ask the observatory"), which reads the Economy tab through ECON.api (plan item 6 regression harness; see capture_economy.js and README.md).
   Run it on index.html:

     eval(await (await fetch('http://127.0.0.1:8099/s/capture_chat.js')).text())                                                          */
(async () => {
  const TAG = location.port === '8022' ? 'old' : 'new', LANG = new URLSearchParams(location.search).get('lang') || 'es';
  const wait = (ms) => new Promise(r => setTimeout(r, ms));
  const post = (name, obj) => fetch('http://127.0.0.1:8099/save?name=' + name, { method: 'POST', body: JSON.stringify(obj) }).then(r => r.json());
  if (!(await ECON.api.ready())) return { error: 'the economy data did not load' };
  const wishKey = typeof CH_WISH_KEY !== 'undefined' ? CH_WISH_KEY : null; if (wishKey) localStorage.removeItem(wishKey);
  const Q = [
    'show poverty by municipality', 'which municipalities have the highest median rent', 'compare poverty and unemployment', 'is rent higher where income is higher?',
    'trend of jobs since 2015', 'tourism jobs per 1,000 residents', 'what is the population of San Juan', 'what data is missing?', 'show me flood zones', 'rank jobs per employed resident',
    'federal awards per capita', 'which datasets are about housing', 'what is the correlation between unemployment and poverty?', 'show median household income in 2018',
    'what is the average pay in Ponce', 'where are the most lodging listings', 'how many people live in poverty in Vieques', 'show everything about Humacao',
    'muestra la pobreza por municipio', '¿qué municipios tienen más empleos?', 'compara el alquiler y el ingreso', 'tendencia del desempleo desde 2012', '¿qué datos faltan?',
    'ingreso mediano en Mayagüez', 'empleos en turismo por cada 1,000 residentes', 'limpia el mapa',
  ];
  const out = { tag: TAG, lang: LANG, env: { width: innerWidth, mobile: typeof isMobile === 'function' ? isMobile() : null }, answers: {}, states: {} };
  const last = () => { const m = [...document.querySelectorAll('#chLog .ch-msg.bot')].pop(); return m ? m.innerHTML.replace(/data-id="\d+"/g, 'data-id="#"') : null; };
  for (const q of Q) {
    ECON.api.clear(); Chat.state.ctx = { keys: [], year: null, muni: null };
    await Chat.ask(q); await wait(250);
    out.answers[q] = last(); out.states[q] = ECON.api.state();
  }
  // the tools the chat uses, called directly
  out.tools = {};
  try { out.tools.search = Chat.tools.search_datasets({ query: 'poverty', limit: 6 }); } catch (e) { out.tools.search = 'error ' + e.message; }
  try { out.tools.rank = await Chat.tools.rank({ key: 'median_gross_rent' }); } catch (e) { out.tools.rank = 'error ' + e.message; }
  try { out.tools.correlate = await Chat.tools.correlate({ a: 'poverty_pct', b: 'laus_unemp_rate' }); } catch (e) { out.tools.correlate = 'error ' + e.message; }
  if (wishKey) localStorage.removeItem(wishKey);
  out.missed = (window.I18N && I18N.missed) ? [...I18N.missed] : null;
  const saved = await post(`${TAG}_chat_${LANG}`, out);
  return { saved, answers: Object.keys(out.answers).length, missed: out.missed };
})()
