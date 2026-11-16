---
type: is
id: is-01m7jeqmkzr97sa0qgethcse2q
title: "PR #452 A2: sse.py docstring says the live tail grows charts; it does not"
kind: bug
status: closed
priority: 3
version: 3
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m7hgpct6qpjeqfpyetf79fef
hold: null
hold_until: null
created_at: 2026-11-16T15:13:42.526Z
updated_at: 2026-11-16T15:27:45.950Z
started_at: 2026-11-16T15:14:14.650Z
closed_at: 2026-11-16T15:27:45.949Z
close_reason: "Fixed in c0a790e5a: sse.py docstring and app.js comment say the tail extends the Log view and cached events; charts do not grow."
resolution: null
duplicate_of: null
---
Low. src/metabrowser/sse.py:1-6,:16-17 vs static/app.js appendLiveEvents and docs/browsing-files.md:185. Review A on PR #452: https://github.com/jlevy/metabrowser/pull/452#pullrequestreview-5922214786
