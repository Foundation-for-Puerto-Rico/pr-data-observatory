"""Writes the Knowledge Area page "Women in the labor force" (site/women-labor.html) and its Spanish (i18n_src/es/women_labor.json).

  python docs/analysis/women-labor-2026-10/make_page.py      read site/data/women_labor.json (python women_labor.py makes it); write the page
                                                             and the Spanish of the page and of site/js/women_labor.js. Then run python i18n.py.

The page follows the site's language rule (docs/i18n.md): the HTML is in English and every English string is its own key; I18N.apply() puts the
Spanish on the static text and women_labor.js asks T() for the rest. Every string is written once, as an (English, Spanish) pair, so the two files
cannot drift apart, and every figure in the text is read from the data file, so no number is typed by hand (the route analysis page does the same).
Prepared with Claude (AI) for FPR, 2026-10-30, for the Human Capital chapter of the Eastern Region Strategic Vision.
"""
import html
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))
import women_labor as W  # noqa: E402

ES = {}


def t(en, es):
    """An English string and its Spanish; returns the English (escaped), for the page."""
    key = " ".join(en.split())
    if key in ES and ES[key] != es:
        raise SystemExit(f"two Spanish texts for {key!r}")
    ES[key] = " ".join(es.split())
    return html.escape(key, quote=False)


def n0(x):
    return f"{x:,.0f}"


def p1(x):
    return f"{x:.1f}"


def pm(e):
    return f"{e[0]:.1f}% ± {e[1]:.1f}"


# Strings women_labor.js asks T() for (the same English keys as in the script)
JS = [
    ("Eastern Region (ERSV)", "Región Este (ERSV)"), ("Rest of Puerto Rico", "Resto de Puerto Rico"), ("Puerto Rico", "Puerto Rico"),
    ("Women", "Mujeres"), ("Men", "Hombres"),
    ("Labor force participation (%)", "Participación en la fuerza laboral (%)"),
    ("{name}: {v}% (90% margin of error ± {m})", "{name}: {v} % (margen de error al 90 % ± {m})"),
    ("{name}, {sex}: {v}% ± {m}", "{name}, {sex}: {v} % ± {m}"),
    ("Women and men 16 and over: labor force participation, with 90% margins of error", "Mujeres y hombres de 16 años o más: participación en la fuerza laboral, con márgenes de error al 90 %"),
    ("in the labor force, working", "en la fuerza laboral, con empleo"),
    ("in the labor force, looking for work", "en la fuerza laboral, buscando empleo"),
    ("not in the labor force", "fuera de la fuerza laboral"),
    ("Of every 100 women 16 and over in the selected area", "De cada 100 mujeres de 16 años o más en el área seleccionada"),
    ("{n} of every 100 women {what}", "{n} de cada 100 mujeres {what}"),
    ("Age group", "Grupo de edad"),
    ("Labor force participation of women by age group, selected area and rest of Puerto Rico", "Participación laboral de las mujeres por grupo de edad, área seleccionada y resto de Puerto Rico"),
    ("{age}: {name} {v}% ± {m}", "{age}: {name} {v} % ± {m}"),
    ("difference significant at 90%", "diferencia significativa al 90 %"),
    ("no significant difference", "sin diferencia significativa"),
    ("Women's rate, rest of Puerto Rico", "Tasa de las mujeres, resto de Puerto Rico"),
    ("Women's rate, Puerto Rico", "Tasa de las mujeres, Puerto Rico"), ("age mix", "composición por edad"), ("participation within each age", "participación dentro de cada edad"),
    ("How the gap with the rest of Puerto Rico splits: age mix and participation within each age", "Cómo se divide la diferencia con el resto de Puerto Rico: composición por edad y participación dentro de cada edad"),
    ("{part}: {v} points", "{part}: {v} puntos"),
    ("With children under 6", "Con hijos menores de 6 años"), ("With children 6 to 17 only", "Solo con hijos de 6 a 17 años"), ("No own children under 18", "Sin hijos propios menores de 18 años"),
    ("Women 20 to 64: labor force participation by own children, selected area and rest of Puerto Rico", "Mujeres de 20 a 64 años: participación laboral según sus hijos propios, área seleccionada y resto de Puerto Rico"),
    ("Women 16 and over", "Mujeres de 16 años o más"), ("Women 25 to 54", "Mujeres de 25 a 54 años"), ("Men 16 and over", "Hombres de 16 años o más"),
    ("Labor force participation in three five-year windows that share no year", "Participación laboral en tres períodos de cinco años que no comparten ningún año"),
    ("{name}, {window}: {v}% ± {m}", "{name}, {window}: {v} % ± {m}"),
    ("Women's labor force participation, women 16 and over", "Participación laboral de las mujeres de 16 años o más"),
    ("Women's labor force participation, women 25 to 54", "Participación laboral de las mujeres de 25 a 54 años"),
    ("Gap, men minus women (points)", "Brecha, hombres menos mujeres (puntos)"),
    ("Unemployment rate, women", "Tasa de desempleo de las mujeres"),
    ("Coefficient of variation of the women's rate (%)", "Coeficiente de variación de la tasa de las mujeres (%)"),
    ("Shade the municipios by", "Sombrear los municipios por"), ("Five-year window", "Período de cinco años"),
    ("Municipio", "Municipio"), ("Rate", "Tasa"), ("± margin", "± margen"), 
    ("{name}: {v} (± {m}). Select to add it to the area or take it out.", "{name}: {v} (± {m}). Seleccione para añadirlo al área o quitarlo."),
    ("{name}: no value", "{name}: sin valor"),
    ("{n} municipios selected", "{n} municipios seleccionados"), ("1 municipio selected", "1 municipio seleccionado"),
    ("Select at least one municipio on the map.", "Seleccione al menos un municipio en el mapa."),
    ("All of Puerto Rico is selected: there is no rest of the island to compare with.", "Todo Puerto Rico está seleccionado: no queda resto de la isla con el cual comparar."),
    ("Women's labor force participation", "Participación laboral de las mujeres"),
    ("Rest of Puerto Rico: {v}%", "Resto de Puerto Rico: {v} %"),
    ("Difference: {d} points ± {m}", "Diferencia: {d} puntos ± {m}"),
    ("Statistically significant at 90%", "Estadísticamente significativa al 90 %"),
    ("Not statistically significant at 90%: the two may be equal", "No es estadísticamente significativa al 90 %: ambas podrían ser iguales"),
    ("Women 16 and over in the area", "Mujeres de 16 años o más en el área"),
    ("Women in the labor force", "Mujeres en la fuerza laboral"),
    ("Women 25 to 54 (prime working age)", "Mujeres de 25 a 54 años (edad laboral principal)"),
    ("Men 16 and over", "Hombres de 16 años o más"),
    ("Gap, men minus women", "Brecha, hombres menos mujeres"),
    ("Unemployment rate, women", "Tasa de desempleo de las mujeres"),
    ("People interviewed by the survey in five years (all ages, both sexes)", "Personas entrevistadas por la encuesta en cinco años (todas las edades, ambos sexos)"),
    ("Simple average of the municipio rates (not the area's rate)", "Promedio simple de las tasas municipales (no es la tasa del área)"),
    ("{v} points", "{v} puntos"),
    ("Less reliable (coefficient of variation over 30%)", "Menos confiable (coeficiente de variación mayor de 30 %)"),
    ("The data could not be loaded ({error}). Check your connection and reload.", "No se pudieron cargar los datos ({error}). Verifique su conexión y vuelva a cargar la página."),
    ("Download CSV", "Descargar CSV"),
    ("Open on the map", "Abrir en el mapa"),
    ("Eastern Region (ERSV, 15)", "Región Este (ERSV, 15)"), ("Clear selection", "Limpiar selección"),
    ("Area", "Área"), ("Window", "Período"), ("Measure", "Medida"), ("Estimate", "Estimado"), ("Margin of error (90%)", "Margen de error (90 %)"),
    ("it is statistically significant at 90%", "es estadísticamente significativa al 90 %"), ("it is not statistically significant at 90%", "no es estadísticamente significativa al 90 %"),
    ("Age-adjusted rate: {adj}% (actual rate {crude}%). Age mix: {mix} points; participation within each age: {rate} points.", "Tasa ajustada por edad: {adj} % (tasa real {crude} %). Composición por edad: {mix} puntos; participación dentro de cada edad: {rate} puntos."),
    ("Select at least one municipio on the map.", "Seleccione al menos un municipio en el mapa."),
    ("the change is statistically significant at 90%", "el cambio es estadísticamente significativo al 90 %"), ("the change is not statistically significant at 90%", "el cambio no es estadísticamente significativo al 90 %"),
    ("Reading it ({area}): the difference with the rest of Puerto Rico is {d} points (± {m}); {sig}.", "Cómo leerlo ({area}): la diferencia con el resto de Puerto Rico es {d} puntos (± {m}); {sig}."),
    ("Reading it ({area}):", "Cómo leerlo ({area}):"),
    ("Gap, men minus women: {g} points (± {gm}); {gsig}.", "Brecha, hombres menos mujeres: {g} puntos (± {gm}); {gsig}."),
    ("Reading it ({area}): every age group differs significantly from the rest of Puerto Rico.", "Cómo leerlo ({area}): todos los grupos de edad difieren de forma significativa del resto de Puerto Rico."),
    ("Reading it ({area}): the age groups that differ significantly from the rest of Puerto Rico are {ages}.", "Cómo leerlo ({area}): los grupos de edad que difieren de forma significativa del resto de Puerto Rico son {ages}."),
    ("Reading it ({area}): no age group differs significantly from the rest of Puerto Rico.", "Cómo leerlo ({area}): ningún grupo de edad difiere de forma significativa del resto de Puerto Rico."),
    ("Reading it ({area}): from {w0} to {w1}, the participation of women 16 and over changed {d} points (± {m}); {sig}. For women 25 to 54 it changed {d2} points (± {m2}); {sig2}.", "Cómo leerlo ({area}): de {w0} a {w1}, la participación de las mujeres de 16 años o más cambió {d} puntos (± {m}); {sig}. La de las mujeres de 25 a 54 años cambió {d2} puntos (± {m2}); {sig2}."),
    ("percentage points", "puntos porcentuales"),
]
for en, es in JS:
    t(en, es)


def build():
    D = json.loads((ROOT / "site" / "data" / "women_labor.json").read_text(encoding="utf-8"))
    A = D["analysis"]["ersv"]
    L, F = A[str(W.LATEST)], A[str(W.WINDOWS[0])]
    r, i, o = L["region"], L["island"], L["rest"]
    a24 = D["areas"][str(W.LATEST)]
    ids = D["groups"]["ersv"]["ids"]
    reg = W.combine([a24[g] for g in ids])
    rest = W.combine([a24[g] for g in a24 if len(g) == 5 and g not in ids])
    age_r = [W.prop(reg["f"][k][1], reg["f"][k][0]) for k in range(len(W.AGES))]
    age_o = [W.prop(rest["f"][k][1], rest["f"][k][0]) for k in range(len(W.AGES))]
    age_d = [W.diff(x, y) for x, y in zip(age_r, age_o)]
    kid_r = {k: W.prop(reg["kids"][k][1], reg["kids"][k][0]) for k, _ in W.KIDS}
    kid_o = {k: W.prop(rest["kids"][k][1], rest["kids"][k][0]) for k, _ in W.KIDS}
    kid_any = any(W.diff(kid_r[k], kid_o[k])["sig"] for k, _ in W.KIDS)
    kid_sig = "some differences between the region and the rest of the island are significant." if kid_any else "no difference between the region and the rest of the island is significant."
    kid_sig_es = "algunas diferencias entre la región y el resto de la isla son significativas." if kid_any else "ninguna diferencia entre la región y el resto de la isla es significativa."
    sig_ages = [W.AGES[k][0] for k in range(len(W.AGES)) if age_d[k] and age_d[k]["sig"]]
    small_m = max(W.measures(a24[g])["lfpr_f"][1] for g in ("72049", "72147"))
    muni = sorted(((D["names"][g], W.measures(a24[g])["lfpr_f"]) for g in ids), key=lambda x: -x[1][0])
    hi, lo = muni[:3], muni[-3:]
    vs = L["vs_rest"]["lfpr_f"]
    gap = L["gender_gap"]
    ch = A["change"]
    adj = L["age_adjusted"]
    women_lf = r["women_lf"][0]
    share65 = r["share_f_65"][0]
    people = r["sample"]["people"]
    cw = json.loads((ROOT / "site" / "data" / "geo" / "crosswalk.json").read_text(encoding="utf-8"))
    pop2020 = sum(u[6] for u in cw["units"]["municipio"] if u[0] in ids)   # 2020 Census residents of the region, all ages
    share_int = 100 * people / pop2020

    def women16(g):
        return sum(a24[g]["f"][k][0][0] for k in range(len(W.AGES)))
    sig_word = (lambda d: ("is", "es") if d["sig"] else ("is not", "no es"))

    kpis = [
        (pm(r["lfpr_f"]), t(f"of women 16 and over in the Eastern Region are in the labor force (2020-2024)", f"de las mujeres de 16 años o más en la Región Este están en la fuerza laboral (2020-2024)")),
        (pm(o["lfpr_f"]), t("in the rest of Puerto Rico: the difference is not statistically significant" if not vs["sig"] else "in the rest of Puerto Rico: the difference is statistically significant",
                             "en el resto de Puerto Rico: la diferencia no es estadísticamente significativa" if not vs["sig"] else "en el resto de Puerto Rico: la diferencia es estadísticamente significativa")),
        (f"{gap['v']:.1f} ± {gap['m']:.1f}", t(f"percentage points more men than women take part ({r['lfpr_m'][0]:.1f}% of men)", f"puntos porcentuales más participan los hombres que las mujeres ({r['lfpr_m'][0]:.1f} % de los hombres)")),
        (pm(r["lfpr_f_prime"]), t(f"of women 25 to 54, the prime working ages, up {ch['lfpr_f_prime']['v']:.1f} points since 2010-2014", f"de las mujeres de 25 a 54 años, las edades laborales principales; {ch['lfpr_f_prime']['v']:.1f} puntos más que en 2010-2014")),
        (n0(r["women16"][0]), t(f"women 16 and over live in the region (± {n0(r['women16'][1])}); {n0(women_lf)} of them are in the labor force", f"mujeres de 16 años o más viven en la región (± {n0(r['women16'][1])}); {n0(women_lf)} de ellas están en la fuerza laboral")),
        (n0(people), t("people of all ages in the region answered the survey in 2020-2024: the sample behind that window's estimates", "personas de todas las edades en la región contestaron la encuesta en 2020-2024: la muestra detrás de los estimados de ese período")),
    ]
    kpi_html = "".join(f'<div class="kpi"><b data-t="skip">{html.escape(v)}</b><span>{s}</span></div>' for v, s in kpis)

    page = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{t("Knowledge Area · Women in the labor force", "Área de conocimiento · Las mujeres en la fuerza laboral")}</title>
<meta name="description" content="{t("Women's labor force participation in the 15 municipios of the Eastern Region and in Puerto Rico, with margins of error, age, children and change over time, from the Census Bureau's American Community Survey. Any group of municipios can be compared with the rest of the island.", "La participación de las mujeres en la fuerza laboral en los 15 municipios de la Región Este y en Puerto Rico, con márgenes de error, edad, hijos y cambio en el tiempo, según la Encuesta sobre la Comunidad Estadounidense del Negociado del Censo. Cualquier grupo de municipios se puede comparar con el resto de la isla.")}">
<meta name="theme-color" content="#FFFFFF">
<link rel="icon" href="img/fpr-mark.png">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Material+Symbols+Rounded:opsz,wght,FILL,GRAD@24,400,1,0&icon_names=account_balance,account_tree,bolt,chat_bubble,close,commute,compare_arrows,dark_mode,delete,diversity_3,download,elderly_woman,explore,family_restroom,grid_view,groups,home_work,hourglass_bottom,info,light_mode,lightbulb,location_city,map,menu_book,payments,price_change,rocket_launch,route,school,send,thermostat,timeline,view_in_ar,warning,water,wifi,woman,work&display=block">
<link rel="stylesheet" href="css/twin.css?v=63">
<link rel="stylesheet" href="css/housing.css?v=22">
<link rel="stylesheet" href="css/women_labor.css?v=5">
<link rel="stylesheet" href="css/chat.css?v=5">
<link rel="stylesheet" href="css/ws.css?v=1">
<script src="js/i18n.js?v=61" data-page="women"></script>
</head>
<body class="research">
<a class="skip" href="#region">{t("Skip to the content", "Ir al contenido")}</a>
<header class="topbar">
  <a class="logo" href="index.html" title="{t("PR Data Observatory home", "Inicio del Observatorio de Datos de PR")}"><img src="img/fpr-logo.png" alt="{t("Foundation for Puerto Rico. PR Data Observatory home", "Foundation for Puerto Rico. Inicio del Observatorio de Datos de PR")}"></a>
  <div class="brand"><b>{t("Knowledge Area · Women in the labor force", "Área de conocimiento · Las mujeres en la fuerza laboral")}</b><span>{t("Eastern Region and Puerto Rico, Census Bureau survey", "Región Este y Puerto Rico, encuesta del Negociado del Censo")}</span></div>
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
  <span class="ka-tabs" role="group" aria-label="{t("Knowledge Area", "Área de conocimiento")}" data-ka="women"></span><span class="ka-sep" aria-hidden="true"></span>
  <a href="#region">{t("Choose the region", "Escoja la región")}</a><a href="#compare">{t("Region and island", "Región e isla")}</a><a href="#people">{t("Who is counted", "Quiénes cuentan")}</a><a href="#age">{t("Age", "Edad")}</a><a href="#children">{t("Children", "Hijos")}</a><a href="#trend">{t("Over time", "En el tiempo")}</a><a href="#municipios">{t("The municipios", "Los municipios")}</a><a href="#ersv">{t("Eastern Region findings", "Hallazgos de la Región Este")}</a><a href="#method">{t("Method", "Método")}</a><a href="#sources">{t("Sources", "Fuentes")}</a>
</nav>

<main class="page">
  <div class="note caution review-note" role="note" data-ka-note></div>

  <section class="hero" id="region">
    <div class="eyebrow">{t("Knowledge Area · Analysis", "Área de conocimiento · Análisis")}</div>
    <h1>{t("Women in the labor force by region", "Las mujeres en la fuerza laboral por región")}</h1>
    <p class="lede">{t("Select the region you want to analyze: The page opens with the 15 municipios of the Eastern Region (ERSV).", "Seleccione la región que desea analizar: la página abre con los 15 municipios de la Región Este (ERSV).")}</p>
    <div class="wl-controls">
      <div class="wl-presets" role="group" aria-label="{t("Regions", "Regiones")}" id="wlPresets"></div>
      <label>{t("Shade the municipios by", "Sombrear los municipios por")} <select id="wlShade"></select></label>
      <label>{t("Five-year window", "Período de cinco años")} <select id="wlWindow"></select></label>
    </div>
    <div class="wl-maprow">
      <div class="card wl-map"><div id="wlMap"></div><div class="wl-legend" id="wlLegend"></div></div>
      <div class="card wl-region" id="wlRegion" aria-live="polite"></div>
    </div>
    <p class="wl-small">{t("Each figure is an estimate from the Census Bureau's American Community Survey (ACS), with its margin of error at the 90% confidence level (±). The five-year window chosen above applies to every chart except section 5, which shows the three windows. Foundation for Puerto Rico prepared this analysis for the PR Data Observatory.", "Cada cifra es un estimado de la Encuesta sobre la Comunidad Estadounidense (ACS) del Negociado del Censo, con su margen de error al nivel de confianza de 90 % (±). El período de cinco años escogido arriba aplica a todas las gráficas menos la sección 5, que muestra los tres períodos. Foundation for Puerto Rico preparó este análisis para el Observatorio de Datos de PR.")}</p>
  </section>

  <section class="block" id="compare">
    <h2><span class="ms-icon" aria-hidden="true">compare_arrows</span>{t("1 · The region, the rest of the island and Puerto Rico", "1 · La región, el resto de la isla y Puerto Rico")}</h2>
    <p class="wl-p">{t("Each dot is an estimate and each line its 90% margin of error. When the lines of two areas overlap a lot, the survey cannot tell their rates apart. The region is compared with the rest of Puerto Rico, not with the island total, because the island total includes the region itself.", "Cada punto es un estimado y cada línea su margen de error al 90 %. Cuando las líneas de dos áreas se solapan mucho, la encuesta no puede distinguir sus tasas. La región se compara con el resto de Puerto Rico, no con el total de la isla, porque el total de la isla incluye a la propia región.")}</p>
    <div class="card wl-chart"><div id="wlCompare"></div></div>
    <div class="note" id="wlReadCompare" data-t="skip"></div>
  </section>

  <section class="block" id="people">
    <h2><span class="ms-icon" aria-hidden="true">groups</span>{t("2 · Who is behind the number", "2 · Quiénes están detrás de la cifra")}</h2>
    <p class="wl-p">{t("The rate divides women in the labor force by all women 16 and over. Women not in the labor force include students, retirees, women caring for family and women who would like to work but are not looking. Women looking for work count as in the labor force.", "La tasa divide las mujeres en la fuerza laboral entre todas las mujeres de 16 años o más. Fuera de la fuerza laboral están las estudiantes, las retiradas, las que cuidan de su familia y las que quisieran trabajar pero no están buscando empleo. Las que buscan empleo cuentan como parte de la fuerza laboral.")}</p>
    <div class="wl-two">
      <div class="card wl-chart"><div id="wlWaffle"></div></div>
      <div class="card wl-sample">
        <h3>{t("Sample size", "Tamaño de la muestra")}</h3>
        <dl id="wlSample"></dl>
        <p class="wl-small">{t("The survey does not publish how many of the people interviewed were women 16 and over. The Census Bureau weights each answer to represent the whole population, and the margins of error already reflect the size of the sample. The number interviewed is published for 2020-2024 only.", "La encuesta no publica cuántas de las personas entrevistadas eran mujeres de 16 años o más. El Negociado del Censo pondera cada respuesta para que represente a toda la población, y los márgenes de error ya reflejan el tamaño de la muestra. El número de entrevistas se publica solo para 2020-2024.")}</p>
      </div>
    </div>
  </section>

  <section class="block" id="age">
    <h2><span class="ms-icon" aria-hidden="true">elderly_woman</span>{t("3 · Age changes the picture", "3 · La edad cambia el panorama")}</h2>
    <p class="wl-p">{t("Participation rises from the late teens, peaks between 25 and 44 and falls after 55, and almost no woman 65 or older works. So an area's overall rate depends on how old its women are. The chart compares each age group; a diamond under an age group marks a difference that is statistically significant at 90%.", "La participación sube desde el final de la adolescencia, llega a su punto más alto entre los 25 y los 44 años y baja después de los 55, y casi ninguna mujer de 65 años o más trabaja. Por eso la tasa general de un área depende de cuán envejecidas estén sus mujeres. La gráfica compara cada grupo de edad; un rombo bajo un grupo de edad marca una diferencia estadísticamente significativa al 90 %.")}</p>
    <div class="card wl-chart"><div id="wlAge"></div></div>
    <p class="wl-p">{t("The age-adjusted rate answers: what would the area's rate be if its women had the age mix of the women in the rest of the island? The bar chart splits the difference between the two areas into a part due to the age mix and a part due to participation within each age.", "La tasa ajustada por edad responde: ¿cuál sería la tasa del área si sus mujeres tuvieran la composición por edad de las mujeres del resto de la isla? La gráfica de barras divide la diferencia entre las dos áreas en una parte debida a la composición por edad y otra debida a la participación dentro de cada edad.")}</p>
    <div class="card wl-chart"><div id="wlBridge"></div></div>
    <div class="note" id="wlReadAge" data-t="skip"></div>
  </section>

  <section class="block" id="children">
    <h2><span class="ms-icon" aria-hidden="true">family_restroom</span>{t("4 · Mothers and young children", "4 · Madres e hijos pequeños")}</h2>
    <p class="wl-p">{t("For women 20 to 64 living in households, the survey also gives participation by the age of their own children. The survey does not give the ages of the women in each group, so part of a difference between groups may come from age. Since 2015-2019 the Census Bureau counts only the children of the householder, so this chart is not comparable with 2010-2014.", "Para las mujeres de 20 a 64 años que viven en hogares, la encuesta también da la participación según la edad de sus hijos propios. La encuesta no da la edad de las mujeres de cada grupo, por lo que parte de una diferencia entre grupos puede deberse a la edad. Desde 2015-2019 el Negociado del Censo cuenta solo los hijos de la persona de referencia del hogar, por lo que esta gráfica no es comparable con 2010-2014.")}</p>
    <div class="card wl-chart"><div id="wlKids"></div></div>
  </section>

  <section class="block" id="trend">
    <h2><span class="ms-icon" aria-hidden="true">timeline</span>{t("5 · Over time", "5 · En el tiempo")}</h2>
    <p class="wl-p">{t("The ACS gives five-year estimates; only windows that share no year can be compared, so this chart uses 2010-2014, 2015-2019 and 2020-2024. Counts from different windows are controlled to different population estimates, so compare rates rather than numbers of people.", "La ACS da estimados de cinco años; solo se pueden comparar períodos que no comparten ningún año, por lo que esta gráfica usa 2010-2014, 2015-2019 y 2020-2024. Los conteos de períodos distintos se ajustan a estimados de población distintos, por lo que conviene comparar tasas y no números de personas.")}</p>
    <div class="card wl-chart"><div id="wlTrend"></div></div>
    <div class="note" id="wlReadTrend" data-t="skip"></div>
  </section>

  <section class="block" id="municipios">
    <h2><span class="ms-icon" aria-hidden="true">location_city</span>{t("6 · The municipios of the region", "6 · Los municipios de la región")}</h2>
    <p class="wl-p">{t("A regional rate can hide a wide spread between its municipios. Each row is a municipio of the selected region, with its 90% margin of error; small municipios have wide margins. The solid line is the region's pooled rate and the dashed line the rest of Puerto Rico.", "Una tasa regional puede esconder una gran dispersión entre sus municipios. Cada fila es un municipio de la región seleccionada, con su margen de error al 90 %; los municipios pequeños tienen márgenes amplios. La línea sólida es la tasa agrupada de la región y la línea entrecortada la del resto de Puerto Rico.")}</p>
    <div class="card wl-chart"><div id="wlDots"></div></div>
    <p class="wl-links"><a class="btn" id="wlCsv" href="#"><span class="ms-icon" aria-hidden="true">download</span>{t("Download CSV", "Descargar CSV")}</a> <a class="btn" href="index.html#e=lfpr_women.f"><span class="ms-icon" aria-hidden="true">map</span>{t("Open on the map", "Abrir en el mapa")}</a></p>
  </section>

  <section class="block" id="ersv">
    <h2><span class="ms-icon" aria-hidden="true">lightbulb</span>{t("7 · Findings for the Eastern Region (ERSV), 2020-2024", "7 · Hallazgos para la Región Este (ERSV), 2020-2024")}</h2>
    <p class="wl-p">{t(f"In 2020-2024, {r['lfpr_f'][0]:.1f}% of women 16 and over in the 15 municipios of the Eastern Region were in the labor force, that is, working or looking for work. In the rest of Puerto Rico the rate was {o['lfpr_f'][0]:.1f}%. With the survey's margins of error, the two rates are statistically the same. The single number hides three things that matter for the Human Capital chapter: women still take part {gap['v']:.1f} points less than men; women 25 to 54 take part much more than the overall rate suggests, and more than a decade ago; and women 55 and over in the region leave the labor force earlier than in the rest of the island.",
                                f"En 2020-2024, el {r['lfpr_f'][0]:.1f} % de las mujeres de 16 años o más en los 15 municipios de la Región Este estaban en la fuerza laboral, es decir, trabajando o buscando empleo. En el resto de Puerto Rico la tasa fue {o['lfpr_f'][0]:.1f} %. Con los márgenes de error de la encuesta, ambas tasas son estadísticamente iguales. La cifra única esconde tres asuntos importantes para el capítulo de Capital Humano: las mujeres todavía participan {gap['v']:.1f} puntos menos que los hombres; las mujeres de 25 a 54 años participan mucho más de lo que sugiere la tasa general, y más que hace una década; y las mujeres de 55 años o más en la región salen de la fuerza laboral antes que en el resto de la isla.")}</p>
    <div class="kpi-row">{kpi_html}</div>
    <p class="wl-small"><b>{t("The region:", "La región:")}</b> {t("Canóvanas, Ceiba, Culebra, Fajardo, Humacao, Juncos, Las Piedras, Loíza, Luquillo, Maunabo, Naguabo, Río Grande, San Lorenzo, Vieques and Yabucoa, as defined by FPR's Eastern Region Strategic Vision (ERSV). To see its charts, choose the button Eastern Region (ERSV, 15) at the top of the page.", "Canóvanas, Ceiba, Culebra, Fajardo, Humacao, Juncos, Las Piedras, Loíza, Luquillo, Maunabo, Naguabo, Río Grande, San Lorenzo, Vieques y Yabucoa, según la Visión Estratégica de la Región Este (ERSV) de FPR. Para ver sus gráficas, escoja el botón Región Este (ERSV, 15) al principio de la página.")}</p>
    <div class="note caution"><b>{t("A regional rate is not an average of municipio rates.", "Una tasa regional no es un promedio de tasas municipales.")}</b> {t(f"The region's rate adds up its women in the labor force and divides by all its women 16 and over ({r['lfpr_f'][0]:.1f}%). The simple average of the 15 municipio rates gives {L['unweighted_mean_lfpr_f']:.1f}%, because it gives Culebra (about {n0(women16('72049'))} women 16 and over) the same weight as Humacao (about {n0(women16('72069'))}). Use the pooled rate in the chapter.", f"La tasa de la región suma sus mujeres en la fuerza laboral y divide entre todas sus mujeres de 16 años o más ({r['lfpr_f'][0]:.1f} %). El promedio simple de las 15 tasas municipales da {L['unweighted_mean_lfpr_f']:.1f} %, porque le da a Culebra (unas {n0(women16('72049'))} mujeres de 16 años o más) el mismo peso que a Humacao (unas {n0(women16('72069'))}). Use la tasa agrupada en el capítulo.")}</div>
    <ul class="wl-findings">
      <li>{t(f"Age: the region differs significantly from the rest of the island only at {', '.join(sig_ages)}. {age_r[5][0]:.1f}% of women 55 to 64 in the region are in the labor force, against {age_o[5][0]:.1f}% in the rest of Puerto Rico ({age_d[5]['v']:+.1f} points, ± {age_d[5]['m']:.1f}). {share65:.1f}% of the region's women 16 and over are 65 or older.", f"Edad: la región difiere de forma significativa del resto de la isla solo en {', '.join(sig_ages)}. El {age_r[5][0]:.1f} % de las mujeres de 55 a 64 años de la región están en la fuerza laboral, frente al {age_o[5][0]:.1f} % en el resto de Puerto Rico ({age_d[5]['v']:+.1f} puntos, ± {age_d[5]['m']:.1f}). El {share65:.1f} % de las mujeres de 16 años o más de la región tienen 65 años o más.")}</li>
      <li>{t(f"Age-adjusted rate: {adj['adjusted']:.1f}%, against an actual {adj['crude']:.1f}%. The region's women are slightly younger than those in the rest of the island, which raises its rate by {adj['from_age_mix']:.1f} points; lower participation after 55 lowers it by {abs(adj['from_rates']):.1f}. Together they change the rate by {adj['from_age_mix'] + adj['from_rates']:+.1f} points, which is why the overall rates look the same.", f"Tasa ajustada por edad: {adj['adjusted']:.1f} %, frente a una tasa real de {adj['crude']:.1f} %. Las mujeres de la región son un poco más jóvenes que las del resto de la isla, lo que sube su tasa {adj['from_age_mix']:.1f} puntos; una participación menor después de los 55 años la baja {abs(adj['from_rates']):.1f}. Juntos cambian la tasa {adj['from_age_mix'] + adj['from_rates']:+.1f} puntos, y por eso las tasas generales se ven iguales.")}</li>
      <li>{t(f"Over time: from 2010-2014 to 2020-2024 the participation of women 16 and over rose {ch['lfpr_f']['v']:.1f} points (± {ch['lfpr_f']['m']:.1f}) and that of women 25 to 54 rose {ch['lfpr_f_prime']['v']:.1f} points (± {ch['lfpr_f_prime']['m']:.1f}).", f"En el tiempo: de 2010-2014 a 2020-2024 la participación de las mujeres de 16 años o más subió {ch['lfpr_f']['v']:.1f} puntos (± {ch['lfpr_f']['m']:.1f}) y la de las mujeres de 25 a 54 años subió {ch['lfpr_f_prime']['v']:.1f} puntos (± {ch['lfpr_f_prime']['m']:.1f}).")}</li>
      <li>{t(f"Count: the estimated number of women 16 and over fell by about {n0(abs(ch['women16']['v']))} from 2010-2014 to 2020-2024; counts from different windows are controlled to different population estimates, so part of that change comes from the controls.", f"Conteo: el número estimado de mujeres de 16 años o más bajó cerca de {n0(abs(ch['women16']['v']))} de 2010-2014 a 2020-2024; los conteos de períodos distintos se ajustan a estimados de población distintos, por lo que parte de ese cambio viene de esos ajustes.")}</li>
      <li>{t(f"Children: in the region and in the rest of the island, mothers of children under 6 ({kid_r['u6'][0]:.1f}% and {kid_o['u6'][0]:.1f}%) take part more than women 20 to 64 without own children under 18 ({kid_r['none'][0]:.1f}% and {kid_o['none'][0]:.1f}%); {kid_sig}", f"Hijos: en la región y en el resto de la isla, las madres de niños menores de 6 años ({kid_r['u6'][0]:.1f} % y {kid_o['u6'][0]:.1f} %) participan más que las mujeres de 20 a 64 años sin hijos propios menores de 18 años ({kid_r['none'][0]:.1f} % y {kid_o['none'][0]:.1f} %); {kid_sig_es}")}</li>
      <li>{t(f"Municipios: from {hi[0][1][0]:.1f}% in {hi[0][0]} and {hi[1][1][0]:.1f}% in {hi[1][0]} to {lo[-1][1][0]:.1f}% in {lo[-1][0]} and {lo[-2][1][0]:.1f}% in {lo[-2][0]}; margins reach ± {small_m:.1f} points in Culebra and Vieques.", f"Municipios: desde {hi[0][1][0]:.1f} % en {hi[0][0]} y {hi[1][1][0]:.1f} % en {hi[1][0]} hasta {lo[-1][1][0]:.1f} % en {lo[-1][0]} y {lo[-2][1][0]:.1f} % en {lo[-2][0]}; los márgenes llegan a ± {small_m:.1f} puntos en Culebra y Vieques.")}</li>
      <li>{t(f"Sample: in 2020-2024 the survey interviewed {n0(people)} people of all ages in the region, about {share_int:.1f}% of its residents (2020 Census).", f"Muestra: en 2020-2024 la encuesta entrevistó a {n0(people)} personas de todas las edades en la región, cerca del {share_int:.1f} % de sus residentes (Censo 2020).")}</li>
    </ul>
  </section>

  <section class="block" id="method">
    <h2><span class="ms-icon" aria-hidden="true">info</span>{t("Method", "Método")}</h2>
    <div class="note"><b>{t("Labor force participation rate.", "Tasa de participación en la fuerza laboral.")}</b> {t("People 16 and over in the labor force (employed, or unemployed and looking for work; civilian or in the Armed Forces) divided by all people 16 and over, as in the Census Bureau's table S2301. The unemployment rate divides the unemployed by the civilian labor force. Table B23001 (sex by age by employment status).", "Las personas de 16 años o más en la fuerza laboral (con empleo, o desempleadas y buscando empleo; civiles o en las Fuerzas Armadas) divididas entre todas las personas de 16 años o más, como en la tabla S2301 del Negociado del Censo. La tasa de desempleo divide las personas desempleadas entre la fuerza laboral civil. Tabla B23001 (sexo por edad por situación de empleo).")}</div>
    <div class="note"><b>{t("Pooled rates for a group of municipios.", "Tasas agrupadas para un grupo de municipios.")}</b> {t("The counts of the municipios are added, then divided. The margin of error of a sum is the square root of the sum of the squared margins, and that of a rate follows the Census Bureau's formula for a proportion (ACS General Handbook, chapter 8). These are approximations the Census Bureau recommends when the published tables do not cover the area.", "Se suman los conteos de los municipios y luego se divide. El margen de error de una suma es la raíz cuadrada de la suma de los márgenes al cuadrado, y el de una tasa sigue la fórmula del Negociado del Censo para una proporción (Manual general de la ACS, capítulo 8). Son aproximaciones que el Negociado del Censo recomienda cuando las tablas publicadas no cubren el área.")}</div>
    <div class="note"><b>{t("Statistical significance.", "Significancia estadística.")}</b> {t("A difference is called significant when it is larger than its own margin of error at 90%, the square root of the sum of the two squared margins. An area is compared with the rest of Puerto Rico so that the two estimates do not include the same people. Windows that share years are never compared.", "Una diferencia se llama significativa cuando es mayor que su propio margen de error al 90 %, la raíz cuadrada de la suma de los dos márgenes al cuadrado. Un área se compara con el resto de Puerto Rico para que los dos estimados no incluyan a las mismas personas. Nunca se comparan períodos que comparten años.")}</div>
    <div class="note"><b>{t("Age-adjusted rate and the split of the gap.", "Tasa ajustada por edad y división de la diferencia.")}</b> {t("Direct standardization: the area's rate in each of seven age groups, weighted by the age mix of the women 16 and over in the rest of the island. The difference with the rest of the island is split into a part due to age mix and a part due to participation within each age (Kitagawa's method, 1955). These two parts have no margin of error on the page.", "Estandarización directa: la tasa del área en cada uno de siete grupos de edad, ponderada por la composición por edad de las mujeres de 16 años o más del resto de la isla. La diferencia con el resto de la isla se divide en una parte debida a la composición por edad y otra debida a la participación dentro de cada edad (método de Kitagawa, 1955). Estas dos partes no tienen margen de error en la página.")}</div>
    <div class="note"><b>{t("Reliability.", "Confiabilidad.")}</b> {t("The coefficient of variation (CV) is the standard error divided by the estimate. Values with a CV over 30% are marked less reliable, the observatory's rule. Survey answers are weighted to represent the whole population.", "El coeficiente de variación (CV) es el error estándar dividido entre el estimado. Los valores con un CV mayor de 30 % se marcan como menos confiables, la regla del observatorio. Las respuestas de la encuesta se ponderan para representar a toda la población.")}</div>
  </section>

  <section class="block" id="sources">
    <h2><span class="ms-icon" aria-hidden="true">menu_book</span>{t("Sources and licenses", "Fuentes y licencias")}</h2>
    <div class="note"><b>{t("American Community Survey, 5-year estimates.", "Encuesta sobre la Comunidad Estadounidense, estimados de 5 años.")}</b> {t("U.S. Census Bureau, tables B23001 (sex by age by employment status), B23003 (females 20 to 64 by own children and employment status), B98003 and B98001 (unweighted sample), windows 2010-2014, 2015-2019 and 2020-2024, read from the Census Bureau's summary files. US Government work, public use without restrictions.", "Negociado del Censo de los EE. UU., tablas B23001 (sexo por edad por situación de empleo), B23003 (mujeres de 20 a 64 años por hijos propios y situación de empleo), B98003 y B98001 (muestra sin ponderar), períodos 2010-2014, 2015-2019 y 2020-2024, leídas de los archivos resumen del Negociado del Censo. Obra del Gobierno de los EE. UU., uso público sin restricciones.")}</div>
    <div class="note"><b>{t("The Eastern Region.", "La Región Este.")}</b> {t("The 15 municipios of FPR's Eastern Region Strategic Vision (ERSV), Human Capital chapter. The other presets are the Puerto Rico Tourism Company's tourism regions, the only other region scheme the observatory holds.", "Los 15 municipios de la Visión Estratégica de la Región Este (ERSV) de FPR, capítulo de Capital Humano. Las otras regiones predefinidas son las regiones turísticas de la Compañía de Turismo de Puerto Rico, el único otro esquema regional que tiene el observatorio.")}</div>
    <div class="note"><b>{t("Data and method.", "Datos y método.")}</b> {t("The data file is data/women_labor.json (women_labor.py) and the map's datasets are in data/labor_sex_series.json; the method and its checks are in docs/analysis/women-labor-2026-10/ of the project repository.", "El archivo de datos es data/women_labor.json (women_labor.py) y los conjuntos de datos del mapa están en data/labor_sex_series.json; el método y sus pruebas están en docs/analysis/women-labor-2026-10/ del repositorio del proyecto.")}</div>
    <div class="note"><b>{t("How to cite this page.", "Cómo citar esta página.")}</b> {t("Foundation for Puerto Rico, Knowledge Area: Women in the labor force, PR Data Observatory, Snapshot 2026-10 (draft). Data: U.S. Census Bureau, American Community Survey 5-year estimates.", "Foundation for Puerto Rico, Área de conocimiento: Las mujeres en la fuerza laboral, Observatorio de Datos de PR, Snapshot 2026-10 (borrador). Datos: Negociado del Censo de los EE. UU., estimados de 5 años de la Encuesta sobre la Comunidad Estadounidense.")}</div>
  </section>
</main>
<script src="js/core/knowledge.js?v=35"></script>
<script>Core.knowledge.render(); I18N.apply();</script>
<script src="js/common.js?v=20"></script>
<script src="js/women_labor.js?v=8"></script>
<script src="js/chatboot.js?v=45"></script>
</body>
</html>
"""
    # A note that starts with a bold lead is translated whole (I18N.apply reads its innerHTML as one key): pair the two halves' Spanish
    for m in re.finditer(r"<b>([^<]*)</b> ([^<]*)</(?:div|p)>", page):
        lead, body = " ".join(html.unescape(m.group(1)).split()), " ".join(html.unescape(m.group(2)).split())
        key = " ".join(f"<b>{m.group(1)}</b> {m.group(2)}".split())
        ES[key] = f"<b>{html.escape(ES[lead], quote=False)}</b> {html.escape(ES[body], quote=False)}"
        ES.pop(lead, None)
        ES.pop(body, None)
    (ROOT / "site" / "women-labor.html").write_text(page, encoding="utf-8", newline="\n")
    es = {"_about": "The Women in the labor force page of the Knowledge Area (women-labor.html) and site/js/women_labor.js. Written by docs/analysis/women-labor-2026-10/make_page.py from its (English, Spanish) pairs: edit them there, not here."}
    es.update(ES)
    (ROOT / "i18n_src" / "es" / "women_labor.json").write_text(json.dumps(es, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(f"wrote site/women-labor.html and i18n_src/es/women_labor.json ({len(ES)} strings)")


if __name__ == "__main__":
    build()
