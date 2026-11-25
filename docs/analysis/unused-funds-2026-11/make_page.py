"""Writes the Knowledge Area page "Federal funds returned and unused" (site/unused-funds.html) and its Spanish (i18n_src/es/unused_funds.json).

  python docs/analysis/unused-funds-2026-11/make_page.py   read site/data/unused_funds.json (python unused_funds.py makes it); write the page and its
                                                           Spanish. Then run python i18n.py.

HANDOFF decision 110. Step 1: federal grants that have ended with an unpaid balance, by federal agency and by program (site/data/unused_funds.json).
Step 2: money taken back, the net reduction of each grant (site/data/taken_back.json, python taken_back.py).
Step 3: audit findings that repeat (site/data/audit_findings.json, python audit_findings.py). The page follows the site's
language rule (docs/i18n.md) and the pattern of the Broadband gaps page (docs/analysis/broadband-2026-11/make_page.py): every string is written once,
as an (English, Spanish) pair, and every figure is read from the data file. The page has no script of its own: its tables are written here.
It covers every federal grant program and singles none out; it names no recipient; it states amounts, dates and rules and draws no conclusion
about any agency. Prepared with Claude (AI) for FPR, 2026-11-18.
"""
import html
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
ES = {}
TOP = 25   # programs shown before the fold

AGENCY_ES = {
    "Department of Health and Human Services": "Departamento de Salud y Servicios Humanos",
    "Department of Education": "Departamento de Educación federal",
    "Environmental Protection Agency": "Agencia de Protección Ambiental",
    "Department of Labor": "Departamento del Trabajo federal",
    "Department of Agriculture": "Departamento de Agricultura federal",
    "Department of Commerce": "Departamento de Comercio federal",
    "Department of Homeland Security": "Departamento de Seguridad Nacional",
    "Department of Justice": "Departamento de Justicia federal",
    "National Science Foundation": "Fundación Nacional de Ciencias",
    "Department of Transportation": "Departamento de Transportación federal",
    "National Endowment for the Humanities": "Fundación Nacional para las Humanidades",
    "Department of Defense": "Departamento de Defensa",
    "Department of Housing and Urban Development": "Departamento de Vivienda y Desarrollo Urbano federal",
    "Corporation for National and Community Service": "Corporación para el Servicio Nacional y Comunitario",
    "Small Business Administration": "Administración de Pequeños Negocios",
    "National Aeronautics and Space Administration": "Administración Nacional de Aeronáutica y el Espacio",
    "Department of the Interior": "Departamento del Interior",
    "Department of Energy": "Departamento de Energía",
    "Department of the Treasury": "Departamento del Tesoro",
    "Department of State": "Departamento de Estado federal",
    "Department of Veterans Affairs": "Departamento de Asuntos de Veteranos",
    "National Endowment for the Arts": "Fundación Nacional para las Artes",
    "Institute of Museum and Library Services": "Instituto de Servicios de Museos y Bibliotecas",
    "Election Assistance Commission": "Comisión de Asistencia Electoral",
    "Social Security Administration": "Administración del Seguro Social",
    "Federal Communications Commission": "Comisión Federal de Comunicaciones",
    "Nuclear Regulatory Commission": "Comisión Reguladora Nuclear",
    "National Archives and Records Administration": "Administración Nacional de Archivos y Registros",
    "Agency for International Development": "Agencia para el Desarrollo Internacional",
    "Appalachian Regional Commission": "Comisión Regional de los Apalaches",
    "Library of Congress": "Biblioteca del Congreso",
    "Other federal agencies": "Otras agencias federales",
    "Not stated": "No indicada",
}


def t(en, es):
    key = " ".join(en.split())
    if key in ES and ES[key] != " ".join(es.split()):
        raise SystemExit(f"two Spanish texts for {key!r}")
    ES[key] = " ".join(es.split())
    return html.escape(key, quote=False)


def num(v, d=0):
    return f"{v:,.{d}f}"


def mil(v):
    """Millions of dollars with one decimal."""
    return f"{v / 1e6:,.1f}"


def bn(v):
    return f"{v / 1e9:.2f}"


def skip(text, cls="num"):
    return f'<td class="{cls}" data-t="skip">{html.escape(str(text), quote=False)}</td>'


def bar(v, top):
    return f'<td class="uf-barcell" data-t="skip"><span class="uf-bar" style="width:{max(1, round(100 * v / top))}%"></span></td>'


def agency(name):
    if name not in AGENCY_ES:
        raise SystemExit(f"no Spanish name for the federal agency {name!r}: add it to AGENCY_ES")
    return t(name, AGENCY_ES[name])


def build():
    D = json.loads((ROOT / "site" / "data" / "unused_funds.json").read_text(encoding="utf-8"))
    T = D["totals"]
    STEP1_APART = {
        "medicaid": (t("Medicaid", "Medicaid"),
                     t("Its ended grants show billions unpaid, mostly in grants that ended in 2020 and 2021. That is more likely a gap in what USAspending reports as paid for this program than money that was not paid: USAspending has payments only from fiscal year 2020.", "Sus subvenciones vencidas muestran miles de millones sin pagar, casi todo en subvenciones que vencieron en 2020 y 2021. Es más probable que sea un vacío en lo que USAspending informa como pagado en este programa que dinero que no se pagó: USAspending tiene pagos solo desde el año fiscal 2020.")),
        "carryover": (t("TANF (Temporary Assistance for Needy Families)", "TANF (Asistencia Temporal para Familias Necesitadas)"),
                      t("A State or territory may carry its unspent TANF money forward to later years, with no deadline. A balance after a grant's end date is not money left behind.", "Un estado o territorio puede arrastrar a años posteriores el dinero de TANF que no ha gastado, sin fecha límite. Un saldo después de la fecha de cierre de la subvención no es dinero que se quedó atrás.")),
        "federal": (t("Programs the federal government ended", "Programas que el gobierno federal terminó"),
                    t("The Environmental Protection Agency terminated Solar for All on August 7, 2025, and canceled the Community Change Grants in 2025. Their balances come from a federal decision, not from how the grants were carried out in Puerto Rico.", "La Agencia de Protección Ambiental terminó Solar for All el 7 de agosto de 2025 y canceló las Community Change Grants en 2025. Sus saldos vienen de una decisión federal, no de cómo se ejecutaron las subvenciones en Puerto Rico.")),
    }
    if set(D["apart"]) != set(STEP1_APART):
        raise SystemExit("the groups shown apart in step 1 changed: update STEP1_APART")
    apart_rows = "\n".join(f'        <tr class="uf-apart"><th scope="row">{STEP1_APART[g][0]}</th><td>{STEP1_APART[g][1]}</td>{skip(num(v["with_balance"]))}{skip(mil(v["with_balance_unpaid"]))}</tr>' for g, v in D["apart"].items())
    apart_usd = sum(v["with_balance_unpaid"] for v in D["apart"].values())
    NOTE_TXT = {"84.010": t("† Title I: under the Tydings Amendment the money stays available for 27 months, and the Department of Education can extend the time to pay it out. Part of this balance may still be paid.", "† Title I: por la Enmienda Tydings el dinero sigue disponible por 27 meses, y el Departamento de Educación federal puede extender el tiempo para desembolsarlo. Parte de este saldo todavía puede pagarse.")}
    if set(D["notes"]) - set(NOTE_TXT):
        raise SystemExit("a program has a note without page text: update NOTE_TXT")
    notes_html = "\n".join(f'    <p class="pm-small">{NOTE_TXT[c]}</p>' for c in D["notes"])
    blank_rows = "\n".join(f'        <tr class="uf-blank"><th scope="row">{agency(a)}</th>{skip(num(n))}{skip(mil(o))}</tr>' for a, n, o in D["no_outlay"])
    y0, y1 = D["years"][0], D["years"][-1]
    read = D["read"]
    months_en = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
    months_es = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
    ry, rm, rd = (int(x) for x in read.split("-"))
    read_en, read_es = f"{months_en[rm - 1]} {rd}, {ry}", f"{rd} de {months_es[rm - 1]} de {ry}"
    by, bm, bd = (int(x) for x in D["ended_before"].split("-"))
    before_en, before_es = f"{months_en[bm - 1]} {bd}, {by}", f"{bd} de {months_es[bm - 1]} de {by}"
    n_prog = len({r[0] for r in D["listings"]})
    n_ag = len(D["agencies"])
    share = round(100 * T["with_balance_unpaid"] / T["with_balance_obligated"])
    top_ag = D["agencies"][0][3]
    top_li = D["listings"][0][5]
    top_y = max(r[2] for r in D["end_years"])

    ag_rows = "\n".join(
        f'        <tr><th scope="row">{agency(a)}</th>{skip(num(n))}{skip(mil(o))}{skip(mil(u))}{bar(u, top_ag)}</tr>' for a, n, o, u in D["agencies"])

    def li_row(r):
        code, name, ag, n, o, u = r
        return (f'        <tr>{skip(code, "uf-code")}<th scope="row" data-t="skip" lang="en">{html.escape(name or code, quote=False)}{" †" if code in D["notes"] else ""}</th><td>{agency(ag)}</td>'
                f'{skip(num(n))}{skip(mil(o))}{skip(mil(u))}{bar(u, top_li)}</tr>')

    li_top = "\n".join(li_row(r) for r in D["listings"][:TOP])
    li_rest = "\n".join(li_row(r) for r in D["listings"][TOP:])
    rest_n = len(D["listings"]) - TOP
    rest_usd = sum(r[5] for r in D["listings"][TOP:])
    ey_rows = "\n".join(f'        <tr><th scope="row" data-t="skip">{y}</th>{skip(num(n))}{skip(mil(u))}{bar(u, top_y)}</tr>' for y, n, u in D["end_years"])

    B = json.loads((ROOT / "site" / "data" / "taken_back.json").read_text(encoding="utf-8"))
    BT, BC = B["totals"], B["read_counts"]
    b0, b1 = B["years"][0], B["years"][-1]
    tb_top_ag, tb_top_li = B["agencies"][0][2], B["listings"][0][4]
    tb_top_y = max(r[2] for r in B["by_year"])
    tb_ag_rows = "\n".join(f'        <tr class="tb-ag"><th scope="row">{agency(a)}</th>{skip(num(n))}{skip(mil(v))}{bar(v, tb_top_ag)}</tr>' for a, n, v in B["agencies"])

    def tb_row(r):
        code, name, ag, n, v, _comb = r
        return (f'        <tr>{skip(code, "tb-code")}<th scope="row" data-t="skip" lang="en">{html.escape(name or code, quote=False)}</th><td>{agency(ag)}</td>'
                f'{skip(num(n))}{skip(mil(v))}{bar(v, tb_top_li)}</tr>')

    tb_top = "\n".join(tb_row(r) for r in B["listings"][:TOP])
    tb_rest = "\n".join(tb_row(r) for r in B["listings"][TOP:])
    tb_rest_n = len(B["listings"]) - TOP
    tb_rest_usd = sum(r[4] for r in B["listings"][TOP:])
    tb_y_rows = "\n".join(f'        <tr><th scope="row" data-t="skip">{y}</th>{skip(num(n))}{skip(mil(v))}{bar(v, tb_top_y)}</tr>' for y, n, v in B["by_year"])
    APART_TXT = {
        "estimates": (t("Programs paid by actual cost", "Programas que se pagan por el costo real"),
                      t("These programs pay a share of whatever the costs turn out to be, so each grant is an estimate that is lowered or raised to the actual costs. Medicaid is the largest.", "Estos programas pagan una parte de lo que resulten ser los costos, así que cada subvención es un estimado que se baja o se sube al costo real. Medicaid es el mayor.")),
        "highways": (t("Highway projects", "Proyectos de carreteras"),
                     t("Money released when a highway project closes goes back to the highway balance of Puerto Rico and can be used on another project.", "El dinero que se libera cuando cierra un proyecto de carreteras vuelve al balance de carreteras de Puerto Rico y se puede usar en otro proyecto.")),
        "federal": (t("Money the federal government withdrew by its own decision", "Dinero que el gobierno federal retiró por decisión propia"),
                    t("In 2025 the Department of Energy redirected the solar funds of the Puerto Rico Energy Resilience Fund ($365 million, in three transactions of May 21, 2025), and the Environmental Protection Agency terminated Solar for All and canceled the Community Change Grants.", "En 2025 el Departamento de Energía redirigió los fondos de energía solar del Fondo de Resiliencia Energética de Puerto Rico ($365 millones, en tres transacciones del 21 de mayo de 2025), y la Agencia de Protección Ambiental terminó Solar for All y canceló las Community Change Grants.")),
        "disaster": (t("Disaster programs", "Programas de desastres"),
                     t("Their projects are re-versioned many times. The Budget and public spending page counts FEMA Public Assistance project by project.", "Sus proyectos se revisan muchas veces. La página de Presupuesto y gasto público cuenta la Asistencia Pública de FEMA proyecto por proyecto.")),
    }
    if set(B["apart"]) != set(APART_TXT):
        raise SystemExit("the groups shown apart changed: update APART_TXT")
    tb_apart_rows = "\n".join(f'        <tr class="tb-apart"><th scope="row">{APART_TXT[g][0]}</th><td>{APART_TXT[g][1]}</td>{skip(num(v["awards"]))}{skip(mil(v["net"]))}</tr>' for g, v in B["apart"].items())
    tb_apart_usd = sum(v["net"] for v in B["apart"].values())
    h_net = (t("Net reduction ($ millions)", "Reducción neta (millones de $)"), ' class="num"')
    h_bar2 = (f'<span class="sr-only">{t("Net reduction, as a bar", "Reducción neta, en barra")}</span>', "")

    A = json.loads((ROOT / "site" / "data" / "audit_findings.json").read_text(encoding="utf-8"))
    a0 = A["years"][0]
    a_done = int(A["read"][:4]) - 2   # the latest audit year whose audits have mostly arrived
    done = [r for r in A["by_year"] if r[0] <= a_done]
    af_audits, af_with, af_find, af_rep = (sum(r[k] for r in done) for k in (1, 2, 3, 4))
    af_late = sum(r[7] for r in done)
    af_share = round(100 * af_rep / af_find)
    af_lo, af_hi = min(round(100 * r[4] / r[3]) for r in done), max(round(100 * r[4] / r[3]) for r in done)
    pct = lambda a, b: f"{round(100 * a / b)}%" if b else ""

    def af_year(r):
        y, n, w, f, rp, mw, qc, late, med, _usd = r
        mark = "" if y <= a_done else " *"
        return (f'        <tr class="af-y"><th scope="row" data-t="skip">{y}{mark}</th>{skip(num(n))}{skip(num(w))}{skip(num(f))}{skip(num(rp))}{skip(pct(rp, f))}{skip(num(mw))}{skip(num(qc))}'
                f'{skip(num(late))}{skip("" if med is None else f"{med:.1f}")}</tr>')

    af_y_rows = "\n".join(af_year(r) for r in A["by_year"] if r[1])
    KIND_TXT = {"state": t("Commonwealth government bodies", "Entidades del Gobierno de Puerto Rico"), "local": t("Municipios and other local bodies", "Municipios y otras entidades locales"),
                "higher_ed": t("Colleges and universities", "Colegios y universidades"), "nonprofit": t("Nonprofit organizations", "Organizaciones sin fines de lucro"),
                "other": t("Other bodies", "Otras entidades")}
    af_k_rows = "\n".join(f'        <tr class="af-k"><th scope="row">{KIND_TXT[k]}</th>{skip(num(v["audits"]))}{skip(num(v["tally"][0]))}{skip(num(v["tally"][1]))}{skip(pct(v["tally"][1], v["tally"][0]))}{skip(num(v["tally"][2]))}{skip(num(v["tally"][3]))}</tr>'
                           for k, v in sorted(A["kinds"].items(), key=lambda kv: -kv[1]["tally"][0]))
    af_a_rows = "\n".join(f'        <tr class="af-ag"><th scope="row">{agency(a)}</th>{skip(num(f))}{skip(num(rp))}{skip(pct(rp, f))}{skip(num(mw))}{skip(num(qc))}</tr>' for a, f, rp, mw, qc in A["agencies"])

    def af_row(r):
        code, name, ag, f, rp, mw, qc = r
        return (f'        <tr>{skip(code, "af-code")}<th scope="row" data-t="skip" lang="en">{html.escape(name or code, quote=False)}</th><td>{agency(ag)}</td>'
                f'{skip(num(f))}{skip(num(rp))}{skip(pct(rp, f))}{skip(num(mw))}{skip(num(qc))}</tr>')

    af_top = "\n".join(af_row(r) for r in A["listings"][:TOP])
    af_rest = "\n".join(af_row(r) for r in A["listings"][TOP:])
    af_rest_n = len(A["listings"]) - TOP
    h_find = (t("Findings", "Hallazgos"), ' class="num"')
    h_rep = (t("Repeated", "Repetidos"), ' class="num"')
    h_share = (t("Share repeated", "Parte repetida"), ' class="num"')
    h_mw = (t("Material weakness", "Debilidad material"), ' class="num"')
    h_qc = (t("With questioned costs", "Con costos cuestionados"), ' class="num"')

    def head(*cols):
        return "<thead><tr>" + "".join(f'<th scope="col"{c[1]}>{c[0]}</th>' for c in cols) + "</tr></thead>"

    N = ' class="num"'
    h_awards = (t("Grants", "Subvenciones"), N)
    h_obl = (t("Obligated ($ millions)", "Obligado (millones de $)"), N)
    h_unp = (t("Unpaid ($ millions)", "Sin pagar (millones de $)"), N)
    h_bar = (f'<span class="sr-only">{t("Unpaid, as a bar", "Sin pagar, en barra")}</span>', "")

    # ── Five grants rebuilt (decision 112, step 4; decision 111 (d)): awards_rebuilt.json beside this file, from rebuild_awards.py ──
    RB = json.loads((HERE / "awards_rebuilt.json").read_text(encoding="utf-8"))

    def day(iso):
        y, m, d = (int(x) for x in iso.split("-"))
        return f"{months_en[m - 1]} {d}, {y}", f"{d} de {months_es[m - 1]} de {y}"

    RB_NAME = {
        "17.258/17.259/17.278": t("WIOA: adult, youth and dislocated worker programs (one combined grant)", "WIOA: programas de adultos, jóvenes y trabajadores desplazados (una subvención combinada)"),
        "93.767": t("Children's Health Insurance Program (CHIP)", "Programa de Seguro Médico para Niños (CHIP)"),
        "84.425": t("Education Stabilization Fund (pandemic relief for schools)", "Fondo de Estabilización Educativa (alivio por la pandemia para las escuelas)"),
        "84.010": t("Title I grants to local educational agencies", "Subvenciones del Título I a agencias educativas locales"),
        "84.287": t("Twenty-First Century Community Learning Centers", "Centros Comunitarios de Aprendizaje del Siglo XXI"),
    }

    def rb_note(g):
        """What the record shows for one grant, in words. Each text holds only while the record reads as it did; the checks stop the build when it changes."""
        k, yrs, efy = "/".join(g["listings"]), g["paid_by_year"], g["end_fiscal_year"]
        paid_years = [y[0] for y in yrs if y[2]]
        share_after = round(100 * g["paid_after_end_year"] / g["paid"]) if g["paid"] > 0 else 0
        if k == "17.258/17.259/17.278":
            assert max(paid_years) < efy - 1 and g["last_period"][0] < efy, g
            return t(f"The record shows payments in fiscal years {paid_years[0]} and {paid_years[-1]} and none after, although the grant ran until fiscal year {efy}. After fiscal year {g['last_period'][0]} the grant is no longer in the account reports the federal agency files. The record does not say why, so the balance cannot be read as money not paid.",
                     f"El registro muestra pagos en los años fiscales {paid_years[0]} y {paid_years[-1]} y ninguno después, aunque la subvención duró hasta el año fiscal {efy}. Después del año fiscal {g['last_period'][0]} la subvención ya no está en los informes de cuentas que presenta la agencia federal. El registro no dice por qué, así que el saldo no se puede leer como dinero sin pagar.")
        if k == "93.767":
            cut = min(c for c in g["changes"] if c[2] < 0)
            assert min(paid_years) > efy and cut[0] > g["end"], g
            return t(f"The amount committed was lowered by ${mil(-cut[2])} million on {day(cut[0])[0]}, after the end date. Payments are on record only from fiscal year {min(paid_years)}: none for fiscal years {fiscal(g['start'])} and {efy}, the years of the grant. For this grant the record of payments begins after the grant's own period.",
                     f"El monto comprometido se redujo en ${mil(-cut[2])} millones el {day(cut[0])[1]}, después de la fecha de fin. Solo hay pagos en el registro desde el año fiscal {min(paid_years)}: ninguno en los años fiscales {fiscal(g['start'])} y {efy}, los de la subvención. En esta subvención el registro de pagos empieza después del período de la propia subvención.")
        if k == "84.425":
            assert share_after > 50 and g["record_changed"] < g["end"], g
            return t(f"${mil(g['paid_after_end_year'])} million, {share_after}% of everything paid, was paid in the fiscal years after the end date on record. That end date was last changed on {day(g['record_changed'])[0]}: the record shows no later end date, and payments went on for three more fiscal years.",
                     f"${mil(g['paid_after_end_year'])} millones, el {share_after} % de todo lo pagado, se pagaron en los años fiscales posteriores a la fecha de fin del registro. Esa fecha de fin se cambió por última vez el {day(g['record_changed'])[1]}: el registro no muestra una fecha de fin posterior, y los pagos siguieron tres años fiscales más.")
        if k == "84.010":
            assert share_after > 50 and yrs[-1][2] > 0 and yrs[-1][0] > fiscal(g['start']) + 2, g   # the last year paid is after the 27 months
            return t(f"{share_after}% of everything paid was paid after the fiscal year of the end date. The law of this program keeps the money available for 27 months, longer than the end date on record. Payments went on after those 27 months too: ${mil(yrs[-1][2])} million in fiscal year {yrs[-1][0]}. The record does not say under what rule, and the balance was still going down when the data were read.",
                     f"El {share_after} % de todo lo pagado se pagó después del año fiscal de la fecha de fin. La ley de este programa mantiene el dinero disponible 27 meses, más que la fecha de fin del registro. Los pagos siguieron también después de esos 27 meses: ${mil(yrs[-1][2])} millones en el año fiscal {yrs[-1][0]}. El registro no dice bajo qué regla, y el saldo todavía bajaba cuando se leyeron los datos.")
        if k == "84.287":
            up = sum(y[2] for y in yrs if y[2] > 0)
            assert yrs[-1][2] < 0 and g["paid"] < 0.05 * g["obligated"], g
            return t(f"Payments of ${mil(up)} million through fiscal year {yrs[-2][0]} were followed in fiscal year {yrs[-1][0]} by corrections that lowered the total by ${mil(-yrs[-1][2])} million. A total that goes down means earlier payments were reversed or corrected; the record does not say which.",
                     f"A pagos de ${mil(up)} millones hasta el año fiscal {yrs[-2][0]} les siguieron en el año fiscal {yrs[-1][0]} correcciones que bajaron el total en ${mil(-yrs[-1][2])} millones. Un total que baja significa que pagos anteriores se revirtieron o se corrigieron; el registro no dice cuál de las dos.")
        raise SystemExit(f"no text for the rebuilt grant {k}: write one in rb_note")

    def fiscal(iso):
        return int(iso[:4]) + (1 if iso[5:7] >= "10" else 0)

    rb_cards = []
    for g in RB["grants"]:
        k = "/".join(g["listings"])
        share = round(100 * g["paid"] / g["obligated"])
        rows = "".join(f'<tr><th scope="row" data-t="skip">{y[0]}</th>{skip(mil(y[2]))}<td>{t("after the year of the end date", "después del año de la fecha de fin") if y[0] > g["end_fiscal_year"] else ""}</td></tr>' for y in g["paid_by_year"] if y[2])
        ch = "".join(f'<tr><th scope="row" data-t="skip">{c[0]}</th>{skip(mil(c[2]))}</tr>' for c in g["changes"] if c[2])
        rb_cards.append(f"""    <div class="card uf-rb">
      <h3 class="uf-h3">{RB_NAME[k]}</h3>
      <p class="pm-small"><span data-t="skip">{k}</span> · <span>{agency(g["agency"])}</span></p>
      <p class="pm-p">{t(f"Signed on {day(g['signed'])[0]}. Period on record: {day(g['start'])[0]} to {day(g['end'])[0]}. Committed: ${mil(g['obligated'])} million. Paid out on record: ${mil(g['paid'])} million ({share}%).",
                         f"Firmada el {day(g['signed'])[1]}. Período en el registro: del {day(g['start'])[1]} al {day(g['end'])[1]}. Comprometido: ${mil(g['obligated'])} millones. Desembolsado en el registro: ${mil(g['paid'])} millones ({share} %).")}</p>
      <p class="pm-p">{rb_note(g)}</p>
      <div class="pm-tablebox uf-all"><table class="pm-table uf-table">
        <caption>{t("Paid out, by federal fiscal year", "Desembolsado, por año fiscal federal")}</caption>
        {head((t("Fiscal year", "Año fiscal"), ""), (t("Paid out ($ millions)", "Desembolsado (millones de $)"), N), ("", ""))}
        <tbody>{rows}</tbody>
      </table></div>
      <details class="uf-more"><summary>{t("See each change of the amount committed", "Ver cada cambio del monto comprometido")}</summary>
      <div class="pm-tablebox uf-all"><table class="pm-table uf-table">
        <caption>{t("Changes of the amount committed, by day", "Cambios del monto comprometido, por día")}</caption>
        {head((t("Date", "Fecha"), ""), (t("Change ($ millions)", "Cambio (millones de $)"), N))}
        <tbody>{ch}</tbody>
      </table></div></details>
    </div>""")
    rb_cards = "\n".join(rb_cards)
    rb_read_en, rb_read_es = day(RB["read"])
    rb_n = len(RB["grants"])
    rb_late = sum(1 for g in RB["grants"] if g["paid"] > 0 and g["paid_after_end_year"] > 0.5 * g["paid"])
    assert rb_n == 5 and rb_late == 3, (rb_n, rb_late)

    ref = (ROOT / "site" / "broadband.html").read_text(encoding="utf-8")
    ver = lambda name: re.search(re.escape(name) + r"\?v=(\d+)", ref).group(1)
    I18N_V = 67   # the ?v= of js/i18n.js also versions this page's Spanish bundle: raise it when the page's strings change (docs/i18n.md, rule 12)
    icons = sorted(set(re.search(r"icon_names=([a-z0-9_,]+)", ref).group(1).split(",")) | {"school", "hourglass_bottom", "account_balance", "category", "event", "call_split", "help", "info", "menu_book", "undo", "fact_check", "account_tree", "dark_mode", "explore", "grid_view", "light_mode"})
    title = t("Knowledge Area · Federal grants: balances, reductions and audit findings", "Área de conocimiento · Subvenciones federales: saldos, reducciones y hallazgos de auditoría")

    page = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<meta name="description" content="{t("Federal grants for Puerto Rico: balances not yet paid out in grants that have ended, reductions of the amounts committed, and audit findings that repeat, for every program. A balance on record is not money lost.", "Subvenciones federales para Puerto Rico: saldos sin desembolsar en subvenciones que ya vencieron, reducciones de los montos comprometidos y hallazgos de auditoría que se repiten, en todos los programas. Un saldo en el registro no es dinero perdido.")}">
<meta name="robots" content="noindex, nofollow">
<meta name="theme-color" content="#FFFFFF">
<link rel="icon" href="img/fpr-mark.png">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Material+Symbols+Rounded:opsz,wght,FILL,GRAD@24,400,1,0&icon_names={",".join(icons)}&display=block">
<link rel="stylesheet" href="css/twin.css?v={ver("css/twin.css")}">
<link rel="stylesheet" href="css/housing.css?v={ver("css/housing.css")}">
<link rel="stylesheet" href="css/public_money.css?v={ver("css/public_money.css")}">
<link rel="stylesheet" href="css/unused_funds.css?v=6">
<link rel="stylesheet" href="css/chat.css?v={ver("css/chat.css")}">
<link rel="stylesheet" href="css/ws.css?v=2">
<script src="js/i18n.js?v={max(int(ver("js/i18n.js")), I18N_V)}" data-page="unusedfunds"></script>
</head>
<body class="research">
<a class="skip" href="#now">{t("Skip to the content", "Ir al contenido")}</a>
<header class="topbar">
  <a class="logo" href="index.html" title="{t("PR Data Observatory home", "Inicio del Observatorio de Datos de PR")}"><img src="img/fpr-logo.png" alt="{t("Foundation for Puerto Rico. PR Data Observatory home", "Foundation for Puerto Rico. Inicio del Observatorio de Datos de PR")}"></a>
  <div class="brand"><b>{title}</b><span>{t("What the federal record shows, and what it cannot say", "Lo que muestra el registro federal y lo que no puede decir")}</span></div>
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
  <span class="ka-tabs" role="group" aria-label="{t("Knowledge Area", "Área de conocimiento")}" data-ka="unusedfunds"></span><span class="ka-sep" aria-hidden="true"></span>
  <a href="#now">{t("Now", "Ahora")}</a><a href="#agencies">{t("By agency", "Por agencia")}</a><a href="#programs">{t("By program", "Por programa")}</a><a href="#years">{t("By end year", "Por año de cierre")}</a><a href="#apart">{t("Shown apart", "Aparte")}</a><a href="#taken">{t("Reductions", "Reducciones")}</a><a href="#findings">{t("Audit findings", "Hallazgos de auditoría")}</a><a href="#rebuilt">{t("Five grants rebuilt", "Cinco subvenciones")}</a><a href="#limits">{t("What is missing", "Lo que falta")}</a><a href="#method">{t("Method", "Método")}</a><a href="#sources">{t("Sources", "Fuentes")}</a>
</nav>

<main class="page">
  <div class="note caution review-note" role="note" data-ka-note></div>

  <section class="hero" id="now">
    <div class="eyebrow">{t("Knowledge Area · Public money", "Área de conocimiento · Dinero público")}</div>
    <h1>{t("Federal grants: balances, reductions and audit findings", "Subvenciones federales: saldos, reducciones y hallazgos de auditoría")}</h1>
    <p class="lede">{t(f"Of the {num(T['awards'])} federal grants that began in federal fiscal years {y0} to {y1} for work in Puerto Rico, {num(T['ended'])} ended more than a year ago. In {num(T['with_balance'])} of them the federal record shows a balance not yet paid out: ${bn(T['with_balance_unpaid'])} billion of the ${bn(T['with_balance_obligated'])} billion obligated to them ({share}%), in {n_prog} federal programs of {n_ag} federal agencies. A balance on record is not money lost, and by itself it does not show that money is at risk: a grant can be extended, closing a grant often runs late on the federal side, and the record of payments can be behind.",
                       f"De las {num(T['awards'])} subvenciones federales que comenzaron en los años fiscales federales {y0} a {y1} para trabajos en Puerto Rico, {num(T['ended'])} vencieron hace más de un año. En {num(T['with_balance'])} de ellas el registro federal muestra un saldo sin desembolsar: ${bn(T['with_balance_unpaid'])} mil millones de los ${bn(T['with_balance_obligated'])} mil millones obligados a ellas ({share} %), en {n_prog} programas federales de {n_ag} agencias federales. Un saldo en el registro no es dinero perdido, y por sí solo no demuestra que el dinero esté en riesgo: una subvención se puede extender, el cierre muchas veces se atrasa del lado federal y el registro de pagos puede estar atrasado.")}</p>
    <div class="uf-cards">
      <div class="uf-card"><span class="ms-icon" aria-hidden="true">hourglass_bottom</span><div><div class="uf-v" data-t="skip">{num(T['with_balance'])}</div><div class="uf-l">{t("grants ended with an unpaid balance", "subvenciones vencidas con saldo sin pagar")}</div></div></div>
      <div class="uf-card"><span class="ms-icon" aria-hidden="true">payments</span><div><div class="uf-v" data-t="skip">${bn(T['with_balance_unpaid'])} B</div><div class="uf-l">{t("unpaid in those grants (B = billion)", "sin pagar en esas subvenciones (B = mil millones)")}</div></div></div>
      <div class="uf-card"><span class="ms-icon" aria-hidden="true">category</span><div><div class="uf-v" data-t="skip">{n_prog}</div><div class="uf-l">{t("federal programs with at least one such grant", "programas federales con al menos una de esas subvenciones")}</div></div></div>
      <div class="uf-card"><span class="ms-icon" aria-hidden="true">account_balance</span><div><div class="uf-v" data-t="skip">{n_ag}</div><div class="uf-l">{t("federal agencies", "agencias federales")}</div></div></div>
    </div>
    <p class="pm-small">{t(f"Data read from USAspending on {read_en}. Medicaid, TANF and two programs the federal government ended in 2025 are shown apart and are not in these figures.", f"Datos leídos de USAspending el {read_es}. Medicaid, TANF y dos programas que el gobierno federal terminó en 2025 se muestran aparte y no están en estas cifras.")}</p>
    <div class="note"><b>{t("Four different things.", "Cuatro cosas distintas.")}</b> {t("The page keeps them apart: balances not yet paid out (sections 1 to 4), reductions of the amount committed, or de-obligations (section 5), programs the federal government canceled (shown apart in both), and documented losses. For this last one the page has no figure: no open data source records a loss as such.", "La página las mantiene separadas: saldos sin desembolsar (secciones 1 a 4), reducciones del monto comprometido, o desobligaciones (sección 5), programas que el gobierno federal canceló (aparte en ambas), y pérdidas documentadas. De esta última la página no tiene cifra: ninguna fuente de datos abiertos registra una pérdida como tal.")}</div>
    <p class="pm-p">{t(f"A second measure, further down, counts reductions of the amount committed: from fiscal year {b0} to {b1}, {num(BT['awards'])} grants ended the period ${bn(BT['net'])} billion below the highest amount committed to them, for reasons the data do not give. The two measures count different things and are never added.", f"Una segunda medida, más abajo, cuenta las reducciones del monto comprometido: del año fiscal {b0} al {b1}, {num(BT['awards'])} subvenciones terminaron el período ${bn(BT['net'])} mil millones por debajo del monto más alto que se les comprometió, por razones que los datos no dan. Las dos medidas cuentan cosas distintas y nunca se suman.")}</p>
    <p class="pm-p"><a href="#taken">{t("Go to reductions of the amount committed", "Ir a las reducciones del monto comprometido")}</a></p>
    <p class="pm-p">{t(f"A third measure answers a different question: when a yearly audit finds a problem in a federal program, is it corrected? From {a0} to {a_done}, auditors reported {num(af_find)} findings in the audits of bodies in Puerto Rico, and marked {num(af_rep)} of them ({af_share}%) as repeated from the audit before.", f"Una tercera medida contesta otra pregunta: cuando una auditoría anual encuentra un problema en un programa federal, ¿se corrige? De {a0} a {a_done}, los auditores informaron {num(af_find)} hallazgos en las auditorías de entidades de Puerto Rico, y marcaron {num(af_rep)} de ellos ({af_share} %) como repetidos de la auditoría anterior.")}</p>
    <p class="pm-p"><a href="#findings">{t("Go to audit findings that repeat", "Ir a los hallazgos de auditoría que se repiten")}</a></p>
    <p class="pm-p"><a href="#rebuilt">{t("See five grants rebuilt one by one, and what they say about these balances", "Vea cinco subvenciones reconstruidas una por una, y lo que dicen sobre estos saldos")}</a></p>
    <p class="pm-p"><a href="money-cycle.html">{t("How public money moves: the stages behind these figures", "Cómo se mueve el dinero público: las etapas detrás de estas cifras")}</a></p>
    <div class="note caution"><b>{t("Read with care.", "Lea con cuidado.")}</b> {t("An unpaid balance is not proof that money was lost or that anyone did something wrong. The federal record of payments can be late or incomplete, a grant's end date can be extended after the data were read, and some programs pay through other accounts. The page counts grants and dollars; it does not say why a balance exists.", "Un saldo sin pagar no prueba que el dinero se perdió ni que alguien hizo algo mal. El registro federal de pagos puede estar atrasado o incompleto, la fecha de cierre de una subvención se puede extender después de leídos los datos, y algunos programas pagan por otras cuentas. La página cuenta subvenciones y dólares; no dice por qué existe un saldo.")}</div>
    <div class="note"><b>{t("Every program.", "Todos los programas.")}</b> {t("The page reads every federal grant program and singles none out. Programs that appear in news reports, such as the workforce grants, are here like any other: one line among many.", "La página lee todos los programas federales de subvenciones y no destaca ninguno. Los programas que salen en las noticias, como las subvenciones de desarrollo laboral, están aquí como cualquier otro: una línea entre muchas.")}</div>
  </section>

  <section class="block" id="agencies">
    <h2><span class="ms-icon" aria-hidden="true">account_balance</span>{t("1 · By federal agency", "1 · Por agencia federal")}</h2>
    <p class="pm-p">{t(f"The {n_ag} federal agencies whose grants ended with an unpaid balance, from the largest balance. The agency is the one that awarded the grant, not the body in Puerto Rico that received it.", f"Las {n_ag} agencias federales cuyas subvenciones vencieron con un saldo sin pagar, del saldo mayor al menor. La agencia es la que otorgó la subvención, no la entidad de Puerto Rico que la recibió.")}</p>
    <div class="card pm-tablebox uf-all"><table class="pm-table uf-table">
      <caption>{t(f"Grants that ended before {before_en} with an unpaid balance, by awarding federal agency", f"Subvenciones que vencieron antes del {before_es} con un saldo sin pagar, por agencia federal que las otorgó")}</caption>
      {head((t("Federal agency", "Agencia federal"), ""), h_awards, h_obl, h_unp, h_bar)}
      <tbody>
{ag_rows}
      </tbody>
    </table></div>
  </section>

  <section class="block" id="programs">
    <h2><span class="ms-icon" aria-hidden="true">category</span>{t("2 · By program", "2 · Por programa")}</h2>
    <p class="pm-p">{t(f"The {TOP} programs with the largest unpaid balance in grants that have ended. A program is an assistance listing, the federal government's own list of grant programs; its name is shown as the federal government writes it, in English. The other {rest_n} program lines add ${mil(rest_usd)} million and open below.", f"Los {TOP} programas con el mayor saldo sin pagar en subvenciones que ya vencieron. Un programa es un listado de asistencia, la lista de programas de subvenciones del propio gobierno federal; su nombre aparece como lo escribe el gobierno federal, en inglés. Las otras {rest_n} líneas de programas suman ${mil(rest_usd)} millones y se abren abajo.")}</p>
    <div class="card pm-tablebox"><table class="pm-table uf-table">
      <caption>{t(f"Programs by unpaid balance in grants that ended before {before_en}", f"Programas por saldo sin pagar en subvenciones que vencieron antes del {before_es}")}</caption>
      {head((t("Listing", "Listado"), ""), (t("Program", "Programa"), ""), (t("Federal agency", "Agencia federal"), ""), h_awards, h_obl, h_unp, h_bar)}
      <tbody>
{li_top}
      </tbody>
    </table></div>
    <details class="uf-more"><summary>{t(f"See the other {rest_n} program lines", f"Ver las otras {rest_n} líneas de programas")}</summary>
    <div class="card pm-tablebox"><table class="pm-table uf-table">
      <caption>{t("The other program lines, in the same order", "Las otras líneas de programas, en el mismo orden")}</caption>
      {head((t("Listing", "Listado"), ""), (t("Program", "Programa"), ""), (t("Federal agency", "Agencia federal"), ""), h_awards, h_obl, h_unp, h_bar)}
      <tbody>
{li_rest}
      </tbody>
    </table></div></details>
    <p class="pm-small">{t("One large grant can put a program near the top. Read the number of grants next to the dollars.", "Una sola subvención grande puede poner un programa cerca del principio. Lea el número de subvenciones junto a los dólares.")}</p>
{notes_html}
  </section>

  <section class="block" id="years">
    <h2><span class="ms-icon" aria-hidden="true">event</span>{t("3 · When the grants ended", "3 · Cuándo vencieron las subvenciones")}</h2>
    <p class="pm-p">{t("The same grants by the calendar year of their end date. The longer ago a grant ended, the less likely its balance will still be paid.", "Las mismas subvenciones por el año natural de su fecha de cierre. Mientras más tiempo hace que venció una subvención, menos probable es que su saldo todavía se pague.")}</p>
    <div class="card pm-tablebox uf-all"><table class="pm-table uf-table">
      <caption>{t("Grants with an unpaid balance, by the year they ended", "Subvenciones con saldo sin pagar, por el año en que vencieron")}</caption>
      {head((t("Year the grant ended", "Año en que venció la subvención"), ""), h_awards, h_unp, h_bar)}
      <tbody>
{ey_rows}
      </tbody>
    </table></div>
  </section>

  <section class="block" id="apart">
    <h2><span class="ms-icon" aria-hidden="true">call_split</span>{t("4 · Shown apart", "4 · Aparte")}</h2>
    <p class="pm-p">{t(f"Three kinds of programs are not in the figures above, each for a reason that holds for the whole program. Together they show ${bn(apart_usd)} billion in balances, which the page never adds to the rest.", f"Tres clases de programas no están en las cifras de arriba, cada una por una razón que vale para todo el programa. Juntas muestran ${bn(apart_usd)} mil millones en saldos, que la página nunca suma a lo demás.")}</p>
    <div class="card pm-tablebox uf-all"><table class="pm-table uf-table">
      <caption>{t("Programs shown apart, and why", "Programas que se muestran aparte, y por qué")}</caption>
      {head((t("Program", "Programa"), ""), (t("Why it is apart", "Por qué está aparte"), ""), (t("Ended grants with a balance", "Subvenciones vencidas con saldo"), N), h_unp)}
      <tbody>
{apart_rows}
      </tbody>
    </table></div>
    <h3 class="uf-h3">{t("Ended grants with no payment on record", "Subvenciones vencidas sin ningún pago en el registro")}</h3>
    <p class="pm-p">{t(f"{num(T['no_outlay'])} grants that ended more than a year ago (${mil(T['no_outlay_obligated'])} million obligated) show no payment at all in USAspending. A blank is not a zero: the payments may simply not be reported. They are listed here and are in no figure above, until the record can be checked grant by grant.", f"{num(T['no_outlay'])} subvenciones que vencieron hace más de un año (${mil(T['no_outlay_obligated'])} millones obligados) no muestran ningún pago en USAspending. Un espacio en blanco no es un cero: puede que los pagos simplemente no se hayan informado. Se listan aquí y no están en ninguna cifra de arriba, hasta que el registro se pueda verificar subvención por subvención.")}</p>
    <div class="card pm-tablebox uf-all"><table class="pm-table uf-table">
      <caption>{t("Ended grants with no payment on record, by awarding federal agency", "Subvenciones vencidas sin pago en el registro, por agencia federal que las otorgó")}</caption>
      {head((t("Federal agency", "Agencia federal"), ""), h_awards, h_obl)}
      <tbody>
{blank_rows}
      </tbody>
    </table></div>
    <div class="note"><b>{t("Also apart: FEMA Public Assistance.", "También aparte: Asistencia Pública de FEMA.")}</b> {t("Its grants do not follow the projects in USAspending. The Budget and public spending page counts those projects one by one, by stage and by age, from FEMA's own data.", "Sus subvenciones no siguen los proyectos en USAspending. La página de Presupuesto y gasto público cuenta esos proyectos uno por uno, por etapa y por antigüedad, con los datos de la propia FEMA.")}</div>
    <p class="pm-p"><a href="public-spending.html#fema">{t("Open the Budget and public spending page", "Abrir la página de Presupuesto y gasto público")}</a></p>
  </section>

  <section class="block" id="taken">
    <h2><span class="ms-icon" aria-hidden="true">undo</span>{t("5 · Reductions of the amount committed", "5 · Reducciones del monto comprometido")}</h2>
    <p class="pm-p">{t(f"After a grant is signed, the federal government can lower the amount committed to it (a de-obligation). The data do not say why an amount was lowered. A reduction can be an administrative adjustment, an adjustment to the actual cost, a federal cancellation, or money that was not committed in time, and the page cannot tell them apart. With that limit: from federal fiscal year {b0} to {b1}, {num(BT['awards'])} grants for work in Puerto Rico ended the period below the highest amount committed to them, a net reduction of ${bn(BT['net'])} billion in {BT['listings']} programs of {BT['agencies']} federal agencies.", f"Después de firmada una subvención, el gobierno federal puede bajar el monto que le comprometió (una desobligación). Los datos no dicen por qué se bajó un monto. Una reducción puede ser un ajuste administrativo, un ajuste al costo real, una cancelación federal o dinero que no se comprometió a tiempo, y la página no puede distinguirlos. Con ese límite: del año fiscal federal {b0} al {b1}, {num(BT['awards'])} subvenciones para trabajos en Puerto Rico terminaron el período por debajo del monto más alto que se les comprometió, una reducción neta de ${bn(BT['net'])} mil millones en {BT['listings']} programas de {BT['agencies']} agencias federales.")}</p>
    <div class="note caution"><b>{t("Not a measure of how grants were carried out.", "No es una medida de cómo se ejecutaron las subvenciones.")}</b> {t("A reduction is not proof that anyone did something wrong, and many come from federal decisions. The page counts all of them the same way.", "Una reducción no prueba que alguien hizo algo mal, y muchas vienen de decisiones federales. La página las cuenta todas de la misma manera.")}</div>
    <div class="note"><b>{t("Net, not gross.", "Neto, no bruto.")}</b> {t(f"USAspending lists {num(BC['negative'])} negative transactions worth ${bn(BC['gross_negative'])} billion in these years, but most are lowered one day and raised again later. The page counts only what each grant lost for good: its highest level minus its final level.", f"USAspending lista {num(BC['negative'])} transacciones negativas por ${bn(BC['gross_negative'])} mil millones en estos años, pero la mayoría se bajan un día y se vuelven a subir después. La página cuenta solo lo que cada subvención perdió de forma definitiva: su nivel más alto menos su nivel final.")}</div>

    <h3 class="uf-h3">{t("By federal agency", "Por agencia federal")}</h3>
    <div class="card pm-tablebox uf-all"><table class="pm-table uf-table">
      <caption>{t(f"Grants with a net reduction, fiscal years {b0} to {b1}, by awarding federal agency", f"Subvenciones con reducción neta, años fiscales {b0} a {b1}, por agencia federal que las otorgó")}</caption>
      {head((t("Federal agency", "Agencia federal"), ""), h_awards, h_net, h_bar2)}
      <tbody>
{tb_ag_rows}
      </tbody>
    </table></div>

    <h3 class="uf-h3">{t("By program", "Por programa")}</h3>
    <p class="pm-p">{t(f"The {TOP} programs with the largest net reduction. The other {tb_rest_n} program lines add ${mil(tb_rest_usd)} million and open below. A grant that carries several programs, as some workforce grants do, is placed under the program with most money; {BT['combined_awards']} grants are like that.", f"Los {TOP} programas con la mayor reducción neta. Las otras {tb_rest_n} líneas de programas suman ${mil(tb_rest_usd)} millones y se abren abajo. Una subvención que lleva varios programas, como algunas de desarrollo laboral, se pone bajo el programa con más dinero; {BT['combined_awards']} subvenciones son así.")}</p>
    <div class="card pm-tablebox"><table class="pm-table uf-table">
      <caption>{t(f"Programs by net reduction, fiscal years {b0} to {b1}", f"Programas por reducción neta, años fiscales {b0} a {b1}")}</caption>
      {head((t("Listing", "Listado"), ""), (t("Program", "Programa"), ""), (t("Federal agency", "Agencia federal"), ""), h_awards, h_net, h_bar2)}
      <tbody>
{tb_top}
      </tbody>
    </table></div>
    <details class="uf-more"><summary>{t(f"See the other {tb_rest_n} program lines with a net reduction", f"Ver las otras {tb_rest_n} líneas de programas con reducción neta")}</summary>
    <div class="card pm-tablebox"><table class="pm-table uf-table">
      <caption>{t("The other program lines with a net reduction, in the same order", "Las otras líneas de programas con reducción neta, en el mismo orden")}</caption>
      {head((t("Listing", "Listado"), ""), (t("Program", "Programa"), ""), (t("Federal agency", "Agencia federal"), ""), h_awards, h_net, h_bar2)}
      <tbody>
{tb_rest}
      </tbody>
    </table></div></details>

    <h3 class="uf-h3">{t("By year", "Por año")}</h3>
    <p class="pm-p">{t("Each grant is counted in the federal fiscal year of its last reduction. The latest years can still change: a grant lowered this year can be raised again.", "Cada subvención se cuenta en el año fiscal federal de su última reducción. Los años más recientes todavía pueden cambiar: una subvención que se bajó este año se puede volver a subir.")}</p>
    <div class="card pm-tablebox uf-all"><table class="pm-table uf-table">
      <caption>{t("Grants with a net reduction, by the fiscal year of their last reduction", "Subvenciones con reducción neta, por el año fiscal de su última reducción")}</caption>
      {head((t("Federal fiscal year", "Año fiscal federal"), ""), h_awards, h_net, h_bar2)}
      <tbody>
{tb_y_rows}
      </tbody>
    </table></div>

    <h3 class="uf-h3">{t("Shown apart: routine reductions and federal decisions", "Aparte: reducciones de rutina y decisiones federales")}</h3>
    <p class="pm-p">{t(f"Four kinds of programs are not in the figures above: three whose reductions are part of how they work, and the money the federal government withdrew by its own decision in 2025. Together they show ${bn(tb_apart_usd)} billion in net reductions, which the page never adds to the rest.", f"Cuatro clases de programas no están en las cifras de arriba: tres cuyas reducciones son parte de cómo funcionan, y el dinero que el gobierno federal retiró por decisión propia en 2025. Juntas muestran ${bn(tb_apart_usd)} mil millones en reducciones netas, que la página nunca suma a lo demás.")}</p>
    <div class="card pm-tablebox uf-all"><table class="pm-table uf-table">
      <caption>{t("Programs shown apart, and why", "Programas que se muestran aparte, y por qué")}</caption>
      {head((t("Kind of program", "Clase de programa"), ""), (t("Why it is apart", "Por qué está aparte"), ""), h_awards, h_net)}
      <tbody>
{tb_apart_rows}
      </tbody>
    </table></div>
    <div class="note caution"><b>{t("Never add the two measures.", "Nunca sume las dos medidas.")}</b> {t("The grants that ended with an unpaid balance and the grants with a net reduction overlap, and they cover different years. Each answers its own question.", "Las subvenciones que vencieron con saldo sin pagar y las subvenciones con reducción neta se solapan, y cubren años distintos. Cada una contesta su propia pregunta.")}</div>
  </section>

  <section class="block" id="findings">
    <h2><span class="ms-icon" aria-hidden="true">fact_check</span>{t("6 · Audit findings that repeat", "6 · Hallazgos de auditoría que se repiten")}</h2>
    <p class="pm-p">{t(f"Every body that spends $750,000 or more of federal money in a year must have a single audit. The auditor reports each problem found in a federal program as a finding, and says whether the same finding was in the audit before. From audit year {a0} to {a_done}, bodies in Puerto Rico filed {num(af_audits)} single audits; {num(af_with)} had at least one finding. Of the {num(af_find)} findings, {num(af_rep)} ({af_share}%) were repeated. The share stayed between {af_lo}% and {af_hi}% every year.", f"Toda entidad que gasta $750,000 o más de dinero federal en un año tiene que hacerse una auditoría única. El auditor informa cada problema que encuentra en un programa federal como un hallazgo, y dice si el mismo hallazgo estaba en la auditoría anterior. Del año de auditoría {a0} al {a_done}, las entidades de Puerto Rico radicaron {num(af_audits)} auditorías únicas; {num(af_with)} tuvieron al menos un hallazgo. De los {num(af_find)} hallazgos, {num(af_rep)} ({af_share} %) fueron repetidos. La proporción se mantuvo entre {af_lo} % y {af_hi} % todos los años.")}</p>
    <div class="note caution"><b>{t("A finding is not a loss.", "Un hallazgo no es una pérdida.")}</b> {t("A finding says a rule was not followed or a control was weak. It does not say money was misused or taken back, and many findings are small. The page counts findings; it does not weigh them. Questioned costs appear only as a yes or no: the source publishes no amount.", "Un hallazgo dice que no se siguió una regla o que un control era débil. No dice que el dinero se usó mal ni que se retiró, y muchos hallazgos son menores. La página cuenta hallazgos; no los pondera. Los costos cuestionados aparecen solo como un sí o un no: la fuente no publica ningún monto.")}</div>
    <div class="note"><b>{t("Why repeated findings matter.", "Por qué importan los hallazgos repetidos.")}</b> {t("A repeated finding is the closest open measure of whether a problem found one year was corrected by the next. It does not say why it was not: some corrections take more than a year.", "Un hallazgo repetido es la medida abierta más cercana a si un problema encontrado un año se corrigió para el siguiente. No dice por qué no se corrigió: algunas correcciones toman más de un año.")}</div>

    <h3 class="uf-h3">{t("By audit year", "Por año de auditoría")}</h3>
    <p class="pm-p">{t(f"An audit is due nine months after the fiscal year ends. From {a0} to {a_done}, {num(af_late)} of the {num(af_audits)} audits were accepted after that. Years marked * are still arriving, so their counts will grow.", f"Una auditoría vence nueve meses después del cierre del año fiscal. De {a0} a {a_done}, {num(af_late)} de las {num(af_audits)} auditorías se aceptaron después de esa fecha. Los años marcados con * todavía están llegando, así que sus conteos van a crecer.")}</p>
    <div class="card pm-tablebox uf-all"><table class="pm-table uf-table">
      <caption>{t("Single audits of bodies in Puerto Rico and their findings, by audit year", "Auditorías únicas de entidades de Puerto Rico y sus hallazgos, por año de auditoría")}</caption>
      {head((t("Audit year", "Año de auditoría"), ""), (t("Audits", "Auditorías"), N), (t("With findings", "Con hallazgos"), N), h_find, h_rep, h_share, h_mw, h_qc, (t("Accepted late", "Aceptadas tarde"), N), (t("Median months to acceptance", "Mediana de meses hasta la aceptación"), N))}
      <tbody>
{af_y_rows}
      </tbody>
    </table></div>

    <h3 class="uf-h3">{t("By kind of body", "Por clase de entidad")}</h3>
    <p class="pm-p">{t(f"Audit years {a0} to {a_done}, by the kind of body the Clearinghouse records; the years still arriving are left out. No body is named.", f"Años de auditoría {a0} a {a_done}, por la clase de entidad que registra el Clearinghouse; los años que todavía están llegando se dejan fuera. No se nombra ninguna entidad.")}</p>
    <div class="card pm-tablebox uf-all"><table class="pm-table uf-table">
      <caption>{t("Findings by kind of audited body", "Hallazgos por clase de entidad auditada")}</caption>
      {head((t("Kind of body", "Clase de entidad"), ""), (t("Audits", "Auditorías"), N), h_find, h_rep, h_share, h_mw, h_qc)}
      <tbody>
{af_k_rows}
      </tbody>
    </table></div>

    <h3 class="uf-h3">{t("By federal agency", "Por agencia federal")}</h3>
    <p class="pm-p">{t("The agency is the federal agency whose program the finding is about. A finding that touches programs of two agencies counts in both, so the rows add up to more than the findings.", "La agencia es la agencia federal del programa al que se refiere el hallazgo. Un hallazgo que toca programas de dos agencias cuenta en las dos, así que las filas suman más que los hallazgos.")}</p>
    <div class="card pm-tablebox uf-all"><table class="pm-table uf-table">
      <caption>{t(f"Findings by federal agency of the program, audit years from {a0}", f"Hallazgos por agencia federal del programa, años de auditoría desde {a0}")}</caption>
      {head((t("Federal agency", "Agencia federal"), ""), h_find, h_rep, h_share, h_mw, h_qc)}
      <tbody>
{af_a_rows}
      </tbody>
    </table></div>

    <h3 class="uf-h3">{t("By program", "Por programa")}</h3>
    <p class="pm-p">{t(f"The {TOP} programs with most findings, of {len(A['listings'])} programs with at least one. A finding counts once in each program it touches. Programs with many audited bodies have more findings, so read the share repeated next to the count.", f"Los {TOP} programas con más hallazgos, de {len(A['listings'])} programas con al menos uno. Un hallazgo cuenta una vez en cada programa que toca. Los programas con muchas entidades auditadas tienen más hallazgos, así que lea la parte repetida junto al conteo.")}</p>
    <div class="card pm-tablebox"><table class="pm-table uf-table">
      <caption>{t(f"Programs by number of findings, audit years from {a0}", f"Programas por número de hallazgos, años de auditoría desde {a0}")}</caption>
      {head((t("Listing", "Listado"), ""), (t("Program", "Programa"), ""), (t("Federal agency", "Agencia federal"), ""), h_find, h_rep, h_share, h_mw, h_qc)}
      <tbody>
{af_top}
      </tbody>
    </table></div>
    <details class="uf-more"><summary>{t(f"See the other {af_rest_n} programs with findings", f"Ver los otros {af_rest_n} programas con hallazgos")}</summary>
    <div class="card pm-tablebox"><table class="pm-table uf-table">
      <caption>{t("The other programs with findings, in the same order", "Los otros programas con hallazgos, en el mismo orden")}</caption>
      {head((t("Listing", "Listado"), ""), (t("Program", "Programa"), ""), (t("Federal agency", "Agencia federal"), ""), h_find, h_rep, h_share, h_mw, h_qc)}
      <tbody>
{af_rest}
      </tbody>
    </table></div></details>
  </section>

  <section class="block" id="rebuilt">
    <h2><span class="ms-icon" aria-hidden="true">payments</span>{t("Five grants rebuilt, one by one", "Cinco subvenciones reconstruidas, una por una")}</h2>
    <p class="pm-p">{t(f"Before building any new measure, the page follows five large grants through everything the open record gives: each change of the amount committed and each year's payments. It is a test of the source: how far can a balance on record be trusted? The five were not chosen by hand. They are the grants with the largest balance on record among those that ended more than a year ago, one for each of the first five programs, read on {rb_read_en}.",
                       f"Antes de construir cualquier medida nueva, la página sigue cinco subvenciones grandes por todo lo que da el registro abierto: cada cambio del monto comprometido y los pagos de cada año. Es una prueba de la fuente: ¿cuánto se puede confiar en un saldo del registro? Las cinco no se escogieron a mano. Son las subvenciones con el mayor saldo en el registro entre las que vencieron hace más de un año, una por cada uno de los primeros cinco programas, leídas el {rb_read_es}.")}</p>
    <div class="note"><b>{t("What the five show.", "Lo que muestran las cinco.")}</b> {t(f"In {rb_late} of the {rb_n}, more than half of everything paid was paid after the fiscal year of the end date. In one, payments stop in the record two years before the grant ended. In one, the total paid went down. None of the five has a closing date, an approved extension or a decision of the federal agency in the record: USAspending does not publish them.",
                       f"En {rb_late} de las {rb_n}, más de la mitad de todo lo pagado se pagó después del año fiscal de la fecha de fin. En una, los pagos se detienen en el registro dos años antes de que venciera la subvención. En una, el total pagado bajó. Ninguna de las cinco tiene en el registro una fecha de cierre, una extensión aprobada o una decisión de la agencia federal: USAspending no las publica.")}</div>
    <div class="note caution"><b>{t("What follows from it.", "Lo que se desprende.")}</b> {t("A balance after the end date tells where to ask, not how much money went without use. The end date on record is often not the last day to pay, and the record of payments can begin late, stop early or be corrected. For that reason the page builds no indicator from these balances, and the figures of sections 1 to 4 are a count of what the record shows, with these limits.",
                       "Un saldo después de la fecha de fin dice dónde preguntar, no cuánto dinero quedó sin uso. La fecha de fin del registro muchas veces no es el último día para pagar, y el registro de pagos puede empezar tarde, detenerse antes o corregirse. Por eso la página no construye ningún indicador con estos saldos, y las cifras de las secciones 1 a 4 son un conteo de lo que muestra el registro, con estos límites.")}</div>
{rb_cards}
    <p class="pm-small">{t("The recipient of each grant is not read and no grant number is published; a grant is told apart by its program, its federal agency and its dates. Payments are the ones the federal agency reported to USAspending for each fiscal year, and they add up to the grant's total paid out on record.",
                           "No se lee el receptor de cada subvención ni se publica ningún número de subvención; una subvención se distingue por su programa, su agencia federal y sus fechas. Los pagos son los que la agencia federal informó a USAspending para cada año fiscal, y suman el total desembolsado de la subvención en el registro.")}</p>
  </section>

  <section class="block" id="limits">
    <h2><span class="ms-icon" aria-hidden="true">help</span>{t("What this page cannot answer", "Lo que esta página no puede contestar")}</h2>
    <div class="note"><b>{t("What open data cannot answer.", "Lo que los datos abiertos no pueden contestar.")}</b> {t("Why a balance was not used, what services were not delivered, and how much Commonwealth money replaced a federal payment that was denied. No public data source has these.", "Por qué no se usó un saldo, qué servicios no se dieron y cuánto dinero del Gobierno de Puerto Rico reemplazó un pago federal denegado. Ninguna fuente pública de datos tiene esto.")}</div>
  </section>

  <section class="block" id="method">
    <h2><span class="ms-icon" aria-hidden="true">info</span>{t("Method", "Método")}</h2>
    <div class="note"><b>{t("Stage and basis.", "Etapa y base.")}</b> {t(f"Obligated and paid out by the federal government, by grant; reported in USAspending, not audited. Grants signed in federal fiscal years {y0} to {y1} (October to September), with place of performance Puerto Rico.", f"Obligado y desembolsado por el gobierno federal, por subvención; informado en USAspending, no auditado. Subvenciones firmadas en los años fiscales federales {y0} a {y1} (de octubre a septiembre), con lugar de ejecución en Puerto Rico.")}</div>
    <div class="note"><b>{t("The grants read.", "Las subvenciones leídas.")}</b> {t(f"Grants that began in federal fiscal years {y0} to {y1}. USAspending's search also returns older grants that were only amended in those years; those {num(T['older_left_out'])} grants are left out, because USAspending has no payments for them before fiscal year 2020.", f"Subvenciones que comenzaron en los años fiscales federales {y0} a {y1}. La búsqueda de USAspending también devuelve subvenciones más viejas que solo se enmendaron en esos años; esas {num(T['older_left_out'])} subvenciones se dejan fuera, porque USAspending no tiene sus pagos anteriores al año fiscal 2020.")}</div>
    <div class="note"><b>{t("Ended.", "Vencida.")}</b> {t(f"A grant's end date closes its period of performance. The data were read on {read_en}, and a grant counts as ended when its end date is before {before_en}, more than one year earlier. The one-year line follows the closeout rule (2 CFR 200.344): the recipient has 120 days to pay its bills and send its reports (90 days for grants made before November 12, 2020), and the agency should make every effort to close the grant within a year. Passing that line does not show that the balance was lost: the time to pay out can be extended, and closing is often late on the federal side.", f"La fecha de cierre de una subvención termina su período de ejecución. Los datos se leyeron el {read_es}, y una subvención cuenta como vencida cuando su fecha de cierre es anterior al {before_es}, más de un año antes. La línea de un año sigue la regla de cierre (2 CFR 200.344): el receptor tiene 120 días para pagar sus cuentas y enviar sus informes (90 días en las subvenciones otorgadas antes del 12 de noviembre de 2020), y la agencia debe hacer todo esfuerzo por cerrar la subvención dentro de un año. Pasar esa línea no demuestra que el saldo se perdió: el tiempo para desembolsar se puede extender, y el cierre muchas veces se atrasa del lado federal.")}</div>
    <div class="note"><b>{t("Unpaid balance.", "Saldo sin pagar.")}</b> {t(f"The amount obligated minus what the federal Treasury has paid out, never below zero. A grant is counted when its balance is at least 5% of the grant and at least $1,000. {num(T['no_outlay'])} ended grants (${mil(T['no_outlay_obligated'])} million) report no payment at all; they are shown apart in section 4, because a blank is not a zero.", f"El monto obligado menos lo que el Tesoro federal ha desembolsado, nunca menos de cero. Una subvención se cuenta cuando su saldo es al menos el 5 % de la subvención y al menos $1,000. {num(T['no_outlay'])} subvenciones vencidas (${mil(T['no_outlay_obligated'])} millones) no informan ningún pago; se muestran aparte en la sección 4, porque un espacio en blanco no es un cero.")}</div>
    <div class="note"><b>{t("Net reduction.", "Reducción neta.")}</b> {t(f"For money taken back, the page reads every transaction on grants with place of performance Puerto Rico from federal fiscal year {b0} to {b1}: {num(BC['transactions'])} transactions on {num(BC['awards'])} grants. A negative transaction is a de-obligation. For each grant, the transactions of one day count as one change; the net reduction is the highest level the grant reached in the period minus the level where it ended. Grants with less than $1,000 are left out.", f"Para el dinero retirado, la página lee todas las transacciones de las subvenciones con lugar de ejecución en Puerto Rico del año fiscal federal {b0} al {b1}: {num(BC['transactions'])} transacciones en {num(BC['awards'])} subvenciones. Una transacción negativa es una desobligación. En cada subvención, las transacciones de un mismo día cuentan como un solo cambio; la reducción neta es el nivel más alto que alcanzó la subvención en el período menos el nivel donde terminó. Las subvenciones con menos de $1,000 se dejan fuera.")}</div>
    <div class="note"><b>{t("Money moved, not taken back.", "Dinero movido, no retirado.")}</b> {t(f"When a reduction on one grant is matched by an equal increase on another grant of the same program and agency within 31 days, the money was moved. Those {num(BC['moves'])} reductions (${mil(BC['moved'])} million) are not counted.", f"Cuando una reducción en una subvención coincide con un aumento igual en otra subvención del mismo programa y agencia dentro de 31 días, el dinero se movió. Esas {num(BC['moves'])} reducciones (${mil(BC['moved'])} millones) no se cuentan.")}</div>
    <div class="note"><b>{t("Audit findings.", "Hallazgos de auditoría.")}</b> {t(f"The page reads every single audit filed by a body in Puerto Rico from audit year {a0} in the Federal Audit Clearinghouse: {num(A['totals']['audits'])} audits. The source lists a finding once for each award line it touches; here a finding is counted once per audit, and it is repeated, a material weakness or has questioned costs when any of its lines says so. Bodies are counted by the kind the source records and are never named.", f"La página lee todas las auditorías únicas radicadas por entidades de Puerto Rico desde el año de auditoría {a0} en el Federal Audit Clearinghouse: {num(A['totals']['audits'])} auditorías. La fuente lista un hallazgo una vez por cada línea de adjudicación que toca; aquí un hallazgo se cuenta una vez por auditoría, y es repetido, debilidad material o tiene costos cuestionados cuando alguna de sus líneas lo dice. Las entidades se cuentan por la clase que registra la fuente y nunca se nombran.")}</div>
    <div class="note"><b>{t("What the page leaves out.", "Lo que la página deja fuera.")}</b> {t("Contracts, loans and direct payments to people. Grants signed before fiscal year 2020, because USAspending has no payments for them. The name of any recipient: this step counts by federal agency and program only.", "Contratos, préstamos y pagos directos a personas. Subvenciones firmadas antes del año fiscal 2020, porque USAspending no tiene sus pagos. El nombre de cualquier receptor: este paso cuenta solo por agencia federal y por programa.")}</div>
    <div class="note"><b>{t("More detail.", "Más detalle.")}</b> {t("The method, the tests and the code are in docs/unused-funds.md of the project repository. The files data/unused_funds.json, data/taken_back.json and data/audit_findings.json have every program line.", "El método, las pruebas y el código están en docs/unused-funds.md del repositorio del proyecto. Los archivos data/unused_funds.json, data/taken_back.json y data/audit_findings.json tienen todas las líneas de programas.")}</div>
    <p class="pm-p"><a href="data/unused_funds.json" download>{t("Download the data on unpaid balances (JSON)", "Descargar los datos de saldos sin pagar (JSON)")}</a> · <a href="data/taken_back.json" download>{t("Download the data on money taken back (JSON)", "Descargar los datos de dinero retirado (JSON)")}</a> · <a href="data/audit_findings.json" download>{t("Download the data on audit findings (JSON)", "Descargar los datos de hallazgos de auditoría (JSON)")}</a></p>
  </section>

  <section class="block" id="sources">
    <h2><span class="ms-icon" aria-hidden="true">menu_book</span>{t("Sources and licenses", "Fuentes y licencias")}</h2>
    <div class="note"><b>{t("USAspending.gov (US Department of the Treasury).", "USAspending.gov (Departamento del Tesoro de EE. UU.).")}</b> {t(f"Award search: grants with place of performance Puerto Rico, by the federal fiscal year they were signed, with the amount obligated, the total outlays and the end date of each. Read on {read_en}. US Government work, public domain.", f"Búsqueda de adjudicaciones: subvenciones con lugar de ejecución en Puerto Rico, por el año fiscal federal en que se firmaron, con el monto obligado, los desembolsos totales y la fecha de cierre de cada una. Leído el {read_es}. Obra del Gobierno de EE. UU., dominio público.")}</div>
    <div class="note"><b>{t("USAspending.gov, transactions.", "USAspending.gov, transacciones.")}</b> {t(f"Transaction search: every change to the amount obligated to a grant with place of performance Puerto Rico, by action date, federal fiscal years {b0} to {b1}. US Government work, public domain.", f"Búsqueda de transacciones: cada cambio al monto obligado de una subvención con lugar de ejecución en Puerto Rico, por fecha de la acción, años fiscales federales {b0} a {b1}. Obra del Gobierno de EE. UU., dominio público.")}</div>
    <div class="note"><b>{t("Federal Audit Clearinghouse (US General Services Administration).", "Federal Audit Clearinghouse (Administración de Servicios Generales de EE. UU.).")}</b> {t(f"The single audits filed by bodies in Puerto Rico, their findings and the award lines with a finding, audit years from {a0}. Read on {A['read']}. US Government work, public domain.", f"Las auditorías únicas radicadas por entidades de Puerto Rico, sus hallazgos y las líneas de adjudicación con hallazgos, años de auditoría desde {a0}. Leído el {A['read']}. Obra del Gobierno de EE. UU., dominio público.")}</div>
    <div class="note"><b>{t("Code of Federal Regulations, 2 CFR 200.344.", "Código de Regulaciones Federales, 2 CFR 200.344.")}</b> {t("The closeout rule: the days a recipient has to draw down and report after a grant ends, and the time the agency has to close it.", "La regla de cierre: los días que tiene el receptor para retirar el dinero e informar después de que vence una subvención, y el tiempo que tiene la agencia para cerrarla.")}</div>
    <div class="note"><b>{t("How to cite this page.", "Cómo citar esta página.")}</b> {t(f"Foundation for Puerto Rico, Knowledge Area: Federal grants: balances, reductions and audit findings, PR Data Observatory, USAspending data read on {read_en} (draft). Data: USAspending.gov.", f"Foundation for Puerto Rico, Área de conocimiento: Subvenciones federales: saldos, reducciones y hallazgos de auditoría, Observatorio de Datos de PR, datos de USAspending leídos el {read_es} (borrador). Datos: USAspending.gov.")}</div>
  </section>
</main>
<script src="js/core/knowledge.js?v={ver("js/core/knowledge.js")}"></script>
<script>Core.knowledge.render(); I18N.apply();</script>
<script src="js/common.js?v={ver("js/common.js")}"></script>
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
    (ROOT / "site" / "unused-funds.html").write_text(page, encoding="utf-8", newline="\n")
    es = {"_about": "The Federal funds returned and unused page of the Knowledge Area (unused-funds.html). Written by docs/analysis/unused-funds-2026-11/make_page.py from its (English, Spanish) pairs: edit them there, not here."}
    es.update(ES)
    (ROOT / "i18n_src" / "es" / "unused_funds.json").write_text(json.dumps(es, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(f"wrote site/unused-funds.html and i18n_src/es/unused_funds.json ({len(ES)} strings)")


if __name__ == "__main__":
    build()
