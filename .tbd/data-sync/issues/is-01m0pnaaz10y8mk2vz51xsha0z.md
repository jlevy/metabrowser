---
type: is
id: is-01m0pnaaz10y8mk2vz51xsha0z
title: A UI probe clicked every disclosure, then measured the DOM it had just changed
kind: bug
status: open
priority: 2
version: 1
labels: []
dependencies: []
parent_id: is-01m0pn7vkfkd7tfzt7r331jkp8
created_at: 2026-08-23T06:35:51.648Z
updated_at: 2026-08-23T06:35:51.648Z
---
WHAT HAPPENED. Checking the new rollup rule -- never show entries at or below 1% -- a probe expanded every disclosure in the page and then counted visible rows. It reported 36 rows at or below 1%, which reads as the rule not being applied at all.

WHY IT WAS WRONG. Expanding a disclosure is exactly the action that reveals the hidden tail. The probe created the state it then reported as a violation. On a clean load, without the probe's own clicks, the rule holds.

THE GENERAL SHAPE. A probe that interacts before it observes is measuring itself. This is the DOM version of the mutating-corpus bug filed as a sibling here, and the two happened within a day of each other, which suggests the pattern rather than the instance is the thing to guard.

THE FIX. Observe first, interact second, and where both are needed, reload between them. A probe should state in its own output which of the two it did -- 'measured on load' or 'measured after expanding' are different claims about different things, and the number alone does not distinguish them.
