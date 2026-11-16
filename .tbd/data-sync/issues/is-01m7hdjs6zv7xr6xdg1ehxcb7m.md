---
type: is
id: is-01m7hdjs6zv7xr6xdg1ehxcb7m
title: "PR #461 A2: three of four changed review-state mappings have no test"
kind: bug
status: in_progress
priority: 2
version: 2
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m7hcjhzg676034x3900gjvgd
hold: null
hold_until: null
created_at: 2026-11-16T05:34:20.382Z
updated_at: 2026-11-16T05:34:29.913Z
started_at: 2026-11-16T05:34:29.912Z
---
Medium. src/metabrowser/builtin_plugins/github/pull-page.js:231-237, :548, :4908-4910. Fixture holds only APPROVED and COMMENTED. Fix: tests/dom/github-pull-timeline-session.js adds CHANGES_REQUESTED, DISMISSED and an unknown-state review, asserts each head's badge text, and no badge for PENDING and COMMENTED. PR #461, review A: https://github.com/jlevy/metabrowser/pull/461#pullrequestreview-5915431885
