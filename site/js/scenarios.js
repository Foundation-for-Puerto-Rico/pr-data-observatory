/* PR Data Observatory: the scenario workspace, the workbench's "Scenarios" view (plan item 15, section F; docs/scenarios.md). Loaded the first time the view opens.
   A scenario keeps what the map showed (its link: layers, year, composite, planned route), the figures it produced (the planned route's measures, Puerto Rico's value of each
   visible layer) and any model outputs loaded with it. Scenarios stay in this browser (IndexedDB) unless the person exports one to a file; nothing is sent anywhere.
   Uses the Economy tab's engine (E, EC, ecAdd, ecRender, ecBenchOpen, ecSaveCsv) and Core.scenario. Text goes through T / Tn / Th. */
const Scenarios = (() => {
  const DB = 'pr-twin-scenarios', STORE = 'scenarios', S_ = Core.scenario;
  let mem = null;   // when the browser keeps no IndexedDB (a private window), the scenarios of this visit only
  const st = { a: '', b: '', msg: '', err: [], models: [], persistent: true };

  // ── storage ────────────────────────────────────────────────────────────
  function open() {
    return new Promise((ok, fail) => {
      if (typeof indexedDB === 'undefined') return fail(new Error('no IndexedDB'));
      const r = indexedDB.open(DB, 1);
      r.onupgradeneeded = () => r.result.createObjectStore(STORE, { keyPath: 'id' });
      r.onsuccess = () => ok(r.result); r.onerror = () => fail(r.error);
    });
  }
  async function run(mode, fn) {
    const d = await open();
    return new Promise((ok, fail) => { const t = d.transaction(STORE, mode), req = fn(t.objectStore(STORE)); t.oncomplete = () => ok(req && req.result); t.onerror = () => fail(t.error); });
  }
  async function list() {   // the stored scenarios that pass the checks, newest first; one that fails (saved before a check was added) is left out, not allowed to hide the rest
    let all; try { all = (await run('readonly', s => s.getAll())) || []; } catch { st.persistent = false; all = (mem = mem || []).slice(); }
    return all.filter(x => !S_.check(x, EC.PR + 1).length).sort((p, q) => String(q.created).localeCompare(String(p.created)));
  }
  async function save(sc) { try { await run('readwrite', s => s.put(sc)); } catch { st.persistent = false; mem = (mem || []).filter(x => x.id !== sc.id).concat(sc); } }
  async function remove(id) { try { await run('readwrite', s => s.delete(id)); } catch { mem = (mem || []).filter(x => x.id !== id); } }
  async function get(id) { return (await list()).find(x => x.id === id) || null; }

  // ── model outputs as datasets of the engine ────────────────────────────
  const NOT_OBSERVED = 'Model output (not observed data)';
  const keyOf = (h, v) => 'model_' + [...`${h.model_name}|${h.model_version}|${h.run_id}|${v}`].reduce((a, c) => (a * 31 + c.charCodeAt(0)) >>> 0, 7).toString(36);   // the same file gives the same key, so a saved link finds it again
  function register(m) {   // m = { header, series }: one dataset for each variable; returns their keys
    const h = m.header;
    return m.series.map(s => {
      const key = keyOf(h, s.variable), ys = Object.keys(s.years).map(Number).sort((p, q) => p - q), unit = ['%', '$'].includes(s.unit) ? s.unit : '';
      E.add({ key, group: NOT_OBSERVED, label: `${T(NOT_OBSERVED)}: ${s.variable}${unit ? '' : s.unit ? ` (${s.unit})` : ''} · ${h.model_name} ${h.model_version}`, unit, d: 2, type: 'ratio', family: 'model',
        years: s.years, ys, static: ys.length === 1, ...(ys.length === 1 ? { time: { type: 'snapshot' } } : {}), sources: [], dictId: 'measures.model_output', model: h,
        ref: T('Model output loaded in your browser: {model} {version}, run {run} of {date}', { model: h.model_name, version: h.model_version, run: h.run_id, date: h.date }),
        definition: T('{model} {version}, run {run} of {date}. Assumptions: {url}. License: {licence}. Contact: {contact}. These are the results of a model, not observed data; the observatory does not check them.', { model: h.model_name, version: h.model_version, run: h.run_id, date: h.date, url: h.assumptions_url, licence: h.licence, contact: h.contact_label })
          + (s.lower || s.upper ? ' ' + T('The file also gives a lower and an upper value for each place; the map shows the central value.') : '') });
      return key;
    });
  }
  function shade(key) { EC.layers = EC.layers.filter(l => l.mode !== 'fill'); ecAdd(key, 'fill', { classes: 'quantile' }); ecRender(); }   // the model output alone as the shaded layer, so it is read on its own; symbols stay

  // ── what a scenario keeps ──────────────────────────────────────────────
  function outputs() {
    const out = [], r = typeof Plan !== 'undefined' && Plan.result && Plan.result.score;
    if (r) {
      const add = (key, label, unit, value) => { if (value != null && isFinite(value)) out.push({ key: 'route.' + key, label, unit, value }); };
      add('length_km', T('Planned route: length'), 'km', r.length_km);
      add('residents', T('Planned route: residents within 400 m'), '', r.residents_within_400m);
      add('not_served', T('Planned route: of them, with no current stop within 400 m'), '', r.residents_not_served_today);
      add('places', T('Planned route: tourism places within 400 m'), '', r.tourism_places_within_400m);
      add('parallel', T('Planned route: % of the length near an existing route'), '%', r.share_parallel_to_existing_routes_pct);
      add('flood', T('Planned route: % of the length in a flood hazard area'), '%', r.share_in_flood_hazard_area_pct);
      add('municipios', T('Planned route: municipalities crossed'), '', (r.municipalities || []).length);
    }
    for (const L of EC.layers.filter(l => l.visible && EC.eval[l.id] && EC.eval[l.id].a)) {
      const ev = EC.eval[L.id], x = ev.a[EC.PR];
      if (x != null && isFinite(x)) out.push({ key: `layer.${L.key}.${L.norm}.${ev.y}`, label: T('{name}, Puerto Rico ({period})', { name: E.title(L, ev.y), period: E.chip(L, ev) }), unit: E.out(L).unit || '', value: x });
    }
    return out;
  }

  // ── the view ───────────────────────────────────────────────────────────
  const date = (s) => { try { return I18N.date(new Date(s), { dateStyle: 'medium', timeStyle: 'short' }); } catch { return s.slice(0, 16).replace('T', ' '); } };
  async function render(body) {
    const all = await list();
    const opt = (sel) => `<option value="">${esc(T('Choose…'))}</option>` + all.map(s => `<option value="${esc(s.id)}"${s.id === sel ? ' selected' : ''}>${esc(s.name)}</option>`).join('');
    const rows = all.map(s => `<tr><th scope="row">${esc(s.name)}<small>${esc(date(s.created))}${s.label ? ' · ' + esc(s.label) : ''}${s.models.length ? ' · ' + esc(Tn(s.models.length, '{n} model output', '{n} model outputs')) : ''}</small>${s.notes ? `<small class="sc-notes">${esc(s.notes)}</small>` : ''}</th><td class="sc-acts"><button type="button" class="btn small" data-open="${esc(s.id)}">${esc(T('Open scenario'))}</button><button type="button" class="btn small" data-export="${esc(s.id)}"><span class="ms-icon" aria-hidden="true">download</span>${esc(T('Export'))}</button><button type="button" class="icon-btn small" data-del="${esc(s.id)}" aria-label="${esc(T('Delete {name}', { name: s.name }))}"><span class="ms-icon" aria-hidden="true">delete</span></button></td></tr>`).join('');
    body.innerHTML = `<div class="sc-grid">
      <section class="sc-box" aria-labelledby="scSaveH"><h3 class="sec" id="scSaveH">${esc(T('Save this view as a scenario'))}</h3>
        <div class="note">${esc(T('A scenario keeps the map\'s layers, year, composite and planned route, the figures they give, and the model outputs on the map. It stays in this browser; export it to share it.'))}${st.persistent ? '' : ' ' + esc(T('This browser keeps no stored data here (a private window, for example): scenarios last until the page closes. Export the ones to keep.'))}</div>
        <label class="sc-f">${esc(T('Name'))} <input type="text" id="scName" maxlength="120" required></label>
        <label class="sc-f">${esc(T('Prepared by (a team or organization, not a person\'s contact)'))} <input type="text" id="scLabel" maxlength="120"></label>
        <label class="sc-f">${esc(T('Notes'))} <textarea id="scNotes" rows="2" maxlength="4000"></textarea></label>
        <div class="btn-row"><button type="button" class="btn primary" id="scSave">${esc(T('Save the scenario'))}</button><label class="btn" for="scImport">${esc(T('Import a scenario (JSON)'))}</label><input type="file" id="scImport" accept=".json,application/json" hidden></div>
      </section>
      <section class="sc-box" aria-labelledby="scModelH"><h3 class="sec" id="scModelH">${esc(T('Load a model output'))}</h3>
        <div class="ix-warn" role="note"><span class="ms-icon" aria-hidden="true">warning</span>${esc(T('A model output is the result of a model, not observed data. The observatory checks its format, not its numbers.'))}</div>
        <div class="note">${Th('A CSV or GeoJSON file in the format of the <a href="{doc}" target="_blank" rel="noopener">documentation</a>, by municipio. <a href="{sample}" download>Sample file (made-up values)</a>.', { doc: 'https://github.com/Foundation-for-Puerto-Rico/pr-data-observatory/blob/main/docs/scenarios.md', sample: 'samples/model_output_sample.csv' })}</div>
        <div class="btn-row"><label class="btn" for="scModel"><span class="ms-icon" aria-hidden="true">upload</span>${esc(T('Choose a file'))}</label><input type="file" id="scModel" accept=".csv,.geojson,.json,text/csv,application/geo+json,application/json" hidden></div>
        ${st.models.length ? `<ul class="sc-ul">${st.models.map(m => `<li>${esc(m.header.model_name)} ${esc(m.header.model_version)} · ${esc(Tn(m.series.length, '{n} variable', '{n} variables'))}</li>`).join('')}</ul>` : ''}
      </section></div>
      <div class="note" role="status" id="scMsg">${esc(st.msg)}</div>${st.err.length ? `<ul class="sc-err">${st.err.slice(0, 10).map(e => `<li>${esc(e)}</li>`).join('')}</ul>` : ''}
      <h3 class="sec">${esc(Tn(all.length, '{n} saved scenario', '{n} saved scenarios'))}</h3>
      ${all.length ? `<div class="eb-scroll" tabindex="0" role="region" aria-label="${esc(T('Saved scenarios, scrollable'))}"><table class="ec-tbl wide"><tbody>${rows}</tbody></table></div>` : `<div class="empty">${esc(T('No scenario saved yet.'))}</div>`}
      ${all.length >= 2 ? `<h3 class="sec">${esc(T('Compare two scenarios'))}</h3><div class="eb-tools"><label>A <select id="scA">${opt(st.a)}</select></label><label>B <select id="scB">${opt(st.b)}</select></label></div><div id="scCmp"></div>` : ''}`;
    body.classList.add('eb-free');
    wire(body, all);
    if (st.a && st.b) compare(body, all);
  }
  function wire(body, all) {
    const say = (msg, err = []) => { st.msg = msg; st.err = err; render(body); };
    body.querySelector('#scSave').onclick = async () => {
      const name = body.querySelector('#scName').value.trim(), label = body.querySelector('#scLabel').value.trim(), notes = body.querySelector('#scNotes').value.trim();
      if (!name) { body.querySelector('#scName').focus(); return say(T('Give the scenario a name.')); }
      if ([name, label, notes].some(S_.personal)) return say(T('Leave out e-mail addresses and telephone numbers: name a team or organization instead.'));
      ecWriteHash(true); await new Promise(r => setTimeout(r, 300));   // the link of this view, written now
      const onMap = new Set(EC.layers.map(l => l.key)), models = [...st.models, ...(EC.scenario ? EC.scenario.models : [])].filter((m, i, a) => a.findIndex(x => keyOf(x.header, '') === keyOf(m.header, '')) === i && m.series.some(sr => onMap.has(keyOf(m.header, sr.variable))));   // the model outputs whose layers are on the map: a scenario holds the runs it shows
      const sc = S_.make({ name, label, notes, hash: location.hash, outputs: outputs(), models });
      await save(sc); say(T('Saved "{name}" with {n} figures.', { name, n: sc.outputs.length }));
    };
    body.querySelector('#scImport').onchange = async (e) => { const f = e.target.files[0]; if (!f) return; const r = S_.read(await f.text(), EC.PR + 1); if (!r.scenario) return say(T('The file is not a scenario of the observatory.'), r.errors); await save(r.scenario); say(T('Imported "{name}".', { name: r.scenario.name })); };
    body.querySelector('#scModel').onchange = async (e) => {
      const f = e.target.files[0]; if (!f) return;
      if (f.size > 5 * 1024 * 1024) return say(T('The file is larger than 5 MB.'));
      const m = S_.parseModel(await f.text(), EC.ids.slice(0, EC.PR));
      if (m.errors.length) return say(T('The file was not loaded: fix these and try again.'), m.errors);
      const keys = register(m); st.models.push({ header: m.header, series: m.series }); shade(keys[0]);
      say(Tn(keys.length, 'Loaded {n} variable from {model}: it is on the map, labeled as a model output. Save the view as a scenario to keep it.', 'Loaded {n} variables from {model}: the first is on the map, labeled as a model output. Save the view as a scenario to keep them.', { model: `${m.header.model_name} ${m.header.model_version}` }));
    };
    body.onclick = async (e) => {
      const b = e.target.closest('[data-open],[data-export],[data-del]'); if (!b) return;
      const sc = all.find(x => x.id === (b.dataset.open || b.dataset.export || b.dataset.del)); if (!sc) return;
      if (b.dataset.open) { location.hash = sc.hash + (sc.models.length ? '&sc=' + encodeURIComponent(sc.id) : ''); location.reload(); return; }
      if (b.dataset.export) { const a = document.createElement('a'); a.href = URL.createObjectURL(new Blob([JSON.stringify(sc, null, 1)], { type: 'application/json' })); a.download = `pr_scenario_${norm(sc.name).replace(/[^a-z0-9]+/g, '_').slice(0, 40) || 'scenario'}.json`; a.click(); setTimeout(() => URL.revokeObjectURL(a.href), 4000); return; }
      if (b.dataset.del && window.confirm(T('Delete the scenario "{name}" from this browser?', { name: sc.name }))) { await remove(sc.id); if (st.a === sc.id) st.a = ''; if (st.b === sc.id) st.b = ''; say(T('Deleted "{name}".', { name: sc.name })); }
    };
    const pick = (id, k) => { const el = body.querySelector(id); if (el) el.onchange = e => { st[k] = e.target.value; render(body); }; };
    pick('#scA', 'a'); pick('#scB', 'b');
  }
  function compare(body, all) {
    const A = all.find(x => x.id === st.a), B = all.find(x => x.id === st.b), box = body.querySelector('#scCmp'); if (!A || !B || !box) return;
    const rows = S_.diff(A, B), f = (x, u) => x == null ? '—' : fmt(x, Math.abs(x) < 10 && x % 1 ? 2 : 0) + (u === '%' ? '%' : u ? ' ' + u : '');
    const common = A.models.flatMap(m => m.series.map(s => ({ m, s }))).filter(a => B.models.some(m => m.series.some(s => s.variable === a.s.variable)));
    box.innerHTML = (rows.length ? `<div class="eb-scroll" tabindex="0" role="region" aria-label="${esc(T('The figures of the two scenarios, scrollable'))}"><table class="ec-tbl wide"><thead><tr><th scope="col">${esc(T('Figure'))}</th><th scope="col" class="num">A</th><th scope="col" class="num">B</th><th scope="col" class="num">B − A</th><th scope="col" class="num">%</th></tr></thead><tbody>${rows.map(r => `<tr><th scope="row">${esc(r.label)}</th><td class="num">${f(r.a, r.unit)}</td><td class="num">${f(r.b, r.unit)}</td><td class="num">${f(r.delta, r.unit)}</td><td class="num">${r.pct == null ? '—' : fmt(r.pct, 1) + '%'}</td></tr>`).join('')}</tbody></table></div>`
      : `<div class="empty">${esc(T('Neither scenario kept any figures: plan a route or put layers on the map before saving.'))}</div>`)
      + `<div class="note">${esc(T('A figure that only one scenario has shows a dash for the other. Figures of layers are kept with their year and settings, so the same dataset in another year is another figure.'))}</div>`
      + (common.length ? `<div class="btn-row">${common.map((c, i) => `<button type="button" class="btn small" data-diffmap="${i}">${esc(T('Map B − A: {variable}', { variable: c.s.variable }))}</button>`).join('')}</div>` : '');
    box.querySelectorAll('[data-diffmap]').forEach(b => { b.onclick = () => {
      const a = common[+b.dataset.diffmap], bs = B.models.flatMap(m => m.series.map(s => ({ m, s }))).find(x => x.s.variable === a.s.variable), d = S_.diffSeries(a.s, bs.s), ys = Object.keys(d.years).map(Number);
      if (!ys.length) { st.msg = T('The two model outputs share no period for this variable.'); render(body); return; }
      const key = 'model_diff_' + keyOf(a.m.header, a.s.variable) + '_' + keyOf(bs.m.header, bs.s.variable);
      E.add({ key, group: NOT_OBSERVED, label: `${T(NOT_OBSERVED)}: ${d.variable}, B − A (${B.name} − ${A.name})`, unit: ['%', '$'].includes(d.unit) ? d.unit : '', d: 2, type: 'ratio', family: 'model', years: d.years, ys: ys.sort((p, q) => p - q), static: ys.length === 1, ...(ys.length === 1 ? { time: { type: 'snapshot' } } : {}), sources: [], dictId: 'measures.model_output',
        ref: T('Difference of two model outputs, computed in your browser'), definition: T('The value of scenario B minus the value of scenario A for {variable}, where both give one. Model outputs, not observed data.', { variable: d.variable }) });
      shade(key);
    }; });
  }

  /** On a page opened from a scenario (#…&sc=id): the scenario's model outputs become datasets again, before the layers of the link are restored. */
  async function restore(id) {
    const sc = await get(id); if (!sc) return false;
    sc.models.forEach(register); EC.scenario = sc;
    return true;
  }
  return { render, restore, list, save, remove, register };
})();
