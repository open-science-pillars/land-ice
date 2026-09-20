#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["numpy==2.2.6", "netCDF4==1.7.2", "pyproj==3.7.1"]
# ///
"""Loader for the surface mass balance term of the ice sheet mass
balance closure: the surface mass balance from NASA's GEMB (Glacier
Energy and Mass Balance) model output as ITS_LIVE distributes it on
AWS, aggregated per ice sheet domain and per time step, written as
the data root's smb.csv.

What ITS_LIVE distributes, and what this loader therefore reads:

  Antarctica  height_change/Antarctica/Floating/ANT_G1920V01_IceShelfMelt.nc
              (the ice shelf height change and basal melt product,
              version 1.0, doi 10.5067/SE3XH9RXQWAM, NSIDC-0792). Its
              variable smb is the surface mass budget in metres of ice
              per year (density 917 kg per m3, the variable's attribute)
              from GEMB r24739 forced with 3-hourly ERA5 (the user
              guide), quarterly from 1992-03 to 2017-12 on the 1920 m
              EPSG:3031 grid, over the floating ice shelves only (ID 1
              to 182; land is 255), with smb_err and smb_mean.
  Greenland   nothing: the Greenland elevation change product in the
              bucket carries firn air content anomalies (dfac_gemb,
              dfac_gsfc) and no surface mass balance field, and no
              other GEMB output for Greenland is in the distribution.
              The loader has no --greenland option for that reason,
              and the stamp says so under not_in_the_distribution.

What it computes, per time step, over the fixed set of ice shelf cells
finite in smb, smb_err and smb_mean at every step:

  1. The true ground area of every grid cell from the projection's
     areal scale (pyproj get_factors).
  2. The surface mass balance rate integrated over the domain in
     gigatonnes per year (value_gt_per_yr): the sum of smb times cell
     area times the product's ice density, and the same rate as an
     area-weighted mean in metres of ice per year (mean_m_ice_per_yr).
  3. The uncertainty in gigatonnes per year: the sum of smb_err times
     cell area times the density over the cells whose error is finite
     and below the 9999 sentinel the product uses where it has none,
     the cell errors treated as fully correlated (an upper bound); the
     count of cells without an error is recorded in the stamp.
  4. The length of each time step in years (period_years) from the
     interval to the next time value (the last step takes the median
     interval), so the mass over a step is value_gt_per_yr times
     period_years, left to the reader rather than integrated here.
  5. The calendar month of each time value as the row label. A step
     with no finite smb inside the mask (the product's last quarter)
     is a non-sample, skipped and listed in the stamp, never filled. A
     second step in a month already taken is refused, never averaged.
     The rows are quarterly and say so in their sampling column.

Sign convention: positive is mass gained at the surface (accumulation
exceeding ablation), the product's own.

Usage:
  isb_smb_gemb.py --antarctic FILE.nc --out smb.csv [--stamp-out smb-stamp.json]
  --fetch-to DIR   download the product file from its ITS_LIVE bucket URL into DIR
                   when the given path does not exist (the bucket is public)
  --selftest       a synthetic shelf grid with a total known by hand
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
PRODUCT = {
    "key": "height_change/Antarctica/Floating/ANT_G1920V01_IceShelfMelt.nc",
    "doi": "10.5067/SE3XH9RXQWAM",
    "epsg": 3031,
    "shelf_ids": (1, 182),
}
ALTERNATES_NOT_READ = [
    "RACMO2 (IMAU regional climate model surface mass balance output): not read",
    "MAR (regional climate model surface mass balance output): not read",
    "the IMBIE basin definitions: not read; the product's own ice shelf identifiers partition the grid",
]
CSV_COLUMNS = ["ice_sheet", "domain", "month", "value_gt_per_yr", "uncertainty_gt_per_yr",
               "mean_m_ice_per_yr", "period_years", "area_km2", "n_cells", "sampling"]


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


ERROR_SENTINEL = 9000.0     # the product's error fields carry 9999 where they have no error


def nonempty_steps(var, n: int, inside: np.ndarray) -> list[int]:
    """The time steps that carry at least one finite value inside the
    mask; a step with none is a non-sample, skipped and recorded."""
    return [i for i in range(n) if np.isfinite(field(var, i)[inside]).any()]


def fixed_cell_set(var, steps, inside: np.ndarray) -> np.ndarray:
    """Cells inside the mask that are finite at every listed time step."""
    ok = inside.copy()
    for i in steps:
        ok &= np.isfinite(field(var, i))
    return ok


def gigatonnes_per_year(rate_m_ice: np.ndarray, area_km2: np.ndarray, ok: np.ndarray,
                        density: float) -> float:
    """Sum of a rate in m of ice per year times area in km2 times the
    density in kg per m3, in Gt per year: m times km2 is 1e6 m3."""
    return float(np.sum(rate_m_ice[ok] * area_km2[ok])) * 1e6 * density / 1e12


def period_years(t) -> list[float]:
    days = np.asarray(t[:], float)
    d = np.diff(days)
    if len(d) == 0:
        return [float("nan")]
    return [float(v) / 365.25 for v in np.r_[d, np.median(d)]]


def run(antarctica: Path, out: Path, stamp_out: Path | None):
    ds = nc.Dataset(antarctica)
    attrs = {a: str(getattr(ds, a)) for a in ds.ncattrs()}
    mapping = ds["mapping"]
    epsg = int(float(getattr(mapping, "spatial_epsg", PRODUCT["epsg"])))
    if epsg != PRODUCT["epsg"]:
        sys.exit(f"{antarctica.name}: spatial_epsg {epsg} is not the expected {PRODUCT['epsg']}")
    x, y, t = ds["x"][:], ds["y"][:], ds["time"]
    n = len(t)
    area = cell_area_km2(epsg, x, y)
    ident = np.asarray(ds["ID"][:]).astype(int)
    lo, hi = PRODUCT["shelf_ids"]
    smb, err, smean = ds["smb"], ds["smb_err"], field2d(ds["smb_mean"])
    density = float(getattr(smb, "density", 917.0))
    shelf = (ident >= lo) & (ident <= hi)
    steps = nonempty_steps(smb, n, shelf)
    empty = [date_of(t, i) for i in range(n) if i not in steps]
    ok = fixed_cell_set(smb, steps, shelf) & np.isfinite(smean)
    total_area = float(area[ok].sum())
    print(f"  antarctica ice_shelves: {int(ok.sum())} cells, {total_area:.0f} km2, density {density}, "
          f"{len(empty)} empty steps skipped", file=sys.stderr)
    periods = period_years(t)
    months, rows, no_error = {}, [], []
    for i in steps:
        label = month_of(t, i)
        if label in months:
            sys.exit(f"{antarctica.name}: two time steps ({months[label]} and {i}) fall in {label}; "
                     "the loader does not average steps")
        months[label] = i
        s = field(smb, i)
        gt = gigatonnes_per_year(s, area, ok, density)
        e = field(err, i)
        valid = ok & np.isfinite(e) & (e < ERROR_SENTINEL)
        no_error.append(int(ok.sum() - valid.sum()))
        gt_err = gigatonnes_per_year(e, area, valid, density)
        mean_m = float(np.sum(s[ok] * area[ok]) / total_area)
        rows.append(["antarctica", "ice_shelves", label, f"{gt:.6f}", f"{gt_err:.6f}",
                     f"{mean_m:.6f}", f"{periods[i]:.6f}", f"{total_area:.2f}", int(ok.sum()),
                     "quarterly"])
    labels = sorted(months)
    with out.open("w", encoding="utf-8", newline="") as f:
        wr = csv.writer(f)
        wr.writerow(CSV_COLUMNS)
        wr.writerows(rows)
    stamp = {
        "term": "smb",
        "quantity": "surface mass balance rate from GEMB, per ice sheet domain and time step",
        "units": "value_gt_per_yr and uncertainty_gt_per_yr in gigatonnes per year over the "
                 "domain; mean_m_ice_per_yr in metres of ice per year (area-weighted mean); "
                 "period_years in years; area_km2 in km2",
        "sign_convention": "positive is mass gained at the surface (accumulation exceeding "
                           "ablation), the product's own",
        "months": [labels[0], labels[-1]],
        "n_rows": len(rows),
        "domains": [["antarctica", "ice_shelves"]],
        "not_in_the_distribution": [
            "Greenland: the ITS_LIVE Greenland elevation change product carries firn air "
            "content anomalies and no surface mass balance field; no other GEMB output for "
            "Greenland is distributed with ITS_LIVE on AWS",
            "Antarctica, grounded ice sheet: no GEMB surface mass balance field is distributed "
            "with ITS_LIVE on AWS; the rows cover the floating ice shelves",
        ],
        "alternates_not_read": ALTERNATES_NOT_READ,
        "series": {
            "antarctica": {
                "product": attrs.get("title", ""),
                "doi": PRODUCT["doi"],
                "product_version": attrs.get("version", ""),
                "granule": antarctica.name,
                "granule_sha256": sha256(antarctica),
                "source_url": BUCKET + PRODUCT["key"],
                "read_utc": utcnow(),
                "variable": "smb (with smb_err and smb_mean)",
                "variable_source": str(getattr(smb, "source", "")),
                "gemb_version": "GEMB r24739 (the variable's source attribute)",
                "forcing": "3-hourly ERA5 reanalysis, 1979 to 2017, after a relaxation simulation "
                           "(the NSIDC-0792 user guide, section 2.3.1.3)",
                "grid": f"1920 m polar stereographic, EPSG:{epsg}, {len(y)} by {len(x)} cells; "
                        "cell areas from the projection's areal scale; the user guide says the "
                        "GEMB fields were interpolated from a 5 km grid",
                "mask": "the file's ID variable: ice shelf identifiers 1 to 182 (an edited "
                        "MEaSUREs Antarctic Boundaries version 2), land 255; the domain is the "
                        "floating ice shelves only",
                "aggregation": "sum of smb times cell area times the product's ice density "
                               f"({density} kg per m3) over the fixed set of ice shelf cells "
                               "finite in smb at every time step and in smb_mean; the error "
                               "sum runs over the subset of those cells finite in smb_err and "
                               "below its sentinel at each step, and the stamp counts the rest",
                "sampling": "quarterly: one row per product time step, labelled by the calendar "
                            "month of the time value (the user guide calls it the quarter start "
                            "date); period_years is the interval to the next time value",
                "time_coverage": [date_of(t, steps[0]), date_of(t, steps[-1])],
                "months": [labels[0], labels[-1]],
                "n_steps": len(steps),
                "empty_steps_skipped": empty,
                "cells": {"ice_shelves": int(ok.sum())},
                "area_km2": {"ice_shelves": round(total_area, 2)},
                "cells_without_error_max": max(no_error),
                "uncertainty_basis": "the sum of the product's smb_err times cell area times "
                                     "the density over the cells whose error is finite and below "
                                     "the 9999 sentinel, the cell errors treated as fully "
                                     "correlated (an upper bound)",
                "global_attributes": attrs,
            }
        },
    }
    ds.close()
    if stamp_out:
        stamp_out.write_text(json.dumps(stamp, indent=2) + "\n", encoding="utf-8")
    print(f"{out.name}: {len(rows)} rows, {labels[0]} to {labels[-1]}, antarctica/ice_shelves")


def write_toy(p: Path):
    """A 3-quarter, 3 by 3 EPSG:3031 grid at the standard parallel, where
    a cell is 1920 m square on the ground: three shelf 1 cells at 1 m of
    ice per year, three shelf 2 cells at -0.5 m per year, errors 0.2 m per
    year with one 9999 sentinel in the first quarter, the third quarter
    empty, two land cells and one ocean cell."""
    ds = nc.Dataset(p, "w")
    ds.title = "toy antarctica"; ds.version = "1.0"
    ds.createDimension("x", 3); ds.createDimension("y", 3); ds.createDimension("time", 3)
    fwd = Transformer.from_crs(4326, CRS.from_epsg(3031), always_xy=True)
    x0, y0 = fwd.transform(0.0, -71.0)
    x = ds.createVariable("x", "f8", ("x",)); y = ds.createVariable("y", "f8", ("y",))
    x[:] = x0 + 1920.0 * np.arange(3); y[:] = y0 + 1920.0 * np.arange(3)
    t = ds.createVariable("time", "f8", ("time",)); t.units = "days since 1950-01-01"
    t[:] = [15416.0, 15507.0, 15599.0]             # 1992-03-17, 06-16 and 09-16
    mp = ds.createVariable("mapping", "S1", ()); mp.spatial_epsg = "3031.0"
    ident = ds.createVariable("ID", "u1", ("y", "x"))
    ident[:] = [[1, 1, 255], [2, 2, 0], [1, 2, 255]]
    smb = ds.createVariable("smb", "f4", ("time", "y", "x"), fill_value=-32767.0)
    smb.source = "GEMB toy"; smb.density = "917.0"
    err = ds.createVariable("smb_err", "f4", ("time", "y", "x"), fill_value=-32767.0)
    sm = ds.createVariable("smb_mean", "f4", ("y", "x"), fill_value=-32767.0)
    s = np.where(ident[:] == 1, 1.0, np.where(ident[:] == 2, -0.5, np.nan))
    for i in range(2):
        smb[i] = np.where(np.isfinite(s), s, -32767.0)
        e = np.where(np.isfinite(s), 0.2, -32767.0)
        if i == 0:
            e[0, 0] = 9999.0
        err[i] = e
    smb[2] = -32767.0; err[2] = -32767.0
    sm[:] = np.where(np.isfinite(s), s, -32767.0)
    ds.close()


def selftest():
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        p = td / "toy.nc"; write_toy(p)
        out, st = td / "smb.csv", td / "smb-stamp.json"
        run(p, out, st)
        rows = list(csv.DictReader(out.open()))
        assert [r["month"] for r in rows] == ["1992-03", "1992-06"], rows
        assert all(r["n_cells"] == "6" and r["sampling"] == "quarterly" for r in rows), rows
        # Six cells of 1.92 km squared at the standard parallel (the areal
        # scale drifts by a part in ten thousand across the toy grid): net
        # 3 * 1.0 - 3 * 0.5 = 1.5 m per year times the cell area times
        # 917 kg per m3, in Gt per year.
        cell = 1.92 ** 2                            # km2 at the standard parallel
        want = 1.5 * cell * 1e6 * 917.0 / 1e12
        want_err = [5 * 0.2 * cell * 1e6 * 917.0 / 1e12,     # the sentinel cell carries no error
                    6 * 0.2 * cell * 1e6 * 917.0 / 1e12]
        got = float(rows[0]["value_gt_per_yr"])
        got_err = [float(r["uncertainty_gt_per_yr"]) for r in rows]
        assert abs(got - want) < 1e-3 * want, (got, want)
        assert all(abs(g - w) < 1e-3 * w for g, w in zip(got_err, want_err)), (got_err, want_err)
        mean = float(rows[0]["mean_m_ice_per_yr"])
        assert abs(mean - 0.25) < 1e-3, mean
        per = [float(r["period_years"]) for r in rows]
        assert abs(per[0] - 91 / 365.25) < 1e-5 and abs(per[1] - 92 / 365.25) < 1e-5, per
        stamp = json.loads(st.read_text())
        ant = stamp["series"]["antarctica"]
        assert stamp["months"] == ["1992-03", "1992-06"] and ant["cells"] == {"ice_shelves": 6}
        assert ant["empty_steps_skipped"] == ["1992-09-16"] and ant["cells_without_error_max"] == 1, ant
        print(f"selftest: {got:.6e} Gt per year vs {want:.6e}, errors {got_err[0]:.6e} and "
              f"{got_err[1]:.6e} vs {want_err[0]:.6e} and {want_err[1]:.6e}, mean {mean:.3f} m of "
              f"ice per year, periods {per[0]:.4f} and {per[1]:.4f} yr, one empty quarter skipped; OK")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--antarctic", type=Path)
    ap.add_argument("--out", type=Path); ap.add_argument("--stamp-out", type=Path)
    ap.add_argument("--fetch-to", type=Path)
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        selftest(); return
    if not (a.antarctic and a.out):
        ap.error("--antarctic and --out are required")
    if not a.antarctic.is_file():
        if not a.fetch_to:
            sys.exit(f"{a.antarctic} does not exist (give --fetch-to DIR to download it)")
        fetch(BUCKET + PRODUCT["key"], a.antarctic)
    run(a.antarctic, a.out, a.stamp_out)


if __name__ == "__main__":
    main()
