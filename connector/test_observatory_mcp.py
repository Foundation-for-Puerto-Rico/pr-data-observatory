"""Checks the connector end to end over MCP stdio, against the repo's site/data.

Run from the repo root:
    uv run --with "mcp>=2.3,<3" python connector/test_observatory_mcp.py
Set OBSERVATORY_DATA="" to check against the live site instead, or pass a URL to check a
hosted connector over streamable HTTP:
    uv run --with "mcp>=2.3,<3" python connector/test_observatory_mcp.py https://observatory.foundationpr.org/api/mcp
"""

import asyncio
import json
import os
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.client.streamable_http import streamable_http_client

HERE = os.path.dirname(os.path.abspath(__file__))
ENV = {**os.environ, "OBSERVATORY_DATA": os.environ.get("OBSERVATORY_DATA", os.path.join(HERE, "..", "site", "data"))}
if not ENV["OBSERVATORY_DATA"]:
    del ENV["OBSERVATORY_DATA"]


async def main():
    if len(sys.argv) > 1:
        transport = streamable_http_client(sys.argv[1])
    else:
        transport = stdio_client(StdioServerParameters(command=sys.executable, args=[os.path.join(HERE, "observatory_mcp.py")], env=ENV))
    async with transport as (r, w), ClientSession(r, w) as s:
        await s.initialize()

        async def call(name, **args):
            res = await s.call_tool(name, args)
            assert not res.is_error, (name, res.content)
            out = res.structured_content  # set for list and str results; a dict result comes as JSON text
            if out is None:
                return json.loads(res.content[0].text)
            return out["result"] if set(out) == {"result"} else out

        tools = {t.name for t in (await s.list_tools()).tools}
        assert tools == {"list_domains", "search_datasets", "describe_dataset", "get_values",
                         "get_trend", "municipality_profile", "map_link"}, tools

        hits = await call("search_datasets", query="pobreza")
        assert any(h["id"] == "housing.poverty_pct" and h["has_values"] for h in hits), hits

        v = await call("get_values", dataset="housing.poverty_pct", year=2024)
        assert v["year"] == 2024 and len(v["rows"]) == 78 and v["rows"][0]["rank"] == 1
        assert v["rows"][0]["value"] >= v["rows"][1]["value"]

        t = await call("get_trend", dataset="qcew_jobs", municipio="mayaguez")  # accents optional
        assert t["municipio"] == "Mayagüez" and len(t["series"]) > 5

        f = await call("get_values", dataset="exposure.pop_flood", municipios=["San Juan"])
        assert f["rows"][0]["municipio"] == "San Juan" and f["rows"][0]["value"] > 0

        per = await call("get_values", dataset="municipalities.assets_per_1000_residents")
        assert per["label"].endswith("per 1,000 residents"), per["label"]

        p = await call("municipality_profile", municipio="Loíza", domain="health")
        assert p["datasets"] and all(d["domain"].startswith("health") for d in p["datasets"])

        d = await call("describe_dataset", dataset="population.acs_veteran_pct")
        assert d["plain"] and d["sources"] and d["dictionary_url"].endswith("#population.acs_veteran_pct")

        link = await call("map_link", datasets=["housing.poverty_pct"], municipio="Ponce")
        assert link.endswith("/#Ponce&e=poverty_pct.f"), link

        bad = await s.call_tool("get_trend", {"dataset": "qcew_jobs", "municipio": "Atlantis"})
        assert bad.is_error and "Unknown municipio" in bad.content[0].text, bad.content  # the hint reaches Claude
    print("ok")


asyncio.run(main())
