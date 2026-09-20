# Land Ice

This capability carries two attested ice sheet mass balance
computations and runs them. Each one is a concept under `knowledge/`
with its executor and its attester in the scripts of the skill beside
it, a golden under `verification/` that proves those scripts, and the
stamped data root it reads committed here as data. Every number a skill
here reports is owned by one of those concepts: the skill names it,
runs its sanctioned executor, runs the attester on the receipt before a
number is quoted, and reports the verdict, the run identifier, the
runtime and the caveats the concept states. The dataset and gotcha
concepts the two computations rest on stay in the NSIDC bundle of
[nasa-daac-knowledge](https://github.com/open-science-pillars/nasa-daac-knowledge),
which is the authority on those products and arrives as a declared
dependency. A capability that computed a number no concept here owns
would be domain expansion and waits on the decision that governs it.

A domain capability: discipline Land Ice inside the Cryosphere sphere.
Pillar means sphere, one of the five Earth science spheres; a
capability is skills, knowledge signed by its stewards and
deterministic checks, delivered as one plugin. The words used on this
page are defined in the
[glossary](https://github.com/open-science-pillars/marketplace/blob/main/GLOSSARY.md),
and the decision this release is made under is ADR E in
[marketplace/docs/decisions](https://github.com/open-science-pillars/marketplace/tree/main/docs/decisions).

## Install

On Claude Code:

```bash
claude plugin marketplace add open-science-pillars/marketplace
claude plugin install land-ice@open-science-pillars
```

What comes with it: `core`, the foundation capability, and
`nasa-daac-knowledge`, the provider bundle whose NSIDC and PO.DAAC
concepts the two computations here cite for their products. Both are
declared dependencies, so the installer brings them; nothing from
either is copied into this repository.

On Claude Cowork: add the marketplace by repository
(`open-science-pillars/marketplace`) under Customize > Plugins > Add
marketplace, then install the same capability from it; the shell
commands on this page are for Claude Code.

Local requirements: [uv](https://docs.astral.sh/uv/getting-started/installation/).
Every script a skill here invokes declares its dependencies in a PEP 723
header and runs as `uv run <script>`; uv builds the environment on
first run. Never `python script.py`, which skips the header. No account
and no credential are needed to run either chain on its fixture, and
no download is needed to run either on the data roots the provider
bundle commits.

## Runtimes

Which runtimes this release is qualified on is the table below,
rendered from the qualification records; what each word asserts is in
the marketplace repository's
[docs/runtime-distribution.md](https://github.com/open-science-pillars/marketplace/blob/main/docs/runtime-distribution.md).
This is a first release and carries no qualification record yet, so no
surface says supported.

<!-- osp-runtimes:start -->
Runtime support for land-ice 0.1.0 (release lock `sha256:be15726676f2`), rendered by build-kit's `osp.py advertise` from `.osp/surfaces.yaml` and the qualification records; edit those, not this block.

| Runtime | Role | Declared status | Qualification |
|---|---|---|---|
| Claude Code | development and runtime, required | supported | Qualified on 2026-09-19 |
| Claude Cowork | runtime, required | planned | Not qualified, waived for this release (Claude Cowork is not qualified for this first release. A Cowork record is a run by a person with Cowork in front of them, installing from the catalog, and the maintainer has not made one for 0.1.0; the coordinator cannot make one on their behalf because the runtime cannot be driven headlessly. Nothing about the capability is known to fail there: its projection renders and validates in the gate, and the Claude Code run passed every required test. The surface is simply not advertised until a run exists.; human:PaulMRamirez, 2026-09-19) |
| OpenAI Codex | runtime, required | planned | Not qualified, waived for this release (OpenAI Codex is not qualified for this first release. No release in this organization has been qualified on Codex yet: the Agent Plugins projection renders and passes plugin-check in the gate, but the Codex leg has never been exercised, so there is no procedure to run and nothing to record. The surface is not advertised, and the projection is published as conformant rather than as tested.; human:PaulMRamirez, 2026-09-19) |
| Claude Science | future runtime | limited-release | Outside the required matrix |

A runtime is advertised as supported only on a qualified record for this exact release; a release stays valid when a runtime is not qualified, and that runtime is simply not advertised.
<!-- osp-runtimes:end -->

## What's inside

- **Skills** (`skills/`, one `SKILL.md` each), the two that run a
  computation named for the workflow rather than for the product, and
  three that work over the receipts those two produce:

  - `ice-mass-change` runs
    `knowledge/computations/ice-sheet-balance.md`, whose executor,
    attester and six loaders are its `scripts/`: over one window and
    one ice sheet, the gravimetric mass rate from the mascon sum
    against the altimetric volume change less the firn air content
    change times a stated ice density, the residual on the epochs both
    methods share, the bar the receipt forms and the verdict. Its
    verdict is window dependent on the committed root and the skill
    reports the window it ran rather than a headline rate for the ice
    sheet; Antarctica refuses there for want of a grounded firn air
    content term, and the skill reports that refusal as a finding about
    the data.
  - `ice-sheet-input-output` runs
    `knowledge/computations/ice-sheet-input-output.md`, whose executor,
    attester and four loaders are its `scripts/`: the surface mass
    balance over the grounded domain less the discharge through a named
    flux gate set, formed node by node from a velocity and a thickness.
    What the concept stands for is the method and its refusals rather
    than a measurement: its record run refuses, so no real-data
    estimate by this method exists yet, and the skill says so plainly
    and says what would produce one.
  - `sweep`, `receipt-figures` and `methods` work over the receipts
    those two write, and compute nothing of their own: a table of one
    declared parameter's receipts that refuses any aggregate across
    them, the term series and the annual-lag differences of an attested
    receipt drawn as figures, and a methods paragraph with the
    concept's own reference list.

  Both computation concepts came in from the provider bundle on
  2026-09-20 with every reference run reproduced at the new paths, and
  both are `draft` until the maintainer re-signs them, because a
  signature covers the digests a concept names.

- **Knowledge** (`knowledge/`): this capability's own bundle, holding
  the two computation concepts and, under
  `references/retrieval/`, the two stamped data roots they read as
  data. `knowledge/index.md` lists them and says which facts stay in
  the provider bundle. Nothing under `knowledge/` is runnable.

- **Verification** (`verification/`): `ice_sheet_balance.py` and
  `ice_sheet_input_output.py`, the goldens that prove every script
  those concepts name, headless and offline (each script's selftest,
  the committed root against its manifest, each reference run attested
  and compared with what the concept records, and each refusal attested
  as a refusal rather than as a number), `receipt_skills.py` for the
  three receipt skills, and the committed expectations they read under
  `fixtures/`.

## The sea level equivalent is another capability's number

An ice sheet mass rate is not a sea level contribution, and nothing
here converts one into the other. The conversion, with the ocean area
constant it rests on and the uncertainty terms that travel with it, is
owned by the PO.DAAC bundle's recipe
`knowledge/podaac/recipes/grace-mass-to-sea-level.md`, and the
receipted budget that carries the ocean mass term is the attested
computation `knowledge/podaac/computations/sea-level-budget.md`,
run by the
[ocean-science](https://github.com/open-science-pillars/ocean-science)
capability's `sea-level-budget` skill. A reader who wants the sea level
equivalent of a rate reported here goes there. Two capabilities never
quote the same number.

## What this release does not do

It carries no connector and no agent, and it computes nothing outside
the two concepts above. An analysis that needs a fact about a product
the NSIDC bundle has not signed belongs in that bundle first, where the
fact can be reviewed and signed; a new method belongs in a concept
here, signed by this capability's maintainer, and reaches a reader only
once it is.

## Ownership

Owned by @open-science-pillars/cryosphere-maintainers (`CODEOWNERS`);
one person holds the team during the interim solo period, and
accepting a maintainer is a membership change, never a rearrangement.
Provider contacts who could confirm the facts this capability relies
on: NSIDC (ITS_LIVE, BedMachine, ICESat-2 land ice) and PO.DAAC (the
GRACE and GRACE-FO mascons). A confirmation is invited on every
concept the skills cite and required on none; the concepts live in the
provider bundle, and each carries its own confirm link.

## Contributing

Start with the marketplace repository's
[CONTRIBUTING.md](https://github.com/open-science-pillars/marketplace/blob/main/CONTRIBUTING.md)
and the guides under its `docs/` (contributing a skill, contributing
knowledge, testing, the package authoring guide). A change to what a
skill here reports is a change to the computation concept it runs,
reviewed here; a change to a fact about a product is a change in
nasa-daac-knowledge and is reviewed there.

## Place in the organization

What this repository is and how far along it is are declared once, in
`.osp/repository.yaml`; the organization profile, build-kit's
[sphere view](https://github.com/open-science-pillars/build-kit/blob/main/SPHERE-VIEW.md)
and the GitHub topics are rendered from that file, never the other way
round. The runtime manifests are rendered from `.osp/package.yaml` by
build-kit's `osp.py render` and are never edited by hand.

## License

Apache 2.0, the organization's license; see `LICENSE`.
