/* PR Data Observatory core: the base map, one configuration for every map (docs/basemap.md).

   The observatory's maps have four layers, kept apart here:
     1. the geographic data source: OpenStreetMap (© OpenStreetMap contributors, ODbL), which every street, building and place name of the base map comes from;
     2. the tile provider: OpenFreeMap, which cuts that data into vector tiles in the OpenMapTiles schema and serves them with a style, no key and no sign-up;
        and, for the aerial imagery, topographic and shaded relief choices, the USGS National Map, whose picture tiles are its own (no OpenStreetMap in them);
     3. the rendering library: MapLibre GL JS 4.7.1, which draws the tiles (in the 2D maps under Leaflet, through MapLibre GL Leaflet);
     4. the observatory's own data, drawn by each page on top. This file holds none of it.
   Terrain is a source of its own (AWS Terrain Tiles, Terrarium encoding), used by the 3D view only.

   Each source carries its license, its link and the credit lines the map must show, in English and Spanish. To change provider or style, edit PROVIDERS and
   VIEWS below (docs/basemap.md, "Switching providers"): the pages read everything from here. Nothing here is a credential. A future provider that needs a
   key names it in its `key` field; the key itself goes in site/js/basemap.local.js, which git ignores (.gitignore), as
   window.BASEMAP_LOCAL = { <key name>: '<key>' }, and is loaded before the style is asked for. A key in a web page is public, so prefer providers without one.

   The 2D map and the two WCRP maps load this file after the page is ready (performance.mark('ready')), and it loads MapLibre and the bridge, so the base map
   stays off every page's budgeted first load (budget.py, the "deferred" list of dictionary_src/routes.json). The 3D view loads it with the page: it needs the
   style to start. When WebGL is off, the style does not load or the tiles keep failing, the 2D maps go on with no base map, on a plain light background,
   with a short notice; they never fall back to the OpenStreetMap Foundation's own tile servers, which are not for production use. */
(function (name, root, factory) {
  const api = factory(root);
  if (typeof module === 'object' && module.exports) module.exports = api; else { root.Core = root.Core || {}; root.Core[name] = api; }
})('basemap', typeof window !== 'undefined' ? window : globalThis, function (root) {
  const CHECKED = '2026-10-23';   // the date the terms and links below were last read

  // ── 1. Sources: who made what the base map shows, and how to credit them ──────────────────────────────────────────────────────────────────────
  const SOURCES = {
    osm: { role: 'geographic data source', name: 'OpenStreetMap', publisher: 'OpenStreetMap contributors', url: 'https://www.openstreetmap.org/copyright',
      licence: 'Open Database License (ODbL) 1.0', licence_url: 'https://opendatacommons.org/licenses/odbl/1-0/',
      credit: { en: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors', es: '© colaboradores de <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>' } },
    openmaptiles: { role: 'vector schema', name: 'OpenMapTiles', publisher: 'MapTiler and OpenMapTiles contributors', url: 'https://openmaptiles.org/',
      licence: 'Schema design CC BY 4.0; code BSD 3-Clause', licence_url: 'https://github.com/openmaptiles/openmaptiles/blob/master/LICENSE.md',
      credit: { en: '<a href="https://openmaptiles.org/">© OpenMapTiles</a>', es: '<a href="https://openmaptiles.org/">© OpenMapTiles</a>' } },
    openfreemap: { role: 'tile provider', name: 'OpenFreeMap', publisher: 'OpenFreeMap', url: 'https://openfreemap.org/',
      licence: 'Free public instance, no key, no SLA, provided as is (terms of 2026-10-14)', licence_url: 'https://openfreemap.org/tos/',
      credit: { en: '<a href="https://openfreemap.org/">OpenFreeMap</a>', es: '<a href="https://openfreemap.org/">OpenFreeMap</a>' } },
    maplibre: { role: 'rendering library', name: 'MapLibre GL JS 4.7.1', publisher: 'MapLibre contributors', url: 'https://maplibre.org/',
      licence: 'BSD 3-Clause', licence_url: 'https://github.com/maplibre/maplibre-gl-js/blob/main/LICENSE.txt', credit: null },
    bridge: { role: 'rendering library', name: 'MapLibre GL Leaflet 0.1.4', publisher: 'MapLibre contributors', url: 'https://github.com/maplibre/maplibre-gl-leaflet',
      licence: 'ISC', licence_url: 'https://github.com/maplibre/maplibre-gl-leaflet/blob/main/LICENSE', credit: null },
    terrain: { role: 'terrain source', name: 'AWS Terrain Tiles (Mapzen, Terrarium encoding)', publisher: 'Mapzen (Linux Foundation), AWS Open Data', url: 'https://registry.opendata.aws/terrain-tiles/',
      licence: 'Attribution required; the US elevation data (3DEP, SRTM, GMTED2010) are public domain', licence_url: 'https://github.com/tilezen/joerd/blob/master/docs/attribution.md',
      credit: { en: 'Terrain: Mapzen / AWS Open Data · 3DEP, SRTM and GMTED2010 data courtesy of the U.S. Geological Survey · ETOPO1: NOAA',
                es: 'Terreno: Mapzen / AWS Open Data · datos 3DEP, SRTM y GMTED2010 cortesía del Servicio Geológico de EE. UU. (USGS) · ETOPO1: NOAA' } },
    // The National Map (read 2026-11-13): free to use, no use restrictions, credit requested ("Map services and data available from U.S. Geological Survey,
    // National Geospatial Program"). Its USGSImageryTopo service retires on 2026-11-16, so it is not offered.
    usgs: { role: 'tile provider', name: 'USGS The National Map base maps', publisher: 'U.S. Geological Survey, National Geospatial Program', url: 'https://apps.nationalmap.gov/services/',
      licence: 'Free to use, no use restrictions; credit requested', licence_url: 'https://www.usgs.gov/faqs/what-are-terms-uselicensing-map-services-and-data-national-map',
      credit: { en: 'Base map: <a href="https://apps.nationalmap.gov/services/">U.S. Geological Survey, National Geospatial Program</a>',
                es: 'Mapa base: <a href="https://apps.nationalmap.gov/services/">Servicio Geológico de EE. UU. (USGS), Programa Geoespacial Nacional</a>' } },
    ortho: { role: 'imagery source', name: 'USGS Imagery Only (orthoimagery of The National Map)', publisher: 'USDA and USGS', url: 'https://basemap.nationalmap.gov/arcgis/rest/services/USGSImageryOnly/MapServer',
      licence: 'Free to use, no use restrictions; credit requested', licence_url: 'https://www.usgs.gov/faqs/what-are-terms-uselicensing-map-services-and-data-national-map',
      credit: { en: 'Orthoimagery: USDA, USGS', es: 'Ortoimágenes: USDA, USGS' } },
  };

  // ── 2. Tile providers: where the tiles and styles come from ───────────────────────────────────────────────────────────────────────────────────
  // styles: name → style URL; for a raster provider, name → { tiles, gap, bg } from which rasterStyle builds the style. credits: the SOURCES each must show on the
  // map, in order. host: matches the URLs (or an error message naming one) of its style, tiles, fonts and sprites, to tell its errors from the observatory's own
  // layers. key: null, or { name, param } for a provider that needs a key (see the header).
  const OFM = 'https://tiles.openfreemap.org/styles/', TNM = 'https://basemap.nationalmap.gov/arcgis/rest/services/';
  const PROVIDERS = {
    openfreemap: { name: 'OpenFreeMap', schema: 'openmaptiles', styles: { liberty: OFM + 'liberty', positron: OFM + 'positron', bright: OFM + 'bright', dark: OFM + 'dark', fiord: OFM + 'fiord' },
      credits: ['osm', 'openmaptiles', 'openfreemap'], host: /openfreemap\.org/i, key: null },
    // 256 px picture tiles to zoom 16 (enlarged above it). Over Puerto Rico every zoom from 6 to 16 answers, except USGSImageryOnly at 9 and 10 (404, checked
    // 2026-11-13): its `gap` is drawn from its zoom 8 tiles, enlarged, as the service's own export does there.
    usgs: { name: 'USGS The National Map', schema: 'raster', maxzoom: 16, styles: {
      imagery: { tiles: TNM + 'USGSImageryOnly/MapServer/tile/{z}/{y}/{x}', gap: [9, 10] },
      topo: { tiles: TNM + 'USGSTopo/MapServer/tile/{z}/{y}/{x}' },
      relief: { tiles: TNM + 'USGSShadedReliefOnly/MapServer/tile/{z}/{y}/{x}', bg: '#fdfdfd' } },   // its sea is white in some tiles, see-through in others
      credits: ['usgs'], host: /nationalmap\.gov/i, key: null },
  };
  // A raster style has no fonts of its own; the 3D view's labels and stop counts (its own layers) read OpenFreeMap's, as on the other styles.
  const GLYPHS = 'https://tiles.openfreemap.org/fonts/{fontstack}/{range}.pbf';

  // ── 3. The styles a viewer can pick, and the one each view starts on ─────────────────────────────────────────────────────────────────────────
  // The switcher ("Base map" in the Layers panel of the 2D map and the 3D view) offers these, in this order. Each names its provider and style (both null for
  // "none", which loads nothing: the data over a plain background), with its name and a short description in English and Spanish. The choice travels in the
  // address as bm=<name> (the 2D and 3D links carry it) and is kept in this browser (localStorage 'twin.basemap') as the viewer's default; a link with no bm=
  // opens on that default, or on the view's own (VIEWS). The WCRP maps keep their view's default and show no switcher. `group` puts it under a heading of the
  // select (GROUPS); `credits`, when set, replaces its provider's.
  const OPTIONS = {
    positron: { provider: 'openfreemap', style: 'positron', group: 'osm', name: { en: 'Light (Positron)', es: 'Claro (Positron)' },
      desc: { en: 'A light map style that keeps the data in front: soft colors, few labels.', es: 'Estilo de mapa claro que deja los datos al frente: colores suaves, pocos rótulos.' } },
    liberty: { provider: 'openfreemap', style: 'liberty', group: 'osm', name: { en: 'Detailed (Liberty)', es: 'Detallado (Liberty)' },
      desc: { en: 'A detailed map style: streets, places, buildings and more labels.', es: 'Estilo de mapa detallado: calles, lugares, edificios y más rótulos.' } },
    bright: { provider: 'openfreemap', style: 'bright', group: 'osm', name: { en: 'Colorful (Bright)', es: 'Colorido (Bright)' },
      desc: { en: 'A colorful map style: roads by class, parks, water and points of interest.', es: 'Estilo de mapa colorido: carreteras por tipo, parques, agua y puntos de interés.' } },
    dark: { provider: 'openfreemap', style: 'dark', group: 'osm', name: { en: 'Dark', es: 'Oscuro' },
      desc: { en: 'A dark map style with few labels: bright data colors stand out.', es: 'Estilo de mapa oscuro, con pocos rótulos: los colores vivos de los datos resaltan.' } },
    fiord: { provider: 'openfreemap', style: 'fiord', group: 'osm', name: { en: 'Dark blue (Fiord)', es: 'Azul oscuro (Fiord)' },
      desc: { en: 'A dark blue map style, with streets and labels in soft tones.', es: 'Estilo de mapa azul oscuro, con calles y rótulos en tonos suaves.' } },
    imagery: { provider: 'usgs', style: 'imagery', group: 'usgs', credits: ['usgs', 'ortho'], name: { en: 'Aerial imagery', es: 'Imágenes aéreas' },
      desc: { en: 'Orthoimagery from the USGS National Map: aerial photos corrected to map scale, with no labels. Sharp when zoomed in to a town; coarse at the island view.',
              es: 'Ortoimágenes de The National Map del USGS: fotos aéreas corregidas a escala de mapa, sin rótulos. Nítidas al acercarse a un pueblo; con poco detalle en la vista de la isla.' } },
    topo: { provider: 'usgs', style: 'topo', group: 'usgs', name: { en: 'Topographic', es: 'Topográfico' },
      desc: { en: 'A topographic map from the USGS National Map: contour lines, shaded relief, rivers, roads and place names.',
              es: 'Mapa topográfico de The National Map del USGS: curvas de nivel, relieve sombreado, ríos, carreteras y nombres de lugares.' } },
    relief: { provider: 'usgs', style: 'relief', group: 'usgs', name: { en: 'Shaded relief', es: 'Relieve sombreado' },
      desc: { en: 'Shaded relief from USGS elevation data (3DEP): the shape of the land, with no roads or labels.',
              es: 'Relieve sombreado a partir de los datos de elevación del USGS (3DEP): la forma del terreno, sin carreteras ni rótulos.' } },
    none: { provider: null, style: null, name: { en: 'No base map', es: 'Sin mapa base' },
      desc: { en: 'Data only, on a plain background. No base map is loaded.', es: 'Solo los datos, sobre un fondo liso. No se carga ningún mapa base.' } },
  };
  const NAMES = Object.keys(OPTIONS);
  const GROUPS = { osm: { en: 'OpenStreetMap maps', es: 'Mapas de OpenStreetMap' }, usgs: { en: 'USGS maps', es: 'Mapas del USGS' } };
  // Each view's default: 2d, the 2D map and the WCRP maps (Positron, a light style under choropleths); 3d, the 3D view (Liberty, whose `building` layer
  // gives the extruded buildings; Positron has the same tiles and buildings).
  const VIEWS = { '2d': { provider: 'openfreemap', style: 'positron' }, '3d': { provider: 'openfreemap', style: 'liberty' } };
  const STORE = 'twin.basemap';

  // ── 4. Terrain (3D view) and the plain style used when the base map cannot load ───────────────────────────────────────────────────────────────
  const TERRAIN = { tiles: ['https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png'], encoding: 'terrarium', tileSize: 256, maxzoom: 15 };
  const FALLBACK_BG = '#dfeef7';
  const FALLBACK_STYLE = { version: 8, sources: {}, layers: [{ id: 'bg', type: 'background', paint: { 'background-color': FALLBACK_BG } }] };

  // ── 5. The libraries the 2D maps load after ready: the same MapLibre file and integrity as 3d.html, so the browser's cache serves both views ──────
  const LIBS = {
    css: { href: 'https://cdnjs.cloudflare.com/ajax/libs/maplibre-gl/4.7.1/maplibre-gl.min.css', integrity: 'sha384-K282sW/zFjTkrjR/+yr1H+gCukuy4OEYrkXRybV88g7pk+kZZYpNV6SAV59NcgFg' },
    maplibre: { src: 'https://cdnjs.cloudflare.com/ajax/libs/maplibre-gl/4.7.1/maplibre-gl.min.js', integrity: 'sha384-KKgyz2mG25bKJ1O2PyqTJPlAF8Kw2BpDmsLTNBXslICOBvhTAyF5F0XhLWF2ZovY' },
    bridge: { src: 'vendor/maplibre-gl-leaflet/0.1.4/leaflet-maplibre-gl.js' },   // vendored, ISC (site/vendor/maplibre-gl-leaflet/0.1.4/VERSION.md)
    local: { src: 'js/basemap.local.js' },   // only for a provider with a key; not in git
  };

  const TEXT = {
    loading: { en: 'Loading the base map…', es: 'Cargando el mapa base…' },
    off: { en: 'Base map unavailable', es: 'Mapa base no disponible' },
    webgl: { en: 'Base map unavailable: this browser cannot draw it (WebGL is off or not supported). The data are shown on a plain background.',
             es: 'Mapa base no disponible: este navegador no puede dibujarlo (WebGL está desactivado o no es compatible). Los datos se muestran sobre un fondo liso.' },
    provider: { en: 'Base map unavailable: its provider is not responding. The data are shown on a plain background.',
                es: 'Mapa base no disponible: su proveedor no responde. Los datos se muestran sobre un fondo liso.' },
    none: { en: 'Base map off', es: 'Mapa base desactivado' },
    noneLong: { en: 'Base map off: the data are shown on a plain background. Choose a base map in the Layers panel.',
                es: 'Mapa base desactivado: los datos se muestran sobre un fondo liso. Elija un mapa base en el panel de Capas.' },
    failed: { en: 'That base map could not be loaded. The map keeps the one it had.', es: 'Ese mapa base no se pudo cargar. El mapa conserva el que tenía.' },
    close: { en: 'Close', es: 'Cerrar' },
    credits: { en: 'Map credits', es: 'Créditos del mapa' },
  };
  const lang = () => (root.I18N && root.I18N.lang === 'en' ? 'en' : (root.I18N ? 'es' : 'en'));
  const tx = (o, l) => o[l || lang()];
  /** A notice of TEXT in the page language or `l`. */
  const text = (k, l) => tx(TEXT[k], l);

  const view = (v) => VIEWS[v] || VIEWS['2d'];
  const valid = (n) => NAMES.includes(n);
  /** The default style of a view ('2d' or '3d'): its name in OPTIONS. */
  // In the dark theme (css/ws.css, html[data-theme=dark]) the 2D maps open on the dark style, so the map does not glare between charcoal panels. A viewer's own
  // choice still comes first (bm= in the address, then the default kept in this browser: pick() below). The 3D view keeps Liberty, whose buildings it extrudes.
  const darkTheme = () => { try { return root.document.documentElement.dataset.theme === 'dark'; } catch (e) { return false; } };
  const defaultOf = (v) => (v === '2d' && darkTheme() ? 'dark' : view(v).style);
  /** The provider of a view's style, or of the named one (null for "none"). */
  const provider = (v, n) => { const o = OPTIONS[valid(n) ? n : defaultOf(v)]; return o.provider ? PROVIDERS[o.provider] : null; };
  const keyOf = (p) => (p.key ? ((root.BASEMAP_LOCAL || {})[p.key.name] || '') : '');
  /** The style of a view ('2d' or '3d'), or of the named one: its URL, with the provider's key when it needs one; for a raster provider, a style object
   *  (rasterStyle); for "none", a copy of the plain FALLBACK_STYLE (an object). */
  function style(v, n) {
    const name = valid(n) ? n : defaultOf(v), p = provider(v, name);
    if (!p) return JSON.parse(JSON.stringify(FALLBACK_STYLE));   // a copy: MapLibre keeps the object it is given
    if (p.schema === 'raster') return rasterStyle(name);
    const url = p.styles[OPTIONS[name].style], k = keyOf(p);
    return k ? `${url}${url.includes('?') ? '&' : '?'}${p.key.param}=${encodeURIComponent(k)}` : url;
  }
  /** A raster provider's style, built here: a plain background, then its picture tiles (source and layer `usgs`). A style with a `gap` (zooms the service lacks)
   *  draws a second source (`usgs-low`) under it from the zoom below the gap, enlarged, while the main source starts above it. Every source carries the credits,
   *  which the 3D view reads off its source; the 2D map's come from credits(). */
  function rasterStyle(name) {
    const p = PROVIDERS[OPTIONS[name].provider], d = p.styles[OPTIONS[name].style], attribution = credits(null, null, name);
    const src = (o) => ({ type: 'raster', tiles: [d.tiles], tileSize: 256, maxzoom: p.maxzoom, attribution, ...o });
    const sources = {}, layers = [{ id: 'bm-bg', type: 'background', paint: { 'background-color': d.bg || FALLBACK_BG } }];
    if (d.gap) { sources['usgs-low'] = src({ maxzoom: d.gap[0] - 1 }); layers.push({ id: 'usgs-low', type: 'raster', source: 'usgs-low' }); }
    sources.usgs = src(d.gap ? { minzoom: d.gap[1] + 1 } : {});
    layers.push({ id: 'usgs', type: 'raster', source: 'usgs' });
    return { version: 8, name: `${p.name}: ${name}`, glyphs: GLYPHS, sources, layers };
  }
  /** The credit line the base map of a view (or the named style) must show (HTML), in the page language or `l`: its sources in order (the style's own list, or
   *  its provider's), joined by " · "; empty for "none", which draws nothing of theirs. */
  const credits = (v, l, n) => {
    const p = provider(v, n), o = OPTIONS[valid(n) ? n : defaultOf(v)];
    return p ? (o.credits || p.credits).map(id => tx(SOURCES[id].credit, l)).join(' · ') : '';
  };
  /** True when the named style draws OpenStreetMap's vector tiles, which the map inspector reads (core/osminspect.js); the picture tiles of a raster style have no features. */
  const inspectable = (n) => { const o = OPTIONS[n]; return !!(o && o.provider && PROVIDERS[o.provider].schema === 'openmaptiles'); };
  /** The terrain's credit line (text). */
  const terrainCredit = (l) => tx(SOURCES.terrain.credit, l);
  /** True when a URL, or an error message that names one, belongs to a base-map provider (its style, tiles, glyphs or sprites). */
  const isProvider = (url) => Object.values(PROVIDERS).some(p => p.host.test(String(url || '')));
  /** The bm= of an address's hash ('#c=…&bm=liberty'), when it names a style; else null. */
  const fromHash = (hash) => { const m = /(?:^|[#&])bm=([a-z]+)(?=&|$)/.exec(String(hash || '')); return m && valid(m[1]) ? m[1] : null; };
  /** The viewer's default kept in this browser, or null (no storage, nothing kept, or a name no longer offered). */
  const stored = () => { try { const n = root.localStorage.getItem(STORE); return valid(n) ? n : null; } catch (e) { return null; } };
  /** Keeps a choice as the viewer's default (nothing when storage is unavailable: the choice then lasts for this page). */
  const store = (n) => { try { if (valid(n)) root.localStorage.setItem(STORE, n); } catch (e) { /* private window or blocked storage */ } };
  /** The style a view opens on: bm= in the address, else the viewer's default, else the view's own. */
  const pick = (v, hash) => fromHash(hash) || stored() || defaultOf(v);
  /** An address hash with bm= set to `n` (or taken out, for null), its other parts unchanged and in order. */
  const withHash = (hash, n) => {
    const parts = String(hash || '').replace(/^#/, '').split('&').filter(p => p && !/^bm=/.test(p));
    if (valid(n)) parts.push('bm=' + n);
    return parts.length ? '#' + parts.join('&') : '';
  };

  function webglOk() {
    try { const c = document.createElement('canvas'); return !!(c.getContext('webgl2') || c.getContext('webgl')); } catch (e) { return false; }
  }
  const once = {};
  function addScript(src, integrity) {
    return once[src] || (once[src] = new Promise((ok, fail) => {
      const s = document.createElement('script'); s.src = src; s.async = true;
      if (integrity) { s.integrity = integrity; s.crossOrigin = 'anonymous'; }
      s.onload = ok; s.onerror = () => { s.remove(); delete once[src]; fail(new Error(src)); };
      document.head.appendChild(s);
    }));
  }
  function addCss() {
    if (document.querySelector(`link[href="${LIBS.css.href}"]`)) return;
    const l = document.createElement('link'); l.rel = 'stylesheet'; l.href = LIBS.css.href; l.integrity = LIBS.css.integrity; l.crossOrigin = 'anonymous';
    document.head.appendChild(l);
  }
  /** MapLibre and the bridge, once per page (the key file first, for a provider that needs one). */
  let libsP = null;
  function libs(v, n) {
    return libsP || (libsP = (async () => {
      addCss();
      const p = provider(v, n);
      if (p && p.key && !root.BASEMAP_LOCAL) await addScript(LIBS.local.src).catch(() => {});
      if (!root.maplibregl) await addScript(LIBS.maplibre.src, LIBS.maplibre.integrity);
      if (!(root.L && root.L.maplibreGL)) await addScript(LIBS.bridge.src);
    })().catch(e => { libsP = null; throw e; }));
  }
  let styled = false;
  function addStyle() {   // the light background of a map with no base map, and the status in the credits line
    if (styled) return; styled = true;
    const s = document.createElement('style');
    s.textContent = `.leaflet-container[data-basemap="off"]:not(#map),.leaflet-container[data-basemap="none"]:not(#map){background:#eef3f6}.leaflet-gl-layer{position:absolute;left:0;top:0}`
      + `.bm-status{color:#4a5560}.bm-status.off{color:#7a3b00;font-weight:600}.bm-status.none{font-style:italic}.bm-status.loading::before{content:"";display:inline-block;width:8px;height:8px;margin-right:4px;border:1.5px solid #8a96a0;border-top-color:transparent;border-radius:50%;vertical-align:-1px;animation:bm-spin 1s linear infinite}`
      + `.bm-notice{position:absolute;top:58px;left:50%;transform:translateX(-50%);z-index:900;box-sizing:border-box;max-width:min(92%,460px);display:flex;gap:8px;align-items:flex-start;padding:6px 6px 6px 10px;background:#fff8ec;color:#5a2d00;border:1px solid #e3b26b;border-radius:6px;box-shadow:0 2px 6px rgba(0,0,0,.15);font-size:12.5px;line-height:1.4}`
      + `.bm-notice button{flex:none;border:0;background:none;color:inherit;font-size:18px;line-height:1;padding:0 4px;cursor:pointer}`
      + `.cr-btn{position:relative;float:left;clear:both;width:32px;height:32px;margin:10px;padding:0;border:1px solid rgba(0,0,0,.3);border-radius:50%;cursor:pointer;pointer-events:auto;`
      + `background:#fff url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 20 20'%3E%3Ccircle cx='10' cy='10' r='7.6' fill='none' stroke='%23205D7B' stroke-width='1.6'/%3E%3Ccircle cx='10' cy='6.3' r='1.25' fill='%23205D7B'/%3E%3Crect x='9' y='8.7' width='2' height='6' rx='1' fill='%23205D7B'/%3E%3C/svg%3E") center/20px no-repeat}`
      + `.cr-btn.cr-r{float:right}.cr-btn[aria-expanded="true"]{background-color:#e6f0f5}.cr-btn::after{content:"";position:absolute;inset:-7px}.cr-btn[hidden]{display:none}.cr-shut{display:none!important}`
      + `@media print{.cr-shut{display:block!important}.cr-btn{display:none}}`
      + `@keyframes bm-spin{to{transform:rotate(360deg)}}@media (prefers-reduced-motion:reduce){.bm-status.loading::before{animation:none}}`;
    document.head.appendChild(s);
  }

  const MAX_TILE_ERRORS = 8;   // tile errors in a row (no tile loaded in between) after which the provider counts as down
  // A small map needs few tiles (the WCRP vulnerability map, about 6 at zoom 9), fewer than that: the provider also counts as down when the map goes idle and
  // every tile it asked for since it was last idle failed (none arrived), at least MIN_FAILED of them: one tile that fails alone is not an outage.
  const MIN_FAILED = 2;
  const LOAD_TIMEOUT_MS = 30000;   // the style must load within this time
  /**
   * Draws the base map under a Leaflet map's own layers, after loading MapLibre and the bridge. Returns a handle { state, reason, name, layer, set(name) }.
   * opts: view ('2d'), style (a name of OPTIONS; default the view's), onState(state, message) called with 'loading', 'on', 'none' or 'off' (with a sentence
   * for a notice), pane (Leaflet pane, default tilePane: under every overlay pane). The credits are added to the map's attribution control while the base map
   * is on; the control's prefix shows the loading state and, when the base map is off or switched off, a short notice whose full sentence is its title.
   * set(name, { keep }) switches the style: only the base map changes (one layer of the tile pane), never the observatory's layers, their order or their pop-ups.
   * "none" removes it and loads nothing. A failed base map stays off until the viewer picks a style again, which tries afresh. With keep (a viewer's pick), the
   * name is kept as this viewer's default (store) once that style has loaded ("none" at once), never when it fails or another set() came first. A style that
   * loads, or "none", also takes away a notice still shown over the map (a failure that a new pick has made old).
   */
  function leaflet(map, opts = {}) {
    const v = opts.view || '2d', el = map.getContainer(), ac = map.attributionControl;
    const h = { state: 'loading', reason: null, name: valid(opts.style) ? opts.style : defaultOf(v), layer: null, set: null };
    const prefix0 = ac ? ac.options.prefix : '';
    addStyle();
    if (ac && ac.getContainer) fold(ac.getContainer(), { map: el });
    const status = (cls, short, long) => {
      if (!ac) return;
      const s = short ? `<span class="bm-status ${cls}" role="status"${long ? ` title="${long.replace(/"/g, '&quot;')}"` : ''}>${short}</span>` : '';
      ac.setPrefix([s, prefix0].filter(Boolean).join(' · '));
    };
    const tell = (state, msg) => { if (opts.onState) opts.onState(state, msg || ''); };
    let keep = 0;   // the attempt (gen) of a pick to keep as the viewer's default once it has loaded
    const taken = (g) => { clearNotice(el); if (keep === g) store(h.name); keep = 0; };
    const mark = (state, reason) => { h.state = state; h.reason = reason || null; el.dataset.basemap = state; };
    // A layer that goes is hidden at once and removed when MapLibre has no request in flight (idle), so removing it aborts nothing and logs no AbortError;
    // its credits go with it at once (Leaflet does not count below zero when the layer is removed later).
    const drop = (layer) => {
      const gl = layer.getMaplibreMap && layer.getMaplibreMap();
      const go = () => { if (layer._map) { try { map.removeLayer(layer); } catch (e) { /* already gone */ } } };
      const box = layer.getContainer && layer.getContainer(); if (box) box.style.display = 'none';
      const text = layer.getAttribution();
      if (ac) {
        ac.removeAttribution(text);
        // the bridge adds the credits again when its map loads (it removes, then adds them on 'load'), which can come after this, while the layer waits to
        // be removed: take them off again then (seen with only the fonts blocked: the base map was off and its credits stayed)
        if (gl) gl.on('load', () => ac.removeAttribution(text));
      }
      if (gl && !gl.areTilesLoaded()) { gl.once('idle', go); setTimeout(go, 15000); } else go();
    };
    let gen = 0;   // each set() is a new attempt: the events of an older layer are ignored
    const fail = (g, reason) => {
      if (g !== gen || h.state === 'off') return;
      if (h.layer) { drop(h.layer); h.layer = null; }
      mark('off', reason);
      const msg = tx(reason === 'webgl' ? TEXT.webgl : TEXT.provider);
      status('off', tx(TEXT.off), msg); tell('off', msg);
    };
    h.set = (name, o = {}) => {
      if (!valid(name)) return h;
      const g = ++gen; h.name = name; keep = o.keep ? g : 0;
      if (h.layer) { drop(h.layer); h.layer = null; }
      if (name === 'none') { mark('none'); status('none', tx(TEXT.none), tx(TEXT.noneLong)); taken(g); tell('none'); return h; }
      mark('loading'); status('loading', tx(TEXT.loading)); tell('loading');
      if (!webglOk()) { fail(g, 'webgl'); return h; }
      libs(v, name).then(() => {
        if (g !== gen) return;
        let errors = 0, loaded = false, layer;
        const timer = setTimeout(() => { if (!loaded) fail(g, 'timeout'); }, LOAD_TIMEOUT_MS);
        try {
          layer = h.layer = root.L.maplibreGL({ style: style(v, name), pane: opts.pane || 'tilePane', interactive: false, preserveDrawingBuffer: true,   // kept so the map prints
            attributionControl: { customAttribution: credits(v, null, name) } }).addTo(map);
        } catch (e) { clearTimeout(timer); fail(g, 'webgl'); return; }   // MapLibre could not create a WebGL context
        const gl = layer.getMaplibreMap();
        // A style can name an icon its sprite does not hold (the Dark style asks for "circle-11"): give it an empty one, so the label draws without it and the console stays clean.
        gl.on('styleimagemissing', (e) => { try { if (e && e.id && !gl.hasImage(e.id)) gl.addImage(e.id, { width: 1, height: 1, data: new Uint8Array(4) }); } catch (err) { /* the style changed meanwhile */ } });
        gl.on('load', () => { if (g !== gen) return; loaded = true; clearTimeout(timer); mark('on'); status('', ''); taken(g); tell('on'); });
        gl.on('error', (e) => {
          if (g !== gen) return;
          h.error = String((e && e.error && (e.error.message || e.error.url)) || '');   // the last one, for a reader of the console
          if (e && (e.tile || e.sourceId)) { if (++errors >= MAX_TILE_ERRORS) fail(g, 'tiles'); return; }   // a tile: only a run of them counts
          if (!loaded) { clearTimeout(timer); fail(g, 'style'); }   // the style, its fonts or icons before the first draw
        });
        let bad = 0, good = 0;   // tile errors and tiles arrived since the map was last idle
        gl.on('error', (e) => { if (g === gen && e && (e.tile || e.sourceId)) bad++; });
        gl.on('sourcedata', (e) => { if (e && e.tile) { errors = 0; good++; } });   // a tile arrived: the provider answers
        gl.on('idle', () => { if (g !== gen) return; if (bad >= MIN_FAILED && !good) fail(g, 'tiles'); bad = good = 0; });
        gl.getCanvas().addEventListener('webglcontextlost', () => fail(g, 'webgl'));
      }, () => fail(g, 'library'));
      return h;
    };
    return h.set(h.name);
  }

  /** Credits that fold on a phone (decision 65; docs/basemap.md, "Credits on a phone"): under PHONE an "i" button below the box; the box folds FOLD_MS after
   *  the OpenStreetMap credit shows, or at the first touch of the map (OSMF attribution guidelines). Call again with a rebuilt box: the state is kept. */
  const PHONE = '(max-width: 699px)', FOLD_MS = 5000, WAIT_MS = 20000;
  const CREDITED = /OpenStreetMap|Geospatial Program|Programa Geoespacial/;   // a base map's credit is in the box (OpenStreetMap's, or the USGS National Map's)
  let folds = 0;
  function fold(box, o = {}) {
    const doc = root.document;
    if (!box || !doc || !root.matchMedia || !box.parentNode) return null;
    addStyle();
    const corner = box.parentNode, map = o.map || box.closest('.leaflet-container, .maplibregl-map') || corner;
    let b = corner.querySelector(':scope > .cr-btn');
    const st = b ? b._cr : { open: true, user: false, mq: root.matchMedia(PHONE) };
    if (!b) {
      b = doc.createElement('button'); b.type = 'button'; b._cr = st;
      b.className = 'cr-btn' + (/right/.test(corner.className) ? ' cr-r' : '');
      b.onclick = () => { st.user = true; st.set(!st.open); };
      // The button sits in the map's corner but outside Leaflet's attribution control, so a tap would also reach the map as a click (review of #108).
      ['click', 'dblclick', 'mousedown', 'pointerdown', 'touchstart', 'contextmenu'].forEach(k => b.addEventListener(k, e => e.stopPropagation()));
      st.set = (open) => {
        const phone = st.mq.matches, bx = st.box;
        st.open = open; b.hidden = !phone;
        bx.classList.toggle('cr-shut', phone && !open);
        b.setAttribute('aria-expanded', String(!phone || open));
      };
      const shut = (e) => { if (!st.user && st.open && !(e && e.target && (st.box.contains(e.target) || b.contains(e.target)))) { st.set(false); stop(); } };
      const stop = () => { clearTimeout(st.t); clearInterval(st.i); ['pointerdown', 'wheel'].forEach(k => map.removeEventListener(k, shut, true)); };
      ['pointerdown', 'wheel'].forEach(k => map.addEventListener(k, shut, { capture: true, passive: true }));
      const t0 = Date.now();
      st.i = setInterval(() => { if (CREDITED.test(st.box.textContent) || Date.now() - t0 > WAIT_MS) { clearInterval(st.i); st.t = setTimeout(shut, FOLD_MS); } }, 250);
      if (st.mq.addEventListener) st.mq.addEventListener('change', () => st.set(st.open));
    }
    corner.appendChild(b);   // below the box: the corner's last control
    st.box = box;
    if (!box.id) box.id = `cr-box-${++folds}`;
    b.setAttribute('aria-controls', box.id);
    b.setAttribute('aria-label', tx(TEXT.credits)); b.title = tx(TEXT.credits);
    st.set(st.open);
    return b;
  }

  /**
   * A short notice over a map (in its container `el`), apart from the page's message bar, so it never takes the place of an Undo there. It stays `ms`
   * milliseconds (or until its × is pressed); a new one replaces it. Returns the element.
   */
  function notice(el, msg, ms = 9000) {
    addStyle();
    let n = el.querySelector(':scope > .bm-notice');
    if (!n) { n = root.document.createElement('div'); n.className = 'bm-notice'; n.setAttribute('role', 'status'); el.appendChild(n); }
    n.innerHTML = `<span></span><button type="button" aria-label="${tx(TEXT.close)}">×</button>`;
    n.firstChild.textContent = msg;
    n.lastChild.onclick = () => n.remove();
    clearTimeout(n._t); n._t = setTimeout(() => n.remove(), ms);
    return n;
  }
  /** Takes away the notice over a map (in `el`), if one is shown: a base map that has loaded makes a pending "could not be loaded" wrong (review of PR #92). */
  function clearNotice(el) {
    const n = el && el.querySelector && el.querySelector(':scope > .bm-notice');
    if (n) { clearTimeout(n._t); n.remove(); }
  }

  /**
   * The 3D view's clock rule for tiles that keep failing (twin3d.js; docs/basemap.md, section 4). The 3D view is seldom idle (its sources keep asking), so the
   * 2D maps' idle rule runs on a clock: a window opens with a failed base-map tile and closes `ms` later. A source then counts as down when at least `min` of its
   * tiles failed in the window and none arrived. Tiles still loading are not failures (review of PR #92: one tile failed while the others were held 7 s, and
   * the base map was hidden at 6 s and stayed off): while the source has some, the window stays open and is looked at again every `again` ms, so a slow provider
   * is not taken for a dead one; a tile that arrives meanwhile clears its source. o: { ms (6000), min (MIN_FAILED), again (1000), loading(id) → true while the
   * source has tiles in flight, down(ids) the sources that count as down, clock ({ setTimeout, clearTimeout }; the page's by default) }.
   * Returns { failed(id), arrived(id), reset(), open() }.
   */
  function tileWatch(o) {
    const ms = o.ms || 6000, min = o.min || MIN_FAILED, again = o.again || 1000, T = o.clock || root;
    let bad = {}, good = {}, t = 0;
    const clear = () => { bad = {}; good = {}; t = 0; };
    const run = () => {
      t = 0;
      const failing = Object.keys(bad).filter(id => bad[id] >= min && !good[id]);
      const down = failing.filter(id => !o.loading(id));
      if (down.length) { clear(); o.down(down); return; }
      if (failing.length) { t = T.setTimeout(run, again); return; }   // tiles still loading: not failures yet
      clear();
    };
    return {
      failed(id) { if (!t) { clear(); t = T.setTimeout(run, ms); } bad[id] = (bad[id] || 0) + 1; },   // the window opens with this failed tile
      arrived(id) { if (t) good[id] = (good[id] || 0) + 1; },
      reset() { if (t) T.clearTimeout(t); clear(); },
      open: () => !!t,
    };
  }

  /**
   * Wires the switcher: a <select> whose options are the names of OPTIONS (in the page's HTML in English, translated by its bundle), and the element its
   * aria-describedby names, which shows the chosen style's description. o: { value (the style shown now), onPick(name) }. The option texts are written again
   * from OPTIONS in the page language, so the names have one source. The page keeps a pick as this viewer's default (store) once it has taken it. Returns { set(name) } to show a style
   * chosen elsewhere (a new address).
   */
  function control(sel, o) {
    if (!sel) return null;
    const l = lang(), desc = root.document.getElementById(sel.getAttribute('aria-describedby') || '');
    for (const op of sel.options) if (OPTIONS[op.value]) op.textContent = OPTIONS[op.value].name[l];
    for (const g of sel.querySelectorAll('optgroup')) if (GROUPS[g.dataset.group]) g.label = GROUPS[g.dataset.group][l];
    const show = () => {
      if (!desc) return;
      desc.textContent = OPTIONS[sel.value].desc[l];
      const G = root.Core && root.Core.glossary; if (G && G.mark) try { G.mark(desc); } catch (e) { /* the glossary is optional */ }   // "map style" is a defined term
    };
    sel.value = valid(o.value) ? o.value : NAMES[0]; sel.disabled = false; show();
    sel.addEventListener('change', () => { if (!valid(sel.value)) return; show(); o.onPick(sel.value); });   // the page keeps the pick (store) once it has taken it: a refused pick is not kept
    return { set: (n) => { if (valid(n)) { sel.value = n; show(); } } };
  }

  return { CHECKED, SOURCES, PROVIDERS, OPTIONS, NAMES, GROUPS, VIEWS, STORE, TERRAIN, FALLBACK_STYLE, FALLBACK_BG, GLYPHS, LIBS, TEXT, MAX_TILE_ERRORS, MIN_FAILED, text, valid, defaultOf, style, credits,
    inspectable, terrainCredit, isProvider, fromHash, stored, store, pick, withHash, webglOk, leaflet, fold, notice, clearNotice, tileWatch, control };
});
