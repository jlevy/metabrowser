---
type: is
id: is-01kxz2ztvzj0tj8pp088rpmvp3
title: "P1: shell folder selection, dir hash routes, breadcrumb and up"
kind: task
status: open
priority: 1
version: 2
spec_path: docs/project/specs/active/plan-2026-07-20-folder-views-and-treemap-overview.md
labels: []
dependencies:
  - type: blocks
    target: is-01kxz3131cqxh1xc4zdq4x9ss8
parent_id: is-01kxz2z9v1bbfcfmqstffkhvxp
created_at: 2026-07-20T06:21:37.535Z
updated_at: 2026-07-20T06:22:31.436Z
---
app.js: renderTreeNodes folder rows get .tree-toggle[data-role=toggle] chevron + data-action=select-dir; tree click handler branches on closest('[data-role=toggle]') (keep shift-recursive), select-dir selects + expands (never collapses); parseHashRoute trailing-slash dir marker (#/ = root) skipping the anchor heuristic; selectFile writes dir hashes with trailing slash, skips fileCache/liveStream for kind folder; revealInTree matches .tree-item; renderFolderHeader(data) breadcrumb + up button + aggregate summary; init() lands on selectFile('') when no hash/initial/README. styles.css: .tree-toggle hover, folder header/breadcrumb rules. DOM tests under tests/dom/ for toggle/select split, hash roundtrip, breadcrumb nav. See spec 'Browser Shell'.
