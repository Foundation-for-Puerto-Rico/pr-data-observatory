/* PR Data Observatory core: legends shared by every page. One component writes the legends of the observatory, so a class has the same colour, the same wording and the same count wherever it is
   drawn (docs/engine.md, "Legend and popup"). The markup has several variants because the places that show a legend are laid out differently; the content does not differ.

     Legend.counts(breaks, values, k)       how many values fall in each class (the island is not among `values`)
     Legend.inline(items, note)             one line of colour chips with a note (the maps of the Housing page)
     Legend.swatches(colors, labels, note)  a strip of colours with labels below it (the columns of the 3D view)
   A row is { color, label, n }. The legends that only the map page draws are in stack.js. */
(function (name, root, factory) {
  const dep = (n) => (typeof module === 'object' && module.exports ? require('./' + n + '.js') : root.Core[n]);   // the other core modules, in Node or in a page
  const api = factory(root, dep);
  if (typeof module === 'object' && module.exports) module.exports = api; else { root.Core = root.Core || {}; root.Core[name] = api; }
})('legend', typeof window !== 'undefined' ? window : globalThis, function (root, dep) {
  'use strict';
  const { T, esc } = dep('text'), classify = dep('classify');

  const counts = (b, vals, k = 5) => { const n = new Array(k).fill(0); vals.forEach(x => { const c = classify.classOf(b, x, k); if (c >= 0) n[c]++; }); return n; };

  // ── the other places a legend is drawn ───────────────────────────────────
  function inline(items, note) {
    return `<div class="legend-row" role="group" aria-label="${esc(T('Map legend'))}">${items.map(i => `<span class="lg"><i style="background:${i.color}"></i>${esc(i.label)} <small>${i.n}</small></span>`).join('')}</div><div class="legend-note-sm">${esc(note)}</div>`;
  }
  function swatches(colors, labels, note) {
    return `<div class="legend-swatches">${colors.map(c => `<span style="background:${c}"></span>`).join('')}</div><div class="ramp-labels">${labels.map(l => `<span>${l}</span>`).join('')}</div><div class="note">${esc(note)}</div>`;
  }

  return { counts, inline, swatches };
});
