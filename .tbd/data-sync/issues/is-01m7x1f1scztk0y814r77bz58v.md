---
type: is
id: is-01m7x1f1scztk0y814r77bz58v
title: "Cache contract: recent targets move to the state directory; deletion rule 'whenever no metab is running' stated once; CACHEDIR.TAG says it; state dir in Storage Locations and validate_storage_separation; macOS Time Machine exclusion of the cache root; sizes in /api/cache/stores and --doctor; then a --cache listing"
kind: task
status: open
priority: 1
version: 1
labels: []
dependencies: []
created_at: 2026-11-20T17:53:28.363Z
updated_at: 2026-11-20T17:53:28.363Z
---
Owner decisions 2026-11-20 on the cache layout research (attic/cache-layout-research/report.txt): move recent-targets.yml to the state directory (reverses 2026-11-18; nothing released wrote it); the deletion guarantee is 'safe whenever no metab is running' until a prune command with the store lease exists. Also from the report: Time Machine exclusion at creation on macOS, sizes in the stores route and doctor, a --cache listing flag; one vocabulary per layer (section 5.2). Prune/remove comes later with the store lease. The repos/ rename and source-slug respelling ride in mb-dwq7's f03 step.
