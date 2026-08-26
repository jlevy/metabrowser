---
type: is
id: is-01m0xp9057jb8f0pcjhch592qd
title: Make retained preview dimming visibly cover the main view
kind: bug
status: in_progress
priority: 1
version: 5
spec_path: docs/project/specs/active/plan-2026-08-25-git-revision-navigation-performance.md
labels: []
dependencies:
  - type: blocks
    target: is-01m0w542g2gzak7th85hx2bdz8
parent_id: is-01m0w52mbqvhdj9r2et2eh9p55
created_at: 2026-08-26T00:07:17.395Z
updated_at: 2026-08-26T01:04:36.557Z
---
Implementation uses one fixed, pointer-transparent ::after sheet on #preview-pane, contained to the preview scrollport by the existing preview-pane containment. No descendant filter, opacity, layout, or per-element style work runs during selection. The tokenized neutral sheet appears from the shared claim-owned pending class, leaves nav at full contrast, and clears at painted readiness; reduced motion removes only the fade. Validate in both themes with focused CSS/lifecycle tests and the headed Git scenario's pending onset/clearance checks.

## Notes

Implemented one fixed, pointer-transparent neutral ::after sheet over the contained preview scrollport, with nav left at full contrast and a dedicated 60 ms ease-out opacity transition (instant under reduced motion). Focused CSS/lifecycle tests pass. Headed Git captures observe pending onset and clearance with zero blank frames.
