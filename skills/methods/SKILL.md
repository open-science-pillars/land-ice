---
name: methods
description: "Write the methods paragraph and the reference list of an attested ice sheet balance run from the receipt's bookkeeping block and the concept's own sources, and from nothing else: the attester runs first, every sentence is bound to a receipt field path, a missing bookkeeping statement is a refusal, and the reference list is the concept's source list copied verbatim. Keywords: methods section, methods paragraph, write up, references, citations, bibliography, how was this computed, provenance paragraph, GIA model, firn model version, ice density, manuscript."
---

# methods

This skill computes nothing. Every number, product name, model version,
mask rule and parameter in the paragraph it writes is a field of one
receipt that the provider bundle's attester passed, and every entry of
the reference list is an entry of the concept's own `sources`
frontmatter, copied verbatim. The computation that owns those facts is
`knowledge/nsidc/computations/ice-sheet-balance.md`, and the procedure
that produced the receipt is the `ice-mass-change` skill; read both
before writing anything up.

A methods section is where an unattested fact is least likely to be
caught. A reader checks the numbers and trusts the prose around them,
so a sentence that says "a firn densification model was applied" when
the receipt names GEMB 1.3.0, or "the standard GIA correction" when the
receipt names ICE-6G_D subtracted by the product before the CRI filter,
passes review and is wrong in the way that matters. The writer
therefore composes no prose about the science freehand: it assembles
the paragraph from a fixed table of statements, each bound to one
dotted path in the receipt, and refuses rather than writing around a
path the receipt does not carry.

This is the shape of the ocean-science `cite-ecco` skill, one step
further: there a tool emits a citation block byte for byte and the
skill's rule is never to compose citation text freehand; here the tool
emits a methods paragraph and its reference list the same way, and the
same rule holds for both.

## Where the concept and the attester are

The provider bundle arrives with the `nasa-daac-knowledge` dependency;
its root is the `installPath` of that entry in
`claude plugin list --json`, or a checkout named by
`NASA_DAAC_KNOWLEDGE`. The script resolves it that way, exactly as the
wrapping skill, the `sweep` script and the `receipt-figures` renderer
do, and copies nothing into this repository. `$NSIDC` below stands for
`<that root>/knowledge/nsidc`:

- concept: `$NSIDC/computations/ice-sheet-balance.md` (its `sources`
  block is the reference list, and the script reads it there rather
  than keeping a list of its own)
- executor: `$NSIDC/references/computations/ice_sheet_balance.py`
- attester: `$NSIDC/references/attesters/ice_sheet_balance_check.py`

## Behavior, in order

1. **Get the receipt from a run of the wrapping skill.** The paragraph
   describes one run: one ice sheet, one window, one altimetry product,
   one density, one input. The writer does not run the executor.
2. **The attester runs before a single field is read.** The script
   hashes the receipt's bytes before and after, so the paragraph is
   written from the file that attested. Pass `--data-root DIR` for a
   data-root receipt so the term file digests are verified against the
   tree rather than taken on the executor's word.
3. **Write it, from the plugin root:**

   ```bash
   uv run skills/methods/scripts/methods.py \
     --receipt /tmp/ice-mass-change-record.json \
     --data-root $NSIDC/references/retrieval/ice-sheet-balance-root \
     --out /tmp/methods.md
   ```

   The output is one markdown file with four sections: **Methods**, the
   paragraph; **References**, the concept's source list verbatim, keyed
   by the footnote ids the paragraph uses; **Field map**, every sentence
   beside the receipt field paths it was built from; and
   **Provenance**, the concept, the executor and its digest, the
   attester and its verdict line, the wrapping skill, the run
   identifier, the runtime and the receipt's own digest.
4. **Use the paragraph verbatim.** Append it to the manuscript, report
   or notebook under a Methods heading, and the reference list under
   References. Do not rewrite a sentence to read better: each one is a
   receipt field, and an edit that smooths it is an edit to a fact. If
   a sentence is unclear, the place to fix it is the stamped root's
   `RECORD.json` or the concept, where it becomes a receipt field the
   attester checks.
5. **Hand over the field map with the paragraph** when a reviewer asks
   where a statement came from, and say which run identifier the
   paragraph is of. A fixture paragraph proves the chain and not the
   ice sheet, and the receipt's own caveats, which the paragraph
   carries verbatim, say so.
6. **Say what the paragraph does not cover, in your own text beside
   it.** The comparison with the published assessment, the sea level
   equivalent, and anything about a second window or a second run are
   facts of other concepts and other receipts. Cite those concepts by
   bundle path in your own prose; never put them inside this paragraph.

## What the paragraph states, and where each statement comes from

Every one of these is required, and a receipt that carries none of them
is refused rather than written around:

- the concept, the executor and its digest, the runtime, and the input
  (the stamped root and its manifest digest, or the fixture seed and
  digest);
- the five declared parameters as bound, and whether the window crosses
  the gap between the gravimetry missions;
- the gravimetric term's domain, its epoch count in the window and the
  mascon selection rule; and its bookkeeping as the product applied it,
  the glacial isostatic adjustment model, the low degree replacements,
  the reference frame, the effective smoothing and the uncertainty
  basis, restated and never re-applied;
- the altimetric term's rule, domain, epoch count and firn domain; the
  volume term's reference, mask and uncertainty basis and the statement
  that it is not a mass; the firn model's version, forcing, reference
  and uncertainty basis; the floor rule and its per-domain values; and
  the ice density with the basis the receipt states for it;
- the product, DOI, granule and granule digest of each term whose stamp
  records one, with the time it was read;
- the rate method, each rate with its interval and which error the
  interval rests on, the residual rule and its common difference count,
  and the bar with its two parts named separately;
- the epoch handling rule and every mascon month missing from the
  window;
- the verdict rule and the verdict, attached to this window and these
  bindings;
- the receipt's own caveats, verbatim;
- the attester's verdict line, the run identifier and the receipt
  digest.

## Must NOT

- Never add a fact that is neither a receipt field nor an entry of the
  concept's sources: a published rate, a comparison with another study,
  a product name the stamp does not record, a model version the
  bookkeeping does not carry, a sentence about what the result means.
  The script refuses `--add` with that reason; do not do by hand what
  it refuses.
- Never write from a receipt the attester did not pass, and never write
  from a refusal receipt. A refusal is never a number and never a
  methods paragraph; report it in the executor's own words.
- Never edit, rewrite, shorten or "tidy" a sentence of the paragraph.
  Each is a receipt field, and an edit is an edit to a fact.
- Never compose, abbreviate or reconstruct a citation. The reference
  list is the concept's `sources` block copied verbatim; a source the
  concept does not list is not added here, and a DOI is never guessed.
- Never merge two runs' paragraphs, and never write one paragraph that
  covers two windows, two altimetry products or two densities. One
  receipt, one paragraph.
- Never present the paragraph as describing the ice sheet rather than
  the run: the verdict belongs to the window, and the paragraph says
  so.
- Never state a sea level equivalent or a comparison with the published
  assessment inside the paragraph; those belong to the concepts the
  `ice-mass-change` skill names, cited by bundle path in your own text.
- Never commit a receipt, an attestation or a generated methods file to
  this repository or to the provider bundle.
