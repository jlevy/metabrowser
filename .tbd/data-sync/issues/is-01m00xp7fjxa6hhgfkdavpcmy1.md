---
type: is
id: is-01m00xp7fjxa6hhgfkdavpcmy1
title: Replace red file-age ramp with yellow-to-neutral freshness palette
kind: feature
status: open
priority: 2
version: 2
spec_path: docs/project/specs/active/plan-2026-07-20-folder-views-and-treemap-overview.md
labels:
  - browser
  - design-system
dependencies: []
parent_id: is-01kxz2z9v1bbfcfmqstffkhvxp
created_at: 2026-08-14T19:58:52.401Z
updated_at: 2026-08-14T20:28:32.420Z
---
Design and implement one coherent, shared file-age color system across every age presentation: navigation rows, recent-filter and dropdown menus, file listings, plugins, badges, and any age-derived foreground or fill. Preserve the existing six time thresholds and public age bucket names. Add a presentation-only Live modifier in a distinct warm salmon family; all non-live ages must remain in a yellow-to-dark-neutral family with saturation and prominence decaying as age increases, never drifting into pink or red. On light surfaces, pair an accessible dark foreground with a small high-chroma marker or accent token so fresh yellow remains visibly yellow; use the same semantic pairing in dark mode. Keep destructive error red deeper and visibly separate from Live salmon, and keep success green independent. Remove menu-specific color workarounds, retune foreground and fill tokens centrally, update design documentation and CSS comments, and add automated contrast coverage plus behavior checks for filters and the plugin SDK. This bead records the reviewed proposal only; implementation has not started.
