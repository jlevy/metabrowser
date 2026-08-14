---
type: is
id: is-01m019a6s7sv3538e6cwqzyd3q
title: Restore light-theme recent file prominence
kind: bug
status: closed
priority: 1
version: 3
spec_path: docs/project/specs/active/plan-2026-07-20-folder-views-and-treemap-overview.md
labels:
  - browser
  - design-system
dependencies: []
parent_id: is-01kxz2z9v1bbfcfmqstffkhvxp
created_at: 2026-08-14T23:22:01.372Z
updated_at: 2026-08-14T23:30:41.421Z
closed_at: 2026-08-14T23:30:41.420Z
close_reason: Restored light-theme recent-age prominence with a wider contrast-safe OKLCH ramp, added perceptual separation regression coverage, updated the design-system contract, validated the live light render, and passed make verify.
---
The approved yellow-to-neutral age ramp is rendered too dull in light mode: recent entries visually collapse toward the one-week tier. Diagnose the actual shared tokens against the prior branch and approved intent, then restore strong but readable chroma/prominence for Live, under one hour, and under one day while retaining the approved salmon-only Live hue, yellow elapsed-age family, OKLCH system, text-only cue, and WCAG AA contrast. Apply centrally to all consumers, update focused palette tests and current design docs, validate in the live light theme, and update PR #44.
