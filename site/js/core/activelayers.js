/* PR Data Observatory core: the "layers on" chip at the top of the 2D map and the 3D view, its list, "Turn all off" with Undo, and the map's message (toast).
   Each page builds its adapter from the parts below (switches, select, econ, plan, state, combine) and mounts it on its map. docs/active-layers.md explains what counts and why. */
(function (name, root, factory) {
  const dep = (n) => (typeof module === 'object' && module.exports ? require('./' + n + '.js') : root.Core[n]);
  const api = factory(root, dep);
  if (typeof module === 'object' && module.exports) module.exports = api; else { root.Core = root.Core || {}; root.Core[name] = api; }
})('activelayers', typeof window !== 'undefined' ? window : globalThis, function (root, dep) {
  'use strict';
  const { T, Tn, esc } = dep('text');
  const doc = root.document;
  const fire = (el) => el.dispatchEvent(typeof Event === 'function' ? new Event('change') : { type: 'change' });
  const flip = (el, on) => { if (el && el.checked !== on) { el.checked = on; fire(el); } };
  const clean = (n) => { const c = n.cloneNode(true); c.querySelectorAll('small, .ms-icon, button, input, select').forEach(x => x.remove()); return c.textContent.replace(/\s+/g, ' ').trim(); };
  // a switch in the list: its label without the note in <small>, and the title of its group
  function describe(el) {
    const l = el.closest('label'); let g = el.closest('.fold'), h = g && g.querySelector('.fold-title');
    if (!h) for (h = el.closest('.layer') || el.closest('label'); h && !h.matches('h2.sec'); h = h.previousElementSibling);
    return { name: l ? clean(l) : el.id, group: h ? clean(h) : '' };
  }

  // ── adapter parts ─────────────────────────────────────────────────────────
  // names: a shorter or live name for some switches; drawn: listed only while it is drawn (the walk rings need a zoom and stops)
  function switches(els, names = {}, drawn = {}) {
    els = els.filter(Boolean);
    return {
      list: () => els.filter(e => e.checked && (!drawn[e.id] || drawn[e.id]())).map(e => { const d = api.describe(e); return { id: e.id, name: names[e.id] ? names[e.id]() || d.name : d.name, group: d.group }; }),
      turnOff: id => flip(els.find(e => e.id === id), false),
      clear: () => els.forEach(e => flip(e, false)),   // "Turn all off": a ticked switch that is not drawn goes off too, or it would come back (the walk rings after a zoom)
      sig: () => els.map(e => e.checked ? e.id + ':' + (names[e.id] ? names[e.id]() : '') : '').join(),   // the settings, not what is drawn: a zoom that hides the rings keeps Undo
      snapshot: () => els.map(e => e.checked),
      restore: s => els.forEach((e, i) => flip(e, s[i])),
    };
  }
  function select(el, group) {
    const set = v => { if (el.value !== v) { el.value = v; fire(el); } };
    return {
      list: () => el && el.value ? [{ id: el.id, name: (el.selectedOptions && el.selectedOptions[0] || {}).text || el.value, group }] : [],
      turnOff: () => set(''), snapshot: () => el ? el.value : '', restore: v => el && set(v),
    };
  }
  function econ(get) {
    return {
      list: () => { const a = get(); return a ? a.active().map(l => ({ id: 'ec' + l.id, name: l.name, group: l.group })) : []; },
      turnOff: id => get().remove(+id.slice(2)),
      clear: () => get().clear({ scenario: true, keepPlace: true }),   // the layers, the composite and the scenario
      snapshot: () => { const a = get(); return a ? a.snap() : null; },
      restore: s => { const a = get(); if (a && s) a.restore(s); },
    };
  }
  function plan(get) {
    const copy = P => JSON.stringify({ stops: P.stops, follow: P.follow });
    return {
      list: () => { const P = get(); return P && P.placed().length ? [{ id: 'plan', name: T('Planned route'), group: T('Plan a route'), keep: true }] : []; },
      turnOff: () => { const P = get(); if (P) P.clear(); },
      snapshot: () => { const P = get(); return P ? copy(P) : null; },
      sig: () => { const P = get(); return P ? copy(P) : ''; },   // a moved stop changes the plan, not the list
      restore: s => { const P = get(); if (!P || !s || copy(P) === s) return; const o = JSON.parse(s); P.stops = o.stops; P.follow = o.follow; P.render(); P.stopsChanged(true); },
    };
  }
  // a value of the page that Undo puts back after the switches (the 3D view's sea level rise that the year mode switched on)
  const state = (get, set) => ({ list: () => [], turnOff() {}, snapshot: get, restore: set, sig: () => '' });
  // the list in the order of the page's menus (js/core/layers.js): a row whose switch or menu is on the page comes where it stands there, the others (the Economy
  // tab's layers, the route plan) after them, as they come
  const at = (i) => { const e = doc && doc.getElementById(i.id); return e && /^(INPUT|SELECT)$/.test(e.tagName) ? e : null; };
  const inMenu = (items) => items.map((i, k) => [i, at(i), k]).sort((a, b) => a[1] && b[1] ? (a[1].compareDocumentPosition(b[1]) & 4 ? -1 : 1) : a[1] ? -1 : b[1] ? 1 : a[2] - b[2]).map(x => x[0]);
  function combine(...parts) {
    const owner = id => parts.find(p => p.list().some(i => i.id === id));
    return {
      list: () => inMenu(parts.flatMap(p => p.list())),
      turnOff: id => { const p = owner(id); if (p) p.turnOff(id); },
      off(id) {   // one layer's button; returns how many rows went with it (stops off: the walk rings are no longer drawn)
        const before = parts.flatMap(p => p.list()); if (!before.some(i => i.id === id)) return 0;
        this.turnOff(id); const left = new Set(parts.flatMap(p => p.list()).map(i => i.id));
        return Math.max(1, before.filter(i => !left.has(i.id)).length);
      },
      allOff() {   // all but the kept ones (the route plan); returns how many went off
        const off = parts.map(p => p.list().filter(i => !i.keep)), n = off.reduce((a, l) => a + l.length, 0);
        if (n) parts.forEach((p, k) => { if (p.clear) p.clear(); else off[k].forEach(i => p.turnOff(i.id)); });
        return n;
      },
      sig: () => parts.map(p => p.sig ? p.sig() : JSON.stringify(p.list())).join('|'),   // what is on: a change after "Turn all off" withdraws its Undo
      snapshot: () => parts.map(p => p.snapshot()),
      restore: s => parts.forEach((p, i) => p.restore(s[i])),
    };
  }

  // ── the map's message, with an optional button (Undo) that stays while pointed at or focused
  let tt = 0, tms = 0, ctl = null, undo = null;   // undo: what is on right after the action its message can undo
  const tEl = () => doc.getElementById('toast');
  const arm = () => { clearTimeout(tt); tt = setTimeout(hide, tms); };
  const refocus = () => { if (ctl) ctl.focusBack(); };   // never the page's body
  function hide() { clearTimeout(tt); undo = null; const t = tEl(); if (!t) return; const had = t.contains(doc.activeElement); t.classList.remove('show'); if (had) refocus(); changed(); }
  function toast(msg, ms = 3500, act) {
    const t = tEl(); if (!t) return;
    let b = doc.getElementById('toastAct');
    if (!b) {
      t.insertAdjacentHTML('beforeend', '<span class="toast-sep" aria-hidden="true" hidden>·</span><button type="button" class="toast-act" id="toastAct" hidden></button>');
      b = doc.getElementById('toastAct'); stopMap(t);
      t.addEventListener('mouseenter', () => clearTimeout(tt)); t.addEventListener('focusin', () => clearTimeout(tt));
      t.addEventListener('mouseleave', arm); t.addEventListener('focusout', arm);
    }
    const had = b === doc.activeElement && !act;
    undo = null;
    doc.getElementById('toastText').textContent = msg;
    b.hidden = b.previousElementSibling.hidden = !act;
    if (act) { b.textContent = act.label; b.onclick = () => { hide(); act.run(); }; }
    if (had) refocus();   // another message took the place of Undo
    t.classList.add('show'); tms = ms; if (!t.contains(doc.activeElement)) arm();
    changed();   // an open list moves below it
  }
  // a press here is not a press on the map (Leaflet and MapLibre listen on the map's element)
  const stopMap = el => ['click', 'dblclick', 'mousedown', 'pointerdown', 'touchstart', 'wheel', 'contextmenu'].forEach(t => el.addEventListener(t, e => e.stopPropagation()));

  // ── the chip and its list (WAI-ARIA disclosure) ──
  function changed() { if (ctl) ctl.update(); }
  // The open list ends above whatever sits lower on the map in its column: the map's buttons, scale and credits, the 3D time bar (always), and a legend (when the list keeps 140 px)
  const HARD = '.leaflet-control, .maplibregl-ctrl, #timebar', SOFT = '.map-legend.show, .econ-legend:not(.docked)';
  function room(panel, host) {
    const p = panel.getBoundingClientRect(), top = p.top, below = (sel) => [...host.querySelectorAll(sel), ...(sel === HARD ? [doc.getElementById('timebar')] : [])].filter(Boolean).map(e => e.getBoundingClientRect())
      .filter(r => r.height && r.width && r.top > top + 20 && r.left < p.right && r.right > p.left).map(r => r.top);
    const end = Math.min(host.getBoundingClientRect().bottom, ...below(HARD)), soft = Math.min(end, ...below(SOFT));
    return Math.max(96, (soft - top >= 140 ? soft : end) - top - 8);
  }
  function mount(adapter, host) {
    host.insertAdjacentHTML('afterbegin', `<div class="al" id="alWrap" data-no-glossary hidden><button type="button" class="al-chip" id="alChip" aria-expanded="false" aria-controls="alPanel"><span class="ms-icon" aria-hidden="true">layers</span><span class="al-n" aria-hidden="true"></span><span class="al-t"></span><span class="ms-icon al-chev" aria-hidden="true">keyboard_arrow_down</span></button><div class="al-panel" id="alPanel" hidden><p class="al-h">${esc(T('On the map'))}</p><div class="al-items"></div><div class="al-dock" id="alDock" hidden></div></div></div>`);
    const wrap = doc.getElementById('alWrap'), chip = doc.getElementById('alChip'), panel = doc.getElementById('alPanel'), box = panel.querySelector('.al-items'), dockEl = doc.getElementById('alDock');
    // On a wide screen the list stays open while a layer is on (navigation plan, decision 81: the "On the map" panel), unless folded with the chip this visit
    const wide = () => !!(root.matchMedia && root.matchMedia('(min-width: 1100px)').matches) && !(host.clientWidth && host.clientWidth < 820);   // and the map itself has the room: beside the widgets of the map workspace (css/ws.css) a 1,440 px window leaves it about 680 px, where the open list would cover half of it
    let folded = false; try { folded = root.sessionStorage.getItem('alFolded') === '1'; } catch { /* storage blocked: open by default */ }
    let queued = false, sig = null;
    stopMap(wrap);
    const isOpen = () => chip.getAttribute('aria-expanded') === 'true';
    const fit = () => {   // the open list starts below the message, if one shows (it sits under the chip), and ends above what is lower on the map
      if (!isOpen()) return;
      const t = tEl(), on = t && t.classList.contains('show');
      panel.style.marginTop = on ? Math.max(6, t.getBoundingClientRect().bottom - chip.getBoundingClientRect().bottom + 6) + 'px' : '';
      panel.style.maxHeight = ''; panel.style.maxHeight = room(panel, host) + 'px';
    };
    // ... and fitted again when what is below it changes size while it is open: the credits grow as the layers' sources load (3D: from 40 to 100 px; 2D at 390 px
    // they push the scale up), after the list was fitted. The controls themselves are watched: a corner of Leaflet's can keep no height of its own.
    const ro = root.ResizeObserver ? new root.ResizeObserver(() => fit()) : null;
    const watch = (on) => { if (!ro) return; ro.disconnect(); if (on) [...host.querySelectorAll(HARD), doc.getElementById('timebar')].filter(Boolean).forEach(e => ro.observe(e)); };
    const setOpen = (on) => { chip.setAttribute('aria-expanded', String(on)); panel.hidden = !on; wrap.classList.toggle('open', on); sig = null; watch(on); if (on) render(); };
    const focusBack = () => { const b = doc.getElementById('toastAct'); (!wrap.hidden ? chip : b && !b.hidden && tEl().classList.contains('show') ? b : host.matches('[tabindex]') ? host : host.querySelector('canvas') || host).focus(); };
    function build(items, every) {
      const kept = every.some(i => i.keep), all = every.some(i => !i.keep);
      box.innerHTML = `<ul class="al-list" aria-label="${esc(T('Layers on the map'))}">${items.map(i => `<li><span class="al-name">${esc(i.name)}${i.group ? `<small>${esc(i.group)}</small>` : ''}</span><button type="button" class="icon-btn small al-x" data-id="${esc(i.id)}" aria-label="${esc(T('Turn off {name}', { name: i.name }))}" title="${esc(T('Turn off {name}', { name: i.name }))}"><span class="ms-icon" aria-hidden="true">close</span></button></li>`).join('')}</ul>`
        + (kept ? `<p class="al-note">${esc(T('Turn all off keeps the planned route; use its × to remove it.'))}</p>` : '')
        + (all ? `<button type="button" class="btn small al-all">${esc(T('Turn all off'))}</button>` : '');
    }
    function render() {
      queued = false;
      const items = adapter.list(), n = items.length, had = wrap.contains(doc.activeElement);
      if (undo != null && adapter.sig() !== undo) hide();   // something changed since "Turn all off": its Undo would undo that too
      chip.querySelector('.al-n').textContent = n; chip.querySelector('.al-t').textContent = Tn(n, '{n} layer on', '{n} layers on', { n });   // the words of the layer menu's group counts
      wrap.hidden = !n; host.classList.toggle('al-on', !!n); wrap.classList.toggle('pinned', wide());
      if (n && wide() && !folded && !isOpen()) { setOpen(true); return; }
      if (!n) { if (isOpen()) setOpen(false); if (had) focusBack(); return; }
      const s = isOpen() && JSON.stringify(items); if (!s || s === sig) return fit();
      const at = had && doc.activeElement.classList.contains('al-x') ? [...panel.querySelectorAll('.al-x')].indexOf(doc.activeElement) : -1;
      const docked = !!(ctl && ctl.docked), ec = (i) => /^ec\d/.test(i.id);   // the Economy tab's layers show as their own cards in the dock
      dockEl.hidden = !(docked && items.some(ec));
      sig = s; build(docked ? items.filter(i => !ec(i)) : items, items); fit();
      if (at >= 0) { const x = panel.querySelectorAll('.al-x'); (x[Math.min(at, x.length - 1)] || panel.querySelector('.al-all') || chip).focus(); }
    }
    function off(ids) {   // one layer, or null for all, then a message with Undo
      const snap = adapter.snapshot(), n = ids ? ids.reduce((a, id) => a + adapter.off(id), 0) : adapter.allOff();
      if (!ids) setOpen(false);
      render();
      if (!n) return;
      toast(Tn(n, '{n} layer turned off', '{n} layers turned off', { n }), 10000, { label: T('Undo'), run: () => { adapter.restore(snap); render(); focusBack(); } });
      undo = adapter.sig(); fit();
      if (!ids || wrap.hidden) doc.getElementById('toastAct').focus();
    }
    chip.onclick = () => { const on = !isOpen(); setOpen(on); if (wide()) { folded = !on; try { root.sessionStorage.setItem('alFolded', folded ? '1' : '0'); } catch { /* not kept */ } } };
    panel.onclick = e => { const x = e.target.closest('.al-x'); if (x) off([x.dataset.id]); else if (e.target.closest('.al-all')) off(null); };
    wrap.addEventListener('keydown', e => { if (e.key === 'Escape' && isOpen()) { e.stopPropagation(); setOpen(false); chip.focus(); } });
    doc.addEventListener('pointerdown', e => { if (isOpen() && !wide() && !wrap.contains(e.target)) setOpen(false); }, true);   // a wide screen keeps it open
    doc.addEventListener('change', () => ctl.update(), true);   // capture: the change events code fires do not bubble
    root.addEventListener('resize', () => ctl.update());   // the room below the list
    const tl = doc.getElementById('tab-layers'), fr = tl && tl.foldRefresh;   // refreshFolds(): a layer switched without an event
    if (fr) tl.foldRefresh = () => { fr(); changed(); };
    ctl = { update() { if (!queued) { queued = true; Promise.resolve().then(render); } }, render, list: () => adapter.list(), count: () => adapter.list().length, off, adapter, focusBack, open: () => setOpen(true), docked: false };
    if (pend) dock(pend);
    render();
    return (root.ActiveLayers = ctl);
  }

  // The Economy tab's year, layer cards and buttons move into the panel once the tab has built them, with their handlers (economy.js econBoot)
  let pend = null;
  function dock(nodes) { const d = doc && doc.getElementById('alDock'); if (!d || !ctl) { pend = nodes; return; } pend = null; d.replaceChildren(...nodes.filter(Boolean)); ctl.docked = true; ctl.update(); }
  const api = { switches, select, econ, plan, state, combine, mount, changed, toast, hide, describe, dock };
  return api;
});
