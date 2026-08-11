---
type: is
id: is-01ky8h2cygce1xzb0b2ar0m1wf
title: "Bugbot R2-2: pending folder age must show the tally skeleton"
kind: task
status: closed
priority: 2
version: 2
spec_path: docs/project/specs/active/plan-2026-07-20-folder-views-and-treemap-overview.md
labels: []
dependencies: []
parent_id: is-01kxz2z9v1bbfcfmqstffkhvxp
created_at: 2026-07-23T22:20:51.536Z
updated_at: 2026-07-23T22:23:50.962Z
closed_at: 2026-07-23T22:23:50.962Z
close_reason: "Fixed in commit: active-gate + IntersectionObserver catch-up (vm-tested skip/stale/refresh), pending skeleton via countHtml/formatAge(null), status honesty in hidden mode (vm-tested), RO re-measures height before relayout."
---
folderHeaderSummaryHtml passes mtime ?? 0 into formatAge, so a pending dir (mtime null) renders a blank instead of the tally-pending skeleton; also use countHtml for the count so pending counts skeleton too.
