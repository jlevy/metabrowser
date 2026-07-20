---
type: is
id: is-01ky071eaj0gb21nxtnzsgtffn
title: "Navigation equivalence: history semantics for folder zooms"
kind: task
status: open
priority: 2
version: 1
spec_path: docs/project/specs/active/plan-2026-07-20-folder-views-and-treemap-overview.md
labels: []
dependencies: []
parent_id: is-01kxz2z9v1bbfcfmqstffkhvxp
created_at: 2026-07-20T16:51:38.962Z
updated_at: 2026-07-20T16:51:38.962Z
---
Spec invariant 4 ('Navigation Equivalence' section of the folder-views spec): folder-to-folder navigation uses history.pushState so browser back retraces zooms; file selection keeps replaceState; popstate routes through navigateToPath; guard against pushState loops from hashchange re-entry. DOM tests for the back-button trail across tree clicks, treemap cell zooms, breadcrumb, and up.
