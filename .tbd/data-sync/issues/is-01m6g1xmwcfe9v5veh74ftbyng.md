---
type: is
id: is-01m6g1xmwcfe9v5veh74ftbyng
title: "PR #285 C3: the window guard and the whole-read guard are unpinned"
kind: bug
status: closed
priority: 2
version: 3
spec_path: docs/project/specs/active/plan-2026-10-01-github-pulls-tab.md
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m6g1x4rv0qbdqdqdz64p3qn0
hold: null
hold_until: null
created_at: 2026-11-03T06:35:37.226Z
updated_at: 2026-11-03T07:05:03.450Z
started_at: 2026-11-03T07:04:22.857Z
closed_at: 2026-11-03T07:05:03.450Z
close_reason: "fixed in 2cfed240: two step groups on newly recorded at-cap answers; M12 and M16 now fail cli-ui-github-pulls-panel"
resolution: null
duplicate_of: null
---
pulls-panel.js:885 (window answered for rows a poll replaced) and :694 (list.version !== version) are load-bearing in a harness but mutations M12 and M16 pass the panel golden. Add two session steps. Review: https://github.com/jlevy/metabrowser/pull/285#pullrequestreview-5747624823 (severity Low).
