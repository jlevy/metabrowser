---
type: is
id: is-01m6hrdycpqxatz8424yb9p6mv
title: Refresh changed-file force-push golden through the metadata catalog
kind: bug
status: in_progress
priority: 2
version: 2
spec_path: docs/project/specs/active/plan-2026-10-01-github-pulls-tab.md
delegate: codex@spud10
labels: []
dependencies: []
parent_id: is-01m6hkbt0t0qhvrhxhktgefe38
hold: null
hold_until: null
created_at: 2026-11-03T22:28:14.352Z
updated_at: 2026-11-03T22:28:37.645Z
started_at: 2026-11-03T22:28:37.641Z
---
Full verification at6b93a964 reproduced a changed-files transcript failure: the force-push scenario updates the removed REST list fixture and sends an implicit old All-default request, so the new GraphQL catalog never publishes its changed row and the asserted file-list staleness does not occur. Update the fixture to catalog_entries and the explicit all/target request, preserving stale-then-conditional-reread assertions. Regenerate only the actual production transcript with explicit observed catalog-epoch labeling, then check unchanged files failures and related session goldens. No product behavior should change.
