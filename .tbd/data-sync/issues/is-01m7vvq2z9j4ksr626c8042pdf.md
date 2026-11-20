---
type: is
id: is-01m7vvq2z9j4ksr626c8042pdf
title: "PR Conversation comment boxes: more horizontal padding around the text, as a design-system rule"
kind: task
status: in_progress
priority: 2
version: 3
delegate: claude-code@spud10
labels: []
dependencies: []
hold: null
hold_until: null
created_at: 2026-11-20T06:53:45.831Z
updated_at: 2026-11-20T07:22:12.708Z
started_at: 2026-11-20T06:54:25.483Z
---
Owner, 2026-11-20: 'on the comment box at the top of the PR conversation overview, the text inside has too little padding. Let's update the design system consistently to have a little more padding on the left and right of the text in those boxes. The h2s are quite close to the left border.'

## Notes

PR 646 (claude/boxed-text-padding): token --boxed-prose-padding-inline (16px) in static/styles.css; --github-pull-text-inset and .git-commit-body read it; docs/design-system.md 'Boxed Prose'; Chrome measurement in tests/dom/github-pull-text-chrome.mjs; before/after screenshots in the worktree's attic/boxed-text-padding/.
