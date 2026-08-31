---
type: is
id: is-01m1apk83pwwfrc6pcgyda271k
title: "PR #90 P90-18: --data with an empty file silently issues a GET"
kind: bug
status: closed
priority: 3
version: 2
labels: []
dependencies: []
parent_id: is-01m1apk016z6h7ms919ekta9z0
created_at: 2026-08-31T01:23:00.853Z
updated_at: 2026-08-31T01:40:12.995Z
closed_at: 2026-08-31T01:40:12.995Z
close_reason: "Fixed on feat/cli-parity-mechanism; see the disposition map on PR #90."
resolution: null
duplicate_of: null
---
An empty body falls through to the GET path with no diagnostic.
