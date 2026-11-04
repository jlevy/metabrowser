---
type: is
id: is-01ky8h2dqhkcwfx5mm30ym210t
title: "Bugbot R2-4: re-measure viewport height on container resize"
kind: task
status: closed
priority: 1
version: 3
spec_path: docs/project/specs/done/plan-2026-08-12-directory-file-type-summary.md
labels: []
dependencies: []
parent_id: is-01kxz2z9v1bbfcfmqstffkhvxp
created_at: 2026-07-23T22:20:52.337Z
updated_at: 2026-11-04T17:07:22.868Z
closed_at: 2026-07-23T22:23:50.969Z
close_reason: "Fixed in commit: active-gate + IntersectionObserver catch-up (vm-tested skip/stale/refresh), pending skeleton via countHtml/formatAge(null), status honesty in hidden mode (vm-tested), RO re-measures height before relayout."
---
ResizeObserver only calls relayout(); a pane-width drag that wraps the toolbar/breadcrumb moves the viewport top without a window resize, leaving a stale inline height. RO callback now runs sizeViewport() before relayout().
