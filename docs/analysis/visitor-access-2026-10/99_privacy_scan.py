"""Privacy scan of everything this analysis wrote: does any output contain a business name, address, website or e-mail from places.json?
Matches are reported masked (first two characters and length only), never in full.
"""
from common import *
import re

places = jload("places.json")
names = set()
addrs = set()
webs = set()
for p in places:
    n = (p.get("name") or "").strip().lower()
    if len(n) >= 8:
        names.add(n)
    a = (p.get("address") or "").strip().lower()
    if len(a) >= 10:
        addrs.add(a)
    w_ = (p.get("website") or "").strip().lower()
    if w_:
        webs.add(w_.replace("https://", "").replace("http://", "").rstrip("/"))
print("names", len(names), "addresses", len(addrs), "websites", len(webs))

SKIP = {"ati_gtfs.zip", "ati_open.html", "ati_urbana.html", "99_privacy_scan.py"}
files = [f for f in HERE.rglob("*") if f.is_file() and f.suffix.lower() in (".md", ".json", ".csv", ".txt", ".py") and f.name not in SKIP]
total = 0
for f in sorted(files):
    txt = f.read_text(encoding="utf-8", errors="replace").lower()
    hits = [n for n in names if n in txt]
    ah = [a for a in addrs if a in txt]
    wh = [w_ for w_ in webs if w_ in txt]
    em = re.findall(r"[\w.+-]+@[\w-]+\.[\w.]+", txt)
    if hits or ah or wh or em:
        total += 1
        print(f.relative_to(HERE), "| name hits", len(hits), [h[:2] + "***(" + str(len(h)) + ")" for h in hits[:6]], "| address hits", len(ah), "| website hits", len(wh), "| emails", len(em))
print("files scanned", len(files), "files with hits", total)
