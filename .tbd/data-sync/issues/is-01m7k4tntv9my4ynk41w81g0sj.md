---
type: is
id: is-01m7k4tntv9my4ynk41w81g0sj
title: The Files nav panel's '+ N ignored' summary line is laid out from first paint, holding the pending placeholder while its count fills in, so nothing below it moves
kind: bug
status: open
priority: 1
version: 19
delegate: claude-code@spud10.local
labels: []
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
hold: null
hold_until: null
created_at: 2026-11-16T21:39:50.746Z
updated_at: 2026-11-17T03:16:34.644Z
started_at: 2026-11-16T21:40:37.650Z
closed_at: null
close_reason: null
resolution: null
duplicate_of: null
---
Owner, 2026-11-16: 'also on the main files nav panel, the + xxxx ignored line appears later, so the view shifts. this should never happen. if something is slow it should be laid out in a stable way with a progress box to show it is filling in'. The line is the ignored half of the tree summary (navigation.js tree-summary-split, .tree-summary-ignored). Measure the shift, hold the line's box while its count is unknown with the shell's pending placeholder, and audit the Files nav panel for any other late line.

## Notes

2026-11-17 handoff: PR #490 (claude/ignored-line-stable) reviewed A+B, both dispositions posted at 0855877; main merged twice (head f2c81b5f4); CI running. Merge when CI green; then close mb-h3hc and mb-w3va (W3VA reopened earlier by mistake-close). mb-a5pa, mb-v2ls remain as follow-ups.

2026-11-17: CI at f2c81b5f4 failed on test_files_totals_stable_chrome.py:171 (none unknown slow 180px light, 3.13); PR now conflicts with main in CHANGELOG.md after #491. See handoff PR #497.
