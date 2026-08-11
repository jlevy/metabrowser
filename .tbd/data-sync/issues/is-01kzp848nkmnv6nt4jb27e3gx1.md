---
type: is
id: is-01kzp848nkmnv6nt4jb27e3gx1
title: Extension tallies exclude gitignored files
kind: bug
status: closed
priority: 2
version: 2
spec_path: docs/project/specs/active/plan-2026-08-09-nav-filter-controls.md
labels:
  - ui
dependencies: []
parent_id: is-01kzp82ktssqmf4fhm8sxmvb6p
created_at: 2026-08-10T16:29:39.379Z
updated_at: 2026-08-10T18:19:50.246Z
closed_at: 2026-08-10T18:19:50.245Z
close_reason: Tallies now come from InventoryIndex.extension_tally on /api/tree, with tracked and ignored counts kept apart so the menu follows Show ignored. Also fixed the ranking, which still used server totals after the count switch.
---
InventoryIndex.catalog_files() filters out gitignored entries, so the known-file catalog the extension menu tallies from never sees them. With the Gitignored checkbox on (the default) the tree shows rows the menu did not count, and a count next to an extension understates it. Fix means widening the catalog feed or tallying from a second source.
