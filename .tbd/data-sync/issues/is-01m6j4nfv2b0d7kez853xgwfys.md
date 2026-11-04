---
type: is
id: is-01m6j4nfv2b0d7kez853xgwfys
title: Use shared branch chips throughout Git and PR views
kind: task
status: in_progress
priority: 1
version: 4
spec_path: docs/design-system.md
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m6j4m8h98qy2w5w5wj5d46gj
hold: null
hold_until: null
created_at: 2026-11-04T02:02:04.513Z
updated_at: 2026-11-04T02:56:01.920Z
started_at: 2026-11-04T02:28:29.835Z
---
All structured branch references in Git history, pull history, PR header/list and other places should share the existing dark blue/purple git-ref chips. Use structured base/head data rather than parsing display strings. Retain trunk/tag/HEAD semantics where appropriate and unify size/tokens/tooltip behavior without hiding long refs or breaking row window geometry.

## Notes

Implemented shared SDK refChip/refChipHtml across Git history/summary, PR list/header and source branch/tag selector. Structured base/head raw names remain independent of displayed fork qualification and arrows; local/remote/tag/trunk/HEAD semantics retained. Dense Git history stays micro10; full summary/PR/source chips ui-small12. Focused existing navigation and literal long-ref checks pass; final artifact QA pending.
