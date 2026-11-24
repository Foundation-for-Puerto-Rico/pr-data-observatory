"""Writes the Knowledge Area page "Reservoirs" (site/reservoirs.html) and its Spanish (i18n_src/es/reservoirs.json).

  python docs/analysis/reservoirs-2026-11/make_page.py   read site/data/reservoir_history.json (python reservoirs.py makes it); write the page and the Spanish
                                                         of the page and of site/js/reservoirs_page.js. Then run python i18n.py.

The page follows the site's language rule (docs/i18n.md) and the pattern of the Urban heat page (docs/analysis/urban-heat-2026-11/make_page.py): every string
is written once, as an (English, Spanish) pair, and every figure in the static text is read from the data file; the figures that change (today's levels) are
the script's. HANDOFF decision 98: how Puerto Rico's reservoirs stand now against their own history, with no volume (USGS publishes none) and without AAA's
alert levels (no licence stated). Prepared with Claude (AI) for FPR, 2026-11-10.
"""
import html
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
ES = {}


def t(en, es):
    key = " ".join(en.split())
    if key in ES and ES[key] != es:
        raise SystemExit(f"two Spanish texts for {key!r}")
    ES[key] = " ".join(es.split())
    return html.escape(key, quote=False)


JS = [
    ("The data could not be loaded ({error}). Check your connection and reload.", "No se pudieron cargar los datos ({error}). Verifique su conexión y vuelva a cargar la página."),
    ("Lower than usual", "Más bajo de lo usual"),
    ("Usual for this time of year", "Usual para esta época del año"),
    ("Higher than usual", "Más alto de lo usual"),
    ("No usual range for this week", "Sin rango usual para esta semana"),
    ("Water at {p}% of its 2011-2025 range", "Agua al {p} % de su rango de 2011-2025"),
    ("{p}% of its range", "{p} % de su rango"),
    ("Loading the latest readings from USGS…", "Cargando las lecturas más recientes de USGS…"),
    ("Latest readings from USGS loaded {t}; they are provisional, as USGS publishes them.", "Lecturas más recientes de USGS cargadas el {t}; son provisionales, como USGS las publica."),
    ("The latest readings could not be loaded from USGS: the figures are those of {date}.", "No se pudieron cargar las lecturas más recientes de USGS: las cifras son las del {date}."),
    ("Of the {n} reservoirs in AAA's daily report, {low} are lower than usual for this time of year, {usual} are within their usual range and {high} are higher.",
     "De los {n} embalses del informe diario de la AAA, {low} están más bajos de lo usual para esta época del año, {usual} están dentro de su rango usual y {high} están más altos."),
    ("The median reservoir sits at {f}% of its own 2011-2025 range, and its level is higher than in {p}% of the years 2011-2025 for this week.",
     "El embalse mediano está al {f} % de su propio rango de 2011-2025, y su nivel es más alto que en el {p} % de los años de 2011-2025 para esta semana."),
    ("Reservoir", "Embalse"), ("Water (share of its 2011-2025 range)", "Agua (parte de su rango de 2011-2025)"), ("Level now (m)", "Nivel ahora (m)"),
    ("Change in 7 days (m)", "Cambio en 7 días (m)"), ("Change in 30 days (m)", "Cambio en 30 días (m)"),
    ("Higher than in this share of years, same week", "Más alto que en esta parte de los años, misma semana"), ("Status", "Estado"),
    ("{p}% ({b} of {n} years)", "{p} % ({b} de {n} años)"),
    ("Puerto Rico: median of AAA's {n} reservoirs", "Puerto Rico: mediana de los {n} embalses de la AAA"),
    ("Puerto Rico: the median of AAA's {n} reservoirs", "Puerto Rico: la mediana de los {n} embalses de la AAA"),
    ("{low} lower · {usual} usual · {high} higher", "{low} más bajos · {usual} usuales · {high} más altos"),
    ("Reservoirs ranked from the lowest to the highest for this time of year", "Embalses ordenados del más bajo al más alto para esta época del año"),
    ("Level now", "Nivel ahora"), ("{v} m above mean sea level", "{v} m sobre el nivel medio del mar"), ("Change", "Cambio"),
    ("{a} m in 7 days, {b} m in 30 days", "{a} m en 7 días, {b} m en 30 días"),
    ("This week in 2011-2025", "Esta semana en 2011-2025"),
    ("Usual range {a} to {b} m; today's level is higher than in {p}% of those years ({k} of {n}).", "Rango usual de {a} a {b} m; el nivel de hoy es más alto que en el {p} % de esos años ({k} de {n})."),
    ("Its range in 2011-2025", "Su rango en 2011-2025"), ("{lo} m ({lod}) to {hi} m ({hid})", "{lo} m ({lod}) a {hi} m ({hid})"),
    ("Lowest on record", "El más bajo registrado"), ("{v} m on {d} (since {m0})", "{v} m el {d} (desde {m0})"),
    ("See it on the map", "Verlo en el mapa"), ("AAA's alert level for this reservoir", "Nivel de alerta de la AAA para este embalse"),
    ("{name}: daily level over the last {n} days, over its usual range for each week", "{name}: nivel diario de los últimos {n} días, sobre su rango usual de cada semana"),
    ("m above mean sea level", "m sobre el nivel medio del mar"), ("Daily level", "Nivel diario"),
    ("Usual range for the week (10th to 90th percentile, 2011-2025)", "Rango usual de la semana (percentil 10 a 90, 2011-2025)"), ("Latest reading", "Lectura más reciente"),
    ("{v} m", "{v} m"), ("Usual: {a} to {b} m", "Usual: de {a} a {b} m"),
    ("{month} in every year since {y0}", "{month} de cada año desde {y0}"),
    ("{name}: mean level in {month} of each year since {y0}; the last dot is this month so far", "{name}: nivel promedio de {month} de cada año desde {y0}; el último punto es este mes hasta ahora"),
    ("Each dot is the mean level of the month; this year's (larger, darker) is the month so far. A missing year had fewer than 15 days of readings that month.",
     "Cada punto es el nivel promedio del mes; el de este año (más grande y oscuro) es el mes hasta ahora. Un año que falta tuvo menos de 15 días de lecturas ese mes."),
    ("Every month since {m0}", "Cada mes desde {m0}"), ("{name}: mean level of every month since {m0}", "{name}: nivel promedio de cada mes desde {m0}"),
    ("lowest 2011-2025: {v} m", "más bajo de 2011-2025: {v} m"),
    ("Share of AAA's reservoirs below their usual level for the month, each month since {y}", "Parte de los embalses de la AAA bajo su nivel usual del mes, cada mes desde {y}"),
    ("% of AAA's reservoirs with data", "% de los embalses de la AAA con datos"),
    ("{low} of {n} reservoirs below their usual level for the month", "{low} de {n} embalses bajo su nivel usual del mes"),
    ("The months with the largest share below usual: {list}.", "Los meses con la mayor parte bajo lo usual: {list}."),
    ("{month} {y} ({low} of {n})", "{month} de {y} ({low} de {n})"),
]
# Section 4 (js/reservoirs_upstream.js, on first use with its Spanish module 'upstream'; decision 107, step 9, fourth part): written to
# i18n_src/es/reservoirs_upstream.json, so neither counts against the page's first load.
UP = [
    ("Reservoir", "Embalse"), ("River gauge", "Medidor de río"), ("Land that drains to it (km²)", "Terreno que drena hacia él (km²)"),
    ("USGS's drainage area (km²)", "Área de drenaje según USGS (km²)"), ("Residents", "Residentes"), ("Buildings", "Edificios"),
    ("Wastewater treatment plants", "Plantas de tratamiento de aguas residuales"), ("Protected land (%)", "Terreno protegido (%)"),
    ("not checked", "sin comprobar"), ("{d}% apart", "{d} % de diferencia"),
    ("USGS publishes no drainage area for this site, so the land found here is not checked.", "USGS no publica un área de drenaje para este lugar, así que el terreno hallado aquí no se comprueba."),
    ("The land found here differs from USGS's drainage area by more than a quarter.", "El terreno hallado aquí difiere del área de drenaje de USGS en más de una cuarta parte."),
    ("Off the stream, fed by a canal or pumps: the stream network cannot say what drains into it, and USGS publishes no drainage area.",
     "Fuera del cauce, alimentado por un canal o por bombeo: la red de ríos no puede decir qué drena hacia él, y USGS no publica un área de drenaje."),
    ("What lies upstream of each river gauge", "Qué hay aguas arriba de cada medidor de río"), ("What lies upstream of each reservoir", "Qué hay aguas arriba de cada embalse"),
    ("The river gauges", "Los medidores de río"),
    ("The data could not be loaded ({error}). Check your connection and reload.", "No se pudieron cargar los datos ({error}). Verifique su conexión y vuelva a cargar la página."),
    ("{most} has the most people upstream: {n} residents on {km} km². {p} of the {r} reservoirs on a stream have a wastewater treatment plant upstream. The land found here is within a quarter of USGS's own drainage area for {w} of the {u} sites USGS gives one.",
     "{most} tiene la mayor cantidad de gente aguas arriba: {n} residentes en {km} km². {p} de los {r} embalses en un cauce tienen una planta de tratamiento de aguas residuales aguas arriba. El terreno hallado aquí está dentro de una cuarta parte del área de drenaje de USGS en {w} de los {u} lugares para los que USGS da una."),
    ("The land whose rain runs into each reservoir and past each river gauge, and what is on it: residents, buildings, wastewater treatment plants and protected land. The land comes from the US Geological Survey's map of small catchments linked downstream, the same one as the map's tool What drains here. Select a column heading to sort; hold the pointer on a number of plants to read their names.",
     "El terreno cuya lluvia corre hacia cada embalse y pasa por cada medidor de río, y lo que hay en él: residentes, edificios, plantas de tratamiento de aguas residuales y terreno protegido. El terreno viene del mapa de pequeñas cuencas enlazadas aguas abajo del Servicio Geológico de los Estados Unidos, el mismo de la herramienta Qué drena aquí del mapa. Seleccione el encabezado de una columna para ordenar; deje el puntero sobre un número de plantas para leer sus nombres."),
    ("Read the figures upstream with care.", "Lea con cuidado las cifras aguas arriba."),
    ("A count on the land upstream says what is there, not what reaches the water: a wastewater plant may discharge below the reservoir, and most homes are not on a sewer. In the northern karst water also moves underground, so the land that drains on the surface is not all the water that arrives. Some reservoirs also receive water piped or channelled from another basin, and six are off the stream, fed by canals or pumps: for those the page gives no figures.",
     "Un conteo en el terreno aguas arriba dice qué hay allí, no qué llega al agua: una planta de aguas residuales puede descargar más abajo del embalse, y la mayoría de las viviendas no están conectadas al alcantarillado. En el carso del norte el agua también se mueve bajo tierra, así que el terreno que drena por la superficie no es toda el agua que llega. Algunos embalses reciben además agua por tubería o canal desde otra cuenca, y seis están fuera del cauce, alimentados por canales o bombeo: para esos la página no da cifras."),
    ("What drains into it.", "Qué drena hacia él."),
    ("Each reservoir and gauge is placed on the catchment of its own stream: within 300 m, the catchment whose stream bears its name and drains the most land; else, within 150 m, the one that drains the most land. Its land is that catchment and every catchment upstream of it. A split in a river is followed only when both branches reach the same mouth, and river mouths are not linked along the coast. Residents and housing units are the 2020 census blocks whose point is on that land; buildings, the footprints of the map's building layer; wastewater plants, EPA's publicly owned treatment works whose permit is in force; protected land, the areas of PAD-US. The check is USGS's own drainage area for each site; the sites more than a quarter apart are marked. The method and the check are in docs/upstream.md of the project repository.",
     "Cada embalse y medidor se ubica en la cuenca pequeña de su propio río: a menos de 300 m, la que lleva su nombre y drena más terreno; si no, a menos de 150 m, la que drena más terreno. Su terreno es esa cuenca y todas las que están aguas arriba. Una bifurcación de un río se sigue solo cuando ambas ramas llegan a la misma desembocadura, y las desembocaduras no se enlazan a lo largo de la costa. Los residentes y las unidades de vivienda son los bloques censales de 2020 cuyo punto está en ese terreno; los edificios, las huellas de la capa de edificios del mapa; las plantas de aguas residuales, las plantas públicas de tratamiento de la EPA con permiso vigente; el terreno protegido, las áreas de PAD-US. La comprobación es el área de drenaje que USGS publica para cada lugar; se marcan los lugares que difieren en más de una cuarta parte. El método y la comprobación están en docs/upstream.md del repositorio del proyecto."),
    ("What drains into each reservoir.", "Qué drena hacia cada embalse."),
    ("USGS NHDPlus High Resolution catchments and USGS's drainage areas (NWIS site service); EPA Facility Registry Service, publicly owned treatment works; USGS PAD-US protected areas; US Census Bureau 2020 blocks; Overture Maps buildings (ODbL). The data file is data/upstream.json (upstream.py).",
     "Cuencas pequeñas de USGS NHDPlus High Resolution y áreas de drenaje de USGS (servicio de sitios de NWIS); Registro de Instalaciones de la EPA, plantas públicas de tratamiento; áreas protegidas de PAD-US de USGS; bloques de 2020 de la Oficina del Censo de EE. UU.; edificios de Overture Maps (ODbL). El archivo de datos es data/upstream.json (upstream.py)."),
    ("Loading what drains into each reservoir…", "Cargando qué drena hacia cada embalse…"),
]
for en, es in JS:
    t(en, es)


def build():
    D = json.loads((ROOT / "site" / "data" / "reservoir_history.json").read_text(encoding="utf-8"))
    y0, y1 = D["years"]
    n, n_aaa = len(D["reservoirs"]), sum(r["aaa"] for r in D["reservoirs"])
    oldest = min(r["m0"] for r in D["reservoirs"])[:4]
    other = n - n_aaa
    heat = (ROOT / "site" / "urban-heat.html").read_text(encoding="utf-8")
    ver = lambda name: re.search(re.escape(name) + r"\?v=(\d+)", heat).group(1)
    I18N_V = 63   # the ?v= of js/i18n.js also versions this page's Spanish bundle: raise it when the page's strings change (docs/i18n.md, rule 12)
    icons = sorted(set(re.search(r"icon_names=([a-z0-9_,]+)", heat).group(1).split(",")) | {"school", "water", "water_drop", "arrow_downward", "arrow_upward", "check", "remove", "open_in_new", "show_chart", "history", "park", "account_tree", "dark_mode", "explore", "grid_view", "light_mode"})

    page = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{t("Knowledge Area · Reservoirs", "Área de conocimiento · Embalses")}</title>
<meta name="description" content="{t("How full Puerto Rico's reservoirs are now compared with the same time of year in the past, how each one has changed, and how they stand together, from the US Geological Survey's live gauges.", "Qué tan llenos están los embalses de Puerto Rico ahora comparados con la misma época en años anteriores, cómo ha cambiado cada uno y cómo están en conjunto, con los medidores en vivo del Servicio Geológico de los Estados Unidos.")}">
<meta name="robots" content="noindex, nofollow">
<meta name="theme-color" content="#FFFFFF">
<link rel="icon" href="img/fpr-mark.png">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Material+Symbols+Rounded:opsz,wght,FILL,GRAD@24,400,1,0&icon_names={",".join(icons)}&display=block">
<link rel="stylesheet" href="css/twin.css?v={ver("css/twin.css")}">
<link rel="stylesheet" href="css/housing.css?v={ver("css/housing.css")}">
<link rel="stylesheet" href="css/public_money.css?v={ver("css/public_money.css")}">
<link rel="stylesheet" href="css/urban_heat.css?v={ver("css/urban_heat.css")}">
<link rel="stylesheet" href="css/reservoirs.css?v=2">
<link rel="stylesheet" href="css/chat.css?v={ver("css/chat.css")}">
<link rel="stylesheet" href="css/ws.css?v=1">
<script src="js/i18n.js?v={max(int(ver("js/i18n.js")), I18N_V)}" data-page="reservoirs"></script>
</head>
<body class="research">
<a class="skip" href="#now">{t("Skip to the content", "Ir al contenido")}</a>
<header class="topbar">
  <a class="logo" href="index.html" title="{t("PR Data Observatory home", "Inicio del Observatorio de Datos de PR")}"><img src="img/fpr-logo.png" alt="{t("Foundation for Puerto Rico. PR Data Observatory home", "Foundation for Puerto Rico. Inicio del Observatorio de Datos de PR")}"></a>
  <div class="brand"><b>{t("Knowledge Area · Reservoirs", "Área de conocimiento · Embalses")}</b><span>{t("How much water Puerto Rico's reservoirs hold now, compared with their own history", "Cuánta agua tienen los embalses de Puerto Rico ahora, comparada con su propia historia")}</span></div>
  <div class="spacer"></div>
  <nav class="views" aria-label="{t("Views", "Vistas")}">
    <a class="btn" href="explore.html" title="{t("Explore: start from a question, a topic or a saved map", "Explorar: comience con una pregunta, un tema o un mapa guardado")}"><span class="ms-icon" aria-hidden="true">explore</span><span class="lbl">{t("Explore", "Explorar")}</span></a>
    <a class="btn" href="data.html" title="{t("Data: every dataset, map layer and set of places", "Datos: todos los conjuntos de datos, capas del mapa y grupos de lugares")}"><span class="ms-icon" aria-hidden="true">grid_view</span><span class="lbl">{t("Data", "Datos")}</span></a>
    <a class="btn" href="index.html"><span class="ms-icon" aria-hidden="true">map</span><span class="lbl">{t("Map", "Mapa")}</span></a>
    <a class="btn" href="workflows.html" title="{t("Workflows: steps that turn data into a result on the map", "Flujos de trabajo: pasos que convierten datos en un resultado en el mapa")}"><span class="ms-icon" aria-hidden="true">account_tree</span><span class="lbl">{t("Workflows", "Flujos")}</span></a>
    <a class="btn" href="3d.html" title="{t("Immersive 3D + time view", "Vista inmersiva en 3D y tiempo")}"><span class="ms-icon" aria-hidden="true">view_in_ar</span><span class="lbl">{t("3D + Time", "3D + Tiempo")}</span></a>
    <a class="btn" href="knowledge.html" aria-current="page" title="{t("Knowledge: FPR studies, analyses and tools", "Conocimiento: estudios, análisis y herramientas de FPR")}"><span class="ms-icon" aria-hidden="true">lightbulb</span><span class="lbl">{t("Knowledge", "Conocimiento")}</span></a>
    <a class="btn" href="dictionary.html" title="{t("Data dictionary: meanings, sources, licenses, how to cite", "Diccionario de datos: significados, fuentes, licencias y cómo citar")}"><span class="ms-icon" aria-hidden="true">menu_book</span><span class="lbl">{t("Data dictionary", "Diccionario de datos")}</span></a>
    <a class="btn" href="learn.html" title="{t("Learn: short lessons about maps and spatial analysis", "Aprende: lecciones cortas sobre mapas y análisis espacial")}"><span class="ms-icon" aria-hidden="true">school</span><span class="lbl">{t("Learn", "Aprende")}</span></a>
  </nav>
</header>

<nav class="toc" id="toc" aria-label="{t("On this page", "En esta página")}">
  <span class="ka-tabs" role="group" aria-label="{t("Knowledge Area", "Área de conocimiento")}" data-ka="reservoirs"></span><span class="ka-sep" aria-hidden="true"></span>
  <a href="#now">{t("Now", "Ahora")}</a><a href="#ranking">{t("Ranking", "Orden")}</a><a href="#detail">{t("One reservoir", "Un embalse")}</a><a href="#history">{t("Over time", "En el tiempo")}</a><a href="#upstream">{t("Upstream", "Aguas arriba")}</a><a href="#method">{t("Method", "Método")}</a><a href="#sources">{t("Sources", "Fuentes")}</a>
</nav>

<main class="page">
  <div class="note caution review-note" role="note" data-ka-note></div>

  <section class="hero" id="now">
    <div class="eyebrow">{t("Knowledge Area · Water", "Área de conocimiento · Agua")}</div>
    <h1>{t("Puerto Rico's reservoirs: how full they are now", "Los embalses de Puerto Rico: qué tan llenos están ahora")}</h1>
    <p class="lede">{t(f"The water level of {n} reservoirs, read live from the US Geological Survey, compared with the same week in {y0} to {y1}. A reservoir is lower than usual when its level is below what it had in nine of every ten of those years for this week. The {n_aaa} reservoirs in the daily report of the Aqueduct and Sewer Authority (AAA) give Puerto Rico's overall picture.", f"El nivel del agua de {n} embalses, leído en vivo del Servicio Geológico de los Estados Unidos (USGS), comparado con la misma semana de {y0} a {y1}. Un embalse está más bajo de lo usual cuando su nivel es menor que el que tuvo en nueve de cada diez de esos años para esta semana. Los {n_aaa} embalses del informe diario de la Autoridad de Acueductos y Alcantarillados (AAA) dan el panorama general de Puerto Rico.")}</p>
    <div class="rv-now-row">
      <div id="rvTank" aria-live="polite"></div>
      <div><div class="rv-counts" id="rvCounts"></div><p class="pm-p" id="rvOverall" data-t="skip"></p><p class="pm-small" id="rvLive" data-t="skip"></p></div>
    </div>
    <div class="note caution"><b>{t("Read with care.", "Lea con cuidado.")}</b> {t("The water in each tank is where the reservoir's level sits between its lowest and highest level of 2011-2025: a level, not a volume. USGS publishes no volumes, and sediment has filled part of several reservoirs, so the same level holds less water than it once did. 'Usual' compares a reservoir with its own past, not with a safe or unsafe line: the Aqueduct and Sewer Authority (AAA) sets the official alert levels, linked from each reservoir.", "El agua en cada tanque es dónde está el nivel del embalse entre su nivel más bajo y su nivel más alto de 2011-2025: un nivel, no un volumen. USGS no publica volúmenes, y el sedimento ha llenado parte de varios embalses, así que el mismo nivel guarda menos agua que antes. «Usual» compara un embalse con su propio pasado, no con una línea de seguridad: la Autoridad de Acueductos y Alcantarillados (AAA) fija los niveles de alerta oficiales, enlazados desde cada embalse.")}</div>
  </section>

  <section class="block" id="ranking">
    <h2><span class="ms-icon" aria-hidden="true">water</span>{t("1 · All the reservoirs, ranked", "1 · Todos los embalses, en orden")}</h2>
    <p class="pm-p">{t(f"Ranked from the lowest to the highest for this time of year: by how many of the years {y0} to {y1} had a lower level in the same week. The first row is Puerto Rico: the median of the {n_aaa} reservoirs in AAA's report ({other} other reservoirs, for irrigation or flood control, are listed without AAA). Select a column heading to sort, or a reservoir to see it below.", f"En orden del más bajo al más alto para esta época del año: según cuántos de los años de {y0} a {y1} tuvieron un nivel más bajo en la misma semana. La primera fila es Puerto Rico: la mediana de los {n_aaa} embalses del informe de la AAA (otros {other} embalses, de riego o de control de inundaciones, aparecen sin la marca AAA). Seleccione el encabezado de una columna para ordenar, o un embalse para verlo abajo.")}</p>
    <div class="card pm-tablebox rv-tablebox" id="rvRank"></div>
  </section>

  <section class="block" id="detail">
    <h2><span class="ms-icon" aria-hidden="true">water_drop</span>{t("2 · One reservoir", "2 · Un embalse")}</h2>
    <div class="pm-controls"><label>{t("Reservoir", "Embalse")} <select id="rvSel"></select></label></div>
    <div class="card rv-detail"><div id="rvBigTank"></div><div id="rvFacts" data-t="skip"></div></div>
    <h3 class="rv-h3"><span class="ms-icon" aria-hidden="true">show_chart</span>{t("The last 400 days against its usual range", "Los últimos 400 días frente a su rango usual")}</h3>
    <div class="card pm-chart" id="rvRecent" data-t="skip"></div>
    <div class="card pm-chart" id="rvSame" data-t="skip"></div>
    <div class="card pm-chart" id="rvMonthly" data-t="skip"></div>
  </section>

  <section class="block" id="history">
    <h2><span class="ms-icon" aria-hidden="true">history</span>{t("3 · Puerto Rico over time", "3 · Puerto Rico a través del tiempo")}</h2>
    <p class="pm-p">{t(f"Each bar is a month since 1995: the share of AAA's reservoirs whose mean level that month was below their usual level for the month (the 10th percentile of the same month in {y0} to {y1}). Tall bars are the droughts.", f"Cada barra es un mes desde 1995: la parte de los embalses de la AAA cuyo nivel promedio ese mes estuvo bajo su nivel usual del mes (el percentil 10 del mismo mes de {y0} a {y1}). Las barras altas son las sequías.")}</p>
    <div class="card pm-chart" id="rvPR" data-t="skip"></div>
    <p class="pm-small" id="rvPRread" data-t="skip"></p>
  </section>

  <section class="block" id="upstream">
    <h2><span class="ms-icon" aria-hidden="true">park</span>{t("4 · What drains into each reservoir", "4 · Qué drena hacia cada embalse")}</h2>
    <div id="rvUpBox" data-t="skip"><p class="pm-small">{t("Loading what drains into each reservoir…", "Cargando qué drena hacia cada embalse…")}</p></div>
  </section>

  <section class="block" id="method">
    <h2><span class="ms-icon" aria-hidden="true">info</span>{t("Method", "Método")}</h2>
    <div class="note"><b>{t("The level.", "El nivel.")}</b> {t("The water-surface elevation of each reservoir, in metres above local mean sea level (USGS parameter 72376), read live from USGS when the page opens, with the daily values since the file was built. On 2 November 2026 these matched AAA's morning chart to within 0.08 m for 18 of its 19 reservoirs (the check is in docs/facilities.md of the project repository).", "La elevación de la superficie del agua de cada embalse, en metros sobre el nivel medio del mar local (parámetro 72376 de USGS), leída en vivo de USGS al abrir la página, con los valores diarios desde que se preparó el archivo. El 2 de noviembre de 2026 coincidieron con la gráfica matutina de la AAA con una diferencia de 0.08 m o menos en 18 de sus 19 embalses (la comprobación está en docs/facilities.md del repositorio del proyecto).")}</div>
    <div class="note"><b>{t("Usual for this time of year.", "Usual para esta época del año.")}</b> {t(f"For each week of the year, the mean level of that week in each year from {y0} to {y1}. Lower than usual is below the 10th percentile of those yearly values, higher than usual above the 90th, usual in between, at least 8 years. The ranking is the share of those years with a lower level than today. The map's Reservoir levels layer uses the same rule.", f"Para cada semana del año, el nivel promedio de esa semana en cada año de {y0} a {y1}. Más bajo de lo usual es por debajo del percentil 10 de esos valores anuales, más alto de lo usual por encima del 90, y usual entre ambos, con al menos 8 años. El orden es la parte de esos años con un nivel más bajo que el de hoy. La capa Niveles de los embalses del mapa usa la misma regla.")}</div>
    <div class="note"><b>{t("The water in the tanks.", "El agua en los tanques.")}</b> {t(f"Where today's level sits between the reservoir's lowest and highest daily level of {y0} to {y1}: 0% at its lowest, 100% at its highest. The shaded band in a large tank is the usual range for this week. Puerto Rico's tank is the median of the {n_aaa} reservoirs in AAA's report. It is not a share of the reservoir's volume.", f"Dónde está el nivel de hoy entre el nivel diario más bajo y el más alto del embalse de {y0} a {y1}: 0 % en su nivel más bajo, 100 % en el más alto. La franja sombreada en un tanque grande es el rango usual de esta semana. El tanque de Puerto Rico es la mediana de los {n_aaa} embalses del informe de la AAA. No es una parte del volumen del embalse.")}</div>
    <div class="note"><b>{t("The history.", "La historia.")}</b> {t(f"The monthly mean level since each gauge's first daily value (the oldest in {oldest}); a month needs 15 days of readings. Older years on another reference, or while a reservoir was still filling, are left out: Toa Vaca reported a depth, not an elevation, until 2005, and Cerrillos was filling in 1991-1992.", f"El nivel promedio mensual desde el primer valor diario de cada medidor (el más antiguo en {oldest}); un mes necesita 15 días de lecturas. Se excluyen los años antiguos medidos con otra referencia o mientras un embalse se estaba llenando: Toa Vaca reportó una profundidad, no una elevación, hasta 2005, y Cerrillos se estaba llenando en 1991-1992.")}</div>
    <div id="rvUpMethod" data-t="skip"></div>
    <div class="note"><b>{t("What the page does not do.", "Lo que la página no hace.")}</b> {t("It does not say whether there will be water rationing, how many days of water are left, or how much water a reservoir holds. AAA decides rationing with its own alert levels, and its daily report is on its website. A reservoir can be lowered on purpose for repairs, dredging or before a storm.", "No dice si habrá racionamiento de agua, cuántos días de agua quedan ni cuánta agua tiene un embalse. La AAA decide el racionamiento con sus propios niveles de alerta, y su informe diario está en su sitio web. Un embalse puede bajarse a propósito para reparaciones, dragado o antes de una tormenta.")}</div>
  </section>

  <section class="block" id="sources">
    <h2><span class="ms-icon" aria-hidden="true">menu_book</span>{t("Sources and licenses", "Fuentes y licencias")}</h2>
    <div class="note"><b>{t("US Geological Survey.", "Servicio Geológico de los Estados Unidos (USGS).")}</b> {t("Water Data for the Nation, through its Water Data API: lake and reservoir water-surface elevation, the latest readings and daily values. US Government work, public domain. Recent data are provisional and subject to revision.", "Water Data for the Nation, mediante su Water Data API: elevación de la superficie del agua de lagos y embalses, las lecturas más recientes y los valores diarios. Obra del Gobierno de EE. UU., dominio público. Los datos recientes son provisionales y pueden revisarse.")}</div>
    <div class="note"><b>{t("Aqueduct and Sewer Authority (AAA).", "Autoridad de Acueductos y Alcantarillados (AAA).")}</b> {t("The list of the 19 reservoirs in its daily report. Its alert levels are not reproduced here; each reservoir links to AAA's page.", "La lista de los 19 embalses de su informe diario. Sus niveles de alerta no se reproducen aquí; cada embalse enlaza a la página de la AAA.")}</div>
    <div class="note"><b>{t("Data and method.", "Datos y método.")}</b> {t("The data file is data/reservoir_history.json (reservoirs.py), rebuilt once a month; the page adds the latest readings itself. The method is in docs/facilities.md of the project repository.", "El archivo de datos es data/reservoir_history.json (reservoirs.py), que se prepara de nuevo cada mes; la página añade por sí misma las lecturas más recientes. El método está en docs/facilities.md del repositorio del proyecto.")}</div>
    <div id="rvUpSource" data-t="skip"></div>
    <div class="note"><b>{t("How to cite this page.", "Cómo citar esta página.")}</b> {t("Foundation for Puerto Rico, Knowledge Area: Reservoirs, PR Data Observatory, Snapshot 2026-11 (draft). Data: US Geological Survey.", "Foundation for Puerto Rico, Área de conocimiento: Embalses, Observatorio de Datos de PR, Edición 2026-11 (borrador). Datos: Servicio Geológico de los Estados Unidos.")}</div>
  </section>
</main>
<div class="rv-tip" id="rvTip" hidden data-t="skip"></div>
<script src="js/core/knowledge.js?v={ver("js/core/knowledge.js")}"></script>
<script>Core.knowledge.render(); I18N.apply();</script>
<script src="js/common.js?v={ver("js/common.js")}"></script>
<script src="js/reservoirs_page.js?v=2"></script>
<script src="js/chatboot.js?v={ver("js/chatboot.js")}"></script>
</body>
</html>
"""
    for m in re.finditer(r"<b>([^<]*)</b> ([^<]*)</(?:div|p)>", page):
        lead, body = " ".join(html.unescape(m.group(1)).split()), " ".join(html.unescape(m.group(2)).split())
        key = " ".join(f"<b>{m.group(1)}</b> {m.group(2)}".split())
        ES[key] = f"<b>{html.escape(ES[lead], quote=False)}</b> {html.escape(ES[body], quote=False)}"
        ES.pop(lead, None)
        ES.pop(body, None)
    (ROOT / "site" / "reservoirs.html").write_text(page, encoding="utf-8", newline="\n")
    es = {"_about": "The Reservoirs page of the Knowledge Area (reservoirs.html) and site/js/reservoirs_page.js. Written by docs/analysis/reservoirs-2026-11/make_page.py from its (English, Spanish) pairs: edit them there, not here."}
    es.update(ES)
    (ROOT / "i18n_src" / "es" / "reservoirs.json").write_text(json.dumps(es, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    up = {"_about": "Section 4 of the Reservoirs page (site/js/reservoirs_upstream.js, the on-use module 'upstream'). Written by docs/analysis/reservoirs-2026-11/make_page.py from its (English, Spanish) pairs: edit them there, not here."}
    up.update({" ".join(en.split()): " ".join(es.split()) for en, es in UP})
    (ROOT / "i18n_src" / "es" / "reservoirs_upstream.json").write_text(json.dumps(up, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(f"wrote site/reservoirs.html and i18n_src/es/reservoirs.json ({len(ES)} strings), reservoirs_upstream.json ({len(UP)})")


if __name__ == "__main__":
    build()
