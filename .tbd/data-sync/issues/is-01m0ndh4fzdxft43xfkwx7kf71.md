---
type: is
id: is-01m0ndh4fzdxft43xfkwx7kf71
title: Flush the shell head before repository context resolves (H29)
kind: task
status: open
priority: 2
version: 1
spec_path: docs/project/specs/active/plan-2026-08-21-load-time-performance.md
labels: []
dependencies: []
parent_id: is-01m0k5wh7jgr0dgs5y78kwwke1
created_at: 2026-08-22T19:00:31.358Z
updated_at: 2026-08-22T19:00:31.358Z
---
index() blocks its first byte on discover_repository_context (serial, off-thread) and ships one buffered response, so the browser cannot start fetching CSS/JS until the whole page is built. Early-flush the head; move repository context off the pre-first-byte path (late script tag or fetch). Measure with H26's remote setup — on localhost the shell is ~200ms and the win may be invisible. Metric: request-to-first-stylesheet-fetch.
