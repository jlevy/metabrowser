---
type: is
id: is-01m7w1w8da04pw131z5jaxdqdr
title: test_refs_that_differ_only_in_case_are_refused_where_the_store_cannot_hold_them fails under Git 2.56.1
kind: bug
status: open
priority: 2
version: 2
labels: []
dependencies: []
parent_id: is-01m2gb3gpn7vcsw0as4xa243tg
created_at: 2026-11-20T08:41:26.697Z
updated_at: 2026-11-20T17:20:58.717Z
---
Reported by two agents on 2026-11-20 after Homebrew Git was upgraded to 2.56.1: tests/test_cache_resolve.py::test_refs_that_differ_only_in_case_are_refused_where_the_store_cannot_hold_them fails locally on origin/main under Git 2.56.1 (passes in CI and under 2.50.1). Determine whether Git 2.56 changed case-colliding ref handling (e.g. reftable or refs backend changes) so Metabrowser's refusal no longer triggers, which would be a real behavior change for users on new Git, or whether only the test's expectation is stale. Add 2.56.1 coverage.
