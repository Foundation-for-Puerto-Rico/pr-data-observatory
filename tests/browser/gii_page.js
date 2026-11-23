// The Global Innovation Index page (site/gii.html; docs/analysis/gii-2021/README.md) in a real browser, in each language and width: the profile drawn as the
// 2021 PDF (7 pillars, 21 sub-pillars, 80 indicators), every row a <details> that opens and closes, the printed values and ranks, updated values with their
// year and its change arrow (only the arrow coloured, with words as its label), the indicative GII 2026 position "X/N" with its † note, the GII 2026
// status badges, "Changes in the index since 2020" loaded only when opened, a link to one indicator, the Knowledge Area tabs all alike, no horizontal
// scroll, no missing Spanish and a clean console.
//   chrome --headless=new --remote-debugging-port=9333 --user-data-dir=<a scratch folder> --no-first-run     (or your own port in CDP_PORT)
//   node tests/browser/serve_gzip.js site 8041
//   node tests/browser/gii_page.js [base URL, default http://127.0.0.1:8041] [folder for screenshots] [langs, default es,en] [widths, default 1400,390]
// Exit code: 0 when every check passed, 1 when one failed, 2 on an error.
const fs = require('fs'), path = require('path');
const { openPage } = require('./cdp.js');
const base = process.argv[2] || 'http://127.0.0.1:8041', shots = process.argv[3] || '', langs = (process.argv[4] || 'es,en').split(','), widths = (process.argv[5] || '1400,390').split(',').map(Number);
const sleep = (ms) => new Promise(r => setTimeout(r, ms));
const results = [];
const check = (tag, what, ok, detail) => { results.push({ tag, what, ok: !!ok, detail }); if (!ok) console.error(`FAIL ${tag}: ${what}`, detail === undefined ? '' : JSON.stringify(detail)); };
const consoleErrors = (logs) => logs.filter(l => /error|EXCEPTION/i.test(l.type) && !/favicon/.test(l.text + (l.url || '')));
const WORDS = { es: { name: 'Efectividad del gobierno', tab: 'Índice Global de Innovación', fpr: 'Estimado de FPR', pos: 'ocuparía la posición', worse: 'peor que 2021', better: 'mejor que 2021', same: 'sin cambio apreciable respecto a 2021', drop: 'Eliminado en el GII 2026', fn: 'Posición indicativa calculada por FPR, no oficial de la OMPI' },
                en: { name: 'Government effectiveness', tab: 'Global Innovation Index', fpr: 'FPR estimate', pos: 'would rank', worse: 'worse than 2021', better: 'better than 2021', same: 'no meaningful change from 2021', drop: 'Dropped in GII 2026', fn: 'Indicative position calculated by FPR, not an official WIPO rank' } };
const sum = (code) => `document.querySelector('#i-${code.replace(/\./g, '-')} > summary')`;

async function shot(p, name, selector, maxH = 2400) {
  if (!shots) return;
  await p.eval(`(() => { const e = document.querySelector(${JSON.stringify(selector)}); e.scrollIntoView({ block: 'start' }); window.scrollBy(0, -110); })()`);
  await sleep(900);
  const b = await p.eval(`(() => { const r = document.querySelector(${JSON.stringify(selector)}).getBoundingClientRect(); return { y: r.top + scrollY, h: r.height, w: innerWidth }; })()`);
  const res = await p.send('Page.captureScreenshot', { format: 'png', captureBeyondViewport: true, clip: { x: 0, y: Math.max(0, b.y - 8), width: b.w, height: Math.min(b.h + 16, maxH), scale: 1 } });
  fs.mkdirSync(shots, { recursive: true }); fs.writeFileSync(path.join(shots, name + '.png'), Buffer.from(res.data, 'base64'));
}

async function page(lang, width) {
  const tag = `${lang} ${width}`, W = WORDS[lang];
  const p = await openPage(`${base}/gii.html?lang=${lang}`, { width, height: width < 500 ? 844 : 900, mobile: width < 500, noCache: true });
  try {
    await p.eval("localStorage.setItem('twin.gloss', 'off')");
    check(tag, 'ready (the profile drawn)', await p.waitFor("document.querySelectorAll('.gp-ind').length === 80", 60000));
    const n = await p.eval("({ p: document.querySelectorAll('.gp-pillar').length, s: document.querySelectorAll('.gp-sub').length, i: document.querySelectorAll('.gp-ind').length })");
    check(tag, '7 pillars, 21 sub-pillars, 80 indicators', n.p === 7 && n.s === 21 && n.i === 80, n);
    check(tag, 'pillars and sub-pillars open, indicators closed', await p.eval("[...document.querySelectorAll('.gp-pillar, .gp-sub')].every(d => d.open) && ![...document.querySelectorAll('.gp-ind')].some(d => d.open)"));
    // the printed values and ranks, the updated value with its year and no rank
    const r = await p.eval(`({ t: ${sum('1.1.2')}.textContent, val: ${sum('1.1.2')}.querySelector('.gp-val').textContent, rank: ${sum('1.1.2')}.querySelector('.gp-rank b').textContent, upd: ${sum('1.1.2')}.querySelector('.gp-upd').textContent })`);
    check(tag, '1.1.2: name, printed value -0.2 and rank 80 / 132', r.t.includes(W.name) && /-0\.2$/.test(r.val) && r.rank === '80 / 132', r);
    check(tag, '1.1.2: updated value with its year, no rank', /2025/.test(r.upd) && !/\//.test(r.upd), r.upd);
    check(tag, 'no updated cell carries a rank', await p.eval("![...document.querySelectorAll('.gp-upd')].some(e => /\\d\\s*\\/\\s*\\d/.test(e.textContent))"));
    const marks = await p.eval(`({ star: !!${sum('1.2.3')}.querySelector('.gp-star'), hg: !!${sum('2.1.4')}.querySelector('.gp-hg'), nd: ${sum('2.3.3')}.querySelector('.gp-rank b').textContent, f: ${sum('6.2.1')}.querySelector('.gp-upd').textContent })`);
    check(tag, 'the * and hourglass marks, N/D, the FPR estimate label', marks.star && marks.hg && marks.nd === 'N/D' && marks.f.includes(W.fpr), marks);
    const printed = await p.eval("[...document.querySelectorAll('.gp-ind')].filter(d => d.querySelector('.gp-rank b').textContent.includes('/ 132')).length");
    check(tag, '56 printed ranks', printed === 56, printed);
    // the change arrow: shape, colour on the arrow only, words as its label
    const a = await p.eval(`(() => { const s = ${sum('1.1.2')}, g = s.querySelector('.gp-chg'), b = ${sum('2.1.3')}.querySelector('.gp-chg'), cs = (e) => getComputedStyle(e).color;
      return { g: g.textContent, gl: g.getAttribute('aria-label'), role: g.getAttribute('role'), gc: cs(g), bl: b.getAttribute('aria-label'), b: b.textContent, bc: cs(b),
               upd: cs(s.querySelector('.gp-upd')), val: cs(s.querySelector('.gp-val')), bg: getComputedStyle(s.querySelector('.gp-upd')).backgroundColor,
               r26: s.querySelector('.gp-r26 b').textContent, r26bg: s.querySelector('.gp-r26 b').style.background, rankbg: s.querySelector('.gp-rank b').style.background,
               fn: s.querySelector('.gp-fn').title, sr: s.querySelector('.gp-r26 .sr-only').textContent }; })()`);
    check(tag, '1.1.2: ≈ within one WGI release, labelled, grey', a.g === '≈' && a.gl === W.same && a.role === 'img' && a.gc === 'rgb(102, 102, 102)', a);
    const w = await p.eval(`(() => { const g = ${sum('1.2.1')}.querySelector('.gp-chg'); return { g: g.textContent, gl: g.getAttribute('aria-label'), gc: getComputedStyle(g).color }; })()`);
    check(tag, '1.2.1: a red ▼ labelled worse than 2021', w.g === '▼' && w.gl === W.worse && w.gc === 'rgb(184, 36, 21)', w);
    check(tag, '2.1.3: a green ▲ labelled better than 2021', a.b === '▲' && a.bl === W.better && a.bc === 'rgb(71, 86, 15)', a);
    check(tag, 'only the arrow is coloured: the value and the cell keep the normal colour', a.upd === a.val && a.upd === 'rgb(42, 46, 46)' && a.bg === 'rgba(0, 0, 0, 0)', a);
    check(tag, '1.1.2: indicative position 104/140 styled like the 2021 rank, with the † note', a.r26 === '104/140' && a.r26bg === a.rankbg && a.fn === W.fn && a.sr.includes(W.fn), a);
    const cnt = await p.eval("({ pos: document.querySelectorAll('.gp-r26 b').length, badges: document.querySelectorAll('.gp-ind > summary .gp-st').length, arrows: document.querySelectorAll('.gp-upd .gp-chg').length, drop: " + sum('1.2.3') + ".querySelector('.gp-upd').textContent, st: " + sum('1.2.3') + ".querySelector('.gp-st').className, eq: " + sum('3.2.3') + ".querySelector('.gp-chg').textContent, na: " + sum('6.2.2') + ".querySelector('.gp-chg').textContent })");
    check(tag, '10 indicative positions, 80 status badges, 14 change markers', cnt.pos === 10 && cnt.badges === 80 && cnt.arrows === 14, cnt);
    const nc = await p.eval(`({ a: ${sum('2.1.5')}.querySelector('.gp-chg').textContent, r: ${sum('2.1.5')}.querySelector('.gp-r26').textContent, b: ${sum('6.2.1')}.querySelector('.gp-chg').textContent })`);
    check(tag, '2.1.5 and 6.2.1: — and no position', nc.a === '—' && !/\d\/\d/.test(nc.r) && nc.b === '—', nc);
    check(tag, 'a dropped indicator keeps its original and says so in the updated cell; ≈ and — markers', cnt.drop.includes(W.drop) && /dropped/.test(cnt.st) && cnt.eq === '≈' && cnt.na === '—', cnt);
    check(tag, 'the legend above the table', await p.eval("!!document.querySelector('.gp-key') && document.querySelector('.gp-key').getBoundingClientRect().top < document.getElementById('giiProfile').getBoundingClientRect().top"));
    // collapsing
    await p.eval(`${sum('1.1.2')}.click()`);
    const open = await p.eval("({ open: document.querySelector('#i-1-1-2').open, body: document.querySelector('#i-1-1-2 .gp-body').innerText })");
    check(tag, 'a click opens 1.1.2 with its definition, original, update and GII 2026 position', open.open && open.body.includes(W.pos) && /2025/.test(open.body) && open.body.length > 300, open.body.slice(0, 200));
    await shot(p, `pillar1_${lang}_${width}`, '.gp-pillar', width < 500 ? 2600 : 1600);
    await p.eval(`${sum('1.1.2')}.click()`);
    check(tag, 'a second click closes it', !(await p.eval("document.querySelector('#i-1-1-2').open")));
    await p.eval("document.querySelector('.gp-pillar > summary').click()");
    check(tag, 'a pillar closes', !(await p.eval("document.querySelector('.gp-pillar').open")));
    await p.eval("document.getElementById('giiOpen').click()");
    check(tag, 'Open all opens every row', await p.eval("[...document.querySelectorAll('.gp-profile details')].every(d => d.open)"));
    check(tag, 'every open indicator has its four parts', await p.eval("[...document.querySelectorAll('.gp-ind .gp-body dl')].every(dl => dl.querySelectorAll('dt').length === 4)"));
    check(tag, 'no horizontal scroll with every row open', !(await p.eval('document.documentElement.scrollWidth > innerWidth')), await p.eval('[document.documentElement.scrollWidth, innerWidth]'));
    await p.eval("document.getElementById('giiClose').click()");
    check(tag, 'Close all closes the indicators and sub-pillars and keeps the pillars open', await p.eval("![...document.querySelectorAll('.gp-ind, .gp-sub')].some(d => d.open) && [...document.querySelectorAll('.gp-pillar')].every(d => d.open)"));
    // a link to one indicator opens it
    await p.eval("location.hash = '#i-2-2-3'"); await sleep(300);
    check(tag, 'a link to 2.2.3 opens it and its sub-pillar', await p.eval("document.querySelector('#i-2-2-3').open && document.querySelector('#i-2-2-3').closest('.gp-sub').open"));
    // the Knowledge Area tabs: four, all alike, this one current and marked
    const tabs = await p.eval("[...document.querySelectorAll('.ka-tab')].map(a => { const s = getComputedStyle(a); return { t: a.textContent, cur: a.getAttribute('aria-current'), f: s.fontSize + s.fontWeight + s.paddingTop + s.paddingLeft, h: a.getBoundingClientRect().height, mark: !!a.querySelector('.ka-mark') }; })");
    check(tag, 'four Knowledge Area tabs, all alike', tabs.length === 4 && new Set(tabs.map(t => t.f + t.h)).size === 1, tabs);
    check(tag, 'this tab is current and carries the In review badge', tabs[3] && tabs[3].cur === 'page' && tabs[3].mark && tabs[3].t.includes(W.tab), tabs[3]);
    check(tag, 'noindex', await p.eval("(document.querySelector('meta[name=robots]') || {}).content === 'noindex, nofollow'"));
    if (lang === 'es') {
      const miss = await p.eval("({ missed: [...(I18N.missed || [])], audit: I18N.audit ? I18N.audit() : [] })");
      check(tag, 'no missing Spanish', !miss.missed.length && !(miss.audit || []).length, miss);
    }
    // "Changes in the index since 2020": its data loads only when the section is opened
    const before = await p.eval("performance.getEntriesByType('resource').some(e => /gii_changes\.json/.test(e.name))");
    check(tag, 'gii_changes.json is not loaded before the section is opened', !before);
    await p.eval("document.querySelector('#giiChanges > summary').click()");
    check(tag, 'opening the section loads it and draws its tables', await p.waitFor("document.querySelectorAll('#giiChangesBody table').length === 3", 20000));
    const ch = await p.eval("({ rows: document.querySelectorAll('#giiChangesBody .gp-cw tbody tr').length, nw: document.querySelectorAll('#giiChangesBody table')[2].querySelectorAll('tbody tr').length, ed: document.querySelectorAll('#giiChangesBody table')[0].querySelectorAll('tbody tr').length, li: document.querySelectorAll('#giiChangesBody .gp-method li').length })");
    check(tag, 'editions 3, method 7, 31 indicators that changed, 16 new', ch.ed === 3 && ch.li === 7 && ch.rows === 31 && ch.nw === 16, ch);
    check(tag, 'no horizontal scroll with the changes open', !(await p.eval('document.documentElement.scrollWidth > innerWidth')), await p.eval('[document.documentElement.scrollWidth, innerWidth]'));
    await shot(p, `changes_${lang}_${width}`, '#changes', width < 500 ? 4000 : 2600);
    if (lang === 'es') {
      const miss = await p.eval("({ missed: [...(I18N.missed || [])], audit: I18N.audit ? I18N.audit() : [] })");
      check(tag, 'no missing Spanish in the changes section', !miss.missed.length && !(miss.audit || []).length, miss);
    }
    await p.eval("scrollTo(0, 0)");
    await shot(p, `top_${lang}_${width}`, 'main', width < 500 ? 2600 : 1400);
    await shot(p, `legend_${lang}_${width}`, '#profile', width < 500 ? 1800 : 1100);
    const errs = consoleErrors(p.logs);
    check(tag, 'clean console', !errs.length && !p.bad.length, { errs, bad: p.bad });
  } finally { try { await p.eval("localStorage.removeItem('twin.gloss')"); } catch (e) { /* closed */ } await p.close(); }
}

(async () => {
  for (const lang of langs) for (const w of widths) await page(lang, w);
  const bad = results.filter(r => !r.ok);
  console.log(`${results.length - bad.length} of ${results.length} checks passed`);
  process.exit(bad.length ? 1 : 0);
})().catch(e => { console.error(e); process.exit(2); });
