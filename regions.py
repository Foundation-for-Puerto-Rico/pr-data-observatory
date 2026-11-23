"""The regions the observatory offers as groups of whole municipios: site/data/geo/regions.json (2026-10-31).

    python regions.py            # writes site/data/geo/regions.json from the crosswalk (geo.py) and the lists below
    python regions.py --check    # rebuilds in memory and exits 1 when the published file differs

Two kinds:
  planning  regions FPR works with. Today: the Eastern Region of the Eastern Region Strategic Vision (ERSV), 15 municipios
            (FPR, Eastern Region Economic Development Council, "Human Capital Demographic Profile", 2025).
  tourism   the Puerto Rico Tourism Company's seven tourism regions, read from the crosswalk (docs/geography.md).

A region is a list of municipio codes; its figures are always built from its municipios (sums of counts, pooled rates), never stored.
The map's Region tab, the regional area profile (profile.html?region=) and the Women in the labor force page read this file.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "site" / "data" / "geo" / "regions.json"

ERSV = {
    "72029": "Canóvanas", "72037": "Ceiba", "72049": "Culebra", "72053": "Fajardo", "72069": "Humacao",
    "72077": "Juncos", "72085": "Las Piedras", "72087": "Loíza", "72089": "Luquillo", "72095": "Maunabo",
    "72103": "Naguabo", "72119": "Río Grande", "72129": "San Lorenzo", "72147": "Vieques", "72151": "Yabucoa",
}
PLANNING = [
    {"id": "ersv", "kind": "planning", "name": {"en": "Eastern Region (ERSV)", "es": "Región Este (ERSV)"}, "ids": sorted(ERSV),
     "source": {"en": "FPR, Eastern Region Strategic Vision, Human Capital chapter", "es": "FPR, Visión Estratégica de la Región Este, capítulo de Capital Humano"}},
]


def build():
    cw = json.loads((ROOT / "site" / "data" / "geo" / "crosswalk.json").read_text(encoding="utf-8"))
    names = {u[0]: u[2] for u in cw["units"]["municipio"]}
    for g, n in ERSV.items():
        if names.get(g) != n:
            raise SystemExit(f"regions: ERSV municipio {g}: the crosswalk says {names.get(g)!r}, the list says {n!r}")
    tourism = [{"id": r[0], "kind": "tourism", "name": {"en": r[3], "es": r[2]}, "ids": sorted(u[0] for u in cw["units"]["municipio"] if u[1] == r[0]),
                "source": {"en": "Puerto Rico Tourism Company tourism regions", "es": "Regiones turísticas de la Compañía de Turismo de Puerto Rico"}}
               for r in sorted(cw["units"]["region"], key=lambda r: r[2])]
    regions = PLANNING + tourism
    for r in regions:
        r["names"] = [names[g] for g in r["ids"]]
    return {"version": "1", "regions": regions}


def main(argv=None):
    check = "--check" in (argv if argv is not None else sys.argv[1:])
    doc = build()
    text = json.dumps(doc, ensure_ascii=False, separators=(",", ":"))
    if check:
        same = OUT.exists() and OUT.read_text(encoding="utf-8") == text
        print("regions.json is current" if same else "regions.json differs: run python regions.py")
        return 0 if same else 1
    OUT.write_text(text, encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}: {len(doc['regions'])} regions")
    return 0


if __name__ == "__main__":
    sys.exit(main())
