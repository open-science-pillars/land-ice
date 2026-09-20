#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["matplotlib"]
# ///
"""Draw a figure from an attested ice sheet balance receipt, and from
nothing else.

This is the ocean-science receipt-figures renderer with its discipline
intact, over this package's closure receipts: the attester runs first and
the renderer stops on anything but PASS, every array drawn is verified
against what the receipt records before a line is plotted, and the
caption carries the run identifier, the code digest and the verdict so
a reader can trace the picture to the receipt and the receipt to the
sanctioned code and the stamped tree.

Two modes, both of which draw only series the closure receipt itself
carries:

  terms         the four term series the receipt records: the
                gravimetric mass anomaly, the altimetric mass anomaly,
                and, on their own axis, the volume anomaly and the firn
                air volume anomaly that the density turns into the
                second of them. Nothing is fitted; the rates and their
                intervals are quoted in the legend from the receipt's
                own rate blocks.

  differences   the annual-lag differences the rate method is the mean
                of: the altimetry differences, the gravimetry
                differences and the residual between them on the epochs
                both terms carry. This is the figure the concept's
                prose narrates when it reads the 2010 and the 2013
                spikes and says which term carries each; the picture
                shows the two spikes and lets a reader see which curve
                moves.

  map           always refused. These receipts carry no per-cell
                fields: the closure sums to a scalar per epoch and the
                executor writes no fields file, so there is no array a
                map could draw and no hash a map could be checked
                against. The refusal names the reason rather than
                drawing a map from something else.

What it refuses, each with exit 4 and a reason code:

  attester-did-not-pass  this package's attester did not PASS this
                         exact receipt. A figure exists only for a
                         receipt that attests; a FAIL is reported, never
                         drawn around.
  array-hash-mismatch    an array the figure would draw does not match
                         what the receipt records. See the note below
                         for what "the hashes the receipt records" is
                         for these receipts.
  map-mode-unavailable   a map was asked for, and these receipts carry
                         no per-cell fields.

**What verifying an array against the receipt means here.** The PO.DAAC
fields receipts the ocean-science renderer draws carry a `fields` block
with a sha256 per array and an .npz beside the receipt, and the
renderer hashes each array against it. An ice sheet balance receipt
carries no such block, because it carries its series inline at full
precision instead; the hashes it records are `code_sha256`, the input
digests (`data.digest` for a fixture, `data.record.manifest_sha256` and
the per-term-file digests under `data.files` for a stamped tree) and
nothing per array. The renderer therefore binds every array it draws to
the receipt three ways, and refuses on any of them:

  1. the receipt's own bytes are hashed before the attester runs and
     again after, and must be identical, so the arrays drawn come from
     the exact receipt the attester passed and not from a file that
     changed underneath it;
  2. the receipt records the input digests its series were built from,
     and a receipt missing them is refused rather than drawn;
  3. every array drawn is one of the named series the receipt carries,
     checked against the length the receipt states for it and against
     the derivation rule the receipt states for it (the altimetric mass
     is the density times the volume less the firn air at every epoch;
     the residual is the altimetry differences less the gravimetry
     differences at every common epoch; an annual-lag difference is the
     term series at an epoch less its value twelve months earlier). An
     array that fails any of these is refused, never drawn and never
     redrawn from somewhere else.

The renderer also prints and captions a sha256 of each array as it drew
it, so a reader can recompute the same digest from the receipt.

The attester is named by --attester: a path, or a bare name resolved
in the scripts of the skill that runs the computation, under this
package's root (`CLAUDE_PLUGIN_ROOT` where the runtime sets it for the
installed plugin, else the package tree this script sits in).

Usage:
  uv run skills/receipt-figures/scripts/receipt_figure.py terms RECEIPT.json \
      --attester ice_sheet_balance_check --out terms.png
  uv run skills/receipt-figures/scripts/receipt_figure.py differences RECEIPT.json \
      --attester ice_sheet_balance_check --out differences.png
  uv run skills/receipt-figures/scripts/receipt_figure.py --selftest
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path

CONCEPT = "knowledge/computations/ice-sheet-balance.md"
SCRIPTS = "skills/ice-mass-change/scripts"
DEFAULT_ATTESTER = "ice_sheet_balance_check"
REFUSALS = ("attester-did-not-pass", "array-hash-mismatch",
            "map-mode-unavailable")
TOLERANCE = 1e-6


class Refusal(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def refuse(code: str, message: str):
    raise Refusal(code, message)


# ---- this package

def package_root() -> Path:
    """This package's root: `CLAUDE_PLUGIN_ROOT` where the runtime sets it
    for the installed plugin, else the package tree this script sits in.
    The computation's scripts are beside this one now, so nothing is
    resolved through another repository."""
    override = os.environ.get("CLAUDE_PLUGIN_ROOT")
    start = Path(override).expanduser().resolve() if override \
        else Path(__file__).resolve()
    for p in (start, *start.parents):
        if (p / ".osp" / "package.yaml").is_file():
            return p
    sys.exit(f"no package root above {start} (no .osp/package.yaml); set "
             "CLAUDE_PLUGIN_ROOT to this plugin's installed root")


def resolve_attester(name: str) -> Path:
    p = Path(name).expanduser()
    if p.is_file():
        return p.resolve()
    candidate = (package_root() / SCRIPTS
                 / (name if name.endswith(".py") else name + ".py"))
    if not candidate.is_file():
        sys.exit(f"attester {name} not found at {candidate}")
    return candidate


# ---- the attester, and the receipt bytes it passed

def attest(receipt_path: Path, attester: Path, data_root: Path | None):
    """Run the deterministic attester on this exact file and return its
    PASS line with the digest of the bytes it read. The receipt is
    hashed before and after, so a file that changed under the attester
    is a refusal and not a figure."""
    before = hashlib.sha256(receipt_path.read_bytes()).hexdigest()
    cmd = ["uv", "run", str(attester), str(receipt_path)]
    if data_root is not None:
        cmd += ["--data-root", str(data_root)]
    run = subprocess.run(cmd, capture_output=True, text=True)
    verdict = ((run.stdout or "").strip() or (run.stderr or "").strip()).splitlines()
    line = verdict[-1] if verdict else "the attester printed nothing"
    if run.returncode != 0 or not line.startswith("PASS"):
        refuse("attester-did-not-pass",
               f"{attester.name} did not PASS {receipt_path}; a figure exists "
               f"only for a receipt that attests, so nothing is drawn. Report "
               f"the attester's own lines:\n" + "\n".join(verdict))
    after = hashlib.sha256(receipt_path.read_bytes()).hexdigest()
    if before != after:
        refuse("array-hash-mismatch",
               f"{receipt_path} changed while the attester read it "
               f"(sha256 {before[:12]} then {after[:12]}); the arrays a figure "
               "would draw are not the arrays that attested")
    return line, before


# ---- verifying the arrays against what the receipt records

def digest(values) -> str:
    """A canonical sha256 of one array as it is drawn: the repr of each
    float at full precision, joined, so a reader can recompute it from
    the receipt with no library."""
    payload = "\n".join(repr(float(v)) for v in values).encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def close_enough(a, b) -> bool:
    return abs(a - b) <= TOLERANCE * max(1.0, abs(b))


def require_input_digests(receipt: dict) -> dict:
    """The hashes the receipt records for the input its series were
    built from. A receipt without them is refused."""
    data = receipt.get("data") or {}
    if data.get("mode") == "data-root":
        record = data.get("record") or {}
        got = {"mode": "data-root", "record": record.get("record"),
               "manifest_sha256": record.get("manifest_sha256"),
               "files": data.get("files")}
        if not got["manifest_sha256"] or not got["files"]:
            refuse("array-hash-mismatch",
                   "this data-root receipt records no manifest digest or no "
                   "per-term-file digests, so the series it carries are bound "
                   "to no input this renderer can name; nothing is drawn")
        return got
    got = {"mode": data.get("mode"), "seed": data.get("seed"),
           "digest": data.get("digest"),
           "generator_sha256": data.get("generator_sha256")}
    if not got["digest"]:
        refuse("array-hash-mismatch",
               "this fixture receipt records no input digest, so the series "
               "it carries are bound to no input this renderer can name; "
               "nothing is drawn")
    return got


def series_of(receipt: dict, name: str):
    """One named series the receipt carries, checked against the length
    the receipt states for it elsewhere."""
    block = ((receipt.get("series") or {}).get(name)) or {}
    epochs, values = block.get("epochs"), block.get("values")
    if not isinstance(epochs, list) or not isinstance(values, list):
        refuse("array-hash-mismatch",
               f"the receipt carries no series named {name!r}; this renderer "
               "draws the receipt's own series and never an array assembled "
               "from anywhere else")
    if len(epochs) != len(values):
        refuse("array-hash-mismatch",
               f"series {name}: {len(epochs)} epochs against {len(values)} "
               "values in the receipt")
    stated = None
    if name in ("gravimetry", "altimetry", "volume", "firn"):
        stated = ((receipt.get("terms") or {}).get(name) or {}).get("n_epochs")
    elif name == "residual":
        stated = (receipt.get("residual") or {}).get("n_common_differences")
    if stated is not None and stated != len(values):
        refuse("array-hash-mismatch",
               f"series {name} carries {len(values)} values and the receipt "
               f"states {stated}; the array is not the one the receipt "
               "describes")
    return epochs, [float(v) for v in values]


def verify_altimetric_mass(receipt: dict) -> None:
    """The receipt's stated rule for the altimetric mass series: the ice
    density times the volume anomaly less the firn air volume anomaly at
    every epoch, one cubic kilometre being density over a thousand
    gigatonnes."""
    a_epochs, a = series_of(receipt, "altimetry")
    v_epochs, v = series_of(receipt, "volume")
    f_epochs, f = series_of(receipt, "firn")
    if not (a_epochs == v_epochs == f_epochs):
        refuse("array-hash-mismatch",
               "the altimetry, volume and firn series in this receipt do not "
               "stand on the same epochs, so the rule the receipt states for "
               "the altimetric mass cannot be checked")
    rho = (receipt.get("bound_parameters") or {}).get("ice_density")
    if rho is None:
        refuse("array-hash-mismatch",
               "the receipt binds no ice_density, so the altimetric mass "
               "series cannot be checked against the rule it states")
    for i, (mass, vol, firn) in enumerate(zip(a, v, f)):
        want = float(rho) * (vol - firn) / 1000.0
        if not close_enough(mass, want):
            refuse("array-hash-mismatch",
                   f"the altimetry series at {a_epochs[i]} is {mass!r} and the "
                   f"receipt's own rule (density {rho} times volume less firn "
                   f"air) gives {want!r}; the array does not match the receipt")


def verify_differences(receipt: dict):
    """The annual-lag differences the rate method is the mean of, checked
    against the term series they are differences of, and the residual
    checked against the two."""
    block = (receipt.get("series") or {}).get("residual") or {}
    epochs = block.get("epochs")
    residual = block.get("values")
    alt_d = block.get("altimetry_differences")
    grav_d = block.get("gravimetry_differences")
    for name, arr in (("epochs", epochs), ("values", residual),
                      ("altimetry_differences", alt_d),
                      ("gravimetry_differences", grav_d)):
        if not isinstance(arr, list):
            refuse("array-hash-mismatch",
                   f"the receipt's residual series carries no {name}; the "
                   "annual-lag differences are not in this receipt to draw")
    if not (len(epochs) == len(residual) == len(alt_d) == len(grav_d)):
        refuse("array-hash-mismatch",
               "the residual series' four arrays are of different lengths in "
               "this receipt")
    alt_d = [float(x) for x in alt_d]
    grav_d = [float(x) for x in grav_d]
    residual = [float(x) for x in residual]
    for i, epoch in enumerate(epochs):
        if not close_enough(residual[i], alt_d[i] - grav_d[i]):
            refuse("array-hash-mismatch",
                   f"the residual at {epoch} is {residual[i]!r} and the "
                   f"receipt's own rule (altimetry difference less gravimetry "
                   f"difference) gives {alt_d[i] - grav_d[i]!r}")
    # each difference against the term series it is a difference of
    for term, diffs in (("altimetry", alt_d), ("gravimetry", grav_d)):
        t_epochs, t_values = series_of(receipt, term)
        by_epoch = dict(zip(t_epochs, t_values))
        for i, epoch in enumerate(epochs):
            year, month = (int(part) for part in epoch.split("-"))
            earlier = f"{year - 1:04d}-{month:02d}"
            if epoch not in by_epoch or earlier not in by_epoch:
                refuse("array-hash-mismatch",
                       f"the {term} annual-lag difference at {epoch} has no "
                       f"pair in the {term} series ({earlier} or {epoch} is "
                       "missing); the difference array is not the one this "
                       "receipt's series produce")
            want = by_epoch[epoch] - by_epoch[earlier]
            if not close_enough(diffs[i], want):
                refuse("array-hash-mismatch",
                       f"the {term} annual-lag difference at {epoch} is "
                       f"{diffs[i]!r} and the receipt's own series give "
                       f"{want!r}; the array does not match the receipt")
    return epochs, alt_d, grav_d, residual


# ---- the caption

def caption(receipt: dict, verdict: str, attester: Path, receipt_sha: str,
            inputs: dict, arrays: dict) -> str:
    bits = [f"receipt run {receipt['run_id']}",
            f"code sha256 {receipt['code_sha256'].split(':')[-1][:12]}",
            f"receipt sha256 {receipt_sha[:12]}"]
    if inputs.get("mode") == "data-root":
        bits.append(f"data {inputs['record']} manifest "
                    f"{inputs['manifest_sha256'].split(':')[-1][:12]}")
    else:
        bits.append(f"fixture seed {inputs['seed']} digest "
                    f"{inputs['digest'].split(':')[-1][:12]}")
    closed = (receipt.get("verdict") or {}).get("closed_within_uncertainty")
    bits.append(f"closed_within_uncertainty {'true' if closed else 'false'}")
    bits.append(f"{attester.name} {verdict.split()[0]}")
    bits.append("arrays " + ", ".join(
        f"{name} {sha.split(':')[-1][:8]}" for name, sha in arrays.items()))
    return " · ".join(bits)


def dates_of(epochs):
    return [dt.date(int(e[:4]), int(e[5:7]), 15) for e in epochs]


def window_title(receipt: dict) -> str:
    bp = receipt.get("bound_parameters") or {}
    mode = (receipt.get("data") or {}).get("mode")
    where = "the stamped data root" if mode == "data-root" else \
        f"the synthetic fixture at seed {(receipt.get('data') or {}).get('seed')}"
    return (f"{bp.get('ice_sheet')} {bp.get('window')}, altimetry "
            f"{bp.get('altimetry')}, ice density {bp.get('ice_density')} "
            f"kg per m3, on {where}")


# ---- the figures

def check_closure_receipt(receipt: dict) -> None:
    if receipt.get("refused"):
        refuse("array-hash-mismatch",
               f"this receipt is a refusal ({receipt.get('reason_code')}) and "
               "carries no series: a refusal is never a number and never a "
               "figure. Report the refusal in the executor's own words.")
    if "ice_sheet_balance" not in (receipt.get("computation") or ""):
        refuse("array-hash-mismatch",
               f"this renderer draws ice sheet balance receipts and this one "
               f"is from {receipt.get('computation')!r}")


def draw_terms(args, receipt, verdict, attester, receipt_sha, inputs) -> int:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.dates as mdates
    import matplotlib.pyplot as plt

    verify_altimetric_mass(receipt)
    g_epochs, g = series_of(receipt, "gravimetry")
    a_epochs, a = series_of(receipt, "altimetry")
    v_epochs, v = series_of(receipt, "volume")
    f_epochs, f = series_of(receipt, "firn")
    arrays = {"gravimetry": digest(g), "altimetry": digest(a),
              "volume": digest(v), "firn": digest(f)}

    rates = receipt["rates"]

    def legend(term, units):
        r = rates[term]
        return (f"{term} {r['rate']:+.3f} [{r['ci_low']:+.3f}, "
                f"{r['ci_high']:+.3f}] {units} ({r['se_basis']} error)")

    fig, (top, bottom) = plt.subplots(2, 1, figsize=(11, 7.4), dpi=args.dpi,
                                      sharex=True,
                                      gridspec_kw={"height_ratios": [3, 2]})
    top.plot(dates_of(g_epochs), g, color="#1f4e79", linewidth=1.1,
             label=legend("gravimetry", "Gt/year"))
    top.plot(dates_of(a_epochs), a, color="#b2411c", linewidth=1.1,
             label=legend("altimetry", "Gt/year"))
    top.axhline(0, color="k", linewidth=0.4)
    top.set_ylabel("mass anomaly, Gt")
    top.grid(True, linewidth=0.3, alpha=0.5)
    top.legend(loc="upper right", fontsize=8, frameon=False)
    top.set_title(args.title or f"ice sheet balance terms: {window_title(receipt)}",
                  fontsize=10)

    bottom.plot(dates_of(v_epochs), v, color="#2f6f4f", linewidth=1.0,
                label=legend("volume", "km3/year"))
    bottom.plot(dates_of(f_epochs), f, color="#c9a227", linewidth=1.0,
                label=legend("firn", "km3 of air/year"))
    bottom.axhline(0, color="k", linewidth=0.4)
    bottom.set_ylabel("volume anomaly, km3")
    bottom.grid(True, linewidth=0.3, alpha=0.5)
    bottom.legend(loc="upper right", fontsize=8, frameon=False)
    bottom.xaxis.set_major_locator(mdates.YearLocator(2))
    bottom.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))

    cap = caption(receipt, verdict, attester, receipt_sha, inputs, arrays)
    fig.text(0.01, 0.01, textwrap.fill(cap, 150), fontsize=6.5,
             family="monospace", alpha=0.85)
    fig.tight_layout(rect=(0, 0.07, 1, 1))
    out = Path(args.out).expanduser()
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out)
    print(f"{out}: the four term series, {len(g)} gravimetry and {len(a)} "
          f"altimetry epochs; the lower panel is the volume anomaly and the "
          f"firn air volume anomaly the density turns into the altimetric mass")
    print(f"  {cap}")
    return 0


def draw_differences(args, receipt, verdict, attester, receipt_sha, inputs) -> int:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.dates as mdates
    import matplotlib.pyplot as plt

    epochs, alt_d, grav_d, residual = verify_differences(receipt)
    arrays = {"altimetry_differences": digest(alt_d),
              "gravimetry_differences": digest(grav_d),
              "residual": digest(residual)}
    rates = receipt["rates"]
    res = rates["residual"]
    bar = receipt["combined_uncertainty"]["bar_gt_per_yr"]
    dates = dates_of(epochs)

    fig, (top, bottom) = plt.subplots(2, 1, figsize=(11, 7.4), dpi=args.dpi,
                                      sharex=True,
                                      gridspec_kw={"height_ratios": [3, 2]})
    top.plot(dates, alt_d, color="#b2411c", linewidth=1.1,
             label=f"altimetry differences, mean "
                   f"{receipt['residual']['altimetry_on_common_epochs_gt_per_yr']:+.3f} Gt/year")
    top.plot(dates, grav_d, color="#1f4e79", linewidth=1.1,
             label=f"gravimetry differences, mean "
                   f"{receipt['residual']['gravimetry_on_common_epochs_gt_per_yr']:+.3f} Gt/year")
    top.axhline(0, color="k", linewidth=0.4)
    top.set_ylabel("annual-lag difference, Gt/year")
    top.grid(True, linewidth=0.3, alpha=0.5)
    top.legend(loc="lower left", fontsize=8, frameon=False)
    top.set_title(args.title or f"annual-lag differences: {window_title(receipt)}",
                  fontsize=10)

    bottom.axhspan(-bar, bar, color="#c9a227", alpha=0.2, linewidth=0,
                   label=f"bar {bar:.3f} Gt/year (half width "
                         f"{receipt['combined_uncertainty']['residual_half_width_gt_per_yr']:.3f} "
                         f"plus selection systematic "
                         f"{receipt['combined_uncertainty']['selection_systematic']['value_gt_per_yr']:.3f})")
    bottom.plot(dates, residual, color="#4a2d6b", linewidth=1.1,
                label="residual, altimetry difference less gravimetry difference")
    bottom.axhline(res["rate"], color="#4a2d6b", linewidth=1.6, linestyle="--",
                   label=f"residual rate {res['rate']:+.3f} [{res['ci_low']:+.3f}, "
                         f"{res['ci_high']:+.3f}] Gt/year")
    bottom.axhline(0, color="k", linewidth=0.4)
    bottom.set_ylabel("residual, Gt/year")
    bottom.grid(True, linewidth=0.3, alpha=0.5)
    bottom.legend(loc="lower left", fontsize=7.5, frameon=False)
    bottom.xaxis.set_major_locator(mdates.YearLocator(2))
    bottom.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))

    cap = caption(receipt, verdict, attester, receipt_sha, inputs, arrays)
    fig.text(0.01, 0.01, textwrap.fill(cap, 150), fontsize=6.5,
             family="monospace", alpha=0.85)
    fig.tight_layout(rect=(0, 0.07, 1, 1))
    out = Path(args.out).expanduser()
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out)
    print(f"{out}: {len(epochs)} annual-lag differences on the epochs both "
          f"terms carry, from {epochs[0]} to {epochs[-1]}")
    print(f"  {cap}")
    return 0


def draw(args) -> int:
    if args.mode == "map":
        refuse("map-mode-unavailable",
               "an ice sheet balance receipt carries no per-cell fields: the "
               "closure sums each term to one value per epoch, the executor "
               "writes no fields file and the receipt records no per-cell "
               "array or its hash, so there is nothing a map could draw that "
               "the receipt licenses. Draw the terms or the annual-lag "
               f"differences instead, and read {CONCEPT} for what the domains "
               "of the two terms are; a map of where the ice sheet is losing "
               "mass is a different computation that this capability does "
               "not carry.")
    receipt_path = Path(args.receipt).expanduser().resolve()
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    attester = resolve_attester(args.attester)
    data_root = Path(args.data_root).expanduser().resolve() if args.data_root else None
    verdict, receipt_sha = attest(receipt_path, attester, data_root)
    check_closure_receipt(receipt)
    inputs = require_input_digests(receipt)
    if args.mode == "terms":
        return draw_terms(args, receipt, verdict, attester, receipt_sha, inputs)
    return draw_differences(args, receipt, verdict, attester, receipt_sha, inputs)


# ---- selftest

def selftest() -> int:
    """Every refusal, on the executor's synthetic fixture."""
    scripts = package_root() / SCRIPTS
    executor = scripts / "ice_sheet_balance.py"
    attester = scripts / "ice_sheet_balance_check.py"
    for p in (executor, attester):
        if not p.is_file():
            sys.exit(f"this package carries no {p.name} at {p.parent}")

    def render(argv):
        return subprocess.run(
            [sys.executable, str(Path(__file__).resolve()), *argv],
            capture_output=True, text=True)

    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        receipt = work / "receipt.json"
        run = subprocess.run(
            ["uv", "run", str(executor), "--ice-sheet", "greenland",
             "--window", "2003-01:2016-12", "--altimetry", "itslive",
             "--ice-density", "917", "--fixture", "--seed", "7",
             "--runtime", "selftest", "--receipt", str(receipt)],
            capture_output=True, text=True)
        assert run.returncode == 0, run.stdout + run.stderr

        # 1. Both figures draw from a receipt the attester passed, and
        #    each caption carries the run id, the code digest and the
        #    verdict.
        for mode, out in (("terms", "terms.png"), ("differences", "diff.png")):
            done = render([mode, str(receipt), "--attester", str(attester),
                           "--out", str(work / out)])
            assert done.returncode == 0, done.stdout + done.stderr
            assert (work / out).is_file() and (work / out).stat().st_size > 0
            body = json.loads(receipt.read_text())
            assert body["run_id"] in done.stdout, done.stdout
            assert body["code_sha256"].split(":")[-1][:12] in done.stdout
            assert "closed_within_uncertainty" in done.stdout
            assert "arrays " in done.stdout

        # 2. A map is refused, because these receipts carry no per-cell
        #    fields.
        out = render(["map", str(receipt), "--attester", str(attester),
                      "--out", str(work / "map.png")])
        assert out.returncode == 4 and "map-mode-unavailable" in out.stdout, out.stdout
        assert not (work / "map.png").exists()

        # 3. A receipt the attester does not pass is never drawn.
        tampered = work / "tampered.json"
        body = json.loads(receipt.read_text())
        body["residual"]["rate_gt_per_yr"] = body["residual"]["rate_gt_per_yr"] + 0.5
        tampered.write_text(json.dumps(body, indent=2) + "\n")
        out = render(["terms", str(tampered), "--attester", str(attester),
                      "--out", str(work / "no.png")])
        assert out.returncode == 4 and "attester-did-not-pass" in out.stdout, out.stdout
        assert not (work / "no.png").exists()

        # 4. An array that does not match what the receipt records is
        #    refused rather than drawn. The attester runs on the file and
        #    the renderer checks the arrays, so the case is exercised on
        #    the verifier directly with the receipt's own body.
        good = json.loads(receipt.read_text())
        for mutate, what in (
            (lambda d: d["series"]["altimetry"]["values"].__setitem__(
                3, d["series"]["altimetry"]["values"][3] + 1.0),
             "the altimetric mass against the density rule"),
            (lambda d: d["series"]["volume"]["values"].__setitem__(
                5, d["series"]["volume"]["values"][5] + 1.0),
             "the volume the altimetric mass rests on"),
        ):
            doctored = json.loads(json.dumps(good))
            mutate(doctored)
            try:
                verify_altimetric_mass(doctored)
            except Refusal as bad:
                assert bad.code == "array-hash-mismatch", (what, bad.code)
            else:
                raise AssertionError(f"{what} was not refused")
        for mutate, what in (
            (lambda d: d["series"]["residual"]["values"].__setitem__(
                2, d["series"]["residual"]["values"][2] + 1.0),
             "the residual against its two differences"),
            (lambda d: d["series"]["residual"]["altimetry_differences"].__setitem__(
                4, d["series"]["residual"]["altimetry_differences"][4] + 1.0),
             "an annual-lag difference against the term series"),
            (lambda d: d["series"]["residual"].pop("gravimetry_differences"),
             "a difference array the receipt does not carry"),
        ):
            doctored = json.loads(json.dumps(good))
            mutate(doctored)
            try:
                verify_differences(doctored)
            except Refusal as bad:
                assert bad.code == "array-hash-mismatch", (what, bad.code)
            else:
                raise AssertionError(f"{what} was not refused")
        # a series whose length disagrees with the count the receipt states
        doctored = json.loads(json.dumps(good))
        doctored["terms"]["gravimetry"]["n_epochs"] += 1
        try:
            series_of(doctored, "gravimetry")
        except Refusal as bad:
            assert bad.code == "array-hash-mismatch"
        else:
            raise AssertionError("a series against a stated count was not refused")
        # a receipt that records no input digest
        doctored = json.loads(json.dumps(good))
        doctored["data"].pop("digest")
        try:
            require_input_digests(doctored)
        except Refusal as bad:
            assert bad.code == "array-hash-mismatch"
        else:
            raise AssertionError("a receipt with no input digest was not refused")
        # the good receipt passes every check
        verify_altimetric_mass(good)
        verify_differences(good)
        require_input_digests(good)

        # 5. A refusal receipt is never a figure.
        refusal = work / "refusal.json"
        run = subprocess.run(
            ["uv", "run", str(executor), "--ice-sheet", "greenland",
             "--window", "2019-01:2025-12", "--altimetry", "atl15",
             "--ice-density", "917", "--fixture", "--seed", "7",
             "--runtime", "selftest", "--receipt", str(refusal)],
            capture_output=True, text=True)
        assert run.returncode == 3, run.stdout + run.stderr
        out = render(["terms", str(refusal), "--attester", str(attester),
                      "--out", str(work / "refusal.png")])
        assert out.returncode == 4 and "array-hash-mismatch" in out.stdout, out.stdout
        assert "refusal" in out.stdout and not (work / "refusal.png").exists()

        # 6. The array digest is reproducible from the receipt.
        assert digest([1.0, 2.0]) == digest([1, 2])
        assert digest([1.0, 2.0]) != digest([1.0, 2.5])

    print("receipt-figures selftest: ok "
          f"({len(REFUSALS)} refusals exercised: {', '.join(REFUSALS)}; "
          "the terms and the annual-lag differences draw from an attested "
          "fixture receipt, a refusal receipt is never a figure)")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("mode", nargs="?", choices=("terms", "differences", "map"),
                    help="terms: the four term series; differences: the "
                         "annual-lag differences and the residual; map: always "
                         "refused, these receipts carry no per-cell fields")
    ap.add_argument("receipt", nargs="?", help="the receipt to draw from")
    ap.add_argument("--attester", default=DEFAULT_ATTESTER,
                    help=f"attester path, or a bare name under this package's "
                         f"{SCRIPTS} (default {DEFAULT_ATTESTER})")
    ap.add_argument("--data-root", default=None,
                    help="the stamped tree, so a data-root receipt is attested "
                         "against it rather than on the executor's word")
    ap.add_argument("--dpi", type=int, default=150, help="output resolution")
    ap.add_argument("--title")
    ap.add_argument("--out", help="where the figure is written")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()

    if args.selftest:
        return selftest()
    if not args.mode:
        ap.error("a mode is required: terms, differences or map")
    if args.mode != "map" and not args.receipt:
        ap.error("a receipt is required")
    if not args.out:
        ap.error("--out is required")
    try:
        return draw(args)
    except Refusal as bad:
        print(f"FIGURE REFUSED ({bad.code}): {bad}")
        return 4


if __name__ == "__main__":
    sys.exit(main())
