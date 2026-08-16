---
type: is
id: is-01kzcvmqr515dr7afbvc0e6krq
title: "HTML P3: path-shaped raw route so relative references resolve"
kind: task
status: open
priority: 1
version: 3
spec_path: docs/project/specs/active/plan-2026-08-06-html-rendering-and-trust-model.md
labels: []
dependencies:
  - type: blocks
    target: is-01kzcvmr0d1eyegyds8zpbffbz
parent_id: is-01kzcvm6cpe5b8sb9b9n3gb16g
created_at: 2026-08-07T00:58:17.732Z
updated_at: 2026-08-16T08:05:43.361Z
extensions:
  linear:
    id: da24fe06-1e60-44e4-bad5-fd8a93098265
    linked_at: 2026-08-16T08:05:43.361Z
---
Add GET /raw/{path:path} alongside the existing query form, sharing one resolution and response path. Required for fidelity: with /raw?path=dir/page.html the document base is /raw, so every relative stylesheet, image, and sibling link breaks. Keep the query form (public API, live caller in the image renderer). Cover traversal, symlink escape, and percent-encoding equivalence across both routes.
