---
type: is
id: is-01kzcvmqr515dr7afbvc0e6krq
title: "HTML P3: path-shaped raw route so relative references resolve"
kind: task
status: in_progress
priority: 1
version: 7
spec_path: docs/project/specs/active/plan-2026-08-06-html-rendering-and-trust-model.md
delegate: unknown@cursor
labels: []
dependencies:
  - type: blocks
    target: is-01kzcvmr0d1eyegyds8zpbffbz
parent_id: is-01kzcvm6cpe5b8sb9b9n3gb16g
hold: null
hold_until: null
created_at: 2026-08-07T00:58:17.732Z
updated_at: 2026-09-18T04:43:22.894Z
started_at: 2026-09-18T04:27:04.031Z
extensions:
  linear:
    id: da24fe06-1e60-44e4-bad5-fd8a93098265
    linked_at: 2026-08-16T08:05:43.361Z
---
Add GET /raw/{path:path} alongside the existing query form, sharing one resolution and response path. Required for fidelity: with /raw?path=dir/page.html the document base is /raw, so every relative stylesheet, image, and sibling link breaks. Keep the query form (public API, live caller in the image renderer). Cover traversal, symlink escape, and percent-encoding equivalence across both routes.

## Notes

Draft https://github.com/jlevy/metabrowser/pull/154 stacked on #153. GET /raw/{path} shares the query-form handler and sandbox headers. Query form stays (inventory identities). Path form uses filesystem addresses like /view. CI green: 7 checks on aabdc5d573366d91d3beb54d4a436230b208a882 after pinning /raw/{path:path} in the route-index golden. Bead stays open for review; do not merge.
