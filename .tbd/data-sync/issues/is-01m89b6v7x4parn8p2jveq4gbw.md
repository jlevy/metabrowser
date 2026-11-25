---
type: is
id: is-01m89b6v7x4parn8p2jveq4gbw
title: "Pulls row lines Chrome check: a second line read for rows drawn after the first batch (420 px dark)"
kind: bug
status: closed
priority: 2
version: 5
delegate: claude-code@spud10.local
labels: []
dependencies: []
hold: null
hold_until: null
created_at: 2026-11-25T12:34:38.460Z
updated_at: 2026-11-25T14:44:32.339Z
started_at: 2026-11-25T14:17:01.553Z
closed_at: 2026-11-25T14:44:32.338Z
close_reason: "Fixed in #840 (merge 4e5893d33): the lane settles the Pulls window before its read names the rows drawn; mechanism in the notes."
resolution: null
duplicate_of: null
---
CI run 45614060332, job chrome (3.13, 3/4), on #838 head 92138db64 (a merge of main a032645d9 with no change to pulls-panel.js, row-lines.js, or the check): tests/dom/github-pulls-row-lines-chrome.mjs:830 failed at '420 px dark: one read names every row drawn' with window.__asked = [[106..60],[59,58,57]]: rows 59, 58 and 57 were read in a second batch. The same check passed on #834's run at fc78dc2b3 and on main's run 45611637433 for a032645d9. Candidate mechanism, not yet confirmed: the dark pass at 420 px follows the light pass at 180 px, so the panel's first drawn window may be sized from rows measured at the narrower width, and rows that fit once the shorter rows are measured are drawn in a later frame, after the batched read has been sent. Confirm by logging the drawn window per frame in that pass, or by reproducing with the light-180-then-dark-420 order.

## Notes

2026-11-25: did not recur on #838's next head ed4b9c780: CI run 45617633028 passed all four chrome shards, chrome (3.13, 3/4) included. One pass does not settle the mechanism above; it is still unconfirmed.

2026-11-25: failed again on main's push run 45630767314 at 1d6bae30d (chrome (3.13, 3/4)) at 340 px light ([[106..60],[59,58]]) and 299 px light ([[106..60],[59]]). Reproduced locally 3 of 3 runs at a load average near 72 (380/299 light, 340/299 light, 420 dark).

Mechanism, confirmed with a per-frame log of the page (requestAnimationFrame, ResizeObserver deliveries, requestIdleCallback asks and runs, every paint of the window with its caller, and each summary read, with the count of rows drawn at each): the candidate above (dark 420 sized from rows measured at 180 px) is not it; every mount starts a fresh row window. Each mount draws its first window with every row placed at ROW_ESTIMATE_PX (80.5 px): at(bottom) + PULL_ROWS_OVERSCAN, 47 rows, #106 to #60. That paint calls rowLines.want(47 rows), which asks requestIdleCallback for the read. The same frame lays the rows out and rowSizes (ResizeObserver) measures them: at 420 to 299 px most runs are two lines, rows shorter than the estimate, so more rows are in view and the window grows to 48 to 50 rows (at 260 to 180 px it shrinks to 44 to 46); the measure queues the window's next paint for the next animation frame (queueWindow). Chrome had 5 to 13 ms of idle time left after that frame, so the idle callback ran before the next frame: run() took wanted() as the 47 estimated rows and sent the read. The next frame drew the grown window and called want() again, but next() does nothing while a read runs, so the added rows (#59, #58, #57) were read in a second request once the first answered. Whether it splits is a race between the idle callback and the next window paint (the rAF, or a controller render that repaints synchronously when the stacks or anchor settle), so it passed on some runs. Logged example, 340 px light: idle-ask 4 ms (47 drawn), rAF 16, RO 17 (47 rows measured), idle-run 19 (47 drawn), read 19 (47 numbers), rAF 37 (47 -> 49 drawn), read 154 (2 numbers).

Fix (claude/fix-row-lines-one-read): the lane calls deps.settle() in its idle callback before it names the rows; the panel's settleWindow() measures the rows drawn as rowSizes would (getBoundingClientRect), and if a measure moved the window or a window frame is waiting, cancels that frame and draws the window at once, which calls want() with the settled rows. The rows in view are all among the first window's 47, so one pass places the window. With it, 4 of 4 Chrome runs and 2 instrumented runs passed; the log shows settleWindow growing 47 -> 50 (420 dark, 380 light) and 47 -> 48 (299 light) inside the idle callback, then one read of the full window.

Test: tests/dom/github-pulls-row-lines-session.js `window` mounts the production panel in a 600 px pane whose rows lay out 61 px, with frames, resize notifications and idle time in the session's hands, and holds that one read names every row the window draws when the browser is idle after the frame that measured the rows and before it laid them out; without the lane's settle call both give [#106..#59 (48), #58..#57 (2)], and without the forced measure the before-layout case does. The lane story adds a step whose settle draws #102 too.
