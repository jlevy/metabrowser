---
type: is
id: is-01kzse0dcec8030qn0akzvar9w
title: Fix listed paths that fail to open and separate file error detail
kind: bug
status: closed
priority: 1
version: 3
labels: []
dependencies: []
parent_id: is-01kzrtbtsh9k6p8x84rta84y4p
created_at: 2026-08-11T22:10:07.885Z
updated_at: 2026-08-11T22:49:22.490Z
closed_at: 2026-08-11T22:49:22.489Z
close_reason: Classified symlinks as non-expanded inventory leaves, added the Lucide leading icon, preserved served-root containment, separated actionable error summary and detail, fixed link-only directory emptiness, and verified locally and in CI.
---
Reproduce and fix the ~/.claude skills path that inventory exposes as navigable but the file endpoint rejects. Preserve safe-path containment, and render the file-open error summary and server detail as distinct UI elements with regression coverage.
