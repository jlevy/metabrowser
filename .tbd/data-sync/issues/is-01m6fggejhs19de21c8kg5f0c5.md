---
type: is
id: is-01m6fggejhs19de21c8kg5f0c5
title: "PR #284 B5: hostile names reach an error body whole, warnings carry names of any length"
kind: bug
status: closed
priority: 1
version: 2
labels: []
dependencies: []
parent_id: is-01m6fgg7mr3vtzcxz7m1njv3ck
created_at: 2026-11-03T01:31:18.992Z
updated_at: 2026-11-03T02:31:07.727Z
closed_at: 2026-11-03T02:31:07.726Z
close_reason: "B5 fixed at faab2f01d9b60fb1da14b1e04ba42e0654478419 in 5609a0b6: fixed error bodies, paths in warnings cut at 200 chars."
resolution: null
duplicate_of: null
---
Low. Review B https://github.com/jlevy/metabrowser/pull/284#pullrequestreview-5745588159. diff/sidekick.py:361-362,427-431; patch_file.py:541-545. Fixed message for GitError bodies; cap named paths.
