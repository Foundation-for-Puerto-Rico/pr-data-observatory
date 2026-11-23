# The candidate check behind decision 69 (run 2026-10-31): for 26 assistance listings and 15 agencies, how many municipios get money and San Juan's share of the placed dollars, FY2019 and FY2024.
# python docs/analysis/public-money-v2-2026-10/candidates.py docs/analysis/public-money-v2-2026-10/candidates_fy2019_fy2024.json
import json, sys, time, requests
U = "https://api.usaspending.gov/api/v2/search/spending_by_geography/"
H = {"User-Agent": "pr-digital-twin probe"}
PROGS = ["96.002", "96.001", "96.004", "93.774", "93.773", "93.770", "93.778", "10.566", "64.109", "84.063", "84.010", "93.600",
         "14.850", "14.871", "14.872", "14.195", "20.205", "66.458", "66.468", "10.555", "10.557", "97.036", "14.228", "97.039", "84.425", "11.035"]
AGS = ["Department of Health and Human Services", "Social Security Administration", "Department of Homeland Security", "Department of Agriculture",
       "Department of Education", "Department of Veterans Affairs", "Department of Housing and Urban Development", "Department of Defense",
       "Department of Transportation", "Environmental Protection Agency", "Department of Commerce", "Department of Energy", "Department of Labor",
       "Small Business Administration", "Federal Communications Commission"]

def geo(fy, extra):
    body = {"scope": "place_of_performance", "geo_layer": "county", "geo_layer_filters": [f"72{i:03d}" for i in range(1, 154, 2)], "subawards": False,
            "filters": {"time_period": [{"start_date": f"{fy-1}-10-01", "end_date": f"{fy}-09-30"}], "place_of_performance_locations": [{"country": "USA", "state": "PR"}], **extra}}
    for a in range(4):
        r = requests.post(U, json=body, headers=H, timeout=180)
        if r.status_code == 200:
            return {x["shape_code"]: x["aggregated_amount"] for x in r.json()["results"] if x["shape_code"].startswith("72")}
        time.sleep(3 * (a + 1))
    raise RuntimeError(r.text[:300])

out = {}
for fy in (2019, 2024):
    for kind, items in (("prog", PROGS), ("ag", AGS)):
        for it in items:
            extra = {"program_numbers": [it]} if kind == "prog" else {"agencies": [{"type": "awarding", "tier": "toptier", "name": it}]}
            d = geo(fy, extra)
            tot = sum(v for v in d.values() if v > 0)
            sj = d.get("72127", 0)
            n = sum(1 for v in d.values() if v > 0)
            out[f"{kind}|{it}|{fy}"] = {"n": n, "total": tot, "sj_share": round(sj / tot * 100, 1) if tot else None}
            print(fy, kind, it[:40], "municipios", n, "placed $M", round(tot / 1e6), "SJ%", out[f"{kind}|{it}|{fy}"]["sj_share"], flush=True)
            time.sleep(0.3)
json.dump(out, open(sys.argv[1], "w"), indent=1)
