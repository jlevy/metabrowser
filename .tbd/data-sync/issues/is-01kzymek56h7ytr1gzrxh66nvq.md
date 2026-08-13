---
type: is
id: is-01kzymek56h7ytr1gzrxh66nvq
title: Show generic icons for non-extension Files rows
kind: task
status: closed
priority: 2
version: 3
spec_path: docs/project/specs/done/plan-2026-08-12-directory-file-type-summary.md
labels:
  - browser
  - design-system
  - folder-overview
dependencies: []
parent_id: is-01kzwg302q9172bvjc543whcte
created_at: 2026-08-13T22:38:56.165Z
updated_at: 2026-08-13T22:56:07.614Z
closed_at: 2026-08-13T22:56:07.614Z
close_reason: "Implemented and verified in f2ea147: live watcher reconciliation keeps rebuilt directories indexed, completed misses are terminal, and non-extension breakdown rows use the generic file icon."
---
Use the shared generic blank-page file icon for No extension and Remaining types rows in the folder Files breakdown, matching the fallback used for .bin. Keep Total and Ignored as aggregate rows without file-type icons, and update tests and design documentation.
