/* PR Data Observatory: the About page (about.html; docs/workspace.md). The text is the page's own; this fills what comes from the data (the counts, the
   topics, the snapshot) and runs the tutorial: one step at a time with Back, Next and Start again, or all the steps at once. Without this script the
   page still shows every step as a list. */
(function () {
  'use strict';
  const el = (id) => document.getElementById(id);
  const kpi = (v, l) => (v == null ? '' : `<div class="kpi"><div class="v">${fmt(v)}</div><div class="l">${esc(l)}</div></div>`);

  // ── The tutorial ──
  const steps = [...document.querySelectorAll('#tourSteps .tour-step')];
  let at = 0, all = false;
  function show(focus) {
    const tour = el('tour'); tour.classList.toggle('all', all);
    steps.forEach((s, i) => { s.hidden = !all && i !== at; });
    el('tourCount').textContent = all ? T('All {n} steps', { n: steps.length }) : T('Step {n} of {m}', { n: at + 1, m: steps.length });
    el('tourPrev').disabled = all || at === 0; el('tourNext').disabled = all || at === steps.length - 1;
    el('tourAll').setAttribute('aria-pressed', String(all));
    if (focus && !all) { const h = steps[at].querySelector('h3'); h.tabIndex = -1; h.focus({ preventScroll: true }); }
  }
  if (steps.length) {
    el('tourPrev').onclick = () => { at = Math.max(0, at - 1); show(true); };
    el('tourNext').onclick = () => { at = Math.min(steps.length - 1, at + 1); show(true); };
    el('tourReplay').onclick = () => { all = false; at = 0; show(true); };
    el('tourAll').onclick = () => { all = !all; show(false); };
    el('tour').addEventListener('keydown', (e) => { if (all || /^(INPUT|SELECT|TEXTAREA)$/.test(e.target.tagName)) return; if (e.key === 'ArrowRight') el('tourNext').click(); else if (e.key === 'ArrowLeft') el('tourPrev').click(); });
    show(false);
  }

  // ── What comes from the data ──
  async function fill() {
    try {
      const m = await fetchJson('data/meta.json'), c = m.counts || {}, k = (m.transport || {}).kinds || {};
      const stops = (k.transit_stop || 0) + (k.bus_stop || 0) + (k.bus_station || 0) + (k.rail_station || 0) + (k.ferry_terminal || 0);
      el('aboutKpis').innerHTML = kpi(c.municipalities || 78, T('municipalities')) + kpi(c.population_2020, T('residents (2020 Census)')) + kpi(c.tourism_places, T('tourism places')) + kpi((m.network || {}).routes, T('transit routes, all operators')) + kpi(stops, T('stops and stations'));
      const b = el('aboutBuilt'); if (b) b.innerHTML = Th('Current snapshot: <b>{label}</b>, built {date}.', { label: snapshotLabel(m.label), date: (m.generated_at || '').slice(0, 10) });
      document.querySelectorAll('.snap').forEach(e => { e.textContent = m.label ? snapshotLabel(m.label) : ''; });
    } catch (e) { /* the counts are an extra: the page reads without them */ }
    try {
      const d = await fetchJson('data/dictionary_summary.json');
      el('aboutKpis').insertAdjacentHTML('beforeend', kpi(d.entries, T('documented datasets, variables and measures')) + kpi(d.data_sources, T('data sources, each with its license')));
    } catch (e) { /* optional */ }
    try {
      const cat = await fetchJson('data/catalog.json'), box = el('aboutDomains');
      if (box) box.innerHTML = cat.domains.filter(d => !d.parent && !d.system).sort((a, b) => a.order - b.order).map(d => `<li><b>${esc(I18N.name(d))}:</b> ${esc(I18N.text(d.description))}${d.status === 'planned' ? ` <i>${esc(T('(no data yet)'))}</i>` : ''}</li>`).join('');
    } catch (e) { /* optional */ }
  }
  fill();
})();
