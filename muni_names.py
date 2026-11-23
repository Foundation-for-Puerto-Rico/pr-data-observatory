"""Municipio names to Census FIPS ids (72001-72153), one helper for every source that names a municipio instead of giving its id.

    from muni_names import municipio_id
    municipio_id("MUNICIPIO AUTONOMO DE MAYAGUEZ")   # '72097'
    municipio_id("Bayam?n")                         # '72021' (a lost ñ or accent matches any one letter, when only one municipio fits)
    municipio_id("Statewide")                       # None

The names come from the geography crosswalk (site/data/geo/crosswalk.json, built by geo.py), so there is one list of the 78. Joins between
published files use ids; this helper is only for sources that give names (OGP budget lines, Contralor contracts, audits, portal tables).
"""
import json
import re
import unicodedata
from functools import lru_cache
from pathlib import Path

CROSSWALK = Path(__file__).parent / "site" / "data" / "geo" / "crosswalk.json"

# How sources wrap a municipio's name. Removed before matching; the order matters (longest first).
WRAPPERS = [
    r"^GOBIERNO MUNICIPAL (?:AUTONOMO )?DE ", r"^MUNICIPIO AUTONOMO DE ", r"^MUNICIPIO DE ", r"^AUTONOMOUS MUNICIPALITY OF ",
    r"^MUNICIPALITY OF ", r"^MUNICIPIO ", r",? MUNICIPALITY OF$", r" MUNICIPIO,? PUERTO RICO$", r",? PUERTO RICO$", r",? PR$",
    r" MUNICIPIO$", r" MUNICIPALITY$",
]
# Spellings that are not just a lost accent (seen in FAC and USAspending downloads).
TYPOS = {"MANAT1": "MANATI", "LOIZA ALDEA": "LOIZA"}
LOST = ("?", chr(0xFFFD))   # what a source shows where it lost ñ, á, í...
WILD = chr(0)               # one unreadable letter, kept through the clean-up


def name_key(s):
    """Upper case, ASCII letters and single spaces; a lost letter kept as a one-letter wildcard; wrappers like 'Municipio de' removed."""
    s = str(s or "")
    for c in LOST:
        s = s.replace(c, WILD)
    s = "".join(c for c in unicodedata.normalize("NFKD", s) if unicodedata.category(c) != "Mn").upper()
    for a, b in TYPOS.items():
        s = re.sub(r"\b" + a + r"\b", b, s)
    s = re.sub(r"\s+", " ", re.sub("[^A-Z," + WILD + "]", " ", s)).strip()
    for w in WRAPPERS:
        s = re.sub(w, "", s).strip()
    return re.sub(r"\s+", " ", s.replace(",", " ")).strip()


@lru_cache(maxsize=1)
def municipios(path=CROSSWALK):
    """{name_key: geoid} for the 78 municipios, from the crosswalk's Spanish and English names."""
    cw = json.loads(Path(path).read_text(encoding="utf-8"))
    F = cw["fields"]
    out = {}
    for u in cw["units"]["municipio"]:
        r = dict(zip(F, u))
        for n in (r["name_es"], r["name_en"]):
            out[name_key(n)] = r["id"]
    return out


def municipio_id(name, path=CROSSWALK):
    """The 5-digit geoid of the municipio a name or id refers to, or None (island-wide, unknown or more than one possible match)."""
    if name is None:
        return None
    t = str(name).strip()
    by = municipios(path)
    if re.fullmatch(r"\d{1,5}", t):
        g = t if len(t) == 5 else "72" + t.zfill(3)
        return g if g in set(by.values()) else None
    k = name_key(t)
    if k in by:
        return by[k]
    if WILD in k:
        rx = re.compile("^" + ".".join(re.escape(p) for p in k.split(WILD)) + "$")
        hits = {g for n, g in by.items() if rx.match(n)}
        return hits.pop() if len(hits) == 1 else None
    return None
