---
type: is
id: is-01kxry3135peyv0t9xedrxsavz
title: "Platform A2: SDK data-plane v2 — POST bodies, streaming/NDJSON, SSE helper wired to view disposal"
kind: feature
status: open
priority: 1
version: 2
labels: []
dependencies:
  - type: blocks
    target: is-01kxse0vt4cyng7mvtr3hk2rct
parent_id: is-01kxry18kdjj6xk8nkz4bs4ba6
created_at: 2026-07-17T21:00:32.741Z
updated_at: 2026-07-18T01:39:20.841Z
---
fetchPluginData is GET-only query-param JSON (plugin_sdk.js:141-167); add fetchPluginResponse + EventSource helper returning a disposer.
