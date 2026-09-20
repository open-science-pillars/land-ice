#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["numpy==2.2.6", "netCDF4==1.7.2"]
# ///
"""Loader for the thickness factor of the discharge term of the ice
sheet input-output balance: the BedMachine ice thickness at each flux
gate node, with the error field and, per node, the method that made
that pixel, written as the data root's thickness.csv.

Why the method travels with the number. BedMachine's thickness is
continuous over the ice sheet, but between the radar flight lines it
is computed: mass conservation where the ice flows fast, kriging,
streamline diffusion, ice flow perturbation analysis or plain
interpolation in the slow interior, hydrostatic equilibrium on
floating ice. The file records which per pixel in its source
variable, and errbed records how far to trust the value. A gate node
whose thickness is an interpolation is not a discharge measurement,
so this loader writes the method as a word beside every thickness and
counts the nodes by method in the stamp; the computation refuses a
gate set that rests on them rather than multiplying them by a
velocity.

What it reads. One BedMachine granule per ice sheet:

  greenland   BedMachineGreenland-v6.nc (IceBridge BedMachine
              Greenland Version 6, doi 10.5067/6B6B225B8V2D), 150 m on
              EPSG:3413, nominal year 2007.
  antarctica  NSIDC-0756_BedMachineAntarctica_19700101-20191001_V04.1.nc
              (MEaSUREs BedMachine Antarctica Version 4, doi
              10.5067/POJQI54A45HX), 500 m on EPSG:3031, nominal year
              2015, thickness in ice equivalent with the firn air
              content removed and carried as the firn variable.

The two files number their source codes differently, so the loader
carries one table per ice sheet and writes the word, never the number
alone. The node table comes from the velocity term's CSV, so the two
factors of the discharge sit on the same nodes by construction.

Access. Both granules are distributed only from the NSIDC cloud
archive, which answers a request for the file with a redirect to a
content distribution host. Where an environment's egress policy
refuses that host, the loader cannot read the product; --fetch-to
records the status it got and exits rather than writing a thickness
nobody opened.

Usage:
  iio_thickness_bedmachine.py --ice-sheet greenland --bedmachine FILE.nc
      --nodes velocity.csv --out thickness.csv [--stamp-out thickness-stamp.json]
      [--gate-set NAME] [--fetch-to DIR]
  iio_thickness_bedmachine.py --selftest
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
import urllib.error
import urllib.request
from pathlib import Path

import netCDF4 as nc
import numpy as np

PRODUCTS = {
    "greenland": {
        "granule": "BedMachineGreenland-v6.nc",
        "short_name": "IDBMG4",
        "version": "6",
        "doi": "10.5067/6B6B225B8V2D",
        "url": "https://data.nsidc.earthdatacloud.nasa.gov/nsidc-cumulus-prod-protected/"
               "ICEBRIDGE/IDBMG4/6/1993/01/01/BedMachineGreenland-v6.nc",
        "epsg": 3413,
        "posting_m": 150.0,
        "nominal_year": 2007,
        "source_codes": {0: "none", 1: "gimp_dem", 2: "mass_conservation", 3: "synthetic",
                         4: "interpolation", 5: "hydrostatic", 6: "kriging", 7: "rtopo2",
                         8: "gravity_inversion", 9: "iceboost"},
        "source_codes_note": "codes 10 and above are bathymetry data (the Version 6 user "
                             "guide's parameter table)",
        "ice_equivalent": False,
    },
    "antarctica": {
        "granule": "NSIDC-0756_BedMachineAntarctica_19700101-20191001_V04.1.nc",
        "short_name": "NSIDC-0756",
        "version": "4",
        "doi": "10.5067/POJQI54A45HX",
        "url": "https://data.nsidc.earthdatacloud.nasa.gov/nsidc-cumulus-prod-protected/"
               "MEASURES/NSIDC-0756/4/1970/01/01/"
               "NSIDC-0756_BedMachineAntarctica_19700101-20191001_V04.1.nc",
        "epsg": 3031,
        "posting_m": 500.0,
        "nominal_year": 2015,
        "source_codes": {0: "none", 1: "rema_or_ibcso", 2: "mass_conservation",
                         3: "interpolation", 4: "hydrostatic",
                         5: "ice_flow_perturbation_analysis", 6: "gravity", 7: "seismic",
                         8: "iceboost", 10: "multibeam"},
        "source_codes_note": "the Version 4 user guide's parameter table",
        "ice_equivalent": True,
    },
}
MASK_CODES = {0: "ocean", 1: "ice_free_land", 2: "grounded_ice", 3: "floating_ice",
              4: "lake_vostok"}
SUPPORTS_DISCHARGE = ("mass_conservation",)
CSV_COLUMNS = ["ice_sheet", "gate_set", "gate", "node", "x_m", "y_m", "thickness_m",
               "thickness_error_m", "source_code", "provenance", "mask_code", "mask"]


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return "sha256:" + h.hexdigest()


def utcnow() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def fetch(url: str, dest: Path) -> None:
    """Stream the granule to dest with an Earthdata Login bearer token
    when one is in the environment. The token is sent as a request
    header and is never printed, logged or written anywhere."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    token = os.environ.get("EARTHDATA_TOKEN")
    req = urllib.request.Request(url)
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    print(f"fetching {url} -> {dest}", file=sys.stderr)
    try:
        with urllib.request.urlopen(req, timeout=300) as r, dest.open("wb") as f:
            for chunk in iter(lambda: r.read(1 << 20), b""):
                f.write(chunk)
    except (urllib.error.HTTPError, urllib.error.URLError, OSError) as e:
        status = getattr(e, "code", None)
        sys.exit(f"the granule could not be fetched from {url}: "
                 f"{'HTTP ' + str(status) if status else e}. The NSIDC cloud archive answers "
                 "with a redirect to a content distribution host; where an environment's egress "
                 "policy refuses that host the product cannot be read from it, and the data "
                 "root records the term as absent with this status rather than carrying a "
                 "thickness nobody opened.")


def read_nodes(path: Path, ice_sheet: str, gate_set: str | None):
    seen, out = set(), []
    for r in csv.DictReader(path.open(encoding="utf-8")):
        if r["ice_sheet"] != ice_sheet or (gate_set and r["gate_set"] != gate_set):
            continue
        key = (r["gate_set"], r["gate"], int(r["node"]))
        if key in seen:
            continue
        seen.add(key)
        out.append({"gate_set": r["gate_set"], "gate": r["gate"], "node": int(r["node"]),
                    "x_m": float(r["x_m"]), "y_m": float(r["y_m"])})
    if not out:
        sys.exit(f"{path} carries no nodes for {ice_sheet}"
                 + (f" and gate set {gate_set}" if gate_set else ""))
    return out


def sample(ds, nodes, product) -> None:
    x = np.asarray(ds["x"][:], float)
    y = np.asarray(ds["y"][:], float)
    x0, sx = float(x[0]), float(x[1]) - float(x[0])
    y0, sy = float(y[0]), float(y[1]) - float(y[0])
    off = 0
    for n in nodes:
        ci = int(round((n["x_m"] - x0) / sx))
        ri = int(round((n["y_m"] - y0) / sy))
        if not (0 <= ri < len(y) and 0 <= ci < len(x)):
            n.update({"thickness_m": None, "thickness_error_m": None, "source_code": None,
                      "provenance": "off_grid", "mask_code": None, "mask": "off_grid"})
            off += 1
            continue
        n["row"], n["col"] = ri, ci
    inside = [n for n in nodes if "row" in n]
    for n in inside:
        r, c = n["row"], n["col"]
        thk = float(ds["thickness"][r, c])
        err = float(ds["errbed"][r, c])
        src = int(ds["source"][r, c])
        msk = int(ds["mask"][r, c])
        n.update({"thickness_m": thk, "thickness_error_m": err, "source_code": src,
                  "provenance": product["source_codes"].get(src, f"code_{src}"),
                  "mask_code": msk, "mask": MASK_CODES.get(msk, f"code_{msk}")})
    return off


def run(ice_sheet: str, granule: Path, nodes_csv: Path, out: Path, stamp_out: Path | None,
        gate_set: str | None):
    product = PRODUCTS[ice_sheet]
    ds = nc.Dataset(granule)
    attrs = {a: str(getattr(ds, a)) for a in ds.ncattrs()}
    nodes = read_nodes(nodes_csv, ice_sheet, gate_set)
    off = sample(ds, nodes, product)
    rows = [[ice_sheet, n["gate_set"], n["gate"], n["node"], f"{n['x_m']:.2f}", f"{n['y_m']:.2f}",
             "" if n["thickness_m"] is None else f"{n['thickness_m']:.4f}",
             "" if n["thickness_error_m"] is None else f"{n['thickness_error_m']:.4f}",
             "" if n["source_code"] is None else n["source_code"], n["provenance"],
             "" if n["mask_code"] is None else n["mask_code"], n["mask"]] for n in nodes]
    with out.open("w", encoding="utf-8", newline="") as f:
        wr = csv.writer(f)
        wr.writerow(CSV_COLUMNS)
        wr.writerows(rows)
    by_prov, by_mask = {}, {}
    for n in nodes:
        by_prov[n["provenance"]] = by_prov.get(n["provenance"], 0) + 1
        by_mask[n["mask"]] = by_mask.get(n["mask"], 0) + 1
    unsupported = sorted({n["provenance"] for n in nodes if n["provenance"] not in SUPPORTS_DISCHARGE})
    gates = sorted({n["gate"] for n in nodes})
    sets = sorted({n["gate_set"] for n in nodes})
    stamp = {
        "term": "thickness",
        "quantity": "ice thickness and its error at each flux gate node, with the method that "
                    "made the pixel",
        "units": "thickness_m and thickness_error_m in metres; x_m and y_m in projection metres",
        "sign_convention": "thickness is positive downward from the ice surface to the bed"
                           + (", in ice equivalent with the firn air content removed"
                              if product["ice_equivalent"] else ""),
        "months": ["", ""],
        "n_rows": len(rows),
        "domains": [[ice_sheet, s] for s in sets],
        "gate_sets": sets,
        "nodes_by_provenance": by_prov,
        "nodes_by_mask": by_mask,
        "nodes_off_grid": off,
        "provenance_supporting_a_discharge": list(SUPPORTS_DISCHARGE),
        "provenance_not_supporting_a_discharge": unsupported,
        "not_in_the_distribution": [],
        "alternates_not_read": [
            "IRMCR3 (IceBridge MCoRDS L3 gridded ice thickness): not read",
            "the BedMachine bed GeoTIFF: not read; the netCDF granule carries every field used",
        ],
        "series": {
            ice_sheet: {
                "product": attrs.get("title", product["short_name"]),
                "short_name": product["short_name"],
                "product_version": attrs.get("version", product["version"]),
                "doi": product["doi"],
                "granule": granule.name,
                "granule_sha256": sha256(granule),
                "source_url": product["url"],
                "read_utc": utcnow(),
                "variables_read": "thickness, errbed, source, mask, x, y",
                "grid": f"{product['posting_m']:.0f} m polar stereographic, "
                        f"EPSG:{product['epsg']}, {len(ds['y'][:])} by {len(ds['x'][:])} cells; "
                        "the guide states that the true resolution varies and is not the posting",
                "nominal_year": product["nominal_year"],
                "mask": "the file's mask variable: " + ", ".join(
                    f"{k} {v}" for k, v in sorted(MASK_CODES.items())),
                "source_variable": "the file's source variable: " + ", ".join(
                    f"{k} {v}" for k, v in sorted(product["source_codes"].items()))
                + "; " + product["source_codes_note"],
                "aggregation": "no aggregation: the value at the node's nearest cell, nothing "
                               "interpolated and no hole filled",
                "sampling": "static: one thickness per node, of the product's nominal year, "
                            "against velocity epochs of other years",
                "gates": gates,
                "n_nodes": len(nodes),
                "uncertainty_basis": "the product's errbed at the node, described in the guides "
                                     "as the bed topography and ice thickness error in metres; "
                                     "neither guide states that it is a formal covariance or "
                                     "that it is independent between cells, so a discharge that "
                                     "sums it along a gate treats it as fully correlated",
                "global_attributes": attrs,
            }
        },
    }
    ds.close()
    if stamp_out:
        stamp_out.write_text(json.dumps(stamp, indent=2) + "\n", encoding="utf-8")
    print(f"{out.name}: {len(rows)} nodes on {len(gates)} gates, by method {by_prov}, "
          f"by mask {by_mask}")
    return stamp


# ---- selftest

def write_toy(p: Path, epsg: int):
    """A 40 by 40 grid of 150 m cells on EPSG:3413 whose thickness is
    a known ramp, whose source is mass conservation in a band and
    interpolation outside it, and whose mask is grounded ice except
    for a floating strip."""
    ds = nc.Dataset(p, "w")
    ds.title = "toy bedmachine"
    ds.version = "6"
    n = 40
    ds.createDimension("x", n); ds.createDimension("y", n)
    x = ds.createVariable("x", "f8", ("x",)); y = ds.createVariable("y", "f8", ("y",))
    x[:] = -300000.0 + 150.0 * np.arange(n)
    y[:] = -1200000.0 - 150.0 * np.arange(n)
    j, i = np.meshgrid(np.arange(n), np.arange(n))
    thk = ds.createVariable("thickness", "f4", ("y", "x"))
    thk[:] = (100.0 + 10.0 * j).astype("f4")
    err = ds.createVariable("errbed", "f4", ("y", "x"))
    err[:] = (20.0 + 0.5 * i).astype("f4")
    src = ds.createVariable("source", "i1", ("y", "x"))
    src[:] = np.where(i < 20, 2, 4).astype("i1")          # mass conservation, then interpolation
    msk = ds.createVariable("mask", "i1", ("y", "x"))
    msk[:] = np.where(j >= 35, 3, 2).astype("i1")         # a floating strip at high column
    ds.close()


def write_toy_nodes(p: Path):
    rows = [["ice_sheet", "gate_set", "gate", "node", "x_m", "y_m", "normal_x", "normal_y",
             "width_m", "areal_scale", "epoch", "sampling", "v_normal_m_per_yr",
             "v_normal_error_m_per_yr", "speed_m_per_yr", "count"]]
    spec = [("gate-01", 0, 5, 3), ("gate-01", 1, 6, 3), ("gate-01", 2, 7, 3),
            ("gate-02", 3, 5, 25), ("gate-02", 4, 6, 25),
            ("gate-03", 5, 36, 3)]
    for epoch in ("2020-01", "2021-01"):
        for gate, node, col, row in spec:
            rows.append(["greenland", "toy-gates", gate, node,
                         f"{-300000.0 + 150.0 * col:.2f}", f"{-1200000.0 - 150.0 * row:.2f}",
                         "1.0", "0.0", "150.0", "1.0", epoch, "annual", "900.0", "9.0",
                         "900.0", "7"])
    with p.open("w", encoding="utf-8", newline="") as f:
        csv.writer(f).writerows(rows)


def selftest():
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        g = td / "toy-bedmachine.nc"; write_toy(g, 3413)
        nodes_csv = td / "velocity.csv"; write_toy_nodes(nodes_csv)
        out, st = td / "thickness.csv", td / "thickness-stamp.json"
        stamp = run("greenland", g, nodes_csv, out, st, None)
        rows = list(csv.DictReader(out.open()))
        assert len(rows) == 6, rows
        by = {(r["gate"], int(r["node"])): r for r in rows}
        # the ramp is 100 + 10 times the column, and the error 20 plus half the row
        assert abs(float(by[("gate-01", 0)]["thickness_m"]) - 150.0) < 1e-6, by[("gate-01", 0)]
        assert abs(float(by[("gate-01", 2)]["thickness_m"]) - 170.0) < 1e-6, by[("gate-01", 2)]
        assert abs(float(by[("gate-01", 0)]["thickness_error_m"]) - 21.5) < 1e-6
        # the source band: rows below 20 are mass conservation, above it interpolation
        assert by[("gate-01", 0)]["provenance"] == "mass_conservation", by[("gate-01", 0)]
        assert by[("gate-02", 3)]["provenance"] == "interpolation", by[("gate-02", 3)]
        # the floating strip is read as floating ice, not as grounded
        assert by[("gate-03", 5)]["mask"] == "floating_ice", by[("gate-03", 5)]
        assert by[("gate-01", 1)]["mask"] == "grounded_ice", by[("gate-01", 1)]
        assert stamp["nodes_by_provenance"] == {"mass_conservation": 4, "interpolation": 2}, stamp["nodes_by_provenance"]
        assert stamp["nodes_by_mask"] == {"grounded_ice": 5, "floating_ice": 1}
        assert stamp["provenance_not_supporting_a_discharge"] == ["interpolation"]
        assert stamp["series"]["greenland"]["granule_sha256"].startswith("sha256:")
        assert stamp["series"]["greenland"]["n_nodes"] == 6
        # the same node table sampled for a gate set that is not there refuses
        try:
            run("greenland", g, nodes_csv, td / "x.csv", None, "no-such-set")
            raise AssertionError("a missing gate set was not refused")
        except SystemExit as e:
            assert "carries no nodes" in str(e), e
        print("iio_thickness_bedmachine selftest: 6 nodes, thickness ramp and error recovered, "
              "4 mass conservation and 2 interpolation, 1 floating node marked; OK")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--ice-sheet", choices=sorted(PRODUCTS))
    ap.add_argument("--bedmachine", type=Path)
    ap.add_argument("--nodes", type=Path, help="the velocity.csv whose node table to sample")
    ap.add_argument("--gate-set", default=None)
    ap.add_argument("--out", type=Path)
    ap.add_argument("--stamp-out", type=Path)
    ap.add_argument("--fetch-to", type=Path)
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        selftest(); return
    if not (a.ice_sheet and a.bedmachine and a.nodes and a.out):
        ap.error("--ice-sheet, --bedmachine, --nodes and --out are required")
    if not a.bedmachine.is_file():
        if not a.fetch_to:
            sys.exit(f"{a.bedmachine} does not exist (give --fetch-to DIR to download it)")
        fetch(PRODUCTS[a.ice_sheet]["url"], a.bedmachine)
    run(a.ice_sheet, a.bedmachine, a.nodes, a.out, a.stamp_out, a.gate_set)


if __name__ == "__main__":
    main()
