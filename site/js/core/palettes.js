/* PR Data Observatory core: palettes. Every colour a data layer uses is defined here, once, so a map, a legend and a chart agree. docs/palettes.md says where each comes from
   and how it was tested for colour-vision deficiency.

   Core.palettes.RAMPS      sequential, five classes, light to dark: blue, green, gold, red, gray
   Core.palettes.DIVERGING  five classes around a centre: below (red) to above (blue)
   Core.palettes.BIVARIATE  3 x 3 grid, [class of B][class of A], for two layers shaded together
   Core.palettes.SYMBOLS    colours for sized symbols; Core.palettes.LINES colours for chart lines (the first is Puerto Rico)
   Core.palettes.NOVAL      colour of a place with no value
*/
(function (name, root, factory) {
  const dep = (n) => (typeof module === 'object' && module.exports ? require('./' + n + '.js') : root.Core[n]);   // the other core modules, in Node or in a page
  const api = factory(root, dep);
  if (typeof module === 'object' && module.exports) module.exports = api; else { root.Core = root.Core || {}; root.Core[name] = api; }
})('palettes', typeof window !== 'undefined' ? window : globalThis, function () {
  'use strict';
  const RAMPS = {
    blue: ['#BDE0F2', '#8FCAE8', '#5FAFDA', '#338CB3', '#205D7B'],
    green: ['#E4EFB8', '#C2D85E', '#A6BF33', '#79901E', '#47560F'],
    gold: ['#FFE9A8', '#FFD96E', '#FFC83C', '#FFA600', '#B56D00'],
    red: ['#FFD0C9', '#FFAB9F', '#FF8270', '#E03220', '#8C180D'],
    gray: ['#E6E6E6', '#CCCCCC', '#B3B3B3', '#8C8E8E', '#2A2E2E'],
  };
  const RAMP_ORDER = ['blue', 'green', 'gold', 'red', 'gray'];
  const DIVERGING = ['#B82415', '#FF8270', '#F2F2F2', '#8FCAE8', '#205D7B'];
  const BIVARIATE = [['#e8e8e8', '#ace4e4', '#5ac8c8'], ['#dfb0d6', '#a5add3', '#5698b9'], ['#be64ac', '#8c62aa', '#3b4994']];   // [B class][A class]
  const SYMBOLS = ['#B82415', '#205D7B', '#B56D00', '#47560F', '#2A2E2E'];
  const LINES = ['#2A2E2E', '#205D7B', '#B82415', '#79901E', '#B56D00', '#338CB3', '#FF4D38', '#A6BF33'];
  const NOVAL = '#EDEDED';
  const ramp = (name) => (Object.prototype.hasOwnProperty.call(RAMPS, name) ? RAMPS[name] : RAMPS.blue);   // own names only: a link's ramp "constructor" is blue
  return { RAMPS, RAMP_ORDER, DIVERGING, BIVARIATE, SYMBOLS, LINES, NOVAL, ramp };
});
