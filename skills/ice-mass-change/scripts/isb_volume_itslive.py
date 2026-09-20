#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["numpy==2.2.6", "netCDF4==1.7.2", "pyproj==3.7.1"]
# ///
"""Loader for the altimetric volume term of the ice sheet mass balance
closure from the ITS_LIVE elevation change products: the multi-mission
surface elevation change summed to a volume anomaly per ice sheet
domain and time step, in km3, written as the data root's
volume-itslive.csv. It is the altimetry term the closure reads when
the ATL15 granules cannot be fetched, and it shares its grid, mask and
cell set with the firn term, since the Greenland file is the one the
firn loader reads.

What ITS_LIVE distributes, and what this loader therefore reads:

  Greenland   height_change/Greenland/Greenland_G1920V01_IceSheetGlacierIceHeight.nc
              (version 1.1, doi 10.5067/ICFVI7DKHZJV): dh is the surface
              elevation change against 2014-01-01, monthly from 1992-01
              to 2023-12 on the 1920 m EPSG:3413 grid, beside rms, the
              root-square-sum of the systematic and random error; the
              mask separates the ice sheet (1) from the peripheral
              glaciers (2). The same file carries the GEMB and GSFC
              firn air content anomalies the firn loader reads.
  Antarctica  height_change/Antarctica/Grounded/ANT_G1920V01_GroundedIceHeight.nc
              (version 1.0, doi 10.5067/L3LSVDZS15ZV): dh against
              2013-12-16, monthly from 1985 on the 1920 m EPSG:3031
              grid, beside rmse (the paper's sigma_m), quality_flag
              (0 no data, 1 high quality, 2 low quality, 3 pole hole)
              and the basin identifiers. Grounded ice only.

What it computes, per domain and time step:

  1. The true ground area of every grid cell from the projection's
     areal scale (pyproj get_factors), as the firn loader does.
  2. A fixed cell set per domain: the cells inside the mask that carry
     a finite dh at every time step (Antarctica: and a quality flag
     other than no-data at every step), so the volume series is never
     moved by coverage changes; the stamp counts the pole hole cells.
  3. The volume anomaly in km3: the sum of dh times cell area over
     that set. It is a volume of surface height change, not ice: the
     firn air content change is removed and a density applied by the
     computation, never here (the bundle's gotcha).
  4. Two uncertainties, both in km3: the error field times area in
     quadrature over the cells (a floor, since the errors correlate
     across cells) and the same summed linearly (the bound where they
     correlate fully), over the cells where the error is finite at
     that step; the CSV carries both and the stamp counts the cells
     without an error.
  5. The calendar month of each time value; a step with no finite
     value inside the mask is skipped and listed, never filled; a
     second step in a month already taken is refused, never averaged.
     The Antarctic record starts in 1985 with sparse coverage, and a
     cell set fixed over every step since then keeps a quarter of the
     sheet; --antarctic-from YYYY-MM fixes the set over the steps from
     that month on and writes rows from it, and the stamp says so.

Usage:
  isb_volume_itslive.py [--greenland FILE.nc] [--antarctic FILE.nc [--antarctic-from YYYY-MM]]
      --out volume-itslive.csv [--stamp-out volume-itslive-stamp.json] [--fetch-to DIR]
  --fetch-to DIR   download the product file from its ITS_LIVE bucket URL into DIR
                   when the given path does not exist (the bucket is public)
  --selftest       synthetic grids in both layouts with sums known by hand
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import re
import sys
import tempfile
import urllib.request
from pathlib import Path

import netCDF4 as nc
import numpy as np
from pyproj import CRS, Proj, Transformer

BUCKET = "https://its-live-data.s3.amazonaws.com/"
PRODUCTS = {
    "greenland": {
        "key": "height_change/Greenland/Greenland_G1920V01_IceSheetGlacierIceHeight.nc",
        "doi": "10.5067/ICFVI7DKHZJV", "epsg": 3413,
        "domains": {"ice_sheet": 1, "peripheral_glaciers": 2},
    },
    "antarctica": {
        "key": "height_change/Antarctica/Grounded/ANT_G1920V01_GroundedIceHeight.nc",
        "doi": "10.5067/L3LSVDZS15ZV", "epsg": 3031,
        "domains": {"grounded": None},
    },
}
CSV_COLUMNS = ["ice_sheet", "domain", "month", "value_km3", "uncertainty_km3",
               "uncertainty_correlated_km3", "area_km2", "n_cells", "sampling", "epoch_date", "product"]


def bare_doi(text: str) -> str:
    s = text.strip()
    for prefix in ("https://doi.org/", "http://doi.org/", "https://dx.doi.org/", "doi.org/", "doi:"):
        if s.lower().startswith(prefix):
            return s[len(prefix):]
    return s


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return "sha256:" + h.hexdigest()


def utcnow() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def fetch(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    print(f"fetching {url} -> {dest}", file=sys.stderr)
    with urllib.request.urlopen(url, timeout=120) as r, dest.open("wb") as f:
        for chunk in iter(lambda: r.read(1 << 20), b""):
            f.write(chunk)


def cell_area_km2(epsg: int, x: np.ndarray, y: np.ndarray) -> np.ndarray:
    crs = CRS.from_epsg(epsg)
    dx = float(abs(x[1] - x[0])) if len(x) > 1 else 0.0
    dy = float(abs(y[1] - y[0])) if len(y) > 1 else 0.0
    if dx == 0.0 or dy == 0.0:
        sys.exit("a grid axis has fewer than two nodes; no cell size can be derived")
    X, Y = np.meshgrid(np.asarray(x, float), np.asarray(y, float))
    lon, lat = Transformer.from_crs(crs, 4326, always_xy=True).transform(X, Y)
    f = Proj(crs).get_factors(lon, lat)
    return (dx * dy / 1e6) / np.asarray(f.areal_scale, float)


def field(var, i: int) -> np.ndarray:
    return np.ma.filled(np.ma.masked_invalid(var[i]), np.nan).astype(float)


def month_of(t, i: int) -> str:
    d = nc.num2date(float(t[i]), t.units, getattr(t, "calendar", "standard"))
    return f"{d.year:04d}-{d.month:02d}"


def date_of(t, i: int) -> str:
    d = nc.num2date(float(t[i]), t.units, getattr(t, "calendar", "standard"))
    return f"{d.year:04d}-{d.month:02d}-{d.day:02d}"


def nonempty_steps(var, n: int, inside: np.ndarray) -> list[int]:
    return [i for i in range(n) if np.isfinite(field(var, i)[inside]).any()]


def fixed_cell_set(var, steps, inside: np.ndarray, flag=None) -> np.ndarray:
    ok = inside.copy()
    for i in steps:
        ok &= np.isfinite(field(var, i))
        if flag is not None:
            ok &= np.asarray(flag[i]).astype(int) != 0
    return ok


def sums(dh: np.ndarray, err: np.ndarray, area: np.ndarray, ok: np.ndarray):
    """Volume (km3), quadrature and linear error (km3), cells without an error."""
    w = area[ok]
    vol = float(np.sum(dh[ok] * w)) * 1e-3
    e = err[ok]
    fin = np.isfinite(e)
    quad = float(np.sqrt(np.sum((e[fin] * w[fin]) ** 2))) * 1e-3
    lin = float(np.sum(e[fin] * w[fin])) * 1e-3
    return vol, quad, lin, int((~fin).sum())


def read_greenland(path: Path, rows: list, stamp: dict) -> None:
    ds = nc.Dataset(path)
    attrs = {a: str(getattr(ds, a)) for a in ds.ncattrs()}
    epsg = int(float(attrs.get("epsg_number", PRODUCTS["greenland"]["epsg"])))
    if epsg != PRODUCTS["greenland"]["epsg"]:
        sys.exit(f"{path.name}: epsg_number {epsg} is not the expected {PRODUCTS['greenland']['epsg']}")
    x, y, t = ds["x"][:], ds["y"][:], ds["time"]
    n = len(t)
    area = cell_area_km2(epsg, x, y)
    mask = np.asarray(ds["mask"][:]).astype(int)
    dh, rms = ds["dh"], ds["rms"]
    iced = (mask == 1) | (mask == 2)
    steps = nonempty_steps(dh, n, iced)
    empty = [date_of(t, i) for i in range(n) if i not in steps]
    domains = {name: fixed_cell_set(dh, steps, mask == code)
               for name, code in PRODUCTS["greenland"]["domains"].items()}
    for name, ok in domains.items():
        print(f"  greenland {name}: {int(ok.sum())} cells, {float(area[ok].sum()):.0f} km2", file=sys.stderr)
    months, no_error = {}, {name: 0 for name in domains}
    for i in steps:
        label = month_of(t, i)
        if label in months:
            sys.exit(f"{path.name}: two time steps ({months[label]} and {i}) fall in {label}; "
                     "the loader does not average steps")
        months[label] = i
        d, e = field(dh, i), field(rms, i)
        for name, ok in domains.items():
            vol, quad, lin, missing = sums(d, e, area, ok)
            no_error[name] = max(no_error[name], missing)
            rows.append(["greenland", name, label, vol, quad, lin, float(area[ok].sum()), int(ok.sum()),
                         "monthly", date_of(t, i), "itslive"])
    labels = sorted(months)
    stamp["greenland"] = {
        "product": attrs.get("title", ""),
        "doi": bare_doi(attrs.get("doi", "")),
        "product_version": attrs.get("version", ""),
        "granule": path.name,
        "granule_sha256": sha256(path),
        "source_url": BUCKET + PRODUCTS["greenland"]["key"],
        "read_utc": utcnow(),
        "variable": "dh (with rms)",
        "variable_comment": str(getattr(dh, "comment", "")),
        "error_comment": str(getattr(rms, "comment", "")),
        "grid": f"1920 m polar stereographic, EPSG:{epsg}, {len(y)} by {len(x)} cells; "
                "cell areas from the projection's areal scale",
        "mask": "the file's mask variable: 1 ice sheet, 2 peripheral glacier, 0 non-ice; the ice "
                "sheet domain is the grounded ice sheet, the product being a grounded ice "
                "elevation change product",
        "aggregation": "sum of dh times cell area over the fixed set of cells inside the mask that are "
                       "finite in dh at every time step; 1e-3 km3 per m km2; the rms error times area "
                       "in quadrature and linearly over the cells of that set where rms is finite at "
                       "the step",
        "reference": "anomaly against 2014-01-01, the product's own reference",
        "sampling": "monthly",
        "time_coverage": [date_of(t, steps[0]), date_of(t, steps[-1])],
        "months": [labels[0], labels[-1]],
        "n_steps": len(steps),
        "empty_steps_skipped": empty,
        "cells": {name: int(ok.sum()) for name, ok in domains.items()},
        "area_km2": {name: round(float(area[ok].sum()), 2) for name, ok in domains.items()},
        "cells_without_error_max": no_error,
        "uncertainty_basis": "the product's rms (the root-square-sum of the systematic and random "
                             "error, its comment) times cell area, in quadrature over the cells (a "
                             "floor where errors correlate across cells) and summed linearly (the "
                             "bound where they correlate fully), both carried",
        "global_attributes": attrs,
    }
    ds.close()


def read_antarctica(path: Path, rows: list, stamp: dict, start_month: str | None = None) -> None:
    ds = nc.Dataset(path)
    attrs = {a: str(getattr(ds, a)) for a in ds.ncattrs()}
    mapping = ds["mapping"] if "mapping" in ds.variables else None
    epsg = int(float(getattr(mapping, "spatial_epsg", PRODUCTS["antarctica"]["epsg"]))) if mapping is not None \
        else PRODUCTS["antarctica"]["epsg"]
    if epsg != PRODUCTS["antarctica"]["epsg"]:
        sys.exit(f"{path.name}: spatial_epsg {epsg} is not the expected {PRODUCTS['antarctica']['epsg']}")
    x, y, t = ds["x"][:], ds["y"][:], ds["time"]
    n = len(t)
    area = cell_area_km2(epsg, x, y)
    dh, err, flag = ds["dh"], ds["rmse"], ds["quality_flag"]
    basin = np.asarray(ds["basin"][:]).astype(int) if "basin" in ds.variables else None
    everywhere = np.ones(dh.shape[1:], bool)
    candidates = [i for i in range(n) if start_month is None or month_of(t, i) >= start_month]
    before_start = [date_of(t, i) for i in range(n) if i not in candidates]
    steps = [i for i in nonempty_steps(dh, n, everywhere) if i in set(candidates)]
    empty = [date_of(t, i) for i in candidates if i not in steps]
    ok = fixed_cell_set(dh, steps, everywhere, flag)
    flags_last = np.asarray(flag[steps[-1]]).astype(int)
    pole = int(((flags_last == 3) & ok).sum())
    print(f"  antarctica grounded: {int(ok.sum())} cells, {float(area[ok].sum()):.0f} km2, "
          f"{pole} pole hole cells, {len(empty)} empty steps skipped", file=sys.stderr)
    months, no_error = {}, 0
    for i in steps:
        label = month_of(t, i)
        if label in months:
            sys.exit(f"{path.name}: two time steps ({months[label]} and {i}) fall in {label}; "
                     "the loader does not average steps")
        months[label] = i
        vol, quad, lin, missing = sums(field(dh, i), field(err, i), area, ok)
        no_error = max(no_error, missing)
        rows.append(["antarctica", "grounded", label, vol, quad, lin, float(area[ok].sum()), int(ok.sum()),
                     "monthly", date_of(t, i), "itslive"])
    labels = sorted(months)
    stamp["antarctica"] = {
        "product": attrs.get("title", ""),
        "doi": bare_doi(attrs.get("doi", PRODUCTS["antarctica"]["doi"])),
        "product_version": attrs.get("version", ""),
        "granule": path.name,
        "granule_sha256": sha256(path),
        "source_url": BUCKET + PRODUCTS["antarctica"]["key"],
        "read_utc": utcnow(),
        "variable": "dh (with rmse and quality_flag)",
        "variable_comment": str(getattr(dh, "standard_name", "")),
        "error_comment": str(getattr(err, "description", "")),
        "grid": f"1920 m polar stereographic, EPSG:{epsg}, {len(y)} by {len(x)} cells; "
                "cell areas from the projection's areal scale",
        "mask": "every cell finite in dh and with a quality flag other than no-data at every time "
                "step: the grounded ice sheet, the product being a grounded ice elevation change "
                "product; the pole hole cells (flag 3) are in the set and counted",
        "aggregation": "sum of dh times cell area over the fixed set of cells finite in dh and flagged "
                       "at every time step; 1e-3 km3 per m km2; the rmse times area in quadrature and "
                       "linearly over the cells of that set where rmse is finite at the step",
        "reference": "anomaly against 2013-12-16, the product's own reference (the dh standard name)",
        "sampling": "monthly",
        "time_coverage": [date_of(t, steps[0]), date_of(t, steps[-1])],
        "months": [labels[0], labels[-1]],
        "n_steps": len(steps),
        "empty_steps_skipped": empty,
        "start_month": start_month,
        "steps_before_start_month": len(before_start),
        "cell_set_rule": ("cells finite in dh and flagged at every step from " + start_month + " on; "
                          "the earlier steps are not read") if start_month else
                         "cells finite in dh and flagged at every step of the record",
        "cells": {"grounded": int(ok.sum())},
        "area_km2": {"grounded": round(float(area[ok].sum()), 2)},
        "pole_hole_cells": pole,
        "basins_present": int(len(np.unique(basin[ok]))) if basin is not None else None,
        "cells_without_error_max": {"grounded": no_error},
        "uncertainty_basis": "the product's rmse (sigma_m of Nilsson and others 2022, its description) "
                             "times cell area, in quadrature over the cells (a floor where errors "
                             "correlate across cells) and summed linearly (the bound where they "
                             "correlate fully), both carried",
        "global_attributes": attrs,
    }
    ds.close()


def run(greenland: Path | None, antarctica: Path | None, out: Path, stamp_out: Path | None,
        antarctic_from: str | None = None):
    if not (greenland or antarctica):
        sys.exit("nothing to read: give --greenland and/or --antarctic")
    rows, series = [], {}
    if greenland:
        read_greenland(greenland, rows, series)
    if antarctica:
        read_antarctica(antarctica, rows, series, antarctic_from)
    rows.sort(key=lambda r: (r[0], r[1], r[2]))
    with out.open("w", encoding="utf-8", newline="") as f:
        wr = csv.writer(f)
        wr.writerow(CSV_COLUMNS)
        for r in rows:
            wr.writerow([r[0], r[1], r[2], f"{r[3]:.6f}", f"{r[4]:.6f}", f"{r[5]:.6f}", f"{r[6]:.2f}",
                         r[7], r[8], r[9], r[10]])
    first, last = min(r[2] for r in rows), max(r[2] for r in rows)
    stamp = {
        "term": "volume-itslive",
        "quantity": "surface elevation change from the ITS_LIVE elevation change products summed to a "
                    "volume anomaly per ice sheet domain and time step",
        "units": "value_km3, uncertainty_km3 and uncertainty_correlated_km3 in km3 of surface height "
                 "change (not ice); area_km2 in km2",
        "sign_convention": "positive is a higher surface (more volume), the product's own",
        "months": [first, last],
        "n_rows": len(rows),
        "domains": sorted({(r[0], r[1]) for r in rows}),
        "not_mass": "a volume of surface height change: the firn air content change is removed and "
                    "a density applied by the computation, never here (the bundle's gotcha "
                    "atl15-height-change-is-not-mass-change states the trap for ATL15; it holds "
                    "for every altimetric height change)",
        "series": series,
    }
    if stamp_out:
        stamp_out.write_text(json.dumps(stamp, indent=2) + "\n", encoding="utf-8")
    print(f"{out.name}: {len(rows)} rows, {first} to {last}, domains "
          + ", ".join(f"{a}/{b}" for a, b in stamp["domains"]))


def write_toy_greenland(p: Path):
    """A 3-month, 3 by 4 EPSG:3413 grid: the ice sheet at 0, -1 and -2 m
    with rms 0.5 m, the peripheral glaciers at +0.5 m with rms 0.2, one
    ice sheet cell missing in month two, one rms missing in month three."""
    ds = nc.Dataset(p, "w")
    ds.title = "toy greenland"; ds.doi = "doi.org/10.5067/TOY"; ds.version = "9.9"; ds.epsg_number = 3413
    ds.createDimension("x", 4); ds.createDimension("y", 3); ds.createDimension("time", 3)
    x = ds.createVariable("x", "f4", ("x",)); y = ds.createVariable("y", "f4", ("y",))
    x[:] = -645127.5 + 1920.0 * np.arange(4); y[:] = -641272.5 + 1920.0 * np.arange(3)
    t = ds.createVariable("time", "f8", ("time",)); t.units = "days since 1992-01-15 00:00:00"; t.calendar = "gregorian"
    t[:] = [0.0, 31.0, 60.0]
    m = ds.createVariable("mask", "u1", ("y", "x"))
    m[:] = [[1, 1, 2, 0], [1, 1, 2, 0], [1, 0, 2, 0]]
    dh = ds.createVariable("dh", "f4", ("time", "y", "x"), fill_value=-32767.0); dh.comment = "toy dh w.r.t. 2014-01-01"
    rms = ds.createVariable("rms", "f4", ("time", "y", "x"), fill_value=-32767.0); rms.comment = "toy rms"
    for i in range(3):
        d = np.where(m[:] == 1, -1.0 * i, np.where(m[:] == 2, 0.5, np.nan))
        e = np.where(m[:] == 1, 0.5, np.where(m[:] == 2, 0.2, np.nan))
        if i == 1:
            d[2, 0] = np.nan
        if i == 2:
            e[0, 0] = np.nan
        dh[i] = np.where(np.isfinite(d), d, -32767.0)
        rms[i] = np.where(np.isfinite(e), e, -32767.0)
    ds.close()


def write_toy_antarctica(p: Path):
    """A 3-month, 2 by 2 EPSG:3031 grid: three grounded cells at +1, +2
    and -1 m per month index, rmse 0.3, one cell flagged no-data
    throughout, one pole hole cell."""
    ds = nc.Dataset(p, "w")
    ds.title = "toy antarctica grounded"; ds.version = "1.0"; ds.doi = "doi.org/10.5067/TOYANT"
    ds.createDimension("x", 2); ds.createDimension("y", 2); ds.createDimension("time", 3)
    x = ds.createVariable("x", "f8", ("x",)); y = ds.createVariable("y", "f8", ("y",))
    x[:] = 1920.0 * np.arange(2); y[:] = 2798407.5 - 1920.0 * np.arange(2)
    t = ds.createVariable("time", "f8", ("time",)); t.units = "days since 1950-01-01"
    t[:] = [15416.0, 15447.0, 15477.0]
    mp = ds.createVariable("mapping", "S1", ()); mp.spatial_epsg = "3031.0"
    dh = ds.createVariable("dh", "f4", ("time", "y", "x"), fill_value=-32767.0); dh.standard_name = "height anomaly w.r.t. 2013-12-16"
    err = ds.createVariable("rmse", "f4", ("time", "y", "x"), fill_value=-32767.0); err.description = "toy rmse"
    fl = ds.createVariable("quality_flag", "u1", ("time", "y", "x"))
    bs = ds.createVariable("basin", "u1", ("y", "x")); bs[:] = [[1, 1], [2, 0]]
    for i in range(3):
        dh[i] = np.array([[1.0, 2.0], [-1.0, 0.0]]) * i
        err[i] = 0.3
        fl[i] = [[1, 3], [2, 0]]
    ds.close()


def selftest():
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        pg, pa = td / "toy_greenland.nc", td / "toy_antarctica.nc"
        write_toy_greenland(pg); write_toy_antarctica(pa)
        out, st = td / "volume-itslive.csv", td / "volume-itslive-stamp.json"
        run(pg, pa, out, st, antarctic_from="1992-04")      # the first Antarctic step is left out
        rows = list(csv.DictReader(out.open()))
        gis = [r for r in rows if r["ice_sheet"] == "greenland" and r["domain"] == "ice_sheet"]
        gpg = [r for r in rows if r["ice_sheet"] == "greenland" and r["domain"] == "peripheral_glaciers"]
        ant = [r for r in rows if r["ice_sheet"] == "antarctica"]
        assert [r["month"] for r in gis] == ["1992-01", "1992-02", "1992-03"], gis
        assert all(r["n_cells"] == "4" for r in gis), gis       # the cell missing in month two is dropped
        area = float(gis[0]["area_km2"])
        # volume = dh (m) times area (km2) times 1e-3: -1 m over the four cells in month two
        got = [float(r["value_km3"]) for r in gis]
        want = [0.0, -1.0 * area * 1e-3, -2.0 * area * 1e-3]
        assert all(abs(g - w) < 2e-5 for g, w in zip(got, want)), (got, want)   # area_km2 is written at 0.01
        # month one: rms 0.5 over four cells of area a each: quadrature 0.5 a sqrt(4), linear 0.5 a 4
        a = area / 4.0
        assert abs(float(gis[0]["uncertainty_km3"]) - 0.5 * a * 2.0 * 1e-3) < 2e-5, gis[0]
        assert abs(float(gis[0]["uncertainty_correlated_km3"]) - 0.5 * a * 4.0 * 1e-3) < 2e-5, gis[0]
        # month three: one rms missing, so the sums run over three cells
        assert abs(float(gis[2]["uncertainty_correlated_km3"]) - 0.5 * a * 3.0 * 1e-3) < 2e-5, gis[2]
        assert all(abs(float(r["value_km3"]) - 0.5 * float(r["area_km2"]) * 1e-3) < 2e-5 for r in gpg), gpg
        assert all(r["n_cells"] == "3" and r["sampling"] == "monthly" for r in gpg), gpg
        # Antarctica: three flagged cells (1, 3 and 2), one no-data cell out: dh sums to 2 m times i
        assert all(r["n_cells"] == "3" and r["domain"] == "grounded" for r in ant), ant
        assert [r["month"] for r in ant] == ["1992-04", "1992-05"], ant
        aa = float(ant[0]["area_km2"]) / 3.0
        assert abs(float(ant[0]["value_km3"]) - 2.0 * aa * 1e-3) < 2e-5, ant[0]
        stamp = json.loads(st.read_text())
        assert stamp["series"]["greenland"]["cells"] == {"ice_sheet": 4, "peripheral_glaciers": 3}, stamp
        assert stamp["series"]["greenland"]["doi"] == "10.5067/TOY", stamp["series"]["greenland"]["doi"]
        assert stamp["series"]["greenland"]["cells_without_error_max"] == {"ice_sheet": 1, "peripheral_glaciers": 0}
        assert stamp["series"]["antarctica"]["pole_hole_cells"] == 1 and stamp["series"]["antarctica"]["basins_present"] == 2
        assert stamp["series"]["antarctica"]["steps_before_start_month"] == 1
        assert stamp["months"] == ["1992-01", "1992-05"], stamp["months"]   # greenland Jan to Mar, antarctica Apr to May
        print(f"selftest: greenland ice sheet volumes {[round(v, 6) for v in got]} km3 over four fixed cells, "
              f"peripheral +0.5 m; one missing rms counted; antarctic grounded three cells "
              f"{float(ant[0]['value_km3']):.6f} km3 with one pole hole cell, the step before "
              "--antarctic-from left out; OK")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--greenland", type=Path); ap.add_argument("--antarctic", type=Path)
    ap.add_argument("--out", type=Path); ap.add_argument("--stamp-out", type=Path)
    ap.add_argument("--antarctic-from", default=None, help="YYYY-MM: fix the Antarctic cell set over the steps from this month")
    ap.add_argument("--fetch-to", type=Path)
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        selftest(); return
    if not a.out:
        ap.error("--out is required")
    if a.antarctic_from and not re.fullmatch(r"\d{4}-\d{2}", a.antarctic_from):
        ap.error("--antarctic-from takes YYYY-MM")
    paths = {}
    for name, path in (("greenland", a.greenland), ("antarctica", a.antarctic)):
        if path and not path.is_file():
            if not a.fetch_to:
                ap.error(f"{path} does not exist; give --fetch-to DIR to download it")
            path = a.fetch_to / Path(PRODUCTS[name]["key"]).name
            if not path.is_file():
                fetch(BUCKET + PRODUCTS[name]["key"], path)
        paths[name] = path
    run(paths["greenland"], paths["antarctica"], a.out, a.stamp_out, a.antarctic_from)


if __name__ == "__main__":
    main()
