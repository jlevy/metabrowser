---
type: is
id: is-01m8bp7frvh6qd5m9963agwg1m
title: "PR #874 C3: keep optional link loading off the text render's critical path"
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
created_at: 2026-11-26T10:25:42.682Z
updated_at: 2026-11-26T10:25:45.967Z
started_at: 2026-11-26T10:25:45.967Z
---
Review C, P2, static/git-panel.js:1454. A pending repository-links asset kept the commit body plain; PR texts, stack notes, and rendered diffs also awaited it. https://github.com/jlevy/metabrowser/pull/874#pullrequestreview-6071796228
