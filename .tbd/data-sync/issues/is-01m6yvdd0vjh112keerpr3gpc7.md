---
type: is
id: is-01m6yvdd0vjh112keerpr3gpc7
title: Toggle focused collapsible navigation rows with Space
kind: bug
status: in_progress
priority: 1
version: 3
labels: []
dependencies:
  - type: blocks
    target: is-01m5wdbsy6z6d95sgg03kwmm76
parent_id: is-01m6f3n89kn7ztmfhrzswxnsgz
created_at: 2026-11-09T00:30:29.914Z
updated_at: 2026-11-09T00:30:48.306Z
---
Space on a focused expandable PR row should expand or collapse the changed-file tree, matching Files and Commits. Preserve selection, focus, and the current page. Do not intercept native Space activation on nested buttons or scroll the page. Audit other collapsible navigation rows and verify the keyboard path in a browser and a focused regression.
