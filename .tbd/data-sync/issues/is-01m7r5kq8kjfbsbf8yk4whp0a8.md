---
type: is
id: is-01m7r5kq8kjfbsbf8yk4whp0a8
title: "Flake: test_recent_targets concurrent writers hit the 2 s lock wait on loaded CI"
kind: bug
status: closed
priority: 3
version: 7
refs:
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/569
    at: 2026-11-20T17:05:49.417Z
delegate: claude-code@spud10
labels:
  - linear
dependencies: []
hold: null
hold_until: null
created_at: 2026-11-18T20:29:43.551Z
updated_at: 2026-11-20T18:01:01.939Z
started_at: 2026-11-18T21:02:22.944Z
closed_at: 2026-11-18T22:17:17.266Z
close_reason: null
resolution: null
duplicate_of: null
extensions:
  linear:
    id: aabaaa19-99fc-4212-9a56-c5163cdd9ad7
    linked_at: 2026-11-20T18:01:01.935Z
---
Main CI run 44386715486 at a1100bca6: unit (3.14t, 2/2) failed tests/test_recent_targets.py:803 (writers * each <= MAX_RECENT_TARGETS case) with RecentTargetsError 'another Metabrowser process has held the recent targets list for 2 seconds' (BlockingIOError EAGAIN). The test's concurrent writers can exceed the lock wait on a loaded free-threaded runner.

## Notes

Fixed in PR #569 (merged as 87e35ed51, head 6f6d39c7c, CI green). Cause: test design. The test's 8 writers each take the lock 5 times running; the writer that just released it re-takes it before a polling waiter's next try (27-32 of 39 handoffs per burst at load ~300 on macOS), so the last-served writer waits behind nearly all other records. Real servers record once each. Product LOCK_WAIT_S kept: 40 one-shot processes at load ~300 waited at most 1.3 s over 10 bursts (recorded beside the constant). Fix: the test's writers wait up to 30 s (inside its 50 s child wait); the 2 s bound keeps its own deterministic test. Mutation check: lock disabled -> 3/3 fail. Loops: fixed test 30/30 at load 68-126; main's version also 30/30 locally (macOS fsync is fast; not reproducible here).
