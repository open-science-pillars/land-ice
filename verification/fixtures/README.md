# Fixtures

What the goldens at the top of `verification/` read. Everything here is
committed, offline and deterministic: a golden touches no live service,
needs no credential and carries no secret.

## `ice_sheet_balance.json`

The expected values of the attested ice sheet mass balance closure this
package runs, read by `ice_sheet_balance.py`.

**Provenance.** Every number in it is quoted from the Reference run and
Boundaries sections of `knowledge/computations/ice-sheet-balance.md` in
this package, and every one of them was reproduced at these paths on
2026-09-20, when the computation moved out of the provider bundle and
into the capability that runs it under ADR E. The `concept_status`
field carries the word the concept's frontmatter carries, and the
golden reads that frontmatter and fails when the two disagree, so the
field cannot go stale in silence. The two fixture runs are at seed 7,
which the executor regenerates deterministically from a hash-based
Gaussian stream with no numeric library in the path; the eight data
root runs read the stamped tree committed under
`knowledge/references/retrieval/ice-sheet-balance-root`. Neither drifts
with a release of anything.

**The executor's and the attester's digests.** The file records
`executor_sha256` and `attester_sha256`, and the golden asserts the
first against the receipt's own `code_sha256`. They are asserted for a
reason the numbers cannot cover: an edit that changes no number, a
comment or a rename, still moves a digest, and a golden that only
re-ran the chain and compared the numbers would never see it. The run
identifier is not what to assert for this, although it moves too: it
binds the runtime name, the package block and the package-relative data
root, so it differs between two runtimes and between two checkouts.

**The two refusals.** The file records a reason code rather than a value
for each: the fixture window outside the terms' overlap
(`window-outside-overlap`), and Antarctica on the committed root
(`firn-term-missing`), for want of a grounded firn air content term.
Both are what the concept records, the second a finding about the data
rather than an error, and the golden asserts each as a refusal attested
against the tree.

**What it is not.** It is not a receipt and not a generated fixture.
The executor's synthetic root is regenerated at run time and is never
committed anywhere.

**When it changes.** Only when the concept it quotes changes its
reference runs, and then the concept is the thing to read first. A value
edited here to make a golden pass is the golden lying.

## `ice_sheet_input_output.json`

The expected values of the attested input-output balance this package
runs, read by `ice_sheet_input_output.py`. The same rules hold, and the
provenance is the Reference run section of
`knowledge/computations/ice-sheet-input-output.md`, reproduced at these
paths on 2026-09-20.

**The record run is a refusal.** The committed root under
`knowledge/references/retrieval/ice-sheet-input-output-root` carries the
real ITS_LIVE gate velocities and no thickness term, so the record run
refuses with `term-not-in-root` and the file records that reason code
and no number. No real-data estimate by this method exists yet; the two
fixture runs are what prove the method.

## `receipt_skills.json`

The expectations of the three skills this capability carries over the
closure's receipts, read by `receipt_skills.py`: the `sweep` table, the
`receipt-figures` captions and the `methods` paragraph.

**Provenance.** Every cell under `sweeps` is a field of one receipt that
the attester passed, named in the `columns` block by its dotted path in
the receipt, and measured on 2026-09-20 from fixture runs of the closure
executor at seed 7 under the contract
`knowledge/computations/ice-sheet-balance.md`. The fixture is
regenerated deterministically at run time, so the values do not drift
with a release of anything, and the golden checks the recorded
`code_sha256` and the regenerated fixture's digest before it compares a
number. A row the executor refused carries its reason code and no
number, which is the measurement and not a gap: the `ice_sheet` sweep
records the Antarctic refusal `firn-term-missing`, the same refusal the
committed root gives.

The `code_sha256` here was re-measured on 2026-09-20 when the
computation moved into this package: the move changed the paths the
executor names and so its digest, and changed no number. Every cell was
compared against the new executor and every one of them was equal.

**Two precisions in one row, on purpose.** The rate columns are the
receipt's own headline fields, which the executor states rounded to
four decimals, and the interval columns are the same rates' intervals,
which the receipt carries at full precision. Both are recorded here as
the receipt states them. Reconciling them, by rounding the intervals or
by re-deriving a rate to unround it, would put a number in this file
that no receipt carries.

**The refusals.** The `refusals`, `figures` and `methods` blocks record
what each script must refuse and what each output must carry: the
aggregate across rows, the map mode, a fact from outside the receipt
and the concept's sources, and a receipt the attester did not pass.
They are reason codes and required substrings, not science values.

**What it is not.** It is not a receipt, not a figure and not a
generated table; none of those is ever committed here.

**When it changes.** Only when the executor moves, and then the
concept's reference run is the thing to read first. A value edited here
to make a golden pass is the golden lying.
