---
type: is
id: is-01m85d2ydrwxsq3ne620b9kd98
title: "PR #768 A10: keep the free-space policy in core and let providers report a size"
kind: task
status: closed
priority: 3
version: 3
delegate: claude-code@vm
labels: []
dependencies: []
parent_id: is-01m85d2hj4x5fmcx1vdke1637w
hold: null
hold_until: null
created_at: 2026-11-23T23:50:30.072Z
updated_at: 2026-11-24T00:16:49.562Z
started_at: 2026-11-23T23:50:51.122Z
closed_at: 2026-11-24T00:16:49.562Z
close_reason: "fixed in d8acc98f, equivalently: comparison, reserve read and message live in core (refuse_below_reserve, refuse_unless_it_fits in cache/free_space.py); the provider passes the size gh reports"
resolution: null
duplicate_of: null
---
Low, design suggestion. src/metabrowser/cache/providers.py:202-209. The provider owns the comparison, reserve read and message; a second provider would copy all three. PR 768, review https://github.com/jlevy/metabrowser/pull/768#pullrequestreview-6031209981
