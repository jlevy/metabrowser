---
type: is
id: is-01m7rrz0nqayqnha5hj3j2q238
title: "Flaky: test_e2e_filesystem_to_sse.py:216 counts more events than expected under load"
kind: bug
status: closed
priority: 2
version: 7
refs:
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/598
    at: 2026-11-20T17:03:56.768Z
delegate: claude-code@spud10
labels:
  - linear
dependencies: []
parent_id: is-01m2gb3gpn7vcsw0as4xa243tg
hold: null
hold_until: null
created_at: 2026-11-19T02:07:56.598Z
updated_at: 2026-11-20T19:12:50.604Z
started_at: 2026-11-19T02:08:25.656Z
closed_at: 2026-11-19T03:11:11.436Z
close_reason: "Landed in #598"
resolution: null
duplicate_of: null
extensions:
  linear:
    id: de6d048f-35b3-45a6-ad2d-4bd79b837609
    linked_at: 2026-11-20T18:01:24.094Z
---
Seen on #586's CI, run 44440236584, in unit (3.12, 1/2): assert (6, 210) == (4, 180) at tests/test_e2e_filesystem_to_sse.py:216. The PR changed only apps/macos, docs and changelog.d. A rerun passed. Likely a timing-dependent count of filesystem events reaching SSE; it should assert a bound or settle before counting.
