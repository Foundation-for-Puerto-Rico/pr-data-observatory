// Reduces a piece of markup to what a person sees and the colours and sizes that matter, so markup written by a template and markup read back from the page's DOM
// (whose attributes are written differently: selected="", checked="") can be compared. Used by tests/browser/make_golden.js and tests/core.test.js.
const NAMED = { '&amp;': '&', '&lt;': '<', '&gt;': '>', '&quot;': '"', '&#39;': "'", '&nbsp;': ' ' };
function flat(html) {
  return String(html || '')
    .replace(/<([a-zA-Z][a-zA-Z0-9]*)((?:\s[^>]*)?)>/g, (m, tag, attrs) => {   // an opening tag becomes the marks that matter in it
      let extra = '';
      const st = /\sstyle="([^"]*)"/.exec(attrs);
      if (st) extra += ' ' + [...st[1].matchAll(/(?:background|width|height):[^;"]+/g)].map(x => `{${x[0].replace(/\s+/g, '')}}`).join('') + ' ';
      if (tag === 'option' && /\sselected\b/.test(attrs)) extra += ' {selected} ';
      if (tag === 'input' && /\stype="checkbox"/.test(attrs)) extra += /\schecked\b/.test(attrs) ? ' {checked} ' : ' {unchecked} ';
      return '\u0001' + extra;
    })
    .replace(/<\/[a-zA-Z][^>]*>/g, ' ')
    .replace(/\u0001/g, ' ')
    .replace(/&(?:amp|lt|gt|quot|#39|nbsp);/g, (m) => NAMED[m])
    .replace(/\s+/g, ' ').trim();
}
module.exports = { flat };
