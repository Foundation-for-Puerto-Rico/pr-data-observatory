"""Compare two captures of the same page (plan item 6 regression harness; see README.md).

    python tests/browser/compare.py CAPTURES_DIR economy_en            # compares old_economy_en.json with new_economy_en.json
    python tests/browser/compare.py CAPTURES_DIR economy_en --show 40  # print up to 40 differences (default 12)
    python tests/browser/compare.py CAPTURES_DIR economy_en --expect tests/browser/expected.json   # differences that a change was meant to make are listed, with their reason, and do not fail the run

The file given to --expect lists two kinds of entry. { "path": regex, "why": text } lets every difference at a path that matches pass, and says why. A normaliser is applied to BOTH captures
before they are compared, so that what a change meant to add is taken out and everything else is still compared exactly: { "sub": [regex, replacement], "why": text } rewrites every
string (replacement "$window" turns a five-year window "2020\u20132024" back into its last year), { "drop_key": regex, "why": text } leaves out dictionary keys, { "drop_item": value, "why": text }
leaves out list items equal to value, { "drop_pair": regex, "why": text } leaves out [id, label] pairs whose id matches. The run says how many things each normaliser changed in the new capture, so a rule that matches nothing is visible.

A capture is the JSON a capture script posted from the browser. Numbers are compared with a relative tolerance of 1e-9; text and structure must be identical, except for
the map view in a link (`c=lat,lng,zoom`), which depends on how far an animation had run when the page was read. Exit status 1 when anything differs.
"""
import json
import math
import re
import sys
from pathlib import Path

REL = 1e-9
ABS = 1e-12


def normal(key, v):
    if key in ("hash", "encode") and isinstance(v, str):
        return re.sub(r"c=[^&]*&?", "", v)
    return v


CANVAS = re.compile(r"<canvas[^>]*>")   # Chart.js writes its size into the canvas tag as it resizes; that is not content


def apply_norm(v, rules, counts):
    """Take what a change meant to add out of a capture (see the module text); counts[i] is how many things rule i changed."""
    if isinstance(v, str):
        for i, r in enumerate(rules):
            if "sub" in r:
                rep = r["sub"][1]
                new = r["_rx"].sub((lambda m: m.group(2) if int(m.group(2)) - int(m.group(1)) == 4 else m.group(0)) if rep == "$window" else rep, v)
                if new != v:
                    counts[i] += 1
                    v = new
        return v
    if isinstance(v, list):
        out = []
        for x in v:
            hit = next((i for i, r in enumerate(rules) if ("drop_item" in r and x == r["drop_item"]) or ("drop_pair" in r and isinstance(x, list) and len(x) == 2 and isinstance(x[0], str) and r["_rp"].search(x[0]))), None)
            if hit is not None:
                counts[hit] += 1
            else:
                out.append(apply_norm(x, rules, counts))
        return out
    if isinstance(v, dict):
        out = {}
        for k, x in v.items():
            hit = next((i for i, r in enumerate(rules) if "drop_key" in r and r["_rk"].search(k)), None)
            if hit is not None:
                counts[hit] += 1
            else:
                out[k] = apply_norm(x, rules, counts)
        return out
    return v


def strip_racy(name, d):
    """The address bar of the Economy tab is written by a timer; older captures recorded it, and it is not part of the comparison."""
    if name.startswith("economy") and isinstance(d.get("configs"), dict):
        for c in d["configs"].values():
            c.pop("hash", None)


def walk(a, b, path, out):
    if isinstance(a, dict) and isinstance(b, dict):
        for k in sorted(set(a) | set(b), key=str):
            if k not in a:
                out.append((f"{path}.{k}", "<missing>", "present"))
            elif k not in b:
                out.append((f"{path}.{k}", "present", "<missing>"))
            else:
                walk(normal(k, a[k]), normal(k, b[k]), f"{path}.{k}", out)
    elif isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            out.append((path, f"list of {len(a)}", f"list of {len(b)}"))
        for i, (x, y) in enumerate(zip(a, b)):
            walk(x, y, f"{path}[{i}]", out)
    elif isinstance(a, (int, float)) and isinstance(b, (int, float)) and not isinstance(a, bool) and not isinstance(b, bool):
        if not (a == b or math.isclose(a, b, rel_tol=REL, abs_tol=ABS)):
            out.append((path, a, b))
    elif a != b and not (isinstance(a, str) and isinstance(b, str) and CANVAS.sub("<canvas>", a) == CANVAS.sub("<canvas>", b)):
        out.append((path, a, b))


def short(v, n=170):
    s = json.dumps(v, ensure_ascii=False) if not isinstance(v, str) else v
    return s if len(s) <= n else s[: n // 2] + " ... " + s[-n // 2:]


def first_diff(a, b):
    if not (isinstance(a, str) and isinstance(b, str)):
        return ""
    i = next((k for k in range(min(len(a), len(b))) if a[k] != b[k]), min(len(a), len(b)))
    return f"   first difference at character {i}: old ...{a[max(0, i - 60):i + 80]!r}\n                                    new ...{b[max(0, i - 60):i + 80]!r}"


def main(argv):
    args = [a for a in argv[1:] if not a.startswith("--")]
    show = int(argv[argv.index("--show") + 1]) if "--show" in argv else 12
    if "--show" in argv:
        args = [a for a in args if a != str(show)]
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    expect, rules = [], []
    if "--expect" in argv:
        ef = argv[argv.index("--expect") + 1]
        args = [a for a in args if a != ef]
        for e in json.loads(Path(ef).read_text(encoding="utf-8")):
            if "path" in e:
                expect.append((re.compile(e["path"]), e["why"]))
            else:
                if "sub" in e:
                    e["_rx"] = re.compile(e["sub"][0], re.S)
                if "drop_key" in e:
                    e["_rk"] = re.compile(e["drop_key"])
                if "drop_pair" in e:
                    e["_rp"] = re.compile(e["drop_pair"])
                rules.append(e)
    if len(args) != 2:
        print(__doc__)
        return 2
    d, name = Path(args[0]), args[1]
    old = json.loads((d / f"old_{name}.json").read_text(encoding="utf-8"))
    new = json.loads((d / f"new_{name}.json").read_text(encoding="utf-8"))
    envs = [side.pop("env", None) for side in (old, new)]
    if envs[1] and envs[1].get("mobile"):
        print("  warning: the new capture ran in a mobile-width page (legends start folded, symbols are smaller); run it in a desktop-width page")
    elif envs[0] and envs[1] and envs[0] != envs[1]:
        print(f"  warning: the two captures ran in pages of different width: {envs[0]} and {envs[1]}")
    for side in (old, new):
        side.pop("tag", None)
        strip_racy(name, side)
    if rules:
        counts = [0] * len(rules)
        old = apply_norm(old, rules, [0] * len(rules))
        new = apply_norm(new, rules, counts)
        for r, n in zip(rules, counts):
            print(f"  normalised ({n}): {r['why']}")
    out = []
    walk(old, new, name, out)
    if not out:
        print(f"{name}: identical ({len(json.dumps(old)) // 1024} KB compared)")
        return 0
    expected = {}
    rest = []
    for d in out:
        why = next((w for rx, w in expect if rx.search(d[0])), None)
        if why:
            expected.setdefault(why, []).append(d[0])
        else:
            rest.append(d)
    for why, paths in expected.items():
        print(f"  expected ({len(paths)}): {why}")
    out = rest
    if not out:
        print(f"{name}: only the expected differences ({sum(len(p) for p in expected.values())})")
        return 0
    print(f"{name}: {len(out)} differences")
    seen = set()
    for path, a, b in out:
        top = re.sub(r"\[\d+\]", "[]", path)
        top = ".".join(top.split(".")[:4])
        if top in seen and len(seen) > show:
            continue
        seen.add(top)
        if len(seen) > show:
            break
        print(f"  {path}\n     old: {short(a)}\n     new: {short(b)}")
        fd = first_diff(a, b)
        if fd:
            print(fd)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
