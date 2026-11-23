"""Sanity checks on the files the nightly transit refresh rewrote, before the bot publishes them (refresh-transit.yml).

Each count is compared with the last published copy (git HEAD). The job stops, and nothing is published, when:
  - a file does not parse, or a count is zero;
  - a count falls by more than a quarter from the published copy (DROP; a threshold chosen by hand, not measured);
  - the refresh added or removed rows of a file it should only update (places, municipalities);
  - places.json carries a contact field (phone, e-mail, social accounts, street address, website).
A large drop can be real (an operator's feed expired). A person then looks at it and runs the workflow by hand with "allow drop".

    python check_refresh.py                # compare site/data with HEAD; exit 1 on a problem
    python check_refresh.py --allow-drop   # a large drop is reported, not fatal
"""

import json
import subprocess
import sys
from pathlib import Path

DATA = Path(__file__).parent / "site" / "data"
DROP = 0.25
COUNTS = {   # file -> how many records it holds
    "transit_routes.geojson": lambda d: len(d["features"]),
    "trips.json": lambda d: len(d["trips"]),
    "trips_sa.json": lambda d: len(d["trips"]),
    "trips_su.json": lambda d: len(d["trips"]),
    "operators.json": lambda d: len(d["operators"]),
    "transport.json": len,
    "population_blocks.json": len,
}
SAME = {"places.json": len, "municipalities.json": len,   # the refresh rewrites fields of these, never their rows
        "place_access.json": lambda d: len(d["ts_m"]), "transit_supply.json": lambda d: len(d["days"])}
BANNED = {"phone", "email", "socials", "address", "website", "postcode"}   # places_privacy.CONTACT_FIELDS: no contact detail is published


def from_disk(name):
    return json.loads((DATA / name).read_text(encoding="utf-8"))


def from_head(name):
    r = subprocess.run(["git", "show", f"HEAD:site/data/{name}"], capture_output=True, cwd=Path(__file__).parent)
    return json.loads(r.stdout.decode("utf-8")) if r.returncode == 0 else None


def check(new, old, allow_drop=False):
    """new, old: name -> parsed file (old may give None for a file not yet published). Returns (problems, notes)."""
    problems, notes = [], []
    for name, count in {**COUNTS, **SAME}.items():
        try:
            n = count(new(name))
        except Exception as e:   # missing, not JSON, or not the expected shape
            problems.append(f"{name}: cannot be read ({type(e).__name__}: {e})")
            continue
        o = old(name)
        p = None if o is None else count(o)
        notes.append(f"{name}: {n:,}" + ("" if p is None else f" (published {p:,})"))
        if n == 0:
            problems.append(f"{name}: no records")
        elif name in SAME and p is not None and n != p:
            problems.append(f"{name}: {n:,} rows, the published copy has {p:,}; the refresh only updates fields")
        elif name in COUNTS and p and n < p * (1 - DROP):
            msg = f"{name}: {n:,} records, down {1 - n / p:.0%} from {p:,} (more than {DROP:.0%})"
            (notes if allow_drop else problems).append(msg + (" - allowed by hand" if allow_drop else ""))
    try:
        bad = {k for p in new("places.json") for k in p} & BANNED
        if bad:
            problems.append(f"places.json publishes contact fields: {sorted(bad)}")
        import places_privacy   # a withheld place drawn again, or a name that holds a telephone (the values, not only the field names)
        problems += [f"places.json: {x}" for x in places_privacy.problems(new("places.json"), places_privacy.load_review())[:20]]
    except Exception:
        pass   # already reported above
    return problems, notes


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    problems, notes = check(from_disk, from_head, "--allow-drop" in argv)
    for n in notes:
        print("  " + n)
    for p in problems:
        print("PROBLEM " + p)
    print(f"check_refresh: {len(problems)} problems")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
