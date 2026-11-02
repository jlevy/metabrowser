---
type: is
id: is-01m6f9zfnk0v9j69463ezd8znq
title: "gh runner: huge Retry-After values and deeply nested bodies raise past the typed failures"
kind: bug
status: open
priority: 3
version: 1
labels: []
dependencies: []
parent_id: is-01m402dbhn3zsc1h896f3xnrsq
created_at: 2026-11-02T23:37:11.602Z
updated_at: 2026-11-02T23:37:11.602Z
---
Found 2026-11-02 by the security review of PR 279, pre-existing on main, reproduced with the fake gh. gh.py near lines 309-313: a twenty-digit Retry-After or X-Ratelimit-Reset raises OverflowError. gh.py near lines 150-154: RecursionError from a deeply nested body escapes. Both are GitHub-controlled, not user-controlled, and should end as gh_failed.
