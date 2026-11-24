"""Writes the Knowledge Area page "Energy in Puerto Rico" (site/energy.html) and its Spanish (i18n_src/es/energy.json).

  python docs/analysis/energy-2026-11/make_page.py   read site/data/energy.json (python energy_series.py makes it); write the page and the Spanish of the page
                                                     and of site/js/energy_page.js. Then run python i18n.py.

The page follows the site's language rule (docs/i18n.md) and the pattern of the Broadband gaps page: every string is written once, as an (English, Spanish)
pair, and every figure in the static text is read from the data file. HANDOFF decision 104, step 3. Facts only: the page reports what LUMA, EIA and the law
say, with no judgement of the utility, the operators or the policy. Prepared with Claude (AI) for FPR, 2026-11-14.
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


JS = [   # the strings of site/js/energy_page.js
    ("Oil", "Petróleo"), ("Natural gas", "Gas natural"), ("Coal", "Carbón"), ("Hydroelectric", "Hidroeléctrica"), ("Solar plants", "Plantas solares"), ("Wind", "Eólica"),
    ("Landfill gas", "Gas de vertedero"), ("Rooftop solar sent to the grid", "Solar en techos enviada a la red"),
    ("The data could not be loaded ({error}). Check your connection and reload.", "No se pudieron cargar los datos ({error}). Verifique su conexión y vuelva a cargar la página."),
    ("Power plants of 1 MW or more", "Plantas de energía de 1 MW o más"), ("{v} MW", "{v} MW"), ("{r} MW renewable; EIA, {m}", "{r} MW renovables; EIA, {m}"),
    ("{r} MW renewable; EIA, {m}. Another {b} MW of solar is built, not yet in commercial operation", "{r} MW renovables; EIA, {m}. Otros {b} MW solares están construidos, aún sin operación comercial"),
    ("Rooftop solar", "Solar en techos"), ("{n} customers; LUMA, {m}", "{n} clientes; LUMA, {m}"),
    ("Home and business batteries", "Baterías en hogares y negocios"), ("installations; LUMA, {m}", "instalaciones; LUMA, {m}"),
    ("Renewable share of production, {y}", "Parte renovable de la producción, {y}"), ("{p} from the plants alone", "{p} solo de las plantas"),
    ("Residential price", "Precio residencial"), ("{v} ¢/kWh", "{v} ¢/kWh"), ("United States {u} ¢/kWh; EIA, {m}", "Estados Unidos {u} ¢/kWh; EIA, {m}"),
    ("Stacked bar chart: Puerto Rico's electricity production by source, every year from {a} to {b}. In {b}, renewables were {r} of production with rooftop solar sent to the grid, {p} from the plants alone.",
     "Gráfico de barras apiladas: la producción de electricidad de Puerto Rico por fuente, cada año de {a} a {b}. En {b}, las renovables fueron el {r} de la producción con la solar en techos enviada a la red, y el {p} solo de las plantas."),
    ("LUMA counted {a} of the electricity it distributed in {y} toward the renewable portfolio standard, on average over the year. Act 17-2019 set 40% for 2025; Act 1-2025 removed that target and kept 100% for 2050.",
     "LUMA contó el {a} de la electricidad que distribuyó en {y} para la cartera de energía renovable, en promedio durante el año. La Ley 17-2019 fijó un 40 % para 2025; la Ley 1-2025 eliminó esa meta y mantuvo el 100 % para 2050."),
    ("Line chart: rooftop solar capacity registered with the utility, every month from {a} to {b}, reaching {v} MW, against the {r} MW of renewable power plants.",
     "Gráfico de líneas: la capacidad solar en techos registrada con la empresa eléctrica, cada mes de {a} a {b}, hasta llegar a {v} MW, frente a los {r} MW de las plantas de energía renovable."),
    ("Rooftop solar, MW (LUMA)", "Solar en techos, MW (LUMA)"), ("Renewable power plants: {v} MW (EIA, {m})", "Plantas de energía renovable: {v} MW (EIA, {m})"),
    ("Rooftop solar grew from {a} MW in {ma} to {b} MW in {mb}, {x} times the capacity of the renewable power plants. Batteries: {n} installations in {mn}, {f} in {mf}.",
     "La solar en techos pasó de {a} MW en {ma} a {b} MW en {mb}, {x} veces la capacidad de las plantas de energía renovable. Baterías: {n} instalaciones en {mn}, {f} en {mf}."),
    ("Puerto Rico", "Puerto Rico"),
    ("Batteries in {b}; electricity sales from {s0} to {s1}. Select a heading to sort.", "Baterías en {b}; ventas de electricidad de {s0} a {s1}. Seleccione un encabezado para ordenar."),
    ("Municipio", "Municipio"), ("Batteries", "Baterías"), ("Per 100 housing units", "Por cada 100 unidades de vivienda"), ("Stored, MWh", "Almacenamiento, MWh"),
    ("Sales, GWh in 12 months", "Ventas, GWh en 12 meses"), ("MWh per resident", "MWh por residente"), ("Smart meters", "Contadores inteligentes"),
    ("Rooftop solar by LUMA commercial district, {m}. LUMA publishes no map of its districts; each is named after its main town.",
     "Solar en techos por distrito comercial de LUMA, {m}. LUMA no publica un mapa de sus distritos; cada uno lleva el nombre de su pueblo principal."),
    ("District", "Distrito"), ("Rooftop solar, MW", "Solar en techos, MW"), ("Installations", "Instalaciones"), ("kW per installation", "kW por instalación"),
    ("Line chart: minutes without power per customer each month from transmission and distribution outages (SAIDI), {a} to {b}. The last 12 months add up to {v} minutes.",
     "Gráfico de líneas: minutos sin servicio por cliente cada mes por interrupciones de transmisión y distribución (SAIDI), de {a} a {b}. Los últimos 12 meses suman {v} minutos."),
    ("SAIDI, transmission and distribution (minutes)", "SAIDI, transmisión y distribución (minutos)"), ("Of it, distribution", "De ello, distribución"),
    ("In the 12 months to {m}, the average customer was without power {v} minutes ({h} hours) from transmission and distribution outages. Counting every event, generation shortfalls included, EIA's figure for 2025 is {a} minutes ({ah} hours), {f} interruptions per customer.",
     "En los 12 meses hasta {m}, el cliente promedio estuvo sin servicio {v} minutos ({h} horas) por interrupciones de transmisión y distribución. Contando todos los eventos, incluidas las faltas de generación, la cifra de la EIA para 2025 es de {a} minutos ({ah} horas) y {f} interrupciones por cliente."),
    ("SAIDI by LUMA technical district, minutes in the 12 months to {m}", "SAIDI por distrito técnico de LUMA, minutos en los 12 meses hasta {m}"),
    ("Minutes without power per customer", "Minutos sin servicio por cliente"),
    ("Line chart: average residential price of electricity in Puerto Rico and the United States, every month from {a} to {b}: {pr} and {us} cents per kWh in the last month.",
     "Gráfico de líneas: el precio residencial promedio de la electricidad en Puerto Rico y en Estados Unidos, cada mes de {a} a {b}: {pr} y {us} centavos por kWh en el último mes."),
    ("Puerto Rico (the utility)", "Puerto Rico (la empresa eléctrica)"), ("United States", "Estados Unidos"),
    ("Transmission lines inside FEMA flood hazard areas, as drawn on the map (simplified)", "Líneas de transmisión dentro de las zonas de riesgo de inundación de FEMA, como se dibujan en el mapa (simplificadas)"),
    ("Voltage", "Voltaje"), ("Km mapped", "Km mapeados"), ("Km in the 1% flood area", "Km en la zona de inundación del 1 %"), ("Share", "Proporción"), ("Km in coastal V zones", "Km en zonas costeras V"),
    ("{n} of the {all} plants with an operating generator ({mw} of {allmw} MW) stand inside the 1% flood area. The largest:",
     "{n} de las {all} plantas con un generador en operación ({mw} de {allmw} MW) están dentro de la zona de inundación del 1 %. Las más grandes:"),
    ("{name}, {muni}: {mw} MW", "{name}, {muni}: {mw} MW"),
]
for en, es in JS:
    t(en, es)


def num(v, d=0):
    return f"{v:,.{d}f}"


MES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
MON = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]


def month(m, es=False):
    y, k = m.split("-")
    return f"{MES[int(k) - 1]} de {y}" if es else f"{MON[int(k) - 1]} {y}"


def build():
    D = json.loads((ROOT / "site" / "data" / "energy.json").read_text(encoding="utf-8"))
    A, c, s, x = D["annual_gwh"], D["capacity"], D["series"], D["exposure"]
    ly = sorted(A)[-1]
    tot = sum(A[ly].values())
    ren = sum(A[ly][k] for k in ("hydro", "solar", "wind", "landfill"))
    sh_all, sh_pl, sh_dg = round((ren + A[ly]["dg"]) / tot * 100, 1), round(ren / (tot - A[ly]["dg"]) * 100, 1), round(A[ly]["dg"] / tot * 100, 1)
    fossil = round((A[ly]["oil"] + A[ly]["gas"] + A[ly]["coal"]) / tot * 100, 1)
    if not sh_dg > sh_all / 2:
        raise SystemExit("make_page: rooftop exports are no longer more than half of the renewable share; rewrite the lede")
    roof, rmon = c["rooftop_mw"], c["rooftop_month"]
    times = num(roof / c["renewable_mw"], 1)
    bess = sum(D["municipios"]["bess"])
    km38 = D["lines_km"]["38"]
    heat = (ROOT / "site" / "broadband.html").read_text(encoding="utf-8")
    ver = lambda name: re.search(re.escape(name) + r"\?v=(\d+)", heat).group(1)
    icons = sorted(set(re.search(r"icon_names=([a-z0-9_,]+)", heat).group(1).split(",")) | {"school", "bolt", "solar_power", "battery_charging_full", "eco", "payments", "flood", "show_chart",
                                                                                               "table_view", "info", "menu_book", "location_city", "map"})
    mixes = ", ".join
    page = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{t("Knowledge Area · Energy in Puerto Rico", "Área de conocimiento · Energía en Puerto Rico")}</title>
<meta name="description" content="{t("Where Puerto Rico's electricity comes from, how much of it is renewable, the rooftop solar and batteries of homes and businesses by municipio, reliability, price and the grid's exposure to floods, from LUMA's filings with the Energy Bureau, EIA and FEMA.", "De dónde viene la electricidad de Puerto Rico, cuánta es renovable, la energía solar en techos y las baterías de hogares y negocios por municipio, la confiabilidad, el precio y la exposición de la red a las inundaciones, según los informes de LUMA al Negociado de Energía, la EIA y FEMA.")}">
<meta name="robots" content="noindex, nofollow">
<meta name="theme-color" content="#FFFFFF">
<link rel="icon" href="img/fpr-mark.png">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Material+Symbols+Rounded:opsz,wght,FILL,GRAD@24,400,1,0&icon_names={",".join(icons)}&display=block">
<link rel="stylesheet" href="css/twin.css?v={ver("css/twin.css")}">
<link rel="stylesheet" href="css/housing.css?v={ver("css/housing.css")}">
<link rel="stylesheet" href="css/public_money.css?v={ver("css/public_money.css")}">
<link rel="stylesheet" href="css/broadband.css?v={ver("css/broadband.css")}">
<link rel="stylesheet" href="css/energy.css?v=1">
<link rel="stylesheet" href="css/chat.css?v={ver("css/chat.css")}">
<script src="js/i18n.js?v={ver("js/i18n.js")}" data-page="energy"></script>
</head>
<body class="research">
<a class="skip" href="#now">{t("Skip to the content", "Ir al contenido")}</a>
<header class="topbar">
  <a class="logo" href="index.html" title="{t("PR Data Observatory home", "Inicio del Observatorio de Datos de PR")}"><img src="img/fpr-logo.png" alt="{t("Foundation for Puerto Rico. PR Data Observatory home", "Foundation for Puerto Rico. Inicio del Observatorio de Datos de PR")}"></a>
  <div class="brand"><b>{t("Knowledge Area · Energy in Puerto Rico", "Área de conocimiento · Energía en Puerto Rico")}</b><span>{t("Plants, rooftop solar, batteries, reliability and price", "Plantas, solar en techos, baterías, confiabilidad y precio")}</span></div>
  <div class="spacer"></div>
  <nav class="views" aria-label="{t("Views", "Vistas")}">
    <a class="btn" href="index.html#l=powerlines,plants"><span class="ms-icon" aria-hidden="true">map</span><span class="lbl">{t("Map", "Mapa")}</span></a>
    <a class="btn" href="3d.html" title="{t("Immersive 3D + time view", "Vista inmersiva en 3D y tiempo")}"><span class="ms-icon" aria-hidden="true">view_in_ar</span><span class="lbl">{t("3D + Time", "3D + Tiempo")}</span></a>
    <a class="btn" href="knowledge.html" aria-current="page" title="{t("Knowledge: FPR studies, analyses and tools", "Conocimiento: estudios, análisis y herramientas de FPR")}"><span class="ms-icon" aria-hidden="true">lightbulb</span><span class="lbl">{t("Knowledge", "Conocimiento")}</span></a>
    <a class="btn" href="dictionary.html" title="{t("Data dictionary: meanings, sources, licenses, how to cite", "Diccionario de datos: significados, fuentes, licencias y cómo citar")}"><span class="ms-icon" aria-hidden="true">menu_book</span><span class="lbl">{t("Dictionary", "Diccionario")}</span></a>
    <a class="btn" href="learn.html" title="{t("Learn: short lessons about maps and spatial analysis", "Aprende: lecciones cortas sobre mapas y análisis espacial")}"><span class="ms-icon" aria-hidden="true">school</span><span class="lbl">{t("Learn", "Aprende")}</span></a>
  </nav>
</header>

<nav class="toc" id="toc" aria-label="{t("On this page", "En esta página")}">
  <span class="ka-tabs" role="group" aria-label="{t("Knowledge Area", "Área de conocimiento")}" data-ka="energy"></span><span class="ka-sep" aria-hidden="true"></span>
  <a href="#now">{t("Now", "Ahora")}</a><a href="#mix">{t("Sources", "Fuentes")}</a><a href="#rooftop">{t("Rooftop solar", "Solar en techos")}</a><a href="#municipios">{t("Municipios", "Municipios")}</a><a href="#reliability">{t("Reliability", "Confiabilidad")}</a><a href="#price">{t("Price", "Precio")}</a><a href="#hazards">{t("Floods", "Inundaciones")}</a><a href="#method">{t("Method", "Método")}</a><a href="#sources">{t("Data sources", "Fuentes de datos")}</a>
</nav>

<main class="page">
  <div class="note caution review-note" role="note" data-ka-note></div>

  <section class="hero" id="now">
    <div class="eyebrow">{t("Knowledge Area · Energy", "Área de conocimiento · Energía")}</div>
    <h1>{t("Energy in Puerto Rico", "Energía en Puerto Rico")}</h1>
    <p class="lede">{t(f"In {ly}, {fossil}% of Puerto Rico's electricity came from oil, natural gas and coal. Renewables were {sh_all}% of production, and more than half of that was rooftop solar sent to the grid ({sh_dg}%); the renewable plants alone gave {sh_pl}%. Rooftop systems now add up to {num(roof)} MW, {times} times the {num(c['renewable_mw'])} MW of renewable power plants, and homes and businesses have {num(bess)} batteries.",
                          f"En {ly}, el {fossil} % de la electricidad de Puerto Rico vino del petróleo, el gas natural y el carbón. Las renovables fueron el {sh_all} % de la producción, y más de la mitad fue solar en techos enviada a la red ({sh_dg} %); las plantas renovables solas aportaron el {sh_pl} %. Los sistemas en techos ya suman {num(roof)} MW, {times} veces los {num(c['renewable_mw'])} MW de las plantas de energía renovable, y los hogares y negocios tienen {num(bess)} baterías.")}</p>
    <div id="enNow" aria-live="polite"></div>
    <div class="note caution"><b>{t("Read with care.", "Lea con cuidado.")}</b> {t("Rooftop solar that a home uses itself is not counted as production anywhere: the production figures include only what rooftop systems send to the grid. Capacity (MW) is what equipment is built to produce, not what it produces.", "La energía solar en techos que un hogar usa por sí mismo no se cuenta como producción en ninguna parte: las cifras de producción incluyen solo lo que los sistemas en techos envían a la red. La capacidad (MW) es lo que el equipo está hecho para producir, no lo que produce.")}</div>
  </section>

  <section class="block" id="mix">
    <h2><span class="ms-icon" aria-hidden="true">show_chart</span>{t("1 · Where the electricity comes from", "1 · De dónde viene la electricidad")}</h2>
    <p class="pm-p">{t(f"The share of each source in the electricity produced every full year since {sorted(A)[0]}, as LUMA reports it to the Energy Bureau: the utility's and its contractors' plants, plus what rooftop systems send to the grid. Hover over or tap a bar for the figures.", f"La parte de cada fuente en la electricidad producida cada año completo desde {sorted(A)[0]}, como LUMA lo informa al Negociado de Energía: las plantas de la empresa eléctrica y de sus contratistas, más lo que los sistemas en techos envían a la red. Pase el cursor sobre una barra o tóquela para ver las cifras.")}</p>
    <div class="card" id="enMix" data-t="skip"></div>
    <p class="pm-small" id="enMixNote" data-t="skip"></p>
  </section>

  <section class="block" id="rooftop">
    <h2><span class="ms-icon" aria-hidden="true">solar_power</span>{t("2 · Rooftop solar and batteries", "2 · Solar en techos y baterías")}</h2>
    <p class="pm-p">{t("The capacity of the solar systems registered for net metering, every month since they began, against the renewable power plants in EIA's inventory. Most of these systems now come with a battery.", "La capacidad de los sistemas solares registrados en medición neta, cada mes desde que comenzaron, frente a las plantas de energía renovable del inventario de la EIA. La mayoría de estos sistemas ahora vienen con una batería.")}</p>
    <div class="card" id="enRooftop" data-t="skip"></div>
    <p class="pm-small" id="enRooftopNote" data-t="skip"></p>
  </section>

  <section class="block" id="municipios">
    <h2><span class="ms-icon" aria-hidden="true">location_city</span>{t("3 · By municipio and district", "3 · Por municipio y distrito")}</h2>
    <p class="pm-p">{t("Batteries, electricity use and smart meters by municipio, from LUMA's monthly metrics. Batteries per 100 housing units use the 2020 Census; electricity sales cover homes, businesses, industry and government, so a municipio with large plants or malls uses more per resident. Smart meters are being installed: LUMA reports no share yet where the column is empty.", "Baterías, consumo de electricidad y contadores inteligentes por municipio, según las métricas mensuales de LUMA. Las baterías por cada 100 unidades de vivienda usan el Censo 2020; las ventas de electricidad incluyen hogares, comercios, industria y gobierno, así que un municipio con grandes plantas o centros comerciales consume más por residente. Los contadores inteligentes se están instalando: LUMA aún no informa una parte donde la columna está vacía.")}</p>
    <div class="card pm-tablebox bb-tablebox" id="enMunis" data-t="skip"></div>
    <h3 class="bb-h3">{t("Rooftop solar by LUMA district", "Solar en techos por distrito de LUMA")}</h3>
    <p class="pm-p">{t("LUMA reports rooftop solar by its 34 commercial districts, not by municipio.", "LUMA informa la solar en techos por sus 34 distritos comerciales, no por municipio.")}</p>
    <div class="card pm-tablebox bb-tablebox" id="enDistricts" data-t="skip"></div>
  </section>

  <section class="block" id="reliability">
    <h2><span class="ms-icon" aria-hidden="true">bolt</span>{t("4 · Reliability", "4 · Confiabilidad")}</h2>
    <p class="pm-p">{t("SAIDI is the average number of minutes each customer is without power. LUMA's monthly figure counts outages of the transmission and distribution system it runs; outages caused by a lack of generation are not in it.", "El SAIDI es el promedio de minutos que cada cliente está sin servicio. La cifra mensual de LUMA cuenta las interrupciones del sistema de transmisión y distribución que opera; las interrupciones causadas por falta de generación no están incluidas.")}</p>
    <div class="card" id="enSaidi" data-t="skip"></div>
    <p class="pm-small" id="enSaidiNote" data-t="skip"></p>
    <div class="card pm-tablebox bb-tablebox" id="enSaidiD" data-t="skip"></div>
  </section>

  <section class="block" id="price">
    <h2><span class="ms-icon" aria-hidden="true">payments</span>{t("5 · Price", "5 · Precio")}</h2>
    <p class="pm-p">{t("The average residential price: what residential customers paid in the month divided by the electricity they bought, from what utilities report to EIA. It includes the fuel charge, which moves with oil and gas prices.", "El precio residencial promedio: lo que pagaron los clientes residenciales en el mes dividido entre la electricidad que compraron, según lo que las empresas eléctricas informan a la EIA. Incluye el cargo por combustible, que varía con los precios del petróleo y el gas.")}</p>
    <div class="card" id="enPrice" data-t="skip"></div>
  </section>

  <section class="block" id="hazards">
    <h2><span class="ms-icon" aria-hidden="true">flood</span>{t("6 · The grid and floods", "6 · La red y las inundaciones")}</h2>
    <p class="pm-p">{t(f"The transmission lines of the map (OpenStreetMap, simplified) and the power plants (EIA) inside FEMA's 1% annual chance flood area and its coastal high-hazard V zones. The 38 kV network is about half mapped ({num(km38)} km), so its figures are a lower bound.", f"Las líneas de transmisión del mapa (OpenStreetMap, simplificadas) y las plantas de energía (EIA) dentro de la zona de 1 % de probabilidad anual de inundación de FEMA y de sus zonas costeras V de alto riesgo. La red de 38 kV está mapeada a medias ({num(km38)} km), así que sus cifras son un mínimo.")}</p>
    <div class="card pm-tablebox bb-tablebox" id="enHazLines" data-t="skip"></div>
    <div id="enHazPlants" data-t="skip"></div>
    <p class="pm-small"><a href="index.html#l=powerlines,plants,flood">{t("See the lines, plants and flood areas on the map", "Ver las líneas, las plantas y las zonas inundables en el mapa")}</a></p>
  </section>

  <section class="block" id="method">
    <h2><span class="ms-icon" aria-hidden="true">info</span>{t("Method", "Método")}</h2>
    <div class="note"><b>{t("Production by source.", "Producción por fuente.")}</b> {t("LUMA's monthly net production of the utility's and its contractors' plants by fuel, plus the energy rooftop systems export to the grid. Solar, wind and landfill gas are read from the file's contracted renewable production; the file's second set of columns for these fuels holds other quantities before October 2017. A year is shown when it has its twelve months.", "La producción neta mensual de LUMA de las plantas de la empresa eléctrica y de sus contratistas por combustible, más la energía que los sistemas en techos exportan a la red. La solar, la eólica y el gas de vertedero se leen de la producción renovable contratada del archivo; el segundo grupo de columnas del archivo para esas fuentes contiene otras cantidades antes de octubre de 2017. Un año se muestra cuando tiene sus doce meses.")}</div>
    <div class="note"><b>{t("Rooftop solar and batteries.", "Solar en techos y baterías.")}</b> {t("The capacity and the customers registered for net metering in LUMA's distributed generation filing; batteries by municipio from its monthly metrics, where LUMA splits San Juan into San Juan, Río Piedras and Santurce, added back together here.", "La capacidad y los clientes registrados en medición neta en el informe de generación distribuida de LUMA; las baterías por municipio de sus métricas mensuales, donde LUMA divide San Juan en San Juan, Río Piedras y Santurce, que aquí se suman.")}</div>
    <div class="note"><b>{t("Floods.", "Inundaciones.")}</b> {t("The lines and plant points are intersected with the observatory's FEMA flood layer (zones in the 1% annual chance Special Flood Hazard Area; V zones are its coastal high-hazard part). Sea level rise and landslides are not counted yet.", "Las líneas y los puntos de las plantas se cruzan con la capa de inundaciones de FEMA del observatorio (zonas del Área Especial de Riesgo de Inundación de 1 % de probabilidad anual; las zonas V son su parte costera de alto riesgo). El aumento del nivel del mar y los deslizamientos aún no se cuentan.")}</div>
    <div class="note"><b>{t("What the page does not say.", "Lo que la página no dice.")}</b> {t("It does not judge the utility, the operators or the policy, and it does not name any customer, address or installation. The full method and the code are in docs/energy.md of the project repository; each figure has an entry in the data dictionary.", "No juzga a la empresa eléctrica, a los operadores ni a la política pública, y no nombra a ningún cliente, dirección ni instalación. El método completo y el código están en docs/energy.md del repositorio del proyecto; cada cifra tiene una entrada en el diccionario de datos.")}</div>
  </section>

  <section class="block" id="sources">
    <h2><span class="ms-icon" aria-hidden="true">menu_book</span>{t("Data sources and licenses", "Fuentes de datos y licencias")}</h2>
    <div class="note"><b>{t("LUMA Energy, filed with the Puerto Rico Energy Bureau.", "LUMA Energy, presentado ante el Negociado de Energía de Puerto Rico.")}</b> {t(f"Distributed generation data, Exhibit 2 (case NEPR-MI-2019-0016), monthly from 2010 to {month(s['months'][-1])}; monthly metrics workbook (case NEPR-MI-2019-0007), monthly from June 2021 to {month(D['municipios']['as_of'])}. Public filings; no license is stated.", f"Datos de generación distribuida, Anejo 2 (caso NEPR-MI-2019-0016), mensual desde 2010 hasta {month(s['months'][-1], True)}; libro de métricas mensuales (caso NEPR-MI-2019-0007), mensual desde junio de 2021 hasta {month(D['municipios']['as_of'], True)}. Documentos públicos; no indican licencia.")}</div>
    <div class="note"><b>{t("US Energy Information Administration (EIA).", "Administración de Información Energética de EE. UU. (EIA).")}</b> {t(f"Form EIA-860M (power plants, {month(c['as_of'])}), Form EIA-861M (residential revenue and sales) and Form EIA-861 (reliability, 2025). US Government data, public domain.", f"Formulario EIA-860M (plantas de energía, {month(c['as_of'], True)}), Formulario EIA-861M (ingresos y ventas residenciales) y Formulario EIA-861 (confiabilidad, 2025). Datos del Gobierno de EE. UU., dominio público.")}</div>
    <div class="note"><b>{t("FEMA, OpenStreetMap and the Census Bureau.", "FEMA, OpenStreetMap y el Negociado del Censo.")}</b> {t("FEMA's National Flood Hazard Layer; transmission lines © OpenStreetMap contributors (ODbL); 2020 Census residents and housing units.", "La capa nacional de riesgo de inundación de FEMA; las líneas de transmisión © colaboradores de OpenStreetMap (ODbL); los residentes y las unidades de vivienda del Censo 2020.")}</div>
    <div class="note"><b>{t("Laws.", "Leyes.")}</b> {t("Act 17-2019 (Puerto Rico Energy Public Policy Act) and Act 1-2025, which removed the 2025 and 2040 renewable targets, kept 100% for 2050 and moved the end of coal to December 31, 2032.", "La Ley 17-2019 (Ley de Política Pública Energética de Puerto Rico) y la Ley 1-2025, que eliminó las metas renovables de 2025 y 2040, mantuvo el 100 % para 2050 y movió el fin del carbón al 31 de diciembre de 2032.")}</div>
    <div class="note"><b>{t("Data file.", "Archivo de datos.")}</b> {t("data/energy.json (energy_series.py), rebuilt when LUMA files new reports and EIA publishes a new month.", "data/energy.json (energy_series.py), que se reconstruye cuando LUMA presenta nuevos informes y la EIA publica un mes nuevo.")}</div>
    <div class="note"><b>{t("How to cite this page.", "Cómo citar esta página.")}</b> {t(f"Foundation for Puerto Rico, Knowledge Area: Energy in Puerto Rico, PR Data Observatory, data to {month(D['municipios']['as_of'])} (draft). Data: LUMA Energy filings with the Puerto Rico Energy Bureau; US EIA; FEMA; OpenStreetMap contributors.", f"Foundation for Puerto Rico, Área de conocimiento: Energía en Puerto Rico, Observatorio de Datos de PR, datos hasta {month(D['municipios']['as_of'], True)} (borrador). Datos: informes de LUMA Energy al Negociado de Energía de Puerto Rico; EIA de EE. UU.; FEMA; colaboradores de OpenStreetMap.")}</div>
  </section>
</main>
<script src="js/core/knowledge.js?v={ver("js/core/knowledge.js")}"></script>
<script>Core.knowledge.render(); I18N.apply();</script>
<script src="js/common.js?v={ver("js/common.js")}"></script>
<script src="js/energy_page.js?v=2"></script>
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
    (ROOT / "site" / "energy.html").write_text(page, encoding="utf-8", newline="\n")
    es = {"_about": "The Energy in Puerto Rico page of the Knowledge Area (energy.html) and site/js/energy_page.js. Written by docs/analysis/energy-2026-11/make_page.py from its (English, Spanish) pairs: edit them there, not here."}
    es.update(ES)
    (ROOT / "i18n_src" / "es" / "energy.json").write_text(json.dumps(es, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(f"wrote site/energy.html and i18n_src/es/energy.json ({len(ES)} strings)")


if __name__ == "__main__":
    build()
