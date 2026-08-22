---
type: is
id: is-01m0nvhbznwzats0ctjmw57vq0
title: "PR #66 review F5: empty pass branch used as control flow"
kind: bug
status: closed
priority: 3
version: 3
labels: []
dependencies: []
parent_id: is-01m0nvgqxqbb35etfxh3xbbkh9
created_at: 2026-08-22T23:05:19.092Z
updated_at: 2026-08-22T23:16:35.807Z
closed_at: 2026-08-22T23:16:35.806Z
close_reason: "Fixed: inverted to a positive guard; the empty pass arm is gone."
---
server.py:1513-1514. 'if navigation_tallies is None and not wants_tallies: pass' followed by two elifs reads as an unfinished edit. Invert to a positive guard wrapping the two real branches.
