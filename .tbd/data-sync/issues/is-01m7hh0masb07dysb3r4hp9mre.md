---
type: is
id: is-01m7hh0masb07dysb3r4hp9mre
title: "PR #466 A1: keyboard Group by prefetch starts a pass for every row passed"
kind: bug
status: closed
priority: 1
version: 3
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m7hcjpsxhfvt5ms7769smjwf
hold: null
hold_until: null
created_at: 2026-11-16T06:34:19.864Z
updated_at: 2026-11-16T07:26:32.668Z
started_at: 2026-11-16T06:34:32.418Z
closed_at: 2026-11-16T07:26:32.667Z
close_reason: "fixed in f913800 (keyboard dwell, stale in-flight entry left alone, session and Chrome checks); PR #466 review A"
resolution: null
duplicate_of: null
---
Medium. app.js:1562-1588, tree-filter-model.js:478-492. Review A https://github.com/jlevy/metabrowser/pull/466#pullrequestreview-5915498910. Fix: dwell before a keyboard prefetch, leave a stale in-flight entry alone, session step 'a row passed over asks for nothing' plus a Down, Down case; correct CHANGELOG.md:23 and design-system.md:2831.
