/* PR Data Observatory: the understanding layer of "Ask the observatory" (docs/ask.md, "How Ask understands a question").

   chat.js loads this file the first time someone asks something (with core/layers.js, the layer registry), so neither the map's nor the 3D view's first load
   carries it. Nothing here leaves the browser and nothing here is a language model: a lexicon, a scorer and a planner.

     build(src)                one index over what Ask can show: the datasets of the Economy tab (their names in English and Spanish, groups, dictionary
                               "ask" words and Spanish summary words), the map layers of the registry (core/layers.js) and their everyday names, the 3D
                               column measures, the glossary terms (both languages), the municipios and a list of well-known place names
     understand(n, ix, o)      a question (normalised as chat.js's chParse does) cut into topics (concepts of the lexicon, datasets, layers), a place, a time
                               and an operation, with typos corrected against the index's vocabulary; o.rest is chParse's question with the words its rules took blanked
     words(c, lang) ...        the texts the answers use (proxy and sensitive notes, layer names)

   The lexicon (CONCEPTS, LAYER_WORDS, ALIASES) is plain data: docs/ask.md says how to extend it. Words are written without accents, in lower case; a final '*'
   is a prefix ("guagua*" takes guaguas). A concept's datasets are in order of preference (the freshest and most direct first); its layers are what a map of the
   topic shows; proxy says what is missing when its datasets only approach the question. Tourism goes last wherever a list is offered. */
(function (root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api; else root.Ask = api;
})(typeof window !== 'undefined' ? window : globalThis, function () {
  'use strict';
  const VERSION = 1;

  // ── Text ─────────────────────────────────────────────────────────────────────
  const nrm = (s) => String(s || '').normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();   // common.js norm(), without the trim
  const split = (s) => s.split('|').map(x => x.trim()).filter(Boolean);
  /** The words of a normalised text, with where each one starts and ends. */
  function toks(n) { const out = [], re = /[a-z0-9]+(?:-[a-z0-9]+)*/g; let m; while ((m = re.exec(n))) out.push({ w: m[0], a: m.index, b: m.index + m[0].length }); return out; }
  const SUF = ['aciones', 'iciones', 'ciones', 'amientos', 'imientos', 'amiento', 'imiento', 'idades', 'acion', 'icion', 'cion', 'idad', 'ations', 'ation', 'ities', 'ments', 'ment', 'ados', 'adas', 'idos', 'idas', 'ado', 'ada', 'ido', 'ida', 'ed', 'es', 's'];
  /** A light stem for Spanish and English: plurals and the common endings of nouns and participles, then a final e ("transporte", "transportation" and
      "transportación" share "transport"; "escuela" and "escuelas" share "escuela"). A final a or o stays: "costo" is not "costa", "puerto" is not "puerta".
      Words of four letters or fewer stay as they are, and a Spanish gerund is a verb ("viviendo" is not "vivienda"). */
  function stem(w) {
    if (w.length <= 4 || /\d/.test(w) || /(?:ando|iendo|yendo)$/.test(w)) return w;
    if (/ies$/.test(w) && w.length > 5) return w.slice(0, -3) + 'y';
    for (const s of SUF) if (w.endsWith(s) && w.length - s.length >= 4) { w = w.slice(0, -s.length); break; }
    return w.length >= 5 && /e$/.test(w) ? w.slice(0, -1) : w;
  }
  /** Damerau-Levenshtein distance of two words (a swap of two letters is one edit), or max + 1 when it is larger than max. */
  function dl(a, b, max = 2) {
    if (Math.abs(a.length - b.length) > max) return max + 1;
    const d = Array.from({ length: a.length + 1 }, (_, i) => [i, ...Array(b.length).fill(0)]);
    for (let j = 1; j <= b.length; j++) d[0][j] = j;
    for (let i = 1; i <= a.length; i++) {
      let lo = Infinity;
      for (let j = 1; j <= b.length; j++) {
        const c = a[i - 1] === b[j - 1] ? 0 : 1;
        d[i][j] = Math.min(d[i - 1][j] + 1, d[i][j - 1] + 1, d[i - 1][j - 1] + c);
        if (i > 1 && j > 1 && a[i - 1] === b[j - 2] && a[i - 2] === b[j - 1]) d[i][j] = Math.min(d[i][j], d[i - 2][j - 2] + 1);
        lo = Math.min(lo, d[i][j]);
      }
      if (lo > max) return max + 1;
    }
    return d[a.length][b.length];
  }

  // Function words, question words and verbs of both languages: never a topic, never corrected as a typo.
  const STOPW = new Set(('a al ante bajo con contra de del desde durante e el ella ellos en entre es esa ese eso esta este esto estos estas hacia hasta la las le les lo los mas me mi mis muy ni no nos o os para pero por que se sea ser si sin sobre su sus tal te tu un una unas uno unos y ya yo ' +
    'about above after all also an and any are as at be been before being below between both but by can could did do does each few for from had has have he her here him his how i if in into is it its just me more most my no nor not of off on once only or other our out over own same she should so some such than that the their them then there these they this those through to too under until up very was we were what when where which while who whom why will with would you your per since via within without across among along whose ' +
    'cual cuales cuanto cuanta cuantos cuantas donde como cuando quien quienes porque ').split(' ').filter(Boolean));
  const NEARW = new Set('near nearby nearest close closer closest cerca cercano cercana cercanos cercanas proximo proxima proximos proximas lejos far farther'.split(' '));   // distance, not a topic (understand: the datasets' own words)
  const KNOWN = new Set(('muestra muestrame muestreme mostrar mostrarme ensena ensename enseneme ver veo quiero queremos dime digame dame deme hablame hableme cuentame quisiera puedes puede podrias podria necesito busco buscar enciende encender prende prender activa activar pon ponme ponga poner agrega agregar anade quita quitar apaga dibuja dibujar mapa mapas capa capas datos dato informacion info sobre tema temas ' +
    'hola gracias favor saludos buenos buenas dias tardes noches ok vale bueno claro ayuda ayudame pregunta preguntar respuesta ahora hoy ayer manana ano anos mes meses semana tiempo vez veces cosa cosas algo nada todo toda todos todas cada otro otra otros otras mismo misma ' +
    'municipio municipios pueblo pueblos isla region regiones zona zonas area areas lugar lugares sitio sitios parte partes puerto rico pr boricua nivel tasa tasas porcentaje numero cantidad total promedio mediana alto alta altos altas bajos bajas mayor menor mejor peor primero primeros ultimo ultimos top ' +
    'show me tell give see map maps layer layers data please thanks hello hi hey help want need like look find list display turn switch put add remove clear reset now today year years month time thing things way ' +
    'municipality municipalities town towns island area areas place places region level rate rates percent percentage number count total average median high higher highest low lower lowest best worst top bottom first last most least ' +
    'hay tiene tienen tengo tenemos esta estan estoy son fue fueron ha han he hemos hace hacen hacer haciendo vive viven vivir viviendo existe existen pasa pasando sale salen va van ir vamos sigue siguen cambia cambian deberia ' +
    'is are was were has have had do does did go goes going live lives living exist exists happen happening compare comparar compara versus vs relacion relaciona relacionan relationship correlation correlacion trend tendencia ' +
    'menos mas mayores menores maximo minimo peores mejores much many more less fewer higher lower greater greatest largest smallest biggest worst best highest lowest ' +
    'cambio cambios cambiado cambiada cambiaron cambia change changes changed changing tendencias trends evolucion evolution crecimiento growth aumento increase disminucion decrease subida bajada historia history ' +
    'comparacion comparison relaciones relations correlaciones correlations diferencia diferencias difference differences casos caso gente medio junto juntos together ' +
    'grande grandes pequeno pequenos nuevo nuevos nueva nuevas reciente recientes actual actuales general entera completo completa ' +
    'people persons person residents resident adults adult individuals individual citizens citizen folks humans members member neighbors neighbours families family share shares ' +
    'personas persona residentes adultos adulto individuos individuo ciudadanos ciudadano miembros vecinos familias familia proporcion parte partes ' +
    'addition relation relations relationship decade decades military minimal maximal varies vary moves move moving based due figure figures value values measure measures ' +
    'question questions answer answers example examples kind kinds type types group groups set sets list lists table tables chart charts view views word words name names ' +
    'one two three four five six seven eight nine ten uno dos tres cuatro cinco seis siete ocho nueve diez primera segundo segunda tercero tercera second third ' +
    'order older links lines tries trips distinct const floor topic cancel decision conservative exported expected survives parses minimap file files class classes legend link value ' +
    'counted count counts number numbers figure source sources note notes break breaks rising falling moved hair strictly weighted weight ' +
    'pasada pasado pasadas pasados proxima proximo proximas proximos siguiente siguientes anterior anteriores ultima ultimas semana semanas mitad entero enteros cerca lejos dentro fuera arriba abajo ' +
    'except excepto including incluye incluido overall built open opened closed abierto abierta cerrado call llamar apart aparte other others otros all every each only also used use usa based basado kind').split(' ').filter(Boolean));   // and words of datasets' names that name nothing by themselves ("except", "overall", "built")

  // The topic words of chat.js's rules (its CONCEPTS list), which the lexicon below does not repeat: what a typo is corrected to, beside the lexicon's own words.
  const TOPIC_WORDS = ('pobreza poverty desempleo unemployment empleo empleos employment jobs ingreso ingresos income salario salarios sueldo sueldos wages alquiler rent rentas vivienda viviendas housing ' +
    'poblacion population habitantes turismo tourism hoteles hotels restaurantes restaurants manufactura manufacturing construccion construction agricultura agriculture finanzas finance gobierno government ' +
    'crimenes crimes delitos asesinatos murders homicidios veteranos veterans discapacidad disability mujeres women ninos children ancianos elderly hogares households vacantes vacancy abandonadas ' +
    'hacinamiento overcrowding asequibilidad affordability internet commute desigualdad inequality federales federal establecimientos negocios businesses escuelas schools hospitales hospitals ' +
    'clinicas clinics dentistas dentists psiquiatras escasez shortage puentes bridges derrumbes landslides terremotos earthquakes humedales wetlands bibliotecas libraries bomberos policia police').split(' ');
  // The topics a typo is never corrected to: a real word read as crime, addiction, disease, death or violence is worse than a word not understood ("shopping" is not
  // "shooting", "cancelar" is not "cáncer").
  const ALARM = new Set(['crime', 'shootings', 'domestic_violence', 'addiction', 'drug_use', 'disease', 'mental', 'emergency_rooms', 'hospice', 'shelters', 'property_crime']);
  const ALARM_WORDS = new Set('crimenes crimes delitos asesinatos murders homicidios muertes muertos deaths death violencia violence'.split(' '));
  // The function words of each language: what a question is written in, whatever its names of places and of datasets ("unemployment in Bayamón" is English).
  const FW = { es: new Set('el la los las del de que en es son por para con una unos unas como donde cual cuales cuanto cuanta cuantos cuantas hay tiene tienen tienes mas menos muy pero sin sobre entre desde hasta y muestra muestrame ensename dime quiero puedes estan esta este estos estas al se cuales mi su sus'.split(' ')),
    en: new Set('the of in on at to for with is are was were what which where how show and or by from about most more less than this that these those do does did there my your their it be have has can you we'.split(' ')) };
  /** The language a question is written in, by its function words: 'es', 'en' or null (none, or as many of each). */
  function langOf(n) { let es = 0, en = 0; for (const t of toks(n)) { if (FW.es.has(t.w)) es++; if (FW.en.has(t.w)) en++; } return es > en ? 'es' : en > es ? 'en' : null; }
  // Real words that are one edit from a topic word: never corrected ("tienes" is not "trenes", "Guayabal" is not Guayama, "Cidral" is not Cidra). tests/ask_words.js
  // writes them: common Spanish and English words, the observatory's own texts, every name of the gazetteer and of the barrios that the correction would change.
  /* PROTECTED-BEGIN (tests/ask_words.js) */
  const PROTECTED = new Set(('acercan adultas alquilar antillas arenas arroyos attracting ayudan ayudar bajas bajura barcelona bares barros batches berrios bimbas bonito boquern botija botijas brenas bridle bright ' +
    'busque cables caguabo caidos calida caller cambie caminan candal capitan cargan cargar caribe caridad carlos carola carolinas casey casillas catalina catolica causas cayano cdbgdr ' +
    'cellular centra cerraran changa charge charters charting chivos ciara ciclos cidral cierra cifra colina collections collective combinando comentarios comercio compran conditioners conductivity connecting connectors ' +
    'constructor contributing contribution convention conventions conversation coralina coroza corrections cresta critically cuales cuarta cubones cuebas cuenta cuentan cuentas cueste cuesten culebras culebrina culebrinas curras ' +
    'curves desarrollado desserts divida diving dorados electronic electronica electronico electronicos electronics escobar especially essentially estacionales estadio extensive fares fatalidades fatalities finest floors founding frames ' +
    'garage generativa generative gentle gravel grazes guaonica guayabo guayabos horses hostel hostels immigrants incentivos inmigrantes intentarlo interaction interruptions inundarian irlandes islanders jaguas juntas juntos ' +
    'landfall landuse lanes latas leading lijas lindas lineal linear listan listar llanos llegan llenar llevar lucero lylibraries maestria maestrias maneja manejada mangoes manzanas mapper ' +
    'maraguez marcados marcas mareas mares marinas marini marino markers matias mediation medidas medinas mexico morado naranjo negron neighbourhood neighbourhoods numera nutritional obrera oceano padilla ' +
    'pagada pagados paints pajilla palmar palomas panell papeles parana pardas pardos pares parquet paseos pasillos pastor pavimentado pavimentar penones pequenas personales pezuela piensa pilones ' +
    'planillas pointy policiales policy polluters ponche prados preciso precisos prints programado propia puerca puerco qualify quemaos recortados rectas refuse refuses relied rellenados reproduction rescale ' +
    'resiliency restate rivera rivero roofers router sabalos seguida segura senala sports stopping storey storeys suites tariff tariffs terminalfl terminan terminar terminated toledo topics traces ' +
    'transfiere transformation transforms transportan traves turabo urbina vailla valles varias varios vegano vender ventaja viales writes writing yaguez').split(' '));
  /* PROTECTED-END */

  // ── Lexicon: everyday words → what the observatory can show ─────────────────
  // [id, Spanish words, English words, datasets (best first), layers, options]. options: proxy { es, en }: the datasets only approach the question (what is missing);
  // missing { es, en }: the observatory has nothing on it; sens: 'count' (counted by area, never drawn as points); domain: the registry field the topic belongs to.
  const RAW = [
    // mobility
    ['transit', 'guagua*|autobus*|omnibus|bus|buses|ama|metrobus|metro bus|transporte colectivo|transporte publico|transportacion publica|transporte en comun|carro publico|carros publicos|carritos publicos|los publicos|sistema de transporte', 'bus|buses|bus service|public transit|public transport|public transportation|mass transit|transit system|transit', 'pop_walk_active_pct|commute_transit_pct|pop_served_active_pct|transit_stops|exp_stop_cur_pop', 'lyRoutes|lyStops', { domain: 'infrastructure.mobility' }],
    ['transport', 'transporte|transportacion|movilidad|ati|autoridad de transporte', 'transportation|transport|mobility|getting around', 'pop_walk_active_pct|commute_transit_pct|no_vehicle_hh_pct|commute_45plus_pct', 'lyRoutes|lyStops', { domain: 'infrastructure.mobility' }],
    ['train', 'tren urbano|tren|trenes', 'train|trains|urban train|rail|light rail|tren urbano', 'pop_walk_active_pct|commute_transit_pct', 'lyHubs|lyRoutes', { domain: 'infrastructure.mobility' }],
    ['ferry', 'lancha*|ferry|ferri|ferris|ferries|transporte maritimo|acuaexpreso', 'ferry|ferries|ferry boat*', 'ferry_passengers', 'lyHubs|lyRoutes', { domain: 'infrastructure.mobility' }],
    ['airport', 'aeropuerto*|avion*|vuelo*|aerolinea*|pasajeros aereos', 'airport*|flight*|airline*|plane*|air travel|air passengers', 'air_passengers|air_departures|air_enplanements_faa', 'lyHubs', { domain: 'infrastructure.mobility' }],
    ['traffic', 'tapon|tapones|trafico|transito|congestion|embotellamiento*|hora pico|horas pico', 'traffic|congestion|traffic jam*|rush hour|gridlock', 'commute_45plus_pct|commute_drive_alone_pct', '', { proxy: { es: 'no hay datos de tráfico ni de congestión; muestro los viajes al trabajo de 45 minutos o más', en: 'there are no traffic or congestion data; commutes of 45 minutes or more stand in' } }],
    ['no_car', 'hogares sin carro|hogares sin vehiculo|sin carro|sin vehiculo|sin auto|no tienen carro|no tienen vehiculo', 'households without a car|households without a vehicle|no car|no vehicle|without a car|carless|car-free households', 'no_vehicle_hh_pct', ''],
    ['car', 'carro|carros|auto|autos|automovil*|vehiculo|vehiculos|guiar|conducir', 'car|cars|vehicle|vehicles|driving', 'no_vehicle_hh_pct|commute_drive_alone_pct', ''],
    ['walk', 'caminar|caminando|a pie|peaton*|caminabilidad', 'walk|walking|walkability|walkable|pedestrian*|on foot', 'commute_walk_pct|pop_walk_active_pct|street_intersection_density', ''],
    ['commute', 'viaje al trabajo|viajes al trabajo|tiempo de viaje|ir al trabajo|llegar al trabajo|trayecto*', 'commute*|travel time|trip to work|trips to work', 'commute_45plus_pct|commute_drive_alone_pct|commute_transit_pct', ''],
    ['roads', 'carretera*|calles|autopista*|vias|expreso*|red vial', 'road|roads|streets|highway*|street network', 'street_intersection_density|bridges_poor|bridges', ''],
    ['potholes', 'hoyo|hoyos|bache*|pavimento|asfalto|carreteras en mal estado|calles en mal estado|mal estado de las carreteras|estado de las carreteras', 'pothole*|pavement|road condition*|road quality|bad roads', '', '', { missing: { es: 'el observatorio no tiene datos del estado del pavimento ni de baches', en: 'the observatory has no pavement condition or pothole data' }, near: 'bridges_poor_pct|bridges_poor' }],
    ['frequent_service', 'paradas frecuentes|servicio frecuente|guaguas frecuentes|alta frecuencia', 'frequent stops|frequent service|frequent buses|high frequency', 'exp_stop_freq_pop|exp_walk_freq_pop', 'lyStops'],
    ['weekend_service', 'servicio los domingos|guaguas los domingos|transporte los domingos|servicio los sabados|guaguas los sabados|transporte los fines de semana|servicio de fin de semana|servicio los fines de semana', 'sunday service|weekend service|saturday service|buses on sundays|buses on weekends|transit on weekends', 'exp_stop_sun_pop|exp_stop_sat_pop', 'lyStops'],
    ['bridges', 'puente|puentes', 'bridge|bridges', 'bridges_poor|bridges_poor_pct|bridges', ''],
    // housing
    ['housing', 'vivienda|viviendas|casa|casas|hogar propio|apartamento*|inmuebles', 'housing|homes|houses|house|home|apartment*|dwelling*', 'median_gross_rent|renter_cost_burden_pct|median_home_value|vacancy_pct|affordability_ratio|owner_occupied_pct|housing_units|households|census_housing_units|vacant_units', '', { domain: 'housing' }],
    ['home_value', 'valor de las casas|valor de la casa|valor de las viviendas|valor de la vivienda|precio de las viviendas|precio de la vivienda|precio de las propiedades|valor de la propiedad|valor de las propiedades|cuanto cuestan las casas|costo de las casas|precio de las casas|precios de las casas|precio de una casa|precio de casas|precios de vivienda|precio de vivienda|casas valen|valen las casas|cuanto vale una casa|cuanto valen las casas|cuesta una casa|cuestan las casas|cuesta comprar una casa', 'home value*|house price*|home price*|housing price*|property value*|cost of homes|cost of a house|price of homes|price of houses|houses are worth|homes are worth|homes worth|houses worth|home worth|what homes are worth|cost to buy a house', 'median_home_value|affordability_ratio', ''],
    ['cost_of_living', 'costo de vida|costo de la vida|lo caro|carestia|vida cara|lo que cuesta vivir', 'cost of living|living costs|expensive to live', 'median_gross_rent|renter_cost_burden_pct|median_owner_costs_mortgage|median_home_value', '', { proxy: { es: 'no hay un índice de costo de vida por municipio; muestro los costos de vivienda', en: 'there is no cost-of-living index by municipio; housing costs stand in' } }],
    ['housing_units', 'unidades de vivienda|unidades de viviendas|numero de viviendas|cantidad de viviendas|cuantas viviendas|cuantas casas|parque de viviendas|inventario de viviendas', 'housing units|number of homes|how many homes|how many houses|housing stock', 'housing_units|census_housing_units', ''],
    ['rental_vacancy', 'vacantes de alquiler|alquileres vacantes|viviendas de alquiler vacantes|desocupacion de alquiler', 'rental vacancy|vacant rentals|rental vacancies', 'rental_vacancy_pct', ''],
    ['home_age', 'casas viejas|viviendas viejas|casas antiguas|viviendas antiguas|edificios viejos|ano de construccion|antiguedad de las viviendas|edad de las casas', 'older homes|old homes|old houses|old buildings|year built|age of homes|housing age', 'median_year_built', ''],
    ['severe_burden', 'carga severa|carga extrema|mas de la mitad del ingreso en alquiler|mitad del ingreso', 'severe rent burden|severely cost burdened|severely burdened|half of their income', 'renter_severe_burden_pct', ''],
    ['household_size', 'tamano de los hogares|tamano del hogar|tamano promedio del hogar|personas por hogar|miembros por hogar', 'household size|people per household|persons per household', 'avg_household_size', ''],
    ['mortgage', 'hipoteca*', 'mortgage*', 'median_owner_costs_mortgage|owner_cost_burden_pct', ''],
    ['public_housing', 'residencial|residenciales|caserio|caserios|vivienda publica|viviendas publicas|vivienda de interes social|proyectos de vivienda', 'public housing|housing projects|housing project', 'ph_units|ph_devs', 'lyPubHousing'],
    ['tax_credit_housing', 'credito contributivo de vivienda|creditos contributivos de vivienda|vivienda con credito contributivo|lihtc', 'low-income housing tax credit*|tax credit housing|lihtc', 'lihtc_li_units|lihtc_units|lihtc_projects', 'lyLihtc'],
    ['new_markets', 'nuevos mercados|credito de nuevos mercados|nmtc|inversion en comunidades de bajos ingresos', 'new markets tax credit*|new markets|nmtc|qlici*', 'nmtc_qlici|nmtc_projects', ''],
    ['vacant', 'estorbo*|casas vacias|casa vacia|viviendas vacias|vivienda vacia|viviendas vacantes|unidades vacantes|casas abandonadas|viviendas abandonadas|edificios abandonados|viviendas desocupadas|casas desocupadas|viviendas deshabitadas|propiedades abandonadas|desocupad*|deshabitad*', 'empty homes|empty houses|vacant homes|vacant houses|vacant housing|vacant units|abandoned homes|abandoned houses|abandoned buildings|abandoned properties|blight*', 'other_vacant_pct|vacancy_pct', ''],
    ['homeless', 'sin hogar|sin techo|deambulante*|personas sin vivienda|desamparad*', 'homeless*|unhoused|without a home', 'chas_severe_pct|renter_severe_burden_pct|poverty_pct', '', { proxy: { es: 'no hay un conteo de personas sin hogar (el conteo Point-in-Time de HUD no está en el observatorio); muestro los hogares con problemas graves de vivienda', en: "there is no count of people experiencing homelessness (HUD's Point-in-Time count is not in the observatory); households with severe housing problems stand in" } }],
    ['gentrification', 'gentrifica*|desplazamiento|desplazados|aburguesamiento', 'gentrif*|displacement', 'seasonal_pct|median_gross_rent|median_home_value', '', { proxy: { es: 'no hay una medida de gentrificación; muestro las unidades de uso estacional (incluyen alquileres a corto plazo) y los costos de vivienda', en: 'there is no measure of gentrification; seasonal-use units (they include short-term rentals) and housing costs stand in' } }],
    ['housing_problems', 'problemas de vivienda|problemas graves de vivienda|condiciones de vivienda|vivienda inadecuada|casas en mal estado', 'housing problems|substandard housing|housing conditions', 'chas_severe_pct|overcrowded_pct', ''],
    // population
    ['population', 'poblacion|habitantes|demografia|demografic*|censo', 'population|inhabitants|demograph*|census', 'population|pop_change_since_2010_pct|median_age|age65_pct', '', { domain: 'population' }],
    ['population_count', 'cuanta gente|cuantas personas|cuantos viven|cuanta poblacion|cuantos habitantes', 'how many people|how many residents|how many inhabitants', 'population|pop_change_since_2010_pct', '', { alone: true }],
    ['pop_loss', 'despoblacion|se despuebla|despoblad*|perdieron poblacion|perdio poblacion|perdida de poblacion|menos gente|perdieron gente|pierden gente|perdio gente|perdieron habitantes|quedando vacios|se vacian|vaciando', 'depopulation|population loss|shrinking population|lost people|losing people|lost population|losing population|lost residents|losing residents', 'pop_change_since_2010_pct|pop_change_since_2020_pct', ''],
    ['migration', 'emigracion|emigra*|migracion|migra*|inmigra*|se van|se va|se fue|se fueron|se mudan|se muda|se mudo|se mudaron|mudarse|exodo|diaspora|irse de la isla', 'migration|emigration|emigrat*|migrat*|migrant*|immigra*|leaving the island|moving to the mainland|moving away|moving to|moved to|move to|relocat*|exodus|diaspora|out-migration', 'pop_change_since_2010_pct|pop_change_since_2020_pct', '', { proxy: { es: 'no hay datos de migración por municipio; muestro el cambio de población desde el censo de 2010, que también incluye nacimientos y muertes', en: 'there are no migration data by municipio; population change since the 2010 census stands in, and it also counts births and deaths' } }],
    ['elderly', 'envejecientes|envejeciente|viejos|viejitos|viejitas|tercera edad|personas mayores|gente mayor|gente de edad|personas de edad|edad avanzada|jubilados|retirados|pensionados|adultos mayores|ancianos', 'older people|old people|retirees|pensioners|aging population|elderly|seniors', 'age65_pct|acs_age65plus_pct|median_age', '', { domain: 'population', group: { es: 'las personas de 65 años o más', en: 'people aged 65 and over' } }],
    ['children', 'nenes|nenas|chamacos|chamaquitos|infantes|bebes|menores', 'kids|babies|infants|children', 'acs_under18_pct|acs_age_under3_pct|acs_age5to17_pct', '', { group: { es: 'los niños', en: 'children' } }],
    ['young_children', 'menores de 5|menores de cinco|ninos pequenos|ninos de edad preescolar|bebes|infantes|primera infancia', 'under 5|under five|young children|toddlers|preschoolers|babies|infants|early childhood', 'acs_age_under3_pct|acs_age3to4_pct', '', { group: { es: 'los niños pequeños', en: 'young children' } }],
    ['youth', 'jovenes|juventud|juvenil|juveniles|adolescentes', 'youth|young people|young adults|teens|teenagers', 'acs_age18to24_pct|acs_age5to17_pct', '', { group: { es: 'los jóvenes', en: 'young people' } }],
    ['childcare', 'cuido|cuidos|cuido de ninos|guarderia*|centros de cuido|cuidado infantil|cuidado de ninos|head start|preescolar|pre escolar', 'child care|childcare|daycare|day care|preschool*|head start|nursery school*', 'acs_age_under3_pct|acs_age3to4_pct|acs_under18_pct', '', { proxy: { es: 'no hay datos de centros de cuido ni de su capacidad; muestro la proporción de niños pequeños, que es la población que lo necesita', en: 'there are no data on child care centres or their capacity; the share of young children, who need it, stands in' } }],
    // economy
    ['quality_of_life', 'calidad de vida|bienestar|como se vive|condiciones de vida', 'quality of life|well-being|wellbeing|living conditions|livability', 'poverty_pct|median_hh_income|laus_unemp_rate', '', { profile: true }],
    ['economy', 'economia|economic*|desarrollo economico|actividad economica|crecimiento economico', 'economy|economic*|economic development', 'qcew_jobs|laus_unemp_rate|median_hh_income|qcew_avg_pay|qcew_estabs', '', { domain: 'economy' }],
    ['jobs', 'trabajo|trabajos|chamba|puestos de trabajo|oportunidades de empleo', 'work|careers', 'qcew_jobs|laus_unemp_rate|employment_rate_pct', '', { domain: 'economy' }],
    ['unemployment', 'sin trabajo|sin empleo|sin empleos|desempleados|desocupados|parados|cesantes', 'jobless|out of work|unemployed', 'laus_unemp_rate|laus_unemployed', ''],
    ['government_jobs', 'empleados publicos|empleo publico|empleos publicos|trabajos del gobierno|empleados del gobierno', 'public employees|public sector jobs|government workers|government employees', 'qcew_gov_jobs|gov_job_share_pct|gov_worker_pct', ''],
    ['money', 'chavos|dinero|plata|billetes', 'money|cash', 'median_hh_income|per_capita_income|qcew_avg_pay', ''],
    ['min_wage', 'salario minimo|sueldo minimo|paga minima', 'minimum wage', '', '', { missing: { es: 'el observatorio no tiene datos del salario mínimo ni de quién lo gana', en: 'the observatory has no minimum-wage data' }, near: 'qcew_avg_pay|hh_income_under_25k_pct' }],
    ['welfare', 'pan|cupones|asistencia nutricional|programa de asistencia nutricional|mantengo|ayudas del gobierno|asistencia publica|tanf|wic', 'food stamps|snap|nutrition assistance|welfare|public assistance|tanf|wic', 'poverty_pct|hh_income_under_25k_pct', '', { proxy: { es: 'no hay datos del PAN ni de otras ayudas por municipio; muestro la pobreza y los hogares de ingreso bajo', en: 'there are no data on nutrition assistance (PAN, SNAP) or other aid by municipio; poverty and low-income households stand in' } }],
    ['social_security', 'seguro social', 'social security', 'fed_direct_payments', '', { proxy: { es: 'no hay datos del Seguro Social aparte; muestro los pagos directos federales, que lo incluyen', en: 'there are no Social Security data on their own; federal direct payments, which include them, stand in' } }],
    ['business', 'comercios|tiendas|colmados|pymes|pequenos negocios', 'shops|stores|small business*', 'qcew_estabs|jobs_naics_44_45', ''],
    ['pharma', 'farmaceutica*|industria farmaceutica', 'pharmaceutical*|pharma', 'jobs_naics_31_33', '', { proxy: { es: 'no separo la industria farmacéutica; muestro los empleos de toda la manufactura', en: 'the pharmaceutical industry is not separated; all manufacturing jobs stand in' } }],
    ['agriculture', 'agricultores|fincas|finca|cosechas|ganaderia|pesca|pescadores', 'farmers|crops|fisheries|ranching', 'jobs_naics_11', ''],
    ['nonprofits', 'organizaciones comunitarias|ong|ongs|organizaciones sin fines de lucro|fundaciones|tercer sector', 'ngo|ngos|charities|charity|community organizations|nonprofit sector', 'npo_all|npo_501c3', ''],
    ['federal', 'fondos federales|dinero federal|chavos federales|ayuda federal|fondos de recuperacion|recuperacion|cdbg|cdbg-dr|asignaciones federales', 'federal funds|federal money|federal funding|recovery funds|recovery|cdbg|cdbg-dr', 'fed_awards_total|fema_pa_obligated|fed_grants|fed_direct_payments|fed_contracts|fed_loans|fed_other', '', { domain: 'public-money' }],
    ['tourism', 'turistas|visitantes|hospederias|paradores|cruceros|chinchorros|turismo', 'tourists|visitors|cruise*|tourism', 'tourism_jobs|tourism_places|lodging_places', 'lyPlaces', { domain: 'economy.visitor-economy', last: true }],
    // health
    ['health', 'salud|sistema de salud|servicios de salud|acceso a salud|acceso a la salud|cuidado de salud|atencion medica|servicios medicos', 'health|healthcare|health care|health services|medical care|access to care|health access', 'hc_sites|hpsa_pc_short|hc_drive_min|acs_uninsured_pct|cms_hospitals', '', { domain: 'health' }],
    ['hospitals', 'hospital|hospitales', 'hospital|hospitals', 'cms_hospitals|hosp_drive_min|cms_hospitals_er|hosp_road_km', '', { sens: 'count' }],
    ['emergency_rooms', 'sala de emergencia*|salas de emergencia*|urgencias|hospitales con emergencia|cuarto de urgencia*', 'emergency room*|emergency department*|er visits', 'cms_hospitals_er|hosp_drive_min', '', { sens: 'count' }],
    ['home_health', 'cuidado en el hogar|salud en el hogar|cuido en el hogar|agencias de salud en el hogar', 'home health|home care|home health care', 'cms_home_health', '', { sens: 'count' }],
    ['hospice', 'hospicio*|cuidado paliativo|cuidados paliativos', 'hospice*|palliative care', 'cms_hospice', '', { sens: 'count' }],
    ['clinics', 'centros 330|centro 330|centros de salud comunitarios|centro de salud comunitario|clinica*', 'community health center*|health clinic*|clinic*|330 center*', 'hc_sites|hc_drive_min|hc_vans', '', { sens: 'count' }],
    ['cdt', 'cdt|cdts|centro de diagnostico y tratamiento|centros de diagnostico y tratamiento', 'cdt|cdts|diagnostic and treatment center*', 'hc_sites|hc_drive_min', '', { sens: 'count', proxy: { es: 'el observatorio no tiene la lista de los CDT; muestro los sitios de los centros de salud comunitarios (HRSA, sección 330), contados por municipio', en: 'the observatory has no list of CDTs (diagnostic and treatment centers); community health center sites (HRSA section 330), counted by municipio, stand in' } }],
    ['pharmacy', 'farmacia*|botica*|medicamentos|medicinas', 'pharmac*|drugstore*|medication*|prescription*', '', '', { missing: { es: 'el observatorio no tiene datos de farmacias', en: 'the observatory has no pharmacy data' }, near: 'hc_sites|hc_drive_min' }],
    ['disease', 'diabetes|asma|cancer|obesidad|hipertension|presion alta|enfermedad*|dengue|covid*|mortalidad|esperanza de vida|natalidad|nacimientos|epidemia*|vacunacion|vacunas|vih|sida', 'diabetes|asthma|cancer|obesity|hypertension|disease*|illness*|dengue|covid*|mortality|life expectancy|birth rate|births|vaccin*|hiv|aids', '', '', { missing: { es: 'el observatorio no tiene datos de enfermedades, nacimientos ni muertes por municipio', en: 'the observatory has no data on disease, births or deaths by municipio' }, near: 'hpsa_pc_short|acs_uninsured_pct|hc_drive_min' }],
    ['insurance', 'plan de salud|planes de salud|seguro medico|seguro de salud|sin seguro|sin plan medico', 'health insurance|uninsured|insurance coverage|without insurance', 'acs_uninsured_pct', ''],
    ['medicaid', 'la reforma|plan vital|medicaid|plan del gobierno|tarjeta de salud', 'medicaid', '', '', { missing: { es: 'el observatorio no tiene la matrícula del Plan Vital (Medicaid) por municipio', en: 'the observatory has no Plan Vital (Medicaid) enrolment data by municipio' }, near: 'acs_uninsured_pct|poverty_pct' }],
    ['medicare', 'medicare', 'medicare', 'medicare_benes|medicare_ma_pct', ''],
    ['mental', 'mental|psicolog*|psiquiatr*|depresion|ansiedad', 'mental|psycholog*|psychiatr*|depression|anxiety', 'hpsa_mh_short|bh_mh|bh_all', ''],
    ['addiction', 'tratamiento de drogas|tratamiento de adiccion*|rehabilitacion|centros de rehabilitacion|metadona|clinicas de metadona|clinica de metadona|centros de metadona|clinicas de tratamiento|centros de tratamiento', 'drug treatment|addiction treatment|rehab|rehabilitation|methadone|methadone clinic*|treatment facilit*|treatment centers|treatment centres', 'bh_su|bh_all|bh_both', '', { sens: 'count' }],
    ['drug_use', 'drogas|droga|consumo de drogas|uso de drogas|uso de sustancias|adiccion*|adictos|narcoticos|opioides|fentanilo', 'drugs|drug use|drug abuse|substance use|substance abuse|addiction*|opioid*|fentanyl', 'bh_su|bh_all', '', { sens: 'count', proxy: { es: 'no hay datos de consumo de drogas ni de sobredosis por municipio; muestro los centros de tratamiento de uso de sustancias (SAMHSA), que no miden el consumo', en: 'there are no drug use or overdose data by municipio; substance use treatment facilities (SAMHSA), which do not measure use, stand in' } }],
    ['nursing', 'hogares de ancianos|hogar de ancianos|hogares de envejecientes|asilo*|hogar de cuido|hogares de cuido', 'nursing home*|elder care|assisted living', 'cms_nursing_homes|age65_pct', ''],
    ['egidas', 'egida|egidas', 'senior housing', 'cms_nursing_homes|age65_pct', '', { proxy: { es: 'no hay datos de égidas; muestro los hogares de ancianos certificados por CMS y la proporción de residentes de 65 años o más', en: 'there are no senior-housing data; CMS-certified nursing homes and the share of residents aged 65 and over stand in' } }],
    ['dialysis', 'dialisis', 'dialysis', 'cms_dialysis', ''],
    ['emergency', 'emergencias|ambulancia*|911|manejo de emergencias|rescate', 'emergency services|ambulance*|911', 'fire_stations|cms_hospitals_er', 'lyFire'],
    // education
    ['education', 'educacion|educativo|educativa|escolaridad|nivel educativo|aprovechamiento escolar', 'education|educational|schooling', 'bachelors_pct|acs_no_hs_pct|sch_open|sch_enroll', 'lyLibraries', { domain: 'education' }],
    ['schools', 'escuela|escuelas|planteles|plantel escolar|escuelas publicas|sistema escolar|departamento de educacion', 'school|schools|public schools|school system', 'sch_open|sch_enroll|sch_ptr', ''],
    ['school_closures', 'escuelas cerradas|cierre de escuelas|cierres de escuelas|escuelas que cerraron|cerraron escuelas', 'school closures|closed schools|schools closed|school closing*|closing schools', 'sch_closed|sch_open', ''],
    ['student_teacher', 'estudiantes por maestro|alumnos por maestro|estudiantes por maestra|razon de estudiantes', 'students per teacher|pupil teacher ratio|pupils per teacher|student teacher ratio', 'sch_ptr|sch_teachers', ''],
    ['college_students', 'estudiantes universitarios|universitarios|matricula universitaria|estudiantes de universidad', 'college students|university students|college enrollment|university enrollment', 'he_enroll|he_inst', ''],
    ['students', 'estudiantes|alumnos|matricula', 'students|pupils|enrollment|enrolment', 'sch_enroll|he_enroll', ''],
    ['teachers', 'maestros|maestras|docentes|profesores', 'teachers|teaching staff', 'sch_teachers|sch_ptr', ''],
    ['universities', 'recintos|upr|universidad de puerto rico|instituciones postsecundarias', 'postsecondary|higher education institutions', 'he_inst|he_enroll', ''],
    ['dropout', 'desercion escolar|abandono escolar|desertores|no terminaron la escuela|sin cuarto ano|sin diploma', 'dropout*|drop out|high school dropouts', 'acs_no_hs_pct', '', { proxy: { es: 'no hay tasas de deserción escolar; muestro los adultos de 25 años o más sin diploma de escuela superior', en: 'there are no dropout rates; adults 25 and over without a high school diploma stand in' } }],
    ['private_schools', 'colegios|colegios privados|escuelas privadas', 'private schools', '', '', { missing: { es: 'el observatorio no tiene datos de colegios privados', en: 'the observatory has no private-school data' }, near: 'sch_open|sch_enroll' }],
    ['libraries', 'biblioteca|bibliotecas', 'library|libraries', 'libraries', 'lyLibraries'],
    // safety
    ['crime', 'crimen|criminalidad|delito*|delincuencia|inseguridad|seguridad|seguridad publica|que tan seguro|violencia|robos|robo|asaltos|criminal*', 'crime|crimes|criminality|safety|public safety|how safe|violence|robbery|robberies', 'crime_type1|crime_violent|crime_property|crime_murders', '', {}],
    ['property_crime', 'hurto*|escalamiento*|apropiacion ilegal|robo de carros|robos de carros|robo de autos|carros robados|vehiculos hurtados|delitos contra la propiedad', 'theft*|larceny|burglar*|car theft|vehicle theft|stolen cars|property crime*', 'crime_property|crime_type1', ''],
    ['shootings', 'tiroteo*|balacera*|disparos|armas de fuego|baleados|muertes violentas', 'shooting*|gun violence|gunfire|firearm*', 'crime_violent|crime_murders', '', { proxy: { es: 'no hay datos de tiroteos; muestro los delitos Tipo I violentos', en: 'there are no shooting data; violent Type I crimes stand in' } }],
    ['domestic_violence', 'violencia domestica|violencia de genero|maltrato|feminicidio*', 'domestic violence|gender violence|gender-based violence|femicide*', '', '', { missing: { es: 'no hay datos de violencia doméstica por municipio en el observatorio', en: 'the observatory has no domestic violence data by municipio' } }],
    // hazards and environment
    ['flood', 'inundacion*|inundable*|crecida*|desbordamiento*|riesgo de inundacion|zonas de inundacion', 'flood*|flooding|floodplain*|flood risk|flood zone*', 'exp_flood_sfha_pop|nri_eal_inland_flood|exp_flood_any_pop', 'lyFlood', { domain: 'hazards' }],
    ['sea_level', 'nivel del mar|aumento del mar|subida del mar|erosion costera|erosion|costa|costas|costero*|zona costera', 'sea level*|sea-level*|coastal flood*|coastal erosion|erosion|coast|coastal', 'exp_slr_3ft_pop|nri_eal_coastal_flood|exp_slr_1ft_pop', 'lySlr', { domain: 'hazards' }],
    ['storm_surge', 'marejada ciclonica|marejadas ciclonicas|marejada*|oleaje de tormenta', 'storm surge*', 'exp_surge_cat3_pop|exp_surge_cat5_pop|exp_surge_deep_cat3_pop|nri_eal_coastal_flood', '', { domain: 'hazards' }],
    ['hurricane', 'huracan|huracanes|tormenta*|ciclon*|vientos|huracan maria|huracan fiona|huracan irma|huracan georges|huracan hugo', 'hurricane*|storm*|cyclone*|wind', 'nri_eal_hurricane|fema_pa_obligated', 'lyStorms', { domain: 'hazards' }],
    ['earthquake', 'terremoto*|temblor*|sismo*|sismic*', 'earthquake*|quake*|seismic*|tremor*', 'quakes_m25|nri_eal_earthquake|quakes_m4', '', { domain: 'hazards' }],
    ['landslide', 'derrumbe*|deslizamiento*|deslave*|desprendimiento*', 'landslide*|mudslide*|slope failure*', 'landslides_maria|ls_res_high_pct|nri_eal_landslide|ls_land_high_pct', '', { domain: 'hazards' }],
    ['tsunami', 'tsunami*|maremoto*', 'tsunami*', 'nri_eal_tsunami', '', { domain: 'hazards' }],
    ['hazards', 'riesgos naturales|riesgo natural|desastres|desastres naturales|amenazas naturales|peligros naturales|riesgos|perdidas esperadas', 'natural hazards|hazards|disasters|natural disasters|disaster risk|risks|expected loss*', 'nri_eal_total|exp_flood_sfha_pop|ls_res_high_pct', 'lyFlood', { domain: 'hazards' }],
    ['resilience', 'resiliencia|vulnerabilidad|vulnerable*|factores de riesgo', 'resilience|vulnerability|vulnerable|risk factors', 'cre_risk3_pct|rvi_overall_rebuild', ''],
    ['wcrp', 'wcrp|programa de resiliencia comunitaria', 'wcrp', 'rvi_overall_rebuild|rvi_overall_orig', 'lyWcrp'],
    ['environment', 'medio ambiente|ambiente|ambiental*|naturaleza|ecologia|ecologic*|recursos naturales|conservacion', 'environment*|nature|ecolog*|natural resources|conservation', 'protected_land_pct|epa_npl|epa_tri|wetland_pct', 'lyProt', { domain: 'environment' }],
    ['pollution', 'contamina*|toxic*|polucion|quimicos|emisiones|sustancias toxicas', 'pollut*|toxic*|contamina*|emissions|chemicals', 'epa_tri|epa_npl|epa_rmp|epa_303d_pct', ''],
    ['water_quality', 'contaminacion del agua|agua contaminada|calidad del agua|rios contaminados|aguas contaminadas', 'water pollution|water quality|polluted water|contaminated water', 'epa_303d_pct|water_health_vio', ''],
    ['air', 'calidad del aire|contaminacion del aire|aire contaminado|smog|polvo del sahara', 'air quality|air pollution|polluted air|smog|saharan dust', 'epa_naa_so2_pct|epa_naa_lead_pct|epa_tri', '', { proxy: { es: 'no hay mediciones de calidad del aire por municipio; muestro las áreas de incumplimiento de la EPA (dióxido de azufre, plomo), que cubren pocos municipios', en: 'there are no air quality measurements by municipio; EPA non-attainment areas (sulfur dioxide, lead), which cover few municipios, stand in' } }],
    ['landfills', 'vertedero*|basura|desperdicios|reciclaje|relleno sanitario|rellenos sanitarios', 'landfill*|garbage|trash|recycling|dump*', 'epa_landfills_open|epa_landfills', ''],
    ['superfund', 'superfondo*', 'superfund*', 'epa_npl', ''],
    ['protected', 'areas protegidas|area protegida|parques|parque|bosque*|reserva|reservas|reservas naturales|el yunque|refugio de vida silvestre|parques nacionales|areas verdes|zonas verdes|espacios verdes', 'protected areas|parks|park|forest*|reserve*|nature reserve*|national park*|wildlife refuge*|green spaces|green areas', 'protected_land_pct|exp_protected_pop', 'lyProt', { domain: 'environment.land' }],
    ['beaches', 'playa|playas|balneario*|acceso a la playa|acceso a playas', 'beach|beaches|beach access', '', '', { missing: { es: 'el observatorio no tiene una capa de playas ni de su acceso (el buscador del mapa encuentra playas por nombre)', en: 'the observatory has no layer of beaches or of their access (the map search finds beaches by name)' }, related: 'lySlr', near: 'exp_slr_3ft_pop' }],
    ['mangroves', 'manglar|manglares|mangle|mangles', 'mangrove|mangroves', 'mangrove_km2|wetland_pct', ''],
    ['wetlands', 'humedal*|manglar*|cienaga*|estuario*', 'wetland*|mangrove*|marsh*|swamp*|estuar*', 'wetland_pct|mangrove_km2|wetland_km2', ''],
    ['land_use', 'uso de terrenos|usos de terrenos|uso del suelo|uso de suelo|zonificacion|calificacion|clasificacion del suelo|suelo urbano|suelo rustico|plan de uso de terrenos|terrenos agricolas|tierras agricolas|suelo agricola', 'land use|zoning|land classification|farmland|agricultural land', 'urban_pct|protected_land_pct', 'lyLanduse', { domain: 'environment.land' }],
    ['rural', 'rural|rurales|campo|el campo|zona rural|zonas rurales|la montana|zona montanosa|centro de la isla|jibaro*', 'rural|countryside|mountain towns|mountains', 'urban_pct|population', '', { proxy: { es: 'el observatorio no tiene una clasificación rural oficial; un % bajo de Suelo Urbano (Plan de Uso de Terrenos 2015) indica un municipio más rural', en: 'the observatory has no official rural classification; a low % of Suelo Urbano (2015 Land Use Plan) marks a more rural municipio' } }],
    ['urban', 'urbano|urbana|zona urbana|urbanizacion*|ciudades', 'urban|cities|urbanization|built-up', 'urban_pct', 'lyLanduse'],
    ['climate', 'cambio climatico|calentamiento global|clima', 'climate change|global warming|climate', 'exp_slr_3ft_pop|nri_eal_total', 'lySlr', { proxy: { es: 'el observatorio no tiene datos de clima ni de temperatura; muestro la exposición al aumento del nivel del mar (NOAA), uno de sus efectos medidos', en: 'the observatory has no climate or temperature data; exposure to sea level rise (NOAA), one of its measured effects, stands in' } }],
    ['heat', 'calor|temperatura*|islas de calor|ola de calor', 'heat|temperature*|heat island*|heat wave*', 'urban_pct', 'lyLanduse', { proxy: { es: 'no hay datos de temperatura; muestro el % de Suelo Urbano, porque las islas de calor se forman en zonas construidas (EPA)', en: 'there are no temperature data; % urban land stands in, because heat islands form in built-up areas (EPA)' } }],
    // infrastructure
    ['infrastructure', 'infraestructura*', 'infrastructure', 'bridges_poor_pct|water_health_vio|power_mw', 'lyHubs', { domain: 'infrastructure' }],
    ['water', 'agua|aguas|agua potable|acueducto*|aaa|autoridad de acueductos|prasa|sistemas de agua|servicio de agua', 'water|drinking water|water systems|water service|prasa|aqueduct*', 'water_health_vio|water_systems|water_nonprasa|water_nonprasa_pop', ''],
    ['water_outage', 'sin agua|interrupciones de agua|se va el agua|se fue el agua|cortes de agua|racionamiento', 'water outage*|water shut*|no water|water cuts', '', '', { missing: { es: 'el observatorio no tiene datos de interrupciones del servicio de agua', en: 'the observatory has no water service interruption data' }, near: 'water_health_vio|water_systems' }],
    ['power', 'luz|electricidad|electrica|energia|energia electrica|aee|prepa|luma|genera pr|plantas de energia|generacion|red electrica|sistema electrico', 'power|electricity|electric*|energy|grid|power plants|generation|luma|prepa', 'power_mw|power_plants|power_renewable_mw', ''],
    ['outages', 'apagon|apagones|se va la luz|se fue la luz|sin luz|cortes de luz|relevos de carga', 'outage*|blackout*|power cuts', '', '', { missing: { es: 'el observatorio no tiene datos de apagones', en: 'the observatory has no power outage data' }, near: 'power_mw|power_renewable_mw' }],
    ['power_price', 'factura de luz|factura de la luz|la factura|tarifa*|costo de la luz|luz cara|precio de la luz|precio de la electricidad|precio de la energia|costo de la electricidad|costo de la energia|cuanto cuesta la luz', 'electric bill*|power bill*|electricity bill*|electricity rate*|electricity price*|price of electricity|power price*|cost of electricity|energy cost*|energy price*|electricity cost*', '', '', { missing: { es: 'el observatorio no tiene datos de tarifas ni de facturas de luz', en: 'the observatory has no electricity rate or bill data' }, near: 'power_mw|power_plants' }],
    ['renewable', 'renovable*|solar|energia solar|eolica|molinos de viento|granjas solares|granja solar|parques solares|parque solar|fincas solares|plantas solares', 'renewable*|solar|wind power|solar farm*|solar plant*|solar park*', 'power_renewable_mw', ''],
    ['internet', 'wifi|wi-fi|conexion|conectividad|brecha digital', 'wifi|wi-fi|connectivity|digital divide', 'no_internet_pct|internet_subscription_pct', ''],
    ['computers', 'computadora*|computador|computadores|ordenador*|acceso a computadoras', 'computer*|laptop*|computer access', 'no_internet_pct|internet_subscription_pct', '', { proxy: { es: 'no hay datos de acceso a computadoras; muestro los hogares sin acceso a internet (ACS)', en: 'there are no computer access data; households with no internet access (ACS) stand in' } }],
    // communities and government
    ['special_communities', 'comunidades especiales|comunidad especial', 'special communities|comunidades especiales', '', 'lyComunidades'],
    ['shelters', 'refugio|refugios|albergue|albergues', 'shelter|shelters|emergency shelter*', '', '', { missing: { es: 'el observatorio no tiene la lista de refugios', en: 'the observatory has no list of shelters' }, related: 'lyFire|lyFlood' }],
    ['rooftop_solar', 'placas solares|paneles solares|techos solares|solar en los techos|placas en el techo|sistemas solares residenciales', 'rooftop solar|solar panels|home solar|residential solar|solar roofs', '', '', { missing: { es: 'el observatorio no tiene datos de placas solares en los techos (solo la capacidad de las plantas de generación)', en: 'the observatory has no rooftop solar data (only the capacity of power plants)' }, near: 'power_renewable_mw' }],
    ['er_wait', 'tiempo de espera|tiempos de espera|espera en emergencia|esperar en la sala', 'wait time*|waiting time*|er wait*|emergency room wait*', '', '', { missing: { es: 'el observatorio no tiene tiempos de espera en las salas de emergencia', en: 'the observatory has no emergency room wait times' }, near: 'cms_hospitals_er|hosp_drive_min' }],
    ['dentists', 'dentista*|odontolog*', 'dentist*|dental care', 'hpsa_dh_short|hpsa_dh_met', '', { proxy: { es: 'no hay un conteo de dentistas; muestro los dentistas que faltan en las áreas de escasez (HRSA)', en: 'there is no count of dentists; the dentists still needed in shortage areas (HRSA) stand in' } }],
    ['cargo', 'carga aerea|vuelos de carga|carga por avion|carga maritima|furgones', 'cargo flight*|air cargo|air freight|freight flight*|cargo', '', '', { missing: { es: 'el observatorio no tiene datos de carga aérea ni marítima', en: 'the observatory has no air or sea cargo data' }, near: 'air_departures|air_passengers' }],
    ['free_wifi', 'wifi gratis|wifi publico|internet gratis|internet publico|puntos de wifi|wifi gratuito', 'free wifi|public wifi|wifi hotspot*|free internet|hotspot*', '', '', { missing: { es: 'el observatorio no tiene la lista de puntos de wifi público', en: 'the observatory has no list of public wifi spots' }, near: 'no_internet_pct|internet_subscription_pct' }],
    ['for_sale', 'casas en venta|casas a la venta|viviendas en venta|propiedades en venta|casas para la venta|se venden casas', 'homes for sale|houses for sale|for sale|home listings|real estate listings', '', '', { missing: { es: 'el observatorio no tiene listados de casas en venta', en: 'the observatory has no listings of homes for sale' }, near: 'median_home_value|vacancy_pct' }],
    ['blue_tarps', 'toldo azul|toldos azules|techos azules|lonas azules', 'blue tarp*|blue roof*', '', '', { missing: { es: 'el observatorio no tiene datos de los toldos azules (techos temporeros después de María)', en: 'the observatory has no data on blue tarps (temporary roofs after María)' }, near: 'fema_ia_households|chas_severe_pct' }],
    ['news_media', 'medios de comunicacion|prensa|periodicos|noticias|emisoras|canales de television', 'news media|the media|mass media|media outlets|newspapers|news outlets|social media', '', '', { missing: { es: 'el observatorio no tiene datos de medios de comunicación', en: 'the observatory has no data on the news media' }, near: 'jobs_naics_51' }],
    ['occupancy', 'ocupacion hotelera|tasa de ocupacion|tasas de ocupacion|ocupacion de hoteles|ocupacion de los hoteles|porcentaje de ocupacion|hoteles llenos', 'hotel occupancy|occupancy rate*|occupancy', '', '', { missing: { es: 'el observatorio no tiene tasas de ocupación hotelera', en: 'the observatory has no hotel occupancy rates' }, near: 'accommodation_jobs|lodging_places' }],
    ['permits', 'permisos de construccion|permiso de construccion|permisos de uso|permisologia|permisos|ogpe', 'building permits|construction permits|permits|permitting', '', '', { missing: { es: 'el observatorio no tiene datos de permisos de construcción', en: 'the observatory has no building permit data' }, near: 'jobs_naics_23' }],
    ['crim', 'crim|tasacion|tasaciones|valor tasado|valores tasados|valor de tasacion|impuesto a la propiedad|impuesto sobre la propiedad|contribucion sobre la propiedad|contribuciones sobre la propiedad|catastro', 'assessed value*|property assessment*|property tax*|tax assessment*|cadastre|cadastral', 'median_home_value', '', { proxy: { es: 'no hay valores tasados del CRIM por municipio; muestro el valor mediano de la vivienda que declaran los dueños en la encuesta (ACS)', en: 'there are no CRIM assessed values by municipio; the median home value owners report in the survey (ACS) stands in' } }],
    ['trees', 'arboles|arbol|arbolado|arborizacion|cobertura arborea|cubierta forestal|dosel', 'trees|tree|tree canopy|tree cover|canopy|urban forest*', '', '', { missing: { es: 'el observatorio no tiene datos de árboles ni de cobertura arbórea', en: 'the observatory has no tree or tree canopy data' }, related: 'lyProt|lyLanduse', near: 'protected_land_pct|urban_pct' }],
    ['malls', 'centros comerciales|centro comercial|plazas comerciales|mall|malls', 'shopping malls|shopping mall|shopping centers|shopping centres|shopping center|malls|mall', '', '', { missing: { es: 'el observatorio no tiene una capa de centros comerciales (el buscador del mapa los encuentra por nombre)', en: 'the observatory has no layer of shopping malls (the map search finds them by name)' }, near: 'jobs_naics_44_45|qcew_estabs' }],
    ['critical_facilities', 'instalaciones criticas|facilidades criticas|infraestructura critica|servicios esenciales|instalaciones esenciales', 'critical facilities|critical infrastructure|essential facilities|essential services', 'fire_stations|police_stations|cms_hospitals', 'lyFire|lyPolice', { sens: 'count' }],
    ['food', 'supermercados|acceso a alimentos|desiertos alimentarios|inseguridad alimentaria|comida|alimentos', 'supermarkets|grocery stores|food access|food deserts|food insecurity|groceries', '', '', { missing: { es: 'el observatorio no tiene datos de acceso a alimentos ni de supermercados', en: 'the observatory has no data on food access or grocery stores' } }],
    ['cell_coverage', 'senal de celular|cobertura celular|senal movil|cobertura de celular', 'cell coverage|cell signal|mobile coverage|cell phone signal', '', '', { missing: { es: 'el observatorio no tiene datos de cobertura celular', en: 'the observatory has no cell coverage data' } }],
    ['drought', 'sequia|sequias', 'drought*', 'water_systems', '', { missing: { es: 'el observatorio no tiene datos de sequía', en: 'the observatory has no drought data' } }],
    ['wildfires', 'incendios forestales|fuegos forestales|incendios de pastos|quemas', 'wildfire*|brush fire*|forest fire*', '', '', { missing: { es: 'el observatorio no tiene datos de incendios forestales', en: 'the observatory has no wildfire data' }, related: 'lyFire' }],
    ['elections', 'elecciones|votos|votantes|electoral*|partidos politicos', 'election*|voting|voters|votes', '', '', { missing: { es: 'el observatorio no tiene datos electorales', en: 'the observatory has no election data' } }],
    ['worship', 'iglesias|templos|parroquias|lugares de culto', 'churches|places of worship|temples', '', '', { missing: { es: 'el observatorio no muestra lugares de culto', en: 'the observatory does not show places of worship' } }],
  ];
  const CONCEPTS = RAW.map(([id, es, en, data, layers, o = {}]) => ({ id, es: split(es), en: split(en), data: split(data), layers: split(layers), ...o, related: o.related ? split(o.related) : [], near: o.near ? split(o.near) : [] }));
  const CONCEPT = Object.fromEntries(CONCEPTS.map(c => [c.id, c]));

  // Everyday names of the map layers (core/layers.js holds their menu names, which are matched too). Layers marked 3d exist only on the 3D view.
  const LAYER_WORDS = {
    lyBarrios: ['barrios|barrio|limites de barrios|limites de los barrios|capa de barrios|division por barrios', 'barrios|barrio boundaries|neighborhood boundaries'],
    lyFlood: ['zonas inundables|zona inundable|zonas de inundacion|mapas de inundacion|mapa de inundacion|zonas de riesgo de inundacion|areas inundables|sfha', 'flood zones|flood zone|flood maps|flood map|flood hazard areas|sfha'],
    lySlr: ['aumento del nivel del mar|subida del nivel del mar|capa del mar', 'sea level rise|sea-level rise'],
    lyProt: ['areas protegidas|area protegida|reservas naturales|bosques estatales', 'protected areas|protected area|nature reserves'],
    lyLanduse: ['uso de terrenos|usos de terrenos|uso del suelo|uso de suelo|mapa de uso de terrenos|calificacion de terrenos|plan de uso de terrenos', 'land use|land-use|zoning map'],
    lyPubHousing: ['residenciales publicos|residenciales|residencial publico|caserios|vivienda publica|viviendas publicas', 'public housing|public housing developments|housing projects'],
    lyLihtc: ['vivienda con credito contributivo|proyectos de vivienda con credito contributivo|proyectos lihtc', 'tax credit housing|tax credit housing projects|lihtc projects'],
    lyRoutes: ['rutas|ruta|rutas de guagua|rutas de guaguas|rutas de transporte|lineas de guagua|lineas de autobus|rutas de autobus|rutas de la ama|recorridos|rutas de publicos|carros publicos|carro publico', 'routes|bus routes|transit routes|bus lines|transit lines|route map'],
    lyStops: ['paradas|parada|paradas de guagua|paradas de guaguas|paradas de autobus|paradas de transporte|garitas|garita', 'stops|bus stops|transit stops|bus stop'],
    lyHubs: ['estaciones|terminales|terminal|aeropuertos|aeropuerto|estaciones del tren|estaciones del tren urbano|terminal de lanchas|terminales de lanchas|muelles|muelle|centros de transbordo', 'stations|terminals|airports|airport|train stations|ferry terminals|transit hubs|hubs'],
    lyTaxi: ['taxis|taxi|paradas de taxi|paradas de taxis|carga de vehiculos electricos|cargadores|cargadores electricos|estaciones de carga|cargadores de carros electricos|carros electricos|vehiculos electricos', 'taxis|taxi|taxi stands|ev charging|ev chargers|charging stations|electric vehicle charging|electric cars|electric vehicles'],
    walkRings: ['radio de 400|400 metros|400 m|radio de 400 metros|distancia a pie|a pie de las paradas|radio a pie|caminar a la parada', '400 m|400 meters|400 metres|walk radius|walking radius|walking distance|walk to a stop'],
    lyFire: ['bomberos|estaciones de bomberos|cuartel de bomberos|parque de bombas|parques de bombas|emergencias medicas', 'fire stations|fire station|firehouses|fire department|ems|ems stations'],
    lyPolice: ['policia|policias|cuarteles|cuartel|cuarteles de la policia|comandancias|precintos', 'police|police stations|police station|precincts'],
    lyTownhalls: ['alcaldias|alcaldia|casas alcaldias|casa alcaldia|gobiernos municipales', 'city halls|city hall|town halls|town hall'],
    lyLibraries: ['bibliotecas|biblioteca', 'libraries|library'],
    lyHistoric: ['lugares historicos|sitios historicos|edificios historicos|patrimonio|monumentos|registro nacional', 'historic places|historic sites|historic buildings|national register|heritage|monuments|landmarks'],
    lyComunidades: ['comunidades especiales|comunidad especial', 'comunidades especiales|special communities'],
    lyWcrp: ['comunidades wcrp|comunidades del wcrp|wcrp', 'wcrp communities|wcrp'],
    lyPlaces: ['lugares turisticos|sitios turisticos|atracciones turisticas|puntos de interes|lugares de interes', 'tourism places|tourist places|points of interest|tourist spots|tourist attractions'],
    lyTerrain: ['terreno|relieve|topografia|montanas|elevacion|terreno en 3d', 'terrain|relief|topography|elevation'],
    lyBuildings: ['edificios|edificios en 3d|edificaciones|estructuras|alturas de los edificios', 'buildings|3d buildings|building heights|structures'],
    lyTrips: ['vehiculos con horario|vehiculos en movimiento|guaguas en movimiento|guaguas moviendose|movimiento de guaguas|simulacion|reproduccion de horarios|tiempo real|guaguas en vivo', 'scheduled vehicles|moving buses|buses moving|vehicles moving|live buses|real time|real-time|replay|simulation'],
    lySupRoutes: ['rutas por servicio|rutas por viajes|rutas por frecuencia|frecuencia de las rutas|frecuencia del servicio|servicio por hora|viajes por hora|cuantas guaguas pasan|cada cuanto pasa la guagua', 'routes by service|routes by trips|route frequency|service frequency|frequency of service|trips per hour|how often the bus comes'],
    lySupStops: ['paradas por salidas|paradas por frecuencia|salidas por hora|salidas de las paradas', 'stops by departures|departures per hour|stop frequency'],
    lyGaps: ['lejos del servicio|lejos de una parada|lejos de las paradas|sin servicio de transporte|zonas sin transporte|brechas de servicio|vacios de servicio|desiertos de transporte', 'far from service|service gaps|transit deserts|far from a stop|far from stops|no transit service'],
    lyXfer: ['puntos de integracion|transbordos|transbordo|conexiones entre rutas|puntos de transbordo|integracion del transporte', 'integration points|transfers|transfer points|connections between routes'],
    lyNow: ['vehiculos ahora|guaguas ahora|vehiculos en este momento|guaguas en este momento|vehiculos en su horario', 'vehicles now|buses now|vehicles right now|buses right now'],
    lyStorms: ['trayectorias de huracanes|trayectorias|huracanes desde 1851|tormentas historicas|rutas de huracanes|huracanes historicos|historia de huracanes', 'storm tracks|hurricane tracks|hurricane paths|historic hurricanes|past hurricanes'],
  };
  const ONLY_3D = new Set(['lyTerrain', 'lyBuildings', 'lyTrips', 'lyStorms', 'lyCols', 'lySupRoutes', 'lySupStops']), ONLY_2D = new Set(['lyNow']);
  // on the 2D map a request for a layer of the 3D view only goes to the 2D layer that shows the same thing (the vehicles on their timetable now, the routes); the 3D scene has none
  const IN_2D = { lyTrips: 'lyNow', lySupRoutes: 'lyRoutes', lySupStops: 'lyStops' };
  const SETTINGS_3D = new Set(['lyTerrain', 'lyBuildings']);   // the 3D scene: on when the page opens
  // the datasets a layer's answer offers next (chips): the measure that goes with what the layer draws
  const LAYER_DATA = { lyRoutes: ['pop_walk_active_pct', 'commute_transit_pct'], lyStops: ['pop_walk_active_pct', 'transit_stops'], walkRings: ['pop_walk_active_pct'], lyHubs: ['air_passengers', 'ferry_passengers'], lyFlood: ['exp_flood_sfha_pop', 'nri_eal_inland_flood'],
    lySlr: ['exp_slr_3ft_pop', 'nri_eal_coastal_flood'], lyProt: ['protected_land_pct', 'exp_protected_pop'], lyLanduse: ['urban_pct', 'protected_land_pct'], lyPubHousing: ['ph_units', 'ph_devs'], lyLihtc: ['lihtc_li_units', 'lihtc_projects'], lyFire: ['fire_stations'], lyPolice: ['police_stations', 'crime_type1'],
    lyLibraries: ['libraries'], lyHistoric: ['nrhp_places'], lyWcrp: ['rvi_overall_rebuild'], lyComunidades: ['poverty_pct'], lyPlaces: ['tourism_places'], lyStorms: ['nri_eal_hurricane', 'fema_pa_obligated'], lyTrips: ['pop_walk_active_pct'] };
  // the layers whose features are timetables, not live positions (the standing rule: label schedules)
  const SCHEDULE = new Set(['lyRoutes', 'lyStops', 'lyTrips', 'walkRings', 'lyNow', 'lySupRoutes', 'lySupStops', 'lyGaps', 'lyXfer']);

  // Well-known places that are not municipios: [municipio, lat, lon] (the point from the observatory's gazetteer, data/gazetteer.json), or [municipio] alone.
  const ALIASES = {
    'santurce': ['San Juan', 18.44666, -66.06868], 'hato rey': ['San Juan', 18.4221, -66.06571], 'rio piedras': ['San Juan', 18.39742, -66.05011], 'condado': ['San Juan', 18.45592, -66.07167], 'el condado': ['San Juan', 18.45592, -66.07167],
    'miramar': ['San Juan', 18.45469, -66.08351], 'ocean park': ['San Juan', 18.45179, -66.04867], 'viejo san juan': ['San Juan', 18.46618, -66.11643], 'san juan antiguo': ['San Juan', 18.46618, -66.11643], 'old san juan': ['San Juan', 18.46618, -66.11643],
    'puerta de tierra': ['San Juan', 18.46496, -66.09926], 'cupey': ['San Juan', 18.35273, -66.04579], 'barrio obrero': ['San Juan', 18.43766, -66.05303], 'villa palmeras': ['San Juan', 18.44534, -66.04969], 'la perla': ['San Juan', 18.46874, -66.11532],
    'el morro': ['San Juan', 18.47087, -66.12432], 'plaza las americas': ['San Juan', 18.42191, -66.07412], 'la capital': ['San Juan'], 'isla verde': ['Carolina', 18.44374, -66.0256], 'pinones': ['Loíza', 18.44642, -65.95829],
    'levittown': ['Toa Baja'], 'sabana seca': ['Toa Baja', 18.43603, -66.20038], 'isla de cabras': ['Toa Baja', 18.47078, -66.13628], 'isla nena': ['Vieques'], 'la isla nena': ['Vieques'], 'isabel segunda': ['Vieques', 18.14929, -65.44129],
    'culebrita': ['Culebra'], 'el yunque': ['Río Grande', 18.31069, -65.79138], 'yunque': ['Río Grande', 18.31069, -65.79138], 'la parguera': ['Lajas', 17.97762, -67.04845], 'parguera': ['Lajas', 17.97762, -67.04845], 'boqueron': ['Cabo Rojo', 18.02279, -67.16643],
    'guavate': ['Cayey', 18.13263, -66.07647], 'palmas del mar': ['Humacao', 18.08499, -65.80341], 'punta santiago': ['Humacao', 18.16466, -65.75464], 'las croabas': ['Fajardo', 18.36502, -65.62604], 'ramey': ['Aguadilla'],
    'cano martin pena': ['San Juan', 18.43727, -66.07222], 'martin pena': ['San Juan', 18.43958, -66.06141], 'aeropuerto luis munoz marin': ['Carolina', 18.4394, -66.00213], 'aeropuerto internacional luis munoz marin': ['Carolina', 18.4394, -66.00213],
    'luis munoz marin airport': ['Carolina', 18.4394, -66.00213], 'aeropuerto de isla verde': ['Carolina', 18.4394, -66.00213], 'sju': ['Carolina', 18.4394, -66.00213], 'el aeropuerto': ['Carolina', 18.4394, -66.00213, 'generic'], 'the airport': ['Carolina', 18.4394, -66.00213, 'generic'],
    'aeropuerto de aguadilla': ['Aguadilla', 18.49299, -67.12804], 'aeropuerto rafael hernandez': ['Aguadilla', 18.49299, -67.12804], 'aguadilla airport': ['Aguadilla', 18.49299, -67.12804], 'aeropuerto de ponce': ['Ponce', 18.00978, -66.56652], 'aeropuerto mercedita': ['Ponce', 18.00978, -66.56652],
    'mosquito bay': ['Vieques', 18.094, -65.44892], 'bahia bioluminiscente de vieques': ['Vieques', 18.094, -65.44892], 'cerro de punta': ['Jayuya', 18.17223, -66.59172], 'toro negro': ['Ciales', 18.22669, -66.53432], 'cavernas del rio camuy': ['Camuy', 18.34477, -66.82445], 'cuevas de camuy': ['Camuy', 18.34477, -66.82445],
    'isla de mona': ['Mayagüez', 18.09854, -67.89348], 'mona island': ['Mayagüez', 18.09854, -67.89348], 'caja de muertos': ['Ponce', 17.89362, -66.5195], 'cueva ventana': ['Arecibo', 18.37122, -66.69156], 'bosque seco de guanica': ['Guánica', 17.94362, -66.87078], 'bosque de guanica': ['Guánica', 17.94362, -66.87078],
    'punta tuna': ['Maunabo', 17.99496, -65.88211], 'bosque de carite': ['Guayama', 18.06677, -66.11663],
    'ciudad senorial': ['Ponce'], 'la ciudad senorial': ['Ponce'], 'la perla del sur': ['Ponce'], 'sultana del oeste': ['Mayagüez'], 'la sultana del oeste': ['Mayagüez'], 'ciudad criolla': ['Caguas'], 'ciudad del chicharron': ['Bayamón'], 'ciudad gigante': ['Carolina'],
  };
  // Events that people date things by: "después de María" is a time, not a topic.
  const EVENTS = [[/\b(?:huracan(?:es)?\s+|hurricane\s+)?(?:maria|irma)\b/, 2017], [/\b(?:huracan\s+|hurricane\s+)?fiona\b/, 2022], [/\b(?:huracan\s+|hurricane\s+)?georges\b/, 1998], [/\b(?:huracan\s+|hurricane\s+)?hugo\b/, 1989],
    [/\b(?:la\s+|the\s+)?(?:pandemia|pandemic|covid(?:-?19)?|coronavirus)\b/, 2020], [/\b(?:los\s+|the\s+)?(?:terremotos?|earthquakes?)\s+(?:de|del|of)\s+(?:2020|enero|january)\b/, 2020]];
  const EVENT_CUE = /\b(?:despues|antes|tras|desde|luego|after|before|since|post)\s+(?:de\s+|del\s+|la\s+|el\s+|los\s+|the\s+)*$/;

  // ── Patterns: the operation, a definition, what must not be drawn ──────────
  const TREND = /\b(?:subio|subido|sube|suben|ha subido|aumento|aumentado|aumenta|aumentan|disminu\w+|crecio|crecido|creciendo|cayo|caido|empeor\w*|mejor(?:o|ado)|evoluci\w*|cambiad[oa]|ha cambiado|han cambiado|a traves del tiempo|con los anos|en los ultimos|increas\w*|decreas\w*|rose|risen|rising|fell|fallen|falling|went (?:up|down)|gone (?:up|down)|grew|grown|growing|dropp\w*|declin\w*|got (?:worse|better)|over the years|over time|historia|(?:last|past) (?:decade|ten years|few years)|ultima decada|ultimos (?:diez|cinco) anos|decada pasada)\b|^(?:ha |han |se )?bajo\b|\b(?:ha|han|habia) bajado\b/;
  const EXPLAIN = /^(?:y\s+)?(?:que|qu[eé])\s+(?:es|son|significa|significan|quiere decir|mide)\s+|^(?:what|whats|what's)\s+(?:is|are|does)\s+|^(?:define|definicion de|definition of|meaning of|explica(?:me)?|explain)\s+|^(?:que|what)\s+(?:quiere decir|means?)\s+/;
  const STRONG_EXPLAIN = /^(?:y\s+)?que\s+(?:significa|significan|quiere decir)\b|^(?:define|definicion|definition|meaning)\b|\bmean\b|^what does\b/;
  const FRESH = /\b(?:actualizad\w*|al dia|que tan recientes?|ultimo dato|ultima actualizacion|ultimos datos|de que ano|how recent|up to date|up-to-date|last updated|latest data|how old|how current|fecha de los datos)\b/;
  const COUNT_DATA = /\b(?:cuantos (?:conjuntos de )?datos|cuantos conjuntos|cuantas capas|how many datasets|how many layers|numero de conjuntos)\b/;
  const SENS = {
    dv: [/\b(?:refugios?|albergues?|hogar(?:es)? seguros?|casas? seguras?|shelters?|safe ?houses?)\b/, /\b(?:violencia|maltrat\w*|abus\w*|victimas?|domestic\w*|genero|battered)\b/],
    drugs: /\bpuntos? de (?:venta de )?(?:droga|drogas)\b|\bdrug (?:spots?|points?|dealing|corners?|houses?)\b|\bbichot\w*/,
    pii: /\b(?:alcalde|alcaldesa|gobernador[a]?|senador\w*|representante\w*|legislador\w*|juez|jueza|presidente|mayor|governor|senator|representative|judge|famos[oa]s?|celebrit\w*|fulano|mi vecin[oa]|my neighbou?r)\b/,
    piiWhere: /\b(?:donde vive|donde reside|donde queda la casa|casa del?|direccion\w*|domicilio|telefono|numero de telefono|correo electronico|email|where does|lives?|home address|address|phone number|house of)\b/,
    locate: /\b(?:ubicaci\w*|direcci\w*|location\w*|address\w*|coordenadas|coordinates|exact\w*|exacta\w*|donde (?:estan|esta|quedan|queda)|where (?:are|is)|puntos de)\b/,
    facility: /\b(?:hospital\w*|clinica\w*|clinic\w*|centros? de salud|health cent\w*|cdts?|330|hrsa|metadona|methadone|tratamiento\w*|treatment|rehab\w*|dialisis|dialysis)\b/,
    homes: /\b(?:casas? privadas?|residencias? privadas?|private homes?|private houses?|private residences?|viviendas? privadas?)\b/,
    // the names of people, where people with a condition live, home addresses, who received aid, the names of care homes, short-term rental addresses, "near me"
    names: /\b(?:nombres?|lista|listado|names?|list of|roster)\s+(?:de\s+|of\s+)?(?:los\s+|las\s+|the\s+|all\s+)?(?:estudiantes|alumnos|pacientes|residentes|beneficiarios|participantes|personas|ninos|ninas|vecinos|empleados|trabajadores|maestros|donantes|victimas|inquilinos|students|pupils|patients|residents|beneficiaries|participants|people|children|kids|neighbou?rs|employees|workers|teachers|donors|victims|tenants)\b|\b(?:who are|quienes son)\s+(?:the\s+|los\s+|las\s+)?(?:patients|pacientes|students|estudiantes|residents|residentes|beneficiaries|beneficiarios|victims|victimas)\b/,
    healthPerson: /\b(?:where|donde)\s+(?:do|does)\s+(?:the\s+)?(?:people|persons|patients|those|folks|residents)\s+(?:with|who have|that have)\s+(?:[a-z]+\s+){0,2}?(?:diabetes|cancer|hiv|aids|asthma|covid\w*|dengue|diseases?|illness\w*|conditions?|addictions?|depression|schizophrenia|alzheimer\w*|dementia|tuberculosis|hepatitis|autism)\b|\b(?:donde|where)\s+(?:viven|vive|estan|esta|live|lives|are|is)\s+(?:las\s+|los\s+|the\s+)?(?:personas\s+|gente\s+|pacientes\s+|people\s+|patients\s+|those\s+|persons\s+)?(?:con|with|que tienen|que padecen|who have|that have)\s+(?:[a-z]+\s+){0,2}?(?:diabetes|cancer|vih|sida|hiv|aids|asma|asthma|covid\w*|dengue|enfermedad\w*|diseases?|illness\w*|condicion\w*|conditions?|adiccion\w*|addictions?|depresion|depression|esquizofrenia|schizophrenia|alzheimer\w*|demencia|dementia|tuberculosis|hepatitis|autismo|autism)\b|\b(?:quien|quienes|who)\s+(?:tiene|tienen|has|have)\s+(?:diabetes|cancer|vih|sida|hiv|aids|covid\w*|dengue)\b/,
    addresses: /\b(?:direcciones?|domicilios?|addresses?)\s+(?:de\s+|of\s+)?(?:las\s+|los\s+|the\s+)?(?:casas|hogares|viviendas|residencias|residentes|personas|familias|homes|houses|households|residences|residents|people|families)\b|\bhome addresses?\b|\bdirecciones residenciales\b|\bresidential addresses?\b/,
    aid: /\b(?:casas|hogares|familias|personas|quien|quienes|cuales|que hogares|homes|houses|households|families|people|who|which)\s+(?:[a-z]+\s+){0,2}?(?:recibieron|recibio|recibe|reciben|obtuvieron|received|receive|receives|got|get|gets)\s+(?:[a-z]+\s+){0,3}?(?:ayuda|asistencia|fema|subsidios?|cupones|pan|beneficios|aid|assistance|help|subsid\w*|benefits|food stamps|snap)\b/,
    careNames: /\b(?:nombres?|lista|listado|names?|list of)\s+(?:de\s+|of\s+)?(?:los\s+|las\s+|the\s+|all\s+)?(?:hogares de (?:ancianos|envejecientes|cuido)|egidas|asilos?|centros de cuido|nursing homes?|care homes?|assisted living|group homes?|hogares de grupo)\b/,
    rentals: /\b(?:direcciones?|ubicaci\w*|donde (?:estan|quedan)|addresses?|locations?|where are)\s+(?:de\s+|of\s+)?(?:los\s+|las\s+|the\s+)?(?:alquileres? (?:a|de) corto plazo|alquileres? vacacionales?|airbnbs?|short[- ]term rentals?|vacation rentals?)\b|\b(?:airbnbs?|short[- ]term rentals?|alquileres? a corto plazo)\s+(?:addresses?|locations?|direcciones?|ubicaci\w*)\b/,
    nearMe: /\b(?:cerca de mi|cerca de donde (?:estoy|vivo)|cercan[oa]s? a mi|mas cercan[oa]s? a mi|near me|nearest to me|closest to me|around me|near my (?:home|house)|cerca de mi casa)\b/,
    // what reads like a crisis word but is not (review of PR #95): a highway numbered 988, people dying in a disaster. Any "no quiero vivir" stays a crisis: over-triggering is the safe side
    notCrisis: /\b(?:pr|carr|carretera|ruta|road|route|highway|hwy)[- ]?988\b|\bgoing to die (?:in|from|of|during|because of) (?:the |a |an )?(?:flood|hurricane|storm|earthquake|tsunami|heat|fire|landslide|disaster|accident|crash|inundaci|huracan|terremoto|tormenta)\w*/g,
    crisis: /\b(?:suicid\w*|(?:se |me |te )?quit\w* la vida|matarse|matarme|autolesi\w*|auto-lesi\w*|hacerse dano|hacerme dano|self[- ]?harm\w*|kill (?:myself|themselves|himself|herself|oneself)|killing (?:myself|themselves)|end (?:my|their|his|her) life|took (?:his|her|their) (?:own )?life|sobredosis|overdos\w*|muertes por drogas|drug deaths|(?:me )?(?:quiero|quisiera|deseo|voy a|pienso|tengo ganas de) (?:morir(?:me)?|matarme|suicidarme)|me (?:quiero|voy a|pienso) (?:morir|matar|suicidar)|ganas de morir(?:me)?|no (?:quiero|deseo) (?:seguir )?vivir|no quiero seguir viviendo|(?:lastimarme|hacerme dano|cortarme las venas)|(?:i )?(?:want|wanna|going) to die|(?:want|going|plan|planning) to (?:kill|hurt|harm) myself|(?:hurt|harm|cut)(?:ing)? myself|(?:don'?t|do not) want to (?:live|be alive)|better off dead|no reason to live|end it all|linea pas|988)\b/,
    foster: /\b(?:hogares? de crianza|hogares? sustitutos?|familias? de crianza|hogares? temporeros? para menores|albergues? (?:de|para) menores|refugios? (?:de|para) menores|hogares? (?:de|para) menores|hogares? de ninos|foster (?:homes?|care|families)|youth shelters?|children'?s shelters?|shelters? for (?:minors|children|kids))\b/,
    namedHome: /\b(?:hogar(?:es)? crea|teen challenge|hogar(?:es)? de rehabilitacion|hogar(?:es)? de recuperacion|casas? de recuperacion|sober (?:homes?|houses?)|halfway houses?)\b/,
    homebound: /\b(?:encamad[oa]s?|postrad[oa]s?|confinad[oa]s? en (?:su |sus )?casas?|que no salen de (?:su )?casa|homebound|bedridden|house-?bound)\b/,
    origin: /\b(?:dominican[oa]s|cuban[oa]s|haitian[oa]s|venezolan[oa]s|colombian[oa]s|mexican[oa]s|chin[oa]s|inmigrantes|extranjeros|indocumentados|dominicans|cubans|haitians|venezuelans|colombians|mexicans|immigrants|foreigners|undocumented)\b/,
    officials: /^(?=[\s\S]*\b(?:alcalde\w*|gobernador\w*|legislador\w*|senador\w*|representante\w*|mayor|governor|legislators?|senators?|politic[oa]s?|politicians?)\b)(?=[\s\S]*\b(?:trabajo|desempeno|gestion|bueno|buena|malo|mala|corrupt\w*|aprueba\w*|aprobacion|eficiente|ineficiente|performance|doing|job|good|bad|rating|approval|effective|competent|lo esta haciendo)\b)/,
    // round 4: abortion services (counted, never listed); the hosts or owners of short-term rentals; the owners, names or addresses of abandoned or vacant homes; where aid recipients live
    abortion: /\b(?:abort\w*|interrupcion(?:es)? (?:voluntaria(?:s)? )?del embarazo|terminacion del embarazo|pregnancy terminations?|terminations? of pregnancy)\b/,
    rentalHosts: /^(?=[\s\S]*\b(?:anfitrion\w*|hosts?|duen[oa]s?|propietari[oa]s?|owners?|landlords?|quien\w* (?:alquila\w*|renta\w*)|who (?:rents?|runs?|owns?)|operador\w*|operators?|direcci\w*|address\w*|ubicaci\w*|locations?|mapa de|map of|lista|list)\b)(?=[\s\S]*\b(?:airbnbs?|vrbo|alquileres? (?:a|de) corto plazo|alquileres? vacacionales?|short[- ]term rentals?|vacation rentals?|rentas? (?:a|de) corto plazo)\b)/,
    vacant: /^(?=[\s\S]*\b(?:duen[oa]s?|propietari[oa]s?|nombres? de (?:los|las|sus) (?:duen|propietari)\w*|direcci\w*|owners?|owns?|owned|names? of (?:the |their )?owners?|addresses?|de quien|whose|titulares?)\b)(?=[\s\S]*\b(?:abandon\w*|vacia\w*|desocupad\w*|vacant\w*|empty (?:homes?|houses?|properties)|estorbos?|derelict|deshabitad\w*|en ruinas)\b)/,
    aidWho: /\b(?:donde (?:viven|vive|estan|esta|quedan)|where (?:do|does|are|is)\b[\s\S]{0,40}\b(?:live|living|located)|casas?|hogares?|viviendas?|familias?|homes?|houses?|households?|direcci\w*|address\w*|nombres?|names?|lista|list|quien\w*|who|which (?:homes|households|families|people))\b/,
    aidWhat: /\b(?:cupones|pan|snap|wic|food stamps?|welfare|mantengo|beneficencia|asistencia (?:nutricional|economica|publica|social)|ayudas? (?:del gobierno|federal\w*|de fema)|fema|beneficios|benefits|subsidi\w*|seccion 8|section 8|vales|tanf|ayuda economica|public assistance|aid)\b/,
    aidGet: /\b(?:recib\w*|receiv\w*|recipients?|beneficiari\w*|get|gets|got|getting|obtuv\w*|cobran?|on (?:welfare|food stamps|snap|wic|benefits)|en (?:el )?(?:pan|mantengo|cupones)|que tienen (?:el )?(?:pan|cupones|wic|seccion 8)|con (?:el )?(?:pan|cupones|wic|seccion 8|mantengo)|with (?:food stamps|snap|section 8|welfare))\b/,
    aggregate: /\b(?:cuant[oa]s|how many|mas|menos|most|least|more|fewer|municipios?|pueblos?|towns?|municipalit\w*|ciudades|cities|porcentaje|percent\w*|share|proporcion|tasa|rate|por municipio|by municipio|by municipality|totales|numero de|number of)\b/,
    aidFood: /\b(?:cupones|pan|snap|wic|food stamps?|welfare|mantengo|beneficencia|asistencia (?:nutricional|economica|publica|social)|tanf|ayuda economica|seccion 8|section 8|vales)\b/,
    treatment: /\b(?:tratamiento\w*|rehab\w*|metadona|methadone|treatment|detox|desintoxicacion|drogas?|drugs?|adiccion\w*|addiction\w*|mental|psicolog\w*|psiquiatr\w*|therap\w*|terapia\w*)\b/,
  };
  // the kinds that are answered by their reason (and a count by area when there is one), never by a map of points or a list
  const PRIVATE = new Set(['dv', 'drugs', 'pii', 'abortion', 'vacant', 'names', 'healthPerson', 'addresses', 'aid', 'careNames', 'rentals', 'nearMe', 'nearMeTx', 'foster', 'namedHome', 'homebound', 'origin']);
  // crime in a place smaller than a municipio ("los residenciales con más crimen", "the safest barrio of Ponce"): the crime counts are published by municipio only
  const CRIME_SITE = /^(?=[\s\S]*\b(?:crimen\w*|criminal\w*|delitos?|delincuencia|asesinatos?|homicidios?|robos?|tiroteos?|balaceras?|insegur\w*|peligros[oa]s?|crimes?|murders?|homicides?|robber\w*|shootings?|safest|dangerous|unsafe)\b)(?=[\s\S]*\b(?:residencial\w*|caserios?|public housing|housing projects?|barrios?|urbanizaci\w*|vecindario\w*|calles?|neighbou?rhoods?|streets?|cuadras?)\b)/;
  // Qualifiers a dataset may not carry ("la velocidad del internet", "por mes"): when the dataset shown lacks it, the answer says it is an approximation. ok: what in
  // the dataset's meta carries the qualifier (null: no dataset of the observatory does).
  const QUALS = [
    { id: 'speed', re: /\b(?:velocidad\w*|rapidez|mbps|megas|speeds?)\b/, ok: (m) => /speed|velocidad|mbps/i.test(m.label || ''), what: { es: 'la velocidad', en: 'speed' } },
    { id: 'month', re: /\b(?:mensual\w*|por mes|por meses|cada mes|al mes|mes a mes|monthly|per month|by month|each month|month by month|enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|setiembre|octubre|noviembre|diciembre|january|february|march|april|june|july|august|september|october|november|december)\b/, ok: null, what: { es: 'las cifras por mes', en: 'monthly figures' } },
    { id: 'price', re: /\b(?:precios?|tarifas?|prices?|pricing|tariffs?)\b/, ok: (m) => m.unit === '$', what: { es: 'el precio', en: 'the price' } },
  ];
  const RELATE = /\b(?:relaci\w*|relacion\w*|correlac\w*|correlat\w*|compar\w*|versus|vs|contra|frente a|against|together|juntos?|related|relate|asocia\w*|associat\w*)\b/;
  const DENSITY = /\b(?:con|with)\s+(?:mas|menos|more|less|fewer)\b.*\b(?:tienen|tiene|have|has|hay)\s+(?:mas|menos|more|less|fewer)\b/;   // "los pueblos con más viejos tienen más pobreza": two things related across places
  const COORD = /^\s*(?:[,;:&+/]\s*(?:(?:y|e|and)\s+)?|(?:y|e|and|plus|junto (?:a|con)|ademas de|as well as|along with|o|or|u)\s+)(?:(?:el|la|los|las|the|de|del|of|sus|su)\s+)*$/;   // the words between two topics of a list: a comma or a connector, then articles ("transporte y vivienda", "pobreza, desempleo y crimen", "poverty and flood risk"); two words side by side are one phrase
  const COORD_REL = /^\s*(?:con|with|vs\.?|versus|contra|against|frente a)\s+(?:(?:el|la|los|las|the|de|del|of|sus|su)\s+)*$/;   // and, in a question that relates things, "con", "with", "versus" ("compara el acceso a transporte con la carga de alquiler"); elsewhere "with" names a group ("people with disabilities")
  const LISTED = /^(?:y|e|and|o|or|u|vs|versus|con|with)$/;
  const PLACING = /^(?:en|in|de|of|para|desde|from|at|cerca|near)$/;   // a word that places what follows ("en ponse", "in bayamom")   // a word in a list of topics (a typo there is read even when the rest of the question is understood)

  // ── The index ────────────────────────────────────────────────────────────────
  /** One index over what Ask can show.
      src: { datasets: [{ key, label, labelEs, group, groupEs, dictId, last }], ask: { dictId: { en: [], es: [] } }, words: { dictId: 'spanish summary words' }, layers: registry rows ({ id, en, es, src, views }),
             metrics: [[value, label]] (the 3D view's own column measures), glossary: [[id, forms]] (both languages), places: [municipio names], view: '2d' | '3d' } */
  function build(src) {
    const view = src.view || '2d';
    const phrases = [];   // { kind: 'concept' | 'layer' | 'place' | 'glossary', id, words: [..], lang }
    const add = (kind, id, text, lang, extra) => { const ws = nrm(text).split(/[\s/]+/).map(w => w.replace(/[^a-z0-9*-]/g, '').replace(/^-+|-+$/g, '')).filter(w => w && w !== '*'); if (ws.length) phrases.push({ kind, id, words: ws, lang, ...(extra || {}) }); };   // a final '*' (a prefix) is kept
    for (const c of CONCEPTS) { c.es.forEach(p => add('concept', c.id, p, 'es')); c.en.forEach(p => add('concept', c.id, p, 'en')); }
    const rows = src.layers || [];
    const layerOk = (id) => view === '3d' ? !ONLY_2D.has(id) : !ONLY_3D.has(id);
    for (const [id0, [es, en]] of Object.entries(LAYER_WORDS)) { const id = view === '2d' && IN_2D[id0] ? IN_2D[id0] : id0; if (!layerOk(id)) continue; split(es).forEach(p => add('layer', id, p, 'es')); split(en).forEach(p => add('layer', id, p, 'en')); }
    for (const r of rows) { if (!r.id || !/^ly|^walkRings$/.test(r.id) || !layerOk(r.id)) continue; if (r.es) add('layer', r.id, r.es, 'es', { name: true }); if (r.en) add('layer', r.id, r.en, 'en', { name: true }); }
    for (const [a, v] of Object.entries(ALIASES)) add('place', a, a, null, { muni: v[0], lat: v[1], lon: v[2], generic: v[3] === 'generic' });
    // on the map page, the 3D view's own layers by their everyday names ("elevación", "edificios en 3D"): the answer says where they are
    if (view === '2d') for (const [id, [es, en]] of Object.entries(LAYER_WORDS)) if (ONLY_3D.has(id) && !IN_2D[id]) { split(es).forEach(p => add('layer3d', id, p, 'es')); split(en).forEach(p => add('layer3d', id, p, 'en')); }
    for (const [id, forms] of src.glossary || []) for (const f of forms || []) if (f && f[0] !== '!') add('glossary', id, f, null);
    // the datasets: their words, for what the lexicon does not name (a dataset is askable by its own name, in either language)
    const docs = [], df = new Map();
    for (const d of src.datasets || []) {
      const label = new Set(), group = new Set(), extra = new Set(), words = new Set();   // words: the label's words as written (a stem of four letters or fewer is read only as written: "calls" is not "calles")
      for (const s of [d.label, d.labelEs]) toks(nrm(s || '')).forEach(t => { if (t.w.length > 2 && !STOPW.has(t.w)) { label.add(stem(t.w)); words.add(t.w); } });
      for (const s of [d.group, d.groupEs]) toks(nrm(s || '')).forEach(t => { if (t.w.length > 2 && !STOPW.has(t.w)) group.add(stem(t.w)); });
      const a = (src.ask || {})[d.dictId]; if (a) [...(a.en || []), ...(a.es || [])].forEach(p => toks(nrm(p)).forEach(t => { if (t.w.length > 2 && !STOPW.has(t.w)) { label.add(stem(t.w)); words.add(t.w); } }));
      const w = (src.words || {})[d.dictId]; if (w) toks(nrm(w)).forEach(t => { if (t.w.length > 3 && !STOPW.has(t.w)) extra.add(stem(t.w)); });
      const doc = { key: d.key, label, group, extra, words, last: !!d.last, year: d.last || 0 };
      docs.push(doc);
      for (const s of new Set([...label, ...group])) df.set(s, (df.get(s) || 0) + 1);
    }
    const metrics = (src.metrics || []).map(([value, label]) => ({ value, label, words: new Set(toks(nrm(label)).filter(t => t.w.length > 2 && !STOPW.has(t.w)).map(t => stem(t.w))) }));
    // the vocabulary a typo is corrected to: the words of the lexicon, the layers and the places, the words of the datasets' names (both languages) and of
    // their Spanish summaries, and the glossary's terms. A word is never corrected to one with another first letter.
    const vocab = new Map(), alarm = new Set(), safe = new Set(), addV = (w, kind, lang = null, bad = false) => {   // a prefix ("inundacion*") with its plurals; lang null: a word of both languages
      const pre = /\*$/.test(w); w = w.replace(/\*$/, '');
      for (const x of pre ? [w, w + 's', w + 'es'] : [w]) { if (x.length < 4 || STOPW.has(x)) continue; (bad ? alarm : safe).add(x); const v = vocab.get(x); if (!v) vocab.set(x, { kind, lang }); else if (v.lang !== lang) v.lang = null; }
    };
    for (const p of phrases) if (p.kind !== 'glossary') for (const w of p.words) addV(w, p.kind, p.lang || null, p.kind === 'concept' && ALARM.has(p.id));
    TOPIC_WORDS.forEach(w => addV(w, 'rule', null, ALARM_WORDS.has(w)));
    const munis = (src.places || []).map(name => ({ name, n: nrm(name) }));
    for (const m of munis) for (const w of m.n.split(/\s+/)) addV(w, 'muni');
    safe.forEach(w => alarm.delete(w));   // a word of an alarm topic that another topic also uses ("hospitales" of "hospitales con emergencia") is not one
    // the words the observatory's own texts use (dataset names and definitions, the Spanish summaries, the glossary): real words, never read as typos
    const real = new Set();
    for (const d of src.datasets || []) for (const s of [d.label, d.labelEs, d.group, d.groupEs, d.definition]) toks(nrm(s || '')).forEach(t => real.add(t.w));
    for (const w of Object.values(src.words || {})) toks(nrm(w)).forEach(t => real.add(t.w));
    for (const p of phrases) if (p.kind === 'glossary') p.words.forEach(w => real.add(w));
    const stems = new Set([...vocab.keys()].map(stem));
    phrases.sort((p, q) => q.words.length - p.words.length || (p.kind === 'layer' ? -1 : 0) - (q.kind === 'layer' ? -1 : 0));
    return { view, phrases, docs, df, n: docs.length || 1, metrics, vocab, alarm, stems, real, munis, glossaryForms: src.glossary || [], VERSION };
  }

  // ── Understanding a question ────────────────────────────────────────────────
  function wordMatch(pw, t, strict) {   // strict: the phrase is of the other language than the question: its word as written, or a prefix
    if (pw.endsWith('*')) { const p = pw.slice(0, -1); return t.startsWith(p) && t.length - p.length <= 8 && !STOPW.has(t); }
    if (t === pw) return true;
    if (strict || STOPW.has(t) || t.length < 5 || pw.length < 5) return false;
    const s = stem(t); return s.length >= 5 && s === stem(pw);
  }
  /** The best correction of a word that is not in the vocabulary: words of six letters or more, one edit up to nine letters and two from ten, with the same first
      letter and one best word; null when there is none, when two different words tie, when the word is real (PROTECTED, the observatory's own words, a form of a
      known one: "escuelas" for "escuela") or when the best word names an alarm topic. o.muni: a municipio or a place may be the correction (after a word that
      places, or as the whole question); o.lang: the question's language (a word of the other language only is not a correction). */
  function correct(w, ix, o = {}) {
    if (w.length < 6 || /\d/.test(w) || STOPW.has(w) || KNOWN.has(w) || ix.vocab.has(w) || (ix.real && ix.real.has(w)) || (!ix.noProtect && PROTECTED.has(w))) return null;
    const sw = stem(w); if (ix.stems.has(sw)) return null;
    const max = w.length >= 10 ? 2 : 1;
    let best = null, bd = max + 1, tie = false;
    for (const [v, x] of ix.vocab) {
      if (v[0] !== w[0] || Math.abs(v.length - w.length) > max || v.length < 5) continue;
      if (!o.muni && (x.kind === 'muni' || x.kind === 'place')) continue;
      if (o.lang && x.lang && x.lang !== o.lang) continue;
      const d = dl(w, v, max);
      if (d < bd) { bd = d; best = v; tie = false; } else if (d === bd && best && stem(best) !== stem(v)) tie = true;
    }
    return best && bd <= max && !tie && !ix.alarm.has(best) ? best : null;
  }
  /** The question with its typos corrected, word by word, in the text as written (accents and capitals of the other words kept): { text, fixes: [[as written, read as]] }.
      chat.js parses the corrected text, so its rules and its list of municipios read "pobresa en mayaguez" as "pobreza en mayaguez". */
  function fix(q, ix, o = {}) {   // o.listed: only the words in a list of topics ("pobreza y desempelo"): the rest of the question was understood, so its other words are real
    const fixes = [], words = [...String(q || '').matchAll(/[A-Za-zÀ-ÿ0-9]+(?:-[A-Za-zÀ-ÿ0-9]+)*/g)];
    if (words.length > 8) return { text: String(q || ''), fixes };   // a typo is read in a short question; a long sentence that names nothing the observatory has is not a misspelt topic
    const lang = langOf(nrm(q)), all = words.map(m => nrm(m[0]));
    let text = '', at = 0;
    words.forEach((m, i) => {
      const word = m[0], w = nrm(word), prev = i > 0 ? nrm(words[i - 1][0]) : '', next = i + 1 < words.length ? nrm(words[i + 1][0]) : '';
      const sep = (j) => j > 0 && j < words.length && /,/.test(q.slice(words[j - 1].index + words[j - 1][0].length, words[j].index));
      const listed = LISTED.test(prev) || LISTED.test(next) || sep(i) || sep(i + 1);
      let c = o.listed && !listed ? null : correct(w, ix, { muni: PLACING.test(prev), lang });
      if (!c && !o.listed && words.length <= 3) {   // a municipio as the whole question ("bayamom", "san germam"): the corrected question is its name
        const c2 = correct(w, ix, { muni: true, lang }), whole = c2 && all.map((x, j) => j === i ? c2 : x).join(' ');
        if (c2 && ix.munis.some(x => x.n === whole)) c = c2;
      }
      text += q.slice(at, m.index) + (c || word); at = m.index + word.length;
      if (c) fixes.push([word, c]);
    });
    return { text: text + String(q || '').slice(at), fixes };
  }
  /**
   * n: the question as chParse normalises it; o: { rest (chParse's question with what its rules and the places took blanked), lang, places (municipios chParse found) }.
   * Returns { tokens, hits: [{ kind, id, a, b, words, fuzzy, covered }], concepts, layers, places, dataset (from the index), metric, time: { since, until, years }, trend,
   *           explain: { target, glossary, layer } | null, sens: [{ kind }], fresh, countData, showVerb, relate, unknown: [words] }.
   */
  function understand(n, ix, o = {}) {
    const rest = o.rest == null ? n : o.rest;
    const T = toks(n);
    T.forEach(t => { t.taken = !/\S/.test(rest.slice(t.a, t.b)); t.c = t.w; });   // taken: a rule of chParse (or a municipio) has it
    // time: the events people date things by, with their cue ("después de María")
    const time = { since: null, until: null };
    for (const [re, y] of EVENTS) {
      const g = new RegExp(re.source, 'g'); let m;
      while ((m = g.exec(n))) {
        const cue = EVENT_CUE.exec(n.slice(0, m.index));
        if (!cue) continue;   // "después de María", "since the pandemic": a time only with its cue ("poverty overlapping with the pandemic" is not one)
        const before = cue && /\b(?:antes|before)\b/.test(cue[0]);
        if (before) time.until = y; else time.since = y;
        T.forEach(t => { if (t.a >= (cue ? cue.index : m.index) && t.b <= m.index + m[0].length) t.time = true; });
      }
    }
    // phrases, longest first; a word is used once
    const hits = [], lang = langOf(n), placeAt = new Set();
    for (const p of ix.phrases) {
      if (p.kind !== 'place') continue;   // well-known places first, without taking their words: a topic may read them too
      for (let i = 0; i <= T.length - p.words.length; i++) {
        const ts = T.slice(i, i + p.words.length);
        if (ts.some((t, k) => placeAt.has(i + k) || t.time || t.c !== p.words[k])) continue;
        ts.forEach((t, k) => placeAt.add(i + k));
        hits.push({ kind: 'place', id: p.id, a: ts[0].a, b: ts[ts.length - 1].b, words: ts.map(t => t.w), covered: ts.every(t => t.taken), partly: ts.some(t => t.taken), lang: null, extra: p });
      }
    }
    for (const p of ix.phrases) {
      if (p.kind === 'place') continue;
      const strict = !!(lang && p.lang && p.lang !== lang);   // "911 calls" is not "calles", "parking" is not "parques"
      for (let i = 0; i < T.length; i++) {
        if (T[i].used || T[i].time || !wordMatch(p.words[0], T[i].c, strict)) continue;
        const at = [i]; let j = i + 1, skips = 0;
        for (let k = 1; k < p.words.length && j < T.length; ) {
          if (!T[j].used && wordMatch(p.words[k], T[j].c, strict)) { at.push(j); k++; j++; skips = 0; continue; }
          if (STOPW.has(T[j].w) && skips < 2 && !T[j].used) { j++; skips++; continue; }
          break;
        }
        if (at.length !== p.words.length) continue;
        const ts = at.map(x => T[x]);
        if (p.kind === 'glossary' && !o.explain) continue;
        ts.forEach(t => { t.used = true; });
        hits.push({ kind: p.kind, id: p.id, a: ts[0].a, b: ts[ts.length - 1].b, words: ts.map(t => t.w), covered: ts.every(t => t.taken), partly: ts.some(t => t.taken), lang: p.lang, name: !!p.name, extra: p });
      }
    }
    hits.sort((p, q) => p.a - q.a);
    // municipios that chParse did not find: one edit away ("ponse", "bayamom")
    const places = [];
    for (const h of hits.filter(x => x.kind === 'place')) if (!(h.extra.generic && (o.places || []).length)) places.push({ muni: h.extra.muni, name: h.words.join(' '), lat: h.extra.lat, lon: h.extra.lon, a: h.a, b: h.b, alias: true, generic: h.extra.generic });   // "el aeropuerto" is Luis Muñoz Marín unless a municipio is named
    if (!(o.places || []).length && !places.length) {   // after a word that places ("en ponse", "in bayamom", "de Toa Vaja") or as the last words of a question with a topic ("poverty Aguadila"); never a real word ("la cifra" is not Cidra, Guayabal is not Guayama)
      const free = (t) => t && !t.used && !t.taken && !t.time && !STOPW.has(t.w) && !KNOWN.has(t.w);
      const first = new Set(ix.munis.filter(m => m.n.includes(' ')).map(m => m.n.split(' ')[0]));   // "las", "toa", "san": the first word of a two-word municipio, even a stop word ("Las Pierdas")
      const free2 = (ts) => ts.every((t, k) => free(t) || (ts.length === 2 && t && !t.used && !t.taken && first.has(ts[0].w)));   // and the word after it may be a word of time or a known word ("Juana Dias")
      for (let i = 0; i < T.length && !places.length; i++) for (const len of [2, 1]) {
        const ts = T.slice(i, i + len); if (ts.length < len || !free2(ts)) continue;
        const last = i + len === T.length && T.slice(0, i).some(x => x.used || x.taken);
        if (i === 0 ? !(len === 2 && T.length === 2) : (!PLACING.test(T[i - 1].w) && !last)) continue;   // or the whole question is the two words ("Toa Vaja", "Juana Dias")
        const m = muniNear(ts.map(t => t.w), ix);
        if (m) { places.push({ muni: m.name, name: ts.map(t => t.w).join(' '), a: ts[0].a, b: ts[ts.length - 1].b, typo: true }); ts.forEach(t => { t.used = true; }); break; }
      }
    }
    // the words left: matched against the datasets' own words, and the 3D view's column measures
    // a word of distance ("near", "cerca") says where, not what: alone it took the 10 km to a health centre, whose own words have "near a health center" (PR #8)
    const left = T.filter(t => !t.used && !t.taken && !t.time && t.w.length > 2 && !STOPW.has(t.w) && !KNOWN.has(t.w) && !NEARW.has(t.w) && !/^\d+$/.test(t.w));
    let dataset = null, metric = null;
    if (left.length) {
      const scored = [], st = (t) => t.st || (t.st = stem(t.c));
      // a word of a dataset's name: by its stem, or as written when the stem is four letters or fewer ("calls" is not "calles"); its group and summary words by a stem of five or more
      const lab = (d, t) => d.label.has(st(t)) && (st(t).length >= 5 || d.words.has(t.c)), grp = (d, t) => st(t).length >= 5 && d.group.has(st(t)), ext = (d, t) => st(t).length >= 5 && d.extra.has(st(t));
      for (const d of ix.docs) {
        let s = 0, strong = 0;
        for (const t of left) {
          const idf = Math.log(1 + ix.n / (ix.df.get(st(t)) || 1));
          if (lab(d, t)) { s += 3 * idf; strong++; } else if (grp(d, t)) s += 1.5 * idf; else if (ext(d, t)) s += 0.6 * idf;
        }
        if (strong) scored.push({ key: d.key, s, strong, last: d.last });
      }
      scored.sort((p, q) => q.s - p.s || q.strong - p.strong || (q.last || 0) - (p.last || 0));
      const top = scored[0] && ix.docs.find(x => x.key === scored[0].key);
      const distinct = top && left.some(t => lab(top, t) && (ix.df.get(st(t)) || 99) <= 8);   // a word that few datasets have ("manglares", "dialysis"), not "one", "count" or "residents"
      const covers = top && left.filter(t => lab(top, t) || grp(top, t)).length / left.length >= 0.66;   // most of what is left of the question, not one word of a sentence ("the island is never scored")
      if (scored.length && scored[0].s >= 6 && distinct && covers) {   // beside a place too, when the dataset's words are most of what is left
        const d = ix.docs.find(x => x.key === scored[0].key), hit = left.filter(t => lab(d, t) || grp(d, t) || ext(d, t));
        dataset = { key: d.key, score: scored[0].s, next: scored.slice(1, 4).filter(x => x.s >= scored[0].s * 0.6).map(x => x.key), words: hit.map(t => t.w), a: Math.min(...hit.map(t => t.a)), b: Math.max(...hit.map(t => t.b)) };
      }
      if (ix.metrics.length) {
        const ms = ix.metrics.map(m => ({ m, s: left.filter(t => m.words.has(stem(t.c))).length })).filter(x => x.s).sort((p, q) => q.s - p.s);
        if (ms.length && ms[0].s >= Math.min(2, left.length)) metric = ms[0].m.value;
      }
    }
    // explain: "¿qué es X?", "what is X", "define X", "qué significa X"
    let explain = null;
    const em = EXPLAIN.exec(n.replace(/^[\s¿?]+/, ''));
    if (em) {
      const target = n.replace(/^[\s¿?]+/, '').slice(em[0].length).replace(/^(?:el|la|los|las|un|una|lo|the|a|an)\s+/, '').replace(/[?.!¿\s]+$/, '').trim();
      const tn = target.replace(/[^a-z0-9]+/g, ' ').trim();
      let gl = null;
      for (const [id, forms] of ix.glossaryForms) for (const f of forms || []) { if (!f || f[0] === '!') continue; const fn = nrm(f).replace(/[^a-z0-9]+/g, ' ').trim(); if (fn && (tn === fn || (tn.startsWith(fn + ' ') && tn.split(' ').length - fn.split(' ').length <= 2) || tn.endsWith(' ' + fn) && tn.split(' ').length - fn.split(' ').length <= 2)) { if (!gl || fn.length > gl.len) gl = { id, len: fn.length }; } }
      const lay = hits.find(h => h.kind === 'layer' && h.name);
      explain = { target, glossary: gl && gl.id, layer: lay && lay.id, strong: STRONG_EXPLAIN.test(n.replace(/^[\s¿?]+/, '')) };
      if (!explain.glossary && !explain.layer && !explain.strong) explain = em && /^(?:y\s+)?(?:que|qu[eé])\s+es\b|^(?:what|whats|what's)\s+(?:is|are)\b/.test(n.replace(/^[\s¿?]+/, '')) ? { target, weak: true } : null;
    }
    // what must not be drawn
    const sens = [];
    if (SENS.dv[0].test(n) && SENS.dv[1].test(n)) sens.push({ kind: 'dv' });
    if (SENS.drugs.test(n)) sens.push({ kind: 'drugs' });
    if (SENS.pii.test(n) && SENS.piiWhere.test(n)) sens.push({ kind: 'pii' });
    else if (/\b(?:donde|where)\s+(?:vive|reside|lives|does\s+[a-z]+(?:\s+[a-z]+)?\s+live)\b/.test(n) && !/\b(?:mas|menos|gente|personas|mayoria|most|more|fewer|people|families|familias|los|las|ricos|pobres|rich|poor)\b/.test(n)) sens.push({ kind: 'pii' });
    if (SENS.locate.test(n) && SENS.facility.test(n) && !SENS.abortion.test(n)) sens.push({ kind: 'facility' });
    if (SENS.homes.test(n)) sens.push({ kind: 'homes' });
    if (SENS.abortion.test(n)) sens.push({ kind: 'abortion' });   // before 'facility': a reason of its own, and no list of health centres
    if (SENS.vacant.test(n)) sens.push({ kind: 'vacant' });   // before 'addresses': the owners or addresses of abandoned homes, with the vacancy counts
    if (SENS.rentalHosts.test(n)) sens.push({ kind: 'rentals' });
    if ((SENS.aid.test(n) || (SENS.aidWho.test(n) && SENS.aidWhat.test(n) && SENS.aidGet.test(n))) && !SENS.aggregate.test(n)) sens.push({ kind: 'aid', food: SENS.aidFood.test(n) && !/\bfema\b/.test(n) });   // who receives aid or where they live; "cuántos hogares reciben el PAN" is a count
    for (const k of ['names', 'healthPerson', 'addresses', 'careNames', 'rentals', 'foster', 'namedHome', 'homebound']) if (SENS[k].test(n) && !sens.some(x => x.kind === k)) sens.push({ kind: k });
    if (SENS.origin.test(n) && /\b(?:donde|where|viven|vive|live|lives|living|cuantos|cuantas|how many|lista|list|direcci\w*|address\w*|ubicaci\w*|locat\w*)\b/.test(n)) sens.push({ kind: 'origin' });   // where people of a national origin live, or how many in a place; "poverty in immigrants" is a group's figure
    if (SENS.officials.test(n)) sens.push({ kind: 'officials' });
    if (SENS.crisis.test(n.replace(SENS.notCrisis, ' '))) sens.unshift({ kind: 'crisis' });
    if (SENS.nearMe.test(n)) sens.push({ kind: SENS.treatment.test(n) ? 'nearMeTx' : 'nearMe' });
    const concepts = hits.filter(h => h.kind === 'concept'), layers = hits.filter(h => h.kind === 'layer'), layers3d = [...new Set(hits.filter(h => h.kind === 'layer3d').map(h => h.id))];
    // language: the lexicon's words of each language in the question
    const vote = { es: 0, en: 0 }; hits.forEach(h => { if (h.lang === 'es' || h.lang === 'en') { const other = h.lang === 'es' ? 'en' : 'es', both = ix.phrases.some(p => p.kind === h.kind && p.id === h.id && p.lang === other && p.words.join(' ') === h.words.join(' ')); if (!both) vote[h.lang]++; } });
    return { tokens: T, hits, concepts, layers, layers3d, places, dataset, metric, time, trend: TREND.test(n), explain, sens, fresh: FRESH.test(n), countData: COUNT_DATA.test(n), relate: RELATE.test(n) || DENSITY.test(n), density: DENSITY.test(n), vote, lang,
      quals: QUALS.filter(q => q.re.test(n)).map(q => q.id) };
  }
  /** The one municipio a misspelt name is close to: words ws (one or two), within one edit of the name (two from eight letters), and no other municipio as close;
      null when a word that differs is real (protected, of the vocabulary or of the observatory's texts) or too short. o.noProtect: tests/ask_words.js. */
  function muniNear(ws, ix, o = {}) {
    const s = ws.join(' '); if (s.replace(/\s/g, '').length < 5) return null;
    const c = ix.munis.filter(x => x.n.split(' ').length === ws.length && x.n !== s).map(x => ({ x, d: dl(s, x.n, x.n.length >= 8 ? 2 : 1) })).filter(y => y.d <= (y.x.n.length >= 8 ? 2 : 1));
    if (c.length !== 1) return null;
    const own = c[0].x.n.split(' '), diff = ws.filter((w, k) => w !== own[k]);
    // two words of which one is the municipio's own and the other one edit from its other word: the name, even when that word is real ("Juana Dias", "Las Pierdas")
    const anchored = ws.length === 2 && diff.length === 1 && diff[0].length >= 4 && dl(diff[0], own[ws.indexOf(diff[0])], 1) <= 1 && !ix.vocab.has(diff[0]);
    if (!anchored && diff.some(w => w.length < 4 || (!o.noProtect && PROTECTED.has(w)) || ix.vocab.has(w) || (ix.real && ix.real.has(w)) || /\d/.test(w))) return null;
    return c[0].x;
  }
  /** Whether two spans of the question are items of one list or one relation ("transporte y vivienda", "pobreza con las paradas"): only connecting words between them. */
  function coordinated(n, a, b, relate) { const [x, y] = a.a < b.a ? [a, b] : [b, a]; if (x.b > y.a) return false; const g = n.slice(x.b, y.a); return COORD.test(g) || (!!relate && COORD_REL.test(g)); }

  // ── Texts ──────────────────────────────────────────────────────────────────
  const SENS_TEXT = {
    dv: { es: 'Por seguridad, el observatorio nunca publica ni dibuja la ubicación de refugios o albergues para víctimas de violencia doméstica.', en: 'For safety, the observatory never publishes or draws the location of domestic violence shelters.' },
    drugs: { es: 'El observatorio no publica ubicaciones de actividad delictiva y no tiene esos datos: solo cuenta los delitos reportados por municipio.', en: 'The observatory has no locations of criminal activity and never publishes any: it only counts reported crimes by municipio.' },
    pii: { es: 'El observatorio no muestra dónde vive una persona, su dirección ni sus datos de contacto: solo publica datos agregados por área.', en: 'The observatory does not show where a person lives, their address or contact details: it only publishes data aggregated by area.' },
    facility: { es: 'Las instalaciones de salud se cuentan por municipio y nunca se dibujan como puntos en el mapa.', en: 'Health facilities are counted by municipio and are never drawn as points on the map.' },
    homes: { es: 'Las casas privadas se cuentan por área y nunca se dibujan ni se nombran.', en: 'Private homes are counted by area and are never drawn or named.' },
    names: { es: 'El observatorio no publica nombres ni datos de personas: solo cifras agregadas por área.', en: 'The observatory never publishes names or details of people: only figures aggregated by area.' },
    healthPerson: { es: 'El observatorio no tiene ni publica datos de salud de personas ni dónde viven: solo datos agregados por municipio.', en: 'The observatory neither holds nor publishes health data on people or where they live: only data aggregated by municipio.' },
    addresses: { es: 'El observatorio no publica direcciones de casas ni de personas: solo datos agregados por área.', en: 'The observatory never publishes home or personal addresses: only data aggregated by area.' },
    aid: { es: 'El observatorio no muestra qué hogares o personas reciben o recibieron ayuda, ni dónde viven: es información privada. Solo publica totales por municipio.', en: 'The observatory does not show which households or people receive or received aid, or where they live: that is private. It only publishes totals by municipio.' },
    abortion: { es: 'El observatorio no tiene datos sobre servicios de aborto. Las instalaciones de salud solo se cuentan por municipio; el observatorio no las nombra, no las lista ni las dibuja.', en: 'The observatory has no data on abortion services. Health facilities are only counted by municipio; the observatory does not name, list or draw them.' },
    vacant: { es: 'El observatorio no publica dueños, nombres ni direcciones de casas abandonadas o vacías: son propiedades privadas. Solo cuenta las viviendas vacías por municipio.', en: 'The observatory does not publish the owners, names or addresses of abandoned or vacant homes: they are private property. It only counts vacant homes by municipio.' },
    crimeSite: { es: 'El crimen solo se publica por municipio: el observatorio no tiene delitos por residencial, barrio ni calle.', en: 'Crime is only published by municipio: the observatory has no crimes by public housing development, barrio or street.' },
    careNames: { es: 'Los hogares de ancianos y de cuido se cuentan por municipio; el observatorio no los nombra ni los dibuja, porque son el hogar de quienes viven en ellos.', en: 'Nursing and care homes are counted by municipio; the observatory does not name or draw them, because they are the home of the people who live there.' },
    rentals: { es: 'El observatorio no publica direcciones, anfitriones ni dueños de alquileres a corto plazo: son casas privadas, que se cuentan por municipio y nunca se dibujan. Solo cuenta las unidades de uso estacional por municipio.', en: 'The observatory does not publish the addresses, hosts or owners of short-term rentals: they are private homes, counted by municipio and never drawn. It only counts seasonal-use units by municipio.' },
    nearMe: { es: 'Este chat no usa su ubicación. Escriba su municipio (por ejemplo, «hospitales en Caguas») para ver los datos de esa área.', en: 'This chat does not use your location. Name your municipio (for example, "hospitals in Caguas") to see that area\'s data.' },
    nearMeTx: { es: 'Este chat no usa su ubicación, y los centros de tratamiento y de salud se cuentan por municipio sin dibujarse. Para buscar tratamiento cerca de usted: findtreatment.gov (SAMHSA). Si usted o alguien que conoce está en crisis, llame o escriba al 988 (marque 2 para español; o escriba AYUDA al 988). En Puerto Rico también puede llamar a la Línea PAS de ASSMCA al 1-800-981-0023 (24 horas, gratis y confidencial) o usar su chat en lineapas.assmca.pr.gov.', en: 'This chat does not use your location, and treatment and health facilities are counted by municipio, never drawn. To find treatment near you: findtreatment.gov (SAMHSA). If you or someone you know is in crisis, call or text 988. In Puerto Rico you can also call ASSMCA\'s Línea PAS at 1-800-981-0023 (24 hours, free and confidential) or use its chat at lineapas.assmca.pr.gov.' },
    crisis: { es: 'El observatorio no tiene datos sobre esto. Si usted o alguien que conoce está en crisis, llame o escriba al 988 (marque 2 para español; o escriba AYUDA al 988). En Puerto Rico también puede llamar a la Línea PAS de ASSMCA al 1-800-981-0023 (24 horas, gratis y confidencial) o usar su chat en lineapas.assmca.pr.gov.', en: 'The observatory has no data on this. If you or someone you know is in crisis, call or text 988. In Puerto Rico you can also call ASSMCA\'s Línea PAS at 1-800-981-0023 (24 hours, free and confidential) or use its chat at lineapas.assmca.pr.gov.' },
    foster: { es: 'El observatorio no publica ni dibuja hogares de crianza ni albergues de menores: protegen a niños y jóvenes.', en: 'The observatory never publishes or draws foster homes or shelters for minors: they protect children and young people.' },
    namedHome: { es: 'El observatorio no nombra ni dibuja hogares de tratamiento o de recuperación: son el hogar de quienes viven en ellos. Los centros de tratamiento se cuentan por municipio.', en: 'The observatory does not name or draw treatment or recovery homes: they are the home of the people who live there. Treatment facilities are counted by municipio.' },
    homebound: { es: 'El observatorio no localiza a personas encamadas ni confinadas en su casa: solo publica datos agregados por municipio.', en: 'The observatory does not locate people who are bedridden or homebound: it only publishes data aggregated by municipio.' },
    origin: { es: 'El observatorio no localiza ni cuenta a personas por su origen nacional en un lugar.', en: 'The observatory does not locate or count people by national origin in a place.' },
    officials: { es: 'El observatorio no evalúa a funcionarios electos. Estos son datos del municipio, como contexto.', en: 'The observatory does not evaluate elected officials. These are the municipio\'s data, as context.' },
  };
  const ON3D = { es: 'Ver en 3D', en: 'See in 3D' };

  return { VERSION, ONLY_2D, IN_2D, nrm, toks, stem, dl, langOf, correct, muniNear, fix, build, understand, coordinated, PROTECTED, PRIVATE, QUALS, CONCEPTS, CONCEPT, LAYER_WORDS, LAYER_DATA, ONLY_3D, SETTINGS_3D, SCHEDULE, ALIASES, SENS_TEXT, ON3D, STOPW, KNOWN, CRIME_SITE };
});
