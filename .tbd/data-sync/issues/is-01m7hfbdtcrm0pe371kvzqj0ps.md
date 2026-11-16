---
type: is
id: is-01m7hfbdtcrm0pe371kvzqj0ps
title: "PR #473 A7: pin every heading-tally builder to one node sequence and the design system's list"
kind: bug
status: in_progress
priority: 3
version: 2
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m7he951v8gwjt3ejjes5d4ab
hold: null
hold_until: null
created_at: 2026-11-16T06:05:16.491Z
updated_at: 2026-11-16T06:05:26.125Z
started_at: 2026-11-16T06:05:26.124Z
---
Suggestion. app.js:1609-1613 and pull-page.js:5191-5198 build the markup twice; docs/design-system.md:4019-4022 lists users in prose only. Coordinator chose the test_design_vocabulary.py check. Review A round 1 on PR #473: https://github.com/jlevy/metabrowser/pull/473#pullrequestreview-5915676394
