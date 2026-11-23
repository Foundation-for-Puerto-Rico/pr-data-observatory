/* PR Data Observatory core: the datasets every page reads, and the order they are added to an engine. The Economy tab and the area profiles (profile.html) load the same
   files through this list, so a dataset added here appears in both (docs/engine.md).

     Datasets.FILES                       the files: { name, file, required }; an optional file that fails leaves its datasets out
     Datasets.apply(E, docs, muni, year)  adds the datasets of the loaded files to engine E, in order. `docs` maps a name to its parsed file (null or absent when it did not
                                          load); `muni` is municipalities.json; `year` the snapshot's year (meta.json).
     Datasets.fetchFiles(get, names)      fetches the files named (every file when names is omitted): { docs, failed }; a required file that fails rejects. The area profile
                                          fetches the files of its first field, draws it, then fetches the others and applies them all again, so the order stays the same. */
(function (name, root, factory) {
  const dep = (n) => (typeof module === 'object' && module.exports ? require('./' + n + '.js') : root.Core[n]);   // the other core modules, in Node or in a page
  const api = factory(root, dep);
  if (typeof module === 'object' && module.exports) module.exports = api; else { root.Core = root.Core || {}; root.Core[name] = api; }
})('datasets', typeof window !== 'undefined' ? window : globalThis, function (root, dep) {
  'use strict';
  const FILES = [
    { name: 'econ', file: 'economy_series.json', required: true }, { name: 'hous', file: 'housing_series.json', required: true },
    { name: 'expo', file: 'exposure_municipio.json' }, { name: 'popu', file: 'population_series.json' }, { name: 'commuting', file: 'commuting_series.json' }, { name: 'health', file: 'health_series.json' },
    { name: 'care', file: 'care_series.json' }, { name: 'svi', file: 'svi_series.json' }, { name: 'fx', file: 'facility_exposure_series.json' }, { name: 'credit', file: 'credit_series.json' }, { name: 'drought', file: 'drought_series.json' }, { name: 'storm', file: 'storm_recovery_series.json' }, { name: 'ess', file: 'essentials_series.json' }, { name: 'cut', file: 'cutoff_series.json' }, { name: 'deg', file: 'degrees_series.json' }, { name: 'crdc', file: 'school_conditions_series.json' }, { name: 'prof', file: 'proficiency_series.json' }, { name: 'prov', file: 'providers_series.json' }, { name: 'educ', file: 'education_series.json' }, { name: 'medi', file: 'medicare_series.json' },
    { name: 'infra', file: 'infrastructure_series.json' }, { name: 'bridges', file: 'bridges_series.json' }, { name: 'traffic', file: 'traffic_series.json' }, { name: 'crashes', file: 'crashes_series.json' }, { name: 'envi', file: 'environment_series.json' }, { name: 'hazard', file: 'hazard_series.json' },
    { name: 'gateways', file: 'gateway_series.json' }, { name: 'facilities', file: 'facility_series.json' }, { name: 'nonprofits', file: 'nonprofit_series.json' },
    { name: 'conditions', file: 'conditions_series.json' }, { name: 'community', file: 'community_series.json' }, { name: 'landslide', file: 'landslide_series.json' }, { name: 'heat', file: 'heat_series.json' }, { name: 'vegetation', file: 'vegetation_series.json' }, { name: 'buildings', file: 'buildings_series.json' }, { name: 'fires', file: 'fires_series.json' }, { name: 'nightheat', file: 'night_heat_series.json' }, { name: 'climb', file: 'climb_series.json' }, { name: 'slope', file: 'slope_series.json' },
    { name: 'wcrp', file: 'wcrp_rvi_barrio.json' }, { name: 'laborsex', file: 'labor_sex_series.json' }, { name: 'nightlights', file: 'nightlights_series.json' }, { name: 'broadband', file: 'broadband_series.json' }, { name: 'energy', file: 'energy_series.json' },
  ];

  function apply(E, docs, muni, year) {
    const A = dep('adapters'), d = docs;
    A.series(E, d.econ, d.hous, muni);   // the economy datasets, and every other Housing series as a dataset of its own, so housing and economy layers can be put on one map
    A.tourism(E, muni, year);
    A.snapshot(E, muni, E.snapYear);   // places in a hazard or protected area, transit stops, residents near a stop, land by plan class
    if (d.expo) A.exposure(E, { municipio: d.expo });   // residents and housing units inside a hazard, inside protected land or near transit (docs/exposure.md)
    if (d.popu) A.seriesFile(E, d.popu, { dict: 'population.', group: 'Population · ' });   // age, households, disability and veterans, from the survey (docs/small-area.md)
    if (d.commuting) A.seriesFile(E, d.commuting, { dict: 'commuting.', group: '' });   // daytime population and commuting by municipio, calculated from the Census Bureau's commuting flows (docs/commuting.md)
    if (d.health) A.snapshotFile(E, d.health, { dict: 'health.', group: 'Health care · ' });   // health center sites and shortage-area designations, from HRSA (docs/health.md)
    if (d.care) A.snapshotFile(E, d.care, { dict: 'health.', group: 'Health care · ' });   // hospitals and care facilities (CMS) and distance to a health center (care_access.py; docs/health.md)
    if (d.svi) A.snapshotFile(E, d.svi, { dict: 'svi.', group: '' });   // CDC/ATSDR Social Vulnerability Index: ranks among the 78 municipios (docs/svi.md)
    if (d.fx) A.snapshotFile(E, d.fx, { dict: 'facility_exposure.', group: '' });   // facilities, students and main roads inside FEMA's 1% flood area (docs/facility-exposure.md)
    if (d.credit) A.seriesFile(E, d.credit, { dict: 'credit.', group: '' });   // FDIC bank offices and deposits, HMDA home loans (docs/credit.md)
    if (d.drought) A.seriesFile(E, d.drought, { dict: 'drought.', group: '' });   // US Drought Monitor by municipio and year (docs/drought.md)
    if (d.storm) A.seriesFile(E, d.storm, { dict: 'storm_recovery.', group: '' });   // months for night-time light to come back after María and Fiona (docs/storm_recovery.md)
    if (d.ess) A.seriesFile(E, d.ess, { dict: 'essentials.', group: '' });   // road distance to a supermarket, pharmacy, bank, library and fire station (docs/essentials.md)
    if (d.cut) A.seriesFile(E, d.cut, { dict: 'cutoff.', group: '' });   // residents cut off from every hospital when flooded roads or poor bridges close (docs/cutoff.md)
    if (d.deg) A.seriesFile(E, d.deg, { dict: 'degrees.', group: '' });   // degrees awarded by level and field, IPEDS (docs/degrees.md)
    if (d.crdc) A.seriesFile(E, d.crdc, { dict: 'school_conditions.', group: '' });   // school conditions from the Civil Rights Data Collection (docs/school_conditions.md)
    if (d.prof) A.seriesFile(E, d.prof, { dict: 'proficiency.', group: '' });   // META-PR results by municipio (docs/proficiency.md)
    if (d.prov) A.seriesFile(E, d.prov, { dict: 'providers.', group: '' });   // health care providers by type, NPPES (docs/providers.md)
    if (d.educ) A.seriesFile(E, d.educ, { dict: 'education.', group: 'Education · ' });   // NCES via the Urban Institute; docs/education.md
    if (d.laborsex) A.seriesFile(E, d.laborsex, { dict: 'labor_sex.', group: '' });   // ACS B23001 (women_labor.py); its group sorts next to Labor force
    if (d.nightlights) A.seriesFile(E, d.nightlights, { dict: 'nightlights.', group: '' });
    if (d.broadband) A.seriesFile(E, d.broadband, { dict: 'broadband.', group: '' });   // fixed broadband by June release (FCC BDC; BEAD tiers and fiber); barrio file; docs/broadband.md
    if (d.energy) A.seriesFile(E, d.energy, { dict: 'energy.', group: '' });
    if (d.fires) A.seriesFile(E, d.fires, { dict: 'fires.', group: '' });   // vegetation fire detections by year and the last 12 months (NASA FIRMS, NOAA-20; docs/fires.md)
    if (d.medi) A.seriesFile(E, d.medi, { dict: 'health.', group: 'Health care · ' });   // Medicare enrollment every year since 2013, from CMS (docs/health.md)
    if (d.infra) A.snapshotFile(E, d.infra, { dict: 'infrastructure.', group: 'Infrastructure · ' });   // drinking water systems (EPA ECHO) and power plants (EIA-860M) (docs/infrastructure.md)
    if (d.traffic) A.seriesFile(E, d.traffic, { dict: 'infrastructure.', group: '' });
    if (d.crashes) A.seriesFile(E, d.crashes, { dict: 'infrastructure.', group: '' });   // people killed in traffic crashes by municipio and year, counts only (NHTSA FARS; docs/road-safety.md)
    if (d.bridges) A.seriesFile(E, d.bridges, { dict: 'infrastructure.', group: 'Infrastructure · ' });   // bridges and their condition every year (FHWA NBI; docs/infrastructure.md)
    if (d.envi) A.snapshotFile(E, d.envi, { dict: 'environment.', group: 'Environment · ' });   // hazard loss (FEMA NRI), landslides after María (USGS) and wetlands (USFWS NWI) (docs/environment.md)
    if (d.hazard) A.seriesFile(E, d.hazard, { dict: 'environment.', group: 'Environment · ' });   // community resilience (Census CRE) and earthquakes (USGS ComCat) every year (docs/environment.md)
    if (d.gateways) A.seriesFile(E, d.gateways, { dict: 'infrastructure.', group: 'Infrastructure · ' });   // BTS T-100, FAA, ferry census; docs/infrastructure.md
    if (d.facilities) A.snapshotFile(E, d.facilities, { dict: 'facilities.' });   // HUD, USGS, OpenStreetMap, USAC; docs/facilities.md
    if (d.nonprofits) A.snapshotFile(E, d.nonprofits, { dict: 'nonprofits.' });   // tax-exempt organizations by NTEE major group (IRS EO BMF; docs/facilities.md)
    if (d.conditions) A.snapshotFile(E, d.conditions, { dict: 'conditions.' });   // EPA, HUD CHAS, TIGER, drive time; barrio file; docs/conditions.md
    if (d.community) A.snapshotFile(E, d.community, { dict: 'community.' });   // historic places (NPS), treatment facilities (SAMHSA) (docs/community.md)
    if (d.landslide) A.snapshotFile(E, d.landslide, { dict: 'landslide.' });   // USGS; barrio file; docs/landslide.md
    if (d.heat) A.snapshotFile(E, d.heat, { dict: 'heat.' });   // Landsat; docs/heat.md
    if (d.vegetation) A.snapshotFile(E, d.vegetation, { dict: 'vegetation.' });
    if (d.buildings) A.snapshotFile(E, d.buildings, { dict: 'buildings.' });   // buildings, land under roofs, flood hazard areas (Overture; docs/buildings.md)   // NDVI (Sentinel-2; docs/vegetation.md)
    if (d.nightheat) A.snapshotFile(E, d.nightheat, { dict: 'night_heat.' });   // ECOSTRESS; docs/ecostress.md
    if (d.climb) A.snapshotFile(E, d.climb, { dict: 'climb.' });   // 3DEP; docs/climb.md
    if (d.slope) A.snapshotFile(E, d.slope, { dict: 'slope.' });   // 3DEP; docs/slope.md
    if (d.wcrp) { A.snapshotFile(E, d.wcrp, { dict: 'wcrp.', group: 'Vulnerability (WCRP) · ' }); A.levelFile(E, d.wcrp, { level: 'barrio' }); }   // WCRP vulnerability ranks: barrio values only, so no municipio has one (docs/wcrp.md)
    return E;
  }

  /** The files named (every file when `names` is omitted) through `get(file)` (a promise of the parsed file). Resolves to { docs, failed: [files that did not load] };
      a required file that fails rejects. */
  async function fetchFiles(get, names) {
    const failed = [], docs = {};
    await Promise.all(FILES.filter(f => !names || names.includes(f.name)).map(f => get('data/' + f.file).then(x => { docs[f.name] = x; }, e => { if (f.required) throw e; failed.push('data/' + f.file); docs[f.name] = null; })));
    return { docs, failed };
  }

  /** Every file through `get(file)`, then apply(). Resolves to { failed: [files that did not load] }; a required file that fails rejects. `skip`: names left out (pages that show municipios only). */
  async function load(E, get, muni, year, skip = []) {
    const { docs, failed } = await fetchFiles(get, FILES.map(f => f.name).filter(n => !skip.includes(n)));
    apply(E, docs, muni, year);
    return { failed };
  }

  /* The order of the dataset groups wherever a page lists them (the Analysis tab's datasets, Rankings, the 3D columns' menus): the ten topics of the Explore tab, in
     the order of dictionary_src/domains.json, as the layer menu has them (js/core/layers.js, docs/layers.md; decision 81 (e)). A group goes where the longest of these
     beginnings it starts with stands; a group none matches comes after the listed ones, in the order it was added. The visitor economy is always last. */
  const ORDER = ['People', 'Population · ',   // population and households
    'Jobs and employers', 'Labor force', 'Industries', 'Income and poverty', 'Workers and commuting', 'Economy · ',   // the economy
    'Public money',   // public money
    'Housing · Population', 'Housing · Housing stock', 'Housing · Households', 'Housing · Prices and incomes', 'Housing · Cost burden', 'Housing · Affordability', 'Housing · Disaster recovery', 'Housing · ',   // housing
    'Health',   // health (Health care · …, Health · …)
    'Education · ',   // education
    'Environment · Surface heat', 'Environment · Night surface heat', 'Environment · Vegetation', 'Environment · Water and air', 'Environment · Regulated', 'Environment · Wetlands', 'Land use', 'Residents · Protected', 'Housing units · Protected',   // environment and climate
    'Residents · Flood', 'Housing units · Flood', 'Residents · Sea level', 'Housing units · Sea level', 'Environment · ',   // hazards: the risk, landslide, earthquake and resilience groups
    'Transit access', 'Residents · Transit', 'Housing units · Transit', 'Infrastructure · Airports', 'Infrastructure · Street', 'Infrastructure · Climb', 'Public safety', 'Infrastructure · Emergency', 'Infrastructure · ',   // infrastructure and mobility
    'Vulnerability (WCRP)',   // communities
    '￿', 'Tourism supply'];   // the groups none matches, then the visitor economy
  const rank = (g) => { let best = -1, len = -1; ORDER.forEach((p, i) => { if (String(g).startsWith(p) && p.length > len) { best = i; len = p.length; } }); return best < 0 ? ORDER.length - 2 : best; };
  /** The group names, each once, in that order. */
  const sortGroups = (groups) => [...new Set(groups)].map((g, k) => [g, rank(g), k]).sort((a, b) => a[1] - b[1] || a[2] - b[2]).map(x => x[0]);

  return { FILES, apply, fetchFiles, load, sortGroups };
});
