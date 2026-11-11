---
type: is
id: is-01m75bmyd1prayaeevk82aw7ks
title: "PR #349 D4: a child that died idle yields a cached unsupported; a failed spawn is never retried"
kind: bug
status: closed
priority: 2
version: 3
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m75bmvxx4egd93b4ggyde6k2
hold: null
hold_until: null
created_at: 2026-11-11T13:09:40.896Z
updated_at: 2026-11-11T13:33:55.160Z
started_at: 2026-11-11T13:09:41.478Z
closed_at: 2026-11-11T13:33:55.159Z
close_reason: "Fixed in 37a4755b: an exited child or a broken pipe falls back to a thread for that request, and a failed spawn clears the start so a later projection retries."
resolution: null
duplicate_of: null
---
Severity: Low. PR #349 review D: https://github.com/jlevy/metabrowser/pull/349#pullrequestreview-5859191069
