/* PR Data Observatory: the Learn page (learn.html; docs/learn.md, HANDOFF decision 106). It draws one card for every built lesson of the Learn
   registry and, in each lesson, the part called "In the observatory": the same idea on real data. Every figure comes from window.LEARN, which
   learn.py computes from the published data files (js/learn_items.js); nothing here is a typed number. Titles and terms of the lessons are
   { en, es } (data-t="skip"); interface words are T() keys of the learn scope. The lessons' own text is static HTML in learn.html. */
(function () {
  'use strict';
  const L = window.LEARN, cards = document.getElementById('lnCards');
  if (!L || !cards) return;
  const lang = () => (window.I18N && I18N.lang === 'es' ? 'es' : 'en');
  const tx = (o) => (o && (o[lang()] || o.en)) || '';
  const parts = Object.fromEntries(L.parts.map(p => [p.id, p]));
  const F = L.figures;
  const byCode = (a, b) => (a < b ? -1 : a > b ? 1 : 0);   // code-point order, as learn.py sorts
  const gloss = (el) => { if (window.Core && Core.glossary && Core.glossary.mark) Core.glossary.mark(el); };
  const dist = (m) => (m >= 1000 ? T('{n} km', { n: fmt(m / 1000, m % 1000 ? 1 : 0) }) : T('{n} m', { n: fmt(m) }));

  // ---- the cards: one for each built lesson, in the order of the parts ----
  function drawCards() {
    const order = L.parts.map(p => p.id);
    const ls = L.lessons.slice().sort((a, b) => order.indexOf(a.part) - order.indexOf(b.part) || byCode(a.code, b.code));
    cards.innerHTML = ls.map(l => {
      const tools = l.tools.map(tx).filter(Boolean);
      return `<a class="ln-card" href="#lesson-${esc(l.id)}">` +
        `<svg viewBox="0 0 272 76" aria-hidden="true" focusable="false"><use href="#lg-${esc(l.id)}"/></svg>` +
        `<span class="ln-code">${esc(l.code)} · ${esc(tx(parts[l.part].name))}</span>` +
        `<b>${esc(tx(l.title))}</b>` +
        `<span class="ln-term">${esc(T('GIS term: {term}', { term: tx(l.term) }))}</span>` +
        (tools.length ? `<span class="ln-uses">${esc(T('Map tools: {tools}', { tools: tools.join('; ') }))}</span>` : '') +
        `</a>`;
    }).join('');
    const more = document.getElementById('lnMore');
    if (more) more.textContent = L.planned ? Tn(L.planned, '{n} more lesson is planned.', '{n} more lessons are planned.') : '';
  }

  // ---- A1 Layers and shapes: what four real layers hold ----
  function drawShapes() {
    const el = document.getElementById('lnShapesFig'), s = F.shapes;
    if (!el) return;
    el.innerHTML = '<ul class="ln-list">' + [
      Th('<b>Points.</b> Tourism places draws {n} points, one for each place.', { n: fmt(s.points) }),
      Th('<b>Lines.</b> Watersheds and streams draws {n} stream lines.', { n: fmt(s.lines) }),
      Th('<b>Areas.</b> Barrios draws {n} areas. Together they fill the {m} areas of the municipios.', { n: fmt(s.barrios), m: fmt(s.municipios) }),
      Th('<b>Grid.</b> Surface heat is a grid of cells {size} m wide: {across} cells across and {down} down.', { size: fmt(s.cell_m), across: fmt(s.cells_across), down: fmt(s.cells_down) }),
    ].map(h => `<li>${h}</li>`).join('') + '</ul>';
    const a = document.getElementById('lnShapesTry');   // open the four layers over the same town the "What is near" lesson uses
    if (a) a.href = `index.html#c=${F.near.lat},${F.near.lng},14&l=places,watersheds,barrios,surfheat`;
    gloss(el);
  }

  const pm = (v, m, d) => T('{v} ± {m}', { v: fmt(v, d), m: fmt(m, d) });

  // ---- A2 What a shape knows: the row behind one barrio, and what a join by its GEOID adds ----
  function drawAttributes() {
    const el = document.getElementById('lnAttributesFig'), a = F.attributes;
    if (!el) return;
    const tr = (k, v) => `<tr><th scope="row">${esc(k)}</th><td>${v}</td></tr>`;
    el.innerHTML =
      `<p>${Th('The barrio with the most tourism places is <b>{b}</b>, in {m}. Its row in the Barrios layer has {n} columns. Some of them:', { b: a.barrio, m: a.municipality, n: fmt(a.fields) })}</p>` +
      `<table class="ln-table"><caption>${esc(T('From the map\'s layer'))}</caption><tbody>` +
      tr(T('GEOID'), esc(a.geoid)) + tr(T('Area, km²'), fmt(a.km2, 1)) + tr(T('Tourism places'), fmt(a.assets)) +
      tr(T('Places in the flood hazard area'), fmt(a.sfha)) + tr(T('Places to stay'), fmt(a.lodging)) + tr(T('Tourism places per km²'), fmt(a.per_km2, 1)) +
      `</tbody></table>` +
      `<table class="ln-table"><caption>${esc(T('Joined by its GEOID from the survey, {w}', { w: a.window }))}</caption><tbody>` +
      tr(T('Residents'), esc(pm(a.residents[0], a.residents[1], 0))) + tr(T('Median household income, $'), esc(pm(a.income[0], a.income[1], 0))) + tr(T('Median age'), esc(pm(a.age[0], a.age[1], 1))) +
      `</tbody></table>` +
      `<p>${Th('The survey file has <b>{n}</b> datasets for every barrio. Its codes match <b>{j}</b> of the {b} barrios of the map, so the join leaves none out.', { n: fmt(a.acs_fields), j: fmt(a.joined), b: fmt(a.barrios) })}</p>` +
      `<p>${Th('Names would not work as well: {k} barrio names are used by more than one barrio. "{name}" alone names {n}.', { k: fmt(a.shared_names), name: a.top_name.name, n: fmt(a.top_name.n) })}</p>`;
    gloss(el);
  }

  // ---- A3 How shapes relate: places in barrios, and the points that fall in none ----
  function drawRelations() {
    const el = document.getElementById('lnRelationsFig'), r = F.relations;
    if (!el) return;
    el.innerHTML =
      `<p>${Th('The {m} municipios are divided into <b>{b}</b> barrios. Every barrio lies in one municipio. {most} has the most, {n}; {one} is a single barrio.',
        { m: fmt(r.municipios), b: fmt(r.barrios), most: r.most.name, n: fmt(r.most.n), one: r.one.join(', ') })}</p>` +
      `<p>${Th('Of the {p} tourism places the observatory counts, <b>{in}</b> fall inside a barrio outline.', { p: fmt(r.places), in: fmt(r.in_barrio) })}</p>` +
      `<p>${Th('<b>{l}</b> places have a point that falls in no barrio. {off} of them are also outside every municipio: past the drawn coast, a median of {med} m from it.',
        { l: fmt(r.loose), off: fmt(r.off_island), med: fmt(r.median_m) })}</p>` +
      `<p class="ln-small">${esc(T('Tested with the map\'s own point-in-polygon code. The places counted and not drawn have no point; they are placed in their barrio and municipio another way.'))}</p>`;
    gloss(el);
  }

  // ---- A4 Colours and classes: the same 78 values in five classes by three methods ----
  let classM = 'quantile';
  const RAMP = ['#BDE0F2', '#8FCAE8', '#5FAFDA', '#338CB3', '#205D7B'];
  function drawClasses() {
    const el = document.getElementById('lnClassesFig'), c = F.classes;
    if (!el) return;
    const m = c.methods[classM], e = m.edges, lim = (v) => fmt(+v.toFixed(1), 1),   // a limit rounded as the map's legend rounds it
      lo = e[0], hi = e[e.length - 1], W = 600, X = (v) => 20 + (v - lo) / (hi - lo) * (W - 40);
    const chip = (k, label) => `<button type="button" class="ln-chip" data-classes="${k}" aria-pressed="${classM === k}">${esc(label)}</button>`;
    // one dot for each municipio along the scale of values, stacked where values are close; a band of colour for each class under it
    const order = c.values.map((v, i) => [v, i]).filter(x => x[0] != null).sort((p, q) => p[0] - q[0]);
    const lastX = [];
    const dots = order.map(([v, i]) => {
      const x = X(v); let row = 0;
      while (lastX[row] != null && x - lastX[row] < 9) row++;
      lastX[row] = x;
      return `<circle cx="${x.toFixed(1)}" cy="${(84 - row * 9).toFixed(1)}" r="4" fill="${RAMP[m.cls[i]]}" stroke="#2A2E2E" stroke-width=".6"><title>${esc(c.names[i])}: ${esc(fmt(v, 1))}%</title></circle>`;
    }).join('');
    const bands = e.slice(0, -1).map((a, k) => `<rect x="${X(a).toFixed(1)}" y="96" width="${Math.max(1, X(e[k + 1]) - X(a)).toFixed(1)}" height="14" fill="${RAMP[k]}"/>`).join('');
    const ticks = e.map(v => `<line x1="${X(v).toFixed(1)}" y1="92" x2="${X(v).toFixed(1)}" y2="114" stroke="#2A2E2E" stroke-width="1"/><text x="${X(v).toFixed(1)}" y="128" font-size="11" text-anchor="middle" fill="#2A2E2E">${esc(lim(v))}</text>`).join('');
    const svg = `<svg viewBox="0 0 ${W} 136" role="img" aria-label="${esc(T('The poverty rate of the {n} municipios on a scale, coloured by class; the limits of the five classes below', { n: fmt(c.n) }))}">${dots}${bands}${ticks}</svg>`;
    const rows = m.counts.map((n, k) => `<tr><th scope="row"><span class="ln-sw" style="background:${RAMP[k]}"></span>${esc(T('{a} to {b}%', { a: lim(e[k]), b: lim(e[k + 1]) }))}</th><td>${fmt(n)}</td></tr>`).join('');
    el.innerHTML =
      `<p>${Th('The share of residents below the poverty level, for the {n} municipios, in the survey that ends in {y}. Choose how to cut the classes:', { n: fmt(c.n), y: c.year })}</p>` +
      `<div class="ln-switch" role="group" aria-label="${esc(T('Method of the classes'))}">${chip('quantile', T('Quantiles'))}${chip('equal', T('Equal intervals'))}${chip('jenks', T('Natural breaks'))}</div>` +
      `<figure class="ln-fig ln-strip">${svg}</figure>` +
      `<table class="ln-table"><caption>${esc(T('Municipios in each class'))}</caption><thead><tr><th scope="col">${esc(T('Class'))}</th><th scope="col">${esc(T('Municipios'))}</th></tr></thead><tbody>${rows}</tbody></table>` +
      `<p>${Th('The darkest class holds <b>{q}</b> municipios in quantiles, <b>{e}</b> in equal intervals and <b>{j}</b> in natural breaks. Between quantiles and equal intervals, {moved} of the {n} municipios change class.',
        { q: fmt(c.methods.quantile.counts[4]), e: fmt(c.methods.equal.counts[4]), j: fmt(c.methods.jenks.counts[4]), moved: fmt(c.moved), n: fmt(c.n) })}</p>` +
      `<p class="ln-small">${esc(T('Classes made by the map\'s own code, as the Analysis tab makes them.'))}</p>`;
    gloss(el);
  }

  // ---- A6 How old, how sure: margins of error by the size of the area ----
  function drawSure() {
    const el = document.getElementById('lnSureFig'), s = F.sure;
    if (!el) return;
    const bar = (x, label) => {   // the estimate and its margin on a scale of 0 to 100%
      const a = Math.max(0, x.rate - x.moe), b = Math.min(100, x.rate + x.moe), P = (v) => 10 + v * 5.8;
      return `<g><text x="10" y="${label.y}" font-size="12" font-weight="700" fill="#2A2E2E">${esc(label.t)}</text>` +
        `<line x1="${P(a).toFixed(1)}" y1="${label.y + 14}" x2="${P(b).toFixed(1)}" y2="${label.y + 14}" stroke="#338CB3" stroke-width="8" stroke-linecap="round" opacity=".45"/>` +
        `<circle cx="${P(x.rate).toFixed(1)}" cy="${label.y + 14}" r="5" fill="#205D7B"/></g>`;
    };
    const axis = [0, 25, 50, 75, 100].map(v => `<text x="${10 + v * 5.8}" y="112" font-size="11" text-anchor="middle" fill="#5C5E5E">${esc(T('{n}%', { n: fmt(v) }))}</text>`).join('');
    const svg = `<svg viewBox="0 0 600 118" role="img" aria-label="${esc(T('Two poverty estimates with their margins of error'))}">` +
      bar(s.big, { y: 14, t: T('{b}, {m}: {r} residents', { b: s.big.barrio, m: s.big.municipality, r: fmt(s.big.residents) }) }) +
      bar(s.small, { y: 54, t: T('{b}, {m}: {r} residents', { b: s.small.barrio, m: s.small.municipality, r: fmt(s.small.residents) }) }) + axis + `</svg>`;
    el.innerHTML =
      `<p>${Th('The newest survey figures describe <b>{w}</b>: five years of answers pooled together.', { w: s.window })}</p>` +
      `<p>${Th('Poverty rate, with its margin of error: <b>{a}</b> in {b} and <b>{c}</b> in {d}.', { a: pm(s.big.rate, s.big.moe, 1) + '%', b: s.big.barrio, c: pm(s.small.rate, s.small.moe, 1) + '%', d: s.small.barrio })}</p>` +
      `<figure class="ln-fig">${svg}</figure>` +
      `<table class="ln-table"><caption>${esc(T('Poverty rates with a margin of error above 30% of the estimate'))}</caption>` +
      `<thead><tr><th scope="col">${esc(T('Areas'))}</th><th scope="col">${esc(T('With a rate'))}</th><th scope="col">${esc(T('Margin above 30%'))}</th><th scope="col">${esc(T('Share'))}</th></tr></thead><tbody>` +
      `<tr><th scope="row">${esc(T('Municipios'))}</th><td>${fmt(s.muni.n)}</td><td>${fmt(s.muni.flagged)}</td><td>${fmt(s.muni.pct, 1)}%</td></tr>` +
      `<tr><th scope="row">${esc(T('Barrios'))}</th><td>${fmt(s.barrio.n)}</td><td>${fmt(s.barrio.flagged)}</td><td>${fmt(s.barrio.pct, 1)}%</td></tr></tbody></table>` +
      `<p>${Th('For median household income, {none} barrios have no published estimate, and {f} of the {n} that have one carry a margin above 30%.', { none: fmt(s.income_barrio.none), f: fmt(s.income_barrio.flagged), n: fmt(s.income_barrio.n) })}</p>` +
      `<p class="ln-small">${esc(T('Margins at 90% confidence, as the Census Bureau publishes them. The 30% rule is the one the map uses to mark an area as less reliable.'))}</p>`;
    gloss(el);
  }

  // ---- A5 Counts and rates: the same places as a count and per 1,000 residents ----
  let ratesMode = 'count';
  function drawRates() {
    const el = document.getElementById('lnRatesFig'), r = F.rates;
    if (!el) return;
    const col = ratesMode === 'rate' ? 3 : 1, d = ratesMode === 'rate' ? 1 : 0;
    const ranked = r.rows.slice().sort((a, b) => b[col] - a[col] || byCode(a[0], b[0]));
    const follow = [r.top_count.name, r.top_rate.name];   // the two municipios the text follows, kept in view in both orders
    const rows = ranked.map((row, i) => ({ row, rank: i + 1 })).filter(x => x.rank <= 8 || follow.includes(x.row[0]));
    const max = ranked[0][col];
    const chip = (mode, label) => `<button type="button" class="ln-chip" data-rates="${mode}" aria-pressed="${ratesMode === mode}">${esc(label)}</button>`;
    let prev = 0;
    const lis = rows.map(({ row, rank }) => {
      const gap = rank - prev > 1 ? '<li class="ln-gap" aria-hidden="true">…</li>' : '';
      prev = rank;
      const cls = row[0] === r.top_count.name ? ' ln-a' : row[0] === r.top_rate.name ? ' ln-b' : '';
      return gap + `<li class="ln-row${cls}"><span class="ln-rank">${fmt(rank)}</span><span class="ln-name">${esc(row[0])}</span>` +
        `<span class="ln-track"><span class="ln-bar" style="width:${Math.max(1, Math.round(row[col] / max * 100))}%"></span></span>` +
        `<span class="ln-num">${fmt(row[col], d)}</span></li>`;
    }).join('');
    el.innerHTML =
      `<div class="ln-switch" role="group" aria-label="${esc(T('Show tourism places as'))}">${chip('count', T('A count'))}${chip('rate', T('Per 1,000 residents'))}</div>` +
      `<p class="ln-cap">${esc(ratesMode === 'rate' ? T('Tourism places per 1,000 residents, by municipio: the eight highest') : T('Tourism places by municipio: the eight highest counts'))}</p>` +
      `<ol class="ln-bars">${lis}</ol>` +
      `<p>${Th('By count, <b>{a}</b> is first of the {k} municipios, with {n} tourism places. Per 1,000 residents it is number {rank}, with {rate}.',
        { a: r.top_count.name, k: fmt(r.rows.length), n: fmt(r.top_count.count), rank: fmt(r.top_count.rank_by_rate), rate: fmt(r.top_count.rate, 1) })}</p>` +
      `<p>${Th('Per 1,000 residents, <b>{b}</b> is first, with {rate}. It has {n} tourism places and {pop} residents, and is number {rank} by count.',
        { b: r.top_rate.name, rate: fmt(r.top_rate.rate, 1), n: fmt(r.top_rate.count), pop: fmt(r.top_rate.residents), rank: fmt(r.top_rate.rank_by_count) })}</p>` +
      `<p class="ln-small">${esc(T('Tourism places as the observatory counts them, and residents in the 2020 Census.'))}</p>`;
    gloss(el);
  }

  // ---- B3 What is near: what each distance around a public plaza holds ----
  // ---- C1 The size of the area changes the answer: one survey figure by municipio and by barrio; the fullest area at three sizes ----
  function drawAreasize() {
    const el = document.getElementById('lnAreasizeFig'), a = F.areasize;
    if (!el) return;
    const P = (v) => 10 + v * 5.8, row = (y, lo, hi, label, col) =>
      `<text x="10" y="${y}" font-size="12" font-weight="700" fill="#2A2E2E">${esc(label)}</text>` +
      `<line x1="${P(lo).toFixed(1)}" y1="${y + 14}" x2="${P(hi).toFixed(1)}" y2="${y + 14}" stroke="${col}" stroke-width="10" stroke-linecap="round"/>` +
      `<text x="${P(lo).toFixed(1)}" y="${y + 34}" font-size="11" text-anchor="middle" fill="#2A2E2E">${esc(T('{n}%', { n: fmt(lo, 1) }))}</text>` +
      `<text x="${P(hi).toFixed(1)}" y="${y + 34}" font-size="11" text-anchor="middle" fill="#2A2E2E">${esc(T('{n}%', { n: fmt(hi, 1) }))}</text>`;
    const svg = `<svg viewBox="0 0 600 112" role="img" aria-label="${esc(T('The range of the poverty rate by municipio and by barrio, on a scale of 0 to 100%'))}">` +
      row(12, a.muni.lo, a.muni.hi, T('{n} municipios', { n: fmt(a.muni.n) }), '#5FAFDA') + row(62, a.barrio.lo, a.barrio.hi, T('{n} barrios', { n: fmt(a.barrio.n) }), '#205D7B') + `</svg>`;
    const s = a.spread;
    el.innerHTML =
      `<p>${Th('The poverty rate in {w}. By municipio it runs from <b>{a}%</b> to <b>{b}%</b>. By barrio it runs from <b>{c}%</b> to <b>{d}%</b>.', { w: a.window, a: fmt(a.muni.lo, 1), b: fmt(a.muni.hi, 1), c: fmt(a.barrio.lo, 1), d: fmt(a.barrio.hi, 1) })}</p>` +
      `<figure class="ln-fig">${svg}</figure>` +
      `<p>${Th('{n} barrios are above the highest municipio, and {m} below the lowest. In <b>{muni}</b> ({r}%), the barrios run from {lo}% to {hi}%.', { n: fmt(a.barrio.above), m: fmt(a.barrio.below), muni: s.municipality, r: fmt(s.rate, 1), lo: fmt(s.low.rate, 1), hi: fmt(s.high.rate, 1) })}</p>` +
      `<p>${Th('The fullest area for tourism places changes with the size too: <b>{m}</b> by municipio ({mn}), <b>{b}</b> by barrio ({bn}), and a hexagon of {k} km² with {h}.', { m: F.rates.top_count.name, mn: fmt(F.rates.top_count.count), b: F.count.max_barrio, bn: fmt(F.count.max), k: fmt(F.hex.km2), h: fmt(F.hex.max) })}</p>` +
      `<p class="ln-small">${esc(T('Barrios count here only where the margin of error is within 30% of the estimate, so a gap is not the noise of a small sample.'))}</p>`;
    gloss(el);
  }

  // ---- C2 Two patterns that match are not a cause: degrees against poverty, by municipio and by barrio ----
  function drawCause() {
    const el = document.getElementById('lnCauseFig'), c = F.cause;
    if (!el) return;
    const pts = c.muni.points.filter(p => p[0] != null && p[1] != null), X = (v) => 50 + v * 8.5, Y = (v) => 210 - v * 3;
    const xmax = Math.ceil(Math.max(...pts.map(p => p[0])) / 10) * 10;
    const ax = [0, 20, 40, 60].filter(v => v <= xmax).map(v => `<text x="${X(v)}" y="228" font-size="11" text-anchor="middle" fill="#5C5E5E">${esc(T('{n}%', { n: fmt(v) }))}</text>`).join('') +
      [0, 20, 40, 60].map(v => `<text x="44" y="${Y(v) + 4}" font-size="11" text-anchor="end" fill="#5C5E5E">${esc(T('{n}%', { n: fmt(v) }))}</text>`).join('');
    const svg = `<svg viewBox="0 0 ${X(xmax) + 20} 250" role="img" aria-label="${esc(T('The {n} municipios by their share of adults with a degree and their poverty rate', { n: fmt(pts.length) }))}">` +
      `<line x1="50" y1="210" x2="${X(xmax)}" y2="210" stroke="#8C8E8E"/><line x1="50" y1="210" x2="50" y2="20" stroke="#8C8E8E"/>` +
      pts.map(p => `<circle cx="${X(p[0]).toFixed(1)}" cy="${Y(p[1]).toFixed(1)}" r="4" fill="#338CB3" fill-opacity=".75"/>`).join('') + ax +
      `<text x="${(X(xmax) + 50) / 2}" y="246" font-size="11" text-anchor="middle" fill="#2A2E2E">${esc(T('Adults with a bachelor\'s degree'))}</text>` +
      `<text x="56" y="14" font-size="11" fill="#2A2E2E">${esc(T('Poverty rate'))}</text></svg>`;
    el.innerHTML =
      `<p>${Th('Across the {n} municipios, the share of adults with a bachelor\'s degree and the poverty rate move in opposite directions: <b>r = {r}</b>.', { n: fmt(c.muni.n), r: fmt(c.muni.r, 2) })}</p>` +
      `<figure class="ln-fig ln-strip">${svg}</figure>` +
      `<p>${Th('Across {n} barrios the same two measures give <b>r = {r}</b>: the same direction, but weaker. A correlation depends on the areas it is measured in.', { n: fmt(c.barrio.n), r: fmt(c.barrio.r, 2) })}</p>` +
      `<p>${esc(T('Neither number says that a degree lowers poverty, or that poverty keeps people from a degree. Both can come from something else, such as where jobs are.'))}</p>` +
      `<p class="ln-small">${esc(T('Correlation computed by the map\'s own code, as the Analysis tab\'s workbench computes it, on the survey that ends in {y}.', { y: c.year }))}</p>`;
    gloss(el);
  }

  // ---- C3 What a map leaves out: counted and not drawn, and estimates not published ----
  function drawLeftout() {
    const el = document.getElementById('lnLeftoutFig'), o = F.leftout;
    if (!el) return;
    const stat = (v, label) => `<div class="ln-stat"><b>${v}</b><span>${esc(label)}</span></div>`;
    el.innerHTML =
      `<div class="ln-stats">${stat(fmt(o.withheld), T('tourism listings counted, never drawn'))}${stat(fmt(o.no_income), T('barrios with no published income'))}</div>` +
      `<p>${Th('<b>{n}</b> tourism listings have no point and no name in the published file: {h} holiday rentals, and {a} rented units whose name is a street address. They still count in their barrio and municipio.', { n: fmt(o.withheld), h: fmt(o.reasons.holiday_rental || 0), a: fmt(o.reasons.address || 0) })}</p>` +
      `<p>${Th('{c} of them are among the {t} tourism places the map counts (confidence 0.50 or more, no places of worship).', { t: fmt(o.counted), c: fmt(o.counted_not_drawn) })}</p>` +
      `<p>${Th('For median household income in {w}, <b>{n}</b> of the {b} barrios have no published estimate.', { w: o.window, n: fmt(o.no_income), b: fmt(o.barrios) })}</p>`;
    gloss(el);
  }

  // ---- D1 Bring your own data: what the tools accept, read from their own code ----
  function drawOwndata() {
    const el = document.getElementById('lnOwndataFig'), o = F.owndata;
    if (!el) return;
    el.innerHTML = '<ul class="ln-list">' + [
      Th('<b>Count my points</b> reads up to {n} points, in a file of up to {mb} MB. A count under {min} is shown as "fewer than {min}".', { n: fmt(o.max_points), mb: fmt(o.max_mb), min: fmt(o.min_shown) }),
      Th('<b>Study areas</b> holds up to {n} areas in a set, from a file of up to {mb} MB.', { n: fmt(o.max_areas), mb: fmt(o.areas_mb) }),
      esc(T('Nothing you load leaves your browser: the page sends no request with it.')),
    ].map(h => `<li>${h}</li>`).join('') + '</ul>';
    gloss(el);
  }

  // ---- D2 From the observatory to QGIS: the files, and the parts of a GEOID ----
  function drawQgis() {
    const el = document.getElementById('lnQgisFig'), q = F.qgis, g = q.geoid;
    if (!el) return;
    const part = (code, label) => `<span class="ln-geoid"><b>${esc(code)}</b><small>${esc(label)}</small></span>`;
    el.innerHTML =
      `<p>${Th('<b>{f}</b> has {n} barrios in {kb} KB. <b>{m}</b> has {mn} municipios in {mkb} KB. Both store longitude and latitude in degrees (GeoJSON, RFC 7946).', { f: q.barrios.file, n: fmt(q.barrios.features), kb: fmt(q.barrios.kb), m: q.municipios.file, mn: fmt(q.municipios.features), mkb: fmt(q.municipios.kb) })}</p>` +
      `<p>${Th('The GEOID of {b}, in {m}, read in three parts:', { b: g.barrio, m: g.municipality })}</p>` +
      `<p class="ln-geoids">${part(g.state, T('Puerto Rico'))}${part(g.county, T('municipio'))}${part(g.subdivision, T('barrio'))}</p>` +
      `<p>${Th('To measure in metres, reproject to <b>NAD83 / Puerto Rico &amp; Virgin Is.</b> (EPSG:32161).')}</p>`;
    gloss(el);
  }

  // the workshop guide prints alone: the page is marked while the browser prints, so learn.css hides everything else
  const printBtn = document.getElementById('lnPrintGuide');
  if (printBtn && printBtn.addEventListener) printBtn.addEventListener('click', () => {
    document.body.classList.add('ln-print-guide');
    const done = () => { document.body.classList.remove('ln-print-guide'); window.removeEventListener('afterprint', done); };
    window.addEventListener('afterprint', done);
    window.print();
  });

  let nearI = 1;   // 800 m, the distance the Area around a point tool opens with
  function drawNear() {
    const el = document.getElementById('lnNearFig'), n = F.near;
    if (!el) return;
    const ring = n.rings[nearI], base = n.rings[0], R = 92, C = 104;
    const chips = n.rings.map((r, i) => `<button type="button" class="ln-chip" data-ring="${i}" aria-pressed="${i === nearI}">${esc(dist(r.m))}</button>`).join('');
    // the chosen ring fills the drawing; the shorter distances are drawn inside it at the same scale
    const inner = n.rings.slice(0, nearI).map(r => `<circle cx="${C}" cy="${C}" r="${(R * r.m / ring.m).toFixed(1)}" fill="none" stroke="#338CB3" stroke-width="1" stroke-dasharray="3 3"/>`).join('');
    const svg = `<svg viewBox="0 0 208 208" role="img" aria-label="${esc(T('A ring of {d} around the plaza, with the shorter distances inside it', { d: dist(ring.m) }))}">` +
      `<circle cx="${C}" cy="${C}" r="${R}" fill="#BDE0F2" stroke="#338CB3" stroke-width="2"/>${inner}` +
      `<line x1="${C}" y1="${C}" x2="${C + R}" y2="${C}" stroke="#205D7B" stroke-width="1.5"/>` +
      `<text x="${C + R / 2}" y="${C - 6}" font-size="13" font-weight="700" fill="#205D7B" text-anchor="middle">${esc(dist(ring.m))}</text>` +
      `<circle cx="${C}" cy="${C}" r="6" fill="#FF4D38" stroke="#FFFFFF" stroke-width="2"/></svg>`;
    const times = ring.m / base.m, x = times * times;
    const stat = (v, label) => `<div class="ln-stat"><b>${v}</b><span>${esc(label)}</span></div>`;
    const tr = (r, i) => `<tr${i === nearI ? ' class="ln-on"' : ''}><th scope="row">${esc(dist(r.m))}</th><td>${fmt(r.places)}</td><td>${fmt(r.residents)}</td><td>${fmt(r.km2, 1)}</td></tr>`;
    el.innerHTML =
      `<p>${Th('Around <b>{place}</b>, in {muni}. Choose a distance:', { place: n.place, muni: n.municipality })}</p>` +
      `<div class="ln-switch" role="group" aria-label="${esc(T('Distance of the ring'))}">${chips}</div>` +
      `<div class="ln-near">${svg}<div>` +
      `<div class="ln-stats">${stat(fmt(ring.places), T('tourism places'))}${stat(fmt(ring.residents), T('residents, about'))}${stat(fmt(ring.km2, 1), T('km² of land and sea'))}</div>` +
      `<p>${nearI ? Th('This ring holds <b>{x} times</b> the area of the {d} ring, for a distance {t} times as long.', { x: fmt(x, x % 1 ? 1 : 0), d: dist(base.m), t: fmt(times, times % 1 ? 1 : 0) })
        : esc(T('This is the shortest distance. Choose a longer one and watch how fast the area grows.'))}</p>` +
      `</div></div>` +
      `<table class="ln-table"><caption>${esc(T('Every distance, in a straight line from the plaza'))}</caption>` +
      `<thead><tr><th scope="col">${esc(T('Distance'))}</th><th scope="col">${esc(T('Tourism places'))}</th><th scope="col">${esc(T('Residents'))}</th><th scope="col">${esc(T('Area, km²'))}</th></tr></thead>` +
      `<tbody>${n.rings.map(tr).join('')}</tbody></table>` +
      `<p class="ln-small">${esc(T('Counted as the Area around a point tool counts them: every listed tourism place that has a point, and the residents of the 2020 Census blocks whose point falls inside the ring.'))}</p>`;
    const at = `c=${n.lat},${n.lng},16`;
    const a = document.getElementById('lnNearTry'), b = document.getElementById('lnNearRings');
    if (a) a.href = `index.html#${at}&l=places&mt=b:study:saAroundH`;
    if (b) b.href = `index.html#${at}&l=stops,rings`;
    gloss(el);
  }

  // ---- B1 How many, how much: tourism places counted by barrio ----
  function drawCount() {
    const el = document.getElementById('lnCountFig'), c = F.count;
    if (!el) return;
    const label = (i) => (i === 0 ? T('none') : i === c.bins.length - 1 ? T('{n} or more', { n: fmt(c.bins[i]) }) : T('{a} to {b}', { a: fmt(c.bins[i]), b: fmt(c.bins[i + 1] - 1) }));
    const max = Math.max(...c.hist);
    const bars = c.hist.map((n, i) => `<li class="ln-row"><span class="ln-name">${esc(label(i))}</span>` +
      `<span class="ln-track"><span class="ln-bar" style="width:${Math.max(1, Math.round(n / max * 100))}%"></span></span><span class="ln-num">${fmt(n)}</span></li>`).join('');
    el.innerHTML =
      `<p>${Th('Tourism places are counted in <b>{b}</b> barrios: {t} in all.', { b: fmt(c.barrios), t: fmt(c.total) })}</p>` +
      `<p>${Th('The mean is <b>{mean}</b> places a barrio. The median barrio has <b>{median}</b>. {below} of the {b} barrios are below the mean.', { mean: fmt(c.mean, 1), median: fmt(c.median), below: fmt(c.below_mean), b: fmt(c.barrios) })}</p>` +
      `<p>${Th('{barrio}, in {muni}, has {max}. {none} barrios have none. The tenth of the barrios with the most hold {share}% of all the places.', { barrio: c.max_barrio, muni: c.max_municipio, max: fmt(c.max), none: fmt(c.none), share: fmt(c.top_decile_share, 1) })}</p>` +
      `<p class="ln-cap">${esc(T('Barrios by the number of tourism places they hold'))}</p><ol class="ln-bars ln-hist">${bars}</ol>` +
      `<p class="ln-small">${esc(T('Tourism places as the observatory counts them, by the barrio each one falls in.'))}</p>`;
    gloss(el);
  }

  // ---- B2 What overlaps: tourism places inside another layer ----
  let overlayKey = 'flood';
  function drawOverlay() {
    const el = document.getElementById('lnOverlayFig'), o = F.overlay;
    if (!el) return;
    const L2 = o[overlayKey];
    const chip = (k, label) => `<button type="button" class="ln-chip" data-overlay="${k}" aria-pressed="${overlayKey === k}">${esc(label)}</button>`;
    const rows = L2.top.map(r => `<tr><th scope="row">${esc(r[0])}</th><td>${fmt(r[1])}</td><td>${fmt(r[2])}</td><td>${fmt(r[3], 1)}%</td></tr>`).join('');
    el.innerHTML =
      `<div class="ln-switch" role="group" aria-label="${esc(T('Layer placed under the tourism places'))}">${chip('flood', T('Flood hazard area'))}${chip('protected', T('Protected areas'))}</div>` +
      `<p>${overlayKey === 'flood'
        ? Th('<b>{n}</b> of the {t} tourism places are inside FEMA\'s Special Flood Hazard Area: <b>{pct}%</b>.', { n: fmt(L2.inside), t: fmt(o.places), pct: fmt(L2.pct, 1) })
        : Th('<b>{n}</b> of the {t} tourism places are inside a protected area: <b>{pct}%</b>.', { n: fmt(L2.inside), t: fmt(o.places), pct: fmt(L2.pct, 1) })}</p>` +
      `<table class="ln-table"><caption>${esc(T('The five municipios with the largest share inside'))}</caption>` +
      `<thead><tr><th scope="col">${esc(T('Municipio'))}</th><th scope="col">${esc(T('Inside'))}</th><th scope="col">${esc(T('Tourism places'))}</th><th scope="col">${esc(T('Share'))}</th></tr></thead><tbody>${rows}</tbody></table>` +
      `<p>${esc(Tn(L2.none, '{n} municipio has no place inside.', '{n} municipios have no place inside.'))}</p>` +
      `<p class="ln-small">${esc(T('Each place is a point; the build checks which outline it falls in.'))}</p>`;
    gloss(el);
  }

  // ---- B4 How to get there: a walk along the roads beside the ring of the same distance ----
  let walkI = 1;   // 10 minutes
  function drawWalk() {
    const el = document.getElementById('lnNetworkFig'), w = F.walk;
    if (!el) return;
    const s = w.steps[walkI];
    const chips = w.steps.map((x, i) => `<button type="button" class="ln-chip" data-walk="${i}" aria-pressed="${i === walkI}">${esc(T('{n} minutes', { n: fmt(x.min) }))}</button>`).join('');
    const pair = (label, a, b2, d) => `<li class="ln-row ln-b"><span class="ln-name">${esc(T('Ring'))}</span><span class="ln-track"><span class="ln-bar" style="width:100%"></span></span><span class="ln-num">${fmt(a, d)}</span></li>` +
      `<li class="ln-row ln-a"><span class="ln-name">${esc(T('Walk'))}</span><span class="ln-track"><span class="ln-bar" style="width:${Math.max(1, Math.round(b2 / a * 100))}%"></span></span><span class="ln-num">${fmt(b2, d)}</span></li>`;
    const tr = (x, i) => `<tr${i === walkI ? ' class="ln-on"' : ''}><th scope="row">${esc(T('{n} minutes', { n: fmt(x.min) }))}</th><td>${esc(dist(x.m))}</td><td>${fmt(x.residents)}</td><td>${fmt(x.ring_residents)}</td><td>${fmt(x.km2, 1)}</td><td>${fmt(x.ring_km2, 1)}</td></tr>`;
    el.innerHTML =
      `<p>${Th('A walk from <b>{place}</b>, in {muni}, at 4.8 km an hour. Choose the minutes:', { place: w.place, muni: w.municipality })}</p>` +
      `<div class="ln-switch" role="group" aria-label="${esc(T('Minutes of the walk'))}">${chips}</div>` +
      `<p>${Th('In <b>{min} minutes</b> ({d}) the walk along mapped roads reaches about <b>{r}</b> residents. The ring of {d} holds {rr}. The walk reaches <b>{pct}%</b> of them.',
        { min: fmt(s.min), d: dist(s.m), r: fmt(s.residents), rr: fmt(s.ring_residents), pct: fmt(s.residents / s.ring_residents * 100) })}</p>` +
      `<p class="ln-cap">${esc(T('Residents'))}</p><ol class="ln-bars ln-pair">${pair('', s.ring_residents, s.residents, 0)}</ol>` +
      `<p class="ln-cap">${esc(T('Area, km²'))}</p><ol class="ln-bars ln-pair">${pair('', s.ring_km2, s.km2, 1)}</ol>` +
      `<table class="ln-table"><caption>${esc(T('Every walk, beside the ring of the same distance'))}</caption>` +
      `<thead><tr><th scope="col">${esc(T('Walk'))}</th><th scope="col">${esc(T('Distance'))}</th><th scope="col">${esc(T('Residents, walk'))}</th><th scope="col">${esc(T('Residents, ring'))}</th><th scope="col">${esc(T('km², walk'))}</th><th scope="col">${esc(T('km², ring'))}</th></tr></thead>` +
      `<tbody>${w.steps.map(tr).join('')}</tbody></table>` +
      `<p class="ln-small">${esc(T('Traced as the Walking time tool traces it, on the mapped roads; residents of the 2020 Census blocks whose point falls inside.'))}</p>`;
    const a = document.getElementById('lnWalkTry');
    if (a) a.href = `index.html#c=${w.lat},${w.lng},15&mt=b:study:saWalkH`;
    gloss(el);
  }

  // ---- B5 Between measurements: how far apart the rain gauges are (read from the layer's own file when the lesson comes into view) ----
  let rainP = null;
  function drawBetween() {
    const el = document.getElementById('lnBetweenFig');
    if (!el || rainP) return;
    el.innerHTML = `<p class="ln-small">${esc(T('Reading the rain gauges…'))}</p>`;
    rainP = fetchJson('data/rain_gauges.geojson').then((g) => {   // common.js: tried again once when a download fails
      const pts = g.features.map(f => f.geometry.coordinates).filter(c => Array.isArray(c) && isFinite(c[0]) && isFinite(c[1]));
      const km = (a, b2) => Math.hypot((a[0] - b2[0]) * 111.32 * Math.cos(a[1] * Math.PI / 180), (a[1] - b2[1]) * 110.574);
      const near = pts.map((a, i) => Math.min(...pts.filter((_, j) => j !== i).map(b2 => km(a, b2)))).sort((x, y) => x - y);
      const median = near.length % 2 ? near[(near.length - 1) / 2] : (near[near.length / 2 - 1] + near[near.length / 2]) / 2;
      el.innerHTML =
        `<p>${Th('<b>Rainfall</b> draws <b>{n}</b> rain gauges for {km2} km² of land: one gauge for every <b>{per}</b> km².', { n: fmt(pts.length), km2: fmt(F.land_km2), per: fmt(F.land_km2 / pts.length) })}</p>` +
        `<p>${Th('From a gauge, the nearest other gauge is {med} km away (the median). The most isolated gauge is <b>{max} km</b> from any other.', { med: fmt(median, 1), max: fmt(near[near.length - 1], 1) })}</p>` +
        `<p>${Th('<b>Surface heat</b> has a measured value in every cell of {m} m.', { m: fmt(F.shapes.cell_m) })}</p>` +
        `<p class="ln-small">${esc(T('The gauges are read from the layer\'s own file as you open this lesson, so the count is today\'s.'))}</p>`;
      gloss(el);
    }, () => { rainP = null; el.innerHTML = `<p class="ln-small">${esc(T('The rain gauges could not be read. Check your connection and open the lesson again.'))}</p>`; });
  }

  // ---- B6 Where things concentrate: tourism places counted in hexagons of equal area ----
  function drawHex() {
    const el = document.getElementById('lnConcentrateFig'), h = F.hex;
    if (!el) return;
    el.innerHTML =
      `<p>${Th('The <b>{p}</b> tourism places on the map fall in <b>{c}</b> hexagons of {a} km².', { p: fmt(h.places), c: fmt(h.cells), a: fmt(h.km2) })}</p>` +
      `<p>${Th('Half of the places are in only <b>{h}</b> of those hexagons ({pct}%). The ten fullest hold {t}% of all the places.', { h: fmt(h.half_cells), pct: fmt(h.half_pct_of_cells, 1), t: fmt(h.top10_pct, 1) })}</p>` +
      `<p>${Th('The fullest hexagon has {max} places. {one} hexagons have a single place.', { max: fmt(h.max), one: fmt(h.one) })}</p>` +
      `<p class="ln-small">${esc(T('Counted as "Places in hexagons" counts them, with the map\'s own filters.'))}</p>`;
    gloss(el);
  }

  // a pressed chip redraws its lesson and keeps the keyboard focus on the same choice
  document.addEventListener('click', (e) => {
    const b = e.target.closest('.ln-chip');
    if (!b) return;
    if (b.dataset.rates) { ratesMode = b.dataset.rates; drawRates(); const f = document.querySelector(`.ln-chip[data-rates="${ratesMode}"]`); if (f) f.focus(); }
    else if (b.dataset.ring) { nearI = +b.dataset.ring; drawNear(); const f = document.querySelector(`.ln-chip[data-ring="${nearI}"]`); if (f) f.focus(); }
    else if (b.dataset.overlay) { overlayKey = b.dataset.overlay; drawOverlay(); const f = document.querySelector(`.ln-chip[data-overlay="${overlayKey}"]`); if (f) f.focus(); }
    else if (b.dataset.classes) { classM = b.dataset.classes; drawClasses(); const f = document.querySelector(`.ln-chip[data-classes="${classM}"]`); if (f) f.focus(); }
    else if (b.dataset.walk) { walkI = +b.dataset.walk; drawWalk(); const f = document.querySelector(`.ln-chip[data-walk="${walkI}"]`); if (f) f.focus(); }
  });

  drawCards(); drawShapes(); drawAttributes(); drawRelations(); drawClasses(); drawRates(); drawSure(); drawNear(); drawCount(); drawOverlay(); drawWalk(); drawHex(); drawAreasize(); drawCause(); drawLeftout(); drawOwndata(); drawQgis();
  // the rain gauges are a file of their own: it is read only when its lesson comes near the screen
  const between = document.getElementById('lesson-between');
  if (between && typeof IntersectionObserver === 'function') { const io = new IntersectionObserver((es) => { if (es.some(e => e.isIntersecting)) { io.disconnect(); drawBetween(); } }, { rootMargin: '600px' }); io.observe(between); }
  else if (between) drawBetween();
  const toBetween = () => { if (location.hash === '#lesson-between') drawBetween(); };   // a link straight to the lesson
  window.addEventListener('hashchange', toBetween); toBetween();
})();
