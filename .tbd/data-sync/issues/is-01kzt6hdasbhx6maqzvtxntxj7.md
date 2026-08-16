---
type: is
id: is-01kzt6hdasbhx6maqzvtxntxj7
title: "Repo cache Phase 2: large-repo mode via shallow clone plus progressive deepening"
kind: feature
status: open
priority: 3
version: 2
spec_path: docs/project/specs/active/plan-2026-08-11-open-repo-from-git-url.md
labels: []
dependencies: []
created_at: 2026-08-12T05:18:50.711Z
updated_at: 2026-08-16T08:05:43.459Z
extensions:
  linear:
    id: 7766c0ab-8af4-4ee0-a3c5-d984d20cb1db
    linked_at: 2026-08-16T08:05:43.459Z
---
Deferred optimization for repositories where the Phase 1 blobless path is still too slow. Clone --depth=1 --single-branch --filter=blob:none (django: 14.6s, 14MB .git) and deepen in pages: fetch --deepen=500 measured 1.25s for the first 500 commits, ~12,500 commits at 35MB, versus a 90s all-or-nothing --unshallow.

Hard requirements: blame MUST be disabled while .git/shallow exists (a shallow blame exits 0 and attributes every line to the graft-boundary commit), and history must be marked truncated at the boundary. /api/git/ needs to report shallow-state capability so the panel can honor it.

Not needed for the feature to work end to end — Phase 1 opens django in 16.5s. Start when a repo large enough to justify it is actually in the way.
