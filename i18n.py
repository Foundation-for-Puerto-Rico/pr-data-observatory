"""Builds the Spanish string bundles for the site from i18n_src/ and checks that they stay complete.

  python i18n.py              build site/i18n/es.<page>.js for every page (one file per page, merged from its scopes), and es.<page>.<module>.js for each module of a page
  python i18n.py --check      validate the sources without writing (the build runs this); exit 1 on errors
  python i18n.py --keys PAGE  list the keys the page's scripts ask for (T(), Tn(), Th()) that its Spanish bundle lacks
  python i18n.py --stats      strings per scope and per page, with the size of each bundle

The Spanish summaries of the data dictionary entries live apart, in i18n_src/dictionary_plain.json ({entry id: {"en": the English
plain it translates, "es": Spanish}}); dictionary.py puts them in site/data/dictionary.json. --check warns for each entry without one.

The code is written in English and every user-visible English string is its own key (see site/js/i18n.js and docs/i18n.md).
i18n_src/es/<scope>.json maps English text to Spanish: a string, or [one, other] for plurals (the key is the "one" form).
i18n_src/pages.json says which scopes and scripts each page uses. A page's "modules" are the parts it loads on first use (the Scenarios view, the
land-use analysis...): each gets its own bundle, which the module's loader fetches with I18N.load('<module>') before it renders, so their Spanish stays out
of the page bundle. A module's bundle holds its scopes and every key its scripts ask for that the page's module scopes translate, less what the page bundle
already has; the check runs each module's scripts against the page bundle plus that module's bundle alone, as the browser has them. Two things keep text that only a module
shows out of the page bundle: a data label spec's "modules" ({page: module}: on that page the labels load with that module's bundle, as the RVI input labels of the
WCRP page do with its vulnerability map), a module's "html" (the ids of elements of the page whose static text the module's loader translates, with
I18N.apply(element), once its bundle is in: text shown only there loads with the module, as the map's About tab does) and a page's "pick" (scopes shared
with other pages, of which the page bundle takes only the keys the page's scripts ask for, its HTML shows or its data labels need). The build fails when a script asks for a key that has no
Spanish, when a Spanish text loses a {placeholder} or an HTML tag of its English key, or when two scopes translate one key differently.
"""
import html
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).parent
SRC = ROOT / "i18n_src"
SITE = ROOT / "site"
OUT = SITE / "i18n"

PLACEHOLDER = re.compile(r"\{(\w+)\}")
TAG = re.compile(r"<\s*/?\s*([A-Za-z][A-Za-z0-9]*)([^>]*)>")
# T('key'), T("key"), T(`key`), Tn(n, 'one', 'other'), Th('key'), with the usual escapes inside the literal
LIT = r"""(?P<q>['"`])(?P<s>(?:\\.|(?!(?P=q)).)*)(?P=q)"""
CALL_T = re.compile(r"(?<![\w$.])(?:T|Th|TK)\s*\(\s*" + LIT, re.S)   # TK('text') marks a key that is translated later, where it is shown
CALL_TN = re.compile(r"(?<![\w$.])Tn\s*\(\s*[^,()]+(?:\([^()]*\))?[^,()]*,\s*" + LIT, re.S)
ESCAPES = {"n": "\n", "t": "\t", "r": "\r", "'": "'", '"': '"', "`": "`", "\\": "\\", "$": "$"}


def unescape(s):
    return re.sub(r"\\(u[0-9a-fA-F]{4}|x[0-9a-fA-F]{2}|.)", lambda m: chr(int(m.group(1)[1:], 16)) if m.group(1)[0] in "ux" and len(m.group(1)) > 1 else ESCAPES.get(m.group(1), m.group(1)), s)


def load_json(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def load_pages():
    return load_json(SRC / "pages.json")


def load_scopes(pages):
    """{scope: {key: value}} from i18n_src/es/<scope>.json, plus problems."""
    scopes, problems = {}, []
    for f in sorted((SRC / "es").glob("*.json")):
        try:
            d = load_json(f)
        except ValueError as e:
            problems.append(("error", f.name, "-", f"not valid JSON: {e}"))
            continue
        scopes[f.stem] = {k: v for k, v in d.items() if not k.startswith("_")}
    used = {s for p in pages["pages"].values() for s in p["scopes"] + [x for m in p.get("modules", {}).values() for x in m["scopes"]]}
    for s in used - set(scopes):
        problems.append(("error", "pages.json", s, "scope has no file in i18n_src/es/"))
    return scopes, problems


def tags_of(s):
    return [(m.group(1).lower(), re.sub(r"\s+", " ", m.group(2)).strip()) for m in TAG.finditer(s)]


def validate(scopes, keep):
    P = []
    seen = {}
    for scope, d in scopes.items():
        for k, v in d.items():
            where = f"{scope}.json"
            vals = v if isinstance(v, list) else [v]
            if not all(isinstance(x, str) and x.strip() for x in vals) or (isinstance(v, list) and len(v) != 2):
                P.append(("error", where, k, "value must be a non-empty string or [one, other]"))
                continue
            kp = set(PLACEHOLDER.findall(k))
            for x in vals:
                if set(PLACEHOLDER.findall(x)) - kp:
                    P.append(("error", where, k, f"Spanish uses a placeholder the key lacks: {sorted(set(PLACEHOLDER.findall(x)) - kp)}"))
                if not isinstance(v, list) and kp - set(PLACEHOLDER.findall(x)):
                    P.append(("error", where, k, f"Spanish drops placeholder(s) {sorted(kp - set(PLACEHOLDER.findall(x)))}"))
                if "<" in k and tags_of(k) != tags_of(x):
                    P.append(("error", where, k, "HTML tags of the Spanish text differ from the key (same tags and attributes, in the same order)"))
                if k.rstrip().endswith("?") and not x.lstrip().startswith("¿") and "<" not in k:
                    P.append(("warn", where, k, "a question should open with ¿"))
                if re.search(r"\s{2,}|^\s|\s$", x):
                    P.append(("warn", where, k, "extra whitespace in the Spanish text"))
                if x == k and len(re.findall(r"[A-Za-z]{4,}", k)) >= 1 and k not in keep and not re.search(r"[<{]", k):
                    P.append(("warn", where, k, "Spanish equals the English key: translate it, or list it in i18n_src/keep.json if it is a name"))
            if k in seen and seen[k][1] != v:
                P.append(("error", where, k, f"also translated in {seen[k][0]}.json with different Spanish"))
            seen.setdefault(k, (scope, v))
    return P


def merged_all(pages, scopes, page):
    """Every key of the page's scopes."""
    out = {}
    for s in pages["pages"][page]["scopes"]:
        out.update(scopes.get(s, {}))
    return out


def shown_text(text):
    """HTML with runs of whitespace made one space, as written and with its entities read (keys are the text the browser shows)."""
    return re.sub(r"\s+", " ", text) + "\n" + re.sub(r"\s+", " ", html.unescape(text))


def element_html(src, el_id):
    """The outer HTML of the element with id="el_id" in src, or None: from its start tag to the end tag that closes it (elements of its kind nested inside counted)."""
    m = re.search(r'<([A-Za-z][\w-]*)\b[^>]*\bid="' + re.escape(el_id) + r'"[^>]*>', src)
    if not m:
        return None
    tag, depth, pos = m.group(1).lower(), 1, m.end()
    for t in re.finditer(r"<(/?)" + re.escape(tag) + r"\b[^>]*>", src[pos:], re.I):
        if t.group(0).endswith("/>"):
            continue
        depth += -1 if t.group(1) else 1
        if depth == 0:
            return src[m.start():pos + t.end()]
    return None


def whole_in(key, text):
    """Whether key is the whole of a text, an attribute value or an element's content in text (shown_text of HTML): "adds" inside a longer sentence is not."""
    k = re.sub(r"\s+", " ", key).strip()
    return bool(k) and re.search(r'[>"] ?' + re.escape(k) + r' ?[<"]', text) is not None


def page_parts(pages, page):
    """The page's HTML text split in two: what shows at first load, and {module: the text of the elements that module translates when it loads}."""
    spec = pages["pages"][page]
    f = spec.get("file")
    src = (SITE / f).read_text(encoding="utf-8") if f and (SITE / f).exists() else ""
    parts = {}
    for mod, ms in modules(pages, page).items():
        for el_id in ms.get("html", []):
            frag = element_html(src, el_id)
            if frag:
                parts[mod] = parts.get(mod, "") + shown_text(frag) + "\n"
                src = src.replace(frag, "", 1)
    return shown_text(src), parts


def page_text(page_spec):
    """The page's HTML as shown_text() gives it."""
    f = page_spec.get("file")
    if not f or not (SITE / f).exists():
        return ""
    return shown_text((SITE / f).read_text(encoding="utf-8"))


def first_load_keys(pages, page):
    """What the page needs before any module loads: the keys its scripts ask for and the data labels it shows itself; and its HTML text."""
    spec = pages["pages"][page]
    keys = set()
    for js in spec.get("scripts", []):
        if (SITE / "js" / js).exists():
            keys |= {k for k, _ in js_keys(SITE / "js" / js)[0]}
    keys |= {v for _, _, v, on, mods in data_labels(pages) if page in on and page not in mods}
    return keys, page_parts(pages, page)[0]


def held_back(pages, scopes, page):
    """Keys of the page's scopes that its bundle leaves to a module: the labels a data label spec gives to a module of the page, the text of the elements a
    module translates ("html"), and the keys of the page's "pick" scopes, unless the page's scripts ask for them, its HTML outside those elements shows them or a
    data label of the page itself needs them."""
    spec = pages["pages"][page]
    pick = [s for s in spec.get("pick", []) if s in spec["scopes"]]
    to_mod = {v for _, _, v, on, mods in data_labels(pages, only_page=page) if page in mods}
    if any(ms.get("html") for ms in modules(pages, page).values()):
        frags = "\n".join(page_parts(pages, page)[1].values())
        to_mod |= {k for k in merged_all(pages, scopes, page) if whole_in(k, frags)}
    if not pick and not to_mod:
        return set()
    plain = set()   # a key of a picked scope that a scope not picked also has stays
    for s in spec["scopes"]:
        if s not in pick:
            plain |= set(scopes.get(s, {}))
    cand = to_mod | ({k for s in pick for k in scopes.get(s, {})} - plain)
    used, text = first_load_keys(pages, page)
    shown = lambda k: re.sub(r"\s+", " ", k) in text
    return {k for k in cand if k not in used and not shown(k)}


def merged(pages, scopes, page):
    """The page bundle: its scopes, less what held_back() leaves to its modules."""
    out = merged_all(pages, scopes, page)
    held = held_back(pages, scopes, page)
    return {k: v for k, v in out.items() if k not in held} if held else out


def modules(pages, page):
    return pages["pages"][page].get("modules", {})


def module_bundle(pages, scopes, page, mod):
    """The Spanish a module brings: its scopes, and the keys its scripts ask for that any module scope of the page translates, less the page bundle."""
    base, pool, out = merged(pages, scopes, page), {}, {}
    for m in modules(pages, page).values():
        for s in m["scopes"]:
            pool.update(scopes.get(s, {}))
    full = merged_all(pages, scopes, page)
    for k in full:   # what the page bundle leaves to its modules (held_back)
        if k not in base:
            pool.setdefault(k, full[k])
    spec = modules(pages, page)[mod]
    for s in spec["scopes"]:
        out.update(scopes.get(s, {}))
    for js in spec["scripts"]:
        if (SITE / "js" / js).exists():
            for k, _ in js_keys(SITE / "js" / js)[0]:
                if k in pool:
                    out.setdefault(k, pool[k])
    for _, _, v, on, mods in data_labels(pages, only_page=page):   # the data labels that load with this module
        if mods.get(page) == mod and v in pool:
            out.setdefault(v, pool[v])
    if spec.get("html"):   # the static text of the elements it translates
        frag = page_parts(pages, page)[1].get(mod, "")
        for k in pool:
            if whole_in(k, frag):
                out.setdefault(k, pool[k])
    return {k: v for k, v in out.items() if k not in base}


LOAD = re.compile(r"""I18N\.load\(\s*(['"])(\w+)\1""")   # I18N.load('module'): a module's loader fetching its bundle


def js_keys(path):
    """Static keys a script asks for. Returns (keys, problems) where problems are T() calls whose key is a template with ${...}."""
    src = path.read_text(encoding="utf-8")
    keys, bad = [], []
    for rx in (CALL_T, CALL_TN):
        for m in rx.finditer(src):
            raw = m.group("s")
            line = src.count("\n", 0, m.start()) + 1
            if m.group("q") == "`" and "${" in raw:
                bad.append((line, raw[:80]))
                continue
            keys.append((unescape(raw), line))
    return keys, bad


def data_labels(pages, optional=False, only_page=None):
    """Display strings that live in data files and reach the screen through T(variable): they must have Spanish too. A spec with "required": false lists text a page
    shows in Spanish when there is Spanish for it and in English otherwise (the names of dictionary entries in the Catalog tab): it is left out unless `optional`,
    which the check of unused keys asks for. A spec's "modules" ({page: module}) says the labels load, on that page, with that module's bundle, not the page's.
    Yields (file, path, value, pages, modules); `only_page` reads only the specs that give a module of that page labels."""
    out = []
    for spec in pages.get("data_labels", []):
        if spec.get("required", True) is False and not optional:
            continue
        mods = spec.get("modules") or {}
        if only_page is not None and only_page not in mods:
            continue
        p = SITE / "data" / spec["file"]
        if not p.exists():
            continue
        data = load_json(p)
        for path in spec["paths"]:
            cur = [data]
            for part in path.split("."):
                nxt = []
                for c in cur:
                    if part == "*":
                        nxt += list(c.values()) if isinstance(c, dict) else []
                    elif part == "[]":
                        nxt += c if isinstance(c, list) else []
                    elif part.endswith("[]"):
                        c = c.get(part[:-2]) if isinstance(c, dict) else None
                        nxt += c if isinstance(c, list) else []
                    elif part.isdigit():   # a column of a row kept as a list ("index.rows[].1")
                        nxt.append(c[int(part)] if isinstance(c, list) and len(c) > int(part) else None)
                    elif isinstance(c, dict):
                        nxt.append(c.get(part))
                cur = nxt
            seen = set()
            for v in cur:
                if isinstance(v, str) and spec.get("transform") == "humanize":   # the pages show humanize(value): underscores to spaces, first letter capital
                    v = v.replace("_", " ")[:1].upper() + v.replace("_", " ")[1:]
                if isinstance(v, str) and re.search(r"[A-Za-z]{2}", v) and v not in seen:
                    seen.add(v)
                    for pre in spec.get("prefixes") or [""]:   # a label the engine composes ("Residents: " + the family's label)
                        out.append((spec["file"], path, pre + v, spec["pages"], mods))
    return out


def check_scripts(P, page, scripts, d, what):
    """Every key the scripts ask for must be in d; returns the modules they load with I18N.load()."""
    loads = set()
    for js in scripts:
        f = SITE / "js" / js
        if not f.exists():
            P.append(("error", "pages.json", page, f"script {js} does not exist"))
            continue
        keys, bad = js_keys(f)
        for line, k in bad:
            P.append(("error", f"js/{js}", line, f"T() key is a template literal with ${{}}: use {{name}} placeholders ({k!r})"))
        seen = set()
        for k, line in keys:
            if k in seen:
                continue
            seen.add(k)
            if k not in d:
                P.append(("error", f"js/{js}", line, f"{what} has no Spanish for: {k[:90]!r}"))
        loads |= {m.group(2) for m in LOAD.finditer(f.read_text(encoding="utf-8"))}
    return loads


def check(pages, scopes, keep, verbose=True):
    P = validate(scopes, keep)
    for page, spec in pages["pages"].items():
        d = merged(pages, scopes, page)
        loads = check_scripts(P, page, spec.get("scripts", []), d, f"page '{page}'")
        for mod, ms in modules(pages, page).items():
            for js in ms["scripts"]:
                if js in spec.get("scripts", []):
                    P.append(("error", "pages.json", page, f"script {js} is listed in 'scripts' and in module '{mod}': a module's scripts load on first use, so list it only there"))
            # as the browser has it when the module renders: the page bundle and this module's bundle, not another module's
            loads |= check_scripts(P, page, ms["scripts"], {**d, **module_bundle(pages, scopes, page, mod)}, f"page '{page}' (module '{mod}', with its bundle)")
        if any(ms.get("html") for ms in modules(pages, page).values()):
            src = (SITE / spec["file"]).read_text(encoding="utf-8") if spec.get("file") and (SITE / spec["file"]).exists() else ""
            for mod, ms in modules(pages, page).items():
                for el_id in ms.get("html", []):
                    if element_html(src, el_id) is None:
                        P.append(("error", "pages.json", page, f"module '{mod}' translates the element #{el_id}, which the page does not have"))
        for mod in sorted(set(modules(pages, page)) - loads):
            P.append(("error", "pages.json", page, f"no script of the page calls I18N.load('{mod}'): the module's Spanish would never load"))
        for mod in sorted(loads - set(modules(pages, page))):
            P.append(("error", "pages.json", page, f"a script calls I18N.load('{mod}') but the page has no module '{mod}'"))
    bundles = {}   # (page, module or None): the Spanish the page has when the label is shown
    def has(page, mod):
        if (page, mod) not in bundles:
            bundles[page, mod] = {**merged(pages, scopes, page), **(module_bundle(pages, scopes, page, mod) if mod else {})}
        return bundles[page, mod]
    for spec in pages.get("data_labels", []):
        for page, mod in (spec.get("modules") or {}).items():
            if page not in spec["pages"] or page not in pages["pages"] or mod not in modules(pages, page):
                P.append(("error", "pages.json", spec["file"], f"data label modules: '{page}' has no module '{mod}' (or the spec is not for that page)"))
    for file, path, value, on_pages, mods in data_labels(pages):
        for page in on_pages:
            if page not in pages["pages"]:
                continue
            mod = mods.get(page) if mods.get(page) in modules(pages, page) else None
            if value not in has(page, mod):
                P.append(("error", f"data/{file}", path, f"page '{page}'{f' (module {mod!r})' if mod else ''} has no Spanish for the label {value[:80]!r}"))
    # keys no page uses (a key is used when its text occurs in a script, a page, or a data label)
    corpus = []
    for p in list(SITE.glob("*.html")) + list((SITE / "js").glob("*.js")) + list((SITE / "js" / "core").glob("*.js")):
        text = p.read_text(encoding="utf-8")
        corpus.append(re.sub(r"\s+", " ", text))
        if p.suffix == ".html":
            corpus.append(re.sub(r"\s+", " ", html.unescape(text)))   # keys are the text the browser shows, so &amp; in the source counts as &
    labels = " ".join(v for _, _, v, _, _ in data_labels(pages, optional=True))
    blob = "\n".join(corpus) + "\n" + labels
    for scope, d in scopes.items():
        for k in d:
            probe = re.sub(r"\s+", " ", k)
            if probe not in blob and probe.replace("'", "\\'") not in blob and probe.replace("\n", "\\n") not in blob:
                P.append(("warn", f"{scope}.json", k[:70], "not found in any page, script or data label (stale key?)"))
    return P


def dictionary_plain():
    """Warnings for the Spanish summaries of dictionary entries: missing, translating an older English text, or for no entry; errors for a held one."""
    P, f = [], "dictionary_plain.json"
    plain = {e["id"]: e.get("plain") or "" for p in sorted((ROOT / "dictionary_src" / "entries").glob("*.json")) for e in load_json(p)}
    d = {k: v for k, v in load_json(SRC / f).items() if not k.startswith("_")} if (SRC / f).exists() else {}
    held = load_json(SRC / "held_for_review.json").get("dictionary_plain", {}) if (SRC / "held_for_review.json").exists() else {}
    for k, en in plain.items():
        s = d.get(k)
        if k in held:
            if s:
                P.append(("error", f, k, "the Spanish summary is held for review (held_for_review.json): keep it out of this file"))
        elif not en:
            continue
        elif not isinstance(s, dict) or not str(s.get("es") or "").strip():
            P.append(("warn", f, k, "entry has no Spanish summary (the page shows the English plain)"))
        elif s.get("en") != en:
            P.append(("warn", f, k, "the Spanish summary translates an older English plain: update 'es' and copy the new 'en'"))
        elif set(re.findall(r"\d+", en)) - set(re.findall(r"\d+", s["es"])):
            lost = sorted(set(re.findall(r"\d+", en)) - set(re.findall(r"\d+", s["es"])))
            P.append(("warn", f, k, f"Spanish summary drops number(s) {lost}"))
    for k in sorted(set(d) - set(plain)):
        P.append(("warn", f, k, "not an entry id in dictionary_src/entries (renamed or deleted?)"))
    return P


def build(pages, scopes):
    OUT.mkdir(exist_ok=True)
    sizes = {}

    def write(name, d, what):
        body = json.dumps(dict(sorted(d.items())), ensure_ascii=False, separators=(",", ":"))
        text = f"/* Generated by i18n.py from i18n_src/. Do not edit. {what} */\nI18N.add({body});\n"
        (OUT / f"es.{name}.js").write_text(text, encoding="utf-8", newline="\n")   # LF on every system: a Windows build wrote CRLF and CI saw every bundle as changed
        sizes[name] = (len(d), len(text.encode("utf-8")))
    for page in pages["pages"]:
        write(page, merged(pages, scopes, page), f"Page: {page}")
        for mod in modules(pages, page):
            write(f"{page}.{mod}", module_bundle(pages, scopes, page, mod), f"Page: {page}, module: {mod} (loaded on first use)")
    for f in OUT.glob("es.*.js"):   # the bundle of a page or module that no longer exists
        if f.name[3:-3] not in sizes:
            f.unlink()
    return sizes


def main(argv):
    pages = load_pages()
    scopes, problems = load_scopes(pages)
    keep = set(load_json(SRC / "keep.json")) if (SRC / "keep.json").exists() else set()
    if "--stats" in argv:
        for s, d in scopes.items():
            print(f"{s:14s} {len(d):5d} strings")
        for page in pages["pages"]:
            d = merged(pages, scopes, page)
            print(f"page {page:10s} {len(d):5d} strings")
            for mod in modules(pages, page):
                print(f"  module {mod:12s} {len(module_bundle(pages, scopes, page, mod)):5d} strings")
        return 0
    if "--keys" in argv:
        page = argv[argv.index("--keys") + 1]
        d = merged(pages, scopes, page)
        n = 0
        parts = [(None, pages["pages"][page].get("scripts", []))] + [(m, s["scripts"]) for m, s in modules(pages, page).items()]
        for mod, scripts in parts:
            dm = {**d, **module_bundle(pages, scopes, page, mod)} if mod else d
            for js in scripts:
                keys, _ = js_keys(SITE / "js" / js)
                for k, line in keys:
                    if k not in dm:
                        n += 1
                        print(f"{js}:{line}  {k}" + (f"  (module {mod})" if mod else ""))
        print(f"{n} missing")
        return 1 if n else 0
    problems += check(pages, scopes, keep) + dictionary_plain()
    errs = [p for p in problems if p[0] == "error"]
    warns = [p for p in problems if p[0] != "error"]
    show = problems if "--verbose" in argv else errs + warns[:15]
    for sev, f, i, msg in show:
        print(f"  {sev.upper():5s} {f}:{i}  {msg}")
    if len(warns) > 15 and "--verbose" not in argv:
        print(f"  ... {len(warns) - 15} more warnings (use --verbose)")
    print(f"i18n: {len(scopes)} scopes, {sum(len(d) for d in scopes.values())} strings, {len(errs)} errors, {len(warns)} warnings")
    if "--check" in argv:
        return 1 if errs else 0
    sizes = build(pages, scopes)
    for page, (n, b) in sizes.items():
        print(f"  site/i18n/es.{page}.js  {n} strings, {b / 1024:.1f} KB")
    return 1 if errs else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
