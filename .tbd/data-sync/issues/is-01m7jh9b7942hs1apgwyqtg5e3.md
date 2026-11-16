---
type: is
id: is-01m7jh9b7942hs1apgwyqtg5e3
title: "PR #464 B3: a new file that sorts last is inserted above the undrawn rows after a reveal drew the last page"
kind: bug
status: closed
priority: 3
version: 3
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m7hcjm7dvfsqanbt2jtdyxfy
hold: null
hold_until: null
created_at: 2026-11-16T15:58:19.880Z
updated_at: 2026-11-16T16:33:03.575Z
started_at: 2026-11-16T15:58:29.769Z
closed_at: 2026-11-16T16:33:03.573Z
close_reason: "fixed in 288a055: an arrival that sorts last goes before the last more row only when it ends the folder; session step fails without it. https://github.com/jlevy/metabrowser/pull/464#issuecomment-6922472756"
resolution: null
duplicate_of: null
---
Low. Review B (follow-up, round 2) on PR #464: https://github.com/jlevy/metabrowser/pull/464#pullrequestreview-5922595963. src/metabrowser/static/app.js:8084-8090 (_insertRowSorted anchors on the last "more" row, which after a reveal into the last page sits above the drawn page). Fix: anchor on the last "more" row only when it is the container's last .tree-item; otherwise append.
