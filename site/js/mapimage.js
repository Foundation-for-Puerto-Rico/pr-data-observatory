/* PR Data Observatory: Save the map as an image (Tools › Map tools, decision 97 step 3; docs/map-image.md). js/maptools.js loads this file, core/mapimage.js and
   their Spanish (I18N.load('mapimage')) the first time it is used.
   The image is the map as it is on screen, drawn in this browser and saved as a PNG; nothing is sent anywhere. It stacks, in the order the map draws them:
     - the base map (MapLibre's canvas, kept readable by preserveDrawingBuffer in core/basemap.js) and every Leaflet canvas (the map uses preferCanvas);
     - the images on the map (heat, slope, night lights...): all served by this site, so the image can be saved;
     - the markers drawn as boxes (place clusters, stop symbols): their colors, shapes and numbers;
   then, under the map, a band with the title, the legends on screen (the Analysis layers' legend and each switched-on layer's legend), a scale bar, the
   sources (the map's credit line) and the date and address of the view. Pop-ups and the map's buttons are left out. */
const MapImage = (() => {
  const K = Core.mapimage, FONT = '"Gotham", "Montserrat", "Helvetica Neue", Arial, sans-serif';
  const txt = (el) => { if (!el) return ''; const c = el.cloneNode(true); c.querySelectorAll('small, .ms-icon, button, input, select, .help-btn').forEach(x => x.remove()); return c.textContent.replace(/\s+/g, ' ').trim(); };
  const shown = (el) => !!el && el.style.display !== 'none' && !el.hidden;   // a layer's legend box is shown while its layer is on, even inside a closed section of Map layers

  // ── the legends on screen, as { title, rows: [{ label, sw }] } ─────────────
  function rowsOf(box) {
    const bar = box.querySelector('.surf-bar');   // a continuous surface (slope, heat, greenness: core/surfscale.js): its color ramp, its ends and the threshold if one is set
    if (bar) {
      const ticks = [...box.querySelectorAll('.surf-ticks span')].map(x => x.textContent.trim()).filter(Boolean), rows = [{ label: ticks.join(' … ') || txt(box.querySelector('.legend-title')), sw: K.swatch({ bgImage: getComputedStyle(bar).backgroundImage }) }];
      const mn = box.querySelector('.surf-min input'), out = box.querySelector('.surf-min output');
      if (mn && +mn.value > +(mn.min || 0) && out) rows.push({ label: out.textContent.trim(), sw: null });
      return rows;
    }
    return [...box.querySelectorAll('.row')].filter(r => !r.closest('.el-hist') && (!r.querySelector('input[type=checkbox]') || r.querySelector('input').checked)).map(r => {
      const s = r.querySelector('.sw'), cs = s ? getComputedStyle(s) : null;
      return { label: txt(r), sw: cs ? K.swatch({ cls: s.className, bg: cs.backgroundColor, bgImage: cs.backgroundImage, border: [cs.borderTopColor, cs.borderTopWidth !== '0px' ? cs.borderTopColor : ''].filter(Boolean).join(' ') }) : null };
    }).filter(r => r.label);
  }
  function legends() {
    const out = [], seen = new Set(), add = (title, rows) => { if (!rows.length || seen.has(title)) return; seen.add(title); out.push({ title, rows: rows.slice(0, 12), more: Math.max(0, rows.length - 12) }); };
    document.querySelectorAll('#econLegend .el-block').forEach(b => { const t = b.querySelector('.el-t'); add(t ? t.textContent.replace(/\s+/g, ' ').trim() : T('Map'), rowsOf(b)); });   // with its year
    document.querySelectorAll('.legend-box').forEach(b => {
      const prev = b.previousElementSibling, sw = prev && prev.querySelector && prev.querySelector('input[type=checkbox]');   // a layer's legend sits under its switch
      if (!shown(b) || b.id === 'econLegend' || (sw && !sw.checked)) return;
      add(txt(b.querySelector('.legend-title')) || (prev ? txt(prev.querySelector('.ly-name') || prev) : '') || T('Map'), rowsOf(b));
    });
    const ml = document.getElementById('mapLegend'); if (ml && ml.textContent.trim()) add(txt(ml.querySelector('.legend-title')) || T('Map'), rowsOf(ml));
    return out;
  }
  function layerNames() {   // the switched-on layers the chip lists ("On the map"), for the title when there is no shaded layer
    return [...document.querySelectorAll('#alPanel .al-name, #alPanel li b, #alPanel li')].map(txt).filter(Boolean).slice(0, 4);
  }

  // ── drawing ──────────────────────────────────────────────────────────────
  function drawMap(g, c, R) {
    const draw = (el) => { const r = el.getBoundingClientRect(); if (r.width < 1 || r.height < 1 || r.right < R.left || r.left > R.right || r.bottom < R.top || r.top > R.bottom) return; g.drawImage(el, r.left - R.left, r.top - R.top, r.width, r.height); };
    const panes = c.querySelector('.leaflet-map-pane');
    // in the order the map stacks them: by the z-index of each element's pane (panes made by the page come last in the page but sit under the markers)
    const z = (el) => { let p = el; while (p.parentElement && p.parentElement !== panes) p = p.parentElement; return parseInt(getComputedStyle(p).zIndex, 10) || 0; };
    const els = [...panes.querySelectorAll('canvas, img, .leaflet-marker-icon')].map((el, i) => ({ el, i, z: z(el) })).sort((a, b) => a.z - b.z || a.i - b.i).map(o => o.el);
    for (const el of els) {
      if (el.closest('.leaflet-popup-pane, .leaflet-tooltip-pane')) continue;
      try {
        if (el.tagName === 'CANVAS' || el.tagName === 'IMG') { if (getComputedStyle(el).visibility !== 'hidden' && +getComputedStyle(el.parentElement).opacity !== 0) draw(el); }
        else box(g, el, R);
      } catch (e) { /* one element that cannot be read (another site's image) is left out, not the whole map */ }
    }
  }
  function box(g, el, R, depth = 0) {   // a marker built from boxes: its background, border and round corners, then its children, then its own text
    const r = el.getBoundingClientRect(), cs = getComputedStyle(el); if (r.width < 1) return;
    const x = r.left - R.left, y = r.top - R.top, rad = Math.min(r.width, r.height) / 2, round = parseFloat(cs.borderTopLeftRadius) >= rad * 0.8;
    const path = () => { g.beginPath(); if (round) g.arc(x + r.width / 2, y + r.height / 2, rad, 0, Math.PI * 2); else g.rect(x, y, r.width, r.height); };
    if (!/rgba\([^)]*,\s*0\)|transparent/.test(cs.backgroundColor)) { path(); g.fillStyle = cs.backgroundColor; g.fill(); }
    const bw = parseFloat(cs.borderTopWidth) || 0; if (bw) { path(); g.lineWidth = bw; g.strokeStyle = cs.borderTopColor; g.stroke(); }
    if (el.tagName === 'IMG') { g.drawImage(el, x, y, r.width, r.height); return; }
    if (depth < 3) [...el.children].forEach(ch => box(g, ch, R, depth + 1));
    const own = [...el.childNodes].filter(n => n.nodeType === 3).map(n => n.textContent.trim()).join(' ');
    if (own && !el.classList.contains('ms-icon')) { g.fillStyle = cs.color; g.font = `${cs.fontWeight} ${cs.fontSize} ${FONT}`; g.textAlign = 'center'; g.textBaseline = 'middle'; g.fillText(own, x + r.width / 2, y + r.height / 2); }
  }
  function swatchAt(g, sw, x, y) {
    if (!sw) return;
    if (sw.kind === 'ramp') { const gr = g.createLinearGradient(x, 0, x + 22, 0); sw.colors.forEach((c, i) => gr.addColorStop(i / (sw.colors.length - 1), c)); g.fillStyle = gr; g.fillRect(x, y + 3, 22, 10); return; }
    if (sw.kind === 'line') { g.strokeStyle = sw.colors[0]; g.lineWidth = 3; g.beginPath(); g.moveTo(x, y + 8); g.lineTo(x + 22, y + 8); g.stroke(); return; }
    if (sw.kind === 'pin') { g.beginPath(); g.arc(x + 11, y + 8, 6, 0, Math.PI * 2); g.fillStyle = sw.colors[0]; g.fill(); g.lineWidth = 2; g.strokeStyle = sw.colors[1]; g.stroke(); return; }
    g.fillStyle = sw.colors[0]; g.fillRect(x, y + 2, 22, 12); if (sw.colors[1]) { g.lineWidth = 1; g.strokeStyle = sw.colors[1]; g.strokeRect(x + .5, y + 2.5, 21, 11); }
  }
  function fit(g, s, w) { if (g.measureText(s).width <= w) return s; while (s.length > 1 && g.measureText(s + '…').width > w) s = s.slice(0, -1); return s + '…'; }
  function lines(g, s, w) { const out = []; let cur = ''; for (const word of s.split(' ')) { const t = cur ? cur + ' ' + word : word; if (g.measureText(t).width > w && cur) { out.push(cur); cur = word; } else cur = t; } if (cur) out.push(cur); return out; }

  function make() {
    const c = map.getContainer(), R = c.getBoundingClientRect(), W = Math.round(R.width), H = Math.round(R.height), dpr = Math.min(2, window.devicePixelRatio || 1);
    const blocks = legends(), M = 16, colW = 260;
    const probe = document.createElement('canvas').getContext('2d'); probe.font = `12px ${FONT}`;
    const credit = txt(c.querySelector('.leaflet-control-attribution')).replace(/^[^|]*…\s*\|\s*/, '');
    const creditLines = lines(probe, T('Sources: {list}', { list: credit }), W - 2 * M);
    const lay = K.columns(blocks, W - 2 * M, colW);
    const title = blocks.length ? blocks.slice(0, 3).map(b => b.title).join(' · ') + (blocks.length > 3 ? ' …' : '') : (layerNames().join(' · ') || T('PR Data Observatory'));
    const date = I18N.date ? I18N.date(new Date(), { dateStyle: 'long' }) : new Date().toISOString().slice(0, 10);
    const footLines = lines(probe, T('PR Data Observatory · Foundation for Puerto Rico · {date} · {url}', { date, url: location.href.split('?')[0].replace(/^https?:\/\//, '') + location.hash }), W - 2 * M);
    const bandH = M + 28 + (lay.height ? lay.height + 4 : 0) + (lay.left ? 18 : 0) + 30 + creditLines.length * 16 + 4 + footLines.length * 16 + M;
    const cv = document.createElement('canvas'); cv.width = W * dpr; cv.height = (H + bandH) * dpr;
    const g = cv.getContext('2d'); g.scale(dpr, dpr);
    g.fillStyle = '#fff'; g.fillRect(0, 0, W, H + bandH);
    g.save(); g.beginPath(); g.rect(0, 0, W, H); g.clip(); drawMap(g, c, R); g.restore();
    g.strokeStyle = '#d5dadd'; g.lineWidth = 1; g.strokeRect(.5, .5, W - 1, H - 1);
    // the band under the map
    let y = H + M; g.textBaseline = 'top'; g.textAlign = 'left';
    g.fillStyle = '#205D7B'; g.font = `600 17px ${FONT}`; g.fillText(fit(g, title, W - 2 * M), M, y); y += 28;
    for (const p of lay.placed) {
      const bx = M + p.x, by = y + p.y; g.fillStyle = '#2A2E2E'; g.font = `600 12px ${FONT}`; g.fillText(fit(g, p.block.title, colW - 16), bx, by);
      g.font = `12px ${FONT}`; p.block.rows.forEach((r, i) => { const ry = by + 20 + i * 18; swatchAt(g, r.sw, bx, ry); g.fillStyle = '#2A2E2E'; g.fillText(fit(g, r.label, colW - 46), bx + 30, ry + 2); });
      if (p.block.more) { g.fillStyle = '#666'; g.fillText(Tn(p.block.more, '{n} more row on the map page', '{n} more rows on the map page', { n: p.block.more }), bx + 30, by + 20 + p.block.rows.length * 18 + 2); }
    }
    y += lay.height ? lay.height + 4 : 0;
    g.font = `12px ${FONT}`; g.fillStyle = '#666';
    if (lay.left) { g.fillText(Tn(lay.left, '{n} more legend is on the map page.', '{n} more legends are on the map page.', { n: lay.left }), M, y); y += 18; }
    // scale bar at the map's center latitude
    const ctr = map.getSize().divideBy(2), a = map.containerPointToLatLng(ctr), b = map.containerPointToLatLng(ctr.add([100, 0])), sc = K.niceScale(a.distanceTo(b) / 100, 160);
    if (sc) { g.strokeStyle = '#2A2E2E'; g.lineWidth = 2; g.beginPath(); g.moveTo(M, y + 14); g.lineTo(M, y + 20); g.lineTo(M + sc.px, y + 20); g.lineTo(M + sc.px, y + 14); g.stroke(); g.fillStyle = '#2A2E2E'; g.fillText(sc.label, M + sc.px + 8, y + 12); }
    y += 30; g.fillStyle = '#666';
    creditLines.forEach(l => { g.fillText(l, M, y); y += 16; });
    g.fillStyle = '#2A2E2E'; y += 4; footLines.forEach(l => { g.fillText(l, M, y); y += 16; });
    return cv;
  }
  async function save() {
    try {
      if (typeof writeHash === 'function') writeHash();
      const cv = make(), blob = await new Promise((ok, no) => cv.toBlob(b => b ? ok(b) : no(new Error('toBlob')), 'image/png'));
      const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = K.fileName(); document.body.appendChild(a); a.click(); a.remove();
      setTimeout(() => URL.revokeObjectURL(a.href), 10000);
      toast(T('The map image was saved: {file}.', { file: a.download }), 5000);
      return a.download;
    } catch (e) { console.error(e); toast(T('The map image could not be made. Try again, or use your device\'s screenshot.'), 6000); return null; }
  }
  return { save, make, legends };
})();
