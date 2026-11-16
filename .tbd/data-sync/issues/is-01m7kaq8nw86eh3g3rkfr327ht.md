---
type: is
id: is-01m7kaq8nw86eh3g3rkfr327ht
title: "Chrome sessions can outlive their result: tests/dom/chrome-session.mjs close() waits 5 s after SIGTERM, but the piped stderr and exit listener keep Node alive until Chrome exits, so a slow exit overruns a test's run budget"
kind: bug
status: open
priority: 2
version: 1
labels: []
dependencies: []
parent_id: is-01m7hgpc9550w78kmwqsvv64xh
created_at: 2026-11-16T23:22:50.427Z
updated_at: 2026-11-16T23:22:50.427Z
---
Seen by the mb-nvo0 fix (#488): in 3 of 30 prose-faces runs Chrome exited 1.2 to 7.5 s after '96 checks passed' and the test hit its 30 s budget. Shared helper used by 23 test files. Candidate fixes: SIGKILL after the bound, or chrome.stderr.destroy() plus chrome.unref(). Prove with a loaded-machine loop.
