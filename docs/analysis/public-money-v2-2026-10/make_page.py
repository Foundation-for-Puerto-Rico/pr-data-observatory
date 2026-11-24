"""Writes the Knowledge Area page "Disaster funding and need" (site/public-money.html) and its Spanish (i18n_src/es/public_money.json).

  python docs/analysis/public-money-v2-2026-10/make_page.py   read site/data/public_money_need.json (python public_money_need.py makes it); write the page
                                                              and the Spanish of the page and of site/js/public_money.js. Then run python i18n.py.

The page follows the site's language rule (docs/i18n.md): the HTML is in English and every English string is its own key; I18N.apply() puts the
Spanish on the static text and public_money.js asks T() for the rest. Every string is written once, as an (English, Spanish) pair, so the two files
cannot drift apart, and every figure in the text is read from the data file, so no number is typed by hand (as on the Women in the labor force page).
Public money v2, step 5 (HANDOFF decision 72). The page states facts and draws no conclusions; it carries no headline figure (decision 21).
HUD's CDBG-DR, CDBG-MIT and yearly CDBG money were added under decision 100 (2026-11-12). A string that names CDBG or HUD keeps its Spanish in
i18n_src/held_for_review.json and shows English on the Spanish page until Finance and Compliance review it (decision 21), as on the Public spending page.
Prepared with Claude (AI) for FPR, 2026-10-31.
"""
import html
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))
import public_money_need as P  # noqa: E402

ES = {}
HELD = {}   # strings about federal grant work: the Spanish page shows English until Finance and Compliance review them (docs/i18n.md, decision 21)
HOLD = re.compile(r"CDBG|LIHTC|WCRP|\bHUD\b", re.I)
MONTHS_ES = dict(zip("January February March April May June July August September October November December".split(),
                     "enero febrero marzo abril mayo junio julio agosto septiembre octubre noviembre diciembre".split()))


def t(en, es):
    """An English string and its Spanish; returns the English (escaped), for the page."""
    key, es = " ".join(en.split()), " ".join(es.split())
    if HOLD.search(key) or HOLD.search(es):
        HELD[key] = es
        es = key
    if key in ES and ES[key] != es:
        raise SystemExit(f"two Spanish texts for {key!r}")
    ES[key] = es
    return html.escape(key, quote=False)


def bn(x):
    return f"{x / 1e9:.2f}"


# Strings public_money.js asks T() for (the same English keys as in the script)
JS = [
    ("The data could not be loaded ({error}). Check your connection and reload.", "No se pudieron cargar los datos ({error}). Verifique su conexión y vuelva a cargar la página."),
    ("billion", "mil millones"), ("million", "millones"),
    ("FEMA Public Assistance obligated", "Asistencia Pública de FEMA obligada"),
    ("FEMA Individual Assistance approved", "Asistencia Individual de FEMA aprobada"),
    ("FEMA Hazard Mitigation approved", "Mitigación de Riesgos de FEMA aprobada"),
    ("The three FEMA programs together", "Los tres programas de FEMA juntos"),
    ("HUD CDBG-DR and CDBG-MIT subawards", "Subadjudicaciones CDBG-DR y CDBG-MIT de HUD"),
    ("HUD CDBG yearly grants", "Subvenciones anuales CDBG de HUD"),
    ("{a} to {b}", "{a} a {b}"),
    ("CDBG-DR and CDBG-MIT subawards", "Subadjudicaciones CDBG-DR y CDBG-MIT"),
    ("CDBG-DR and CDBG-MIT, per resident", "CDBG-DR y CDBG-MIT, por residente"),
    ("CDBG entitlement grant", "Subvención CDBG de derecho (entitlement)"),
    ("CDBG state program subawards", "Subadjudicaciones del programa estatal CDBG"),
    ("CDBG yearly grants, per resident", "Subvenciones anuales CDBG, por residente"),
    ("Puerto Rico (the prime grants, with what is not placed)", "Puerto Rico (las subvenciones principales, con lo que no está ubicado)"),
    ("HUD CDBG-DR, CDBG-MIT and yearly CDBG by municipio, federal fiscal years {y}", "CDBG-DR, CDBG-MIT y CDBG anual de HUD por municipio, años fiscales federales {y}"),
    ("Expected annual loss from natural hazards, per resident", "Pérdida anual esperada por amenazas naturales, por residente"),
    ("Residents with three or more risk factors", "Residentes con tres o más factores de riesgo"),
    ("lower third", "tercio inferior"), ("middle third", "tercio medio"), ("upper third", "tercio superior"),
    ("Money: {m}. Need: {n}.", "Dinero: {m}. Necesidad: {n}."),
    ("{name}: {money} per resident; {need}. {cell} Select for the figures.", "{name}: {money} por residente; {need}. {cell} Seleccione para ver las cifras."),
    ("Bivariate map: {money} and {need}, by municipio", "Mapa bivariado: {money} y {need}, por municipio"),
    ("Need", "Necesidad"), ("Money", "Dinero"),
    ("Key: money per resident in thirds, from bottom to top, and need in thirds, from left to right; each square says how many municipios",
     "Leyenda: dinero por residente en tercios, de abajo hacia arriba, y necesidad en tercios, de izquierda a derecha; cada cuadro dice cuántos municipios"),
    ("Each square counts the municipios. Thirds of money per resident: below {a}, from {a} to below {b}, {b} or more. Thirds of need: below {c}, from {c} to below {d}, {d} or more.",
     "Cada cuadro cuenta los municipios. Tercios de dinero por residente: menos de {a}, de {a} a menos de {b}, {b} o más. Tercios de necesidad: menos de {c}, de {c} a menos de {d}, {d} o más."),
    ("Puerto Rico", "Puerto Rico"),
    ("Select a municipio on the map or in the chart for its figures.", "Seleccione un municipio en el mapa o en la gráfica para ver sus cifras."),
    ("Residents (2020 Census)", "Residentes (Censo 2020)"),
    ("{total} ({per} per resident)", "{total} ({per} por residente)"),
    ("Back to Puerto Rico", "Volver a Puerto Rico"),
    ("Median money per resident", "Mediana del dinero por residente"), ("Median need", "Mediana de la necesidad"),
    ("Rank correlation (Spearman) between the two", "Correlación de rangos (Spearman) entre ambos"),
    ("A rank correlation near 0 means the order of the municipios by money says little about their order by need; near 1, the two orders agree; below 0, they run opposite.",
     "Una correlación de rangos cercana a 0 significa que el orden de los municipios por dinero dice poco sobre su orden por necesidad; cercana a 1, ambos órdenes coinciden; menor que 0, van en sentido contrario."),
    ("{money}, per resident", "{money}, por residente"),
    ("{name}: {money} per resident; {need}", "{name}: {money} por residente; {need}"),
    ("Scatter plot: each dot is a municipio; dashed lines mark the medians", "Gráfica de dispersión: cada punto es un municipio; las líneas discontinuas marcan las medianas"),
    ("Above the median in money and in need: {hh} municipios. Above in money, below in need: {hl}. Below in money, above in need: {lh}. Below in both: {ll}. Rank correlation: {rho}.",
     "Sobre la mediana en dinero y en necesidad: {hh} municipios. Sobre la mediana en dinero y bajo ella en necesidad: {hl}. Bajo la mediana en dinero y sobre ella en necesidad: {lh}. Bajo la mediana en ambos: {ll}. Correlación de rangos: {rho}."),
    ("{p} of {total}", "{p} de {total}"),
    ("Share of each program placed in a municipio", "Parte de cada programa ubicada en un municipio"),
    ("placed in a municipio (on the map)", "ubicado en un municipio (en el mapa)"),
    ("recorded as statewide or not placed", "registrado como estatal o sin ubicar"),
    ("Municipio", "Municipio"), ("Federal share approved", "Parte federal aprobada"), ("Federal money obligated", "Dinero federal obligado"),
    ("Obligated as a share of approved", "Obligado como parte de lo aprobado"), ("Awaiting a FEMA decision", "En espera de una decisión de FEMA"),
    ("Approved subapplications", "Subsolicitudes aprobadas"),
    ("Puerto Rico (its own total, with what is statewide)", "Puerto Rico (su propio total, con lo estatal)"),
    ("FEMA Hazard Mitigation by benefiting municipio, fiscal years 2017 to 2025", "Mitigación de Riesgos de FEMA por municipio beneficiado, años fiscales 2017 a 2025"),
    ("Expected annual loss from natural hazards ($ a year)", "Pérdida anual esperada por amenazas naturales ($ al año)"),
    ("Third of money (1 to 3)", "Tercio de dinero (1 a 3)"), ("Third of need (1 to 3)", "Tercio de necesidad (1 a 3)"),
]
for en, es in JS:
    t(en, es)


def build():
    D = json.loads((ROOT / "site" / "data" / "public_money_need.json").read_text(encoding="utf-8"))
    I, H, N, U = D["island"], D["hma_island"], D["notes"], D["cdbg_parts"]
    u0, u1 = D["money_years"]["cdbg"]
    if D["money_years"]["cdbg_dr"] != [u0, u1]:
        raise SystemExit("make_page: the two HUD files cover different years")
    share = {k: 100 * v["placed"] / v["total"] for k, v in I.items()}
    y0, y1 = D["years"]["first"], D["years"]["last"]
    nri, cre = D["need_year"]["eal"], D["need_year"]["cre3"]
    nri_es = " de ".join([MONTHS_ES.get(nri.split()[0], nri.split()[0]), *nri.split()[1:]])   # "December 2025" -> "diciembre de 2025"
    obl = 100 * H["obligated"] / H["approved"]

    page = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{t("Knowledge Area · Disaster funding and need", "Área de conocimiento · Fondos por desastres y necesidad")}</title>
<meta name="description" content="{t("Federal disaster and community development money per resident by municipio, set next to two measures of need: expected loss from natural hazards and residents with three or more risk factors. Facts only, with what the data can and cannot place.", "El dinero federal para desastres y desarrollo comunitario por residente en cada municipio, junto a dos medidas de necesidad: la pérdida esperada por amenazas naturales y los residentes con tres o más factores de riesgo. Solo hechos, con lo que los datos pueden y no pueden ubicar.")}">
<meta name="robots" content="noindex, nofollow">
<meta name="theme-color" content="#FFFFFF">
<link rel="icon" href="img/fpr-mark.png">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Material+Symbols+Rounded:opsz,wght,FILL,GRAD@24,400,1,0&icon_names=account_balance,bolt,chat_bubble,close,commute,delete,diversity_3,download,home_work,hourglass_bottom,info,lightbulb,map,menu_book,payments,pie_chart,price_change,rocket_launch,route,scatter_plot,school,send,table_view,thermostat,view_in_ar,warning,water,wifi,woman,work&display=block">
<link rel="stylesheet" href="css/twin.css?v=62">
<link rel="stylesheet" href="css/housing.css?v=21">
<link rel="stylesheet" href="css/public_money.css?v=1">
<link rel="stylesheet" href="css/chat.css?v=4">
<script src="js/i18n.js?v=85" data-page="publicmoney"></script>
</head>
<body class="research">
<a class="skip" href="#compare">{t("Skip to the content", "Ir al contenido")}</a>
<header class="topbar">
  <a class="logo" href="index.html" title="{t("PR Data Observatory home", "Inicio del Observatorio de Datos de PR")}"><img src="img/fpr-logo.png" alt="{t("Foundation for Puerto Rico. PR Data Observatory home", "Foundation for Puerto Rico. Inicio del Observatorio de Datos de PR")}"></a>
  <div class="brand"><b>{t("Knowledge Area · Disaster funding and need", "Área de conocimiento · Fondos por desastres y necesidad")}</b><span>{t("Federal disaster and community development money and two measures of need, by municipio", "El dinero federal para desastres y desarrollo comunitario y dos medidas de necesidad, por municipio")}</span></div>
  <div class="spacer"></div>
  <nav class="views" aria-label="{t("Views", "Vistas")}">
    <a class="btn" href="index.html"><span class="ms-icon" aria-hidden="true">map</span><span class="lbl">{t("Map", "Mapa")}</span></a>
    <a class="btn" href="3d.html" title="{t("Immersive 3D + time view", "Vista inmersiva en 3D y tiempo")}"><span class="ms-icon" aria-hidden="true">view_in_ar</span><span class="lbl">{t("3D + Time", "3D + Tiempo")}</span></a>
    <a class="btn" href="knowledge.html" aria-current="page" title="{t("Knowledge: FPR studies, analyses and tools", "Conocimiento: estudios, análisis y herramientas de FPR")}"><span class="ms-icon" aria-hidden="true">lightbulb</span><span class="lbl">{t("Knowledge", "Conocimiento")}</span></a>
    <a class="btn" href="dictionary.html" title="{t("Data dictionary: meanings, sources, licenses, how to cite", "Diccionario de datos: significados, fuentes, licencias y cómo citar")}"><span class="ms-icon" aria-hidden="true">menu_book</span><span class="lbl">{t("Data dictionary", "Diccionario de datos")}</span></a>
    <a class="btn" href="learn.html" title="{t("Learn: short lessons about maps and spatial analysis", "Aprende: lecciones cortas sobre mapas y análisis espacial")}"><span class="ms-icon" aria-hidden="true">school</span><span class="lbl">{t("Learn", "Aprende")}</span></a>
  </nav>
</header>

<nav class="toc" id="toc" aria-label="{t("On this page", "En esta página")}">
  <span class="ka-tabs" role="group" aria-label="{t("Knowledge Area", "Área de conocimiento")}" data-ka="publicmoney"></span><span class="ka-sep" aria-hidden="true"></span>
  <a href="#compare">{t("Money and need", "Dinero y necesidad")}</a><a href="#scatter">{t("Municipio by municipio", "Municipio por municipio")}</a><a href="#placed">{t("What the map can show", "Lo que el mapa puede mostrar")}</a><a href="#mitigation">{t("Hazard Mitigation", "Mitigación de Riesgos")}</a><a href="#hud">{t("HUD grants", "Subvenciones de HUD")}</a><a href="#method">{t("Method", "Método")}</a><a href="#sources">{t("Sources", "Fuentes")}</a>
</nav>

<main class="page">
  <div class="note caution review-note" role="note" data-ka-note></div>

  <section class="hero" id="compare">
    <div class="eyebrow">{t("Knowledge Area · Public money", "Área de conocimiento · Dinero público")}</div>
    <h1>{t("Disaster funding and need by municipio", "Fondos por desastres y necesidad por municipio")}</h1>
    <p class="lede">{t(f"Where federal disaster money per resident and two measures of need line up, and where they do not. The FEMA money is what FEMA obligated or approved for disasters declared, or grants of fiscal years, {y0} to {y1}; it is divided by each municipio's residents in the 2020 Census. COVID-19 relief is not included.", f"Dónde coinciden el dinero federal para desastres por residente y dos medidas de necesidad, y dónde no. El dinero de FEMA es lo que FEMA obligó o aprobó para desastres declarados, o subvenciones de los años fiscales, de {y0} a {y1}; se divide entre los residentes de cada municipio en el Censo 2020. No incluye la ayuda por el COVID-19.")}</p>
    <p class="pm-p">{t(f"The page also shows HUD's Community Development Block Grants (CDBG): the disaster recovery and mitigation grants (CDBG-DR and CDBG-MIT) and the yearly grants, as obligated in federal fiscal years {u0} to {u1}. HUD's money is never added to FEMA's: the years are counted differently. Pick it under Money, or see section 4.", f"La página también muestra las Subvenciones en Bloque para el Desarrollo Comunitario (CDBG) de HUD: las de recuperación y mitigación por desastres (CDBG-DR y CDBG-MIT) y las anuales, según se obligaron en los años fiscales federales {u0} a {u1}. El dinero de HUD nunca se suma al de FEMA: los años se cuentan de otra forma. Selecciónelo en Dinero o vea la sección 4.")}</p>
    <div class="pm-controls">
      <label>{t("Money", "Dinero")} <select id="pmMoney"></select></label>
      <label>{t("Need", "Necesidad")} <select id="pmNeed"></select></label>
      <button type="button" class="btn" id="pmCsv"><span class="ms-icon" aria-hidden="true">download</span>{t("Download CSV", "Descargar CSV")}</button>
    </div>
    <div class="pm-maprow">
      <div class="card pm-map"><div id="pmMap"></div><div class="pm-keyrow"><div id="pmKey"></div></div></div>
      <div class="card pm-place" id="pmPlace" aria-live="polite"></div>
    </div>
    <p class="pm-small">{t("Each municipio falls in a third (tercile) of the 78 by money per resident and in a third by need, so the map has nine colours. Dark red: more need and less money than most; blue: more money and less need; dark brown: high in both. The colour compares municipios with each other, not with a standard of what is enough.", "Cada municipio cae en un tercio (tercil) de los 78 por dinero por residente y en un tercio por necesidad, así que el mapa tiene nueve colores. Rojo oscuro: más necesidad y menos dinero que la mayoría; azul: más dinero y menos necesidad; marrón oscuro: alto en ambos. El color compara los municipios entre sí, no con una norma de lo que es suficiente.")}</p>
    <div class="note caution"><b>{t("Read with care.", "Lea con cuidado.")}</b> {t(f"This page states facts and draws no conclusions. Money obligated or approved is not money spent. Most FEMA Public Assistance cannot be placed in a municipio: {share['pa']:.0f}% of it is on this map, the rest is recorded as statewide (power, water and Commonwealth agencies). Expected annual loss is a model estimate, not a record of losses. A municipio can rank high on money because of one large project.", f"Esta página presenta hechos y no saca conclusiones. El dinero obligado o aprobado no es dinero gastado. La mayor parte de la Asistencia Pública de FEMA no se puede ubicar en un municipio: el {share['pa']:.0f} % está en este mapa; el resto se registra como estatal (energía, agua y agencias del Gobierno de Puerto Rico). La pérdida anual esperada es un estimado de un modelo, no un registro de pérdidas. Un municipio puede quedar alto en dinero por un solo proyecto grande.")}</div>
  </section>

  <section class="block" id="scatter">
    <h2><span class="ms-icon" aria-hidden="true">scatter_plot</span>{t("1 · Municipio by municipio", "1 · Municipio por municipio")}</h2>
    <p class="pm-p">{t("Each dot is a municipio, in the colour it has on the map. Need runs across and money per resident runs up, on a scale where each step is ten times the one below, because a few municipios have many times the median; values under $10 are drawn at $10. The dashed lines are the medians of the 78. Select a dot to see the municipio's figures.", "Cada punto es un municipio, con el color que tiene en el mapa. La necesidad va de izquierda a derecha y el dinero por residente de abajo hacia arriba, en una escala donde cada paso es diez veces el de abajo, porque unos pocos municipios tienen muchas veces la mediana; los valores menores de 10 $ se dibujan en 10 $. Las líneas discontinuas son las medianas de los 78. Seleccione un punto para ver las cifras del municipio.")}</p>
    <div class="card pm-chart"><div id="pmScatter"></div></div>
    <div class="note" id="pmRead" data-t="skip"></div>
  </section>

  <section class="block" id="placed">
    <h2><span class="ms-icon" aria-hidden="true">pie_chart</span>{t("2 · What a municipio map can show", "2 · Lo que un mapa por municipio puede mostrar")}</h2>
    <p class="pm-p">{t(f"FEMA records Public Assistance by the applicant. When the applicant is the Puerto Rico Electric Power Authority, the Aqueduct and Sewer Authority or another Commonwealth agency, the money is recorded for the whole island and cannot be placed in a municipio. Individual Assistance is placed by the household's address. Hazard Mitigation is placed by the municipios a project benefits; a project that benefits several is split equally among them. Each bar shows its own years:", f"FEMA registra la Asistencia Pública por el solicitante. Cuando el solicitante es la Autoridad de Energía Eléctrica, la Autoridad de Acueductos y Alcantarillados u otra agencia del Gobierno de Puerto Rico, el dinero se registra para toda la isla y no se puede ubicar en un municipio. La Asistencia Individual se ubica por la dirección del hogar. La Mitigación de Riesgos se ubica por los municipios que beneficia un proyecto; un proyecto que beneficia a varios se divide en partes iguales entre ellos. Cada barra muestra sus propios años:")}</p>
    <div class="card pm-chart"><div id="pmPlaced"></div></div>
    <p class="pm-small">{t("HUD's grants are placed through the subawards the Puerto Rico Department of Housing reports, and the yearly entitlement grants through the municipio that receives them. Money the Department keeps for its own programs, has not passed on yet, or reports with no municipio is not placed.", "Las subvenciones de HUD se ubican por las subadjudicaciones que informa el Departamento de la Vivienda de Puerto Rico, y las subvenciones anuales de derecho (entitlement) por el municipio que las recibe. El dinero que el Departamento conserva para sus propios programas, aún no ha transferido o informa sin municipio no está ubicado.")}</p>
  </section>

  <section class="block" id="mitigation">
    <h2><span class="ms-icon" aria-hidden="true">table_view</span>{t("3 · Hazard Mitigation: approved, obligated and awaiting a decision", "3 · Mitigación de Riesgos: aprobado, obligado y en espera de decisión")}</h2>
    <p class="pm-p">{t(f"Hazard Mitigation pays for projects and plans that reduce future disaster losses. For fiscal years {y0} to {y1}, FEMA approved a federal share of ${bn(H['approved'])} billion for Puerto Rico and has obligated ${bn(H['obligated'])} billion of it ({obl:.0f}%); FEMA obligates money in steps as projects meet their milestones. Another ${bn(H['pending'])} billion has been requested and awaits a FEMA decision. Of the {N['hma_subapplications']:,} Hazard Mitigation subapplications FEMA lists for Puerto Rico in all years and statuses, it reports a payment for {N['hma_payment_reported']}, too few to show money paid. Select a column heading to sort.", f"La Mitigación de Riesgos paga proyectos y planes que reducen las pérdidas de desastres futuros. Para los años fiscales {y0} a {y1}, FEMA aprobó una parte federal de {bn(H['approved'])} mil millones de dólares para Puerto Rico y ha obligado {bn(H['obligated'])} mil millones ({obl:.0f} %); FEMA obliga el dinero por etapas, según los proyectos cumplen sus hitos. Otros {bn(H['pending'])} mil millones se han solicitado y esperan una decisión de FEMA. De las {N['hma_subapplications']:,} subsolicitudes de Mitigación de Riesgos que FEMA lista para Puerto Rico en todos los años y estados, informa un pago para {N['hma_payment_reported']}, muy pocas para mostrar el dinero pagado. Seleccione el título de una columna para ordenar.")}</p>
    <div class="card pm-tablebox" id="pmHma"></div>
  </section>

  <section class="block" id="hud">
    <h2><span class="ms-icon" aria-hidden="true">home_work</span>{t("4 · HUD grants: CDBG-DR, CDBG-MIT and yearly CDBG", "4 · Subvenciones de HUD: CDBG-DR, CDBG-MIT y CDBG anual")}</h2>
    <p class="pm-p">{t(f"HUD's Community Development Block Grants reach Puerto Rico in three ways. The disaster recovery and mitigation grants (CDBG-DR and CDBG-MIT) go to the Puerto Rico Department of Housing: HUD obligated ${bn(I['cdbg_dr']['total'])} billion of them in federal fiscal years {u0} to {u1}, and the Department reported ${bn(U['dr_subawards'])} billion in subawards to municipalities, contractors and nonprofits, ${bn(I['cdbg_dr']['placed'])} billion of it with a municipio. The yearly grants go straight from HUD to {U['entitlement_municipios']} larger municipios (entitlement grants, ${U['entitlement_total'] / 1e6:.0f} million) and, for the other municipios, to the Department of Housing as the CDBG state program (${U['state_prime'] / 1e6:.0f} million), which passes it on as subawards. Subawards often arrive a year or more after the grant, so the latest year can show little. Obligated is not spent. Select a column heading to sort.", f"Las Subvenciones en Bloque para el Desarrollo Comunitario de HUD llegan a Puerto Rico de tres formas. Las de recuperación y mitigación por desastres (CDBG-DR y CDBG-MIT) van al Departamento de la Vivienda de Puerto Rico: HUD obligó {bn(I['cdbg_dr']['total'])} mil millones de dólares en los años fiscales federales {u0} a {u1}, y el Departamento informó {bn(U['dr_subawards'])} mil millones en subadjudicaciones a municipios, contratistas y organizaciones sin fines de lucro, {bn(I['cdbg_dr']['placed'])} mil millones con un municipio. Las anuales van directo de HUD a {U['entitlement_municipios']} municipios más grandes (subvenciones de derecho o entitlement, {U['entitlement_total'] / 1e6:.0f} millones) y, para los demás municipios, al Departamento de la Vivienda como programa estatal CDBG ({U['state_prime'] / 1e6:.0f} millones), que las transfiere como subadjudicaciones. Las subadjudicaciones suelen llegar un año o más después de la subvención, así que el último año puede mostrar poco. Obligado no es gastado. Seleccione el título de una columna para ordenar.")}</p>
    <div class="card pm-tablebox" id="pmHud"></div>
  </section>

  <section class="block" id="method">
    <h2><span class="ms-icon" aria-hidden="true">info</span>{t("Method", "Método")}</h2>
    <div class="note"><b>{t("Money per resident.", "Dinero por residente.")}</b> {t(f"For each municipio, the dollars of each program from {y0} to {y1} are added, then divided by its residents in the 2020 Census. Public Assistance: federal share obligated, by applicant and the year the disaster was declared. Individual Assistance: dollars approved for owners and renters, by the year the disaster was declared. Hazard Mitigation: federal share approved, by benefiting municipio and fiscal year of the grant. The three FEMA programs together add the three; approved and obligated are different steps, so the sum is a rough total.", f"Para cada municipio se suman los dólares de cada programa de {y0} a {y1} y se dividen entre sus residentes en el Censo 2020. Asistencia Pública: parte federal obligada, por solicitante y el año en que se declaró el desastre. Asistencia Individual: dólares aprobados para dueños e inquilinos, por el año en que se declaró el desastre. Mitigación de Riesgos: parte federal aprobada, por municipio beneficiado y año fiscal de la subvención. Los tres programas de FEMA juntos suman los tres; aprobado y obligado son pasos distintos, así que la suma es un total aproximado.")}</div>
    <div class="note"><b>{t("HUD money per resident.", "Dinero de HUD por residente.")}</b> {t(f"The same 2020 Census residents, over federal fiscal years {u0} to {u1} (October to September), by the year HUD obligated the money. CDBG-DR and CDBG-MIT: the subawards of the Department of Housing's disaster grants, by the municipio where the work is done. Yearly CDBG: the entitlement grants by the municipio that receives them, plus the CDBG state program's subawards by municipio; COVID-19 grants (CDBG-CV) are left out. Subawards are part of the prime grants and are never added to them, nor to FEMA's money.", f"Los mismos residentes del Censo 2020, en los años fiscales federales {u0} a {u1} (octubre a septiembre), por el año en que HUD obligó el dinero. CDBG-DR y CDBG-MIT: las subadjudicaciones de las subvenciones por desastre del Departamento de la Vivienda, por el municipio donde se hace el trabajo. CDBG anual: las subvenciones de derecho (entitlement) por el municipio que las recibe, más las subadjudicaciones del programa estatal CDBG por municipio; se excluyen las subvenciones del COVID-19 (CDBG-CV). Las subadjudicaciones son parte de las subvenciones principales y nunca se suman a ellas ni al dinero de FEMA.")}</div>
    <div class="note"><b>{t("Need.", "Necesidad.")}</b> {t(f"Expected annual loss: FEMA's National Risk Index ({nri}) estimate of the average dollars lost each year to buildings, agriculture and lives from 18 natural hazards, divided by residents. It is higher where there is more to lose, so it reflects the value of what is exposed as well as the hazard. Residents with three or more risk factors: the Census Bureau's Community Resilience Estimates ({cre}), the share of residents with three or more of ten factors such as poverty, disability, no vehicle or no health insurance. The two measures are never combined.", f"Pérdida anual esperada: el estimado del Índice Nacional de Riesgo de FEMA ({nri_es}) del promedio de dólares que se pierden cada año en edificios, agricultura y vidas por 18 amenazas naturales, dividido entre los residentes. Es mayor donde hay más que perder, así que refleja el valor de lo expuesto además de la amenaza. Residentes con tres o más factores de riesgo: las Estimaciones de Resiliencia Comunitaria del Negociado del Censo ({cre}), la parte de los residentes con tres o más de diez factores, como pobreza, discapacidad, no tener vehículo o no tener seguro médico. Las dos medidas nunca se combinan.")}</div>
    <div class="note"><b>{t("Thirds and medians.", "Tercios y medianas.")}</b> {t("The 78 municipios are ranked on each measure and cut into three groups of 26 (terciles). The rank correlation (Spearman) compares the two orders: 1 when they agree, 0 when they are unrelated, below 0 when they run opposite. The medians split the 78 into two halves of 39.", "Los 78 municipios se ordenan en cada medida y se dividen en tres grupos de 26 (terciles). La correlación de rangos (Spearman) compara ambos órdenes: 1 cuando coinciden, 0 cuando no se relacionan, menos de 0 cuando van en sentido contrario. Las medianas dividen los 78 en dos mitades de 39.")}</div>
    <div class="note"><b>{t("What the page does not do.", "Lo que la página no hace.")}</b> {t("It does not say how much money a municipio should have received, rank municipios as better or worse, or explain why the money went where it did.", "No dice cuánto dinero debió recibir un municipio, no clasifica los municipios como mejores o peores ni explica por qué el dinero fue a donde fue.")}</div>
  </section>

  <section class="block" id="sources">
    <h2><span class="ms-icon" aria-hidden="true">menu_book</span>{t("Sources and licenses", "Fuentes y licencias")}</h2>
    <div class="note"><b>{t("OpenFEMA.", "OpenFEMA.")}</b> {t("Public Assistance Funded Projects Details, Hazard Mitigation Assistance Subapplications and Housing Assistance Data (owners and renters), as published on the map (Explore) and the Housing page. US Government work; OpenFEMA terms apply.", "Public Assistance Funded Projects Details, Hazard Mitigation Assistance Subapplications y Housing Assistance Data (dueños e inquilinos), tal como se publican en el mapa (Explorar) y en la página de Vivienda. Obra del Gobierno de EE. UU.; aplican los términos de OpenFEMA.")}</div>
    <div class="note"><b>{t("USAspending.gov.", "USAspending.gov.")}</b> {t("HUD's CDBG grants to Puerto Rico (assistance listings 14.218 and 14.228) and the subawards reported under the federal transparency law (FFATA), read from USAspending's API by cdbg_dr.py and cdbg_regular.py, as published on the Public spending page. US Government work; USAspending states no license for the data.", "Las subvenciones CDBG de HUD a Puerto Rico (listados de asistencia 14.218 y 14.228) y las subadjudicaciones informadas bajo la ley federal de transparencia (FFATA), leídas de la API de USAspending con cdbg_dr.py y cdbg_regular.py, tal como se publican en la página de Gasto público. Obra del Gobierno de EE. UU.; USAspending no declara una licencia para los datos.")}</div>
    <div class="note"><b>{t("FEMA National Risk Index.", "Índice Nacional de Riesgo de FEMA.")}</b> {t("County table, expected annual loss, as published on the map's Environment tab. US Government work.", "Tabla por condado, pérdida anual esperada, tal como se publica en la pestaña Ambiente del mapa. Obra del Gobierno de EE. UU.")}</div>
    <div class="note"><b>{t("Census Bureau Community Resilience Estimates.", "Estimaciones de Resiliencia Comunitaria del Negociado del Censo.")}</b> {t("Municipio table, as published on the map's Environment tab. US Government work.", "Tabla por municipio, tal como se publica en la pestaña Ambiente del mapa. Obra del Gobierno de EE. UU.")}</div>
    <div class="note"><b>{t("Data and method.", "Datos y método.")}</b> {t("The data file is data/public_money_need.json (public_money_need.py), built only from the observatory's published data files; the method is in docs/analysis/public-money-v2-2026-10/ of the project repository.", "El archivo de datos es data/public_money_need.json (public_money_need.py), construido solo con los archivos de datos publicados del observatorio; el método está en docs/analysis/public-money-v2-2026-10/ del repositorio del proyecto.")}</div>
    <div class="note"><b>{t("How to cite this page.", "Cómo citar esta página.")}</b> {t("Foundation for Puerto Rico, Knowledge Area: Disaster funding and need, PR Data Observatory, Snapshot 2026-11 (draft). Data: FEMA (OpenFEMA, National Risk Index), USAspending.gov and U.S. Census Bureau (Community Resilience Estimates, 2020 Census).", "Foundation for Puerto Rico, Área de conocimiento: Fondos por desastres y necesidad, Observatorio de Datos de PR, Snapshot 2026-11 (borrador). Datos: FEMA (OpenFEMA, Índice Nacional de Riesgo), USAspending.gov y Negociado del Censo de EE. UU. (Estimaciones de Resiliencia Comunitaria, Censo 2020).")}</div>
  </section>
</main>
<script src="js/core/knowledge.js?v=35"></script>
<script>Core.knowledge.render(); I18N.apply();</script>
<script src="js/common.js?v=20"></script>
<script src="js/public_money.js?v=3"></script>
<script src="js/chatboot.js?v=45"></script>
</body>
</html>
"""
    # A note that starts with a bold lead is translated whole (I18N.apply reads its innerHTML as one key): pair the two halves' Spanish
    for m in re.finditer(r"<b>([^<]*)</b> ([^<]*)</(?:div|p)>", page):
        lead, body = " ".join(html.unescape(m.group(1)).split()), " ".join(html.unescape(m.group(2)).split())
        key = " ".join(f"<b>{m.group(1)}</b> {m.group(2)}".split())
        es_lead, es_body = HELD.get(lead, ES[lead]), HELD.get(body, ES[body])
        es = f"<b>{html.escape(es_lead, quote=False)}</b> {html.escape(es_body, quote=False)}"
        if lead in HELD or body in HELD:
            HELD[key] = es
            es = key
        ES[key] = es
        for k in (lead, body):
            ES.pop(k, None)
            HELD.pop(k, None)
    (ROOT / "site" / "public-money.html").write_text(page, encoding="utf-8", newline="\n")
    es = {"_about": "The Disaster funding and need page of the Knowledge Area (public-money.html) and site/js/public_money.js. Written by docs/analysis/public-money-v2-2026-10/make_page.py from its (English, Spanish) pairs: edit them there, not here."}
    es.update(ES)
    (ROOT / "i18n_src" / "es" / "public_money.json").write_text(json.dumps(es, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    root_i18n = ROOT / "i18n_src"
    held_p = root_i18n / "held_for_review.json"
    held = json.loads(held_p.read_text(encoding="utf-8"))
    held["spanish"]["public_money"] = dict(sorted(HELD.items()))   # each held key is listed under the scope file that holds it
    if not HELD:
        held["spanish"].pop("public_money")
    held_p.write_text(json.dumps(held, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    keep_p = root_i18n / "keep.json"
    keep = json.loads(keep_p.read_text(encoding="utf-8"))
    keep += [k for k in sorted(HELD) if k not in keep]
    keep_p.write_text(json.dumps(keep, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")   # the file is one line
    print(f"wrote site/public-money.html and i18n_src/es/public_money.json ({len(ES)} strings), {len(HELD)} held for review")


if __name__ == "__main__":
    build()
