---
type: is
id: is-01m6g1xny9dqq8xnxte85d7qah
title: "PR #285 C4: the design system states one history rule the file tree and Git do not follow"
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
created_at: 2026-11-03T06:35:38.311Z
updated_at: 2026-11-03T07:05:03.797Z
started_at: 2026-11-03T07:04:23.214Z
closed_at: 2026-11-03T07:05:03.796Z
close_reason: "fixed in b1dee9bf: design-system.md says what each collection does with a key, a click, and Enter, checked against v0.11.0 source"
resolution: null
duplicate_of: null
---
docs/design-system.md:1094-1096 and :1050-1051 say a click or Enter pushes in all three collections; Git replaces on a click, and Enter does nothing to history in Git or the file tree. Say what each does. Review: https://github.com/jlevy/metabrowser/pull/285#pullrequestreview-5747624823 (severity Low).
