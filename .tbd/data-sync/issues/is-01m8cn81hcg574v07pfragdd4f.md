---
type: is
id: is-01m8cn81hcg574v07pfragdd4f
title: "PR #888 C1: Bound the foreground catalog member lookup"
kind: bug
status: in_progress
priority: 2
version: 2
delegate: codex@spud10.local
labels: []
dependencies: []
parent_id: is-01m8cn7g58hfbbdjx6x1ng7bbg
hold: null
hold_until: null
created_at: 2026-11-26T19:27:46.731Z
updated_at: 2026-11-26T19:27:48.640Z
started_at: 2026-11-26T19:27:48.639Z
---
Medium. The updated-state index can scan the entire state on a lookup by explicit PR number. src/metabrowser/builtin_plugins/github/pull_catalog.py:889. Review C https://github.com/jlevy/metabrowser/pull/888#pullrequestreview-6079487103
