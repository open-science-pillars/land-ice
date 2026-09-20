# Bundle change log

Newest first. One line per change: date, concept path, what changed, who.

- 2026-09-20 · STEWARD RE-SIGNING of
  knowledge/computations/ice-sheet-balance.md,
  knowledge/computations/ice-sheet-input-output.md: Re-signed after the
  computation moved into the capability that runs it. The coordinator
  compared every number in each concept against the bundle's copy and
  found them identical, 270 and 123 numbers with none added and none
  removed, and osp.py validate reports no warning. The new verified
  event is appended on the steward's word, the earlier events kept as
  history. (steward)

- 2026-09-20 · knowledge/computations/ice-sheet-balance.md, knowledge/computations/ice-sheet-input-output.md, knowledge/references/retrieval/ice-sheet-balance-root, knowledge/references/retrieval/ice-sheet-input-output-root · the two attested ice sheet mass balance computations came in from the nsidc bundle of nasa-daac-knowledge under ADR E, from the bundle paths knowledge/nsidc/computations/ and knowledge/nsidc/references/{computations,attesters,loaders,retrieval}: each concept's computation, executor.resource and attester.resource now name the scripts of the skill that runs it, the retired executor.skill key is gone, provider concepts are cited by bundle path, the two stamped roots are committed here as data, and the check chains and named reference runs are the goldens verification/ice_sheet_balance.py and verification/ice_sheet_input_output.py. Every reference run reproduced at the new paths to the digit and no number changed; only the run identifiers moved, because they bind the package block and the package-relative data root. Both concepts are left draft and owe a re-sign: ice-sheet-balance.md sha256:f8e234efb3e16f2d31aad3d09432655bdbe72f321eb8523638ec0293805ee49b in the bundle, sha256:209f22eea9582db7ef3a3ba02616236ac83fa1dca85f7623ad4f0fb56d4647c8 here; ice-sheet-input-output.md sha256:33728777880d3b183fc2ab68cc8f434eed79c734ba7cc4afb5306236d8a753ac in the bundle, sha256:8211355392889cbbe4885f9ab273ae427bf5565141f9a8c0471a0d98038e6d3b here · claude
- 2026-09-20 · skills/sweep, skills/receipt-figures, skills/methods · three receipt skills added over the two nsidc closures, each computing nothing of its own: a sweep that tables one declared parameter's receipts and refuses any aggregate across them, a renderer that draws the term series and the annual-lag differences of an attested closure receipt, and a writer that states the methods paragraph and the reference list from a receipt's bookkeeping block and the concept's sources; the golden verification/receipt_skills.py runs all three offline · claude
- 2026-09-19 · knowledge/index.md · bundle opened with the capability's first release; it holds no concepts, because the release wraps computations signed in the nsidc provider bundle and owns no claim of its own · claude
