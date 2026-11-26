---
type: is
id: is-01m8cn7zpggdgeevgab4b1rz02
title: "PR #888 A1: Discover the requested prefix in activity order"
kind: bug
status: closed
priority: 1
version: 3
delegate: codex@spud10.local
labels: []
dependencies: []
parent_id: is-01m8cn7g58hfbbdjx6x1ng7bbg
hold: null
hold_until: null
created_at: 2026-11-26T19:27:44.845Z
updated_at: 2026-11-26T20:08:25.518Z
started_at: 2026-11-26T19:27:47.554Z
closed_at: 2026-11-26T20:08:25.502Z
close_reason: "Fixed, independently reviewed, passed CI, and merged with PR #888."
resolution: null
duplicate_of: null
---
High. Older PRs can be absent from the top window when creation-order background work is held. src/metabrowser/builtin_plugins/github/pull_list_refresh.py:222. Review A https://github.com/jlevy/metabrowser/pull/888#pullrequestreview-6079402458
