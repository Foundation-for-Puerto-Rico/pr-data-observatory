/* PR Data Observatory core: what a place says about the layers on the map. One component writes the pop-up of a click, the hover card and the inspector of the workbench,
   so a value, its margin of error, its rank and its trend look the same in all three (docs/engine.md, "Legend and popup").

     Popup.value(E, L, ev, i)              { txt, moe, rank, y, a } for place i under layer L (ev is the layer's evaluation: { y, a, exact, early })
     Popup.swatch(E, L)                    the little color mark in front of a layer's name
     Popup.spark(E, L, ev, i)              the trend of place i over the years, as a small line with the shown year marked
     Popup.inspect(E, layers, evals, i, compact, footer)   the table of every visible layer for place i (beside Puerto Rico and with the trend unless `compact`)
     Popup.hover(E, layers, evals, i)      the hover card: one line for each visible layer
   Texts come from the language layer; a layer's name and group are English data shown with T(). */
(function (name, root, factory) {
  const dep = (n) => (typeof module === 'object' && module.exports ? require('./' + n + '.js') : root.Core[n]);   // the other core modules, in Node or in a page
  const api = factory(root, dep);
  if (typeof module === 'object' && module.exports) module.exports = api; else { root.Core = root.Core || {}; root.Core[name] = api; }
})('popup', typeof window !== 'undefined' ? window : globalThis, function (root, dep) {
  'use strict';
  const { T, esc, num } = dep('text'), stats = dep('stats'), reliability = dep('reliability');

  const swatch = (E, L) => L.mode === 'symbol' ? `<span class="sw" style="background:${L.color};border-radius:50%"></span>` : `<span class="sw" style="background:${E.ramp(L)[3]}"></span>`;

  function rank(E, a, i, m) {   // with margins: the ranks the place could hold (stats.rankRange)
    const r = stats.rank(a, i, E.geo.pr), g = r && stats.rankRange(a, m, i, E.geo.pr);
    return !r ? '' : g && g.lo !== g.hi ? T('#{rank} of {n}, could be {lo}–{hi}', { ...r, ...g }) : T('#{rank} of {n}', r);
  }

  function value(E, L, ev, i) {
    if (!ev || !ev.a) return { txt: '—' };
    const v = E.V[L.key], m = E.moe(L, ev.y), mo = m && m[i] != null ? m[i] : null;
    return { txt: ev.a[i] == null && E.missing(L, i) || E.fmt(L, ev.a[i]), miss: ev.a[i] == null && !!E.missing(L, i), moe: mo != null ? (v.type === 'rate' ? `±${num(mo, 1)} pts` : `±${E.fmt({ ...L, norm: 'value' }, mo)}`) : '', rank: rank(E, ev.a, i, m), y: ev.y, a: ev.a, flagged: !!E.reliability(L, ev).flagged[i] };   // flagged: a wide margin of error or few counted (reliability.js)
  }

  function spark(E, L, ev, i) {
    const v = E.V[L.key]; if (v.static || v.ys.length < 2) return '';
    const pts = v.ys.filter(y => y >= 2010).map(y => { const a = E.calc(L, y); return a && a[i] != null ? [y, a[i]] : null; }).filter(Boolean); if (pts.length < 2) return '';
    const W = 84, H = 20, x0 = pts[0][0], x1 = pts[pts.length - 1][0], vs = pts.map(p => p[1]), lo = Math.min(...vs), hi = Math.max(...vs), cur = ev && ev.y;
    const X = y => (y - x0) / (x1 - x0 || 1) * (W - 4) + 2, Y = n => H - 2 - (hi === lo ? .5 : (n - lo) / (hi - lo)) * (H - 4), dot = pts.find(p => p[0] === cur);
    const span = x1 - x0 + 1, cap = pts.length < span ? T('{span} yrs, {n} values · {from}–{to}', { span, n: pts.length, from: x0, to: String(x1).slice(2) }) : T('{span} yrs · {from}–{to}', { span, from: x0, to: String(x1).slice(2) });
    return `<svg class="spark" width="${W}" height="${H}" viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(T('Trend from {from} to {to}: {n} yearly values', { from: x0, to: x1, n: pts.length }))}"><title>${esc(T('{from} to {to}', { from: x0, to: x1 }))}</title><polyline fill="none" stroke="#8C8E8E" stroke-width="1.3" points="${pts.map(p => `${X(p[0]).toFixed(1)},${Y(p[1]).toFixed(1)}`).join(' ')}"/>${dot ? `<circle cx="${X(dot[0]).toFixed(1)}" cy="${Y(dot[1]).toFixed(1)}" r="2.6" fill="#205D7B"/>` : ''}</svg><small class="sp-cap">${esc(cap)}</small>`;
  }

  /** `footer(i)` is HTML a page adds under the table for place i (the Economy tab names the largest employer group there). */
  function inspect(E, layers, evals, i, compact, footer) {
    const name = E.geo.names[i], pr = E.geo.pr;
    let anyFlag = false;
    const rows = layers.filter(l => l.visible).map(L => {
      const ev = evals[L.id], r = value(E, L, ev, i), p = value(E, L, ev, pr), v = E.V[L.key], chip = E.chip(L, ev); if (r.flagged) anyFlag = true;
      return `<tr><th scope="row">${swatch(E, L)}<button type="button" class="linklike" data-ecinfo="${esc(L.key)}">${esc(T(v.label))}</button><small>${esc(E.title(L, r.y).replace(T(v.label), '').replace(/^ · /, ''))}${chip ? ' · ' + esc(chip) : ''}</small></th><td class="num${r.flagged ? ' unrel' : ''}${r.miss ? ' miss' : ''}"><b>${esc(r.txt)}</b>${r.flagged ? `<span class="sr-only"> (${esc(reliability.lessReliable())})</span>` : ''} ${r.moe ? `<span class="moe">${esc(r.moe)}</span>` : ''}${r.rank ? `<small class="rk">${esc(r.rank)}</small>` : ''}</td>${compact ? '' : `<td class="num">${esc(p.txt)}</td><td class="sp">${spark(E, L, ev, i)}</td>`}</tr>`;
    }).join('');
    return `<div class="ec-insp"><h4>${esc(name)}</h4>${rows ? `<table class="ec-tbl"><thead><tr><th scope="col">${esc(T('Layer'))}</th><th scope="col" class="num">${esc(name)}</th>${compact ? '' : `<th scope="col" class="num">Puerto Rico</th><th scope="col">${esc(T('Trend'))}<small class="th-sub">${esc(T('years shown; dot = chosen year'))}</small></th>`}</tr></thead><tbody>${rows}</tbody></table>${anyFlag ? `<div class="note rel-note">${esc(reliability.flagKey())}</div>` : ''}` : `<div class="note">${esc(T('No visible layers. Add a dataset from Home.'))}</div>`}${footer ? footer(i) : ''}</div>`;
  }

  function hover(E, layers, evals, i) {
    const rows = layers.filter(l => l.visible).map(L => { const r = value(E, L, evals[L.id], i); return `<div class="eh-row">${swatch(E, L)}<span>${esc(T(E.V[L.key].label))}</span><b${r.flagged || r.miss ? ` class="${[r.flagged ? 'unrel' : '', r.miss ? 'miss' : ''].filter(Boolean).join(' ')}"` : ''}>${esc(r.txt)}${r.flagged ? `<span class="sr-only"> (${esc(reliability.lessReliable())})</span>` : ''}</b></div>`; }).join('');
    return `<b>${esc(E.geo.names[i])}</b>${rows}`;
  }

  return { swatch, rank, value, spark, inspect, hover };
});
