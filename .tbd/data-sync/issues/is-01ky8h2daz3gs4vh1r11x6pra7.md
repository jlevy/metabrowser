---
type: is
id: is-01ky8h2daz3gs4vh1r11x6pra7
title: "Bugbot R2-3: treemap status line must honor hidden gitignored mode"
kind: task
status: closed
priority: 2
version: 2
spec_path: docs/project/specs/active/plan-2026-07-20-folder-views-and-treemap-overview.md
labels: []
dependencies: []
parent_id: is-01kxz2z9v1bbfcfmqstffkhvxp
created_at: 2026-07-23T22:20:51.935Z
updated_at: 2026-07-23T22:23:50.966Z
closed_at: 2026-07-23T22:23:50.966Z
close_reason: "Fixed in commit: active-gate + IntersectionObserver catch-up (vm-tested skip/stale/refresh), pending skeleton via countHtml/formatAge(null), status honesty in hidden mode (vm-tested), RO re-measures height before relayout."
---
With ignored=hidden the cells lay out from unignored_* weights but the footer prints total_files/total_size. statusHtml takes the toggle state and reports unignored figures plus an explicit 'gitignored hidden' note in hidden mode.
