---
type: is
id: is-01m0f0328mjzvbwd41wtmeykpz
title: "PR #58 review R10: Diff view discards server error payloads the SDK preserves; render payload"
kind: bug
status: closed
priority: 2
version: 2
labels: []
dependencies: []
parent_id: is-01m0f02zaw865q3swdc9xvmdb9
created_at: 2026-08-20T07:10:12.243Z
updated_at: 2026-08-20T07:35:58.032Z
closed_at: 2026-08-20T07:35:58.031Z
close_reason: "R10 fixed in c0ae341: the view renders err.payload.message and logs the raw error; refresh advice only as fallback"
---
PR #58, review 4979975854, finding R10. Diff view discards server error payloads the SDK preserves; render payload.message, drop refresh advice for 4xx. index.js:40-42
