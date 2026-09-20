#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Deterministic attester for the attested ice sheet mass balance
closure (ice_sheet_balance.py). Stdlib only, consumer side, no
language model.

A receipt from any runtime attests PASS (exit 0) only when ALL hold,
else FAIL (exit 1) naming the check; one line per check, PASS name or
FAIL name: reason:

  fields       every declared receipt field is present;
  code         the receipt's code_sha256 is the sanctioned executor
               beside this file (or the one --computation names), so an
               edited computation invalidates every earlier receipt;
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
  series       the four series are well formed on the window, the
               altimetric mass series is the stated density times the
               volume less the firn air volume at every epoch, the firn
               uncertainties are floored above the stated ones, the
               residual series is the difference of the two terms'
               annual-lag differences on their common epochs, and
               every value is what the regenerated fixture yields, or
               with --data-root what the tree's term files rebuild
               through the executor's own assembly (1e-9);
  recompute    every rate block (the annual-lag difference mean, its
               effective sample size, interval and formal error), the
               residual block on the common epochs, the selection
               systematic, the bar and the verdict recomputed here from
               the series match the receipt (1e-9 relative), by a
               second implementation of the method statement;
  bookkeeping  every required statement is present (the mass term's
               GIA, low-degree, frame, smoothing and selection; the
               volume term's reference, mask and not-mass statement;
               the firn term's reference, model and forcing; the
               closure table), the density and firn floor blocks agree
               with the bound parameters and the series, and the gap
               handling agrees with the mass months used;
  plausible    on the fixture, the known truth: the verdict says closed,
               each rate is within a stated band of the imposed one and
               the residual within a band of the planted one; on a data
               root, each rate lies inside the stated plausibility
               bounds for the ice sheet.

A refusal receipt (refused true) attests PASS only as a refusal: the
identity checks hold, the reason code is one the executor issues, and
the refusal is reproduced here (on a fixture by re-running the
executor's own assembly and compute at the bound parameters; on a
data root the same way on the tree when --data-root names it, else
from the spans and domains the receipt records, or on the executor's
word where the tree is needed). The verdict line then
carries PASS refusal, and the exit is 0.

--out writes the attestation: the verdict, whether it is a refusal,
the digests, the run id, the capability, bundle and runtime blocks
copied from the receipt, and every check.

  ice_sheet_balance_check.py RECEIPT.json [--computation PATH] [--data-root DIR] [--out ATTESTATION.json]
  ice_sheet_balance_check.py --selftest
"""

import argparse
import contextlib
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
DEFAULT_COMPUTATION = HERE / "ice_sheet_balance.py"
FIELDS = ("run_id", "computation", "code_sha256", "capability", "bundle", "runtime",
          "generated_utc", "data", "bound_parameters", "refused", "window", "terms", "series",
          "rates", "residual", "combined_uncertainty", "verdict", "bookkeeping", "caveats")
REFUSAL_FIELDS = ("run_id", "computation", "code_sha256", "capability", "bundle",
                  "runtime", "generated_utc", "data", "bound_parameters", "refused",
                  "reason_code", "reason")
SERIES = ("gravimetry", "altimetry", "volume", "firn")
REL_TOL = 1e-9
ROUNDING = 5.0e-5
CONFIDENCE = 0.95
MIN_DOF = 1.0
CLIM_MIN_YEARS = 2
Z95 = 1.959963984540054
TRUTH_BAND = {"gravimetry": 15.0, "altimetry": 20.0, "residual_floor": 5.0}
LAG_MONTHS = 12
PLAUSIBLE_GT_YR = {"greenland": (-600.0, 100.0), "antarctica": (-400.0, 200.0)}
PLAUSIBLE_VOLUME_KM3_YR = (-1000.0, 500.0)
PLAUSIBLE_FLOOR_M = (0.01, 1.0)


def load(path: Path):
    spec = importlib.util.spec_from_file_location("ice_sheet_balance", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def sha256_file(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def ym(d: str) -> int:
    return int(d[:4]) * 12 + int(d[5:7]) - 1


def label(k: int) -> str:
    return f"{k // 12:04d}-{k % 12 + 1:02d}"


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


def lag_differences(epochs, values, unc):
    """The annual-lag differences of a series, keyed by epoch, with
    their uncertainties in quadrature."""
    by = {m: (v, u) for m, v, u in zip(epochs, values, unc)}
    out = {}
    for m in epochs:
        prev = label(ym(m) - LAG_MONTHS)
        if prev in by:
            out[m] = (by[m][0] - by[prev][0], math.sqrt(by[m][1] ** 2 + by[prev][1] ** 2))
    return out


def mean_recompute(epochs, d, du, step):
    """Written from the method statement: the mean of the differences;
    the lag-1 autocorrelation over differences one step apart; n_eff
    the AR(1) estimate floored at the number of non-overlapping years;
    Student's t on n_eff minus 1; the larger of the sampling and the
    formal error of the mean."""
    n = len(d)
    per_year = LAG_MONTHS // step
    out = {"n": n, "interval": False}
    if n < max(2, per_year):
        return out
    mean = sum(d) / n
    formal_se = math.sqrt(sum(u * u for u in du)) / n
    out.update({"rate": mean, "formal_se": formal_se, "formal_95": Z95 * formal_se})
    ss = sum((x - mean) ** 2 for x in d)
    sd = math.sqrt(ss / (n - 1))
    pairs = [(i, i + 1) for i in range(n - 1) if ym(epochs[i + 1]) - ym(epochs[i]) == step]
    r1 = (sum((d[i] - mean) * (d[j] - mean) for i, j in pairs) / ss) if ss > 0 and pairs else 0.0
    n_ar1 = min(float(n), n * (1.0 - r1) / (1.0 + r1)) if r1 < 1.0 else 1.0
    n_years = n / per_year
    n_eff = max(n_ar1, n_years)
    dof = n_eff - 1.0
    sampling_se = sd / math.sqrt(n_eff)
    out.update({"sd": sd, "r1": r1, "n_eff_ar1": n_ar1, "n_years": n_years, "n_eff": n_eff, "dof": dof,
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


def check_rate_block(block, epochs, values, unc, step, is_difference_series=False):
    """None when the block recomputes, else why not. A term block is
    formed from the series' annual-lag differences; the residual block
    from a series that already is one."""
    if not isinstance(block, dict):
        return "missing or not an object"
    if block.get("confidence") != CONFIDENCE or block.get("step_months") != step or block.get("lag_months") != LAG_MONTHS:
        return f"confidence {block.get('confidence')}, step {block.get('step_months')} ({step}) or lag {block.get('lag_months')}"
    if is_difference_series:
        d_epochs, d, du = list(epochs), list(values), list(unc)
    else:
        diffs = lag_differences(epochs, values, unc)
        d_epochs = list(diffs)
        d, du = [diffs[m][0] for m in d_epochs], [diffs[m][1] for m in d_epochs]
        if block.get("n_epochs") != len(epochs):
            return f"n_epochs {block.get('n_epochs')} (series has {len(epochs)})"
    if block.get("difference_epochs") != d_epochs or block.get("n_differences") != len(d_epochs):
        return "difference epochs disagree with the series"
    c = mean_recompute(d_epochs, d, du, step)
    if "rate" not in c:
        return None if block.get("stated") is False and block.get("reason") else "block states a rate the recompute cannot form"
    for k in ("rate", "formal_se", "formal_95", "sd", "r1", "n_eff_ar1", "n_years", "n_eff", "dof", "sampling_se"):
        v = block.get(k)
        if k not in c:
            continue
        if not isinstance(v, (int, float)) or not close(v, c[k]):
            return f"{k} {v} does not recompute ({c.get(k)})"
    if block.get("stated") is False:
        if c["interval"]:
            return "block refuses an interval the recompute states"
        return None if isinstance(block.get("reason"), str) and block["reason"] else "refused interval carries no reason"
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


def systematic_value(book: dict, ice_sheet: str) -> float:
    sens = ((book.get("mass") or {}).get("selection_sensitivity") or {}).get(ice_sheet)
    trends = [v.get("trend_gt_per_yr_full_series") for v in (sens or {}).values()
              if isinstance(v, dict) and isinstance(v.get("trend_gt_per_yr_full_series"), (int, float))]
    return 0.5 * (max(trends) - min(trends)) if len(trends) >= 2 else 0.0


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
    check("code", r.get("code_sha256") == sanctioned, f"receipt {r.get('code_sha256')} vs sanctioned {sanctioned}")

    identity = mod.package_identity(mod.package_root(computation.parent))
    bundle = r.get("bundle") or {}
    cap = r.get("capability") or {}
    cap_ok = (isinstance(cap, dict) and isinstance(cap.get("name"), str) and cap["name"]
              and isinstance(cap.get("version"), str) and cap["version"] and "release_lock" in cap
              and (cap["release_lock"] is None or re.fullmatch(r"sha256:[0-9a-f]{64}", str(cap["release_lock"]))))
    check("release", bundle == identity and bool(identity.get("name")) and cap_ok,
          f"bundle {bundle} vs this tree {identity}; capability {cap} {'well formed' if cap_ok else 'malformed'}")
    rt = r.get("runtime") or {}
    check("runtime", isinstance(rt, dict) and isinstance(rt.get("name"), str) and bool(rt.get("name")),
          f"runtime {rt.get('name')!r} {rt.get('version') or ''}".strip())

    data = r.get("data") or {}
    bound = r.get("bound_parameters") or {}
    window = str(bound.get("window", ""))
    m = re.fullmatch(r"(\d{4}-\d{2}):(\d{4}-\d{2})", window)
    start, end = (m.group(1), m.group(2)) if m else (None, None)
    ice_sheet, altimetry = bound.get("ice_sheet"), bound.get("altimetry")
    density = bound.get("ice_density")
    fx = None
    if data.get("mode") == "fixture":
        seed = data.get("seed")
        ok = isinstance(seed, int)
        if ok:
            fx = mod.make_fixture(seed)
            digest = mod.fixture_digest(fx)
            ok = (data.get("digest") == digest and data.get("generator_sha256") == sanctioned
                  and data.get("spans", {}).get("mass") == list(mod.FIXTURE_SPANS["mass"]))
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
              and isinstance(files, dict) and {"mass.csv", "firn.csv"} <= set(files)
              and any(k.startswith("volume-") for k in files)
              and isinstance(data.get("data_root"), str) and data["data_root"])
        detail = f"data root {data.get('data_root')} stamped {rec.get('record') if isinstance(rec, dict) else None}"
        if ok and data_root is not None:
            root = Path(data_root).expanduser().resolve()
            problems = []
            manifest = {}
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
            if fx is not None:
                terms, again = mod.assemble(ice_sheet, altimetry, fx["rows"], float(density or 917.0))
                if again is None:
                    _, again = mod.compute(terms, start, end, bound.get("bridge"), mod.FIXTURE_BOOKKEEPING, ice_sheet)
                reproduced = again is not None and again[0] == code
                why = f"the executor's assembly and compute on the regenerated fixture refuse with {again and again[0]!r}: {reproduced}"
            elif data_root is not None and (Path(data_root) / "RECORD.json").is_file():
                try:
                    tree = mod.read_data_root(Path(data_root))
                    terms, again = mod.assemble(ice_sheet, altimetry, tree["rows"], float(density or 917.0))
                    if again is None:
                        _, again = mod.compute(terms, start, end, bound.get("bridge"), tree["bookkeeping"], ice_sheet)
                    reproduced = again is not None and again[0] == code
                    why = f"the executor's assembly and compute on the tree refuse with {again and again[0]!r}: {reproduced}"
                except SystemExit as e:
                    why = f"the tree cannot be read: {e}"
            else:
                spans = (data.get("spans") or {}).get("terms") or {}
                domains = data.get("domains") or {}
                if code == "window-outside-overlap":
                    inside = all(isinstance(spans.get(k), list) and ym(spans[k][0]) <= ym(start) and ym(end) <= ym(spans[k][1])
                                 for k in ("gravimetry", "altimetry"))
                    reproduced = not inside
                    why = f"the window {window} against the recorded spans {spans}: outside {reproduced}"
                elif code == "firn-term-missing":
                    need = {f"{ice_sheet}/{d}" for d in mod.FIRN_DOMAINS[ice_sheet]}
                    reproduced = not need <= set(domains.get("firn") or [])
                    why = f"the firn domains {sorted(need)} against the root's {domains.get('firn')}: missing {reproduced}"
                elif code == "term-not-in-root":
                    key = f"volume-{altimetry}"
                    need = {f"{ice_sheet}/{d}" for d in mod.ALTIMETRY_DOMAINS.get(altimetry, {}).get(ice_sheet, ())}
                    reproduced = key not in domains or not need <= set(domains.get(key) or []) \
                        or f"{ice_sheet}/{mod.MASS_DOMAIN}" not in (domains.get("mass") or [])
                    why = f"the {key} and mass domains against the root's {domains}: missing {reproduced}"
                elif code == "gap-without-bridge":
                    reproduced = ym(start) < ym(mod.GAP[0]) and ym(end) > ym(mod.GAP[1]) and not bound.get("bridge")
                    why = f"the window {window} spans the gap {mod.GAP} with no bridge bound: {reproduced}"
                else:
                    reproduced, why = True, "a data-root refusal of this kind is taken on the executor's word"
        check("refusal", recognized and reproduced, f"reason_code {code!r} {'recognized' if recognized else 'unknown'}; {why}")
        verdict = "PASS" if all(c["ok"] for c in checks) else "FAIL"
        return verdict, True, checks, r

    # series
    s = r.get("series") or {}
    w = r.get("window") or {}
    n_cal = ym(end) - ym(start) + 1 if start else 0
    series_ok = (bool(start) and w.get("start") == start and w.get("end") == end
                 and w.get("n_calendar") == n_cal and isinstance(w.get("years"), (int, float))
                 and close(w["years"], n_cal / 12.0) and isinstance(density, (int, float)) and density > 0)
    detail = "window well formed" if series_ok else "window or density malformed"
    for name in SERIES:
        t = s.get(name) or {}
        ep = t.get("epochs")
        ok = (isinstance(ep, list) and len(ep) >= 3 and all(isinstance(x, str) and re.fullmatch(r"\d{4}-\d{2}", x) for x in ep)
              and ep == sorted(ep) and len(set(ep)) == len(ep)
              and all(ym(start) <= ym(x) <= ym(end) for x in ep)
              and numbers(t.get("values"), len(ep)) and numbers(t.get("uncertainties"), len(ep)))
        series_ok = series_ok and ok
    rs_ = s.get("residual") or {}
    series_ok = series_ok and (isinstance(rs_.get("epochs"), list) and len(rs_["epochs"]) >= 2
                               and numbers(rs_.get("values"), len(rs_["epochs"]))
                               and numbers(rs_.get("uncertainties"), len(rs_["epochs"]))
                               and numbers(rs_.get("altimetry_differences"), len(rs_["epochs"]))
                               and numbers(rs_.get("gravimetry_differences"), len(rs_["epochs"])))
    if series_ok:
        rho = density / 1000.0
        vol, firn, alt = s["volume"], s["firn"], s["altimetry"]
        same = vol["epochs"] == firn["epochs"] == alt["epochs"]
        dev = 0.0
        if same:
            for i in range(len(alt["epochs"])):
                want = rho * (vol["values"][i] - firn["values"][i])
                want_u = rho * math.sqrt(vol["uncertainties"][i] ** 2 + firn["uncertainties"][i] ** 2)
                dev = max(dev, abs(want - alt["values"][i]), abs(want_u - alt["uncertainties"][i]))
        floored = (numbers(firn.get("uncertainties_stated"), len(firn["epochs"]))
                   and all(u >= st and u > 0 for u, st in zip(firn["uncertainties"], firn["uncertainties_stated"])))
        # the residual series: the difference of the two terms' annual-lag differences on their common epochs
        da = lag_differences(alt["epochs"], alt["values"], alt["uncertainties"])
        dg = lag_differences(s["gravimetry"]["epochs"], s["gravimetry"]["values"], s["gravimetry"]["uncertainties"])
        common = sorted(set(da) & set(dg))
        rdev = 0.0
        resid_ok = rs_["epochs"] == common
        if resid_ok:
            for i, m in enumerate(common):
                rdev = max(rdev, abs(da[m][0] - rs_["altimetry_differences"][i]), abs(dg[m][0] - rs_["gravimetry_differences"][i]),
                           abs((da[m][0] - dg[m][0]) - rs_["values"][i]),
                           abs(math.sqrt(da[m][1] ** 2 + dg[m][1] ** 2) - rs_["uncertainties"][i]))
            resid_ok = rdev <= REL_TOL * 1e3
        series_ok = same and dev <= REL_TOL * 1e3 and floored and resid_ok
        detail = (f"altimetric mass is density times (volume minus firn air) at every epoch (max deviation {dev:.2e}); "
                  f"firn uncertainties floored above the stated ones: {floored}; the residual series is the difference "
                  f"of the annual-lag differences on {len(common)} common epochs (max deviation {rdev:.2e}): {resid_ok}")
    if series_ok and fx is not None:
        terms, again = mod.assemble(ice_sheet, altimetry, fx["rows"], float(density))
        maxdev, agree = 0.0, again is None
        if agree:
            for name in SERIES:
                u = mod.window_terms(terms[name], start, end)
                agree = agree and u["epochs"] == s[name]["epochs"]
                if agree:
                    for k in ("values", "uncertainties"):
                        maxdev = max(maxdev, max(abs(a - b) for a, b in zip(u[k], s[name][k])))
        series_ok = agree and maxdev <= 1e-9
        detail += f"; the regenerated fixture yields the same epochs and values (max deviation {maxdev:.2e}): {series_ok}"
    if series_ok and fx is None and data_root is not None and (Path(data_root) / "RECORD.json").is_file():
        maxdev, agree = 0.0, True
        try:
            tree = mod.read_data_root(Path(data_root))
            terms, again = mod.assemble(ice_sheet, altimetry, tree["rows"], float(density))
            agree = again is None
            if agree:
                for name in SERIES:
                    u = mod.window_terms(terms[name], start, end)
                    agree = agree and u["epochs"] == s[name]["epochs"]
                    if agree:
                        for k in ("values", "uncertainties"):
                            maxdev = max(maxdev, max(abs(a - b) for a, b in zip(u[k], s[name][k])))
        except SystemExit as e:
            agree, detail = False, detail + f"; the tree cannot be read: {e}"
        series_ok = agree and maxdev <= 1e-9
        detail += f"; the tree's term files rebuild the same epochs and values (max deviation {maxdev:.2e}): {series_ok}"
    check("series", series_ok, detail)

    # recompute
    rec_ok, rec_detail = False, "series not checkable"
    terms = r.get("terms") or {}
    if series_ok:
        rates = r.get("rates") or {}
        problems = []
        step_alt = int((terms.get("altimetry") or {}).get("step_months") or 1)
        for name in SERIES:
            t_ = s[name]
            step = 1 if name == "gravimetry" else step_alt
            err = check_rate_block(rates.get(name), t_["epochs"], t_["values"], t_["uncertainties"], step)
            if err:
                problems.append(f"rates.{name}: {err}")
        rs_ = s["residual"]
        err = check_rate_block(rates.get("residual"), rs_["epochs"], rs_["values"], rs_["uncertainties"], step_alt, True)
        if err:
            problems.append(f"rates.residual: {err}")
        if not problems:
            for name in ("gravimetry", "altimetry", "residual"):
                if rates[name].get("stated") is not True:
                    problems.append(f"rates.{name} carries no interval; the run should have refused")
        if not problems:
            years = n_cal / 12.0
            for name, key in (("gravimetry", "rate_gt_per_yr"), ("altimetry", "rate_gt_per_yr"),
                              ("volume", "rate_km3_per_yr"), ("firn", "rate_km3_per_yr")):
                v = (terms.get(name) or {}).get(key)
                want = rates[name].get("rate")
                if want is None:
                    if v is not None:
                        problems.append(f"terms.{name}.{key} {v} where the block has no rate")
                elif not isinstance(v, (int, float)) or abs(v - want) > ROUNDING + 1e-9:
                    problems.append(f"terms.{name}.{key} {v} is not the block's rate rounded")
                if name in ("gravimetry", "altimetry"):
                    ch = (terms.get(name) or {}).get("change_over_window_gt")
                    if not isinstance(ch, (int, float)) or not close(ch, rates[name]["rate"] * years):
                        problems.append(f"terms.{name}.change_over_window_gt {ch} does not recompute")
                    tu = (terms.get(name) or {}).get("uncertainty_gt_per_yr")
                    if not isinstance(tu, (int, float)) or not close(tu, rates[name]["half_width"]):
                        problems.append(f"terms.{name}.uncertainty_gt_per_yr {tu} is not the block's half width")
            residual = rates["residual"]["rate"]
            n_common = len(rs_["epochs"])
            sysv = systematic_value(r.get("bookkeeping") or {}, ice_sheet)
            bar = rates["residual"]["half_width"] + sysv
            cu = r.get("combined_uncertainty") or {}
            stated = cu.get("terms_gt_per_yr") or {}
            for n_ in ("gravimetry", "altimetry"):
                if not isinstance(stated.get(n_), (int, float)) or not close(stated[n_], rates[n_]["half_width"]):
                    problems.append(f"combined_uncertainty.terms_gt_per_yr.{n_} {stated.get(n_)} is not the block's half width")
            for k, want in (("residual_half_width_gt_per_yr", rates["residual"]["half_width"]), ("bar_gt_per_yr", bar)):
                v = cu.get(k)
                if not isinstance(v, (int, float)) or not close(v, want):
                    problems.append(f"combined_uncertainty.{k} {v} does not recompute ({want})")
            sv = (cu.get("selection_systematic") or {}).get("value_gt_per_yr")
            if not isinstance(sv, (int, float)) or not close(sv, sysv):
                problems.append(f"selection_systematic {sv} does not recompute from the bookkeeping ({sysv})")
            rs = r.get("residual") or {}
            vd = r.get("verdict") or {}
            closed = abs(residual) <= bar
            mean_alt = sum(rs_["altimetry_differences"]) / n_common
            mean_grav = sum(rs_["gravimetry_differences"]) / n_common
            if (not isinstance(rs.get("rate_gt_per_yr"), (int, float)) or not close(rs["rate_gt_per_yr"], residual)
                    or rs.get("n_common_differences") != n_common
                    or not isinstance(rs.get("change_over_window_gt"), (int, float))
                    or not close(rs["change_over_window_gt"], residual * years)
                    or not isinstance(rs.get("altimetry_on_common_epochs_gt_per_yr"), (int, float))
                    or not close(rs["altimetry_on_common_epochs_gt_per_yr"], mean_alt)
                    or not isinstance(rs.get("gravimetry_on_common_epochs_gt_per_yr"), (int, float))
                    or not close(rs["gravimetry_on_common_epochs_gt_per_yr"], mean_grav)):
                problems.append(f"residual block {rs.get('rate_gt_per_yr')} does not recompute ({residual} on {n_common} epochs)")
            if (not isinstance(vd.get("residual_gt_per_yr"), (int, float)) or not close(vd["residual_gt_per_yr"], residual)
                    or not isinstance(vd.get("bar_gt_per_yr"), (int, float)) or not close(vd["bar_gt_per_yr"], bar)
                    or vd.get("closed_within_uncertainty") is not closed):
                problems.append(f"verdict {vd.get('closed_within_uncertainty')} residual {vd.get('residual_gt_per_yr')} "
                                f"bar {vd.get('bar_gt_per_yr')} does not recompute (closed {closed}, residual {residual}, bar {bar})")
        rec_ok = not problems
        rec_detail = ("; ".join(problems) if problems else
                      "four term rates and the residual with intervals and formal errors, the systematic, the bar, "
                      "the residual block and the verdict recompute")
    check("recompute", rec_ok, rec_detail)

    # bookkeeping
    book = r.get("bookkeeping") or {}
    lacking = [f"{sec}.{key}" for sec, key in mod.REQUIRED_BOOKKEEPING
               if not (isinstance(book.get(sec), dict) and book[sec].get(key) not in (None, "", {}))]
    dens = book.get("density") if isinstance(book.get("density"), dict) else {}
    floor = book.get("firn_floor") if isinstance(book.get("firn_floor"), dict) else {}
    gh = book.get("gap_handling") if isinstance(book.get("gap_handling"), dict) else {}
    used_mass = (s.get("gravimetry") or {}).get("epochs") or []
    calendar = [label(k) for k in range(ym(start), ym(end) + 1)] if start else []
    crosses = bool(used_mass) and ym(used_mass[0]) < ym(mod.GAP[0]) and ym(used_mass[-1]) > ym(mod.GAP[1])
    book_ok = (not lacking
               and dens.get("ice_density_kg_m3") == density and isinstance(dens.get("basis"), str) and dens["basis"]
               and isinstance(floor.get("floor_m"), dict) and floor["floor_m"]
               and floor.get("floor_m") == (terms.get("firn") or {}).get("floor_m")
               and all(isinstance(v, (int, float)) and v > 0 for v in floor["floor_m"].values())
               and isinstance(gh.get("rule"), str) and gh.get("rule")
               and gh.get("mass_months_missing") == [x for x in calendar if x not in set(used_mass)]
               and gh.get("crosses_intermission_gap") is crosses
               and gh.get("bridge") == bound.get("bridge")
               and (not crosses or (isinstance(gh.get("bridge"), str) and gh["bridge"].strip())))
    check("bookkeeping", book_ok,
          (f"lacks {lacking}; " if lacking else "every required statement present; ")
          + f"density {dens.get('ice_density_kg_m3')} kg/m3; firn floor {floor.get('floor_m')}; "
          f"{len(gh.get('mass_months_missing') or [])} mass months missing; crosses the gap {crosses}, bridge {gh.get('bridge')!r}")

    # plausibility
    if rec_ok:
        vd, tr = r["verdict"], r["rates"]
        if fx is not None:
            truth = mod.TRUTH[ice_sheet]
            g_true = truth["gravimetry_gt_yr"]
            a_true = g_true + truth["residual_gt_yr"]
            near_g = abs(tr["gravimetry"]["rate"] - g_true)
            near_a = abs(tr["altimetry"]["rate"] - a_true)
            near_r = abs(vd["residual_gt_per_yr"] - truth["residual_gt_yr"])
            band_r = max(TRUTH_BAND["residual_floor"], vd["bar_gt_per_yr"])
            ok = (vd.get("closed_within_uncertainty") is True and near_g <= TRUTH_BAND["gravimetry"]
                  and near_a <= TRUTH_BAND["altimetry"] and near_r <= band_r)
            detail = (f"known truth: gravimetry within {near_g:.3f} of {g_true} (band {TRUTH_BAND['gravimetry']}), "
                      f"altimetry within {near_a:.3f} of {a_true} (band {TRUTH_BAND['altimetry']}), residual within "
                      f"{near_r:.3f} of the planted {truth['residual_gt_yr']} (band {band_r:.3f}), verdict closed "
                      f"{vd.get('closed_within_uncertainty')}")
        else:
            lo, hi = PLAUSIBLE_GT_YR.get(ice_sheet, (-1e9, 1e9))
            rates = {n_: tr[n_]["rate"] for n_ in ("gravimetry", "altimetry")}
            floors = (terms.get("firn") or {}).get("floor_m") or {}
            ok = (all(lo <= v <= hi for v in rates.values())
                  and PLAUSIBLE_VOLUME_KM3_YR[0] <= tr["volume"].get("rate", 0.0) <= PLAUSIBLE_VOLUME_KM3_YR[1]
                  and all(PLAUSIBLE_FLOOR_M[0] <= v <= PLAUSIBLE_FLOOR_M[1] for v in floors.values())
                  and vd["bar_gt_per_yr"] > 0)
            detail = (f"{ice_sheet}: rates {rates} within [{lo}, {hi}] Gt/yr, volume rate {tr['volume'].get('rate', 0.0):.3f} km3/yr "
                      f"within {PLAUSIBLE_VOLUME_KM3_YR}, firn floors {floors} within {PLAUSIBLE_FLOOR_M} m; the verdict "
                      f"({vd.get('closed_within_uncertainty')}) stands on the recompute")
        check("plausible", ok, detail)
    else:
        check("plausible", False, "not checkable: the recompute failed")

    verdict = "PASS" if all(c["ok"] for c in checks) else "FAIL"
    return verdict, False, checks, r


def attestation_doc(verdict, refusal, checks, r, receipt_path, computation):
    return {
        "verdict": verdict, "refusal": refusal,
        "attester": "skills/ice-mass-change/scripts/ice_sheet_balance_check.py",
        "attester_sha256": sha256_file(Path(__file__).resolve()),
        "computation_sha256": sha256_file(computation),
        "receipt": receipt_path.name, "receipt_sha256": sha256_file(receipt_path),
        "run_id": r.get("run_id"),
        "capability": r.get("capability") or {}, "bundle": r.get("bundle") or {}, "runtime": r.get("runtime") or {},
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
        lines.append(f"PASS refusal ({r.get('reason_code')}) run {r.get('run_id')}: {bound.get('ice_sheet')} "
                     f"{bound.get('window')} refused, {r.get('reason')}")
    else:
        v, t = r["verdict"], r["terms"]
        lines.append(f"PASS run {r.get('run_id')}: {bound.get('ice_sheet')} {bound.get('window')} ({bound.get('altimetry')}), "
                     f"gravimetry {t['gravimetry']['rate_gt_per_yr']:+.3f} Gt/yr, altimetry {t['altimetry']['rate_gt_per_yr']:+.3f} Gt/yr, "
                     f"residual {v['residual_gt_per_yr']:+.3f} against bar {v['bar_gt_per_yr']:.3f}, closed_within_uncertainty "
                     f"{str(v['closed_within_uncertainty']).lower()} (recomputed)")
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
        gl = ["--fixture", "--seed", "7", "--ice-sheet", "greenland"]
        ref = w / "ref.json"
        assert run([*gl, "--window", "2019-01:2022-12", "--altimetry", "atl15"], ref) == 0
        assert verdict_of(ref) == ("PASS", False, []), verdict_of(ref)
        long = w / "long.json"
        assert run([*gl, "--window", "2003-01:2016-12", "--altimetry", "itslive"], long) == 0
        v, refusal, checks, doc = attest(long, computation)
        assert v == "PASS" and doc["verdict"]["closed_within_uncertainty"] is True, checks
        assert abs(doc["verdict"]["residual_gt_per_yr"] - mod.TRUTH["greenland"]["residual_gt_yr"]) < 10.0, doc["verdict"]

        # tampers, each failing on its check
        t1 = tampered(long, w / "t1.json", lambda r: r["series"]["gravimetry"]["values"].__setitem__(3, r["series"]["gravimetry"]["values"][3] + 1e-6))
        assert first_fail(t1) == "series", verdict_of(t1)
        t2 = tampered(long, w / "t2.json", lambda r: r["rates"]["gravimetry"].__setitem__("rate", r["rates"]["gravimetry"]["rate"] * 1.001))
        assert first_fail(t2) == "recompute", verdict_of(t2)
        t3 = tampered(long, w / "t3.json", lambda r: r["verdict"].__setitem__("closed_within_uncertainty", False))
        assert first_fail(t3) == "recompute", verdict_of(t3)
        t4 = tampered(long, w / "t4.json", lambda r: r["rates"]["residual"].__setitem__("half_width", r["rates"]["residual"]["half_width"] / 2))
        t4b = tampered(long, w / "t4b.json", lambda r: r["series"]["residual"]["values"].__setitem__(0, r["series"]["residual"]["values"][0] + 1.0))
        assert first_fail(t4b) == "series", verdict_of(t4b)
        assert first_fail(t4) == "recompute", verdict_of(t4)
        t5 = tampered(long, w / "t5.json", lambda r: r["bookkeeping"]["mass"].pop("gia"))
        assert verdict_of(t5)[2] == ["bookkeeping"], verdict_of(t5)
        t6 = tampered(long, w / "t6.json", lambda r: r["runtime"].__setitem__("name", ""))
        assert verdict_of(t6)[2] == ["runtime"], verdict_of(t6)
        t7 = tampered(long, w / "t7.json", lambda r: r["data"].__setitem__("seed", 8))
        assert first_fail(t7) == "data", verdict_of(t7)
        t8 = tampered(long, w / "t8.json", lambda r: r["series"]["firn"]["uncertainties"].__setitem__(0, 0.0))
        assert first_fail(t8) == "series", verdict_of(t8)
        t9 = tampered(long, w / "t9.json", lambda r: r["combined_uncertainty"]["selection_systematic"].__setitem__("value_gt_per_yr", 50.0))
        assert first_fail(t9) == "recompute", verdict_of(t9)
        w1 = tampered(long, w / "w1.json", lambda r: r["bundle"].__setitem__("version", "0.0.0"))
        assert verdict_of(w1)[2] == ["release"], verdict_of(w1)
        w2 = tampered(long, w / "w2.json", lambda r: r["capability"].__setitem__("name", ""))
        assert verdict_of(w2)[2] == ["release"], verdict_of(w2)

        # a tampered computation fails code and the generator digest
        bad = w / "ice_sheet_balance.py"
        bad.write_bytes(computation.read_bytes() + b"\n")
        v, _, failed = verdict_of(long, bad)
        assert v == "FAIL" and "code" in failed and "data" in failed, failed

        # refusals attest PASS as refusals, exit 3 from the executor
        rf = w / "outside.json"
        assert run([*gl, "--window", "2019-01:2025-12", "--altimetry", "atl15"], rf) == 3
        v, refusal, checks, doc = attest(rf, computation)
        assert (v, refusal) == ("PASS", True) and doc["reason_code"] == "window-outside-overlap", checks
        assert "PASS refusal" in report(v, refusal, checks, doc)
        ant = w / "antarctica.json"
        assert run(["--fixture", "--seed", "7", "--ice-sheet", "antarctica", "--window", "2003-01:2016-12"], ant) == 3
        v, refusal, checks, doc = attest(ant, computation)
        assert (v, refusal) == ("PASS", True) and doc["reason_code"] == "firn-term-missing", checks
        gap = w / "gap.json"
        assert run([*gl, "--window", "2010-01:2022-12"], gap) == 3
        v, refusal, checks, doc = attest(gap, computation)
        assert (v, refusal) == ("PASS", True) and doc["reason_code"] == "gap-without-bridge", checks
        short = w / "short.json"
        assert run([*gl, "--window", "2019-01:2019-12"], short) == 3
        assert verdict_of(short) == ("PASS", True, []), verdict_of(short)
        forged = tampered(rf, w / "forged.json", lambda r: r["bound_parameters"].__setitem__("window", "2019-01:2022-12"))
        assert verdict_of(forged)[2] == ["refusal"], verdict_of(forged)
        # across the gap with a bridge it computes; with the bridge stripped it fails bookkeeping
        br = w / "bridged.json"
        assert run([*gl, "--window", "2010-01:2022-12", "--bridge", "selftest: a continuity citation"], br) == 0
        assert verdict_of(br) == ("PASS", False, []), verdict_of(br)
        nb = tampered(br, w / "nobridge.json", lambda r: (r["bookkeeping"]["gap_handling"].__setitem__("bridge", None),
                                                          r["bound_parameters"].__setitem__("bridge", None)))
        assert verdict_of(nb)[2] == ["bookkeeping"], verdict_of(nb)

        # the data-root path on the fixture written as a root: the receipt
        # attests, the tree verifies against it, and a changed file fails data
        root = w / "root"
        mod.write_fixture_root(mod.make_fixture(7), root)
        dr = w / "dataroot.json"
        assert run(["--data-root", str(root), "--ice-sheet", "greenland", "--window", "2003-01:2016-12"], dr) == 0
        assert verdict_of(dr) == ("PASS", False, []), verdict_of(dr)
        assert verdict_of(dr, None, root) == ("PASS", False, []), verdict_of(dr, None, root)
        # the tree rebuild: a receipt whose series were tampered after the run
        # fails series against the tree it names
        t10 = tampered(dr, w / "t10.json", lambda r: r["series"]["volume"]["values"].__setitem__(2, r["series"]["volume"]["values"][2] + 1e-6))
        assert first_fail(t10, None, root) == "series", verdict_of(t10, None, root)
        doc = json.loads(dr.read_text())
        assert doc["data"]["data_root"] == root.resolve().as_posix() or not doc["data"]["data_root"].startswith("/"), doc["data"]
        # a value altered in a term file with RECORD.json untouched: the executor
        # refuses the drifted tree, and the earlier receipt fails data against it
        lines = (root / "mass.csv").read_text(encoding="utf-8").splitlines()
        cells = lines[5].split(",")
        cells[3] = f"{float(cells[3]) + 50.0:.6f}"
        lines[5] = ",".join(cells)
        (root / "mass.csv").write_text("\n".join(lines) + "\n", encoding="utf-8")
        try:
            run(["--data-root", str(root), "--ice-sheet", "greenland", "--window", "2003-01:2016-12"], w / "drifted.json")
            raise AssertionError("the executor computed on a tree that drifted from its stamp")
        except SystemExit as e:
            assert "manifest" in str(e), e
        assert first_fail(dr, None, root) == "data", verdict_of(dr, None, root)
        # the manifest rewritten to the altered file: the executor runs, the receipt
        # attests on its own and against that tree, and against the committed
        # tree it fails data
        rec = json.loads((root / "RECORD.json").read_text(encoding="utf-8"))
        rec["manifest"]["mass.csv"] = sha256_file(root / "mass.csv")
        (root / "RECORD.json").write_text(json.dumps(rec, indent=2) + "\n", encoding="utf-8")
        dr2 = w / "dataroot2.json"
        assert run(["--data-root", str(root), "--ice-sheet", "greenland", "--window", "2003-01:2016-12"], dr2) == 0
        assert verdict_of(dr2) == ("PASS", False, []), verdict_of(dr2)
        assert verdict_of(dr2, None, root) == ("PASS", False, []), verdict_of(dr2, None, root)
        good = w / "root-good"
        mod.write_fixture_root(mod.make_fixture(7), good)
        assert first_fail(dr2, None, good) == "data", verdict_of(dr2, None, good)
        # term-not-in-root: the ATL15 term removed from a root, reproduced from the tree
        noatl = w / "root-noatl"
        mod.write_fixture_root(mod.make_fixture(7), noatl)
        (noatl / "volume-atl15.csv").unlink()
        rec = json.loads((noatl / "RECORD.json").read_text(encoding="utf-8"))
        rec["terms_present"] = [x for x in rec["terms_present"] if x != "volume-atl15"]
        rec["manifest"].pop("volume-atl15.csv")
        (noatl / "RECORD.json").write_text(json.dumps(rec, indent=2) + "\n", encoding="utf-8")
        tnr = w / "term-not-in-root.json"
        assert run(["--data-root", str(noatl), "--ice-sheet", "greenland", "--window", "2019-01:2022-12", "--altimetry", "atl15"], tnr) == 3
        assert json.loads(tnr.read_text())["reason_code"] == "term-not-in-root"
        assert verdict_of(tnr) == ("PASS", True, []), verdict_of(tnr)
        assert verdict_of(tnr, None, noatl) == ("PASS", True, []), verdict_of(tnr, None, noatl)
        # interval-not-stated: a short quarterly window whose residual scatter vanishes
        ins = w / "interval-not-stated.json"
        assert run(["--fixture", "--seed", "36", "--ice-sheet", "greenland", "--window", "2020-01:2021-12", "--altimetry", "atl15"], ins) == 3
        assert json.loads(ins.read_text())["reason_code"] == "interval-not-stated", json.loads(ins.read_text())["reason"]
        assert verdict_of(ins) == ("PASS", True, []), verdict_of(ins)
        # the same root refuses the ATL15 term for Antarctica and reproduces it from the recorded domains
        drf = w / "dataroot-refusal.json"
        assert run(["--data-root", str(root), "--ice-sheet", "antarctica", "--window", "2003-01:2016-12", "--altimetry", "itslive"], drf) == 3
        assert verdict_of(drf) == ("PASS", True, []), verdict_of(drf)

        # the attestation document carries the verdict and the identity blocks
        adoc = attestation_doc(*attest(ref, computation), ref, computation)
        assert adoc["verdict"] == "PASS" and adoc["capability"]["name"] and adoc["runtime"]["name"] == "selftest"
        assert {c["name"] for c in adoc["checks"]} == {"fields", "code", "release", "runtime", "data",
                                                        "series", "recompute", "bookkeeping", "plausible"}
    print("ice_sheet_balance_check selftest: ok")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("receipt", nargs="?", type=Path)
    ap.add_argument("--computation", type=Path, default=DEFAULT_COMPUTATION)
    ap.add_argument("--data-root", type=Path, default=None, help="verify the receipt's digests against this tree")
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
        args.out.write_text(json.dumps(attestation_doc(verdict, refusal, checks, r, args.receipt, computation),
                                       indent=2) + "\n", encoding="utf-8")
    print(report(verdict, refusal, checks, r) + (f"; attestation {args.out}" if args.out else ""))
    return 0 if verdict == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
