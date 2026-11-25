/* PR Data Observatory core: small maps of the 78 municipios drawn as SVG, with no base map and no tiles: the workbench's small multiples and swipe view, and the area profiles.

     MiniMap.project(fc, names, width)   the outlines of a GeoJSON of municipios (feature property `municipality`) as SVG paths, in the order of `names`: { w, h, d: [path per place] }.
                                         A plain projection with the longitude scaled by the cosine of 18.2°N; points closer than half a unit are dropped.
     MiniMap.svg(P, fills, o)            one map: fills[i] is the color of place i; o = { label, titles: [text per place], strong: Set of places drawn with a dark outline, cls } */
(function (name, root, factory) {
  const dep = (n) => (typeof module === 'object' && module.exports ? require('./' + n + '.js') : root.Core[n]);   // the other core modules, in Node or in a page
  const api = factory(root, dep);
  if (typeof module === 'object' && module.exports) module.exports = api; else { root.Core = root.Core || {}; root.Core[name] = api; }
})('minimap', typeof window !== 'undefined' ? window : globalThis, function (root, dep) {
  'use strict';
  const { esc } = dep('text');
  const K = Math.cos(18.2 * Math.PI / 180);

  function project(fc, names, width = 600) {
    const rings = (g) => g.type === 'Polygon' ? g.coordinates : g.type === 'MultiPolygon' ? g.coordinates.flat() : [];
    let x0 = Infinity, x1 = -Infinity, y0 = Infinity, y1 = -Infinity;
    for (const f of fc.features) for (const r of rings(f.geometry)) for (const [x, y] of r) { x0 = Math.min(x0, x); x1 = Math.max(x1, x); y0 = Math.min(y0, y); y1 = Math.max(y1, y); }
    const s = width / ((x1 - x0) * K), h = Math.ceil((y1 - y0) * s), at = new Map(names.map((n, i) => [n, i])), d = new Array(names.length).fill('');
    for (const f of fc.features) {
      const i = at.get(f.properties.municipality); if (i == null) continue;
      d[i] = rings(f.geometry).map(r => {
        let out = '', px = null, py = null;
        r.forEach(([x, y], k) => { const X = (x - x0) * K * s, Y = (y1 - y) * s; if (k && k < r.length - 1 && Math.abs(X - px) < .5 && Math.abs(Y - py) < .5) return; out += (out ? 'L' : 'M') + X.toFixed(1) + ' ' + Y.toFixed(1); px = X; py = Y; });
        return out + 'Z';
      }).join('');
    }
    return { w: width, h, d };
  }

  function svg(P, fills, o = {}) {
    const strong = o.strong || new Set(), t = o.titles || [];
    const path = (i, extra) => P.d[i] ? `<path d="${P.d[i]}" fill="${fills[i] || '#EDEDED'}"${extra}>${t[i] ? `<title>${esc(t[i])}</title>` : ''}</path>` : '';
    return `<svg class="${o.cls || 'mm'}" viewBox="0 0 ${P.w} ${P.h}" role="img" aria-label="${esc(o.label || '')}" preserveAspectRatio="xMidYMid meet">`
      + `<g stroke="#fff" stroke-width="${o.thin ? .6 : 1}" stroke-linejoin="round">${P.d.map((_, i) => strong.has(i) ? '' : path(i, '')).join('')}</g>`
      + `<g stroke="#2A2E2E" stroke-width="2.2" stroke-linejoin="round">${[...strong].map(i => path(i, '')).join('')}</g></svg>`;
  }

  return { project, svg };
});
