"""All 78 Puerto Rico municipalities with center coordinates, region, and search radius.

`region` is the Puerto Rico Tourism Company's own tourism region, per
https://tourism.pr.gov/regions/ — Porta Capital, Porta Atlántico, Porta del Mar,
Porta Caribe, Porta Cordillera, Porta del Sol Norte and Porta del Sol Sur. Using the
PRTC's scheme means VIEWPR's regional figures line up with official tourism reporting
and with the PRTC room inventory.

The entries below stay grouped by compass area because that is how the coordinates are
maintained; those grouping comments are not the region. The two cross-cut — Porta
Capital and Porta del Mar both draw from what the comments call Metro and East.
"""

MUNICIPALITIES = [
    # Metro Region
    {"name": "Bayamón",       "lat": 18.3987, "lng": -66.1638, "region": "Porta Capital",     "radius": 12000},
    {"name": "Carolina",      "lat": 18.3860, "lng": -65.9571, "region": "Porta Capital",     "radius": 11000},
    {"name": "Cataño",        "lat": 18.4337, "lng": -66.1632, "region": "Porta Capital",     "radius": 5000},
    {"name": "Guaynabo",      "lat": 18.3697, "lng": -66.1053, "region": "Porta Capital",     "radius": 9000},
    {"name": "Loíza",         "lat": 18.4317, "lng": -65.8778, "region": "Porta del Mar",     "radius": 8000},
    {"name": "San Juan",      "lat": 18.4655, "lng": -66.1057, "region": "Porta Capital",     "radius": 11000},
    {"name": "Toa Alta",      "lat": 18.3885, "lng": -66.2488, "region": "Porta Atlántico",     "radius": 9000},
    {"name": "Toa Baja",      "lat": 18.4436, "lng": -66.2546, "region": "Porta Atlántico",     "radius": 9000},
    {"name": "Trujillo Alto", "lat": 18.3627, "lng": -66.0169, "region": "Porta Capital",     "radius": 8000},
    # North Coast
    {"name": "Arecibo",       "lat": 18.4724, "lng": -66.7216, "region": "Porta Atlántico",     "radius": 14000},
    {"name": "Barceloneta",   "lat": 18.4487, "lng": -66.5388, "region": "Porta Atlántico",     "radius": 7000},
    {"name": "Camuy",         "lat": 18.4837, "lng": -66.8445, "region": "Porta Atlántico",     "radius": 9000},
    {"name": "Corozal",       "lat": 18.3413, "lng": -66.3169, "region": "Porta Cordillera",     "radius": 9000},
    {"name": "Dorado",        "lat": 18.4579, "lng": -66.2685, "region": "Porta Atlántico",     "radius": 8000},
    {"name": "Florida",       "lat": 18.3625, "lng": -66.5604, "region": "Porta Atlántico",     "radius": 6000},
    {"name": "Hatillo",       "lat": 18.4866, "lng": -66.8250, "region": "Porta Atlántico",     "radius": 9000},
    {"name": "Manatí",        "lat": 18.4284, "lng": -66.4834, "region": "Porta Atlántico",     "radius": 9000},
    {"name": "Morovis",       "lat": 18.3258, "lng": -66.4070, "region": "Porta Cordillera",     "radius": 8000},
    {"name": "Naranjito",     "lat": 18.3006, "lng": -66.2438, "region": "Porta Cordillera",     "radius": 7000},
    {"name": "Vega Alta",     "lat": 18.4120, "lng": -66.3231, "region": "Porta Atlántico",     "radius": 8000},
    {"name": "Vega Baja",     "lat": 18.4456, "lng": -66.3867, "region": "Porta Atlántico",     "radius": 9000},
    # Northeast
    {"name": "Canóvanas",     "lat": 18.3775, "lng": -65.9004, "region": "Porta del Mar", "radius": 9000},
    {"name": "Ceiba",         "lat": 18.2649, "lng": -65.6487, "region": "Porta del Mar", "radius": 8000},
    {"name": "Culebra",       "lat": 18.3020, "lng": -65.3028, "region": "Porta del Mar", "radius": 7000},
    {"name": "Fajardo",       "lat": 18.3249, "lng": -65.6534, "region": "Porta del Mar", "radius": 10000},
    {"name": "Luquillo",      "lat": 18.3721, "lng": -65.7137, "region": "Porta del Mar", "radius": 8000},
    {"name": "Naguabo",       "lat": 18.2115, "lng": -65.7303, "region": "Porta del Mar", "radius": 9000},
    {"name": "Río Grande",    "lat": 18.3792, "lng": -65.8326, "region": "Porta del Mar", "radius": 10000},
    {"name": "Vieques",       "lat": 18.1286, "lng": -65.4401, "region": "Porta del Mar", "radius": 12000},
    # East
    {"name": "Aguas Buenas",  "lat": 18.2568, "lng": -66.1021, "region": "Porta Capital",      "radius": 8000},
    {"name": "Caguas",        "lat": 18.2341, "lng": -66.0355, "region": "Porta Capital",      "radius": 11000},
    {"name": "Cidra",         "lat": 18.1759, "lng": -66.1601, "region": "Porta Cordillera",      "radius": 8000},
    {"name": "Gurabo",        "lat": 18.2536, "lng": -65.9755, "region": "Porta Capital",      "radius": 8000},
    {"name": "Humacao",       "lat": 18.1494, "lng": -65.8275, "region": "Porta del Mar",      "radius": 10000},
    {"name": "Juncos",        "lat": 18.2274, "lng": -65.9196, "region": "Porta del Mar",      "radius": 8000},
    {"name": "Las Piedras",   "lat": 18.1851, "lng": -65.8679, "region": "Porta del Mar",      "radius": 8000},
    {"name": "San Lorenzo",   "lat": 18.1880, "lng": -65.9648, "region": "Porta del Mar",      "radius": 9000},
    # Southeast
    {"name": "Arroyo",        "lat": 17.9660, "lng": -66.0607, "region": "Porta Caribe", "radius": 7000},
    {"name": "Guayama",       "lat": 17.9842, "lng": -66.1137, "region": "Porta Caribe", "radius": 9000},
    {"name": "Maunabo",       "lat": 18.0074, "lng": -65.9002, "region": "Porta del Mar", "radius": 7000},
    {"name": "Patillas",      "lat": 18.0016, "lng": -66.0134, "region": "Porta Caribe", "radius": 8000},
    {"name": "Salinas",       "lat": 17.9766, "lng": -66.2978, "region": "Porta Caribe", "radius": 9000},
    {"name": "Yabucoa",       "lat": 18.0506, "lng": -65.8794, "region": "Porta del Mar", "radius": 8000},
    # South
    {"name": "Coamo",         "lat": 18.0762, "lng": -66.3591, "region": "Porta Caribe",     "radius": 10000},
    {"name": "Juana Díaz",    "lat": 18.0530, "lng": -66.5058, "region": "Porta Caribe",     "radius": 9000},
    {"name": "Peñuelas",      "lat": 18.0630, "lng": -66.7242, "region": "Porta Caribe",     "radius": 8000},
    {"name": "Ponce",         "lat": 18.0110, "lng": -66.6141, "region": "Porta Caribe",     "radius": 13000},
    {"name": "Santa Isabel",  "lat": 17.9662, "lng": -66.4070, "region": "Porta Caribe",     "radius": 8000},
    {"name": "Villalba",      "lat": 18.1256, "lng": -66.4897, "region": "Porta Caribe",     "radius": 9000},
    # Southwest
    {"name": "Cabo Rojo",     "lat": 18.0864, "lng": -67.1495, "region": "Porta del Sol Sur", "radius": 11000},
    {"name": "Guánica",       "lat": 17.9726, "lng": -66.9082, "region": "Porta del Sol Sur", "radius": 8000},
    {"name": "Guayanilla",    "lat": 17.9918, "lng": -66.7914, "region": "Porta Caribe", "radius": 8000},
    {"name": "Hormigueros",   "lat": 18.1395, "lng": -67.1299, "region": "Porta del Sol Sur", "radius": 6000},
    {"name": "Lajas",         "lat": 18.0509, "lng": -67.0602, "region": "Porta del Sol Sur", "radius": 9000},
    {"name": "Sabana Grande", "lat": 18.0789, "lng": -66.9577, "region": "Porta del Sol Sur", "radius": 7000},
    {"name": "San Germán",    "lat": 18.0818, "lng": -67.0413, "region": "Porta del Sol Sur", "radius": 9000},
    {"name": "Yauco",         "lat": 18.0349, "lng": -66.8503, "region": "Porta del Sol Sur", "radius": 10000},
    # West
    {"name": "Aguada",        "lat": 18.3799, "lng": -67.1863, "region": "Porta del Sol Norte",      "radius": 8000},
    {"name": "Aguadilla",     "lat": 18.4275, "lng": -67.1541, "region": "Porta del Sol Norte",      "radius": 11000},
    {"name": "Añasco",        "lat": 18.2822, "lng": -67.1432, "region": "Porta del Sol Norte",      "radius": 9000},
    {"name": "Las Marías",    "lat": 18.2515, "lng": -66.9910, "region": "Porta del Sol Norte",      "radius": 8000},
    {"name": "Mayagüez",      "lat": 18.2013, "lng": -67.1397, "region": "Porta del Sol Sur",      "radius": 12000},
    {"name": "Moca",          "lat": 18.3935, "lng": -67.1141, "region": "Porta del Sol Norte",      "radius": 8000},
    {"name": "Rincón",        "lat": 18.3405, "lng": -67.2497, "region": "Porta del Sol Norte",      "radius": 8000},
    {"name": "San Sebastián", "lat": 18.3363, "lng": -66.9921, "region": "Porta del Sol Norte",      "radius": 9000},
    # Northwest
    {"name": "Isabela",       "lat": 18.5009, "lng": -67.0227, "region": "Porta del Sol Norte", "radius": 10000},
    {"name": "Quebradillas",  "lat": 18.4745, "lng": -66.9385, "region": "Porta del Sol Norte", "radius": 7000},
    # Central / Mountain
    {"name": "Adjuntas",      "lat": 18.1632, "lng": -66.7229, "region": "Porta Cordillera",   "radius": 12000},
    {"name": "Aibonito",      "lat": 18.1410, "lng": -66.2658, "region": "Porta Cordillera",   "radius": 8000},
    {"name": "Barranquitas",  "lat": 18.1864, "lng": -66.3069, "region": "Porta Cordillera",   "radius": 8000},
    {"name": "Cayey",         "lat": 18.1133, "lng": -66.1652, "region": "Porta Capital",   "radius": 9000},
    {"name": "Ciales",        "lat": 18.3367, "lng": -66.4688, "region": "Porta Cordillera",   "radius": 9000},
    {"name": "Comerío",       "lat": 18.2194, "lng": -66.2270, "region": "Porta Cordillera",   "radius": 7000},
    {"name": "Jayuya",        "lat": 18.2198, "lng": -66.5946, "region": "Porta Cordillera",   "radius": 9000},
    {"name": "Lares",         "lat": 18.2947, "lng": -66.8777, "region": "Porta del Sol Norte",   "radius": 10000},
    {"name": "Maricao",       "lat": 18.1815, "lng": -66.9820, "region": "Porta del Sol Sur",   "radius": 9000},
    {"name": "Orocovis",      "lat": 18.2275, "lng": -66.3939, "region": "Porta Cordillera",   "radius": 10000},
    {"name": "Utuado",        "lat": 18.2672, "lng": -66.6997, "region": "Porta Cordillera",   "radius": 12000},
]

def sort_key(name: str) -> str:
    """Accent-insensitive key so Añasco, Bayamón, Cataño and Mayagüez land where a reader
    expects them rather than after Z."""
    import unicodedata
    return "".join(
        c for c in unicodedata.normalize("NFD", name or "") if unicodedata.category(c) != "Mn"
    ).lower()


# The list above is grouped by region because that is how it is maintained; everything that
# displays municipalities wants them alphabetical.
MUNICIPALITIES_ALPHA = sorted(MUNICIPALITIES, key=lambda m: sort_key(m["name"]))
MUNICIPALITY_NAMES = [m["name"] for m in MUNICIPALITIES_ALPHA]
REGIONS = sorted(set(m["region"] for m in MUNICIPALITIES))

# ── CIH baseline ─────────────────────────────────────────────────────────────
# A reporting group, not a region: these 15 municipalities span Northeast, East,
# Southeast and Metro, so they cannot be selected by region.
CIH_MUNICIPALITIES = [
    "Canóvanas", "Ceiba", "Culebra", "Fajardo", "Humacao", "Juncos", "Las Piedras",
    "Loíza", "Luquillo", "Maunabo", "Naguabo", "Río Grande", "San Lorenzo",
    "Vieques", "Yabucoa",
]
CIH_MUNICIPALITIES.sort(key=sort_key)

# Named municipality groups, so a reporting scope can be passed as one query parameter
# wherever a single municipality can. Keyed by the value used in URLs.
ASSET_GROUPS = {"cih": CIH_MUNICIPALITIES}
GROUP_LABELS = {"cih": "CIH Baseline"}

_known = {m["name"] for m in MUNICIPALITIES}
_missing = [n for n in CIH_MUNICIPALITIES if n not in _known]
if _missing:
    raise RuntimeError(f"CIH_MUNICIPALITIES names not in MUNICIPALITIES: {_missing}")


def get_municipality(name: str) -> dict | None:
    for m in MUNICIPALITIES:
        if m["name"].lower() == name.lower():
            return m
    return None
