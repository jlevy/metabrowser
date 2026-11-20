---
type: is
id: is-01m7wy6m46z0709x2rn5jfgzs9
title: "PR #656 A2: byte cap does not bound parse-cache memory or request time"
kind: bug
status: closed
priority: 1
version: 3
delegate: claude-code@vm
labels: []
dependencies: []
parent_id: is-01m7wy6kbgkfyg4kf94bk8z11e
hold: null
hold_until: null
created_at: 2026-11-20T16:56:26.501Z
updated_at: 2026-11-20T18:12:02.334Z
started_at: 2026-11-20T17:22:57.007Z
closed_at: 2026-11-20T18:12:02.334Z
close_reason: fixed in 7868d4844,33fa82e99,c006c753d; CI green at ee5f72c6b; dispositions https://github.com/jlevy/metabrowser/pull/656#issuecomment-7047094985
resolution: null
duplicate_of: null
---
Severity High. PR #656 review A (https://github.com/jlevy/metabrowser/pull/656#pullrequestreview-5996326781). delimited/source.py DELIMITED_* bounds, held_bytes, sort_index; table_source.py deadline comment; bench.
