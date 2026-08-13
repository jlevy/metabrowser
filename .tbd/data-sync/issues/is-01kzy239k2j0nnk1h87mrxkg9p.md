---
type: is
id: is-01kzy239k2j0nnk1h87mrxkg9p
title: "Treemap hierarchy: folders and files with shared file-type colors"
kind: feature
status: closed
priority: 1
version: 2
spec_path: docs/project/specs/active/plan-2026-07-20-folder-views-and-treemap-overview.md
labels:
  - ui
  - treemap
dependencies: []
parent_id: is-01kxz2z9v1bbfcfmqstffkhvxp
created_at: 2026-08-13T17:18:11.553Z
updated_at: 2026-08-13T18:12:40.816Z
closed_at: 2026-08-13T18:12:40.815Z
close_reason: Implemented hierarchy-only folder/file layout with shared Overview file-type palette mapping and neutral remainder behavior.
---
Make the Folder Treemap permanently spatially organized by its directory hierarchy, with folder and file cells present according to the rollup tree. Color every cell by its file type using the same per-folder category palette lease as the File Types Overview; directory cells use their dominant extension and aggregate/rest cells remain neutral. Remove the extension-grouped layout branch and obsolete ext-tally layout options while preserving weight conservation, nesting, keyboard navigation, and bounded DOM output. Acceptance: matching extensions receive the same palette class across Overview and Treemap, hierarchy is always navigable, and tests pin neutral remainder behavior.
