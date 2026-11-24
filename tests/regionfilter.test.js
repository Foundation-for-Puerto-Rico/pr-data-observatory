// The region filter of the Layers tab's Reference group (site/js/core/regionfilter.js, docs/regions.md "The region filter", HANDOFF decision 113):
//  - the regions are those of site/data/geo/regions.json (regions.py), never defined in the module; each region's ids split the 78 municipios exactly;
//  - the menu lists "All of Puerto Rico", then the planning regions, then the tourism regions, each with its number of municipios;
//  - an unknown or malformed id names no region; the bounding box of the ERSV holds Vieques and Culebra;
//  - both pages have the menu in their Reference group, with its note, and load the module on use (not in their HTML, not after ready): when the group opens, or rg=;
//  - the filter does not touch the data layers (no layer switch, legend or count is read or changed by the module).
// Run: node --test tests/regionfilter.test.js
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');

const ROOT = path.join(__dirname, '..');
const read = (f) => fs.readFileSync(path.join(ROOT, f), 'utf8').replace(/\r\n/g, '\n');
const RF = require(path.join(ROOT, 'site', 'js', 'core', 'regionfilter.js'));
const regions = JSON.parse(read('site/data/geo/regions.json')).regions;
const munis = JSON.parse(read('site/data/municipios.geojson')).features;

test('every region splits the 78 municipios into its own and the others', () => {
  assert.strictEqual(munis.length, 78);
  for (const r of regions) {
    const { inside, outside } = RF.split(munis, r.ids);
    assert.strictEqual(inside.length, r.ids.length, r.id);
    assert.strictEqual(inside.length + outside.length, 78, r.id);
    assert.deepStrictEqual(inside.map(f => f.properties.municipality).sort(), [...r.names].sort(), r.id);
  }
});

test('find: own ids only', () => {
  assert.strictEqual(RF.find(regions, 'ersv').ids.length, 15);
  for (const bad of [null, '', 'ERSV', 'nope', '__proto__', 'constructor', 'ersv&x']) assert.strictEqual(RF.find(regions, bad), null, String(bad));
});

test('the ERSV box reaches Culebra and Vieques (east of -65.6) and stays in Puerto Rico', () => {
  const b = RF.bbox(RF.split(munis, RF.find(regions, 'ersv').ids).inside);
  assert.ok(b[1][0] > -65.3 && b[0][0] > -66.1 && b[0][1] > 17.9 && b[1][1] < 18.6, JSON.stringify(b));
  assert.strictEqual(RF.bbox([]), null);
});

test('the menu: All of Puerto Rico, planning regions, tourism regions, each with its count', () => {
  const html = RF.options(regions, 'en');
  assert.match(html, /^<option value="">All of Puerto Rico<\/option><optgroup label="FPR planning regions"><option value="ersv">Eastern Region \(ERSV\) \(15\)<\/option><\/optgroup><optgroup label="Tourism regions">/);
  assert.strictEqual((html.match(/<option value="reg-/g) || []).length, regions.filter(r => r.kind === 'tourism').length);
  assert.match(RF.options(regions, 'es'), /Región Este \(ERSV\) \(15\)/);
});

test('both pages: the menu in Reference, the note, the module loaded after ready, the rg= key written', () => {
  for (const [page, js] of [['site/index.html', 'site/js/app.js'], ['site/3d.html', 'site/js/twin3d.js']]) {
    const html = read(page), ref = html.indexOf('</span>Reference</h2>'), next = html.indexOf('<h2 class="sec">', ref + 1);
    const at = html.indexOf('<select id="regionFilter" aria-describedby="regionFilterNote" disabled>');
    assert.ok(ref > 0 && at > ref && at < next, `${page}: the menu is in the Reference group`);
    assert.ok(html.includes('id="regionFilterNote"'), page);
    assert.ok(!/<script src="js\/core\/regionfilter\.js/.test(html), `${page}: not in the first load`);
    const src = read(js);
    assert.match(src, /whenShown\(\$\('#regionFilter'\), (rgLink|RF\.id), \(\) => \(window\.Core\.regionfilter \? Promise\.resolve\(\) : addJs\('js\/core\/regionfilter\.js\?v=\d+'\)\)/, `${js}: on use`);
    assert.match(src, /rg: (rgLink|RF\.id) \|\| null/, `${js}: writes rg=`);
  }
  const routes = JSON.parse(read('dictionary_src/routes.json')).routes;
  for (const r of ['map', '3d']) { assert.ok(!(routes[r].deferred || []).includes('js/core/regionfilter.js'), r); assert.ok(routes[r].on_use.includes('geo/regions.json'), r); }
});

test('the module frames and highlights only: it never reads or changes a layer switch', () => {
  const src = read('site/js/core/regionfilter.js');
  assert.ok(!/getElementById\('ly|querySelector\(['"]#ly|\.checked/.test(src));
});
