"""Writes the Knowledge Area page "Public spending" (site/public-spending.html) and its Spanish (i18n_src/es/public_spending.json).

  python docs/analysis/public-spending-2026-11/make_page.py   read site/data/spending_state.json (python ogp_budget.py makes it); write the page and the
                                                              Spanish of the page and of site/js/public_spending.js. Then run python i18n.py.

The page follows the site's language rule (docs/i18n.md): the HTML is in English and every English string is its own key; I18N.apply() puts the
Spanish on the static text and public_spending.js asks T() for the rest. Every string is written once, as an (English, Spanish) pair, so the two
files cannot drift apart, and every figure in the text is read from the data file (as on the FEMA disaster funding page). Public spending PR 4
(HANDOFF decision 78). The page states facts and draws no conclusions. Prepared with Claude (AI) for FPR, 2026-11-04.
"""
import html
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
DATA = ROOT / "site" / "data" / "spending_state.json"

ES = {}
# A string the site already translates keeps that Spanish (i18n.py --check refuses two Spanish texts for one English key)
SITE_ES = {}
for f in sorted((ROOT / "i18n_src" / "es").glob("*.json")):
    if f.name not in ("public_spending.json", "public_spending_after.json"):
        try:
            SITE_ES.update({k: v for k, v in json.loads(f.read_text(encoding="utf-8")).items() if isinstance(v, str) and not k.startswith("_")})
        except ValueError:
            pass


HELD = {}   # strings about federal grant work: the Spanish pages show English until Finance and Compliance review them (docs/i18n.md, decision 21)
HOLD = re.compile(r"CDBG|LIHTC|WCRP|\bHUD\b", re.I)


def t(en, es):
    """An English string and its Spanish; returns the English (escaped), for the page. A string that names federal grant work keeps its Spanish
    in i18n_src/held_for_review.json and shows English on the Spanish page (decision 21)."""
    key = " ".join(en.split())
    es = SITE_ES.get(key, es)
    if HOLD.search(key) or HOLD.search(es):
        HELD[key] = " ".join(es.split())
        es = key
    if key in ES and ES[key] != " ".join(es.split()):
        raise SystemExit(f"two Spanish texts for {key!r}")
    ES[key] = " ".join(es.split())
    return html.escape(key, quote=False)


def tb(label_en, label_es, text_en, text_es):
    """A note's bold label and its text as one key (the HTML of the note), so I18N.apply translates the whole note."""
    e = lambda x: html.escape(" ".join(x.split()), quote=False)
    en, es = f"<b>{e(label_en)}</b> {e(text_en)}", f"<b>{e(label_es)}</b> {e(text_es)}"
    key = SITE_ES.get(en) and en or en
    es = SITE_ES.get(en, es)
    if HOLD.search(en) or HOLD.search(es):
        HELD[en] = es
        es = en
    if en in ES and ES[en] != es:
        raise SystemExit(f"two Spanish texts for {en!r}")
    ES[en] = es
    return key


def bn(x):
    return f"{x / 1e9:.2f}"


# Strings public_spending.js asks T() for (the same English keys as in the script)
JS = [
    ("The data could not be loaded ({error}). Check your connection and reload.", "No se pudieron cargar los datos ({error}). Verifique su conexión y vuelva a cargar la página."),
    ("billion", "mil millones"), ("million", "millones"),
    ("Education", "Educación"), ("Health", "Salud"), ("Public safety", "Seguridad pública"), ("Transportation", "Transportación"), ("Housing", "Vivienda"),
    ("Parks, recreation and culture", "Parques, recreación y cultura"), ("Environment and natural resources", "Ambiente y recursos naturales"),
    ("Economic development", "Desarrollo económico"), ("Utilities, energy and communications", "Servicios públicos, energía y comunicaciones"),
    ("Social services", "Servicios sociales"), ("Debt and pensions", "Deuda y pensiones"), ("General government", "Gobierno general"), ("Other", "Otros"),
    ("Payroll", "Nómina"), ("Purchased and professional services", "Servicios comprados y profesionales"),
    ("Transfers, subsidies and contributions", "Transferencias, subsidios y aportaciones"), ("Capital works and equipment", "Obras permanentes y equipo"),
    ("Debt service", "Servicio de la deuda"), ("Other expenses", "Otros gastos"),
    ("General Fund", "Fondo General"), ("Federal funds", "Fondos federales"), ("Special funds", "Fondos especiales"),
    ("spent", "gastado"), ("approved", "aprobado"), ("proposed", "propuesto"),
    ("FY{year} {stage}", "AF {year} {stage}"),
    ("Treemap: {fn}, {col}, by agency", "Mapa de árbol: {fn}, {col}, por agencia"),
    ("Treemap: {col}, by function", "Mapa de árbol: {col}, por función"),
    ("{label}: {value} ({share} of the total)", "{label}: {value} ({share} del total)"),
    ("{fn}: {value}, by agency. Select “All functions” to go back.", "{fn}: {value}, por agencia. Seleccione «Todas las funciones» para regresar."),
    ("{col}: {value}, by function. Select a function to see its agencies.", "{col}: {value}, por función. Seleccione una función para ver sus agencias."),
    ("Total", "Total"), ("Agency", "Agencia"), ("Function", "Función"), ("Dollars", "Dólares"), ("Share", "Proporción"),
    ("{fn} by agency, {col}", "{fn} por agencia, {col}"), ("By function, {col}", "Por función, {col}"),
    ("No fiscal year has both an approved and a spent column yet.", "Todavía ningún año fiscal tiene una columna de aprobado y una de gastado."),
    ("Dot plot: approved and spent by function, FY{year}. The table below has the figures.", "Gráfico de puntos: aprobado y gastado por función, AF {year}. La tabla de abajo tiene las cifras."),
    ("{fn}: {spent} spent of {approved} approved ({share})", "{fn}: {spent} gastado de {approved} aprobado ({share})"),
    ("{share} spent", "{share} gastado"), ("not approved", "no aprobado"),
    ("FY{year}: {spent} spent of {approved} approved ({share}). Hollow dot: approved; filled dot: spent.", "AF {year}: {spent} gastado de {approved} aprobado ({share}). Punto hueco: aprobado; punto lleno: gastado."),
    ("Approved and spent by function, FY{year}", "Aprobado y gastado por función, AF {year}"), ("Approved", "Aprobado"), ("Spent", "Gastado"),
    ("Spent as a share of approved", "Gastado como proporción de lo aprobado"),
    ("Bars: each column of the budget by fund. The table below has the figures.", "Barras: cada columna del presupuesto por fondo. La tabla de abajo tiene las cifras."),
    ("Each column of the budget by fund", "Cada columna del presupuesto por fondo"), ("Column", "Columna"),
    ("{col}, by what the money pays for", "{col}, por lo que paga el dinero"),
    ("dollars per resident", "dólares por residente"), ("dollars", "dólares"), ("no projects", "sin proyectos"),
    ("Map: capital projects of the four-year program by municipio, {measure}", "Mapa: proyectos de mejoras capitales del programa de cuatro años por municipio, {measure}"),
    ("{a} to {b}", "{a} a {b}"), ("{a} or more", "{a} o más"),
    ("Not placed in a municipio", "Sin ubicar en un municipio"),
    ("{share} of the program{agency}: lines for a region, several municipios, the whole island or no defined place. They are not on the map.",
     "{share} del programa{agency}: líneas para una región, varios municipios, toda la isla o un lugar no definido. No están en el mapa."),
    ("On the map: {placed}. Total of the lines read: {all}.", "En el mapa: {placed}. Total de las líneas leídas: {all}."),
    ("Four-year program", "Programa de cuatro años"), ("Per resident", "Por residente"), ("No projects in this municipio.", "No hay proyectos en este municipio."),
    ("Show the ranking", "Ver la clasificación"),
    ("Capital projects planned per resident: the ten highest municipios", "Mejoras capitales planificadas por residente: los diez municipios más altos"),
    ("Capital projects planned, in dollars: the ten highest municipios", "Mejoras capitales planificadas, en dólares: los diez municipios más altos"),
    ("Disaster recovery subawards per resident: the ten highest municipios", "Subadjudicaciones de recuperación por residente: los diez municipios más altos"),
    ("Disaster recovery subawards, in dollars: the ten highest municipios", "Subadjudicaciones de recuperación, en dólares: los diez municipios más altos"),
    ("Select a municipio on the map to see its agencies.", "Seleccione un municipio en el mapa para ver sus agencias."),
    ("Capital projects by municipio, fiscal years {a} to {b}", "Proyectos de mejoras capitales por municipio, años fiscales {a} a {b}"),
    ("Municipio", "Municipio"), ("All agencies", "Todas las agencias"),
    ("The program for fiscal years {a} to {b}: {total} in project lines, of the {stated} the program states.",
     "El programa de los años fiscales {a} a {b}: {total} en líneas de proyectos, de los {stated} que indica el programa."),
    ("under {b}", "menos de {b}"),
    ("Grants", "Subvenciones"), ("Direct payments", "Pagos directos"), ("Contracts", "Contratos"),
    ("Loans (cost to the government)", "Préstamos (costo para el gobierno)"), ("Insurance and other", "Seguros y otros"),
    ("Contracts, loans and other", "Contratos, préstamos y otros"),
    ("Federal FY{year}", "AF federal {year}"),
    ("Federal fiscal year {year} (October {prev} to September {year}): {total}, by function",
     "Año fiscal federal {year} (octubre de {prev} a septiembre de {year}): {total}, por función"),
    ("The 15 largest programs, federal fiscal year {year}", "Los 15 programas más grandes, año fiscal federal {year}"),
    ("Program", "Programa"), ("Award type", "Tipo de adjudicación"),
    ("Columns: federal money in Puerto Rico in each federal fiscal year. The selector above changes the year.",
     "Columnas: fondos federales en Puerto Rico en cada año fiscal federal. El selector de arriba cambia el año."),
    ("no subawards", "sin subadjudicaciones"),
    ("Map: disaster recovery subawards by municipio, federal fiscal years {a} to {b}. The table below has the figures.",
     "Mapa: subadjudicaciones de recuperación por desastres por municipio, años fiscales federales {a} a {b}. La tabla de abajo tiene las cifras."),
    ("Federal fiscal years {a} to {b}", "Años fiscales federales {a} a {b}"),
    ("Prime grants obligated to the Department of Housing", "Subvenciones principales obligadas al Departamento de la Vivienda"),
    ("Subawards reported", "Subadjudicaciones informadas"), ("On the map", "En el mapa"),
    ("The subawards are {share} of the prime grants in these years; the rest is spent through the Department\u2019s own programs and contracts and is not placed by USAspending.",
     "Las subadjudicaciones son el {share} de las subvenciones principales en estos años; el resto se gasta mediante los programas y contratos propios del Departamento y USAspending no lo ubica."),
    ("Commonwealth budget, FY{year} approved", "Presupuesto del Gobierno, AF {year} aprobado"),
    ("{share} of the budget", "{share} del presupuesto"),
    ("Spent in FY{year}", "Gastado en el AF {year}"),
    ("{spent} of {approved} approved ({share})", "{spent} de {approved} aprobado ({share})"),
    ("Federal obligations, federal FY{year}", "Obligaciones federales, AF federal {year}"),
    ("Capital projects, fiscal years {a} to {b}", "Mejoras capitales, años fiscales {a} a {b}"),
    ("Approved budget per resident, FY{year}", "Presupuesto aprobado por residente, AF {year}"),
    ("Largest agencies, FY{year} approved", "Agencias más grandes, AF {year} aprobado"),
    ("The figures come from different sources and stages and are never added together: the budget is the Commonwealth's, federal obligations include money that also passes through the budget, and the capital program is a plan.",
     "Las cifras vienen de fuentes y etapas distintas y nunca se suman: el presupuesto es el del Gobierno de Puerto Rico, las obligaciones federales incluyen dinero que también pasa por el presupuesto y el programa de mejoras capitales es un plan."),
    ("Loading public school students…", "Cargando los estudiantes de escuelas públicas…"),
    ("Per public school student", "Por estudiante de escuela pública"),
    ("Department of Education, spent in FY{year}", "Departamento de Educación, gastado en el AF {year}"),
    ("Students in public schools, {a}-{b} school year", "Estudiantes en escuelas públicas, año escolar {a}-{b}"),
    ("Spent per student", "Gastado por estudiante"),
    ("An estimate by municipio", "Un estimado por municipio"),
    ("An estimate, not spending reported by municipio: the Department of Education's FY{year} spending split by each municipio's share of the public school students. It is never added into any total.",
     "Un estimado, no gasto informado por municipio: el gasto del Departamento de Educación en el AF {year} repartido según la proporción de estudiantes de escuelas públicas de cada municipio. Nunca se suma a ningún total."),
    ("Students", "Estudiantes"), ("Estimated dollars", "Dólares estimados"),
    ("Data built {date}.", "Datos preparados el {date}."),
    ("Data built {date}: older than two update cycles, a newer release may exist.", "Datos preparados el {date}: tienen más de dos ciclos de actualización; puede haber una publicación más reciente."),
    ("{fn}: proposed, approved and spent by fiscal year", "{fn}: propuesto, aprobado y gastado por año fiscal"),
    ("The whole budget: proposed, approved and spent by fiscal year", "Todo el presupuesto: propuesto, aprobado y gastado por año fiscal"),
    ("Columns: proposed, approved and spent in each fiscal year. The table below has the figures.",
     "Columnas: propuesto, aprobado y gastado en cada año fiscal. La tabla de abajo tiene las cifras."),
    ("Fiscal year", "Año fiscal"), ("FY{year}", "AF {year}"),
    ("{col}: from the fund to the function", "{col}: del fondo a la función"),
    ("Bands: each fund of the budget chosen above, split by the function it pays for. The table of section 2 has the funds of every budget.",
     "Bandas: cada fondo del presupuesto elegido arriba, dividido por la función que paga. La tabla de la sección 2 tiene los fondos de cada presupuesto."),
    ("Billions of dollars obligated in each federal fiscal year, not adjusted for inflation; the darker column is the year chosen. Years before 2017 are less complete: agencies reported less to USAspending before the DATA Act.",
     "Miles de millones de dólares obligados en cada año fiscal federal, sin ajustar por inflación; la columna más oscura es el año elegido. Los años antes de 2017 están menos completos: las agencias informaban menos a USAspending antes de la ley DATA."),
    # section 5's paid-out card (public_spending_outlays.js; decision 96, step 2)
    ("Grants and contracts", "Subvenciones y contratos"), ("Signed in", "Firmado en"), ("Share paid out", "Proporción desembolsada"),
    ("Signed in federal fiscal years {a} to {b}: {paid} paid out of {obligated} obligated ({share})",
     "Firmado en los años fiscales federales {a} a {b}: {paid} desembolsados de {obligated} obligados ({share})"),
    ("Bars: obligated and paid out by function. The table below has the figures.", "Barras: obligado y desembolsado por función. La tabla de abajo tiene las cifras."),
    ("Columns: share paid out by the federal fiscal year the awards were signed. The table below has the figures.", "Columnas: proporción desembolsada según el año fiscal federal en que se firmaron las adjudicaciones. La tabla de abajo tiene las cifras."),
    ("{fn}: {paid} paid out of {obligated} obligated ({share})", "{fn}: {paid} desembolsados de {obligated} obligados ({share})"),
    ("{over} awards report more paid out than obligated ({excess} in all); each counts here up to its obligated amount. {none} awards report no outlay yet; about a third of the contracts report none, so their share is understated. FEMA Public Assistance is left out ({pa} obligated in these awards): USAspending does not follow its projects.",
     "{over} adjudicaciones informan más desembolsado que obligado ({excess} en total); cada una cuenta aquí hasta su monto obligado. {none} adjudicaciones todavía no informan desembolsos; cerca de un tercio de los contratos no informa ninguno, por lo que su proporción está subestimada. Se excluye la Asistencia Pública de FEMA ({pa} obligados en estas adjudicaciones): USAspending no sigue sus proyectos."),
    # section 8, FEMA Public Assistance by stage and age (public_spending_fema.js; decision 109, step 2)
    ("Obligated, all projects", "Obligado, todos los proyectos"),
    ("Closed out", "Cerrado"),
    ("Open", "Abierto"),
    ("Pending a review", "Pendiente de una revisión"),
    ("{n} projects", "{n} proyectos"),
    ("Bar: obligated by stage. The tiles above have the figures.", "Barra: obligado por etapa. Los recuadros de arriba tienen las cifras."),
    ("{sw} of the {tot} ({share}) is recorded as Statewide: those projects name no municipio and are not on the map.", "{sw} de los {tot} ({share}) está registrado como Statewide: esos proyectos no nombran un municipio y no están en el mapa."),
    ("Under 2 years", "Menos de 2 años"),
    ("2 to 5 years", "De 2 a 5 años"),
    ("5 to 8 years", "De 5 a 8 años"),
    ("8 years or more", "8 años o más"),
    ("Median age of the money still open, weighted by dollars: {age} years since its first obligation.", "Mediana de antigüedad del dinero todavía abierto, ponderada por dólares: {age} años desde su primera obligación."),
    ("Hurricane María", "Huracán María"),
    ("Hurricane Irma", "Huracán Irma"),
    ("Hurricane Fiona", "Huracán Fiona"),
    ("Earthquakes of 2020", "Terremotos de 2020"),
    ("COVID-19", "COVID-19"),
    ("{type}, {year}", "{type}, {year}"),
    ("Hurricane", "Huracán"),
    ("Earthquake", "Terremoto"),
    ("Tropical Storm", "Tormenta tropical"),
    ("Severe Storm", "Tormenta severa"),
    ("Flood", "Inundación"),
    ("Biological", "Biológico"),
    ("Fire", "Incendio"),
    ("Coastal Storm", "Tormenta costera"),
    ("Disaster", "Desastre"),
    ("Median age of what is open", "Mediana de antigüedad de lo abierto"),
    ("{age} years", "{age} años"),
    ("Damage category", "Categoría de daño"),
    ("Debris removal", "Remoción de escombros"),
    ("Emergency protective measures", "Medidas de protección de emergencia"),
    ("Roads and bridges", "Carreteras y puentes"),
    ("Water control facilities", "Instalaciones de control de agua"),
    ("Public buildings and contents", "Edificios públicos y su contenido"),
    ("Public utilities", "Utilidades públicas"),
    ("Parks, recreation and other", "Parques, recreación y otros"),
    ("Management costs", "Costos de administración"),
    ("Map: FEMA Public Assistance by municipio, the projects that name one. The table below has the figures.", "Mapa: Asistencia Pública de FEMA por municipio, los proyectos que nombran uno. La tabla de abajo tiene las cifras."),
    ("none", "ninguno"),
    ("Most dollars open more than five years, per resident", "Más dólares abiertos hace más de cinco años, por residente"),
    ("Lowest share closed out", "Menor proporción cerrada"),
    ("Oldest money still open", "Dinero abierto más antiguo"),
    ("Open more than 5 years", "Abierto hace más de 5 años"),
    # section 7, the prime grants obligated and paid out (public_spending_recovery.js; decision 109, step 3)
    ("Recovery, hurricanes Irma and María", "Recuperación, huracanes Irma y María"),
    ("Mitigation", "Mitigación"),
    ("Electrical grid", "Red eléctrica"),
    ("Recovery, Hurricane Fiona", "Recuperación, huracán Fiona"),
    ("Recovery, 2020 earthquakes", "Recuperación, terremotos de 2020"),
    ("Recovery, other disasters", "Recuperación, otros desastres"),
    ("Recovery, 2008 floods", "Recuperación, inundaciones de 2008"),
    ("Bars: each prime grant, obligated and paid out. The figures are beside each bar.", "Barras: cada subvención principal, obligado y desembolsado. Las cifras están junto a cada barra."),
    ("{paid} of {obligated}", "{paid} de {obligated}"),
    ("All grants: {paid} paid out of {obligated} obligated ({share}), read on {date}", "Todas las subvenciones: {paid} desembolsados de {obligated} obligados ({share}), leído el {date}"),
    # Method, where each line's function comes from (public_spending_charts.js; decision 109, step 4)
    ("Budget", "Presupuesto"),
    ("Object of expense", "Objeto de gasto"),
    ("Concept (debt, pensions)", "Concepto (deuda, pensiones)"),
    ("Agency's general function", "Función general de la agencia"),
    ("Bars: share of each budget by where its function comes from. The table has the figures.", "Barras: proporción de cada presupuesto según de dónde viene su función. La tabla tiene las cifras."),
    ("The largest agencies classified only by their general function, FY{year} approved", "Las agencias más grandes clasificadas solo por su función general, AF {year} aprobado"),
    ("Agencies whose money is split across functions (debt and pensions aside), FY{year} approved: {n}", "Agencias cuyo dinero se reparte entre funciones (aparte de deuda y pensiones), AF {year} aprobado: {n}"),
    ("{n} functions", "{n} funciones"),
    # section 1, by agency and fund (public_spending_agencies.js, on first use; decision 112, step 2)
    ("Reported spent", "Gastado informado"),
    ("Difference", "Diferencia"),
    ("Concept of expense", "Concepto de gasto"),
    ("{fund}, fiscal year {year}: {approved} approved and {spent} reported as spent ({share}). {n} agencies reported less than their approved budget, {under} together; {m} reported more, {over} together.",
     "{fund}, año fiscal {year}: {approved} aprobados y {spent} informados como gastados ({share}). {n} agencias informaron menos que su presupuesto aprobado, {under} en conjunto; {m} informaron más, {over} en conjunto."),
    ("Read with care: federal money is often awarded for several years, above all for disaster recovery, so a year with less spent than approved is expected. The difference does not say the money went unused.",
     "Lea con cuidado: el dinero federal muchas veces se adjudica para varios años, sobre todo el de recuperación por desastres, así que es de esperar un año con menos gastado que aprobado. La diferencia no dice que el dinero se quedó sin usar."),
    ("Read with care: special funds are fees and other revenue set aside by law. When less comes in than was budgeted, less can be spent. The difference does not say the money was available.",
     "Lea con cuidado: los fondos especiales son derechos y otros ingresos separados por ley. Cuando entra menos de lo presupuestado, se puede gastar menos. La diferencia no dice que el dinero estaba disponible."),
    ("Read with care: the difference does not say why. It can come from reserves held back, payments made after June 30 or changes to the budget during the year, which the data sheets do not record.",
     "Lea con cuidado: la diferencia no dice por qué. Puede deberse a reservas retenidas, pagos hechos después del 30 de junio o cambios al presupuesto durante el año, que las hojas de datos no registran."),
    ("{fund}, fiscal year {year}: the {k} agencies with the largest difference between approved and reported spent", "{fund}, año fiscal {year}: las {k} agencias con la mayor diferencia entre lo aprobado y lo informado como gastado"),
    ("See all {n} agencies that reported less than approved", "Ver las {n} agencias que informaron menos que lo aprobado"),
    ("{fund}, fiscal year {year}: every agency that reported less than approved", "{fund}, año fiscal {year}: todas las agencias que informaron menos que lo aprobado"),
    ("See the {n} agencies that reported more than approved", "Ver las {n} agencias que informaron más que lo aprobado"),
    ("{fund}, fiscal year {year}: agencies that reported more than approved", "{fund}, año fiscal {year}: agencias que informaron más que lo aprobado"),
    ("An agency can report more than its approved budget when money is moved to it during the year: the data sheets give the budget as approved, not as amended.",
     "Una agencia puede informar más que su presupuesto aprobado cuando se le transfiere dinero durante el año: las hojas de datos dan el presupuesto como se aprobó, no como se enmendó."),
    ("See the same by concept of expense", "Ver lo mismo por concepto de gasto"),
    ("{fund}, fiscal year {year}: approved and reported spent by concept of expense", "{fund}, año fiscal {year}: aprobado e informado como gastado por concepto de gasto"),
    ("* Two codes read as one: the data sheets approve the Police inside this body and report its spending under its own code.",
     "* Dos códigos leídos como uno: las hojas de datos aprueban la Policía dentro de esta entidad e informan su gasto bajo su propio código."),
    ("Reported spent is what each agency told the Office of Management and Budget during the next budget process, not the audited close.",
     "Lo informado como gastado es lo que cada agencia le dijo a la Oficina de Gerencia y Presupuesto durante el siguiente proceso presupuestario, no el cierre auditado."),
    ("What happens to money not spent: in the General Fund, an agency cannot use money of an earlier fiscal year unless the certified budget says so (Manual of the Budget Process of OGP). The data sheets do not show what was done with each difference.",
     "Qué pasa con el dinero no gastado: en el Fondo General, una agencia no puede usar dinero de un año fiscal anterior a menos que el presupuesto certificado lo disponga (Manual del Proceso Presupuestario de la OGP). Las hojas de datos no muestran qué se hizo con cada diferencia."),
    ("What happens to money not spent: in special revenue funds, the income of earlier fiscal years can be used, under the rules that apply to each fund (Manual of the Budget Process of OGP). The data sheets do not show what was done with each difference.",
     "Qué pasa con el dinero no gastado: en los fondos de ingresos especiales, los ingresos de años fiscales anteriores se pueden usar, según las reglas que apliquen a cada fondo (Manual del Proceso Presupuestario de la OGP). Las hojas de datos no muestran qué se hizo con cada diferencia."),
    ("What happens to money not spent: federal money follows the rules and the period of each federal grant, not the fiscal year of the Commonwealth. The data sheets do not show what was done with each difference.",
     "Qué pasa con el dinero no gastado: el dinero federal sigue las reglas y el período de cada subvención federal, no el año fiscal del Gobierno de Puerto Rico. Las hojas de datos no muestran qué se hizo con cada diferencia."),
    # section 9, My municipio (public_spending_municipio.js, on first use; decision 109, step 5)
    ("Money in its territory", "Dinero en su territorio"),
    ("Who runs it", "Quién lo administra"),
    ("Capital plan, fiscal years {a} to {b} (planned)", "Plan de mejoras capitales, años fiscales {a} a {b} (planificado)"),
    ("Disaster recovery subawards, federal fiscal years {a} to {b} (obligated)", "Subadjudicaciones de recuperación por desastres, años fiscales federales {a} a {b} (obligado)"),
    ("The Department of Housing, which passed them to municipalities, contractors and nonprofits", "El Departamento de la Vivienda, que las entregó a municipios, contratistas y organizaciones sin fines de lucro"),
    ("FEMA Public Assistance, projects that name the municipio (obligated)", "Asistencia Pública de FEMA, proyectos que nombran el municipio (obligado)"),
    ("The applicant of each project (the municipio, Commonwealth agencies or nonprofits), with FEMA and COR3", "El solicitante de cada proyecto (el municipio, agencias del Gobierno u organizaciones sin fines de lucro), con FEMA y COR3"),
    ("Federal awards of every type, federal fiscal year {y} (obligated)", "Adjudicaciones federales de todo tipo, año fiscal federal {y} (obligado)"),
    ("Federal agencies, paying benefits, grants and contracts to people and organizations in the municipio", "Agencias federales, que pagan beneficios, subvenciones y contratos a personas y organizaciones en el municipio"),
    ("The four questions", "Las cuatro preguntas"),
    ("1. How much recovery money is obligated?", "1. ¿Cuánto dinero de recuperación está obligado?"),
    ("{total}: {sub} in disaster recovery subawards and {fema} in FEMA projects that name the municipio. The {sw} of FEMA money recorded as Statewide names no municipio, so this is only part of it.", "{total}: {sub} en subadjudicaciones de recuperación por desastres y {fema} en proyectos de FEMA que nombran el municipio. El {sw} del dinero de FEMA registrado como Statewide no nombra un municipio, por lo que esto es solo una parte."),
    ("2. How much has been paid?", "2. ¿Cuánto se ha pagado?"),
    ("Not published by municipio: USAspending reports no payments on subawards and OpenFEMA none on projects. Island-wide payments are in sections 5 and 7.", "No se publica por municipio: USAspending no informa pagos de las subadjudicaciones y OpenFEMA no los informa por proyecto. Los pagos de toda la isla están en las secciones 5 y 7."),
    ("3. How long has it been pending?", "3. ¿Cuánto tiempo lleva pendiente?"),
    ("No open FEMA project names the municipio.", "Ningún proyecto abierto de FEMA nombra el municipio."),
    ("FEMA money still open has a median age of {age} years since its first obligation; {over5} has been open more than five years.", "El dinero de FEMA todavía abierto tiene una mediana de antigüedad de {age} años desde su primera obligación; {over5} lleva abierto más de cinco años."),
    ("4. What do we know of the progress?", "4. ¿Qué sabemos del avance?"),
    ("{share} of the FEMA dollars that name the municipio are in projects closed out. No open source reports the physical progress of the works.", "El {share} de los dólares de FEMA que nombran el municipio está en proyectos cerrados. Ninguna fuente abierta informa el avance físico de las obras."),
    ("What could be requested to evaluate execution", "Qué se podría pedir para evaluar la ejecución"),
    ("From the municipio: its FEMA projects, their status and the documents still pending.", "Al municipio: sus proyectos de FEMA, su estado y los documentos todavía pendientes."),
    ("From COR3: the project worksheets and reimbursement requests of the projects in the municipio.", "A COR3: las hojas de trabajo y las solicitudes de reembolso de los proyectos en el municipio."),
    ("From the Department of Housing: the disaster recovery activities and draws in the municipio (its quarterly performance reports).", "Al Departamento de la Vivienda: las actividades de recuperación por desastres y los giros en el municipio (sus informes trimestrales de desempeño)."),
    ("From the agencies of the capital plan: the status of their projects in the municipio.", "A las agencias del plan de mejoras capitales: el estado de sus proyectos en el municipio."),
    ("The municipal government's own finances: {name} on ABRE Tu Municipio", "Las finanzas del propio gobierno municipal: {name} en ABRE Tu Municipio"),
    ("* Grants made before fiscal year 2020: USAspending has payments only from 2020, so the share paid out is understated. Do not compare these grants with the later ones.",
     "* Subvenciones otorgadas antes del año fiscal 2020: USAspending tiene pagos solo desde 2020, así que la parte desembolsada está subestimada. No compare estas subvenciones con las posteriores."),
    ("The municipal government's own audits", "Las auditorías del propio gobierno municipal"),
    ("Single audits filed for {a} to {b}", "Auditorías únicas radicadas de {a} a {b}"),
    ("{k} of {n}", "{k} de {n}"),
    ("Findings on federal programs in those audits", "Hallazgos sobre programas federales en esas auditorías"),
    ("Findings repeated from the audit before", "Hallazgos repetidos de la auditoría anterior"),
    ("A finding is not a loss: it says a rule was not followed or a control was weak. These are the audits of the municipal government only, not of other bodies in the municipio.",
     "Un hallazgo no es una pérdida: dice que no se siguió una regla o que un control era débil. Son las auditorías del gobierno municipal solamente, no de otras entidades del municipio."),
    ("Audit findings that repeat, in all of Puerto Rico", "Hallazgos de auditoría que se repiten, en todo Puerto Rico"),
    # section 3, a concept opened (public_spending_charts.js concept)
    ("Salaries, wages and the employer's share of benefits of public employees.", "Sueldos, salarios y la aportación patronal a los beneficios de los empleados públicos."),
    ("Services the agencies buy from others, such as professional contracts, rents and utilities.", "Servicios que las agencias compran a otros, como contratos profesionales, rentas y utilidades."),
    ("Money the government passes to people or to other entities, such as the government health plan's payments, nutrition assistance and contributions to other entities.", "Dinero que el gobierno entrega a personas o a otras entidades, como los pagos del plan de salud del gobierno, la asistencia nutricional y las aportaciones a otras entidades."),
    ("Construction, equipment and other long-lived assets.", "Construcción, equipo y otros activos de larga duración."),
    ("Principal and interest on public debt, whatever agency pays them.", "Principal e intereses de la deuda pública, sin importar qué agencia los pague."),
    ("Lines whose concept is none of the above, such as lump-sum appropriations whose purpose the budget does not detail.", "Líneas cuyo concepto no es ninguno de los anteriores, como asignaciones globales cuyo propósito el presupuesto no detalla."),
    ("By function", "Por función"),
    ("Largest agencies", "Agencias más grandes"),
]


def build():
    d = json.loads(DATA.read_text(encoding="utf-8"))
    col = {(c["year"], c["stage"]): c for c in d["columns"]}
    ap27, sp25, ap25 = col[(2027, "approved")]["total"], col[(2025, "actual")]["total"], col[(2025, "approved")]["total"]
    ci27 = d["columns"].index(col[(2027, "approved")])
    other27 = round(100 * sum(r[4][ci27] for r in d["rows"] if d["functions"][r[3]] == "other") / ap27)
    # decision 112, step 3: the notes on names and lines that readers confuse, from the newest approved budget
    def ag27(code, concept=None, fund=None):
        return sum(r[4][ci27] for r in d["rows"] if r[0] == code and (concept is None or d["concepts"][r[2]] == concept) and (fund is None or d["funds"][r[1]] == fund))
    for code, word in (("025", "Custodia de Hacienda"), ("017", "Custodia de la Oficina de Gerencia"), ("024", "Departamento de Hacienda"), ("078", "Departamento de la Vivienda"), ("106", "Vivienda P")):
        assert word in d["agencies"][code], (code, d["agencies"][code])
    debt27 = sum(r[4][ci27] for r in d["rows"] if d["concepts"][r[2]] == "debt_service")
    debt_cust = round(100 * ag27("025", "debt_service") / debt27)
    viv_fed = round(100 * ag27("078", fund="federal") / ag27("078"))
    years = d["years"]
    pica = json.loads((ROOT / "site" / "data" / "spending_pica.json").read_text(encoding="utf-8"))
    fema = json.loads((ROOT / "site" / "data" / "spending_fema_pa.json").read_text(encoding="utf-8"))
    f_closed_n, f_all_n = fema["island"]["count"][fema["stages"].index("closed")], sum(fema["island"]["count"])
    f_closed_usd = round(100 * fema["island"]["usd"][fema["stages"].index("closed")] / sum(fema["island"]["usd"]))
    f_closed_cnt = round(100 * f_closed_n / f_all_n)
    by_basis = d["basis"]["by_column"][d["basis"]["column"]]
    agency_share = round(100 * by_basis[d["basis"]["kinds"].index("agency")] / sum(by_basis))
    fema_n, fema_tot = sum(fema["island"]["count"]), sum(fema["island"]["usd"])
    pica_placed = round(100 * pica["placed_usd"] / pica["total_usd"])
    fed = json.loads((ROOT / "site" / "data" / "spending_federal.json").read_text(encoding="utf-8"))
    contract = json.loads((ROOT / "dictionary_src" / "datasets.json").read_text(encoding="utf-8"))
    CYCLE = {"daily": 1, "weekly": 7, "monthly": 31, "quarterly": 92, "annual": 365}
    cycle = {d["file"]: CYCLE.get(d.get("cadence"), 365) for d in (contract if isinstance(contract, list) else contract["datasets"]) if d.get("file", "").startswith("spending_")}
    age = lambda f: f'<p class="ps-age" data-age="{f}" data-cycle="{cycle[f]}" aria-live="polite"></p>'
    fy = fed["years"][-1]
    spent_y = max(y for (y, st) in col if st == "actual" and (y, "approved") in col)   # the "Spent" line of section 6 (js/public_spending_sectors.js: the latest year with both)
    cap_a, cap_b = pica["years"][0], pica["years"][-1]   # its capital-projects line: a total of the four-year program
    assert col[(2025, "approved")]["sheet"] != col[(2025, "actual")]["sheet"], "the FY2025 gap note says the two figures come from two data sheets"
    gap25 = ap25 - sp25
    fyi = len(fed["years"]) - 1
    fed_tot = sum(fed["totals"][g][fyi] for g in fed["groups"])
    fed_dp = round(100 * fed["totals"]["direct_payments"][fyi] / fed_tot)
    fed_peak_i = max(range(len(fed["years"])), key=lambda i: sum(fed["totals"][g][i] for g in fed["groups"]))
    fed_peak = sum(fed["totals"][g][fed_peak_i] for g in fed["groups"])
    for en, es in JS:
        t(en, es)
    T = t
    TB = tb
    page = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{T("Knowledge Area · Budget and public spending", "Área de conocimiento · Presupuesto y gasto público")}</title>
<meta name="description" content="{T("The Government of Puerto Rico's budget by function, agency, fund and what the money pays for: what was approved, proposed and spent, from the Office of Management and Budget's data sheets.", "El presupuesto del Gobierno de Puerto Rico por función, agencia, fondo y lo que paga el dinero: lo aprobado, lo propuesto y lo gastado, según las hojas de datos de la Oficina de Gerencia y Presupuesto.")}">
<meta name="theme-color" content="#FFFFFF">
<link rel="icon" href="img/fpr-mark.png">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Material+Symbols+Rounded:opsz,wght,FILL,GRAD@24,400,1,0&icon_names=account_balance,arrow_back,bar_chart,bolt,chat_bubble,close,commute,compare_arrows,delete,diversity_3,download,home_work,hourglass_bottom,info,lightbulb,location_city,map,menu_book,payments,pie_chart,price_change,rocket_launch,route,school,send,table_view,thermostat,view_in_ar,warning,water,wifi,woman,work&display=block">
<link rel="stylesheet" href="css/twin.css?v=62">
<link rel="stylesheet" href="css/housing.css?v=21">
<link rel="stylesheet" href="css/public_spending.css?v=15">
<link rel="stylesheet" href="css/chat.css?v=4">
<script src="js/i18n.js?v=65" data-page="publicspending"></script>
</head>
<body class="research">
<a class="skip" href="#budget">{T("Skip to the content", "Saltar al contenido")}</a>
<header class="topbar">
  <a class="logo" href="index.html" title="{T("PR Data Observatory home", "Inicio del Observatorio de Datos de PR")}"><img src="img/fpr-logo.png" alt="{T("Foundation for Puerto Rico. PR Data Observatory home", "Foundation for Puerto Rico. Inicio del Observatorio de Datos de PR")}"></a>
  <div class="brand"><b>{T("Knowledge Area · Budget and public spending", "Área de conocimiento · Presupuesto y gasto público")}</b><span>{T("The Government of Puerto Rico's budget: approved, proposed and spent", "El presupuesto del Gobierno de Puerto Rico: aprobado, propuesto y gastado")}</span></div>
  <div class="spacer"></div>
  <nav class="views" aria-label="{T("Views", "Vistas")}">
    <a class="btn" href="index.html"><span class="ms-icon" aria-hidden="true">map</span><span class="lbl">{T("Map", "Mapa")}</span></a>
    <a class="btn" href="3d.html" title="{T("Immersive 3D + time view", "Vista inmersiva en 3D + tiempo")}"><span class="ms-icon" aria-hidden="true">view_in_ar</span><span class="lbl">{T("3D + Time", "3D + Tiempo")}</span></a>
    <a class="btn" href="knowledge.html" aria-current="page" title="{T("Knowledge: FPR studies, analyses and tools", "Conocimiento: estudios, análisis y herramientas de FPR")}"><span class="ms-icon" aria-hidden="true">lightbulb</span><span class="lbl">{T("Knowledge", "Conocimiento")}</span></a>
    <a class="btn" href="dictionary.html" title="{T("Data dictionary: meanings, sources, licenses, how to cite", "Diccionario de datos: significados, fuentes, licencias, cómo citar")}"><span class="ms-icon" aria-hidden="true">menu_book</span><span class="lbl">{T("Data dictionary", "Diccionario de datos")}</span></a>
    <a class="btn" href="learn.html" title="{T("Learn: short lessons about maps and spatial analysis", "Aprende: lecciones cortas sobre mapas y análisis espacial")}"><span class="ms-icon" aria-hidden="true">school</span><span class="lbl">{T("Learn", "Aprende")}</span></a>
  </nav>
</header>

<nav class="toc" id="toc" aria-label="{T("On this page", "En esta página")}">
  <span class="ka-tabs" role="group" aria-label="{T("Knowledge Area", "Área de conocimiento")}" data-ka="publicspending"></span><span class="ka-sep" aria-hidden="true"></span>
  <a href="#budget">{T("The budget", "El presupuesto")}</a><a href="#gap">{T("Approved and spent", "Aprobado y gastado")}</a><a href="#funds">{T("Where the money comes from", "De dónde viene el dinero")}</a><a href="#concepts">{T("What it pays for", "Qué paga")}</a><a href="#capital">{T("Capital projects", "Mejoras capitales")}</a><a href="#federal">{T("Federal money", "Fondos federales")}</a><a href="#sector">{T("By sector", "Por sector")}</a><a href="#recovery">{T("Disaster recovery", "Recuperación por desastres")}</a><a href="#fema">{T("FEMA projects", "Proyectos de FEMA")}</a><a href="#municipio">{T("My municipio", "Mi municipio")}</a><a href="#method">{T("Method", "Método")}</a><a href="#sources">{T("Sources", "Fuentes")}</a>
</nav>

<main class="page">
  <div class="note caution review-note" role="note" data-ka-note></div>

  <section class="hero" id="budget">
    <div class="eyebrow">{T("Knowledge Area · Public money", "Área de conocimiento · Dinero público")}</div>
    <h1>{T("Budget and public spending", "Presupuesto y gasto público")}</h1>
    <p class="lede">{T(f"What the government's agencies were approved to spend, were proposed to spend and spent, by function and by agency. The approved budget for fiscal year {years[-1]} (July {years[-1] - 1} to June {years[-1]}) is ${bn(ap27)} billion. These are the agencies in the fiscal plan: public corporations with their own budgets, such as the electric and water utilities, and the municipal governments' own budgets are not included (ABRE Tu Municipio covers municipal finances), and no figure is placed in a municipio, because the budget names none.",
                      f"Lo que las agencias del gobierno tenían aprobado gastar, lo que se propuso que gastaran y lo que gastaron, por función y por agencia. El presupuesto aprobado del año fiscal {years[-1]} (julio de {years[-1] - 1} a junio de {years[-1]}) es de ${bn(ap27)} mil millones. Son las agencias del plan fiscal: no se incluyen las corporaciones públicas con presupuesto propio, como las de energía eléctrica y de agua, ni los presupuestos propios de los gobiernos municipales (ABRE Tu Municipio cubre las finanzas municipales), y ninguna cifra se ubica en un municipio, porque el presupuesto no nombra ninguno.")} <a href="https://www.abretumunicipio.org/" target="_blank" rel="noopener">{T("ABRE Tu Municipio", "ABRE Tu Municipio")}</a></p>
    <p class="ps-p"><a href="money-cycle.html">{T("How public money moves: the stages behind these figures", "Cómo se mueve el dinero público: las etapas detrás de estas cifras")}</a></p>
    <p class="ps-stage" data-t-wait>{TB("Stage and basis.", "Etapa y base.", "Proposed and approved are OGP's budgets; spent is what the agencies reported to OGP in the next budget process, not the audited close. Each fiscal year runs from July to June.",
        "Lo propuesto y lo aprobado son los presupuestos de la OGP; lo gastado es lo que las agencias informaron a la OGP en el proceso presupuestario siguiente, no el cierre auditado. Cada año fiscal va de julio a junio.")}</p>
    <div class="ps-controls">
      <label>{T("Budget", "Presupuesto")} <select id="psCol"></select></label>
      <button type="button" class="btn" id="psCsv"><span class="ms-icon" aria-hidden="true">download</span>{T("Download CSV", "Descargar CSV")}</button>
    </div>
    <div class="ps-tiles" id="psTiles" aria-live="polite"></div>
    {age("spending_state.json")}
    <div class="card ps-chart">
      <div class="ps-head"><button type="button" class="btn" id="psBack" hidden><span class="ms-icon" aria-hidden="true">arrow_back</span>{T("All functions", "Todas las funciones")}</button><span id="psTreeHead" aria-live="polite"></span></div>
      <div id="psTree"></div>
      <details class="ps-more"><summary>{T("See the figures as a table", "Ver las cifras en una tabla")}</summary><div class="ps-tablebox" id="psTable"></div></details>
    </div>
    <p class="ps-small">{T(f"Each rectangle's area is its share of the budget chosen. The function of each budget line is assigned by a crosswalk reviewed on 9 November 2026. In the approved budget for fiscal year {years[-1]}, {other27}% of the money is “Other”, mostly the lottery, the Gaming Commission and lines of the custodial accounts that mix several purposes; for fiscal years 2023 and 2024, whose custodial lines use other codes, the share is larger.",
                           f"El área de cada rectángulo es su proporción del presupuesto elegido. La función de cada línea del presupuesto se asigna con una tabla de equivalencias revisada el 9 de noviembre de 2026. En el presupuesto aprobado del año fiscal {years[-1]}, el {other27} % del dinero es «Otros», sobre todo la lotería, la Comisión de Juegos y líneas de las cuentas de custodia que mezclan varios propósitos; en los años fiscales 2023 y 2024, cuyas líneas de custodia usan otros códigos, la proporción es mayor.")}</p>
    <div class="note caution">{TB("Functions are approximate.", "Las funciones son aproximadas.", f"About {agency_share}% of this budget takes the general function of its agency, not of its own program, because the data sheets do not say more. A function's total is a guide, not an exact figure; the Method section shows which agencies this affects most.",
        f"Cerca del {agency_share} % de este presupuesto toma la función general de su agencia, no la de su propio programa, porque las hojas de datos no dicen más. El total de una función es una guía, no una cifra exacta; la sección Método muestra a qué agencias afecta más.")}</div>
    <div class="note" data-t-wait>{TB("Names that are easy to confuse.", "Nombres que se confunden.", f"The appropriations under the custody of Hacienda (${bn(ag27('025'))} billion) are not the Treasury Department's own budget, which is a separate line (${bn(ag27('024'))} billion): they are money it holds for the whole government, mostly transfers (${bn(ag27('025', 'transfers'))} billion) and debt service (${bn(ag27('025', 'debt_service'))} billion). The appropriations under the custody of the Office of Management and Budget (${bn(ag27('017'))} billion) are apart from that office's own budget in the same way. The Department of Housing (${bn(ag27('078'))} billion, {viv_fed}% of it federal funds) and the Public Housing Administration (${bn(ag27('106'))} billion) are two bodies: the second is attached to the first and runs the public housing projects. Figures: approved budget, fiscal year {years[-1]}.",
        f"Las asignaciones bajo la custodia de Hacienda (${bn(ag27('025'))} mil millones) no son el presupuesto propio del Departamento de Hacienda, que es una línea aparte (${bn(ag27('024'))} mil millones): son dinero que guarda para todo el gobierno, sobre todo transferencias (${bn(ag27('025', 'transfers'))} mil millones) y servicio de la deuda (${bn(ag27('025', 'debt_service'))} mil millones). Las asignaciones bajo la custodia de la Oficina de Gerencia y Presupuesto (${bn(ag27('017'))} mil millones) están aparte del presupuesto propio de esa oficina de la misma manera. El Departamento de la Vivienda (${bn(ag27('078'))} mil millones, {viv_fed} % en fondos federales) y la Administración de Vivienda Pública (${bn(ag27('106'))} mil millones) son dos entidades: la segunda está adscrita a la primera y administra los residenciales públicos. Cifras: presupuesto aprobado, año fiscal {years[-1]}.")}</div>
  </section>

  <section class="block" id="gap">
    <h2><span class="ms-icon" aria-hidden="true">compare_arrows</span>{T("1 · Approved and spent", "1 · Aprobado y gastado")}</h2>
    <p class="ps-p">{T(f"For fiscal year 2025 the data sheets give both the approved budget and what was spent: ${bn(sp25)} billion spent of ${bn(ap25)} billion approved. Spent is what the agencies reported during the next budget process; the official close is the Treasury Department's financial statements.",
                      f"Para el año fiscal 2025 las hojas de datos de la OGP dan tanto el presupuesto aprobado como lo gastado: ${bn(sp25)} mil millones gastados de ${bn(ap25)} mil millones aprobados. Lo gastado es lo que las agencias informaron durante el proceso presupuestario siguiente; el cierre oficial son los estados financieros del Departamento de Hacienda.")}</p>
    <div class="note" data-t-wait>{TB("What the difference can mean.", "Lo que puede significar la diferencia.", f"The ${bn(gap25)} billion between approved and spent in fiscal year 2025 can come from reserves held back, payments scheduled after June 30, legal restrictions on some funds, accounting differences or later amendments to the budget; the two figures also come from two different OGP data sheets. The difference alone does not show inefficiency or a lack of capacity. The audited close is the Treasury Department's Basic Financial Statements, prepared on another accounting basis; the latest found as of November 2026 is for fiscal year 2023.",
        f"Los ${bn(gap25)} mil millones entre lo aprobado y lo gastado en el año fiscal 2025 pueden deberse a reservas retenidas, pagos programados después del 30 de junio, restricciones legales sobre algunos fondos, diferencias contables o enmiendas posteriores al presupuesto; además, las dos cifras vienen de dos hojas de datos distintas de la OGP. La diferencia por sí sola no demuestra ineficiencia ni falta de capacidad. El cierre auditado son los Estados Financieros Básicos del Departamento de Hacienda, preparados con otra base contable; el más reciente encontrado a noviembre de 2026 es el del año fiscal 2023.")}</div>
    <p class="ps-stage" data-t-wait>{TB("Stage and basis.", "Etapa y base.", "Approved, from OGP's approved budget; spent, the “Gastado” column of OGP's data sheets, which is what each agency reported. Neither is audited, and this page reads no figure from the Treasury Department (Hacienda).",
        "Aprobado, según el presupuesto aprobado de la OGP; gastado, la columna «Gastado» de las hojas de datos de la OGP, que es lo que cada agencia informó. Ninguno es auditado, y esta página no lee ninguna cifra del Departamento de Hacienda.")}</p>
    <div class="card ps-chart"><div id="psGap"></div>
      <div class="ps-legend"><div><i class="dot" aria-hidden="true"></i><span>{T("Approved", "Aprobado")}</span></div><div><i class="dot f" aria-hidden="true"></i><span>{T("Spent", "Gastado")}</span></div></div>
      <p class="ps-small" id="psGapNote" aria-live="polite"></p>
      <details class="ps-more"><summary>{T("See the figures as a table", "Ver las cifras en una tabla")}</summary><div class="ps-tablebox" id="psGapTable"></div></details>
    </div>
    <h3>{T("By agency and fund", "Por agencia y fondo")}</h3>
    <p class="ps-p">{T("Choose a fund to see, agency by agency, what was approved and what was reported as spent. The funds are never mixed, because each follows its own rules.", "Escoja un fondo para ver, agencia por agencia, lo aprobado y lo informado como gastado. Los fondos nunca se mezclan, porque cada uno sigue sus propias reglas.")}</p>
    <div class="ps-controls"><label>{T("Fund", "Fondo")} <select id="psAgFund"><option value="">{T("Choose a fund", "Escoja un fondo")}</option></select></label></div>
    <div id="psAgencies" aria-live="polite"></div>
    <p class="ps-p" data-t-wait>{T("Each budget goes through stages: the Governor sends a proposed budget to the Oversight Board, the Board approves it or sends it back, the Legislature evaluates and adopts it, the Governor signs it, the Board certifies the budget that follows the fiscal plan, and the agencies spend it. The Board has no column of its own, but it is in two of the three: in OGP's own words, the proposed budget is the one the Governor presents to the Board and the Legislature, the approved budget is the one the Board certified, and the spent budget is the one used during the fiscal year. A missing stage is a dot.",
                      "Cada presupuesto pasa por etapas: el Gobernador envía un presupuesto propuesto a la Junta de Supervisión Fiscal, la Junta lo aprueba o lo devuelve, la Asamblea Legislativa lo evalúa y lo adopta, el Gobernador lo firma, la Junta certifica el presupuesto que cumple con el plan fiscal, y las agencias lo gastan. La Junta no tiene una columna propia, pero está en dos de las tres: en palabras de la propia OGP, el presupuesto propuesto es el que el Gobernador presenta a la Junta y a la Asamblea Legislativa, el presupuesto aprobado es el que certificó la Junta, y el presupuesto gastado es el que se usó durante el año fiscal. Una etapa que falta es un punto.")}</p>
    <p class="ps-p" data-t-wait><a href="money-cycle.html#stages">{T("See every stage and who does what", "Vea todas las etapas y quién hace qué")}</a></p>
    <p class="ps-p" data-t-wait>{T("Select a function in the treemap above to see only that function here. The chart then stays on that function: “All functions”, here and above, brings the whole budget back.",
                      "Seleccione una función en el mapa de árbol de arriba para ver aquí solo esa función. El gráfico se queda entonces en esa función: «Todas las funciones», aquí y arriba, devuelve todo el presupuesto.")}</p>
    <div class="card ps-chart"><div class="ps-head"><button type="button" class="btn" id="psBack2" hidden><span class="ms-icon" aria-hidden="true">arrow_back</span>{T("All functions", "Todas las funciones")}</button><span id="psPipeHead" aria-live="polite"></span></div><div id="psPipe"></div><div class="ps-legend" id="psPipeKey"></div>
      <p class="ps-small" data-t-wait>{T("Where “spent” comes from: the “Gastado” column of OGP's data sheets, which is what each agency reported in the next budget process. It is not a figure of the Treasury Department (Hacienda) and it is not audited.",
                             "De dónde sale «gastado»: de la columna «Gastado» de las hojas de datos de la OGP, que es lo que cada agencia informó en el siguiente proceso presupuestario. No es una cifra del Departamento de Hacienda y no está auditada.")}</p>
      <details class="ps-more"><summary>{T("See the figures as a table", "Ver las cifras en una tabla")}</summary><div class="ps-tablebox" id="psPipeTable"></div></details>
    </div>
  </section>

  <section class="block" id="funds">
    <h2><span class="ms-icon" aria-hidden="true">payments</span>{T("2 · Where the money comes from", "2 · De dónde viene el dinero")}</h2>
    <p class="ps-p">{T("Every budget in the data sheets, by fund. The General Fund is mostly taxes. Federal funds are grants from the federal government that the agencies manage, such as the Nutrition Assistance Program and Medicaid; the same dollars also appear in USAspending as federal awards, so the two sources are never added together. Special funds are fees and other revenue set aside by law.",
                      "Cada presupuesto de las hojas de datos, por fondo. El Fondo General es sobre todo impuestos. Los fondos federales son subvenciones del gobierno federal que administran las agencias, como el Programa de Asistencia Nutricional y Medicaid; los mismos dólares aparecen también en USAspending como asignaciones federales, por lo que nunca se suman las dos fuentes. Los fondos especiales son cargos y otros ingresos asignados por ley.")}</p>
    <div class="card ps-chart"><div id="psFunds"></div><div class="ps-legend" id="psFundKey"></div>
      <details class="ps-more"><summary>{T("See the figures as a table", "Ver las cifras en una tabla")}</summary><div class="ps-tablebox" id="psFundTable"></div></details>
    </div>
    <p class="ps-p">{T("The budget chosen at the top of the page, from the fund the money comes from to the function it pays for. The width of each band is its dollars.",
                      "El presupuesto elegido al principio de la página, desde el fondo de donde viene el dinero hasta la función que paga. El ancho de cada banda es su cantidad de dólares.")}</p>
    <div class="card ps-chart"><div class="ps-head" id="psFlowHead" aria-live="polite"></div><div id="psFlow"></div><div class="ps-legend" id="psFlowKey"></div></div>
  </section>

  <section class="block" id="concepts">
    <h2><span class="ms-icon" aria-hidden="true">bar_chart</span>{T("3 · What the money pays for", "3 · Qué paga el dinero")}</h2>
    <p class="ps-p">{T("The budget chosen above, by concept of expense. Transfers include the government health plan's payments, nutrition assistance and contributions to other entities; debt service and pensions are counted here whatever agency pays them.",
                      "El presupuesto elegido arriba, por concepto de gasto. Las transferencias incluyen los pagos del plan de salud del gobierno, la asistencia nutricional y las aportaciones a otras entidades; el servicio de la deuda y las pensiones se cuentan aquí sin importar qué agencia los pague.")}</p>
    <p class="ps-small" data-t-wait>{T(f"Debt service is the payment of principal and interest on the government's debt: ${bn(debt27)} billion in the approved budget for fiscal year {years[-1]}, {debt_cust}% of it under the appropriations in Hacienda's custody. The Constitution of Puerto Rico (Article VI, section 8) orders that, when a year's resources do not cover its appropriations, interest and principal on the public debt are paid first.",
                           f"El servicio de la deuda es el pago de principal e intereses de la deuda del gobierno: ${bn(debt27)} mil millones en el presupuesto aprobado del año fiscal {years[-1]}, el {debt_cust} % bajo las asignaciones en custodia de Hacienda. La Constitución de Puerto Rico (Artículo VI, Sección 8) ordena que, cuando los recursos de un año no alcancen para sus asignaciones, se paguen primero los intereses y la amortización de la deuda pública.")}</p>
    <div class="card ps-chart"><div class="ps-head" id="psConceptsHead" aria-live="polite"></div><p class="ps-small">{T("Open a line to see what it covers, the functions it pays for and the agencies with the most of it.", "Abra una línea para ver qué incluye, las funciones que paga y las agencias con más de ella.")}</p><div id="psConcepts"></div></div>
  </section>

  <section class="block" id="capital">
    <h2><span class="ms-icon" aria-hidden="true">location_city</span>{T("4 · Capital projects by municipio", "4 · Proyectos de mejoras capitales por municipio")}</h2>
    <p class="ps-p">{T(f"Where the government plans to build: the Planning Board's Four-Year Investment Program for fiscal years {pica['years'][0]} to {pica['years'][-1]} lists the capital projects of the agencies and public corporations, each with its municipio. It is a plan of recommended projects, not money approved or spent, and it includes public corporations, such as the Aqueduct and Sewer Authority, that the budget above leaves out. {pica_placed}% of the money is in projects with a municipio; the rest is beside the map.",
                      f"Dónde el gobierno planifica construir: el Programa de Inversiones de Cuatro Años de la Junta de Planificación para los años fiscales {pica['years'][0]} a {pica['years'][-1]} enumera los proyectos de mejoras capitales de las agencias y corporaciones públicas, cada uno con su municipio. Es un plan de proyectos recomendados, no dinero aprobado ni gastado, e incluye corporaciones públicas, como la Autoridad de Acueductos y Alcantarillados, que el presupuesto de arriba no incluye. El {pica_placed} % del dinero está en proyectos con municipio; el resto está al lado del mapa.")}</p>
    <p class="ps-stage" data-t-wait>{TB("Stage and basis.", "Etapa y base.", "Planned: projects the Planning Board recommends, not money approved, obligated or spent. Basis: the adopted program as published.",
        "Planificado: proyectos que recomienda la Junta de Planificación, no dinero aprobado, obligado ni gastado. Base: el programa adoptado, según se publicó.")}</p>
    <div class="ps-controls">
      <label>{T("Show", "Mostrar")} <select id="psPicaMeasure"><option value="per">{T("Dollars per resident", "Dólares por residente")}</option><option value="total">{T("Total dollars", "Dólares en total")}</option></select></label>
      <label>{T("Agency", "Agencia")} <select id="psPicaAgency"></select></label>
      <label>{T("View", "Vista")} <select id="psPicaView"><option value="map">{T("Map", "Mapa")}</option><option value="hex">{T("Equal hexagons", "Hexágonos iguales")}</option></select></label>
    </div>
    <div class="ps-maprow">
      <div class="card ps-chart"><div id="psMap"></div><div class="ps-legend" id="psMapKey"></div></div>
      <div class="ps-side">
        <div class="card ps-unplaced" id="psUnplaced" aria-live="polite"></div>
        <div class="card ps-place" id="psPlace" aria-live="polite"></div>
      </div>
    </div>
    <p class="ps-small" id="psPicaNote"></p>
    {age("spending_pica.json")}
    <details class="ps-more"><summary>{T("See the figures as a table", "Ver las cifras en una tabla")}</summary><div class="ps-tablebox" id="psPicaTable"></div></details>
    <p class="ps-small">{T("Equal hexagons give every municipio the same size, so a small municipio counts as much on the screen as a large one; each hexagon keeps its municipio's place on the island as closely as the grid allows.",
                           "Los hexágonos iguales dan a cada municipio el mismo tamaño, por lo que un municipio pequeño cuenta en la pantalla tanto como uno grande; cada hexágono conserva el lugar de su municipio en la isla tanto como lo permite la cuadrícula.")}</p>
    <div class="note caution">{TB("Read with care.", "Lea con cuidado.", "A large project, such as a water treatment plant that serves a region, lands in the one municipio where it is built, so a few municipios stand out per resident. The map shows where a project is built, not who runs the money (often a central agency) or who benefits. Part of the program is federal money (FEMA, HUD, EPA revolving funds) that other sources also report: never add it to them.",
        "Un proyecto grande, como una planta de tratamiento de agua que sirve a una región, cae en el único municipio donde se construye, por lo que algunos municipios sobresalen por residente. El mapa muestra dónde se construye un proyecto, no quién administra el dinero (a menudo una agencia central) ni quién se beneficia. Parte del programa es dinero federal (FEMA, HUD, fondos rotatorios de la EPA) que otras fuentes también informan: nunca lo sume a ellas.")}</div>
  </section>

  <section class="block" id="federal">
    <h2><span class="ms-icon" aria-hidden="true">account_balance</span>{T("5 · Federal money in Puerto Rico", "5 · Fondos federales en Puerto Rico")}</h2>
    <p class="ps-p">{T(f"What federal agencies committed to spend on work or benefits in Puerto Rico, from USAspending.gov. In federal fiscal year {fy} (October {fy - 1} to September {fy}) the obligations add up to ${bn(fed_tot)} billion; {fed_dp}% are direct payments, mostly Social Security and Medicare benefits paid to people. The highest year was {fed['years'][fed_peak_i]}, with ${bn(fed_peak)} billion, when pandemic relief was added.",
                      f"Lo que las agencias federales se comprometieron a gastar en obras o beneficios en Puerto Rico, según USAspending.gov. En el año fiscal federal {fy} (octubre de {fy - 1} a septiembre de {fy}) las obligaciones suman ${bn(fed_tot)} mil millones; el {fed_dp} % son pagos directos, sobre todo beneficios del Seguro Social y Medicare pagados a personas. El año más alto fue {fed['years'][fed_peak_i]}, con ${bn(fed_peak)} mil millones, cuando se añadió el alivio por la pandemia.")}</p>
    <p class="ps-stage" data-t-wait>{TB("Stage and basis.", "Etapa y base.", "Obligated: committed by federal agencies, not necessarily paid out. Basis: reported by the agencies to USAspending.gov, not audited. Each federal fiscal year runs from October to September.",
        "Obligado: comprometido por las agencias federales, no necesariamente desembolsado. Base: informado por las agencias a USAspending.gov, no auditado. Cada año fiscal federal va de octubre a septiembre.")}</p>
    <div class="ps-controls">
      <label>{T("Year", "Año")} <select id="psFedYear"></select></label>
      <button type="button" class="btn" id="psFedCsv"><span class="ms-icon" aria-hidden="true">download</span>{T("Download CSV", "Descargar CSV")}</button>
    </div>
    <div class="ps-tiles" id="psFedTiles" aria-live="polite"></div>
    <p class="ps-small" data-t-wait>{T("A grant is not repaid; a loan is. The Loans figure is what the loans cost the federal government, not the amount lent.", "Una subvención no se devuelve; un préstamo sí. La cifra de Préstamos es lo que los préstamos le cuestan al gobierno federal, no la cantidad prestada.")}</p>
    {age("spending_federal.json")}
    <div class="card ps-chart"><div id="psFedYears"></div><p class="ps-small" id="psFedYearsNote"></p></div>
    <div class="card ps-chart"><div class="ps-head" id="psFedHead" aria-live="polite"></div><div id="psFedFns"></div>
      <details class="ps-more"><summary>{T("See the largest programs", "Ver los programas más grandes")}</summary><div class="ps-tablebox" id="psFedTable"></div></details>
    </div>
    <div class="card ps-chart ps-outlays" id="outlays" data-t-wait>
      <h3>{T("Obligated and paid out", "Obligado y desembolsado")}</h3>
      <p class="ps-small">{T("For the federal grants and contracts signed in each federal fiscal year since 2020, what was obligated over the awards' lives and what the federal Treasury has paid out to the recipients so far (USAspending's outlays start in fiscal year 2020). Paid out is a payment to the recipient, such as a Commonwealth agency, not yet money spent on the work. Direct payments such as Social Security are paid when they are recorded and are not shown.",
                             "Para las subvenciones y los contratos federales firmados en cada año fiscal federal desde 2020, lo que se obligó durante la vida de las adjudicaciones y lo que el Tesoro federal ha desembolsado a los receptores hasta ahora (los desembolsos de USAspending comienzan en el año fiscal 2020). Desembolsado es un pago al receptor, como una agencia del Gobierno, no todavía dinero gastado en la obra. Los pagos directos, como el Seguro Social, se pagan cuando se registran y no se muestran.")}</p>
      <div class="ps-controls"><label>{T("Awards", "Adjudicaciones")} <select id="psOutGroup"></select></label></div>
      <div class="ps-head" id="psOutHead" aria-live="polite"></div>
      <h4>{T("Share paid out by signing year", "Proporción desembolsada por año de firma")}</h4>
      <div id="psOutYrs"></div>
      <p class="ps-small">{T("Older awards have had more time to pay out, so compare a year with the years around it. A low share in an older year shows where to ask, not that anyone failed to comply.", "Las adjudicaciones más antiguas han tenido más tiempo para desembolsar, así que compare un año con los de alrededor. Una proporción baja en un año antiguo indica dónde preguntar, no que alguien incumplió.")}</p>
      <h4>{T("By function", "Por función")}</h4>
      <div id="psOut"></div>
      <div class="ps-legend"><span><i class="sw o" aria-hidden="true"></i>{T("Obligated", "Obligado")}</span><span><i class="sw p" aria-hidden="true"></i>{T("Paid out", "Desembolsado")}</span></div>
      <p class="ps-small" id="psOutNote" aria-live="polite"></p>
      {age("spending_outlays.json")}
      <details class="ps-more"><summary>{T("See the figures as a table", "Ver las cifras en una tabla")}</summary><div class="ps-tablebox" id="psOutYears"></div></details>
    <!-- /outlays --></div>
    <div class="note caution">{TB("Read with care.", "Lea con cuidado.", "Never add these figures to the budget above: the budget's federal funds are federal grants here too. Federal disaster Public Assistance is also on the FEMA disaster funding page, from OpenFEMA. An obligation is a commitment to pay, recorded when an award is made or changed, so a large grant for several years can show up in one year. The function of each program comes from the same reviewed crosswalk; program names are USAspending's, in English. The municipio figures are in the federal awards series of the map.",
        "Nunca sume estas cifras al presupuesto de arriba: los fondos federales del presupuesto también son subvenciones federales aquí. La Asistencia Pública federal por desastres también está en la página de fondos de FEMA por desastres, según OpenFEMA. Una obligación es un compromiso de pago, que se registra cuando se otorga o cambia una adjudicación, por lo que una subvención grande de varios años puede aparecer en un solo año. La función de cada programa viene de la misma tabla de equivalencias revisada; los nombres de los programas son los de USAspending, en inglés. Las cifras por municipio están en las series de adjudicaciones federales del mapa.")}</div>
  </section>

  <section class="block" id="sector" data-t-wait>
    <h2><span class="ms-icon" aria-hidden="true">pie_chart</span>{T("6 · One sector across the sources", "6 · Un sector en todas las fuentes")}</h2>
    <p class="ps-p">{T("Choose a function to see, side by side, what the Commonwealth budget gives it, what federal agencies obligated for it, what the capital program plans for it and how much that is per resident. For Education, the page adds spending per public school student and an estimate by municipio.",
                      "Elija una función para ver, lado a lado, lo que le asigna el presupuesto del Gobierno, lo que las agencias federales obligaron para ella, lo que el programa de mejoras capitales planifica y cuánto es por residente. Para Educación, la página añade el gasto por estudiante de escuela pública y un estimado por municipio.")}</p>
    <p class="ps-stage" data-t-wait>{TB("Two fiscal years.", "Dos años fiscales.", f"The Commonwealth's fiscal year runs from July to June and the federal one from October to September. Each line shows its source's latest year: the approved budget of fiscal year {years[-1]} sits beside the federal obligations of federal fiscal year {fy}. Two lines differ: spent is fiscal year {spent_y}, the latest with both approved and spent, and capital projects are the total of the program for fiscal years {cap_a} to {cap_b}. Compare shares and orders of magnitude, not dollars of one year.",
        f"El año fiscal del Gobierno va de julio a junio y el federal de octubre a septiembre. Cada línea muestra el año más reciente de su fuente: el presupuesto aprobado del año fiscal {years[-1]} aparece junto a las obligaciones federales del año fiscal federal {fy}. Dos líneas son distintas: lo gastado es del año fiscal {spent_y}, el más reciente con aprobado y gastado, y las mejoras capitales son el total del programa de los años fiscales {cap_a} a {cap_b}. Compare proporciones y órdenes de magnitud, no dólares de un mismo año.")}</p>
    <div class="ps-controls"><label>{T("Function", "Función")} <select id="psSectorPick"></select></label></div>
    <div class="card ps-chart ps-sector" id="psSector" aria-live="polite"></div>
  </section>

  <section class="block" id="recovery" data-t-wait>
    <h2><span class="ms-icon" aria-hidden="true">home_work</span>{T("7 · Disaster recovery money by municipio", "7 · Dinero de recuperación por desastres por municipio")}</h2>
    <p class="ps-p">{T("The Department of Housing manages the federal disaster recovery and mitigation grants of the Community Development Block Grant program (CDBG-DR and CDBG-MIT). USAspending places those grants where the Department is, in San Juan. The part the Department passes on as subawards, to municipalities, contractors and nonprofits, is reported where the work is done. This map shows those subawards.",
                      "El Departamento de la Vivienda administra las subvenciones federales de recuperación y mitigación por desastres del programa Community Development Block Grant (CDBG-DR y CDBG-MIT). USAspending ubica esas subvenciones donde está el Departamento, en San Juan. La parte que el Departamento entrega como subadjudicaciones, a municipios, contratistas y organizaciones sin fines de lucro, se informa donde se hace el trabajo. Este mapa muestra esas subadjudicaciones.")}</p>
    <p class="ps-stage" data-t-wait>{TB("Stage and basis.", "Etapa y base.", "Subawarded: the part of the prime grants passed on to first-tier subrecipients, counted when it is made, not when it is paid out. Basis: reported by the Department of Housing under the federal transparency law, not audited.",
        "Subadjudicado: la parte de las subvenciones principales que se entrega a subreceptores de primer nivel, contada cuando se otorga, no cuando se desembolsa. Base: informado por el Departamento de la Vivienda bajo la ley federal de transparencia, no auditado.")}</p>
    <div class="ps-controls">
      <label>{T("Show", "Mostrar")} <select id="psRecMeasure"><option value="per">{T("Dollars per resident", "Dólares por residente")}</option><option value="total">{T("Total dollars", "Dólares en total")}</option></select></label>
      <label>{T("From", "Desde")} <select id="psRecFrom"></select></label>
    </div>
    <div class="ps-maprow">
      <div class="card ps-chart"><div id="psRecMap"></div><div class="ps-legend" id="psRecKey"></div></div>
      <div class="card ps-place" id="psRecSide" aria-live="polite"></div>
    </div>
    {age("spending_cdbgdr.json")}
    <details class="ps-more"><summary>{T("See the figures as a table", "Ver las cifras en una tabla")}</summary><div class="ps-tablebox" id="psRecTable"></div></details>
    <div class="card ps-chart" id="psRecGrantsCard">
      <h3>{T("The prime grants: obligated and paid out", "Las subvenciones principales: obligado y desembolsado")}</h3>
      <p class="ps-small">{T("Each CDBG-DR and CDBG-MIT grant to the Department of Housing: what HUD obligated over the grant's life and what the Treasury has paid out to the Department so far (its draws), from USAspending. HUD's own monthly reports for 1 September 2026 give draws within 2% of these for four of the six grants over $100 million, and lower for the mitigation grant (4%) and the 2020 earthquakes grant (19%); USAspending was read later, in November 2026. A draw pays the Department, not yet the work; a grant signed later has had less time to draw.",
                             "Cada subvención CDBG-DR y CDBG-MIT al Departamento de la Vivienda: lo que HUD obligó durante la vida de la subvención y lo que el Tesoro ha desembolsado al Departamento hasta ahora (sus giros), según USAspending. Los informes mensuales de HUD al 1 de septiembre de 2026 dan giros con una diferencia de 2 % o menos para cuatro de las seis subvenciones de más de $100 millones, y menores para la subvención de mitigación (4 %) y la de los terremotos de 2020 (19 %); USAspending se leyó después, en noviembre de 2026. Un giro le paga al Departamento, todavía no a la obra; una subvención firmada más tarde ha tenido menos tiempo para girar.")}</p>
      <div id="psRecGrants"></div>
      <div class="ps-legend"><span><i class="sw o" aria-hidden="true"></i>{T("Obligated", "Obligado")}</span><span><i class="sw p" aria-hidden="true"></i>{T("Paid out", "Desembolsado")}</span></div>
    </div>
    <div class="note caution">{TB("Read with care.", "Lea con cuidado.", "Subawards are a part of the prime grants, not money on top of them, and they are already inside the federal money of section 5: never add the two. Only first-tier subawards that the Department reports under the federal transparency law are here, usually of $30,000 or more; the money it spends through its own housing programs is not placed. A subaward is counted in the year it is made and where the work is reported, which can differ from where the people it helps live.",
        "Las subadjudicaciones son una parte de las subvenciones principales, no dinero adicional, y ya están dentro de los fondos federales de la sección 5: nunca sume ambas. Solo están las subadjudicaciones de primer nivel que el Departamento informa bajo la ley federal de transparencia, por lo general de $30,000 o más; el dinero que gasta mediante sus propios programas de vivienda no se ubica. Una subadjudicación se cuenta en el año en que se otorga y donde se informa el trabajo, que puede ser distinto de donde vive la gente a la que ayuda.")}</div>
  </section>

  <section class="block" id="fema" data-t-wait>
    <h2><span class="ms-icon" aria-hidden="true">home_work</span>{T("8 · FEMA Public Assistance: stage and age", "8 · Asistencia Pública de FEMA: etapa y antigüedad")}</h2>
    <p class="ps-p">{T(f"FEMA's Public Assistance pays to repair public roads, schools, utilities and other public facilities after a disaster. OpenFEMA lists {fema_n:,} Puerto Rico projects with ${bn(fema_tot)} billion of federal share obligated, and the step each project is in: closed out, open or pending a review. It gives obligations, not payments. The Disaster funding and need page has the same money by municipio with each disaster's damage and need.",
                      f"La Asistencia Pública de FEMA paga la reparación de carreteras, escuelas, utilidades y otras instalaciones públicas después de un desastre. OpenFEMA lista {fema_n:,} proyectos de Puerto Rico con ${bn(fema_tot)} mil millones de parte federal obligada, y la etapa de cada proyecto: cerrado, abierto o pendiente de una revisión. Da obligaciones, no pagos. La página de Fondos por desastres y necesidad tiene el mismo dinero por municipio con los daños y la necesidad de cada desastre.")}</p>
    <p class="ps-stage">{TB("Stage and basis.", "Etapa y base.", "Obligated by FEMA, by each project's process step; reported in OpenFEMA, not audited. Closed out is FEMA's final reconciliation of a project's costs: an open project can be finished on the ground and still waiting for its documents.",
        "Obligado por FEMA, según la etapa de cada proyecto; informado en OpenFEMA, no auditado. Cerrado es la conciliación final de FEMA de los costos de un proyecto: un proyecto abierto puede estar terminado en el terreno y esperando sus documentos.")}</p>
    <p class="ps-p"><a href="public-money.html">{T("Open the Disaster funding and need page", "Abrir la página de Fondos por desastres y necesidad")}</a></p>
    <div class="ps-tiles" id="psFemaTiles" aria-live="polite"></div>
    <div class="card ps-chart"><h3>{T("By stage", "Por etapa")}</h3><div id="psFemaStage"></div><div class="ps-legend" id="psFemaKey"></div></div>
    <div class="card ps-chart"><h3>{T("How long the open money has been open", "Cuánto tiempo lleva abierto el dinero abierto")}</h3><div id="psFemaAge"></div></div>
    <div class="ps-controls">
      <label>{T("Show", "Mostrar")} <select id="psFemaMeasure"><option value="old">{T("Dollars open more than five years, per resident", "Dólares abiertos hace más de cinco años, por residente")}</option><option value="closed">{T("Share closed out", "Proporción cerrada")}</option><option value="age">{T("Median age of what is open", "Mediana de antigüedad de lo abierto")}</option></select></label>
    </div>
    <div class="ps-maprow">
      <div class="card ps-chart"><div id="psFemaMap"></div><div class="ps-legend" id="psFemaKey2"></div></div>
      <div class="card ps-place" id="psFemaSide" aria-live="polite"></div>
    </div>
    {age("spending_fema_pa.json")}
    <details class="ps-more"><summary>{T("See the figures as a table", "Ver las cifras en una tabla")}</summary><div class="ps-tablebox" id="psFemaMuni"></div><div class="ps-tablebox" id="psFemaTable"></div></details>
    <div class="note caution">{TB("Read with care.", "Lea con cuidado.", f"Most of the money, recorded as Statewide, names no municipio and is not on the map, so a municipio's figure is only the part that names it. An old open project points to where to ask, not to a failure: large permanent works take years, and some wait only for their documents. Never add these dollars to the federal money of section 5, which counts the same awards. Closed out is measured in dollars ({f_closed_usd}%); counted in projects, {f_closed_n:,} of {f_all_n:,} ({f_closed_cnt}%) are closed out, because the largest projects are the ones still open.",
        f"La mayor parte del dinero, registrada como Statewide, no nombra un municipio y no está en el mapa, por lo que la cifra de un municipio es solo la parte que lo nombra. Un proyecto abierto antiguo indica dónde preguntar, no un fallo: las obras permanentes grandes toman años y algunas solo esperan sus documentos. Nunca sume estos dólares a los fondos federales de la sección 5, que cuentan las mismas adjudicaciones. El cierre se mide en dólares ({f_closed_usd} %); contado en proyectos, {f_closed_n:,} de {f_all_n:,} ({f_closed_cnt} %) están cerrados, porque los proyectos más grandes son los que siguen abiertos.")}</div>
  </section>

  <section class="block" id="municipio" data-t-wait>
    <h2><span class="ms-icon" aria-hidden="true">location_city</span>{T("9 · My municipio", "9 · Mi municipio")}</h2>
    <p class="ps-p">{T("Choose a municipio to see, in one place, the public money in its territory that this page can place, who runs each part, the answers to four questions about its disaster recovery money, and what could be requested to evaluate how it is being spent.",
                      "Elija un municipio para ver, en un solo lugar, el dinero público en su territorio que esta página puede ubicar, quién administra cada parte, las respuestas a cuatro preguntas sobre su dinero de recuperación por desastres y qué se podría pedir para evaluar cómo se está gastando.")}</p>
    <div class="ps-controls"><label>{T("Municipio", "Municipio")} <select id="psMuniPick"><option value="">{T("Choose a municipio", "Elija un municipio")}</option></select></label></div>
    <div class="card ps-place ps-muni" id="psMuni" aria-live="polite"></div>
    <p class="ps-small">{T("A municipio's figures are the money that names it: much of the money is run island-wide and is in no municipio. The municipal government's own budget is not here; ABRE Tu Municipio covers its finances.",
                           "Las cifras de un municipio son el dinero que lo nombra: gran parte del dinero se administra para toda la isla y no está en ningún municipio. El presupuesto propio del gobierno municipal no está aquí; ABRE Tu Municipio cubre sus finanzas.")}</p>
    <p class="ps-small">{T("Why one municipio shows far more recovery money than another: besides the damage, FEMA Public Assistance is obligated project by project, for the projects an applicant requests and documents; and the large federal recovery grants to Commonwealth agencies are recorded in San Juan, where the agency is. Only what is passed on by subaward is placed where the work is reported.",
                           "Por qué un municipio muestra mucho más dinero de recuperación que otro: además de los daños, la Asistencia Pública de FEMA se obliga proyecto por proyecto, para los proyectos que un solicitante pide y documenta; y las subvenciones federales grandes de recuperación a agencias del Gobierno se registran en San Juan, donde está la agencia. Solo lo que se pasa por subadjudicación se ubica donde se informa la obra.")}</p>
  </section>

  <section class="block" id="method">
    <h2><span class="ms-icon" aria-hidden="true">info</span>{T("Method", "Método")}</h2>
    <div class="note">{TB("The data sheets.", "Las hojas de datos.", "The Office of Management and Budget (OGP) publishes one data sheet (sábana) for each approved and each proposed budget, with one line for each agency, fund, program, concept and object of expense. A newer sheet repeats earlier years; each fiscal year and stage on this page comes from the newest sheet whose lines add up to its own total, so every figure equals OGP's published total. A draft marked confidential that is posted on the budget site is not used.",
        "La Oficina de Gerencia y Presupuesto (OGP) publica una hoja de datos (que llama «sábana») por cada presupuesto aprobado y cada propuesto, con una línea por agencia, fondo, programa, concepto y objeto de gasto. Una hoja más reciente repite años anteriores; cada año fiscal y etapa de esta página viene de la hoja más reciente cuyas líneas suman su propio total, por lo que cada cifra es igual al total publicado por la OGP. No se usa un borrador marcado como confidencial que está en el sitio del presupuesto.")}</div>
    <div class="note">{TB("Functions.", "Funciones.", "Each agency has one function (Education, Health and so on); a few programs and the funds in custodial accounts have their own. Debt service and pensions are always Debt and pensions. The table of equivalences was reviewed on 9 November 2026 against the UN Classification of the Functions of Government (COFOG); the decisions are in the project repository.",
        "Cada agencia tiene una función (Educación, Salud, etc.); algunos programas y los fondos de las cuentas de custodia tienen la suya. El servicio de la deuda y las pensiones siempre son Deuda y pensiones. La tabla de equivalencias se revisó el 9 de noviembre de 2026 según la Clasificación de las Funciones del Gobierno de la ONU (COFOG); las decisiones están en el repositorio del proyecto.")}</div>
    <div class="card ps-chart" id="basis" data-t-wait>
      <h3>{T("Where each line's function comes from", "De dónde viene la función de cada línea")}</h3>
      <p class="ps-small">{T("A line takes its function from its own row of the table of equivalences when it has one: its program, its object of expense, or its concept when that is debt service or pensions. Otherwise it takes its agency's general function. An agency with mixed work, classified by its general function, hides the mix, so the largest such agencies come first in the next review.",
                             "Una línea toma su función de su propia fila en la tabla de equivalencias cuando la tiene: su programa, su objeto de gasto o su concepto cuando es servicio de la deuda o pensiones. Si no, toma la función general de su agencia. Una agencia con trabajo mixto, clasificada por su función general, esconde la mezcla, por lo que las más grandes de ellas van primero en la próxima revisión.")}</p>
      <div id="psBasis"></div>
    </div>
    <div class="note">{TB("Capital projects.", "Mejoras capitales.", "Each project line of the program's agency tables is read with its municipio and its four fiscal years; a line counts only when its years add up to its total. A line that lists several municipios is split equally among them; a line for a region, the whole island or no defined place is shown beside the map. Per resident uses the Census Bureau's estimate for July 1, 2025. Project names are not shown.",
        "Cada línea de proyecto de las tablas de agencias del programa se lee con su municipio y sus cuatro años fiscales; una línea cuenta solo cuando sus años suman su total. Una línea que enumera varios municipios se divide en partes iguales entre ellos; una línea para una región, toda la isla o un lugar no definido se muestra al lado del mapa. Por residente usa el estimado de la Oficina del Censo al 1 de julio de 2025. No se muestran los nombres de los proyectos.")}</div>
    <div class="note">{TB("Federal money.", "Fondos federales.", "For each finished federal fiscal year, USAspending.gov's obligations with place of performance Puerto Rico are read once for each award type: assistance by program (assistance listing), contracts by awarding agency. Each program takes its function from the crosswalk, or else its agency's; a contract takes its agency's. A year counts as final from 15 November, about six weeks after it ends. Loans are the estimated cost to the government, not the amount lent.",
        "Para cada año fiscal federal terminado se leen las obligaciones de USAspending.gov con lugar de ejecución Puerto Rico, una vez por cada tipo de adjudicación: la asistencia por programa (listado de asistencia) y los contratos por agencia que adjudica. Cada programa toma su función de la tabla de equivalencias o, si no, la de su agencia; un contrato toma la de su agencia. Un año se considera final desde el 15 de noviembre, unas seis semanas después de terminar. Los préstamos son el costo estimado para el gobierno, no la cantidad prestada.")}</div>
    <div class="note" data-t-wait>{TB("Paid out.", "Desembolsado.", "USAspending.gov's award search gives, for each grant and contract in Puerto Rico signed from federal fiscal year 2020, its obligation over its life and its outlays to date. An award counts up to its obligated amount; the note under the chart counts the exceptions. The two latest signing years are read again each year.",
        "La búsqueda de adjudicaciones de USAspending.gov da, para cada subvención y contrato en Puerto Rico firmado desde el año fiscal federal 2020, su obligación durante su vida y sus desembolsos hasta la fecha. Una adjudicación cuenta hasta su monto obligado; la nota bajo el gráfico cuenta las excepciones. Los dos años de firma más recientes se leen de nuevo cada año.")}</div>
    <div class="note">{TB("Sectors and data age.", "Sectores y antigüedad de los datos.", "Section 6 reads the same files as the rest of the page. Per resident uses one population: the Census Bureau's estimate for July 1, 2025. Spending per public school student divides the Department of Education's spending by the students of the school year that matches the fiscal year (NCES Common Core of Data); the estimate by municipio splits that spending by each municipio's share of the students. Each data section says when its file was built and is marked when the file is older than two of its update cycles.",
        "La sección 6 lee los mismos archivos que el resto de la página. Por residente usa una sola población: la estimación de la Oficina del Censo para el 1 de julio de 2025. El gasto por estudiante de escuela pública divide el gasto del Departamento de Educación entre los estudiantes del año escolar que corresponde al año fiscal (Common Core of Data de NCES); el estimado por municipio reparte ese gasto según la proporción de estudiantes de cada municipio. Cada sección de datos dice cuándo se preparó su archivo y se marca cuando el archivo tiene más de dos de sus ciclos de actualización.")}</div>
    <div class="note">{TB("Disaster recovery.", "Recuperación por desastres.", "For each finished federal fiscal year, USAspending.gov's subawards with place of performance Puerto Rico are read for the Department of Housing's disaster grants only (grant numbers of the DR, MIT and electrical grid grants; the yearly block grants and the COVID grant are left out): once by municipio and once for Puerto Rico as a whole, so the subawards that name no municipio are shown apart. Per resident uses the same population as the capital projects map.",
        "Para cada año fiscal federal terminado se leen las subadjudicaciones de USAspending.gov con lugar de ejecución Puerto Rico, solo de las subvenciones por desastres del Departamento de la Vivienda (los números de las subvenciones de recuperación, mitigación y red eléctrica; quedan fuera las subvenciones anuales y la de COVID): una vez por municipio y otra para Puerto Rico en conjunto, para mostrar aparte las subadjudicaciones que no nombran un municipio. Por residente usa la misma población que el mapa de mejoras capitales.")}</div>
    <div class="note">{TB("What the page does not do.", "Lo que la página no hace.", "It does not place the budget in municipios (the capital projects and disaster recovery maps place plans and subawards where the work is reported), compare Puerto Rico with other places, or say whether a function received enough. It shows where money is assigned, not what it achieved. Never add two budgets: they are different stages, or different years, of the same money.",
        "No ubica el presupuesto en los municipios (los mapas de mejoras capitales y de recuperación ubican planes y subadjudicaciones donde se informa el trabajo), no compara a Puerto Rico con otros lugares ni dice si una función recibió suficiente. Muestra dónde se asigna el dinero, no lo que logró. Nunca sume dos presupuestos: son etapas distintas, o años distintos, del mismo dinero.")}</div>
  </section>

  <section class="block" id="sources">
    <h2><span class="ms-icon" aria-hidden="true">menu_book</span>{T("Sources and licenses", "Fuentes y licencias")}</h2>
    <div class="note">{TB("Office of Management and Budget (OGP), Government of Puerto Rico.", "Oficina de Gerencia y Presupuesto (OGP), Gobierno de Puerto Rico.", "Budget data sheets (Sábana) of the approved and proposed budgets, www.presupuestos.pr.gov. Public documents of the Government of Puerto Rico; OGP states no license for them.",
        "Hojas de datos («sábanas») de los presupuestos aprobados y propuestos, www.presupuestos.pr.gov. Documentos públicos del Gobierno de Puerto Rico; la OGP no indica una licencia para ellos.")}</div>
    <div class="note" data-t-wait>{TB("Law and roles.", "Leyes y funciones.", "Who proposes, adopts and certifies the budget, what proposed, approved and spent mean, and the rule on money of earlier fiscal years: OGP's Manual of the Budget Process (gestion-presupuestaria.ogp.pr.gov, updated 18 November 2025) and PROMESA, section 202 (Public Law 114-187; 48 U.S.C. 2142). The order of payment when resources fall short: Constitution of Puerto Rico, Article VI, section 8. The Public Housing Administration: Act 66 of 1989, as OGP's budget document for the agency describes it (docs.pr.gov).",
        "Quién propone, adopta y certifica el presupuesto, qué significan propuesto, aprobado y gastado, y la regla sobre el dinero de años fiscales anteriores: Manual del Proceso Presupuestario de la OGP (gestion-presupuestaria.ogp.pr.gov, actualizado el 18 de noviembre de 2025) y PROMESA, sección 202 (Ley Pública 114-187; 48 U.S.C. 2142). El orden de pago cuando los recursos no alcanzan: Constitución de Puerto Rico, Artículo VI, Sección 8. La Administración de Vivienda Pública: Ley 66 de 1989, según la describe el documento de presupuesto de la OGP para la agencia (docs.pr.gov).")}</div>
    <div class="note">{TB("Junta de Planificación de Puerto Rico.", "Junta de Planificación de Puerto Rico.", "Programa de Inversiones de Cuatro Años (PICA), adopted, jp.pr.gov. Public document of the Government of Puerto Rico; the Planning Board states no license for it. Population: U.S. Census Bureau, Population Estimates.",
        "Programa de Inversiones de Cuatro Años (PICA), adoptado, jp.pr.gov. Documento público del Gobierno de Puerto Rico; la Junta de Planificación no indica una licencia para él. Población: Oficina del Censo de EE. UU., Estimados de Población.")}</div>
    <div class="note">{TB("USAspending.gov, US Department of the Treasury.", "USAspending.gov, Departamento del Tesoro de EE. UU.", "Federal awards by place of performance (spending_by_category API) and award outlays (spending_by_award API), www.usaspending.gov. No license is stated for the data; the API's source code is CC0-1.0.",
        "Adjudicaciones federales por lugar de ejecución (API spending_by_category) y desembolsos por adjudicación (API spending_by_award), www.usaspending.gov. No se indica una licencia para los datos; el código fuente de la API es CC0-1.0.")}</div>
    <div class="note">{TB("Data and method.", "Datos y método.", "The data files are data/spending_state.json (ogp_budget.py), data/spending_pica.json (pica.py), data/spending_federal.json (federal_awards.py), data/spending_outlays.json (federal_outlays.py), data/spending_cdbgdr.json (cdbg_dr.py) and data/spending_fema_pa.json (fema_pa_stage.py); the method is in docs/spending.md of the project repository.",
        "Los archivos de datos son data/spending_state.json (ogp_budget.py), data/spending_pica.json (pica.py), data/spending_federal.json (federal_awards.py), data/spending_outlays.json (federal_outlays.py), data/spending_cdbgdr.json (cdbg_dr.py) y data/spending_fema_pa.json (fema_pa_stage.py); el método está en docs/spending.md del repositorio del proyecto.")}</div>
    <div class="note">{TB("How to cite this page.", "Cómo citar esta página.", "Foundation for Puerto Rico, Knowledge Area: Budget and public spending, PR Data Observatory, Snapshot 2026-11. Data: Oficina de Gerencia y Presupuesto and Junta de Planificación, Gobierno de Puerto Rico; USAspending.gov.",
        "Foundation for Puerto Rico, Área de conocimiento: Gasto público, Observatorio de Datos de PR, Snapshot 2026-11. Datos: Oficina de Gerencia y Presupuesto y Junta de Planificación, Gobierno de Puerto Rico; USAspending.gov.")}</div>
  </section>
</main>
<script src="js/core/knowledge.js?v=36"></script>
<script>Core.knowledge.render(); I18N.apply();</script>
<script src="js/common.js?v=20"></script>
<script src="js/public_spending.js?v=27"></script>
<script src="js/chatboot.js?v=59"></script>
</body>
</html>
"""
    (ROOT / "site" / "public-spending.html").write_text(page, encoding="utf-8", newline="\n")
    # Keys that only the after-ready parts use (public_spending_charts.js, _sectors.js, _recovery.js and the text of sections 6 and 7) go to the module
    # "after" (i18n_src/pages.json), loaded with those scripts, so the page bundle stays within the first-load budget (dictionary_src/routes.json).
    main_js = (ROOT / "site" / "js" / "public_spending.js").read_text(encoding="utf-8")
    outside = re.sub(r'<section class="block" id="(sector|recovery|fema|municipio)" data-t-wait>.*?</section>', "", page, flags=re.S)
    outside = re.sub(r'<div class="card ps-chart ps-outlays" id="outlays" data-t-wait>.*?<!-- /outlays --></div>', "", outside, flags=re.S)
    outside = re.sub(r'<div class="card ps-chart" id="basis" data-t-wait>.*?<div id="psBasis"></div>\s*</div>', "", outside, flags=re.S)   # step 4 card   # section 5's paid-out card (decision 96, step 2)
    outside = re.sub(r'<(p|div) class="[^"]*" data-t-wait>.*?</\1>', "", outside, flags=re.S)   # the stage lines and the gap note (decision 96) wait for the module too
    def first_load(k):
        e = html.escape(k, quote=False)
        return k in outside or e in outside or html.escape(k) in outside or f"'{k}'" in main_js or f'"{k}"' in main_js or f"`{k}`" in main_js
    muni_js = (ROOT / "site" / "js" / "public_spending_municipio.js").read_text(encoding="utf-8")
    on_use = lambda k: (f"'{k}'" in muni_js or f'"{k}"' in muni_js or f"`{k}`" in muni_js) and not first_load(k) and k not in page   # decision 109, step 5
    muni = {k: v for k, v in ES.items() if on_use(k)}
    ag_js = (ROOT / "site" / "js" / "public_spending_agencies.js").read_text(encoding="utf-8")   # decision 112, step 2: the module 'agencies', on first use like 'municipio'
    ag = {k: v for k, v in ES.items() if (f"'{k}'" in ag_js or f'"{k}"' in ag_js or f"`{k}`" in ag_js) and not first_load(k) and k not in page and k not in muni}
    after = {k: v for k, v in ES.items() if not first_load(k) and k not in muni and k not in ag}
    es = {"_about": "Spanish of the Public spending page (public-spending.html) and of public_spending.js; written by docs/analysis/public-spending-2026-11/make_page.py. Do not edit by hand.",
          **dict(sorted((k, v) for k, v in ES.items() if k not in after and k not in muni and k not in ag))}
    es_after = {"_about": "Spanish of the after-ready parts of the Public spending page (public_spending_charts.js, public_spending_sectors.js, public_spending_recovery.js, sections 6 and 7): the module 'after' of the page in i18n_src/pages.json; written by docs/analysis/public-spending-2026-11/make_page.py. Do not edit by hand.",
                **dict(sorted(after.items()))}
    (ROOT / "i18n_src" / "es" / "public_spending_after.json").write_text(json.dumps(es_after, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    es_muni = {"_about": "Spanish of the Public spending page's My municipio section (public_spending_municipio.js, loaded on first use): the module 'municipio' of the page in i18n_src/pages.json; written by docs/analysis/public-spending-2026-11/make_page.py. Do not edit by hand.",
               **dict(sorted(muni.items()))}
    (ROOT / "i18n_src" / "es" / "public_spending_municipio.json").write_text(json.dumps(es_muni, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    es_ag = {"_about": "Spanish of the Public spending page's approved and spent by agency and fund (public_spending_agencies.js, loaded on first use): the module 'agencies' of the page in i18n_src/pages.json; written by docs/analysis/public-spending-2026-11/make_page.py. Do not edit by hand.",
             **dict(sorted(ag.items()))}
    (ROOT / "i18n_src" / "es" / "public_spending_agencies.json").write_text(json.dumps(es_ag, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    (ROOT / "i18n_src" / "es" / "public_spending.json").write_text(json.dumps(es, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    held_p = ROOT / "i18n_src" / "held_for_review.json"
    held = json.loads(held_p.read_text(encoding="utf-8"))
    for scope, keys in (("public_spending", {k: v for k, v in HELD.items() if k not in after and k not in muni and k not in ag}), ("public_spending_after", {k: v for k, v in HELD.items() if k in after}),
                        ("public_spending_municipio", {k: v for k, v in HELD.items() if k in muni})):
        held["spanish"][scope] = dict(sorted(keys.items()))   # each held key is listed under the scope file that holds it
        if not keys:
            held["spanish"].pop(scope)
    held_p.write_text(json.dumps(held, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    keep_p = ROOT / "i18n_src" / "keep.json"
    keep = json.loads(keep_p.read_text(encoding="utf-8"))
    keep += [k for k in sorted(HELD) if k not in keep]
    keep_p.write_text(json.dumps(keep, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")   # the file is one line
    print(f"wrote site/public-spending.html, i18n_src/es/public_spending.json ({len(ES) - len(after) - len(muni) - len(ag)} strings), public_spending_agencies.json ({len(ag)} strings), public_spending_after.json ({len(after)} strings) and public_spending_municipio.json ({len(muni)} strings), {len(HELD)} held for review")


if __name__ == "__main__":
    build()
