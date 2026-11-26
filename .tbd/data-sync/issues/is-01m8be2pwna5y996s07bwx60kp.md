---
type: is
id: is-01m8be2pwna5y996s07bwx60kp
title: "test_closing_on_a_later_loops_child: a killed child of a closed loop stays a zombie under Python 3.13's pidfd watcher"
kind: bug
status: closed
priority: 2
version: 4
delegate: claude-code@vm
labels: []
dependencies: []
hold: null
hold_until: null
created_at: 2026-11-26T08:03:17.524Z
updated_at: 2026-11-26T21:33:21.464Z
started_at: 2026-11-26T19:07:56.873Z
closed_at: 2026-11-26T21:33:21.464Z
close_reason: Implemented in https://github.com/jlevy/metabrowser/pull/891 (CI green at d9463651; senior review G1-G4 fixed).
resolution: null
duplicate_of: null
---
Found while triaging make verify in a cloud container (Linux, Python 3.13.18, can_use_pidfd() True): tests/test_markdown_child_sharing.py::test_closing_on_a_later_loop_does_not_wait_for_an_earlier_loops_child[stopped|running] fail every time; the child shows as Z <defunct> and os.kill(pid, 0) counts a zombie as alive. asyncio reaps through a pidfd watcher tied to one loop, so once the first loop closes nothing reaps its child. Forcing ThreadedChildWatcher made both pass. Also fails on origin/main cb3bf843; main CI was green, so it is timing- or platform-dependent. Decide: reap from a thread, or treat a zombie as gone.

## Notes

PR: https://github.com/jlevy/metabrowser/pull/891
