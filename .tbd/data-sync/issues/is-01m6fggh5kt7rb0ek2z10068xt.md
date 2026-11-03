---
type: is
id: is-01m6fggh5kt7rb0ek2z10068xt
title: "PR #284 C6: a kept body is decompressed on the event loop for a client without gzip"
kind: bug
status: closed
priority: 1
version: 2
labels: []
dependencies: []
parent_id: is-01m6fgg7mr3vtzcxz7m1njv3ck
created_at: 2026-11-03T01:31:21.650Z
updated_at: 2026-11-03T02:31:09.960Z
closed_at: 2026-11-03T02:31:09.959Z
close_reason: "C6 fixed at faab2f01d9b60fb1da14b1e04ba42e0654478419 in 5609a0b6: gzip.decompress in a thread; golden block."
resolution: null
duplicate_of: null
---
Low. Review C https://github.com/jlevy/metabrowser/pull/284#pullrequestreview-5745841338. diff/sidekick.py:232-244. Decompress off the loop.
