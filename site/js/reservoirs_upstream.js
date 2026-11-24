/* Reservoirs page, section 4 "What drains into each reservoir" (HANDOFF decision 107, step 9, fourth part; docs/upstream.md).
   Reads data/upstream.json (upstream.py) and draws two sortable tables: the reservoirs and the river gauges, each with the land that drains to it and the
   residents, buildings, wastewater treatment plants and protected land on that land, beside USGS's own drainage area (the check). */
(function (root) {
  'use strict';
  const doc = root.document, $ = (s) => doc.querySelector(s);
  const loc = () => (root.I18N && I18N.lang === 'es' ? 'es-PR' : 'en-US');
  const fmt = (v, d = 0) => v == null || !isFinite(v) ? '—' : Number(v).toLocaleString(loc(), { minimumFractionDigits: d, maximumFractionDigits: d });
  const COLS = [['name', 'Reservoir', ''], ['km2', 'Land that drains to it (km²)', 'num'], ['usgs_km2', "USGS's drainage area (km²)", 'num'], ['residents', 'Residents', 'num'],
                ['buildings', 'Buildings', 'num'], ['wastewater_plants', 'Wastewater treatment plants', 'num'], ['protected_pct', 'Protected land (%)', 'num']];
  const S = { reservoir: ['residents', -1], gauge: ['residents', -1] };
  let D;

  // loaded on first use by the page's own loader (reservoirs.html), after its Spanish module 'upstream'
  if (doc && $('#rvUpBox')) {
    const note = (lead, body, cls = '') => `<div class="note${cls}"><b>${esc(T(lead))}</b> ${esc(T(body))}</div>`;
    $('#rvUpBox').innerHTML = `<p class="pm-p">${esc(T("The land whose rain runs into each reservoir and past each river gauge, and what is on it: residents, buildings, wastewater treatment plants and protected land. The land comes from the US Geological Survey's map of small catchments linked downstream, the same one as the map's tool What drains here. Select a column heading to sort; hold the pointer on a number of plants to read their names."))}</p>
      <p class="pm-p" id="rvUpRead"></p><div class="card pm-tablebox rv-tablebox" id="rvUp"></div>
      <details class="rv-up-more"><summary>${esc(T('The river gauges'))}</summary><div class="card pm-tablebox rv-tablebox" id="rvUpG"></div></details>
      ${note('Read the figures upstream with care.', 'A count on the land upstream says what is there, not what reaches the water: a wastewater plant may discharge below the reservoir, and most homes are not on a sewer. In the northern karst water also moves underground, so the land that drains on the surface is not all the water that arrives. Some reservoirs also receive water piped or channelled from another basin, and six are off the stream, fed by canals or pumps: for those the page gives no figures.', ' caution')}`;
    if ($('#rvUpMethod')) $('#rvUpMethod').innerHTML = note('What drains into it.', "Each reservoir and gauge is placed on the catchment of its own stream: within 300 m, the catchment whose stream bears its name and drains the most land; else, within 150 m, the one that drains the most land. Its land is that catchment and every catchment upstream of it. A split in a river is followed only when both branches reach the same mouth, and river mouths are not linked along the coast. Residents and housing units are the 2020 census blocks whose point is on that land; buildings, the footprints of the map's building layer; wastewater plants, EPA's publicly owned treatment works whose permit is in force; protected land, the areas of PAD-US. The check is USGS's own drainage area for each site; the sites more than a quarter apart are marked. The method and the check are in docs/upstream.md of the project repository.");
    if ($('#rvUpSource')) $('#rvUpSource').innerHTML = note('What drains into each reservoir.', "USGS NHDPlus High Resolution catchments and USGS's drainage areas (NWIS site service); EPA Facility Registry Service, publicly owned treatment works; USGS PAD-US protected areas; US Census Bureau 2020 blocks; Overture Maps buildings (ODbL). The data file is data/upstream.json (upstream.py).");
    fetchJson('data/upstream.json').then((d) => { D = d; draw('reservoir', '#rvUp'); draw('gauge', '#rvUpG'); summary(); }, (e) => {
      $('#rvUp').innerHTML = `<p class="pm-p">${esc(T('The data could not be loaded ({error}). Check your connection and reload.', { error: e.message }))}</p>`;
    });
  }

  function check(r) {
    if (r.usgs_km2 == null) return `<span class="rv-up-flag" title="${esc(T('USGS publishes no drainage area for this site, so the land found here is not checked.'))}">${esc(T('not checked'))}</span>`;
    const d = Math.round((r.km2 / r.usgs_km2 - 1) * 100);
    return r.agrees ? fmt(r.usgs_km2, 1) : `${fmt(r.usgs_km2, 1)} <span class="rv-up-flag" title="${esc(T('The land found here differs from USGS\'s drainage area by more than a quarter.'))}">${esc(T('{d}% apart', { d: (d > 0 ? '+' : '−') + Math.abs(d) }))}</span>`;
  }

  function draw(kind, sel) {
    const [k, dir] = S[kind], rows = D.sites.filter(r => r.kind === kind);
    const val = (r) => k === 'name' ? r.name : r[k];
    rows.sort((a, b) => { const p = val(a), q = val(b); return (p == null) - (q == null) || (typeof p === 'string' ? p.localeCompare(q, loc()) : p - q) * dir; });
    const head = COLS.map(([c, l, cls]) => `<th scope="col" class="${cls}" aria-sort="${c === k ? (dir > 0 ? 'ascending' : 'descending') : 'none'}"><button type="button" data-sort="${c}">${esc(T(kind === 'gauge' && c === 'name' ? 'River gauge' : l))}</button></th>`).join('');
    const body = rows.map(r => {
      const name = `<th scope="row"><b>${esc(r.name)}</b><small>${esc(r.municipio || '')}${r.aaa ? ' · AAA' : ''}</small></th>`;
      if (r.withheld) return `<tr>${name}<td colspan="${COLS.length - 1}" class="rv-up-off">${esc(T('Off the stream, fed by a canal or pumps: the stream network cannot say what drains into it, and USGS publishes no drainage area.'))}</td></tr>`;
      const plants = r.wastewater_plants ? `<span title="${esc(r.plant_names.join('; '))}">${fmt(r.wastewater_plants)}</span>` : '0';
      return `<tr>${name}<td class="num">${fmt(r.km2, 1)}</td><td class="num">${check(r)}</td><td class="num">${fmt(r.residents)}</td><td class="num">${fmt(r.buildings)}</td><td class="num">${plants}</td><td class="num">${fmt(r.protected_pct, 1)}</td></tr>`;
    }).join('');
    const cap = kind === 'gauge' ? T('What lies upstream of each river gauge') : T('What lies upstream of each reservoir');
    $(sel).innerHTML = `<table class="pm-table rv-table rv-up-table"><caption class="sr-only">${esc(cap)}</caption><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table>`;
    $(sel).querySelectorAll('button[data-sort]').forEach(b => b.onclick = () => { const c = b.dataset.sort; S[kind] = [c, S[kind][0] === c ? -S[kind][1] : (c === 'name' ? 1 : -1)]; draw(kind, sel); });
  }

  function summary() {
    const c = D.notes.check, res = D.sites.filter(r => r.kind === 'reservoir' && !r.withheld);
    const most = res.slice().sort((a, b) => b.residents - a.residents)[0];
    const plants = res.filter(r => r.wastewater_plants > 0).length;
    $('#rvUpRead').textContent = T('{most} has the most people upstream: {n} residents on {km} km². {p} of the {r} reservoirs on a stream have a wastewater treatment plant upstream. The land found here is within a quarter of USGS\'s own drainage area for {w} of the {u} sites USGS gives one.',
      { most: most.name, n: fmt(most.residents), km: fmt(most.km2, 0), p: plants, r: res.length, w: c.within, u: c.with_a_usgs_area });
  }
})(typeof window !== 'undefined' ? window : globalThis);
