"""One municipio's public money in one small file, for the "My municipio" section of the Public spending page (HANDOFF decision 109, step 5).

    python municipio_view.py           # build site/data/spending_municipio.json from the published files (no network)
    python municipio_view.py --check   # exit 1 when the published file is not what the published files give

Reads only files the observatory already publishes, so it adds no source:
- spending_pica.json: the capital plan by municipio, with the agency that runs each project line (planned, not obligated);
- spending_cdbgdr.json: the Department of Housing's CDBG-DR and CDBG-MIT subawards by municipio of the work (obligated);
- spending_fema_pa.json: FEMA Public Assistance by stage and age, the projects that name the municipio (obligated);
- economy_series.json: federal awards of every type by municipio of the work (fed_awards_total, obligated);
- audit_findings.json: the single audits of each municipio government and their findings (municipio_governments; HANDOFF decision 110, step 4).

For each of the 78 municipios: population; the capital plan's total and its three largest agencies; CDBG-DR subawards over the years read; FEMA
Public Assistance by stage, the median age of its open money and the dollars open more than five years; federal awards in the latest year and the
average of the last five; and the slug of the municipio's page on ABRE Tu Municipio (abretumunicipio.org/municipio/<slug>?year=<year>), which the
page links to for the municipal government's own finances (decision 109 (c): link, never copy). Island-wide context: the Statewide share of FEMA
Public Assistance and the CDBG-DR subawards that name no municipio, so the page can say how much of the money no municipio figure shows.
"""

import json
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).parent
D = ROOT / "site" / "data"
OUT = D / "spending_municipio.json"
ABRE_YEAR = 2024      # the latest year of ABRE Tu Municipio's Fiscal Health Index (checked 2026-11-17)


def slug(name):
    s = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower()
    return "-".join(s.split())


def load(name):
    return json.loads((D / name).read_text(encoding="utf-8"))


def build(check=False):
    pica, cd, fema, eco = load("spending_pica.json"), load("spending_cdbgdr.json"), load("spending_fema_pa.json"), load("economy_series.json")
    ids, names, pop = cd["geo"]["ids"], cd["geo"]["names"], cd["population"]
    assert pica["geo"]["ids"] == ids and fema["geo"]["ids"] == ids, "the Public spending files must share one municipio order"
    aud_doc = load("audit_findings.json")
    aud, aud_built = aud_doc["municipio_governments"], aud_doc["built"]
    fed = next(v for v in eco["vars"] if v["key"] == "fed_awards_total")
    eat = {str(g): i for i, g in enumerate(eco["geo"]["ids"])}
    fy = sorted(int(y) for y in fed["years"])
    last5 = [str(y) for y in fy[-5:]]
    rows = []
    for i, (g, n) in enumerate(zip(ids, names)):
        plan = sum(yr[i] for yr in pica["by_muni"])
        ag = sorted(((a, v[i]) for a, v, _unplaced in pica["by_agency"]), key=lambda x: -x[1])
        top = [[a, round(v)] for a, v in ag if v > 0][:3]
        e = eat[str(g)]
        rows.append({"id": g, "name": n, "pop": pop[i], "abre": slug(n),
                     "plan": round(plan), "plan_top": top,
                     "cdbgdr": round(sum(yr[i] for yr in cd["by_muni"])),
                     "fema_usd": fema["by_muni"]["usd"][i], "fema_count": fema["by_muni"]["count"][i],
                     "fema_age": fema["by_muni"]["median_age"][i], "fema_over5": fema["by_muni"]["over5_usd"][i],
                     "fed_last": round(fed["years"][str(fy[-1])][e]), "fed_avg5": round(sum(fed["years"][y][e] for y in last5) / len(last5)),
                     "audit": aud["by_code"].get(str(g), [0, 0, 0, None])})   # [audits filed, findings, repeated, latest audit year filed] of the municipio government
    doc = {"version": 1, "built": max(pica["built"], cd["built"], fema["built"], eco["built"], aud_built), "level": "municipio",
           "years": {"plan": [pica["years"][0], pica["years"][-1]], "cdbgdr": [cd["years"][0], cd["years"][-1]], "fed": [fy[-5], fy[-1]], "fema_read": fema["read"], "audit": [aud["years"][0], aud["years"][-1]]},
           "abre_year": ABRE_YEAR, "stages": fema["stages"], "geo": {"ids": ids, "names": names},
           "context": {"fema_statewide_usd": sum(fema["statewide"]["usd"]), "fema_total_usd": sum(fema["island"]["usd"]),
                       "cdbgdr_unplaced_usd": sum(cd["unplaced"]), "cdbgdr_subawards_usd": sum(cd["subawards"])},
           "municipios": rows}
    text = json.dumps(doc, ensure_ascii=False, separators=(",", ":"))
    if check:
        same = OUT.exists() and json.loads(OUT.read_text(encoding="utf-8")) == json.loads(text)
        print(f"  spending_municipio.json {'is current' if same else 'differs: run python municipio_view.py'}")
        return same
    OUT.write_text(text, encoding="utf-8", newline="\n")
    print(f"  wrote spending_municipio.json: {len(rows)} municipios, {OUT.stat().st_size / 1e3:.0f} KB")
    return doc


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if "--check" in argv:
        sys.exit(0 if build(check=True) else 1)
    build()


if __name__ == "__main__":
    main()
