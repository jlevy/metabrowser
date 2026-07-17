---
type: is
id: is-01kxry1s18fgw212e33k8q1aqg
title: "Review D1: research doc omits plugin-platform prerequisites (routing, SDK verbs, event bus, UI mount, subprocess runner)"
kind: task
status: closed
priority: 1
version: 2
labels: []
dependencies: []
parent_id: is-01kxry18kdjj6xk8nkz4bs4ba6
created_at: 2026-07-17T20:59:51.720Z
updated_at: 2026-07-17T21:04:55.376Z
closed_at: 2026-07-17T21:04:55.376Z
close_reason: "Addressed in commit cc92da0 on the diff-research branch: platform prerequisites section + Phase 0 fold-in, packaging-reality paragraph, self-describing comparison IDs, git adapter safety additions, tool-surface and tree-decoration open decisions, docs-tree conventions in development.md. make verify green (705 tests)."
---
Doc claims installed-plugin home but data hooks are single-segment GET/POST (manifest.py:171-185), SDK fetchPluginData GET/JSON-only (plugin_sdk.js:141-167), event bus not in plugin_api, no repo-scoped view mount (views bind to file kinds; /api/file rejects dirs server.py:1130), no subprocess infra. Add Platform Prerequisites subsection + fold into Phase 0.
