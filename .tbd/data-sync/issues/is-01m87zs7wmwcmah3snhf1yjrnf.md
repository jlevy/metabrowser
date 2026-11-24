---
type: is
id: is-01m87zs7wmwcmah3snhf1yjrnf
title: "Expand between hunks: @@ -a,b +c,d @@ separators open the hidden lines like a fold"
kind: feature
status: open
priority: 2
version: 1
labels: []
dependencies: []
created_at: 2026-11-24T23:55:43.881Z
updated_at: 2026-11-24T23:55:43.881Z
---
User request 2026-11-24: the hunk separators in the source diff (@@ ranges) should be expandable, fetching the unchanged lines between hunks (and before the first and after the last), in the same fold design as the other collapsible chunks (see the fold-design bead). Needs the lines from the snapshot through a route reachable from metab --api with a golden (parity), fetched on demand, bounded by measured size.
