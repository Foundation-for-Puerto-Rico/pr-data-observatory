"""Which data sources have a new release: cheap checks, on each source's own schedule (docs/automation.md, part 2).

refresh/sources.json says, for every downloaded source, how to tell that it published something new without downloading the data (a file's
headers, an API's latest date or count, whether next year's file exists), how often to look, the months a release is expected (looked at
daily then), what rebuilds it and whether a person reviews the result. This program runs the checks that are due, compares each answer with
the one it kept from last time (the state file), and writes what changed.

    python freshness.py                    # run the checks that are due; write the state, a report and the list of changes
    python freshness.py --all              # run every check now
    python freshness.py --only acs5,bls_cpi
    python freshness.py --sync-time        # after a rebuild: move dictionary_src/datasets.json time.last forward to the year the files now reach
    python freshness.py --review UNIT [source ...]   # print "auto" or "human" for a rebuild of UNIT ("auto" only when every source the unit reads is routine
                                                     # and no file of the unit's "human_if_changed" changed)
    python freshness.py --changed-unit UNIT           # exit 0 when the unit's published files really changed against git HEAD (dates of the build ignored), else 1
    python freshness.py --doc              # print the schedule table of docs/automation.md
    python freshness.py --check-doc        # exit 1 when docs/automation.md does not hold the current schedule table

The first answer a check gets is its baseline, not a change. A check that fails (a server down) is reported and tried again next time.
"""
import json
import os
import re
import sys
import time
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).parent
SCHEDULE = ROOT / "refresh" / "sources.json"
STATE = Path(os.environ.get("FRESHNESS_STATE", ROOT / ".freshness" / "state.json"))
OUT = Path(os.environ.get("FRESHNESS_OUT", ROOT / ".freshness"))
DOC = ROOT / "docs" / "automation.md"
MONTHS = ["january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december"]
UA = "PR-Data-Observatory/1.0 (+https://github.com/Foundation-for-Puerto-Rico/pr-data-observatory)"


class ProbeError(Exception):
    pass


def load_schedule(path=SCHEDULE):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def load_state(path=STATE):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


# ── when a check is due ────────────────────────────────────────────────────
def interval(src, today):
    """Days between checks: 1 in a month when a release is expected, else the source's own interval."""
    return 1 if today.month in src.get("hot_months", []) else max(1, int(src.get("every_days") or 30))


def due(src, entry, today):
    if src["probe"]["kind"] == "follows":
        return False
    if not entry or not entry.get("checked"):
        return True
    return (today - date.fromisoformat(entry["checked"])).days >= interval(src, today)


# ── the checks ─────────────────────────────────────────────────────────────
class Http:
    """requests with retries and a polite user agent. `contact` adds FRESHNESS_CONTACT (an FPR role address; BLS refuses anonymous requests)."""
    def __init__(self, tries=3, wait=(3, 10, 20), timeout=30):
        import requests
        self.s, self.tries, self.wait, self.timeout = requests.Session(), tries, wait, timeout

    def request(self, method, url, contact=False, **kw):
        ua = UA + (f" contact: {os.environ['FRESHNESS_CONTACT']}" if contact and os.environ.get("FRESHNESS_CONTACT") else "")
        headers = {"User-Agent": ua, **kw.pop("headers", {})}
        last = None
        for k in range(self.tries):
            try:
                return self.s.request(method, url, headers=headers, timeout=self.timeout, allow_redirects=True, **kw)
            except Exception as e:   # connection reset, timeout, TLS: try again, then give up
                last = e
                if k + 1 < self.tries:
                    time.sleep(self.wait[min(k, len(self.wait) - 1)])
        raise ProbeError(f"{type(last).__name__}: {last}")


def fill(template, period=None, today=None):
    today = today or date.today()
    v = {"this_year": today.year, "last_year": today.year - 1}
    if period:
        y = int(period[:4]); v.update(y=y, yy=f"{y % 100:02d}")
        if len(period) > 4:
            v["month"] = MONTHS[int(period[5:7]) - 1]
    return template.format(**v)


def step(period, kind):
    if kind == "year":
        return str(int(period) + 1)
    y, m = int(period[:4]), int(period[5:7])
    return f"{y + (m == 12)}-{m % 12 + 1:02d}"


def pick(obj, path):
    """A value inside parsed JSON by a dotted path (list indices as numbers); "" is the whole value."""
    for part in [p for p in path.split(".") if p != ""]:
        if isinstance(obj, list):
            obj = obj[int(part)]
        elif isinstance(obj, dict):
            if part not in obj:
                raise ProbeError(f"no '{part}' in the answer")
            obj = obj[part]
        else:
            raise ProbeError(f"cannot read '{part}' from {type(obj).__name__}")
    return obj


def exists(http, url, ok):
    """Does a period's file exist? 'json-count': the API answers a count above 0; 'spreadsheet': 200 with a spreadsheet type; 'get': asks for one byte (a server that
    answers HEAD with an error, such as EPA's Envirofacts downloads); default: 200."""
    if ok == "get":
        r = http.request("GET", url, headers={"Range": "bytes=0-0"}, stream=True); r.close()
        if r.status_code in (404, 410):
            return False
        if r.status_code not in (200, 206):
            raise ProbeError(f"HTTP {r.status_code} for {url}")
        return True
    if ok == "json-count":
        r = http.request("GET", url)
        if r.status_code == 404:
            return False
        if r.status_code != 200:
            raise ProbeError(f"HTTP {r.status_code} for {url}")
        try:
            return (r.json().get("count") or 0) > 0
        except ValueError:
            return False
    r = http.request("HEAD", url)
    if r.status_code in (403, 405):   # some servers refuse HEAD: ask for one byte instead
        r = http.request("GET", url, headers={"Range": "bytes=0-0"}, stream=True); r.close()
    if r.status_code in (404, 410) or (ok == "spreadsheet" and r.status_code == 503):   # EIA answers 503 for a month not yet published
        return False
    if r.status_code not in (200, 206):   # a server error says nothing about the period: the check fails and is tried again
        raise ProbeError(f"HTTP {r.status_code} for {url}")
    if ok == "spreadsheet":
        return any(k in r.headers.get("Content-Type", "").lower() for k in ("spreadsheet", "officedocument", "excel", "octet-stream"))
    return True


def probe(src, http, today=None, last=None):
    """The fingerprint of a source's latest release, as a string. `last` is the fingerprint of the previous run (a walk starts from it)."""
    p, today = src["probe"], today or date.today()
    kind = p["kind"]
    if kind == "head":
        r = http.request("HEAD", fill(p["url"], today=today), contact=p.get("contact", False))
        if r.status_code != 200:
            hint = " (this server wants a contact address: set the repository variable FRESHNESS_CONTACT to an FPR role mailbox)" if p.get("contact") and r.status_code == 403 and not os.environ.get("FRESHNESS_CONTACT") else ""
            raise ProbeError(f"HTTP {r.status_code}{hint}")
        return " | ".join(f"{h}={r.headers.get(h, '')}" for h in p["headers"])
    if kind == "range-size":
        out = []
        for u in p["urls"]:
            r = http.request("GET", u, headers={"Range": "bytes=0-0"}, stream=True); r.close()
            m = re.search(r"/(\d+)$", r.headers.get("Content-Range", ""))
            if r.status_code not in (200, 206) or not m:
                raise ProbeError(f"HTTP {r.status_code}, no size")
            out.append(m.group(1))
        return " | ".join(out)
    if kind == "walk":
        # forward from the newest period seen so far (or the period the observatory held when the schedule was written), until one is missing
        period = last if last and len(last) == len(p["start"]) and last > p["start"] else p["start"]
        newest = None
        for _ in range(24):
            if not exists(http, fill(p["url"], period, today), p.get("ok")):
                break
            newest, period = period, step(period, p["step"])
        else:
            raise ProbeError(f"24 periods in a row exist after {p['start']}: the check cannot tell the newest; look at the source")
        if newest is None:
            raise ProbeError(f"even {p['start']} is missing: the address may have moved")
        return newest
    if kind == "json":
        vals = []
        for i, u in enumerate(p["urls"]):   # "paths" holds the same paths for every address, or, with "per_url", one list of paths for each address in turn
            r = http.request("GET", fill(u, today=today), contact=p.get("contact", False))
            if r.status_code != 200:
                raise ProbeError(f"HTTP {r.status_code}")
            try:
                j = r.json()
            except ValueError:
                raise ProbeError("the answer is not JSON")
            vals += [str(pick(j, path)) for path in (p["paths"][i] if p.get("per_url") else p["paths"])]
        return " | ".join(vals)
    if kind == "regex":
        r = http.request("GET", p["url"])
        if r.status_code != 200:
            raise ProbeError(f"HTTP {r.status_code}")
        found = re.findall(p["pattern"], r.text)
        if not found:
            raise ProbeError("the pattern matches nothing: the page may have changed")
        return max(found)
    if kind == "calendar":
        if p["rule"] == "quarter":
            return f"{today.year}-Q{(today.month - 1) // 3 + 1}"
        if p["rule"] == "month":   # a monthly rebuild of a source that changes every day (reservoir levels)
            return f"{today.year}-{today.month:02d}"
        if p["rule"] == "summer":   # the last complete summer (June to September), complete once October has begun: the window of surface heat, vegetation and night heat (heat.py, vegetation.py, ecostress.py)
            return f"summer-{today.year if today.month >= 10 else today.year - 1}"
        if p["rule"] == "fiscal-year-final":   # a federal fiscal year (October to September) counts as final from 15 November
            return f"FY{today.year if today >= date(today.year, 11, 15) else today.year - 1}"
    raise ProbeError(f"unknown check kind {kind}")


# ── a run ──────────────────────────────────────────────────────────────────
def run(schedule, state, today, http, force=False, only=None):
    """Runs the due checks, updates `state` in place. Returns (changes, failures, checked ids)."""
    units = schedule["units"]
    changes, failures, checked = [], [], []
    for src in schedule["sources"]:
        if only and src["id"] not in only:
            continue
        entry = state.get(src["id"], {})
        if src["probe"]["kind"] == "follows" or not (force or only or due(src, entry, today)):
            continue
        try:
            fp = probe(src, http, today, entry.get("fingerprint"))
        except Exception as e:
            since = entry.get("failing_since") or today.isoformat()
            failures.append({"id": src["id"], "name": src["name"], "error": str(e)[:200], "since": since, "new": since == today.isoformat()})
            entry["failing_since"] = since; state[src["id"]] = entry
            continue
        checked.append(src["id"])
        old = entry.get("fingerprint")
        if old is not None and old != fp:
            u = units[src["unit"]]
            changes.append({"id": src["id"], "name": src["name"], "unit": src["unit"], "where": u["where"], "how": u["how"], "review": src["review"],
                            "code_edit": src.get("code_edit"), "note": src.get("note"), "old": old, "new": fp})
            entry["changed"] = today.isoformat()
        entry.update(fingerprint=fp, checked=today.isoformat()); entry.pop("failing_since", None)
        state[src["id"]] = entry
    return changes, failures, checked


def rebuildable(changes):
    """{unit: [source ids]} for the changes that a workflow can rebuild by itself: a clean runner can run the unit, and no code edit is needed first."""
    out = {}
    for c in changes:
        if c["where"] == "ci" and not c["code_edit"]:
            out.setdefault(c["unit"], []).append(c["id"])
    return out


def review_of(schedule, unit, ids=(), changed=()):
    """'auto' only when every source the unit reads is routine: a rebuild re-reads all of them, so a new vintage of one can ride along with
    a routine change of another. Sources named for the run must belong to the unit. `changed`: the published files the run changed; a file the
    unit lists under "human_if_changed" (a file another script rebuilds from the unit's output, such as the WCRP index from the local conditions)
    always waits for a person."""
    mine = [s for s in schedule["sources"] if s["unit"] == unit]
    stray = [i for i in ids if i not in {s["id"] for s in mine}]
    if stray:
        raise SystemExit(f"not sources of the unit {unit}: {', '.join(stray)}")
    if set(changed) & set(schedule["units"].get(unit, {}).get("human_if_changed", [])):
        return "human"
    return "auto" if mine and all(s["review"] == "auto" for s in mine) else "human"


def report(changes, failures, checked, schedule, state, today):
    L = [f"# Data freshness, {today.isoformat()}", ""]
    if changes:
        L += ["## New releases", "", "| Source | Was | Now | What happens |", "|---|---|---|---|"]
        for c in changes:
            if c["where"] == "nightly":
                what = "The nightly transit job publishes it."
            elif c["code_edit"]:
                what = f"Needs a code edit first ({c['code_edit']}), then: `{c['how']}`."
            elif c["where"] == "ci":
                what = "Rebuilt automatically; " + ("its pull request merges itself when the checks pass." if c["review"] == "auto" else "its pull request waits for a person.")
            else:
                what = f"Rebuild locally: `{c['how']}`."
            L.append(f"| {c['name']} (`{c['id']}`) | {c['old'][:60]} | {c['new'][:60]} | {what}{' ' + c['note'] if c.get('note') else ''} |")
        L.append("")
    else:
        L += ["No source has a new release since its last check.", ""]
    if failures:
        L += ["## Checks that failed (tried again next time)", ""] + [f"- {f['name']} (`{f['id']}`), failing since {f['since']}: {f['error']}" for f in failures] + [""]
    nxt = []
    for s in schedule["sources"]:
        e = state.get(s["id"], {})
        if s["probe"]["kind"] == "follows" or not e.get("checked"):
            continue
        nxt.append((date.fromisoformat(e["checked"]) + timedelta(days=interval(s, today)), s["name"]))
    L += [f"Checked today: {len(checked)} source(s). Never checked yet: {sum(1 for s in schedule['sources'] if s['probe']['kind'] != 'follows' and not state.get(s['id'], {}).get('checked'))}.", ""]
    if nxt:
        L += ["Next checks: " + "; ".join(f"{d.isoformat()} {n}" for d, n in sorted(nxt)[:6]) + ".", ""]
    return "\n".join(L)


# ── after a rebuild: the declared years follow the files ───────────────────
def sync_time(root=ROOT):
    """Moves time.last in dictionary_src/datasets.json forward to the last year a file now holds, when only the end moved (never back, never the start).
    Returns the files changed. A file that starts in another year, or ends earlier, is left for contract.py to report."""
    sys.path.insert(0, str(root))
    import contract
    p = root / "dictionary_src" / "datasets.json"
    raw = p.read_bytes(); nl = "\r\n" if b"\r\n" in raw else "\n"
    d = json.loads(raw.decode("utf-8"))
    moved = []
    for r in d["datasets"]:
        t = r.get("time") or {}
        f = root / "site" / "data" / r["file"]
        if not t.get("years_path") or t.get("last") is None or not f.exists():
            continue
        oy = contract.observed_years(json.loads(f.read_text(encoding="utf-8")), t["years_path"])
        if oy and oy[1] > t["last"] and (t.get("first") is None or t["first"] == oy[0]):
            moved.append(f"{r['file']}: {t['last']} -> {oy[1]}"); t["last"] = oy[1]
    if moved:
        p.write_bytes((json.dumps(d, ensure_ascii=False, indent=1) + "\n").replace("\n", nl).encode("utf-8"))
    return moved


# ── did a rebuild change anything but its date? ────────────────────────────
STAMPS = {"built", "generated", "generated_at", "retrieved", "fetched", "as_of_run"}   # when a build ran, not what it found


def strip_stamps(x, extra=()):
    drop = STAMPS | set(extra)
    if isinstance(x, dict):
        return {k: strip_stamps(v, extra) for k, v in x.items() if k not in drop}
    if isinstance(x, list):
        return [strip_stamps(v, extra) for v in x]
    return x


def material_changes(files, root=ROOT, ignore=()):
    """The published files (names in site/data) whose content differs from git HEAD once the build's own date stamps are set aside."""
    import subprocess
    out = []
    for f in files:
        p = root / "site" / "data" / f
        r = subprocess.run(["git", "show", f"HEAD:site/data/{f}"], capture_output=True, cwd=root)
        if r.returncode != 0:
            out.append(f) if p.exists() else None   # a new file is a change
            continue
        if not p.exists() or strip_stamps(json.loads(r.stdout.decode("utf-8")), ignore) != strip_stamps(json.loads(p.read_text(encoding="utf-8")), ignore):
            out.append(f)
    return out


# ── the schedule table of docs/automation.md ───────────────────────────────
def doc_table(schedule):
    names = {1: "Jan", 2: "Feb", 3: "Mar", 4: "Apr", 5: "May", 6: "Jun", 7: "Jul", 8: "Aug", 9: "Sep", 10: "Oct", 11: "Nov", 12: "Dec"}
    where = {"nightly": "nightly transit job", "ci": "automatic", "local": "by hand (local)"}
    L = ["| Source | Checked | Daily in | Rebuilt | Merged |", "|---|---|---|---|---|"]
    for s in schedule["sources"]:
        u = schedule["units"][s["unit"]]
        every = "with the schools" if s["probe"]["kind"] == "follows" else ("daily" if s["every_days"] == 1 else f"every {s['every_days']} days")
        hot = "all year" if len(s["hot_months"]) == 12 else ", ".join(names[m] for m in s["hot_months"]) or "—"
        rebuilt = where[u["where"]] + (" after a code edit" if s.get("code_edit") else "")
        merged = "when the checks pass" if s["review"] == "auto" and u["where"] in ("ci", "nightly") and not s.get("code_edit") else "after a person reviews it"
        if merged == "when the checks pass" and u.get("human_if_changed"):
            merged += " (a person reviews it when " + ", ".join(f"`{f}`" for f in u["human_if_changed"]) + " change)"
        L.append(f"| {s['name']} | {every} | {hot} | {rebuilt} | {merged} |")
    return "\n".join(L)


DOC_START, DOC_END = "<!-- schedule:start (python freshness.py --doc) -->", "<!-- schedule:end -->"


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    sched = load_schedule()
    if "--doc" in argv:
        print(doc_table(sched)); return 0
    if "--check-doc" in argv:
        t = DOC.read_text(encoding="utf-8").replace("\r\n", "\n")
        ok = DOC_START in t and t.split(DOC_START, 1)[1].split(DOC_END, 1)[0].strip() == doc_table(sched)
        print("docs/automation.md schedule table is current" if ok else "docs/automation.md schedule table is out of date: run python freshness.py --doc and paste it")
        return 0 if ok else 1
    if "--sync-time" in argv:
        moved = sync_time()
        print("\n".join(moved) if moved else "time.last already matches every file"); return 0
    if "--changed-unit" in argv:
        u = sched["units"][argv[argv.index("--changed-unit") + 1]]
        ch = material_changes(u["files"], ignore=u.get("ignore", []))
        print("changed: " + ", ".join(ch) if ch else "no change but the build date in " + ", ".join(u["files"]))
        return 0 if ch else 1
    if "--review" in argv:
        rest = argv[argv.index("--review") + 1:]
        u = sched["units"][rest[0]]
        changed = material_changes(u.get("human_if_changed", []), ignore=u.get("ignore", []))   # after the rebuild: the working tree against git HEAD
        print(review_of(sched, rest[0], [i for i in rest[1:] if i], changed)); return 0
    only = set(argv[argv.index("--only") + 1].split(",")) if "--only" in argv else None
    today = date.fromisoformat(os.environ["FRESHNESS_TODAY"]) if os.environ.get("FRESHNESS_TODAY") else date.today()
    state = load_state()
    changes, failures, checked = run(sched, state, today, Http(), force="--all" in argv, only=only)
    OUT.mkdir(parents=True, exist_ok=True); STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(state, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    notify = len(changes) + sum(1 for f in failures if f["new"])   # a known failure is reported every day but notifies once
    (OUT / "changes.json").write_text(json.dumps({"changes": changes, "failures": failures, "notify": notify, "rebuild": rebuildable(changes)}, indent=1) + "\n", encoding="utf-8")
    (OUT / "report.md").write_text(report(changes, failures, checked, sched, state, today), encoding="utf-8")
    print(f"freshness: {len(checked)} checked, {len(changes)} new release(s), {len(failures)} failed")
    for c in changes:
        print(f"  NEW {c['id']}: {c['old'][:50]} -> {c['new'][:50]}")
    for f in failures:
        print(f"  FAILED {f['id']}: {f['error'][:120]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
