// Replays every question of the main branch's tests/core.test.js through the chat's parser with the real datasets, without and with the generated lexicon (plan item 14), and lists the
// questions whose datasets change. The lexicon must only answer questions that found nothing before, or add a dataset named by its "ask" words.
//   node tests/chat_lexicon_replay.js            (exit 1 when a question that found datasets before finds different ones now)
const fs = require('fs'), path = require('path');
const core = (n) => require(path.join(__dirname, '..', 'site', 'js', 'core', n + '.js'));
const readData = (f) => JSON.parse(fs.readFileSync(path.join(__dirname, '..', 'site', 'data', f), 'utf8'));
globalThis.fmt = (n, d = 0) => Number(n).toLocaleString('en-US', { minimumFractionDigits: d, maximumFractionDigits: d });
const engine = core('engine'), datasets = core('datasets');

function tabEngine() {
  const X = engine.create(), muni = readData('municipalities.json'), meta = readData('meta.json'), docs = {};
  for (const f of datasets.FILES) docs[f.name] = readData(f.file);
  datasets.apply(X, docs, muni, +((meta.generated_at || '').slice(0, 4)) || 2026);
  return X;
}
function chatEnv(ask, s = fs.readFileSync(path.join(__dirname, '..', 'site', 'js', 'chat.js'), 'utf8')) {
  const at = s.indexOf('const CONCEPTS = [');
  const concepts = s.slice(at, s.indexOf('\n];', at) + 3), mid = s.slice(s.indexOf('const STOP'), s.indexOf('function chFuzzy')), intent = s.slice(s.indexOf('function chIntent'), s.indexOf('// ── Data helpers'));
  const norm = (x) => (x || '').normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase().trim();
  const code = `let API = null; const chApi = () => API; const I18N = { lang: 'en' }; const CH = { lastLang: null, ui: 'en', ctx: { keys: [], year: null, muni: null }, ask: ${JSON.stringify(ask)} }; const CH_CONTEXT = [];\n${concepts}\n${mid}\n${intent}\nreturn { chParse, setApi: (a) => { API = a; } };`;
  return new Function('norm', 'esc', 'fmt', 'T', code)(norm, (x) => String(x), (n) => String(n), (x) => x);
}

const X = tabEngine(), api = { datasets: () => X.info(), meta: (k) => X.V[k] || null, dictId: (k) => X.dictId(k), places: () => X.geo.names.slice() };
const cat = readData('catalog_index.json'), F = cat.index.fields, ask = {};   // the index of the dictionary (catalog.py writes it apart from catalog.json since 2026-10-18)
cat.index.rows.forEach(r => { if (r[F.indexOf('ask')]) ask[r[F.indexOf('id')]] = r[F.indexOf('ask')]; });
// before: the chat of the main branch (git show origin/main:site/js/chat.js, or the file named by BASE); after: this branch's, with the words of the dictionary entries
const baseSrc = process.env.BASE ? fs.readFileSync(process.env.BASE, 'utf8') : require('child_process').execSync('git show origin/main:site/js/chat.js', { cwd: path.join(__dirname, '..'), maxBuffer: 1 << 26 }).toString('utf8');
const askOf = (c) => { const F = c.index.fields, a = F.indexOf('ask'), o = {}; if (a >= 0) c.index.rows.forEach(r => { if (r[a]) o[r[F.indexOf('id')]] = r[a]; }); return o; };   // main's own "ask" words (none before item 14), from main's catalog
const gitShow = (f) => require('child_process').execSync('git show origin/main:' + f, { cwd: path.join(__dirname, '..'), maxBuffer: 1 << 26, stdio: ['ignore', 'pipe', 'ignore'] }).toString('utf8');
const baseCat = process.env.BASE ? null : JSON.parse((() => { try { return gitShow('site/data/catalog_index.json'); } catch (e) { return gitShow('site/data/catalog.json'); } })());   // main's index: its own file, or inside catalog.json before 2026-10-18
const off = chatEnv(baseCat ? askOf(baseCat) : null, baseSrc), after = chatEnv(ask);
off.setApi(api); after.setApi(api);

if (process.env.PROBE) { for (const q of process.env.PROBE.split('|')) { const p = after.chParse(q); console.log(q, '->', JSON.stringify(p.keys), p.intent, JSON.stringify(p.places), process.env.FULL ? JSON.stringify({ dropped: p.dropped, rest: p.rest }) : ''); } process.exit(0); }
const src = require('child_process').execSync('git show origin/main:tests/core.test.js', { cwd: path.join(__dirname, '..'), maxBuffer: 1 << 26 }).toString('utf8');   // the questions the main branch's tests ask: new tests may ask new things on purpose
const qs = [...new Set([...src.matchAll(/'((?:[^'\\\n]|\\.){4,140})'/g)].map(m => m[1].replace(/\\'/g, "'")).filter(q => /[a-záéíóúñ]{3}/i.test(q) && /\s/.test(q) && !/[{}=<>$`]|\.json|\.js\b|^\s|https?:/.test(q)))];
let changed = 0, gained = 0;
for (const q of qs) {
  let a, b;
  try { a = off.chParse(q).keys; b = after.chParse(q).keys; } catch (e) { continue; }
  const A = JSON.stringify(a), B = JSON.stringify(b);
  if (A === B) continue;
  if (!a.length) { gained++; if (process.env.SHOW) console.log('gained  ', q, '->', B); continue; }
  if (b.length > a.length && a.every((k, i) => b.includes(k))) { gained++; console.log('added   ', q, A, '->', B); continue; }
  changed++; console.log('CHANGED ', q, A, '->', B);
}
console.log(`${qs.length} questions replayed: ${changed} changed, ${gained} gained a dataset they did not have`);
process.exitCode = changed ? 1 : 0;
