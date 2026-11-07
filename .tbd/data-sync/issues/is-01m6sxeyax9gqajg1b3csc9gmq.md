---
type: is
id: is-01m6sxeyax9gqajg1b3csc9gmq
title: Automatically load changed files when a PR tree is expanded
kind: bug
status: closed
priority: 2
version: 5
spec_path: docs/project/specs/active/plan-2026-10-01-github-pulls-tab.md
labels: []
dependencies: []
parent_id: is-01m6f3n89kn7ztmfhrzswxnsgz
created_at: 2026-11-07T02:30:05.404Z
updated_at: 2026-11-07T04:55:40.464Z
closed_at: 2026-11-07T04:55:40.463Z
close_reason: "PR #319 reviewed head f61dad59 is green in CI. Automatic cold listing, cached use, reopen polling, damaged-cache repair, rate/failure holds, shared spinner and Retry focus pass the focused production-path sessions and full gate. Ready for owner merge."
resolution: null
duplicate_of: null
---
Remove the normal “Its changed files have not been listed yet” and “List files” prompt. An intentional expansion uses cached metadata immediately or starts one bounded file-list fetch automatically. Preserve the shared progress spinner, offline cached rows, and a specific recovery message/action for a real failure. Reuse existing selected/visible prefetch when useful and avoid work from arrow-only selection.

## Notes

PR #319 review corrections are in a6e7e427 and integrated at ab905365. Fresh missing, malformed, or schema-mismatched caches automatically repair after a prior success; failure and provider rate holds are preserved. Idle no-work responses show Retry. A removed focused Retry button transfers focus to the existing tree/owner. All 75 targeted tests, both browser type configurations, focused type analysis and formatting passed. Exact-head full gate is running before the forward push.
