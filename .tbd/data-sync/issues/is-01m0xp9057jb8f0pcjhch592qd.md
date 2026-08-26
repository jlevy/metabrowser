---
type: is
id: is-01m0xp9057jb8f0pcjhch592qd
title: Make retained preview dimming visibly cover the main view
kind: bug
status: in_progress
priority: 1
version: 3
spec_path: docs/project/specs/active/plan-2026-08-25-git-revision-navigation-performance.md
labels: []
dependencies:
  - type: blocks
    target: is-01m0w542g2gzak7th85hx2bdz8
parent_id: is-01m0w52mbqvhdj9r2et2eh9p55
created_at: 2026-08-26T00:07:17.395Z
updated_at: 2026-08-26T00:07:32.169Z
---
User acceptance regression on PR #82. The shared pending class currently reduces only the first preview child's opacity to 0.9. On the real Git view this is not a perceptible gray treatment and leaves the preview background unchanged, so selection gives no clear immediate feedback. Files/functions: src/metabrowser/static/styles.css preview-navigation-pending rules and tokens; src/metabrowser/static/app.js begin/end preview lifecycle only if ownership needs adjustment; tests/test_browser_loading_delay.py and the headed Git scenario. Behavior: the entire main preview surface receives an immediate, subtle neutral veil while retained content stays visible and geometrically stable; nav chrome is not dimmed; the veil clears only at claim-owned painted readiness and reduced motion removes animation without removing state. Acceptance: focused test fails before/fix after, both themes have a visible tokenized gray treatment, pending appears before slow work, stale/error/cancel paths clear it, and real-browser validation passes.
