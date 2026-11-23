/* PR Data Observatory core: the in-page glossary (docs/glossary.md). It underlines, with a dotted line, the first occurrence of each technical term in each section of a
   page, and shows the term's definition, its source and a link to the dictionary's Glossary when the reader points at the word, focuses it with the keyboard or taps it.
   The terms are dictionary_src/glossary.json; dictionary.py writes the two files this module reads: data/glossary_forms_<lang>.json (the match forms, fetched just after the
   page is ready) and data/glossary_defs_<lang>.json (the definitions, fetched the first time a reader points at a word). The dictionary page reads both from its own copy of
   the glossary (dictionary_list.json). common.js loads this file when the page has its data and the browser is idle, so it is never part of a page's first load.

     formCs(term, form)          whether a match form is compared with its capitals (dictionary.py glossary_form_cs)
     formsFrom(glossary, lang)   the highlighted terms' forms, as glossary_forms_<lang>.json holds them;  defsFrom(glossary, lang): the tooltips' text, as glossary_defs_<lang>.json
     compile(terms)              a matcher: find(text) gives [start, end, id] for each match, the longest form first, whole words only
     skipped(el), inControl(el), sectionOf(el)  the skip rules (inControl: the part of them that also binds a mark on purpose) and the section a text counts in; they read tagName, id, classes and attributes only, so the Node tests use plain objects
     plan(nodes, matchers, ctx)  which matches to mark in a list of text nodes: the first occurrence of each term in each section
     tipHtml(d, id, opts)        the tooltip's markup
     mark(root), observe(root)   in a page: mark a container now, or watch it for content drawn later (pop-ups, panels, legends, entries)
   Turning the underlines off (the tooltip's "Hide the underlines", the switch in the dictionary's Glossary) is kept in localStorage ('twin.gloss'). */
(function (name, root, factory) {
  const api = factory(root);
  if (typeof module === 'object' && module.exports) module.exports = api;
  else { root.Core = root.Core || {}; root.Core[name] = api; if (root.document) api.boot(); }
})('glossary', typeof window !== 'undefined' ? window : globalThis, function (root) {
  'use strict';
  const fill = (s, v) => String(s).replace(/\{(\w+)\}/g, (m, k) => v && k in v ? v[k] : m);
  const T = (k, v) => root.T ? root.T(k, v) : fill(k, v);
  const esc = (s) => s == null ? '' : String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  const safeHref = (u) => { try { const x = new URL(u, root.location ? root.location.href : 'https://example.org/'); return /^https?:$/.test(x.protocol) ? x.href : null; } catch (e) { return null; } };
  const nrm = (s) => String(s || '').normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase().trim();   // common.js norm()

  // ── The data: the same structures dictionary.py writes ─────────────────────
  const formCs = (term, f) => !!term.case_sensitive || (f === f.toUpperCase() && f.replace(/[^A-Z]/g, '').length >= 2);
  // A phrase in not_match holds a form but is not the term ("por residente empleado" is not per capita): it is kept with a "!" in front, and where it is the longest
  // match nothing is marked.
  function formsFrom(glossary, lang) {
    return glossary.filter(g => g.highlight).map(g => {
      const not = ((g.not_match || {})[lang] || []), forms = [...g.match[lang], ...not.map(f => '!' + f)];
      return [g.id, forms, [...g.match[lang], ...not].map(f => formCs(g, f) ? 1 : 0)];
    });
  }
  function shown(g, lang) {   // the name and the expansion, as the dictionary's Glossary section shows them: the expansion only when the name does not hold it
    const es = lang === 'es', name = (es && g.term_es) || g.term, exp = (es && g.expansion_es) || g.expansion || '';
    return [name, exp && nrm(name).includes(nrm(exp)) ? '' : exp];
  }
  function defsFrom(glossary, lang) {   // {id: [name, expansion, definition, source name, url, date checked, english]}; english: 1 the definition, 2 the expansion, 4 the source's name
    const es = lang === 'es', out = {};
    for (const g of glossary) {
      const [n, exp] = shown(g, lang), s = g.source || {};
      out[g.id] = [n, exp, (es && g.plain_es) || g.plain, (es && s.name_es) || s.name || '', s.url || '', s.checked || '', (es && !g.plain_es ? 1 : 0) | (es && exp && !g.expansion_es ? 2 : 0) | (es && !s.name_es ? 4 : 0)];
    }
    return out;
  }

  // ── The matcher ────────────────────────────────────────────────────────────
  // A form's first or last character that is a letter or a digit must not touch another letter or digit (accented letters are letters), so "rate" is not found in
  // "separate". An edge that is punctuation needs no boundary: ".geojson" is found at the end of "flood.geojson", and the mark then covers the whole file name.
  // The forms are kept in two letter trees (one compared in lower case, one with its capitals), so a text is read once, with no large regular expression to compile.
  const EDGE = /[\p{L}\p{N}\p{M}]/u, WORD_START = /^[\p{L}\p{N}]/u, WORD_END = /[\p{L}\p{N}]$/u, SPACE = /\s/, FILE_CH = /[^\s()[\]{}"'“”‘’«»,;:<>]/;
  const WC = new Map();
  function isWord(s, i) {   // a letter, a digit or a combining mark, with a quick answer for plain ASCII
    const c = s.charCodeAt(i);
    if (c < 128) return (c >= 48 && c <= 57) || (c >= 65 && c <= 90) || (c >= 97 && c <= 122);
    if (c !== c) return false;   // past the end
    const ch = s[i]; let v = WC.get(ch); if (v === undefined) { v = EDGE.test(ch); WC.set(ch, v); }
    return v;
  }
  const isSpace = (s, i) => { const c = s.charCodeAt(i); return c === 32 || (c >= 9 && c <= 13) || c === 160 || (c > 127 && SPACE.test(s[i])); };
  const lower = (s) => { const l = s.toLowerCase(); return l.length === s.length ? l : [...s].map(c => { const x = c.toLowerCase(); return x.length === c.length ? x : c; }).join(''); };   // the same length, so offsets stay right
  function compile(terms) {
    const trees = [new Map(), new Map()];   // [compared in lower case, compared with its capitals]; a node is a Map of characters, a space stands for any run of white space
    let size = 0;
    for (const [id, forms, cs] of terms) forms.forEach((f0, k) => {
      const not = f0[0] === '!', f = not ? f0.slice(1) : f0, c = cs[k] ? 1 : 0, s = c ? f : lower(f);
      let node = trees[c];
      for (let i = 0; i < s.length; i++) {
        let ch = s[i];
        if (SPACE.test(ch)) { while (i + 1 < s.length && SPACE.test(s[i + 1])) i++; ch = ' '; }
        if (!node.has(ch)) node.set(ch, new Map());
        node = node.get(ch);
      }
      node.id = id; node.not = not; node.edge = WORD_END.test(f); node.dot = !WORD_START.test(f); if (!not) size++;
    });
    function longest(tree, s, p) {   // the longest form that starts at p and ends on a word edge: [end, node]
      let node = tree.get(s[p]), i = p + 1, best = null;   // no form starts with a space
      while (node) {
        if (node.id != null && (!node.edge || !isWord(s, i))) best = [i, node];
        if (i >= s.length) break;
        if (isSpace(s, i)) { node = node.get(' '); i++; while (i < s.length && isSpace(s, i)) i++; } else node = node.get(s[i++]);
      }
      return best;
    }
    function find(text) {
      const low = lower(text), out = [], t0 = trees[0], t1 = trees[1];
      for (let p = 0; p < text.length; p++) {
        if (!t0.has(low[p]) && !t1.has(text[p])) continue;   // no form starts with this character
        const word = isWord(text, p);
        if (word && p > 0 && isWord(text, p - 1)) continue;   // inside a word: a form starts only at the start of a word, or at punctuation (".geojson")
        const a = longest(trees[0], low, p), b = longest(trees[1], text, p), m = a && b ? (b[0] > a[0] ? b : a) : a || b;
        if (!m || (word && !WORD_START.test(text[p]))) continue;
        if (m[1].not) { p = m[0] - 1; continue; }   // a phrase that is not the term: read past it
        let start = p;
        if (m[1].dot) {   // a file extension: the mark covers the whole file name, and takes the place of a match inside it
          while (start > 0 && FILE_CH.test(text[start - 1])) start--;
          while (out.length && out[out.length - 1][1] > start) out.pop();
        }
        out.push([start, m[0], m[1].id]);
        p = m[0] - 1;
      }
      return out;
    }
    return { find, size };
  }

  // ── What is skipped, and the section a text counts in ──────────────────────
  // Headings, controls, links, labels, code, the chat, map labels and controls, icons and screen-reader-only text are never marked; nor is anything under
  // [data-gloss="off"], [data-no-glossary], translate="no" or aria-hidden="true". An element marked on purpose (data-gloss="<term id>") is marked by markExplicit, even inside a heading.
  // A mark is a focusable button: inside a control it would be a second Tab stop and a focusable inside a focusable, so every interactive control and role is skipped.
  const SKIP_TAGS = new Set(['H1', 'H2', 'H3', 'H4', 'H5', 'H6', 'A', 'BUTTON', 'INPUT', 'SELECT', 'TEXTAREA', 'LABEL', 'OPTION', 'OPTGROUP', 'SUMMARY', 'LEGEND', 'DT', 'CAPTION', 'CODE', 'KBD', 'PRE', 'SAMP', 'VAR', 'SCRIPT', 'STYLE', 'NOSCRIPT', 'TEMPLATE', 'SVG', 'CANVAS', 'IFRAME', 'OBJECT', 'TITLE', 'HEAD', 'MATH', 'AUDIO', 'VIDEO']);
  const SKIP_ROLES = new Set(['button', 'link', 'tab', 'menuitem', 'menuitemcheckbox', 'menuitemradio', 'option', 'switch', 'checkbox', 'radio', 'tooltip', 'combobox', 'listbox', 'slider', 'spinbutton', 'textbox', 'searchbox', 'heading', 'treeitem', 'img']);
  const SKIP_CLASSES = new Set(['ms-icon', 'sr-only', 'gl-mark', 'gl-tip', 'side-h', 'leaflet-control-container', 'leaflet-control', 'maplibregl-ctrl', 'maplibregl-canvas-container', 'maplibregl-marker', 'muni-label', 'hover-info', 'econ-hover', 'tooltip', 'lang-switch', 'map-toast', 'loader', 'search-results', 'skip', 'dm-tip']);
  const SKIP_IDS = new Set(['chat', 'gl-tip', 'hoverInfo', 'econHover', 'tip', 'loader', 'toast', 'searchResults']);
  const attr = (el, a) => el.getAttribute ? el.getAttribute(a) : null;
  const hasClass = (el, c) => !!(el.classList && el.classList.contains(c));
  function ownSkip(el) {   // it reads each class and each attribute once: this runs for every element of a page
    if (SKIP_TAGS.has(String(el.tagName || '').toUpperCase()) || (el.id && SKIP_IDS.has(el.id))) return true;
    let pane = false;
    if (el.classList) for (const c of el.classList) {
      if (SKIP_CLASSES.has(c)) return true;
      if (c === 'leaflet-pane') pane = pane || 1; else if (c === 'leaflet-popup-pane' || c === 'leaflet-map-pane') pane = 2;
    }
    if (pane === 1) return true;   // Leaflet's panes hold the map's tiles, shapes, markers and labels; its pop-ups are content (the pop-up pane, inside the map pane)
    const at = el.attributes || [];
    for (let i = 0; i < at.length; i++) {
      const n = at[i].name, v = at[i].value;
      if (n === 'data-gloss' || n === 'data-no-glossary' || (n === 'role' && SKIP_ROLES.has(v)) || (n === 'aria-hidden' && v === 'true') || (n === 'translate' && v === 'no') || (n === 'contenteditable' && v !== 'false')) return true;
    }
    return false;
  }
  // An element marked on purpose (data-gloss="<term id>") may sit in a heading, but never in or under a control or a part opted out with data-no-glossary:
  // the same reason as above (a mark is a focusable button). Headings, code and the other non-interactive skips do not stop it.
  const CONTROL_TAGS = new Set(['A', 'BUTTON', 'INPUT', 'SELECT', 'TEXTAREA', 'LABEL', 'OPTION', 'OPTGROUP', 'SUMMARY']);
  const NOT_CONTROL_ROLES = new Set(['heading', 'img', 'tooltip']);
  function inControl(el) {
    for (let e = el; e && e.nodeType === 1; e = e.parentNode) {
      if (CONTROL_TAGS.has(String(e.tagName || '').toUpperCase()) || attr(e, 'data-no-glossary') != null) return true;
      const r = attr(e, 'role'), ce = attr(e, 'contenteditable');
      if ((r && SKIP_ROLES.has(r) && !NOT_CONTROL_ROLES.has(r)) || (ce != null && ce !== 'false')) return true;
    }
    return false;
  }
  function skipped(el, cache) {
    if (!el || el.nodeType !== 1) return false;
    if (cache && cache.has(el)) return cache.get(el);
    const v = ownSkip(el) || skipped(el.parentNode, cache);
    if (cache) cache.set(el, v);
    return v;
  }
  const SECTION_TAGS = new Set(['SECTION', 'ARTICLE', 'DETAILS', 'ASIDE', 'DIALOG', 'MAIN', 'NAV', 'HEADER', 'FOOTER', 'FIELDSET', 'BODY']);
  const SECTION_CLASSES = new Set(['tab-page', 'fold', 'legend-box', 'map-legend', 'econ-legend', 'leaflet-popup-content', 'maplibregl-popup-content', 'help-pop', 'src-card', 'de-body', 'pf-sec', 'dom']);
  function isSection(e) {
    if (SECTION_TAGS.has(String(e.tagName || '').toUpperCase()) || attr(e, 'data-gloss-root') != null) return true;
    if (e.classList) for (const c of e.classList) if (SECTION_CLASSES.has(c)) return true;
    return String(e.tagName).toUpperCase() === 'DD' && hasClass(e.parentNode || {}, 'gl-dl');   // each term of the dictionary's Glossary
  }
  function sectionOf(el, cache) {   // data-gloss-root="one": the element is one section, the sections inside it included (the dictionary's list of sources)
    if (!el || el.nodeType !== 1) return null;
    if (cache && cache.has(el)) return cache.get(el);
    const up = sectionOf(el.parentNode, cache), v = up && attr(up, 'data-gloss-root') === 'one' ? up : isSection(el) ? el : up;
    if (cache) cache.set(el, v);
    return v;
  }
  function selfOf(sec) {   // the term a section defines, which it does not mark (a term's own definition in the Glossary)
    if (!sec) return null;
    const own = attr(sec, 'data-gloss-self'); if (own) return own;
    const dt = String(sec.tagName).toUpperCase() === 'DD' && sec.previousElementSibling;
    return dt && /^g-/.test(dt.id || '') ? dt.id.slice(2) : null;
  }
  function langOf(el, cache) {   // the nearest lang attribute: English text on a Spanish page is matched with the English forms when the page has them
    if (!el || el.nodeType !== 1) return '';
    if (cache && cache.has(el)) return cache.get(el);
    const l = attr(el, 'lang'), v = l ? l.slice(0, 2).toLowerCase() : langOf(el.parentNode, cache);
    if (cache) cache.set(el, v);
    return v;
  }
  const newCtx = (existing) => ({ skip: new WeakMap(), sec: new WeakMap(), lang: new WeakMap(), seen: new Map(), existing: existing || (() => []), done: new WeakSet() });
  function seenOf(ctx, sec) {
    let s = ctx.seen.get(sec);
    if (!s) { s = new Set(ctx.existing(sec)); ctx.seen.set(sec, s); }
    return s;
  }
  const HAS_LETTERS = /\p{L}{2}/u;
  /** For text nodes in document order: [[node, [[start, end, id], ...]], ...], the first occurrence of each term in each section, never a term the section already marks.
      matchers: {lang: matcher, default: matcher}. ctx: newCtx(existing), where existing(section) lists the ids already marked there; ctx.hidden(el), when set, says
      that an element is not shown (its text waits). */
  function plan(nodes, matchers, ctx) {
    const out = [];
    for (const n of nodes) {
      if (ctx.done.has(n)) continue;
      const el = n.parentNode, t = n.nodeValue;
      if (el && ctx.hidden && ctx.hidden(el)) continue;   // not shown: read again when it shows (the pages watch the hidden attribute)
      ctx.done.add(n);
      if (!el || !t || !HAS_LETTERS.test(t) || skipped(el, ctx.skip)) continue;
      const m = matchers[langOf(el, ctx.lang)] || matchers.default; if (!m) continue;
      const sec = sectionOf(el, ctx.sec), seen = seenOf(ctx, sec), self = selfOf(sec), picks = [];
      for (const x of m.find(t)) if (!seen.has(x[2]) && x[2] !== self) { seen.add(x[2]); picks.push(x); }
      if (picks.length) out.push([n, picks]);
    }
    return out;
  }

  // ── The tooltip's markup ───────────────────────────────────────────────────
  /** d: a glossary_defs entry [name, expansion, definition, source name, url, checked, english]. opts: { href (the glossary link), date (formats the date checked) }. */
  function tipHtml(d, id, opts = {}) {
    const [n, exp, def, src, url, checked, en] = d, L = (bit, html) => en & bit ? `<span lang="en">${html}</span>` : html, href = url && safeHref(url);
    return `<p class="gl-term"><b>${esc(n)}</b>${exp ? ` <span class="gl-exp">${L(2, esc(exp))}</span>` : ''}</p>`
      + `<p class="gl-def">${L(1, esc(def))}</p>`
      + (href ? `<p class="gl-src">${esc(T('Source:'))} <a href="${esc(href)}" target="_blank" rel="noopener">${L(4, esc(src))}</a>${checked ? ` <span class="gl-chk">· ${esc(T('link checked {date}', { date: opts.date ? opts.date(checked) : checked }))}</span>` : ''}</p>` : '')
      + (opts.lesson ? `<p class="gl-lesson"><a href="learn.html#lesson-${esc(opts.lesson[0])}">${esc(T('Lesson: {title}', { title: opts.lesson[1] }))}</a></p>` : '')
      + `<p class="gl-foot"><a href="${esc(opts.href || 'dictionary.html#g-' + id)}">${esc(T('See in the glossary'))}</a><button type="button" class="gl-hide">${esc(T('Hide the underlines'))}</button></p>`
      + `<button type="button" class="gl-close" aria-label="${esc(T('Close'))}"><span aria-hidden="true">×</span></button>`;   // last, so the description a screen reader reads starts with the term
  }

  const api = { formCs, formsFrom, defsFrom, compile, skipped, inControl, sectionOf, selfOf, plan, newCtx, tipHtml, boot: () => {}, state: 'off', marks: 0, stats: { slices: 0, ms: 0, maxMs: 0, firstMs: null } };
  if (!root.document) return api;

  // ── In a page ──────────────────────────────────────────────────────────────
  const doc = root.document, STORE = 'twin.gloss';
  const isOff = () => { try { return root.localStorage.getItem(STORE) === 'off'; } catch (e) { return false; } };
  const setOff = (off) => { try { if (off) root.localStorage.setItem(STORE, 'off'); else root.localStorage.removeItem(STORE); } catch (e) { /* a private window: the choice lasts for this page */ } };
  const now = () => root.performance.now();
  const idle = (f) => root.requestIdleCallback ? root.requestIdleCallback(f, { timeout: 1500 }) : setTimeout(() => f(null), 30);
  const dictGlossary = () => { try { return typeof D !== 'undefined' && D && D.data && Array.isArray(D.data.glossary) ? D.data.glossary : null; } catch (e) { return null; } };   // the dictionary page's own copy (dictionary.js)
  const lang = () => (root.I18N && root.I18N.lang) || 'en';
  const S = { on: false, matchers: null, forms: null, defs: null, defsP: null, queue: new Set(), timer: 0, work: null, done: new WeakSet(), quiet: new WeakSet(), obs: [], busyUntil: 0, dragging: false, tip: null, cur: null, pinned: false, hoverT: 0, hideT: 0, first: true };
  // Content containers whose content is drawn later (the side panel, the legends, the workbench and dialogs, every page's main but the maps', the dictionary's lists and
  // entries, the help pop-up). The map pop-ups come through Leaflet's and MapLibre's own update (hookMaps), not through an observer, so a moving map is never watched.
  const ROOTS = '#panel, .map-legend, .econ-legend, .econ-bench, dialog, .help-pop, main:not(#map), .dict-side';

  const CSS = `.gl-mark{text-decoration-line:underline;text-decoration-style:dotted;text-decoration-color:var(--color-primary-dark,#205D7B);text-decoration-thickness:1.5px;text-underline-offset:.2em;text-decoration-skip-ink:none;cursor:help;border-radius:2px}
.gl-mark:hover,.gl-mark.gl-on{background:rgba(51,140,179,.13)}
.gl-mark:focus-visible{outline:2px solid var(--color-primary,#338CB3);outline-offset:1px}
.gl-tip{position:fixed;z-index:4000;left:0;top:0;box-sizing:border-box;width:max-content;max-width:min(340px,calc(100vw - 32px));max-height:calc(100vh - 32px);overflow:auto;margin:0;padding:10px 32px 10px 12px;background:var(--color-surface,#fff);color:var(--color-text,#2A2E2E);border:1px solid var(--color-border,#E6E6E6);border-radius:var(--radius-md,10px);box-shadow:var(--shadow-lg,0 8px 24px rgba(42,46,46,.16));font:400 13px/1.45 var(--font,system-ui,sans-serif);text-align:left;letter-spacing:normal;text-transform:none;white-space:normal;overflow-wrap:break-word}
.gl-tip[hidden]{display:none}
.gl-tip p{margin:0 0 6px}
.gl-tip .gl-term b{color:var(--color-primary-dark,#205D7B);font-weight:600}
.gl-tip .gl-exp,.gl-tip .gl-src,.gl-tip .gl-foot{color:var(--color-text-muted,#666)}
.gl-tip .gl-src,.gl-tip .gl-foot{font-size:12px}
.gl-tip .gl-lesson{font-size:12px;font-weight:600;margin:0 0 6px}
.gl-tip .gl-foot{display:flex;flex-wrap:wrap;gap:4px 14px;align-items:center;margin:0}
.gl-tip a{color:var(--color-primary-strong,#2A7699);text-decoration:underline}
.gl-tip button{font:inherit;background:none;border:0;padding:0;margin:0;color:inherit;cursor:pointer}
.gl-tip .gl-hide{text-decoration:underline}
.gl-tip .gl-close{position:absolute;top:4px;right:4px;width:26px;height:26px;font-size:18px;line-height:26px;border-radius:6px;color:var(--color-text-muted,#666)}
.gl-tip .gl-close:hover{background:var(--color-bg,#F2F2F2)}
.gl-switch{display:flex;flex-wrap:wrap;gap:4px 10px;align-items:center;margin:8px 0 12px;font-size:13px}
.gl-switch label{display:inline-flex;gap:6px;align-items:center;font-weight:500;cursor:pointer}
.gl-switch small{color:var(--color-text-muted,#666)}
@media print{.gl-mark{text-decoration:none;background:none}.gl-tip{display:none!important}}`;

  function setup() {
    if (!doc.getElementById('gl-css')) { const st = doc.createElement('style'); st.id = 'gl-css'; st.textContent = CSS; doc.head.appendChild(st); }
    let t = doc.getElementById('gl-tip');
    if (!t) { t = doc.createElement('div'); t.id = 'gl-tip'; t.className = 'gl-tip'; t.setAttribute('role', 'tooltip'); t.hidden = true; doc.body.appendChild(t); }   // exists from the start, so every mark's aria-describedby resolves
    S.tip = t;
  }

  // ── Marking ────────────────────────────────────────────────────────────────
  const existingIn = (sec) => [...(sec || doc.body).querySelectorAll('.gl-mark')].filter(m => sectionOf(m.parentNode, S.ctx.sec) === sec).map(m => m.dataset.gl);
  function queue(node) { if (S.on && node) { S.queue.add(node); schedule(); } }
  function schedule(ms = 150) { if (!S.timer && !S.work) S.timer = setTimeout(run, ms); }
  const busy = () => S.dragging || now() < S.busyUntil;
  function run() { if (S.on) idle(slice); else S.timer = 0; }   // S.timer stays set until the slice runs, so a pass is never asked for twice
  function startWork() {   // the containers queued since the last pass; their text is read a little at a time (next)
    const roots = [...S.queue]; S.queue.clear();
    S.ctx = newCtx(existingIn); S.ctx.done = S.done; S.ctx.disp = new WeakMap(); S.ctx.hidden = (el) => displayOf(el) === 'none';
    S.work = { roots, r: 0, walker: null, nodes: [] };
  }
  function next(W, max) {   // up to max text nodes, in document order, never inside a skipped element
    const out = [];
    while (out.length < max) {
      if (W.nodes.length) { out.push(W.nodes.shift()); continue; }
      if (W.walker) { const n = W.walker.nextNode(); if (n) { if (!S.done.has(n)) out.push(n); continue; } W.walker = null; }
      if (W.r >= W.roots.length) break;
      const r = W.roots[W.r++];
      if (!r.isConnected) continue;
      if (r.nodeType === 3) { W.nodes.push(r); continue; }
      if (r.nodeType !== 1 || skippedAbove(r)) continue;
      const ex = r.matches('[data-gloss]') ? [r] : []; ex.push(...r.querySelectorAll('[data-gloss]'));
      ex.forEach(markExplicit);
      const sk = S.ctx.skip;   // under a root that is not skipped, an element is skipped exactly when it is skipped itself: the walker fills the cache that plan() reads
      if (!ownSkip(r)) W.walker = doc.createTreeWalker(r, 5 /* elements and text */, { acceptNode: (n) => { if (n.nodeType === 3) return 1; const v = ownSkip(n); sk.set(n, v); return v ? 2 /* the whole subtree is left out */ : 3 /* look inside */; } });
    }
    return out;
  }
  const skippedAbove = (el) => skipped(el.parentNode, S.ctx.skip);
  function displayOf(el) { const c = S.ctx.disp; let d = c.get(el); if (d === undefined) { d = root.getComputedStyle(el).display; c.set(el, d); } return d; }   // read before the slice writes
  function slice(deadline) {
    S.timer = 0;
    if (!S.on) { S.work = null; return; }
    if (busy()) { S.timer = setTimeout(run, 300); return; }   // never while the page scrolls or a map is dragged or zoomed
    const t0 = now(), st = api.stats;
    if (!S.work) startWork();
    const W = S.work;
    pending();   // the page's own changes made before this slice are queued for the next pass, not lost
    let more = true;
    const todo = [];
    while (now() - t0 < 6 && (!deadline || deadline.didTimeout || deadline.timeRemaining() > 3)) {   // about 8 ms at a time with the writing, in the browser's idle time
      const batch = next(W, 40); if (!batch.length) { more = false; break; }
      todo.push(...plan(batch.filter(n => n.isConnected), S.matchers, S.ctx));
    }
    const box = todo.map(([n]) => /flex|grid/.test(displayOf(n.parentNode)));   // every box is read before anything is written: one style pass
    todo.forEach(([n, picks], k) => wrap(n, picks, box[k]));
    S.obs.forEach(o => o.takeRecords());   // the marks' own changes
    const ms = now() - t0; st.slices++; st.ms += ms; st.maxMs = Math.max(st.maxMs, ms);
    if (more) { idle(slice); return; }
    S.work = null;
    if (S.first) { S.first = false; api.state = 'on'; st.firstMs = Math.round(st.ms * 10) / 10; }
    api.marks = doc.querySelectorAll('.gl-mark').length;
    if (S.queue.size) schedule(50);
  }
  function wrap(node, picks, box) {
    if (box) {   // in a flex or grid box a text is one item: it stays one item (a plain span), or each mark would become an item of its own and move
      const run = doc.createElement('span'); run.className = 'gl-run'; node.parentNode.insertBefore(run, node); run.appendChild(node);
    }
    for (let k = picks.length - 1; k >= 0; k--) {   // from the end, so the earlier offsets stay right
      const [a, b, id] = picks[k], mid = a > 0 ? node.splitText(a) : node, after = mid.splitText(b - a);
      S.done.add(mid); S.done.add(after);
      mid.parentNode.insertBefore(markEl(id), mid).appendChild(mid);
    }
  }
  function markEl(id) {
    const s = doc.createElement('span');
    s.className = 'gl-mark'; s.tabIndex = 0; s.setAttribute('role', 'button'); s.dataset.gl = id;   // aria-describedby only while its tooltip is open (show)
    return s;
  }
  /** An element marked on purpose (data-gloss="<term id>"): the term's first form found in its text, or else its whole text. */
  function markExplicit(el) {
    const id = el.getAttribute('data-gloss');
    if (!id || id === 'off' || inControl(el) || el.querySelector('.gl-mark') || (S.defsIds && !S.defsIds.has(id))) return;   // the skip rule of controls and data-no-glossary holds here too
    const t = S.forms.get(id), m = t ? compile([t]) : null;
    const texts = []; const w = doc.createTreeWalker(el, 4); for (let n; (n = w.nextNode());) if (!(n.parentNode.closest && n.parentNode.closest('.ms-icon,small'))) texts.push(n);
    for (const n of texts) { const f = m && m.find(n.nodeValue)[0]; if (f) { S.done.add(n); wrap(n, [f], /flex|grid/.test(root.getComputedStyle(n.parentNode).display)); return; } }
    const move = [...el.childNodes].filter(n => !(n.nodeType === 1 && n.matches('.ms-icon,small')));
    if (!move.length) return;
    const s = markEl(id); el.insertBefore(s, move[0]); move.forEach(n => s.appendChild(n));
  }
  function pending() { S.obs.forEach(o => onMut(o.takeRecords())); }
  function onMut(recs) {
    for (const r of recs) {
      const t = r.target;
      if (S.quiet.has(t)) continue;
      if (t.nodeType === 1 && skipped(t, S.quietCache)) { if (!t.querySelector || !t.querySelector('[data-gloss]')) { S.quiet.add(t); continue; } }   // text a script rewrites in a skipped place (a clock, a slider's label)
      if (r.type === 'attributes') { if (!t.hidden) S.queue.add(t); continue; }   // a part that shows (a layer group opened, a note shown)
      for (const n of r.addedNodes) if (n.nodeType === 3 ? !S.done.has(n) : n.nodeType === 1 && !hasClass(n, 'gl-mark') && n.id !== 'gl-tip') S.queue.add(n);
    }
    if (S.queue.size) schedule();
  }
  function observe(el) {
    if (!el || el.__glObs) return;
    const o = new MutationObserver(onMut); o.observe(el, { childList: true, subtree: true, attributes: true, attributeFilter: ['hidden'] }); el.__glObs = o; S.obs.push(o);
  }
  function hookMaps() {   // pop-ups, on every map of the page and every map made later, through the libraries' own update
    const L = root.L, M = root.maplibregl;
    if (L && L.Popup && !L.Popup.prototype.__gl) {
      const up = L.Popup.prototype.update;
      L.Popup.prototype.update = function () { const r = up.apply(this, arguments); if (this._contentNode) queue(this._contentNode); return r; };
      L.Popup.prototype.__gl = true;
    }
    if (M && M.Popup && !M.Popup.prototype.__gl) {
      for (const f of ['setDOMContent', 'addTo']) { const o = M.Popup.prototype[f]; M.Popup.prototype[f] = function () { const r = o.apply(this, arguments); if (this._content) queue(this._content); return r; }; }
      M.Popup.prototype.__gl = true;
    }
  }
  async function start() {
    const lg = lang(), dg = dictGlossary();
    let terms;
    if (dg) terms = formsFrom(dg, lg);
    else terms = (await fetchJson(`data/glossary_forms_${lg}.json`)).terms;
    S.forms = new Map(terms.map(t => [t[0], t]));
    S.matchers = { default: compile(terms) };
    S.matchers[lg] = S.matchers.default;
    if (dg && lg === 'es') S.matchers.en = compile(formsFrom(dg, 'en'));   // the dictionary's English text, on its Spanish page
    S.defsIds = dg ? new Set(dg.map(g => g.id)) : null;   // elsewhere a mark on purpose is trusted (tests/test_glossary.py checks the ids in the pages): the definitions wait for the first use
    S.on = true; S.quietCache = new WeakMap(); S.ctx = newCtx(existingIn);
    hookMaps();
    doc.querySelectorAll(ROOTS).forEach(observe);
    if (!S.bodyObs) (S.bodyObs = new MutationObserver(recs => recs.forEach(r => r.addedNodes.forEach(n => { if (S.on && n.nodeType === 1 && n.matches(ROOTS)) { observe(n); queue(n); } })))).observe(doc.body, { childList: true });   // a workbench or a dialog added later
    queue(doc.body);
  }
  function unmarkAll() {
    S.on = false; S.queue.clear(); S.work = null; clearTimeout(S.timer); S.timer = 0;
    S.obs.forEach(o => { o.disconnect(); }); doc.querySelectorAll(ROOTS).forEach(el => { delete el.__glObs; }); S.obs = [];
    const parents = new Set();
    doc.querySelectorAll('.gl-mark, .gl-run').forEach(m => { parents.add(m.parentNode); m.replaceWith(...m.childNodes); });
    parents.forEach(p => p && p.normalize());
    S.done = new WeakSet(); api.marks = 0;
  }

  // ── The tooltip ────────────────────────────────────────────────────────────
  function defs() {
    if (S.defs) return Promise.resolve(S.defs);
    const dg = dictGlossary();
    if (dg) return Promise.resolve(S.defs = defsFrom(dg, lang()));
    return S.defsP || (S.defsP = fetchJson(`data/glossary_defs_${lang()}.json`).then(j => (S.defs = j.terms), e => { S.defsP = null; throw e; }));
  }
  // The lesson of the Learn page that teaches a term (js/learn_links.js, written by learn.py), asked for with the first definition; a pop-up opens without it
  // when it does not come.
  const lessons = () => S.lessonsP || (S.lessonsP = new Promise((ok) => { if (root.LEARN_LINKS) return ok(); const s = doc.createElement('script'); s.src = 'js/learn_links.js?v=5'; s.onload = s.onerror = () => ok(); doc.body.appendChild(s); }));
  const lessonOf = (id) => { const l = root.LEARN_LINKS && root.LEARN_LINKS.terms[id]; return l ? [l[0], l[1][lang()] || l[1].en] : null; };
  const onDictionary = () => !!dictGlossary();
  const glossHref = (id) => (onDictionary() ? '' : 'dictionary.html') + '#g-' + id;
  const dateText = (d) => { try { return root.I18N.date(d); } catch (e) { return d; } };
  function place(m, o = {}) {   // under the whole word, so a word on two lines keeps both visible (or above it near the bottom), at the left of the line under the pointer
    const t = S.tip, rects = [...m.getClientRects()], all = m.getBoundingClientRect(); let r = rects[0] || all;
    if (o.x != null) for (const q of rects) if (o.x >= q.left - 1 && o.x <= q.right + 1 && (o.y == null || (o.y >= q.top - 1 && o.y <= q.bottom + 1))) { r = q; break; }
    const vw = doc.documentElement.clientWidth || root.innerWidth, vh = root.innerHeight, G = 16;
    t.style.left = '0px'; t.style.top = '0px';
    const tw = t.offsetWidth, th = t.offsetHeight;
    let top = all.bottom + 6;
    if (top + th > vh - G) top = all.top - 6 - th >= G ? all.top - 6 - th : Math.max(G, vh - G - th);
    t.style.left = Math.round(Math.max(G, Math.min(r.left, vw - G - tw))) + 'px'; t.style.top = Math.round(top) + 'px';
  }
  function show(m, o = {}) {
    clearTimeout(S.hideT); clearTimeout(S.hoverT);
    if (S.cur && S.cur !== m) { S.cur.classList.remove('gl-on'); S.cur.removeAttribute('aria-describedby'); }
    S.cur = m; S.pinned = !!o.pin; m.classList.add('gl-on');
    const t = S.tip, host = m.closest('dialog[open]') || doc.body;   // a modal dialog is in the top layer: the tooltip goes inside it
    if (t.parentNode !== host) host.appendChild(t);
    t.removeAttribute('aria-label'); t.setAttribute('role', 'tooltip');   // as a tooltip its text is the description of the word: a label would take its place
    m.setAttribute('aria-describedby', 'gl-tip');   // only this word is described by the tooltip, and only while it is open
    const p = S.defs ? null : Promise.all([defs(), lessons()]);
    if (!S.defs) {
      t.innerHTML = `<p class="gl-def">${esc(T('Loading the definition…'))}</p>`; t.hidden = false; place(m, o);
      p.then(() => { if (S.cur === m) fillTip(m, o); }, () => { if (S.cur === m) { t.innerHTML = `<p class="gl-def">${esc(T('The definition could not be loaded. Check your connection and try again.'))}</p>`; place(m, o); } });
      return;
    }
    fillTip(m, o);   // at once: the description is in place when the focus arrives
  }
  function fillTip(m, o) {
    const t = S.tip, id = m.dataset.gl, d = S.defs[id];
    if (!d) { hide(); return; }
    t.innerHTML = tipHtml(d, id, { href: glossHref(id), date: dateText, lesson: lessonOf(id) });
    t.hidden = false; place(m, o);
    if (o.focus) { t.setAttribute('role', 'dialog'); t.setAttribute('aria-label', T('Definition of {term}', { term: m.textContent.trim() })); const f = t.querySelector('a[href]'); if (f) f.focus({ preventScroll: true }); }   // Enter: a small dialog with its links
  }
  function hide(focusMark) {
    clearTimeout(S.hideT); clearTimeout(S.hoverT);
    const m = S.cur, t = S.tip; if (!t) return;
    const inside = t.contains(doc.activeElement);
    t.hidden = true; t.innerHTML = ''; t.setAttribute('role', 'tooltip'); t.removeAttribute('aria-label'); S.pinned = false; S.cur = null;   // emptied: no word is ever described by another word's text
    if (m) { m.classList.remove('gl-on'); m.removeAttribute('aria-describedby'); if (focusMark || inside) { S.noFocusShow = true; m.focus({ preventScroll: true }); S.noFocusShow = false; } }
    else if ((focusMark || inside) && S.after) { focusPlace(S.after); }   // the note after "Hide the underlines": back where the word was
    S.after = null;
  }
  function focusPlace(el) {   // an element that is not focusable gets tabindex="-1" until the focus leaves it
    if (!el.isConnected) return;
    if (el.tabIndex < 0 && !el.hasAttribute('tabindex')) { el.setAttribute('tabindex', '-1'); el.addEventListener('blur', () => el.removeAttribute('tabindex'), { once: true }); }
    el.focus({ preventScroll: true });
  }
  const markOf = (e) => e.target && e.target.closest ? e.target.closest('.gl-mark') : null;
  const inTip = (n) => !!(S.tip && n && S.tip.contains(n));
  function turnOff() {
    const at = S.cur && S.cur.parentElement;   // where the word was: the focus goes back there when the note closes
    setOff(true); unmarkAll(); api.state = 'off';
    const t = S.tip; if (S.cur) S.cur = null;
    S.after = at && at.isConnected ? at : null;
    t.setAttribute('role', 'status');
    t.innerHTML = `<button type="button" class="gl-close" aria-label="${esc(T('Close'))}"><span aria-hidden="true">×</span></button><p class="gl-def">${esc(T("The underlines are hidden on every page. To show them again, use the switch in the dictionary's Glossary."))}</p><p class="gl-foot"><a href="${onDictionary() ? '' : 'dictionary.html'}#glossary">${esc(T('Open the Glossary'))}</a></p>`;
    t.hidden = false; const f = t.querySelector('a'); if (f) f.focus({ preventScroll: true });
    syncSwitch();
  }
  function wire() {
    doc.addEventListener('pointerover', e => {
      if (e.pointerType === 'touch') return;
      const m = markOf(e);
      if (m) { clearTimeout(S.hideT); defs().catch(() => {}); if (S.cur !== m) { clearTimeout(S.hoverT); const x = e.clientX, y = e.clientY; S.hoverT = setTimeout(() => show(m, { x, y }), 150); } }
      else if (inTip(e.target)) clearTimeout(S.hideT);
    });
    doc.addEventListener('pointerout', e => {
      if (e.pointerType === 'touch') return;
      const from = markOf(e) || (inTip(e.target) ? S.tip : null), to = e.relatedTarget;
      if (!from || (to && ((to.closest && to.closest('.gl-mark') === S.cur) || inTip(to)))) return;
      clearTimeout(S.hoverT);
      if (S.cur && !S.pinned && !(S.cur === doc.activeElement || inTip(doc.activeElement))) S.hideT = setTimeout(hide, 250);
    });
    doc.addEventListener('focusin', e => {
      const m = markOf(e);
      if (!m || S.noFocusShow || S.cur === m) return;
      let kb = true; try { kb = m.matches(':focus-visible'); } catch (x) { /* an older browser: show it */ }
      if (kb) show(m);   // keyboard focus; a click or a tap is handled by the click
    });
    doc.addEventListener('focusout', e => {
      if (!S.cur || !(markOf(e) || inTip(e.target))) return;
      setTimeout(() => { const a = doc.activeElement; if (S.cur && a !== S.cur && !inTip(a) && !(S.pinned && (!a || a === doc.body))) hide(); }, 0);   // a pinned tooltip stays when the focus only drops to the page
    });
    doc.addEventListener('click', e => {
      if (inTip(e.target)) {
        const b = e.target.closest('.gl-close,.gl-hide'); if (!b) return;   // a link opens as usual
        e.stopPropagation();   // the page's own "click outside" handlers (the help pop-up) stay out of it
        if (b.classList.contains('gl-close')) hide(true); else turnOff();
        return;
      }
      const m = markOf(e); if (!m) return;
      e.preventDefault(); e.stopPropagation();   // a mark inside a clickable row does only this
      if (S.cur !== m || S.tip.hidden) show(m, { pin: true, x: e.clientX, y: e.clientY });
      else if (!S.pinned) S.pinned = true;
      else hide();
    }, true);
    doc.addEventListener('keydown', e => {
      const m = markOf(e);
      if (m && (e.key === 'Enter' || e.key === ' ')) { e.preventDefault(); e.stopPropagation(); show(m, { pin: true, focus: true }); return; }
      if (S.tip && !S.tip.hidden && e.key === 'Escape') {
        const ours = (S.cur && S.cur === doc.activeElement) || inTip(doc.activeElement);
        hide(ours);
        if (ours) { e.preventDefault(); e.stopPropagation(); }   // else the key is the page's (a search box, the chat)
        return;
      }
      if (inTip(e.target) && e.key === 'Tab') {   // Tab moves through the tooltip's links; past either end it goes back to the word
        const f = [...S.tip.querySelectorAll('a[href],button')], i = f.indexOf(e.target);
        if ((!e.shiftKey && i === f.length - 1) || (e.shiftKey && i <= 0)) { e.preventDefault(); const c = S.cur; hide(true); if (c) show(c); }
      }
    }, true);
    doc.addEventListener('pointerdown', e => {
      if (e.target.closest && e.target.closest('.leaflet-container,.maplibregl-map')) S.dragging = true;
      if (S.tip && !S.tip.hidden && !inTip(e.target) && markOf(e) !== S.cur) hide();
    }, true);
    const rest = () => { S.dragging = false; S.busyUntil = now() + 300; };
    doc.addEventListener('pointerup', rest, true); doc.addEventListener('pointercancel', rest, true);
    const moving = (e) => { S.busyUntil = now() + 300; if (S.tip && !S.tip.hidden && !inTip(e.target) && e.type === 'scroll') hide(); };
    root.addEventListener('wheel', moving, { capture: true, passive: true });
    root.addEventListener('scroll', moving, { capture: true, passive: true });
    root.addEventListener('resize', () => { if (S.tip && !S.tip.hidden) hide(); });
  }

  // ── The switch in the dictionary's Glossary ─────────────────────────────────
  function syncSwitch() { const c = doc.getElementById('glSwitch'); if (c) c.checked = !isOff(); }
  function addSwitch() {
    const lede = doc.querySelector('#glossary .d-lede'); if (!lede || doc.getElementById('glSwitch')) return;
    const p = doc.createElement('p'); p.className = 'gl-switch'; p.setAttribute('data-gloss', 'off');
    p.innerHTML = `<label><input type="checkbox" id="glSwitch"> ${esc(T('Underline technical terms on every page'))}</label><small>${esc(T('Point at an underlined word, focus it with the keyboard or tap it to see its definition and its source.'))}</small>`;
    lede.after(p); syncSwitch();
    doc.getElementById('glSwitch').onchange = (e) => { setOff(!e.target.checked); if (e.target.checked) { api.state = 'loading'; S.first = true; start().catch(() => { api.state = 'error'; }); } else { hide(); unmarkAll(); api.state = 'off'; } };
  }

  api.boot = async function boot() {
    api.state = 'loading';
    try {
      setup(); wire();
      await root.I18N.load('glossary').catch(() => {});   // the module's own words (site/i18n/es.<page>.glossary.js); English needs none
      addSwitch();
      if (isOff()) { api.state = 'off'; return; }
      await start();
    } catch (e) { api.state = 'error'; }
  };
  api.mark = (el) => queue(el);
  api.observe = (el) => { observe(el); queue(el); };
  api.hide = hide;
  return api;
});
