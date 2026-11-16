---
type: is
id: is-01m7jh9b7942hs1apgwyqtg5e3
title: "PR #464 B3: a new file that sorts last is inserted above the undrawn rows after a reveal drew the last page"
kind: bug
status: in_progress
priority: 3
version: 2
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m7hcjm7dvfsqanbt2jtdyxfy
hold: null
hold_until: null
created_at: 2026-11-16T15:58:19.880Z
updated_at: 2026-11-16T15:58:29.770Z
started_at: 2026-11-16T15:58:29.769Z
---
Low. Review B (follow-up, round 2) on PR #464: https://github.com/jlevy/metabrowser/pull/464#pullrequestreview-5922595963. src/metabrowser/static/app.js:8084-8090 (_insertRowSorted anchors on the last "more" row, which after a reveal into the last page sits above the drawn page). Fix: anchor on the last "more" row only when it is the container's last .tree-item; otherwise append.
