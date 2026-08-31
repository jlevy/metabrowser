---
type: is
id: is-01m1apk3v0xyqa2md5ryw1nr1h
title: "PR #90 P90-08: check_parity treats --walk and --diff as route evidence"
kind: bug
status: open
priority: 2
version: 1
labels: []
dependencies: []
parent_id: is-01m1apk016z6h7ms919ekta9z0
created_at: 2026-08-31T01:22:56.479Z
updated_at: 2026-08-31T01:22:56.479Z
---
_INDIRECT_MODES includes --walk and --diff, which reach their models through the library and never issue a route. That reopens the model-versus-wire hole this PR exists to close.
