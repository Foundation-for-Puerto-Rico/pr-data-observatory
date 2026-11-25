"""Writes the Knowledge Area page "How public money moves" (site/money-cycle.html) and its Spanish (i18n_src/es/money_cycle.json).

  python docs/analysis/money-cycle-2026-11/make_page.py   write the page and its Spanish. Then run python i18n.py.

HANDOFF decision 112, step 1: the budget cycle as a page of its own, which explains the stages the three public money pages show (Budget and public
spending, Federal grants, Disaster funding and need). The page teaches: it has no data and no script of its own, every statement rests on a public
source listed at the end (SOURCES), and it gives no opinion on how the process should work. It follows the site's language rule (docs/i18n.md):
every string is written once, as an (English, Spanish) pair. Prepared with Claude (AI) for FPR, 2026-11-19.
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


# The stages of the Commonwealth budget, in order: (icon, name, what happens, who).
STAGES = [
    ("edit_note", ("Design", "Diseño"),
     ("An agency works out what it needs the money for and writes its request, with its plan of work.", "Una agencia define para qué necesita el dinero y escribe su petición, con su plan de trabajo."),
     ("The agency", "La agencia")),
    ("outgoing_mail", ("Request", "Solicitud"),
     ("The Office of Management and Budget puts the requests together into the Governor's proposed budget, which goes to the Oversight Board. The Board approves it or sends it back to be corrected.", "La Oficina de Gerencia y Presupuesto reúne las peticiones en el presupuesto propuesto del Gobernador, que va a la Junta de Supervisión Fiscal. La Junta lo aprueba o lo devuelve para que se corrija."),
     ("Office of Management and Budget, Governor", "Oficina de Gerencia y Presupuesto, Gobernador")),
    ("how_to_vote", ("Approval", "Aprobación"),
     ("The version the Board approved goes to the Legislature, which evaluates and adopts a budget. The Governor signs it, and the Oversight Board certifies it when it follows the fiscal plan. If it does not, the Board can write the budget itself.", "La versión que aprobó la Junta va a la Asamblea Legislativa, que evalúa y adopta un presupuesto. El Gobernador lo firma, y la Junta de Supervisión Fiscal lo certifica cuando cumple con el plan fiscal. Si no cumple, la Junta puede redactar el presupuesto."),
     ("Legislature, Oversight Board", "Asamblea Legislativa, Junta de Supervisión Fiscal")),
    ("assignment", ("Assignment", "Asignación"),
     ("Each agency receives its share of the certified budget for the fiscal year, by fund and by concept of expense.", "Cada agencia recibe su parte del presupuesto certificado para el año fiscal, por fondo y por concepto de gasto."),
     ("Office of Management and Budget", "Oficina de Gerencia y Presupuesto")),
    ("contract", ("Obligation", "Obligación"),
     ("The agency commits the money: it signs a contract, places an order or hires. From here the government owes the money to someone.", "La agencia compromete el dinero: firma un contrato, hace una orden o contrata personal. Desde aquí el gobierno le debe ese dinero a alguien."),
     ("The agency; purchases go through the General Services Administration", "La agencia; las compras pasan por la Administración de Servicios Generales")),
    ("construction", ("Execution", "Ejecución"),
     ("The work is done or the service is given.", "Se hace la obra o se da el servicio."),
     ("The agency and its contractors", "La agencia y sus contratistas")),
    ("payments", ("Spending", "Gasto"),
     ("The Treasury pays the bill. Only now is the money spent.", "Hacienda paga la cuenta. Solo ahora el dinero está gastado."),
     ("Department of the Treasury (Hacienda)", "Departamento de Hacienda")),
    ("verified", ("In service", "En servicio"),
     ("People use what was paid for: the school is open, the clinic sees patients.", "La gente usa lo que se pagó: la escuela está abierta, la clínica atiende pacientes."),
     ("No one reports it in open data", "Nadie lo informa en datos abiertos")),
]

# The federal side: (name, what happens).
FEDERAL = [
    (("Appropriation", "Asignación del Congreso"), ("Congress sets aside money for a program.", "El Congreso separa dinero para un programa.")),
    (("Award", "Adjudicación"), ("A federal agency awards a grant to a recipient in Puerto Rico. For the federal government the money is now obligated.", "Una agencia federal adjudica una subvención a un receptor en Puerto Rico. Para el gobierno federal el dinero ya está obligado.")),
    (("The recipient commits it", "El receptor lo compromete"), ("The recipient, usually a Commonwealth agency, must still buy, contract or pass the money on. A grant can be fully awarded and not yet committed here.", "El receptor, casi siempre una agencia del Gobierno de Puerto Rico, todavía tiene que comprar, contratar o pasar el dinero a otros. Una subvención puede estar adjudicada por completo y todavía no comprometida aquí.")),
    (("Outlay", "Desembolso"), ("The federal Treasury pays the recipient, often as a refund of what it already spent.", "El Tesoro federal le paga al receptor, muchas veces como reembolso de lo que ya gastó.")),
    (("End of the period of performance", "Fin del período de ejecución"), ("The time to do the work ends. The recipient has 120 days to pay its bills and report.", "Termina el tiempo para hacer el trabajo. El receptor tiene 120 días para pagar sus cuentas e informar.")),
    (("Closeout", "Cierre"), ("The federal agency closes the grant. What was not used is taken off the grant (a de-obligation).", "La agencia federal cierra la subvención. Lo que no se usó se le quita a la subvención (una desobligación).")),
]

# (page, href, what it shows, stage).
PAGES = [
    (("Budget and public spending", "Presupuesto y gasto público"), "public-spending.html",
     ("The Commonwealth budget proposed, approved and spent; federal money obligated and paid out; FEMA projects by stage.", "El presupuesto del Gobierno de Puerto Rico propuesto, aprobado y gastado; el dinero federal obligado y desembolsado; los proyectos de FEMA por etapa."),
     ("Request to spending", "De la solicitud al gasto")),
    (("Federal grants: balances, reductions and audit findings", "Subvenciones federales: saldos, reducciones y hallazgos de auditoría"), "unused-funds.html",
     ("Grants that ended with a balance not yet paid out, amounts lowered after the award, and what the yearly audits found.", "Subvenciones que vencieron con un saldo sin desembolsar, montos reducidos después de la adjudicación, y lo que encontraron las auditorías anuales."),
     ("Outlay to closeout", "Del desembolso al cierre")),
    (("Disaster funding and need", "Fondos por desastres y necesidad"), "public-money.html",
     ("Federal disaster and community development money obligated per resident, by municipio, next to two measures of need.", "El dinero federal para desastres y desarrollo comunitario obligado por residente, por municipio, junto a dos medidas de necesidad."),
     ("Obligation", "Obligación")),
]

# What a reader can do after the page (the hero's list).
LEARN = [
    ("Name the stage a figure is in, and say what it does and does not mean.", "Nombrar la etapa en que está una cifra, y decir lo que significa y lo que no."),
    ("Tell apart approved, obligated, paid and in service.", "Distinguir entre aprobado, obligado, pagado y en servicio."),
    ("Ask five questions of any figure about public money before drawing a conclusion.", "Hacerle cinco preguntas a cualquier cifra de dinero público antes de sacar una conclusión."),
]

# One made-up grant followed from start to end: (what happens, where it shows, link or None). No amount: the example teaches the order, not a figure.
EXAMPLE = [
    (("Congress sets aside money for a program that repairs community buildings.", "El Congreso separa dinero para un programa que repara edificios comunitarios."),
     ("In the federal budget, for the whole program and not for one place", "En el presupuesto federal, para todo el programa y no para un lugar"), None),
    (("A Commonwealth agency designs a project, the repair of a community center, and applies.", "Una agencia del Gobierno de Puerto Rico diseña un proyecto, la reparación de un centro comunitario, y solicita."),
     ("Not in open data", "No está en datos abiertos"), None),
    (("The federal agency awards the grant. For the federal government the money is obligated.", "La agencia federal adjudica la subvención. Para el gobierno federal el dinero está obligado."),
     ("Budget and public spending, section 5", "Presupuesto y gasto público, sección 5"), "public-spending.html#federal"),
    (("The agency's Commonwealth budget for the year counts the federal money among its funds.", "El presupuesto estatal de la agencia para el año cuenta el dinero federal entre sus fondos."),
     ("Budget and public spending, section 2", "Presupuesto y gasto público, sección 2"), "public-spending.html#funds"),
    (("The agency signs a contract with a builder. This is the second obligation, the one made here.", "La agencia firma un contrato con un constructor. Esta es la segunda obligación, la que se hace aquí."),
     ("Not in the federal record, and not on these pages", "No está en el registro federal ni en estas páginas"), None),
    (("The builder works and sends its bills. The agency pays them and asks the federal Treasury for the money back.", "El constructor trabaja y envía sus facturas. La agencia las paga y le pide al Tesoro federal que le devuelva ese dinero."),
     ("Not in open data until the federal payment is made", "No está en datos abiertos hasta que se hace el pago federal"), None),
    (("The federal Treasury pays the agency. This is an outlay.", "El Tesoro federal le paga a la agencia. Esto es un desembolso."),
     ("Budget and public spending, section 5", "Presupuesto y gasto público, sección 5"), "public-spending.html#federal"),
    (("The time to do the work ends. What has not been paid out by then shows as a balance.", "Termina el tiempo para hacer el trabajo. Lo que no se ha desembolsado para entonces aparece como un saldo."),
     ("Federal grants, sections 1 to 3", "Subvenciones federales, secciones 1 a 3"), "unused-funds.html#now"),
    (("The federal agency closes the grant and takes off what was not used.", "La agencia federal cierra la subvención y le quita lo que no se usó."),
     ("Federal grants, section 5", "Subvenciones federales, sección 5"), "unused-funds.html#taken"),
    (("The community center opens and people use it.", "El centro comunitario abre y la gente lo usa."),
     ("No open source records it", "Ninguna fuente abierta lo registra"), None),
]

# Pairs that are often read as the same thing: (what is not what, why).
CONFUSED = [
    (("Approved is not spent", "Aprobado no es gastado"),
     ("A budget gives permission to spend up to an amount. It does not say the money was used. The permission ends with the fiscal year: in the General Fund, money of an earlier year cannot be used unless the certified budget says so. Special funds are different: their income of earlier years can be used, under the rules of each fund.", "Un presupuesto da permiso para gastar hasta un monto. No dice que el dinero se usó. El permiso termina con el año fiscal: en el Fondo General, el dinero de un año anterior no se puede usar a menos que el presupuesto certificado lo disponga. Los fondos especiales son distintos: sus ingresos de años anteriores se pueden usar, según las reglas de cada fondo.")),
    (("Obligated is not paid", "Obligado no es pagado"),
     ("A signed contract commits the money. The payment comes later, as the work is done and billed.", "Un contrato firmado compromete el dinero. El pago llega después, según se hace y se factura el trabajo.")),
    (("Paid is not in service", "Pagado no es en servicio"),
     ("The last bill can be paid before anyone uses what was built. No open source records the opening day.", "La última factura puede pagarse antes de que alguien use lo que se construyó. Ninguna fuente abierta registra el día en que abre.")),
    (("A balance is not money lost", "Un saldo no es dinero perdido"),
     ("A balance says an amount had not been paid out on the day the record was read. It does not say why, and it does not say the money is gone.", "Un saldo dice que un monto no se había desembolsado el día en que se leyó el registro. No dice por qué, y no dice que el dinero ya no está.")),
    (("A reduction is not a payment sent back", "Una reducción no es un pago devuelto"),
     ("A reduction lowers the amount a federal agency had committed. It is a change to money not yet paid out, and the record does not give the reason.", "Una reducción baja el monto que una agencia federal había comprometido. Es un cambio a dinero que todavía no se había desembolsado, y el registro no da la razón.")),
    (("An audit finding is not a verdict", "Un hallazgo de auditoría no es un veredicto"),
     ("A finding says the auditor saw a rule or a control that was not followed. It can be a late report or a missing record. It does not judge intent.", "Un hallazgo dice que el auditor vio una regla o un control que no se siguió. Puede ser un informe tardío o un documento que falta. No juzga la intención.")),
    (("The same fiscal year is not the same months", "El mismo año fiscal no son los mismos meses"),
     ("The Commonwealth's fiscal year and the federal one share a name and differ by three months.", "El año fiscal del Gobierno de Puerto Rico y el federal comparten nombre y difieren por tres meses.")),
]

# Questions to ask of a figure: (question, why it matters).
QUESTIONS = [
    (("Which stage is it in?", "¿En qué etapa está?"),
     ("Approved, obligated, paid or closed. Compare only figures of the same stage.", "Aprobado, obligado, pagado o cerrado. Compare solo cifras de la misma etapa.")),
    (("Whose fiscal year is it?", "¿De quién es el año fiscal?"),
     ("July to June for the Commonwealth, October to September for the federal government.", "De julio a junio para el Gobierno de Puerto Rico, de octubre a septiembre para el gobierno federal.")),
    (("Who reports it, and when was it read?", "¿Quién la informa, y cuándo se leyó?"),
     ("An agency, the Treasury, a federal record or an auditor. Records change after the day they are read.", "Una agencia, Hacienda, un registro federal o un auditor. Los registros cambian después del día en que se leen.")),
    (("Is it a service or a work?", "¿Es un servicio o una obra?"),
     ("A service is paid as it is given. A work is paid over years.", "Un servicio se paga mientras se da. Una obra se paga a lo largo de años.")),
    (("What does it leave out?", "¿Qué deja fuera?"),
     ("The contracts signed here, whether the result is in use, and the reasons.", "Los contratos firmados aquí, si el resultado está en uso, y las razones.")),
]

# Where to see each idea in the figures: (what to look for, stage, link text, address).
SEE = [
    (("What the Commonwealth approved for a year and what agencies reported spent", "Lo que el Gobierno de Puerto Rico aprobó para un año y lo que las agencias informaron como gastado"),
     ("Approval to spending", "De la aprobación al gasto"), ("Budget and public spending, section 1", "Presupuesto y gasto público, sección 1"), "public-spending.html#gap"),
    (("Federal money obligated to Puerto Rico and paid out, year by year", "El dinero federal obligado a Puerto Rico y desembolsado, año por año"),
     ("Award and outlay", "Adjudicación y desembolso"), ("Budget and public spending, section 5", "Presupuesto y gasto público, sección 5"), "public-spending.html#federal"),
    (("Disaster projects by how far along they are", "Los proyectos por desastres según lo avanzados que están"),
     ("Obligation to closeout", "De la obligación al cierre"), ("Budget and public spending, section 8", "Presupuesto y gasto público, sección 8"), "public-spending.html#fema"),
    (("Grants whose time ended with a balance not yet paid out", "Subvenciones cuyo tiempo terminó con un saldo sin desembolsar"),
     ("End of the period of performance", "Fin del período de ejecución"), ("Federal grants, section 3", "Subvenciones federales, sección 3"), "unused-funds.html#years"),
    (("Amounts lowered after the award", "Montos reducidos después de la adjudicación"),
     ("Closeout", "Cierre"), ("Federal grants, section 5", "Subvenciones federales, sección 5"), "unused-funds.html#taken"),
    (("What the yearly audits found, and what they found again", "Lo que encontraron las auditorías anuales, y lo que volvieron a encontrar"),
     ("After the spending", "Después del gasto"), ("Federal grants, section 6", "Subvenciones federales, sección 6"), "unused-funds.html#findings"),
    (("Disaster money obligated per resident, by municipio", "El dinero por desastres obligado por residente, por municipio"),
     ("Obligation", "Obligación"), ("Disaster funding and need, section 1", "Fondos por desastres y necesidad, sección 1"), "public-money.html#compare"),
]

# Check what you learned: (question, answer). The answer opens when the reader asks for it; the browser does it, with no script.
CHECK = [
    (("A report says an agency has 90 percent of its budget approved and 40 percent spent with two months left in the year. What can you say, and what can you not?",
      "Un informe dice que una agencia tiene el 90 por ciento de su presupuesto aprobado y el 40 por ciento gastado cuando faltan dos meses del año. ¿Qué se puede decir, y qué no?"),
     ("You can say that less than half of what was approved had been paid. You cannot say how much is under contract, because obligated sits between the two and the figure does not give it. You also cannot say why.",
      "Se puede decir que menos de la mitad de lo aprobado se había pagado. No se puede decir cuánto está bajo contrato, porque lo obligado queda entre los dos y la cifra no lo da. Tampoco se puede decir por qué.")),
    (("A federal grant for a bridge shows a small share paid out three years after the award. Is that a problem?",
      "Una subvención federal para un puente muestra una proporción pequeña desembolsada tres años después de la adjudicación. ¿Es un problema?"),
     ("The figure alone does not say. A work is paid over years, so a small share is normal early on. You would need the period of performance and the contracts signed here, and the federal record does not show the contracts.",
      "La cifra sola no lo dice. Una obra se paga a lo largo de años, así que una proporción pequeña es normal al principio. Haría falta el período de ejecución y los contratos firmados aquí, y el registro federal no muestra los contratos.")),
    (("Someone compares the Commonwealth's fiscal year 2027 with the federal fiscal year 2027. What is wrong?",
      "Alguien compara el año fiscal 2027 del Gobierno de Puerto Rico con el año fiscal 2027 federal. ¿Qué está mal?"),
     ("They do not cover the same months. The Commonwealth's year ends in June and the federal one in September.",
      "No cubren los mismos meses. El año del Gobierno de Puerto Rico termina en junio y el federal en septiembre.")),
    (("A school repair is fully paid. Is the school open?",
      "La reparación de una escuela está pagada por completo. ¿Está abierta la escuela?"),
     ("The data cannot say. Paid is the last stage open data reach. In service is the stage no open source records.",
      "Los datos no lo pueden decir. Pagado es la última etapa a la que llegan los datos abiertos. En servicio es la etapa que ninguna fuente abierta registra.")),
]

# Every statement of the page rests on one of these: (name, what it supports, address).
SOURCES = [
    (("PROMESA, section 202 (Public Law 114-187; 48 U.S.C. 2142).", "PROMESA, sección 202 (Ley Pública 114-187; 48 U.S.C. 2142)."),
     ("How the Commonwealth budget is proposed, adopted and certified, and what the Oversight Board can do when a budget does not follow the fiscal plan.", "Cómo se propone, se adopta y se certifica el presupuesto del Gobierno de Puerto Rico, y lo que puede hacer la Junta de Supervisión Fiscal cuando un presupuesto no cumple con el plan fiscal."),
     "https://www.govinfo.gov/content/pkg/PLAW-114publ187/html/PLAW-114publ187.htm"),
    (("Office of Management and Budget, Manual of the Budget Process (updated 18 November 2025).", "Oficina de Gerencia y Presupuesto, Manual del Proceso Presupuestario (actualizado el 18 de noviembre de 2025)."),
     ("The ten stages of the budget process, the meaning of proposed, approved and spent budget, the reserves, and the rule on money of earlier fiscal years by kind of fund.", "Las diez etapas del proceso presupuestario, lo que significan presupuesto propuesto, aprobado y gastado, las reservas, y la regla sobre el dinero de años fiscales anteriores según la clase de fondo."),
     "https://gestion-presupuestaria.ogp.pr.gov/"),
    (("Act 147 of 1980, Organic Act of the Office of Management and Budget.", "Ley 147 de 1980, Ley Orgánica de la Oficina de Gerencia y Presupuesto."),
     ("The Office prepares the Governor's budget request and follows how the budget is carried out.", "La Oficina prepara la petición presupuestaria del Gobernador y da seguimiento a la ejecución del presupuesto."),
     "https://bvirtualogp.pr.gov/ogp/Bvirtual/LeyesOrganicas/PDF/147-1980.pdf"),
    (("Act 230 of 1974, Government Accounting Act of Puerto Rico.", "Ley 230 de 1974, Ley de Contabilidad del Gobierno de Puerto Rico."),
     ("The Secretary of the Treasury keeps the central accounts and sets how payments are made.", "El Secretario de Hacienda lleva la contabilidad central y establece cómo se hacen los pagos."),
     "https://hacienda.pr.gov/node/4680"),
    (("Act 73 of 2019, General Services Administration Act for the Centralization of Government Purchases.", "Ley 73 de 2019, Ley de la Administración de Servicios Generales para la Centralización de las Compras del Gobierno."),
     ("Government purchases of goods, works and services go through the General Services Administration.", "Las compras de bienes, obras y servicios del gobierno pasan por la Administración de Servicios Generales."),
     "https://docs.pr.gov/files/OGP/website_Federales/Local_Guidance/Law-of-the-PR-General-Services-Administration.pdf"),
    (("US Government Accountability Office, A Glossary of Terms Used in the Federal Budget Process (GAO-05-734SP).", "Oficina de Rendición de Cuentas del Gobierno de EE. UU., A Glossary of Terms Used in the Federal Budget Process (GAO-05-734SP)."),
     ("Appropriation, obligation, de-obligation and outlay.", "Asignación, obligación, desobligación y desembolso."),
     "https://www.gao.gov/products/gao-05-734sp"),
    (("Code of Federal Regulations, 2 CFR 200.1 and 200.344.", "Código de Regulaciones Federales, 2 CFR 200.1 y 200.344."),
     ("Period of performance and closeout: the 120 days to pay and report, and the agency's effort to close a grant within a year.", "Período de ejecución y cierre: los 120 días para pagar e informar, y el esfuerzo de la agencia por cerrar una subvención dentro de un año."),
     "https://www.ecfr.gov/current/title-2/section-200.344"),
    (("Code of Federal Regulations, 2 CFR 200.516.", "Código de Regulaciones Federales, 2 CFR 200.516."),
     ("What an auditor must report as an audit finding.", "Lo que un auditor tiene que informar como hallazgo de auditoría."),
     "https://www.ecfr.gov/current/title-2/section-200.516"),
    (("31 U.S.C. 1102, and the National Conference of State Legislatures.", "31 U.S.C. 1102, y la Conferencia Nacional de Legislaturas Estatales."),
     ("The federal fiscal year begins on October 1. Forty-six states begin theirs on July 1; New York, Texas, Alabama and Michigan do not.", "El año fiscal federal comienza el 1 de octubre. Cuarenta y seis estados comienzan el suyo el 1 de julio; Nueva York, Texas, Alabama y Michigan no."),
     "https://www.ncsl.org/resources/details/states-face-minimal-turbulence-as-new-fiscal-year-takes-off"),
]

MONTHS = [("Jul", "jul"), ("Aug", "ago"), ("Sep", "sep"), ("Oct", "oct"), ("Nov", "nov"), ("Dec", "dic"), ("Jan", "ene"), ("Feb", "feb"), ("Mar", "mar"), ("Apr", "abr"), ("May", "may"), ("Jun", "jun"),
          ("Jul", "jul"), ("Aug", "ago"), ("Sep", "sep")]


def build():
    ref = (ROOT / "site" / "unused-funds.html").read_text(encoding="utf-8")
    ver = lambda name: re.search(re.escape(name) + r"\?v=(\d+)", ref).group(1)
    I18N_V = 68   # the ?v= of js/i18n.js also versions this page's Spanish bundle: raise it when the page's strings change (docs/i18n.md, rule 12)
    icons = sorted(set(re.search(r"icon_names=([a-z0-9_,]+)", ref).group(1).split(",")) | {s[0] for s in STAGES} | {"info", "route", "groups", "account_balance", "calendar_month", "compare_arrows", "help", "map", "menu_book", "arrow_downward", "school", "footprint", "rule", "quiz", "query_stats", "difference", "account_tree", "dark_mode", "explore", "grid_view", "light_mode"})
    title = t("Knowledge Area · How public money moves", "Área de conocimiento · Cómo se mueve el dinero público")

    steps = "\n".join(
        f'      <li class="mc-step{" mc-gap" if i == len(STAGES) - 1 else ""}"><span class="ms-icon" aria-hidden="true">{icon}</span><div><b>{t(*name)}</b><p>{t(*what)}</p><small>{t(*who)}</small></div></li>'
        for i, (icon, name, what, who) in enumerate(STAGES))
    fed = "\n".join(f'      <li class="mc-fstep"><div><b>{t(*name)}</b><p>{t(*what)}</p></div></li>' for name, what in FEDERAL)
    month_cells = "".join(f'<span class="mc-m">{t(*m)}</span>' for m in MONTHS)
    pages = "\n".join(f'        <tr><th scope="row"><a href="{href}">{t(*name)}</a></th><td>{t(*what)}</td><td>{t(*stage)}</td></tr>' for name, href, what, stage in PAGES)
    learn = "\n".join(f"      <li>{t(*x)}</li>" for x in LEARN)
    example = "\n".join(
        f'        <tr><td>{t(*what)}</td><td>' + (f'<a href="{href}">{t(*where)}</a>' if href else f'<span class="mc-none">{t(*where)}</span>') + "</td></tr>"
        for what, where, href in EXAMPLE)
    confused = "\n".join(f'      <div class="card mc-kind mc-not"><h3>{t(*a)}</h3><p>{t(*b)}</p></div>' for a, b in CONFUSED)
    questions = "\n".join(f"      <li><b>{t(*q)}</b><p>{t(*why)}</p></li>" for q, why in QUESTIONS)
    see = "\n".join(f'        <tr><td>{t(*what)}</td><td>{t(*stage)}</td><td><a href="{href}">{t(*name)}</a></td></tr>' for what, stage, name, href in SEE)
    check = "\n".join(f'    <details class="card mc-check"><summary>{t(*q)}</summary><p>{t(*a)}</p></details>' for q, a in CHECK)
    sources = "\n".join(f'    <div class="note"><b>{t(*name)}</b> {t(*what)}</div>\n    <p class="pm-small mc-src" data-t="skip"><a href="{html.escape(url)}" target="_blank" rel="noopener">{html.escape(url)}</a></p>' for name, what, url in SOURCES)

    page = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<meta name="description" content="{t("The path of public money in Puerto Rico, from the design of a budget to a service in use: the stages, who does each one, the federal side, and what open data do not show.", "El camino del dinero público en Puerto Rico, desde el diseño de un presupuesto hasta un servicio en uso: las etapas, quién hace cada una, el lado federal y lo que los datos abiertos no muestran.")}">
<meta name="robots" content="noindex, nofollow">
<meta name="theme-color" content="#FFFFFF">
<link rel="icon" href="img/fpr-mark.png">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Material+Symbols+Rounded:opsz,wght,FILL,GRAD@24,400,1,0&icon_names={",".join(icons)}&display=block">
<link rel="stylesheet" href="css/twin.css?v={ver("css/twin.css")}">
<link rel="stylesheet" href="css/housing.css?v={ver("css/housing.css")}">
<link rel="stylesheet" href="css/public_money.css?v={ver("css/public_money.css")}">
<link rel="stylesheet" href="css/money_cycle.css?v=3">
<link rel="stylesheet" href="css/chat.css?v={ver("css/chat.css")}">
<link rel="stylesheet" href="css/ws.css?v=2">
<script src="js/i18n.js?v={max(int(ver("js/i18n.js")), I18N_V)}" data-page="moneycycle"></script>
</head>
<body class="research">
<a class="skip" href="#now">{t("Skip to the content", "Ir al contenido")}</a>
<header class="topbar">
  <a class="logo" href="index.html" title="{t("PR Data Observatory home", "Inicio del Observatorio de Datos de PR")}"><img src="img/fpr-logo.png" alt="{t("Foundation for Puerto Rico. PR Data Observatory home", "Foundation for Puerto Rico. Inicio del Observatorio de Datos de PR")}"></a>
  <div class="brand"><b>{title}</b><span>{t("From the design of a budget to a service in use", "Del diseño de un presupuesto a un servicio en uso")}</span></div>
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
  <span class="ka-tabs" role="group" aria-label="{t("Knowledge Area", "Área de conocimiento")}" data-ka="moneycycle"></span><span class="ka-sep" aria-hidden="true"></span>
  <a href="#now">{t("Now", "Ahora")}</a><a href="#stages">{t("The stages", "Las etapas")}</a><a href="#who">{t("Who does what", "Quién hace qué")}</a><a href="#federal">{t("The federal side", "El lado federal")}</a><a href="#calendars">{t("Two calendars", "Dos calendarios")}</a><a href="#pace">{t("Services and works", "Servicios y obras")}</a><a href="#example">{t("An example", "Un ejemplo")}</a><a href="#gap">{t("What data do not show", "Lo que los datos no muestran")}</a><a href="#confused">{t("Often confused", "Lo que se confunde")}</a><a href="#questions">{t("Five questions", "Cinco preguntas")}</a><a href="#pages">{t("See it in the data", "Véalo en los datos")}</a><a href="#check">{t("Test yourself", "Compruebe")}</a><a href="#sources">{t("Sources", "Fuentes")}</a>
</nav>

<main class="page">
  <div class="note caution review-note" role="note" data-ka-note></div>

  <section class="hero" id="now">
    <div class="eyebrow">{t("Knowledge Area · Public money", "Área de conocimiento · Dinero público")}</div>
    <h1>{t("How public money moves", "Cómo se mueve el dinero público")}</h1>
    <p class="lede">{t("Public money does not go from a budget to a service in one step. It is designed, requested, approved, assigned, committed, carried out and paid, and only then does someone use what it bought. Each step has its own word and its own figure, and a number means little until you know which step it is. This page explains the steps, so the other public money pages can be read with care.", "El dinero público no va de un presupuesto a un servicio en un solo paso. Se diseña, se solicita, se aprueba, se asigna, se compromete, se ejecuta y se paga, y solo entonces alguien usa lo que se compró. Cada paso tiene su palabra y su cifra, y un número dice poco hasta que se sabe de qué paso es. Esta página explica los pasos, para que las demás páginas de dinero público se lean con cuidado.")}</p>
    <div class="note"><b>{t("A page that explains.", "Una página que explica.")}</b> {t("It has no figures of its own. Every statement rests on a law, a rule or an official glossary listed at the end, and the page gives no opinion on how the process should work.", "No tiene cifras propias. Cada afirmación se apoya en una ley, una regla o un glosario oficial que aparece al final, y la página no opina sobre cómo debería funcionar el proceso.")}</div>
    <div class="card mc-learn">
      <h2 class="mc-h">{t("After this page you can", "Después de esta página usted puede")}</h2>
      <ul>
{learn}
      </ul>
    </div>
  </section>

  <section class="block" id="stages">
    <h2><span class="ms-icon" aria-hidden="true">route</span>{t("1 · The stages", "1 · Las etapas")}</h2>
    <p class="pm-p">{t("The path of the Commonwealth's own budget, from top to bottom. The name of each stage is the word the other pages use.", "El camino del presupuesto propio del Gobierno de Puerto Rico, de arriba hacia abajo. El nombre de cada etapa es la palabra que usan las demás páginas.")}</p>
    <ol class="mc-path">
{steps}
    </ol>
    <div class="note caution"><b>{t("Three words that are not the same.", "Tres palabras que no son lo mismo.")}</b> {t("Approved is what an agency may spend. Obligated is what it has committed by contract. Spent is what has been paid. A year can end with money approved and never obligated, or obligated and not yet paid.", "Aprobado es lo que una agencia puede gastar. Obligado es lo que ha comprometido por contrato. Gastado es lo que se ha pagado. Un año puede terminar con dinero aprobado que nunca se obligó, u obligado que todavía no se ha pagado.")}</div>
  </section>

  <section class="block" id="who">
    <h2><span class="ms-icon" aria-hidden="true">groups</span>{t("2 · Who does what", "2 · Quién hace qué")}</h2>
    <div class="card pm-tablebox mc-all"><table class="pm-table mc-table">
      <caption>{t("The bodies of the Commonwealth's budget process and their part in it", "Las entidades del proceso presupuestario del Gobierno de Puerto Rico y su parte en él")}</caption>
      <thead><tr><th scope="col">{t("Body", "Entidad")}</th><th scope="col">{t("Its part", "Su parte")}</th></tr></thead>
      <tbody>
        <tr><th scope="row">{t("Oversight Board", "Junta de Supervisión Fiscal")}</th><td>{t("It sets the calendar of the budget each year, reviews the Governor's proposal and certifies the budget that follows the fiscal plan. The process begins and ends with the Board.", "Establece cada año el calendario del presupuesto, revisa la propuesta del Gobernador y certifica el presupuesto que cumple con el plan fiscal. El proceso empieza y termina con la Junta.")}</td></tr>
        <tr><th scope="row">{t("Office of Management and Budget", "Oficina de Gerencia y Presupuesto")}</th><td>{t("It prepares the Governor's budget request with the agencies and follows how the budget is carried out during the year.", "Prepara con las agencias la petición presupuestaria del Gobernador y da seguimiento a la ejecución del presupuesto durante el año.")}</td></tr>
        <tr><th scope="row">{t("Legislature", "Asamblea Legislativa")}</th><td>{t("It adopts the budget.", "Adopta el presupuesto.")}</td></tr>
        <tr><th scope="row">{t("Department of the Treasury (Hacienda)", "Departamento de Hacienda")}</th><td>{t("It keeps the central accounts and makes the payments. It is the government's cashier, not the body that decides what to spend on.", "Lleva la contabilidad central y hace los pagos. Es el cajero del gobierno, no la entidad que decide en qué se gasta.")}</td></tr>
        <tr><th scope="row">{t("General Services Administration", "Administración de Servicios Generales")}</th><td>{t("Government purchases of goods, works and services go through it.", "Las compras de bienes, obras y servicios del gobierno pasan por ella.")}</td></tr>
        <tr><th scope="row">{t("The agency", "La agencia")}</th><td>{t("It designs its request, commits its money and carries out the work.", "Diseña su petición, compromete su dinero y ejecuta el trabajo.")}</td></tr>
      </tbody>
    </table></div>
  </section>

  <section class="block" id="federal">
    <h2><span class="ms-icon" aria-hidden="true">account_balance</span>{t("3 · The federal side", "3 · El lado federal")}</h2>
    <p class="pm-p">{t("Federal money follows its own path, and it meets the Commonwealth's in the middle. A federal grant is obligated twice: once by the federal agency, when it awards the grant, and again by the recipient here, when it signs the contracts that use it.", "El dinero federal sigue su propio camino, y se encuentra con el del Gobierno de Puerto Rico a mitad de camino. Una subvención federal se obliga dos veces: una vez por la agencia federal, cuando la adjudica, y otra por el receptor aquí, cuando firma los contratos que la usan.")}</p>
    <ol class="mc-path mc-fed">
{fed}
    </ol>
    <div class="note"><b>{t("Why this matters for the numbers.", "Por qué importa para los números.")}</b> {t("The federal record (USAspending) shows the award and the outlays. It does not show the second obligation, the one made here, so it cannot say how much of a grant is already under contract.", "El registro federal (USAspending) muestra la adjudicación y los desembolsos. No muestra la segunda obligación, la que se hace aquí, así que no puede decir cuánto de una subvención ya está bajo contrato.")}</div>
  </section>

  <section class="block" id="calendars">
    <h2><span class="ms-icon" aria-hidden="true">calendar_month</span>{t("4 · Two calendars", "4 · Dos calendarios")}</h2>
    <p class="pm-p">{t("The Commonwealth's fiscal year runs from July to June. The federal one runs from October to September. Both take the name of the year in which they end, so fiscal year 2027 covers different months in each.", "El año fiscal del Gobierno de Puerto Rico va de julio a junio. El federal va de octubre a septiembre. Los dos llevan el nombre del año en que terminan, así que el año fiscal 2027 cubre meses distintos en cada uno.")}</p>
    <div class="card mc-cal" role="img" aria-label="{t("Two bars over fifteen months: the Commonwealth's fiscal year covers July to June; the federal fiscal year covers October to September, three months later.", "Dos barras sobre quince meses: el año fiscal del Gobierno de Puerto Rico cubre de julio a junio; el año fiscal federal cubre de octubre a septiembre, tres meses después.")}">
      <div class="mc-months" aria-hidden="true">{month_cells}</div>
      <div class="mc-bar mc-pr" aria-hidden="true"><span>{t("Commonwealth fiscal year", "Año fiscal del Gobierno de Puerto Rico")}</span></div>
      <div class="mc-bar mc-us" aria-hidden="true"><span>{t("Federal fiscal year", "Año fiscal federal")}</span></div>
    </div>
    <p class="pm-p">{t("Forty-six states begin their fiscal year on July 1, as Puerto Rico does, so the three-month gap with the federal year is common. It still has a cost: an agency that depends on a federal grant writes its Commonwealth request before it knows what the federal government will give it. On the pages, never compare a Commonwealth figure and a federal figure of the same fiscal year as if they covered the same months.", "Cuarenta y seis estados comienzan su año fiscal el 1 de julio, igual que Puerto Rico, así que la diferencia de tres meses con el año federal es común. Aun así tiene un costo: una agencia que depende de una subvención federal escribe su petición al Gobierno de Puerto Rico antes de saber lo que le dará el gobierno federal. En las páginas, nunca compare una cifra estatal y una federal del mismo año fiscal como si cubrieran los mismos meses.")}</p>
  </section>

  <section class="block" id="pace">
    <h2><span class="ms-icon" aria-hidden="true">compare_arrows</span>{t("5 · Services and works move at different speeds", "5 · Los servicios y las obras van a velocidades distintas")}</h2>
    <div class="mc-two">
      <div class="card mc-kind"><h3>{t("A service", "Un servicio")}</h3><p>{t("Money for a service, such as child care or job training, is paid as the service is given. Payment and delivery go together, month by month. If little has been paid late in the grant, little has been delivered.", "El dinero para un servicio, como el cuido de niños o el adiestramiento para empleo, se paga mientras se da el servicio. El pago y la entrega van juntos, mes a mes. Si se ha pagado poco al final de la subvención, se ha entregado poco.")}</p></div>
      <div class="card mc-kind"><h3>{t("A work", "Una obra")}</h3><p>{t("Money for a bridge, a school or a dredging is committed years before the work is finished. It is normal for a large work to show little paid for a long time, and to be in service long after the last payment.", "El dinero para un puente, una escuela o un dragado se compromete años antes de que termine la obra. Es normal que una obra grande muestre poco pagado por mucho tiempo, y que entre en servicio mucho después del último pago.")}</p></div>
    </div>
    <p class="pm-p">{t("So the same share paid out means different things. Read it next to the kind of program before drawing a conclusion.", "Por eso la misma proporción desembolsada significa cosas distintas. Léala junto a la clase de programa antes de sacar una conclusión.")}</p>
  </section>

  <section class="block" id="example">
    <h2><span class="ms-icon" aria-hidden="true">footprint</span>{t("6 · Follow one grant from start to end", "6 · Siga una subvención de principio a fin")}</h2>
    <div class="note"><b>{t("A made-up example.", "Un ejemplo inventado.")}</b> {t("This grant does not exist. It shows the order of the steps and where each one can be seen, with no amount and no real place.", "Esta subvención no existe. Muestra el orden de los pasos y dónde se puede ver cada uno, sin monto y sin un lugar real.")}</div>
    <div class="card pm-tablebox mc-all"><table class="pm-table mc-table mc-steps">
      <caption>{t("A federal grant to repair a community center, step by step", "Una subvención federal para reparar un centro comunitario, paso a paso")}</caption>
      <thead><tr><th scope="col">{t("What happens", "Qué pasa")}</th><th scope="col">{t("Where you can see it", "Dónde se puede ver")}</th></tr></thead>
      <tbody>
{example}
      </tbody>
    </table></div>
    <p class="pm-p">{t("Count the steps that no page can show: the design, the contract signed here, the bills, and the day the center opens. The figures on the other pages are the steps in between.", "Cuente los pasos que ninguna página puede mostrar: el diseño, el contrato firmado aquí, las facturas y el día en que abre el centro. Las cifras de las otras páginas son los pasos intermedios.")}</p>
  </section>

  <section class="block" id="gap">
    <h2><span class="ms-icon" aria-hidden="true">help</span>{t("7 · What open data do not show", "7 · Lo que los datos abiertos no muestran")}</h2>
    <div class="note caution"><b>{t("The last stage has no data.", "La última etapa no tiene datos.")}</b> {t("No open source records whether what was paid for is in service: whether the school opened, the clinic sees patients or the office is in use. Paid is the last stage the data reach. A project can be fully paid and not yet serve anyone.", "Ninguna fuente abierta registra si lo que se pagó está en servicio: si la escuela abrió, si la clínica atiende pacientes o si la oficina está en uso. Pagado es la última etapa a la que llegan los datos. Un proyecto puede estar pagado por completo y todavía no servirle a nadie.")}</div>
    <div class="note"><b>{t("Also missing.", "También falta.")}</b> {t("The second obligation of federal money, made by the recipient here. Spending as it happens: the Commonwealth's figures of what was spent are what agencies report at the end of a year. And the reasons: why money was not committed, or why an amount was lowered.", "La segunda obligación del dinero federal, la que hace el receptor aquí. El gasto mientras ocurre: las cifras de lo gastado del Gobierno de Puerto Rico son lo que informan las agencias al final de un año. Y las razones: por qué no se comprometió un dinero, o por qué se bajó un monto.")}</div>
  </section>

  <section class="block" id="confused">
    <h2><span class="ms-icon" aria-hidden="true">difference</span>{t("8 · Often confused", "8 · Lo que se confunde")}</h2>
    <p class="pm-p">{t("Seven pairs that are easy to read as the same thing. Each one changes what a figure means.", "Siete pares que es fácil leer como la misma cosa. Cada uno cambia lo que significa una cifra.")}</p>
    <div class="mc-two">
{confused}
    </div>
  </section>

  <section class="block" id="questions">
    <h2><span class="ms-icon" aria-hidden="true">rule</span>{t("9 · Five questions to ask a figure", "9 · Cinco preguntas para hacerle a una cifra")}</h2>
    <p class="pm-p">{t("Use them on any figure about public money: on these pages, in a report or in the news.", "Úselas con cualquier cifra de dinero público: en estas páginas, en un informe o en las noticias.")}</p>
    <ol class="mc-ask">
{questions}
    </ol>
  </section>

  <section class="block" id="pages">
    <h2><span class="ms-icon" aria-hidden="true">query_stats</span>{t("10 · See it in the data", "10 · Véalo en los datos")}</h2>
    <p class="pm-p">{t("Each idea of this page has a chart or a table on another page. Open one and name its stage before you read its figure.", "Cada idea de esta página tiene un gráfico o una tabla en otra página. Abra uno y nombre su etapa antes de leer su cifra.")}</p>
    <div class="card pm-tablebox mc-all"><table class="pm-table mc-table">
      <caption>{t("Where to see each stage in the figures", "Dónde ver cada etapa en las cifras")}</caption>
      <thead><tr><th scope="col">{t("What to look for", "Qué buscar")}</th><th scope="col">{t("Stage", "Etapa")}</th><th scope="col">{t("Where", "Dónde")}</th></tr></thead>
      <tbody>
{see}
      </tbody>
    </table></div>
    <h3 class="mc-h">{t("The three pages", "Las tres páginas")}</h3>
    <div class="card pm-tablebox mc-all"><table class="pm-table mc-table">
      <caption>{t("The public money pages and the stages their figures are in", "Las páginas de dinero público y las etapas en que están sus cifras")}</caption>
      <thead><tr><th scope="col">{t("Page", "Página")}</th><th scope="col">{t("What it shows", "Qué muestra")}</th><th scope="col">{t("Stages", "Etapas")}</th></tr></thead>
      <tbody>
{pages}
      </tbody>
    </table></div>
  </section>

  <section class="block" id="check">
    <h2><span class="ms-icon" aria-hidden="true">quiz</span>{t("11 · Check what you learned", "11 · Compruebe lo que aprendió")}</h2>
    <p class="pm-p">{t("Four cases. Think of your answer, then open ours.", "Cuatro casos. Piense su respuesta y luego abra la nuestra.")}</p>
{check}
  </section>

  <section class="block" id="sources">
    <h2><span class="ms-icon" aria-hidden="true">menu_book</span>{t("Sources", "Fuentes")}</h2>
{sources}
    <div class="note"><b>{t("How to cite this page.", "Cómo citar esta página.")}</b> {t("Foundation for Puerto Rico, Knowledge Area: How public money moves, PR Data Observatory, November 2026 (draft).", "Foundation for Puerto Rico, Área de conocimiento: Cómo se mueve el dinero público, Observatorio de Datos de PR, noviembre de 2026 (borrador).")}</div>
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
        if lead not in {html.unescape(x) for x in re.findall(r"<b>([^<]*)</b><p>", page)}:
            ES.pop(lead, None)
        ES.pop(body, None)
    (ROOT / "site" / "money-cycle.html").write_text(page, encoding="utf-8", newline="\n")
    es = {"_about": "The How public money moves page of the Knowledge Area (money-cycle.html). Written by docs/analysis/money-cycle-2026-11/make_page.py from its (English, Spanish) pairs: edit them there, not here."}
    es.update(ES)
    (ROOT / "i18n_src" / "es" / "money_cycle.json").write_text(json.dumps(es, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(f"wrote site/money-cycle.html and i18n_src/es/money_cycle.json ({len(ES)} strings)")


if __name__ == "__main__":
    build()
