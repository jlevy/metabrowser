---
type: is
id: is-01m036wy3pwxv6afsdx4qpx25j
title: Navigation tree rows are not real links
kind: feature
status: open
priority: 2
version: 2
labels: []
dependencies: []
created_at: 2026-08-15T17:18:18.230Z
updated_at: 2026-08-16T08:05:43.497Z
extensions:
  linear:
    id: 50793e33-3f25-40a8-a941-d87da73a1971
    linked_at: 2026-08-16T08:05:43.497Z
---
Rendered Markdown links now carry canonical /view/ hrefs, so middle-click, Cmd/Ctrl-click, copy-link, and the browser status preview all work inside a document. The file tree does not: rows are div elements with a data-path attribute and a click handler, so the primary navigation surface has none of that native behavior and its selection cannot be copied as a URL.

This is pre-existing rather than a regression from the /view/ work, but it is now the largest remaining inconsistency in the URL scheme: the same file is a real link in a document and an unlinkable div in the tree.

Scope: give tree rows (and any other shell navigation surface that selects a path) a real anchor with the canonical href from window.metabrowser.navigation.href, keep plain primary activation delegated to the SPA, and leave modifier and middle-click to the browser. Recent entries, quick-file results, and breadcrumbs deserve the same audit.
