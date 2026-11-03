---
type: is
id: is-01m6fggbnj9awvhmrj529hx95s
title: "PR #284 A11: MAX_CACHED_MANIFESTS is a count the docs table calls memory"
kind: bug
status: closed
priority: 1
version: 2
labels: []
dependencies: []
parent_id: is-01m6fgg7mr3vtzcxz7m1njv3ck
created_at: 2026-11-03T01:31:16.018Z
updated_at: 2026-11-03T02:31:05.149Z
closed_at: 2026-11-03T02:31:05.148Z
close_reason: "A11 fixed at faab2f01d9b60fb1da14b1e04ba42e0654478419 in eae61c7d: the limits table says 16 comparisons, up to 131 MB."
resolution: null
duplicate_of: null
---
Low. Review A https://github.com/jlevy/metabrowser/pull/284#pullrequestreview-5745572379. comparison_cache.py:47-52; docs/large-content-rendering.md table.
