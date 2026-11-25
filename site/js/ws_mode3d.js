/* PR Data Observatory: the 3D view as a mode of Map (docs/workspace.md). Adds the 2D / 3D switch to the 3D view and says which layers of the map it
   cannot draw. The analysis travels in the address (js/core/viewstate.js); a layer this view does not have stays in the address, so it is back in 2D. */
(function () {
  'use strict';
  const host = document.getElementById('map'); if (!host) return;
  const box = document.createElement('div'); box.className = 'ws-mode3d';
  box.innerHTML = `<div class="ws-mode" role="group" aria-label="${esc(T('Map view'))}"><a id="wsMode2d" href="index.html" title="${esc(T('Back to the 2D view of this map'))}">2D</a><button type="button" aria-pressed="true" title="${esc(T('This is the 3D view'))}">3D</button></div><p class="ws-mode-note" id="wsModeNote" role="status" hidden></p>`;
  document.body.appendChild(box);
  const NAMES = { watersheds: T('Watersheds and streams'), slope: T('Slope'), contours: T('Contour lines'), now: T('Transit vehicles now') };
  const back = () => { const a = document.querySelector('.views a[href^="index.html"]'); return a ? a.getAttribute('href') : 'index.html' + location.search + location.hash; };
  document.getElementById('wsMode2d').addEventListener('click', (e) => { e.preventDefault(); location.href = back(); });
  function note() {
    const V = window.Core && Core.viewstate; if (!V) return;
    const l = (V.parse(location.hash).l || []).filter(t => t && t[0] !== '-' && V.LAYERS[t] && !V.LAYERS[t]['3d']);
    const n = document.getElementById('wsModeNote'), parts = [];
    if (l.length) parts.push(T('Not drawn in 3D: {layers}. They are kept and come back in 2D.', { layers: l.map(t => NAMES[t] || t).join(', ') }));
    parts.push(T('Insights, the timeline slider and the workbench are in 2D. Here the Time tab sets the year, the day of transit and the storms.'));
    n.textContent = parts.join(' '); n.hidden = false;
  }
  note(); window.addEventListener('hashchange', note); setTimeout(note, 4000);
})();
