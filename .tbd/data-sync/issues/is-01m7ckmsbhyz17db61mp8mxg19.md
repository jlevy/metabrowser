---
type: is
id: is-01m7ckmsbhyz17db61mp8mxg19
title: Shift strip misses N/P when stack membership arrives while Shift is held
kind: bug
status: open
priority: 4
version: 1
labels: []
dependencies: []
created_at: 2026-11-14T08:44:05.360Z
updated_at: 2026-11-14T08:44:05.360Z
---
Found reviewing #423 (mb-6pup), pre-existing on main, inferred from code. pull-page.js's watchStacks callback paints the stack menu but publishes no registry event, and the menu attaches no shortcut targets, so a membership answer that arrives while Shift is held (with no first-paint hold) leaves N and P out of the strip until the next registry event. Fix: refresh the reveal (refreshBadges through the plugin facade, or equivalent) from the callback when membership changes; test in tests/dom/github-pull-first-paint-behavior.js or the stack mount session.
