// No regular expression lookbehind in the site's scripts: Safari before 16.4 (older iPhones) cannot parse "(?<=" or "(?<!", so a file with one fails to load
// at all (PR #84: a lookbehind in a rule of chat.js would have kept the Ask button from opening). Read the text before a match instead.
'use strict';
const test = require('node:test'), assert = require('node:assert'), fs = require('fs'), path = require('path');

function jsFiles(dir) {
  return fs.readdirSync(dir, { withFileTypes: true }).flatMap(e => {
    const p = path.join(dir, e.name);
    return e.isDirectory() ? jsFiles(p) : e.name.endsWith('.js') ? [p] : [];
  });
}

test('no file in site/js uses a regular expression lookbehind', () => {
  const root = path.join(__dirname, '..', 'site', 'js'), bad = [];
  for (const f of jsFiles(root)) {
    fs.readFileSync(f, 'utf8').split('\n').forEach((line, i) => { if (/\(\?<[=!]/.test(line)) bad.push(`${path.relative(root, f)}:${i + 1}`); });
  }
  assert.deepStrictEqual(bad, [], `lookbehind found (Safari before 16.4 cannot parse it): ${bad.join(', ')}`);
});
