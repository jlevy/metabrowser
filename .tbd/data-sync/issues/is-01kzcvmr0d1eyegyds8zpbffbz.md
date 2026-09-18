---
type: is
id: is-01kzcvmr0d1eyegyds8zpbffbz
title: "HTML P4: html kind, full-page detection, and sandboxed preview"
kind: feature
status: in_progress
priority: 1
version: 6
spec_path: docs/project/specs/active/plan-2026-08-06-html-rendering-and-trust-model.md
delegate: unknown@cursor
labels: []
dependencies: []
parent_id: is-01kzcvm6cpe5b8sb9b9n3gb16g
hold: null
hold_until: null
created_at: 2026-08-07T00:58:17.996Z
updated_at: 2026-09-18T04:44:38.208Z
started_at: 2026-09-18T04:31:31.949Z
extensions:
  linear:
    id: 4c13f679-cdd5-48b6-9f28-d6cd16cc62de
    linked_at: 2026-08-16T08:05:43.368Z
---
Add a built-in html kind for .html/.htm with preview and source views. A bounded 4 KiB sniff (doctype/<html/<head/<body/<frameset, BOM- and comment-tolerant) selects the default view only, never gates the feature. Preview renders an iframe with sandbox="allow-scripts allow-popups allow-forms allow-downloads" and referrerpolicy="no-referrer" — never allow-same-origin, never allow-top-navigation — with a disposal path. Fidelity envelope = file:// parity: classic scripts/styles/images/nested frames work; localStorage, same-document fetch, ES modules, CORS webfonts do not (and /raw must never send Access-Control-Allow-Origin to compensate). Suppress the preview view when active_content is off. Document the preview, its containment, and the invariant in SECURITY.md as shipped guarantees.

## Notes

Draft https://github.com/jlevy/metabrowser/pull/155 stacked on #154. html kind with Preview/Source, 4 KiB full-page sniff for the default tab, sandboxed iframe at path-shaped /raw/{path}, Preview omitted when active_content is off. Wheel smoke and serve banner now include html (6a0fe8a8). Bead stays open for review; do not merge. Next HTML slice is mb-d658 publication review.
