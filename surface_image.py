"""A surface draped on the maps: the cells of a grid (heat.py's 60 m land surface temperature) as one Web Mercator image, coloured on a fixed diverging scale
around Puerto Rico's median, with its corners and scale for the pages (docs/heat.md, "The surface on the map"; navigation plan follow-up, HANDOFF decision 88).

    mercator_png(values, X, Y, epsg, res, ...) -> (png bytes, meta)

The image is an indexed PNG written with zlib alone (no imaging library): index 0 is transparent (water, no value, outside the area), indices 1..N are the colour
steps of the scale. One pixel is about one grid cell, so nothing is invented between cells. The 2D map lays it with L.imageOverlay and the 3D view with a
MapLibre image source; both stretch an image linearly between its corners in Web Mercator, which is how it is resampled here. The width stays under 4,096
pixels, the largest texture every phone's WebGL can hold.
"""
import math
import struct
import zlib

import numpy as np

import raster

STEPS = 64                                          # colour steps: a smooth ramp in one byte per pixel
STOPS = ["#205D7B", "#8FCAE8", "#F2F2F2", "#FF8270", "#B82415"]   # core/palettes.js DIVERGING, cool to hot: blue below the median, grey at it, red above
MAX_PX = 4096


def _rgb(h):
    return tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))


def ramp(steps=STEPS, stops=STOPS):
    """[(r, g, b)] of `steps` colours from the first stop to the last, linear in sRGB between the stops."""
    cs = [_rgb(s) for s in stops]
    out = []
    for k in range(steps):
        t = k / (steps - 1) * (len(cs) - 1)
        i = min(int(t), len(cs) - 2); f = t - i
        out.append(tuple(round(cs[i][j] + (cs[i + 1][j] - cs[i][j]) * f) for j in range(3)))
    return out


def png_indexed(idx, palette):
    """An 8-bit indexed PNG of the 2D array idx (0 = transparent), deterministic (zlib level 9)."""
    h, w = idx.shape
    raw = b"".join(b"\x00" + idx[r].astype(np.uint8).tobytes() for r in range(h))   # filter 0 on every row
    chunk = lambda t, d: struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
    plte = bytes([0, 0, 0]) + b"".join(bytes(c) for c in palette)
    trns = bytes([0])                                                                 # index 0 transparent, the rest opaque
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 3, 0, 0, 0)) + chunk(b"PLTE", plte) + chunk(b"tRNS", trns)
            + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))


def mercator_png(values, X, Y, epsg, res, centre, half, min_lon=None, pad_deg=0.01):
    """values at the cell centres X, Y (EPSG `epsg`, a square grid of `res` m) as a Web Mercator image of about one cell per pixel.
    centre: the value drawn grey (Puerto Rico's median); half: the distance from it to each end of the scale (values beyond are drawn at the ends).
    min_lon: leave out the cells west of it (Mona, Monito and Desecheo, which would widen the image past MAX_PX with open sea)."""
    values = np.asarray(values, float); X = np.asarray(X, float); Y = np.asarray(Y, float)
    lon, lat = raster.transform_points(X, Y, epsg, 4326)
    keep = np.isfinite(values) & (lon >= min_lon if min_lon is not None else True)
    w, e = float(lon[keep].min()) - pad_deg, float(lon[keep].max()) + pad_deg
    s, n = float(lat[keep].min()) - pad_deg, float(lat[keep].max()) + pad_deg
    (mx0, mx1), (my0, my1) = raster.transform_points([w, e], [s, n], 4326, 3857)
    px = res / math.cos(math.radians((s + n) / 2))                                    # one cell, in Web Mercator metres at the middle latitude
    W, H = int(math.ceil((mx1 - mx0) / px)), int(math.ceil((my1 - my0) / px))
    if W > MAX_PX:
        px = (mx1 - mx0) / MAX_PX; W, H = MAX_PX, int(math.ceil((my1 - my0) / px))
    # the grid as a full array, by the cells' own column and row
    c = np.rint((X - X.min()) / res).astype(np.int64); r = np.rint((Y.max() - Y) / res).astype(np.int64)
    full = np.full((int(r.max()) + 1, int(c.max()) + 1), np.nan, dtype=np.float32)
    full[r[keep], c[keep]] = values[keep]
    # each pixel centre, back into the grid; the cell under it gives its value (nearest: nothing is invented between cells)
    cols, rows = np.meshgrid(np.arange(W), np.arange(H))
    gx, gy = raster.transform_points(mx0 + (cols.ravel() + 0.5) * px, my1 - (rows.ravel() + 0.5) * px, 3857, epsg)
    ci = np.floor((gx - (X.min() - res / 2)) / res).astype(np.int64); ri = np.floor(((Y.max() + res / 2) - gy) / res).astype(np.int64)
    ok = (ci >= 0) & (ci < full.shape[1]) & (ri >= 0) & (ri < full.shape[0])
    v = np.full(ci.shape, np.nan, dtype=np.float32); v[ok] = full[ri[ok], ci[ok]]
    t = np.clip((v - (centre - half)) / (2 * half), 0, 1)
    idx = np.where(np.isfinite(v), 1 + np.rint(t * (STEPS - 1)), 0).astype(np.uint8).reshape(H, W)
    (cw, ce), (cs, cn) = raster.transform_points([mx0, mx0 + W * px], [my1 - H * px, my1], 3857, 4326)   # the corners of the whole pixels, not the padded box
    meta = {"bounds": [round(cw, 6), round(cs, 6), round(ce, 6), round(cn, 6)], "size": [W, H], "pixel_m": round(px * math.cos(math.radians((s + n) / 2)), 1),
            "scale": {"low": round(centre - half, 1), "centre": round(centre, 1), "high": round(centre + half, 1), "steps": STEPS, "stops": STOPS},
            "cells_drawn": int(np.isfinite(v).sum()), "left_out_west_of": min_lon}
    return png_indexed(idx, ramp()), meta
