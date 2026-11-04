---
type: is
id: is-01m6hrdycpqxatz8424yb9p6mv
title: Refresh changed-file force-push golden through the metadata catalog
kind: bug
status: closed
priority: 2
version: 3
spec_path: docs/project/specs/active/plan-2026-10-01-github-pulls-tab.md
delegate: codex@spud10
labels: []
dependencies: []
parent_id: is-01m6hkbt0t0qhvrhxhktgefe38
hold: null
hold_until: null
created_at: 2026-11-03T22:28:14.352Z
updated_at: 2026-11-04T17:14:29.693Z
started_at: 2026-11-03T22:28:37.641Z
closed_at: 2026-11-04T17:14:29.693Z
close_reason: "Scoped implementation independently reviewed and tested; owning feature PRs are actually merged. Final main https://github.com/jlevy/metabrowser/commit/db52ec09cf839269da3a56fd396e44f3092995a9 includes account fix https://github.com/jlevy/metabrowser/pull/297 and documentation https://github.com/jlevy/metabrowser/pull/298, with final manual acceptance and per-issue qualifications checked. Individual source, test, review and merge evidence: ACTION-PLAN.json SHA-256 d0867a696ee055cc27911e83c4f70744b419a3ca4a7a1218f0eeaf419dc37589. Future scope and historical dependency relationships remain open or preserved as recorded."
resolution: null
duplicate_of: null
---
Full verification at6b93a964 reproduced a changed-files transcript failure: the force-push scenario updates the removed REST list fixture and sends an implicit old All-default request, so the new GraphQL catalog never publishes its changed row and the asserted file-list staleness does not occur. Update the fixture to catalog_entries and the explicit all/target request, preserving stale-then-conditional-reread assertions. Regenerate only the actual production transcript with explicit observed catalog-epoch labeling, then check unchanged files failures and related session goldens. No product behavior should change.
