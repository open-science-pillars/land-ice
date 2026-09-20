#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Assemble and stamp the data root of the ice sheet input-output
balance: the term files the loaders wrote and the RECORD.json a
computation reads before the CSVs.

The terms: velocity (the surface velocity normal to each flux gate
node, per epoch, iio_velocity_itslive.py), thickness (the ice
thickness at the same nodes with the method that made each pixel,
iio_thickness_bedmachine.py) and smb (the surface mass balance over a
stated ice sheet domain, iio_smb_gemb.py). Only velocity is required,
because a root is worth stamping as soon as one factor of the
discharge is in it; thickness and smb are optional, and a root
without one names the reason in the record (--absent), so a
computation asked for an input-output balance finds the gap here
rather than in a missing file.

The stamp carries the record name, the SHA-256 manifest of every term
file, the time of stamping, the loaders' own stamps (what each read,
from where, when, with which hash, and how it sampled), and the
bookkeeping table: per term the product and its version, the grid,
the mask, the aggregation, the units, the sign convention and the
uncertainty basis; the gate table, which says for each gate set which
ice sheet it belongs to, how many gates and nodes it holds, the rule
that placed them, whether it spans the ice sheet's margin and which
product's mask decided that a node is grounded; and the closure
table, which says per ice sheet which terms this root can supply to
an input-output balance and which it cannot, so a refusal is
traceable to one file.

Usage:
  iio_data_root.py --root DIR --record NAME [--absent "TERM: reason" ...]
      DIR holds <term>.csv and <term>-stamp.json for every term present
  --check     verify an existing RECORD.json against the files (exit 1 on drift)
  --selftest  build and check a small root the tool writes itself
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import sys
import tempfile
from pathlib import Path

REQUIRED_TERMS = ("velocity",)
OPTIONAL_TERMS = ("thickness", "smb")
TERMS = REQUIRED_TERMS + OPTIONAL_TERMS


def sha256(p: Path) -> str:
    return "sha256:" + hashlib.sha256(p.read_bytes()).hexdigest()


def present_terms(root: Path) -> list:
    return [t for t in TERMS if (root / f"{t}.csv").is_file()]


def manifest(root: Path, terms) -> dict:
    out = {}
    for t in terms:
        p = root / f"{t}.csv"
        if not p.is_file():
            sys.exit(f"{root} lacks {t}.csv")
        out[p.name] = sha256(p)
    return out


def per_series(stamp: dict, key: str) -> dict:
    return {name: s.get(key, "") for name, s in stamp.get("series", {}).items()}


def product_rows(stamp: dict) -> dict:
    return {name: f"{s.get('product', '')} (product version {s.get('product_version', '')}, "
                  f"doi {s.get('doi', '')})"
            for name, s in stamp.get("series", {}).items()}


def coverage(stamp: dict) -> dict:
    return {name: {"months": s.get("months"), "n_steps": s.get("n_steps") or s.get("n_epochs"),
                   "n_nodes": s.get("n_nodes"), "cells": s.get("cells"),
                   "area_km2": s.get("area_km2")}
            for name, s in stamp.get("series", {}).items()}


def velocity_row(st: dict) -> dict:
    return {
        "product_and_version": product_rows(st),
        "archive_collection": per_series(st, "archive_collection"),
        "archive_version": per_series(st, "archive_version"),
        "version_note": per_series(st, "version_note"),
        "region": per_series(st, "region"),
        "grid": per_series(st, "grid"),
        "mask": per_series(st, "mask"),
        "aggregation": per_series(st, "aggregation"),
        "sampling": per_series(st, "sampling"),
        "epochs": per_series(st, "epochs"),
        "coverage": coverage(st),
        "units": st.get("units", ""),
        "sign_convention": st.get("sign_convention", ""),
        "uncertainty_basis": per_series(st, "uncertainty_basis"),
        "map_units": per_series(st, "map_units"),
        "nodes_without_velocity": per_series(st, "nodes_without_velocity"),
        "granules": {name: [{k: g.get(k) for k in ("epoch", "granule", "granule_sha256",
                                                    "source_url", "read_utc")}
                            for g in (s.get("granules") or [])]
                     for name, s in st.get("series", {}).items()},
        "alternates_not_read": st.get("alternates_not_read", []),
    }


def thickness_row(st: dict) -> dict:
    return {
        "product_and_version": product_rows(st),
        "short_name": per_series(st, "short_name"),
        "grid": per_series(st, "grid"),
        "nominal_year": per_series(st, "nominal_year"),
        "mask": per_series(st, "mask"),
        "source_variable": per_series(st, "source_variable"),
        "aggregation": per_series(st, "aggregation"),
        "sampling": per_series(st, "sampling"),
        "coverage": coverage(st),
        "units": st.get("units", ""),
        "sign_convention": st.get("sign_convention", ""),
        "uncertainty_basis": per_series(st, "uncertainty_basis"),
        "nodes_by_provenance": st.get("nodes_by_provenance", {}),
        "nodes_by_mask": st.get("nodes_by_mask", {}),
        "provenance_rule": "a gate node carries a discharge only where the thickness at it was "
                           "made by mass conservation; the method is the product's own source "
                           "variable, written as a word in the provenance column of every row",
        "alternates_not_read": st.get("alternates_not_read", []),
    }


def smb_row(st: dict) -> dict:
    return {
        "product_and_version": product_rows(st),
        "short_name": per_series(st, "short_name"),
        "gemb_version": per_series(st, "gemb_version"),
        "forcing": per_series(st, "forcing"),
        "grid": per_series(st, "grid"),
        "mask": per_series(st, "mask"),
        "aggregation": per_series(st, "aggregation"),
        "sampling": per_series(st, "sampling"),
        "coverage": coverage(st),
        "units": st.get("units", ""),
        "sign_convention": st.get("sign_convention", ""),
        "uncertainty_basis": per_series(st, "uncertainty_basis"),
        "grounded_domains": st.get("grounded_domains", []),
        "grounded_note": st.get("grounded_note", ""),
        "not_in_the_distribution": st.get("not_in_the_distribution", []),
        "alternates_not_read": st.get("alternates_not_read", []),
    }


ROWS = {"velocity": velocity_row, "thickness": thickness_row, "smb": smb_row}


def gate_table(root: Path, stamps: dict) -> dict:
    """One entry per gate set, from the velocity stamp and, where the
    thickness term is present, the node counts by method and mask."""
    out = {}
    gs = (stamps.get("velocity") or {}).get("gate_set") or {}
    if gs:
        out[gs.get("name", "unnamed")] = {
            "ice_sheet": gs.get("ice_sheet"),
            "n_gates": gs.get("n_gates"),
            "n_nodes": gs.get("n_nodes"),
            "node_width_m": gs.get("node_width_m"),
            "rule": gs.get("rule"),
            "reference_year": gs.get("reference_year"),
            "spans_margin": gs.get("spans_margin"),
            "spans_margin_note": gs.get("spans_margin_note"),
            "grounded_by": gs.get("grounded_by"),
            "mask_cells": gs.get("mask_cells"),
            "thickness": {
                "nodes_by_provenance": (stamps.get("thickness") or {}).get("nodes_by_provenance"),
                "nodes_by_mask": (stamps.get("thickness") or {}).get("nodes_by_mask"),
            } if "thickness" in stamps else {"absent": "no thickness term in this root"},
        }
    return out


def ice_sheets_present(root: Path, terms) -> dict:
    """The ice sheet and domain labels each term file actually holds."""
    out = {}
    for t in terms:
        seen = set()
        with (root / f"{t}.csv").open(encoding="utf-8") as f:
            for r in csv.DictReader(f):
                seen.add((r.get("ice_sheet", ""), r.get("gate_set") or r.get("domain") or ""))
        out[t] = sorted(f"{a}/{b}" for a, b in seen)
    return out


def closure_table(present: dict, absent: dict, labels: dict, gates: dict) -> dict:
    """Per ice sheet, which terms this root can supply to an
    input-output balance and which it cannot."""
    table = {}
    for sheet in ("greenland", "antarctica"):
        vel = [s for s in labels.get("velocity", []) if s.startswith(sheet + "/")]
        thk = [s for s in labels.get("thickness", []) if s.startswith(sheet + "/")]
        smb = [s for s in labels.get("smb", []) if s.startswith(sheet + "/")]
        grounded_smb = [s for s in smb if s.endswith("/grounded") or s.endswith("/ice_sheet")]
        entry = {
            "velocity": (f"gate nodes for {vel}" if vel else
                         "not possible from this root: it holds no velocity rows for this ice sheet"),
            "thickness": (f"thickness at the gate nodes for {thk}" if thk else
                          "not possible from this root: " + absent.get(
                              "thickness", "it holds no thickness rows for this ice sheet")),
            "surface_mass_balance": (f"surface mass balance over {grounded_smb}" if grounded_smb else
                                     "not possible from this root: " + absent.get(
                                         "smb", "it holds no grounded surface mass balance rows "
                                                "for this ice sheet"
                                         + (f"; the domains it does hold are {smb}" if smb else ""))),
        }
        entry["input_output"] = (
            "possible: every term is present"
            if vel and thk and grounded_smb else
            "not possible from this root: the computation refuses for the first term above that "
            "is not possible")
        entry["gate_sets"] = sorted(k for k, v in gates.items() if v.get("ice_sheet") == sheet)
        table[sheet] = entry
    return table


def bookkeeping(root: Path, stamps: dict, absent: dict, terms) -> dict:
    table = {t: ROWS[t](st) for t, st in stamps.items()}
    for term, reason in absent.items():
        table[term] = {"absent": reason}
    labels = ice_sheets_present(root, terms)
    table["labels_present"] = labels
    table["gates"] = gate_table(root, stamps)
    table["closure"] = closure_table(terms, absent, labels, table["gates"])
    table["reading_rule"] = (
        "a computation reads velocity rows by ice_sheet, gate_set, gate, node and epoch and by "
        "the sampling column, thickness rows by ice_sheet, gate_set, gate and node, and smb "
        "rows by ice_sheet, domain and month; a quarterly row is one product time step labelled "
        "by the month of its time value, an annual row is one composite labelled by the January "
        "of its year, and no epoch is ever filled")
    table["discharge_rule"] = (
        "the discharge through a gate set at an epoch is the sum over its nodes of the ice "
        "density times the velocity normal to the gate times the node width divided by the "
        "projection's areal scale at the node times the thickness at the node, in gigatonnes "
        "per year; the areal scale brings a map velocity and a map width to the ground, and the "
        "thickness is of the thickness product's nominal year, not of the velocity epoch")
    return table


def parse_absent(items) -> dict:
    out = {}
    for item in items or []:
        term, _, reason = item.partition(":")
        term, reason = term.strip(), reason.strip()
        if term not in OPTIONAL_TERMS or not reason:
            sys.exit(f"--absent takes 'TERM: reason' with TERM one of {OPTIONAL_TERMS}, got {item!r}")
        out[term] = reason
    return out


def build(root: Path, record: str, absent: dict):
    terms = present_terms(root)
    for t in REQUIRED_TERMS:
        if t not in terms:
            sys.exit(f"{root} lacks {t}.csv (a required term)")
    for t in OPTIONAL_TERMS:
        if t not in terms and t not in absent:
            sys.exit(f"{root} lacks {t}.csv and no --absent reason was given for it")
        if t in terms and t in absent:
            sys.exit(f"{t}.csv is present; it cannot also be declared absent")
    stamps = {}
    for t in terms:
        p = root / f"{t}-stamp.json"
        if not p.is_file():
            sys.exit(f"{root} lacks {t}-stamp.json (the loader's stamp)")
        stamps[t] = json.loads(p.read_text(encoding="utf-8"))
    files = manifest(root, terms)
    mh = hashlib.sha256("\n".join(f"{k} {v}" for k, v in sorted(files.items())).encode()).hexdigest()
    stamp = {
        "record": record,
        "manifest": files,
        "manifest_sha256": "sha256:" + mh,
        "verified_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "terms_present": terms,
        "terms_absent": absent,
        "terms": stamps,
        "bookkeeping": bookkeeping(root, stamps, absent, terms),
    }
    (root / "RECORD.json").write_text(json.dumps(stamp, indent=2) + "\n", encoding="utf-8")
    print(f"RECORD.json written for {record}: manifest sha256:{mh[:16]}, "
          + ", ".join(f"{t} {stamps[t]['months'][0]} to {stamps[t]['months'][1]}"
                      if stamps[t].get("months", ["", ""])[0] else f"{t} static"
                      for t in terms)
          + (f"; absent: {', '.join(absent)}" if absent else ""))


def check(root: Path):
    p = root / "RECORD.json"
    if not p.is_file():
        sys.exit(f"{root} lacks RECORD.json")
    stamp = json.loads(p.read_text(encoding="utf-8"))
    terms = stamp.get("terms_present") or list(stamp.get("terms", {}))
    for t in REQUIRED_TERMS:
        if t not in terms:
            sys.exit(f"RECORD.json does not list the required term {t}")
    files = manifest(root, terms)
    if files != stamp.get("manifest"):
        sys.exit("RECORD.json manifest does not match the files")
    for t in terms:
        if t not in stamp.get("terms", {}) or t not in stamp.get("bookkeeping", {}):
            sys.exit(f"RECORD.json lacks the {t} stamp or its bookkeeping row")
        if not (root / f"{t}-stamp.json").is_file():
            sys.exit(f"{root} lacks {t}-stamp.json")
    for t, reason in (stamp.get("terms_absent") or {}).items():
        if (root / f"{t}.csv").is_file():
            sys.exit(f"RECORD.json declares {t} absent but {t}.csv is in the tree")
        if not reason:
            sys.exit(f"RECORD.json declares {t} absent without a reason")
    book = stamp.get("bookkeeping", {})
    for key in ("closure", "gates", "reading_rule", "discharge_rule"):
        if key not in book:
            sys.exit(f"RECORD.json bookkeeping lacks the {key} entry")
    print(f"RECORD.json matches the files ({', '.join(terms)}"
          + (f"; absent: {', '.join(stamp['terms_absent'])}" if stamp.get("terms_absent") else "")
          + ")")


def write_toy(root: Path, with_thickness: bool) -> None:
    """A small root the selftest builds itself: one gate of two nodes,
    two epochs of velocity, and a thickness term when asked for one."""
    root.mkdir(parents=True, exist_ok=True)
    vel = [["ice_sheet", "gate_set", "gate", "node", "x_m", "y_m", "normal_x", "normal_y",
            "width_m", "areal_scale", "epoch", "sampling", "v_normal_m_per_yr",
            "v_normal_error_m_per_yr", "speed_m_per_yr", "count"]]
    for epoch in ("2020-01", "2021-01"):
        for node in (0, 1):
            vel.append(["greenland", "toy-gates", "gate-01", node, 0.0 + 120 * node, -1000.0,
                        1.0, 0.0, 120.0, 1.0, epoch, "annual", 900.0, 9.0, 900.0, 7])
    with (root / "velocity.csv").open("w", encoding="utf-8", newline="") as f:
        csv.writer(f).writerows(vel)
    (root / "velocity-stamp.json").write_text(json.dumps({
        "term": "velocity", "months": ["2020-01", "2021-01"], "units": "m/yr",
        "sign_convention": "positive along the normal",
        "gate_set": {"name": "toy-gates", "ice_sheet": "greenland", "n_gates": 1, "n_nodes": 2,
                     "node_width_m": 120.0, "rule": "a toy gate", "spans_margin": False,
                     "grounded_by": "the toy mask"},
        "series": {"greenland": {"product": "toy", "product_version": "0", "doi": "",
                                 "epochs": ["2020-01", "2021-01"], "n_epochs": 2}},
    }, indent=2) + "\n", encoding="utf-8")
    if with_thickness:
        thk = [["ice_sheet", "gate_set", "gate", "node", "x_m", "y_m", "thickness_m",
                "thickness_error_m", "source_code", "provenance", "mask_code", "mask"]]
        for node in (0, 1):
            thk.append(["greenland", "toy-gates", "gate-01", node, 0.0 + 120 * node, -1000.0,
                        800.0, 40.0, 2, "mass_conservation", 2, "grounded_ice"])
        with (root / "thickness.csv").open("w", encoding="utf-8", newline="") as f:
            csv.writer(f).writerows(thk)
        (root / "thickness-stamp.json").write_text(json.dumps({
            "term": "thickness", "months": ["", ""], "units": "m",
            "nodes_by_provenance": {"mass_conservation": 2},
            "nodes_by_mask": {"grounded_ice": 2},
            "series": {"greenland": {"product": "toy bed", "product_version": "0", "doi": "",
                                     "n_nodes": 2}},
        }, indent=2) + "\n", encoding="utf-8")


def selftest():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td) / "root"
        write_toy(root, with_thickness=True)
        # a term with no file and no reason is refused
        try:
            build(root, "toy", {})
            raise AssertionError("an undeclared absent term was not refused")
        except SystemExit as e:
            assert "smb.csv" in str(e), e
        build(root, "toy", {"smb": "selftest: no surface mass balance was read"})
        rec = json.loads((root / "RECORD.json").read_text(encoding="utf-8"))
        assert rec["terms_present"] == ["velocity", "thickness"], rec["terms_present"]
        assert rec["terms_absent"] == {"smb": "selftest: no surface mass balance was read"}
        book = rec["bookkeeping"]
        assert book["gates"]["toy-gates"]["spans_margin"] is False, book["gates"]
        assert book["gates"]["toy-gates"]["thickness"]["nodes_by_provenance"] == {"mass_conservation": 2}
        assert book["labels_present"]["velocity"] == ["greenland/toy-gates"], book["labels_present"]
        gl = book["closure"]["greenland"]
        assert gl["input_output"].startswith("not possible"), gl
        assert "no surface mass balance was read" in gl["surface_mass_balance"], gl
        assert book["closure"]["antarctica"]["velocity"].startswith("not possible"), book["closure"]
        assert "discharge_rule" in book and "reading_rule" in book
        check(root)
        # a term file edited after the stamp fails the check
        (root / "velocity.csv").write_text(
            (root / "velocity.csv").read_text(encoding="utf-8") + "\n", encoding="utf-8")
        try:
            check(root)
            raise AssertionError("a drifted term file passed the check")
        except SystemExit as e:
            assert "manifest" in str(e), e
        # a root without the required term is refused
        bare = Path(td) / "bare"
        bare.mkdir()
        try:
            build(bare, "bare", {})
            raise AssertionError("a root without the velocity term was not refused")
        except SystemExit as e:
            assert "velocity.csv" in str(e), e
    print("iio_data_root selftest: build, absent terms, the gate and closure tables, the check "
          "and its drift refusal; OK")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--root", type=Path)
    ap.add_argument("--record")
    ap.add_argument("--absent", nargs="*", help="'TERM: reason' for an optional term not in the tree")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        selftest(); return
    if not a.root:
        ap.error("--root is required")
    if a.check:
        check(a.root); return
    if not a.record:
        ap.error("--record is required to build")
    build(a.root, a.record, parse_absent(a.absent))


if __name__ == "__main__":
    main()
