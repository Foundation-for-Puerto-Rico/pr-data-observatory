/* PR Data Observatory core: what an area page's header loads after the page is ready (Knowledge plan, decision 90, PR 2; docs/knowledge-areas.md):
   the "All areas" menu's panel and the page's foot (its related areas and the published datasets it uses). core/knowledge.js loads it right after
   js/knowledge_items.js (window.KNOWLEDGE: titles and dataset names), so neither weighs on the first load. */
(function (root, factory) {
  const node = typeof module === 'object' && module.exports;
  const K = node ? require('./knowledge.js') : root.Core && root.Core.knowledge;
  const api = factory(root, K);
  if (node) module.exports = api;
  else if (K) { K.more = api; api.draw(root.document); }
})(typeof window !== 'undefined' ? window : globalThis, function (root, K) {
  'use strict';
  const fill = (s, v) => String(s).replace(/\{(\w+)\}/g, (m, k) => v && k in v ? v[k] : m);
  const T = (s, v) => root.T ? root.T(s, v) : fill(s, v);
  const esc = (s) => String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  const lang = () => root.I18N ? root.I18N.lang : 'en';
  const named = (o, l) => (o && (o[l] || o.en)) || '';
  const KN = () => root.KNOWLEDGE || { datasets: {}, items: [] };
  const item = (id) => KN().items.find(i => i.id === id) || {};
  const top = (a) => String(a.domain || '').split('.')[0];

  /** The menu's panel: every area that is not hidden, grouped by the top domain of its home domain, the page's own area current, then the home page. */
  function menu(current, opts = {}) {
    const areas = opts.areas || K.AREAS, l = opts.lang || lang(), doms = opts.domains || K.DOMAINS, groups = new Map();
    K.visible(areas).forEach(a => { const g = top(a); if (!groups.has(g)) groups.set(g, []); groups.get(g).push(a); });
    let html = '';
    for (const [g, list] of groups) {
      html += `<div class="ka-menu-group"><b>${esc(named(doms[g], l) || g)}</b>` + list.map(a =>
        `<a href="${esc(a.page)}"${a.id === current ? ' aria-current="page"' : ''}><span class="ms-icon" aria-hidden="true">${esc(a.icon)}</span>${esc(K.label(a, l))}${K.marked(a) ? `<span class="ka-mark">${esc(T('In review'))}</span>` : ''}</a>`).join('') + '</div>';
    }
    return html + `<a class="ka-menu-all" href="knowledge.html">${esc(T('All of Knowledge, with search'))}</a>`;
  }
  /** Fills an opened menu's panel, once. */
  function fillMenu(d) {
    const p = d && d.querySelector('.ka-menu-panel');
    if (p && !p.children.length) p.innerHTML = menu(d.getAttribute('data-ka-menu'));
  }

  /** The foot's HTML for area `current`; '' for an area that is not published or has nothing to list. opts (tests): lang, areas, datasets, titles, related, datasetIds. */
  function foot(current, opts = {}) {
    const areas = opts.areas || K.AREAS, l = opts.lang || lang(), a = K.find(current, areas), ds = opts.datasets || KN().datasets;
    if (!a || a.status !== 'published') return '';
    const it = item(a.id), rel = (opts.related || it.related || []).map(r => K.find(r, areas)).filter(r => r && r.status === 'published');
    const data = (opts.datasetIds || it.datasets || []).map(d => named(ds[d], l)).filter(Boolean);
    if (!rel.length && !data.length) return '';
    const title = (r) => named((opts.titles || {})[r.id] || item(r.id).title, l) || K.label(r, l);
    return `<section class="block ka-foot" id="kaFoot" data-t="skip"><h2><span class="ms-icon" aria-hidden="true">lightbulb</span>${esc(T('Related and data'))}</h2>` +
      (rel.length ? `<p class="ka-foot-h">${esc(T('Related'))}</p><ul class="ka-foot-list">${rel.map(r => `<li><a href="${esc(r.page)}"><span class="ms-icon" aria-hidden="true">${esc(r.icon)}</span>${esc(title(r))}</a></li>`).join('')}</ul>` : '') +
      (data.length ? `<p class="ka-foot-h">${esc(T('Data used on this page'))}</p><ul class="ka-foot-list">${data.map(t => `<li>${esc(t)}</li>`).join('')}</ul>` : '') +
      `<p class="ka-foot-links"><a href="data-management.html">${esc(T('All published files, with their sources and licenses'))}</a>${it.cite ? `<a href="${esc(it.cite)}">${esc(T('How to cite this page'))}</a>` : ''}</p></section>`;
  }

  /** Puts the foot at the end of main.page (once) and fills any menu already open. */
  function draw(doc) {
    if (!doc || !doc.querySelector) return;
    doc.querySelectorAll('details.ka-menu[open]').forEach(fillMenu);
    const bar = doc.querySelector('.ka-tabs[data-ka]'), page = doc.querySelector('main.page');
    if (!bar || !page || doc.getElementById('kaFoot')) return;
    const html = foot(bar.getAttribute('data-ka'));
    if (!html) return;
    page.insertAdjacentHTML('beforeend', html);
    if (root.I18N && root.I18N.apply) root.I18N.apply(page.lastElementChild);
  }

  return { menu, fill: fillMenu, foot, draw };
});
