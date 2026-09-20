#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Write the methods paragraph and the reference list of an attested ice
sheet balance run, from the receipt's bookkeeping block and the
concept's sources and from nothing else.

A methods section is where an unattested fact is least likely to be
caught, because a reader checks the numbers and trusts the prose around
them. So this writer composes no prose about the science freehand. It
assembles the paragraph from a fixed table of statements, each bound to
one dotted path in the receipt, and the reference list from the
concept's own `sources` frontmatter, whose titles it copies verbatim
the way the ocean-science cite-ecco tool copies a citation block. A
statement whose receipt path is absent is a refusal, not an omission
and not a sentence written around the gap, so the paragraph either
names every product, version, model and parameter the receipt records
or it is not written at all.

The attester runs on the receipt before a single field is read, and the
receipt's bytes are hashed before and after so the paragraph is written
from the file that attested.

What it refuses, each with exit 4 and a reason code:

  attester-did-not-pass   the bundle's attester did not PASS this exact
                          receipt. A methods paragraph exists only for a
                          receipt that attests.
  fact-not-in-receipt     a fact to state that is neither a receipt
                          field nor an entry of the concept's sources
                          (asked for with --add TEXT). Every sentence
                          here is one or the other; there is no third
                          source and none is improvised.
  bookkeeping-incomplete  the receipt does not carry a statement the
                          paragraph must make (a GIA model, a firn model
                          version, a density basis, a floor rule, a gap
                          rule). The refusal names the missing path.

The concept, the executor and the attester are reached at the installed
provider bundle's path, the way the wrapping skill reaches them: the
installer's record (`claude plugin list --json`), or a checkout named
by NASA_DAAC_KNOWLEDGE. Nothing is copied here.

Usage:
  methods.py --receipt RECEIPT.json --out methods.md
  methods.py --receipt RECEIPT.json --data-root DIR --out methods.md
  methods.py --selftest
"""

from __future__ import annotations

import argparse
import hashlib
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
CONCEPT = "computations/ice-sheet-balance.md"
ATTESTER = "references/attesters/ice_sheet_balance_check.py"
EXECUTOR = "references/computations/ice_sheet_balance.py"
REFUSALS = ("attester-did-not-pass", "fact-not-in-receipt",
            "bookkeeping-incomplete")


class Refusal(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def refuse(code: str, message: str):
    raise Refusal(code, message)


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


def bundle_file(relative: str) -> Path:
    path = provider_root() / "knowledge" / BUNDLE / relative
    if not path.is_file():
        sys.exit(f"the provider bundle carries no {relative} at {path}; this "
                 f"skill needs {PROVIDER_PLUGIN} at a release that ships it")
    return path


# ---- the concept's sources, copied and never composed

def concept_sources(concept: Path):
    """The concept's own `sources` frontmatter: one entry of id, resource
    and title, with the title copied verbatim. This writer never composes
    or abbreviates a citation; the concept's list is the reference list."""
    text = concept.read_text(encoding="utf-8")
    if not text.startswith("---"):
        sys.exit(f"{concept} carries no frontmatter to read sources from")
    front = text.split("---", 2)[1]
    out, entry, inside = [], None, False
    for line in front.splitlines():
        if re.match(r"^sources:\s*$", line):
            inside = True
            continue
        if not inside:
            continue
        if not line.startswith((" ", "\t")) and line.strip():
            break
        found = re.match(r"^\s*-\s*id:\s*(\S+)\s*$", line)
        if found:
            entry = {"id": found.group(1), "resource": "", "title": ""}
            out.append(entry)
            continue
        if entry is None:
            continue
        for key in ("resource", "title"):
            found = re.match(rf"^\s+{key}:\s*(.*)$", line)
            if found:
                value = found.group(1).strip()
                if len(value) > 1 and value[0] == value[-1] and value[0] in "\"'":
                    value = value[1:-1]
                entry[key] = value
    if not out:
        sys.exit(f"{concept} lists no sources; the reference list is its list")
    return out


# ---- the attester, and the receipt bytes it passed

def attest(receipt_path: Path, attester: Path, data_root: Path | None):
    before = hashlib.sha256(receipt_path.read_bytes()).hexdigest()
    cmd = ["uv", "run", str(attester), str(receipt_path)]
    if data_root is not None:
        cmd += ["--data-root", str(data_root)]
    run = subprocess.run(cmd, capture_output=True, text=True)
    lines = ((run.stdout or "").strip() or (run.stderr or "").strip()).splitlines()
    line = lines[-1] if lines else "the attester printed nothing"
    if run.returncode != 0 or not line.startswith("PASS"):
        refuse("attester-did-not-pass",
               f"{attester.name} did not PASS {receipt_path}; a methods "
               "paragraph exists only for a receipt that attests, so nothing "
               "is written. Report the attester's own lines:\n"
               + "\n".join(lines))
    after = hashlib.sha256(receipt_path.read_bytes()).hexdigest()
    if before != after:
        refuse("bookkeeping-incomplete",
               f"{receipt_path} changed while the attester read it "
               f"(sha256 {before[:12]} then {after[:12]}); the facts a "
               "paragraph would state are not the facts that attested")
    return line, before


# ---- reading the receipt, and refusing where it is silent

def get(receipt: dict, path: str, required: bool = True):
    node = receipt
    for part in path.split("."):
        if not isinstance(node, dict) or part not in node:
            if required:
                refuse("bookkeeping-incomplete",
                       f"the receipt carries no {path}, and the methods "
                       "paragraph must state it. A sentence written around a "
                       "missing bookkeeping statement would be a fact from "
                       "outside the receipt, so nothing is written. Rerun the "
                       "computation with a root whose RECORD.json carries "
                       "that statement, or report the gap.")
            return None
        node = node[part]
    if required and node is None:
        refuse("bookkeeping-incomplete",
               f"the receipt's {path} is null, and the methods paragraph must "
               "state it")
    return node


def statement(value, ice_sheet: str):
    """A bookkeeping statement is either one sentence or one sentence per
    ice sheet; take the bound ice sheet's where the receipt keys it that
    way, and never merge two ice sheets' statements into one."""
    if isinstance(value, dict) and ice_sheet in value:
        return value[ice_sheet]
    return value


def product_of(receipt: dict, term: str, ice_sheet: str):
    """The product, DOI and granule the term's stamp records, or None
    where the stamp carries none (a synthetic root)."""
    stamp = get(receipt, f"terms.{term}.stamp", required=False) or {}
    series = (stamp.get("series") or {}).get(ice_sheet) or {}
    if not series.get("product"):
        return None
    return {"product": series.get("product"), "doi": series.get("doi"),
            "granule": series.get("granule"),
            "granule_sha256": series.get("granule_sha256"),
            "read_utc": series.get("read_utc")}


# ---- the paragraph

def number(value, places: int = 3) -> str:
    return f"{value:+.{places}f}" if isinstance(value, float) else str(value)


def domain_text(value) -> str:
    """A domain the receipt states as one name or as a list of them,
    read out as words rather than as a Python list."""
    if isinstance(value, list):
        return " and ".join(str(part) for part in value)
    return str(value)


def build(receipt: dict, sources, verdict_line: str, receipt_sha: str):
    """The paragraph and its field map. Every sentence is appended with
    the receipt paths it was built from, so the map is a by-product of
    writing rather than a claim about it."""
    said = []          # (sentence, [receipt paths or source ids])

    def say(sentence: str, *paths: str):
        said.append((sentence, list(paths)))

    sheet = get(receipt, "bound_parameters.ice_sheet")
    window = get(receipt, "bound_parameters.window")
    altimetry = get(receipt, "bound_parameters.altimetry")
    density = get(receipt, "bound_parameters.ice_density")
    bridge = get(receipt, "bound_parameters.bridge", required=False)
    mode = get(receipt, "data.mode")
    ids = {entry["id"] for entry in sources}

    def cite(*keys):
        return "".join(f"[^{k}]" for k in keys if k in ids)

    # 1. What was run, and on what.
    if mode == "data-root":
        where = (f"the stamped data root {get(receipt, 'data.record.record')} "
                 f"(manifest {get(receipt, 'data.record.manifest_sha256')})")
        where_paths = ["data.mode", "data.record.record",
                       "data.record.manifest_sha256"]
    else:
        where = (f"the executor's synthetic fixture at seed "
                 f"{get(receipt, 'data.seed')} (digest "
                 f"{get(receipt, 'data.digest')}), which proves the chain and "
                 f"not the ice sheet")
        where_paths = ["data.mode", "data.seed", "data.digest"]
    say(f"The {sheet.capitalize()} mass balance closure over {window} was "
        f"computed by the "
        f"attested computation knowledge/{BUNDLE}/{CONCEPT}, run through the "
        f"sanctioned executor knowledge/{BUNDLE}/{EXECUTOR} at digest "
        f"{get(receipt, 'code_sha256')} under the runtime "
        f"{get(receipt, 'runtime.name')}, on {where}"
        + cite("slb") + ".",
        "bound_parameters.ice_sheet", "bound_parameters.window",
        "computation", "code_sha256", "runtime.name", *where_paths)

    # 2. The parameters bound.
    bound = (f"ice_sheet {sheet}, window {window}, altimetry {altimetry}, "
             f"ice_density {density} kg per cubic metre, and bridge "
             + (f"{bridge!r}" if bridge else "unbound"))
    say(f"The five parameters the concept declares were bound as {bound}"
        + (", the window not crossing the gap between the gravimetry missions"
           if get(receipt, "bookkeeping.gap_handling.crosses_intermission_gap")
           is False else
           ", the window crossing the gap between the gravimetry missions")
        + cite("gotcha-gap") + ".",
        "bound_parameters.ice_sheet", "bound_parameters.window",
        "bound_parameters.altimetry", "bound_parameters.ice_density",
        "bound_parameters.bridge",
        "bookkeeping.gap_handling.crosses_intermission_gap")

    # 3. The gravimetric term and its bookkeeping.
    say(f"The gravimetric term is the mascon sum over the "
        f"{domain_text(get(receipt, 'terms.gravimetry.domain'))} domain at "
        f"{get(receipt, 'terms.gravimetry.n_epochs')} solution epochs in the "
        f"window, selected by the rule: "
        f"{statement(get(receipt, 'bookkeeping.mass.selection'), sheet)}"
        + cite("mascons") + ".",
        "terms.gravimetry.domain", "terms.gravimetry.n_epochs",
        "bookkeeping.mass.selection")
    say(f"Its bookkeeping is the product's, restated and not re-applied: the "
        f"glacial isostatic adjustment model is "
        f"{statement(get(receipt, 'bookkeeping.mass.gia'), sheet)}; the low "
        f"degree replacements are "
        f"{statement(get(receipt, 'bookkeeping.mass.low_degree'), sheet)}; the "
        f"reference frame is "
        f"{statement(get(receipt, 'bookkeeping.mass.reference_frame'), sheet)}; "
        f"the effective smoothing is "
        f"{statement(get(receipt, 'bookkeeping.mass.effective_smoothing'), sheet)}; "
        f"and the uncertainty basis is "
        f"{statement(get(receipt, 'bookkeeping.mass.uncertainty_basis'), sheet)}"
        + cite("gotcha-gia", "gotcha-low-degree", "gotcha-leakage") + ".",
        "bookkeeping.mass.gia", "bookkeeping.mass.low_degree",
        "bookkeeping.mass.reference_frame",
        "bookkeeping.mass.effective_smoothing",
        "bookkeeping.mass.uncertainty_basis")

    # 4. The altimetric term, the firn term and the density.
    say(f"The altimetric term is formed by the rule "
        f"{get(receipt, 'terms.altimetry.rule')}, over the "
        f"{domain_text(get(receipt, 'terms.altimetry.domain'))} domain at "
        f"{get(receipt, 'terms.altimetry.n_epochs')} epochs, with the firn "
        f"term subtracted over the "
        f"{domain_text(get(receipt, 'terms.altimetry.firn_domain'))} domain"
        + cite("gotcha-firn", "gotcha-grid") + ".",
        "terms.altimetry.rule", "terms.altimetry.domain",
        "terms.altimetry.n_epochs", "terms.altimetry.firn_domain")
    say(f"The volume term's reference is "
        f"{statement(get(receipt, 'bookkeeping.volume.reference'), sheet)}, its "
        f"mask is {statement(get(receipt, 'bookkeeping.volume.mask'), sheet)}, "
        f"its uncertainty basis is "
        f"{statement(get(receipt, 'bookkeeping.volume.uncertainty_basis'), sheet)}, "
        f"and it is not a mass: "
        f"{statement(get(receipt, 'bookkeeping.volume.not_mass'), sheet)}.",
        "bookkeeping.volume.reference", "bookkeeping.volume.mask",
        "bookkeeping.volume.uncertainty_basis", "bookkeeping.volume.not_mass")
    say(f"The firn air content term is version "
        f"{statement(get(receipt, 'bookkeeping.firn.gemb_version'), sheet)} "
        f"forced by "
        f"{statement(get(receipt, 'bookkeeping.firn.forcing'), sheet)}, "
        f"referenced to "
        f"{statement(get(receipt, 'bookkeeping.firn.reference'), sheet)}, with "
        f"uncertainty "
        f"{statement(get(receipt, 'bookkeeping.firn.uncertainty_basis'), sheet)}"
        + cite("its-live") + ".",
        "bookkeeping.firn.gemb_version", "bookkeeping.firn.forcing",
        "bookkeeping.firn.reference", "bookkeeping.firn.uncertainty_basis")
    say(f"Because that uncertainty is a model spread rather than a formal "
        f"error, it is floored: {get(receipt, 'bookkeeping.firn_floor.rule')}, "
        f"at {json.dumps(get(receipt, 'bookkeeping.firn_floor.floor_m'))} "
        f"metres by domain.",
        "bookkeeping.firn_floor.rule", "bookkeeping.firn_floor.floor_m")
    say(f"The ice density applied is "
        f"{get(receipt, 'bookkeeping.density.ice_density_kg_m3')} kilograms "
        f"per cubic metre: "
        f"{get(receipt, 'bookkeeping.density.basis')}.",
        "bookkeeping.density.ice_density_kg_m3", "bookkeeping.density.basis")

    # 5. The products the stamps name.
    for term, label in (("altimetry", "altimetric volume"), ("firn", "firn air content")):
        product = product_of(receipt, term, sheet)
        if product is None:
            continue
        bits = [f"The {label} term was read from {product['product']}"]
        if product.get("doi"):
            bits.append(f"doi {product['doi']}")
        if product.get("granule"):
            bits.append(f"granule {product['granule']}")
        if product.get("granule_sha256"):
            bits.append(f"sha256 {product['granule_sha256']}")
        if product.get("read_utc"):
            bits.append(f"read {product['read_utc']}")
        say(", ".join(bits) + ".", f"terms.{term}.stamp.series.{sheet}")

    # 6. The rate method, the rates and the residual.
    say(f"Each rate is the {get(receipt, 'rates.gravimetry.method')}.",
        "rates.gravimetry.method")
    conf = get(receipt, "rates.gravimetry.confidence")
    for term, label in (("gravimetry", "gravimetric"), ("altimetry", "altimetric")):
        say(f"The {label} rate over the window is "
            f"{number(get(receipt, f'terms.{term}.rate_gt_per_yr'))} gigatonnes "
            f"per year, {int(conf * 100)} percent interval "
            f"[{number(get(receipt, f'rates.{term}.ci_low'))}, "
            f"{number(get(receipt, f'rates.{term}.ci_high'))}], on the "
            f"{get(receipt, f'rates.{term}.se_basis')} error.",
            f"terms.{term}.rate_gt_per_yr", f"rates.{term}.ci_low",
            f"rates.{term}.ci_high", f"rates.{term}.se_basis",
            "rates.gravimetry.confidence")
    say(f"The residual is {get(receipt, 'residual.rule')}, over "
        f"{get(receipt, 'residual.n_common_differences')} common differences: "
        f"{number(get(receipt, 'residual.rate_gt_per_yr'))} gigatonnes per "
        f"year, interval [{number(get(receipt, 'rates.residual.ci_low'))}, "
        f"{number(get(receipt, 'rates.residual.ci_high'))}].",
        "residual.rule", "residual.n_common_differences",
        "residual.rate_gt_per_yr", "rates.residual.ci_low",
        "rates.residual.ci_high")
    say(f"The bar is {get(receipt, 'combined_uncertainty.rule')}: "
        f"{number(get(receipt, 'combined_uncertainty.bar_gt_per_yr'))} "
        f"gigatonnes per year, the residual's own half width "
        f"{number(get(receipt, 'combined_uncertainty.residual_half_width_gt_per_yr'))} "
        f"plus a selection systematic of "
        f"{number(get(receipt, 'combined_uncertainty.selection_systematic.value_gt_per_yr'))} "
        f"whose basis is "
        f"{get(receipt, 'combined_uncertainty.selection_systematic.basis')}"
        + cite("gotcha-basins") + ".",
        "combined_uncertainty.rule", "combined_uncertainty.bar_gt_per_yr",
        "combined_uncertainty.residual_half_width_gt_per_yr",
        "combined_uncertainty.selection_systematic.value_gt_per_yr",
        "combined_uncertainty.selection_systematic.basis")

    # 7. Missing epochs, the gap rule and the verdict.
    missing = get(receipt, "bookkeeping.gap_handling.mass_months_missing")
    say(f"Epochs are handled by the rule "
        f"{get(receipt, 'bookkeeping.gap_handling.rule')}; "
        f"{len(missing)} mascon months are missing from the window"
        + (f" ({', '.join(missing)})" if missing else "") + ".",
        "bookkeeping.gap_handling.rule",
        "bookkeeping.gap_handling.mass_months_missing")
    say(f"The verdict is {get(receipt, 'verdict.rule')}, and for this run "
        f"closed_within_uncertainty is "
        f"{'true' if get(receipt, 'verdict.closed_within_uncertainty') else 'false'}; "
        f"it belongs to this window and to these bindings, not to the ice "
        f"sheet"
        + cite("otosaka-2023") + ".",
        "verdict.rule", "verdict.closed_within_uncertainty")

    # 8. The receipt's own caveats, verbatim.
    for index, caveat in enumerate(get(receipt, "caveats")):
        say(caveat[0].upper() + caveat[1:] + ".", f"caveats[{index}]")

    say(f"The receipt was attested before any field above was read: "
        f"{verdict_line}. Run identifier {get(receipt, 'run_id')}, receipt "
        f"sha256 {receipt_sha}.", "run_id")

    return said


def render(receipt: dict, sources, said, verdict_line: str,
           receipt_sha: str, concept_path: str) -> str:
    sheet = receipt["bound_parameters"]["ice_sheet"]
    window = receipt["bound_parameters"]["window"]
    lines = [f"# Methods: {sheet} ice sheet mass balance closure, {window}", ""]
    lines += ["Written from one attested receipt and the concept's own "
              "sources. Every sentence below is a field of that receipt or an "
              "entry of that source list; nothing here is composed freehand "
              "and no number is this capability's own.", ""]
    lines += ["## Methods", ""]
    lines.append(" ".join(sentence for sentence, _ in said))
    lines += ["", "## References", ""]
    lines.append("The reference list is the concept's own `sources` block, "
                 "copied verbatim; this writer never composes, abbreviates or "
                 "reconstructs a citation.")
    lines.append("")
    for entry in sources:
        lines.append(f"[^{entry['id']}]: {entry['title']} ({entry['resource']})")
    lines += ["", "## Field map", "",
              "Each sentence of the methods paragraph, with the receipt "
              "fields it was built from. A statement whose path is absent "
              "from a receipt is refused, never written around.", "",
              "| # | statement | receipt fields |",
              "| --- | --- | --- |"]
    for index, (sentence, paths) in enumerate(said, start=1):
        short = sentence if len(sentence) <= 90 else sentence[:87] + "..."
        short = short.replace("|", "\\|")
        lines.append(f"| {index} | {short} | "
                     + ", ".join(f"`{p}`" for p in paths) + " |")
    lines += ["", "## Provenance", "",
              f"- concept: `{concept_path}`",
              f"- executor: `knowledge/{BUNDLE}/{EXECUTOR}` at "
              f"`{receipt['code_sha256']}`",
              f"- attester: `knowledge/{BUNDLE}/{ATTESTER}`, verdict "
              f"`{verdict_line}`",
              f"- wrapping skill: `land-ice/ice-mass-change`",
              f"- run identifier: `{receipt['run_id']}`, runtime "
              f"`{receipt['runtime']['name']}`, generated "
              f"`{receipt['generated_utc']}`",
              f"- receipt sha256: `{receipt_sha}`",
              "", "Produced by Open Science Pillars. Not a NASA, JPL or "
              "NSIDC product.", ""]
    return "\n".join(lines)


def write(args) -> int:
    if args.add:
        refuse("fact-not-in-receipt",
               f"this writer will not add a fact that is neither a field of "
               f"the receipt nor an entry of the concept's sources, and what "
               f"was asked for is one: {args.add}. A methods paragraph that "
               f"carries a number, a product name, a model version or a "
               f"published rate from outside the receipt cannot be checked by "
               f"the attester that passed it, and a reader cannot follow it "
               f"back. If the fact belongs to the computation, it belongs in "
               f"the concept knowledge/{BUNDLE}/{CONCEPT} or in the stamped "
               f"root's RECORD.json, where it becomes a receipt field and "
               f"this writer states it; if it belongs to another concept, "
               f"cite that concept by bundle path in your own text beside "
               f"this paragraph rather than inside it.")
    concept = bundle_file(CONCEPT)
    attester = bundle_file(ATTESTER)
    receipt_path = Path(args.receipt).expanduser().resolve()
    data_root = Path(args.data_root).expanduser().resolve() if args.data_root else None
    verdict_line, receipt_sha = attest(receipt_path, attester, data_root)
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    if receipt.get("refused"):
        refuse("bookkeeping-incomplete",
               f"this receipt is a refusal ({receipt.get('reason_code')}) and "
               "carries no rates, no residual and no verdict: a refusal is "
               "never a number and never a methods paragraph. Report the "
               "refusal in the executor's own words.")
    if "ice_sheet_balance" not in (receipt.get("computation") or ""):
        refuse("bookkeeping-incomplete",
               f"this writer states the methods of the ice sheet balance "
               f"closure and this receipt is from "
               f"{receipt.get('computation')!r}")
    sources = concept_sources(concept)
    said = build(receipt, sources, verdict_line, receipt_sha)
    text = render(receipt, sources, said, verdict_line, receipt_sha,
                  f"knowledge/{BUNDLE}/{CONCEPT}")
    out = Path(args.out).expanduser()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    print(text)
    print(f"methods written: {out} ({len(said)} statements, "
          f"{len(sources)} references, every statement a receipt field)")
    return 0


# ---- selftest

def selftest() -> int:
    """Every refusal, on the executor's synthetic fixture."""
    executor = bundle_file(EXECUTOR)
    attester = bundle_file(ATTESTER)
    concept = bundle_file(CONCEPT)
    here = str(Path(__file__).resolve())

    def run_methods(argv):
        return subprocess.run([sys.executable, here, *argv],
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
        body = json.loads(receipt.read_text())

        # 1. The paragraph is written, and it names every product,
        #    version, model and parameter the receipt records.
        done = run_methods(["--receipt", str(receipt), "--out", str(work / "m.md")])
        assert done.returncode == 0, done.stdout + done.stderr
        text = (work / "m.md").read_text()
        for must in (body["code_sha256"], body["run_id"],
                     body["bound_parameters"]["window"],
                     str(body["bookkeeping"]["density"]["ice_density_kg_m3"]),
                     body["bookkeeping"]["mass"]["gia"],
                     body["bookkeeping"]["mass"]["low_degree"],
                     body["bookkeeping"]["mass"]["reference_frame"],
                     body["bookkeeping"]["firn"]["gemb_version"],
                     body["bookkeeping"]["firn"]["forcing"],
                     body["bookkeeping"]["firn_floor"]["rule"],
                     body["bookkeeping"]["gap_handling"]["rule"],
                     body["verdict"]["rule"],
                     body["residual"]["rule"]):
            assert str(must) in text, f"the paragraph does not state {must!r}"
        assert "## References" in text and "## Field map" in text
        for entry in concept_sources(concept):
            assert f"[^{entry['id']}]:" in text, entry["id"]
            assert entry["title"] in text, entry["id"]
        assert "Not a NASA, JPL or NSIDC product." in text
        for caveat in body["caveats"]:
            assert caveat[1:] in text, caveat

        # 2. A fact from outside the receipt and the sources is refused.
        out = run_methods(["--receipt", str(receipt), "--out", str(work / "no.md"),
                           "--add", "the published IMBIE rate for these years"])
        assert out.returncode == 4 and "fact-not-in-receipt" in out.stdout, out.stdout
        assert not (work / "no.md").exists()

        # 3. A receipt the attester did not pass is never written from.
        tampered = work / "tampered.json"
        doctored = json.loads(json.dumps(body))
        doctored["residual"]["rate_gt_per_yr"] += 0.5
        tampered.write_text(json.dumps(doctored, indent=2) + "\n")
        out = run_methods(["--receipt", str(tampered), "--out", str(work / "no2.md")])
        assert out.returncode == 4 and "attester-did-not-pass" in out.stdout, out.stdout
        assert not (work / "no2.md").exists()

        # 4. A receipt missing a bookkeeping statement is refused, and
        #    the refusal names the path rather than writing around it.
        for path in ("bookkeeping.mass.gia", "bookkeeping.firn.gemb_version",
                     "bookkeeping.density.basis", "bookkeeping.firn_floor.rule",
                     "bookkeeping.gap_handling.rule"):
            doctored = json.loads(json.dumps(body))
            node, last = doctored, path.split(".")
            for part in last[:-1]:
                node = node[part]
            node.pop(last[-1])
            try:
                build(doctored, concept_sources(concept), "PASS", "x")
            except Refusal as bad:
                assert bad.code == "bookkeeping-incomplete", (path, bad.code)
                assert path in str(bad), (path, str(bad))
            else:
                raise AssertionError(f"a receipt without {path} was not refused")

        # 5. A refusal receipt is never a methods paragraph.
        refusal = work / "refusal.json"
        run = subprocess.run(
            ["uv", "run", str(executor), "--ice-sheet", "greenland",
             "--window", "2019-01:2025-12", "--altimetry", "atl15",
             "--ice-density", "917", "--fixture", "--seed", "7",
             "--runtime", "selftest", "--receipt", str(refusal)],
            capture_output=True, text=True)
        assert run.returncode == 3, run.stdout + run.stderr
        out = run_methods(["--receipt", str(refusal), "--out", str(work / "no3.md")])
        assert out.returncode == 4 and "bookkeeping-incomplete" in out.stdout, out.stdout
        assert "refusal" in out.stdout and not (work / "no3.md").exists()

        # 6. The reference list is the concept's own, copied verbatim.
        sources = concept_sources(concept)
        assert {"gotcha-firn", "mascons", "otosaka-2023",
                "smith-2020"} <= {s["id"] for s in sources}
        assert all(s["title"] and s["resource"] for s in sources)

    print("methods selftest: ok "
          f"({len(REFUSALS)} refusals exercised: {', '.join(REFUSALS)}; "
          "the paragraph is written from an attested fixture receipt and the "
          "concept's own source list, and a refusal receipt is never a "
          "paragraph)")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--receipt", help="the attested receipt to write from")
    ap.add_argument("--data-root", default=None,
                    help="the stamped tree, so a data-root receipt is attested "
                         "against it rather than on the executor's word")
    ap.add_argument("--out", help="where the methods markdown is written")
    ap.add_argument("--add", default=None,
                    help="a fact to add to the paragraph; always refused, and "
                         "the refusal says where such a fact belongs instead")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()

    if args.selftest:
        return selftest()
    try:
        if not args.receipt or not args.out:
            if args.add:
                return write(args)
            ap.error("--receipt and --out are required")
        return write(args)
    except Refusal as bad:
        print(f"METHODS REFUSED ({bad.code}): {bad}")
        return 4


if __name__ == "__main__":
    sys.exit(main())
