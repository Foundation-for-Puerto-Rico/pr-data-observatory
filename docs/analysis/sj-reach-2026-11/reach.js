/* San Juan reach prototype: the street area reached in a time budget from one point, by mode, on roads.bin (site/js/roads.js).
   Used by index.html and check.js. Each mode is a Dijkstra over the road graph in seconds; public transport is walk + the ATI timetable (connection scan)
   + walk. Area = 25 m cells within OFF_M of a reached stretch of road, or less when less time is left (a walk off the road). Speeds are assumptions: see MODES. */
(function (root) {
  'use strict';
  const KMH = (k) => k / 3.6;
  const ROAD_KMH = [90, 55, 75, 45, 55, 40, 48, 35, 40, 30, 35, 25, 12, 12, 40];   // roads.py SPEED_KMH: free-flow planning speeds by class
  const NO_MOTORWAY = (c) => c === 0 || c === 1;
  const BUSWAY = 14;
  const P = { SNAP_M: 300, OFF_M: 50, CELL_M: 25, STEP_M: 20, WALK_MS: KMH(4.8) };

  // id, legend, meters-per-second of an edge class (null: not allowed), follows one-way rules
  const MODES = [
    { id: 'walk', es: 'A pie', note: '4.8 km/h', color: '#7cc3e8', ms: (c) => NO_MOTORWAY(c) ? null : P.WALK_MS, oneway: false },
    { id: 'transit', es: 'Transporte público', note: 'horario ATI', color: '#3fa7a0', transit: true },
    { id: 'car_rush', es: 'Carro, hora pico', note: 'libre × factor', color: '#e0664f', ms: (c, o) => c === BUSWAY ? null : KMH(ROAD_KMH[c]) * o.rush, oneway: true },
    { id: 'scooter', es: 'E-scooter', note: '12 km/h', color: '#e8c33f', ms: (c) => NO_MOTORWAY(c) ? null : KMH(12), oneway: true },
    { id: 'bike', es: 'Bicicleta', note: '14.5 km/h', color: '#5fb052', ms: (c) => NO_MOTORWAY(c) ? null : KMH(14.5), oneway: true },
    { id: 'car_free', es: 'Carro, calles vacías', note: 'velocidad libre', color: '#9a7fd1', ms: (c) => c === BUSWAY ? null : KMH(ROAD_KMH[c]), oneway: true, theory: true },
  ];

  // adjacency of a mode: node -> (neighbor, edge, seconds), kept per graph and mode
  const adjCache = new WeakMap();
  function adjacency(R, mode, o) {
    const key = mode.id + (mode.id === 'car_rush' ? o.rush : '');
    let m = adjCache.get(R); if (!m) adjCache.set(R, m = new Map());
    if (m.has(key)) return m.get(key);
    const ms = new Float64Array(R.nE), deg = new Int32Array(R.nN + 1);
    for (let e = 0; e < R.nE; e++) { ms[e] = mode.ms(R.cls[e], o) || 0; if (!ms[e]) continue; deg[R.eu[e] + 1]++; if (!(mode.oneway && R.oneway[e])) deg[R.ev[e] + 1]++; }
    for (let i = 0; i < R.nN; i++) deg[i + 1] += deg[i];
    const to = new Int32Array(deg[R.nN]), ed = new Int32Array(deg[R.nN]), sec = new Float32Array(deg[R.nN]), fill = deg.slice(0, R.nN);
    for (let e = 0; e < R.nE; e++) {
      if (!ms[e]) continue; const s = R.len[e] * 2 / ms[e];
      let k = fill[R.eu[e]]++; to[k] = R.ev[e]; ed[k] = e; sec[k] = s;
      if (!(mode.oneway && R.oneway[e])) { k = fill[R.ev[e]]++; to[k] = R.eu[e]; ed[k] = e; sec[k] = s; }
    }
    const A = { start: deg, to, ed, sec, ms }; m.set(key, A); return A;
  }

  function dijkstra(R, A, sources, budget) {   // sources: [[node, seconds]] -> Map node -> seconds
    const t = new Map(), hp = [], hv = [];
    const push = (p, v) => { let i = hp.length; hp.push(p); hv.push(v); while (i > 0) { const j = (i - 1) >> 1; if (hp[j] <= p) break; hp[i] = hp[j]; hv[i] = hv[j]; i = j; } hp[i] = p; hv[i] = v; };
    const pop = () => { const p = hp[0], v = hv[0], lp = hp.pop(), lv = hv.pop(), n = hp.length; if (n) { let i = 0; for (;;) { let c = 2 * i + 1; if (c >= n) break; if (c + 1 < n && hp[c + 1] < hp[c]) c++; if (hp[c] >= lp) break; hp[i] = hp[c]; hv[i] = hv[c]; i = c; } hp[i] = lp; hv[i] = lv; } return [p, v]; };
    const relax = (n, s) => { if (s <= budget && s < (t.has(n) ? t.get(n) : Infinity)) { t.set(n, s); push(s, n); } };
    for (const [n, s] of sources) relax(n, s);
    while (hp.length) { const [s, n] = pop(); if (s > t.get(n)) continue; for (let k = A.start[n]; k < A.start[n + 1]; k++) relax(A.to[k], s + A.sec[k]); }
    return t;
  }

  // the two ends of the snapped edge, reached by walking to the road and then along it at the mode's speed (either way: ponytail, ignores one-way on the first edge)
  function startNodes(s, A) {
    const ms = A.ms[s.edge] || P.WALK_MS, walk = s.dist / P.WALK_MS, a = s.along / s.total * s.len;
    return [[s.u, walk + a / ms], [s.v, walk + (s.len - a) / ms]];
  }
  function snap(R, lng, lat) {
    const s = R.snap(lng, lat, P.SNAP_M); if (!s) return null;
    return { ...s, u: R.eu[s.edge], v: R.ev[s.edge], len: R.len[s.edge] * 2 };
  }

  // cells within reach: along every adjacency entry out of a reached node, stamping as far as the time lasts
  function area(R, A, times, budget, lat0) {
    const kx = Math.cos(lat0 * Math.PI / 180) * 111320, ky = 110574, C = P.CELL_M, cells = new Map();
    const stamp = (lng, lat, r, t) => {   // ponytail: a cell takes the time of the road point that reaches it, not plus the walk off the road
      const x = lng * kx, y = lat * ky, i0 = Math.floor((x - r) / C), i1 = Math.floor((x + r) / C), j0 = Math.floor((y - r) / C), j1 = Math.floor((y + r) / C);
      for (let i = i0; i <= i1; i++) for (let j = j0; j <= j1; j++) { const dx = (i + 0.5) * C - x, dy = (j + 0.5) * C - y; if (dx * dx + dy * dy <= r * r + C * C / 2) { const key = i * 1e7 + j, old = cells.get(key); if (old === undefined || t < old) cells.set(key, t); } }
    };
    for (const [n, t0] of times) {
      stamp(R.lonOf(n), R.latOf(n), Math.min(P.OFF_M, (budget - t0) * P.WALK_MS), t0);
      for (let k = A.start[n]; k < A.start[n + 1]; k++) {
        const e = A.ed[k], p = R.poly(e), fwd = R.eu[e] === n, pts = [];
        for (let i = 0; i < p.length; i += 2) pts.push([p[i], p[i + 1]]);
        if (!fwd) pts.reverse();
        const per = A.sec[k] / (R.len[e] * 2);   // seconds per meter on this edge
        let run = 0;
        for (let i = 1; i < pts.length; i++) {
          const l = Math.hypot((pts[i][0] - pts[i - 1][0]) * kx, (pts[i][1] - pts[i - 1][1]) * ky), steps = Math.max(1, Math.ceil(l / P.STEP_M));
          for (let q = 1; q <= steps; q++) {
            const at = t0 + (run + l * q / steps) * per, left = budget - at; if (left < 0) { i = pts.length; break; }
            const f = q / steps; stamp(pts[i - 1][0] + (pts[i][0] - pts[i - 1][0]) * f, pts[i - 1][1] + (pts[i][1] - pts[i - 1][1]) * f, Math.min(P.OFF_M, left * P.WALK_MS), at);
          }
          run += l;
        }
      }
    }
    // km², and the cells as arrays for drawing: center lng, lat and the second each is first reached
    const n = cells.size, x = new Float64Array(n), y = new Float64Array(n), t = new Float32Array(n); let k = 0;
    for (const [key, s] of cells) { const i = Math.floor(key / 1e7), j = key - i * 1e7; x[k] = (i + 0.5) * C / kx; y[k] = (j + 0.5) * C / ky; t[k++] = s; }
    return { km2: n * C * C / 1e6, cells: { x, y, t, cellM: C } };
  }

  // public transport: walk to stops, connection scan over the window, walk from every stop reached
  function transit(R, s, TT, budget, stopNode) {
    const W = adjacency(R, MODES[0], {}), walk = dijkstra(R, W, startNodes(s, W), budget);
    const arr = new Float64Array(TT.stops.length).fill(Infinity), boarded = new Uint8Array(1 + Math.max(0, ...TT.connections.map(c => c[4])));
    const foot = new Map(); for (const [a, b, w] of TT.footpaths) { (foot.get(a) || foot.set(a, []).get(a)).push([b, w]); (foot.get(b) || foot.set(b, []).get(b)).push([a, w]); }
    TT.stops.forEach((_, i) => { const sn = stopNode[i]; if (sn && walk.has(sn.node)) arr[i] = walk.get(sn.node) + sn.walk; });
    for (const [a, b, dep, at, trip] of TT.connections) {
      if (dep > budget) break;
      if (!boarded[trip] && arr[a] > dep) continue;
      boarded[trip] = 1;
      if (at < arr[b]) { arr[b] = at; for (const [c, w] of foot.get(b) || []) if (at + w < arr[c]) arr[c] = at + w; }
    }
    const sources = [...walk];
    arr.forEach((t, i) => { if (t <= budget && stopNode[i]) sources.push([stopNode[i].node, t + stopNode[i].walk]); });
    return { times: dijkstra(R, W, sources, budget), A: W, stopsReached: arr.filter(t => t <= budget).length };
  }

  /** km² reached in `minutes` from (lng, lat) by every mode. o.rush: car speed factor at rush hour. TT: timetable.json. stopNode: from stopNodes(). */
  function reachAll(R, lng, lat, minutes, o, TT, stopNode) {
    const s = snap(R, lng, lat); if (!s) return null;
    const budget = minutes * 60;
    const out = MODES.map(m => {
      if (m.transit) { const r = transit(R, s, TT, budget, stopNode); return { ...m, ...area(R, r.A, r.times, budget, lat), stops: r.stopsReached }; }
      const A = adjacency(R, m, o);
      return { ...m, ...area(R, A, dijkstra(R, A, startNodes(s, A), budget), budget, lat) };
    });
    return { snapM: s.dist, modes: out };
  }
  function stopNodes(R, TT) {   // each stop's nearest walkable road node and the seconds to walk there (straight line)
    return TT.stops.map(([x, y]) => { const s = snap(R, x, y); if (!s) return null; const a = s.along / s.total * s.len, near = a < s.len / 2;
      return { node: near ? s.u : s.v, walk: (s.dist + (near ? a : s.len - a)) / P.WALK_MS }; });
  }

  const api = { MODES, P, reachAll, stopNodes };
  if (typeof module !== 'undefined') module.exports = api; else root.Reach = api;
})(typeof window !== 'undefined' ? window : globalThis);
