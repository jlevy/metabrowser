---
type: is
id: is-01m1apk7ckc3q95b9ymk041n8t
title: "PR #90 P90-16: Unused normalizer surface"
kind: bug
status: closed
priority: 3
version: 3
labels: []
dependencies: []
parent_id: is-01m1apk016z6h7ms919ekta9z0
created_at: 2026-08-31T01:23:00.114Z
updated_at: 2026-09-14T07:00:59.860Z
closed_at: 2026-09-14T07:00:59.859Z
close_reason: "Fixed in PR #116: removed NormalizeContext.home, normalize_mtimes, describe_schema, and their placeholders; no production caller on main (both CLI modes construct NormalizeContext(root=...) only). Tests that existed only for them removed; plan records the rules land with Phase 1A (mb-4gnu)."
resolution: null
duplicate_of: null
---
home, normalize_mtimes, and describe_schema have no production caller yet.
