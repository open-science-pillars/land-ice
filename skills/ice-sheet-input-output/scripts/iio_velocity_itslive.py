#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["numpy==2.2.6", "netCDF4==1.7.2", "pyproj==3.7.1"]
# ///
"""Loader for the velocity factor of the discharge term of the ice
sheet input-output balance: the surface velocity component normal to
a flux gate, sampled node by node from the ITS_LIVE regional velocity
mosaics, written as the data root's velocity.csv.

What it reads. The ITS_LIVE annual velocity mosaics as the project
distributes them on AWS under velocity_mosaic/v2.1/annual, one file
per region and year (ITS_LIVE_velocity_120m_RGI05A_<year>_V02.1.nc for
Greenland, RGI19A for the Antarctic and Subantarctic region), 120 m on
the region's polar stereographic grid, carrying v, vx, vy, their
errors, count, and the landice and floatingice masks. The bucket's
version label is V02.1; the collection NSIDC distributes under
NSIDC-0776 is Version 2 and spans 1985 through 2022, so the stamp
records both labels and never calls the bucket copy the archived
version.

The gate set. A discharge is a flux across a gate, and a gate is a
geometry this loader either derives or is handed:

  --derive-gates   the gate nodes are derived from one reference
                   mosaic by a stated rule and written into the CSV,
                   so the geometry travels with the values: the
                   grounded margin is the set of cells with landice 1
                   and floatingice 0 that touch a cell which is not,
                   in the four-neighbourhood; the seeds are the
                   fastest margin cells taken in order, each at least
                   --gate-separation from every seed already taken,
                   up to --n-gates of them above --gate-speed; and
                   each gate is the straight segment through its seed,
                   perpendicular to the seed's flow direction, of
                   --gate-half-length on each side, sampled at the
                   grid posting. A node whose nearest cell is off the
                   grid or not land ice is dropped and counted.
  --gates-from CSV the node table of an existing velocity.csv is
                   reused unchanged, so a second epoch family or a
                   later year samples the same geometry.

A gate set derived this way sits on the ice mask's margin, which is
not the grounding line: the grounding line is the thickness product's
mask, and the loader records `spans_margin` false and
`grounded_by` for the mask that placed the nodes, so a computation
reads the provenance rather than assuming it. In the Greenland
mosaics the floatingice mask carries no cell at all, which the stamp
records per region.

What it writes, one row per ice sheet, gate set, gate, node and
epoch: the node's projected position, the unit normal of its gate,
the node width along the gate in map metres, the projection's areal
scale at the node (so a flux formed from map velocity and map width
can be corrected to the ground, the bundle's polar stereographic
gotcha), the velocity component along the normal, its error, the
speed and the image-pair count. Velocities are the product's own map
units; nothing is interpolated, nothing is filled, and a node with no
finite velocity in an epoch is written with an empty value so the
reader sees the hole.

Usage:
  iio_velocity_itslive.py --ice-sheet greenland --region RGI05A
      --years 2014:2024 --work-dir DIR --out velocity.csv
      [--stamp-out velocity-stamp.json] [--derive-gates | --gates-from CSV]
      [--gate-set NAME] [--n-gates N] [--gate-speed M_PER_YR]
      [--gate-separation M] [--gate-half-length M] [--reference-year YYYY]
      [--keep]      keep each product file in the work directory after reading it
  iio_velocity_itslive.py --selftest
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
ANNUAL_PREFIX = "velocity_mosaic/v2.1/annual/"
STATIC_PREFIX = "velocity_mosaic/v2.1/static/"
BUCKET_VERSION = "V02.1"
ARCHIVE = {
    "short_name": "NSIDC-0776",
    "version": "2",
    "doi": "10.5067/JQ6337239C96",
    "note": "the bucket copy read here is labelled V02.1 and runs to 2024; the collection "
            "NSIDC distributes as NSIDC-0776 Version 2 runs 1985 through 2022, so the two "
            "labels are not the same distribution",
}
REGIONS = {"greenland": "RGI05A", "antarctica": "RGI19A"}
CSV_COLUMNS = ["ice_sheet", "gate_set", "gate", "node", "x_m", "y_m", "normal_x", "normal_y",
               "width_m", "areal_scale", "epoch", "sampling", "v_normal_m_per_yr",
               "v_normal_error_m_per_yr", "speed_m_per_yr", "count"]
ALTERNATES_NOT_READ = [
    "NSIDC-0725 (MEaSUREs Greenland annual ice sheet velocity mosaics from SAR and Landsat): "
    "not read",
    "NSIDC-0478 and NSIDC-0670 (the InSAR Greenland velocity maps): not read",
    "NSIDC-0484 (the InSAR Antarctic velocity map): not read",
    "the ITS_LIVE monthly mosaics and the image pair granules: not read; the annual mosaic is "
    "the epoch this loader samples",
]


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
    with urllib.request.urlopen(url, timeout=300) as r, dest.open("wb") as f:
        for chunk in iter(lambda: r.read(1 << 20), b""):
            f.write(chunk)


def annual_key(region: str, year: int) -> str:
    return f"{ANNUAL_PREFIX}ITS_LIVE_velocity_120m_{region}_{year}_{BUCKET_VERSION}.nc"


def masked(var, sl=Ellipsis) -> np.ndarray:
    return np.ma.filled(np.ma.masked_invalid(var[sl].astype(float)), np.nan)


# ---- the gate geometry

def grounded_margin(landice: np.ndarray, floatingice: np.ndarray) -> np.ndarray:
    """Cells that are land ice and not floating ice and touch, in the
    four-neighbourhood, a cell that is not."""
    g = (landice == 1) & (floatingice == 0)
    edge = np.zeros_like(g)
    edge[1:, :] |= ~g[:-1, :]
    edge[:-1, :] |= ~g[1:, :]
    edge[:, 1:] |= ~g[:, :-1]
    edge[:, :-1] |= ~g[:, 1:]
    return g & edge


def margin_candidates(ds, margin: np.ndarray, gate_speed: float, block: int = 1024):
    """The margin cells at or above the seed speed, read in row blocks
    so a continental mosaic never sits in memory as a float array."""
    ny = margin.shape[0]
    speeds, rows, cols = [], [], []
    for r0 in range(0, ny, block):
        r1 = min(r0 + block, ny)
        v = np.ma.filled(np.ma.masked_invalid(ds["v"][r0:r1, :].astype(np.float32)), np.nan)
        hit = margin[r0:r1] & np.isfinite(v) & (v >= gate_speed)
        rr, cc = np.nonzero(hit)
        if rr.size:
            speeds.append(v[rr, cc]); rows.append(rr + r0); cols.append(cc)
    if not rows:
        return np.empty(0, np.float32), np.empty(0, int), np.empty(0, int)
    return np.concatenate(speeds), np.concatenate(rows), np.concatenate(cols)


def seeds(speeds: np.ndarray, rows: np.ndarray, cols: np.ndarray, x: np.ndarray,
          y: np.ndarray, n_gates: int, gate_speed: float, separation: float):
    """The fastest margin cells in order, each at least `separation`
    metres from every seed already taken."""
    if rows.size == 0:
        sys.exit(f"no grounded margin cell reaches {gate_speed} m per year; no gate can be seeded")
    order = np.argsort(-speeds, kind="stable")
    taken = []
    for k in order:
        r, c = int(rows[k]), int(cols[k])
        px, py = float(x[c]), float(y[r])
        if all((px - qx) ** 2 + (py - qy) ** 2 >= separation ** 2 for qx, qy, _, _ in taken):
            taken.append((px, py, r, c))
        if len(taken) >= n_gates:
            break
    return taken


def gate_nodes(ds, region_epsg: int, x: np.ndarray, y: np.ndarray, gate_set: str,
               n_gates: int, gate_speed: float, separation: float, half_length: float):
    """The node table of a derived gate set: for each seed, the
    segment through it perpendicular to the seed's flow direction,
    sampled at the grid posting, clipped to land ice. The masks are
    read as bytes and the speed in row blocks, so a continental
    mosaic is never held as a float array."""
    dx = float(abs(x[1] - x[0]))
    dy = float(abs(y[1] - y[0]))
    landice = np.asarray(ds["landice"][:], dtype=np.uint8)
    floatingice = np.asarray(ds["floatingice"][:], dtype=np.uint8)
    mask_cells = {"landice_cells": int((landice == 1).sum()),
                  "floatingice_cells": int((floatingice == 1).sum())}
    margin = grounded_margin(landice, floatingice)
    del floatingice
    speeds, rows, cols = margin_candidates(ds, margin, gate_speed)
    del margin
    picked = seeds(speeds, rows, cols, x, y, n_gates, gate_speed, separation)
    k_max = int(round(half_length / dx))
    nodes, dropped = [], 0
    for gi, (px, py, r, c) in enumerate(picked, start=1):
        sx, sy = float(ds["vx"][r, c]), float(ds["vy"][r, c])
        seed_speed = float(ds["v"][r, c])
        norm = (sx * sx + sy * sy) ** 0.5
        if not np.isfinite(norm) or norm == 0.0:
            dropped += 2 * k_max + 1
            continue
        nx_, ny_ = sx / norm, sy / norm          # the gate normal is the seed's flow direction
        tx, ty = -ny_, nx_                       # the gate runs across the flow
        for k in range(-k_max, k_max + 1):
            qx, qy = px + k * dx * tx, py + k * dx * ty
            ci = int(round((qx - float(x[0])) / (float(x[1]) - float(x[0]))))
            ri = int(round((qy - float(y[0])) / (float(y[1]) - float(y[0]))))
            if not (0 <= ri < len(y) and 0 <= ci < len(x)) or landice[ri, ci] != 1:
                dropped += 1
                continue
            nodes.append({"gate_set": gate_set, "gate": f"gate-{gi:02d}", "node": len(nodes),
                          "row": ri, "col": ci, "x_m": float(x[ci]), "y_m": float(y[ri]),
                          "normal_x": nx_, "normal_y": ny_, "width_m": dx,
                          "seed_speed_m_per_yr": seed_speed})
    if not nodes:
        sys.exit("every derived gate node fell outside the land ice mask; no gate set was written")
    add_areal_scale(nodes, region_epsg)
    seeds_out = [{"gate": f"gate-{gi:02d}", "x_m": round(px, 2), "y_m": round(py, 2),
                  "speed_m_per_yr": round(float(ds["v"][r, c]), 3)}
                 for gi, (px, py, r, c) in enumerate(picked, start=1)]
    return nodes, dropped, {"dy": dy, "dx": dx, "n_seeds": len(picked),
                            "mask_cells": mask_cells, "seeds": seeds_out}


def add_areal_scale(nodes, epsg: int) -> None:
    """The projection's areal scale at each node, so a flux formed
    from a map velocity and a map width can be brought to the ground."""
    crs = CRS.from_epsg(epsg)
    xs = np.array([n["x_m"] for n in nodes], float)
    ys = np.array([n["y_m"] for n in nodes], float)
    lon, lat = Transformer.from_crs(crs, 4326, always_xy=True).transform(xs, ys)
    scale = np.asarray(Proj(crs).get_factors(lon, lat).areal_scale, float)
    for n, s in zip(nodes, scale):
        n["areal_scale"] = float(s)


def nodes_from_csv(path: Path, ice_sheet: str, gate_set: str | None):
    """The node table of an existing velocity.csv, one entry per node,
    with the epochs dropped."""
    seen, out = set(), []
    for r in csv.DictReader(path.open(encoding="utf-8")):
        if r["ice_sheet"] != ice_sheet or (gate_set and r["gate_set"] != gate_set):
            continue
        key = (r["gate_set"], r["gate"], int(r["node"]))
        if key in seen:
            continue
        seen.add(key)
        out.append({"gate_set": r["gate_set"], "gate": r["gate"], "node": int(r["node"]),
                    "x_m": float(r["x_m"]), "y_m": float(r["y_m"]),
                    "normal_x": float(r["normal_x"]), "normal_y": float(r["normal_y"]),
                    "width_m": float(r["width_m"]), "areal_scale": float(r["areal_scale"])})
    if not out:
        sys.exit(f"{path} carries no nodes for {ice_sheet}"
                 + (f" and gate set {gate_set}" if gate_set else ""))
    return out


def locate(nodes, x: np.ndarray, y: np.ndarray) -> None:
    """The nearest cell of this grid for each node, by the axes' own
    spacing; a node off the grid is a hard error, not a silent hole."""
    x0, y0 = float(x[0]), float(y[0])
    sx, sy = float(x[1]) - x0, float(y[1]) - y0
    for n in nodes:
        ci = int(round((n["x_m"] - x0) / sx))
        ri = int(round((n["y_m"] - y0) / sy))
        if not (0 <= ri < len(y) and 0 <= ci < len(x)):
            sys.exit(f"node {n['gate']}/{n['node']} at ({n['x_m']}, {n['y_m']}) is off this grid")
        n["row"], n["col"] = ri, ci


# ---- sampling one epoch

def sample_epoch(ds, nodes) -> list[dict]:
    """The velocity at every node of one mosaic, read gate by gate as
    a block so the file is touched once per gate."""
    out = {}
    by_gate: dict[str, list] = {}
    for n in nodes:
        by_gate.setdefault(n["gate"], []).append(n)
    for gate, ns in by_gate.items():
        r0, r1 = min(n["row"] for n in ns), max(n["row"] for n in ns) + 1
        c0, c1 = min(n["col"] for n in ns), max(n["col"] for n in ns) + 1
        block = {name: masked(ds[name], (slice(r0, r1), slice(c0, c1)))
                 for name in ("vx", "vy", "v", "v_error")}
        cnt = np.asarray(ds["count"][r0:r1, c0:c1]).astype(float)
        err_fill = float(getattr(ds["v_error"], "fill_value", 32767))
        for n in ns:
            i, j = n["row"] - r0, n["col"] - c0
            vx_, vy_ = block["vx"][i, j], block["vy"][i, j]
            v_ = block["v"][i, j]
            e_ = block["v_error"][i, j]
            if e_ >= err_fill:
                e_ = np.nan
            vn = (vx_ * n["normal_x"] + vy_ * n["normal_y"]
                  if np.isfinite(vx_) and np.isfinite(vy_) else np.nan)
            out[(n["gate"], n["node"])] = {"v_normal": vn, "v_error": e_, "speed": v_,
                                           "count": int(cnt[i, j])}
    return out


def epoch_label(ds, year: int) -> str:
    """The mosaic's own year attribute, as a month label; the annual
    mosaic is one composite of a calendar year and is labelled by its
    January, never spread over the months it drew on."""
    attr = str(getattr(ds, "year", "")).strip()
    if attr:
        tail = attr.split("-")[-1]
        if tail.isdigit() and len(tail) == 4:
            return f"{int(tail):04d}-01"
    return f"{year:04d}-01"


# ---- the run

def run(ice_sheet: str, region: str, years, work: Path, out: Path, stamp_out: Path | None,
        derive: bool, gates_from: Path | None, gate_set: str, n_gates: int, gate_speed: float,
        separation: float, half_length: float, reference_year: int | None, keep: bool,
        fetch_enabled: bool = True):
    years = list(years)
    ref_year = reference_year if reference_year is not None else years[0]
    if derive and ref_year not in years:
        sys.exit(f"the reference year {ref_year} is not among the years read {years}")
    per_epoch, granules, nodes, geometry = {}, [], None, {}
    epsg = None
    masks_note = {}
    for year in years:
        path = work / f"ITS_LIVE_velocity_120m_{region}_{year}_{BUCKET_VERSION}.nc"
        if not path.is_file():
            if not fetch_enabled:
                sys.exit(f"{path} does not exist and fetching is off")
            fetch(BUCKET + annual_key(region, year), path)
        digest = sha256(path)
        ds = nc.Dataset(path)
        attrs = {a: str(getattr(ds, a)) for a in ds.ncattrs()}
        this_epsg = int(float(getattr(ds["mapping"], "spatial_epsg", 0)))
        if epsg is None:
            epsg = this_epsg
        elif this_epsg != epsg:
            sys.exit(f"{path.name}: spatial_epsg {this_epsg} is not the {epsg} of the earlier years")
        x, y = np.asarray(ds["x"][:], float), np.asarray(ds["y"][:], float)
        if nodes is None:
            if gates_from is not None:
                nodes = nodes_from_csv(gates_from, ice_sheet, gate_set)
                locate(nodes, x, y)
                geometry = {"dx": float(abs(x[1] - x[0])), "dy": float(abs(y[1] - y[0])),
                            "n_seeds": len({n["gate"] for n in nodes})}
            elif year != ref_year:
                ds.close()
                continue                      # the geometry comes from the reference year first
        if nodes is None:
            nodes, dropped, geometry = gate_nodes(
                ds, epsg, x, y, gate_set, n_gates, gate_speed, separation, half_length)
            geometry["nodes_dropped"] = dropped
            masks_note[region] = geometry.pop("mask_cells")
            print(f"  gate set {gate_set}: {len({n['gate'] for n in nodes})} gates, "
                  f"{len(nodes)} nodes, {dropped} dropped", file=sys.stderr)
        label = epoch_label(ds, year)
        per_epoch[label] = sample_epoch(ds, nodes)
        granules.append({"year": year, "epoch": label, "granule": path.name,
                         "granule_sha256": digest, "source_url": BUCKET + annual_key(region, year),
                         "read_utc": utcnow(), "grid": f"{geometry['dx']:.0f} m, EPSG:{epsg}, "
                                                       f"{len(y)} by {len(x)} cells",
                         "date_created": attrs.get("date_created", ""),
                         "mosaics_software_version": attrs.get("mosaics_software_version", ""),
                         "year_attribute": attrs.get("year", "")})
        ds.close()
        if not keep:
            path.unlink()
        print(f"  {label}: sampled {len(nodes)} nodes from {path.name}", file=sys.stderr)
    if nodes is None:
        sys.exit("no mosaic supplied a gate set")
    missing_years = [y for y in years if f"{y:04d}-01" not in per_epoch]
    if missing_years:
        # the reference year was read first for its geometry; read the rest
        for year in missing_years:
            path = work / f"ITS_LIVE_velocity_120m_{region}_{year}_{BUCKET_VERSION}.nc"
            if not path.is_file():
                if not fetch_enabled:
                    sys.exit(f"{path} does not exist and fetching is off")
                fetch(BUCKET + annual_key(region, year), path)
            digest = sha256(path)
            ds = nc.Dataset(path)
            attrs = {a: str(getattr(ds, a)) for a in ds.ncattrs()}
            x, y = np.asarray(ds["x"][:], float), np.asarray(ds["y"][:], float)
            locate(nodes, x, y)
            label = epoch_label(ds, year)
            per_epoch[label] = sample_epoch(ds, nodes)
            granules.append({"year": year, "epoch": label, "granule": path.name,
                             "granule_sha256": digest,
                             "source_url": BUCKET + annual_key(region, year),
                             "read_utc": utcnow(),
                             "grid": f"{geometry['dx']:.0f} m, EPSG:{epsg}, {len(y)} by {len(x)} cells",
                             "date_created": attrs.get("date_created", ""),
                             "mosaics_software_version": attrs.get("mosaics_software_version", ""),
                             "year_attribute": attrs.get("year", "")})
            ds.close()
            if not keep:
                path.unlink()
            print(f"  {label}: sampled {len(nodes)} nodes from {path.name}", file=sys.stderr)
    labels = sorted(per_epoch)
    rows, holes = [], 0
    for label in labels:
        for n in nodes:
            s = per_epoch[label][(n["gate"], n["node"])]
            if not np.isfinite(s["v_normal"]):
                holes += 1
            rows.append([ice_sheet, n["gate_set"], n["gate"], n["node"],
                         f"{n['x_m']:.2f}", f"{n['y_m']:.2f}",
                         f"{n['normal_x']:.9f}", f"{n['normal_y']:.9f}",
                         f"{n['width_m']:.3f}", f"{n['areal_scale']:.9f}", label, "annual",
                         "" if not np.isfinite(s["v_normal"]) else f"{s['v_normal']:.6f}",
                         "" if not np.isfinite(s["v_error"]) else f"{s['v_error']:.6f}",
                         "" if not np.isfinite(s["speed"]) else f"{s['speed']:.6f}",
                         s["count"]])
    with out.open("w", encoding="utf-8", newline="") as f:
        wr = csv.writer(f)
        wr.writerow(CSV_COLUMNS)
        wr.writerows(rows)
    gates = sorted({n["gate"] for n in nodes})
    stamp = {
        "term": "velocity",
        "quantity": "surface velocity component normal to a flux gate, per node and epoch",
        "units": "v_normal_m_per_yr, v_normal_error_m_per_yr and speed_m_per_yr in metres per "
                 "year in the mosaic's map units; x_m, y_m and width_m in projection metres; "
                 "areal_scale dimensionless",
        "sign_convention": "positive is flow along the gate's stated normal, which points down "
                           "the seed's flow direction, so a positive value is ice leaving through "
                           "the gate",
        "months": [labels[0], labels[-1]],
        "n_rows": len(rows),
        "domains": [[ice_sheet, gate_set]],
        "gate_set": {
            "name": gate_set,
            "ice_sheet": ice_sheet,
            "n_gates": len(gates),
            "n_nodes": len(nodes),
            "gates": gates,
            "node_width_m": geometry["dx"],
            "rule": (f"the grounded margin of the {region} mosaic of {ref_year} (landice 1 and "
                     "floatingice 0, touching a cell that is not, in the four-neighbourhood); "
                     f"seeds the fastest margin cells at or above {gate_speed} m per year, each "
                     f"at least {separation} m from every seed already taken, up to {n_gates}; "
                     f"each gate the straight segment through its seed perpendicular to the "
                     f"seed's flow direction, {half_length} m on each side, sampled at the grid "
                     "posting and clipped to land ice")
            if gates_from is None else
            f"the node table of {gates_from.name}, reused unchanged",
            "reference_year": ref_year,
            "nodes_dropped_outside_land_ice": geometry.get("nodes_dropped"),
            "seeds": geometry.get("seeds"),
            "areal_scale_range": [min(n["areal_scale"] for n in nodes),
                                  max(n["areal_scale"] for n in nodes)],
            "nodes_per_gate": {g: sum(1 for n in nodes if n["gate"] == g) for g in gates},
            "spans_margin": False,
            "spans_margin_note": "the gate set is a set of segments across the fastest outlets, "
                                 "not a curve around the whole grounded margin, so the discharge "
                                 "it carries is the discharge of those outlets and not the ice "
                                 "sheet's total",
            "grounded_by": "the velocity mosaic's own landice and floatingice masks, not the "
                           "thickness product's grounded mask; the ice mask margin is not the "
                           "grounding line, and a node's grounding is settled by the thickness "
                           "term's mask",
            "mask_cells": masks_note,
        },
        "not_in_the_distribution": [],
        "alternates_not_read": ALTERNATES_NOT_READ,
        "series": {
            ice_sheet: {
                "product": "ITS_LIVE annual mosaics of image pair velocities",
                "product_version": f"bucket {BUCKET_VERSION}",
                "archive_collection": ARCHIVE["short_name"],
                "archive_version": ARCHIVE["version"],
                "doi": ARCHIVE["doi"],
                "version_note": ARCHIVE["note"],
                "region": region,
                "granules": granules,
                "grid": f"{geometry['dx']:.0f} m polar stereographic, EPSG:{epsg}",
                "mask": "the mosaic's landice and floatingice masks; the nodes lie on land ice, "
                        "and whether a node is grounded is the thickness term's statement",
                "aggregation": "no aggregation: one row per node and epoch, the velocity read at "
                               "the node's nearest cell, nothing interpolated and no hole filled",
                "sampling": "annual: one row per annual mosaic, labelled by the January of the "
                            "mosaic's year attribute; an annual mosaic is an error-weighted fit "
                            "of the image pairs overlapping the year, a composite with its own "
                            "effective date and not a calendar mean. The user guide states that "
                            "data scarcity and low radiometric quality significantly limit "
                            "coverage for many regions in the earlier years and that annual "
                            "coverage is nearly complete for all regions after 2013",
                "epochs": labels,
                "n_epochs": len(labels),
                "nodes_without_velocity": holes,
                "uncertainty_basis": "the product's v_error at the node, the error weighted error "
                                     "for v; the user guide states that this formal propagation "
                                     "typically produces errors that are unrealistically low and "
                                     "that v_error and count are qualitative error metrics, so a "
                                     "discharge interval formed from it is a lower bound",
                "map_units": "the Version 2 user guide states that the velocities are "
                             "calculated in map units, that the distortion of up to a few "
                             "percent was not corrected as it was in Version 1, and that a flux "
                             "gate cross section therefore no longer needs to be corrected for "
                             "projection scale distortion. A map velocity times a map width is "
                             "the ground flux times the projection's areal scale, so the two "
                             "readings differ by that factor; the areal_scale column carries it "
                             "at every node and a computation states which reading it took",
                "read_utc": utcnow(),
            }
        },
    }
    if stamp_out:
        stamp_out.write_text(json.dumps(stamp, indent=2) + "\n", encoding="utf-8")
    print(f"{out.name}: {len(rows)} rows, {len(nodes)} nodes on {len(gates)} gates, "
          f"{labels[0]} to {labels[-1]}, {holes} node epochs without a velocity")
    return stamp


# ---- selftest

def write_toy(p: Path, year: int, scale: float):
    """A 80 by 80 grid of 120 m cells on EPSG:3413, land ice inside a
    disc of 30 cells, no floating ice, and a radial outward velocity
    of `scale` times the radius in cells, so the fastest cells are the
    disc's own margin and the normal component at a node on the
    seed's segment is known by hand."""
    ds = nc.Dataset(p, "w")
    ds.title = "toy its_live mosaic"
    ds.year = f"01-Jan-{year}"
    ds.region = "TOY"
    ds.date_created = "01-Jan-2026 00:00:00"
    ds.mosaics_software_version = "toy"
    n = 80
    ds.createDimension("x", n); ds.createDimension("y", n)
    x = ds.createVariable("x", "f8", ("x",)); y = ds.createVariable("y", "f8", ("y",))
    x[:] = -300000.0 + 120.0 * np.arange(n)
    y[:] = -1200000.0 - 120.0 * np.arange(n)
    mp = ds.createVariable("mapping", "S1", ()); mp.spatial_epsg = "3413.0"
    j, i = np.meshgrid(np.arange(n), np.arange(n))       # i is the row, j the column
    ci = cj = n // 2
    dr = i - ci
    dc = j - cj
    rad = np.sqrt(dr * dr + dc * dc)
    disc = rad <= 30.0
    li = ds.createVariable("landice", "u1", ("y", "x")); li[:] = disc.astype("u1")
    fi = ds.createVariable("floatingice", "u1", ("y", "x")); fi[:] = np.zeros((n, n), "u1")
    cnt = ds.createVariable("count", "u4", ("y", "x")); cnt[:] = np.where(disc, 7, 0).astype("u4")
    with np.errstate(invalid="ignore", divide="ignore"):
        ux = np.where(rad > 0, dc / np.maximum(rad, 1e-9), 0.0) * rad * scale
        uy = np.where(rad > 0, -dr / np.maximum(rad, 1e-9), 0.0) * rad * scale
    for name, arr in (("vx", ux), ("vy", uy), ("v", np.sqrt(ux ** 2 + uy ** 2))):
        v = ds.createVariable(name, "f4", ("y", "x"), fill_value=-32767.0)
        v[:] = np.where(disc, arr, -32767.0)
    e = ds.createVariable("v_error", "u2", ("y", "x"), fill_value=32767)
    e.fill_value = 32767
    e[:] = np.where(disc, 9, 32767).astype("u2")
    ds.close()


def selftest():
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        years = [2020, 2021]
        for k, yr in enumerate(years):
            write_toy(td / f"ITS_LIVE_velocity_120m_TOY_{yr}_{BUCKET_VERSION}.nc", yr, 10.0 + k)
        out, st = td / "velocity.csv", td / "velocity-stamp.json"
        stamp = run("greenland", "TOY", years, td, out, st, True, None, "toy-gates", 3, 100.0,
                    2000.0, 480.0, None, True, fetch_enabled=False)
        rows = list(csv.DictReader(out.open()))
        gates = sorted({r["gate"] for r in rows})
        nodes = sorted({(r["gate"], int(r["node"])) for r in rows})
        assert gates == ["gate-01", "gate-02", "gate-03"], gates
        assert len(rows) == 2 * len(nodes), (len(rows), len(nodes))
        assert sorted({r["epoch"] for r in rows}) == ["2020-01", "2021-01"], rows[0]
        # the seed sits on the disc's margin at radius 30 cells, so its
        # speed is 30 times the year's scale; the gate's normal is the
        # seed's flow direction, and at the seed the normal component is
        # the speed itself.
        for epoch, sc in (("2020-01", 10.0), ("2021-01", 11.0)):
            seed_rows = [r for r in rows if r["epoch"] == epoch and abs(
                float(r["speed_m_per_yr"] or "nan") - 30.0 * sc) < 0.6 * sc]
            assert seed_rows, (epoch, sc)
            r = seed_rows[0]
            assert abs(float(r["v_normal_m_per_yr"]) - float(r["speed_m_per_yr"])) < 0.35 * sc, r
        # a node away from its seed keeps the seed's normal, so its
        # normal component is the speed times the cosine of the turn
        far = [r for r in rows if r["epoch"] == "2020-01" and int(r["node"]) % 9 == 0]
        assert all(abs(float(r["v_normal_m_per_yr"])) <= float(r["speed_m_per_yr"]) + 1e-6
                   for r in far if r["v_normal_m_per_yr"] and r["speed_m_per_yr"]), far[:3]
        # the geometry travels with the values and is reusable
        again = td / "velocity-2.csv"
        run("greenland", "TOY", [2021], td, again, None, False, out, "toy-gates", 3, 100.0,
            2000.0, 480.0, None, True, fetch_enabled=False)
        a = [r for r in csv.DictReader(again.open())]
        b = [r for r in rows if r["epoch"] == "2021-01"]
        assert len(a) == len(b) and all(x["v_normal_m_per_yr"] == z["v_normal_m_per_yr"]
                                        for x, z in zip(a, b)), (len(a), len(b))
        # the areal scale of EPSG 3413 is near one at these latitudes and never absurd
        sc = [float(r["areal_scale"]) for r in rows]
        assert all(0.5 < v < 2.0 for v in sc), (min(sc), max(sc))
        gs = stamp["gate_set"]
        assert gs["n_gates"] == 3 and gs["spans_margin"] is False and gs["n_nodes"] == len(nodes)
        assert stamp["series"]["greenland"]["n_epochs"] == 2
        assert stamp["series"]["greenland"]["granules"][0]["granule_sha256"].startswith("sha256:")
        print(f"iio_velocity_itslive selftest: {len(nodes)} nodes on 3 gates over 2 epochs, "
              f"normal component recovered at the seeds, node table reused; OK")


def parse_years(spec: str):
    if ":" in spec:
        a, b = spec.split(":", 1)
        return list(range(int(a), int(b) + 1))
    return [int(v) for v in spec.split(",")]


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--ice-sheet", choices=sorted(REGIONS))
    ap.add_argument("--region", help=f"the mosaic region (default {REGIONS})")
    ap.add_argument("--years", help="YYYY:YYYY inclusive, or a comma separated list")
    ap.add_argument("--work-dir", type=Path, help="where the product files are read or fetched")
    ap.add_argument("--out", type=Path)
    ap.add_argument("--stamp-out", type=Path)
    ap.add_argument("--gate-set", default=None, help="the gate set's name (default <ice sheet>-outlets-v1)")
    ap.add_argument("--derive-gates", action="store_true")
    ap.add_argument("--gates-from", type=Path, help="reuse the node table of a velocity.csv")
    ap.add_argument("--n-gates", type=int, default=12)
    ap.add_argument("--gate-speed", type=float, default=500.0, help="m per year at the seed")
    ap.add_argument("--gate-separation", type=float, default=25000.0, help="m between seeds")
    ap.add_argument("--gate-half-length", type=float, default=3000.0, help="m each side of the seed")
    ap.add_argument("--reference-year", type=int, default=None)
    ap.add_argument("--keep", action="store_true", help="keep each product file after reading it")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        selftest(); return
    if not (a.ice_sheet and a.years and a.work_dir and a.out):
        ap.error("--ice-sheet, --years, --work-dir and --out are required")
    if a.derive_gates == bool(a.gates_from):
        ap.error("give exactly one of --derive-gates and --gates-from")
    a.work_dir.mkdir(parents=True, exist_ok=True)
    run(a.ice_sheet, a.region or REGIONS[a.ice_sheet], parse_years(a.years), a.work_dir, a.out,
        a.stamp_out, a.derive_gates, a.gates_from, a.gate_set or f"{a.ice_sheet}-outlets-v1",
        a.n_gates, a.gate_speed, a.gate_separation, a.gate_half_length, a.reference_year, a.keep)


if __name__ == "__main__":
    main()
