---
type: is
id: is-01kzcvmr0d1eyegyds8zpbffbz
title: "HTML P4: html kind, full-page detection, and sandboxed preview"
kind: feature
status: in_progress
priority: 1
version: 8
spec_path: docs/project/specs/active/plan-2026-08-06-html-rendering-and-trust-model.md
delegate: unknown@cursor
labels: []
dependencies: []
parent_id: is-01kzcvm6cpe5b8sb9b9n3gb16g
hold: null
hold_until: null
created_at: 2026-08-07T00:58:17.996Z
updated_at: 2026-09-18T18:32:44.479Z
started_at: 2026-09-18T04:31:31.949Z
extensions:
  linear:
    id: 4c13f679-cdd5-48b6-9f28-d6cd16cc62de
    linked_at: 2026-08-16T08:05:43.368Z
---
Add a built-in html kind for .html/.htm with preview and source views. A bounded 4 KiB sniff (doctype/<html/<head/<body/<frameset, BOM- and comment-tolerant) selects the default view only, never gates the feature. Preview renders an iframe with sandbox="allow-scripts allow-popups allow-forms allow-downloads" and referrerpolicy="no-referrer" — never allow-same-origin, never allow-top-navigation — with a disposal path. Fidelity envelope = file:// parity: classic scripts/styles/images/nested frames work; localStorage, same-document fetch, ES modules, CORS webfonts do not (and /raw must never send Access-Control-Allow-Origin to compensate). Suppress the preview view when active_content is off. Document the preview, its containment, and the invariant in SECURITY.md as shipped guarantees.

## Notes

HTML #152–#155 measured 393/560/176/1037. Combined vs main: 43 files, +1993/−125 (<~4k), so one parallel phase on main — not mixed into cache/git.

Branch pushed at existing tip SHA (no new commit): cursor/v011-html-trust-preview-bd04 @ 6a0fe8a8, base main, supersedes #152–#155 (sandbox /raw + same-origin /api, --untrusted, path-shaped /raw, html kind + preview).

gh write failed (Resource not accessible by integration). ManagePullRequest missing in this session. Draft PR not opened; #152–#155 not closed. Bead stays open for review; do not merge. Do not start mb-d658.
