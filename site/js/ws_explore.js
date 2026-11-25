/* PR Data Observatory: Map Gallery (explore.html; docs/workspace.md). A way in: ready-made views, the topics, the maps saved in this browser,
   and every topic page and tool. Nothing here is a list kept by hand: the views come from data/catalog_views.json, the topics from data/catalog.json
   (both written by catalog.py) and the Knowledge pages from js/knowledge_items.js (written by knowledge.py), so a new one appears on its own. */
(function () {
  'use strict';
  const el = (id) => document.getElementById(id);
  const icon = (n) => `<span class="ms-icon" aria-hidden="true">${esc(n)}</span>`;
  const read = (k, d) => { try { const v = localStorage.getItem(k); return v == null ? d : JSON.parse(v); } catch (e) { return d; } };
  const tile = (href, ic, tint, title, text) => `<a class="ws-tile" href="${esc(href)}"><span class="ws-tile-ic ws-tint-${tint}">${icon(ic)}</span><span><b>${esc(title)}</b><i>${esc(text)}</i></span></a>`;
  const TINT = { '--fpr-blue': 'blue', '--fpr-green': 'green', '--fpr-yellow': 'yellow', '--fpr-red': 'red' };
  /** The address of the map with a ready-made view on it: its datasets in the engine's own link form (e=key.f for shaded, key.s for symbols) and its layers (l=). */
  const viewHref = (v) => 'index.html#' + [v.show.length ? 'e=' + encodeURIComponent(v.show.map(([key, mode]) => key + '.' + (mode === 'symbol' ? 's' : 'f')).join(',')) : '', (v.on || []).length ? 'l=' + v.on.join(',') : ''].filter(Boolean).join('&');

  function saved() {
    const all = read('twin.maps', {}), names = Object.keys(all).sort((a, b) => String(all[b].saved).localeCompare(String(all[a].saved))), last = read('twin.ws.last', '');
    const ok = (h) => typeof h === 'string' && /^#[\w\-.,~%=&:+ ]*$/.test(h);
    el('exSaved').innerHTML = (ok(last) && last.length > 1 ? `<div class="ws-tiles">${tile('index.html' + last, 'history', 'blue', T('Continue where you left off'), T('The map as you last had it in this browser.'))}</div>` : '')
      + (names.length ? `<div class="ws-tiles">${names.filter(n => ok(all[n].hash)).map(n => tile('index.html' + all[n].hash, 'map', 'green', n, I18N.date(new Date(all[n].saved), { dateStyle: 'medium' }))).join('')}</div>`
        : `<p class="ws-muted">${esc(T('None yet. Save a map from the Map area and it appears here. Saved maps stay in this browser.'))}</p>`);
  }
  function pages() {
    const K = window.KNOWLEDGE || { items: [], kinds: {} };
    const fixed = [
      ['index.html', 'map', T('The map'), T('Every layer and tool, with the timeline')],
      ['3d.html', 'view_in_ar', T('3D + Time'), T('Terrain and buildings, a day of transit, storms and sea level by year')],
      ['profile.html', 'place', T('Area profiles'), T('One page for a municipio or a region')],
      ['dictionary.html', 'menu_book', T('Data dictionary'), T('Meanings, sources, licenses and how to cite')],
      ['data-management.html', 'inventory_2', T('Data management'), T('Every published file, its size, license and review')],
      ['learn.html', 'school', T('Learn'), T('Short lessons that use the map')],
      ['knowledge.html', 'lightbulb', T('All Knowledge'), T('FPR studies, analyses and program tools')],
    ];
    el('exPages').innerHTML = `<div class="ws-tiles small">${fixed.map(p => tile(p[0], p[1], 'blue', p[2], p[3])).join('')}${(K.items || []).map(it => tile(it.page, it.icon || 'lightbulb', 'yellow', I18N.text(it.title), I18N.text(K.kinds[it.kind]))).join('')}</div>`;
  }
  async function start() {
    saved(); pages();
    let cat = null, views = null;
    try { [cat, views] = await Promise.all([fetchJson('data/catalog.json'), fetchJson('data/catalog_views.json').catch(() => ({ presets: {} }))]); }
    catch (e) { el('exTopics').innerHTML = el('exViews').innerHTML = `<p class="ws-muted" role="alert">${esc(T('The list could not be loaded. Check your connection.'))} <button type="button" class="linklike" id="exRetry">${esc(T('Try again'))}</button></p>`; el('exRetry').onclick = start; return; }
    const doms = cat.domains.filter(d => !d.system).sort((a, b) => a.order - b.order), top = doms.filter(d => !d.parent), name = (d) => I18N.name(d), byId = Object.fromEntries(cat.domains.map(d => [d.id, d]));
    // ready-made views: a whole map from one click
    const vs = doms.flatMap(d => ((views.presets || {})[d.id] || []).map(v => ({ v, d })));
    el('exViews').innerHTML = vs.length ? `<div class="ws-tiles big">${vs.map(({ v, d }) => tile(viewHref(v), (byId[d.parent] || d).icon || d.icon, TINT[(byId[d.parent] || d).accent] || 'blue', I18N.text(v.name), I18N.text(v.note))).join('')}</div>` : `<p class="ws-muted">${esc(T('No ready-made views yet.'))}</p>`;
    // the topics, with what each holds
    el('exTopics').innerHTML = `<div class="ws-tiles big">${top.map(d => `<div class="ws-tile topic"><span class="ws-tile-ic ws-tint-${TINT[d.accent] || 'blue'}">${icon(d.icon)}</span><span><b>${esc(name(d))}</b><i>${esc(I18N.text(d.description))}</i>
      <span class="ws-links"><a href="index.html#topic=${encodeURIComponent(d.id)}">${esc(T('Open on the map'))}</a><a href="data.html#domain=${encodeURIComponent(d.id)}">${esc(Tn(d.entries, 'Browse {n} dataset', 'Browse {n} datasets'))}</a></span></span></div>`).join('')}</div>`;
    el('exCount').textContent = T('{n} topics. {snapshot}.', { n: top.length, snapshot: snapshotLabel(cat.snapshot) });
  }
  window.addEventListener('storage', saved);
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start); else start();
})();
