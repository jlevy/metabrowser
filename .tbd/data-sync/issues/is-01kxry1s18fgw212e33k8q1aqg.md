---
type: is
id: is-01kxry1s18fgw212e33k8q1aqg
title: "Review D1: research doc omits plugin-platform prerequisites (routing, SDK verbs, event bus, UI mount, subprocess runner)"
kind: task
status: open
priority: 1
version: 1
labels: []
dependencies: []
parent_id: is-01kxry18kdjj6xk8nkz4bs4ba6
created_at: 2026-07-17T20:59:51.720Z
updated_at: 2026-07-17T20:59:51.720Z
---
Doc claims installed-plugin home but data hooks are single-segment GET/POST (manifest.py:171-185), SDK fetchPluginData GET/JSON-only (plugin_sdk.js:141-167), event bus not in plugin_api, no repo-scoped view mount (views bind to file kinds; /api/file rejects dirs server.py:1130), no subprocess infra. Add Platform Prerequisites subsection + fold into Phase 0.
