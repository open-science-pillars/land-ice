---
type: Attested Computation
spheres: [cryosphere]
title: "Ice sheet mass balance closure from GRACE-FO mascons against altimetric volume change with a firn correction (attested)"
description: "Sanctioned closure of one ice sheet's mass balance over a stated window: the JPL mascon sum over the ice sheet's land mascons against the altimetric volume change less the GEMB firn air content change times a stated ice density, each as the mean of its annual-lag differences with an interval, the residual formed on the epochs both methods share, the bar its own half width plus the stated mascon selection systematic, a verdict closed_within_uncertainty, the GIA, low-degree, frame, smoothing, firn and density statements as receipt facts, and a refusal (exit 3, never a number) for a window outside the terms' overlap, an ice sheet without a firn term over its altimetry domain, or a window across the GRACE to GRACE-FO gap without continuity evidence. Proven on a synthetic fixture with a planted residual and anchored on a Greenland run over 2003 through 2016 from the stamped data root, read against the IMBIE 2023 assessment. The committed root carries both altimetry terms, the ITS_LIVE elevation change and ICESat-2 ATL15, and a Greenland window they share is run on each: the two rates differ by 80 Gt per year and the verdict turns on which is used."
tags: [ice-sheet, mass-balance, closure, greenland, antarctica, grace, grace-fo, mascons, altimetry, atl15, its-live, firn, gemb, attested]
runtime: python
parameters:
  - { name: ice_sheet, type: string, required: true }
  - { name: window, type: string, required: true }
  - { name: altimetry, type: string, required: false }
  - { name: ice_density, type: number, required: false }
  - { name: bridge, type: string, required: false }
computation: skills/ice-mass-change/scripts/ice_sheet_balance.py
executor:
  resource: skills/ice-mass-change/scripts/ice_sheet_balance.py
  receipt: [run_id, computation, code_sha256, capability, bundle, runtime, generated_utc, data, bound_parameters, refused, window, terms, series, rates, residual, combined_uncertainty, verdict, bookkeeping, caveats]
attester:
  resource: skills/ice-mass-change/scripts/ice_sheet_balance_check.py
generated: { by: knowledge-seeder/claude, at: 2026-09-15T20:00:00Z }
verified:
  - { by: human:PaulMRamirez, at: 2026-09-16T03:06:45Z, role: maintainer, source: https://github.com/open-science-pillars/nasa-daac-knowledge/pull/176 }
  - { by: human:PaulMRamirez, at: 2026-09-16T05:50:55Z, role: maintainer, source: https://github.com/open-science-pillars/nasa-daac-knowledge/pull/183 }
  - { by: human:PaulMRamirez, at: 2026-09-19T08:36:53Z, role: maintainer, source: https://github.com/open-science-pillars/nasa-daac-knowledge/pull/201 }
  - { by: human:PaulMRamirez, at: 2026-09-19T20:09:02Z, role: maintainer, source: https://github.com/open-science-pillars/nasa-daac-knowledge/pull/204 }
status: draft
stale_after: 2027-03-15
sources:
  - id: gotcha-firn
    resource: knowledge/nsidc/gotchas/atl15-height-change-is-not-mass-change.md
    title: "Bundle gotcha: a height change becomes a mass change only after the firn air content change is removed and a density applied, each with its own uncertainty"
  - id: atl15
    resource: knowledge/nsidc/datasets/icesat2-atl15.md
    title: "Bundle dataset concept: ICESat-2 ATL15 gridded land ice height change, the reduced resolutions and their error fields, ice_area"
  - id: its-live
    resource: knowledge/nsidc/datasets/its-live-ice-velocity.md
    title: "Bundle dataset concept: the MEaSUREs ITS_LIVE products, the project whose elevation change files supply the altimetry and firn terms"
  - id: bedmachine
    resource: knowledge/nsidc/datasets/bedmachine-greenland-antarctica.md
    title: "Bundle dataset concept: BedMachine, the thickness a discharge through flux gates would need (not read by this computation)"
  - id: gotcha-gate
    resource: knowledge/nsidc/gotchas/bedmachine-mask-and-grounding-line.md
    title: "Bundle gotcha: a discharge gate sits on grounded ice upstream of the grounding line"
  - id: gotcha-thickness
    resource: knowledge/nsidc/gotchas/bedmachine-thickness-is-interpolated.md
    title: "Bundle gotcha: the thickness between flight lines is mass conservation or an interpolation, and a discharge carries both factors' errors"
  - id: gotcha-basins
    resource: knowledge/nsidc/gotchas/ice-sheet-boundaries-and-drainage-basins.md
    title: "Bundle gotcha: a per-region number names the boundary set it used"
  - id: gotcha-grid
    resource: knowledge/nsidc/gotchas/polar-stereographic-not-latlon.md
    title: "Bundle gotcha: a sum on a polar stereographic grid needs the true cell area"
  - id: mascons
    resource: knowledge/podaac/datasets/grace-fo-mascons.md
    title: "Podaac bundle dataset concept: GRACE/GRACE-FO JPL mascon solutions, RL06.3 version 4, the mass term's product and its per-mascon uncertainty"
  - id: gotcha-gia
    resource: knowledge/podaac/gotchas/grace-gia-correction.md
    title: "Podaac bundle gotcha: the GIA model already applied to the mascon product"
  - id: gotcha-leakage
    resource: knowledge/podaac/gotchas/grace-coastal-leakage.md
    title: "Podaac bundle gotcha: leakage across the coastline in the mascons"
  - id: gotcha-gap
    resource: knowledge/podaac/gotchas/grace-intermission-gap.md
    title: "Podaac bundle gotcha: the GRACE to GRACE-FO gap and the missing months"
  - id: gotcha-low-degree
    resource: knowledge/podaac/gotchas/grace-low-degree-replacements.md
    title: "Podaac bundle gotcha: the degree-1 and C20/C30 series substituted in the mascon product"
  - id: slb
    resource: knowledge/podaac/computations/sea-level-budget.md
    title: "Podaac bundle attested computation: the sea level budget closure whose shape (terms, bookkeeping as receipt facts, fixture, refusal, attester) this computation keeps"
  - id: data-root
    resource: ../references/retrieval/ice-sheet-balance-root/RECORD.json
    title: "The stamped data root committed in this package: the loaders' stamps, the bookkeeping and closure tables, the manifest of the term files, and SOURCES.json for the downloads, including the two ATL15 attempts an egress policy refused before the third succeeded"
  - id: loaders
    resource: ../../skills/ice-mass-change/scripts/isb_data_root.py
    title: "The term loaders and the stamp assembler in the ice-mass-change skill's scripts (isb_mass_mascons.py, isb_volume_itslive.py, isb_volume_atl15.py, isb_firn_gemb.py, isb_smb_gemb.py, isb_data_root.py), each with a selftest"
  - id: provider-series
    resource: https://podaac.jpl.nasa.gov/dataset/GREENLAND_MASS_TELLUS_MASCON_CRI_TIME_SERIES_RL06.3_V4
    title: "JPL GRACE and GRACE-FO Greenland mass time series, RL06.3Mv04 CRI (PO.DAAC), the provider's own sum the mass stamp is cross-checked against; the Antarctica series is its sibling collection"
  - id: otosaka-2023
    resource: https://doi.org/10.5194/essd-15-1597-2023
    title: "Otosaka and others (2023), Mass balance of the Greenland and Antarctic ice sheets from 1992 to 2020, Earth System Science Data 15, 1597 to 1616 (IMBIE): the reconciled rates by period and the spread between altimetry, gravimetry and the input-output method"
  - id: smith-2020
    resource: https://doi.org/10.1126/science.aaz5845
    title: "Smith and others (2020), Pervasive ice sheet mass loss reflects competing ocean and atmosphere processes, Science 368, 1239 to 1242: the reference conversion of altimetric height change to mass with a firn model"
---

# Ice sheet mass balance closure from GRACE-FO mascons against altimetric volume change with a firn correction (attested)

The sanctioned computation behind any receipted statement that an
ice sheet's mass balance closes, or does not, between gravimetry and
altimetry over a window: the JPL mascon sum over the ice sheet's
mascons against the altimetric volume change converted to mass with
the GEMB firn air content change and a stated density, in the shape
of the podaac bundle's sea level budget closure.[^slb][^gotcha-firn]
It exists so that the conversion the ATL15 gotcha demands (a firn
model, a density, the GIA and elastic bookkeeping) is a set of receipt
facts an attester checks rather than a paragraph a reader trusts, and
so that the residual between the two observing systems is a stated
number with a stated bar. Version 1 is proven on a synthetic fixture
with a planted residual, and its real-data anchor is the stamped data
root committed beside it, run for Greenland over 2003 through 2016 in
the reference run below.[^data-root] The third estimate the
intercomparison literature uses, the input-output balance from a
surface mass balance and a discharge through flux gates, is not made
here; the boundaries section says why and names what would make it.

## Parameters

- `ice_sheet` (string, required): `greenland` or `antarctica`.
- `window` (string, required): an inclusive month range
  `YYYY-MM:YYYY-MM` of at least two years within the overlap of the
  terms (the committed root's Greenland overlap is 2002-04 through
  2023-12; the fixture's is 2003-01 through 2023-12 for the ITS_LIVE
  term and 2019-01 through 2023-10 for the ATL15 term).
- `altimetry` (string, optional, default `itslive`): the volume
  term's product, `itslive` (the ITS_LIVE elevation change, monthly)
  or `atl15` (ICESat-2 ATL15, quarterly); a root without the named
  term refuses.
- `ice_density` (number, optional, default 917): kilograms per cubic
  metre applied to the firn-corrected volume change; the default is
  the ice density the GEMB surface mass balance product itself uses,
  and a run may state another.
- `bridge` (string, optional): a citation of the independent
  continuity evidence across the GRACE to GRACE-FO gap; required for
  a window whose mass months lie on both sides of 2017-07 through
  2018-05.[^gotcha-gap]

## The terms and the bookkeeping

**Gravimetry.** The JPL RL06.3 version 4 CRI mascon grid summed over
the ice sheet's land mascons per solution month, in gigatonnes, with
the product's one-sigma-per-mascon uncertainty combined in quadrature
over the selected mascons.[^mascons] The Greenland set is the land
mascons whose land area is at least a quarter Greenland ice by the
ITS_LIVE Greenland mask binned onto the mascon grid with true cell
areas, 27 mascons of 2,122,549 square kilometres of land in the
committed root; the Antarctic set is every land mascon south of 60 S,
148 mascons, the CRI land mask counting the floating shelves as land.
A mascon that straddles Nares Strait or Denmark Strait cannot be
split by any rule, so the mass stamp lists every selected mascon with
its ice fraction, the four excluded land mascons that carry some
Greenland ice, and the full-series trend under two other thresholds
(minus 268.1 Gt per year at 5 percent, minus 244.3 at 50 percent,
against minus 252.0 at the rule's 25 percent); half that spread,
11.9 Gt per year, is the selection systematic the bar carries. The
stamp also records the comparison with the provider's own Greenland
series over the same 257 months (trends minus 252.0 and minus 255.8
Gt per year, a standard deviation of 29.0 Gt between the two after
the mean offset), read for the comparison only and never used to
adjust the sum.[^provider-series][^data-root] The GIA model
(ICE-6G_D, subtracted by the product), the low-degree series (C20 and
C30 from TN-14, degree 1 from JPL's mascon-consistent geocenter), the
reference frame and the mascon smoothing are stated in the mass stamp
as the product applied them, nothing re-applied, and travel in the
receipt's `bookkeeping.mass` block; the coastal leakage the CRI
filter reduces and does not remove is why the selection systematic is
stated beside the formal error.[^gotcha-gia][^gotcha-low-degree][^gotcha-leakage]

**Altimetry.** The volume anomaly of the surface height change summed
with true cell areas over the ice sheet's cells, less the firn air
content volume anomaly at the same epochs over the same domains,
times the stated ice density: one kilometre cubed is density over a
thousand gigatonnes.[^gotcha-firn][^gotcha-grid] The committed
root carries both volume terms, so the parameter chooses between two
independent altimetric records over the window they share. The
ITS_LIVE Greenland elevation change is monthly, 1992 through 2023,
the same file and the same fixed cell sets of 464,999 ice sheet and
23,827 peripheral glacier cells as the firn term. The ATL15 term is
quarterly, 2019-01 through 2026-01, the Version 5 10 km GL granule
summed over the 20,016 cells whose ice_area is above zero at every
epoch, one undivided region of 1,748,582 km2 covering the ice sheet
and the peripheral ice caps together.[^its-live][^atl15][^data-root]
The two altimetry domains are therefore not the same cell set, and
neither is the firn domain: the firn term is subtracted over the
ITS_LIVE cell sets, 1,822,362 km2 in total, which is 4.2 percent
larger than the ATL15 region. Scaling the firn rate by the area ratio
moves the ATL15 altimetric rate of the run below by 2.8 Gt per year,
small against that run's bar of 154 and not nothing; it is a property
of this root, where one firn product serves two volume grids, and not
of either product.[^data-root] The
firn term is the earlier seed's root: the GEMB 1.3.0 firn air content
anomaly against 2014-01-01 with the GEMB to GSFC-FDM spread as its
uncertainty, a spread that crosses zero on 29 ice sheet rows, so each
row's uncertainty is floored at the series median of its domain
(0.109 m for the ice sheet, 0.072 m for the peripheral glaciers) and
the receipt says so in `bookkeeping.firn_floor`.[^data-root] Antarctica
has no grounded firn term in this root (the ITS_LIVE distribution
carries GEMB output over the floating shelves only), so the Antarctic
run refuses rather than states a volume as a mass; its mascon and
grounded volume terms are in the root for the day a grounded firn
loader lands.

**The rate method.** Each term's rate over the window is the mean of
its annual-lag differences (the value at an epoch less the value
twelve months earlier, so the seasonal cycle cancels exactly and a
monthly mascon hole removes only the differences it touches). Its
interval takes the effective sample size from the lag-1
autocorrelation of the differences, floored at the number of
non-overlapping years (differences a year apart share no epoch),
Student's t on the effective degrees of freedom, and the larger of
the sampling error and the formal error the per-epoch uncertainties
propagate; the receipt states which one the interval rests on. The
residual is the mean of altimetry minus gravimetry differences on the
epochs both terms carry, so the interannual signal both observing
systems see cancels before its scatter is measured, and the bar is
the residual's own half width plus the selection systematic. The
verdict `closed_within_uncertainty` is true when the residual lies
within that bar. A residual that fails to close is read as a
correction-consistency finding before a missing-physics one: the firn
model and its forcing, the density, the mascon selection and the
altimetry record's mission transitions are the first things a reader
audits, in the bookkeeping block.[^gotcha-firn][^slb]

## The fixture and its known truth

`--fixture --seed N` generates the root deterministically from a
hash-based Gaussian stream (no numeric library in the path): a
Greenland-like sheet losing 250 Gt per year with a 120 Gt annual
cycle peaking in April, an AR(1) interannual component and monthly
mascon noise of 20 to 30 Gt, the mascon months the real record lacks
removed (the gap and the battery-management months the sea level
budget fixture lists); a firn air volume losing 6 cubic kilometres
per year with a 45 cubic kilometre cycle and a stated uncertainty
drawn from |N(0.08, 0.06)| metres so that it crosses zero and the
floor rule is exercised; a monthly ITS_LIVE-shaped volume from 1992
and a quarterly ATL15-shaped one from 2019, each the ice volume plus
the firn air plus noise, with the altimetric rate exceeding the
gravimetric one by a planted +5 Gt per year; and an Antarctic-like
sheet with mass and volume but no grounded firn term. The receipt
records the seed, the fixture digest and the generator's digest (the
executor itself), and the attester regenerates the fixture and
compares every series value.

## The refusal rule

A run writes a refusal receipt (`refused: true`, a `reason_code` and
the reason in words) and exits 3, never a number, when the window
lies outside the overlap of the terms it needs
(`window-outside-overlap`); when the window is shorter than two years
or a term has too few epochs in it, or too few annual-lag differences
are common to both terms (`too-few-epochs`); when the firn term does
not cover the altimetry domain (`firn-term-missing`, the Antarctic
case on this root); when the root does not carry the altimetry
product named (`term-not-in-root`); when the mass months lie on both
sides of the inter-mission gap with no bridge (`gap-without-bridge`);
or when a rate's interval cannot be stated (`interval-not-stated`).
The attester attests a refusal PASS only as a refusal, reproduced
by re-running the executor's own assembly and compute on the
regenerated fixture, or on the tree when `--data-root` names it;
without the tree, a data-root refusal is reproduced from the spans
and domains the receipt records where it can be
(`window-outside-overlap`, `firn-term-missing`, `term-not-in-root`,
`gap-without-bridge`) and taken on the executor's word otherwise.
The verdict line reads `PASS refusal`.

## The attester criterion (deterministic, consumer-side)

A run PASSES only when all hold, one `PASS name` or `FAIL name:
reason` line per check: every declared field present; the code hash
is the sanctioned file; the `bundle` block names this package's
name, version and release lock digest and the `capability` block
is well formed; a runtime is named; the fixture regenerated at the
receipt's seed hashes to the receipt's digest (for a data root, the
RECORD stamp, its digest and the term file digests are present, and
with `--data-root DIR` each matches the tree and the tree's own
RECORD manifest, and the recorded root is that tree
package-relative; the executor itself refuses a term file whose
digest is not the manifest's); the four series are well formed, the
altimetric mass is the density times the volume less the firn air at
every epoch, the firn uncertainties are floored, the residual series
is the difference of the two terms' annual-lag differences on their
common epochs, and every value is what the regenerated fixture
yields, or with `--data-root` what the tree's term files rebuild
through the executor's own assembly; every rate block, the residual
block, the selection systematic, the bar and the verdict recompute
from the series by a second implementation of the method
statement; the bookkeeping
carries every required statement, the density and firn floor blocks
agree with the bound parameters and the series, and the gap handling
agrees with the mass months; and on the fixture the known truth
holds (the verdict says closed, each rate within 15 and 20 Gt per
year of the imposed ones, the residual within the larger of 5 Gt per
year and the bar of the planted one), while on a data root each rate
lies inside stated plausibility bounds. The verdict is scatter-forgiving by
construction: the bar is the residual's own half width, so it grows
with the disagreement it measures (2003 through 2016 closes at a bar
of 141 while 2010 through 2016 fails at 94), and a closed verdict
over a long window says the two records agree in the mean, not that
they agree year by year. The selftest covers two fixture passes,
eleven tampers each failing on its check, a wrong release, a
tampered computation, all six refusals and a forged one, a bridged
run across the gap and the same receipt with its bridge stripped, and
the data-root path on the fixture written as a root: attested against
the tree, refused by the executor when a term file drifts from the
manifest, failed against another tree when the manifest is rewritten,
and failed on its series when they are tampered.

## The data root, for a real run

A computation is a skill (ADR E in the marketplace repository), so this concept lives in the capability that runs it and the executor, the attester and the loaders are the scripts of the skill named in `computation` above, `ice-mass-change`. The `SKILL.md` beside them is the run procedure. The executor's usage text (`--help`) states the fixture run, the refusal rule and the receipt path, the attester's usage text states how a receipt is attested, and this section keeps the one part of the procedure that is contract and not procedure, the layout of the data root the executor reads.

The real run's tree is committed at
knowledge/references/retrieval/ice-sheet-balance-root, built by the
loaders in the skill's scripts (isb_firn_gemb.py and isb_smb_gemb.py
for the GEMB terms, isb_mass_mascons.py for the mascon grid,
isb_volume_itslive.py for the ITS_LIVE elevation change,
isb_volume_atl15.py for ATL15, each with `--selftest`) and stamped by
isb_data_root.py, which writes RECORD.json with the bookkeeping and
closure tables from the loaders' stamps; SOURCES.json records the
downloads, including the two attempts at the ATL15 granules that an
egress policy refused before the third succeeded. This is the layout the computation reads.
`--data-root DIR` in place of `--fixture`:

```
DIR/
  RECORD.json           the stamp: record name, manifest_sha256, verified_utc,
                        terms_present, terms_absent, the loaders' stamps and the
                        bookkeeping table with its closure section
  mass.csv              ice_sheet, domain (land_mascons), month, value_gt,
                        uncertainty_gt, ...   one row per ice sheet and solution month
  firn.csv              ice_sheet, domain, month, value_m, uncertainty_m, volume_km3,
                        area_km2, ...          the firn root of the earlier seed
  volume-itslive.csv    ice_sheet, domain, month, value_km3, uncertainty_km3,
                        uncertainty_correlated_km3, area_km2, ..., sampling, product
  volume-atl15.csv      the same columns from ATL15, quarterly, one undivided
                        Greenland region and the four Antarctic quadrants summed
  smb.csv               the surface mass balance term (ice shelves only; not read
                        by this computation)
  <term>-stamp.json     one stamp per term file
  SOURCES.json          the downloads, with URL, hash and time
```

Months are `YYYY-MM`, unique per ice sheet and domain; a quarterly row
is one product epoch labelled by its month. The executor reads only
these files, never a product file, refuses a term file whose digest
is not the RECORD manifest's, and copies the RECORD summary, its
digest and the term file digests into the receipt; the data root is
recorded package-relative so the run id is the same on any machine.
`RECORD.json` must carry, under `bookkeeping`, the mass term's `gia`,
`low_degree`, `reference_frame`, `effective_smoothing`, `selection`
and `uncertainty_basis`, the volume term's `reference`, `mask`,
`uncertainty_basis` and `not_mass`, the firn term's `reference`,
`uncertainty_basis`, `gemb_version` and `forcing`, and a `closure`
table for both ice sheets; the attester refuses a receipt missing any
of them.

Which loader produces each file:

- `mass.csv`: the CRI-filtered mascon grid summed over the ice sheet's
  land mascons per solution month, in gigatonnes, with the per-mascon
  formal error in quadrature; the Greenland set is the land mascons
  whose land is at least a quarter Greenland ice by the ITS_LIVE mask,
  the Antarctic set every land mascon south of 60 S, and the stamp
  records the selection's sensitivity and the comparison with the
  provider's own series ([the mascon concept in the podaac bundle](knowledge/podaac/datasets/grace-fo-mascons.md)).
- `firn.csv` and `smb.csv`: the GEMB firn air content and surface
  mass balance terms of the earlier seed, unchanged in value.
- `volume-itslive.csv`: the ITS_LIVE surface elevation change summed
  to a volume anomaly over the same cell sets as the firn term
  (Greenland) and over the grounded Antarctic product's cells from
  2003 on ([the velocity and elevation change products](knowledge/nsidc/datasets/its-live-ice-velocity.md)
  are the same project's).
- `volume-atl15.csv`: the ATL15 10 km delta_h summed with ice_area
  ([the ATL15 concept](knowledge/nsidc/datasets/icesat2-atl15.md)); the loader
  needs an Earthdata Login and a route to the NSIDC cloud archive,
  which the archive serves by redirecting a token-bearing request to a
  content distribution host.

## Reference run

**Fixture run (seed 7, Greenland, 2019-01 through 2022-12, the ATL15
term, measured 2026-09-15).** 48 mascon months and 16 quarterly
altimetry epochs; 12 annual-lag differences common to both.
Gravimetry minus 252.790 Gt per year, 95 percent interval [minus
274.535, minus 231.044] on the sampling error; altimetry minus
245.189, [minus 386.044, minus 104.335] on the formal error, which
the floored firn spread dominates; residual +15.729 against a bar of
142.670 (the residual's half width, the selection systematic being
zero on a synthetic root); `closed_within_uncertainty` true, the
planted +5 recovered within the bar. **Fixture run (seed 7,
Greenland, 2003-01 through 2016-12, the ITS_LIVE term).** 152 mascon
months and 168 altimetry epochs, 128 common differences; gravimetry
minus 250.649, [minus 261.184, minus 240.113]; altimetry minus
243.821, [minus 285.038, minus 202.603]; residual +7.999 against a
bar of 44.971; closed. The imposed truth is gravimetry minus 250 and
a residual of +5. The refusal case the gate exercises is the ATL15
window 2019-01 through 2025-12 (outside the fixture's firn term,
exit 3, attested as a refusal); the Antarctic refusal
(`firn-term-missing`) is exercised on the committed root. The two
fixture runs are the cases `ice-sheet-balance` and
`ice-sheet-balance-long` of the golden
verification/ice_sheet_balance.py, which runs them on every change.

**Real-data run (the stamped data root
ice-sheet-balance-root-2026-09-19, Greenland, 2003-01 through
2016-12, the ITS_LIVE term, run sha256:72008644b500e242 under the
runtime claude-code, measured 2026-09-15, rerun 2026-09-19 and rerun
at this package's paths 2026-09-20).** Every number below is the
number first measured; the run identifier moved twice, because it
binds the data root's manifest, which gained the ATL15 term, and
then the package block and the package-relative data root, which the
move changed. It was sha256:5f704e13835ccc00 in the provider bundle.
151 of 168 mascon months (the 17 missing are June
2003 and the battery-management months the product's list names),
168 altimetry epochs, 127 common differences. Gravimetry minus
281.297 Gt per year, 95 percent interval [minus 328.727, minus
233.867] on the sampling error (the year-to-year variability of the
rate; the formal error at 95 percent is 3.99); altimetry minus
283.353, [minus 387.747, minus 178.959] on the sampling error (formal
44.83, the floored firn spread); a volume rate of minus 364.4 cubic
kilometres per year of which minus 55.4 is firn air. On the 127
common epochs the altimetry mean is minus 306.421 and the gravimetry
mean minus 281.297, so the residual is minus 25.123 Gt per year
against a bar of 140.813 (the residual's half width 128.879, its
sampling error 58.5 on 12.0 effective years, plus the selection
systematic 11.934); `closed_within_uncertainty` true. The two rates
agree in the mean to 2 Gt per year on their own epochs, but the
residual series scatters by 203 Gt per year from month to month: the
two records disagree at the annual scale by hundreds of gigatonnes
per year, and the receipt's series say which term carries each
spike. At 2010-01 the annual-lag volume difference is minus 994
cubic kilometres per year while the firn air difference is minus 78
(the sheet-wide volume anomaly falls 400 cubic kilometres between
2009-06 and 2010-01 while the firn air anomaly falls 82), so the
altimetric loss reads minus 840 Gt per year against the mascons'
minus 309: that interval, from the end of ICESat in October 2009 to
the start of CryoSat-2 in July 2010, is where the ITS_LIVE record
rests on Envisat alone, so the 2010 spike belongs to the volume term
and its mission transition, which the volume stamp cannot confirm
because the product records no per-epoch mission composition. At
2013-01 the volume difference is minus 494 and the firn air
difference minus 297 (between 2012-06 and 2012-09 the volume drops
468 cubic kilometres and the firn air anomaly 479, GEMB's response to
the July 2012 melt), so the firn correction cancels most of the
surface lowering and the altimetric loss reads minus 180 against the
mascons' minus 516: the 2013 spike belongs to the firn term. Mascon
leakage is the least likely carrier, the mascon term's annual-lag
scatter being 112 Gt per year and the provider's series matching it
to 29 Gt. Against the IMBIE
2023 assessment, whose Table 2 gives Greenland minus 180 with an
uncertainty of 39 Gt per year for 2002 to 2006, minus 280 with 38 for
2007 to 2011 and minus 213 with 40 for 2012 to 2016 (an average near
minus 228 over 2003 to 2016) and whose 2003 to 2018 overlap gives a
reconciled minus 221 with an uncertainty of 22 with the three
techniques within a standard deviation of 19 Gt per year of each
other, both rates here sit about 55 Gt per year more negative,
outside the assessment's uncertainty and inside the interval each
rate carries; the provider's own Greenland series (header trend minus
259.8 with 21.0 one sigma over 2002 to 2026; minus 255.8 by the same
least squares over the same 257 months) is 4 Gt per year more
negative than the mass stamp's sum, and over 2003 through 2016 its
annual-lag mean is minus 285.4 against this sum's minus 281.3, so the
offset from the assessment is a property of the mascon product and
the selection rule, not of this
sum.[^otosaka-2023][^provider-series][^data-root] The
registry entry `ice-sheet-balance-record` reruns it, and the check
chain the pull request names verifies the stamp, reruns the executor
on the data root and attests the receipt against the tree on every
change.

**The two altimetry records over the window they share (Greenland,
2019-01 through 2023-10, the widest window both terms and the firn
term cover, measured 2026-09-19 under the runtime claude-code).** The
gravimetric side is the same run on both, minus 220.962 Gt per year,
because the parameter changes only the altimetric term. On ITS_LIVE
the altimetric rate is minus 66.832 Gt per year, [minus 241.030,
+107.367], and the residual is +154.131, [+62.117, +246.145], against
a bar of 103.948, so `closed_within_uncertainty` is false (run
sha256:997d29f8051fcc40, sha256:c22e7623a3fd9bd7 in the provider
bundle). On ATL15 it is minus 146.812, [minus
370.152, +76.528], and the residual is +88.944, [minus 53.248,
+231.135], against a bar of 154.126, so the verdict is true (run
sha256:d266b6889b36af96, sha256:0782898ea9b8f1a2 in the provider
bundle).

Read this carefully, because the verdict flips and the two records do
not formally disagree. The altimetric rates differ by 80.0 Gt per
year, ATL15 the more negative and the nearer both to the gravimetric
rate and to every published Greenland rate for these years, which is
what the boundaries below suspected. But their intervals overlap over
most of their length, so this is not a measurement of a discrepancy
between the two records: it is one record sitting where the mascons
sit and the other not. The bars differ too, and for a reason worth
stating: ATL15's quarterly epochs give 20 of them against ITS_LIVE's
58 monthly ones, yet the residual's effective sample size is larger
on ATL15 (14.0 against 6.3), because the monthly ITS_LIVE differences
are strongly autocorrelated (lag-1 +0.777). So the wider ATL15 bar
comes from fewer epochs and the narrower ITS_LIVE bar from epochs
that are not independent, and the flip in the verdict is carried by
the residual falling from +154 to +89 as much as by the bar. The
firn domain mismatch stated above moves the ATL15 rate a further 2.8
Gt per year in the same direction and is not corrected here.

**Pass bar.** There is no measured tolerance to record: the verdict
is a comparison of the residual against the bar the receipt itself
carries, and the attester recomputes both. The plausibility bands on
the fixture (15 and 20 Gt per year around the imposed rates, the
larger of 5 Gt per year and the bar around the planted residual) are
sanity bounds on the chain, not a science tolerance.

**Re-homed on 2026-09-20, and left draft until it is re-signed.** This
concept, the executor, the attester, the six loaders and the stamped
data root moved out of the provider bundle and into this package, the
capability that runs them, under ADR E. Nothing about any number
changed: the code, the root and the reference values were re-homed and
re-run, not revised. Every run this section states was reproduced at
the new paths on 2026-09-20 under the runtime claude-code and attested,
to the digit: both fixture runs, the fixture overlap refusal, the
record run over 2003-01 through 2016-12, the Antarctic refusal, the two
altimetry records over 2019-01 through 2023-10, and the five further
windows the boundaries section quotes. Only the run identifiers moved,
because a run identifier binds the package block and the
package-relative data root and both changed with the move; the old
identifiers are recorded beside the new ones above. The status is
draft, and the signature events below are the provider steward's on the
text as it stood in the bundle; the maintainer re-signs this concept in
this package after the move merges, which is what a signature over a
moved digest owes.

## Boundaries

One real-data run is the anchor, Greenland over 2003 through 2016, a
window that does not cross the inter-mission gap; a run across the
gap needs a bridge citation and has not been made. The anchor's
closure is a cancellation of two halves of opposite sign: 2003
through 2009 gives a residual of minus 82 against a bar of 201
(closed) and 2010 through 2016 gives +109 against 94 (not closed,
gravimetry minus 324 against altimetry minus 203). The windows after
2019 on this root do not close either: 2019 through 2022 gives +136
against 117, 2019 through 2023 gives +157 against 103 with gravimetry
minus 223 against altimetry minus 66 (a volume rate of minus 148
cubic kilometres per year of which minus 76 is firn air), and 2020
through 2023 gives +139 against 138. The provider's mascon series
tracks the loader's sum in every window (minus 329 against minus 324
over 2010 through 2016, minus 228 against minus 223 over 2019 through
2023), so the term that drifts is the ITS_LIVE elevation change with
its GEMB firn correction, whose altimetric rate after 2019 is far
from every published Greenland rate; the closure verdict is window
dependent, and the altimetry term is the suspect. Those windows are
all ITS_LIVE runs: on ATL15 the 2019 through 2023-10 window closes,
which is the first independent evidence for that reading rather than
an inference from the mascons alone. Antarctica refuses on this
root for want of a grounded firn air content term: the ITS_LIVE
distribution carries GEMB output over the floating shelves only, and
the RACMO2 and MAR alternates the firn stamp names were not read; a
loader for one of them on the grounded sheet would make the Antarctic
run without any change to the executor.[^data-root] The
input-output balance is not made: the root holds no Greenland surface
mass balance and no grounded Antarctic one, and no discharge, which
would take the ITS_LIVE velocity mosaics across flux gates on
grounded ice upstream of the grounding line with BedMachine
thickness, where the thickness between flight lines is mass
conservation or an interpolation with errbed saying which and the
Antarctic guide's mass-conservation threshold is 30 metres per
year;[^its-live][^bedmachine][^gotcha-gate][^gotcha-thickness] the
published input-output estimates the reader compares against are
IMBIE's input-output group, which in Greenland agrees with altimetry
and gravimetry over 2003 to 2018 within the 19 Gt per year spread
quoted above.[^otosaka-2023] Both altimetry terms are now in
the root and the run above puts them side by side over 2019-01
through 2023-10: ATL15 gives an altimetric rate 80 Gt per year more
negative than ITS_LIVE and the closure closes on it, which supports
the reading here without settling it, because the two rates'
intervals overlap. ATL15 begins in 2019, so it cannot test the
ITS_LIVE record before then, and the pre-2019 anchor stands on
ITS_LIVE alone.
The Greenland altimetry domain is the ITS_LIVE mask (the ice sheet
and the peripheral glaciers) and the gravimetry domain is a set of
whole mascons that also hold ice-free land, coastal ocean and, at
the rule's threshold, a share of the Canadian Arctic and Iceland
signal; the residual carries that mismatch, and the selection
systematic is its stated size.[^gotcha-basins][^gotcha-leakage] The
firn uncertainty is a two-model spread, floored, not a formal error;
the density is one number for the whole sheet; no elastic or GIA
correction is applied to the altimetry, and the mascon product's GIA
model is stated, not varied. The intervals on the term rates are
dominated by the year-to-year variability of the rate itself (the
sampling error) and are not measurement uncertainties in the
assessment's sense; the formal error stands beside each. Produced by
Open Science Pillars, not a NASA, JPL or NSIDC product.

**Verification.** The bundle-path sources are the nsidc and podaac
bundles' own concepts in the provider bundle; the data root and its
stamp are committed in this package and the real-data run was made
and attested on 2026-09-15 from them.[^data-root][^loaders] The mascon
granule, the provider's two mass series and the three ITS_LIVE files
were read on 2026-09-15 and their hashes are in SOURCES.json, as are
the ATL15 access attempts with their status codes; Otosaka and others
2023 was read in full on 2026-09-15 through its Crossref record's
link after the DOI resolved, and its record (title, authors, journal,
volume, pages, year) was verified against the Crossref registry the
same day, as was Smith and others 2020, whose text the ATL15 gotcha
read on 2026-09-13 and which is cited here on its registry
record.[^otosaka-2023][^smith-2020] The chain is verified on every
change by the golden verification/ice_sheet_balance.py, which the
goldens workflow runs: the attester's selftest, the two fixture runs
and the fixture refusal, the loaders' selftests, the data root check,
the record run attested against the tree, the Antarctic refusal and
the two altimetry records over the window they share.

[^gotcha-firn]: knowledge/nsidc/gotchas/atl15-height-change-is-not-mass-change.md, the conversion and its terms
[^atl15]: knowledge/nsidc/datasets/icesat2-atl15.md, the product the ATL15 loader reads
[^its-live]: knowledge/nsidc/datasets/its-live-ice-velocity.md, the ITS_LIVE project whose elevation change files supply the altimetry and firn terms
[^bedmachine]: knowledge/nsidc/datasets/bedmachine-greenland-antarctica.md, the thickness a discharge would need
[^gotcha-gate]: knowledge/nsidc/gotchas/bedmachine-mask-and-grounding-line.md
[^gotcha-thickness]: knowledge/nsidc/gotchas/bedmachine-thickness-is-interpolated.md
[^gotcha-basins]: knowledge/nsidc/gotchas/ice-sheet-boundaries-and-drainage-basins.md
[^gotcha-grid]: knowledge/nsidc/gotchas/polar-stereographic-not-latlon.md
[^mascons]: knowledge/podaac/datasets/grace-fo-mascons.md, the mass term's product
[^gotcha-gia]: knowledge/podaac/gotchas/grace-gia-correction.md
[^gotcha-leakage]: knowledge/podaac/gotchas/grace-coastal-leakage.md
[^gotcha-gap]: knowledge/podaac/gotchas/grace-intermission-gap.md
[^gotcha-low-degree]: knowledge/podaac/gotchas/grace-low-degree-replacements.md
[^slb]: knowledge/podaac/computations/sea-level-budget.md, the pattern this computation keeps
[^data-root]: knowledge/references/retrieval/ice-sheet-balance-root/RECORD.json and SOURCES.json, the stamped data root
[^loaders]: skills/ice-mass-change/scripts, the term loaders and the stamp assembler
[^provider-series]: JPL GRACE and GRACE-FO Greenland mass time series, RL06.3Mv04 CRI, PO.DAAC
[^otosaka-2023]: Otosaka and others (2023), Earth System Science Data 15, doi:10.5194/essd-15-1597-2023
[^smith-2020]: Smith and others (2020), Science 368, doi:10.1126/science.aaz5845
