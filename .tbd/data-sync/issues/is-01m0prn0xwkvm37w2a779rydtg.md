---
type: is
id: is-01m0prn0xwkvm37w2a779rydtg
title: "PR #72 review R5: the tally row reservation leaves 7px of dead space under a filter"
kind: bug
status: open
priority: 2
version: 1
labels: []
dependencies: []
parent_id: is-01m0prm49eb29wxywrqtdck27b
created_at: 2026-08-23T07:34:07.548Z
updated_at: 2026-08-23T07:34:07.548Z
---
styles.css:1724 reserves calc(1.5*var(--nav-font-size) + 13px), baking in 12px padding and a 1px border. styles.css:2881-2884 removes border-bottom and padding-bottom when .tree-summary-filtered or .tree-selection-note follows, so the natural box is 25.5px and min-height forces 32.5px — reopening the gap that :has() rule exists to close, whenever a filter is active. Regression vs main. Fix: scope the reservation with :not(:has(...)), or add a matching override to the :has() rule.
