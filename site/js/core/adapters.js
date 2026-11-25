/* PR Data Observatory core: adapters. An adapter reads one kind of published file and registers datasets in an engine (engine.js). Nothing else knows how a file is laid out.

     series(E, econ, hous, muni)        economy_series.json and housing_series.json: a yearly value for each municipality and Puerto Rico (the Economy tab and the Housing page)
     tourism(E, muni, snapYear)         counts of tourism listings per municipality, from the snapshot fields of municipalities.json
     snapshot(E, muni, snapYear)        nine snapshot fields of municipalities.json that sit beside the yearly series: places in a hazard or protected area, transit stops, the share of residents
                                        near a stop, the share of land by plan class
     derived(E, spec)                   a dataset computed from two others (a ratio, a difference or a sum), with its formula kept and shown
     points(E, spec)                    a list of points (listings, schools, stops) as a count for each municipality and, as its `hex` level, the same points counted in hexagons of equal area
     exposure(E, files, names)          exposure_municipio.json (and, for finer levels, exposure_barrio.json and exposure_tract.json): residents and housing units inside a hazard,
                                        inside protected land or near transit, each shaded by default as a share of the area's own residents or housing units
     seriesFile(E, doc, o)              a file in the shape of economy_series.json: population_series.json (the Population domain: windows of the survey, with margins of error)
     levelFile(E, doc, o)               acs_barrio.json, acs_tract.json and acs_blockgroup.json: the values and margins of error of areas below the municipio, added as a level of datasets that already exist
     levelsFor(ds, have)                the levels below the municipio a dataset's window offers a CSV for (ACS datasets, as far as the dictionary lists them)
     levelTable(E, key, level, o)       the table of the CSV by area of a dataset at a level (estimate, margin and "less reliable" for each window), or null; o = { name(n), municipality(id) }; the names of the areas are { es, en } objects
     snapshotFile(E, doc, o)            a file that holds one snapshot of figures for each municipality, in the arrays of economy_series.json: health_series.json (health centers and shortage areas); a variable may carry
                                        noIsland, noValue, noPerHU, dPer, classes, tag and counted (see normalize.js)

   A dataset is { key, label, group, unit, d, type, family, sources, ref, definition, years: {year: array with the island last}, ys, moe, static, time, dictId, denom, levels, ... } (docs/engine.md). */
(function (name, root, factory) {
  const dep = (n) => (typeof module === 'object' && module.exports ? require('./' + n + '.js') : root.Core[n]);   // the other core modules, in Node or in a page
  const api = factory(root, dep);
  if (typeof module === 'object' && module.exports) module.exports = api; else { root.Core = root.Core || {}; root.Core[name] = api; }
})('adapters', typeof window !== 'undefined' ? window : globalThis, function (root, dep) {
  'use strict';
  const hexbin = dep('hexbin');
  const years = (y) => Object.keys(y).map(Number).sort((a, b) => a - b);
  const WINDOW5 = { type: 'window', windowYears: 5 };   // an ACS year is the last year of a five-year window: 2024 is 2020–2024
  const isWindow = (sources) => !!sources && sources.length > 0 && sources.every(s => s === 'acs' || s === 'hs_derived');   // a series made only from ACS tables; one that mixes in a yearly count (jobs per employed resident) is not a window
  const sum = (muni, fn) => Object.values(muni).reduce((a, m) => a + (fn(m) || 0), 0);

  /** The economy file's datasets, and every other series of the Housing file as a dataset of its own (so housing and economy layers can be put on one map). */
  function series(E, econ, hous, muni) {
    const ids = econ.geo.ids, names = econ.geo.names, pr = names.length - 1;
    E.setGeo(ids, names, names.map((n, i) => i === pr ? sum(muni, m => m.land_km2) : (muni[n] || {}).land_km2));
    E.extras = econ.extras || {}; E.sources = econ.sources || {}; E.notes = econ.notes || {}; E.built = econ.built;
    E.setDeflator((econ.deflator || {}).cpi);
    const hv = Object.fromEntries(hous.vars.map(v => [v.key, v]));
    econ.vars.forEach(m => {
      const src = m.from === 'housing' ? hv[m.key] : m; if (!src || !src.years) return;
      E.add({ ...m, years: src.years, moe: src.moe, basis: src.basis, ys: years(src.years), noShare: m.noShare || m.key === 'fed_loans', dictId: (m.from === 'housing' ? 'housing.' : 'economy.') + m.key, ...(/^jobs_naics_/.test(m.key) ? { withheld: true } : {}), ...(isWindow(m.sources) ? { time: WINDOW5 } : {}) });   // withheld: the source hides small cells (QCEW), so a blank is not a zero
    });
    const HS_SRC = { pop: ['pep'], census: ['hs_census'], acs: ['acs'], derived: ['acs', 'hs_derived'], fema: ['openfema'] };
    E.sources.hs_census = hous.sources.census; E.sources.hs_derived = hous.sources.derived;
    const HS_COUNT = new Set(['census_housing_units', 'census_vacant_units', 'housing_units', 'vacant_units', 'seasonal_units', 'other_vacant_units', 'households', 'fema_ia_households']);
    hous.vars.forEach(h => {
      if (E.V[h.key]) return;
      const type = h.unit === '$' ? (h.key === 'fema_ia_amount' ? 'total$' : 'level$') : HS_COUNT.has(h.key) ? 'count' : h.unit === '%' ? 'rate' : 'ratio';
      E.add({ key: h.key, group: 'Housing · ' + h.group, label: h.label, unit: h.unit === '%' || h.unit === '$' ? h.unit : '', d: h.d, type, sources: HS_SRC[h.kind] || ['acs'], ref: h.ref, definition: h.definition, years: h.years, moe: h.moe, plain: h.key === 'median_year_built', housing: true, ...(isWindow(HS_SRC[h.kind] || ['acs']) ? { time: WINDOW5 } : {}), ys: years(h.years), dictId: 'housing.' + h.key });
    });
  }

  /** Tourism listings as one-period datasets, for every category: they join the stack so they can be shaded per resident or per km². `muni` is municipalities.json; `snapYear` the snapshot's year. */
  function tourism(E, muni, snapYear) {
    E.snapYear = snapYear;
    const pr = E.geo.pr, names = E.geo.names;
    const snap = (key, label, fn, def) => E.add({ key, group: 'Tourism supply', label, unit: '', d: 0, type: 'count', sources: ['overture'], ref: 'Overture Maps places, classified by FPR', definition: def, static: true, family: 'places', ys: [snapYear], years: { [snapYear]: names.map((n, i) => i === pr ? sum(muni, fn) : fn(muni[n] || {})) } });
    snap('tourism_places', 'Tourism places (all categories)', m => m.assets, 'Tourism listings (attractions, gastronomy, accommodations, visitor services) with confidence 0.50 or higher, places of worship excluded. A snapshot of listings, not a count of businesses.');
    snap('lodging_places', 'Lodging listings (hotels, inns, rentals)', m => (m.by_category || {}).ACCOMMODATIONS, 'Accommodation listings in the Overture places snapshot.');
    snap('gastronomy_places', 'Restaurant, bar and café listings', m => (m.by_category || {}).GASTRONOMY, 'Gastronomy listings in the Overture places snapshot.');
    snap('attractions_places', 'Attraction listings', m => (m.by_category || {}).ATTRACTIONS, 'Attraction listings (beaches, parks, museums, landmarks and similar) in the Overture places snapshot.');
    snap('visitor_services_places', 'Visitor service listings', m => (m.by_category || {}).VISITOR_SERVICES, 'Visitor-service listings (tour operators, rentals, travel services) in the Overture places snapshot.');
  }

  // ── Snapshot fields ──────────────────────────────────────────────────────
  const TK = (s) => s;   // an English text that is translated where it is shown, with T(): the language tool reads it like T()
  const SNAPSHOT_FIELDS = [
    { key: 'sfha_pct', label: TK('% of places in flood hazard area'), unit: '%', d: 1, type: 'rate', group: 'Tourism supply', family: 'places', island: { ratio: ['in_sfha', 'assets'] }, counted: 'assets', sources: ['overture', 'exp_flood'], definition: 'Share of the counted tourism places whose coordinates fall inside a FEMA Special Flood Hazard Area (1% annual chance). Listings, not businesses.' },
    { key: 'in_sfha', label: TK('Places in flood hazard area'), unit: '', d: 0, type: 'count', group: 'Tourism supply', family: 'places', island: 'sum', sources: ['overture', 'exp_flood'], definition: 'Number of counted tourism places inside a FEMA Special Flood Hazard Area (1% annual chance).' },
    { key: 'in_protected', label: TK('Places inside protected areas'), unit: '', d: 0, type: 'count', group: 'Tourism supply', family: 'places', island: 'sum', sources: ['overture', 'exp_protected'], definition: 'Number of counted tourism places inside a protected area (USGS PAD-US; proclamation boundaries are left out).' },
    { key: 'with_website', label: TK('Places with a website'), unit: '', d: 0, type: 'count', group: 'Tourism supply', family: 'places', island: 'sum', sources: ['overture'], definition: 'Number of counted tourism places that list a website.' },
    { key: 'transit_stops', label: TK('Transit stops & stations'), unit: '', d: 0, type: 'count', group: 'Transit access', island: 'sum', sources: ['exp_transit'], definition: 'Stops, stations and terminals of every kind mapped in the municipality: ATI and municipal timetables, and stops that volunteers mapped in OpenStreetMap.' },
    { key: 'pop_walk_active_pct', label: TK('% of residents within a 400 m walk of a stop with a current timetable'), unit: '%', d: 1, type: 'rate', group: 'Transit access', island: { mean: 'population_2020' }, sources: ['exp_blocks', 'exp_transit'], definition: "Share of the municipality's residents (2020 Census blocks) within a 400 m walk along mapped roads (OpenStreetMap roads, no footpaths; network.py with walknet.py) of a stop whose timetable has not expired. A block with no mapped road within 150 m is measured in a straight line." },
    { key: 'pop_walk_pct', label: TK('% of residents within a 400 m walk of a scheduled stop (incl. expired timetables)'), unit: '%', d: 1, type: 'rate', group: 'Transit access', island: { mean: 'population_2020' }, sources: ['exp_blocks', 'exp_transit'], definition: "Share of the municipality's residents (2020 Census blocks) within a 400 m walk along mapped roads of a scheduled stop, expired timetables included. A block with no mapped road within 150 m is measured in a straight line." },
    { key: 'pop_served_pct', label: TK('% of residents within 400 m (straight line) of a scheduled stop (incl. expired timetables)'), unit: '%', d: 1, type: 'rate', group: 'Transit access', island: { mean: 'population_2020' }, sources: ['exp_blocks', 'exp_transit'], definition: "Share of the municipality's residents (2020 Census blocks) within 400 m, in a straight line, of a stop that has a timetable on file, expired timetables included. Schedule-based." },
    { key: 'pop_served_active_pct', label: TK('% of residents within 400 m (straight line) of a stop with a current timetable'), unit: '%', d: 1, type: 'rate', group: 'Transit access', island: { mean: 'population_2020' }, sources: ['exp_blocks', 'exp_transit'], definition: "Share of the municipality's residents (2020 Census blocks) within 400 m, in a straight line, of a stop whose operator's timetable has not ended. Schedule-based." },
    { key: 'urban_pct', label: TK('% Suelo Urbano'), unit: '%', d: 1, type: 'rate', group: 'Land use (PUT 2015)', island: { mean: 'land_km2' }, sources: ['put2015'], definition: "Share of the municipality's land (water and roads excluded) classified Suelo Urbano in the Plan de Uso de Terrenos 2015." },
    { key: 'protected_land_pct', label: TK('% Suelo Rústico Especialmente Protegido'), unit: '%', d: 1, type: 'rate', group: 'Land use (PUT 2015)', island: { mean: 'land_km2' }, sources: ['put2015'], definition: "Share of the municipality's land classified Suelo Rústico Especialmente Protegido (ecological, agricultural or hydric) in the Plan de Uso de Terrenos 2015." },
    // the measures of the retired shading menu of the 2D map (navigation plan, decision 81 (d), 2026-11-04): each is a dataset, so s= links, Rankings and Explore reach them
    { key: 'transit_pct', label: TK("% of places within 400 m of any mapped stop"), unit: '%', d: 1, type: 'rate', group: 'Tourism supply', family: 'places', island: { mean: 'assets' }, counted: 'assets', sources: ['overture', 'exp_transit'], definition: "Share of the counted tourism places (confidence 0.50 or higher, places of worship left out) within 400 m, in a straight line, of a mapped stop of any kind (timetabled or mapped by volunteers in OpenStreetMap). The stop can be in another municipality. On the 2D map a municipality with no mapped stop of its own shows no value: it has no transit measurement, not a measured 0%." },
    { key: 'acc_walk400_pct', label: TK("% of places within a 400 m walk of a stop with a current timetable"), unit: '%', d: 1, type: 'rate', group: 'Tourism supply', family: 'places', island: { mean: 'assets' }, counted: 'assets', sources: ['overture', 'exp_transit'], definition: "Share of the counted tourism places (confidence 0.50 or higher, places of worship left out) within a 400 m walk along mapped roads of a stop whose timetable has not expired. The stop can be in another municipality. On the 2D map a municipality with no mapped stop of its own shows no value: it has no transit measurement, not a measured 0%." },
    { key: 'acc_wfreq400_pct', label: TK("% of places within a 400 m walk of a frequent stop (20+ weekday departures)"), unit: '%', d: 1, type: 'rate', group: 'Tourism supply', family: 'places', island: { mean: 'assets' }, counted: 'assets', sources: ['overture', 'exp_transit'], definition: "Share of the counted tourism places (confidence 0.50 or higher, places of worship left out) within a 400 m walk along mapped roads of a stop with 20 or more weekday departures. On the 2D map a municipality with no mapped stop of its own shows no value: it has no transit measurement, not a measured 0%." },
    { key: 'acc_walk800_pct', label: TK("% of places within an 800 m walk of a stop with a current timetable"), unit: '%', d: 1, type: 'rate', group: 'Tourism supply', family: 'places', island: { mean: 'assets' }, counted: 'assets', sources: ['overture', 'exp_transit'], definition: "Share of the counted tourism places (confidence 0.50 or higher, places of worship left out) within an 800 m walk along mapped roads of a stop whose timetable has not expired. On the 2D map a municipality with no mapped stop of its own shows no value: it has no transit measurement, not a measured 0%." },
    { key: 'acc_cur400_pct', label: TK("% of places within 400 m (straight line) of a stop with a current timetable"), unit: '%', d: 1, type: 'rate', group: 'Tourism supply', family: 'places', island: { mean: 'assets' }, counted: 'assets', sources: ['overture', 'exp_transit'], definition: "Share of the counted tourism places (confidence 0.50 or higher, places of worship left out) within 400 m, in a straight line, of a stop whose timetable has not expired. On the 2D map a municipality with no mapped stop of its own shows no value: it has no transit measurement, not a measured 0%." },
    { key: 'acc_freq400_pct', label: TK("% of places within 400 m (straight line) of a frequent stop (20+ weekday departures)"), unit: '%', d: 1, type: 'rate', group: 'Tourism supply', family: 'places', island: { mean: 'assets' }, counted: 'assets', sources: ['overture', 'exp_transit'], definition: "Share of the counted tourism places (confidence 0.50 or higher, places of worship left out) within 400 m, in a straight line, of a stop with 20 or more weekday departures. On the 2D map a municipality with no mapped stop of its own shows no value: it has no transit measurement, not a measured 0%." },
    { key: 'acc_sat400_pct', label: TK("% of places within 400 m (straight line) of a stop with Saturday service"), unit: '%', d: 1, type: 'rate', group: 'Tourism supply', family: 'places', island: { mean: 'assets' }, counted: 'assets', sources: ['overture', 'exp_transit'], definition: "Share of the counted tourism places (confidence 0.50 or higher, places of worship left out) within 400 m, in a straight line, of a stop with Saturday service. On the 2D map a municipality with no mapped stop of its own shows no value: it has no transit measurement, not a measured 0%." },
    { key: 'acc_sun400_pct', label: TK("% of places within 400 m (straight line) of a stop with Sunday service"), unit: '%', d: 1, type: 'rate', group: 'Tourism supply', family: 'places', island: { mean: 'assets' }, counted: 'assets', sources: ['overture', 'exp_transit'], definition: "Share of the counted tourism places (confidence 0.50 or higher, places of worship left out) within 400 m, in a straight line, of a stop with Sunday service. On the 2D map a municipality with no mapped stop of its own shows no value: it has no transit measurement, not a measured 0%." },
    { key: 'acc_paper_pct', label: TK("% of places near only an expired or unscheduled stop"), unit: '%', d: 1, type: 'rate', group: 'Tourism supply', family: 'places', island: { mean: 'assets' }, counted: 'assets', sources: ['overture', 'exp_transit'], definition: "Share of the counted tourism places (confidence 0.50 or higher, places of worship left out) with a mapped stop within 400 m but no stop with a current timetable within 400 m: the stop is in a feed that has ended, or mapped by volunteers with no timetable. On the 2D map a municipality with no mapped stop of its own shows no value: it has no transit measurement, not a measured 0%." },
    { key: 'gross_rent_change_pct', label: TK('Rent change 2012 → latest'), unit: '%', d: 1, type: 'rate', group: 'Housing · Prices and incomes', island: 'none', sources: ['acs'], definition: 'Change in the median gross rent between the 2008-2012 and the latest American Community Survey 5-year windows (table B25064), in each window\'s own dollars, not adjusted for inflation. No value for Puerto Rico as a whole: the file holds the change by municipio only.' },
    { key: 'uber_listed', label: TK('Uber lists service (1 = listed, 0 = not)'), unit: '', d: 0, type: 'rate', group: 'Transit access', island: 'none', sources: ['uber'], definition: '1 when the municipality appears on Uber\'s list of Puerto Rico cities on the date FPR checked it (2026-10-01), 0 when it does not. A listing, not measured coverage.' },
  ];
  const SNAPSHOT_SOURCES = { put2015: { name: 'Junta de Planificación — Plan de Uso de Terrenos 2015', license: 'Official plan of the Government of Puerto Rico; the service states no license', url: 'https://jp.pr.gov/' },
    uber: { name: 'Uber — cities served in Puerto Rico (service listing), checked 2026-10-01', license: 'Public web page; no license stated. Listed or not listed only', url: 'https://www.uber.com/global/en/r/united-states/puerto-rico/cities/' } };

  /** Fields of municipalities.json as one-period datasets. The island's value follows the rule of the field: a sum, a ratio of two sums, or a mean weighted by residents or by land. Run after series(). */
  function snapshot(E, muni, snapYear) {
    const pr = E.geo.pr, names = E.geo.names;
    Object.assign(E.sources, SNAPSHOT_SOURCES);
    for (const f of SNAPSHOT_FIELDS) {
      const vals = names.slice(0, pr).map(n => { const v = (muni[n] || {})[f.key]; return v == null ? null : typeof v === 'boolean' ? +v : v; });   // a yes/no field (uber_listed) as 1 or 0
      const island = f.island === 'none' ? null : f.island === 'sum' ? sum(muni, m => m[f.key])
        : f.island.ratio ? sum(muni, m => m[f.island.ratio[0]]) / sum(muni, m => m[f.island.ratio[1]]) * 100
          : sum(muni, m => (m[f.island.mean] || 0) * (m[f.key] || 0)) / sum(muni, m => m[f.island.mean]);
      E.add({ key: f.key, group: f.group, label: f.label, unit: f.unit, d: f.d, type: f.type, family: f.family, sources: f.sources, ref: "The observatory's municipality statistics (municipalities.json)", definition: f.definition, static: true,
        time: { type: 'snapshot' }, ys: [snapYear], years: { [snapYear]: [...vals, island] }, dictId: 'municipalities.' + f.key,
        ...(f.counted ? { counted: [...names.slice(0, pr).map(n => (muni[n] || {})[f.counted] ?? null), sum(muni, m => m[f.counted])] } : {}) });   // counted: the number each share rests on (a share of fewer than 10 places is flagged)
    }
  }

  // ── Derived ──────────────────────────────────────────────────────────────
  /** A dataset computed in the browser from two others, for the years both have: op 'ratio' (a ÷ b × scale), 'diff' (a − b) or 'sum' (a + b). The formula is kept in `derived` and written in the
      definition, so a person can see what the number is; margins of error are not carried through, and the dataset says so (reliability.js). spec = { key, label, group, of: [keyA, keyB], op, scale, unit, d, type, definition, dictId }. */
  function derived(E, spec) {
    const [A, B] = spec.of.map(k => E.V[k]); if (!A || !B) return null;
    const op = spec.op || 'ratio', ys = A.ys.filter(y => B.years[y] && A.years[y]), f = { ratio: (x, z) => z ? x / z * (spec.scale || 1) : null, diff: (x, z) => x - z, sum: (x, z) => x + z }[op];
    if (!f || !ys.length) return null;
    const out = Object.fromEntries(ys.map(y => [y, A.years[y].map((x, i) => { const z = B.years[y][i]; return x == null || z == null ? null : f(x, z); })]));
    const formula = { ratio: `${A.label} ÷ ${B.label}${spec.scale && spec.scale !== 1 ? ` × ${spec.scale}` : ''}`, diff: `${A.label} − ${B.label}`, sum: `${A.label} + ${B.label}` }[op];
    return E.add({ key: spec.key, group: spec.group || 'Derived', label: spec.label, unit: spec.unit || '', d: spec.d ?? 1, type: spec.type || (op === 'ratio' ? 'ratio' : A.type), family: 'derived', sources: [...new Set([...(A.sources || []), ...(B.sources || [])])],
      ref: `Computed in the browser: ${formula}`, definition: `${spec.definition || ''} Formula: ${formula}.`.trim(), years: out, ys, derived: { op, of: spec.of, scale: spec.scale || 1, formula }, dictId: spec.dictId });
  }

  // ── Points ───────────────────────────────────────────────────────────────
  /** A list of points that carry a municipality as a dataset: how many there are in each municipality (the island last), and, as the `hex` level, how many there are in each hexagon of equal area.
      spec = { key, label, group, points: [{ lat, lng, municipality }], filter(point), sources, ref, definition, dictId, snapYear }. The municipality counts are made when this runs; the hexagons are counted
      each time the series is asked for, with `filter` as it is then, so a user's filters apply. E.series({ key, hex: { area } }, null, 'hex') returns one value for each hexagon that holds a point. */
  function points(E, spec) {
    const pr = E.geo.pr, names = E.geo.names, at = new Map(names.map((n, i) => [n, i])), snapYear = spec.snapYear || E.snapYear, pass = () => spec.points.filter(spec.filter || (() => true));
    const counts = new Array(pr + 1).fill(0);
    for (const p of pass()) { const i = at.get(p.municipality); if (i != null && i < pr) { counts[i]++; counts[pr]++; } }
    return E.add({ key: spec.key, group: spec.group, label: spec.label, unit: '', d: 0, type: 'count', family: spec.family || 'places', sources: spec.sources || [], ref: spec.ref, definition: spec.definition, static: true, time: { type: 'snapshot' },
      ys: [snapYear], years: { [snapYear]: counts }, dictId: spec.dictId,
      levels: { hex: { series: (E, L, r) => {
        const b = hexbin.bin(pass(), { area: (L.hex && L.hex.area) || 10 });
        return { ids: b.cells.map(c => c.id), names: null, values: b.cells.map(c => c.n), moe: null, flags: { exact: true, early: false, noValue: b.cells.map(() => false) },
          meta: { key: spec.key, level: 'hex', period: r.y, timeType: 'snapshot', unit: '', decimals: 0, label: spec.label, norm: 'value', island: b.cells.reduce((t, c) => t + c.n, 0), cell: { km2: b.km2 }, method: 'points counted in each hexagon; hexagons are equal-area' } };
      } } } });
  }

  // ── Exposure ─────────────────────────────────────────────────────────────
  const MEASURE = { pop: 'Residents', hu: 'Housing units' };   // the Spanish of the labels built from these is in i18n_src/es/labels_exposure.json (written by exposure.py)
  const SHARE = { pop: "% of the area's residents", hu: "% of the area's housing units" };
  const EXPOSURE_SOURCES = {   // as in dictionary_src/sources.json
    exp_blocks: { name: 'US Census Bureau — TIGERweb boundaries and counts', license: 'US Government work (no US copyright)', url: 'https://www.census.gov/data/developers/data-sets/TIGERweb-map-service.html' },
    exp_flood: { name: 'FEMA National Flood Hazard Layer (NFHL)', license: "US Government work; FEMA's metadata lists no access constraints", url: 'https://www.fema.gov/flood-maps/national-flood-hazard-layer' },
    exp_slr: { name: 'NOAA — Sea Level Rise Viewer', license: "No license stated; NOAA's disclaimer applies", url: 'https://coast.noaa.gov/slr/' },
    exp_surge: { name: 'NOAA National Hurricane Center — SLOSH storm surge maps (Maximum of MEOWs, high tide)', license: 'Public domain (NHC)', url: 'https://www.nhc.noaa.gov/nationalsurge/' },
    exp_protected: { name: 'USGS — PAD-US 4.1 (protected areas)', license: 'US public domain (USGS)', url: 'https://www.usgs.gov/programs/gap-analysis-project/science/pad-us-data-overview' },
    exp_transit: { name: 'Public transit timetables (ATI and municipal GTFS) and OpenStreetMap stops', license: 'ATI open-data terms; municipal feeds state no license; OpenStreetMap is ODbL 1.0', url: 'https://www.ati.pr.gov/relaciones-comunidad?tab=DatosAbiertos' },
  };
  const EXPOSURE_FROM = { flood: ['exp_blocks', 'exp_flood'], slr: ['exp_blocks', 'exp_slr'], low: ['exp_blocks', 'exp_slr'], surge: ['exp_blocks', 'exp_surge'], protected: ['exp_blocks', 'exp_protected'], transit: ['exp_blocks', 'exp_transit'] };

  /** The datasets of the exposure series. `files` is { municipio, barrio?, tract? }: the files exposure.py writes. `names` is optional ({ barrio: [...], tract: [...] }, in the order of each file's ids)
      and only labels the places of a finer level. Counts of residents and housing units are shaded as a share of the area's own total; no page needs the finer levels yet, but
      E.series(layer, period, 'barrio') answers when the files are given. Run after series(), which sets the places. */
  function exposure(E, files, names) {
    const m = files.municipio, n = E.geo.pr, at = new Map(E.geo.ids.map((id, i) => [id, i])), year = +String(m.as_of).slice(0, 4);
    const align = (arr) => { const out = new Array(n + 1).fill(null); m.geo.ids.forEach((id, j) => { const i = at.get(id); if (i != null && i < n) out[i] = arr[j]; }); out[n] = arr.reduce((a, x) => a + x, 0); return out; };
    Object.assign(E.sources, EXPOSURE_SOURCES);
    for (const meas of ['pop', 'hu']) {
      const total = align(m.total[meas]);
      for (const [fam, v] of Object.entries(m.vars)) {
        const finer = {};
        for (const level of ['barrio', 'tract']) if (files[level]) finer[level] = levelOf(files[level], level, fam, meas, v, year, names && names[level]);
        E.add({
          key: `exp_${fam}_${meas}`, group: `${MEASURE[meas]} · ${m.groups[v.group].en}`, label: `${MEASURE[meas]}: ${v.label.en}`, unit: '', d: 0, type: 'count', family: 'exposure', sources: EXPOSURE_FROM[v.group],
          ref: `Exposure series: 2020 Census blocks counted by their internal point (${m.inputs[v.group] || m.inputs.blocks})`,
          definition: `${MEASURE[meas]} (2020 Census) of the municipality that live in census blocks whose internal point is: ${v.label.en.charAt(0).toLowerCase()}${v.label.en.slice(1)}. ${m.basis.en} The dictionary entry gives the method and its limits.`,
          static: true, time: { type: 'snapshot', asOf: m.as_of }, ys: [year], years: { [year]: align(v[meas]) }, denom: { total, label: SHARE[meas] }, dictId: `exposure.${meas}_${v.group}`,
          levels: Object.keys(finer).length ? finer : undefined,
        });
      }
    }
  }
  // ── A series file, and the finer levels of a dataset (plan item 7) ───────────
  /** The datasets of a file in the shape of economy_series.json: { years: [..], geo: { ids }, vars: [{ key, group, label, unit, d, type, sources, ref, definition, family, years: {window: array}, moe }] },
      for the 78 municipios and Puerto Rico (the last id). The arrays are put in the order of the engine's places (the order of the file is looked up, not assumed); an empty value stays empty.
      A dataset made only from survey tables is a five-year window (labeled by the years it covers), as in series(). o = { dict: prefix of the dictionary ids ('population.'), group: text put before each
      group ('Population · ') }. Run after series(), which sets the places. */
  function seriesFile(E, doc, o = {}) {
    const at = new Map(E.geo.ids.map((id, i) => [id, i])), n = E.geo.pr + 1;
    const align = (arr) => { const out = new Array(n).fill(null); doc.geo.ids.forEach((id, j) => { const i = at.get(id); if (i != null) out[i] = arr[j] == null ? null : arr[j]; }); return out; };
    const each = (o2) => Object.fromEntries(Object.entries(o2).map(([y, arr]) => [y, align(arr)]));
    Object.assign(E.sources, doc.sources || {});
    for (const v of doc.vars) {
      const years = each(v.years);
      E.add({ ...v, group: (o.group || '') + v.group, years, moe: v.moe ? each(v.moe) : undefined, ys: Object.keys(years).map(Number).sort((p, q) => p - q), ...(isWindow(v.sources) ? { time: WINDOW5 } : {}), built: doc.built, dictId: (o.dict || '') + v.key });
    }
  }

  /** A level below the municipio for the datasets that a file holds values for: { level, windows, geo: { ids }, vars: [{ key, years: {window: array}, moe: {window: array} }] } (small_area.py). Each variable keeps
      the key of the dataset it is a level of, so E.series({ key }, period, 'tract') answers beside the municipal values, which are untouched. The array of a window is in the order of geo.ids and has no
      value for Puerto Rico. A period before the first window gets the first (flagged early), a period after the last gets the last. Only "as published" and the percentile among the areas of the level are
      offered at a level: the rescalings of a municipio (per resident, per km²) need the residents and the land of each area. `names` (optional) is the name of each id. */
  function levelFile(E, doc, o = {}) {
    const level = o.level || doc.level, ids = doc.geo.ids, names = o.names || null, stats = dep('stats');
    for (const v of doc.vars) {
      const ds = E.V[v.key]; if (!ds) continue;
      const ys = Object.keys(v.years).map(Number).sort((p, q) => p - q);
      const whyAt = new Map(); (v.noValueWhy || []).forEach(w => (w.ids || []).forEach(id => whyAt.set(id, w.why)));   // noValueWhy: [{ why, ids }], why some areas are empty when it is not the dataset's noValue (a barrio with no residents: landslide.py)
      const why = whyAt.size ? ids.map(id => whyAt.get(id) || null) : null;
      ds.levels = { ...(ds.levels || {}), [level]: { ids, ys, series(E, L, r, period) {
        const want = period == null ? ys[ys.length - 1] : period, y = ys.filter(x => x <= want).pop() ?? ys[0], vals = v.years[y], pct = L.norm === 'pctile';
        const a = pct ? stats.percentiles(vals, vals.length) : vals;
        return { ids, names, values: a, moe: pct ? null : (v.moe ? v.moe[y] : null), flags: { exact: y === want, early: want < ys[0], noValue: a.map(x => x == null), why: why && a.map((x, i) => x == null ? why[i] : null) },
          meta: { key: ds.key, level, period: y, timeType: (ds.time && ds.time.type) || (ds.barrioFile ? 'period' : 'window'), unit: pct ? '' : ds.unit, decimals: pct ? 0 : ds.d, label: ds.label, norm: pct ? 'pctile' : 'value' } };
      } } };
    }
  }

  /** The levels below the municipio that a dataset's window offers a CSV for. `have` is what the dictionary lists for the entry (the catalog index); only datasets made from ACS tables are offered them,
      because those are the ones the level files hold: the dictionary also lists the exposure datasets at barrio and tract, from files the Economy tab does not read. */
  function levelsFor(ds, have) { return ds && !ds.level && Array.isArray(ds.sources) && ds.sources.includes('acs') ? ['barrio', 'tract', 'block-group'].filter(l => (have || []).includes(l)) : []; }

  /** The table of the CSV by area of a dataset at a level: one row for each area and, for each window, the estimate, its margin of error and "less reliable" (a margin above 30% of the estimate, or a share of exactly 100%,
      which has no margin and would otherwise read as exact); then the variable, its unit and dictionary entry, the source and, where a margin is missing, why. o = { name(n): an area's name in the page language, municipality(id): the name of its municipio }.
      Null when the dataset has no values at the level. */
  const UNIT_WORDS = { acs_population: TK('people'), housing_units: TK('housing units'), households: TK('households'), avg_household_size: TK('people per household'), median_age: TK('years'), median_year_built: TK('year'), gini: TK('index from 0 to 1') };   // the variables that have no unit symbol
  function levelTable(E, key, level, o = {}) {
    const v = E.V[key], lv = v && v.levels && v.levels[level]; if (!lv) return null;
    const { T } = dep('text'), reliability = dep('reliability'), hasM = !!v.moe, share = v.unit === '%', name = o.name || ((n) => n && n.en), mun = o.municipality || (() => '');
    const win = (y) => v.time && v.time.type === 'window' ? `${y - 4}–${y}` : String(y);
    const per = lv.ys.map(y => E.series({ key }, y, level)), first = per[0], marginOf = (s, i) => s.moe ? s.moe[i] : null;
    const rough = (s, i) => { const x = s.values[i]; return x != null && (reliability.isUnreliable(x, marginOf(s, i)) || (share && x === 100 && marginOf(s, i) == null)); };
    const blank = (i) => hasM && per.some(s => s.values[i] != null && marginOf(s, i) == null);
    const header = ['GEOID', T('Area'), T('Municipality'), ...lv.ys.flatMap(y => hasM ? [win(y), T('{year} margin of error', { year: win(y) }), T('{year} less reliable', { year: win(y) })] : [win(y)]), T('Variable'), T('Unit'), T('Dictionary entry'), T('Source'), ...(hasM ? [T('Note')] : [])];
    const unit = v.unit === '%' ? T('percent') : v.unit === '$' ? T('US dollars of the last year of each window') : T(UNIT_WORDS[key] || TK('count')), src = T('US Census Bureau, American Community Survey 5-year estimates; margins of error at 90% confidence; neighboring windows share four of their five years'), why = T('A blank margin of error means that none is published: the Census Bureau controls the figure, or the share is exactly 100%, or its margin works out to zero (which would read as exact).');
    const rows = first.ids.map((id, i) => [id, name(first.names && first.names[i]) || '', mun(id), ...per.flatMap(s => hasM ? [s.values[i], marginOf(s, i), rough(s, i) ? T('yes') : ''] : [s.values[i]]), T(v.label), unit, v.dictId || '', src, ...(hasM ? [blank(i) ? why : ''] : [])]);
    return { header, rows };
  }

  // ── A snapshot series file ───────────────────────────────────────────────
  /** The datasets of a file that holds one snapshot of figures for each municipality, written by a script in the shape of economy_series.json: { as_of, years: [year], geo: { ids }, vars: [...], sources }.
      health_series.json is the first (health_series.py). The arrays are put in the order of the engine's places (the order of the file is looked up, not assumed); a value the file leaves empty stays empty
      (a score is not a zero); the island's value is what the file says, and a dataset the file marks `noIsland` has none (a score is not added or averaged, so it offers no index or difference from Puerto Rico).
      o = { dict: prefix of the dictionary ids ('health.'), group: text put before each group ('Health care · ') }. Run after series(), which sets the places. */
  function snapshotFile(E, doc, o = {}) {
    const at = new Map(E.geo.ids.map((id, i) => [id, i])), n = E.geo.pr + 1;
    const align = (arr) => { const out = new Array(n).fill(null); doc.geo.ids.forEach((id, j) => { const i = at.get(id); if (i != null) out[i] = arr[j] == null ? null : arr[j]; }); return out; };
    Object.assign(E.sources, doc.sources || {});
    for (const v of doc.vars) {
      const years = Object.fromEntries(Object.entries(v.years).map(([y, arr]) => [y, align(arr)]));
      E.add({ ...v, group: (o.group || '') + v.group, years, ys: Object.keys(years).map(Number).sort((p, q) => p - q), static: true, time: { type: 'snapshot', asOf: doc.as_of }, built: doc.built, dictId: (o.dict || '') + v.key });   // `built`: the day the file was made, shown in the dataset's window instead of the economy file's
    }
  }

  function levelOf(file, level, fam, meas, v, year, names) {
    const at = file.geo.ids, values = file.vars[fam][meas], total = file.total[meas];
    return { ids: at, series(E, L, r) {
      const share = L.norm === 'shareArea', a = values.map((x, i) => share ? (total[i] ? x / total[i] * 100 : null) : x), island = values.reduce((s, x) => s + x, 0), all = total.reduce((s, x) => s + x, 0);
      return { ids: at, names: names || null, values: a, moe: null, flags: { exact: true, early: false, noValue: a.map(x => x == null) },
        meta: { key: `exp_${fam}_${meas}`, level, period: year, timeType: 'snapshot', unit: share ? '%' : '', decimals: share ? 1 : 0, label: v.label.en, norm: share ? 'shareArea' : 'value', island: share ? (all ? island / all * 100 : null) : island, total } };
    } };
  }

  return { series, tourism, snapshot, derived, points, exposure, seriesFile, levelFile, levelsFor, levelTable, snapshotFile, SNAPSHOT_FIELDS, EXPOSURE_SOURCES };
});
