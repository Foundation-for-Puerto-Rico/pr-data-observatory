# Adding the missing city halls to OpenStreetMap

A guide for the FPR person who will map the city halls that OpenStreetMap (OSM) lacks. FPR decided on 2026-10-18 (HANDOFF decision 46) to add them. The observatory draws city halls from OSM (`amenity=townhall`) and never adds one by hand, so a hall appears on the map only after it is in OSM.

On 2026-10-18 these 16 municipios have no city hall in OSM: Adjuntas, Aguas Buenas, Arroyo, Barceloneta, Barranquitas, Cidra, Coamo, Florida, Guayama, Hormigueros, Juana Díaz, Juncos, Orocovis, Quebradillas, Río Grande and San Sebastián (`town_halls.geojson`, `notes.municipios_without_a_city_hall_mapped`).

## 1. What you may copy, and what you may not

OSM accepts only data it may legally republish under its license (ODbL).

- **Never copy from Google Maps**, Google Street View, Apple Maps, Waze, Yelp, tourism directories, Wikipedia coordinates or any other copyrighted map, not even one point or one street name. OSM's rule: "Do not use data from copyrighted maps or any other proprietary data", and "If unsure, do not use" ([Copyright](https://wiki.openstreetmap.org/wiki/Copyright)). The [Legal FAQ, section 2.1](https://wiki.openstreetmap.org/wiki/Legal_FAQ) answers "Can I trace data from Google Maps?" with no.
- **Allowed:**
  - Your own visit to the place (a survey).
  - Tracing from the imagery the OSM editors offer: Esri World Imagery ([Esri](https://wiki.openstreetmap.org/wiki/Esri)) or Bing aerial imagery ([Bing Maps](https://wiki.openstreetmap.org/wiki/Bing_Maps); the aerial photos only, never Bing's labels or street names).
  - US federal government data in the public domain, such as the USGS dataset below.
- **Puerto Rico government data** (a municipio's website, the Junta de Planificación's maps at [gis.jp.pr.gov](https://gis.jp.pr.gov/), the statistics committee's directory) is not automatically public domain the way federal data are. Use it to **confirm** that the hall is where the federal source and the imagery put it ("compare, but do not take", as the Legal FAQ puts it). Do not trace it or copy a list from it. A single address read on the municipio's own page to confirm one building is a fact, which is low risk; copying a directory is not allowed. This is practical guidance, not legal advice.
- **One by one, by hand.** Sixteen points placed by hand, each checked against imagery, are ordinary mapping. Do not upload the USGS points with a script: that would be an import, which needs a discussion with the OSM community first ([Import guidelines](https://wiki.openstreetmap.org/wiki/Import/Guidelines)).

## 2. The sources for each municipio

**Primary source: USGS National Structures Dataset** (US Geological Survey, public domain), layer 4 "City/Town Halls" (feature code 83044) of the map service [carto.nationalmap.gov/arcgis/rest/services/structures/MapServer](https://carto.nationalmap.gov/arcgis/rest/services/structures/MapServer/4). The point is placed at the center of the building. It has all 16 halls. We read them on 2026-10-18 with this query (a plain web address; anyone can open it):

`https://carto.nationalmap.gov/arcgis/rest/services/structures/MapServer/4/query?geometry=-67.97,17.85,-65.20,18.57&geometryType=esriGeometryEnvelope&inSR=4326&outSR=4326&outFields=*&f=json`

The coordinates below come from that query. Use them to find the building, then **place the node on the building you see in the imagery**, not at the pasted coordinate: some USGS points were loaded in 2019. "Confirm with" names an official page that gives the same street; "none found" means we found no official page with an address, so check the imagery and, if in doubt, call or visit the municipio.

| Municipio | USGS point (lat, lon), loaded | USGS address (ZIP) | Confirm with | Status |
|---|---|---|---|---|
| Adjuntas | 18.16188, -66.72341 (2019-09-11) | Calle César González Esquina San Joaquín (00601) | None found | Check on imagery; another directory gives a different street at the same corner of San Joaquín |
| Aguas Buenas | 18.25707, -66.10308 (2019-10-22) | 47 Calle Rafael Laza (00703) | None found (the municipio's site is under construction) | Street agrees with another directory; the house number does not (47 against 44): leave `addr:housenumber` out |
| Arroyo | 17.96331, -66.06321 (2024-11-11) | 64 Calle Morse (00714) | [arroyopr.gov, Contáctenos](https://www.arroyopr.gov/contactenos): Calle Morse #64 | Ready |
| Barceloneta | 18.45515, -66.53864 (2019-10-22) | Calle Georgetti (00617) | [barceloneta.pr.gov, Contactos](https://barceloneta.pr.gov/contactos/) (town and ZIP only) | Ready |
| Barranquitas | 18.18607, -66.30656 (2019-07-08) | Calle Luis Muñoz Rivera (00794) | [barranquitas.pr.gov, Contactos](https://barranquitas.pr.gov/contactos/): Calle Muñoz Rivera No. 25 | Ready |
| Cidra | 18.17615, -66.15866 (2024-10-04) | Carretera 172 (00739) | None found | **Hold.** USGS (updated 2024) puts it on PR-172; another directory puts it facing the town plaza. Ask the municipio which building is the seat today |
| Coamo | 18.08065, -66.35693 (2019-10-22) | Calle Mario Braschi (00769) | None found | Ready after the imagery check |
| Florida | 18.36294, -66.56748 (2019-09-12) | 69 Calle Ramón Torres (00650) | [florida.pr.gov, Contactos](https://florida.pr.gov/contactos/) gives another building: PR-140, interior Calle Juan Rosado, second floor, the former Instrucción Pública building | **Hold.** The offices may have moved, perhaps for a while. Ask the municipio before mapping |
| Guayama | 17.98590, -66.11371 (2024-11-15) | Calle Vicente Palés Matos (00785) | None found | Ready after the imagery check |
| Hormigueros | 18.13898, -67.12776 (2019-10-22) | Calle Mateo Fajardo (00660) | None found | **Check.** Another directory names Calle 1ro de Abril: probably a corner building. Confirm on imagery; leave `addr:street` out if unsure |
| Juana Díaz | 18.05352, -66.50577 (2019-10-22) | Calle Degetau (00795) | None found | Ready after the imagery check |
| Juncos | 18.22853, -65.92416 (2024-11-14) | Paseo Escuté Final (00777) | [municipiodejuncos.gov.pr, Contacto](https://www.municipiodejuncos.gov.pr/copy-of-contacto): Paseo Escuté | Ready |
| Orocovis | 18.22678, -66.39132 (2019-07-08) | Calle Luis Muñoz Rivera (00720) | None found (the site shows no address) | Ready after the imagery check |
| Quebradillas | 18.47214, -66.93776 (2019-09-30) | Calle San Carlos (00678) | None found | **Check.** A municipal resolution of 2021-22 may speak of a "former" city hall on Calle San Carlos (not confirmed). Ask the municipio which building is the seat today |
| Río Grande | 18.38121, -65.83017 (2024-11-14) | Calle San José Esquina Calle San Juan (00745) | None found | Ready after the imagery check |
| San Sebastián | 18.33702, -66.99133 (2019-07-08) | Calle Padre Feliciano (00685) | None found | Ready after the imagery check |

"Another directory" is the Comité de Coordinación de Estadísticas' municipal pages (cce.estadisticas.pr), a Puerto Rico government source: use it to compare only, and do not copy anything from it (its pages also list staff contacts). In most towns the Casa Alcaldía faces the plaza pública or plaza de recreo; that is a hint for the search, not a source.

## 3. How to add one

1. Sign in to openstreetmap.org with the account FPR chooses for this work, and open the iD editor ("Edit") at the USGS point.
2. Choose Esri World Imagery or Bing aerial imagery as the background. Find the building.
3. If the building is already drawn, select it and add the tags to it; otherwise add a point (node) on the building. Check first that the hall is not already mapped under another tag (`office=government`, `building=civic`): then fix that feature instead of adding a second one.
4. Tags:

   | Tag | Value | Note |
   |---|---|---|
   | `amenity` | `townhall` | Required: this is what the observatory reads ([Tag:amenity=townhall](https://wiki.openstreetmap.org/wiki/Tag:amenity%3Dtownhall)) |
   | `townhall:type` | `municipality` | The documented value for a municipal seat ([Key:townhall:type](https://wiki.openstreetmap.org/wiki/Key:townhall:type)). `municipal` is not documented (one use worldwide); do not use it |
   | `name` | `Casa Alcaldía de <Municipio>` | The form the 65 halls already in OSM use, with accents (Casa Alcaldía de Juana Díaz) |
   | `operator` | `Municipio de <Municipio>` | Optional; most halls in OSM have it |
   | `addr:street` | the street, written out in Spanish (`Calle Morse`) | Only from the table above (USGS or the municipio's own page) |
   | `addr:housenumber` | the number | Only where the USGS record and the municipio's page agree (Arroyo: 64). Otherwise leave it out |
   | `addr:city`, `addr:postcode`, `addr:state` | `<Municipio>`, the ZIP in the table, `PR` | |
   | `building` | `townhall` | Only on a building outline, if you draw or select one |

   Do not add telephones, e-mails or the names of officials.
5. Save with a changeset comment such as "Add Casa Alcaldía de Arroyo (amenity=townhall)" and a source such as `source=USGS National Structures Dataset;Esri World Imagery` (or Bing, or survey).
6. Skip the municipios marked **Hold** until the municipio confirms the building.

## 4. Check that the observatory picks them up

OSM changes reach the Overpass service within minutes. Then, in the repository, on a machine that can reach Overpass (a GitHub runner cannot; this unit is refreshed by hand):

```
python community_assets.py --refresh townhall
python community_assets.py --check
```

- The first command downloads the city halls again and rewrites `site/data/town_halls.geojson`. Its `notes.municipios_without_a_city_hall_mapped` should no longer list the municipios you mapped, and `notes.municipios_with_a_city_hall` should grow by as many.
- The second rebuilds from the new cache and should print "matches the cache" for the three files.
- Update the counts written in text (the `town_halls` note in `dictionary_src/datasets.json`, the city-hall rows of `docs/community.md` and `README.md`), run `python dictionary.py`, `python catalog.py`, the checks and the tests (`python -m unittest discover -s tests`), and open the map's Layers tab, Infrastructure · City halls, to see the new points.
- A hall mapped without `amenity=townhall`, or outside every municipio's outline, will not appear; a second hall within about 30 meters of one already mapped with the same name is counted once.
