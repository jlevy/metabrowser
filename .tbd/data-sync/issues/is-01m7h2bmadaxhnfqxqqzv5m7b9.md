---
type: is
id: is-01m7h2bmadaxhnfqxqqzv5m7b9
title: "PR #442 B2: SEARCH_TEXTS and HIT_CHILDREN count text nodes, but a node's cost is up to LONG_TEXT characters"
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
created_at: 2026-11-16T02:18:11.660Z
updated_at: 2026-11-20T17:23:36.200Z
started_at: 2026-11-16T02:28:57.148Z
---
Medium finding B2 of review B on PR #442 (round 1, head 33b11020d21d2503ca60237f07b5f32795d3404e): https://github.com/jlevy/metabrowser/pull/442#pullrequestreview-5914046325

References: explorations/performance-loop/transitions-recorder.mjs:427, :385-394, :501, :441, :632; src/metabrowser/static/source-append.js:32

## Notes

Deferred from PR #442 (coordinator decision): the README now says a text node costs up to LONG_TEXT characters, so a view of many long text nodes (Load more's 64 KiB nodes under one <code>, source-append.js TEXT_NODE_MAX_LENGTH) costs more than the synthetic pages' short lines. Left: bound the walk by characters measured (a SEARCH_CHARS budget set from a measurement, sending the search on to the hit test once spent), or locate a long node by collapsed ranges at its start and end before slicing; add the many-node shape to transitions-search-cost.mjs and a Chrome check that R.lastSearch.chars stays under the bound scrolled to the end. Waits on the A/A run of revision 6 (mb-tpol).
