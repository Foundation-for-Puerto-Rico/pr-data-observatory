# Sharing the PR Data Observatory

## Live links

| Page | URL |
|---|---|
| PR Data Observatory (2D map) | https://observatory.foundationpr.org/ |
| 3D + Time | https://observatory.foundationpr.org/3d.html |
| FPR Research in Data · The State of Housing | https://observatory.foundationpr.org/housing.html |
| Knowledge Area · WCRP (published with an "In review" marker; not indexed) | https://observatory.foundationpr.org/wcrp.html |
| A municipality directly (example) | https://observatory.foundationpr.org/#San%20Juan |

Hosting: Azure Static Web Apps, deployed from the `site/` folder of the public repo `Foundation-for-Puerto-Rico/pr-data-observatory` by the workflow in `.github/workflows/pages.yml` (`docs/azure.md`). Every push to `main` that touches `site/` republishes within about two minutes. The repo stays private; only the site is public.

## Before sharing outside FPR

- Compliance review of the housing page (the study was produced under the NALCAB Advancing Equitable Neighborhood Development grant).
- The WCRP page (`wcrp.html`) is published with an "In review" marker (the project lead's approval of 2026-10-19, HANDOFF decision 51): its content may still change, so say so when you share it. WCRP is a HUD CDBG-DR program. The original index and the Social Capital Mapping list state no open license: FPR publishes them on the observatory with the program's approval (the data contract's license reviews were cleared on 2026-10-19, HANDOFF decision 54), and anyone who wants to re-use them should ask PRDOH and FPR first.
- Personal data: place listings carry business names only. Phone numbers and emails are used while the data is built and are not published (removed 2026-10-01; the file served before that date included them, so Compliance may want to note it). Street addresses and websites were published until 2026-10-18 and are removed (about 1,240 of the 9,683 websites were social-media, bio-link or messaging pages; telephone numbers written into 4 names are removed too). Private homes, holiday rentals, residential buildings, listings named by a street address and care, shelter or treatment services (3,360 listings) are counted in their municipality but not drawn and have no name, id or point in the file (`docs/places-privacy.md`). Copies of the data made before 2026-10-18 still hold the addresses and websites.
- Licenses: every layer is public data with the license or terms shown in each page's About / Sources section; nine sources state no license (the dictionary's list of sources says which). Two cases need care when re-sharing the data files: OpenStreetMap-derived stops (`transport.json`) are ODbL, which requires attribution and share-alike; and the original WCRP index and the Social Capital Mapping list's flags (`wcrp_rvi_barrio.json`, `wcrp_rvi_inputs.json`, `wcrp_social.json`) state no open license, so others should ask PRDOH and FPR before re-using them.

## One-paragraph description (EN)

The PR Data Observatory is an open model of Puerto Rico built by Foundation for Puerto Rico. It puts public data from many fields (housing, jobs, transport, hazards and more, growing over time) on one map and one timeline for all 78 municipalities, so anyone can compare them, ask questions and cite the source of every number. A 3D view adds terrain, buildings, a replay of a full day of transit and hurricane tracks since 1851, and the first "FPR Research in Data" page turns FPR's 2023 study The State of Housing in Puerto Rico into live charts and maps for every municipality. Open data and no API keys; the one exception, the short-term rental counts that were licensed to FPR for its 2023 study, is marked on the page. Every source is credited.

## Un párrafo (ES)

El Observatorio de Datos de PR es un modelo abierto de Puerto Rico creado por Foundation for Puerto Rico. Pone datos públicos de muchos campos (vivienda, empleos, transporte, riesgos y más, y seguirá creciendo) en un mismo mapa y una misma línea de tiempo para los 78 municipios, para que cualquier persona pueda compararlos, hacer preguntas y citar la fuente de cada cifra. Una vista 3D añade relieve, edificios, la repetición de un día completo de transporte público y trayectorias de huracanes desde 1851, y la primera página de "FPR Research in Data" convierte el estudio de FPR de 2023 El Estado de la Vivienda en Puerto Rico en gráficas y mapas vivos para cada municipio. Datos abiertos y sin claves de API; la única excepción, los conteos de alquileres a corto plazo que se cedieron bajo licencia a FPR para su estudio de 2023, está señalada en la página. Cada fuente está acreditada.

## Note for the WordPress team

> Please add a menu item or page linking to the PR Data Observatory at https://observatory.foundationpr.org/ (suggested label: "Data Observatory"; in Spanish, "Observatorio de Datos de PR"). The housing study page can be embedded on the Housing in Puerto Rico page with the iframe below, or linked at https://observatory.foundationpr.org/housing.html. No plugin, upload or database is needed; the site is hosted on GitHub Pages and updates on its own.

Embed (works in a WordPress Custom HTML block):

```html
<iframe src="https://observatory.foundationpr.org/housing.html?embed=1"
        title="FPR Research in Data: The State of Housing in Puerto Rico"
        style="width:100%;height:85vh;border:0;border-radius:12px" loading="lazy" allowfullscreen></iframe>
```

For the map views use the same tag with `index.html` or `3d.html` (no `?embed`; they keep their own top bar). Give them a frame at least 900 px wide and 700 px tall: below 860 px wide the pages switch to the phone layout, so on phones link to the page instead of embedding it. `?embed=1` on the housing page hides its top bar and table of contents.

Indexing: `housing.html` carries `noindex` until Compliance has reviewed it; delete the robots meta tag in that file to allow search engines. `dictionary.html` and `profile.html` carry `noindex, follow` for the same review (HANDOFF decision 13). `data-management.html` is open to search engines (HANDOFF decision 56(a), 2026-10-20) and can be shared and linked like the map: https://observatory.foundationpr.org/data-management.html. `wcrp.html` carries `noindex, nofollow` and a visible "In review" notice, with the small "In review" badge on its tab, while its review marker is on; remove them together, when the marker is taken off (`review: true` in `site/js/core/knowledge.js`, docs/knowledge-areas.md).

## Attribution line (for posts, slides, emails)

Map data © OpenStreetMap contributors; places © Overture Maps Foundation; FEMA NFHL; NOAA (sea level rise, HURDAT2); USGS PAD-US; US Census Bureau (2010, 2020, ACS); ATI GTFS; FAA/BTS; Junta de Planificación PUT 2015; FPR, The State of Housing in Puerto Rico (2023), NALCAB Advancing Equitable Neighborhood Development grant.

## Custom domain (optional, later)

Ask IT to create a DNS CNAME `twin.foundationforpuertorico.org → foundation-for-puerto-rico.github.io`, then set the custom domain in the repo's Pages settings. Links above keep working either way.

## Updating the data

```bash
venv\Scripts\python build.py --label "Snapshot 2026-11"
git add site/data && git commit -m "Snapshot 2026-11" && git push
```

The snapshot label appears in the top bar of every page.
