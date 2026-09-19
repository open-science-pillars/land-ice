---
name: ice-mass-change
description: "Run the attested ice sheet mass balance closure of the NSIDC bundle, the GRACE and GRACE-FO mascon sum against the altimetric volume change less the firn air content change times a stated ice density, through the provider bundle's sanctioned executor, and attest the receipt before quoting any number from it. Keywords: ice sheet, mass balance, mass change, closure, Greenland, Antarctica, GRACE, GRACE-FO, mascons, gravimetry, altimetry, elevation change, ITS_LIVE, ATL15, firn air content, GEMB, ice density, inter-mission gap, bridge."
---

# ice-mass-change

Run instructions for the attested computation
`knowledge/nsidc/computations/ice-sheet-balance.md` in the provider
bundle: over one stated window and for one ice sheet, two rates of
mass change in gigatonnes per year with the interval each carries
(gravimetry from the mascon sum, altimetry from the volume change
less the firn air content change times a stated density), the
residual on the epochs both methods share, the bar the receipt forms,
the verdict `closed_within_uncertainty`, and the GIA, low degree,
frame, smoothing, firn and density statements as receipt facts.

This capability computes nothing. The contract (the parameters, the
receipt fields, the refusal codes, the attester criterion) is the
concept and the executor's own usage text; this skill is the procedure
an agent follows to run it, and every number it reports is owned by
that signed concept. Read the concept before the first run, and read
the bundle's recipe `knowledge/nsidc/recipes/ice-sheet-balance.md` for
how to read what comes back.

The name is the workflow, not the product: this is a mass change of an
ice sheet, not an ATL15 reader and not a mascon reader.

## Where the executor is

The provider bundle arrives with the `nasa-daac-knowledge` dependency.
Its root is the `installPath` of that entry in
`claude plugin list --json`, which is the installer's own record of
what is installed; a checkout named by `NASA_DAAC_KNOWLEDGE` is the one
override, for a workspace that holds the repository beside this one.
`$NSIDC` below stands for `<that root>/knowledge/nsidc`:

- concept: `$NSIDC/computations/ice-sheet-balance.md`
- executor: `$NSIDC/references/computations/ice_sheet_balance.py`
- attester: `$NSIDC/references/attesters/ice_sheet_balance_check.py`
- the committed data root: `$NSIDC/references/retrieval/ice-sheet-balance-root`
- the loaders that built it: `$NSIDC/references/loaders/isb_data_root.py`,
  `isb_mass_mascons.py`, `isb_volume_itslive.py`, `isb_volume_atl15.py`,
  `isb_firn_gemb.py` and `isb_smb_gemb.py`

Never edit the executor or the attester. The attester hashes the
executor on disk, so an edited computation invalidates every earlier
receipt by construction.

## The parameters this skill binds

The concept declares five parameters. This skill binds the four that
apply to every run, and the fifth on every run that needs it:

- `ice_sheet` (string, required), bound as
  `--ice-sheet greenland|antarctica`. Antarctica refuses on the
  committed root, for the reason the refusals section states; that
  refusal is a finding, and binding the parameter is how it is
  reached.
- `window` (string, required), bound as `--window YYYY-MM:YYYY-MM`:
  an inclusive month range of at least two years inside the overlap of
  the terms the run needs. The concept states the committed root's
  Greenland overlap and the fixture's two spans; read them there
  rather than guessing a window.
- `altimetry` (string, optional, default `itslive`), bound as
  `--altimetry itslive|atl15` and always stated out loud, because the
  two products are different records with different sampling and the
  committed root carries only one of them. A root without the named
  term refuses.
- `ice_density` (number, optional, default 917), bound as
  `--ice-density KG_M3`. The default is the density the firn product
  itself uses; a run that states another states why, and the receipt's
  density block carries it either way.
- `bridge` (string, optional), bound as `--bridge TEXT` on every
  window whose mass months lie on both sides of the gap between the
  gravimetry missions, and left unbound otherwise. It is a citation of
  the independent continuity evidence across that gap, and the
  computation refuses a crossing window without one
  (`gap-without-bridge`). Where the window does not cross the gap the
  receipt records the parameter as unbound, which is the concept's own
  rule and not an omission; say which of the two cases the run is.

The rest of the command line is execution plumbing, not science:
`--runtime NAME` names the runtime that ran it (from Claude Code pass
`--runtime claude-code`, from another runtime its own name, with
`--runtime-version V` where the runtime states one); `--fixture
[--seed N]` or `--data-root DIR` selects the input; `--receipt PATH`
says where the receipt is written; `--capability-root DIR` names the
package tree a run is evidence for. The run identifier is bound to the
runtime name, so the same run under two runtime names carries two
identifiers and the same numbers.

## The verdict belongs to the window, not to the ice sheet

The concept's boundaries section is explicit that the closure's
verdict is window dependent on the committed root, and it names which
term it holds responsible: the provider's own mascon series tracks the
loader's gravimetric sum in every window the concept examined, while
the altimetry term (the elevation change with its firn correction)
drifts after 2019, so the altimetry term is the suspect where a window
fails to close. Read that section and cite it by bundle path before
reporting a verdict.

What follows, and belongs in every report:

- **Report the window you ran, and say the verdict is that window's.**
  Never report a headline mass rate for the ice sheet, and never
  present one window's closed verdict as the ice sheet's state. The
  concept records windows on the committed root that close and windows
  on the same root that do not, including halves of the anchor window
  with residuals of opposite sign; quote them from the concept by
  bundle path where a reader needs them, and never average them into
  one number.
- **A closed verdict is a statement about the mean, not about the
  years.** The bar is the residual's own half width, so it grows with
  the disagreement it measures; the concept says so, and a report that
  quotes the verdict without that sentence has changed its meaning.
  The receipt's residual series is what says which term carries each
  year's spike, and the concept reads two of them.
- **The offset from the published assessment is the assessment
  concept's number, not this run's.** Where a reader asks how a rate
  here compares with the published reconciled rates, cite
  `knowledge/nsidc/datasets/imbie-ice-sheet-assessment.md` for those
  numbers and the closure concept for the size of the offset, and
  restate neither as your own. Cite
  `knowledge/nsidc/gotchas/assessment-method-groups-are-not-independent.md`
  in the same breath: the assessment's three method groups are not
  independent measurements of the same thing, so the comparison is not
  a test of one against three.

## The sea level equivalent is another capability's number

An ice sheet mass rate is not a sea level contribution, and this skill
never converts one into the other. The conversion, with the ocean area
constant it rests on and the uncertainty terms that travel with it, is
owned by the podaac bundle's recipe
`knowledge/podaac/recipes/grace-mass-to-sea-level.md`, and the
receipted global budget that carries the ocean mass term is the
attested computation `knowledge/podaac/computations/sea-level-budget.md`,
wrapped by the ocean-science capability's `sea-level-budget` skill.
Send a reader who wants the sea level equivalent there: run that
skill, or read that recipe. Two capabilities never quote the same
number, and a conversion done here would be a number this release does
not own.

## Behavior, in order

1. **Parse and show back:** the ice sheet; the window and whether it
   crosses the gap between the gravimetry missions, so whether a
   bridge citation is bound; the altimetry product; the ice density;
   and whether the run is a rehearsal on the synthetic fixture or a
   real run on the committed data root. Consult the concept and the
   gotchas it rests on, and cite all three by bundle path, the concept
   first, because it is the one that owns every number this run can
   report: `knowledge/nsidc/computations/ice-sheet-balance.md`, then
   `knowledge/nsidc/gotchas/atl15-height-change-is-not-mass-change.md`
   (a height change is a mass change only after the firn air content
   change is removed and a density applied) and
   `knowledge/nsidc/gotchas/firn-air-content-spread-dominates-the-altimetric-mass-rate.md`
   (the firn term's model spread, which is what the altimetric rate's
   formal error mostly is). Restate what each fixes about the
   bookkeeping before anything runs.
2. **The fixture run** (the rehearsal, and the reference the concept
   records):

   ```bash
   uv run $NSIDC/references/computations/ice_sheet_balance.py \
     --ice-sheet greenland --window 2003-01:2016-12 \
     --altimetry itslive --ice-density 917 \
     --fixture --seed 7 \
     --runtime claude-code --receipt /tmp/ice-mass-change-receipt.json
   ```

   The fixture is regenerated deterministically from the seed (a
   hash-based Gaussian stream, no numeric library in the path), with a
   planted gravimetric rate and a planted residual between the two
   methods, the mascon months the real record lacks removed, and firn
   uncertainties that cross zero so the floor rule is exercised; the
   attester regenerates it and compares every series value. A fixture
   receipt says in its own caveats that it proves the chain and not
   the ice sheet, and a report of a fixture run says the same.
3. **The real run on the committed data root:**

   ```bash
   uv run $NSIDC/references/computations/ice_sheet_balance.py \
     --ice-sheet greenland --window 2003-01:2016-12 \
     --altimetry itslive --ice-density 917 \
     --data-root $NSIDC/references/retrieval/ice-sheet-balance-root \
     --runtime claude-code --receipt /tmp/ice-mass-change-record.json
   ```

   The root carries `RECORD.json` (the stamp, the manifest and the
   bookkeeping table with its closure section), `mass.csv`,
   `firn.csv`, `volume-itslive.csv`, `smb.csv`, one stamp per term
   file and `SOURCES.json`. The executor checks every term file
   against the RECORD manifest's digest before it reads a number, and
   refuses a stamp missing any required statement. The altimetry term
   on this root is the elevation change and not ATL15, for the reason
   the root records; a run asking for `atl15` here refuses.
4. **The refusal rule.** A refusal is never a number: the run writes a
   refusal receipt with `refused: true`, a reason code and the reason
   in words, and exits 3.

   ```bash
   uv run $NSIDC/references/computations/ice_sheet_balance.py \
     --ice-sheet antarctica --window 2003-01:2016-12 \
     --altimetry itslive --ice-density 917 \
     --data-root $NSIDC/references/retrieval/ice-sheet-balance-root \
     --runtime claude-code --receipt /tmp/refusal.json
   echo $?   # 3, and the receipt carries firn-term-missing
   ```

   The codes are `window-outside-overlap`, `too-few-epochs`,
   `firn-term-missing`, `term-not-in-root`, `gap-without-bridge` and
   `interval-not-stated`. Report the refusal and its reason in the
   executor's own words. A refusal attests PASS only as a refusal, and
   the attester's verdict line then reads `PASS refusal`.

   **The Antarctic refusal is a finding about the data, not an
   error.** Antarctica refuses on this root because no grounded firn
   air content term covers its altimetry domain: the distribution the
   firn term comes from carries model output over the floating shelves
   only. Report it that way, in the executor's own words, with what
   the concept says would lift it (a loader for one of the alternate
   firn models over the grounded sheet, with no change to the
   executor) and what it does not mean (it is not a statement that
   Antarctica is not losing mass, and not a fault in the mascon or
   volume terms, which the root carries). Never approximate the
   missing term, never substitute a firn number from anywhere else,
   and never report an Antarctic volume change as a mass change.
5. **Attest before quoting anything.** Every number quoted from a
   receipt comes after the attester has said PASS on that exact
   receipt:

   ```bash
   uv run $NSIDC/references/attesters/ice_sheet_balance_check.py \
     /tmp/ice-mass-change-receipt.json [--data-root DIR] [--out /tmp/attestation.json]
   ```

   A data-root receipt is attested with `--data-root DIR` naming the
   tree: without it the data digests are taken on the executor's word
   and are not verified, and a data-root refusal is reproduced only
   from the spans and domains the receipt records, or taken on the
   executor's word where the tree is needed. The checks are `fields`,
   `code`, `release`, `runtime`, `data`, `series`, `recompute`,
   `bookkeeping` and `plausible`; `--out` writes the attestation for a
   qualification record, and `--selftest` runs the tampers, the wrong
   release, the refusals and the forged cases. Report the attester's
   verdict, not your own reading of the numbers.
6. **Report**, with each of these beside the number it qualifies: the
   two rates with their intervals and which error each interval rests
   on (the sampling error or the formal error, as the receipt states);
   the residual on the common epochs against the bar, with the bar's
   two parts (the residual's own half width and the mascon selection
   systematic) named separately; the verdict as the receipt states it,
   attached to the window that produced it; the epochs used and the
   epochs missing; the bound parameters, including the density and
   whether a bridge was bound; the run identifier and the runtime name
   the receipt carries; and the attester's verdict. Then the caveats
   the concept states, in the report and not in a footnote:

   - **The window dependence**, as the section above states it, with
     the altimetry term named as the suspect where a window does not
     close.
   - **The altimetric rate is a mass rate only through the firn term
     and the density.** The firn uncertainty is a two model spread,
     floored where it crosses zero, and not a formal error; the
     receipt's firn floor block says where the floor bit. The density
     is one number for the whole sheet.
   - **The two domains are not the same ice.** The altimetry domain is
     the elevation change product's mask and the gravimetry domain is
     a set of whole mascons that also hold ice free land, coastal
     ocean and a share of the neighbouring regions' signal; the
     residual carries that mismatch and the selection systematic is
     its stated size. Cite
     `knowledge/nsidc/gotchas/ice-sheet-boundaries-and-drainage-basins.md`
     and the podaac bundle's `gotchas/grace-coastal-leakage.md`.
   - **The mascon bookkeeping is the product's, restated and not
     re-applied:** the GIA model, the low degree replacements, the
     reference frame and the smoothing travel in the receipt's mass
     block. Cite the podaac bundle's `gotchas/grace-gia-correction.md`
     and `gotchas/grace-low-degree-replacements.md`.
   - **The intervals are sampling statements**, dominated by the year
     to year variability of the rate itself, and are not measurement
     uncertainties in the published assessment's sense; the formal
     error stands beside each.
   - **This is not a NASA, JPL or NSIDC product.** The concept says so
     and so does a report.

## Must NOT

- Never quote a number from a receipt the attester has not passed, and
  never edit the sanctioned executor or attester.
- Never present a refusal as a number, and never widen, relabel or
  shift a window to get past one.
- Never report a headline mass rate for an ice sheet. A rate here is
  of one window, one altimetry product and one density, and the
  verdict travels with them.
- Never present the Antarctic refusal as a failure of the run or of
  the products, and never fill the missing grounded firn term with an
  estimate, a shelf value or a published rate.
- Never cross the gap between the gravimetry missions without a bridge
  citation, and never satisfy the parameter with a citation that is
  not independent continuity evidence.
- Never convert a mass rate to a sea level equivalent here; cite the
  podaac recipe and the ocean-science skill that own it.
- Never restate the published assessment's rates or the size of the
  offset from them as numbers of this run; cite the assessment
  dataset concept and the closure concept by bundle path.
- Never state a number this release owns. Every figure in a report
  comes from the receipt or from the concept, cited by bundle path.
- Never commit a receipt, an attestation or a generated fixture to
  this repository.
