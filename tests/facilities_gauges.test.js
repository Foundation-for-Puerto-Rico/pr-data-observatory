/* The gauge layers of core/facilities.js: Reservoir levels, River flow, Groundwater levels and Rainfall. The live reading, its unit, the usual range and the pop-up, on the published files.
     node --test tests/facilities_gauges.test.js */
const test = require('node:test');
const assert = require('node:assert');
const fs = require('fs');
const path = require('path');

const F = require('../site/js/core/facilities.js');
const DATA = path.join(__dirname, '..', 'site', 'data');
const load = (f) => JSON.parse(fs.readFileSync(path.join(DATA, f), 'utf8'));
const answer = (rows) => async () => ({ ok: true, json: async () => ({ features: rows.map(p => ({ properties: p })) }) });

test('River flow is a layer of its own, with a switch, a file, a help text and a live parameter', () => {
  const L = F.LAYERS.rivers;
  assert.strictEqual(L.id, 'lyRivers');
  assert.strictEqual(L.file, 'river_gauges.geojson');
  assert.ok(F.HELP_TEXT.fac_rivers && /None of this is a flood warning/.test(F.HELP_TEXT.fac_rivers[1]), 'the help says what the layer is not');
  assert.deepStrictEqual(Object.keys(F.GAUGE), ['reservoirs', 'rivers', 'groundwater', 'rain'], 'the four layers that read USGS live');
  assert.strictEqual(F.GAUGE.rivers.code, '00060');
  assert.ok(F.TYPES.includes('River gauge'), 'the type the file holds is translated');
});

test('the live reading of a river: one request with every gauge, cubic feet per second turned into m³/s; a failure keeps the file\'s flows', async () => {
  const d = load('river_gauges.geojson'), a = d.features[0].properties, b = d.features[1].properties;
  const asked = [];
  const old = global.fetch;
  try {
    global.fetch = async (url) => { asked.push(url); return answer([{ monitoring_location_id: a.usgs, time: '2026-11-11T14:30:00+00:00', value: '100' }, { monitoring_location_id: b.usgs, time: '2026-11-11T14:30:00+00:00', value: null }])(); };
    await F.live('rivers', d);
    assert.strictEqual(asked.filter(u => u.includes('parameter_code=00060')).length, 1);
    assert.strictEqual(asked.filter(u => u.includes('parameter_code=00065')).length, 1, 'the gauge heights, in one more request');
    assert.ok(Math.abs(a.liveMore.stage.v - 30.48) < 1e-9, '100 ft is 30.48 m');
    assert.ok(asked[0].includes('parameter_code=00060') && asked[0].includes(a.usgs) && asked[0].includes(d.features[d.features.length - 1].properties.usgs));
    assert.ok(Math.abs(a.live.level - 2.83168) < 1e-9, '100 ft³/s is 2.83 m³/s');
    assert.strictEqual(b.live, undefined, 'a gauge with no value keeps the file\'s reading');
    assert.ok(d.liveAt && !d.liveFailed);
    await F.live('rivers', d);
    assert.strictEqual(asked.filter(u => u.includes('parameter_code=00060')).length, 1, 'not asked again within ten minutes');

    const d2 = load('river_gauges.geojson');
    global.fetch = async () => ({ ok: false, status: 429 });
    await F.live('rivers', d2);
    assert.ok(d2.liveFailed && !d2.features.some(f => f.properties.live));
    assert.match(F.noteText('rivers', d2, ''), /could not be loaded/);

    const r = load('reservoirs.geojson'), r0 = r.features[0].properties;
    global.fetch = async (url) => { asked.push(url); return answer([{ monitoring_location_id: r0.usgs, time: '2026-11-11T14:30:00+00:00', value: '41.5' }])(); };
    await F.live('reservoirs', r);
    assert.ok(asked[asked.length - 1].includes('parameter_code=72376'));
    assert.strictEqual(r0.live.level, 41.5, 'a reservoir level is in meters already');
    await F.live('fire', {});
    assert.strictEqual(asked.length, 3, 'the other layers ask nothing: the river flows, the river levels and the reservoirs');
  } finally { global.fetch = old; }
});

test('the pop-up of every river gauge: the flow, its unit, the usual range, the chart, the warning that it is no flood warning, the USGS station', () => {
  const d = load('river_gauges.geojson');
  for (const f of d.features) {
    const p = f.properties, html = F.popup('rivers', { usgs: p.usgs }, d);   // the 3D view hands over the id; the pop-up reads the file's feature
    assert.ok(html.includes(p.name.replace(/&/g, '&amp;')), p.usgs);
    assert.match(html, /m³\/s \(cubic meters of water per second\)/);
    assert.match(html, /A flow higher than usual is not a flood warning\./);
    assert.ok(html.includes('https://waterdata.usgs.gov/monitoring-location/' + p.usgs + '/'));
    assert.match(html, /(Lower than usual|Usual|Higher than usual) for this time of year|No usual range for this week/);
    assert.ok(!/NaN|undefined|Infinity/.test(html), p.usgs + ': no broken number');
    if (p.recent.filter(v => v != null).length > 1) assert.match(html, /<svg class="res-spark"/);
  }
});

test('a flow of zero or far above the usual range still draws (the chart\'s scale is logarithmic)', () => {
  const d = load('river_gauges.geojson'), p = d.features[0].properties;
  for (const v of [0, 0.004, 5000]) {
    p.live = { level: v, time: new Date(Date.parse(p.recent_start + 'T12:00:00Z') + 119 * 864e5).toISOString() };
    const html = F.popup('rivers', p, d);
    assert.ok(!/NaN|Infinity/.test(html), 'flow ' + v);
    assert.match(html, /<circle /);
  }
  p.live = { level: 5000, time: p.flow_time };
  assert.match(F.popup('rivers', p, d), /Higher than usual for this time of year/);
});

test('the reservoir pop-up is what it was: meters above mean sea level, a 7-day change, a linear chart', () => {
  const d = load('reservoirs.geojson'), p = d.features[0].properties, html = F.popup('reservoirs', p, d);
  assert.match(html, /m above mean sea level/);
  assert.ok(!/m³\/s|flood warning/.test(html));
  assert.match(html, /aria-label="Level over the last 120 days/);
});

test('the note under the switch counts the gauges and the rivers', () => {
  const d = load('river_gauges.geojson');
  assert.match(F.noteText('rivers', d, ''), new RegExp('^' + d.features.length + ' gauges on ' + d.notes.rivers + ' rivers and streams\\. Loading'));
});


test('a river gauge with flood reference levels: the pop-up says how far the water is from each, lowest first', () => {
  const d = load('river_gauges.geojson'), f = d.features.find(x => x.properties.refs);
  assert.ok(f, 'the file has a gauge with flood reference levels');
  const p = JSON.parse(JSON.stringify(f.properties));
  p.stage = 1; p.refs = [{ kind: 'bank', label: '', level: 3.5 }, { kind: 'deck', label: 'Bridge Deck', level: 5 }, { kind: 'mystery', label: 'X', level: 0.4 }];
  assert.deepStrictEqual(F.floodRefs(p).map(r => [r.kind, r.gap]), [['bank', 2.5], ['deck', 4], ['other', -0.6]]);
  p.liveMore = { stage: { v: 4, time: '2026-11-12T10:00:00+00:00' } };
  assert.deepStrictEqual(F.floodRefs(p).map(r => r.gap), [-0.5, 1, -3.6], 'the live level replaces the file\'s');
  const html = F.popup('rivers', p, { features: [{ properties: p }], vintage: '2026-11-12', notes: {} });
  assert.match(html, /Water level on the gauge: 4\.00 m/);
  assert.match(html, /Flood reference levels at this gauge/);
  assert.match(html, /Top of the riverbank: the water is at or above it, by 0\.50 m/);
  assert.match(html, /Deck of the bridge \(the road\) <span translate="no">\(Bridge Deck\)<\/span>: 1\.00 m above the water now/);
  assert.match(html, /do not replace a warning from the National Weather Service/);
  delete p.refs; delete p.stage; delete p.liveMore;
  assert.deepStrictEqual(F.floodRefs(p), []);
  assert.doesNotMatch(F.popup('rivers', p, { features: [{ properties: p }], vintage: '2026-11-12', notes: {} }), /Flood reference levels|Water level on the gauge/);
});

test('Groundwater levels is a layer of its own: a switch, a file, a help text, a live parameter in feet', () => {
  const L = F.LAYERS.groundwater;
  assert.strictEqual(L.id, 'lyGroundwater');
  assert.strictEqual(L.file, 'groundwater.geojson');
  assert.ok(F.HELP_TEXT.fac_groundwater && /one point of one aquifer/.test(F.HELP_TEXT.fac_groundwater[1]), 'the help says what a well shows');
  assert.deepStrictEqual(F.GAUGE.groundwater, { code: '72019', k: 0.3048 });
  assert.ok(F.TYPES.includes('Groundwater well'), 'the type the file holds is translated');
});

test('the live reading of a well: one request, feet turned into meters; a failure keeps the depths of the file', async () => {
  const d = load('groundwater.geojson'), a = d.features[0].properties;
  const asked = [], old = global.fetch;
  try {
    global.fetch = async (url) => { asked.push(url); return answer([{ monitoring_location_id: a.usgs, time: '2026-11-12T14:30:00+00:00', value: '10' }])(); };
    await F.live('groundwater', d);
    assert.strictEqual(asked.length, 1);
    assert.ok(asked[0].includes('parameter_code=72019') && asked[0].includes(d.features[d.features.length - 1].properties.usgs));
    assert.ok(Math.abs(a.live.level - 3.048) < 1e-9, '10 ft is 3.05 m');
    const d2 = load('groundwater.geojson');
    global.fetch = async () => ({ ok: false, status: 429 });
    await F.live('groundwater', d2);
    assert.ok(d2.liveFailed && !d2.features.some(f => f.properties.live));
    assert.match(F.noteText('groundwater', d2, ''), /could not be loaded/);
  } finally { global.fetch = old; }
});

test('the pop-up of every well: the depth, its unit, the usual range or its absence, the chart, what a well shows, the USGS station', () => {
  const d = load('groundwater.geojson');
  for (const f of d.features) {
    const p = f.properties, html = F.popup('groundwater', { usgs: p.usgs }, d);   // the 3D view hands over the id; the pop-up reads the file's feature
    assert.ok(html.includes(p.name.replace(/&/g, '&amp;')), p.usgs);
    assert.match(html, /Water -?[\d.]+ m below the ground/);
    assert.match(html, /A well shows the water at one point of an aquifer\./);
    assert.ok(html.includes('https://waterdata.usgs.gov/monitoring-location/' + p.usgs + '/'));
    assert.match(html, /Water (lower|higher) than usual for this time of year|Usual for this time of year|No usual range for this week/);
    assert.ok(!/NaN|undefined|Infinity|m³\/s|flood/.test(html), p.usgs + ': no broken number, nothing of the river pop-up');
    if (p.recent.filter(v => v != null).length > 1) assert.match(html, /<svg class="res-spark"/);
  }
  assert.match(F.noteText('groundwater', d, ''), new RegExp('^' + d.features.length + ' wells in ' + d.notes.municipios + ' municipios\. Loading'));
});

test('a depth is read upside down: deeper water is lower than usual, and it is drawn lower on the chart', () => {
  const d = load('groundwater.geojson'), f = d.features.find(x => x.properties.p10.every(v => v != null));
  assert.ok(f, 'the file has a well with a usual range');
  const p = f.properties, t = new Date(Date.parse(p.recent_start + 'T12:00:00Z') + 119 * 864e5).toISOString(), w = F.weekOf(t.slice(0, 10));
  const cy = (html) => +html.match(/<circle cx="[\d.]+" cy="([\d.]+)"/)[1];
  p.live = { level: p.p90[w] + 5, time: t };
  const deep = F.popup('groundwater', p, d);
  assert.match(deep, /Water lower than usual for this time of year/);
  p.live = { level: Math.max(p.p10[w] - 5, -1), time: t };
  const shallow = F.popup('groundwater', p, d);
  assert.match(shallow, /Water higher than usual for this time of year/);
  assert.ok(cy(deep) > cy(shallow), 'the deeper reading is lower on the chart');
  p.live = { level: (p.p10[w] + p.p90[w]) / 2, time: t };
  assert.match(F.popup('groundwater', p, d), /<b>Usual for this time of year<\/b>/);
  const back = p.recent[119 - 7];
  if (back != null) {
    p.live = { level: back - 1, time: t };
    assert.match(F.popup('groundwater', p, d), /The water rose 1\.00 m in 7 days/);
    p.live = { level: back + 0.5, time: t };
    assert.match(F.popup('groundwater', p, d), /The water fell 0\.50 m in 7 days/);
    p.live = { level: back, time: t };
    assert.match(F.popup('groundwater', p, d), /The water is where it was 7 days ago/);
  }
});

test('Rainfall is a layer of its own: a switch, a file, a help text, and a live parameter that is added up', () => {
  const L = F.LAYERS.rain;
  assert.strictEqual(L.id, 'lyRain');
  assert.strictEqual(L.file, 'rain_gauges.geojson');
  assert.ok(F.HELP_TEXT.fac_rain && /not a flood warning or a forecast/.test(F.HELP_TEXT.fac_rain[1]), 'the help says what the layer is not');
  assert.deepStrictEqual(F.GAUGE.rain, { code: '00045', k: 25.4, sum: true });
  assert.ok(F.TYPES.includes('Rain gauge'), 'the type the file holds is translated');
});

test('the live rain: the last 24 hours added up from CSV, inches turned into millimeters, then the daily totals; a failure is said', async () => {
  const d = load('rain_gauges.geojson'), a = d.features[0].properties, b = d.features[1].properties;
  const asked = [], old = global.fetch;
  try {
    global.fetch = async (url) => {
      asked.push(url);
      if (url.includes('/continuous/')) return { ok: true, text: async () => `x,y,monitoring_location_id,time,value\r\n,,${a.usgs},2026-11-12 10:00:00+00:00,0.10\r\n,,${a.usgs},2026-11-12 10:15:00+00:00,0.40\r\n,,${a.usgs},2026-11-12 10:30:00+00:00,\r\n,,USGS-0,2026-11-12 10:30:00+00:00,9\r\n` };
      return answer([{ monitoring_location_id: a.usgs, time: '2026-11-11', value: '1.00' }, { monitoring_location_id: a.usgs, time: '2026-11-10', value: null }])();
    };
    await F.live('rain', d);
    assert.strictEqual(asked.length, 2, 'two requests: the readings of 24 hours and the daily totals');
    assert.ok(asked[0].includes('/continuous/items?parameter_code=00045') && asked[0].includes('f=csv') && asked[0].includes(a.usgs) && asked[0].includes(d.features[d.features.length - 1].properties.usgs));
    assert.ok(asked[1].includes('/daily/items?parameter_code=00045') && asked[1].includes('statistic_id=00006'));
    assert.ok(Math.abs(a.live.level - 12.7) < 1e-9, '0.5 in is 12.7 mm');
    assert.strictEqual(a.live.n, 2, 'an empty reading is not counted');
    assert.strictEqual(a.live.time, '2026-11-12T10:15:00+00:00');
    assert.strictEqual(b.live, undefined, 'a gauge with no reading has no total');
    assert.deepStrictEqual(a.liveDays, { '2026-11-11': 25.4 });
    assert.ok(d.liveAt && !d.liveFailed);
    await F.live('rain', d);
    assert.strictEqual(asked.length, 2, 'not asked again within ten minutes');

    const d2 = load('rain_gauges.geojson');
    global.fetch = async () => ({ ok: false, status: 429 });
    await F.live('rain', d2);
    assert.ok(d2.liveFailed && !d2.features.some(f => f.properties.live));
    assert.match(F.noteText('rain', d2, ''), /could not be loaded/);

    const d3 = load('rain_gauges.geojson'), c = d3.features[0].properties;
    global.fetch = async (url) => url.includes('/continuous/') ? { ok: true, text: async () => `x,y,monitoring_location_id,time,value\r\n,,${c.usgs},2026-11-12 10:00:00+00:00,0.00\r\n` } : { ok: false, status: 500 };
    await F.live('rain', d3);
    assert.ok(!d3.liveFailed && c.live.level === 0 && !c.liveDays, 'the daily totals failing keeps the 24 hours and the file’s days');
  } finally { global.fetch = old; }
});

test('the rain of the last 7 whole days: USGS’s daily totals when they loaded, the file otherwise, nothing when a day is missing', () => {
  const p = { recent_start: '2026-11-01', recent: [1, 1, 1, 1, 1, 1, 1, 2, 2, null] };   // 1 to 10 November; the day of the build has no total yet
  assert.deepStrictEqual(F.rainWeek(p, '2026-11-20'), { mm: 9, end: '2026-11-09', live: false }, 'the file: the 7 days to its last whole day');
  p.liveDays = { '2026-11-19': 5, '2026-11-18': 0, '2026-11-17': 0, '2026-11-16': 0, '2026-11-15': 0, '2026-11-14': 0, '2026-11-13': 2.5 };
  assert.deepStrictEqual(F.rainWeek(p, '2026-11-20'), { mm: 7.5, end: '2026-11-19', live: true });
  delete p.liveDays['2026-11-19']; p.liveDays['2026-11-12'] = 1;
  assert.deepStrictEqual(F.rainWeek(p, '2026-11-20'), { mm: 3.5, end: '2026-11-18', live: true }, 'yesterday not posted yet: the 7 days to the day before');
  delete p.liveDays['2026-11-15'];
  assert.deepStrictEqual(F.rainWeek(p, '2026-11-20'), { mm: 9, end: '2026-11-09', live: false }, 'a day missing: back to the file');
  assert.strictEqual(F.rainWeek({ recent_start: '2026-11-01', recent: [1, null, 1, null, 1, 1, null, 2, null, null] }, '2026-11-20'), null);
  p.liveDays = { '2026-11-11': 4, '2026-11-10': 3 };   // the live days join the file's days
  assert.deepStrictEqual(F.rainWeek(p, '2026-11-12'), { mm: 4 + 3 + 2 + 2 + 1 + 1 + 1, end: '2026-11-11', live: true });
});

test('the pop-up of every rain gauge: the 7 days, the usual range or its absence, a bar a day, what a gauge is not, the USGS station', () => {
  const d = load('rain_gauges.geojson');
  for (const f of d.features) {
    const p = f.properties, html = F.popup('rain', { usgs: p.usgs }, d);   // the 3D view hands over the id; the pop-up reads the file's feature
    assert.ok(html.includes(p.name.replace(/&/g, '&amp;')), p.usgs);
    assert.match(html, /The readings of the last 24 hours could not be loaded\./, 'before the live readings arrive');
    assert.match(html, /mm in the 7 days to \d{4}-\d\d-\d\d|No total for the last 7 days/);
    assert.match(html, /This is not a flood warning or a forecast\./);
    assert.ok(html.includes('https://waterdata.usgs.gov/monitoring-location/' + p.usgs + '/'));
    assert.match(html, /<svg class="res-spark"/);
    assert.ok(!/NaN|undefined|Infinity|m³\/s|below the ground/.test(html), p.usgs + ': no broken number, nothing of the other pop-ups');
  }
  assert.match(F.noteText('rain', d, ''), new RegExp('^' + d.features.length + ' rain gauges in ' + d.notes.municipios + ' municipios. Loading'));
});

test('a wet or a dry week is said against the usual rain of that week, and the 24 hours are shown when they loaded', () => {
  const d = load('rain_gauges.geojson'), f = d.features.find(x => x.properties.p10.every(v => v != null));
  assert.ok(f, 'the file has a gauge with a usual range');
  const p = f.properties, today = new Date().toLocaleDateString('en-CA', { timeZone: 'America/Puerto_Rico' });
  const days = (mm) => { const o = {}; for (let i = 1; i <= 7; i++) o[new Date(Date.parse(today + 'T12:00:00Z') - i * 864e5).toISOString().slice(0, 10)] = mm / 7; return o; };
  const w = F.weekOf(Object.keys(days(0))[0]);
  p.live = { level: 12.7, time: new Date().toISOString(), n: 96 };
  p.liveDays = days(p.p90[w] + 50);
  let html = F.popup('rain', p, d);
  assert.match(html, /<b>12\.7 mm of rain in the last 24 hours<\/b>/);
  assert.match(html, /<b>Wetter than usual for this time of year<\/b>/);
  p.liveDays = days(0);
  html = F.popup('rain', p, d);
  assert.match(html, p.p10[w] > 0 ? /<b>Drier than usual for this time of year<\/b>/ : /<b>Usual for this time of year<\/b>/);
  assert.match(html, /<b>0\.0 mm in the 7 days to /);
  p.liveDays = days((p.p10[w] + p.p90[w]) / 2);
  assert.match(F.popup('rain', p, d), /<b>Usual for this time of year<\/b>/);
});

test('a river gauge with National Weather Service flood stages: which stage the water has reached and how far it is from each', () => {
  const d = load('river_gauges.geojson'), f = d.features.find(x => x.properties.nws && x.properties.nws.major != null);
  assert.ok(f, 'the file has a gauge with NWS flood stages');
  const p = JSON.parse(JSON.stringify(f.properties)), doc = { features: [{ properties: p }], vintage: '2026-11-12', notes: {} };
  p.nws = { lid: 'AAAP4', action: 3, minor: 4, major: 6 }; p.stage = 1; delete p.liveMore;
  assert.deepStrictEqual(F.nwsStages(p), { now: 'none', stages: [{ kind: 'action', level: 3, gap: 2 }, { kind: 'minor', level: 4, gap: 3 }, { kind: 'major', level: 6, gap: 5 }] });
  let html = F.popup('rivers', p, doc);
  assert.match(html, /Flood stages of the National Weather Service at this gauge/);
  assert.match(html, /<b>Now: below the action stage<\/b>/);
  assert.match(html, /Action stage \(3\.00 m on the gauge, 9\.8 ft\): 2\.00 m above the water now/);
  assert.ok(!/Moderate flood stage/.test(html), 'a stage NWS has not set is not shown');
  assert.match(html, /not an official warning/);
  assert.ok(html.includes('href="https://water.noaa.gov/gauges/AAAP4"'));
  p.liveMore = { stage: { v: 4.5, time: '2026-11-12T10:00:00+00:00' } };
  assert.strictEqual(F.nwsStages(p).now, 'minor', 'the live level replaces the file\u2019s');
  html = F.popup('rivers', p, doc);
  assert.match(html, /<b>Now: at or above the minor flood stage<\/b>/);
  assert.match(html, /Minor flood stage \(4\.00 m on the gauge, 13\.1 ft\): the water is at or above it, by 0\.50 m/);
  assert.match(html, /Major flood stage \(6\.00 m on the gauge, 19\.7 ft\): 1\.50 m above the water now/);
  p.liveMore.stage.v = 6;
  assert.strictEqual(F.nwsStages(p).now, 'major');
  delete p.nws;
  assert.strictEqual(F.nwsStages(p), null);
  assert.doesNotMatch(F.popup('rivers', p, doc), /Flood stages of the National Weather Service/);
  delete p.liveMore; delete p.stage; p.nws = { lid: 'AAAP4', action: 3 };
  assert.strictEqual(F.nwsStages(p), null, 'no level of the water, no comparison');
  for (const g of d.features) assert.ok(!/NaN|undefined|Infinity/.test(F.popup('rivers', { usgs: g.properties.usgs }, d)), g.properties.usgs);
});
