/* PR Data Observatory: routing that follows roads, in the browser.
   Reads data/roads.bin (built by roads.py from OpenStreetMap, ODbL): a directed graph of Puerto Rico's drivable roads.
   The build snaps every transit route to it; this is the same router, so a planned route lines up with the published ones.

     const roads = await Roads.load('data/roads.bin');
     roads.path([[lng, lat], [lng, lat], ...])  ->  { coords, meters, secs, legs: [{ok, meters, secs}], legAt: [index in coords where each leg starts], allOnRoads }

   Speeds are planning speeds by road class (only their ratios decide which way is "fastest"); the time is indicative:
   it counts neither stops nor traffic. File layout is documented in roads.py. */

const Roads = (() => {
  const Q = 1e5, CELL = 0.002;
  const SPEED_MS = [90, 55, 75, 45, 55, 40, 48, 35, 40, 30, 35, 25, 12, 12, 40].map(k => k / 3.6);   // same order as roads.py CLASSES
  const MAX_MS = Math.max(...SPEED_MS);
  const KX = (lat) => Math.cos(lat * Math.PI / 180) * 111320, KY = 110574;

  // a binary min-heap of (priority, node) pairs; stale entries are skipped when popped
  class Heap {
    constructor() { this.p = []; this.v = []; }
    get size() { return this.p.length; }
    push(p, v) {
      const P = this.p, V = this.v; let i = P.length; P.push(p); V.push(v);
      while (i > 0) { const j = (i - 1) >> 1; if (P[j] <= p) break; P[i] = P[j]; V[i] = V[j]; i = j; }
      P[i] = p; V[i] = v;
    }
    pop() {
      const P = this.p, V = this.v, top = [P[0], V[0]], lp = P.pop(), lv = V.pop(), n = P.length;
      if (n) { let i = 0; for (;;) { let c = 2 * i + 1; if (c >= n) break; if (c + 1 < n && P[c + 1] < P[c]) c++; if (P[c] >= lp) break; P[i] = P[c]; V[i] = V[c]; i = c; } P[i] = lp; V[i] = lv; }
      return top;
    }
  }

  class Roads {
    static async load(url = 'data/roads.bin') {
      return new Roads(await fetchRetry(url, (r) => r.arrayBuffer()));
    }

    constructor(buf) {
      const dv = new DataView(buf);
      if (dv.getUint32(0, true) !== 0x44525250) throw new Error('not a roads.bin file');   // "PRRD"
      const nN = dv.getUint32(8, true), nE = dv.getUint32(12, true), nS = dv.getUint32(16, true);
      this.nN = nN; this.nE = nE;
      this.nodeXY = new Uint32Array(buf, 20, nN * 2);
      let off = 20 + nN * 8;
      this.eu = new Uint32Array(nE); this.ev = new Uint32Array(nE); this.len = new Uint16Array(nE);
      this.cls = new Uint8Array(nE); this.oneway = new Uint8Array(nE); this.shapeAt = new Uint32Array(nE + 1);
      for (let i = 0; i < nE; i++, off += 12) {
        this.eu[i] = dv.getUint32(off, true); this.ev[i] = dv.getUint32(off + 4, true); this.len[i] = dv.getUint16(off + 8, true);
        const fl = dv.getUint8(off + 10); this.cls[i] = fl & 15; this.oneway[i] = (fl >> 4) & 1;
        this.shapeAt[i + 1] = this.shapeAt[i] + dv.getUint8(off + 11);
      }
      this.shape = new Int16Array(buf, off, nS * 2);
      this.cost = new Float64Array(nE);   // seconds to drive the whole edge
      for (let i = 0; i < nE; i++) this.cost[i] = this.len[i] * 2 / SPEED_MS[this.cls[i]];
      // adjacency in compressed rows: node -> (neighbor, edge, traveled forward?)
      const deg = new Int32Array(nN + 1);
      for (let i = 0; i < nE; i++) { deg[this.eu[i] + 1]++; if (!this.oneway[i]) deg[this.ev[i] + 1]++; }
      for (let i = 0; i < nN; i++) deg[i + 1] += deg[i];
      this.adjStart = deg; this.adjTo = new Int32Array(deg[nN]); this.adjEdge = new Int32Array(deg[nN]); this.adjFwd = new Uint8Array(deg[nN]);
      const fill = deg.slice(0, nN);
      for (let i = 0; i < nE; i++) {
        const u = this.eu[i], v = this.ev[i];
        let k = fill[u]++; this.adjTo[k] = v; this.adjEdge[k] = i; this.adjFwd[k] = 1;
        if (!this.oneway[i]) { k = fill[v]++; this.adjTo[k] = u; this.adjEdge[k] = i; this.adjFwd[k] = 0; }
      }
      this.grid = null;   // the snapping index is built the first time it is needed
      this.gScore = new Float64Array(nN).fill(Infinity);
      this.prevNode = new Int32Array(nN); this.prevEdge = new Int32Array(nN); this.prevHow = new Uint8Array(nN);
    }

    lonOf(n) { return this.nodeXY[n * 2] / Q - 68; }
    latOf(n) { return this.nodeXY[n * 2 + 1] / Q + 17; }

    /** Points of edge e as a flat [lng, lat, lng, lat, ...] array, from its u end to its v end. */
    poly(e) {
      const u = this.eu[e], v = this.ev[e];
      let x = this.nodeXY[u * 2], y = this.nodeXY[u * 2 + 1];
      const out = [x / Q - 68, y / Q + 17];
      for (let k = this.shapeAt[e]; k < this.shapeAt[e + 1]; k++) { x += this.shape[k * 2]; y += this.shape[k * 2 + 1]; out.push(x / Q - 68, y / Q + 17); }
      out.push(this.nodeXY[v * 2] / Q - 68, this.nodeXY[v * 2 + 1] / Q + 17);
      return out;
    }

    _buildGrid() {
      const g = new Map(), add = (lon, lat, e) => { const k = Math.floor((lon + 70) / CELL) * 2048 + Math.floor((lat - 17) / CELL); const a = g.get(k); if (!a) g.set(k, [e]); else if (a[a.length - 1] !== e) a.push(e); };
      for (let e = 0; e < this.nE; e++) {
        const p = this.poly(e);
        add(p[0], p[1], e);
        for (let i = 2; i < p.length; i += 2) {
          const steps = Math.min(40, Math.floor(Math.max(Math.abs(p[i] - p[i - 2]), Math.abs(p[i + 1] - p[i - 1])) / (CELL / 2)));   // long straight pieces cross cells that hold none of their points
          for (let s = 1; s < steps; s++) add(p[i - 2] + (p[i] - p[i - 2]) * s / steps, p[i - 1] + (p[i + 1] - p[i - 1]) * s / steps, e);
          add(p[i], p[i + 1], e);
        }
      }
      this.grid = g;
    }

    _project(lng, lat, e) {
      const p = this.poly(e), kx = KX(lat);
      let best = null, run = 0, total = 0;
      const segLen = [];
      for (let i = 0; i + 3 < p.length; i += 2) { const l = Math.hypot((p[i + 2] - p[i]) * kx, (p[i + 3] - p[i + 1]) * KY); segLen.push(l); total += l; }
      for (let j = 0, i = 0; i + 3 < p.length; i += 2, j++) {
        const ax = (p[i] - lng) * kx, ay = (p[i + 1] - lat) * KY, dx = (p[i + 2] - p[i]) * kx, dy = (p[i + 3] - p[i + 1]) * KY, l2 = dx * dx + dy * dy;
        const t = l2 === 0 ? 0 : Math.max(0, Math.min(1, -(ax * dx + ay * dy) / l2)), d = Math.hypot(ax + t * dx, ay + t * dy);
        if (!best || d < best.dist) best = { edge: e, dist: d, along: run + t * segLen[j], total, lng: p[i] + t * (p[i + 2] - p[i]), lat: p[i + 1] + t * (p[i + 3] - p[i + 1]) };
        run += segLen[j];
      }
      return best;
    }

    /** The nearest point on a road within maxM meters of the given position, or null. */
    snap(lng, lat, maxM = 300) {
      if (!this.grid) this._buildGrid();
      const cx = Math.floor((lng + 70) / CELL), cy = Math.floor((lat - 17) / CELL), r = maxM <= 220 ? 1 : maxM <= 450 ? 2 : maxM <= 900 ? 4 : 8;
      const seen = new Set(); let best = null;
      for (let dx = -r; dx <= r; dx++) for (let dy = -r; dy <= r; dy++) {
        const a = this.grid.get((cx + dx) * 2048 + cy + dy); if (!a) continue;
        for (const e of a) { if (seen.has(e)) continue; seen.add(e); const p = this._project(lng, lat, e); if (!best || p.dist < best.dist) best = p; }
      }
      return best && best.dist <= maxM ? best : null;
    }

    /** Points of edge e between two distances along it (meters of its drawn length), in the direction lo -> hi, or hi -> lo when reversed. */
    _slice(e, a, lo, hi, reverse) {
      const p = this.poly(e), kx = KX(a.lat);
      const out = []; let run = 0;
      const at = (s, i, t) => [p[i] + t * (p[i + 2] - p[i]), p[i + 1] + t * (p[i + 3] - p[i + 1])];
      let started = false;
      for (let i = 0; i + 3 < p.length; i += 2) {
        const l = Math.hypot((p[i + 2] - p[i]) * kx, (p[i + 3] - p[i + 1]) * KY), s0 = run, s1 = run + l;
        if (s1 >= lo && s0 <= hi) {
          if (!started) { out.push(at(lo, i, l ? Math.max(0, (lo - s0) / l) : 0)); started = true; }
          if (s1 <= hi) out.push([p[i + 2], p[i + 3]]); else { out.push(at(hi, i, l ? (hi - s0) / l : 0)); break; }
        }
        run = s1;
      }
      if (!out.length) out.push([p[0], p[1]]);
      return reverse ? out.reverse() : out;
    }

    /** Fastest road path between two snapped points: {secs, meters, coords: [[lng, lat], ...]} or null. */
    route(a, b) {
      const spd = (e) => SPEED_MS[this.cls[e]], eCost = this.cost;
      const ea = a.edge, eb = b.edge, fa = a.along / (a.total || 1), fb = b.along / (b.total || 1);
      if (ea === eb && (fb >= fa || !this.oneway[ea])) {   // both on one road piece
        const lo = Math.min(a.along, b.along), hi = Math.max(a.along, b.along), secs = Math.abs(fb - fa) * eCost[ea];
        return { secs, metres: hi - lo, coords: this._slice(ea, a, lo, hi, b.along < a.along) };
      }
      const g = this.gScore, touched = [], heap = new Heap();
      const bx = b.lng, by = b.lat, kx = KX(by);
      const h = (n) => Math.hypot((this.lonOf(n) - bx) * kx, (this.latOf(n) - by) * KY) * .995 / MAX_MS;
      const relax = (n, cost, how, prevN, prevE) => { if (cost < g[n]) { if (g[n] === Infinity) touched.push(n); g[n] = cost; this.prevNode[n] = prevN; this.prevEdge[n] = prevE; this.prevHow[n] = how; heap.push(cost + h(n), n); } };
      relax(this.ev[ea], (1 - fa) * eCost[ea], 1, -1, ea);   // leave the first road piece at its v end (how = 1) ...
      if (!this.oneway[ea]) relax(this.eu[ea], fa * eCost[ea], 2, -1, ea);   // ... or at its u end (how = 2)
      const tails = new Map();   // node -> [seconds from that node to b, 1 = arrive from the u end, 2 = from the v end]
      tails.set(this.eu[eb], [fb * eCost[eb], 1]);
      if (!this.oneway[eb]) { const t = [(1 - fb) * eCost[eb], 2], old = tails.get(this.ev[eb]); if (!old || t[0] < old[0]) tails.set(this.ev[eb], t); }
      let best = Infinity, bestNode = -1;
      while (heap.size) {
        const [f, n] = heap.pop(), d = g[n];
        if (f - h(n) > d + 1e-9) continue;   // stale entry
        if (f >= best) break;
        const tl = tails.get(n); if (tl && d + tl[0] < best) { best = d + tl[0]; bestNode = n; }
        for (let k = this.adjStart[n]; k < this.adjStart[n + 1]; k++) { const e = this.adjEdge[k]; relax(this.adjTo[k], d + eCost[e], 3 + this.adjFwd[k], n, e); }
      }
      let out = null;
      if (bestNode >= 0) {
        const seq = []; let n = bestNode, first;
        for (;;) { if (this.prevNode[n] < 0) { first = this.prevHow[n]; break; } seq.push([this.prevEdge[n], this.prevHow[n] === 4]); n = this.prevNode[n]; }
        seq.reverse();
        let geo = first === 1 ? this._slice(ea, a, a.along, a.total) : this._slice(ea, a, 0, a.along, true);
        for (const [e, fwd] of seq) { const p = this.poly(e), pts = []; for (let i = 0; i < p.length; i += 2) pts.push([p[i], p[i + 1]]); geo = geo.concat(fwd ? pts : pts.reverse()); }
        geo = geo.concat(tails.get(bestNode)[1] === 1 ? this._slice(eb, b, 0, b.along) : this._slice(eb, b, b.along, b.total, true));
        const coords = [geo[0]]; let metres = 0;
        for (let i = 1; i < geo.length; i++) { const q = coords[coords.length - 1]; if (geo[i][0] !== q[0] || geo[i][1] !== q[1]) { metres += Math.hypot((geo[i][0] - q[0]) * KX(q[1]), (geo[i][1] - q[1]) * KY); coords.push(geo[i]); } }
        out = { secs: best, metres, coords };
      }
      for (const n of touched) g[n] = Infinity;
      return out;
    }

    /** A road path through the given [lng, lat] points, in order. A leg that cannot follow roads (a point far from any road,
     *  or no connection) is drawn straight and marked ok: false, so the caller can say so. */
    path(points, { maxSnap = 500 } = {}) {
      const snaps = points.map(p => this.snap(p[0], p[1], maxSnap));
      const coords = [], legs = [], legAt = []; let metres = 0, secs = 0;
      for (let i = 1; i < points.length; i++) {
        const a = points[i - 1], b = points[i], sa = snaps[i - 1], sb = snaps[i], straight = Math.hypot((b[0] - a[0]) * KX(a[1]), (b[1] - a[1]) * KY);
        let r = sa && sb ? this.route(sa, sb) : null;
        if (r && r.metres > 4 * straight + 1500) r = null;   // a detour this long means the roads do not really connect the two
        let seg, leg;
        if (r) { seg = [[a[0], a[1]], ...r.coords, [b[0], b[1]]]; leg = { ok: true, metres: r.metres + (sa.dist || 0) + (sb.dist || 0), secs: r.secs + ((sa.dist || 0) + (sb.dist || 0)) / 1.4 }; }
        else { seg = [[a[0], a[1]], [b[0], b[1]]]; leg = { ok: false, metres: straight, secs: straight / 8 }; }
        legs.push(leg); legAt.push(Math.max(0, coords.length - 1)); metres += leg.metres; secs += leg.secs;
        for (const p of seg) { const q = coords[coords.length - 1]; if (!q || q[0] !== p[0] || q[1] !== p[1]) coords.push(p); }
      }
      return { coords: coords.map(p => [+p[0].toFixed(5), +p[1].toFixed(5)]), metres, secs, legs, legAt, allOnRoads: legs.every(l => l.ok) };
    }
  }
  return Roads;
})();
if (typeof module !== 'undefined') module.exports = { Roads };
