---
type: is
id: is-01m82c8abm03xzpvctgea74ywj
title: "Nightly soak 2026-11-21 (run 44905073328): nav-reveal Chrome address step finds no row for /view/docs/deep/deeper/leaf.md on main 98c2dffd4"
kind: bug
status: closed
priority: 1
version: 5
refs:
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/699
    at: 2026-11-22T21:09:45.160Z
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m7hgpc9550w78kmwqsvv64xh
hold: null
hold_until: null
created_at: 2026-11-22T19:38:14.258Z
updated_at: 2026-11-22T21:09:45.163Z
started_at: 2026-11-22T19:55:39.318Z
closed_at: 2026-11-22T20:55:16.664Z
close_reason: "Fixed by #699 (merged 3b2cfe142): serve mode now holds its listening socket from the port search through Uvicorn's start, so two servers started together can no longer both print one port. The failing run's logs showed both servers on 50071 and the checkout server losing the bind. Reproduced on main 10/10; 0/10 after the fix. Evidence is in the bead notes."
resolution: null
duplicate_of: null
---
Nightly soak chrome (4, 4/4): tests/dom/nav-reveal-chrome.mjs:141 'failed the address: the row is selected / in view', row null, selectedFiles []. Same test family as closed mb-551m, so that fix did not hold or a second mechanism exists. Check mb-a124 (fixture accepting a different server on the same port) as a candidate cause. Find the mechanism before the 0.13.0 candidate.

## Notes

2026-11-22: PR #699 (branch claude/soak-nav-reveal, not merged). Mechanism: not a reveal race; same event as mb-a124. The run's logs show the checkout and history servers both printed port 50071; the checkout server then failed to bind (Errno 98) and exited, and the history server answered the checkout's address, so the Files tree had no row for docs/deep/deeper/leaf.md. Cause is in serve mode: the port search only probed (bind, close), and Uvicorn bound after attach and lifespan startup, so two servers started together both took one port. Fix: listen_on_available_local_port returns a listening socket that Uvicorn serves on, holding the port from search to exit. Evidence on a loaded 10-core Mac: two real servers on one --port collided 10 of 10 on main, 0 of 10 fixed; nav-reveal with both servers asked for one port failed 3 of 3 on main (2 with the soak's exact lines) and passed 3 of 3 fixed; new tests/test_serve_holds_port.py fails 3 of 3 on main. Unknown: whether the two _free_port() calls returned one number or the searches met at 50071 (the log lacks --port). Not closed: awaiting review and merge.
