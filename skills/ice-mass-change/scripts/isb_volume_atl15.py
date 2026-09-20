#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["numpy==2.2.6", "netCDF4==1.7.2"]
# ///
"""Loader for the altimetric volume term of the ice sheet mass balance
closure from ICESat-2 ATL15: the gridded land ice height change summed
to a volume anomaly per ice sheet and quarterly epoch, in km3, written
as the data root's volume-atl15.csv.

What it reads: the ATL15 Version 5 granules at 10 km (the bundle's
dataset concept: the reduced resolutions exist because their error
fields account for the per-track correlated errors, which a sum of
1 km cells would lack). Greenland is the GL region granule (the ice
sheet and the peripheral ice caps the region covers, undivided);
Antarctica is the four quadrant granules A1 to A4 summed per epoch,
grounded and floating ice together, since the product carries no
grounding mask. The delta_h group holds delta_h (m, relative to the
ATL14 surface at 2020-01-01), delta_h_sigma (m) and ice_area (m2,
time-varying where the ice front moves); time is days since
2018-01-01.

What it computes, per ice sheet and epoch:

  1. A fixed cell set: the cells finite in delta_h and with ice_area
     above zero at every epoch, so the volume series is never moved by
     coverage changes; each cell's area is the minimum ice_area over
     the epochs, the rule the product's own lagged rates apply to
     their differencing period.
  2. The volume anomaly in km3: the sum of delta_h times that area.
     It is a volume of surface height change, not ice: the firn air
     content change is removed and a density applied by the
     computation, never here (the bundle's gotcha).
  3. Two uncertainties, both in km3: delta_h_sigma times area in
     quadrature over the cells (a floor, since the errors correlate
     across cells), and the same summed linearly (the bound where they
     correlate fully); the CSV carries both, and the computation takes
     the quadrature value with the bound stated beside it.
  4. The calendar month of each epoch, from its time value. Epochs are
     the product's quarterly ones and the rows say so in their
     sampling column; nothing is interpolated to months.

Usage:
  isb_volume_atl15.py [--greenland ATL15_GL_..nc] [--antarctic ATL15_A1..nc ATL15_A2..nc ...]
      --out volume-atl15.csv [--stamp-out volume-atl15-stamp.json] [--fetch-to DIR]
  --fetch-to DIR   download a granule named but absent from the NSIDC cloud archive
                   into DIR; the archive needs an Earthdata Login bearer token, read
                   from EARTHDATA_TOKEN and sent as a header only
  --selftest       synthetic granules in the product's group layout with sums known by hand
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import os
import sys
import tempfile
import urllib.request
from pathlib import Path

import netCDF4 as nc
import numpy as np

ARCHIVE = "https://data.nsidc.earthdatacloud.nasa.gov/nsidc-cumulus-prod-protected/ATLAS/ATL15/005/2019/01/01/"
DOI = "10.5067/ATLAS/ATL15.005"
REGIONS = {"greenland": ("GL",), "antarctica": ("A1", "A2", "A3", "A4")}
CSV_COLUMNS = ["ice_sheet", "domain", "month", "value_km3", "uncertainty_km3",
               "uncertainty_correlated_km3", "area_km2", "n_cells", "sampling", "epoch_date", "product"]


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return "sha256:" + h.hexdigest()


def utcnow() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def fetch(url: str, dest: Path) -> None:
    """Stream a granule to dest; the bearer token in EARTHDATA_TOKEN, when
    set, goes in the Authorization header and nowhere else."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    print(f"fetching {url} -> {dest}", file=sys.stderr)
    headers = {}
    token = os.environ.get("EARTHDATA_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=300) as r, dest.open("wb") as f:
        for chunk in iter(lambda: r.read(1 << 20), b""):
            f.write(chunk)


def field(var, i: int) -> np.ndarray:
    return np.ma.filled(np.ma.masked_invalid(var[i]), np.nan).astype(float)


def epoch_labels(t):
    units, cal = t.units, getattr(t, "calendar", "standard")
    out = []
    for i in range(len(t)):
        d = nc.num2date(float(t[i]), units, cal)
        out.append((f"{d.year:04d}-{d.month:02d}", f"{d.year:04d}-{d.month:02d}-{d.day:02d}"))
    return out


def read_granule(path: Path) -> dict:
    """The per-epoch volume, its two uncertainties, the fixed cell set
    and the epoch labels of one granule."""
    ds = nc.Dataset(path)
    attrs = {a: str(getattr(ds, a)) for a in ds.ncattrs()}
    g = ds["delta_h"]
    dh, sig, ia, t = g["delta_h"], g["delta_h_sigma"], g["ice_area"], g["time"]
    x, y = np.asarray(g["x"][:], float), np.asarray(g["y"][:], float)
    n = len(t)
    labels = epoch_labels(t)
    ok = None
    area_min = None
    for i in range(n):
        a = field(ia, i)
        fin = np.isfinite(field(dh, i)) & np.isfinite(field(sig, i)) & np.isfinite(a) & (a > 0)
        ok = fin if ok is None else (ok & fin)
        area_min = a if area_min is None else np.fmin(area_min, a)
    area_km2 = np.where(ok, area_min, 0.0) / 1e6
    rows = []
    for i in range(n):
        d, s = field(dh, i)[ok], field(sig, i)[ok]
        w = area_km2[ok]
        vol = float(np.sum(d * w)) * 1e-3                       # m km2 -> km3
        quad = float(np.sqrt(np.sum((s * w) ** 2))) * 1e-3
        lin = float(np.sum(s * w)) * 1e-3
        rows.append((labels[i][0], labels[i][1], vol, quad, lin))
    dx = float(abs(x[1] - x[0])) if len(x) > 1 else 0.0
    info = {
        "granule": path.name, "granule_sha256": sha256(path), "source_url": ARCHIVE + path.name,
        "read_utc": utcnow(),
        "grid": f"{dx / 1000:.0f} km polar stereographic, {len(y)} by {len(x)} cells; "
                f"the cell area is the product's ice_area (m2), the ice-covered area of the cell",
        "cells": int(ok.sum()), "area_km2": round(float(area_km2.sum()), 2),
        "epochs": n, "months": [labels[0][0], labels[-1][0]],
        "time_coverage": [labels[0][1], labels[-1][1]],
        "global_attributes": {k: attrs[k] for k in sorted(attrs) if k in (
            "title", "short_name", "version", "identifier_product_doi", "time_coverage_start",
            "time_coverage_end", "date_created", "region", "resolution", "Conventions")},
    }
    ds.close()
    return {"rows": rows, "info": info}


def combine(parts: list[dict]) -> list:
    """Sum per epoch across granules whose epochs agree exactly."""
    labels = [r[0] for r in parts[0]["rows"]]
    for p in parts[1:]:
        if [r[0] for r in p["rows"]] != labels:
            sys.exit("the quadrant granules do not share one epoch list; nothing is summed")
    out = []
    for i, lab in enumerate(labels):
        vol = sum(p["rows"][i][2] for p in parts)
        quad = float(np.sqrt(sum(p["rows"][i][3] ** 2 for p in parts)))
        lin = sum(p["rows"][i][4] for p in parts)
        out.append((lab, parts[0]["rows"][i][1], vol, quad, lin))
    return out


def run(greenland: Path | None, antarctic: list[Path], out: Path, stamp_out: Path | None):
    if not (greenland or antarctic):
        sys.exit("nothing to read: give --greenland and/or --antarctic")
    rows, series = [], {}
    if greenland:
        g = read_granule(greenland)
        for lab, date, vol, quad, lin in g["rows"]:
            rows.append(["greenland", "gl", lab, vol, quad, lin, g["info"]["area_km2"], g["info"]["cells"],
                         "quarterly", date, "atl15"])
        series["greenland"] = {
            "product": "ICESat-2 ATL15 Gridded Antarctic and Arctic Land Ice Height Change, Version 5",
            "doi": DOI, "granules": [g["info"]],
            "variable": "delta_h/delta_h (with delta_h_sigma, ice_area, time)",
            "mask": "the product's ice_area above zero at every epoch: the Greenland ice sheet and the "
                    "peripheral ice caps the GL region covers, undivided; no grounding mask (Greenland's "
                    "floating tongues are in the sum)",
            "aggregation": "sum of delta_h times the cell's minimum ice_area over the epochs, over the "
                           "fixed set of cells finite in delta_h and delta_h_sigma and ice-covered at "
                           "every epoch; 1e-3 km3 per m km2",
            "reference": "anomaly against the ATL14 reference surface at 2020-01-01, the product's own",
            "sampling": "quarterly: one row per product epoch, labelled by the calendar month of its time value",
            "uncertainty_basis": "delta_h_sigma times area in quadrature over the cells (a floor where "
                                 "errors correlate across cells) and the same summed linearly (the bound "
                                 "where they correlate fully), both carried",
            "cells": {"gl": g["info"]["cells"]}, "area_km2": {"gl": g["info"]["area_km2"]},
            "months": g["info"]["months"], "n_steps": g["info"]["epochs"],
            "time_coverage": g["info"]["time_coverage"],
        }
    if antarctic:
        parts = [read_granule(p) for p in antarctic]
        summed = combine(parts)
        cells = sum(p["info"]["cells"] for p in parts)
        area = round(sum(p["info"]["area_km2"] for p in parts), 2)
        for lab, date, vol, quad, lin in summed:
            rows.append(["antarctica", "a1_a4", lab, vol, quad, lin, area, cells, "quarterly", date, "atl15"])
        series["antarctica"] = {
            "product": "ICESat-2 ATL15 Gridded Antarctic and Arctic Land Ice Height Change, Version 5",
            "doi": DOI, "granules": [p["info"] for p in parts],
            "variable": "delta_h/delta_h (with delta_h_sigma, ice_area, time)",
            "mask": "the product's ice_area above zero at every epoch in each quadrant granule, the four "
                    "quadrants summed per epoch; grounded and floating ice together, since the product "
                    "carries no grounding mask",
            "aggregation": "per quadrant, sum of delta_h times the cell's minimum ice_area over the "
                           "epochs, over the fixed set of cells finite in delta_h and delta_h_sigma and "
                           "ice-covered at every epoch; the quadrants summed, their quadrature errors "
                           "in quadrature and their linear bounds added",
            "reference": "anomaly against the ATL14 reference surface at 2020-01-01, the product's own",
            "sampling": "quarterly: one row per product epoch, labelled by the calendar month of its time value",
            "uncertainty_basis": "delta_h_sigma times area in quadrature over the cells (a floor where "
                                 "errors correlate across cells) and the same summed linearly (the bound "
                                 "where they correlate fully), both carried",
            "cells": {"a1_a4": cells}, "area_km2": {"a1_a4": area},
            "months": parts[0]["info"]["months"], "n_steps": parts[0]["info"]["epochs"],
            "time_coverage": parts[0]["info"]["time_coverage"],
        }
    rows.sort(key=lambda r: (r[0], r[1], r[2]))
    with out.open("w", encoding="utf-8", newline="") as f:
        wr = csv.writer(f)
        wr.writerow(CSV_COLUMNS)
        for r in rows:
            wr.writerow([r[0], r[1], r[2], f"{r[3]:.6f}", f"{r[4]:.6f}", f"{r[5]:.6f}", f"{r[6]:.2f}",
                         r[7], r[8], r[9], r[10]])
    first, last = min(r[2] for r in rows), max(r[2] for r in rows)
    stamp = {
        "term": "volume-atl15",
        "quantity": "land ice surface height change from ICESat-2 ATL15 summed to a volume anomaly "
                    "per ice sheet and quarterly epoch",
        "units": "value_km3, uncertainty_km3 and uncertainty_correlated_km3 in km3 of surface height "
                 "change (not ice); area_km2 in km2",
        "sign_convention": "positive is a higher surface (more volume), the product's own",
        "months": [first, last],
        "n_rows": len(rows),
        "domains": sorted({(r[0], r[1]) for r in rows}),
        "not_mass": "a volume of surface height change: the firn air content change is removed and "
                    "a density applied by the computation, never here (the bundle's gotcha "
                    "atl15-height-change-is-not-mass-change)",
        "series": series,
    }
    if stamp_out:
        stamp_out.write_text(json.dumps(stamp, indent=2) + "\n", encoding="utf-8")
    print(f"{out.name}: {len(rows)} rows, {first} to {last}, domains "
          + ", ".join(f"{a}/{b}" for a, b in stamp["domains"]))


def write_toy(p: Path, region: str, values, sigmas, areas):
    """A granule in the product's layout: a delta_h group with delta_h,
    delta_h_sigma, ice_area, time, x, y on a 2 by 2 grid of 10 km cells
    and len(values) epochs; values, sigmas and areas are per epoch lists
    of 2 by 2 arrays (areas in m2)."""
    ds = nc.Dataset(p, "w")
    ds.title = "toy ATL15"; ds.region = region; ds.short_name = "ATL15"; ds.version = "005"
    g = ds.createGroup("delta_h")
    g.createDimension("time", len(values)); g.createDimension("y", 2); g.createDimension("x", 2)
    t = g.createVariable("time", "f8", ("time",)); t.units = "days since 2018-01-01"; t.calendar = "standard"
    t[:] = [365.0 + 91.25 * i for i in range(len(values))]     # 2019-01-01, 2019-04-02, 2019-07-02 ...
    x = g.createVariable("x", "f8", ("x",)); y = g.createVariable("y", "f8", ("y",))
    x[:] = [0.0, 10000.0]; y[:] = [0.0, 10000.0]
    dh = g.createVariable("delta_h", "f4", ("time", "y", "x"), fill_value=3.4028235e38)
    sg = g.createVariable("delta_h_sigma", "f4", ("time", "y", "x"), fill_value=3.4028235e38)
    ia = g.createVariable("ice_area", "f4", ("time", "y", "x"), fill_value=3.4028235e38)
    for i in range(len(values)):
        dh[i] = np.where(np.isfinite(values[i]), values[i], 3.4028235e38)
        sg[i] = np.where(np.isfinite(sigmas[i]), sigmas[i], 3.4028235e38)
        ia[i] = areas[i]
    ds.close()


def selftest():
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        # Greenland: three epochs; cell (0,0) has 1e8 m2 of ice at every epoch,
        # cell (0,1) 1e8 then 0.5e8 (the front retreats: its area is the
        # minimum, 0.5e8), cell (1,0) is never ice, cell (1,1) is missing
        # at the second epoch, so the fixed set is two cells.
        nan = np.nan
        v = [np.array([[0.0, 0.0], [0.0, 0.0]]), np.array([[-1.0, 2.0], [0.5, nan]]),
             np.array([[-2.0, 4.0], [1.0, 1.0]])]
        s = [np.array([[0.1, 0.2], [0.3, 0.3]])] * 3
        a = [np.array([[1e8, 1e8], [0.0, 1e8]]), np.array([[1e8, 0.5e8], [0.0, 1e8]]),
             np.array([[1e8, 0.5e8], [0.0, 1e8]])]
        gl = td / "ATL15_GL_toy.nc"
        write_toy(gl, "GL", v, s, a)
        # Antarctica: two quadrants with one ice cell each at +1 and -1 m
        a1, a2 = td / "ATL15_A1_toy.nc", td / "ATL15_A2_toy.nc"
        zero = np.zeros((2, 2))
        write_toy(a1, "A1", [zero, np.array([[1.0, 0.0], [0.0, 0.0]])], [np.full((2, 2), 0.5)] * 2,
                  [np.array([[2e8, 0.0], [0.0, 0.0]])] * 2)
        write_toy(a2, "A2", [zero, np.array([[0.0, -1.0], [0.0, 0.0]])], [np.full((2, 2), 0.5)] * 2,
                  [np.array([[0.0, 4e8], [0.0, 0.0]])] * 2)
        out, st = td / "volume-atl15.csv", td / "volume-atl15-stamp.json"
        run(gl, [a1, a2], out, st)
        rows = list(csv.DictReader(out.open()))
        g = [r for r in rows if r["ice_sheet"] == "greenland"]
        an = [r for r in rows if r["ice_sheet"] == "antarctica"]
        assert [r["month"] for r in g] == ["2019-01", "2019-04", "2019-07"], g
        assert all(r["n_cells"] == "2" and r["sampling"] == "quarterly" for r in g), g
        # epoch 3: -2 m over 100 km2 plus 4 m over 50 km2 = 0 km3; epoch 2: -0.1 + 0.1 = 0;
        # quadrature error: sqrt((0.1*100)^2 + (0.2*50)^2) * 1e-3 = 0.014142 km3; linear 0.020
        got = [float(r["value_km3"]) for r in g]
        assert all(abs(x) < 1e-6 for x in got), got
        assert abs(float(g[1]["uncertainty_km3"]) - 0.0141421) < 1e-6, g[1]
        assert abs(float(g[1]["uncertainty_correlated_km3"]) - 0.02) < 1e-6, g[1]
        assert abs(float(g[0]["area_km2"]) - 150.0) < 1e-6, g[0]
        # Antarctica summed: epoch 2 is +1 m over 200 km2 and -1 m over 400 km2 = -0.2 km3,
        # quadrature sqrt((0.5*200)^2 + (0.5*400)^2) * 1e-3 = 0.223607, linear 0.3
        assert abs(float(an[1]["value_km3"]) + 0.2) < 1e-6 and an[1]["domain"] == "a1_a4", an[1]
        assert abs(float(an[1]["uncertainty_km3"]) - 0.2236068) < 1e-6, an[1]
        assert abs(float(an[1]["uncertainty_correlated_km3"]) - 0.3) < 1e-6, an[1]
        stamp = json.loads(st.read_text())
        assert stamp["series"]["greenland"]["cells"] == {"gl": 2} and len(stamp["series"]["antarctica"]["granules"]) == 2
        assert stamp["series"]["greenland"]["granules"][0]["granule_sha256"].startswith("sha256:")
        print(f"selftest: greenland volumes {got} km3 over two fixed cells (150 km2 at the minimum "
              f"ice area), quadrature 0.014142 and linear 0.020 km3; antarctic quadrants summed "
              f"to {float(an[1]['value_km3']):+.3f} km3; OK")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--greenland", type=Path)
    ap.add_argument("--antarctic", type=Path, nargs="*", default=[])
    ap.add_argument("--out", type=Path); ap.add_argument("--stamp-out", type=Path)
    ap.add_argument("--fetch-to", type=Path)
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        selftest(); return
    if not a.out:
        ap.error("--out is required")
    paths = ([a.greenland] if a.greenland else []) + list(a.antarctic)
    resolved = []
    for p in paths:
        if not p.is_file():
            if not a.fetch_to:
                ap.error(f"{p} does not exist; give --fetch-to DIR to download it")
            p = a.fetch_to / p.name
            if not p.is_file():
                fetch(ARCHIVE + p.name, p)
        resolved.append(p)
    greenland = resolved[0] if a.greenland else None
    antarctic = resolved[1:] if a.greenland else resolved
    run(greenland, antarctic, a.out, a.stamp_out)


if __name__ == "__main__":
    main()
