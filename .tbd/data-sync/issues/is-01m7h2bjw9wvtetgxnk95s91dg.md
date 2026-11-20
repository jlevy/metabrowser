---
type: is
id: is-01m7h2bjw9wvtetgxnk95s91dg
title: "PR #442 A12: the dwell sweep's 200 ms point is 50 ms under the 250 ms hover intent and can be bimodal"
kind: task
status: open
priority: 2
version: 5
spec_path: docs/project/specs/active/plan-2026-11-11-ui-apparent-performance.md
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m774q0ep0jq6vhb790rart0v
hold: null
hold_until: null
created_at: 2026-11-16T02:18:10.184Z
updated_at: 2026-11-20T17:23:25.552Z
started_at: 2026-11-16T02:28:57.126Z
---
Suggestion finding A12 of review A on PR #442 (round 1, head 33b11020d21d2503ca60237f07b5f32795d3404e): https://github.com/jlevy/metabrowser/pull/442#pullrequestreview-5913924421

References: explorations/performance-loop/README.md:992

## Notes

Deferred from PR #442: whether the 200 ms dwell point should move clear of the product's 250 ms hover intent, or each row should say whether the realized dwell (hoverDwellMs, recorded) crossed it, is H94's protocol's choice (mb-fejb); the instrument records the realized dwell and the README says the 200 ms point can land on either side of the intent.
