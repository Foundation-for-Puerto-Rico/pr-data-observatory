// Makes tests/golden/economy.json from a capture of the Economy tab (capture_economy.js) taken on code you trust.
//   node tests/browser/make_golden.js <captures dir>/old_economy_en.json tests/golden/economy.json
// tests/core.test.js (python -m unittest discover runs it) checks the shared engine against this file. It holds fingerprints of the values the tab computed (a SHA-1 of each
// array, so the file stays small), the options and formats of every dataset, and, for 26 layer stacks, the text of the legend and the layer cards, the colour of each
// municipality and the symbols. Aggregates of published series only.
const fs = require('fs'), crypto = require('crypto');
const [, , inFile, outFile] = process.argv;
const cap = JSON.parse(fs.readFileSync(inFile, 'utf8'));
const sha = (v) => crypto.createHash('sha1').update(JSON.stringify(v)).digest('hex');
const { flat } = require('../golden_flat.js');

const out = { about: 'Fingerprints of what the Economy tab computed and drew on commit 8cc851a, in English (tests/browser/make_golden.js). tests/core.test.js compares the shared engine with it.', source: 'old_economy_en', places: cap.places, years: cap.years, base: cap.base, datasets: cap.datasets.map(d => d.key), perKey: {}, configs: {} };
for (const [k, e] of Object.entries(cap.perKey)) {
  out.perKey[k] = { norm: e.norm, defaultFill: e.defaultFill, defaultSymbol: e.defaultSymbol, dictId: e.dictId, units: e.units, fmt: e.fmt, values: {} };
  for (const [c, r] of Object.entries(e.values)) out.perKey[k].values[c] = r ? { year: r.year, exact: r.exact, sha1: sha(r.values) } : null;
}
const body = (legend) => { const m = /<div class="el-body"[^>]*>([\s\S]*)<\/div>$/.exec(legend || ''); return m ? m[1] : ''; };
for (const [id, c] of Object.entries(cap.configs)) {
  out.configs[id] = {
    applied: c.applied, skipped: c.skipped, encode: c.encode, extra: c.extra, legend: flat(body(c.legend)), cards: flat(c.cards), status: c.status,
    fills: c.fills ? cap.places.slice(0, cap.places.length - 1).map(n => c.fills[n][0]) : null, opacity: c.fills ? c.fills[cap.places[0]][1] : null,
    symbols: c.symbols.map(s => [s[2], s[3], s[4]]),
  };
}
fs.mkdirSync(require('path').dirname(outFile), { recursive: true });
fs.writeFileSync(outFile, JSON.stringify(out) + '\n');
console.log(`${outFile}: ${Object.keys(out.perKey).length} datasets, ${Object.keys(out.configs).length} layer stacks, ${(fs.statSync(outFile).size / 1024).toFixed(0)} KB`);
