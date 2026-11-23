"""The Knowledge registry (docs/knowledge-plan-2026-11.md, HANDOFF decision 90; fields in docs/knowledge-areas.md).

    python knowledge.py           check knowledge_src/items.json and write the two files made from it
    python knowledge.py --check   check it and exit 1 if a file made from it is out of date (the tests run this)

Writes:
  site/js/core/knowledge.js   the AREAS list between its two marker lines (the tabs and notices of every area page; no network)
  site/js/knowledge_items.js  window.KNOWLEDGE for the Knowledge home page (knowledge.html): the published, public items with
                              their cards, the kinds, the reviewers, the domains they use and the titles of the datasets they use

An item with "audience": "internal" is checked but never written into site/: internal work belongs to fpr-platform (plan, section 9).
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "knowledge_src" / "items.json"
SITE = ROOT / "site"
CORE = SITE / "js" / "core" / "knowledge.js"
ITEMS_JS = SITE / "js" / "knowledge_items.js"
START = "  // <knowledge:areas> written by knowledge.py from knowledge_src/items.json: edit that file, then run python knowledge.py"
END = "  // </knowledge:areas>"

STATUSES = ("published", "in_review", "hidden")
AUDIENCES = ("public", "internal")
AREA_KEYS = ("id", "label", "icon", "page", "status", "review", "ai")   # what the area pages need; `domain` is the first of `domains`
CARD_KEYS = ("id", "label", "title", "icon", "page", "status", "review", "ai", "kind", "domains", "updated", "cite", "summary", "datasets", "related", "reviewer")


def load_json(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def bilingual(v):
    return isinstance(v, dict) and all(isinstance(v.get(k), str) and v[k].strip() for k in ("en", "es"))


def problems(reg, domain_ids, dataset_ids, site=SITE):
    """Every rule the registry breaks, as text; an empty list when it is sound."""
    P = []
    if reg.get("version") != 1:
        P.append("version must be 1")
    kinds, reviewers = reg.get("kinds") or {}, reg.get("reviewers") or {}
    for k, v in list(kinds.items()) + list(reviewers.items()):
        if not bilingual(v):
            P.append(f"{k}: needs English and Spanish")
    items = reg.get("items") or []
    ids = [it.get("id") for it in items]
    for d in sorted({i for i in ids if ids.count(i) > 1}):
        P.append(f"{d}: id used twice")
    for it in items:
        i = it.get("id") or "?"
        if not re.fullmatch(r"[a-z][a-z0-9]*", str(i)):
            P.append(f"{i}: id must be lower-case letters and digits")
        for f in ("label", "title", "summary"):
            if not bilingual(it.get(f)):
                P.append(f"{i}: {f} needs English and Spanish")
        if it.get("status") not in STATUSES:
            P.append(f"{i}: status must be one of {', '.join(STATUSES)}")
        if it.get("review") and it.get("status") != "published":
            P.append(f"{i}: review: true is only for a published item")
        if it.get("audience") not in AUDIENCES:
            P.append(f"{i}: audience must be public or internal")
        if it.get("kind") not in kinds:
            P.append(f"{i}: kind {it.get('kind')!r} is not in kinds")
        page = it.get("page") or ""
        if it.get("audience") == "public" and not (site / page).is_file():
            P.append(f"{i}: page {page!r} is not in site/")
        if not it.get("icon"):
            P.append(f"{i}: needs an icon")
        doms = it.get("domains") or []
        if not doms:
            P.append(f"{i}: needs at least one domain (the first is its home)")
        for d in doms:
            if d not in domain_ids:
                P.append(f"{i}: domain {d!r} is not in dictionary_src/domains.json")
        if len(set(doms)) != len(doms):
            P.append(f"{i}: a domain is listed twice")
        for d in it.get("datasets") or []:
            if d not in dataset_ids:
                P.append(f"{i}: dataset {d!r} is not in dictionary_src/datasets.json")
        for r in it.get("related") or []:
            if r == i or r not in ids:
                P.append(f"{i}: related {r!r} is not another item")
        for r in it.get("reviewer") or []:
            if r not in reviewers:
                P.append(f"{i}: reviewer {r!r} is not in reviewers")
        if not re.fullmatch(r"20\d\d-(0[1-9]|1[0-2])", str(it.get("updated") or "")):
            P.append(f"{i}: updated must be YYYY-MM")
        if not str(it.get("cite") or "").startswith("#"):
            P.append(f"{i}: cite must be the anchor of the page's cite text, like #sources")
    pub = {it.get("id") for it in items if it.get("audience") == "public"}
    for it in items:
        if it.get("audience") == "public":
            for r in it.get("related") or []:
                if r in ids and r not in pub:
                    P.append(f"{it.get('id')}: related {r!r} is internal, so a public page cannot link to it")
    return P


def public(items):
    return [it for it in items if it.get("audience") == "public"]


def js(v):
    """A value as the hand-written JS of core/knowledge.js: single quotes, bare keys, spaces inside braces (other code and tests read it that way)."""
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, str):
        return "'" + v.replace("\\", "\\\\").replace("'", "\\'") + "'"
    if isinstance(v, dict):
        key = lambda k: k if re.fullmatch(r"[A-Za-z_$][\w$]*", k) else js(k)
        return "{ " + ", ".join(f"{key(k)}: {js(x)}" for k, x in v.items()) + " }"
    if isinstance(v, list):
        return "[" + ", ".join(js(x) for x in v) + "]"
    return json.dumps(v)


HEADER_KEYS = ("reviewer", "updated")   # what an area page header adds (Knowledge PR 2): keys and a date; the foot reads related and cite from knowledge_items.js


def areas_block(items, reg=None, domains=(), datasets=()):
    """The generated part of core/knowledge.js: AREAS (every public item with what its tab and header need), the names of their top domains
    (TOPICS) and the reviewers' names (REVIEWERS). Titles, summaries and dataset names stay out of it: an in-review area's placeholder page
    loads this file, and it must carry no program terms (tests/knowledge.test.js). The foot's titles and dataset names come from
    js/knowledge_items.js, which a published area page loads after it is ready (core/knowledge.js render())."""
    pub = public(items)
    lines = [START]
    lines.append("  const AREAS = [")
    for it in pub:
        a = {k: it[k] for k in AREA_KEYS if k in it and it[k] not in (None, False)}
        for k in HEADER_KEYS:
            if it.get(k):
                a[k] = it[k]
        a["domain"] = it["domains"][0]   # last: tests and catalog.py read `... domain: '<id>' }`
        lines.append("    " + js(a) + ",")
    lines.append("  ];")
    tops = {it["domains"][0].split(".")[0] for it in pub}
    names = {d["id"]: d["name"] for d in domains if d["id"] in tops}
    lines.append("  const TOPICS = " + js({k: names[k] for k in sorted(names)}) + ";")
    lines.append("  const REVIEWER_NAMES = " + js((reg or {}).get("reviewers") or {}) + ";")
    lines.append(END)
    return "\n".join(lines)


def core_text(old, items, reg=None, domains=(), datasets=()):
    if START not in old or END not in old:
        raise SystemExit(f"{CORE.relative_to(ROOT)}: the marker lines are missing")
    a, b = old.index(START), old.index(END) + len(END)
    return old[:a] + areas_block(items, reg, domains, datasets) + old[b:]


def items_text(reg, domains, datasets):
    items = [it for it in public(reg["items"]) if it["status"] == "published"]   # an item in review or hidden gets no card (its page is a placeholder)
    used = {d for it in items for d in it["domains"]}
    used |= {d.split(".")[0] for d in used}   # a sub-domain's parent, for the group heading
    dom = [{"id": d["id"], "order": d.get("order", 0), "name": d["name"]} for d in domains if d["id"] in used]
    want = {d for it in items for d in it.get("datasets") or []}
    titles = {d["id"]: d["title"] for d in datasets if d["id"] in want}
    data = {
        "kinds": reg["kinds"], "reviewers": reg["reviewers"], "domains": sorted(dom, key=lambda d: d["order"]),
        "items": [{k: it[k] for k in CARD_KEYS if k in it} for it in items], "datasets": titles,
    }
    body = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    return ("/* PR Data Observatory: the Knowledge home page's items (knowledge.html). Written by knowledge.py from knowledge_src/items.json:\n"
            "   edit that file, then run python knowledge.py. Only published, public items are here (docs/knowledge-plan-2026-11.md). */\n"
            f"window.KNOWLEDGE = {body};\n")


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    check = "--check" in argv
    reg = load_json(SRC)
    domains = load_json(ROOT / "dictionary_src" / "domains.json")
    domains = domains.get("domains", domains)
    datasets = load_json(ROOT / "dictionary_src" / "datasets.json")["datasets"]
    P = problems(reg, {d["id"] for d in domains}, {d["id"] for d in datasets})
    for p in P:
        print("knowledge:", p)
    if P:
        return 1
    out = {CORE: core_text(CORE.read_text(encoding="utf-8"), reg["items"], reg, domains, datasets), ITEMS_JS: items_text(reg, domains, datasets)}
    stale = [p for p, t in out.items() if not p.is_file() or p.read_text(encoding="utf-8") != t]
    if check:
        for p in stale:
            print(f"knowledge: {p.relative_to(ROOT)} is out of date: run python knowledge.py")
        return 1 if stale else 0
    for p in stale:
        p.write_text(out[p], encoding="utf-8", newline="\n")
        print(f"knowledge: wrote {p.relative_to(ROOT)}")
    n = len(public(reg["items"]))
    print(f"knowledge: {len(reg['items'])} items, {n} public")
    return 0


if __name__ == "__main__":
    sys.exit(main())
