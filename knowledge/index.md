---
okf_version: "0.2"
---

# land-ice bundle

This capability's own knowledge bundle. OKF v0.2 conformant
(okf_version "0.2" above).

## Attested computations

A computation is a skill (ADR E in the marketplace repository's
docs/decisions): the concept lives in the capability that runs it, its
executor and attester are the scripts of the skill beside it, a golden
under `verification/` proves each of those scripts, and the stamped
data root the executor reads is committed here as data. Both concepts
below came in from the `nsidc` bundle of nasa-daac-knowledge on
2026-09-20 with every reference run reproduced at the new paths, and
both are draft until the maintainer re-signs them, because a signature
covers the digests a concept names.

- [computations/ice-sheet-balance.md](computations/ice-sheet-balance.md),
  the mass balance closure from GRACE and GRACE-FO mascons against the
  altimetric volume change with a firn correction. Run by the
  `ice-mass-change` skill, whose scripts hold its executor, its
  attester and the six loaders that built its root; proven by
  `verification/ice_sheet_balance.py`.
- [computations/ice-sheet-input-output.md](computations/ice-sheet-input-output.md),
  the mass balance by the input-output method, surface mass balance in
  and gate discharge out. Run by the `ice-sheet-input-output` skill,
  whose scripts hold its executor, its attester and the four loaders
  that built its root; proven by
  `verification/ice_sheet_input_output.py`. What the concept is signed
  for is the method and its refusals: its record run refuses, so no
  real-data estimate exists to quote.

## The stamped data roots, as data

`references/retrieval/ice-sheet-balance-root` and
`references/retrieval/ice-sheet-input-output-root` are the recorded
trees the two executors read: `RECORD.json` with each term's stamp, the
manifest and the bookkeeping table, one CSV per term, one stamp per
term file, and `SOURCES.json` with the downloads and the granules that
could not be fetched. They are evidence for a signed number and carry
no runnable file. An executor refuses a term file whose digest is not
the RECORD manifest's, so nothing is computed on a tree that drifted
from its stamp.

## Provider bundles (declared dependencies)

**nasa-daac-knowledge, the `nsidc` bundle** (the National Snow and Ice
Data Center's ice sheet, sea ice and ice velocity products). Canonical
home:
[nasa-daac-knowledge](https://github.com/open-science-pillars/nasa-daac-knowledge),
`knowledge/nsidc/` in that repository. It is declared under
`dependencies.knowledge` in `.osp/package.yaml` with a version floor
(the plugin manifests are rendered from that file, never edited), so
it installs with this capability.

The provider bundle is the authority on products and this capability is
the authority on methods. The dataset, gotcha and recipe concepts the
two computations rest on stay there and are cited by bundle path,
`knowledge/nsidc/<type>/<concept>.md`; on a conflict about a fact
about a product the provider concept wins, `stable` outranks `draft`,
and a draft is voiced as a draft. Nothing from that bundle is copied
here. The core skill `consult-knowledge` finds every installed bundle
through the installer's record.

What the two computations cite there, and never restate, are the
bundle's `datasets/icesat2-atl15.md`,
`datasets/its-live-ice-velocity.md`,
`datasets/bedmachine-greenland-antarctica.md`,
`datasets/firn-model-air-content.md`,
`datasets/imbie-ice-sheet-assessment.md`, its gotchas
`atl15-height-change-is-not-mass-change.md`,
`firn-air-content-spread-dominates-the-altimetric-mass-rate.md`,
`bedmachine-thickness-is-interpolated.md`,
`bedmachine-mask-and-grounding-line.md`,
`velocity-mosaic-epochs-and-gaps.md`,
`ice-sheet-boundaries-and-drainage-basins.md`,
`polar-stereographic-not-latlon.md` and
`assessment-method-groups-are-not-independent.md`, and its recipes
`ice-sheet-balance.md` and `ice-sheet-input-output.md`, which say how
to read what a run returns.

**nasa-daac-knowledge, the `podaac` bundle**, reached through the same
dependency. The mass term of the closure is the JPL mascon product,
whose concept and gotchas live there
(`datasets/grace-fo-mascons.md`, `gotchas/grace-gia-correction.md`,
`gotchas/grace-coastal-leakage.md`,
`gotchas/grace-intermission-gap.md`,
`gotchas/grace-low-degree-replacements.md`). The recipe that turns an
ice sheet mass rate into a sea level equivalent is owned there too, by
`recipes/grace-mass-to-sea-level.md`. The receipted budget that carries
the ocean mass term is not in the bundle: it is the attested
computation `ocean-science/knowledge/computations/sea-level-budget.md`,
which the ocean-science capability's `sea-level-budget` skill runs.
This capability cites that route in words and runs neither, so two
capabilities never quote the same number.
