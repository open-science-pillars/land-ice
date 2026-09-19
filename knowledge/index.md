---
okf_version: "0.2"
---

# land-ice bundle

This capability's own knowledge bundle. OKF v0.2 conformant
(okf_version "0.2" above).

## It holds no concepts

There is nothing to list below, and that is the release rather than an
omission. This is a wrap-only release (ADR D in the marketplace
repository's docs/decisions): the capability wraps attested
computations that are already signed in a provider bundle and computes
nothing of its own, so it owns no scientific claim and states no
convention a provider does not already state. Every concept its skills
consult lives in the provider bundle named below and arrives as a
declared dependency, never as a copy.

A concept belongs here when the capability itself owns the convention:
a rule about how this discipline's workflows are run that no provider
bundle states, decided and signed here. The first such concept is
listed here when it lands, and the knowledge-linter flags a concept
unreachable from this page.

## Provider bundles (declared dependencies)

**nasa-daac-knowledge, the `nsidc` bundle** (the National Snow and Ice
Data Center's ice sheet, sea ice and ice velocity products). Canonical
home:
[nasa-daac-knowledge](https://github.com/open-science-pillars/nasa-daac-knowledge),
`knowledge/nsidc/` in that repository. It is declared under
`dependencies.knowledge` in `.osp/package.yaml` with a version floor
(the plugin manifests are rendered from that file, never edited), so
it installs with this capability.

How it is consulted: the core skill `consult-knowledge` finds every
installed bundle through the installer's record; the skills here cite
provider concepts by bundle path,
`knowledge/nsidc/<type>/<concept>.md`, and reach the sanctioned
executors and attesters under `knowledge/nsidc/references/`. On a
conflict the provider concept wins, `stable` outranks `draft`, and a
draft is voiced as a draft. Nothing from that bundle is copied here.

What the skills of this release wrap:

- `knowledge/nsidc/computations/ice-sheet-balance.md`, wrapped by the
  `ice-mass-change` skill. Signed stable in the provider bundle.
- `knowledge/nsidc/computations/ice-sheet-input-output.md`, wrapped by
  the `ice-sheet-input-output` skill. It is `status: draft` in the
  provider bundle at the release this capability declares a floor on,
  and the skill voices it as a draft on every run, as the conflict
  rule above requires.

The concepts those two rest on, and which the skills cite rather than
restate, are the bundle's `datasets/icesat2-atl15.md`,
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
`ice-sheet-balance.md` and `ice-sheet-input-output.md`.

**nasa-daac-knowledge, the `podaac` bundle**, reached through the same
dependency. The mass term of the closure is the JPL mascon product,
whose concept and gotchas live there
(`datasets/grace-fo-mascons.md`, `gotchas/grace-gia-correction.md`,
`gotchas/grace-coastal-leakage.md`,
`gotchas/grace-intermission-gap.md`,
`gotchas/grace-low-degree-replacements.md`). The sea level equivalent
of an ice sheet mass rate is owned there too, by
`recipes/grace-mass-to-sea-level.md` and the attested computation
`computations/sea-level-budget.md`, which the ocean-science
capability's `sea-level-budget` skill wraps. This capability cites
that route in words and wraps neither, so two capabilities never
quote the same number.
