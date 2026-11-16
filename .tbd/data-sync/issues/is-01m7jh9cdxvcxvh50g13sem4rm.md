---
type: is
id: is-01m7jh9cdxvcxvh50g13sem4rm
title: "PR #464 B5: two wording slips (Show 400 more; a changed file's address never reveals)"
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
created_at: 2026-11-16T15:58:21.113Z
updated_at: 2026-11-16T15:58:30.619Z
started_at: 2026-11-16T15:58:30.617Z
---
Low. Review B (follow-up, round 2) on PR #464: https://github.com/jlevy/metabrowser/pull/464#pullrequestreview-5922595963. docs/design-system.md:3279 says "Show 400 more" (the fixture's count), app.js:8851-8852 says a changed file's address never reveals the pull request's row, true only for the pull request shown. Fix: "Show N more", and "a changed file of the pull request shown never reveals its row".
