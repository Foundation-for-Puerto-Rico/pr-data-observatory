/* PR Data Observatory core: the panel of a layer stack. The card of one layer (show, hide, move, remove, settings) and the list of datasets that can be added. Both return markup;
   the page owns the buttons' behavior (the attributes data-act, data-f, data-add and data-key say what each one does). docs/engine.md, "Legend and popup". */
(function (name, root, factory) {
  const dep = (n) => (typeof module === 'object' && module.exports ? require('./' + n + '.js') : root.Core[n]);   // the other core modules, in Node or in a page
  const api = factory(root, dep);
  if (typeof module === 'object' && module.exports) module.exports = api; else { root.Core = root.Core || {}; root.Core[name] = api; }
})('panel', typeof window !== 'undefined' ? window : globalThis, function (root, dep) {
  'use strict';
  const { T, esc } = dep('text'), palettes = dep('palettes'), norm = dep('normalize'), classify = dep('classify');
  const plain = (s) => (s || '').normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase().trim();

  /** The field for a layer's own class limits: four numbers in rising order. */
  function limits(L) {
    const ok = !!classify.parseBreaks(L.breaks, 5);
    return `<label class="wide">${esc(T('Class limits'))}<input type="text" data-f="breaks" value="${esc(L.breaks || '')}" inputmode="text" placeholder="10, 20, 30, 40" aria-describedby="brk${L.id}"${ok ? '' : ' aria-invalid="true"'}></label><div class="note wide" id="brk${L.id}">${esc(ok ? T('Four limits between five classes; a value on a limit goes in the lower class. A scale around a center (index, difference, change) keeps its own cut-offs, and two shaded layers together use three classes each.') : T('Type four numbers in rising order, for example 10, 20, 30, 40. Until then the classes are quantiles.'))}</div>`;
  }

  /** The card of layer L, which is number k of n in the stack; `ev` is its evaluation. `on(key, mode)` says whether L's dataset is on the map as shading ('fill') or
      symbols ('symbol'), as in the dataset list: the card's Shaded and Symbol switches show it; `full` is true when two layers are shaded already (no third). */
  function layerCard(E, L, k, n, ev, on = (key, m) => L.mode === m, full = false) {
    const v = E.V[L.key], e = ev || {}, opts = norm.options(v);
    const names = { blue: T('Blue'), green: T('Green'), gold: T('Gold'), red: T('Red'), gray: T('Gray'), teal: T('Teal'), purple: T('Purple'), sunset: T('Sunset: yellow to purple'), pinkteal: T('Pink to turquoise'), yelblue: T('Yellow to blue') }, colours = { '#B82415': T('Red'), '#205D7B': T('Blue'), '#B56D00': T('Gold'), '#47560F': T('Green'), '#2A2E2E': T('Charcoal') };
    return `<div class="ec-layer ${L.visible ? '' : 'off'}" data-id="${L.id}"><div class="ec-lh"><label class="ec-vis" title="${esc(T('Show'))}"><input type="checkbox" data-act="vis"${L.visible ? ' checked' : ''} aria-label="${esc(T('Show {name}', { name: T(v.label) }))}"></label>
      <div class="ec-lt"><b>${esc(T(v.label))}</b><small>${esc(L.mode === 'fill' ? T('Shaded') : T('Symbols'))} · ${esc(E.title(L, e.y).replace(T(v.label), '').replace(/^ · /, '') || T('as published'))} · ${esc(E.chip(L, e))}</small></div>
      <button type="button" class="icon-btn small" data-act="up" aria-label="${esc(T('Move up'))}" title="${esc(T('Move up'))}" ${k === 0 ? 'disabled' : ''}><span class="ms-icon" aria-hidden="true">arrow_upward</span></button><button type="button" class="icon-btn small" data-act="down" aria-label="${esc(T('Move down'))}" title="${esc(T('Move down'))}" ${k === n - 1 ? 'disabled' : ''}><span class="ms-icon" aria-hidden="true">arrow_downward</span></button>
      <button type="button" class="icon-btn small" data-act="info" aria-label="${esc(T('Sources and definition of {name}', { name: T(v.label) }))}" title="${esc(T('Sources and definition'))}"><span class="ms-icon" aria-hidden="true">info</span></button><button type="button" class="icon-btn small" data-act="del" aria-label="${esc(T('Remove {name}', { name: T(v.label) }))}" title="${esc(T('Remove'))}"><span class="ms-icon" aria-hidden="true">close</span></button></div>
      <div class="ec-modes" role="group" aria-label="${esc(T('{name} on the map', { name: T(v.label) }))}">${[['fill', T('Shaded'), on(L.key, 'fill') ? T('Turn the shading off') : full ? T('A map can shade two datasets together (a bivariate map). Remove one shaded layer first, or show this one as symbols.') : T('Shade the map by this dataset')], ['symbol', T('Symbol'), on(L.key, 'symbol') ? T('Turn the symbols off') : T('Show as sized symbols')]].map(([m, label, tip]) => `<button type="button" class="ec-mode ${m}" data-act="mode" data-mode="${m}" aria-pressed="${on(L.key, m)}" title="${esc(tip)}">${esc(label)}</button>`).join('')}</div>
      <details class="ec-set"><summary>${esc(T('Settings'))}</summary><div class="ec-grid">
        ${L.mode === 'fill' && L.levels ? `<label>${esc(T('Area'))}<select data-f="level"><option value="">${esc(T('Municipalities'))}</option><option value="barrio"${L.level === 'barrio' ? ' selected' : ''}>${esc(T('Barrios'))}</option></select></label>` : ''}
        <label>${esc(T('Show as'))}<select data-f="norm">${opts.map(o => `<option value="${o[0]}"${o[0] === L.norm ? ' selected' : ''}>${esc(T(o[1]))}</option>`).join('')}</select></label>
        ${L.mode === 'fill' ? `<label>${esc(T('Classes'))}<select data-f="classes"><option value="quantile"${L.classes === 'quantile' ? ' selected' : ''}>${esc(T('Quantiles (equal counts)'))}</option><option value="equal"${L.classes === 'equal' ? ' selected' : ''}>${esc(T('Equal intervals'))}</option><option value="jenks"${L.classes === 'jenks' ? ' selected' : ''}>${esc(T('Natural breaks'))}</option><option value="manual"${L.classes === 'manual' ? ' selected' : ''}>${esc(T('My own limits'))}</option></select></label><label>${esc(T('Colors'))}<select data-f="ramp">${(palettes.RAMP_MENU || palettes.RAMP_ORDER).map(r => `<option value="${r}"${L.ramp === r ? ' selected' : ''}>${esc(names[r])}</option>`).join('')}</select></label>${L.classes === 'manual' ? limits(L) : ''}` : `<label>${esc(T('Color'))}<select data-f="color">${palettes.SYMBOLS.map(c => `<option value="${c}"${L.color === c ? ' selected' : ''}>${esc(colours[c])}</option>`).join('')}</select></label>`}
        <label>${esc(T('Opacity'))}<input type="range" data-f="opacity" min="0.2" max="1" step="0.05" value="${L.opacity}"></label>
        ${v.static ? '' : `<label class="chk"><input type="checkbox" data-f="fixed" ${L.fixed ? 'checked' : ''}> ${esc(T('Same classes in every year'))}</label>`}
        ${v.unit === '$' && E.cpiRef ? `<label class="chk"><input type="checkbox" data-f="real" ${L.real ? 'checked' : ''}> ${esc(T('Inflation-adjusted ({year} dollars)', { year: E.cpiRef }))}</label>` : ''}
      </div></details></div>`;
  }

  /** The datasets that match the search text `q`, grouped, as <details> blocks; the groups in `order` come first. `on(key, mode)` says whether
      that dataset is on the map as shading ('fill') or symbols ('symbol'): each is a checkbox, so a dataset can be shaded, symbols, both or neither. Returns { html, n }. */
  function browse(E, q, order, openGroup, on = () => false) {
    const query = plain(q), groups = {};
    E.list().forEach(v => { if (query && !plain(`${T(v.label)} ${T(v.group)} ${v.ref} ${v.definition}`).includes(query)) return; (groups[v.group] = groups[v.group] || []).push(v); });
    let n = 0;
    const html = [...order.filter(g => groups[g]), ...Object.keys(groups).filter(g => !order.includes(g))].map(g => `<details class="ec-grp" ${query || g === openGroup ? 'open' : ''}><summary>${esc(T(g))} <small>${groups[g].length}</small></summary>${groups[g].map(v => { n++; const yrs = v.static ? T('snapshot {year}', { year: v.ys[0] }) : v.ys.length > 1 ? `${v.ys[0]}–${v.ys[v.ys.length - 1]}` : `${v.ys[0]}`; return `<div class="ec-ds" data-key="${esc(v.key)}"><div class="ec-dn"><span>${esc(T(v.label))}</span><small>${esc(yrs)}${v.moe ? ' · ' + esc(T('± margins')) : ''}</small></div><div class="ec-da"><label class="ec-pick fill" title="${esc(T('Shade the map by this dataset'))}"><input type="checkbox" data-add="fill"${on(v.key, 'fill') ? ' checked' : ''} aria-label="${esc(T('Shade the map by {name}', { name: T(v.label) }))}">${esc(T('Shade'))}</label><label class="ec-pick sym" title="${esc(T('Show as sized symbols'))}"><input type="checkbox" data-add="symbol"${on(v.key, 'symbol') ? ' checked' : ''} aria-label="${esc(T('Show {name} as symbols', { name: T(v.label) }))}">${esc(T('Symbols'))}</label><button type="button" class="icon-btn small" data-act="info" aria-label="${esc(T('Sources and definition of {name}', { name: T(v.label) }))}" title="${esc(T('Sources and definition'))}"><span class="ms-icon" aria-hidden="true">info</span></button></div></div>`; }).join('')}</details>`).join('') || `<div class="empty">${esc(T('No dataset matches.'))}</div>`;
    return { html, n };
  }

  return { layerCard, browse };
});
