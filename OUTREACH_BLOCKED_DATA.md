# Blocked data: requests to send (drafts, not sent)

Plan item 17 (`docs/proposal-2026-10.md`, J row 17). The PR Data Observatory checked these sources with live requests on 2026-10-05 and 2026-10-06 and did **not** harvest the blocked ones. The one exception is the Police's December municipal reports of Type I crimes, which are live while their terms are confirmed (letters 1 and 2; HANDOFF decision 24). Each blocked source is held back by terms that require written permission, by personal data in the files, by a missing license, or because no open file exists. The status of each is in `site/data/wanted.json` (its "check" and "who_to_ask" fields).

**Nothing here has been sent, and Claude will not contact anyone.** Before any request goes out:

1. **Review.** FPR leadership and Compliance review the text. They decide who signs and which address each request goes to; every address below is a placeholder.
2. **Requests that need leadership approval first.**
   - Section 1, Police: crime counts by barrio. HANDOFF decision 24 approved crime counts only by municipio, and warned that a crime map under FPR's name can stigmatize communities, some of them WCRP communities.
   - Section 3, Comisión Estatal de Elecciones: it asks only for registered voters and votes cast, but it touches elections.
3. **No harvesting before permission.** Nothing is downloaded from a blocked source until its written permission or license is on file. Record it in `wanted.json` and `dictionary_src/sources.json`.

None of these requests is part of federal grant work (HUD CDBG-DR/MIT, USDA, EDA). If one comes to support such work, it also goes through Finance and Compliance review before it is sent. Letters 4 and 5 refer to the site's public money data (federal funds), whose headline is held for Compliance (decision 21): Compliance should see them with that in mind.

## What FPR can offer

Most letters say what FPR will not use (personal data, names, addresses); letters 6b and 7 say what FPR would publish. The commitments below are FPR's to approve (leadership, at the review step). Once approved, offer them when an agency replies, so every agency gets the same terms:

- **Aggregated or facility-level figures only.** No names, addresses, case narratives or person-level records, and small cells suppressed by the agency's rule.
- **Credit and accuracy.** The agency is credited as the source, with the date of the data. Figures are shown as the agency gives them, and derived figures (rates per 1,000 residents, for example) are labeled as such.
- **Terms.** The agency's terms of use are followed, and FPR takes the data off the site if the agency asks. Copies that people have already downloaded cannot be recalled.
- **A copy back.** The agency gets a link to how its data are shown. Help with formats (CSV, GTFS, GeoJSON) at no cost is an offer of staff time, so leadership decides whether to make it.

## Summary

| # | To | What we ask | Why it is blocked today |
|---|---|---|---|
| 1 | Negociado de la Policía (leadership approval first) | Incidents counted by barrio and month, small cells suppressed; a license for the December municipal reports | The public incident feed holds addresses and narratives (personal data) and states no terms |
| 2 | Instituto de Estadísticas | A working portal certificate; vital statistics after 2020 by municipio; a license for the Type I crime reports | The portal fails its TLS certificate check; the annual report stops at 2020 (PDF) |
| 3 | Comisión Estatal de Elecciones (leadership approval first) | Registered voters and votes cast by precinct, in a file | The site blocks automated access; no license stated |
| 4 | ABRE Puerto Rico | Permission to reuse the municipal index, a version without officials' names, and other years | No license; the file names mayors; one year only |
| 5 | Oficina del Contralor | Contract totals by entity, municipio and fiscal year, after fiscal 2022-23; a license | No license; contractor names are personal data; stale since 2022-23 |
| 6 | LUMA Energy and Negociado de Energía | Service interruptions by municipio and month, or written permission to read the outage data | LUMA's terms bar automated access without written permission |
| 7 | Autoridad de Acueductos y Alcantarillados | Service interruptions by municipio or service area | The interruptions page returned 404; no open dataset |
| 8 | Departamento de Salud | Written consent to republish aggregated surveillance series | The terms bar republishing without written consent; some files are person-level |
| 9 | Office of Head Start (HHS) | Reuse terms for the service location file; earlier snapshots | The license is not stated |
| 10 | Departamento de Educación, and ACUDEN or the Departamento de la Familia | School list with openings and closings; licensed child-care centers and capacity | Portals in maintenance or behind a token; no child-care file found |
| — | HRSA, Area Health Resources File | Permission to reuse | Draft already in `docs/health.md` |

---

## 1. Negociado de la Policía de Puerto Rico (leadership approval first)

**Para:** Negociado de la Policía de Puerto Rico, División de Estadísticas de la Criminalidad. [Dirección o buzón a confirmar por FPR]
**Asunto:** Solicitud de datos agregados de incidencia criminal por barrio y mes, y de términos de uso

Estimados señores y señoras:

Foundation for Puerto Rico (FPR) mantiene el Observatorio de Datos de PR, un sitio público de datos abiertos con mapas por municipio. Ya muestra los delitos Tipo I por municipio y año a partir de los informes de diciembre de la Policía, del 2017 al 2025, y acredita a la Policía como fuente.

Para estudiar patrones por debajo del municipio, les solicitamos:

1. Un archivo con el **número de incidentes por barrio y mes**, por tipo de delito (Tipo I o NIBRS), desde el año que tengan disponible. Las celdas pequeñas pueden suprimirse según la regla que ustedes usan (por ejemplo, menos de cinco incidentes).
2. Los **términos de uso** de los informes municipales de diciembre y del archivo solicitado, para citarlos correctamente.

No necesitamos ni publicaríamos direcciones, narrativas ni ningún dato de personas. Por esa razón no usamos el mapa público de incidencias, que contiene esa información.

Con gusto coordinamos una reunión breve.

Atentamente,
[Nombre y cargo — a completar por FPR]

**English summary.** Leadership approves before this is sent: a map of crime by barrio under FPR's name can stigmatize communities (decision 24). We ask the Police Bureau for incident counts by barrio and month and by offense type, with small cells suppressed, and for the reuse terms of the December municipal reports already shown on the site. We would not use or publish addresses, narratives or any personal data. That is why we did not use the public incident map, which holds them.

## 2. Instituto de Estadísticas de Puerto Rico

**Para:** Instituto de Estadísticas de Puerto Rico. [Dirección o buzón a confirmar por FPR]
**Asunto:** Acceso al portal, estadísticas vitales después del 2020 y términos de uso de los informes de delitos Tipo I

Estimados señores y señoras:

El Observatorio de Datos de PR, de Foundation for Puerto Rico, usa los informes de delitos Tipo I que el Instituto publica, y acredita al Instituto y a la Policía. Les escribimos por tres asuntos:

1. **Acceso al portal.** Al conectarnos al portal del Instituto, el certificado de seguridad (TLS) no se valida porque su cadena está incompleta. Esto dificulta la descarga automática de los archivos. Les informamos por si es útil para su equipo técnico.
2. **Estadísticas vitales.** El informe anual que encontramos llega hasta el 2020 y está en PDF. ¿Hay nacimientos y defunciones por municipio y año después del 2020 en un archivo de datos (CSV o Excel)?
3. **Términos de uso.** ¿Qué términos aplican a los informes de delitos Tipo I y a las estadísticas vitales que publica el Instituto?

[Párrafo opcional: el liderato decide si se incluye.] Además, notamos que algunos archivos de los informes de delitos incluyen nombres y correos electrónicos de personal en el pie de página o en las propiedades del archivo. Nosotros no usamos ni publicamos esa información. Se lo comentamos por si les resulta útil.

Atentamente,
[Nombre y cargo — a completar por FPR]

**English summary.** We tell the Instituto that its portal's certificate chain fails to validate. We ask for births and deaths by municipio and year after 2020 as a data file, and for the reuse terms of the Type I crime reports and vital statistics. An optional paragraph, for leadership to keep or drop, mentions that some report files carry staff names and e-mails in their footers or properties; we do not use or publish them.

## 3. Comisión Estatal de Elecciones (leadership approval first)

**Para:** Comisión Estatal de Elecciones. [Dirección o buzón a confirmar por FPR]
**Asunto:** Solicitud de electores inscritos y votantes por precinto en formato de datos

Estimados señores y señoras:

Foundation for Puerto Rico mantiene el Observatorio de Datos de PR, un sitio público de datos abiertos por municipio sobre población, economía y servicios. Queremos mostrar la **participación electoral** por lugar como un indicador cívico, sin análisis partidista.

Les solicitamos:

1. El número de **electores inscritos y votantes por precinto y municipio**, para las elecciones generales que tengan disponibles, en un archivo de datos (CSV o Excel). No necesitamos resultados por partido ni por candidatura.
2. Los términos de uso de esos datos.

Su sitio web no permite la descarga automática, por lo que preferimos pedirlos directamente.

Atentamente,
[Nombre y cargo — a completar por FPR]

**English summary.** We ask the Elections Commission for registered voters and votes cast by precinct and municipio as a data file, and for reuse terms; results by party or candidate are not needed. The stated use is turnout as a civic indicator, with no partisan analysis. **Leadership approves before this is sent.**

## 4. ABRE Puerto Rico

**Para:** ABRE Puerto Rico. [Dirección o buzón a confirmar por FPR]
**Asunto:** Permiso para usar el índice municipal en el Observatorio de Datos de PR

Estimados señores y señoras:

Foundation for Puerto Rico mantiene el Observatorio de Datos de PR. Su índice municipal sería un complemento valioso a los datos de dinero público por municipio que ya mostramos, como los fondos federales.

Les solicitamos:

1. **Permiso** para mostrar el índice por municipio en el Observatorio, con crédito a ABRE y bajo los términos que ustedes indiquen.
2. Una versión del archivo **sin nombres de funcionarios**. Solo mostramos datos agregados por municipio, nunca datos de personas.
3. Si existen, las ediciones de **otros años**, para mostrar el cambio en el tiempo.

Atentamente,
[Nombre y cargo — a completar por FPR]

**English summary.** We ask ABRE for permission to show its municipal index by municipio with credit, for a version without officials' names, and for other years.

## 5. Oficina del Contralor de Puerto Rico

**Para:** Oficina del Contralor de Puerto Rico. [Dirección o buzón a confirmar por FPR]
**Asunto:** Solicitud de totales del Registro de Contratos por entidad, municipio y año fiscal

Estimados señores y señoras:

El Observatorio de Datos de PR, de Foundation for Puerto Rico, muestra el dinero público por municipio, y el Registro de Contratos de la Oficina sería una fuente central. Les solicitamos:

1. **Totales** de contratos (número y cuantía) por entidad, municipio, año fiscal y tipo de servicio, desde el año fiscal 2012-13.
2. Los años fiscales **después del 2022-23**, si ya están disponibles.
3. Los términos de uso de esos datos.

No necesitamos los nombres de los contratistas. Solo publicaríamos totales.

Atentamente,
[Nombre y cargo — a completar por FPR]

**English summary.** We ask the Comptroller for contract counts and amounts by entity, municipio, fiscal year and service type, from fiscal 2012-13 and for years after 2022-23, and for reuse terms. Contractor names are not needed, and only totals would be published.

## 6. LUMA Energy and Negociado de Energía de Puerto Rico

### 6a. LUMA Energy

**Para:** LUMA Energy. [Dirección o buzón a confirmar por FPR]
**Asunto:** Permiso por escrito o archivo periódico de interrupciones de servicio por municipio

Estimados señores y señoras:

Foundation for Puerto Rico mantiene el Observatorio de Datos de PR, que estudia la resiliencia por municipio. Sus términos de uso no permiten el acceso automático al mapa de interrupciones sin permiso por escrito, y por eso no lo usamos.

Les solicitamos una de estas dos opciones:

1. Un **archivo periódico** (mensual, por ejemplo) con el número de clientes afectados y la duración de las interrupciones **por municipio**, desde el año que tengan disponible.
2. **Permiso por escrito** para leer los datos de su mapa de interrupciones con la frecuencia que ustedes indiquen, con crédito a LUMA.

Atentamente,
[Nombre y cargo — a completar por FPR]

### 6b. Negociado de Energía

**Para:** Negociado de Energía de Puerto Rico. [Dirección o buzón a confirmar por FPR]
**Asunto:** Indicadores de confiabilidad del servicio eléctrico por municipio en formato de datos

Estimados señores y señoras:

Foundation for Puerto Rico mantiene el Observatorio de Datos de PR, un sitio público de datos abiertos con mapas por municipio, que estudia la resiliencia por lugar.

Si el Negociado recibe indicadores de confiabilidad del servicio eléctrico (por ejemplo, SAIDI y SAIFI), les solicitamos esos indicadores **por municipio o región y por mes**, en un archivo de datos, con sus términos de uso. Si ya son públicos, ¿dónde se publican? Solo publicaríamos totales por municipio o región; no necesitamos datos de clientes.

Atentamente,
[Nombre y cargo — a completar por FPR]

**English summary.** We ask LUMA for monthly interruptions by municipio (customers affected, duration), or for written permission to read its outage map; its terms bar automated access without it. We ask the Energy Bureau, if it receives reliability indicators (SAIDI, SAIFI), for them by municipio or region and month as a data file. The site shows no outage data today; EAGLE-I reports Puerto Rico only as six LUMA regions.

## 7. Autoridad de Acueductos y Alcantarillados (AAA)

**Para:** Autoridad de Acueductos y Alcantarillados. [Dirección o buzón a confirmar por FPR]
**Asunto:** Solicitud de datos de interrupciones del servicio de agua por municipio

Estimados señores y señoras:

El Observatorio de Datos de PR, de Foundation for Puerto Rico, ya muestra por municipio los sistemas de agua comunitarios y sus registros de cumplimiento, con datos de la EPA. La página de interrupciones de la AAA no estaba disponible cuando la consultamos (error 404), y no encontramos un conjunto de datos abierto.

Les solicitamos las **interrupciones del servicio**, programadas y no programadas, con fecha, duración y municipio o área de servicio afectada, desde el año que tengan disponible, en un archivo de datos, con sus términos de uso. Solo publicaríamos totales por municipio o área de servicio; no necesitamos datos de clientes.

Atentamente,
[Nombre y cargo — a completar por FPR]

**English summary.** We ask PRASA for planned and unplanned interruptions with date, duration and municipio or service area, as a data file with reuse terms.

## 8. Departamento de Salud

**Para:** Departamento de Salud de Puerto Rico, a la oficina a cargo del servicio de datos de Bioestadísticas. [Dirección o buzón a confirmar por FPR]
**Asunto:** Consentimiento por escrito para publicar series agregadas de vigilancia

Estimados señores y señoras:

Foundation for Puerto Rico mantiene el Observatorio de Datos de PR. Sus términos indican que los datos del servicio de Bioestadísticas no se pueden republicar sin consentimiento por escrito, y por eso no los hemos usado.

Les solicitamos **consentimiento por escrito** para mostrar series de vigilancia **agregadas por municipio y año** (o por región, si es lo que publican), con la supresión de celdas pequeñas que ustedes indiquen, y con crédito al Departamento.

No usaríamos ni publicaríamos los archivos con registros de personas ni los nombres de proveedores. Solo usaríamos totales.

Atentamente,
[Nombre y cargo — a completar por FPR]

**English summary.** We ask the Department of Health for written consent to show surveillance series aggregated by municipio and year, with its small-cell suppression. Person-level files and provider names would not be used.

## 9. Office of Head Start (HHS)

**To:** Office of Head Start, Administration for Children and Families, U.S. Department of Health and Human Services. [Address to be confirmed by FPR]
**Subject:** Reuse terms for the Head Start service location file (Puerto Rico)

Dear Office of Head Start,

Foundation for Puerto Rico maintains the PR Data Observatory, a public open-data site with maps by municipio. Your service location file listed 852 sites in Puerto Rico with 21,907 funded slots when we read it on 2026-10-05. It would show where early-childhood services are, next to where young children live.

We ask:

1. Under what terms may the file be reused and shown in the observatory (for example, counts of sites and funded slots by municipio), with credit to the Office of Head Start?
2. Are earlier snapshots available? The file is a daily snapshot, and a history would show change over time.

We would show site and slot figures only; no personal data.

Sincerely,
[Name and title — to be completed by FPR]

## 10. Departamento de Educación, and ACUDEN or the Departamento de la Familia

**Para:** Departamento de Educación de Puerto Rico; Administración para el Cuidado y Desarrollo Integral de la Niñez (ACUDEN). [Direcciones o buzones a confirmar por FPR. Antes de enviar, confirmar qué agencia otorga las licencias de los centros de cuido: puede ser el Departamento de la Familia y no ACUDEN.]
**Asunto:** Lista de escuelas con su estado y lista de centros de cuido licenciados

Estimados señores y señoras:

El Observatorio de Datos de PR, de Foundation for Puerto Rico, ya muestra escuelas y matrícula por municipio a partir de datos federales (NCES). Para completar el cuadro con datos de Puerto Rico, solicitamos:

1. **Al Departamento de Educación:** la lista de escuelas públicas con su municipio y su estado (abierta, cerrada o consolidada), con la fecha de cada cierre o consolidación.
2. **A la agencia que otorga las licencias de cuido:** la lista de centros de cuido licenciados con su municipio y su capacidad licenciada.
3. A ambos, los términos de uso de esos datos.

Los portales datos.pr.gov y Busca tu Escuela estaban en mantenimiento o requerían una clave cuando los consultamos. Solo mostraríamos datos de las instalaciones, nunca de estudiantes ni de personas.

Atentamente,
[Nombre y cargo — a completar por FPR]

**English summary.** We ask the Department of Education for the school list with status and closing dates, and the agency that licenses child-care centers (ACUDEN or the Department of the Family: confirm before sending) for licensed centers with capacity, both by municipio and with reuse terms. Only facility data would be shown.

---

## After a reply

- **Written permission or license:** save it with FPR's records (not in this repo if it names people). Set the row in `site/data/wanted.json` to **checked** with the date and the terms, and add the license to `dictionary_src/sources.json`. The harvest then becomes a normal data item, with tests and a dictionary entry.
- **No reply or a refusal:** note the date in the row's "check" field and keep it **blocked**.
