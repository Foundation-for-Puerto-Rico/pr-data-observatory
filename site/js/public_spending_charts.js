/* PR Data Observatory: the Public spending page's after-ready charts (Public spending PR 7, HANDOFF decision 85). public_spending.js loads this file
   once the budget is drawn and calls it with the figures; nothing here reads data or the address. Three drawings, each an SVG with a text equivalent
   in the page's tables:
   - pipeline(box, o): for each fiscal year, the proposed, approved and spent columns of the budget side by side (one function or all);
   - sankey(box, o): one budget column as bands from the fund the money comes from to the function it pays for;
   - hexMap(): the 78 municipios as equal hexagons (HEX, written by docs/analysis/public-spending-2026-11/make_hex.py), in the same shape as the
     outline map's paths, so the capital projects map can switch between the two.
   Strings come from the caller already translated (o.t), so this file has no Spanish of its own. */
(function (root) {
  'use strict';
  const NS = 'http://www.w3.org/2000/svg';
  // municipio id (without 72), column, row and short label of each hexagon: make_hex.py
  const HEX = '001:4.3:Adj,003:0.1:Agu,005:1.0:Aga,007:8.4:AB,009:6.5:Aib,011:1.2:Aña,013:4.1:Are,015:9.6:Arr,017:5.0:Bar,019:7.4:Baa,021:8.1:Bay,023:1.4:CR,025:8.3:Cag,027:3.1:Cam,029:10.1:Can,031:9.1:Car,033:8.0:Cat,035:8.5:Cay,037:12.2:Cei,039:5.3:Cia,041:7.5:Cid,043:5.5:Coa,045:7.3:Com,047:6.3:Cor,049:14.1:Cul,051:7.0:Dor,053:12.1:Faj,054:5.2:Flo,055:2.5:Guá,057:8.6:Gua,059:3.6:Guy,061:9.2:Gun,063:9.3:Gur,065:4.0:Hat,067:0.3:Hor,069:11.4:Hum,071:2.0:Isa,073:5.4:Jay,075:5.6:JD,077:11.2:Jun,079:2.4:Laj,081:3.2:Lar,083:2.2:Las,085:10.3:Lap,087:10.0:Loí,089:11.1:Luq,091:5.1:Man,093:3.3:Mar,095:10.5:Mau,097:1.3:May,099:1.1:Moc,101:6.2:Mor,103:11.3:Nag,105:7.2:Nar,107:6.4:Oro,109:9.5:Pat,111:4.4:Peñ,113:4.6:Pon,115:3.0:Que,117:0.2:Rin,119:11.0:RG,121:3.4:SG,123:7.6:Sal,125:2.3:Sge,127:9.0:SJ,129:9.4:SL,131:2.1:SS,133:6.6:SI,135:8.2:TA,137:7.1:TB,139:10.2:Tal,141:4.2:Utu,143:6.1:VA,145:6.0:VB,147:13.3:Vie,149:4.5:Vil,151:10.4:Yab,153:3.5:Yau';
  function el(tag, attrs, parent) { const e = root.document.createElementNS(NS, tag); for (const k in attrs) e.setAttribute(k, attrs[k]); if (parent) parent.appendChild(e); return e; }
  const width = (box) => Math.max(320, box.clientWidth || 800);
  function wrapText(s, n) { const out = []; let line = ''; for (const w of String(s).split(/\s+/)) { if ((line + ' ' + w).trim().length > n && line) { out.push(line); line = w; } else line = (line + ' ' + w).trim(); } if (line) out.push(line); return out; }

  // ── Proposed, approved and spent for each fiscal year ──
  // o: { years: [..], stages: [[key, label, colour], ..], value(year, stage) -> number|null, money(v), short(v), label: aria label, t: {none} }
  function pipeline(box, o) {
    const W = width(box), H = 210, top = 26, base = H - 30, n = o.years.length, ns = o.stages.length;
    const vals = o.years.map((y) => o.stages.map(([s]) => o.value(y, s)));
    const max = Math.max(1, ...vals.flat().filter((v) => v != null));
    const gw = (W - 8) / n, bw = Math.min(46, (gw - 18) / ns);
    box.innerHTML = '';
    const svg = el('svg', { viewBox: `0 0 ${W} ${H}`, width: '100%', role: 'img', 'aria-label': o.label }, box);
    el('line', { x1: 0, x2: W, y1: base, y2: base, class: 'grid' }, svg);
    o.years.forEach((y, i) => {
      const x0 = 4 + i * gw + (gw - bw * ns) / 2;
      o.stages.forEach(([s, lab, col], k) => {
        const v = vals[i][k], x = x0 + k * bw;
        if (v == null) {
          el('text', { x: x + bw / 2, y: base - 6, class: 'tick', 'text-anchor': 'middle' }, svg).textContent = '·';
          return;
        }
        const h = (base - top) * Math.max(0, v) / max, g = el('g', {}, svg);
        el('title', {}, g).textContent = `${o.yearLabel(y)}, ${lab}: ${o.money(v)}`;
        el('rect', { x: x + 2, y: base - h, width: bw - 4, height: h, rx: 3, fill: col }, g);
        if (bw >= 30) el('text', { x: x + bw / 2, y: base - h - 6, class: 'val', 'text-anchor': 'middle' }, g).textContent = o.short(v);
      });
      el('text', { x: x0 + bw * ns / 2, y: base + 18, class: 'lab', 'text-anchor': 'middle' }, svg).textContent = o.yearLabel(y);
    });
  }

  // ── One budget column from fund to function ──
  // o: { left: [[key, label, colour, value]], right: [[key, label, value]], flows: [[leftKey, rightKey, value]], money(v), label, minLabel }
  function sankey(box, o) {
    const W = width(box), narrow = W < 560, gap = 6, nodeW = 14;
    const xL0 = narrow ? 0 : 150, xR0 = narrow ? W * 0.22 : W * 0.5, perLine = Math.max(12, Math.floor((W - xR0 - nodeW - 10) / 7));
    const lines = (lab) => (narrow ? wrapText(lab, perLine) : [lab]), slot = (lab) => (narrow ? 15 * (lines(lab).length + 1) + 6 : 22);   // each function keeps room for its label
    const total = o.left.reduce((s, x) => s + x[3], 0) || 1, right = o.right.filter((r) => r[2] > 0);
    const k = 300 / total, xL = xL0, xR = xR0;
    const L = {}, R = {};
    let yr = 5;
    right.forEach(([key, lab, v]) => { const h = v * k; R[key] = { y: yr, h, lab, v, off: 0 }; yr += Math.max(h, slot(lab)) + gap; });
    const lsum = o.left.reduce((s, x) => s + x[3] * k, 0), lgap = o.left.length > 1 ? Math.max(gap, (yr - 5 - gap - lsum) / (o.left.length - 1)) : 0;
    let yl = 5;
    o.left.forEach(([key, lab, col, v]) => { L[key] = { y: yl, h: v * k, col, lab, v, off: 0 }; yl += v * k + lgap; });
    const H = Math.ceil(Math.max(yr, yl) + 4);
    box.innerHTML = '';
    const svg = el('svg', { viewBox: `0 0 ${W} ${H}`, width: '100%', role: 'img', 'aria-label': o.label }, box);
    // bands: from each fund into each function, in the order of the functions
    const order = new Map(right.map((r, i) => [r[0], i]));
    o.flows.filter((f) => f[2] > 0 && R[f[1]] && L[f[0]]).sort((a, b) => order.get(a[1]) - order.get(b[1])).forEach(([a, b, v]) => {
      const s = L[a], t = R[b], h = v * k, y0 = s.y + s.off, y1 = t.y + t.off, x0 = xL + nodeW, x1 = xR, mx = (x0 + x1) / 2;
      s.off += h; t.off += h;
      const g = el('g', {}, svg); el('title', {}, g).textContent = `${s.lab} → ${t.lab}: ${o.money(v)}`;
      el('path', { d: `M${x0},${y0}C${mx},${y0} ${mx},${y1} ${x1},${y1}L${x1},${y1 + h}C${mx},${y1 + h} ${mx},${y0 + h} ${x0},${y0 + h}Z`, fill: s.col, 'fill-opacity': 0.38, class: 'band' }, g);
    });
    for (const key in L) {
      const n = L[key];
      el('rect', { x: xL, y: n.y, width: nodeW, height: Math.max(1, n.h), fill: n.col, rx: 2 }, svg);
      if (!narrow) {
        el('text', { x: xL - 8, y: n.y + n.h / 2 - 2, class: 'lab', 'text-anchor': 'end' }, svg).textContent = n.lab;
        el('text', { x: xL - 8, y: n.y + n.h / 2 + 14, class: 'tick', 'text-anchor': 'end' }, svg).textContent = o.money(n.v);
      }
    }
    for (const key in R) {
      const n = R[key], ls = lines(n.lab), cy = n.y + Math.max(n.h, slot(n.lab) - gap) / 2 - (ls.length - 1) * 7.5;
      el('rect', { x: xR, y: n.y, width: nodeW, height: Math.max(1, n.h), fill: '#5b6475', rx: 2 }, svg);
      if (narrow) {
        ls.forEach((l, i) => { el('text', { x: xR + nodeW + 6, y: cy - 2 + 15 * i, class: 'lab' }, svg).textContent = l; });
        el('text', { x: xR + nodeW + 6, y: cy + 13 + 15 * (ls.length - 1), class: 'tick' }, svg).textContent = o.money(n.v);
      } else el('text', { x: xR + nodeW + 6, y: cy + 4, class: 'lab' }, svg).textContent = `${n.lab} · ${o.money(n.v)}`;
    }
    return narrow;
  }

  // ── The municipios as equal hexagons, in the outline map's shape: { W, H, paths: [{ id, d, x, y, abbr }] } ──
  function hexMap() {
    const r = 30, w = Math.sqrt(3) * r, cells = HEX.split(',').map((s) => { const [id, qr, abbr] = s.split(':'); const [q, rr] = qr.split('.').map(Number); return { id: '72' + id, q, r: rr, abbr }; });
    const pts = (cx, cy) => [0, 1, 2, 3, 4, 5].map((i) => { const a = Math.PI / 180 * (60 * i - 30); return `${(cx + (r - 1) * Math.cos(a)).toFixed(1)},${(cy + (r - 1) * Math.sin(a)).toFixed(1)}`; });
    const maxQ = Math.max(...cells.map((c) => c.q)), maxR = Math.max(...cells.map((c) => c.r));
    const paths = cells.map((c) => { const x = w / 2 + c.q * w + (c.r % 2 ? w / 2 : 0) + 2, y = r + c.r * 1.5 * r + 2; return { id: c.id, d: 'M' + pts(x, y).join('L') + 'Z', x, y, abbr: c.abbr }; });
    return { W: Math.ceil((maxQ + 1.5) * w + 4), H: Math.ceil(maxR * 1.5 * r + 2 * r + 4), paths, hex: true };
  }

  /** Method card (decision 109, step 4): each budget's share by where its lines take their function, and the agencies classified by default. */
  function basis(box, o) {
    const { D, T, esc, big, pct, FUNCTION } = o, B = D.basis; if (!box || !B) return;
    const K = ['#205D7B', '#5FAFDA', '#9AA3B2', '#E39B2D'], L = { program: 'Program', object: 'Object of expense', concept: 'Concept (debt, pensions)', agency: "Agency's general function" };
    const col = (c) => T('FY{year}', { year: c.year }) + ' ' + T(c.stage === 'actual' ? 'spent' : c.stage), last = D.columns[B.column];
    let h = `<div class="ps-legend">${B.kinds.map((k, i) => `<span><i style="background:${K[i]}" aria-hidden="true"></i>${esc(T(L[k]))}</span>`).join('')}</div>`;
    h += `<table class="ps-table"><thead><tr><th scope="col">${esc(T('Budget'))}</th>${B.kinds.map((k) => `<th scope="col">${esc(T(L[k]))}</th>`).join('')}</tr></thead><tbody>${
      B.by_column.map((v, i) => { const s = v.reduce((a, x) => a + x, 0) || 1; return `<tr><th scope="row">${esc(col(D.columns[i]))}<div class="ps-stack" role="img" aria-label="${esc(T('Bars: share of each budget by where its function comes from. The table has the figures.'))}">${v.map((x, k) => `<i style="width:${(100 * x / s).toFixed(1)}%;background:${K[k]}"></i>`).join('')}</div></th>${v.map((x) => `<td>${esc(pct(100 * x / s, 1))}</td>`).join('')}</tr>`; }).join('')}</tbody></table>`;
    const def = B.agencies.filter((a) => a[2] / a[1] > 0.95).slice(0, 8), mixed = B.agencies.filter((a) => a[3] > 1);
    h += `<h4>${esc(T('The largest agencies classified only by their general function, FY{year} approved', { year: last.year }))}</h4><ul class="ps-bars">${
      def.map((a) => `<li><span class="l">${esc(D.agencies[a[0]] || a[0])}</span><span class="v">${esc(big(a[1]))}</span><span class="v">${esc(T(FUNCTION[D.functions[a[4]]] || D.functions[a[4]]))}</span></li>`).join('')}</ul>`;
    h += `<h4>${esc(T('Agencies whose money is split across functions (debt and pensions aside), FY{year} approved: {n}', { year: last.year, n: mixed.length }))}</h4><ul class="ps-bars">${
      mixed.map((a) => `<li><span class="l">${esc(D.agencies[a[0]] || a[0])}</span><span class="v">${esc(big(a[1]))}</span><span class="v">${esc(T('{n} functions', { n: a[3] }))}</span></li>`).join('')}</ul>`;
    box.innerHTML = h;
  }

  /** Section 3: one concept of expense opened (its definition, its functions and its largest agencies in the budget chosen). */
  const CX = { payroll: 'Salaries, wages and the employer\'s share of benefits of public employees.', purchased_services: 'Services the agencies buy from others, such as professional contracts, rents and utilities.', transfers: 'Money the government passes to people or to other entities, such as the government health plan\'s payments, nutrition assistance and contributions to other entities.', capex: 'Construction, equipment and other long-lived assets.', debt_service: 'Principal and interest on public debt, whatever agency pays them.', other: 'Lines whose concept is none of the above, such as lump-sum appropriations whose purpose the budget does not detail.' };
  function concept(box, o) {
    const { D, ci, k, T, esc, big, pct, FUNCTION } = o, ki = D.concepts.indexOf(k), fns = new Map(), ags = new Map();
    let tot = 0;
    for (const r of D.rows) { const v = r[4][ci]; if (r[2] !== ki || !v) continue; tot += v; fns.set(r[3], (fns.get(r[3]) || 0) + v); ags.set(r[0], (ags.get(r[0]) || 0) + v); }
    const top = (m, name) => [...m].filter(([, v]) => v > 0).sort((a, b) => b[1] - a[1]).slice(0, 6).map(([x, v]) => `<li><span class="l">${esc(name(x))}</span><span class="v">${esc(big(v))} · ${esc(pct(100 * v / tot, 0))}</span></li>`).join('');
    box.innerHTML = `<p class="ps-small">${esc(T(CX[k] || ''))}</p><div class="ps-cx-two"><div><h4>${esc(T('By function'))}</h4><ul class="ps-list">${top(fns, (f) => T(FUNCTION[D.functions[f]] || D.functions[f]))}</ul></div>` +
      `<div><h4>${esc(T('Largest agencies'))}</h4><ul class="ps-list">${top(ags, (a) => D.agencies[a] || a)}</ul></div></div>`;
  }

  root.PSCharts = { pipeline, sankey, hexMap, basis, concept };
})(typeof window !== 'undefined' ? window : globalThis);
