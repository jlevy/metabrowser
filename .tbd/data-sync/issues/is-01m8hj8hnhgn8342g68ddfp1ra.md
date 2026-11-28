---
type: is
id: is-01m8hj8hnhgn8342g68ddfp1ra
title: Restore explicit Git source choices through history and copied addresses
kind: feature
status: open
priority: 2
version: 3
spec_path: docs/project/specs/active/plan-2026-11-28-shared-navigation-history.md
labels: []
dependencies: []
created_at: 2026-11-28T17:11:49.680Z
updated_at: 2026-11-28T19:10:06.422Z
---
Implement phase 2 after the draft spec is reviewed. Specify source-qualified routes and validate restoration in browsers and the native host without changing other windows.

## Notes

Phase 2 routing decision. The URL is the source of truth for the intended view, including any explicit Git source, path, presentation, and fragment. A named branch or PR-head URL resolves the current tip each time it opens, including on a Back or Forward landing or when an old document is restored from browser cache. Acceptance example: open a file on main, leave the page, advance main, and use Back. The file renders from the new tip. An explicit revision URL continues to show the exact commit after main moves. A working-tree URL resolves the live checkout. Direct open, reload, copied links, Back, and Forward share the route resolver. Do not add a history-specific commit store, convert a named head to a fixed revision merely because it has been resolved, or replay changes to the shared server pin. If the existing URL grammar obscures the source choice, review the grammar and propose explicit branch, commit, and working-tree forms. Preserve the documented behavior of existing unqualified links and resolve sources without changing what other windows display.
