---
type: is
id: is-01m6fgge6pzjee7ynxxb2v2jhn
title: "PR #284 B4: a tree entry Git pathspec normalization refuses fails every file of the page"
kind: bug
status: open
priority: 1
version: 1
labels: []
dependencies: []
parent_id: is-01m6fgg7mr3vtzcxz7m1njv3ck
created_at: 2026-11-03T01:31:18.614Z
updated_at: 2026-11-03T01:31:18.614Z
---
Low. Review B https://github.com/jlevy/metabrowser/pull/284#pullrequestreview-5745588159. diff/adapters/git.py:521-528. Fall back to an unrestricted run on GitCommandError from a path-limited run.
