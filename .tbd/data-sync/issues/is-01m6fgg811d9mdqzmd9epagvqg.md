---
type: is
id: is-01m6fgg811d9mdqzmd9epagvqg
title: "PR #284 A1: catalog-feed journals stream changes without bound while held"
kind: bug
status: closed
priority: 1
version: 2
labels: []
dependencies: []
parent_id: is-01m6fgg7mr3vtzcxz7m1njv3ck
created_at: 2026-11-03T01:31:12.288Z
updated_at: 2026-11-03T02:31:01.908Z
closed_at: 2026-11-03T02:31:01.907Z
close_reason: "A1 fixed at faab2f01d9b60fb1da14b1e04ba42e0654478419 in 0aa8f047: the catalog feed journals nothing while held; tests/dom/catalog-feed-behavior.js."
resolution: null
duplicate_of: null
---
Medium. Review A https://github.com/jlevy/metabrowser/pull/284#pullrequestreview-5745572379. static/catalog-feed.js:409-418,437-448,453-464. Drop or bound changes while held; add held-with-changes case to the session.
