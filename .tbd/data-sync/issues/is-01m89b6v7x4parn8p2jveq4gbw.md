---
type: is
id: is-01m89b6v7x4parn8p2jveq4gbw
title: "Pulls row lines Chrome check: a second line read for rows drawn after the first batch (420 px dark)"
kind: bug
status: open
priority: 2
version: 2
labels: []
dependencies: []
created_at: 2026-11-25T12:34:38.460Z
updated_at: 2026-11-25T13:15:19.423Z
---
CI run 45614060332, job chrome (3.13, 3/4), on #838 head 92138db64 (a merge of main a032645d9 with no change to pulls-panel.js, row-lines.js, or the check): tests/dom/github-pulls-row-lines-chrome.mjs:830 failed at '420 px dark: one read names every row drawn' with window.__asked = [[106..60],[59,58,57]]: rows 59, 58 and 57 were read in a second batch. The same check passed on #834's run at fc78dc2b3 and on main's run 45611637433 for a032645d9. Candidate mechanism, not yet confirmed: the dark pass at 420 px follows the light pass at 180 px, so the panel's first drawn window may be sized from rows measured at the narrower width, and rows that fit once the shorter rows are measured are drawn in a later frame, after the batched read has been sent. Confirm by logging the drawn window per frame in that pass, or by reproducing with the light-180-then-dark-420 order.

## Notes

2026-11-25: did not recur on #838's next head ed4b9c780: CI run 45617633028 passed all four chrome shards, chrome (3.13, 3/4) included. One pass does not settle the mechanism above; it is still unconfirmed.
