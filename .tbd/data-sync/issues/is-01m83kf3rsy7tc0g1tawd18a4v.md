---
type: is
id: is-01m83kf3rsy7tc0g1tawd18a4v
title: A folder page's reveal of a stale origin store shows Refreshing; make that fetch quiet
kind: task
status: in_progress
priority: 2
version: 2
spec_path: docs/project/specs/active/plan-2026-11-22-pull-request-update-cadence.md
delegate: claude-code@spud10
labels:
  - review
dependencies: []
parent_id: is-01m82h0qrnw9vg6vrj597asgpv
hold: null
hold_until: null
created_at: 2026-11-23T07:03:31.340Z
updated_at: 2026-11-23T07:13:29.657Z
started_at: 2026-11-23T07:13:29.647Z
---
PR #740 review A, finding A3 (Medium). static/source-freshness.js poll() sends POST /api/source/refresh {} once per visible period when status.stale, which is a reader's refresh (MirrorSession.request_refresh), so the row paints and announces Refreshing. A folder's store is stale after FRESHNESS_WINDOW_S and the idle timer keeps it only STORE_IDLE_REFRESH_S old, so most reveals of a folder page show it, though nothing on a working-tree page depends on the store. Recommendation: for a folder page with nothing of the store served (checkout and follows false), send {"for": "page"} instead, which StoreSession.page_ask answers with a quiet fetch (refresh_quiet) and holds after a failure; keep the visible refresh for the Refresh button and for a page on an origin branch. Update the folder part of cli-ui-source-freshness.tryscript.md.
