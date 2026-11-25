/* PR Data Observatory: the Slope and Contour lines layers of the 2D map (GIS tools step 2, HANDOFF decision 93; docs/slope.md). app.js loads this file and its
   Spanish (I18N.load('terrain')) the first time either layer is switched on (terrainLoad), so the map's first load does not carry them (docs/performance.md).
   - Slope: slope.py's image (data/slope_surface.png, the mean slope of each block of about 60 m from the USGS 10 m elevation model), read with core/surfscale.js like
     the heat image, on its fixed scale from 0% to 60%. Its legend's slider shows only the ground at or above a slope (a threshold: GIS "reclassify").
   - Contour lines: drawn in the browser, tile by tile, from the terrain tiles the 3D view uses (AWS Terrain Tiles, Terrarium encoding; in Puerto Rico from USGS
     3DEP), by marching squares on each tile's heights. The interval follows the zoom (100 m, 50 m, 20 m, 10 m), every fifth line thicker. Nothing is stored. */
map.createPane('slope'); map.getPane('slope').style.zIndex = 352;            // under the landslide (353) and soil (356) layers
map.createPane('contours'); map.getPane('contours').style.zIndex = 405;      // over the area shading (overlay pane, 400), under markers
map.getPane('contours').style.pointerEvents = 'none';

// ── Slope ────────────────────────────────────────────────────────────────────
let slopeO = null, slopeLayer = null, slopeP = null;
const SLOPE_MARKS = [[15, 'terraces or special design'], [30, 'too steep to build without engineering']];
function slopeOpen() {
  return slopeP || (slopeP = (async () => {
    if (!(window.Core && Core.surfscale)) await addJs('js/core/surfscale.js?v=4');
    const m = await getJson('data/slope_surface.json', T('slope'));
    const o = await Core.surfscale.open('data/' + m.image, m); o.meta = m; return o;
  })().catch(e => { slopeP = null; throw e; }));
}
async function slopeOn() {
  const o = slopeO = await slopeOpen(), [w, s, e, n] = o.meta.bounds;
  if (!slopeLayer) slopeLayer = L.imageOverlay('data/' + o.meta.image, [[s, w], [n, e]], { pane: 'slope', opacity: .75, interactive: false, attribution: T('Slope: USGS 3DEP') });
  if ($('#lySlope').checked) { slopeLayer.addTo(map); await slopePaint(); }
}
function slopeOff() { if (slopeLayer) map.removeLayer(slopeLayer); }
/** The image on its scale, with the threshold the legend's slider set; and the legend (called by surfscale.js when the slider is released). */
async function slopePaint() {
  const o = slopeO; if (!o || !slopeLayer) return;
  const sc = o.meta.scale;
  slopeLayer.setUrl(await o.paint(sc));
  const stops = sc.stops, pct = (v) => T('{v}%', { v: fmt(v, 0) });
  $('#slopeLegend').innerHTML = `<div data-surf-own="slopePaint"><div class="legend-title">${esc(T('Slope of the ground'))} <small>${esc(T('% (rise over run)'))}</small></div>`
    + `<div class="surf-bar" style="background:linear-gradient(90deg,${stops.join(',')})"></div>`
    + `<div class="surf-ticks"><span>${pct(sc.low)}</span><span>${pct(sc.centre)}</span><span>${esc(T('{v} or more', { v: pct(sc.high) }))}</span></div>`
    + o.threshold(sc.low, sc.high, 5, (v) => v == null ? T('All the land') : T('Only the land at {v} or steeper', { v: pct(v) }))
    + `<div class="note">${esc(SLOPE_MARKS.map(([v, what]) => T('{v}: {what}', { v: pct(v), what: T(what) })).join(' · '))}. ${esc(T('USGS 3DEP 10 m elevation, the mean slope of each block of about {m} m; Mona and Desecheo are not drawn. The share of steep land by barrio is in Explore (Environment and climate).', { m: fmt(o.meta.pixel_m, 0) }))}</div></div>`;
}
window.slopePaint = slopePaint;
/** The slope under a point, for the map's pop-up: from the image's step (within half a step, about 0.5%). */
function slopeAt(ll) {
  const o = slopeO; if (!o) return [];   // the same arithmetic as Core.study.raster (core/study.js), which this page has only with the Study areas view
  const [w, s, e, n] = o.meta.bounds, sc = o.meta.scale, my = (la) => Math.log(Math.tan(Math.PI / 4 + la * Math.PI / 360)), x = ll.lng, y = ll.lat;
  if (!(x >= w && x < e && y >= s && y < n)) return [];
  const c = Math.min(o.W - 1, Math.floor((x - w) / (e - w) * o.W)), r = Math.min(o.H - 1, Math.max(0, Math.floor((my(n) - my(y)) / (my(n) - my(s)) * o.H))), k = o.steps()[r * o.W + c];
  if (!k) return [];
  const val = sc.low + (k - 1) / (Core.surfscale.STEPS - 1) * (sc.high - sc.low);
  return [`<div class="pop-sec"><b>${esc(T('Slope of the ground'))}</b>: ${k === Core.surfscale.STEPS ? esc(T('{v} or more', { v: T('{v}%', { v: fmt(sc.high, 0) }) })) : esc(T('about {v}', { v: T('{v}%', { v: fmt(val, 0) }) }))}<br><small>${esc(T('Mean of the block of about 60 m under the point (USGS 3DEP 10 m).'))}</small></div>`];
}
window.slopeAt = slopeAt;

// ── Contour lines ────────────────────────────────────────────────────────────
const TERRARIUM = 'https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png', TERRAIN_MAX_Z = 15;
const contourStep = (z) => z <= 11 ? 100 : z === 12 ? 50 : z === 13 ? 20 : 10;   // meters between lines at a zoom; every fifth line is thicker
/** Heights (m) of a 256 x 256 Terrarium tile: (R x 256 + G + B / 256) - 32768. */
function heights(img) {
  const cv = document.createElement('canvas'); cv.width = cv.height = 256;
  const cx = cv.getContext('2d', { willReadFrequently: true }); cx.drawImage(img, 0, 0);
  const d = cx.getImageData(0, 0, 256, 256).data, h = new Float32Array(65536);
  for (let i = 0, p = 0; i < 65536; i++, p += 4) h[i] = d[p] * 256 + d[p + 1] + d[p + 2] / 256 - 32768;
  return h;
}
/** The contour segments of a height grid (N x N, values at pixel centers) at every multiple of `step` above 0, by marching squares (the saddle cases split by
    the cell's mean): [[level, x0, y0, x1, y1], ...] in pixels. Pure, so the tests run it. */
function marching(h, N, step) {
  const out = [];
  for (let r = 0; r < N - 1; r++) for (let c = 0; c < N - 1; c++) {
    const a = h[r * N + c], b = h[r * N + c + 1], d = h[(r + 1) * N + c], e = h[(r + 1) * N + c + 1];   // top-left, top-right, bottom-left, bottom-right
    const lo = Math.min(a, b, d, e), hi = Math.max(a, b, d, e);
    if (hi <= 0 || hi - lo < 1e-6) continue;
    for (let L = Math.max(step, Math.ceil(lo / step) * step); L <= hi; L += step) {
      if (L === lo) continue;
      const k = (a >= L ? 8 : 0) | (b >= L ? 4 : 0) | (e >= L ? 2 : 0) | (d >= L ? 1 : 0);
      if (k === 0 || k === 15) continue;
      const x0 = c + 0.5, y0 = r + 0.5, f = (p, q) => (L - p) / (q - p);
      const T_ = [x0 + f(a, b), y0], R_ = [x0 + 1, y0 + f(b, e)], B_ = [x0 + f(d, e), y0 + 1], L_ = [x0, y0 + f(a, d)];
      const seg = (p, q) => out.push([L, p[0], p[1], q[0], q[1]]);
      switch (k) {
        case 1: case 14: seg(L_, B_); break;
        case 2: case 13: seg(B_, R_); break;
        case 3: case 12: seg(L_, R_); break;
        case 4: case 11: seg(T_, R_); break;
        case 6: case 9: seg(T_, B_); break;
        case 7: case 8: seg(L_, T_); break;
        case 5: case 10: {
          const up = (a + b + d + e) / 4 >= L;
          if ((k === 5) === up) { seg(L_, T_); seg(B_, R_); } else { seg(L_, B_); seg(T_, R_); }
          break;
        }
      }
    }
  }
  return out;
}
const ContourLayer = L.GridLayer.extend({
  createTile(coords, done) {
    const tile = document.createElement('canvas'), ratio = Math.min(2, window.devicePixelRatio || 1);
    tile.width = tile.height = 256 * ratio;
    const img = new Image(); img.crossOrigin = 'anonymous';
    img.onload = () => {
      try {
        const step = contourStep(coords.z), segs = marching(heights(img), 256, step), cx = tile.getContext('2d');
        cx.scale(ratio, ratio); cx.lineCap = 'round';
        for (const major of [false, true]) {
          cx.beginPath();
          for (const [L0, x0, y0, x1, y1] of segs) if ((L0 % (step * 5) === 0) === major) { cx.moveTo(x0, y0); cx.lineTo(x1, y1); }
          cx.strokeStyle = major ? 'rgba(92,51,20,.85)' : 'rgba(92,51,20,.55)'; cx.lineWidth = major ? 1.3 : 0.6; cx.stroke();
        }
        done(null, tile);
      } catch (e) { done(e, tile); }
    };
    img.onerror = () => done(new Error('terrain tile'), tile);
    img.src = TERRARIUM.replace('{z}', coords.z).replace('{x}', coords.x).replace('{y}', coords.y);
    return tile;
  },
});
let contourLayer = null;
function contoursOn() {
  contourLayer = contourLayer || new ContourLayer({ pane: 'contours', maxNativeZoom: TERRAIN_MAX_Z, maxZoom: 20, minZoom: 9, bounds: [[17.8, -68.0], [18.6, -65.2]],
    attribution: T('Contour lines: AWS Terrain Tiles (USGS 3DEP)') });
  if ($('#lyContours').checked) { contourLayer.addTo(map); contourLegend(); map.on('zoomend', contourLegend); }
}
function contoursOff() { if (contourLayer) map.removeLayer(contourLayer); map.off('zoomend', contourLegend); }
function contourLegend() {
  const z = Math.round(map.getZoom()), step = contourStep(Math.min(z, TERRAIN_MAX_Z));
  $('#contourLegend').innerHTML = z < 9 ? `<div class="note">${esc(T('Zoom in to see the contour lines.'))}</div>`
    : `<div class="legend-title">${esc(T('Contour lines'))}</div><div class="row"><span class="sw line" style="border-top:1px solid rgba(92,51,20,.6)"></span>${esc(T('Every {m} m of height at this zoom', { m: step }))}</div>`
      + `<div class="row"><span class="sw line" style="border-top:2px solid rgba(92,51,20,.85)"></span>${esc(T('Every {m} m (thicker)', { m: step * 5 }))}</div>`
      + `<div class="note">${esc(T('Drawn in your browser from the terrain tiles of the 3D view (USGS 3DEP elevation in Puerto Rico). Zoom in for closer lines.'))}</div>`;
}
// ── Watersheds (watersheds.py; GIS tools step 3, docs/watersheds.md) ─────────
// The USGS subwatersheds (HUC-12) as outlines, and the main streams (5 km² or more of drainage) wider for larger rivers. The pop-up names the subwatershed
// under a click (shedAt, called by app.js), with its subbasin, area and residents. "What drains here" is in Tools › Map tools.
map.createPane('sheds'); map.getPane('sheds').style.zIndex = 404; map.getPane('sheds').style.pointerEvents = 'none';
let shedLayer = null, streamLayer = null, shedData = null, shedP = null;
const STREAM = '#1F78B4', SHED = '#0B3D5C';
function shedOpen() {
  return shedP || (shedP = Promise.all([getJson('data/watersheds.geojson', T('watersheds')), getJson('data/streams.geojson', T('streams'))]).then(([s, r]) => {
    shedData = { sheds: s, at: null };
    shedLayer = L.geoJSON(s, { pane: 'sheds', interactive: false, style: { color: SHED, weight: 1.2, opacity: .8, fill: false, dashArray: '4 3' } });
    streamLayer = L.geoJSON(r, { pane: 'sheds', interactive: false, style: (f) => ({ color: STREAM, opacity: .85, weight: f.properties.km2 >= 200 ? 3 : f.properties.km2 >= 50 ? 2.2 : f.properties.km2 >= 20 ? 1.5 : 1 }),
      attribution: T('Watersheds and streams: USGS WBD, NHDPlus HR') });
  }).catch(e => { shedP = null; throw e; }));
}
async function shedsOn() {
  await shedOpen();
  if (!$('#lyWatersheds').checked) return;
  shedLayer.addTo(map); streamLayer.addTo(map);
  const n = shedData.sheds.features.length;
  $('#shedLegend').innerHTML = `<div class="legend-title">${esc(T('Watersheds and streams'))}</div>`
    + `<div class="row"><span class="sw line" style="border-top:1.5px dashed ${SHED}"></span>${esc(T('Subwatershed (HUC-12): {n} in Puerto Rico', { n }))}</div>`
    + `<div class="row"><span class="sw line" style="border-top:3px solid ${STREAM}"></span>${esc(T('Stream, wider for a larger river (drains 5 km² or more)'))}</div>`
    + `<div class="note">${esc(T('USGS Watershed Boundary Dataset and NHDPlus High Resolution. Click the map for the subwatershed there. To see the land that drains to any point, use What drains here in Tools › Map tools.'))}</div>`;
}
function shedsOff() { if (shedLayer) { map.removeLayer(shedLayer); map.removeLayer(streamLayer); } }
/** The subwatershed under a point, for the map's pop-up. */
function shedAt(ll) {
  if (!shedData) return [];
  const fs = shedData.sheds.features;
  if (!shedData.at) {   // point in polygon, with each outline's box first
    const boxes = fs.map(f => { let b = [Infinity, Infinity, -Infinity, -Infinity]; const walk = (c) => typeof c[0] === 'number' ? (b = [Math.min(b[0], c[0]), Math.min(b[1], c[1]), Math.max(b[2], c[0]), Math.max(b[3], c[1])]) : c.forEach(walk); walk(f.geometry.coordinates); return b; });
    const ring = (r, x, y) => { let o = false; for (let i = 0, j = r.length - 1; i < r.length; j = i++) if ((r[i][1] > y) !== (r[j][1] > y) && x < (r[j][0] - r[i][0]) * (y - r[i][1]) / (r[j][1] - r[i][1]) + r[i][0]) o = !o; return o; };
    const poly = (p, x, y) => ring(p[0], x, y) && !p.slice(1).some(h => ring(h, x, y));
    shedData.at = (x, y) => fs.findIndex((f, k) => { const b = boxes[k]; if (x < b[0] || x > b[2] || y < b[1] || y > b[3]) return false; const g = f.geometry; return (g.type === 'Polygon' ? [g.coordinates] : g.coordinates).some(p => poly(p, x, y)); });
  }
  const k = shedData.at(ll.lng, ll.lat); if (k < 0) return [];
  const p = fs[k].properties;
  return [`<div class="pop-sec"><b>${esc(T('Subwatershed'))}</b>: ${esc(p.name)} <small translate="no">HUC ${esc(p.huc12)}</small><br>${esc(T('Subbasin'))}: ${esc(p.basin)}<br>${esc(T('{km2} km², {n} residents (Census 2020)', { km2: fmt(p.km2, 1), n: fmt(p.residents, 0) }))}</div>`];
}
window.shedAt = shedAt; window.shedsOn = shedsOn; window.shedsOff = shedsOff;
if (typeof module === 'object' && module.exports) module.exports = { marching, contourStep };
