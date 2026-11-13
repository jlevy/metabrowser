---
type: is
id: is-01m79y3sm47m0r6f6trv9m90mr
title: Remove the 'Rendered diff unavailable. Showing source.' notice
kind: task
status: open
priority: 2
version: 1
labels: []
dependencies: []
created_at: 2026-11-13T07:49:19.619Z
updated_at: 2026-11-13T07:49:19.619Z
---
The user, 2026-11-12: the diff viewer sometimes shows 'Rendered diff unavailable. Showing source.' This is superfluous and must be removed completely: rendering or not rendering is a behavior, not something to announce. Stacked on #390's branch with the toggle fix.
