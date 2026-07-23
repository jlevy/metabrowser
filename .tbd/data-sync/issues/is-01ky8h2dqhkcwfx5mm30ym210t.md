---
type: is
id: is-01ky8h2dqhkcwfx5mm30ym210t
title: "Bugbot R2-4: re-measure viewport height on container resize"
kind: task
status: closed
priority: 1
version: 2
spec_path: docs/project/specs/active/plan-2026-07-20-folder-views-and-treemap-overview.md
labels: []
dependencies: []
parent_id: is-01kxz2z9v1bbfcfmqstffkhvxp
created_at: 2026-07-23T22:20:52.337Z
updated_at: 2026-07-23T22:23:50.969Z
closed_at: 2026-07-23T22:23:50.969Z
close_reason: "Fixed in commit: active-gate + IntersectionObserver catch-up (vm-tested skip/stale/refresh), pending skeleton via countHtml/formatAge(null), status honesty in hidden mode (vm-tested), RO re-measures height before relayout."
---
ResizeObserver only calls relayout(); a pane-width drag that wraps the toolbar/breadcrumb moves the viewport top without a window resize, leaving a stale inline height. RO callback now runs sizeViewport() before relayout().
