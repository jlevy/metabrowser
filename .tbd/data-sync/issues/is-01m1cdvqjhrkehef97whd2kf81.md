---
type: is
id: is-01m1cdvqjhrkehef97whd2kf81
title: "PR #90 CODE-01: /api/file on a folder returned pending data as success"
kind: bug
status: open
priority: 1
version: 1
labels: []
dependencies: []
parent_id: is-01m1cdvq5dqpv1t2svby05zhx5
created_at: 2026-08-31T17:28:50.512Z
updated_at: 2026-08-31T17:28:50.512Z
---
A folder envelope carries inventory aggregates but /api/file was absent from _INDEX_DEPENDENT. Reproduced: state pending, null totals, HTTP 200, exit 0. The sweep that built the list only requested a file.
