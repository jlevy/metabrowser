---
type: is
id: is-01m894fr99c3e4r4sawnch2eg0
title: "PR #829 B1: the stack route reads fetching after the members' records"
kind: bug
status: closed
priority: 2
version: 3
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m894fq5p2chk8wm0qd0vp1yy
hold: null
hold_until: null
created_at: 2026-11-25T10:37:10.312Z
updated_at: 2026-11-25T10:58:41.348Z
started_at: 2026-11-25T10:37:15.812Z
closed_at: 2026-11-25T10:58:41.347Z
close_reason: "Fixed in 3af9f4f (PR #829): read_stack takes each member's running state on the loop before reading records; the page confirms an ended reader's fetch with one more read. Route test and session ended_race case. Disposition: https://github.com/jlevy/metabrowser/pull/829#issuecomment-7160421193"
resolution: null
duplicate_of: null
---
Medium. PR #829, review B: https://github.com/jlevy/metabrowser/pull/829#pullrequestreview-6055810869. read_stack reads the members' records in a thread (pull_stack.py:416, _read_members); _envelope asks running() only afterwards on the loop (:679, after combined and the retain write :719-735). A member whose job writes its record and ends between the two is answered pending with fetching false, so asksAfterRead (stack-page.js:201-208) names a reader's ask failed and the page waits up to SLOW_POLL_MS. Fix: take each member's running state on the loop before its record is read (the rule at pull_route.py:387-388); optionally a confirming read on the page.
