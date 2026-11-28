---
type: is
id: is-01m8hj8hnhgn8342g68ddfp1ra
title: Restore explicit Git source choices through history and copied addresses
kind: feature
status: open
priority: 2
version: 2
spec_path: docs/project/specs/active/plan-2026-11-28-shared-navigation-history.md
labels: []
dependencies: []
created_at: 2026-11-28T17:11:49.680Z
updated_at: 2026-11-28T19:09:32.084Z
---
Implement phase 2 after the draft spec is reviewed. Specify source-qualified routes and validate restoration in browsers and the native host without changing other windows.

## Notes

Design decision for phase 2. The URL is the source of truth for the intended view, including any explicit Git source, route, and fragment. Direct open, reload, copied links, Back, and Forward must resolve the same URL through the same routing path. Do not add a history-specific source or commit store, or replay a previous change to the shared server pin. A branch route identifies the named branch, a commit route identifies the exact revision, and a working-tree route identifies the live checkout. Preserve the documented meaning of existing unqualified URLs. Work out how the route can read its source without changing what other windows display.
