/* PR Data Observatory: the Route analysis page (route-analysis.html, Knowledge Area).
   Loads the routes from data/route_compare.json (written by docs/analysis/route-analysis-2026-10/make_page.py; registered in the data contract and the
   data dictionary as route_compare.*), then draws the 12 routes most exposed to peak-hour congestion (#rcChart), the comparison table (#rcTable) with its
   system filter, and the card of the chosen route. The page's headline figures are static text, written by make_page.py.
   Every visible string goes through T(): its Spanish is in i18n_src/es/routes.json. Route and system names are proper names and stay as they are. */
(function () {
  'use strict';
  // On a narrow screen the tab bar scrolls sideways, and this page's tab (the last area) starts out of view: bring it in
  const toc = document.getElementById('toc'), cur = toc && toc.querySelector('.ka-tab[aria-current="page"]');
  if (cur && toc.scrollWidth > toc.clientWidth) toc.scrollLeft = Math.max(0, cur.offsetLeft + cur.offsetWidth - toc.clientWidth + 24);
  fetchJson('data/route_compare.json').then(start, (e) => {
    document.getElementById('rcBody').innerHTML = `<tr><td class="l">${esc(T('The route data could not be loaded ({error}). Check your connection and reload.', { error: e.message }))}</td></tr>`;
  });

  function start(D) {
    const ROUTES = D.routes, OPS = {}, FEED_END = {};
    D.operators.forEach(o => { OPS[o.operator] = o.operator_name; FEED_END[o.operator] = o.feed_end; });
    // An expired timetable is one whose end date has passed on the day the page is read (the file's flag is that of its own date, as_of)
    const now = new Date(), TODAY = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`;
    const EXPIRED = new Set(Object.keys(FEED_END).filter(k => FEED_END[k] && FEED_END[k] < TODAY));
    ROUTES.forEach(r => { r.timetable_expired = EXPIRED.has(r.operator); });
    const loc = I18N.lang === 'es' ? 'es-PR' : 'en-US';
    const fmt = (v, d) => v === '' || v == null ? '' : Number(v).toLocaleString(loc, { maximumFractionDigits: d == null ? 1 : d });
    const esc = (t) => String(t == null ? '' : t).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/"/g, '&quot;');
    const NS = 'http://www.w3.org/2000/svg';

    // ── Two bar charts of one series each, sorted: #rcChart, the 12 routes with most crossings of high-volume intersections at both peaks (6-9 a.m. plus
    //    4-7 p.m.: it grows with the number of trips), and #rcChart2, the routes whose trip crosses most of them (busy_junctions, whatever the number of trips) ──
    // a short name: the route number and its two ends, without "Estación" and "Terminal" (the full name is in the hover text)
    const short = (r) => r.route + (r.name !== r.route ? ' · ' + r.name.replace(/(Estación|Terminal|Teminal) /g, '').split(' - ').join(' → ') : '') + (r.operator !== 'ati' ? ' (' + r.operator_name + ')' : '');
    const full = (r) => r.operator_name + ' · ' + T('route {route}', { route: r.route }) + (r.name !== r.route ? ' · ' + r.name : '');
    function bars(id, rows, value, tip, axis, aria) {
      const W = 920, L = 380, R = 60, row = 28, top0 = 6, H = top0 + row * rows.length + 40;
      const max = Math.max(...rows.map(value)), step = max > 400 ? 200 : max > 40 ? 10 : 5, end = Math.ceil(max / step) * step;
      const x = (v) => L + (W - L - R) * v / end;
      let s = '';
      for (let v = 0; v <= end; v += step) s += `<line x1="${x(v)}" x2="${x(v)}" y1="${top0}" y2="${top0 + row * rows.length}" stroke="#e4e7ec"/><text x="${x(v)}" y="${top0 + row * rows.length + 16}" text-anchor="middle" class="tick">${fmt(v, 0)}</text>`;
      rows.forEach((r, i) => {
        const y = top0 + i * row + row / 2, v = value(r);
        s += `<g><title>${esc(tip(r))}</title><rect x="0" y="${y - row / 2}" width="${W}" height="${row}" fill="transparent"/>` +
          `<text x="${L - 12}" y="${y + 4.5}" text-anchor="end" class="lab2">${esc(short(r))}${r.timetable_expired ? ' !' : ''}</text>` +
          `<rect x="${L}" y="${y - 8}" width="${Math.max(1, x(v) - L)}" height="16" rx="3" fill="#338CB3"/>` +
          `<text x="${x(v) + 6}" y="${y + 4.5}" class="val">${fmt(v, 0)}</text></g>`;
      });
      s += `<text x="${(L + W - R) / 2}" y="${H - 4}" text-anchor="middle" class="axis">${esc(axis)}</text>`;
      const svg = document.createElementNS(NS, 'svg');
      svg.setAttribute('viewBox', `0 0 ${W} ${H}`); svg.setAttribute('width', '100%'); svg.setAttribute('role', 'img'); svg.setAttribute('aria-label', aria);
      svg.innerHTML = s;
      document.getElementById(id).appendChild(svg);
    }
    function chart() {
      const both = (r) => r.busy_passes_6_9 + r.busy_passes_16_19;
      bars('rcChart', ROUTES.slice().sort((a, b) => both(b) - both(a)).slice(0, 12), both,
        r => T('{route}: {n} times ({am} from 6 to 9 a.m., {pm} from 4 to 7 p.m.)', { route: full(r), n: fmt(both(r), 0), am: fmt(r.busy_passes_6_9, 0), pm: fmt(r.busy_passes_16_19, 0) }),
        T('times its buses go through an intersection with heavy traffic, 6–9 a.m. and 4–7 p.m.'),
        T('The 12 routes with most crossings of high-volume intersections at peak hours'));
      // the 12 routes whose trip crosses most high-volume intersections, and every route tied with the 12th
      const byJ = ROUTES.slice().sort((a, b) => b.busy_junctions - a.busy_junctions), cut = byJ[11].busy_junctions;
      bars('rcChart2', byJ.filter(r => r.busy_junctions >= cut), r => r.busy_junctions,
        r => T('{route}: {n} high-volume intersections on its path; {t} trips a day', { route: full(r), n: fmt(r.busy_junctions, 0), t: fmt(r.weekday_trips, 0) }),
        T('intersections with heavy traffic on a single trip, start to end'),
        T('The routes whose trip crosses most high-volume intersections'));
    }

    // ── The comparison table ──
    // key: shown in the short table, with its own heading (hk) because the short table has no group row; g: the dimension of the full table's group row
    const COLS = [
      { k: 'operator_name', h: T('System'), l: 1, s: 'str', key: 1, g: 0 },
      { k: 'route', h: T('Route'), l: 1, s: 'route', cls: 'rt', key: 1, g: 0 },
      { k: 'name', h: T('Name'), l: 1, s: 'str', cls: 'name', key: 1, g: 0 },
      { k: 'weekday_trips', h: T('Trips'), t: T('Trips on a weekday, both directions'), key: 1, g: 1 },
      { k: 'peak_headway_min', h: T('Frequency'), t: T('Every how many minutes it runs 6 to 9 a.m., in the direction with most trips'), key: 1, g: 1 },
      { k: 'length_km', h: T('Km'), t: T('Length of the main route, in km'), g: 2 },
      { k: 'speed_kmh', h: T('Km/h'), t: T('Scheduled speed, in km an hour'), g: 2 },
      { k: 'busy_junctions', h: T('Total'), hk: T('High-volume intersections'), t: T('Intersections with an estimated 2,000 or more vehicles an hour in the design hour on its path'), key: 1, g: 3 },
      { k: 'busy_per_10km', h: T('Per 10 km'), t: T('High-volume intersections per 10 km of route'), g: 3 },
      { k: 'busy_passes_6_9', h: T('Crossings a.m.'), hk: T('Crossings 6–9 a.m.'), t: T('Times its trips cross those intersections 6 to 9 a.m.'), key: 1, g: 3 },
      { k: 'busy_passes_16_19', h: T('Crossings p.m.'), t: T('Times its trips cross those intersections 4 to 7 p.m.'), g: 3 },
      { k: 'reaches_tren_urbano', h: T('Train'), t: T('Has a stop within 300 m of a Tren Urbano station'), s: 'bool', g: 4 },
      { k: 'other_operators', h: T('Systems'), t: T('Other systems with a stop within 250 m of its stops'), g: 4 },
      { k: 'residents_400m', h: T('People'), hk: T('Residents within 400 m'), t: T('Residents (2020 Census) within 400 m of a stop, each person counted once'), key: 1, g: 5 },
      { k: 'footbridges_30m', h: T('Bridges'), t: T('Pedestrian bridges within 30 m of its path'), g: 6 },
    ];
    const GROUPS = ['', T('1 · Service'), T('2 · Route'), T('3 · Peak-hour intersections'), T('4 · Connections'), T('5 · Residents'), T('Supplementary')];
    let op = 'all', sortK = 'busy_passes_6_9', dir = -1, sel = null, all = false;
    const ops = document.getElementById('rcOps'), head = document.getElementById('rcHead'), body = document.getElementById('rcBody');
    const group = document.getElementById('rcGroup'), table = document.getElementById('rcTable'), toggle = document.getElementById('rcAll');
    const shown = () => COLS.filter(c => all || c.key);

    function filters() {
      const counts = {}; ROUTES.forEach(r => counts[r.operator] = (counts[r.operator] || 0) + 1);
      const nM = ROUTES.filter(r => r.region === 'metro').length;
      const list = [['all', T('All ({n})', { n: ROUTES.length })], ['metro', T('Metro area ({n})', { n: nM })], ['este', T('East ({n})', { n: ROUTES.length - nM })]]
        .concat(Object.keys(OPS).map(k => [k, OPS[k] + ' (' + counts[k] + ')']));
      ops.innerHTML = list.map(([k, t]) => `<button type="button" data-op="${k}" aria-pressed="${k === op}">${esc(t)}</button>`).join('');
      ops.addEventListener('click', e => { const b = e.target.closest('button'); if (!b) return; op = b.dataset.op; draw(); });
    }
    function header() {
      const cols = shown();
      head.innerHTML = cols.map(c => `<th class="${c.l ? 'l' : ''}" data-k="${c.k}"${c.t ? ` title="${esc(c.t)}"` : ''}><button type="button">${esc(!all && c.hk ? c.hk : c.h)}${c.t ? `<span class="rc-help">${esc(c.t)}</span>` : ''}</button></th>`).join('');
      // the group row (the five dimensions) only in the full table; the short table names each column in full instead
      const runs = []; cols.forEach(c => { const u = runs[runs.length - 1]; if (u && u.g === c.g) u.n++; else runs.push({ g: c.g, n: 1 }); });
      group.innerHTML = all ? runs.map(u => `<th colspan="${u.n}">${esc(GROUPS[u.g])}</th>`).join('') : '';
      table.classList.toggle('compact', !all);
      toggle.textContent = all ? T('Show the key columns') : T('Show all columns ({n})', { n: COLS.length });
      toggle.setAttribute('aria-pressed', all);
    }
    head.addEventListener('click', e => { const th = e.target.closest('th'); if (!th) return; const k = th.dataset.k; if (k === sortK) dir = -dir; else { sortK = k; dir = COLS.find(c => c.k === k).l ? 1 : -1; } draw(); });
    toggle.addEventListener('click', () => { all = !all; header(); draw(); stick(); });
    const val = (r, c) => {
      const v = r[c.k];
      if (c.s === 'str') return String(v).toLowerCase();
      if (c.s === 'route') return isNaN(+v) ? 1e6 + String(v).charCodeAt(0) : +v;
      if (c.s === 'bool') return v ? 1 : 0;
      return v === '' || v == null ? null : +v;
    };
    const cell = (r, c) => {
      const v = r[c.k];
      if (c.k === 'operator_name') return esc(v) + (r.timetable_expired ? ` <span class="rc-flag" title="${esc(T('Expired timetable'))}">!</span>` : '');
      if (c.k === 'name') return `<span title="${esc(v)}">${esc(v)}</span>`;
      // the asterisk of an estimate goes by the route, which every screen shows (the crossings columns can be off a narrow screen)
      if (c.k === 'route') return `<b title="${esc(v)}">${esc(v)}</b>` + (r.passes_estimated ? `<span class="rc-flag" title="${esc(T('Estimated'))}">*</span>` : '');
      if (c.k === 'reaches_tren_urbano') return v ? esc(T('Yes')) : esc(T('No'));
      if (c.k === 'residents_400m') return fmt(v, 0);
      if (c.k === 'busy_passes_6_9' || c.k === 'busy_passes_16_19') return fmt(v, 0);
      // a timetable-only route: its length is the operator's line and its speed that of the timed stretch (the note under the table)
      if ((c.k === 'length_km' || c.k === 'speed_kmh') && r.timepoints_only && v !== '' && v != null) return fmt(v) + `<span class="rc-flag" title="${esc(T('Timetable only: see note 3'))}">*</span>`;
      return fmt(v);
    };
    function draw() {
      ops.querySelectorAll('button').forEach(b => b.setAttribute('aria-pressed', b.dataset.op === op));
      head.querySelectorAll('th').forEach(th => th.setAttribute('aria-sort', th.dataset.k === sortK ? (dir > 0 ? 'ascending' : 'descending') : 'none'));
      const c = COLS.find(x => x.k === sortK);
      const rows = ROUTES.filter(r => op === 'all' || r.operator === op || r.region === op).slice().sort((a, b) => {
        const x = val(a, c), y = val(b, c);
        if (x === null && y === null) return 0; if (x === null) return 1; if (y === null) return -1;
        return x < y ? -dir : x > y ? dir : 0;
      });
      body.innerHTML = rows.map(r => {
        const id = r.operator + '|' + r.route;
        return `<tr data-id="${esc(id)}"${id === sel ? ' class="sel"' : ''} tabindex="0">` + shown().map(c => `<td class="${c.l ? 'l ' : ''}${c.cls || ''}">${cell(r, c)}</td>`).join('') + '</tr>';
      }).join('');
    }
    function detail(id) {
      sel = id; const r = ROUTES.find(x => x.operator + '|' + x.route === id); if (!r) return;
      const t = (a, b) => `<div><dt>${esc(a)}</dt><dd>${b}</dd></div>`;
      const service = T('{n} trips a day, from {first} to {last}', { n: fmt(r.weekday_trips, 0), first: r.first, last: r.last }) +
        (r.peak_headway_min ? '. ' + T('At the morning peak, one every {m} min', { m: r.peak_headway_min }) : '');
      const route = (r.length_km ? T('{km} km', { km: fmt(r.length_km) }) : T('no data')) + ', ' +
        (r.speed_kmh ? T('{v} km/h scheduled', { v: fmt(r.speed_kmh) }) : T('speed not calculated')) +
        (r.timepoints_only ? ' ' + T('(timetable only: length of the route line drawn by the operator)') : '');
      const junctions = T('{n} high-volume intersections ({p} per 10 km). Its trips cross them {am} times 6 to 9 a.m. and {pm} times 4 to 7 p.m.',
        { n: fmt(r.busy_junctions, 0), p: fmt(r.busy_per_10km), am: fmt(r.busy_passes_6_9, 0), pm: fmt(r.busy_passes_16_19, 0) }) + (r.passes_estimated ? ' ' + T('(estimated)') : '');
      const links = (r.reaches_tren_urbano ? T('Reaches the Tren Urbano') : T('Does not reach the Tren Urbano')) +
        (r.other_operators ? '. ' + T('Shares stops with: {names}', { names: r.other_operator_names }) : '') + (r.region === 'este' ? '. ' + T('No connection with the ATI network') : '');
      const title = r.operator_name + ' · ' + T('route {route}', { route: r.route }) + (r.name !== r.route ? ' · ' + r.name : '');
      document.getElementById('rcDetail').innerHTML = `<div class="card-head"><h3>${esc(title)}</h3></div><dl>` +
        t(T('1 · Service'), esc(service)) + t(T('2 · Route'), esc(route)) + t(T('3 · Peak-hour intersections'), esc(junctions)) +
        t(T('4 · Connections'), esc(links)) + t(T('5 · Nearby residents'), esc(T('{n} within 400 m of one of its {s} stops', { n: fmt(r.residents_400m, 0), s: r.stops }))) +
        t(T('Supplementary · Pedestrian bridges'), esc(r.footbridges_30m ? T('{n} within 30 m of its path', { n: fmt(r.footbridges_30m, 0) }) : T('none on its path'))) + '</dl>' +
        (r.timetable_expired ? `<p class="ra-p rc-flag">${esc(T('Timetable expired on {date}: it may not be the current service.', { date: FEED_END[r.operator] }))}</p>` : '');
      draw();
    }

    const names = Object.keys(OPS).filter(k => EXPIRED.has(k)).map(k => OPS[k]);
    document.getElementById('rcExpired').innerHTML = '<b class="rc-flag">!</b> ' + esc(names.length
      ? T('Timetables expired today: {names}. They may not reflect the current service.', { names: I18N.list(names) })
      : T('No timetable has expired today.'));

    chart();
    filters(); header();
    body.addEventListener('click', e => { const tr = e.target.closest('tr'); if (tr) detail(tr.dataset.id); });
    body.addEventListener('keydown', e => { if (e.key === 'Enter') { const tr = e.target.closest('tr'); if (tr) detail(tr.dataset.id); } });
    draw(); detail('ati|7');
    function stick() { head.querySelectorAll('th').forEach(th => th.style.top = group.offsetHeight + 'px'); }
    stick(); addEventListener('resize', stick);
  }
})();
