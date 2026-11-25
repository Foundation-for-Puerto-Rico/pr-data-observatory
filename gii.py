"""Global Innovation Index for Puerto Rico (Knowledge Area): the frozen 2021 FPR profile, its updated values and an indicative GII 2026 comparison.

    python gii.py                  build site/data/gii_profile.json and site/data/gii_changes.json (downloads only what is missing from the cache, cache/gii/)
    python gii.py --refresh        download every series again (the newest release of each source)
    python gii.py --check          rebuild from the cache and exit 1 when the two files are not what it gives (no network, nothing written)
    python -I gii.py --extract-2026   read the GII 2026 database (cache/gii/2026/, downloaded by hand, CC BY 4.0) with openpyxl and keep only what
                                   the comparison needs in cache/gii/2026/gii2026_extract.json; run it with a Python that has openpyxl (the build does not)

The original (docs/analysis/gii-2021/gii_original.json) is FPR's 2021 country profile, made with the GII 2020 method (Cornell University, INSEAD, WIPO)
and frozen as printed: 80 indicators, the raw values, the ranks "x / 132" and the marks. This script never changes it. It adds, beside it:

  - the newest value of each indicator that an open API publishes for Puerto Rico, freshest source first (UPDATES: when two sources publish the
    same series, the one with the most recent year wins; a tie keeps the first listed);
      World Bank WGI (api.worldbank.org, source 3)   government effectiveness, regulatory quality, rule of law
      World Bank WDI (api.worldbank.org)             gross capital formation, new business density, the US tariff (FPR's method), ICT components
      UNESCO UIS Data API (api.uis.unesco.org)       education spending, school life expectancy, pupils per qualified teacher, tertiary enrollment,
                                                     STEM graduates, inbound mobility
      IMF DataMapper (imf.org)                       GDP in PPP dollars; real GDP growth for 6.2.1
      BLS LAUS (api.bls.gov, v1, no key)             employment in Puerto Rico for 6.2.1
      EIA bulk file INTL.zip (api.eia.gov/bulk, no key, about 24 MB)   net electricity generation for 3.2.1; energy consumption for the FPR estimate
                                                     of IN.3.3.2, new in the GII 2026 (shown in gii_changes.json, not as one of the 80)
      Census Bureau population estimates (www2.census.gov CSV, no key)   population for 3.2.1
      BLS OEWS state file oesmYYst.zip (bls.gov, no key, about 7.5 MB)   employment by occupation group for 5.1.1
    A value computed with FPR's method from these sources is upd_kind "fpr" ("Estimado de FPR" on the page). The updated column never has a rank.
    Census Bureau APIs are not used: the repository has no Census key (acs_small.py reads the summary files instead). Patent applications (6.1.1) have
    no keyless source: PatentsView's files moved to the USPTO Open Data Portal, which needs a key (NOT_UPDATED).
  - for the indicators whose Puerto Rico source and definition match GII 2026 (COMPARE), where the updated value would fall among the 139 GII 2026
    economies with data: "X/N" (N = the economies with data plus Puerto Rico, like the profile's "/132"), with the 25th, 50th and 75th percentiles of
    their values. Indicative position calculated by FPR, not an official WIPO rank.
    NO_POSITION says why the other updated indicators get none.
  - a change marker for each updated value against the printed one (change): better or worse in the GII's direction (dir, from the profile's *),
    "same" below CHANGE_SHARE (5%) of the GII 2026 interquartile range of the indicator, "na" when not comparable (NOT_COMPARABLE, or no 2021 value); the WGI through one release (WGI_BASE);
  - the status of each indicator in the GII 2026 (same, renamed, redefined, dropped) from docs/analysis/gii-2021/gii_crosswalk.json, and from the same
    file site/data/gii_changes.json, which the page loads when "Changes in the index since 2020" is opened. No pillar, sub-index or overall score is computed, and no economy is named
    (a published percentile can coincide with one unnamed economy's value: the median in 8 of the 10, all three for IN.3.2.4).

No other economy's GII 2020 data are published (that edition is CC BY-NC-ND 3.0 IGO): only Puerto Rico's own values and the printed ranks.
"""

import io
import json
import math
import os
import re
import statistics
import sys
import time
import xml.etree.ElementTree as ET
import zipfile
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ORIGINAL = ROOT / "docs" / "analysis" / "gii-2021" / "gii_original.json"
OUT = ROOT / "site" / "data" / "gii_profile.json"
OUT_CHANGES = ROOT / "site" / "data" / "gii_changes.json"
CROSSWALK = ROOT / "docs" / "analysis" / "gii-2021" / "gii_crosswalk.json"
CACHE = ROOT / "cache" / "gii"
G26_DIR = CACHE / "2026"
G26_XLSX = G26_DIR / "wipo-pub-2000-2026-tech1.xlsx"
G26_EXTRACT = G26_DIR / "gii2026_extract.json"
G26_URL = "https://www.wipo.int/edocs/pubdocs/en/wipo-pub-2000-2026-tech1.xlsx"
G26_DOWNLOADED = "2026-10-23"
# SHA-256 of the file as WIPO serves it (943,159 bytes, Last-Modified 2026-09-28), taken at the download on 2026-10-23. A copy in a folder that SharePoint
# or OneDrive syncs gains customXml metadata parts (the sheets are unchanged), so its own hash differs: the extract records both, and their difference.
G26_SHA256_WIPO = "bbce0a2da785d566992e8d0b7677f76da2a8399a08fc45fd7e7e5485dd4ffd73"
UA = {"User-Agent": "pr-digital-twin/1.0 (Foundation for Puerto Rico; open-data build)"}
LAST_YEAR = date.today().year - 1   # IMF series run into projections: the newest year taken is last year (an estimate until the IMF has the actual)


def log(*a):
    print(*a, file=sys.stderr)


# ── Sources ──────────────────────────────────────────────────────────────────

SOURCES = {
    "wb_wgi": {"name": {"en": "World Bank, Worldwide Governance Indicators (WGI)", "es": "Banco Mundial, Indicadores Mundiales de Gobernanza (WGI)"}, "url": "https://www.worldbank.org/en/publication/worldwide-governance-indicators", "license": "CC BY 4.0"},
    "wb_wdi": {"name": {"en": "World Bank, World Development Indicators (WDI)", "es": "Banco Mundial, Indicadores del Desarrollo Mundial (WDI)"}, "url": "https://datacatalog.worldbank.org/search/dataset/0037712", "license": "CC BY 4.0"},
    "unesco_uis": {"name": {"en": "UNESCO Institute for Statistics (UIS)", "es": "Instituto de Estadística de la UNESCO (UIS)"}, "url": "https://databrowser.uis.unesco.org/", "license": "CC BY-SA 3.0 IGO"},
    "imf_weo": {"name": {"en": "IMF, World Economic Outlook", "es": "FMI, Perspectivas de la Economía Mundial"}, "url": "https://www.imf.org/external/datamapper/", "license": "IMF terms of use: free reuse with attribution"},
    "bls_laus": {"name": {"en": "BLS, Local Area Unemployment Statistics (LAUS)", "es": "BLS, Estadísticas de Desempleo de Áreas Locales (LAUS)"}, "url": "https://www.bls.gov/lau/", "license": "US Government work (public domain)"},
    "wipo_gii2026": {"name": {"en": "WIPO, Global Innovation Index 2026 database", "es": "OMPI, base de datos del Índice Global de Innovación 2026"}, "url": G26_URL, "license": "CC BY 4.0 (third-party data excluded)"},
    "eia_intl": {"name": {"en": "US EIA, International Energy Data", "es": "EIA de EE. UU., datos internacionales de energía"}, "url": "https://www.eia.gov/international/data/country/PRI", "license": "US Government work (public domain)"},
    "census_pep": {"name": {"en": "US Census Bureau, Population Estimates", "es": "Negociado del Censo de EE. UU., estimados de población"}, "url": "https://www.census.gov/programs-surveys/popest.html", "license": "US Government work; cite the Census Bureau as the source"},
    "bls_oews": {"name": {"en": "BLS, Occupational Employment and Wage Statistics (OEWS)", "es": "BLS, Estadísticas de Empleo y Salarios por Ocupación (OEWS)"}, "url": "https://www.bls.gov/oes/", "license": "US Government work (public domain)"},
}
LINK = {
    "wb_wgi": "https://www.worldbank.org/en/publication/worldwide-governance-indicators",
    "wb": "https://data.worldbank.org/indicator/{series}?locations=PR",
    "wb_usa": "https://data.worldbank.org/indicator/{series}?locations=US",
    "uis": "https://databrowser.uis.unesco.org/",
    "imf": "https://www.imf.org/external/datamapper/{series}@WEO/PRI",
    "eia": "https://www.eia.gov/international/data/country/PRI",
    "oews": "https://www.bls.gov/oes/tables.htm",
}
EIA_INTL = "https://www.eia.gov/opendata/bulk/INTL.zip"
# The EIA series kept from INTL.zip (Puerto Rico, annual): net generation, total energy consumption and its part from nuclear, renewables and other
EIA_GEN, EIA_ENERGY, EIA_LOWC = "INTL.2-12-PRI-BKWH.A", "INTL.44-2-PRI-QBTU.A", "INTL.4419-2-PRI-QBTU.A"
PEP = "https://www2.census.gov/programs-surveys/popest/datasets/2020-{v}/state/totals/NST-EST{v}-ALLDATA.csv"
OEWS = "https://www.bls.gov/oes/special-requests/oesm{yy}st.zip"
# 5.1.1: the SOC 2018 major groups taken as ISCO-08 groups 1-3 (managers, professionals, technicians and associate professionals): 11 management,
# 13 business and financial operations, 15 computer and mathematical, 17 architecture and engineering, 19 life, physical and social science, 21 community
# and social service, 23 legal, 25 educational instruction and library, 27 arts, design, entertainment, sports and media, 29 healthcare practitioners and
# technical: the BLS's "management, professional and related occupations". Healthcare support (31) and the service, sales, office, construction,
# production and transport groups (33-53) are left out.
ISCO_1_3 = ("11", "13", "15", "17", "19", "21", "23", "25", "27", "29")

# Each updated indicator: candidates (kind, series), freshest first; then what the page says about it (en, es)
UPDATES = {
    "1.1.2": {"cand": [("wgi", "GOV_WGI_GE.EST")], "note": ("The World Bank's current WGI release (September 2026) revises every past year, so the printed value, from an earlier release, cannot be matched to a year of this one.", "La edición actual de los WGI del Banco Mundial (septiembre de 2026) revisa todos los años anteriores, así que el valor publicado, de una edición anterior, no corresponde a un año de esta.")},
    "1.2.1": {"cand": [("wgi", "GOV_WGI_RQ.EST")], "note": ("The current WGI release revises every past year.", "La edición actual de los WGI revisa todos los años anteriores.")},
    "1.2.2": {"cand": [("wgi", "GOV_WGI_RL.EST")], "note": ("The current WGI release revises every past year.", "La edición actual de los WGI revisa todos los años anteriores.")},
    "2.1.1": {"cand": [("uis", "XGDP.FSGOV"), ("wb", "SE.XPD.TOTL.GD.ZS")], "note": None},
    "2.1.3": {"cand": [("uis", "SLE.1T8")], "note": ("UIS revised the series: its current release gives 16.0 for 2013, the year of the printed 15.3.", "El UIS revisó la serie: su edición actual da 16.0 para 2013, el año del 15.3 publicado.")},
    "2.1.5": {"cand": [("uis", "PTRHC.2T3.QUALIFIED")], "note": ("FPR's series: pupils per qualified teacher (SDG 4.c.4). The GII uses the plain pupil-teacher ratio, which UIS does not publish for Puerto Rico. UIS's teacher series for Puerto Rico changed in 2024: the share of qualified secondary teachers went from 100% (2013-2016) to 48% (81% in lower secondary), the share of trained teachers from 84-95% to 13.6%, and upper secondary was not published. So the 2024 value is shown but not compared with the printed one, and no GII 2026 position is given.", "La serie de FPR: estudiantes por maestro cualificado (ODS 4.c.4). El GII usa la razón simple de estudiantes por maestro, que el UIS no publica para Puerto Rico. Las series de maestros del UIS para Puerto Rico cambiaron en 2024: la proporción de maestros de secundaria cualificados pasó del 100 % (2013-2016) al 48 % (81 % en la secundaria baja), la de maestros formados pasó del 84-95 % al 13.6 %, y la secundaria alta no se publicó. Por eso el valor de 2024 se muestra, pero no se compara con el publicado ni se da una posición en el GII 2026.")},
    "2.2.1": {"cand": [("uis", "GER.5T8"), ("wb", "SE.TER.ENRR")], "note": ("UIS revised the series after 2021 (its current release gives 107.5 for 2018).", "El UIS revisó la serie después de 2021 (su edición actual da 107.5 para 2018).")},
    "2.2.2": {"cand": [("uis", "FOSGP.5T8.F500600700")], "note": None},
    "2.2.3": {"cand": [("uis", "MOR.5T8.40510")], "note": ("New since the profile: UIS now publishes this for Puerto Rico, as a UIS estimate.", "Nuevo desde el perfil: el UIS publica ahora este dato para Puerto Rico, como un estimado del UIS.")},
    "3.2.1": {"cand": [("fpr_electricity", "")], "kind": "fpr", "note": ("FPR's method on open data: Puerto Rico's net electricity generation (US EIA) divided by its population on July 1 (Census Bureau estimates). For 2017 this gives 4,923.1 against the printed 4,920.0: FPR used 16,360 GWh from PREPA, the EIA has 16,371 GWh, and both use 3.325 million people. 2017 was the year of Hurricane María (September); the EIA's generation was 20,643 GWh in 2016. The GII takes gross generation from the International Energy Agency; net generation leaves out what the plants use themselves.", "Método de FPR con datos abiertos: la generación neta de electricidad de Puerto Rico (EIA de EE. UU.) entre su población al 1 de julio (estimados del Negociado del Censo). Para 2017 da 4,923.1 frente al 4,920.0 publicado: FPR usó 16,360 GWh de la AEE, la EIA tiene 16,371 GWh y ambos usan 3.325 millones de habitantes. 2017 fue el año del huracán María (septiembre); la generación de la EIA fue de 20,643 GWh en 2016. El GII toma la generación bruta de la Agencia Internacional de Energía; la generación neta excluye lo que consumen las propias plantas.")},
    "3.2.3": {"cand": [("wb", "NE.GDI.TOTL.ZS")], "note": None},
    "4.3.1": {"cand": [("wb_usa", "TM.TAX.MRCH.WM.AR.ZS")], "kind": "fpr", "note": ("FPR's method: the United States tariff schedule applies in Puerto Rico, so this is the value of the United States. GII 2026 uses a newer WTO figure (2024) for the United States than the World Bank's latest, so no GII 2026 position is given.", "Método de FPR: en Puerto Rico aplica el arancel de los Estados Unidos, así que este es el valor de los Estados Unidos. El GII 2026 usa una cifra más reciente de la OMC (2024) para los Estados Unidos que la más reciente del Banco Mundial, por lo que no se da una posición en el GII 2026.")},
    "4.3.3": {"cand": [("imf", "PPPGDP")], "note": ("The current World Economic Outlook revises 2019 to 119.6 (FPR used 126.9 from the October 2019 edition). The latest year may be an IMF estimate.", "Las Perspectivas de la Economía Mundial actuales revisan 2019 a 119.6 (FPR usó 126.9 de la edición de octubre de 2019). El año más reciente puede ser un estimado del FMI.")},
    "5.1.1": {"cand": [("fpr_knowledge_jobs", "")], "kind": "fpr", "note": ("FPR's method on open data: the employment of the occupation groups that match ISCO groups 1 to 3, divided by total employment, from the BLS OEWS estimates for Puerto Rico (May of the year shown). The groups are SOC major groups 11 to 29: management; business and financial; computer and mathematical; architecture and engineering; life, physical and social science; community and social service; legal; education; arts, design and media; and healthcare practitioners and technicians. FPR's 2021 list of detailed occupations is not in the repository, and these groups give 29.6% for May 2019 and 30.2% for May 2020, not the printed 32.0, so the value is not compared with it. OEWS counts wage and salary jobs in establishments and leaves out the self-employed.", "Método de FPR con datos abiertos: el empleo de los grupos de ocupaciones que corresponden a los grupos 1 a 3 de la CIUO, entre el empleo total, según los estimados OEWS del BLS para Puerto Rico (mayo del año indicado). Los grupos son los grupos mayores 11 a 29 del SOC: gerencia; negocios y finanzas; computación y matemáticas; arquitectura e ingeniería; ciencias biológicas, físicas y sociales; servicios comunitarios y sociales; legales; educación; artes, diseño y medios; y profesionales y técnicos de la salud. La lista de ocupaciones detalladas que usó FPR en 2021 no está en el repositorio, y estos grupos dan 29.6 % para mayo de 2019 y 30.2 % para mayo de 2020, no el 32.0 publicado, así que el valor no se compara con él. OEWS cuenta empleos asalariados en establecimientos y excluye a los trabajadores por cuenta propia.")},
    "6.2.1": {"cand": [("fpr_productivity", "")], "kind": "fpr", "note": ("FPR estimate: the three-year average of the growth of real GDP (IMF, calendar years) per person employed (BLS LAUS annual average). The original used fiscal-year GDP of the Junta de Planificación, so the two are not strictly comparable.", "Estimado de FPR: el promedio de tres años del crecimiento del PIB real (FMI, años naturales) por persona empleada (promedio anual de LAUS del BLS). El original usó el PIB por año fiscal de la Junta de Planificación, así que no son estrictamente comparables.")},
    "6.2.2": {"cand": [("wb", "IC.BUS.NDNS.ZS")], "note": ("The World Bank's Entrepreneurship Database, the source GII 2020 used; FPR's original counted corporations in the Departamento de Estado's registry. GII 2026 dropped this indicator.", "La Base de Datos de Emprendimiento del Banco Mundial, la fuente que usó el GII 2020; el original de FPR contó corporaciones en el registro del Departamento de Estado. El GII 2026 eliminó este indicador.")},
}
SOURCE_OF = {"wgi": "wb_wgi", "wb": "wb_wdi", "wb_usa": "wb_wdi", "uis": "unesco_uis", "imf": "imf_weo"}
# Context for the two ICT composites (3.1.1, 3.1.2): the latest value of each component, not a new index value
COMPONENTS = {
    "3.1.1": [("IT.MLT.MAIN.P2", "Fixed telephone subscriptions per 100 people", "Suscripciones de teléfono fijo por cada 100 personas"),
              ("IT.CEL.SETS.P2", "Mobile subscriptions per 100 people", "Suscripciones móviles por cada 100 personas")],
    "3.1.2": [("IT.NET.USER.ZS", "Individuals using the internet, %", "Personas que usan internet, %"),
              ("IT.NET.BBND.P2", "Fixed broadband subscriptions per 100 people", "Suscripciones de banda ancha fija por cada 100 personas")],
}
# GII 2026 comparison: indicators whose Puerto Rico source and definition match. code -> (GII 2026 code, lower is better, how the PR value is taken)
#   "year": PR's value for the year most GII economies use (the WGI revision differs; the IMF year matches), else its latest
#   "avg3": the three-year average ending in that year (GII 2026 uses a three-year average of gross capital formation)
COMPARE = {
    "1.1.2": ("IN.1.1.2", False, "year"), "1.2.1": ("IN.1.2.1", False, "year"), "1.2.2": ("IN.1.2.2", False, "year"),
    "2.1.1": ("IN.2.1.1", False, "latest"), "2.1.3": ("IN.2.1.3", False, "latest"), "2.2.1": ("IN.2.2.1", False, "latest"),
    "2.2.2": ("IN.2.2.2", False, "latest"), "2.2.3": ("IN.2.2.3", False, "latest"), "3.2.3": ("IN.3.2.4", False, "avg3"),
    "4.3.3": ("IN.4.3.3", False, "year"),
}
# Updated indicators with no GII 2026 position, and why (en, es)
NO_POSITION = {
    "2.1.5": ("UIS's teacher series for Puerto Rico changed in 2024 (see the updated value), so the GII's plain pupil-teacher ratio cannot be derived reliably and no position is given.",
              "Las series de maestros del UIS para Puerto Rico cambiaron en 2024 (vea el valor actualizado), así que la razón simple de estudiantes por maestro del GII no se puede derivar con confianza y no se da posición."),
    "3.2.1": ("The GII 2026 takes gross electricity production from the International Energy Agency; the EIA publishes Puerto Rico's net generation, which leaves out what the plants use themselves, so no position is given.",
              "El GII 2026 toma la producción bruta de electricidad de la Agencia Internacional de Energía; la EIA publica la generación neta de Puerto Rico, que excluye lo que consumen las propias plantas, así que no se da posición."),
    "5.1.1": ("The GII 2026 takes this share from the ILO's labor force surveys, which count every employed person by ISCO group; the BLS OEWS counts jobs in establishments by SOC group and leaves out the self-employed, so no position is given.",
              "El GII 2026 toma esta proporción de las encuestas de fuerza laboral de la OIT, que cuentan a toda persona empleada por grupo de la CIUO; OEWS del BLS cuenta empleos en establecimientos por grupo del SOC y excluye a los trabajadores por cuenta propia, así que no se da posición."),
    "4.3.1": ("The GII 2026 uses the WTO's 2024 figure for the United States; the newest open figure FPR can read (World Bank) is for 2022, so no position is given.",
              "El GII 2026 usa la cifra de 2024 de la OMC para los Estados Unidos; la cifra abierta más reciente que FPR puede leer (Banco Mundial) es de 2022, así que no se da posición."),
    "6.2.1": ("The GII 2026 averages labor productivity growth over five years (2021-2025). BLS LAUS has no 2020 annual average for Puerto Rico (March and April 2020 were not published), so the five-year average cannot be built and the three-year FPR estimate is not the GII's definition.",
              "El GII 2026 promedia el crecimiento de la productividad laboral en cinco años (2021-2025). LAUS del BLS no tiene promedio anual de 2020 para Puerto Rico (no se publicaron marzo ni abril de 2020), así que no se puede calcular el promedio de cinco años y el estimado de FPR de tres años no es la definición del GII."),
    "6.2.2": ("The GII 2026 dropped this indicator, so there is no distribution to place Puerto Rico in.",
              "El GII 2026 eliminó este indicador, así que no hay distribución en la cual ubicar a Puerto Rico."),
}
# Updated values that cannot be compared with the printed 2021 value: no change marker ("—"), and why
NOT_COMPARABLE = {"2.1.5": "series", "5.1.1": "method", "6.2.1": "definition", "6.2.2": "definition"}
# Why an indicator is not updated, where the reason in gii_original.json (frozen, written 2026-10-23) is no longer accurate (en, es). For an updated
# indicator the original's reason is dropped from the published texts.
NOT_UPDATED = {
    "6.1.1": ("Not updated: no keyless open source gives patent applications for Puerto Rico. WIPO counts Puerto Rico within the United States. PatentsView's download files moved to the USPTO Open Data Portal, whose API needs a key (it answered HTTP 401 without one on 2026-10-29) and whose download pages run a bot check. The USPTO's state reports of the Patent Technology Monitoring Team, which counted granted patents rather than applications, were no longer at their address on 2026-10-29 (HTTP 404).",
              "No se actualiza: ninguna fuente abierta sin clave da las solicitudes de patentes de Puerto Rico. La OMPI cuenta a Puerto Rico dentro de los Estados Unidos. Los archivos de descarga de PatentsView pasaron al Portal de Datos Abiertos de la USPTO, cuya API requiere una clave (respondió HTTP 401 sin ella el 2026-10-29) y cuyas páginas de descarga aplican una verificación contra robots. Los informes por estado del Patent Technology Monitoring Team de la USPTO, que contaban patentes concedidas y no solicitudes, ya no estaban en su dirección el 2026-10-29 (HTTP 404)."),
}
# A new GII 2026 indicator that FPR estimates from open data (gii_changes.json, new_2026): the GII 2026 code and the note that replaces pr_note
LOW_CARBON = ("IN.3.3.2",
              ("Not in the Energy Institute's review. FPR estimate from the US EIA's international energy data: the share of Puerto Rico's total energy consumption that comes from nuclear, renewable and other non-fossil sources (Puerto Rico has no nuclear power). Like the GII's physical energy content method, the EIA counts wind, solar and hydro electricity at its energy content. The GII uses each economy's total energy supply from the Energy Institute, so no position among the GII 2026 economies is given.",
               "No está en la revisión del Energy Institute. Estimado de FPR con los datos internacionales de energía de la EIA de EE. UU.: la proporción del consumo total de energía de Puerto Rico que viene de fuentes nucleares, renovables y otras no fósiles (Puerto Rico no tiene energía nuclear). Como el método del contenido energético físico del GII, la EIA cuenta la electricidad eólica, solar e hidroeléctrica por su contenido energético. El GII usa el suministro total de energía de cada economía según el Energy Institute, así que no se da una posición entre las economías del GII 2026."))
# The WGI revises every past year in each release, so the printed WGI values (WGI 2019 update, 2018 data, as the GII 2020 used) are compared through the
# current release: its value for 2018 against its latest year. The printed value stays as it is.
WGI_BASE = {"1.1.2": "2018", "1.2.1": "2018", "1.2.2": "2018"}
CHANGE_SHARE = 0.05   # "≈" (no meaningful change) when |updated - 2021| < 5% of the interquartile range of the GII 2026 economies' values


# ── Download and cache ───────────────────────────────────────────────────────

_FETCHED = {}   # name -> what cached() returned in this run

def cached(name, url, refresh, offline, parse, method="get", body=None, headers=UA, raw=False):
    """The parsed response of one request, from cache/gii/<name>.json or the network (4 tries). url may be a function, called only when downloading
    (to find the newest file). raw: parse gets the response's bytes (a zip or a CSV) instead of its JSON; only what parse keeps is cached.
    A run fetches each name once (--refresh would otherwise download INTL.zip, about 24 MB, for 3.2.1 and again for IN.3.3.2)."""
    if name in _FETCHED:
        return _FETCHED[name]
    f = CACHE / f"{name}.json"
    if f.exists() and not refresh:
        _FETCHED[name] = json.loads(f.read_text(encoding="utf-8"))
        return _FETCHED[name]
    if offline:
        raise SystemExit(f"gii --check: {f.name} is not in the cache, so there is nothing to check (python gii.py makes it; --check never downloads)")
    import requests
    if callable(url):
        url = url()
    for attempt in range(4):
        try:
            r = requests.post(url, json=body, headers=headers, timeout=90) if method == "post" else requests.get(url, headers=headers, timeout=90)
            r.raise_for_status()
            out = parse(r.content if raw else r.json())
            break
        except (requests.RequestException, ValueError, KeyError, IndexError, TypeError, zipfile.BadZipFile, ET.ParseError) as e:
            if attempt == 3:
                raise SystemExit(f"gii: {url} failed: {e}")
            time.sleep(4 * (attempt + 1))
    CACHE.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(out, ensure_ascii=False, sort_keys=True, separators=(",", ":")), encoding="utf-8")
    log(f"  {name}: {len(out.get('values') or out.get('major') or {})} values")
    _FETCHED[name] = out
    return out


def wb(series, country="PRI", source=None, refresh=False, offline=False):
    """{years: {year: value}, updated}: one World Bank API series (WDI, or WGI with source=3)."""
    url = f"https://api.worldbank.org/v2/country/{country}/indicator/{series}?format=json&per_page=200" + (f"&source={source}" if source else "")
    def parse(d):
        if len(d) < 2 or d[1] is None:
            return {"values": {}, "updated": d[0].get("lastupdated")}
        return {"values": {x["date"]: x["value"] for x in d[1] if x["value"] is not None}, "updated": d[0].get("lastupdated")}
    return cached(f"wb_{country}_{series}", url, refresh, offline, parse)


def uis(code, refresh=False, offline=False):
    url = f"https://api.uis.unesco.org/api/public/data/indicators?indicator={code}&geoUnit=PRI"
    def parse(d):
        recs = [x for x in d.get("records", []) if x.get("value") is not None]
        return {"values": {str(x["year"]): x["value"] for x in recs}, "qualifier": {str(x["year"]): x["qualifier"] for x in recs if x.get("qualifier")}}
    return cached(f"uis_{code}", url, refresh, offline, parse)


def imf(series, refresh=False, offline=False):
    # The IMF's server refuses requests that carry this project's User-Agent (HTTP 403, 2026-10-23), so this one request goes with the library's default
    url = f"https://www.imf.org/external/datamapper/api/v1/{series}"
    return cached(f"imf_{series}", url, refresh, offline, lambda d: {"values": {k: v for k, v in d["values"][series]["PRI"].items() if v is not None}}, headers=None)


def bls_annual(series, first, last, refresh=False, offline=False):
    """{year: annual average} of a monthly BLS series, from the 12 months of each complete year (API v1 has no annual averages)."""
    url = "https://api.bls.gov/publicAPI/v1/timeseries/data/"
    def parse(d):
        if d.get("status") != "REQUEST_SUCCEEDED":
            raise ValueError(d.get("message"))
        months = {}
        for x in d["Results"]["series"][0]["data"]:
            if x["period"].startswith("M") and x["period"] != "M13" and x["value"].replace(".", "", 1).isdigit():   # "-": not yet published
                months.setdefault(x["year"], []).append(float(x["value"]))
        return {"values": {y: sum(v) / 12 for y, v in months.items() if len(v) == 12}}
    return cached(f"bls_{series}_{first}_{last}", url, refresh, offline, parse, method="post", body={"seriesid": [series], "startyear": str(first), "endyear": str(last)})


def bls_headers():
    """bls.gov refuses requests without a descriptive User-Agent; like freshness.py, add FRESHNESS_CONTACT (an FPR role mailbox) when it is set."""
    contact = os.environ.get("FRESHNESS_CONTACT")
    return {"User-Agent": UA["User-Agent"] + (f" contact: {contact}" if contact else "")}


def parse_intl(data, keep=(EIA_GEN, EIA_ENERGY, EIA_LOWC)):
    """{values: {series: {year: value}}, updated: {series: date}} of the EIA series in keep, from the bytes of INTL.zip (one JSON series per line;
    "--" and other non-numbers are left out)."""
    out = {"values": {}, "updated": {}}
    with zipfile.ZipFile(io.BytesIO(data)) as z, z.open(z.namelist()[0]) as f:
        for line in f:
            if b"-PRI-" not in line:
                continue
            d = json.loads(line)
            if d.get("series_id") in keep:
                out["values"][d["series_id"]] = {str(y): v for y, v in d.get("data", []) if isinstance(v, (int, float))}
                out["updated"][d["series_id"]] = d.get("last_updated")
    missing = set(keep) - set(out["values"])
    if missing:
        raise KeyError(f"not in INTL.zip: {sorted(missing)}")
    return out


def eia_intl(refresh=False, offline=False):
    return cached("eia_INTL_PRI", EIA_INTL, refresh, offline, parse_intl, raw=True)


def parse_pep(data):
    """{values: {year: population on July 1}, vintage} of Puerto Rico (STATE 72) from a Census Bureau NST-EST<vintage>-ALLDATA.csv."""
    import csv
    for row in csv.DictReader(io.StringIO(data.decode("latin-1"))):
        if row.get("STATE") == "72":
            vals = {k[len("POPESTIMATE"):]: int(v) for k, v in row.items() if re.fullmatch(r"POPESTIMATE\d{4}", k or "") and v}
            return {"values": vals, "vintage": max(vals)}
    raise KeyError("Puerto Rico (STATE 72) is not in the file")


def pep_url():
    """The newest Census Bureau state totals file (Vintage <year>), looking back from this year."""
    import requests
    for v in range(date.today().year, date.today().year - 4, -1):
        if requests.head(PEP.format(v=v), headers=UA, timeout=60).status_code == 200:
            return PEP.format(v=v)
    raise SystemExit("gii: no Census Bureau state population file found in the last four vintages")


def census_pep(refresh=False, offline=False):
    return cached("census_pep_PR", pep_url, refresh, offline, parse_pep, raw=True)


def xlsx_rows(data):
    """The rows of the first sheet of an .xlsx (bytes), as lists of cell text, read as a stream with the standard library (the build has no Excel library)."""
    m = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        shared = []
        if "xl/sharedStrings.xml" in z.namelist():
            shared = ["".join(t.text or "" for t in si.iter(m + "t")) for si in ET.fromstring(z.read("xl/sharedStrings.xml")).findall(m + "si")]
        with z.open("xl/worksheets/sheet1.xml") as f:
            for _, el in ET.iterparse(f):
                if el.tag != m + "row":
                    continue
                cells = {}
                for c in el.findall(m + "c"):
                    v = c.find(m + "v")
                    text = ("".join(t.text or "" for t in c.iter(m + "t")) if c.get("t") == "inlineStr" else "" if v is None
                            else shared[int(v.text)] if c.get("t") == "s" else v.text or "")
                    col = 0
                    for ch in re.match(r"[A-Z]+", c.get("r")).group(0):
                        col = col * 26 + ord(ch) - 64
                    cells[col - 1] = text
                el.clear()
                yield [cells.get(i, "") for i in range(max(cells) + 1)] if cells else []


def parse_oews(data):
    """{year, total, major: {SOC major group: employment}} of Puerto Rico (area 72) from a BLS OEWS state file (oesmYYst.zip, one .xlsx). A suppressed
    estimate ("**") is None."""
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        name = next(n for n in z.namelist() if n.lower().endswith(".xlsx"))
        inner = z.read(name)
    year = re.search(r"M(\d{4})", name).group(1)
    rows, ix, out = xlsx_rows(inner), None, {"year": year, "total": None, "major": {}}
    for row in rows:
        if ix is None:
            ix = {h.strip().upper(): i for i, h in enumerate(row)}
            continue
        get = lambda k: row[ix[k]] if ix[k] < len(row) else ""
        if get("AREA").split(".")[0] != "72":
            continue
        try:
            emp = float(get("TOT_EMP"))
        except ValueError:
            emp = None
        if get("OCC_CODE") == "00-0000":
            out["total"] = emp
        elif get("O_GROUP").lower() == "major":
            out["major"][get("OCC_CODE")[:2]] = emp
    if not out["total"] or not out["major"]:
        raise KeyError(f"no Puerto Rico total or major groups in {name}")
    return out


def oews_url():
    """The newest OEWS state file: May of last year, else the year before (BLS publishes it about a year later; it answers 403 for a file that is not there)."""
    import requests
    for y in range(date.today().year - 1, date.today().year - 4, -1):
        r = requests.get(OEWS.format(yy=f"{y % 100:02d}"), headers=bls_headers(), timeout=60, stream=True)
        r.close()
        if r.status_code == 200:
            return OEWS.format(yy=f"{y % 100:02d}")
    raise SystemExit("gii: bls.gov gave no OEWS state file for the last three years (it refuses requests it takes for robots: set FRESHNESS_CONTACT to an FPR role mailbox)")


def oews(refresh=False, offline=False):
    return cached("bls_oews_PR", oews_url, refresh, offline, parse_oews, headers=bls_headers(), raw=True)


def series_of(kind, code, refresh, offline):
    if kind == "wgi":
        return wb(code, source=3, refresh=refresh, offline=offline)
    if kind == "wb":
        return wb(code, refresh=refresh, offline=offline)
    if kind == "wb_usa":
        return wb(code, country="USA", refresh=refresh, offline=offline)
    if kind == "uis":
        return uis(code, refresh, offline)
    if kind == "imf":
        s = imf(code, refresh, offline)
        return {"values": {y: v for y, v in s["values"].items() if int(y) <= LAST_YEAR}}
    raise ValueError(kind)


def productivity(refresh, offline):
    """6.2.1, FPR's method on open data: the mean, over the three latest years both sources have, of (1 + real GDP growth) / (1 + employment growth) - 1, in %."""
    g = series_of("imf", "NGDP_RPCH", refresh, offline)["values"]
    e = bls_annual("LAUST720000000000005", LAST_YEAR - 5, LAST_YEAR, refresh, offline)["values"]
    years = sorted(y for y in g if y in e and str(int(y) - 1) in e)[-3:]
    if len(years) < 3:
        return None
    rates = [((1 + g[y] / 100) / (e[y] / e[str(int(y) - 1)]) - 1) * 100 for y in years]
    return {"value": round(sum(rates) / 3, 2), "year": f"{years[0]}-{years[-1]}", "series": "NGDP_RPCH + LAUST720000000000005", "url": LINK["imf"].format(series="NGDP_RPCH"), "source": "imf_weo+bls_laus"}


def per_million(gen, pop):
    """3.2.1, FPR's method: (year, GWh per million people) for the latest year both have; gen in billion kWh (EIA), pop in people (Census Bureau)."""
    years = [y for y in gen if y in pop and pop[y]]
    if not years:
        return None
    y = max(years, key=int)
    return y, gen[y] * 1000 / (pop[y] / 1e6)


def electricity(refresh, offline):
    """3.2.1 on open data: Puerto Rico's net generation (EIA INTL) per million people (Census Bureau estimate of July 1)."""
    p = census_pep(refresh, offline)
    r = per_million(eia_intl(refresh, offline)["values"][EIA_GEN], p["values"])
    if not r:
        return None
    return {"value": round(r[1], 1), "year": r[0], "series": f"{EIA_GEN} + NST-EST{p['vintage']}", "url": LINK["eia"], "source": "eia_intl+census_pep"}


def knowledge_share(o):
    """5.1.1, FPR's method: the employment of the SOC major groups in ISCO_1_3 as a % of all occupations, or None when one of them is suppressed."""
    emp = [o["major"].get(g) for g in ISCO_1_3]
    if not o.get("total") or any(e is None for e in emp):
        return None
    return 100 * sum(emp) / o["total"]


def knowledge_jobs(refresh, offline):
    o = oews(refresh, offline)
    v = knowledge_share(o)
    if v is None:
        return None
    return {"value": round(v, 2), "year": o["year"], "series": f"oesm{o['year'][2:]}st: SOC {ISCO_1_3[0]}-{ISCO_1_3[-1]} / 00-0000", "url": LINK["oews"], "source": "bls_oews"}


def share_of(part, whole):
    """(year, 100 x part / whole) for the latest year both have, or None."""
    years = [y for y in part if whole.get(y)]
    if not years:
        return None
    y = max(years, key=int)
    return y, 100 * part[y] / whole[y]


def low_carbon(refresh, offline):
    """IN.3.3.2 (new in the GII 2026), FPR estimate: consumption from nuclear, renewables and other as a % of total energy consumption (EIA INTL)."""
    e = eia_intl(refresh, offline)["values"]
    r = share_of(e[EIA_LOWC], e[EIA_ENERGY])
    if not r:
        return None
    return {"value": round(r[1], 2), "year": r[0], "series": f"{EIA_LOWC} / {EIA_ENERGY}", "url": LINK["eia"], "source": "eia_intl"}


FPR_METHODS = {"fpr_productivity": productivity, "fpr_electricity": electricity, "fpr_knowledge_jobs": knowledge_jobs}


def newest(code, refresh, offline):
    """The freshest candidate of an indicator: (value, year, kind, series, its whole series)."""
    best = None
    for kind, series in UPDATES[code]["cand"]:
        if kind in FPR_METHODS:
            return FPR_METHODS[kind](refresh, offline), None
        s = series_of(kind, series, refresh, offline)
        if not s["values"]:
            continue
        y = max(s["values"], key=int)
        if best is None or int(y) > int(best[1]):
            best = (s["values"][y], y, kind, series, s)
    if best is None:
        return None, None
    v, y, kind, series, s = best
    rec = {"value": round(v, 3), "year": y, "series": series, "url": LINK.get(kind, "").format(series=series), "source": SOURCE_OF[kind]}
    if s.get("qualifier", {}).get(y) == "UIS_EST":
        rec["estimate"] = True
    return rec, s["values"]


# ── GII 2026 comparison ──────────────────────────────────────────────────────

def extract_2026():
    """Reads the GII 2026 database with openpyxl (read-only, values only) and keeps, for every indicator: its name, the year most economies use, the
    sorted screened values of the economies that have one (no economy names) and four checks of WIPO's method on its own data: the direction (the sign of
    the rank correlation between value and score), whether the score is the plain min-max of the value (linear), the value range in which the score is
    neither 0 nor 100 (free_lo, free_hi: outside it a value may be winsorized) and how many ranks are 1 + the economies with a strictly higher score.
    Run with python -I and a Python that has openpyxl. The extract stays in cache/gii/2026/ and is never published."""
    import openpyxl
    import hashlib
    raw = G26_XLSX.read_bytes()
    sha_file = hashlib.sha256(raw).hexdigest()
    wb_ = openpyxl.load_workbook(G26_XLSX, read_only=True, data_only=True)
    names = {}
    for row in wb_["Index Structure"].iter_rows(min_row=2, values_only=True):
        if row[2] == "Indicator":
            names[row[0]] = row[1]
    rows, economies = {c: [] for c in names}, set()
    for r in wb_["Data"].iter_rows(min_row=2, values_only=True):
        if r[0]:
            economies.add(r[0])
        if r[2] in names and r[5] is not None and r[6] is not None:
            rows[r[2]].append((float(r[5]), float(r[6]), int(r[7]), int(r[4])))
    wb_.close()
    inds = {}
    for c in sorted(names):
        P = rows[c]
        xs, sc = [p[0] for p in P], [p[1] for p in P]
        rec = {"name": names[c], "year": statistics.mode([p[3] for p in P]) if P else None, "values": sorted(xs)}
        if len(P) >= 3:
            rho = spearman(xs, sc)
            lo, hi = min(xs), max(xs)
            lin = hi > lo and all(abs((100 * (x - lo) / (hi - lo) if rho > 0 else 100 * (hi - x) / (hi - lo)) - y) < 0.001 for x, y in zip(xs, sc))
            free = [x for x, y in zip(xs, sc) if 0 < y < 100]
            z = [gii_log(x, lo, hi) for x in xs] if hi > lo else []
            lg = not lin and bool(z) and max(z) > min(z) and all(abs(100 * (a - min(z)) / (max(z) - min(z)) - y) < 0.001 for a, y in zip(z, sc))
            rec.update({"dir": 1 if rho > 0 else -1, "rho": round(rho, 4), "linear": lin, "log": lg, "free_lo": min(free) if free else None, "free_hi": max(free) if free else None,
                        "rank_rule_ok": sum(1 for p in P if p[2] == 1 + sum(1 for q in P if q[1] > p[1] + 1e-9)), "n": len(P)})
        inds[c] = rec
    same = sha_file == G26_SHA256_WIPO
    out = {"url": G26_URL, "sha256_wipo": G26_SHA256_WIPO, "bytes_wipo": 943159, "sha256_file": sha_file, "bytes_file": len(raw),
           "hash_note": "the file read is WIPO's file, byte for byte" if same else "the file read differs from WIPO's: a folder that SharePoint or OneDrive syncs adds customXml metadata parts to it; on 2026-10-23 its sheets were compared with a fresh download outside that folder (which matched WIPO's hash) and are identical",
           "downloaded": G26_DOWNLOADED, "economies": len(economies), "indicators": inds}
    G26_EXTRACT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"wrote {G26_EXTRACT.name}: {len(inds)} indicators, {len(economies)} economies, {sum(1 for v in inds.values() if v.get('linear'))} plain min-max, "
          f"inverted {[c for c, v in inds.items() if v.get('dir') == -1]}, rank rule true for {sum(1 for v in inds.values() if v.get('rank_rule_ok') == v.get('n'))}; "
          f"file sha256 {sha_file[:16]} ({'WIPO' if same else 'not WIPO'}'s {G26_SHA256_WIPO[:16]})")
    return 0


def gii_log(x, lo, hi):
    """The GII's log transform of a skewed 'good' (GII 2020 Appendix IV; factor f = 1): ln[(max - 1) (x - min) / (max - min) + 1], with the sample's min and max.
    In the GII 2026 database it reproduces the score of exactly 9 indicators, the number WIPO reports as log-transformed."""
    return math.log(max((hi - 1) * (x - lo) / (hi - lo) + 1, 1e-12))


def spearman(xs, ys):
    """Spearman's rank correlation (average ranks for ties)."""
    def ranks(v):
        order = sorted(range(len(v)), key=lambda i: v[i])
        r, i = [0.0] * len(v), 0
        while i < len(order):
            j = i
            while j + 1 < len(order) and v[order[j + 1]] == v[order[i]]:
                j += 1
            for k in range(i, j + 1):
                r[order[k]] = (i + j) / 2
            i = j + 1
        return r
    a, b = ranks(xs), ranks(ys)
    ma, mb = sum(a) / len(a), sum(b) / len(b)
    num = sum((p - ma) * (q - mb) for p, q in zip(a, b))
    den = (sum((p - ma) ** 2 for p in a) * sum((q - mb) ** 2 for q in b)) ** 0.5
    return num / den if den else 0.0


def position(pr, values, lower_better):
    """Where pr would rank among values: 1 + the number of economies that do strictly better (ties share the better place), out of len(values) + 1.
    This is WIPO's own rule: in the GII 2026 database each indicator's rank is 1 + the economies with a strictly higher score (78 of the 79 indicators;
    in 1.1.1 six near-ties differ by two places). Ranking the raw value gives the same place as ranking the 0-100 score, because min-max and the log
    transform keep the order; winsorization can tie the most extreme values, so a position is only given inside the range where no value is capped."""
    better = sum(1 for v in values if (v < pr if lower_better else v > pr))
    return better + 1, len(values) + 1


def compare(code, upd, full, g26):
    """The indicative GII 2026 position of Puerto Rico's updated value for one indicator of COMPARE, or None."""
    if code not in COMPARE or not upd or not g26:
        return None
    c26, lower, how = COMPARE[code]
    ind = g26["indicators"].get(c26)
    if not ind or not ind["values"]:
        return None
    y = str(ind["year"])
    if how == "avg3":
        ys = [str(int(y) - k) for k in range(3)]
        if not all(k in full for k in ys):
            return None
        pr, pr_year = sum(full[k] for k in ys) / 3, f"{ys[-1]}-{ys[0]}"
    elif how == "year" and y in full:
        pr, pr_year = full[y], y
    else:
        pr, pr_year = upd["value"], upd["year"]
    if not ind.get("linear", True) and ind.get("free_lo") is not None and not (ind["free_lo"] <= pr <= ind["free_hi"]):
        return None   # where the GII winsorizes, a value beyond the capped economies has no well-defined place
    x, n = position(pr, ind["values"], lower)
    q1, med, q3 = statistics.quantiles(ind["values"], n=4, method="inclusive")
    return {"c26_code": c26, "c26_year": ind["year"], "c26_n": len(ind["values"]), "c26_pos": x, "c26_of": n, "c26_pr_value": round(pr, 3), "c26_pr_year": pr_year,
            "c26_q1": round(q1, 3), "c26_median": round(med, 3), "c26_q3": round(q3, 3), "c26_lower_better": lower}


def change(r, g26, c26, full=None):
    """The change marker of an updated value against the printed 2021 value, in the GII's direction: better, worse, same (|change| below the threshold) or
    na (not comparable), with the threshold: CHANGE_SHARE (5%) of the interquartile range of the GII 2026 economies' values for the matching indicator.
    For the WGI (WGI_BASE) the base is the current release's value for the printed value's data year, so both years come from one release."""
    if r.get("upd_value") is None:
        return None
    if r.get("value") is None:
        return {"chg": "na", "chg_why": "no_2021"}
    if r["code"] in NOT_COMPARABLE:
        return {"chg": "na", "chg_why": NOT_COMPARABLE[r["code"]]}
    base, base_year = r["value"], None
    if r["code"] in WGI_BASE:
        base_year = WGI_BASE[r["code"]]
        if base_year not in (full or {}):
            return {"chg": "na", "chg_why": "no_base"}
        base = full[base_year]
    ind = (g26 or {}).get("indicators", {}).get(c26 or "")
    if not ind or len(ind["values"]) < 4:
        return {"chg": "na", "chg_why": "no_threshold"}
    vals, a, b = ind["values"], base, r["upd_value"]
    if ind.get("log"):   # the GII log-transforms this indicator: measure the change on its scale
        lo, hi = vals[0], vals[-1]
        vals, a, b = [gii_log(v, lo, hi) for v in vals], gii_log(a, lo, hi), gii_log(b, lo, hi)
    q1, _, q3 = statistics.quantiles(vals, n=4, method="inclusive")
    thr = CHANGE_SHARE * (q3 - q1)
    d = b - a
    out = {"chg_delta": round(r["upd_value"] - base, 3), "chg_thr": round(thr, 4)}
    if base_year:
        out.update({"chg_base": round(base, 3), "chg_base_year": base_year})
    if ind.get("log"):
        out["chg_log"] = True
    if abs(d) < thr:
        out["chg"] = "same"
    else:
        out["chg"] = "better" if d * r["dir"] > 0 else "worse"
    return out


# ── Build ────────────────────────────────────────────────────────────────────

def compute(refresh=False, offline=False):
    orig = json.loads(ORIGINAL.read_text(encoding="utf-8"))
    cw = json.loads(CROSSWALK.read_text(encoding="utf-8"))
    g26 = json.loads(G26_EXTRACT.read_text(encoding="utf-8")) if G26_EXTRACT.exists() else None
    rows, texts = [], {}
    for o in orig["indicators"]:
        code = o["code"]
        r = {k: o[k] for k in ("code", "pillar", "sub", "value", "shown", "rank", "rank_printed_of", "rank_n", "star", "hourglass", "year",
                               "composite", "survey", "higher_is_worse", "gii2026")}
        r["proprietary"] = bool(o["proprietary"])
        r["dir"] = -1 if o["higher_is_worse"] else 1
        x = cw["crosswalk"][code]
        r["c26_status"] = x["status"]
        if x["c26"]:
            r["c26_full"] = x["c26"]
        t = {k: o[k] for k in ("name", "source_printed", "definition", "method", "note", "not_updated") if o.get(k)}
        if x.get("note"):
            t["c26_note"] = x["note"]
        if o["proprietary"]:
            t["proprietary"] = o["proprietary"]
        if code in NOT_UPDATED:
            t["not_updated"] = {"en": NOT_UPDATED[code][0], "es": NOT_UPDATED[code][1]}
        if code in UPDATES:
            t.pop("not_updated", None)   # the original's reason (2026-10-23) no longer applies
            upd, full = newest(code, refresh, offline)
            if upd:
                r.update({"upd_value": upd["value"], "upd_year": upd["year"], "upd_kind": UPDATES[code].get("kind", "official"), "upd_source": upd["source"],
                          "upd_series": upd["series"], "upd_url": upd["url"]})
                if upd.get("estimate"):
                    r["upd_estimate"] = True
                if UPDATES[code]["note"]:
                    t["upd_note"] = {"en": UPDATES[code]["note"][0], "es": UPDATES[code]["note"][1]}
                c = compare(code, upd, full or {}, g26)
                if c:
                    r.update(c)
                elif code in NO_POSITION:
                    t["c26_why"] = {"en": NO_POSITION[code][0], "es": NO_POSITION[code][1]}
                r.update(change(r, g26, x["c26"], full) or {})
        if code in COMPONENTS:
            comp = []
            for series, en, es in COMPONENTS[code]:
                s = series_of("wb", series, refresh, offline)["values"]
                if s:
                    y = max(s, key=int)
                    comp.append({"series": series, "value": round(s[y], 1), "year": y})
                    t.setdefault("components", {})[series] = {"en": en, "es": es}
            r["components"] = comp
        rows.append(r)
        texts[code] = t
    n_upd = sum(1 for r in rows if "upd_value" in r)
    n_cmp = sum(1 for r in rows if "c26_pos" in r)
    changes = {"checked": cw["checked"], "sources": cw["sources"], "editions": cw["editions"], "method": cw["method"],
               "crosswalk": [{"code": c, "c26": v["c26"], "status": v["status"]} for c, v in cw["crosswalk"].items()], "new_2026": cw["new_2026"]}
    est_sources = set()
    for e in changes["new_2026"]:
        e["n"] = len(((g26 or {}).get("indicators", {}).get(e["c26"]) or {}).get("values", [])) or None
        if e["c26"] == LOW_CARBON[0]:
            est = low_carbon(refresh, offline)
            if est:   # an FPR estimate replaces "an FPR estimate is possible"
                e.update({"pr": "fpr", "pr_note": {"en": LOW_CARBON[1][0], "es": LOW_CARBON[1][1]}, "pr_est": est})
                est_sources.add(est["source"])
    used = sorted({s for r in rows for s in r.get("upd_source", "").split("+") if s} | est_sources | ({"wipo_gii2026"} if n_cmp else set()))
    about = {"profile": orig["profile"], "updated_count": n_upd, "compared_count": n_cmp, "change_share": CHANGE_SHARE,
             "status_count": {k: sum(1 for r in rows if r["c26_status"] == k) for k in ("same", "renamed", "redefined", "dropped")}, "new_2026": len(cw["new_2026"]),
             "gii2026": {k: g26[k] for k in ("url", "sha256_wipo", "sha256_file", "hash_note", "downloaded", "economies")} if g26 else None}
    return {"about": about, "pillars": orig["pillars"], "sources": {k: SOURCES[k] for k in used}, "indicators": rows, "texts": texts}, changes


def build(refresh=False, check=False):
    out, changes = compute(refresh, offline=check)
    files = {OUT: {"built": date.today().isoformat(), **out}, OUT_CHANGES: changes}
    texts = {f: json.dumps(v, ensure_ascii=False, separators=(",", ":")) for f, v in files.items()}
    if check:
        bad = []
        for f, text in texts.items():
            old = json.loads(f.read_text(encoding="utf-8")) if f.exists() else None
            if old is None or {**old, "built": None} != {**json.loads(text), "built": None}:
                bad.append(f.name)
        if bad:
            print(f"{', '.join(bad)}: not what the cache gives; run python gii.py")
            return 1
        print("gii_profile.json and gii_changes.json match the cache")
        return 0
    for f, text in texts.items():
        f.write_text(text, encoding="utf-8")
    log(f"wrote {OUT.name}: {len(out['indicators'])} indicators, {out['about']['updated_count']} updated, {out['about']['compared_count']} compared with GII 2026, "
        f"{OUT.stat().st_size / 1024:.1f} KB; {OUT_CHANGES.name}, {OUT_CHANGES.stat().st_size / 1024:.1f} KB")
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if "--extract-2026" in sys.argv:
        raise SystemExit(extract_2026())
    raise SystemExit(build("--refresh" in sys.argv, "--check" in sys.argv))
