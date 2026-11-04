---
type: is
id: is-01m6j8aa93fz82fma0c7vtvtsm
title: Keep shared branch-copy helpers within the startup byte budget
kind: bug
status: in_progress
priority: 1
version: 2
spec_path: docs/design-system.md
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m6j4m8h98qy2w5w5wj5d46gj
hold: null
hold_until: null
created_at: 2026-11-04T03:05:52.674Z
updated_at: 2026-11-04T03:09:42.882Z
started_at: 2026-11-04T03:09:42.881Z
---
Full fifth Make lint-check at local41e4ec6f catches20startuprequests181833bytes versus179711byte175KBbudget,2122bytesover. Shared eagerSDKrefhelpercode caused growth. Preserve fixed budget, allcopy/lifecycle/selection/contrast semantics and readiness; reduce duplication or move genuinely narrow work to an explicit existingon-demand tier onlyafter reviewing actualstartupdependency. No speculativefallbacks/newframework. Originalsemanticreview remainsvalidat41e4; forwardfixmusthave focusedloadingtests/newbytegate/independentreview, no historyrewrite.
