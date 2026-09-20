#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Deterministic attester for the attested ice sheet mass balance by
the input-output method (ice_sheet_input_output.py). Stdlib only,
consumer side, no language model.

A receipt from any runtime attests PASS (exit 0) only when ALL hold,
else FAIL (exit 1) naming the check; one line per check, PASS name or
FAIL name: reason:

  fields       every declared receipt field is present;
  code         the receipt's code_sha256 is the sanctioned executor
               beside this file (or the one --computation names), so
               an edited computation invalidates every earlier receipt;
  release      the receipt's bundle block names this bundle's package
               name, version and release lock digest, and its
               capability block is well formed;
  runtime      the receipt names the runtime that produced it;
  data         a fixture regenerated here at the receipt's seed hashes
               to the receipt's digest and the generator to the
               sanctioned executor; for a data root, the RECORD stamp,
               its digest and the term file digests are present, and
               with --data-root DIR each digest matches the tree and
               the tree's own RECORD.json manifest, and the recorded
               root is that tree, package-relative;
  gates        the gate block agrees with the bound gate set, the gate
               set spans the ice sheet's grounded margin, every node's
               thickness was made by mass conservation and lies on
               grounded ice, and the node and gate counts agree with
               the term files;
  series       the three series are well formed on the window and on
               the same epochs; the discharge at every epoch is the
               node sum of the ice density times the normal velocity
               times the node width over the areal scale times the
               thickness, recomputed here from the term rows by a
               second implementation; the per gate sums add to it; the
               surface mass balance at every epoch is the period
               weighted mean of the product's steps in that year,
               recomputed the same way; and the mass rate series is
               their difference;
  recompute    every rate block (the mean, its effective sample size,
               interval and formal error), the gate systematic, the
               bar and the verdict recomputed here from the series
               match the receipt (1e-9 relative), by a second
               implementation of the method statement;
  bookkeeping  every required statement is present (the velocity
               term's product, grid, mask, aggregation, sampling,
               uncertainty basis and map units; the thickness term's
               product, grid, nominal year, mask, source variable,
               uncertainty basis and provenance rule; the surface mass
               balance term's product, grid, mask, aggregation,
               sampling, uncertainty basis and sign convention; the
               gate and closure tables), and the density, discharge,
               annualisation and epoch handling blocks agree with the
               bound parameters and the series;
  plausible    on the fixture, the known truth: each rate is within a
               stated band of the planted one and the verdict
               recomputes; on a data root, each rate and the gate
               thicknesses lie inside the stated plausibility bounds
               for the ice sheet.

A refusal receipt (refused true) attests PASS only as a refusal: the
identity checks hold, the reason code is one the executor issues, and
the refusal is reproduced here (on a fixture by re-running the
executor's own assembly and compute at the bound parameters; on a
data root the same way on the tree when --data-root names it, else
from the gate sets, domains and epoch families the receipt records,
or on the executor's word where the tree is needed). The verdict line
then carries PASS refusal, and the exit is 0.

--out writes the attestation: the verdict, whether it is a refusal,
the digests, the run id, the capability, bundle and runtime blocks
copied from the receipt, and every check.

  ice_sheet_input_output_check.py RECEIPT.json [--computation PATH]
      [--data-root DIR] [--out ATTESTATION.json]
  ice_sheet_input_output_check.py --selftest
"""

import argparse
import contextlib
import csv
import datetime as dt
import hashlib
import importlib.util
import io
import json
import math
import re
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_COMPUTATION = HERE / "ice_sheet_input_output.py"
FIELDS = ("run_id", "computation", "code_sha256", "capability", "bundle", "runtime",
          "generated_utc", "data", "bound_parameters", "refused", "window", "gates", "terms",
          "series", "rates", "residual", "combined_uncertainty", "verdict", "bookkeeping",
          "caveats")
REFUSAL_FIELDS = ("run_id", "computation", "code_sha256", "capability", "bundle", "runtime",
                  "generated_utc", "data", "bound_parameters", "refused", "reason_code", "reason")
SERIES = ("smb", "discharge", "mass_rate")
REL_TOL = 1e-9
ROUNDING = 5.0e-5
CONFIDENCE = 0.95
MIN_DOF = 1.0
MIN_N_EFF = 1.0
Z95 = 1.959963984540054
TRUTH_BAND = {"smb": 40.0, "discharge": 30.0, "mass_rate_floor": 45.0}
PLAUSIBLE_DISCHARGE_GT_YR = {"greenland": (50.0, 1200.0), "antarctica": (200.0, 4000.0)}
PLAUSIBLE_SMB_GT_YR = {"greenland": (0.0, 1200.0), "antarctica": (500.0, 4000.0)}
PLAUSIBLE_MASS_RATE_GT_YR = {"greenland": (-900.0, 400.0), "antarctica": (-900.0, 500.0)}
PLAUSIBLE_THICKNESS_M = (10.0, 4000.0)


def load(path: Path):
    spec = importlib.util.spec_from_file_location("ice_sheet_input_output", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def sha256_file(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def ym(d: str) -> int:
    return int(d[:4]) * 12 + int(d[5:7]) - 1


def year_of(d: str) -> int:
    return int(d[:4])


def close(a, b) -> bool:
    return abs(a - b) <= REL_TOL * max(1.0, abs(a), abs(b))


def numbers(v, n=None):
    return (isinstance(v, list) and (n is None or len(v) == n)
            and all(isinstance(x, (int, float)) and not isinstance(x, bool)
                    and math.isfinite(x) for x in v))


# ---- the independent recompute of the method statement

def betacf(a, b, x):
    tiny, eps = 1e-300, 3e-16
    qab, qap, qam = a + b, a + 1.0, a - 1.0
    c, d = 1.0, 1.0 - qab * x / qap
    d = 1.0 / (d if abs(d) > tiny else tiny)
    h = d
    for m in range(1, 400):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        d = 1.0 / (d if abs(d) > tiny else tiny)
        c = 1.0 + aa / (c if abs(c) > tiny else tiny)
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        d = 1.0 / (d if abs(d) > tiny else tiny)
        c = 1.0 + aa / (c if abs(c) > tiny else tiny)
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < eps:
            return h
    raise ArithmeticError("incomplete beta did not converge")


def betainc(a, b, x):
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    lbeta = math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b)
    front = math.exp(lbeta + a * math.log(x) + b * math.log(1.0 - x))
    if x < (a + 1.0) / (a + b + 2.0):
        return front * betacf(a, b, x) / a
    return 1.0 - front * betacf(b, a, 1.0 - x) / b


def t_cdf(t, df):
    x = df / (df + t * t)
    tail = 0.5 * betainc(df / 2.0, 0.5, x)
    return 1.0 - tail if t >= 0 else tail


def t_quantile(p, df):
    lo, hi = 0.0, 1.0
    while t_cdf(hi, df) < p:
        hi *= 2.0
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        if t_cdf(mid, df) < p:
            lo = mid
        else:
            hi = mid
        if hi - lo < 1e-13 * max(1.0, hi):
            break
    return 0.5 * (lo + hi)


def mean_recompute(epochs, values, unc):
    """Written from the method statement: the mean of the epochs; the
    lag-1 autocorrelation over epochs one year apart; n_eff the AR(1)
    estimate clipped to [1, n]; Student's t on n_eff minus 1; the
    larger of the sampling error and the formal error of the mean,
    which is the mean of the per epoch uncertainties."""
    n = len(values)
    out = {"n": n, "interval": False}
    if n < 2:
        return out
    mean = sum(values) / n
    formal_se = sum(unc) / n
    out.update({"rate": mean, "formal_se": formal_se, "formal_95": Z95 * formal_se})
    ss = sum((x - mean) ** 2 for x in values)
    sd = math.sqrt(ss / (n - 1))
    pairs = [(i, i + 1) for i in range(n - 1) if year_of(epochs[i + 1]) - year_of(epochs[i]) == 1]
    r1 = (sum((values[i] - mean) * (values[j] - mean) for i, j in pairs) / ss) if ss > 0 and pairs else 0.0
    n_ar1 = n * (1.0 - r1) / (1.0 + r1) if r1 < 1.0 else MIN_N_EFF
    n_eff = min(float(n), max(MIN_N_EFF, n_ar1))
    dof = n_eff - 1.0
    sampling_se = sd / math.sqrt(n_eff)
    out.update({"sd": sd, "r1": r1, "n_eff_ar1": n_ar1, "n_eff": n_eff, "dof": dof,
                "sampling_se": sampling_se})
    if dof < MIN_DOF or sd == 0.0:
        return out
    tq = t_quantile(0.5 + CONFIDENCE / 2.0, dof)
    se = max(sampling_se, formal_se)
    half = tq * se
    out.update({"interval": True, "t_quantile": tq, "se": se, "half_width": half,
                "ci_low": mean - half, "ci_high": mean + half,
                "se_basis": "sampling" if sampling_se >= formal_se else "formal"})
    return out


def check_rate_block(block, epochs, values, unc):
    """None when the block recomputes, else why not."""
    if not isinstance(block, dict):
        return "missing or not an object"
    if block.get("confidence") != CONFIDENCE:
        return f"confidence {block.get('confidence')}"
    if block.get("epochs") != list(epochs) or block.get("n_epochs") != len(epochs):
        return "epochs disagree with the series"
    c = mean_recompute(list(epochs), list(values), list(unc))
    if "rate" not in c:
        return None if block.get("stated") is False and block.get("reason") else \
            "block states a rate the recompute cannot form"
    for k in ("rate", "formal_se", "formal_95", "sd", "r1", "n_eff_ar1", "n_eff", "dof",
              "sampling_se"):
        if k not in c:
            continue
        v = block.get(k)
        if not isinstance(v, (int, float)) or not close(v, c[k]):
            return f"{k} {v} does not recompute ({c.get(k)})"
    if block.get("stated") is False:
        if c["interval"]:
            return "block refuses an interval the recompute states"
        return None if isinstance(block.get("reason"), str) and block["reason"] else \
            "refused interval carries no reason"
    if block.get("stated") is not True:
        return "stated must be true or false"
    if not c["interval"]:
        return "block states an interval the recompute refuses"
    for k in ("t_quantile", "se", "half_width", "ci_low", "ci_high"):
        v = block.get(k)
        if not isinstance(v, (int, float)) or not close(v, c[k]):
            return f"{k} {v} does not recompute ({c[k]})"
    if block.get("se_basis") != c["se_basis"]:
        return f"se_basis {block.get('se_basis')} is not the larger error ({c['se_basis']})"
    if block.get("significant_at_confidence") is not (c["ci_low"] * c["ci_high"] > 0):
        return "significance flag disagrees with the interval"
    return None


def systematic_value(book: dict, gate_set: str) -> float:
    sens = ((book.get("gates") or {}).get(gate_set) or {}).get("discharge_sensitivity")
    values = [v.get("discharge_gt_per_yr_full_series") for v in (sens or {}).values()
              if isinstance(v, dict)
              and isinstance(v.get("discharge_gt_per_yr_full_series"), (int, float))]
    return 0.5 * (max(values) - min(values)) if len(values) >= 2 else 0.0


# ---- a second implementation of the two terms

def discharge_from_rows(vel_rows, thk_rows, ice_sheet, gate_set, family, density):
    """The discharge at every epoch, from the term rows, written from
    the discharge rule rather than from the executor's assembly."""
    thick = {(r["gate"], int(r["node"])): r for r in thk_rows
             if r["ice_sheet"] == ice_sheet and r["gate_set"] == gate_set}
    vel = [r for r in vel_rows if r["ice_sheet"] == ice_sheet and r["gate_set"] == gate_set
           and r.get("sampling") == family]
    nodes = sorted({(r["gate"], int(r["node"])) for r in vel})
    by_epoch = {}
    for r in vel:
        by_epoch.setdefault(r["epoch"], {})[(r["gate"], int(r["node"]))] = r
    out, per_gate, errs = {}, {}, {}
    for epoch in sorted(by_epoch):
        here = by_epoch[epoch]
        if any(k not in here or not here[k]["v_normal_m_per_yr"] for k in nodes):
            continue
        total, gates, gate_err = 0.0, {}, {}
        for k in nodes:
            v, t = here[k], thick[k]
            u = float(v["v_normal_m_per_yr"])
            w = float(v["width_m"]) / float(v["areal_scale"])
            h = float(t["thickness_m"])
            f = density * u * w * h / 1e12
            du = float(v["v_normal_error_m_per_yr"] or 0.0)
            dh = float(t["thickness_error_m"] or 0.0)
            gate_err[k[0]] = gate_err.get(k[0], 0.0) + density * w * math.sqrt(
                (du * h) ** 2 + (u * dh) ** 2) / 1e12
            total += f
            gates[k[0]] = gates.get(k[0], 0.0) + f
        out[epoch] = total
        per_gate[epoch] = gates
        errs[epoch] = math.sqrt(sum(e * e for e in gate_err.values()))
    return out, errs, per_gate, nodes, thick


def smb_from_rows(smb_rows, ice_sheet, domains):
    """The surface mass balance at every year, the period weighted mean
    of the product's steps in it, written from the annualisation rule."""
    per_year = {}
    for r in smb_rows:
        if r["ice_sheet"] == ice_sheet and r["domain"] in domains:
            per_year.setdefault(year_of(r["month"]), []).append(r)
    out, errs, steps = {}, {}, {}
    for year, rows in per_year.items():
        w = [float(s["period_years"]) for s in rows]
        tw = sum(w)
        if tw <= 0:
            continue
        key = f"{year:04d}-01"
        out[key] = sum(float(s["value_gt_per_yr"]) * p for s, p in zip(rows, w)) / tw
        errs[key] = sum(float(s["uncertainty_gt_per_yr"]) * p for s, p in zip(rows, w)) / tw
        steps[key] = len(rows)
    return out, errs, steps


def rows_of(mod, fx, data_root):
    """The term rows behind a receipt: the regenerated fixture, or the
    tree the attester was pointed at. A tree that drifted from its own
    stamp yields nothing, and the data check is where that is reported."""
    if fx is not None:
        return fx["rows"], None
    if data_root is not None and (Path(data_root) / "RECORD.json").is_file():
        try:
            tree = mod.read_data_root(Path(data_root))
        except SystemExit:
            return None, None
        return tree["rows"], tree
    return None, None


# ---- the attestation

def attest(receipt_path: Path, computation: Path, data_root=None):
    """(verdict, refusal, checks, receipt) for one receipt."""
    checks = []

    def check(name, ok, detail):
        checks.append({"name": name, "ok": bool(ok), "detail": detail})
        return bool(ok)

    try:
        r = json.loads(receipt_path.read_text(encoding="utf-8"))
        assert isinstance(r, dict)
    except (OSError, ValueError, AssertionError) as e:
        check("fields", False, f"unreadable or not a JSON object: {e}")
        return "FAIL", False, checks, {}
    mod = load(computation)
    refusal = r.get("refused") is True
    fields = REFUSAL_FIELDS if refusal else FIELDS
    missing = [f for f in fields if f not in r]
    check("fields", not missing, "all present" if not missing else f"missing {missing}")

    sanctioned = sha256_file(computation)
    check("code", r.get("code_sha256") == sanctioned,
          f"receipt {r.get('code_sha256')} vs sanctioned {sanctioned}")

    identity = mod.package_identity(mod.package_root(computation.parent))
    bundle = r.get("bundle") or {}
    cap = r.get("capability") or {}
    cap_ok = (isinstance(cap, dict) and isinstance(cap.get("name"), str) and cap["name"]
              and isinstance(cap.get("version"), str) and cap["version"] and "release_lock" in cap
              and (cap["release_lock"] is None
                   or re.fullmatch(r"sha256:[0-9a-f]{64}", str(cap["release_lock"]))))
    check("release", bundle == identity and bool(identity.get("name")) and cap_ok,
          f"bundle {bundle} vs this tree {identity}; capability {cap} "
          f"{'well formed' if cap_ok else 'malformed'}")
    rt = r.get("runtime") or {}
    check("runtime", isinstance(rt, dict) and isinstance(rt.get("name"), str) and bool(rt.get("name")),
          f"runtime {rt.get('name')!r} {rt.get('version') or ''}".strip())

    data = r.get("data") or {}
    bound = r.get("bound_parameters") or {}
    window = str(bound.get("window", ""))
    m = re.fullmatch(r"(\d{4}-\d{2}):(\d{4}-\d{2})", window)
    start, end = (m.group(1), m.group(2)) if m else (None, None)
    ice_sheet = bound.get("ice_sheet")
    gate_set = bound.get("gates")
    family = bound.get("velocity_epoch")
    density = bound.get("ice_density")
    fx = None
    if data.get("mode") == "fixture":
        seed = data.get("seed")
        ok = isinstance(seed, int)
        if ok:
            fx = mod.make_fixture(seed)
            digest = mod.fixture_digest(fx)
            ok = (data.get("digest") == digest and data.get("generator_sha256") == sanctioned
                  and data.get("spans", {}).get("velocity") == list(mod.FIXTURE_SPANS["velocity"]))
            detail = (f"regenerated fixture at seed {seed}: {digest}; receipt {data.get('digest')}; "
                      f"generator match {data.get('generator_sha256') == sanctioned}")
        else:
            detail = "fixture seed missing"
        check("data", ok, detail)
    elif data.get("mode") == "data-root":
        rec = data.get("record")
        files = data.get("files") or {}
        ok = (isinstance(rec, dict) and isinstance(rec.get("record"), str) and rec.get("record")
              and isinstance(rec.get("manifest_sha256"), str)
              and re.fullmatch(r"sha256:[0-9a-f]{64}", str(data.get("record_sha256", "")))
              and isinstance(files, dict) and "velocity.csv" in files
              and isinstance(data.get("data_root"), str) and data["data_root"])
        detail = f"data root {data.get('data_root')} stamped {rec.get('record') if isinstance(rec, dict) else None}"
        if ok and data_root is not None:
            root = Path(data_root).expanduser().resolve()
            problems, manifest = [], {}
            if not (root / "RECORD.json").is_file():
                problems.append("no RECORD.json in the tree")
            elif sha256_file(root / "RECORD.json") != data["record_sha256"]:
                problems.append("RECORD.json digest differs from the receipt's")
            else:
                try:
                    manifest = json.loads((root / "RECORD.json").read_text(encoding="utf-8")).get("manifest") or {}
                except (OSError, ValueError, AttributeError):
                    problems.append("RECORD.json unreadable")
            for name, digest in files.items():
                p = root / name
                if not p.is_file():
                    problems.append(f"{name} missing from the tree")
                elif sha256_file(p) != digest:
                    problems.append(f"{name} digest differs from the receipt's")
                if manifest.get(name) != digest:
                    problems.append(f"{name} digest is not the RECORD.json manifest's ({manifest.get(name)})")
            if mod.relative_root(root) != data["data_root"]:
                problems.append(f"the tree is {mod.relative_root(root)}, the receipt names {data['data_root']}")
            ok = not problems
            detail += "; " + ("; ".join(problems) if problems else
                              f"the tree at {root} matches the receipt's RECORD and file digests")
        check("data", ok, detail)
    else:
        check("data", False, f"data mode {data.get('mode')!r} is neither fixture nor data-root")

    if refusal:
        code = r.get("reason_code")
        recognized = code in mod.REASONS
        reproduced, why = False, "reason not reproduced"
        if recognized and start and ice_sheet in ("greenland", "antarctica"):
            rows, tree = rows_of(mod, fx, data_root)
            if rows is not None:
                book = (json.loads(json.dumps(mod.FIXTURE_BOOKKEEPING)) if fx is not None
                        else tree["bookkeeping"])
                if fx is not None:
                    book["gates"] = mod.fixture_gate_table(fx)
                absent = {} if fx is not None else tree["absent"]
                terms, again = mod.assemble(ice_sheet, gate_set, family, rows,
                                            float(density or 917.0), book, absent)
                if again is None:
                    _, again = mod.compute(terms, start, end, book, ice_sheet, gate_set, family)
                reproduced = again is not None and again[0] == code
                why = (f"the executor's assembly and compute on the "
                       f"{'regenerated fixture' if fx is not None else 'tree'} refuse with "
                       f"{again and again[0]!r}: {reproduced}")
            else:
                sets = (data.get("gate_sets") or {})
                families = data.get("velocity_epoch_families") or []
                domains = (data.get("domains") or {}).get("smb") or []
                spans = (data.get("spans") or {}).get("terms") or {}
                key = f"{ice_sheet}/{gate_set}"
                if code == "term-not-in-root":
                    absent = ((data.get("record") or {}).get("terms_absent") or {})
                    present = ((data.get("record") or {}).get("terms_present") or [])
                    reproduced = bool(absent) or not {"velocity", "thickness", "smb"} <= set(present) \
                        or key not in (sets.get("thickness") or [])
                    why = f"the record's terms_present {present} and terms_absent {sorted(absent)}: {reproduced}"
                elif code == "gate-set-not-in-root":
                    reproduced = key not in (sets.get("velocity") or [])
                    why = f"the velocity gate sets {sets.get('velocity')} lack {key}: {reproduced}"
                elif code == "velocity-epoch-not-in-root":
                    reproduced = family not in families
                    why = f"the velocity epoch families {families} lack {family!r}: {reproduced}"
                elif code == "smb-term-missing":
                    need = {f"{ice_sheet}/{d}" for d in mod.GROUNDED_SMB_DOMAINS[ice_sheet]}
                    reproduced = not need & set(domains)
                    why = f"the grounded domains {sorted(need)} against the root's {domains}: {reproduced}"
                elif code == "window-outside-epochs":
                    inside = all(isinstance(spans.get(k), list)
                                 and ym(spans[k][0]) <= ym(end) and ym(start) <= ym(spans[k][1])
                                 for k in ("discharge", "smb"))
                    reproduced = not inside
                    why = f"the window {window} against the recorded spans {spans}: outside {reproduced}"
                elif code == "too-few-epochs" and ym(end) - ym(start) + 1 < mod.MIN_WINDOW_MONTHS:
                    reproduced = True
                    why = f"the window {window} is shorter than {mod.MIN_WINDOW_MONTHS} months"
                else:
                    reproduced, why = True, "a data-root refusal of this kind is taken on the executor's word"
        check("refusal", recognized and reproduced,
              f"reason_code {code!r} {'recognized' if recognized else 'unknown'}; {why}")
        verdict = "PASS" if all(c["ok"] for c in checks) else "FAIL"
        return verdict, True, checks, r

    # gates
    rows, tree = rows_of(mod, fx, data_root)
    g = r.get("gates") or {}
    gate_problems = []
    if g.get("gate_set") != gate_set:
        gate_problems.append(f"the gate block names {g.get('gate_set')!r}, the run bound {gate_set!r}")
    if g.get("spans_margin") is not True:
        gate_problems.append(f"spans_margin {g.get('spans_margin')!r}; a sheet wide rate needs a "
                             "gate set that spans the grounded margin")
    prov = g.get("provenance")
    if not (isinstance(prov, list) and prov and set(prov) <= set(mod.SUPPORTED_PROVENANCE)):
        gate_problems.append(f"the node methods are {prov}, not only {list(mod.SUPPORTED_PROVENANCE)}")
    msk = g.get("mask")
    if not (isinstance(msk, list) and msk and set(msk) <= set(mod.GROUNDED_MASK)):
        gate_problems.append(f"the node masks are {msk}, not only {list(mod.GROUNDED_MASK)}")
    thk = g.get("thickness_m") or {}
    if not all(isinstance(thk.get(k), (int, float)) for k in ("min", "max", "mean")):
        gate_problems.append("the gate block carries no thickness range")
    if rows is not None:
        _, _, _, nodes, thick = discharge_from_rows(
            rows["velocity"], rows["thickness"], ice_sheet, gate_set, family,
            float(density or 917.0))
        if g.get("n_nodes") != len(nodes):
            gate_problems.append(f"n_nodes {g.get('n_nodes')} against {len(nodes)} in the term files")
        if g.get("n_gates") != len({a for a, _ in nodes}):
            gate_problems.append(f"n_gates {g.get('n_gates')} against {len({a for a, _ in nodes})}")
        if nodes:
            tv = [float(thick[k]["thickness_m"]) for k in nodes]
            for key, want in (("min", min(tv)), ("max", max(tv)), ("mean", sum(tv) / len(tv))):
                if not close(float(thk.get(key, 0.0)), want):
                    gate_problems.append(f"thickness_m.{key} {thk.get(key)} does not recompute ({want})")
    check("gates", not gate_problems,
          "; ".join(gate_problems) if gate_problems else
          f"{g.get('n_gates')} gates, {g.get('n_nodes')} nodes, every thickness "
          f"{prov} on {msk}, spanning the margin, thickness "
          f"{thk.get('min'):.1f} to {thk.get('max'):.1f} m")

    # series
    s = r.get("series") or {}
    w = r.get("window") or {}
    n_cal = ym(end) - ym(start) + 1 if start else 0
    series_ok = (bool(start) and w.get("start") == start and w.get("end") == end
                 and w.get("n_calendar") == n_cal and isinstance(w.get("years"), (int, float))
                 and close(w["years"], n_cal / 12.0)
                 and isinstance(density, (int, float)) and density > 0)
    detail = "window well formed" if series_ok else "window or density malformed"
    epochs = None
    for name in SERIES:
        t_ = s.get(name) or {}
        ep = t_.get("epochs")
        ok = (isinstance(ep, list) and len(ep) >= 3
              and all(isinstance(x, str) and re.fullmatch(r"\d{4}-\d{2}", x) for x in ep)
              and ep == sorted(ep) and len(set(ep)) == len(ep)
              and all(ym(start) <= ym(x) <= ym(end) for x in ep)
              and numbers(t_.get("values"), len(ep)) and numbers(t_.get("uncertainties"), len(ep)))
        series_ok = series_ok and ok
        if ok and epochs is None:
            epochs = ep
        elif ok and ep != epochs:
            series_ok = False
    if series_ok:
        dev = 0.0
        for i in range(len(epochs)):
            want = s["smb"]["values"][i] - s["discharge"]["values"][i]
            want_u = math.sqrt(s["smb"]["uncertainties"][i] ** 2
                               + s["discharge"]["uncertainties"][i] ** 2)
            dev = max(dev, abs(want - s["mass_rate"]["values"][i]),
                      abs(want_u - s["mass_rate"]["uncertainties"][i]))
        per_gate = s.get("discharge_per_gate") or {}
        gdev, gok = 0.0, set(per_gate) == set(epochs)
        if gok:
            for i, e in enumerate(epochs):
                gdev = max(gdev, abs(sum(per_gate[e].values()) - s["discharge"]["values"][i]))
            gok = gdev <= REL_TOL * 1e3
        series_ok = dev <= REL_TOL * 1e3 and gok
        detail = (f"the mass rate series is the surface mass balance less the discharge at every "
                  f"epoch (max deviation {dev:.2e}); the per gate discharges add to the total "
                  f"(max deviation {gdev:.2e}): {gok}")
    if series_ok and rows is not None:
        d_by, d_err, per_gate_r, nodes, _ = discharge_from_rows(
            rows["velocity"], rows["thickness"], ice_sheet, gate_set, family, float(density))
        smb_by, smb_err, steps = smb_from_rows(
            rows["smb"], ice_sheet, mod.GROUNDED_SMB_DOMAINS[ice_sheet])
        maxdev, agree = 0.0, True
        for i, e in enumerate(epochs):
            if e not in d_by or e not in smb_by:
                agree = False
                break
            maxdev = max(maxdev, abs(d_by[e] - s["discharge"]["values"][i]),
                         abs(d_err[e] - s["discharge"]["uncertainties"][i]),
                         abs(smb_by[e] - s["smb"]["values"][i]),
                         abs(smb_err[e] - s["smb"]["uncertainties"][i]))
        series_ok = agree and maxdev <= 1e-6
        detail += (f"; the term rows rebuild the same discharge and surface mass balance by a "
                   f"second implementation of the discharge and annualisation rules (max "
                   f"deviation {maxdev:.2e}): {series_ok}")
    check("series", series_ok, detail)

    # recompute
    rec_ok, rec_detail = False, "series not checkable"
    terms = r.get("terms") or {}
    if series_ok:
        rates = r.get("rates") or {}
        problems = []
        for name in SERIES:
            t_ = s[name]
            err = check_rate_block(rates.get(name), t_["epochs"], t_["values"], t_["uncertainties"])
            if err:
                problems.append(f"rates.{name}: {err}")
        if not problems:
            for name in SERIES:
                if rates[name].get("stated") is not True:
                    problems.append(f"rates.{name} carries no interval; the run should have refused")
        if not problems:
            years = n_cal / 12.0
            for name in SERIES:
                v = (terms.get(name) or {}).get("rate_gt_per_yr")
                want = rates[name]["rate"]
                if not isinstance(v, (int, float)) or abs(v - want) > ROUNDING + 1e-9:
                    problems.append(f"terms.{name}.rate_gt_per_yr {v} is not the block's rate rounded")
                ch = (terms.get(name) or {}).get("change_over_window_gt")
                if not isinstance(ch, (int, float)) or not close(ch, want * years):
                    problems.append(f"terms.{name}.change_over_window_gt {ch} does not recompute")
                tu = (terms.get(name) or {}).get("uncertainty_gt_per_yr")
                if not isinstance(tu, (int, float)) or not close(tu, rates[name]["half_width"]):
                    problems.append(f"terms.{name}.uncertainty_gt_per_yr {tu} is not the half width")
            mass_rate = rates["mass_rate"]["rate"]
            sysv = systematic_value(r.get("bookkeeping") or {}, gate_set)
            bar = rates["mass_rate"]["half_width"] + sysv
            cu = r.get("combined_uncertainty") or {}
            stated = cu.get("terms_gt_per_yr") or {}
            for n_ in ("smb", "discharge"):
                if not isinstance(stated.get(n_), (int, float)) or not close(stated[n_], rates[n_]["half_width"]):
                    problems.append(f"combined_uncertainty.terms_gt_per_yr.{n_} {stated.get(n_)} "
                                    "is not the block's half width")
            for k, want in (("mass_rate_half_width_gt_per_yr", rates["mass_rate"]["half_width"]),
                            ("bar_gt_per_yr", bar)):
                v = cu.get(k)
                if not isinstance(v, (int, float)) or not close(v, want):
                    problems.append(f"combined_uncertainty.{k} {v} does not recompute ({want})")
            sv = (cu.get("gate_systematic") or {}).get("value_gt_per_yr")
            if not isinstance(sv, (int, float)) or not close(sv, sysv):
                problems.append(f"gate_systematic {sv} does not recompute from the bookkeeping ({sysv})")
            rs = r.get("residual") or {}
            vd = r.get("verdict") or {}
            significant = abs(mass_rate) > bar
            sign = "loss" if significant and mass_rate < 0 else (
                "gain" if significant else "indistinguishable")
            if (not isinstance(rs.get("rate_gt_per_yr"), (int, float))
                    or not close(rs["rate_gt_per_yr"], mass_rate)
                    or rs.get("n_epochs") != len(epochs)
                    or not isinstance(rs.get("smb_gt_per_yr"), (int, float))
                    or not close(rs["smb_gt_per_yr"], rates["smb"]["rate"])
                    or not isinstance(rs.get("discharge_gt_per_yr"), (int, float))
                    or not close(rs["discharge_gt_per_yr"], rates["discharge"]["rate"])
                    or not isinstance(rs.get("change_over_window_gt"), (int, float))
                    or not close(rs["change_over_window_gt"], mass_rate * years)):
                problems.append(f"residual block {rs.get('rate_gt_per_yr')} does not recompute "
                                f"({mass_rate} on {len(epochs)} epochs)")
            if (not isinstance(vd.get("mass_rate_gt_per_yr"), (int, float))
                    or not close(vd["mass_rate_gt_per_yr"], mass_rate)
                    or not isinstance(vd.get("bar_gt_per_yr"), (int, float))
                    or not close(vd["bar_gt_per_yr"], bar)
                    or vd.get("significant_at_confidence") is not significant
                    or vd.get("sign") != sign):
                problems.append(f"verdict {vd.get('significant_at_confidence')} {vd.get('sign')} "
                                f"mass rate {vd.get('mass_rate_gt_per_yr')} bar {vd.get('bar_gt_per_yr')} "
                                f"does not recompute (significant {significant}, {sign}, "
                                f"{mass_rate}, bar {bar})")
            # the surface mass balance less the discharge is the mass rate, in the means too
            if not close(rates["smb"]["rate"] - rates["discharge"]["rate"], mass_rate):
                problems.append("the mass rate is not the surface mass balance rate less the "
                                "discharge rate on the same epochs")
        rec_ok = not problems
        rec_detail = ("; ".join(problems) if problems else
                      "three rates with intervals and formal errors, the gate systematic, the "
                      "bar, the residual block and the verdict recompute")
    check("recompute", rec_ok, rec_detail)

    # bookkeeping
    book = r.get("bookkeeping") or {}
    lacking = [f"{sec}.{key}" for sec, key in mod.REQUIRED_BOOKKEEPING
               if not (isinstance(book.get(sec), dict) and book[sec].get(key) not in (None, "", {}))]
    for key in ("gates", "closure"):
        if not (isinstance(book.get(key), dict) and book[key]):
            lacking.append(key)
    dens = book.get("density") if isinstance(book.get("density"), dict) else {}
    disc = book.get("discharge_rule") if isinstance(book.get("discharge_rule"), dict) else {}
    ann = book.get("annualisation") if isinstance(book.get("annualisation"), dict) else {}
    eh = book.get("epoch_handling") if isinstance(book.get("epoch_handling"), dict) else {}
    steps_ok = True
    if rows is not None and epochs:
        _, _, steps = smb_from_rows(rows["smb"], ice_sheet, mod.GROUNDED_SMB_DOMAINS[ice_sheet])
        steps_ok = (ann.get("steps_per_year") or {}) == {e: steps.get(e) for e in epochs}
    book_ok = (not lacking
               and dens.get("ice_density_kg_m3") == density
               and isinstance(dens.get("basis"), str) and dens["basis"]
               and isinstance(disc.get("rule"), str) and disc["rule"]
               and disc.get("gate_set") == gate_set
               and disc.get("n_nodes") == (r.get("gates") or {}).get("n_nodes")
               and isinstance(disc.get("thickness_epoch"), str) and disc["thickness_epoch"]
               and isinstance(ann.get("rule"), str) and ann["rule"] and steps_ok
               and isinstance(eh.get("rule"), str) and eh["rule"]
               and eh.get("velocity_epoch") == family
               and eh.get("epochs_used") == epochs
               and isinstance(eh.get("years_in_the_window_without_both_terms"), list))
    check("bookkeeping", book_ok,
          (f"lacks {lacking}; " if lacking else "every required statement present; ")
          + f"density {dens.get('ice_density_kg_m3')} kg/m3; gate set {disc.get('gate_set')} with "
          f"{disc.get('n_nodes')} nodes; velocity epoch {eh.get('velocity_epoch')}; "
          f"{len(eh.get('years_in_the_window_without_both_terms') or [])} years in the window "
          f"without both terms; annualisation steps agree: {steps_ok}")

    # plausibility
    if rec_ok:
        vd, tr = r["verdict"], r["rates"]
        if fx is not None:
            truth = mod.TRUTH[ice_sheet]
            mean_year = sum(year_of(e) for e in epochs) / len(epochs)
            want_d = (truth["discharge_gt_yr_at_2005"]
                      + truth["discharge_trend_gt_yr_per_yr"] * (mean_year - 2005))
            want_s = truth["smb_gt_yr"]
            want_m = want_s - want_d
            near_d = abs(tr["discharge"]["rate"] - want_d)
            near_s = abs(tr["smb"]["rate"] - want_s)
            near_m = abs(vd["mass_rate_gt_per_yr"] - want_m)
            band_m = max(TRUTH_BAND["mass_rate_floor"], vd["bar_gt_per_yr"])
            ok = (near_d <= TRUTH_BAND["discharge"] and near_s <= TRUTH_BAND["smb"]
                  and near_m <= band_m)
            detail = (f"known truth: discharge within {near_d:.3f} of {want_d:.3f} (band "
                      f"{TRUTH_BAND['discharge']}), surface mass balance within {near_s:.3f} of "
                      f"{want_s} (band {TRUTH_BAND['smb']}), mass rate within {near_m:.3f} of the "
                      f"planted {want_m:.3f} (band {band_m:.3f}), verdict "
                      f"{vd.get('sign')} {vd.get('significant_at_confidence')}")
        else:
            dlo, dhi = PLAUSIBLE_DISCHARGE_GT_YR.get(ice_sheet, (-1e9, 1e9))
            slo, shi = PLAUSIBLE_SMB_GT_YR.get(ice_sheet, (-1e9, 1e9))
            mlo, mhi = PLAUSIBLE_MASS_RATE_GT_YR.get(ice_sheet, (-1e9, 1e9))
            thk = (r.get("gates") or {}).get("thickness_m") or {}
            ok = (dlo <= tr["discharge"]["rate"] <= dhi and slo <= tr["smb"]["rate"] <= shi
                  and mlo <= vd["mass_rate_gt_per_yr"] <= mhi
                  and PLAUSIBLE_THICKNESS_M[0] <= float(thk.get("min", 0.0))
                  and float(thk.get("max", 1e9)) <= PLAUSIBLE_THICKNESS_M[1]
                  and vd["bar_gt_per_yr"] > 0)
            detail = (f"{ice_sheet}: discharge {tr['discharge']['rate']:.3f} within [{dlo}, {dhi}], "
                      f"surface mass balance {tr['smb']['rate']:.3f} within [{slo}, {shi}], mass "
                      f"rate {vd['mass_rate_gt_per_yr']:.3f} within [{mlo}, {mhi}] Gt/yr, gate "
                      f"thicknesses {thk.get('min')} to {thk.get('max')} m within "
                      f"{PLAUSIBLE_THICKNESS_M}; the verdict ({vd.get('sign')}) stands on the recompute")
        check("plausible", ok, detail)
    else:
        check("plausible", False, "not checkable: the recompute failed")

    verdict = "PASS" if all(c["ok"] for c in checks) else "FAIL"
    return verdict, False, checks, r


def attestation_doc(verdict, refusal, checks, r, receipt_path, computation):
    return {
        "verdict": verdict, "refusal": refusal,
        "attester": "skills/ice-sheet-input-output/scripts/ice_sheet_input_output_check.py",
        "attester_sha256": sha256_file(Path(__file__).resolve()),
        "computation_sha256": sha256_file(computation),
        "receipt": receipt_path.name, "receipt_sha256": sha256_file(receipt_path),
        "run_id": r.get("run_id"),
        "capability": r.get("capability") or {}, "bundle": r.get("bundle") or {},
        "runtime": r.get("runtime") or {},
        "attested_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "checks": checks,
    }


def report(verdict, refusal, checks, r) -> str:
    lines = [f"PASS {c['name']}" if c["ok"] else f"FAIL {c['name']}: {c['detail']}" for c in checks]
    bound = r.get("bound_parameters") or {}
    if verdict != "PASS":
        first = next(c for c in checks if not c["ok"])
        lines.append(f"FAIL {first['name']}: {first['detail']}")
    elif refusal:
        lines.append(f"PASS refusal ({r.get('reason_code')}) run {r.get('run_id')}: "
                     f"{bound.get('ice_sheet')} {bound.get('window')} gates {bound.get('gates')} "
                     f"refused, {r.get('reason')}")
    else:
        v, t = r["verdict"], r["terms"]
        lines.append(f"PASS run {r.get('run_id')}: {bound.get('ice_sheet')} {bound.get('window')} "
                     f"(gates {bound.get('gates')}, {bound.get('velocity_epoch')}), surface mass "
                     f"balance {t['smb']['rate_gt_per_yr']:+.3f} Gt/yr, discharge "
                     f"{t['discharge']['rate_gt_per_yr']:+.3f} Gt/yr, mass rate "
                     f"{v['mass_rate_gt_per_yr']:+.3f} against bar {v['bar_gt_per_yr']:.3f}, "
                     f"significant_at_confidence "
                     f"{str(v['significant_at_confidence']).lower()} ({v['sign']}) (recomputed)")
    return "\n".join(lines)


# ---- selftest

def selftest(computation: Path) -> int:
    mod = load(computation)

    def run(argv, path):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            return mod.main([*argv, "--runtime", "selftest", "--receipt", str(path)])

    def verdict_of(path, comp=None, root=None):
        v, refusal, checks, _ = attest(path, comp or computation, root)
        return v, refusal, [c["name"] for c in checks if not c["ok"]]

    def first_fail(path, comp=None, root=None):
        v, _, failed = verdict_of(path, comp, root)
        return failed[0] if v == "FAIL" and failed else None

    def tampered(src: Path, dst: Path, edit):
        doc = json.loads(src.read_text(encoding="utf-8"))
        edit(doc)
        dst.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
        return dst

    with tempfile.TemporaryDirectory() as d:
        w = Path(d)
        gl = ["--fixture", "--seed", "7", "--ice-sheet", "greenland", "--gates",
              "synthetic-outlets"]
        ref = w / "ref.json"
        assert run([*gl, "--window", "2005-01:2014-12"], ref) == 0
        assert verdict_of(ref) == ("PASS", False, []), verdict_of(ref)
        long = w / "long.json"
        assert run([*gl, "--window", "1995-01:2018-12"], long) == 0
        v, refusal, checks, doc = attest(long, computation)
        assert v == "PASS" and doc["verdict"]["sign"] == "loss", checks
        truth = mod.TRUTH["greenland"]
        assert abs(doc["terms"]["smb"]["rate_gt_per_yr"] - truth["smb_gt_yr"]) < 40.0, doc["terms"]

        # tampers, each failing on its check
        t1 = tampered(long, w / "t1.json", lambda r: r["series"]["discharge"]["values"].__setitem__(
            3, r["series"]["discharge"]["values"][3] + 1e-3))
        assert first_fail(t1) == "series", verdict_of(t1)
        t2 = tampered(long, w / "t2.json", lambda r: r["rates"]["smb"].__setitem__(
            "rate", r["rates"]["smb"]["rate"] * 1.001))
        assert first_fail(t2) == "recompute", verdict_of(t2)
        t3 = tampered(long, w / "t3.json", lambda r: r["verdict"].__setitem__(
            "significant_at_confidence", False))
        assert first_fail(t3) == "recompute", verdict_of(t3)
        t4 = tampered(long, w / "t4.json", lambda r: r["rates"]["mass_rate"].__setitem__(
            "half_width", r["rates"]["mass_rate"]["half_width"] / 2))
        assert first_fail(t4) == "recompute", verdict_of(t4)
        t5 = tampered(long, w / "t5.json", lambda r: r["bookkeeping"]["thickness"].pop("provenance_rule"))
        assert verdict_of(t5)[2] == ["bookkeeping"], verdict_of(t5)
        t6 = tampered(long, w / "t6.json", lambda r: r["runtime"].__setitem__("name", ""))
        assert verdict_of(t6)[2] == ["runtime"], verdict_of(t6)
        t7 = tampered(long, w / "t7.json", lambda r: r["data"].__setitem__("seed", 8))
        assert first_fail(t7) == "data", verdict_of(t7)
        t8 = tampered(long, w / "t8.json", lambda r: r["gates"].__setitem__(
            "provenance", ["mass_conservation", "interpolation"]))
        assert first_fail(t8) == "gates", verdict_of(t8)
        t9 = tampered(long, w / "t9.json", lambda r: r["gates"].__setitem__("spans_margin", False))
        assert first_fail(t9) == "gates", verdict_of(t9)
        t10 = tampered(long, w / "t10.json", lambda r: r["series"]["discharge_per_gate"][
            r["series"]["discharge"]["epochs"][0]].__setitem__("gate-01", 0.0))
        assert first_fail(t10) == "series", verdict_of(t10)
        t11 = tampered(long, w / "t11.json", lambda r: r["combined_uncertainty"][
            "gate_systematic"].__setitem__("value_gt_per_yr", 50.0))
        assert first_fail(t11) == "recompute", verdict_of(t11)
        t12 = tampered(long, w / "t12.json", lambda r: r["series"]["mass_rate"]["values"].__setitem__(
            0, r["series"]["mass_rate"]["values"][0] + 1.0))
        assert first_fail(t12) == "series", verdict_of(t12)
        w1 = tampered(long, w / "w1.json", lambda r: r["bundle"].__setitem__("version", "0.0.0"))
        assert verdict_of(w1)[2] == ["release"], verdict_of(w1)
        w2 = tampered(long, w / "w2.json", lambda r: r["capability"].__setitem__("name", ""))
        assert verdict_of(w2)[2] == ["release"], verdict_of(w2)

        # a tampered computation fails code and the generator digest
        bad = w / "ice_sheet_input_output.py"
        bad.write_bytes(computation.read_bytes() + b"\n")
        v, _, failed = verdict_of(long, bad)
        assert v == "FAIL" and "code" in failed and "data" in failed, failed

        # every refusal attests PASS as a refusal, exit 3 from the executor
        cases = [
            ("interior.json", [*gl[:-1], "synthetic-interior", "--window", "1995-01:2018-12"],
             "gate-thickness-interpolated"),
            ("shelf.json", [*gl[:-1], "synthetic-shelf", "--window", "1995-01:2018-12"],
             "gate-not-grounded"),
            ("partial.json", [*gl[:-1], "synthetic-partial", "--window", "1995-01:2018-12"],
             "gate-set-incomplete"),
            ("noset.json", [*gl[:-1], "no-such-set", "--window", "1995-01:2018-12"],
             "gate-set-not-in-root"),
            ("nofamily.json", [*gl, "--window", "1995-01:2018-12", "--velocity-epoch", "static"],
             "velocity-epoch-not-in-root"),
            ("outside.json", [*gl, "--window", "2021-01:2023-12"], "window-outside-epochs"),
            ("short.json", [*gl, "--window", "2017-01:2018-06"], "too-few-epochs"),
            ("antarctica.json", ["--fixture", "--seed", "7", "--ice-sheet", "antarctica",
                                 "--gates", "synthetic-outlets-ant", "--window", "1995-01:2018-12"],
             "smb-term-missing"),
        ]
        for name, argv, code in cases:
            p = w / name
            assert run(argv, p) == 3, name
            v, refusal, checks, doc = attest(p, computation)
            assert (v, refusal) == ("PASS", True) and doc["reason_code"] == code, (name, code, checks)
            assert "PASS refusal" in report(v, refusal, checks, doc)
        forged = tampered(w / "outside.json", w / "forged.json",
                          lambda r: r["bound_parameters"].__setitem__("window", "2005-01:2014-12"))
        assert verdict_of(forged)[2] == ["refusal"], verdict_of(forged)

        # the data-root path on the fixture written as a root
        root = w / "root"
        mod.write_fixture_root(mod.make_fixture(7), root)
        dr = w / "dataroot.json"
        assert run(["--data-root", str(root), "--ice-sheet", "greenland", "--gates",
                    "synthetic-outlets", "--window", "1995-01:2018-12"], dr) == 0
        assert verdict_of(dr) == ("PASS", False, []), verdict_of(dr)
        assert verdict_of(dr, None, root) == ("PASS", False, []), verdict_of(dr, None, root)
        t13 = tampered(dr, w / "t13.json", lambda r: r["series"]["smb"]["values"].__setitem__(
            2, r["series"]["smb"]["values"][2] + 1e-3))
        assert first_fail(t13, None, root) == "series", verdict_of(t13, None, root)
        # a value altered in a term file with RECORD.json untouched: the
        # executor refuses the drifted tree and the earlier receipt fails data
        lines = (root / "velocity.csv").read_text(encoding="utf-8").splitlines()
        cells = lines[5].split(",")
        cells[12] = f"{float(cells[12]) + 50.0:.9f}"
        lines[5] = ",".join(cells)
        (root / "velocity.csv").write_text("\n".join(lines) + "\n", encoding="utf-8")
        try:
            run(["--data-root", str(root), "--ice-sheet", "greenland", "--gates",
                 "synthetic-outlets", "--window", "1995-01:2018-12"], w / "drifted.json")
            raise AssertionError("the executor computed on a tree that drifted from its stamp")
        except SystemExit as e:
            assert "manifest" in str(e), e
        assert first_fail(dr, None, root) == "data", verdict_of(dr, None, root)
        rec = json.loads((root / "RECORD.json").read_text(encoding="utf-8"))
        rec["manifest"]["velocity.csv"] = sha256_file(root / "velocity.csv")
        (root / "RECORD.json").write_text(json.dumps(rec, indent=2) + "\n", encoding="utf-8")
        dr2 = w / "dataroot2.json"
        assert run(["--data-root", str(root), "--ice-sheet", "greenland", "--gates",
                    "synthetic-outlets", "--window", "1995-01:2018-12"], dr2) == 0
        assert verdict_of(dr2, None, root) == ("PASS", False, []), verdict_of(dr2, None, root)
        good = w / "root-good"
        mod.write_fixture_root(mod.make_fixture(7), good)
        assert first_fail(dr2, None, good) == "data", verdict_of(dr2, None, good)

        # term-not-in-root: the thickness term removed from a root, reproduced from the tree
        nothk = w / "root-nothk"
        mod.write_fixture_root(mod.make_fixture(7), nothk)
        (nothk / "thickness.csv").unlink()
        rec = json.loads((nothk / "RECORD.json").read_text(encoding="utf-8"))
        rec["terms_present"] = [x for x in rec["terms_present"] if x != "thickness"]
        rec["terms_absent"] = {"thickness": "selftest: the term was removed from the tree"}
        rec["manifest"].pop("thickness.csv")
        (nothk / "RECORD.json").write_text(json.dumps(rec, indent=2) + "\n", encoding="utf-8")
        tnr = w / "term-not-in-root.json"
        assert run(["--data-root", str(nothk), "--ice-sheet", "greenland", "--gates",
                    "synthetic-outlets", "--window", "1995-01:2018-12"], tnr) == 3
        assert json.loads(tnr.read_text())["reason_code"] == "term-not-in-root"
        assert verdict_of(tnr) == ("PASS", True, []), verdict_of(tnr)
        assert verdict_of(tnr, None, nothk) == ("PASS", True, []), verdict_of(tnr, None, nothk)

        # interval-not-stated: a root whose surface mass balance never moves
        flat = w / "root-flat"
        mod.write_fixture_root(mod.make_fixture(7), flat)
        rows = list(csv.DictReader((flat / "smb.csv").open(encoding="utf-8")))
        for r_ in rows:
            r_["value_gt_per_yr"] = "400.000000"
        with (flat / "smb.csv").open("w", encoding="utf-8", newline="") as f:
            wr = csv.DictWriter(f, fieldnames=list(rows[0]))
            wr.writeheader(); wr.writerows(rows)
        rec = json.loads((flat / "RECORD.json").read_text(encoding="utf-8"))
        rec["manifest"]["smb.csv"] = sha256_file(flat / "smb.csv")
        (flat / "RECORD.json").write_text(json.dumps(rec, indent=2) + "\n", encoding="utf-8")
        ins = w / "interval-not-stated.json"
        assert run(["--data-root", str(flat), "--ice-sheet", "greenland", "--gates",
                    "synthetic-outlets", "--window", "1995-01:2018-12"], ins) == 3
        got = json.loads(ins.read_text())["reason_code"]
        assert got == "interval-not-stated", got
        assert verdict_of(ins, None, flat) == ("PASS", True, []), verdict_of(ins, None, flat)

        # the attestation document carries the verdict and the identity blocks
        adoc = attestation_doc(*attest(ref, computation), ref, computation)
        assert adoc["verdict"] == "PASS" and adoc["capability"]["name"] \
            and adoc["runtime"]["name"] == "selftest"
        assert {c["name"] for c in adoc["checks"]} == {
            "fields", "code", "release", "runtime", "data", "gates", "series", "recompute",
            "bookkeeping", "plausible"}
    print("ice_sheet_input_output_check selftest: ok")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("receipt", nargs="?", type=Path)
    ap.add_argument("--computation", type=Path, default=DEFAULT_COMPUTATION)
    ap.add_argument("--data-root", type=Path, default=None,
                    help="verify the receipt's digests against this tree")
    ap.add_argument("--out", type=Path, default=None, help="write the attestation JSON here")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()
    computation = args.computation.resolve()
    if args.selftest:
        return selftest(computation)
    if not args.receipt:
        ap.error("give a receipt, or --selftest")
    verdict, refusal, checks, r = attest(args.receipt, computation, args.data_root)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(
            attestation_doc(verdict, refusal, checks, r, args.receipt, computation),
            indent=2) + "\n", encoding="utf-8")
    print(report(verdict, refusal, checks, r) + (f"; attestation {args.out}" if args.out else ""))
    return 0 if verdict == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
