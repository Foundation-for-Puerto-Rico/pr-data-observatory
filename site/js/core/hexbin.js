/* PR Data Observatory core: hexagon binning of points (plan item 6, B2). A point layer drawn as pins says where each place is; counted in hexagons it says how many are where, and the user's own filters
   (a category, a confidence) can be applied first, because the counting is done in the browser, on the points that pass the filter.

   The hexagons are all the same size on the ground: points are projected with a Lambert azimuthal equal-area projection centred on Puerto Rico, in which equal areas on the plane are equal areas on
   the ground, and the hexagons are laid on the plane. So a count per hexagon is also a density: no cell has more room than another. (The projection is exact on a sphere of the earth's mean radius;
   on the real, slightly flattened earth the areas are right to about 0.3%.)

     Hexbin.bin(points, { area })      points are { lat, lng, w? }; area is the area of one hexagon in km² (default 10). Returns { km2, size, cells: [{ id, q, r, n, w }] }, one cell for each hexagon that holds a point
     Hexbin.features(bins)             GeoJSON polygons of those cells, with their counts n and weights w in the properties
     Hexbin.corners(q, r, size)        the six corners of one hexagon, as [lat, lng]
     Hexbin.project(lat, lng), Hexbin.unproject(x, y)    km east and north of the centre, and back
   Cell ids are "q,r" (axial coordinates); they depend on `area`, so a count at one size is never compared with a count at another. */
(function (name, root, factory) {
  const api = factory(root);
  if (typeof module === 'object' && module.exports) module.exports = api; else { root.Core = root.Core || {}; root.Core[name] = api; }
})('hexbin', typeof window !== 'undefined' ? window : globalThis, function () {
  'use strict';
  const R = 6371.0088;   // km, the mean radius of the earth
  const rad = (d) => d * Math.PI / 180, deg = (r) => r * 180 / Math.PI;
  const LAT0 = rad(18.2), LON0 = rad(-66.45), S0 = Math.sin(LAT0), C0 = Math.cos(LAT0);   // the centre of Puerto Rico

  function project(lat, lng) {
    const f = rad(lat), l = rad(lng) - LON0, k = Math.sqrt(2 / (1 + S0 * Math.sin(f) + C0 * Math.cos(f) * Math.cos(l)));
    return [R * k * Math.cos(f) * Math.sin(l), R * k * (C0 * Math.sin(f) - S0 * Math.cos(f) * Math.cos(l))];
  }
  function unproject(x, y) {
    const rho = Math.hypot(x, y); if (!rho) return [deg(LAT0), deg(LON0)];
    const c = 2 * Math.asin(rho / (2 * R)), sc = Math.sin(c), cc = Math.cos(c);
    return [deg(Math.asin(cc * S0 + y * sc * C0 / rho)), deg(LON0 + Math.atan2(x * sc, rho * C0 * cc - y * S0 * sc))];
  }

  const size = (km2) => Math.sqrt(2 * km2 / (3 * Math.sqrt(3)));   // the corner-to-centre length of a regular hexagon of this area
  function cellAt(x, y, s) {   // axial coordinates of the pointy-topped hexagon that holds the point (x, y)
    const q = (Math.sqrt(3) / 3 * x - y / 3) / s, r = (2 / 3 * y) / s, t = -q - r;
    let rq = Math.round(q), rr = Math.round(r), rt = Math.round(t);
    const dq = Math.abs(rq - q), dr = Math.abs(rr - r), dt = Math.abs(rt - t);
    if (dq > dr && dq > dt) rq = -rr - rt; else if (dr > dt) rr = -rq - rt;
    return [rq + 0, rr + 0];   // + 0 turns a negative zero into zero, so ids are the same whichever way a point rounds
  }
  const centre = (q, r, s) => [s * Math.sqrt(3) * (q + r / 2), s * 1.5 * r];
  const corners = (q, r, s) => { const [cx, cy] = centre(q, r, s); return Array.from({ length: 6 }, (_, i) => { const a = rad(60 * i - 30); return unproject(cx + s * Math.cos(a), cy + s * Math.sin(a)); }); };

  function bin(points, o = {}) {
    const km2 = o.area || 10, s = size(km2), cells = new Map();
    for (const p of points) {
      if (p.lat == null || p.lng == null) continue;
      const [x, y] = project(p.lat, p.lng), [q, r] = cellAt(x, y, s), id = q + ',' + r;
      let c = cells.get(id); if (!c) cells.set(id, c = { id, q, r, n: 0, w: 0 });
      c.n++; c.w += p.w == null ? 1 : p.w;
    }
    return { km2, size: s, cells: [...cells.values()] };
  }
  function features(bins) {
    return bins.cells.map(c => { const ring = corners(c.q, c.r, bins.size).map(([la, lo]) => [lo, la]); ring.push(ring[0]); return { type: 'Feature', properties: { id: c.id, n: c.n, w: c.w }, geometry: { type: 'Polygon', coordinates: [ring] } }; });
  }

  return { project, unproject, size, bin, features, corners };
});
