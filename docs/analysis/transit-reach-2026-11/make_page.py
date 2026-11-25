"""Writes the Knowledge Area page "Transit, barrio by barrio" (site/transit-reach.html) and its Spanish (i18n_src/es/treach.json).

  python docs/analysis/transit-reach-2026-11/make_page.py   read site/data/transit_reach.json (python transit_reach.py makes it); write the page and the
                                                             Spanish of the page and of site/js/transit_reach_page.js. Then run python i18n.py.

The Puerto Rico version of a county map of public transit in the United States: each of the 901 barrios is shaded by what the published lists put inside
it (a stop with a current timetable, only service without one, or nothing), with the barrios a timetabled route crosses with no stop. It follows the
pattern of the Opportunity Zones page (docs/analysis/opportunity-zones-2026-11/make_page.py): every string is written once, as an (English, Spanish)
pair, and every figure in the static text is read from the data file. It describes the lists and recommends nothing. Prepared with Claude (AI) for FPR,
2026-11-21.
"""
import html
import json
import re
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
ES = {}
MONTHS = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]


def t(en, es):
    key = " ".join(en.split())
    if key in ES and ES[key] != " ".join(es.split()):
        raise SystemExit(f"two Spanish texts for {key!r}")
    ES[key] = " ".join(es.split())
    return html.escape(key, quote=False)


JS = [   # the strings of site/js/transit_reach_page.js
    ("The data could not be loaded ({error}). Check your connection and reload.", "No se pudieron cargar los datos ({error}). Verifique su conexión y vuelva a cargar la página."),
    ("The map could not be loaded ({error}). Check your connection and reload.", "No se pudo cargar el mapa ({error}). Verifique su conexión y vuelva a cargar la página."),
    ("A stop with a current timetable", "Una parada con horario vigente"), ("Only service without a current timetable", "Solo servicio sin horario vigente"), ("Nothing on file", "Nada en las listas"),
    ("Under 5%", "Menos de 5 %"), ("5% to 10%", "5 % a 10 %"), ("10% to 20%", "10 % a 20 %"), ("20% to 30%", "20 % a 30 %"), ("30% or more", "30 % o más"),
    ("Barrios with a stop with a current timetable", "Barrios con una parada con horario vigente"), ("of {n}; {s} of residents", "de {n}; {s} de los residentes"),
    ("Barrios with only service without a timetable", "Barrios solo con servicio sin horario"), ("{s} of residents", "{s} de los residentes"),
    ("Barrios with nothing on file", "Barrios sin nada en las listas"), ("{n} residents", "{n} residentes"),
    ("A route passes, with no stop", "Una ruta pasa, sin parada"),
    ("Households with no vehicle outside a barrio with a current stop", "Hogares sin vehículo fuera de un barrio con parada vigente"),
    ("of {n} in Puerto Rico (ACS 2020-2024)", "de {n} en Puerto Rico (ACS 2020-2024)"),
    ("Map view", "Vista del mapa"), ("Transit", "Transporte"), ("Households with no vehicle", "Hogares sin vehículo"),
    ("{b}: households with no vehicle {v}", "{b}: hogares sin vehículo {v}"), ("unreliable", "poco confiable"), ("{b}: {c}", "{b}: {c}"),
    ("a route passes, with no stop", "una ruta pasa, sin parada"),
    ("Map of the {n} barrios of Puerto Rico: {a} with a stop with a current timetable, {b} with only service without a timetable, {c} with nothing on file",
     "Mapa de los {n} barrios de Puerto Rico: {a} con una parada con horario vigente, {b} solo con servicio sin horario y {c} sin nada en las listas"),
    ("Map of the {n} barrios of Puerto Rico by the share of households with no vehicle", "Mapa de los {n} barrios de Puerto Rico según la proporción de hogares sin vehículo"),
    ("A route with a current timetable passes, with no stop", "Pasa una ruta con horario vigente, sin parada"), ("Tren Urbano and ferries", "Tren Urbano y lanchas"),
    ("Lighter: estimate unreliable", "Más claro: estimado poco confiable"), ("No residents", "Sin residentes"),
    ("Select a barrio for its figures. Timetables as of {d}.", "Seleccione un barrio para ver sus cifras. Horarios al {d}."),
    ("Select a barrio for its figures. Lighter barrios have fewer than {n} residents or a margin of error as large as the estimate.",
     "Seleccione un barrio para ver sus cifras. Los barrios más claros tienen menos de {n} residentes o un margen de error tan grande como el estimado."),
    ("No barrio selected.", "No hay ningún barrio seleccionado."),
    ("Class", "Clase"), ("Municipio", "Municipio"), ("Stops with a current timetable", "Paradas con horario vigente"), ("Stops whose timetable has ended", "Paradas con horario vencido"),
    ("Stops mapped in OpenStreetMap, no timetable", "Paradas cartografiadas en OpenStreetMap, sin horario"), ("Público routes of the 2020 list that cross it", "Rutas de públicos de la lista de 2020 que lo cruzan"),
    ("Yes", "Sí"), ("No", "No"), ("Residents (2020 Census)", "Residentes (Censo 2020)"),
    ("Residents within 400 m of a stop with a current timetable, timetables of {d}", "Residentes a 400 m o menos de una parada con horario vigente, horarios del {d}"),
    ("Households (ACS 2020-2024)", "Hogares (ACS 2020-2024)"), ("Households with no vehicle (ACS 2020-2024)", "Hogares sin vehículo (ACS 2020-2024)"), ("{v} ± {m}", "{v} ± {m}"),
    ("Municipal system", "Sistema municipal"),
    ("{m} reports a bus system to the National Transit Database but publishes no timetable", "{m} informa un sistema de guaguas a la Base de Datos Nacional de Tránsito, pero no publica horario"),
    ("Current timetable", "Horario vigente"), ("Timetable ended", "Horario vencido"), ("Reports to the NTD, no timetable", "Informa a la NTD, sin horario"),
    ("Municipios: select a heading to sort. Residents of the 2020 Census.", "Municipios: seleccione un encabezado para ordenar. Residentes del Censo 2020."),
    ("Barrios", "Barrios"), ("With a current timetable", "Con horario vigente"), ("Only without a timetable", "Solo sin horario"), ("A route passes, no stop", "Una ruta pasa, sin parada"),
    ("Residents", "Residentes"), ("Residents without a current stop in their barrio", "Residentes sin parada vigente en su barrio"), ("Share", "Proporción"), ("Puerto Rico", "Puerto Rico"),
]
for en, es in JS:
    t(en, es)


def num(v, d=0):
    return f"{v:,.{d}f}"


def days(iso):
    d = date.fromisoformat(iso)
    return d.strftime("%B %-d, %Y"), f"{d.day} de {MONTHS[d.month - 1]} de {d.year}"


def build():
    D = json.loads((ROOT / "site" / "data" / "transit_reach.json").read_text(encoding="utf-8"))
    p = D["pr"]
    MF = D["muni_fields"]
    mrows = [dict(zip(MF, r)) for r in D["municipios"]]
    ntd = sorted(m["name"] for m in mrows if m["ntd_no_feed"])
    asof_en, asof_es = days(D["as_of"])
    mill = lambda v: f"{v / 1e6:.1f}"
    ref = (ROOT / "site" / "reservoirs.html").read_text(encoding="utf-8")
    ver = lambda name: re.search(re.escape(name) + r"\?v=(\d+)", ref).group(1)
    I18N_V = 69   # the ?v= of js/i18n.js also versions this page's Spanish bundle: raise it when the page's strings change (docs/i18n.md, rule 12)
    icons = sorted(set(re.search(r"icon_names=([a-z0-9_,]+)", ref).group(1).split(",")) | {"school", "map", "table_view", "info", "menu_book", "directions_bus", "account_tree", "dark_mode", "explore", "grid_view", "light_mode"})

    page = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{t("Knowledge Area · Transit, barrio by barrio", "Área de conocimiento · Transporte colectivo, barrio por barrio")}</title>
<meta name="description" content="{t("Which of Puerto Rico's 901 barrios have a bus, train or ferry stop with a current timetable, which have only público routes or ended timetables, and which have nothing on file, with the residents and the households with no vehicle.", "Cuáles de los 901 barrios de Puerto Rico tienen una parada de guagua, tren o lancha con horario vigente, cuáles solo tienen rutas de públicos u horarios vencidos y cuáles no tienen nada en las listas, con los residentes y los hogares sin vehículo.")}">
<meta name="theme-color" content="#FFFFFF">
<meta name="robots" content="noindex, nofollow">
<link rel="icon" href="img/fpr-mark.png">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Material+Symbols+Rounded:opsz,wght,FILL,GRAD@24,400,1,0&icon_names={",".join(icons)}&display=block">
<link rel="stylesheet" href="css/twin.css?v={ver("css/twin.css")}">
<link rel="stylesheet" href="css/housing.css?v={ver("css/housing.css")}">
<link rel="stylesheet" href="css/public_money.css?v={ver("css/public_money.css")}">
<link rel="stylesheet" href="css/oz.css?v=5">
<link rel="stylesheet" href="css/chat.css?v={ver("css/chat.css")}">
<link rel="stylesheet" href="css/ws.css?v=2">
<script src="js/i18n.js?v={max(int(ver("js/i18n.js")), I18N_V)}" data-page="treach"></script>
</head>
<body class="research">
<a class="skip" href="#now">{t("Skip to the content", "Ir al contenido")}</a>
<header class="topbar">
  <a class="logo" href="index.html" title="{t("PR Data Observatory home", "Inicio del Observatorio de Datos de PR")}"><img src="img/fpr-logo.png" alt="{t("Foundation for Puerto Rico. PR Data Observatory home", "Foundation for Puerto Rico. Inicio del Observatorio de Datos de PR")}"></a>
  <div class="brand" data-gloss="off"><b>{t("Knowledge Area · Transit, barrio by barrio", "Área de conocimiento · Transporte colectivo, barrio por barrio")}</b><span>{t("Where the published lists put a bus, train or ferry stop", "Dónde las listas publicadas ponen una parada de guagua, tren o lancha")}</span></div>
  <div class="spacer"></div>
  <nav class="views" aria-label="{t("Views", "Vistas")}">
    <a class="btn" href="index.html" title="{t("Map: every layer and tool, in 2D or 3D", "Mapa: todas las capas y herramientas, en 2D o 3D")}"><span class="ms-icon" aria-hidden="true">map</span><span class="lbl">{t("Map", "Mapa")}</span></a>
    <a class="btn" href="explore.html" title="{t("Map Gallery: ready-made maps, topics and your saved maps", "Galería de mapas: mapas preparados, temas y sus mapas guardados")}"><span class="ms-icon" aria-hidden="true">explore</span><span class="lbl">{t("Map Gallery", "Galería de mapas")}</span></a>
    <a class="btn" href="data.html" title="{t("Data: every dataset, map layer and set of places", "Datos: todos los conjuntos de datos, capas del mapa y grupos de lugares")}"><span class="ms-icon" aria-hidden="true">grid_view</span><span class="lbl">{t("Data", "Datos")}</span></a>
    <a class="btn" href="workflows.html" title="{t("Workflows: steps that turn data into a result on the map", "Flujos de trabajo: pasos que convierten datos en un resultado en el mapa")}"><span class="ms-icon" aria-hidden="true">account_tree</span><span class="lbl">{t("Workflows", "Flujos")}</span></a>
    <a class="btn" href="knowledge.html" aria-current="page" title="{t("Knowledge: FPR studies, analyses and tools", "Conocimiento: estudios, análisis y herramientas de FPR")}"><span class="ms-icon" aria-hidden="true">lightbulb</span><span class="lbl">{t("Knowledge", "Conocimiento")}</span></a>
    <a class="btn" href="dictionary.html" title="{t("Data dictionary: meanings, sources, licenses, how to cite", "Diccionario de datos: significados, fuentes, licencias y cómo citar")}"><span class="ms-icon" aria-hidden="true">menu_book</span><span class="lbl">{t("Data dictionary", "Diccionario de datos")}</span></a>
    <a class="btn" href="learn.html" title="{t("Learn: short lessons about maps and spatial analysis", "Aprende: lecciones cortas sobre mapas y análisis espacial")}"><span class="ms-icon" aria-hidden="true">school</span><span class="lbl">{t("Learn", "Aprende")}</span></a>
    <a class="btn" href="about.html" title="{t("About: this initiative, how to use the Observatory, terms", "Acerca de: esta iniciativa, cómo usar el Observatorio y los términos")}"><span class="ms-icon" aria-hidden="true">info</span><span class="lbl">{t("About", "Acerca de")}</span></a>
  </nav>
</header>

<nav class="toc" id="toc" aria-label="{t("On this page", "En esta página")}">
  <span class="ka-tabs" role="group" aria-label="{t("Knowledge Area", "Área de conocimiento")}" data-ka="treach"></span><span class="ka-sep" aria-hidden="true"></span>
  <a href="#now">{t("Now", "Ahora")}</a><a href="#barrios">{t("Map", "Mapa")}</a><a href="#municipios">{t("Municipios", "Municipios")}</a><a href="#method">{t("How it is counted", "Cómo se cuenta")}</a><a href="#sources">{t("Sources", "Fuentes")}</a>
</nav>

<main class="page">
  <div class="note caution review-note" role="note" data-ka-note></div>

  <section class="hero" id="now">
    <div class="eyebrow">{t("Knowledge Area · Infrastructure", "Área de conocimiento · Infraestructura")}</div>
    <h1>{t("Transit in Puerto Rico, barrio by barrio", "El transporte colectivo en Puerto Rico, barrio por barrio")}</h1>
    <p class="lede">{t(f"{p['b3']} of Puerto Rico's {p['barrios']} barrios have a bus, train or ferry stop with a current timetable. Another {p['b2']} have only service without one: a público route of the 2020 list, a stop whose timetable has ended or a stop mapped by volunteers. {mill(p['p_out'])} million people, {p['p_out_share']}% of residents, live in a barrio with no stop with a current timetable; {num(p['p1'])} of them live where the lists show nothing at all.", f"{p['b3']} de los {p['barrios']} barrios de Puerto Rico tienen una parada de guagua, tren o lancha con horario vigente. Otros {p['b2']} solo tienen servicio sin horario: una ruta de públicos de la lista de 2020, una parada cuyo horario venció o una parada cartografiada por voluntarios. {mill(p['p_out'])} millones de personas, el {p['p_out_share']} % de los residentes, viven en un barrio sin parada con horario vigente; {num(p['p1'])} de ellas viven donde las listas no muestran nada.")}</p>
    <div id="trNow" aria-live="polite"></div>
    <div class="note caution"><b>{t("What the map is not.", "Lo que el mapa no es.")}</b> {t("It shows what the published lists of routes and timetables hold, not how often a bus comes or whether a público runs today. A barrio without a timetabled stop can still have service, and a barrio with one can have a stop far from most homes.", "Muestra lo que tienen las listas publicadas de rutas y horarios, no cada cuánto pasa una guagua ni si un público corre hoy. Un barrio sin parada con horario puede tener servicio, y un barrio con una puede tener la parada lejos de la mayoría de las casas.")}</div>
  </section>

  <section class="block" id="barrios">
    <h2><span class="ms-icon" aria-hidden="true">map</span>{t("1 · The barrios", "1 · Los barrios")}</h2>
    <p class="pm-p">{t(f"Each barrio is shaded by the best service the lists put inside it. A yellow edge marks the {p['passes']} barrios that a route with a current timetable crosses with no stop, home to {num(p['pop_passes'])} people. The red lines are the Tren Urbano and the ferries. The second view shades each barrio by the share of households with no vehicle, the people who most depend on transit.", f"Cada barrio está coloreado según el mejor servicio que las listas ponen dentro de él. Un borde amarillo marca los {p['passes']} barrios que cruza una ruta con horario vigente sin parada, donde viven {num(p['pop_passes'])} personas. Las líneas rojas son el Tren Urbano y las lanchas. La segunda vista colorea cada barrio según la proporción de hogares sin vehículo, las personas que más dependen del transporte colectivo.")}</p>
    <div class="tr-toggle" id="trToggle" data-t="skip"></div>
    <div class="card pm-map oz-map" id="trMap" data-t="skip"></div>
    <p class="pm-small" id="trMapNote" data-t="skip"></p>
    <div class="oz-tract" id="trBarrio" aria-live="polite" data-t="skip"></div>
  </section>

  <section class="block" id="municipios">
    <h2><span class="ms-icon" aria-hidden="true">table_view</span>{t("2 · By municipio", "2 · Por municipio")}</h2>
    <p class="pm-p">{t(f"In {p['munis_no_timetable']} of the 78 municipios no barrio has a stop with a current timetable. {p['munis_ntd_no_feed']} municipios report a bus system to the federal National Transit Database but publish no timetable, so their service does not appear on the map: {', '.join(ntd)}. The table is sorted by the residents without a current stop in their barrio; select a heading to sort by another column.", f"En {p['munis_no_timetable']} de los 78 municipios ningún barrio tiene una parada con horario vigente. {p['munis_ntd_no_feed']} municipios informan un sistema de guaguas a la Base de Datos Nacional de Tránsito federal, pero no publican horario, así que su servicio no aparece en el mapa: {', '.join(ntd)}. La tabla está ordenada por los residentes sin parada vigente en su barrio; seleccione un encabezado para ordenar por otra columna.")}</p>
    <div class="card pm-tablebox oz-tablebox" id="trMunis" data-t="skip"></div>
  </section>

  <section class="block" id="method">
    <h2><span class="ms-icon" aria-hidden="true">info</span>{t("How it is counted", "Cómo se cuenta")}</h2>
    <div class="note"><b>{t("The classes.", "Las clases.")}</b> {t(f"A barrio has a stop with a current timetable when a stop of ATI (AMA buses, Tren Urbano, ferries) or of a municipal system lies inside it and that system's GTFS timetable has not ended on {asof_en}. Otherwise it has service without a timetable when the lists put inside it a stop whose timetable has ended, a stop mapped in OpenStreetMap, or a público route of the 2020 list. A stop counts only in the barrio it lies in; a stop just across the line does not count.", f"Un barrio tiene una parada con horario vigente cuando dentro de él hay una parada de ATI (guaguas de la AMA, Tren Urbano, lanchas) o de un sistema municipal y el horario GTFS de ese sistema no ha vencido al {asof_es}. Si no, tiene servicio sin horario cuando las listas ponen dentro de él una parada cuyo horario venció, una parada cartografiada en OpenStreetMap o una ruta de públicos de la lista de 2020. Una parada cuenta solo en el barrio donde está; una parada justo al otro lado del límite no cuenta.")}</div>
    <div class="note"><b>{t("Limits of the lists.", "Límites de las listas.")}</b> {t(f"The público list is from 2020 and has no timetable; a route on it may no longer run. Several municipal timetables have ended or end soon, and a barrio changes class on the day its timetable ends: the map, the figure cards and the table follow the timetables every night, while the text of the page gives the figures of {asof_en}. {p['munis_ntd_no_feed']} municipal systems publish nothing. Dial-a-ride service is not shown: it is reported by agency, not by place. Routes drawn from stop to stop where a system publishes no route shape make the yellow edge approximate.", f"La lista de públicos es de 2020 y no tiene horario; una ruta puede ya no correr. Varios horarios municipales vencieron o vencen pronto, y un barrio cambia de clase el día que vence su horario: el mapa, las tarjetas de cifras y la tabla siguen los horarios cada noche, mientras el texto de la página da las cifras del {asof_es}. {p['munis_ntd_no_feed']} sistemas municipales no publican nada. No se muestra el servicio a pedido: se informa por agencia, no por lugar. Las rutas trazadas de parada a parada donde un sistema no publica el trazado hacen aproximado el borde amarillo.")}</div>
    <div class="note"><b>{t("Residents and households.", "Residentes y hogares.")}</b> {t(f"Residents are those of the 2020 Census, counted by census block. The residents within 400 m of a stop with a current timetable, {num(p['pop_400m'])} ({p['pop_400m_share']}%), come from the exposure series of the Observatory, computed with the timetables of {days(p['pop_400m_as_of'])[0]}. Households with no vehicle are estimates of the American Community Survey 2020-2024 (table B25044) with margins of error; barrios with fewer than {D['rules']['min_pop']} residents or a margin as large as the estimate are drawn lighter.", f"Los residentes son los del Censo 2020, contados por bloque censal. Los residentes a 400 m o menos de una parada con horario vigente, {num(p['pop_400m'])} ({p['pop_400m_share']} %), vienen de la serie de exposición del Observatorio, calculada con los horarios del {days(p['pop_400m_as_of'])[1]}. Los hogares sin vehículo son estimados de la Encuesta sobre la Comunidad 2020-2024 (tabla B25044) con márgenes de error; los barrios con menos de {D['rules']['min_pop']} residentes o un margen tan grande como el estimado se dibujan más claros.")}</div>
    <div class="note"><b>{t("More detail.", "Más detalle.")}</b> {t("The code is transit_reach.py in the project repository, and the data file has an entry in the data dictionary (search for 'transit by barrio'). The idea comes from a county map of public transit in the United States made for the 30 Day Map Challenge.", "El código es transit_reach.py en el repositorio del proyecto, y el archivo de datos tiene una entrada en el diccionario de datos (busque «transporte por barrio»). La idea viene de un mapa por condado del transporte colectivo en Estados Unidos hecho para el 30 Day Map Challenge.")}</div>
  </section>

  <section class="block" id="sources">
    <h2><span class="ms-icon" aria-hidden="true">menu_book</span>{t("Sources and licenses", "Fuentes y licencias")}</h2>
    <div class="note"><b>{t("Timetables.", "Horarios.")}</b> {t("Autoridad de Transporte Integrado (ATI), GTFS feed; the municipal systems' GTFS feeds published through the National RTAP portal.", "Autoridad de Transporte Integrado (ATI), feed GTFS; los feeds GTFS de los sistemas municipales publicados en el portal de National RTAP.")}</div>
    <div class="note"><b>{t("Públicos.", "Públicos.")}</b> {t("The list of público routes of the Autoridad de Carreteras y Transportación, published by the Instituto de Estadísticas de Puerto Rico (2020-03-19), CC BY.", "La lista de rutas de públicos de la Autoridad de Carreteras y Transportación, publicada por el Instituto de Estadísticas de Puerto Rico (2020-03-19), CC BY.")}</div>
    <div class="note"><b>{t("Other stops.", "Otras paradas.")}</b> {t("OpenStreetMap contributors, ODbL; the Federal Transit Administration's National Transit Database for the municipal systems that report service.", "Colaboradores de OpenStreetMap, ODbL; la Base de Datos Nacional de Tránsito de la Administración Federal de Tránsito para los sistemas municipales que informan servicio.")}</div>
    <div class="note"><b>{t("US Census Bureau.", "Negociado del Censo de EE. UU.")}</b> {t("2020 Census residents by block and the barrio outlines; American Community Survey 5-year estimates 2020-2024, table B25044. US Government works.", "Residentes del Censo 2020 por bloque y los contornos de los barrios; estimados de 5 años de la Encuesta sobre la Comunidad 2020-2024, tabla B25044. Obras del Gobierno de EE. UU.")}</div>
    <div class="note"><b>{t("Data files.", "Archivos de datos.")}</b> {t("data/transit_reach.json (transit_reach.py) and data/barrios.geojson for the map.", "data/transit_reach.json (transit_reach.py) y data/barrios.geojson para el mapa.")}</div>
    <div class="note"><b>{t("How to cite this page.", "Cómo citar esta página.")}</b> {t(f"Foundation for Puerto Rico, Knowledge Area: Transit, barrio by barrio, PR Data Observatory, timetables as of {asof_en}. Data: ATI; municipal transit systems; Instituto de Estadísticas de Puerto Rico; OpenStreetMap; US Census Bureau.", f"Foundation for Puerto Rico, Área de conocimiento: Transporte colectivo, barrio por barrio, Observatorio de Datos de PR, horarios al {asof_es}. Datos: ATI; sistemas municipales de transporte; Instituto de Estadísticas de Puerto Rico; OpenStreetMap; Negociado del Censo de EE. UU.")}</div>
  </section>
</main>
<script src="js/core/knowledge.js?v={ver("js/core/knowledge.js")}"></script>
<script>Core.knowledge.render(); I18N.apply();</script>
<script src="js/common.js?v={ver("js/common.js")}"></script>
<script src="js/transit_reach_page.js?v=2"></script>
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
    (ROOT / "site" / "transit-reach.html").write_text(page, encoding="utf-8", newline="\n")
    es = {"_about": "The page Transit, barrio by barrio of the Knowledge Area (transit-reach.html) and site/js/transit_reach_page.js. Written by docs/analysis/transit-reach-2026-11/make_page.py from its (English, Spanish) pairs: edit them there, not here."}
    es.update(ES)
    (ROOT / "i18n_src" / "es" / "treach.json").write_text(json.dumps(es, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(f"wrote site/transit-reach.html and i18n_src/es/treach.json ({len(ES)} strings)")


if __name__ == "__main__":
    build()
