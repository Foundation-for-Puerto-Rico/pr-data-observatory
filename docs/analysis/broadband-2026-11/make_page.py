"""Writes the Knowledge Area page "Broadband gaps" (site/broadband.html) and its Spanish (i18n_src/es/broadband.json).

  python docs/analysis/broadband-2026-11/make_page.py   read site/data/broadband_series.json and broadband_barrio.json (python broadband.py makes them); write
                                                        the page and the Spanish of the page and of site/js/broadband_page.js. Then run python i18n.py.

The page follows the site's language rule (docs/i18n.md) and the pattern of the Reservoirs page (docs/analysis/reservoirs-2026-11/make_page.py): every string
is written once, as an (English, Spanish) pair, and every figure in the static text is read from the data files. HANDOFF decision 99: where broadband
infrastructure may be needed, from the FCC's provider-reported availability (decision 94), by municipio and barrio, with no location or provider.
Prepared with Claude (AI) for FPR, 2026-11-12.
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
    ("The map could not be loaded ({error}). Check your connection and reload.", "No se pudo cargar el mapa ({error}). Verifique su conexión y vuelva a cargar la página."),
    ("points", "puntos"),
    ("Locations below 100/20 Mbps (underserved or unserved, %)", "Ubicaciones por debajo de 100/20 Mbps (subatendidas o sin servicio, %)"),
    ("Locations unserved, below 25/3 Mbps (%)", "Ubicaciones sin servicio, menos de 25/3 Mbps (%)"),
    ("Locations where fiber is available (%)", "Ubicaciones con fibra disponible (%)"),
    ("since June {y}", "desde junio de {y}"),
    ("As of June 30, {y}, Puerto Rico had {n} broadband serviceable locations.", "Al 30 de junio de {y}, Puerto Rico tenía {n} ubicaciones con servicio de banda ancha posible."),
    ("Served: 100/20 Mbps or more", "Servidas: 100/20 Mbps o más"),
    ("Underserved: 25/3 to 100/20 Mbps", "Subatendidas: de 25/3 a 100/20 Mbps"),
    ("Unserved: below 25/3 Mbps", "Sin servicio: menos de 25/3 Mbps"),
    ("Locations below 100/20 Mbps", "Ubicaciones por debajo de 100/20 Mbps"),
    ("Fiber available", "Fibra disponible"),
    ("Shade by", "Colorear por"), ("As of June 30 of", "Al 30 de junio de"),
    ("No locations", "Sin ubicaciones"),
    ("{name} ({muni}): no broadband serviceable locations", "{name} ({muni}): sin ubicaciones con servicio de banda ancha posible"),
    ("{name} ({muni}): {value} of {n} locations; {below} below 100/20 Mbps", "{name} ({muni}): {value} de {n} ubicaciones; {below} por debajo de 100/20 Mbps"),
    ("Map of the {n} barrios shaded by {measure}, as of June 30, {y}", "Mapa de los {n} barrios coloreados por {measure}, al 30 de junio de {y}"),
    ("{a} barrios in the darkest class, {none} with no locations. Hover over or tap a barrio for its figures.",
     "{a} barrios en la clase más oscura, {none} sin ubicaciones. Pase el cursor sobre un barrio o tóquelo para ver sus cifras."),
    ("Municipios as of June 30, {y}: select a heading to sort", "Municipios al 30 de junio de {y}: seleccione un encabezado para ordenar"),
    ("Municipio", "Municipio"), ("Locations", "Ubicaciones"), ("Below 100/20 Mbps", "Por debajo de 100/20 Mbps"), ("Share below 100/20", "Parte por debajo de 100/20"),
    ("Unserved", "Sin servicio"), ("Change below 100/20 since {y}", "Cambio por debajo de 100/20 desde {y}"), ("Puerto Rico", "Puerto Rico"),
    ("Rank the barrios by", "Ordenar los barrios por"), ("number of locations below 100/20 Mbps", "número de ubicaciones por debajo de 100/20 Mbps"),
    ("share below 100/20 Mbps (barrios with at least {n} locations)", "parte por debajo de 100/20 Mbps (barrios con al menos {n} ubicaciones)"),
    ("The {k} barrios first in this order, of {n}, as of June 30, {y}", "Los {k} primeros barrios en este orden, de {n}, al 30 de junio de {y}"),
    ("Barrio", "Barrio"),
    ("Share of locations below 100/20 Mbps, as of June 30 of each year; municipios from the highest share in {y}",
     "Parte de las ubicaciones por debajo de 100/20 Mbps, al 30 de junio de cada año; municipios de la parte más alta en {y} a la más baja"),
    ("Change in points", "Cambio en puntos"), ("Trend", "Tendencia"),
]
for en, es in JS:
    t(en, es)


def num(v, d=0):
    return f"{v:,.{d}f}"


def build():
    S = json.loads((ROOT / "site" / "data" / "broadband_series.json").read_text(encoding="utf-8"))
    B = json.loads((ROOT / "site" / "data" / "broadband_barrio.json").read_text(encoding="utf-8"))
    V = {v["key"]: v["years"] for v in S["vars"]}
    BV = {v["key"]: v["years"] for v in B["vars"]}
    ys = [str(y) for y in S["years"]]
    y0, y1 = ys[0], ys[-1]
    pr = len(S["geo"]["ids"]) - 1
    n1, b1, b0 = V["bb_locations"][y1][pr], V["bb_below100_n"][y1][pr], V["bb_below100_n"][y0][pr]
    f0, f1 = V["bb_fiber_pct"][y0][pr], V["bb_fiber_pct"][y1][pr]
    nb = len(B["geo"]["ids"])
    no_loc = sum(1 for x in BV["bb_locations"][y1] if not x)
    half = sum(1 for n, b in zip(BV["bb_locations"][y1], BV["bb_below100_n"][y1]) if n and b / n >= 0.5)
    muni_top = sorted(((V["bb_below100_n"][y1][i], S["geo"]["names"][i]) for i in range(pr)), reverse=True)[:3]
    top_txt_en = ", ".join(f"{m} ({num(v)})" for v, m in muni_top)
    sh_b = round(b1 / n1 * 100, 1)
    heat = (ROOT / "site" / "reservoirs.html").read_text(encoding="utf-8")
    ver = lambda name: re.search(re.escape(name) + r"\?v=(\d+)", heat).group(1)
    I18N_V = 62   # the ?v= of js/i18n.js also versions this page's Spanish bundle: raise it when the page's strings change (docs/i18n.md, rule 12)
    icons = sorted(set(re.search(r"icon_names=([a-z0-9_,]+)", heat).group(1).split(",")) | {"school", "wifi", "cable", "location_on", "signal_cellular_alt_2_bar", "signal_cellular_off", "map", "table_view", "show_chart", "info", "menu_book", "account_tree", "dark_mode", "explore", "grid_view", "light_mode"})

    page = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{t("Knowledge Area · Broadband gaps", "Área de conocimiento · Dónde falta banda ancha")}</title>
<meta name="description" content="{t("Where homes and businesses in Puerto Rico cannot get fast home internet, by barrio and municipio, from what providers report to the FCC: where broadband infrastructure may be needed.", "Dónde los hogares y negocios de Puerto Rico no pueden tener internet rápido en casa, por barrio y municipio, según lo que los proveedores informan a la FCC: dónde puede hacer falta infraestructura de banda ancha.")}">
<meta name="robots" content="noindex, nofollow">
<meta name="theme-color" content="#FFFFFF">
<link rel="icon" href="img/fpr-mark.png">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Material+Symbols+Rounded:opsz,wght,FILL,GRAD@24,400,1,0&icon_names={",".join(icons)}&display=block">
<link rel="stylesheet" href="css/twin.css?v={ver("css/twin.css")}">
<link rel="stylesheet" href="css/housing.css?v={ver("css/housing.css")}">
<link rel="stylesheet" href="css/public_money.css?v={ver("css/public_money.css")}">
<link rel="stylesheet" href="css/broadband.css?v=2">
<link rel="stylesheet" href="css/chat.css?v={ver("css/chat.css")}">
<link rel="stylesheet" href="css/ws.css?v=2">
<script src="js/i18n.js?v={max(int(ver("js/i18n.js")), I18N_V)}" data-page="broadband"></script>
</head>
<body class="research">
<a class="skip" href="#now">{t("Skip to the content", "Ir al contenido")}</a>
<header class="topbar">
  <a class="logo" href="index.html" title="{t("PR Data Observatory home", "Inicio del Observatorio de Datos de PR")}"><img src="img/fpr-logo.png" alt="{t("Foundation for Puerto Rico. PR Data Observatory home", "Foundation for Puerto Rico. Inicio del Observatorio de Datos de PR")}"></a>
  <div class="brand"><b>{t("Knowledge Area · Broadband gaps", "Área de conocimiento · Dónde falta banda ancha")}</b><span>{t("Where fast home internet is not available, barrio by barrio", "Dónde no hay internet rápido en casa, barrio por barrio")}</span></div>
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
  <span class="ka-tabs" role="group" aria-label="{t("Knowledge Area", "Área de conocimiento")}" data-ka="broadband"></span><span class="ka-sep" aria-hidden="true"></span>
  <a href="#now">{t("Now", "Ahora")}</a><a href="#gaps">{t("Map", "Mapa")}</a><a href="#ranking">{t("Ranking", "Orden")}</a><a href="#trend">{t("Over time", "En el tiempo")}</a><a href="#method">{t("Method", "Método")}</a><a href="#sources">{t("Sources", "Fuentes")}</a>
</nav>

<main class="page">
  <div class="note caution review-note" role="note" data-ka-note></div>

  <section class="hero" id="now">
    <div class="eyebrow">{t("Knowledge Area · Infrastructure", "Área de conocimiento · Infraestructura")}</div>
    <h1>{t("Where broadband is needed in Puerto Rico", "Dónde falta banda ancha en Puerto Rico")}</h1>
    <p class="lede">{t(f"As of June 30, {y1}, {num(b1)} of Puerto Rico's {num(n1)} broadband serviceable locations ({sh_b}%) could not get home internet of 100/20 Mbps or more over a reliable technology, down from {num(b0)} in June {y0}. These are the places where new or better broadband infrastructure may be needed, and the ones the federal BEAD program can fund. The municipios with the most such locations are {top_txt_en}.", f"Al 30 de junio de {y1}, {num(b1)} de las {num(n1)} ubicaciones con servicio de banda ancha posible de Puerto Rico ({sh_b} %) no podían tener internet en casa de 100/20 Mbps o más por una tecnología confiable, frente a {num(b0)} en junio de {y0}. Son los lugares donde puede hacer falta infraestructura de banda ancha nueva o mejor, y los que el programa federal BEAD puede financiar. Los municipios con más de estas ubicaciones son {top_txt_en}.")}</p>
    <div id="bbNow" aria-live="polite"></div>
    <div class="note caution"><b>{t("Read with care.", "Lea con cuidado.")}</b> {t("These figures are what internet providers report to the FCC they can install within ten business days: availability, not what households subscribe to or the speed they get. Providers' reports can be challenged and corrected, and the FCC's list of locations changes between releases.", "Estas cifras son lo que los proveedores de internet informan a la FCC que pueden instalar en diez días laborables: disponibilidad, no lo que los hogares contratan ni la velocidad que reciben. Los informes de los proveedores se pueden impugnar y corregir, y la lista de ubicaciones de la FCC cambia entre publicaciones.")}</div>
  </section>

  <section class="block" id="gaps">
    <h2><span class="ms-icon" aria-hidden="true">map</span>{t("1 · The map, barrio by barrio", "1 · El mapa, barrio por barrio")}</h2>
    <p class="pm-p">{t(f"Each of the {nb} barrios is shaded by the share of its locations that cannot get 100/20 Mbps (underserved or unserved). Switch to the share unserved (below 25/3 Mbps) or to the share where fiber is available, and pick a year. Hatched barrios have no locations. In June {y1}, {half} barrios had half or more of their locations below 100/20 Mbps.", f"Cada uno de los {nb} barrios está coloreado según la parte de sus ubicaciones que no puede tener 100/20 Mbps (subatendidas o sin servicio). Cambie a la parte sin servicio (menos de 25/3 Mbps) o a la parte con fibra disponible, y escoja un año. Los barrios rayados no tienen ubicaciones. En junio de {y1}, {half} barrios tenían la mitad o más de sus ubicaciones por debajo de 100/20 Mbps.")}</p>
    <div class="pm-controls" id="bbControls"></div>
    <div class="card pm-map bb-map" id="bbMap" data-t="skip"></div>
    <p class="pm-small" id="bbMapNote" data-t="skip"></p>
  </section>

  <section class="block" id="ranking">
    <h2><span class="ms-icon" aria-hidden="true">table_view</span>{t("2 · Where the gaps are largest", "2 · Dónde las brechas son mayores")}</h2>
    <p class="pm-p">{t("The municipios, sorted by the number of locations below 100/20 Mbps; select a heading to sort by another column. The first row is Puerto Rico.", "Los municipios, ordenados por el número de ubicaciones por debajo de 100/20 Mbps; seleccione un encabezado para ordenar por otra columna. La primera fila es Puerto Rico.")}</p>
    <div class="card pm-tablebox bb-tablebox" id="bbMunis" data-t="skip"></div>
    <h3 class="bb-h3">{t("The barrios", "Los barrios")}</h3>
    <p class="pm-p">{t("A count shows where the most homes and businesses are waiting; a share shows where a whole community is behind. A barrio with few locations can have a high share from a handful of places, so the share ranking leaves out the barrios with fewer than 50 locations.", "Un conteo muestra dónde esperan más hogares y negocios; una proporción muestra dónde una comunidad entera está rezagada. Un barrio con pocas ubicaciones puede tener una proporción alta por unos pocos lugares, así que el orden por proporción deja fuera los barrios con menos de 50 ubicaciones.")}</p>
    <div id="bbRankBy" data-t="skip"></div>
    <div class="card pm-tablebox bb-tablebox" id="bbBarrios" data-t="skip"></div>
  </section>

  <section class="block" id="trend">
    <h2><span class="ms-icon" aria-hidden="true">show_chart</span>{t("3 · How it changed since 2023", "3 · Cómo ha cambiado desde 2023")}</h2>
    <p class="pm-p">{t(f"The share of each municipio's locations below 100/20 Mbps in each June release from {y0} to {y1}. Fiber reached {f1}% of Puerto Rico's locations in June {y1}, from {f0}% in June {y0}. Part of a change from one year to the next comes from the FCC's list of locations, not from the networks.", f"La parte de las ubicaciones de cada municipio por debajo de 100/20 Mbps en cada publicación de junio de {y0} a {y1}. La fibra llegó al {f1} % de las ubicaciones de Puerto Rico en junio de {y1}, desde el {f0} % en junio de {y0}. Parte del cambio de un año a otro viene de la lista de ubicaciones de la FCC, no de las redes.")}</p>
    <div class="card pm-tablebox bb-tablebox" id="bbTrend" data-t="skip"></div>
  </section>

  <section class="block" id="method">
    <h2><span class="ms-icon" aria-hidden="true">info</span>{t("Method", "Método")}</h2>
    <div class="note"><b>{t("The locations.", "Las ubicaciones.")}</b> {t("A broadband serviceable location is a place where the FCC says a home or business is, or could be, connected to fixed internet. An apartment building can be one location with many units, so a location is not a household.", "Una ubicación con servicio de banda ancha posible es un lugar donde la FCC dice que hay, o podría haber, un hogar o negocio conectado a internet fijo. Un edificio de apartamentos puede ser una sola ubicación con muchas unidades, así que una ubicación no es un hogar.")}</div>
    <div class="note"><b>{t("Served, underserved and unserved.", "Servidas, subatendidas y sin servicio.")}</b> {t("The BEAD program's definitions: a location is served when it can get 100/20 Mbps or more, underserved at 25/3 or more but less than 100/20, and unserved below 25/3. Only reliable technologies with low latency count: copper, cable, fiber to the premises, and licensed or licensed-by-rule fixed wireless. Satellite and unlicensed fixed wireless do not, so an unserved location may still have one of them.", "Las definiciones del programa BEAD: una ubicación está servida cuando puede tener 100/20 Mbps o más, subatendida con 25/3 o más pero menos de 100/20, y sin servicio por debajo de 25/3. Solo cuentan las tecnologías confiables de baja latencia: cobre, cable, fibra hasta el local e inalámbrico fijo con licencia o con licencia por regla. El satélite y el inalámbrico fijo sin licencia no cuentan, así que una ubicación sin servicio puede tener uno de ellos.")}</div>
    <div class="note"><b>{t("Barrios and municipios.", "Barrios y municipios.")}</b> {t("Each location belongs to its 2020 census block; each block to its municipio and, by the Census Bureau's internal point, to its barrio. The barrios add up exactly to the municipios and the municipios to Puerto Rico. The map's classes are the same in every year, so the years compare.", "Cada ubicación pertenece a su bloque censal de 2020; cada bloque a su municipio y, por el punto interno del Negociado del Censo, a su barrio. Los barrios suman exactamente los municipios y los municipios suman Puerto Rico. Las clases del mapa son las mismas todos los años, para que los años se puedan comparar.")}</div>
    <div class="note"><b>{t("What the page does not say.", "Lo que la página no dice.")}</b> {t("It does not say what anyone pays, what speed they get or who provides the service, and it does not name any location or provider. It does not include mobile service. A location the FCC counts as served may still have no subscriber.", "No dice cuánto paga nadie, qué velocidad recibe ni quién da el servicio, y no nombra ninguna ubicación ni proveedor. No incluye el servicio móvil. Una ubicación que la FCC cuenta como servida puede no tener ningún suscriptor.")}</div>
    <div class="note"><b>{t("More detail.", "Más detalle.")}</b> {t("The full method, the checks and the code are in docs/broadband.md of the project repository; each figure has an entry in the data dictionary (search for 'broadband'). The same data are layers of the map, in the group Infrastructure · Broadband (FCC).", "El método completo, las comprobaciones y el código están en docs/broadband.md del repositorio del proyecto; cada cifra tiene una entrada en el diccionario de datos (busque «banda ancha»). Los mismos datos son capas del mapa, en el grupo Infraestructura · Banda ancha (FCC).")}</div>
  </section>

  <section class="block" id="sources">
    <h2><span class="ms-icon" aria-hidden="true">menu_book</span>{t("Sources and licenses", "Fuentes y licencias")}</h2>
    <div class="note"><b>{t("Federal Communications Commission (FCC).", "Comisión Federal de Comunicaciones (FCC).")}</b> {t(f"Broadband Data Collection, fixed broadband availability: Puerto Rico's state location files of each release as of June 30, {y0} to {y1}, read with FPR's FCC account. US Government work, public domain.", f"Broadband Data Collection, disponibilidad de banda ancha fija: los archivos de ubicaciones de Puerto Rico de cada publicación al 30 de junio, de {y0} a {y1}, leídos con la cuenta de FPR en la FCC. Obra del Gobierno de EE. UU., dominio público.")}</div>
    <div class="note"><b>{t("National Telecommunications and Information Administration (NTIA).", "Administración Nacional de Telecomunicaciones e Información (NTIA).")}</b> {t("The BEAD program's definitions of served, underserved and unserved.", "Las definiciones de servida, subatendida y sin servicio del programa BEAD.")}</div>
    <div class="note"><b>{t("US Census Bureau.", "Negociado del Censo de EE. UU.")}</b> {t("2020 census blocks and the barrio outlines (TIGER/Line). US Government work.", "Los bloques censales de 2020 y los contornos de los barrios (TIGER/Line). Obra del Gobierno de EE. UU.")}</div>
    <div class="note"><b>{t("Data files.", "Archivos de datos.")}</b> {t("data/broadband_series.json and data/broadband_barrio.json (broadband.py), rebuilt when the FCC publishes a new June release; data/barrios.geojson for the map.", "data/broadband_series.json y data/broadband_barrio.json (broadband.py), que se preparan de nuevo cuando la FCC publica una nueva publicación de junio; data/barrios.geojson para el mapa.")}</div>
    <div class="note"><b>{t("How to cite this page.", "Cómo citar esta página.")}</b> {t(f"Foundation for Puerto Rico, Knowledge Area: Broadband gaps, PR Data Observatory, FCC data as of June 30, {y1} (draft). Data: FCC Broadband Data Collection; US Census Bureau.", f"Foundation for Puerto Rico, Área de conocimiento: Dónde falta banda ancha, Observatorio de Datos de PR, datos de la FCC al 30 de junio de {y1} (borrador). Datos: FCC, Broadband Data Collection; Negociado del Censo de EE. UU.")}</div>
  </section>
</main>
<script src="js/core/knowledge.js?v={ver("js/core/knowledge.js")}"></script>
<script>Core.knowledge.render(); I18N.apply();</script>
<script src="js/common.js?v={ver("js/common.js")}"></script>
<script src="js/broadband_page.js?v=1"></script>
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
    (ROOT / "site" / "broadband.html").write_text(page, encoding="utf-8", newline="\n")
    es = {"_about": "The Broadband gaps page of the Knowledge Area (broadband.html) and site/js/broadband_page.js. Written by docs/analysis/broadband-2026-11/make_page.py from its (English, Spanish) pairs: edit them there, not here."}
    es.update(ES)
    (ROOT / "i18n_src" / "es" / "broadband.json").write_text(json.dumps(es, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(f"wrote site/broadband.html and i18n_src/es/broadband.json ({len(ES)} strings)")


if __name__ == "__main__":
    build()
