---
type: is
id: is-01m6fggf9pwsfkh9mvr90wzjbs
title: "PR #284 C1: a file whose limited diff carries another file section can be deferred on every request"
kind: bug
status: closed
priority: 1
version: 2
labels: []
dependencies: []
parent_id: is-01m6fgg7mr3vtzcxz7m1njv3ck
created_at: 2026-11-03T01:31:19.733Z
updated_at: 2026-11-03T02:31:08.367Z
closed_at: 2026-11-03T02:31:08.366Z
close_reason: "C1 fixed at faab2f01d9b60fb1da14b1e04ba42e0654478419 in 5609a0b6 and 0aa8f047: only asked sections spend the bound, a pair asked alone uses --diff-filter=RC, deferred has client copy; adapter tests and the real-bound probe."
resolution: null
duplicate_of: null
---
High. Review C https://github.com/jlevy/metabrowser/pull/284#pullrequestreview-5745841338. diff/adapters/git.py:162-178,529-545; diff-view.js:1708-1712. Count only asked sections; never deferred for a single-file ask; client copy for deferred. Same as Qodo inline comment 4 https://github.com/jlevy/metabrowser/pull/284#discussion_r4449451268
