---
type: is
id: is-01m6j8aa93fz82fma0c7vtvtsm
title: Keep shared branch-copy helpers within the startup byte budget
kind: bug
status: closed
priority: 1
version: 6
spec_path: docs/design-system.md
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m6j4m8h98qy2w5w5wj5d46gj
hold: null
hold_until: null
created_at: 2026-11-04T03:05:52.674Z
updated_at: 2026-11-04T17:14:29.582Z
started_at: 2026-11-04T03:09:42.881Z
closed_at: 2026-11-04T17:14:29.582Z
close_reason: "Scoped implementation independently reviewed and tested; owning feature PRs are actually merged. Final main https://github.com/jlevy/metabrowser/commit/db52ec09cf839269da3a56fd396e44f3092995a9 includes account fix https://github.com/jlevy/metabrowser/pull/297 and documentation https://github.com/jlevy/metabrowser/pull/298, with final manual acceptance and per-issue qualifications checked. Individual source, test, review and merge evidence: ACTION-PLAN.json SHA-256 d0867a696ee055cc27911e83c4f70744b419a3ca4a7a1218f0eeaf419dc37589. Future scope and historical dependency relationships remain open or preserved as recorded."
resolution: null
duplicate_of: null
---
Full fifth Make lint-check at local41e4ec6f catches20startuprequests181833bytes versus179711byte175KBbudget,2122bytesover. Shared eagerSDKrefhelpercode caused growth. Preserve fixed budget, allcopy/lifecycle/selection/contrast semantics and readiness; reduce duplication or move genuinely narrow work to an explicit existingon-demand tier onlyafter reviewing actualstartupdependency. No speculativefallbacks/newframework. Originalsemanticreview remainsvalidat41e4; forwardfixmusthave focusedloadingtests/newbytegate/independentreview, no historyrewrite.

## Notes

Resolved in forwardb85cd1f4 on fifthbranch afterfullMake lint-checkPASSexit0/normalhooks. Independent22sourcehashreconciliationclean; actual179380bytes20requests,2453saved,331underunchangedthreshold. Author112affected+15DOMgoldens; independent31loadingtests andoriginalactualChromeclip/Tabproofgreen. Fullsixthaggregategate/artifactacceptance stillpending; keepmerge-onlyclosuretracking.
