/* PR Data Observatory core: measuring on the map (Tools › Map tools › Measure distance and area, decision 97 step 2; docs/measure.md). No page state: points in, numbers out.

     Measure.lineKm(path)        the length of a path of [lng, lat] points, in km
     Measure.areaKm2(path)       the area of the polygon a path outlines (closed or not), in km²
     Measure.perimeterKm(path)   the length of its edge, closing it
     Measure.polygon(path)       the GeoJSON Polygon of a path (closed), for Study areas
     Measure.crosses(path)       whether two edges of the polygon cross (its area is then not meaningful)
     Measure.units(km2)          { km2, ha, cuerdas, acres, m2 }: an area in the units people in Puerto Rico use
     Measure.CUERDA_M2           3,930.395625 m², the cuerda of the Ley de Pesas y Medidas (Ley 145 de 1968, sección 3; 23 L.P.R.A. § 903)

   Distances follow the globe (the haversine formula on a sphere of the Earth's mean radius): within about 0.3% of the distance on the ellipsoid. Areas use the flat
   projection Core.study.areaKm2 uses (111.32 km per degree of longitude times the cosine of the latitude, 110.574 km per degree of latitude), so an area drawn here
   has the same size in Study areas; across an area of Puerto Rico's size it is within about 0.3% too. */
(function (name, root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api; else { root.Core = root.Core || {}; root.Core[name] = api; }
})('measure', typeof window !== 'undefined' ? window : globalThis, function () {
  'use strict';
  const KY = 110.574, KX0 = 111.32, CUERDA_M2 = 3930.395625, ACRE_M2 = 4046.8564224;
  const rad = (d) => d * Math.PI / 180;
  const open = (path) => path.length > 1 && path[0][0] === path[path.length - 1][0] && path[0][1] === path[path.length - 1][1] ? path.slice(0, -1) : path.slice();
  const midLat = (path) => { let lo = Infinity, hi = -Infinity; for (const p of path) { if (p[1] < lo) lo = p[1]; if (p[1] > hi) hi = p[1]; } return (lo + hi) / 2; };
  const R = 6371.0088;   // the mean radius of the Earth (IUGG), km
  function segKm(a, b) { const dl = rad(b[1] - a[1]), dg = rad(b[0] - a[0]), h = Math.sin(dl / 2) ** 2 + Math.cos(rad(a[1])) * Math.cos(rad(b[1])) * Math.sin(dg / 2) ** 2; return 2 * R * Math.asin(Math.min(1, Math.sqrt(h))); }   // haversine
  function lineKm(path) { let s = 0; for (let i = 1; i < path.length; i++) s += segKm(path[i - 1], path[i]); return s; }
  function perimeterKm(path) { const p = open(path); return p.length < 2 ? 0 : lineKm(p) + (p.length > 2 ? segKm(p[p.length - 1], p[0]) : 0); }
  function areaKm2(path) {
    const p = open(path); if (p.length < 3) return 0;
    const kx = KX0 * Math.cos(rad(midLat(p)));
    let s = 0; for (let i = 0, j = p.length - 1; i < p.length; j = i++) s += (p[j][0] * kx) * (p[i][1] * KY) - (p[i][0] * kx) * (p[j][1] * KY);
    return Math.abs(s) / 2;
  }
  function polygon(path) { const p = open(path); return { type: 'Polygon', coordinates: [[...p.map(q => [q[0], q[1]]), [p[0][0], p[0][1]]]] }; }
  // Two edges cross when each one's ends lie on opposite sides of the other; edges that share a corner do not count.
  const side = (a, b, c) => Math.sign((b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0]));
  function crosses(path) {
    const p = open(path), n = p.length; if (n < 4) return false;
    for (let i = 0; i < n; i++) {
      const a = p[i], b = p[(i + 1) % n];
      for (let j = i + 2; j < n; j++) {
        if (i === 0 && j === n - 1) continue;   // the closing edge shares the first corner
        const c = p[j], d = p[(j + 1) % n];
        if (side(a, b, c) * side(a, b, d) < 0 && side(c, d, a) * side(c, d, b) < 0) return true;
      }
    }
    return false;
  }
  const units = (km2) => ({ km2, m2: km2 * 1e6, ha: km2 * 100, cuerdas: km2 * 1e6 / CUERDA_M2, acres: km2 * 1e6 / ACRE_M2 });
  return { lineKm, areaKm2, perimeterKm, polygon, crosses, units, CUERDA_M2, ACRE_M2 };
});
