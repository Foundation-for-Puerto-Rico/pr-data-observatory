/* PR Data Observatory: land-use analysis. The share of each class of the Plan de Uso de Terrenos 2015 (Junta de Planificación) for Puerto Rico and for each
   municipality, from data/landuse_summary.json (landuse.py class_summary). Loaded the first time the panel opens (app.js openLanduse); it docks under the map
   like the Economy workbench. Shares are of the land in the plan: water bodies and road rights-of-way are left out, as in municipalities.json. */
const LanduseView = (() => {
  const st = { doc: null, sel: null, by: 'class', sort: 'SU', box: null };
  const GROUPS = () => [['urban', T('Urban land'), '#8C8E8E'], ['urbanizable', T('Land for urban growth'), '#FFA600'], ['rustic', T('Ordinary rural land'), '#C2D85E'], ['protected', T('Specially protected rural land'), '#79901E']];
  const PR = 'Puerto Rico';
  const pct = (x, d = 1) => fmt(x, d) + '%';
  const shell = (msg) => {   // while the data loads, or when it fails: a title and a close button, so the panel can always be left
    st.box.innerHTML = `<div class="eb-head"><h2 class="lu-title">${icon('landscape', { size: 18 })}${esc(T('Land use: Plan de Uso de Terrenos 2015'))}</h2><button type="button" class="icon-btn small" id="luClose" aria-label="${esc(T('Close the land-use analysis'))}"><span class="ms-icon" aria-hidden="true">close</span></button></div><div class="empty" role="status">${esc(msg)}</div>`;
    st.box.querySelector('#luClose').onclick = close;
  };

  function cats() {   // the bars' categories: the ten classes of the legend, or the four groups
    const c = st.doc.classes.filter(k => k.in_share);
    return st.by === 'group' ? GROUPS().map(([key, label, color]) => ({ key, label, color, members: c.filter(k => k.group === key).map(k => k.key) }))
      : c.map(k => ({ key: k.key, label: k.label, color: k.color, members: [k.key] }));
  }
  function shares(areas) {   // {category: [km², % of the land]} and the land total
    const cs = cats(), km = cs.map(c => c.members.reduce((a, k) => a + (areas[k] || 0), 0)), land = km.reduce((a, b) => a + b, 0);
    return { land, rows: cs.map((c, i) => ({ ...c, km2: km[i], pct: land ? km[i] / land * 100 : 0 })) };
  }
  const areasOf = (name) => name === PR ? st.doc.puerto_rico : st.doc.municipios[name] || {};
  const bar = (s, big) => `<div class="lu-bar${big ? ' big' : ''}" role="img" aria-label="${esc(s.rows.filter(r => r.pct >= 0.05).sort((a, b) => b.pct - a.pct).map(r => `${r.label} ${pct(r.pct)}`).join(', '))}">${s.rows.filter(r => r.pct > 0).map(r => `<span style="width:${r.pct.toFixed(3)}%;background:${r.color}" title="${esc(r.label)}: ${pct(r.pct)}"></span>`).join('')}</div>`;

  function render(box) {
    st.box = box || st.box; if (!st.box) return;
    if (!st.doc) { shell(T('Loading the land-use areas…')); return; }
    const sel = st.sel || PR, s = shares(areasOf(sel)), cs = cats();
    if (!cs.some(c => c.key === st.sort)) st.sort = cs[0].key;
    const names = Object.keys(st.doc.municipios).sort((a, b) => a.localeCompare(b, 'es'));
    const list = names.map(n => ({ n, s: shares(areasOf(n)) })).map(o => ({ ...o, v: o.s.rows.find(r => r.key === st.sort).pct })).sort((a, b) => b.v - a.v || a.n.localeCompare(b.n, 'es'));
    const sortLabel = cs.find(c => c.key === st.sort).label;
    st.box.innerHTML = `<div class="eb-head"><h2 class="lu-title">${icon('landscape', { size: 18 })}${esc(T('Land use: Plan de Uso de Terrenos 2015'))}</h2>
        <label class="lu-ctl">${esc(T('Show'))} <select id="luBy"><option value="class"${st.by === 'class' ? ' selected' : ''}>${esc(T('the ten classes'))}</option><option value="group"${st.by === 'group' ? ' selected' : ''}>${esc(T('the four groups'))}</option></select></label>
        <label class="lu-ctl">${esc(T('Area'))} <select id="luSel"><option value="${PR}">${esc(T('Puerto Rico'))}</option>${names.map(n => `<option${n === sel ? ' selected' : ''}>${esc(n)}</option>`).join('')}</select></label>
        <button type="button" class="btn small" id="luCsv">${icon('download', { size: 14 })}${esc(T('Download CSV'))}</button>
        <button type="button" class="icon-btn small" id="luClose" aria-label="${esc(T('Close the land-use analysis'))}"><span class="ms-icon" aria-hidden="true">close</span></button></div>
      <div class="eb-body lu-body">
        <section class="lu-area" aria-labelledby="luAreaH"><h3 class="sec" id="luAreaH">${esc(sel === PR ? T('Puerto Rico') : sel)} <small>${esc(T('{km2} km² of land', { km2: fmt(s.land, 1) }))}</small></h3>
          ${bar(s, true)}
          <table class="lu-tbl"><thead><tr><th scope="col">${esc(T('Class'))}</th><th scope="col" class="num">km²</th><th scope="col" class="num">${esc(T('Share of land'))}</th></tr></thead><tbody>
          ${s.rows.map(r => `<tr><th scope="row"><span class="sw" style="background:${r.color}"></span>${esc(r.label)}</th><td class="num">${fmt(r.km2, 1)}</td><td class="num">${pct(r.pct)}</td></tr>`).join('')}</tbody></table>
          ${sel === PR ? '' : `<button type="button" class="linklike" id="luMuni">${esc(T('Open the municipality profile'))}</button>`}
        </section>
        <section class="lu-munis" aria-labelledby="luMuniH"><h3 class="sec" id="luMuniH">${esc(T('All 78 municipalities'))}</h3>
          <label class="lu-ctl">${esc(T('Sort by the share of'))} <select id="luSort">${cs.map(c => `<option value="${c.key}"${c.key === st.sort ? ' selected' : ''}>${esc(c.label)}</option>`).join('')}</select></label>
          <table class="lu-tbl lu-list"><thead><tr><th scope="col">${esc(T('Municipality'))}</th><th scope="col">${esc(T('Land by class'))}</th><th scope="col" class="num">${esc(sortLabel)}</th></tr></thead><tbody>
          ${list.map(o => `<tr class="${o.n === sel ? 'on' : ''}"><th scope="row"><button type="button" class="linklike" data-lu-muni="${esc(o.n)}">${esc(o.n)}</button></th><td>${bar(o.s)}</td><td class="num">${pct(o.v)}</td></tr>`).join('')}</tbody></table>
        </section>
        <p class="note lu-note">${esc(T('The plan classifies land for planning (what may be built where); it is not a map of land cover today. Shares are of the land in the plan: water and road rights-of-way are left out. Source: Junta de Planificación, Plan de Uso de Terrenos de Puerto Rico 2015.'))}</p>
      </div>`;
    const $$ = (id) => st.box.querySelector('#' + id);
    $$('luClose').onclick = close;
    $$('luBy').onchange = e => { st.by = e.target.value; render(); };
    $$('luSort').onchange = e => { st.sort = e.target.value; render(); };
    $$('luSel').onchange = e => pick(e.target.value === PR ? null : e.target.value);
    $$('luCsv').onclick = () => downloadCsv([PR, ...names].map(n => { const x = shares(areasOf(n)); return Object.assign({ area: n, land_km2: +x.land.toFixed(3) }, ...x.rows.map(r => ({ [`${r.key}_km2`]: +r.km2.toFixed(3), [`${r.key}_pct`]: +r.pct.toFixed(2) }))); }), `land_use_${st.by === 'group' ? 'groups' : 'classes'}_put2015.csv`);
    if ($$('luMuni')) $$('luMuni').onclick = () => selectMuni(sel);
    st.box.querySelector('.lu-list').onclick = e => { const b = e.target.closest('[data-lu-muni]'); if (b) pick(b.dataset.luMuni); };
  }
  function pick(name) {
    st.sel = name; render();
    const f = name && S.muniFc && S.muniFc.features.find(x => x.properties.municipality === name);
    if (f) map.fitBounds(L.geoJSON(f).getBounds(), { padding: [20, 20], maxZoom: 12 });
  }
  function open(box) {
    st.box = box; box.hidden = false; document.body.classList.add('bench-open'); setTimeout(() => map.invalidateSize(), 60);
    render();
    if (!st.doc) getJson('data/landuse_summary.json', T('land-use areas')).then(d => { st.doc = d; render(); }, () => shell(T('The land-use areas could not be loaded. Check your connection and open the analysis again.')));
  }
  function close() {
    if (!st.box || st.box.hidden) return;
    st.box.hidden = true; if (!(typeof EC !== 'undefined' && EC.bench && EC.bench.open)) document.body.classList.remove('bench-open'); setTimeout(() => map.invalidateSize(), 60);
  }
  return { open, close, render, shares: (areas, by = 'class') => { const b = st.by; st.by = by; const r = shares(areas); st.by = b; return r; }, setDoc: d => { st.doc = d; } };
})();
