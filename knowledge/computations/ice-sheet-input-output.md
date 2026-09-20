---
type: Attested Computation
spheres: [cryosphere]
title: "Ice sheet mass balance by the input-output method: surface mass balance in, gate discharge out (attested)"
description: "Sanctioned third estimate of one ice sheet's mass rate over a stated window: the surface mass balance over the grounded domain less the discharge through a named flux gate set, the discharge formed node by node as the ice density times the velocity normal to the gate times the node width over the projection's areal scale times the thickness, each rate the mean of its annual epochs with an interval, the mass rate their difference epoch by epoch, the bar its own half width plus the stated gate systematic, a verdict on whether the mass rate is distinguishable from zero, the product, mask, gate and uncertainty statements as receipt facts, and a refusal (exit 3, never a number) for a gate node whose thickness is an interpolation, a gate node the thickness mask does not call grounded, a gate set that does not span the grounded margin, a velocity epoch family or window the root does not cover, and an ice sheet whose grounded surface mass balance term is absent. Proven on a synthetic fixture with a planted discharge and surface mass balance; the committed root carries the real ITS_LIVE gate velocities and refuses, because the thickness product is unreachable from the drafting environment and no grounded surface mass balance is distributed by any NASA archive."
tags: [ice-sheet, mass-balance, input-output, discharge, flux-gate, greenland, antarctica, its-live, velocity, bedmachine, thickness, surface-mass-balance, attested]
runtime: python
parameters:
  - { name: ice_sheet, type: string, required: true }
  - { name: window, type: string, required: true }
  - { name: gates, type: string, required: true }
  - { name: velocity_epoch, type: string, required: false }
  - { name: ice_density, type: number, required: false }
computation: skills/ice-sheet-input-output/scripts/ice_sheet_input_output.py
executor:
  resource: skills/ice-sheet-input-output/scripts/ice_sheet_input_output.py
  receipt: [run_id, computation, code_sha256, capability, bundle, runtime, generated_utc, data, bound_parameters, refused, window, gates, terms, series, rates, residual, combined_uncertainty, verdict, bookkeeping, caveats]
attester:
  resource: skills/ice-sheet-input-output/scripts/ice_sheet_input_output_check.py
generated: { by: knowledge-seeder/claude, at: 2026-09-19T08:00:00Z }
verified:
  - { by: human:PaulMRamirez, at: 2026-09-19T08:08:31Z, role: maintainer, source: https://github.com/open-science-pillars/nasa-daac-knowledge/pull/198 }
  - { by: human:PaulMRamirez, at: 2026-09-19T08:36:53Z, role: maintainer, source: https://github.com/open-science-pillars/nasa-daac-knowledge/pull/201 }
status: draft
stale_after: 2027-03-19
sources:
  - id: closure
    resource: ice-sheet-balance.md
    title: "This package's attested computation: the ice sheet mass balance closure, whose gravimetric and altimetric estimates this method is the third of, and whose shape (terms, bookkeeping as receipt facts, fixture, refusal, attester) this computation keeps"
  - id: slb
    resource: knowledge/podaac/computations/sea-level-budget.md
    title: "Podaac bundle attested computation: the sea level budget closure the whole pattern descends from"
  - id: its-live
    resource: knowledge/nsidc/datasets/its-live-ice-velocity.md
    title: "Bundle dataset concept: the MEaSUREs ITS_LIVE regional velocity mosaics (NSIDC-0776), their variables, their error fields and the map-unit convention"
  - id: gotcha-mosaic
    resource: knowledge/nsidc/gotchas/velocity-mosaic-epochs-and-gaps.md
    title: "Bundle gotcha: an annual mosaic is a composite with its own effective date and count, and a discharge needs thickness from another product"
  - id: bedmachine
    resource: knowledge/nsidc/datasets/bedmachine-greenland-antarctica.md
    title: "Bundle dataset concept: BedMachine Greenland Version 6 and BedMachine Antarctica Version 4, their thickness, errbed, source and mask fields and their nominal years"
  - id: gotcha-thickness
    resource: knowledge/nsidc/gotchas/bedmachine-thickness-is-interpolated.md
    title: "Bundle gotcha: thickness between flight lines is mass conservation or an interpolation, with source, dataid and errbed saying which, and a gate in the slow interior rests on a model quantity"
  - id: gotcha-gate
    resource: knowledge/nsidc/gotchas/bedmachine-mask-and-grounding-line.md
    title: "Bundle gotcha: a discharge gate sits on grounded ice upstream of the grounding line, and the mask is what places it"
  - id: gotcha-basins
    resource: knowledge/nsidc/gotchas/ice-sheet-boundaries-and-drainage-basins.md
    title: "Bundle gotcha: a per-region number names the boundary set it used"
  - id: gotcha-grid
    resource: knowledge/nsidc/gotchas/polar-stereographic-not-latlon.md
    title: "Bundle gotcha: the grids are polar stereographic metres and a sum without the true ground scale biases a total"
  - id: imbie
    resource: knowledge/nsidc/datasets/imbie-ice-sheet-assessment.md
    title: "Bundle dataset concept: the published multi-method assessment, what it reports per ice sheet and period, what its input-output group is and how far the three technique groups spread"
  - id: gotcha-groups
    resource: knowledge/nsidc/gotchas/assessment-method-groups-are-not-independent.md
    title: "Bundle gotcha: an assessment's method groups are not independent measurements of the same thing"
  - id: firn
    resource: knowledge/nsidc/datasets/firn-model-air-content.md
    title: "Bundle dataset concept: the firn model air content term, which the altimetric method needs and the input-output method does not"
  - id: data-root
    resource: ../references/retrieval/ice-sheet-input-output-root/RECORD.json
    title: "The stamped data root committed in this package: the velocity term, the gate table, the absent terms with their reasons, and SOURCES.json for the downloads and the granules that could not be fetched"
  - id: loaders
    resource: ../../skills/ice-sheet-input-output/scripts/iio_data_root.py
    title: "The term loaders and the stamp assembler in this skill's scripts (iio_velocity_itslive.py, iio_thickness_bedmachine.py, iio_smb_gemb.py, iio_data_root.py), each with a selftest"
  - id: closure-root
    resource: ../references/retrieval/ice-sheet-balance-root/SOURCES.json
    title: "The closure's own committed root in this package, whose search established that the ITS_LIVE distribution carries no Greenland surface mass balance field and no grounded Antarctic firn field"
  - id: nsidc-0776-guide
    resource: https://nsidc.org/sites/default/files/documents/user-guide/nsidc-0776-v002-userguide.pdf
    title: "MEaSUREs ITS_LIVE Regional Glacier and Ice Sheet Surface Velocities, Version 2 user guide (NSIDC): the variable table, the coverage statement, the map-unit convention and its flux gate implication, and the error computation section, read in full 2026-09-19"
  - id: gardner-2018
    resource: https://doi.org/10.5194/tc-12-521-2018
    title: "Gardner and others (2018), Increased West Antarctic and unchanged East Antarctic ice discharge over the last 7 years, The Cryosphere 12, 521 to 547: the reference flux-gate discharge computation, 1929 gigatonnes per year in 2015 with an uncertainty of 40, record and abstract verified against the Crossref registry 2026-09-19"
---

# Ice sheet mass balance by the input-output method (attested)

The sanctioned computation behind any receipted statement of an ice
sheet's mass rate by the third of the three satellite methods: the
surface mass balance that falls on the grounded ice, less the ice
that leaves it through a flux gate, over a stated window. The
bundle's closure already makes the other two, gravimetry and
firn-corrected altimetry, and its own boundaries section names this
one as not made; this computation is that gap closed as far as the
data reachable from the drafting environment allows.[^closure] It
keeps the closure's shape, which is the sea level budget's: terms
assembled from a stamped data root, bookkeeping as receipt facts
rather than prose, a deterministic fixture with a planted answer, a
refusal instead of a number wherever the inputs do not support one,
and a consumer-side attester that recomputes every
term.[^slb][^closure]

The method's one advantage over the altimetric method is that it
needs no firn term. An altimetric mass rate is a height change that
becomes a mass only after a firn air content model is subtracted and
a density applied, and in this bundle's closure that model spread is
what dominates the altimetric rate's formal error.[^firn][^closure]
An input-output rate touches the firn nowhere: the surface mass
balance is already a mass and the discharge is a thickness times a
velocity. It buys that with two other model dependencies, the
regional climate model behind the surface mass balance and the mass
conservation inversion behind the thickness, which the bookkeeping
states.[^gotcha-thickness][^imbie]

## Parameters

- `ice_sheet` (string, required): `greenland` or `antarctica`.
- `window` (string, required): an inclusive month range
  `YYYY-MM:YYYY-MM` of at least two years, covered by the velocity
  and surface mass balance epochs, with at least three epochs common
  to both.
- `gates` (string, required): the name of the gate set in the data
  root. A gate set is a table of nodes, each with a position, a unit
  normal, a width along the gate and the projection's areal scale at
  it; the root's gate table states the rule that placed them, whether
  the set spans the ice sheet's grounded margin, and which product's
  mask decided that a node is grounded.
- `velocity_epoch` (string, optional, default `annual`): the epoch
  family of the velocity term, `annual` (one mosaic per calendar
  year) or `static` (the record mean mosaic). A root without the
  named family refuses.[^gotcha-mosaic]
- `ice_density` (number, optional, default 917): kilograms per cubic
  metre applied to the volume flux through the gate; the default is
  the density the GEMB products themselves use.

## The terms and the bookkeeping

**Surface mass balance.** The product's own rate over the ice sheet's
grounded domain, in gigatonnes per year, positive for mass gained at
the surface, read from the root's `smb.csv` at the product's native
sampling and aggregated to each velocity epoch's calendar year as the
period weighted mean of the steps in it; the uncertainty is the
period weighted mean of theirs, the steps treated as fully correlated
within the year. A root whose surface mass balance covers other ice
than the grounded sheet does not supply this term and the run
refuses, because an input-output balance differences a grounded
discharge and a shelf accumulation is not its input.

**Discharge.** At every node of the gate set, the ice density times
the velocity component along the gate's normal times the node width
divided by the projection's areal scale at the node times the
thickness at the node, summed over every node of every gate, in
gigatonnes per year and positive for ice leaving.[^gotcha-grid] The
node uncertainty is the velocity error times the thickness and the
velocity times the thickness error, in quadrature; the node errors
are summed along a gate as fully correlated, because neither product
states a spatial correlation for its error field, and the gates are
combined in quadrature. Two properties of the thickness decide
whether a node may carry a flux at all, and both are read from the
thickness product's own per-cell fields rather than assumed: the
method that made the pixel must be mass conservation, since a flux
through a kriged or interpolated thickness is a model quantity the
method was not built to conserve, and the mask at the node must be
grounded ice, since the discharge of an ice sheet is the flux across
the grounding line and ice that has passed it has already left the
sheet.[^gotcha-thickness][^gotcha-gate] A node that fails either is a
refusal, not a number.

**The velocity's map units.** The velocity mosaics state their
velocities in map units, and the Version 2 user guide says the
distortion of up to a few percent was not corrected as it was in
Version 1, and that a flux gate cross section therefore no longer
needs to be corrected for projection scale
distortion.[^nsidc-0776-guide][^its-live] A map velocity times a map
width is the ground flux times the projection's areal scale, so the
two readings differ by that factor. This computation divides by the
areal scale and states the ground flux; the areal scale at every node
travels in the term file and in the receipt's gate block, so a reader
who prefers the guide's reading multiplies it back. On the committed
root's Greenland gate set the areal scale runs from 0.9784 to 1.0684,
so the two readings differ by up to about 7 percent of a node's
flux.[^data-root][^gotcha-grid]

**The rate method.** Each term's rate over the window is the mean of
its annual epochs. Its interval takes the effective sample size from
the lag-1 autocorrelation of the series over epochs one year apart,
clipped to at least one and at most the number of epochs, Student's t
on the effective degrees of freedom, and the larger of the sampling
error and the formal error; the per-epoch uncertainties are treated
as fully correlated across epochs, because the thickness error and
the surface mass balance model error do not resample from one year to
the next, so the formal error of the mean is the mean of them and not
their quadrature. The mass rate is the surface mass balance less the
discharge at each epoch and then the mean, so a year both terms carry
differences two numbers measured in the same year before the mean is
taken, as the closure's residual does on the epochs both its methods
carry.[^closure] The bar is the mass rate's own half width plus the
stated gate systematic, half the spread of the full-series discharges
the velocity stamp records under the other gate rules where it
records any, and zero with the reason where it records none. The
verdict `significant_at_confidence` is true when the magnitude of the
mass rate exceeds that bar, with `sign` reading `loss`, `gain` or
`indistinguishable`.

## The fixture and its known truth

`--fixture --seed N` generates the root deterministically from a
hash-based Gaussian stream (no numeric library in the path): a
Greenland-like sheet whose gate set `synthetic-outlets` spans its
margin with 8 gates of 31 nodes at 2 km, a thickness profile from 600
to 1100 metres, and a discharge planted at 480 gigatonnes per year in
2005 rising by 2 a year with an AR(1) component, the node velocities
scaled at each epoch so that the gate sum is exactly the planted
discharge; a quarterly surface mass balance of 400 gigatonnes per
year with an AR(1) component and a seasonal cycle of 900 that cancels
exactly over four quarters, so the annualisation is exercised; a gate
set `synthetic-interior` whose thickness is an interpolation at a
third of its nodes; a gate set `synthetic-shelf` with a node on
floating ice; a gate set `synthetic-partial` that does not span the
margin; and an Antarctic-like sheet with both discharge factors and
no grounded surface mass balance, as the real root has none. The
receipt records the seed, the fixture digest and the generator's
digest (the executor itself), and the attester regenerates the
fixture and rebuilds every term from its rows.

## The refusal rule

A run writes a refusal receipt (`refused: true`, a `reason_code` and
the reason in words) and exits 3, never a number, when a term the
balance needs is not in the root (`term-not-in-root`); when the root
carries no rows for the ice sheet and gate set named
(`gate-set-not-in-root`); when it carries no rows in the velocity
epoch family named (`velocity-epoch-not-in-root`); when the gate set
does not span the ice sheet's grounded margin, so no sheet wide rate
can be formed from it (`gate-set-incomplete`); when the thickness at
any node was not made by mass conservation
(`gate-thickness-interpolated`); when the thickness product's mask
does not call any node grounded ice (`gate-not-grounded`); when the
ice sheet's grounded surface mass balance term is absent
(`smb-term-missing`); when the window lies outside the epochs the
terms cover (`window-outside-epochs`); when the window is shorter
than two years or fewer than three epochs are common to both terms
(`too-few-epochs`); or when a rate's interval cannot be stated
(`interval-not-stated`). The attester attests a refusal PASS only as
a refusal, reproduced by re-running the executor's own assembly and
compute on the regenerated fixture, or on the tree when `--data-root`
names it; without the tree, a data-root refusal is reproduced from
the gate sets, domains, epoch families and spans the receipt records
where it can be, and taken on the executor's word otherwise. The
verdict line reads `PASS refusal`.

## The attester criterion (deterministic, consumer-side)

A run PASSES only when all hold, one `PASS name` or `FAIL name:
reason` line per check: every declared field present; the code hash
is the sanctioned file; the `bundle` block names this bundle's
package, version and release lock digest and the `capability` block
is well formed; a runtime is named; the fixture regenerated at the
receipt's seed hashes to the receipt's digest, or for a data root the
RECORD stamp, its digest and the term file digests are present and,
with `--data-root DIR`, match the tree and the tree's own manifest;
the gate block names the bound gate set, the set spans the margin,
every node is mass conservation on grounded ice, and the node and
gate counts and the thickness range recompute from the term files;
the three series are well formed on the same epochs, the mass rate
series is the surface mass balance less the discharge at every epoch,
the per gate discharges add to the total, and the discharge and the
surface mass balance rebuild from the term rows by a second
implementation of the discharge and annualisation rules; every rate
block, the gate systematic, the bar, the residual block and the
verdict recompute from the series by a second implementation of the
method statement; the bookkeeping carries every required statement
and its density, discharge, annualisation and epoch handling blocks
agree with the bound parameters and the series; and on the fixture
the known truth holds (each rate within 30 and 40 gigatonnes per year
of the planted one and the mass rate within the larger of 45 and the
bar), while on a data root each rate and the gate thicknesses lie
inside stated plausibility bounds. The selftest covers two fixture
passes, thirteen tampers each failing on its check, two wrong-release
tampers, a tampered computation, all eight fixture refusals and a
forged one,
and the data-root path on the fixture written as a root: attested
against the tree, refused by the executor when a term file drifts
from the manifest, failed against another tree when the manifest is
rewritten, failed on its series when they are tampered, refused as
`term-not-in-root` when the thickness term is removed, and refused as
`interval-not-stated` when the surface mass balance never moves.

## The data root, for a real run

A computation is a skill (ADR E in the marketplace repository), so
this concept lives in the capability that runs it and the executor,
the attester and the loaders are the scripts of the skill named in
`computation` above, `ice-sheet-input-output`. The `SKILL.md` beside
them is the run procedure. The executor's usage text (`--help`)
states the fixture run, the refusal rule and the receipt path, and
this section keeps the part of the procedure that is contract and not
procedure, the layout of the data root the executor reads.

The tree is committed at
knowledge/references/retrieval/ice-sheet-input-output-root, built by
the loaders in this skill's scripts (iio_velocity_itslive.py for the
gate velocities and the gate geometry, iio_thickness_bedmachine.py
for the thickness and the method that made each pixel,
iio_smb_gemb.py for the surface mass balance, each with `--selftest`)
and stamped by iio_data_root.py, which writes RECORD.json with the
bookkeeping, gate and closure tables from the loaders' stamps;
SOURCES.json records the downloads and the granules that could not be
fetched.[^loaders][^data-root] `--data-root DIR` in place of
`--fixture`:

```
DIR/
  RECORD.json        the stamp: record name, manifest_sha256, verified_utc,
                     terms_present, terms_absent, the loaders' stamps and the
                     bookkeeping table with its gate and closure sections
  velocity.csv       ice_sheet, gate_set, gate, node, x_m, y_m, normal_x,
                     normal_y, width_m, areal_scale, epoch, sampling,
                     v_normal_m_per_yr, v_normal_error_m_per_yr,
                     speed_m_per_yr, count   one row per node and epoch
  thickness.csv      ice_sheet, gate_set, gate, node, x_m, y_m, thickness_m,
                     thickness_error_m, source_code, provenance, mask_code,
                     mask                    one row per node
  smb.csv            ice_sheet, domain, month, value_gt_per_yr,
                     uncertainty_gt_per_yr, mean_m_ice_per_yr, period_years,
                     area_km2, n_cells, sampling
  <term>-stamp.json  one stamp per term file
  SOURCES.json       the downloads, with URL, hash and the time read
```

Epochs are `YYYY-MM`; an annual velocity mosaic is one composite
labelled by the January of its year, and a quarterly surface mass
balance step is labelled by the month of its time value. The executor
reads only these files, never a product file, refuses a term file
whose digest is not the RECORD manifest's, and copies the RECORD
summary, its digest and the term file digests into the receipt; the
data root is recorded package-relative so the run id is the same on
any machine. `RECORD.json` must carry, under `bookkeeping`, the
velocity term's product, grid, mask, aggregation, sampling,
uncertainty basis and map units, the thickness term's product, grid,
nominal year, mask, source variable, uncertainty basis and provenance
rule, the surface mass balance term's product, grid, mask,
aggregation, sampling, uncertainty basis and sign convention, and the
gate and closure tables; the attester refuses a receipt missing any
of them. The velocity and thickness terms sit on one node table: the
velocity loader derives it and writes it into `velocity.csv`, and the
thickness loader samples the thickness product at those same nodes,
so the two factors of a node's flux are the same point on the ground
by construction.

## Reference run

**Fixture run (seed 7, Greenland, the gate set `synthetic-outlets`,
2005-01 through 2014-12, measured 2026-09-19).** 10 annual epochs on
248 nodes over 8 gates. Surface mass balance +400.086 gigatonnes per
year, 95 percent interval [+343.532, +456.640] on the formal error;
discharge +490.809, [+437.847, +543.771] on the formal error; mass
rate minus 90.723 against a bar of 67.518 (the mass rate's own half
width, the gate systematic being zero on a synthetic root);
`significant_at_confidence` true, `sign` loss. The planted values are
a surface mass balance of 400 and a discharge of 480 rising by 2 a
year from 2005, which over this window is 489.0, so the recovered
mass rate of minus 90.7 sits 1.7 gigatonnes per year from the planted
minus 89.0. **Fixture run (seed 7, Greenland, the same gate set,
1995-01 through 2018-12).** 24 epochs; surface mass balance +384.323,
[+328.688, +439.957]; discharge +486.912, [+437.938, +535.885]; mass
rate minus 102.589 against a bar of 63.873; loss. The cases
`ice-sheet-input-output` and `ice-sheet-input-output-long` of
the golden verification/ice_sheet_input_output.py runs are these two
fixture runs. The refusal the
check chain exercises on the fixture is the window 2021-01 through
2023-12, outside the surface mass balance epochs
(`window-outside-epochs`, exit 3, attested as a refusal).

**Real-data run (the stamped data root
ice-sheet-input-output-root-2026-09-19, Greenland, 2014-01 through
2023-12, the gate set `greenland-outlets-v1`, measured 2026-09-19):
a refusal, not a number.** The committed root carries the velocity
term and nothing else, so the record run refuses with
`term-not-in-root` naming the thickness term and the reason it is
absent, exits 3, and attests `PASS refusal` against the tree as run
sha256:54f634aa61a18415 under the runtime `record` (the run id
depends on the runtime name, so the same run under `goldens` in the
golden carries its own; at this package's paths under the runtime
`record` it is sha256:81ee7cd5fd476242, because the identifier binds
the package block and the package-relative data root and the move
changed both). The golden
verification/ice_sheet_input_output.py runs it and requires the
refusal and its attestation. What the root does carry
is stated below, because the gate geometry and the gate velocities
are real and only the thickness at those nodes is missing.

**Pass bar.** There is no measured tolerance to record: the verdict
is a comparison of the mass rate against the bar the receipt itself
carries, and the attester recomputes both. The plausibility bands on
the fixture (30 gigatonnes per year on the discharge, 40 on the
surface mass balance, the larger of 45 and the bar on the mass rate)
are sanity bounds on the chain, not a science tolerance.

**Re-homed on 2026-09-20, and left draft until it is re-signed.** This
concept, the executor, the attester, the four loaders and the stamped
data root moved out of the provider bundle and into this package, the
capability that runs them, under ADR E. Nothing about any number
changed: the code, the root and the reference values were re-homed and
re-run, not revised. Every run this section states was reproduced at
the new paths on 2026-09-20 and attested, to the digit: both fixture
runs, the fixture window refusal, and the record run, which refuses
with `term-not-in-root` as it did in the bundle and attests `PASS
refusal` against the tree. Only the run identifiers moved, because a
run identifier binds the package block and the package-relative data
root and both changed with the move; the old identifier is recorded
beside the new one above. The status is draft, and the signature
events below are the provider steward's on the text as it stood in the
bundle; the maintainer re-signs this concept in this package after the
move merges, which is what a signature over a moved digest owes.

## What the committed root holds, and what it lacks

**The velocity term is real.** The gate set `greenland-outlets-v1` is
derived from the ITS_LIVE annual mosaic of 2015 for the Greenland
Periphery region (RGI05A) by the rule the velocity stamp states: the
grounded margin is every cell with the mosaic's land ice mask set and
its floating ice mask clear that touches a cell which is not, in the
four-neighbourhood; the seeds are the fastest such cells in order,
each at least 25 km from every seed already taken, up to twelve of
them above 500 metres per year; and each gate is the straight segment
through its seed perpendicular to the seed's flow direction, 3 km on
each side, sampled at the 120 m posting and clipped to the land ice
mask. The velocity normal to each gate is then sampled from the
annual mosaics of 2014 through 2024, the years the user guide's
coverage statement puts after the point where annual coverage is
nearly complete for all regions.[^nsidc-0776-guide][^data-root] The
result is 12 gates of 286 nodes, 4 to 38 nodes apiece after 326 of
the 612 candidate nodes fell outside the land ice mask, over 11
annual epochs from 2014-01 to 2024-01, with 70 of the 3,146 node
epochs carrying no finite velocity and written as holes. The seeds
run from 9,972 to 17,337 metres per year, and the eleven granules
are named with their SHA-256 digests and the times they were read in
SOURCES.json; none of them is in the tree.[^data-root]

**The thickness term is absent for one reason, and it is an access
reason.** BedMachine Greenland Version 6 and BedMachine Antarctica
Version 4 are distributed only from the NSIDC cloud archive, which
answers a request for a granule with 302 to the login without a token
and, with one, 303 to a content distribution host that this
environment's egress policy refuses at the connection (the proxy
answers 403 to the CONNECT). Both granules were tried on 2026-09-19
and both were refused the same way; the root names the term absent
with that status and the host, and SOURCES.json records the
attempts.[^data-root][^bedmachine] Nothing about the product, the
version or the credential is at fault, and the block moves with the
environment rather than with the data.

**The surface mass balance term is absent for a different reason, and
it is a distribution reason.** No gridded surface mass balance over
the grounded Greenland ice sheet is distributed by any NASA archive
reachable from these sources: the ITS_LIVE Greenland elevation change
product carries firn air content anomalies and no surface mass
balance field, the only GEMB surface mass balance in the distribution
is masked to the floating Antarctic ice shelves, and a search of the
Common Metadata Repository on 2026-09-19 for a Greenland surface mass
balance returned one directory record with no data
distribution.[^closure-root][^data-root] The two regional climate
models the published assessment's input-output estimates rest on,
RACMO and MAR, are not NASA products.[^imbie] This is not an access
failure that a different network would fix.

**The gate set is provisional, and the product says why.** The
Greenland mosaic's floating ice mask carries no cell at all: over the
23,334 by 13,333 grid of the 2015 mosaic, 124,145,873 cells are land
ice and none are floating ice. A gate placed on that mask therefore
sits on the ice mask's margin, which is not the grounding line, and
the velocity product alone cannot tell a grounded node from a
floating one.[^gotcha-gate][^data-root] That is why the velocity
stamp records `spans_margin` false and `grounded_by` as the velocity
mosaic's own masks, and why the computation settles a node's
grounding from the thickness product's mask instead. With the
thickness term in place, the same gate set would be refused as
`gate-set-incomplete` until it is extended to span the margin, and
any node the thickness mask calls floating would be refused as
`gate-not-grounded`. The committed root's gate set is the geometry
the thickness loader will sample the day BedMachine is reachable, not
a gate set a discharge may be quoted from.

## Reading the three estimates

The input-output method is the third of three, and the reading this
concept exists for is the comparison of all three over the same
window against the published anchor. Two of the three are already
receipted in this bundle. Over 2003-01 through 2016-12 on its own
stamped root the closure gives a gravimetric rate of minus 281.297
gigatonnes per year and an altimetric rate of minus 283.353, a
residual of minus 25.123 against a bar of 140.813, closed within
uncertainty.[^closure] The third is not stated here, for the two
reasons above, and no number for it is invented.

The published anchor is the assessment's, and this bundle's dataset
concept owns its numbers: it reports Greenland by period and over the
full record, it reconciles the three technique groups by an
error-weighted mean, and it records that over 2003 to 2018 the three
Greenland technique rates lie within a standard deviation of 19
gigatonnes per year of each other against a reconciled uncertainty of
22.[^imbie] Three of its statements bear directly on what a run of
this computation should be read against. First, across all ice sheets
the input-output estimate is the most negative of the three groups
and altimetry the most positive, except in East Antarctica, where the
three disagree on even the sign of the change; so an input-output
rate that came out above the other two would be the surprise, not the
agreement.[^imbie] Second, the input-output estimates include the
peripheral glaciers and ice caps, the altimetry estimates exclude
them and gravimetry cannot separate them, which the assessment names
as a systematic bias between the techniques still to be
removed.[^imbie][^gotcha-basins] Third, only three input-output
estimates stand behind the Greenland group and one behind the
Antarctic, and only two surface mass balance models behind them all,
so the group is not a wide sample and its uncertainty shrinks by the
square root of a small count.[^imbie][^gotcha-groups]

Against that frame, the disagreement this bundle can already state is
between its own two estimates and the assessment: both of the
closure's rates sit about 55 gigatonnes per year more negative than
the assessment's reconciled rates for 2003 to 2016, outside the
assessment's uncertainty and inside the interval each rate
carries.[^closure][^imbie] A third estimate from this computation
would test whether that offset is a property of the two observing
systems the closure uses or of the reconciliation, and it is exactly
the number the thickness access and the surface mass balance
distribution gaps withhold. The reference flux-gate computation the
literature quotes, an Antarctic discharge of 1929 gigatonnes per year
in 2015 with an uncertainty of 40 through an optimized flux gate, is
the shape of the number this computation would produce for
Antarctica.[^gardner-2018]

## Boundaries

No real-data anchor exists: every number in the reference run above
is from the fixture, and the committed root's run is a refusal. The
computation is therefore proven as a chain and not as a measurement
of any ice sheet, and the concept says so rather than quoting the
fixture's planted values as if they were Greenland's.

The discharge is a flux through a gate set at a single thickness
epoch. The thickness is of the thickness product's nominal year, 2007
for Greenland and 2015 for Antarctica, while the velocity is of each
epoch's own mosaic, so the discharge series holds the thickness fixed
while the velocity changes and a real thinning at the gate is not in
it; the receipt states that in `bookkeeping.discharge_rule`.[^bedmachine]
An annual mosaic is a composite of image pairs with its own effective
date and count rather than a calendar mean, and the mosaics' error
fields are, in the user guide's own words, typically unrealistically
low and to be used with the image pair count as qualitative error
metrics, so the discharge's formal error is a lower
bound.[^gotcha-mosaic][^nsidc-0776-guide][^its-live] The thickness
error is the product's errbed, which neither guide states to be a
formal covariance or independent between cells, so it is summed along
a gate as fully correlated.[^gotcha-thickness]

The gate set is a rule, not a fact, in the same way the closure's
mascon selection is: where it is drawn decides what is inside it, and
half the spread of the discharges under the other rules is the
systematic the bar would carry. The committed root records no such
sensitivity, so the systematic is stated as zero with that reason,
and a later root that samples two gate rules gives the bar a real
term. A gate set that does not span the grounded margin cannot
produce an ice sheet wide rate at all, which the computation refuses
rather than reports, so the partial gate set that a handful of
outlets makes is not a mass balance.

Antarctica refuses on the committed root twice over: the root carries
no Antarctic velocity rows and no grounded Antarctic surface mass
balance, the second for the same distribution reason the closure's
own root records for its firn term.[^closure-root] The peripheral
glaciers of Greenland are inside the velocity product's land ice mask
and would be inside a margin-spanning gate set, while the closure's
altimetry domain separates them, so the two estimates would not cover
the same ice without a stated
reconciliation.[^gotcha-basins][^closure] Produced by Open Science
Pillars, not a NASA, JPL or NSIDC product.

**Verification.** The bundle-path sources are the nsidc and podaac
bundles' own concepts in the provider bundle; the data root and its
stamp are committed in this package and the velocity term was read on
2026-09-19 from the eleven ITS_LIVE annual mosaics whose URLs and
hashes SOURCES.json carries.[^data-root][^loaders] The Version 2 user
guide was read in full on 2026-09-19 and its hash is in SOURCES.json;
the collection records of NSIDC-0776, IDBMG4 and NSIDC-0756 were read
in the Common Metadata Repository the same day, and the DOIs
10.5067/JQ6337239C96, 10.5067/6B6B225B8V2D and 10.5067/POJQI54A45HX
were resolved on doi.org the same day, each answering 302 to its
product page; they are registered with DataCite and are not in
Crossref.[^nsidc-0776-guide][^its-live][^bedmachine] Gardner and
others 2018 was verified against the Crossref registry (title,
authors, journal, volume, pages, year) on 2026-09-19 and is cited on
its record and its registry abstract; the journal page was not
read.[^gardner-2018] The published assessment's numbers are the
dataset concept's and are cited from it, not restated from the
paper.[^imbie] The chain is verified on every change by the golden
verification/ice_sheet_input_output.py, which the goldens workflow
runs: the attester's selftest, the two fixture runs and the fixture
refusal, the loaders' selftests, the data root check and the record
run attested against the tree as a refusal.

[^closure]: knowledge/computations/ice-sheet-balance.md, the gravimetric and altimetric estimates and the shape this computation keeps
[^slb]: knowledge/podaac/computations/sea-level-budget.md, the pattern both closures descend from
[^its-live]: knowledge/nsidc/datasets/its-live-ice-velocity.md, the velocity mosaics
[^gotcha-mosaic]: knowledge/nsidc/gotchas/velocity-mosaic-epochs-and-gaps.md
[^bedmachine]: knowledge/nsidc/datasets/bedmachine-greenland-antarctica.md, the thickness product
[^gotcha-thickness]: knowledge/nsidc/gotchas/bedmachine-thickness-is-interpolated.md
[^gotcha-gate]: knowledge/nsidc/gotchas/bedmachine-mask-and-grounding-line.md
[^gotcha-basins]: knowledge/nsidc/gotchas/ice-sheet-boundaries-and-drainage-basins.md
[^gotcha-grid]: knowledge/nsidc/gotchas/polar-stereographic-not-latlon.md
[^imbie]: knowledge/nsidc/datasets/imbie-ice-sheet-assessment.md, the published multi-method assessment
[^gotcha-groups]: knowledge/nsidc/gotchas/assessment-method-groups-are-not-independent.md
[^firn]: knowledge/nsidc/datasets/firn-model-air-content.md
[^data-root]: knowledge/references/retrieval/ice-sheet-input-output-root/RECORD.json and SOURCES.json, the stamped data root
[^loaders]: skills/ice-sheet-input-output/scripts, the term loaders and the stamp assembler
[^closure-root]: knowledge/references/retrieval/ice-sheet-balance-root/SOURCES.json, the closure's own root and its searches
[^nsidc-0776-guide]: MEaSUREs ITS_LIVE Regional Glacier and Ice Sheet Surface Velocities, Version 2 user guide, NSIDC
[^gardner-2018]: Gardner and others (2018), The Cryosphere 12, doi:10.5194/tc-12-521-2018
