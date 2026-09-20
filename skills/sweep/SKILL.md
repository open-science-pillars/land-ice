---
name: sweep
description: "Sweep one parameter an attested nsidc computation declares and table the receipts: the sanctioned executor once per value, the attester on every receipt before any field is read, and a CSV, a markdown table and a JSON manifest of the executor's own headline fields, with a refused run as a row carrying its refusal code. Keywords: parameter sweep, window dependence, sensitivity, every window, table of runs, ice sheet mass balance over many windows, altimetry product, ITS_LIVE against ATL15, ice density, gate set, closure verdict."
---

# sweep

This skill computes nothing. Every number it puts in a table is a field
of one receipt that the provider bundle's attester passed, copied by
the receipt field path the script records beside each column, and the
computation that owns those numbers is the concept the sweep names
(`knowledge/nsidc/computations/ice-sheet-balance.md` for the closure,
`knowledge/nsidc/computations/ice-sheet-input-output.md` for the
input-output balance). The script fits nothing, averages nothing and
carries no expected value of its own. What the sweep adds is
arrangement: a concept states its boundaries in prose from a handful of
runs someone made by hand, and a sweep turns that sentence into a
measured table by running the sanctioned executor once per value of one
parameter the concept declares.

The closure concept's boundaries section is the case this skill exists
for. It quotes seven windows run by hand on the committed root, reports
that some close and some do not, names the altimetry term as the
suspect, and concludes that the closure verdict is window dependent.
That is a claim about a family of runs, and a sweep measures it: run
the executor over the windows, table what each receipt says, and let a
reader see the dependence instead of taking it on the prose.

Use it when the question is how an answer moves with a parameter the
concept declares: every window of a stated length stepping through the
record, the same window on each of the two altimetry records the root
now carries, the same window at two ice densities, the same window
through two gate sets. Use the wrapping skill (`ice-mass-change` for
the closure, `ice-sheet-input-output` for the input-output balance)
when the question is about one run, which is also the only thing a
reader may quote as a number.

The runs it drives are the wrapping skills' runs, so read the wrapping
skill first: it states the parameters, the refusal codes, the receipt
fields and the caveats that travel with every number. The sweep changes
none of that. It runs the same executor with the same flags, one value
at a time.

This is the ocean-science `sweep` skill's command line and output shape
over the nsidc computations. A reader who knows one knows both: the
same flags, the same three files, the same five refusals with the same
reason codes and the same exit codes.

## Where the executor, the attester and the concept are

The provider bundle is installed with the nasa-daac-knowledge
dependency; its root is the `installPath` of that entry in
`claude plugin list --json`, or a checkout named by
`NASA_DAAC_KNOWLEDGE`. The script resolves it that way, exactly as the
wrapping skills do, and copies nothing into this repository. `$NSIDC`
below stands for `<that root>/knowledge/nsidc`:

- the closure: concept `$NSIDC/computations/ice-sheet-balance.md`,
  executor `$NSIDC/references/computations/ice_sheet_balance.py`,
  attester `$NSIDC/references/attesters/ice_sheet_balance_check.py`,
  committed root `$NSIDC/references/retrieval/ice-sheet-balance-root`
- the input-output balance: concept
  `$NSIDC/computations/ice-sheet-input-output.md`, executor
  `$NSIDC/references/computations/ice_sheet_input_output.py`, attester
  `$NSIDC/references/attesters/ice_sheet_input_output_check.py`,
  committed root `$NSIDC/references/retrieval/ice-sheet-input-output-root`

The script reads the declared parameter set from the concept's
frontmatter rather than from a list of its own, so a parameter the
concept gains is sweepable without editing this skill and a knob nobody
declared is refused.

## The command line

Every run states the parameter swept, its values, and the fixed value
of every other parameter the concept declares. A declared parameter
that is neither swept nor fixed is a refusal, so the table always says
what every run was bound to.

```bash
uv run skills/sweep/scripts/sweep.py \
  --computation ice-sheet-balance --parameter window \
  --windows 84:12 --span 2003-01:2016-12 \
  --fixed ice_sheet=greenland --fixed altimetry=itslive \
  --fixed ice_density=917 --fixed bridge=unbound \
  --input data-root --data-root $NSIDC/references/retrieval/ice-sheet-balance-root \
  --runtime claude-code --capability-root . \
  --out-dir /tmp/sweep-ice-sheet-balance
```

- `--computation NAME` is `ice-sheet-balance` or
  `ice-sheet-input-output`.
- `--parameter NAME` is swept, named as the concept declares it
  (`ice_sheet`, `window`, `altimetry`, `ice_density`, `bridge` for the
  closure; `ice_sheet`, `window`, `gates`, `velocity_epoch`,
  `ice_density` for the input-output balance). `--values A,B,C` states
  the values one by one, or `--windows LENGTH:STEP --span FIRST:LAST`
  states a window rule in months that expands to explicit values, which
  the manifest and every row then carry.
- `--fixed NAME=VALUE` states another declared parameter;
  `--fixed bridge=unbound` says in the table that no bridge citation
  was bound on any run, which is why a window whose mass months straddle
  the gap between the gravimetry missions refuses.
- `--input fixture [--seed N]` rehearses on the executor's synthetic
  record; `--input data-root --data-root DIR` is a real run on a stamped
  tree, and every receipt is then attested against that tree. One input
  for the whole sweep: a table is one method on one root.
- `--runtime NAME` is passed to every run (from Claude Code, pass
  `--runtime claude-code`), and `--capability-root DIR` names the
  package the runs are evidence for.
- `--out-dir DIR` receives `sweep.csv` (every column as the receipt
  states it), `sweep.md` (the same columns, floats shown to four
  decimals, with the provenance line above the table), `sweep.json`
  (the manifest: the command, the one executor digest, the one input
  identity, the column-to-receipt-field map, and every row with its
  receipt path, run id and the attester's own verdict line) and
  `receipts/` (every receipt and its attestation).
- `--selftest` runs the whole discipline on both executors' synthetic
  fixtures and exercises every refusal below.

## Behavior, in order

1. **Name the concept first, then show the sweep back.** State the
   concept by bundle path (`knowledge/nsidc/computations/ice-sheet-balance.md`
   for the closure), the parameter to be swept as that concept declares
   it, the values, the fixed value of every other declared parameter,
   and the input (the fixture as a rehearsal, or the stamped data root
   for a real run). Consult the wrapping skill and the concepts and
   gotchas it names before running.
2. **Run the sweep.** One executor run per value, each writing its own
   receipt. A run the executor refuses (exit 3) is a row carrying its
   reason code, never a skipped row and never retried with a different
   binding to get a number out of it: the refusal is part of what the
   sweep measures. Antarctica refuses on the closure's committed root
   with `firn-term-missing`, a window outside the terms' overlap
   refuses with `window-outside-overlap`, a window whose mass months
   straddle the inter-mission gap refuses with `gap-without-bridge`
   unless a bridge citation the user supplies is fixed on the sweep,
   and every record run of the input-output balance refuses with
   `term-not-in-root`, because its thickness term is not in the root.
   A sweep of the input-output balance on that root is therefore a
   table of refusals, and that is the finding, not a failure.
3. **The attester runs on every receipt before any field is read.**
   The script attests each receipt and only then copies fields out of
   it; a data-root sweep passes `--data-root` to the attester so the
   term file digests are verified against the tree rather than taken on
   the executor's word. A receipt that does not pass is a failed row
   carrying the attester's own line and no number, and the script exits
   nonzero so the failure cannot pass for a table. Do not work around
   it; report it.
4. **Read the table.** The columns are the receipt fields the concept's
   reference run names: the bound parameters, the epochs each term
   carried and the differences common to both, each term's rate with
   its interval, the residual or the mass rate with its interval, the
   two parts of the bar, and the verdict. The manifest maps every
   column to its receipt field path and every row to its receipt and
   run id.
5. **Report the table with its provenance and the concept's caveats.**
   Hand over the markdown table together with the provenance line the
   script writes above it (the executor digest, the attester, the
   concept, the input identity, the runtime), the run identifiers of
   the rows discussed, and the caveats the concept states, beside the
   numbers and not after them. Say how many rows the executor refused
   and why. A fixture sweep proves the chain, not the ice sheet, and
   says so.
6. **Answer the aggregate question with a row.** A reader who sees a
   table of windows asks for one number across it, and for this
   computation that number has a name: the Greenland mass balance in
   gigatonnes per year. Give the row that answers the question as asked
   (the window the question names, or the longest window that does not
   cross the inter-mission gap), quote it with its interval, its bar,
   its verdict and its run id, and say that the verdict belongs to that
   window and that the spread across the rows is what the table shows
   and not a quantity any receipt carries. The script refuses
   `--aggregate` with that reason, and the reason is the answer to
   give.

## Reading a sweep of the closure

- **The verdict belongs to the window.** The concept's boundaries
  section records windows on the committed root that close and windows
  on the same root that do not, including halves of the anchor window
  with residuals of opposite sign. A sweep measures that dependence; it
  does not resolve it into a state of the ice sheet, and neither does a
  report of one.
- **Compare a row against its own bar, never against another row's.**
  The bar is the residual's own half width plus the mascon selection
  systematic, so it grows with the disagreement it measures. A short
  window is not a small version of a long one: the interval widens, the
  months dropped at the gravimetry gap grow as a share of the window,
  and the bar moves with them. The table carries both parts of the bar
  for that reason.
- **A refused row and a row that fails to close are different
  findings.** The first says the run was not licensed. The second is a
  correction-consistency finding before a missing-physics one: the firn
  model and its forcing, the density, the mascon selection and the
  altimetry record's mission transitions are what a reader audits
  first, in the receipt's bookkeeping block and the concept's
  boundaries.
- **A sweep over `altimetry` is a sweep over two different records.**
  The concept reports that the two altimetric rates over the window
  they share differ by 80 gigatonnes per year and that the verdict
  flips between them while their intervals still overlap. Report both
  rows and the concept's reading of them; the table does not decide
  which record is right.
- **The rate columns and the interval columns carry different
  precisions.** The receipt states each term's headline rate rounded to
  four decimals and the interval on that same rate at full precision,
  and the sweep copies both as the receipt states them. Neither is
  rounded nor unrounded here; a cell that reconciled them would be a
  number no receipt carries.

## Reading a sweep of the input-output balance

- **The record run refuses, and a sweep of the committed root is a
  table of refusals.** The thickness term is absent for an access
  reason and the grounded surface mass balance term for a distribution
  reason, both of which the concept states. Report the refusal codes
  and the concept's two reasons; never fill a cell with an estimate,
  and never present the absence as a small number.
- **The fixture sweep proves the method and nothing about Greenland.**
  Say so with every fixture table.

## Must NOT

- Never state the headline number a reader will ask for first: the
  Greenland or Antarctic mass balance in gigatonnes per year read off
  the rows, the mean residual over the windows, the average closure
  gap, or the fraction of windows that closed read as a rate. No
  receipt carries any of them and no concept owns them; a capability
  that computes one is computing a number of its own, which is domain
  expansion under ADR D of the marketplace decisions and waits on the
  ablation. The `ice-mass-change` skill forbids the headline mass rate
  for the same reason. The script refuses them; do not do by hand what
  it refuses.
- Never present one window's closed verdict as the ice sheet's state,
  and never average two windows' rates or verdicts into one.
- Never compare or table rows whose receipts carry different executor
  digests or different input identities. The script refuses that too:
  a table is one method on one root.
- Never quote a number from a receipt the attester did not pass, and
  never drop a failed row to make the table look complete.
- Never drop a refused row, and never rerun it with an invented
  binding (a bridge phrase nobody supplied, a widened window) to fill
  the cell.
- Never sweep something the concept does not declare (a seed, an output
  path, a knob invented for the occasion); the script reads the
  declared set from the concept and refuses the rest.
- Never convert any row's mass rate into a sea level equivalent; that
  conversion belongs to the podaac recipe and the ocean-science skill
  the `ice-mass-change` skill names.
- Never present a table without the run identifiers, the executor
  digest and the concept's caveats, and never commit a receipt, an
  attestation or a generated table to this repository or to the
  provider bundle.
