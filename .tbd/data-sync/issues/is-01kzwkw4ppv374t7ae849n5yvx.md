---
type: is
id: is-01kzwkw4ppv374t7ae849n5yvx
title: Stabilize folder envelopes and root routing
kind: task
status: open
priority: 1
version: 2
spec_path: docs/project/specs/active/plan-2026-08-12-directory-file-type-summary.md
labels:
  - backend
dependencies:
  - type: blocks
    target: is-01kzwkx7fnx68rfsx0d6y36w1w
parent_id: is-01kzwg302q9172bvjc543whcte
created_at: 2026-08-13T03:50:22.677Z
updated_at: 2026-08-13T03:50:58.292Z
---
Implement folder_discovery.py and the server.py folder-envelope/startup portions of the function map. Bound direct-child README discovery, run it off the event loop, always advertise Overview and Treemap, retain readme_path as data, remove root README auto-selection, and preserve safe-path/no-store behavior. Tests cover root and nested folders, unusual casing, symlinks, discovery cap, missing/traversal paths, empty folders, pending aggregates, and no-hash root Overview startup.
