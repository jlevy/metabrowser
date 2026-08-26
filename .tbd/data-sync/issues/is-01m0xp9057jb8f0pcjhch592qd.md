---
type: is
id: is-01m0xp9057jb8f0pcjhch592qd
title: Make retained preview dimming visibly cover the main view
kind: bug
status: closed
priority: 1
version: 6
spec_path: docs/project/specs/active/plan-2026-08-25-git-revision-navigation-performance.md
labels: []
dependencies:
  - type: blocks
    target: is-01m0w542g2gzak7th85hx2bdz8
parent_id: is-01m0w52mbqvhdj9r2et2eh9p55
created_at: 2026-08-26T00:07:17.395Z
updated_at: 2026-08-26T01:16:25.945Z
closed_at: 2026-08-26T01:16:25.944Z
close_reason: Implemented and validated one fixed pointer-transparent preview overlay with a 60 ms transition, claim-owned clearance, reduced-motion behavior, and real-browser pending onset/clearance checks. Three repeated fixed-corpus headed runs observed the sheet within 7.7–18.8 ms with zero blank frames and exact convergence; make verify passes.
resolution: null
duplicate_of: null
---
Implementation uses one fixed, pointer-transparent ::after sheet on #preview-pane, contained to the preview scrollport by the existing preview-pane containment. No descendant filter, opacity, layout, or per-element style work runs during selection. The tokenized neutral sheet appears from the shared claim-owned pending class, leaves nav at full contrast, and clears at painted readiness; reduced motion removes only the fade. Validate in both themes with focused CSS/lifecycle tests and the headed Git scenario's pending onset/clearance checks.

## Notes

Implemented one fixed, pointer-transparent neutral ::after sheet over the contained preview scrollport, with nav left at full contrast and a dedicated 60 ms ease-out opacity transition (instant under reduced motion). Focused CSS/lifecycle tests pass. Headed Git captures observe pending onset and clearance with zero blank frames.
