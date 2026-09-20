#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["numpy==2.2.6", "netCDF4==1.7.2", "pyproj==3.7.1"]
# ///
"""Loader for the mass term of the ice sheet mass balance closure: the
JPL GRACE and GRACE-FO mascon solution summed over one ice sheet's
mascons per solution month, in gigatonnes, written as the data root's
mass.csv (one row per ice sheet and month).

What it reads: the CRI-filtered mascon grid granule (RL06.3Mv04,
doi 10.5067/TEMSC-3JC634, the podaac bundle's dataset concept), the
same file the sea level budget's mass loader reads. Its lwe_thickness
is centimetres of equivalent water thickness against the product's
2004 to 2009 baseline on a 0.5 degree grid that represents 3 degree
mascons; land_mask is the CRI partition (1 land, 0 ocean); uncertainty
is one 1-sigma value per mascon, not per cell (the variable's comment).

What it computes, per ice sheet and solution epoch:

  1. The ice sheet's mascon set, a stated rule per ice sheet.
     Greenland: the product's land mascons whose land area is covered
     by Greenland ice for at least --min-ice-fraction of it (default
     0.25), the ice taken from the ITS_LIVE Greenland elevation change
     product's mask (ice sheet 1 and peripheral glaciers 2, the file
     the firn loader reads) binned onto the 0.5 degree grid with true
     cell areas. A mascon that straddles Nares Strait or Denmark
     Strait cannot be split by any rule, so the stamp lists every
     selected mascon with its ice fraction, the land mascons that were
     excluded although they carry some Greenland ice, and the trend
     the series would have under two other thresholds.
     Antarctica: every land mascon whose centroid lies south of 60 S;
     the CRI land mask marks the floating ice shelves as land, so the
     sum spans the grounded sheet and the shelves together, and the
     stamp says so (a shelf in hydrostatic balance carries no gravity
     signal, so the shelf part of the sum is the product's own
     leakage bookkeeping, not an ice mass).
  2. The mass anomaly in gigatonnes: the sum over the land cells of
     the selected mascons of lwe_thickness times the cell's true area
     (1 cm of water over 1 km2 is 1e-5 Gt).
  3. The formal error: one sigma per mascon times the mascon's land
     area, combined in quadrature over the selected mascons, treated
     as independent; a floor where mascon errors correlate, and the
     stamp says so. Leakage from the surrounding ocean and land is
     not in it; the provider's own ice sheet series carries a
     leakage-aware error, and the cross-check below records it.
  4. The calendar month of each solution from the midpoint of its
     time_bounds, with the product's April 2015 pair handled as the
     sea level budget loader does (the later solution goes to the
     following month when its span reaches into it; any other
     collision is refused). Months the product lacks are absent from
     the file, never filled.
  5. A cross-check against the provider's Greenland or Antarctica
     mass time series (--provider-series, the podaac text file of the
     same release): over the common months, the linear trend of both
     series and the standard deviation of their difference after the
     mean offset is removed; recorded in the stamp, never used to
     alter the sum.

The GIA model, the low-degree replacements, the reference frame and
the smoothing are the product's, stated in the stamp from the podaac
bundle's concepts and the release note, nothing re-applied.

Usage:
  isb_mass_mascons.py --granule FILE.nc --ice-mask GREENLAND.nc --out mass.csv
      [--stamp-out mass-stamp.json] [--provider-series greenland_mass.txt ...]
      [--min-ice-fraction F] [--fetch-to DIR]
  --fetch-to DIR   download the granule from the archive into DIR when the given
                   path does not exist; the archive needs an Earthdata Login
                   bearer token, read from EARTHDATA_TOKEN and sent as a header only
  --selftest       a synthetic two-mascon world with a toy ice mask
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
from pyproj import CRS, Proj, Transformer

EARTH_RADIUS_KM = 6371.0
CM_KM2_TO_GT = 1e-5          # 1 cm of water over 1 km2 is 1e7 kg, 1e-5 Gt
ARCHIVE = ("https://archive.podaac.earthdata.nasa.gov/podaac-ops-cumulus-protected/"
           "TELLUS_GRAC-GRFO_MASCON_CRI_GRID_RL06.3_V4/")
GRANULE = "GRCTellus.JPL.200204_202607.GLO.RL06.3M.MSCNv04CRI.nc"
ICE_MASK_URL = ("https://its-live-data.s3.amazonaws.com/height_change/Greenland/"
                "Greenland_G1920V01_IceSheetGlacierIceHeight.nc")
DEFAULT_MIN_ICE_FRACTION = 0.25
SENSITIVITY_FRACTIONS = (0.05, 0.5)
ANTARCTIC_LATITUDE = -60.0
CSV_COLUMNS = ["ice_sheet", "domain", "month", "value_gt", "uncertainty_gt",
               "land_area_km2", "n_mascons", "sampling", "epoch_start", "epoch_end"]
BOOKKEEPING = {
    "gia": "ICE-6G_D (Peltier and others 2018) subtracted by the product before the CRI "
           "filter and from the released fields (the release note; the podaac bundle's "
           "GIA gotcha); nothing re-applied. Over Antarctica the GIA model is the "
           "largest systematic of a gravimetric mass balance and is not in the formal "
           "error below",
    "low_degree": "C20 and C30 from TN-14 version 3 across the whole series, degree 1 from "
                  "JPL's mascon-consistent geocenter; nothing re-applied (the release note; "
                  "the podaac bundle's low-degree gotcha)",
    "reference_frame": "centre of figure restored through JPL's mascon-consistent geocenter "
                       "(degree 1 computed with the mascon field as background, the release "
                       "note)",
    "effective_smoothing": "3 degree spherical-cap mascons on a 0.5 degree grid; the sum runs "
                           "over whole mascons, so signal from the ice-free land and the "
                           "ocean inside a selected mascon, and ice signal in an excluded "
                           "neighbour, is leakage the product's CRI filter reduces and does "
                           "not remove (the podaac bundle's coastal-leakage gotcha)",
    "gad": "the GAD de-aliasing signal is restored over the ocean part of the mascons only "
           "(the release note); the land cells summed here carry none",
    "elastic_and_hydrology": "no elastic rebound or terrestrial hydrology correction is "
                             "applied to the mascons: the product's land mascon value is "
                             "the full surface mass anomaly",
}


def bare_doi(text: str) -> str:
    """The bare DOI of an attribute that may carry a resolver prefix."""
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
    """Stream a product file to dest. The archive answers 401 without an
    Earthdata Login; the bearer token in EARTHDATA_TOKEN, when set, goes
    in the Authorization header and nowhere else."""
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


def cell_areas_km2(lat_bounds: np.ndarray, lon_bounds: np.ndarray) -> np.ndarray:
    """Spherical cell areas from bounds, shape (nlat, nlon)."""
    s = np.sin(np.deg2rad(lat_bounds))
    dlat = np.abs(s[:, 1] - s[:, 0])
    dlon = np.deg2rad(np.abs(lon_bounds[:, 1] - lon_bounds[:, 0]))
    return EARTH_RADIUS_KM ** 2 * dlat[:, None] * dlon[None, :]


def next_month(label: str) -> str:
    y, m = int(label[:4]), int(label[5:])
    return f"{y + m // 12:04d}-{m % 12 + 1:02d}"


def decimal_year_month(t: float) -> str:
    year = int(np.floor(t))
    month = int(np.floor((t - year) * 12.0)) + 1
    return f"{year:04d}-{min(month, 12):02d}"


# ---- the ice mask on the mascon grid

def projected_cell_area_km2(epsg: int, x: np.ndarray, y: np.ndarray):
    """True ground area of every cell of a projected grid and the
    latitude and longitude of its centre (the firn loader's method)."""
    crs = CRS.from_epsg(epsg)
    dx, dy = float(abs(x[1] - x[0])), float(abs(y[1] - y[0]))
    X, Y = np.meshgrid(np.asarray(x, float), np.asarray(y, float))
    lon, lat = Transformer.from_crs(crs, 4326, always_xy=True).transform(X, Y)
    f = Proj(crs).get_factors(lon, lat)
    return (dx * dy / 1e6) / np.asarray(f.areal_scale, float), lat, lon


def ice_area_on_grid(mask_path: Path, lat_b: np.ndarray, lon_b: np.ndarray) -> tuple[np.ndarray, dict]:
    """Greenland ice area (km2) in every cell of the mascon grid: the
    ITS_LIVE mask's ice cells (1 and 2) binned by the latitude and
    longitude of their centres into the cells whose bounds hold them,
    each with its true area."""
    ds = nc.Dataset(mask_path)
    attrs = {a: str(getattr(ds, a)) for a in ds.ncattrs()}
    epsg = int(float(attrs.get("epsg_number", 3413)))
    x, y = ds["x"][:], ds["y"][:]
    mask = np.asarray(ds["mask"][:]).astype(int)
    ds.close()
    area, clat, clon = projected_cell_area_km2(epsg, x, y)
    ice = (mask == 1) | (mask == 2)
    plat, plon = clat[ice], clon[ice] % 360.0
    ilat = np.searchsorted(lat_b[:, 0], plat, side="right") - 1
    ilon = np.searchsorted(lon_b[:, 0], plon, side="right") - 1
    ok = (ilat >= 0) & (ilon >= 0)
    ok[ok] &= (plat[ok] < lat_b[ilat[ok], 1]) & (plon[ok] < lon_b[ilon[ok], 1])
    grid = np.zeros((len(lat_b), len(lon_b)))
    np.add.at(grid, (ilat[ok], ilon[ok]), area[ice][ok])
    info = {"file": mask_path.name, "file_sha256": sha256(mask_path), "epsg": epsg,
            "ice_cells": int(ice.sum()), "ice_area_km2": round(float(area[ice].sum()), 2),
            "title": attrs.get("title", ""), "doi": bare_doi(attrs.get("doi", ""))}
    return grid, info


# ---- the mascon selection

def mascon_table(mid: np.ndarray, land: np.ndarray, area: np.ndarray, lat2d, lon2d, ice_area=None):
    """Per mascon: cells, land area, centroid, and the ice area when a
    mask is given; keyed by mascon id."""
    table = {}
    for i in np.unique(mid):
        m = mid == i
        land_area = float((area * land)[m].sum())
        row = {"cells": int(m.sum()), "land_cells": int(land[m].sum()),
               "land_area_km2": round(land_area, 1),
               "centroid_lat": round(float(lat2d[m].mean()), 2),
               "centroid_lon": round(float(lon2d[m].mean()), 2)}
        if ice_area is not None:
            ia = float(ice_area[m].sum())
            row["ice_area_km2"] = round(ia, 1)
            row["ice_fraction_of_land"] = round(ia / land_area, 4) if land_area > 0 else 0.0
        table[int(i)] = row
    return table


def select(ice_sheet: str, table: dict, min_fraction: float):
    if ice_sheet == "greenland":
        return sorted(i for i, r in table.items()
                      if r["land_cells"] > 0 and r.get("ice_fraction_of_land", 0.0) >= min_fraction)
    return sorted(i for i, r in table.items()
                  if r["land_cells"] > 0 and r["centroid_lat"] < ANTARCTIC_LATITUDE)


def sum_mascons(lwe, unc, mid, land, area, ids):
    """Mass (Gt) over the land cells of the mascons in ids and the
    formal error (Gt) from one sigma per mascon over its land area."""
    inside = np.isin(mid, ids) & (land == 1) & np.isfinite(lwe)
    w = area * inside
    mass = float(np.sum(lwe * w)) * CM_KM2_TO_GT
    err2 = 0.0
    for i in ids:
        m = inside & (mid == i)
        if not m.any():
            continue
        err2 += (float(unc[m][0]) * float(area[m].sum()) * CM_KM2_TO_GT) ** 2
    return mass, float(np.sqrt(err2)), float(w.sum())


def ols_trend_per_year(months: list[str], values: list[float]) -> float:
    t = np.array([int(m[:4]) + (int(m[5:]) - 0.5) / 12.0 for m in months])
    v = np.asarray(values, float)
    return float(np.polyfit(t, v, 1)[0])


def read_provider_series(path: Path) -> dict:
    """The podaac ice sheet mass text file: month, Gt, one sigma."""
    rows, header = {}, []
    with path.open(encoding="utf-8") as f:
        for line in f:
            if line.startswith("HDR"):
                header.append(line.rstrip())
                continue
            parts = line.split()
            if len(parts) < 3:
                continue
            label = decimal_year_month(float(parts[0]))
            if label in rows:
                label = next_month(label)
            rows[label] = (float(parts[1]), float(parts[2]))
    trend_line = next((h for h in header if "Trend" in h), "")
    return {"file": path.name, "file_sha256": sha256(path), "rows": rows,
            "header_trend": trend_line.replace("HDR", "").strip(), "n": len(rows)}


def cross_check(rows: list, provider: dict) -> dict:
    mine = {r[2]: r[3] for r in rows}
    common = sorted(set(mine) & set(provider["rows"]))
    if len(common) < 12:
        return {"file": provider["file"], "file_sha256": provider["file_sha256"],
                "common_months": len(common), "note": "too few common months to compare"}
    a = np.array([mine[m] for m in common])
    b = np.array([provider["rows"][m][0] for m in common])
    d = a - b
    return {
        "file": provider["file"], "file_sha256": provider["file_sha256"],
        "provider_header_trend": provider["header_trend"],
        "common_months": len(common), "first": common[0], "last": common[-1],
        "trend_gt_per_yr": {"this_loader": round(ols_trend_per_year(common, list(a)), 3),
                            "provider": round(ols_trend_per_year(common, list(b)), 3)},
        "difference_after_mean_offset_gt": {"std": round(float(np.std(d - d.mean(), ddof=1)), 3),
                                            "max_abs": round(float(np.max(np.abs(d - d.mean()))), 3)},
        "provider_one_sigma_gt": {"median": round(float(np.median([provider["rows"][m][1] for m in common])), 3)},
        "rule": "the provider's series is read for this comparison only; the sum above is "
                "never adjusted to it. Its monthly uncertainty includes leakage (its header), "
                "the formal error here does not",
    }


# ---- the run

def run(granule: Path, out: Path, stamp_out: Path | None, ice_mask: Path | None,
        provider_series: list[Path], min_fraction: float, ice_sheets: tuple[str, ...]):
    ds = nc.Dataset(granule)
    attrs = {a: str(getattr(ds, a)) for a in ds.ncattrs()}
    t = ds["time"]
    tb = np.asarray(ds["time_bounds"][:], dtype=float)
    units, cal = t.units, getattr(t, "calendar", "standard")
    lat, lon = np.asarray(ds["lat"][:], float), np.asarray(ds["lon"][:], float)
    lat_b = np.asarray(ds["lat_bounds"][:], float)
    lon_b = np.asarray(ds["lon_bounds"][:], float)
    area = cell_areas_km2(lat_b, lon_b)
    land = np.asarray(ds["land_mask"][:], float)
    mid = np.asarray(ds["mascon_ID"][:], float)
    lat2d, lon2d = np.meshgrid(lat, lon, indexing="ij")
    ice_grid, ice_info = (None, None)
    if "greenland" in ice_sheets:
        if ice_mask is None:
            sys.exit("--ice-mask (the ITS_LIVE Greenland product) is required for the Greenland sum")
        ice_grid, ice_info = ice_area_on_grid(ice_mask, lat_b, lon_b)
    table = mascon_table(mid, land, area, lat2d, lon2d, ice_grid)
    selections = {s: select(s, table, min_fraction) for s in ice_sheets}
    for s, ids in selections.items():
        print(f"  {s}: {len(ids)} mascons, land area "
              f"{sum(table[i]['land_area_km2'] for i in ids):.0f} km2", file=sys.stderr)
        if not ids:
            sys.exit(f"no mascon selected for {s}")

    n = len(t)
    rows, months_seen, assignments = [], {}, []
    for i in range(n):
        mid_t = 0.5 * (tb[i, 0] + tb[i, 1])
        d = nc.num2date(mid_t, units, cal)
        label = f"{d.year:04d}-{d.month:02d}"
        start = nc.num2date(tb[i, 0], units, cal)
        end = nc.num2date(tb[i, 1], units, cal)
        if label in months_seen:
            following = next_month(label)
            if f"{end.year:04d}-{end.month:02d}" == following and following not in months_seen:
                assignments.append({"epoch": i, "midpoint_month": label, "assigned": following,
                                    "span": [f"{start:%Y-%m-%d}", f"{end:%Y-%m-%d}"],
                                    "reason": "midpoint month already taken by the previous "
                                              "solution; the span reaches into the following "
                                              "month, which the product's month list labels it"})
                label = following
            else:
                sys.exit(f"two solutions fall in {label} (epochs {months_seen[label]} and {i}) "
                         "and the later one does not reach into a free following month; "
                         "the loader does not average solutions")
        months_seen[label] = i
        lwe = np.ma.filled(np.ma.masked_invalid(ds["lwe_thickness"][i]), np.nan).astype(float)
        unc = np.ma.filled(np.ma.masked_invalid(ds["uncertainty"][i]), np.nan).astype(float)
        for s, ids in selections.items():
            mass, err, land_area = sum_mascons(lwe, unc, mid, land, area, ids)
            rows.append([s, "land_mascons", label, mass, err, land_area, len(ids), "monthly",
                         f"{start:%Y-%m-%d}", f"{end:%Y-%m-%d}"])
    ds.close()
    rows.sort(key=lambda r: (r[0], r[2]))
    with out.open("w", encoding="utf-8", newline="") as f:
        wr = csv.writer(f)
        wr.writerow(CSV_COLUMNS)
        for r in rows:
            wr.writerow([r[0], r[1], r[2], f"{r[3]:.6f}", f"{r[4]:.6f}", f"{r[5]:.1f}",
                         r[6], r[7], r[8], r[9]])
    labels = sorted(months_seen)
    series = {}
    for s, ids in selections.items():
        mine = [r for r in rows if r[0] == s]
        entry = {
            "domain": "land_mascons",
            "rule": ("the product's land mascons whose land area is covered by Greenland ice "
                     f"(the ITS_LIVE mask, ice sheet and peripheral glaciers) for at least "
                     f"{min_fraction} of it" if s == "greenland" else
                     f"every land mascon whose centroid lies south of {abs(ANTARCTIC_LATITUDE):.0f} S; "
                     "the CRI land mask marks the floating ice shelves as land, so the sum spans "
                     "the grounded sheet and the shelves together"),
            "n_mascons": len(ids),
            "land_area_km2": round(sum(table[i]["land_area_km2"] for i in ids), 1),
            "mascons": {str(i): table[i] for i in ids},
            "trend_gt_per_yr_full_series": round(ols_trend_per_year([r[2] for r in mine], [r[3] for r in mine]), 3),
        }
        if s == "greenland":
            entry["ice_mask"] = {**ice_info, "source_url": ICE_MASK_URL,
                                 "ice_area_in_selected_mascons_km2": round(sum(table[i]["ice_area_km2"] for i in ids), 1)}
            entry["excluded_land_mascons_with_greenland_ice"] = {
                str(i): table[i] for i in sorted(table) if table[i]["land_cells"] > 0
                and 0.0 < table[i].get("ice_fraction_of_land", 0.0) < min_fraction}
            entry["selection_sensitivity"] = {}
            for frac in SENSITIVITY_FRACTIONS:
                alt = select(s, table, frac)
                # the alternative sums are formed from the rows already read
                # only when the set is the same; otherwise re-read below
                entry["selection_sensitivity"][str(frac)] = {"n_mascons": len(alt), "mascons": alt}
        series[s] = entry
    # sensitivity sums need a second pass over the epochs for the other sets
    if "greenland" in selections:
        alt_sets = {frac: select("greenland", table, frac) for frac in SENSITIVITY_FRACTIONS}
        ds = nc.Dataset(granule)
        alt_rows = {frac: [] for frac in alt_sets}
        for label, i in sorted(months_seen.items(), key=lambda kv: kv[1]):
            lwe = np.ma.filled(np.ma.masked_invalid(ds["lwe_thickness"][i]), np.nan).astype(float)
            unc = np.ma.filled(np.ma.masked_invalid(ds["uncertainty"][i]), np.nan).astype(float)
            for frac, ids in alt_sets.items():
                if ids:
                    alt_rows[frac].append((label, sum_mascons(lwe, unc, mid, land, area, ids)[0]))
        ds.close()
        for frac, rr in alt_rows.items():
            sens = series["greenland"]["selection_sensitivity"][str(frac)]
            sens["trend_gt_per_yr_full_series"] = (round(ols_trend_per_year([a for a, _ in rr], [b for _, b in rr]), 3)
                                                   if len(rr) > 12 else None)
    checks = {}
    for p in provider_series:
        prov = read_provider_series(p)
        s = "greenland" if "greenland" in p.name.lower() else "antarctica" if "antarctica" in p.name.lower() else None
        if s in selections:
            checks[s] = cross_check([r for r in rows if r[0] == s], prov)
    stamp = {
        "term": "mass",
        "quantity": "surface mass anomaly from the JPL mascon solution summed over one ice "
                    "sheet's land mascons, per solution month",
        "product": attrs.get("title", ""),
        "doi": attrs.get("id", ""),
        "product_version": "RL06.3Mv04 CRI",
        "granule": granule.name,
        "granule_sha256": sha256(granule),
        "source_url": ARCHIVE + granule.name,
        "read_utc": utcnow(),
        "variable": "lwe_thickness (with uncertainty, land_mask, mascon_ID, lat_bounds, lon_bounds, time_bounds)",
        "grid": "0.5 degree grid representing 3 degree spherical-cap mascons; cell areas from the "
                "latitude and longitude bounds on a sphere of radius 6371 km",
        "mask": "the granule's land_mask (1 is land, the CRI partition); the ice sheet's mascon "
                "set by the rule each series states",
        "aggregation": "sum over the land cells of the selected mascons of lwe_thickness (cm) "
                       "times the cell area (km2) times 1e-5 Gt; one sigma per mascon times its "
                       "land area, in quadrature over the selected mascons",
        "reference": "anomaly against the product's own baseline (the 2004 to 2009 mean)",
        "sampling": "monthly: one row per solution, labelled by the calendar month of the "
                    "midpoint of its time_bounds; missing months absent",
        "units": "value_gt and uncertainty_gt in gigatonnes; land_area_km2 in km2",
        "sign_convention": "positive is mass gained (more equivalent water thickness), the product's own",
        "time_coverage": [rows[0][8], max(r[9] for r in rows)],
        "months": [labels[0], labels[-1]],
        "n_solutions": len(labels),
        "month_assignments": assignments,
        "uncertainty_basis": "formal: the granule's one sigma per mascon over the mascon's land "
                             "area, in quadrature, mascons treated as independent; a floor where "
                             "mascon errors correlate; leakage is not in it",
        "bookkeeping": BOOKKEEPING,
        "series": series,
        "provider_cross_check": checks,
        "global_attributes": {k: attrs[k] for k in ("title", "id", "time_coverage_start",
                                                    "time_coverage_end", "date_created",
                                                    "processing_level", "source")
                              if k in attrs},
    }
    if stamp_out:
        stamp_out.write_text(json.dumps(stamp, indent=2) + "\n", encoding="utf-8")
    print(f"{out.name}: {len(rows)} rows, {len(labels)} solution months {labels[0]} to {labels[-1]}, "
          + ", ".join(f"{s} {len(ids)} mascons" for s, ids in selections.items()))


# ---- the selftest

def write_toy_granule(p: Path):
    """Three mascons on a 4 by 2 grid straddling 60 S and 80 N: mascon 1
    (two land cells near Greenland at +2 cm, sigma 1), mascon 2 (one
    land cell and one ocean cell, -1 cm, sigma 2), mascon 3 (two land
    cells south of 60 S at -3 cm, sigma 0.5); three epochs, the third
    a spring pair as the product has."""
    ds = nc.Dataset(p, "w")
    ds.createDimension("time", 3); ds.createDimension("lat", 4); ds.createDimension("lon", 2); ds.createDimension("bounds", 2)
    ds.title = "toy mascons"; ds.id = "10.5067/TOY"
    t = ds.createVariable("time", "f8", ("time",)); t.units = "days since 2002-01-01T00:00:00Z"; t.calendar = "gregorian"
    tb = ds.createVariable("time_bounds", "f8", ("time", "bounds"))
    t[:] = [1110.0, 1140.0, 1155.0]
    tb[:] = [[1096.0, 1126.0], [1127.0, 1157.0], [1138.0, 1167.0]]
    lat = ds.createVariable("lat", "f8", ("lat",)); lon = ds.createVariable("lon", "f8", ("lon",))
    lat[:] = [-70.25, -69.75, 70.25, 70.75]; lon[:] = [315.25, 315.75]
    lat_b = ds.createVariable("lat_bounds", "f8", ("lat", "bounds")); lon_b = ds.createVariable("lon_bounds", "f8", ("lon", "bounds"))
    lat_b[:] = [[-70.5, -70.0], [-70.0, -69.5], [70.0, 70.5], [70.5, 71.0]]; lon_b[:] = [[315.0, 315.5], [315.5, 316.0]]
    for name in ("lwe_thickness", "uncertainty"):
        ds.createVariable(name, "f8", ("time", "lat", "lon"))
    for name in ("land_mask", "mascon_ID"):
        ds.createVariable(name, "f8", ("lat", "lon"))
    ds["mascon_ID"][:] = [[3, 3], [3, 3], [1, 1], [2, 2]]
    ds["land_mask"][:] = [[1, 1], [0, 0], [1, 1], [1, 0]]
    ds["lwe_thickness"][:] = [[[-3, -3], [-3, -3], [2, 2], [-1, -1]]] * 3
    ds["uncertainty"][:] = [[[0.5, 0.5], [0.5, 0.5], [1, 1], [2, 2]]] * 3
    ds.close()


def write_toy_mask(p: Path):
    """An EPSG:3413 grid of 3 by 3 cells of 1920 m whose centre falls in
    the toy granule's mascon 1 cell (lat 70.25, lon 315.25, that is
    45 W) with every cell ice; the mascon 2 cells get none."""
    crs = CRS.from_epsg(3413)
    x0, y0 = Transformer.from_crs(4326, crs, always_xy=True).transform(-44.75, 70.25)
    ds = nc.Dataset(p, "w")
    ds.title = "toy mask"; ds.doi = "doi.org/10.5067/TOY"; ds.epsg_number = 3413
    ds.createDimension("x", 3); ds.createDimension("y", 3)
    x = ds.createVariable("x", "f8", ("x",)); y = ds.createVariable("y", "f8", ("y",))
    x[:] = x0 + 1920.0 * (np.arange(3) - 1); y[:] = y0 + 1920.0 * (np.arange(3) - 1)
    m = ds.createVariable("mask", "u1", ("y", "x")); m[:] = [[1, 1, 2], [1, 1, 2], [0, 1, 2]]
    ds.close()


def selftest():
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        g, mk = td / "toy.nc", td / "mask.nc"
        write_toy_granule(g); write_toy_mask(mk)
        prov = td / "greenland_mass_toy.txt"
        prov.write_text("HDR Greenland Mass\nHDR Greenland Mass Trend (x): -1 +/-1 Gt/yr\nHDR Header_End\n"
                        "2005.04 0.0 1.0\n2005.12 0.5 1.0\n2005.21 1.0 1.0\n", encoding="utf-8")
        out, st = td / "mass.csv", td / "mass-stamp.json"
        # nine 1920 m cells cover about 1.6 percent of the two 0.5 degree land
        # cells of mascon 1, so the toy runs at a 1 percent threshold
        run(g, out, st, mk, [prov], 0.01, ("greenland", "antarctica"))
        rows = list(csv.DictReader(out.open()))
        area = cell_areas_km2(np.array([[-70.5, -70.0], [-70.0, -69.5], [70.0, 70.5], [70.5, 71.0]]),
                              np.array([[315.0, 315.5], [315.5, 316.0]]))
        gl = [r for r in rows if r["ice_sheet"] == "greenland"]
        an = [r for r in rows if r["ice_sheet"] == "antarctica"]
        assert [r["month"] for r in gl] == ["2005-01", "2005-02", "2005-03"], gl
        # Greenland: mascon 1 only (mascon 2 carries no ice): 2 cm over its two land cells
        a1 = float(area[2].sum())
        want_gl, want_gl_err = 2.0 * a1 * CM_KM2_TO_GT, 1.0 * a1 * CM_KM2_TO_GT
        got = float(gl[0]["value_gt"]), float(gl[0]["uncertainty_gt"])
        assert abs(got[0] - want_gl) < 1e-6 and abs(got[1] - want_gl_err) < 1e-6, (got, want_gl, want_gl_err)
        assert gl[0]["n_mascons"] == "1", gl[0]
        # Antarctica: mascon 3's two land cells at -3 cm, sigma 0.5
        a3 = float(area[0].sum())
        got = float(an[0]["value_gt"]), float(an[0]["uncertainty_gt"])
        assert abs(got[0] + 3.0 * a3 * CM_KM2_TO_GT) < 1e-6 and abs(got[1] - 0.5 * a3 * CM_KM2_TO_GT) < 1e-6, got
        stamp = json.loads(st.read_text())
        assert stamp["month_assignments"][0]["assigned"] == "2005-03", stamp["month_assignments"]
        assert list(stamp["series"]["greenland"]["mascons"]) == ["1"], stamp["series"]["greenland"]["mascons"]
        assert "2" in stamp["series"]["greenland"]["excluded_land_mascons_with_greenland_ice"] or \
            stamp["series"]["greenland"]["excluded_land_mascons_with_greenland_ice"] == {}
        frac = stamp["series"]["greenland"]["mascons"]["1"]["ice_fraction_of_land"]
        assert 0.01 <= frac < 0.05, frac        # nine 1920 m cells against two 0.5 degree cells
        assert stamp["provider_cross_check"]["greenland"]["common_months"] == 3
        assert stamp["bookkeeping"]["gia"].startswith("ICE-6G_D")
        print(f"selftest: greenland mascon 1 {want_gl:.6f} Gt (formal {want_gl_err:.6f}), ice fraction "
              f"{frac:.5f}; antarctica mascon 3 {-3.0 * a3 * CM_KM2_TO_GT:.6f} Gt; the spring pair's "
              "later solution assigned to March; provider cross-check on 3 months; OK")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--granule", type=Path); ap.add_argument("--out", type=Path)
    ap.add_argument("--stamp-out", type=Path)
    ap.add_argument("--ice-mask", type=Path, help="the ITS_LIVE Greenland elevation change file")
    ap.add_argument("--provider-series", type=Path, nargs="*", default=[])
    ap.add_argument("--min-ice-fraction", type=float, default=DEFAULT_MIN_ICE_FRACTION)
    ap.add_argument("--ice-sheet", choices=["greenland", "antarctica"], nargs="*",
                    default=["greenland", "antarctica"])
    ap.add_argument("--fetch-to", type=Path)
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        selftest(); return
    if not (a.granule and a.out):
        ap.error("--granule and --out are required")
    if not a.granule.is_file():
        if not a.fetch_to:
            ap.error(f"{a.granule} does not exist; give --fetch-to DIR to download it")
        a.granule = a.fetch_to / a.granule.name
        if not a.granule.is_file():
            fetch(ARCHIVE + a.granule.name, a.granule)
    run(a.granule, a.out, a.stamp_out, a.ice_mask, a.provider_series, a.min_ice_fraction,
        tuple(a.ice_sheet))


if __name__ == "__main__":
    main()
