/* PR Data Observatory: "Ask the observatory" chat.

   What it is: an assistant that knows the observatory's datasets. You ask in English or Spanish; it finds the datasets, computes the answer from the real
   numbers (rankings, comparisons, trends, patterns across municipalities), puts the right layers on the map, and tells you what is missing.
   What it is not: a generative model. In this version every sentence it writes is built from computed facts, and nothing you type leaves your
   browser. Its rules (below) and its understanding layer (js/ask.js, loaded with the first question: a lexicon of everyday words, the layer registry,
   the glossary and well-known places; docs/ask.md) read the question. An optional language-model back end can be switched on later with TWIN_CHAT.endpoint (see the tool list at the end of this file);
   it would use the same tools, so answers stay grounded in the data.

   Long-term: the observatory's database only grows. The chat reads data/registry.json (what is published, how big) and data/wanted.json (candidate
   datasets), and it keeps a local wishlist of requests it could not answer, so gaps become a list the team can act on. */

// The chat speaks the page language (I18N.lang). Its ES / EN button can switch it for this visit only: nothing is saved, so the page language wins every time the page opens.
const CH = { open: false, log: [], ctx: { keys: [], year: null, muni: null }, ui: I18N.lang, wanted: null, registry: null, busy: false, lastLang: null, insights: null };
const CH_WISH_KEY = 'twin.wishlist.v1';
const chApi = () => window.ECON && window.ECON.api;
const chSearch = () => typeof location !== 'undefined' ? location.search : '';   // the page's ?lang=, kept in the links to the other views
const chMapless = () => !!(chApi() && chApi().mapless);   // a page without a map (askpage.js): answers in the chat, and "Show on the map" hands the question to the map

// ── Text (English and Spanish) ───────────────────────────────────────────────
const TX = {
  en: {
    title: 'Ask the observatory', beta: 'beta', close: 'Close the chat', send: 'Send', ph: 'Ask about the data…', clear: 'Clear conversation',
    hello: "Ask me about the data in the observatory: what exists, where something is highest, how two things relate, how it has changed, or ask for a map layer (bus routes, flood zones). I show each answer on the map. Everything I say is computed from the datasets loaded here, so I find patterns, not causes.",
    foot: 'Answers are computed in your browser from the observatory’s datasets. Nothing you type is sent anywhere.',
    chips: ['Where is unemployment highest?', 'Transportation and housing', 'What are the most interesting patterns?', 'Do jobs and pay move together?', 'Tell me about Ponce', 'What data is missing?'],
    working: 'Working…', loading: 'Loading the data…',
    sawYear: (y) => `Year set to ${y}.`,
    showing: 'On the map now', highest: 'Highest', lowest: 'Lowest', island: 'Puerto Rico', rank: 'Rank',
    noMatch: "I could not match that to a dataset in the observatory.", noted: 'I added your request to the data wishlist so the team can see what people ask for.', closest: 'Closest datasets I have:',
    wantedHit: 'On the list of datasets we could add:', askMissing: 'See everything that is missing',
    tryAsk: 'You could ask:',
    early: (k, y) => `${k} starts in ${y}; I used ${y}.`,
    near: (k, y, r) => `${k} has no ${r} value; I used ${y}.`,
    clearedMap: 'Map cleared.', clearedChat: 'Conversation cleared.',
    corr: (r, n, a, b, dir) => `Across ${n} municipalities, ${a} and ${b} ${dir} (correlation r = ${fmt(r, 2)}).`,
    together: 'rise together', apart: 'move in opposite directions', nolink: 'show little relationship',
    caveat: 'That is a pattern across places, not proof that one causes the other. Large places, small samples and survey noise can drive it.',
    outliers: (l) => `Biggest exceptions: ${l}.`,
    sources: 'Sources', defn: 'What it measures', years: 'Years', open: 'Open the full source details',
    actWorkbench: 'Open the workbench', actScatter: 'Show the scatter plot', actTrend: 'Show the trend chart', actInspect: 'Compare with Puerto Rico', actShow: 'Show on the map', actSources: 'Sources and definition', actCopy: 'Copy wishlist', actIssue: 'Open as a GitHub issue (review the text first)', actWish: 'Add to the wishlist',
    wishAdded: 'Added to the wishlist.', wishEmpty: 'The wishlist is empty.',
    table: 'Table, scrollable', copied: 'Copied.', copyFail: 'Copy did not work here; select the list in the chat instead.', noWanted: 'The wanted-data list did not load.', noInventory: 'The data inventory did not load.',
    oops: (m) => `Something went wrong (${m}). Try rephrasing, or open Explore directly.`,
    err: { 'no data': 'no data', 'too few places with both values': 'too few places with both values', 'no years': 'no years' },
  },
  es: {
    title: 'Pregunte al observatorio', beta: 'beta', close: 'Cerrar el chat', send: 'Enviar', ph: 'Pregunte sobre los datos…', clear: 'Borrar la conversación',
    hello: 'Pregúnteme sobre los datos del observatorio: qué hay, dónde algo es más alto, cómo se relacionan dos cosas, cómo ha cambiado, o pídame una capa del mapa (rutas de guagua, zonas inundables). Muestro cada respuesta en el mapa. Todo lo que digo se calcula con los datos cargados aquí, así que encuentro patrones, no causas.',
    foot: 'Las respuestas se calculan en su navegador con los datos del observatorio. Nada de lo que escribe se envía a ningún sitio.',
    chips: ['¿Dónde es más alto el desempleo?', 'Transporte y vivienda', '¿Cuáles son los patrones más interesantes?', '¿Empleos y salarios se mueven juntos?', 'Hábleme de Ponce', '¿Qué datos faltan?'],
    working: 'Trabajando…', loading: 'Cargando los datos…',
    sawYear: (y) => `Año cambiado a ${y}.`,
    showing: 'En el mapa ahora', highest: 'Más alto', lowest: 'Más bajo', island: 'Puerto Rico', rank: 'Posición',
    noMatch: 'No pude relacionar eso con un conjunto de datos del observatorio.', noted: 'Agregué su petición a la lista de datos deseados para que el equipo vea lo que la gente pregunta.', closest: 'Los conjuntos de datos más cercanos:',
    wantedHit: 'En la lista de datos que podríamos agregar:', askMissing: 'Ver todo lo que falta',
    tryAsk: 'Podría preguntar:',
    early: (k, y) => `${k} empieza en ${y}; usé ${y}.`,
    near: (k, y, r) => `${k} no tiene valor para ${r}; usé ${y}.`,
    clearedMap: 'Mapa limpio.', clearedChat: 'Conversación borrada.',
    corr: (r, n, a, b, dir) => `En ${n} municipios, ${a} y ${b} ${dir} (correlación r = ${fmt(r, 2)}).`,
    together: 'suben juntos', apart: 'se mueven en direcciones opuestas', nolink: 'casi no se relacionan',
    caveat: 'Es un patrón entre lugares, no prueba de que uno cause el otro. Los municipios grandes, las muestras pequeñas y la imprecisión de las encuestas pueden explicarlo.',
    outliers: (l) => `Mayores excepciones: ${l}.`,
    sources: 'Fuentes', defn: 'Qué mide', years: 'Años', open: 'Abrir los detalles de la fuente',
    actWorkbench: 'Abrir la mesa de trabajo', actScatter: 'Ver el diagrama de dispersión', actTrend: 'Ver la tendencia', actInspect: 'Comparar con Puerto Rico', actShow: 'Mostrar en el mapa', actSources: 'Fuentes y definición', actCopy: 'Copiar la lista', actIssue: 'Abrir como issue de GitHub (revise el texto)', actWish: 'Agregar a la lista',
    wishAdded: 'Agregado a la lista.', wishEmpty: 'La lista está vacía.',
    table: 'Tabla, desplazable', copied: 'Copiado.', copyFail: 'Aquí no funcionó la copia; seleccione la lista en el chat.', noWanted: 'No se pudo cargar la lista de datos deseados.', noInventory: 'No se pudo cargar el inventario de datos.',
    oops: (m) => `Algo salió mal (${m === 'data' ? 'datos' : m}). Reformule la pregunta o abra Explorar directamente.`,
    err: { 'no data': 'no hay datos', 'too few places with both values': 'hay muy pocos municipios con ambos valores', 'no years': 'no hay años disponibles' },
  },
};
const chTx = (lang) => TX[lang] || TX.en;
const chErr = (e, lang) => (chTx(lang).err || {})[e] || e;   // the short messages the tools return, in the language of the question

// ── Lexicon: words (English and Spanish, accents removed) → dataset ──────────
// Ordered from specific to general; a matched phrase is consumed so it cannot match twice. A value can be a function of the whole question.
// the HRSA words: a discipline named, "need met" and "priority score" (their own datasets), and the words that choose among the three disciplines
const HPSA_NAMED = (q) => /\b(mental|psychiatr\w*|psiquiatr\w*|dental|dentist\w*|dentistas?|primary care|atencion primaria)\b/.test(q);
const HPSA_ASKS = (q) => /\b(need met|percent of need|share of need|necesidad (?:[a-z]+ ){0,5}?cubierta|porcentaje de necesidad|cobertura de la necesidad|priority score|shortage score|puntuacion de prioridad|puntaje de prioridad)\b/.test(q);
const HPSA = (q, kind) => `hpsa_${/\b(dental|dentist\w*|dentistas?)\b/.test(q) ? 'dh' : /\b(mental|psychiatr\w*|psiquiatr\w*)\b/.test(q) ? 'mh' : 'pc'}_${kind}`;
const CONCEPTS = [
  // transit stops (ideas from PR #8 by Maite Barragán): residents near a stop are the 400 m walk to a stop with a current timetable, not the 10 km road distance to a health
  // centre, which took "near" from its own words; a count of stops is the stops dataset with its rank; transit to work is how people commute, not the jobs. Before the jobs rule ("trabajo").
  [/\b(?:near|nearby|close to|within (?:a )?(?:short )?walk(?:ing distance)? (?:of|to|from)|(?:in |at )?walking distance (?:of|to|from)|(?:within |a )?400 ?m(?:eters|etres|etros)? (?:of|from|de)|cerca(?:nos?|nas?)? (?:de|a)|a pie de|a poca distancia de|a (?:una )?distancia (?:a pie|caminable) de)\s+(?:(?:an?|the|una?|la|las|el|los|alguna)\s+)?(?:(?:(?:bus|transit|train)\s+)?stops?|(?:bus|transit|train)\s+stations?|paradas?|estaciones de (?:tren|guaguas?))(?:\s+(?:de|del)\s+(?:la\s+|el\s+|las\s+|los\s+)?(?:guaguas?|autobus\w*|tren(?: urbano)?|t\w*port\w*(?:\s+(?:colectivo|publico))?))?\b/, 'pop_walk_active_pct'],
  [/\b(?:(?:(?:bus|transit|train)\s+)?stops|(?:bus|transit|train)\s+stations|paradas|estaciones de (?:tren|guaguas?))(?:\s+(?:de|del)\s+(?:la\s+|el\s+|las\s+|los\s+)?(?:guaguas?|autobus\w*|tren(?: urbano)?|t\w*port\w*(?:\s+(?:colectivo|publico))?))?\b/, (n, m) => /\b(?:(?:number|count|total|amount)\s+of|how many|cuant[ao]s|numero\s+de|cantidad\s+de|total\s+de|most|more|fewest|fewer|least|mas|menos)\s+(?:(?:the|las|los)\s+)?$/.test(n.slice(0, m.index)) ? 'transit_stops' : null],   // a count or a ranking right before the stops; read on the text before them, not with a lookbehind (Safari before 16.4 cannot parse one), so the cue stays for the intent ("most", "fewest")
  [/\b(?:t\w*port\w*\s+(?:publico|publica|colec\w*)|guaguas?|autobus(?:es)?|public transport\w*|transit|bus(?:es)?|tren(?: urbano)?|trains?)\s+(?:al|para (?:ir|llegar) al|hacia el|para el|to|for)\s+(?:trabajo|work)\b|\b(?:al|to)\s+(?:trabajo|work)\s+(?:en|by|on|in)\s+(?:(?:el|la|the)\s+)?(?:t\w*port\w*\s+(?:publico|publica|colec\w*)|guaguas?|autobus(?:es)?|bus(?:es)?|transit|public transport\w*|tren|trains?)\b|\bcommut\w*\s+(?:by|on|via)\s+(?:the\s+)?(?:bus(?:es)?|transit|public transport\w*|trains?)\b/, 'commute_transit_pct'],
  [/\b(tourism|tourist|turismo|turistic\w*)\s+(places|listings|assets|supply|lugares|sitios|oferta)\b/, 'tourism_places'],
  [/\b(hotels?|lodging|accommodations?|hoteles|alojamientos?)\s+(places|listings)\b|\bairbnbs?\b/, 'lodging_places'],
  [/\b(restaurants?|bars?|cafes?|gastronomy|restaurantes)\s+(places|listings)\b/, 'gastronomy_places'],
  [/\battractions?\b|\batractivos?\b/, 'attractions_places'],
  [/\b(tourism|tourist|visitor economy|turismo|turistic\w*)\b/, 'tourism_jobs'],
  [/\b(hotels?|lodging|accommodations?|hoteles|alojamientos?|hospedaje)\b/, 'accommodation_jobs'],
  [/\b(restaurants?|restaurantes|food service|bars?|cafes?|gastronom\w*)\b/, 'food_service_jobs'],
  [/\b(bachelor\w*|college|degrees?|universit\w*|educational attainment|nivel educativo|grado universitario|educacion superior)\b|\beducation\b(?! (jobs?|sector|industry))/, 'bachelors_pct'],
  [/\bmanufactur\w*|manufactura\b/, 'jobs_naics_31_33'],
  [/\bconstruction\b|\bconstruccion\b/, 'jobs_naics_23'],
  [/\bretail\b|\bcomercio al detal\b/, 'jobs_naics_44_45'],
  [/\bwholesale\b|\bcomercio al por mayor\b/, 'jobs_naics_42'],
  [/\b(mobile (?:health )?vans?|unidades? moviles?)\b/, 'hc_vans'],   // HRSA health centers and shortage areas (health_series.json): before the generic health words below, which would take "salud" and "health care"
  [/\b(need met|percent of need|share of need|necesidad (?:[a-z]+ ){0,5}?cubierta|porcentaje de necesidad|cobertura de la necesidad)\b/, (q) => HPSA(q, 'met')],
  [/\b(priority score|shortage score|puntuacion de prioridad|puntaje de prioridad)\b/, (q) => HPSA(q, 'score')],
  [/\b(?:(?:clinicas?|clinics?)\s+(?:de\s+)?)?(mental health|salud mental|psychiatr\w*|psiquiatr\w*)(?: (?:clinics?|centers?|care|services|clinicas?|centros?|servicios|atencion))?(?!\s+(?:jobs?|work\w*|employ\w*|empleos?|trabaj\w*|salar\w*|pay\b))\b/, (q) => HPSA_ASKS(q) ? false : 'hpsa_mh_short'],
  [/\b(?:(?:clinicas?|clinics?)\s+(?:de\s+)?)?(dentists?|dental|dentistas?|dentales?|salud dental|salud oral)(?: (?:clinics?|centers?|care|services|clinicas?|centros?|servicios|atencion))?(?!\s+(?:jobs?|work\w*|employ\w*|empleos?|trabaj\w*|salar\w*|pay\b))\b/, (q) => HPSA_ASKS(q) ? false : 'hpsa_dh_short'],
  [/\b(?:(?:clinicas?|clinics?)\s+(?:de\s+)?)?(primary care|atencion primaria)(?: (?:clinics?|clinicas?))?(?!\s+(?:jobs?|work\w*|employ\w*|empleos?|trabaj\w*|salar\w*|pay\b))\b/, (q) => HPSA_ASKS(q) ? false : 'hpsa_pc_short'],
  [/\b(hpsa|health professional shortage|shortage areas?|areas? de escasez|escasez de (?:profesionales|personal|trabajadores) de (?:la )?salud)\b/, (q) => HPSA_NAMED(q) ? false : /\b(hpsa|health|salud|medic\w*|clinic\w*|physicians?|doctors?|nurs\w*|care)\b/.test(q) ? 'hpsa_pc_short' : null],   // the generic words name the primary care measure only in a question about health, and only when no discipline is named
  [/\b(?:(?:federally funded |federally qualified |community )?health ?centers?|federally qualified|look-?alikes?|fqhc|clinics?|centros? de salud(?: con fondos federales| federales)?|clinicas?)\b/, 'hc_sites'],
  [/\bhealth ?care\b|\bhospitals?\b|\bsalud\b|\bsocial assistance\b/, 'jobs_naics_62'],
  [/\beducation\w* (jobs?|sector|industry|services)|\bschool jobs\b|\bempleos en educacion\b/, 'jobs_naics_61'],
  [/\b(finance|financial|banking|banks?|insurance|finanzas|bancos?|seguros)\b/, 'jobs_naics_52'],
  [/\breal estate\b|\bbienes raices\b/, 'jobs_naics_53'],
  [/\b(professional services|scientific|servicios profesionales)\b/, 'jobs_naics_54'],
  [/\b(administrative|support services|waste management)\b/, 'jobs_naics_56'],
  [/\b(agricultur\w*|farming|farms?|fishing|forestry|agricola)\b/, 'jobs_naics_11'],
  [/\b(mining|quarr\w*|mineria)\b/, 'jobs_naics_21'],
  [/\butilities jobs?|\butilities sector\b/, 'jobs_naics_22'],
  [/(transportation|warehousing|logistics|logistica)\s+(jobs?|sector|industry|employment)|jobs in transportation/, 'jobs_naics_48_49'],
  [/\b(telecom\w*|publishing)\b|information (sector|jobs?)/, 'jobs_naics_51'],
  [/\bmedia\b/, (n, m) => /\bla $/.test(n.slice(0, m.index)) ? null : 'jobs_naics_51'],   // "la media" is the average
  [/\b(headquarters|corporate offices|management of companies)\b/, 'jobs_naics_55'],
  [/\b(arts|entertainment|recreation)\b/, 'jobs_naics_71'],
  [/\b(government|public sector|gobierno|sector publico)\b/, (q) => /share|dependen|percent|proporc|porcentaje|%/.test(q) ? 'gov_job_share_pct' : 'qcew_gov_jobs'],
  [/\b(private sector|private jobs?|sector privado|empleos privados)\b/, 'qcew_private_jobs'],
  [/\bfema\b/, (q) => /individual|household|housing|hogar|vivienda/.test(q) ? (/household|how many|hogares/.test(q) ? 'fema_ia_households' : 'fema_ia_amount') : 'fema_pa_obligated'],
  [/\b(federal|usaspending|fondos federales|federal funds?|federal money)\b/, (q) => /grants?|subvenciones/.test(q) ? 'fed_grants' : /contracts?|contratos/.test(q) ? 'fed_contracts' : /loans?|prestamos/.test(q) ? 'fed_loans' : /direct payments?|benefits|pagos directos/.test(q) ? 'fed_direct_payments' : 'fed_awards_total'],
  [/\b(total wages|payroll|nomina)\b/, 'qcew_wages'],
  [/\b(wages?|salar\w*|pay(?!\s+(?:for\s+)?(?:the\s+|in\s+)?(?:rent|mortgage))|paga(?!\s+(?:de|en|por|el|la)\s+(?:la\s+|el\s+)?(?:alquiler|renta|hipoteca))|sueldos?|earnings)\b/, 'qcew_avg_pay'],   // "¿cuánto se paga de alquiler?", "pay in rent": the rent, not pay
  [/\b(establishments?|businesses|business|firms|companies|negocios?|empresas?|establecimientos?)\b/, 'qcew_estabs'],
  [/\b(job cent(?:er|re)s?|bedroom communit\w*|jobs per (?:employed )?resident|centros? de empleo)\b/, 'jobs_per_employed_resident'],
  [/\b(diversif\w*|concentration|herfindahl|hhi|diversidad economica)\b/, 'industry_hhi'],
  [/\b(unemploy\w*|jobless\w*|desemple\w*|paro)\b/, (q) => /number|how many|count|cuant\w*|people|personas|cantidad/.test(q) ? 'laus_unemployed' : 'laus_unemp_rate'],
  [/\b(labou?r force|fuerza laboral|fuerza trabajadora)\b/, 'laus_labor_force'],
  [/\b(employment rate|employment.population|tasa de empleo|participation)\b/, 'employment_rate_pct'],
  [/\b(jobs?|employment|employ\w*|empleos?|puestos de trabajo|workplaces?|trabajos?)\b/, 'qcew_jobs'],
  [/\b(murders?|homicid\w*|asesinatos?)\b/, 'crime_murders'],
  [/\b(crimes?|criminal\w*|crimenes|delitos?|delincuencia)\b/, (q) => /violen/.test(q) ? 'crime_violent' : /propert\w*|propiedad|burglar\w*|theft|escalamiento|hurto|apropiacion/.test(q) ? 'crime_property' : 'crime_type1'],
  [/\b(poverty|poor|pobreza|pobres?|low income)\b/, 'poverty_pct'],
  [/\b(inequality|gini|desigualdad)\b/, 'gini'],
  [/\b(?:(?:median|average|mean) )?(?:household )?(?:income|incomes|ingresos?|rich|wealth\w*|affluen\w*|riqueza)\b/, (q) => /per.?capita/.test(q) ? 'per_capita_income' : /owner|propietari/.test(q) ? 'median_owner_income' : /renter|inquilino/.test(q) ? 'median_renter_income' : 'median_hh_income'],
  [/\bricos?\b/, (q, m) => /\bpuerto $/.test(q.slice(0, m.index)) ? null : /per.?capita/.test(q) ? 'per_capita_income' : /owner|propietari/.test(q) ? 'median_owner_income' : /renter|inquilino/.test(q) ? 'median_renter_income' : 'median_hh_income'],   // "ricos" (rich), not the "rico" of Puerto Rico
  [/\b(self.?employ\w*|autoemple\w*|cuenta propia|informal\w*)\b/, 'self_employed_pct'],
  [/\b(non.?profit\w*|sin fines de lucro)\b/, 'nonprofit_worker_pct'],
  [/\b(work(?:ing)? (?:from|at) home|remote work\w*|telework\w*|teletrabajo|trabajo remoto)\b/, 'work_from_home_pct'],
  [/\b(drive|drives|driving) alone\b|\bconducen solos\b/, 'commute_drive_alone_pct'],
  [/\b(no|without|sin|zero) (a )?(car|vehicle|vehiculo|carro|auto)s?\b|\bcar.?free\b/, 'no_vehicle_hh_pct'],
  [/\b(public transport\w*|transit (?:commut\w*|riders?|use|share)|transporte publico)\b/, 'commute_transit_pct'],
  [/\bwalk\w* to work\b|\bcamina\w* al trabajo\b/, 'commute_walk_pct'],
  [/\b(commut\w*|travel time|long trips? to work|viaje\w* al trabajo|desplazamiento)\b/, 'commute_45plus_pct'],
  [/\b(no|without|sin) (internet|broadband|banda ancha)\b|\boffline\b/, 'no_internet_pct'],
  [/\b(internet|broadband|banda ancha)\b/, 'internet_subscription_pct'],
  [/\bmedian age\b|\bedad mediana\b|\bedad promedio\b/, 'median_age'],
  [/\bresidents aged 65 and over\b|\bresidentes de 65 anos o mas\b/, 'age65_pct'],   // the whole label of the older dataset names it, not the survey's "People 65 and older"
  [/\b(?:people |persons |personas )?(?:aged )?65 (?:and|or|y|o) (?:older|over|mas)\b|\b65 anos o mas\b|\bmayores de 65\b/, 'acs_age65plus_pct'],
  [/\b(elderly|seniors?|older adults?|aging|ageing|envejecimiento|ancianos|adultos mayores|over 65|65\+)\b/, 'age65_pct'],
  [/\b(?:(?:military|war) )?(?:veterans?|veteran[oa]s?|ex.?militares)\b/, 'acs_veteran_pct'],
  [/\b(disabilit\w*|disabled|discapacidad\w*|discapacitad\w*|impedimentos?)\b/, 'acs_disability_pct'],
  [/\b(?:live|lives|living) alone\b|\b(?:one|single|1).?person households?\b|\bhouseholds? of (?:one|1) person\b|\bhouseholds? with (?:one|a single|1) person\b|\bviv\w* sol[oa]s?\b|\bpersonas? sol[oa]s?\b|\bhogares? (?:unipersonales|(?:de|con) (?:una|1) (?:sola )?persona)\b/, 'acs_living_alone_pct'],
  [/\bfamily households?\b|\bhogares familiares\b/, 'acs_family_households_pct'],
  [/\b(children|kids|minors|ninos|ninas|ninez|menores de (?:18|edad))\b|\bunder 18\b(?! min)/, 'acs_under18_pct'],
  [/\b(women and girls|women|females?|mujeres|femenin\w*)\b(?![ -]?(?:headed|owned)|\s+jefas|\s+propietarias|\s+duenas)/, 'acs_female_pct'],
  [/population (?:change|growth|loss|decline)|\b(growing|shrinking|depopulat\w*|crecimiento poblacional|perdida de poblacion)\b/, (q) => /2020/.test(q) ? 'pop_change_since_2020_pct' : 'pop_change_since_2010_pct'],
  [/\b(?:(?:survey|acs|encuesta)\s+(?:estimates?|estimados?)\s+(?:of|de)\s+(?:the\s+|la\s+)?(?:population|poblacion)|(?:population|poblacion)\s*\((?:survey|acs|encuesta)[^)]*\))/, 'acs_population'],
  [/\b(population|poblacion|habitantes|inhabitants)\b/, 'population'],
  [/\bowner (?:cost|burden)\b|\bowner.?cost.?burden\b/, 'owner_cost_burden_pct'],
  [/\b(rent|renter)s? ?(?:cost.?)?burden\w*|\bcost.?burden\w*|\bcarga (?:de costos|(?:de|del) (?:los )?alquiler(?:es)?)\b/, 'renter_cost_burden_pct'],
  [/\b(home values?|house prices?|home prices?|property values?|valor de (?:la )?vivienda|precio de (?:las )?casas?)\b/, 'median_home_value'],
  [/\b(rents?|rental|rentas?)\b/, 'median_gross_rent'],
  [/\baffordab\w*|\basequib\w*\b/, 'affordability_ratio'],
  [/\b(second homes?|vacation homes?|seasonal|short.?term rentals?|alquiler(?:es)? (?:a|de) corto plazo|alquiler(?:es)? vacacional\w*|estacional\w*|segundas viviendas)\b/, 'seasonal_pct'],
  [/\babandon\w*|\babandonad\w*/, 'other_vacant_pct'],
  [/\b(vacan\w*|empty homes?|vacantes)\b/, 'vacancy_pct'],
  [/\b(homeownership|home ownership|owner.?occupied|propietarios|own their homes?)\b/, 'owner_occupied_pct'],
  [/\b(overcrowd\w*|hacinamiento)\b/, 'overcrowded_pct'],
  [/\bmobile homes?\b/, 'mobile_home_pct'],
  [/\b(housing units|viviendas|housing stock)\b/, 'housing_units'],
  [/\b(households?|hogares)\b/, 'households'],
  // Spanish alquiler is the rent, as it is in "tendencia de alquileres", "mapa del alquiler" and "el alquiler". It only describes something else when the word before "de", "del", "en", "por" or "para" is a dataset that another rule already took
  // ("carga de costos de alquiler", "tasa de vacantes de alquiler", "asequibilidad del alquiler", "viviendas de alquiler") or a thing that is not rent ("casas de alquiler", "contratos de alquiler"): then the rule takes the word and names nothing. It runs last, so the heads are already taken.
  [/\balquiler(?:es)?\b/, (q, m) => {
    if (/^\s+asequibles?\b/.test(q.slice(m.index + m[0].length))) return false;   // "alquiler asequible" is the affordability (its rule takes it)
    const w = m.input, pm = /\b(?:de|del|en|por|para)\s+$/.exec(w.slice(0, m.index)); if (!pm) return 'median_gross_rent';
    const head = /([a-z0-9]+)\s*$/.exec(q.slice(0, pm.index)); if (!head) return 'median_gross_rent';
    return !/\S/.test(w.slice(head.index, head.index + head[1].length)) || /^(?:casas?|apartamentos?|unidades|propiedades|contratos?|subsidios?|edificios?|inmuebles?|inquilinos?|ayudas?|asistencias?|vales?|programas?|beneficios?)$/.test(head[1]) ? false : 'median_gross_rent';
  }],
];
const CH_CONTEXT = [[/\b(flood\w*|inundacion\w*|hazard\w*)\b/, 'lyFlood'], [/\b(transit routes?|bus routes?|rutas?)\b/, 'lyRoutes'], [/\b(protected areas?|parks?|areas protegidas)\b/, 'lyProt'], [/\bbarrios?\b/, 'lyBarrios'], [/\b(land use|zoning|uso de terrenos)\b/, 'lyLanduse'], [/\b(tourism places|attractions?|pins)\b/, 'lyPlaces'],
  // the point layers both views draw (docs/layers.md): the words that name them switch them on beside the answer's datasets ("muestra las estaciones de bomberos")
  [/\b(transit stops|bus stops|paradas)\b/, 'lyStops'], [/\b(stations,? terminals|terminals?|airports?|terminales|aeropuertos?|estaciones del tren urbano)\b/, 'lyHubs'], [/\b(taxis?|taxi stands?|ev charg\w*|electric vehicle charg\w*|carga de vehiculos electricos)\b/, 'lyTaxi'],
  [/\b(bridges?|puentes?|tunnels?|tuneles?)\b/, 'lyBridges'], [/\b(heliports?|helipuertos?|helipads?)\b/, 'lyAirports'], [/\b(ferr(y|ies)|ferry routes?|lanchas?|rutas? de lanchas?)\b/, 'lyFerries'],
  [/\b(ev charg\w*|electric vehicle charg\w*|charging stations?|carga de vehiculos electricos|estaciones de carga|cargadores? (de vehiculos )?electricos?)\b/, 'lyEvCharge'],
  [/\b(opportunity zones?|qualified opportunity zones?|zonas? de oportunidad|zonas? de oportunidades)\b/, 'lyOz'],
  [/\b(power plants?|power stations?|electric plants?|generating plants?|plantas? (de energia|electricas?|generatrices|de generacion)|centrales? electricas?)\b/, 'lyPlants'],
  [/\b(transmission lines?|power lines?|power grid|electric grid|grid lines?|lineas? de transmision|lineas? electricas?|red electrica|tendido electrico)\b/, 'lyPowerLines'],
  [/\b(public housing|vivienda publica|residencial(es)? public[oa]s?|(show|muestra|mostrar|ver) (the |los )?residenciales)\b/, 'lyPubHousing'], [/\b(tax credit housing|lihtc|low-income housing tax credits?|vivienda con credito contributivo|credito contributivo (de|para) vivienda)\b/, 'lyLihtc'], [/\b(reservoirs?|reservoir levels?|lakes? levels?|embalses?|niveles? de (los )?embalses|represas?)\b/, 'lyReservoirs'], [/\b((show|map|muestra|mostrar|ver|mapa de) (the |las |los )?(broadband|banda ancha) (gaps?|hexagons?|brechas?|hexagonos)|(broadband|banda ancha) (gaps?|brechas?) (on|en) (the |el )?mapa?|hexagonos de (la )?fcc|fcc hexagons?)\b/, 'lyBroadband'], [/\b(river (flows?|gauges?|gages?|levels?)|stream ?(flows?|gauges?|gages?)|rivers? (now|today)|caudal(es)?( de (los )?rios)?|nivel(es)? de (los )?rios|rios (ahora|hoy)|crecidas?)\b/, 'lyRivers'], [/\b(ground ?water( levels?| wells?)?|water table|aquifers?|wells? (now|today)|aguas? subterraneas?|nivel(es)? freaticos?|acuiferos?|pozos? de (agua|observacion))\b/, 'lyGroundwater'], [/\b(rain ?gau?ges?|rain ?fall (now|today|gau?ges?)|rain (now|today)|how much (did it )?rain(ed)?|lluvia (ahora|hoy|de hoy)|cuanto (ha llovido|llovio)|pluviometros?)\b/, 'lyRain'], [/\b(fire (and ems )?stations?|fire ?houses?|fire departments?|ems stations?|bomberos|parques? de bombas)\b/, 'lyFire'],
  [/\b(police( stations?)?|policias?|cuarteles?( de (la )?policia)?)\b/, 'lyPolice'], [/\b(city halls?|town halls?|alcaldias?)\b/, 'lyTownhalls'], [/\b(librar(y|ies)|bibliotecas?)\b/, 'lyLibraries'],
  [/\b(historic (places?|sites?|buildings?|districts?)|national register|lugares historicos|sitios historicos|edificios historicos|registro nacional)\b/, 'lyHistoric']];
const STOP = new Set('the a an of in on at to for and or with by is are was were be it its this that these those what which who where when how do does did show me map see plot display about tell give find please can could would you i we our us my mine from than then so as not no yes any all some more most less least highest lowest top bottom rank municipality municipalities municipio municipios island puerto rico pr data dataset datasets el la los las un una de del en y o con por para es son que cual cuales donde como muestra muestrame mostrar mapa ver dime sobre dato datos'.split(' '));

// ── Questions: language, years, places, intent ───────────────────────────────
function chLang(q, last) {
  const api = chApi(); if (api && api.places) for (const p of api.places()) if (/[^\x00-\x7f]/.test(p)) q = q.split(p).join(' ');   // "poverty in Mayagüez" is English
  const n = norm(q);
  const es = (n.match(/\b(escasez|dentistas?|salud|centros?|medicos?|doctor(?:es|as?)?|atencion|cuidado|puntaje|puntuacion|prioridad|psiquiatr\w*|necesidad|cubierta|hogar(?:es)?|mujeres|veteran[oa]s?|ninos|ninas|ancianos|discapacidad\w*|viven|vive|solas|jefatura|encabezados|muestr\w*|que|cual(?:es)?|donde|como|cuanto\w*|municipios?|desempleo|pobreza|ingresos?|empleos?|vivienda|alquiler|turismo|datos|fuentes?|compara\w*|entre|tienen|tiene|los|las|del|con|para|por|mas|menos|hay|falta\w*|ayuda|gracias|hola|quiero|puedes|anos?|hablame|dime|juntos|salarios?|sueldos?)\b/g) || []).length + (/[¿¡ñáéíóú]/i.test(q) ? 1 : 0);
  const en = (n.match(/\b(the|what|which|where|show|how|and|with|is|are|of|in|by|highest|lowest|data|tell|about|jobs?|compare|missing|patterns?|together|help|hello|hi|who|why|shortage|doctors?|health|clinics?|centers?|dentists?|need|score|priority)\b/g) || []).length;
  if (es > en) return 'es'; if (en > es) return 'en';
  return es > 0 ? 'es' : (last || 'en');
}
function chYears(n) {
  const ys = [...n.matchAll(/\b(20[0-2]\d)\b/g)].map(m => +m[1]);
  return ys;
}
function chPlaces(n) {
  const api = chApi(); if (!api) return { places: [], rest: n };
  const names = api.places().slice(0, -1).map(x => [x, norm(x)]).sort((a, b) => b[1].length - a[1].length);
  const found = []; let rest = n;
  for (const [orig, nm] of names) {
    const re = new RegExp('(^|[^a-z])' + nm.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + '(?![a-z])');
    const m = re.exec(rest); if (m) { found.push({ name: orig, pos: m.index }); rest = rest.slice(0, m.index + m[1].length) + ' '.repeat(nm.length) + rest.slice(m.index + m[1].length + nm.length); }
  }
  found.sort((a, b) => a.pos - b.pos);
  return { places: found.map(f => f.name), rest };
}
const JOBWORDS = (re) => new RegExp('(?:\\b(?:jobs?|employment|empleos?)\\s+(?:in|of|de|del|en)\\s+(?:the\\s+)?)?(?:' + re.source + ')(?:\\s+(?:jobs?|employment|workers?|empleos?|trabajos?|sector|industry))?');
// ── Who a figure is about ─────────────────────────────────────────────────────
// A group of people named beside another dataset says whose figure is wanted, not a second dataset: "poverty among women", "how many kids are in poverty", "women's poverty", "households headed by women".
// A category (who: women, children, older adults) qualifies an attribute (veterans, disability, living alone) and every other dataset; an attribute qualifies every other dataset.
// Two modes. A group that main had a dataset for (the elderly) keeps both datasets unless the wording is one of the plain ways to say whose figure it is, so nothing main answered is lost: nothing ("female unemployment"), a possessive ("women's poverty"),
// a preposition ("poverty among the elderly", "women in poverty", "pobreza entre mujeres"), "are in" ("how many kids are in poverty"), "headed by" ("households headed by women"). A group that main had no dataset for (women, children, veterans, disability, living alone,
// "65 and older") is the figure's group by default, whatever the words between, and the second layer is kept only when the question asks how the two relate ("compare", "and", "next to", "where", "places with more", "with the share of").
const CH_CATEGORY = new Set(['acs_female_pct', 'acs_under18_pct', 'acs_age65plus_pct', 'age65_pct']);
const CH_ATTRIBUTE = new Set(['acs_veteran_pct', 'acs_disability_pct', 'acs_living_alone_pct', 'acs_family_households_pct']);
const chLevel = (k) => CH_CATEGORY.has(k) ? 1 : CH_ATTRIBUTE.has(k) ? 2 : 3;
const CH_OF = { households: new Set(['acs_living_alone_pct', 'acs_family_households_pct']) };   // "hogares de personas solas", "households living alone": the household type is the dataset itself
const CH_TOTAL = new Set(['population', 'acs_population']);   // the population is what a group counts: "the elderly population", "veteran population" and "población con discapacidad" name the group's own dataset, so a group never qualifies them
const CH_OWN_NOUN = new Set('people persons person residents resident adults adult individuals individual those ones everyone everybody folks citizens citizen inhabitant islanders families family puerto ricans personas persona residentes residente gente adultos adulto individuos individuo ciudadanos ciudadano habitante familias familia quienes aquellos aquellas boricuas puertorriquenos puertorriquenas islenos islenas members member locals neighbors neighbours humans folk dwellers occupants miembros miembro vecinos vecino humanos'.split(' '));   // who a group is made of: the nouns before its name ("people with disabilities", "those who live alone") or after it ("female residents", "disabled people")
const CH_OWN_LINK = new Set('with who that which where of in on de del con que donde en sexo genero'.split(' '));   // the words that join those nouns to the name of the group
const CH_OWN_AUX = new Set('are have has having live lives living reside resides son tienen tiene viven vive viviendo residen sufren padecen estan a an un una the el la los las some any alguna'.split(' '));   // and the words inside it ("who are", "who have a", "que viven con")
const CH_OWN_STOP = new Set('but among amongst for by between entre para por to as like from'.split(' '));   // never a modifier of the name ("people with physical disabilities": physical is, "poverty among people with disabilities": among is not); the connectors ("and", "versus") are not modifiers either, by the list of words that connect
const CH_OWN_AGE = new Set('aged age over under above below older younger more less old years year anos ano edad mayores menores than'.split(' '));   // an age that stands next to the noun and a number ("persons aged 18 or more", "adults over 18")
const CH_OWN_DET = new Set('both ambos ambas'.split(' '));   // the words before the noun that belong to the phrase ("both people with disabilities", "ambos veteranos")
const CH_OWN_TAIL = /^\s+(?:(?:and|y)\s+(?:live|lives|living|reside|resides|viven|vive|residen)\s+(?:here|there|aqui|alli)|de guerra|en casa|en su casa|at home|years?|old|anos|de edad)\b/;   // what ends the name of a group ("veteranos de guerra", "viven solas en casa", "who are female and live here", "under 18 years old", "menores de 18 años de edad")
const chOwnTotal = (x) => CH_TOTAL.has(x.key) || x.key === 'households';   // the total that a group counts: the population for any group of people, the households for a group of households ("households living alone", "veteran households", "households living with a disability")
const CH_OWN_INTO = /^\s+(?:in|of|among|within|en|de|entre)\s+(?:(?:the|all|los|la|todos|toda)\s+)*/;   // what joins a group to the total that it counts ("veterans in the population", "mujeres de la poblacion")
function chWordsBefore(n, p, max = 20) {   // the words and numbers that end right before the position p with only white space between them, the nearest first
  const out = []; let e = p;
  while (out.length < max) {
    const base = Math.max(0, e - 80), m = /([a-zñ0-9]+)\s*$/.exec(n.slice(base, e));
    if (!m || /\S/.test(n.slice(base + m.index + m[1].length, e))) break;
    out.push({ w: m[1], a: base + m.index, b: base + m.index + m[1].length }); e = base + m.index;
  }
  return out;
}
function chPhraseStart(n, hits, h) {   // where the own words of a group begin: the farthest noun or total, with joining words, an age and at most two modifiers between it and the name ("people who live alone", "households in which people live alone", "population with a disability", "persons aged 18 or more who are veterans", "los que viven solos")
  let best = h.pos, mods = 0;
  const toks = chWordsBefore(n, h.pos);
  for (let i = 0; i < toks.length; i++) {
    const t = toks[i], x = hits.find(y => y !== h && y.pos <= t.a && t.b <= y.end);
    if (x) { if (chOwnTotal(x)) { best = t.a; continue; } break; }   // the total that the group counts is part of its phrase; any other dataset or group is not
    if (CH_OWN_NOUN.has(t.w) || (i > 0 && toks[i - 1].w === 'que' && /^(?:los|las)$/.test(t.w))) {   // "los que viven solos": those who live alone
      const left = toks[i + 1], d = left && hits.find(y => y.pos <= left.a && left.b <= y.end);
      if (d && CH_COMPARE_BEFORE.test(n.slice(0, d.pos))) break;   // "compare employed residents with children": the noun is the rest of the name of the dataset that is compared
      best = t.a; continue;
    }
    if (CH_OWN_AGE.has(t.w) || (t.w === 'or' && i + 1 < toks.length && /^\d+$/.test(toks[i + 1].w))) continue;   // an age: "aged 18 or more", "over 18"
    if (CH_OWN_LINK.has(t.w) || CH_OWN_AUX.has(t.w)) { if (h.key === 'acs_female_pct' && /^(?:with|con)$/.test(t.w)) break; continue; }   // "people with disabilities" is a phrase, "residents with women" is not
    if (mods < 2 && !CH_OWN_STOP.has(t.w) && !CH_LINKS_AT.test(n.slice(t.a, t.a + 40))) { mods++; continue; }   // a word that connects ("alongside") is not a modifier
    break;
  }
  for (const t of chWordsBefore(n, best)) { if (!CH_OWN_DET.has(t.w)) break; best = t.a; }
  return best;
}
function chPhraseEnd(n, hits, h) {   // where the group's phrase ends: the nouns or totals that follow its name ("disabled people", "female residents", "the veteran population"), and what closes the name ("veteranos de guerra", "viven solas en casa", "under 18 years old")
  let e = h.end;
  for (let k = 0; k < 3; k++) {
    const tail = CH_OWN_TAIL.exec(n.slice(e, e + 60)); if (tail) { e += tail[0].length; continue; }
    const into = CH_OWN_INTO.exec(n.slice(e, e + 40)), z = into && hits.find(y => y.pos === e + into[0].length && chOwnTotal(y)); if (z) { e = z.end; continue; }   // "veterans in the population"
    const m = /^\s+([a-zñ]+)/.exec(n.slice(e, e + 40)); if (!m) break;
    const a = e + m[0].length - m[1].length, b = e + m[0].length, x = hits.find(y => y !== h && y.pos <= a && b <= y.end);
    if (x ? chOwnTotal(x) : CH_OWN_NOUN.has(m[1])) e = b; else break;
  }
  return e;
}
const CH_JOIN = /^[\s,;&]*(?:(?:and|or|y|e|o|u|plus|also|too|as well as|asi como|tambien|ademas|who are|who is|that are|which are|que son|quienes son|particularly|especially|including|in particular|en particular|especialmente|incluyendo)\s+)*(?:(?:the|los|las|el|la|those|aquellos|aquellas)\s+)*$/;   // two groups joined by "and", "and the", "who are", "particularly" are one group
const CH_CONTRAST = 'vs\\.?|versus|against|contra|or (?:else|maybe|perhaps|even|rather|alternatively)|or|o (?:mas )?bien|o|u|ni|nor|and\\/or|\\/|v\\.?|rather than|instead of|(?:as )?opposed to|in contrast (?:to|with)|unlike|than|but not|and not|not including|not|other than|except for|except|excluding|apart from|aside from|whereas|while|otherwise than|otherwise|rather|different (?:from|than)|differently from|as against|contrasted (?:with|to)|contrary to|in place of|in lieu of|by contrast with|with the exception of|(?:as )?compared (?:with|to|against)|in comparison (?:with|to)|relative to|comparad[oa]s? (?:con|a|contra)|frente a(?:l)?|en contraste con|a diferencia d(?:e|el)|en vez d(?:e|el)|en lugar d(?:e|el)|con respecto a(?:l)?|respecto d(?:e|el)|respecto a(?:l)?|en comparacion con|mientras que|mientras|sino que|sino|distint[oa]s? d(?:e|el)|diferentes? (?:d(?:e|el)|a)|aparte d(?:e|el)|mas que|menos que|a excepcion d(?:e|el)|con excepcion d(?:e|el)|contrario a(?:l)?|al contrario d(?:e|el)|por el contrario|sin contar|excluyendo|en oposicion a(?:l)?|pero no|y no|excepto|salvo';   // what sets two groups against each other, or a group against its counterpart, or offers them as a choice
const CH_VS = new RegExp('^[\\s,;&]*(?:' + CH_CONTRAST + ')(?:\\s+(?:the|los|las|el|la|those|aquellos|aquellas|all|todos|todas))*(?:\\s+non-?)?[\\s,;&]*$');   // two groups against each other or offered as a choice ("one-person households versus family households poverty", "women compared to the children", "who has higher poverty, women or veterans") are a breakdown of the other dataset
const CH_NOUN = 'rates?|shares?|levels?|percentages?|percent|numbers?|counts?|figures?|index|ratios?|proportions?|totals?|trends?|maps?|values?|prices?|costs?|access|time|times|median|medians|average|mean|per|capita|incomes?|highest|lowest|higher|lower|greatest|largest|biggest|smallest|worst|best|tasas?|niveles|nivel|porcentajes?|cantidad|numero|cifras?|indice|proporcion|tendencias?|mapas?|valor|valores|precios?|costos?|acceso|tiempo|mediana|mediano|promedio|ingresos?|mas alta|mas alto|mas baja|mas bajo|mayor|menor|alta|alto|baja|bajo';   // what may stand between a dataset and the preposition: the rest of its name that its rule left, and a rank word
const CH_PREP = 'among|amongst|of|in|for|by|within|between|entre|de|del|en|para|por';
const CH_ART = 'the|a|an|all|los|las|el|la|todos|todas';
const CH_VERB = 'are|is|were|was|live|lives|living|viven|vive|estan|esta|son|es|who|that|que|quienes';
const CH_AFTER = new RegExp('^\\s*(?:(?:' + CH_NOUN + ')\\s+)*(?:(?:' + CH_PREP + ')\\s+(?:(?:' + CH_ART + ')\\s+)*|(?:headed|owned|run|led|encabezad[oa]s|dirigid[oa]s)\\s+(?:by|por)\\s+)?$');   // the gap when the group comes after the dataset
const CH_BEFORE = new RegExp('^(?:[\'’]s?\\s*|\\s*(?:(?:' + CH_VERB + ')\\s+)*(?:(?:' + CH_PREP + ')\\s+(?:(?:' + CH_ART + ')\\s+)*)?(?:(?:' + CH_NOUN + ')\\s+)*)$');   // and when it comes first
const CH_PAIR = /\b(relat\w*|correlat\w*|correlac\w*|versus|vs|against|together|compar\w*|relacion\w*|junt\w*|contra|asocia\w*|overlay|overlap\w*|scatter|plot|chart|graf\w*|side by side|lado a lado|superpon\w*|sobrepon\w*|connect\w*|conect\w*|link|associat\w*)\b/;   // a question that relates two things keeps both
const CH_EXPLICIT = /\b(among|amongst|entre|headed|owned|encabezad\w*|jefatura)\b/;   // unless it says whose figure it is in so many words
const CH_CMP = /\b(?:compar\w*|contrast\w*|versus|vs|against|contra|correlat\w*|correlac\w*|overlay\w*|overlap\w*|scatter\w*|plot|chart|graph\w*|graf\w*|side by side|lado a lado|superpon\w*|sobrepon\w*|connect\w*|conect\w*|link|associat\w*|asocia\w*|pair\w*|match\w*|combin\w*|juxtapos\w*|mix\w*|relate|relates|related|line(?:s|d)? up|empare\w*|cruz\w*|relacion\w*|vincul\w*)\b/;   // words that make "with" put two datasets side by side ("compare women with poverty") instead of describing the group ("women with low income")
const CH_CONN = 'and|or|plus|y|o|e|u|with|con|vs\\.?|versus|against|contra|compared (?:with|to)|comparad[oa]s? con|alongside|along with|together with|next to|near|beside|besides|as well as|asi como|junto con|junto a|linked to|tied to|associated with|asociad[oa]s? con|relacionad[oa]s? con|se relacionan? con|in addition to|ademas de|aparte de|apart from|frente a|en contraste con|then|luego|followed by|cerca de|on top of|overlaid on|overlay on|where|donde|wherever|dondequiera|when|cuando|affects?|impacts?|influences?|afecta|influye|vary with|varies with|varying with|depends? on|moves? with|changes? with|rises? with|falls? with|tracks?|follows?|goes up as|go up as|goes down as|go down as|the more|cuanto mas|by the (?:share|percentage|number|proportion) of|por (?:el|la) (?:porcentaje|proporcion|numero|cantidad) de|(?:in\\s+)?(?:places|areas|municipalities|towns|neighborhoods|lugares|municipios|zonas|barrios|pueblos)\\s+(?:with|where|con|donde)';   // words that put two datasets side by side or say that one goes with the other ("on" and "over" are not here: "figures on women", "data on women" say whose figure it is)
const CH_FILL = 'high|low|all|alta|baja|mucho|mucha|poco|poca|pocos|pocas|higher|lower|more|less|fewer|most|many|there are|there is|hay|are|is|do|does|have|has|live|lives|living|viven|vive|exist|exists|mas|menos|muchos|muchas|the|a|an|of|de|los|las|el|la|share|percentage|number|count|proportion|rate|porcentaje|proporcion|numero|cantidad|tasa|people|residents|show|map|display|see|muestra|mapa|ver|also|too|then|only|just|tambien|ademas|solo|solamente';   // words that may stand between those
const CH_WORD_AT = new RegExp('^(?:' + CH_FILL + '|' + CH_NOUN + ')\\b');
const CH_DEGREE_AT = /^\s*(?:with|con)\s+(?:(?:the|el|la|los|las)\s+)?(?:high|low|higher|lower|more|less|fewer|many|few|most|highest|lowest|alta|baja|alto|bajo|mucha|poca|mucho|poco|mayor|menor|no|any|some)\b/;
const CH_SCOPE = /\b(?:by|across|per|in each|por|en cada)\s+(?:(?:the|los|el)\s+)?(?:municipalit(?:y|ies)|municipios?|towns?|pueblos?)\b/g;   // "by municipality", "por pueblo": where the answer is cut, not a word of the question about the datasets
const CH_TIMEREF = /\b(?:last|previous|prior|past|same|years?|decades?|periods?|baseline|pasado|anterior|anos?|decadas?|periodos?|antes)\b|\b(?:19|20)\d\d\b/;   // a time that a word of comparing may have as its object ("compare last year ...")
const CH_YEAR_FILTER = /\b(?:in|en|since|desde|during|durante|for|para)\s+(?:19|20)\d\d\b/g;   // a year that filters ("overlay in 2020 women on poverty") is not a time that the word compares with
function chCompares(n, c, o, hits = []) {   // a word that compares ("compare", "plot", "chart", "link") before the two datasets, with a few light words between it and the first of them ("compare these: women with poverty", "plot for me", "chart quickly", "link in Ponce"): it makes "with" put them side by side ("compare women with poverty"). Not when another dataset, or a time, stands between ("compare rent for women with poverty", "compare last year women with poverty"), and not when the word is far; a word after them ("compared to last year") has its own object
  const lo = Math.min(c.pos, o.pos), pre = n.slice(0, lo), re = new RegExp(CH_CMP.source, 'g'); let m, last = null;
  while ((m = re.exec(pre))) last = m;
  if (!last) return false;
  const base = last.index + last[0].length; let between = pre.slice(base);
  for (const h of hits) if (h.pos >= base && h.end <= lo) { if (chLevel(h.key) >= 3 && !CH_TOTAL.has(h.key) && h.key !== 'households') return false; between = between.slice(0, h.pos - base) + ' '.repeat(h.end - h.pos) + between.slice(h.end - base); }   // the other groups of the same phrase ("women who live alone") and the totals ("households living with a disability") are blanked; any other dataset is what the word is about
  between = between.replace(CH_YEAR_FILTER, ' ').replace(CH_SCOPE, ' ').replace(/\b(?:with|con|who|that|que)\b/g, ' ').replace(/[,;:%]/g, ' ');   // a year that filters, the words that join the parts of a group's name ("family households with children") and the signs
  return (o.pos < c.pos || (between.match(/[a-zñ]+/g) || []).length <= 4) && !CH_TIMEREF.test(between);   // the words before the dataset belong to its name when it comes first ("compare Seasonal, recreational or occasional-use units with ..."); before a group they are counted
}
const CH_CONJ = '(?:and|y|' + CH_CONTRAST + ')';
const CH_TIME_AT = /^(?:(?:the|a|an|one|few|some|el|la|los|las|un|una)\s+)*(?:(?:in|en|for|para|since|desde|during|durante|de|del|from|between|entre)\s+(?:the\s+)?)?(?:(?:19|20)\d\ds?|last|previous|prior|past|earlier|older|later|before|after|pre|post|decades?|years?|months?|baseline|antes|despues|hace|decadas?|anos?|mes|meses)\b/;   // a time after the word of contrast: after "and" it is not the counterpart ("poverty and women versus 2015")
const CH_WEAK_PARTNER = new RegExp('^[\\s,;]*(?:' + CH_CONTRAST + ')\\s+([a-z0-9ñ]+)');   // a word of contrast after the group and the first word after it
const CH_PARTNER_AFTER = new RegExp('^(?:[\'’]s?)?[\\s,;]*' + CH_CONJ + '\\s+(?:(?:the|los|las|el|la|all|other|otros|otras|everyone|everybody|todos|todo|able-bodied|those)\\s+)*([a-z0-9ñ]+)');
const CH_PARTNER_BEFORE = new RegExp('([a-z0-9ñ]+)(?:[\'’]s?)?\\s+' + CH_CONJ + '\\s+(?:(?:the|los|las|el|la|all|for|of|de|para|por)\\s+)*$');
const CH_REF = /^(?:average|mean|median|total|highest|lowest|whole|entire|overall|promedio|mediana)$/;   // a statistic that a group is set against ("women versus the average"); in the name of a dataset it stands next to the dataset's own words ("average income", "total jobs")
const CH_REF_OF = /^\s+(?:households?|population)/;   // "the average household", "the total population": the statistic and the one it describes
const CH_REF_HEAD = /^(?:population|households|poblacion)$/, CH_REF_AFTER = /^\s+(?:total|entera|as a whole|overall)\b/;   // the population or the households, with a word after it that says it is the whole: the counterpart of a group
const CH_REF_NOUN = /^(?:rates?|figures?|levels?|tasas?|cifras?|niveles|nivel)$/;   // "the rate for men", "la tasa de los hombres": the figure of the counterpart
const CH_NOT_PARTNER = /^(?:tell|what|how|where|which|who|with|for|in|to|least|few|que|como|donde|cual|con|para|en|es|son|last|previous|prior|past|same|year|years|decade|period|earlier|now|today|baseline|pasado|anterior|ano|anos|decada|periodo|antes|ahora|hoy)$/;   // words that are not a counterpart (a time: "compared to last year") and that the lists of filler words and of the rest of a dataset's name (CH_FILL, CH_NOUN) do not hold
const CH_PLACE = /\b(?:in|en|from|de)\s+(?:the\s+|los\s+|las\s+)?(?:[a-zñ-]+\s+){0,2}(?:municipalities|municipios|towns|pueblos|areas|zonas|places|lugares|neighborhoods|barrios|communities|comunidades|cities|ciudades)\b(?:\s+[a-zñ-]+){0,4}|\b(?:where|donde)\s+(?:(?:do|does|did|are|is|can|could|viven?|estan|esta)\s+)?(?:the\s+|los\s+|las\s+)?(?:[a-zñ-]+\s+){0,5}(?:live|lives|living|reside|resides|viven|vive|residen)\b(?:\s+[a-zñ-]+){0,4}/;   // "seniors in poor municipalities", "where do rich seniors live": the group is placed, the other dataset describes the places
const CH_NEW = (k) => /^acs_/.test(k);   // the datasets main did not have
const chNewGroup = (k) => CH_NEW(k) && chLevel(k) < 3;   // the groups main had no dataset for
const chAsksRelation = (keys, st) => {   // the sentence on the correlation is about the first two datasets: told when neither is a group dataset (as on main) or when the question relates those two
  const two = keys.slice(0, 2);
  if (!two.some(chNewGroup)) return true;
  if (!st) return false;
  return st.relPairs ? st.relPairs.some(([x, y]) => two.includes(x) && two.includes(y)) : !!st.related;
};
const chComparable = (st) => st.keys.slice(0, 2).every(k => chLevel(k) < 3) || chAsksRelation(st.keys, st);   // two group datasets named together may be compared; a group and another dataset, only when the question relates them
const CH_LIVE = /\b(?:live|lives|living|reside|resides|viven|vive|residen)\b/, CH_SPEAKER = /\b(?:i|we|you)\s+(?:live|lives|living|reside|resides)\b/g;   // the verb of "where do rich seniors live"; not the speaker's own ("where I live")
function chBlank(text, at, members) {   // the text with the phrases of the groups blanked
  let s = text;
  for (const x of members) { const a = Math.max((x.ps == null ? x.pos : x.ps) - at, 0), b = Math.min((x.pe == null ? x.end : x.pe) - at, text.length); if (b > a) s = s.slice(0, a) + ' '.repeat(b - a) + s.slice(b); }
  return s;
}
const CH_PLACE_NOUN = /\b(?:municipalities|municipios|towns|pueblos|areas|zonas|places|lugares|neighborhoods|barrios|communities|comunidades|cities|ciudades)\b/;
function chPlaceOf(n, o, c) {   // does a place phrase hold the dataset that describes the places ("in poor municipalities", "where do rich seniors live")? The dataset stands after the noun or just before it, not in a clause of its own ("veteran in poverty across municipalities"); the verb that closes "where ... live" is not the group's own word ("where is poverty highest among people living alone"); a group that has a preposition of its own after the place ("jobs in poor municipalities among women") is the breakdown, not placed
  const re = new RegExp(CH_PLACE.source, 'g'); let m;
  while ((m = re.exec(n))) {
    if (o.pos >= m.index && o.end <= m.index + m[0].length) {
      const where = /^(?:where|donde)\b/.test(m[0]), k = m.index + m[0].search(CH_PLACE_NOUN);
      if (!where && c.pos >= k && (/\b(?:among|amongst|entre|for|para|of|de|by|por)\b/.test(n.slice(k, c.pos)) || /\b(?:in|en)\s+(?:(?:the|all|los|las|el|la|todos|todas)\s+)*$/.test(n.slice(k, c.pos)))) { if (!m[0].length) re.lastIndex++; continue; }
      if (where ? CH_LIVE.test(chBlank(m[0], m.index, c.members).replace(CH_SPEAKER, ' ')) : o.pos >= k || /^\s*(?:(?:and|or|y|o|very|most|more|less|highly|extremely|muy|mas|menos)\s+)*$/.test(n.slice(o.end, k))) return true;
    }
    if (!m[0].length) re.lastIndex++;
  }
  return false;
}
function chContrast(n, w, hits, c, weak = false) {   // the group is set against its counterpart ("women and men", "children vs adults", "veterans and everyone else", "women versus the average"): it is the breakdown of the other dataset. weak: the group follows the dataset after a colon or a comma only ("poverty: women vs last year"), so a time is its counterpart too
  if (c.versus) return true;
  { const m = CH_WEAK_PARTNER.exec(n.slice(c.end)), at = m ? c.end + m[0].length - m[1].length : 0, nx = m && hits.find(h => h.pos >= at), front = nx && (n.slice(at, nx.pos).match(/[a-z0-9ñ]+/g) || []).length <= 2, total = front && (CH_TOTAL.has(nx.key) || nx.key === 'households'); if ((weak && total) || (weak && m && !(weak === 2 && CH_TIME_AT.test(n.slice(at))) && !/^\d+$/.test(m[1].replace(/^(?:19|20)\d\d$/, 'y')) && !front)) return true; }   // in a list of the dataset and the group (after a colon, a comma, "and") a total right after a word of contrast is the counterpart ("poverty and women vs all households", "rent: women vs the male population"); after a colon or a comma, whatever follows a word of contrast and is not a dataset, a group, the front of a dataset's name ("poverty: women versus total jobs") or a number that is not a year ("median rent: women vs 300") is the counterpart ("poverty: women vs the 2010s", "poverty, women compared with a few years ago")
  const free = (word, at) => {   // a word that no dataset rule took, that is not the rest of a dataset's name and does not stand against a dataset; a statistic is the counterpart unless it is the front of a dataset's name
    if ((hits.removed || []).some(r => at >= r.pos && at < r.end)) return true;
    if (CH_REF_HEAD.test(word) && CH_REF_AFTER.test(n.slice(at + word.length))) return true;   // "la población total", "the population as a whole": the population is the counterpart, and stays a dataset of the question as on main
    if (/^\d/.test(word)) return false;
    if (CH_NOT_PARTNER.test(word) || !/\S/.test(w.slice(at, at + word.length))) return false;
    const wordEnd = at + word.length, noun = new RegExp('\\b(?:' + CH_NOUN + ')\\b', 'g'), rest = (h) => chLevel(h.key) >= 3 && ((h.end <= at && !/\S/.test(chNameRest(n.slice(h.end, wordEnd), false).replace(noun, ' '))) || (h.pos >= wordEnd && !/\S/.test(chNameRest(' ' + n.slice(at, h.pos), true).replace(noun, ' '))));   // the word is the rest of the name of the dataset before it ("el ingreso del hogar y mujeres") or the front of the name of the one after it ("women and private-sector jobs", "women and average annual pay")
    const near = hits.some(h => Math.abs(h.end - at) <= 1 || Math.abs(h.pos - wordEnd) <= 1 || rest(h)), after = n.slice(wordEnd);
    if (CH_REF.test(word)) return !near || CH_REF_OF.test(after);
    if (/^(?:mas|menos)$/.test(word) && /^\s+(?:alt[oa]s?|baj[oa]s?)\b/.test(after)) return !near;   // "el más alto", "el más bajo": the highest, the lowest
    if (CH_REF_NOUN.test(word) && /^\s+(?:promedio|mediana|media)\b/.test(after)) return true;   // "la tasa promedio": the average rate
    if (CH_REF_NOUN.test(word)) { const f = /^\s+(?:for|of|de|para)\s+(?:(?:the|los|las|el|la)\s+)?([a-zñ]+)/.exec(after); return !!f && free(f[1], at + word.length + f[0].length - f[1].length); }   // "the rate for men", "la tasa de los hombres": the figure of the counterpart, when what follows is not a dataset
    return !(CH_WORD_AT.test(word) && !/^(?:people|residents)$/.test(word)) && !near;
  };
  const a = CH_PARTNER_AFTER.exec(n.slice(c.end)); if (a && free(a[1], c.end + a[0].length - a[1].length)) return true;
  const b = CH_PARTNER_BEFORE.exec(n.slice(0, c.pos)); if (b && free(b[1], b.index)) return true;
  return false;
}
function chDensity(n, c) {   // "places with more veterans have higher poverty": the group is counted in places, the other dataset describes them; "afecta el porcentaje de mujeres a la pobreza": the share of the group is what the verb is about
  const pre = n.slice(0, c.pos);
  return /\b(?:where|donde)\s+(?:there\s+are|there\s+is|hay|viven|live)\s+(?:more|fewer|less|many|mas|menos|muchos|muchas)\s+$/.test(pre) || /\b(?:places|areas|municipalities|towns|neighborhoods|lugares|municipios|zonas|barrios|pueblos)\s+(?:with|where|con|donde)\s+(?:(?:more|fewer|less|many|most|mas|menos|muchos|muchas|few|pocos|pocas|high|low|alta|baja|a high|a low|the)\s+)*(?:(?:people|persons|residents|adults|personas|residentes|gente)\s+(?:with|con)\s+)?$/.test(pre)
    || /\b(?:affects?|impacts?|influences?|afecta|influye)\s+(?:(?:the|el|la|los|las)\s+)?(?:share|percentage|number|proportion|porcentaje|proporcion|numero|cantidad)\s+(?:of|de)\s+(?:(?:the|el|la|los|las)\s+)?$/.test(pre)   // "how did the hurricane affect women's poverty" is not about the share
    || /\b(?:depends? on|depende de|correlates? with|relates? to|se relaciona con|the more|cuanto mas)\s+(?:(?:the|el|la|los|las)\s+)?(?:(?:share|percentage|number|proportion|porcentaje|proporcion|numero|cantidad)\s+(?:of|de)\s+(?:(?:the|el|la|los|las)\s+)?)?$/.test(pre);
}
const CH_LINKS = [CH_CONN, CH_CMP.source].join('|');   // the words and phrases that connect two things or compare them
const CH_FUNC = new RegExp('^(?:' + [CH_PREP, CH_FILL, CH_NOUN].join('|') + ')$');   // the words that are not part of a name: prepositions, filler words, rank words and the words of a statistic
const CH_NAME_OF = new RegExp('\\b(?:' + CH_NOUN + ')\\s+(?:of|de|del)\\b', 'g');   // "the cost of rent", "el tiempo de viaje": the preposition inside the name of a dataset, not between two datasets
const CH_SHARE_OF = /\b(?:shares?|percentages?|percent|proportions?|numbers?|counts?|totals?|porcentajes?|proporcion|numero|cantidad|parte)\s+(?:of|de)\b/g;   // "the share of women", "el porcentaje de mujeres": the share of the group is named, the preposition is not whose figure it is
const CH_PEOPLE_IN = /\b(?:people|persons|residents|personas|gente|residentes)\s+(?:in|en)\b/g;   // "people in poverty", "personas en pobreza": the rest of the name of the dataset after it
const CH_LINKS_AT = new RegExp('^\\s*(?:' + CH_LINKS + ')\\b');   // a gap that starts with a connection ("related to", "junto a", "compared with"): its first word is not the rest of a name
const CH_PERSON = new Set('men man male males boy boys adults adult youth youths teens teenagers hombres hombre varones varon adultos adulto jovenes joven ones everyone everybody others rest otros demas civilians civiles'.split(' '));   // the words for a kind of people: the counterpart of a group ("women and men poverty"), never the rest of the name of a dataset
const CH_COMPARE_BEFORE = new RegExp(CH_CMP.source + '(?:\\s+[a-zñ-]+){0,4}\\s*$');   // a word that compares, with at most four words after it (as many as chCompares counts), right before a dataset
const CH_LINKS_END = new RegExp('(?:^|[\\s,;&])(?:' + CH_LINKS + ')[\\s,;&]*$');   // a gap that ends with a connection or a contrast ("apart from", "versus the"): the word after it is not the rest of a name
const CH_CONTRAST_END = new RegExp('(?:^|[\\s,;&])(?:' + CH_CONTRAST + ')(?:\\s+(?:the|los|las|el|la|those|aquellos|aquellas|all|todos|todas))*[\\s,;&]*$');   // a gap that ends with a word of contrast, and the articles after it
function chNameTail(s) {   // "en servicios", "con hipoteca", "por residente", "in services": a preposition and one or two plain words that a dataset's name ends with, when a connector follows; how many characters of the gap they take
  const m = /^\s*(?:en|in|con|with|por|de|del|of|on)\s+(?:(?:the|la|el|los|las)\s+)?/.exec(s); if (!m) return 0;
  let i = m[0].length, words = 0, w;
  while (words < 2 && !CH_LINKS_AT.test(s.slice(i)) && !CH_LIST_AT(s.slice(i)) && (w = /^([a-zñ]+(?:-[a-zñ]+)*)(?=[\s,;:]|$)\s*/.exec(s.slice(i))) && w[1].length >= 3 && !CH_FUNC.test(w[1]) && !CH_PERSON.has(w[1])) { i += w[0].length; words++; }
  return words && (/^\s*(?:$|(?:and|y|or|o|vs|versus|contra|alongside|junto|plus)\b)/.test(s.slice(i)) || CH_LIST_AT(s.slice(i))) ? i : 0;   // a connector closes the name; "with" never does ("poverty of immigrants with disabilities")
}
function chNameRest(g, before) {   // the gap without the rest of the dataset's name that its rule left ("federal funding and women": funding; "women and health insurance": health; "el ingreso del hogar y mujeres": del hogar; "empleos en servicios y mujeres": en servicios): up to two plain words next to the dataset, on the side away from the group
  let s = before ? g.replace(/\s[a-zñ]+-$/, ' ') : g.replace(/^-[a-zñ]+/, ''), m;   // "tourism-related", "self-employed": the part joined with a hyphen
  const plain = (w) => (w.length >= 3 || /^(?:ya|i|ii)$/.test(w)) && !CH_FUNC.test(w) && !CH_PERSON.has(w) && !/^non-/.test(w), noun = new RegExp('^(?:' + CH_NOUN + ')$');   // and the short words of a few labels ("dentistas ya", "delitos tipo i")
  for (let k = 0; k < 2; k++) {   // before a dataset a side word that opens the gap is not the front of its name ("compare women over local poverty")
    if (before) { if (CH_LINKS_END.test(s) || !(m = /\s([a-zñ]+(?:-[a-zñ]+)*)\s*$/.exec(s)) || !plain(m[1]) || (CH_GAP_SIDE.test(m[1]) && !/\S/.test(s.slice(0, m.index)))) break; s = s.slice(0, m.index) + ' '; }
    else { if (CH_LINKS_AT.test(s) || CH_LIST_AT(s) || !(m = /^\s*([a-zñ]+(?:-[a-zñ]+)*)(?=[\s,;:]|$)/.exec(s))) break; if (noun.test(m[1])) { s = s.slice(m[0].length); k--; continue; } if (!plain(m[1])) break; s = s.slice(m[0].length); }   // a word of a statistic inside the name does not count ("vacancy rate census")
  }
  if (!before) s = s.slice(chNameTail(s));
  else if (CH_CONTRAST_END.test(s)) return g;   // after a word of contrast the words that follow are the counterpart's ("women versus the mainland poverty", "veterans vs veteran households")
  return s;
}
const chListGap = (g) => /[,;:]/.test(g) || !/\S/.test(g) ? 1 : /&|\+|\b(?:and|y|e|plus)\b/.test(g) ? 2 : 0;   // the dataset and the group listed: after a colon, a comma or a semicolon (1), after "and", "y", "&" (2); any other words may stand there ("poverty, these women", "poverty: only women", "poverty, half of the women")
const CH_LIST_AT = (s) => CH_GAP_LIST_AT.test(s);   // a list word of the rule at the start of a text
const CH_GAP_LIST = /^(?:and|y|e|or|o|u|and\/or|y\/o|on top of|plus|vs\.?|as well as|along with|together with|in addition to|then|luego|followed by|seguid[oa]s? de|junto con|asi como|ademas de|next to|alongside|beside|junto a|junto al|al lado de|al lado del|[,;:&+/.!?])$/;   // a list of the two: no word of relation is needed ("poverty and women", "poverty: women", "poverty versus children")
const CH_GAP_LIST_AT = new RegExp('^\\s*(?:' + CH_GAP_LIST.source.slice(4, -2) + ')(?=[\\s,;:]|$)');
const CH_GAP_REL = new RegExp('^(?:(?:' + CH_CMP.source.slice(5, -3) + ')(?:\\s+(?:with|to|on|con|sobre))?|(?:vary|varies|change|changes|move|moves|rise|rises)\\s+(?:with|con)|tracks?|affects?|' + /(?:overlaid|linked|plotted)\s+(?:with|to|on|against)|(?:se\s+)?(?:relaciona|relacionan|relacionad[oa]s?|correlaciona|correlacionad[oa]s?|asociad[oa]s?|comparad[oa]s?|vinculad[oa]s?)\s+(?:con|a)|in relation to|en relacion con/.source + ')$');   // a phrase of relation between the two ("poverty correlated with women", "la pobreza relacionada con las mujeres")
const CH_FRONT_WORD = /^(?:local|locales|national|nacional|nacionales|regional|regionales|island-wide|statewide|municipal|municipales|current|actual|actuales|new|nuevo|nueva|nuevos|nuevas|recent|reciente|recientes|high|higher|low|lower|alto|alta|altos|altas|bajo|baja|bajos|bajas|rising|growing|creciente|crecientes)$/;   // the describing words that may stand in front of a dataset after "against", "contra" ("compare women against local poverty"); any other words are a counterpart ("against Puerto Rico poverty", "against the mainland poverty")
const CH_FILL_RE = new RegExp('\\b(?:' + CH_FILL + ')\\b', 'g');
const CH_GAP_SIDE = /^(?:with|con|to|a|al|on|onto|over|sobre|encima de|encima del|against|contra|next to|alongside|beside|junto a|junto al|al lado de|al lado del|frente a|frente al|compared with|compared to)$/;   // the two side by side, when a word that compares stands before them ("compare women with poverty", "overlay women on poverty", "superpone mujeres sobre la pobreza")
function chGapCore(g, groupLast, keepShare = false) {   // the gap without its articles, a year that filters ("in 2020"), a scope ("by town"), a place (its name is blanked: "in Ponce") and, before a group, "the share of"
  let s = g.replace(/\b(?:between|entre|from|desde|de)\s+(?:19|20)\d\d\s+(?:and|y|to|a|hasta)\s+(?:19|20)\d\d\b/g, ' ').replace(CH_YEAR_FILTER, ' ').replace(/\b(?:19|20)\d\d\b/g, ' ').replace(CH_SCOPE, ' ').replace(/\b(?:in|en|for|para|from|desde|across|throughout)\s{4,}/g, ' ');
  s = groupLast ? s.replace(CH_SHARE_OF, ' groupshare ').replace(/%\s*(?:of|de)\b/g, ' groupshare ') : s.replace(CH_NAME_OF, ' ').replace(CH_PEOPLE_IN, ' ');   // before a group "the share of" names the share (kept as a marker that no list holds); before a dataset its own words ("the share of people in poverty", "the cost of rent")
  s = s.replace(new RegExp('\\b(?:todos|todas|todo|toda|some|algunos|algunas|these|those|estos|estas|esos|esas|persons|personas|residentes|gente|' + CH_NOUN + '|' + CH_FILL.replace(/\|(?:of|de|a|an|then|ademas)(?=\|)/g, '') + ')\\b', 'g'), ' ').replace(/\s+/g, ' ').trim();   // articles, filler words and the words of a dataset's name ("poverty rate and women", "Self-employed residents and women", "map women and show poverty")
  return keepShare ? s : s.replace(/ ?groupshare$/, '');
}
const chSide = (n, hits, c, o, s, before, gapRaw) => CH_GAP_SIDE.test(s) && !(before && /^(?:with|con)$/.test(s) && CH_DEGREE_AT.test(gapRaw + ' ' + n.slice(o.pos))) && chCompares(n, c, o, hits);   // "with", "on", "sobre" between the two after a word that compares; "plot women with low income": "with" and a word of degree describe the group
const CH_YEARS = new RegExp(/\b(?:between|entre|from|desde|de)\s+(?:19|20)\d\d\s+(?:and|y|to|a|hasta)\s+(?:19|20)\d\d\b|/.source + CH_YEAR_FILTER.source, 'g');   // a range of years or a year that filters
const chBlankTimes = (n) => n.replace(CH_YEARS, (x, at) => CH_CONTRAST_END.test(n.slice(0, at)) ? x : ' '.repeat(x.length));   // a year or a range of years is blanked unless a word of contrast makes it the counterpart ("poverty: women except for 2015")
function chRelates(n, w, hits, c, o, gap, before) {   // does the question relate the group's dataset and the other one? Only in a few clear forms (owner decision of 2026-10-12): a list of the two, a phrase of relation between them, or "with", "to", "on", "sobre" between them after a word that compares; anything else makes the group whose figure it is
  const rest = chNameRest(gap, before);   // the gap without the rest of the dataset's name ("federal funding and women")
  if (chContrast(chBlankTimes(n.replace(CH_SCOPE, (x) => ' '.repeat(x.length))), w, hits, c, chListGap(rest))) return false;   // a scope or a year is not a counterpart ("poverty by town and women")
  if (before && /^['’]/.test(gap)) return false;   // "women's poverty", "veterans' income": the group is whose figure it is
  if (chDensity(n, c)) return true;   // "places with more veterans have higher poverty"
  if (/^(?:by|with|con|to|a|on|against|por) groupshare$/.test(chGapCore(rest, !before, true))) return true;   // "poverty by the share of women", "compare poverty with % of women": the share of the group is named
  const ag = before && /^\s*(?:against|contra)(?=\s)/.exec(gap), s = ag && gap.slice(ag[0].length).replace(CH_FILL_RE, ' ').trim().split(/\s+/).every(x => CH_FRONT_WORD.test(x)) ? ag[0].trim() : chGapCore(rest, !before), asWritten = chGapCore(gap, !before);   // "compare women against local poverty": the words after "against" are the front of the dataset's name   // the gap without the rest of the dataset's name, and as written: the rest of a name may swallow a word of the rule ("la pobreza seguido de las mujeres", "poverty overlaid with the women")
  if ([s, asWritten].some(x => CH_GAP_LIST.test(x) || CH_GAP_REL.test(x))) return true;
  return (before || !/^(?:to|a|al|on)$/.test(s)) && chSide(n, hits, c, o, s, before, gap);   // "to", "a", "on" right after the rest of a name end phrases like "due to", "based on", "debida a": the figure of the group is asked ("compare poverty due to women"); "with", "con", "sobre" still count ("compare federal funding with women"); "link women to poverty" is chDirect's; with the group first the words before the dataset are its front ("overlay women on local poverty")
}
function chNamesBoth(n, hits, g, t, gap) {   // the total (or the households) and the group it counts: both are asked unless the total is inside the group's own phrase ("the veteran population", "the population with a disability", "households with children", "veterans in the population"); "and", "vs", "on", "sobre" between them put them side by side
  if (/\b(?:and|on|onto|over|sobre|encima)\b|[,;&]/.test(gap)) return true;
  if (/\b(?:shares?|percentages?|percent|proportions?|porcentajes?|proporcion)\s+(?:of|de)\b/.test(gap)) return false;   // "one-person households as a share of households": the group's share of its total
  if (/^\s*(?:with|con)\s+(?:(?:the|los|las|el|la)\s+)?$/.test(gap) && g.key === 'acs_veteran_pct' && CH_CMP.test(n.slice(0, Math.min(t.pos, g.pos)))) return true;   // "compare population with veterans": veterans are people, not a trait of the population (women are never joined to a total by "with") ("the population with a disability" is the group's)
  return !(g.ps != null && g.ps <= t.pos && t.end <= g.pe);
}
function chQualifies(n, w, hits, c, o) {   // c: a cluster of groups, o: the hit it may qualify; records in c.rel the datasets that the question relates the group's dataset to
  const before = c.pos < o.pos, gap = before ? n.slice(c.end, o.pos) : n.slice(o.end, c.pos), lo = before ? c.end : o.end, hi = before ? o.pos : c.pos;
  const between = hits.filter(x => x !== o && x.pos >= lo && x.end <= hi);
  if (between.length && !(between.every(x => CH_TOTAL.has(x.key) || x.key === 'households') && chContrast(n, w, hits, c))) return false;   // another dataset sits between them (the population or the households that the group is set against are not: "women vs the whole population: poverty")
  if (chPlaceOf(n, o, c)) return false;   // "seniors in poor municipalities", "where do rich seniors live": the other dataset describes the places, both are asked
  if (c.members.every(x => chNewGroup(x.key))) {   // main had no dataset for these groups: the figure is the other dataset's, for the group, unless the question names the two side by side
    if (chRelates(n, w, hits, c, o, gap, before)) { (c.rel = c.rel || []).push(o); return false; }
    return true;
  }
  if (CH_PAIR.test(n) && !CH_EXPLICIT.test(gap)) return false;   // "compare poverty seniors", "scatter poverty seniors": the two are asked for
  return (before ? CH_BEFORE : CH_AFTER).test(gap);   // one of the plain ways: the group says whose figure it is
}
function chDirect(n, w, hits, c, o) {   // a word that compares stands before the group and a dataset named side by side ("show unemployment, overlay women on poverty"): the group is not the breakdown of a dataset before them
  const before = c.pos < o.pos, lo = before ? c.end : o.end, hi = before ? o.pos : c.pos;
  if (hits.some(x => x !== o && x.pos >= lo && x.end <= hi) || chPlaceOf(n, o, c)) return false;
  return !chContrast(n, w, hits, c) && chSide(n, hits, c, o, chGapCore(n.slice(lo, hi), !before), before, n.slice(lo, hi));
}
function chBeside(n, hits, a, b) {   // two groups a few words apart with no dataset between them, and no word of share ("poverty among women and the share of veterans" names the second)
  const [x, y] = a.pos < b.pos ? [a, b] : [b, a];
  if (x.end > y.pos) return false;
  const gap = n.slice(x.end, y.pos);
  return (gap.match(/[a-zñ]+/g) || []).length <= 6 && !/\b(?:share|percentage|number|count|proportion|rate|porcentaje|proporcion|numero|cantidad|tasa)\b/.test(gap) && !hits.some(h => h.pos >= x.end && h.end <= y.pos);
}
function chQualifiers(n, hits, w) {   // the hits that only say whose figure is asked for, and the pairs (group, other dataset) that the question relates
  const clusters = [];
  for (const h of hits) if (chLevel(h.key) < 3) { h.ps = chPhraseStart(n, hits, h); h.pe = chPhraseEnd(n, hits, h); }   // the phrase of each group: its name and its own words and totals
  for (const h of hits.filter(x => chLevel(x.key) < 3)) {
    const last = clusters[clusters.length - 1], gap = last ? n.slice(last.end, h.ps) : '';
    if (last && (CH_JOIN.test(gap) || CH_VS.test(gap))) { last.members.push(h); last.end = h.pe; last.level = Math.max(last.level, chLevel(h.key)); if (CH_VS.test(gap)) last.versus = true; }
    else clusters.push({ members: [h], pos: h.ps, end: h.pe, level: chLevel(h.key) });
  }
  const views = [];
  for (const c of clusters) {   // a group main had a dataset for and one it had none for, joined ("veterans and seniors"), are judged each by its own rule
    const fresh = c.members.filter(m => chNewGroup(m.key)), old = c.members.filter(m => !chNewGroup(m.key));
    if (fresh.length && old.length) for (const part of [fresh, old]) views.push({ ...c, members: part, level: Math.max(...part.map(m => chLevel(m.key))) });
    else views.push(c);
  }
  const out = new Set();
  const eligible = (c, o) => !CH_TOTAL.has(o.key) && !(o.pos >= c.pos && o.end <= c.end) && !(CH_OF[o.key] && c.members.some(x => CH_OF[o.key].has(x.key))) && chLevel(o.key) > c.level;
  for (const c of views) {
    let q = null;
    const poss = /^['’]/.test(n.slice(c.end));   // "women's income": the dataset after the possessive is whose figure, whatever stands before the group ("poverty vs women's income")
    for (const o of hits) { if (!eligible(c, o) || (poss && o.pos < c.end)) continue; const related = c.rel && c.rel.length; if (chQualifies(n, w, hits, c, o) && !related) { q = o; break; } }   // once the group is related to a dataset, the later ones only add relations ("poverty and women and also unemployment")   // in the order of the words, the first dataset that the group is whose figure of, or is related to, decides ("pobreza y mujeres y también muestra desempleo")
    const p = q && c.members.every(x => chNewGroup(x.key)) && hits.find(o => eligible(c, o) && chDirect(n, w, hits, c, o));   // a group that a word of relation puts beside another dataset is not the breakdown of the one before it ("show unemployment, overlay women on poverty")
    if (p) (c.rel = c.rel || []).push(p);
    else if (q) { c.q = q; c.members.forEach(m => out.add(m)); }
  }
  for (let again = true; again;) {
    again = false;
    for (const c of views) if (!out.has(c.members[0])) {
      const tied = c.rel && c.rel.every(o => out.has(o));   // a group related only to groups that are themselves left out ("poverty for veterans near women")
      const beside = !c.rel && c.members.every(m => chNewGroup(m.key)) && views.find(a => out.has(a.members[0]) && a.q && chLevel(a.q.key) === 3 && chBeside(n, hits, a, c));   // a group main had no dataset for, a few words from a group that is the breakdown of a dataset, is part of it ("poverty among women with children", "poverty of women near veterans"); the elderly, that main had a dataset for, stay
      if (tied || beside) { c.q = beside ? beside.q : c.q; c.members.forEach(m => out.add(m)); again = true; }
    }
  }
  const relPairs = [];
  for (const c of views) if (c.rel && !out.has(c.members[0])) for (const o of c.rel) for (const m of c.members) relPairs.push([m.key, o.key]);
  return { out: [...out], related: relPairs.length > 0, relPairs };
}
// A question that holds the whole label of a dataset of the Population series (a chip the chat itself offered, a title copied from the list) names that dataset, and nothing else in those words.
let CH_LABEL_SIG = '', CH_LABEL_LIST = [];
function chLabelList() {
  const api = chApi(); if (!api) return [];
  const sig = api.datasets().length + '/' + I18N.lang;
  if (sig !== CH_LABEL_SIG) {
    CH_LABEL_SIG = sig; CH_LABEL_LIST = [];
    for (const d of api.datasets()) if (/^acs_/.test(d.key)) for (const s of new Set([d.label, T(d.label)])) { const full = norm(s); for (const x of new Set([full, full.split(',')[0]])) if (x.length >= 12) CH_LABEL_LIST.push([x, d.key]); }
    CH_LABEL_LIST.sort((p, q) => q[0].length - p[0].length);
  }
  return CH_LABEL_LIST;
}
// ── Generated lexicon (plan item 14): a dataset is askable the day it is registered ──
// Every dataset's own name, in English and in the page's Spanish (T), read only when no rule above named a dataset; and the words its dictionary entry lists under "ask"
// (catalog.json, CH.ask), read also beside a rule's dataset ("poverty and bridges"). A name must match with two words or more; an "ask" phrase may be one word.
let CH_LEX_SIG = '', CH_LEX = [];
const chSame = (q, l) => q === l || (q.length >= 4 && l.length >= 4 && Math.abs(q.length - l.length) <= 2 && (q.startsWith(l) || l.startsWith(q)));   // one word, or its plural ("puente"/"puentes", "escuela"/"escuelas"); "medicos" is not "medicare"
function chLexicon() {
  const api = chApi(); if (!api) return [];
  const ask = CH.ask || {}, sig = api.datasets().length + '/' + Object.keys(ask).length + '/' + I18N.lang;
  if (sig === CH_LEX_SIG) return CH_LEX;
  const out = [], seen = new Map();
  const add = (p, key, alias) => {
    const text = norm(String(p || '')).replace(/[^a-z0-9ñ]+/g, ' ').trim(), toks = text.split(' ').filter(t => t.length > 2 && !STOP.has(t));
    if (!toks.length || (!alias && toks.length < 2)) return;
    const had = seen.get(key + '|' + text); if (had) { had.alias = had.alias || alias; return; }   // a name that is also an "ask" phrase keeps the phrase's standing
    const L = { key, text, stems: toks, alias }; seen.set(key + '|' + text, L); out.push(L);
  };
  for (const d of api.datasets()) {
    for (const l of new Set([d.label, T(d.label)])) { add(l, d.key, false); add(String(l).split(/[,(]/)[0], d.key, false); }
    const a = ask[api.dictId ? api.dictId(d.key) : d.key]; if (a) [...(a.en || []), ...(a.es || [])].forEach(w => add(w, d.key, true));
  }
  out.sort((p, q) => q.stems.length - p.stems.length || q.text.length - p.text.length);
  CH_LEX_SIG = sig; CH_LEX = out;
  return out;
}
function chLexHits(w, askOnly = false) {   // the longest names whose words all appear in what is left of the question (each word used once); at most two datasets. askOnly: only the words of the dictionary entries (a rule already named a dataset)
  const words = [], re = /[a-z0-9ñ]+/g; let m;
  while ((m = re.exec(w))) if (m[0].length > 2 && !STOP.has(m[0])) words.push({ s: m[0], pos: m.index, end: m.index + m[0].length, used: false });
  const hits = [];
  if (!words.length) return hits;
  for (const L of chLexicon()) {
    if ((askOnly && (!L.alias || L.stems.length < 2)) || hits.some(h => h.key === L.key)) continue;   // beside a rule's dataset only an "ask" phrase of two words or more ("students" alone is a group in "rent of students")
    const take = [];
    for (const s of L.stems) { const x = words.find(c => !c.used && !take.includes(c) && chSame(c.s, s)); if (!x) break; take.push(x); }
    if (take.length !== L.stems.length) continue;
    take.forEach(x => { x.used = true; });
    hits.push({ key: L.key, pos: Math.min(...take.map(x => x.pos)), end: Math.max(...take.map(x => x.end)), words: take });
    if (hits.length >= 2) break;
  }
  return hits;
}
/** The "ask" phrases of two words or more that stand whole in the question ("bridges in poor condition", "distancia a un centro de salud"), before the rules: such a phrase is
    the dataset's own name for it, so a rule must not take one of its words ("poor" is poverty elsewhere). Each word may be plural. Longest first; each phrase's text is blanked. */
function chAskPhrases(w) {
  const hits = [];
  for (const L of chLexicon()) {
    if (!L.alias || L.stems.length < 2 || hits.some(h => h.key === L.key)) continue;
    const re = new RegExp('(?:^|[^a-z0-9ñ])(' + L.text.split(' ').map(x => x + '(?:s|es)?').join('[ -]+') + ')(?![a-z0-9ñ])');   // the text holds only letters, digits and single spaces (chLexicon); the question (norm) can keep a hyphen ("non-PRASA")
    const m = re.exec(w); if (!m) continue;
    const pos = m.index + m[0].length - m[1].length, end = pos + m[1].length;
    hits.push({ key: L.key, pos, end });
    w = w.slice(0, pos) + ' '.repeat(end - pos) + w.slice(end);
  }
  return { hits, w };
}
function chConcepts(n) {
  let w = n; const hits = [];
  for (const [lab, key] of chLabelList()) { const i = w.indexOf(lab); if (i < 0 || /[a-z0-9]/.test(w[i - 1] || ' ') || /[a-z0-9]/.test(w[i + lab.length] || ' ')) continue; hits.push({ key, pos: i, end: i + lab.length }); w = w.slice(0, i) + ' '.repeat(lab.length) + w.slice(i + lab.length); }
  { const a = chAskPhrases(w); hits.push(...a.hits); w = a.w; }   // a dataset's own multi-word phrase first (plan item 14)
  for (let [re, val] of CONCEPTS) {
    if ((typeof val === 'string' && (val.startsWith('jobs_naics') || ['tourism_jobs', 'accommodation_jobs', 'food_service_jobs', 'qcew_private_jobs'].includes(val))) || re.source.includes('government')) re = JOBWORDS(re);   // "tourism jobs", "jobs in retail": the word jobs belongs to the industry
    const m = re.exec(w); if (!m) continue;
    const key = typeof val === 'function' ? val(n, m) : val; if (key == null) continue;   // a rule can step aside (null) or take its words and name nothing new (false: the question names the dataset another way)
    if (key !== false) hits.push({ key, pos: m.index, end: m.index + m[0].length });
    w = w.slice(0, m.index) + ' '.repeat(m[0].length) + w.slice(m.index + m[0].length);
    w = w.slice(0, m.index) + ' '.repeat(m[0].length) + w.slice(m.index + m[0].length);
  }
  for (const h of chLexHits(w, hits.length > 0)) { if (hits.some(x => x.key === h.key)) continue; hits.push({ key: h.key, pos: h.pos, end: h.end }); for (const x of h.words) w = w.slice(0, x.pos) + ' '.repeat(x.end - x.pos) + w.slice(x.end); }   // the generated lexicon: a dataset's names when no rule named one, and the words of its dictionary entry in any case (its words are blanked; the rest of the question stays for the intent)
  hits.sort((a, b) => a.pos - b.pos);
  if (hits.some(h => chLevel(h.key) < 3)) for (let i = hits.length - 1; i >= 0; i--) { const h = hits[i]; if (h.key === 'population' && (/\b(?:general|rest of the|resto de la)\s+$/.test(n.slice(0, h.pos)) || /^\s+(?:(?:en|in)\s+)?general\b/.test(n.slice(h.end)))) { const g = n.slice(0, h.pos).search(/\b(?:general|rest of the|resto de la)\s+$/); (hits.removed = hits.removed || []).push({ ...h, pos: g >= 0 ? g : h.pos }); hits.splice(i, 1); } }   // "women and the general population": the counterpart of a group, not the dataset; the removed range starts at the word that names it
  const qs = chQualifiers(n, hits, w), dropped = qs.out.map(h => ({ key: h.key, pos: h.pos, end: h.end, text: n.slice(h.pos, h.end).trim() })), gone = new Set(dropped.map(d => d.key));
  const all = [...new Set(hits.map(h => h.key))].filter(k => !gone.has(k)), last = new Set(), absorbed = new Set();
  for (const t of hits) if (CH_TOTAL.has(t.key) || CH_OF[t.key]) {   // "población con discapacidad", "hogares de personas solas": the group's own dataset answers; the population or the households it counts stand next to it
    const g = hits.find(h => (all.includes(h.key) || gone.has(h.key)) && chLevel(h.key) < 3 && !(h.pos < t.end && t.pos < h.end) && !hits.some(x => x !== t && x !== h && x.pos >= Math.min(h.end, t.end) && x.end <= Math.max(h.pos, t.pos)) && (n.slice(Math.min(h.end, t.end), Math.max(h.pos, t.pos)).replace(/\b(?:people|persons|residents|adults|personas|residentes|gente)(?:\s+(?:with|con))?\b/g, ' ').match(/[a-zñ]+/g) || []).length <= (CH_OF[t.key] ? 4 : 2));
    const foe = all.some(k => chLevel(k) >= 3 && !CH_TOTAL.has(k) && k !== 'households') && hits.find(h => gone.has(h.key) && chNewGroup(h.key) && h.end <= t.pos && new RegExp('^[\\s,;:]*(?:' + CH_CONTRAST + ')(?:\\s+[a-zñ-]+){0,2}\\s*$').test(n.slice(h.pe == null ? h.end : h.pe, t.pos)));   // the counterpart of a group that is left out ("poverty: women vs the total population", "la pobreza: mujeres vs la población total"): it goes with the group
    if (foe) { absorbed.add(t.key); continue; }
    if (!g) continue;
    const between = n.slice(Math.min(g.end, t.end), Math.max(g.pos, t.pos)), own = CH_OF[t.key] ? CH_OF[t.key].has(g.key) : chNewGroup(g.key);
    if (gone.has(g.key) && own) { absorbed.add(t.key); continue; }   // the group is left out (whose figure, or set against its counterpart): its total goes with it ("poverty among the veteran population", "poverty: women vs the total population")   // a household type is a share of the households, a survey group a share of the people: the total is not asked
    if (own ? chNamesBoth(n, hits, g, t, between) : /\b(?:and|or|vs|versus|against|y|o|contra|plus)\b|[,;&]/.test(between)) { if (own) qs.relPairs.push([g.key, t.key]); continue; }   // the question names both side by side: both are asked, in the order of the words, and they are related
    if (own) absorbed.add(t.key);
    else last.add(t.key);   // the elderly population: both datasets (main had them), the group's own first
  }
  const keys = all.filter(k => !absorbed.has(k));
  return { keys: keys.sort((a, b) => last.has(a) - last.has(b)), rest: w, dropped, related: qs.relPairs.length > 0, relPairs: qs.relPairs };
}
// the notes under an answer
const CH_MANY = /\b(most|how many|more(?! than)|cuantos|cuantas|mas(?! (?:alt|baj|elev|grand|peque|buen|mal|cerc|lej)\w*))\b/;   // "where do most veterans live": a count is asked for ("más alto" is not)
const chMoeNote = (lang) => lang === 'es' ? 'Son estimados de una encuesta, con margen de error: puede ser grande y valores cercanos pueden no diferir. La ventana emergente y la mesa de trabajo lo muestran.' : 'These are survey estimates with a margin of error: it can be large, and values that are close may not differ. The pop-up and the workbench show it.';
function chMoeText(k, year, i) {   // the 90% margin of a survey estimate for one place, as the pop-up writes it
  const api = chApi(), mo = api.moe && api.moe(k, year), x = mo && mo[i];
  if (x == null || !isFinite(x)) return '';
  return ` <small>(±${(api.meta(k) || {}).type === 'rate' ? fmt(x, 1) + ' pts' : esc(chVal(k, x, 'value'))})</small>`;
}
function chRankNotes(m, rest, n, lang) {   // m: the meta of the dataset; rest: the question without the words of the datasets; n: the whole question
  const out = [];
  if (m.unit === '%' && CH_MANY.test(rest) && !/\b(share|percent\w*|rate|proportion|porcentaje|proporcion|tasa)\b/.test(n)) out.push(lang === 'es' ? 'Esto ordena un porcentaje, no una cantidad.' : 'This ranks a percentage, not a count.');
  if (m.moe) out.push(chMoeNote(lang));
  return out.map(s => `<p class="ch-note">${s}</p>`).join('');
}
function chWindowNote(from, to, lang) {   // the survey windows of two labels (the last year of each): how many of their five years they share
  const share = Math.max(0, 5 - Math.abs(to - from));
  return lang === 'es'
    ? `Cada valor es un promedio de cinco años de una encuesta. Las dos ventanas comparadas (${from} y ${to}) ${share ? `comparten ${share} de sus cinco años` : 'no comparten ningún año'} y cada una tiene su propio margen de error: un cambio entre ellas es una señal aproximada, no una tendencia para interpretar con rigor.`
    : `Each value is an average of five years of a survey. The two windows compared (${from} and ${to}) ${share ? `share ${share} of their five years` : 'share no year'} and each has its own margin of error, so a change between them is a rough signal, not a trend to read closely.`;
}
function chDroppedNote(dropped, lang) {
  const list = dropped.map(d => lang === 'es' ? `«${esc(d.text)}»` : `“${esc(d.text)}”`).join(lang === 'es' ? ' ni ' : ' or ');
  return `<p class="ch-note">${lang === 'es' ? `Aquí no hay cifras desglosadas por ${list}, así que esto es para las personas residentes en general.` : `No figure here is broken down by ${list}, so this is for all residents.`}</p>`;
}
const chTie = (l, i, lang) => { const n = l.filter(x => x.v === l[i].v).length - 1; return n > 0 ? (lang === 'es' ? `, con ${n} más con el mismo valor` : `, with ${n} more at the same value`) : ''; };   // the highest or the lowest of a list is one of several when they share the value
const chOneYear = (m) => !m || !!m.static || !!m.snapshot || !(m.ys && m.ys.length > 1);   // a dataset with one date has no change to show
function chFuzzy(text, limit = 4) {   // fallback: overlap of the remaining words with dataset labels
  const api = chApi(); if (!api) return [];
  const toks = norm(text).split(/[^a-z0-9]+/).filter(t => t.length > 2 && !STOP.has(t));
  if (!toks.length) return [];
  const at = (text, stem) => new RegExp('(^|[^a-z0-9])' + stem.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).test(text);
  return api.datasets().map(d => { const hay = norm(`${d.label} ${d.group} ${d.definition}`); const lab = norm(d.label), grp = norm(d.group); let s = 0; for (const t of toks) { const stem = t.slice(0, Math.max(4, t.length - 2)); if (at(lab, stem) || at(grp, stem)) s += 3; else if (at(hay, stem)) s += 1; } return { d, s }; }).filter(x => x.s >= 3).sort((a, b) => b.s - a.s).slice(0, limit).map(x => x.d);
}
function chIntent(n, st) {
  const has = (re) => re.test(n);
  if (has(/\b(clear|reset|start over|limpia\w*|borra\w*|reinicia\w*)\b/)) return 'clear';
  if (has(/\b(missing|wish ?list|what should we add|what else|gaps?|backlog|candidates?|falta\w*|que mas|lista de deseos|datos deseados)\b/) && !st.keys.length) return 'missing';
  if (has(/\b(insights?|surprise|surprising|interesting|patterns?|discover\w*|findings?|hallazgos?|interesante\w*|sorprend\w*|patrones?|descubr\w*)\b/)) return 'insights';
  if (has(/\b(how big|database size|size of the (data|database)|storage|tamano|cuanto pesa)\b/)) return 'size';
  if (has(/\b(help|ayuda|what can you do|how do i use|que puedes|como uso|como funciona)\b/) || has(/^(hi|hello|hey|hola|buenas|buenos dias)\b/)) return 'help';
  if (has(/\b(sources?|licen[cs]e|where does .* come from|where do .* come from|from where|de donde|fuentes?|defin\w*|what does .* (mean|measure)|how is .* (measured|calculated|computed)|como se (mide|calcula)|que (mide|significa))\b/) && st.keys.length) return 'sources';
  if ((!st.keys.length || st.fromCtx) && has(/\b(nurses?|enfermer[oa]s?)\b/)) return 'practitioners';   // nurses only since 2026-11-18: doctors are counted (providers_series.json, NPPES); a dataset carried over from the last answer does not make it a question about that dataset
  if (has(/\b(what data|which data|what datasets?|datasets? (do|are)|list (the )?data|what do you have|what is in the (twin|observatory)|que datos|que hay|que tienen|que tienes|lista de datos|catalogo)\b/) || (!st.keys.length && has(/\b(what|which) \w+ data\b/))) return 'catalog';   // also "what health data do you have?"
  if (st.keys.length >= 2 && has(/\b(composite|compuesto|indice|index)\b/)) return 'compose';   // "build an index of poverty and unemployment": the workbench's composite builder
  if (st.keys.length >= 2 && chComparable(st) && has(/\b(relat\w*|correlat\w*|versus|vs\.?|against|together|move together|go together|compar\w*|relacion\w*|junt\w*|contra|asocia\w*)\b/)) return 'compare';
  if ((has(/\b(trend|changed?|changes|over time|since|evolution|grown|growth|decline[ds]?|cambi\w*|tendencia|evoluci\w*|crecid\w*|crecimiento|desde)\b/) || /\b(history|historic\w*)\b/.test(st.rest)) && st.keys.length) return 'trend';   // 'historic' among the words a dataset's name did not take: "historic places" names a dataset, not a trend
  if (/\b(highest|lowest|most|least|top|bottom|rank\w*|worst|best|largest|smallest|biggest|fewest|greatest|mayor(?:es)?|menor(?:es)?|mas alt\w*|mas baj\w*|mas|menos|cual(?:es)? (?:municipio|tiene)|where is|where are|donde (?:es|esta|hay|estan))\b/.test(st.rest) && st.keys.length) return 'rank';   // the words of a dataset ("menores de edad") are not rank words
  if (st.places.length && !st.keys.length) return st.places.length >= 2 ? 'areas' : 'muni';   // two places or more: side by side
  if (st.keys.length >= 2) return 'show';
  if (st.keys.length === 1) return st.places.length ? (st.places.length >= 2 ? 'areas' : 'value') : 'show';
  if (st.years.length && !st.keys.length && has(/^\W*(and |now |also |y |ahora |en )?(in |for |en |para |de |del )?(20[0-2]\d)\W*$/)) return 'year';
  return 'unknown';
}
function chParse(q) {
  const n = norm(q).replace(/[¿¡]/g, '').replace(/\s+/g, ' '), qq = q.normalize('NFC').trim().replace(/[¿¡]/g, '').replace(/\s+/g, ' '), lang = chLang(q, CH.lastLang || CH.ui), { places, rest: r1 } = chPlaces(n), { keys: k0, rest, dropped, related, relPairs } = chConcepts(r1), api = chApi(), keys = api ? k0.filter(k => api.meta(k)) : k0, years = chYears(n);   // a dataset the page did not load (an optional file failed) is not offered   // Spanish questions open with ¿: the patterns below match the words, so drop the marks
  const num = n.match(/\btop (\d{1,2})\b|\b(\d{1,2}) (?:highest|lowest|most|least)\b|\blos (\d{1,2})\b/);
  const st = { q, n, lang, places, keys, years, rest, n_top: num ? Math.min(15, +(num[1] || num[2] || num[3])) : 5, dir: /\b(lowest|least|bottom|fewest|smallest|menor\w*|mas baj\w*|menos|minim\w*)\b/.test(rest) ? 'asc' : 'desc', related, relPairs, dropped: dropped.map(d => ({ key: d.key, text: ((qq.length === n.length ? qq.slice(d.pos, d.end) : d.text) || d.text).trim() })), ctx: [...CH_CONTEXT.filter(([re]) => re.test(n)).map(c => c[1])] };
  if (st.keys.some(k => /^(?:transit_stops|pop_walk|pop_served|exp_stop_|exp_walk_)/.test(k)) && !st.ctx.includes('lyStops')) st.ctx.push('lyStops');   // what the stops data count, on the map with them (PR #8)
  if (!st.keys.length && CH.ctx.keys.length && (/\b(it|this|that|them|these|those|esto|eso|ese|esa|esos)\b/.test(n) || /^(where|how|which|donde|como|cual)/.test(n))) { st.keys = CH.ctx.keys.slice(0, 2); st.fromCtx = true; }
  st.intent = chIntent(n, st);
  return st;
}

// ── Data helpers ─────────────────────────────────────────────────────────────
const chVec = (key, o = {}) => chApi().values(key, o);
function chList(vals, dir = 'desc') {
  const api = chApi(), pls = api.places(), n = pls.length - 1;
  return vals.slice(0, n).map((v, i) => ({ i, name: pls[i], v })).filter(r => r.v != null && isFinite(r.v)).sort((a, b) => dir === 'asc' ? a.v - b.v : b.v - a.v);
}
function chNormLabel(key, norm_) { const o = chApi().normOptions(key).find(x => x[0] === norm_); return o ? T(o[1]) : norm_; }   // economy.js hands back English labels: shown in the page language
function chVal(key, x, norm_ = 'value', real = false, short = false) { const api = chApi(), u = api.unitLabel(key, norm_); return api.fmt(key, x, norm_, real) + (!short && u.suffix && norm_ !== 'value' ? u.suffix.replace(' (PR = 100)', '') : ''); }
function chCell(k, x, i, norm_) { const api = chApi(); return (x == null && api.missing && api.missing(k, i)) || chVal(k, x, norm_); }   // an empty place says what that means for the dataset (a shortage area: "No area shortage designation"), not a dash
// English lowercases a whole label; Spanish only its first letter, so names such as Puerto Rico keep their capitals
const chLc = (s) => I18N.lang === 'en' ? String(s).toLowerCase() : String(s).charAt(0).toLowerCase() + String(s).slice(1);
const chClip = (s, n) => s.length <= n ? s : s.slice(0, n).replace(/\s+\S*$/, '') + '…';   // a label in a narrow table header is cut at a word
function chLabel(key) { return T(chApi().meta(key).label); }   // dataset names are English data: shown in the page language
function chTitle(key, norm_, y, real) { const t = `${chLabel(key)}${norm_ !== 'value' ? ' · ' + chLc(chNormLabel(key, norm_)) : ''}${y ? ' · ' + y : ''}`; return real ? T('{title} · inflation-adjusted', { title: t }) : t; }
function chPearson(a, b) {
  const idx = []; for (let i = 0; i < a.length - 1; i++) if (a[i] != null && b[i] != null && isFinite(a[i]) && isFinite(b[i])) idx.push(i);
  const n = idx.length; if (n < 8) return null;
  const mx = idx.reduce((s, i) => s + a[i], 0) / n, my = idx.reduce((s, i) => s + b[i], 0) / n;
  let sxx = 0, syy = 0, sxy = 0; idx.forEach(i => { sxx += (a[i] - mx) ** 2; syy += (b[i] - my) ** 2; sxy += (a[i] - mx) * (b[i] - my); });
  if (!sxx || !syy) return null;
  const r = sxy / Math.sqrt(sxx * syy), slope = sxy / sxx, icpt = my - slope * mx;
  const res = idx.map(i => ({ i, e: b[i] - (icpt + slope * a[i]) })), sd = Math.sqrt(res.reduce((s, x) => s + x.e * x.e, 0) / Math.max(1, n - 2));
  return { r, n, slope, icpt, outliers: res.map(x => ({ i: x.i, z: sd ? x.e / sd : 0 })).sort((p, q) => Math.abs(q.z) - Math.abs(p.z)) };
}
const chNormFor = (key, mode = 'fill') => chApi().defaultNorm(key, mode);
function chViewNorm(key, mode = 'fill') {   // the default view, unless it is one number in every municipio ("Resident population per 1,000 residents" is 1,000 everywhere): then as published
  const nm = chNormFor(key, mode); if (nm === 'value') return nm;
  const r = chVec(key, { norm: nm }), x = r ? r.values.slice(0, -1).filter(y => y != null && isFinite(y)) : [];
  return x.length > 1 && x.every(y => Math.abs(y - x[0]) < 1e-9) ? 'value' : nm;
}
const chShort = (l) => l.length > 42 ? l.replace(/\s*\([^)]*\)/g, '').trim() : l;
// "2026-10-05" is a calendar day, not a moment: build it in local time so it never shows as the day before (I18N.date would read the string as UTC).
// English keeps the ISO text it always showed (like network.js); Spanish gets the long form.
const chDate = (iso) => { const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(String(iso || '')); return m && I18N.lang !== 'en' ? I18N.date(new Date(+m[1], +m[2] - 1, +m[3])) : String(iso || ''); };
const chOrd = (n) => { const v = n % 100; return n + (v >= 11 && v <= 13 ? 'th' : ({ 1: 'st', 2: 'nd', 3: 'rd' }[n % 10] || 'th')); };

// ── Tools: structured, grounded results (the local engine and any model use the same ones) ──
const Tools = {
  search_datasets({ query, limit = 6 }) { const p = chParse(query || ''); const fz = p.keys.length ? p.keys.map(k => chApi().meta(k)).filter(Boolean) : chFuzzy(query || '', limit); return fz.slice(0, limit).map(d => ({ key: d.key, label: d.label, group: d.group, years: d.years ? [d.years[0], d.years[d.years.length - 1]] : (d.ys ? [d.ys[0], d.ys[d.ys.length - 1]] : null), unit: d.unit, type: d.type })); },
  rank({ dataset, year = null, n = 5, direction = 'desc', norm = 'value', real = false }) {
    const r = chVec(dataset, { year, norm, real }); if (!r) return { error: 'no data' };
    const l = chList(r.values, direction);
    return { dataset, label: chLabel(dataset), year: r.year, exact: r.exact, norm, puertoRico: r.values[r.values.length - 1], top: l.slice(0, n).map(x => ({ place: x.name, value: x.v, display: chVal(dataset, x.v, norm, real) })), count: l.length };
  },
  correlate({ a, b, year = null }) {
    // each side in its default view, unless that is one number in every municipio (the resident population per 1,000 residents is 1,000 everywhere, so r has nothing to work on): then as published
    const varies = (v) => { const x = v.values.slice(0, -1).filter(y => y != null && isFinite(y)); return x.some(y => y !== x[0]); };
    const view = (key) => {
      const nm = chNormFor(key), r = chVec(key, { year, norm: nm });
      if (!r || nm === 'value' || varies(r)) return [nm, r];
      const p = chVec(key, { year, norm: 'value' }); return p && varies(p) ? ['value', p] : [nm, r];
    };
    const [na, A] = view(a), [nb, B] = view(b); if (!A || !B) return { error: 'no data' };
    const c = chPearson(A.values, B.values); if (!c) return { error: 'too few places with both values' };
    return { a, b, normA: na, normB: nb, yearA: A.year, yearB: B.year, r: c.r, n: c.n, outliers: c.outliers.slice(0, 3).map(o => ({ place: chApi().places()[o.i], z: o.z })) };
  },
  trend({ dataset, from = null, to = null, norm = 'value', real = false }) {
    const api = chApi(), m = api.meta(dataset), ys = (m.ys || []).filter(y => y >= 2003); if (!ys.length) return { error: 'no years' };
    const y0 = from && ys.includes(from) ? from : ys[0], y1 = to && ys.includes(to) ? to : ys[ys.length - 1];
    const a = chVec(dataset, { year: y0, norm, real }), b = chVec(dataset, { year: y1, norm, real }); if (!a || !b) return { error: 'no data' };
    const pr0 = a.values[a.values.length - 1], pr1 = b.values[b.values.length - 1];
    const rate = m.type === 'rate' || m.type === 'ratio', mv = [], minBase = m.type === 'count' ? 50 : m.type === 'total$' ? 100000 : 0;
    for (let i = 0; i < a.values.length - 1; i++) { const x = a.values[i], y = b.values[i]; if (x != null && y != null && (rate || x >= Math.max(minBase, 1e-9))) mv.push({ i, place: api.places()[i], d: rate ? y - x : (y - x) / x * 100, x, y }); }
    mv.sort((p, q) => q.d - p.d);
    return { dataset, label: m.label, from: y0, to: y1, rate, puertoRico: { from: pr0, to: pr1 }, up: mv.slice(0, 3), down: mv.slice(-3).reverse(), years: ys, all: mv };
  },
};

// ── Chat messages ────────────────────────────────────────────────────────────
/** A dataset's home topic in Explore (navigation plan PR 3, decision 81 h): "Abrir su tema / Open its topic" on the 2D map, where the Explore tab is. */
function chTopic(k, lang) {
  const api = chApi(); if (chMapless() || typeof Catalog === 'undefined' || !Catalog.openDomain || !api || !api.dictId) return null;
  const id = api.dictId(k); if (!id) return null;
  return { label: lang === 'es' ? 'Abrir su tema' : 'Open its topic', run: async () => { await Catalog.ensure(); const d = Catalog.homeOf(id); if (d) Catalog.openDomain(d); } };
}
// A reply is { html, actions: [{label, run, primary}] }; text inside html is escaped by the helpers below.
const chP = (s) => `<p>${s}</p>`;   // chP, chTx: named so that no page's own globals (profile.js P, dictionary.js tx) clash with them
const B = (s) => `<b>${esc(s)}</b>`;
// The sources of the Línea PAS line in the crisis and treatment replies (ask.js SENS_TEXT), checked 2026-10-21 (docs/ask.md, "Línea PAS"; HANDOFF decision 57): ASSMCA's home page
// states every fact of the sentence (the number, 24 hours, free, confidential, the chat); the Línea PAS site states the number, 24 hours and the chat.
const CH_PAS_SRC = { urls: ['https://assmca.pr.gov/', 'https://lineapas.assmca.pr.gov/'], checked: '2026-10-21' };
const chPasNote = (es) => `<p class="ch-note">${es ? 'Fuente' : 'Source'}: ASSMCA (${CH_PAS_SRC.urls.map(u => `<a href="${u}" target="_blank" rel="noopener">${u.replace(/^https:\/\/|\/$/g, '')}</a>`).join(es ? ' y ' : ' and ')}), ${es ? 'consultadas el' : 'checked'} ${CH_PAS_SRC.checked}.</p>`;
function chTable(cols, rows, lang = CH.ui) { return `<div class="ch-tw" tabindex="0" role="region" aria-label="${esc(chTx(lang).table)}"><table class="ch-t"><thead><tr>${cols.map((c, i) => `<th scope="col"${i ? ' class="num"' : ''}>${esc(c)}</th>`).join('')}</tr></thead><tbody>${rows.map(r => `<tr>${r.map((c, i) => i ? `<td class="num">${esc(c)}</td>` : `<th scope="row">${esc(c)}</th>`).join('')}</tr>`).join('')}</tbody></table></div>`; }
function chLinks(keys) {
  const api = chApi(), src = api.sources(), ids = new Set(); keys.forEach(k => (api.meta(k).sources || []).forEach(s => ids.add(s)));
  const rows = [...ids].map(id => src[id]).filter(Boolean).map(s => `<li><a href="${esc(s.url)}" target="_blank" rel="noopener">${esc(s.name)}</a>${s.license ? ` <small>· ${esc(s.license)}</small>` : ''}</li>`);
  return rows.length ? `<ul class="ch-src">${rows.join('')}</ul>` : '';
}
function chYearNotes(L, keys, rs, lang) {
  const t = chTx(lang), out = [];
  keys.forEach((k, i) => { const r = rs[i]; if (!r) return; const m = chApi().meta(k); if (m.snapshot) return; if (L.years.length && !r.exact) { const want = L.years[0]; const ys = m.ys; if (want < ys[0]) out.push(t.early(T(m.label), ys[0])); else out.push(t.near(T(m.label), r.year, want)); } });
  return out;
}

// plan which layers show a set of datasets well: rates as shading, counts as sized symbols (or shaded per resident when alone)
function chPlan(keys) {
  const api = chApi(), ms = keys.map(k => api.meta(k)), ext = (m) => m.type === 'count' || m.type === 'total$';
  const layers = [];
  if (keys.length === 1) {
    layers.push({ key: keys[0], mode: 'fill', norm: chViewNorm(keys[0]) });
    if (ext(ms[0])) layers.push({ key: keys[0], mode: 'symbol', norm: 'value' });
    return layers;
  }
  let fills = 0;
  keys.forEach((k, i) => { if (!ext(ms[i]) && fills < 2) { layers.push({ key: k, mode: 'fill', norm: 'value' }); fills++; } });
  keys.forEach((k, i) => { if (layers.some(l => l.key === k)) return; if (ext(ms[i]) && !fills) { layers.push({ key: k, mode: 'fill', norm: chViewNorm(k) }); fills++; } else layers.push({ key: k, mode: 'symbol', norm: ext(ms[i]) ? 'value' : 'value' }); });
  return layers.slice(0, 4);
}

const Handlers = {
  async show(st) {
    const api = chApi(), t = chTx(st.lang), keys = st.keys.slice(0, 4), layers = chPlan(keys).map((l, i) => st.byBarrio && i === 0 && l.mode === 'fill' ? { ...l, norm: 'value', level: 'barrio' } : l), year = st.years.length ? st.years[st.years.length - 1] : (CH.ctx.year && !st.keys.length ? CH.ctx.year : null);   // "por barrio": the first shading by barrio, when its dataset has barrio values (economy.js)
    const spec = { layers, year, context: st.ctx, base: st.years.length > 1 ? Math.min(...st.years) : undefined };
    if (st.places.length) spec.select = st.places[0];
    const res = await api.show(spec);
    CH.ctx = { keys, year, muni: st.places[0] || null };
    const rs = keys.map(k => chVec(k, { year })), notes = chYearNotes({ years: year ? [year] : [] }, keys, rs, st.lang);
    let html = chP(`${B(t.showing)}:`) + `<ul class="ch-ul">${res.applied.map(a => `<li>${esc(chLabel(a.key))} <small>${chMapless() ? '' : '· ' + (a.mode === 'fill' ? (st.lang === 'es' ? 'sombreado' : 'shaded') : (st.lang === 'es' ? 'símbolos' : 'symbols'))}${a.norm !== 'value' ? ' · ' + esc(chLc(chNormLabel(a.key, a.norm))) : ''}</small></li>`).join('')}</ul>`;
    if (notes.length) html += `<p class="ch-note">${notes.map(esc).join(' ')}</p>`;
    // a first finding for the lead dataset
    const k0 = keys[0], lead = res.applied.find(a => a.key === k0) || res.applied[0];
    if (lead) { const r = chVec(k0, { year, norm: lead.norm }); if (r) { const l = chList(r.values); if (l.length) html += chP(`${B(t.highest)}: ${esc(l[0].name)} (${esc(chVal(k0, l[0].v, lead.norm))}${chTie(l, 0, st.lang)}). ${B(t.lowest)}: ${esc(l[l.length - 1].name)} (${esc(chVal(k0, l[l.length - 1].v, lead.norm))}${chTie(l, l.length - 1, st.lang)}). ${B(t.island)}: ${esc(chVal(k0, r.values[r.values.length - 1], lead.norm))}.`); } }
    if (keys.some(k => (api.meta(k) || {}).moe)) html += `<p class="ch-note">${chMoeNote(st.lang)}</p>`;
    if (keys.length >= 2 && chAsksRelation(keys, st)) { const c = Tools.correlate({ a: keys[0], b: keys[1], year }); if (!c.error && Math.abs(c.r) >= .3) html += chP(esc(t.corr(c.r, c.n, chLabel(keys[0]), chLabel(keys[1]), c.r > 0 ? t.together : t.apart))); }
    const actions = [{ label: t.actWorkbench, run: () => api.benchOpen('table') }];
    if (keys.length >= 2) actions.unshift({ label: t.actScatter, run: () => api.benchOpen('scatter'), primary: true });
    else { const m = api.meta(k0); if (!m.snapshot && m.years.length > 1) actions.unshift({ label: t.actTrend, run: () => api.benchOpen('trend') }); }
    actions.push({ label: t.actSources, run: () => api.info(k0) });
    const tp = chTopic(k0, st.lang); if (tp) actions.push(tp);
    return { html, actions, follow: keys.length === 1 ? (st.lang === 'es' ? ['¿Dónde es más alto ese dato?', ...(chOneYear(api.meta(keys[0])) ? [] : ['¿Cómo ha cambiado ese dato?'])] : ['Where is it highest?', ...(chOneYear(api.meta(keys[0])) ? [] : ['How has it changed?'])]) : [] };
  },
  async value(st) {   // a dataset and a place: answer the number, and show it
    const api = chApi(), t = chTx(st.lang), k = st.keys[0], place = st.places[0], year = st.years[st.years.length - 1] ?? null, norm_ = chViewNorm(k), lens = [{ norm: 'value' }, ...(norm_ !== 'value' ? [{ norm: norm_ }] : [])];
    const i = api.placeIndex(place); let html = '';
    lens.forEach(lv => { const r = chVec(k, { year, norm: lv.norm }); if (!r) return; if (lv !== lens[0] && r.values[i] == null && api.missing(k, i)) return; const l = chList(r.values), pos = l.findIndex(x => x.i === i) + 1; html += chP(`${B(place)}: ${esc(chLabel(k))}${lv.norm !== 'value' ? ' · ' + esc(chLc(chNormLabel(k, lv.norm))) : ''} · ${r.year} → ${B(chCell(k, r.values[i], i, lv.norm))}${lv.norm === 'value' ? chMoeText(k, r.year, i) : ''}${pos ? ` (${st.lang === 'es' ? `puesto ${pos} de ${l.length} de mayor a menor` : `${chOrd(pos)} highest of ${l.length}`}; ${t.island}: ${esc(chVal(k, r.values[r.values.length - 1], lv.norm))})` : ''}.`); });
    if ((api.meta(k) || {}).moe) html += `<p class="ch-note">${chMoeNote(st.lang)}</p>`;
    await api.show({ layers: chPlan([k]), year, context: st.ctx, select: place });
    CH.ctx = { keys: [k], year, muni: place };
    return { html, actions: [{ label: t.actInspect, run: () => api.benchOpen('inspect') }, { label: t.actSources, run: () => api.info(k) }] };
  },
  async rank(st) {
    const api = chApi(), t = chTx(st.lang), k = st.keys[0], m = api.meta(k), year = st.years.length ? st.years[st.years.length - 1] : null, n = st.n_top;
    const within = /\bbarrios?\b|\b(?:donde|where|en que parte|what part)\s+(?:en|de|in|of)\b|\bdentro de\b|\bwithin\b/.test(st.n), towns = /\b(?:municipios?|pueblos?|municipalit\w*|towns?)\b/.test(st.n);
    if (st.u && st.places.length === 1 && (within || !towns) && !st.u.relate) {
      let inside = await chRankInside(st, k, year, n);
      const twin = !inside && [CH_BARRIO_TWIN[k], ...(st.alts || [])].find(x => x && api.meta(x));   // the same thing from the survey, which has barrio values
      if (!inside && twin && (inside = await chRankInside(st, twin, year, n))) { inside.html = chP(esc(st.lang === 'es' ? `«${chLabel(k)}» no tiene valores por barrio; por barrio uso «${chLabel(twin)}», de la encuesta.` : `“${chLabel(k)}” has no barrio values; by barrio this uses “${chLabel(twin)}”, from the survey.`)) + inside.html; st.keys = [twin, ...st.keys.filter(x => x !== twin)]; }
      if (inside) return inside;
    }   // "¿qué barrios de Ponce tienen más pobreza?" (ask.js)
    const ext = m.type === 'count' || m.type === 'total$', views = ext && chViewNorm(k) !== 'value' ? [{ norm: 'value' }, { norm: chViewNorm(k) }] : [{ norm: 'value' }];
    let html = '', first = null;
    for (const v of views) {
      const r = Tools.rank({ dataset: k, year, n, direction: st.dir, norm: v.norm }); if (r.error) continue; first = first || r;
      const mo = v.norm === 'value' && m.moe && api.moe ? api.moe(k, r.year) : null, rows = mo ? r.top.map(x => { const i = api.placeIndex(x.place); return { name: x.place, v: x.value, m: mo[i] }; }) : null;   // survey estimates: their margins, and which are unreliable
      html += chP(`${B(chTitle(k, v.norm, r.year))}${st.dir === 'asc' ? ` — ${st.lang === 'es' ? 'los más bajos' : 'lowest'}` : ''}`) + chTable([st.lang === 'es' ? 'Municipio' : 'Municipality', chClip(chLabel(k), 34)], [...r.top.map((x, j) => [x.place, chVal(k, x.value, v.norm, false, true) + (rows && rows[j].m != null && isFinite(rows[j].m) ? ` ±${m.type === 'rate' ? fmt(rows[j].m, 1) : chVal(k, rows[j].m)}` + (chUnreliable(rows[j].v, rows[j].m) ? (st.lang === 'es' ? ' (poco confiable)' : ' (unreliable)') : '') : '')]), [t.island, chVal(k, r.puertoRico, v.norm, false, true)]], st.lang);
      if (rows && rows.some(x => x.m != null)) { const all = api.places().slice(0, -1).map((p, i) => ({ name: p, v: chVec(k, { year: r.year }).values[i], m: mo[i] })).filter(x => x.v != null); html += chMoeRead(rows, all, st.lang, st.lang === 'es' ? 'municipios' : 'municipios'); }
    }
    if (views.length > 1) html += `<p class="ch-note">${st.lang === 'es' ? 'Los totales favorecen a los municipios grandes; la segunda tabla lo corrige por población.' : 'Totals favour big municipalities; the second table corrects for population.'}</p>`;
    html += chRankNotes(m, st.rest, st.n, st.lang);
    const notes = chYearNotes({ years: year ? [year] : [] }, [k], [chVec(k, { year })], st.lang); if (notes.length) html += `<p class="ch-note">${notes.map(esc).join(' ')}</p>`;
    const pl = st.u && st.places.length === 1 ? st.places[0] : null;
    if (pl && first) { const v0 = views[views.length - 1], r0 = chVec(k, { year, norm: v0.norm }), l0 = r0 ? chList(r0.values, st.dir) : [], i0 = api.placeIndex(pl), pos = l0.findIndex(x => x.i === i0) + 1; if (pos) html = chP(`${B(pl)}: ${esc(chVal(k, r0.values[i0], v0.norm))}; ${st.lang === 'es' ? `puesto ${pos} de ${l0.length} ${st.dir === 'asc' ? 'de menor a mayor' : 'de mayor a menor'}` : `${chOrd(pos)} of ${l0.length}, ${st.dir === 'asc' ? 'lowest first' : 'highest first'}`}. ${within ? esc(st.lang === 'es' ? 'No hay valores por barrio para este dato aquí, así que la tabla ordena los municipios.' : 'There are no barrio values for this dataset here, so the table ranks the municipios.') : ''}`) + html; }
    await api.show({ layers: chPlan([k]), year, context: st.ctx, select: pl || (first && first.top[0] ? first.top[0].place : undefined) });
    CH.ctx = { keys: [k], year, muni: pl };
    const actions = [{ label: t.actWorkbench, run: () => api.benchOpen('table'), primary: true }];
    if (!m.snapshot && m.years.length > 1) actions.push({ label: t.actTrend, run: () => api.benchOpen('trend') });
    actions.push({ label: t.actSources, run: () => api.info(k) });
    const tp = chTopic(k, st.lang); if (tp) actions.push(tp);
    return { html, actions, follow: st.lang === 'es' ? [...(chOneYear(m) ? [] : ['¿Cómo ha cambiado ese dato?']), 'Compárelo con la pobreza'] : [...(chOneYear(m) ? [] : ['How has it changed?']), 'Compare it with poverty'] };
  },
  async compare(st) {
    const api = chApi(), t = chTx(st.lang), [a, b] = st.keys, year = st.years.length ? st.years[st.years.length - 1] : null, c = Tools.correlate({ a, b, year });
    await api.show({ layers: [{ key: a, mode: 'fill', norm: chNormFor(a) }, { key: b, mode: 'fill', norm: chNormFor(b) }], year, context: st.ctx, bench: 'scatter', ...(st.places.length === 1 && st.u ? { select: st.places[0] } : {}) });   // a place named in the question is selected, so its dot stands out
    CH.ctx = { keys: [a, b], year, muni: null };
    if (c.error) return { html: chP(esc(chErr(c.error, st.lang))), actions: [] };
    const la = chTitle(a, c.normA, c.yearA), lb = chTitle(b, c.normB, c.yearB), dir = Math.abs(c.r) < .3 ? t.nolink : (c.r > 0 ? t.together : t.apart);
    let html = chP(`${B(chLabel(a))} ${st.lang === 'es' ? 'y' : 'and'} ${B(chLabel(b))}`) + chP(esc(t.corr(c.r, c.n, chLabel(a), chLabel(b), dir)));
    html += `<p class="ch-note">${esc(la)} ↔ ${esc(lb)}</p>`;
    if (Math.abs(c.r) >= .3 && c.outliers.length) html += chP(esc(t.outliers(c.outliers.slice(0, 3).map(o => o.place).join(', '))));
    html += `<p class="ch-note">${esc(t.caveat)}</p>`;
    return { html, actions: [{ label: t.actScatter, run: () => api.benchOpen('scatter'), primary: true }, { label: t.actSources, run: () => api.info(a) }] };
  },
  async trend(st) {
    const api = chApi(), t = chTx(st.lang), k = st.keys[0], m = api.meta(k);
    if (chOneYear(m)) { return { html: chP(st.lang === 'es' ? `${B(T(m.label))} es un solo corte de datos; no tengo serie en el tiempo.` : `${B(T(m.label))} is a single snapshot; there is no time series.`), actions: [] }; }
    const from = st.since || (st.years.length > 1 ? Math.min(...st.years) : (st.years.length === 1 && /\b(since|desde)\b/.test(st.n) ? st.years[0] : null)), to = st.until || (st.years.length > 1 ? Math.max(...st.years) : null);   // since, until: an event the question dates by (ask.js reads "después de María" as 2017)
    const r = Tools.trend({ dataset: k, from, to, norm: 'value' }); if (r.error) return { html: chP(esc(chErr(r.error, st.lang))), actions: [] };
    const pr = r.puertoRico, pct = r.rate ? null : (pr.from ? (pr.to - pr.from) / pr.from * 100 : null);
    let html = chP(`${B(chLabel(k))}: ${esc(t.island)} ${r.from} → ${r.to}: ${esc(chVal(k, pr.from))} → ${B(chVal(k, pr.to))}${pct != null ? ` (${pct >= 0 ? '+' : '−'}${fmt(Math.abs(pct), 1)}%)` : (pr.from != null && pr.to != null ? ` (${pr.to - pr.from >= 0 ? '+' : '−'}${fmt(Math.abs(pr.to - pr.from), 1)} ${st.lang === 'es' ? 'puntos' : 'points'})` : '')}.`);
    const f = (x) => `${x.place} (${r.rate ? (x.d >= 0 ? '+' : '−') + fmt(Math.abs(x.d), 1) + (st.lang === 'es' ? ' pts' : ' pts') : (x.d >= 0 ? '+' : '−') + fmt(Math.abs(x.d), 0) + '%'})`;
    const pl = st.u && st.places.length === 1 ? st.places[0] : null, own = pl && r.all.find(x => x.place === pl);   // a place named in the question: its own change first, and where it stands (ask.js)
    if (pl) html = (own ? chP(`${B(pl)} ${r.from} → ${r.to}: ${esc(chVal(k, own.x))} → ${B(chVal(k, own.y))} (${esc(f(own).slice(pl.length + 2, -1))}); ${st.lang === 'es' ? `puesto ${r.all.indexOf(own) + 1} de ${r.all.length} en el cambio, de mayor a menor` : `${chOrd(r.all.indexOf(own) + 1)} of ${r.all.length} by change, highest first`}.`) : chP(esc(st.lang === 'es' ? `${pl} no tiene valores para ${r.from} y ${r.to}.` : `${pl} has no values for ${r.from} and ${r.to}.`))) + html;
    const es2 = st.lang === 'es', fell = r.down.length && r.down[0].d < 0, rose = r.up.filter(x => x.d > 0), still = r.up.filter(x => x.d <= 0); st.period = [r.from, r.to];
    // the words follow the signs: places that rose are "rose most", the others of the top three (all of them when every place fell) "fell least"
    const top = [rose.length ? `${B(es2 ? 'Más subieron' : 'Rose most')}: ${esc(rose.map(f).join(', '))}.` : '', still.length ? `${B(es2 ? 'Menos bajaron' : 'Fell least')}: ${esc(still.map(f).join(', '))}.` : ''].filter(Boolean).join(' ');
    html += chP(`${top} ${B(fell ? (es2 ? 'Más bajaron' : 'Fell most') : (es2 ? 'Subieron menos' : 'Rose least'))}: ${esc(r.down.map(f).join(', '))}.`);
    if (m.time && m.time.type === 'window') html += `<p class="ch-note">${chWindowNote(r.from, r.to, st.lang)}</p>`;
    if (m.unit === '$') html += `<p class="ch-note">${st.lang === 'es' ? 'Dólares del año de cada dato; use “ajustado por inflación” en la capa para comparar en dólares constantes.' : 'Dollars of each year; tick “inflation-adjusted” on the layer to compare in constant dollars.'}</p>`;
    await api.show({ layers: [{ key: k, mode: 'fill', norm: r.rate ? 'change' : 'change', real: m.unit === '$' }], year: null, base: r.from, context: st.ctx, ...(pl ? { select: pl } : {}) });
    api.trendPlaces([...(pl ? [pl] : []), ...[...r.up.slice(0, 2), ...r.down.slice(0, 2)].map(x => x.place)]); api.benchOpen('trend');
    CH.ctx = { keys: [k], year: null, muni: null };
    return { html: html + (chMapless() ? '' : `<p class="ch-note">${st.lang === 'es' ? `El mapa muestra el cambio desde ${r.from}.` : `The map shows the change since ${r.from}.`}</p>`), actions: [{ label: t.actTrend, run: () => api.benchOpen('trend'), primary: true }, { label: t.actSources, run: () => api.info(k) }] };
  },
  async areas(st) {   // two places or more side by side: the datasets asked for, or a few headline ones (plan item 14, the compare_areas tool)
    const api = chApi(), t = chTx(st.lang), es = st.lang === 'es', places = st.places.slice(0, 5), ix = places.map(p => api.placeIndex(p)), year = st.years[st.years.length - 1] ?? null;
    const keys = st.keys.length ? st.keys.slice(0, 4) : ['population', 'poverty_pct', 'median_hh_income', 'laus_unemp_rate', 'qcew_jobs', 'qcew_avg_pay'].filter(k => api.meta(k));
    const rows = [];
    // the datasets asked for also as a shaded map compares them; the headline ones as published
    keys.forEach(k => { const nm = chNormFor(k); for (const n of (nm !== 'value' && st.keys.length && k !== 'population' ? ['value', nm] : ['value'])) { const r = chVec(k, { year, norm: n }); if (!r) continue; rows.push([`${chShort(chLabel(k))}${n !== 'value' ? ' (' + chLc(chNormLabel(k, n)) + ')' : ''} · ${r.year}`, ...ix.map(i => chCell(k, r.values[i], i, n)), chVal(k, r.values[r.values.length - 1], n)]); } });
    let html = chP(B(places.join(' · '))) + chTable([es ? 'Indicador' : 'Indicator', ...places, t.island], rows, st.lang);
    if (keys.some(k => (api.meta(k) || {}).moe)) html += `<p class="ch-note">${chMoeNote(st.lang)}</p>`;
    await api.show({ layers: chPlan([keys[0]]), year, context: st.ctx, select: places[0] });
    CH.ctx = { keys: keys.slice(0, 1), year, muni: places[0] };
    return { html, actions: places.slice(0, 3).map(p => chProfileAction(p, st.lang)).filter(Boolean) };
  },
  async compose(st) {   // "an index of poverty and unemployment": the composite builder opens with those inputs; the person sets the directions and weights (plan item 14, the composite tool)
    const api = chApi(), es = st.lang === 'es', keys = st.keys.slice(0, 12), list = keys.map(k => chLabel(k)).join('; ');
    const opened = !!api.compose && api.compose(keys) !== false;   // false on the 3D view: the builder is on the 2D map, behind a button (ask3d.js)
    CH.ctx = { keys: keys.slice(0, 2), year: null, muni: null };
    const n = B(String(keys.length)), there = opened ? [] : [{ label: es ? 'Abrir el constructor en el mapa 2D' : 'Open the builder on the 2D map', run: () => api.compose(keys, true), primary: true }];
    return { html: chP(opened ? (es ? `Abrí el constructor de índices compuestos de la mesa de trabajo con ${n} componentes: ${esc(list)}.` : `I opened the workbench's composite builder with ${n} inputs: ${esc(list)}.`) : (es ? `El constructor de índices compuestos está en la mesa de trabajo del mapa 2D. El botón lo abre en otra pestaña con ${n} componentes: ${esc(list)}.` : `The composite builder is on the 2D map's workbench. The button opens it in another tab with ${n} inputs: ${esc(list)}.`))
      + chP(esc(es ? 'No hay una dirección elegida: indique para cada uno si un valor más alto es mejor o peor, ajuste los pesos y pulse «Poner en el mapa». El resultado es su propio índice, no uno oficial.' : 'No direction is set: say for each whether a higher value is better or worse, adjust the weights and press "Put on the map". The result is your own index, not an official one.')), actions: there };
  },
  async muni(st) {
    const api = chApi(), t = chTx(st.lang), place = st.places[0], i = api.placeIndex(place);
    const PROFILE = [['population', 'value'], ['poverty_pct', 'value'], ['median_hh_income', 'value'], ['laus_unemp_rate', 'value'], ['qcew_jobs', 'value'], ['qcew_avg_pay', 'value'], ['jobs_per_employed_resident', 'value'], ['gov_job_share_pct', 'value'], ['tourism_jobs', 'shareJobs'], ['commute_45plus_pct', 'value'], ['median_gross_rent', 'value'], ['fed_awards_total', 'perCapita']];
    const rows = [], stand = [];
    PROFILE.forEach(([k, nm]) => { const r = chVec(k, { norm: nm }); if (!r) return; const l = chList(r.values), pos = l.findIndex(x => x.i === i) + 1; if (!pos) return; rows.push([`${chShort(chLabel(k))}${nm !== 'value' ? ' (' + chLc(chNormLabel(k, nm)) + ')' : ''} · ${r.year}`, chVal(k, r.values[i], nm, false, true), chVal(k, r.values[r.values.length - 1], nm, false, true), `${pos}/${l.length}`]); if (pos <= 5 || pos >= l.length - 4) stand.push(`${chLabel(k)} (${pos <= 5 ? (st.lang === 'es' ? 'entre los 5 más altos' : 'top 5') : (st.lang === 'es' ? 'entre los 5 más bajos' : 'bottom 5')})`); });
    let html = chP(`${B(place)}`) + chTable([st.lang === 'es' ? 'Indicador' : 'Indicator', place, t.island, t.rank], rows, st.lang) + `<p class="ch-note">${st.lang === 'es' ? 'Posición 1 = el valor más alto entre los 78 municipios.' : 'Rank 1 = the highest value among the 78 municipalities.'}</p>`;
    if (stand.length) html += chP(`${B(st.lang === 'es' ? 'Se destaca en' : 'Stands out for')}: ${esc(stand.slice(0, 5).join('; '))}.`);
    await api.show({ layers: [{ key: 'poverty_pct', mode: 'fill' }, { key: 'qcew_jobs', mode: 'symbol' }], year: null, context: st.ctx, select: place });
    CH.ctx = { keys: ['poverty_pct', 'qcew_jobs'], year: null, muni: place };
    const wants = /\b(profile|perfil|ficha|everything about|todo sobre)\b/.test(st.n), prof = chProfileAction(place, st.lang);   // the area profile: every dataset for the place (profile.html)
    return { html, actions: [...(wants && prof ? [prof] : []), { label: t.actInspect, run: () => api.benchOpen('inspect'), primary: !wants }, ...(!wants && prof ? [prof] : [])], follow: st.lang === 'es' ? [`¿Cómo ha cambiado el empleo en ${place}?`] : [`How have jobs changed in ${place}?`] };
  },
  async sources(st) {
    const api = chApi(), t = chTx(st.lang), keys = st.keys.slice(0, 3);
    let html = '';
    keys.forEach(k => { const m = api.meta(k); html += chP(`${B(T(m.label))}`) + chP(`${B(t.defn)}: ${I18N.en(esc(m.definition))}`) + chP(`${B(t.years)}: ${m.snapshot ? (st.lang === 'es' ? 'un corte de ' : 'one snapshot, ') + m.ys[0] : m.ys[0] + '–' + m.ys[m.ys.length - 1]}. ${esc(m.ref || '')}`); });
    html += chP(`${B(t.sources)}:`) + chLinks(keys);
    if (st.lang === 'es') html += `<p class="ch-note">Las definiciones y las notas de las fuentes están en inglés por ahora.</p>`;
    return { html, actions: [...keys.map(k => ({ label: `${t.open}: ${chLabel(k).slice(0, 28)}`, run: () => api.info(k) })), { href: 'dictionary.html#' + api.dictId(keys[0]), label: st.lang === 'es' ? 'Entrada en el diccionario de datos' : 'Entry in the data dictionary' }] };
  },
  async catalog(st) {
    const api = chApi(), t = chTx(st.lang), ds = api.datasets(), reg = CH.registry;
    const topic = st.n.replace(/\b(what|which|data|datasets?|do|you|have|about|on|list|the|twin|observatory|observatorio|are|there|in|que|datos|hay|tienen|sobre|de|lista|catalogo)\b/g, ' ').replace(/\s+/g, ' ').trim();
    const groups = {}; ds.forEach(d => (groups[d.group] = groups[d.group] || []).push(d));
    const gHits = topic ? ds.filter(d => topic.split(' ').some(w => w.length > 3 && norm(d.group + ' ' + T(d.group)).split(/[^a-z]+/).some(g => g.startsWith(w.slice(0, Math.max(4, w.length - 2)))))) : [];
    const all = [...new Map([...st.keys.map(k => ds.find(d => d.key === k)).filter(Boolean), ...gHits, ...(topic ? chFuzzy(topic, 10) : [])].map(d => [d.key, d])).values()], fz = all.slice(0, 14);
    let html;
    if (fz.length) html = chP(`${B(st.lang === 'es' ? 'Lo que tengo sobre eso' : 'What I have on that')} (${fmt(all.length)}):`) + `<ul class="ch-ul">${fz.map(d => `<li>${esc(T(d.label))} <small>· ${esc(T(d.group))} · ${d.snapshot || !d.years ? (st.lang === 'es' ? 'un corte de datos' : 'snapshot') : d.years[0] + '–' + d.years[d.years.length - 1]}</small></li>`).join('')}</ul>` + (all.length > fz.length ? `<p class="ch-note">+${fmt(all.length - fz.length)} ${st.lang === 'es' ? 'más: abra Explorar para ver todos.' : 'more: open Explore to browse them all.'}</p>` : '');
    else html = chP(st.lang === 'es' ? `El observatorio tiene ${B(fmt(ds.length))} conjuntos de datos por municipio, en ${fmt(Object.keys(groups).length)} grupos${reg ? `, ${fmt(reg.total_bytes / 1048576, 0)} MB publicados` : ''}:` : `The observatory has ${B(fmt(ds.length))} datasets by municipality, in ${fmt(Object.keys(groups).length)} groups${reg ? `, ${fmt(reg.total_bytes / 1048576, 0)} MB published` : ''}:`) + `<ul class="ch-ul">${Object.entries(groups).map(([g, a]) => `<li>${esc(T(g))} <small>· ${a.length}</small></li>`).join('')}</ul>` + chP(st.lang === 'es' ? 'Además: lugares turísticos, zonas inundables, áreas protegidas, uso de terrenos, rutas y paradas de transporte, y barrios.' : 'Also: tourism places, flood zones, protected areas, land use, transit routes and stops, and barrios.');
    return { html, actions: [{ label: t.askMissing, run: () => chAsk(st.lang === 'es' ? '¿Qué datos faltan?' : 'What data is missing?') }, { href: 'dictionary.html', label: st.lang === 'es' ? 'Abrir el diccionario de datos' : 'Open the data dictionary' }], follow: t.chips.slice(0, 2) };
  },
  async missing(st) {
    const t = chTx(st.lang), w = CH.wanted; if (!w) return { html: chP(esc(t.noWanted)), actions: [] };
    const by = {}; w.items.forEach(x => (by[x.theme] = by[x.theme] || []).push(x));
    const wish = chWish();
    let html = chP(st.lang === 'es' ? `${B('Datos que podríamos agregar')} (${fmt(w.items.length)}, todos candidatos: falta confirmar fuente, licencia y términos antes de recolectar):` : `${B('Datasets we could add')} (${fmt(w.items.length)}, all candidates: source, license and terms must be confirmed before anything is harvested):`);
    if (st.lang === 'es') html += `<p class="ch-note">Los títulos y las descripciones de la lista están en inglés por ahora.</p>`;
    html += Object.entries(by).map(([th, a]) => `<details class="ch-det"><summary>${esc(T(th))} <small>· ${a.length}</small></summary><ul class="ch-ul">${a.map(x => `<li>${x.url ? `<a href="${esc(x.url)}" target="_blank" rel="noopener">${esc(x.title)}</a>` : esc(x.title)} <small>· ${esc(x.status)} · ${esc(x.cadence)} · ${esc(x.licence)}</small><br><small>${esc(x.why)}</small></li>`).join('')}</ul></details>`).join('');
    if (wish.length) html += chP(`${B(st.lang === 'es' ? 'Peticiones de la gente' : 'Requests people made')} (${fmt(wish.length)}):`) + `<ul class="ch-ul">${wish.slice(-8).map(x => `<li>${esc(x.q)}</li>`).join('')}</ul>`;
    const actions = []; if (wish.length) { actions.push({ label: t.actCopy, run: () => chCopyWish() }); actions.push({ href: chIssueUrl(wish), label: t.actIssue }); }
    return { html: html + `<p class="ch-note">${st.lang === 'es' ? 'Lista actualizada el' : 'List updated'} ${esc(chDate(w.updated))}.</p>`, actions };
  },
  async size(st) {
    const t = chTx(st.lang), r = CH.registry; if (!r) return { html: chP(esc(t.noInventory)), actions: [] };
    const mb = (b) => fmt(b / 1048576, 1), big = [...r.files].sort((a, b) => b.bytes - a.bytes).slice(0, 5);
    let html = chP(st.lang === 'es' ? `${B('Tamaño de los datos')}: ${mb(r.total_bytes)} MB en ${fmt(r.files.length)} archivos, ${fmt(r.used_fraction * 100, 1)}% del límite de 1 GB de GitHub Pages.` : `${B('Size of the data')}: ${mb(r.total_bytes)} MB in ${fmt(r.files.length)} files, ${fmt(r.used_fraction * 100, 1)}% of the 1 GB GitHub Pages limit.`);
    html += `<ul class="ch-ul">${big.map(f => `<li>${esc(st.lang === 'es' && f.title_es ? f.title_es : f.title)} <small>· ${mb(f.bytes)} MB</small></li>`).join('')}</ul>` + `<p class="ch-note">${esc(T(r.growth_note))}</p>`;
    return { html, actions: [] };
  },
  async insights(st) { return chInsights(st); },
  async year(st) { const y = st.years[0]; chApi().setYear(y); CH.ctx.year = y; return { html: chP(chTx(st.lang).sawYear(y)), actions: [] }; },
  async clear(st) { if (CH.handed) return { html: chP(esc(st.lang === 'es' ? 'Una pregunta que llega en un enlace no quita las capas del mapa. Para quitarlas, pídalo aquí.' : 'A question that arrives in a link does not turn the map’s layers off. To turn them off, ask here.')), actions: [] };   // a link must not clear the map
    if (chMapless()) return { html: chP(esc(st.lang === 'es' ? 'Esta página no tiene mapa, así que no hay capas que quitar.' : 'This page has no map, so there are no layers to turn off.')), actions: [] }; chApi().clear(); if (typeof ActiveLayers !== 'undefined' && ActiveLayers && ActiveLayers.off) ActiveLayers.off(null); CH.ctx = { keys: [], year: null, muni: null }; return { html: chP(chTx(st.lang).clearedMap), actions: [] }; },
  async help(st) { const t = chTx(st.lang); return { html: chP(t.hello) + chP(`${B(t.tryAsk)}`) + `<ul class="ch-ul">${t.chips.map(c => `<li>${esc(c)}</li>`).join('')}</ul>`, actions: [] }; },
  async practitioners(st) {   // nurses: the NPI registry lists only nurses who bill, so the observatory holds no count of them; doctors are counted (providers_series.json)
    const es = st.lang === 'es';
    const html = chP(es ? 'El observatorio no tiene el número de enfermeras: el registro federal de proveedores (NPPES) solo incluye a las que facturan, unas 1,250 frente a decenas de miles que trabajan en Puerto Rico. Sí tiene los médicos, dentistas, farmacéuticos y otros proveedores registrados en cada municipio, y las áreas de escasez de la Administración de Recursos y Servicios de Salud (HRSA) de EE. UU.'
                      : 'The observatory has no count of nurses: the federal provider registry (NPPES) lists only those who bill, about 1,250 against tens of thousands working in Puerto Rico. It does have the physicians, dentists, pharmacists and other providers registered in each municipio, and the shortage areas of the federal Health Resources and Services Administration (HRSA).');
    return { html, actions: [{ label: es ? 'Ver los médicos de atención primaria' : 'Show primary care physicians', run: () => chAsk(es ? 'médicos de atención primaria' : 'primary care physicians'), primary: true }],
             follow: es ? ['escasez de atención primaria', 'dentistas'] : ['primary care shortage areas', 'dentists'] };
  },
  async unknown(st) {
    const api = chApi(), t = chTx(st.lang), fz = chFuzzy(st.rest || st.q, 4), w = CH.wanted ? CH.wanted.items.filter(x => { const hay = norm(`${x.title} ${x.why} ${x.theme}`); return norm(st.rest || st.q).split(/[^a-z0-9]+/).some(tok => tok.length > 3 && !STOP.has(tok) && hay.includes(tok.slice(0, Math.max(4, tok.length - 2)))); }).slice(0, 3) : [];
    const content = norm(st.q).split(/[^a-z0-9]+/).filter(x => x.length > 3 && !STOP.has(x));
    if (api.notLoaded && api.notLoaded().length) return { html: chP(esc(st.lang === 'es' ? 'Algunos datos no se cargaron, así que quizá no pueda responder. Recargue la página y vuelva a preguntar.' : 'Some data did not load, so I may not be able to answer. Reload the page and ask again.')), actions: [] };
    if (content.length >= 2) chAddWish(st.q);
    const dom = chDomainAnswer(st); if (dom) return dom;   // a field of the registry is named: what it holds, or that it holds nothing yet
    let html = chP(esc(t.noMatch));
    if (fz.length) html += chP(`${B(t.closest)}`) + `<ul class="ch-ul">${fz.map(d => `<li>${esc(T(d.label))}</li>`).join('')}</ul>`;
    if (w.length) html += chP(`${B(t.wantedHit)}`) + `<ul class="ch-ul">${w.map(x => `<li>${esc(x.title)} <small>· ${esc(x.status)}</small></li>`).join('')}</ul>`;
    if (content.length >= 2) html += `<p class="ch-note">${esc(t.noted)}</p>`;
    return { html, actions: [{ label: t.askMissing, run: () => chAsk(st.lang === 'es' ? '¿Qué datos faltan?' : 'What data is missing?') }], follow: t.chips.slice(0, 3), chips: fz.slice(0, 3).map(d => d.label) };
  },
};

/** The barrios of the place a ranking names, ranked by the dataset's barrio values, and the map shaded by barrio; null when the dataset has no barrio values here
    (the 3D view shows municipios only) or the place has fewer than two barrios with a value: the ranking of the municipios answers then. */
async function chRankInside(st, k, year, n) {
  const api = chApi(), es = st.lang === 'es', pl = st.places[0], pid = api.placeId(pl);
  const s = pid && api.levelSeries ? await api.levelSeries(k, 'barrio', year).catch(() => null) : null; if (!s || !s.values) return null;
  const name = (x) => x && typeof x === 'object' ? (es ? x.es : x.en) || x.en || x.es : x;
  const rows = s.ids.map((id, j) => ({ id: String(id), name: name(s.names[j]), v: s.values[j], m: s.moe ? s.moe[j] : null })).filter(x => x.id.startsWith(pid) && x.v != null && isFinite(x.v)).sort((a, b) => st.dir === 'asc' ? a.v - b.v : b.v - a.v);
  if (rows.length < 2) return null;
  const per = (s.meta && s.meta.period) || year, top = rows.slice(0, Math.max(n, 5)), rate = (api.meta(k) || {}).type === 'rate';
  let html = chP(`${B(es ? `Barrios de ${pl}` : `Barrios of ${pl}`)} · ${esc(chLabel(k))}${per ? ' · ' + per : ''}${st.dir === 'asc' ? ` — ${es ? 'los más bajos' : 'lowest'}` : ''}`) + chTable(['Barrio', chClip(chLabel(k), 34)], top.map(x => [x.name, chVal(k, x.v) + (x.m != null && isFinite(x.m) ? ` ±${rate ? fmt(x.m, 1) : chVal(k, x.m)}` : '') + (chUnreliable(x.v, x.m) ? (es ? ' (poco confiable)' : ' (unreliable)') : '')]), st.lang);
  html += chMoeRead(top, rows, st.lang, es ? `barrios de ${pl}` : `barrios of ${pl}`);
  await api.show({ layers: [{ key: k, mode: 'fill', norm: 'value', level: 'barrio' }], year, context: [...new Set([...(st.ctx || []), 'lyBarrios'])], select: pl });
  CH.ctx = { keys: [k], year, muni: pl }; st.level = 'barrio';
  return { html, actions: [{ label: chTx(st.lang).actWorkbench, run: () => api.benchOpen('table') }, { label: chTx(st.lang).actSources, run: () => api.info(k) }], follow: es ? [`¿Cómo ha cambiado ese dato en ${pl}?`] : [`How has it changed in ${pl}?`] };
}
// Survey estimates (ACS) by area: a 90% margin of error (MOE) larger than half the estimate, or a zero with a margin, is an unreliable estimate (a coefficient of
// variation over 30%, the Census Bureau's and most statistical agencies' threshold); two estimates differ when |a − b| / √(SEa² + SEb²) > 1.645, SE = MOE / 1.645
// (the Census Bureau's test at 90% confidence).
const chUnreliable = (v, m) => m != null && isFinite(m) && v != null && isFinite(v) && (v === 0 ? m > 0 : m / Math.abs(v) > 0.5);
const chDiffers = (a, b) => a.m == null || b.m == null || !isFinite(a.m) || !isFinite(b.m) ? true : Math.abs(a.v - b.v) / Math.sqrt((a.m / 1.645) ** 2 + (b.m / 1.645) ** 2) > 1.645;
function chMoeRead(top, rows, lang, what) {   // the notes under a ranked table of survey estimates: how many are unreliable, and which of the first are not distinguishable from the first
  const es = lang === 'es', bad = rows.filter(x => chUnreliable(x.v, x.m)).length, tie = top.slice(1).filter(x => !chDiffers(top[0], x)).map(x => x.name);
  const out = [es ? `${rows.length} ${what} con valor.` : `${rows.length} ${what} with a value.`];
  if (bad) out.push(es ? `${bad} de ${rows.length} son estimados poco confiables (margen de error mayor que la mitad del estimado): úselos con cautela.` : `${bad} of ${rows.length} are unreliable estimates (a margin of error larger than half the estimate): use them with care.`);
  const all = tie.length === top.length - 1 && tie.length > 1;
  if (tie.length) out.push(es ? `${all ? 'Los siguientes' : tie.join(', ')} ${tie.length === 1 ? 'no se distingue' : 'no se distinguen'} estadísticamente de ${top[0].name} (al 90% de confianza, la prueba de la Oficina del Censo): el orden entre ellos puede deberse al margen de error.` : `${all ? 'The next ones' : tie.join(', ')} ${tie.length === 1 ? 'is' : 'are'} not statistically different from ${top[0].name} (at 90% confidence, the Census Bureau's test): their order may be the margin of error.`);
  else if (top.length > 1 && top[0].m != null) out.push(es ? `${top[0].name} se distingue estadísticamente de los siguientes (al 90% de confianza).` : `${top[0].name} is statistically different from the next ones (at 90% confidence).`);
  return `<p class="ch-note">${esc(out.join(' '))}</p>`;
}
/** A link to the area profile of a place (profile.html), or null when the page does not know its code. */
function chProfileAction(place, lang) {
  const id = chApi().placeId && chApi().placeId(place);
  return id ? { href: 'profile.html?area=' + id, label: lang === 'es' ? `Perfil de ${place}` : `Profile of ${place}` } : null;
}
/** When a question the chat cannot answer names a field of the registry (catalog.json: "salud", "environment", "public money"): how many datasets the field holds and a few of them,
    or that it holds none yet; the field's own example questions follow. Null when no field is named. */
function chDomainAnswer(st) {
  const cat = typeof S !== 'undefined' && S.catalog; if (!cat || !cat.index) return null;   // chAsk has waited for the index (catalog_index.json)
  const api = chApi(), es = st.lang === 'es', words = norm(st.n).split(/[^a-z0-9ñ]+/).filter(x => x.length > 3 && !STOP.has(x));
  const named = cat.domains.filter(d => !String(d.id).startsWith('system')).map(d => ({ d, hit: [d.name.en, d.name.es].some(nm => { const ws = norm(nm).split(/[^a-z0-9ñ]+/).filter(x => x.length > 3 && !STOP.has(x)); return ws.length && ws.every(x => words.some(q => chSame(q, x))); }) })).filter(x => x.hit).map(x => x.d);
  if (!named.length) return null;
  const d = named.sort((a, b) => (b.parent ? 1 : 0) - (a.parent ? 1 : 0))[0], F = cat.index.fields, dom = new Map(cat.index.rows.map(r => [r[F.indexOf('id')], r[F.indexOf('domain')]]));
  const mine = api.datasets().filter(x => { const g = dom.get(api.dictId(x.key)) || ''; return g === d.id || g.startsWith(d.id + '.'); });
  const name = es ? d.name.es : d.name.en;
  let html;
  if (mine.length) html = chP(es ? `No encontré un conjunto de datos que responda eso. En ${B(name)} el observatorio tiene ${B(fmt(mine.length))} conjuntos de datos por municipio, por ejemplo:` : `I could not find a dataset that answers that. In ${B(name)} the observatory has ${B(fmt(mine.length))} datasets by municipality, for example:`)
    + `<ul class="ch-ul">${mine.slice(0, 6).map(x => `<li>${esc(T(x.label))}</li>`).join('')}</ul>`;
  else html = chP(es ? `Todavía no hay datos de ${B(name)} en el observatorio.` : `The observatory has no data on ${B(name)} yet.`);
  html += `<p class="ch-note">${esc(chTx(st.lang).noted)}</p>`;
  return { html, actions: [{ label: chTx(st.lang).askMissing, run: () => chAsk(es ? '¿Qué datos faltan?' : 'What data is missing?') }], follow: ((d.examples || {})[st.lang] || []).slice(0, 3) };
}
// ── Understanding (ask.js): typos, topics, layers, places and time, on top of the rules above (docs/ask.md) ───────────────────
// The rules above (CONCEPTS, the groups, CH_CONTEXT) answer what they always answered. ask.js reads the question again with a lexicon of everyday words
// (Puerto Rican ones too), the layer registry, the glossary and well-known place names, and adds what the rules left: a second topic, a layer, a place, a time, a
// typo, an approximation when the data do not exist, and what must never be drawn. It loads with the first question, so no page's first load carries it.
let CH_MOD = null;
const chScript = (src) => new Promise((ok, fail) => { const s = document.createElement('script'); s.src = src; s.onload = ok; s.onerror = () => { s.remove(); fail(new Error(src)); }; document.body.appendChild(s); });
// The page actions an answer of the understanding takes, here so that neither page carries them before the chat opens. Both pages hold their layers as switches
// (input#id): turned on as a person would, so the "layers on" chip lists them and "Turn all off" and Undo treat them like any other. The 2D map is Leaflet, the 3D view MapLibre.
const chView = () => typeof document !== 'undefined' && document.getElementById('metric') ? '3d' : '2d';   // the 3D view's column menu (#metric)
function chLayersOn(ids) {   // the switches with these ids, on (never off); the ids that are on
  const done = []; if (chMapless()) return done;   // a page without a map has no switches: "Show on the map" hands the question over
  (ids || []).forEach(id => { const el = /^ly\w+$|^walkRings$/.test(id) && id !== 'lyCols' && document.getElementById(id); if (!el || el.type !== 'checkbox') return; if (!el.checked) { el.checked = true; el.dispatchEvent(new Event('change')); } done.push(id); });
  if (typeof ecContextSync === 'function') ecContextSync();   // the Economy tab's copy of the switches (economy.js)
  return done;
}
function chGoTo(t) {   // the map to a municipio (selected, as an answer selects it) or to a point { lat, lon, z } (a place the chat knows, such as Santurce); false when it did not move
  const api = chApi(); if (chMapless()) return false;
  if (typeof t === 'string' || (t && t.muni)) api.show({ clear: false, layers: [], select: typeof t === 'string' ? t : t.muni });   // the municipio selected, as an answer selects it
  if (typeof t === 'string') return true;
  if (!t || !isFinite(t.lat) || !isFinite(t.lon) || typeof map === 'undefined' || !map) return false;
  const reduce = typeof matchMedia === 'function' && matchMedia('(prefers-reduced-motion: reduce)').matches, leaflet = typeof map.invalidateSize === 'function';
  const go = () => leaflet ? map.flyTo([t.lat, t.lon], t.z || 14, { duration: reduce ? 0 : .8 }) : map.flyTo({ center: [t.lon, t.lat], zoom: t.z || 14, duration: reduce ? 0 : 1200 });
  go();
  // the municipio's selection may move the map to its centre a moment later (economy.js): the point is where the map ends
  if (typeof map.on === 'function' && typeof map.off === 'function') {
    const t0 = Date.now(), back = () => { const c = map.getCenter(), lat = c.lat, lng = c.lng; if (Date.now() - t0 > 3000) { map.off('moveend', back); return; } if (Math.abs(lat - t.lat) > .01 || Math.abs(lng - t.lon) > .01) { map.off('moveend', back); go(); } };
    map.on('moveend', back);
  }
  return true;
}
function chMetrics() {   // the 3D view's own column measures, by their names in the page language; none on the 2D map
  const sel = typeof document !== 'undefined' && document.getElementById('metric'); return sel ? [...sel.options].filter(o => o.value && o.value !== '__any').map(o => [o.value, o.textContent.trim()]) : [];
}
async function chSetMetric(v) {   // the 3D columns on one of those measures (twin3d.js setMetric)
  const sel = document.getElementById('metric'); if (!sel || ![...sel.options].some(o => o.value === v) || typeof setMetric !== 'function') return false;
  sel.value = v; document.getElementById('lyCols').checked = true; await setMetric(v); if (typeof showTab === 'function') showTab('layers', { open: false }); return true;
}
/** ask.js and its index of what Ask can show, built once (the first question waits for it); null when ask.js could not load, and the rules answer alone. */
function chAskWords() {   // the words of the dictionary entries (catalog index, column ask), for the generated lexicon and ask.js's index
  if (!CH.ask && typeof S !== 'undefined' && S.catalog && S.catalog.index) { const F = S.catalog.index.fields, a = F.indexOf('ask'), id = F.indexOf('id'); CH.ask = {}; if (a >= 0) S.catalog.index.rows.forEach(r => { if (r[a]) CH.ask[r[id]] = r[a]; }); }
}
function chAskModule() {
  if (CH_MOD) return CH_MOD;
  return CH_MOD = (async () => {
    const api = chApi(), es = I18N.lang === 'es', boot = typeof ChatBoot !== 'undefined' && ChatBoot.extra ? ChatBoot.extra() : null;   // chatboot.js starts ask.js and the layer registry beside chat.js
    // the Spanish summaries of the datasets (catalog_es.json, 33 KB) only on a Spanish page: an English page's index has no Spanish dataset names to match them with
    const files = Promise.all([...(es ? ['data/catalog_es.json'] : []), 'data/glossary_forms_en.json', 'data/glossary_forms_es.json'].map(f => Data.json(f).catch(() => null)));
    await (boot || Promise.all([typeof Ask === 'undefined' ? chScript('js/ask.js?v=15') : null, !(typeof Core !== 'undefined' && Core.layers) ? chScript('js/core/layers.js?v=19').catch(() => null) : null]));
    if (typeof Ask === 'undefined') await chScript('js/ask.js?v=15');
    // the index needs the page's datasets and municipios, and the dictionary's ask words: built before them (the chat opens before the Economy tab has loaded), it held no
    // municipio and no dataset, so a misspelt municipio was never read and the datasets' own words never matched (docs/ask.md, round 4)
    const idx = typeof S !== 'undefined' && S.catalog ? withIndex(S.catalog).catch(() => null) : null;
    if (!(api && (await api.ready().catch(() => false)))) throw new Error('data');
    await idx; chAskWords();
    const got = await files, [words, gEn, gEs] = es ? got : [null, ...got];
    const datasets = api.datasets().map(d => { const m = api.meta(d.key) || {}, ys = m.ys || []; return { key: d.key, label: d.label, labelEs: es ? T(d.label) : '', group: d.group, groupEs: es ? T(d.group) : '', definition: d.definition || m.definition || '', dictId: api.dictId ? api.dictId(d.key) : d.key, last: ys[ys.length - 1] || 0 }; });
    const ix = Ask.build({ datasets, ask: CH.ask || {}, words: (words && words.words_es) || {}, layers: typeof Core !== 'undefined' && Core.layers ? Core.layers.rows() : [], metrics: chMetrics(),
      glossary: [...((gEn && gEn.terms) || []), ...((gEs && gEs.terms) || [])].map(t => [t[0], t[1]]), places: api.places().slice(0, -1), view: chView() });
    if (!ix.munis.length || !ix.docs.length) throw new Error('data');   // never kept empty: the next question builds it again
    return { A: Ask, ix };
  })().catch(() => { CH_MOD = null; return null; });
}
/** The spans of the question that the rules took (not the places, which chPlaces blanked before them): where the datasets of chParse come from. */
function chRuleSpans(n, rest) {
  const r1 = chPlaces(n).rest, out = []; let a = -1;
  for (let i = 0; i <= n.length; i++) { const t = i < n.length && /[a-z0-9]/.test(n[i]) && r1[i] !== ' ' && rest[i] === ' '; if (t && a < 0) a = i; if (!t && a >= 0) { out.push({ a, b: i, rule: true }); a = -1; } }
  for (let i = out.length - 1; i > 0; i--) if (!/\S/.test(n.slice(out[i - 1].b, out[i].a))) { out[i - 1].b = out[i].b; out.splice(i, 1); }   // the words of one phrase ("mental health shortage areas"), with only spaces between them, are one span
  return out;
}
const CH_TOURISM = new Set(['tourism_jobs', 'accommodation_jobs', 'food_service_jobs', 'tourism_places', 'lodging_places', 'gastronomy_places', 'attractions_places', 'visitor_services_places', 'jobs_naics_71', 'jobs_naics_72']);
const chTourismLast = (keys) => [...keys.filter(k => !CH_TOURISM.has(k)), ...keys.filter(k => CH_TOURISM.has(k))];   // the standing rule: tourism goes last in a list
// clear: a command alone, or with the map, the layers or the conversation as its object ("limpia las playas" and "clear water" are topics)
const CH_CLEAR_CMD = /^(?:por favor\s+|please\s+)?(?:clear|reset|limpia\w*|borra\w*|reinicia\w*|start over|empieza de nuevo|empezar de nuevo)(?:\s+(?:el|la|los|las|the|todo|todos|todas|all|everything))*(?:\s+(?:mapa|map|capas|layers|conversacion|chat|pantalla|screen|todo|everything))?\s*[.!]*$/;
const CH_OFF_ALL = /^(?:por favor\s+|please\s+)?(?:quita\w*|quitar|apaga\w*|apagar|remueve|elimina\w*|remove|turn off|switch off|hide|oculta\w*|esconde\w*)\s+(?:todas?\s+|todos\s+|all\s+)?(?:las\s+|los\s+|the\s+)?(?:capas|layers|todo|everything)\b/;
const CH_SENS_KEYS = { vacant: ['vacant_units', 'other_vacant_units'], drugs: ['crime_type1'], addresses: ['housing_units'], aid: ['fema_ia_households'], careNames: ['cms_nursing_homes'], rentals: ['seasonal_units', 'seasonal_pct'], nearMeTx: ['bh_all'], namedHome: ['bh_su'], homebound: ['acs_disability_pct'] };
// a name that is a municipio and something else: "se muda a Florida" is the state, "Río Grande de Loíza" a river
const CH_NOT_PLACE = [
  [/\b(?:mud\w*|se van|se fue|se fueron|irse|emigr\w*|viv\w* en|vive en|move[ds]?|moving|moved|relocat\w*|living in|lives in|went|left for)\s+(?:a|al|para|to|in|en)\s+florida\b|\bflorida\s+(?:usa|ee\.?\s?uu\.?|eeuu|estados unidos|the state)\b|\b(?:orlando|miami|tampa|kissimmee)\b/, ['Florida'], { es: '«Florida» aquí es el estado de EE. UU., no el municipio.', en: '“Florida” here is the US state, not the municipio.' }],
  [/\brio grande de (?:loiza|manati|arecibo|anasco)\b/, ['Río Grande', 'Loíza', 'Manatí', 'Arecibo', 'Añasco'], { es: 'El «Río Grande de …» es un río, no un municipio.', en: 'The “Río Grande de …” is a river, not a municipio.' }],
];
// the dataset of the same thing that has barrio values, when a ranking of barrios is asked for one that has none (the BLS rate is by municipio only; the ACS rate is by barrio too)
const CH_BARRIO_TWIN = { laus_unemp_rate: 'unemployment_rate_pct', laus_unemployed: 'unemployment_rate_pct' };
function chSensKeys(st, A) {   // the counts by area that answer what is never drawn: students for their names, nursing homes for theirs, seasonal units for rentals
  const kind = st.sens.find(k => A.PRIVATE.has(k)), n = st.n;
  if (kind === 'names') return /\b(?:estudiantes|alumnos|students|pupils)\b/.test(n) ? ['sch_enroll'] : /\b(?:maestros|teachers)\b/.test(n) ? ['sch_teachers'] : /\b(?:residentes|personas|vecinos|residents|people|neighbou?rs)\b/.test(n) ? ['population'] : [];
  if (kind === 'healthPerson') return /\b(?:discapacidad\w*|disabilit\w*|disabled)\b/.test(n) ? ['acs_disability_pct'] : [];
  if (kind === 'nearMe') return st.keys.slice(0, 1);   // "hospitals near me": the topic's count by municipio
  if (kind === 'aid' && (st.u.sens.find(x => x.kind === 'aid') || {}).food) return ['poverty_pct'];   // food stamps, welfare: no data by municipio; poverty stands in, labelled (chRefine)
  return CH_SENS_KEYS[kind] || [];
}
/** What ask.js adds to chParse's reading (st): layers, a place and its point, a time, topics the rules left, approximations, what must not be drawn; then the intent again. */
function chRefine(st, { A, ix }) {
  // a barrio first ("pobreza en el barrio Playa de Ponce"): its words are a place, never a topic; the rules and the lexicon read the question without them
  if (CH.barrios && !st.barPre) {
    const u0 = A.understand(st.n, ix, { rest: st.rest, places: st.places, explain: true }), b0 = !u0.sens.length ? chBarrioFind(st, u0, ix) : null;
    if (b0) { const s2 = chParse(st.n.slice(0, b0.a) + ' '.repeat(b0.b - b0.a) + st.n.slice(b0.b)); for (const k of ['n', 'keys', 'rest', 'dropped', 'related', 'relPairs', 'intent', 'years']) st[k] = s2[k]; st.barPre = b0; }
  }
  const api = chApi(), view = chView(), n = st.n, ok = (k) => !!api.meta(k), okLayer = (id) => view === '3d' ? !A.ONLY_2D.has(id) : !A.ONLY_3D.has(id), places0 = st.places.slice(), keys0 = st.keys.slice();
  const u = A.understand(n, ix, { rest: st.rest, places: st.places, explain: true });
  Object.assign(st, { u, view, layersAsked: [], proxy: [], missing: [], standIn: [], groups: [], alts: [], sens: u.sens.map(s => s.kind), relation: null, topics: [], quals: u.quals || [], layers3d: view === '2d' ? (u.layers3d || []) : [] });
  if (chLang(st.q, 'x') === 'x' && u.vote.es !== u.vote.en) st.lang = u.vote.es > u.vote.en ? 'es' : 'en';   // no word that chLang knows ("vivienda", "transit"): the lexicon's language
  if (!st.places.length && u.places.length) { st.places = [u.places[0].muni]; if (u.places[0].typo) st.fixes = [...(st.fixes || []), [u.places[0].name, u.places[0].muni]]; }   // a misspelt municipio is said, as a corrected topic is ("Leí «toa vaja» como «Toa Baja»")
  const pt = u.places.find(p => p.lat != null); if (pt && st.places[0] === pt.muni) st.zoom = { lat: pt.lat, lon: pt.lon, z: 14, name: pt.name, muni: pt.muni };
  for (const [re, names, say] of CH_NOT_PLACE) if (re.test(n) && st.places.some(p => names.includes(p))) { st.places = st.places.filter(p => !names.includes(p)); st.zoom = null; (st.placeNotes = st.placeNotes || []).push(say); }
  const bar = st.barPre || (!st.sens.length ? chBarrioFind(st, u, ix) : null);   // a barrio named on its own ("pobreza en Guayabal"), or with its municipio ("Pueblo, Juana Díaz")
  if (bar) { st.barrio = bar; if (bar.rows.length === 1) { const r = bar.rows[0]; st.places = [r.muni]; st.zoom = { lat: r.lat, lon: r.lng, z: 13, name: r.name, muni: r.muni, barrio: true }; } }
  if (st.sens.includes('crisis')) { st.intent = 'crisis'; st.keys = []; st.ctx = []; return st; }   // suicide, self-harm, overdose deaths: no stand-in, no ranking, the crisis line
  if (st.sens.includes('officials')) { st.officials = true; if (st.places.length) { st.intent = 'muni'; st.keys = []; return st; } st.intent = 'sensitive'; st.keys = []; st.ctx = []; return st; }   // the observatory does not rate officials; a municipio's data as context
  if (st.sens.some(k => A.PRIVATE.has(k))) {   // never a point, an address, a name or a person: the answer says why; a count by area follows when there is one
    st.intent = 'sensitive'; st.keys = chSensKeys(st, A).filter(ok); st.ctx = [];
    if (st.keys[0] === 'poverty_pct' && A.CONCEPT.welfare) st.proxy = [A.CONCEPT.welfare];   // where aid recipients live: poverty as a labelled approximation, no relation drawn
    return st;
  }
  if (CH_OFF_ALL.test(n)) { st.intent = 'clear'; st.keys = []; return st; }   // "quita todas las capas", "turn off all layers"
  if (u.time.since) st.since = u.time.since; if (u.time.until) st.until = u.time.until;
  for (const h of u.layers) if (okLayer(h.id) && !st.layersAsked.includes(h.id)) st.layersAsked.push(h.id);
  if (u.explain && (u.explain.glossary || u.explain.layer) && !st.places.length) { st.intent = 'explain'; st.explain = u.explain; return st; }
  if (u.explain && u.explain.strong && st.keys.length) st.intent = 'sources';
  if (u.fresh && st.keys.length) st.intent = 'sources';
  if (u.countData) st.intent = 'catalog';
  // the datasets the rules found in a span of the question: what is left when that span is blanked, against what the span's words name on their own
  const without = (h) => { const w = n.slice(0, h.a) + ' '.repeat(h.b - h.a) + n.slice(h.b), k2 = chConcepts(chPlaces(w).rest).keys.filter(ok); return st.keys.filter(k => !k2.includes(k)); };
  const alone = (h) => chConcepts(n.slice(h.a, h.b)).keys.filter(ok);
  // a concept of two words or more that reads part of what a rule took ("cuido de niños", "salario mínimo", "health insurance", "viviendas vacías"): when it holds an
  // approximation, a count or nothing to show, or the rule's dataset is not one of its own, the concept reads the question better
  for (const h of u.concepts) {
    const c = A.CONCEPT[h.id];
    if (h.words.length < 2 || !h.partly || h.covered) continue;
    const gone = without(h);
    const stray = gone.filter(k => !c.data.includes(k));   // "hogares sin carro": the rule's households beside the concept's no-vehicle households
    if (!(c.proxy || c.missing || c.sens) && !(gone.length && !gone.some(k => c.data.includes(k))) && !(stray.length && gone.length > stray.length)) continue;
    st.keys = st.keys.filter(k => !(c.proxy || c.missing || c.sens || !gone.some(x => c.data.includes(x)) ? gone : stray).includes(k)); h.partly = false; h.superseding = true;
    st.rest = st.rest.slice(0, h.a) + n.slice(h.a, h.b) + st.rest.slice(h.b);
  }
  const groupAt = (st.dropped || []).map(d => { const t = norm(d.text || ''), i = t ? n.indexOf(t) : -1; return i >= 0 ? { a: i, b: i + t.length } : null; }).filter(Boolean);   // the words of a group the figure is broken down by ("children" in "teenagers and children poverty"): not a dataset of the answer
  const rules = chRuleSpans(n, st.rest).filter(r => !groupAt.some(g => r.a < g.b && g.a < r.b)), topics = [];
  for (const h of u.concepts) {
    const c = A.CONCEPT[h.id], own = c.data.filter(ok);
    if (c.alone && (keys0.length || u.concepts.some(x => x !== h && !A.CONCEPT[x.id].alone) || u.layers.length)) continue;   // "¿cuántas personas tienen internet?" asks about internet, not the population
    if (h.covered && own.length && rules.some(r => r.a === h.a && r.b === h.b)) {   // a rule took exactly the concept's words for a dataset the concept does not hold ("salud" → health-care jobs, "hospitals" → health-care jobs): the topic's own dataset first, the rule's as a chip
      const gone = without(h);
      if (gone.length && JSON.stringify(gone) === JSON.stringify(alone(h)) && !gone.some(k => c.data.includes(k))) { st.keys = st.keys.map(k => gone.includes(k) ? (k === gone[0] ? own[0] : null) : k).filter(Boolean); st.alts.push(...gone); }
    }
    if (h.covered && h.words.length >= 2) { const al = alone(h); if (al.some(k => c.data.includes(k))) { const stray = al.filter(k => !c.data.includes(k)); if (stray.length) { st.keys = st.keys.filter(k => !stray.includes(k)); st.alts.push(...stray); } } }   // "hogares sin carro": the no-vehicle households, not the households the rules read beside them
    if (h.covered) { if (c.missing && st.keys.length) st.standIn.push({ c, words: n.slice(h.a, h.b) }); if (rules.some(r => r.a === h.a && r.b === h.b)) { if (c.proxy) st.proxy.push(c); st.alts.push(...own); } continue; }   // "apagones": a rule's dataset (generating capacity) stands in for what the observatory does not have   // a rule took exactly its words: the concept labels the answer and offers its other datasets
    topics.push({ a: h.a, b: h.b, c, data: c.data.filter(ok), layers: c.layers.filter(okLayer), superseding: !!h.superseding });
  }
  if (u.dataset && ok(u.dataset.key) && !keys0.length) topics.push({ a: u.dataset.a, b: u.dataset.b, data: [u.dataset.key, ...u.dataset.next.filter(ok)], layers: [], ds: true });   // the datasets' own words, only when the rules found nothing
  topics.sort((p, q) => p.a - q.a);
  // beside datasets of the rules, a topic counts when the question lists it with them ("pobreza y escuelas", "guaguas y empleos") or relates them across places ("con más viejos tienen más pobreza"); else it is a word of their phrase ("rent of students")
  let used = topics;
  if (st.keys.length && !u.density) {
    const all = [...rules, ...topics].sort((p, q) => p.a - q.a), linked = new Set(rules);
    const modifier = (i) => i > 0 && (u.relate ? /^\s*(?:(?:de|del|sin|of|without|para|for)\s+)(?:(?:el|la|los|las|un|una|the|a|an)\s+)?$/ : /^\s*(?:(?:de|del|con|sin|of|with|without|para|for)\s+)(?:(?:el|la|los|las|un|una|the|a|an)\s+)?$/).test(n.slice(all[i - 1].b, all[i].a));   // "propietarios con hipoteca": a word of the phrase before it, whatever follows (in a question that relates things, "con" joins the two: "¿se relaciona el ingreso con la educación?")
    for (let again = true; again;) { again = false; for (let i = 0; i < all.length; i++) for (const j of [i - 1, i + 1]) { const x = all[i], y = all[j]; if (!y || linked.has(x) || !linked.has(y) || modifier(i)) continue; if (A.coordinated(n, x, y, u.relate)) { linked.add(x); again = true; } } }
    used = topics.filter(t => t.superseding || linked.has(t));
  }
  // a stand-in comes from the field of the nearest data the lexicon names for the missing topic ("apagones de luz": power plants); a dataset of another field is a word of
  // its phrase when it follows it ("placas solares en las casas": the houses, not the rent; "pobreza en la playa" keeps the poverty), and the answer is "not available" with the nearest data
  const field = (k) => ((api.meta(k) || {}).group || '').split(' · ')[0], akin = (c, ks) => !c.near.length || ks.some(k => c.near.some(x => field(x) === field(k)));
  for (const t of used) if (t.c && t.c.missing && !t.data.length) { const host = used.find(x => x !== t && x.data.length && !A.coordinated(n, t, x, u.relate)); if (host && host.a > t.a && !akin(t.c, host.data.slice(0, 1))) { host.data = []; host.layers = []; } }
  for (const t of topics) if (!used.includes(t) && t.c && t.c.missing && st.keys.length && rules.length && rules.every(r => r.a > t.a) && !akin(t.c, st.keys)) { st.keys = []; used = [...used, t]; }
  for (const t of topics) if (!used.includes(t) && t.c) {
    if (t.c.missing) st.standIn.push({ c: t.c, words: n.slice(t.a, t.b) });   // "apagones de luz": the rules' dataset stands in for what the observatory does not have
    else if (t.c.group && st.keys.length && !t.c.data.includes(st.keys[0])) st.groups.push(t.c);   // "desempleo juvenil": the figure is for all ages
    else if (t.c.proxy && t.data.length && st.keys.length && !st.keys.some(k => t.data.includes(k))) {   // "hogares que reciben el PAN": a topic only approached, which qualifies the rules' dataset
      if (st.keys.every(k => CH_COUNTS_OF.has(k))) { st.keys = t.data.slice(0, 1); st.proxy.push(t.c); } else st.standIn.push({ c: t.c, words: n.slice(t.a, t.b) });   // a bare count of homes or people: the topic's own stand-in, labelled; else the rules' dataset, labelled
    }
  }
  const dataTopics = used.filter(t => t.data.length), add = [], layers = [];
  const otherData = (t) => st.keys.length > 0 || dataTopics.some(x => x !== t);
  for (const t of used) {
    if (t.c && t.c.proxy && !st.proxy.includes(t.c)) st.proxy.push(t.c);
    if (t.c && t.c.missing && !t.data.length) {   // a topic the observatory lacks: said, or, beside a topic that is a word of its phrase ("apagones de luz", "hoyos en las carreteras"), that topic's dataset stands in for it
      const host = used.find(x => x !== t && x.data.length && !A.coordinated(n, t, x, u.relate));
      if (host) st.standIn.push({ c: t.c, words: n.slice(t.a, t.b) }); else st.missing.push(t.c);
      continue;
    }
    if (t.layers.length && t.data.length && otherData(t) && !(t.c && t.c.proxy)) { layers.push(...t.layers); t.rel = t.data[0]; continue; }   // "transporte y vivienda": the routes and stops, beside the housing data
    if (t.data.length) add.push({ key: t.data[0], a: t.a, t });
    if (t.layers.length && !(t.data.length && otherData(t))) layers.push(...t.layers);   // a topic on its own: its layers and its data ("inundaciones": the flood zones and the residents in them)
  }
  st.topics = used;
  const rulePos = rules.length ? rules[0].a : Infinity;
  const merged = [...new Set([...add.filter(x => x.a < rulePos).map(x => x.key), ...st.keys, ...add.filter(x => x.a >= rulePos).map(x => x.key)])].slice(0, 4);
  const relT = used.find(t => t.rel), lead = merged.find(k => !relT || k !== relT.rel);
  if (relT && lead) st.relation = [lead, relT.rel];
  st.ctx = [...new Set([...(st.ctx || []), ...st.layersAsked, ...layers])].filter(okLayer);
  const leadT = used.find(t => t.data.length && merged.includes(t.data[0]));
  st.alts = chTourismLast([...new Set([...(leadT ? leadT.data.slice(1) : []), ...st.alts])].filter(k => !merged.includes(k) && ok(k))).slice(0, 3);
  const changed = JSON.stringify(merged) !== JSON.stringify(keys0) || JSON.stringify(st.places) !== JSON.stringify(places0);
  st.keys = merged;
  if (changed && ['unknown', 'muni', 'show', 'value', 'rank', 'trend', 'areas'].includes(st.intent)) {
    st.intent = chIntent(n, st);
    if (st.intent === 'sources' && !/\b(?:datos?|data|fuentes?|sources?|defin\w*|mide|measured?|calcul\w*|licen\w*)\b/.test(n)) st.intent = /\b(?:mas|menos|most|least|more|fewer)\b/.test(n) ? 'rank' : 'show';   // "¿de dónde se va más gente?" asks where, not where the data come from
  }
  if (st.keys.length >= 2 && ['show', 'rank'].includes(st.intent) && u.relate && chComparable(st)) st.intent = 'compare';   // "correlación entre crimen y pobreza", "los pueblos con más viejos tienen más pobreza"
  if (st.keys.length && st.intent === 'show' && /\b(?:peor|peores|mejor|mejores|ranking|clasificacion|ordena\w*)\b/.test(n)) st.intent = 'rank';   // "los peores municipios en desempleo"
  if (st.keys.length === 1 && st.years.length >= 2 && ['show', 'value'].includes(st.intent)) st.intent = 'trend';
  st.byBarrio = /\b(?:por|by|each|cada|todos los)\s+barrios?\b|\bbarrio por barrio\b|\b(?:los\s+)?barrios\s+(?:de|of|in|en)\b/.test(n);   // "pobreza por barrio", "los barrios de Ponce": the map by barrio, and a place's barrios ranked
  if (st.byBarrio && st.keys.length === 1 && st.places.length === 1 && ['show', 'value'].includes(st.intent)) st.intent = 'rank';   // "desempleo entre 2015 y 2020": the change between the two
  if (st.places.length === 1 && used.some(t => t.c && t.c.profile) && ['value', 'show', 'unknown'].includes(st.intent)) { st.keys = []; st.intent = 'muni'; }   // "calidad de vida en Caguas": the municipio's profile
  if (st.keys.length && (u.trend || (st.since && ['show', 'value'].includes(st.intent))) && !['compare', 'areas', 'compose', 'sources', 'catalog', 'missing', 'insights', 'clear', 'help', 'size'].includes(st.intent)) st.intent = 'trend';
  // a command word that is also a word of a topic: "agua limpia" is clean water, not "clear"; "ayuda federal" is aid, not "help"; "falta de vivienda", "tamaño de los hogares", "fuentes de agua"
  const topical = st.keys.length || st.ctx.length || used.length;
  const keep = { help: !topical, clear: CH_CLEAR_CMD.test(n), missing: !topical || /\b(?:datos?|data|datasets?|lista|list|wish ?list)\b/.test(n), size: !topical || /\b(?:datos|data|database|base de datos|observatorio|observatory)\b/.test(n),
    sources: !/\bfuentes? de (?:agua|energia|empleo|trabajo|ingresos?|contaminacion|luz)\b|\b(?:water|energy|job|income|pollution|power) sources?\b|\bsources? of (?:water|energy|income|jobs|pollution|power)\b/.test(n) };
  if (st.intent in keep && !keep[st.intent]) { const n2 = n.replace(/\b(?:clear|reset|start over|limpia\w*|borra\w*|reinicia\w*|missing|falta\w*|tamano|help|ayuda|sources?|fuentes?)\b/g, (x) => ' '.repeat(x.length)); st.intent = st.keys.length ? chIntent(n2, st) : 'layers'; if (st.intent in keep) st.intent = st.keys.length ? 'show' : 'layers'; }
  if (!st.keys.length && st.ctx.length && ['unknown', 'muni', 'show'].includes(st.intent)) st.intent = 'layers';   // a layer named alone, by ask.js or by the rules' context words: the layer, not a wish for missing data
  if (!st.keys.length && view === '3d' && u.metric && ['unknown', 'show'].includes(st.intent)) { st.intent = 'metric3d'; st.metric = u.metric; }
  if (!st.keys.length && !st.ctx.length && st.missing.length && ['unknown', 'muni', 'layers'].includes(st.intent)) st.intent = 'nodata';
  if (!st.keys.length && !st.ctx.length && st.layers3d.length && ['unknown', 'muni', 'show', 'layers'].includes(st.intent)) st.intent = 'layers';   // "elevación en Utuado" on the map page: the 3D view has it
  if (st.intent === 'layers' && !st.ctx.length && !st.layers3d.length) st.intent = st.places.length ? 'muni' : 'unknown';
  if (A.CRIME_SITE.test(n) && (st.keys.some(k => /^crime_/.test(k)) || /\b(?:residencial\w*|caserios?|public housing|housing projects?)\b/.test(n))) {   // "residenciales con más crimen": crime by municipio, said so; the public housing layer stays on
    st.crimeSite = true; const ck = st.keys.find(k => /^crime_/.test(k)) || 'crime_type1'; st.keys = [ck, ...st.keys.filter(k => k !== ck && /^crime_/.test(k))].filter(ok).slice(0, 2);
    if (!['rank', 'value', 'show', 'trend'].includes(st.intent)) st.intent = st.places.length ? 'value' : 'rank';
    if (st.barrio) st.barrio = null;
  }
  if (st.barrio && (st.barrio.rows.length > 1 || ['show', 'value', 'unknown', 'muni', 'layers'].includes(st.intent) || (st.intent === 'catalog' && !st.keys.length)) && !['compare', 'areas', 'trend'].includes(st.intent)) st.intent = 'barrio';
  return st;
}
// ── Barrios named on their own (round 4): the crosswalk's 901 barrios, read when a question has words after "en", "in", "barrio" that are no municipio ──
const CH_COUNTS_OF = new Set(['households', 'housing_units', 'population', 'acs_population', 'families']);   // what a qualifier counts ("hogares que reciben el PAN"), not a topic of the question
const CH_BAR_AT = /^(?:en|in|barrio|bo|at)$/;
function chBarrioCand(st, ix) {   // a word after "en", "in" or "barrio" (an article between them aside) that is no municipio's and no word of the lexicon, or a short question of no such word: the crosswalk (161 KB) is worth reading
  if (CH.barrios) return false;
  const ws = st.n.split(/[^a-z0-9ñ]+/).filter(Boolean), mw = new Set(ix.munis.flatMap(m => m.n.split(' '))), art = /^(?:el|la|los|las|the)$/;
  const plain = (w) => w.length > 2 && !mw.has(w) && !ix.vocab.has(w) && !art.test(w) && !/^\d+$/.test(w);
  const after = (i) => i > 0 && (CH_BAR_AT.test(ws[i - 1]) || (i > 1 && art.test(ws[i - 1]) && CH_BAR_AT.test(ws[i - 2])));
  return /\bbarrio\b/.test(st.n) || (ws.length <= 4 && !st.keys.length && !st.places.length && ws.some(plain) && ws.every(w => !ix.vocab.has(w))) || ws.some((w, i) => after(i) && plain(w));
}
async function chLoadBarrios() {   // name → the barrios of that name: { id, name, muni, lat, lng } (data/geo/crosswalk.json, as economy.js reads it for the barrio values)
  if (CH.barrios) return CH.barrios;
  const cw = await Data.json('data/geo/crosswalk.json').catch(() => null); if (!cw || !cw.units) return null;
  const F = Object.fromEntries(cw.fields.map((f, i) => [f, i])), munis = new Map((cw.units.municipio || []).map(r => [r[F.id], r[F.name_es]])), by = new Map();
  for (const r of cw.units.barrio || []) { const k = r[F.norm] || norm(r[F.name_es]); if (!by.has(k)) by.set(k, []); by.get(k).push({ id: String(r[F.id]), name: r[F.name_es], muni: munis.get(r[F.parent]) || '', lat: r[F.lat], lng: r[F.lng] }); }
  return CH.barrios = by;
}
/** The barrio a question names: after "en", "in" or "barrio", one to four words that are exactly one barrio name (accents aside), not a municipio's name, not a word of a
    topic the question already reads, and, alone, not an everyday word of the lexicon or the observatory's texts unless "barrio" comes before it. With a municipio named, only
    that municipio's barrios count. { name, rows, a, b } or null. */
function chBarrioFind(st, u, ix) {
  const by = CH.barrios; if (!by) return null;
  const n = st.n, ws = [...n.matchAll(/[a-z0-9ñ]+/g)], spans = (u.hits || []).filter(h => h.kind !== 'place');
  if (u.places.some(p => p.alias)) return null;   // a well-known place (Santurce, El Yunque) is read as itself
  const pid = st.places.length === 1 ? chApi().placeId(st.places[0]) : null;
  const whole = ws.length && ws.length <= 4 && !st.keys.length && !st.places.length;   // the question is a barrio's name ("Guayabal")
  for (let i = whole ? 0 : 1; i < ws.length; i++) {
    let at = i - 1; const art = at >= 0 && /^(?:el|la|los|las|the)$/.test(ws[at][0]); if (art) at--;
    if (!(whole && i === 0) && (at < 0 || !CH_BAR_AT.test(ws[at][0]))) continue;
    const named = at >= 0 && (ws[at][0] === 'barrio' || ws[at][0] === 'bo');
    for (let len = Math.min(4, ws.length - i); len >= 1; len--) {
      const part = ws.slice(i, i + len), name = part.map(m => m[0]).join(' '), a = part[0].index, b = part[len - 1].index + part[len - 1][0].length;
      let rows = by.get(name); if (!rows || (whole && i === 0 && len !== ws.length)) continue;
      if (ix.munis.some(m => m.n === name)) continue;   // "Rincón" is the municipio
      if (!named && len === 1 && (ix.vocab.has(name) || (ix.real && ix.real.has(name)) || name.length < 4)) continue;   // "en el pueblo", "en la playa": words, not barrios
      if (!named && spans.some(h => h.a < b && a < h.b)) continue;   // after "barrio" the name is the barrio's even when it is also a topic's word ("barrio Playa", "barrio Montaña")
      if (pid) { rows = rows.filter(r => r.id.startsWith(pid)); if (!rows.length) continue; }
      return { name: rows[0].name, rows, a, b };
    }
  }
  return null;
}
const chLayerRow = (id) => (typeof Core !== 'undefined' && Core.layers ? Core.layers.rows().find(r => r.id === id) : null);
const CH_LAYER_EXTRA = {   // layers outside the registry's menu: the 3D view's Time tab and clock, the 2D map's Transit tab
  lyStorms: { en: 'Storm tracks within 250 km', es: 'Trayectorias de tormentas a 250 km o menos', src: 'NOAA HURDAT2' },
  lySupRoutes: { en: 'Routes by trips in the hour', es: 'Rutas por viajes en la hora', src: { en: 'GTFS timetables', es: 'Horarios GTFS' } }, lySupStops: { en: 'Stops by departures in the hour', es: 'Paradas por salidas en la hora', src: { en: 'GTFS timetables', es: 'Horarios GTFS' } },
  lyGaps: { en: 'Residents far from service', es: 'Residentes lejos del servicio', src: { en: 'Census 2020 blocks, GTFS timetables', es: 'Bloques del Censo 2020, horarios GTFS' } }, lyXfer: { en: 'Integration points', es: 'Puntos de integración', src: { en: 'GTFS timetables', es: 'Horarios GTFS' } },
  lyNow: { en: 'Vehicles on their timetable now', es: 'Vehículos según su horario ahora', src: { en: 'GTFS timetables', es: 'Horarios GTFS' } },
};
function chLayerName(id, lang) { const r = chLayerRow(id) || CH_LAYER_EXTRA[id]; return r ? (lang === 'es' ? r.es : r.en) : id; }
function chLayerSrc(id, lang) { const r = chLayerRow(id) || CH_LAYER_EXTRA[id], s = r && r.src; return !s ? '' : typeof s === 'string' ? s : (lang === 'es' ? s.es : s.en); }
/** One to three sentences on a dataset: the geography, the period of the value shown, the source, and whether it is a survey estimate or an approximation. */
function chAbout(k, lang, proxy, moeSaid, level, period) {
  const api = chApi(), m = api.meta(k); if (!m) return '';
  const es = lang === 'es', src = [...new Set((m.sources || []).map(id => (api.sources()[id] || {}).name).filter(Boolean))].slice(0, 2).join('; ');
  const r = chVec(k), y = r && r.year, win = m.time && m.time.type === 'window' && y ? `${y - (m.time.windowYears || 5) + 1}–${y}` : null, snap = m.snapshot || (m.time && m.time.type === 'snapshot');
  const W = (y1) => m.time && m.time.type === 'window' ? `${y1 - (m.time.windowYears || 5) + 1}–${y1}` : String(y1), wins = m.time && m.time.type === 'window';
  const when = period && period[0] !== period[1] && !snap ? (es ? `${wins ? 'ventanas de cinco años ' : ''}de ${W(period[0])} a ${W(period[1])}` : `${wins ? 'five-year windows ' : ''}${W(period[0])} to ${W(period[1])}`) : snap ? (es ? `corte de ${m.time && m.time.asOf ? chDate(m.time.asOf) : y}` : `snapshot of ${m.time && m.time.asOf ? m.time.asOf : y}`) : win ? (es ? `ventana de cinco años ${win}` : `five-year window ${win}`) : y ? String(y) : '';
  const est = m.moe && moeSaid ? '' : m.moe ? (es ? 'Es un estimado de encuesta con margen de error.' : 'It is a survey estimate with a margin of error.') : /\bestimate\b/i.test(m.label) ? (es ? 'Es un estimado del observatorio.' : 'It is an estimate made by the observatory.') : '';
  return `${es ? 'Sobre' : 'About'} «${chLabel(k)}»: ${level === 'barrio' ? (es ? 'por barrio' : 'by barrio') : (es ? 'por municipio' : 'by municipio')}${when ? ', ' + when : ''}${src ? `; ${es ? 'fuente' : 'source'}: ${src}` : ''}.${est ? ' ' + est : ''}${proxy ? ' ' + (es ? 'Es una aproximación, no la medida exacta.' : 'It is an approximation, not the exact measure.') : ''}`;
}
/** What every answer gets from the understanding: the typos read, the layers switched on, the relation of two topics, approximations and missing data (added to
    the wishlist), what is never drawn, the values of a place named beside the datasets, what the dataset is, the follow-up chips and buttons. */
function chDecorate(out, st) {
  if (!st.u || typeof out.html !== 'string') return out;
  const api = chApi(), es = st.lang === 'es', A = typeof Ask !== 'undefined' ? Ask : null, notes = [], shown = (st.shown || []).length > 0 || (['show', 'value', 'rank', 'trend', 'compare', 'areas', 'catalog', 'sources'].includes(st.intent) && st.keys.length > 0);   // st.shown: what the handler put on the map (chAnswer)
  (st.placeNotes || []).forEach(x => notes.push(esc(x[es ? 'es' : 'en'])));
  if (st.officials && st.intent === 'muni' && A) out.html = chP(esc(A.SENS_TEXT.officials[es ? 'es' : 'en'])) + out.html;
  if (st.zoom && st.zoom.name && st.intent !== 'layers' && !(st.barrio && (st.level === 'barrio' || !st.keys.length))) notes.push(esc(chMapless() ? (es ? `${st.zoom.name.replace(/\b\w/g, c => c.toUpperCase())} está en ${st.zoom.muni}; los datos son del municipio.` : `${st.zoom.name.replace(/\b\w/g, c => c.toUpperCase())} is in ${st.zoom.muni}; the data are the municipio's.`) : es ? `El mapa va a ${st.zoom.name.replace(/\b\w/g, c => c.toUpperCase())} (${st.zoom.muni}); los datos son del municipio.` : `The map goes to ${st.zoom.name.replace(/\b\w/g, c => c.toUpperCase())} (${st.zoom.muni}); the data are the municipio's.`));   // a place inside a municipio: the figures are the municipio's
  if (st.fixes && st.fixes.length) notes.push(es ? `Leí ${st.fixes.map(([a, b]) => `«${esc(a)}» como «${esc(b)}»`).join(', ')}.` : `I read ${st.fixes.map(([a, b]) => `“${esc(a)}” as “${esc(b)}”`).join(', ')}.`);
  const lys = st.intent === 'layers' || st.intent === 'explain' ? [] : (st.ctx || []);
  if (lys.length && shown) notes.push(`${chMapless() ? (es ? 'Capas del mapa para esta respuesta' : 'Map layers for this answer') : es ? 'Capas encendidas' : 'Layers on'}: ${lys.map(id => `${esc(chLayerName(id, st.lang))}${chLayerSrc(id, st.lang) ? ` <small>(${esc(chLayerSrc(id, st.lang))})</small>` : ''}`).join(', ')}.${lys.some(id => A && A.SCHEDULE.has(id)) ? ' ' + (es ? 'El transporte se muestra según sus horarios programados (GTFS), no con posiciones en vivo.' : 'Transit is shown from its scheduled timetables (GTFS), not live positions.') : ''}`);
  let rel = null;
  if (st.relation && st.intent !== 'compare') {
    const [a, b] = st.relation, c = Tools.correlate({ a, b });
    if (!c.error) { const t = chTx(st.lang), dir = Math.abs(c.r) < .3 ? t.nolink : (c.r > 0 ? t.together : t.apart); notes.push(esc(t.corr(c.r, c.n, chLabel(a), chLabel(b), dir)) + ' ' + esc(es ? 'Es un patrón, no una causa.' : 'A pattern, not a cause.')); rel = [a, b]; }
  }
  const prox = [...new Set(st.proxy || [])], miss = [...new Set(st.missing || [])];
  prox.forEach(c => notes.push(`<b>${es ? 'Aproximación' : 'Approximation'}:</b> ${esc(c.proxy[es ? 'es' : 'en'])}.`));
  if (st.intent !== 'nodata') miss.forEach(c => notes.push(esc(c.missing[es ? 'es' : 'en'].replace(/^./, x => x.toUpperCase())) + '.'));
  if (prox.length || miss.length) { chAddWish(st.q); if (st.intent !== 'nodata') notes.push(esc(chTx(st.lang).noted)); }
  (st.sens || []).filter(k => A && A.SENS_TEXT[k] && st.intent !== 'sensitive' && st.intent !== 'crisis' && k !== 'crisis' && k !== 'officials').forEach(k => notes.push(esc(A.SENS_TEXT[k][es ? 'es' : 'en'])));
  if (st.intent === 'show' && st.places.length && st.keys.length) {   // a place named beside the datasets: its values first ("pobreza y escuelas en Ponce")
    const i = api.placeIndex(st.places[0]), vals = st.keys.slice(0, 3).map(k => { const r = chVec(k); return r && i >= 0 ? `${esc(chLabel(k))} ${esc(chCell(k, r.values[i], i, 'value'))}` : null; }).filter(Boolean);
    if (vals.length) out.html = chP(`${B(st.places[0])}: ${vals.join(' · ')}.`) + out.html;
  }
  if (/correlaci[oó]n r =|correlation r =/.test(out.html) && !/patrón|pattern|no prueba|not proof/.test(out.html)) notes.push(esc(es ? 'Es un patrón entre municipios, no una causa.' : 'A pattern across municipios, not a cause.'));
  // a dataset shown in place of what was asked: the rules' dataset for a topic the observatory lacks, a figure for all ages, a qualifier the dataset lacks
  const k1 = [...st.keys, ...(st.shown || [])].find(k => api.meta(k) && (!(st.shown || []).length || st.shown.includes(k))), lead = shown && k1 && api.meta(k1), leadName = lead ? chLabel(k1) : '', q = (s) => es ? `«${s}»` : `“${s}”`, AP = `<b>${es ? 'Aproximación' : 'Approximation'}:</b>`, NOT = es ? 'que el observatorio no tiene' : 'which the observatory does not have';
  const lacking = lead && A ? A.QUALS.filter(x => (st.quals || []).includes(x.id) && !(x.ok && x.ok(lead))) : [];
  let approx = 0;
  if (lead) {
    (st.standIn || []).forEach(x => { notes.push(`${AP} ${esc(q(leadName))} ${es ? 'en lugar de' : 'instead of'} ${esc(q(x.words))}, ${NOT}.`); approx++; });
    (st.groups || []).forEach(c => { notes.push(`${AP} ${esc(q(leadName))}, ${es ? `de todas las edades, en lugar de la cifra de ${esc(c.group.es)}` : `for all ages, instead of the figure for ${esc(c.group.en)}`}, ${NOT}.`); approx++; });
    lacking.forEach(x => { notes.push(`${AP} ${esc(q(leadName))} ${es ? 'en lugar de' : 'instead of'} ${esc(x.what[es ? 'es' : 'en'])}, ${NOT}.`); approx++; });
    if (st.crimeSite && A) { notes.push(`${AP} ${esc(A.SENS_TEXT.crimeSite[es ? 'es' : 'en'])}`); approx++; }
    if (approx && !prox.length && !miss.length) { chAddWish(st.q); notes.push(esc(chTx(st.lang).noted)); }
  }
  if (shown && k1 && st.intent !== 'sources') notes.push(esc(chAbout(k1, st.lang, prox.length + approx > 0, out.html.includes(chMoeNote(st.lang)), st.level, st.intent === 'trend' ? st.period : null)));
  const seen = new Set();   // a sentence once: not one the answer already says, not twice among the notes
  const fresh = notes.filter(x => { const t = x.replace(/<[^>]+>/g, ''); if (seen.has(t) || out.html.includes(x)) return false; seen.add(t); return true; });
  if (fresh.length) out.html += fresh.map(x => `<p class="ch-note">${x}</p>`).join('');
  out.actions = out.actions || [];
  if (st.intent !== 'nodata' && !chMapless()) [...new Set(miss.flatMap(c => c.related || []))].forEach(id => out.actions.push({ label: chLayerName(id, st.lang), run: () => chLayersOn([id]) }));   // the nearest layers to what is missing, as buttons
  if (rel) out.actions.unshift({ label: es ? 'Ver la relación (dispersión)' : 'See the relation (scatter)', run: () => api.show({ layers: rel.map(k => ({ key: k, mode: 'fill', norm: chNormFor(k) })), context: st.ctx, bench: 'scatter' }), primary: true });
  const noMap = (st.sens || []).some(x => ['crisis', 'nearMe', 'nearMeTx'].includes(x.kind || x));   // a crisis or "near me": the reply and its lines, never a map
  if (shown && !noMap && st.view !== '3d' && !out.actions.some(x => /3D/.test(x.label))) out.actions.push({ href: '3d.html' + chSearch() + '#ask=' + encodeURIComponent(String(st.q).slice(0, 400)), label: A ? A.ON3D[es ? 'es' : 'en'] : '3D' });   // the same question on the 3D view (ask3d.js reads #ask=)
  const k0 = st.keys[0];
  if (shown && k0 && api.dictId && !out.actions.some(x => x.href && /dictionary/.test(x.href))) out.actions.push({ href: 'dictionary.html#' + api.dictId(k0), label: es ? 'Ver en el diccionario' : 'See in the dictionary' });
  const alts = (st.alts || []).filter(k => !st.keys.includes(k)).slice(0, 2).map(k => T(api.meta(k).label));   // the other readings of a broad question, as chips the parser resolves by the dataset's own name
  out.follow = [...alts, ...(out.follow || [])].slice(0, 4);
  out.plan = { intent: st.intent, keys: st.keys.slice(), layers: (st.ctx || []).slice(), place: st.places[0] || null, zoom: st.zoom || null, proxy: [...prox.map(c => c.id), ...(lead ? [...(st.standIn || []).map(x => x.c.id), ...(st.groups || []).map(c => c.id), ...lacking.map(x => x.id)] : [])], missing: miss.map(c => c.id), relation: rel, sens: st.sens, fixes: st.fixes || [] };
  return out;
}
/** A question, answered: chParse (on the question with its typos corrected), ask.js's reading, the handler, and what the understanding adds. No page here. */
async function chAnswer(q) {
  const M = await chAskModule();
  let st = chParse(q), fixes = [];
  if (M) {   // typos: read every unknown word when nothing in the question was understood ("pobresa en mayaguez"), else only the words in a list of topics ("pobreza y desempelo")
    const u0 = M.A.understand(st.n, M.ix, { rest: st.rest, places: st.places }), found = st.keys.length || u0.concepts.length || u0.layers.length;
    const fx = M.A.fix(q, M.ix, { listed: !!found });
    if (fx.fixes.length) { st = chParse(fx.text); fixes = fx.fixes; }
  }
  st.q = q; st.fixes = fixes; CH.lastLang = st.lang;
  if (M) { if (chBarrioCand(st, M.ix)) await chLoadBarrios(); chRefine(st, M); CH.lastLang = st.lang; }
  // every dataset the handler shows is recorded (st.shown): chDecorate labels a stand-in from what is on the map, whatever handler showed it
  const fn = Handlers[st.intent] || Handlers.unknown, api0 = chApi(), show0 = api0 && api0.show; st.shown = [];
  if (show0) api0.show = function (spec) { (spec && spec.layers || []).forEach(l => { if (l && l.key && !st.shown.includes(l.key)) st.shown.push(l.key); }); return show0.apply(this, arguments); };
  let out;
  try { out = await fn(st); } finally { if (show0) api0.show = show0; }
  if (M && !st.shown.length && ['nodata', 'crisis', 'sensitive'].includes(st.intent) && api0 && api0.clear) { api0.clear({ keepPlace: true }); if (chView() === '3d' && st.places[0]) api0.show({ clear: false, layers: [], select: st.places[0] }); }   // the 3D view's clear also drops the place   // an answer that shows nothing leaves no earlier answer's datasets on the map, which would read as its answer
  if (st.dropped.length && st.keys.length && typeof out.html === 'string') out.html += chDroppedNote(st.dropped, st.lang);
  if (M) {
    const api = chApi();
    if ((st.ctx || []).length && !['layers', 'explain', 'sensitive'].includes(st.intent)) chLayersOn(st.ctx);   // every layer the answer names, in either view (the 2D tab and the 3D columns switch on only their own list)
    if (st.zoom && st.zoom.lat != null && st.intent !== 'layers') chGoTo(st.zoom);
    chDecorate(out, st);
  }
  if (chMapless()) chHandOver(out, st);
  return { st, out };
}
/** On a page without a map (askpage.js), an answer that needs the map gets "Show on the map": index.html (3d.html for the 3D view's own layers) with the question in
    #ask=, which chatboot.js (ask3d.js on the 3D view) asks there once the map is ready and then takes out of the address. Links to this page's own entries stay on it. */
function chHandOver(out, st) {
  const api = chApi(), es = st.lang === 'es', ctx = st.ctx || [], l3 = st.layers3d || [], shown = (st.shown || []).length > 0;
  out.actions = out.actions || [];
  if (api.page && api.page.name === 'dictionary') out.actions.forEach(a => { if (a.href && /^dictionary\.html#/.test(a.href)) { a.href = a.href.slice(15); a.self = true; } });   // this page's own entries, opened here
  if (st.intent === 'crisis' || st.intent === 'clear' || typeof out.html !== 'string') return;
  if ((st.sens || []).some(x => ['crisis', 'nearMe', 'nearMeTx'].includes(x.kind || x))) { out.actions = out.actions.filter(a => !(a.href && /^(?:index|3d)\.html[?#]/.test(a.href))); return; }   // a crisis, or "near me": the reply and its lines, never a map
  const needs = shown || ctx.length || l3.length || st.zoom || st.barrio || st.intent === 'layers' || (st.explain && st.explain.layer) || (st.missing || []).some(c => (c.related || []).length);
  if (!needs) return;
  const in3d = l3.length > 0 && !ctx.length && !shown, link = api.page && api.page.viaLink && api.page.mapLink ? api.page.mapLink() : null;   // a question that said "this" on the page: the map with the answer's datasets
  const href = link || (in3d ? '3d.html' : 'index.html') + location.search + '#ask=' + encodeURIComponent(String(st.q).slice(0, 400));
  if (in3d || link) out.actions = out.actions.filter(a => !(a.href && /^3d\.html#ask=/.test(a.href)));
  out.actions.unshift({ href, label: es ? 'Ver en el mapa' : 'Show on the map', primary: true, map: true });
}
Object.assign(Handlers, {
  async layers(st) {   // "muestra las rutas", "zonas inundables en Toa Baja", "edificios en 3D": the layers on, the place in view, where each layer comes from
    const api = chApi(), es = st.lang === 'es', A = typeof Ask !== 'undefined' ? Ask : null, ids = [...new Set(st.ctx || [])];
    if (chMapless()) {   // no map here: the layers asked for, their sources, and the button that opens the map with the question (chHandOver)
      const all = [...new Set([...ids, ...(st.layers3d || [])])].filter(id => chLayerName(id, st.lang));
      let h = all.length ? chP(`${B(es ? 'Capas del mapa' : 'Map layers')}:`) + `<ul class="ch-ul">${all.map(id => `<li>${esc(chLayerName(id, st.lang))}${chLayerSrc(id, st.lang) ? ` <small>· ${esc(chLayerSrc(id, st.lang))}</small>` : ''}${(st.layers3d || []).includes(id) ? ` <small>· ${es ? 'vista 3D' : '3D view'}</small>` : ''}</li>`).join('')}</ul>` : '';
      h += chP(esc(es ? 'Esta página no tiene mapa: «Ver en el mapa» abre el mapa con su pregunta y enciende las capas allí.' : 'This page has no map: “Show on the map” opens the map with your question and turns the layers on there.'));
      if (all.some(id => A && A.SCHEDULE.has(id))) h += `<p class="ch-note">${esc(es ? 'El transporte se muestra según sus horarios programados (GTFS), no con posiciones en vivo: no hay datos públicos en tiempo real.' : 'Transit is shown from its scheduled timetables (GTFS), not live positions: there are no public real-time data.')}</p>`;
      CH.ctx = { keys: [], year: null, muni: st.places[0] || null };
      return { html: h, actions: [], follow: [...new Set(all.flatMap(id => (A && A.LAYER_DATA[id]) || []))].filter(k => api.meta(k)).slice(0, 3).map(k => T(api.meta(k).label)) };
    }
    const done = chLayersOn(ids), scene = done.filter(id => A && A.SETTINGS_3D.has(id));
    const place = st.zoom || st.places[0]; if (place) chGoTo(place);
    CH.ctx = { keys: [], year: null, muni: st.places[0] || null };
    const where = place ? (typeof place === 'string' ? place : `${place.name.replace(/\b\w/g, c => c.toUpperCase())} (${place.muni})`) : '';
    const in3d = (st.layers3d || []).map(id => chLayerName(id, st.lang) || id);
    if (!done.length && in3d.length) {
      let h = chP(esc(es ? `${in3d.join(', ')}: ${in3d.length > 1 ? 'están' : 'está'} en la vista 3D, no en este mapa.` : `${in3d.join(', ')}: in the 3D view, not on this map.`));
      if (where) h += chP(esc(es ? `Acerqué el mapa a ${where}.` : `I moved the map to ${where}.`));
      return { html: h, actions: [{ href: '3d.html' + chSearch() + '#ask=' + encodeURIComponent(String(st.q).slice(0, 400)), label: A ? A.ON3D[es ? 'es' : 'en'] : '3D', primary: true }], follow: [] };
    }
    let html = done.length ? chP(`${B(es ? 'Capas encendidas' : 'Layers on')}:`) + `<ul class="ch-ul">${done.map(id => `<li>${esc(chLayerName(id, st.lang))}${chLayerSrc(id, st.lang) ? ` <small>· ${esc(chLayerSrc(id, st.lang))}</small>` : ''}</li>`).join('')}</ul>` : chP(esc(es ? 'Esa capa no está en esta vista.' : 'That layer is not in this view.'));
    if (where) html += chP(esc(es ? `Acerqué el mapa a ${where}.` : `I moved the map to ${where}.`));
    if (scene.length) html += `<p class="ch-note">${esc(es ? 'El terreno y los edificios en 3D se ven al acercar el mapa; los edificios, desde el nivel de la calle.' : 'Terrain and 3D buildings show as you zoom in; buildings from street level.')}</p>`;
    if (done.some(id => A && A.SCHEDULE.has(id))) html += `<p class="ch-note">${esc(es ? 'El transporte se muestra según sus horarios programados (GTFS), no con posiciones en vivo: no hay datos públicos en tiempo real.' : 'Transit is shown from its scheduled timetables (GTFS), not live positions: there are no public real-time data.')}</p>`;
    const rel = [...new Set(done.flatMap(id => (A && A.LAYER_DATA[id]) || []))].filter(k => api.meta(k)).slice(0, 3);
    return { html, actions: [], follow: rel.map(k => T(api.meta(k).label)) };
  },
  async explain(st) {   // "¿qué es el margen de error?", "what is the source of the transit routes?": the glossary's definition and its source, or a layer's source
    const es = st.lang === 'es', e = st.explain, api = chApi();
    if (e.glossary) {
      const d = await Data.json(`data/glossary_defs_${es ? 'es' : 'en'}.json`).catch(() => null), g = d && d.terms && d.terms[e.glossary];
      if (g) {
        const [name, exp, plain, srcName, srcUrl] = g, k = st.keys[0];
        if (k) { await api.show({ layers: chPlan([k]), context: st.ctx }); CH.ctx = { keys: [k], year: null, muni: null }; }   // a term that is also a dataset ("índice de Gini", "HPSA"): the definition, and the dataset on the map
        return { html: chP(`${B(name)}${exp ? ` (${esc(exp)})` : ''}: ${esc(plain)}`) + `<p class="ch-note">${es ? 'Fuente' : 'Source'}: ${srcUrl ? `<a href="${esc(srcUrl)}" target="_blank" rel="noopener">${esc(srcName)}</a>` : esc(srcName)}</p>` + (k ? chP(`${B(chTx(st.lang).showing)}: ${esc(chLabel(k))}.`) : ''), actions: [{ href: 'dictionary.html#g-' + e.glossary, label: es ? 'Ver en el glosario' : 'See in the glossary' }, ...(k ? [{ label: chTx(st.lang).actSources, run: () => api.info(k) }] : [])] };
      }
    }
    if (e.layer) {
      const done = chLayersOn([e.layer]);
      return { html: chP(`${B(chLayerName(e.layer, st.lang))}: ${esc(es ? 'fuente' : 'source')}: ${esc(chLayerSrc(e.layer, st.lang) || '—')}.`) + (done.length ? chP(esc(es ? 'La encendí en el mapa.' : 'I switched it on.')) : '') + (typeof Ask !== 'undefined' && Ask.SCHEDULE.has(e.layer) ? `<p class="ch-note">${esc(es ? 'Horarios programados (GTFS), no posiciones en vivo.' : 'Scheduled timetables (GTFS), not live positions.')}</p>` : ''), actions: [{ href: 'dictionary.html', label: es ? 'Fuentes y licencias en el diccionario' : 'Sources and licences in the dictionary' }] };
    }
    return Handlers.unknown(st);
  },
  async sensitive(st) {   // a shelter for victims of violence, a person's home, drug points: never drawn; a count by area when there is one
    const es = st.lang === 'es', A = typeof Ask !== 'undefined' ? Ask : null, kind = st.officials ? 'officials' : st.sens.find(k => A && A.PRIVATE.has(k)), say = A && A.SENS_TEXT[kind];
    let html = chP(esc(say ? say[es ? 'es' : 'en'] : '')) + (kind === 'nearMeTx' ? chPasNote(es) : '');
    if (st.keys.length) { html += chP(esc(es ? 'Lo que sí hay, contado por municipio:' : 'What there is, counted by municipio:')); const r = await Handlers[st.places.length ? 'value' : 'show']({ ...st, intent: 'show' }); html += r.html; }
    else if (kind === 'healthPerson') html += chP(esc(es ? 'Tampoco hay datos agregados de esa condición por municipio en el observatorio.' : 'The observatory has no aggregated data on that condition by municipio either.'));
    return { html, actions: [], follow: kind === 'drugs' ? (es ? ['¿Dónde es más alto el crimen?', '¿Qué datos faltan?'] : ['Where is crime highest?', 'What data is missing?']) : kind === 'pii' ? chTx(st.lang).chips.slice(0, 2) : [] };
  },
  async nodata(st) {   // nothing in the observatory answers it (shelters, elections): said plainly, put on the wishlist, with the nearest layers as buttons
    const es = st.lang === 'es', api = chApi(), miss = [...new Set(st.missing)], rel = [...new Set(miss.flatMap(c => c.related || []))], near = chTourismLast([...new Set(miss.flatMap(c => c.near || []))].filter(k => api.meta(k)));
    chAddWish(st.q);
    const said = [...new Set(miss.map(c => c.missing[es ? 'es' : 'en']))];   // one sentence per thing missing, never twice
    let html = chP(esc(said.join('; ').replace(/^./, c => c.toUpperCase()) + '.'));
    const on = chLayersOn(rel), place = st.zoom || st.places[0];   // the nearest layers, on; the place asked about, in view
    if (on.length) html += chP(`${B(es ? 'Encendí lo más cercano' : 'I switched on the nearest layers')}: ${on.map(id => esc(chLayerName(id, st.lang))).join(', ')}.`);
    if (near.length) html += chP(`${B(es ? 'Lo más cercano en datos' : 'The nearest data')}: ${near.slice(0, 3).map(k => esc(chLabel(k))).join('; ')} ${esc(es ? '(no miden lo que pidió).' : '(they do not measure what you asked).')}`);
    if (place && chGoTo(place)) { html += chP(esc(es ? `Acerqué el mapa a ${typeof place === 'string' ? place : place.name.replace(/\b\w/g, c => c.toUpperCase()) + ' (' + place.muni + ')'}.` : `I moved the map to ${typeof place === 'string' ? place : place.name.replace(/\b\w/g, c => c.toUpperCase()) + ' (' + place.muni + ')'}.`)); }
    html += `<p class="ch-note">${esc(chTx(st.lang).noted)}</p>`;
    return { html, actions: [{ label: chTx(st.lang).askMissing, run: () => chAsk(es ? '¿Qué datos faltan?' : 'What data is missing?') }], follow: [...near.slice(0, 2).map(k => T(api.meta(k).label)), ...chTx(st.lang).chips.slice(0, 2)].slice(0, 4) };
  },
  async barrio(st) {   // a barrio named on its own: its value and the map by barrio, the barrio in view; a name that several municipios' barrios share: one chip per municipio
    const api = chApi(), es = st.lang === 'es', b = st.barrio, k = st.keys[0], t = chTx(st.lang);
    if (b.rows.length > 1) {
      const munis = [...new Set(b.rows.map(r => r.muni))], q0 = st.q.replace(/[\s?¿!¡.]+$/, '').trim();
      let html = chP(esc(es ? `Hay ${b.rows.length} barrios llamados ${b.name}, en ${munis.join(', ')}. Escoja uno:` : `${b.rows.length} barrios are named ${b.name}, in ${munis.join(', ')}. Choose one:`));
      if (k && chView() !== '3d') { const r = await api.show({ layers: [{ key: k, mode: 'fill', norm: 'value', level: 'barrio' }], context: [...new Set([...(st.ctx || []), 'lyBarrios'])] }); st.level = (r.applied || []).length ? 'barrio' : ''; CH.ctx = { keys: [k], year: null, muni: null }; html += chP(`${B(t.showing)}: ${esc(chLabel(k))}${esc(es ? ', por barrio donde hay valores.' : ', by barrio where there are values.')}`); }
      else chLayersOn(['lyBarrios']);
      return { html, actions: [], follow: [], chips: munis.slice(0, 4).map(m => `${q0}, ${m}`) };
    }
    const r = b.rows[0], where = `${r.name} (${r.muni})`;
    if (!k) { chLayersOn(['lyBarrios']); CH.ctx = { keys: [], year: null, muni: r.muni }; return { html: chP(esc(chMapless() ? (es ? `El barrio ${r.name} es del municipio de ${r.muni}.` : `The barrio ${r.name} is in the municipio of ${r.muni}.`) : es ? `Acerqué el mapa al barrio ${where}.` : `I moved the map to the barrio ${where}.`)), actions: [chProfileAction(r.muni, st.lang)].filter(Boolean), follow: es ? [`pobreza en ${r.name}, ${r.muni}`, `ingreso en ${r.name}, ${r.muni}`] : [`poverty in ${r.name}, ${r.muni}`, `income in ${r.name}, ${r.muni}`] }; }
    const series = async (x) => x && api.meta(x) && api.levelSeries ? api.levelSeries(x, 'barrio').catch(() => null) : null;
    let s = await series(k), twin = '';
    if (!s && (twin = [CH_BARRIO_TWIN[k], ...(st.alts || [])].find(x => x && api.meta(x)) || '') && (s = await series(twin))) { st.keys = [twin, ...st.keys.filter(x => x !== twin)]; }   // the same thing from the survey, which has barrio values
    const kk = s && twin ? twin : k, j = s && s.ids ? s.ids.findIndex(id => String(id) === r.id) : -1, v = j >= 0 ? s.values[j] : null;
    if (v == null || !isFinite(v)) {   // no barrio values for this dataset (or on the 3D view), or none for this barrio: the municipio's figure, said so
      const o = await Handlers.value({ ...st, intent: 'value', places: [r.muni], keys: [k] });
      o.html = chP(esc(chView() === '3d' ? (es ? `La vista 3D muestra municipios: este es el valor de ${r.muni}, el municipio del barrio ${r.name}. El mapa 2D tiene los valores por barrio.` : `The 3D view shows municipios: this is ${r.muni}'s value, the municipio of the barrio ${r.name}. The 2D map has the barrio values.`) : s ? (es ? `El barrio ${r.name} no tiene un valor publicado de «${chLabel(kk)}»; muestro el de ${r.muni}, y el mapa por barrio.` : `The barrio ${r.name} has no published value of “${chLabel(kk)}”; this is ${r.muni}'s, and the map by barrio.`) : (es ? `«${chLabel(k)}» no tiene valores por barrio; muestro el de ${r.muni}, el municipio del barrio ${r.name}.` : `“${chLabel(k)}” has no barrio values; this is ${r.muni}'s, the municipio of the barrio ${r.name}.`))) + o.html;
      if (s) { await api.show({ layers: [{ key: kk, mode: 'fill', norm: 'value', level: 'barrio' }], context: [...new Set([...(st.ctx || []), 'lyBarrios'])], select: r.muni }); st.level = 'barrio'; st.keys = [kk]; }
      return o;
    }
    const k0 = k; { const k = kk;
    const m = s.moe ? s.moe[j] : null, rate = (api.meta(k) || {}).type === 'rate', per = (s.meta && s.meta.period) || '', mv = chVec(k), i = api.placeIndex(r.muni);
    let html = chP(`${B(where)}: ${esc(chLabel(k))}${per ? ' · ' + esc(per) : ''} → ${B(chVal(k, v))}${m != null && isFinite(m) ? ` (±${esc(rate ? fmt(m, 1) : chVal(k, m))})` : ''}${chUnreliable(v, m) ? esc(es ? ' (poco confiable: margen de error mayor que la mitad del estimado)' : ' (unreliable: a margin of error larger than half the estimate)') : ''}.`);
    if (mv && i >= 0) html += chP(`${esc(r.muni)}: ${esc(chCell(k, mv.values[i], i, 'value'))} · ${esc(t.island)}: ${esc(chVal(k, mv.values[mv.values.length - 1]))}.`);
    if ((api.meta(k) || {}).moe) html += `<p class="ch-note">${chMoeNote(st.lang)}</p>`;
    await api.show({ layers: [{ key: k, mode: 'fill', norm: 'value', level: 'barrio' }], context: [...new Set([...(st.ctx || []), 'lyBarrios'])], select: r.muni });
    CH.ctx = { keys: [k], year: null, muni: r.muni }; st.level = 'barrio';
    if (k !== k0) html = chP(esc(es ? `«${chLabel(k0)}» no tiene valores por barrio; por barrio uso «${chLabel(k)}», de la encuesta.` : `“${chLabel(k0)}” has no barrio values; by barrio this uses “${chLabel(k)}”, from the survey.`)) + html;
    return { html, actions: [{ label: t.actWorkbench, run: () => api.benchOpen('table') }, { label: t.actSources, run: () => api.info(k) }], follow: es ? [`¿Qué barrios de ${r.muni} tienen más ${chLc(chLabel(k))}?`] : [`Which barrios of ${r.muni} rank highest?`] };
    }
  },
  async crisis(st) {   // suicide, self-harm, overdose deaths: said plainly, the crisis line, nothing shaded, no ranking, not a data wish; related data only as a labelled chip
    const es = st.lang === 'es', A = typeof Ask !== 'undefined' ? Ask : null, api = chApi(), rel = ['hpsa_mh_short', 'bh_mh'].filter(k => api.meta(k));
    let html = chP(esc(A ? A.SENS_TEXT.crisis[es ? 'es' : 'en'] : '')) + chPasNote(es);
    if (rel.length) html += `<p class="ch-note">${esc(es ? 'Datos relacionados con la salud mental, que no responden la pregunta:' : 'Related mental health data, which do not answer the question:')} ${rel.map(k => esc(chLabel(k))).join('; ')}.</p>`;
    return { html, actions: [], follow: rel.map(k => T(api.meta(k).label)) };
  },
  async metric3d(st) {   // the 3D view's own column measures ("Uber", "places within a 400 m walk of a stop")
    const es = st.lang === 'es', lab = chMetrics().find(m => m[0] === st.metric);
    await chSetMetric(st.metric);
    return { html: chP(`${B(es ? 'Columnas' : 'Columns')}: ${esc(lab ? lab[1] : st.metric)}.`), actions: [] };
  },
});
// ── Patterns across municipalities ───────────────────────────────────────────
const INSIGHT_KEYS = [['laus_unemp_rate', 'value'], ['poverty_pct', 'value'], ['median_hh_income', 'value'], ['qcew_avg_pay', 'value'], ['gov_job_share_pct', 'value'], ['self_employed_pct', 'value'], ['bachelors_pct', 'value'], ['commute_45plus_pct', 'value'], ['no_vehicle_hh_pct', 'value'], ['no_internet_pct', 'value'], ['gini', 'value'], ['median_gross_rent', 'value'], ['median_home_value', 'value'], ['renter_cost_burden_pct', 'value'], ['vacancy_pct', 'value'], ['age65_pct', 'value'], ['employment_rate_pct', 'value'], ['jobs_per_employed_resident', 'value'], ['work_from_home_pct', 'value'], ['owner_occupied_pct', 'value'], ['commute_drive_alone_pct', 'value'], ['tourism_jobs', 'shareJobs'], ['fed_awards_total', 'perCapita'], ['fema_pa_obligated', 'perCapita'], ['qcew_estabs', 'per1000'], ['qcew_jobs', 'per1000']];
const DOMAIN = { laus_unemp_rate: 'welfare', poverty_pct: 'welfare', median_hh_income: 'welfare', gini: 'welfare', employment_rate_pct: 'welfare', bachelors_pct: 'welfare', no_internet_pct: 'welfare', no_vehicle_hh_pct: 'welfare', median_gross_rent: 'housing', median_home_value: 'housing', renter_cost_burden_pct: 'housing', vacancy_pct: 'housing', owner_occupied_pct: 'housing', qcew_avg_pay: 'work', gov_job_share_pct: 'work', self_employed_pct: 'work', jobs_per_employed_resident: 'work', work_from_home_pct: 'work', qcew_estabs: 'work', qcew_jobs: 'work', commute_45plus_pct: 'mobility', commute_drive_alone_pct: 'mobility', tourism_jobs: 'tourism', fed_awards_total: 'money', fema_pa_obligated: 'money', age65_pct: 'people' };
const MECHANICAL = new Set(['vacancy_pct|seasonal_pct', 'poverty_pct|median_hh_income', 'employment_rate_pct|laus_unemp_rate', 'median_gross_rent|median_home_value', 'commute_drive_alone_pct|no_vehicle_hh_pct', 'qcew_jobs|qcew_estabs', 'jobs_per_employed_resident|qcew_jobs', 'median_hh_income|qcew_avg_pay'].map(s => s.split('|').sort().join('|')));
async function chInsights(st) {
  const api = chApi(), t = chTx(st.lang);
  if (!CH.insights) {
    const V = INSIGHT_KEYS.map(([k, nm]) => ({ k, nm, r: chVec(k, { norm: nm }) })).filter(x => x.r), pairs = [];
    for (let i = 0; i < V.length; i++) for (let j = i + 1; j < V.length; j++) {
      if (MECHANICAL.has([V[i].k, V[j].k].sort().join('|')) || DOMAIN[V[i].k] === DOMAIN[V[j].k]) continue;   // links inside one domain (income and rent) are expected
      const c = chPearson(V[i].r.values, V[j].r.values); if (c && c.n >= 60 && Math.abs(c.r) >= .4) pairs.push({ a: V[i], b: V[j], c });
    }
    pairs.sort((p, q) => Math.abs(q.c.r) - Math.abs(p.c.r));
    const used = {}, doms = new Set(), pick = [];   // one finding per pair of domains and one per dataset, so the list covers different ground
    for (const p of pairs) { const dp = [DOMAIN[p.a.k], DOMAIN[p.b.k]].sort().join('|'); if (used[p.a.k] || used[p.b.k] || doms.has(dp)) continue; pick.push(p); used[p.a.k] = used[p.b.k] = 1; doms.add(dp); if (pick.length >= 5) break; }
    // job concentration
    const jobs = chVec('qcew_jobs'), pop = chVec('population'), lj = chList(jobs.values), pr = jobs.values[jobs.values.length - 1];
    const top = lj[0], popShare = pop ? pop.values[top.i] / pop.values[pop.values.length - 1] * 100 : null, jobShare = top.v / pr * 100, top5 = lj.slice(0, 5).reduce((s, x) => s + x.v, 0) / pr * 100;
    CH.insights = { pairs: pick, jobs: { place: top.name, jobShare, popShare, top5, k: 'qcew_jobs' } };
  }
  const I = CH.insights;
  let html = chP(`${B(st.lang === 'es' ? 'Patrones en los datos reales' : 'Patterns in the real data')} <small>${st.lang === 'es' ? '(los vínculos más fuertes entre áreas distintas, en los 78 municipios, año más reciente de cada dato)' : '(strongest links between different areas of life, across the 78 municipalities, latest year of each dataset)'}</small>`);
  const items = [];
  const j = I.jobs;
  items.push({ text: st.lang === 'es' ? `${j.place} concentra ${fmt(j.jobShare, 0)}% de los empleos de la isla pero solo ${j.popShare ? fmt(j.popShare, 0) + '%' : '—'} de los residentes; los cinco municipios con más empleos suman ${fmt(j.top5, 0)}%. Mucha gente cruza municipios para trabajar.` : `${j.place} holds ${fmt(j.jobShare, 0)}% of the island's jobs but only ${j.popShare ? fmt(j.popShare, 0) + '%' : '—'} of its residents, and the five biggest job centres hold ${fmt(j.top5, 0)}%. Many people cross municipal lines to work.`, run: () => api.show({ layers: [{ key: 'jobs_per_employed_resident', mode: 'fill' }, { key: 'qcew_jobs', mode: 'symbol' }], context: [], bench: 'table' }) });
  I.pairs.forEach(p => {
    const a = chLabel(p.a.k), b = chLabel(p.b.k), dir = p.c.r > 0 ? t.together : t.apart, out = p.c.outliers.slice(0, 2).map(o => api.places()[o.i]).join(', ');
    items.push({ text: `${t.corr(p.c.r, p.c.n, a + (p.a.nm !== 'value' ? ' (' + chLc(chNormLabel(p.a.k, p.a.nm)) + ')' : ''), b + (p.b.nm !== 'value' ? ' (' + chLc(chNormLabel(p.b.k, p.b.nm)) + ')' : ''), dir)} ${out ? t.outliers(out) : ''}`, run: () => api.show({ layers: [{ key: p.a.k, mode: 'fill', norm: p.a.nm }, { key: p.b.k, mode: 'fill', norm: p.b.nm }], context: [], bench: 'scatter' }) });
  });
  html += `<ol class="ch-ol">${items.map((x, i) => `<li>${esc(x.text)} <button type="button" class="linklike" data-ins="${i}">${esc(t.actShow)}</button></li>`).join('')}</ol><p class="ch-note">${esc(t.caveat)}</p>`;
  return { html, actions: [], hook: (box) => box.querySelectorAll('[data-ins]').forEach(b => b.onclick = () => items[+b.dataset.ins].run()), follow: st.lang === 'es' ? ['¿Qué datos faltan?'] : ['What data is missing?'] };
}

// ── Wishlist: requests the observatory could not answer ─────────────────────────────
function chWish() { try { return JSON.parse(localStorage.getItem(CH_WISH_KEY) || '[]'); } catch { return []; } }
function chSaveWish(a) { try { localStorage.setItem(CH_WISH_KEY, JSON.stringify(a.slice(-50))); } catch { /* storage unavailable: the list lasts for this visit only */ CH.memWish = a.slice(-50); } }
function chAddWish(q) { if (CH.handed) return;   // a question that arrived in a link (#ask=) is not the visitor's own wish
  const a = chWish().concat(CH.memWish || []).filter((x, i, s) => s.findIndex(y => y.q === x.q) === i); if (a.some(x => x.q === q)) return; a.push({ q: q.slice(0, 200), t: new Date().toISOString().slice(0, 10) }); chSaveWish(a); }
function chWishText(w) { return 'Data requests from the PR Data Observatory chat\n\n' + w.map(x => `- ${x.q} (${x.t})`).join('\n'); }
function chIssueUrl(w) { return 'https://github.com/Foundation-for-Puerto-Rico/pr-data-observatory/issues/new?title=' + encodeURIComponent('Data requests from the chat') + '&body=' + encodeURIComponent(chWishText(w)); }
async function chCopyWish() { const w = chWish(); if (!w.length) { toast(chTx(CH.ui).wishEmpty, 3000); return; } try { await navigator.clipboard.writeText(chWishText(w)); toast(chTx(CH.ui).copied, 2500); } catch { toast(chTx(CH.ui).copyFail, 4000); } }

// ── Ask ──────────────────────────────────────────────────────────────────────
async function chAsk(q) {
  q = (q || '').trim(); if (!q || CH.busy) return;
  CH.busy = true; chAdd('user', esc(q)); const wait = chAdd('bot', `<span class="ch-wait">${esc(chTx(CH.ui).working)}</span>`, { temp: true });
  try {
    if (!(await chApi().ready())) throw new Error('data');
    if (!CH.wanted) { try { [CH.wanted, CH.registry] = await Promise.all([Data.json('data/wanted.json'), Data.json('data/registry.json')]); } catch { /* the lists are optional */ } }
    if (!CH.ask && typeof S !== 'undefined' && S.catalog) { await withIndex(S.catalog).catch(() => null); }   // the index of the dictionary (catalog_index.json) loads on first use; without it the answers that need it are left out
    chAskWords();
    const pg = chMapless() ? chApi().page : null, own = pg && pg.answer ? await pg.answer(q, chLang(q, CH.lastLang || CH.ui)) : null;   // a page without a map answers "what is this?" from what it shows (askpage.js)
    const { out } = own ? { out: own } : await chAnswer(pg && pg.rewrite ? pg.rewrite(q) : q);
    wait.remove(); chAdd('bot', out.html, out);
  } catch (e) {
    wait.remove(); chAdd('bot', chP(esc(chTx(chLang(q, CH.lastLang || CH.ui)).oops(e.message))));
  } finally { CH.busy = false; }
}
function chAdd(role, html, o = {}) {
  const log = $('#chLog'), el = document.createElement('div'); el.className = 'ch-msg ' + role;
  el.innerHTML = `<div class="ch-b">${html}</div>`;
  const b = el.firstChild;
  if (o.actions && o.actions.length) { const row = document.createElement('div'); row.className = 'ch-acts'; o.actions.forEach(a => { if (a.href) { const l = document.createElement('a'); l.className = 'btn small' + (a.primary ? ' primary' : ''); l.href = a.href; if (!a.self) { l.target = '_blank'; l.rel = 'noopener'; } l.textContent = a.label; row.appendChild(l); } else { const x = document.createElement('button'); x.type = 'button'; x.className = 'btn small' + (a.primary ? ' primary' : ''); x.textContent = a.label; x.onclick = async () => { await a.run(); if (isMobile()) chSheetPeek(); }; row.appendChild(x); } }); b.appendChild(row); }
  const chips = [...(o.follow || []), ...(o.chips || [])];
  if (chips.length) { const row = document.createElement('div'); row.className = 'ch-chips'; chips.slice(0, o.maxChips || 4).forEach(c => { const x = document.createElement('button'); x.type = 'button'; x.className = 'chip'; x.textContent = c; x.style.background = '#BDE0F2'; x.style.color = '#205D7B'; x.onclick = () => chAsk(c); row.appendChild(x); }); b.appendChild(row); }
  if (o.hook) o.hook(b);
  log.appendChild(el); log.scrollTop = log.scrollHeight;
  if (!o.temp) CH.log.push({ role, html });
  return el;
}
const chSheetPeek = () => {};   // on a phone the chat is a bottom sheet over half the map; nothing more to do

// ── UI ───────────────────────────────────────────────────────────────────────
function chBuild() {
  const t = chTx(CH.ui);
  document.body.insertAdjacentHTML('beforeend', `<aside class="chat" id="chat" aria-label="${esc(t.title)}" data-t="skip" hidden>
    <div class="ch-head"><span class="ms-icon" aria-hidden="true">chat_bubble</span><h2 id="chTitle">${esc(t.title)}</h2><span class="tag live">${esc(t.beta)}</span><span class="ch-sp"></span>
      <button type="button" class="btn small" id="chLang" translate="no" aria-label="Español / English" title="Español / English">${CH.ui === 'en' ? 'ES' : 'EN'}</button>
      <button type="button" class="icon-btn small" id="chReset" aria-label="${esc(t.clear)}" title="${esc(t.clear)}"><span class="ms-icon" aria-hidden="true">delete</span></button>
      <button type="button" class="icon-btn small" id="chClose" aria-label="${esc(t.close)}"><span class="ms-icon" aria-hidden="true">close</span></button></div>
    <div class="ch-log" id="chLog" role="log" aria-live="polite" aria-relevant="additions"></div>
    <form class="ch-in" id="chForm"><label for="chInput" class="sr-only">${esc(t.ph)}</label><textarea id="chInput" rows="1" placeholder="${esc(t.ph)}" maxlength="400" autocomplete="off"></textarea><button type="submit" class="icon-btn" id="chSend" aria-label="${esc(t.send)}"><span class="ms-icon" aria-hidden="true">send</span></button></form>
    <div class="ch-foot" id="chFoot">${esc(t.foot)}</div></aside>`);
  $('#chClose').onclick = () => chToggle(false); $('#chBtn').onclick = () => chToggle(!CH.open);
  $('#chReset').onclick = () => { $('#chLog').innerHTML = ''; CH.log = []; chHello(); };
  $('#chLang').onclick = () => { CH.ui = CH.ui === 'en' ? 'es' : 'en'; chRelabel(); };   // for this visit only
  const inp = $('#chInput');
  $('#chForm').onsubmit = e => { e.preventDefault(); const q = inp.value; inp.value = ''; inp.style.height = ''; chAsk(q); };
  inp.onkeydown = e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); $('#chForm').requestSubmit(); } };
  inp.oninput = () => { inp.style.height = 'auto'; inp.style.height = Math.min(120, inp.scrollHeight) + 'px'; };
  $('#chat').addEventListener('keydown', e => { if (e.key === 'Escape') { e.stopPropagation(); chToggle(false); } });
  chHello();
}
function chRelabel() {
  const t = chTx(CH.ui);
  $('#chTitle').textContent = t.title; $('#chat').setAttribute('aria-label', t.title); $('#chLang').textContent = CH.ui === 'en' ? 'ES' : 'EN';
  $('#chInput').placeholder = t.ph; $('#chFoot').textContent = t.foot; $('#chReset').setAttribute('aria-label', t.clear); $('#chClose').setAttribute('aria-label', t.close); $('#chSend').setAttribute('aria-label', t.send); $('#chReset').title = t.clear; const lb = $('#chat label[for="chInput"]'); if (lb) lb.textContent = t.ph;
  const log = $('#chLog'); if (log.children.length === 1 && log.firstChild.dataset.hello) { log.innerHTML = ''; CH.log = []; chHello(); }   // only the greeting so far: say it in the other language
}
function chHello() {
  const pg = chMapless() && chApi().page && chApi().page.intro ? chApi().page.intro(CH.ui) : null;   // a page without a map: its own greeting and questions (askpage.js)
  const el = chAdd('bot', `<p>${esc(pg ? pg.hello : chTx(CH.ui).hello)}</p>`, { follow: pg ? pg.chips : chTx(CH.ui).chips, maxChips: 6, hello: true }); el.dataset.hello = '1';
}
function chToggle(on) {
  CH.open = on; $('#chat').hidden = !on; document.body.classList.toggle('chat-open', on); $('#chBtn').setAttribute('aria-expanded', String(on));
  if (!chMapless()) setTimeout(() => map.invalidateSize ? map.invalidateSize() : map.resize(), 80);   // Leaflet on the 2D map, MapLibre on the 3D view; a page without a map has none
  if (on) { if (isMobile()) setPanel(false); $('#chInput').focus({ preventScroll: true }); if (chApi()) chApi().ready().catch(() => {}); chAskModule(); } else $('#chBtn').focus({ preventScroll: true });   // open: ask.js's index, built once the page's data are in, while the person types the first question; closed: the focus back on the Ask button
}
/** A question handed over in #ask=… (index.html: chatboot.js read it before the map rewrote the address; 3d.html: ask3d.js): out of the address, then asked, capped
    like the box. It may come from any link, so it never clears the map and is never added to the wishlist. */
function chHandIn(q) {
  // ask= out of the address, the other parts as they came (core/viewstate.js on the maps), so a bare "#Ponce" stays a municipality
  const parts = location.hash.slice(1).split('&'), rest = parts.filter(p => !/^ask=/.test(p));
  if (rest.length !== parts.length) history.replaceState(null, '', location.pathname + location.search + (window.Core && Core.viewstate ? Core.viewstate.write('3d', '#' + rest.join('&'), {}) : (rest.filter(Boolean).length ? '#' + rest.filter(Boolean).join('&') : '')));
  if (!CH.open) chToggle(true);
  CH.handed = true;   // chAddWish and the clear answer read it
  return Promise.resolve(chAsk(String(q || '').slice(0, 400))).finally(() => { CH.handed = false; });
}
function chInit() {   // called by chatboot.js once this file has loaded: the button and the suggested questions are chatboot.js's, the window is built here
  chBuild();
  window.Chat = { ask: chAsk, parse: chParse, tools: Tools, state: CH, toggle: chToggle, handOver: chHandIn };
  if (chMapless()) { TX.en.showing = 'Data in this answer'; TX.es.showing = 'Datos de esta respuesta'; }   // nothing is on a map here
  if (typeof S !== 'undefined' && S.catalog) withIndex(S.catalog).catch(() => null);   // the index of the dictionary, for the first answer (chAsk waits for it)
}

/* ── Language-model back end (not enabled) ─────────────────────────────────────
   To let a model answer open-ended questions, set TWIN_CHAT = { endpoint: 'https://…' } to a small proxy FPR hosts, which holds the API key,
   adds the system prompt below, limits tokens and rate, and forwards to the Anthropic Messages API. The page would send { system, messages, tools },
   run any tool_use block with Tools[name](input) and send the tool_result back, so the model only ever sees numbers computed here. Tool names:
   search_datasets, rank, correlate, trend (above), plus show_on_map (ECON.api.show) and missing_data (data/wanted.json). Never put a key in this file.
   System prompt: "You are the PR Data Observatory's data guide for Foundation for Puerto Rico. Answer only from tool results. Say patterns, not causes.
   Reply in the user's language (Spanish when mixed). Never include personal information. Say when data are missing and offer to add the request to the wishlist." */
