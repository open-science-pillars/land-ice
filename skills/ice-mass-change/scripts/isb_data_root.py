#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Assemble and stamp the data root of the ice sheet mass balance
closure: the term files the loaders wrote and the RECORD.json a
computation reads before the CSVs.

The terms: firn (firn air content anomaly, isb_firn_gemb.py), smb
(surface mass balance, isb_smb_gemb.py), mass (the JPL mascon sum per
ice sheet, isb_mass_mascons.py) and the altimetric volume, from the
ITS_LIVE elevation change products (volume-itslive,
isb_volume_itslive.py) and, when its granules could be fetched, from
ICESat-2 ATL15 (volume-atl15, isb_volume_atl15.py). The first four are
required; volume-atl15 is optional, and a root without it names the
reason in the record (--absent), so a computation asked for the ATL15
term finds the gap here rather than in a missing file.

The stamp carries the record name, the SHA-256 manifest of every term
file, the time of stamping, the loaders' own stamps (what each read,
from where, when, with which hash, and how it aggregated), and the
bookkeeping table: per term the product and its version, the grid,
the mask and aggregation, the units, the sign convention, the
uncertainty basis and the alternates not read; for the mass term the
GIA model, the low-degree series, the reference frame, the smoothing
and the mascon selection per ice sheet with its provider cross-check;
plus the closure table, which says per ice sheet which terms this
root can supply to the closure and which it cannot (no grounded
Antarctic firn term, no surface mass balance or discharge for an
input-output estimate), so a refusal is traceable to one file. The
statements are read from the loaders' stamps where the loader
determined them and written down here so a reader auditing a closure
residual starts in one file.

Usage:
  isb_data_root.py --root DIR --record NAME [--absent "TERM: reason" ...]
      DIR holds <term>.csv and <term>-stamp.json for every term present
  --check   verify an existing RECORD.json against the files (exit 1 on drift)
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import sys
from pathlib import Path

REQUIRED_TERMS = ("firn", "smb", "mass", "volume-itslive")
OPTIONAL_TERMS = ("volume-atl15",)
TERMS = REQUIRED_TERMS + OPTIONAL_TERMS


def sha256(p: Path) -> str:
    return "sha256:" + hashlib.sha256(p.read_bytes()).hexdigest()


def present_terms(root: Path) -> list[str]:
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


def coverage(stamp: dict) -> dict:
    return {name: {"months": s.get("months"), "n_steps": s.get("n_steps"),
                   "cells": s.get("cells"), "area_km2": s.get("area_km2")}
            for name, s in stamp.get("series", {}).items()}


def product_rows(stamp: dict) -> dict:
    return {name: f"{s.get('product', '')} (product version {s.get('product_version', '')}, "
                  f"doi {s.get('doi', '')})"
            for name, s in stamp.get("series", {}).items()}


def gemb_row(term: str, st: dict) -> dict:
    return {
        "product_and_version": product_rows(st),
        "gemb_version": per_series(st, "gemb_version"),
        "forcing": per_series(st, "forcing"),
        "grid": per_series(st, "grid"),
        "mask": per_series(st, "mask"),
        "aggregation": per_series(st, "aggregation"),
        "reference": per_series(st, "reference"),
        "sampling": per_series(st, "sampling"),
        "coverage": coverage(st),
        "units": st.get("units", ""),
        "sign_convention": st.get("sign_convention", ""),
        "uncertainty_basis": per_series(st, "uncertainty_basis"),
        "not_in_the_distribution": st.get("not_in_the_distribution", []),
        "alternates_not_read": st.get("alternates_not_read", []),
    }


def mass_row(st: dict) -> dict:
    series = st.get("series", {})
    return {
        "product_and_version": {name: f"{st.get('product', '')} (product version "
                                      f"{st.get('product_version', '')}, doi {st.get('doi', '')})"
                                for name in series},
        "grid": st.get("grid", ""),
        "mask": st.get("mask", ""),
        "selection": {name: {"rule": s.get("rule", ""), "n_mascons": s.get("n_mascons"),
                             "land_area_km2": s.get("land_area_km2"),
                             "ice_mask": {k: v for k, v in (s.get("ice_mask") or {}).items()
                                          if k in ("file", "file_sha256", "ice_area_km2",
                                                   "ice_area_in_selected_mascons_km2")} or None,
                             "selection_sensitivity": s.get("selection_sensitivity")}
                      for name, s in series.items()},
        "aggregation": st.get("aggregation", ""),
        "reference": st.get("reference", ""),
        "sampling": st.get("sampling", ""),
        "coverage": {name: {"months": st.get("months"), "n_steps": st.get("n_solutions"),
                            "n_mascons": s.get("n_mascons"), "land_area_km2": s.get("land_area_km2")}
                     for name, s in series.items()},
        "units": st.get("units", ""),
        "sign_convention": st.get("sign_convention", ""),
        "uncertainty_basis": st.get("uncertainty_basis", ""),
        "gia": st.get("bookkeeping", {}).get("gia", ""),
        "low_degree": st.get("bookkeeping", {}).get("low_degree", ""),
        "reference_frame": st.get("bookkeeping", {}).get("reference_frame", ""),
        "effective_smoothing": st.get("bookkeeping", {}).get("effective_smoothing", ""),
        "gad": st.get("bookkeeping", {}).get("gad", ""),
        "elastic_and_hydrology": st.get("bookkeeping", {}).get("elastic_and_hydrology", ""),
        "provider_cross_check": {name: {k: v for k, v in c.items() if k != "rule"}
                                 for name, c in st.get("provider_cross_check", {}).items()},
    }


def volume_row(st: dict) -> dict:
    return {
        "product_and_version": product_rows(st),
        "grid": {name: (s.get("grid") or (s.get("granules") or [{}])[0].get("grid", ""))
                 for name, s in st.get("series", {}).items()},
        "mask": per_series(st, "mask"),
        "aggregation": per_series(st, "aggregation"),
        "reference": per_series(st, "reference"),
        "sampling": per_series(st, "sampling"),
        "coverage": coverage(st),
        "units": st.get("units", ""),
        "sign_convention": st.get("sign_convention", ""),
        "uncertainty_basis": per_series(st, "uncertainty_basis"),
        "not_mass": st.get("not_mass", ""),
    }


def bookkeeping(stamps: dict, absent: dict) -> dict:
    table = {}
    for term, st in stamps.items():
        if term in ("firn", "smb"):
            table[term] = gemb_row(term, st)
        elif term == "mass":
            table[term] = mass_row(st)
        else:
            table[term] = volume_row(st)
    for term, reason in absent.items():
        table[term] = {"absent": reason}
    table["domains"] = {
        "greenland/ice_sheet": "the grounded Greenland Ice Sheet (mask 1 of the ITS_LIVE Greenland "
                               "product); firn and volume-itslive",
        "greenland/peripheral_glaciers": "the peripheral glaciers of Greenland (mask 2); firn and "
                                         "volume-itslive",
        "greenland/land_mascons": "the JPL land mascons selected for Greenland by the mass stamp's "
                                  "rule: the ice sheet, the peripheral glaciers and the ice-free "
                                  "land and coastal ocean inside those mascons; mass",
        "greenland/gl": "the ATL15 GL region (ice sheet and peripheral ice caps, undivided); "
                        "volume-atl15 when present",
        "antarctica/ice_shelves": "the floating Antarctic ice shelves (ID 1 to 182 of the ice shelf "
                                  "product); firn and surface mass balance; not the grounded ice sheet",
        "antarctica/land_mascons": "every JPL land mascon south of 60 S: the grounded sheet and the "
                                   "floating shelves together; mass",
        "antarctica/grounded": "the grounded Antarctic Ice Sheet of the ITS_LIVE grounded product; "
                               "volume-itslive when present",
        "antarctica/a1_a4": "the four ATL15 Antarctic quadrants summed, grounded and floating "
                            "together; volume-atl15 when present",
    }
    have = {(r[0], r[1]) for t in stamps for r in
            (tuple(d) for d in stamps[t].get("domains", []))}
    table["closure"] = {
        "greenland": {
            "gravimetry": "mass over greenland/land_mascons",
            "altimetry": "volume over greenland/ice_sheet plus greenland/peripheral_glaciers "
                         "(volume-itslive) or over greenland/gl (volume-atl15), less the firn air "
                         "content volume over the same two firn domains, times a stated ice density",
            "input_output": "not possible from this root: it holds no Greenland surface mass balance "
                            "and no discharge; the published input-output estimates are IMBIE's "
                            "input-output group (Otosaka and others 2023)",
        },
        "antarctica": {
            "gravimetry": "mass over antarctica/land_mascons",
            "altimetry": "not possible from this root: the firn term covers the floating ice shelves "
                         "only (antarctica/ice_shelves) and no grounded Antarctic firn air content "
                         "field is in the ITS_LIVE distribution, so the grounded volume "
                         + ("(antarctica/grounded, present) " if ("antarctica", "grounded") in have
                            else "(antarctica/grounded, absent) ")
                         + "cannot be converted to mass; the computation refuses",
            "input_output": "not possible from this root: the surface mass balance covers the ice "
                            "shelves only and there is no discharge",
        },
    }
    table["reading_rule"] = ("a computation reads rows by ice_sheet and domain and by the sampling "
                             "column; a quarterly row is one product time step labelled by the "
                             "month of its time value, not a monthly value, and no month is ever "
                             "filled")
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
        "bookkeeping": bookkeeping(stamps, absent),
    }
    (root / "RECORD.json").write_text(json.dumps(stamp, indent=2) + "\n", encoding="utf-8")
    print(f"RECORD.json written for {record}: manifest sha256:{mh[:16]}, "
          + ", ".join(f"{t} {stamps[t]['months'][0]} to {stamps[t]['months'][1]}" for t in terms)
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
    if "closure" not in stamp.get("bookkeeping", {}):
        sys.exit("RECORD.json bookkeeping lacks the closure table")
    print(f"RECORD.json matches the files ({', '.join(terms)}"
          + (f"; absent: {', '.join(stamp['terms_absent'])}" if stamp.get("terms_absent") else "") + ")")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--root", type=Path, required=True)
    ap.add_argument("--record")
    ap.add_argument("--absent", nargs="*", help="'TERM: reason' for an optional term not in the tree")
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    if a.check:
        check(a.root); return
    if not a.record:
        ap.error("--record is required to build")
    build(a.root, a.record, parse_absent(a.absent))


if __name__ == "__main__":
    main()
