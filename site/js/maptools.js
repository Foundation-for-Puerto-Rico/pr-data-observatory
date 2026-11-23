/* PR Data Observatory: the Tools › Map tools pane of the 2D map (decision 97, docs/map-tools-proposal-2026-11.md). app.js loads this file the first time the pane
   opens (onTabShown), so the map's first load does not carry it; the pane's Spanish (es.map.maptools.js, module "maptools" in i18n_src/pages.json, html "tab-maptools")
   loads with it, and the pane waits unseen until then (data-t-wait), as the About tab does.
   The pane is a list: each button opens a tool where it already works, and nothing is copied. Its data-mt says how:
     l:<id>          switch on the layer whose checkbox is #<id>, in the pane that holds it (Map layers or Transit), open its section and show it
     s:<id>          show #<id> in the pane that holds it (Plan a route)
     b:<view>[:<id>] open the workbench under the map at a view (study, swipe, multiples, composite, scenarios, table) and, for a study-area tool, scroll to its box
     h:<view>        tourism places as hexagons of equal area (setPlacesView in app.js)
     f:landuse       the land-use analysis (openLanduse in app.js)
     c:copy          copy the address of this view
     i:png           Save the map as an image (js/mapimage.js, decision 97 step 3)
     m:<mode>        Measure distance and area (line) or Draw an area (area): js/measure.js and core/measure.js, loaded the first time (decision 97 step 2) */
(() => {
  const tab = $('#tab-maptools');
  const foldOpen = (el) => { const b = el.closest('.fold-body'); if (b && b.hidden) b.previousElementSibling.querySelector('.fold-toggle').click(); };   // common.js initFolds
  const show = (el) => { showTab(el.closest('.tab-page').id.slice(4)); foldOpen(el); setTimeout(() => el.scrollIntoView({ block: 'center' }), 60); };
  const layerOn = (el) => { show(el); if (!el.checked) el.click(); el.focus({ preventScroll: true }); };
  const fail = () => toast(T('The tool could not be opened. Check your connection and try again.'));
  async function bench(view, id) {
    if (typeof ecBenchOpen !== 'function') { try { await econLoad(); } catch { return; } }   // the Economy tab's scripts load on first use (js/econ_shell.js, which says what failed)
    if (typeof ecBenchOpen !== 'function') return fail();
    map.closePopup(); if (isMobile()) setPanel(false);
    ecBenchOpen(view);
    if (!id) return;
    let n = 0; const t = setInterval(() => {   // the study-area view draws its boxes once its module is in
      const h = document.getElementById(id);
      if (h) { clearInterval(t); h.scrollIntoView({ block: 'start' }); h.setAttribute('tabindex', '-1'); h.focus({ preventScroll: true }); } else if (++n > 50) clearInterval(t);
    }, 100);
  }
  async function copy() {
    if (typeof writeHash === 'function') writeHash();
    try { await navigator.clipboard.writeText(location.href); toast(T('Link copied: it reopens this view.'), 4000); }
    catch { toast(T('Copy the address from the address bar of your browser.'), 5000); }
  }
  let msP = null;
  const measure = (mode) => {
    if (isMobile()) setPanel(false);
    msP = msP || allIn([I18N.load('measure'), addJs('js/core/measure.js?v=1').then(() => addJs('js/measure.js?v=3'))]).catch(e => { msP = null; throw e; });
    msP.then(() => Measure.open(mode), fail);
  };
  let imP = null;
  const image = () => {   // Save the map as an image (decision 97 step 3): js/mapimage.js and core/mapimage.js, loaded the first time
    imP = imP || allIn([I18N.load('mapimage'), addJs('js/core/mapimage.js?v=1').then(() => addJs('js/mapimage.js?v=1'))]).catch(e => { imP = null; throw e; });
    imP.then(() => MapImage.save(), fail);
  };
  const run = (spec) => {
    const [k, a, b] = spec.split(':');
    if (k === 'l') layerOn($('#' + a));
    else if (k === 's') { const el = $('#' + a); show(el); if (a === 'planBox' && typeof planLoad === 'function') planLoad(); }
    else if (k === 'b') bench(a, b);
    else if (k === 'h') { layerOn($('#lyPlaces')); setPlacesView(a); setTimeout(() => $('#placesView').scrollIntoView({ block: 'center' }), 80); }
    else if (k === 'f' && a === 'landuse') { if (isMobile()) setPanel(false); openLanduse(); }
    else if (k === 'c') copy();
    else if (k === 'm') measure(a);
    else if (k === 'i') image();
  };
  tab.addEventListener('click', (e) => { const b = e.target.closest('[data-mt]'); if (b) run(b.dataset.mt); });
  I18N.load('maptools').then(() => I18N.apply(tab), (e) => console.error(e)).finally(() => {
    tab.removeAttribute('data-t-wait'); tab.removeAttribute('aria-hidden');
    if (window.Core && Core.glossary && Core.glossary.mark) Core.glossary.mark(tab);
  });
  // each tool a lesson of the Learn page teaches gets a link to it (js/learn_links.js; decision 106, step 2)
  learnLinks().then((L) => {
    if (!L) return;
    for (const b of tab.querySelectorAll('[data-mt]')) {
      const l = L.tools[b.dataset.mt], li = b.closest('.mt-item'); if (!l || !li || li.querySelector('.mt-learn')) continue;
      const a = document.createElement('a'); a.className = 'mt-learn'; a.href = 'learn.html#lesson-' + l[0]; a.textContent = lessonName(l); a.setAttribute('data-t', 'skip'); li.appendChild(a);
    }
  });
  window.MapTools = { run };
})();
