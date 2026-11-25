"""Writes the Knowledge Area page "Opportunity Zones 2.0" (site/opportunity-zones.html) and its Spanish (i18n_src/es/oppzones.json).

  python docs/analysis/opportunity-zones-2026-11/make_page.py   read site/data/opportunity_zones.json (python opportunity_zones.py makes it); write the page
                                                                and the Spanish of the page and of site/js/oz_page.js. Then run python i18n.py.

The page follows the site's language rule (docs/i18n.md) and the pattern of the Broadband gaps page (docs/analysis/broadband-2026-11/make_page.py): every
string is written once, as an (English, Spanish) pair, and every figure in the static text is read from the data file. HANDOFF decision 103: the 178 census
tracts of Puerto Rico that the US Treasury designated as Opportunity Zones for 2027-2036, the tracts that were eligible and the first round, described as the
federal designation, with no judgment of which tracts were chosen. Prepared with Claude (AI) for FPR, 2026-11-13.
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


JS = [   # the strings of site/js/oz_page.js
    ("The data could not be loaded ({error}). Check your connection and reload.", "No se pudieron cargar los datos ({error}). Verifique su conexión y vuelva a cargar la página."),
    ("The map could not be loaded ({error}). Check your connection and reload.", "No se pudo cargar el mapa ({error}). Verifique su conexión y vuelva a cargar la página."),
    ("Census tracts designated", "Sectores censales designados"), ("of {e} eligible; the limit was {l}", "de {e} elegibles; el límite era {l}"),
    ("Of them, rural zones", "De ellos, zonas rurales"), ("{n} not rural", "{n} no rurales"),
    ("Residents in a zone", "Residentes en una zona"), ("{s} of Puerto Rico, 2020 Census", "{s} de Puerto Rico, Censo 2020"),
    ("Municipios with a zone", "Municipios con una zona"), ("of 78", "de 78"),
    ("Zones of the first round", "Zonas de la primera ronda"), ("{s} of residents (2010 Census); they end {d}", "{s} de los residentes (Censo 2010); terminan el {d}"),
    ("Census tract {t}, {muni}: {status}", "Sector censal {t}, {muni}: {status}"), ("no residents", "sin residentes"),
    ("Zone, rural", "Zona rural"), ("Zone, not rural", "Zona no rural"), ("Eligible, not designated", "Elegible, no designado"), ("Not eligible", "No elegible"),
    ("Map of the {n} census tracts of Puerto Rico: {z} Opportunity Zones ({r} rural), {e} eligible tracts not designated",
     "Mapa de los {n} sectores censales de Puerto Rico: {z} Zonas de Oportunidad ({r} rurales) y {e} sectores elegibles no designados"),
    ("No residents", "Sin residentes"),
    ("Select a census tract for its figures. Tracts are drawn from the Census Bureau's 1:500,000 outlines; {w} tracts that are only water are not drawn.",
     "Seleccione un sector censal para ver sus cifras. Los sectores se dibujan con los contornos 1:500,000 del Negociado del Censo; no se dibujan {w} sectores que son solo agua."),
    ("No tract selected.", "No hay ningún sector seleccionado."),
    ("Status", "Estado"), ("Municipio", "Municipio"), ("Barrios with residents in the tract", "Barrios con residentes en el sector"),
    ("Residents (2020 Census)", "Residentes (Censo 2020)"), ("Housing units (2020 Census)", "Unidades de vivienda (Censo 2020)"), ("Land area", "Área de tierra"), ("{v} km²", "{v} km²"),
    ("Poverty rate (ACS 2020-2024)", "Tasa de pobreza (ACS 2020-2024)"), ("Median family income (ACS 2020-2024)", "Ingreso familiar mediano (ACS 2020-2024)"), ("${v}", "${v}"),
    ("As a percent of the area's median family income", "Como porcentaje del ingreso familiar mediano del área"), ("{v} of the median of {area} ({a})", "{v} de la mediana de {area} ({a})"),
    ("Puerto Rico outside a metropolitan or micropolitan area", "Puerto Rico fuera de un área metropolitana o micropolitana"),
    ("Rural under the law's definition", "Rural según la definición de la ley"), ("Yes", "Sí"), ("No", "No"), ("Census tract {t}", "Sector censal {t}"),
    ("Municipios: select a heading to sort. Residents of the 2020 Census.", "Municipios: seleccione un encabezado para ordenar. Residentes del Censo 2020."),
    ("Tracts with residents", "Sectores con residentes"), ("Eligible tracts", "Sectores elegibles"), ("Zones", "Zonas"), ("Rural zones", "Zonas rurales"),
    ("Residents in zones", "Residentes en zonas"), ("Share of residents in zones", "Parte de los residentes en zonas"), ("Residents in eligible tracts", "Residentes en sectores elegibles"),
    ("Puerto Rico", "Puerto Rico"), ("Show", "Mostrar"), ("The 25 barrios with the most residents in zones", "Los 25 barrios con más residentes en zonas"),
    ("The barrios of {m}", "Los barrios de {m}"), ("The {n} barrios of {m} with residents, most in a zone first", "Los {n} barrios de {m} con residentes, primero los que tienen más en una zona"),
    ("The {n} barrios with the most residents in zones, of {all} with residents", "Los {n} barrios con más residentes en zonas, de {all} con residentes"),
    ("Barrio", "Barrio"), ("Residents", "Residentes"), ("In a zone", "En una zona"), ("Share in a zone", "Parte en una zona"), ("In an eligible tract", "En un sector elegible"),
    ("poverty {p}, income {i} of the area median", "pobreza {p}, ingreso: {i} de la mediana del área"),
    ("Scatter plot of {n} census tracts: poverty rate against median family income as a percent of the area median, with the eligibility lines at 70% and 125% of income and 20% poverty",
     "Gráfico de dispersión de {n} sectores censales: tasa de pobreza frente al ingreso familiar mediano como porcentaje de la mediana del área, con las líneas de elegibilidad en 70 % y 125 % del ingreso y 20 % de pobreza"),
    ("Median family income, as a percent of the area median (ACS 2020-2024)", "Ingreso familiar mediano, como porcentaje de la mediana del área (ACS 2020-2024)"),
    ("Poverty rate, %", "Tasa de pobreza, %"), ("Eligible by the law's test", "Elegible según la prueba de la ley"),
    ("{n} tracts with residents and both figures are drawn; {m} tracts with residents but no median family income in the survey are left out (Treasury applied the poverty test alone to them). Incomes above 250% are drawn at the right edge.",
     "Se dibujan {n} sectores con residentes y ambas cifras; quedan fuera {m} sectores con residentes pero sin ingreso familiar mediano en la encuesta (el Tesoro les aplicó solo la prueba de pobreza). Los ingresos sobre 250 % se dibujan en el borde derecho."),
    ("Zones, rural", "Zonas rurales"), ("Zones, not rural", "Zonas no rurales"), ("Not eligible (with residents)", "No elegibles (con residentes)"),
    ("The tracts by status: medians of the figures Treasury used (ACS 2020-2024)", "Los sectores según su estado: medianas de las cifras que usó el Tesoro (ACS 2020-2024)"),
    ("Tracts", "Sectores"), ("Number", "Número"), ("Median poverty rate", "Tasa de pobreza mediana"), ("Median income, % of the area median", "Ingreso mediano, % de la mediana del área"),
    ("{n} of {all} census tracts", "{n} de {all} sectores censales"), ("Census geography", "Geografía censal"), ("2010 tracts", "Sectores de 2010"), ("2020 tracts", "Sectores de 2020"),
    ("{n} ({s} of the 2010 Census)", "{n} ({s} del Censo 2010)"), ("{n} ({s} of the 2020 Census)", "{n} ({s} del Censo 2020)"),
    ("How the tracts became zones", "Cómo los sectores llegaron a ser zonas"),
    ("Every low-income tract was deemed a zone by law ({lic} tracts), with {c} tracts next to them", "La ley consideró zona a todo sector de bajos ingresos ({lic} sectores), junto con {c} sectores colindantes"),
    ("Puerto Rico's government could nominate up to a quarter of the {e} eligible tracts ({l}); it nominated {n} and Treasury designated them all", "El Gobierno de Puerto Rico podía nominar hasta una cuarta parte de los {e} sectores elegibles ({l}); nominó {n} y el Tesoro los designó todos"),
    ("Rural zones with larger benefits", "Zonas rurales con beneficios mayores"), ("{r} of the {n}", "{r} de los {n}"),
    ("In effect", "Vigencia"), ("Through {d}", "Hasta el {d}"), ("From {a} to {b}", "Del {a} al {b}"),
    ("The first and second rounds of Opportunity Zones in Puerto Rico", "La primera y la segunda ronda de Zonas de Oportunidad en Puerto Rico"),
    ("First round (2018)", "Primera ronda (2018)"), ("Second round (2027)", "Segunda ronda (2027)"),
]
for en, es in JS:
    t(en, es)


def num(v, d=0):
    return f"{v:,.{d}f}"


def build():
    D = json.loads((ROOT / "site" / "data" / "opportunity_zones.json").read_text(encoding="utf-8"))
    p, r1, v = D["pr"], D["first_round"], D["vintage"]
    MF = D["muni_fields"]
    mrows = [dict(zip(MF, r)) for r in D["municipios"]]
    top = sorted(mrows, key=lambda m: -m["pop_designated"])[:3]
    top_txt = ", ".join(f"{m['name']} ({num(m['pop_designated'])})" for m in top)
    most = max(m["designated"] for m in mrows)
    most_m = sorted(m["name"] for m in mrows if m["designated"] == most)
    one = sum(1 for m in mrows if m["designated"] == 1)
    G = D["groups"]
    eligible_share = p["pop_eligible_share"]
    ref = (ROOT / "site" / "reservoirs.html").read_text(encoding="utf-8")
    ver = lambda name: re.search(re.escape(name) + r"\?v=(\d+)", ref).group(1)
    I18N_V = 63   # the ?v= of js/i18n.js also versions this page's Spanish bundle: raise it when the page's strings change (docs/i18n.md, rule 12)
    icons = sorted(set(re.search(r"icon_names=([a-z0-9_,]+)", ref).group(1).split(",")) | {"school", "work", "map", "table_view", "scatter_plot", "history", "info", "menu_book", "location_city", "savings", "account_tree", "dark_mode", "explore", "grid_view", "light_mode"})
    and_most = " and ".join([", ".join(most_m[:-1]), most_m[-1]] if len(most_m) > 1 else most_m)
    y_most = " y ".join([", ".join(most_m[:-1]), most_m[-1]] if len(most_m) > 1 else most_m)

    page = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{t("Knowledge Area · Opportunity Zones 2.0", "Área de conocimiento · Zonas de Oportunidad 2.0")}</title>
<meta name="description" content="{t("The census tracts of Puerto Rico that the US Treasury designated as Opportunity Zones for 2027 to 2036, rural or not, with the tracts that were eligible, the residents in zones by municipio and barrio, and the first round.", "Los sectores censales de Puerto Rico que el Tesoro de EE. UU. designó como Zonas de Oportunidad para 2027 a 2036, rurales o no, con los sectores que eran elegibles, los residentes en zonas por municipio y barrio, y la primera ronda.")}">
<meta name="theme-color" content="#FFFFFF">
<link rel="icon" href="img/fpr-mark.png">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Material+Symbols+Rounded:opsz,wght,FILL,GRAD@24,400,1,0&icon_names={",".join(icons)}&display=block">
<link rel="stylesheet" href="css/twin.css?v={ver("css/twin.css")}">
<link rel="stylesheet" href="css/housing.css?v={ver("css/housing.css")}">
<link rel="stylesheet" href="css/public_money.css?v={ver("css/public_money.css")}">
<link rel="stylesheet" href="css/oz.css?v=4">
<link rel="stylesheet" href="css/chat.css?v={ver("css/chat.css")}">
<link rel="stylesheet" href="css/ws.css?v=1">
<script src="js/i18n.js?v={max(int(ver("js/i18n.js")), I18N_V)}" data-page="oppzones"></script>
</head>
<body class="research">
<a class="skip" href="#now">{t("Skip to the content", "Ir al contenido")}</a>
<header class="topbar">
  <a class="logo" href="index.html" title="{t("PR Data Observatory home", "Inicio del Observatorio de Datos de PR")}"><img src="img/fpr-logo.png" alt="{t("Foundation for Puerto Rico. PR Data Observatory home", "Foundation for Puerto Rico. Inicio del Observatorio de Datos de PR")}"></a>
  <div class="brand" data-gloss="off"><b>{t("Knowledge Area · Opportunity Zones 2.0", "Área de conocimiento · Zonas de Oportunidad 2.0")}</b><span>{t("Where the federal investment incentive applies from 2027", "Dónde aplica el incentivo federal a la inversión desde 2027")}</span></div>
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
  <span class="ka-tabs" role="group" aria-label="{t("Knowledge Area", "Área de conocimiento")}" data-ka="oppzones"></span><span class="ka-sep" aria-hidden="true"></span>
  <a href="#intro">{t("Introduction", "Introducción")}</a><a href="#now">{t("Now", "Ahora")}</a><a href="#zones">{t("Map", "Mapa")}</a><a href="#municipios">{t("Municipios", "Municipios")}</a><a href="#barrios">{t("Barrios", "Barrios")}</a><a href="#eligibility">{t("Eligibility", "Elegibilidad")}</a><a href="#rounds">{t("Two rounds", "Dos rondas")}</a><a href="#incentive">{t("The incentive", "El incentivo")}</a><a href="#method">{t("Method", "Método")}</a><a href="#sources">{t("Sources", "Fuentes")}</a>
</nav>

<main class="page">
  <div class="note caution review-note" role="note" data-ka-note></div>

  <section class="hero" id="now">
    <div class="eyebrow">{t("Knowledge Area · Economy", "Área de conocimiento · Economía")}</div>
    <h1>{t("Opportunity Zones 2.0 in Puerto Rico", "Zonas de Oportunidad 2.0 en Puerto Rico")}</h1>
    <div class="oz-intro" id="intro">
      <h2 class="oz-h2">{t("What Opportunity Zones are and why they matter", "Qué son las Zonas de Oportunidad y por qué importan")}</h2>
      <p class="pm-p">{t("An Opportunity Zone is a census tract with low incomes or high poverty where federal tax law rewards long-term private investment. A person or company that sells an asset at a profit (a capital gain) can put that money into a Qualified Opportunity Fund, which invests in businesses, housing or buildings in the zones. In exchange, the federal tax on that gain is deferred for up to five years and can be reduced, and the growth of the investment itself is not taxed if it is held ten years or more. Congress created the zones in 2017 and made them permanent in 2025, with a new round every ten years.", "Una Zona de Oportunidad es un sector censal de ingresos bajos o pobreza alta donde la ley contributiva federal premia la inversión privada a largo plazo. Una persona o empresa que vende un activo con ganancia (una ganancia de capital) puede colocar ese dinero en un Fondo de Oportunidad Calificado, que invierte en negocios, vivienda o edificios en las zonas. A cambio, la contribución federal sobre esa ganancia se aplaza hasta cinco años y puede reducirse, y el crecimiento de la propia inversión no tributa si se conserva diez años o más. El Congreso creó las zonas en 2017 y las hizo permanentes en 2025, con una ronda nueva cada diez años.")}</p>
      <p class="pm-p">{t("The incentive exists to bring private capital to places that have trouble attracting it: the IRS describes the zones as designed to spur economic development and job creation in distressed communities. Because the benefit goes to investors who stay for years, it favors long-term projects, such as new or larger businesses, housing, commercial buildings and infrastructure, that can create jobs and services where they are scarce. For municipios, community organizations and entrepreneurs, a project inside a zone can offer investors a tax advantage that a project elsewhere cannot.", "El incentivo existe para llevar capital privado a lugares a los que les cuesta atraerlo: el IRS describe las zonas como diseñadas para impulsar el desarrollo económico y la creación de empleos en comunidades económicamente desfavorecidas. Como el beneficio es para inversionistas que se quedan por años, favorece proyectos a largo plazo, como negocios nuevos o ampliados, vivienda, edificios comerciales e infraestructura, que pueden crear empleos y servicios donde escasean. Para los municipios, las organizaciones comunitarias y los empresarios, un proyecto dentro de una zona puede ofrecer a los inversionistas una ventaja contributiva que un proyecto en otro lugar no tiene.")}</p>
      <p class="pm-p">{t("A designation alone does not bring investment. Treasury's Office of Tax Analysis counts $112 billion invested through Opportunity Funds through 2024, reaching 77% of the zones in the states; more than half of it was in real estate, and more of it went to less distressed areas and to areas that were already growing. In Puerto Rico, where over 90% of census tracts were zones in the first round, only 7% of those zones had received investment by 2024. From 2027 there are fewer zones, 178, and rural zones offer larger benefits, so knowing exactly where they are helps plan projects and bring investors to them.", "Una designación por sí sola no trae inversión. La Oficina de Análisis Contributivo del Tesoro cuenta $112 mil millones invertidos mediante Fondos de Oportunidad hasta 2024, que llegaron al 77 % de las zonas de los estados; más de la mitad fue a bienes raíces, y llegó más a las áreas menos desfavorecidas y a las que ya estaban creciendo. En Puerto Rico, donde más del 90 % de los sectores censales eran zonas en la primera ronda, solo el 7 % de esas zonas había recibido inversión hasta 2024. Desde 2027 hay menos zonas, 178, y las rurales ofrecen beneficios mayores, así que saber exactamente dónde están ayuda a planificar proyectos y a atraer inversionistas a ellos.")}</p>
    </div>
    <h2 class="oz-h2">{t("The 2026 designation", "La designación de 2026")}</h2>
    <p class="lede">{t(f"On November 5, 2026, the US Treasury designated {p['designated']} census tracts of Puerto Rico as Opportunity Zones for ten years from January 1, 2027: {p['non_rural']} not rural and {p['rural']} rural. They were home to {num(p['pop_designated'])} people, {p['pop_share']}% of Puerto Rico's residents in the 2020 Census, and each of the {p['municipios_with_zone']} municipios has at least one. In the first round, {num(r1['tracts'])} tracts were zones, with {r1['pop_share']}% of the residents of the 2010 Census; those zones end on December 31, 2027.", f"El 5 de noviembre de 2026, el Tesoro de EE. UU. designó {p['designated']} sectores censales de Puerto Rico como Zonas de Oportunidad por diez años a partir del 1 de enero de 2027: {p['non_rural']} no rurales y {p['rural']} rurales. En ellos vivían {num(p['pop_designated'])} personas, el {p['pop_share']} % de los residentes de Puerto Rico en el Censo 2020, y cada uno de los {p['municipios_with_zone']} municipios tiene al menos uno. En la primera ronda, {num(r1['tracts'])} sectores eran zonas, con el {r1['pop_share']} % de los residentes del Censo 2010; esas zonas terminan el 31 de diciembre de 2027.")}</p>
    <div id="ozNow" aria-live="polite"></div>
    <div class="note caution"><b>{t("What a zone is not.", "Lo que una zona no es.")}</b> {t("It is not a grant: no public money is paid to the zone or to its residents. This page describes the federal designation; it does not judge which tracts were chosen.", "No es una subvención: no se paga dinero público a la zona ni a sus residentes. Esta página describe la designación federal; no juzga qué sectores se escogieron.")}</div>
  </section>

  <section class="block" id="zones">
    <h2><span class="ms-icon" aria-hidden="true">map</span>{t("1 · The zones, tract by tract", "1 · Las zonas, sector por sector")}</h2>
    <p class="pm-p">{t(f"Each 2020 census tract is shaded by its status: a zone made entirely of rural area (orange), a zone that is not rural (purple), a tract that was eligible but was not designated (sand) or a tract that was not eligible (light gray). Of the {p['eligible']} eligible tracts, {p['eligible_rural']} were rural. Select a tract for its residents, barrios and the figures Treasury used.", f"Cada sector censal de 2020 está coloreado según su estado: una zona formada por completo por área rural (anaranjado), una zona que no es rural (morado), un sector que era elegible pero no se designó (arena) o un sector que no era elegible (gris claro). De los {p['eligible']} sectores elegibles, {p['eligible_rural']} eran rurales. Seleccione un sector para ver sus residentes, sus barrios y las cifras que usó el Tesoro.")}</p>
    <div class="card pm-map oz-map" id="ozMap" data-t="skip"></div>
    <p class="pm-small" id="ozMapNote" data-t="skip"></p>
    <div class="oz-tract" id="ozTract" aria-live="polite" data-t="skip"></div>
  </section>

  <section class="block" id="municipios">
    <h2><span class="ms-icon" aria-hidden="true">table_view</span>{t("2 · By municipio", "2 · Por municipio")}</h2>
    <p class="pm-p">{t(f"Every municipio has between 1 and {most} zones: {and_most} {'have' if len(most_m) > 1 else 'has'} {most}, and {one} municipios have one. The municipios with the most residents in zones are {top_txt}. The table is sorted by the residents in zones; select a heading to sort by another column. The first row is Puerto Rico.", f"Cada municipio tiene entre 1 y {most} zonas: {y_most} {'tienen' if len(most_m) > 1 else 'tiene'} {most}, y {one} municipios tienen una. Los municipios con más residentes en zonas son {top_txt}. La tabla está ordenada por los residentes en zonas; seleccione un encabezado para ordenar por otra columna. La primera fila es Puerto Rico.")}</p>
    <div class="card pm-tablebox oz-tablebox" id="ozMunis" data-t="skip"></div>
  </section>

  <section class="block" id="barrios">
    <h2><span class="ms-icon" aria-hidden="true">location_city</span>{t("3 · By barrio", "3 · Por barrio")}</h2>
    <p class="pm-p">{t("A barrio can lie in several census tracts, some in a zone and some not, so part of its residents can live in a zone. The residents are counted by census block, so the barrios add up exactly to the municipios. Pick a municipio to see all its barrios.", "Un barrio puede estar en varios sectores censales, algunos en una zona y otros no, así que parte de sus residentes puede vivir en una zona. Los residentes se cuentan por bloque censal, así que los barrios suman exactamente los municipios. Escoja un municipio para ver todos sus barrios.")}</p>
    <div class="oz-pick" id="ozBarrioPick" data-t="skip"></div>
    <div class="card pm-tablebox oz-tablebox" id="ozBarrios" data-t="skip"></div>
  </section>

  <section class="block" id="eligibility">
    <h2><span class="ms-icon" aria-hidden="true">scatter_plot</span>{t("4 · How a tract qualified", "4 · Cómo un sector calificó")}</h2>
    <p class="pm-p">{t(f"A tract was eligible if it was a low-income community under the law as amended in 2025: a median family income of at most 70% of its area's, or a poverty rate of 20% or more with a median family income of at most 125% of its area's. The area is the metropolitan or micropolitan area the tract is in, or Puerto Rico outside them. Treasury used the American Community Survey of {v['acs']}. {p['eligible']} of Puerto Rico's tracts were eligible, with {eligible_share}% of its residents. Puerto Rico's government could nominate a quarter of them, rounded up: {p['limit']}. It nominated {p['designated']} and Treasury designated all of them.", f"Un sector era elegible si era una comunidad de bajos ingresos según la ley enmendada en 2025: un ingreso familiar mediano de no más del 70 % del de su área, o una tasa de pobreza de 20 % o más con un ingreso familiar mediano de no más del 125 % del de su área. El área es el área metropolitana o micropolitana en que está el sector, o Puerto Rico fuera de ellas. El Tesoro usó la Encuesta sobre la Comunidad de {v['acs']}. {p['eligible']} de los sectores de Puerto Rico eran elegibles, con el {eligible_share} % de sus residentes. El Gobierno de Puerto Rico podía nominar una cuarta parte de ellos, redondeada hacia arriba: {p['limit']}. Nominó {p['designated']} y el Tesoro los designó todos.")}</p>
    <div class="card pm-map" id="ozScatter" data-t="skip"></div>
    <p class="pm-small" id="ozScatterNote" data-t="skip"></p>
    <p class="pm-p">{t("The medians of each group, from the figures Treasury published. They describe the tracts; they do not explain why a tract was or was not nominated.", "Las medianas de cada grupo, con las cifras que publicó el Tesoro. Describen los sectores; no explican por qué un sector se nominó o no.")}</p>
    <div class="card pm-tablebox oz-tablebox" id="ozGroups" data-t="skip"></div>
  </section>

  <section class="block" id="rounds">
    <h2><span class="ms-icon" aria-hidden="true">history</span>{t("5 · The first round and the second", "5 · La primera ronda y la segunda")}</h2>
    <p class="pm-p">{t(f"In 2018, a rule for Puerto Rico alone made every low-income tract a zone, so nearly the whole island was one. The 2025 law ended that rule: from 2027, Puerto Rico follows the same limit as the states. The first round's zones stay in effect until December 31, 2027, so during 2027 both sets apply. The two rounds use different census tracts (2010 and 2020), so they are compared by counts and shares, not tract by tract.", f"En 2018, una regla solo para Puerto Rico convirtió en zona a todo sector de bajos ingresos, así que casi toda la isla lo era. La ley de 2025 terminó esa regla: desde 2027, Puerto Rico sigue el mismo límite que los estados. Las zonas de la primera ronda siguen vigentes hasta el 31 de diciembre de 2027, así que durante 2027 aplican ambas. Las dos rondas usan sectores censales distintos (de 2010 y de 2020), así que se comparan por conteos y proporciones, no sector por sector.")}</p>
    <div class="card pm-tablebox oz-tablebox" id="ozRounds" data-t="skip"></div>
  </section>

  <section class="block" id="incentive">
    <h2><span class="ms-icon" aria-hidden="true">savings</span>{t("6 · What the incentive offers investors", "6 · Lo que el incentivo ofrece a los inversionistas")}</h2>
    <div class="note"><b>{t("For investments made after December 31, 2026.", "Para inversiones hechas después del 31 de diciembre de 2026.")}</b> {t("A taxpayer who invests a capital gain in a Qualified Opportunity Fund pays the federal tax on that gain when the investment is sold, or five years after it was made, whichever comes first. If the investment is held five years, the gain taxed then is 10% smaller (30% smaller for a fund that invests in rural zones). If it is held ten years or more, the growth of the investment itself is not taxed, up to 30 years. A fund must hold at least 90% of its assets in property, stock or partnership interests in zones.", "Un contribuyente que invierte una ganancia de capital en un Fondo de Oportunidad Calificado paga la contribución federal sobre esa ganancia cuando vende la inversión, o cinco años después de hacerla, lo que ocurra primero. Si conserva la inversión cinco años, la ganancia que tributa entonces es 10 % menor (30 % menor en un fondo que invierte en zonas rurales). Si la conserva diez años o más, el crecimiento de la propia inversión no tributa, hasta 30 años. Un fondo debe tener al menos el 90 % de sus activos en propiedades, acciones o participaciones en sociedades en zonas.")}</div>
    <div class="note"><b>{t("Rural zones.", "Zonas rurales.")}</b> {t("A zone is rural when it lies entirely outside any city or town of more than 50,000 inhabitants and the urban areas joined to it; in Puerto Rico, Treasury used the census designated places of more than 50,000 inhabitants as the cities. Besides the larger tax cut, a building bought in a rural zone qualifies when it is improved by half of what it cost, not counting the land, instead of by all of it (IRS Notice 2025-50).", "Una zona es rural cuando está por completo fuera de toda ciudad o pueblo de más de 50,000 habitantes y de las áreas urbanas unidas a ellos; en Puerto Rico, el Tesoro usó como ciudades los lugares designados por el censo de más de 50,000 habitantes. Además de la mayor reducción contributiva, un edificio comprado en una zona rural califica cuando se mejora por la mitad de lo que costó, sin contar el terreno, en vez de por todo (Aviso del IRS 2025-50).")}</div>
    <div class="note"><b>{t("What the page does not show.", "Lo que la página no muestra.")}</b> {t("Where Opportunity Fund money has gone: Treasury publishes the investment in zones only in aggregate studies, not by tract. Nor Puerto Rico's own incentives, or how federal tax applies to a resident of Puerto Rico; ask a tax adviser for that.", "A dónde ha ido el dinero de los Fondos de Oportunidad: el Tesoro publica la inversión en zonas solo en estudios agregados, no por sector. Tampoco los incentivos propios de Puerto Rico, ni cómo aplica la contribución federal a un residente de Puerto Rico; consulte a un asesor contributivo para eso.")}</div>
  </section>

  <section class="block" id="method">
    <h2><span class="ms-icon" aria-hidden="true">info</span>{t("Method", "Método")}</h2>
    <div class="note"><b>{t("The lists.", "Las listas.")}</b> {t(f"The designated tracts, their rural status and the figures of every tract are Treasury's (Data Transparency files of October 30, 2026), checked against the CDFI Fund's full list of November 5, 2026: Puerto Rico's {p['designated']} tracts and their rural status are the same in both. Some announcements gave 97 tracts that are not rural; both lists have {p['non_rural']}, for {p['designated']} in all.", f"Los sectores designados, su condición rural y las cifras de cada sector son del Tesoro (archivos de Data Transparency del 30 de octubre de 2026), comprobados con la lista completa del CDFI Fund del 5 de noviembre de 2026: los {p['designated']} sectores de Puerto Rico y su condición rural son los mismos en ambas. Algunos anuncios dieron 97 sectores no rurales; ambas listas tienen {p['non_rural']}, para {p['designated']} en total.")}</div>
    <div class="note"><b>{t("Eligibility.", "Elegibilidad.")}</b> {t("The law's test, applied to Treasury's published poverty rate and median family income, gives exactly Treasury's list of eligible tracts; tracts with no income figure were judged by the poverty test alone. The figures are survey estimates with margins of error, and Treasury's file is the official list.", "La prueba de la ley, aplicada a la tasa de pobreza y al ingreso familiar mediano que publicó el Tesoro, da exactamente la lista de sectores elegibles del Tesoro; los sectores sin cifra de ingreso se evaluaron solo con la prueba de pobreza. Las cifras son estimados de encuesta con márgenes de error, y el archivo del Tesoro es la lista oficial.")}</div>
    <div class="note"><b>{t("Residents.", "Residentes.")}</b> {t("Residents and housing units are those of the 2020 Census. Each census block is counted whole in its tract and, by its internal point, in its barrio, so tracts, barrios and municipios add up exactly. The first round's residents are those of the 2010 Census in its 2010 tracts.", "Los residentes y las unidades de vivienda son los del Censo 2020. Cada bloque censal se cuenta entero en su sector y, por su punto interno, en su barrio, así que los sectores, los barrios y los municipios suman exactamente. Los residentes de la primera ronda son los del Censo 2010 en sus sectores de 2010.")}</div>
    <div class="note"><b>{t("More detail.", "Más detalle.")}</b> {t("The method, the checks and the code are in docs/opportunity-zones.md of the project repository; each figure has an entry in the data dictionary (search for 'Opportunity Zones'). The zones are also a layer of the map and of the 3D view, in the group Economy.", "El método, las comprobaciones y el código están en docs/opportunity-zones.md del repositorio del proyecto; cada cifra tiene una entrada en el diccionario de datos (busque «Zonas de Oportunidad»). Las zonas también son una capa del mapa y de la vista 3D, en el grupo Economía.")}</div>
  </section>

  <section class="block" id="sources">
    <h2><span class="ms-icon" aria-hidden="true">menu_book</span>{t("Sources and licenses", "Fuentes y licencias")}</h2>
    <div class="note"><b>{t("US Department of the Treasury.", "Departamento del Tesoro de EE. UU.")}</b> {t("Office of Tax Policy, Data Transparency for Qualified Opportunity Zones: the 2027 designations and the tracts eligible for nomination, with their methodology; CDFI Fund, the full list of designated zones (2027) and the 2018 list; IRS Revenue Procedure 2026-14. US Government works, no US copyright.", "Oficina de Política Contributiva, Data Transparency para Zonas de Oportunidad Calificadas: las designaciones de 2027 y los sectores elegibles para nominación, con su metodología; CDFI Fund, la lista completa de zonas designadas (2027) y la lista de 2018; Procedimiento Contributivo del IRS 2026-14. Obras del Gobierno de EE. UU., sin derechos de autor en EE. UU.")}</div>
    <div class="note"><b>{t("Treasury, Office of Tax Analysis.", "Tesoro, Oficina de Análisis Contributivo.")}</b> {t("David Coyne and Craig Johnson, Use of the Opportunity Zone Tax Incentive through 2024: An Update, Working Paper 128, June 2026: investment through Opportunity Funds by zone and state, from tax returns (the figures of the introduction).", "David Coyne y Craig Johnson, Use of the Opportunity Zone Tax Incentive through 2024: An Update, documento de trabajo 128, junio de 2026: la inversión mediante Fondos de Oportunidad por zona y estado, según las planillas (las cifras de la introducción).")}</div>
    <div class="note"><b>{t("Internal Revenue Service (IRS).", "Servicio de Rentas Internas (IRS).")}</b> {t("Opportunity Zones Frequently Asked Questions: what a zone is and what it is for.", "Preguntas frecuentes sobre las Zonas de Oportunidad: qué es una zona y para qué sirve.")}</div>
    <div class="note"><b>{t("The law.", "La ley.")}</b> {t("26 U.S.C. 1400Z-1 and 1400Z-2, as amended by section 70421 of Public Law 119-21 (July 4, 2025).", "26 U.S.C. 1400Z-1 y 1400Z-2, según enmendados por la sección 70421 de la Ley Pública 119-21 (4 de julio de 2025).")}</div>
    <div class="note"><b>{t("US Census Bureau.", "Negociado del Censo de EE. UU.")}</b> {t("2020 Census residents and housing units by block, the barrio and tract outlines, and the 2010 Census residents of the 2010 tracts (TIGERweb). US Government work.", "Residentes y unidades de vivienda del Censo 2020 por bloque, los contornos de los barrios y los sectores, y los residentes del Censo 2010 en los sectores de 2010 (TIGERweb). Obra del Gobierno de EE. UU.")}</div>
    <div class="note"><b>{t("Data files.", "Archivos de datos.")}</b> {t("data/opportunity_zones.json and the map layer data/oz_tracts.geojson (opportunity_zones.py), rebuilt when Treasury publishes a new file; data/geo/tracts.geojson for the map.", "data/opportunity_zones.json y la capa del mapa data/oz_tracts.geojson (opportunity_zones.py), que se preparan de nuevo cuando el Tesoro publica un archivo nuevo; data/geo/tracts.geojson para el mapa.")}</div>
    <div class="note"><b>{t("How to cite this page.", "Cómo citar esta página.")}</b> {t("Foundation for Puerto Rico, Knowledge Area: Opportunity Zones 2.0, PR Data Observatory, designations of November 5, 2026. Data: US Department of the Treasury; US Census Bureau.", "Foundation for Puerto Rico, Área de conocimiento: Zonas de Oportunidad 2.0, Observatorio de Datos de PR, designaciones del 5 de noviembre de 2026. Datos: Departamento del Tesoro de EE. UU.; Negociado del Censo de EE. UU.")}</div>
  </section>
</main>
<script src="js/core/knowledge.js?v={ver("js/core/knowledge.js")}"></script>
<script>Core.knowledge.render(); I18N.apply();</script>
<script src="js/common.js?v={ver("js/common.js")}"></script>
<script src="js/oz_page.js?v=2"></script>
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
    (ROOT / "site" / "opportunity-zones.html").write_text(page, encoding="utf-8", newline="\n")
    es = {"_about": "The Opportunity Zones 2.0 page of the Knowledge Area (opportunity-zones.html) and site/js/oz_page.js. Written by docs/analysis/opportunity-zones-2026-11/make_page.py from its (English, Spanish) pairs: edit them there, not here."}
    es.update(ES)
    (ROOT / "i18n_src" / "es" / "oppzones.json").write_text(json.dumps(es, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(f"wrote site/opportunity-zones.html and i18n_src/es/oppzones.json ({len(ES)} strings)")


if __name__ == "__main__":
    build()
