/* PR Data Observatory core: Clean view, on the 2D map and the 3D view (2026-11-11). One button in the map's controls, or the V key, hides the boxes over
   the map (the layer list, legends, the time bar, the map's buttons and messages) for a clear look, a presentation or a screenshot; the scale and the
   map credits stay, as their licences ask. A "Show controls" button, Escape or V brings them back. What is hidden is one list in twin.css (body.clean-view).
   The page calls CleanView.button() and puts the button in its map's controls. */
(function (root) {
  'use strict';
  const doc = root.document;
  if (!doc) return;
  const T = (s) => (root.T ? root.T(s) : s);
  const esc = (s) => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  let on = false, pill = null, btn = null;

  function set(v) {
    on = !!v;
    doc.body.classList.toggle('clean-view', on);
    if (btn) btn.setAttribute('aria-pressed', String(on));
    if (on) {
      if (!pill) {
        pill = doc.createElement('button');
        pill.type = 'button'; pill.className = 'cv-show';
        pill.innerHTML = `<span class="ms-icon" aria-hidden="true">visibility</span>${esc(T('Show controls'))}`;
        pill.addEventListener('click', () => set(false));
        (doc.getElementById('map') || doc.body).appendChild(pill);
      }
      pill.hidden = false; pill.focus();
    } else if (pill) { pill.hidden = true; if (btn && doc.activeElement === pill) btn.focus(); }
  }

  /** The button for the map's controls (a Leaflet bar or a MapLibre control group). */
  function button() {
    if (btn) return btn;
    btn = doc.createElement('button');
    btn.type = 'button'; btn.className = 'cv-btn';
    const label = T('Clean view: hide the boxes over the map (V)');
    btn.title = label; btn.setAttribute('aria-label', label); btn.setAttribute('aria-pressed', 'false');
    btn.innerHTML = '<span class="ms-icon" aria-hidden="true">visibility_off</span>';
    btn.addEventListener('click', (e) => { e.stopPropagation(); set(!on); });
    return btn;
  }

  doc.addEventListener('keydown', (e) => {
    if (e.ctrlKey || e.metaKey || e.altKey) return;
    if (on && e.key === 'Escape') { set(false); return; }
    const a = doc.activeElement;
    if (a && (/^(INPUT|TEXTAREA|SELECT)$/.test(a.tagName) || a.isContentEditable)) return;
    if (e.key === 'v' || e.key === 'V') set(!on);
  });

  root.CleanView = { set, button, isOn: () => on };
})(typeof window !== 'undefined' ? window : globalThis);
