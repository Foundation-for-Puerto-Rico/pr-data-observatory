// The dictionary page's links and focus while its Spanish arrives (PR #10). Needs a headless Chrome on port 9333 (or CDP_PORT) and a served copy of site/:
//   node tests/browser/dictionary_links.js http://127.0.0.1:8041
// The Spanish page reads dictionary_list_es.json after it is ready and then draws the list and the sources again (dictionary.js redraw). This checks, in Spanish and
// in English, at 1400 and 390 px, at full speed and on Slow 4G, that a link to dictionary.html#<id> ends with that entry open within 120 px of the top of the window,
// and, in Spanish, that the redraw keeps the focused element focused (an entry's button, a source card's button). Exits 1 when a check fails, 2 on an error.
const { openPage } = require('./cdp.js');
const base = process.argv[2] || 'http://127.0.0.1:8041';
const SLOW4G = { offline: false, latency: 150, downloadThroughput: 1.6e6 / 8, uploadThroughput: 750e3 / 8 };
const IDS = ['housing.rental_vacancy_pct', 'economy.fed_grants'];   // an entry with Spanish, and one held for review
const READY = "!!document.querySelector('#snapshotLabel') && document.querySelector('#snapshotLabel').textContent !== '—' && document.querySelectorAll('#dList details.de').length > 0";
const SPANISH_IN = "!!(D.data && D.data.labels_es)";   // set by applySpanish (dictionary.js)

(async () => {
  let bad = 0; const rows = [];
  const check = (ok, what) => { if (!ok) { bad++; console.error('FAIL ' + what); } };
  for (const net of ['full', 'slow4g']) for (const lang of ['es', 'en']) for (const width of [1400, 390]) for (const id of IDS) {
    const p = await openPage(`${base}/dictionary.html?lang=${lang}#${id}`, { width, height: 900, mobile: width < 768, noCache: true, ...(net === 'slow4g' ? { network: SLOW4G } : {}) });
    check(await p.waitFor(READY, 120000), `${net} ${lang} ${width} ${id}: the page is ready`);
    if (lang === 'es') check(await p.waitFor(SPANISH_IN, 120000), `${net} ${lang} ${width} ${id}: the Spanish is in`);
    await new Promise(r => setTimeout(r, 2000));   // the smooth scroll to the entry ends
    const r = await p.eval(`(() => { const d = document.getElementById(${JSON.stringify(id)}); return d ? { top: Math.round(d.getBoundingClientRect().top), open: d.open, filled: !!d.querySelector('.de-body').dataset.filled, name: d.querySelector('.de-name').textContent.slice(0, 50) } : null; })()`);
    const row = { net, lang, width, id, ...r }; rows.push(row);
    check(r && r.open, `${net} ${lang} ${width} ${id}: the linked entry is open`);
    check(r && r.top >= 0 && r.top <= 120, `${net} ${lang} ${width} ${id}: the linked entry is at the top (${r && r.top} px)`);
    check(!p.logs.some(l => l.type === 'EXCEPTION' || l.type === 'error'), `${net} ${lang} ${width} ${id}: the console is clean`);
    await p.close();
  }
  // focus kept through the redraw (Spanish only: the English page does not redraw)
  for (const width of [1400, 390]) {
    const p = await openPage(`${base}/dictionary.html?lang=es`, { width, height: 900, mobile: width < 768 });
    check(await p.waitFor(READY, 60000) && await p.waitFor(SPANISH_IN, 60000), `focus ${width}: the page and its Spanish are in`);
    const r = await p.eval(`(async () => {
      const out = {};
      const d = document.getElementById('places.name'); d.open = true; fillBody(d);
      for (let i = 0; i < 100 && !d.querySelector('.de-body').dataset.filled; i++) await new Promise(r => setTimeout(r, 50));
      const b = d.querySelector('[data-act=link]'); b.focus(); redraw();
      out.entry = { tag: document.activeElement.tagName, act: document.activeElement.dataset.act, inside: (document.activeElement.closest('details.de') || {}).id };
      const s = document.querySelector('#src-overture [data-filter-source]'); s.focus(); redraw();
      out.source = { tag: document.activeElement.tagName, inside: (document.activeElement.closest('.src-card') || {}).id };
      const sum = document.querySelector('#dList details.de summary'); const sid = sum.parentElement.id; sum.focus(); redraw();
      out.summary = { tag: document.activeElement.tagName, inside: (document.activeElement.closest('details.de') || {}).id, want: sid };
      return out;
    })()`);
    rows.push({ focus: width, ...r });
    check(r.entry.tag === 'BUTTON' && r.entry.act === 'link' && r.entry.inside === 'places.name', `focus ${width}: an entry's button keeps the focus (${JSON.stringify(r.entry)})`);
    check(r.source.tag === 'BUTTON' && r.source.inside === 'src-overture', `focus ${width}: a source card's button keeps the focus (${JSON.stringify(r.source)})`);
    check(r.summary.tag === 'SUMMARY' && r.summary.inside === r.summary.want, `focus ${width}: an entry's summary keeps the focus (${JSON.stringify(r.summary)})`);
    await p.close();
  }
  console.log(JSON.stringify(rows));
  console.log(bad ? `${bad} checks failed` : 'all checks passed');
  process.exit(bad ? 1 : 0);
})().catch(e => { console.error(e); process.exit(2); });
