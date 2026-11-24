/* PR Data Observatory core: the Knowledge areas (docs/knowledge-areas.md). AREAS is written by knowledge.py from knowledge_src/items.json.
   Each area page has <span class="ka-tabs" ... data-ka="<id>"></span> in its .toc bar and calls Core.knowledge.render() before I18N.apply():
   the header (decision 90, PR 2), the in-review message of an area that is not published (<main id="kaReview">) and the notice ([data-ka-note]).
   status: published | in_review | hidden; review: true keeps the marker on a published area (decision 51); ai: true adds the AI sentence (65). */
(function (name, root, factory) {
  const api = factory(root);
  if (typeof module === 'object' && module.exports) module.exports = api; else { root.Core = root.Core || {}; root.Core[name] = api; }
})('knowledge', typeof window !== 'undefined' ? window : globalThis, function (root) {
  'use strict';
  // <knowledge:areas> written by knowledge.py from knowledge_src/items.json: edit that file, then run python knowledge.py
  const AREAS = [
    { id: 'housing', label: { en: 'Housing', es: 'Vivienda' }, icon: 'home_work', page: 'housing.html', status: 'published', updated: '2026-10', domain: 'housing' },
    { id: 'wcrp', label: { en: 'WCRP', es: 'WCRP' }, icon: 'diversity_3', page: 'wcrp.html', status: 'published', review: true, updated: '2026-11', domain: 'communities' },
    { id: 'routes', label: { en: 'Transit congestion', es: 'Congestión en las rutas' }, icon: 'commute', page: 'route-analysis.html', status: 'published', review: true, ai: true, updated: '2026-10', domain: 'infrastructure.mobility' },
    { id: 'gii', label: { en: 'Global Innovation Index', es: 'Índice Global de Innovación' }, icon: 'rocket_launch', page: 'gii.html', status: 'published', review: true, ai: true, updated: '2026-10', domain: 'economy' },
    { id: 'women', label: { en: 'Women in the labor force', es: 'Mujeres en la fuerza laboral' }, icon: 'woman', page: 'women-labor.html', status: 'published', ai: true, updated: '2026-10', domain: 'economy' },
    { id: 'moneycycle', label: { en: 'How public money moves', es: 'Cómo se mueve el dinero público' }, icon: 'route', page: 'money-cycle.html', status: 'published', review: true, ai: true, reviewer: ['leadership'], updated: '2026-11', domain: 'public-money' },
    { id: 'publicmoney', label: { en: 'Disaster funding and need', es: 'Fondos por desastres y necesidad' }, icon: 'payments', page: 'public-money.html', status: 'published', review: true, ai: true, reviewer: ['compliance'], updated: '2026-11', domain: 'public-money' },
    { id: 'publicspending', label: { en: 'Budget and public spending', es: 'Presupuesto y gasto público' }, icon: 'account_balance', page: 'public-spending.html', status: 'published', ai: true, reviewer: ['leadership'], updated: '2026-11', domain: 'public-money' },
    { id: 'unusedfunds', label: { en: 'Balances, reductions and findings', es: 'Saldos, reducciones y hallazgos' }, icon: 'hourglass_bottom', page: 'unused-funds.html', status: 'published', review: true, ai: true, reviewer: ['compliance'], updated: '2026-11', domain: 'public-money' },
    { id: 'urbanheat', label: { en: 'Urban heat', es: 'Calor urbano' }, icon: 'thermostat', page: 'urban-heat.html', status: 'published', review: true, ai: true, updated: '2026-10', domain: 'environment' },
    { id: 'inflation', label: { en: 'Inflation', es: 'Inflación' }, icon: 'price_change', page: 'inflation.html', status: 'published', review: true, ai: true, updated: '2026-11', domain: 'economy' },
    { id: 'reservoirs', label: { en: 'Reservoirs', es: 'Embalses' }, icon: 'water', page: 'reservoirs.html', status: 'published', review: true, ai: true, updated: '2026-11', domain: 'infrastructure' },
    { id: 'broadband', label: { en: 'Broadband gaps', es: 'Dónde falta banda ancha' }, icon: 'wifi', page: 'broadband.html', status: 'published', review: true, ai: true, updated: '2026-11', domain: 'infrastructure' },
    { id: 'energy', label: { en: 'Energy', es: 'Energía' }, icon: 'bolt', page: 'energy.html', status: 'published', review: true, ai: true, updated: '2026-11', domain: 'infrastructure.energy' },
    { id: 'oppzones', label: { en: 'Opportunity Zones 2.0', es: 'Zonas de Oportunidad 2.0' }, icon: 'work', page: 'opportunity-zones.html', status: 'published', ai: true, updated: '2026-11', domain: 'economy' },
    { id: 'tlinks', label: { en: 'Connections between municipios', es: 'Conexiones entre municipios' }, icon: 'commute', page: 'transit-links.html', status: 'published', review: true, ai: true, updated: '2026-11', domain: 'infrastructure' },
  ];
  const TOPICS = { communities: { es: 'Comunidades', en: 'Communities' }, economy: { es: 'Economía', en: 'Economy' }, environment: { es: 'Ambiente y clima', en: 'Environment and climate' }, housing: { es: 'Vivienda', en: 'Housing' }, infrastructure: { es: 'Infraestructura y movilidad', en: 'Infrastructure and mobility' }, 'public-money': { es: 'Dinero público', en: 'Public money' } };
  const REVIEWER_NAMES = { compliance: { en: 'Compliance', es: 'Cumplimiento' }, leadership: { en: 'leadership', es: 'la dirección' } };
  // </knowledge:areas>
  const STATUSES = ['published', 'in_review', 'hidden'];

  const fill = (s, v) => String(s).replace(/\{(\w+)\}/g, (m, k) => v && k in v ? v[k] : m);
  const T = (s, v) => root.T ? root.T(s, v) : fill(s, v);   // the page's T (js/i18n.js), or plain English (Node tests)
  const esc = (s) => String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  const lang = () => root.I18N ? root.I18N.lang : 'en';
  const label = (a, l) => a.label[l || lang()] || a.label.en;

  /** The areas that have a tab, in order: every area that is not hidden. */
  const visible = (areas = AREAS) => areas.filter(a => a.status === 'published' || a.status === 'in_review');
  const find = (id, areas = AREAS) => areas.find(a => a.id === id) || null;
  /** Whether an area's tab carries the "In review" marker: an area in review, or a published area that keeps it (review: true). */
  const marked = (a) => a.status === 'in_review' || (a.status === 'published' && a.review === true);

  /** The body of an in-review area's page: its name, the marker, one message, and the way back (the first published area and the map). */
  function reviewHtml(id, opts = {}) {
    const areas = opts.areas || AREAS, l = opts.lang || lang(), a = find(id, areas), home = areas.find(x => x.status === 'published');
    if (!a) return '';
    return `<section class="hero ka-review-page" data-t="skip"><div class="eyebrow">${esc(T('Knowledge Area'))}</div>` +
      `<h1>${esc(label(a, l))} <span class="ka-mark">${esc(T('In review'))}</span></h1>` +
      `<p class="lede">${esc(T('This knowledge area is in review and will be published when the review is complete.'))}</p>` +
      `<p class="ka-links">${home ? `<a class="btn" href="${esc(home.page)}"><span class="ms-icon" aria-hidden="true">${esc(home.icon)}</span>${esc(T('Go to {area}', { area: label(home, l) }))}</a>` : ''}` +
      `<a class="btn" href="index.html"><span class="ms-icon" aria-hidden="true">map</span>${esc(T('Open the map'))}</a></p></section>`;
  }

  const NOTICE = '<b>In review:</b> the content of this page is under review and may change.', AI = 'Draft prepared with the help of Claude (artificial intelligence).';
  /** The notice (HTML) of a published area's page: the base sentence while marked, then the AI sentence; '' for none. */
  function notice(id, opts = {}) {
    const a = find(id, opts.areas || AREAS);
    if (!a || a.status !== 'published') return '';
    return [marked(a) ? T(NOTICE) : '', a.ai ? T(AI) : ''].filter(Boolean).join(' ');
  }

  // ── The header of an area page (Knowledge plan, decision 90, PR 2): it replaces the strip of tabs, so the page's own sections fit in the bar ──
  // ── The header of an area page (decision 90, PR 2), in place of the strip of tabs. TOPICS and REVIEWER_NAMES (generated above) carry no program
  // terms. The menu's panel and the foot are js/core/knowledge_more.js, loaded with js/knowledge_items.js after the page is ready. ──
  const ITEMS_V = 20, MORE_V = 1;   // ?v= of js/knowledge_items.js (as on knowledge.html) and of js/core/knowledge_more.js
  const DOMAINS = TOPICS, REVIEWERS = REVIEWER_NAMES;
  const top = (a) => String(a.domain || '').split('.')[0];
  const named = (o, l) => (o && (o[l] || o.en)) || '';
  const month = (ym, l) => { const m = /^(\d{4})-(\d\d)$/.exec(ym || ''); if (!m) return ''; try { return new Intl.DateTimeFormat(l === 'es' ? 'es-PR' : 'en-US', { month: 'long', year: 'numeric', timeZone: 'UTC' }).format(new Date(Date.UTC(+m[1], +m[2] - 1, 15))); } catch { return ym; } };
  /** "In review", with who reviews it, for an area that keeps the marker; '' otherwise. */
  function statusText(a, opts = {}) {
    if (!marked(a)) return '';
    const l = opts.lang || lang(), who = (a.reviewer || []).map(r => named((opts.reviewers || REVIEWERS)[r], l)).filter(Boolean);
    return who.length ? T('In review · {who}', { who: who.join(', ') }) : T('In review');
  }
  /** The header's HTML for the page of area `current`: Knowledge › its topic on the map, the "All areas" menu, its status and when it was updated. */
  function header(current, opts = {}) {
    const areas = opts.areas || AREAS, l = opts.lang || lang(), a = find(current, areas), doms = opts.domains || DOMAINS;
    if (!a) return '';
    const st = statusText(a, opts), upd = a.status === 'published' && a.updated ? T('Updated {month}', { month: month(a.updated, l) }) : '';
    return `<a class="ka-home" href="knowledge.html" data-t="skip"><span class="ms-icon" aria-hidden="true">lightbulb</span>${esc(T('Knowledge'))}</a>` +
      `<span class="ka-crumb" aria-hidden="true">›</span>` +
      `<a class="ka-topic" href="index.html#topic=${esc(top(a))}" title="${esc(T('This topic on the map'))}" data-t="skip"><span class="ms-icon" aria-hidden="true">map</span>${esc(named(doms[top(a)], l) || T('This topic on the map'))}</a>` +
      `<details class="ka-menu" data-t="skip" data-ka-menu="${esc(current)}"><summary>${esc(T('All areas'))}</summary><div class="ka-menu-panel"></div></details>` + (st ? `<span class="ka-mark ka-status">${esc(st)}</span>` : '') + (upd ? `<span class="ka-upd">${esc(upd)}</span>` : '');
  }

  /** Draws the header of the page's area into its .ka-tabs group (its menu panel and foot follow after the page is ready), the in-review message when the page's own area
      is not published (in review or hidden), and the notice into [data-ka-note]. Call it before I18N.apply(). */
  function render(doc = root.document) {
    if (!doc) return;
    let own = null;
    doc.querySelectorAll('.ka-tabs[data-ka]').forEach(el => { own = el.getAttribute('data-ka'); el.innerHTML = header(own); });
    const a = own && find(own), main = doc.getElementById('kaReview');
    const more = (then) => {   // the menu's panel and the foot: after the page is ready, or at once when the menu is opened first
      if (root.Core && root.Core.knowledge && root.Core.knowledge.more) { if (then) then(); return; }
      if (render.waiting) { if (then) render.waiting.push(then); return; }
      render.waiting = then ? [then] : [];
      const add = (src, done) => { const el = doc.createElement('script'); el.src = src; el.onload = done; doc.body.appendChild(el); };
      add('js/knowledge_items.js?v=' + ITEMS_V, () => add('js/core/knowledge_more.js?v=' + MORE_V, () => render.waiting.forEach(f => f())));
    };
    if (a && doc.createElement && !render.wired) {
      if (doc.readyState === 'complete') setTimeout(() => more(), 0); else root.addEventListener('load', () => more(), { once: true });
      doc.querySelectorAll('details.ka-menu').forEach(d => d.addEventListener('toggle', () => { if (d.open) more(() => root.Core.knowledge.more.fill(d)); }));
    }
    if (doc.addEventListener && !render.wired) {   // the menu closes on Escape and on a click outside it
      render.wired = true;
      doc.addEventListener('click', e => doc.querySelectorAll('details.ka-menu[open]').forEach(d => { if (!d.contains(e.target)) d.open = false; }));
      doc.addEventListener('keydown', e => { if (e.key === 'Escape') doc.querySelectorAll('details.ka-menu[open]').forEach(d => { d.open = false; const s = d.querySelector('summary'); if (s) s.focus(); }); });
    }
    if (a && a.status !== 'published' && main) {
      main.innerHTML = reviewHtml(a.id);
      doc.title = `${T('Knowledge Area')} · ${label(a)} · ${T('In review')}`;
    }
    doc.querySelectorAll('[data-ka-note]').forEach(el => {
      const html = a ? notice(a.id) : '';
      if (!html) { el.remove(); return; }
      el.setAttribute('data-t', 'skip');
      el.innerHTML = `<span class="ms-icon" aria-hidden="true">warning</span><span>${html}</span>`;
    });
  }

  return { AREAS, STATUSES, DOMAINS, REVIEWERS, NOTICE, AI, visible, find, marked, label, header, statusText, reviewHtml, notice, render };
});
