---
type: is
id: is-01m75bn1xwnnwg5tvk3dz2vjkh
title: "PR #349 D9: a failed sanitizer load is cached, so retry cannot succeed"
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
created_at: 2026-11-11T13:09:44.507Z
updated_at: 2026-11-11T13:33:56.765Z
started_at: 2026-11-11T13:09:45.084Z
closed_at: 2026-11-11T13:33:56.764Z
close_reason: "Fixed in ee1289fb: a failed or empty sanitizer load is not kept, so the retry loads it again; DOM test added."
resolution: null
duplicate_of: null
---
Severity: Low. PR #349 review D: https://github.com/jlevy/metabrowser/pull/349#pullrequestreview-5859191069
