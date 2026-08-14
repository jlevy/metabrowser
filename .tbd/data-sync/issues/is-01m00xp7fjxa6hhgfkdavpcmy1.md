---
type: is
id: is-01m00xp7fjxa6hhgfkdavpcmy1
title: Replace red file-age ramp with yellow-to-neutral freshness palette
kind: feature
status: open
priority: 2
version: 1
spec_path: docs/project/specs/active/plan-2026-07-20-folder-views-and-treemap-overview.md
labels:
  - browser
  - design-system
dependencies: []
parent_id: is-01kxz2z9v1bbfcfmqstffkhvxp
created_at: 2026-08-14T19:58:52.401Z
updated_at: 2026-08-14T19:58:52.401Z
---
Design and implement a coherent file-age palette without changing the existing six age thresholds or public age bucket names. Sample one continuous freshness curve from saturated golden yellow through yellow-olive and moss to a low-saturation green-gray neutral. Live aliases the under-one-minute foreground token; its label, dot, or motion conveys live state rather than a separate hue. Reserve red for destructive and error states, and keep success green semantically independent from freshness. Retune light and dark foreground and fill tokens for contrast on actual Metabrowser surfaces, remove the menu-specific age-min color workaround, update design documentation and CSS comments, and add automated contrast coverage plus behavior checks for filter and plugin-SDK mappings. This bead records the reviewed proposal only; implementation has not started.
