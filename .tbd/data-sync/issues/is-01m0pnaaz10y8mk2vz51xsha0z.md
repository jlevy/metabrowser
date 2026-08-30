---
type: is
id: is-01m0pnaaz10y8mk2vz51xsha0z
title: A UI probe clicked every disclosure, then measured the DOM it had just changed
kind: bug
status: closed
priority: 2
version: 2
labels: []
dependencies: []
parent_id: is-01m0pn7vkfkd7tfzt7r331jkp8
created_at: 2026-08-23T06:35:51.648Z
updated_at: 2026-08-30T09:08:47.068Z
---
WHAT HAPPENED. Checking the new rollup rule -- never show entries at or below 1% -- a probe expanded every disclosure in the page and then counted visible rows. It reported 36 rows at or below 1%, which reads as the rule not being applied at all.

WHY IT WAS WRONG. Expanding a disclosure is exactly the action that reveals the hidden tail. The probe created the state it then reported as a violation. On a clean load, without the probe's own clicks, the rule holds.

THE GENERAL SHAPE. A probe that interacts before it observes is measuring itself. This is the DOM version of the mutating-corpus bug filed as a sibling here, and the two happened within a day of each other, which suggests the pattern rather than the instance is the thing to guard.

THE FIX. Observe first, interact second, and where both are needed, reload between them. A probe should state in its own output which of the two it did -- 'measured on load' or 'measured after expanding' are different claims about different things, and the number alone does not distinguish them.

## Notes

CLOSED as documented rather than as code, because the fix is a rule about how to measure and the loop's README is where that rule is now enforced.

WHAT HAPPENED. A probe expanded every disclosure in the page and then counted visible rows, reporting 36 rows at or below 1% -- which reads as the rollup rule not being applied. Expanding a disclosure is exactly the action that reveals the hidden tail, so the probe created the state it then reported as a violation.

IT WAS NOT AN ISOLATED SLIP. The same session produced three more of the same family: an element-level `.click()` that never reached the handler and so reported expansion as broken; `offsetParent !== null` reporting a `visibility: hidden` group as visible; and a heredoc that expanded `$(git rev-parse ...)` at file-write time rather than inside the hook it was supposedly probing. Each produced a specific, confident, wrong finding.

WHAT IS NOW WRITTEN DOWN, in explorations/performance-loop/README.md: observe before interacting, say in the output which of the two a run did, and calibrate an instrument against a known-good case before trusting it on the case under test. The visibility precondition in that file is the same rule in its most consequential form -- a run that cannot say it was measured visible is void, and the probe now certifies that itself rather than leaving it to whoever reads the numbers.

No further code change is warranted. The failure was never in the app.
