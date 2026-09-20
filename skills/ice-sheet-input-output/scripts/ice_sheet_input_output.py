#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Sanctioned computation for the attested ice sheet mass balance by
the input-output method, in the ice sheet balance closure's shape.

Contract: knowledge/computations/ice-sheet-input-output.md. Over one
stated window, for one ice sheet and one named gate set, two terms in
gigatonnes per year and the mass rate they imply, a third estimate of
the same quantity the gravimetric and altimetric methods give:

  smb        the surface mass balance over the ice sheet's grounded
             domain (the data root's smb.csv), the product's own rate
             per time step, aggregated to the velocity epoch's
             calendar year by a period weighted mean, positive for
             mass gained at the surface;
  discharge  the flux of ice out through the gate set (the root's
             velocity.csv and thickness.csv): at each gate node, the
             ice density times the velocity component normal to the
             gate times the node width divided by the projection's
             areal scale at the node times the thickness at the node,
             summed over the nodes of every gate, positive for ice
             leaving.

The mass rate is smb minus discharge at each epoch, so a year the two
terms share cancels its common signal before the mean is taken. Each
rate over the window is the mean of its epochs, its interval takes
the effective sample size from the lag-1 autocorrelation of the
series, Student's t on the effective degrees of freedom, and the
larger of the sampling error and the formal error; the per-epoch
uncertainties are treated as fully correlated across epochs, because
the thickness error and the surface mass balance model error do not
resample from one year to the next, so the formal error of the mean
is the mean of them and not their quadrature. The bar on the mass
rate is its own half width plus the stated gate systematic, and the
verdict is whether the mass rate is distinguishable from zero.

Two input modes. --data-root DIR reads the term CSVs and RECORD.json
the loaders beside this file wrote (never a product file); the
committed root is
knowledge/references/retrieval/ice-sheet-input-output-root.
--fixture [--seed N] generates a synthetic root deterministically (a
hash-based Gaussian stream, stdlib only): a Greenland-like sheet with
a gate set that spans its margin and a planted discharge that rises
with time, a quarterly surface mass balance whose seasonal cycle
cancels over a year, a gate set whose thickness is an interpolation,
a gate set with a node on floating ice, and an Antarctic-like sheet
with both discharge factors and no grounded surface mass balance.

Refusals, exit 3 with a refusal receipt and never a number: a term
the root does not carry (term-not-in-root); a gate set the root does
not carry for the ice sheet (gate-set-not-in-root); a velocity epoch
family the root does not carry (velocity-epoch-not-in-root); a gate
set that does not span the ice sheet's grounded margin, so no sheet
wide rate can be formed from it (gate-set-incomplete); a gate node
whose thickness was not made by mass conservation
(gate-thickness-interpolated); a gate node the thickness product's
mask does not call grounded ice (gate-not-grounded); an ice sheet
whose grounded surface mass balance term is absent
(smb-term-missing); a window the velocity and surface mass balance
epochs do not cover (window-outside-epochs); a window shorter than
two years or with too few epochs in it (too-few-epochs); a rate whose
interval cannot be stated (interval-not-stated).

Consumers bind values for the declared parameters and MUST NOT edit
this file; the attester hashes it, regenerates the fixture at the
receipt's seed, and recomputes every node flux, every rate, every
interval, the mass rate, the bar and the verdict from the series in
the receipt.

  ice_sheet_input_output.py --ice-sheet greenland|antarctica
      --window YYYY-MM:YYYY-MM --gates NAME --runtime NAME
      (--fixture [--seed N] | --data-root DIR)
      [--velocity-epoch annual|static] [--ice-density KG_M3]
      [--runtime-version V] [--receipt PATH] [--capability-root DIR]
"""

import argparse
import csv
import datetime as dt
import hashlib
import json
import math
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
COMPUTATION = "skills/ice-sheet-input-output/scripts/ice_sheet_input_output.py"
DEFAULT_ROOT = "knowledge/references/retrieval/ice-sheet-input-output-root"

ICE_DENSITY_DEFAULT = 917.0        # kg per m3, the density the GEMB products themselves apply
MIN_WINDOW_MONTHS = 24
MIN_EPOCHS = 3                     # velocity epochs inside the window
CONFIDENCE = 0.95
MIN_DOF = 1.0
MIN_N_EFF = 1.0
Z95 = 1.959963984540054
EPOCH_FAMILIES = ("annual", "static")
SUPPORTED_PROVENANCE = ("mass_conservation",)
GROUNDED_MASK = ("grounded_ice",)
GROUNDED_SMB_DOMAINS = {"greenland": ("ice_sheet",), "antarctica": ("grounded",)}
TERMS = ("velocity", "thickness", "smb")
REASONS = ("term-not-in-root", "gate-set-not-in-root", "velocity-epoch-not-in-root",
           "gate-set-incomplete", "gate-thickness-interpolated", "gate-not-grounded",
           "smb-term-missing", "window-outside-epochs", "too-few-epochs",
           "interval-not-stated")

FIXTURE_SPANS = {"velocity": ("1990-01", "2023-01"), "smb": ("1992-03", "2020-12"),
                 "thickness": ("static", "static")}
TRUTH = {
    "greenland": {
        "smb_gt_yr": 400.0, "smb_ar1": {"phi": 0.45, "sigma_gt": 30.0},
        "smb_seasonal_amplitude_gt_yr": 900.0, "smb_uncertainty_gt_yr": 25.0,
        "discharge_gt_yr_at_2005": 480.0, "discharge_trend_gt_yr_per_yr": 2.0,
        "discharge_ar1": {"phi": 0.5, "sigma_gt": 10.0},
        "gate_sets": {
            "synthetic-outlets": {"gates": 8, "nodes_per_gate": 31, "spans_margin": True,
                                  "provenance": "mass_conservation", "mask": "grounded_ice"},
            "synthetic-interior": {"gates": 2, "nodes_per_gate": 11, "spans_margin": True,
                                   "provenance": "interpolation", "mask": "grounded_ice"},
            "synthetic-shelf": {"gates": 2, "nodes_per_gate": 11, "spans_margin": True,
                                "provenance": "mass_conservation", "mask": "floating_ice"},
            "synthetic-partial": {"gates": 2, "nodes_per_gate": 11, "spans_margin": False,
                                  "provenance": "mass_conservation", "mask": "grounded_ice"},
        },
        "node_width_m": 2000.0, "thickness_m": "600 to 1100, a fixed profile per node",
    },
    "antarctica": {
        "discharge_gt_yr_at_2005": 2000.0, "discharge_trend_gt_yr_per_yr": 4.0,
        "discharge_ar1": {"phi": 0.5, "sigma_gt": 25.0},
        "gate_sets": {
            "synthetic-outlets-ant": {"gates": 4, "nodes_per_gate": 21, "spans_margin": True,
                                      "provenance": "mass_conservation", "mask": "grounded_ice"},
        },
        "node_width_m": 5000.0,
        "smb": "no grounded surface mass balance term, as the real root",
    },
}
FIXTURE_BOOKKEEPING = {
    "velocity": {
        "product_and_version": {"synthetic": "synthetic annual mosaics; a real run names the "
                                             "ITS_LIVE product, its bucket label and the "
                                             "archived collection"},
        "grid": {"synthetic": "synthetic 2 km nodes; no projection"},
        "mask": {"synthetic": "synthetic: every node is on the sheet by construction"},
        "aggregation": {"synthetic": "no aggregation: one value per node and epoch"},
        "sampling": {"synthetic": "annual: one epoch per synthetic year, labelled by its January"},
        "uncertainty_basis": {"synthetic": "the stated per node error, 3 percent of the speed "
                                           "plus 5 m per year"},
        "map_units": {"synthetic": "synthetic: the areal scale is one at every node"},
        "epochs": {"synthetic": "1990 through 2023"},
    },
    "thickness": {
        "product_and_version": {"synthetic": "synthetic thickness; a real run names BedMachine, "
                                             "its version and its DOI"},
        "grid": {"synthetic": "synthetic: one thickness per node"},
        "nominal_year": {"synthetic": "synthetic: the thickness has no year"},
        "mask": {"synthetic": "the planted mask word per node, grounded_ice or floating_ice"},
        "source_variable": {"synthetic": "the planted method word per node, mass_conservation "
                                         "or interpolation"},
        "uncertainty_basis": {"synthetic": "the stated per node error, 30 m plus 5 percent of "
                                           "the thickness, summed along a gate as fully correlated"},
        "provenance_rule": "a gate node carries a discharge only where the thickness at it was "
                           "made by mass conservation",
    },
    "smb": {
        "product_and_version": {"synthetic": "synthetic surface mass balance; a real run names "
                                             "the product and its model version"},
        "grid": {"synthetic": "synthetic: one rate per domain and quarter"},
        "mask": {"synthetic": "the grounded domain of the synthetic sheet"},
        "aggregation": {"synthetic": "the planted rate plus a seasonal cycle that sums to zero "
                                     "over four quarters"},
        "sampling": {"synthetic": "quarterly: four rows a year, each a quarter of a year long"},
        "uncertainty_basis": {"synthetic": "the stated per quarter error"},
        "sign_convention": "positive is mass gained at the surface",
        "gemb_version": {"synthetic": "synthetic"},
        "forcing": {"synthetic": "synthetic"},
    },
    "gates": {},
    "closure": {
        "greenland": {"velocity": "synthetic gate nodes", "thickness": "synthetic thickness",
                      "surface_mass_balance": "synthetic grounded surface mass balance",
                      "input_output": "possible: every term is present"},
        "antarctica": {"velocity": "synthetic gate nodes", "thickness": "synthetic thickness",
                       "surface_mass_balance": "not possible: the fixture carries no grounded "
                                               "surface mass balance for this sheet, as the "
                                               "real root carries none",
                       "input_output": "not possible: the surface mass balance term is absent"},
    },
    "reading_rule": "synthetic root: the reading rule of the real root, restated",
    "discharge_rule": "the ice density times the velocity normal to the gate times the node "
                      "width divided by the areal scale times the thickness, summed over nodes",
}
REQUIRED_BOOKKEEPING = (
    ("velocity", "product_and_version"), ("velocity", "grid"), ("velocity", "mask"),
    ("velocity", "aggregation"), ("velocity", "sampling"), ("velocity", "uncertainty_basis"),
    ("velocity", "map_units"),
    ("thickness", "product_and_version"), ("thickness", "grid"), ("thickness", "nominal_year"),
    ("thickness", "mask"), ("thickness", "source_variable"),
    ("thickness", "uncertainty_basis"), ("thickness", "provenance_rule"),
    ("smb", "product_and_version"), ("smb", "grid"), ("smb", "mask"), ("smb", "aggregation"),
    ("smb", "sampling"), ("smb", "uncertainty_basis"), ("smb", "sign_convention"),
)


# ---- months and years

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


def year_of(epoch: str) -> int:
    return int(epoch[:4])


# ---- the interval method (stdlib)

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


def mean_block(epochs, values, uncertainties, units) -> dict:
    """The method statement on one annual rate series: the rate is the
    mean of its epochs; the lag-1 autocorrelation over epochs one year
    apart gives the effective sample size, clipped below at two and
    above at the number of epochs; Student's t on n_eff minus 1; the
    half width is that quantile times the larger of the sampling error
    (the standard deviation over the root of n_eff) and the formal
    error of the mean, which is the mean of the per epoch
    uncertainties because they are treated as fully correlated across
    epochs (the thickness error and the surface mass balance model
    error do not resample from year to year)."""
    n = len(values)
    block = {"method": "the mean of the term's annual epochs in the window; the effective "
                       "sample size from the lag-1 autocorrelation of the series over epochs "
                       "one year apart, clipped to at least two and at most the number of "
                       "epochs; Student's t on n_eff minus 1; the larger of the sampling error "
                       "and the formal error, the per epoch uncertainties being treated as "
                       "fully correlated across epochs (the method statement in this "
                       "executor's docstring)",
             "confidence": CONFIDENCE, "units": units, "epochs": list(epochs), "n_epochs": n}
    if n < 2:
        block.update({"stated": False, "reason": f"{n} epochs; no scatter"})
        return block
    mean = sum(values) / n
    block["rate"] = mean
    block["formal_se"] = sum(uncertainties) / n
    block["formal_95"] = Z95 * block["formal_se"]
    ss = sum((x - mean) ** 2 for x in values)
    sd = math.sqrt(ss / (n - 1))
    pairs = [(i, i + 1) for i in range(n - 1) if year_of(epochs[i + 1]) - year_of(epochs[i]) == 1]
    r1 = (sum((values[i] - mean) * (values[j] - mean) for i, j in pairs) / ss) if ss > 0 and pairs else 0.0
    n_ar1 = n * (1.0 - r1) / (1.0 + r1) if r1 < 1.0 else MIN_N_EFF
    n_eff = min(float(n), max(MIN_N_EFF, n_ar1))
    dof = n_eff - 1.0
    block.update({"sd": sd, "r1": r1, "n_eff_ar1": n_ar1, "n_eff": n_eff, "dof": dof,
                  "sampling_se": sd / math.sqrt(n_eff)})
    if dof < MIN_DOF or sd == 0.0:
        block.update({"stated": False,
                      "reason": f"{dof:.2f} degrees of freedom or no scatter; no interval is stated"})
        return block
    tq = t_quantile(0.5 + CONFIDENCE / 2.0, dof)
    se = max(block["sampling_se"], block["formal_se"])
    half = tq * se
    block.update({"stated": True, "t_quantile": tq, "se": se, "half_width": half,
                  "ci_low": mean - half, "ci_high": mean + half,
                  "se_basis": "sampling" if block["sampling_se"] >= block["formal_se"] else "formal",
                  "significant_at_confidence": bool((mean - half) * (mean + half) > 0)})
    return block


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


def fixture_nodes(sheet: str, gate_set: str, spec: dict, width: float):
    """The node table of one synthetic gate set: a fixed thickness
    profile per node, a fixed relative speed shape, the planted method
    and mask words, the areal scale one."""
    nodes = []
    for g in range(1, spec["gates"] + 1):
        for k in range(spec["nodes_per_gate"]):
            idx = len(nodes)
            thick = 600.0 + 500.0 * (0.5 - 0.5 * math.cos(2.0 * math.pi * k / spec["nodes_per_gate"]))
            shape = 1.0 + 0.4 * math.cos(2.0 * math.pi * k / spec["nodes_per_gate"]) + 0.05 * g
            prov = spec["provenance"]
            mask = spec["mask"]
            if gate_set == "synthetic-interior" and k % 3 == 0:
                prov = "interpolation"
            elif gate_set == "synthetic-interior":
                prov = "mass_conservation"
            if gate_set == "synthetic-shelf":
                mask = "floating_ice" if k % 4 == 0 else "grounded_ice"
            nodes.append({"ice_sheet": sheet, "gate_set": gate_set, "gate": f"gate-{g:02d}",
                          "node": idx, "x_m": 1000.0 * idx, "y_m": -2000.0 * g,
                          "normal_x": 1.0, "normal_y": 0.0, "width_m": width,
                          "areal_scale": 1.0, "thickness_m": thick,
                          "thickness_error_m": 30.0 + 0.05 * thick,
                          "source_code": 2 if prov == "mass_conservation" else 4,
                          "provenance": prov,
                          "mask_code": 2 if mask == "grounded_ice" else 3, "mask": mask,
                          "shape": shape})
    return nodes


def make_fixture(seed: int) -> dict:
    """The synthetic root as rows of the loaders' CSV schemas, keyed by
    term; the truth is TRUTH and the planted discharge and surface mass
    balance are recovered by the computation."""
    rows = {"velocity": [], "thickness": [], "smb": []}
    years = list(range(year_of(FIXTURE_SPANS["velocity"][0]),
                       year_of(FIXTURE_SPANS["velocity"][1]) + 1))
    rho = ICE_DENSITY_DEFAULT
    for sheet, t in TRUTH.items():
        d_noise = ar1(seed, f"{sheet}-discharge", len(years), t["discharge_ar1"]["phi"],
                      t["discharge_ar1"]["sigma_gt"])
        for gate_set, spec in t["gate_sets"].items():
            nodes = fixture_nodes(sheet, gate_set, spec, t["node_width_m"])
            for n in nodes:
                rows["thickness"].append({k: n[k] for k in (
                    "ice_sheet", "gate_set", "gate", "node", "x_m", "y_m", "thickness_m",
                    "thickness_error_m", "source_code", "provenance", "mask_code", "mask")})
            weight = [n["thickness_m"] * n["width_m"] / n["areal_scale"] for n in nodes]
            total_w = sum(weight)
            e = normals(seed, f"{sheet}-{gate_set}-nodes", len(nodes) * len(years))
            for iy, year in enumerate(years):
                target = (t["discharge_gt_yr_at_2005"]
                          + t["discharge_trend_gt_yr_per_yr"] * (year - 2005) + d_noise[iy])
                shape = [n["shape"] * (1.0 + 0.05 * e[iy * len(nodes) + i])
                         for i, n in enumerate(nodes)]
                got = sum(s * w for s, w in zip(shape, weight))
                u_mean = target * 1e12 / (rho * got)
                for i, n in enumerate(nodes):
                    u = u_mean * shape[i]
                    rows["velocity"].append({
                        "ice_sheet": sheet, "gate_set": gate_set, "gate": n["gate"],
                        "node": n["node"], "x_m": n["x_m"], "y_m": n["y_m"],
                        "normal_x": n["normal_x"], "normal_y": n["normal_y"],
                        "width_m": n["width_m"], "areal_scale": n["areal_scale"],
                        "epoch": f"{year:04d}-01", "sampling": "annual",
                        "v_normal_m_per_yr": u, "v_normal_error_m_per_yr": 0.03 * abs(u) + 5.0,
                        "speed_m_per_yr": abs(u), "count": 7})
        if sheet == "greenland":
            s_years = list(range(year_of(FIXTURE_SPANS["smb"][0]),
                                 year_of(FIXTURE_SPANS["smb"][1]) + 1))
            s_noise = ar1(seed, f"{sheet}-smb", len(s_years), t["smb_ar1"]["phi"],
                          t["smb_ar1"]["sigma_gt"])
            for iy, year in enumerate(s_years):
                base = t["smb_gt_yr"] + s_noise[iy]
                for q, month in enumerate((3, 6, 9, 12)):
                    if f"{year:04d}-{month:02d}" < FIXTURE_SPANS["smb"][0] \
                            or f"{year:04d}-{month:02d}" > FIXTURE_SPANS["smb"][1]:
                        continue
                    season = t["smb_seasonal_amplitude_gt_yr"] * math.cos(2.0 * math.pi * q / 4.0)
                    rows["smb"].append({
                        "ice_sheet": sheet, "domain": GROUNDED_SMB_DOMAINS[sheet][0],
                        "month": f"{year:04d}-{month:02d}",
                        "value_gt_per_yr": base + season,
                        "uncertainty_gt_per_yr": t["smb_uncertainty_gt_yr"],
                        "mean_m_ice_per_yr": (base + season) / 1733.0,
                        "period_years": 0.25, "area_km2": 1733000.0, "n_cells": 120347,
                        "sampling": "quarterly"})
    return {"seed": seed, "spans": FIXTURE_SPANS, "rows": rows}


def fixture_digest(fx: dict) -> str:
    return "sha256:" + hashlib.sha256(
        json.dumps(fx, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


FIXTURE_COLUMNS = {
    "velocity": ["ice_sheet", "gate_set", "gate", "node", "x_m", "y_m", "normal_x", "normal_y",
                 "width_m", "areal_scale", "epoch", "sampling", "v_normal_m_per_yr",
                 "v_normal_error_m_per_yr", "speed_m_per_yr", "count"],
    "thickness": ["ice_sheet", "gate_set", "gate", "node", "x_m", "y_m", "thickness_m",
                  "thickness_error_m", "source_code", "provenance", "mask_code", "mask"],
    "smb": ["ice_sheet", "domain", "month", "value_gt_per_yr", "uncertainty_gt_per_yr",
            "mean_m_ice_per_yr", "period_years", "area_km2", "n_cells", "sampling"],
}


def fixture_gate_table(fx: dict) -> dict:
    out = {}
    for sheet, t in TRUTH.items():
        for name, spec in t["gate_sets"].items():
            out[name] = {"ice_sheet": sheet, "n_gates": spec["gates"],
                         "n_nodes": spec["gates"] * spec["nodes_per_gate"],
                         "node_width_m": t["node_width_m"],
                         "rule": "synthetic gate set", "spans_margin": spec["spans_margin"],
                         "grounded_by": "the planted mask word per node"}
    return out


def write_fixture_root(fx: dict, root: Path, record: str = "fixture-root") -> None:
    """The fixture as a data root on disk (the loaders' CSV schemas, a
    stamp per term and a RECORD.json), for the attester's selftest of
    the data-root path."""
    root.mkdir(parents=True, exist_ok=True)
    files, stamps = {}, {}
    for term, rows in fx["rows"].items():
        p = root / f"{term}.csv"
        with p.open("w", encoding="utf-8", newline="") as f:
            wr = csv.DictWriter(f, fieldnames=FIXTURE_COLUMNS[term])
            wr.writeheader()
            for r in rows:
                wr.writerow({k: (f"{v:.9f}" if isinstance(v, float) else v)
                             for k, v in r.items() if k in FIXTURE_COLUMNS[term]})
        files[p.name] = sha256_file(p)
        stamps[term] = {"term": term, "granule": "synthetic", "granule_sha256": "sha256:synthetic",
                        "read_utc": "synthetic", "months": list(fx["spans"][term]),
                        "domains": sorted({(r["ice_sheet"], r.get("gate_set") or r.get("domain"))
                                           for r in rows}),
                        "series": {}}
        (root / f"{term}-stamp.json").write_text(json.dumps(stamps[term], indent=2) + "\n",
                                                 encoding="utf-8")
    mh = hashlib.sha256("\n".join(f"{k} {v}" for k, v in sorted(files.items())).encode()).hexdigest()
    book = json.loads(json.dumps(FIXTURE_BOOKKEEPING))
    book["gates"] = fixture_gate_table(fx)
    record_doc = {"record": record, "manifest": files, "manifest_sha256": "sha256:" + mh,
                  "verified_utc": "synthetic", "terms_present": sorted(files_term(k) for k in files),
                  "terms_absent": {}, "terms": stamps, "bookkeeping": book}
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
    for term in TERMS:
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
    if "velocity" not in rows:
        raise SystemExit("RECORD.json lists no velocity term; the discharge needs it")
    record_summary = {k: record.get(k) for k in ("record", "manifest_sha256", "verified_utc",
                                                 "terms_present", "terms_absent")}
    stamps = {t: {k: s.get(k) for k in ("term", "months", "read_utc")} | {
        "series": {name: {k: v for k, v in ss.items()
                          if k in ("granule", "granule_sha256", "read_utc", "product", "doi",
                                   "short_name", "product_version")}
                   for name, ss in (s.get("series") or {}).items()}}
              for t, s in record.get("terms", {}).items()}
    return {"rows": rows, "record": record_summary, "record_sha256": sha256_file(stamp),
            "stamps": stamps, "bookkeeping": book, "absent": record.get("terms_absent") or {},
            "files": files, "data_root": relative_root(root)}


# ---- assembling the terms

def gate_sets_in(rows, ice_sheet: str):
    return sorted({r["gate_set"] for r in rows if r["ice_sheet"] == ice_sheet})


def assemble(ice_sheet: str, gate_set: str, epoch_family: str, rows: dict, density: float,
             bookkeeping: dict, absent: dict):
    """The per-term series the balance needs, or a refusal."""
    for term in TERMS:
        if term not in rows:
            why = absent.get(term)
            return None, ("term-not-in-root",
                          f"the root carries no {term} term"
                          + (f": {why}" if why else "") + "; the input-output balance needs it")
    vel_all = [r for r in rows["velocity"] if r["ice_sheet"] == ice_sheet]
    if not vel_all:
        return None, ("gate-set-not-in-root",
                      f"the velocity term carries no rows for {ice_sheet} (it holds "
                      f"{sorted({r['ice_sheet'] for r in rows['velocity']})})")
    families = sorted({r.get("sampling", "annual") for r in vel_all})
    if epoch_family not in families:
        return None, ("velocity-epoch-not-in-root",
                      f"the velocity term carries no {epoch_family} epochs for {ice_sheet} "
                      f"(it holds {families})")
    vel = [r for r in vel_all if r["gate_set"] == gate_set and r.get("sampling") == epoch_family]
    if not vel:
        return None, ("gate-set-not-in-root",
                      f"the velocity term carries no {epoch_family} rows for {ice_sheet} and "
                      f"gate set {gate_set!r} (it holds {gate_sets_in(vel_all, ice_sheet)})")
    thick = {(r["gate"], int(r["node"])): r for r in rows["thickness"]
             if r["ice_sheet"] == ice_sheet and r["gate_set"] == gate_set}
    if not thick:
        return None, ("term-not-in-root",
                      f"the thickness term carries no rows for {ice_sheet} and gate set "
                      f"{gate_set!r}; a discharge is velocity times thickness")
    table = (bookkeeping.get("gates") or {}).get(gate_set) or {}
    if table.get("spans_margin") is not True:
        return None, ("gate-set-incomplete",
                      f"the gate set {gate_set!r} does not span the grounded margin of "
                      f"{ice_sheet} (the record's gate table says spans_margin "
                      f"{table.get('spans_margin')!r}), so the discharge through it is the "
                      "discharge of its own outlets and no ice sheet wide mass rate can be "
                      "formed from it")
    nodes = sorted({(r["gate"], int(r["node"])) for r in vel})
    lacking = [k for k in nodes if k not in thick]
    if lacking:
        return None, ("term-not-in-root",
                      f"{len(lacking)} of {len(nodes)} gate nodes carry no thickness "
                      f"(the first is {lacking[0]}); a discharge is velocity times thickness")
    interpolated = sorted({thick[k]["provenance"] for k in nodes
                           if thick[k]["provenance"] not in SUPPORTED_PROVENANCE})
    if interpolated:
        counts = {p: sum(1 for k in nodes if thick[k]["provenance"] == p) for p in interpolated}
        return None, ("gate-thickness-interpolated",
                      f"the thickness at {sum(counts.values())} of {len(nodes)} nodes of "
                      f"{gate_set!r} was not made by mass conservation ({counts}); a flux "
                      "through a gate whose thickness is an interpolation is a model quantity "
                      "the method was not built to conserve, so no discharge is stated")
    ungrounded = sorted({thick[k]["mask"] for k in nodes if thick[k]["mask"] not in GROUNDED_MASK})
    if ungrounded:
        counts = {m: sum(1 for k in nodes if thick[k]["mask"] == m) for m in ungrounded}
        return None, ("gate-not-grounded",
                      f"{sum(counts.values())} of {len(nodes)} nodes of {gate_set!r} are not on "
                      f"grounded ice by the thickness product's mask ({counts}); the discharge "
                      "of an ice sheet is the flux across the grounding line, and ice crossing "
                      "a gate downstream of it has already left the grounded sheet")
    # the discharge per epoch
    by_epoch = {}
    for r in vel:
        by_epoch.setdefault(r["epoch"], {})[(r["gate"], int(r["node"]))] = r
    epochs, values, uncertainties, holes = [], [], [], {}
    per_gate = {}
    for epoch in sorted(by_epoch):
        here = by_epoch[epoch]
        missing = [k for k in nodes if k not in here or not here[k]["v_normal_m_per_yr"]]
        if missing:
            holes[epoch] = len(missing)
            continue
        total, gate_sum, gate_err = 0.0, {}, {}
        for k in nodes:
            v = here[k]
            t = thick[k]
            u = float(v["v_normal_m_per_yr"])
            w = float(v["width_m"]) / float(v["areal_scale"])
            h = float(t["thickness_m"])
            flux = density * u * w * h / 1e12
            du = float(v["v_normal_error_m_per_yr"] or 0.0)
            dh = float(t["thickness_error_m"] or 0.0)
            err = density * w * math.sqrt((du * h) ** 2 + (u * dh) ** 2) / 1e12
            total += flux
            gate_sum[k[0]] = gate_sum.get(k[0], 0.0) + flux
            gate_err[k[0]] = gate_err.get(k[0], 0.0) + err
        epochs.append(epoch)
        values.append(total)
        uncertainties.append(math.sqrt(sum(e * e for e in gate_err.values())))
        per_gate[epoch] = {g: gate_sum[g] for g in sorted(gate_sum)}
    if not epochs:
        return None, ("term-not-in-root",
                      f"no epoch of {gate_set!r} carries a velocity at every node "
                      f"({len(nodes)} nodes, {len(by_epoch)} epochs seen)")
    discharge = {"epochs": epochs, "values": values, "uncertainties": uncertainties,
                 "per_gate": per_gate, "epochs_with_holes": holes}
    # the surface mass balance over the grounded domain, aggregated by year
    domains = GROUNDED_SMB_DOMAINS[ice_sheet]
    smb_rows = [r for r in rows["smb"] if r["ice_sheet"] == ice_sheet and r["domain"] in domains]
    if not smb_rows:
        have = sorted({(r["ice_sheet"], r["domain"]) for r in rows["smb"]})
        return None, ("smb-term-missing",
                      f"the surface mass balance term carries no rows for {ice_sheet} over the "
                      f"grounded domains {list(domains)} (the root holds {have}); an "
                      "input-output balance differences a grounded discharge, so a surface mass "
                      "balance over other ice is not its input term")
    per_year = {}
    for r in smb_rows:
        per_year.setdefault(year_of(r["month"]), []).append(r)
    smb = {"epochs": [], "values": [], "uncertainties": [], "n_steps": {}, "sampling": {}}
    for year in sorted(per_year):
        steps = per_year[year]
        w = [float(s["period_years"]) for s in steps]
        tw = sum(w)
        if tw <= 0:
            continue
        smb["epochs"].append(f"{year:04d}-01")
        smb["values"].append(sum(float(s["value_gt_per_yr"]) * p for s, p in zip(steps, w)) / tw)
        smb["uncertainties"].append(
            sum(float(s["uncertainty_gt_per_yr"]) * p for s, p in zip(steps, w)) / tw)
        smb["n_steps"][f"{year:04d}-01"] = len(steps)
        smb["sampling"][f"{year:04d}-01"] = sorted({s["sampling"] for s in steps})
    return {"discharge": discharge, "smb": smb, "nodes": nodes, "thickness": thick,
            "gate_table": table, "density": density,
            "spans": {"discharge": [discharge["epochs"][0], discharge["epochs"][-1]],
                      "smb": [smb["epochs"][0], smb["epochs"][-1]] if smb["epochs"] else None},
            "domains": {"smb": list(domains), "gate_set": gate_set}}, None


def overlap(terms: dict):
    spans = [s for s in (terms["spans"]["discharge"], terms["spans"]["smb"]) if s]
    if len(spans) < 2:
        return None
    lo, hi = max(ym(s[0]) for s in spans), min(ym(s[1]) for s in spans)
    return [label(lo), label(hi)] if lo <= hi else "empty"


def gate_systematic(bookkeeping: dict, gate_set: str) -> dict:
    """The stated systematic of the gate set: half the spread of the
    full series discharges the velocity stamp recorded under the other
    gate rules, added to the bar as the closure adds its mascon
    selection systematic; zero, and said so, where the stamp recorded
    none."""
    sens = ((bookkeeping.get("gates") or {}).get(gate_set) or {}).get("discharge_sensitivity")
    values = [v.get("discharge_gt_per_yr_full_series") for v in (sens or {}).values()
              if isinstance(v, dict) and isinstance(v.get("discharge_gt_per_yr_full_series"), (int, float))]
    if len(values) >= 2:
        return {"value_gt_per_yr": 0.5 * (max(values) - min(values)),
                "basis": "half the spread of the full series discharges under the other gate "
                         "rules the velocity stamp records (discharge_sensitivity); a stated "
                         "systematic of the gate placement, added to the bar, not folded into "
                         "the noise",
                "discharges_gt_per_yr": {k: v.get("discharge_gt_per_yr_full_series")
                                         for k, v in sens.items()}}
    return {"value_gt_per_yr": 0.0,
            "basis": "no gate sensitivity recorded for this gate set in the velocity stamp (a "
                     "synthetic root, or one rule only); the systematic is stated as zero"}


def window_series(term: dict, start: str, end: str):
    k0, k1 = ym(start), ym(end)
    idx = [i for i, m in enumerate(term["epochs"]) if k0 <= ym(m) <= k1]
    return {"epochs": [term["epochs"][i] for i in idx],
            "values": [term["values"][i] for i in idx],
            "uncertainties": [term["uncertainties"][i] for i in idx]}


def compute(terms: dict, start: str, end: str, bookkeeping: dict, ice_sheet: str, gate_set: str,
            epoch_family: str):
    """(receipt body, None) or (None, (reason_code, reason)) over the window."""
    n_calendar = ym(end) - ym(start) + 1
    if n_calendar < MIN_WINDOW_MONTHS:
        return None, ("too-few-epochs", f"the window {start}:{end} spans {n_calendar} months; "
                                        f"the balance needs at least {MIN_WINDOW_MONTHS}")
    for name in ("discharge", "smb"):
        span = terms["spans"][name]
        if span is None or not (ym(span[0]) <= ym(end) and ym(start) <= ym(span[1])):
            return None, ("window-outside-epochs",
                          f"the window {start}:{end} lies outside the {name} term's epochs "
                          f"{span[0] if span else None} through {span[1] if span else None}; "
                          f"the overlap of the terms is {overlap(terms)}")
    used = {name: window_series(terms[name], start, end) for name in ("discharge", "smb")}
    common = sorted(set(used["discharge"]["epochs"]) & set(used["smb"]["epochs"]))
    if len(common) < MIN_EPOCHS:
        return None, ("too-few-epochs",
                      f"{len(common)} epochs are common to the discharge and the surface mass "
                      f"balance in {start}:{end} ({len(used['discharge']['epochs'])} discharge "
                      f"and {len(used['smb']['epochs'])} surface mass balance epochs); the "
                      f"balance needs at least {MIN_EPOCHS}")
    series = {}
    for name in ("discharge", "smb"):
        by = {m: (v, u) for m, v, u in zip(used[name]["epochs"], used[name]["values"],
                                           used[name]["uncertainties"])}
        series[name] = {"epochs": common, "values": [by[m][0] for m in common],
                        "uncertainties": [by[m][1] for m in common]}
    series["mass_rate"] = {
        "epochs": common,
        "values": [s - d for s, d in zip(series["smb"]["values"], series["discharge"]["values"])],
        "uncertainties": [math.sqrt(a * a + b * b) for a, b in
                          zip(series["smb"]["uncertainties"], series["discharge"]["uncertainties"])],
    }
    blocks = {name: mean_block(series[name]["epochs"], series[name]["values"],
                               series[name]["uncertainties"], "Gt/year")
              for name in ("discharge", "smb", "mass_rate")}
    for name in ("discharge", "smb", "mass_rate"):
        if not blocks[name]["stated"]:
            return None, ("interval-not-stated",
                          f"the {name} rate carries no interval ({blocks[name]['reason']}); a "
                          "combined uncertainty cannot be formed")
    systematic = gate_systematic(bookkeeping, gate_set)
    bar = blocks["mass_rate"]["half_width"] + systematic["value_gt_per_yr"]
    mass_rate = blocks["mass_rate"]["rate"]
    significant = abs(mass_rate) > bar
    sign = "loss" if significant and mass_rate < 0 else ("gain" if significant else "indistinguishable")
    years = n_calendar / 12.0
    calendar = [f"{y:04d}-01" for y in range(year_of(start), year_of(end) + 1)]
    missing = [m for m in calendar if m not in set(common) and ym(start) <= ym(m) <= ym(end)]
    book = json.loads(json.dumps(bookkeeping))
    book["density"] = {"ice_density_kg_m3": terms["density"],
                       "basis": "the density applied to the ice volume flux through the gate; "
                                "the default 917 kg per m3 is the density the GEMB products "
                                "themselves use, and the parameter is declared so a run may "
                                "state another"}
    book["discharge_rule"] = {
        "rule": "at each gate node the ice density times the velocity component normal to the "
                "gate times the node width divided by the projection's areal scale at the node "
                "times the thickness at the node, in gigatonnes per year; summed over every "
                "node of every gate of the set",
        "map_scale": "the velocity and the node width are both in the mosaic's map units, and "
                     "their product is the ground flux times the projection's areal scale, so "
                     "this computation divides by that scale and states the ground flux; the "
                     "velocity product's user guide instead states that a flux gate cross "
                     "section needs no correction for projection scale distortion, which is the "
                     "same number multiplied by the areal scale, and the areal scale at every "
                     "node travels in the term file so either reading can be formed",
        "node_uncertainty": "the velocity error times the thickness and the velocity times the "
                            "thickness error, in quadrature at the node; summed along a gate as "
                            "fully correlated (the products state no spatial correlation for "
                            "either error field) and combined across gates in quadrature",
        "n_nodes": len(terms["nodes"]), "n_gates": len({g for g, _ in terms["nodes"]}),
        "gate_set": gate_set,
        "thickness_epoch": "the thickness is of the thickness product's nominal year and the "
                           "velocity of each epoch's own mosaic; the discharge therefore holds "
                           "the thickness fixed while the velocity changes, and a real "
                           "thinning at the gate is not in it",
    }
    book["annualisation"] = {
        "rule": "the surface mass balance rate of a velocity epoch's calendar year is the "
                "period weighted mean of the product's time steps in that year; its uncertainty "
                "is the period weighted mean of theirs, the steps treated as fully correlated "
                "within the year",
        "steps_per_year": {m: terms["smb"]["n_steps"].get(m) for m in common},
        "sampling": {m: terms["smb"]["sampling"].get(m) for m in common},
    }
    book["epoch_handling"] = {
        "rule": "an epoch missing from a term is a hole, never interpolated; the rates are "
                "taken over the epochs both terms carry, so the mass rate at an epoch is the "
                "difference of two numbers measured in the same year",
        "velocity_epoch": epoch_family,
        "epochs_used": common,
        "years_in_the_window_without_both_terms": missing,
        "discharge_epochs_with_a_node_without_velocity": terms["discharge"]["epochs_with_holes"],
    }
    body = {
        "window": {"start": start, "end": end, "n_calendar": n_calendar, "years": years},
        "gates": {
            "gate_set": gate_set, "n_gates": book["discharge_rule"]["n_gates"],
            "n_nodes": len(terms["nodes"]),
            "spans_margin": terms["gate_table"].get("spans_margin"),
            "rule": terms["gate_table"].get("rule"),
            "grounded_by": terms["gate_table"].get("grounded_by"),
            "provenance": sorted({terms["thickness"][k]["provenance"] for k in terms["nodes"]}),
            "mask": sorted({terms["thickness"][k]["mask"] for k in terms["nodes"]}),
            "thickness_m": {
                "min": min(float(terms["thickness"][k]["thickness_m"]) for k in terms["nodes"]),
                "max": max(float(terms["thickness"][k]["thickness_m"]) for k in terms["nodes"]),
                "mean": sum(float(terms["thickness"][k]["thickness_m"]) for k in terms["nodes"])
                        / len(terms["nodes"])},
        },
        "terms": {
            "smb": {"units": "Gt/year", "domain": terms["domains"]["smb"],
                    "n_epochs": len(common), "sign": "positive is mass gained at the surface",
                    "rate_gt_per_yr": round(blocks["smb"]["rate"], 4),
                    "uncertainty_gt_per_yr": blocks["smb"]["half_width"],
                    "change_over_window_gt": blocks["smb"]["rate"] * years},
            "discharge": {"units": "Gt/year", "domain": gate_set, "n_epochs": len(common),
                          "sign": "positive is ice leaving through the gate",
                          "rate_gt_per_yr": round(blocks["discharge"]["rate"], 4),
                          "uncertainty_gt_per_yr": blocks["discharge"]["half_width"],
                          "change_over_window_gt": blocks["discharge"]["rate"] * years,
                          "rule": book["discharge_rule"]["rule"]},
            "mass_rate": {"units": "Gt/year", "domain": f"{ice_sheet} grounded ice",
                          "n_epochs": len(common),
                          "sign": "negative is mass lost by the ice sheet",
                          "rate_gt_per_yr": round(blocks["mass_rate"]["rate"], 4),
                          "uncertainty_gt_per_yr": blocks["mass_rate"]["half_width"],
                          "change_over_window_gt": blocks["mass_rate"]["rate"] * years,
                          "rule": "the surface mass balance less the discharge at each epoch, "
                                  "then the mean over the window"},
        },
        "series": series,
        "rates": blocks,
        "residual": {"rate_gt_per_yr": mass_rate,
                     "rule": "the input-output mass rate: the mean over the window of the "
                             "surface mass balance less the discharge at each epoch",
                     "n_epochs": len(common),
                     "smb_gt_per_yr": blocks["smb"]["rate"],
                     "discharge_gt_per_yr": blocks["discharge"]["rate"],
                     "change_over_window_gt": mass_rate * years},
        "combined_uncertainty": {
            "rule": "the mass rate's own half width (95 percent, the method statement on the "
                    "mass rate series: the larger of its sampling and formal errors), so the "
                    "year to year signal the two terms share does not enter the bar twice; the "
                    "gate systematic is stated separately and added to the bar, not folded in",
            "mass_rate_half_width_gt_per_yr": blocks["mass_rate"]["half_width"],
            "terms_gt_per_yr": {name: blocks[name]["half_width"] for name in ("smb", "discharge")},
            "gate_systematic": systematic, "bar_gt_per_yr": bar,
        },
        "verdict": {"significant_at_confidence": significant, "sign": sign,
                    "rule": "the mass rate is distinguishable from zero when its magnitude "
                            "exceeds its own half width plus the stated gate systematic",
                    "mass_rate_gt_per_yr": mass_rate, "bar_gt_per_yr": bar},
        "bookkeeping": book,
    }
    body["series"]["discharge_per_gate"] = {m: terms["discharge"]["per_gate"][m] for m in common}
    return body, None


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
                             "gates": args.gates, "velocity_epoch": args.velocity_epoch,
                             "ice_density": float(args.ice_density)},
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
    ap.add_argument("--ice-sheet", required=True, choices=["greenland", "antarctica"],
                    help="declared parameter")
    ap.add_argument("--window", required=True, help="YYYY-MM:YYYY-MM inclusive (declared parameter)")
    ap.add_argument("--gates", required=True, help="the gate set's name (declared parameter)")
    ap.add_argument("--velocity-epoch", default="annual", choices=list(EPOCH_FAMILIES),
                    help="the velocity epoch family (declared parameter; default annual)")
    ap.add_argument("--ice-density", type=float, default=ICE_DENSITY_DEFAULT,
                    help=f"kg per m3 applied to the gate flux (declared parameter; default "
                         f"{ICE_DENSITY_DEFAULT})")
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--fixture", action="store_true", help="the synthetic root")
    mode.add_argument("--data-root", type=Path, help="a recorded tree (execution plumbing)")
    ap.add_argument("--seed", type=int, default=7, help="fixture seed (default 7)")
    ap.add_argument("--runtime", required=True, help="the runtime that ran this (recorded verbatim)")
    ap.add_argument("--runtime-version", default=None)
    ap.add_argument("--receipt", type=Path, default=None)
    ap.add_argument("--capability-root", type=Path, default=None,
                    help="the package tree this run is evidence for (default: the bundle this "
                         "executor ships in)")
    args = ap.parse_args(argv)

    start, end = parse_window(args.window)
    if not (args.ice_density > 0):
        raise SystemExit("ice density must be positive")
    bundle = package_identity(bundle_root())
    capability = (package_identity(package_root(args.capability_root.expanduser().resolve()))
                  if args.capability_root else bundle)
    if args.fixture:
        fx = make_fixture(args.seed)
        rows, bookkeeping, absent = fx["rows"], json.loads(json.dumps(FIXTURE_BOOKKEEPING)), {}
        bookkeeping["gates"] = fixture_gate_table(fx)
        data = {"mode": "fixture", "seed": args.seed, "spans": fx["spans"],
                "digest": fixture_digest(fx), "generator": COMPUTATION + " (make_fixture)",
                "generator_sha256": sha256_file(Path(__file__).resolve()), "truth": TRUTH}
        stamps = {t: {"term": t, "granule": "synthetic"} for t in rows}
    else:
        tree = read_data_root(args.data_root)
        rows, bookkeeping, absent = tree["rows"], tree["bookkeeping"], tree["absent"]
        data = {"mode": "data-root", "data_root": tree["data_root"], "record": tree["record"],
                "record_sha256": tree["record_sha256"], "files": tree["files"]}
        stamps = tree["stamps"]
    data["gate_sets"] = {t: sorted({f"{r['ice_sheet']}/{r['gate_set']}" for r in rr})
                         for t, rr in rows.items() if t in ("velocity", "thickness")}
    data["domains"] = {"smb": sorted({f"{r['ice_sheet']}/{r['domain']}" for r in rows["smb"]})
                       if "smb" in rows else []}
    data["velocity_epoch_families"] = sorted({r.get("sampling", "annual")
                                              for r in rows.get("velocity", [])})
    terms, refusal = assemble(args.ice_sheet, args.gates, args.velocity_epoch, rows,
                              args.ice_density, bookkeeping, absent)
    if terms is not None:
        data["spans"] = {**data.get("spans", {}), "terms": terms["spans"]}
    head = receipt_head(args, capability, bundle, data)
    if refusal is None:
        body, refusal = compute(terms, start, end, bookkeeping, args.ice_sheet, args.gates,
                                args.velocity_epoch)
    if refusal:
        receipt = finish({**head, "refused": True, "reason_code": refusal[0], "reason": refusal[1]})
        print(f"REFUSED ({refusal[0]}): {refusal[1]}")
        write(receipt, args.receipt)
        return 3
    for name, key in (("smb", "smb"), ("discharge", "velocity"), ("mass_rate", "velocity")):
        body["terms"][name]["stamp"] = {"term": key,
                                        **{k: v for k, v in (stamps.get(key) or {}).items()
                                           if k != "term"}}
    body["terms"]["discharge"]["thickness_stamp"] = {
        "term": "thickness", **{k: v for k, v in (stamps.get("thickness") or {}).items()
                                if k != "term"}}
    receipt = finish({**head, "refused": False, **body, "caveats": [
        ("a fixture run proves the chain, not the ice sheet; the real-data anchor is the stamped "
         "data root run the concept records") if args.fixture else
        ("a real-data run on a stamped root: each loader's stamp in the root states the product, "
         "the mask, the gate rule and the uncertainty basis"),
        "the series travel at full precision so every rate, interval, the mass rate, the bar and "
        "the verdict are recomputable from the receipt",
        "the discharge is a flux through one gate set at one thickness epoch; it is the ice "
        "sheet's discharge only where the gate set spans its grounded margin, which the record's "
        "gate table states and this computation refuses without",
        "the interval is a statement about sampling under an AR(1) model on the epochs used; "
        "product systematics (the thickness method and its error, the velocity mosaic's "
        "composite date, the surface mass balance model and its forcing) enter through the "
        "bookkeeping table, not the bar",
        "the input-output rate is one of three estimates of the same mass rate; the gravimetric "
        "and altimetric estimates of the ice sheet mass balance closure are the other two, and "
        "the concept reads all three against the published assessment",
    ]})
    v = receipt["verdict"]
    where = f"fixture seed {args.seed}" if args.fixture else f"data root {data['data_root']}"
    for name in ("smb", "discharge", "mass_rate"):
        b = receipt["rates"][name]
        band = (f"95% [{b['ci_low']:+.3f}, {b['ci_high']:+.3f}] (r1 {b['r1']:+.3f}, n_eff "
                f"{b['n_eff']:.1f} of {b['n_epochs']}, {b['se_basis']} error)"
                if b["stated"] else f"no interval: {b['reason']}")
        print(f"rate {name} {b['rate']:+.3f} {b['units']}, {band}", file=sys.stderr)
    print(f"ice sheet input-output {args.ice_sheet} {start}:{end} (gates {args.gates}, "
          f"{args.velocity_epoch}) on {where}: surface mass balance "
          f"{receipt['terms']['smb']['rate_gt_per_yr']:+.3f} Gt/yr, discharge "
          f"{receipt['terms']['discharge']['rate_gt_per_yr']:+.3f} Gt/yr, mass rate "
          f"{v['mass_rate_gt_per_yr']:+.3f} against a bar of {v['bar_gt_per_yr']:.3f} (half width "
          f"{receipt['combined_uncertainty']['mass_rate_half_width_gt_per_yr']:.3f} plus gate "
          f"systematic {receipt['combined_uncertainty']['gate_systematic']['value_gt_per_yr']:.3f}); "
          f"significant_at_confidence {str(v['significant_at_confidence']).lower()} ({v['sign']}); "
          f"run {receipt['run_id']}")
    write(receipt, args.receipt)
    return 0


if __name__ == "__main__":
    sys.exit(main())
