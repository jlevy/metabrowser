---
type: is
id: is-01m0fvkdykbbdhefdpc0mrgghf
title: "Branch chips: their own vocabulary — bold, square"
kind: bug
status: closed
priority: 2
version: 2
labels: []
dependencies: []
created_at: 2026-08-20T15:11:00.042Z
updated_at: 2026-08-20T15:28:43.003Z
closed_at: 2026-08-20T15:28:43.002Z
close_reason: "Landed in 4554983: .git-ref bold on --radius-tag square corners as its own Branch Chips vocabulary; HEAD distinguished by a hairline ring"
---
Git ref badges (branch/tag chips in the graph and commit view) are their own vocabulary, not filter chips: at their small size the name must be boldface, and corners go square-ish (small radius) instead of pill-rounded. Document as Branch Chips in design-system.md and pin the weight/radius in test_design_vocabulary.py.
