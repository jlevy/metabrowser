---
type: is
id: is-01m022w3jg7wzpcz4vw96tj96k
title: Preserve SDK 0.1 compatibility for existing plugin manifests
kind: bug
status: closed
priority: 1
version: 3
labels: []
dependencies: []
parent_id: is-01m022qgb1r5z8n94ygsjqbnzp
created_at: 2026-08-15T06:48:42.319Z
updated_at: 2026-08-15T06:57:37.829Z
closed_at: 2026-08-15T06:57:37.827Z
close_reason: Preserved the released 0.4.0 manifest contract by pinning omitted sdk_version to SDK 0.1; added a regression test, validated known plugin manifests, documented the boundary, and passed make verify.
---
The v0.4.1 audit found real installed plugin consumers whose manifests omit sdk_version under the v0.4.0 contract. Keep omission pinned to the original SDK 0.1 rather than the moving host version, so current plugins remain compatible while a future SDK bump still fails closed. Add regression coverage and document the compatibility rule.
