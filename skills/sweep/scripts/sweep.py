#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Sweep one declared parameter of an attested computation and table the
receipts, computing nothing.

This is the ocean-science sweep's command line and output shape over
the nsidc bundle's two closures, so that a reader who knows one knows
both: the same flags, the same three files, the same five refusals with
the same reason codes and the same exit codes.

The concept of a computation states its boundaries in prose, often from
a handful of runs someone made by hand. The ice sheet balance concept's
boundaries quote seven windows run that way and conclude that the
closure verdict is window dependent on the committed root, with the
altimetry term as the suspect. This script turns that sentence into a
measured table: it runs the sanctioned executor once per value of one
parameter the concept declares, runs the attester on every receipt
BEFORE reading a field out of it, and writes the executor's own
headline fields as a CSV, a markdown table and a JSON manifest that
names every receipt with the attester's verdict line, so a reader can
follow any cell back to a receipt that passed.

Every cell of the table is a field of one receipt, read by the path the
catalog below records. The script fits nothing, averages nothing and
carries no expected value of its own. A run the executor refused is a
row carrying its reason code, never a skipped row, because a refusal is
part of the measurement: the input-output computation's record run on
the committed root refuses, and a sweep of it tables that refusal
rather than an estimate nobody has made.

What it refuses, each with exit 4 and a reason code, and never a
partial table:

  aggregate-across-rows   any aggregate over the rows (--aggregate):
                          a mean, a headline mass rate for the ice
                          sheet, a count of closures read as a rate.
                          Those are numbers no concept owns, and the
                          headline mass rate is the one the
                          land-ice/ice-mass-change skill already
                          forbids in its Must NOT list. A capability
                          that computes a number of its own is domain
                          expansion under ADR D of the marketplace
                          decisions and waits on the ablation; a sweep
                          is a wrap, so it stops here and says which
                          single receipt a reader may quote instead.
  parameter-not-declared  a parameter the concept does not declare
                          (the declared set is read from the concept's
                          Parameters in its frontmatter, not from a
                          list kept here).
  parameter-not-stated    a declared parameter that the command line
                          neither sweeps nor fixes: every run states
                          the swept parameter, its values and the fixed
                          value of every other parameter.
  mixed-method            two receipts in one sweep whose executor
                          digest (code_sha256) differs, so the table
                          would be two methods.
  mixed-input             two receipts in one sweep whose input
                          identity differs (the data root's record and
                          manifest digest, or the fixture's seed and
                          digest), so the table would be two roots.

The executor, the attester and the concept are reached at the installed
provider bundle's path, the way the wrapping skills in this capability
reach them: the installer's record (`claude plugin list --json`), or a
checkout named by NASA_DAAC_KNOWLEDGE. Nothing is copied here.

Usage:
  sweep.py --computation ice-sheet-balance --parameter window \
      --values 2003-01:2009-12,2010-01:2016-12 \
      --fixed ice_sheet=greenland --fixed altimetry=itslive \
      --fixed ice_density=917 --fixed bridge=unbound \
      --input fixture --seed 7 --runtime claude-code --out-dir DIR

  sweep.py --computation ice-sheet-balance --parameter window \
      --windows 48:12 --span 2003-01:2016-12 \
      --fixed ice_sheet=greenland --fixed altimetry=itslive \
      --fixed ice_density=917 --fixed bridge=unbound \
      --input data-root --data-root DIR --runtime claude-code --out-dir DIR

  sweep.py --selftest
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

PROVIDER_PLUGIN = "nasa-daac-knowledge"
BUNDLE = "nsidc"

# One entry per computation this sweep can drive. The columns are the
# receipt fields the concept's Reference run section names, each a
# dotted path into the receipt: the table is those fields and nothing
# else. Adding a computation here adds no number; it names paths.
#
# The receipt states each term's headline rate rounded to four decimals
# (terms.<term>.rate_gt_per_yr) beside the full-precision interval the
# same rate carries (rates.<term>.ci_low and ci_high). A row therefore
# mixes the two precisions. That is the receipt's own bookkeeping and
# it is copied as it stands: rounding the intervals to match, or
# re-deriving the rate from the interval to unround it, would make a
# cell that no receipt carries.
CATALOG = {
    "ice-sheet-balance": {
        "concept": "computations/ice-sheet-balance.md",
        "executor": "references/computations/ice_sheet_balance.py",
        "attester": "references/attesters/ice_sheet_balance_check.py",
        "skill": "land-ice/ice-mass-change",
        "columns": [
            ("ice_sheet", "bound_parameters.ice_sheet"),
            ("window", "bound_parameters.window"),
            ("altimetry", "bound_parameters.altimetry"),
            ("ice_density_kg_m3", "bound_parameters.ice_density"),
            ("bridge", "bound_parameters.bridge"),
            ("months_calendar", "window.n_calendar"),
            ("gravimetry_epochs", "terms.gravimetry.n_epochs"),
            ("altimetry_epochs", "terms.altimetry.n_epochs"),
            ("common_differences", "residual.n_common_differences"),
            ("gravimetry_gt_per_yr", "terms.gravimetry.rate_gt_per_yr"),
            ("gravimetry_ci_low", "rates.gravimetry.ci_low"),
            ("gravimetry_ci_high", "rates.gravimetry.ci_high"),
            ("altimetry_gt_per_yr", "terms.altimetry.rate_gt_per_yr"),
            ("altimetry_ci_low", "rates.altimetry.ci_low"),
            ("altimetry_ci_high", "rates.altimetry.ci_high"),
            ("residual_gt_per_yr", "residual.rate_gt_per_yr"),
            ("residual_ci_low", "rates.residual.ci_low"),
            ("residual_ci_high", "rates.residual.ci_high"),
            ("selection_systematic_gt_per_yr",
             "combined_uncertainty.selection_systematic.value_gt_per_yr"),
            ("bar_gt_per_yr", "combined_uncertainty.bar_gt_per_yr"),
            ("closed_within_uncertainty", "verdict.closed_within_uncertainty"),
        ],
    },
    "ice-sheet-input-output": {
        "concept": "computations/ice-sheet-input-output.md",
        "executor": "references/computations/ice_sheet_input_output.py",
        "attester": "references/attesters/ice_sheet_input_output_check.py",
        "skill": "land-ice/ice-sheet-input-output",
        "columns": [
            ("ice_sheet", "bound_parameters.ice_sheet"),
            ("window", "bound_parameters.window"),
            ("gates", "bound_parameters.gates"),
            ("velocity_epoch", "bound_parameters.velocity_epoch"),
            ("ice_density_kg_m3", "bound_parameters.ice_density"),
            ("months_calendar", "window.n_calendar"),
            ("n_gates", "gates.n_gates"),
            ("n_nodes", "gates.n_nodes"),
            ("spans_margin", "gates.spans_margin"),
            ("epochs", "residual.n_epochs"),
            ("smb_gt_per_yr", "terms.smb.rate_gt_per_yr"),
            ("smb_ci_low", "rates.smb.ci_low"),
            ("smb_ci_high", "rates.smb.ci_high"),
            ("discharge_gt_per_yr", "terms.discharge.rate_gt_per_yr"),
            ("discharge_ci_low", "rates.discharge.ci_low"),
            ("discharge_ci_high", "rates.discharge.ci_high"),
            ("mass_rate_gt_per_yr", "residual.rate_gt_per_yr"),
            ("mass_rate_ci_low", "rates.mass_rate.ci_low"),
            ("mass_rate_ci_high", "rates.mass_rate.ci_high"),
            ("gate_systematic_gt_per_yr",
             "combined_uncertainty.gate_systematic.value_gt_per_yr"),
            ("bar_gt_per_yr", "combined_uncertainty.bar_gt_per_yr"),
            ("significant_at_confidence", "verdict.significant_at_confidence"),
            ("sign", "verdict.sign"),
        ],
    },
}

# Columns the sweep owns rather than the receipt: the bookkeeping that
# says whether a cell may be read at all.
STATUS_COLUMNS = ("status", "run_id", "reason_code")
UNBOUND = "unbound"
REFUSALS = ("aggregate-across-rows", "parameter-not-declared",
            "parameter-not-stated", "mixed-method", "mixed-input")


# ---- refusing

def refuse(code: str, message: str) -> int:
    print(f"SWEEP REFUSED ({code}): {message}")
    return 4


# ---- the installed bundle

def provider_root() -> Path:
    """The installed provider plugin's root, from the installer's record."""
    override = os.environ.get("NASA_DAAC_KNOWLEDGE")
    if override:
        return Path(override).expanduser().resolve()
    claude = shutil.which("claude")
    if claude is None:
        sys.exit("no `claude` on PATH to read the installed-plugin record; "
                 "set NASA_DAAC_KNOWLEDGE to a checkout of the provider "
                 "repository instead")
    rec = subprocess.run([claude, "plugin", "list", "--json"],
                         capture_output=True, text=True)
    if rec.returncode != 0:
        sys.exit(f"`claude plugin list --json` failed: {rec.stderr.strip()}")
    for entry in json.loads(rec.stdout):
        if entry.get("id", "").split("@")[0] != PROVIDER_PLUGIN:
            continue
        if not entry.get("enabled", True) or entry.get("errors"):
            sys.exit(f"{entry['id']} is installed but not usable: "
                     f"{entry.get('errors') or 'disabled'}")
        return Path(entry["installPath"])
    sys.exit(f"{PROVIDER_PLUGIN} is not installed; it arrives with this "
             "plugin's dependencies (`claude plugin install "
             "land-ice@open-science-pillars`), or set NASA_DAAC_KNOWLEDGE "
             "to a checkout of the provider repository")


def bundle_paths(computation: str):
    """The concept, the executor and the attester at the installed
    bundle's path; nothing is copied into this repository."""
    spec = CATALOG[computation]
    base = provider_root() / "knowledge" / BUNDLE
    paths = {k: base / spec[k] for k in ("concept", "executor", "attester")}
    for name, p in paths.items():
        if not p.is_file():
            sys.exit(f"the provider bundle carries no {name} for {computation} "
                     f"at {p}; the sweep needs {PROVIDER_PLUGIN} at a release "
                     "that ships it")
    return paths


def declared_parameters(concept: Path):
    """The parameter names the concept declares, read from its
    frontmatter's Parameters block rather than kept in a list here."""
    text = concept.read_text(encoding="utf-8")
    if not text.startswith("---"):
        sys.exit(f"{concept} carries no frontmatter to read parameters from")
    front = text.split("---", 2)[1]
    names, inside = [], False
    for line in front.splitlines():
        if re.match(r"^parameters:\s*$", line):
            inside = True
            continue
        if inside:
            if not line.startswith((" ", "\t")) and line.strip():
                break
            found = re.search(r"\bname:\s*['\"]?([A-Za-z0-9_-]+)", line)
            if found:
                names.append(found.group(1))
    if not names:
        sys.exit(f"{concept} declares no parameters; a sweep needs one to sweep")
    return names


# ---- the values swept

def month_index(label: str) -> int:
    y, m = label.split("-")
    return int(y) * 12 + int(m) - 1


def month_label(index: int) -> str:
    return f"{index // 12:04d}-{index % 12 + 1:02d}"


def windows(span: str, length: int, step: int):
    """Every window of `length` months stepping `step` months through
    `span`. Calendar arithmetic on the stated rule, so the values are
    explicit in the manifest and in every row; no science number is
    formed here."""
    first, last = span.split(":")
    out, start = [], month_index(first)
    while start + length - 1 <= month_index(last):
        out.append(f"{month_label(start)}:{month_label(start + length - 1)}")
        start += step
    if not out:
        sys.exit(f"no window of {length} months fits in {span}")
    return out


# ---- running, attesting, reading

def flag(parameter: str) -> str:
    """The executor's flag for a declared parameter. The concepts declare
    ice_sheet, ice_density and velocity_epoch with underscores and the
    executors take them with hyphens; the sweep states the concept's
    name everywhere a reader sees it and translates only here."""
    return "--" + parameter.replace("_", "-")


def run_executor(executor: Path, parameter: str, value: str, fixed: dict,
                 args, receipt: Path) -> subprocess.CompletedProcess:
    """One run of the sanctioned executor with every declared parameter
    stated: the swept one at this value, the others at their fixed
    values. Exit 3 is the executor's refusal and is a row, not a stop."""
    cmd = ["uv", "run", str(executor), flag(parameter), value,
           "--runtime", args.runtime, "--receipt", str(receipt)]
    for name, bound in fixed.items():
        if bound != UNBOUND:
            cmd += [flag(name), bound]
    if args.input == "fixture":
        cmd += ["--fixture", "--seed", str(args.seed)]
    else:
        cmd += ["--data-root", str(args.data_root)]
    if args.runtime_version:
        cmd += ["--runtime-version", args.runtime_version]
    if args.capability_root:
        cmd += ["--capability-root", str(args.capability_root)]
    return subprocess.run(cmd, capture_output=True, text=True)


def attest(attester: Path, receipt: Path, attestation: Path,
           data_root: Path | None = None):
    """The attester on this receipt, before any field of it is read.
    A data-root receipt is attested against the tree, so the term file
    digests are verified rather than taken on the executor's word.
    Returns (passed, the attester's own verdict line)."""
    cmd = ["uv", "run", str(attester), str(receipt), "--out", str(attestation)]
    if data_root is not None:
        cmd += ["--data-root", str(data_root)]
    run = subprocess.run(cmd, capture_output=True, text=True)
    text = (run.stdout or "").strip() or (run.stderr or "").strip()
    lines = [line for line in text.splitlines() if line.strip()]
    line = lines[-1] if lines else "the attester printed nothing"
    return run.returncode == 0 and line.startswith("PASS"), line


def field(receipt: dict, path: str):
    """One receipt field by its dotted path, or None where the receipt
    does not carry it (a refusal receipt carries no rate)."""
    node = receipt
    for part in path.split("."):
        if not isinstance(node, dict) or part not in node:
            return None
        node = node[part]
    return node


def method_identity(receipt: dict) -> str:
    return receipt.get("code_sha256") or ""


def input_identity(receipt: dict) -> dict:
    """What makes a table one root: the stamped record and its manifest
    digest for a data root, the seed and digest for a fixture."""
    data = receipt.get("data") or {}
    if data.get("mode") == "data-root":
        record = data.get("record") or {}
        return {"mode": "data-root", "data_root": data.get("data_root"),
                "record": record.get("record"),
                "manifest_sha256": record.get("manifest_sha256")}
    return {"mode": data.get("mode"), "seed": data.get("seed"),
            "digest": data.get("digest")}


def one_method(rows):
    """(code, message) where two rows carry different methods or
    different inputs, else None. A sweep is one method on one root."""
    seen_method, seen_input = {}, {}
    for row in rows:
        receipt = row.get("receipt_body")
        if receipt is None:
            continue
        seen_method.setdefault(method_identity(receipt), row["value"])
        key = json.dumps(input_identity(receipt), sort_keys=True)
        seen_input.setdefault(key, row["value"])
    if len(seen_method) > 1:
        first, second = list(seen_method.items())[:2]
        return ("mixed-method",
                f"the receipts in this sweep were produced by two executors: "
                f"{first[0]} at {first[1]} and {second[0]} at {second[1]}; a "
                "table is one method, and these rows are not comparable")
    if len(seen_input) > 1:
        first, second = list(seen_input.items())[:2]
        return ("mixed-input",
                f"the receipts in this sweep read two different inputs: "
                f"{first[0]} at {first[1]} and {second[0]} at {second[1]}; a "
                "table is one root, and these rows are not comparable")
    return None


def build_row(value: str, receipt_path: Path, attestation_path: Path,
              exit_code: int, attester: Path, columns,
              data_root: Path | None = None):
    """One row: the attester first, then the receipt's own fields. A
    receipt the attester did not pass is a failed row carrying the
    attester's line and no number."""
    row = {"value": value, "receipt": str(receipt_path), "cells": {},
           "attested": False, "attestation": None, "run_id": None,
           "status": "not-attested", "reason_code": None,
           "receipt_body": None, "executor_exit": exit_code}
    if not receipt_path.is_file():
        row["attestation"] = f"the executor wrote no receipt (exit {exit_code})"
        return row
    passed, line = attest(attester, receipt_path, attestation_path, data_root)
    row["attestation"] = line
    row["attested"] = passed
    if not passed:
        return row
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    row["receipt_body"] = receipt
    row["run_id"] = receipt.get("run_id")
    row["reason_code"] = receipt.get("reason_code")
    row["status"] = "refused" if receipt.get("refused") else "computed"
    row["cells"] = {name: field(receipt, path) for name, path in columns}
    return row


# ---- the table

def show(value) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def show_md(value) -> str:
    if isinstance(value, float):
        return f"{value:+.4f}" if value else "0.0000"
    return show(value)


def headers(columns):
    return list(STATUS_COLUMNS) + [name for name, _ in columns]


def row_cells(row, columns):
    out = {"status": row["status"], "run_id": row["run_id"] or "",
           "reason_code": row["reason_code"] or ""}
    for name, _ in columns:
        out[name] = row["cells"].get(name)
    return out


def write_csv(path: Path, rows, columns) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(headers(columns))
        for row in rows:
            cells = row_cells(row, columns)
            writer.writerow([show(cells[name]) for name in headers(columns)])


def write_markdown(path: Path, rows, columns, head: dict) -> None:
    names = headers(columns)
    lines = [f"# {head['computation']}: {head['parameter']} swept over "
             f"{len(rows)} values", ""]
    lines += [head["provenance"], "",
              "| " + " | ".join(names) + " |",
              "| " + " | ".join("---" for _ in names) + " |"]
    for row in rows:
        cells = row_cells(row, columns)
        lines.append("| " + " | ".join(show_md(cells[name]) for name in names) + " |")
    lines += ["", head["reading"], ""]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_manifest(path: Path, rows, columns, head: dict) -> None:
    doc = dict(head)
    doc["columns"] = [{"name": name, "receipt_field": field_path}
                      for name, field_path in columns]
    doc["rows"] = [{
        "value": row["value"],
        "status": row["status"],
        "run_id": row["run_id"],
        "reason_code": row["reason_code"],
        "receipt": row["receipt"],
        "attested": row["attested"],
        "attestation": row["attestation"],
        "cells": row["cells"],
    } for row in rows]
    path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")


# ---- the sweep

def sweep(args) -> int:
    spec = CATALOG[args.computation]
    paths = bundle_paths(args.computation)
    declared = declared_parameters(paths["concept"])

    if args.aggregate:
        return refuse(
            "aggregate-across-rows",
            f"this sweep will not emit an aggregate across its rows, and "
            f"what was asked for is one: {args.aggregate}. Each row is a "
            f"receipt the attester passed, and an aggregate over the "
            f"rows is a number no concept owns: "
            f"knowledge/{BUNDLE}/{spec['concept']} owns the rates and the "
            f"verdict of one stated window, and nothing in the bundle owns a "
            f"rate across windows or a headline mass rate for an ice sheet, "
            f"which {spec['skill']} forbids in its Must NOT list for the same "
            f"reason. Computing one here would be a number of this "
            f"capability's own, which is domain expansion under ADR D of the "
            f"marketplace decisions and waits on the ablation. Quote one row "
            f"instead: its receipt carries the rates, their intervals, the "
            f"epochs used, the bar and the verdict, and its run id is in the "
            f"manifest. The verdict belongs to the window that produced it.")
    if args.parameter not in declared:
        return refuse(
            "parameter-not-declared",
            f"{args.parameter} is not a parameter "
            f"knowledge/{BUNDLE}/{spec['concept']} declares; it declares "
            f"{', '.join(declared)}. Sweeping execution plumbing (a seed, an "
            "output path) or an invented knob produces a table of runs no "
            "concept licenses.")
    fixed = {}
    for item in args.fixed:
        if "=" not in item:
            return refuse("parameter-not-stated",
                          f"--fixed takes NAME=VALUE, or NAME={UNBOUND} for a "
                          f"parameter left unbound; got {item}")
        name, bound = item.split("=", 1)
        if name not in declared:
            return refuse("parameter-not-declared",
                          f"{name} is not a parameter "
                          f"knowledge/{BUNDLE}/{spec['concept']} declares; it "
                          f"declares {', '.join(declared)}")
        if name == args.parameter:
            return refuse("parameter-not-stated",
                          f"{name} is the swept parameter and cannot also be "
                          "fixed")
        fixed[name] = bound
    unstated = [name for name in declared
                if name != args.parameter and name not in fixed]
    if unstated:
        return refuse(
            "parameter-not-stated",
            f"every declared parameter is stated on every run: "
            f"{', '.join(unstated)} is neither swept nor fixed. State it with "
            f"--fixed {unstated[0]}=VALUE, or --fixed {unstated[0]}={UNBOUND} "
            "to leave it unbound on every run, so the table says what it was.")

    if args.values:
        values = [v for v in (item.strip() for item in args.values.split(",")) if v]
    else:
        length, step = (int(part) for part in args.windows.split(":"))
        values = windows(args.span, length, step)
    if not values:
        return refuse("parameter-not-stated",
                      "the sweep has no values; state them with --values or "
                      "--windows LENGTH:STEP with --span FIRST:LAST")

    out_dir = Path(args.out_dir).expanduser().resolve()
    receipts_dir = out_dir / "receipts"
    receipts_dir.mkdir(parents=True, exist_ok=True)
    data_root = Path(args.data_root) if args.input == "data-root" else None

    rows = []
    for index, value in enumerate(values):
        stem = f"{index:03d}-{re.sub(r'[^A-Za-z0-9._-]', '_', value)}"
        receipt = receipts_dir / f"{stem}.json"
        attestation = receipts_dir / f"{stem}-attestation.json"
        run = run_executor(paths["executor"], args.parameter, value, fixed,
                           args, receipt)
        if run.returncode not in (0, 3):
            print((run.stderr or run.stdout or "").strip())
            return refuse("executor-failed",
                          f"the executor exited {run.returncode} at "
                          f"{args.parameter} {value}; that is neither a result "
                          "nor a refusal, so the sweep stops rather than "
                          "tabling a run it cannot read")
        rows.append(build_row(value, receipt, attestation, run.returncode,
                              paths["attester"], spec["columns"], data_root))

    mixed = one_method(rows)
    if mixed:
        return refuse(*mixed)

    attested = [row for row in rows if row["attested"]]
    body = attested[0]["receipt_body"] if attested else {}
    head = {
        "sweep": "one declared parameter swept; every cell is a field of a "
                 "receipt this sweep attested, and no aggregate across rows "
                 "is computed here",
        "generated_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "computation": args.computation,
        "concept": f"knowledge/{BUNDLE}/{spec['concept']}",
        "executor": f"knowledge/{BUNDLE}/{spec['executor']}",
        "attester": f"knowledge/{BUNDLE}/{spec['attester']}",
        "wrapping_skill": spec["skill"],
        "parameter": args.parameter,
        "values": values,
        "values_rule": (f"--windows {args.windows} --span {args.span}"
                        if args.windows else "--values, stated one by one"),
        "fixed": fixed,
        "runtime": args.runtime,
        "code_sha256": method_identity(body),
        "input": input_identity(body),
        "refusals_enforced": list(REFUSALS),
        "not_computed": "the rate across the rows, the mean of any column, a "
                        "headline mass rate for the ice sheet, and any rate "
                        "read off the count of closed rows: no concept owns "
                        "them",
        "precision_note": "the rate columns are the receipt's own headline "
                          "fields, which the executor states rounded to four "
                          "decimals, beside interval columns the receipt "
                          "carries at full precision; both are copied as the "
                          "receipt states them and neither is rounded or "
                          "unrounded here",
    }
    head["provenance"] = (
        f"Every cell is a field of a receipt the attester passed. Executor "
        f"{head['executor']} at {head['code_sha256']}; attester "
        f"{head['attester']}; concept {head['concept']}; input "
        f"{json.dumps(head['input'], sort_keys=True)}; runtime "
        f"{args.runtime}. Floats are shown to four decimals; the CSV and the "
        f"receipts carry them as the receipt states them.")
    head["reading"] = (
        "A refused row is a measurement: the executor wrote a refusal receipt "
        "with that reason code and no number. Read one row at a time, against "
        f"its own bar, with the caveats {head['concept']} states beside it. "
        "This table licenses no statement about the rows together, and this "
        "sweep refuses to compute one.")

    write_csv(out_dir / "sweep.csv", rows, spec["columns"])
    write_markdown(out_dir / "sweep.md", rows, spec["columns"], head)
    write_manifest(out_dir / "sweep.json", rows, spec["columns"], head)

    computed = sum(1 for row in rows if row["status"] == "computed")
    refused = sum(1 for row in rows if row["status"] == "refused")
    failed = [row for row in rows if not row["attested"]]
    print((out_dir / "sweep.md").read_text(encoding="utf-8"))
    print(f"sweep: {len(rows)} rows over {args.parameter}, {computed} computed, "
          f"{refused} refused by the executor, {len(failed)} not attested; "
          f"{out_dir}/sweep.csv, sweep.md, sweep.json")
    for row in failed:
        print(f"  not attested at {args.parameter} {row['value']}: "
              f"{row['attestation']}")
    return 1 if failed else 0


# ---- selftest

def selftest() -> int:
    """Every refusal, on the executors' synthetic fixtures."""
    paths = bundle_paths("ice-sheet-balance")
    io_paths = bundle_paths("ice-sheet-input-output")
    columns = CATALOG["ice-sheet-balance"]["columns"]
    base = ["--computation", "ice-sheet-balance", "--input", "fixture",
            "--seed", "7", "--runtime", "selftest"]
    closure_fixed = ["--fixed", "ice_sheet=greenland",
                     "--fixed", "altimetry=itslive",
                     "--fixed", "ice_density=917",
                     "--fixed", "bridge=unbound"]

    def run_sweep(extra, work, prefix=None):
        cmd = [sys.executable, str(Path(__file__).resolve()),
               *(prefix if prefix is not None else base),
               "--out-dir", str(work), *extra]
        return subprocess.run(cmd, capture_output=True, text=True)

    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)

        # 1. The sweep itself: three windows of the closure, one of which
        #    the executor refuses for falling outside the terms' overlap.
        #    Every row is attested, the refusal is a row, and every cell
        #    is the receipt's own field.
        values = "2003-01:2009-12,2010-01:2016-12,1980-01:1989-12"
        done = run_sweep(["--parameter", "window", "--values", values,
                          *closure_fixed], work / "table")
        assert done.returncode == 0, done.stdout + done.stderr
        doc = json.loads((work / "table" / "sweep.json").read_text())
        assert [row["value"] for row in doc["rows"]] == values.split(",")
        assert all(row["attested"] for row in doc["rows"]), doc["rows"]
        assert [row["status"] for row in doc["rows"]] == ["computed", "computed", "refused"]
        assert doc["rows"][2]["reason_code"] == "window-outside-overlap", doc["rows"][2]
        assert doc["rows"][2]["cells"]["residual_gt_per_yr"] is None
        assert "PASS refusal" in doc["rows"][2]["attestation"]
        for row in doc["rows"]:
            receipt = json.loads(Path(row["receipt"]).read_text())
            for name, path in columns:
                assert row["cells"][name] == field(receipt, path), (name, row["value"])
            assert row["run_id"] == receipt["run_id"]
        assert (work / "table" / "sweep.csv").is_file()
        assert "| status |" in (work / "table" / "sweep.md").read_text()
        assert doc["fixed"] == {"ice_sheet": "greenland", "altimetry": "itslive",
                                "ice_density": "917", "bridge": "unbound"}
        # the two precisions the receipt states, copied and not reconciled
        first = json.loads(Path(doc["rows"][0]["receipt"]).read_text())
        assert doc["rows"][0]["cells"]["gravimetry_gt_per_yr"] == \
            first["terms"]["gravimetry"]["rate_gt_per_yr"]
        assert doc["rows"][0]["cells"]["gravimetry_ci_low"] == \
            first["rates"]["gravimetry"]["ci_low"]

        # 2. The aggregate a reader asks for first is refused, and the
        #    refusal says what to quote instead.
        out = run_sweep(["--parameter", "window", "--values", values,
                         *closure_fixed,
                         "--aggregate", "the Greenland mass rate across the windows"],
                        work / "agg")
        assert out.returncode == 4 and "aggregate-across-rows" in out.stdout, out.stdout
        assert "ADR D" in out.stdout and "Quote one row instead" in out.stdout
        assert "land-ice/ice-mass-change" in out.stdout, out.stdout
        assert not (work / "agg" / "sweep.csv").is_file(), \
            "a refusal leaves no partial table"

        # 3. A parameter the concept does not declare, swept or fixed.
        out = run_sweep(["--parameter", "seed", "--values", "7,8",
                         *closure_fixed], work / "undeclared")
        assert out.returncode == 4 and "parameter-not-declared" in out.stdout, out.stdout
        out = run_sweep(["--parameter", "window", "--values", values,
                         *closure_fixed, "--fixed", "seed=7"],
                        work / "undeclared2")
        assert out.returncode == 4 and "parameter-not-declared" in out.stdout, out.stdout

        # 4. A declared parameter the command line leaves unstated.
        out = run_sweep(["--parameter", "window", "--values", values,
                         "--fixed", "ice_sheet=greenland"], work / "unstated")
        assert out.returncode == 4 and "parameter-not-stated" in out.stdout, out.stdout
        assert "altimetry" in out.stdout and "bridge" in out.stdout, out.stdout

        # 5. Two methods or two inputs in one table, on real receipts:
        #    the same window at two fixture seeds gives two inputs, and a
        #    receipt whose executor digest differs gives two methods.
        seven = run_sweep(["--parameter", "window", "--values", "2003-01:2009-12",
                           *closure_fixed], work / "seed7")
        assert seven.returncode == 0, seven.stdout + seven.stderr
        eight = run_sweep(["--parameter", "window", "--values", "2003-01:2009-12",
                           *closure_fixed], work / "seed8",
                          prefix=["--computation", "ice-sheet-balance",
                                  "--input", "fixture", "--seed", "8",
                                  "--runtime", "selftest"])
        assert eight.returncode == 0, eight.stdout + eight.stderr

        def only_receipt(out_dir: Path):
            # by the manifest, never by a glob: the receipts directory
            # holds each attestation beside its receipt, and the order a
            # glob returns them in is the filesystem's business
            manifest = json.loads((out_dir / "sweep.json").read_text())
            return json.loads(Path(manifest["rows"][0]["receipt"]).read_text())

        a = only_receipt(work / "seed7")
        b = only_receipt(work / "seed8")
        assert a["data"]["seed"] == 7 and b["data"]["seed"] == 8
        mixed = one_method([{"value": "seed 7", "receipt_body": a},
                            {"value": "seed 8", "receipt_body": b}])
        assert mixed and mixed[0] == "mixed-input", mixed
        other = json.loads(json.dumps(a))
        other["code_sha256"] = "sha256:" + "0" * 64
        mixed = one_method([{"value": "a", "receipt_body": a},
                            {"value": "b", "receipt_body": other}])
        assert mixed and mixed[0] == "mixed-method", mixed
        assert one_method([{"value": "a", "receipt_body": a}]) is None

        # 6. A receipt the attester does not pass is a failed row with
        #    the attester's own line and no number in it.
        tampered = work / "tampered.json"
        doctored = json.loads(json.dumps(a))
        doctored["residual"]["rate_gt_per_yr"] = \
            doctored["residual"]["rate_gt_per_yr"] + 0.5
        tampered.write_text(json.dumps(doctored, indent=2) + "\n")
        row = build_row("2003-01:2009-12", tampered, work / "tampered-att.json",
                        0, paths["attester"], columns)
        assert row["attested"] is False and row["status"] == "not-attested", row
        assert row["cells"] == {} and row["run_id"] is None
        assert row["attestation"].startswith("FAIL"), row["attestation"]

        # 7. The window rule expands to explicit values, and the values
        #    are what the rows carry.
        assert windows("2005-01:2010-12", 24, 12) == [
            "2005-01:2006-12", "2006-01:2007-12", "2007-01:2008-12",
            "2008-01:2009-12", "2009-01:2010-12"]
        out = run_sweep(["--parameter", "window", "--windows", "84:84",
                         "--span", "2003-01:2016-12", *closure_fixed],
                        work / "windows")
        assert out.returncode == 0, out.stdout + out.stderr
        doc = json.loads((work / "windows" / "sweep.json").read_text())
        assert [row["value"] for row in doc["rows"]] == ["2003-01:2009-12",
                                                          "2010-01:2016-12"]
        assert doc["values_rule"] == "--windows 84:84 --span 2003-01:2016-12"

        # 8. The declared set comes from each concept, not from here.
        assert declared_parameters(paths["concept"]) == [
            "ice_sheet", "window", "altimetry", "ice_density", "bridge"]
        assert declared_parameters(io_paths["concept"]) == [
            "ice_sheet", "window", "gates", "velocity_epoch", "ice_density"]

        # 9. The second computation sweeps by the same command line, and
        #    its declared parameters are its own.
        out = run_sweep(["--parameter", "window",
                         "--values", "2005-01:2014-12,2021-01:2023-12",
                         "--fixed", "ice_sheet=greenland",
                         "--fixed", "gates=synthetic-outlets",
                         "--fixed", "velocity_epoch=annual",
                         "--fixed", "ice_density=917"],
                        work / "io",
                        prefix=["--computation", "ice-sheet-input-output",
                                "--input", "fixture", "--seed", "7",
                                "--runtime", "selftest"])
        assert out.returncode == 0, out.stdout + out.stderr
        doc = json.loads((work / "io" / "sweep.json").read_text())
        assert [row["status"] for row in doc["rows"]] == ["computed", "refused"]
        assert doc["rows"][1]["reason_code"] == "window-outside-epochs", doc["rows"][1]
        assert doc["rows"][1]["cells"]["mass_rate_gt_per_yr"] is None
        assert doc["rows"][0]["cells"]["sign"] == "loss"

    print("sweep selftest: ok "
          f"({len(REFUSALS)} refusals exercised: {', '.join(REFUSALS)}; "
          "a tampered receipt is a failed row, not a number; both nsidc "
          "computations sweep by the same command line)")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--computation", choices=sorted(CATALOG),
                    help="the attested computation to sweep")
    ap.add_argument("--parameter", help="the declared parameter swept")
    ap.add_argument("--values", help="the values, comma separated, stated explicitly")
    ap.add_argument("--windows", help="LENGTH:STEP in months, expanded over --span "
                                      "into explicit values")
    ap.add_argument("--span", help="FIRST:LAST as YYYY-MM:YYYY-MM, with --windows")
    ap.add_argument("--fixed", action="append", default=[],
                    help=f"NAME=VALUE for another declared parameter, or "
                         f"NAME={UNBOUND} to leave it unbound; every declared "
                         "parameter is stated on every run")
    ap.add_argument("--input", choices=("fixture", "data-root"),
                    help="the executor's input, one for the whole sweep")
    ap.add_argument("--data-root", type=Path, help="the stamped tree, with --input data-root")
    ap.add_argument("--seed", type=int, default=7, help="fixture seed (default 7)")
    ap.add_argument("--runtime", help="the runtime that ran this, passed to every run")
    ap.add_argument("--runtime-version", default=None)
    ap.add_argument("--capability-root", type=Path, default=None,
                    help="the package tree these runs are evidence for")
    ap.add_argument("--out-dir", help="where sweep.csv, sweep.md, sweep.json and "
                                      "the receipts go")
    ap.add_argument("--aggregate", default=None,
                    help="an aggregate across the rows; always refused, and the "
                         "refusal says which receipt to quote instead")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args(argv)

    if args.selftest:
        return selftest()
    missing = [name for name in ("computation", "parameter", "input", "runtime",
                                 "out_dir") if getattr(args, name) is None]
    if missing:
        ap.error("these are required for a sweep: "
                 + ", ".join("--" + name.replace("_", "-") for name in missing))
    if bool(args.values) == bool(args.windows):
        ap.error("state the values with --values, or a window rule with "
                 "--windows LENGTH:STEP and --span FIRST:LAST, not both")
    if args.windows and not args.span:
        ap.error("--windows needs --span FIRST:LAST")
    if (args.input == "data-root") != bool(args.data_root):
        ap.error("--input data-root needs --data-root DIR, and --data-root is "
                 "not read with --input fixture")
    return sweep(args)


if __name__ == "__main__":
    sys.exit(main())
