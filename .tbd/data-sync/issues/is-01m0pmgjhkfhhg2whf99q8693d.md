---
type: is
id: is-01m0pmgjhkfhhg2whf99q8693d
title: Depth-capped /api/tree no longer computes navigation tallies
kind: task
status: open
priority: 2
version: 1
labels: []
dependencies: []
parent_id: is-01m0ndp6h7a3hx27zbswtknk89
created_at: 2026-08-23T06:21:47.429Z
updated_at: 2026-08-23T06:21:47.429Z
---
Recorded from the side-by-side validation of #66 (mb-j7xx), as the one behaviour difference found between v0.6.0 and main. It is DELIBERATE and documented -- exp-007 states it in as many words -- and it is written down here because it is a change an API client can observe and the release notes do not mention it.

WHAT CHANGED. Navigation tallies -- `summary`, `extensions`, `canonical_extensions`, `file_type_registry`, `type_families`, `type_presets`, `recency_tallies` -- are no longer computed for a depth-capped `/api/tree` request. `depth=0` is now the channel that computes them; a `depth>=1` request serves them only when a fresh memo happens to exist, and returns null otherwise.

MEASURED, on a frozen corpus (601 files, git-tracked only, made read-only so nothing moved between runs):

    /api/tree?depth=0    0 differences between the two builds
    /api/tree?depth=2    13 differences, every one of them a tally field:
                         baseline populated, candidate null/empty

And on a live tree, polling ONLY depth=2 until the scan settles:

    baseline   7/7 tally fields populated
    candidate  0/7 -- then 7/7 after any single depth=0 request

NOT USER-VISIBLE. app.js fetches `/api/tree?depth=0` (app.js:1032), so the browser always uses the channel that computes them. The UI is identical, which is what the depth=0 result above says.

WHO WOULD SEE IT. Any client that requests only a depth-capped tree and never depth=0. That is a narrow case and it is a real one, and it is the reason this is filed rather than waved through: the change is invisible in the app and visible at the API.

WHY IT WAS DONE, from exp-007: "a row request serves tallies only from a fresh memo; depth=0 is the channel that computes them, fetched by the client after the render", worth `srv_scanning_ms` 311ms -> 2ms on a 246,282-file corpus.

WHAT TO DECIDE. Whether this belongs in the API documentation for `/api/tree`, and in the notes for whichever release ships #66. Nothing needs to change in the code; the argument for the trade is sound and measured. This is about a reader of the API being able to find out.

TWO NOTES FOR WHOEVER RUNS THIS COMPARISON NEXT, both of which cost time here:
- Do not use a working checkout as the corpus. Running the comparison writes `__pycache__`, so the tree changes between the two builds' runs and the diff fills with .pyc counts that have nothing to do with either build. Freeze a copy.
- Settle the poll on the same endpoint the claim is about, and be explicit about which. Polling depth=2 while the app uses depth=0 compares a computed answer against an uncomputed one, which reads as a regression and is not one.
