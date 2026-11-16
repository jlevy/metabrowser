---
type: is
id: is-01m7k4kq96y8azzpxt989vgctz
title: "PR #484 A4: headings with no line pulse and go blank again in every window"
kind: bug
status: in_progress
priority: 2
version: 2
spec_path: docs/project/specs/active/plan-2026-11-15-files-grouping-diff-summary-and-pull-stacks.md
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m7jwtbafwhwvmsjwvzvz9xg9
hold: null
hold_until: null
created_at: 2026-11-16T21:36:02.853Z
updated_at: 2026-11-16T21:36:12.968Z
started_at: 2026-11-16T21:36:12.967Z
---
Medium. stack-lines.js:343-346 returns waiting after the window; tests/dom/github-pulls-stack-lines-chrome.mjs:331, :406-409 pin pulse-then-blank. Review A (round 1) of PR #484: https://github.com/jlevy/metabrowser/pull/484#pullrequestreview-5928039724
