"""Reads the rows of an .xlsx sheet from its XML, with the standard library only (the build installs no Excel reader; openpyxl also stops at a sheet property
of HUD's LIHTC file). Used by facilities.py (HUD's LIHTC database) and economy_series.py (the CDFI Fund's NMTC release).

    rows(data, sheet=None)   the rows of the sheet named `sheet` (or of the first sheet), each {column index: text or None}; numbers stay text
"""

import io
import re
import xml.etree.ElementTree as ET
import zipfile

NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
REL = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"


def sheet_path(x, sheet):
    """The member that holds the named sheet (or the first sheet), from xl/workbook.xml and its relationships."""
    wb = ET.fromstring(x.read("xl/workbook.xml"))
    tabs = [(s.get("name"), s.get(REL)) for s in wb.iter(NS + "sheet")]
    rid = next((r for n, r in tabs if sheet is None or n == sheet), None)
    if rid is None:
        raise KeyError(f"no sheet named {sheet!r} (the file has {[n for n, _ in tabs]})")
    rels = ET.fromstring(x.read("xl/_rels/workbook.xml.rels"))
    target = next(r.get("Target") for r in rels if r.get("Id") == rid)
    return target.lstrip("/") if target.startswith("/") else "xl/" + target


def rows(data, sheet=None):
    x = zipfile.ZipFile(io.BytesIO(data))
    ss = []
    if "xl/sharedStrings.xml" in x.namelist():
        ss = ["".join(t.text or "" for t in si.iter(NS + "t")) for si in ET.fromstring(x.read("xl/sharedStrings.xml")).iter(NS + "si")]
    col = lambda ref: sum((ord(c) - 64) * 26 ** i for i, c in enumerate(reversed(re.match(r"[A-Z]+", ref).group()))) - 1
    with x.open(sheet_path(x, sheet)) as f:
        for _, el in ET.iterparse(f):
            if el.tag == NS + "row":
                row = {}
                for c in el.iter(NS + "c"):
                    v, t = c.find(NS + "v"), c.get("t")
                    row[col(c.get("r"))] = ss[int(v.text)] if t == "s" and v is not None else "".join(y.text or "" for y in c.iter(NS + "t")) if t == "inlineStr" else (v.text if v is not None else None)
                yield row
                el.clear()
