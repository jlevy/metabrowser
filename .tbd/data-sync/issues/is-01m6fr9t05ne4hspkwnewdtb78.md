---
type: is
id: is-01m6fr9t05ne4hspkwnewdtb78
title: "PR #284 D1: on the admitted floor a store's answer depends on HEAD's .gitattributes, which nothing names"
kind: bug
status: closed
priority: 0
version: 3
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m6fr829v5p0bx9wm4rr3z5wj
hold: null
hold_until: null
created_at: 2026-11-03T03:47:29.924Z
updated_at: 2026-11-03T03:53:08.640Z
started_at: 2026-11-03T03:48:07.889Z
closed_at: 2026-11-03T03:53:08.639Z
close_reason: |
  fixed in e610ebab on #284: every store read names the store's empty tree in GIT_ATTR_SOURCE, computed per object format; test_a_stores_default_branch_attributes_change_nothing fails before and passes after on a local build of the 2.43.7 floor; 154 store answers byte-identical on 2.50.1 with and without the variable, and between 2.43.7 and 2.50.1 with it.
resolution: null
duplicate_of: null
---
Blocker. src/metabrowser/builtin_plugins/diff/comparison_cache.py:24-30 and sidekick.py _kept_key rested on a bare store reading no commit's attributes; Git 2.43 reads HEAD's (attr.c compute_default_attr_source), so admitted-git (2.43.7) failed tests/test_diff_comparison_cache.py::test_a_stores_default_branch_attributes_change_nothing and a refetch served a stale comparison from memory, the ETag and the browser. Review D: https://github.com/jlevy/metabrowser/pull/284#pullrequestreview-5746804338. Fix: GIT_ATTR_SOURCE=<empty tree of the store's object format> on every store read (STORE_READ_POLICY, BATCH_OBJECT_POLICY).
