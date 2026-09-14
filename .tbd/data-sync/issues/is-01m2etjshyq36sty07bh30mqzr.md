---
type: is
id: is-01m2etjshyq36sty07bh30mqzr
title: Show loading progress, not 'Select a file to preview', while a folder view loads
kind: bug
status: open
priority: 1
version: 1
labels:
  - navigation
  - ux
dependencies: []
created_at: 2026-09-14T02:05:19.803Z
updated_at: 2026-09-14T02:05:19.803Z
---
Never show "Select a file to preview." merely because a view has not loaded yet; show progress, then content or an explicit empty state.

Observed: while a folder's view is still loading, the preview pane can read "Select a file to preview." Every folder selection, including the root landing, always has something loading: the folder Overview and, when present, its README. The placeholder is currently painted by:
- src/metabrowser/server.py ~1335 (the shell's initial preview pane);
- src/metabrowser/static/app.js ~3679 (a nav tab switch retires an in-flight loading placeholder by replacing it with the empty message);
- src/metabrowser/static/app.js ~7451 showNavigationLanding.

Expected:
1. While the selected folder's view (Overview, README) or a file preview is loading, the pane shows the standard progress indicator (the delayed-loading spinner pattern, with its accessible label), never the select-a-file message.
2. When the load settles, the pane shows the content. For an empty folder it shows a graceful empty state (for example "This folder is empty"), never an error. Server side this already works: for an empty folder, `metab <root> --show empty`, `--api "/api/file?path=empty"`, and `--api "/api/rollup?path=empty"` return 200 with a complete folder envelope and 0 files.
3. "Select a file to preview." appears only when nothing is selected and nothing is loading; the root landing selects the root folder, so in practice it should be rare.
4. A tab switch that invalidates an in-flight load must not leave the select-a-file message on screen; it restores the current selection's view or its loading state.

Acceptance: a browserless production-module session plus golden pins the pane state transitions (loading → content, loading → empty folder, tab switch during load, landing); an empty-folder browser check shows the empty state; CHANGELOG entry.
