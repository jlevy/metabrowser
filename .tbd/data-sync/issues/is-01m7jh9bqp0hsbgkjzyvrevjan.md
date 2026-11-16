---
type: is
id: is-01m7jh9bqp0hsbgkjzyvrevjan
title: 'PR #464 B4: a live update corrects the total of only one "more" row'
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
created_at: 2026-11-16T15:58:20.405Z
updated_at: 2026-11-16T15:58:30.196Z
started_at: 2026-11-16T15:58:30.194Z
---
Low. Review B (follow-up, round 2) on PR #464: https://github.com/jlevy/metabrowser/pull/464#pullrequestreview-5922595963. src/metabrowser/static/app.js:7988-7992 and :8009 (_synchronizeDeferredTreePage renumbers every row but writes the total into only the page it was given). Rows a stale page draws get a total one short (renderTreeNodes, :2295). Fix: write the total into every "more" row of the container, its page's options.setSize and its label.
