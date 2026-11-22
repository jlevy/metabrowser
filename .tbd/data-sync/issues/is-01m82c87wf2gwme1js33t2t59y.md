---
type: is
id: is-01m82c87wf2gwme1js33t2t59y
title: "Nightly soak 2026-11-19 (run 44526255047): tests/test_nav_collapse_chrome.py:96 fails at 'phase load' on main 169496f05"
kind: bug
status: in_progress
priority: 1
version: 3
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m7hgpc9550w78kmwqsvv64xh
hold: null
hold_until: null
created_at: 2026-11-22T19:38:11.711Z
updated_at: 2026-11-22T20:11:25.309Z
started_at: 2026-11-22T19:55:37.966Z
---
Nightly soak chrome (4, 4/4) on main 169496f05: AssertionError 'phase load 269', assert 1 == 0 at tests/test_nav_collapse_chrome.py:96. Intermittent across five soak repetitions; find the mechanism before the 0.13.0 candidate (no rerun-it-away). Prior related: mb-hujg.

## Notes

Investigated 2026-11-22: this is the mb-hujg failure, not a new one. No code change and no PR. Evidence: (1) the soak ran on main 169496f05 at 2026-11-19T12:41Z, the same commit mb-hujg names, about 4.5 h before its fix (PR #610, commit 4d15b3f8d, merged 17:18Z); 169496f05 is an ancestor of 4d15b3f8d. (2) The soak log line is the mb-hujg signature exactly: "failed at load: the chevron and Up are each a 24 px target, neither over the other, and a press anywhere in either lands on it" with up left 328 right 352 top 4.5 and owns {button:true, up:false}; "phase load 269" is only the first stderr line (the phase timestamp), and every later phase ran. Mechanism (from mb-hujg): at 169496f05 the load phase waited for shellToolsReady and the shortcut hints only, so READ could measure the Up of the folder view still staged in .preview-file-stage (inert, pointer-events none) while a press there hit the loading placeholder. #610 makes load wait for no stage and a committed Up, and READ skip a staged Up; the commit is one preview.replaceChildren() in app.js renderFile, so there is no window after it where Up is present but covered. (3) Since the fix: nightly soaks 44737855133, 44905073328, 45023473576 each ran test_nav_collapse_chrome.py 5 times, 15 of 15 passed (their failures are other tests / time-limits). Locally on origin/main 2d52d2824, 12 of 12 sequential runs passed with load average ~270 from other agents. mb-a124 (two fixture servers on one port) is not involved: the server log shows the right folder served and the page loaded. Left open for the owner to close.
