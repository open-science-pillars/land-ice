---
name: ice-sheet-input-output
description: "Run the attested input-output mass balance of the NSIDC bundle, the surface mass balance over the grounded ice less the discharge through a named flux gate set formed node by node from velocity and thickness, through the provider bundle's sanctioned executor, and attest the receipt before quoting any number from it; the record run on the committed root refuses and the skill reports that refusal. Keywords: ice sheet, mass balance, input-output, discharge, flux gate, surface mass balance, SMB, grounding line, Greenland, Antarctica, ITS_LIVE, velocity mosaic, BedMachine, thickness, mass conservation."
---

# ice-sheet-input-output

Run instructions for the attested computation
`knowledge/nsidc/computations/ice-sheet-input-output.md` in the
provider bundle: over one stated window, for one ice sheet and one
named gate set, the surface mass balance over the grounded domain and
the discharge through the gate set, each as the mean of its annual
epochs with an interval, the mass rate as their difference epoch by
epoch, the bar the receipt forms, and a verdict on whether the mass
rate is distinguishable from zero.

This capability computes nothing. The contract (the parameters, the
receipt fields, the refusal codes, the attester criterion) is the
concept and the executor's own usage text; this skill is the procedure
an agent follows to run it, and every number it reports is owned by
that concept. Read the concept before the first run, and read the
bundle's recipe `knowledge/nsidc/recipes/ice-sheet-input-output.md`
for how to read what comes back.

The name is the workflow, not the product: this is the input-output
method, the third of the three satellite methods, not a velocity
reader and not a thickness reader.

**This concept is a draft.** At the provider release this capability
declares a floor on, `knowledge/nsidc/computations/ice-sheet-input-output.md`
carries `status: draft` and no maintainer signature. Say so on every
run, before the numbers: a draft is voiced as a draft, and a stable
concept outranks it wherever the two meet. The companion closure
concept `knowledge/nsidc/computations/ice-sheet-balance.md`, which
this skill's sibling wraps, is signed stable, and where the two
disagree the stable one wins.

## Where the executor is

The provider bundle arrives with the `nasa-daac-knowledge` dependency.
Its root is the `installPath` of that entry in
`claude plugin list --json`, which is the installer's own record of
what is installed; a checkout named by `NASA_DAAC_KNOWLEDGE` is the one
override, for a workspace that holds the repository beside this one.
`$NSIDC` below stands for `<that root>/knowledge/nsidc`:

- concept: `$NSIDC/computations/ice-sheet-input-output.md`
- executor: `$NSIDC/references/computations/ice_sheet_input_output.py`
- attester: `$NSIDC/references/attesters/ice_sheet_input_output_check.py`
- the committed data root: `$NSIDC/references/retrieval/ice-sheet-input-output-root`
- the loaders that built it: `$NSIDC/references/loaders/iio_data_root.py`,
  `iio_velocity_itslive.py`, `iio_thickness_bedmachine.py` and
  `iio_smb_gemb.py`

Never edit the executor or the attester. The attester hashes the
executor on disk, so an edited computation invalidates every earlier
receipt by construction.

## The parameters this skill binds

The concept declares five parameters, and this skill binds all five on
every run:

- `ice_sheet` (string, required), bound as
  `--ice-sheet greenland|antarctica`.
- `window` (string, required), bound as `--window YYYY-MM:YYYY-MM`:
  an inclusive month range of at least two years covered by both
  terms' epochs, with at least three epochs common to them.
- `gates` (string, required), bound as `--gates NAME`: the name of the
  gate set in the data root. A gate set is a rule and not a fact, so
  the name is stated in every report beside every discharge it
  produced, and the root's gate table is what says how the nodes were
  placed, whether the set spans the ice sheet's grounded margin and
  which product's mask decided that a node is grounded.
- `velocity_epoch` (string, optional, default `annual`), bound as
  `--velocity-epoch annual|static`. An annual mosaic is a composite
  with its own effective date and count rather than a calendar mean,
  which the bundle's gotcha
  `knowledge/nsidc/gotchas/velocity-mosaic-epochs-and-gaps.md` owns;
  cite it and never treat an epoch label as a measurement date.
- `ice_density` (number, optional, default 917), bound as
  `--ice-density KG_M3`, applied to the volume flux through the gate.

The rest of the command line is execution plumbing, not science:
`--runtime NAME` names the runtime that ran it (from Claude Code pass
`--runtime claude-code`, from another runtime its own name, with
`--runtime-version V` where the runtime states one); `--fixture
[--seed N]` or `--data-root DIR` selects the input; `--receipt PATH`
says where the receipt is written; `--capability-root DIR` names the
package tree a run is evidence for. The run identifier is bound to the
runtime name.

## No real-data estimate exists yet, and this skill says so first

The record run on the committed data root is a refusal, not a number,
and that is the honest state of this method in this bundle. Two
different things are missing and they are missing for two different
reasons, which the concept and the root's own SOURCES record:

- **The thickness term is an access block.** The thickness product is
  distributed only from an archive that answers a granule request with
  a redirect to a content distribution host that the drafting
  environment's egress policy refuses at the connection. Nothing about
  the product, its version or a credential is at fault, and the block
  moves with the environment rather than with the data. Quote the
  executor's own refusal text, which names the host and the status
  codes, rather than paraphrasing it.
- **The grounded surface mass balance term is a distribution gap.** No
  gridded surface mass balance over the grounded Greenland ice sheet
  is distributed by any NASA archive the concept's search reached; the
  two regional climate models the published assessment's input-output
  estimates rest on are not NASA products. A different network does
  not fix this one.

What follows, and belongs in every report of this skill:

- Say plainly that no real-data input-output estimate of any ice sheet
  exists in this bundle yet, and that every number the fixture run
  produces is a planted synthetic value that proves the chain and not
  an ice sheet. Never present a fixture number as Greenland's or
  Antarctica's.
- Say what would produce one: a reachable thickness granule sampled at
  the existing gate nodes, a gridded grounded surface mass balance
  term, and a gate set extended to span the grounded margin. The
  existing gate set is the geometry the thickness loader will sample,
  not a gate set a discharge may be quoted from, and the concept says
  so.
- The skill is usable anyway, and that is its point: the fixture chain
  runs offline, binds every declared parameter, attests, and exercises
  the refusals, so the method is proven and ready for the day the
  terms land.
- Where a reader wants the number this method would give, send them to
  the two estimates the bundle does have, through this skill's sibling
  `ice-mass-change`, and to the published assessment's own
  input-output group in
  `knowledge/nsidc/datasets/imbie-ice-sheet-assessment.md`. Cite that
  concept for its numbers and restate none of them here, and cite
  `knowledge/nsidc/gotchas/assessment-method-groups-are-not-independent.md`
  beside it, because the assessment's method groups are not
  independent measurements of the same thing.

A sea level contribution is not computed here either. That conversion
is owned by the podaac bundle's recipe
`knowledge/podaac/recipes/grace-mass-to-sea-level.md` and reported by
the ocean-science capability's `sea-level-budget` skill.

## Behavior, in order

1. **Parse and show back:** that the concept is a draft; the ice
   sheet, the window, the gate set by name, the velocity epoch family
   and the ice density; and whether the run is a rehearsal on the
   synthetic fixture or a run on the committed data root, which
   refuses. Consult the concept and the gotchas it rests on, and cite
   each by bundle path:
   `knowledge/nsidc/gotchas/bedmachine-thickness-is-interpolated.md`
   (the thickness between flight lines is mass conservation or an
   interpolation, and the product's own fields say which, which is why
   a node whose thickness is an interpolation is refused),
   `knowledge/nsidc/gotchas/bedmachine-mask-and-grounding-line.md` (a
   discharge gate sits on grounded ice upstream of the grounding line,
   and the mask is what places it),
   `knowledge/nsidc/gotchas/velocity-mosaic-epochs-and-gaps.md` and
   `knowledge/nsidc/gotchas/polar-stereographic-not-latlon.md` (the
   grids are projected metres, so a node's flux carries the
   projection's areal scale). Restate what each fixes before anything
   runs.
2. **The fixture run** (the rehearsal, and the reference the concept
   records):

   ```bash
   uv run $NSIDC/references/computations/ice_sheet_input_output.py \
     --ice-sheet greenland --window 2005-01:2014-12 \
     --gates synthetic-outlets --velocity-epoch annual --ice-density 917 \
     --fixture --seed 7 \
     --runtime claude-code --receipt /tmp/input-output-receipt.json
   ```

   The fixture is regenerated deterministically from the seed (a
   hash-based Gaussian stream, no numeric library in the path), with a
   gate set that spans its margin and a planted discharge that rises
   with time, a surface mass balance whose seasonal cycle cancels over
   a year so the annualisation is exercised, a gate set whose
   thickness is an interpolation, a gate set with a node on floating
   ice, and an ice sheet with no grounded surface mass balance; the
   attester regenerates it and rebuilds every term from its rows. A
   fixture receipt says in its own caveats that it proves the chain
   and not the ice sheet, and a report of a fixture run says the same.
3. **The run on the committed data root, which refuses:**

   ```bash
   uv run $NSIDC/references/computations/ice_sheet_input_output.py \
     --ice-sheet greenland --window 2014-01:2023-12 \
     --gates greenland-outlets-v1 --velocity-epoch annual --ice-density 917 \
     --data-root $NSIDC/references/retrieval/ice-sheet-input-output-root \
     --runtime claude-code --receipt /tmp/input-output-record.json
   echo $?   # 3, and the receipt carries term-not-in-root
   ```

   The root carries `RECORD.json`, `velocity.csv`, its stamp and
   `SOURCES.json`, and nothing else: the gate geometry and the gate
   velocities are real and only the other two terms are absent. Run
   this anyway, and report the refusal and what the root does hold.
   It is the honest state of the method, and a reader who is told only
   about the fixture has been told less than the bundle knows.
4. **The refusal rule.** A refusal is never a number: the run writes a
   refusal receipt with `refused: true`, a reason code and the reason
   in words, and exits 3. The codes are `term-not-in-root`,
   `gate-set-not-in-root`, `velocity-epoch-not-in-root`,
   `gate-set-incomplete`, `gate-thickness-interpolated`,
   `gate-not-grounded`, `smb-term-missing`, `window-outside-epochs`,
   `too-few-epochs` and `interval-not-stated`. Report the refusal in
   the executor's own words; a refusal attests PASS only as a refusal,
   and the verdict line reads `PASS refusal`.

   Three of these are findings about the ice, not accidents, and a
   report says which one it met. `gate-thickness-interpolated` says a
   node's thickness is a model quantity the method was not built to
   conserve a flux through. `gate-not-grounded` says a node sits on
   ice that has already crossed the grounding line, so its flux has
   already left the sheet. `gate-set-incomplete` says the gate set
   does not span the grounded margin, so no ice sheet wide rate can be
   formed from it at all: a handful of outlets is not a mass balance,
   and the computation refuses rather than reports one.
5. **Attest before quoting anything.** Every number quoted from a
   receipt comes after the attester has said PASS on that exact
   receipt:

   ```bash
   uv run $NSIDC/references/attesters/ice_sheet_input_output_check.py \
     /tmp/input-output-receipt.json [--data-root DIR] [--out /tmp/attestation.json]
   ```

   A data-root receipt is attested with `--data-root DIR` naming the
   tree: without it the data digests are taken on the executor's word
   and are not verified, and a data-root refusal is reproduced only
   from the gate sets, domains, epoch families and spans the receipt
   records, or taken on the executor's word where the tree is needed.
   The checks are `fields`, `code`, `release`, `runtime`, `data`,
   `gates`, `series`, `recompute`, `bookkeeping` and `plausible`;
   `--out` writes the attestation for a qualification record, and
   `--selftest` runs the tampers, the wrong release, the refusals and
   the forged cases. Report the attester's verdict, not your own
   reading of the numbers.
6. **Report**, with each of these beside the number it qualifies: that
   the concept is a draft; the gate set by name with its node and gate
   counts, whether it spans the grounded margin and what settled each
   node's grounding; the two terms with their intervals and which
   error each interval rests on; the mass rate against the bar, with
   the bar's two parts (the mass rate's own half width and the gate
   systematic) named separately, and the reason the gate systematic is
   what it is; the verdict and its sign as the receipt states them;
   the epochs used; the bound parameters; the run identifier and the
   runtime name; and the attester's verdict. Then the caveats the
   concept states:

   - **The discharge holds the thickness fixed.** It is a flux through
     one gate set at one thickness epoch while the velocity changes
     epoch by epoch, so a real thinning at the gate is not in the
     series; the receipt's discharge rule block says so.
   - **The formal error on the discharge is a lower bound.** The
     velocity product's own guide calls its error fields
     unrealistically low and asks that they be read with the image
     pair count as qualitative metrics; the thickness error is the
     product's own field, which neither guide states to be
     independent between cells, so it is summed along a gate as fully
     correlated.
   - **The gate set is a rule.** Where it is drawn decides what is
     inside it, and half the spread of the discharges under other
     rules is the systematic the bar would carry; where the root
     records no such sensitivity the systematic is stated as zero with
     that reason, which is a statement about the record and not about
     the ice.
   - **The domains of the three methods are not the same ice.** The
     peripheral glaciers sit inside the velocity product's land ice
     mask and a margin spanning gate set would include them, while the
     closure's altimetry domain separates them; the two estimates do
     not cover the same ice without a stated reconciliation. Cite
     `knowledge/nsidc/gotchas/ice-sheet-boundaries-and-drainage-basins.md`.
   - **The method needs no firn term**, which is its one advantage
     over the altimetric method, and it buys that with two model
     dependencies instead: the climate model behind the surface mass
     balance and the mass conservation inversion behind the thickness.
     The bookkeeping states both.
   - **This is not a NASA, JPL or NSIDC product.** The concept says so
     and so does a report.

## Must NOT

- Never quote a number from a receipt the attester has not passed, and
  never edit the sanctioned executor or attester.
- Never present a fixture number as an ice sheet's mass rate,
  discharge or surface mass balance. No real-data estimate exists in
  this bundle, and the fixture's values are planted.
- Never present a refusal as a number, and never work around one by
  dropping a node, widening a gate set, substituting a thickness or
  supplying a surface mass balance from outside the root.
- Never quote a discharge from a gate set that does not span the
  grounded margin as an ice sheet's discharge.
- Never report the concept's statements as settled: it is a draft
  until the maintainer signs it, and the report says so.
- Never restate the published assessment's rates or its technique
  spread as numbers of this run; cite the assessment dataset concept
  by bundle path.
- Never convert a mass rate to a sea level equivalent here; cite the
  podaac recipe and the ocean-science skill that own it.
- Never state a number this release owns. Every figure in a report
  comes from the receipt or from the concept, cited by bundle path.
- Never commit a receipt, an attestation or a generated fixture to
  this repository.
