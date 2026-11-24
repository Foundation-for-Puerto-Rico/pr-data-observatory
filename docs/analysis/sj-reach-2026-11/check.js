// node docs/analysis/sj-reach-2026-11/check.js  — runs the six modes from three San Juan points and fails if the ordering that must hold breaks.
const fs = require('fs'), path = require('path');
const { Roads } = require('../../../site/js/roads.js');
const Reach = require('./reach.js');
const buf = fs.readFileSync(path.join(__dirname, '../../../site/data/roads.bin'));
const R = new Roads(buf.buffer.slice(buf.byteOffset, buf.byteOffset + buf.byteLength));
const TT = JSON.parse(fs.readFileSync(path.join(__dirname, 'timetable.json'), 'utf8')), SN = Reach.stopNodes(R, TT);
const POINTS = { 'Viejo San Juan': [-66.1165, 18.4655], 'Río Piedras': [-66.0505, 18.3990], 'Santurce': [-66.0640, 18.4480] };
for (const [name, [x, y]] of Object.entries(POINTS)) {
  const t = Date.now(), r = Reach.reachAll(R, x, y, 15, { rush: 0.55 }, TT, SN), k = Object.fromEntries(r.modes.map(m => [m.id, m.km2]));
  console.log(name.padEnd(15), r.modes.map(m => `${m.id} ${m.km2.toFixed(1)}`).join(' · '), `(${Date.now() - t} ms)`);
  console.assert(k.walk > 0.5 && k.walk < 6, name, 'walk area out of range');
  console.assert(k.transit >= k.walk - 1e-9, name, 'transit below walking');
  console.assert(k.bike > k.walk && k.car_free > k.car_rush, name, 'speed ordering broken');
  if (k.walk <= 0.5 || k.transit < k.walk - 1e-9 || !(k.bike > k.walk && k.car_free > k.car_rush)) process.exitCode = 1;
}
