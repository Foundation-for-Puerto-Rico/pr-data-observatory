/* PR Data Observatory core: the language and number helpers every other core module uses. In a page these are the page's own (js/i18n.js: T, Tn, Th, I18N.fmt; js/common.js: esc);
   without a page (the Node tests) they fall back to plain English, so the modules can be tested on their own. Load this file before the other core files. */
(function (name, root, factory) {
  const dep = (n) => (typeof module === 'object' && module.exports ? require('./' + n + '.js') : root.Core[n]);   // the other core modules, in Node or in a page
  const api = factory(root, dep);
  if (typeof module === 'object' && module.exports) module.exports = api; else { root.Core = root.Core || {}; root.Core[name] = api; }
})('text', typeof window !== 'undefined' ? window : globalThis, function (root) {
  'use strict';
  const fill = (s, v) => String(s).replace(/\{(\w+)\}/g, (m, k) => v && k in v ? v[k] : m);
  const escape = (s) => s == null ? '' : String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  return {
    T: (s, v) => root.T ? root.T(s, v) : fill(s, v),
    Tn: (n, one, other, v) => root.Tn ? root.Tn(n, one, other, v) : fill(n === 1 ? one : other, Object.assign({ n }, v)),
    Th: (s, v) => root.Th ? root.Th(s, v) : fill(s, v),
    // fmt and esc are constants of common.js (global lexical bindings, not properties of window), so they are looked up by name
    num: (n, d = 0) => typeof fmt === 'function' ? fmt(n, d) : Number(n).toLocaleString('en-US', { minimumFractionDigits: d, maximumFractionDigits: d }),
    esc: (s) => typeof esc === 'function' ? esc(s) : escape(s),
    lang: () => root.I18N ? root.I18N.lang : 'en',
    fill, escape,
  };
});
