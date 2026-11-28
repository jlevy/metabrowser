---
type: is
id: is-01m8hj8hnhgn8342g68ddfp1ra
title: Restore explicit Git source choices through history and copied addresses
kind: feature
status: open
priority: 2
version: 4
spec_path: docs/project/specs/active/plan-2026-11-28-shared-navigation-history.md
labels: []
dependencies: []
created_at: 2026-11-28T17:11:49.680Z
updated_at: 2026-11-28T19:10:46.418Z
---
Implement phase 2 after the draft spec is reviewed. Specify source-qualified routes and validate restoration in browsers and the native host without changing other windows.

## Notes

Phase 2 routing decision. The URL describes the intended view, including any explicit Git source, path, presentation, and fragment. A named branch or PR-head URL serves the current tip; a fixed-revision URL serves that exact commit; a working-tree URL serves the live checkout. If the existing grammar obscures these distinctions, review it for explicit source forms while preserving the documented behavior of existing unqualified links. Use the same serving and cache-validation rules for direct open, reload, and history traversal. Leave Back and Forward to the browser’s or embedded WebKit view’s built-in history. Do not add a navigation-specific commit store, source-switch replay, or separate history resolver. Resolve a URL without changing what other windows display. Acceptance: open a file on main, leave the page, advance main, and go Back. Expect the current tip in both a browser and the native app. Repeat with a fixed-commit URL and expect the original revision in both.
