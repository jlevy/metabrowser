---
type: is
id: is-01kxry3135peyv0t9xedrxsavz
title: "Platform A2: SDK data-plane v2 — POST bodies, streaming/NDJSON, SSE helper wired to view disposal"
kind: feature
status: closed
priority: 1
version: 6
labels: []
dependencies:
  - type: blocks
    target: is-01kxse0vt4cyng7mvtr3hk2rct
parent_id: is-01kxry18kdjj6xk8nkz4bs4ba6
created_at: 2026-07-17T21:00:32.741Z
updated_at: 2026-11-20T19:15:57.200Z
closed_at: 2026-11-14T18:43:19.619Z
close_reason: "Superseded: the diff viewer became a built-in plugin, mb-qatc shipped without this, and the thin-mirror plan (PR #227) retired new public SDK surface for it; reopen under mb-xbw3 if a third-party plugin needs a POST/streaming data plane."
resolution: canceled
duplicate_of: null
extensions: {}
---
fetchPluginData is GET-only query-param JSON (plugin_sdk.js:141-167); add fetchPluginResponse + EventSource helper returning a disposer.
