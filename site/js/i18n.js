/* PR Data Observatory: language layer. Spanish first.

   The code is written in English and every user-visible English string is its own key. The Spanish lives in i18n_src/es/*.json and
   is built by `python i18n.py` into site/i18n/es.<page>.js, which this script loads before the page scripts run. English needs no file.

     T('Tourism places')                          plain text in the page language
     T('{n} of {m} places', { n, m })             {name} placeholders; the caller escapes the result where it goes into HTML (esc(T(...)))
     Tn(n, '{n} place', '{n} places')             plural: one form and the other form (the Spanish entry is [one, other])
     Th('<b>{n}</b> places', { n })               HTML text: values are escaped unless wrapped in I18N.raw(html)
     I18N.apply(root)                             translates static markup: text, title / aria-label / placeholder / alt, and mixed text with inline tags
     I18N.fmt(n, d), I18N.date(d, opts), I18N.name(record)   locale-aware numbers, dates and registry names ({es, en})
     I18N.load('scenarios')                       a promise for the Spanish of a module that loads on first use (es.<page>.<module>.js; "modules" in i18n_src/pages.json)
     I18N.has('text')                             whether T('text') has Spanish, without listing it in I18N.missed (data whose Spanish may not exist yet: names of dictionary entries)

   Language: ?lang=es|en in the URL (kept for the browser session), else the choice saved with the ES / EN switch, else the browser (any Spanish: es; only English: en), else Spanish.
   Switching reloads the page with ?lang= (the map's view lives in the URL hash, so it survives). Rules and style guide: docs/i18n.md. */
(function (root) {
  'use strict';
  const SUPPORTED = ['es', 'en'];
  const LOCALE = { es: 'es-PR', en: 'en-US' };
  const STORE = 'twin.lang';
  const ATTRS = ['title', 'aria-label', 'placeholder', 'alt', 'data-ask', 'aria-description'];
  const SKIP = new Set(['SCRIPT', 'STYLE', 'NOSCRIPT', 'TEXTAREA', 'CODE', 'PRE', 'SVG', 'CANVAS', 'TEMPLATE']);
  const INLINE = new Set(['A', 'B', 'I', 'EM', 'STRONG', 'KBD', 'ABBR', 'U', 'MARK', 'SUB', 'SUP', 'BR', 'Q', 'CITE']);
  const CTX = '\u0004';

  function create(env) {
    const doc = env.document || null;
    const state = { lang: 'en', source: 'default', dict: Object.create(null), missed: new Set(), pending: new Set() };

    function storageGet(s) { try { return s ? s.getItem(STORE) : null; } catch (e) { return null; } }
    function storageSet(s, v) { try { if (s) s.setItem(STORE, v); } catch (e) { /* private window: the URL still carries the choice */ } }

    function pick() {
      const q = new URLSearchParams(env.search || '').get('lang');
      if (SUPPORTED.includes(q)) return { lang: q, source: 'url' };
      const ses = storageGet(env.session);                // a choice made by a link (?lang=) lasts for the browser session
      if (SUPPORTED.includes(ses)) return { lang: ses, source: 'session' };
      const s = storageGet(env.storage);                  // a choice made with the ES / EN switch is remembered
      if (SUPPORTED.includes(s)) return { lang: s, source: 'saved' };
      const base = (env.languages || []).map(l => String(l).toLowerCase().split('-')[0]);
      if (base.includes('es')) return { lang: 'es', source: 'browser' };
      if (base.includes('en')) return { lang: 'en', source: 'browser' };
      return { lang: 'es', source: 'default' };
    }
    const chosen = pick();
    state.lang = chosen.lang; state.source = chosen.source;

    const esc = (s) => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
    class Raw { constructor(html) { this.html = String(html); } toString() { return this.html; } }
    const raw = (html) => new Raw(html);
    /** HTML for English text that has no Spanish (dictionary entries, definitions): marked lang="en" in Spanish mode, so a screen reader changes voice (WCAG 3.1.2). `html` is already escaped. */
    const en = (html) => state.lang === 'es' && html ? `<span lang="en">${html}</span>` : html;
    const fill = (s, vars, escape) => vars ? s.replace(/\{(\w+)\}/g, (m, k) => {
      if (!(k in vars)) return m;
      const v = vars[k];
      return escape ? (v instanceof Raw ? v.html : esc(v == null ? '' : v)) : String(v == null ? '' : v);
    }) : s;
    const norm = (s) => String(s).replace(/\s+/g, ' ').trim();

    function lookup(key, ctx) {
      if (state.lang === 'en') return key;
      const d = state.dict;
      let v = ctx ? d[ctx + CTX + key] : undefined;
      if (v === undefined) v = d[key];
      if (v === undefined) { state.missed.add(key); return key; }
      return v;
    }
    function t(key, vars, ctx) {
      let v = lookup(key, ctx);
      if (Array.isArray(v)) v = v[0];
      return fill(v, vars, false);
    }
    const rules = (() => { try { return new Intl.PluralRules(LOCALE[state.lang]); } catch (e) { return null; } })();
    function tn(n, one, other, vars) {
      const all = Object.assign({ n }, vars);
      if (state.lang === 'en') return fill(n === 1 ? one : other, all, false);
      const v = state.dict[one];
      if (v === undefined) { state.missed.add(one); return fill(n === 1 ? one : other, all, false); }
      if (!Array.isArray(v)) return fill(v, all, false);
      const isOne = rules ? rules.select(n) === 'one' : n === 1;
      return fill(isOne ? v[0] : (v[1] != null ? v[1] : v[0]), all, false);
    }
    function th(key, vars) { return fill(lookup(key), vars, true); }

    function add(obj) { Object.assign(state.dict, obj); }
    // The Spanish of a part of the page that loads on first use (site/i18n/es.<page>.<module>.js): its loader waits for this before it renders. Once per module; a failed load can be tried again.
    const loading = Object.create(null);
    function load(mod) {
      if (state.lang === 'en' || !env.bundle) return Promise.resolve();
      return loading[mod] || (loading[mod] = Promise.resolve().then(() => env.bundle(mod)).catch(e => { delete loading[mod]; throw e; }));
    }
    const locale = () => LOCALE[state.lang];
    function fmt(n, d = 0) {
      return n == null ? '—' : Number(n).toLocaleString(locale(), { maximumFractionDigits: d, minimumFractionDigits: d });
    }
    function date(dt, opts) {
      // a date-only text (2026-10-05) is a calendar day, not a UTC instant: read it as that day in local time
      const d = dt instanceof Date ? dt : (typeof dt === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(dt) ? new Date(+dt.slice(0, 4), +dt.slice(5, 7) - 1, +dt.slice(8, 10)) : new Date(dt));
      return d.toLocaleDateString(locale(), opts || { year: 'numeric', month: 'long', day: 'numeric' });
    }
    function list(items) {
      try { return new Intl.ListFormat(locale(), { style: 'long', type: 'conjunction' }).format(items); } catch (e) { return items.join(', '); }
    }
    function name(rec) { return rec && rec.name ? (rec.name[state.lang] || rec.name.en || '') : ''; }
    function text(obj) { return obj ? (obj[state.lang] || obj.en || '') : ''; }

    // ── Static markup ────────────────────────────────────────────────────────────
    const done = typeof WeakSet !== 'undefined' ? new WeakSet() : null;
    const hasLetters = (s) => /[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]{2}/.test(s);
    let excluded = null;   // a selector the audit leaves out (English data shown on purpose, such as dictionary entries)
    function skipped(el) {
      return SKIP.has(el.tagName) || el.getAttribute('translate') === 'no' || el.getAttribute('data-t') === 'skip' || (el.classList && el.classList.contains('ms-icon')) || (excluded && el.matches(excluded));
    }
    // An element whose own text is mixed with inline tags (a sentence with <b>, <a>, <i>...) is translated as one unit, by its innerHTML.
    function isUnit(el) {
      if (el.getAttribute('data-t') === 'html') return true;
      if (el.getAttribute('data-t') === 'text') return false;
      let text = false, inline = false;
      for (const c of el.childNodes) {
        if (c.nodeType === 3 && hasLetters(c.nodeValue)) text = true;
        else if (c.nodeType === 1 && INLINE.has(c.tagName)) inline = true;
      }
      return text && inline;
    }
    function unitKey(el) { return norm(el.innerHTML); }
    function translateValue(s) {
      const k = norm(s);
      if (!k || !hasLetters(k)) return null;
      const v = state.dict[k];
      if (v === undefined) return undefined;
      return Array.isArray(v) ? v[0] : v;
    }
    function walk(el, visit) {
      if (skipped(el)) return;
      if (visit.attrs) visit.attrs(el);
      if (isUnit(el)) { visit.unit(el); return; }
      for (const c of Array.from(el.childNodes)) {
        if (c.nodeType === 3) visit.text(c);
        else if (c.nodeType === 1) walk(c, visit);
      }
    }
    function apply(rootEl) {
      if (state.lang === 'en' || !doc) return;
      const r = rootEl || doc.body;
      walk(r, {
        attrs(el) {
          for (const a of ATTRS) {
            const v = el.getAttribute(a);
            if (!v) continue;
            const tr = translateValue(v);
            if (tr) el.setAttribute(a, tr); else if (tr === undefined && hasLetters(v)) state.pending.add(norm(v));
          }
          if (el.tagName === 'INPUT' && /^(button|submit|reset)$/.test(el.type) && el.value) {
            const tr = translateValue(el.value); if (tr) el.value = tr;
          }
        },
        text(node) {
          if (done && done.has(node)) return;
          const m = /^(\s*)([\s\S]*?)(\s*)$/.exec(node.nodeValue);
          const tr = translateValue(m[2]);
          if (tr) { node.nodeValue = m[1] + tr + m[3]; if (done) done.add(node); } else if (tr === undefined && hasLetters(m[2])) state.pending.add(norm(m[2]));
        },
        unit(el) {
          const k = unitKey(el);
          const tr = state.dict[k];
          if (tr !== undefined) el.innerHTML = Array.isArray(tr) ? tr[0] : tr; else state.pending.add(k);
        },
      });
      if (r === doc.body && doc.title) { const tt = translateValue(doc.title); if (tt) doc.title = tt; }
    }
    // Text on the page that has no translation yet (static markup that apply() left alone): used by the regression check, never in production.
    function audit(rootEl, opts) {
      excluded = (opts && opts.exclude) || null;
      const out = new Set(), have = new Set(), patterns = [];
      for (const v of Object.values(state.dict)) (Array.isArray(v) ? v : [v]).forEach(x => {
        const n = norm(x); have.add(n);
        if (/\{\w+\}/.test(n)) patterns.push(new RegExp('^' + n.replace(/[.*+?^$()|[\]\\]/g, '\\$&').replace(/\{\w+\}/g, '.*?') + '$'));
      });
      const known = (k) => !(opts && opts.all) && (state.dict[k] !== undefined || have.has(k) || isKept(k) || patterns.some(r => r.test(k)));   // Spanish text built from a template counts as translated; {all: true} lists everything (to extract keys)
      const r = rootEl || doc.body;
      walk(r, {
        attrs(el) { for (const a of ATTRS) { const v = el.getAttribute(a); if (v && hasLetters(v) && !known(norm(v))) out.add('attr: ' + norm(v)); } },
        text(node) { const k = norm(node.nodeValue); if (k && hasLetters(k) && !known(k)) out.add('text: ' + k); },
        unit(el) { const k = unitKey(el); if (!known(k)) out.add('html: ' + k); },
      });
      excluded = null;
      return Array.from(out);
    }
    const kept = [];
    function keep(...patterns) { kept.push(...patterns); }
    function isKept(s) { return kept.some(p => p instanceof RegExp ? p.test(s) : p === s); }

    // ── Language switch ─────────────────────────────────────────────────────────
    function href(lang) {
      const u = new URL(env.href || 'http://localhost/');
      u.searchParams.set('lang', lang);
      return u.pathname + u.search + u.hash;
    }
    function set(lang) {
      if (!SUPPORTED.includes(lang) || !doc) return;
      storageSet(env.storage, lang); storageSet(env.session, lang);
      env.navigate(href(lang));
    }
    function mount() {
      if (!doc) return;
      const bar = doc.querySelector('header.topbar');
      if (!bar || bar.querySelector('.lang-switch')) return;
      const wrap = doc.createElement('div');
      wrap.className = 'lang-switch'; wrap.setAttribute('translate', 'no'); wrap.setAttribute('role', 'group'); wrap.setAttribute('aria-label', 'Idioma / Language');
      for (const l of SUPPORTED) {
        const b = doc.createElement('button');
        b.type = 'button'; b.textContent = l.toUpperCase(); b.lang = l;
        b.title = l === 'es' ? 'Español' : 'English'; b.setAttribute('aria-label', l === 'es' ? 'Español' : 'English');
        b.setAttribute('aria-pressed', String(l === state.lang));
        b.onclick = () => { if (l !== state.lang) set(l); };
        wrap.appendChild(b);
      }
      const snap = bar.querySelector('.snapshot');
      snap ? bar.insertBefore(wrap, snap) : bar.appendChild(wrap);
    }
    function init() {
      if (!doc) return;
      doc.documentElement.lang = state.lang;
      // keep the choice in the address, so a shared link opens in the same language
      if (state.source === 'url') storageSet(env.session, state.lang);   // so the other pages open in the same language
      else if (env.replace) env.replace(href(state.lang));
    }

    return {
      get lang() { return state.lang; }, get locale() { return locale(); }, get source() { return state.source; },
      supported: SUPPORTED, t, tn, th, raw, en, add, load, apply, audit, keep, fmt, date, list, name, text, mount, set, init, href, has: (key) => state.lang === 'en' || state.dict[key] !== undefined,
      get missed() { return Array.from(state.missed); }, get pending() { return Array.from(state.pending); }, size: () => Object.keys(state.dict).length,
    };
  }

  if (typeof document === 'undefined') { if (typeof module !== 'undefined') module.exports = { create }; return; }   // node tests

  const me = document.currentScript, page = me && me.dataset.page, v = me && /\?.*$/.exec(me.getAttribute('src') || '');
  const bundleUrl = (name) => new URL('../i18n/' + I.lang + '.' + name + '.js', me.src).href + (v ? v[0] : '');   // the bundles carry the ?v= of this script
  const I = create({
    document, search: location.search, href: location.href,
    bundle: page ? (mod) => new Promise((ok, fail) => { const s = document.createElement('script'); s.src = bundleUrl(page + '.' + mod); s.onload = ok; s.onerror = () => { s.remove(); fail(new Error('Spanish for ' + mod)); }; document.head.appendChild(s); }) : null,
    storage: (() => { try { return window.localStorage; } catch (e) { return null; } })(), session: (() => { try { return window.sessionStorage; } catch (e) { return null; } })(),
    languages: navigator.languages && navigator.languages.length ? navigator.languages : [navigator.language || ''],
    navigate: (u) => location.assign(u), replace: (u) => history.replaceState(null, '', u),
  });
  window.I18N = I;
  window.T = I.t; window.Tn = I.tn; window.Th = I.th;
  I.init();
  // Spanish strings for this page, loaded before the page scripts run (a small synchronous script; English needs none)
  if (I.lang !== 'en' && page) document.write('<script src="' + bundleUrl(page) + '"><\/script>');
  // Each page also calls I18N.apply() from an inline script just before its page scripts, so static text is translated before it is painted;
  // this is the safety net (apply is safe to repeat).
  document.addEventListener('DOMContentLoaded', () => { I.apply(); I.mount(); });
})(typeof window !== 'undefined' ? window : globalThis);

