---
type: is
id: is-01m6fr995ezm50x8vyrcnvz5xb
title: "PR #284 D6: say that a folder's comparison keeps honoring the reader's attributes and configuration where a store's does not"
kind: task
status: closed
priority: 3
version: 3
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m6fr829v5p0bx9wm4rr3z5wj
hold: null
hold_until: null
created_at: 2026-11-03T03:47:12.686Z
updated_at: 2026-11-03T03:52:30.800Z
started_at: 2026-11-03T03:47:30.623Z
closed_at: 2026-11-03T03:52:30.799Z
close_reason: "fixed in e610ebab: arch-views-models-routes.md and CHANGELOG.md say a store's reads see only its own info/attributes and a folder's comparison keeps honoring the reader's attributes and configuration"
resolution: null
duplicate_of: null
---
Low suggestion. docs/project/architecture/arch-views-models-routes.md (diff/comparison paragraph) and CHANGELOG.md: the asymmetry between a store's isolated reads and a folder's was unstated. Review D: https://github.com/jlevy/metabrowser/pull/284#pullrequestreview-5746804338.
