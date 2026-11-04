---
type: is
id: is-01m6j4nfv2b0d7kez853xgwfys
title: Use shared branch chips throughout Git and PR views
kind: task
status: closed
priority: 1
version: 5
spec_path: docs/design-system.md
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m6j4m8h98qy2w5w5wj5d46gj
hold: null
hold_until: null
created_at: 2026-11-04T02:02:04.513Z
updated_at: 2026-11-04T17:14:29.448Z
started_at: 2026-11-04T02:28:29.835Z
closed_at: 2026-11-04T17:14:29.448Z
close_reason: "Scoped implementation independently reviewed and tested; owning feature PRs are actually merged. Final main https://github.com/jlevy/metabrowser/commit/db52ec09cf839269da3a56fd396e44f3092995a9 includes account fix https://github.com/jlevy/metabrowser/pull/297 and documentation https://github.com/jlevy/metabrowser/pull/298, with final manual acceptance and per-issue qualifications checked. Individual source, test, review and merge evidence: ACTION-PLAN.json SHA-256 d0867a696ee055cc27911e83c4f70744b419a3ca4a7a1218f0eeaf419dc37589. Future scope and historical dependency relationships remain open or preserved as recorded."
resolution: null
duplicate_of: null
---
All structured branch references in Git history, pull history, PR header/list and other places should share the existing dark blue/purple git-ref chips. Use structured base/head data rather than parsing display strings. Retain trunk/tag/HEAD semantics where appropriate and unify size/tokens/tooltip behavior without hiding long refs or breaking row window geometry.

## Notes

Implemented shared SDK refChip/refChipHtml across Git history/summary, PR list/header and source branch/tag selector. Structured base/head raw names remain independent of displayed fork qualification and arrows; local/remote/tag/trunk/HEAD semantics retained. Dense Git history stays micro10; full summary/PR/source chips ui-small12. Focused existing navigation and literal long-ref checks pass; final artifact QA pending.
