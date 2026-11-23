// The top bar of the four pages at many widths, in both languages: what leaves the screen, what overlaps, what scrolls sideways.
// node bars.js [base=http://127.0.0.1:8020] [pages=index.html,3d.html,housing.html,dictionary.html] [widths=...]
const { openPage } = require('./cdp.js');
const fs = require('fs');
const BASE = process.argv[2] || 'http://127.0.0.1:8020';
const PAGES = (process.argv[3] || 'index.html,3d.html,housing.html,dictionary.html').split(',');
const WIDTHS = (process.argv[4] || '320,330,340,352,359,360,375,390,411,480,560,561,600,643,700,768,860,861,880,900,920,949,960,1000,1100,1101,1131,1180,1181,1240,1300,1400,1401,1500,1520,1600,1700').split(',').map(Number);
const CHECK = fs.readFileSync(__dirname + '/bar_check.js', 'utf8').replace(/JSON\.stringify\(out\)\s*$/, 'return JSON.stringify(out)');

(async () => {
  let bad = 0, total = 0;
  for (const page of PAGES) for (const lang of ['en', 'es']) {
    const p = await openPage(`${BASE}/${page}?lang=${lang}`, { width: 1400, height: 900, noCache: true });
    await p.waitFor("!!document.querySelector('.topbar .brand, .topbar .logo')", 30000);
    const rows = [];
    for (const w of WIDTHS) {
      await p.send('Emulation.setDeviceMetricsOverride', { width: w, height: 900, deviceScaleFactor: 1, mobile: w < 700 });
      await new Promise(r => setTimeout(r, 150));
      const o = JSON.parse(await p.eval(`(async () => { ${CHECK} })()`));
      total++;
      const problems = [];
      if (o.outOfView.length) problems.push('out of view: ' + o.outOfView.join(','));
      if (o.overlaps.length) problems.push('overlap: ' + o.overlaps.join(','));
      if (o.scrollOverflow) problems.push('page scrolls sideways');
      if (o.lang && o.lang[1] > w + 1) problems.push('ES|EN switch off screen by ' + (o.lang[1] - w));
      if (typeof o.h1 !== 'string' && o.h1 && o.h1[1] > o.h1[0] + 1) problems.push('title clipped ' + o.h1.join('>'));
      if (problems.length) { bad++; rows.push(`  ${String(w).padStart(5)} px: ${problems.join('; ')}`); }
    }
    console.log(`${page} ${lang}: ${rows.length ? rows.length + ' widths with problems' : 'no problems at any of ' + WIDTHS.length + ' widths'}`);
    rows.forEach(r => console.log(r));
    await p.close();
  }
  console.log(`checked ${total} page/width/language combinations; ${bad} with problems`);
  process.exit(0);
})().catch(e => { console.error(e); process.exit(1); });
