/* PR Data Observatory: the Ask button; the chat loads on first use (docs/ask.md). */
const ChatBoot = (() => {
  const PG = (document.querySelector('script[data-page]') || { dataset: {} }).dataset.page, MAP = PG === 'map' || PG === 'threed';
  const SRC = 'js/chat.js?v=64', EXTRA = ['js/ask.js?v=16', 'js/core/layers.js?v=20'], PAGE = !MAP && 'js/askpage.js?v=30';
  let asked = PG === 'map' && new URLSearchParams(location.hash.slice(1)).get('ask'), loading = null, extra = null;
  const script = (src) => new Promise((ok, fail) => { const s = document.createElement('script'); s.src = src; s.onload = ok; s.onerror = () => { s.remove(); fail(new Error(src)); }; document.body.appendChild(s); });
  const more = () => extra || (extra = Promise.all(EXTRA.filter(src => !(src.includes('ask.js') ? typeof Ask !== 'undefined' : typeof Core !== 'undefined' && Core.layers)).map(src => script(src).catch(() => null))));
  function load() {
    more();
    return loading || (loading = Promise.all([script(SRC), PAGE && script(PAGE)]).then(() => chInit(), (e) => { loading = null; throw e; }));
  }
  async function use(fn) {
    const b = $('#chBtn'); b.setAttribute('aria-busy', 'true');
    try { await load(); fn(); } catch { const m = T('The chat could not be loaded. Check your connection and try again.'); typeof toast === 'function' ? toast(m, 6000) : alert(m); } finally { b.removeAttribute('aria-busy'); }
  }
  function init() {
    if ($('#chBtn')) return;
    document.querySelector('.topbar .views').insertAdjacentHTML('beforebegin', `<button type="button" class="btn chat-btn" id="chBtn" aria-controls="chat" aria-expanded="false" title="${esc(T('Ask the observatory'))}"><span class="ms-icon" aria-hidden="true">chat_bubble</span><span class="lbl">${esc(T('Ask'))}</span></button>`);
    const b = $('#chBtn'); b.onclick = () => use(() => Chat.toggle(true));
    ['pointerenter', 'focus', 'touchstart'].forEach(t => b.addEventListener(t, () => { load().catch(() => null); }, { once: true, passive: true }));
    document.addEventListener('click', e => {
      const a = e.target.closest('[data-ask],[data-ask-open]');
      if (a) use(() => { if (!Chat.state.open) Chat.toggle(true); if (a.dataset.ask) Chat.ask(a.dataset.ask); });
    });
    if (asked) use(() => Chat.handOver(asked));
  }
  if (MAP) { const prev = window.onMapReady; window.onMapReady = async function () { init(); if (prev) await prev(); }; }
  else if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init, { once: true }); else init();
  return { load, init, extra: () => extra };
})();
