---
name: receipt-figures
description: "Draw the term series or the annual-lag differences of an attested ice sheet balance receipt, and from nothing else: the renderer runs the bundle's attester, verifies every array it draws against what the receipt records, and writes the run identifier, the code digest and the verdict into the caption. Keywords: plot, figure, chart, time series, mass anomaly series, volume anomaly, firn air content, annual-lag differences, residual series, 2010 spike, 2013 spike, closure figure, show me the series."
---

# receipt-figures

This skill computes nothing. Every value in every figure it draws is a
number the receipt already carries: a point of one of the series the
ice sheet balance receipt records, or a rate, an interval or a bar the
receipt states, quoted in a legend or a caption. Nothing is fitted,
smoothed, resampled, averaged or converted, and no two receipts are
ever drawn on one pair of axes. The computation that owns those numbers
is the concept `knowledge/computations/ice-sheet-balance.md`, and
the procedure that runs it is the `ice-mass-change` skill; read both
before drawing.

The attested closure answers how much and how well with scalars in a
receipt, and a reader who has those scalars still asks to see the
series. That question is the easiest place for an unattested number to
slip in, because a picture invites a smoothing, an extrapolation or a
second record drawn beside the first. This renderer draws only from a
receipt that attests, only the arrays the receipt records, and stamps
every figure with what it was drawn from.

The concept's own reading of the anchor run is a reading of these two
figures. It reports that the two rates agree in the mean to 2
gigatonnes per year while the residual series scatters by hundreds from
month to month, and it names the carrier of two spikes: at 2010-01 the
altimetric loss reads far below the mascons' because the ITS_LIVE
record rests on Envisat alone between the end of ICESat and the start
of CryoSat-2, so the spike belongs to the volume term; at 2013-01 the
firn correction cancels most of the surface lowering that followed the
July 2012 melt, so that spike belongs to the firn term. That is prose
about a picture. The `differences` mode is the picture, and the `terms`
mode is the volume and the firn air series the reading rests on.

The renderer ships beside this skill (`scripts/receipt_figure.py`, PEP
723, matplotlib). It finds the attester in the scripts of the
`ice-mass-change` skill under this package's root, which it resolves
the way the runtime does, `${CLAUDE_PLUGIN_ROOT}` where the runtime sets it and the
package tree the script sits in otherwise, exactly as the
`ice-mass-change` skill and the `sweep` script do, and reaches nothing
in another repository.

## Behavior, in order

1. **Get the receipt from a run of the wrapping skill.** A figure is
   drawn from a receipt the `ice-mass-change` skill produced, on the
   fixture as a rehearsal or on the committed data root. The
   renderer does not run the executor; it draws what a run already
   wrote.
2. **The attester runs first, and the renderer stops on anything but
   PASS.** It hashes the receipt's bytes before the attester reads them
   and again after, so the arrays drawn are the arrays that attested.
   Pass `--data-root DIR` for a data-root receipt so the term file
   digests are verified against the tree rather than taken on the
   executor's word. Do not draw around a FAIL; report the attester's
   own lines.
3. **Draw, from the plugin root:**

   ```bash
   uv run skills/receipt-figures/scripts/receipt_figure.py terms RECEIPT.json \
     --attester ice_sheet_balance_check \
     --data-root ${CLAUDE_PLUGIN_ROOT}/knowledge/references/retrieval/ice-sheet-balance-root \
     --out /tmp/terms.png

   uv run skills/receipt-figures/scripts/receipt_figure.py differences RECEIPT.json \
     --attester ice_sheet_balance_check \
     --data-root ${CLAUDE_PLUGIN_ROOT}/knowledge/references/retrieval/ice-sheet-balance-root \
     --out /tmp/differences.png
   ```

   - `terms` draws the two mass anomaly series (gravimetry and
     altimetry) on an upper panel and, on a lower panel with its own
     axis, the volume anomaly and the firn air volume anomaly that the
     stated density turns into the second of them. Each legend entry
     carries that term's rate, its interval and which error the
     interval rests on, quoted from the receipt's rate block.
   - `differences` draws the annual-lag differences the rate method is
     the mean of (altimetry and gravimetry, on the epochs both terms
     carry) on an upper panel, and the residual between them on a lower
     panel against the bar the receipt forms, with the residual's rate
     and interval as a line.
   - `map` is always refused. These receipts carry no per-cell fields.
4. **Hand over the figure WITH its caption line** (the renderer prints
   it): the receipt's run identifier, the code digest, the receipt's
   own digest, the input identity (the stamped record and its manifest
   digest, or the fixture seed and digest), the verdict
   `closed_within_uncertainty` as the receipt states it, the attester's
   verdict, and a short digest of every array drawn so a reader can
   recompute it from the receipt. Never crop the caption.
5. **Report the concept's caveats beside the figure, not after it.**
   The verdict belongs to the window the receipt names; the bar is the
   residual's own half width plus the mascon selection systematic, so
   it grows with the disagreement it measures; the altimetric series is
   a mass series only through the firn term and the stated density; the
   two domains are not the same ice. A fixture figure proves the chain,
   not the ice sheet, and says so.

## What verifying an array against the receipt means here

The PO.DAAC fields receipts the ocean-science `receipt-figures` skill
draws carry a `fields` block with a sha256 per array and a `.npz`
beside the receipt, and its renderer hashes each array against that
block. An ice sheet balance receipt carries no such block, because it
carries its series inline at full precision instead: the hashes it
records are the executor's digest, the fixture digest or the stamped
root's manifest and per-term-file digests, and nothing per array.

So this renderer binds every array it draws to the receipt three ways,
and refuses on any of them:

1. the receipt's bytes are hashed before the attester runs and again
   after, and must be identical;
2. the receipt must record the input digests its series were built
   from, and a receipt missing them is refused;
3. every array drawn must be one of the receipt's own named series,
   must match the count the receipt states for it, and must satisfy the
   derivation rule the receipt states for it: the altimetric mass is
   the bound ice density times the volume anomaly less the firn air
   anomaly at every epoch, the residual is the altimetry difference
   less the gravimetry difference at every common epoch, and each
   annual-lag difference is the term series at an epoch less its value
   twelve months earlier.

The renderer prints a sha256 of each array as it drew it, so a reader
can recompute the same digest from the receipt with no library. Say
this plainly when handing a figure over: the arrays are verified
against the receipt, and the receipt's series are verified against the
regenerated fixture or the stamped tree by the attester, which is the
step that binds them to the data.

## Reading the figures

- **The two mass series, not one.** The upper panel of `terms` is two
  independent observing systems, not a measurement and its error bars.
  Where they part, the concept's boundaries name the altimetry term as
  the suspect on the committed root; say so rather than letting the
  picture imply a mean.
- **The lower panel is where a height change becomes a mass change.**
  The volume anomaly is metres of surface height summed to cubic
  kilometres; the firn air anomaly is what must come off it before a
  density may be applied. The two bundle gotchas the wrapping skill
  cites are what that panel is a picture of.
- **A spike in the residual belongs to a term, and the upper panel of
  `differences` says which.** Read the two curves at the spike, not the
  residual alone. The concept reads 2010 and 2013 that way on the
  committed root and names the volume term and the firn term
  respectively; quote its reading by bundle path rather than inventing
  a third.
- **The shaded band is the bar, and it is not an error bar on each
  point.** It is the residual's own half width plus the mascon
  selection systematic, the quantity the verdict compares the residual
  rate against. Individual differences lying outside it are the
  scatter the concept describes, not failures.
- **A quarterly record and a monthly one do not look alike.** An ATL15
  receipt carries about a fifth of the epochs an ITS_LIVE receipt does
  over the same window. Say which altimetry product the receipt bound
  before comparing any two figures, and never draw one figure from two
  receipts.

## Must NOT

- Never draw from a receipt the attester did not pass, and never draw
  an array the receipt does not carry or that fails the receipt's own
  stated derivation. The renderer refuses both; do not work around it
  with a hand-loaded file or a series copied out into a spreadsheet.
- Never draw a map, a per-basin panel or a per-cell field from these
  receipts. The closure sums each term to one value per epoch and the
  executor writes no fields file, so there is no per-cell array and no
  hash to check one against; the renderer refuses the mode and the
  refusal is the answer.
- Never draw two receipts on one pair of axes, never put a difference
  between two receipts on a figure, and never add a fitted line, a
  smoothed curve, a rolling mean or an extrapolation. Every one of them
  is a number no receipt carries.
- Never crop or drop the caption line, and never put a number in a
  title or a legend that the receipt does not carry.
- Never present a fixture figure as a picture of an ice sheet, and
  never present one window's figure as the ice sheet's state.
- Never draw a refusal receipt. A refusal is never a number and never a
  figure; report it in the executor's own words.
- Never commit a receipt, an attestation or a generated figure to this
  repository or to the provider bundle.
