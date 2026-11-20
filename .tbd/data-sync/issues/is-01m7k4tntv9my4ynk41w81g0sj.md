---
type: is
id: is-01m7k4tntv9my4ynk41w81g0sj
title: The Files nav panel's '+ N ignored' summary line is laid out from first paint, holding the pending placeholder while its count fills in, so nothing below it moves
kind: bug
status: closed
priority: 1
version: 24
refs:
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/490
    at: 2026-11-20T17:01:46.000Z
delegate: claude-code@spud10.local
labels:
  - linear
dependencies: []
parent_id: is-01m7dm3az28qmj39y5hmdq2k0v
child_order_hints:
  - is-01m7k6w6hj2p10bfr9zkd20c4x
  - is-01m7k7yw4522qy8mgb8h6c9y0y
  - is-01m7kdd7txfkyanyw0rnwjv6pw
  - is-01m7kdd8fqzc6mvh76g6xh5m9p
  - is-01m7kdd8zffjrm5pby3n8q3zcy
  - is-01m7kdd9j4nfd2pfwhm2c563mb
  - is-01m7kdda1kyysv08g87fedzpz5
  - is-01m7kddahbg6j2tm8yd4rkqpfp
  - is-01m7kddb49j3hpvswjfzkzm6w1
  - is-01m7kddbqzemff49eq4xj27xf4
  - is-01m7kgg2g37gev8jgq5rsf7kk2
  - is-01m7kgg36dvwj9r6tnbcx0t4mp
  - is-01m7kgg3sjf9caypx07ep5y6qs
  - is-01m7ks84dwc8ag94n6v3rs34tv
hold: null
hold_until: null
created_at: 2026-11-16T21:39:50.746Z
updated_at: 2026-11-20T17:01:46.013Z
started_at: 2026-11-16T21:40:37.650Z
closed_at: 2026-11-17T06:21:13.492Z
close_reason: "PR #490 merged at 2c4692bd7: the Files nav's ignored-files line is laid out from first paint, so the tally row holds its settled shape while counts fill in (tests/test_files_totals_stable_chrome.py: 0 px movement after first paint across all loads). Reviews A, B, C dispositioned; CI green at 64aa838ab."
resolution: null
duplicate_of: null
---
Owner, 2026-11-16: 'also on the main files nav panel, the + xxxx ignored line appears later, so the view shifts. this should never happen. if something is slow it should be laid out in a stable way with a progress box to show it is filling in'. The line is the ignored half of the tree summary (navigation.js tree-summary-split, .tree-summary-ignored). Measure the shift, hold the line's box while its count is unknown with the shell's pending placeholder, and audit the Files nav panel for any other late line.

## Notes

2026-11-17 handoff: PR #490 (claude/ignored-line-stable) reviewed A+B, both dispositions posted at 0855877; main merged twice (head f2c81b5f4); CI running. Merge when CI green; then close mb-h3hc and mb-w3va (W3VA reopened earlier by mistake-close). mb-a5pa, mb-v2ls remain as follow-ups.

2026-11-17: CI at f2c81b5f4 failed on test_files_totals_stable_chrome.py:171 (none unknown slow 180px light, 3.13); PR now conflicts with main in CHANGELOG.md after #491. See handoff PR #497.

2026-11-17 fix (head 8957c4d9): the f2c81b5f4 failure was a race in the check's session, not a layout shift and not the merged main (main touched nothing in the Files tree, totals, tree route, or event stream; the other three test jobs passed this check before fail-fast cancelled them). The failing load's only frame was already "No ignored files", so no held frame was recorded. It moved 0 px, its shift after first paint was 0, and its shift before first paint was the 180 px filter-bar wrap (0.00268, as in every 180 px load). Cause: the "unknown" loads stripped the shell's inlined totals and held the tally 2 s, but let the event stream's fs.snapshot through at once, and its root entry carries the same totals (server.py _root_totals). An instrumented copy of the session showed the line settling 2-33 ms after the snapshot in all 32 such loads; for the clean folder that was 17-100 ms after first paint, and in that CI run it was before the filter bar filled. Fix (test-only, tests/dom/files-totals-stable-chrome.mjs): every unknown load holds /api/events until the probe has recorded first paint, then releases it, so the held frame comes first by order rather than by a timing margin; provisional loads keep their 1.5 s release. Result: 40/40 instrumented unknown loads held first (snapshot 20-157 ms after first paint), and tests/test_files_totals_stable_chrome.py passed twice locally. Main (ae554dda) merged at e7af15cc, with the CHANGELOG conflict resolved by keeping both entries, this PR's above #491's. No golden was stale.
