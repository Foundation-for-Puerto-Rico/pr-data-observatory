// The Data management page (site/data-management.html; docs/data-management.md) in a real browser, in each language and width: ready, six figures, one row per
// published file with a totals row equal to the registry's totals, sorting on a column both ways, the text and review filters with their totals, the CSV of what
// is shown, the growth chart and its measure switch, the counts of what is not published, the table scrolling in its own box and never the page, no missing Spanish
// (scripts and static text), a clean console.
//   chrome --headless=new --remote-debugging-port=9333 --user-data-dir=<a scratch folder> --no-first-run     (or your own port in CDP_PORT)
//   node tests/browser/serve_gzip.js site 8041
//   node tests/browser/datamgmt_page.js [base URL, default http://127.0.0.1:8041] [folder for screenshots] [langs, default es,en] [widths, default 1400,390]
// Exit code: 0 when every check passed, 1 when one failed, 2 on an error.
const fs = require('fs'), path = require('path');
const { openPage } = require('./cdp.js');
const base = process.argv[2] || 'http://127.0.0.1:8041', shots = process.argv[3] || '', langs = (process.argv[4] || 'es,en').split(','), widths = (process.argv[5] || '1400,390').split(',').map(Number);
const REG = JSON.parse(fs.readFileSync(path.join(__dirname, '..', '..', 'site', 'data', 'registry.json'), 'utf8'));
const sleep = (ms) => new Promise(r => setTimeout(r, ms));
const results = [];
const check = (tag, what, ok, detail) => { results.push({ tag, what, ok: !!ok, detail }); if (!ok) console.error(`FAIL ${tag}: ${what}`, detail === undefined ? '' : JSON.stringify(detail)); };
const consoleErrors = (logs) => logs.filter(l => /error|EXCEPTION/i.test(l.type) && !/favicon/.test(l.text + (l.url || '')));
const num = (s) => +String(s).replace(/[^\d]/g, '');

async function shot(p, name, selector, maxH = 2400) {
  if (!shots) return;
  await p.eval(`(() => { const e = document.querySelector(${JSON.stringify(selector)}); e.scrollIntoView({ block: 'start' }); window.scrollBy(0, -70); })()`);
  await sleep(600);
  const b = await p.eval(`(() => { const r = document.querySelector(${JSON.stringify(selector)}).getBoundingClientRect(); return { y: r.top + scrollY, h: r.height, w: innerWidth }; })()`);
  const res = await p.send('Page.captureScreenshot', { format: 'png', captureBeyondViewport: true, clip: { x: 0, y: Math.max(0, b.y - 8), width: b.w, height: Math.min(b.h + 16, maxH), scale: 1 } });
  fs.mkdirSync(shots, { recursive: true }); fs.writeFileSync(path.join(shots, name + '.png'), Buffer.from(res.data, 'base64'));
}

async function page(lang, width) {
  const tag = `${lang} ${width}`;
  const p = await openPage(`${base}/data-management.html?lang=${lang}`, { width, height: width < 500 ? 844 : 900, mobile: width < 500, noCache: true });
  try {
    check(tag, 'ready', await p.waitFor("performance.getEntriesByName('ready').length > 0", 60000));
    check(tag, 'six figures', (await p.eval("document.querySelectorAll('#dmTiles .kpi').length")) === 6);
    const t = REG.totals;
    check(tag, 'one row per published file', (await p.eval("document.querySelectorAll('#dmTbl tbody tr').length")) === REG.files.length);
    const foot = await p.eval("[...document.querySelectorAll('#dmTbl tfoot td, #dmTbl tfoot th')].map(c => c.textContent)");
    check(tag, 'the totals row is the registry totals', num(foot[3]) === t.records && num(foot[4]) === t.fields && num(foot[5]) === t.values && foot[7] === t.first_published && foot[8] === t.last_updated, foot);
    const tiles = await p.eval("[...document.querySelectorAll('#dmTiles .kpi .v')].map(c => c.textContent)");
    check(tag, 'the figures are the registry totals', num(tiles[0]) === t.files && num(tiles[2]) === t.records && num(tiles[3]) === t.values && num(tiles[4]) === t.items && tiles[5] === t.last_updated, tiles);
    // sorting: Values is the default (largest first); a click turns it, another column sorts on its own key
    const top = REG.files.filter(f => f.kind === 'data').sort((a, b) => b.values - a.values)[0].file;
    check(tag, 'sorted by values, largest first', (await p.eval("document.querySelector('#dmTbl tbody th a').textContent")) === top && (await p.eval("document.querySelector('#dmTbl th[aria-sort]').textContent")).length > 0);
    await p.eval("document.querySelector('#dmTbl [data-sort=\"values\"]').click()");
    const asc = await p.eval("({ sort: document.querySelector('#dmTbl th[aria-sort]').getAttribute('aria-sort'), last: [...document.querySelectorAll('#dmTbl tbody tr')].slice(-1)[0].querySelector('td.num:nth-of-type(6)') ? 1 : 1, first: document.querySelector('#dmTbl tbody th a').textContent })");
    const small = REG.files.filter(f => f.kind === 'data').sort((a, b) => a.values - b.values || (a.file < b.file ? -1 : 1))[0].file;
    check(tag, 'a second click sorts smallest first', asc.sort === 'ascending' && asc.first === small, asc);
    await p.eval("document.querySelector('#dmTbl [data-sort=\"last_updated\"]').click()");
    const newest = await p.eval("[...document.querySelectorAll('#dmTbl tbody tr')].slice(0, 3).map(r => r.children[8].textContent)");
    check(tag, 'Last updated sorts newest first', newest.every(d => d === t.last_updated), newest);
    await p.eval("document.querySelector('#dmTbl [data-sort=\"review\"]').click()");
    check(tag, 'Compliance review sorts the open reviews first', (await p.eval("document.querySelector('#dmTbl tbody td.rev .dm-st').className")).includes('open'));
    // filters: text and review, with the totals of what is shown
    const open = REG.files.filter(f => f.review.status === 'open');
    await p.eval("(() => { const s = document.querySelector('#dmRev'); s.value = 'open'; s.dispatchEvent(new Event('change')); })()");
    const f1 = await p.eval("({ n: document.querySelectorAll('#dmTbl tbody tr').length, foot: document.querySelector('#dmTbl tfoot th').textContent, lines: document.querySelectorAll('#dmTbl tbody .dm-st.open').length })");
    check(tag, 'the review filter shows the files with an open review, and their reasons', f1.n === open.length && num(f1.foot) === open.length && f1.lines === open.reduce((s, f) => s + f.review.open.length, 0), f1);
    await shot(p, `open_reviews_${lang}_${width}`, '#files');
    await p.eval("(() => { const s = document.querySelector('#dmRev'); s.value = 'unstated'; s.dispatchEvent(new Event('change')); })()");
    const un = REG.files.filter(f => f.licence_class === 'unstated').length, label = lang === 'es' ? 'GTFS municipales' : 'municipal GTFS feeds';
    const f3 = await p.eval(`({ n: document.querySelectorAll('#dmTbl tbody tr').length, barrio: [...document.querySelectorAll('#dmTbl tbody tr')].filter(r => r.querySelector('th a').textContent === 'barrios.geojson').map(r => r.querySelector('td.rev').textContent)[0] })`);
    check(tag, '"License not stated" keeps every file of that class and names the source that sets it', f3.n === un && (f3.barrio || '').includes(label), f3);
    await p.eval("document.querySelector('#dmReset').click()");
    await p.eval("(() => { const q = document.querySelector('#dmQ'); q.value = 'barrio'; q.dispatchEvent(new Event('input')); })()");
    await sleep(400);
    const f2 = await p.eval("({ n: document.querySelectorAll('#dmTbl tbody tr').length, foot: document.querySelector('#dmTbl tfoot th').textContent, count: document.querySelector('#dmCount').textContent })");
    check(tag, 'the text filter narrows the list and the totals follow', f2.n > 0 && f2.n < REG.files.length && num(f2.foot) === f2.n, f2);
    // the CSV of what is shown: a header, one line per file, the totals
    const csv = await p.eval(`(async () => { let blob = null; const c = URL.createObjectURL, k = HTMLAnchorElement.prototype.click; URL.createObjectURL = (b) => { blob = b; return 'blob:none'; }; HTMLAnchorElement.prototype.click = function () {};
      document.querySelector('#dmCsv').click(); URL.createObjectURL = c; HTMLAnchorElement.prototype.click = k; const b = new Uint8Array(await blob.arrayBuffer()), s = await blob.text(); return { lines: s.split('\\n').length, bom: b[0] === 0xef && b[1] === 0xbb && b[2] === 0xbf, head: s.split('\\n')[0].slice(0, 40) }; })()`);
    check(tag, 'the CSV holds the files shown and their totals', csv.lines === f2.n + 2 && csv.bom, csv);
    await p.eval("document.querySelector('#dmReset').click()");
    // growth: the chart, its readout and the measure switch
    check(tag, 'the growth chart is drawn', await p.eval("!!document.querySelector('#dmChart svg path.ln') && document.querySelectorAll('#dmHist tbody tr').length === " + REG.history.length));
    const end1 = await p.eval("document.querySelector('#dmChart .end-lbl').textContent");
    await p.eval("document.querySelector('#dmMeasure [data-measure=\"files\"]').click()");
    const end2 = await p.eval("document.querySelector('#dmChart .end-lbl').textContent");
    check(tag, 'the measure switch redraws the chart', num(end1) === REG.history.slice(-1)[0].values && num(end2) === REG.history.slice(-1)[0].files, { end1, end2 });
    await p.eval("document.querySelector('#dmMeasure [data-measure=\"values\"]').click()");
    const tip = await p.eval(`(async () => { const s = document.querySelector('#dmChart svg'); s.focus(); s.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowLeft', bubbles: true })); await new Promise(r => setTimeout(r, 100)); return document.querySelector('#dmTip').classList.contains('show') && document.querySelector('#dmTip b').textContent; })()`);
    check(tag, 'the keyboard reads a date of the chart', num(tip) === REG.history.slice(-2)[0].values, tip);
    // what is not published: counts only
    const wh = await p.eval("[...document.querySelectorAll('#dmWithheld tbody tr')].map(r => r.children[1].textContent)");
    check(tag, 'what is not published: eight counts', wh.length === 8 && wh.every(x => /\d/.test(x)), wh);
    // layout and language
    check(tag, 'no horizontal scroll of the page', !(await p.eval('document.documentElement.scrollWidth > innerWidth')));
    if (width < 500) check(tag, 'the table scrolls in its own box', await p.eval("(() => { const w = document.querySelector('#files .dm-wrap'); return w.scrollWidth > w.clientWidth; })()"));
    if (lang === 'es') {
      check(tag, 'no missing Spanish in the scripts', (await p.eval('I18N.missed ? (I18N.missed.size !== undefined ? I18N.missed.size : I18N.missed.length) : 0')) === 0, await p.eval('[...(I18N.missed || [])]'));
      // the static text of the page: what the script fills from the registry (names, titles, sizes: data, already in the page's language) is left out; the glossary's
      // underlines (js/core/glossary.js) are taken off the copy first, since a mark splits a text in pieces the audit would not find
      const audit = (await p.eval("(() => { const c = document.body.cloneNode(true); c.querySelectorAll('.gl-mark, .gl-run').forEach(m => m.replaceWith(...m.childNodes)); c.querySelectorAll('#gl-tip').forEach(e => e.remove()); c.normalize(); c.querySelectorAll('#dmTiles, #dmTbl, #dmHist, #dmWithheld, #dmChart, #dmTip, #filesLede, #growthLede, #dmCount, #dmMeasure, #dmChartCap, #snapshotLabel').forEach(e => e.remove()); return I18N.audit(c); })()")).filter(s => !/^text: (ledger\.py|registry\.json)$/.test(s));
      check(tag, 'no static text without Spanish', audit.length === 0, audit.slice(0, 12));
    }
    await p.eval("scrollTo(0, 0); document.querySelectorAll('.dm-wrap').forEach(w => { w.scrollLeft = 0; })");
    await shot(p, `top_${lang}_${width}`, '.d-hero');
    await shot(p, `files_${lang}_${width}`, '#files', 1800);
    await shot(p, `growth_${lang}_${width}`, '#growth');
    await shot(p, `withheld_${lang}_${width}`, '#withheld');
    await shot(p, `definitions_${lang}_${width}`, '#definitions');
  } finally {
    check(tag, 'a clean console', consoleErrors(p.logs).length === 0, consoleErrors(p.logs));
    await p.close();
  }
}

(async () => {
  for (const lang of langs) for (const w of widths) await page(lang, w);
  const bad = results.filter(r => !r.ok);
  console.log(`${results.length - bad.length} of ${results.length} checks passed`);
  process.exitCode = bad.length ? 1 : 0;
})().catch(e => { console.error(e); process.exit(2); });
