# /// script
# requires-python = ">=3.11"
# dependencies = ["mcp>=2.3,<3"]
# ///
"""MCP server for the PR Data Observatory.

Gives Claude read access to the observatory's published data: the catalog, the
data dictionary and every per-municipio series, plus links that open the map
with the right layers on. It reads the same public JSON files the site serves,
so it needs no key and holds no data of its own.

Run it locally (Claude Desktop or Claude Code, stdio):
    uv run --script connector/observatory_mcp.py
Serve it over HTTP for claude.ai (streamable HTTP on /mcp):
    uv run --script connector/observatory_mcp.py --http --port 8000

Environment:
    OBSERVATORY_URL   site to read and link to (default https://observatory.foundationpr.org)
    OBSERVATORY_DATA  a local site/data folder to read instead of the site (tests, offline)
"""

import json
import os
import sys
import unicodedata
import urllib.parse
import urllib.request
from functools import lru_cache

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations

SITE = os.environ.get("OBSERVATORY_URL", "https://observatory.foundationpr.org").rstrip("/")
DATA = os.environ.get("OBSERVATORY_DATA")
PR_ID = "72"  # the Puerto Rico total row in every series file
READ_ONLY = ToolAnnotations(readOnlyHint=True, openWorldHint=False)

mcp = MCPServer(
    "observatorio-pr",
    instructions=(
        "PR Data Observatory (Foundation for Puerto Rico): open public data on Puerto Rico's "
        "78 municipios, by field (population, economy, housing, health, hazards, environment, "
        "infrastructure, public money and more). Start with search_datasets, then get_values, "
        "get_trend or municipality_profile. Before you report a number, read describe_dataset "
        "for its definition and cautions. State the year, the unit and the source of every "
        "figure, and say patterns, not causes. Give a map_link so readers can see the data. "
        "Reply in the user's language (Spanish when mixed)."
    ),
)


@lru_cache(maxsize=None)  # ponytail: cached for the life of the process; restart after a site build, or add a TTL if hosted long-running
def load(name: str):
    """Returns one published data file, parsed."""
    if DATA:
        with open(os.path.join(DATA, name), encoding="utf-8") as f:
            return json.load(f)
    req = urllib.request.Request(f"{SITE}/data/{name}", headers={"User-Agent": "observatorio-pr-mcp"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def fold(s: str) -> str:
    """Lowercase without accents, so "Mayaguez" finds "Mayagüez"."""
    return "".join(c for c in unicodedata.normalize("NFD", str(s).lower()) if unicodedata.category(c) != "Mn")


@lru_cache(maxsize=None)
def catalog():
    """Catalog rows as dicts, with the Spanish name added."""
    idx = load("catalog_index.json")["index"]
    es = load("dictionary_list_es.json").get("names", {})
    rows = [dict(zip(idx["fields"], r)) for r in idx["rows"]]
    for r in rows:
        r["name_es"] = es.get(r["id"])
    return rows


@lru_cache(maxsize=None)
def series():
    """Every per-municipio dataset with values: series key -> (var, geo, file)."""
    files = [f["file"] for f in load("registry.json")["files"] if f["file"].endswith("_series.json")]
    out = {}
    for name in files:
        d = load(name)
        for v in d["vars"]:
            if v.get("years") and v["key"] not in out:  # a var marked "from" another file may come without values
                out[v["key"]] = (v, d["geo"], name)
    # Catalog datasets kept outside the series files: municipio snapshot fields
    # (flood, transit access, tourism places) and census-block exposure counts.
    geo = load("economy_series.json")["geo"]
    munis = load("municipalities.json")
    expo = load("exposure_municipio.json")
    exp_at = {g: i for i, g in enumerate(expo["geo"]["ids"])}
    in_files = set(out)
    for r in catalog():
        if not (r["map"] and r["map"][0] == "econ") or r["map"][1] in in_files:
            continue
        key, field = r["map"][1], r["id"].split(".", 1)[1]
        year = str(r["years"][1]) if r["years"] else "2020"
        var = {"key": key, "label": r["name"], "unit": "", "sources": r["sources"] or [], "years": {}}
        if r["id"].startswith("municipalities.") and any(field in m for m in munis.values()):
            var["years"][year] = [munis.get(n, {}).get(field) for n in geo["names"]]
            out.setdefault(key, (var, geo, "municipalities.json"))
            out[r["id"]] = (var, geo, "municipalities.json")  # several ids share one map key (count, per 1,000, per km²)
        elif key.startswith("exp_"):
            name, measure = key[4:].rsplit("_", 1)
            vals = expo["vars"].get(name, {}).get(measure)
            if vals:
                var["years"]["2020"] = [vals[exp_at[g]] if g in exp_at else None for g in geo["ids"]]
                out[key] = (var, geo, "exposure_municipio.json")
    return out


def resolve(dataset: str):
    """Finds a series by its catalog id ("population.acs_veteran_pct") or its key ("acs_veteran_pct")."""
    s = series()
    if dataset in s:
        return s[dataset][0]["key"], s[dataset]
    for r in catalog():
        if r["id"] == dataset and r["map"] and r["map"][0] == "econ" and r["map"][1] in s:
            return r["map"][1], s[r["map"][1]]
    raise ToolError(f"No values for '{dataset}'. Use search_datasets and pick a result with has_values=true.")


def muni_index(geo, municipio: str) -> int:
    want = fold(municipio)
    for i, n in enumerate(geo["names"]):
        if fold(n) == want or geo["ids"][i] == municipio:
            return i
    raise ToolError(f"Unknown municipio '{municipio}'. Use one of the 78 names, such as 'Mayagüez' or 'Puerto Rico'.")


def pick_year(v, year):
    years = sorted(v["years"], key=int)
    if year is None:
        return years[-1], years
    if str(year) not in v["years"]:
        raise ToolError(f"No {year} for {v['key']}. Years: {', '.join(years)}.")
    return str(year), years


def at(table, year, i):
    row = (table or {}).get(year)
    return row[i] if row and i < len(row) else None


def sources_of(v, file):
    own, cat = load(file).get("sources") or {}, load("catalog_index.json").get("sources", {})
    out = []
    for k in v.get("sources", []):
        s = own.get(k) or cat.get(k) or {}
        out.append({"name": s.get("name", k), "url": s.get("url"), "license": s.get("license") or s.get("licence_class")})
    return out


def link(keys=(), municipio=None, year=None):
    parts = [urllib.parse.quote(municipio)] if municipio else []
    if keys:
        parts.append("e=" + urllib.parse.quote(",".join(f"{k}.f" for k in keys)))
    if year:
        parts.append(f"ey={year}")
    return f"{SITE}/" + ("#" + "&".join(parts) if parts else "")


@mcp.tool(annotations=READ_ONLY)
def list_domains() -> list[dict]:
    """Lists the observatory's fields of information (domains), in Spanish and English, with how many datasets each holds."""
    reg = load("dictionary_list.json")["domain_registry"]
    counts = {}
    for r in catalog():
        counts[r["domain"]] = counts.get(r["domain"], 0) + 1
    return [{"id": k, "name_es": d["name"]["es"], "name_en": d["name"]["en"],
             "description_es": d["description"]["es"], "datasets": counts.get(k, 0)}
            for k, d in sorted(reg.items(), key=lambda x: x[1].get("order", 0))]


@mcp.tool(annotations=READ_ONLY)
def search_datasets(query: str, domain: str | None = None, limit: int = 25) -> list[dict]:
    """Finds datasets by words in their Spanish or English name.

    Args:
        query: words to look for, in Spanish or English ("pobreza", "flood", "empleos turismo").
        domain: optional domain id from list_domains ("housing", "hazards").
        limit: maximum results.

    Results with has_values=true can be read with get_values, get_trend and
    municipality_profile. The others are map layers, points or barrio-level data:
    describe_dataset explains them and map_link shows them.
    """
    words = fold(query).split()
    s = series()
    hits = []
    for r in catalog():
        if domain and r["domain"] != domain and domain not in (r["domains"] or []):
            continue
        ask = r.get("ask") or {}
        text = fold(" ".join([r["id"], r["name"], r["name_es"] or "", *ask.get("en", []), *ask.get("es", [])]))
        score = sum(w in text for w in words)
        if score:
            key = r["map"][1] if r["map"] and r["map"][0] == "econ" else None
            hits.append((score, {"id": r["id"], "name_es": r["name_es"], "name_en": r["name"], "domain": r["domain"],
                                 "levels": r["levels"], "years": r["years"], "licence": r["licence"],
                                 "has_values": key in s}))
    hits.sort(key=lambda h: -h[0])
    return [h[1] for h in hits[:limit]]


@mcp.tool(annotations=READ_ONLY)
def describe_dataset(dataset: str) -> dict:
    """Returns the data dictionary entry for a dataset: plain meaning (es/en), exact definition, method, unit, years, cautions and sources.

    Args:
        dataset: a catalog id from search_datasets ("housing.median_rent").
    """
    row = next((r for r in catalog() if r["id"] == dataset), None)
    if not row:
        raise ToolError(f"Unknown dataset '{dataset}'. Use search_datasets.")
    file = f"dictionary_detail_{row['domain'].split('.')[0]}"
    entry = {**load(f"{file}.json")["entries"].get(dataset, {}), **load(f"{file}_es.json")["entries"].get(dataset, {})}
    keep = ("plain", "definition", "method", "value_type", "how_to_read", "caveats", "values", "geography", "source_detail")
    out = {k: v for k, v in entry.items() if k.removesuffix("_es") in keep}  # Spanish text where the dictionary has it
    out.update(id=dataset, name_en=row["name"], name_es=row["name_es"], domain=row["domain"],
               levels=row["levels"], licence=row["licence"], dictionary_url=f"{SITE}/dictionary.html#{dataset}")
    src = load("catalog_index.json").get("sources", {})
    out["sources"] = [{"id": s, **src.get(s, {})} for s in row["sources"] or []]
    return out


@mcp.tool(annotations=READ_ONLY)
def get_values(dataset: str, year: int | None = None, municipios: list[str] | None = None) -> dict:
    """Returns one dataset's value for every municipio in one year, ranked from highest, with the Puerto Rico total.

    Args:
        dataset: catalog id or series key with has_values=true.
        year: the year (survey windows go by their last year); latest when left out.
        municipios: optional names to keep; all 78 when left out.
    """
    key, (v, geo, file) = resolve(dataset)
    y, years = pick_year(v, year)
    vals, moe = v["years"][y], v.get("moe")
    rows = [{"municipio": n, "value": vals[i], **({"moe90": at(moe, y, i)} if moe else {})}
            for i, n in enumerate(geo["names"]) if geo["ids"][i] != PR_ID]
    ranked = sorted([r for r in rows if r["value"] is not None], key=lambda r: -r["value"])
    for rank, r in enumerate(ranked, 1):
        r["rank"] = rank
    if municipios:
        want = {fold(m) for m in municipios}
        rows = [r for r in rows if fold(r["municipio"]) in want]
        ranked = [r for r in ranked if fold(r["municipio"]) in want]
    pr = geo["ids"].index(PR_ID) if PR_ID in geo["ids"] else None
    return {"key": key, "label": v["label"], "unit": v.get("unit", ""), "type": v.get("type"), "year": int(y),
            "years_available": [int(x) for x in years], "definition": v.get("definition"),
            "puerto_rico": vals[pr] if pr is not None else None,
            "rows": ranked + [r for r in rows if r["value"] is None],
            "sources": sources_of(v, file), "map_link": link([key], year=y)}


@mcp.tool(annotations=READ_ONLY)
def get_trend(dataset: str, municipio: str) -> dict:
    """Returns every year of one dataset for one municipio, next to the Puerto Rico total.

    Args:
        dataset: catalog id or series key with has_values=true.
        municipio: municipio name (accents optional) or "Puerto Rico".
    """
    key, (v, geo, file) = resolve(dataset)
    i = muni_index(geo, municipio)
    pr = geo["ids"].index(PR_ID) if PR_ID in geo["ids"] else None
    moe = v.get("moe")
    return {"key": key, "label": v["label"], "unit": v.get("unit", ""), "municipio": geo["names"][i],
            "series": [{"year": int(y), "value": at(v["years"], y, i),
                        **({"moe90": at(moe, y, i)} if moe else {}),
                        "puerto_rico": at(v["years"], y, pr) if pr is not None else None}
                       for y in sorted(v["years"], key=int)],
            "sources": sources_of(v, file), "map_link": link([key], geo["names"][i])}


@mcp.tool(annotations=READ_ONLY)
def municipality_profile(municipio: str, domain: str | None = None) -> dict:
    """Returns the latest value of every dataset for one municipio, with its rank among the 78 and the Puerto Rico total.

    Args:
        municipio: municipio name (accents optional).
        domain: optional domain id from list_domains to narrow the profile ("health").
    """
    domain_of = {r["map"][1]: r["domain"] for r in catalog() if r["map"] and r["map"][0] == "econ"}
    out, name, seen = [], None, set()
    for key, (v, geo, _file) in series().items():
        if id(v) in seen:
            continue
        seen.add(id(v))
        d = domain_of.get(key, "")
        if domain and d != domain and not d.startswith(domain + "."):
            continue
        i = muni_index(geo, municipio)
        name = geo["names"][i]
        y = max(v["years"], key=int)
        val = at(v["years"], y, i)
        if val is None:
            continue
        pr = geo["ids"].index(PR_ID) if PR_ID in geo["ids"] else None
        others = [x for j, x in enumerate(v["years"][y]) if x is not None and geo["ids"][j] != PR_ID]
        out.append({"key": key, "label": v["label"], "domain": d, "unit": v.get("unit", ""), "year": int(y),
                    "value": val, "rank": 1 + sum(x > val for x in others), "of": len(others),
                    "puerto_rico": at(v["years"], y, pr) if pr is not None else None})
    if name is None:
        raise ToolError(f"No datasets for domain '{domain}'. Use list_domains.")
    return {"municipio": name, "rank_note": "rank 1 = highest value", "datasets": out, "map_link": link(municipio=name)}


@mcp.tool(annotations=READ_ONLY)
def map_link(datasets: list[str] | None = None, municipio: str | None = None, year: int | None = None) -> str:
    """Builds a link that opens the observatory's map with these datasets shaded, zoomed to a municipio.

    Args:
        datasets: up to two catalog ids or series keys with has_values=true (two make a bivariate map).
        municipio: optional municipio to select.
        year: optional year; latest when left out.
    """
    return link([resolve(d)[0] for d in (datasets or [])[:2]], municipio, year)


if __name__ == "__main__":
    if "--http" in sys.argv:
        port = int(sys.argv[sys.argv.index("--port") + 1]) if "--port" in sys.argv else 8000
        mcp.run(transport="streamable-http", host="0.0.0.0", port=port, stateless_http=True)
    else:
        mcp.run()
