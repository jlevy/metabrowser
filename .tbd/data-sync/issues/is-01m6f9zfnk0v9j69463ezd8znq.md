---
type: is
id: is-01m6f9zfnk0v9j69463ezd8znq
title: "gh runner: a deeply nested GitHub body raises RecursionError past the typed failures"
kind: bug
status: open
priority: 3
version: 2
labels: []
dependencies: []
parent_id: is-01m402dbhn3zsc1h896f3xnrsq
created_at: 2026-11-02T23:37:11.602Z
updated_at: 2026-11-14T18:45:04.397Z
---
Found 2026-11-02 by the security review of PR 279, pre-existing on main, reproduced with the fake gh. GhResponse.json in builtin_plugins/github/gh.py (near lines 189-193) and _mentions_rate_limit (near line 416) catch only ValueError, so a RecursionError from json.loads on a deeply nested body escapes the typed failures; gh_lists.response_json converts only GhError. The body is GitHub-controlled, not user-controlled, and should end as gh_failed. The other half of the original report, a twenty-digit Retry-After or X-Ratelimit-Reset raising OverflowError, was fixed by b416cb7c: rate_limit_reset now answers "unknown".
