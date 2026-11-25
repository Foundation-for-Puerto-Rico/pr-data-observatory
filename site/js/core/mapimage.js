/* PR Data Observatory core: the parts of "Save the map as an image" that need no page (Tools › Map tools, decision 97 step 3; docs/map-image.md).

     MapImage.niceScale(mPerPx, maxPx)   the longest round length (1, 2 or 5 × 10^n meters) whose bar fits in maxPx pixels: { m, px, label }
     MapImage.fileName(date)            pr-data-observatory-map-YYYY-MM-DD.png
     MapImage.swatch(style)             how a legend swatch is drawn, from its classes and computed colors: { kind: 'fill'|'line'|'pin'|'ramp', colors: [...] }
     MapImage.columns(blocks, width, colW)   legend blocks laid out in columns across the band under the map: [{ x, y, block }] and the band's height
   site/js/mapimage.js draws the image with these. Tested in Node by tests/mapimage.test.js. */
(function (name, root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api; else { root.Core = root.Core || {}; root.Core[name] = api; }
})('mapimage', typeof window !== 'undefined' ? window : globalThis, function () {
  'use strict';
  function niceScale(mPerPx, maxPx) {
    if (!(mPerPx > 0 && maxPx > 0)) return null;
    const max = mPerPx * maxPx, p = Math.pow(10, Math.floor(Math.log10(max)));
    const m = [5, 2, 1].map(k => k * p).find(v => v <= max) || p;
    return { m, px: m / mPerPx, label: m >= 1000 ? `${m / 1000} km` : `${m} m` };
  }
  const pad = (n) => String(n).padStart(2, '0');
  const fileName = (d = new Date()) => `pr-data-observatory-map-${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}.png`;
  // the colors a CSS value holds, in order: rgb()/rgba() and #hex
  const colorsIn = (s) => (String(s || '').match(/rgba?\([^)]*\)|#[0-9a-fA-F]{3,8}\b/g) || []);
  const clear = (c) => !c || c === 'transparent' || /rgba\([^)]*,\s*0\)$/.test(c);
  function swatch({ cls = '', bg = '', bgImage = '', border = '' }) {
    const ramp = colorsIn(bgImage);
    if (ramp.length > 1) return { kind: 'ramp', colors: ramp };
    const fill = clear(bg) ? (ramp[0] || '') : bg, edge = colorsIn(border)[0] || '';
    if (/\bline\b/.test(cls)) return { kind: 'line', colors: [clear(fill) || !fill ? edge || '#205D7B' : fill] };
    if (/\bpin\b/.test(cls)) return { kind: 'pin', colors: [fill || '#fff', edge || fill || '#205D7B'] };
    return { kind: 'fill', colors: [fill || edge || '#BDBDBD', edge] };
  }
  /** Blocks of { title, rows: [...] } in columns of colW pixels: each column takes blocks until it is as tall as the tallest single block or 6 rows, whichever is more. */
  function columns(blocks, width, colW, rowH = 18, titleH = 20, gap = 14) {
    const n = Math.max(1, Math.floor(width / colW)), h = (b) => titleH + b.rows.length * rowH + gap;
    const cap = Math.max(titleH + 6 * rowH + gap, ...blocks.map(h));
    const out = []; let col = 0, y = 0, band = 0;
    for (const b of blocks) {
      if (y > 0 && y + h(b) > cap) { col++; y = 0; }
      if (col >= n) break;   // more legends than room: the rest are left out, and the caller says so
      out.push({ x: col * colW, y, block: b }); y += h(b); band = Math.max(band, y);
    }
    return { placed: out, height: band, left: blocks.length - out.length };
  }
  return { niceScale, fileName, swatch, columns, colorsIn };
});
