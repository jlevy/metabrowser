---
type: is
id: is-01m6sxeyax9gqajg1b3csc9gmq
title: Automatically load changed files when a PR tree is expanded
kind: bug
status: in_progress
priority: 2
version: 2
spec_path: docs/project/specs/active/plan-2026-10-01-github-pulls-tab.md
labels: []
dependencies: []
parent_id: is-01m6f3n89kn7ztmfhrzswxnsgz
created_at: 2026-11-07T02:30:05.404Z
updated_at: 2026-11-07T03:08:26.355Z
---
Remove the normal “Its changed files have not been listed yet” and “List files” prompt. An intentional expansion uses cached metadata immediately or starts one bounded file-list fetch automatically. Preserve the shared progress spinner, offline cached rows, and a specific recovery message/action for a real failure. Reuse existing selected/visible prefetch when useful and avoid work from arrow-only selection.
