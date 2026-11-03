---
type: is
id: is-01m6fggd3sfqa2c0dq5ff8b3ng
title: "PR #284 B1: entity tag omits the store, and 304 is answered before the store is consulted"
kind: bug
status: closed
priority: 1
version: 2
labels: []
dependencies: []
parent_id: is-01m6fgg7mr3vtzcxz7m1njv3ck
created_at: 2026-11-03T01:31:17.496Z
updated_at: 2026-11-03T02:31:06.423Z
closed_at: 2026-11-03T02:31:06.422Z
close_reason: "B1 fixed at faab2f01d9b60fb1da14b1e04ba42e0654478419 in 5609a0b6: the tag names the store and a 304 waits for the store to resolve the commits; test_another_store_on_the_same_origin_answers_for_itself."
resolution: null
duplicate_of: null
---
Medium. Review B https://github.com/jlevy/metabrowser/pull/284#pullrequestreview-5745588159. diff/sidekick.py:292-298. Fold a store identity into the tag and the address; a store holding neither commit answers 404 not 304.
