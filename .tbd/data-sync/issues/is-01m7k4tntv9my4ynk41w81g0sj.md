---
type: is
id: is-01m7k4tntv9my4ynk41w81g0sj
title: The Files nav panel's '+ N ignored' summary line is laid out from first paint, holding the pending placeholder while its count fills in, so nothing below it moves
kind: bug
status: in_progress
priority: 1
version: 15
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
updated_at: 2026-11-17T01:03:47.505Z
started_at: 2026-11-16T21:40:37.650Z
---
Owner, 2026-11-16: 'also on the main files nav panel, the + xxxx ignored line appears later, so the view shifts. this should never happen. if something is slow it should be laid out in a stable way with a progress box to show it is filling in'. The line is the ignored half of the tree summary (navigation.js tree-summary-split, .tree-summary-ignored). Measure the shift, hold the line's box while its count is unknown with the shell's pending placeholder, and audit the Files nav panel for any other late line.
