"""Writes the Knowledge Area page "Connections between municipios" (site/transit-links.html) and its Spanish (i18n_src/es/tlinks.json).

  python docs/analysis/transit-links-2026-11/make_page.py   read site/data/transit_links.json (python transit_links.py makes it); write the page and the
                                                            Spanish of the page and of site/js/transit_links_page.js. Then run python i18n.py.

The page follows the site's language rule (docs/i18n.md) and the pattern of the Opportunity Zones page (docs/analysis/opportunity-zones-2026-11/make_page.py):
every string is written once, as an (English, Spanish) pair, and every figure in the static text is read from the data file. HANDOFF decision 105: how many
workers travel between each pair of municipios, which pairs a timetabled route or a público route of the 2020 list joins, and a simulated connection for the
pairs with many workers and no timetabled route. The page describes what the open data show; it proposes no route and no service change (the transit analysis
plan's decision 4 reserves that for FPR's leadership). Prepared with Claude (AI) for FPR, 2026-11-13.
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
    if key in ES and ES[key] != " ".join(es.split()):
        raise SystemExit(f"two Spanish texts for {key!r}")
    ES[key] = " ".join(es.split())
    return html.escape(key, quote=False)


JS = [   # the strings of site/js/transit_links_page.js
    ("The data could not be loaded ({error}). Check your connection and reload.", "No se pudieron cargar los datos ({error}). Verifique su conexión y vuelva a cargar la página."),
    ("The map could not be loaded ({error}). Check your connection and reload.", "No se pudo cargar el mapa ({error}). Verifique su conexión y vuelva a cargar la página."),
    ("Timetabled route", "Ruta con horario"), ("Timetable expired", "Horario vencido"), ("Público route on the 2020 list", "Ruta de públicos en la lista de 2020"),
    ("No route listed", "Sin ruta en las listas"),
    ("Timetable published", "Publica horario"), ("No timetable published", "No publica horario"), ("None listed", "No aparece ninguno"),
    ("{n} pairs of municipios; {s} of those workers", "{n} pares de municipios; {s} de esas personas"),
    ("Workers who travel to another municipio", "Personas que viajan a otro municipio para trabajar"),
    ("{s} of {n} workers, {period}", "{s} de {n} personas que trabajan, {period}"),
    ("Between municipios with a timetabled route", "Entre municipios con una ruta con horario"),
    ("With only a público route on the 2020 list", "Solo con una ruta de públicos en la lista de 2020"),
    ("Between municipios whose only timetable expired", "Entre municipios cuyo único horario está vencido"),
    ("With no route listed", "Sin ninguna ruta en las listas"),
    ("Simulated connections", "Conexiones simuladas"),
    ("pairs with {w} workers or more and no timetabled route; {n} workers", "pares con {w} personas o más y sin ruta con horario; {n} personas"),
    ("{pair}: {n} workers; timetabled route, {t} weekday trips", "{pair}: {n} personas; ruta con horario, {t} viajes en día de semana"),
    ("{pair}: {n} workers; simulated connection, {s}", "{pair}: {n} personas; conexión simulada, {s}"),
    ("Map of Puerto Rico: {t} pairs of municipios joined by a timetabled route and {n} simulated connections for pairs without one",
     "Mapa de Puerto Rico: {t} pares de municipios unidos por una ruta con horario y {n} conexiones simuladas para pares que no la tienen"),
    ("Timetabled route today (along its route)", "Ruta con horario hoy (por su recorrido)"),
    ("Simulated connection", "Conexión simulada"), ("Thicker lines: more workers", "Líneas más gruesas: más personas"),
    ("Pairs with a journey by timetable", "Pares con un viaje por horario"),
    ("of {n} pairs, town center to town center leaving from 6 to 9 a.m.; a median of {r} times as long as by car", "de {n} pares, de centro de pueblo a centro de pueblo saliendo de 6 a 9 a. m.; una mediana de {r} veces lo que toma en carro"),
    ("Town centers with no stop of a weekday timetable within 1 km", "Centros de pueblo sin una parada con horario de día de semana a 1 km o menos"),
    ("{n} of {m}", "{n} de {m}"),
    ("there a trip starts with a longer walk, a car or a público", "allí el viaje empieza con una caminata más larga, un carro o un público"),
    ("By timetable, minutes (fastest, 6 to 9 a.m.)", "Por horario, minutos (el más rápido, de 6 a 9 a. m.)"),
    ("Households with no vehicle, each end", "Hogares sin vehículo, en cada extremo"),
    ("Residents within 1 km of its roads (beyond 400 m of a stop)", "Residentes a 1 km o menos de sus carreteras (a más de 400 m de una parada)"),
    ("Bridges in poor condition on its roads", "Puentes en mala condición en sus carreteras"),
    ("no stop within 1 km of a center", "sin parada a 1 km de un centro"),
    ("none within 3 hours", "ninguno en 3 horas"),
    ("1 transfer", "1 trasbordo"), ("{n} transfers", "{n} trasbordos"), ("direct", "directo"),
    ("{r} times the car", "{r} veces el carro"),
    ("Nearest weekday timetable stop to the town center, km", "Parada con horario de día de semana más cercana al centro de pueblo, km"),
    ("Households with no vehicle", "Hogares sin vehículo"), ("Below the poverty level", "Bajo el nivel de pobreza"),
    ("Select a municipio to see only its connections. Simulated connections follow the fastest roads between two town centers (OpenStreetMap); they are not proposed routes.",
     "Seleccione un municipio para ver solo sus conexiones. Las conexiones simuladas siguen las carreteras más rápidas entre dos centros de pueblo (OpenStreetMap); no son rutas propuestas."),
    ("Municipio", "Municipio"), ("All of Puerto Rico", "Todo Puerto Rico"), ("Listed today", "En las listas hoy"), ("Any", "Cualquiera"),
    ("{t} weekday trips ({o})", "{t} viajes en día de semana ({o})"), ("timetabled routes join them with a transfer", "hay rutas con horario que los unen con un trasbordo"),
    ("{n} pairs of {m} with workers traveling between them: {w} workers; {a} between pairs with a timetabled route, {b} with only a público route on the 2020 list, {c} with no route listed.",
     "{n} pares de {m} con personas que viajan entre ellos para trabajar: {w} personas; {a} entre pares con una ruta con horario, {b} solo con una ruta de públicos en la lista de 2020 y {c} sin ninguna ruta en las listas."),
    ("{n} pairs of municipios, {w} workers. Select a heading to sort. Workers are survey estimates ({period}); ± is the margin of error.",
     "{n} pares de municipios, {w} personas. Seleccione un encabezado para ordenar. Las cifras son estimados de una encuesta ({period}); ± es el margen de error."),
    ("The margin of error is as large as the estimate", "El margen de error es tan grande como el estimado"), ("low reliability", "poco confiable"),
    ("Pair of municipios", "Par de municipios"), ("Workers who travel between them", "Personas que viajan entre ellos para trabajar"),
    ("Público routes (2020 list)", "Rutas de públicos (lista de 2020)"), ("Road distance, km", "Distancia por carretera, km"),
    ("Minutes by car, no traffic", "Minutos en carro, sin tráfico"), ("Traffic on its roads, vehicles a day", "Tránsito en sus carreteras, vehículos al día"), ("Road deaths on its roads, per 10 km, five years", "Muertes en sus carreteras, por cada 10 km, cinco años"), ("Show all {n} pairs", "Mostrar los {n} pares"),
    ("Municipios: select a heading to sort. Workers 16 and over, {period}.", "Municipios: seleccione un encabezado para ordenar. Personas de 16 años o más que trabajan, {period}."),
    ("Workers who live here", "Personas que trabajan y viven aquí"), ("Work in another municipio", "Trabajan en otro municipio"),
    ("Share who work in another municipio", "Parte que trabaja en otro municipio"), ("Come in from another municipio", "Llegan de otro municipio a trabajar"),
    ("Where most go", "A dónde va la mayoría"), ("Share of that travel with a timetabled route", "Parte de esos viajes con una ruta con horario"),
    ("Its own transit system", "Su propio sistema de transporte"),
]
for en, es in JS:
    t(en, es)


def num(v, d=0):
    return f"{v:,.{d}f}"


def build():
    D = json.loads((ROOT / "site" / "data" / "transit_links.json").read_text(encoding="utf-8"))
    p, pub = D["pr"], D["publicos"]
    b = p["by_status"]
    name = {m[0]: m[1] for m in D["municipios"]}
    P = [dict(zip(D["pair_fields"], r)) for r in D["pairs"]]
    sims = sorted((x for x in P if x["sim"]), key=lambda x: x["sim"])
    top_none = [x for x in sims if x["status"] == "none"][:3]
    top_pub = [x for x in sims if x["status"] == "publico"][:3]
    lst = lambda xs: "; ".join(f"{name[x['a']]} – {name[x['b']]} ({num(x['workers'])})" for x in xs)
    munis = [dict(zip(D["muni_fields"], r)) for r in D["municipios"]]
    own = {k: sum(1 for m in munis if m["own_system"] == k) for k in ("current", "expiring", "expired", "none")}
    published = own["current"] + own["expiring"]
    no_system = sum(1 for m in munis if m["own_system"] is None)
    period, as_of, minw = D["flows"]["period"], D["timetables"]["as_of"], D["rules"]["sim_min_workers"]
    low = sum(1 for x in P if x["low"])
    tt = D.get("transit_time") or {}
    rs = sorted(x["tt_best"] / x["min"] for x in P if x.get("tt_best") is not None and x["min"])
    ratio = f"{rs[len(rs) // 2]:.1f}" if rs else "—"
    cs = next((x for x in P if {x["a"], x["b"]} == {"72025", "72127"}), {})   # Caguas and San Juan
    METRO = {"72021", "72025", "72029", "72031", "72033", "72061", "72087", "72127", "72135", "72137", "72139"}   # San Juan and the municipios around it, Caguas included
    metro = all(x["a"] in METRO and x["b"] in METRO for x in P if x.get("tt_best") is not None)
    where_en, where_es = ("all of them in and around San Juan", "todos en San Juan y sus alrededores") if metro else ("nearly all in the San Juan area", "casi todos en el área de San Juan")
    ends_only = len(D["timetables"].get("ends_only") or [])
    need_period = (D.get("need") or {}).get("period", "—")
    from statistics import median as _median
    # the findings (section 0): facts from steps 1 to 5 of the upgrade, side by side, never a ranking
    sims_all = [x for x in P if x["sim"]]
    poor_br = sum(1 for x in sims_all if x.get("bridges_poor"))
    med_traffic = round(_median([x["aadt_med"] for x in sims_all if x.get("aadt_med")])) if any(x.get("aadt_med") for x in sims_all) else 0
    eco = json.loads((ROOT / "site" / "data" / "economy_series.json").read_text(encoding="utf-8"))
    nvv = next(v for v in eco["vars"] if v["key"] == "no_vehicle_hh_pct")
    nv_pr = nvv["years"][max(nvv["years"], key=int)][-1]
    tr = D.get("traffic") or {}
    sf = D.get("safety") or {"years": ["—", "—"]}
    dk = sorted([(10 * x["deaths_5y"] / x["km"], x) for x in P if x["sim"] and x.get("deaths_5y") is not None and x["km"]], key=lambda t: -t[0])
    med_death = sorted(v for v, _ in dk)[len(dk) // 2] if dk else 0
    top_death = "; ".join(f"{name[x['a']]} – {name[x['b']]} ({v:.1f})" for v, x in dk[:3])
    top_death_es = top_death
    from statistics import median as _median
    med_all = round(_median([x["aadt_med"] for x in P if x["sim"] and x.get("aadt_med")])) if tr else 0
    ex = b["expired"]
    exp_en = f" The other {ex['pct']}% travel between {ex['pairs']} pairs whose only timetabled route has a timetable that expired." if ex["pairs"] else ""
    exp_es = f" El otro {ex['pct']} % viaja entre {ex['pairs']} pares cuya única ruta con horario tiene el horario vencido." if ex["pairs"] else ""
    ends = D["timetables"]["ends_only"]
    ends_en = ", ".join(ends[:-1]) + " and " + ends[-1]
    ends_es = ", ".join(ends[:-1]) + (" e " if ends[-1][:1].lower() in "ií" else " y ") + ends[-1]
    src = (ROOT / "site" / "js" / "transit_links_page.js").read_text(encoding="utf-8")
    missing = sorted({m for m in re.findall(r"""T\('((?:[^'\\]|\\.)*)'""", src)} - {k.replace("'", "\\'") for k in ES} - {k for k in ES})
    missing = [m for m in missing if m.replace("\\'", "'") not in ES]
    if missing:
        raise SystemExit(f"transit_links_page.js has strings with no Spanish here: {missing}")
    ref = (ROOT / "site" / "opportunity-zones.html").read_text(encoding="utf-8")
    ver = lambda n: re.search(re.escape(n) + r"\?v=(\d+)", ref).group(1)
    I18N_V = 68   # the ?v= of js/i18n.js also versions this page's Spanish bundle: raise it when the page's strings change (docs/i18n.md, rule 12)
    icons = sorted(set(re.search(r"icon_names=([a-z0-9_,]+)", ref).group(1).split(",")) | {"school", "commute", "map", "table_view", "info", "menu_book", "location_city", "route", "directions_bus", "account_tree", "dark_mode", "explore", "grid_view", "light_mode"})

    page = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{t("Knowledge Area · Connections between municipios", "Área de conocimiento · Conexiones entre municipios")}</title>
<meta name="description" content="{t("How many workers travel between each pair of municipios of Puerto Rico, which pairs a timetabled route or a listed público route joins, and simulated connections for the pairs with many workers and no timetabled route.", "Cuántas personas viajan entre cada par de municipios de Puerto Rico para trabajar, qué pares tienen una ruta con horario o una ruta de públicos en las listas, y conexiones simuladas para los pares con muchas personas y sin ruta con horario.")}">
<meta name="robots" content="noindex, nofollow">
<meta name="theme-color" content="#FFFFFF">
<link rel="icon" href="img/fpr-mark.png">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Material+Symbols+Rounded:opsz,wght,FILL,GRAD@24,400,1,0&icon_names={",".join(icons)}&display=block">
<link rel="stylesheet" href="css/twin.css?v={ver("css/twin.css")}">
<link rel="stylesheet" href="css/housing.css?v={ver("css/housing.css")}">
<link rel="stylesheet" href="css/public_money.css?v={ver("css/public_money.css")}">
<link rel="stylesheet" href="css/oz.css?v={ver("css/oz.css")}">
<link rel="stylesheet" href="css/tlinks.css?v=4">
<link rel="stylesheet" href="css/chat.css?v={ver("css/chat.css")}">
<link rel="stylesheet" href="css/ws.css?v=2">
<script src="js/i18n.js?v={max(int(ver("js/i18n.js")), I18N_V)}" data-page="tlinks"></script>
</head>
<body class="research">
<a class="skip" href="#now">{t("Skip to the content", "Ir al contenido")}</a>
<header class="topbar">
  <a class="logo" href="index.html" title="{t("PR Data Observatory home", "Inicio del Observatorio de Datos de PR")}"><img src="img/fpr-logo.png" alt="{t("Foundation for Puerto Rico. PR Data Observatory home", "Foundation for Puerto Rico. Inicio del Observatorio de Datos de PR")}"></a>
  <div class="brand" data-gloss="off"><b>{t("Knowledge Area · Connections between municipios", "Área de conocimiento · Conexiones entre municipios")}</b><span>{t("Where people travel to work and where transit joins the towns", "A dónde viaja la gente a trabajar y dónde el transporte colectivo une los pueblos")}</span></div>
  <div class="spacer"></div>
  <nav class="views" aria-label="{t("Views", "Vistas")}">
    <a class="btn" href="index.html" title="{t("Map: every layer and tool, in 2D or 3D", "Mapa: todas las capas y herramientas, en 2D o 3D")}"><span class="ms-icon" aria-hidden="true">map</span><span class="lbl">{t("Map", "Mapa")}</span></a>
    <a class="btn" href="explore.html" title="{t("Map Gallery: ready-made maps, topics and your saved maps", "Galería de mapas: mapas preparados, temas y sus mapas guardados")}"><span class="ms-icon" aria-hidden="true">explore</span><span class="lbl">{t("Map Gallery", "Galería de mapas")}</span></a>
    <a class="btn" href="data.html" title="{t("Data: every dataset, map layer and set of places", "Datos: todos los conjuntos de datos, capas del mapa y grupos de lugares")}"><span class="ms-icon" aria-hidden="true">grid_view</span><span class="lbl">{t("Data", "Datos")}</span></a>
    <a class="btn" href="workflows.html" title="{t("Workflows: steps that turn data into a result on the map", "Flujos de trabajo: pasos que convierten datos en un resultado en el mapa")}"><span class="ms-icon" aria-hidden="true">account_tree</span><span class="lbl">{t("Workflows", "Flujos")}</span></a>
    <a class="btn" href="knowledge.html" aria-current="page" title="{t("Knowledge: FPR studies, analyses and tools", "Conocimiento: estudios, análisis y herramientas de FPR")}"><span class="ms-icon" aria-hidden="true">lightbulb</span><span class="lbl">{t("Knowledge", "Conocimiento")}</span></a>
    <a class="btn" href="dictionary.html" title="{t("Data Dictionary: meanings, sources, licenses, how to cite", "Diccionario de datos: significados, fuentes, licencias y cómo citar")}"><span class="ms-icon" aria-hidden="true">menu_book</span><span class="lbl">{t("Data Dictionary", "Diccionario de datos")}</span></a>
    <a class="btn" href="learn.html" title="{t("Learn: short lessons about maps and spatial analysis", "Aprende: lecciones cortas sobre mapas y análisis espacial")}"><span class="ms-icon" aria-hidden="true">school</span><span class="lbl">{t("Learn", "Aprende")}</span></a>
    <a class="btn" href="about.html" title="{t("About: this initiative, how to use the Observatory, terms", "Acerca de: esta iniciativa, cómo usar el Observatorio y los términos")}"><span class="ms-icon" aria-hidden="true">info</span><span class="lbl">{t("About", "Acerca de")}</span></a>
  </nav>
</header>

<nav class="toc" id="toc" aria-label="{t("On this page", "En esta página")}">
  <span class="ka-tabs" role="group" aria-label="{t("Knowledge Area", "Área de conocimiento")}" data-ka="tlinks"></span><span class="ka-sep" aria-hidden="true"></span>
  <a href="#now">{t("Now", "Ahora")}</a><a href="#findings">{t("Findings", "Hallazgos")}</a><a href="#links">{t("Map", "Mapa")}</a><a href="#pairs">{t("Pairs", "Pares")}</a><a href="#municipios">{t("Municipios", "Municipios")}</a><a href="#reading">{t("How to read it", "Cómo leerlo")}</a><a href="#method">{t("Method", "Método")}</a><a href="#sources">{t("Sources", "Fuentes")}</a>
</nav>

<main class="page">
  <div class="note caution review-note" role="note" data-ka-note></div>

  <section class="hero" id="now">
    <div class="eyebrow">{t("Knowledge Area · Infrastructure and mobility", "Área de conocimiento · Infraestructura y movilidad")}</div>
    <h1>{t("Connections between municipios", "Conexiones entre municipios")}</h1>
    <p class="lede">{t(f"More than half of Puerto Rico's workers, {num(p['other_municipio'])} of {num(p['workers'])} ({p['other_municipio_pct']}%), work in a municipio other than the one where they live (American Community Survey {period}). Workers travel between {num(p['pairs'])} pairs of municipios, and a route with a published timetable joins {b['timetable']['pairs']} of those pairs. Those {b['timetable']['pairs']} pairs carry {b['timetable']['pct']}% of the workers who cross a municipal line. Another {b['publico']['pct']}% travel between pairs that had a público route on the 2020 list, and {b['none']['pct']}% between pairs with no route listed.{exp_en}",
                         f"Más de la mitad de las personas que trabajan en Puerto Rico, {num(p['other_municipio'])} de {num(p['workers'])} ({p['other_municipio_pct']} %), trabaja en un municipio distinto de donde vive (Encuesta sobre la Comunidad {period}). Hay personas que viajan para trabajar entre {num(p['pairs'])} pares de municipios, y una ruta con horario publicado une {b['timetable']['pairs']} de esos pares. Esos {b['timetable']['pairs']} pares reúnen el {b['timetable']['pct']} % de las personas que cruzan de un municipio a otro. Otro {b['publico']['pct']} % viaja entre pares que tenían una ruta de públicos en la lista de 2020, y el {b['none']['pct']} % entre pares sin ninguna ruta en las listas.{exp_es}")}</p>
    <div id="tlNow" aria-live="polite"></div>
    <div class="note caution"><b>{t("What this page is, and what it is not.", "Qué es esta página y qué no es.")}</b> {t("It sets two open datasets side by side: where people travel to work, and where a transit route is listed. Where many people travel and no timetabled route is listed, it draws a simulated connection along the roads. A simulated connection marks a place to look at. It is not a proposed route, a service plan or a demand forecast, and it is not a position of Foundation for Puerto Rico on what service should exist. Públicos carry many of these trips without a timetable, so a pair with no timetabled route is not a pair with no service.",
                                                                                                                              "Pone dos conjuntos de datos abiertos uno al lado del otro: a dónde viaja la gente a trabajar y dónde aparece una ruta de transporte colectivo. Donde viaja mucha gente y no aparece una ruta con horario, dibuja una conexión simulada por las carreteras. Una conexión simulada marca un lugar que conviene mirar. No es una ruta propuesta, un plan de servicio ni un pronóstico de demanda, y no es una posición de Foundation for Puerto Rico sobre qué servicio debe existir. Los públicos hacen muchos de estos viajes sin horario, así que un par sin ruta con horario no es un par sin servicio.")}</div>
  </section>

  <section class="block" id="findings">
    <h2><span class="ms-icon" aria-hidden="true">lightbulb</span>{t("Findings: where the gaps are", "Hallazgos: dónde están las brechas")}</h2>
    <p class="pm-p">{t("What the open data say about travel between municipios, from the workers who travel to the time a trip takes by timetable. Each finding is explained further down the page. They are facts to read side by side; Foundation for Puerto Rico publishes no ranking of where service should go, which is a decision for its leadership.",
                       "Lo que dicen los datos abiertos sobre los viajes entre municipios, desde las personas que viajan hasta el tiempo que toma un viaje por horario. Cada hallazgo se explica más abajo en la página. Son datos para leer uno al lado del otro; Foundation for Puerto Rico no publica una clasificación de dónde debe ir el servicio, que es una decisión de su dirección.")}</p>
    <ol class="tl-findings">
      <li><b>{t("Most travel to work crosses a municipal line, and little of it has a timetabled route.", "La mayoría de los viajes al trabajo cruzan un límite municipal, y pocos tienen una ruta con horario.")}</b> <span>{t(f"{num(p['other_municipio'])} workers ({p['other_municipio_pct']}%) work outside the municipio where they live. Only {b['timetable']['pct']}% of that travel is between pairs of municipios that a route with a current timetable joins; {b['publico']['pct']}% has only a público route of the 2020 list and {b['none']['pct']}% has no route listed.",
             f"{num(p['other_municipio'])} personas ({p['other_municipio_pct']} %) trabajan fuera del municipio donde viven. Solo el {b['timetable']['pct']} % de esos viajes ocurre entre pares de municipios que une una ruta con horario vigente; el {b['publico']['pct']} % solo tiene una ruta de públicos de la lista de 2020 y el {b['none']['pct']} % no tiene ninguna ruta en las listas.")}</span></li>
      <li><b>{t("By timetable, a trip between town centers is possible only in and around San Juan, and it is slow.", "Por horario, un viaje entre centros de pueblo solo es posible en San Juan y sus alrededores, y es lento.")}</b> <span>{t(f"Leaving between 6:00 and 9:00 on a weekday, {tt.get('pairs_with_a_journey', 0)} of the {num(p['pairs'])} pairs have a trip of three hours or less; the fastest takes a median of {ratio} times as long as driving.",
             f"Saliendo entre las 6:00 y las 9:00 en día de semana, {tt.get('pairs_with_a_journey', 0)} de los {num(p['pairs'])} pares tienen un viaje de tres horas o menos; el más rápido toma una mediana de {ratio} veces lo que toma en carro.")}</span></li>
      <li><b>{t("Most town centers have no timetabled stop nearby.", "La mayoría de los centros de pueblo no tienen una parada con horario cerca.")}</b> <span>{t(f"{tt.get('centres_without_a_stop', '—')} of the 78 have no stop of a weekday timetable within 1 km. Only {published} municipios publish a timetable for their own system; {own['expired']} have one that expired and {own['none']} report service but publish none.",
             f"{tt.get('centres_without_a_stop', '—')} de los 78 no tienen una parada con horario de día de semana a 1 km o menos. Solo {published} municipios publican un horario de su propio sistema; {own['expired']} tienen uno vencido y {own['none']} informan servicio pero no publican ninguno.")}</span></li>
      <li><b>{t(f"{p['simulated']} pairs have many workers and no timetabled route.", f"{p['simulated']} pares tienen muchas personas y ninguna ruta con horario.")}</b> <span>{t(f"Each has 500 workers or more traveling between them ({num(p['simulated_workers'])} in all); {p['simulated_none']} have no route listed at all and {p['simulated'] - p['simulated_none']} only a público route of 2020. The map draws each as a simulated connection along the roads, not as a proposed route.",
             f"En cada uno viajan 500 personas o más ({num(p['simulated_workers'])} en total); {p['simulated_none']} no tienen ninguna ruta en las listas y {p['simulated'] - p['simulated_none']} solo una ruta de públicos de 2020. El mapa dibuja cada uno como una conexión simulada por las carreteras, no como una ruta propuesta.")}</span></li>
      <li><b>{t("The roads those connections follow are busy, and many pass bridges in poor condition.", "Las carreteras que siguen esas conexiones tienen mucho tránsito, y muchas pasan por puentes en mala condición.")}</b> <span>{t(f"Their counted roads carry a median of {num(med_traffic)} vehicles a day, and {poor_br} of the {p['simulated']} pass a bridge in poor condition.",
             f"Sus carreteras con conteo llevan una mediana de {num(med_traffic)} vehículos al día, y {poor_br} de las {p['simulated']} pasan por un puente en mala condición.")}</span></li>
      <li><b>{t("One household in eight has no vehicle.", "Uno de cada ocho hogares no tiene vehículo.")}</b> <span>{t(f"{nv_pr}% of Puerto Rico's households have no vehicle (American Community Survey {need_period}); the tables give the share at both ends of every pair.",
             f"El {nv_pr} % de los hogares de Puerto Rico no tiene vehículo (Encuesta sobre la Comunidad {need_period}); las tablas dan la proporción en los dos extremos de cada par.")}</span></li>
      <li><b>{t("Part of the gap is in the data.", "Parte de la brecha está en los datos.")}</b> <span>{t("Públicos run without timetables and the only list of their routes is of 2020; many municipal systems publish no timetable; the open crash data hold only deaths. Where a pair shows no route, people may still travel by público or with a transfer.",
             "Los públicos operan sin horario y la única lista de sus rutas es de 2020; muchos sistemas municipales no publican horario; los datos abiertos de choques solo tienen las muertes. Donde un par no muestra ruta, la gente puede viajar en público o con un trasbordo.")}</span></li>
    </ol>
  </section>

  <section class="block" id="links">
    <h2><span class="ms-icon" aria-hidden="true">map</span>{t("1 · Where timetables join municipios, and where they do not", "1 · Dónde los horarios unen municipios y dónde no")}</h2>
    <p class="pm-p">{t(f"Green lines join the {b['timetable']['pairs']} pairs of municipios that share a route with a current timetable; nearly all are in the San Juan area. Each follows the stretch of its busiest route between the two municipios, as the timetable draws it, the ferry crossings included. Dashed lines are the {p['simulated']} simulated connections: pairs with {num(minw)} workers or more and no timetabled route. {p['simulated_none']} of them have no route listed at all (orange) and {p['simulated'] - p['simulated_none']} had a público route on the 2020 list (purple). The largest with no route listed are {lst(top_none)}. The largest with only a público route listed are {lst(top_pub)}.",
                       f"Las líneas verdes unen los {b['timetable']['pairs']} pares de municipios que comparten una ruta con horario vigente; casi todos están en el área de San Juan. Cada una sigue el tramo de su ruta más frecuente entre los dos municipios, como lo traza el horario, incluidos los cruces en lancha. Las líneas entrecortadas son las {p['simulated']} conexiones simuladas: pares con {num(minw)} personas o más y sin ruta con horario. {p['simulated_none']} de ellas no tienen ninguna ruta en las listas (anaranjado) y {p['simulated'] - p['simulated_none']} tenían una ruta de públicos en la lista de 2020 (violeta). Las mayores sin ninguna ruta en las listas son {lst(top_none)}. Las mayores que solo tienen una ruta de públicos en las listas son {lst(top_pub)}.")}</p>
    <div class="card pm-map tl-map" id="tlMap" data-t="skip"></div>
    <p class="pm-small" id="tlMapNote" data-t="skip"></p>
    <p class="pm-p">{t(f"By the weekday timetables, a trip that leaves a town center between 6:00 and 9:00 reaches the other town center within three hours for {tt.get('pairs_with_a_journey', 0)} of the {num(p['pairs'])} pairs, {where_en}. The fastest of those trips takes a median of {ratio} times as long as driving without traffic (Caguas to San Juan: {cs.get('tt_best', '—')} minutes by timetable, {cs.get('min', '—')} by car). {tt.get('centres_without_a_stop', '—')} of the 78 town centers have no stop of a weekday timetable within 1 km. The tables below give these figures for every pair and every municipio. They are facts to look at side by side, not a ranking of where service should go.",
                       f"Según los horarios de día de semana, un viaje que sale de un centro de pueblo entre las 6:00 y las 9:00 llega al otro centro de pueblo en tres horas o menos en {tt.get('pairs_with_a_journey', 0)} de los {num(p['pairs'])} pares, {where_es}. El más rápido de esos viajes toma una mediana de {ratio} veces lo que toma en carro sin tráfico (de Caguas a San Juan: {cs.get('tt_best', '—')} minutos por horario y {cs.get('min', '—')} en carro). {tt.get('centres_without_a_stop', '—')} de los 78 centros de pueblo no tienen una parada con horario de día de semana a 1 km o menos. Las tablas de abajo dan estas cifras para cada par y cada municipio. Son datos para mirar uno al lado del otro, no una clasificación de dónde debe ir el servicio.")}</p>
    <p class="pm-p">{t("The same lines are layers of the main map, where they can be set over any other data:", "Las mismas líneas son capas del mapa principal, donde se pueden poner sobre cualquier otro dato:")}</p>
    <p class="pm-p"><a href="index.html#l=links">{t("simulated connections", "conexiones simuladas")}</a> · <a href="index.html#l=links,publicos,routes">{t("with the público routes of 2020 and the timetabled routes", "con las rutas de públicos de 2020 y las rutas con horario")}</a></p>
  </section>

  <section class="block" id="pairs">
    <h2><span class="ms-icon" aria-hidden="true">table_view</span>{t("2 · Pair by pair", "2 · Par por par")}</h2>
    <p class="pm-p">{t(f"Each row is a pair of municipios, with the workers who travel between them in both directions. Pick a municipio or a kind of pair. The number in the last column is the pair's place among the simulated connections, from the most workers down. {num(low)} of the {num(p['pairs'])} pairs have few workers and a margin of error as large as the estimate; they are marked low reliability and never get a simulated connection.",
                       f"Cada fila es un par de municipios, con las personas que viajan entre ellos para trabajar en las dos direcciones. Escoja un municipio o un tipo de par. El número de la última columna es el lugar del par entre las conexiones simuladas, de más a menos personas. {num(low)} de los {num(p['pairs'])} pares tienen pocas personas y un margen de error tan grande como el estimado; se marcan como poco confiables y nunca reciben una conexión simulada.")}</p>
    <div class="tl-pick" id="tlPick" data-t="skip"></div>
    <div class="card pm-tablebox oz-tablebox" id="tlPairs" data-t="skip"></div>
  </section>

  <section class="block" id="municipios">
    <h2><span class="ms-icon" aria-hidden="true">location_city</span>{t("3 · By municipio", "3 · Por municipio")}</h2>
    <p class="pm-p">{t(f"For each municipio: the workers who live there, how many work in another municipio, how many come in, and the share of that travel (in and out) that is between pairs with a timetabled route. The last column says whether the municipio's own bus or trolley system publishes a timetable: {published} do, {own['expired']} have one that expired, {own['none']} report service to the federal transit database but publish none, and {no_system} have no system listed.",
                       f"Para cada municipio: las personas que trabajan y viven allí, cuántas trabajan en otro municipio, cuántas llegan, y la parte de esos viajes (de entrada y de salida) que ocurre entre pares con una ruta con horario. La última columna indica si el sistema de guaguas o trolleys del propio municipio publica un horario: {published} lo publican, {own['expired']} tienen uno vencido, {own['none']} informan servicio a la base de datos federal de tránsito pero no publican ninguno, y {no_system} no tienen ningún sistema en las listas.")}</p>
    <div class="card pm-tablebox oz-tablebox" id="tlMunis" data-t="skip"></div>
  </section>

  <section class="block" id="reading">
    <h2><span class="ms-icon" aria-hidden="true">route</span>{t("4 · How to read a simulated connection", "4 · Cómo leer una conexión simulada")}</h2>
    <div class="note"><b>{t("Timetabled route.", "Ruta con horario.")}</b> {t(f"A route of the Autoridad de Transporte Integrado or of a municipal system, with a timetable that still runs on {as_of}, has stops in both municipios; one stop just across the municipal line is enough, so look at the trips in the table. Where the only such route has a timetable that expired, the pair is marked so and gets no simulated connection. Only direct routes count. On the map, the green line is the stretch of the pair's route with the most weekday trips, from its point in each municipio nearest the town center: a route that serves San Juan in Río Piedras is drawn to Río Piedras. Each stop counts in the municipio whose outline holds it. Where the table says a transfer joins a pair, the two municipios are linked through other municipios by timetabled routes, but no journey time was computed and the trip may be long.",
                                                                              f"Una ruta de la Autoridad de Transporte Integrado o de un sistema municipal, con un horario que sigue vigente al {as_of}, tiene paradas en los dos municipios; basta una parada justo al otro lado del límite municipal, así que mire los viajes en la tabla. Donde la única ruta así tiene el horario vencido, el par se marca así y no recibe una conexión simulada. Solo cuentan las rutas directas. En el mapa, la línea verde es el tramo de la ruta del par con más viajes en día de semana, desde su punto en cada municipio más cercano al centro de pueblo: una ruta que sirve a San Juan en Río Piedras se dibuja hasta Río Piedras. Cada parada cuenta en el municipio cuyo límite la contiene. Donde la tabla dice que un trasbordo une un par, los dos municipios se conectan a través de otros municipios con rutas con horario, pero no se calculó el tiempo del viaje y puede ser largo.")}</div>
    <div class="note"><b>{t("Público route on the 2020 list.", "Ruta de públicos en la lista de 2020.")}</b> {t(f"The Instituto de Estadísticas de Puerto Rico published {num(pub['routes'])} público routes of the Autoridad de Carreteras y Transportación on March 19, 2020; {num(pub['between_municipios'])} of them join two municipios or more. A route joins the municipios where its line ends and those whose town center it passes within 1 km. The list has no timetable and has not been updated, so a route on it may no longer run. The first step for any of these pairs is to confirm with the operators what runs today.",
                                                                                                      f"El Instituto de Estadísticas de Puerto Rico publicó {num(pub['routes'])} rutas de públicos de la Autoridad de Carreteras y Transportación el 19 de marzo de 2020; {num(pub['between_municipios'])} de ellas unen dos municipios o más. Una ruta une los municipios donde termina su línea y aquellos por cuyo centro de pueblo pasa a 1 km o menos. La lista no tiene horarios y no se ha actualizado, así que una ruta de la lista puede que ya no opere. El primer paso para cualquiera de estos pares es confirmar con los operadores qué opera hoy.")}</div>
    <div class="note"><b>{t("Time by timetable.", "Tiempo por horario.")}</b> {t(f"For every pair, a program searched the published weekday timetables for the fastest trip between the two town centers, in either direction, leaving every 15 minutes from 6:00 to 9:00. It walks up to 1 km to the first stop and from the last, and up to 400 m between stops to transfer, with 2 minutes for each transfer. The table gives the fastest of those trips and how many times longer it is than driving without traffic; the usual trip, with the wait for the bus, is longer. {ends_only} municipal systems publish times only for the ends of some routes, so trips that board or leave at their other stops are missed. Públicos are in no timetable.",
                                                                     f"Para cada par, un programa buscó en los horarios publicados de día de semana el viaje más rápido entre los dos centros de pueblo, en cualquiera de las dos direcciones, saliendo cada 15 minutos de las 6:00 a las 9:00. Camina hasta 1 km hasta la primera parada y desde la última, y hasta 400 m entre paradas para un trasbordo, con 2 minutos por cada trasbordo. La tabla da el más rápido de esos viajes y cuántas veces más largo es que manejar sin tráfico; el viaje de costumbre, con la espera de la guagua, es más largo. {ends_only} sistemas municipales publican horas solo para los extremos de algunas rutas, así que se pierden los viajes que suben o bajan en sus otras paradas. Los públicos no están en ningún horario.")}</div>
    <div class="note"><b>{t("Need at each end.", "Necesidad en cada extremo.")}</b> {t(f"The shares of households with no vehicle and of residents below the poverty level in each municipio come from the American Community Survey {need_period} (5-year), as on the Analysis tab. They describe the whole municipio, not the people who travel between the two.",
                                                                     f"Las proporciones de hogares sin vehículo y de residentes bajo el nivel de pobreza de cada municipio vienen de la Encuesta sobre la Comunidad {need_period} (5 años), como en la pestaña Análisis. Describen todo el municipio, no a las personas que viajan entre los dos.")}</div>
    <div class="note"><b>{t("Along a simulated connection.", "A lo largo de una conexión simulada.")}</b> {t("The residents of the 2020 Census blocks within 1 km of the connection's line and, in brackets, those of them more than 400 m in a straight line from a scheduled stop; and the bridges within 50 m of the line that the Federal Highway Administration rates in poor condition. Connections share roads, so these counts must not be added up.",
                                                                     "Los residentes de los bloques del Censo 2020 a 1 km o menos de la línea de la conexión y, entre paréntesis, los que viven a más de 400 m en línea recta de una parada con horario; y los puentes a 50 m o menos de la línea que la Administración Federal de Carreteras califica en mala condición. Las conexiones comparten carreteras, así que estas cifras no deben sumarse.")}</div>
    <div class="note"><b>{t("No route listed.", "Sin ruta en las listas.")}</b> {t("Neither source lists a route that joins the two municipios. People may still travel between them by car, by a público that is not on the 2020 list, or with a transfer.", "Ninguna de las dos fuentes tiene una ruta que una los dos municipios. La gente puede viajar entre ellos en carro, en un público que no está en la lista de 2020 o con un trasbordo.")}</div>
    <div class="note"><b>{t("The line.", "La línea.")}</b> {t(f"A simulated connection is the fastest path along the roads between the two town centers, for a pair with {num(minw)} workers or more. Together the {p['simulated']} lines measure {num(p['simulated_km'])} km, counting shared roads once for each pair. The line shows a distance and a direction. Where a route would run, where it would stop and how often are questions for a transit study with the operators and the communities.",
                                                              f"Una conexión simulada es el camino más rápido por las carreteras entre los dos centros de pueblo, para un par con {num(minw)} personas o más. Juntas, las {p['simulated']} líneas miden {num(p['simulated_km'])} km, contando las carreteras compartidas una vez por cada par. La línea muestra una distancia y una dirección. Por dónde pasaría una ruta, dónde pararía y con qué frecuencia son preguntas para un estudio de transporte con los operadores y las comunidades.")}</div>
    <div class="note"><b>{t("Traffic on its roads.", "Tránsito en sus carreteras.")}</b> {t(f"The last column of the table gives, for each simulated connection, the traffic on the roads it follows: points every 100 m along the line take the annual average daily traffic of the counted main road within 25 m (FHWA's Highway Performance Monitoring System, data year {tr['data_year']}), and the column shows their median. Across the {p['simulated']} connections the median is {num(med_all)} vehicles a day. A busy road means people already drive that way; it does not say whether a bus would be used. The layer Traffic on the main roads shows every counted road.", f"La última columna de la tabla da, para cada conexión simulada, el tránsito en las carreteras que sigue: puntos cada 100 m a lo largo de la línea toman el tránsito promedio diario anual de la carretera principal con conteo que esté a 25 m o menos (Sistema de Monitoreo del Desempeño de Carreteras de la FHWA, año de datos {tr['data_year']}), y la columna muestra su mediana. Entre las {p['simulated']} conexiones, la mediana es de {num(med_all)} vehículos al día. Una carretera con mucho tránsito indica que la gente ya viaja por ahí; no dice si se usaría una guagua. La capa Tránsito en las carreteras principales muestra todas las carreteras con conteo.")}</div>
    <div class="note"><b>{t("Road deaths on its roads.", "Muertes en sus carreteras.")}</b> {t(f"The last column counts the people killed in fatal crashes within 100 m of each simulated connection over {sf['years'][0]}-{sf['years'][1]} (NHTSA's Fatality Analysis Reporting System), for every 10 km of the connection, so that long and short connections can be compared. Connections share roads, so the counts must not be added up. The observatory publishes only these five-year totals, never a crash's place or date. Across the {p['simulated']} connections the middle value is {num(med_death, 1)} deaths per 10 km; the highest are {top_death}.", f"La última columna cuenta las personas muertas en choques fatales a 100 m o menos de cada conexión simulada en {sf['years'][0]}-{sf['years'][1]} (Sistema de Informes de Análisis de Fatalidades de la NHTSA), por cada 10 km de la conexión, para poder comparar conexiones largas y cortas. Las conexiones comparten carreteras, así que las cifras no se deben sumar. El observatorio publica solo estos totales de cinco años, nunca el lugar ni la fecha de un choque. Entre las {p['simulated']} conexiones, el valor del medio es {num(med_death, 1)} muertes por cada 10 km; las más altas son {top_death_es}.")}</div>
  </section>

  <section class="block" id="method">
    <h2><span class="ms-icon" aria-hidden="true">info</span>{t("Method and limits", "Método y límites")}</h2>
    <div class="note"><b>{t("Workers.", "Personas que trabajan.")}</b> {t(f"The Census Bureau's County-to-County Commuting Flows of the American Community Survey {period} count workers 16 and over by the municipio where they live and the municipio where they work. It is the newest release: the Bureau publishes these flows every five years, and the survey years include the start of the pandemic. For a pair, the page adds the two directions; the margin of error of the sum is the root of the sum of the squares of the two margins (90% confidence).",
                                                                         f"Los Flujos de Viaje al Trabajo entre Condados del Negociado del Censo, de la Encuesta sobre la Comunidad {period}, cuentan a las personas de 16 años o más que trabajan según el municipio donde viven y el municipio donde trabajan. Es la publicación más reciente: el Negociado publica estos flujos cada cinco años, y los años de la encuesta incluyen el comienzo de la pandemia. Para un par, la página suma las dos direcciones; el margen de error de la suma es la raíz de la suma de los cuadrados de los dos márgenes (90 % de confianza).")}</div>
    <div class="note"><b>{t("Only work trips.", "Solo viajes al trabajo.")}</b> {t("The flows count where people work. Trips to study, to a doctor, to shop or to visit family are not counted, and neither are people without a job, who often depend most on transit. The figures say how many people make the trip, not how they travel: most drive.", "Los flujos cuentan dónde trabaja la gente. No se cuentan los viajes para estudiar, ir al médico, comprar o visitar a la familia, ni las personas sin empleo, que muchas veces son las que más dependen del transporte colectivo. Las cifras dicen cuántas personas hacen el viaje, no cómo viajan: la mayoría conduce.")}</div>
    <div class="note"><b>{t("Timetables.", "Horarios.")}</b> {t(f"A timetable shows the service an operator publishes, not the service that ran. Several municipal systems publish no timetable or let theirs expire, so some real routes are missing here. {len(ends)} municipal systems ({ends_en}) time only the first and last stop of some routes; for those routes, the system's stops along the route's line count as its stops. The timetables are refreshed every night; this page's figures are rebuilt when the sources change.", f"Un horario muestra el servicio que un operador publica, no el servicio que se dio. Varios sistemas municipales no publican horario o dejaron vencer el suyo, así que aquí faltan algunas rutas reales. {len(ends)} sistemas municipales ({ends_es}) solo dan la hora de la primera y la última parada de algunas rutas; para esas rutas, las paradas del sistema a lo largo de la línea de la ruta cuentan como sus paradas. Los horarios se actualizan cada noche; las cifras de esta página se preparan de nuevo cuando cambian las fuentes.")}</div>
    <div class="note"><b>{t("Town centers and roads.", "Centros de pueblo y carreteras.")}</b> {t("Distances and times run between town centers along the roads mapped in OpenStreetMap, at typical speeds for each kind of road, without traffic. San Juan's center is Old San Juan, though many of its jobs are in Hato Rey, Río Piedras and Santurce. Vieques and Culebra have no road to the main island, so their pairs have no distance and no simulated connection; the ferry from Ceiba is a timetabled route.", "Las distancias y los tiempos van de un centro de pueblo a otro por las carreteras que aparecen en OpenStreetMap, a velocidades típicas para cada tipo de carretera y sin tráfico. El centro de San Juan es el Viejo San Juan, aunque muchos de sus empleos están en Hato Rey, Río Piedras y Santurce. Vieques y Culebra no tienen carretera a la isla grande, así que sus pares no tienen distancia ni conexión simulada; la lancha desde Ceiba es una ruta con horario.")}</div>
    <div class="note"><b>{t("More detail.", "Más detalle.")}</b> {t("The method, the checks and the code are in docs/transit-links.md of the project repository; each figure has an entry in the data dictionary (search for 'between municipios').", "El método, las comprobaciones y el código están en docs/transit-links.md del repositorio del proyecto; cada cifra tiene una entrada en el diccionario de datos (busque «entre municipios»).")}</div>
  </section>

  <section class="block" id="sources">
    <h2><span class="ms-icon" aria-hidden="true">menu_book</span>{t("Sources and licenses", "Fuentes y licencias")}</h2>
    <div class="note"><b>{t("US Census Bureau.", "Negociado del Censo de EE. UU.")}</b> {t(f"County-to-County Commuting Flows, American Community Survey {period} (5-year), Table 1. US Government work.", f"Flujos de Viaje al Trabajo entre Condados, Encuesta sobre la Comunidad {period} (5 años), Tabla 1. Obra del Gobierno de EE. UU.")}</div>
    <div class="note"><b>{t("Instituto de Estadísticas de Puerto Rico and Autoridad de Carreteras y Transportación.", "Instituto de Estadísticas de Puerto Rico y Autoridad de Carreteras y Transportación.")}</b> {t("Mapa de rutas de porteadores públicos, open data portal of the Instituto (published March 19, 2020). Creative Commons Attribution.", "Mapa de rutas de porteadores públicos, portal de datos abiertos del Instituto (publicado el 19 de marzo de 2020). Creative Commons Atribución.")}</div>
    <div class="note"><b>{t("Timetable feeds.", "Archivos de horarios.")}</b> {t("GTFS feeds of the Autoridad de Transporte Integrado and of the municipal systems, as the observatory's Transit tab lists them, each with its own terms.", "Archivos GTFS de la Autoridad de Transporte Integrado y de los sistemas municipales, como los presenta la pestaña Transporte del observatorio, cada uno con sus propios términos.")}</div>
    <div class="note"><b>{t("Roads.", "Carreteras.")}</b> {t("© OpenStreetMap contributors, Open Database License (ODbL).", "© colaboradores de OpenStreetMap, Open Database License (ODbL).")}</div>
    <div class="note"><b>{t("Data files.", "Archivos de datos.")}</b> {t("data/transit_links.json, and the map layers data/simulated_links.geojson and data/publicos.geojson (transit_links.py).", "data/transit_links.json, y las capas del mapa data/simulated_links.geojson y data/publicos.geojson (transit_links.py).")}</div>
    <div class="note"><b>{t("How to cite this page.", "Cómo citar esta página.")}</b> {t(f"Foundation for Puerto Rico, Knowledge Area: Connections between municipios, PR Data Observatory, timetables of {as_of} (draft). Data: US Census Bureau; Instituto de Estadísticas de Puerto Rico and ACT; ATI and municipal transit systems; OpenStreetMap contributors.", f"Foundation for Puerto Rico, Área de conocimiento: Conexiones entre municipios, Observatorio de Datos de PR, horarios del {as_of} (borrador). Datos: Negociado del Censo de EE. UU.; Instituto de Estadísticas de Puerto Rico y ACT; ATI y sistemas municipales de transporte; colaboradores de OpenStreetMap.")}</div>
  </section>
</main>
<script src="js/core/knowledge.js?v={ver("js/core/knowledge.js")}"></script>
<script>Core.knowledge.render(); I18N.apply();</script>
<script src="js/common.js?v={ver("js/common.js")}"></script>
<script src="js/transit_links_page.js?v=5"></script>
<script src="js/chatboot.js?v={ver("js/chatboot.js")}"></script>
</body>
</html>
"""
    for m in re.finditer(r"<b>([^<]*)</b> ([^<]*)</(?:div|p)>", page):
        lead, body = " ".join(html.unescape(m.group(1)).split()), " ".join(html.unescape(m.group(2)).split())
        key = " ".join(f"<b>{m.group(1)}</b> {m.group(2)}".split())
        ES[key] = f"<b>{html.escape(ES[lead], quote=False)}</b> {html.escape(ES[body], quote=False)}"
        keep = {" ".join(en.split()) for en, _ in JS}   # a lead that is also a string of the script stays on its own too
        if lead not in keep:
            ES.pop(lead, None)
        ES.pop(body, None)
    (ROOT / "site" / "transit-links.html").write_text(page, encoding="utf-8", newline="\n")
    es = {"_about": "The Connections between municipios page of the Knowledge Area (transit-links.html) and site/js/transit_links_page.js. Written by docs/analysis/transit-links-2026-11/make_page.py from its (English, Spanish) pairs: edit them there, not here."}
    es.update(ES)
    (ROOT / "i18n_src" / "es" / "tlinks.json").write_text(json.dumps(es, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(f"wrote site/transit-links.html and i18n_src/es/tlinks.json ({len(ES)} strings)")


if __name__ == "__main__":
    build()
