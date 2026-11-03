---
type: is
id: is-01m6fgge6pzjee7ynxxb2v2jhn
title: "PR #284 B4: a tree entry Git pathspec normalization refuses fails every file of the page"
kind: bug
status: closed
priority: 1
version: 2
labels: []
dependencies: []
parent_id: is-01m6fgg7mr3vtzcxz7m1njv3ck
created_at: 2026-11-03T01:31:18.614Z
updated_at: 2026-11-03T02:31:07.398Z
closed_at: 2026-11-03T02:31:07.397Z
close_reason: "B4 fixed at faab2f01d9b60fb1da14b1e04ba42e0654478419 in 5609a0b6: a refused pathspec falls back to the unrestricted run; mktree test with .. and .git."
resolution: null
duplicate_of: null
---
Low. Review B https://github.com/jlevy/metabrowser/pull/284#pullrequestreview-5745588159. diff/adapters/git.py:521-528. Fall back to an unrestricted run on GitCommandError from a path-limited run.
