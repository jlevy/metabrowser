---
type: is
id: is-01m7327d4wd92r1n5bnmr1b0zb
title: Implement cache-first PR review and rendered Markdown
kind: epic
status: open
priority: 2
version: 6
spec_path: docs/project/specs/active/plan-2026-11-02-pr-review-mirror-and-checkout.md
labels: []
dependencies: []
child_order_hints:
  - is-01m715sezspp55zz5v346nrv9n
  - is-01m715sfem46c801k52wr03qt6
  - is-01m715y0nv4hwkwvkvfze1m4r1
  - is-01m718rgbk80mnnjb8d4b1r4xz
  - is-01m73288nre2ajj6ve3p0c9b86
created_at: 2026-11-10T15:46:31.195Z
updated_at: 2026-11-10T15:46:59.383Z
---
Implement the reviewed designs in #346 in dependency order. Stack after #346: exact immutable revision views; bounded eager comparison preparation and keyed GitHub reads; Markdown rendered diffs. Keep checkout and managed modes on the same snapshot path and verify cold, warm, offline and concurrent sessions.
