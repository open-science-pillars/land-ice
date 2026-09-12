# Land Ice

> **Planned. This repository holds no capability yet; it exists so the
> organization's target shape is visible. Nothing here is installable.**

A domain capability: discipline Land Ice inside the Cryosphere sphere.

## Intended scope

Ice sheets and glaciers: elevation change, mass balance, velocity and
discharge, and the sea level contribution they imply.

## Ownership

Owned by @open-science-pillars/cryosphere-maintainers (`CODEOWNERS`); one person
holds the team during the interim solo period, and accepting a
maintainer is a membership change, never a rearrangement.

Candidate provider stewards, who would sign the facts a capability
here relies on: NSIDC DAAC (ICESat-2 elevation, MEaSUREs ice velocity) and PO.DAAC (GRACE-FO mass change). None engaged yet.

## What promotion takes

Promotion out of planned is governed, cross-cutting work, never a
quiet commit: a dated entry in the Phase-2 pre-registration
([marketplace/docs/phase2-preregistration.md](https://github.com/open-science-pillars/marketplace/blob/main/docs/phase2-preregistration.md)),
a steward who signs, a knowledge bundle that conforms to the knowledge
format and is validated in evals, and only then the package, surfaces
and runtime metadata that the planned status forbids. A proposal starts
with the new domain plugin issue template in the organization's [.github](https://github.com/open-science-pillars/.github)
repository and is decided under the roadmap proposal labels.

## What stays out while planned

No `SKILL.md`, no `.osp/package.yaml` or `.osp/surfaces.yaml`, no
runtime manifest (`.claude-plugin`, `plugin.json`, `mcp.json`), no
marketplace catalog entry, no release, no `CITATION.cff`. The gate
runs build-kit's `osp.py validate`, which refuses each of them for a
repository whose status is planned, so the honest banner above cannot
drift from what the tree contains.

## Place in the organization

Pillar means sphere: one of the five Earth science spheres. What this
repository is and how far along it is are declared once, in
`.osp/repository.yaml`; the organization profile, build-kit's
[sphere view](https://github.com/open-science-pillars/build-kit/blob/main/SPHERE-VIEW.md) and the
GitHub topics are rendered from that file, never the other way round.
The decision record is ADR A in [marketplace/docs/decisions](https://github.com/open-science-pillars/marketplace/tree/main/docs/decisions);
the roadmap deliverable is in build-kit's [ROADMAP.md](https://github.com/open-science-pillars/build-kit/blob/main/ROADMAP.md).

## License

Apache 2.0, the organization's license; see `LICENSE`.
