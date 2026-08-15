---
type: is
id: is-01m01x5vbrd6cr5vh199c3k50v
title: Increase light-theme saturation for recent file-age text
kind: bug
status: closed
priority: 2
version: 5
spec_path: docs/project/specs/active/plan-2026-07-20-folder-views-and-treemap-overview.md
labels:
  - browser
  - design-system
dependencies: []
parent_id: is-01kxz2z9v1bbfcfmqstffkhvxp
created_at: 2026-08-15T05:09:10.135Z
updated_at: 2026-08-15T06:13:16.545Z
closed_at: 2026-08-15T06:13:16.544Z
close_reason: "Finalized the shared OKLCH file-age palette: Live and under-one-minute use one orange foreground/fill source and bold presentation across the nav menu and file rows, with documentation, contract tests, visual verification, and full CI passing."
---
Increase the chroma and visual prominence of the brighter recent-age text tiers in the centralized light-theme OKLCH palette while preserving the approved salmon Live cue, yellow/gold elapsed-age direction, WCAG AA contrast, dark-theme behavior, and token reuse across every age-bearing surface. Add or update token and contrast tests, validate the live browser, document the durable palette rule, and update PR #44.
