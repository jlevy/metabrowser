---
type: is
id: is-01m6hkgedpcnemk1d6x6tqrwen
title: Persist and incrementally backfill the lightweight PR catalog with exact totals
kind: feature
status: closed
priority: 1
version: 5
spec_path: docs/project/specs/active/plan-2026-10-01-github-pulls-tab.md
delegate: checkout_design
labels: []
dependencies: []
parent_id: is-01m6hkbt0t0qhvrhxhktgefe38
hold: null
hold_until: null
created_at: 2026-11-03T21:02:13.429Z
updated_at: 2026-11-04T17:14:29.941Z
started_at: 2026-11-03T21:06:07.926Z
closed_at: 2026-11-04T17:14:29.941Z
close_reason: "Scoped implementation independently reviewed and tested; owning feature PRs are actually merged. Final main https://github.com/jlevy/metabrowser/commit/db52ec09cf839269da3a56fd396e44f3092995a9 includes account fix https://github.com/jlevy/metabrowser/pull/297 and documentation https://github.com/jlevy/metabrowser/pull/298, with final manual acceptance and per-issue qualifications checked. Individual source, test, review and merge evidence: ACTION-PLAN.json SHA-256 d0867a696ee055cc27911e83c4f70744b419a3ca4a7a1218f0eeaf419dc37589. Future scope and historical dependency relationships remain open or preserved as recorded."
resolution: null
duplicate_of: null
---

## Notes

2026-11-03 author checkpoint: implemented the private SQLite catalog, fixed GraphQL metadata queries, exact provider totals, bounded indexed windows, resumable all-PR backfill, inclusive updatedAt refresh, account/repository identity reset, and page-fair scheduling. Obsolete list JSON models/caps removed and current CLI/cache/API references updated. Final owned catalog plus real CLI tests: 75 passed in 12.44s; types and lint clean. Earlier affected catalog/file-list/detail run: 205 passed in 166.74s. Evidence: catalog-backend-author/final-catalog-and-cli.log and final-types.log. Source remains uncommitted on the coordinator branch, pending final independent review and integrated gates.
