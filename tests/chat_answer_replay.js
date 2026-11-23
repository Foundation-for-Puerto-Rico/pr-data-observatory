// The chat's answers before and after: every question-like string of the main branch's tests/core.test.js (the 2,226 of tests/chat_lexicon_replay.js) and the
// development set (tests/ask_dev.json), answered by the main branch's chat and by this branch's (tests/ask_runtime.js, the real datasets, a page stand-in that
// records the map). Lists each question whose answer changed (the intent, the datasets on the map, the layers switched on, the place) with a kind of change, so
// every changed answer can be classified (docs/ask.md, "Replay").
//   node tests/chat_answer_replay.js [--all] [--json <file>] [--kind <kind>]
'use strict';
const fs = require('fs'), path = require('path');
const R = require('./ask_runtime');

const args = process.argv.slice(2), opt = (k) => { const i = args.indexOf(k); return i >= 0 ? args[i + 1] : null; };
const src = R.gitShow('tests/core.test.js');
const qs = [...new Set([...src.matchAll(/'((?:[^'\\\n]|\\.){4,140})'/g)].map(m => m[1].replace(/\\'/g, "'")).filter(q => /[a-záéíóúñ]{3}/i.test(q) && /\s/.test(q) && !/[{}=<>$`]|\.json|\.js\b|^\s|https?:/.test(q)))];   // the same strings as chat_lexicon_replay.js

const sig = (o) => ({ intent: o.intent, data: o.modes.map(x => x.join(':')), layers: o.layers, place: o.select || null });
/** What kind of change an answer had: the first that applies. */
function kind(a, b) {
  const da = new Set(a.data.map(x => x.split(':')[0])), db = new Set(b.data.map(x => x.split(':')[0]));
  const la = new Set(a.layers), lb = new Set(b.layers);
  if (!da.size && !la.size && (db.size || lb.size)) return 'shows-something';   // main showed nothing on the map
  if ([...da].some(k => !db.has(k))) return [...db].some(k => !da.has(k)) ? 'dataset-replaced' : 'dataset-dropped';
  if ([...la].some(k => !lb.has(k))) return 'layer-dropped';
  if ([...db].some(k => !da.has(k))) return 'dataset-added';
  if ([...lb].some(k => !la.has(k))) return 'layer-added';
  if (a.place !== b.place) return a.place && !b.place ? 'place-dropped' : 'place-changed';
  if (a.intent !== b.intent) return 'intent-changed';
  if (JSON.stringify(a.data) !== JSON.stringify(b.data)) return 'view-changed';
  return 'same';
}
async function main() {
  const DEV = JSON.parse(fs.readFileSync(path.join(__dirname, 'ask_dev.json'), 'utf8')).cases.filter(c => (c.view || '2d') === '2d').map(c => c.q);
  const sets = [['core.test.js', qs, 'en'], ['ask_dev.json', DEV, 'es']];
  const out = [], counts = {};
  for (const [name, list, lang] of sets) {
    const before = R.env({ chatSrc: R.gitShow('site/js/chat.js'), askSrc: R.gitShow('site/js/ask.js'), data: 'main', lang }), after = R.env({ lang });
    for (const q of list) {
      const a = sig(await before.answer(q)), b0 = await after.answer(q), b = sig(b0), k = kind(a, b);
      if (k === 'same') continue;
      counts[name + ' ' + k] = (counts[name + ' ' + k] || 0) + 1;
      out.push({ set: name, q, kind: k, before: a, after: b, fixes: b0.plan ? b0.plan.fixes : [] });
    }
    console.log(`${name}: ${list.length} questions, ${out.filter(x => x.set === name).length} answers changed`);
  }
  for (const [k, v] of Object.entries(counts).sort()) console.log(`  ${k}: ${v}`);
  const only = opt('--kind');
  if (args.includes('--all') || only) for (const x of out.filter(x => !only || x.kind === only)) console.log(`${x.kind.padEnd(16)} ${x.q}\n    main: ${JSON.stringify(x.before)}\n    now:  ${JSON.stringify(x.after)}${x.fixes.length ? '  fixes ' + JSON.stringify(x.fixes) : ''}`);
  if (opt('--json')) fs.writeFileSync(opt('--json'), JSON.stringify(out, null, 1));
}
main().catch(e => { console.error(e); process.exitCode = 2; });
