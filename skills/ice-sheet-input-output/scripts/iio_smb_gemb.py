#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["numpy==2.2.6", "netCDF4==1.7.2", "pyproj==3.7.1"]
# ///
"""Loader for the input term of the ice sheet input-output balance:
the surface mass balance rate over a stated ice sheet domain, from
NASA's GEMB (Glacier Energy and Mass Balance) output as ITS_LIVE
distributes it, written as the data root's smb.csv.

The input-output method needs the surface mass balance over the
grounded ice sheet, because the discharge it is differenced against
is the flux out of the grounded ice. That is the domain this loader
asks for, and the domain column of every row names the one it got.

What ITS_LIVE distributes. One product file carries a GEMB surface
mass balance field: the Antarctic ice shelf height change and basal
melt product (NSIDC-0792 Version 1, doi 10.5067/SE3XH9RXQWAM), whose
smb variable is masked to the floating ice shelves, identifiers 1 to
182 of its ID variable, and carries no value over grounded ice. The
Greenland elevation change product carries firn air content anomalies
and no surface mass balance field. The result is that no grounded
surface mass balance is in the distribution for either ice sheet, so
a root built from these sources supplies no input term for an
input-output balance and the computation refuses rather than
differencing a shelf accumulation against a grounded discharge. The
loader states that in its stamp rather than in a comment, and the
aggregation below is the one the ice sheet mass balance closure's own
surface mass balance loader uses, so a shelf row written here and a
shelf row written there hold the same number.

What it computes, per time step, over the fixed set of cells inside
the stated mask that are finite in smb at every step and in smb_mean:

  1. The true ground area of every grid cell from the projection's
     areal scale (pyproj get_factors).
  2. The surface mass balance rate over the domain in gigatonnes per
     year (value_gt_per_yr): the sum of smb times cell area times the
     product's ice density; and the same rate as an area-weighted
     mean in metres of ice per year (mean_m_ice_per_yr).
  3. The uncertainty in gigatonnes per year: the sum of smb_err times
     cell area times the density over the cells whose error is finite
     and below the 9999 sentinel the product uses where it has none,
     the cell errors treated as fully correlated (an upper bound);
     the count of cells without an error is recorded in the stamp.
  4. The length of each step in years (period_years) from the
     interval to the next time value, so the mass over a step is the
     rate times the period, left to the reader.
  5. The calendar month of the time value as the row label. A step
     with no finite value inside the mask is a non-sample, skipped
     and listed, never filled; a second step in a month already taken
     is refused, never averaged.

Sign convention: positive is mass gained at the surface (accumulation
exceeding ablation), the product's own.

Usage:
  iio_smb_gemb.py --product FILE.nc --ice-sheet antarctica --domain ice_shelves
      --mask-variable ID --mask-range 1:182 --out smb.csv
      [--stamp-out smb-stamp.json] [--epsg N] [--sampling WORD] [--fetch-to DIR]
  iio_smb_gemb.py --selftest
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
KNOWN = {
    "antarctica/ice_shelves": {
        "key": "height_change/Antarctica/Floating/ANT_G1920V01_IceShelfMelt.nc",
        "doi": "10.5067/SE3XH9RXQWAM",
        "short_name": "NSIDC-0792",
        "epsg": 3031,
        "mask_variable": "ID",
        "mask_range": (1, 182),
        "sampling": "quarterly",
        "floating": True,
    },
}
NOT_IN_THE_DISTRIBUTION = [
    "Greenland, grounded ice sheet and peripheral glaciers: the ITS_LIVE Greenland elevation "
    "change product carries firn air content anomalies (dfac_gemb, dfac_gsfc) and no surface "
    "mass balance field, and no other GEMB output for Greenland is distributed with ITS_LIVE "
    "on AWS",
    "Antarctica, grounded ice sheet: no GEMB surface mass balance field is distributed with "
    "ITS_LIVE on AWS; the only field is masked to the floating ice shelves",
]
ALTERNATES_NOT_READ = [
    "RACMO2 (IMAU regional climate model surface mass balance output): not read; it is not "
    "distributed by a NASA archive",
    "MAR (regional climate model surface mass balance output): not read; it is not distributed "
    "by a NASA archive",
    "MERRA-2 (the GES DISC reanalysis): not read; its land surface fields are not an ice sheet "
    "surface mass balance product",
    "the IMBIE basin definitions: not read",
]
CSV_COLUMNS = ["ice_sheet", "domain", "month", "value_gt_per_yr", "uncertainty_gt_per_yr",
               "mean_m_ice_per_yr", "period_years", "area_km2", "n_cells", "sampling"]
ERROR_SENTINEL = 9000.0


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
    with urllib.request.urlopen(url, timeout=300) as r, dest.open("wb") as f:
        for chunk in iter(lambda: r.read(1 << 20), b""):
            f.write(chunk)


def cell_area_km2(epsg: int, x, y) -> np.ndarray:
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


def period_years(t) -> list:
    days = np.asarray(t[:], float)
    d = np.diff(days)
    if len(d) == 0:
        return [float("nan")]
    return [float(v) / 365.25 for v in np.r_[d, np.median(d)]]


def gigatonnes_per_year(rate_m_ice, area_km2, ok, density: float) -> float:
    return float(np.sum(rate_m_ice[ok] * area_km2[ok])) * 1e6 * density / 1e12


def run(product: Path, ice_sheet: str, domain: str, mask_variable: str, mask_range,
        out: Path, stamp_out: Path | None, epsg_expected: int | None, sampling: str):
    ds = nc.Dataset(product)
    attrs = {a: str(getattr(ds, a)) for a in ds.ncattrs()}
    if "smb" not in ds.variables:
        sys.exit(f"{product.name} carries no smb variable (it holds "
                 f"{sorted(ds.variables)}); this product distributes no surface mass balance "
                 "field and no smb.csv is written from it")
    epsg = int(float(getattr(ds["mapping"], "spatial_epsg", epsg_expected or 0))) \
        if "mapping" in ds.variables else (epsg_expected or 0)
    if epsg_expected and epsg != epsg_expected:
        sys.exit(f"{product.name}: spatial_epsg {epsg} is not the expected {epsg_expected}")
    x, y, t = ds["x"][:], ds["y"][:], ds["time"]
    n = len(t)
    area = cell_area_km2(epsg, x, y)
    ident = np.asarray(ds[mask_variable][:]).astype(int)
    lo, hi = mask_range
    inside = (ident >= lo) & (ident <= hi)
    smb, err = ds["smb"], ds["smb_err"]
    smean = field2d(ds["smb_mean"])
    density = float(getattr(smb, "density", 917.0))
    steps = [i for i in range(n) if np.isfinite(field(smb, i)[inside]).any()]
    if not steps:
        sys.exit(f"{product.name}: no time step carries a finite smb inside "
                 f"{mask_variable} {lo} to {hi}; nothing is written")
    empty = [date_of(t, i) for i in range(n) if i not in steps]
    ok = inside.copy()
    for i in steps:
        ok &= np.isfinite(field(smb, i))
    ok &= np.isfinite(smean)
    total_area = float(area[ok].sum())
    periods = period_years(t)
    months, rows, no_error = {}, [], []
    for i in steps:
        label = month_of(t, i)
        if label in months:
            sys.exit(f"{product.name}: two time steps ({months[label]} and {i}) fall in {label}; "
                     "the loader does not average steps")
        months[label] = i
        s = field(smb, i)
        e = field(err, i)
        valid = ok & np.isfinite(e) & (e < ERROR_SENTINEL)
        no_error.append(int(ok.sum() - valid.sum()))
        rows.append([ice_sheet, domain, label,
                     f"{gigatonnes_per_year(s, area, ok, density):.6f}",
                     f"{gigatonnes_per_year(e, area, valid, density):.6f}",
                     f"{float(np.sum(s[ok] * area[ok]) / total_area):.6f}",
                     f"{periods[i]:.6f}", f"{total_area:.2f}", int(ok.sum()), sampling])
    labels = sorted(months)
    with out.open("w", encoding="utf-8", newline="") as f:
        wr = csv.writer(f)
        wr.writerow(CSV_COLUMNS)
        wr.writerows(rows)
    known = KNOWN.get(f"{ice_sheet}/{domain}", {})
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
        "domains": [[ice_sheet, domain]],
        "grounded_domains": [],
        "grounded_note": "this loader wrote no grounded ice sheet domain: the domain above is "
                         + ("the floating ice shelves, and an input-output balance differences a "
                            "grounded discharge, so it is not the input term that method needs"
                            if known.get("floating") else "the one the mask named"),
        "not_in_the_distribution": NOT_IN_THE_DISTRIBUTION,
        "alternates_not_read": ALTERNATES_NOT_READ,
        "series": {
            ice_sheet: {
                "product": attrs.get("title", ""),
                "short_name": known.get("short_name", ""),
                "doi": known.get("doi", ""),
                "product_version": attrs.get("version", ""),
                "granule": product.name,
                "granule_sha256": sha256(product),
                "source_url": BUCKET + known["key"] if known.get("key") else "",
                "read_utc": utcnow(),
                "variable": "smb (with smb_err and smb_mean)",
                "variable_source": str(getattr(smb, "source", "")),
                "gemb_version": str(getattr(smb, "source", "")) or "stated by the product",
                "forcing": "3-hourly ERA5 reanalysis, 1979 to 2017, after a relaxation "
                           "simulation (the NSIDC-0792 user guide, section 2.3.1.3)"
                           if known.get("short_name") == "NSIDC-0792" else "stated by the product",
                "grid": f"EPSG:{epsg}, {len(y)} by {len(x)} cells; cell areas from the "
                        "projection's areal scale",
                "mask": f"the file's {mask_variable} variable, values {lo} to {hi}; the domain "
                        f"is {domain}",
                "aggregation": "sum of smb times cell area times the product's ice density "
                               f"({density} kg per m3) over the fixed set of cells inside the "
                               "mask finite in smb at every time step and in smb_mean; the "
                               "error sum runs over the subset of those cells finite in smb_err "
                               "and below its sentinel at each step, and the stamp counts the rest",
                "sampling": f"{sampling}: one row per product time step, labelled by the "
                            "calendar month of the time value; period_years is the interval to "
                            "the next time value",
                "time_coverage": [date_of(t, steps[0]), date_of(t, steps[-1])],
                "months": [labels[0], labels[-1]],
                "n_steps": len(steps),
                "empty_steps_skipped": empty,
                "cells": {domain: int(ok.sum())},
                "area_km2": {domain: round(total_area, 2)},
                "cells_without_error_max": max(no_error),
                "uncertainty_basis": "the sum of the product's smb_err times cell area times "
                                     "the density over the cells whose error is finite and "
                                     "below the 9999 sentinel, the cell errors treated as fully "
                                     "correlated (an upper bound)",
                "global_attributes": attrs,
            }
        },
    }
    ds.close()
    if stamp_out:
        stamp_out.write_text(json.dumps(stamp, indent=2) + "\n", encoding="utf-8")
    print(f"{out.name}: {len(rows)} rows, {labels[0]} to {labels[-1]}, {ice_sheet}/{domain}")
    return stamp


# ---- selftest

def write_toy(p: Path):
    """A 3-step, 3 by 3 EPSG:3031 grid at the standard parallel, where a
    cell is 1920 m square on the ground: three cells of domain 1 at 1 m
    of ice per year, three of domain 2 at minus 0.5, errors of 0.2 with
    one sentinel in the first step, an empty third step, two cells of
    domain 255 and one of 0."""
    ds = nc.Dataset(p, "w")
    ds.title = "toy ice shelf product"; ds.version = "1.0"
    ds.createDimension("x", 3); ds.createDimension("y", 3); ds.createDimension("time", 3)
    fwd = Transformer.from_crs(4326, CRS.from_epsg(3031), always_xy=True)
    x0, y0 = fwd.transform(0.0, -71.0)
    x = ds.createVariable("x", "f8", ("x",)); y = ds.createVariable("y", "f8", ("y",))
    x[:] = x0 + 1920.0 * np.arange(3); y[:] = y0 + 1920.0 * np.arange(3)
    t = ds.createVariable("time", "f8", ("time",)); t.units = "days since 1950-01-01"
    t[:] = [15416.0, 15507.0, 15599.0]
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


def write_toy_without_smb(p: Path):
    ds = nc.Dataset(p, "w")
    ds.createDimension("x", 2); ds.createDimension("y", 2)
    ds.createVariable("dfac_gemb", "f4", ("y", "x"))
    ds.close()


def selftest():
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        p = td / "toy.nc"; write_toy(p)
        out, st = td / "smb.csv", td / "smb-stamp.json"
        stamp = run(p, "antarctica", "ice_shelves", "ID", (1, 182), out, st, 3031, "quarterly")
        rows = list(csv.DictReader(out.open()))
        assert [r["month"] for r in rows] == ["1992-03", "1992-06"], rows
        assert all(r["n_cells"] == "6" and r["sampling"] == "quarterly" for r in rows), rows
        cell = 1.92 ** 2
        want = 1.5 * cell * 1e6 * 917.0 / 1e12
        want_err = [5 * 0.2 * cell * 1e6 * 917.0 / 1e12, 6 * 0.2 * cell * 1e6 * 917.0 / 1e12]
        got = float(rows[0]["value_gt_per_yr"])
        got_err = [float(r["uncertainty_gt_per_yr"]) for r in rows]
        assert abs(got - want) < 1e-3 * want, (got, want)
        assert all(abs(g - w) < 1e-3 * w for g, w in zip(got_err, want_err)), (got_err, want_err)
        assert abs(float(rows[0]["mean_m_ice_per_yr"]) - 0.25) < 1e-3
        per = [float(r["period_years"]) for r in rows]
        assert abs(per[0] - 91 / 365.25) < 1e-5 and abs(per[1] - 92 / 365.25) < 1e-5, per
        assert stamp["grounded_domains"] == [] and stamp["domains"] == [["antarctica", "ice_shelves"]]
        assert stamp["series"]["antarctica"]["empty_steps_skipped"] == ["1992-09-16"]
        assert stamp["series"]["antarctica"]["cells_without_error_max"] == 1
        # a second domain of the same file is a separate, correctly labelled run
        out2 = td / "smb-2.csv"
        run(p, "antarctica", "shelf_two", "ID", (2, 2), out2, None, 3031, "quarterly")
        r2 = list(csv.DictReader(out2.open()))
        want2 = -0.5 * 3 * cell * 1e6 * 917.0 / 1e12
        assert abs(float(r2[0]["value_gt_per_yr"]) - want2) < 1e-3 * abs(want2), r2[0]
        # a product with no smb variable is refused, not written empty
        q = td / "nosmb.nc"; write_toy_without_smb(q)
        try:
            run(q, "greenland", "ice_sheet", "ID", (1, 1), td / "x.csv", None, None, "monthly")
            raise AssertionError("a product without an smb variable was not refused")
        except SystemExit as e:
            assert "no smb variable" in str(e), e
        print(f"iio_smb_gemb selftest: {got:.6e} Gt per year vs {want:.6e}, errors "
              f"{got_err[0]:.6e} and {got_err[1]:.6e}, one empty step skipped, a second domain "
              f"aggregated alone, a product without smb refused; OK")


def parse_range(spec: str):
    a, _, b = spec.partition(":")
    return (int(a), int(b or a))


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--product", type=Path)
    ap.add_argument("--ice-sheet")
    ap.add_argument("--domain")
    ap.add_argument("--mask-variable", default="ID")
    ap.add_argument("--mask-range", default="1:182", help="LO:HI of the mask variable")
    ap.add_argument("--epsg", type=int, default=None)
    ap.add_argument("--sampling", default="quarterly")
    ap.add_argument("--out", type=Path)
    ap.add_argument("--stamp-out", type=Path)
    ap.add_argument("--fetch-to", type=Path)
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        selftest(); return
    if not (a.product and a.ice_sheet and a.domain and a.out):
        ap.error("--product, --ice-sheet, --domain and --out are required")
    known = KNOWN.get(f"{a.ice_sheet}/{a.domain}", {})
    if not a.product.is_file():
        if not (a.fetch_to and known.get("key")):
            sys.exit(f"{a.product} does not exist (give --fetch-to DIR for a known product)")
        fetch(BUCKET + known["key"], a.product)
    run(a.product, a.ice_sheet, a.domain, a.mask_variable, parse_range(a.mask_range), a.out,
        a.stamp_out, a.epsg or known.get("epsg"), a.sampling)


if __name__ == "__main__":
    main()
