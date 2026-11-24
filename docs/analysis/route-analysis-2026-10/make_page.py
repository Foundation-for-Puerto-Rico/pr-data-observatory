"""Writes the Route analysis page of the Knowledge Area and its Spanish.

  python make_page.py      read route_compare.json (this folder); write site/route-analysis.html (English), site/data/route_compare.json (the
                           routes, which the page loads) and i18n_src/es/routes.json (the Spanish of the page and of site/js/route_analysis.js).
                           Then run python i18n.py, python dictionary.py and python registry.py.

The page follows the site's language rule (docs/i18n.md): the HTML is in English and every English string is its own key; I18N.apply() puts the
Spanish on the static text and route_analysis.js asks T() for the rest. Each string below is written once, as an (English, Spanish) pair, so the
two files cannot drift apart. The routes are a published data file (site/data/route_compare.json, registered in dictionary_src/datasets.json and
documented in dictionary_src/entries/route_analysis.json), which route_analysis.js loads; the headline figures are written into the page here.
Prepared with Claude (AI), with Zoralis Alicea (FPR), 2026-10.
"""
import csv
import html
import json
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
ES = {}


def t(en, es):
    """An English string and its Spanish; returns the English, for the page."""
    key = " ".join(en.split())
    if key in ES and ES[key] != es:
        raise SystemExit(f"two Spanish texts for {key!r}")
    ES[key] = es
    return en


# Strings route_analysis.js asks T() for (the same English keys as in the script)
JS = [
    ("route {route}", "ruta {route}"),
    ("{route}: {n} times ({am} from 6 to 9 a.m., {pm} from 4 to 7 p.m.)", "{route}: {n} veces ({am} de 6 a 9 a.m. y {pm} de 4 a 7 p.m.)"),
    ("times its buses go through an intersection with heavy traffic, 6–9 a.m. and 4–7 p.m.",
     "veces que los autobuses pasan por una intersección con mucho tránsito, 6–9 a.m. y 4–7 p.m."),
    ("{route}: {n} high-volume intersections on its path; {t} trips a day", "{route}: {n} intersecciones con mucho tránsito en su camino; {t} viajes al día"),
    ("intersections with heavy traffic on a single trip, start to end", "intersecciones con mucho tránsito en un solo viaje, de principio a fin"),
    ("The routes whose trip crosses most high-volume intersections", "Las rutas cuyo viaje cruza más intersecciones con mucho tránsito"),
    ("The 12 routes with most crossings of high-volume intersections at peak hours",
     "Las 12 rutas con más cruces por intersecciones con mucho tránsito en hora pico"),
    ("System", "Sistema"), ("Route", "Ruta"), ("Name", "Nombre"), ("Trips", "Viajes"), ("Frequency", "Frecuencia"),
    ("Km", "Km"), ("Km/h", "Km/h"), ("Total", "Total"), ("Per 10 km", "Por 10 km"),
    ("Crossings a.m.", "Cruces a.m."), ("Crossings p.m.", "Cruces p.m."), ("Train", "Tren"), ("Systems", "Sistemas"),
    ("People", "Personas"), ("Bridges", "Puentes"),
    ("Trips on a weekday, both directions", "Viajes en un día de semana, las dos direcciones"),
    ("Every how many minutes it runs 6 to 9 a.m., in the direction with most trips",
     "Cada cuántos minutos pasa de 6 a 9 a.m., en la dirección con más viajes"),
    ("Length of the main route, in km", "Largo del recorrido principal, en km"),
    ("Scheduled speed, in km an hour", "Velocidad programada, en km por hora"),
    ("Intersections with an estimated 2,000 or more vehicles an hour in the design hour on its path",
     "Intersecciones con un estimado de 2,000 o más vehículos por hora en la hora de diseño en su camino"),
    ("High-volume intersections per 10 km of route", "Intersecciones con mucho tránsito por cada 10 km de recorrido"),
    ("Times its trips cross those intersections 6 to 9 a.m.", "Veces que sus viajes cruzan esas intersecciones de 6 a 9 a.m."),
    ("Times its trips cross those intersections 4 to 7 p.m.", "Veces que sus viajes cruzan esas intersecciones de 4 a 7 p.m."),
    ("Has a stop within 300 m of a Tren Urbano station", "Tiene una parada a 300 m o menos de una estación del Tren Urbano"),
    ("Other systems with a stop within 250 m of its stops", "Otros sistemas con una parada a 250 m o menos de las suyas"),
    ("Residents (2020 Census) within 400 m of a stop, each person counted once",
     "Residentes (Censo 2020) a 400 m de alguna parada, cada persona contada una vez"),
    ("Pedestrian bridges within 30 m of its path", "Puentes peatonales a 30 m o menos de su camino"),
    ("All ({n})", "Todos ({n})"), ("Metro area ({n})", "Área metro ({n})"), ("East ({n})", "Este ({n})"),
    ("Expired timetable", "Horario vencido"), ("Yes", "Sí"), ("No", "No"), ("Estimated", "Estimado"),
    ("Timetable only: see note 3", "Solo horario de punto a punto: vea la nota 3"),
    ("High-volume intersections", "Intersecciones con mucho tránsito"), ("Crossings 6–9 a.m.", "Cruces 6–9 a.m."),
    ("Residents within 400 m", "Residentes a 400 m"), ("5 · Residents", "5 · Residentes"), ("Supplementary", "Suplementario"),
    ("Show all columns ({n})", "Ver todas las columnas ({n})"), ("Show the key columns", "Ver solo las columnas principales"),
    ("(timetable only: length of the route line drawn by the operator)", "(solo horario de punto a punto: largo de la línea que dibuja el operador)"),
    ("Timetables expired today: {names}. They may not reflect the current service.",
     "Horarios vencidos hoy: {names}. Pueden no reflejar el servicio actual."),
    ("No timetable has expired today.", "Ningún horario está vencido hoy."),
    ("The route data could not be loaded ({error}). Check your connection and reload.",
     "No se pudieron cargar los datos de las rutas ({error}). Revise su conexión y vuelva a cargar la página."),
    ("{n} trips a day, from {first} to {last}", "{n} viajes al día, de {first} a {last}"),
    ("At the morning peak, one every {m} min", "En la hora pico de la mañana, uno cada {m} min"),
    ("{km} km", "{km} km"), ("no data", "sin dato"),
    ("{v} km/h scheduled", "{v} km/h programados"), ("speed not calculated", "rapidez sin calcular"),
    ("{n} high-volume intersections ({p} per 10 km). Its trips cross them {am} times 6 to 9 a.m. and {pm} times 4 to 7 p.m.",
     "{n} intersecciones con mucho tránsito ({p} por cada 10 km). Sus viajes las cruzan {am} veces de 6 a 9 a.m. y {pm} veces de 4 a 7 p.m."),
    ("(estimated)", "(estimado)"),
    ("Reaches the Tren Urbano", "Llega al Tren Urbano"), ("Does not reach the Tren Urbano", "No llega al Tren Urbano"),
    ("Shares stops with: {names}", "Comparte paradas con: {names}"),
    ("No connection with the ATI network", "Sin conexión con la red de la ATI"),
    ("1 · Service", "1 · Servicio"), ("2 · Route", "2 · Recorrido"), ("3 · Peak-hour intersections", "3 · Intersecciones en hora pico"),
    ("4 · Connections", "4 · Conexiones"), ("5 · Nearby residents", "5 · Residentes cercanos"),
    ("Supplementary · Pedestrian bridges", "Suplementario · Puentes peatonales"),
    ("{n} within 400 m of one of its {s} stops", "{n} a 400 m de alguna de sus {s} paradas"),
    ("{n} within 30 m of its path", "{n} a 30 m o menos de su camino"), ("none on its path", "ninguno en su camino"),
    ("Timetable expired on {date}: it may not be the current service.", "Horario vencido el {date}: puede no ser el servicio actual."),
]
for en, es in JS:
    t(en, es)

# The fields of site/data/route_compare.json: every column of route_compare.csv (each documented in dictionary_src/entries/route_analysis.json)
FIELDS = ["operator", "operator_name", "region", "route", "name", "timetable_expired", "weekday_trips", "first", "last", "peak_trips_one_direction",
          "peak_headway_min", "length_km", "speed_kmh", "busy_junctions", "busy_per_10km", "busy_passes_6_9", "busy_passes_16_19", "passes_estimated",
          "timepoints_only", "express_two_stops", "minutes_peak", "minutes_midday", "peak_extra_pct", "reaches_tren_urbano", "other_operators",
          "other_operator_names", "stops", "residents_400m", "footbridges_30m", "km_to_ati"]


def main():
    rc = json.loads((HERE / "route_compare.json").read_text(encoding="utf-8"))
    R = rc["routes"]
    M = [r for r in R if r["region"] == "metro"]
    E = [r for r in R if r["region"] == "este"]
    n_busy = sum(1 for r in M if r["busy_junctions"])
    n_tren = sum(1 for r in M if r["reaches_tren_urbano"])
    n_trips = sum(r["weekday_trips"] for r in M)
    r7 = next(r for r in R if r["operator"] == "ati" and r["route"] == "7")
    # the two charts of section 1, as route_analysis.js draws them: the 12 routes with most crossings at both peaks, and the routes whose trip crosses
    # most high-volume intersections (the 12 first and every route tied with the 12th)
    both = lambda r: r["busy_passes_6_9"] + r["busy_passes_16_19"]
    top = sorted(R, key=lambda r: -both(r))[:12]
    assert all(r["operator"] == "ati" for r in top) and top[0] is r7 and top[1]["route"] == "2"   # the notes name routes 7 and 2 (review of #101)
    # the routes of the first chart whose afternoon differs from the morning by 15% or more
    diff = [(r["route"], round(100 * (r["busy_passes_16_19"] - r["busy_passes_6_9"]) / r["busy_passes_6_9"])) for r in top]
    big = [(k, d) for k, d in diff if abs(d) >= 15]
    assert big and all(d > 0 for k, d in big)
    big_en = ", ".join(f"{k} (+{d}%)" for k, d in big[:-1]) + f" and {big[-1][0]} (+{big[-1][1]}%)"
    big_es = ", ".join(f"{k} (+{d}%)" for k, d in big[:-1]) + f" y {big[-1][0]} (+{big[-1][1]}%)"
    byj = sorted(R, key=lambda r: -r["busy_junctions"])
    tied = [r for r in byj if r["busy_junctions"] >= byj[11]["busy_junctions"]]
    assert byj[0] is r7
    # the routes of the second chart with 15 or more on the path that the first chart leaves out (fewer trips)
    extra = [r for r in tied if r not in top and r["busy_junctions"] >= 15]
    ex_ati = [r["route"] for r in extra if r["operator"] == "ati"]
    ex_cag = [r["route"] for r in extra if r["operator"] == "caguas"]
    assert len(ex_ati) >= 2 and len(ex_cag) == 1 and len(extra) == len(ex_ati) + 1
    ex_en = f"ATI routes {', '.join(ex_ati[:-1])} and {ex_ati[-1]} and Caguas's route \"{ex_cag[0]}\" (that is its name)"
    ex_es = f"las rutas {', '.join(ex_ati[:-1])} y {ex_ati[-1]} de la ATI y la ruta «{ex_cag[0]}» de Caguas (así se llama)"
    # the metro routes of the headline that are timetable-only estimates, and the junctions whose K is the class median (road_flow.csv)
    est = [r for r in M if r["busy_junctions"] and r["passes_estimated"]]
    n_est, n_est_bay, n_est_cag = len(est), sum(r["operator"] == "bayamon" for r in est), sum(r["operator"] == "caguas" for r in est)
    assert {r["operator"] for r in est} <= {"bayamon", "caguas", "ati"} and n_est - n_est_bay - n_est_cag == 1
    assert all(r["timetable_expired"] for r in M if r["operator"] == "caguas")
    flow = list(csv.DictReader(open(HERE / "road_flow.csv", encoding="utf-8")))
    k_all, k_imp = len(flow), sum(r["k_imputed"] == "True" for r in flow)
    k_pct = round(100 * k_imp / k_all)
    # the example of a timetable-only route whose line holds both directions: its line (length_km) against its timed path in trips.json
    br1 = next(r for r in R if r["operator"] == "bayamon" and r["route"] == "BR-1")
    trips = json.loads((ROOT / "site" / "data" / "trips.json").read_text(encoding="utf-8"))
    main_k = Counter(x["k"] for x in trips["trips"] if x["o"] == "bayamon" and x["r"] == "BR-1").most_common(1)[0][0]
    br1_path = round(trips["paths"][main_k][-1][2] / 1000, 1)
    assert br1["timepoints_only"] and br1_path < br1["length_km"]
    assert all(list(r) == FIELDS for r in R), "route_compare.json has fields make_page.py does not publish"
    data = {"about": "Bus routes of the ATI and of the municipal systems of the San Juan metro area and eastern Puerto Rico, compared on the weekday "
                     "timetables (typical Wednesday): service, route, peak-hour intersections, connections and nearby residents. The flow that makes an "
                     "intersection high-volume is an estimated design-hour volume (FHWA HPMS 2024 AADT x K factor: the 30th-busiest hour of "
                     "the year, not a typical weekday peak). Built by docs/analysis/route-analysis-2026-10/ (route_compare.py, make_page.py); "
                     "fields in the data dictionary (route_compare.*).",
            "day": rc["day"], "as_of": rc["as_of"],
            "operators": [{"operator": k, "operator_name": v, "feed_end": rc["feed_end"][k]} for k, v in rc["operators"].items()],
            "routes": [{k: r[k] for k in FIELDS} for r in R]}
    title = t("Knowledge Area · Public transit route profile: crossings at high-volume intersections", "Área de conocimiento · Perfil de rutas de transporte colectivo: cruces por intersecciones de alto volumen vehicular")
    desc = ("An exploratory, comparative analysis of the bus routes of the ATI and of the municipal systems of the San Juan metro area and "
            "eastern Puerto Rico: service, route, peak-hour intersections, connections and nearby residents.")
    icons = "account_balance,account_tree,bolt,chat_bubble,close,commute,compare_arrows,dark_mode,delete,directions_bus,diversity_3,explore,grid_view,home_work,hourglass_bottom,info,light_mode,lightbulb,map,menu_book,payments,price_change,rocket_launch,route,school,send,thermostat,view_in_ar,warning,water,wifi,woman,work"
    page = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<meta name="description" content="{html.escape(desc)}">
<meta name="theme-color" content="#FFFFFF">
<!-- Published with the "In review" marker kept, like WCRP: held back from search engines while the marker is on (docs/knowledge-areas.md). -->
<meta name="robots" content="noindex, nofollow">
<link rel="icon" href="img/fpr-mark.png">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Material+Symbols+Rounded:opsz,wght,FILL,GRAD@24,400,1,0&icon_names={icons}&display=block">
<link rel="stylesheet" href="css/twin.css?v=62">
<link rel="stylesheet" href="css/housing.css?v=21">
<link rel="stylesheet" href="css/route_analysis.css?v=5">
<link rel="stylesheet" href="css/chat.css?v=4">
<link rel="stylesheet" href="css/ws.css?v=1">
<script src="js/i18n.js?v=69" data-page="routes"></script>
</head>
<body class="research">
<a class="skip" href="#about">Skip to the content</a>
<header class="topbar">
  <a class="logo" href="index.html" title="PR Data Observatory home"><img src="img/fpr-logo.png" alt="Foundation for Puerto Rico. PR Data Observatory home"></a>
  <div class="brand"><b>{t("Knowledge Area · Transit congestion", "Área de conocimiento · Congestión en las rutas")}</b><span>{t("Bus routes of the metro area and the east, one by one", "Rutas de autobús del área metro y del este, una por una")}</span></div>
  <div class="spacer"></div>
  <nav class="views" aria-label="Views">
    <a class="btn" href="explore.html" title="Explore: start from a question, a topic or a saved map"><span class="ms-icon" aria-hidden="true">explore</span><span class="lbl">Explore</span></a>
    <a class="btn" href="data.html" title="Data: every dataset, map layer and set of places"><span class="ms-icon" aria-hidden="true">grid_view</span><span class="lbl">Data</span></a>
    <a class="btn" href="index.html"><span class="ms-icon" aria-hidden="true">map</span><span class="lbl">Map</span></a>
    <a class="btn" href="workflows.html" title="Workflows: steps that turn data into a result on the map"><span class="ms-icon" aria-hidden="true">account_tree</span><span class="lbl">Workflows</span></a>
    <a class="btn" href="3d.html" title="Immersive 3D + time view"><span class="ms-icon" aria-hidden="true">view_in_ar</span><span class="lbl">3D + Time</span></a>
    <a class="btn" href="knowledge.html" aria-current="page" title="Knowledge: FPR studies, analyses and tools"><span class="ms-icon" aria-hidden="true">lightbulb</span><span class="lbl">Knowledge</span></a>
    <a class="btn" href="dictionary.html" title="Data dictionary: meanings, sources, licenses, how to cite"><span class="ms-icon" aria-hidden="true">menu_book</span><span class="lbl">Data dictionary</span></a>
    <a class="btn" href="learn.html" title="Learn: short lessons about maps and spatial analysis"><span class="ms-icon" aria-hidden="true">school</span><span class="lbl">Learn</span></a>
  </nav>
</header>

<nav class="toc" id="toc" aria-label="On this page">
  <span class="ka-tabs" role="group" aria-label="Knowledge Area" data-ka="routes"></span><span class="ka-sep" aria-hidden="true"></span>
  <a href="#about">{t("Summary", "Resumen")}</a><a href="#exposure">{t("Busy intersections", "Intersecciones con mucho tránsito")}</a><a href="#compare">{t("Route comparison", "Comparación de rutas")}</a><a href="#sources">{t("Sources and licenses", "Fuentes y licencias")}</a>
</nav>

<main class="page">
  <div class="note caution review-note" role="note" data-ka-note></div>

  <section class="hero" id="about">
    <div class="eyebrow">{t("Knowledge Area · Research", "Área de conocimiento · Investigación")}</div>
    <h1>{t("Public transit route profile: crossings at high-volume intersections", "Perfil de rutas de transporte colectivo: cruces por intersecciones de alto volumen vehicular")}</h1>
    <p class="lede">{t(
        "This exploratory, comparative analysis examines, one by one, the bus routes that run in the San Juan metropolitan area and in the municipios of eastern Puerto Rico. "
        "Using the official weekday timetables (GTFS), each route is analysed on five dimensions: the level of service, the route, the intersections with heavy traffic on its path at peak hours, "
        "the integration with other services and the population near its stops. The analysis focuses on crossings at high-volume intersections; the other four dimensions help compare the routes.",
        "Este análisis exploratorio y comparativo examina, una por una, las rutas de autobús que operan en el área metropolitana de San Juan y en los municipios del este de Puerto Rico. "
        "A partir de los horarios oficiales de un día de semana (GTFS), cada ruta se analiza en cinco dimensiones: el nivel de servicio, el recorrido, las intersecciones con mucho tránsito en su camino en horas pico, "
        "la integración con otros servicios y la población cercana a sus paradas. El análisis se centra en los cruces por intersecciones de alto volumen vehicular; las otras cuatro dimensiones ayudan a comparar las rutas.")}</p>
    <div class="kpi-row">
      <div class="kpi"><b>{len(M)}</b><span>{t("bus routes in the metropolitan area: the ATI and 5 municipal systems", "rutas de autobús en el área metropolitana: ATI y 5 sistemas municipales")}</span></div>
      <div class="kpi"><b>{n_trips:,}</b><span>{t("scheduled trips on a weekday on those routes", "viajes programados en un día de semana en esas rutas")}</span></div>
      <div class="kpi"><b>{t(f"{n_busy} of {len(M)}", f"{n_busy} de {len(M)}")}</b><span>{t("routes go through intersections with heavy traffic at peak hours", "rutas pasan por intersecciones con mucho tránsito en hora pico")}</span></div>
      <div class="kpi"><b>{t(f"{n_tren} of {len(M)}", f"{n_tren} de {len(M)}")}</b><span>{t("routes have a stop within 300 m of a Tren Urbano station", "rutas tienen una parada a 300 m o menos de una estación del Tren Urbano")}</span></div>
      <div class="kpi"><b>{len(E)}</b><span>{t(f"more routes from {len({r['operator'] for r in E})} eastern systems, with no connection to the ATI network", f"rutas adicionales de {len({r['operator'] for r in E})} sistemas del este, sin conexión con la red de la ATI")}</span></div>
    </div>
    <p class="legend-note">{t(
        f"<b>About the {n_busy} of {len(M)}:</b> {n_est} of them are estimates, marked with an asterisk in the table (note 3).",
        f"<b>Sobre las {n_busy} de {len(M)}:</b> {n_est} de ellas son estimados, marcados con asterisco en la tabla (nota 3).")}</p>
    <p class="legend-note">{t(
        "Foundation for Puerto Rico prepared this analysis for the PR Data Observatory with public data: the timetables of the ATI and of the municipal systems, "
        "the traffic of the Federal Highway Administration (HPMS 2024), OpenStreetMap and the 2020 Census.",
        "Foundation for Puerto Rico preparó este análisis para el Observatorio de Datos de PR con datos públicos: los horarios de la ATI y de los sistemas municipales, "
        "el tráfico de la Administración Federal de Carreteras (HPMS 2024), OpenStreetMap y el Censo 2020.")}</p>
  </section>

  <section class="block" id="exposure">
    <h2><span class="ms-icon" aria-hidden="true">directions_bus</span>{t("1 · The 12 routes that cross busy intersections most often at peak hours", "1 · Las 12 rutas que más veces cruzan intersecciones con mucho tránsito en horas pico")}</h2>
    <p class="ra-p">{t(
        "Here an intersection with heavy traffic is one where an estimated 2,000 or more vehicles pass in an hour, in one of the busiest hours of the year (note 1). "
        "A bus can lose time there, but this analysis does not measure it: using each route's weekday timetable, the two charts count those intersections on its path. "
        "The Tren Urbano is left out: it does not share the street.",
        "Aquí, una intersección con mucho tránsito es una por donde pasan un estimado de 2,000 vehículos por hora o más, en una de las horas más cargadas del año (nota 1). "
        "Un autobús puede perder tiempo allí, pero este análisis no lo mide: con el horario de un día de semana de cada ruta, las dos gráficas cuentan esas intersecciones en su camino. "
        "El Tren Urbano no se incluye porque no comparte la calle.")}</p>
    <div class="card ra-chart"><div class="card-head"><h3>{t("How many times do the buses of each route go through those intersections at peak hours?", "¿Cuántas veces pasan los autobuses de cada ruta por esas intersecciones en horas pico?")}</h3></div>
    <p class="ra-p rc-foot">{t(
        "<b>How to read it:</b> each bar is a route. The number at the end of the bar is the total times the buses of that route go through an intersection with heavy traffic, from 6 to 9 a.m. and from 4 to 7 p.m. "
        "For example, a route with 10 trips in those hours, each going through 5 of those intersections, adds up to 50.",
        "<b>Cómo leer:</b> cada barra es una ruta. El número al final de la barra es el total de veces que los autobuses de esa ruta pasan por una intersección con mucho tránsito, de 6 a 9 a.m. y de 4 a 7 p.m. "
        "Por ejemplo, una ruta con 10 viajes en esas horas, y cada viaje por 5 de esas intersecciones, suma 50.")}</p><div id="rcChart"></div></div>
    <p class="ra-p rc-foot">{t(
        f"<b>Morning and afternoon.</b> In the afternoon, routes {big_en} add up to more than in the morning; in the other {12 - len(big)} routes the difference is under 15%.",
        f"<b>Mañana y tarde.</b> En la tarde, las rutas {big_es} suman más que en la mañana; en las otras {12 - len(big)} rutas la diferencia es menor de 15%.")}</p>
    <div class="note">{t(
        f"<b>What it shows:</b> the buses of ATI routes 7 (Estación Cupey to Terminal Carolina) and 2 go through those intersections {both(r7):,} and {both(top[1]):,} times, "
        f"well above the third route ({both(top[2]):,}).",
        f"<b>Lo que muestra:</b> los autobuses de las rutas 7 (Estación Cupey a Terminal Carolina) y 2 de la ATI pasan {both(r7):,} y {both(top[1]):,} veces por esas intersecciones, "
        f"muy por encima de la tercera ruta ({both(top[2]):,}).")}</div>
    <p class="ra-p">{t(
        "The first chart adds up all the trips, so a route with more trips comes out higher. The second counts a single trip only, from start to end.",
        "La primera gráfica suma todos los viajes, por eso una ruta con más viajes sale más alta. La segunda cuenta un solo viaje, de principio a fin.")}</p>
    <div class="card ra-chart"><div class="card-head"><h3>{t("How many of those intersections does one trip go through?", "¿Por cuántas de esas intersecciones pasa un solo viaje?")}</h3></div>
    <p class="ra-p rc-foot">{t(
        f"<b>How to read it:</b> each bar is a route. The number at the end of the bar is how many intersections with heavy traffic there are on a single trip, from the first stop to the last. The {len(tied)} routes with most are shown (there is a tie). "
        "<b class=\"rc-flag\">!</b> Expired timetable.",
        f"<b>Cómo leer:</b> cada barra es una ruta. El número al final de la barra es cuántas intersecciones con mucho tránsito hay en un solo viaje, desde la primera parada hasta la última. Se muestran las {len(tied)} rutas con más (hay un empate). "
        "<b class=\"rc-flag\">!</b> Horario vencido.")}</p><div id="rcChart2"></div></div>
    <div class="note">{t(
        f"<b>What it shows:</b> route 7 also leads on a single trip, with {r7['busy_junctions']}. {ex_en[0].upper() + ex_en[1:]} are not in the first chart, because they have few trips a day, "
        "but each of their trips goes through 15 or more of these intersections.",
        f"<b>Lo que muestra:</b> la ruta 7 también es la primera en un solo viaje, con {r7['busy_junctions']}. {ex_es[0].upper() + ex_es[1:]} no salen en la primera gráfica porque tienen pocos viajes al día, "
        "pero cada uno de sus viajes pasa por 15 o más de estas intersecciones.")}</div>
    <div class="ra-notes"><p id="note1">{t(
        "<b>1.</b> <b>How the flow is estimated.</b> It is the annual average daily traffic (AADT) of the busiest road within 30 m of the intersection, multiplied by its K factor: "
        "the share of AADT that passes in the design hour, the 30th-busiest hour of the year (FHWA, HPMS 2024, Field Manual item 26). "
        "So the 2,000 vehicles an hour apply to one of the busiest hours of the year, not to a typical weekday peak. HPMS requires K only on its Sample Panel sections; "
        f"for {k_imp:,} of the {k_all:,} intersections ({k_pct}%) the road has none, and the observatory used the median K of the road class: its own estimate, which HPMS guidance does not endorse "
        "(it says statewide or system-wide values shall not be used).",
        "<b>1.</b> <b>Cómo se estima el flujo.</b> Es el tránsito promedio diario anual (AADT) de la carretera más cargada a 30 m o menos de la intersección, multiplicado por su factor K: "
        "la parte del AADT que pasa en la hora de diseño, la trigésima hora de más tránsito del año (FHWA, HPMS 2024, Manual de campo, dato 26). "
        "Así, los 2,000 vehículos por hora se refieren a una de las horas de más tránsito del año, no a una hora pico típica de un día de semana. HPMS exige el factor K solo en sus tramos de muestra (Sample Panel); "
        f"en {k_imp:,} de las {k_all:,} intersecciones ({k_pct}%) la carretera no lo tiene, y el observatorio usó la mediana del factor K de su clase de carretera: un estimado propio, que la guía de HPMS no avala "
        "(indica que no se usen valores estatales ni por sistema).")}</p></div>
  </section>

  <section class="block" id="compare">
    <h2><span class="ms-icon" aria-hidden="true">compare_arrows</span>{t("2 · Route comparison", "2 · Comparación de las rutas")}</h2>
    <p class="ra-p">{t(
        "Each row is a route of the metro area or of the east (note 2). Sort by any column, see all the columns with the button, and select a row to see the card of the route.",
        "Cada fila es una ruta del área metropolitana o del este (nota 2). Puede ordenar por cualquier columna, ver todas las columnas con el botón y seleccionar una fila para ver la ficha de la ruta.")}</p>
    <div class="rc-ops" role="group" aria-label="{t("System", "Sistema")}" id="rcOps"></div>
    <div class="rc-wide">
      <div class="rc-tools"><button type="button" class="rc-toggle" id="rcAll" aria-pressed="false" aria-controls="rcTable" data-t="skip"></button></div>
      <div class="rc-wrap"><table class="rc compact" id="rcTable">
      <thead>
        <tr class="rc-group" id="rcGroup"></tr>
        <tr id="rcHead"></tr>
      </thead>
      <tbody id="rcBody" data-no-glossary></tbody>
    </table></div></div>
    <p class="ra-p rc-foot">{t(
        "Hovering over a heading shows its definition. <b class=\"rc-flag\">*</b> by the route: its crossings are an estimate from a timetable with times only at the ends of each trip (note 3). <b class=\"rc-flag\">!</b> by the system: expired timetable.",
        "Al colocar el cursor sobre un título se muestra su definición. <b class=\"rc-flag\">*</b> junto a la ruta: sus cruces son un estimado de un horario con hora solo en los extremos de cada viaje (nota 3). <b class=\"rc-flag\">!</b> junto al sistema: horario vencido.")}</p>
    <p class="ra-p rc-foot" id="rcExpired" data-t="skip"></p>
    <div class="card rc-detail" id="rcDetail" aria-live="polite"></div>
    <div class="note">{t(
        "<b>Definitions.</b> <i>Trips:</i> trips on a weekday, both directions. <i>Frequency:</i> every how many minutes it runs from 6 to 9 a.m., in the direction with most trips. "
        "<i>High-volume intersections:</i> those with heavy traffic (section 1) on its path. "
        "<i>Crossings 6–9 a.m.:</i> how many times its trips cross them in that period. <i>Residents within 400 m:</i> people (2020 Census) within 400 m of a stop, each counted once per route.",
        "<b>Definiciones.</b> <i>Viajes:</i> viajes en un día de semana, las dos direcciones. <i>Frecuencia:</i> cada cuántos minutos pasa de 6 a 9 a.m., en la dirección con más viajes. "
        "<i>Intersecciones con mucho tránsito:</i> las de la sección 1 que hay en su camino. "
        "<i>Cruces 6–9 a.m.:</i> cuántas veces las cruzan sus viajes en ese horario. <i>Residentes a 400 m:</i> personas (Censo 2020) a 400 m de alguna parada, cada una contada una vez por ruta.")}</div>
    <div class="ra-notes">
      <p id="note2">{t(
        "<b>2.</b> <b>Regions.</b> The metropolitan area includes the ATI (AMA) and the municipal systems with at least one stop within 250 m of an ATI stop: San Juan, Bayamón, Guaynabo, Caguas and Canóvanas. "
        "The east includes Fajardo, Humacao, Juncos, San Lorenzo, Patillas and Vieques, which run their own systems with no connection to the ATI network.",
        "<b>2.</b> <b>Regiones.</b> El área metropolitana incluye la ATI (AMA) y los sistemas municipales con al menos una parada a 250 m o menos de una parada de la ATI: San Juan, Bayamón, Guaynabo, Caguas y Canóvanas. "
        "El este incluye Fajardo, Humacao, Juncos, San Lorenzo, Patillas y Vieques, que operan sistemas propios sin conexión con la red de la ATI.")}</p>
      <p id="note3">{t(
        "<b>3.</b> <b>Timetable only.</b> The timetables of Bayamón, Caguas, Juncos and San Lorenzo, and of ATI express route 20 (two stops), "
        "give the time only at the first and the last stop of each trip. For these routes the <i>Km</i> is the length of the route line the operator draws, which on some routes holds both directions "
        f"(Bayamón BR-1: {br1['length_km']} km of line, {br1_path} km between its two timed stops); the <i>Km/h</i> is that of the stretch between the two timed stops, and is left blank when that stretch is under half the line; "
        "and the crossings are estimated as the trips of the period times the high-volume intersections on the line.",
        "<b>3.</b> <b>Solo horario de punto a punto.</b> Los horarios de Bayamón, Caguas, Juncos y San Lorenzo, y el de la ruta expreso 20 de la ATI (dos paradas), "
        "dan la hora solo en la primera y la última parada de cada viaje. En estas rutas, el <i>Km</i> es el largo de la línea de la ruta que dibuja el operador, que en algunas rutas incluye las dos direcciones "
        f"(Bayamón BR-1: {br1['length_km']} km de línea, {br1_path} km entre sus dos paradas con hora); los <i>Km/h</i> son los del tramo entre las dos paradas con hora, y quedan en blanco cuando ese tramo es menos de la mitad de la línea; "
        "y los cruces se estiman como los viajes del horario por las intersecciones con mucho tránsito en la línea.")}</p>
      <p id="note4">{t(
        "<b>4.</b> <b>The other columns</b> (with the button and in the card of each route): <i>Km</i> and scheduled <i>Km/h</i>; intersections with heavy traffic <i>Per 10 km</i>; "
        "<i>Crossings p.m.</i> (4 to 7 p.m.); <i>Train</i> (a stop within 300 m of a station); <i>Systems</i> (other systems with stops within 250 m); "
        "and pedestrian <i>Bridges</i> within 30 m of its path.",
        "<b>4.</b> <b>Las demás columnas</b> (con el botón y en la ficha de cada ruta): <i>Km</i> y <i>Km/h</i> programados; intersecciones con mucho tránsito <i>Por 10 km</i>; "
        "<i>Cruces p.m.</i> (4 a 7 p.m.); <i>Tren</i> (una parada a 300 m o menos de una estación); <i>Sistemas</i> (otros sistemas con paradas a 250 m); "
        "y <i>Puentes</i> peatonales a 30 m o menos de su camino.")}</p>
      <p id="note5">{t(
        "<b>5.</b> <b>Limitations.</b> ATI route 20 (Estación Bayamón to Terminal Campanilla) is an express service with two stops, so few residents live near it. "
        "Some routes of San Juan and Canóvanas have scheduled speeds under 8 km/h, possibly because their timetable includes long waits. "
        "The routes of Humacao and Patillas are under 4 km long, with scheduled speeds under 6 km/h. "
        "Cataño and Toa Baja do not publish timetables in GTFS format, so they are not included.",
        "<b>5.</b> <b>Limitaciones.</b> La ruta 20 de la ATI (Estación Bayamón a Terminal Campanilla) es un servicio expreso con dos paradas, por lo que la población cercana es baja. "
        "Algunas rutas de San Juan y de Canóvanas tienen velocidades programadas menores de 8 km/h, posiblemente porque su horario incluye esperas prolongadas. "
        "Las rutas de Humacao y Patillas tienen recorridos de menos de 4 km y velocidades programadas menores de 6 km/h. "
        "Cataño y Toa Baja no publican horarios en formato GTFS, por lo que no se incluyen.")}</p>
    </div>
  </section>

  <section class="block" id="sources">
    <h2><span class="ms-icon" aria-hidden="true">info</span>{t("Sources and licenses", "Fuentes y licencias")}</h2>
    <div class="note">{t(
        "<b>Intersections and pedestrian bridges.</b> © OpenStreetMap contributors, ODbL (Geofabrik extract of 2026-10-15). An intersection with heavy traffic (section 1) is a junction with a traffic signal or a roundabout.",
        "<b>Intersecciones y puentes peatonales.</b> © colaboradores de OpenStreetMap, ODbL (extracto de Geofabrik al 2026-10-15). Una intersección con mucho tránsito (sección 1) es un cruce con semáforo o rotonda.")}</div>
    <div class="note">{t(
        "<b>Traffic in the design hour (estimate).</b> US Department of Transportation, Federal Highway Administration, Highway Performance Monitoring System (HPMS), 2024 data. US Government work, public use without restrictions. "
        "How the flow at each intersection is estimated with the K factor: note 1 (section 1). "
        "HPMS covers state and federal-aid roads, so an intersection of local streets has no flow and is not counted.",
        "<b>Tránsito en la hora de diseño (estimado).</b> US Department of Transportation, Federal Highway Administration, Highway Performance Monitoring System (HPMS), datos de 2024. Obra del gobierno de EE. UU., uso público sin restricciones. "
        "Cómo se estima el flujo en cada intersección con el factor K: nota 1 (sección 1). "
        "HPMS cubre las carreteras estatales y de ayuda federal, por lo que una intersección de calles locales no tiene flujo y no se cuenta.")}</div>
    <div class="note">{t(
        "<b>Timetables.</b> Autoridad de Transporte Integrado (ATI) and the municipal systems of San Juan, Bayamón, Guaynabo, Caguas, Canóvanas, Fajardo, Humacao, Juncos, San Lorenzo, Patillas and Vieques: the GTFS timetables the PR Data Observatory already uses.",
        "<b>Horarios.</b> Autoridad de Transporte Integrado (ATI) y los sistemas municipales de San Juan, Bayamón, Guaynabo, Caguas, Canóvanas, Fajardo, Humacao, Juncos, San Lorenzo, Patillas y Vieques: horarios en formato GTFS que integra el Observatorio de Datos de PR.")}</div>
    <div class="note">{t(
        "<b>Residents.</b> 2020 Census, population by block (U.S. Census Bureau, US Government work).",
        "<b>Residentes.</b> Censo 2020, población por bloque (U.S. Census Bureau, obra del gobierno de EE. UU.).")}</div>
    <div class="note">{t(
        "<b>Method.</b> The results and how they were made are in docs/analysis/route-analysis-2026-10/ of the project repository.",
        "<b>Metodología.</b> Los resultados y cómo se calcularon están en docs/analysis/route-analysis-2026-10/ del repositorio del proyecto.")}</div>
    <div class="note">{t(
        "<b>How to cite this page.</b> Foundation for Puerto Rico, <i>Knowledge Area: Public transit route profile: crossings at high-volume intersections</i>, PR Data Observatory, Snapshot 2026-10 (draft).",
        "<b>Cómo citar esta página.</b> Foundation for Puerto Rico, <i>Área de conocimiento: Perfil de rutas de transporte colectivo: cruces por intersecciones de alto volumen vehicular</i>, Observatorio de Datos de PR, Corte 2026-10 (borrador).")}</div>
  </section>
</main>
<script src="js/core/knowledge.js?v=35"></script>
<script>Core.knowledge.render(); I18N.apply();</script>
<script src="js/common.js?v=20"></script>
<script src="js/route_analysis.js?v=7"></script>
<script src="js/chatboot.js?v=45"></script>
</body>
</html>
"""
    (ROOT / "site" / "route-analysis.html").write_text(page, encoding="utf-8", newline="\n")
    (ROOT / "site" / "data" / "route_compare.json").write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8",
                                                              newline="\n")
    out = {"_about": "The Route analysis page of the Knowledge Area (route-analysis.html) and site/js/route_analysis.js. Written by "
                     "docs/analysis/route-analysis-2026-10/make_page.py from its (English, Spanish) pairs: edit them there, not here."}
    out.update(ES)
    (ROOT / "i18n_src" / "es" / "routes.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(f"site/route-analysis.html, site/data/route_compare.json and i18n_src/es/routes.json written: {len(R)} routes, {len(ES)} strings")


if __name__ == "__main__":
    main()
