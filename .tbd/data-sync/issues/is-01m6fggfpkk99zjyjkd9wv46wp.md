---
type: is
id: is-01m6fggfpkk99zjyjkd9wv46wp
title: "PR #284 C2: the immutable address names no subject, so a folder replays a store answer"
kind: bug
status: closed
priority: 1
version: 2
labels: []
dependencies: []
parent_id: is-01m6fgg7mr3vtzcxz7m1njv3ck
created_at: 2026-11-03T01:31:20.146Z
updated_at: 2026-11-03T02:31:08.684Z
closed_at: 2026-11-03T02:31:08.683Z
close_reason: "C2 fixed at faab2f01d9b60fb1da14b1e04ba42e0654478419 in 5609a0b6 and 0aa8f047: STORE_TAG in the address, immutable requires it; reproduced and proven in visible Chrome (c2-before/after.json); golden and shell tests."
resolution: null
duplicate_of: null
---
High. Review C https://github.com/jlevy/metabrowser/pull/284#pullrequestreview-5745841338. diff/index.js:36-52, pull-page.js:1856-1867, sidekick.py:291-301. Server-provided store token in the address; immutable only when it matches.
