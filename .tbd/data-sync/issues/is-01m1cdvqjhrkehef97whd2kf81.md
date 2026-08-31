---
type: is
id: is-01m1cdvqjhrkehef97whd2kf81
title: "PR #90 CODE-01: /api/file on a folder returned pending data as success"
kind: bug
status: closed
priority: 1
version: 2
labels: []
dependencies: []
parent_id: is-01m1cdvq5dqpv1t2svby05zhx5
created_at: 2026-08-31T17:28:50.512Z
updated_at: 2026-08-31T17:29:11.096Z
closed_at: 2026-08-31T17:29:11.095Z
close_reason: "Fixed in 501b31b; see the disposition map on PR #90."
resolution: null
duplicate_of: null
---
A folder envelope carries inventory aggregates but /api/file was absent from _INDEX_DEPENDENT. Reproduced: state pending, null totals, HTTP 200, exit 0. The sweep that built the list only requested a file.
