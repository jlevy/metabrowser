---
type: is
id: is-01m7zkv1jbvg6gt4sw55ec9rqg
title: Show installed plugins in macOS Settings and link the repository from About
kind: feature
status: in_progress
priority: 2
version: 4
spec_path: docs/project/specs/active/plan-2026-11-10-native-macos-app.md
refs:
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/683
    at: 2026-11-21T19:01:27.244Z
labels: []
dependencies: []
parent_id: is-01m748xpx7bjg68tfaf3q4nxmj
created_at: 2026-11-21T17:53:04.585Z
updated_at: 2026-11-21T19:01:27.246Z
---
Add a read-only plugin inventory to the native Settings information section, based on the existing metab --plugins --json command in the server environment. Keep actual preferences separate, link the full project URL from About, and document discovery and diagnostics.

## Notes

First-run, waiting-folder, and Check Setup paths surface discovery and version details and use the same GitHub README for installation and troubleshooting. Swift contract and app setup tests pass.
