# Fixtures

What the goldens at the top of `verification/` read. Everything here is
committed, offline and deterministic: a golden touches no live service,
needs no credential and carries no secret.

## `wrapped_computations.json`

The expected values of this capability's two wrapping chains, read by
`wrapped_computations.py`.

**Provenance.** Every number in it is quoted from the Reference run
section of the concept it names, in the nasa-daac-knowledge `nsidc`
bundle: `knowledge/nsidc/computations/ice-sheet-balance.md` (signed
stable, verified 2026-09-16) and
`knowledge/nsidc/computations/ice-sheet-input-output.md` (signed
stable, verified 2026-09-19). The `concept_status` field in each chain
carries that word, and the golden reads the concept's own frontmatter
and fails when the two disagree, so the field cannot go stale in
silence. Both are fixture runs at seed 7, which the executors
regenerate deterministically from a hash-based Gaussian stream with no
numeric library in the path, so the values do not drift with a release
of anything. Recorded 2026-09-19.

**The executor's digest.** Each chain also records `executor_sha256`,
the digest of the provider executor the chain runs, which the receipt
carries as `code_sha256`. It is asserted for a reason the numbers
cannot cover: an edit to a provider executor that changes no number, a
comment or a rename, still moves the digest, and a golden that only
re-ran the chain and compared the numbers would never see it. The run
identifier is not what to assert for this, although it moves too: it
takes the capability root's path, so it differs between a checkout and
a runner.

**The two record runs.** Each chain also names a run on a data root
the provider bundle commits, and both of those runs refuse, so the
file records a reason code rather than a value for each: the closure
refuses Antarctica with `firn-term-missing`, for want of a grounded
firn air content term, and the input-output computation refuses its
own record window with `term-not-in-root`, because the thickness term
is not in its root. Both refusals are what the concepts record, and
the golden asserts them as refusals attested against the tree.

**What it is not.** It is not a copy of a provider fixture and not a
receipt. The provider's fixtures are generated at run time and are
never committed anywhere; the executors, the attesters and the
committed data roots stay in the provider bundle and arrive with the
dependency. This capability owns none of these numbers, and the file
exists so that a chain which stops reproducing its concept fails the
gate.

**When it changes.** Only when the concept it quotes changes its
reference run, and then the concept is the thing to read first. A
value edited here to make a golden pass is the golden lying.

## `receipt_skills.json`

The expectations of this capability's three receipt skills, read by
`receipt_skills.py`: the `sweep` table, the `receipt-figures` captions
and the `methods` paragraph.

**Provenance.** Every cell under `sweeps` is a field of one receipt
that the bundle's attester passed, named in the `columns` block by its
dotted path in the receipt, and measured on 2026-09-20 from fixture
runs of the closure executor at seed 7 under the contract
`knowledge/nsidc/computations/ice-sheet-balance.md`. The fixture is
regenerated deterministically at run time, so the values do not drift
with a release of anything, and the golden checks the recorded
`code_sha256` and the regenerated fixture's digest before it compares a
number. A row the executor refused carries its reason code and no
number, which is the measurement and not a gap: the `ice_sheet` sweep
records the Antarctic refusal `firn-term-missing`, the same refusal the
committed root gives.

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
generated table; none of those is ever committed here. The executors,
the attesters and the committed data roots stay in the provider bundle
and arrive with the dependency.

**When it changes.** Only when the provider executor moves, and then
the concept's reference run is the thing to read first. A value edited
here to make a golden pass is the golden lying.
