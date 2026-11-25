---
type: is
id: is-01m84x33c0caf03wmz9eyam3ab
title: test_cache_resolve case-collision test gets FetchFailedError, not RefCaseCollisionError, on macOS's case-insensitive filesystem
kind: bug
status: open
priority: 2
version: 2
labels: []
dependencies: []
parent_id: is-01m2gb3gpn7vcsw0as4xa243tg
created_at: 2026-11-23T19:10:57.919Z
updated_at: 2026-11-25T02:33:35.519Z
---
tests/test_cache_resolve.py::test_refs_that_differ_only_in_case_are_refused_where_the_store_cannot_hold_them fails in isolation on origin/main 1b809775f and on #762's head, on a local macOS checkout (case-insensitive APFS, git 2.56.1). git fetch exits 1 and raises FetchFailedError, where the test expects RefCaseCollisionError, so the collision is detected only after git has already refused the fetch. CI (Linux, case-sensitive) passes. mb-j2cp's notes mention the same ordering. Find git's stderr, then detect the collision before fetching, or classify that fetch failure as the collision. Evidence: .claude/worktrees/fix-mirror-pm/attic/full-python-762a.txt
