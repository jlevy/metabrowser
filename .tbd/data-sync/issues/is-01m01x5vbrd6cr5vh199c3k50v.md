---
type: is
id: is-01m01x5vbrd6cr5vh199c3k50v
title: Increase light-theme saturation for recent file-age text
kind: bug
status: closed
priority: 2
version: 3
spec_path: docs/project/specs/active/plan-2026-07-20-folder-views-and-treemap-overview.md
labels:
  - browser
  - design-system
dependencies: []
parent_id: is-01kxz2z9v1bbfcfmqstffkhvxp
created_at: 2026-08-15T05:09:10.135Z
updated_at: 2026-08-15T05:33:37.836Z
closed_at: 2026-08-15T05:33:37.835Z
close_reason: Restored the approved salmon-and-yellow light-theme file-age ramp exactly in OKLCH, documented it, and pinned it with a regression contract; make verify and PR CI pass.
---
Increase the chroma and visual prominence of the brighter recent-age text tiers in the centralized light-theme OKLCH palette while preserving the approved salmon Live cue, yellow/gold elapsed-age direction, WCAG AA contrast, dark-theme behavior, and token reuse across every age-bearing surface. Add or update token and contrast tests, validate the live browser, document the durable palette rule, and update PR #44.
