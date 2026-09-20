#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["numpy==2.2.6", "netCDF4==1.7.2", "pyproj==3.7.1"]
# ///
"""Loader for the firn term of the ice sheet mass balance closure: the
firn air content change from NASA's GEMB (Glacier Energy and Mass
Balance) model output as ITS_LIVE distributes it on AWS, aggregated
per ice sheet and per time step, written as the data root's firn.csv.

What ITS_LIVE distributes, and what this loader therefore reads:

  Greenland   height_change/Greenland/Greenland_G1920V01_IceSheetGlacierIceHeight.nc
              (the grounded ice sheet and peripheral glacier elevation
              change product, version 1.1, doi 10.5067/ICFVI7DKHZJV).
              Its variable dfac_gemb is the firn air content anomaly
              against 2014-01-01 from GEMB version 1.3.0, monthly from
              1992-01 to 2023-12 on the 1920 m EPSG:3413 grid, beside
              dfac_gsfc from GSFC-FDM version 1.2.1. Its mask separates
              the ice sheet (1) from the peripheral glaciers (2).
  Antarctica  height_change/Antarctica/Floating/ANT_G1920V01_IceShelfMelt.nc
              (the ice shelf height change and basal melt product,
              version 1.0, doi 10.5067/SE3XH9RXQWAM, NSIDC-0792). Its
              variable fac is the firn air content from GEMB r24739
              forced with 3-hourly ERA5 (the user guide), quarterly
              from 1992-03 to 2017-12 on the 1920 m EPSG:3031 grid,
              over the floating ice shelves only (ID 1 to 182; land is
              255). No GEMB field over grounded Antarctica is in the
              ITS_LIVE distribution, and the loader says so rather
              than substituting one.

What it computes, per domain and time step:

  1. The true ground area of every grid cell from the projection's
     areal scale (pyproj get_factors), so a polar stereographic cell
     counts by its area on the ellipsoid, not by its map area.
  2. A fixed cell set per domain: the cells inside the mask that carry
     a finite value at every time step, so an anomaly series is never
     moved by coverage changes.
  3. The area-weighted mean firn air content anomaly in metres of air
     over that set (value_m), the same anomaly integrated to a volume
     in km3 of air (volume_km3), the area and the cell count.
     Greenland: the product's own anomaly against 2014-01-01.
     Antarctica: fac minus the product's fac_mean (its 1992 to 2017
     record mean), so the reference is stated per domain in the stamp.
  4. The uncertainty. Greenland: the product ships no firn error, so
     the loader takes the absolute difference between the GEMB and the
     GSFC-FDM aggregates the file carries, a model-spread basis, not a
     formal error. Antarctica: the stated noise floor the altimetry
     and steric loaders use (the standard deviation of adjacent-step
     differences of the finished series over sqrt(2)), because the
     product's fac_err does not read as a firn air content error (tens
     of metres at the median, 9999 where it has none, a units
     attribute of m of ice per year); its statistics go in the stamp.
  5. The calendar month of each time value. A step with no finite
     value inside the mask (the ice shelf product's last quarter) is a
     non-sample, skipped and listed in the stamp, never filled. A
     second step falling in a month already taken is refused, never
     averaged. The Antarctic rows are quarterly (one row per product
     time step, labelled by the month of the time value) and say so in
     their sampling column.

Sign convention: positive is more air in the firn column, that is a
thicker firn column at unchanged mass.

Usage:
  isb_firn_gemb.py [--greenland FILE.nc] [--antarctic FILE.nc] --out firn.csv [--stamp-out firn-stamp.json]
  --fetch-to DIR   download the product file from its ITS_LIVE bucket URL into DIR
                   when the given path does not exist (the bucket is public)
  --selftest       synthetic grids in both layouts with aggregates known by hand
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
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
        "doi": "10.5067/ICFVI7DKHZJV",
        "epsg": 3413,
        "domains": {"ice_sheet": 1, "peripheral_glaciers": 2},
    },
    "antarctica": {
        "key": "height_change/Antarctica/Floating/ANT_G1920V01_IceShelfMelt.nc",
        "doi": "10.5067/SE3XH9RXQWAM",
        "epsg": 3031,
        "domains": {"ice_shelves": (1, 182)},
    },
}
ALTERNATES_NOT_READ = [
    "RACMO2 (IMAU regional climate model firn and surface mass balance output): not read",
    "MAR (regional climate model surface mass balance output): not read",
    "the IMBIE basin definitions: not read; the products' own masks partition the grids",
]
CSV_COLUMNS = ["ice_sheet", "domain", "month", "value_m", "uncertainty_m",
               "volume_km3", "area_km2", "n_cells", "sampling"]


def bare_doi(text: str) -> str:
    """The bare DOI of a file attribute that may carry a resolver prefix
    (the Greenland file writes doi.org/10.5067/...)."""
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
    """Stream a public product file to dest; nothing else is sent."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    print(f"fetching {url} -> {dest}", file=sys.stderr)
    with urllib.request.urlopen(url, timeout=120) as r, dest.open("wb") as f:
        for chunk in iter(lambda: r.read(1 << 20), b""):
            f.write(chunk)


def cell_area_km2(epsg: int, x: np.ndarray, y: np.ndarray) -> np.ndarray:
    """Ground area of every cell of a projected grid, shape (ny, nx): the
    map area of a cell divided by the projection's areal scale there."""
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


def field2d(var) -> np.ndarray:
    return np.ma.filled(np.ma.masked_invalid(var[:]), np.nan).astype(float)


def month_of(t, i: int) -> str:
    d = nc.num2date(float(t[i]), t.units, getattr(t, "calendar", "standard"))
    return f"{d.year:04d}-{d.month:02d}"


def date_of(t, i: int) -> str:
    d = nc.num2date(float(t[i]), t.units, getattr(t, "calendar", "standard"))
    return f"{d.year:04d}-{d.month:02d}-{d.day:02d}"


ERROR_SENTINEL = 9000.0     # the ice shelf product's fac_err carries 9999 where it has no error


def nonempty_steps(var, n: int, inside: np.ndarray) -> list[int]:
    """The time steps that carry at least one finite value inside the
    mask; a step with none is a non-sample (the product's last quarter
    is one), skipped and recorded, never filled."""
    return [i for i in range(n) if np.isfinite(field(var, i)[inside]).any()]


def fixed_cell_set(var, steps, inside: np.ndarray) -> np.ndarray:
    """Cells inside the mask that are finite at every listed time step."""
    ok = inside.copy()
    for i in steps:
        ok &= np.isfinite(field(var, i))
    return ok


def noise_floor(values) -> float:
    """The stated noise floor the altimetry and steric loaders use: the
    standard deviation of adjacent-step differences divided by sqrt(2)."""
    v = np.asarray(values, float)
    return float(np.std(np.diff(v), ddof=1) / np.sqrt(2.0)) if len(v) > 2 else float("nan")


def aggregate(values: np.ndarray, area: np.ndarray, ok: np.ndarray):
    """Area-weighted mean (m) and integrated volume (km3) over ok."""
    w = area[ok]
    v = values[ok]
    total = float(np.sum(v * w))            # m times km2
    return total / float(w.sum()), total * 1e-3


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
    gemb, gsfc = ds["dfac_gemb"], ds["dfac_gsfc"]
    iced = (mask == 1) | (mask == 2)
    steps = nonempty_steps(gemb, n, iced)
    empty = [date_of(t, i) for i in range(n) if i not in steps]
    domains = {}
    for name, code in PRODUCTS["greenland"]["domains"].items():
        ok = fixed_cell_set(gemb, steps, mask == code)
        ok &= fixed_cell_set(gsfc, steps, mask == code)
        domains[name] = ok
        print(f"  greenland {name}: {int(ok.sum())} cells, {float(area[ok].sum()):.0f} km2",
              file=sys.stderr)
    months = {}
    for i in steps:
        label = month_of(t, i)
        if label in months:
            sys.exit(f"{path.name}: two time steps ({months[label]} and {i}) fall in {label}; "
                     "the loader does not average steps")
        months[label] = i
        g, s = field(gemb, i), field(gsfc, i)
        for name, ok in domains.items():
            mean_g, vol_g = aggregate(g, area, ok)
            mean_s, _ = aggregate(s, area, ok)
            rows.append(["greenland", name, label, f"{mean_g:.6f}", f"{abs(mean_g - mean_s):.6f}",
                         f"{vol_g:.4f}", f"{float(area[ok].sum()):.2f}", int(ok.sum()), "monthly"])
    labels = sorted(months)
    stamp["greenland"] = {
        "product": attrs.get("title", ""),
        "doi": bare_doi(attrs.get("doi", "")),
        "product_version": attrs.get("version", ""),
        "granule": path.name,
        "granule_sha256": sha256(path),
        "source_url": BUCKET + PRODUCTS["greenland"]["key"],
        "read_utc": utcnow(),
        "variable": "dfac_gemb",
        "variable_comment": str(getattr(gemb, "comment", "")),
        "gemb_version": "1.3.0 (the variable's comment)",
        "forcing": "not stated in the file's attributes; no product documentation for this "
                   "file was found on nsidc.org or in the ITS_LIVE bucket, so the forcing of "
                   "the GEMB 1.3.0 run is left unstated here rather than assumed",
        "grid": f"1920 m polar stereographic, EPSG:{epsg}, {len(y)} by {len(x)} cells; "
                "cell areas from the projection's areal scale",
        "mask": "the file's mask variable: 1 ice sheet, 2 peripheral glacier, 0 non-ice; "
                "the ice sheet domain is the grounded ice sheet, the product being a grounded "
                "ice elevation change product",
        "aggregation": "area-weighted mean over the fixed set of cells inside the mask that are "
                       "finite in dfac_gemb and dfac_gsfc at every time step; the same anomaly "
                       "integrated to km3 of air",
        "reference": "anomaly against 2014-01-01, the product's own reference",
        "sampling": "monthly",
        "time_coverage": [date_of(t, steps[0]), date_of(t, steps[-1])],
        "months": [labels[0], labels[-1]],
        "n_steps": len(steps),
        "empty_steps_skipped": empty,
        "cells": {name: int(ok.sum()) for name, ok in domains.items()},
        "area_km2": {name: round(float(area[ok].sum()), 2) for name, ok in domains.items()},
        "uncertainty_basis": "model spread: the absolute difference between the GEMB 1.3.0 and "
                             "the GSFC-FDM 1.2.1 aggregates the file carries (dfac_gemb, "
                             "dfac_gsfc); the product ships no firn error field",
        "global_attributes": attrs,
    }
    ds.close()


def read_antarctica(path: Path, rows: list, stamp: dict) -> None:
    ds = nc.Dataset(path)
    attrs = {a: str(getattr(ds, a)) for a in ds.ncattrs()}
    mapping = ds["mapping"]
    epsg = int(float(getattr(mapping, "spatial_epsg", PRODUCTS["antarctica"]["epsg"])))
    if epsg != PRODUCTS["antarctica"]["epsg"]:
        sys.exit(f"{path.name}: spatial_epsg {epsg} is not the expected {PRODUCTS['antarctica']['epsg']}")
    x, y, t = ds["x"][:], ds["y"][:], ds["time"]
    n = len(t)
    area = cell_area_km2(epsg, x, y)
    ident = np.asarray(ds["ID"][:]).astype(int)
    lo, hi = PRODUCTS["antarctica"]["domains"]["ice_shelves"]
    fac, err, fmean = ds["fac"], ds["fac_err"], field2d(ds["fac_mean"])
    shelf = (ident >= lo) & (ident <= hi)
    steps = nonempty_steps(fac, n, shelf)
    empty = [date_of(t, i) for i in range(n) if i not in steps]
    ok = fixed_cell_set(fac, steps, shelf) & np.isfinite(fmean)
    print(f"  antarctica ice_shelves: {int(ok.sum())} cells, {float(area[ok].sum()):.0f} km2, "
          f"{len(empty)} empty steps skipped", file=sys.stderr)
    ref_mean, _ = aggregate(fmean, area, ok)
    months, series, err_stats = {}, [], []
    for i in steps:
        label = month_of(t, i)
        if label in months:
            sys.exit(f"{path.name}: two time steps ({months[label]} and {i}) fall in {label}; "
                     "the loader does not average steps")
        months[label] = i
        f = field(fac, i)
        mean_f, _ = aggregate(f, area, ok)
        _, vol = aggregate(f - fmean, area, ok)
        e = field(err, i)[ok]
        valid = np.isfinite(e) & (e < ERROR_SENTINEL)
        err_stats.append([label, int((~valid).sum()),
                          [round(float(q), 3) for q in np.percentile(e[valid], [1, 50, 99])]
                          if valid.any() else None])
        series.append([label, mean_f - ref_mean, vol])
    floor = noise_floor([s[1] for s in series])
    for label, anom, vol in series:
        rows.append(["antarctica", "ice_shelves", label, f"{anom:.6f}", f"{floor:.6f}",
                     f"{vol:.4f}", f"{float(area[ok].sum()):.2f}", int(ok.sum()), "quarterly"])
    labels = sorted(months)
    stamp["antarctica"] = {
        "product": attrs.get("title", ""),
        "doi": PRODUCTS["antarctica"]["doi"],
        "product_version": attrs.get("version", ""),
        "granule": path.name,
        "granule_sha256": sha256(path),
        "source_url": BUCKET + PRODUCTS["antarctica"]["key"],
        "read_utc": utcnow(),
        "variable": "fac (with fac_err and fac_mean)",
        "variable_source": str(getattr(fac, "source", "")),
        "gemb_version": "GEMB r24739 (the variable's source attribute)",
        "forcing": "3-hourly ERA5 reanalysis, 1979 to 2017, after a relaxation simulation "
                   "(the NSIDC-0792 user guide, section 2.3.1.3)",
        "grid": f"1920 m polar stereographic, EPSG:{epsg}, {len(y)} by {len(x)} cells; "
                "cell areas from the projection's areal scale; the user guide says the GEMB "
                "fields were interpolated from a 5 km grid",
        "mask": "the file's ID variable: ice shelf identifiers 1 to 182 (an edited MEaSUREs "
                "Antarctic Boundaries version 2), land 255; the domain is the floating ice "
                "shelves only, since no GEMB field over grounded Antarctica is in the ITS_LIVE "
                "distribution",
        "aggregation": "area-weighted mean over the fixed set of ice shelf cells finite in fac "
                       "at every time step and in fac_mean; the anomaly integrated to km3 of "
                       "air; fac_err is read only for the statistics in the stamp, where it is "
                       "finite and below its sentinel",
        "reference": "anomaly against the product's fac_mean (its 1992 to 2017 record mean), "
                     f"whose area-weighted mean over the cell set is {ref_mean:.6f} m",
        "sampling": "quarterly: one row per product time step, labelled by the calendar month "
                    "of the time value (the user guide calls it the quarter start date)",
        "time_coverage": [date_of(t, steps[0]), date_of(t, steps[-1])],
        "months": [labels[0], labels[-1]],
        "n_steps": len(steps),
        "empty_steps_skipped": empty,
        "cells": {"ice_shelves": int(ok.sum())},
        "area_km2": {"ice_shelves": round(float(area[ok].sum()), 2)},
        "uncertainty_m": floor,
        "uncertainty_basis": "stated noise floor: standard deviation of adjacent-step "
                             "differences of the finished anomaly series divided by sqrt(2), "
                             "written on every row; the product's fac_err is not used because "
                             "its values (tens of metres at the median, 9999 where it has none) "
                             "and its units attribute (m of ice per year, where the user guide "
                             "gives m) do not read as a firn air content error",
        "fac_err_not_used": {
            "per_step": "[label, cells at or above the 9999 sentinel or not finite, percentiles "
                        "1, 50 and 99 of the rest over the fixed cell set]",
            "first_middle_last": [err_stats[0], err_stats[len(err_stats) // 2], err_stats[-1]],
        },
        "global_attributes": attrs,
    }
    ds.close()


def run(greenland: Path | None, antarctica: Path | None, out: Path, stamp_out: Path | None):
    if not (greenland or antarctica):
        sys.exit("nothing to read: give --greenland and/or --antarctic")
    rows, series = [], {}
    if greenland:
        read_greenland(greenland, rows, series)
    if antarctica:
        read_antarctica(antarctica, rows, series)
    rows.sort(key=lambda r: (r[0], r[1], r[2]))
    with out.open("w", encoding="utf-8", newline="") as f:
        wr = csv.writer(f)
        wr.writerow(CSV_COLUMNS)
        wr.writerows(rows)
    first = min(r[2] for r in rows)
    last = max(r[2] for r in rows)
    stamp = {
        "term": "firn",
        "quantity": "firn air content anomaly from GEMB, per ice sheet domain and time step",
        "units": "value_m and uncertainty_m in metres of air (area-weighted mean over the "
                 "domain); volume_km3 in km3 of air; area_km2 in km2",
        "sign_convention": "positive is more air in the firn column (a thicker column at "
                           "unchanged mass)",
        "months": [first, last],
        "n_rows": len(rows),
        "domains": sorted({(r[0], r[1]) for r in rows}),
        "not_in_the_distribution": [
            "Antarctica, grounded ice sheet: no GEMB firn air content field is distributed "
            "with ITS_LIVE on AWS (the bucket was listed under height_change, mass_change, "
            "ice_masks and documentation); the Antarctic rows cover the floating ice shelves",
        ],
        "alternates_not_read": ALTERNATES_NOT_READ,
        "series": series,
    }
    if stamp_out:
        stamp_out.write_text(json.dumps(stamp, indent=2) + "\n", encoding="utf-8")
    print(f"{out.name}: {len(rows)} rows, {first} to {last}, domains "
          + ", ".join(f"{a}/{b}" for a, b in stamp["domains"]))


def write_toy_greenland(p: Path):
    """A 3-month, 3 by 4 EPSG:3413 grid: the ice sheet at +0.5 m rising by
    0.1 m per month with the GSFC field 0.05 m lower, the peripheral
    glaciers at -0.2 m, one ice sheet cell missing in one month."""
    ds = nc.Dataset(p, "w")
    ds.title = "toy greenland"; ds.doi = "doi.org/10.5067/TOY"; ds.version = "9.9"; ds.epsg_number = 3413
    ds.createDimension("x", 4); ds.createDimension("y", 3); ds.createDimension("time", 3)
    x = ds.createVariable("x", "f4", ("x",)); y = ds.createVariable("y", "f4", ("y",))
    x[:] = -645127.5 + 1920.0 * np.arange(4); y[:] = -641272.5 + 1920.0 * np.arange(3)
    t = ds.createVariable("time", "f8", ("time",)); t.units = "days since 1992-01-15 00:00:00"; t.calendar = "gregorian"
    t[:] = [0.0, 31.0, 60.0]
    m = ds.createVariable("mask", "u1", ("y", "x"))
    m[:] = [[1, 1, 2, 0], [1, 1, 2, 0], [1, 0, 2, 0]]
    g = ds.createVariable("dfac_gemb", "f4", ("time", "y", "x"), fill_value=-32767.0); g.comment = "GEMB Version 1.3.0"
    s = ds.createVariable("dfac_gsfc", "f4", ("time", "y", "x"), fill_value=-32767.0)
    base = np.where(m[:] == 1, 0.5, np.where(m[:] == 2, -0.2, np.nan))
    for i in range(3):
        gi = base + 0.1 * i * (m[:] == 1)
        if i == 1:
            gi[2, 0] = np.nan                     # one ice sheet cell missing in month two
        g[i] = np.where(np.isfinite(gi), gi, -32767.0)
        s[i] = np.where(np.isfinite(gi), gi - 0.05, -32767.0)
    ds.close()


def write_toy_antarctica(p: Path):
    """A 4-quarter, 3 by 3 EPSG:3031 grid: the three shelf 1 cells at 2,
    3 and 2.5 m of air, the three shelf 2 cells at 1 m throughout, the
    record mean stored as fac_mean, the fourth quarter empty (as the
    product's last quarter is), errors 44 m with one 9999 sentinel, two
    land cells and one ocean cell."""
    ds = nc.Dataset(p, "w")
    ds.title = "toy antarctica"; ds.version = "1.0"
    ds.createDimension("x", 3); ds.createDimension("y", 3); ds.createDimension("time", 4)
    x = ds.createVariable("x", "f8", ("x",)); y = ds.createVariable("y", "f8", ("y",))
    x[:] = 1920.0 * np.arange(3); y[:] = 2798407.5 - 1920.0 * np.arange(3)
    t = ds.createVariable("time", "f8", ("time",)); t.units = "days since 1950-01-01"
    t[:] = [15416.0, 15507.0, 15599.0, 15690.0]    # 1992-03-17, 06-16, 09-16, 12-16
    mp = ds.createVariable("mapping", "S1", ()); mp.spatial_epsg = "3031.0"
    ident = ds.createVariable("ID", "u1", ("y", "x"))
    ident[:] = [[1, 1, 255], [2, 2, 0], [1, 2, 255]]
    fac = ds.createVariable("fac", "f4", ("time", "y", "x"), fill_value=-32767.0); fac.source = "GEMB toy"
    err = ds.createVariable("fac_err", "f4", ("time", "y", "x"), fill_value=-32767.0)
    fm = ds.createVariable("fac_mean", "f4", ("y", "x"), fill_value=-32767.0)
    shelf1, shelf2 = ident[:] == 1, ident[:] == 2
    for i, v1 in enumerate([2.0, 3.0, 2.5]):
        f = np.where(shelf1, v1, np.where(shelf2, 1.0, np.nan))
        fac[i] = np.where(np.isfinite(f), f, -32767.0)
        e = np.where(np.isfinite(f), 44.0, -32767.0); e[0, 0] = 9999.0
        err[i] = e
    fac[3] = -32767.0; err[3] = -32767.0
    fmv = np.where(shelf1, 2.5, np.where(shelf2, 1.0, np.nan))
    fm[:] = np.where(np.isfinite(fmv), fmv, -32767.0)
    ds.close()


def selftest():
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        # The area function: at the standard parallel the areal scale is one,
        # so a cell there has its map area, 1920 m squared.
        crs = CRS.from_epsg(3413)
        fwd = Transformer.from_crs(4326, crs, always_xy=True)
        x70, y70 = fwd.transform(-45.0, 70.0)
        a = cell_area_km2(3413, np.array([x70, x70 + 1920.0]), np.array([y70, y70 + 1920.0]))
        assert abs(a[0, 0] - 1.92 ** 2) < 1e-5, a
        pg, pa = td / "toy_greenland.nc", td / "toy_antarctica.nc"
        write_toy_greenland(pg); write_toy_antarctica(pa)
        out, st = td / "firn.csv", td / "firn-stamp.json"
        run(pg, pa, out, st)
        rows = list(csv.DictReader(out.open()))
        gis = [r for r in rows if r["ice_sheet"] == "greenland" and r["domain"] == "ice_sheet"]
        gpg = [r for r in rows if r["ice_sheet"] == "greenland" and r["domain"] == "peripheral_glaciers"]
        ant = [r for r in rows if r["ice_sheet"] == "antarctica"]
        assert [r["month"] for r in gis] == ["1992-01", "1992-02", "1992-03"], gis
        # The fixed cell set drops the cell missing in month two: four ice sheet cells.
        assert all(r["n_cells"] == "4" for r in gis), gis
        got = [float(r["value_m"]) for r in gis]
        want = [0.5, 0.6, 0.7]
        assert all(abs(g - w) < 1e-5 for g, w in zip(got, want)), (got, want)
        assert all(abs(float(r["uncertainty_m"]) - 0.05) < 1e-5 for r in gis), gis
        assert all(abs(float(r["value_m"]) + 0.2) < 1e-5 for r in gpg), gpg
        assert all(r["n_cells"] == "3" and r["sampling"] == "monthly" for r in gpg), gpg
        # Antarctica: six shelf cells, three at 2, 3, 2.5 m and three at 1 m;
        # the anomaly against the record mean is about -0.25, +0.25 and 0 m
        # (exactly antisymmetric in area weight), the empty fourth quarter
        # is skipped, and the noise floor of the three-step series is the
        # standard deviation of (0.5, -0.25) over sqrt(2), about 0.375 m.
        assert [r["month"] for r in ant] == ["1992-03", "1992-06", "1992-09"], ant
        assert all(r["n_cells"] == "6" and r["sampling"] == "quarterly" for r in ant), ant
        v0, v1, v2 = (float(r["value_m"]) for r in ant)
        assert abs(v0 + v1) < 1e-5 and abs(v1 - 0.25) < 1e-3 and abs(v2) < 1e-3, (v0, v1, v2)
        floor = noise_floor([v0, v1, v2])
        assert abs(floor - 0.375) < 2e-3, floor
        assert all(abs(float(r["uncertainty_m"]) - floor) < 1e-5 for r in ant), ant
        stamp = json.loads(st.read_text())
        assert stamp["series"]["greenland"]["cells"] == {"ice_sheet": 4, "peripheral_glaciers": 3}, stamp
        assert stamp["series"]["antarctica"]["granule_sha256"].startswith("sha256:")
        assert stamp["series"]["antarctica"]["empty_steps_skipped"] == ["1992-12-16"], stamp["series"]["antarctica"]["empty_steps_skipped"]
        assert stamp["series"]["antarctica"]["fac_err_not_used"]["first_middle_last"][0][1] == 1
        assert stamp["months"] == ["1992-01", "1992-09"], stamp["months"]
        print(f"selftest: greenland ice sheet {got} m vs {want}, spread 0.05 m; peripheral -0.2 m; "
              f"antarctic shelves {v0:+.4f}, {v1:+.4f}, {v2:+.4f} m, noise floor {floor:.4f} m, "
              f"one empty quarter skipped; standard parallel cell {a[0,0]:.6f} km2; OK")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--greenland", type=Path); ap.add_argument("--antarctic", type=Path)
    ap.add_argument("--out", type=Path); ap.add_argument("--stamp-out", type=Path)
    ap.add_argument("--fetch-to", type=Path)
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        selftest(); return
    if not a.out:
        ap.error("--out is required")
    for name, path in (("greenland", a.greenland), ("antarctica", a.antarctic)):
        if path and not path.is_file():
            if not a.fetch_to:
                sys.exit(f"{path} does not exist (give --fetch-to DIR to download it)")
            fetch(BUCKET + PRODUCTS[name]["key"], path)
    run(a.greenland, a.antarctic, a.out, a.stamp_out)


if __name__ == "__main__":
    main()
