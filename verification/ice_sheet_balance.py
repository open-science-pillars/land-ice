#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Golden and qualification prove step for the attested ice sheet mass
balance closure this package runs: the executor, the attester and the
six loaders in the scripts of the `ice-mass-change` skill, run on their
synthetic fixture and on the stamped data root committed under
knowledge/references/retrieval/, so every chain the concept records is
proven headless with no data download and no NASA host reachable.

Nothing scientific is reimplemented here. The contract is
knowledge/computations/ice-sheet-balance.md in this package; the
expected values are quoted from that concept's Reference run and
Boundaries sections and committed beside this file under fixtures/
(provenance in the README there).

The scripts this golden proves, every one the concept names:

  skills/ice-mass-change/scripts/ice_sheet_balance.py        the executor
  skills/ice-mass-change/scripts/ice_sheet_balance_check.py  the attester
  skills/ice-mass-change/scripts/isb_data_root.py            the stamp assembler
  skills/ice-mass-change/scripts/isb_mass_mascons.py         the mascon term
  skills/ice-mass-change/scripts/isb_volume_itslive.py       the ITS_LIVE volume term
  skills/ice-mass-change/scripts/isb_volume_atl15.py         the ATL15 volume term
  skills/ice-mass-change/scripts/isb_firn_gemb.py            the firn air term
  skills/ice-mass-change/scripts/isb_smb_gemb.py             the surface mass balance term

and the tree they wrote,
knowledge/references/retrieval/ice-sheet-balance-root.

What it runs, and in the order a reader checks it:

  1. the attester's own selftest, and each loader's selftest;
  2. the committed data root against its RECORD.json manifest;
  3. each fixture run with every declared parameter bound and the
     runtime named: the executor, then the attester with PASS
     required, and only then the receipt read and compared with what
     the concept records;
  4. each run on the committed data root, the same way, attested
     against the tree with --data-root;
  5. each refusal the concept records: exit 3, a refusal receipt
     carrying the reason code, and an attestation that passes it as a
     refusal. The fixture refusal is the window outside the terms'
     overlap; the record refusal is Antarctica, for want of a grounded
     firn air content term, which is a finding about the data.

Three modes:

  (no flags)                 the golden: the selftests, the root check,
                             ten runs and two refusals. Exit 0 only
                             when all of it holds.
  --runtime NAME --out R     the qualification prove step
                             (.osp/surfaces.yaml): run the closure on
                             its fixture and write the receipt at R, the
                             capability and bundle blocks naming this
                             package.
  --attest R --out A         run the attester on receipt R and write
                             the attestation at A. Exit 0 on PASS.
"""

import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
PACKAGE_ROOT = HERE.parent
FIXTURE = HERE / "fixtures" / "ice_sheet_balance.json"
PROVE_RUN = "ice-sheet-balance-long"


def spec() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def in_package(rel: str) -> Path:
    path = (PACKAGE_ROOT / rel).resolve()
    if not path.exists():
        sys.exit(f"this package carries nothing at {rel}; the golden proves the "
                 "scripts the concept names, and one of them is not there")
    return path


def sha256_file(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def concept_status(s: dict) -> str:
    """The status the concept itself carries.

    The fixture records the word the golden prints beside the chain. A
    concept is promoted by the maintainer's signature, not here, so the
    word goes stale the moment a draft is signed, and a golden that only
    printed it would keep saying draft forever. Reading the concept's own
    frontmatter and failing on a disagreement is what stops the fixture
    from lying about a status the way it cannot lie about a number."""
    path = in_package(s["concept"])
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0].strip() != "---":
        sys.exit(f"{path} opens with no frontmatter")
    for line in lines[1:]:
        if line.strip() == "---":
            break
        if line.startswith("status:"):
            return line.split(":", 1)[1].strip()
    sys.exit(f"{path} carries no status key in its frontmatter")


def run_computation(s: dict, args: list[str], receipt: Path, runtime: str,
                    runtime_version=None, mode: str = "fixture") -> subprocess.CompletedProcess:
    source = ["--data-root", str(in_package(s["data_root"]))] if mode == "data-root" \
        else ["--fixture", "--seed", str(s["seed"])]
    cmd = ["uv", "run", str(in_package(s["executor"])), *source, *args,
           "--runtime", runtime, "--capability-root", str(PACKAGE_ROOT),
           "--receipt", str(receipt)]
    if runtime_version:
        cmd += ["--runtime-version", runtime_version]
    return subprocess.run(cmd, capture_output=True, text=True)


def run_attester(s: dict, receipt: Path, out: Path | None = None,
                 mode: str = "fixture") -> subprocess.CompletedProcess:
    cmd = ["uv", "run", str(in_package(s["attester"])), str(receipt)]
    if mode == "data-root":
        cmd += ["--data-root", str(in_package(s["data_root"]))]
    if out is not None:
        cmd += ["--out", str(out)]
    return subprocess.run(cmd, capture_output=True, text=True)


def last_line(p: subprocess.CompletedProcess) -> str:
    text = (p.stdout or "").strip() or (p.stderr or "").strip()
    return text.splitlines()[-1] if text else ""


def close(got: float, want: float, tol: float, what: str) -> None:
    assert abs(got - want) <= tol, f"{what}: {got!r} is not {want!r} within {tol}"


def check_receipt(s: dict, run: dict, receipt: dict) -> None:
    """The receipt against what the concept records. Read only after the
    attester has passed it, which is the discipline the skill states."""
    name = run["name"]
    e = run["expect"]
    tol = e["tolerance"]

    assert receipt["bound_parameters"] == run["bound_parameters"], (
        f"{name}: bound parameters {receipt['bound_parameters']} are not the "
        f"declared {run['bound_parameters']}")
    assert receipt["refused"] is False, f"{name}: the reference run refused"
    assert receipt["runtime"]["name"], f"{name}: the receipt names no runtime"
    assert receipt["run_id"].startswith("sha256:"), f"{name}: no run identifier"
    # The executor's own digest, which the numbers cannot cover: an edit that
    # changes no number, a comment or a rename, still moves it, and a golden
    # that only re-ran the chain and compared numbers would never see it. The
    # run identifier is not what to assert here: it binds the runtime name and
    # the package-relative data root, so it differs between two runtimes. The
    # digest does not.
    assert receipt["code_sha256"] == s["executor_sha256"], (
        f"{name}: the executor digest {receipt['code_sha256']} is not the "
        f"{s['executor_sha256']} this fixture records; the executor moved")
    assert receipt["computation"] == s["executor"], (
        f"{name}: the receipt names the computation {receipt['computation']!r}, "
        f"not {s['executor']!r}")
    for block in ("capability", "bundle"):
        assert receipt[block]["name"] == "land-ice", (
            f"{name}: the {block} block names {receipt[block]['name']!r}, not this package")

    assert receipt["window"]["n_calendar"] == e["months_in_window"], f"{name}: months in window"
    for term, n in e["term_epochs"].items():
        assert receipt["terms"][term]["n_epochs"] == n, (
            f"{name}: {term} epochs {receipt['terms'][term]['n_epochs']} is not {n}")
    assert receipt["residual"]["n_common_differences"] == e["n_common_differences"], (
        f"{name}: common differences")

    # Each rate with the interval the concept records, not the rate alone:
    # the interval is what the concept's boundaries argue about.
    for term, want in e["rates"].items():
        got = receipt["rates"][term]
        close(got["rate"], want["rate"], tol, f"{name} {term} rate")
        close(got["ci_low"], want["ci_low"], tol, f"{name} {term} interval low")
        close(got["ci_high"], want["ci_high"], tol, f"{name} {term} interval high")

    close(receipt["residual"]["rate_gt_per_yr"], e["residual"], tol, f"{name} residual")
    close(receipt["verdict"]["bar_gt_per_yr"], e["bar"], tol, f"{name} bar")
    field = e["verdict_field"]
    assert receipt["verdict"][field] is e["verdict"], (
        f"{name}: verdict {field} is {receipt['verdict'][field]!r}, not {e['verdict']!r}")
    assert receipt["caveats"], f"{name}: the receipt states no caveats"


def refusal_case(s: dict, case: dict, receipt_path: Path) -> str:
    """Run one refusal case and return the attester's verdict line.

    A refusal is never a number: exit 3, a refusal receipt carrying the
    reason code the concept records, and an attestation that passes it as
    a refusal."""
    mode = case["mode"]
    run = run_computation(s, case["args"], receipt_path, "goldens", mode=mode)
    if run.returncode != 3:
        raise AssertionError(f"the refusal case exited {run.returncode}, not 3: {last_line(run)}")
    body = json.loads(receipt_path.read_text(encoding="utf-8"))
    if body.get("refused") is not True or body.get("reason_code") != case["reason_code"]:
        raise AssertionError(f"the refusal is {body.get('reason_code')!r}, not "
                             f"{case['reason_code']!r}")
    if not body.get("reason"):
        raise AssertionError("the refusal receipt states no reason in words")
    att = run_attester(s, receipt_path, mode=mode)
    line = last_line(att)
    if att.returncode != 0 or not line.startswith("PASS refusal"):
        raise AssertionError(f"the refusal did not attest as a refusal: {line}")
    return line


def selftests(s: dict, failures: list[str]) -> None:
    scripts = in_package(s["executor"]).parent
    for name in s["selftests"]:
        p = subprocess.run(["uv", "run", str(scripts / name), "--selftest"],
                           capture_output=True, text=True)
        if p.returncode != 0:
            failures.append(f"{name} --selftest exited {p.returncode}: {last_line(p)}")
        else:
            print(f"   selftest {name}: {last_line(p)}")


def data_root_check(s: dict, failures: list[str]) -> None:
    check = s["data_root_check"]
    scripts = in_package(s["executor"]).parent
    p = subprocess.run(["uv", "run", str(scripts / check["script"]),
                        "--root", str(in_package(s["data_root"])), "--check"],
                       capture_output=True, text=True)
    line = last_line(p)
    if p.returncode != 0 or check["expect"] not in line:
        failures.append(f"{check['script']} --check on the committed root: {line}")
    else:
        print(f"   data root {s['data_root']}: {line}")


def digests(s: dict, failures: list[str]) -> None:
    for key in ("executor", "attester"):
        got = sha256_file(in_package(s[key]))
        if got != s[f"{key}_sha256"]:
            failures.append(f"the {key} {s[key]} hashes {got}, not the "
                            f"{s[f'{key}_sha256']} this fixture records")


def golden() -> int:
    s = spec()
    failures: list[str] = []
    live = concept_status(s)
    if live != s["concept_status"]:
        failures.append(f"the fixture says the concept is {s['concept_status']} and "
                        f"{s['concept']} says {live}")
    digests(s, failures)
    print(f"== {s['skill']} runs {s['concept']} ({s['concept_status']})")
    selftests(s, failures)
    data_root_check(s, failures)

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        for run in s["runs"]:
            name, mode = run["name"], run["mode"]
            receipt_path = tmp / f"{name}.json"
            p = run_computation(s, run["args"], receipt_path, "goldens", mode=mode)
            if p.returncode != 0:
                failures.append(f"{name}: the run exited {p.returncode}: {last_line(p)}")
                continue
            att = run_attester(s, receipt_path, mode=mode)
            if att.returncode != 0:
                failures.append(f"{name}: the attester did not pass the receipt: {last_line(att)}")
                continue
            verdict = last_line(att)
            try:
                check_receipt(s, run, json.loads(receipt_path.read_text(encoding="utf-8")))
            except AssertionError as bad:
                failures.append(f"{name}: {bad}")
                continue
            print(f"   {mode} {name}: {verdict}")

        for case in s["refusals"]:
            try:
                line = refusal_case(s, case, tmp / f"{case['name']}.json")
            except AssertionError as bad:
                failures.append(f"{case['name']}: {bad}")
                continue
            print(f"   {case['mode']} refusal {case['name']} "
                  f"({case['reason_code']}): exit 3, {line.split(' run ')[0]}")

    for bad in failures:
        print(f"FAIL {bad}", file=sys.stderr)
    if failures:
        return 1
    print(f"ice sheet balance: {len(s['selftests'])} selftests, the committed root's manifest, "
          f"{len(s['runs'])} runs each attested and compared with the concept, and "
          f"{len(s['refusals'])} refusals each attested as a refusal")
    return 0


def prove(runtime: str, runtime_version: str | None, out: Path) -> int:
    s = spec()
    run = next(r for r in s["runs"] if r["name"] == PROVE_RUN)
    p = run_computation(s, run["args"], out, runtime, runtime_version, mode=run["mode"])
    print((p.stdout or "") + (p.stderr or ""), end="")
    return p.returncode


def attest(receipt_path: Path, out: Path) -> int:
    s = spec()
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    if receipt.get("computation") != s["executor"]:
        sys.exit(f"this golden does not run {receipt.get('computation')!r}")
    mode = "data-root" if (receipt.get("data") or {}).get("mode") == "data-root" else "fixture"
    att = run_attester(s, receipt_path, out, mode=mode)
    print((att.stdout or "") + (att.stderr or ""), end="")
    return att.returncode


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--runtime", help="the runtime that ran this (the prove step)")
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
