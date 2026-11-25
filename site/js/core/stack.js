/* PR Data Observatory core: the legends that only the map page draws.
     Stack.blocks(E, layers, evals, small)  the legend of the layer stack on the Economy tab's map: one block for one shaded layer, one for two shaded layers together (a bivariate map),
                                            and one for each layer of sized symbols; `small` is true on a phone (smaller symbols)
     Stack.box(title, rows, note, unit)     a titled box of color rows with a note (the shading menu of the Layers tab); unit(n) says what is counted in a row (municipalities unless told otherwise)
     Stack.mini(title, rows)                the same rows without the note (the legend on the map itself) */
(function (name, root, factory) {
  const dep = (n) => (typeof module === 'object' && module.exports ? require('./' + n + '.js') : root.Core[n]);   // the other core modules, in Node or in a page
  const api = factory(root, dep);
  if (typeof module === 'object' && module.exports) module.exports = api; else { root.Core = root.Core || {}; root.Core[name] = api; }
})('stack', typeof window !== 'undefined' ? window : globalThis, function (root, dep) {
  'use strict';
  const { T, Tn, esc } = dep('text'), palettes = dep('palettes'), legend = dep('legend'), classify = dep('classify');
  const reliability = () => dep('reliability'), time = () => dep('time');   // read when a legend is drawn: on the map they load with the Economy tab (js/econ_shell.js), after this file
  const counts = legend.counts;

  /** Under the rows of a layer: what is flagged less reliable and why (hatched, or a dashed outline), and the note about withheld figures. `prefix` names the layer when two share a block. */
  function reliable(E, L, e, prefix = '') {
    return reliability().notes(E, L, e).map(n => n.swatch ? `<div class="row rel"><span class="sw ${n.swatch}"></span>${esc(prefix + n.label)}<small>${n.n}</small></div>` : `<div class="el-note">${esc(prefix + n.label)}</div>`).join('');
  }
  /** A line that says what an empty place means, for a dataset that says (a shortage area: "No area shortage designation") and has empty places; the single legend has its own. `prefix` names the layer when two share a block. */
  function empty(E, L, e, prefix = '') {
    const nv = E.V[L.key].noValue, n = nv ? e.a.slice(0, E.geo.pr).filter(x => x == null).length : 0;
    return n ? `<div class="row"><span class="sw" style="background:${palettes.NOVAL}"></span>${esc(prefix + T(nv))}<small>${n}</small></div>` : '';
  }
  /** A warning when every area with a value has the same one: the view tells no places apart (the population per 1,000 residents was 1,000 everywhere; review 2026-11-05). */
  function flat(E, e, prefix = '') {
    const v = e.a.slice(0, E.geo.pr).filter(x => x != null && isFinite(x));
    return v.length > 1 && v.every(x => x === v[0]) ? `<div class="el-note el-flat" role="note">${esc(prefix + T("Every area has the same value in this view, so the map shows no differences. Choose another view in the layer's Settings."))}</div>` : '';
  }
  function divLabels(E, L, b) {   // the five classes of a scale around a center, in words
    const sp = b.span, c = b.center, f = (x) => E.fmt(L, x, true);
    return [T('below {v}', { v: f(c - .5 * sp) }), T('{from} to {to}', { from: f(c - .5 * sp), to: f(c - .1 * sp) }), T('near {v}', { v: f(c) }), T('{from} to {to}', { from: f(c + .1 * sp), to: f(c + .5 * sp) }), T('above {v}', { v: f(c + .5 * sp) })];
  }
  function bivariate(E, A, B, ea, eb) {
    const ba = E.breaks(A, ea.y, 3), bb = E.breaks(B, eb.y, 3), f = (L, x) => E.fmt(L, x, true);
    const cut = (b, L, i) => i === 0 ? T('up to {v}', { v: f(L, b.edges[1]) }) : i === 2 ? T('above {v}', { v: f(L, b.edges[2]) }) : T('{from} to {to}', { from: f(L, b.edges[1]), to: f(L, b.edges[2]) });
    const nameA = T(E.V[A.key].label), nameB = T(E.V[B.key].label), BIV = palettes.BIVARIATE;
    return `<div class="el-block"><div class="el-t">${esc(T('Two datasets together'))} <small>(${esc(A.classes === 'quantile' && B.classes === 'quantile' ? T('terciles of each') : T('three classes of each'))})</small></div><div class="el-biv"><div class="biv-grid" role="img" aria-label="${esc(T('Bivariate legend: {a} increases to the right, {b} increases upward', { a: nameA, b: nameB }))}">${[2, 1, 0].map(r => [0, 1, 2].map(c => `<i style="background:${BIV[r][c]}"></i>`).join('')).join('')}</div><div class="biv-axes"><span><b>→</b> ${esc(nameA)} <small>${esc(T('{chip}; low {low}, high {high}', { chip: E.chip(A, ea), low: cut(ba, A, 0), high: cut(ba, A, 2) }))}</small></span><span><b>↑</b> ${esc(nameB)} <small>${esc(T('{chip}; low {low}, high {high}', { chip: E.chip(B, eb), low: cut(bb, B, 0), high: cut(bb, B, 2) }))}</small></span></div></div>${flat(E, ea, nameA + ': ')}${flat(E, eb, nameB + ': ')}${empty(E, A, ea, nameA + ': ')}${empty(E, B, eb, nameB + ': ')}${reliable(E, A, ea, nameA + ': ')}${reliable(E, B, eb, nameB + ': ')}</div>`;
  }
  /** A small histogram of the values with the class breaks marked: how many places sit near a break (map review 2026-11-05). */
  function hist(b, vals) {
    const v = vals.filter(x => x != null && isFinite(x)); if (v.length < 10 || !b.edges) return '';
    const lo = Math.min(...v), hi = Math.max(...v), N = 24, c = new Array(N).fill(0); if (hi <= lo) return '';
    v.forEach(x => c[Math.min(N - 1, Math.floor((x - lo) / (hi - lo) * N))]++);
    const mx = Math.max(...c), cuts = b.edges.slice(1, -1).filter(x => x > lo && x < hi);
    return `<div class="el-hist" role="img" aria-label="${esc(T('How the values spread, with the class breaks'))}">${c.map(n => `<i style="height:${Math.round(n / mx * 100)}%"></i>`).join('')}${cuts.map(x => `<b style="left:${Math.round((x - lo) / (hi - lo) * 100)}%"></b>`).join('')}</div>`;
  }
  function single(E, L, e) {
    const b = E.breaks(L, e.y), cols = b.div ? palettes.DIVERGING : E.ramp(L), vals = e.a.slice(0, E.geo.pr), n = counts(b, vals);
    const labels = b.div ? divLabels(E, L, b) : cols.map((_, i) => classify.single(b, i) ? E.fmt(L, b.edges[i], true) : T('{from} to {to}', { from: E.fmt(L, b.edges[i], true), to: E.fmt(L, b.edges[i + 1], true) }));   // a class of one value (the zeros of a count, the barrios outside every non-attainment area) is named, not "0 to 0"
    const rows = cols.map((col, i) => [col, labels[i], n[i]]);
    const nod = vals.filter(x => x == null).length;
    return `<div class="el-block"><div class="el-t">${esc(E.title(L, e.y))} <small>${esc(E.chip(L, e))}</small></div>${flat(E, e)}${hist(b, vals)}${rows.filter((r, i) => (r[2] || !b.div) && !classify.hidden(b, i)).map(r => `<div class="row"><span class="sw" style="background:${r[0]}"></span>${esc(r[1])}<small>${r[2]}</small></div>`).join('')}${nod ? `<div class="row"><span class="sw" style="background:${palettes.NOVAL}"></span>${esc(T(E.V[L.key].noValue || 'No data'))}<small>${nod}</small></div>` : ''}${reliable(E, L, e)}</div>`;
  }
  function symbols(E, L, e, small, ring) {   // ring: drawn as hollow rings, over a shaded layer (economy.js)
    const s = E.symbols(L, e, small), neg = s.sign;
    const circ = [1, .5, .1].map(f => { const r = Math.max(2.5, s.rmax * Math.sqrt(f)); const c = neg ? '#8FCAE8' : L.color; return `<span class="sz"><i style="width:${r * 2}px;height:${r * 2}px;${ring ? `box-sizing:border-box;opacity:1;background:none;border:2px solid ${c};box-shadow:0 0 0 1.5px #fff` : `background:${c}`}"></i><small>${esc(E.fmt(L, s.mx * f, true))}</small></span>`; }).join('');
    return `<div class="el-block"><div class="el-t">${esc(E.title(L, e.y))} <small>${esc(E.chip(L, e))}</small></div><div class="el-sizes" aria-label="${esc(T('Symbol sizes: area proportional to the value'))}">${circ}</div>${empty(E, L, e)}${neg ? `<div class="row"><span class="sw" style="background:#205D7B;border-radius:50%"></span>${esc(T('increase'))}<span class="sw" style="background:#B82415;border-radius:50%;margin-left:10px"></span>${esc(T('decrease'))}</div>` : ''}${reliable(E, L, e)}</div>`;
  }
  /** The blocks of the legend for the visible layers that have values: shaded layers first (one, or two as a bivariate map), then symbols. */
  function blocks(E, layers, evals, small) {
    const vis = layers.filter(l => l.visible && evals[l.id] && evals[l.id].a), fills = vis.filter(l => l.mode === 'fill'), parts = [];
    if (fills.length >= 2) parts.push(bivariate(E, fills[0], fills[1], evals[fills[0].id], evals[fills[1].id]));
    else if (fills.length === 1) parts.push(single(E, fills[0], evals[fills[0].id]));
    vis.filter(l => l.mode === 'symbol').forEach(L => parts.push(symbols(E, L, evals[L.id], small, fills.length > 0)));
    // layers that cover different periods (a 2020–2024 survey window beside a 2025 count) are read together with care: one year control does not make them one moment (review 2026-11-05)
    const per = [...new Set(vis.map(L => time().label(E.V[L.key], evals[L.id].y)).filter(Boolean))];
    // "Match periods": the latest year that every moving layer has, offered while some layer shows another year
    const mov = vis.filter(L => !time().isFixed(E.V[L.key])), com = mov.length > 1 ? mov.map(L => E.V[L.key].ys).reduce((a, ys) => a.filter(y => ys.includes(y))) : [], cy = com.length ? Math.max(...com) : null;
    const btn = cy != null && mov.some(L => evals[L.id].y !== cy) ? ` <button type="button" class="linklike" data-ecyear="${cy}">${esc(T('Match periods: {year}', { year: cy }))}</button>` : '';
    if (per.length > 1 && parts.length) parts[parts.length - 1] += `<div class="el-note el-period" role="note">${esc(T('The layers cover different periods ({periods}): compare them with care.', { periods: per.join(', ') }))}${btn}</div>`;
    return parts;
  }

  const placesLabel = (n) => Tn(n, '{n} municipality', '{n} municipalities', { n });
  function box(title, rows, note, unit = placesLabel) {
    return `<div class="legend-box" role="group" aria-label="${esc(T('{label} legend', { label: title }))}"><div class="legend-title">${esc(title)}</div>${rows.map(r => `<div class="row"><span class="sw" style="background:${r.color}"></span>${esc(r.label)}${r.n != null ? ` <small>${esc(unit(r.n))}</small>` : ''}</div>`).join('')}<div class="note">${note}</div></div>`;
  }
  function mini(title, rows) {   // the legend drawn on the map itself: colors and words only
    return `<div class="legend-title">${esc(title)}</div>${rows.map(r => `<div class="row"><span class="sw" style="background:${r.color}"></span>${esc(r.label)}</div>`).join('')}`;
  }
  return { divLabels, blocks, box, mini, placesLabel };
});
