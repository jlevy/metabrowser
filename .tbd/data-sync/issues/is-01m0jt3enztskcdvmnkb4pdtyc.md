---
type: is
id: is-01m0jt3enztskcdvmnkb4pdtyc
title: "R4: tree_filter._ROLLUP_CACHE has no test reset and relies on process-wide revisions"
kind: bug
status: closed
priority: 2
version: 3
assignee: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m0jt1hr4r6yqhgxkv0bpyayj
created_at: 2026-08-21T18:42:31.229Z
updated_at: 2026-08-21T19:03:44.728Z
closed_at: 2026-08-21T19:03:44.727Z
close_reason: Added reset_rollup_cache_for_tests, called from the server's existing reset_response_caches_for_tests so a test resets every response-shaped cache through one door, and stated the process-wide-revision dependency beside the cache. A test fails if the hook stops clearing it.
---
PR #60 review finding R4 (medium).

tree_filter._ROLLUP_CACHE is a module-level OrderedDict keyed on (generation, TreeFilter)
with no reset hook. Neither tests/conftest.py nor tests/test_tree_filter.py clears it.

On #60's base that is a live test-isolation bug. _rollup_generation was a per-instance
counter starting at 0, and reset_instance_for_tests() builds a fresh index, so two tests
sharing a TreeFilter could collide on (0, filter) and one would be served the other's
rollups.

main happens to fix it. #59 moved the counter to a process-wide itertools.count(1)
specifically so a fresh index never reuses a revision -- done for the /api/rollup ETag,
where the same collision would have served one root's body for another. It protects this
cache as a side effect.

That coupling is real and nothing states it. If someone later simplifies the counter back
to per-instance, this cache breaks silently, in tests first.

Either add a reset hook beside server.reset_response_caches_for_tests() and call it from
conftest, or put a comment on the cache saying its key's uniqueness depends on revisions
being process-wide. The hook is the safer of the two, since it does not depend on a future
reader finding the comment.
