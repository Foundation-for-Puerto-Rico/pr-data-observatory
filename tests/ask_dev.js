// The development set of "Ask the observatory" (tests/ask_dev.json): each question through the chat in Node (tests/ask_runtime.js), with the real datasets, and whether
// the answer shows what the case accepts. Prints the pass rate overall, by category and by language.
//   node tests/ask_dev.js                 this branch
//   node tests/ask_dev.js --base main     the main branch's chat.js, ask.js (if any), catalog files, Spanish bundle and page scripts (the same datasets)
//   node tests/ask_dev.js --set tests/ask_check.json   the second, smaller set (written after the code, to see whether the gains carry over)
//   options: --fail (list the cases that fail and why), --json <file> (write the results), --min <rate> (exit 1 below that pass rate, 0 to 1), --only <text>
'use strict';
const fs = require('fs'), path = require('path');
const R = require('./ask_runtime');

const args = process.argv.slice(2), opt = (k) => { const i = args.indexOf(k); return i >= 0 ? args[i + 1] : null; }, flag = (k) => args.includes(k);
const DEV = JSON.parse(fs.readFileSync(path.join(__dirname, 'ask_dev.json'), 'utf8'));
if (opt('--set')) DEV.cases = JSON.parse(fs.readFileSync(path.resolve(__dirname, '..', opt('--set')), 'utf8')).cases;   // another file of cases (tests/ask_check.json), with the sets of ask_dev.json
const expand = (items) => items.flatMap(x => typeof x === 'string' && x.startsWith('@') ? (DEV.sets[x.slice(1)] || (() => { throw new Error('no set ' + x); })()) : [x]);

/** Whether an answer passes a case: every clause, and something on the map unless an answer in words is enough. */
function judge(c, o) {
  const why = [], shown = new Set([...o.data, ...o.layers]);
  if (o.error) why.push('error: ' + o.error.split('\n')[0]);
  (c.need || []).forEach((g, i) => { const alt = expand(g); if (!alt.some(k => shown.has(k))) why.push(`need[${i}] none of ${g.join(',')}`); });
  if (c.place) { const p = o.select || (o.zoom && o.zoom.muni) || null; if (R.norm(p || '') !== R.norm(c.place)) why.push(`place ${p} ≠ ${c.place}`); }
  if (c.op && !c.op.includes(o.intent)) why.push(`op ${o.intent} ∉ ${c.op.join('|')}`);
  if (c.barrio && !o.modes.some(m => m[2] === 'barrio')) why.push('not shaded by barrio');
  if (c.not) { const bad = expand(c.not).filter(k => shown.has(k)); if (bad.length) why.push('shows ' + bad.join(',')); }
  const words = [o.text, ...o.actions, ...o.follow].join(' ');
  if (c.note && !new RegExp(c.note, 'i').test(words)) why.push(`note /${c.note}/ missing`);
  if (c.proxy && !/aproximaci[oó]n|approximation|proxy/i.test(words)) why.push('not labelled as an approximation');
  if (c.lang && c.lang !== 'any' && o.lang !== c.lang) why.push(`lang ${o.lang} ≠ ${c.lang}`);
  if (!c.text && !shown.size) why.push('nothing on the map');
  if (c.text && !o.text) why.push('no answer');
  return why;
}

async function main() {
  const base = opt('--base'), only = opt('--only');
  const src = base === 'main' ? { chatSrc: R.gitShow('site/js/chat.js'), askSrc: R.gitShow('site/js/ask.js'), data: 'main' } : {};
  const envs = {}, envOf = (lang, view) => envs[lang + view] || (envs[lang + view] = R.env({ ...src, lang, view }));
  const rows = [];
  const t0 = Date.now();
  for (const c of DEV.cases) {
    if (only && !c.q.includes(only)) continue;
    const pageLang = c.lang === 'en' ? 'en' : 'es', e = envOf(pageLang, c.view || '2d');
    const o = await e.answer(c.q), why = judge(c, o);
    rows.push({ q: c.q, cat: c.cat, lang: c.lang, view: c.view || '2d', pass: !why.length, why, intent: o.intent, data: o.modes, layers: o.layers, select: o.select });
  }
  const ms = Date.now() - t0;
  const rate = (a) => a.length ? a.filter(r => r.pass).length / a.length : NaN, pct = (a) => `${(rate(a) * 100).toFixed(1)}% (${a.filter(r => r.pass).length}/${a.length})`;
  const cats = [...new Set(rows.flatMap(r => r.cat))];
  console.log(`${base === 'main' ? 'main' : 'branch'}: ${pct(rows)} of ${rows.length} cases in ${(ms / 1000).toFixed(1)} s`);
  for (const k of cats) console.log(`  ${k.padEnd(11)} ${pct(rows.filter(r => r.cat.includes(k)))}`);
  for (const l of ['es', 'en', 'any']) console.log(`  lang ${l.padEnd(6)} ${pct(rows.filter(r => r.lang === l))}`);
  if (flag('--fail')) for (const r of rows.filter(x => !x.pass)) console.log(`FAIL ${r.q} [${r.cat.join(',')}] ${r.why.join('; ')} -> ${r.intent} ${JSON.stringify(r.data)} ${JSON.stringify(r.layers)} ${r.select || ''}`);
  if (opt('--json') === '-') console.log(JSON.stringify({ base: base || 'branch', rate: rate(rows), n: rows.length, failed: rows.filter(r => !r.pass).map(r => r.q) }));   // one line, for tests/ask.test.js
  else if (opt('--json')) fs.writeFileSync(opt('--json'), JSON.stringify({ base: base || 'branch', rate: rate(rows), rows }, null, 1));
  const min = opt('--min'); if (min != null && rate(rows) < +min) { console.log(`below ${min}`); process.exitCode = 1; }
}
main().catch(e => { console.error(e); process.exitCode = 2; });
