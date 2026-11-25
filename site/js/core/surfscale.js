/* PR Data Observatory core: the colors of the surface heat image (heat_surface.png, made by surface_image.py; HANDOFF decision 88, docs/heat.md "The surface on
   the map"). Both maps load this file with the image, the first time its switch is turned on.

   The image's pixels are the 64 steps of a fixed scale (Puerto Rico's: gray at the island's median). open() reads the steps once, by the palette the build used
   (the same interpolation and rounding as surface_image.ramp); then
     stats(box)      the scale of the land in a lon/lat box [w, s, e, n]: centered on its median, its ends at the larger distance from the median to the 2nd and
                     98th percentiles (at least 1 °C), so a city shows its own hot and cool places; null when the box holds too little land
     paint(scale)    the picture recolored on that scale, as a blob URL (the map lays it where the image was); the last two URLs are kept, older ones revoked
     legend(scale, mode, time)   the legend: the color bar, its ends and median in °C, the switches between "This view" and "Puerto Rico" and, when the
                     page offers both images, between "Morning" and "Night" (meta.time 'night': ECOSTRESS), the threshold slider, and a note
     floor(v)        a threshold (GIS tools step 2, docs/gis-tools-proposal-2026-11.md): paint() leaves out the steps whose value is below v (null: show all);
                     floor() gives the one in use
     threshold(lo, hi, by, label)   the slider that sets it, for a legend; on release it calls the page's surfPaint() (2D map and 3D view), or, inside an element
                     with data-surf-own="name", the page's function of that name (the slope layer)
   No color is invented: a pixel keeps its measured step, only the color given to the step changes. */
(function (name, root, factory) {
  const api = factory(root);
  if (typeof module === 'object' && module.exports) module.exports = api; else { root.Core = root.Core || {}; root.Core[name] = api; }
})('surfscale', typeof window !== 'undefined' ? window : globalThis, function (root) {
  'use strict';
  const STEPS = 64, MIN_PX = 400;
  const hex = (h) => [1, 3, 5].map(i => parseInt(h.slice(i, i + 2), 16));
  const roundEven = (x) => { const f = Math.floor(x), d = x - f; return d > 0.5 ? f + 1 : d < 0.5 ? f : (f % 2 === 0 ? f : f + 1); };   // Python's round()
  /** The color at t (0..1) of a scale through `stops`, linear in sRGB between them (surface_image.ramp), unrounded. */
  function at(stops, t) {
    const cs = stops.map(hex), x = Math.min(Math.max(t, 0), 1) * (cs.length - 1), i = Math.min(Math.floor(x), cs.length - 2), f = x - i;
    return [0, 1, 2].map(j => cs[i][j] + (cs[i + 1][j] - cs[i][j]) * f);
  }
  const mercY = (lat) => Math.log(Math.tan(Math.PI / 4 + lat * Math.PI / 360));

  async function open(url, meta) {
    const img = new Image();
    await new Promise((ok, fail) => { img.onload = ok; img.onerror = () => fail(new Error(url)); img.src = url; });   // not img.decode(): it never settles while the page is in a background tab
    const W = img.naturalWidth, H = img.naturalHeight, cv = document.createElement('canvas'); cv.width = W; cv.height = H;
    const cx = cv.getContext('2d', { willReadFrequently: true }); cx.drawImage(img, 0, 0);
    const src = cx.getImageData(0, 0, W, H).data, sc = meta.scale, stops = sc.stops;
    const pal = new Map();
    for (let k = 0; k < STEPS; k++) { const c = at(stops, k / (STEPS - 1)).map(roundEven); pal.set((c[0] << 16) | (c[1] << 8) | c[2], k + 1); }
    const step = new Uint8Array(W * H);
    for (let i = 0, p = 0; i < step.length; i++, p += 4) if (src[p + 3]) step[i] = pal.get((src[p] << 16) | (src[p + 1] << 8) | src[p + 2]) || 0;
    const value = (k) => sc.low + (k - 1) / (STEPS - 1) * (sc.high - sc.low);
    const island = { low: sc.low, centre: sc.centre, high: sc.high };
    const [w, s, e, n] = meta.bounds, my0 = mercY(s), my1 = mercY(n);
    const out = cx.createImageData(W, H), px = new Uint32Array(out.data.buffer), urls = [];
    let last = '', min = null;

    function stats(box) {
      const c0 = Math.max(0, Math.floor((box[0] - w) / (e - w) * W)), c1 = Math.min(W, Math.ceil((box[2] - w) / (e - w) * W));
      const r0 = Math.max(0, Math.floor((my1 - mercY(Math.min(box[3], 85))) / (my1 - my0) * H)), r1 = Math.min(H, Math.ceil((my1 - mercY(Math.max(box[1], -85))) / (my1 - my0) * H));
      if (c1 <= c0 || r1 <= r0) return null;
      const by = Math.max(1, Math.floor(Math.sqrt((c1 - c0) * (r1 - r0) / 250000))), hist = new Uint32Array(STEPS + 1);   // at most about 250,000 pixels looked at
      let n_ = 0;
      for (let r = r0; r < r1; r += by) for (let c = c0, i = r * W + c0; c < c1; c += by, i += by) { const k = step[i]; if (k) { hist[k]++; n_++; } }
      if (n_ < MIN_PX) return null;
      const q = (p) => { let acc = 0; const want = p * n_; for (let k = 1; k <= STEPS; k++) { acc += hist[k]; if (acc >= want) return value(k); } return value(STEPS); };
      const med = q(0.5), half = Math.max(1, Math.ceil(Math.max(med - q(0.02), q(0.98) - med)));
      return { low: med - half, centre: med, high: med + half };
    }
    function paint(scale) {
      const key = [scale.low, scale.centre, scale.high, min].join();
      if (key === last && urls.length) return Promise.resolve(urls[urls.length - 1]);
      last = key;
      const lut = new Uint32Array(STEPS + 1);
      for (let k = 1; k <= STEPS; k++) {
        const c = at(stops, (value(k) - scale.low) / (scale.high - scale.low)).map(Math.round);
        lut[k] = min != null && value(k) < min - 1e-9 ? 0 : (255 << 24) | (c[2] << 16) | (c[1] << 8) | c[0];   // ImageData is RGBA in memory (little-endian ABGR as a 32-bit word); a step below the threshold is transparent
      }
      for (let i = 0; i < step.length; i++) px[i] = lut[step[i]];
      cx.putImageData(out, 0, 0);
      return new Promise(ok => cv.toBlob(b => { const u = URL.createObjectURL(b); urls.push(u); while (urls.length > 2) URL.revokeObjectURL(urls.shift()); ok(u); }, 'image/png'));
    }
    function legend(scale, mode, time) {   // time: 'day' or 'night' when the page offers both (the switch is drawn), else nothing
      const T = root.T || ((x) => x), esc = root.esc || String, fmt = root.fmt || ((v, d) => v.toFixed(d)), m = meta, night = m.time === 'night';
      const btn = (attr, k, cur, label) => `<button type="button" class="chip${cur === k ? ' on' : ''}" data-surf-${attr}="${k}" aria-pressed="${cur === k}">${esc(T(label))}</button>`;
      const src = night ? T('NASA ECOSTRESS, June to September {first}–{last}, read at 70 m, cells of {m} m.', { first: m.summers[0], last: m.summers[1], m: fmt(m.pixel_m, 0) })
        : T('Landsat 8 and 9, June to September {first}–{last}, cells of {m} m.', { first: m.summers[0], last: m.summers[1], m: fmt(m.pixel_m, 0) });
      const note = mode === 'view' ? T('Blue: cooler than the median of the land in view. Red: hotter. The colors follow the view: move the map and they adjust.')
        : T('Blue: cooler than Puerto Rico\'s median surface. Red: hotter.');
      return `<div class="legend-title">${esc(T(night ? 'Surface temperature, summer nights' : 'Surface temperature, summer mornings'))} <small>${esc(T('°C, of the ground, not the air'))}</small></div>`
        + (time ? `<div class="surf-mode" role="group" aria-label="${esc(T('Time of day'))}"><span>${esc(T('Time of day'))}</span>${btn('time', 'day', time, 'Morning')}${btn('time', 'night', time, 'Night')}</div>` : '')
        + `<div class="surf-mode" role="group" aria-label="${esc(T('Colors'))}"><span>${esc(T('Colors'))}</span>${btn('mode', 'view', mode, 'This view')}${btn('mode', 'island', mode, 'Puerto Rico')}</div>`
        + `<div class="surf-bar" style="background:linear-gradient(90deg,${stops.join(',')})"></div>`
        + `<div class="surf-ticks"><span>${fmt(scale.low, 0)}</span><span>${esc(T('{v} median', { v: fmt(scale.centre, 1) }))}</span><span>${fmt(scale.high, 0)}</span></div>`
        + threshold(Math.floor(island.low), Math.ceil(island.high), 0.5, (v) => v == null ? T('All the ground') : T('Only the ground at {v} °C or hotter', { v: fmt(v, 1) }))
        + `<div class="note">${esc(note)} ${esc(src)}</div>`;
    }
    /** The threshold slider of a legend: from lo (show all) to hi in steps of `by`; label(v) says what is shown (v null: all). It acts on this image. */
    function threshold(lo, hi, by, label) {
      const T = root.T || ((x) => x), esc = root.esc || String, id = 'surfMin' + me;
      labels[me] = label;
      return `<div class="surf-min"><label for="${id}">${esc(T('Show only above'))}</label><input type="range" id="${id}" data-surf-min="${me}" min="${lo}" max="${hi}" step="${by}" value="${min == null ? lo : min}" aria-valuetext="${esc(label(min))}"><output for="${id}">${esc(label(min))}</output></div>`;
    }
    const floor = (v) => { if (v === undefined) return min; min = v == null || !isFinite(v) ? null : +v; return min; };
    const me = images.push(null) - 1, api = { W, H, island, stats, paint, legend, threshold, floor, steps: () => step };
    images[me] = api;
    return api;
  }
  // The slider of whichever legend is on screen. At its lowest it shows all, otherwise only the steps at or above its value. While it moves ('input') only its
  // label follows; on release ('change') the image is repainted and the legend redrawn, so a drag is not cut short by the redraw.
  // Each slider names its image (data-surf-min="<index>"), so the heat and slope legends can be open together.
  const images = [], labels = [];
  const pick = (r) => (+r.value <= +r.min ? null : +r.value);
  if (root.document) {
    root.document.addEventListener('input', (e) => {
      const r = e.target.closest && e.target.closest('[data-surf-min]'), f = r && labels[+r.dataset.surfMin]; if (!f) return;
      const o = r.parentNode.querySelector('output'), t = f(pick(r)); if (o) o.textContent = t; r.setAttribute('aria-valuetext', t);
    });
    root.document.addEventListener('change', (e) => {
      const r = e.target.closest && e.target.closest('[data-surf-min]'), img = r && images[+r.dataset.surfMin]; if (!img) return;
      img.floor(pick(r));
      const own = r.closest('[data-surf-own]');
      if (own && typeof root[own.dataset.surfOwn] === 'function') root[own.dataset.surfOwn](); else if (typeof root.surfPaint === 'function') root.surfPaint();
    });
  }
  return { STEPS, at, roundEven, open };
});
