---
type: is
id: is-01m7hh0masb07dysb3r4hp9mre
title: "PR #466 A1: keyboard Group by prefetch starts a pass for every row passed"
kind: bug
status: in_progress
priority: 1
version: 2
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m7hcjpsxhfvt5ms7769smjwf
hold: null
hold_until: null
created_at: 2026-11-16T06:34:19.864Z
updated_at: 2026-11-16T06:34:32.420Z
started_at: 2026-11-16T06:34:32.418Z
---
Medium. app.js:1562-1588, tree-filter-model.js:478-492. Review A https://github.com/jlevy/metabrowser/pull/466#pullrequestreview-5915498910. Fix: dwell before a keyboard prefetch, leave a stale in-flight entry alone, session step 'a row passed over asks for nothing' plus a Down, Down case; correct CHANGELOG.md:23 and design-system.md:2831.
