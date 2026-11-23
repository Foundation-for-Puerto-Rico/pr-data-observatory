/* PR Data Observatory: the Global Innovation Index page (gii.html, Knowledge Area).
   Loads data/gii_profile.json (written by gii.py from docs/analysis/gii-2021/gii_original.json, gii_crosswalk.json and the open sources) and draws the
   country profile as the 2021 PDF lays it out: 7 pillars, their sub-pillars and the 80 indicators, every row a native <details>. A row shows the printed
   value and rank, the updated value with an arrow against the 2021 value (in the GII's direction), the indicative GII 2026 position "X/N" and what became
   of the indicator in the GII 2026 (a badge). An open indicator explains each. "Changes in the index since 2020" loads data/gii_changes.json the first
   time it is opened. Interface words go through T() (Spanish in i18n_src/es/gii.json); the indicator texts come from the data files ({en, es}). */
(function () {
  'use strict';
  const toc = document.getElementById('toc'), cur = toc && toc.querySelector('.ka-tab[aria-current="page"]');
  if (cur && toc.scrollWidth > toc.clientWidth) toc.scrollLeft = Math.max(0, cur.offsetLeft + cur.offsetWidth - toc.clientWidth + 24);
  const box = document.getElementById('giiProfile');
  box.innerHTML = `<p class="gp-loading">${esc(T('Loading the profile…'))}</p>`;
  const STATUS = { same: 'Same', renamed: 'Renamed', redefined: 'Redefined', dropped: 'Dropped in GII 2026' };
  let profile = null, wantChanges = false;
  fetchJson('data/gii_profile.json').then((D) => { profile = D; start(D); if (wantChanges) changes(); }, (e) => {
    box.innerHTML = `<p class="gp-loading">${esc(T('The profile could not be loaded ({error}). Check your connection and reload.', { error: e.message }))}</p>`;
  });

  const L = () => (I18N.lang === 'es' ? 'es' : 'en');
  const tx = (o) => (o ? o[L()] || o.en || '' : '');
  const dec = (v) => (Math.abs(v) >= 10 ? 1 : 2);
  const num = (v) => (v == null ? '' : fmt(v, dec(v)));
  const badge = (s) => `<span class="gp-st ${esc(s)}">${esc(T(STATUS[s]))}</span>`;
  const IND = () => T('Indicative position calculated by FPR, not an official WIPO rank');
  const short = (c) => c.replace(/^(IN|OUT)\./, '');

  // The arrow beside an updated value: its shape says up or down, its colour better or worse in the GII's direction, its label says it in words
  function arrow(r) {
    if (!r.chg) return '';
    const [glyph, cls, label] = r.chg === 'na' ? ['—', 'na', T('not comparable with 2021')]
      : r.chg === 'same' ? ['≈', 'same', T('no meaningful change from 2021')]
      : [r.chg_delta > 0 ? '▲' : '▼', r.chg, r.chg === 'better' ? T('better than 2021') : T('worse than 2021')];
    return ` <span class="gp-chg ${cls}" role="img" aria-label="${esc(label)}" title="${esc(label)}">${glyph}</span>`;
  }

  function start(D) {
    const TX = D.texts, SRC = D.sources, A = D.about;
    const row = (k, v) => (v ? `<div><dt>${esc(k)}</dt><dd>${v}</dd></div>` : '');
    const anchor = (code) => 'i-' + code.replace(/\./g, '-');

    // ── Summary figures ──
    const nd = D.indicators.filter(r => r.value == null).length;
    document.getElementById('giiKpis').innerHTML = [
      [String(A.profile.indicators), T('indicators in 7 pillars, as in the 2021 profile')],
      [String(A.profile.with_value), T('with a value for Puerto Rico in 2021 ({n} without data)', { n: nd })],
      [String(A.updated_count), T('with a newer value from an open source')],
      [String(A.compared_count), T('with an indicative position among the GII 2026 economies')],
    ].map(([v, l]) => `<div class="kpi"><div class="v">${esc(v)}</div><div class="l">${esc(l)}</div></div>`).join('');

    // ── One indicator ──
    function indicator(r, color) {
      const t = TX[r.code] || {};
      const marks = (r.star ? '<sup class="gp-star" title="' + esc(T('Higher values mean poorer outcomes')) + '">*</sup>' : '') +
        (r.hourglass ? ' <span class="gp-hg" title="' + esc(T('Puerto Rico data older than 2016')) + '">⧗</span>' : '');
      const rank = r.rank ? `${r.rank} / ${r.rank_printed_of}` : T('N/D');
      const upd = r.upd_value != null
        ? `${esc(num(r.upd_value))} <small>${esc(r.upd_year)}</small>${arrow(r)}${r.upd_kind === 'fpr' ? ` <span class="gp-tag fpr">${esc(T('FPR estimate'))}</span>` : ''}`
        : r.c26_status === 'dropped' ? `<span class="gp-none gp-drop">${esc(T('Dropped in GII 2026'))}</span>` : '<span class="gp-none">—</span>';
      const r26 = r.c26_pos
        ? `<b style="background:${color}">${esc(r.c26_pos + '/' + r.c26_of)}</b><sup class="gp-fn" title="${esc(IND())}" aria-hidden="true">†</sup><span class="sr-only"> (${esc(IND())})</span>`
        : '<span class="gp-none">—</span>';
      const head = `<summary><span class="gp-code">${esc(r.code)}</span><span class="gp-name">${esc(tx(t.name))}${marks} ${badge(r.c26_status)}</span>` +
        `<span class="gp-src">${esc(tx(t.source_printed))}</span>` +
        `<span class="gp-val"><span class="gp-lab">${esc(T('2021 value'))}</span>${r.shown == null ? esc(T('N/D')) : esc(r.shown)}</span>` +
        `<span class="gp-rank"><span class="gp-lab">${esc(T('Rank 2021'))}</span><b style="background:${color}">${esc(rank)}</b></span>` +
        `<span class="gp-upd"><span class="gp-lab">${esc(T('Updated value'))}</span>${upd}</span>` +
        `<span class="gp-r26"><span class="gp-lab">${esc(T('Position GII 2026'))}</span>${r26}</span></summary>`;

      const kinds = [r.composite && T('Composite index'), r.survey && T('Survey-based'), r.higher_is_worse && T('Higher is worse')].filter(Boolean)
        .map(k => `<span class="gp-tag">${esc(k)}</span>`).join(' ');
      const what = esc(tx(t.definition)) + (kinds ? `<span class="gp-kinds">${kinds}</span>` : '');

      const orig = r.value == null
        ? esc(tx(t.method))   // every indicator without a value says so in its method note ("No data…")
        : Th('<b>{value}</b> ({year}), rank {rank}', { value: r.shown, year: r.year || T('year not recorded'), rank }) + '. ' +
          esc(T('Source as printed: {source}.', { source: tx(t.source_printed) })) + ' ' + esc(tx(t.method)) +
          (r.rank_n ? ' ' + esc(T('{n} economies, Puerto Rico included, had data for this indicator in the comparison.', { n: r.rank_n })) : '');

      let updated;
      if (r.upd_value != null) {
        const name = (r.upd_source || '').split('+').map(k => SRC[k] ? tx(SRC[k].name) : k).join('; ');
        const link = r.upd_url ? `<a href="${esc(r.upd_url)}" target="_blank" rel="noopener">${esc(name)}</a>` : esc(name);
        updated = Th('<b>{value}</b> ({year})', { value: num(r.upd_value), year: r.upd_year }) + ', ' + link +
          (r.upd_series ? ` <code>${esc(r.upd_series)}</code>` : '') + '.' +
          (r.upd_kind === 'fpr' ? ` <span class="gp-tag fpr">${esc(T('FPR estimate'))}</span>` : '') +
          (r.upd_estimate ? ' ' + esc(T('A UIS estimate.')) : '') + (t.upd_note ? ' ' + esc(tx(t.upd_note)) : '') + ' ' + changeText(r);
      } else updated = esc(tx(t.not_updated));
      if (r.components && r.components.length) {
        updated += '<ul class="gp-comp">' + r.components.map(c => `<li>${esc(tx((t.components || {})[c.series]))}: <b>${esc(num(c.value))}</b> (${esc(c.year)}, ${esc(T('World Bank'))} <code>${esc(c.series)}</code>)</li>`).join('') + '</ul>';
      }

      let g26 = badge(r.c26_status) + ' ' + (r.c26_full ? esc(T('Maps to indicator {code} of the GII 2026.', { code: short(r.c26_full) }))
        : esc(T('Dropped from the GII 2026 or replaced by a different indicator.'))) + (t.c26_note ? ' ' + esc(tx(t.c26_note)) : '');
      if (r.c26_pos) {
        g26 += ' ' + Th('Indicative position: Puerto Rico\'s value of {year} ({value}) would rank <b>{pos}/{of}</b>: {n} economies with data, most of them for {y26}, plus Puerto Rico.',
          { year: r.c26_pr_year, value: num(r.c26_pr_value), pos: r.c26_pos, of: r.c26_of, n: r.c26_n, y26: r.c26_year }) + ' ' +
          esc(T('Half of those economies have a value between {q1} and {q3}; the median is {med}.', { q1: num(r.c26_q1), q3: num(r.c26_q3), med: num(r.c26_median) })) +
          (r.c26_lower_better ? ' ' + esc(T('Lower is better.')) : '') + ' ' + esc(T('† {label}. Source: WIPO, Global Innovation Index 2026, CC BY 4.0.', { label: IND() }));
      } else if (t.c26_why) g26 += ' ' + esc(tx(t.c26_why));

      const notes = (t.note ? `<p class="note caution gp-note">${esc(tx(t.note))}</p>` : '') +
        (t.proprietary ? `<p class="note gp-note">${esc(T('Proprietary source ({name}): the value is shown as FPR published it in 2021 and is not updated here.', { name: t.proprietary }))}</p>` : '');
      return `<details class="gp-ind" id="${anchor(r.code)}">${head}<div class="gp-body">${notes}<dl>` +
        row(T('What it measures'), what) + row(T('Original (FPR, 2021, GII 2020 method)'), orig) + row(T('Updated value'), updated) + row(T('GII 2026'), g26) +
        '</dl></div></details>';
    }

    // The change against the 2021 value, in words, with its threshold
    function changeText(r) {
      if (!r.chg) return '';
      if (r.chg === 'na') return esc(r.chg_why === 'no_2021' ? T('The 2021 profile has no value to compare with.')
        : r.chg_why === 'series' ? T('Not compared with the 2021 value: the source changed its series in 2024.')
        : r.chg_why === 'method' ? T('Not compared with the 2021 value: the method differs from the one FPR used in 2021.')
        : T('Not comparable with the 2021 value: it was measured with another source and definition.'));
      const word = { better: T('better than 2021'), worse: T('worse than 2021'), same: T('no meaningful change from 2021') }[r.chg];
      const delta = (r.chg_delta > 0 ? '+' : '') + num(r.chg_delta);
      return esc(r.chg_base_year
        ? T('The WGI revises every past year, so the arrow compares two years of the current release: {base} for {by} (the data year the GII 2020 used; the printed value is kept as published) and {value} for {year}, a change of {delta} ({word}).',
          { base: num(r.chg_base), by: r.chg_base_year, value: num(r.upd_value), year: r.upd_year, delta, word })
        : T('Change from the 2021 value: {delta} ({word}).', { delta, word })) + ' ' +
        esc(T('"≈" means a change smaller than {share}% of the interquartile range of the GII 2026 economies for this indicator ({thr}{scale}).',
          { share: Math.round(A.change_share * 100), thr: num(r.chg_thr), scale: r.chg_log ? T(', on the logarithmic scale the GII uses for it') : '' }));
    }

    // ── Pillars and sub-pillars ──
    box.innerHTML = D.pillars.map(p => {
      const subs = p.subs.map(s => `<details class="gp-sub" open><summary><h4><span class="gp-code">${esc(s.code)}</span> ${esc(tx(s.name))}</h4></summary>` +
        `<p class="gp-about">${esc(tx(s.about))}</p>` + D.indicators.filter(r => r.sub === s.code).map(r => indicator(r, p.color)).join('') + '</details>').join('');
      return `<details class="gp-pillar" open style="--pc:${esc(p.color)}"><summary><span class="ms-icon" aria-hidden="true">${esc(p.icon)}</span>` +
        `<h3>${esc(p.code)} · ${esc(tx(p.name))}</h3></summary><p class="gp-about">${esc(tx(p.about))}</p>${subs}</details>`;
    }).join('');

    const all = (open) => box.querySelectorAll('details').forEach(d => { d.open = open; });
    document.getElementById('giiOpen').addEventListener('click', () => all(true));
    document.getElementById('giiClose').addEventListener('click', () => { all(false); box.querySelectorAll('.gp-pillar').forEach(d => { d.open = true; }); });
    // A link to one indicator (#i-1-1-2) opens it and the rows around it
    function reveal() {
      const el = location.hash.length > 1 && document.getElementById(location.hash.slice(1));
      if (!el || !el.matches('.gp-ind')) return;
      for (let d = el; d; d = d.parentElement && d.parentElement.closest('details')) d.open = true;
      el.scrollIntoView({ block: 'start' });
    }
    addEventListener('hashchange', reveal); reveal();
  }

  // ── Changes in the index since 2020: data/gii_changes.json loads the first time the section is opened ──
  const sec = document.getElementById('giiChanges'), body = document.getElementById('giiChangesBody');
  let loaded = false;
  sec.addEventListener('toggle', () => { if (sec.open && !loaded) { loaded = true; if (profile) changes(); else wantChanges = true; } });
  if (location.hash === '#changes') sec.open = true;

  function changes() {
    body.innerHTML = `<p class="gp-loading">${esc(T('Loading…'))}</p>`;
    fetchJson('data/gii_changes.json').then((C) => {
      const D = profile, A = D.about, src = Object.fromEntries(C.sources.map(s => [s.id, s]));
      const cite = (id) => src[id] ? ` <a href="${esc(src[id].url)}" target="_blank" rel="noopener" title="${esc(src[id].name)}">[${esc(T('source'))}]</a>` : '';
      const name = (code) => tx((D.texts[code] || {}).name);
      const th = (hs) => '<thead><tr>' + hs.map(h => `<th scope="col">${esc(h)}</th>`).join('') + '</tr></thead>';
      const ed = '<table class="gp-tbl">' + th([T('Edition'), T('Economies'), T('Indicators'), T('Pillars'), T('Sub-pillars')]) + '<tbody>' +
        C.editions.map(e => `<tr><th scope="row">${esc(e.edition)}${cite(e.source)}</th><td>${e.economies}</td><td>${e.indicators}</td><td>${e.pillars}</td><td>${e.subpillars}</td></tr>`).join('') + '</tbody></table>';
      const sc = A.status_count;
      const sum = esc(T('Of the 80 indicators of the 2021 profile, {same} are the same in the GII 2026, {renamed} were renamed, {redefined} were redefined and {dropped} were dropped; {new} indicators of the GII 2026 are new.',
        { same: sc.same, renamed: sc.renamed, redefined: sc.redefined, dropped: sc.dropped, new: A.new_2026 }));
      const changed = C.crosswalk.filter(x => x.status !== 'same');
      const cw = '<table class="gp-tbl gp-cw">' + th([T('GII 2020'), T('Indicator'), T('GII 2026'), T('Status'), T('What changed')]) + '<tbody>' +
        changed.map(x => `<tr><td><a href="#i-${x.code.replace(/\./g, '-')}">${esc(x.code)}</a></td><td>${esc(name(x.code))}</td><td>${x.c26 ? esc(short(x.c26)) : '—'}</td><td>${badge(x.status)}</td><td>${esc(tx((D.texts[x.code] || {}).c26_note))}</td></tr>`).join('') + '</tbody></table>';
      const PR = { yes: T('Yes'), no: T('No'), proxy: T('FPR estimate possible'), fpr: T('FPR estimate'), proprietary: T('Proprietary'), check: T('Not verified') };
      // An FPR estimate (pr_est) shows its value, year and source, like an updated value
      const est = (x) => {
        const s = D.sources[x.source], link = s ? `<a href="${esc(x.url)}" target="_blank" rel="noopener">${esc(tx(s.name))}</a>` : esc(x.source);
        return ' ' + Th('<b>{value}</b> ({year})', { value: num(x.value), year: x.year }) + ', ' + link + ` <code>${esc(x.series)}</code>.`;
      };
      const nw = '<table class="gp-tbl">' + th([T('GII 2026'), T('New indicator'), T('Source'), T('Puerto Rico data')]) + '<tbody>' +
        C.new_2026.map(e => `<tr><td>${esc(short(e.c26))}</td><td>${esc(tx(e.name))}</td><td>${esc(e.source)}</td><td><b>${esc(PR[e.pr])}</b>.${e.pr_est ? est(e.pr_est) : ''} ${esc(tx(e.pr_note))}</td></tr>`).join('') + '</tbody></table>';
      body.innerHTML = `<p>${sum}</p>${ed}<h3>${esc(T('What changed in the method'))}</h3><ul class="gp-method">` + C.method.map(m => `<li>${esc(tx(m))}${cite(m.source)}</li>`).join('') + '</ul>' +
        `<h3>${esc(T('Indicators that changed ({n})', { n: changed.length }))}</h3><p class="gp-small">${esc(T('The other {n} are the same indicator; some moved to a new code, shown in the open row of each.', { n: sc.same }))}</p><div class="gp-scroll">${cw}</div>` +
        `<h3>${esc(T('New in the GII 2026, not in the 2021 profile ({n})', { n: C.new_2026.length }))}</h3><div class="gp-scroll">${nw}</div>` +
        `<p class="gp-small">${esc(T('Checked on {date} in the sources linked.', { date: C.checked }))}</p>`;
    }, (e) => { loaded = false; body.innerHTML = `<p class="gp-loading">${esc(T('This section could not be loaded ({error}). Close it and open it again.', { error: e.message }))}</p>`; });
  }
})();
