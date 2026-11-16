---
type: is
id: is-01m7k4tntv9my4ynk41w81g0sj
title: The Files nav panel's '+ N ignored' summary line is laid out from first paint, holding the pending placeholder while its count fills in, so nothing below it moves
kind: bug
status: open
priority: 1
version: 1
labels: []
dependencies: []
parent_id: is-01m7dm3az28qmj39y5hmdq2k0v
created_at: 2026-11-16T21:39:50.746Z
updated_at: 2026-11-16T21:39:50.746Z
---
Owner, 2026-11-16: 'also on the main files nav panel, the + xxxx ignored line appears later, so the view shifts. this should never happen. if something is slow it should be laid out in a stable way with a progress box to show it is filling in'. The line is the ignored half of the tree summary (navigation.js tree-summary-split, .tree-summary-ignored). Measure the shift, hold the line's box while its count is unknown with the shell's pending placeholder, and audit the Files nav panel for any other late line.
