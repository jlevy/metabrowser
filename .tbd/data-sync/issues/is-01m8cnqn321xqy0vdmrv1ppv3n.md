---
type: is
id: is-01m8cnqn321xqy0vdmrv1ppv3n
title: "PR #888 D1: Keep shared stack representatives stable while the list refreshes"
kind: bug
status: closed
priority: 2
version: 3
delegate: codex@spud10.local
labels: []
dependencies: []
parent_id: is-01m8cn7g58hfbbdjx6x1ng7bbg
hold: null
hold_until: null
created_at: 2026-11-26T19:36:18.271Z
updated_at: 2026-11-26T20:08:44.323Z
started_at: 2026-11-26T19:36:19.523Z
closed_at: 2026-11-26T20:08:44.312Z
close_reason: "Fixed, independently reviewed, passed CI, and merged with PR #888."
resolution: null
duplicate_of: null
---
Medium. A newer shared PR in the Open list can move both stacks before their snapshot refreshes, causing both representatives to land in one group. src/metabrowser/builtin_plugins/github/pulls-panel.js:1002 and pull-stacks.js:335. Review D https://github.com/jlevy/metabrowser/pull/888#pullrequestreview-6079605561
