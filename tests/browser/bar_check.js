await new Promise(r => setTimeout(r, 700));
const tb = document.querySelector('.topbar');
const vis = [...tb.children].filter(c => { const r = c.getBoundingClientRect(); return r.width > 0 && r.height > 0 && getComputedStyle(c).visibility !== 'hidden'; });
const box = (c) => { const r = c.getBoundingClientRect(); return { n: c.className || c.tagName, l: Math.round(r.left), t: Math.round(r.top), r: Math.round(r.right), b: Math.round(r.bottom), w: Math.round(r.width) }; };
const rects = vis.map(box);
const si = tb.querySelector('.search input'); if (si && getComputedStyle(si).display !== 'none') { const r = box(si); r.n = 'search-input'; rects.push(r); }
const overlaps = [];
for (let i = 0; i < rects.length; i++) for (let j = i + 1; j < rects.length; j++) {
  const a = rects[i], b = rects[j];
  if ((a.n === 'search' && b.n === 'search-input') || (b.n === 'search' && a.n === 'search-input')) continue;
  if (a.l < b.r - 1 && b.l < a.r - 1 && a.t < b.b - 1 && b.t < a.b - 1) overlaps.push(a.n + ' x ' + b.n);
}
const h1 = tb.querySelector('.brand h1');
const out = {
  w: innerWidth, barH: Math.round(tb.getBoundingClientRect().height), scrollOverflow: document.documentElement.scrollWidth > innerWidth,
  outOfView: rects.filter(r => r.r > innerWidth + 1 || r.l < -1).map(r => r.n),
  overlaps, h1: h1 && getComputedStyle(h1.parentElement).display !== 'none' ? [Math.round(h1.getBoundingClientRect().width), h1.scrollWidth] : 'hidden',
  sub: (() => { const s = tb.querySelector('.brand span'); return s && getComputedStyle(s).display !== 'none' ? Math.round(s.getBoundingClientRect().height) : 'hidden'; })(),
  lang: (() => { const l = tb.querySelector('.lang-switch'); if (!l) return null; const r = l.getBoundingClientRect(); return [Math.round(r.left), Math.round(r.right)]; })(),
};
JSON.stringify(out)
