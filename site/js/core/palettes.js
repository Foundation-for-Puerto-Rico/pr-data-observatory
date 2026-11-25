/* PR Data Observatory core: palettes. Every color a data layer uses is defined here, once, so a map, a legend and a chart agree. docs/palettes.md says where each comes from
   and how it was tested for color-vision deficiency.

   Core.palettes.RAMPS      sequential, five classes, light to dark: blue, green, gold, red, gray, and five gradients (teal, purple, sunset, pinkteal, yelblue)
   Core.palettes.DIVERGING  five classes around a center: below (red) to above (blue)
   Core.palettes.BIVARIATE  3 x 3 grid, [class of B][class of A], for two layers shaded together
   Core.palettes.SYMBOLS    colors for sized symbols; Core.palettes.LINES colors for chart lines (the first is Puerto Rico)
   Core.palettes.NOVAL      color of a place with no value
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
    // Gradients a person can choose in the Colors menu (2026-11-25; docs/palettes.md). Each runs light to dark, so more is always darker. They are not FPR brand colors.
    teal: ['#D1EEEA', '#96D0D1', '#5BA7B8', '#3B7E9A', '#2A5674'],
    purple: ['#F3E0F7', '#D4B5E8', '#B28FD6', '#8B6BBE', '#5B3F94'],
    sunset: ['#F3E79B', '#FAC484', '#EB7F86', '#B95E9A', '#5C53A5'],
    pinkteal: ['#F9C6DA', '#DBA1CE', '#A68BC6', '#4F93B5', '#0E7C86'],
    yelblue: ['#F7FEAE', '#B7E6A5', '#46AEA0', '#089099', '#045275'],
  };
  const RAMP_ORDER = ['blue', 'green', 'gold', 'red', 'gray'];   // the ramp a new shaded layer takes, in turn
  const RAMP_MENU = RAMP_ORDER.concat(['teal', 'purple', 'sunset', 'pinkteal', 'yelblue']);   // the Colors menu
  const DIVERGING = ['#B82415', '#FF8270', '#F2F2F2', '#8FCAE8', '#205D7B'];
  const BIVARIATE = [['#e8e8e8', '#ace4e4', '#5ac8c8'], ['#dfb0d6', '#a5add3', '#5698b9'], ['#be64ac', '#8c62aa', '#3b4994']];   // [B class][A class]
  const SYMBOLS = ['#B82415', '#205D7B', '#B56D00', '#47560F', '#2A2E2E'];
  const LINES = ['#2A2E2E', '#205D7B', '#B82415', '#79901E', '#B56D00', '#338CB3', '#FF4D38', '#A6BF33'];
  const NOVAL = '#EDEDED';
  const ramp = (name) => (Object.prototype.hasOwnProperty.call(RAMPS, name) ? RAMPS[name] : RAMPS.blue);   // own names only: a link's ramp "constructor" is blue
  return { RAMPS, RAMP_ORDER, RAMP_MENU, DIVERGING, BIVARIATE, SYMBOLS, LINES, NOVAL, ramp };
});
