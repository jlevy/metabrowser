---
type: is
id: is-01m7rrz0nqayqnha5hj3j2q238
title: "Flaky: test_e2e_filesystem_to_sse.py:216 counts more events than expected under load"
kind: bug
status: closed
priority: 2
version: 9
refs:
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/598
    at: 2026-11-20T17:03:56.768Z
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m2gb3gpn7vcsw0as4xa243tg
hold: null
hold_until: null
created_at: 2026-11-19T02:07:56.598Z
updated_at: 2026-11-20T19:16:01.000Z
started_at: 2026-11-19T02:08:25.656Z
closed_at: 2026-11-19T03:11:11.436Z
close_reason: "Landed in #598"
resolution: null
duplicate_of: null
extensions: {}
---
Seen on #586's CI, run 44440236584, in unit (3.12, 1/2): assert (6, 210) == (4, 180) at tests/test_e2e_filesystem_to_sse.py:216. The PR changed only apps/macos, docs and changelog.d. A rerun passed. Likely a timing-dependent count of filesystem events reaching SSE; it should assert a bound or settle before counting.
