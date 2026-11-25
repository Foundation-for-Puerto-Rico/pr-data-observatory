# Palettes of the data layers, and how they read for people with color-vision deficiency

Plan item 6 (2026-10-06). Every color that a data layer uses is defined once, in `site/js/core/palettes.js`, so a map, its legend and a chart agree. This page says where each palette comes from, what it is used for, and what a color-vision test found. **No palette was changed.** Changing one is a design decision (and changes the golden test of the Economy tab); the findings below are for the project lead and the design owner to decide on.

## The palettes

| Palette | Colors | Used for | Source |
|---|---|---|---|
| `RAMPS.blue` | `#BDE0F2 #8FCAE8 #5FAFDA #338CB3 #205D7B` | the shading of one layer (the default and the choropleth menu), Housing maps, the 3D columns | FPR design system, blue 100, 200, 300, 500, 700 |
| `RAMPS.green` | `#E4EFB8 #C2D85E #A6BF33 #79901E #47560F` | the second shaded layer by default; any layer from the Colors menu | green 100, 300, 400, 600, 800 |
| `RAMPS.gold` | `#FFE9A8 #FFD96E #FFC83C #FFA600 #B56D00` | the Colors menu | yellow 100, 200, 300, 500, 700 |
| `RAMPS.red` | `#FFD0C9 #FFAB9F #FF8270 #E03220 #8C180D` | the Colors menu | red 100, 200, 300, 600, 800 |
| `RAMPS.gray` | `#E6E6E6 #CCCCCC #B3B3B3 #8C8E8E #2A2E2E` | the Colors menu | the Pantone Cool Gray scale and the charcoal of the design system |
| `RAMPS.teal` | `#D1EEEA #96D0D1 #5BA7B8 #3B7E9A #2A5674` | the Colors menu (since 25 Nov 2026) | not a brand color; a light-to-dark gradient in the manner of CARTO's sequential schemes |
| `RAMPS.purple` | `#F3E0F7 #D4B5E8 #B28FD6 #8B6BBE #5B3F94` | the Colors menu | as above |
| `RAMPS.sunset` | `#F3E79B #FAC484 #EB7F86 #B95E9A #5C53A5` | the Colors menu | as above: yellow to purple |
| `RAMPS.pinkteal` | `#F9C6DA #DBA1CE #A68BC6 #4F93B5 #0E7C86` | the Colors menu | as above: pink to turquoise |
| `RAMPS.yelblue` | `#F7FEAE #B7E6A5 #46AEA0 #089099 #045275` | the Colors menu | as above: yellow to blue |
| `DIVERGING` | `#B82415 #FF8270 #F2F2F2 #8FCAE8 #205D7B` | scales around a center: index, difference from Puerto Rico, change, location quotient; below in red, above in blue | red 700 and 300, off-white, blue 200 and 700 |
| `BIVARIATE` | 3 × 3 grid from `#e8e8e8` through teal and purple to `#3b4994` | two shaded layers together | the common teal and purple bivariate scheme (not a brand color) |
| `SYMBOLS` | `#B82415 #205D7B #B56D00 #47560F #2A2E2E` | the color of a layer of sized symbols; decreases in a symbol layer of changes | the 700 and 800 steps of red, blue, yellow and green, and charcoal |
| `LINES` | `#2A2E2E #205D7B #B82415 #79901E #B56D00 #338CB3 #FF4D38 #A6BF33` | chart lines (the first is Puerto Rico) | charcoal and the 600 to 700 steps of the four hues, then the base colors |
| `NOVAL` | `#EDEDED` | a municipality with no value | a neutral gray |

The brand rules for documents (no red on gray, white text on blue, and so on) are about print and slides; for a map the question is whether classes and series can be told apart, which is what the test below measures.

## The test

`docs/analysis/palettes-2026-10/colour_vision.py` reads the palettes from `palettes.js` (so the numbers are always those the pages draw) and:

1. simulates the three kinds of dichromacy at full severity (protanopia, deuteranopia, tritanopia; the Machado, Oliveira and Fernandes 2009 matrices, applied in linear sRGB), which is the worst case: partial deficiency is milder;
2. measures how far apart colors are with CIEDE2000, the standard color difference (checked in the script against four published test pairs);
3. compares what must stay apart: neighboring classes and the two ends of each ramp, every pair of colors of the symbol and line palettes, neighboring cells of the bivariate grid and its opposite corners, and the lightest class of each ramp against the no-value gray.

Rules of thumb used to read the numbers: about 2 is the smallest difference an observer notices side by side; **under 5 is hard to tell apart**; 5 to 10 can be told apart with care; 10 or more tells classes apart at a glance. Neighboring classes of an ordered ramp need not reach 10, because their order is carried by lightness and the legend gives the limits in words; two series of a chart or two symbol layers have nothing but color (and a name) to tell them apart, so they should.

```
python docs/analysis/palettes-2026-10/colour_vision.py        # prints the table and writes colour_vision.json beside it
```

## Results (smallest CIEDE2000 of any pair that must stay apart)

| Palette | Normal vision | Protan | Deutan | Tritan | Weakest pair under normal vision |
|---|---:|---:|---:|---:|---|
| ramp blue | 7.8 | 6.9 | 8.1 | 8.5 | classes 1 and 2 |
| ramp green | 6.8 | 6.9 | 6.8 | **4.4** | classes 2 and 3 (tritan: lightest class against no-value gray) |
| ramp gold | 6.0 | 5.8 | **4.7** | 5.1 | classes 2 and 3 |
| ramp red | 9.9 | 8.0 | 8.2 | 9.9 | classes 2 and 3 |
| ramp gray | **1.5** | **1.5** | **1.5** | **1.5** | lightest class against the no-value gray |
| diverging | 20.0 | 16.2 | 19.5 | 24.2 | classes 3 and 4 |
| bivariate grid | 10.9 | **3.5** | 7.7 | 11.5 | cells `[0][1]` and `[0][2]` |
| symbols | 20.5 | **3.4** | 10.5 | 12.1 | blue `#205D7B` and charcoal `#2A2E2E` |
| lines | 14.4 | 7.6 | **2.9** | 13.2 | green `#79901E` and the lighter green `#A6BF33` |

Bold: under 5. The full list of pairs is in `colour_vision.json`.

## Findings, and what each would take to fix

1. **The gray ramp's lightest class cannot be told from "no value" (1.5, for everyone).** `#E6E6E6` against `#EDEDED`. A municipality in the lowest gray class looks like one with no data. This is a plain-vision problem and the strongest finding. Options: start the gray ramp darker (for example `#D4D4D4`), or draw "no value" differently (white with a pattern, or a mid-gray outline) for every ramp. The other ramps keep at least 4.4 from the no-value gray.
2. **Bivariate grid under protanopia (3.5 to 4.6 in three pairs).** The steps along the first layer's axis run together in the left and middle columns when red is missing, so the cell color no longer says "low" or "medium" for that layer. The legend still names the cut-offs of each axis, and a hatching or a click shows the values, but the colors alone are weak. Option: a bivariate scheme designed for color-vision deficiency (blue and orange rather than teal and purple), tested with the same script.
3. **Symbols: red and the olive green look alike under protanopia (3.4).** `#B82415` and `#47560F`. Only if two layers of symbols use exactly those two colors, which the default order (red, blue, gold, green) avoids until a fourth symbol layer. Option: swap the fourth default, or show the layer name beside the symbol.
4. **Lines: two greens-and-gold pairs under deuteranopia (2.9).** `#79901E` and `#B56D00`, the fourth and fifth series of a trend chart or a table chart of the Housing page. Charts name each series in the legend, but with five or more series a person with deuteranopia cannot follow a line to its name. Option: dash patterns or end-of-line labels for series four to eight, or reorder the list so neighbors differ in lightness.
5. **Ramps green and gold have one weak pair each (4.7 to 4.4)**, between the second and third classes (gold, deuteranopia) or the lightest class and the no-value gray (green, tritanopia). Acceptable for an ordered scale with limits in the legend; noted.

What already helps, and is not color: the legends give the limits and the counts in words; a hatched municipality and a dashed symbol outline mark less reliable values with a pattern (`docs/engine.md`, "Reliability"); symbols carry size; the Economy tab has a table view of every layer next to the map.

## Not covered

Contrast of text on these colors (the legend text is dark on white); the 3D view's lighting; the colors of the context layers (flood, protected land, land use, transit routes), which are outside this palette module; and people with partial or other deficiencies (the full-severity simulation is the worst case for the three kinds above).

## To change a palette

Edit `palettes.js`, run the script, update this page and `colour_vision.json`, and regenerate the golden file of the Economy tab (`tests/browser/make_golden.js`; the colors of 26 stacks are in it) in the same commit, so the change is visible in review. Do not change a palette without the design owner's approval.
