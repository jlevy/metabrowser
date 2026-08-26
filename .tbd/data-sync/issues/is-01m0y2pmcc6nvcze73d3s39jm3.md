---
type: is
id: is-01m0y2pmcc6nvcze73d3s39jm3
title: Replace retained-view fading with a minimal arrival animation
kind: task
status: closed
priority: 1
version: 6
spec_path: docs/project/specs/active/plan-2026-08-25-git-revision-navigation-performance.md
labels: []
dependencies:
  - type: blocks
    target: is-01m0w542g2gzak7th85hx2bdz8
parent_id: is-01m0w52mbqvhdj9r2et2eh9p55
created_at: 2026-08-26T03:44:27.019Z
updated_at: 2026-08-26T04:27:59.136Z
closed_at: 2026-08-26T04:27:59.129Z
close_reason: "Fixed in 1e1f5d8: retained views and the theme canvas remain unchanged while pending; only incoming foreground content eases from 0.98 to 1 over 50 ms. Focused/full tests, exact-wheel install, light/dark file and Git checks, exact-head headed scenarios, push hooks, and GitHub CI are green."
resolution: null
duplicate_of: null
---
Remove all visible pending-state treatment from retained file and Git views: no gray sheet, fade-out, filter, cursor, or per-element restyling while content loads. Preserve claim-owned aria-busy state, retained-content continuity, exact selection feedback, performance attribution, and painted-readiness clearance. Add one fast compositor-only incoming-view opacity animation at the shared replacement seams, disabled for reduced motion, with no delay to usable content and no forced layout. Pin the behavior and exact timing in focused tests; reconcile docs/design-system.md, the active performance plan, CHANGELOG.md, and PR #82; validate file and Git transitions in both themes, run make format and make verify, commit and push, reinstall the exact global wheel, and leave the trading repo open for comparison.

## Notes

User superseded the 7% pending sheet after testing. Final implementation keeps the retained pane and its light/dark theme background completely unchanged while work is pending, preserves claim-owned aria-busy and timing state, and animates only the newly inserted foreground content root from 0.98 to 1 over 50 ms with ease-out. The Web Animations API path is compositor-only, performs no DOM traversal or style read, avoids CSS class retrigger/forced layout, cancels obsolete arrival motion, and skips animation for reduced motion. Focused tests, format, lint/check-JS, and make verify (1,559 tests plus 48 golden scenarios) pass with CI-pinned uv 0.11.26. The previously pushed b7c4ece is an intermediate state and will be replaced by the final exact build.
