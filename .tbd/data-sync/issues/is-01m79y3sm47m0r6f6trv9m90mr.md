---
type: is
id: is-01m79y3sm47m0r6f6trv9m90mr
title: Remove the 'Rendered diff unavailable. Showing source.' notice
kind: task
status: closed
priority: 2
version: 3
labels: []
dependencies: []
created_at: 2026-11-13T07:49:19.619Z
updated_at: 2026-11-13T09:02:42.971Z
closed_at: 2026-11-13T09:02:42.970Z
close_reason: "Done in jlevy/metabrowser#394 (cc2392b7, 1962d8d0, fixes through 73dd5cd2): reviews A then B (approve with a Low, fixed). Merges once #390 lands and CI is green."
resolution: null
duplicate_of: null
---
The user, 2026-11-12: the diff viewer sometimes shows 'Rendered diff unavailable. Showing source.' This is superfluous and must be removed completely: rendering or not rendering is a behavior, not something to announce. Stacked on #390's branch with the toggle fix.

## Notes

2026-11-13: jlevy/metabrowser#394, 1962d8d0: both render-fallback notices removed; the fallback is unchanged (failed keeps the chooser for retry); console.warn on failure. Review A running.
