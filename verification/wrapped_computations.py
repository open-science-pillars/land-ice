#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Golden and PROVE wrapper for this capability's wrapping skills: the
sanctioned executors and attesters of the NSIDC bundle, run on the
bundle's synthetic fixtures and on its committed data roots, so every
chain a skill here wraps is proven headless with no data download and
no NASA host reachable.

Nothing scientific is reimplemented. The computations live in the
provider bundle under knowledge/nsidc/references/, under the contracts
knowledge/nsidc/computations/ice-sheet-balance.md and
knowledge/nsidc/computations/ice-sheet-input-output.md; the expected
values are quoted from those concepts' reference runs and committed
beside this file under fixtures/ (provenance in the README there).
The bundle root is resolved the way the skills resolve it:
NASA_DAAC_KNOWLEDGE names a checkout of the provider repository, else
the installer's record (`claude plugin list --json`, the entry's
installPath) names the installed plugin.

For each chain, and in the order a skill follows: run the executor on
the fixture with every declared parameter bound and the runtime named;
attest the receipt and require PASS; only then read the receipt and
compare it with what the concept records; then run the chain's fixture
refusal case and require exit 3 and an attestation that passes it as a
refusal; then run the chain on the bundle's committed data root and
require the refusal the concept records there, attested against the
tree.

Both record runs refuse, and the golden asserts a refusal rather than
a number for each. The closure refuses Antarctica for want of a
grounded firn air content term, which is a finding about the data. The
input-output computation's record run refuses because its thickness
term is not in the root, so no real-data estimate by that method
exists yet; the fixture chain is what proves the method.

Three modes:

  (no flags)                 the golden: both chains, both fixture
                             refusals, both record refusals. Exit 0
                             only when all of it holds.
  --runtime NAME --out R     the PROVE step: run the ice mass change
                             chain's fixture computation and write the
                             receipt at R, the capability block naming
                             this package and the bundle block naming
                             the provider bundle.
  --attest R --out A         run the matching bundle attester on receipt
                             R and write the attestation at A. Exit 0 on
                             PASS.
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
PACKAGE_ROOT = HERE.parent
FIXTURE = HERE / "fixtures" / "wrapped_computations.json"
PROVIDER_PLUGIN = "nasa-daac-knowledge"
BUNDLE = "nsidc"
PACKAGE = "land-ice"
PROVE_SKILL = "ice-mass-change"


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


def chains() -> list[dict]:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))["chains"]


def bundle_root() -> Path:
    return provider_root() / "knowledge" / BUNDLE


def concept_status(chain: dict) -> str:
    """The status the provider concept itself carries.

    The fixture records the word the golden prints beside each chain.
    A concept is promoted in the provider bundle, not here, so that
    word goes stale the moment a draft is signed, and a golden that
    only printed it would keep saying draft forever. Reading the
    concept's own frontmatter and failing on a disagreement is what
    stops the fixture from lying about a status the way it cannot lie
    about a number."""
    path = bundle_root() / chain["concept"].split(f"knowledge/{BUNDLE}/", 1)[1]
    if not path.is_file():
        sys.exit(f"the provider bundle carries no concept at {path}")
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0].strip() != "---":
        sys.exit(f"{path} opens with no frontmatter")
    for line in lines[1:]:
        if line.strip() == "---":
            break
        if line.startswith("status:"):
            return line.split(":", 1)[1].strip()
    sys.exit(f"{path} carries no status key in its frontmatter")


def chain_paths(chain: dict) -> tuple[Path, Path]:
    root = bundle_root()
    computation = root / chain["executor"]
    attester = root / chain["attester"]
    for p in (computation, attester):
        if not p.is_file():
            sys.exit(f"the provider bundle carries no {p.name} at {p.parent}; "
                     f"the {chain['skill']} chain needs {PROVIDER_PLUGIN} at a "
                     "release that ships it")
    return computation, attester


def run_computation(computation: Path, chain: dict, args: list[str], receipt: Path,
                    runtime: str, runtime_version=None,
                    data_root: Path | None = None) -> subprocess.CompletedProcess:
    source = ["--data-root", str(data_root)] if data_root is not None \
        else ["--fixture", "--seed", str(chain["seed"])]
    cmd = ["uv", "run", str(computation), *source, *args,
           "--runtime", runtime, "--capability-root", str(PACKAGE_ROOT),
           "--receipt", str(receipt)]
    if runtime_version:
        cmd += ["--runtime-version", runtime_version]
    return subprocess.run(cmd, capture_output=True, text=True)


def run_attester(attester: Path, receipt: Path, out: Path | None = None,
                 data_root: Path | None = None) -> subprocess.CompletedProcess:
    cmd = ["uv", "run", str(attester), str(receipt)]
    if data_root is not None:
        cmd += ["--data-root", str(data_root)]
    if out is not None:
        cmd += ["--out", str(out)]
    return subprocess.run(cmd, capture_output=True, text=True)


def last_line(p: subprocess.CompletedProcess) -> str:
    text = (p.stdout or "").strip() or (p.stderr or "").strip()
    return text.splitlines()[-1] if text else ""


def close(got: float, want: float, tol: float, what: str) -> None:
    assert abs(got - want) <= tol, f"{what}: {got!r} is not {want!r} within {tol}"


def check_receipt(chain: dict, receipt: dict) -> None:
    """The receipt against what the concept records. Read only after the
    attester has passed it, which is the discipline the skills state."""
    skill = chain["skill"]
    expect = chain["expect"]
    tol = expect["tolerance"]

    # Every declared parameter the skill binds is bound in the receipt.
    assert receipt["bound_parameters"] == chain["bound_parameters"], (
        f"{skill}: bound parameters {receipt['bound_parameters']} are not the "
        f"declared {chain['bound_parameters']}")
    assert receipt["refused"] is False, f"{skill}: the reference run refused"
    assert receipt["runtime"]["name"], f"{skill}: the receipt names no runtime"
    # The run identifier under a fixed runtime name pins the executor's own
    # code: an edit to it that changes no number still moves the identifier,
    # which a golden that only re-ran the chain would never see. The name is
    # always "goldens" here, so the value is stable and worth asserting.
    assert receipt["run_id"] == chain["goldens_run_id"], (
        f"{skill}: run identifier {receipt['run_id']} is not the "
        f"{chain['goldens_run_id']} this fixture records; the executor or its "
        "inputs moved")
    assert receipt["capability"]["name"] == PACKAGE, (
        f"{skill}: the capability block names {receipt['capability']['name']!r}, "
        "not this package")
    assert receipt["bundle"]["name"] == PROVIDER_PLUGIN, (
        f"{skill}: the bundle block names {receipt['bundle']['name']!r}")

    assert receipt["window"]["n_calendar"] == expect["months_in_window"], (
        f"{skill}: months in window")
    for term, n in expect["term_epochs"].items():
        assert receipt["terms"][term]["n_epochs"] == n, (
            f"{skill}: {term} epochs {receipt['terms'][term]['n_epochs']} is not {n}")

    # Each rate with the interval the concept records, not the rate alone:
    # the interval is what the concept's boundaries argue about.
    for term, want in expect["rates"].items():
        got = receipt["rates"][term]
        close(got["rate"], want["rate"], tol, f"{skill} {term} rate")
        close(got["ci_low"], want["ci_low"], tol, f"{skill} {term} interval low")
        close(got["ci_high"], want["ci_high"], tol, f"{skill} {term} interval high")

    close(receipt["residual"]["rate_gt_per_yr"], expect["residual"], tol,
          f"{skill} residual")
    close(receipt["combined_uncertainty"]["bar_gt_per_yr"], expect["bar"], tol,
          f"{skill} bar")

    field = expect["verdict_field"]
    assert receipt["verdict"][field] is expect["verdict"], (
        f"{skill}: verdict {field} is {receipt['verdict'][field]!r}")
    if "sign" in expect:
        assert receipt["verdict"]["sign"] == expect["sign"], (
            f"{skill}: the verdict's sign is {receipt['verdict']['sign']!r}")

    # The closure's residual is formed on the epochs both methods carry.
    if "n_common_differences" in expect:
        assert receipt["residual"]["n_common_differences"] == expect["n_common_differences"], (
            f"{skill}: common differences")

    # The input-output discharge is a flux through a named gate set, and
    # the set spans the grounded margin or the computation refuses.
    if "gates" in expect:
        for key, want in expect["gates"].items():
            assert receipt["gates"][key] == want, (
                f"{skill}: the gate block's {key} is {receipt['gates'][key]!r}, not {want!r}")

    assert receipt["caveats"], f"{skill}: the receipt states no caveats"


def refusal_case(chain: dict, computation: Path, attester: Path, case: dict,
                 receipt_path: Path, data_root: Path | None) -> str:
    """Run one refusal case and return the attester's verdict line.

    A refusal is never a number: exit 3, a refusal receipt carrying the
    reason code the concept records, and an attestation that passes it as
    a refusal.
    """
    skill = chain["skill"]
    run = run_computation(computation, chain, case["args"], receipt_path,
                          "goldens", data_root=data_root)
    if run.returncode != 3:
        raise AssertionError(f"the refusal case exited {run.returncode}, not 3: "
                             f"{last_line(run)}")
    body = json.loads(receipt_path.read_text(encoding="utf-8"))
    if body.get("refused") is not True or body.get("reason_code") != case["reason_code"]:
        raise AssertionError(f"the refusal is {body.get('reason_code')!r}, not "
                             f"{case['reason_code']!r}")
    if not body.get("reason"):
        raise AssertionError("the refusal receipt states no reason in words")
    att = run_attester(attester, receipt_path, data_root=data_root)
    line = last_line(att)
    if att.returncode != 0 or not line.startswith("PASS refusal"):
        raise AssertionError(f"{skill}: the refusal did not attest as a refusal: {line}")
    return line


def golden() -> int:
    failures = []
    root = bundle_root()
    for chain in chains():
        skill = chain["skill"]
        computation, attester = chain_paths(chain)
        live = concept_status(chain)
        if live != chain["concept_status"]:
            failures.append(f"{skill}: the fixture says the concept is "
                            f"{chain['concept_status']} and "
                            f"{chain['concept']} says {live}")
            continue
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            receipt_path = tmp / "receipt.json"
            run = run_computation(computation, chain, chain["args"], receipt_path, "goldens")
            if run.returncode != 0:
                failures.append(f"{skill}: the fixture run exited {run.returncode}: {last_line(run)}")
                continue
            att = run_attester(attester, receipt_path)
            if att.returncode != 0:
                failures.append(f"{skill}: the attester did not pass the receipt: {last_line(att)}")
                continue
            verdict = last_line(att)
            try:
                check_receipt(chain, json.loads(receipt_path.read_text(encoding="utf-8")))
            except AssertionError as bad:
                failures.append(f"{skill}: {bad}")
                continue
            print(f"== {skill} wraps {chain['concept']} ({chain['concept_status']})")
            print(f"   bound {chain['bound_parameters']}")
            print(f"   {verdict}")

            refusal = chain["refusal"]
            try:
                line = refusal_case(chain, computation, attester, refusal,
                                    tmp / "refusal.json", None)
            except AssertionError as bad:
                failures.append(f"{skill}: fixture refusal: {bad}")
                continue
            print(f"   fixture refusal {refusal['reason_code']}: exit 3, "
                  f"{line.split(' run ')[0]}")

            record = chain["record"]
            data_root = root / record["data_root"]
            if not data_root.is_dir():
                failures.append(f"{skill}: the provider bundle carries no committed root "
                                f"at {data_root}")
                continue
            try:
                line = refusal_case(chain, computation, attester, record,
                                    tmp / "record.json", data_root)
            except AssertionError as bad:
                failures.append(f"{skill}: record run: {bad}")
                continue
            print(f"   record refusal {record['reason_code']}: exit 3, "
                  f"{line.split(' run ')[0]}")
            print(f"   {record['about']}")
    for bad in failures:
        print(f"FAIL {bad}", file=sys.stderr)
    if failures:
        return 1
    print(f"wrapped computations: {len(chains())} chains, each run, attested, refused on its "
          "fixture and refused on the bundle's committed root as the concept records")
    return 0


def prove(runtime: str, runtime_version: str | None, out: Path) -> int:
    chain = next(c for c in chains() if c["skill"] == PROVE_SKILL)
    computation, _ = chain_paths(chain)
    run = run_computation(computation, chain, chain["args"], out, runtime, runtime_version)
    print((run.stdout or "") + (run.stderr or ""), end="")
    return run.returncode


def attest(receipt_path: Path, out: Path) -> int:
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    computation = receipt.get("computation", "")
    chain = next((c for c in chains() if c["executor"] == computation), None)
    if chain is None:
        sys.exit(f"no wrapping skill here runs {computation!r}")
    _, attester = chain_paths(chain)
    att = run_attester(attester, receipt_path, out)
    print((att.stdout or "") + (att.stderr or ""), end="")
    return att.returncode


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--runtime", help="the runtime that ran this (PROVE)")
    ap.add_argument("--runtime-version")
    ap.add_argument("--attest", metavar="RECEIPT", help="attest this receipt")
    ap.add_argument("--out", metavar="PATH", help="where the receipt or attestation is written")
    args = ap.parse_args()
    if args.attest:
        if not args.out:
            ap.error("--attest needs --out")
        return attest(Path(args.attest), Path(args.out))
    if args.runtime:
        if not args.out:
            ap.error("--runtime needs --out")
        return prove(args.runtime, args.runtime_version, Path(args.out))
    return golden()


if __name__ == "__main__":
    sys.exit(main())
