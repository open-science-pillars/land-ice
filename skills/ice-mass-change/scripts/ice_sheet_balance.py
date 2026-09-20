#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Sanctioned computation for the attested ice sheet mass balance
closure, in the sea level budget's shape.

Contract: knowledge/computations/ice-sheet-balance.md. Over one stated
window and for one ice sheet, two independent rates of mass change in
gigatonnes per year and their residual:

  gravimetry  the JPL GRACE and GRACE-FO mascon sum over the ice
              sheet's land mascons (the data root's mass.csv, monthly,
              the per-mascon formal uncertainty), with the GIA model,
              the low-degree series, the reference frame and the
              smoothing stated as the product applied them;
  altimetry   the altimetric volume anomaly (ITS_LIVE elevation change,
              monthly, or ICESat-2 ATL15, quarterly; the root's
              volume-itslive.csv or volume-atl15.csv) less the firn air
              content volume anomaly at the same epochs (the root's
              firn.csv, the firn data root of the earlier seed), times
              a stated ice density (917 kg per m3 by default, the
              declared parameter ice_density), so that a surface height
              change becomes a mass change only after the firn is
              removed (the bundle's gotcha).

Each rate is the mean of the term's annual-lag differences (the value
at an epoch less the value twelve months earlier, so the seasonal
cycle cancels) over the window; its interval takes the effective
sample size from the lag-1 autocorrelation of the differences, floored
at the number of non-overlapping years, Student's t on the effective
degrees of freedom, and the larger of the sampling error and the
formal error the per-epoch uncertainties propagate. The residual is
the mean of altimetry minus gravimetry differences on their common
epochs, so the interannual signal both methods see cancels before its
scatter is measured; the bar is the residual's own half width plus the
stated mascon selection systematic; the verdict is
closed_within_uncertainty. The firn air content uncertainty is a
model spread that crosses zero, so it is floored at its series median
per domain and the receipt says so.

Two input modes. --data-root DIR reads the term CSVs and RECORD.json
the loaders beside this file wrote (never a product file); the layout
is documented in the concept's data root section and the committed
root is knowledge/references/retrieval/ice-sheet-balance-root.
--fixture [--seed N] generates a synthetic root deterministically (a
hash-based Gaussian stream, stdlib only): a Greenland-like sheet with
a planted residual of +5 Gt per year between the two methods, the
mascon months the real record lacks removed, an Antarctic-like sheet
with mass and volume but no grounded firn term, both altimetry
products, and firn uncertainties that cross zero.

Refusals, exit 3 with a refusal receipt and never a number: a window
outside the overlap of the terms the run needs
(window-outside-overlap); a window shorter than two years or a term
with too few epochs in it (too-few-epochs); an ice sheet whose firn
term does not cover the altimetry domain (firn-term-missing, the
Antarctic case from this root); an altimetry product the root does
not carry (term-not-in-root); a window whose mass months lie on both
sides of the GRACE to GRACE-FO gap with no --bridge (gap-without-
bridge); a term whose interval cannot be stated (interval-not-stated).

Consumers bind values for the declared parameters and MUST NOT edit
this file; the attester hashes it, regenerates the fixture at the
receipt's seed, and recomputes every rate, interval, the residual, the
bar and the verdict from the series in the receipt.

  ice_sheet_balance.py --ice-sheet greenland|antarctica --window YYYY-MM:YYYY-MM
      --runtime NAME (--fixture [--seed N] | --data-root DIR)
      [--altimetry itslive|atl15] [--ice-density KG_M3] [--bridge TEXT]
      [--runtime-version V] [--receipt PATH] [--capability-root DIR]
"""

import argparse
import csv
import datetime as dt
import hashlib
import json
import math
import re
import statistics
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
COMPUTATION = "skills/ice-mass-change/scripts/ice_sheet_balance.py"
DEFAULT_ROOT = "knowledge/references/retrieval/ice-sheet-balance-root"

ICE_DENSITY_DEFAULT = 917.0           # kg per m3, the density the GEMB product itself applies
GAP = ("2017-07", "2018-05")          # no mascon solution: the inter-mission gap
BATTERY_MONTHS = ("2011-01", "2011-06", "2012-05", "2012-10", "2013-03",
                  "2013-08", "2013-09", "2014-02", "2014-07", "2014-12",
                  "2015-06", "2015-10", "2015-11", "2016-04", "2016-09",
                  "2016-10", "2017-02", "2018-08", "2018-09")
MIN_WINDOW_MONTHS = 24
MIN_EPOCHS = {"gravimetry": 18, "altimetry": 8}
CONFIDENCE = 0.95
MIN_DOF = 1.0
CLIM_MIN_YEARS = 2
Z95 = 1.959963984540054
STEP = {"monthly": 1, "quarterly": 3}
ALTIMETRY_DOMAINS = {
    "itslive": {"greenland": ("ice_sheet", "peripheral_glaciers"), "antarctica": ("grounded",)},
    "atl15": {"greenland": ("gl",), "antarctica": ("a1_a4",)},
}
FIRN_DOMAINS = {"greenland": ("ice_sheet", "peripheral_glaciers"), "antarctica": ("grounded",)}
MASS_DOMAIN = "land_mascons"
REASONS = ("window-outside-overlap", "too-few-epochs", "firn-term-missing", "term-not-in-root",
           "gap-without-bridge", "interval-not-stated")

FIXTURE_SPANS = {"mass": ("2003-01", "2025-12"), "firn": ("1992-01", "2023-12"),
                 "volume-itslive": ("1992-01", "2023-12"), "volume-atl15": ("2019-01", "2025-10")}
TRUTH = {
    "greenland": {
        "gravimetry_gt_yr": -250.0, "residual_gt_yr": 5.0,
        "annual_amplitude_mass_gt": 120.0, "annual_peak_mass_month": 4,
        "interannual_ar1": {"phi": 0.8, "sigma_gt": 15.0},
        "noise_sigma_mass_gt": "20 to 30, an annual pattern",
        "firn_air_km3_yr": -6.0, "annual_amplitude_firn_km3": 45.0, "annual_peak_firn_month": 3,
        "noise_sigma_firn_km3": 4.0, "firn_uncertainty_m": "|N(0.08, 0.06)|, crossing zero",
        "area_km2": {"ice_sheet": 1733000.0, "peripheral_glaciers": 89400.0},
        "volume_split": {"ice_sheet": 0.95, "peripheral_glaciers": 0.05},
        "noise_sigma_volume_km3": 8.0, "volume_uncertainty_km3": [8.0, 30.0],
        "baseline_offsets": {"mass_gt": 400.0, "volume_km3": 3000.0, "firn_km3": 500.0},
    },
    "antarctica": {
        "gravimetry_gt_yr": -130.0, "residual_gt_yr": -5.0,
        "annual_amplitude_mass_gt": 60.0, "annual_peak_mass_month": 9,
        "interannual_ar1": {"phi": 0.8, "sigma_gt": 20.0},
        "noise_sigma_mass_gt": "40 to 50, an annual pattern",
        "area_km2": {"grounded": 12000000.0},
        "noise_sigma_volume_km3": 15.0, "volume_uncertainty_km3": [15.0, 60.0],
        "baseline_offsets": {"mass_gt": 200.0, "volume_km3": 1500.0},
        "firn": "no grounded firn term, as the real root",
    },
}
FIXTURE_BOOKKEEPING = {
    "mass": {
        "gia": "synthetic: no GIA signal generated; a real run names the model the mascon product "
               "subtracted (ICE-6G_D for the JPL product)",
        "low_degree": "synthetic: none; a real run names the degree-1 and C20/C30 series the product applied",
        "reference_frame": "synthetic: one frame by construction",
        "effective_smoothing": "synthetic ice sheet total: no mascon footprint; a real run states the "
                               "mascon selection rule and the leakage caveat",
        "selection": {"greenland": "synthetic: the whole synthetic sheet",
                      "antarctica": "synthetic: the whole synthetic sheet"},
        "selection_sensitivity": {"greenland": None, "antarctica": None},
        "uncertainty_basis": "synthetic: the stated per-month sigma, an annual pattern",
    },
    "volume": {
        "reference": "synthetic: anomaly against the series start",
        "mask": "synthetic: the whole synthetic sheet, split 95 to 5 between the ice sheet and the "
                "peripheral glaciers for Greenland",
        "uncertainty_basis": "synthetic: the stated per-epoch sigma, with a correlated bound stated beside it",
        "not_mass": "synthetic surface height volume: the firn air volume is removed and the density "
                    "applied by the computation",
    },
    "firn": {
        "reference": "synthetic: anomaly against the series start",
        "uncertainty_basis": "synthetic model spread |N(0.08, 0.06)| m, crossing zero, so the floor rule is exercised",
        "gemb_version": "synthetic", "forcing": "synthetic",
    },
    "closure": {
        "greenland": {"gravimetry": "synthetic mass", "altimetry": "synthetic volume less synthetic firn air",
                      "input_output": "not possible: the fixture carries no surface mass balance or discharge"},
        "antarctica": {"gravimetry": "synthetic mass",
                       "altimetry": "not possible: no grounded firn term, as the real root",
                       "input_output": "not possible: no surface mass balance or discharge"},
    },
}
REQUIRED_BOOKKEEPING = (
    ("mass", "gia"), ("mass", "low_degree"), ("mass", "reference_frame"),
    ("mass", "effective_smoothing"), ("mass", "selection"), ("mass", "uncertainty_basis"),
    ("volume", "reference"), ("volume", "mask"), ("volume", "uncertainty_basis"), ("volume", "not_mass"),
    ("firn", "reference"), ("firn", "uncertainty_basis"), ("firn", "gemb_version"), ("firn", "forcing"),
    ("closure", "greenland"), ("closure", "antarctica"),
)


# ---- months

def ym(date: str) -> int:
    return int(date[:4]) * 12 + int(date[5:7]) - 1


def label(k: int) -> str:
    return f"{k // 12:04d}-{k % 12 + 1:02d}"


def parse_window(window: str):
    m = re.fullmatch(r"(\d{4}-\d{2}):(\d{4}-\d{2})", window or "")
    if not m or not (1 <= int(m.group(1)[5:]) <= 12 and 1 <= int(m.group(2)[5:]) <= 12) \
            or ym(m.group(1)) > ym(m.group(2)):
        raise SystemExit(f"window must be YYYY-MM:YYYY-MM, got {window!r}")
    return m.group(1), m.group(2)


def crosses_gap(months) -> bool:
    """Mass months on both sides of the inter-mission gap."""
    ks = [ym(m) for m in months]
    return bool(ks) and min(ks) < ym(GAP[0]) and max(ks) > ym(GAP[1])


# ---- the trend method (stdlib)

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
        if hi > 1e12:
            raise ArithmeticError("t quantile out of range")
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        if t_cdf(mid, df) < p:
            lo = mid
        else:
            hi = mid
        if hi - lo < 1e-13 * max(1.0, hi):
            break
    return 0.5 * (lo + hi)


LAG_MONTHS = 12


def rate_block(epochs, values, uncertainties, step, units) -> dict:
    """The rate method statement on one series: the annual-lag
    differences d(t) = v(t) - v(t - 12 months) at every epoch whose
    partner exists, each with its uncertainty in quadrature; the rate
    is their mean (the seasonal cycle cancels in a 12-month lag); the
    lag-1 autocorrelation over differences one step apart gives the
    effective sample size, floored at the number of non-overlapping
    years (differences a year apart share no epoch); Student's t on
    n_eff minus 1; the half width is that quantile times the larger of
    the sampling error (the standard deviation over root n_eff) and the
    formal error of the mean (the difference uncertainties in
    quadrature over n). Units are per year."""
    by = {m: (v, u) for m, v, u in zip(epochs, values, uncertainties)}
    d_epochs, d, du = [], [], []
    for m in epochs:
        prev = label(ym(m) - LAG_MONTHS)
        if prev in by:
            d_epochs.append(m)
            d.append(by[m][0] - by[prev][0])
            du.append(math.sqrt(by[m][1] ** 2 + by[prev][1] ** 2))
    n = len(d)
    block = {"method": "mean of the annual-lag differences on the epochs whose partner a year "
                       "earlier exists; the effective sample size from the lag-1 autocorrelation "
                       "of the differences, floored at the number of non-overlapping years; "
                       "Student's t on n_eff minus 1; the larger of the sampling and the formal "
                       "error (the method statement in this executor's docstring)",
             "confidence": CONFIDENCE, "units": units, "lag_months": LAG_MONTHS, "step_months": step,
             "n_epochs": len(epochs), "n_differences": n, "difference_epochs": d_epochs}
    per_year = LAG_MONTHS // step
    if n < per_year:
        block.update({"stated": False, "reason": f"{n} annual-lag differences, fewer than one year of them ({per_year})"})
        return block
    mean = sum(d) / n
    block["rate"] = mean
    block["formal_se"] = math.sqrt(sum(u * u for u in du)) / n
    block["formal_95"] = Z95 * block["formal_se"]
    if n < 2:
        block.update({"stated": False, "reason": "one difference; no scatter"})
        return block
    ss = sum((x - mean) ** 2 for x in d)
    sd = math.sqrt(ss / (n - 1))
    pairs = [(i, i + 1) for i in range(n - 1) if ym(d_epochs[i + 1]) - ym(d_epochs[i]) == step]
    r1 = (sum((d[i] - mean) * (d[j] - mean) for i, j in pairs) / ss) if ss > 0 and pairs else 0.0
    n_ar1 = min(float(n), n * (1.0 - r1) / (1.0 + r1)) if r1 < 1.0 else 1.0
    n_years = n / per_year
    n_eff = max(n_ar1, n_years)
    dof = n_eff - 1.0
    block.update({"sd": sd, "r1": r1, "n_eff_ar1": n_ar1, "n_years": n_years, "n_eff": n_eff, "dof": dof,
                  "sampling_se": sd / math.sqrt(n_eff)})
    if dof < MIN_DOF or sd == 0.0:
        block.update({"stated": False, "reason": f"{dof:.2f} degrees of freedom or no scatter; no interval is stated"})
        return block
    tq = t_quantile(0.5 + CONFIDENCE / 2.0, dof)
    se = max(block["sampling_se"], block["formal_se"])
    half = tq * se
    block.update({"stated": True, "t_quantile": tq, "se": se, "half_width": half,
                  "ci_low": mean - half, "ci_high": mean + half,
                  "se_basis": "sampling" if block["sampling_se"] >= block["formal_se"] else "formal",
                  "significant_at_confidence": bool((mean - half) * (mean + half) > 0)})
    return block


def differences(block: dict, epochs, values):
    """The annual-lag differences a block was formed from, keyed by epoch."""
    by = {m: v for m, v in zip(epochs, values)}
    return {m: by[m] - by[label(ym(m) - LAG_MONTHS)] for m in block["difference_epochs"]}


# ---- the fixture

def normals(seed: int, stream: str, n: int):
    """A deterministic standard-normal stream: SHA-256 in counter mode
    for the uniforms, Box-Muller for the pair. Stdlib only, so the
    fixture digest is the same on every platform and library release."""
    out, counter = [], 0
    scale = 2.0 ** 64 + 2.0
    while len(out) < n:
        h = hashlib.sha256(f"{seed}:{stream}:{counter}".encode()).digest()
        u1 = (int.from_bytes(h[:8], "big") + 1) / scale
        u2 = (int.from_bytes(h[8:16], "big") + 1) / scale
        r = math.sqrt(-2.0 * math.log(u1))
        out.append(r * math.cos(2.0 * math.pi * u2))
        out.append(r * math.sin(2.0 * math.pi * u2))
        counter += 1
    return out[:n]


def ar1(seed: int, stream: str, n: int, phi: float, sigma: float):
    e = normals(seed, stream, n)
    x = [e[0] * sigma / math.sqrt(1.0 - phi * phi)]
    for i in range(1, n):
        x.append(phi * x[-1] + sigma * e[i])
    return x


def months_between(span):
    return [label(k) for k in range(ym(span[0]), ym(span[1]) + 1)]


def make_fixture(seed: int) -> dict:
    """The synthetic root as rows of the loaders' CSV schemas, keyed by
    term; the truth is TRUTH and the planted residual is recovered by
    the computation."""
    rows = {"mass": [], "firn": [], "volume-itslive": [], "volume-atl15": []}
    missing = set(BATTERY_MONTHS) | set(months_between(GAP))
    for sheet, t in TRUTH.items():
        # the true mass in Gt on every month of the widest span
        span = ("1992-01", "2025-12")
        months = months_between(span)
        n = len(months)
        k0 = ym(span[0])
        ar = ar1(seed, f"{sheet}-mass-interannual", n, t["interannual_ar1"]["phi"], t["interannual_ar1"]["sigma_gt"])
        e_mass, e_vol, e_firn = normals(seed, f"{sheet}-mass", n), normals(seed, f"{sheet}-volume", n), normals(seed, f"{sheet}-firn", n)
        e_firn_u = normals(seed, f"{sheet}-firn-uncertainty", n)
        e_vol_q = normals(seed, f"{sheet}-volume-quarterly", n)
        true_mass, air = [], []
        for i, m in enumerate(months):
            month = int(m[5:])
            true_mass.append(t["gravimetry_gt_yr"] / 12.0 * i
                             + t["annual_amplitude_mass_gt"]
                             * math.cos(2.0 * math.pi * (month - t["annual_peak_mass_month"]) / 12.0)
                             + ar[i])
            if sheet == "greenland":
                air.append(t["firn_air_km3_yr"] / 12.0 * i
                           + t["annual_amplitude_firn_km3"]
                           * math.cos(2.0 * math.pi * (month - t["annual_peak_firn_month"]) / 12.0)
                           + t["noise_sigma_firn_km3"] * e_firn[i])
            else:
                air.append(0.0)
        rho = ICE_DENSITY_DEFAULT / 1000.0
        for i, m in enumerate(months):
            month = int(m[5:])
            # mass term: the mascon span with its holes
            if ym(FIXTURE_SPANS["mass"][0]) <= ym(m) <= ym(FIXTURE_SPANS["mass"][1]) and m not in missing:
                s_mass = (20.0 if sheet == "greenland" else 40.0) + 10.0 * (1.0 + math.cos(2.0 * math.pi * (month - 1) / 12.0)) / 2.0
                rows["mass"].append({"ice_sheet": sheet, "domain": MASS_DOMAIN, "month": m,
                                     "value_gt": t["baseline_offsets"]["mass_gt"] + true_mass[i] + s_mass * e_mass[i],
                                     "uncertainty_gt": s_mass, "sampling": "monthly"})
            # the altimetric volume: ice volume plus firn air plus the planted residual
            ice_vol = (true_mass[i] + t["residual_gt_yr"] / 12.0 * i) / rho
            vol = t["baseline_offsets"]["volume_km3"] + ice_vol + air[i] + t["noise_sigma_volume_km3"] * e_vol[i]
            if ym(FIXTURE_SPANS["volume-itslive"][0]) <= ym(m) <= ym(FIXTURE_SPANS["volume-itslive"][1]):
                if sheet == "greenland":
                    for dom, frac in t["volume_split"].items():
                        rows["volume-itslive"].append({
                            "ice_sheet": sheet, "domain": dom, "month": m, "value_km3": vol * frac,
                            "uncertainty_km3": t["volume_uncertainty_km3"][0] * frac,
                            "uncertainty_correlated_km3": t["volume_uncertainty_km3"][1] * frac,
                            "area_km2": t["area_km2"][dom], "sampling": "monthly", "product": "itslive"})
                else:
                    rows["volume-itslive"].append({
                        "ice_sheet": sheet, "domain": "grounded", "month": m, "value_km3": vol,
                        "uncertainty_km3": t["volume_uncertainty_km3"][0],
                        "uncertainty_correlated_km3": t["volume_uncertainty_km3"][1],
                        "area_km2": t["area_km2"]["grounded"], "sampling": "monthly", "product": "itslive"})
            if (ym(FIXTURE_SPANS["volume-atl15"][0]) <= ym(m) <= ym(FIXTURE_SPANS["volume-atl15"][1])
                    and month in (1, 4, 7, 10)):
                vq = (t["baseline_offsets"]["volume_km3"] + ice_vol + air[i]
                      + t["noise_sigma_volume_km3"] * e_vol_q[i])
                rows["volume-atl15"].append({
                    "ice_sheet": sheet, "domain": "gl" if sheet == "greenland" else "a1_a4", "month": m,
                    "value_km3": vq, "uncertainty_km3": t["volume_uncertainty_km3"][0] * 1.5,
                    "uncertainty_correlated_km3": t["volume_uncertainty_km3"][1] * 1.5,
                    "area_km2": sum(t["area_km2"].values()), "sampling": "quarterly", "product": "atl15"})
            # the firn air content: Greenland only, split by area, uncertainty in metres crossing zero
            if sheet == "greenland" and ym(FIXTURE_SPANS["firn"][0]) <= ym(m) <= ym(FIXTURE_SPANS["firn"][1]):
                total_area = sum(t["area_km2"].values())
                for dom, area in t["area_km2"].items():
                    vol_air = (t["baseline_offsets"]["firn_km3"] + air[i]) * area / total_area
                    rows["firn"].append({
                        "ice_sheet": sheet, "domain": dom, "month": m,
                        "value_m": vol_air / area * 1e3, "uncertainty_m": abs(0.08 + 0.06 * e_firn_u[i]),
                        "volume_km3": vol_air, "area_km2": area, "sampling": "monthly"})
    return {"seed": seed, "spans": FIXTURE_SPANS, "rows": rows}


def fixture_digest(fx: dict) -> str:
    return "sha256:" + hashlib.sha256(
        json.dumps(fx, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def write_fixture_root(fx: dict, root: Path, record: str = "fixture-root") -> None:
    """The fixture as a data root on disk (the loaders' CSV schemas, a
    stamp per term and a RECORD.json), for the attester's selftest of
    the data-root path."""
    root.mkdir(parents=True, exist_ok=True)
    columns = {
        "mass": ["ice_sheet", "domain", "month", "value_gt", "uncertainty_gt", "sampling"],
        "firn": ["ice_sheet", "domain", "month", "value_m", "uncertainty_m", "volume_km3", "area_km2", "sampling"],
        "volume-itslive": ["ice_sheet", "domain", "month", "value_km3", "uncertainty_km3",
                           "uncertainty_correlated_km3", "area_km2", "sampling", "product"],
        "volume-atl15": ["ice_sheet", "domain", "month", "value_km3", "uncertainty_km3",
                         "uncertainty_correlated_km3", "area_km2", "sampling", "product"],
    }
    files, stamps = {}, {}
    for term, rows in fx["rows"].items():
        p = root / f"{term}.csv"
        with p.open("w", encoding="utf-8", newline="") as f:
            wr = csv.DictWriter(f, fieldnames=columns[term])
            wr.writeheader()
            for r in rows:
                wr.writerow({k: (f"{v:.6f}" if isinstance(v, float) else v) for k, v in r.items() if k in columns[term]})
        files[p.name] = sha256_file(p)
        stamps[term] = {"term": term, "granule": "synthetic", "granule_sha256": "sha256:synthetic",
                        "read_utc": "synthetic", "months": list(fx["spans"][term]),
                        "domains": sorted({(r["ice_sheet"], r["domain"]) for r in rows}),
                        "series": {}}
        (root / f"{term}-stamp.json").write_text(json.dumps(stamps[term], indent=2) + "\n", encoding="utf-8")
    smb = root / "smb.csv"
    smb.write_text("ice_sheet,domain,month,value_gt_per_yr,uncertainty_gt_per_yr,sampling\n", encoding="utf-8")
    files[smb.name] = sha256_file(smb)
    stamps["smb"] = {"term": "smb", "months": ["", ""], "domains": [], "series": {}}
    (root / "smb-stamp.json").write_text(json.dumps(stamps["smb"], indent=2) + "\n", encoding="utf-8")
    mh = hashlib.sha256("\n".join(f"{k} {v}" for k, v in sorted(files.items())).encode()).hexdigest()
    record_doc = {"record": record, "manifest": files, "manifest_sha256": "sha256:" + mh,
                  "verified_utc": "synthetic", "terms_present": sorted(files_term(k) for k in files),
                  "terms_absent": {}, "terms": stamps, "bookkeeping": FIXTURE_BOOKKEEPING}
    (root / "RECORD.json").write_text(json.dumps(record_doc, indent=2) + "\n", encoding="utf-8")


def files_term(name: str) -> str:
    return name[:-4]


# ---- a data root

def read_rows(path: Path) -> list:
    with path.open(encoding="utf-8", newline="") as f:
        return [{k: (v.strip() if isinstance(v, str) else v) for k, v in row.items()}
                for row in csv.DictReader(f)]


def package_root(start: Path):
    for p in (start, *start.parents):
        if (p / ".osp" / "package.yaml").is_file():
            return p
    return None


def relative_root(root: Path) -> str:
    """The data root package-relative when it lies inside a package
    tree (so a run id does not depend on where the tree is checked
    out), else its absolute path."""
    root = root.resolve()
    pkg = package_root(root)
    if pkg is not None:
        return root.relative_to(pkg).as_posix()
    return root.as_posix()


def read_data_root(root: Path) -> dict:
    root = root.expanduser().resolve()
    stamp = root / "RECORD.json"
    if not stamp.is_file():
        raise SystemExit(f"{root} carries no RECORD.json stamp; nothing is computed on an unrecorded tree")
    record = json.loads(stamp.read_text(encoding="utf-8"))
    book = record.get("bookkeeping")
    if not isinstance(book, dict):
        raise SystemExit("RECORD.json carries no bookkeeping table")
    present = record.get("terms_present") or list(record.get("terms", {}))
    rows, files = {}, {}
    for term in ("mass", "firn", "volume-itslive", "volume-atl15"):
        if term not in present:
            continue
        path = root / f"{term}.csv"
        if not path.is_file():
            raise SystemExit(f"{root} lacks {term}.csv though RECORD.json lists it")
        rows[term] = read_rows(path)
        files[path.name] = sha256_file(path)
        if (record.get("manifest") or {}).get(path.name) != files[path.name]:
            raise SystemExit(f"{path.name} does not match the RECORD.json manifest ({files[path.name]} on disk); "
                             "nothing is computed on a tree that drifted from its stamp")
    for term in ("mass", "firn", "volume-itslive"):
        if term not in rows:
            raise SystemExit(f"RECORD.json lists no {term} term; the closure needs it")
    record_summary = {k: record.get(k) for k in ("record", "manifest_sha256", "verified_utc",
                                                  "terms_present", "terms_absent")}
    stamps = {t: {k: s.get(k) for k in ("term", "months", "read_utc")} | {
        "series": {name: {k: v for k, v in ss.items() if k in ("granule", "granule_sha256", "read_utc", "product", "doi")}
                   for name, ss in (s.get("series") or {}).items()}}
              for t, s in record.get("terms", {}).items()}
    return {"rows": rows, "record": record_summary, "record_sha256": sha256_file(stamp),
            "stamps": stamps, "bookkeeping": bookkeeping_from_record(book),
            "files": files, "data_root": relative_root(root)}


def bookkeeping_from_record(book: dict) -> dict:
    """The statements the closure carries, read from the record's
    bookkeeping table (a real root) or passed through (a fixture root)."""
    if "mass" in book and "gia" in book["mass"] and "volume" in book:
        return book                                    # already in the closure's shape
    mass = book.get("mass", {})
    vol_key = "volume-itslive" if "volume-itslive" in book else "volume-atl15"
    vol = book.get(vol_key, {})
    firn = book.get("firn", {})
    return {
        "mass": {k: mass.get(k, "") for k in ("gia", "low_degree", "reference_frame", "effective_smoothing",
                                                "gad", "elastic_and_hydrology", "uncertainty_basis")}
                | {"selection": {name: s.get("rule", "") for name, s in (mass.get("selection") or {}).items()},
                   "selection_sensitivity": {name: s.get("selection_sensitivity")
                                             for name, s in (mass.get("selection") or {}).items()}},
        "volume": {k: vol.get(k, "") for k in ("reference", "mask", "uncertainty_basis", "not_mass", "aggregation")},
        "volume_atl15": {k: book.get("volume-atl15", {}).get(k, "") for k in ("reference", "mask", "uncertainty_basis", "not_mass", "absent")},
        "firn": {k: firn.get(k, "") for k in ("reference", "uncertainty_basis", "gemb_version", "forcing", "mask", "aggregation")},
        "closure": book.get("closure", {}),
    }


# ---- assembling the terms

def series_by_month(rows, ice_sheet, domain, value_key, unc_key):
    out = {}
    for r in rows:
        if r["ice_sheet"] == ice_sheet and r["domain"] == domain:
            if r["month"] in out:
                raise SystemExit(f"two rows for {ice_sheet}/{domain} in {r['month']}")
            out[r["month"]] = (float(r[value_key]), float(r[unc_key]), r)
    return out


def assemble(ice_sheet: str, altimetry: str, rows: dict, density: float):
    """The per-term series the closure fits, or a refusal."""
    mass = series_by_month(rows["mass"], ice_sheet, MASS_DOMAIN, "value_gt", "uncertainty_gt")
    if not mass:
        return None, ("term-not-in-root", f"the root carries no mass rows for {ice_sheet}")
    vol_term = f"volume-{altimetry}"
    if vol_term not in rows:
        return None, ("term-not-in-root", f"the root carries no {vol_term} term (its RECORD names the reason)")
    domains = ALTIMETRY_DOMAINS[altimetry][ice_sheet]
    vols = [series_by_month(rows[vol_term], ice_sheet, d, "value_km3", "uncertainty_km3") for d in domains]
    if any(not v for v in vols):
        return None, ("term-not-in-root",
                      f"the {vol_term} term carries no rows for {ice_sheet} over {list(domains)}")
    firn_domains = FIRN_DOMAINS[ice_sheet]
    firns = [series_by_month(rows["firn"], ice_sheet, d, "volume_km3", "uncertainty_m") for d in firn_domains]
    if any(not f for f in firns):
        have = sorted({(r["ice_sheet"], r["domain"]) for r in rows["firn"]})
        return None, ("firn-term-missing",
                      f"the firn term carries no rows for {ice_sheet} over {list(firn_domains)} (the root "
                      f"holds {have}); a surface height change is not a mass change without the firn "
                      "air content change, so the altimetric rate cannot be formed")
    # the firn floor per domain: the series median of the stated uncertainty in metres
    floors = {}
    for d, f in zip(firn_domains, firns):
        floors[d] = statistics.median(u for _, u, _ in f.values())
    sampling = next(iter(vols[0].values()))[2].get("sampling", "monthly")
    step = STEP.get(sampling, 1)
    # the volume epochs common to every volume domain and every firn domain
    epochs = sorted(set.intersection(*(set(v) for v in vols), *(set(f) for f in firns)))
    volume = {"epochs": epochs, "values": [], "uncertainties": [], "uncertainties_correlated": []}
    firn = {"epochs": epochs, "values": [], "uncertainties": [], "uncertainties_stated": [], "floor_m": floors}
    alt = {"epochs": epochs, "values": [], "uncertainties": []}
    rho = density / 1000.0                       # Gt per km3
    for m in epochs:
        v = sum(vv[m][0] for vv in vols)
        vu = math.sqrt(sum(vv[m][1] ** 2 for vv in vols))
        vc = sum(float(vv[m][2].get("uncertainty_correlated_km3", vv[m][1])) for vv in vols)
        a = sum(ff[m][0] for ff in firns)
        au_stated = math.sqrt(sum((ff[m][1] * float(ff[m][2]["area_km2"]) * 1e-3) ** 2 for ff in firns))
        au = math.sqrt(sum((max(ff[m][1], floors[d]) * float(ff[m][2]["area_km2"]) * 1e-3) ** 2
                           for d, ff in zip(firn_domains, firns)))
        volume["values"].append(v); volume["uncertainties"].append(vu); volume["uncertainties_correlated"].append(vc)
        firn["values"].append(a); firn["uncertainties"].append(au); firn["uncertainties_stated"].append(au_stated)
        alt["values"].append(rho * (v - a))
        alt["uncertainties"].append(rho * math.sqrt(vu * vu + au * au))
    mass_epochs = sorted(mass)
    grav = {"epochs": mass_epochs, "values": [mass[m][0] for m in mass_epochs],
            "uncertainties": [mass[m][1] for m in mass_epochs]}
    return {"gravimetry": grav, "volume": volume, "firn": firn, "altimetry": alt,
            "step": {"gravimetry": 1, "altimetry": step, "volume": step, "firn": step},
            "spans": {"gravimetry": [mass_epochs[0], mass_epochs[-1]],
                      "altimetry": [epochs[0], epochs[-1]] if epochs else None,
                      "volume": [min(min(v) for v in vols), max(max(v) for v in vols)],
                      "firn": [min(min(f) for f in firns), max(max(f) for f in firns)]},
            "domains": {"volume": list(domains), "firn": list(firn_domains), "mass": MASS_DOMAIN},
            "density": density}, None


def window_terms(term: dict, start: str, end: str):
    k0, k1 = ym(start), ym(end)
    idx = [i for i, m in enumerate(term["epochs"]) if k0 <= ym(m) <= k1]
    return {k: ([v[i] for i in idx] if isinstance(v, list) else v) for k, v in term.items()}


def selection_systematic(bookkeeping: dict, ice_sheet: str) -> dict:
    """The stated systematic of the mascon selection: half the spread of
    the full-series trends the mass stamp recorded under the other
    selection thresholds, added to the bar as the sea level budget adds
    its deep-steric uncertainty; zero, and said so, where the stamp
    recorded none (a synthetic root, or a sheet with one rule)."""
    sens = (bookkeeping.get("mass", {}).get("selection_sensitivity") or {}).get(ice_sheet)
    trends = [v.get("trend_gt_per_yr_full_series") for v in (sens or {}).values()
              if isinstance(v, dict) and isinstance(v.get("trend_gt_per_yr_full_series"), (int, float))]
    if len(trends) >= 2:
        return {"value_gt_per_yr": 0.5 * (max(trends) - min(trends)),
                "basis": "half the spread of the full-series mascon trends under the other selection "
                         "thresholds the mass stamp records (selection_sensitivity); a stated "
                         "systematic of the mascon selection, added to the bar, not folded into the noise",
                "trends_gt_per_yr": {k: v.get("trend_gt_per_yr_full_series") for k, v in sens.items()}}
    return {"value_gt_per_yr": 0.0,
            "basis": "no selection sensitivity recorded for this ice sheet in the mass stamp (a "
                     "synthetic root, or one rule only); the systematic is stated as zero"}


def compute(terms: dict, start: str, end: str, bridge, bookkeeping: dict, ice_sheet: str):
    """(receipt body, None) or (None, (reason_code, reason)) over the window."""
    n_calendar = ym(end) - ym(start) + 1
    if n_calendar < MIN_WINDOW_MONTHS:
        return None, ("too-few-epochs", f"the window {start}:{end} spans {n_calendar} months; "
                                        f"the closure needs at least {MIN_WINDOW_MONTHS}")
    for name in ("gravimetry", "altimetry"):
        span = terms["spans"][name]
        if span is None or not (ym(span[0]) <= ym(start) and ym(end) <= ym(span[1])):
            return None, ("window-outside-overlap",
                          f"the window {start}:{end} lies outside the {name} term's span "
                          f"{span[0] if span else None} through {span[1] if span else None}; the "
                          f"overlap of the terms is {overlap(terms)}")
    used = {name: window_terms(terms[name], start, end) for name in ("gravimetry", "altimetry", "volume", "firn")}
    for name in ("gravimetry", "altimetry"):
        if len(used[name]["epochs"]) < MIN_EPOCHS[name]:
            return None, ("too-few-epochs",
                          f"the {name} term has {len(used[name]['epochs'])} epochs in {start}:{end}; "
                          f"the closure needs at least {MIN_EPOCHS[name]}")
    if crosses_gap(used["gravimetry"]["epochs"]) and not bridge:
        return None, ("gap-without-bridge",
                      f"the window {start}:{end} has mascon months on both sides of the GRACE to "
                      f"GRACE-FO gap ({GAP[0]} through {GAP[1]}); a rate across it needs --bridge, a "
                      "citation of the independent continuity evidence, and none was given")
    blocks = {}
    for name in ("gravimetry", "altimetry", "volume", "firn"):
        u = used[name]
        units = "Gt/year" if name in ("gravimetry", "altimetry") else "km3/year"
        blocks[name] = rate_block(u["epochs"], u["values"], u["uncertainties"], terms["step"][name], units)
    for name in ("gravimetry", "altimetry"):
        if not blocks[name]["stated"]:
            return None, ("interval-not-stated",
                          f"the {name} rate carries no interval ({blocks[name]['reason']}); a "
                          "combined uncertainty cannot be formed")
    # the residual on the common difference epochs, so the interannual
    # signal both methods see cancels before its scatter is measured
    d_alt = differences(blocks["altimetry"], used["altimetry"]["epochs"], used["altimetry"]["values"])
    d_grav = differences(blocks["gravimetry"], used["gravimetry"]["epochs"], used["gravimetry"]["values"])
    du_alt = dict(zip(blocks["altimetry"]["difference_epochs"],
                      _difference_uncertainties(used["altimetry"])))
    du_grav = dict(zip(blocks["gravimetry"]["difference_epochs"],
                       _difference_uncertainties(used["gravimetry"])))
    common = sorted(set(d_alt) & set(d_grav))
    if len(common) < LAG_MONTHS // terms["step"]["altimetry"]:
        return None, ("too-few-epochs",
                      f"only {len(common)} annual-lag differences are common to both terms in "
                      f"{start}:{end}; the residual needs at least one year of them")
    resid_series = {"epochs": common, "values": [d_alt[m] - d_grav[m] for m in common],
                    "uncertainties": [math.sqrt(du_alt[m] ** 2 + du_grav[m] ** 2) for m in common],
                    "altimetry_differences": [d_alt[m] for m in common],
                    "gravimetry_differences": [d_grav[m] for m in common]}
    blocks["residual"] = mean_block(resid_series["values"], resid_series["uncertainties"], common,
                                    terms["step"]["altimetry"], "Gt/year")
    if not blocks["residual"]["stated"]:
        return None, ("interval-not-stated",
                      f"the residual carries no interval ({blocks['residual']['reason']})")
    systematic = selection_systematic(bookkeeping, ice_sheet)
    bar = blocks["residual"]["half_width"] + systematic["value_gt_per_yr"]
    residual = blocks["residual"]["rate"]
    closed = abs(residual) <= bar
    years = n_calendar / 12.0
    calendar = [label(k) for k in range(ym(start), ym(end) + 1)]
    mass_missing = [m for m in calendar if m not in set(used["gravimetry"]["epochs"])]
    book = json.loads(json.dumps(bookkeeping))
    book["density"] = {"ice_density_kg_m3": terms["density"],
                       "basis": "the density applied to the firn-corrected height change; the default "
                                "917 kg per m3 is the ice density the GEMB surface mass balance product "
                                "itself uses, and the parameter is declared so a run may state another"}
    book["firn_floor"] = {"floor_m": used["firn"]["floor_m"],
                          "rule": "the firn term's stated uncertainty is a model spread that crosses "
                                  "zero; each row's uncertainty is floored at the series median of its "
                                  "domain before it is propagated, and the stated values travel beside "
                                  "the floored ones"}
    book["gap_handling"] = {
        "rule": "an epoch missing from a term is a hole, never interpolated; an annual-lag difference "
                "exists only where both its epochs do; each rate is the mean of its own term's "
                "differences in the window, and the residual is the mean of the difference of the "
                "two on their common epochs",
        "mass_months_missing": mass_missing,
        "crosses_intermission_gap": crosses_gap(used["gravimetry"]["epochs"]),
        "bridge": bridge or None,
    }
    body = {
        "window": {"start": start, "end": end, "n_calendar": n_calendar, "years": years},
        "terms": {
            "gravimetry": {"units": "Gt", "domain": terms["domains"]["mass"],
                           "n_epochs": len(used["gravimetry"]["epochs"]), "step_months": 1,
                           "rate_gt_per_yr": round(blocks["gravimetry"]["rate"], 4),
                           "uncertainty_gt_per_yr": blocks["gravimetry"]["half_width"],
                           "change_over_window_gt": blocks["gravimetry"]["rate"] * years},
            "altimetry": {"units": "Gt", "domain": terms["domains"]["volume"], "firn_domain": terms["domains"]["firn"],
                          "n_epochs": len(used["altimetry"]["epochs"]), "step_months": terms["step"]["altimetry"],
                          "rate_gt_per_yr": round(blocks["altimetry"]["rate"], 4),
                          "uncertainty_gt_per_yr": blocks["altimetry"]["half_width"],
                          "change_over_window_gt": blocks["altimetry"]["rate"] * years,
                          "rule": "ice density times (volume anomaly minus firn air volume anomaly) at each "
                                  "altimetry epoch; 1 km3 is density/1000 Gt"},
            "volume": {"units": "km3", "domain": terms["domains"]["volume"],
                       "n_epochs": len(used["volume"]["epochs"]),
                       "rate_km3_per_yr": round(blocks["volume"]["rate"], 4) if "rate" in blocks["volume"] else None},
            "firn": {"units": "km3 of air", "domain": terms["domains"]["firn"],
                     "n_epochs": len(used["firn"]["epochs"]),
                     "rate_km3_per_yr": round(blocks["firn"]["rate"], 4) if "rate" in blocks["firn"] else None,
                     "floor_m": used["firn"]["floor_m"]},
        },
        "series": {**{name: {k: v for k, v in used[name].items() if k != "floor_m"}
                      for name in ("gravimetry", "altimetry", "volume", "firn")},
                   "residual": resid_series},
        "rates": blocks,
        "residual": {"rate_gt_per_yr": residual,
                     "rule": "the mean of altimetry minus gravimetry annual-lag differences on their "
                             "common epochs",
                     "n_common_differences": len(common),
                     "altimetry_on_common_epochs_gt_per_yr": sum(resid_series["altimetry_differences"]) / len(common),
                     "gravimetry_on_common_epochs_gt_per_yr": sum(resid_series["gravimetry_differences"]) / len(common),
                     "change_over_window_gt": residual * years},
        "combined_uncertainty": {
            "rule": "the residual's own half width (95 percent, the method statement on the residual "
                    "series: the larger of its sampling and formal errors), so the interannual "
                    "signal common to both methods does not enter the bar; the mascon selection "
                    "systematic is stated separately and added to the bar, not folded in",
            "residual_half_width_gt_per_yr": blocks["residual"]["half_width"],
            "terms_gt_per_yr": {name: blocks[name]["half_width"] for name in ("gravimetry", "altimetry")},
            "selection_systematic": systematic, "bar_gt_per_yr": bar,
        },
        "verdict": {"closed_within_uncertainty": closed,
                    "rule": "closed when the residual rate lies within its own half width plus the "
                            "stated selection systematic",
                    "residual_gt_per_yr": residual, "bar_gt_per_yr": bar},
        "bookkeeping": book,
    }
    return body, None


def _difference_uncertainties(term: dict):
    by = {m: u for m, u in zip(term["epochs"], term["uncertainties"])}
    out = []
    for m in term["epochs"]:
        prev = label(ym(m) - LAG_MONTHS)
        if prev in by:
            out.append(math.sqrt(by[m] ** 2 + by[prev] ** 2))
    return out


def mean_block(values, uncertainties, epochs, step, units) -> dict:
    """The rate_block statistics on a series that is already a
    difference series (the residual): mean, effective sample size,
    Student's t, the larger of the sampling and formal errors."""
    n = len(values)
    block = {"method": "mean of the residual differences with the rate method's effective sample "
                       "size and interval", "confidence": CONFIDENCE, "units": units,
             "lag_months": LAG_MONTHS, "step_months": step, "n_differences": n, "difference_epochs": list(epochs)}
    per_year = LAG_MONTHS // step
    if n < max(2, per_year):
        block.update({"stated": False, "reason": f"{n} differences, fewer than one year of them ({per_year})"})
        return block
    mean = sum(values) / n
    block["rate"] = mean
    block["formal_se"] = math.sqrt(sum(u * u for u in uncertainties)) / n
    block["formal_95"] = Z95 * block["formal_se"]
    ss = sum((x - mean) ** 2 for x in values)
    sd = math.sqrt(ss / (n - 1))
    pairs = [(i, i + 1) for i in range(n - 1) if ym(epochs[i + 1]) - ym(epochs[i]) == step]
    r1 = (sum((values[i] - mean) * (values[j] - mean) for i, j in pairs) / ss) if ss > 0 and pairs else 0.0
    n_ar1 = min(float(n), n * (1.0 - r1) / (1.0 + r1)) if r1 < 1.0 else 1.0
    n_years = n / per_year
    n_eff = max(n_ar1, n_years)
    dof = n_eff - 1.0
    block.update({"sd": sd, "r1": r1, "n_eff_ar1": n_ar1, "n_years": n_years, "n_eff": n_eff, "dof": dof,
                  "sampling_se": sd / math.sqrt(n_eff)})
    if dof < MIN_DOF or sd == 0.0:
        block.update({"stated": False, "reason": f"{dof:.2f} degrees of freedom or no scatter; no interval is stated"})
        return block
    tq = t_quantile(0.5 + CONFIDENCE / 2.0, dof)
    se = max(block["sampling_se"], block["formal_se"])
    half = tq * se
    block.update({"stated": True, "t_quantile": tq, "se": se, "half_width": half,
                  "ci_low": mean - half, "ci_high": mean + half,
                  "se_basis": "sampling" if block["sampling_se"] >= block["formal_se"] else "formal",
                  "significant_at_confidence": bool((mean - half) * (mean + half) > 0)})
    return block


def overlap(terms: dict):
    spans = [s for s in (terms["spans"]["gravimetry"], terms["spans"]["altimetry"]) if s]
    if not spans:
        return None
    lo, hi = max(ym(s[0]) for s in spans), min(ym(s[1]) for s in spans)
    return [label(lo), label(hi)] if lo <= hi else "empty"


# ---- identity and plumbing

def sha256_file(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def value_digest(value) -> str:
    return "sha256:" + hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


def package_identity(root) -> dict:
    if root is None:
        return {"name": None, "version": None, "release_lock": None}
    text = (root / ".osp" / "package.yaml").read_text(encoding="utf-8")
    block = text.split("package:", 1)[1]
    name = re.search(r"^\s+name:\s*['\"]?([A-Za-z0-9._-]+)", block, re.M)
    version = re.search(r"^\s+version:\s*['\"]?([0-9][0-9.]*)", block, re.M)
    lock_path = root / ".osp" / "release-lock.json"
    lock = json.loads(lock_path.read_text(encoding="utf-8")) if lock_path.is_file() else None
    return {"name": name.group(1) if name else None,
            "version": version.group(1) if version else None,
            "release_lock": value_digest(lock) if lock is not None else None}


def bundle_root():
    return package_root(HERE)


def now_utc() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def receipt_head(args, capability, bundle, data) -> dict:
    return {
        "computation": COMPUTATION,
        "code_sha256": sha256_file(Path(__file__).resolve()),
        "capability": capability,
        "bundle": bundle,
        "runtime": {"name": args.runtime, "version": args.runtime_version},
        "generated_utc": now_utc(),
        "data": data,
        "bound_parameters": {"ice_sheet": args.ice_sheet, "window": args.window,
                             "altimetry": args.altimetry, "ice_density": float(args.ice_density),
                             "bridge": args.bridge or None},
    }


def finish(receipt: dict) -> dict:
    receipt["run_id"] = value_digest({k: v for k, v in receipt.items() if k != "generated_utc"})[:23]
    return receipt


def write(receipt: dict, path) -> None:
    text = json.dumps(receipt, indent=2) + "\n"
    if path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        print(f"receipt written: {path}", file=sys.stderr)
    else:
        print(text)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ice-sheet", required=True, choices=["greenland", "antarctica"], help="declared parameter")
    ap.add_argument("--window", required=True, help="YYYY-MM:YYYY-MM inclusive (declared parameter)")
    ap.add_argument("--altimetry", default="itslive", choices=["itslive", "atl15"],
                    help="the altimetric volume product (declared parameter; default itslive)")
    ap.add_argument("--ice-density", type=float, default=ICE_DENSITY_DEFAULT,
                    help=f"kg per m3 applied to the firn-corrected volume (declared parameter; default {ICE_DENSITY_DEFAULT})")
    ap.add_argument("--bridge", default=None,
                    help="citation of the independent continuity evidence; required for a window whose "
                         "mass months lie on both sides of the inter-mission gap (declared parameter)")
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--fixture", action="store_true", help="the synthetic root")
    mode.add_argument("--data-root", type=Path, help="a recorded tree (execution plumbing)")
    ap.add_argument("--seed", type=int, default=7, help="fixture seed (default 7)")
    ap.add_argument("--runtime", required=True, help="the runtime that ran this (recorded verbatim)")
    ap.add_argument("--runtime-version", default=None)
    ap.add_argument("--receipt", type=Path, default=None)
    ap.add_argument("--capability-root", type=Path, default=None,
                    help="the package tree this run is evidence for (default: the bundle this executor ships in)")
    args = ap.parse_args(argv)

    start, end = parse_window(args.window)
    if not (args.ice_density > 0):
        raise SystemExit("ice density must be positive")
    bundle = package_identity(bundle_root())
    capability = (package_identity(package_root(args.capability_root.expanduser().resolve()))
                  if args.capability_root else bundle)
    if args.fixture:
        fx = make_fixture(args.seed)
        rows, bookkeeping = fx["rows"], FIXTURE_BOOKKEEPING
        data = {"mode": "fixture", "seed": args.seed, "spans": fx["spans"], "digest": fixture_digest(fx),
                "generator": COMPUTATION + " (make_fixture)",
                "generator_sha256": sha256_file(Path(__file__).resolve()), "truth": TRUTH}
        stamps = {t: {"term": t, "granule": "synthetic"} for t in rows}
    else:
        tree = read_data_root(args.data_root)
        rows, bookkeeping = tree["rows"], tree["bookkeeping"]
        data = {"mode": "data-root", "data_root": tree["data_root"], "record": tree["record"],
                "record_sha256": tree["record_sha256"], "files": tree["files"]}
        stamps = tree["stamps"]
    data["domains"] = {t: sorted({f"{r['ice_sheet']}/{r['domain']}" for r in rr}) for t, rr in rows.items()}
    terms, refusal = assemble(args.ice_sheet, args.altimetry, rows, args.ice_density)
    if terms is not None:
        data["spans"] = {**data.get("spans", {}), "terms": terms["spans"]}
    head = receipt_head(args, capability, bundle, data)
    if refusal is None:
        body, refusal = compute(terms, start, end, args.bridge, bookkeeping, args.ice_sheet)
    if refusal:
        receipt = finish({**head, "refused": True, "reason_code": refusal[0], "reason": refusal[1]})
        print(f"REFUSED ({refusal[0]}): {refusal[1]}")
        write(receipt, args.receipt)
        return 3
    for name, block in body["terms"].items():
        key = "volume-" + args.altimetry if name == "altimetry" else ("mass" if name == "gravimetry" else
                                                                       "volume-" + args.altimetry if name == "volume" else "firn")
        block["stamp"] = {"term": key, **{k: v for k, v in (stamps.get(key) or {}).items() if k != "term"}}
    receipt = finish({**head, "refused": False, **body, "caveats": [
        ("a fixture run proves the chain, not the ice sheet; the real-data anchor is the stamped data "
         "root run the concept records") if args.fixture else
        ("a real-data run on a stamped root: each loader's stamp in the root states the product, the "
         "mask, the selection rule and the uncertainty basis, and the residual carries the mismatch "
         "between the mascon footprint and the altimetry domain"),
        "the series travel at full precision so every rate, interval, the residual and the verdict are "
        "recomputable from the receipt",
        "the altimetric rate is a mass rate only through the firn term and the stated density; a run "
        "without a firn term over the altimetry domain refuses rather than states a volume as a mass",
        "the interval is a statement about sampling under an AR(1) residual model on the epochs used; "
        "product systematics (the GIA model, leakage, the firn model's forcing) enter through the "
        "bookkeeping table, not the bar",
    ]})
    v = receipt["verdict"]
    where = f"fixture seed {args.seed}" if args.fixture else f"data root {data['data_root']}"
    for name in ("gravimetry", "altimetry", "volume", "firn", "residual"):
        b = receipt["rates"][name]
        band = (f"95% [{b['ci_low']:+.3f}, {b['ci_high']:+.3f}] (r1 {b['r1']:+.3f}, n_eff {b['n_eff']:.1f} of "
                f"{b['n_differences']}, {b['se_basis']} error)" if b["stated"] else f"no interval: {b['reason']}")
        rate = f"{b['rate']:+.3f}" if "rate" in b else "none"
        print(f"rate {name} {rate} {b['units']}, {band}", file=sys.stderr)
    print(f"ice sheet balance {args.ice_sheet} {start}:{end} ({args.altimetry}) on {where}: gravimetry "
          f"{receipt['terms']['gravimetry']['rate_gt_per_yr']:+.3f} Gt/yr, altimetry "
          f"{receipt['terms']['altimetry']['rate_gt_per_yr']:+.3f} Gt/yr, residual {v['residual_gt_per_yr']:+.3f} "
          f"against a bar of {v['bar_gt_per_yr']:.3f} (residual half width "
          f"{receipt['combined_uncertainty']['residual_half_width_gt_per_yr']:.3f} plus selection systematic "
          f"{receipt['combined_uncertainty']['selection_systematic']['value_gt_per_yr']:.3f}); closed_within_uncertainty "
          f"{str(v['closed_within_uncertainty']).lower()}; run {receipt['run_id']}")
    write(receipt, args.receipt)
    return 0


if __name__ == "__main__":
    sys.exit(main())
