"""The ATI timetable of one weekday window, compact, for the San Juan reach prototype (index.html in this folder).

  python docs/analysis/sj-reach-2026-11/export_timetable.py                 Tuesday 2026-11-24, 17:00 to 17:15
  python docs/analysis/sj-reach-2026-11/export_timetable.py --date 2026-12-01 --start 08:00

Reads cache/network/ati.zip (PRITA_GTFS.zip of the Autoridad de Transporte Integrado, the feed network.py downloads) and writes timetable.json here:
  stops        [[lng, lat], ...] for the stops the window uses
  connections  [[from stop, to stop, departure s, arrival s, trip], ...] sorted by departure; seconds from the window start
  footpaths    [[stop, stop, seconds], ...] for stops within FOOT_M of each other, both ways listed once
A connection is one hop of a trip between consecutive stops. Only hops that depart inside the window are kept: a later one cannot help a 15-minute trip.
"""
import argparse
import csv
import io
import json
import math
import zipfile
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
ZIP = ROOT / "cache" / "network" / "ati.zip"
OUT = Path(__file__).resolve().parent / "timetable.json"
WALK_MS = 4.8 / 3.6
FOOT_M = 250        # ponytail: straight-line transfers within 250 m x 1.25 detour; the road graph would be exact, add it if transfers matter
DETOUR = 1.25
DAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]


def rows(z, name):
    with z.open(name) as f:
        yield from csv.DictReader(io.TextIOWrapper(f, encoding="utf-8-sig"))


def secs(hms):
    h, m, s = (int(x) for x in hms.strip().split(":"))
    return h * 3600 + m * 60 + s


def services_on(z, day):
    ymd, wd = day.strftime("%Y%m%d"), DAYS[day.weekday()]
    on = {r["service_id"] for r in rows(z, "calendar.txt") if r["start_date"] <= ymd <= r["end_date"] and r[wd] == "1"}
    for r in rows(z, "calendar_dates.txt"):
        if r["date"] == ymd:
            (on.add if r["exception_type"] == "1" else on.discard)(r["service_id"])
    return on


def build(day, start, minutes):
    t0, t1 = start, start + minutes * 60
    with zipfile.ZipFile(ZIP) as z:
        on = services_on(z, day)
        trips = {r["trip_id"] for r in rows(z, "trips.txt") if r["service_id"] in on}
        by_trip = {}
        for r in rows(z, "stop_times.txt"):
            if r["trip_id"] in trips and r["departure_time"].strip():
                by_trip.setdefault(r["trip_id"], []).append((int(r["stop_sequence"]), r["stop_id"], secs(r["arrival_time"]), secs(r["departure_time"])))
        conns, used = [], {}
        for k, (tid, st) in enumerate(sorted(by_trip.items())):
            st.sort()
            for (_, a, _, dep), (_, b, arr, _) in zip(st, st[1:]):
                if t0 <= dep <= t1 and arr >= dep:
                    conns.append([used.setdefault(a, len(used)), used.setdefault(b, len(used)), dep - t0, arr - t0, k])
        pos = {r["stop_id"]: (float(r["stop_lon"]), float(r["stop_lat"])) for r in rows(z, "stops.txt")}
    conns.sort(key=lambda c: (c[2], c[3]))
    stops = [None] * len(used)
    for sid, i in used.items():
        stops[i] = [round(pos[sid][0], 6), round(pos[sid][1], 6)]
    foot = []
    for i, (x1, y1) in enumerate(stops):
        kx = math.cos(math.radians(y1)) * 111320
        for j in range(i + 1, len(stops)):
            x2, y2 = stops[j]
            d = math.hypot((x2 - x1) * kx, (y2 - y1) * 110574)
            if d <= FOOT_M:
                foot.append([i, j, round(d * DETOUR / WALK_MS)])
    return {"feed": "ATI PRITA_GTFS.zip", "date": day.isoformat(), "start": f"{start // 3600:02d}:{start // 60 % 60:02d}", "minutes": minutes,
            "trips": len({c[4] for c in conns}), "stops": stops, "connections": conns, "footpaths": foot}


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--date", default="2026-11-24")
    ap.add_argument("--start", default="17:00")
    ap.add_argument("--minutes", type=int, default=15)
    a = ap.parse_args()
    h, m = (int(x) for x in a.start.split(":"))
    doc = build(date.fromisoformat(a.date), h * 3600 + m * 60, a.minutes)
    OUT.write_text(json.dumps(doc, separators=(",", ":")) + "\n", encoding="utf-8")
    print(f"wrote {OUT.name}: {doc['date']} {doc['start']} +{doc['minutes']} min, {doc['trips']} trips, {len(doc['connections'])} hops, "
          f"{len(doc['stops'])} stops, {len(doc['footpaths'])} footpaths")
    assert doc["connections"] and all(c[3] >= c[2] for c in doc["connections"]), "no service in the window, or a hop that arrives before it leaves"


if __name__ == "__main__":
    main()
