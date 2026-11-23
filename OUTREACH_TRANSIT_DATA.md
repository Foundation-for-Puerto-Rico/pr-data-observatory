# Transit data: requests to send (drafts, not sent)

Status of public transit data in Puerto Rico as of 2026-10-02, and the messages that would close the gaps. Nothing here has been sent. Review with FPR leadership and Compliance first, and decide who signs.

## What the PR Data Observatory can show today

| Need | Status | Source |
|---|---|---|
| Routes and stops of ATI (Tren Urbano, AMA/Metrobús/Metro Urbano, AcuaExpreso) | Published, current to 2027-07-19 | ATI GTFS |
| Routes and stops of municipal bus and trolley systems | 24 systems publish a GTFS feed (16 current, 1 expiring, 7 expired on 2026-10-02); 15 more municipal systems report to the federal transit database and publish nothing | National RTAP portal, FTA National Transit Database |
| Públicos | Only 16 routes mapped by volunteers in OpenStreetMap; no agency data | OpenStreetMap |
| Real-time bus positions | **Not public.** ATI lists GTFS-Realtime as "en desarrollo". The AMA Móvil app and the independent transPRte app show positions, but no feed is published | ATI open data page |
| Real-time ferry positions | App only (City Experiences) | ATI |

The tool already shows vehicles on their timetable, and it will show real positions as soon as a feed exists.

## 1. Request to ATI: GTFS-Realtime feed (Spanish)

**Para:** Autoridad de Transporte Integrado, Planificación (buzón indicado en el feed GTFS: planificacion@ati.pr.gov)
**Asunto:** Solicitud de acceso al feed GTFS-Realtime (posiciones de vehículos y alertas)

Estimados señores y señoras:

Foundation for Puerto Rico (FPR) mantiene el Observatorio de Datos de PR, un sitio público de datos abiertos con mapas que ya incorpora el feed GTFS de ATI y los feeds de 24 sistemas municipales. Lo usamos para estudiar la integración del transporte colectivo y posibles rutas nuevas.

Vimos en su página de datos abiertos que el feed GTFS-RT está "en desarrollo". Nos interesa saber:

1. ¿Hay una fecha estimada para publicar el feed GTFS-Realtime (posiciones de vehículos, pronósticos de llegada y alertas de servicio)?
2. ¿Podemos probar el feed antes de su publicación general, con el compromiso de acreditar a ATI como fuente?
3. ¿Qué condiciones de uso aplican? Podemos mostrar los datos con la fuente y la hora de actualización, sin alterarlos.
4. Notamos que aplicaciones independientes muestran la posición de las rutas expreso (T3, E10, E20, E30, E40, C22, C35, C36). ¿Se puede ofrecer el mismo acceso de forma abierta?

Con gusto coordinamos una reunión breve.

Atentamente,
[Nombre y cargo — a completar por FPR]

**English version.** Foundation for Puerto Rico maintains the PR Data Observatory, a public open-data site with maps that already includes ATI's GTFS feed and the feeds of 24 municipal systems. We use it to study how collective transit could be integrated and where new routes might go. Your open data page lists GTFS-Realtime as "en desarrollo". Is there an expected publication date? Could we test the feed before general release, crediting ATI as the source? What terms of use apply? Independent apps already show positions for the express routes (T3, E10, E20, E30, E40, C22, C35, C36); could the same access be offered openly? We would be glad to meet.

## 2. Request to each municipality without a public feed (Spanish)

Send to the transit or planning office of: Aguada, Añasco, Barceloneta, Camuy, Carolina, Cataño, Cayey, Comerío, Dorado, Gurabo, Hormigueros, Lares, Mayagüez, Toa Baja, Yauco. (These report a municipal bus system to the federal transit database but have no public GTFS feed we could find. Hormigueros and Barceloneta link a web page or document instead of a feed.)

**Asunto:** Publicar el horario y las rutas de [sistema municipal] en formato abierto (GTFS)

Estimado/a [cargo]:

Su municipio opera transporte colectivo y lo informa a la Base de Datos Nacional de Tránsito (FTA). Publicar rutas, paradas y horarios en formato GTFS permite que aplicaciones y mapas públicos, incluido el Observatorio de Datos de PR de FPR, muestren su servicio y lo conecten con otros sistemas. Veinticuatro municipios ya lo hacen a través del portal nacional de RTAP (rapid.nationalrtap.org).

Ofrecemos ayuda para generar el archivo a partir de sus horarios actuales, sin costo. Si ya tienen un archivo, indíquennos dónde está publicado.

Atentamente,
[Nombre y cargo — a completar por FPR]

## 3. Municipalities with an expired or expiring feed

Ask the same office to upload a new GTFS file: Ponce (expired 2024-12-31), Hatillo (2025-12-31), Cidra (2026-01-15), Caguas (2026-01-31), San Lorenzo (2026-02-28), Fajardo (2026-06-15), Juncos (2026-07-31), Canóvanas (expires 2026-10-31). The site marks these as expired and leaves them out of the "vehicles now" view.

## 4. Route shapes

Most municipal feeds list stops but no route shape, so the map joins the stops in order (dotted lines). Ask each system to export `shapes.txt`; only Bayamón, Guaynabo, Cidra, Orocovis and San Sebastián include shapes.

## 5. Independent app (optional)

transPRte (SENDA LLC, support@sendapr.com) says it shows live positions for ATI express buses "using the positions the operator publishes". Ask whether the source is a feed ATI could also publish openly. FPR should not copy data out of an app without the operator's written permission.

## 6. Live data that needs no permission but needs a relay

Community ADS-B networks (adsb.lol, adsb.fi) publish free live aircraft positions, but their servers do not allow requests from a web page. A small relay (Cloudflare Worker or Azure Function, about 30 lines) would show flights near the airports. FPR would need to host it. Ship positions (AIS) need a free API key from a provider such as aisstream.io.
