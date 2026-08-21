---
type: is
id: is-01m0hfpftgcj7dx4sedsd5vgm4
title: Two rollup tests pass with their mechanism removed
kind: task
status: closed
priority: 3
version: 4
labels: []
dependencies: []
parent_id: is-01m0gfpa3nt74hvrnqbyqhn0ya
created_at: 2026-08-21T06:21:26.223Z
updated_at: 2026-08-21T18:31:17.006Z
closed_at: 2026-08-21T06:53:27.938Z
close_reason: null
---
PR #59 states that every new test was verified to fail when its mechanism is removed.
Two do not, found by mutating the mechanism and re-running.

1. test_rollup_validator_identifies_the_served_root. Removing the served root from the
   ETag leaves all 11 tests in tests/test_rollup_route.py passing. The test's final
   assertion, first_tag != second_tag, is satisfied by a different mechanism: rollup
   revisions come from a process-wide itertools.count, so two roots in one process can
   never collide on a revision even with the root absent from the tag. The root
   component is real defense in depth for the module-level body cache, which outlives a
   root switch, but this test does not exercise it. To bind it, the tags have to be
   compared at a revision the two roots share.

2. test_rollup_revalidates_and_reuses_an_unchanged_body. Forcing the retained-body
   lookup to miss (cached = None) leaves the file green. The test asserts the cache is
   populated and that the two bodies are byte-equal, but a rebuild produces identical
   bytes, so equality holds either way and reuse is never observed. To bind it, assert
   the reuse path was taken -- no aggregation ran for the second request.

The second is a pure optimization with no correctness consequence; the first is
defense in depth. Neither is a bug. They matter because the PR's stated test standard is
what makes the rest of the suite trustworthy, and these two do not meet it.

For contrast, mutation-testing confirmed these do bind their mechanisms: strict
level-order BFS, ancestor-chain aggregate eviction, the asyncio.shield around a shared
build, and single-flight coalescing. The one mechanism with no test at all is tracked
separately in mb-xksv.
