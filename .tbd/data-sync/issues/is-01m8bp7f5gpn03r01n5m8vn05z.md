---
type: is
id: is-01m8bp7f5gpn03r01n5m8vn05z
title: "PR #874 C2: a GitHub way out of a missing commit"
kind: bug
status: in_progress
priority: 2
version: 2
spec_path: docs/project/specs/active/plan-2026-11-26-in-app-link-resolution.md
delegate: claude-code@vm
labels: []
dependencies: []
parent_id: is-01m8bp7ce37pgee1zpr3wrq5q6
hold: null
hold_until: null
created_at: 2026-11-26T10:25:42.063Z
updated_at: 2026-11-26T10:25:45.558Z
started_at: 2026-11-26T10:25:45.558Z
---
Review C, P2, repository-links.js:407. A same-repository commit link became /commit/<id> in a shallow checkout lacking it, and the missing state had no link back to GitHub. https://github.com/jlevy/metabrowser/pull/874#pullrequestreview-6071796228
