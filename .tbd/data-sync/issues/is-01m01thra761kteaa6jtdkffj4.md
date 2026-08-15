---
type: is
id: is-01m01thra761kteaa6jtdkffj4
title: Add hover feedback to tooltip-bearing composition segments
kind: feature
status: closed
priority: 2
version: 3
spec_path: docs/project/specs/done/plan-2026-08-12-directory-file-type-summary.md
labels:
  - browser
  - design-system
dependencies: []
parent_id: is-01kxz2z9v1bbfcfmqstffkhvxp
created_at: 2026-08-15T04:23:14.502Z
updated_at: 2026-08-15T04:37:25.980Z
closed_at: 2026-08-15T04:37:25.979Z
close_reason: Added and documented a shared categorical data-mark hover token, applied it to tooltip-bearing file composition segments and Treemap cells, covered both CSS contracts, verified live tooltip/hover behavior, and passed make verify.
---
Add a subtle theme-aware hover treatment to Files and Ignored semantic composition segments that expose shared tooltips. Fit the treatment into existing non-button hover conventions, preserve category identity and segment/border contrast, support reduced motion, cover the CSS contract with TDD, and document the reusable design-system rule.
