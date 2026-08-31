---
type: is
id: is-01m1apk3v0xyqa2md5ryw1nr1h
title: "PR #90 P90-08: check_parity treats --walk and --diff as route evidence"
kind: bug
status: closed
priority: 2
version: 2
labels: []
dependencies: []
parent_id: is-01m1apk016z6h7ms919ekta9z0
created_at: 2026-08-31T01:22:56.479Z
updated_at: 2026-08-31T01:40:12.944Z
closed_at: 2026-08-31T01:40:12.944Z
close_reason: "Fixed on feat/cli-parity-mechanism; see the disposition map on PR #90."
resolution: null
duplicate_of: null
---
_INDIRECT_MODES includes --walk and --diff, which reach their models through the library and never issue a route. That reopens the model-versus-wire hole this PR exists to close.
