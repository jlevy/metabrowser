---
type: is
id: is-01m6fggh5kt7rb0ek2z10068xt
title: "PR #284 C6: a kept body is decompressed on the event loop for a client without gzip"
kind: bug
status: open
priority: 1
version: 1
labels: []
dependencies: []
parent_id: is-01m6fgg7mr3vtzcxz7m1njv3ck
created_at: 2026-11-03T01:31:21.650Z
updated_at: 2026-11-03T01:31:21.650Z
---
Low. Review C https://github.com/jlevy/metabrowser/pull/284#pullrequestreview-5745841338. diff/sidekick.py:232-244. Decompress off the loop.
