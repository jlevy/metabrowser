---
type: is
id: is-01m6hkgedpcnemk1d6x6tqrwen
title: Persist and incrementally backfill the lightweight PR catalog with exact totals
kind: feature
status: in_progress
priority: 1
version: 4
spec_path: docs/project/specs/active/plan-2026-10-01-github-pulls-tab.md
delegate: checkout_design
labels: []
dependencies: []
parent_id: is-01m6hkbt0t0qhvrhxhktgefe38
hold: null
hold_until: null
created_at: 2026-11-03T21:02:13.429Z
updated_at: 2026-11-03T21:42:59.186Z
started_at: 2026-11-03T21:06:07.926Z
---

## Notes

2026-11-03 author checkpoint: implemented the private SQLite catalog, fixed GraphQL metadata queries, exact provider totals, bounded indexed windows, resumable all-PR backfill, inclusive updatedAt refresh, account/repository identity reset, and page-fair scheduling. Obsolete list JSON models/caps removed and current CLI/cache/API references updated. Final owned catalog plus real CLI tests: 75 passed in 12.44s; types and lint clean. Earlier affected catalog/file-list/detail run: 205 passed in 166.74s. Evidence: catalog-backend-author/final-catalog-and-cli.log and final-types.log. Source remains uncommitted on the coordinator branch, pending final independent review and integrated gates.
