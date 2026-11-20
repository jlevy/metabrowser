---
type: is
id: is-01m7h2bkwq2pzqp6q48zp3anhr
title: "PR #442 B1: the search is bounded, but the rest of each frame's read makes 15 selector traversals of the view"
kind: bug
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
created_at: 2026-11-16T02:18:11.222Z
updated_at: 2026-11-20T17:23:30.177Z
started_at: 2026-11-16T02:28:57.134Z
---
Medium finding B1 of review B on PR #442 (round 1, head 33b11020d21d2503ca60237f07b5f32795d3404e): https://github.com/jlevy/metabrowser/pull/442#pullrequestreview-5914046325

References: explorations/performance-loop/transitions-recorder.mjs:722, :728, :739, :813-816, :858-866, :907-908, :689, :416; README.md:903; transitions-stats.mjs:11-17

## Notes

Deferred from PR #442 (coordinator decision): the README and READ_COST_CEILING_MS comment now say the 4 ms ceiling and the search's bound cover the search only, not the rest of a read. Left: (1) measure the whole read (state's prompt and placeholder queries, the 16 REGIONS selectors, the alert query, the ready predicate's placeholder query) on the large shapes review B counted (Markdown of 10,000 paragraphs, highlighted source of 8,671 lines, diff tables of 1,000 and 20,000 rows) and on #349's Changes and app.js frames, recording it beside READ_COST_CEILING_MS; (2) where it nears the ceiling, cut the traversals: cache placeholders(root) per read, answer the prompt and placeholder queries in one pass, resolve the '#preview-pane >' regions through pane.children, look the palette regions up inside the overlay. Waits on the A/A run of revision 6 (mb-tpol), which gives the read costs on the product's own views.
