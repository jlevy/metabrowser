---
type: is
id: is-01m6j4nfv2b0d7kez853xgwfys
title: Use shared branch chips throughout Git and PR views
kind: task
status: in_progress
priority: 1
version: 2
spec_path: docs/design-system.md
labels: []
dependencies: []
parent_id: is-01m6j4m8h98qy2w5w5wj5d46gj
created_at: 2026-11-04T02:02:04.513Z
updated_at: 2026-11-04T02:02:05.034Z
---
All structured branch references in Git history, pull history, PR header/list and other places should share the existing dark blue/purple git-ref chips. Use structured base/head data rather than parsing display strings. Retain trunk/tag/HEAD semantics where appropriate and unify size/tokens/tooltip behavior without hiding long refs or breaking row window geometry.
