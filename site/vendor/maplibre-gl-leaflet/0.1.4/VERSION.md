# @maplibre/maplibre-gl-leaflet 0.1.4 (vendored)

- What: `leaflet-maplibre-gl.js`, the UMD build of MapLibre GL Leaflet, copied unchanged from the npm package.
- Version: 0.1.4, published on npm 2026-08-16 (the `latest` tag on 2026-10-23).
- Source: https://registry.npmjs.org/@maplibre/maplibre-gl-leaflet/-/maplibre-gl-leaflet-0.1.4.tgz
  (npm integrity `sha512-k57wcndZIvq3m08g2je4pjUPGr43ffNW3j+gXbymt8Vi2l1lUERUi1UmdTZcTPN8LuDDYOMWRNBaSLwpAu02ew==`, checked on download).
- Repository: https://github.com/maplibre/maplibre-gl-leaflet
- Licence: ISC (the `LICENSE` file beside this one, copied from the package).
- Peer dependencies of 0.1.4: `leaflet ^1.9.3`, `maplibre-gl ^2.4.0 || ^3.3.1 || ^4.3.2 || ^5.0.0 || ^6.0.0`.
  The observatory uses Leaflet 1.9.4 and MapLibre GL JS 4.7.1 (the same cdnjs file as the 3D view).
- Loaded by `site/js/core/basemap.js` after the page is ready, never in a page's HTML (docs/basemap.md).
- To update: download the new tarball from npm, check its integrity and licence, copy `leaflet-maplibre-gl.js` and `LICENSE` into a new
  folder named after the version, change `LIBS.bridge` in `site/js/core/basemap.js` and the `deferred` lists in `dictionary_src/routes.json`.
