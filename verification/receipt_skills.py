#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Golden for this capability's three receipt skills: `sweep`,
`receipt-figures` and `methods`, each run offline on the nsidc closure
executor's synthetic fixture and checked against the expectations
committed beside this file.

A receipt skill computes nothing of its own (ADR D in the marketplace
repository's docs/decisions, as amended, and the specification's
section 12.1): every number it emits is a field of a receipt the
attester passed, or a table, figure or paragraph made of such fields,
and it combines no two receipts into a value no receipt carries. Its
script enforces that rather than its prose, so this golden checks the
enforcement and not only the output.

Nothing scientific is reimplemented here and nothing is downloaded: the
sanctioned executor and attester live in the provider bundle under
knowledge/nsidc/references/, under the contract
knowledge/nsidc/computations/ice-sheet-balance.md, and the executor's
synthetic fixture is generated at run time from the seed the
expectations file names, so this golden is headless and offline with no
NASA host reachable. The bundle root is resolved by each skill's own
script the way the wrapping skills resolve it: NASA_DAAC_KNOWLEDGE
names a checkout of the provider repository, else the installer's
record.

What is checked, in order:

  1. each script's own selftest, which exercises every refusal that
     script enforces on the executor's fixture;
  2. the sweep over the concept's declared `window`, cell by cell
     against verification/fixtures/receipt_skills.json (each cell a
     field of a receipt, measured when that file was written);
  3. the sweep over the concept's declared `ice_sheet`, where
     Antarctica refuses for want of a grounded firn air content term:
     the refusal is a row carrying its reason code and no number;
  4. the aggregate a reader asks for first, the Greenland mass balance
     in gigatonnes per year across the rows, refused with its reason
     code and leaving no partial table;
  5. both figure modes drawn from the first receipt of that sweep, each
     caption carrying the run identifier, the code digest and the
     verdict, and the map mode refused because these receipts carry no
     per-cell fields;
  6. the methods paragraph and reference list written from the same
     receipt, carrying every bookkeeping statement the receipt records
     and every source the concept lists, and a fact from outside both
     refused;
  7. a receipt the attester does not pass: a failed row in the sweep
     with the attester's own line and no number, refused by the
     renderer and refused by the methods writer.

Exit 0 only when all of it holds.

  uv run verification/receipt_skills.py
"""

import json
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
PACKAGE_ROOT = HERE.parent
SWEEP = PACKAGE_ROOT / "skills" / "sweep" / "scripts" / "sweep.py"
FIGURE = PACKAGE_ROOT / "skills" / "receipt-figures" / "scripts" / "receipt_figure.py"
METHODS = PACKAGE_ROOT / "skills" / "methods" / "scripts" / "methods.py"
EXPECTATIONS = HERE / "fixtures" / "receipt_skills.json"
TOLERANCE = 1e-9


def run(script: Path, args):
    return subprocess.run(["uv", "run", str(script), *args],
                          capture_output=True, text=True, cwd=PACKAGE_ROOT)


def same(got, want) -> bool:
    if isinstance(want, float) or isinstance(got, float):
        if got is None or want is None:
            return got is want
        return abs(float(got) - float(want)) <= TOLERANCE * max(1.0, abs(float(want)))
    return got == want


def fail(message: str) -> int:
    print(f"receipt-skills golden: {message}")
    return 1


def selftests() -> int | None:
    """Each script's own selftest. A refusal a script enforces is
    exercised there, on the executor's fixture, and this golden fails
    where one of them stops holding."""
    for name, script, marker in (
        ("sweep", SWEEP, "sweep selftest: ok"),
        ("receipt-figures", FIGURE, "receipt-figures selftest: ok"),
        ("methods", METHODS, "methods selftest: ok"),
    ):
        if not script.is_file():
            return fail(f"no {name} script at {script}")
        done = run(script, ["--selftest"])
        line = (done.stdout or "").strip() or (done.stderr or "").strip()
        print(line.splitlines()[-1] if line else "")
        if done.returncode != 0 or marker not in (done.stdout or ""):
            print((done.stdout or "").strip())
            print((done.stderr or "").strip())
            return fail(f"the {name} script's selftest FAILED")
    return None


def check_sweep(spec, expect_columns, work: Path, out_dir: Path):
    """One sweep against its recorded rows. Returns (manifest, message);
    the message is None where every cell holds."""
    common = ["--computation", spec["computation"],
              "--parameter", spec["parameter"],
              *[f"--fixed={name}={value}" for name, value in spec["fixed"].items()],
              "--input", "fixture", "--seed", str(EXPECT["input"]["seed"]),
              "--runtime", "golden", "--capability-root", str(PACKAGE_ROOT)]
    if "windows" in spec:
        common += ["--windows", spec["windows"], "--span", spec["span"]]
    else:
        common += ["--values", spec["values"]]
    done = run(SWEEP, [*common, "--out-dir", str(out_dir)])
    if done.returncode != 0:
        print((done.stdout or "").strip())
        print((done.stderr or "").strip())
        return None, common, (f"the {spec['parameter']} sweep exited "
                              f"{done.returncode}; every receipt of this sweep "
                              "attests, so anything but 0 is a finding")
    doc = json.loads((out_dir / "sweep.json").read_text(encoding="utf-8"))

    if doc["code_sha256"] != EXPECT["code_sha256"]:
        return doc, common, (
            f"the executor in the installed bundle is {doc['code_sha256']}, not "
            f"the {EXPECT['code_sha256']} these expectations were measured "
            "with; the table is a different method, so re-measure "
            f"{EXPECTATIONS.relative_to(PACKAGE_ROOT)} and record the new "
            "digest rather than loosening this check")
    if doc["input"]["digest"] != EXPECT["input"]["digest"]:
        return doc, common, ("the regenerated fixture does not hash to the "
                             "digest the expectations were measured on")
    if doc["values_rule"] != spec["values_rule"]:
        return doc, common, (f"the values rule is {doc['values_rule']!r}, not "
                             f"{spec['values_rule']!r}")
    got_columns = [column["name"] for column in doc["columns"]]
    if got_columns != expect_columns:
        return doc, common, f"the columns are {got_columns}, not {expect_columns}"

    rows = doc["rows"]
    counts = spec["expect"]
    if len(rows) != counts["rows"]:
        return doc, common, (f"{len(rows)} rows, not the {counts['rows']} the "
                             "expectations record")
    for got, want in zip(rows, spec["rows"]):
        where = f"{spec['parameter']} {want['value']}"
        if got["value"] != want["value"]:
            return doc, common, f"a row is {got['value']}, not {want['value']}"
        if not got["attested"]:
            return doc, common, (f"the receipt at {where} did not attest: "
                                 f"{got['attestation']}")
        if got["status"] != want["status"]:
            return doc, common, f"{where} is {got['status']}, not {want['status']}"
        if got["reason_code"] != want["reason_code"]:
            return doc, common, (f"{where} refused with {got['reason_code']}, "
                                 f"not {want['reason_code']}")
        if not got["run_id"]:
            return doc, common, f"{where} carries no run id to follow back"
        if got["status"] == "refused":
            if "PASS refusal" not in (got["attestation"] or ""):
                return doc, common, (f"the refused row {where} did not attest "
                                     f"as a refusal: {got['attestation']}")
            # A refused row still states what the run was bound to, and a
            # binding may be a number (the ice density is 917). Those are
            # the run's own parameters, not its results; what a refusal
            # must never carry is a measured column.
            bound = {column["name"] for column in doc["columns"]
                     if column["receipt_field"].startswith("bound_parameters.")}
            numbers = [name for name, cell in got["cells"].items()
                       if name not in bound
                       and isinstance(cell, (int, float))
                       and not isinstance(cell, bool)]
            if numbers:
                return doc, common, (f"the refused row {where} carries measured "
                                     f"numbers ({', '.join(numbers)}); a "
                                     "refusal is never a number")
        for name in expect_columns:
            if not same(got["cells"].get(name), want["cells"].get(name)):
                return doc, common, (f"{where}, column {name}: "
                                     f"{got['cells'].get(name)} is not the "
                                     f"recorded {want['cells'].get(name)}")
        # every cell is the receipt's own field, read by the path the
        # manifest records: the golden follows one row all the way back
        receipt = json.loads(Path(got["receipt"]).read_text(encoding="utf-8"))
        for column in doc["columns"]:
            node, missing = receipt, False
            for part in column["receipt_field"].split("."):
                if not isinstance(node, dict) or part not in node:
                    node, missing = None, True
                    break
                node = node[part]
            if not same(got["cells"].get(column["name"]), node):
                return doc, common, (
                    f"{where}, column {column['name']}: the table says "
                    f"{got['cells'].get(column['name'])} and the receipt's "
                    f"{column['receipt_field']} says "
                    f"{'nothing' if missing else node}")
        if got["run_id"] != receipt.get("run_id"):
            return doc, common, f"{where}: the row's run id is not the receipt's"

    computed = sum(1 for row in rows if row["status"] == "computed")
    refused = sum(1 for row in rows if row["status"] == "refused")
    if (computed, refused) != (counts["computed"], counts["refused"]):
        return doc, common, (f"{computed} computed and {refused} refused rows, "
                             f"not the {counts['computed']} and "
                             f"{counts['refused']} the expectations record")
    return doc, common, None


EXPECT = None


def main() -> int:
    global EXPECT
    for script in (SWEEP, FIGURE, METHODS):
        if not script.is_file():
            return fail(f"no script at {script}")
    EXPECT = json.loads(EXPECTATIONS.read_text(encoding="utf-8"))
    columns = [column["name"] for column in EXPECT["columns"]]
    refusals = EXPECT["refusals"]

    bad = selftests()
    if bad is not None:
        return bad

    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)

        # 2 and 3. the two sweeps, cell by cell
        manifests = {}
        for name, spec in EXPECT["sweeps"].items():
            doc, common, message = check_sweep(spec, columns, work,
                                               work / f"sweep-{name}")
            if message:
                return fail(f"the {name} sweep: {message}")
            manifests[name] = (doc, common)
            computed = sum(1 for row in doc["rows"] if row["status"] == "computed")
            refused = sum(1 for row in doc["rows"] if row["status"] == "refused")
            print(f"== sweep over {spec['parameter']}: {len(doc['rows'])} rows, "
                  f"{computed} computed, {refused} refused by the executor, "
                  f"every cell equal to the recorded field")
            for row in doc["rows"]:
                if row["status"] == "refused":
                    print(f"   refused at {row['value']}: {row['reason_code']}, "
                          f"no number, attested as a refusal")

        # 4. the aggregate a reader asks for first
        _, common = manifests["windows"]
        aggregate = run(SWEEP, [*common, "--out-dir", str(work / "aggregate"),
                                "--aggregate", refusals["sweep"]["aggregate"]])
        line = (aggregate.stdout or "").strip()
        if aggregate.returncode != refusals["sweep"]["exit"] or \
                refusals["sweep"]["reason_code"] not in line:
            return fail("the sweep did not refuse the aggregate across its rows "
                        f"(exit {aggregate.returncode}); the Greenland mass "
                        "balance read off a table of windows is a number no "
                        "concept owns")
        if (work / "aggregate" / "sweep.csv").is_file():
            return fail("the refused aggregate still wrote a table; a refusal "
                        "leaves no partial output")
        print(f"== {line.splitlines()[0][:150]}")

        # the receipt the figures and the methods paragraph are made of:
        # the first row of the windows sweep, by the manifest and never
        # by a glob
        doc, _ = manifests["windows"]
        receipt_path = Path(doc["rows"][0]["receipt"])
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))

        # 5. both figure modes, and the map refusal
        for mode in EXPECT["figures"]["modes"]:
            out = work / f"{mode}.png"
            drawn = run(FIGURE, [mode, str(receipt_path), "--out", str(out)])
            if drawn.returncode != 0:
                print((drawn.stdout or "").strip())
                print((drawn.stderr or "").strip())
                return fail(f"the {mode} figure exited {drawn.returncode}")
            if not out.is_file() or out.stat().st_size == 0:
                return fail(f"the {mode} figure wrote no file at {out}")
            caption = drawn.stdout or ""
            for must in (receipt["run_id"],
                         receipt["code_sha256"].split(":")[-1][:12],
                         *EXPECT["figures"]["caption_must_carry"]):
                if must not in caption:
                    return fail(f"the {mode} figure's caption does not carry "
                                f"{must!r}; a figure without its run "
                                "identifier, code digest and verdict cannot be "
                                "traced to the receipt")
            print(f"== figure {mode}: drawn from {receipt['run_id']}, caption "
                  "carries the run id, the code digest and the verdict")
        refused = run(FIGURE, [refusals["figures"]["mode"], str(receipt_path),
                               "--out", str(work / "map.png")])
        if refused.returncode != refusals["figures"]["exit"] or \
                refusals["figures"]["reason_code"] not in (refused.stdout or ""):
            return fail("the renderer did not refuse the map mode (exit "
                        f"{refused.returncode}); these receipts carry no "
                        "per-cell fields, so a map would be drawn from "
                        "something the receipt does not hash")
        if (work / "map.png").exists():
            return fail("the refused map still wrote a file")
        print(f"== figure map: refused ({refusals['figures']['reason_code']}), "
              "no file written")

        # 6. the methods paragraph and its reference list
        out = work / "methods.md"
        written = run(METHODS, ["--receipt", str(receipt_path), "--out", str(out)])
        if written.returncode != 0:
            print((written.stdout or "").strip())
            print((written.stderr or "").strip())
            return fail(f"the methods writer exited {written.returncode}")
        text = out.read_text(encoding="utf-8")
        for section in EXPECT["methods"]["sections"]:
            if section not in text:
                return fail(f"the methods output carries no {section} section")
        for source_id in EXPECT["methods"]["source_ids_that_must_appear"]:
            if f"[^{source_id}]:" not in text:
                return fail(f"the reference list carries no entry for "
                            f"{source_id}; the list is the concept's own "
                            "sources block and this golden fails where one "
                            "stops being copied")
        for path in EXPECT["methods"]["statements_that_must_appear"]:
            node = receipt
            for part in path.split("."):
                node = node[part] if isinstance(node, dict) and part in node else None
                if node is None:
                    break
            if node is None:
                return fail(f"the receipt carries no {path}, which the methods "
                            "paragraph must state")
            if str(node) not in text:
                return fail(f"the methods paragraph does not state the "
                            f"receipt's {path}; a paragraph that leaves a "
                            "bookkeeping statement out is not this receipt's "
                            "methods")
            if f"`{path}`" not in text:
                return fail(f"the field map does not name {path}")
        if EXPECT["methods"]["must_say"] not in text:
            return fail(f"the methods output does not say "
                        f"{EXPECT['methods']['must_say']!r}")
        added = run(METHODS, ["--receipt", str(receipt_path),
                              "--out", str(work / "no.md"),
                              "--add", refusals["methods"]["add"]])
        if added.returncode != refusals["methods"]["exit"] or \
                refusals["methods"]["reason_code"] not in (added.stdout or ""):
            return fail("the methods writer did not refuse a fact from outside "
                        f"the receipt and the concept's sources (exit "
                        f"{added.returncode})")
        if (work / "no.md").exists():
            return fail("the refused methods run still wrote a file")
        print(f"== methods: every bookkeeping statement the receipt records, "
              f"{len(EXPECT['methods']['source_ids_that_must_appear'])} of the "
              "concept's sources checked in the reference list, a fact from "
              "outside refused")

        # 7. a receipt the attester does not pass
        tampered = work / "tampered.json"
        doctored = json.loads(json.dumps(receipt))
        doctored["residual"]["rate_gt_per_yr"] = \
            doctored["residual"]["rate_gt_per_yr"] + 0.5
        tampered.write_text(json.dumps(doctored, indent=2) + "\n", encoding="utf-8")
        drawn = run(FIGURE, ["terms", str(tampered), "--out", str(work / "no.png")])
        if drawn.returncode != refusals["tampered"]["exit"] or \
                refusals["tampered"]["figures_reason_code"] not in (drawn.stdout or ""):
            return fail("the renderer drew a receipt the attester did not pass")
        if (work / "no.png").exists():
            return fail("the refused figure still wrote a file")
        written = run(METHODS, ["--receipt", str(tampered),
                                "--out", str(work / "no2.md")])
        if written.returncode != refusals["tampered"]["exit"] or \
                refusals["tampered"]["methods_reason_code"] not in (written.stdout or ""):
            return fail("the methods writer wrote from a receipt the attester "
                        "did not pass")
        if (work / "no2.md").exists():
            return fail("the refused methods run still wrote a file")
        print("== a tampered receipt: refused by the renderer and by the "
              "methods writer, and a failed row in the sweep with the "
              "attester's own line and no number")

    print("receipt-skills golden: the sweep tables the closure over two "
          "declared parameters with every cell a field of a receipt the "
          "attester passed and the Antarctic refusal kept as a row; both "
          "figures draw from an attested receipt and the map mode is refused; "
          "the methods paragraph states every bookkeeping statement the "
          "receipt records and the reference list is the concept's own; the "
          "aggregate across rows, a fact from outside the receipt and a "
          "receipt the attester did not pass are each refused")
    return 0


if __name__ == "__main__":
    sys.exit(main())
