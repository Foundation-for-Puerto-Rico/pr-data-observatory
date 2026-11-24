"""Writes the Knowledge Area page "Inflation" (site/inflation.html) and its Spanish (i18n_src/es/inflation.json).

  python docs/analysis/inflation-2026-11/make_page.py   read site/data/inflation.json (python inflation.py makes it); write the page and the Spanish
                                                        of the page and of site/js/inflation.js. Then run python i18n.py.

The page follows the site's language rule (docs/i18n.md) and the pattern of the Urban heat page (docs/analysis/urban-heat-2026-11/make_page.py): every
string is written once, as an (English, Spanish) pair, and every figure in the text is read from the data file. HANDOFF decision 95,
docs/inflation-plan-2026-11.md. Prepared with Claude (AI) for FPR, 2026-11-10.
"""
import html
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
ES = {}
MONTHS_EN = "January February March April May June July August September October November December".split()
MONTHS_ES = "enero febrero marzo abril mayo junio julio agosto septiembre octubre noviembre diciembre".split()
ICONS = ("account_tree,dark_mode,explore,grid_view,light_mode,"   # the rail and the light/dark switch (css/ws.css)
         "account_balance,bar_chart,bolt,calculate,chat_bubble,close,commute,delete,diversity_3,download,elderly,family_restroom,home_work,hourglass_bottom,info,lightbulb,map,menu_book,"
         "payments,pie_chart,price_change,query_stats,restart_alt,rocket_launch,route,savings,school,send,show_chart,table_view,thermostat,view_in_ar,warning,water,wifi,woman,work")


def t(en, es):
    key = " ".join(en.split())
    if key in ES and ES[key] != es:
        raise SystemExit(f"two Spanish texts for {key!r}")
    ES[key] = " ".join(es.split())
    return html.escape(key, quote=False)


def men(k):
    y, m = map(int, k.split("-"))
    return f"{MONTHS_EN[m - 1]} {y}"


def mes(k):
    y, m = map(int, k.split("-"))
    return f"{MONTHS_ES[m - 1]} de {y}"


def p_en(x, d=1):
    return f"{x:.{d}f}%"


def p_es(x, d=1):
    return f"{x:.{d}f} %"


def d_en(x, d=0):
    return f"${x:,.{d}f}"


def d_es(x, d=0):
    return f"${x:,.{d}f}"


JS = [
    ("The data could not be loaded ({error}). Check your connection and reload.", "No se pudieron cargar los datos ({error}). Verifique su conexión y vuelva a cargar la página."),
    ("Projection", "Proyección"), ("Puerto Rico", "Puerto Rico"), ("United States", "Estados Unidos"), ("projected", "proyectado"),
    ("Line chart: 12-month inflation in Puerto Rico and the United States from {from} to {to}, then the projection to {end} with bands. Latest: Puerto Rico {pr}, United States {us}.",
     "Gráfico de líneas: inflación de 12 meses en Puerto Rico y en Estados Unidos desde {from} hasta {to}, y luego la proyección hasta {end} con bandas. Lo más reciente: Puerto Rico {pr}, Estados Unidos {us}."),
    ("Bar chart: average inflation of each calendar year in Puerto Rico and the United States; lighter bars are projected, with their 80% range",
     "Gráfico de barras: inflación promedio de cada año natural en Puerto Rico y en Estados Unidos; las barras más claras son proyectadas, con su intervalo de 80 %"),
    ("Year", "Año"), ("Difference (points)", "Diferencia (puntos)"), ("Note", "Nota"),
    ("{n} months observed, the rest projected", "{n} meses observados, el resto proyectado"), ("projected (80% range)", "proyectado (intervalo de 80 %)"),
    ("Average of the 12 monthly index values of each year over the year before.", "Promedio de los 12 valores mensuales del índice de cada año sobre el del año anterior."),
    ("Food and beverages", "Alimentos y bebidas"), ("Housing", "Vivienda"), ("Apparel", "Ropa"), ("Transportation", "Transporte"), ("Medical care", "Cuidado médico"),
    ("Recreation", "Entretenimiento"), ("Education and communication", "Educación y comunicación"), ("Other goods and services", "Otros artículos y servicios"),
    ("Group", "Grupo"), ("Weight in Puerto Rico's basket", "Peso en la canasta de Puerto Rico"), ("Puerto Rico, 12 months", "Puerto Rico, 12 meses"),
    ("United States, 12 months", "Estados Unidos, 12 meses"), ("Puerto Rico, since January 2020", "Puerto Rico, desde enero de 2020"), ("United States, since January 2020", "Estados Unidos, desde enero de 2020"),
    ("Bar chart: the rise in prices of each group since January 2020, Puerto Rico and the United States", "Gráfico de barras: el aumento de precios de cada grupo desde enero de 2020, Puerto Rico y Estados Unidos"),
    ("Year {k} ahead", "Año {k} hacia adelante"), ("Cleveland Fed model of {month}", "Modelo de la Reserva Federal de Cleveland de {month}"), ("Horizon", "Horizonte"),
    ("Expected inflation in that year", "Inflación esperada en ese año"), ("Expected average from now", "Promedio esperado desde ahora"),
    ("Puerto Rico follows expected US inflation (the method used)", "Puerto Rico sigue la inflación esperada de EE. UU. (el método usado)"),
    ("A model of Puerto Rico's monthly inflation on US inflation (ARDL)", "Un modelo de la inflación mensual de Puerto Rico sobre la de EE. UU. (ARDL)"),
    ("The last 12 months persist", "Los últimos 12 meses se mantienen"), ("Puerto Rico's own average since 2008", "El promedio propio de Puerto Rico desde 2008"),
    ("Expected US inflation plus the last 10 years' gap", "La inflación esperada de EE. UU. más la brecha de los últimos 10 años"),
    ("Root mean square error, in percentage points of average annual inflation; {n} forecasts from each quarter of {a} to {b}; the smallest in each column is in bold.",
     "Raíz del error cuadrático medio, en puntos porcentuales de inflación anual promedio; {n} pronósticos desde cada trimestre de {a} a {b}; el menor de cada columna está en negritas."),
    ("Method", "Método"), ("1 year", "1 año"), ("{h} years", "{h} años"),
    ("current dollars", "dólares corrientes"),
    ("Median household income after inflation, {a} = 100", "Ingreso mediano del hogar después de la inflación, {a} = 100"),
    ("Line chart: median household income after inflation, {a} = 100, Puerto Rico and the United States, {a} to {z}", "Gráfico de líneas: ingreso mediano del hogar después de la inflación, {a} = 100, Puerto Rico y Estados Unidos, {a} a {z}"),
    ("Puerto Rico, current dollars", "Puerto Rico, dólares corrientes"), ("Puerto Rico, dollars of {y}", "Puerto Rico, dólares de {y}"),
    ("United States, current dollars", "Estados Unidos, dólares corrientes"), ("United States, dollars of {y}", "Estados Unidos, dólares de {y}"),
    ("Median household income, American Community Survey 1-year; ± is the margin of error at 90% confidence; 2020 has no standard 1-year release. Constant dollars use each place's own price index.",
     "Ingreso mediano del hogar, Encuesta sobre la Comunidad de 1 año; ± es el margen de error con 90 % de confianza; 2020 no tiene publicación estándar de 1 año. Los dólares constantes usan el índice de precios de cada lugar."),
    ("In {month}", "En {month}"), ("The same purchases in {month}", "Las mismas compras en {month}"), ("{p} more", "{p} más"),
    ("Projected for {month}", "Proyectado para {month}"), ("80% range: {lo} to {hi}", "Intervalo de 80 %: {lo} a {hi}"), ("Change", "Cambio"),
    ("Effective December of", "Efectivo en diciembre de"), ("Adjustment", "Ajuste"),
    ("What {inc} buys today, at the prices of {month}", "Lo que {inc} compra hoy, a precios de {month}"), ("{p} less buying power", "{p} menos poder de compra"),
    ("Raise needed to buy the same as in {month}", "Aumento necesario para comprar lo mismo que en {month}"), ("{m} a month; an income of {n} a year", "{m} al mes; un ingreso de {n} al año"),
    ("Buying power lost by {month} if the income stays at {inc}", "Poder de compra perdido para {month} si el ingreso sigue en {inc}"),
    ("a year, at today's prices; 80% range: {lo} to {hi}", "al año, a precios de hoy; intervalo de 80 %: {lo} a {hi}"), ("(median, {y})", "(mediana, {y})"),
    ("Annual household income", "Ingreso anual del hogar"), ("Buys today, at the prices of {month}", "Compra hoy, a precios de {month}"), ("Raise needed, a year", "Aumento necesario, al año"),
    ("A month", "Al mes"), ("More lost by {month}, a year", "Pérdida adicional para {month}, al año"), ("{month} (a year ago)", "{month} (hace un año)"),
    ("An income that did not rise since {month}; Puerto Rico's consumer price index to {last}. Every income loses the same share, {p}; the row in bold is the income entered.",
     "Un ingreso que no subió desde {month}; índice de precios al consumidor de Puerto Rico hasta {last}. Todo ingreso pierde la misma proporción, {p}; la fila en negrita es el ingreso que escribió."),
]
for en, es in JS:
    t(en, es)


def build():
    D = json.loads((ROOT / "site" / "data" / "inflation.json").read_text(encoding="utf-8"))
    L, h, P = D["latest"], D["headline"], D["projection"]
    bt, ar, pw, inc, co = D["backtest"], D["ardl"], D["power"], D["income"], D["cola"]
    lpr, lus = L["pr"], L["us"]
    pr_y = {r["year"]: r for r in P["pr_years"]}
    y_next, y_end = int(lpr[:4]) + 1, int(P["end"][:4])
    next5 = [pr_y[y]["c"] for y in range(y_next, y_end + 1)]
    avg5 = sum(next5) / len(next5)
    rm = bt["rmse"]
    inc_rows = inc["rows"]
    i0, i1 = inc_rows[0], inc_rows[-1]
    real_pr = 100 * (i1["pr_real"] / i0["pr_real"] - 1)
    real_us = 100 * (i1["us_real"] / i0["us_real"] - 1)
    ben = co["benefit"]
    groups = {g["key"]: g for g in D["groups"]}
    tr, ho, fo = groups["transport"], groups["housing"], groups["food"]
    above = h["pr_months_above"]
    spf = P["spf"] or {}

    lede_en = (f"In {men(lpr)}, consumer prices in Puerto Rico were {p_en(h['pr_yoy'])} higher than a year before; in the United States, {p_en(h['us_yoy'])}. "
               f"From January 2000 to {men(lpr)}, prices rose {p_en(h['cum2000']['pr'])} in Puerto Rico and {p_en(h['cum2000']['us'])} in the United States. "
               f"What markets and forecasters expect for US prices implies about {p_en(avg5)} a year for both from {y_next} to {y_end}, with a wide range.")
    lede_es = (f"En {mes(lpr)}, los precios al consumidor en Puerto Rico estaban {p_es(h['pr_yoy'])} más altos que un año antes; en Estados Unidos, {p_es(h['us_yoy'])}. "
               f"De enero de 2000 a {mes(lpr)}, los precios subieron {p_es(h['cum2000']['pr'])} en Puerto Rico y {p_es(h['cum2000']['us'])} en Estados Unidos. "
               f"Lo que los mercados y los pronosticadores esperan para los precios de EE. UU. implica cerca de {p_es(avg5)} al año para ambos de {y_next} a {y_end}, con un intervalo amplio.")

    page = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{t("Knowledge Area · Inflation", "Área de conocimiento · Inflación")}</title>
<meta name="description" content="{t("Inflation in Puerto Rico and the United States since 2000, by month and by year, what drives it, a projection to five years ahead with its error bands, and what it means for a person and a family.", "La inflación en Puerto Rico y en Estados Unidos desde 2000, por mes y por año, qué la mueve, una proyección a cinco años con sus bandas de error y lo que significa para una persona y una familia.")}">
<meta name="robots" content="noindex, nofollow">
<meta name="theme-color" content="#FFFFFF">
<link rel="icon" href="img/fpr-mark.png">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Material+Symbols+Rounded:opsz,wght,FILL,GRAD@24,400,1,0&icon_names={ICONS}&display=block">
<link rel="stylesheet" href="css/twin.css?v=63">
<link rel="stylesheet" href="css/housing.css?v=22">
<link rel="stylesheet" href="css/public_money.css?v=2">
<link rel="stylesheet" href="css/inflation.css?v=3">
<link rel="stylesheet" href="css/chat.css?v=5">
<link rel="stylesheet" href="css/ws.css?v=1">
<script src="js/i18n.js?v=74" data-page="inflation"></script>
</head>
<body class="research">
<a class="skip" href="#headline">{t("Skip to the content", "Ir al contenido")}</a>
<header class="topbar">
  <a class="logo" href="index.html" title="{t("PR Data Observatory home", "Inicio del Observatorio de Datos de PR")}"><img src="img/fpr-logo.png" alt="{t("Foundation for Puerto Rico. PR Data Observatory home", "Foundation for Puerto Rico. Inicio del Observatorio de Datos de PR")}"></a>
  <div class="brand"><b>{t("Knowledge Area · Inflation", "Área de conocimiento · Inflación")}</b><span>{t("Prices in Puerto Rico and the United States, a five-year projection and what it means for families", "Los precios en Puerto Rico y en Estados Unidos, una proyección a cinco años y lo que significa para las familias")}</span></div>
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
  <span class="ka-tabs" role="group" aria-label="{t("Knowledge Area", "Área de conocimiento")}" data-ka="inflation"></span><span class="ka-sep" aria-hidden="true"></span>
  <a href="#headline">{t("Puerto Rico and the US", "Puerto Rico y EE. UU.")}</a><a href="#years">{t("By year", "Por año")}</a><a href="#drivers">{t("What drives it", "Qué la mueve")}</a><a href="#people">{t("People and families", "Personas y familias")}</a><a href="#projection">{t("The projection", "La proyección")}</a><a href="#method">{t("Method", "Método")}</a><a href="#sources">{t("Sources", "Fuentes")}</a>
</nav>

<main class="page">
  <div class="note caution review-note" role="note" data-ka-note></div>

  <section class="hero" id="headline">
    <div class="eyebrow">{t("Knowledge Area · Economy", "Área de conocimiento · Economía")}</div>
    <h1>{t("Inflation in Puerto Rico and the United States", "La inflación en Puerto Rico y en Estados Unidos")}</h1>
    <p class="lede">{t(lede_en, lede_es)}</p>
    <div class="in-tiles">
      <div class="in-tile in-pr"><span>{t(f"Puerto Rico, 12 months to {men(lpr)}", f"Puerto Rico, 12 meses a {mes(lpr)}")}</span><b>{t(p_en(h['pr_yoy']), p_es(h['pr_yoy']))}</b></div>
      <div class="in-tile in-us"><span>{t(f"United States, 12 months to {men(lpr)}", f"Estados Unidos, 12 meses a {mes(lpr)}")}</span><b>{t(p_en(h['us_yoy']), p_es(h['us_yoy']))}</b></div>
      <div class="in-tile"><span>{t(f"Projected average, {y_next} to {y_end}", f"Promedio proyectado, {y_next} a {y_end}")}</span><b>{t(p_en(avg5), p_es(avg5))}</b><small>{t("both places; wide range below", "ambos lugares; intervalo amplio abajo")}</small></div>
      <div class="in-tile"><span>{t("Prices since January 2000", "Precios desde enero de 2000")}</span><b>{t(f"+{p_en(h['cum2000']['pr'], 0)} / +{p_en(h['cum2000']['us'], 0)}", f"+{p_es(h['cum2000']['pr'], 0)} / +{p_es(h['cum2000']['us'], 0)}")}</b><small>{t("Puerto Rico / United States", "Puerto Rico / Estados Unidos")}</small></div>
    </div>
    <div class="pm-controls">
      <label>{t("Start year", "Año inicial")} <select id="inFromSel"><option value="2000">2000</option><option value="2010">2010</option><option value="2020">2020</option></select></label>
      <label>{t("Bands", "Bandas")} <select id="inBands"><option value="pr">{t("Puerto Rico", "Puerto Rico")}</option><option value="us">{t("United States", "Estados Unidos")}</option><option value="both">{t("Both", "Ambos")}</option><option value="none">{t("None", "Ninguna")}</option></select></label>
      <button type="button" class="btn" id="inCsv"><span class="ms-icon" aria-hidden="true">download</span>{t("Download CSV", "Descargar CSV")}</button>
    </div>
    <div class="card pm-chart"><div id="inMain"></div>
      <div class="pm-legend"><span><i class="in-key" style="background:#2A2E2E"></i>{t("Puerto Rico (DTRH)", "Puerto Rico (DTRH)")}</span><span><i class="in-key" style="background:#205D7B"></i>{t("United States (BLS CPI-U)", "Estados Unidos (CPI-U del BLS)")}</span><span><i class="in-key in-dash"></i>{t("projected", "proyectado")}</span><span><i class="in-key in-band"></i>{t("80% and 95% bands", "bandas de 80 % y 95 %")}</span></div>
    </div>
    <p class="pm-small">{t(f"12-month change of the consumer price index, by month: Puerto Rico from January 2000 to {men(lpr)}, the United States to {men(lus)}. BLS did not publish October 2025, so the US rate for October 2026 is not shown. The bands are how far this method's forecasts have missed in the past (see The projection).", f"Cambio de 12 meses del índice de precios al consumidor, por mes: Puerto Rico desde enero de 2000 hasta {mes(lpr)}, Estados Unidos hasta {mes(lus)}. El BLS no publicó octubre de 2025, así que la tasa de EE. UU. de octubre de 2026 no aparece. Las bandas muestran cuánto han fallado en el pasado los pronósticos de este método (vea La proyección).")}</p>
    <div class="note"><b>{t("In short.", "En resumen.")}</b> {t(f"For most of the last 25 years Puerto Rico's measured inflation ran below the US rate: on average {p_en(h['avg2007']['pr'], 2)} a year against {p_en(h['avg2007']['us'], 2)} since the end of 2006. The two move together, because Puerto Rico uses the dollar, shares the Federal Reserve's policy and imports most of what it consumes. In {above} of the last 12 months, Puerto Rico's rate was the higher one, led by transportation ({p_en(tr['pr_yoy'])} over 12 months).", f"Durante la mayor parte de los últimos 25 años, la inflación medida de Puerto Rico estuvo por debajo de la de EE. UU.: en promedio {p_es(h['avg2007']['pr'], 2)} al año frente a {p_es(h['avg2007']['us'], 2)} desde finales de 2006. Las dos se mueven juntas, porque Puerto Rico usa el dólar, comparte la política de la Reserva Federal e importa la mayor parte de lo que consume. En {above} de los últimos 12 meses, la tasa de Puerto Rico fue la más alta, impulsada por la transportación ({p_es(tr['pr_yoy'])} en 12 meses).")}</div>
  </section>

  <section class="block" id="years">
    <h2><span class="ms-icon" aria-hidden="true">bar_chart</span>{t("1 · Inflation by year", "1 · La inflación por año")}</h2>
    <p class="pm-p">{t(f"The average inflation of each calendar year, {D['annual'][0]['year']} to {y_end}. The lighter bars are projected; their line is the 80% range. {lpr[:4]} has {pr_y[int(lpr[:4])]['observed_months']} months observed in Puerto Rico.", f"La inflación promedio de cada año natural, {D['annual'][0]['year']} a {y_end}. Las barras más claras son proyectadas; su línea es el intervalo de 80 %. {lpr[:4]} tiene {pr_y[int(lpr[:4])]['observed_months']} meses observados en Puerto Rico.")}</p>
    <div class="card pm-chart"><div id="inYears"></div></div>
    <div class="card pm-tablebox" id="inYearTable"></div>
  </section>

  <section class="block" id="drivers">
    <h2><span class="ms-icon" aria-hidden="true">pie_chart</span>{t("2 · What drives it", "2 · Qué la mueve")}</h2>
    <p class="pm-p">{t(f"The 8 major groups of each index. Since January 2020, housing prices rose {p_en(ho['pr_since2020'])} in Puerto Rico and {p_en(ho['us_since2020'])} in the United States; food, {p_en(fo['pr_since2020'])} and {p_en(fo['us_since2020'])}. Housing is where the two indexes differ most, and also where they measure most differently: the US index gives rent and the rent-equivalent of owned homes about a third of its weight.", f"Los 8 grupos principales de cada índice. Desde enero de 2020, los precios del alojamiento subieron {p_es(ho['pr_since2020'])} en Puerto Rico y {p_es(ho['us_since2020'])} en Estados Unidos; los alimentos, {p_es(fo['pr_since2020'])} y {p_es(fo['us_since2020'])}. El alojamiento es donde los dos índices difieren más, y también donde miden de forma más distinta: el índice de EE. UU. le da al alquiler y al alquiler equivalente de la vivienda propia cerca de un tercio de su peso.")}</p>
    <div class="card pm-tablebox" id="inGroups"></div>
    <div class="card pm-chart"><div id="inGroupBars"></div>
      <div class="pm-legend"><span><i class="in-key" style="background:#2A2E2E"></i>{t("Puerto Rico", "Puerto Rico")}</span><span><i class="in-key" style="background:#205D7B"></i>{t("United States", "Estados Unidos")}</span></div></div>
    <p class="pm-small">{t(f"The weights are the shares of spending in DTRH's basket (survey of 2000-01, the base of December 2006 = 100). The US groups are BLS's major groups of the CPI-U; their names match DTRH's, their contents are close but not identical. US 12-month changes are to {men(D['groups'][0]['us_yoy_month'])}.", f"Los pesos son las proporciones del gasto en la canasta del DTRH (encuesta de 2000-01, la base de diciembre de 2006 = 100). Los grupos de EE. UU. son los grupos principales del CPI-U del BLS; sus nombres coinciden con los del DTRH y su contenido es parecido, pero no idéntico. Los cambios de 12 meses de EE. UU. son a {mes(D['groups'][0]['us_yoy_month'])}.")}</p>
  </section>

  <section class="block" id="people">
    <h2><span class="ms-icon" aria-hidden="true">family_restroom</span>{t("3 · What it means for a person and a family", "3 · Lo que significa para una persona y una familia")}</h2>
    <div class="in-tiles">
      <div class="in-tile in-pr"><span>{t(f"What cost $100 in January 2000 costs, in Puerto Rico in {men(lpr)}", f"Lo que costaba $100 en enero de 2000 cuesta, en Puerto Rico en {mes(lpr)}")}</span><b>{t(d_en(pw['pr']['2000']['cost'], 2), d_es(pw['pr']['2000']['cost'], 2))}</b><small>{t(f"in the United States: {d_en(pw['us']['2000']['cost'], 2)}", f"en Estados Unidos: {d_es(pw['us']['2000']['cost'], 2)}")}</small></div>
      <div class="in-tile in-pr"><span>{t("What cost $100 in January 2020 costs now", "Lo que costaba $100 en enero de 2020 cuesta ahora")}</span><b>{t(d_en(pw['pr']['2020']['cost'], 2), d_es(pw['pr']['2020']['cost'], 2))}</b><small>{t(f"in the United States: {d_en(pw['us']['2020']['cost'], 2)}", f"en Estados Unidos: {d_es(pw['us']['2020']['cost'], 2)}")}</small></div>
      <div class="in-tile"><span>{t(f"What costs $100 today, projected for {men(P['end'])}", f"Lo que cuesta $100 hoy, proyectado para {mes(P['end'])}")}</span><b>{t(d_en(pw['pr']['proj']['cost'], 2), d_es(pw['pr']['proj']['cost'], 2))}</b><small>{t(f"80% range: {d_en(pw['pr']['proj']['lo80'])} to {d_en(pw['pr']['proj']['hi80'])}", f"Intervalo de 80 %: {d_es(pw['pr']['proj']['lo80'])} a {d_es(pw['pr']['proj']['hi80'])}")}</small></div>
    </div>
    <h3>{t("Income and prices", "Ingreso y precios")}</h3>
    <p class="pm-p">{t(f"The median household income in Puerto Rico was {d_en(i1['pr'])} in {i1['year']} ({d_en(i0['pr'])} in {i0['year']}); in the United States, {d_en(i1['us'])}. After removing each place's inflation, Puerto Rico's median rose {p_en(real_pr)} from {i0['year']} to {i1['year']} and the US median {p_en(real_us)}. Most of Puerto Rico's gain came after 2019. A median describes the middle household; many households saw less, and the figures are survey estimates with margins of error.", f"El ingreso mediano del hogar en Puerto Rico fue {d_es(i1['pr'])} en {i1['year']} ({d_es(i0['pr'])} en {i0['year']}); en Estados Unidos, {d_es(i1['us'])}. Al quitar la inflación de cada lugar, la mediana de Puerto Rico subió {p_es(real_pr)} de {i0['year']} a {i1['year']} y la de EE. UU., {p_es(real_us)}. La mayor parte del aumento de Puerto Rico ocurrió después de 2019. Una mediana describe el hogar del medio; muchos hogares vieron menos, y las cifras son estimados de una encuesta con márgenes de error.")}</p>
    <div class="card pm-chart"><div id="inIncome"></div></div>
    <div class="card pm-tablebox" id="inIncomeTable"></div>
    <h3 id="power"><span class="ms-icon" aria-hidden="true">savings</span>{t("Buying power by household income", "Poder de compra según el ingreso del hogar")}</h3>
    <p class="pm-p">{t(f"When prices rise and income does not, the same income buys less. Enter a household's yearly income; it starts at Puerto Rico's median household income in {i1['year']}, {d_en(i1['pr'])}, the latest from the Census Bureau. Choose a starting month to see what that income buys today at that month's prices, the raise it would need to buy the same, and how much more it would lose by {men(P['end'])} if it stays the same.", f"Cuando los precios suben y el ingreso no, el mismo ingreso compra menos. Escriba el ingreso anual de un hogar; empieza con el ingreso mediano del hogar en Puerto Rico en {i1['year']}, {d_es(i1['pr'])}, el más reciente del Negociado del Censo. Escoja un mes inicial para ver lo que ese ingreso compra hoy a precios de ese mes, el aumento que necesitaría para comprar lo mismo y cuánto más perdería para {mes(P['end'])} si no cambia.")}</p>
    <div class="pm-controls">
      <label>{t("Annual household income ($)", "Ingreso anual del hogar ($)")} <input id="inInc" type="number" min="0" step="1000" value="{round(i1['pr'])}" inputmode="decimal"></label>
      <label>{t("Since", "Desde")} <select id="inSince"></select></label>
      <button type="button" class="btn" id="inIncReset"><span class="ms-icon" aria-hidden="true">restart_alt</span>{t("Use the median", "Usar la mediana")}</button>
    </div>
    <div id="inPowerOut" aria-live="polite"></div>
    <p class="pm-small">{t(f"The median is the income of the household in the middle; it is used instead of the average because a few high incomes pull the average up. Every income loses the same share here, because there is one price index for all families. Lower-income households spend more of their income on food, housing, electricity and transportation, so when those prices rise faster (transportation: {p_en(tr['pr_yoy'])} over 12 months) they lose more; DTRH does not publish an index by income.", f"La mediana es el ingreso del hogar del medio; se usa en vez del promedio porque unos pocos ingresos altos suben el promedio. Aquí todo ingreso pierde la misma proporción, porque hay un solo índice de precios para todas las familias. Los hogares de menos ingreso gastan más de su ingreso en alimentos, vivienda, electricidad y transportación, así que cuando esos precios suben más rápido (transportación: {p_es(tr['pr_yoy'])} en 12 meses) pierden más; el DTRH no publica un índice por ingreso.")}</p>
    <h3 id="calc"><span class="ms-icon" aria-hidden="true">calculate</span>{t("Your budget", "Su presupuesto")}</h3>
    <p class="pm-p">{t("Enter what a household spent in a month and when. The calculator splits it among the 8 groups as DTRH's basket does, follows each group's prices in Puerto Rico to the latest month, and applies the projection to the total.", "Escriba lo que un hogar gastó en un mes y cuándo. La calculadora lo reparte entre los 8 grupos como lo hace la canasta del DTRH, sigue los precios de cada grupo en Puerto Rico hasta el mes más reciente y aplica la proyección al total.")}</p>
    <div class="pm-controls">
      <label>{t("Monthly spending ($)", "Gasto mensual ($)")} <input id="inAmt" type="number" min="0" step="50" value="2000" inputmode="decimal"></label>
      <label>{t("Spent in", "Gastado en")} <select id="inFrom"></select></label>
    </div>
    <div id="inCalcOut" aria-live="polite"></div>
    <p class="pm-small">{t("A household whose spending differs from the basket (more on rent, fuel or medicines, for example) saw a different change. The projection is for all items; the groups are not projected one by one.", "Un hogar cuyo gasto difiere de la canasta (más en alquiler, combustible o medicinas, por ejemplo) vio un cambio distinto. La proyección es para todos los artículos; los grupos no se proyectan uno por uno.")}</p>
    <h3><span class="ms-icon" aria-hidden="true">elderly</span>{t("Social Security in Puerto Rico", "El Seguro Social en Puerto Rico")}</h3>
    <p class="pm-p">{t(f"Social Security benefits rise each December by a cost-of-living adjustment set from the US consumer price index for wage earners (CPI-W), the same everywhere. Because Puerto Rico's prices rose less than US prices, the adjustments bought more in Puerto Rico: a benefit of $1,000 in January 2007 was {d_en(ben['now'], 2)} by {men(ben['month'])} after the adjustments; at Puerto Rico's prices of January 2007 that is {d_en(ben['real_pr'], 2)}, and at US prices {d_en(ben['real_us'], 2)}.", f"Los beneficios del Seguro Social suben cada diciembre por un ajuste por costo de vida que se fija con el índice de precios al consumidor de EE. UU. para asalariados (CPI-W), el mismo en todas partes. Como los precios de Puerto Rico subieron menos que los de EE. UU., los ajustes rindieron más en Puerto Rico: un beneficio de $1,000 en enero de 2007 era {d_es(ben['now'], 2)} en {mes(ben['month'])} después de los ajustes; a precios de Puerto Rico de enero de 2007 eso es {d_es(ben['real_pr'], 2)}, y a precios de EE. UU., {d_es(ben['real_us'], 2)}.")}</p>
    <div class="card pm-tablebox" id="inCola"></div>
    <p class="pm-small">{t("The adjustments are computed here from the CPI-W with Social Security's rule (the July to September average over the same months of the last year with an adjustment, rounded to a tenth of a point); they match the adjustments Social Security announced from 2007 to 2025.", "Los ajustes se calculan aquí con el CPI-W y la regla del Seguro Social (el promedio de julio a septiembre sobre los mismos meses del último año con ajuste, redondeado a una décima de punto); coinciden con los ajustes que anunció el Seguro Social de 2007 a 2025.")}</p>
  </section>

  <section class="block" id="projection">
    <h2><span class="ms-icon" aria-hidden="true">query_stats</span>{t("4 · The projection and how reliable it is", "4 · La proyección y cuán confiable es")}</h2>
    <p class="pm-p">{t(f"The central path for both places is the US consumer inflation that markets and forecasters expect, year by year: the Federal Reserve Bank of Cleveland's model of {men(P['origin']['cleveland'])}, which reads Treasury yields, inflation swaps and surveys. It expects {p_en(P['expected'][0], 2)} over the next year and {p_en(P['expected'][4], 2)} a year over five. The Survey of Professional Forecasters ({spf.get('quarter', '')}) expects {p_en(spf.get('cpi1', 0), 2)} over the next year and {p_en(spf.get('cpi10', 0), 2)} a year over ten.", f"La trayectoria central para ambos lugares es la inflación al consumidor de EE. UU. que esperan los mercados y los pronosticadores, año por año: el modelo de la Reserva Federal de Cleveland de {mes(P['origin']['cleveland'])}, que lee los rendimientos del Tesoro, los swaps de inflación y las encuestas. Espera {p_es(P['expected'][0], 2)} en el próximo año y {p_es(P['expected'][4], 2)} al año en cinco. La Encuesta de Pronosticadores Profesionales ({spf.get('quarter', '')}) espera {p_es(spf.get('cpi1', 0), 2)} en el próximo año y {p_es(spf.get('cpi10', 0), 2)} al año en diez.")}</p>
    <div class="card pm-tablebox in-narrow" id="inFwd"></div>
    <p class="pm-p">{t(f"Why use the US expectation for Puerto Rico? Five methods were tested the same way: a forecast from each quarter of {bt['origins'][0][:4]} to {bt['origins'][1][:4]}, using only what was known then, compared with Puerto Rico's actual inflation over the next one to five years. Following the US expectation had the smallest error at every horizon: {rm['us_expected']['5']:.2f} points over five years, against {rm['ardl']['5']:.2f} for a model fitted to Puerto Rico's own monthly data. That model finds that Puerto Rico's prices pass on US inflation about one for one (a long-run pass-through of {ar['pass_through']:.2f}), but its Puerto Rico-specific part did not help forecasts.", f"¿Por qué usar la expectativa de EE. UU. para Puerto Rico? Se probaron cinco métodos de la misma forma: un pronóstico desde cada trimestre de {bt['origins'][0][:4]} a {bt['origins'][1][:4]}, con solo lo que se sabía entonces, comparado con la inflación real de Puerto Rico en los próximos uno a cinco años. Seguir la expectativa de EE. UU. tuvo el menor error en cada horizonte: {rm['us_expected']['5']:.2f} puntos en cinco años, frente a {rm['ardl']['5']:.2f} de un modelo ajustado a los datos mensuales propios de Puerto Rico. Ese modelo encuentra que los precios de Puerto Rico trasladan la inflación de EE. UU. casi uno a uno (un traspaso de largo plazo de {ar['pass_through']:.2f}), pero su parte propia de Puerto Rico no ayudó a pronosticar.")}</p>
    <div class="card pm-tablebox" id="inBt"></div>
    <div class="note caution"><b>{t("Read the bands with care.", "Lea las bandas con cuidado.")}</b> {t(f"The 80% band is the central path plus or minus 1.28 times the root mean square error of the same method in the backtest, at each horizon; the 95% band, 1.96 times. For Puerto Rico's rate over the next year that error is about {P['rmse_year']['pr'][0]:.1f} points, so its 80% range is about ±{1.2816 * P['rmse_year']['pr'][0]:.1f} points. Most of that comes from 2021 and 2022, when inflation rose far above almost every forecast. The bands come from a short history and assume the future misses like the past; they are not a probability statement about any one year.", f"La banda de 80 % es la trayectoria central más o menos 1.28 veces la raíz del error cuadrático medio del mismo método en la prueba retrospectiva, en cada horizonte; la de 95 %, 1.96 veces. Para la tasa de Puerto Rico del próximo año ese error es cerca de {P['rmse_year']['pr'][0]:.1f} puntos, así que su intervalo de 80 % es cerca de ±{1.2816 * P['rmse_year']['pr'][0]:.1f} puntos. La mayor parte viene de 2021 y 2022, cuando la inflación subió muy por encima de casi todos los pronósticos. Las bandas vienen de una historia corta y suponen que el futuro falla como el pasado; no son una afirmación de probabilidad sobre un año en particular.")}</div>
    <div class="note"><b>{t("What would move the path.", "Qué movería la trayectoria.")}</b> {t(f"Fuel: transportation is {groups['transport']['weight']:.0f}% of Puerto Rico's basket, against about a sixth of the US index, and most of Puerto Rico's electricity is made from imported fuel, whose cost reaches bills through the fuel charge, so oil prices move Puerto Rico's rate further. Also electricity rates set by the Energy Bureau, shipping costs and federal tariffs on imports. A change in what markets expect from the Federal Reserve moves the central path of both places.", f"El combustible: la transportación es {groups['transport']['weight']:.0f} % de la canasta de Puerto Rico, frente a cerca de una sexta parte del índice de EE. UU., y la mayor parte de la electricidad de Puerto Rico se produce con combustible importado, cuyo costo llega a las facturas por el cargo de combustible, así que los precios del petróleo mueven más la tasa de Puerto Rico. También las tarifas de electricidad que fija el Negociado de Energía, los costos de transporte marítimo y los aranceles federales a las importaciones. Un cambio en lo que los mercados esperan de la Reserva Federal mueve la trayectoria central de ambos lugares.")}</div>
  </section>

  <section class="block" id="method">
    <h2><span class="ms-icon" aria-hidden="true">info</span>{t("Method", "Método")}</h2>
    <div class="note"><b>{t("The indexes.", "Los índices.")}</b> {t(f"Puerto Rico: the official consumer price index of the Department of Labor and Human Resources (DTRH), all families, base December 2006 = 100, not seasonally adjusted. From 2007 it is the 2010 revision, which averages prices within each item with a geometric mean; before 2007 it is DTRH's earlier index joined to the same base, whose rise from 2005 to 2008 partly reflects its old weights. United States: the BLS consumer price index for all urban consumers (CPI-U), US city average, not seasonally adjusted. The DTRH workbook and DTRH's file on indicadores.pr agree in {D['checks']['dtrh_overlap_months'] - len(D['checks']['dtrh_disagree'])} of {D['checks']['dtrh_overlap_months']} shared months.", f"Puerto Rico: el índice oficial de precios al consumidor del Departamento del Trabajo y Recursos Humanos (DTRH), todas las familias, base diciembre de 2006 = 100, sin ajuste estacional. Desde 2007 es la revisión de 2010, que promedia los precios dentro de cada artículo con una media geométrica; antes de 2007 es el índice anterior del DTRH unido a la misma base, cuyo aumento de 2005 a 2008 refleja en parte sus pesos viejos. Estados Unidos: el índice de precios al consumidor del BLS para todos los consumidores urbanos (CPI-U), promedio de ciudades de EE. UU., sin ajuste estacional. El libro del DTRH y el archivo del DTRH en indicadores.pr coinciden en {D['checks']['dtrh_overlap_months'] - len(D['checks']['dtrh_disagree'])} de {D['checks']['dtrh_overlap_months']} meses en común.")}</div>
    <div class="note"><b>{t("Not the same measurement.", "No es la misma medición.")}</b> {t("Part of the long-run gap between the two rates is how they measure, not only prices: the geometric mean gives a lower rate than BLS's mostly arithmetic one, DTRH's basket is from 2000-01 while BLS updates its weights every year, and rent and owners' rent-equivalent weigh much less in Puerto Rico's index.", "Parte de la brecha de largo plazo entre las dos tasas es cómo miden, no solo los precios: la media geométrica da una tasa más baja que la del BLS, mayormente aritmética; la canasta del DTRH es de 2000-01, mientras el BLS actualiza sus pesos cada año; y el alquiler y el alquiler equivalente de la vivienda propia pesan mucho menos en el índice de Puerto Rico.")}</div>
    <div class="note"><b>{t("The projection.", "La proyección.")}</b> {t(f"The Cleveland Fed's expected inflation over one to ten years is turned into the expected inflation of each single year ahead; each place's index is carried forward at those rates from its latest month, with its own seasonal pattern (the average change of each calendar month over the last ten years), so the 12-month rates show only real base effects. The model in the backtest is an ARDL of Puerto Rico's monthly change on its last month, US inflation this month and last month, and month dummies, from 2008 ({ar['n']} months). For each of the 44 origins, every method saw only data up to that month; the Cleveland Fed re-estimates its model with all data, so its past expectations are close to, but not exactly, what was known then.", f"La inflación esperada de la Reserva Federal de Cleveland a uno y hasta diez años se convierte en la inflación esperada de cada año hacia adelante; el índice de cada lugar se lleva hacia adelante a esas tasas desde su mes más reciente, con su propio patrón estacional (el cambio promedio de cada mes del año en los últimos diez años), así que las tasas de 12 meses muestran solo efectos base reales. El modelo de la prueba retrospectiva es un ARDL del cambio mensual de Puerto Rico sobre su mes anterior, la inflación de EE. UU. de este mes y del anterior, y variables por mes, desde 2008 ({ar['n']} meses). En cada uno de los 44 orígenes, cada método vio solo los datos hasta ese mes; la Reserva Federal de Cleveland reestima su modelo con todos los datos, así que sus expectativas pasadas son cercanas, pero no exactamente, a lo que se sabía entonces.")}</div>
    <div class="note"><b>{t("What the page does not do.", "Lo que la página no hace.")}</b> {t("It is not a forecast of FPR or of any agency. It does not project each group, municipio or kind of household, and it does not measure the cost of living in one place against another: an index measures change over time, not the level of prices.", "No es un pronóstico de FPR ni de ninguna agencia. No proyecta cada grupo, municipio ni tipo de hogar, y no compara el costo de vida de un lugar con otro: un índice mide el cambio en el tiempo, no el nivel de los precios.")}</div>
  </section>

  <section class="block" id="sources">
    <h2><span class="ms-icon" aria-hidden="true">menu_book</span>{t("Sources and licenses", "Fuentes y licencias")}</h2>
    <div class="note"><b>{t("Departamento del Trabajo y Recursos Humanos de Puerto Rico.", "Departamento del Trabajo y Recursos Humanos de Puerto Rico.")}</b> {t(f"Negociado de Estadísticas del Trabajo: Índice de Precios al Consumidor, Serie Histórica (mercadolaboral.pr.gov), to {men(lpr)}; and the index file and 2000-01 basket on indicadores.pr (Creative Commons Attribution).", f"Negociado de Estadísticas del Trabajo: Índice de Precios al Consumidor, Serie Histórica (mercadolaboral.pr.gov), hasta {mes(lpr)}; y el archivo del índice y la canasta de 2000-01 en indicadores.pr (Creative Commons Atribución).")}</div>
    <div class="note"><b>{t("US Bureau of Labor Statistics.", "Negociado de Estadísticas Laborales de EE. UU.")}</b> {t(f"Consumer Price Index, CPI-U and CPI-W, US city average, and the CPI-U major groups, from the public data API, to {men(lus)}, retrieved on {D['built']}. US Government work, public domain. BLS.gov cannot vouch for the data or analyses derived from these data after the data have been retrieved from BLS.gov.", f"Índice de Precios al Consumidor, CPI-U y CPI-W, promedio de ciudades de EE. UU., y los grupos principales del CPI-U, de la API pública de datos, hasta {mes(lus)}, obtenidos el {D['built']}. Obra del Gobierno de EE. UU., dominio público. BLS.gov no puede responder por los datos ni por los análisis derivados de ellos después de obtenidos de BLS.gov.")}</div>
    <div class="note"><b>{t("Federal Reserve Bank of Cleveland.", "Reserva Federal de Cleveland.")}</b> {t("Inflation expectations, model output 1982 to the present (doi 10.26509/frbc-infexp). Free to use with citation.", "Expectativas de inflación, resultados del modelo de 1982 al presente (doi 10.26509/frbc-infexp). Uso libre con cita.")}</div>
    <div class="note"><b>{t("Federal Reserve Bank of Philadelphia.", "Reserva Federal de Filadelfia.")}</b> {t("Survey of Professional Forecasters, median CPI inflation forecasts. Free to use with citation.", "Encuesta de Pronosticadores Profesionales, mediana de los pronósticos de inflación del CPI. Uso libre con cita.")}</div>
    <div class="note"><b>{t("U.S. Census Bureau.", "Negociado del Censo de EE. UU.")}</b> {t(f"American Community Survey 1-year estimates, table B19013, median household income, Puerto Rico and the United States, {i0['year']} to {i1['year']}. US Government work.", f"Estimados de 1 año de la Encuesta sobre la Comunidad, tabla B19013, ingreso mediano del hogar, Puerto Rico y Estados Unidos, {i0['year']} a {i1['year']}. Obra del Gobierno de EE. UU.")}</div>
    <div class="note"><b>{t("Data and method.", "Datos y método.")}</b> {t("The data file is data/inflation.json (inflation.py); the plan and the backtest are in docs/inflation-plan-2026-11.md of the project repository.", "El archivo de datos es data/inflation.json (inflation.py); el plan y la prueba retrospectiva están en docs/inflation-plan-2026-11.md del repositorio del proyecto.")}</div>
    <div class="note"><b>{t("How to cite this page.", "Cómo citar esta página.")}</b> {t(f"Foundation for Puerto Rico, Knowledge Area: Inflation, PR Data Observatory, {men(lpr)} data (draft). Data: DTRH, US Bureau of Labor Statistics, Federal Reserve Banks of Cleveland and Philadelphia, U.S. Census Bureau.", f"Foundation for Puerto Rico, Área de conocimiento: Inflación, Observatorio de Datos de PR, datos de {mes(lpr)} (borrador). Datos: DTRH, Negociado de Estadísticas Laborales de EE. UU., Reservas Federales de Cleveland y Filadelfia, Negociado del Censo de EE. UU.")}</div>
  </section>
</main>
<script src="js/core/knowledge.js?v=35"></script>
<script>Core.knowledge.render(); I18N.apply();</script>
<script src="js/common.js?v=20"></script>
<script src="js/inflation.js?v=2"></script>
<script src="js/chatboot.js?v=45"></script>
</body>
</html>
"""
    for m in re.finditer(r"<b>([^<]*)</b> ([^<]*)</(?:div|p)>", page):
        lead, body = " ".join(html.unescape(m.group(1)).split()), " ".join(html.unescape(m.group(2)).split())
        key = " ".join(f"<b>{m.group(1)}</b> {m.group(2)}".split())
        ES[key] = f"<b>{html.escape(ES[lead], quote=False)}</b> {html.escape(ES[body], quote=False)}"
        ES.pop(lead, None)
        ES.pop(body, None)
    (ROOT / "site" / "inflation.html").write_text(page, encoding="utf-8", newline="\n")
    es = {"_about": "The Inflation page of the Knowledge Area (inflation.html) and site/js/inflation.js. Written by docs/analysis/inflation-2026-11/make_page.py from its (English, Spanish) pairs: edit them there, not here."}
    es.update(ES)
    (ROOT / "i18n_src" / "es" / "inflation.json").write_text(json.dumps(es, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(f"wrote site/inflation.html and i18n_src/es/inflation.json ({len(ES)} strings)")


if __name__ == "__main__":
    build()
