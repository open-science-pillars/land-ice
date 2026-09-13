# Land Ice

> **Planned. This repository holds no capability yet; it exists so the
> organization's target shape is visible. Nothing here is installable.**

A domain capability: discipline Land Ice inside the Cryosphere sphere. Pillar means sphere: one of the five Earth science spheres; a capability is skills, knowledge signed by its stewards and deterministic checks, delivered as one plugin.

## Use something today

Nothing in this repository installs. The capabilities that do are in the
marketplace, and each brings the foundation and the provider knowledge
with it:

```bash
claude plugin marketplace add open-science-pillars/marketplace
claude plugin install ocean-science@open-science-pillars   # or hydrology, or core
```

On Claude Cowork, add the same marketplace from Customize > Plugins and
install from it. The [tutorials](https://github.com/open-science-pillars/tutorials)
take ten to thirty minutes; the [glossary](https://github.com/open-science-pillars/marketplace/blob/main/GLOSSARY.md) says what a sphere,
a capability and a knowledge bundle are.

## Intended scope

Ice sheets and glaciers: elevation change, mass balance, velocity and
discharge, and the sea level contribution they imply.

## Ownership

Owned by @open-science-pillars/cryosphere-maintainers (`CODEOWNERS`); one person
holds the team during the interim solo period, and accepting a
maintainer is a membership change, never a rearrangement.

Provider contacts who could confirm the facts a capability
here relies on: NSIDC DAAC (ICESat-2 elevation, MEaSUREs ice velocity) and PO.DAAC (GRACE-FO mass change). None engaged yet.

## What to do here

- **A scientist**: use core, ocean-science or hydrology now; watch this
  repository for its first release; describe the analyses you would want
  from this discipline in the marketplace
  [Discussions](https://github.com/open-science-pillars/marketplace/discussions).
- **A person at one of the data centers named above**: start by
  confirming or correcting a single concept from the organization's
  [confirm-a-concept issue](https://github.com/open-science-pillars/.github/issues/new?template=confirm_concept.yml),
  no tooling needed; the new domain capability issue in the same
  [.github](https://github.com/open-science-pillars/.github) repository
  is there when you want more. A capability here starts with the people
  who know the data; their confirmation is invited at every step and
  required at none.
- **A maintainer**: promotion out of planned is governed, cross-cutting
  work, never a quiet commit: a dated entry in the
  [pre-registered plan](https://github.com/open-science-pillars/marketplace/blob/main/docs/phase2-preregistration.md),
  a named provider contact who has been invited, a knowledge bundle that conforms to the knowledge
  format and is validated in evals, and only then the package, surfaces
  and runtime metadata that the planned status forbids. The proposal is
  decided under the roadmap proposal labels.

## What stays out while planned

No `SKILL.md`, no `.osp/package.yaml` or `.osp/surfaces.yaml`, no
runtime manifest (`.claude-plugin`, `plugin.json`, `mcp.json`), no
marketplace catalog entry, no release, no `CITATION.cff`. The gate
runs build-kit's `osp.py validate`, which refuses each of them for a
repository whose status is planned, so the honest banner above cannot
drift from what the tree contains.

## Place in the organization

What this repository is and how far along it is are declared once, in
`.osp/repository.yaml`; the organization profile, build-kit's
[sphere view](https://github.com/open-science-pillars/build-kit/blob/main/SPHERE-VIEW.md) and the
GitHub topics are rendered from that file, never the other way round.
The decision record is ADR A in [marketplace/docs/decisions](https://github.com/open-science-pillars/marketplace/tree/main/docs/decisions).

## License

Apache 2.0, the organization's license; see `LICENSE`.
