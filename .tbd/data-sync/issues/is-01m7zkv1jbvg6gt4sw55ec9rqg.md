---
type: is
id: is-01m7zkv1jbvg6gt4sw55ec9rqg
title: Show installed plugins in macOS Settings and link the repository from About
kind: feature
status: in_progress
priority: 2
version: 3
spec_path: docs/project/specs/active/plan-2026-11-10-native-macos-app.md
labels: []
dependencies: []
parent_id: is-01m748xpx7bjg68tfaf3q4nxmj
created_at: 2026-11-21T17:53:04.585Z
updated_at: 2026-11-21T18:17:37.887Z
---
Add a read-only plugin inventory to the native Settings information section, based on the existing metab --plugins --json command in the server environment. Keep actual preferences separate, link the full project URL from About, and document discovery and diagnostics.

## Notes

First-run, waiting-folder, and Check Setup paths surface discovery and version details and use the same GitHub README for installation and troubleshooting. Swift contract and app setup tests pass.
