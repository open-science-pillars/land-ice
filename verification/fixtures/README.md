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

**The run identifier.** Each chain also records `goldens_run_id`, the
identifier the executor stamps on a run under the runtime name
`goldens`, which the golden always passes, so the value is fixed. It
is asserted for a reason the numbers cannot cover: an edit to a
provider executor that changes no number, a comment or a rename, still
moves the identifier, and a golden that only re-ran the chain and
compared the numbers would never see it. It is not a claim about any
other runtime's identifier, which differs by construction.

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
