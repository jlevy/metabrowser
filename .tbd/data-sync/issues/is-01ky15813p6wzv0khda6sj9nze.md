---
type: is
id: is-01ky15813p6wzv0khda6sj9nze
title: "PR13/R6: metric-aware labels and honest interactive semantics"
kind: bug
status: closed
priority: 1
version: 2
spec_path: docs/project/specs/active/plan-2026-07-20-folder-views-and-treemap-overview.md
labels: []
dependencies: []
parent_id: is-01kxz2z9v1bbfcfmqstffkhvxp
created_at: 2026-07-21T01:39:32.085Z
updated_at: 2026-07-21T02:01:48.306Z
closed_at: 2026-07-21T02:01:48.306Z
close_reason: Fixed in the R1-R8 review-response commit (metric-aware aria, actionable-only roles, label-strip buttons, sublabel suppression); geometric arrow-key neighbor selection deferred as polish under mb-ga98's remaining scope
---
Review finding R6: cellAriaLabel always formats bytes (wrong in Files mode); ext/rest cells are focusable no-op buttons; nested dir cells create button-inside-button. Fix: metric-aware aria labels; role=button+tabindex only for actionable cells; nested dir cells become role=group with the label strip as the explicit button; suppress the sublabel on nested parents (also fixes the 16px header overlap). Geometric arrow-key neighbors deferred as follow-up.
