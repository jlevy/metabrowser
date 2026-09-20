---
type: is
id: is-01kzcvmqr515dr7afbvc0e6krq
title: "HTML P3: path-shaped raw route so relative references resolve"
kind: task
status: closed
priority: 1
version: 9
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
updated_at: 2026-09-20T05:50:32.701Z
started_at: 2026-09-18T04:27:04.031Z
closed_at: 2026-09-20T05:50:32.701Z
close_reason: "Implemented on survivor draft #209 https://github.com/jlevy/metabrowser/pull/209 (parallel to stack #218). Publication review remains mb-d658. Nothing merged to main."
resolution: null
duplicate_of: null
extensions:
  linear:
    id: da24fe06-1e60-44e4-bad5-fd8a93098265
    linked_at: 2026-08-16T08:05:43.361Z
---
Add GET /raw/{path:path} alongside the existing query form, sharing one resolution and response path. Required for fidelity: with /raw?path=dir/page.html the document base is /raw, so every relative stylesheet, image, and sibling link breaks. Keep the query form (public API, live caller in the image renderer). Cover traversal, symlink escape, and percent-encoding equivalence across both routes.

## Notes

HTML #152–#155 measured 393/560/176/1037. Combined vs main: 43 files, +1993/−125 (<~4k), so one parallel phase on main — not mixed into cache/git.

Branch pushed at existing tip SHA (no new commit): cursor/v011-html-trust-preview-bd04 @ 6a0fe8a8, base main, supersedes #152–#155 (sandbox /raw + same-origin /api, --untrusted, path-shaped /raw, html kind + preview).

gh write failed (Resource not accessible by integration). ManagePullRequest missing in this session. Draft PR not opened; #152–#155 not closed. Bead stays open for review; do not merge. Do not start mb-d658.
