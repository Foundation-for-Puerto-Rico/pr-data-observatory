/* PR Data Observatory: the time series panel of the 3D view. It shows, under the map, every year of a dataset for one municipality ("Any dataset…":
   ENG.h, rescaled as the columns rescale it), with Puerto Rico as the reference line.
   - It opens from the "Time series" link of a municipality's card. With the "Any dataset" columns on, a click on a municipality also opens it, on a desktop only (700 px and
     wider); while it is open there, a click on another municipality moves it to that one. Its datasets load when it opens, not before (engineLoad).
   - On a phone (under 700 px) it never opens by itself, the card closes when it opens (so the panel never covers it), and a click on the map closes it.
   - With the columns on, the panel and the columns share one year: choosing a year on the chart (a click, the arrow keys, Home, End) sets the columns' year, and the year menu
     moves the chart's marker. With the columns off, the chart keeps a year of its own (X.y) and leaves the columns' year alone. "Latest" goes back to the latest year.
     The chart is a slider: the arrows move one year (Left and Down back, Right and Up on), Page Up and Page Down five, Home and End to the ends; the year chosen with the
     keys shows the pointer's tooltip over its point (keyTip).
   - The key (the municipality's line, Puerto Rico's) shows at every width: under 860 px it takes a row of its own under the title.
   - ACS datasets (5-year windows) are drawn at the last year of each window; the tooltip, the screen reader's text and the peak name the whole window, with the margin of error
     (90% confidence) where the engine has one for the value shown (E.moe: the values as published, not rescaled), drawn as a band around the municipality's line.
   - Esc or the close button give the focus back to the link that opened it, or to the map.
   Loads after twin3d.js and uses its ENG, engineLoad, engineFill, engineDraw, metricKey, map, pop, popup, S and tip. */
const Series = (() => {
  // Without WebGL twin3d.js stops before it creates the map (webglOk): then the panel is not built and nothing here touches the map. The binding may not exist at all, or
  // exist uninitialised, and both throw a ReferenceError, so the check is a try.
  const mapOk = (() => { try { return !!map && typeof map.on === 'function'; } catch { return false; } })();
  if (!mapOk) return null;
  const X = { name: null, open: false, pts: null, y: null, hit: null, at: null, kb: false, opener: null };   // y: the chart's own year while the columns are off (null: the latest); at: the chosen year's point; kb: its tooltip is shown for the keys
  const P = { l: 52, r: 18, t: 30, b: 26 };   // the plot's margins in px: the axes' labels sit in them
  const PHONE = '(max-width: 699px)', phone = () => matchMedia(PHONE).matches;
  const el = document.createElement('section');
  el.className = 'series'; el.id = 'series'; el.hidden = true;
  el.setAttribute('role', 'region'); el.setAttribute('aria-label', T('Time series'));
  el.innerHTML = `<div class="sr-head"><h2 class="sr-title" id="srTitle"></h2>
    <div class="sr-keys" aria-hidden="true"><span><i class="sr-k-m"></i><b id="srKeyM"></b></span><span><i class="sr-k-pr"></i><b id="srKeyPr">Puerto Rico</b></span></div>
    <div class="sr-pills"><select id="srSet" aria-label="${esc(T('Dataset'))}"></select>
      <button type="button" id="srLatest" hidden>${esc(T('Latest'))}</button>
      <button type="button" id="srCols">${icon('bar_chart', { size: 15 })}${esc(T('Show as columns'))}</button>
      <button type="button" class="sr-x" id="srClose" aria-label="${esc(T('Close the time series'))}"><span class="ms-icon" aria-hidden="true">close</span></button></div></div>
    <div class="sr-chart" id="srChart" role="slider" tabindex="0" aria-labelledby="srTitle"></div>
    <p class="sr-note" id="srNote" hidden></p>`;
  document.body.appendChild(el);
  const chart = el.querySelector('#srChart'), note = el.querySelector('#srNote');
  const colsOn = () => metricKey === '__any';   // the columns read ENG.h: the panel shares their year
  const ok = (x) => x != null && isFinite(x) ? x : null;

  /** The years of the dataset for one municipality and for Puerto Rico, as the columns read it, with the margins of error the engine has for them. */
  function points() {
    const E = ENG.E, L = E.makeLayer(ENG.h, 'fill', ENG.ho, []); if (!L || L.error) return null;
    const i = E.placeIndex(X.name), v = E.V[ENG.h]; if (i < 0 || !v) return null;
    const rows = v.ys.map(y => { const a = E.calc(L, y) || [], mo = E.moe(L, y); return { y, m: ok(a[i]), p: ok(a[E.geo.pr]), me: mo ? ok(mo[i]) : null, pe: mo ? ok(mo[E.geo.pr]) : null }; }).filter(r => r.m != null || r.p != null);
    const want = colsOn() ? ENG.y : X.y;
    return { E, L, v, rows, want, win: !!(v.time && v.time.type === 'window'), moe: rows.some(r => r.me != null), sel: E.resolve(ENG.h, want).y };
  }
  const scale = (d0, d1, r0, r1) => (x) => d1 === d0 ? (r0 + r1) / 2 : r0 + (x - d0) / (d1 - d0) * (r1 - r0);
  const niceTicks = (xs) => {   // round marks (1, 2, 2.5 or 5 times a power of ten) from zero, or the lowest loss, to at or above the top
    const a = Math.min(0, ...xs), top = Math.max(...xs), b = top > a ? top : a + 1, raw = (b - a) / 4, p = 10 ** Math.floor(Math.log10(raw)), st = [1, 2, 2.5, 5, 10].map(m => m * p).find(v => v >= raw);
    const out = []; for (let v = Math.floor(a / st) * st; v < b + st; v += st) out.push(+v.toPrecision(12));
    return out;
  };
  /** A value, and its margin of error when there is one ("12.3% ±1.1 pts"): the margin of a percentage is in percentage points. */
  function fv(D, x, e) {
    if (x == null) return T('no value');
    const s = D.E.fmt(D.L, x); if (e == null) return s;
    const m = D.E.fmt(D.L, e);
    return `${s} ±${/%$/.test(m) ? m.replace(/\s*%$/, '') + ' ' + T('pts') : m}`;
  }
  const period = (D, y) => Core.time.label(D.v, y);

  function empty(msg, status) {   // no chart: a message, and nothing left for the pointer or the slider to read
    X.hit = null; X.at = null;
    chart.innerHTML = `<p class="sr-empty"${status ? ' role="status"' : ''}>${esc(msg)}</p>`;
    ['aria-valuemin', 'aria-valuemax', 'aria-valuenow'].forEach(a => chart.removeAttribute(a));
    chart.setAttribute('aria-valuetext', msg);
  }

  function draw() {
    const D = X.pts;
    if (!D || !D.rows.length) return empty(T('This dataset has no values for {name} in any year.', { name: X.name }));
    const { E, L, rows, sel } = D, W = chart.clientWidth || 600, H = chart.clientHeight || 160;
    const ms = rows.map(r => r.m).filter(x => x != null), ps = rows.map(r => r.p).filter(x => x != null);
    const ends = rows.filter(r => r.m != null && r.me != null).flatMap(r => [r.m - r.me, r.m + r.me]);
    // One axis for both: the values share a unit (the columns' rescaling), so a municipality far below Puerto Rico is shown far below it, not lifted by an axis of its own.
    const tk = niceTicks([...ms, ...ps, ...ends]), dl = [tk[0], tk.at(-1)];
    const x = scale(rows[0].y, rows[rows.length - 1].y, P.l, W - P.r), yl = scale(dl[0], dl[1], H - P.b, P.t);
    const f = (v) => E.fmt(L, v, Math.abs(v) >= 1000);
    const line = (k, y) => { let d = '', on = false; for (const r of rows) { if (r[k] == null) { on = false; continue; } d += `${on ? 'L' : 'M'}${x(r.y).toFixed(1)},${y(r[k]).toFixed(1)}`; on = true; } return d; };
    const ticks = tk.map(v => { const yy = yl(v).toFixed(1); return `<line class="sr-grid" x1="${P.l}" x2="${W - P.r}" y1="${yy}" y2="${yy}"/><text class="sr-ax" x="${P.l - 8}" y="${yy}" dy=".32em" text-anchor="end">${esc(f(v))}</text>`; }).join('');
    const every = Math.max(1, Math.ceil(rows.length / Math.max(2, Math.floor((W - P.l - P.r) / 56))));   // a year label every ~56 px; a 5-year window is labelled by its last year (the note says so)
    const xl = rows.filter((r, k) => (rows.length - 1 - k) % every === 0).map(r => `<text class="sr-ax" x="${x(r.y).toFixed(1)}" y="${H - 8}" text-anchor="middle">${r.y}</text>`).join('');
    // the margin of error: a band around the municipality's line, one piece for each run of years that have one
    let band = '', run = [];
    const flush = () => { if (run.length > 1) band += `M${run.map(r => `${x(r.y).toFixed(1)},${yl(r.m + r.me).toFixed(1)}`).join('L')}L${run.slice().reverse().map(r => `${x(r.y).toFixed(1)},${yl(r.m - r.me).toFixed(1)}`).join('L')}Z`; run = []; };
    for (const r of rows) { if (r.m != null && r.me != null) run.push(r); else flush(); } flush();
    const bars = rows.filter(r => r.m != null && r.me != null).map(r => `<line class="sr-err" x1="${x(r.y).toFixed(1)}" x2="${x(r.y).toFixed(1)}" y1="${yl(r.m - r.me).toFixed(1)}" y2="${yl(r.m + r.me).toFixed(1)}"/>`).join('');   // and a bar at each point, so a lone year shows its margin too
    const dm = line('m', yl), area = !band && ms.length > 1 ? `${dm}L${x(rows.filter(r => r.m != null).at(-1).y).toFixed(1)},${yl(Math.max(dl[0], 0)).toFixed(1)}L${x(rows.find(r => r.m != null).y).toFixed(1)},${yl(Math.max(dl[0], 0)).toFixed(1)}Z` : '';
    const peak = rows.reduce((a, r) => r.m != null && (a == null || r.m > a.m) ? r : a, null);
    const pt = peak && T('Peak · {year} · {value}', { year: period(D, peak.y), value: f(peak.m) }), pw = pt ? pt.length * 6.4 + 16 : 0;   // the tag's width from its text (10.5 px mono: about 6.4 px a character)
    const pk = peak ? `<g class="sr-tag" transform="translate(${Math.min(Math.max(x(peak.y), P.l + pw / 2), W - P.r - pw / 2).toFixed(1)},${Math.max(yl(peak.m) - 14, 12).toFixed(1)})"><rect x="${-pw / 2}" y="-10" width="${pw}" height="19" rx="4"/><text text-anchor="middle" dy=".33em">${esc(pt)}</text></g>` : '';
    const s = rows.find(r => r.y === sel), sx = s ? x(s.y).toFixed(1) : null;
    const mark = s ? `<line class="sr-sel" x1="${sx}" x2="${sx}" y1="${P.t - 8}" y2="${H - P.b}"/>${s.p != null ? `<circle class="sr-dot-pr" cx="${sx}" cy="${yl(s.p).toFixed(1)}" r="4.5"/>` : ''}${s.m != null ? `<circle class="sr-dot-m" cx="${sx}" cy="${yl(s.m).toFixed(1)}" r="5.5"/>` : ''}` : '';
    chart.innerHTML = `<svg width="${W}" height="${H}" aria-hidden="true">${ticks}${xl}
      ${band ? `<path class="sr-band" d="${band}"/>` : `<path class="sr-area" d="${area}"/>`}${bars}<path class="sr-line-pr" d="${line('p', yl)}"/><path class="sr-line-m" d="${dm}"/>
      ${rows.map(r => r.m != null ? `<circle class="sr-pt" cx="${x(r.y).toFixed(1)}" cy="${yl(r.m).toFixed(1)}" r="2.5"/>` : '').join('')}${mark}${pk}</svg>`;
    X.hit = rows.map(r => ({ r, x: x(r.y) }));
    X.at = s ? { r: s, x: x(s.y), y: yl(s.m != null ? s.m : s.p) } : null;   // the chosen year's point, for the keys' tooltip
    const at = s || rows.at(-1), o = { year: period(D, at.y), value: fv(D, at.m, at.me), pr: fv(D, at.p, at.pe) };
    chart.setAttribute('aria-valuemin', rows[0].y); chart.setAttribute('aria-valuemax', rows.at(-1).y); chart.setAttribute('aria-valuenow', at.y);
    chart.setAttribute('aria-valuetext', D.win ? T('{year}, 5-year estimate: {value}; Puerto Rico {pr}', o) + (D.moe ? '. ' + T('± margin of error, 90% confidence') : '') : T('{year}: {value}; Puerto Rico {pr}', o));
    if (X.kb) keyTip();   // drawn again (the columns' year, a resize): the keys' tooltip follows its point
  }

  /** The line under the chart: what a 5-year estimate is, and that the municipality has no values when only Puerto Rico's line is drawn. */
  function noteText(D) {
    if (!D || !D.rows.length) return '';
    const out = [];
    if (!D.rows.some(r => r.m != null)) out.push(T('This dataset has no values for {name} in any year.', { name: X.name }));
    if (D.win) {
      const last = D.rows.at(-1).y;
      out.push(T('5-year estimates, each placed at the last year of its period ({period} at {year}).', { period: period(D, last), year: last }));
      out.push(T('The periods overlap, so the change from one point to the next is not a change from one year to the next.'));
      if (D.moe) out.push(T('The band is the margin of error at 90% confidence.'));
      else if (D.v.moe) out.push(T('The margin of error is published for the values as estimated, not for this rescaled value.'));
    }
    return out.join(' ');
  }

  function render() {
    if (!X.open || !ENG.E) return;
    X.pts = points();
    const E = ENG.E, D = X.pts, L = D && D.L;
    $('#srTitle').textContent = L ? `${X.name} · ${E.title(L, D.sel)}` : X.name;
    $('#srKeyM').textContent = X.name;
    $('#srSet').value = ENG.h;
    $('#srCols').hidden = colsOn();
    $('#srLatest').hidden = !D || D.want == null;
    const n = noteText(D); note.textContent = n; note.hidden = !n;
    draw();
    if (window.Core && Core.glossary && Core.glossary.observe) Core.glossary.observe(note);   // the technical words of the note (5-year estimate, margin of error) get their definitions, as in the side panel
  }
  /** A year chosen on the chart (null: the latest): the columns' year when they are on, the chart's own otherwise. */
  function setYear(y) {
    if (colsOn()) { ENG.y = y; $('#engY').value = y == null ? '' : String(y); engineDraw(); }   // engineDraw calls sync()
    else { X.y = y; render(); }
  }

  /** On a desktop, a card the panel would cover moves up (the map pans); on a phone the card closes. */
  function clearCard() {
    if (!pop || !pop.isOpen()) return;
    if (phone()) { popup(); return; }
    const c = pop.getElement().getBoundingClientRect(), s = el.getBoundingClientRect(), d = c.bottom - s.top + 12;
    if (d > 12 && c.right > s.left && c.left < s.right) map.panBy([0, d], { duration: matchMedia('(prefers-reduced-motion: reduce)').matches ? 0 : 300 });
  }

  /** Opens the panel for a municipality of the view (any other name is ignored). o.opener: where the focus goes back on close; o.focus: move the focus to the chart. */
  async function open(name, o = {}) {
    if (!name || !S.muni[name]) return;
    X.name = name; X.open = true; X.opener = o.opener || null; X.pts = null; X.hit = null;
    el.hidden = false; document.body.classList.add('series-open');
    $('#srTitle').textContent = name; $('#srKeyM').textContent = name;
    clearCard();
    if (o.focus) chart.focus({ preventScroll: true });
    if (!ENG.E) { note.hidden = true; empty(T('Loading the datasets…'), true); }
    try { await engineLoad(); } catch { if (X.open && X.name === name) empty(T('The datasets could not be loaded. Check your connection and choose the option again.'), true); return; }
    if (!X.open || X.name !== name) return;   // closed, or another municipality chosen, while they loaded
    engineFill();
    if (!$('#srSet').options.length) $('#srSet').innerHTML = $('#engH').innerHTML;
    render();
  }
  /** A click on a municipality of the map (after its card opened): on a desktop the panel opens by itself with the "Any dataset" columns on, and follows the click while open. */
  function auto(name) { if (name && !phone() && (colsOn() || X.open)) open(name); }
  function close(back = true) {
    if (!X.open) return;
    X.open = false; X.kb = false; el.hidden = true; document.body.classList.remove('series-open'); tip('');
    const to = X.opener && X.opener.isConnected ? X.opener : map.getCanvas();   // the link that opened it, or the map when its card has closed
    X.opener = null; if (back) to.focus({ preventScroll: true });
  }

  $('#srClose').onclick = () => close();
  $('#srLatest').onclick = () => { setYear(null); chart.focus({ preventScroll: true }); };   // the button hides itself: the focus goes to the chart
  $('#srSet').onchange = e => { ENG.h = e.target.value; ENG.ho = {}; $('#engH').value = ENG.h; if (colsOn()) engineDraw(); else render(); };
  $('#srCols').onclick = () => { if (!colsOn() && X.y != null) { ENG.y = X.y; $('#engY').value = String(X.y); } const m = $('#metric'); m.value = '__any'; m.dispatchEvent(new Event('change')); };   // as if chosen in the Layers tab, in the chart's year
  document.addEventListener('click', e => { const b = e.target.closest('[data-series]'); if (b) { e.preventDefault(); open(b.dataset.series, { opener: b, focus: true }); } });   // the link of a municipality's card
  map.on('click', () => { if (X.open && phone()) close(false); });   // a phone: back on the map, the panel makes room for the card the click opens
  const near = (px) => X.hit && X.hit.reduce((a, h) => Math.abs(h.x - px) < Math.abs(a.x - px) ? h : a);
  const tipHtml = (D, r) => `<b>${esc(period(D, r.y))}</b>${D.win ? ` · ${esc(T('5-year estimate'))}` : ''}<br>${esc(X.name)}: ${esc(fv(D, r.m, r.me))}<br>Puerto Rico: ${esc(fv(D, r.p, r.pe))}${D.moe ? `<br><small>${esc(T('± margin of error, 90% confidence'))}</small>` : ''}`;
  /** The tooltip of the year chosen with the keys, over its point and kept inside the window (8 px from each edge), so a keyboard user sees what the pointer shows. */
  function keyTip() {
    const D = X.pts, s = D && X.at; if (!s || !X.kb || document.activeElement !== chart) return;
    const c = chart.getBoundingClientRect(), px = c.left + s.x, py = c.top + s.y, t = $('#tip');
    tip(tipHtml(D, s.r), 0, 0); t.style.left = '0px'; t.style.top = '0px';   // measured at the left edge, at its full width
    const b = t.getBoundingClientRect(), top = py - b.height - 12;   // above its point, or below it when there is no room
    t.style.left = Math.max(8, Math.min(innerWidth - b.width - 8, px - b.width / 2)) + 'px';
    t.style.top = Math.max(8, Math.min(innerHeight - b.height - 8, top >= 8 ? top : py + 12)) + 'px';
  }
  chart.onmousemove = e => {
    const h = near(e.clientX - chart.getBoundingClientRect().left); if (!h) return;
    X.kb = false; tip(tipHtml(X.pts, h.r), e.clientX, e.clientY - 70);
  };
  chart.onmouseleave = () => tip('');
  chart.onblur = () => { if (X.kb) { X.kb = false; tip(''); } };
  chart.onclick = e => { const h = near(e.clientX - chart.getBoundingClientRect().left); if (h) setYear(h.r.y); };
  // The keys of a slider (WAI-ARIA APG): Left and Down one year back, Right and Up one year on, Page Down and Page Up five, Home and End the first and the last
  const STEP = { ArrowLeft: -1, ArrowDown: -1, ArrowRight: 1, ArrowUp: 1, PageDown: -5, PageUp: 5, Home: -Infinity, End: Infinity };
  chart.onkeydown = e => {
    const K = STEP[e.key];
    if (K == null || e.altKey || e.ctrlKey || e.metaKey || !X.pts || !X.pts.rows.length) return;
    e.preventDefault();
    const ys = X.pts.rows.map(r => r.y), k = ys.indexOf(X.pts.sel), n = !isFinite(K) ? (K < 0 ? 0 : ys.length - 1) : k < 0 ? ys.length - 1 : Math.min(ys.length - 1, Math.max(0, k + K));
    X.kb = true; setYear(ys[n]); keyTip();
  };
  new ResizeObserver(() => X.open && X.pts && draw()).observe(chart);   // not while the datasets load: the chart says so
  document.addEventListener('keydown', e => { if (e.key === 'Escape' && X.open && el.contains(document.activeElement)) close(); });

  return { open, auto, close, sync: render, get state() { return { open: X.open, name: X.name, y: X.y, sel: X.pts ? X.pts.sel : null, rows: X.pts ? X.pts.rows.length : 0, hit: X.hit ? X.hit.length : 0 }; } };
})();
window.Series = Series;   // null without a map: twin3d.js checks window.Series before it offers the "Time series" link
