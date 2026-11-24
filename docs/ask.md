# "Ask the observatory"

The chat answers in the browser, with no language model and nothing sent anywhere: rules (`site/js/chat.js`) and an understanding layer with a lexicon, a scorer and a planner (`site/js/ask.js`, 2026-10-20). This file has three parts: how Ask understands a question (2026-10-20, branch `ask-intent`), Ask on the pages without a map (2026-10-26), and the generated lexicon of plan item 14 (below, unchanged).

## How Ask understands a question (2026-10-20)

The project lead, 2026-10-20: "Tienes que trabajar en mejorar la utilidad de 'ask'. Esto es muy importante porque la mayoría de los usuarios pueden navegar el mapa con el ask y no está funcionando correctamente. Si alguien escribe algo en el ask, tienes que poder visibilizar lo más próximo posible y encender las capas correspondientes."

### Why "Transportation and housing" dead-ended

The question reached the last answer for four reasons, each general:

1. **Topics were dataset names.** The rules of `chat.js` name measures ("transportation jobs", "housing units", "rent"). A bare topic word ("transportation", "housing", "salud", "guagua") matched no rule. The generated lexicon (item 14) needs every word of a two-word name, so it did not match either.
2. **Layers only rode along.** `CH_CONTEXT` noticed "routes" or "flood", but the layer was switched on only beside a dataset. With no dataset the answer was `unknown`, which never touches the map, and the question went to the wishlist as missing data although the layer exists.
3. **One topic per question.** Nothing joined a second topic: in "pobreza y escuelas en Ponce" the rule took poverty, and "escuelas", a one-word phrase, was not allowed beside it.
4. **No nearest answer.** The fallback was text: the field of the registry ("In Housing the observatory has 65 datasets…") or the closest labels. Nothing was drawn, nothing was offered as a button, and missing data were never approximated. Typos, Puerto Rican words (guagua, la luz, cuido, chavos), place names that are not municipios (Santurce, Levittown) and questions about a term ("¿qué es el margen de error?") all ended there.

### The design

```
question ─► typos (short questions) ─► chParse (rules, as before) ─► ask.js understand ─► chRefine (compose) ─► handler ─► chDecorate (what it is, chips)
                                              │                         │
                                              └── keys, places, years   └── concepts, layers, places, time, sensitive, a term, the datasets' own words
```

`chat.js` keeps every rule and handler. `ask.js` and `core/layers.js` load with the first question (`chAskModule`), so no page's first load carries them; the index is built once, in the page.

**One index over what Ask can show** (`Ask.build`):

- the 341 datasets of the Economy tab: their names in English and, on a Spanish page, in Spanish, their groups, the `ask` words of their dictionary entries (catalog index), the Spanish summary words of `catalog_es.json` and their definitions;
- the map layers of the registry (`core/layers.js`), with their menu names in both languages, and the switches outside the menu (the Transit tab, the 3D clock and Time tab: routes by trips in the hour, stops by departures, residents far from service, integration points, vehicles now, storm tracks);
- the 3D view's own column measures (its `#metric` menu);
- the glossary terms in both languages (`glossary_forms_*.json`; their definitions are read when a term is asked);
- the municipios, and well-known place names with their municipio and point (`ALIASES`, points from `gazetteer.json`);
- the lexicon (`CONCEPTS`, about 110 topics): everyday words in Spanish and English, Puerto Rican words included, each with its datasets in order of preference, the layers that map it, and, when the data only approach the question, what is missing.

**Scoring.** Text is compared without accents or capitals. A word matches a lexicon word when it is the same, has the same light stem (plurals and the endings of nouns and participles; a final *e*; "transporte", "transportation" and "transportación" share one stem; "costo" is not "costa", "viviendo" is not "vivienda") or starts with a prefix the lexicon marks (`guagua*`). Phrases match longest first, with up to two small words skipped between their words; a word is used once. A **typo** is corrected only toward a topic word (the lexicon, layers, places and the rules' topic words), one edit for five to seven letters and two from eight, with the same first letter, never when the word appears in the observatory's own texts, never when two different words tie, and only in a short question (eight words or fewer); when the rest of the question is understood, only a word in a list is read ("pobreza y desempelo"). The answer says what it read ("Leí «pobresa» como «pobreza»"). The datasets' own words are scored (label and `ask` words three times, group words one and a half, summary words 0.6, each weighted by how rare it is) only when the rules found nothing, and a dataset is taken only when a rare word of its name is there and its words are two thirds of what is left of the question.

**Multi-intent parsing** (`Ask.understand`): the topics with where they stand, the layers, a place (a municipio, an alias with its point, a municipio one edit away after a word that places: "en ponse"), a time ("después de María" is since 2017; an event is a time only with its cue), the operation words the rules do not know (Spanish trend verbs, "la última década", "peores", two years named), a term to define, what must not be drawn, and the language of the lexicon's words when the question has none that `chLang` knows.

**Composition** (`chRefine`):

- Beside the rules' datasets, a topic counts when the question lists it with them (a comma, "y", "and", "e", "o"; "con", "with", "versus" in a question that relates things) or relates them across places ("los pueblos con más viejos tienen más pobreza"). A topic joined by "de", "con", "of", "with" to the phrase before it is a word of that phrase ("propietarios con hipoteca", "rent of students"). The words of a group the figure is broken down by ("children" in "teenagers and children poverty") are not a dataset of the answer.
- Two topics: a topic that a layer maps (transit, ferries, flood zones, protected areas, land use) turns its layers on, the other topic is shaded, and the answer gives the correlation of their two datasets across municipios with "a pattern, not a cause" and a button for the scatter plot. "transporte y vivienda": routes and stops on, median gross rent shaded, rent against the share of residents within a 400 m walk of a stop with a current timetable. Two topics with datasets only: both shaded (a bivariate map), as before.
- A topic alone: its layers and its first dataset ("inundaciones": the flood zones, and the share of residents in a Special Flood Hazard Area).
- A concept of two words or more that reads part of what a rule took takes the rule's place when it holds an approximation, a count or nothing to show, or when the rule's dataset is not one of its own ("cuido de niños", "salario mínimo", "health insurance", "viviendas vacías"). A rule that took exactly a broad concept's words for a dataset the concept does not hold gives way to the concept's first dataset, and the rule's dataset becomes a chip ("salud": health center sites first, health-care jobs as a chip; "hospitals": Medicare-certified hospitals).
- A command word that is also a word of a topic does not command: "agua limpia" is water, "ayuda federal" is federal money, "falta de vivienda" and "tamaño de los hogares" are housing, "fuentes de agua" is water.
- Then the intent again (`chIntent` on the new datasets), with what the rules do not cover: Spanish "correlación" and "frente a" compare; "peores", "mejores" rank; a trend verb or two years trend; "calidad de vida en Caguas" is the municipio's profile.

**Always something.** A layer named alone is switched on (`layers`), with the place in view and the datasets that go with it as chips. When the data do not exist, the nearest dataset is shown, the answer says **"Aproximación: …"** (what is missing and what stands in), and the question goes to the wishlist. When nothing is related, the answer says so and offers the nearest layers as buttons (`nodata`: shelters, elections, places of worship, food access, cell coverage, drought, wildfires). A broad question shows its best guess at once and offers two other readings as chips (the topic's next datasets; tourism last).

**Place-aware rankings and trends.** A ranking with one municipio named ranks its barrios when the dataset has barrio values (the 2D map's level files: the survey datasets, the conditions and the WCRP indices) and shades the map by barrio; otherwise it says where the municipio stands among the 78. A trend with a municipio gives its own change first and its place by change, and selects it. "por barrio" shades the map by barrio.

**What is never drawn.** A question about a shelter for victims of violence, a person's home or contact details, or drug points is answered with the reason and nothing on the map (drug points: the municipio's reported crimes). Health facilities, treatment facilities and private homes are counted by area; the answer says so. HRSA site points are never published.

**Explanations and chips** (`chDecorate`). Every answer that shows a dataset ends with one to three sentences: the dataset, by municipio (or barrio), the period (a five-year window, a snapshot with its date, or a year), the source, and whether it is a survey estimate (once, when the margin note is not already there) or an approximation. Layers name their source; transit is labelled "horarios programados (GTFS), no posiciones en vivo". The chips offer the other readings, then "¿Cómo ha cambiado ese dato?", "Compárelo con…"; the buttons offer the relation, "Ver en 3D" (the 3D view opens with the same question, `3d.html#ask=`, read by `ask3d.js` and taken out of the address) and "Ver en el diccionario".

**3D parity.** The same reading drives the 3D columns (the first dataset is the height, the second the colour) and the 3D switches; on the 3D view the lexicon also reaches the terrain, the 3D buildings, the scheduled vehicles, the storm tracks and the routes by trips in the hour; on the 2D map the same words go to its own layers (vehicles now, routes). The page actions (`chLayersOn`, `chGoTo`, `chMetrics`, `chSetMetric`) are in `chat.js`, so they load with the chat; the page APIs add only `levelSeries` (2D: the barrio values; 3D: none) and the `level` of a shaded layer (2D).

### The lexicon and how to extend it

`site/js/ask.js`:

- **`RAW` (concepts).** `[id, 'spanish|words', 'english|words', 'datasets|best|first', 'layers', options]`. Words without accents, lower case; a final `*` is a prefix. Datasets in order of preference: the freshest and most direct first (LAUS before the survey's unemployment rate). Options: `proxy: { es, en }` (the datasets only approach the question: say what is missing and what stands in, never claim more than the data), `missing: { es, en }` (nothing to show; `related` names the nearest layers), `sens: 'count'` (counted, never drawn), `profile` (with a place, the municipio's profile), `domain`, `last` (tourism). Tourism goes last wherever a list is offered.
- **`LAYER_WORDS`.** Everyday names of each switch, in both languages; the registry's menu names are matched too. `ONLY_3D`, `ONLY_2D` and `IN_2D` say which view has a layer and where a 3D-only request goes on the 2D map. `LAYER_DATA` lists the datasets a layer's answer offers. `SCHEDULE` lists the layers labelled as timetables.
- **`ALIASES`.** A place name that is not a municipio: `[municipio, lat, lon]`, the point from `gazetteer.json`.
- **`TOPIC_WORDS`, `KNOWN`, `STOPW`.** What a typo may be corrected to; words that are never a topic or a typo.

To add a topic: add a row to `RAW` with words in both languages and datasets that exist (`tests/ask.test.js` fails on a dataset or layer that does not), then add cases to `tests/ask_dev.json` and run `node tests/ask_dev.js --fail`, `node tests/chat_answer_replay.js` and `node --test tests/ask.test.js`. Prefer a general word to a phrase of one question. A new dataset is askable by its own name the day it is registered (item 14); a concept only adds the words people use for it.

### Measured

**Development set** (`tests/ask_dev.json`, 247 questions written for this work: Spanish 189, English 48, mixed 10; multi-topic, place, rankings, comparisons, trends, layers, vague, missing data, typos, one word, questions about the data, sensitive, 3D, barrios). `node tests/ask_dev.js [--base main]`, 1.4 s, in CI through `tests/ask.test.js`.

| | main | branch |
|---|---|---|
| all | 39.3% (97/247) | 100% (247/247) |
| multi-topic | 40.0% (14/35) | 100% |
| place | 55.2% (32/58) | 100% |
| layers | 29.8% (14/47) | 100% |
| rank | 59.1% (13/22) | 100% |
| compare | 69.2% (9/13) | 100% |
| trend | 50.0% (7/14) | 100% |
| vague | 26.7% (4/15) | 100% |
| missing data (proxy) | 12.5% (3/24) | 100% |
| typos | 39.1% (9/23) | 100% |
| one word | 28.6% (12/42) | 100% |
| about the data | 38.5% (5/13) | 100% |
| sensitive | 40.0% (4/10) | 100% |
| 3D | 30.8% (4/13) | 100% |
| barrios | 0% (0/5) | 100% |
| Spanish / English / mixed | 36.0% / 47.9% / 60.0% | 100% / 100% / 100% |

The development set was written before the code but the code was tuned on it, so 100% says little about new wordings. **Check set** (`tests/ask_check.json`, 81 questions written after the code and run once before any change for them): main 58.0% (47/81), branch at its first run **87.7% (71/81)**; its failures were vocabulary gaps ("gente mayor", "áreas verdes", "terrenos agrícolas", "seguridad en Bayamón", "consumo de drogas", "lost the most people") and two patterns ("over the last decade", the place of a comparison), fixed in general form; now 100%. The held-out benchmark written by someone else is the real measure.

**Replay.** `node tests/chat_answer_replay.js` answers the 2,226 question-like strings of main's `tests/core.test.js` with main's chat and with this branch's, over the same datasets, and lists every answer whose intent, datasets, layers or place changed. `node tests/chat_lexicon_replay.js` (the parser alone) still finds 0 changed. 86 answers changed, classified:

- **Main showed nothing, now the nearest topic (56).** 45 are test descriptions, not questions ("hexbin: counts are conserved…"), answered with the topic word they hold; 11 are short: "Unidades de vivienda" and "casas de alquiler" (housing data), "Ruta A", "Barrio A" (the routes, the barrios layer), "far by walking" (walking measures).
- **Better dataset (10).** "women and health insurance": uninsured people, not finance-and-insurance jobs; "tasa de vacantes de alquiler": the rental vacancy rate; "las viviendas vacías, mujeres": other vacant units, not all housing units; "hospital(s)" (2): Medicare-certified hospitals, not health-care jobs; the headings "Health care · …" (5): health center sites first; "Florida is mapped entirely as minimal hazard": the expected loss of Florida (a test description).
- **Better kind of answer (16).** Spanish "correlación", "correlaciona", "correlacionadas", "frente a" (5): a comparison; "over the last decade", "la década pasada", "in 2015 and 2020", "de 2010 a 2015" (7): a trend; "Places of Worship": says the observatory has none; three test descriptions ("history", "source") now get a trend or sources answer.
- **Place kept (2).** "correlate women in Ponce with poverty", "correlate poverty among most women in Ponce": Ponce selected.
- **By barrio (1).** "landslide by barrio…": the landslides shaded by barrio.
- **One dataset fewer (1).** "Health care · Health centers": the health center sites once, not health-care jobs beside them.

In the replay no answer that showed something on main shows nothing now. In the development set two do, by design: a question about how fresh the data are (the sources answer, which never drew) and a person's home (the reason, nothing drawn). A term that is also a dataset ("¿qué es el índice de Gini?", "¿qué es un HPSA?") gets the definition and keeps the dataset on the map.

**Weights** (gzip level 6, LF copies): first load, map scripts 243.8 → 244.0 KB of 250 (the 2D `levelSeries` and the layer `level`), 3D 644.7 → 645.1 KB of 700 (`levelSeries` and the `#ask=` hand-over); data unchanged. Loaded with the first question: `chat.js` 45.5 → 57.6 KB, `ask.js` 26.7 KB, `core/layers.js` 3.4 KB, and the files `catalog_es.json` (32 KB, now on English pages too), `glossary_forms_en.json` and `glossary_forms_es.json` (8 KB); the 2D map reads a level file (`acs_barrio.json` or the dataset's own) the first time a ranking by barrio is asked.

### Not done

- Barrios on the 3D view (the columns are by municipio): a ranking of barrios answers on the 2D map.
- Regions ("el oeste", "el área metro") are not places yet; the answer is island-wide.
- A barrio named alone is not a place yet (only the aliases and the municipios); the gazetteer could answer that on use. (Done in round 4, below.)
- The model-assisted chat (plan G) still needs a hosted proxy that FPR decides on.

### Round 2: the review's fixes (2026-10-20)

The review of PR #79 against a held-out set written by someone else said "fix first" (about 45% on main, 80 to 82% on this branch) and named eight kinds of failure. Each is fixed in general form, not for its examples; every example the review gave is a regression test in `tests/ask_review.test.js`.

1. **Typos changed real words and place names** (31 of 610 barrio and municipio name words, 124 common words; "shopping malls" read as shootings, "¿qué tienes?" as trains, "salsa" as emergency rooms). Now: a word is corrected only from six letters, one edit up to nine letters and two from ten, to one best word with the same first letter; never a word of `PROTECTED` (below), of the observatory's own texts or a form of a known word; never into an alarm topic (crime, drug use, disease, death, violence, emergency rooms, shelters), unless another topic uses the word too; to a municipio or a place only after a word that places it ("en", "in", "de"…) or when the corrected question is the municipio's name; never to a word of the other language than the question's. `tests/ask_words.js` builds `PROTECTED`: it runs the correction, unprotected, over a corpus of real words (about 900 common Spanish and English words, the observatory's own texts in both languages except this page, which quotes typos, every barrio, municipio and region name of the crosswalk, and the names of settlements, parks, beaches, peaks, waters, landmarks, airports and malls of the gazetteer; street and institution names are left out because OpenStreetMap's own typos are there, "Calle Mayaguex") and writes into `ask.js` the words it would change, except a change to another form of the same word ("historical" to "historic"): 183 words. `node tests/ask_words.js --check` (and a test) fails when the list is not current.
2. **Stop words and the other language.** A function word is never a form of a topic word ("estas" is not "estaciones"); a light stem of four letters or fewer counts only as written ("calls" is not "calles", in the lexicon and in the datasets' own words); "-ing" is not an ending of the stem ("parking" is not "parks"); a phrase of the other language than the question's matches only as written or as a prefix. The language of a question is read from its function words, and an accented place name no longer makes an English question Spanish ("unemployment in Bayamón").
3. **Stand-ins are labelled.** Every answer that shows a dataset other than the one asked says "Aproximación: «X» en lugar de Y, que el observatorio no tiene" (or the topic's own approximation text) and puts the question on the wishlist: a topic the observatory lacks beside one it has ("apagones de luz", "hoyos en las carreteras"), an age group the figure is not broken down by ("desempleo juvenil"), a qualifier the dataset lacks (speed, monthly figures, a price). New topics with their own approximation: air quality, drug use (treatment facilities stand in, and say they do not measure use), CDTs, storm surge (coastal flood loss, not wind), CRIM assessed values (the ACS home value), computer access. Where the stand-in was weak it is now "not available" with the nearest layers switched on and the nearest datasets offered as chips, never shaded: disease, pharmacies, potholes, beaches, the minimum wage, Medicaid, private schools, water and power outages, electricity prices, hotel occupancy, building permits, trees, shopping malls. The place asked about is still selected.
4. **Margins of error.** A ranking of barrios, and a ranking of municipios of a survey dataset, marks an estimate whose 90% margin is more than half of it (or a zero with a margin) "poco confiable / unreliable" (a coefficient of variation above about 30%), counts them, and says which of the first rows are not statistically different from the first (the Census Bureau's test: |a − b| / √(SEa² + SEb²) > 1.645, SE = MOE / 1.645).
5. **What is never drawn says why** even when nothing could be drawn: names of people (students, patients, residents), where people with a health condition live, home addresses, which homes received aid, the names of nursing and care homes, short-term rental addresses, "near me" (the chat does not use the location; for treatment it points to findtreatment.gov and 988). A count by municipio follows when there is one (public school students, FEMA-approved households, nursing homes, seasonal units, treatment facilities). None goes on the wishlist.
6. **Places beside topics.** Well-known places are read in a pass of their own, so "El Yunque" goes to El Yunque and switches the protected areas on; new: Caño Martín Peña, the airports (Luis Muñoz Marín from the FAA record in `transport.json`; "el aeropuerto" alone is that one unless a municipio is named), Mosquito Bay, Cerro de Punta, Toro Negro, the Camuy caves, Mona, Caja de Muertos, Cueva Ventana, the Guánica and Carite forests, Punta Tuna. The map ends at the point even when the municipio's selection moves it a moment later.
7. **Small ones.** "cuánta gente / cuántas personas" is a topic only alone; a sentence is said once; a trend's About line gives its range; "clear" is a command only alone or with the map or the layers as its object ("limpia las playas" and "clear water" are topics), "quita / apaga todas las capas" turns every layer off with the layer chip's Undo; "hurto", "robo de carros" read property crime; the dictionary's unit for the answers is 23 kinds; a per-resident view that is one number everywhere (the population per 1,000 residents) is shown as published; a trend lists as "rose most" only places that rose ("fell least" for the others); the 3D view's layers asked on the map page ("elevación en Jayuya") say they are in the 3D view, with the link, and go to the place.
8. **Time to the first answer.** `tests/browser/ask_timing.js`: Slow 4G, a first load with the cache off, the pointer over the Ask button, a press 300 ms later and the question at once; three runs each, medians. `chatboot.js` now starts the download when the pointer goes over the button (or it gets the focus or a touch) and loads `chat.js`, `ask.js` and the layer registry side by side; `chat.js` builds the index as the window opens; `catalog_es.json` loads only on a Spanish page; dead fields of `understand` are gone.

| press to first answer | main | round 1 | now |
|---|---|---|---|
| English page | 3.98 s (50 KB) | 5.00 s (134 KB) | 4.08 s (112 KB) |
| Spanish page | 4.06 s (51 KB) | 5.06 s (135 KB) | 4.29 s (145 KB) |

(KB: the chat's files, compressed. The files grew with the lexicon, `chat.js` 62.6 KB and `ask.js` 34.0 KB; the time fell because they no longer load one after another, and start before the press.) Page loads on Slow 4G are unchanged (map ready 4.7 s, 3D 16.9 s). First-load scripts: map 244.7 of 250 KB (with main's Transit tab change, a17c776), 3D 645.4 of 700, WCRP 79.9 of 80.

**Measured again.** Development set, 279 questions (32 new general cases of these eight kinds, not the review's probes, and four whose expected answer changed by policy from a weak stand-in to "not available" with the nearest data): main 36.9%, branch 100%; round 1's code passes 3 of the 36 new or changed cases. Check set (81): main 58.0%, branch 100% (one case changed by the same policy: "mortalidad infantil"). The held-out set remains the measure. **Replay** (2,226 questions): 84 answers differ from main (86 in round 1); between round 1 and now 4 changed, all better: "Unidades de vivienda" shows the housing units (not rent and public housing), two test descriptions no longer get a stray dataset ("the file has a municipality with a site", "study areas: a small area keeps its share…"), and "an older link with a municipio map opens by barrio" switches the barrios on without a stray dataset. No question of the replay is corrected as a typo now.

### Round 3: the measurement of 98f7359 (2026-10-20)

The independent measurement found no sensitive drawing, causal claim or invented number, but one required fix. All of these are tested in `tests/ask_review.test.js` ("Round 3").

- **Crisis topics (required).** Suicide, self-harm and overdose deaths (suicidio, quitarse la vida, autolesión, sobredosis; suicide, self-harm, overdose deaths) get a reply of their own (`crisis`): "El observatorio no tiene datos sobre esto. Si usted o alguien que conoce está en crisis, llame o escriba al 988 (marque 2 para español; o escriba AYUDA al 988)." / "The observatory has no data on this. If you or someone you know is in crisis, call or text 988." Nothing is shaded, no place is ranked, it is not a data wish; the mental health datasets (psychiatrist shortage, mental health treatment facilities) are offered as chips under a line that says they do not answer the question. Suicide and overdose words are no longer words of the mental health and drug use topics. The Línea PAS number is not given (unverified; needs leadership sign-off). Since 2026-10-21 it is given, verified on ASSMCA's own pages: see "Línea PAS" below.
- **Register.** The treatment answer and "near me" use "usted", with the 988 options spelt out.
- **Misspelt municipios.** A word or two after "en", "in", "de"… or at the end of a question with a topic is read as a municipio when it is within one edit of exactly one municipio (two from eight letters) and no word that differs is real: "escuelas en Toa Vaja", "poverty Aguadila", "unemployment in Sabana Grnade". `tests/ask_words.js` protects every corpus word this reading would take, so the barrio names still are not municipios (Guayabal, Santa Catalina, Maragüez, Cayaguas, Guayabo, Cidral): 227 protected words.
- **Prices.** "precio de las casas", "house/housing prices", "casas valen más", "¿cuánto cuesta una casa?", "homes worth": the median home value, not rent.
- **Barrio rankings** of a dataset with no barrio values use the survey dataset of the same thing that has them, and say so (the BLS unemployment rate → the ACS rate); "no barrio values" only when none exists.
- **More privacy kinds**: foster homes and shelters for minors, named treatment and recovery homes (Hogar CREA, sober houses), people who are bedridden or homebound, people of a national origin in a place: the reason, with a count where one exists (substance use treatment facilities, people with a disability). A question about an elected official's performance gets "El observatorio no evalúa a funcionarios electos" and the municipio's data as context.
- **Stand-ins and false friends.** Not available, with the nearest data: rooftop solar (not utility capacity), ER wait times, cargo flights, free wifi, homes for sale, blue tarps, the news media. Labelled: dentists (dentists still needed in shortage areas). Fixed: "hogares sin carro" (the no-vehicle households alone: a concept that the rules read in full drops the rules' other datasets), "solar farms" (renewable capacity, not farm jobs).
- **Names that are a municipio and something else.** "se muda a Florida", "moving to Florida" (with Orlando, Miami…): the US state, said so, and migration's approximation; "Río Grande de Loíza" (and de Manatí, Arecibo, Añasco): a river, not the municipios. "pobreza en Florida" is still the municipio.

**Measured.** Dev set 307 (28 new general cases): main 34.2%, branch 100%; round 2's code passed 2 of the 28. Check set 81 (one case changed by policy: rooftop solar is "not available"): branch 100%. Replay (2,226): 84 answers differ from main, as in round 2; none changed since round 2; no typo correction.

### Round 4: the measurement of f414f75 (2026-10-20)

An end-to-end run in a real browser found four general gaps that the tests in Node did not see. All are tested in `tests/ask_review.test.js` ("Round 4") and, typed into the chat's box and sent with Enter on a page just opened, in `tests/browser/ask_chat.js` (`round4`, 22 checks per language).

- **Misspelt municipios did not zoom in the page (root cause).** `chInit` built ask.js's index as soon as `chat.js` loaded, and later the window's opening did the same. At that moment the Economy tab had not loaded its data, so `api.places()` and `api.datasets()` were empty. The index kept no municipio and no dataset for the rest of the visit. As a result, `muniNear` never read "culbra" or "aguadila", and the datasets' own words never matched. The answer was the island-wide map with nothing selected. The tests in Node build their page stand-in with the data already in, so they passed. Now `chAskModule` waits for `api.ready()` and the dictionary's index (`withIndex`), then reads the `ask` words (`chAskWords`), and only then builds the index. It starts when the chat opens (`chToggle`), not when the file loads, so a pointer over the button no longer loads the Economy data. An index with no municipio or no dataset is never kept, so the next question builds it again. A test in Node now opens the chat with the page's data still empty.
- **One place for the labels.** `chAnswer` records every dataset the handler puts on the map (`st.shown`, through `api.show`), and `chDecorate` labels from that list, whatever handler showed it (a reason with counts, a barrio, a term that is also a dataset). It no longer works from a list of intents. An answer that shows nothing (`nodata`, `crisis`, `sensitive` with no count) takes the earlier answer's datasets off the map and keeps the place. In the page, "vuelos de carga" after "dentistas en Caguas" left the dentists shaded beside "no tiene datos de carga". The tests in Node start every question from a clean map, so they did not see this. Two general rules close the other paths:
  - A stand-in must come from the same field (the first part of the Economy group) as the nearest data that the lexicon names for the missing topic. "placas solares en las casas de Ponce" is "not available" with renewable capacity as the nearest data, not the rent. "apagones de luz" (power plants) and "tiempo de espera en sala de emergencia" (hospitals with an emergency department) stay labelled stand-ins.
  - A topic that is only approximated and qualifies a bare count ("¿cuántos hogares reciben el PAN?", "households on food stamps") shows the topic's own stand-in (poverty), labelled, not the count of households. With any other dataset, that dataset is labelled.
- **Reasons for what is never drawn.**
  - Abortion services: a neutral reason ("no tiene datos sobre servicios de aborto; las instalaciones de salud solo se cuentan por municipio…") and no list of health centres.
  - The hosts, owners or addresses of short-term rentals: they are private homes, counted by municipio and never drawn, with the seasonal units.
  - The owners, names or addresses of abandoned or vacant homes: private property, with the vacant units and other vacant units by municipio.
  - Where people who receive aid live:
    - FEMA aid: the reason, with the FEMA-approved households (Individual Assistance), never Public Assistance.
    - Food stamps, PAN or welfare: the reason, with poverty labelled as an approximation and no relation drawn.
    - A count ("¿cuántos hogares reciben…?") is not a person, so it gets the count.
  - Crime in a public housing development, barrio or street ("residenciales con más crimen"): crime by municipio, with "El crimen solo se publica por municipio" as an approximation. The public housing layer stays on.
- **A barrio named alone.** After "en", "in" or "barrio", or as the whole question, one to four words that are exactly one barrio name of the crosswalk (`data/geo/crosswalk.json`, accents aside, read on use like the barrio values) are a barrio. Some names never count:
  - a municipio's name ("Rincón");
  - a word of a topic the question already reads;
  - an alias (Santurce);
  - a single word of the lexicon or of the observatory's texts ("en el pueblo", "en la playa"), unless "barrio" comes before it.

  Examples: "pobreza en Guayabal" selects Juana Díaz, shades poverty by barrio, moves the map to the barrio (zoom 13) and gives the barrio's estimate with its margin and whether it is reliable, then Juana Díaz and Puerto Rico. A dataset with no barrio values uses its survey twin, as the barrio rankings do; when the barrio has no published value, the answer says so and shows the municipio's figure. A name that barrios of several municipios share ("Cuchillas": Corozal, Moca, Morovis) shades by barrio and offers one chip per municipio ("pobreza en Cuchillas, Moca"); with the municipio named, only its barrios count.

The file versions moved (`chatboot.js?v=9`, `chat.js?v=32`, `ask.js?v=3`), so a browser that kept the old files loads the new ones.

**Time to the first answer** (`ask_timing.js`, Slow 4G, three runs, medians): English 4.11 s on main and 4.14 s now; Spanish 4.33 s and 4.36 s. The chat's files are 122.1 KB and 154.9 KB compressed (main: 116.4 KB and 149.3 KB). Waiting for the page's data costs nothing measurable, because the first answer already waited for them; the index takes about 16 ms to build. The crosswalk (161 KB) is read only for a question that may name a barrio: a word after "en", "in" or "barrio" that is no municipio's and no word of the lexicon, or a short question of such words. A first version read it for "Transportation and housing", which cost 1 s. First-load scripts are unchanged: map 244.7 of 250 KB, 3D 645.4 of 700, WCRP 79.9 of 80.

**Measured.** Dev set 330 (23 new general cases, written for these kinds and not the measurement's probes): main 93.3% (308/330, 1 of the 23 new), branch 100%. Check set 81: main and branch 100%. **Replay** (2,226 test strings and the dev set, against main f414f75): the 2,226 answers are unchanged (`chat_lexicon_replay.js`: 0 changed). In the dev set, 2 earlier answers changed, both barrios now read as barrios: "pobreza en Guayabal" (island map → Guayabal, Juana Díaz, by barrio) and "desempleo en Maragüez" (island map → Maragüez, Ponce, the survey's rate by barrio). 21 of the 23 new cases changed on purpose:
  - barrios (6);
  - a reason, with counts by municipio, in place of a dataset that answered wrongly (9): health centre sites for abortion clinics, lodging listings for Airbnb hosts, vacancy rates for owners of abandoned homes, Public Assistance for FEMA aid recipients, rent beside poverty for homes of PAN recipients;
  - food stamps as a count: poverty, labelled, in place of FEMA households or all households (2);
  - rent dropped for rooftop solar (2);
  - crime by municipio for public housing (2).

  Two new cases did not change: "escuelas en el pueblo" and the FEMA addresses in Humacao, which main already answered with the reason. A question about places is no longer a privacy question: "which municipios get the most federal aid" and "who gets the most FEMA aid" were "who received aid" on main; they now rank the municipios. The browser run (`ask_chat.js`, es and en, 1400 and 390 px): 168 checks pass.

### Round 4b: the measurement of f0deed2 (2026-10-20)

The measurement found two regressions against main, and both are fixed. They are tested in `tests/ask_review.test.js` ("Round 4b") and in `tests/browser/ask_chat.js`.

- **A barrio whose name is also a topic's word.** "pobreza en el barrio Playa de Ponce" showed nothing. "Playa" was read as beaches, which the observatory lacks, and the stand-in rule then removed the poverty. Now a barrio is read first, at the start of `chRefine`. The rules and the lexicon then read the question with the barrio's words blanked, so those words never become a topic and never reach the stand-in rule. After "barrio", the name is the barrio's even when it is a topic's word. Tested with Playa (Ponce), Montaña, Río, Pueblo, Llanos, Costa, Palmas and Centro; Playita, which is not a barrio, keeps the poverty.
- **A topic before a missing word.** The same rule also removed real topics on main's questions: "pobreza en la playa", "escuelas cerca de los centros comerciales" and "ingreso cerca del mall" showed nothing. The rule now applies only when the dataset's words follow the missing topic, as in "placas solares en las casas". When the topic comes first, its dataset stays, labelled as an approximation, as on main.
- **Focus.** Closing the chat, with its close button or Escape, puts the keyboard focus back on the Ask button again. A comment had swallowed the `else` branch of `chToggle`. `ask_chat.js` checks it on the 2D map and the 3D view.
- **Optional fixes:**
  - A corrected municipio is said, as a corrected topic is ("Leí «toa vaja» como «Toa Baja»").
  - A two-word municipio is read as the whole question ("Toa Vaja", "Juana Dias"), after a stop word that begins its name ("en Las Pierdas"), and when one word is the municipio's own and the other is one edit away, even if that other word is real ("dias", "pierdas").
  - "¿cuánto se paga de alquiler / de renta?" and "pay in rent" ask the rent, not pay.
  - The privacy reason for vacant homes now applies only to owners and addresses: "dónde están las casas vacías" shows the vacancy by municipio.

**Measured.** Dev set 340 (10 new cases): branch 100%. Check set 81: 100%. Replay: the 2,226 test strings are unchanged. 8 of the 10 new dev cases changed against main, all as intended:
- 3 barrios after "barrio";
- 3 misspelt two-word municipios;
- 2 rent questions.

"vivienda en la playa" and "dónde están las casas vacías" answer as on main.

### Not done (round 4)

- A barrio on the 3D view goes to the barrio, with the municipio's figure (the columns are by municipio).
- A barrio misspelt is not read (barrio names are protected from correction, and a barrio is read only when its name is written in full).
- "Near me" does not use the location, by design.

### Línea PAS (2026-10-21; HANDOFF decision 57)

The project lead, 2026-10-21: "Añade la información que tengas de Línea PAS de ASSMCA. Lo importante es que esté documentado el source correctamente." Part of HANDOFF decision 57, approved by the project lead on 2026-10-21.

**The replies.** The crisis reply and the treatment answer to "near me" (`SENS_TEXT.crisis` and `SENS_TEXT.nearMeTx` in `site/js/ask.js`) now add, after the 988 line:

- es: "En Puerto Rico también puede llamar a la Línea PAS de ASSMCA al 1-800-981-0023 (24 horas, gratis y confidencial) o usar su chat en lineapas.assmca.pr.gov."
- en: "In Puerto Rico you can also call ASSMCA's Línea PAS at 1-800-981-0023 (24 hours, free and confidential) or use its chat at lineapas.assmca.pr.gov."

Both replies end with a source line (`chPasNote` in `site/js/chat.js`) that cites the pages stating every fact of the sentence: "Fuente: ASSMCA (assmca.pr.gov y lineapas.assmca.pr.gov), consultadas el 2026-10-21." / "Source: ASSMCA (assmca.pr.gov and lineapas.assmca.pr.gov), checked 2026-10-21.", each address linked. ASSMCA's home page states all of them (the number, 24 hours, free, confidential, the chat); the Línea PAS site states the number, 24 hours and the chat, but "gratuito y confidencial" only in its page metadata (the description), not in its visible text, so it is not the source of those two words. The glossary has the term "Línea PAS" (`dictionary_src/glossary.json`, id `linea-pas`), so "¿qué es la Línea PAS?" answers with its definition and source; a term takes one link, so it cites `https://assmca.pr.gov/linea-pas`, the page that states every fact of its definition (the number with 988, 24 hours 7 days a week, the professionals, the chat, VRS, Primera Ayuda Sicosocial and the services), and its definition does not say free or confidential. The dictionary entry `layers.chat_answers` describes the `crisis` answer and names the sources.

**Sources** (all official pages of ASSMCA, Administración de Servicios de Salud Mental y Contra la Adicción, on `.pr.gov`; opened with `curl` and a browser user agent on 2026-10-21, HTTP 200, text read):

| Page (title) | URL | What it states |
|---|---|---|
| "Línea PAS - Apoyo Emocional 24/7 \| ASSMCA Puerto Rico" | https://lineapas.assmca.pr.gov/ | 1-800-981-0023 (also shown as "Ext. 988" and with 988); "disponible las 24 horas del día, los 365 días del año"; only in the page metadata (description), not in the visible text: "Gratuito y confidencial en Puerto Rico"; Chat en Vivo with a counsellor; VRS (video relay for people with hearing conditions) 787-615-4112; offers sesión de desahogo, consejería en crisis y apoyo emocional, cernimiento preliminar psicosocial, coordinación de evaluación psiquiátrica y psicológica, tele-enlaces y referidos; serves people with suicidal behaviour and other mental health problems (depression, domestic violence, anxiety) |
| "Administración de Servicios de Salud Mental y Contra la Adicción ASSMCA" (home page) | https://assmca.pr.gov/ | "Línea PAS: Comunícate confidencialmente y libre de costo las 24 horas. Tel. 1-800-981-0023; 787-615-4112 VRS (Lenguaje de Señas para personas sordas); Chat: lineapas.assmca.pr.gov; Tel. 9-8-8" |
| "Línea PAS" (Programa Integrado de Intervención en Crisis) | https://assmca.pr.gov/linea-pas | PAS is "Primera Ayuda Sicosocial"; 1-800-981-0023 \| 988; "atendida las 24 horas los 7 días de la semana por un equipo multidisciplinario de profesionales de la salud mental"; offers orientation on mental health and addiction, preliminary psychosocial screening, crisis counselling and emotional support, coordination of psychiatric and psychological evaluation, of drug and alcohol rehabilitation and of ambulance, tele-links, referrals and follow-up |

**What was verified.** The number 1-800-981-0023 (the one in circulation: confirmed, on all three pages); 24 hours, every day; free and confidential; the chat at lineapas.assmca.pr.gov; that it offers crisis counselling and emotional support for mental health and coordinates drug and alcohol treatment; Spanish (the pages are in Spanish; the replies do not claim English service, which the pages do not state). Not used: a TDD number (1-888-672-7622) and a change to a three-digit number appear only in news and secondary documents, not on these pages. A second, non-ASSMCA government page was tried: the Departamento de Salud's documents (`salud.pr.gov`, `prevencionsuicidio.salud.pr.gov`) refused the connection from this network on 2026-10-21, so the replies rest on ASSMCA, which runs the line.

**Re-check periodically.** A crisis number must be right. Re-open the three pages and confirm the number, the hours and the chat address at least every quarter, and every time the glossary links are re-checked (`python dictionary.py --check --links`, which checks the term's link but not the number): if anything changed, update `SENS_TEXT` in `site/js/ask.js`, `CH_PAS_SRC` in `site/js/chat.js` (its pages must still state every fact of the sentence), the `linea-pas` term, the `crisis` value of `layers.chat_answers` and this table, with the new date.

### Transit stops, from PR #8 (2026-10-21)

A colleague's PR #8 (branch `fix/chat-show-asked-data`) found that the chat did not answer three kinds of question about transit stops. Its rules are ported here onto the current Ask engine, with credit to its author. The rest of PR #8 (the closest-match note and the 3D hand-over) is not part of this change: main already has its own versions of both.

- **A count of stops.** "Número de paradas de transporte colectivo en San Juan" or "how many bus stops in Caguas" now gives the count of stops and stations (`transit_stops`), with its rank: "1,186 (puesto 1 de 78…)". The stops layer is switched on too. Before, the chat only switched the layer on and moved the map. The count needs a word that asks for a count or a ranking before it: "número de", "cuántas", "how many", "most", "más". "muestra las paradas" still only switches the layer on.
- **Residents near a stop.** "How many people live near a bus stop in Caguas?" or "¿cuántos residentes viven cerca de una parada?" now gives the share of residents within a 400 m walk of a stop with a current timetable (`pop_walk_active_pct`), with the stops layer on. It does not use the straight-line share (`pop_served_active_pct`). The cause of the old answer: the datasets' own words in `ask.js` (`understand`) scored the word "near" alone. "near" is one of the `ask` words of the dataset "Residents within 10 km of a health center by road" ("near a health center"), so the chat answered with that dataset. Now words of distance (`NEARW`: near, close, cerca, cercano, lejos, far…) are never scored as a topic. A side effect, also better: "far by walking" no longer adds the road distance to a health centre.
- **Transit to work.** "transporte colectivo al trabajo", "van al trabajo en guagua" or "take the bus to work" now gives the share of workers who take public transportation to work (`commute_transit_pct`). Before, the jobs rule took "trabajo" and the answer was the jobs.

The rules are in `CONCEPTS` in `site/js/chat.js`, before the jobs rule. They load with the chat, so no page's first load grows. Typos such as "trasnsporte", "trasporte" and "colectvo" are read. The file versions moved: `chatboot.js?v=11`, `chat.js?v=34`, `ask.js?v=4`. The count rule reads the words before the stops in its function, not with a lookbehind: Safari before 16.4 cannot parse a lookbehind, and chat.js would not load at all. `tests/no_lookbehind.test.js` fails if any file in `site/js` has one.

**Measured.**
- Development set: 365 questions, 25 of them new for these three kinds, in Spanish and English, with typos. Main passes 94.2% (344/365) and this branch 100%. Main passes 4 of the 25 new cases: "show bus stops" (the layer alone), "near a health center", and two questions where main already reached the right data by another route.
- Check set (81): 100%.
- Replay: 2 of the 2,231 test strings changed. "residents near a stop with a current timetable…" now shows the walking share. "far by walking" drops the health centre's road distance. In the development set, 23 answers changed, all as intended:
  - 9 counts and rankings of stops;
  - 7 questions about residents near a stop: the walking share, in place of the health centre or of the layer alone. In one, main already showed the walking share; only the routes layer is no longer switched on beside it.
  - 7 questions about transit to work: the commuting share, in place of the jobs or of the long commutes. Two of these no longer switch the routes and stops layers on beside it.
- Browser (`ask_chat.js`, es and en, 1400 and 390 px): three new checks per language, typed into the box (the count, residents near a stop, transit to work). All 200 checks pass.

## Pages without a map (2026-10-26)

The project lead (2026-10-26): "The Ask button should always be available so people can ask questions even when in the data dictionary or in a knowledge area." The "Preguntar / Ask" button is now in the same place in the top bar (just before the views) on every page: the data dictionary, Data management, every Knowledge Area page (Housing, WCRP, route analysis, GII) and the area profiles, as on the 2D map and the 3D view.

**First load.** Each page carries only `chatboot.js` (about 1.3 KB compressed) and the button; `chat.css` and four icon names join the page's styles. `chat.js`, `ask.js`, the layer registry and, on these pages, `askpage.js` load when the pointer goes over the button, it gets the focus or it is touched, as on the map; the shared engine and the datasets load when the chat opens. No budget line was raised, but each page without a map gained about 1.3 KB of first-load script (the starter and the Spanish of its button: GII 28.1 → 29.4 of 30 KB, WCRP 76.0 → 77.3 of 80, dictionary 33.4 → 34.7 of 40, LF copy, `budget.py`); the map and the 3D view lost about 0.2 KB (a shorter starter).

**How it works.** `askpage.js` gives chat.js the same `ECON.api` as the 3D view (`ask3d.js`), over its own copy of the shared engine (`js/core/engine.js` and the files of `js/core/datasets.js`), with `mapless: true`. chat.js then:

- answers in the chat: definitions and the glossary, sources, datasets, numbers for a place, rankings, trends, comparisons, patterns, missing data, and the privacy and crisis replies (988 and the Línea PAS), all unchanged;
- never touches the map: switching layers on, moving the map, the 3D columns and resizing the map do nothing here, and no answer says it moved or switched anything (`chMapless()` guards each of them);
- gives an answer that needs the map a first, primary button, **"Ver en el mapa / Show on the map"**: `index.html#ask=<the question>` (or `3d.html#ask=` when only the 3D view has what was asked, such as 3D buildings). `chatboot.js` reads the question on the 2D map before the map rewrites its address, asks it once the map is ready, and takes it out of the address (`Chat.handOver`), as `ask3d.js` does on the 3D view. The question is capped at 400 characters, set as text, never as HTML, and never leaves the browser. The crisis reply, "near me" (`nearMe`, `nearMeTx`), a refused private location and "turn off all layers" get no such button. A handed-over question may come from any link: it never clears the map (the `clear` intent answers that a link does not turn the layers off) and is never added to the wishlist; the link keeps the page's `?lang=`;
- opens the 2D map with the answer's datasets when a button pressed afterwards needs it (the workbench, the scatter plot, a pattern's "Show on the map"), as the 3D view does.

**Page context, kept modest.** Each page has its own greeting and suggested questions. "¿Qué es esto? / What is this?" answers from what the page shows: on the dictionary, the open entry (its name and summary; "¿dónde es más alto ese dato?" then asks about that entry's dataset); elsewhere, the page's title and summary, and the "In review" notice when the page carries it. On the dictionary, "esto / this" in a question means the open entry's dataset (and "Show on the map" then opens the map with that dataset); on an area profile, "aquí / here" and "este municipio / this municipio" mean the profile's municipio. On the dictionary, links to its own entries open on the page. Data management says that the data are not changed there.

**Names.** `chat.js`'s paragraph and text helpers are now `chP` and `chTx`: the area profile has a global `P` and the dictionary a global `tx`, and classic scripts share one global scope.

**Tests.** `tests/browser/ask_chat.js` opens Ask on every page without a map, in Spanish and English, at 1400 and 390 px (`ONLY_PAGES=1` runs only these): the button before the views, the chat not loaded before use, a definition, a ranking with its numbers and "Show on the map" first, "what is this?", the 3D hand-over, the bus routes handed over to `index.html` (where the question is asked, the routes come on and the address loses `ask=`), the crisis and shelter replies with no map button, the Knowledge Area tabs in view, the focus back on the button (close and Escape), no missing Spanish and a clean console. `tests/test_budget.py` checks that every page loads `chatboot.js` and `chat.css`, has the chat's icons, and never loads `chat.js`, `ask.js` or `askpage.js` first, and that `askpage.js`'s `ECON.api` has every method chat.js calls. `ask_timing.js` measures a page without a map with `ASK_PAGE=dictionary.html`.

### Crisis words (review of PR #95, 2026-10-26)

"me quiero matar", "no quiero vivir" and "línea PAS" got "No pude relacionar eso…" and went to the wishlist. `SENS.crisis` in `ask.js` now also reads first-person forms (quiero morir, me quiero matar, matarme, no quiero (seguir) vivir, quitarme la vida, hacerme daño, ganas de morir; I want to die, kill or hurt myself, don't want to live, better off dead) and the lines named (línea PAS, 988): each gets the crisis reply, unchanged, and is never a wish. "matar" counts only of oneself; deaths and mortality stay data questions ("muertes por accidentes de tránsito", "mortalidad", "traffic deaths"), and ASSMCA alone is a data question ("¿cuántos centros de ASSMCA hay en Ponce?" answers with the treatment counts). `tests/ask.test.js` checks both sides; the development set has five new crisis cases (370 cases, 100%). Replay: core.test.js 0 changed; ask_dev.json 5 changed, the five new crisis cases (unknown → crisis). Read in context (re-review): a highway numbered 988 ("PR-988", "carretera 988") and "going to die in floods" or a hurricane are data questions (`SENS.notCrisis` blanks them before the crisis words are read); any "no quiero (seguir) vivir" ("…en este mundo", "…con este dolor", even "…en San Juan": over-triggering is the safe side), "I'm going to die" and "call 988" stay a crisis. On the 2D map too, a crisis or "near me" reply offers no 3D view, and the 3D link keeps the page's `?lang=`.

## The generated lexicon (Phase 3, item 14)

Plan: `docs/proposal-2026-10.md`, section G (J row 14). This file covers how the chat finds a dataset without a hand-written rule, and the answers added in this item.

### How a question finds a dataset

The parser in `site/js/chat.js` (`chConcepts`) tries four things in this order:

1. **Census labels.** The full labels of the survey (ACS) datasets, as before.
2. **"ask" phrases of two words or more.** These come from the dictionary entries, for example "bridges in poor condition" or "distancia a un centro de salud". They match whole, in order, and each word may be plural. They come before the rules because each phrase is the dataset's own name for itself: the rule for "poor" (poverty) must not take a word of "bridges in poor condition".
3. **The rules** (`CONCEPTS`, 90 hand-written patterns), as before.
4. **The generated lexicon.** It is used only for what the steps above left. It holds every dataset's label in English, its label in the page's Spanish (`T`), the part of each label before a comma or a parenthesis, and every `ask` phrase.
   - **Matching:** a lexicon phrase matches when all its words appear in the question in any order. A word matches itself or its plural: "puente" and "puentes" match; "médicos" does not match "medicare".
   - **When no rule named a dataset:** names of two words or more and `ask` phrases of any length count.
   - **Beside a rule's dataset:** only `ask` phrases of two words or more count. "Students" alone is a group in "rent of students with children", not the school enrollment.
   - **Limits:** each word is used once, and at most two datasets are found this way.

A dataset added to the engine is therefore askable by its name the day it is registered. An `ask` list in its dictionary entry adds the words people use for it.

**Where the words live:**
- In each dictionary entry, as `"ask": {"en": [...], "es": [...]}`.
- `dictionary.py` checks the field: lower-case phrases of three or more characters, with no question marks.
- `catalog.py` carries them in the catalog index (column `ask`). The map already loads the catalog, so the chat needs no extra file; the catalog grew by 1.7 KB.
- In October 2026, 50 entries have `ask` words. They cover the 45 datasets of items 8 to 11 that no rule named, plus health insurance, schooling and the share of need met.

**No question finds different datasets.** `node tests/chat_lexicon_replay.js` runs all 2,055 question-like strings of the main branch's `tests/core.test.js` through the parser of the main branch and through this one, both with the real datasets. It lists any question whose datasets changed and exits 1 if one did: 0 changed. Three strings gained a dataset: two test descriptions and one label of the exposure series ("Residents: Inside a Special Flood Hazard Area"), which now finds that series. The replay compares datasets, not answers: outside the test strings, three questions find a better dataset on purpose ("bridges in poor condition", "distance to a health center", "hogares de ancianos"), and a question that names two places now gets the side-by-side table. `PROBE="question|question"` prints what the parser makes of the questions given.

### New answers

- **Places side by side** (`areas`). With two places or more (up to five), the chat shows a table: the datasets named, or the population, poverty, median household income, unemployment, jobs and average pay. The headline figures are shown as published; a dataset you name is also shown as a shaded map compares it (per 1,000 residents, per resident). Puerto Rico's value is included, and each of the first three places gets a link to its area profile. A question that names two places with a dataset used to answer for the first place only. Examples: "Compare Ponce and Mayagüez", "pobreza en Ponce y Caguas".
- **Area profile** (`muni`). The answer about one place now links to its profile (`profile.html`). The link is the first button when the question says "profile", "perfil", "ficha", "everything about" or "todo sobre".
- **Composite builder** (`compose`). Two datasets or more and the word "index", "índice", "composite" or "compuesto" open the workbench's composite builder with those inputs. The chat does not choose the directions or the weights: each input opens with no direction, and the builder's button stays off until the person sets one for each. Example: "índice compuesto de pobreza y desempleo".
- **Fields of the registry** (in `unknown`). When no dataset matches but the question names a field of the registry (its name in either language, such as "medio ambiente", "health" or "public money"), the chat says how many datasets the field holds and names six of them, or says that it holds none yet. The field's example questions follow. The question also goes to the wishlist, as before.

### Not done

- **Words a rule already claims.** A one-word `ask` phrase cannot take a word from a rule. In English, "hospitals" and "number of hospitals" still find the health-care jobs, as the rules always did; in Spanish, "hospitales" (which no rule claims) finds the Medicare-certified hospitals. An English phrase that a rule does not take first ("hospitals by municipality" fails too, because the rule takes "hospitals") would need a change to the rule.
- **Optional, unbuilt:** the model-assisted chat (plan G) still needs a hosted proxy that FPR decides on.

## Ask and the topics (navigation plan, 2026-11; HANDOFF decision 81 (h))

Ask is the same pop-up on every page of the observatory, the 404 page included since navigation PR 7 (the page is served at any missing address, so it sets `<base href="/">` and loads `common.js` and `chatboot.js` like the pages without a map; `i18n_src/pages.json` "notfound").

- **On the map panel.** Whatever Ask shades or switches on is listed in the On the map panel, with its legend, and can be removed there (PR 2).
- **Topics.** A dataset answer on the 2D map offers "Abrir su tema / Open its topic", which opens the dataset's home topic in Explore (`chat.js` `chTopic`, PR 3). On pages without a map the answer hands over to the map as before (`index.html#ask=`).
- **Tabs.** Ask opens panes by their old names (`showTab('economy')`, `'layers'`), which the four tabs keep as sub-tabs (PR 4); its map actions add datasets without leaving the tab the visitor is on.
- **Analysis.** Rankings, comparisons, trends and relations state the figures and how they were computed and draw no conclusions (decision 72).

