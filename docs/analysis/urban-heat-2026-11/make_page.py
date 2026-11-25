"""Writes the Knowledge Area page "Urban heat" (site/urban-heat.html) and its Spanish (i18n_src/es/urban_heat.json).

  python docs/analysis/urban-heat-2026-11/make_page.py   read site/data/urban_heat.json (python urban_heat.py makes it); write the page and the Spanish
                                                         of the page and of site/js/urban_heat.js. Then run python i18n.py.

The page follows the site's language rule (docs/i18n.md) and the pattern of the FEMA funding page (docs/analysis/public-money-v2-2026-10/make_page.py):
every string is written once, as an (English, Spanish) pair, and every figure in the text is read from the data file. Terrain and climate plan, step 3
(HANDOFF decision 80): the heat of the land set beside the people who live on it, barrio by barrio, never combined into one score, with no conclusion
in the text (the rule of decision 72). Prepared with Claude (AI) for FPR, 2026-11-04.
"""
import html
import json
import re
import statistics
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


def fes(x, d=2):
    """A number in Spanish (Puerto Rico): a point for decimals, as the site writes them."""
    return f"{x:.{d}f}"


JS = [
    ("The data could not be loaded ({error}). Check your connection and reload.", "No se pudieron cargar los datos ({error}). Verifique su conexión y vuelva a cargar la página."),
    ("Surface temperature, summer mornings (°C)", "Temperatura de la superficie, mañanas de verano (°C)"),
    ("Surface temperature, summer nights (°C)", "Temperatura de la superficie, noches de verano (°C)"),
    ("Vegetation greenness (NDVI)", "Verdor de la vegetación (NDVI)"),
    ("Residents 65 and older (%)", "Residentes de 65 años o más (%)"),
    ("Residents below the poverty level (%)", "Residentes bajo el nivel de pobreza (%)"),
    ("Households without a vehicle (%)", "Hogares sin vehículo (%)"),
    ("Households of one person living alone (%)", "Hogares de una persona que vive sola (%)"),
    ("Drive time to a general hospital (minutes)", "Tiempo en carro a un hospital general (minutos)"),
    ("margin of error above 30% of the estimate", "margen de error mayor que el 30 % del estimado"),
    ("{name} ({muni}): {land}; {people}", "{name} ({muni}): {land}; {people}"),
    ("Scatter plot: each dot is a barrio; dashed lines mark the medians of all barrios", "Gráfico de dispersión: cada punto es un barrio; las líneas discontinuas marcan las medianas de todos los barrios"),
    ("Rank correlation across the {n} barrios with both values: {rho}.", "Correlación de rangos entre los {n} barrios con ambos valores: {rho}."),
    ("Within {muni} ({n} barrios): {rho}.", "Dentro de {muni} ({n} barrios): {rho}."),
    ("{muni} has {n} barrios with both values, too few for a rank correlation.", "{muni} tiene {n} barrios con ambos valores, muy pocos para una correlación de rangos."),
    ("Barrio", "Barrio"), ("Municipio", "Municipio"), ("Residents (2020 Census)", "Residentes (Censo 2020)"),
    ("Barrios: surface heat, greenness and residents, side by side", "Barrios: calor de la superficie, verdor y residentes, uno al lado del otro"),
    ("{n} barrios. Values in italics have a margin of error above 30% of the estimate; ± is the margin of error at 90% confidence.",
     "{n} barrios. Los valores en cursiva tienen un margen de error mayor que el 30 % del estimado; ± es el margen de error con 90 % de confianza."),
    ("Rank correlations across the barrios", "Correlaciones de rangos entre los barrios"),
    ("{a} and {b}: {rho}", "{a} y {b}: {rho}"),
    ("{measure}: margin of error", "{measure}: margen de error"),
    ("All of Puerto Rico", "Todo Puerto Rico"),
]
for en, es in JS:
    t(en, es)


def build():
    D = json.loads((ROOT / "site" / "data" / "urban_heat.json").read_text(encoding="utf-8"))
    y = D["land_summers"]["day"]
    y0, y1 = y[0], y[-1]
    acs = D["acs_window"]
    r = lambda a, b: (D["rho"].get(f"{a}:{b}") or D["rho"][f"{b}:{a}"])["rho"]
    n_b = len(D["geo"]["ids"])
    med = lambda k: statistics.median(x for x in D["land"][k] if x is not None)
    day_med, night_med = med("day"), med("night")

    page = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{t("Knowledge Area · Urban heat", "Área de conocimiento · Calor urbano")}</title>
<meta name="description" content="{t("How hot the land gets on summer mornings and how warm it stays at night, and how green it is, barrio by barrio, set beside who lives there: older residents, poverty, households without a vehicle, people living alone and the drive to a hospital. Side by side, never combined; facts only.", "Cuán caliente se pone el terreno en las mañanas de verano y cuán cálido se mantiene de noche, y cuán verde es, barrio por barrio, junto a quienes viven allí: residentes de mayor edad, pobreza, hogares sin vehículo, personas que viven solas y el viaje a un hospital. Uno al lado del otro, nunca combinados; solo hechos.")}">
<meta name="robots" content="noindex, nofollow">
<meta name="theme-color" content="#FFFFFF">
<link rel="icon" href="img/fpr-mark.png">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Material+Symbols+Rounded:opsz,wght,FILL,GRAD@24,400,1,0&icon_names=account_balance,account_tree,bolt,chat_bubble,close,commute,dark_mode,delete,diversity_3,download,explore,grid_on,grid_view,home_work,hourglass_bottom,info,light_mode,lightbulb,map,menu_book,park,payments,price_change,rocket_launch,route,scatter_plot,school,send,table_view,thermostat,view_in_ar,warning,water,wifi,woman,work&display=block">
<link rel="stylesheet" href="css/twin.css?v=63">
<link rel="stylesheet" href="css/housing.css?v=22">
<link rel="stylesheet" href="css/public_money.css?v=2">
<link rel="stylesheet" href="css/urban_heat.css?v=3">
<link rel="stylesheet" href="css/chat.css?v=5">
<link rel="stylesheet" href="css/ws.css?v=2">
<script src="js/i18n.js?v=63" data-page="urbanheat"></script>
</head>
<body class="research">
<a class="skip" href="#compare">{t("Skip to the content", "Ir al contenido")}</a>
<header class="topbar">
  <a class="logo" href="index.html" title="{t("PR Data Observatory home", "Inicio del Observatorio de Datos de PR")}"><img src="img/fpr-logo.png" alt="{t("Foundation for Puerto Rico. PR Data Observatory home", "Foundation for Puerto Rico. Inicio del Observatorio de Datos de PR")}"></a>
  <div class="brand"><b>{t("Knowledge Area · Urban heat", "Área de conocimiento · Calor urbano")}</b><span>{t("Surface heat and greenness beside the people who live there, by barrio", "El calor de la superficie y el verdor junto a quienes viven allí, por barrio")}</span></div>
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
  <span class="ka-tabs" role="group" aria-label="{t("Knowledge Area", "Área de conocimiento")}" data-ka="urbanheat"></span><span class="ka-sep" aria-hidden="true"></span>
  <a href="#compare">{t("Heat and people", "Calor y personas")}</a><a href="#barrios">{t("Barrio by barrio", "Barrio por barrio")}</a><a href="#grid">{t("All the pairs", "Todos los pares")}</a><a href="#cooling">{t("Cooler places", "Lugares más frescos")}</a><a href="#method">{t("Method", "Método")}</a><a href="#sources">{t("Sources", "Fuentes")}</a>
</nav>

<main class="page">
  <div class="note caution review-note" role="note" data-ka-note></div>

  <section class="hero" id="compare">
    <div class="eyebrow">{t("Knowledge Area · Terrain and climate", "Área de conocimiento · Terreno y clima")}</div>
    <h1>{t("Urban heat: the land and the people on it, by barrio", "Calor urbano: el terreno y las personas que viven en él, por barrio")}</h1>
    <p class="lede">{t(f"How hot the land gets on summer mornings, how warm it stays at night and how green it is, measured from satellites over the summers of {y0} to {y1}, set beside measures of the residents of each of the {n_b} barrios. Pick a measure of the land, a measure of the people and, if you wish, a municipio. The two are shown side by side and never combined into one score.", f"Cuán caliente se pone el terreno en las mañanas de verano, cuán cálido se mantiene de noche y cuán verde es, medido desde satélites en los veranos de {y0} a {y1}, junto a medidas de los residentes de cada uno de los {n_b} barrios. Escoja una medida del terreno, una medida de las personas y, si desea, un municipio. Las dos se muestran una al lado de la otra y nunca se combinan en una sola puntuación.")}</p>
    <div class="pm-controls">
      <label>{t("Land", "Terreno")} <select id="uhLand"></select></label>
      <label>{t("People", "Personas")} <select id="uhPeople"></select></label>
      <label>{t("Municipio", "Municipio")} <select id="uhMuni"></select></label>
      <button type="button" class="btn" id="uhCsv"><span class="ms-icon" aria-hidden="true">download</span>{t("Download CSV", "Descargar CSV")}</button>
    </div>
    <div class="card pm-chart"><div id="uhScatter"></div></div>
    <div class="note" id="uhRead" data-t="skip"></div>
    <p class="uh-links"><a id="uhMap" href="index.html"><span class="ms-icon" aria-hidden="true">map</span>{t("Shade the barrios by this land measure on the map", "Sombrear los barrios por esta medida del terreno en el mapa")}</a></p>
    <div class="note caution"><b>{t("Read with care.", "Lea con cuidado.")}</b> {t("This page states facts and draws no conclusions. Surface temperature is the temperature of the ground, roofs and pavement, not of the air people breathe. Two measures that rise together across barrios do not show that one causes the other: elevation, the coast and how built a barrio is move several of them at once. The survey figures of a small barrio can have wide margins of error.", "Esta página presenta hechos y no saca conclusiones. La temperatura de la superficie es la del suelo, los techos y el pavimento, no la del aire que se respira. Que dos medidas suban juntas entre barrios no muestra que una cause la otra: la altura, la costa y cuán construido está un barrio mueven varias a la vez. Las cifras de la encuesta de un barrio pequeño pueden tener márgenes de error amplios.")}</div>
  </section>

  <section class="block" id="barrios">
    <h2><span class="ms-icon" aria-hidden="true">table_view</span>{t("1 · Barrio by barrio", "1 · Barrio por barrio")}</h2>
    <p class="pm-p">{t("Every measure of the barrios of the chosen municipio, or of all Puerto Rico, side by side. Select a column heading to sort.", "Todas las medidas de los barrios del municipio escogido, o de todo Puerto Rico, una al lado de la otra. Seleccione el título de una columna para ordenar.")}</p>
    <p class="pm-small" id="uhCount" data-t="skip"></p>
    <div class="card pm-tablebox uh-tablebox" id="uhTable"></div>
  </section>

  <section class="block" id="grid">
    <h2><span class="ms-icon" aria-hidden="true">grid_on</span>{t("2 · All the pairs at once", "2 · Todos los pares a la vez")}</h2>
    <p class="pm-p">{t(f"The rank correlation (Spearman) of each measure of the land with each measure of the people, across all the barrios that have both values. It is 1 when the two orders agree, 0 when they are unrelated and below 0 when they run opposite. Over the {n_b} barrios, the morning and night temperatures have a rank correlation of {r('day', 'night'):.2f}, and greenness and the morning temperature {r('day', 'ndvi'):.2f}.", f"La correlación de rangos (Spearman) de cada medida del terreno con cada medida de las personas, entre todos los barrios que tienen ambos valores. Es 1 cuando los dos órdenes coinciden, 0 cuando no se relacionan y menos de 0 cuando van en sentido contrario. En los {n_b} barrios, las temperaturas de la mañana y de la noche tienen una correlación de rangos de {fes(r('day', 'night'))}, y el verdor y la temperatura de la mañana, {fes(r('day', 'ndvi'))}.")}</p>
    <div class="card pm-tablebox" id="uhGrid"></div>
  </section>

  <section class="block" id="cooling">
    <h2><span class="ms-icon" aria-hidden="true">park</span>{t("3 · From heat islands to cooler places", "3 · De islas de calor a lugares más frescos")}</h2>
    <p class="pm-p">{t("What makes a place hotter, what studies of San Juan found, and what cities elsewhere are doing to cool down, each stated as its source states it. The section names no barrio and recommends no project: the steps at the end show how to use this page to see where the facts line up.", "Qué hace que un lugar sea más caliente, qué encontraron los estudios de San Juan y qué hacen otras ciudades para refrescarse, cada cosa tal como la dice su fuente. La sección no nombra ningún barrio ni recomienda proyectos: los pasos del final muestran cómo usar esta página para ver dónde coinciden los hechos.")}</p>

    <h3 class="uh-h3">{t("What makes a place hot", "Qué hace que un lugar sea caliente")}</h3>
    <div class="note"><b>{t("Five causes.", "Cinco causas.")}</b> {t("The U.S. Environmental Protection Agency (EPA) names five causes of an urban heat island: fewer trees, plants and bodies of water; pavement and roofs that absorb the sun's heat and release it slowly; buildings close together and narrow streets that trap heat and block the wind; waste heat from vehicles, air conditioners and industry; and calm, clear weather. It reports that, in the United States, cities are about 1 to 7 °F (0.6 to 3.9 °C) warmer than outlying areas by day and 2 to 5 °F (1.1 to 2.8 °C) warmer at night.", "La Agencia de Protección Ambiental de EE. UU. (EPA) nombra cinco causas de una isla de calor urbana: menos árboles, plantas y cuerpos de agua; pavimento y techos que absorben el calor del sol y lo sueltan despacio; edificios muy juntos y calles estrechas que atrapan el calor y bloquean el viento; el calor que sueltan los vehículos, los aires acondicionados y la industria; y el tiempo calmado y despejado. Informa que, en Estados Unidos, las ciudades están entre 1 y 7 °F (0.6 a 3.9 °C) más calientes que las áreas de alrededor de día y entre 2 y 5 °F (1.1 a 2.8 °C) más calientes de noche.")}</div>
    <p class="uh-cite"><a href="https://www.epa.gov/heatislands/learn-about-heat-islands" target="_blank" rel="noopener">{t("EPA, Learn About Heat Islands", "EPA, Learn About Heat Islands (en inglés)")}</a></p>
    <div class="note"><b>{t("In Puerto Rico's barrios.", "En los barrios de Puerto Rico.")}</b> {t(f"Across the {n_b} barrios of this page, greenness and the morning surface temperature have a rank correlation of {r('day', 'ndvi'):.2f}: the greener a barrio, the cooler its surface, with few exceptions. The morning and night temperatures have a rank correlation of {r('day', 'night'):.2f}: most barrios whose surface heats up by day also stay warm at night. The median barrio's surface reaches {day_med:.1f} °C on a summer morning and {night_med:.1f} °C at night. Elevation and the sea also shape these values, so they do not show how much of the difference greenness alone explains.", f"En los {n_b} barrios de esta página, el verdor y la temperatura de la superficie en la mañana tienen una correlación de rangos de {fes(r('day', 'ndvi'))}: mientras más verde un barrio, más fresca su superficie, con pocas excepciones. Las temperaturas de la mañana y de la noche tienen una correlación de rangos de {fes(r('day', 'night'))}: la mayoría de los barrios cuya superficie se calienta de día también se mantienen cálidos de noche. La superficie del barrio mediano llega a {fes(day_med, 1)} °C en una mañana de verano y a {fes(night_med, 1)} °C de noche. La altura y el mar también moldean estos valores, así que no muestran cuánto de la diferencia explica el verdor por sí solo.")}</div>

    <h3 class="uh-h3">{t("What studies of San Juan found", "Qué encontraron los estudios de San Juan")}</h3>
    <div class="note"><b>{t("A heat island that grows.", "Una isla de calor que crece.")}</b> {t("A 2004 report for NASA by Jorge E. González-Cruz (Santa Clara University) compared historical air temperatures of an urban and a rural area. It found a heat island in the San Juan metropolitan area all year round, increasing at a rate of 0.41 °C per decade.", "Un informe de 2004 para la NASA de Jorge E. González-Cruz (Universidad de Santa Clara) comparó temperaturas históricas del aire de un área urbana y de un área rural. Encontró una isla de calor en el área metropolitana de San Juan todo el año, que aumenta a razón de 0.41 °C por década.")}</div>
    <p class="uh-cite"><a href="https://ntrs.nasa.gov/citations/20050215322" target="_blank" rel="noopener">{t("González-Cruz, Analysis of upper air, ground and remote sensing data for the ATLAS field campaign in San Juan, Puerto Rico (NASA, 2004)", "González-Cruz, Analysis of upper air, ground and remote sensing data for the ATLAS field campaign in San Juan, Puerto Rico (NASA, 2004; en inglés)")}</a></p>
    <div class="note"><b>{t("Hottest in the late morning.", "Más caliente a media mañana.")}</b> {t("In the field campaign that followed, in February 2004, the heat island of San Juan peaked between 10:00 and noon, with an average difference of 4.5 °C in air temperature between the city and rural areas (González, Comarazamy, Luvall and Rickman, 2006). These are measurements of the air, not of the surface, and from the cool season.", "En la campaña de campo que siguió, en febrero de 2004, la isla de calor de San Juan alcanzó su punto máximo entre las 10:00 y el mediodía, con una diferencia promedio de 4.5 °C en la temperatura del aire entre la ciudad y las áreas rurales (González, Comarazamy, Luvall y Rickman, 2006). Son medidas del aire, no de la superficie, y de la temporada fresca.")}</div>
    <p class="uh-cite"><a href="https://ams.confex.com/ams/Annual2006/webprogram/Paper105359.html" target="_blank" rel="noopener">{t("González et al., A validation study of the urban heat island in the tropical coastal city of San Juan, Puerto Rico (American Meteorological Society, 2006)", "González et al., A validation study of the urban heat island in the tropical coastal city of San Juan, Puerto Rico (American Meteorological Society, 2006; en inglés)")}</a></p>

    <h3 class="uh-h3">{t("What cities are doing", "Qué hacen las ciudades")}</h3>
    <div class="note"><b>{t("Trees and vegetation.", "Árboles y vegetación.")}</b> {t("Trees cool by their shade and by evapotranspiration. A 2026 study of Barcelona's streets found that street trees in moist soil lowered the air temperature by 1.2 ± 0.4 °C on average. In dry soil, during droughts, that cooling of the air fell, but the shade kept 71% to 97% of its cooling effect.", "Los árboles refrescan con su sombra y con la evapotranspiración. Un estudio de 2026 en las calles de Barcelona encontró que los árboles de la calle en suelo húmedo bajaron la temperatura del aire 1.2 ± 0.4 °C en promedio. En suelo seco, durante las sequías, ese enfriamiento del aire bajó, pero la sombra conservó entre el 71 % y el 97 % de su efecto refrescante.")}</div>
    <p class="uh-cite"><a href="https://doi.org/10.1016/j.uclim.2026.103086" target="_blank" rel="noopener">{t("The role of soil moisture and shading in influencing the capacity of urban street trees to reduce heat stress (Urban Climate, 2026)", "The role of soil moisture and shading in influencing the capacity of urban street trees to reduce heat stress (Urban Climate, 2026; en inglés)")}</a> · <a href="https://www.epa.gov/heatislands/using-trees-and-vegetation-reduce-heat-islands" target="_blank" rel="noopener">{t("EPA, Using Trees and Vegetation to Reduce Heat Islands", "EPA, Using Trees and Vegetation to Reduce Heat Islands (en inglés)")}</a></p>
    <div class="note"><b>{t("Cool roofs.", "Techos fríos.")}</b> {t("A cool roof reflects more sunlight and absorbs less heat than a dark one. EPA reports that cool roofs can lower the highest indoor temperature of buildings without air conditioning by 1.2 to 3.3 °C.", "Un techo frío refleja más luz del sol y absorbe menos calor que uno oscuro. La EPA informa que los techos fríos pueden bajar entre 1.2 y 3.3 °C la temperatura más alta dentro de los edificios sin aire acondicionado.")}</div>
    <p class="uh-cite"><a href="https://www.epa.gov/heatislands/using-cool-roofs-reduce-heat-islands" target="_blank" rel="noopener">{t("EPA, Using Cool Roofs to Reduce Heat Islands", "EPA, Using Cool Roofs to Reduce Heat Islands (en inglés)")}</a></p>
    <div class="note"><b>{t("Pavements, green roofs and the shape of streets.", "Pavimentos, techos verdes y la forma de las calles.")}</b> {t("EPA lists cool pavements and green roofs among the strategies cities use, and names buildings close together that block the wind as one of the causes. The 2004 NASA report above notes that the general climate of Puerto Rico is dominated by the easterly trade winds.", "La EPA incluye los pavimentos fríos y los techos verdes entre las estrategias que usan las ciudades, y nombra los edificios muy juntos que bloquean el viento como una de las causas. El informe de 2004 para la NASA de arriba señala que el clima general de Puerto Rico lo dominan los vientos alisios del este.")}</div>
    <div class="note"><b>{t("Planning with the community.", "Planificar con la comunidad.")}</b> {t("The United Nations Environment Programme's handbook for cities, Beating the Heat (2021), gathers cooling strategies and case studies from cities around the world and gives guidelines for a citywide cooling action plan.", "El manual para ciudades del Programa de las Naciones Unidas para el Medio Ambiente, Beating the Heat (2021), reúne estrategias para refrescar y casos de ciudades de todo el mundo, y da guías para un plan de acción de enfriamiento para toda una ciudad.")}</div>
    <p class="uh-cite"><a href="https://wedocs.unep.org/handle/20.500.11822/37313" target="_blank" rel="noopener">{t("UNEP, Beating the Heat: A Sustainable Cooling Handbook for Cities (2021)", "PNUMA, Beating the Heat: A Sustainable Cooling Handbook for Cities (2021; en inglés)")}</a></p>

    <h3 class="uh-h3">{t("Use this page to see where the facts line up", "Use esta página para ver dónde coinciden los hechos")}</h3>
    <ol class="uh-steps">
      <li>{t("At the top, pick Land: surface temperature, summer mornings, and People: households of one person living alone. Pick your municipio. The dots above and to the right of both dashed lines are barrios above the median on both.", "Arriba, escoja Terreno: temperatura de la superficie, mañanas de verano, y Personas: hogares de una persona que vive sola. Escoja su municipio. Los puntos por encima y a la derecha de las dos líneas discontinuas son barrios por encima de la mediana en ambas.")}</li>
      <li>{t("Change Land to vegetation greenness. The barrios to the left of the median line are the least green of the ones shown.", "Cambie Terreno a verdor de la vegetación. Los barrios a la izquierda de la línea de la mediana son los menos verdes de los que se muestran.")}</li>
      <li>{t("Change Land to the night temperature to see which barrios stay warm after dark.", "Cambie Terreno a la temperatura de la noche para ver qué barrios se mantienen cálidos después de que oscurece.")}</li>
      <li>{t("Open the map or the 3D view with the surface heat layer to see which streets and blocks inside a barrio are hottest.", "Abra el mapa o la vista 3D con la capa de calor de la superficie para ver qué calles y manzanas dentro de un barrio son las más calientes.")}</li>
    </ol>
    <p class="uh-links"><a href="3d.html#c=18.4200,-66.0700,14&amp;b=-30&amp;p=65&amp;l=muni,surfheat,terrain,buildings"><span class="ms-icon" aria-hidden="true">view_in_ar</span>{t("Surface heat under the buildings, in the 3D view", "El calor de la superficie debajo de los edificios, en la vista 3D")}</a></p>
    <div class="note caution"><b>{t("Other places, other times.", "Otros lugares, otros tiempos.")}</b> {t("The studies above were done in other cities and climates, or in San Juan many years ago; what works, and how much, depends on the place. The figures are as each source reports them.", "Los estudios de arriba se hicieron en otras ciudades y climas, o en San Juan hace muchos años; lo que funciona, y cuánto, depende del lugar. Las cifras son como las informa cada fuente.")}</div>
  </section>

  <section class="block" id="method">
    <h2><span class="ms-icon" aria-hidden="true">info</span>{t("Method", "Método")}</h2>
    <div class="note"><b>{t("The land.", "El terreno.")}</b> {t(f"The median surface temperature of each barrio's land on clear summer mornings (Landsat 8 and 9, about 10:30) and on clear summer nights (ECOSTRESS, 21:00 to 06:00), and its median vegetation greenness (Sentinel-2 NDVI), all from June to September of {y0} to {y1}, on one 60 m grid. They are the barrio values of the map's datasets (Home › Environment and climate), groups Surface heat, Night surface heat and Vegetation.", f"La temperatura mediana de la superficie del terreno de cada barrio en mañanas despejadas de verano (Landsat 8 y 9, a eso de las 10:30) y en noches despejadas de verano (ECOSTRESS, de 21:00 a 06:00), y su verdor mediano de la vegetación (NDVI de Sentinel-2), todo de junio a septiembre de {y0} a {y1}, en una cuadrícula de 60 m. Son los valores por barrio de los conjuntos de datos del mapa (Explorar › Ambiente y clima), grupos Calor de superficie, Calor de superficie de noche y Vegetación.")}</div>
    <div class="note"><b>{t("The people.", "Las personas.")}</b> {t(f"Residents 65 and older, residents below the poverty level, households without a vehicle and households of one person living alone: the Census Bureau's American Community Survey, 5-year estimates {acs}, by barrio, with the margins of error the Bureau publishes (90% confidence). Drive time to a general hospital: the observatory's estimate from each barrio's population-weighted point along the road network. Residents: the 2020 Census. The Census Bureau's Community Resilience Estimates have no barrio values, so they are not on this page.", f"Residentes de 65 años o más, residentes bajo el nivel de pobreza, hogares sin vehículo y hogares de una persona que vive sola: la Encuesta sobre la Comunidad del Negociado del Censo, estimados de 5 años {acs}, por barrio, con los márgenes de error que publica el Negociado (90 % de confianza). Tiempo en carro a un hospital general: el estimado del observatorio desde el punto ponderado por población de cada barrio por la red de carreteras. Residentes: el Censo 2020. Las Estimaciones de Resiliencia Comunitaria del Negociado del Censo no tienen valores por barrio, así que no están en esta página.")}</div>
    <div class="note"><b>{t("Margins of error.", "Márgenes de error.")}</b> {t("A survey estimate whose margin of error is above 30% of the estimate is shown in italics in the table and as a hollow dot in the chart, the rule the whole observatory uses. The rank correlations include every barrio with both values; they describe the order of the published estimates, not a test.", "Un estimado de la encuesta cuyo margen de error es mayor que el 30 % del estimado aparece en cursiva en la tabla y como un punto hueco en el gráfico, la regla que usa todo el observatorio. Las correlaciones de rangos incluyen todos los barrios con ambos valores; describen el orden de los estimados publicados, no son una prueba.")}</div>
    <div class="note"><b>{t("What the page does not do.", "Lo que la página no hace.")}</b> {t("It does not combine the measures into an index, rank barrios as better or worse, say who is at risk, or measure the heat people feel. Elevation and the coast shape the land's temperature: the Cordillera is cooler, and the sea keeps the coast warm at night.", "No combina las medidas en un índice, no clasifica los barrios como mejores o peores, no dice quién está en riesgo ni mide el calor que sienten las personas. La altura y la costa moldean la temperatura del terreno: la Cordillera es más fresca y el mar mantiene la costa cálida de noche.")}</div>
  </section>

  <section class="block" id="sources">
    <h2><span class="ms-icon" aria-hidden="true">menu_book</span>{t("Sources and licenses", "Fuentes y licencias")}</h2>
    <div class="note"><b>{t("USGS Landsat 8 and 9.", "Landsat 8 y 9 del USGS.")}</b> {t("Collection 2 Level-2 surface temperature, read from Microsoft Planetary Computer. US Government work, public domain; courtesy of the U.S. Geological Survey.", "Temperatura de la superficie de la Colección 2, Nivel 2, leída de Microsoft Planetary Computer. Obra del Gobierno de EE. UU., dominio público; cortesía del U.S. Geological Survey.")}</div>
    <div class="note"><b>{t("NASA ECOSTRESS.", "ECOSTRESS de NASA.")}</b> {t("Tiled Land Surface Temperature and Emissivity, version 2 (Hook and Hulley 2022, doi 10.5067/ECOSTRESS/ECO_L2T_LSTE.002), from the LP DAAC. NASA data: no restrictions on use, with citation.", "Temperatura y emisividad de la superficie terrestre en mosaicos, versión 2 (Hook y Hulley 2022, doi 10.5067/ECOSTRESS/ECO_L2T_LSTE.002), del LP DAAC. Datos de NASA: sin restricciones de uso, con cita.")}</div>
    <div class="note"><b>{t("Copernicus Sentinel-2.", "Sentinel-2 de Copernicus.")}</b> {t("Level-2A surface reflectance, Collection 1, from Earth Search on AWS. Contains modified Copernicus Sentinel data.", "Reflectancia de la superficie del Nivel 2A, Colección 1, de Earth Search en AWS. Contiene datos modificados de Copernicus Sentinel.")}</div>
    <div class="note"><b>{t("U.S. Census Bureau.", "Negociado del Censo de EE. UU.")}</b> {t("American Community Survey 5-year estimates and the 2020 Census, by county subdivision (barrio). US Government work.", "Estimados de 5 años de la Encuesta sobre la Comunidad y el Censo 2020, por subdivisión de condado (barrio). Obra del Gobierno de EE. UU.")}</div>
    <div class="note"><b>{t("Data and method.", "Datos y método.")}</b> {t("The data file is data/urban_heat.json (urban_heat.py), built only from the observatory's published barrio files; the methods of the land measures are in docs/heat.md, docs/ecostress.md and docs/vegetation.md of the project repository.", "El archivo de datos es data/urban_heat.json (urban_heat.py), construido solo con los archivos por barrio que publica el observatorio; los métodos de las medidas del terreno están en docs/heat.md, docs/ecostress.md y docs/vegetation.md del repositorio del proyecto.")}</div>
    <div class="note"><b>{t("How to cite this page.", "Cómo citar esta página.")}</b> {t("Foundation for Puerto Rico, Knowledge Area: Urban heat, PR Data Observatory, Snapshot 2026-10 (draft). Data: USGS (Landsat), NASA (ECOSTRESS), Copernicus (Sentinel-2) and U.S. Census Bureau.", "Foundation for Puerto Rico, Área de conocimiento: Calor urbano, Observatorio de Datos de PR, Snapshot 2026-10 (borrador). Datos: USGS (Landsat), NASA (ECOSTRESS), Copernicus (Sentinel-2) y Negociado del Censo de EE. UU.")}</div>
  </section>
</main>
<script src="js/core/knowledge.js?v=35"></script>
<script>Core.knowledge.render(); I18N.apply();</script>
<script src="js/common.js?v=20"></script>
<script src="js/urban_heat.js?v=1"></script>
<script src="js/chatboot.js?v=48"></script>
</body>
</html>
"""
    for m in re.finditer(r"<b>([^<]*)</b> ([^<]*)</(?:div|p)>", page):
        lead, body = " ".join(html.unescape(m.group(1)).split()), " ".join(html.unescape(m.group(2)).split())
        key = " ".join(f"<b>{m.group(1)}</b> {m.group(2)}".split())
        ES[key] = f"<b>{html.escape(ES[lead], quote=False)}</b> {html.escape(ES[body], quote=False)}"
        ES.pop(lead, None)
        ES.pop(body, None)
    (ROOT / "site" / "urban-heat.html").write_text(page, encoding="utf-8", newline="\n")
    es = {"_about": "The Urban heat page of the Knowledge Area (urban-heat.html) and site/js/urban_heat.js. Written by docs/analysis/urban-heat-2026-11/make_page.py from its (English, Spanish) pairs: edit them there, not here."}
    es.update(ES)
    (ROOT / "i18n_src" / "es" / "urban_heat.json").write_text(json.dumps(es, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(f"wrote site/urban-heat.html and i18n_src/es/urban_heat.json ({len(ES)} strings)")


if __name__ == "__main__":
    build()
